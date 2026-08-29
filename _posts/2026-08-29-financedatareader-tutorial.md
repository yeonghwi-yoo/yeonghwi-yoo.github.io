---
title: "파이썬으로 주가 데이터 받아오기 — FinanceDataReader 시작하기"
categories:
  - 파이썬
tags:
  - FinanceDataReader
  - pandas
  - 데이터수집
---

퀀트 투자의 시작은 데이터입니다. 이번 글에서는 무료 오픈소스 라이브러리인 **FinanceDataReader**로 국내외 주가 데이터를 받아오는 방법을 정리합니다.

## FinanceDataReader란

[FinanceDataReader](https://github.com/FinanceData/FinanceDataReader)는 한국 주식(KRX), 미국 주식, 환율, 지수 등의 데이터를 pandas DataFrame으로 받아주는 파이썬 라이브러리입니다. 회원가입이나 API 키 없이 바로 쓸 수 있어서 입문용으로 가장 무난합니다.

설치는 pip 한 줄이면 됩니다.

```bash
pip install finance-datareader
```

## 종목 리스트 받기

먼저 KRX 전체 상장 종목 목록을 받아봅니다.

```python
import FinanceDataReader as fdr

# KRX 전체 상장 종목 (코스피 + 코스닥 + 코넥스)
krx = fdr.StockListing('KRX')
print(krx.head())
print(f"전체 종목 수: {len(krx)}")
```

`Code`(종목코드), `Name`(종목명), `Market`(시장) 같은 컬럼이 들어 있습니다. 종목코드는 이후 주가를 조회할 때 사용합니다.

## 개별 종목 주가 받기

삼성전자(005930)의 일별 주가를 받아보겠습니다.

```python
# 삼성전자, 2020년부터 현재까지
df = fdr.DataReader('005930', '2020-01-01')
print(df.tail())
```

결과는 날짜를 인덱스로 하는 DataFrame입니다.

| 컬럼 | 의미 |
|---|---|
| Open / High / Low / Close | 시가 / 고가 / 저가 / 종가 |
| Volume | 거래량 |
| Change | 전일 대비 등락률 |

미국 주식이나 지수도 같은 방식입니다.

```python
spy = fdr.DataReader('SPY', '2020-01-01')      # S&P 500 ETF
kospi = fdr.DataReader('KS11', '2020-01-01')   # 코스피 지수
usdkrw = fdr.DataReader('USD/KRW', '2020-01-01')  # 원달러 환율
```

## 간단한 차트 그리기

받은 데이터로 종가 차트를 그려봅니다.

```python
import matplotlib.pyplot as plt

df['Close'].plot(figsize=(12, 5), title='Samsung Electronics (005930)')
plt.ylabel('Price (KRW)')
plt.tight_layout()
plt.show()
```

누적 수익률로 바꿔서 보면 서로 다른 자산을 비교하기 좋습니다.

```python
# 일별 수익률 → 누적 수익률
returns = df['Close'].pct_change().fillna(0)
cum_returns = (1 + returns).cumprod() - 1
cum_returns.plot(figsize=(12, 5), title='Cumulative Return')
plt.show()
```

## 주의할 점

데이터를 받는 것 자체는 쉽지만, 백테스트에 쓰기 전에 알아야 할 함정이 있습니다.

1. **수정주가 여부** — 액면분할이나 배당이 반영된 가격인지 확인해야 합니다. 삼성전자는 2018년에 50:1 액면분할을 했기 때문에, 수정되지 않은 가격으로 계산하면 수익률이 완전히 틀어집니다.
2. **상장폐지 종목** — 현재 상장된 종목 목록으로 과거를 백테스트하면, 그 사이 망한 회사들이 빠져서 성과가 부풀려집니다(생존 편향).
3. **무료 데이터의 한계** — 실전 운용 수준의 정합성이 필요하면 결국 KRX 정보데이터시스템이나 증권사 API 같은 원천 데이터와 교차 검증이 필요합니다.

이 함정들은 각각 따로 글을 쓸 만큼 중요한 주제라, 시리즈에서 하나씩 다루겠습니다.

## 정리

- FinanceDataReader는 설치 후 바로 국내외 주가를 DataFrame으로 받을 수 있다.
- `StockListing('KRX')`로 종목 목록, `DataReader(코드, 시작일)`로 개별 주가를 받는다.
- 백테스트에 쓰기 전에 수정주가, 생존 편향 같은 데이터 품질 문제를 반드시 확인한다.

다음 글에서는 이 데이터를 이용해 가장 단순한 전략인 **모멘텀 전략의 백테스트**를 만들어 보겠습니다.

---

*이 글은 학습과 정보 공유 목적으로 작성되었으며, 특정 종목이나 상품에 대한 투자 권유가 아닙니다. 투자의 판단과 책임은 투자자 본인에게 있습니다.*
