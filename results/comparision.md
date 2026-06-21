# 증강 조건 비교

baseline, Back Translation, card & SCUins는 epoch 10 기준으로 맞춰 재평가했다. `total_seed_gemini_aug`는 저장된 기존 참고 결과다.

| 조건 | F1-macro | Δ macro vs baseline_e10 | F1-micro | 죄책감 F1 | 근거 |
|---|---:|---:|---:|---:|---|
| baseline_e10 | 0.5587 | 0.0000 | 0.6530 | 0.0230 | epoch 10 metrics |
| total_seed_gemini_aug | 0.5617 | 0.0030 | 0.6481 | - | 기존 비교 JSON, epoch 10 재학습 아님 |
| back_translation_e10 | 0.5611 | 0.0024 | 0.6499 | 0.0980 | BT repaired 19,947, epoch 10 metrics |
| card_scuins_e10 | 0.5678 | 0.0091 | 0.6501 | 0.1714 | card & SCUins filtered 19,734, epoch 10 metrics |

## 해석 메모

- epoch 10 기준 F1-macro는 card & SCUins가 가장 높다.
- card & SCUins는 baseline 대비 macro F1을 개선했지만 micro F1은 baseline보다 낮아, 빈도 중심 전체 성능보다 라벨 균형 관점의 개선으로 해석한다.
- BT도 baseline 대비 macro F1은 소폭 개선하지만 card & SCUins보다 개선 폭이 작다.
- aug_gemini는 epoch 10으로 재학습한 결과가 아니므로 참고 비교군으로만 둔다.
