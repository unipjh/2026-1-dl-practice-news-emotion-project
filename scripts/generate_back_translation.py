#!/usr/bin/env python3
"""KOTE 역번역 비교군을 생성한다.

원본 KOTE label은 유지하고 텍스트만 ko -> pivot -> ko 번역으로 증강한다.
출력 JSONL은 trainer가 바로 읽을 수 있도록 정수 label id를 labels에 저장한다.

실행 예시:
  python scripts/generate_back_translation.py --max-samples 19947 --out aug_bt_need19947_s42.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
KOTE_DIR = DATA_DIR / "kote"
AUG_DIR = DATA_DIR / "augmented" / "bt"
TRAIN_TSV = KOTE_DIR / "train.tsv"

LABELS = [
    "불평/불만", "환영/호의", "감동/감탄", "지긋지긋", "고마움",
    "슬픔", "화남/분노", "존경", "기대감", "우쭐댐/무시함",
    "안타까움/실망", "비장함", "의심/불신", "뿌듯함", "편안/쾌적",
    "신기함/관심", "아껴주는", "부끄러움", "공포/무서움", "절망",
    "한심함", "역겨움/징그러움", "짜증", "어이없음", "없음",
    "패배/자기혐오", "귀찮음", "힘듦/지침", "즐거움/신남", "깨달음",
    "죄책감", "증오/혐오", "흐뭇함(귀여움/예쁨)", "당황/난처", "경악",
    "부담/안_내킴", "서러움", "재미없음", "불쌍함/연민", "놀람",
    "행복", "불안/걱정", "기쁨", "안심/신뢰",
]


def load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for rid, text, labels in csv.reader(f, delimiter="\t"):
            label_ids = [int(x) for x in labels.split(",") if x.strip()]
            rows.append({"id": rid, "text": text, "label_ids": label_ids, "labels": [LABELS[i] for i in label_ids]})
    return rows


def minority_label_ids(rows: list[dict]) -> set[int]:
    counts = Counter(i for r in rows for i in r["label_ids"])
    max_count = max(counts.values())
    irlbl = {i: max_count / counts[i] for i in range(len(LABELS)) if counts[i] > 0}
    mean_ir = sum(irlbl.values()) / len(irlbl)
    return {i for i, v in irlbl.items() if v > mean_ir}


def select_rows(rows: list[dict], mode: str, max_samples: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    if mode == "minority":
        minor = minority_label_ids(rows)
        pool = [r for r in rows if any(i in minor for i in r["label_ids"])]
    else:
        pool = list(rows)
    rng.shuffle(pool)
    return pool[:max_samples]


def batched(items: list[str], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def load_translation_model(model_name: str, device: int):
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "BT 비교군 실행 전 `pip install torch transformers sentencepiece sacremoses`가 필요합니다."
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    target_device = torch.device(f"cuda:{device}" if device >= 0 and torch.cuda.is_available() else "cpu")
    model.to(target_device)
    model.eval()
    return tokenizer, model, target_device


def translate_texts(texts: list[str], model_name: str, batch_size: int, device: int, max_length: int) -> list[str]:
    import torch

    tokenizer, model, target_device = load_translation_model(model_name, device=device)
    out = []
    for batch in batched(texts, batch_size):
        inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=max_length)
        inputs = {k: v.to(target_device) for k, v in inputs.items()}
        with torch.no_grad():
            generated = model.generate(**inputs, max_length=max_length)
        out.extend(tokenizer.batch_decode(generated, skip_special_tokens=True))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-tsv", default=str(TRAIN_TSV))
    parser.add_argument("--out", default="aug_bt_need19947_s42.jsonl", help="output file name under data/augmented/bt")
    parser.add_argument("--max-samples", type=int, default=19947)
    parser.add_argument("--sample-mode", choices=["minority", "all"], default="minority")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", type=int, default=-1, help="-1 for CPU, CUDA device id otherwise")
    parser.add_argument("--ko-en-model", default="Helsinki-NLP/opus-mt-ko-en")
    parser.add_argument("--en-ko-model", default="Helsinki-NLP/opus-mt-tc-big-en-ko")
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    AUG_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AUG_DIR / args.out
    if out_path.exists() and not args.resume:
        raise SystemExit(f"이미 존재합니다: {out_path}  (--resume 또는 다른 --out 사용)")

    rows = select_rows(load_rows(Path(args.train_tsv)), args.sample_mode, args.max_samples, args.seed)
    texts = [r["text"] for r in rows]
    print(f"[BT] selected rows={len(rows):,}, mode={args.sample_mode}, seed={args.seed}")
    print(f"[BT] ko->en model={args.ko_en_model}")
    pivot_texts = translate_texts(texts, args.ko_en_model, args.batch_size, args.device, args.max_length)
    print(f"[BT] en->ko model={args.en_ko_model}")
    bt_texts = translate_texts(pivot_texts, args.en_ko_model, args.batch_size, args.device, args.max_length)

    with out_path.open("w", encoding="utf-8") as f:
        for row, pivot, bt in zip(rows, pivot_texts, bt_texts):
            rec = {
                "text": bt,
                "labels": row["label_ids"],
                "label_names": row["labels"],
                "source": "back_translation",
                "seed_id": row["id"],
                "seed_text": row["text"],
                "pivot_text": pivot,
                "sample_mode": args.sample_mode,
                "ko_en_model": args.ko_en_model,
                "en_ko_model": args.en_ko_model,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[BT] saved: {out_path}")


if __name__ == "__main__":
    main()
