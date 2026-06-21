#!/usr/bin/env python3
"""card/SCUins raw 증강 파일에서 누락된 seed 행만 보충 생성한다.

현재 raw 파일과 seed 목록을 비교해 비어 있는 key만 Gemini로 다시 생성하고,
기존 행은 유지한다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SEED_PATH = PROJECT_DIR / "data" / "seeds_card_scuins_meanir.jsonl"
AUG_DIR = PROJECT_DIR / "data" / "augmented" / "card_scuins"
RAW_PATH = AUG_DIR / "aug_card_scuins_meanir_raw.jsonl"
PARTIAL_PATH = AUG_DIR / "aug_card_scuins_meanir_raw.partial.jsonl"

RE_WS = re.compile(r"\s+")
RE_KOREAN = re.compile(r"[가-힣]")


def normalize(text: str) -> str:
    return RE_WS.sub(" ", str(text).strip())


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)


def seed_key(row: dict) -> tuple:
    return (row.get("label"), row.get("seed_sample_id"), row.get("seed_idx"))


def raw_key(row: dict) -> tuple:
    return (row.get("target_label"), row.get("seed_sample_id"), row.get("seed_idx"))


def pass_basic_quality(text: str, seed_text: str, seen_texts: set[str], min_words: int, min_korean: int) -> tuple[bool, str, str]:
    text = normalize(text)
    if not text:
        return False, text, "empty"
    if len(text.split()) < min_words:
        return False, text, "too_few_words"
    if len(RE_KOREAN.findall(text)) < min_korean:
        return False, text, "too_few_korean_chars"
    if text == normalize(seed_text):
        return False, text, "same_as_seed"
    if text.lower() in seen_texts:
        return False, text, "duplicate_text"
    return True, text, "ok"


def parse_one_paraphrase(raw: str) -> str:
    txt = (raw or "").strip()
    txt = re.sub(r"^```[a-zA-Z]*\s*", "", txt)
    txt = re.sub(r"\s*```$", "", txt).strip()
    try:
        obj = json.loads(txt)
        if isinstance(obj, dict):
            for key in ["paraphrase", "text", "sentence"]:
                if obj.get(key):
                    return str(obj[key])
            arr = obj.get("paraphrases")
            if isinstance(arr, list) and arr:
                return str(arr[0])
        if isinstance(obj, list) and obj:
            return str(obj[0])
    except Exception:
        pass
    lines = [re.sub(r"^[\-\*\d\.\)\s]+", "", x).strip() for x in txt.splitlines() if x.strip()]
    return lines[0] if lines else ""


def init_client():
    load_dotenv(PROJECT_DIR / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(f"GEMINI_API_KEY가 없습니다. {PROJECT_DIR / '.env'}에 설정하세요.")
    from google import genai
    return genai.Client(api_key=api_key)


def generate_one(client, row: dict, model: str, temperature: float, top_p: float, max_output_tokens: int) -> tuple[str, str]:
    label = row["label"]
    seed_text = row["seed_text"]
    prompt = (
        f'아래 원문은 KOTE train 데이터에서 "{label}" 라벨을 포함하고, '
        f'card={row.get("card")}, SCUins={row.get("scuins")} 기준으로 선별된 SEED입니다.\n'
        f'이 원문을 참고해 "{label}" 감정이 더 명확하게 드러나는 한국어 문장 1개만 paraphrase하세요.\n\n'
        '출력 규칙:\n- JSON만 반환하세요.\n- 형식: {"paraphrase": "..."}\n- 설명, 마크다운, 추가 키 없이 JSON만 출력하세요.\n\n'
        '작성 조건:\n- 원문의 상황과 뉘앙스를 유지하되 문장 표현은 새롭게 바꾸세요.\n'
        '- target 감정이 중심이 되게 하세요.\n'
        '- 원문에 없는 구체적 인명, 장소, 사건을 추가하지 마세요.\n'
        '- 1~2문장, 일상 대화체 또는 SNS 댓글체로 작성하세요.\n\n'
        f'원문: {seed_text}'
    )
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config={"temperature": temperature, "top_p": top_p, "max_output_tokens": max_output_tokens},
    )
    raw = resp.text or ""
    return parse_one_paraphrase(raw), raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", default=str(SEED_PATH))
    parser.add_argument("--raw", default=str(RAW_PATH))
    parser.add_argument("--partial", default=str(PARTIAL_PATH))
    parser.add_argument("--model", default="gemini-2.5-flash-lite")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument("--max-retries", type=int, default=6)
    parser.add_argument("--sleep-sec", type=float, default=1.0)
    parser.add_argument("--min-words", type=int, default=3)
    parser.add_argument("--min-korean", type=int, default=6)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    seed_path = Path(args.seed)
    raw_path = Path(args.raw)
    partial_path = Path(args.partial)

    seeds = load_jsonl(seed_path)
    raw_rows = load_jsonl(raw_path)
    existing_keys = {raw_key(row) for row in raw_rows}
    seen_texts = {normalize(row.get("text", "")).lower() for row in raw_rows if row.get("text")}
    missing = [row for row in seeds if seed_key(row) not in existing_keys]

    print(f"[FILL] seeds={len(seeds):,}, raw={len(raw_rows):,}, missing={len(missing):,}")
    if missing:
        by_label: dict[str, int] = {}
        for row in missing:
            by_label[row["label"]] = by_label.get(row["label"], 0) + 1
        print(f"[FILL] missing_by_label={by_label}")
    if args.dry_run or not missing:
        return

    client = init_client()
    added = []
    failed = []
    for i, row in enumerate(missing, start=1):
        last_reason = "not_started"
        last_raw = ""
        for attempt in range(args.max_retries):
            try:
                text, raw = generate_one(client, row, args.model, args.temperature + 0.05 * attempt, args.top_p, args.max_output_tokens)
                last_raw = raw
                ok, norm, reason = pass_basic_quality(text, row["seed_text"], seen_texts, args.min_words, args.min_korean)
                last_reason = reason
                if ok:
                    rec = {
                        "text": norm,
                        "labels": [row["label"]],
                        "source": "aug_card_scuins_meanir_1to1",
                        "target_label": row["label"],
                        "seed_text": row["seed_text"],
                        "seed_idx": row["seed_idx"],
                        "seed_sample_id": row["seed_sample_id"],
                        "seed_card": row.get("card"),
                        "seed_scuins": row.get("scuins"),
                        "selection_rule": row.get("selection_rule"),
                        "model": args.model,
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                        "filled_missing": True,
                    }
                    raw_rows.append(rec)
                    added.append(rec)
                    seen_texts.add(norm.lower())
                    print(f"[OK] {i}/{len(missing)} {row['label']} seed_idx={row['seed_idx']}")
                    break
            except Exception as exc:
                last_reason = type(exc).__name__ + ": " + str(exc)[:160]
            time.sleep(args.sleep_sec * (attempt + 1))
        else:
            failed.append({"seed": row, "reason": last_reason, "raw": last_raw[:500]})
            print(f"[FAIL] {i}/{len(missing)} {row['label']} seed_idx={row['seed_idx']} reason={last_reason}")

    if added:
        write_jsonl(raw_path, raw_rows)
        write_jsonl(partial_path, raw_rows)
    report_path = raw_path.with_suffix(".fill_missing_report.json")
    report = {
        "seed_rows": len(seeds),
        "final_raw_rows": len(raw_rows),
        "missing_before": len(missing),
        "added": len(added),
        "failed": len(failed),
        "failed_items": failed,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] added={len(added)}, failed={len(failed)}, raw_rows={len(raw_rows):,}")
    print(f"[REPORT] {report_path}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
