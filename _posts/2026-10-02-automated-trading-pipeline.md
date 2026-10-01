---
title: "퀀트 실전 ⑩ — 자동매매 파이프라인 만들기, 주문보다 안전장치가 먼저다"
categories:
  - 퀀트투자
tags:
  - 자동매매
  - 증권사API
  - 파이썬
  - 파이프라인
  - 백테스트
---

실전 시리즈에서 전략을 만들고, 검증하고, 비중을 정하고, 비용과 세금까지 넣어 봤습니다. 남은 것은 그 전략을 실제 계좌에서 돌리는 일입니다. 매일 같은 시각에 데이터를 받고, 신호를 계산하고, 주문을 내는 일을 사람이 손으로 하면 언젠가는 빼먹거나 틀립니다. 그래서 자동화를 합니다.

이번 글은 증권사 API에 주문을 넣는 코드보다 **그 앞뒤에 무엇이 있어야 하는지**를 다룹니다. 주문 함수 자체는 증권사 예제를 따라 하면 몇 줄이면 됩니다. 사고는 대부분 그 주변에서 납니다.

## 국내 증권사 API, 어떤 선택지가 있나

개인이 파이썬으로 쓸 수 있는 국내 증권사 API는 크게 두 갈래입니다.

- **REST API**: HTTP 요청으로 시세 조회와 주문을 합니다. 운영체제를 가리지 않아 리눅스 서버나 클라우드에서도 돌릴 수 있습니다. 한국투자증권의 KIS Developers가 대표적이고, 공식 GitHub에 파이썬 예제가 공개돼 있습니다. 키움증권과 LS증권도 REST 방식 API를 제공합니다.
- **윈도우 전용 API**: 키움증권의 OpenAPI+처럼 윈도우 프로그램(COM/OCX) 위에서 동작하는 방식입니다. 오래 쓰여 자료가 많지만 윈도우 PC를 계속 켜 둬야 합니다.

어느 쪽이든 공통으로 확인할 것이 있습니다. **모의투자 환경**이 있는지(실제 돈 없이 주문 흐름을 시험할 수 있는지), 인증 토큰의 유효 기간, 초당 호출 제한입니다. 세부 사양은 증권사마다 다르고 자주 바뀌므로 각 증권사의 공식 문서를 기준으로 봐야 합니다. 이 글의 코드는 특정 증권사에 묶이지 않게 짰습니다.

## 파이프라인의 일곱 단계

하루 한 번 도는 자동매매는 이런 순서를 따릅니다.

```
1. 데이터    오늘까지의 가격을 받는다
2. 신호      목표 비중을 계산한다            (실전 ⑧의 200일 이동평균)
3. 목표 수량  비중 × 평가액 ÷ 가격, 정수 주로 내림
4. 주문 계획  목표 − 현재 보유, 작은 차이는 무시
5. 안전장치   가격 이상, 주문 금액 상한, 중복 실행 확인
6. 주문      브로커에 전달
7. 기록      무엇을 왜 했는지 남긴다
```

백테스트 코드에는 1, 2단계만 있습니다. 3단계부터가 실제 계좌의 세계입니다. 주식은 0.37주를 살 수 없고, 계좌에는 수수료를 낼 현금이 남아 있어야 하고, 같은 프로그램이 실수로 두 번 돌 수 있습니다.

## 코드

아래 코드는 증권사에 주문을 넣지 않습니다. 주문은 메모리 안의 가상 계좌(`PaperBroker`)가 받습니다. 실제 증권사를 붙일 때는 같은 메서드 세 개(`get_cash`, `get_positions`, `place_order`)를 가진 클래스를 만들어 바꿔 끼우면 됩니다. 실제 증권사 쪽에는 현재가 조회도 하나 더 필요합니다.

데모로 사고팔 수 있는 데이터가 필요해서, 코스피 지수 종가를 그대로 가격으로 쓰는 **가상 종목** 하나를 만들었습니다. 실제로는 코스피200을 따르는 ETF를 사고팔게 될 것입니다. [세금 글](/posts/taxes-and-trading-reality/)에서 봤듯이 국내 주식형 ETF는 매매차익이 비과세이고 증권거래세도 없어서, 이런 규칙을 돌리기에 세금 부담이 가장 적은 그릇입니다.

```python
import math

import FinanceDataReader as fdr

SYMBOL = "KOSPI_PROXY"          # 데모용 가상 종목
MA_DAYS = 200
CASH_BUFFER = 0.02              # 수수료·가격 변동 대비로 남겨 두는 현금 비율
MIN_TRADE_VALUE = 100_000       # 이보다 작은 주문은 내지 않는다 (잔돈 주문 방지)
BAND = 0.05                     # 목표와 현재 차이가 평가액의 5% 미만이면 그대로 둔다
MAX_ORDER_RATIO = 1.0           # 한 번에 낼 수 있는 주문 금액 / 평가액 상한
MAX_PRICE_JUMP = 0.15           # 직전 종가 대비 이보다 크게 움직인 가격이면 멈춘다
FEE = 0.00015                   # 편도 수수료 가정 (ETF 는 증권거래세 없음)


# ---------------------------------------------------------------- 브로커

class PaperBroker:
    """가상 계좌. 실제 증권사 클래스도 같은 메서드 네 개만 맞추면 된다."""

    def __init__(self, cash):
        self.cash = float(cash)
        self.positions = {}

    def get_cash(self):
        return self.cash

    def get_positions(self):
        return dict(self.positions)

    def place_order(self, symbol, side, qty, price, client_id):
        value = qty * price
        fee = value * FEE
        if side == "buy":
            if value + fee > self.cash:
                raise RuntimeError(f"현금 부족: {value + fee:,.0f} > {self.cash:,.0f}")
            self.cash -= value + fee
            self.positions[symbol] = self.positions.get(symbol, 0) + qty
        else:
            if qty > self.positions.get(symbol, 0):
                raise RuntimeError("보유 수량보다 많이 팔 수 없음")
            self.cash += value - fee
            self.positions[symbol] -= qty
        return {"client_id": client_id, "symbol": symbol, "side": side,
                "qty": qty, "price": price, "fee": round(fee)}


# ---------------------------------------------------------------- 단계별 함수

def signal(close):
    """종가가 200일 평균 위면 1(보유), 아니면 0(현금). 데이터가 모자라면 판단하지 않는다."""
    if len(close) < MA_DAYS:
        return None
    return 1.0 if close.iloc[-1] > close.iloc[-MA_DAYS:].mean() else 0.0


def target_qty(weight, equity, price):
    return math.floor(equity * (1 - CASH_BUFFER) * weight / price)


def plan_order(current, target, price, equity, band=BAND):
    diff = target - current
    if diff == 0 or abs(diff) * price < max(MIN_TRADE_VALUE, equity * band):
        return None
    return ("buy" if diff > 0 else "sell", abs(diff))


def check(order, price, prev_close, equity):
    """주문 직전 안전장치. 문제가 있으면 이유를 돌려준다."""
    side, qty = order
    if prev_close and abs(price / prev_close - 1) > MAX_PRICE_JUMP:
        return f"가격 이상: 직전 종가 대비 {price / prev_close - 1:+.1%}"
    if qty * price > equity * MAX_ORDER_RATIO:
        return f"주문 금액 상한 초과: {qty * price:,.0f}"
    return None


def run_once(day, close, broker, ledger, band=BAND):
    """하루 한 번 실행. 같은 날 두 번 돌려도 주문은 한 번만 나간다."""
    run_id = f"{day:%Y-%m-%d}-{SYMBOL}"
    if run_id in ledger:
        return "이미 실행됨"
    hist = close.loc[:day]
    w = signal(hist)
    if w is None:
        return "데이터 부족"
    price = hist.iloc[-1]
    prev = hist.iloc[-2] if len(hist) > 1 else None
    pos = broker.get_positions().get(SYMBOL, 0)
    equity = broker.get_cash() + pos * price
    order = plan_order(pos, target_qty(w, equity, price), price, equity, band)
    if order is None:
        ledger[run_id] = {"action": "유지", "weight": w}
        return "유지"
    reason = check(order, price, prev, equity)
    if reason:
        ledger[run_id] = {"action": "중단", "reason": reason}
        return "중단: " + reason
    fill = broker.place_order(SYMBOL, order[0], order[1], price, client_id=run_id)
    ledger[run_id] = {"action": order[0], **fill}
    return f"{order[0]} {order[1]}주 @ {price:,.2f}"


close = fdr.DataReader("KS11", "2023-01-01")["Close"]
broker, ledger = PaperBroker(cash=10_000_000), {}
for day in close.loc["2025-01-01":].index:
    msg = run_once(day, close, broker, ledger)
    if msg != "유지":
        print(f"{day:%Y-%m-%d}  {msg}")
print(run_once(close.index[-1], close, broker, ledger))     # 같은 날 다시 돌리면?
```

전체 스크립트는 `scripts/trading_pipeline.py`에 있습니다.

몇 군데를 짚어 보면 이렇습니다.

- `run_once`는 날짜와 종목으로 **실행 ID**를 만들고, 장부(`ledger`)에 이미 있으면 아무것도 하지 않습니다. 서버가 재시작되거나 스케줄러가 두 번 깨워도 주문은 한 번만 나갑니다. 실제 증권사 주문에서도 이 ID를 주문 메모나 로컬 기록에 남겨 두면, 재시작 후 "이 주문을 이미 냈나"를 확인할 수 있습니다.
- `check`는 주문 직전의 마지막 관문입니다. 가격이 직전 종가 대비 15% 넘게 움직였거나 주문 금액이 평가액을 넘으면 멈춥니다. 데이터 오류로 가격이 0이 되거나 소수점이 밀리는 일은 생각보다 흔합니다.
- `BAND`는 목표와 현재의 차이가 평가액의 5%보다 작으면 주문하지 않게 합니다. 이 값이 왜 필요한지는 아래 결과에서 보입니다.
- 장부에는 주문을 냈을 때만이 아니라 **유지하거나 멈춘 날도** 남깁니다. 나중에 "그날 왜 안 샀지?"를 확인할 수 있어야 합니다.

## 2025년부터 매일 돌렸다면

2025년 1월 2일부터 2026년 9월 17일까지 417거래일 동안 매일 장 마감 후 한 번씩 돌렸다고 보고 재생했습니다. 시작 금액은 1,000만 원입니다.

| 날짜 | 결과 |
|---|---|
| 2025-02-18 | 매수 3,730주 |
| 2025-02-28 | 매도 3,730주 |
| 2025-03-17 | 매수 3,621주 |
| 2025-03-28 | 매도 3,621주 |
| 2025-05-07 | 매수 3,599주 |
| 2026-07-29 | 매도 3,599주 |
| 2026-07-31 | **중단**: 직전 종가 대비 +17.9% |
| 2026-08-03 | 매수 3,221주 |
| 마지막 날 재실행 | 이미 실행됨, 주문 없음 |

417번 실행해서 주문은 7건이었습니다. 최종 평가액은 2,207만 원으로 2.21배, 같은 기간 그냥 들고 있었다면 2.80배였습니다. 2025년 2~3월의 두 번 왕복은 [추세추종 글](/posts/trend-following-stop-loss/)에서 본 휩쏘 그대로입니다. 규칙의 성과는 이 글의 관심사가 아니니 여기까지만 봅니다.

눈여겨볼 것은 두 가지입니다.

**처음 돌렸을 때는 주문이 12건이었습니다.** `BAND` 없이 돌리자 2025년 10월부터 2026년 7월 사이에 13~26주짜리 매도가 네 번, 17주짜리 매수가 한 번 나왔습니다. 원인은 현금 버퍼였습니다. 평가액의 2%를 현금으로 남기도록 했는데, 지수가 오르면 주식 평가액이 커지고 남겨야 할 현금도 커지니 그만큼 주식을 조금씩 팔았습니다. 신호는 그대로 "보유"인데 계좌는 쓸데없이 매매를 하고 있었습니다. 금액이 작아 수수료는 몇십 원이었지만, 실제 계좌라면 매번 체결 확인과 기록이 붙는 주문입니다. 백테스트에서는 비중을 연속된 숫자로 다루니 이런 일이 보이지 않습니다. 정수 주와 현금 버퍼가 들어가는 순간 처음 드러납니다.

**안전장치가 실제 시장 움직임에 걸렸습니다.** 2026년 7월 31일 코스피는 하루에 17.9% 올랐습니다. 데이터 오류가 아니라 실제 움직임이었지만, 15% 기준에 걸려 그날 매수가 멈췄고 다음 거래일에 샀습니다. 이번에는 다음 날 가격이 더 낮아서 결과적으로 손해가 없었지만, 반대였을 수도 있습니다. 안전장치는 **틀린 데이터와 극단적인 진짜 데이터를 구분하지 못합니다.** 그래서 멈췄을 때 조용히 넘어가지 말고 사람에게 알려서 확인하게 해야 합니다. 이 데모에서는 장부에만 남겼지만, 실제로는 메일이나 메신저 알림을 붙이는 것이 보통입니다.

## 실제 API를 붙이기 전에 확인할 것

가상 계좌를 실제 증권사로 바꾸는 순간 새로 생기는 문제들이 있습니다.

- **자격증명 관리.** 앱 키, 비밀 키, 계좌번호는 코드에 적지 않고 환경변수나 별도 설정 파일에 둡니다. 그 파일은 절대 Git에 올리지 않습니다. 공개 저장소에 키가 올라가면 몇 분 안에 수집된다고 보는 편이 안전합니다.
- **모의투자부터.** 같은 코드로 모의투자 계좌에서 최소 몇 주는 돌려 봅니다. 주문이 거부되는 경우(호가 단위, 주문 가능 시간, 잔고 부족)를 실제 돈 없이 겪어 볼 수 있습니다.
- **체결은 주문과 다르다.** 주문을 냈다고 체결된 것이 아닙니다. 지정가 주문은 안 맞을 수 있고, 일부만 체결될 수도 있습니다. 다음 실행에서 목표 수량을 다시 계산할 때 **실제 잔고를 증권사에서 다시 읽어 오는** 구조여야 미체결이 쌓여도 스스로 맞춰집니다. 위 코드가 매번 `get_positions()`로 시작하는 이유입니다.
- **장 시간과 휴장일.** 장 마감 후에 신호를 계산하고 다음 날 시초가나 장중에 주문하는 식으로 시점을 분리합니다. 휴장일에 돌면 아무것도 하지 않아야 합니다.
- **토큰과 호출 제한.** REST API는 대개 일정 시간마다 접근 토큰을 새로 받아야 하고, 초당 호출 수에 제한이 있습니다. 실패하면 몇 번 재시도하되, 주문 요청은 재시도 전에 이미 들어갔는지 먼저 확인합니다. 그렇지 않으면 같은 주문이 두 번 나갑니다.
- **비상 정지.** 파일 하나를 만들거나 설정값 하나를 바꾸면 다음 실행부터 주문을 내지 않는 스위치를 둡니다. 무언가 이상할 때 코드를 고치지 않고도 멈출 수 있어야 합니다.
- **규모는 작게.** 처음에는 전략에 넣을 돈의 일부만으로 시작합니다. 자동매매의 첫 몇 달은 전략이 아니라 **파이프라인을 검증하는 기간**입니다.

## 실전 시리즈를 마치며

실전 시리즈에서 한 일을 돌아보면, 수익을 늘리는 방법보다 **착각을 줄이는 방법**을 더 많이 다뤘습니다. [워크포워드](/posts/walk-forward-validation/)와 [몬테카를로](/posts/monte-carlo-validation/)로 운과 실력을 가르려 했고, [평균-분산](/posts/mean-variance-optimization/)과 [리스크 패리티](/posts/risk-parity/)로 비중을 정하는 법을 봤고, [켈리](/posts/kelly-criterion/)로 얼마나 걸지를, [추세추종](/posts/trend-following-stop-loss/)으로 언제 나올지를, [세금](/posts/taxes-and-trading-reality/)으로 무엇이 실제로 남는지를 봤습니다. 이번 글의 자동화도 같은 이야기입니다. 백테스트에서는 보이지 않던 정수 주, 현금 버퍼, 중복 실행, 극단적인 날이 실제로 돌리는 순간 드러납니다.

전략은 백테스트에서 끝나지 않습니다. 실제 계좌에서 몇 년을 버티며 돌아갈 때 비로소 끝납니다.

---

*이 글은 학습과 정보 공유 목적으로 작성되었으며, 특정 종목이나 상품, 증권사 서비스에 대한 투자 권유나 추천이 아닙니다. 본문의 코드는 교육용 예시이며, 실제 계좌에 연결해 사용할 경우 발생하는 손실과 오류에 대한 책임은 사용자 본인에게 있습니다. 투자의 판단과 책임은 투자자 본인에게 있습니다.*
