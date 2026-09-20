---
title: "퀀트 실전 ① — pykrx로 한국 종목 재무 데이터 받아오기"
categories:
  - 파이썬
tags:
  - pykrx
  - 데이터
  - KRX
---

입문 시리즈는 미국 공개 데이터로 돌렸습니다. 실전 시리즈는 한국 종목으로 갑니다. 첫 관문은 데이터입니다. 종목별 PER, PBR, 배당수익률, 시가총액을 **특정 날짜 기준으로, 전 종목 한 번에** 받아와야 스크리닝이든 팩터 백테스트든 시작할 수 있습니다.

이 일에 가장 많이 쓰는 도구가 `pykrx`입니다. 한국거래소(KRX) 정보데이터시스템에서 내려주는 값을 pandas 표로 받아주는 라이브러리입니다. 가격은 [FinanceDataReader](/posts/financedatareader-tutorial/)로도 받을 수 있지만, 전 종목 재무 지표를 날짜 단위로 주는 건 이쪽입니다.

## 먼저 걸리는 것: 로그인

예전 글들을 보고 `pip install pykrx` 하고 바로 호출하면 이런 메시지가 뜹니다.

```
KRX 로그인 실패: KRX_ID 또는 KRX_PW 환경 변수가 설정되지 않았습니다.
```

KRX가 데이터 포털에 로그인을 요구하도록 바뀌었고, pykrx 1.2 이후 버전은 그에 맞춰 **계정으로 로그인한 세션**을 씁니다. 라이브러리 안을 열어보면 `KRX_ID`, `KRX_PW` 환경 변수를 읽어 로그인하고, 세션이 만료되면 자동으로 다시 로그인하게 되어 있습니다. 계정은 [KRX 정보데이터시스템](https://data.krx.co.kr)에서 무료로 만들 수 있습니다.

```bash
# macOS / Linux
export KRX_ID="아이디"
export KRX_PW="비밀번호"

# Windows PowerShell
$env:KRX_ID = "아이디"
$env:KRX_PW = "비밀번호"
```

비밀번호를 코드나 노트북 안에 직접 쓰지 마세요. 환경 변수로 두면 코드를 공개해도 계정은 남지 않습니다.

## 함수 네 개면 됩니다

pykrx 함수는 수십 개지만, 재무 스냅샷을 만드는 데 필요한 건 넷입니다.

| 함수 | 주는 것 | 인자 |
|---|---|---|
| `get_market_ticker_list(date, market)` | 그 날짜의 상장 종목 코드 목록 | `market`은 `KOSPI` / `KOSDAQ` / `KONEX` / `ALL` |
| `get_market_fundamental(date, market=...)` | 전 종목 BPS, PER, PBR, EPS, DIV, DPS | 날짜 하나를 주면 전 종목, 두 개를 주면 한 종목의 기간 |
| `get_market_cap_by_ticker(date, market=...)` | 전 종목 종가, 시가총액, 거래량, 상장주식수 | |
| `get_market_ohlcv(fromdate, todate, ticker)` | 한 종목의 일별 OHLCV | `adjusted=True`가 기본(수정주가) |

날짜는 전부 `"20260630"` 형식의 문자열입니다. `-`가 들어가도 알아서 지워주지만, 처음부터 여덟 자리로 쓰는 습관이 낫습니다. 종목 코드도 문자열입니다. `5930`이 아니라 `"005930"`입니다. 정수로 들고 있으면 앞의 0이 사라져 다른 종목이 됩니다.

`get_market_fundamental`은 인자 개수로 동작이 갈립니다. 날짜 하나면 "그날 전 종목", 날짜 둘과 종목 코드면 "그 종목의 기간별"입니다. 같은 이름으로 두 가지 일을 하니 처음에 헷갈립니다.

## 하루치 스냅샷 만들기

펀더멘털 표와 시가총액 표를 종목 코드로 합치고, 종목명을 붙이고, CSV로 저장합니다.

```python
import time
import pandas as pd
from pykrx import stock

def fetch_snapshot(date: str, market: str = "KOSPI") -> pd.DataFrame:
    """특정 일자의 전 종목 펀더멘털 + 시가총액을 한 표로 합친다."""
    # 휴일이면 직전 영업일로 대체 (alternative=True)
    fund = stock.get_market_fundamental_by_ticker(date, market=market, alternative=True)
    time.sleep(1)                                   # 연속 호출 사이에 쉬어 준다
    cap = stock.get_market_cap_by_ticker(date, market=market, alternative=True)
    time.sleep(1)
    names = pd.Series({t: stock.get_market_ticker_name(t) for t in fund.index}, name="종목명")

    df = fund.join(cap[["종가", "시가총액", "상장주식수"]], how="inner").join(names)
    df.index.name = "티커"
    return df

df = fetch_snapshot("20260630")
df.to_csv("krx_snapshot_20260630.csv", encoding="utf-8-sig")
```

`alternative=True`는 휴일을 넣었을 때 직전 영업일 값을 돌려달라는 뜻입니다. 이게 없으면 빈 표가 옵니다. `time.sleep(1)`은 예의입니다. 전 종목을 한 번에 받는 호출은 서버 쪽 부담이 크고, 연속으로 두드리면 차단당합니다.

한 날짜에 세 번 호출로 끝나므로, 월말 기준 5년치 스냅샷을 만들어도 180번 정도입니다. 결과는 반드시 파일로 저장하세요. 같은 데이터를 다시 받는 것이 가장 흔한 낭비입니다.

## 받은 다음 반드시 손볼 것

여기가 이 글에서 제일 중요한 부분입니다. KRX가 주는 표에는 **"값이 없음"을 0으로 적는 관례**가 있습니다.

| 열 | 0의 뜻 | 그대로 쓰면 |
|---|---|---|
| PER | 적자 종목 (EPS ≤ 0) | "PER 낮은 순"으로 정렬하면 적자 기업이 맨 위에 옵니다 |
| BPS, PBR | 값 없음 | PBR 0.0이 "극단적으로 싼 주식"으로 잡힙니다 |
| DIV, DPS | 무배당 | 이건 실제로 0이 맞습니다 |

저PER 스크리닝을 하면서 이걸 모르면 적자 기업 목록을 뽑아놓고 "싼 주식"이라 부르게 됩니다. 실제 값과 없음을 구분해서 `NaN`으로 바꿔야 합니다.

```python
import numpy as np

def clean(df: pd.DataFrame) -> pd.DataFrame:
    """KRX 의 '0 = 없음' 관례를 NaN 으로 바꾸고, 스크리닝에 쓸 파생 열을 만든다."""
    out = df.copy()
    out.loc[out["EPS"] <= 0, "PER"] = np.nan      # 적자: PER 0 은 값이 아니라 표시
    out.loc[out["BPS"] <= 0, ["BPS", "PBR"]] = np.nan
    out.loc[out["DPS"] <= 0, "DIV"] = 0.0
    out["시총(억)"] = (out["시가총액"] / 1e8).round(0)
    out["이익수익률"] = (out["EPS"] / out["종가"]).where(out["EPS"] > 0)   # 1/PER
    return out
```

마지막 줄의 이익수익률은 PER의 역수입니다. 다음 글에서 종목을 줄 세울 때 PER 대신 이걸 씁니다. PER은 적자에서 정의가 안 되지만 이익수익률은 음수로 자연스럽게 이어지고, 정렬 방향도 "클수록 싸다"로 직관과 맞습니다.

## 시점 문제

`get_market_fundamental("20260630")`이 주는 EPS와 BPS는 **그 시점에 KRX가 적용하고 있던 직전 확정 실적**입니다. 6월 30일에 조회하면 대개 전년도 사업보고서 기준입니다. 그래서 "2025년 실적으로 2025년 1월의 PER을 계산"하는 실수는 이 함수로는 생기지 않습니다. 그날 실제로 공개되어 있던 숫자를 주기 때문입니다.

이건 장점이면서 주의점입니다. 장점은 [미래 참조 편향](/posts/look-ahead-bias-faces/)이 자동으로 막힌다는 것이고, 주의점은 재무 지표의 갱신 시점이 회사마다 달라서 같은 날짜의 PER이 어떤 종목은 넉 달 전 실적, 어떤 종목은 열 달 전 실적일 수 있다는 것입니다. 정밀하게 하려면 사업보고서 공시일을 따로 붙여야 하는데, 그건 이 시리즈 후반에 다룹니다.

## 이 글에 실제 표가 없는 이유

솔직하게 적습니다. 이 글은 실제 호출 결과를 싣지 못했습니다. 글을 쓴 환경에서 KRX 서버 접속이 막혀 있었습니다. 위 코드는 pykrx 소스를 직접 열어 함수 이름, 인자, 돌려주는 열 이름을 확인해서 썼고, `fetch_snapshot`이 돌려주는 것과 같은 열 구조의 난수 표를 만들어 `clean` 이후의 처리가 맞게 도는지만 확인했습니다. `scripts/krx_snapshot.py`에 `--synthetic` 옵션으로 그 검증 코드가 들어 있습니다.

그래서 이 글에서 확인된 것은 "이 코드가 어떤 표를 주는가"가 아니라 "받은 표를 어떻게 손봐야 하는가"입니다. 직접 돌려보시고 열 이름이 달라져 있으면 알려주시면 고치겠습니다.

다음 글에서는 이 스냅샷 CSV를 재료로 종목 스크리닝을 만듭니다. 이익수익률, PBR, 배당수익률로 줄을 세우고, 시가총액 하한을 두고, 결과가 왜 대부분 지주회사와 은행으로 채워지는지 봅니다.

---

*이 글은 학습과 정보 공유 목적으로 작성되었으며, 특정 종목이나 상품에 대한 투자 권유가 아닙니다. 투자의 판단과 책임은 투자자 본인에게 있습니다.*
