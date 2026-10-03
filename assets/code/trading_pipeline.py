"""
자동매매 파이프라인의 뼈대 — 데이터 → 신호 → 목표 수량 → 주문 계획 → 안전장치 → 주문 → 기록

사용법:
    pip install pandas numpy finance-datareader
    python trading_pipeline.py              # 2025-01 ~ 최근 데이터로 매일 실행을 재생
    python trading_pipeline.py --synthetic  # 난수 데이터로 동작 확인

실제 증권사에 주문을 넣지 않는다. 주문은 PaperBroker(가상 계좌)가 받는다.
실제 API 를 붙일 때는 Broker 와 같은 메서드를 가진 클래스를 하나 더 만들어 바꿔 끼우면 된다.

데모용 가정: 코스피 지수(KS11) 종가를 그대로 가격으로 쓰는 가상 종목 하나를 사고판다.
신호는 200일 이동평균(실전 ⑧). 지수 데이터만 공개적으로 받을 수 있어서 이렇게 했다.
"""
import argparse
import json
import math
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)

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


# ---------------------------------------------------------------- 재생

def load(synthetic=False):
    if synthetic:
        rng = np.random.default_rng(10)
        idx = pd.bdate_range("2023-01-02", "2026-09-17")
        return pd.Series(2500 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, len(idx)))), index=idx)
    import FinanceDataReader as fdr
    return fdr.DataReader("KS11", "2023-01-01")["Close"].dropna()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--start", default="2025-01-01")
    ap.add_argument("--band", type=float, default=BAND)
    a = ap.parse_args()
    close = load(a.synthetic)
    days = close.loc[a.start:].index
    broker = PaperBroker(cash=10_000_000)
    ledger = {}
    log = []
    for d in days:
        msg = run_once(d, close, broker, ledger, a.band)
        if msg not in ("유지",):
            log.append(f"{d:%Y-%m-%d}  {msg}")
    again = run_once(days[-1], close, broker, ledger, a.band)         # 같은 날 재실행
    price = close.iloc[-1]
    equity = broker.get_cash() + broker.get_positions().get(SYMBOL, 0) * price
    bh = close.iloc[-1] / close.loc[a.start:].iloc[0]
    trades = [v for v in ledger.values() if v["action"] in ("buy", "sell")]
    lines = [f"허용 범위(band) {a.band:.0%}", f"재생 기간 {days[0]:%Y-%m-%d} ~ {days[-1]:%Y-%m-%d}, 실행 {len(days)}회, 주문 {len(trades)}건, "
             f"수수료 합계 {sum(t['fee'] for t in trades):,}원"]
    lines += log
    lines.append(f"마지막 날 재실행 결과: {again}")
    lines.append(f"최종 평가액 {equity:,.0f}원 (시작 10,000,000원, {equity / 1e7:.3f}배) / 같은 기간 보유 {bh:.3f}배")
    lines.append(f"현금 {broker.get_cash():,.0f}원, 보유 {broker.get_positions()}")
    print("\n".join(lines))
    with open(os.path.join(OUT, "trading_pipeline_results.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(os.path.join(OUT, "trading_pipeline_ledger.json"), "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    main()
