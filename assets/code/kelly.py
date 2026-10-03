"""
켈리 공식과 포지션 사이징 — 얼마나 걸어야 하나 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python kelly.py
    python kelly.py --synthetic     # 난수 데이터로 동작 확인

1) 동전 던지기: 이길 확률 60%, 이기면 건 만큼 얻고 지면 건 만큼 잃는 내기
2) 주식: 미국 S&P 500 총수익 (all_weather.py 와 같은 데이터), 1972-01 ~ 2020-07
   켈리 비율 f* = (평균 초과수익) / 분산. 매달 그 배수로 레버리지를 맞춘다.
   빌린 돈에는 무위험 금리(FF RF)를 낸다.
결과:  output/kelly_results.txt 와 차트 PNG
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import all_weather as aw                                          # noqa: E402

OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)
END = "2020-07"
SEED = 20260928
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


def coin_growth(f, p):
    """한 판당 기대 로그 성장률: p·ln(1+f) + (1-p)·ln(1-f)."""
    f = np.asarray(f, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        g = p * np.log1p(f) + (1 - p) * np.log1p(-f)
    return np.where(f < 1, g, -np.inf)


def simulate_coin(f, p, n_bets, n_paths, rng):
    wins = rng.random((n_paths, n_bets)) < p
    step = np.where(wins, 1 + f, 1 - f)
    return step.prod(axis=1)


def levered(r, rf, L):
    """매달 L 배로 맞춘 포트폴리오의 월 수익. 한 달에 -100% 아래면 파산(-100%)."""
    out = L * r - (L - 1) * rf
    return out.clip(lower=-1.0)


def stats(r):
    w = (1 + r).cumprod()
    busted = bool((w <= 1e-9).any())
    n = len(r)
    return {
        "연평균": (w.iloc[-1] ** (12 / n) - 1) if not busted else -1.0,
        "연변동성": r.std() * np.sqrt(12),
        "MDD": (w / w.cummax() - 1).min(),
        "최악의 달": r.min(),
        "최종 배수": w.iloc[-1],
    }


def main():
    synthetic = "--synthetic" in sys.argv
    rng = np.random.default_rng(SEED)

    # ----- 1. 동전 던지기 -----
    p = 0.60
    fstar = 2 * p - 1
    log("=" * 72)
    log(f"1. 동전 던지기: 이길 확률 {p:.0%}, 1:1 배당. 켈리 비율 f* = 2p-1 = {fstar:.0%}")
    log("=" * 72)
    fs = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60]
    n_bets, n_paths = 1000, 10000
    log(f"  {n_bets}번 걸기, {n_paths:,}개 경로. 시작 자금 1")
    log(f"  {'비율':>5s} {'판당 성장률':>10s} {'중앙값 최종':>14s} {'원금 이상 비율':>12s} {'90% 이상 잃은 비율':>16s}")
    coin_rows = {}
    for f in fs:
        w = simulate_coin(f, p, n_bets, n_paths, rng)
        g = float(coin_growth(f, p))
        coin_rows[f] = (g, np.median(w), (w >= 1).mean(), (w <= 0.1).mean())
        log(f"  {f:>5.0%} {g:>+10.4f} {np.median(w):>14.3g} {(w >= 1).mean():>12.1%} {(w <= 0.1).mean():>16.1%}")
    ev = p * 1 + (1 - p) * (-1)
    log(f"  모든 비율에서 한 판의 기대 수익은 +{ev:.0%} x 건 금액 (산술 기대값은 항상 플러스)")
    log()

    # ----- 2. 주식에 적용 -----
    df = aw.load(synthetic).loc[:END].dropna()
    r, rf = df["stock"], df["rf"]
    ex = r - rf
    mu, var = ex.mean(), r.var()
    kelly = mu / var
    log("=" * 72)
    log(f"2. 주식(S&P 500 총수익)에 켈리를 적용하면 ({df.index[0]:%Y-%m} ~ {df.index[-1]:%Y-%m}, {len(df)}개월)")
    log("=" * 72)
    log(f"  월평균 초과수익 {mu:.4%} (연 {mu * 12:.2%}), 월 분산 {var:.5f} (연변동성 {np.sqrt(var * 12):.2%})")
    log(f"  켈리 배수 f* = 초과수익 / 분산 = {kelly:.2f}배")
    yrs = len(df) / 12
    se = ex.std() * np.sqrt(12) / np.sqrt(yrs)
    lo, hi = mu * 12 - 1.96 * se, mu * 12 + 1.96 * se
    log(f"  연 초과수익의 95% 구간 {lo:.2%} ~ {hi:.2%} -> 켈리 배수 {lo / 12 / var:.2f}배 ~ {hi / 12 / var:.2f}배")
    log()

    Ls = {"1배 (그냥 보유)": 1.0, "절반 켈리": kelly / 2, "켈리": kelly, "켈리 2배": 2 * kelly}
    res = {k: levered(r, rf, L) for k, L in Ls.items()}
    tab = pd.DataFrame({k: stats(v) for k, v in res.items()}).T
    tab.insert(0, "레버리지", pd.Series(Ls))
    log(tab.round(4).to_string())
    log()
    worst = r.idxmin()
    log(f"  최악의 달: {worst:%Y-%m} 주식 {r.min():.1%}. 이 달을 {kelly:.2f}배로 맞으면 "
        f"{kelly * r.min() - (kelly - 1) * rf.loc[worst]:.1%}")
    log(f"  한 달 만에 파산하는 레버리지: {1 / -r.min():.2f}배 이상")
    log()

    # 이론 성장률 곡선 (정규 근사): g(L) = L·mu - L²·var/2 (월)
    Lgrid = np.linspace(0, 2.5 * kelly, 200)
    g_approx = Lgrid * mu - Lgrid ** 2 * var / 2
    log(f"  이론(정규 근사) 월 성장률: 1배 {mu - var / 2:.4%}, 절반 켈리 {kelly / 2 * mu - (kelly / 2) ** 2 * var / 2:.4%}, "
        f"켈리 {mu * kelly / 2:.4%}, 켈리 2배 {2 * kelly * mu - 4 * kelly ** 2 * var / 2:.4%}")
    log("  절반 켈리는 켈리 성장률의 75% 를 절반의 변동성으로 얻는다 (정규 근사에서 정확히 0.75)")
    log()

    # ----- 3. 과거로 추정한 켈리를 쓰면 -----
    log("=" * 72)
    log("3. 매년 직전 10년 데이터로 켈리 배수를 다시 추정해 쓰면 (미래를 모르는 버전)")
    log("=" * 72)
    W = 120
    Lroll = pd.Series(index=df.index, dtype=float)
    for i in range(W, len(df)):
        if df.index[i].month == 1 or i == W:
            win_ex = ex.iloc[i - W:i]
            win_r = r.iloc[i - W:i]
            Lcur = win_ex.mean() / win_r.var()
        Lroll.iloc[i] = Lcur
    Lroll = Lroll.dropna()
    sub_r, sub_rf = r.loc[Lroll.index], rf.loc[Lroll.index]
    roll = {
        "1배": levered(sub_r, sub_rf, 1.0),
        "추정 켈리": (Lroll.clip(lower=0) * sub_r - (Lroll.clip(lower=0) - 1) * sub_rf).clip(lower=-1),
        "추정 켈리 절반": (Lroll.clip(lower=0) / 2 * sub_r - (Lroll.clip(lower=0) / 2 - 1) * sub_rf).clip(lower=-1),
    }
    rt = pd.DataFrame({k: stats(v) for k, v in roll.items()}).T
    log(f"  운용 구간 {Lroll.index[0]:%Y-%m} ~ {Lroll.index[-1]:%Y-%m}")
    log(rt.round(4).to_string())
    yearly = Lroll[Lroll.index.month == 1]
    log(f"  추정 켈리 배수: 최소 {yearly.min():.2f}배 ({yearly.idxmin():%Y}), 최대 {yearly.max():.2f}배 ({yearly.idxmax():%Y}), "
        f"중앙값 {yearly.median():.2f}배")
    log(f"  0배 이하(주식을 아예 안 삼)로 추정된 해: {(yearly <= 0).sum()}개")
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GREEN, GRAY, RED = "#1f5fbf", "#c45f00", "#1f8a70", "#9a9a9a", "#b22222"

        fgrid = np.linspace(0, 0.6, 300)
        fig, ax = plt.subplots(figsize=(11, 4.2))
        ax.plot(fgrid * 100, coin_growth(fgrid, p) * 100, color=BLUE, linewidth=2)
        ax.axhline(0, color=GRAY, linewidth=1)
        ax.axvline(fstar * 100, color=GREEN, linestyle="--", linewidth=1.3, label=f"Kelly {fstar:.0%}")
        ax.axvline(2 * fstar * 100, color=RED, linestyle="--", linewidth=1.3, label=f"2x Kelly {2 * fstar:.0%}")
        ax.set_xlabel("Fraction of wealth bet each time (%)")
        ax.set_ylabel("Expected log growth per bet (%)")
        ax.set_title("60% coin, even odds: growth peaks at 20% and turns negative past 40%")
        ax.legend(frameon=False)
        ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "42_kelly_coin.png"), dpi=120); plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 4.2))
        ax.plot(Lgrid, g_approx * 12 * 100, color=BLUE, linewidth=2, label="point estimate")
        for m_, c_, lab in [(lo / 12, GRAY, "low end of 95% range"), (hi / 12, GRAY, "high end")]:
            ax.plot(Lgrid, (Lgrid * m_ - Lgrid ** 2 * var / 2) * 12 * 100, color=c_,
                    linewidth=1.3, linestyle=":", label=lab)
        ax.axhline(0, color="black", linewidth=0.8)
        for L_, c_, lab in [(1, "black", "1x"), (kelly / 2, GREEN, "half Kelly"),
                            (kelly, ORANGE, "Kelly"), (2 * kelly, RED, "2x Kelly")]:
            ax.axvline(L_, color=c_, linewidth=1.1, linestyle="--")
            ax.text(L_, ax.get_ylim()[1] * 0.92 if L_ < 2 * kelly else ax.get_ylim()[1] * 0.8,
                    f" {lab}", color=c_, fontsize=9)
        ax.set_xlabel("Leverage on stocks (x)")
        ax.set_ylabel("Expected annual log growth (%)")
        ax.set_title("Kelly curve for US stocks: the peak moves a lot with the expected return")
        ax.legend(frameon=False, loc="lower left")
        ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "43_kelly_stock_curve.png"), dpi=120); plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 4.6))
        for (k, v), c in zip(res.items(), ["black", GREEN, ORANGE, RED]):
            w = (1 + v).cumprod().clip(lower=1e-4)
            ax.plot(w.index, w, color=c, linewidth=1.5, label=f"{['1x','half Kelly','Kelly','2x Kelly'][list(res).index(k)]} ({Ls[k]:.2f}x)")
        ax.set_yscale("log")
        ax.set_ylabel("Growth of 1 (log scale)")
        ax.set_title("Leveraged US stocks with hindsight Kelly, monthly rebalanced, 1972-2020")
        ax.legend(frameon=False, loc="upper left")
        ax.grid(alpha=0.3, which="both")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "44_kelly_paths.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/42_kelly_coin.png, 43_kelly_stock_curve.png, 44_kelly_paths.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "kelly_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/kelly_results.txt")


if __name__ == "__main__":
    main()
