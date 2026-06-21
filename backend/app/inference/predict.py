import json
import os
import time
from pathlib import Path

import torch
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from app.constants import LABELS
from app.db import get_conn
from app.inference.model_loader import get_model
from app.text_preprocess import preprocess_headline

THRESHOLD = 0.2
BATCH_SIZE = 32


def predict_batch(headlines: list[str], model, tokenizer) -> list[dict]:
    headlines = [preprocess_headline(h) for h in headlines]
    inputs = tokenizer(
        headlines,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt",
    )
    with torch.no_grad():
        logits, attentions = model(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            output_attentions=True,
        )
        probs = torch.sigmoid(logits)

        # CLS-token attention from last layer, averaged over heads
        last_attn = attentions[-1].mean(dim=1)  # (batch, seq_len, seq_len)
        cls_attn = last_attn[:, 0, :]           # (batch, seq_len)

    results = []
    for i in range(len(headlines)):
        emotion_probs = {LABELS[j]: round(probs[i][j].item(), 4) for j in range(len(LABELS))}
        tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"][i])
        attention = [
            {"token": t, "weight": round(w.item(), 4)}
            for t, w in zip(tokens, cls_attn[i])
        ]
        results.append({
            "emotion_probs": json.dumps(emotion_probs, ensure_ascii=False),
            "attention_weights": json.dumps(attention, ensure_ascii=False),
        })
    return results


def update_attention_only(batch_size: int = BATCH_SIZE):
    """emotion_probs는 유지하고 attention_weights만 재계산한다."""
    model, tokenizer = get_model()

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT h.id, COALESCE(h.preprocessed_headline, h.headline) AS text "
            "FROM headlines h "
            "JOIN emotion_results e ON h.id = e.headline_id"
        ).fetchall()

    if not rows:
        print("[attention] no rows to update")
        return

    print(f"[attention] updating {len(rows)} rows in batches of {batch_size}")
    ids = [r["id"] for r in rows]
    texts = [r["text"] for r in rows]

    for offset in range(0, len(ids), batch_size):
        batch_ids = ids[offset: offset + batch_size]
        batch_texts = texts[offset: offset + batch_size]
        try:
            results = predict_batch(batch_texts, model, tokenizer)
        except Exception as e:
            print(f"[attention] batch error at offset {offset}: {e}")
            results = [None] * len(batch_ids)

        rows_to_update = [
            (r["attention_weights"], hid)
            for hid, r in zip(batch_ids, results)
            if r is not None
        ]
        for attempt in range(5):
            try:
                with get_conn() as conn:
                    conn.executemany(
                        "UPDATE emotion_results SET attention_weights = ? WHERE headline_id = ?",
                        rows_to_update,
                    )
                break
            except Exception as db_err:
                if attempt < 4:
                    import time; time.sleep(2 ** attempt)
                else:
                    print(f"[attention] DB write failed after 5 attempts: {db_err}")

        done = min(offset + batch_size, len(ids))
        print(f"[attention] {done}/{len(ids)} done")

    print("[attention] all done")


def run_all(batch_size: int = BATCH_SIZE):
    """DB에서 추론 안 된 헤드라인 전체에 배치 추론."""
    model, tokenizer = get_model()

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT h.id, COALESCE(h.preprocessed_headline, h.headline) AS headline "
            "FROM headlines h "
            "LEFT JOIN emotion_results e ON h.id = e.headline_id "
            "WHERE e.headline_id IS NULL"
        ).fetchall()

    if not rows:
        print("[predict] no pending headlines")
        return

    print(f"[predict] processing {len(rows)} headlines in batches of {batch_size}")
    ids = [r["id"] for r in rows]
    texts = [r["headline"] for r in rows]

    for offset in range(0, len(ids), batch_size):
        batch_ids = ids[offset: offset + batch_size]
        batch_texts = texts[offset: offset + batch_size]
        try:
            results = predict_batch(batch_texts, model, tokenizer)
        except Exception as e:
            print(f"[predict] batch error at offset {offset}: {e}")
            results = []
            for text in batch_texts:
                try:
                    r = predict_batch([text], model, tokenizer)
                    results.append(r[0])
                except Exception as e2:
                    print(f"[predict] skip headline: {e2}")
                    results.append(None)

        rows_to_insert = [
            (hid, result["emotion_probs"], result["attention_weights"])
            for hid, result in zip(batch_ids, results)
            if result is not None
        ]
        for attempt in range(5):
            try:
                with get_conn() as conn:
                    conn.executemany(
                        "INSERT OR IGNORE INTO emotion_results "
                        "(headline_id, emotion_probs, attention_weights) VALUES (?, ?, ?)",
                        rows_to_insert,
                    )
                break
            except Exception as db_err:
                if attempt < 4:
                    time.sleep(2 ** attempt)
                else:
                    print(f"[predict] DB write failed after 5 attempts: {db_err}")

        done = min(offset + batch_size, len(ids))
        print(f"[predict] {done}/{len(ids)} done")

    print("[predict] all done")
