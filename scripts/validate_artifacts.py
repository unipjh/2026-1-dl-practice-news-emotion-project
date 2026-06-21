#!/usr/bin/env python3
"""제출본이 자기 루트만으로 재현 가능한지 필수 산출물과 경로를 검증한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE_REQUIRED_FILES = [
    "main.ipynb",
    "requirements.txt",
    "README.md",
    "data/kote/train.tsv",
    "data/kote/val.tsv",
    "data/kote/test.tsv",
    "data/kote/irlbl.json",
    "data/aug_seed.csv",
    "data/augmented/total_seed_gemini_aug/total_seed_gemini_aug_meanir.jsonl",
    "data/augmented/bt/aug_bt_need19947_s42_repaired.jsonl",
    "data/augmented/card_scuins/aug_card_scuins_meanir.jsonl",
    "data/news_db/headlines.csv",
    "data/news_db/emotion_results.csv",
    "data/news_db/crawler_meta.csv",
    "data/news_db/export_summary.json",
    "results/report/model_report.md",
    "results/report/training_history.csv",
    "scripts/export_news_db_csv.py",
    "scripts/finetune.py",
    "src/kote_trainer.py",
    "app/package.json",
    "backend/app/inference/model_loader.py",
]

MODEL_REQUIRED_FILES = [
    "resources/kcelectra-base/config.json",
    "resources/kcelectra-base/vocab.txt",
    "resources/kcelectra-base/pytorch_model.bin",
]

GITHUB_EXTERNAL_FILES = [
    "data/news_db/emotion_results.csv",
]

REQUIRED_RUNS = [
    "baseline_th03",
    "aug_bt_need19947_s42_repaired",
    "aug_card_scuins_meanir",
]

BAD_PATH_MARKERS = [
    "/home/user/projects1/pjh/" + "lab-" + "w16" + "/dl_prac" + "_project",
    "lab-" + "w16" + "/dl_prac" + "_project/results/",
    "lab-" + "w16" + "/dl_prac" + "_project/data/" + "augment" + "ation/",
]


def count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as f:
        return sum(1 for _ in f)


def check_metrics(root: Path) -> tuple[dict[str, dict], list[str]]:
    metrics = {}
    problems = []
    for run in REQUIRED_RUNS:
        run_dir = root / "results" / "model" / run
        metrics_path = run_dir / "metrics.json"
        if not metrics_path.exists():
            problems.append(f"missing metrics: {metrics_path.relative_to(root)}")
            continue
        data = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics[run] = data
        for rel in ["model_path", "ckpt_dir", "aug_jsonl", "resumed_from_ckpt", "base_model_source"]:
            value = data.get(rel)
            if not value:
                continue
            if Path(str(value)).is_absolute():
                problems.append(f"absolute path in {metrics_path.relative_to(root)}: {rel}={value}")
            if any(marker in str(value) for marker in BAD_PATH_MARKERS):
                problems.append(f"source path marker in {metrics_path.relative_to(root)}: {rel}={value}")
        model_path = root / data.get("model_path", "")
        if not model_path.exists():
            problems.append(f"missing model artifact for {run}: {data.get('model_path')}")
        ckpt_dir = root / data.get("ckpt_dir", "")
        if not (ckpt_dir / "best.ckpt").exists():
            problems.append(f"missing best checkpoint for {run}: {data.get('ckpt_dir')}/best.ckpt")
    return metrics, problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--data-only",
        action="store_true",
        help="모델 가중치/checkpoint를 별도 제출할 때 소스와 데이터 산출물만 검증",
    )
    parser.add_argument(
        "--github",
        action="store_true",
        help="GitHub 저장소용 검증: 모델과 100MB 초과 외부 데이터 파일을 제외",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()

    required_files = list(BASE_REQUIRED_FILES)
    if args.github:
        required_files = [rel for rel in required_files if rel not in GITHUB_EXTERNAL_FILES]
    if not (args.data_only or args.github):
        required_files.extend(MODEL_REQUIRED_FILES)

    missing = [rel for rel in required_files if not (root / rel).exists()]
    counts = {}
    if not missing:
        counts = {
            "kote_train": count_lines(root / "data/kote/train.tsv"),
            "kote_val": count_lines(root / "data/kote/val.tsv"),
            "kote_test": count_lines(root / "data/kote/test.tsv"),
            "aug_seed_csv_rows_including_header": count_lines(root / "data/aug_seed.csv"),
            "total_seed_gemini_aug": count_lines(root / "data/augmented/total_seed_gemini_aug/total_seed_gemini_aug_meanir.jsonl"),
            "bt_repaired": count_lines(root / "data/augmented/bt/aug_bt_need19947_s42_repaired.jsonl"),
            "card_scuins": count_lines(root / "data/augmented/card_scuins/aug_card_scuins_meanir.jsonl"),
            "training_history_rows_including_header": count_lines(root / "results/report/training_history.csv"),
            "news_headlines_csv_rows_including_header": count_lines(root / "data/news_db/headlines.csv"),
            **({"news_emotion_results_csv_rows_including_header": count_lines(root / "data/news_db/emotion_results.csv")} if (root / "data/news_db/emotion_results.csv").exists() else {}),
        }

    if args.data_only or args.github:
        metrics, metric_problems = {}, []
    else:
        metrics, metric_problems = check_metrics(root)
    report = {
        "root": str(root),
        "missing": missing,
        "counts": counts,
        "metrics_runs": sorted(metrics),
        "metric_problems": metric_problems,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if missing or metric_problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
