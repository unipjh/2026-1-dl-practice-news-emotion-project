#!/usr/bin/env python3
"""현재 제출본 산출물을 읽어 재현용 Markdown 리포트를 생성한다."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


GUILT_LABEL = "죄책감"


def count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as f:
        return sum(1 for _ in f)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_metrics(root: Path) -> dict[str, dict]:
    out = {}
    for path in sorted((root / "results" / "model").glob("*/metrics.json")):
        out[path.parent.name] = load_json(path)
    return out



def load_training_history(root: Path) -> list[dict]:
    path = root / "results" / "report" / "training_history.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))

def read_label_lengths(tsv: Path) -> list[int]:
    lengths = []
    with tsv.open(encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            if len(row) >= 3:
                lengths.append(len([x for x in row[2].split(",") if x.strip()]))
    return lengths


def write_kote_intro(root: Path) -> None:
    ir = load_json(root / "data" / "kote" / "irlbl.json")
    lengths = read_label_lengths(root / "data" / "kote" / "train.tsv")
    multi = sum(1 for n in lengths if n > 1)
    lines = [
        "# KOTE 데이터 개요",
        "",
        f"- train/val/test: {count_lines(root / 'data/kote/train.tsv'):,} / {count_lines(root / 'data/kote/val.tsv'):,} / {count_lines(root / 'data/kote/test.tsv'):,}",
        f"- 레이블 수: 44",
        f"- train 평균 레이블 수: {sum(lengths) / max(len(lengths), 1):.2f}",
        f"- train 멀티라벨 샘플 비율: {multi / max(len(lengths), 1) * 100:.1f}%",
        f"- MeanIR: {ir['mean_ir']:.6f}",
        f"- minority 라벨 수: {ir['minor_label_count']}",
        f"- 가장 불균형한 라벨: {max(ir['irlbl'], key=ir['irlbl'].get)} (IRLbl={ir['irlbl'][max(ir['irlbl'], key=ir['irlbl'].get)]:.5f})",
        "",
        "## Minority Labels",
        "",
        ", ".join(ir["minor_labels"]),
        "",
        "## IRLbl",
        "",
        "| 라벨 | count | IRLbl |",
        "|---|---:|---:|",
    ]
    for label, score in sorted(ir["irlbl"].items(), key=lambda x: -x[1]):
        lines.append(f"| {label} | {ir['label_count'][label]:,} | {score:.5f} |")
    (root / "data" / "kote_intro.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_aug_strategy(root: Path) -> None:
    seed_csv = root / "data" / "aug_seed.csv"
    counts = Counter()
    need_by_label = {}
    rules = Counter()
    with seed_csv.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            counts[row["label"]] += 1
            need_by_label[row["label"]] = row["need"]
            rules[row["selection_rule"]] += 1

    fill_report_path = root / "data/augmented/card_scuins/aug_card_scuins_meanir_raw.fill_missing_report.json"
    fill_report = load_json(fill_report_path) if fill_report_path.exists() else {}

    lines = [
        "# 증강 전략 요약",
        "",
        "이 제출본은 MeanIR 기준 증강 필요량을 유지하면서, card/SCUins 기반 seed 선정 결과를 재현 가능한 CSV로 고정한다.",
        "",
        "## 실제 사용한 조건",
        "",
        "- `total_seed_gemini_aug`: 기존 MeanIR Gemini paraphrase 산출물 사용",
        "- `back_translation`: ko->en->ko 역번역 후 repair 스크립트의 기본 품질 검사를 통과한 산출물 사용",
        "- `card_scuins`: `card <= 하위 30% cutoff(=6)` 후보를 우선하고, 라벨별 SCUins 오름차순으로 seed를 선택한 1:1 paraphrase 산출물 사용",
        "- `card_scuins` 품질 처리: 최소 토큰/한글 수 기본 품질 조건과 exact dedup만 적용",
        "",
        "## 산출물 수",
        "",
        f"- total_seed_gemini_aug: {count_lines(root / 'data/augmented/total_seed_gemini_aug/total_seed_gemini_aug_meanir.jsonl'):,}",
        f"- back_translation repaired: {count_lines(root / 'data/augmented/bt/aug_bt_need19947_s42_repaired.jsonl'):,}",
        f"- card_scuins filtered: {count_lines(root / 'data/augmented/card_scuins/aug_card_scuins_meanir.jsonl'):,}",
        f"- aug_seed.csv rows: {sum(counts.values()):,}",
        "",
        "## card/SCUins Seed 라벨별 수",
        "",
        "| 라벨 | seed rows | MeanIR need |",
        "|---|---:|---:|",
    ]
    for label, n in counts.most_common():
        lines.append(f"| {label} | {n:,} | {int(float(need_by_label[label])):,} |")

    if fill_report:
        lines.extend([
            "",
            "## card/SCUins missing fill report",
            "",
            f"- seed rows: {fill_report.get('seed_rows'):,}",
            f"- final raw rows: {fill_report.get('final_raw_rows'):,}",
            f"- missing before fill: {fill_report.get('missing_before'):,}",
            f"- added: {fill_report.get('added'):,}",
            f"- failed: {fill_report.get('failed'):,}",
        ])
    (root / "data" / "aug_strategy.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_model_report(root: Path) -> None:
    metrics = load_metrics(root)
    lines = [
        "# 모델 결과 리포트",
        "",
        "최종 test 지표는 각 `results/model/<run>/metrics.json`에서 읽었다.",
        "baseline, Back Translation, card & SCUins는 원논문 설정과 맞추기 위해 epoch 10 기준 결과를 사용한다.",
        "현재 제출본의 기본 run명(`baseline_th03`, `aug_bt_need19947_s42_repaired`, `aug_card_scuins_meanir`)은 epoch 10 결과를 담고 있다.",
        "",
        "| run | F1-macro | F1-micro | 죄책감 F1 | threshold | epochs | model artifact |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for run, m in sorted(metrics.items()):
        guilt = m.get("per_label", {}).get(GUILT_LABEL)
        model_path = Path(m.get("model_path", ""))
        local_model = root / "results" / "model" / run / model_path.name if model_path.name else root / "results" / "model" / run
        lines.append(
            f"| {run} | {m.get('f1_macro', 0):.4f} | {m.get('f1_micro', 0):.4f} | "
            f"{(guilt if guilt is not None else 0):.4f} | {m.get('threshold', '')} | {m.get('epochs', '')} | `{local_model.relative_to(root)}` |"
        )

    history = load_training_history(root)
    if history:
        lines.extend([
            "",
            "## 기록된 Validation History",
            "",
            "보존된 학습 로그에서 확인 가능한 학습 구간만 적었다. 초기 train 로그 파일은 0바이트라 값으로 복원하지 않았다.",
            "",
            "| run | epoch | val_loss | val_macro_f1 | train_loss_epoch |",
            "|---|---:|---:|---:|---:|",
        ])
        canonical = {"baseline_th03", "aug_bt_need19947_s42_repaired", "aug_card_scuins_meanir"}
        for row in history:
            if row["run"] not in canonical:
                continue
            lines.append(
                f"| {row['run']} | {int(row['epoch'])} | {float(row['val_loss']):.3f} | "
                f"{float(row['val_macro_f1']):.3f} | {float(row['train_loss_epoch']):.3f} |"
            )

    best_run = None
    if metrics:
        best_run = max(metrics.items(), key=lambda item: item[1].get("f1_macro", -1))[0]
    lines.extend([
        "",
        "## 최종 선택",
        "",
        f"- F1-macro 기준 최고 run: `{best_run}`" if best_run else "- metrics 없음",
        "- 백엔드에서 이 모델을 사용하려면 `MODEL_PATH=results/model/aug_card_scuins_meanir/ckpt`처럼 checkpoint 디렉터리를 지정한다.",
    ])
    (root / "results" / "report" / "model_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

def write_comparison(root: Path) -> None:
    metrics = load_metrics(root)
    gemini_result_path = root / "results" / "report" / "total_seed_gemini_aug_results_comparison.json"
    gemini = load_json(gemini_result_path).get("total_seed_gemini_aug") if gemini_result_path.exists() else None

    baseline = metrics.get("baseline_th03")
    baseline_macro = baseline.get("f1_macro") if baseline else None

    rows = []
    def add(name: str, m: dict | None, note: str, guilt_available: bool = True):
        if not m:
            rows.append((name, None, None, None, None, note))
            return
        macro = m.get("f1_macro")
        delta = macro - baseline_macro if macro is not None and baseline_macro is not None else None
        guilt = m.get("per_label", {}).get(GUILT_LABEL) if guilt_available else None
        rows.append((name, macro, delta, m.get("f1_micro"), guilt, note))

    add("baseline_e10", metrics.get("baseline_th03"), "epoch 10 metrics")
    add("total_seed_gemini_aug", gemini, "기존 비교 JSON, epoch 10 재학습 아님", guilt_available=False)
    add("back_translation_e10", metrics.get("aug_bt_need19947_s42_repaired"), "BT repaired 19,947, epoch 10 metrics")
    add("card_scuins_e10", metrics.get("aug_card_scuins_meanir"), "card & SCUins filtered 19,734, epoch 10 metrics")

    lines = [
        "# 증강 조건 비교",
        "",
        "baseline, Back Translation, card & SCUins는 epoch 10 기준으로 맞춰 재평가했다. `total_seed_gemini_aug`는 저장된 기존 참고 결과다.",
        "",
        "| 조건 | F1-macro | Δ macro vs baseline_e10 | F1-micro | 죄책감 F1 | 근거 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for name, macro, delta, micro, guilt, note in rows:
        fmt = lambda v: "-" if v is None else f"{v:.4f}"
        lines.append(f"| {name} | {fmt(macro)} | {fmt(delta)} | {fmt(micro)} | {fmt(guilt)} | {note} |")

    lines.extend([
        "",
        "## 해석 메모",
        "",
        "- epoch 10 기준 F1-macro는 card & SCUins가 가장 높다.",
        "- card & SCUins는 baseline 대비 macro F1을 개선했지만 micro F1은 baseline보다 낮아, 빈도 중심 전체 성능보다 라벨 균형 관점의 개선으로 해석한다.",
        "- BT도 baseline 대비 macro F1은 소폭 개선하지만 card & SCUins보다 개선 폭이 작다.",
        "- aug_gemini는 epoch 10으로 재학습한 결과가 아니므로 참고 비교군으로만 둔다.",
    ])
    (root / "results" / "comparision.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    write_kote_intro(root)
    write_aug_strategy(root)
    write_model_report(root)
    write_comparison(root)
    print("[OK] reports generated")


if __name__ == "__main__":
    main()
