#!/usr/bin/env python3
"""Export backend SQLite news tables to CSV files under data/news_db.

This is intended for submission packaging: CSV files are easier to inspect and
can replace the bulky backend/data/news.db file when only data artifacts are
required.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path

DEFAULT_TABLES = ["headlines", "emotion_results", "crawler_meta"]


def export_table(conn: sqlite3.Connection, table: str, out_dir: Path) -> dict[str, object]:
    rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
    columns = [desc[0] for desc in conn.execute(f'SELECT * FROM "{table}" LIMIT 0').description]
    out_path = out_dir / f"{table}.csv"
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    return {
        "table": table,
        "csv": str(out_path.relative_to(out_dir.parent.parent)),
        "rows": len(rows),
        "columns": columns,
        "bytes": out_path.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export news.db tables to CSV")
    parser.add_argument("--db", default="backend/data/news.db", help="SQLite DB path relative to project root")
    parser.add_argument("--out", default="data/news_db", help="CSV output directory relative to project root")
    parser.add_argument("--tables", nargs="*", default=DEFAULT_TABLES, help="Tables to export")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    db_path = (root / args.db).resolve()
    out_dir = root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        raise FileNotFoundError(f"SQLite DB not found: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        available = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = [table for table in args.tables if table not in available]
        if missing:
            raise ValueError(f"Missing tables in {db_path}: {missing}")

        summary = {
            "source_db": str(Path(args.db)),
            "output_dir": str(Path(args.out)),
            "tables": [export_table(conn, table, out_dir) for table in args.tables],
        }
    finally:
        conn.close()

    summary_path = out_dir / "export_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    readme_path = out_dir / "README.md"
    readme_path.write_text(
        "# news_db CSV export\n\n"
        "`backend/data/news.db`에 저장된 뉴스 헤드라인 수집/전처리/감정 추론 결과를 "
        "테이블별 CSV로 내보낸 제출용 데이터다.\n\n"
        "| CSV | 원본 테이블 | 설명 |\n"
        "|---|---|---|\n"
        "| `headlines.csv` | `headlines` | 수집 기사 제목, 카테고리, 언론사, 발행일, URL, 전처리 제목 |\n"
        "| `emotion_results.csv` | `emotion_results` | headline_id별 KOTE 44-class 감정 확률 JSON, attention weights JSON, 추론 시각 |\n"
        "| `crawler_meta.csv` | `crawler_meta` | crawler 실행 메타데이터 |\n\n"
        "`emotion_results.headline_id`는 `headlines.id`와 연결된다. 원본 SQLite DB를 제출하지 않는 경우에도 "
        "이 세 CSV로 뉴스 데이터와 추론 결과를 확인할 수 있다.\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
