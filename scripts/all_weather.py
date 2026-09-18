"""
올웨더 포트폴리오 뜯어보기 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python scripts/all_weather.py

데이터:
  - 미국 주식(S&P500 총수익)·10년물 금리: Shiller 데이터 (asset_allocation_basics.py 와 같은 파일)
  - 금 월별 가격: datasets/gold-prices (LBMA 월평균)
  - 무위험수익률: Fama-French 3팩터 파일의 RF (2020-07 까지)
결과: scripts/output/all_weather_results.txt 와 차트 PNG
(--synthetic 옵션을 주면 실제 데이터 대신 난수 데이터로 동작 확인만 한다)
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asset_allocation_basics import stock_returns, bond_returns
from value_factor import load as load_ff3

SHILLER = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
GOLD = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"
START = "1972-01"            # 금이 달러에 고정돼 있던 시기를 뺀다
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)
lines = []

# 공개된 올웨더 비중: 주식 30 / 장기채 40 / 중기채 15 / 금 7.5 / 원자재 7.5
# 원자재 데이터가 없어 금에 합쳤다 (둘 다 '물가 상승기' 자산으로 묶인 슬리브)
WEIGHTS = {
    "주식 100%": {"stock": 1.0},
    "60/40":     {"stock": 0.6, "mid": 0.4},
    "올웨더 근사": {"stock": 0.30, "long": 0.40, "mid": 0.15, "gold": 0.15},
}


def log(s=""):
    print(s)
    lines.append(str(s))


def load(synthetic=False):
    """월별 수익률: stock / long(20년 만기) / mid(10년 만기) / gold, 그리고 rf."""
    if synthetic:
        rng = np.random.default_rng(3)
        idx = pd.date_range("1972-01-31", "2026-08-31", freq="ME")
        n = len(idx)
        df = pd.DataFrame({
            "stock": rng.normal(0.008, 0.045, n),
            "long": rng.normal(0.005, 0.03, n),
            "mid": rng.normal(0.004, 0.02, n),
            "gold": rng.normal(0.004, 0.05, n),
            "rf": np.full(n, 0.003),
        }, index=idx)
        df.loc["2020-08":, "rf"] = np.nan
        return df

    sh = pd.read_csv(SHILLER, parse_dates=["Date"], index_col="Date")
    sh = sh[["SP500", "Dividend", "Long Interest Rate"]]
    sh = sh[sh.index >= "1950-01-01"]
    # 이 파일은 최근 몇 년의 배당과 10년물 금리를 0 으로 채워 둔다 (아직 집계 전).
    # 금리가 없으면 채권 수익률을 만들 수 없으므로 그 지점에서 데이터를 끊는다.
    sh = sh[(sh["Long Interest Rate"] > 0) & (sh["Dividend"] > 0)]
    df = pd.DataFrame({
        "stock": stock_returns(sh),
        "long": bond_returns(sh, maturity=20),   # 20년물 금리를 따로 못 구해 10년물 금리로 평가
        "mid": bond_returns(sh, maturity=10),
    })
    df.index = df.index + pd.offsets.MonthEnd(0)

    g = pd.read_csv(GOLD)
    g.index = pd.to_datetime(g["Date"], format="%Y-%m") + pd.offsets.MonthEnd(0)
    df["gold"] = g["Price"].pct_change()

    rf = load_ff3()["RF"]
    rf.index = rf.index + pd.offsets.MonthEnd(0)
    df["rf"] = rf
    return df.loc[START:].dropna(subset=["stock", "long", "mid", "gold"])


def portfolio(df, w):
    """매달 목표 비중으로 리밸런싱한 포트폴리오의 월별 수익률."""
    return sum(df[k] * v for k, v in w.items())


def stats(r, rf=None):
    cum = (1 + r).cumprod()
    dd = cum / cum.cummax() - 1
    run = longest = 0
    for f in (dd < 0):
        run = run + 1 if f else 0
        longest = max(longest, run)
    out = {
        "연평균": (1 + r).prod() ** (12 / len(r)) - 1,
        "연변동성": r.std() * np.sqrt(12),
        "MDD": dd.min(),
        "최장침체(개월)": longest,
        "최악의 해": None,
    }
    if rf is not None:
        ex = (r - rf).dropna()
        out["샤프"] = ex.mean() / ex.std() * np.sqrt(12)
    yearly = (1 + r).groupby(r.index.year).prod() - 1
    yearly = yearly[yearly.index > r.index[0].year]      # 첫 해는 부분 연도
    out["최악의 해"] = f"{yearly.idxmin()} ({yearly.min():+.1%})"
    return pd.Series(out)


def risk_contribution(df, w):
    """각 자산이 포트폴리오 변동성에서 차지하는 몫(합이 1)."""
    keys = list(w)
    cov = df[keys].cov().values * 12
    wv = np.array([w[k] for k in keys])
    var = wv @ cov @ wv
    contrib = wv * (cov @ wv) / var
    return dict(zip(keys, contrib)), np.sqrt(var)


def risk_parity(df, keys, iters=500):
    """위험 기여도가 같아지는 비중 (반복 계산)."""
    cov = df[keys].cov().values * 12
    w = np.ones(len(keys)) / len(keys)
    for _ in range(iters):
        marginal = cov @ w
        w = (1 / marginal)
        w = w / w.sum()
    return dict(zip(keys, w))


def main():
    synthetic = "--synthetic" in sys.argv
    df = load(synthetic)
    log(f"데이터: {'합성' if synthetic else '미국 주식·10년/20년물·금 (Shiller + LBMA)'}, "
        f"{df.index[0]:%Y-%m} ~ {df.index[-1]:%Y-%m}, {len(df)}개월")
    log("무위험수익률(FF RF)은 2020-07 까지만 있어 샤프비율은 그 기간으로만 계산")
    log()

    ports = {name: portfolio(df, w) for name, w in WEIGHTS.items()}
    ports["금 100%"] = df["gold"]
    ports["장기채 100%"] = df["long"]

    # ----- 1. 위험 기여도 -----
    log("=" * 74)
    log("1. 자본 비중 vs 위험 기여도 (연율 공분산 기준)")
    log("=" * 74)
    rc = {}
    for name in ["60/40", "올웨더 근사"]:
        contrib, vol = risk_contribution(df, WEIGHTS[name])
        rc[name] = contrib
        log(f"  [{name}]  포트폴리오 변동성 {vol:.1%}")
        for k, v in WEIGHTS[name].items():
            log(f"    {k:6s} 자본 {v:>5.0%}  ->  위험 {contrib[k]:>6.1%}")
        log()

    # ----- 2. 리스크 패리티 비중 -----
    log("=" * 74)
    log("2. 위험 기여도를 똑같이 맞추면 (리스크 패리티)")
    log("=" * 74)
    rp2 = risk_parity(df, ["stock", "mid"])
    log("  주식 + 중기채: " + ", ".join(f"{k} {v:.0%}" for k, v in rp2.items()))
    rp3 = risk_parity(df, ["stock", "long", "gold"])
    log("  주식 + 장기채 + 금: " + ", ".join(f"{k} {v:.0%}" for k, v in rp3.items()))
    log("  (장기채와 중기채는 같은 금리로 평가해 상관이 0.99라 한 자산으로 묶었다)")
    log("  (참고: 올웨더는 stock 30 / 채권 55 / gold 15)")
    log()

    # ----- 3. 성과 (샤프는 RF 있는 구간) -----
    log("=" * 74)
    log("3. 성과 비교 (전체 기간; 샤프는 2020-07 까지)")
    log("=" * 74)
    order = ["주식 100%", "60/40", "올웨더 근사", "장기채 100%", "금 100%"]
    tab = pd.DataFrame({k: stats(ports[k], df["rf"]) for k in order})
    log(tab.to_string())
    log()

    # ----- 4. 10년 단위 -----
    log("=" * 74)
    log("4. 10년 단위 연평균")
    log("=" * 74)
    log(f"  {'연대':8s}" + "".join(f"{k:>12s}" for k in order))
    for y0 in range(1970, df.index[-1].year + 1, 10):
        seg = {k: ports[k].loc[f"{y0}":f"{y0+9}"] for k in order}
        if len(seg["60/40"]) < 24:
            continue
        log(f"  {y0}s{'':3s}" + "".join(
            f"{(1+seg[k]).prod()**(12/len(seg[k]))-1:>12.1%}" for k in order))
    log()

    # ----- 5. 위기 구간 -----
    log("=" * 74)
    log("5. 위기 구간 누적 수익률")
    log("=" * 74)
    crises = [("1973-01", "1974-12", "1차 오일쇼크"),
              ("2000-03", "2002-09", "IT 거품 붕괴"),
              ("2007-11", "2009-02", "금융위기"),
              ("2020-01", "2020-03", "코로나"),
              ("2022-01", "2022-12", "2022 금리 급등")]
    log(f"  {'구간':16s}" + "".join(f"{k:>12s}" for k in order))
    for a, b, label in crises:
        seg = {k: ports[k].loc[a:b] for k in order}
        if len(seg["60/40"]) < 2:
            continue
        log(f"  {label:14s}" + "".join(f"{(1+seg[k]).prod()-1:>12.1%}" for k in order))
    log()

    # ----- 6. 연도별 (최근) -----
    log("=" * 74)
    log("6. 연도별 수익률 2018~ (60/40 vs 올웨더 근사)")
    log("=" * 74)
    yr = {k: (1 + ports[k]).groupby(ports[k].index.year).prod() - 1 for k in ["주식 100%", "60/40", "올웨더 근사"]}
    last = df.index[-1]
    for y in range(2018, last.year + 1):
        tag = f" (~{last:%m}월, 부분 연도)" if y == last.year and last.month < 12 else ""
        log(f"  {y}: " + "  ".join(f"{k} {yr[k].get(y, float('nan')):>+7.1%}" for k in yr) + tag)
    log()

    # ----- 7. 상관계수 -----
    log("=" * 74)
    log("7. 자산 간 상관계수 (월별)")
    log("=" * 74)
    log(df[["stock", "long", "mid", "gold"]].corr().round(2).to_string())
    log()
    for a, b in [("1972", "1999"), ("2000", "2020"), ("2021", None)]:
        seg = df.loc[a:b]
        log(f"  {a}~{b or '끝'} 주식-장기채 {seg['stock'].corr(seg['long']):+.2f}  "
            f"주식-금 {seg['stock'].corr(seg['gold']):+.2f}")
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GREEN, GRAY = "#1f5fbf", "#c45f00", "#1f8a70", "#9a9a9a"
        LAB = {"stock": "Stocks", "long": "Long bonds", "mid": "Mid bonds", "gold": "Gold"}

        # 26: 자본 비중 vs 위험 기여도
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=False)
        for ax, name, title in zip(axes, ["60/40", "올웨더 근사"], ["60/40", "All Weather (approx.)"]):
            keys = list(WEIGHTS[name])
            cap = [WEIGHTS[name][k] * 100 for k in keys]
            risk = [rc[name][k] * 100 for k in keys]
            y = np.arange(len(keys))
            ax.barh(y + 0.18, cap, height=0.34, color=GRAY, label="Capital weight")
            ax.barh(y - 0.18, risk, height=0.34, color=BLUE, label="Risk contribution")
            for yy, c, r in zip(y, cap, risk):
                ax.text(c + 1.5, yy + 0.18, f"{c:.0f}%", va="center", fontsize=8.5, color=GRAY)
                ax.text(r + 1.5, yy - 0.18, f"{r:.0f}%", va="center", fontsize=8.5, color=BLUE)
            ax.set_yticks(y); ax.set_yticklabels([LAB[k] for k in keys])
            ax.invert_yaxis()
            ax.set_xlim(0, 105)
            ax.set_title(title)
            ax.grid(alpha=0.3, axis="x")
        axes[0].legend(frameon=False, loc="lower right", fontsize=9)
        fig.suptitle("Where the risk actually comes from", y=1.0)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "26_risk_contribution.png"), dpi=120, bbox_inches="tight"); plt.close(fig)

        # 27: 누적
        fig, ax = plt.subplots(figsize=(11, 4.8))
        for k, col, lw, lab in [("주식 100%", GRAY, 1.2, "Stocks 100%"), ("60/40", GREEN, 1.4, "60/40"),
                                ("올웨더 근사", BLUE, 2.0, "All Weather (approx.)")]:
            ax.plot(ports[k].index, (1 + ports[k]).cumprod(), color=col, linewidth=lw, label=lab)
        ax.set_yscale("log")
        ax.set_ylabel("Growth of 1 (log scale)")
        ax.set_title("All Weather gives up return for a much smoother ride")
        ax.legend(frameon=False, loc="upper left")
        ax.grid(alpha=0.3, which="both")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "27_all_weather_cumulative.png"), dpi=120); plt.close(fig)

        # 28: 연도별 2018~
        years = [y for y in range(2018, df.index[-1].year + 1)]
        fig, ax = plt.subplots(figsize=(9, 4.2))
        x = np.arange(len(years)); wbar = 0.38
        ax.bar(x - wbar / 2, [yr["60/40"].get(y, 0) * 100 for y in years], wbar, color=GREEN, label="60/40")
        ax.bar(x + wbar / 2, [yr["올웨더 근사"].get(y, 0) * 100 for y in years], wbar, color=BLUE, label="All Weather (approx.)")
        for i, y in enumerate(years):
            for off, k in [(-wbar / 2, "60/40"), (wbar / 2, "올웨더 근사")]:
                v = yr[k].get(y, 0) * 100
                ax.text(i + off, v + (1.2 if v >= 0 else -1.2), f"{v:+.0f}", ha="center",
                        va="bottom" if v >= 0 else "top", fontsize=8)
        ax.axhline(0, color=GRAY, linewidth=1)
        ax.set_xticks(x); ax.set_xticklabels([str(y) + ("*" if y == years[-1] else "") for y in years])
        ax.set_ylabel("Annual return (%)")
        ax.set_title("2022 was the year the bond cushion failed")
        ax.set_xlabel(f"* {years[-1]}: through {df.index[-1]:%B}")
        ax.legend(frameon=False, loc="lower left")
        ax.grid(alpha=0.3, axis="y")
        ax.margins(y=0.2)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "28_yearly_since_2018.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/26_risk_contribution.png, 27_all_weather_cumulative.png, 28_yearly_since_2018.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "all_weather_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/all_weather_results.txt")


if __name__ == "__main__":
    main()
