# news_db CSV export

`backend/data/news.db`에 저장된 뉴스 헤드라인 수집/전처리/감정 추론 결과를 테이블별 CSV로 내보낸 제출용 데이터다.

| CSV | 원본 테이블 | 설명 |
|---|---|---|
| `headlines.csv` | `headlines` | 수집 기사 제목, 카테고리, 언론사, 발행일, URL, 전처리 제목 |
| `emotion_results.csv` | `emotion_results` | headline_id별 KOTE 44-class 감정 확률 JSON, attention weights JSON, 추론 시각 |
| `crawler_meta.csv` | `crawler_meta` | crawler 실행 메타데이터 |

`emotion_results.headline_id`는 `headlines.id`와 연결된다. 원본 SQLite DB를 제출하지 않는 경우에도 이 세 CSV로 뉴스 데이터와 추론 결과를 확인할 수 있다.
