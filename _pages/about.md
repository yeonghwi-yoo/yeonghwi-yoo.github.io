---
title: "소개"
permalink: /about/
description: "퀀트 노트는 퀀트 투자 전략을 공개 데이터와 파이썬 코드로 다시 검증하는 블로그입니다. 쓰는 데이터, 검증 방법, 편집 원칙, 다루지 않는 것을 정리했습니다."
---

**퀀트 노트**는 자주 듣는 퀀트 투자 전략을 공개 데이터와 파이썬 코드로 다시 돌려 보는 블로그입니다.

"이 전략으로 연 몇 퍼센트"라는 이야기는 많지만, 어떤 데이터로 어느 기간을 봤는지, 거래비용과 세금을 넣었는지, 다른 기간에도 통했는지는 잘 나오지 않습니다. 이 블로그는 그 과정을 남깁니다. 데이터를 어디서 받았고, 어떤 코드로 계산했고, 어디서 기대와 달랐는지까지 씁니다.

## 무엇을 쓰나

- **[퀀트 투자 입문](/posts/quant-intro-series-index/)** (20편) — 수익률 계산, 백테스트의 함정(비용·과최적화·미래 참조·생존 편향), 위험 지표, 자산 배분, 팩터, 듀얼 모멘텀과 올웨더
- **[퀀트 실전](/posts/quant-practice-series-index/)** (10편) — 한국 종목 재무 데이터 수집, 스크리닝, 워크포워드·몬테카를로 검증, 평균-분산·리스크 패리티·켈리, 추세추종과 손절, 세금, 자동매매 파이프라인
- 짧은 실험과 논문 읽기 — 큰 시리즈에서 다 확인하지 못한 질문들

전체 목록은 [전체 글](/posts/)에 있습니다.

## 어떤 데이터를 쓰나

글에 쓴 데이터는 모두 누구나 받을 수 있는 공개 데이터입니다.

| 데이터 | 받는 방법 | 쓴 글 예시 |
|---|---|---|
| 코스피·코스닥 지수 일별 종가 | [FinanceDataReader](https://github.com/FinanceData/FinanceDataReader) | [첫 백테스트](/posts/first-backtest-absolute-momentum/), [추세추종과 손절](/posts/trend-following-stop-loss/) |
| 한국 종목 PER·PBR·시가총액·수익률 | [한국거래소 정보데이터시스템](http://data.krx.co.kr), [pykrx](https://github.com/sharebook-kr/pykrx) | [pykrx로 재무 데이터 받기](/posts/pykrx-fundamentals/), [워크포워드 검증](/posts/walk-forward-validation/) |
| 미국 팩터 수익률 | [Kenneth French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) | [밸류 팩터](/posts/value-factor/), [멀티팩터](/posts/multifactor-portfolio/) |
| 미국 주식·배당·장기 금리 | 로버트 실러(Robert Shiller)의 공개 데이터 | [자산 배분 기초](/posts/asset-allocation-basics/), [켈리 공식](/posts/kelly-criterion/) |
| 금 월별 가격 | 공개 데이터셋(datasets/gold-prices) | [올웨더 포트폴리오](/posts/all-weather-portfolio/) |

글마다 데이터의 기간과 한계를 함께 적습니다. 공개 사본의 갱신이 멈춘 데이터는 어디서 끊겼는지 밝히고, 그 뒤의 기간에 대해서는 단정하지 않습니다. 결과를 낸 파이썬 코드는 [코드](/code/) 페이지에서 받을 수 있습니다.

## 어떻게 검증하나

백테스트 숫자는 그대로 믿지 않습니다. 이 블로그의 글은 아래 함정을 확인하는 데서 출발합니다.

- [거래 비용과 슬리피지](/posts/trading-costs-and-slippage/)를 넣었을 때도 성과가 남는가
- [미래 참조 편향](/posts/look-ahead-bias-faces/)이 끼지 않았는가, [생존 편향](/posts/survivorship-bias/)은 없는가
- 여러 설정 중 가장 좋은 것을 고른 [과최적화](/posts/overfitting-in-backtesting/)는 아닌가, [워크포워드](/posts/walk-forward-validation/)로 미래를 보지 않고 골라도 같은가
- 그 수익률이 [운으로도 나올 수 있는 수준](/posts/monte-carlo-validation/)은 아닌가

## 편집 원칙

[첫 글](/posts/hello-quant-note/)에서 세 가지를 약속했습니다.

1. **재현 가능하게** — 결과에는 데이터 출처, 기간, 가정을 함께 남기고 코드를 공개합니다.
2. **틀리면 고치기** — 잘못된 내용은 고치고 그 사실을 [수정 기록](/changelog/)과 해당 글에 남깁니다. 예를 들어 [종목 스크리닝 글](/posts/stock-screener/)은 앞 글의 잘못된 서술을 데이터로 확인하고 바로잡은 절을 따로 두었습니다.
3. **권유하지 않기** — 특정 종목이나 상품을 추천하지 않습니다.

다루지 않는 것도 분명히 해 둡니다. 종목 추천, 시황 해설, 목표 주가, 매매 신호는 이 블로그에 없습니다.

## 운영

이 블로그는 익명으로 운영합니다. 글의 신뢰는 글쓴이의 이력이 아니라, 누구나 같은 데이터와 코드로 다시 확인할 수 있다는 데서 나온다고 생각합니다. 새 글은 보통 일주일에 몇 편씩 올리고, 이미 올린 글도 오류가 발견되거나 더 나은 데이터가 생기면 고칩니다.

## 문의

오류 제보, 데이터나 코드에 대한 질문은 [문의](/contact/) 페이지나 [contact@quant-note.com](mailto:contact@quant-note.com)으로 보내 주세요.

## 면책 조항

이 블로그의 모든 글은 학습과 정보 공유 목적으로 작성되었으며, **특정 종목이나 상품에 대한 투자 권유가 아닙니다**. 과거 데이터로 계산한 결과는 미래 성과를 보장하지 않습니다. 투자에 대한 판단과 책임은 투자자 본인에게 있습니다.
