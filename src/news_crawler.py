"""
news_crawler.py — 한국 뉴스 헤드라인 수집

지원 방식:
  1. RSS 피드 (무료, 별도 인증 불필요) — crawl_rss()
  2. 네이버 뉴스 검색 API (하루 25,000건, client_id/secret 필요) — crawl_naver_api()

사용 예:
    from src.news_crawler import crawl_rss, crawl_naver_api, save_to_csv

    df = crawl_rss(max_per_feed=100)
    df = crawl_naver_api("감정")   # 환경변수 NAVER_CLIENT_ID/SECRET 필요
    save_to_csv(df, "data/news/headlines.csv")
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd
import requests

try:
    import feedparser
    _HAS_FEEDPARSER = True
except ImportError:
    _HAS_FEEDPARSER = False


_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}
KST = timezone(timedelta(hours=9))

# 여 헤드라인 전처리 여
# 스마트 인용부호·말줄임표·장식 기호를 제거해 ELECTRA 토크나이저가
# 기호 토큰에 어텐션을 낭비하는 현상을 방지한다.
# (\uXXXX 이스케이프 사용 — 편집기 스마트 따옴표 오염 방지)
_SMART_QUOTE = re.compile(
    '[\u201c\u201d\u2018\u2019\u201e\u201f\u300c\u300d\u300e\u300f\u2039\u203a\u00ab\u00bb\u2033\u2032\u301d\u301e]'
)
_ELLIPSIS   = re.compile(r'\.{2,}|\u2026+')
_WORD_SEP   = re.compile('[\u00b7\u2022]')   # \u00b7=· \u2022=•
_DECORATIVE = re.compile(
    '[\u25c6\u25c7\u25b6\u25c0\u25b7\u25c1\u25b2\u25bd\u25bc\u2605\u2606\u2666\u2663\u2660\u2665\u25ba\u25bb\u25c9\u25cb\u25cf\u203b]'
)
_SPACES     = re.compile(r'\s+')


def preprocess_headline(text: str) -> str:
    '인용부호\u00b7말줄임\u00b7장식 기호 제거 후 공백 정규화.'
    text = _SMART_QUOTE.sub('', text)
    text = _ELLIPSIS.sub('', text)
    text = _WORD_SEP.sub(' ', text)    # \u00b7 -> 스페이스 (단어 경계 유지)
    text = _DECORATIVE.sub('', text)
    text = _SPACES.sub(' ', text)
    return text.strip()

# ── RSS 피드 목록 ──────────────────────────────────────────────────
# (url, publisher, fixed_category | None)
# fixed_category=None → 헤드라인 키워드로 자동 감지
# w18 백엔드에서 동작 확인된 피드만 포함 (requests + feedparser 기준)
_RSS_FEEDS: list[tuple[str, str, str | None]] = [
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
    # 매일경제 (경제)
    ("https://www.mk.co.kr/rss/30100041/", "매일경제", "경제"),
    # 한국경제 (requests로만 접근 가능)
    ("https://www.hankyung.com/feed/all-news", "한국경제", "경제"),
]

# 하위 호환: 노트북에서 feeds=MEDIA_RSS_FEEDS로 전달하는 경우 대비
MEDIA_RSS_FEEDS = {pub: url for url, pub, _ in _RSS_FEEDS}

# ── 언론사 도메인 맵 ───────────────────────────────────────────────
_PUBLISHER_MAP: dict[str, str] = {
    # 종합일간지
    "chosun.com": "조선일보",
    "donga.com": "동아일보",
    "hani.co.kr": "한겨레",
    "khan.co.kr": "경향신문",
    "joongang.co.kr": "중앙일보",
    "joins.com": "중앙일보",
    "ohmynews.com": "오마이뉴스",
    "hankookilbo.com": "한국일보",
    # 방송
    "kbs.co.kr": "KBS",
    "mbc.co.kr": "MBC",
    "sbs.co.kr": "SBS",
    "jtbc.co.kr": "JTBC",
    "ytn.co.kr": "YTN",
    "mbn.co.kr": "MBN",
    # 통신사
    "yna.co.kr": "연합뉴스",
    "newsis.com": "뉴시스",
    "news1.kr": "뉴스1",
    # 경제지
    "hankyung.com": "한국경제",
    "mt.co.kr": "머니투데이",
    "mk.co.kr": "매일경제",
    "edaily.co.kr": "이데일리",
    "biz.chosun.com": "조선비즈",
    "heraldcorp.com": "헤럴드경제",
    "sedaily.com": "서울경제",
}


def _identify_publisher(url: str, default: str) -> str:
    for domain, name in _PUBLISHER_MAP.items():
        if domain in url:
            return name
    return default


# ── 카테고리 자동 감지 ─────────────────────────────────────────────
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "정치": ["대통령", "국회", "여당", "야당", "정당", "선거", "총선", "대선",
             "청와대", "용산", "총리", "장관", "정치", "여의도", "탄핵", "입법"],
    "경제": ["경제", "주식", "코스피", "코스닥", "금리", "부동산", "환율",
             "수출", "기업", "반도체", "증시", "물가", "무역", "취업", "금융", "투자"],
    "사회": ["사건", "사고", "재판", "교육", "의료", "병원", "환경", "재난",
             "노동", "파업", "복지", "범죄", "경찰", "검찰", "법원", "학교", "저출생"],
    "문화": ["영화", "드라마", "공연", "음악", "스포츠", "야구", "축구",
             "올림픽", "bts", "k팝", "kpop", "연예", "예술", "게임", "넷플릭스", "ott"],
    "국제": ["미국", "중국", "일본", "러시아", "유럽", "우크라이나", "중동",
             "이스라엘", "북한", "un", "nato", "전쟁", "분쟁", "국제", "외교"],
}


def _detect_category(text: str) -> str:
    text_lower = text.lower()
    scores = {
        cat: sum(1 for kw in kws if kw in text_lower)
        for cat, kws in _CATEGORY_KEYWORDS.items()
    }
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else "기타"


# ── 파싱 유틸 ─────────────────────────────────────────────────────
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def _clean(s: str) -> str:
    return _SPACE_RE.sub(" ", _TAG_RE.sub("", s)).strip()


def _parse_date(entry) -> str:
    """feedparser entry → YYYY-MM-DD 문자열 (KST 기준)"""
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if t:
        try:
            dt = datetime(*t[:6], tzinfo=timezone.utc).astimezone(KST)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    return datetime.now(KST).strftime("%Y-%m-%d")


# ── 공개 API ──────────────────────────────────────────────────────

def crawl_rss(
    feeds: Optional[dict[str, str]] = None,
    max_per_feed: int = 100,
    delay: float = 0.2,
) -> pd.DataFrame:
    """
    RSS 피드에서 뉴스 헤드라인 수집.

    Args:
        feeds: {출처명: RSS URL} 딕셔너리. None이면 내부 검증 목록(_RSS_FEEDS) 사용 (권장).
        max_per_feed: 피드당 최대 수집 건수
        delay: 피드 간 요청 대기 시간(초)

    Returns:
        DataFrame with columns: [title, source, published, url, category]
    """
    if not _HAS_FEEDPARSER:
        raise ImportError("feedparser가 설치되지 않았습니다: pip install feedparser")

    # feeds 파라미터 처리 (하위 호환)
    if feeds is not None:
        feed_list: list[tuple[str, str, str | None]] = [
            (url, src, None) for src, url in feeds.items()
        ]
    else:
        feed_list = _RSS_FEEDS

    records: list[dict] = []
    for feed_url, default_publisher, fixed_category in feed_list:
        print(f"  수집 중: {default_publisher} ({feed_url})")
        try:
            # requests로 먼저 수신 (리디렉트 추적, User-Agent 보장)
            resp = requests.get(feed_url, headers=_HEADERS, timeout=8, allow_redirects=True)
            resp.raise_for_status()
            ct = resp.headers.get("Content-Type", "")
            if "html" in ct and not resp.text.strip().startswith("<?xml"):
                print(f"    [SKIP] XML 아님")
                continue

            feed = feedparser.parse(resp.text)
            if not feed.entries:
                print(f"    [SKIP] 항목 없음")
                continue

            count = 0
            for entry in feed.entries[:max_per_feed]:
                url = (entry.get("link") or "").strip()
                title = preprocess_headline(_clean(entry.get("title") or ""))
                if not url or not title:
                    continue

                publisher = _identify_publisher(url, default_publisher)
                category = fixed_category or _detect_category(title)
                published = _parse_date(entry)

                records.append({
                    "title":     title,
                    "source":    publisher,
                    "published": published,
                    "url":       url,
                    "category":  category,
                })
                count += 1
            print(f"    → {count}건 수집")

        except requests.RequestException as e:
            print(f"    [오류] {default_publisher}: {e}")
        except Exception as e:
            print(f"    [오류] {default_publisher}: {e}")

        time.sleep(delay)

    df = pd.DataFrame(records)
    print(f"\n총 {len(df)}건 수집 완료")
    return df


_NAVER_URL = "https://openapi.naver.com/v1/search/news.json"
_MAX_RETRIES = 3


def crawl_naver_api(
    query: str,
    client_id: str = "",
    client_secret: str = "",
    display: int = 100,
    start: int = 1,
    sort: str = "date",
) -> pd.DataFrame:
    """
    네이버 뉴스 검색 API로 헤드라인 수집.
    (https://developers.naver.com/docs/serviceapi/search/news/news.md)

    사전 준비:
        1. https://developers.naver.com 에서 앱 등록
        2. "검색" API 신청 → client_id, client_secret 발급
        무료 티어: 하루 25,000건

    Args:
        query:         검색어 (예: "정치", "경제 사건")
        client_id:     네이버 API 클라이언트 ID (미입력 시 환경변수 NAVER_CLIENT_ID 참조)
        client_secret: 네이버 API 클라이언트 시크릿 (미입력 시 환경변수 NAVER_CLIENT_SECRET 참조)
        display:       1회 요청 건수 (최대 100)
        start:         검색 시작 위치 (1~1000)
        sort:          정렬 기준 ("date" 또는 "sim")

    Returns:
        DataFrame with columns: [title, source, published, url, category]
    """
    cid  = client_id  or os.environ.get("NAVER_CLIENT_ID",     "")
    csec = client_secret or os.environ.get("NAVER_CLIENT_SECRET", "")
    if not cid or not csec:
        raise ValueError(
            "네이버 API 인증 정보 없음. "
            "client_id/client_secret 인자를 전달하거나 "
            "환경변수 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 를 설정하세요."
        )

    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}
    params  = {"query": query, "display": display, "start": start, "sort": sort}

    items: list[dict] = []
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.get(_NAVER_URL, headers=headers, params=params, timeout=5)
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = 2 ** attempt
                print(f"[naver_api] HTTP {resp.status_code}, {wait}s 후 재시도 (시도 {attempt + 1})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            items = resp.json().get("items", [])
            break
        except requests.RequestException as e:
            if attempt < _MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"[naver_api] {_MAX_RETRIES}회 시도 후 실패: {e}")

    records: list[dict] = []
    for item in items:
        title = preprocess_headline(_clean(item.get("title", "")))
        pub_date = item.get("pubDate", "")
        try:
            from email.utils import parsedate
            parsed = parsedate(pub_date)
            pub_date = datetime(*parsed[:3]).strftime("%Y-%m-%d") if parsed else pub_date
        except Exception:
            pass
        url = item.get("originallink", "") or item.get("link", "")
        records.append({
            "title":     title,
            "source":    _identify_publisher(url, url.split("/")[2] if "/" in url else ""),
            "published": pub_date,
            "url":       url,
            "category":  _detect_category(title),
        })

    df = pd.DataFrame(records)
    print(f"네이버 API 수집: {len(df)}건")
    return df


def save_to_csv(df: pd.DataFrame, path: str) -> None:
    """수집 결과를 CSV로 저장"""
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {path}  ({len(df)}건)")
