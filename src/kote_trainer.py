"""
kote_trainer.py — KcELECTRA/KOTE 파인튜닝 및 추론 래퍼

KOTE 학습 코드 기반. 노트북에서 설정값만 넘겨 실행할 수 있도록
run_finetune / run_inference 두 함수로 인터페이스를 통일.
"""

from __future__ import annotations

import csv
import json
import os
import random
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import pytorch_lightning as pl
from torch.utils.data import Dataset, DataLoader
from transformers import ElectraModel, AutoTokenizer, get_linear_schedule_with_warmup
from sklearn.metrics import f1_score

# ── 상수 ──────────────────────────────────────────────────────────
MODEL_NAME = "beomi/KcELECTRA-base"
REVISION   = "v2021"
NUM_LABELS = 44
MAX_LEN    = 512

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_MODEL_DIR = PROJECT_ROOT / "resources" / "kcelectra-base"


def model_source() -> str:
    """Prefer the submission-local KcELECTRA files over a Hugging Face cache."""
    if LOCAL_MODEL_DIR.exists():
        return str(LOCAL_MODEL_DIR)
    return MODEL_NAME


def tokenizer_source() -> str:
    return model_source()


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
LABEL2IDX = {l: i for i, l in enumerate(LABELS)}


# ── Seed 고정 ──────────────────────────────────────────────────────
def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    pl.seed_everything(seed, workers=True)


# ── Token Augmentation (공식 KOTE 코드 그대로) ────────────────────
# 학습 시 입력 다양성을 높이는 전처리. masking + random token switch.
def _token_masking(encoding, prob):
    for i, token in enumerate(encoding["input_ids"][0]):
        if token not in [0, 1, 2, 3]:
            if np.random.uniform(0, 1) < prob:
                encoding["input_ids"][0][i] = 4  # [MASK]
    return encoding


def _token_switching(encoding, prob, vocab_size):
    for i, token in enumerate(encoding["input_ids"][0]):
        if token not in [0, 1, 2, 3, 4]:
            if np.random.uniform(0, 1) < prob:
                encoding["input_ids"][0][i] = np.random.choice(np.arange(5, vocab_size), 1)[0]
    return encoding


def _mask_and_switch(encoding, prob=0.1, vocab_size=32000):
    encoding = _token_masking(encoding, prob / 2)
    encoding = _token_switching(encoding, prob / 2, vocab_size)
    return encoding


# ── Dataset ───────────────────────────────────────────────────────
def _load_tsv(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            if len(row) < 3:
                continue
            label_indices = [int(x) for x in row[2].split(",") if x.strip()]
            rows.append({"text": row[1], "labels": label_indices})
    return rows


def _load_jsonl(path: str) -> list[dict]:
    """증강 JSONL 형식: {"text": ..., "label": "감정명"} 또는 {"text": ..., "labels": [idx,...]}"""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line.strip())
            if not obj.get("text", "").strip():
                continue
            # label 필드 처리 (JSONL 형식이 다를 수 있음)
            if "labels" in obj:
                label_indices = obj["labels"] if isinstance(obj["labels"][0], int) else [LABEL2IDX[l] for l in obj["labels"]]
            elif "label" in obj:
                label_name = obj["label"]
                label_indices = [LABEL2IDX[label_name]] if label_name in LABEL2IDX else []
            else:
                continue
            if label_indices:
                rows.append({"text": obj["text"], "labels": label_indices})
    return rows


class _KOTEDataset(Dataset):
    def __init__(self, rows: list[dict], tokenizer, augment: bool = False):
        self.rows = rows
        self.tokenizer = tokenizer
        self.augment = augment
        self.vocab_size = tokenizer.vocab_size

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, idx):
        row = self.rows[idx]
        encoding = self.tokenizer(
            row["text"],
            add_special_tokens=True,
            max_length=MAX_LEN,
            padding="max_length",
            truncation=True,
            return_attention_mask=True,
            return_token_type_ids=False,
            return_tensors="pt",
        )
        if self.augment:
            encoding = _mask_and_switch(encoding, prob=0.1, vocab_size=self.vocab_size)

        label_vec = torch.zeros(NUM_LABELS, dtype=torch.float)
        for i in row["labels"]:
            if 0 <= i < NUM_LABELS:
                label_vec[i] = 1.0
        return {
            "input_ids":      encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "labels":         label_vec,
        }


# ── 모델 ──────────────────────────────────────────────────────────
class _KOTEtagger(pl.LightningModule):
    def __init__(self, n_training_steps: int, n_warmup_steps: int,
                 threshold: float = 0.3):
        super().__init__()
        self.electra = ElectraModel.from_pretrained(
            model_source(),
            revision=None if LOCAL_MODEL_DIR.exists() else REVISION,
            local_files_only=True,
            use_safetensors=False,
        )
        self.classifier = nn.Linear(self.electra.config.hidden_size, NUM_LABELS)
        self.criterion = nn.BCELoss()
        self.n_training_steps = n_training_steps
        self.n_warmup_steps = n_warmup_steps
        self.threshold = threshold
        self._val_preds, self._val_labels = [], []

    def forward(self, input_ids, attention_mask, labels=None):
        output = self.electra(input_ids=input_ids, attention_mask=attention_mask)
        output = output.last_hidden_state[:, 0, :]  # [CLS] 토큰
        output = torch.sigmoid(self.classifier(output))
        loss = self.criterion(output, labels) if labels is not None else 0
        return loss, output

    def training_step(self, batch, batch_idx):
        loss, _ = self(batch["input_ids"], batch["attention_mask"], batch["labels"])
        self.log("train_loss", loss, on_step=True, on_epoch=True, prog_bar=True)
        return loss

    def validation_step(self, batch, batch_idx):
        loss, preds = self(batch["input_ids"], batch["attention_mask"], batch["labels"])
        self._val_preds.append((preds >= self.threshold).int().cpu().numpy())
        self._val_labels.append(batch["labels"].int().cpu().numpy())
        self.log("val_loss", loss, on_step=False, on_epoch=True, prog_bar=True)

    def on_validation_epoch_end(self):
        preds  = np.concatenate(self._val_preds, 0)
        labels = np.concatenate(self._val_labels, 0)
        self.log("val_macro_f1", f1_score(labels, preds, average="macro", zero_division=0), prog_bar=True)
        self._val_preds.clear(); self._val_labels.clear()

    def configure_optimizers(self):
        optimizer = torch.optim.AdamW(self.parameters(), lr=2e-5, weight_decay=0.01)
        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=self.n_warmup_steps,
            num_training_steps=self.n_training_steps,
        )
        return [optimizer], [{"scheduler": scheduler, "interval": "step"}]


# ── 공개 API ──────────────────────────────────────────────────────

def run_finetune(
    train_tsv: str,
    val_tsv: str,
    test_tsv: str,
    run_name: str,
    output_dir: str,
    aug_jsonl: Optional[str] = None,   # 추가 증강 데이터 JSONL (None이면 원본만)
    epochs: int = 5,
    batch_size: int = 16,
    threshold: float = 0.3,
    seed: int = 42,
) -> dict:
    """
    KcELECTRA fine-tuning 실행 후 테스트셋 평가 결과 반환.

    반환:
        {
          "run_name": str,
          "f1_macro": float,
          "f1_micro": float,
          "per_label": {감정명: f1, ...},
          "model_path": str,
        }
    """
    set_seed(seed)
    run_dir = os.path.join(output_dir, run_name)
    os.makedirs(run_dir, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_source(),
        revision=None if LOCAL_MODEL_DIR.exists() else REVISION,
        local_files_only=True,
    )

    train_rows = _load_tsv(train_tsv)
    if aug_jsonl:
        aug_rows = _load_jsonl(aug_jsonl)
        train_rows = train_rows + aug_rows  # 원본 + 증강 병합
        print(f"  train: {len(_load_tsv(train_tsv)):,}(원본) + {len(aug_rows):,}(증강) = {len(train_rows):,}")
    else:
        print(f"  train: {len(train_rows):,}")

    train_ds = _KOTEDataset(train_rows, tokenizer, augment=True)   # token aug 적용
    val_ds   = _KOTEDataset(_load_tsv(val_tsv),  tokenizer, augment=False)
    test_ds  = _KOTEDataset(_load_tsv(test_tsv), tokenizer, augment=False)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,  num_workers=4, pin_memory=True)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False, num_workers=4, pin_memory=True)
    test_loader  = DataLoader(test_ds,  batch_size=batch_size, shuffle=False, num_workers=4, pin_memory=True)

    # 공식 KOTE 논문 스케줄 기준: total_steps = steps_per_epoch * 10, warmup = total // 5
    steps_per_epoch = len(train_loader)
    total_steps  = steps_per_epoch * 10
    warmup_steps = total_steps // 5

    model = _KOTEtagger(total_steps, warmup_steps, threshold=threshold)

    ckpt_cb = pl.callbacks.ModelCheckpoint(
        dirpath=os.path.join(run_dir, "ckpt"),
        filename="best",
        monitor="val_loss",
        mode="min",
        save_top_k=1,
    )
    early_stop_cb = pl.callbacks.EarlyStopping(monitor="val_loss", patience=3, mode="min")

    trainer = pl.Trainer(
        max_epochs=epochs,
        accelerator="gpu",
        devices=1,
        callbacks=[ckpt_cb, early_stop_cb],
        log_every_n_steps=50,
        deterministic=True,   # 재현성 보장 (cuDNN deterministic 모드)
        enable_progress_bar=True,
    )
    trainer.fit(model, train_loader, val_loader)

    # 최적 체크포인트 로드 후 테스트 평가
    best = _KOTEtagger.load_from_checkpoint(
        ckpt_cb.best_model_path,
        n_training_steps=total_steps,
        n_warmup_steps=warmup_steps,
        threshold=threshold,
    )
    model_path = os.path.join(run_dir, "model.bin")
    torch.save(best.state_dict(), model_path)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    best.to(device).eval()

    all_preds, all_labels = [], []
    with torch.no_grad():
        for batch in test_loader:
            _, logits = best(batch["input_ids"].to(device), batch["attention_mask"].to(device))
            all_preds.append((logits >= threshold).int().cpu().numpy())
            all_labels.append(batch["labels"].int().cpu().numpy())

    preds  = np.concatenate(all_preds,  0)
    labels = np.concatenate(all_labels, 0)

    f1_macro = float(f1_score(labels, preds, average="macro",  zero_division=0))
    f1_micro = float(f1_score(labels, preds, average="micro",  zero_division=0))
    per_cls  = f1_score(labels, preds, average=None, zero_division=0)
    per_label = {LABELS[i]: float(per_cls[i]) for i in range(NUM_LABELS)}

    result = {
        "run_name":  run_name,
        "seed":      seed,
        "epochs":    epochs,
        "threshold": threshold,
        "f1_macro":  f1_macro,
        "f1_micro":  f1_micro,
        "per_label": per_label,
        "model_path": os.path.relpath(model_path, PROJECT_ROOT),
        "ckpt_dir": os.path.relpath(os.path.join(run_dir, "ckpt"), PROJECT_ROOT),
        "aug_jsonl": os.path.relpath(aug_jsonl, PROJECT_ROOT) if aug_jsonl else None,
        "base_model_source": os.path.relpath(model_source(), PROJECT_ROOT) if LOCAL_MODEL_DIR.exists() else MODEL_NAME,
    }
    with open(os.path.join(run_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n[{run_name}] F1-Macro: {f1_macro:.4f}  F1-Micro: {f1_micro:.4f}")
    return result


def run_inference(
    model_path: str,
    texts: list[str],
    threshold: float = 0.3,
    batch_size: int = 32,
) -> list[list[str]]:
    """
    저장된 모델 가중치(.bin)로 텍스트 목록 추론.

    반환:
        각 텍스트에 대한 예측 레이블 목록 e.g. [["불평/불만", "짜증"], ...]
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_source(),
        revision=None if LOCAL_MODEL_DIR.exists() else REVISION,
        local_files_only=True,
    )

    # 더미 행 생성 (labels는 추론 시 사용 안 됨)
    rows = [{"text": t, "labels": []} for t in texts]
    ds  = _KOTEDataset(rows, tokenizer, augment=False)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=2)

    model = _KOTEtagger(n_training_steps=1, n_warmup_steps=0, threshold=threshold)
    state = torch.load(model_path, map_location=device)
    model.load_state_dict(state, strict=False)
    model.to(device).eval()

    all_preds = []
    with torch.no_grad():
        for batch in loader:
            _, logits = model(batch["input_ids"].to(device), batch["attention_mask"].to(device))
            bin_preds = (logits >= threshold).int().cpu().numpy()
            all_preds.append(bin_preds)

    preds = np.concatenate(all_preds, 0)
    return [
        [LABELS[i] for i in range(NUM_LABELS) if preds[j, i] == 1]
        for j in range(len(texts))
    ]
