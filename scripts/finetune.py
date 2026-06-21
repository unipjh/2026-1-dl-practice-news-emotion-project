#!/usr/bin/env python3
"""제출 루트 기준으로 KOTE fine-tuning 조건 하나를 재현 실행한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="dl-prac-submission root")
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--aug-jsonl", default=None, help="Optional augmentation JSONL path, root-relative or absolute")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--threshold", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def resolve_path(root: Path, value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return str(path)


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    sys.path.insert(0, str(root))

    metrics_path = root / "results" / "model" / args.run_name / "metrics.json"
    if metrics_path.exists() and not args.overwrite:
        print(f"[SKIP] metrics already exists: {metrics_path}")
        print(metrics_path.read_text(encoding="utf-8"))
        return

    from src.kote_trainer import run_finetune

    result = run_finetune(
        train_tsv=str(root / "data" / "kote" / "train.tsv"),
        val_tsv=str(root / "data" / "kote" / "val.tsv"),
        test_tsv=str(root / "data" / "kote" / "test.tsv"),
        run_name=args.run_name,
        output_dir=str(root / "results" / "model"),
        aug_jsonl=resolve_path(root, args.aug_jsonl),
        epochs=args.epochs,
        batch_size=args.batch_size,
        threshold=args.threshold,
        seed=args.seed,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
