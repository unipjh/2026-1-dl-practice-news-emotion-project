"""
preprocessed_headline 채우기 + attention_weights만 재계산
emotion_probs는 건드리지 않는다.

사용법:
    cd lab-w18/dl-prac-submission/backend
    python scripts/update_attention_only.py [--dry-run]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_conn, migrate_db
from app.text_preprocess import preprocess_headline


def populate_preprocessed(dry_run: bool = False) -> int:
    """preprocessed_headline이 NULL인 행을 채운다."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, headline FROM headlines WHERE preprocessed_headline IS NULL"
        ).fetchall()

    if not rows:
        print("[preprocess] 모든 행에 preprocessed_headline이 이미 있음")
        return 0

    updates = [(preprocess_headline(r["headline"]), r["id"]) for r in rows]
    print(f"[preprocess] {len(updates)}건 채울 예정")

    if dry_run:
        for cleaned, hid in updates[:5]:
            orig = next(r["headline"] for r in rows if r["id"] == hid)
            print(f"  [{hid}] {orig!r} → {cleaned!r}")
        if len(updates) > 5:
            print(f"  ... 이하 {len(updates)-5}건 생략")
        return len(updates)

    with get_conn() as conn:
        conn.executemany(
            "UPDATE headlines SET preprocessed_headline = ? WHERE id = ?", updates
        )
    print(f"[preprocess] {len(updates)}건 완료")
    return len(updates)


def main():
    parser = argparse.ArgumentParser(description="attention_weights 재계산 (emotion_probs 보존)")
    parser.add_argument("--dry-run", action="store_true", help="전처리 미리보기만, DB 수정 없음")
    args = parser.parse_args()

    # 1. 컬럼 마이그레이션
    migrate_db()

    # 2. preprocessed_headline 채우기
    populate_preprocessed(dry_run=args.dry_run)
    if args.dry_run:
        print("\n[dry-run] 여기서 종료. --dry-run 없이 실행하면 attention 재계산 진행.")
        return

    # 3. attention_weights만 재계산
    from app.inference.predict import update_attention_only
    update_attention_only()


if __name__ == "__main__":
    main()
