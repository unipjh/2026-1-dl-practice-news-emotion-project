"""
CLI: python -m app.crawler.backfill
"""
import os
import re
import sys
from email.utils import parsedate_to_datetime
from pathlib import Path

# .env 로드 (백엔드 루트 기준)
_backend_root = Path(__file__).resolve().parents[3]
_env_file = _backend_root / ".env"

if _env_file.exists():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

from app.db import init_db, get_conn
from app.crawler.naver_api import search_news
from app.crawler.publisher_map import identify_publisher

CATEGORY_KEYWORDS = {
    "정치": ["정치", "국회", "대통령"],
    "경제": ["경제", "증시", "물가"],
    "사회": ["사회", "사건", "재판"],
    "문화": ["문화", "공연", "전시"],
}

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def clean_text(s: str) -> str:
    s = _TAG_RE.sub("", s)
    return _SPACE_RE.sub(" ", s).strip()


def parse_published_at(pub_date: str) -> str:
    try:
        dt = parsedate_to_datetime(pub_date)
        return dt.isoformat()
    except Exception:
        return pub_date


def run_backfill():
    init_db()
    total_inserted = 0
    total_skipped = 0

    with get_conn() as conn:
        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                print(f"[backfill] {category} / {keyword}")
                for start in range(1, 902, 100):
                    items = search_news(keyword, start=start, display=100)
                    if not items:
                        break
                    for item in items:
                        url = item.get("link", "").strip()
                        originallink = item.get("originallink", url).strip()
                        headline = clean_text(item.get("title", ""))
                        published_at = parse_published_at(item.get("pubDate", ""))
                        publisher = identify_publisher(originallink)

                        if not headline or not url:
                            continue

                        try:
                            cursor = conn.execute(
                                "INSERT OR IGNORE INTO headlines "
                                "(headline, category, publisher, published_at, url) "
                                "VALUES (?, ?, ?, ?, ?)",
                                (headline, category, publisher, published_at, url),
                            )
                            if cursor.rowcount:
                                total_inserted += 1
                            else:
                                total_skipped += 1
                        except Exception as e:
                            print(f"[backfill] insert error: {e}")

    print(f"[backfill] done — inserted: {total_inserted}, skipped (dup): {total_skipped}")


if __name__ == "__main__":
    run_backfill()
