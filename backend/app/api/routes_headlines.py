import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.constants import NEUTRAL_LABEL, is_countable_emotion
from app.db import get_conn
from app.schemas import HeadlineItem

router = APIRouter()

THRESHOLD = 0.3


@router.get("/headlines", response_model=list[HeadlineItem])
def get_headlines(
    category: Optional[str] = Query(None),
    publisher: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    emotion: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200000),
):
    # List endpoint: omit attention_weights to reduce response size
    sql = (
        "SELECT h.id, h.headline, h.url, h.category, h.publisher, h.published_at, "
        "e.emotion_probs "
        "FROM headlines h "
        "JOIN emotion_results e ON h.id = e.headline_id "
        "WHERE 1=1"
    )
    params: list = []

    if category:
        sql += " AND h.category = ?"
        params.append(category)
    if publisher:
        sql += " AND h.publisher = ?"
        params.append(publisher)
    if start:
        sql += " AND h.published_at >= ?"
        params.append(start)
    if end:
        sql += " AND h.published_at <= ?"
        params.append(end)
    if emotion and emotion != NEUTRAL_LABEL:
        safe = emotion.replace('"', '""')
        sql += f" AND json_extract(e.emotion_probs, '$.\"{ safe }\"') >= ?"
        params.append(THRESHOLD)

    sql += " ORDER BY h.published_at DESC"

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    result = []
    for row in rows:
        probs = json.loads(row["emotion_probs"])
        if emotion and not is_countable_emotion(probs, emotion, THRESHOLD):
            continue
        emotions = {
            k: v for k, v in probs.items()
            if is_countable_emotion(probs, k, THRESHOLD)
        }
        top_emotion = max(probs, key=probs.get) if probs else None
        result.append(HeadlineItem(
            id=row["id"],
            headline=row["headline"],
            url=row["url"],
            category=row["category"],
            publisher=row["publisher"],
            published_at=row["published_at"],
            emotions=emotions,
            top_emotion=top_emotion,
        ))
        if len(result) >= limit:
            break
    return result


@router.get("/headlines/{headline_id}")
def get_headline_detail(headline_id: int):
    """Single headline with full emotion probs and attention weights."""
    sql = (
        "SELECT h.id, h.headline, h.url, h.category, h.publisher, h.published_at, "
        "e.emotion_probs, e.attention_weights "
        "FROM headlines h "
        "JOIN emotion_results e ON h.id = e.headline_id "
        "WHERE h.id = ?"
    )
    with get_conn() as conn:
        row = conn.execute(sql, [headline_id]).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    probs = json.loads(row["emotion_probs"])
    attn = json.loads(row["attention_weights"]) if row["attention_weights"] else []
    top_emotion = max(probs, key=probs.get) if probs else None
    return {
        "id": row["id"],
        "headline": row["headline"],
        "url": row["url"],
        "category": row["category"],
        "publisher": row["publisher"],
        "published_at": row["published_at"],
        "emotions": probs,
        "top_emotion": top_emotion,
        "attention_weights": attn,
    }
