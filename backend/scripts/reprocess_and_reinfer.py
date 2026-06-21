"""
DB 헤드라인 전처리 재적용 + 감정 추론 재실행

사용법:
    cd lab-w18/dl-prac-submission/backend
    python scripts/reprocess_and_reinfer.py [--dry-run]

동작:
    1. headlines.preprocessed_headline 컬럼에 preprocess_headline() 결과 저장 (원본 보존)
    2. emotion_results 전체 삭제
    3. predict.run_all()로 추론 재실행
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_conn, migrate_db
from app.text_preprocess import preprocess_headline


def reprocess_headlines(dry_run: bool = False) -> int:
    """preprocessed_headline 컬럼을 채운다. 원본 headline은 건드리지 않는다."""
    with get_conn() as conn:
        rows = conn.execute("SELECT id, headline FROM headlines").fetchall()

    updates = []
    for row in rows:
        cleaned = preprocess_headline(row["headline"])
        updates.append((cleaned, row["id"]))

    changed = sum(1 for c, hid in updates
                  if c != next(r["headline"] for r in rows if r["id"] == hid))
    print(f"전처리 변경 대상: {changed}/{len(rows)}건 (나머지는 동일)")

    if dry_run:
        shown = [(c, hid) for c, hid in updates
                 if c != next(r["headline"] for r in rows if r["id"] == hid)][:10]
        for new_text, hid in shown:
            orig = next(r["headline"] for r in rows if r["id"] == hid)
            print(f"  [{hid}] {orig!r}")
            print(f"       → {new_text!r}")
        if changed > 10:
            print(f"  ... 이하 {changed-10}건 생략")
        return changed

    with get_conn() as conn:
        conn.executemany(
            "UPDATE headlines SET preprocessed_headline = ? WHERE id = ?", updates
        )
    print(f"preprocessed_headline 업데이트 완료: {len(updates)}건")
    return len(updates)


def clear_emotion_results() -> int:
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM emotion_results").fetchone()[0]
        conn.execute("DELETE FROM emotion_results")
    print(f"emotion_results 삭제: {n}건")
    return n


def main():
    parser = argparse.ArgumentParser(description="DB 재전처리 + 추론 재실행")
    parser.add_argument("--dry-run", action="store_true", help="변경 내용만 출력, DB는 수정하지 않음")
    parser.add_argument("--preprocess-only", action="store_true", help="전처리만 하고 추론은 건너뜀")
    args = parser.parse_args()

    # 0. 컬럼 마이그레이션 (없으면 추가)
    migrate_db()

    # 1. 전처리 재적용
    reprocess_headlines(dry_run=args.dry_run)
    if args.dry_run:
        print("\n[dry-run] DB 수정 없이 종료합니다.")
        return

    # 2. emotion_results 초기화
    clear_emotion_results()

    if args.preprocess_only:
        print("--preprocess-only: 추론 건너뜀.")
        return

    # 3. 추론 재실행
    print("\n추론 재실행 중...")
    from app.inference.predict import run_all
    run_all()
    print("완료.")


if __name__ == "__main__":
    main()
