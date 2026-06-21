import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.db import get_conn
from app.crawler.naver_api import search_news
from app.crawler.publisher_map import identify_publisher
from app.crawler.rss_crawler import fetch_rss_items

CATEGORY_KEYWORDS = {
    "정치": ["정치", "국회", "대통령"],
    "경제": ["경제", "증시", "물가"],
    "사회": ["사회", "사건", "재판"],
    "문화": ["문화", "공연", "전시"],
}

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")

KST = timezone(timedelta(hours=9))

_scheduler = None


def _clean(s: str) -> str:
    return _SPACE_RE.sub(" ", _TAG_RE.sub("", s)).strip()


def _insert_items(conn, items: list[dict]) -> int:
    """헤드라인 목록을 DB에 삽입. 삽입된 신규 건수 반환."""
    inserted = 0
    for item in items:
        if not item.get("headline") or not item.get("url"):
            continue
        try:
            cur = conn.execute(
                "INSERT OR IGNORE INTO headlines "
                "(headline, category, publisher, published_at, url) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    item["headline"],
                    item["category"],
                    item["publisher"],
                    item["published_at"],
                    item["url"],
                ),
            )
            if cur.rowcount:
                inserted += 1
        except Exception:
            pass
    return inserted


def crawl_recent():
    naver_inserted = 0
    rss_inserted = 0

    with get_conn() as conn:
        # ── 1. Naver API (카테고리 × 키워드, 최신 100건) ──────────────────
        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                raw_items = search_news(keyword, start=1, display=100)
                naver_items = []
                for item in raw_items:
                    url = item.get("link", "").strip()
                    originallink = item.get("originallink", url).strip()
                    headline = _clean(item.get("title", ""))
                    if not headline or not url:
                        continue
                    try:
                        pub_date = item.get("pubDate", "")
                        published_at = parsedate_to_datetime(pub_date).isoformat() if pub_date else ""
                    except Exception:
                        published_at = ""
                    naver_items.append({
                        "headline": headline,
                        "url": url,
                        "published_at": published_at,
                        "publisher": identify_publisher(originallink),
                        "category": category,
                    })
                naver_inserted += _insert_items(conn, naver_items)

        # ── 2. RSS 피드 (23개 언론사, 카테고리 자동 감지) ──────────────────
        try:
            rss_items = fetch_rss_items()
            rss_inserted = _insert_items(conn, rss_items)
        except Exception as e:
            print(f"[crawl_recent] RSS error: {e}")

        # ── 3. 미추론 건수 확인 ────────────────────────────────────────────
        pending = conn.execute(
            "SELECT COUNT(*) FROM headlines h "
            "LEFT JOIN emotion_results e ON h.id = e.headline_id "
            "WHERE e.headline_id IS NULL"
        ).fetchone()[0]

    print(
        f"[crawl_recent] naver={naver_inserted} rss={rss_inserted} "
        f"total_new={naver_inserted + rss_inserted} pending_inference={pending}"
    )

    if pending > 0:
        try:
            from app.inference.predict import run_all
            run_all()
        except Exception as e:
            print(f"[crawl_recent] inference error: {e}")

    now_kst = datetime.now(KST).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE crawler_meta SET value=? WHERE key='last_crawled_at'",
            (now_kst,),
        )
    print(f"[crawl_recent] done at {now_kst}")


def get_last_crawled_at() -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM crawler_meta WHERE key='last_crawled_at'"
        ).fetchone()
    return row["value"] if row else None


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(crawl_recent, "interval", minutes=10, id="crawl_recent")
    _scheduler.start()
    print("[scheduler] started — crawl_recent every 10 minutes")
