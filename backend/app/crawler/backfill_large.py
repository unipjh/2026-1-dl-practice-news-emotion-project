"""
대용량 뉴스 수집 — 3~5년치 목표

Naver News API 제약:
  - 쿼리당 최대 1,000건 (start 1~901, display 100 × 10페이지)
  - 일반 키워드는 최신 기사만 반환 → 과거 기사는 연도/이벤트 특정 키워드로 획득

전략:
  1. 카테고리별 일반 키워드 (최근 기사)
  2. 연도별 이벤트 키워드 2020~2025 (과거 기사)
  3. INSERT OR IGNORE (URL 중복 자동 스킵)

실행:
  cd lab-w18/dl-prac-submission/backend
  python -m app.crawler.backfill_large [--dry-run] [--start-from KEYWORD]

예상 수집량: ~150 키워드 × 평균 600건 = 90,000~120,000건 (중복 제거 후)
예상 소요: 약 15~25분 (API sleep 포함)
"""
import argparse
import os
import sys
import re
import time
from email.utils import parsedate_to_datetime
from pathlib import Path

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

# ─── 키워드 정의 ─────────────────────────────────────────────────────────────
# (카테고리, 키워드) 쌍 목록
# 연도 이벤트 키워드는 해당 시기 기사를 끌어내기 위함

KEYWORDS: list[tuple[str, str]] = [
    # ── 정치 (일반) ──────────────────────────────────────────────────────────
    ("정치", "정치"),
    ("정치", "국회"),
    ("정치", "대통령"),
    ("정치", "여당"),
    ("정치", "야당"),
    ("정치", "선거"),
    ("정치", "국무총리"),
    ("정치", "외교"),
    ("정치", "북한"),
    ("정치", "한미동맹"),
    ("정치", "탄핵"),
    ("정치", "입법"),
    ("정치", "개헌"),
    ("정치", "정당"),
    ("정치", "청와대"),
    ("정치", "용산"),
    # ── 정치 (연도별 이벤트) ─────────────────────────────────────────────────
    ("정치", "21대총선"),        # 2020.04
    ("정치", "재보궐선거 2021"), # 2021.04
    ("정치", "대선 2022"),       # 2022.03
    ("정치", "윤석열 당선"),
    ("정치", "22대총선"),        # 2024.04
    ("정치", "비상계엄 2024"),   # 2024.12
    ("정치", "탄핵 가결"),
    ("정치", "조기대선 2025"),
    ("정치", "이재명 대표"),
    ("정치", "한동훈"),
    ("정치", "국민의힘"),
    ("정치", "더불어민주당"),

    # ── 경제 (일반) ──────────────────────────────────────────────────────────
    ("경제", "경제"),
    ("경제", "증시"),
    ("경제", "물가"),
    ("경제", "금리"),
    ("경제", "부동산"),
    ("경제", "코스피"),
    ("경제", "환율"),
    ("경제", "수출"),
    ("경제", "무역"),
    ("경제", "인플레이션"),
    ("경제", "취업"),
    ("경제", "실업"),
    ("경제", "반도체"),
    ("경제", "삼성전자"),
    ("경제", "SK하이닉스"),
    ("경제", "LG"),
    ("경제", "현대차"),
    ("경제", "스타트업"),
    ("경제", "벤처"),
    ("경제", "IPO"),
    ("경제", "가상화폐"),
    ("경제", "비트코인"),
    # ── 경제 (연도별 이벤트) ─────────────────────────────────────────────────
    ("경제", "코로나 경제"),     # 2020~2021
    ("경제", "재난지원금"),      # 2020~2021
    ("경제", "공급망 위기"),     # 2021~2022
    ("경제", "기준금리 인상"),   # 2022~2023
    ("경제", "부동산 PF"),       # 2023~2024
    ("경제", "AI 반도체"),       # 2023~
    ("경제", "HBM"),
    ("경제", "엔비디아"),

    # ── 사회 (일반) ──────────────────────────────────────────────────────────
    ("사회", "사회"),
    ("사회", "사건"),
    ("사회", "재판"),
    ("사회", "범죄"),
    ("사회", "교육"),
    ("사회", "의료"),
    ("사회", "복지"),
    ("사회", "저출생"),
    ("사회", "인구"),
    ("사회", "기후변화"),
    ("사회", "환경"),
    ("사회", "재난"),
    ("사회", "안전"),
    ("사회", "이민"),
    ("사회", "노동"),
    ("사회", "파업"),
    ("사회", "의대"),
    ("사회", "학교폭력"),
    # ── 사회 (연도별 이벤트) ─────────────────────────────────────────────────
    ("사회", "코로나19"),         # 2020~2022
    ("사회", "백신"),             # 2021~2022
    ("사회", "오미크론"),         # 2021.12~2022
    ("사회", "사회적 거리두기"),
    ("사회", "이태원 참사"),      # 2022.10
    ("사회", "후쿠시마 오염수"),  # 2023
    ("사회", "의대 증원"),        # 2024
    ("사회", "의사 파업 2024"),
    ("사회", "딥페이크"),         # 2023~
    ("사회", "전공의 집단사직"),

    # ── 문화/연예 (일반) ─────────────────────────────────────────────────────
    ("문화", "문화"),
    ("문화", "공연"),
    ("문화", "전시"),
    ("문화", "영화"),
    ("문화", "드라마"),
    ("문화", "K팝"),
    ("문화", "스포츠"),
    ("문화", "야구"),
    ("문화", "축구"),
    ("문화", "게임"),
    ("문화", "웹툰"),
    ("문화", "OTT"),
    ("문화", "넷플릭스"),
    # ── 문화 (연도별 이벤트) ────────────────────────────────────────────────
    ("문화", "BTS 군입대"),       # 2022~2023
    ("문화", "오징어게임"),       # 2021.09
    ("문화", "기생충 오스카"),    # 2020.02
    ("문화", "도쿄올림픽"),       # 2021.07
    ("문화", "카타르월드컵"),     # 2022.11
    ("문화", "파리올림픽"),       # 2024.07
    ("문화", "블랙핑크"),
    ("문화", "뉴진스"),
    ("문화", "아이브"),

    # ── 국제 ────────────────────────────────────────────────────────────────
    ("국제", "국제"),
    ("국제", "미국"),
    ("국제", "중국"),
    ("국제", "일본"),
    ("국제", "러시아"),
    ("국제", "유럽"),
    ("국제", "중동"),
    ("국제", "이스라엘"),
    ("국제", "팔레스타인"),
    # ── 국제 (연도별 이벤트) ────────────────────────────────────────────────
    ("국제", "우크라이나 전쟁"),  # 2022.02~
    ("국제", "러시아 침공"),
    ("국제", "트럼프 당선 2024"),
    ("국제", "미중 무역분쟁"),
    ("국제", "반도체 수출규제"),
    ("국제", "가자 전쟁"),        # 2023.10~
    ("국제", "미국 대선 2024"),
    ("국제", "아프가니스탄"),     # 2021
    ("국제", "탈레반"),

    # ── IT/과학 ─────────────────────────────────────────────────────────────
    ("사회", "인공지능"),
    ("사회", "ChatGPT"),
    ("사회", "AI"),
    ("사회", "우주"),
    ("사회", "누리호"),           # 2022~2023
    ("사회", "자율주행"),
    ("사회", "메타버스"),         # 2021~2022

    # ── 북한 ────────────────────────────────────────────────────────────────
    ("정치", "북한 미사일"),
    ("정치", "북한 핵"),
    ("정치", "남북관계"),
    ("정치", "김정은"),
    ("정치", "북러 협력"),        # 2023~
]

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def clean_text(s: str) -> str:
    s = _TAG_RE.sub("", s)
    return _SPACE_RE.sub(" ", s).strip()


def parse_published_at(pub_date: str) -> str:
    try:
        return parsedate_to_datetime(pub_date).isoformat()
    except Exception:
        return pub_date


def run_large_backfill(dry_run: bool = False, start_from: str | None = None):
    init_db()

    total_inserted = 0
    total_skipped = 0
    total_api_calls = 0

    keywords = KEYWORDS
    if start_from:
        # 특정 키워드부터 재개
        found = False
        for i, (_, kw) in enumerate(KEYWORDS):
            if start_from in kw:
                keywords = KEYWORDS[i:]
                found = True
                print(f"[backfill_large] Resuming from keyword index {i}: '{kw}'")
                break
        if not found:
            print(f"[backfill_large] Warning: '{start_from}' not found, starting from beginning")

    total_keywords = len(keywords)
    print(f"[backfill_large] Target: {total_keywords} keywords × 1,000 items = {total_keywords * 1000:,} max records")
    print(f"[backfill_large] Estimated API calls: {total_keywords * 10:,}")
    if dry_run:
        print("[backfill_large] DRY RUN — no DB writes")
        for category, kw in keywords:
            print(f"  [{category}] {kw}")
        return

    start_time = time.time()

    with get_conn() as conn:
        for ki, (category, keyword) in enumerate(keywords, 1):
            kw_inserted = 0
            kw_skipped = 0

            for start in range(1, 902, 100):
                items = search_news(keyword, start=start, display=100)
                total_api_calls += 1

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
                            kw_inserted += 1
                        else:
                            kw_skipped += 1
                    except Exception as e:
                        print(f"[backfill_large] insert error: {e}")

                # API 호출 간격 (rate limit 방지)
                time.sleep(0.1)

            total_inserted += kw_inserted
            total_skipped += kw_skipped

            elapsed = time.time() - start_time
            remaining_kw = total_keywords - ki
            avg_per_kw = elapsed / ki
            eta_sec = avg_per_kw * remaining_kw

            print(
                f"[{ki:3d}/{total_keywords}] [{category}] {keyword!r:25s} "
                f"+{kw_inserted:4d} skip={kw_skipped:4d} "
                f"| total={total_inserted:,} "
                f"| ETA {int(eta_sec//60)}m{int(eta_sec%60):02d}s"
            )

    elapsed_total = time.time() - start_time
    print()
    print(f"[backfill_large] ─── 완료 ───────────────────────────────────")
    print(f"  신규 삽입:  {total_inserted:,}건")
    print(f"  중복 스킵:  {total_skipped:,}건")
    print(f"  API 호출:   {total_api_calls:,}회")
    print(f"  소요 시간:  {int(elapsed_total//60)}분 {int(elapsed_total%60)}초")
    print()
    print("다음 단계 — 미추론 헤드라인 배치 추론:")
    print("  python -c \"from app.inference.predict import run_all; run_all()\"")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="대용량 뉴스 백필")
    parser.add_argument("--dry-run", action="store_true", help="키워드 목록만 출력, DB 미수정")
    parser.add_argument("--start-from", type=str, default=None, metavar="KEYWORD",
                        help="이 문자열이 포함된 키워드부터 재개 (중단 후 재시작용)")
    args = parser.parse_args()
    run_large_backfill(dry_run=args.dry_run, start_from=args.start_from)
