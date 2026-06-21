import json
from typing import Optional

from fastapi import APIRouter, Query

from app.constants import is_countable_emotion
from app.db import get_conn
from app.schemas import DistributionItem

router = APIRouter()

THRESHOLD = 0.2


@router.get("/distribution", response_model=list[DistributionItem])
def get_distribution(
    category: Optional[str] = Query(None),
    publisher: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    sql = (
        "SELECT e.emotion_probs "
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

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    from collections import defaultdict
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        probs = json.loads(row["emotion_probs"])
        for em, prob in probs.items():
            if is_countable_emotion(probs, em, THRESHOLD):
                counts[em] += 1

    total = sum(counts.values())
    result = [
        DistributionItem(
            emotion=em,
            count=cnt,
            ratio=round(cnt / total, 4) if total else 0.0,
        )
        for em, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True)
    ]
    return result
