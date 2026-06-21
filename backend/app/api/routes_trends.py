import json
from typing import Optional

from fastapi import APIRouter, Query

from app.constants import is_countable_emotion
from app.db import get_conn
from app.schemas import TrendPoint

router = APIRouter()

THRESHOLD = 0.2

_STRFTIME = {
    "1h": "%Y-%m-%dT%H:00:00",
    "1d": "%Y-%m-%d",
    "1w": "%Y-%W",
}


@router.get("/trends", response_model=list[TrendPoint])
def get_trends(
    category: Optional[str] = Query(None),
    emotions: Optional[str] = Query(None),   # comma-separated
    granularity: str = Query("1d"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    fmt = _STRFTIME.get(granularity, "%Y-%m-%d")
    emotion_list = [e.strip() for e in emotions.split(",")] if emotions else []

    sql = (
        "SELECT h.published_at, e.emotion_probs "
        "FROM headlines h "
        "JOIN emotion_results e ON h.id = e.headline_id "
        "WHERE 1=1"
    )
    params: list = []

    if category:
        sql += " AND h.category = ?"
        params.append(category)
    if start:
        sql += " AND h.published_at >= ?"
        params.append(start)
    if end:
        sql += " AND h.published_at <= ?"
        params.append(end)

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    # bucket → emotion → count
    from collections import defaultdict
    import re
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in rows:
        pub = row["published_at"]
        # derive bucket label from ISO timestamp
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(pub)
            if granularity == "1h":
                bucket = dt.strftime("%Y-%m-%dT%H:00:00")
            elif granularity == "1w":
                bucket = dt.strftime("%Y-%m-%d")[:10]  # week-level: use start of week
                # round down to Monday
                bucket = (dt - __import__("datetime").timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
            else:
                bucket = dt.strftime("%Y-%m-%d")
        except Exception:
            bucket = pub[:10]

        probs = json.loads(row["emotion_probs"])
        for em, prob in probs.items():
            if emotion_list and em not in emotion_list:
                continue
            if is_countable_emotion(probs, em, THRESHOLD):
                buckets[bucket][em] += 1

    result = []
    for date in sorted(buckets.keys()):
        for em, count in buckets[date].items():
            result.append(TrendPoint(date=date, emotion=em, count=count))

    return result
