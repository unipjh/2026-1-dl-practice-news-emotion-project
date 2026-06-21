from fastapi import APIRouter

from app.scheduler.jobs import get_last_crawled_at

router = APIRouter()


@router.get("/crawler/status")
def crawler_status():
    return {"last_crawled_at": get_last_crawled_at()}
