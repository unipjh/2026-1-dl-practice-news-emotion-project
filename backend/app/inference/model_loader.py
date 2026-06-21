import os
import sys
import glob
from pathlib import Path

import torch
import torch.nn as nn
from transformers import ElectraModel, AutoTokenizer

from app.constants import NUM_LABELS

MODEL_NAME = "beomi/KcELECTRA-base"
REVISION = "v2021"
DROPOUT = 0.1

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOCAL_MODEL_DIR = PROJECT_ROOT / "resources" / "kcelectra-base"


def _model_source() -> str:
    if LOCAL_MODEL_DIR.exists():
        return str(LOCAL_MODEL_DIR)
    return MODEL_NAME


def _revision():
    return None if LOCAL_MODEL_DIR.exists() else REVISION


def _resolve_model_dir(value: str) -> str:
    path = Path(value)
    candidates = [path]
    if not path.is_absolute():
        candidates = [PROJECT_ROOT / path, Path.cwd() / path, PROJECT_ROOT / "backend" / path]
    for cand in candidates:
        if cand.exists():
            return str(cand.resolve())
    return str(candidates[0].resolve())


_model = None
_tokenizer = None


class KcELECTRAForMultiLabel(nn.Module):
    def __init__(self):
        super().__init__()
        self.electra = ElectraModel.from_pretrained(
            _model_source(), revision=_revision(), local_files_only=True, use_safetensors=False,
            attn_implementation="eager",
        )
        self.dropout = nn.Dropout(DROPOUT)
        self.classifier = nn.Linear(self.electra.config.hidden_size, NUM_LABELS)

    def forward(self, input_ids, attention_mask, output_attentions=False):
        out = self.electra(
            input_ids=input_ids,
            attention_mask=attention_mask,
            output_attentions=output_attentions,
        )
        cls = self.dropout(out.last_hidden_state[:, 0, :])
        logits = self.classifier(cls)
        return logits, out.attentions


def _find_ckpt(model_dir: str) -> str:
    pattern = os.path.join(model_dir, "*.ckpt")
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"No .ckpt file found in {model_dir}")
    return sorted(files)[-1]


def get_model():
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer

    model_path = os.environ.get("MODEL_PATH", "")
    if not model_path:
        raise ValueError("MODEL_PATH not set in environment")

    model_path = _resolve_model_dir(model_path)
    ckpt_path = _find_ckpt(model_path)
    print(f"[model_loader] loading checkpoint: {ckpt_path}")

    ckpt = torch.load(ckpt_path, map_location="cpu")
    state = ckpt.get("state_dict", ckpt)
    # keys are already electra.*/dropout.*/classifier.* — load directly
    model = KcELECTRAForMultiLabel()
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing:
        print(f"[model_loader] missing keys ({len(missing)}): {missing[:5]}")
    if unexpected:
        print(f"[model_loader] unexpected keys ({len(unexpected)}): {unexpected[:5]}")

    model.eval()
    _model = model

    _tokenizer = AutoTokenizer.from_pretrained(
        _model_source(), revision=_revision(), local_files_only=True,
    )
    print("[model_loader] model ready")
    return _model, _tokenizer
