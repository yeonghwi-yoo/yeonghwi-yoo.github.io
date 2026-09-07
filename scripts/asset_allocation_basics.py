"""
자산 배분 기초 — 주식과 채권을 섞는 이유 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python scripts/asset_allocation_basics.py

데이터: Robert Shiller 교수가 공개하는 미국 월별 데이터(S&P500 지수, 배당, 10년물 국채 금리).
        datasets/s-and-p-500 저장소가 CSV로 정리해 둔 것을 그대로 읽는다.
결과:   scripts/output/alloc_results.txt 와 차트 PNG
(--synthetic 옵션을 주면 실제 데이터 대신 난수 데이터로 동작 확인만 한다)
"""
import os
import sys
import numpy as np
import pandas as pd

URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
START = "1950-01-01"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


# ---------- 데이터 ----------
def load(synthetic=False):
    if synthetic:
        rng = np.random.default_rng(0)
        idx = pd.date_range("1950-01-01", "2026-08-01", freq="MS")
        px = 100 * np.cumprod(1 + rng.normal(0.006, 0.04, len(idx)))
        y = np.clip(4 + np.cumsum(rng.normal(0, 0.15, len(idx))), 0.5, 15)
        return pd.DataFrame({"SP500": px, "Dividend": px * 0.03,
                             "Long Interest Rate": y}, index=idx)
    df = pd.read_csv(URL, parse_dates=["Date"], index_col="Date")
    df = df[["SP500", "Dividend", "Long Interest Rate"]].dropna()
    return df[df.index >= START]


def stock_returns(df):
    """지수 가격 변화 + 배당. Dividend 열은 '연율화된 최근 12개월 주당 배당'이므로 12로 나눈다."""
    p, d = df["SP500"], df["Dividend"]
    return ((p + d / 12) / p.shift(1) - 1).dropna()


def bond_returns(df, maturity=10):
    """10년 만기 국채를 한 달 보유한 수익률 근사.

    지난달 금리로 발행된(액면가 100, 표면금리 = 지난달 금리) 채권을
    이번 달 금리로 다시 평가한 가격 변화 + 한 달치 이자.
    """
    y = df["Long Interest Rate"] / 100
    c, ynew = y.shift(1), y
    price = c * (1 - (1 + ynew) ** -maturity) / ynew + (1 + ynew) ** -maturity
    return (price - 1 + c / 12).dropna()


# ---------- 지표 ----------
def drawdown(cum):
    return cum / cum.cummax() - 1


def longest_underwater(dd):
    longest = run = 0
    for flag in (dd < 0):
        run = run + 1 if flag else 0
        longest = max(longest, run)
    return longest


def summary(r, rf_annual=0.03):
    cum = (1 + r).cumprod()
    years = len(r) / 12
    cagr = cum.iloc[-1] ** (1 / years) - 1
    vol = r.std() * np.sqrt(12)
    dd = drawdown(cum)
    rf = (1 + rf_annual) ** (1 / 12) - 1
    ex = r - rf
    return pd.Series({
        "CAGR": cagr,
        "Volatility": vol,
        "MDD": dd.min(),
        "Sharpe": ex.mean() / ex.std() * np.sqrt(12),
        "Calmar": cagr / abs(dd.min()),
        "Longest DD (months)": longest_underwater(dd),
    })


def main():
    synthetic = "--synthetic" in sys.argv
    df = load(synthetic)
    stock = stock_returns(df).rename("Stock")
    bond = bond_returns(df).rename("Bond")
    r = pd.concat([stock, bond], axis=1).dropna()
    log(f"데이터: {'합성' if synthetic else 'S&P500 + 미국 10년물'}, "
        f"{r.index[0]:%Y-%m} ~ {r.index[-1]:%Y-%m}, {len(r)}개월")
    log()

    # ----- 1. 주식/채권 비중별 성과 (매월 리밸런싱) -----
    weights = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]
    mixes = {}
    for w in weights:
        mixes[f"{round(w*100)}/{round((1-w)*100)}"] = w * r["Stock"] + (1 - w) * r["Bond"]
    mixes = pd.DataFrame(mixes)
    table = pd.DataFrame({k: summary(v) for k, v in mixes.items()})
    log("=" * 60)
    log("1. 주식/채권 비중별 성과 (매월 리밸런싱, 무위험수익률 3% 가정)")
    log("=" * 60)
    log(table.round(4).to_string())
    log()

    # ----- 2. 분산 효과: 포트폴리오 변동성 vs 가중평균 변동성 -----
    vs, vb = table.loc["Volatility", "100/0"], table.loc["Volatility", "0/100"]
    corr = r["Stock"].corr(r["Bond"])
    log("=" * 60)
    log("2. 60/40 의 변동성은 왜 가중평균보다 낮은가")
    log("=" * 60)
    log(f"주식 변동성 {vs:.4f}, 채권 변동성 {vb:.4f}, 전체 기간 상관계수 {corr:.3f}")
    log(f"가중평균 변동성(0.6*주식 + 0.4*채권): {0.6*vs + 0.4*vb:.4f}")
    log(f"실제 60/40 변동성:                    {table.loc['Volatility', '60/40']:.4f}")
    log()

    # ----- 3. 기간별 상관계수와 2022년 -----
    log("=" * 60)
    log("3. 기간별 주식-채권 상관계수 (월간 수익률)")
    log("=" * 60)
    periods = [("1950-01", "1999-12"), ("2000-01", "2021-12"), ("2022-01", "2022-12"),
               ("2023-01", str(r.index[-1])[:7])]
    for a, b in periods:
        sub = r.loc[a:b]
        if len(sub) > 3:
            log(f"{a} ~ {b}: 상관계수 {sub['Stock'].corr(sub['Bond']):+.3f}  "
                f"(주식 {(1+sub['Stock']).prod()-1:+.1%}, 채권 {(1+sub['Bond']).prod()-1:+.1%}, "
                f"60/40 {(1+mixes.loc[a:b, '60/40']).prod()-1:+.1%})")
    log()

    # 60/40 의 역대 낙폭 상위
    dd6040 = drawdown((1 + mixes["60/40"]).cumprod())
    log("60/40 의 역대 최대 낙폭 시점:")
    troughs = dd6040[dd6040 < -0.15]
    if len(troughs):
        # 연도별 최저점만
        by_year = troughs.groupby(troughs.index.year).min()
        for yr, v in by_year.items():
            log(f"  {yr}: {v:.1%}")
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GREEN, GRAY = "#1f5fbf", "#c45f00", "#1f8a70", "#9a9a9a"

        # 04: 위험-수익 곡선
        fig, ax = plt.subplots(figsize=(8, 5.5))
        x = table.loc["Volatility"] * 100
        y = table.loc["CAGR"] * 100
        ax.plot(x, y, color=GRAY, linewidth=1.5, zorder=1)
        colors = {"100/0": BLUE, "0/100": ORANGE, "60/40": GREEN}
        for name in table.columns:
            ax.scatter(x[name], y[name], s=70, color=colors.get(name, GRAY), zorder=2)
            ax.annotate(name, (x[name], y[name]), textcoords="offset points",
                        xytext=(8, -3), fontsize=10)
        ax.set_xlabel("Annual volatility (%)")
        ax.set_ylabel("CAGR (%)")
        ax.set_title(f"Stock/Bond mixes, monthly rebalanced ({r.index[0]:%Y}-{r.index[-1]:%Y})")
        ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "04_risk_return.png"), dpi=120); plt.close(fig)

        # 05: 낙폭 비교
        fig, ax = plt.subplots(figsize=(11, 3.8))
        dd100 = drawdown((1 + mixes["100/0"]).cumprod())
        ax.fill_between(dd100.index, dd100 * 100, 0, color=BLUE, alpha=0.25, linewidth=0)
        ax.plot(dd100.index, dd100 * 100, color=BLUE, linewidth=1.2, label="100/0 (stocks only)")
        ax.plot(dd6040.index, dd6040 * 100, color=GREEN, linewidth=1.5, label="60/40")
        ax.set_ylabel("Drawdown (%)")
        ax.set_title("Drawdown: stocks only vs 60/40")
        ax.legend(loc="lower left", frameon=False)
        ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "05_drawdown_6040.png"), dpi=120); plt.close(fig)

        # 06: 36개월 이동 상관계수
        fig, ax = plt.subplots(figsize=(11, 3.8))
        roll = r["Stock"].rolling(36).corr(r["Bond"])
        ax.axhline(0, color=GRAY, linewidth=1)
        ax.plot(roll.index, roll, color=BLUE, linewidth=1.5)
        ax.set_ylabel("Correlation")
        ax.set_ylim(-1, 1)
        ax.set_title("Rolling 36-month correlation: stock vs bond monthly returns")
        ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "06_rolling_corr.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/04_risk_return.png, 05_drawdown_6040.png, 06_rolling_corr.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "alloc_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/alloc_results.txt")


if __name__ == "__main__":
    main()
