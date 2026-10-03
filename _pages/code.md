---
title: "코드"
permalink: /code/
description: "퀀트 노트 글의 결과를 낸 파이썬 스크립트 모음. 글별 스크립트, 함께 받아야 하는 파일, 실행에 필요한 것을 정리했습니다."
---

글에 실린 표와 차트는 아래 파이썬 스크립트로 만들었습니다. 파일 이름을 누르면 내려받을 수 있습니다. 결과를 직접 다시 돌려 보거나, 기간과 가정을 바꿔 보는 데 쓰시면 됩니다.

## 실행하기 전에

- 파이썬 3와 `pandas`, `numpy`, `matplotlib`이 필요합니다. 한국 데이터를 쓰는 스크립트는 `finance-datareader`나 `pykrx`도 필요합니다.
- 한 스크립트가 다른 스크립트의 함수를 가져다 쓰는 경우가 있습니다. 표의 "함께 받을 파일"을 **같은 폴더**에 두고 실행하세요.
- 결과는 스크립트가 있는 폴더 아래 `output/`에 저장됩니다.
- 대부분 `--synthetic` 옵션을 주면 실제 데이터 대신 난수 데이터로 동작만 확인할 수 있습니다.
- 한국거래소(KRX) 종목 데이터를 받는 스크립트는 [KRX 정보데이터시스템](http://data.krx.co.kr) 계정이 필요합니다. 계정 정보는 코드에 적지 말고 환경 변수 `KRX_ID`, `KRX_PW`로 넘깁니다. 받은 KRX 데이터 파일은 이 사이트에서 다시 배포하지 않습니다.

## 퀀트 투자 입문

| 글 | 스크립트 | 함께 받을 파일 |
|---|---|---|
| [첫 백테스트](/posts/first-backtest-absolute-momentum/) ~ [위험 지표](/posts/risk-metrics-explained/) | [run_series_backtests.py](/assets/code/run_series_backtests.py) | |
| [자산 배분 기초](/posts/asset-allocation-basics/) | [asset_allocation_basics.py](/assets/code/asset_allocation_basics.py) | |
| [리밸런싱](/posts/does-rebalancing-work/) | [rebalancing_test.py](/assets/code/rebalancing_test.py) | asset_allocation_basics.py |
| [상관관계와 분산투자](/posts/correlation-and-diversification-math/) | [correlation_math.py](/assets/code/correlation_math.py) | asset_allocation_basics.py |
| [밸류 팩터](/posts/value-factor/) | [value_factor.py](/assets/code/value_factor.py) | |
| [퀄리티 팩터](/posts/quality-factor/) | [quality_factor.py](/assets/code/quality_factor.py) | |
| [저변동성 팩터](/posts/low-volatility-factor/) | [low_volatility_factor.py](/assets/code/low_volatility_factor.py) | quality_factor.py |
| [사이즈 팩터](/posts/size-factor/) | [size_factor.py](/assets/code/size_factor.py) | value_factor.py, quality_factor.py |
| [멀티팩터](/posts/multifactor-portfolio/) | [multifactor.py](/assets/code/multifactor.py) | quality_factor.py |
| [듀얼 모멘텀](/posts/dual-momentum/) | [dual_momentum.py](/assets/code/dual_momentum.py) | asset_allocation_basics.py, value_factor.py |
| [올웨더 포트폴리오](/posts/all-weather-portfolio/) | [all_weather.py](/assets/code/all_weather.py) | asset_allocation_basics.py, value_factor.py |

## 퀀트 실전

| 글 | 스크립트 | 함께 받을 파일 |
|---|---|---|
| [pykrx로 재무 데이터 받기](/posts/pykrx-fundamentals/) | [krx_snapshot.py](/assets/code/krx_snapshot.py), [krx_fetch_monthly.py](/assets/code/krx_fetch_monthly.py), [krx_fetch_returns.py](/assets/code/krx_fetch_returns.py) | |
| [종목 스크리닝](/posts/stock-screener/) | [screener.py](/assets/code/screener.py) | krx_snapshot.py |
| [워크포워드 검증](/posts/walk-forward-validation/) | [walkforward.py](/assets/code/walkforward.py) | krx_snapshot.py, screener.py |
| [몬테카를로](/posts/monte-carlo-validation/) | [montecarlo.py](/assets/code/montecarlo.py) | walkforward.py, krx_snapshot.py, screener.py |
| [평균-분산 최적화](/posts/mean-variance-optimization/) | [mean_variance.py](/assets/code/mean_variance.py) | all_weather.py, asset_allocation_basics.py, value_factor.py |
| [리스크 패리티](/posts/risk-parity/) | [risk_parity.py](/assets/code/risk_parity.py) | all_weather.py, asset_allocation_basics.py, value_factor.py |
| [켈리 공식](/posts/kelly-criterion/) | [kelly.py](/assets/code/kelly.py) | all_weather.py, asset_allocation_basics.py, value_factor.py |
| [추세추종과 손절](/posts/trend-following-stop-loss/) | [stop_loss.py](/assets/code/stop_loss.py) | |
| [세금과 거래 현실](/posts/taxes-and-trading-reality/) | [tax_drag.py](/assets/code/tax_drag.py) | value_factor.py |
| [자동매매 파이프라인](/posts/automated-trading-pipeline/) | [trading_pipeline.py](/assets/code/trading_pipeline.py) | |

워크포워드와 몬테카를로 스크립트는 월말 스냅샷과 구간별 수익률 파일(`data/krx/` 폴더)이 있어야 돌아갑니다. 먼저 `krx_fetch_monthly.py`와 `krx_fetch_returns.py`로 직접 받아 두세요.

코드가 돌아가지 않거나 글의 숫자와 다르게 나오면 [문의](/contact/)로 알려 주세요.
