"""
리스크 패리티 — 기대수익 없이 위험만으로 비중 정하기 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python risk_parity.py
    python risk_parity.py --synthetic     # 난수 데이터로 동작 확인

데이터: all_weather.py 와 같은 미국 월별 자산 수익률 (stock / long / mid / gold)
        무위험 금리(FF RF)는 2020-07 에 끝난다. 샤프와 레버리지 비용이 필요한 비교는
        거기까지 하고, 2020-08 이후는 무위험 금리 없이 볼 수 있는 것만 본다.
결과:  output/risk_parity_results.txt 와 차트 PNG

비교하는 방식 (모두 매달 직전 36개월 공분산으로 비중을 다시 계산, 매달 리밸런싱)
  1/N        : 25% 씩
  역변동성    : 변동성의 역수에 비례 (상관은 무시하는 단순판)
  ERC        : 위험 기여도가 똑같아지는 비중 (상관까지 반영, Equal Risk Contribution)
  60/40      : 주식 60 / 중기채 40
  ERC 레버리지: ERC 를 60/40 과 같은 변동성이 되도록 빌려서 키운 것 (최대 3배)
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
ASSETS = ["stock", "long", "mid", "gold"]
LOOK = 36            # 공분산 추정 창 (개월)
MAX_LEV = 3.0
RF_END = "2020-07"
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


def erc_weights(cov, iters=500, tol=1e-12):
    """위험 기여도 w_i * (Σw)_i 가 모두 같아지는 비중 (ERC).

    좌표하강법: y_i 하나씩, 이차방정식 Σ_ii y_i² + c_i y_i - 1/n = 0 의 양의 근으로 바꾼다.
    c_i = Σ_{j≠i} Σ_ij y_j. 근의 공식에서 제곱근 안이 항상 양수라 음의 공분산이 있어도 안전하다.
    마지막에 합이 1 이 되도록 나눈다.
    """
    n = len(cov)
    b = 1.0 / n
    y = np.ones(n) / np.sqrt(np.diag(cov))
    for _ in range(iters):
        prev = y.copy()
        for i in range(n):
            c = cov[i] @ y - cov[i, i] * y[i]
            a = cov[i, i]
            y[i] = (-c + np.sqrt(c * c + 4 * a * b)) / (2 * a)
        if np.abs(y - prev).max() < tol * np.abs(y).max():
            break
    return y / y.sum()


def inv_vol_weights(cov):
    iv = 1 / np.sqrt(np.diag(cov))
    return iv / iv.sum()


def risk_contrib(w, cov):
    rc = w * (cov @ w)
    return rc / rc.sum()


def stats(r, rf=None):
    cum = (1 + r).cumprod()
    out = {
        "연평균": (1 + r).prod() ** (12 / len(r)) - 1,
        "연변동성": r.std() * np.sqrt(12),
        "MDD": (cum / cum.cummax() - 1).min(),
    }
    if rf is not None:
        ex = r - rf
        out["샤프"] = ex.mean() / ex.std() * np.sqrt(12)
    return out


def fmt(w):
    return " / ".join(f"{x:>4.0%}" for x in w)


def main():
    synthetic = "--synthetic" in sys.argv
    df = aw.load(synthetic)
    R = df[ASSETS]
    X = R.to_numpy()
    log(f"데이터: {'합성' if synthetic else '미국 월별 자산 수익률'}, "
        f"{df.index[0]:%Y-%m} ~ {df.index[-1]:%Y-%m}, {len(df)}개월 (비중 순서: {' / '.join(ASSETS)})")
    log()

    # ----- 1. 역변동성 vs ERC (전체 기간 공분산) -----
    log("=" * 72)
    log("1. 단순판(역변동성)과 ERC 의 비중·위험 기여도 (전체 기간 공분산으로)")
    log("=" * 72)
    covf = R.cov().to_numpy()
    for name, w in [("1/N", np.full(4, .25)), ("60/40", np.array([.6, 0, .4, 0])),
                    ("역변동성", inv_vol_weights(covf)), ("ERC", erc_weights(covf))]:
        log(f"  {name:6s} 비중 {fmt(w)}   위험 기여 {fmt(risk_contrib(w, covf))}")
    ivw = inv_vol_weights(covf)
    ercw = erc_weights(covf)
    log(f"  채권(장기+중기) 비중: 역변동성 {ivw[1] + ivw[2]:.0%}, ERC {ercw[1] + ercw[2]:.0%}")
    log(f"  채권 위험 기여: 역변동성 {risk_contrib(ivw, covf)[1:3].sum():.0%}, "
        f"ERC {risk_contrib(ercw, covf)[1:3].sum():.0%}")
    log()

    # ----- 2. 매달 다시 계산 -----
    idx = df.index[LOOK:]
    W = {k: pd.DataFrame(index=idx, columns=ASSETS, dtype=float) for k in ["역변동성", "ERC", "ERC 금 제외"]}
    lev = pd.Series(index=idx, dtype=float)
    six = np.array([.6, 0, .4, 0])
    for i in range(LOOK, len(df)):
        c = np.cov(X[i - LOOK:i].T)
        W["역변동성"].iloc[i - LOOK] = inv_vol_weights(c)
        we = erc_weights(c)
        W["ERC"].iloc[i - LOOK] = we
        w3 = erc_weights(c[:3, :3])
        W["ERC 금 제외"].iloc[i - LOOK] = np.r_[w3, 0.0]
        target = np.sqrt(six @ c @ six)
        lev.iloc[i - LOOK] = min(target / np.sqrt(we @ c @ we), MAX_LEV)
    Ri = R.loc[idx]
    rf = df["rf"].loc[idx]
    ret = {
        "1/N": Ri @ np.full(4, .25),
        "역변동성": (Ri * W["역변동성"]).sum(axis=1),
        "ERC": (Ri * W["ERC"]).sum(axis=1),
        "ERC 금 제외": (Ri * W["ERC 금 제외"]).sum(axis=1),
        "60/40": Ri @ six,
    }
    # 레버리지: 빌린 돈에는 무위험 금리를 낸다. 무위험 금리가 없는 구간은 따로 본다.
    lev_ret = lev * ret["ERC"] - (lev - 1) * rf

    log("=" * 72)
    log(f"2. 매달 직전 {LOOK}개월 공분산으로 다시 계산 ({idx[0]:%Y-%m} ~ {RF_END})")
    log("=" * 72)
    sl = slice(idx[0], RF_END)
    tab = pd.DataFrame({k: stats(v.loc[sl], rf.loc[sl]) for k, v in ret.items()}).T
    tab.loc["ERC 레버리지"] = pd.Series(stats(lev_ret.loc[sl], rf.loc[sl]))
    log(tab[["연평균", "연변동성", "샤프", "MDD"]].round(4).to_string())
    log()
    log("  같은 구간 자산별 샤프: " + ", ".join(
        f"{a} {stats(Ri[a].loc[sl], rf.loc[sl])['샤프']:.2f}" for a in ASSETS))
    for k in W:
        log(f"  {k:6s} 평균 비중 {fmt(W[k].loc[sl].mean().to_numpy())}")
    log(f"  레버리지: 평균 {lev.loc[sl].mean():.2f}배, 중앙값 {lev.loc[sl].median():.2f}배, "
        f"최대 {lev.loc[sl].max():.2f}배, 상한({MAX_LEV:.0f}배)에 닿은 달 {(lev.loc[sl] >= MAX_LEV - 1e-9).sum()}개")
    borrow = ((lev.loc[sl] - 1) * rf.loc[sl]).sum()
    log(f"  빌린 돈의 이자로 낸 누적 비용(단순합): {borrow:.1%}")
    log()

    # 위기 구간
    log("  위기 구간 누적 수익")
    crises = [("1987 블랙먼데이", "1987-09", "1987-11"), ("2000~02 IT 거품", "2000-04", "2002-09"),
              ("2007~09 금융위기", "2007-11", "2009-02"), ("2020 코로나", "2020-02", "2020-03")]
    rows = {}
    for name, a, b in crises:
        rows[name] = {k: (1 + v.loc[a:b]).prod() - 1 for k, v in ret.items()}
        rows[name]["ERC 레버리지"] = (1 + lev_ret.loc[a:b]).prod() - 1
    log(pd.DataFrame(rows).T.round(3).to_string())
    log()

    # ----- 3. 무위험 금리 이후 구간 -----
    log("=" * 72)
    log("3. 2020-08 이후 (무위험 금리 없음) 와 2022년")
    log("=" * 72)
    tail = slice("2020-08", None)
    if len(Ri.loc[tail]):
        for k, v in ret.items():
            y22 = (1 + v.loc["2022"]).prod() - 1 if len(v.loc["2022"]) else np.nan
            log(f"  {k:8s}: 2020-08 이후 누적 {(1 + v.loc[tail]).prod() - 1:+.1%}, 2022년 {y22:+.1%}")
        l22 = lev.loc["2022"]
        e22 = ret["ERC"].loc["2022"]
        best = (1 + l22 * e22).prod() - 1       # 이자 0 을 가정한 가장 좋은 경우
        log(f"  ERC 레버리지 2022년: 이자를 0 으로 쳐도 {best:+.1%} (평균 레버리지 {l22.mean():.2f}배)")
        log(f"  주식-장기채 상관: 2000~2020 {R['stock'].loc['2000':'2020'].corr(R['long'].loc['2000':'2020']):+.2f}, "
            f"2021~ {R['stock'].loc['2021':].corr(R['long'].loc['2021':]):+.2f}")
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GREEN, GRAY, RED = "#1f5fbf", "#c45f00", "#1f8a70", "#9a9a9a", "#b22222"

        # 39: 역변동성 vs ERC — 비중과 위험 기여
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
        x = np.arange(4)
        for ax, (title, f) in zip(axes, [("Capital weight", lambda w: w),
                                         ("Risk contribution", lambda w: risk_contrib(w, covf))]):
            ax.bar(x - 0.2, f(ivw) * 100, 0.4, color=GRAY, label="inverse vol")
            ax.bar(x + 0.2, f(ercw) * 100, 0.4, color=BLUE, label="ERC")
            ax.set_xticks(x, ASSETS)
            ax.set_title(title)
            ax.axhline(25, color="black", linewidth=0.8, linestyle=":")
            ax.grid(alpha=0.3, axis="y")
        axes[0].set_ylabel("%")
        axes[0].legend(frameon=False)
        fig.suptitle("Inverse volatility counts the two bonds twice; ERC sees one bond risk")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "39_invvol_vs_erc.png"), dpi=120); plt.close(fig)

        # 40: 누적 (1975 ~ 2020-07)
        fig, ax = plt.subplots(figsize=(11, 4.6))
        for k, c, lab in [("ERC", BLUE, "ERC"), ("60/40", "black", "60/40"),
                          ("1/N", RED, "1/N")]:
            ax.plot((1 + ret[k].loc[sl]).cumprod(), color=c, linewidth=1.6, label=lab)
        ax.plot((1 + lev_ret.loc[sl]).cumprod(), color=ORANGE, linewidth=1.8,
                label="ERC levered to 60/40 volatility")
        ax.set_yscale("log")
        ax.set_ylabel("Growth of 1 (log scale)")
        ax.set_title(f"Monthly re-estimated risk parity, {idx[0]:%Y}-{RF_END[:4]}")
        ax.legend(frameon=False, loc="upper left")
        ax.grid(alpha=0.3, which="both")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "40_risk_parity_cum.png"), dpi=120); plt.close(fig)

        # 41: 레버리지 추이
        fig, ax = plt.subplots(figsize=(11, 3.6))
        ax.plot(lev, color=ORANGE, linewidth=1.4)
        ax.axhline(1, color=GRAY, linewidth=1)
        ax.set_ylabel("Leverage (x)")
        ax.set_title("Leverage needed for ERC to match 60/40 volatility")
        ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "41_rp_leverage.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/39_invvol_vs_erc.png, 40_risk_parity_cum.png, 41_rp_leverage.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "risk_parity_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/risk_parity_results.txt")


if __name__ == "__main__":
    main()
