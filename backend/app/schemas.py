from pydantic import BaseModel


class HeadlineItem(BaseModel):
    id: int
    headline: str
    url: str
    category: str
    publisher: str
    published_at: str
    emotions: dict[str, float]
    top_emotion: str | None = None
    attention_weights: list[dict] | None = None


class TrendPoint(BaseModel):
    date: str
    emotion: str
    count: int


class DistributionItem(BaseModel):
    emotion: str
    count: int
    ratio: float


class PredictRequest(BaseModel):
    headline: str


class PredictResponse(BaseModel):
    emotion_probs: dict[str, float]
    attention_weights: list[dict]
