import json

from fastapi import APIRouter

from app.inference.model_loader import get_model
from app.inference.predict import predict_batch
from app.schemas import PredictRequest, PredictResponse

router = APIRouter()


@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    model, tokenizer = get_model()
    results = predict_batch([req.headline], model, tokenizer)
    r = results[0]
    return PredictResponse(
        emotion_probs=json.loads(r["emotion_probs"]),
        attention_weights=json.loads(r["attention_weights"]),
    )
