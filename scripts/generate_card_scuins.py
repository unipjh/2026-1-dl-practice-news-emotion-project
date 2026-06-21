#!/usr/bin/env python3
"""data/aug_seed.csv를 기준으로 card/SCUins 1:1 Gemini paraphrase를 생성한다."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

RE_WS = re.compile(r"\s+")


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
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_one(raw: str) -> str:
    text = (raw or "").strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            for key in ["paraphrase", "text", "sentence"]:
                if obj.get(key):
                    return str(obj[key])
            arr = obj.get("paraphrases")
            if isinstance(arr, list) and arr:
                return str(arr[0])
    except Exception:
        pass
    lines = [re.sub(r"^[\-\*\d\.\)\s]+", "", x).strip() for x in text.splitlines() if x.strip()]
    return lines[0] if lines else ""


def prompt_for(row: dict) -> str:
    return (
        f'아래 원문은 KOTE train 데이터에서 "{row["label"]}" 라벨을 포함하고, '
        f'card={row.get("card")}, SCUins={row.get("scuins")} 기준으로 선별된 SEED입니다.\n'
        f'이 원문을 참고해 "{row["label"]}" 감정이 더 명확하게 드러나는 한국어 문장 1개만 paraphrase하세요.\n\n'
        '출력 규칙:\n- JSON만 반환하세요.\n- 형식: {"paraphrase": "..."}\n- 설명, 마크다운, 추가 키 없이 JSON만 출력하세요.\n\n'
        "작성 조건:\n- 원문의 상황과 뉘앙스를 유지하되 문장 표현은 새롭게 바꾸세요.\n"
        "- target 감정이 중심이 되게 하세요.\n- 원문에 없는 구체적 인명, 장소, 사건을 추가하지 마세요.\n"
        "- 1~2문장, 일상 대화체 또는 SNS 댓글체로 작성하세요.\n\n"
        f'원문: {row["seed_text"]}'
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--seed-csv", default="data/aug_seed.csv")
    parser.add_argument("--output", default="data/augmented/card_scuins/aug_card_scuins_meanir_raw.jsonl")
    parser.add_argument("--model", default="gemini-2.5-flash-lite")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument("--max-retries", type=int, default=6)
    parser.add_argument("--sleep-sec", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    load_dotenv(root / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(f"GEMINI_API_KEY가 필요합니다: {root / '.env'}")

    from google import genai

    client = genai.Client(api_key=api_key)
    seed_path = root / args.seed_csv
    out_path = root / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with seed_path.open(encoding="utf-8") as f:
        seeds = list(csv.DictReader(f))
    if args.limit:
        seeds = seeds[: args.limit]

    done_keys = set()
    if args.resume and out_path.exists():
        with out_path.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                done_keys.add((row.get("target_label"), str(row.get("seed_sample_id")), str(row.get("seed_idx"))))

    mode = "a" if args.resume else "w"
    added = 0
    with out_path.open(mode, encoding="utf-8") as f:
        for idx, row in enumerate(seeds, start=1):
            key = (row["label"], row["seed_sample_id"], row["seed_idx"])
            if key in done_keys:
                continue
            last_error = ""
            for attempt in range(args.max_retries):
                try:
                    resp = client.models.generate_content(
                        model=args.model,
                        contents=prompt_for(row),
                        config={
                            "temperature": args.temperature + 0.05 * attempt,
                            "top_p": args.top_p,
                            "max_output_tokens": args.max_output_tokens,
                        },
                    )
                    text = normalize(parse_one(resp.text or ""))
                    if text:
                        rec = {
                            "text": text,
                            "labels": [row["label"]],
                            "source": "aug_card_scuins_meanir_1to1",
                            "target_label": row["label"],
                            "seed_text": row["seed_text"],
                            "seed_idx": int(row["seed_idx"]),
                            "seed_sample_id": int(row["seed_sample_id"]),
                            "seed_card": int(float(row["card"])),
                            "seed_scuins": float(row["scuins"]),
                            "selection_rule": row["selection_rule"],
                            "model": args.model,
                            "created_at": datetime.now().isoformat(timespec="seconds"),
                        }
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        f.flush()
                        added += 1
                        print(f"[OK] {idx}/{len(seeds)} {row['label']} seed_idx={row['seed_idx']}")
                        break
                except Exception as exc:
                    last_error = type(exc).__name__ + ": " + str(exc)[:160]
                time.sleep(args.sleep_sec * (attempt + 1))
            else:
                print(f"[FAIL] {idx}/{len(seeds)} {row['label']} seed_idx={row['seed_idx']} {last_error}")

    print(f"[DONE] added={added:,}, output={out_path}")


if __name__ == "__main__":
    main()
