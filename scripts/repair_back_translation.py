#!/usr/bin/env python3
"""역번역 생성 결과를 보정해 학습용 JSONL을 완성한다.

기존 raw JSONL에서 품질 조건을 통과한 행은 유지하고, 깨진 행은 재생성해
목표 행 수에 도달할 때까지 보충한다. raw 파일은 직접 수정하지 않는다.

실행 예시:
  python scripts/repair_back_translation.py --input aug_bt_need19947_s42.jsonl --out aug_bt_need19947_s42_repaired.jsonl --target 19947
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

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

RE_WS = re.compile(r"\s+")
RE_KOREAN = re.compile(r"[가-힣]")
RE_LATIN = re.compile(r"[A-Za-z]")
RE_HAN = re.compile(r"[\u4e00-\u9fff]")
RE_BAD_PHRASES = re.compile(
    r"(장쑤|US 호텔|China|Newport|acceptance|Color upon|super general|well、、|、、、、|。。。。)"
)


def normalize(text: str) -> str:
    return RE_WS.sub(" ", str(text).strip())


def repetition_reason(text: str) -> str | None:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 40:
        return None
    for size in range(2, 13):
        seen: Counter[str] = Counter(
            compact[i:i + size] for i in range(0, max(len(compact) - size + 1, 0), size)
        )
        token, count = seen.most_common(1)[0]
        if count >= 8 and len(token) * count >= len(compact) * 0.35:
            return "repeated_chunk"
    words = text.split()
    if len(words) >= 12 and len(set(words)) / len(words) < 0.35:
        return "low_unique_word_ratio"
    return None


def quality_reason(record: dict, min_korean: int, min_words: int, max_chars: int) -> str | None:
    text = normalize(record.get("text", ""))
    labels = record.get("labels")
    if not isinstance(labels, list) or not labels or not all(isinstance(x, int) for x in labels):
        return "bad_labels"
    if not text:
        return "empty_text"
    if len(text) > max_chars:
        return "too_long"
    if len(text.split()) < min_words:
        return "too_few_words"
    korean = len(RE_KOREAN.findall(text))
    latin = len(RE_LATIN.findall(text))
    han = len(RE_HAN.findall(text))
    if korean < min_korean:
        return "too_few_korean_chars"
    if han >= 2:
        return "han_chars"
    if latin > korean and korean < 20:
        return "latin_dominant"
    if RE_BAD_PHRASES.search(text):
        return "known_broken_phrase"
    rep = repetition_reason(text)
    if rep:
        return rep
    return None


def pivot_reason(text: str) -> str | None:
    text = normalize(text)
    if not text:
        return "empty_pivot"
    latin = len(RE_LATIN.findall(text))
    if latin < 3:
        return "too_few_latin_chars"
    rep = repetition_reason(text)
    if rep:
        return "pivot_" + rep
    return None


def load_train_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for rid, text, labels in csv.reader(f, delimiter="\t"):
            label_ids = [int(x) for x in labels.split(",") if x.strip()]
            rows.append({
                "id": rid,
                "text": text,
                "label_ids": label_ids,
                "labels": [LABELS[i] for i in label_ids],
            })
    return rows


def minority_label_ids(rows: list[dict]) -> set[int]:
    counts = Counter(i for row in rows for i in row["label_ids"])
    max_count = max(counts.values())
    irlbl = {i: max_count / counts[i] for i in range(len(LABELS)) if counts[i] > 0}
    mean_ir = sum(irlbl.values()) / len(irlbl)
    return {i for i, score in irlbl.items() if score > mean_ir}


def select_pool(rows: list[dict], mode: str, seed: int) -> list[dict]:
    if mode == "minority":
        minor = minority_label_ids(rows)
        pool = [row for row in rows if any(i in minor for i in row["label_ids"])]
    else:
        pool = list(rows)
    rng = random.Random(seed)
    rng.shuffle(pool)
    return pool


def batched(items: list[dict], size: int) -> Iterable[list[dict]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


class Translator:
    def __init__(self, model_name: str, device: int):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.device = torch.device(f"cuda:{device}" if device >= 0 and torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()

    def translate(self, texts: list[str], max_length: int, attempt: int) -> list[str]:
        inputs = self.tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=max_length)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        gen_kwargs = {
            "max_length": max_length,
            "num_beams": 4,
            "no_repeat_ngram_size": 3,
            "repetition_penalty": 1.15,
        }
        if attempt > 0:
            gen_kwargs.update({"do_sample": True, "top_p": 0.95, "temperature": 0.8 + 0.1 * min(attempt, 3)})
        with self.torch.no_grad():
            generated = self.model.generate(**inputs, **gen_kwargs)
        return self.tokenizer.batch_decode(generated, skip_special_tokens=True)


def candidate_from_record(record: dict) -> dict | None:
    seed_text = record.get("seed_text")
    labels = record.get("labels")
    if not seed_text or not isinstance(labels, list):
        return None
    return {
        "id": str(record.get("seed_id", "")),
        "text": seed_text,
        "label_ids": labels,
        "labels": record.get("label_names") or [LABELS[i] for i in labels if 0 <= i < len(LABELS)],
    }


def record_from_candidate(candidate: dict, pivot: str, bt_text: str, sample_mode: str, ko_en_model: str, en_ko_model: str, attempt: int) -> dict:
    return {
        "text": normalize(bt_text),
        "labels": candidate["label_ids"],
        "label_names": candidate["labels"],
        "source": "back_translation",
        "seed_id": candidate["id"],
        "seed_text": candidate["text"],
        "pivot_text": normalize(pivot),
        "sample_mode": sample_mode,
        "ko_en_model": ko_en_model,
        "en_ko_model": en_ko_model,
        "repair_attempt": attempt,
    }


def read_existing(path: Path, args) -> tuple[list[dict], list[dict], Counter[str]]:
    good = []
    bad_candidates = []
    reasons: Counter[str] = Counter()
    if not path.exists():
        return good, bad_candidates, reasons
    with path.open(encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            reason = quality_reason(record, args.min_korean, args.min_words, args.max_chars)
            if reason is None:
                record.setdefault("quality_status", "kept_from_input")
                good.append(record)
            else:
                reasons[reason] += 1
                candidate = candidate_from_record(record)
                if candidate:
                    candidate["bad_reason"] = reason
                    bad_candidates.append(candidate)
    return good, bad_candidates, reasons


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="aug_bt_need19947_s42.jsonl", help="raw BT JSONL under data/augmented/bt")
    parser.add_argument("--out", default="aug_bt_need19947_s42_repaired.jsonl", help="repaired JSONL under data/augmented/bt")
    parser.add_argument("--report", default=None, help="quality report JSON path. Default: <out>.report.json")
    parser.add_argument("--train-tsv", default=str(TRAIN_TSV))
    parser.add_argument("--target", type=int, default=19947)
    parser.add_argument("--sample-mode", choices=["minority", "all"], default="minority")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", type=int, default=-1)
    parser.add_argument("--ko-en-model", default="Helsinki-NLP/opus-mt-ko-en")
    parser.add_argument("--en-ko-model", default="Helsinki-NLP/opus-mt-tc-big-en-ko")
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--max-retries", type=int, default=6)
    parser.add_argument("--max-rounds", type=int, default=3, help="refill the queue from the same candidate pool with higher attempt ids")
    parser.add_argument("--checkpoint-every", type=int, default=500, help="write partial output every N accepted rows")
    parser.add_argument("--min-korean", type=int, default=8)
    parser.add_argument("--min-words", type=int, default=3)
    parser.add_argument("--max-chars", type=int, default=600)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    in_path = AUG_DIR / args.input
    out_path = AUG_DIR / args.out
    report_path = Path(args.report) if args.report else out_path.with_suffix(".report.json")
    if out_path.exists() and not args.overwrite:
        raise SystemExit(f"이미 존재합니다: {out_path}  (--overwrite 사용 또는 --out 변경)")

    good, bad_candidates, input_reasons = read_existing(in_path, args)
    good = good[:args.target]
    used_good_seed_ids = {str(row.get("seed_id")) for row in good}
    print(f"[BT-REPAIR] input={in_path}")
    print(f"[BT-REPAIR] kept={len(good):,}, rejected={sum(input_reasons.values()):,}, target={args.target:,}")
    if len(good) >= args.target:
        write_jsonl(out_path, good[:args.target])
        report = {"target": args.target, "kept_from_input": args.target, "input_reject_reasons": dict(input_reasons), "regenerated": 0}
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[BT-REPAIR] saved={out_path}")
        return

    train_rows = load_train_rows(Path(args.train_tsv))
    pool = select_pool(train_rows, args.sample_mode, args.seed)
    pool_by_id = {str(row["id"]): row for row in pool}

    base_candidates: list[dict] = []
    queued_ids: set[str] = set()
    for candidate in bad_candidates:
        cid = str(candidate["id"])
        if cid in pool_by_id and cid not in queued_ids:
            base_candidates.append(candidate)
            queued_ids.add(cid)
    for row in pool:
        cid = str(row["id"])
        if cid not in used_good_seed_ids and cid not in queued_ids:
            base_candidates.append(dict(row))
            queued_ids.add(cid)

    queue: list[dict] = []
    for round_id in range(args.max_rounds):
        round_candidates = [dict(candidate, attempt=round_id) for candidate in base_candidates]
        random.Random(args.seed + round_id + 1000).shuffle(round_candidates)
        queue.extend(round_candidates)

    partial_path = out_path.with_suffix(".partial.jsonl")
    ko_en = Translator(args.ko_en_model, args.device)
    en_ko = Translator(args.en_ko_model, args.device)
    regen_reasons: Counter[str] = Counter()
    regenerated = 0
    exhausted = 0
    cursor = 0

    while len(good) < args.target and cursor < len(queue):
        batch = queue[cursor:cursor + args.batch_size]
        cursor += len(batch)
        attempt = max(candidate.get("attempt", 0) for candidate in batch)
        texts = [candidate["text"] for candidate in batch]
        pivots = ko_en.translate(texts, args.max_length, attempt)
        bt_texts = en_ko.translate(pivots, args.max_length, attempt)

        for candidate, pivot, bt_text in zip(batch, pivots, bt_texts):
            record = record_from_candidate(
                candidate, pivot, bt_text, args.sample_mode, args.ko_en_model, args.en_ko_model, candidate.get("attempt", 0)
            )
            reason = pivot_reason(pivot) or quality_reason(record, args.min_korean, args.min_words, args.max_chars)
            if reason is None:
                record["quality_status"] = "regenerated"
                good.append(record)
                regenerated += 1
                if len(good) >= args.target:
                    break
            else:
                regen_reasons[reason] += 1
                next_attempt = candidate.get("attempt", 0) + 1
                if next_attempt < args.max_retries:
                    retry_candidate = dict(candidate)
                    retry_candidate["attempt"] = next_attempt
                    queue.append(retry_candidate)
                else:
                    exhausted += 1
        if len(good) % 200 == 0 or len(good) >= args.target:
            print(f"[BT-REPAIR] accepted={len(good):,}/{args.target:,} queue_cursor={cursor:,}/{len(queue):,}", flush=True)
        if args.checkpoint_every and len(good) % args.checkpoint_every == 0:
            write_jsonl(partial_path, good)

    if len(good) < args.target:
        write_jsonl(partial_path, good)
        report = {
            "target": args.target,
            "output_rows": len(good),
            "kept_from_input": len(good) - regenerated,
            "regenerated": regenerated,
            "input_reject_reasons": dict(input_reasons),
            "regeneration_reject_reasons": dict(regen_reasons),
            "exhausted_candidates": exhausted,
            "status": "partial",
            "partial_output": str(partial_path),
            "hint": "Run again with --sample-mode all, --max-rounds 5, or lower --min-korean only after inspecting quality.",
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        raise SystemExit(
            f"목표 수를 채우지 못했습니다: accepted={len(good):,}, target={args.target:,}, exhausted={exhausted:,}. "
            f"partial 저장: {partial_path}. --sample-mode all 또는 --max-rounds 증가를 사용하세요."
        )

    write_jsonl(out_path, good[:args.target])
    report = {
        "target": args.target,
        "output_rows": args.target,
        "kept_from_input": args.target - regenerated,
        "regenerated": regenerated,
        "input_reject_reasons": dict(input_reasons),
        "regeneration_reject_reasons": dict(regen_reasons),
        "exhausted_candidates": exhausted,
        "input": str(in_path),
        "output": str(out_path),
        "status": "complete",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[BT-REPAIR] saved={out_path}")
    print(f"[BT-REPAIR] report={report_path}")


if __name__ == "__main__":
    main()
