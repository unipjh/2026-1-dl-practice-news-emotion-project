import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.inference.model_loader import get_model
from app.scheduler.jobs import start_scheduler
from app.api.routes_headlines import router as headlines_router
from app.api.routes_predict import router as predict_router
from app.api.routes_crawler import router as crawler_router

app = FastAPI(title="뉴스 감정 분류 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()
    get_model()
    start_scheduler()


app.include_router(headlines_router)
app.include_router(predict_router)
app.include_router(crawler_router)


@app.get("/health")
def health():
    return {"status": "ok"}
