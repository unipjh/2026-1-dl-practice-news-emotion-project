import os
import time
import requests

NAVER_URL = "https://openapi.naver.com/v1/search/news.json"
_MAX_RETRIES = 3


def search_news(query: str, start: int = 1, display: int = 100) -> list[dict]:
    headers = {
        "X-Naver-Client-Id": os.environ["NAVER_CLIENT_ID"],
        "X-Naver-Client-Secret": os.environ["NAVER_CLIENT_SECRET"],
    }
    params = {"query": query, "display": display, "start": start, "sort": "date"}

    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.get(NAVER_URL, headers=headers, params=params, timeout=5)
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = 2 ** attempt
                print(f"[naver_api] HTTP {resp.status_code}, retry in {wait}s (attempt {attempt+1})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json().get("items", [])
        except requests.RequestException as e:
            if attempt < _MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"[naver_api] Failed after {_MAX_RETRIES} attempts: {e}")
    return []
