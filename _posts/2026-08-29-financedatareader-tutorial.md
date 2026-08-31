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

기간을 지정하고 싶으면 종료일을 두 번째 인자로 넘기면 됩니다.

```python
# 2020년 한 해만
df_2020 = fdr.DataReader('005930', '2020-01-01', '2020-12-31')
```

## 월별 데이터로 바꾸기

백테스트에서는 일별 데이터보다 월별 데이터를 쓰는 경우가 많습니다. 월 단위 리밸런싱 전략이 흔하기 때문입니다. pandas의 `resample`로 간단히 변환할 수 있습니다.

```python
# 월말 종가만 추출
monthly = df['Close'].resample('ME').last()

# 월별 수익률
monthly_returns = monthly.pct_change().dropna()
print(monthly_returns.head())
```

받은 데이터를 매번 다시 내려받지 않으려면 CSV로 저장해 두는 것이 좋습니다. 데이터 소스에 부담도 줄이고, 나중에 같은 데이터로 재현할 수도 있습니다.

```python
df.to_csv('samsung_005930.csv')

# 다시 불러올 때
import pandas as pd
df = pd.read_csv('samsung_005930.csv', index_col=0, parse_dates=True)
```

## 여러 종목을 한 번에 받아 합치기

백테스트를 하다 보면 결국 여러 종목의 종가를 한 표에 모으게 됩니다. 반복문으로 받아서 열로 합치는 것이 기본 패턴입니다.

```python
import pandas as pd
import time

tickers = {'005930': '삼성전자', '000660': 'SK하이닉스', '035420': 'NAVER'}

prices = {}
for code, name in tickers.items():
    prices[name] = fdr.DataReader(code, '2022-01-01')['Close']
    time.sleep(0.5)  # 데이터 소스에 부담을 주지 않도록 간격을 둔다

df_all = pd.DataFrame(prices)
print(df_all.tail())
```

이렇게 만든 표는 날짜 인덱스가 자동으로 정렬·정합되지만, 종목마다 거래정지 등으로 빠진 날짜가 다를 수 있으므로 `df_all.isna().sum()`으로 결측을 확인하는 습관이 필요합니다.

## 받은 데이터를 믿기 전에: 검증 습관 3가지

다운로드가 성공했다고 데이터가 멀쩡하다는 보장은 없습니다. 저는 새 데이터를 받으면 반드시 이 세 가지를 봅니다.

```python
# 1. 기간과 개수가 상식적인가 (1년이면 거래일 약 245~250개)
print(df.index.min(), df.index.max(), len(df))

# 2. 값의 범위가 상식적인가 (0이나 음수 가격, 터무니없는 급등락)
print(df['Close'].describe())
print(df['Close'].pct_change().abs().nlargest(5))  # 최대 등락일 확인

# 3. 결측과 중복이 없는가
print(df.isna().sum())
print(df.index.duplicated().sum())
```

2번에서 하루 ±30% 같은 값이 나오면 상한가·하한가(국내는 ±30%)일 수도 있지만 액면분할이 수정 반영되지 않은 것일 수도 있습니다. 날짜를 뉴스와 대조해 확인해야 합니다. 이 10분이 백테스트 전체를 살립니다.

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
4. **결측일 처리** — 휴장일, 거래정지일에는 데이터가 없습니다. 여러 종목을 비교할 때 날짜 인덱스를 맞추지 않으면(`pd.concat` 후 `dropna` 또는 `ffill`) 계산이 어긋납니다.

이 함정들은 각각 따로 글을 쓸 만큼 중요한 주제라, 시리즈에서 하나씩 다루겠습니다.

## 대안 라이브러리: pykrx

국내 데이터에 한정하면 [pykrx](https://github.com/sharebook-kr/pykrx)라는 선택지도 있습니다. KRX 정보데이터시스템을 직접 조회하는 방식이라 시가총액, PER/PBR 같은 투자지표, 공매도 잔고 등 FinanceDataReader에 없는 데이터를 받을 수 있습니다. 다만 요청이 잦으면 차단될 수 있어 대량 수집에는 주의가 필요합니다. 두 라이브러리는 용도가 달라서, 저는 주가는 FinanceDataReader, 재무·지표 데이터는 pykrx로 나눠 쓰고 있습니다. pykrx 사용법도 별도 글로 정리하겠습니다.

## 정리

- FinanceDataReader는 설치 후 바로 국내외 주가를 DataFrame으로 받을 수 있다.
- `StockListing('KRX')`로 종목 목록, `DataReader(코드, 시작일)`로 개별 주가를 받는다.
- 백테스트에 쓰기 전에 수정주가, 생존 편향 같은 데이터 품질 문제를 반드시 확인한다.

다음 글에서는 이 데이터를 이용해 가장 단순한 전략인 **모멘텀 전략의 백테스트**를 만들어 보겠습니다.

---

*이 글은 학습과 정보 공유 목적으로 작성되었으며, 특정 종목이나 상품에 대한 투자 권유가 아닙니다. 투자의 판단과 책임은 투자자 본인에게 있습니다.*
