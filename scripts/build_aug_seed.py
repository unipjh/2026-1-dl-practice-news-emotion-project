#!/usr/bin/env python3
"""card/SCUins seed JSONL을 제출본의 aug_seed.csv 형식으로 변환한다."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FIELDS = [
    "label",
    "irlbl",
    "need",
    "seed_idx",
    "seed_sample_id",
    "seed_text",
    "reuse_round",
    "source_labels",
    "active_labels",
    "card",
    "scuins",
    "selection_rule",
    "selection_rank",
    "origin",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    src = Path(args.input)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    with src.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            rows.append(row)

    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            rec = {field: row.get(field, "") for field in FIELDS}
            for key in ["source_labels", "active_labels"]:
                if isinstance(rec[key], list):
                    rec[key] = "|".join(rec[key])
            writer.writerow(rec)

    print(f"[OK] {len(rows):,} seed rows -> {out}")


if __name__ == "__main__":
    main()
