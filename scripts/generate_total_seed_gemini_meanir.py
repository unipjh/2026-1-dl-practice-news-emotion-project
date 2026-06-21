#!/usr/bin/env python3
"""전체 seed 기반 Gemini MeanIR 증강을 생성한다.

실행 전 조건:
  data/augmented/total_seed_gemini_aug/label_stats.json, data/augmented/total_seed_gemini_aug/augmentation_targets.json 필요
  생성 후 fine-tuning 입력 JSONL까지 같은 디렉토리에 저장

실행:
  python scripts/generate_total_seed_gemini_meanir.py

중단 후 재시작: partial 파일 자동 이어받기
"""

import os
import json
import re
import time
import random

import google.generativeai as genai

# ── 경로 ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MEANIR_DIR = os.path.join(DATA_DIR, "augmented", "total_seed_gemini_aug")

STATS_PATH   = os.path.join(MEANIR_DIR, "label_stats.json")
TARGETS_PATH = os.path.join(MEANIR_DIR, "augmentation_targets.json")
OUTPUT_PATH  = os.path.join(MEANIR_DIR, "augmented_data_meanir_gemini.json")
JSONL_OUTPUT_PATH = os.path.join(MEANIR_DIR, "total_seed_gemini_aug_meanir.jsonl")
PARTIAL_PATH = os.path.join(MEANIR_DIR, "augmented_data_meanir_gemini_partial.json")

BATCH_K      = 10
SEED         = 42
MAX_RETRY    = 2
SLEEP_SEC    = 2.0
AUTOSAVE_N   = 200   # N개 성공마다 partial 저장

PROMPT_TEMPLATE = """다음 텍스트는 아래의 감정들을 표현하는 한국어 온라인 댓글입니다.

감정 카테고리: {labels}
원본 텍스트: {text}

위 감정들이 자연스럽게 드러나도록 원본 텍스트의 paraphrase를 {k}개 생성하세요.
조건:
- 동일한 감정 표현을 유지하되 어휘와 문장 구조는 다르게 작성하세요
- 한국어 온라인 댓글 특유의 구어체와 표현을 유지하세요
- JSON만 반환하세요. 형식: {{"paraphrases": ["...", "...", ...]}}
- 설명, 마크다운, 추가 키 없이 JSON만 출력하세요"""


def _strip_fences(t: str) -> str:
    t = t.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def parse_paraphrases(raw: str) -> list[str]:
    t = _strip_fences(raw)
    try:
        obj = json.loads(t)
        arr = obj.get("paraphrases", [])
        if isinstance(arr, list):
            return [str(x).strip() for x in arr if str(x).strip()]
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, flags=re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            arr = obj.get("paraphrases", [])
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass
    lines = [x.strip() for x in t.splitlines() if x.strip()]
    return [re.sub(r"^[\-\*\d\.\)\s]+", "", x).strip() for x in lines if x.strip()]


def call_gemini(model, prompt: str, gen_cfg: dict) -> tuple[list[str], bool]:
    for attempt in range(MAX_RETRY + 1):
        try:
            resp = model.generate_content(prompt, generation_config=gen_cfg)
            raw = resp.text or ""
            paras = parse_paraphrases(raw)
            if paras:
                return paras, True
        except Exception as e:
            msg = str(e)
            print(f"    [재시도 {attempt+1}] {msg[:80]}")
            wait = 30.0 if "429" in msg else SLEEP_SEC * 2
            if attempt < MAX_RETRY:
                time.sleep(wait)
    return [], False


def autosave(results: list, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)



def write_training_jsonl(results: list, path: str) -> int:
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in results:
            if not r.get("generation_success"):
                continue
            text = str(r.get("augmented_text", "")).strip()
            labels = r.get("labels") or []
            if not text or not labels:
                continue
            rec = {
                "text": text,
                "labels": labels,
                "source": "total_seed_gemini_aug",
                "target_condition": r.get("target_condition", "meanir"),
                "minority_label_target": r.get("minority_label_target", []),
                "seed_text": r.get("original_text", ""),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n

def load_dotenv(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def main():
    load_dotenv(os.path.join(BASE_DIR, ".env"))

    # ── 파일 확인 ──────────────────────────────────────────────────
    for p in [STATS_PATH, TARGETS_PATH]:
        if not os.path.exists(p):
            print(f"[오류] {p} 없음.")
            return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[오류] GEMINI_API_KEY 없음.")
        return

    # ── 데이터 로드 ────────────────────────────────────────────────
    with open(STATS_PATH, encoding="utf-8") as f:
        stats = json.load(f)
    with open(TARGETS_PATH, encoding="utf-8") as f:
        all_targets = json.load(f)

    meanir_targets = stats["augmentation_targets"]["meanir"]  # {label: count}
    minority_labels = stats["minority_labels"]

    # ── resume: partial 이어받기 ───────────────────────────────────
    if os.path.exists(PARTIAL_PATH):
        with open(PARTIAL_PATH, encoding="utf-8") as f:
            results = json.load(f)
        print(f"[RESUME] partial 로드: {len(results)}개")
    else:
        results = []

    # 레이블별 이미 생성된 수 집계
    done_count: dict[str, int] = {label: 0 for label in minority_labels}
    for r in results:
        if not r.get("generation_success"):
            continue
        for lbl in r.get("minority_label_target", []):
            if lbl in done_count:
                done_count[lbl] += 1

    # ── Gemini 설정 ────────────────────────────────────────────────
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    gen_cfg = {"temperature": 0.7, "max_output_tokens": 1024}
    print("Gemini 모델: gemini-2.5-flash-lite  batch_k=10\n")

    # ── 레이블별 seed 풀 구성 ──────────────────────────────────────
    label_seed_pool: dict[str, list[dict]] = {label: [] for label in minority_labels}
    for sample in all_targets:
        for lbl in sample.get("minority_labels_in_sample", []):
            if lbl in label_seed_pool:
                label_seed_pool[lbl].append(sample)

    random.seed(SEED)
    success_since_save = 0
    total_target = sum(meanir_targets.values())
    total_done_start = sum(done_count.values())
    print(f"MeanIR 총 목표: {total_target:,}개  (이미 완료: {total_done_start:,}개)\n")

    # ── 레이블별 증강 루프 ─────────────────────────────────────────
    for label in minority_labels:
        target_n = meanir_targets.get(label, 0)
        already  = done_count[label]
        remain   = target_n - already
        if remain <= 0:
            print(f"  [{label}] 완료 (target={target_n}, done={already})")
            continue

        pool = label_seed_pool[label]
        if not pool:
            print(f"  [{label}] seed 없음. 건너뜀.")
            continue

        print(f"  [{label}]  target={target_n}  done={already}  remain={remain}  pool={len(pool)}")
        pool_cycle = pool[:]
        random.shuffle(pool_cycle)
        pool_idx = 0

        while done_count[label] < target_n:
            seed = pool_cycle[pool_idx % len(pool_cycle)]
            pool_idx += 1

            labels_str = ", ".join(seed["labels"])
            prompt = PROMPT_TEMPLATE.format(labels=labels_str, text=seed["text"], k=BATCH_K)

            paras, success = call_gemini(model, prompt, gen_cfg)

            still_need = target_n - done_count[label]
            kept = 0
            for p in paras[:still_need]:
                results.append({
                    "original_text":       seed["text"],
                    "augmented_text":      p,
                    "labels":              seed["labels"],
                    "minority_label_target": [label],
                    "target_condition":    "meanir",
                    "generation_success":  True,
                })
                done_count[label] += 1
                success_since_save += 1
                kept += 1

            if not success or not paras:
                results.append({
                    "original_text":       seed["text"],
                    "augmented_text":      "",
                    "labels":              seed["labels"],
                    "minority_label_target": [label],
                    "target_condition":    "meanir",
                    "generation_success":  False,
                })

            remain_now = target_n - done_count[label]
            print(f"    gen={len(paras)} kept={kept} remain={remain_now}", flush=True)

            if success_since_save >= AUTOSAVE_N:
                autosave(results, PARTIAL_PATH)
                print(f"    [AUTOSAVE] {len(results)}개")
                success_since_save = 0

            if done_count[label] < target_n:
                time.sleep(SLEEP_SEC)

        print(f"  [{label}] 완료 ✓  생성={done_count[label]}\n")

    # ── 최종 저장 ─────────────────────────────────────────────────
    autosave(results, OUTPUT_PATH)
    autosave(results, PARTIAL_PATH)
    jsonl_total = write_training_jsonl(results, JSONL_OUTPUT_PATH)

    success_total = sum(1 for r in results if r["generation_success"])
    fail_total    = len(results) - success_total
    print(f"\n=== MeanIR 증강 완료 ===")
    print(f"  성공: {success_total:,}  실패: {fail_total:,}  실패율: {fail_total/max(len(results),1)*100:.1f}%")
    print(f"  저장: {OUTPUT_PATH}")
    print(f"  JSONL 저장: {JSONL_OUTPUT_PATH} ({jsonl_total:,} rows)")


if __name__ == "__main__":
    main()
