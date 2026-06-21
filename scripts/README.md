# scripts

`main.ipynb`가 호출하는 장시간 처리와 검증 스크립트만 둔다.

| script | 역할 |
|---|---|
| `validate_artifacts.py` | 제출 루트의 필수 파일, 데이터 산출물, 로컬 모델 리소스, metrics 경로를 검증 (`--data-only` 지원) |
| `build_reports.py` | `data/*.md`, `results/report/model_report.md`, `results/comparision.md` 재생성 |
| `export_news_db_csv.py` | `backend/data/news.db`의 뉴스/추론 테이블을 `data/news_db/*.csv`로 export |
| `finetune.py` | KOTE baseline 또는 증강 조건 fine-tuning 실행 |
| `generate_total_seed_gemini_meanir.py` | MeanIR Gemini 증강 생성 후 학습 입력 JSONL 저장 |
| `generate_back_translation.py` | Back Translation raw 생성 |
| `repair_back_translation.py` | Back Translation raw 보정 및 report 저장 |
| `generate_card_scuins.py` | `data/aug_seed.csv` 기반 card & SCUins Gemini raw 생성 |
| `fill_card_scuins.py` | raw 생성 누락분 보충 |
| `filter_card_scuins.py` | card & SCUins raw에 최소 길이/한글 수와 exact dedup 적용 |
| `build_aug_seed.py` | KOTE IRLbl/SCUins 기반 `data/aug_seed.csv` 재작성 |
