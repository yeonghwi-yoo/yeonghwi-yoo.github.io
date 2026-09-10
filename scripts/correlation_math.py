"""
상관관계와 분산투자의 수학 (검증 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python scripts/correlation_math.py

데이터: asset_allocation_basics.py 와 동일 (Shiller 미국 월별 데이터).
결과:   scripts/output/corr_results.txt 와 차트 PNG
(--synthetic 옵션을 주면 실제 데이터 대신 난수 데이터로 동작 확인만 한다)
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asset_allocation_basics import load, stock_returns, bond_returns

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


def port_vol(w, s1, s2, rho):
    """두 자산 포트폴리오의 변동성 (공식)"""
    var = (w * s1) ** 2 + ((1 - w) * s2) ** 2 + 2 * w * (1 - w) * rho * s1 * s2
    return np.sqrt(var)


def min_var_weight(s1, s2, rho):
    """변동성이 최소가 되는 자산1 비중"""
    cov = rho * s1 * s2
    return (s2 ** 2 - cov) / (s1 ** 2 + s2 ** 2 - 2 * cov)


def main():
    synthetic = "--synthetic" in sys.argv
    df = load(synthetic)
    r = pd.concat([stock_returns(df).rename("Stock"),
                   bond_returns(df).rename("Bond")], axis=1).dropna()
    log(f"데이터: {'합성' if synthetic else 'S&P500 + 미국 10년물'}, "
        f"{r.index[0]:%Y-%m} ~ {r.index[-1]:%Y-%m}, {len(r)}개월")
    log()

    s1 = r["Stock"].std() * np.sqrt(12)
    s2 = r["Bond"].std() * np.sqrt(12)
    rho = r["Stock"].corr(r["Bond"])

    # ----- 1. 공식이 실제 데이터와 맞는가 -----
    log("=" * 68)
    log("1. 공식 검증 — 계산값 vs 실제 60/40 시계열의 변동성")
    log("=" * 68)
    log(f"주식 변동성 s1 = {s1:.4f}, 채권 변동성 s2 = {s2:.4f}, 상관계수 rho = {rho:.4f}")
    for w in [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]:
        actual = (w * r["Stock"] + (1 - w) * r["Bond"]).std() * np.sqrt(12)
        formula = port_vol(w, s1, s2, rho)
        log(f"  주식 {w:.0%}: 공식 {formula:.5f}, 실제 {actual:.5f}, 차이 {abs(formula-actual):.2e}")
    log()

    # ----- 2. 세 번째 항의 크기 -----
    log("=" * 68)
    log("2. 60/40 분산의 세 항을 분해하면")
    log("=" * 68)
    w = 0.6
    t1 = (w * s1) ** 2
    t2 = ((1 - w) * s2) ** 2
    t3 = 2 * w * (1 - w) * rho * s1 * s2
    total = t1 + t2 + t3
    log(f"  1항 주식 몫      : {t1:.6f}")
    log(f"  2항 채권 몫      : {t2:.6f}")
    log(f"  3항 상호작용     : {t3:+.6f}   <- 상관계수가 들어가는 자리")
    log(f"  합계(분산)       : {total:.6f}  -> 변동성 {np.sqrt(total):.4f}")
    log(f"  가중평균 변동성  : {w*s1 + (1-w)*s2:.4f}  (rho=1 이었다면 나왔을 값)")
    log()

    # ----- 3. 상관계수를 바꿔가며 -----
    log("=" * 68)
    log("3. 상관계수만 바꿨을 때 60/40 변동성 (s1, s2는 실제 값 고정)")
    log("=" * 68)
    for x in [-1.0, -0.5, -0.25, 0.0, rho, 0.25, 0.5, 1.0]:
        tag = "  <- 실제" if abs(x - rho) < 1e-9 else ""
        log(f"  rho = {x:+.3f} -> 변동성 {port_vol(0.6, s1, s2, x):.4f}{tag}")
    log()

    # ----- 4. 최소분산 비중 -----
    log("=" * 68)
    log("4. 변동성이 가장 낮아지는 주식 비중")
    log("=" * 68)
    wmin = min_var_weight(s1, s2, rho)
    log(f"  공식으로 구한 최소분산 비중: 주식 {wmin:.1%} / 채권 {1-wmin:.1%}")
    log(f"  그때 변동성: {port_vol(wmin, s1, s2, rho):.4f} (주식 100%는 {s1:.4f}, 채권 100%는 {s2:.4f})")
    grid = np.linspace(0, 1, 1001)
    vols = np.array([port_vol(x, s1, s2, rho) for x in grid])
    log(f"  격자 탐색으로 확인: 주식 {grid[vols.argmin()]:.1%}, 변동성 {vols.min():.4f}")
    log()

    # ----- 5. 종목을 늘리면 어디까지 줄어드나 -----
    log("=" * 68)
    log("5. 같은 변동성 s, 서로 상관계수 rho 인 자산 N개를 균등 보유하면")
    log("=" * 68)
    s = 0.25
    log(f"  (가정: 개별 자산 변동성 {s:.0%}, 자산 간 상관계수는 아래 각 값)")
    header = "   N |" + "".join(f"  rho={x:+.1f}" for x in [0.0, 0.2, 0.4, 0.6])
    log(header)
    for n in [1, 2, 5, 10, 30, 100, 1000]:
        row = f"  {n:4d}|"
        for x in [0.0, 0.2, 0.4, 0.6]:
            v = s * np.sqrt((1 + (n - 1) * x) / n)
            row += f"   {v:.3f}"
        log(row)
    log("  N을 무한히 늘려도 변동성은 s*sqrt(rho) 아래로 내려가지 않는다:")
    log("   " + ", ".join(f"rho={x:.1f} -> {s*np.sqrt(x):.3f}" for x in [0.0, 0.2, 0.4, 0.6]))
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GREEN, GRAY = "#1f5fbf", "#c45f00", "#1f8a70", "#9a9a9a"

        # 09: rho 에 따른 변동성 곡선
        fig, ax = plt.subplots(figsize=(8, 5))
        rs = np.linspace(-1, 1, 401)
        ax.plot(rs, [port_vol(0.6, s1, s2, x) * 100 for x in rs], color=BLUE, linewidth=2)
        wavg = (0.6 * s1 + 0.4 * s2) * 100
        ax.axhline(wavg, color=GRAY, linewidth=1.2, linestyle="--")
        ax.annotate(f"weighted average {wavg:.1f}%", xy=(-0.95, wavg), xytext=(0, 5),
                    textcoords="offset points", color=GRAY, fontsize=9)
        ax.scatter([rho], [port_vol(0.6, s1, s2, rho) * 100], s=90, color=ORANGE, zorder=3)
        ax.annotate(f"actual  rho={rho:.2f}", (rho, port_vol(0.6, s1, s2, rho) * 100),
                    textcoords="offset points", xytext=(14, 12), fontsize=10, color=ORANGE)
        ax.set_xlabel("Correlation between the two assets")
        ax.set_ylabel("Portfolio volatility (%)")
        ax.set_title("60/40 volatility as correlation changes (asset vols held fixed)")
        ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "09_vol_vs_corr.png"), dpi=120); plt.close(fig)

        # 10: N 을 늘릴 때의 하한선
        fig, ax = plt.subplots(figsize=(9, 5))
        ns = np.arange(1, 101)
        for x, c in [(0.0, BLUE), (0.2, GREEN), (0.4, ORANGE)]:
            v = s * np.sqrt((1 + (ns - 1) * x) / ns) * 100
            ax.plot(ns, v, color=c, linewidth=2, label=f"correlation {x:.1f}")
            floor = s * np.sqrt(x) * 100
            if floor > 0:
                ax.axhline(floor, color=c, linewidth=1, linestyle=":")
        ax.set_xlabel("Number of assets held (equal weight)")
        ax.set_ylabel("Portfolio volatility (%)")
        ax.set_title("Adding assets: volatility falls, but only to a floor set by correlation")
        ax.legend(frameon=False)
        ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "10_diversification_floor.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/09_vol_vs_corr.png, 10_diversification_floor.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "corr_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/corr_results.txt")


if __name__ == "__main__":
    main()
