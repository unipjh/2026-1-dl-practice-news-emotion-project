# dl-prac-submission

KOTE 44-class multilabel emotion classification 실험과 뉴스 헤드라인 모니터링 앱을 한 루트에서 재현할 수 있도록 정리한 제출본이다.

## 제출물 확인

이 폴더는 소스코드 제출용 루트다. 보고서와 발표자료를 별도 파일로 제출해야 하는 경우에는 이 폴더와 함께 아래 문서를 근거 자료로 첨부한다.

- 보고서 근거: `results/report/model_report.md`, `results/report/filter_report.md`, `results/comparision.md`, `results/figure/`
- 실행 노트북: `main.ipynb`
- 학습/증강 소스: `scripts/`, `src/`
- 뉴스 모니터링 앱 소스: `backend/`, `app/`
- 사용 데이터: `data/kote/`, `data/aug_seed.csv`, `data/augmented/`, `data/news_db/*.csv`
- 모델 리소스(대용량 별도 제출 권장): `resources/kcelectra-base/`, `results/model/`

제출 전 구조 검증은 다음 명령으로 확인한다.

```bash
cd lab-w18/dl-prac-submission
python scripts/validate_artifacts.py --github      # GitHub 저장소 clone 기준
python scripts/validate_artifacts.py --data-only   # 전체 data/는 있고 모델만 별도 제출하는 경우
python scripts/validate_artifacts.py               # 모델 가중치까지 폴더에 포함한 경우
```

## 데이터 제출 안내

- `data/kote/`: KOTE 원본 split(train/val/test)과 라벨 불균형 분석 결과(`irlbl.json`, `scumble_scores.jsonl`)를 보존했다.
- `data/aug_seed.csv`: MeanIR 기준 minority 라벨 증강 필요량과 card/SCUins 기준 seed 선정 결과다.
- `data/augmented/`: 실제 학습 비교에 사용한 증강 데이터다. `total_seed_gemini_aug`, `bt`, `card_scuins` 조건별 JSONL을 포함한다.
- `data/news_db/`: `backend/data/news.db`에 있던 뉴스 헤드라인 수집/전처리/감정 추론 결과를 제출용 CSV로 내보낸 것이다. `headlines.csv`, `emotion_results.csv`, `crawler_meta.csv`와 `export_summary.json`을 포함한다.

`backend/data/news.db`는 로컬 앱 시연용 SQLite DB다. 데이터 제출은 `data/news_db/*.csv`로 충분하며, DB 파일 자체는 업로드 제한이 있으면 제외해도 된다.

## 모델 분리 제출 안내

현재 폴더 전체 용량은 모델 checkpoint와 base model weight 때문에 크다. LMS/메일 업로드 제한이 있으면 아래 대용량 모델 리소스는 Google Drive 등으로 별도 제출하고, 본 폴더에는 소스코드와 `data/` 산출물만 포함한다.

- base model: `resources/kcelectra-base/pytorch_model.bin`
- fine-tuned state dict: `results/model/*/model.bin`
- fine-tuned checkpoints: `results/model/*/ckpt/best.ckpt`, `results/model/*/ckpt/last.ckpt`

최종 앱 실행에는 F1-macro 기준 최고 모델인 `results/model/aug_card_scuins_meanir/ckpt/best.ckpt` 또는 해당 `model.bin`을 사용한다. `last.ckpt`는 중간/재개용 산출물이므로 용량 제한이 있으면 가장 먼저 별도 제출 또는 제외 대상으로 둔다.


## GitHub 업로드 안내

이 저장소에는 소스코드, 재현 노트북, 보고서/그림, 100MB 이하의 데이터 산출물을 올린다. GitHub 단일 파일 제한 때문에 `data/news_db/emotion_results.csv`(약 225MB), SQLite DB, 모델 가중치/checkpoint, 압축 데이터 파일은 `.gitignore`로 제외했다.

전체 데이터는 별도 제출 파일 `dl-prac-submission-data-utf8.zip`을 사용한다. 이 zip에는 `data/news_db/emotion_results.csv`까지 포함되어 있으므로, GitHub 저장소만 볼 때 누락되어 보이는 대용량 데이터는 해당 zip 또는 별도 제출 링크에서 확인한다.

권장 업로드 범위:

- GitHub: 소스코드, `main.ipynb`, `data/`의 100MB 이하 파일, `results/report/`, `results/figure/`, 실행/검증 문서
- 별도 제출/Drive: `dl-prac-submission-data-utf8.zip`, `data/news_db/emotion_results.csv`, `resources/kcelectra-base/pytorch_model.bin`, `results/model/*/model.bin`, `results/model/*/ckpt/*.ckpt`

## 빠른 재현

```bash
cd lab-w18/dl-prac-submission
cp .env_example .env          # GEMINI_API_KEY, NAVER_CLIENT_ID 등 필요한 키를 채워 넣는다
pip install -r requirements.txt
jupyter notebook main.ipynb
```

`main.ipynb`에서 `ROOT_DIR`를 이 폴더로 맞춘 뒤, 장시간 작업 플래그를 선택한다. 기본값은 기존 산출물을 로드하는 검증 흐름이다.

**기본 True (항상 실행)**
- `RUN_VALIDATE_ARTIFACTS`: 제출 산출물 구조 검증 (`scripts/validate_artifacts.py`)
- `RUN_REBUILD_REPORTS`: 결과 리포트 재생성 (`scripts/build_reports.py`)

**기본 False (필요할 때만 True)**
- `RUN_BASELINE_FINETUNE`: 원본 KOTE train만 사용한 baseline 학습 / False이면 `results/model/baseline_th03/metrics.json` 로드
- `RUN_AUG_GEMINI_GENERATION`: Gemini MeanIR 증강 재생성 (GEMINI_API_KEY 필요) / False이면 `data/augmented/total_seed_gemini_aug/` 기존 파일 사용
- `RUN_AUG_GEMINI_FINETUNE`: Gemini 증강 fine-tuning 실행 / False이면 `results/report/total_seed_gemini_aug_results_comparison.json`의 기존 참고 비교 결과를 사용
- `RUN_BT_GENERATION`, `RUN_BT_REPAIR`, `RUN_BT_FINETUNE`: Back Translation 생성/보정/학습
- `RUN_CARD_SCUINS_GENERATION`, `RUN_CARD_SCUINS_FILTER`, `RUN_CARD_SCUINS_FINETUNE`: card & SCUins 생성/필터/학습 (생성에 GEMINI_API_KEY 필요)
- `RUN_NEWS_RSS_FETCH`, `RUN_NEWS_NAVER_FETCH`: 백엔드 crawler 모듈을 통한 뉴스 수집 (Naver API에 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 필요)
- `RUN_NEWS_DB_INSERT`, `RUN_NEWS_INFERENCE`: 수집 뉴스의 SQLite 저장 및 로컬 ckpt 기반 감정 추론 저장

## 구조

```text
lab-w18/dl-prac-submission/
├── main.ipynb
├── .env_example            # API 키 템플릿 (cp .env_example .env 후 값 입력)
├── data/
│   ├── kote/
│   ├── kote_intro.md
│   ├── aug_seed.csv
│   ├── aug_strategy.md
│   ├── augmented/
│   └── news_db/              # backend SQLite DB export CSV
├── scripts/
├── src/
├── app/
├── frontend_docs/
├── backend/
├── resources/kcelectra-base/
├── results/
│   ├── model/
│   ├── report/
│   ├── figure/
│   └── comparision.md
├── requirements.txt
└── README.md
```

## 현재 반영된 실제 결과

- `baseline_th03`: `results/model/baseline_th03/metrics.json`
- `aug_bt_need19947_s42_repaired`: `results/model/aug_bt_need19947_s42_repaired/metrics.json`
- `aug_card_scuins_meanir`: `results/model/aug_card_scuins_meanir/metrics.json`
- `total_seed_gemini_aug`: `results/report/total_seed_gemini_aug_results_comparison.json`에 저장된 참고 비교 결과 사용

최종 비교는 `results/comparision.md`에 있고, 모델별 F1-macro/F1-micro/죄책감 F1 및 기록된 학습 구간의 epoch별 `val_loss`는 `results/report/model_report.md`와 `results/report/training_history.csv`에 있다.

## 모델 리소스

분류 모델 학습과 백엔드 추론은 제출본 안의 로컬 리소스를 우선 사용한다.

- base tokenizer/config/weights: `resources/kcelectra-base/`
- fine-tuned checkpoints: `results/model/<run>/ckpt/`
- exported state dict: `results/model/<run>/model.bin`

새 환경에서 Hugging Face 다운로드에 의존하지 않도록 `src/kote_trainer.py`와 `backend/app/inference/model_loader.py`는 `resources/kcelectra-base/`를 먼저 찾는다.

## 백엔드 연결

최종 F1-macro 기준 모델은 `aug_card_scuins_meanir`이다.

```bash
cd lab-w18/dl-prac-submission/backend
MODEL_PATH=../results/model/aug_card_scuins_meanir/ckpt uvicorn app.main:app --reload
```

관련 모듈:

- `backend/app/inference/model_loader.py`
- `backend/app/inference/predict.py`
- `backend/app/crawler/rss_crawler.py`
- `backend/app/crawler/naver_api.py`
- `backend/app/db.py`

`main.ipynb`의 뉴스 수집 섹션은 위 백엔드 모듈을 직접 import해서 RSS/Naver API 수집, `backend/data/news.db` 저장, `emotion_results` 추론 저장 흐름을 소량으로 점검한다. Naver API 테스트에는 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 환경변수가 필요하다.

프론트엔드는 별도 Node 환경에서 실행한다.

```bash
cd lab-w18/dl-prac-submission/app
npm install
npm run dev
```
