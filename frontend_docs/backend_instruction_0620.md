# Backend 구현 지침 (CLAUDE.md — Backend)

> 프론트엔드용 CLAUDE.md와 별개의 파일. Claude Code에게 **이 파일만** 먼저 읽게 하고 작업 시작.
> 작업 범위: 크롤러 → DB → 추론 → FastAPI. 프론트는 건드리지 않음 (기존 `lib/api.js` 추상화 레이어가 mock→real 전환을 담당).

---

## 0. 전제 (Why — 이 결정들을 따르는 이유)

- 마감 D-1. 모든 결정은 "정확성 손실 없이 가장 빠른 길"을 기준으로 확정됨. 아래 결정을 임의로 바꾸지 말 것.
- 크롤링 소스: **네이버 뉴스검색 API 단일 사용** (RSS 사용 안 함). 이유: 언론사 식별이 `originallink` 파싱으로 자동 해결되고, 페이지네이션으로 백필 물량 확보가 빠름.
- 추론 트리거: **동기 배치**. 큐(Celery/Redis) 도입 금지. 이유: 트래픽 규모가 작고(수천 건 단위), 실시간성보다 정확성이 우선인 모니터링 시스템.
- DB: **SQLite**. 이유: 단일 서버, 동시 쓰기 부담 없음, 별도 인프라 불필요.

---

## 1. 디렉토리 구조

```
backend/
├── app/
│   ├── main.py                 # FastAPI 앱 엔트리포인트
│   ├── db.py                   # SQLite 연결 + 스키마 생성
│   ├── constants.py            # KOTE 44개 라벨 목록 (single source of truth)
│   ├── schemas.py               # Pydantic request/response 모델
│   ├── crawler/
│   │   ├── naver_api.py         # 네이버 검색 API 호출 wrapper
│   │   ├── publisher_map.py     # 도메인 → 언론사명 매핑
│   │   └── backfill.py          # CLI 백필 스크립트
│   ├── inference/
│   │   ├── model_loader.py      # KcELECTRA 모델 1회 로드 (싱글톤)
│   │   └── predict.py           # batch predict + attention 추출
│   ├── scheduler/
│   │   └── jobs.py              # APScheduler 등록 (최저 우선순위)
│   └── api/
│       ├── routes_predict.py
│       ├── routes_headlines.py
│       ├── routes_trends.py
│       └── routes_distribution.py
├── data/
│   └── news.db                  # SQLite 파일 (gitignore)
├── .env                          # NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, MODEL_PATH
└── requirements.txt
```

---

## 2. 구현 순서 (이 순서를 반드시 지킬 것 — 의존관계 있음)

| 순서 | 파일 | 완료 기준 |
|---|---|---|
| 1 | `constants.py` | KOTE 44개 라벨이 학습 데이터 라벨 순서와 정확히 일치 |
| 2 | `db.py` | `init_db()` 실행 시 두 테이블 생성 확인 |
| 3 | `crawler/publisher_map.py` | 도메인 4개 매핑 (조선/동아/한겨레/경향), 매핑 안 되면 "기타" |
| 4 | `crawler/naver_api.py` | 검색어 1개로 100건 호출 → JSON 정상 응답 확인 |
| 5 | `crawler/backfill.py` | 카테고리 4개 × 키워드 루프 → dedupe → DB insert, 실행 1회로 수천 건 적재 |
| 6 | `inference/model_loader.py`, `predict.py` | DB의 추론 안 된 헤드라인 전체에 대해 배치 predict 1회 성공 |
| 7 | `api/routes_*.py` 4개 | 각 엔드포인트 curl 테스트 통과 |
| 8 | `scheduler/jobs.py` | (시간 남으면) 신규 기사만 polling하는 잡 등록 |

8번은 우선순위 가장 낮음. 시간이 부족하면 스킵하고 보고서에 "구현은 완료, 상시 가동은 운영 환경 기준"으로 서술.

---

## 3. 핵심 결정 사항 (절대 바꾸지 말 것)

| 항목 | 결정 | 비고 |
|---|---|---|
| dedup 기준 | `url` UNIQUE 제약 + `INSERT OR IGNORE` | 동일 기사 중복 적재 방지 |
| emotion_probs 저장 형식 | JSON 문자열 (TEXT 컬럼) | SQLite는 array 타입 없음. `json.dumps`/`json.loads`로 직렬화 |
| label threshold | **0.2로 통일** | 기존 PPT 4.2/4.3에 0.2/0.3 불일치 있었음. 0.2로 확정. 코드 어디서도 0.3 쓰지 말 것 |
| published_at 형식 | ISO 8601 문자열 (`2026-06-20T13:00:00+09:00`) | timezone 누락하면 시계열 집계 깨짐 |
| API 키 | `.env`로만 관리 | 코드에 하드코딩 절대 금지 |

---

## 4. DB 스키마

```sql
CREATE TABLE IF NOT EXISTS headlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    headline TEXT NOT NULL,
    category TEXT NOT NULL,
    publisher TEXT NOT NULL,
    published_at TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS emotion_results (
    headline_id INTEGER PRIMARY KEY REFERENCES headlines(id),
    emotion_probs TEXT NOT NULL,      -- JSON: {"분노": 0.12, ...} 44 keys
    attention_weights TEXT,           -- JSON: [{"token": "北", "weight": 0.91}, ...]
    predicted_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. 크롤러 핵심 로직 (스켈레톤)

```python
# crawler/publisher_map.py
PUBLISHER_MAP = {
    "chosun.com": "조선일보",
    "donga.com": "동아일보",
    "hani.co.kr": "한겨레",
    "khan.co.kr": "경향신문",
}

def identify_publisher(originallink: str) -> str:
    for domain, name in PUBLISHER_MAP.items():
        if domain in originallink:
            return name
    return "기타"
```

```python
# crawler/naver_api.py
import os, requests

NAVER_URL = "https://openapi.naver.com/v1/search/news.json"

def search_news(query: str, start: int = 1, display: int = 100) -> list[dict]:
    headers = {
        "X-Naver-Client-Id": os.environ["NAVER_CLIENT_ID"],
        "X-Naver-Client-Secret": os.environ["NAVER_CLIENT_SECRET"],
    }
    params = {"query": query, "display": display, "start": start, "sort": "date"}
    resp = requests.get(NAVER_URL, headers=headers, params=params, timeout=5)
    resp.raise_for_status()
    return resp.json()["items"]
```

```python
# crawler/backfill.py (CLI 진입점)
CATEGORY_KEYWORDS = {
    "정치": ["정치", "국회", "대통령"],
    "경제": ["경제", "증시", "물가"],
    "사회": ["사회", "사건", "재판"],
    "문화": ["문화", "공연", "전시"],
}
# 카테고리별 키워드 루프 → search_news(query, start=1..901, step=100)
# → originallink로 publisher 식별 → headline 전처리(태그/특수문자 제거, 기존 spec 함수 재사용)
# → DB INSERT OR IGNORE
```

---

## 6. 추론 핵심 로직

```python
# inference/predict.py
import torch, json

def predict_batch(headlines: list[str], model, tokenizer, threshold: float = 0.2):
    inputs = tokenizer(headlines, padding=True, truncation=True, max_length=512, return_tensors="pt")
    with torch.no_grad():
        outputs = model.electra(**inputs, output_attentions=True)
        logits = model.classifier(model.dropout(outputs.last_hidden_state[:, 0, :]))
        probs = torch.sigmoid(logits)  # (batch, 44)

        last_attn = outputs.attentions[-1].mean(dim=1)  # (batch, seq_len, seq_len)
        cls_attn = last_attn[:, 0, :]                    # (batch, seq_len)

    results = []
    for i, h in enumerate(headlines):
        emotion_probs = {LABELS[j]: round(probs[i][j].item(), 4) for j in range(44)}
        tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"][i])
        attention = [{"token": t, "weight": round(w.item(), 4)} for t, w in zip(tokens, cls_attn[i])]
        results.append({"emotion_probs": json.dumps(emotion_probs, ensure_ascii=False),
                         "attention_weights": json.dumps(attention, ensure_ascii=False)})
    return results
```

`LABELS`는 `constants.py`에서 import — KOTE 학습 시 라벨 순서와 절대 어긋나면 안 됨 (가장 흔한 실수 지점).

---

## 7. 에러 처리 원칙

| 상황 | 처리 |
|---|---|
| 네이버 API 429/5xx | exponential backoff, 최대 3회 재시도 후 skip + 로그 |
| 모델 추론 중 특정 헤드라인 실패 (e.g. 토크나이즈 에러) | 해당 건만 skip, 배치 전체 중단 금지 |
| 잘못된 query 파라미터 (category 등) | Pydantic 자동 422 처리, 커스텀 에러 메시지 불필요 |
| DB url UNIQUE 충돌 | 정상 동작 (`INSERT OR IGNORE`로 무시), 에러 아님 |

---

## 8. API 스펙 (Request/Response 예시)

```http
GET /headlines?category=정치&start=2026-06-01&end=2026-06-20&limit=50
→ [{"headline": "...", "category": "정치", "publisher": "한겨레",
    "published_at": "2026-06-20T09:00:00+09:00",
    "emotions": {"분노": 0.81, "불안": 0.34, ...}}]

GET /trends?category=정치&emotions=분노,불안,슬픔&granularity=1d
→ [{"date": "2026-06-18", "emotion": "분노", "count": 12}, ...]

GET /distribution?category=정치&start=...&end=...
→ [{"emotion": "분노", "count": 120, "ratio": 0.18}, ...]

POST /predict   { "headline": "北 미사일 도발, 한반도 긴장 고조" }
→ { "emotion_probs": {...}, "attention_weights": [{"token": "도발", "weight": 0.91}, ...] }
```

응답 필드명은 프론트 mock 데이터 포맷과 **1:1 일치**해야 함 (`lib/api.js`에서 변환 로직 추가하지 않도록).

---

## 9. 완료 체크리스트

- [ ] `backfill.py` 1회 실행으로 헤드라인 1,000건 이상 적재
- [ ] 전체 헤드라인에 `emotion_probs` 44차원 모두 채워짐 (NULL 없음)
- [ ] 4개 엔드포인트 curl 테스트 통과
- [ ] 프론트 mock JSON 구조와 실제 API 응답 구조 비교해서 필드명 불일치 없음
- [ ] `.env` 파일이 `.gitignore`에 포함됨 (API 키 커밋 방지)