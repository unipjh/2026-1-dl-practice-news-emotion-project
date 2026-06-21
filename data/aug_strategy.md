# 증강 전략 요약

이 제출본은 MeanIR 기준 증강 필요량을 유지하면서, card/SCUins 기반 seed 선정 결과를 재현 가능한 CSV로 고정한다.

## 실제 사용한 조건

- `total_seed_gemini_aug`: 기존 MeanIR Gemini paraphrase 산출물 사용
- `back_translation`: ko->en->ko 역번역 후 repair 스크립트의 기본 품질 검사를 통과한 산출물 사용
- `card_scuins`: `card <= 하위 30% cutoff(=6)` 후보를 우선하고, 라벨별 SCUins 오름차순으로 seed를 선택한 1:1 paraphrase 산출물 사용
- `card_scuins` 품질 처리: 최소 토큰/한글 수 기본 품질 조건과 exact dedup만 적용

## 산출물 수

- total_seed_gemini_aug: 19,947
- back_translation repaired: 19,947
- card_scuins filtered: 19,734
- aug_seed.csv rows: 19,947

## card/SCUins Seed 라벨별 수

| 라벨 | seed rows | MeanIR need |
|---|---:|---:|
| 죄책감 | 3,609 | 3,609 |
| 공포/무서움 | 3,113 | 3,113 |
| 패배/자기혐오 | 2,726 | 2,726 |
| 서러움 | 2,276 | 2,276 |
| 부끄러움 | 1,978 | 1,978 |
| 귀찮음 | 1,879 | 1,879 |
| 비장함 | 955 | 955 |
| 절망 | 655 | 655 |
| 재미없음 | 616 | 616 |
| 힘듦/지침 | 538 | 538 |
| 편안/쾌적 | 536 | 536 |
| 존경 | 453 | 453 |
| 역겨움/징그러움 | 443 | 443 |
| 슬픔 | 170 | 170 |

## card/SCUins missing fill report

- seed rows: 19,947
- final raw rows: 19,947
- missing before fill: 20
- added: 20
- failed: 0
