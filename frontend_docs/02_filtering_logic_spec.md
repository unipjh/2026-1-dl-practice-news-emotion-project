# Filtering & Display Logic Spec
# 뉴스 헤드라인 감정 분류 모니터링 대시보드

> Claude Code 참조용 문서 2/3 — 프론트엔드 필터링 및 데이터 표시 로직

---

## 1. 데이터 구조

### 단일 헤드라인 레코드

```typescript
interface HeadlineRecord {
  id: string;
  headline: string;
  category: '정치' | '경제' | '사회' | '문화';
  publisher: string;           // 예: "조선일보", "한겨레"
  published_at: string;        // ISO 8601
  emotions: EmotionScore[];
  tokens: string[];
  attention_weights: number[]; // tokens와 길이 동일
}

interface EmotionScore {
  label: string;               // KOTE 44개 감정 레이블
  prob: number;                // 0.0 ~ 1.0
}
```

### 집계 레코드 (API 응답 또는 프론트 집계)

```typescript
interface AggregatedRecord {
  bucket: string;              // 시간 버킷 (ISO 8601 시작 시간)
  group_key: string;           // 예: "조선일보_정치", "한겨레_전체"
  emotion_label: string;
  count: number;               // 해당 버킷+그룹+감정 헤드라인 수
}
```

---

## 2. 감정군 분류 (KOTE 44개)

감정군 필터 버튼(전체/긍정/중립/부정)에 사용되는 분류표

### 긍정 감정 (22개)

```
감사하는, 감동/감탄, 기쁨, 뿌듯한, 설레는, 신기함/관심, 신뢰/믿음,
안심/안도, 즐거움/신남, 편안/쾌적, 홀가분, 흥분,
사랑/좋아함, 재미있는, 행복한, 희망찬, 기대감, 만족스러운,
자랑스러운, 자신감, 대견한, 기분좋음
```

### 중립 감정 (3개)

```
놀람/충격, 의아함/황당, 무감정/무덤덤
```

> 중립 감정은 3개로 매우 적음. "전체" 선택 시 항상 포함되며,
> "중립" 단독 선택 시 3개 감정만 Bar Chart에 표시됨.

### 부정 감정 (19개)

```
분노/화남, 짜증, 혐오/역겨움, 불안/걱정, 공포/무서움, 슬픔, 외로움/고독,
부끄러움/창피, 죄책감, 후회, 실망, 배신감, 비교/자격지심, 부러움/질투,
답답함, 억울함, 피곤함/지침, 상처/아픔, 절망
```

> 실제 KOTE 레이블 목록 기준으로 구현 전 재검증 필요.
> 위 분류는 의미 기반 초안이며, 모델 학습 완료 후 레이블 목록 확정.

---

## 3. dt(시간 범위) 로직

```typescript
type DtMode = '6h' | '1d' | '1w';

function getTimeRange(mode: DtMode): { start: Date; end: Date } {
  const end = new Date();
  const start = new Date();
  if (mode === '6h')  start.setHours(end.getHours() - 6);
  if (mode === '1d')  start.setDate(end.getDate() - 1);
  if (mode === '1w')  start.setDate(end.getDate() - 7);
  return { start, end };
}
```

**버킷 단위**

| dt | 버킷 단위 | 시계열 X축 레이블 |
|----|-----------|------------------|
| 6h | 30분 | "14:00", "14:30", ... |
| 1d | 2시간 | "00:00", "02:00", ... |
| 1w | 1일 | "1/9", "1/10", ... |

---

## 4. 필터 패널 선택 로직

### 상태 구조

```typescript
interface FilterState {
  publishers: string[];   // 선택된 언론사 목록
  categories: string[];   // 선택된 카테고리 목록
}

// 총 선택 개수 = publishers.length + categories.length ≤ 4
```

### 비교 그룹(CompareGroup) 생성 로직

선택 완료 후 "적용" 클릭 시 또는 실시간으로 계산

```typescript
interface CompareGroup {
  key: string;        // 예: "조선일보_정치"
  label: string;      // 표시용 레이블 (동일)
  publisher?: string;
  category?: string;
}

function buildCompareGroups(filter: FilterState): CompareGroup[] {
  const { publishers: P, categories: C } = filter;

  // 아무것도 선택 안 함 → 전체 단일 그룹
  if (P.length === 0 && C.length === 0) {
    return [{ key: '전체', label: '전체' }];
  }

  // 카테고리만 선택
  if (P.length === 0 && C.length > 0) {
    return C.map(c => ({ key: c, label: c, category: c }));
  }

  // 언론사만 선택
  if (P.length > 0 && C.length === 0) {
    return P.map(p => ({ key: p, label: p, publisher: p }));
  }

  // 언론사 + 카테고리 교차
  // P × C 조합 생성, 최대 4개 항목이므로 조합 수는 P*C개
  const groups: CompareGroup[] = [];
  for (const p of P) {
    for (const c of C) {
      groups.push({ key: `${p}_${c}`, label: `${p}_${c}`, publisher: p, category: c });
    }
  }
  return groups;
}
```

### 교차 조합 예시

| 선택 항목 | 생성되는 비교 그룹 |
|-----------|-------------------|
| (없음) | 전체 |
| 정치 | 정치 |
| 정치, 경제 | 정치 / 경제 |
| 조선일보, 한겨레 | 조선일보 / 한겨레 |
| 조선일보, 한겨레, 정치 | 조선일보_정치 / 한겨레_정치 |
| 조선일보, 한겨레, 정치, 경제 | 조선일보_정치 / 조선일보_경제 / 한겨레_정치 / 한겨레_경제 |

> **주의**: 교차 시 순수 언론사 단독(조선일보 전체)은 그룹에서 제외되고
> 교차 결과만 그룹으로 생성됨.

### 선택 제한 처리

```typescript
function canSelect(current: FilterState): boolean {
  return current.publishers.length + current.categories.length < 4;
}
// 4개 초과 시도 시 토스트: "최대 4개까지 선택 가능합니다"
```

---

## 5. Bar Chart 데이터 구성

### 표시 감정 결정

```
표시 감정 = (감정군 필터 적용된 레이블 목록)
  → 전체: 44개
  → 긍정: 22개
  → 중립: 3개
  → 부정: 19개
```

Count 기준으로 내림차순 정렬 후 상위 N개만 표시 (기본 N=20)

### 전체 평균 오버레이

```typescript
// 필터 그룹 없을 때는 DB 전체 기준
// 필터 그룹 있을 때도 전체 평균은 항상 전체 데이터 기준 고정
function getGlobalAverage(emotion: string, dt: DtMode): number {
  // 해당 dt 기간 내 전체 헤드라인에서 emotion count / total headlines
}
```

### 감정 선택 (시계열 트리거) 상태

```typescript
interface ChartSelectionState {
  selectedEmotions: string[];  // 최대 3개
  timeseriesOpen: boolean;
}

function toggleEmotionSelect(
  state: ChartSelectionState, 
  emotion: string
): ChartSelectionState {
  if (state.selectedEmotions.includes(emotion)) {
    // 이미 선택됨 → 해제
    return { ...state, selectedEmotions: state.selectedEmotions.filter(e => e !== emotion) };
  }
  if (state.selectedEmotions.length >= 3) {
    // 3개 초과 → 무시 (토스트: "최대 3개까지 선택 가능합니다")
    return state;
  }
  return { ...state, selectedEmotions: [...state.selectedEmotions, emotion] };
}
```

---

## 6. 시계열 팝업 데이터 구성

### 구조

```
팝업 입력:
  - selectedEmotions: string[]   (1~3개)
  - compareGroups: CompareGroup[]
  - dt: DtMode

출력 (subplot × emotion):
  감정 1 → { group1: [count by bucket], group2: [...], ... }
  감정 2 → { ... }
  감정 3 → { ... }
```

### subplot 레이아웃

- 선택 감정 1개: 단일 Line Chart (전체 높이)
- 선택 감정 2개: 2행 vertical stack
- 선택 감정 3개: 3행 vertical stack

각 subplot은 **동일한 X축 범위** 공유 (기간 동기화)  
Y축은 subplot별 독립 스케일 (감정마다 절대 count가 다르므로)

---

## 7. 헤드라인 리스트 필터링

```typescript
// 현재 활성화된 모든 필터를 반영하여 헤드라인 조회
interface HeadlineListQuery {
  dt: DtMode;
  sentimentGroup?: 'positive' | 'neutral' | 'negative';  // 감정군 필터
  compareGroups: CompareGroup[];  // 빈 배열이면 전체
  sortBy: 'latest' | 'most_negative' | 'most_positive';
  page: number;
  pageSize: 20;
}
```

감정군 필터가 적용된 경우: 해당 감정군에 속하는 감정이 1개 이상 confidence > 0.5인 헤드라인만 표시

---

## 8. Attention 하이라이팅 로직

```typescript
function getHighlightStyle(weight: number, maxWeight: number): string {
  const normalized = weight / maxWeight;  // 0~1
  if (normalized < 0.3) return '';        // 하이라이트 없음
  if (normalized < 0.6) return 'bg-blue-100';
  if (normalized < 0.85) return 'bg-blue-300';
  return 'bg-blue-500 text-white';
}

// Evidence Tokens: attention_weights 상위 3개 인덱스의 token 반환
function getEvidenceTokens(tokens: string[], weights: number[]): string[] {
  return weights
    .map((w, i) => ({ w, token: tokens[i] }))
    .sort((a, b) => b.w - a.w)
    .slice(0, 3)
    .map(x => x.token);
}
```
