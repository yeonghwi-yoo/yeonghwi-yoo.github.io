"""
퀀트 노트 입문 시리즈 ⑤~⑧ 백테스트 일괄 실행 스크립트

사용법:
    pip install finance-datareader pandas numpy matplotlib
    python scripts/run_series_backtests.py

결과: scripts/output/results.txt 와 차트 PNG 파일들
(--synthetic 옵션을 주면 실제 데이터 대신 난수 데이터로 동작 확인만 한다)
"""
import sys
import os
import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


# ---------- 데이터 ----------
def load_monthly(synthetic=False):
    if synthetic:
        rng = np.random.default_rng(0)
        idx = pd.date_range("2005-01-31", "2026-08-31", freq="ME")
        px = 1000 * np.cumprod(1 + rng.normal(0.006, 0.05, len(idx)))
        return pd.Series(px, index=idx, name="KOSPI(synthetic)")
    import FinanceDataReader as fdr
    kospi = fdr.DataReader("KS11", "2005-01-01")["Close"]
    return kospi.resample("ME").last().rename("KOSPI")


# ---------- 공통 함수 (⑧ 위험 지표) ----------
def drawdown_stats(cum):
    peak = cum.cummax()
    dd = cum / peak - 1
    under = dd < 0
    longest = run = 0
    for flag in under:
        run = run + 1 if flag else 0
        longest = max(longest, run)
    return dd, dd.min(), longest


def sharpe(r, rf_annual=0.03, periods=12):
    rf = (1 + rf_annual) ** (1 / periods) - 1
    ex = r - rf
    return np.nan if ex.std() == 0 else ex.mean() / ex.std() * np.sqrt(periods)


def sortino(r, rf_annual=0.03, periods=12):
    rf = (1 + rf_annual) ** (1 / periods) - 1
    ex = r - rf
    d = ex[ex < 0].std()
    return np.nan if (d == 0 or np.isnan(d)) else ex.mean() / d * np.sqrt(periods)


def performance_summary(returns, rf_annual=0.03, periods=12):
    r = returns.dropna()
    cum = (1 + r).cumprod()
    n_years = len(r) / periods
    cagr = cum.iloc[-1] ** (1 / n_years) - 1
    vol = r.std() * np.sqrt(periods)
    _, mdd, longest = drawdown_stats(cum)
    return pd.Series({
        "CAGR": cagr, "Volatility": vol, "MDD": mdd,
        "Sharpe": sharpe(r, rf_annual, periods),
        "Sortino": sortino(r, rf_annual, periods),
        "Calmar": cagr / abs(mdd) if mdd != 0 else np.nan,
        "Longest DD (months)": longest,
    })


# ---------- ⑤⑥ 절대 모멘텀 (비용 포함) ----------
def momentum(monthly, lookback=12, cost=0.0):
    returns = monthly.pct_change()
    signal = (monthly.pct_change(lookback) > 0).astype(int)
    position = signal.shift(1)
    trades = position.diff().abs().fillna(0)
    net = position * returns - trades * cost
    return returns, net, trades


def cagr_of(r):
    r = r.dropna()
    cum = (1 + r).cumprod()
    return cum.iloc[-1] ** (12 / len(r)) - 1


def main():
    synthetic = "--synthetic" in sys.argv
    monthly = load_monthly(synthetic)
    log(f"데이터: {monthly.name}, {monthly.index[0].date()} ~ {monthly.index[-1].date()}, {len(monthly)}개월")
    if synthetic:
        log("(주의: --synthetic 모드. 난수 데이터이므로 수치는 의미 없음)")
    log()

    # ----- ⑤ 첫 백테스트 -----
    log("=" * 60)
    log("⑤ 절대 모멘텀(12개월) vs Buy & Hold  [비용 미반영]")
    log("=" * 60)
    returns, gross, trades = momentum(monthly, 12, cost=0.0)
    res5 = pd.DataFrame({"Buy & Hold": returns, "Momentum": gross}).dropna()
    cum5 = (1 + res5).cumprod()
    summ5 = pd.DataFrame({c: performance_summary(res5[c]) for c in res5.columns})
    log(summ5.round(4).to_string())
    log()

    # ----- ⑥ 거래 비용 -----
    log("=" * 60)
    log("⑥ 거래 비용 반영 (편도 0.3% 가정)")
    log("=" * 60)
    _, net, trades = momentum(monthly, 12, cost=0.003)
    res6 = pd.DataFrame({"Buy & Hold": returns, "Momentum (gross)": gross, "Momentum (net)": net}).dropna()
    n_years = len(res6) / 12
    n_trades = trades.loc[res6.index].sum()
    log(f"총 매매 횟수: {n_trades:.0f}회, 연평균 {n_trades / n_years:.2f}회")
    log("CAGR:")
    log(res6.apply(cagr_of).round(4).to_string())
    log()

    # ----- ⑦ 과최적화 -----
    log("=" * 60)
    log("⑦ 파라미터 스윕(1~24개월, 비용 0.3%) 및 홀드아웃")
    log("=" * 60)

    def bt(lookback, start=None, end=None, cost=0.003):
        _, n, _ = momentum(monthly, lookback, cost)
        n = n.dropna()
        if start is not None:
            n = n[n.index >= start]
        if end is not None:
            n = n[n.index <= end]
        if len(n) == 0:
            return np.nan
        return (1 + n).cumprod().iloc[-1] ** (12 / len(n)) - 1

    sweep = pd.Series({lb: bt(lb) for lb in range(1, 25)})
    sweep.index.name = "lookback(months)"
    log("전체 기간 CAGR by lookback:")
    log(sweep.round(4).to_string())
    log(f"→ 전체 기간 최고: {sweep.idxmax()}개월 (CAGR {sweep.max():.2%})")
    MID = "2015-12-31"
    ins = pd.Series({lb: bt(lb, end=MID) for lb in range(1, 25)})
    best = ins.idxmax()
    log(f"홀드아웃: 전반부(~{MID}) 최적 = {best}개월, 전반부 CAGR {ins.max():.2%}")
    log(f"          그 파라미터의 후반부 CAGR = {bt(best, start=MID):.2%}")
    log(f"          비교: 12개월의 후반부 CAGR = {bt(12, start=MID):.2%}")
    log(f"          비교: Buy&Hold 후반부 CAGR = {cagr_of(returns[returns.index > MID]):.2%}")
    log()

    # ----- ⑧ 위험 지표 종합 -----
    log("=" * 60)
    log("⑧ 위험 지표 종합 (무위험수익률 3% 가정)")
    log("=" * 60)
    summ8 = pd.DataFrame({
        "Buy & Hold": performance_summary(res6["Buy & Hold"]),
        "Momentum (net)": performance_summary(res6["Momentum (net)"]),
    })
    log(summ8.round(4).to_string())
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(11, 5))
        (1 + res6).cumprod().plot(ax=ax, title="Absolute Momentum vs Buy & Hold (KOSPI)")
        ax.set_ylabel("Growth of 1")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "01_cumulative.png"), dpi=120); plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 3.5))
        dd, _, _ = drawdown_stats((1 + res6["Momentum (net)"]).cumprod())
        dd_bh, _, _ = drawdown_stats((1 + res6["Buy & Hold"]).cumprod())
        pd.DataFrame({"Buy & Hold": dd_bh, "Momentum (net)": dd}).plot(ax=ax, title="Drawdown")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "02_drawdown.png"), dpi=120); plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 4))
        sweep.plot(kind="bar", ax=ax, title="CAGR by Lookback (months), cost 0.3%")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "03_lookback_sweep.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/01_cumulative.png, 02_drawdown.png, 03_lookback_sweep.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/results.txt")


if __name__ == "__main__":
    main()
