# 모델 결과 리포트

최종 test 지표는 각 `results/model/<run>/metrics.json`에서 읽었다.
baseline, Back Translation, card & SCUins는 원논문 설정과 맞추기 위해 epoch 10 기준 결과를 사용한다.
현재 제출본의 기본 run명(`baseline_th03`, `aug_bt_need19947_s42_repaired`, `aug_card_scuins_meanir`)은 epoch 10 결과를 담고 있다.

| run | F1-macro | F1-micro | 죄책감 F1 | threshold | epochs | model artifact |
|---|---:|---:|---:|---:|---:|---|
| aug_bt_need19947_s42_repaired | 0.5611 | 0.6499 | 0.0980 | 0.3 | 10 | `results/model/aug_bt_need19947_s42_repaired/model.bin` |
| aug_card_scuins_meanir | 0.5678 | 0.6501 | 0.1714 | 0.3 | 10 | `results/model/aug_card_scuins_meanir/model.bin` |
| baseline_th03 | 0.5587 | 0.6530 | 0.0230 | 0.3 | 10 | `results/model/baseline_th03/model.bin` |

## 기록된 Validation History

보존된 학습 로그에서 확인 가능한 학습 구간만 적었다. 초기 train 로그 파일은 0바이트라 값으로 복원하지 않았다.

| run | epoch | val_loss | val_macro_f1 | train_loss_epoch |
|---|---:|---:|---:|---:|
| baseline_th03 | 4 | 0.279 | 0.558 | 0.245 |
| baseline_th03 | 5 | 0.283 | 0.565 | 0.226 |
| baseline_th03 | 6 | 0.287 | 0.563 | 0.209 |
| baseline_th03 | 7 | 0.294 | 0.561 | 0.194 |
| baseline_th03 | 8 | 0.296 | 0.556 | 0.195 |
| baseline_th03 | 9 | 0.297 | 0.557 | 0.189 |
| aug_bt_need19947_s42_repaired | 4 | 0.280 | 0.565 | 0.296 |
| aug_bt_need19947_s42_repaired | 5 | 0.283 | 0.560 | 0.276 |
| aug_bt_need19947_s42_repaired | 6 | 0.289 | 0.562 | 0.256 |
| aug_bt_need19947_s42_repaired | 7 | 0.292 | 0.557 | 0.241 |
| aug_bt_need19947_s42_repaired | 8 | 0.295 | 0.557 | 0.241 |
| aug_bt_need19947_s42_repaired | 9 | 0.295 | 0.559 | 0.234 |
| aug_card_scuins_meanir | 3 | 0.282 | 0.566 | 0.181 |
| aug_card_scuins_meanir | 4 | 0.282 | 0.566 | 0.163 |
| aug_card_scuins_meanir | 5 | 0.292 | 0.564 | 0.147 |
| aug_card_scuins_meanir | 6 | 0.295 | 0.562 | 0.143 |
| aug_card_scuins_meanir | 7 | 0.302 | 0.557 | 0.133 |
| aug_card_scuins_meanir | 8 | 0.303 | 0.559 | 0.126 |
| aug_card_scuins_meanir | 9 | 0.305 | 0.558 | 0.121 |

## 최종 선택

- F1-macro 기준 최고 run: `aug_card_scuins_meanir`
- 백엔드에서 이 모델을 사용하려면 `MODEL_PATH=results/model/aug_card_scuins_meanir/ckpt`처럼 checkpoint 디렉터리를 지정한다.
