"""
RSS 기반 뉴스 크롤러

스케줄러에서 주기적으로 호출됨.
requests로 XML 먼저 수신 → feedparser로 파싱 → 카테고리 자동 감지 → DB 저장.
(feedparser 직접 URL 호출 시 리디렉트/User-Agent 처리 불안정하므로 requests 선행)
"""
import re
import time
from datetime import datetime, timezone, timedelta

import feedparser
import requests

from app.crawler.publisher_map import identify_publisher
from app.text_preprocess import preprocess_headline

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}

KST = timezone(timedelta(hours=9))

# ─── RSS 피드 목록 ────────────────────────────────────────────────────────────
# (url, publisher, category | None)
# category=None → 헤드라인 키워드로 자동 감지
# 동작 확인된 피드만 포함 (feedparser + User-Agent 기준)

RSS_FEEDS: list[tuple[str, str, str | None]] = [
    # 연합뉴스 (카테고리별 — 가장 안정적)
    ("https://www.yna.co.kr/rss/politics.xml",      "연합뉴스", "정치"),
    ("https://www.yna.co.kr/rss/economy.xml",       "연합뉴스", "경제"),
    ("https://www.yna.co.kr/rss/society.xml",       "연합뉴스", "사회"),
    ("https://www.yna.co.kr/rss/culture.xml",       "연합뉴스", "문화"),
    ("https://www.yna.co.kr/rss/international.xml", "연합뉴스", "국제"),
    ("https://www.yna.co.kr/rss/sports.xml",        "연합뉴스", "문화"),
    # 한겨레 (전체, 자동 분류)
    ("https://www.hani.co.kr/rss/", "한겨레", None),
    # 경향신문 (전체)
    ("https://www.khan.co.kr/rss/rssdata/total_news.xml", "경향신문", None),
    # 동아일보 (전체)
    ("https://rss.donga.com/total.xml", "동아일보", None),
    # JTBC (전체)
    ("https://fs.jtbc.co.kr/RSS/newsflash.xml", "JTBC", None),
    # 매일경제 (전체)
    ("https://www.mk.co.kr/rss/30100041/", "매일경제", "경제"),
    # 한국경제 (전체) — requests로만 접근 가능
    ("https://www.hankyung.com/feed/all-news", "한국경제", "경제"),
]

# ─── 카테고리 자동 감지 ───────────────────────────────────────────────────────

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "정치": ["대통령", "국회", "여당", "야당", "정당", "선거", "총선", "대선",
             "청와대", "용산", "국무", "총리", "외교", "탄핵", "입법", "개헌",
             "의원", "장관", "정치", "여의도"],
    "경제": ["경제", "주식", "코스피", "코스닥", "금리", "부동산", "환율",
             "수출", "기업", "반도체", "증시", "물가", "인플레", "무역",
             "취업", "실업", "gdp", "금융", "은행", "투자", "펀드"],
    "사회": ["사건", "사고", "재판", "교육", "의료", "병원", "코로나",
             "환경", "재난", "노동", "파업", "복지", "저출생", "인구",
             "범죄", "경찰", "검찰", "법원", "학교", "대학", "안전"],
    "문화": ["영화", "드라마", "공연", "음악", "스포츠", "야구", "축구",
             "올림픽", "월드컵", "bts", "k팝", "kpop", "연예", "예술",
             "전시", "문학", "출판", "게임", "웹툰", "ott", "넷플릭스"],
    "국제": ["미국", "중국", "일본", "러시아", "유럽", "우크라이나", "중동",
             "이스라엘", "이란", "북한", "un", "nato", "g7", "g20",
             "전쟁", "분쟁", "외교", "국제"],
}


def detect_category(text: str) -> str:
    text_lower = text.lower()
    scores: dict[str, int] = {cat: 0 for cat in _CATEGORY_KEYWORDS}
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[cat] += 1
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else "기타"


# ─── 파싱 유틸 ────────────────────────────────────────────────────────────────

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def _clean(s: str) -> str:
    return _SPACE_RE.sub(" ", _TAG_RE.sub("", s)).strip()


def _parse_time(entry) -> str:
    """feedparser entry → ISO 8601 KST 문자열"""
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if t:
        try:
            dt = datetime(*t[:6], tzinfo=timezone.utc).astimezone(KST)
            return dt.isoformat()
        except Exception:
            pass
    return datetime.now(KST).isoformat()


# ─── 메인 함수 ───────────────────────────────────────────────────────────────

def fetch_rss_items() -> list[dict]:
    """
    모든 RSS 피드를 순회해 기사 목록을 반환.
    반환 형식: [{"headline", "url", "published_at", "publisher", "category"}, ...]
    """
    collected: list[dict] = []

    for feed_url, default_publisher, fixed_category in RSS_FEEDS:
        try:
            # requests로 먼저 수신 (리디렉트 추적, User-Agent 보장)
            resp = requests.get(feed_url, headers=_HEADERS, timeout=8, allow_redirects=True)
            resp.raise_for_status()
            # Content-Type이 HTML이면 RSS가 아님
            ct = resp.headers.get("Content-Type", "")
            if "html" in ct and not resp.text.strip().startswith("<?xml"):
                print(f"[rss] skip (not XML): {feed_url}")
                continue
            feed = feedparser.parse(resp.text)
            if not feed.entries:
                print(f"[rss] skip (no entries): {feed_url}")
                continue

            for entry in feed.entries:
                url = (entry.get("link") or "").strip()
                headline = preprocess_headline(_clean(entry.get("title") or ""))
                if not url or not headline:
                    continue

                publisher = identify_publisher(url) if identify_publisher(url) != "기타" else default_publisher
                category = fixed_category or detect_category(headline)
                published_at = _parse_time(entry)

                collected.append({
                    "headline": headline,
                    "url": url,
                    "published_at": published_at,
                    "publisher": publisher,
                    "category": category,
                })

            time.sleep(0.2)  # 피드 서버 부하 방지

        except requests.RequestException as e:
            print(f"[rss] fetch error ({feed_url}): {e}")
            continue
        except Exception as e:
            print(f"[rss] parse error ({feed_url}): {e}")
            continue

    return collected
