#!/usr/bin/env python3
"""card/SCUins raw 증강에 실제 사용한 기본 품질 필터와 exact dedup만 적용한다."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

RE_WS = re.compile(r"\s+")
RE_KOREAN = re.compile(r"[가-힣]")


def normalize(text: str) -> str:
    return RE_WS.sub(" ", str(text).strip())


def pass_basic(text: str, min_tokens: int, min_korean: int) -> bool:
    text = normalize(text)
    return len(text.split()) >= min_tokens and len(RE_KOREAN.findall(text)) >= min_korean


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--input", default="data/augmented/card_scuins/aug_card_scuins_meanir_raw.jsonl")
    parser.add_argument("--output", default="data/augmented/card_scuins/aug_card_scuins_meanir.jsonl")
    parser.add_argument("--report", default="results/report/filter_report.md")
    parser.add_argument("--min-tokens", type=int, default=5)
    parser.add_argument("--min-korean", type=int, default=8)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    in_path = root / args.input
    out_path = root / args.output
    report_path = root / args.report

    rows = [json.loads(line) for line in in_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    n_raw = len(rows)
    rows = [row for row in rows if pass_basic(row.get("text", ""), args.min_tokens, args.min_korean)]
    n_basic = len(rows)

    seen = set()
    deduped = []
    for row in rows:
        key = normalize(row.get("text", "")).lower()
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    rows = deduped

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# filter_report.md - card/SCUins 기본 품질 필터 결과",
        "",
        "| 단계 | 입력 | 제거 | 출력 |",
        "|---|---:|---:|---:|",
        f"| 최소 길이/한글 수(min_tokens={args.min_tokens}, min_korean={args.min_korean}) | {n_raw:,} | {n_raw - n_basic:,} | {n_basic:,} |",
        f"| Exact dedup | {n_basic:,} | {n_basic - len(rows):,} | {len(rows):,} |",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] {n_raw:,} -> {len(rows):,}; report={report_path}")


if __name__ == "__main__":
    main()
