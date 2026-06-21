# 뉴스 헤드라인 감정 모니터링 프론트엔드

KOTE 44-class 감정 추론 결과를 뉴스 헤드라인 단위로 탐색하는 React/Vite 앱이다. 백엔드 API(`../backend`)가 실행 중이면 실제 SQLite DB의 헤드라인, 감정 분포, 추세 데이터를 조회한다.

## 실행

```bash
cd lab-w18/dl-prac-submission/app
npm install
npm run dev
```

기본 API 주소는 `src/lib/api.js`의 `API_BASE`를 따른다. 로컬 FastAPI 서버를 함께 실행하는 경우:

```bash
cd lab-w18/dl-prac-submission/backend
MODEL_PATH=../results/model/aug_card_scuins_meanir/ckpt uvicorn app.main:app --reload
```

## 주요 화면

- 헤드라인 목록 및 상세 감정 확률
- 카테고리/언론사/기간/감정 필터
- 감정 분포 막대그래프
- 기간별 감정 추세 모달

## 검증

```bash
npm run lint
npm run build
```
