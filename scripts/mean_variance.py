"""
평균-분산 최적화 — 마코위츠의 효율적 투자선과 그 약점 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python scripts/mean_variance.py
    python scripts/mean_variance.py --synthetic     # 난수 데이터로 동작 확인

데이터: all_weather.py 와 같은 미국 월별 자산 수익률 네 개
        stock(S&P 500 총수익), long(장기채), mid(10년물), gold
        무위험 금리(Fama-French RF)가 2020-07 에 끝나므로 분석도 거기서 끊는다.
결과:  scripts/output/mean_variance_results.txt 와 차트 PNG

scipy 없이 돌도록, 네 자산의 비중을 1% 간격으로 전부 늘어놓고(17만여 개)
그중에서 최소분산·최대샤프를 고른다. 공매도 없음(비중 0~100%).
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
END = "2020-07"
WINDOW = 120          # 워크포워드 추정 창 (개월)
SEED = 20260926
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


def simplex_grid(n_assets=4, step=0.01):
    """비중 합이 1 인 모든 조합 (각 0 이상, step 간격)."""
    k = int(round(1 / step))
    out = []
    for a in range(k + 1):
        for b in range(k + 1 - a):
            for c in range(k + 1 - a - b):
                out.append((a, b, c, k - a - b - c))
    return np.array(out, dtype=float) / k


def port_stats(W, mu, cov):
    """비중 행렬 W (N x 4) 의 월평균·월변동성."""
    m = W @ mu
    v = np.einsum("ij,jk,ik->i", W, cov, W)
    return m, np.sqrt(np.maximum(v, 0))


def pick(W, mu, cov, rf):
    """최소분산과 최대샤프(초과수익 기준) 비중."""
    m, s = port_stats(W, mu, cov)
    i_mv = int(np.argmin(s))
    i_ms = int(np.argmax((m - rf) / s))
    return W[i_mv], W[i_ms]


def fmt_w(w):
    return " / ".join(f"{a} {x:>4.0%}" for a, x in zip(ASSETS, w))


def perf(r, rf):
    cum = (1 + r).cumprod()
    ex = r - rf
    return {
        "연평균": (1 + r).prod() ** (12 / len(r)) - 1,
        "연변동성": r.std() * np.sqrt(12),
        "샤프": ex.mean() / ex.std() * np.sqrt(12),
        "MDD": (cum / cum.cummax() - 1).min(),
    }


def main():
    synthetic = "--synthetic" in sys.argv
    rng = np.random.default_rng(SEED)
    df = aw.load(synthetic)
    df = df.loc[:END].dropna()
    R = df[ASSETS]
    rf = df["rf"]
    log(f"데이터: {'합성' if synthetic else '미국 월별 자산 수익률'}, "
        f"{df.index[0]:%Y-%m} ~ {df.index[-1]:%Y-%m}, {len(df)}개월")
    log()

    W = simplex_grid()
    log(f"후보 포트폴리오: 1% 간격으로 {len(W):,}개")
    log()

    mu, cov, rfm = R.mean().to_numpy(), R.cov().to_numpy(), rf.mean()

    # ----- 1. 자산별 -----
    log("=" * 70)
    log("1. 자산별 연율 성과 (전체 기간)")
    log("=" * 70)
    t = pd.DataFrame({a: perf(R[a], rf) for a in ASSETS}).T
    log(t.round(4).to_string())
    log()
    log("  상관계수")
    log(R.corr().round(2).to_string())
    log()

    # ----- 2. 전체 기간으로 최적화 -----
    log("=" * 70)
    log("2. 전체 기간 데이터로 구한 최적 비중 (사후적, 미래를 다 본 결과)")
    log("=" * 70)
    w_mv, w_ms = pick(W, mu, cov, rfm)
    eq = np.full(4, 0.25)
    sixty = np.array([0.6, 0.0, 0.4, 0.0])
    rows = {}
    for name, w in [("최소분산", w_mv), ("최대샤프", w_ms), ("균등 1/N", eq), ("60/40", sixty)]:
        r = R @ w
        rows[name] = perf(r, rf)
        log(f"  {name:8s}: {fmt_w(w)}")
    log()
    log(pd.DataFrame(rows).T.round(4).to_string())
    log()

    # ----- 3. 기대수익 민감도 -----
    log("=" * 70)
    log("3. 기대수익을 조금만 바꾸면 최대샤프 비중이 어떻게 되나")
    log("=" * 70)
    log(f"  기준            : {fmt_w(w_ms)}")
    for asset, bump in [("stock", -0.01), ("stock", +0.01), ("long", +0.005),
                        ("mid", -0.005), ("gold", +0.01), ("gold", -0.01)]:
        mu2 = mu.copy()
        mu2[ASSETS.index(asset)] += bump / 12
        _, w2 = pick(W, mu2, cov, rfm)
        log(f"  {asset:5s} 연 {bump:+.1%}p : {fmt_w(w2)}")
    log()

    # ----- 4. 부트스트랩 -----
    log("=" * 70)
    log("4. 같은 역사를 다시 뽑으면 (부트스트랩 500회, 월 단위 복원추출)")
    log("=" * 70)
    B = 500
    X = R.to_numpy()
    rfv = rf.to_numpy()
    mv_ws, ms_ws = np.empty((B, 4)), np.empty((B, 4))
    for b in range(B):
        idx = rng.integers(0, len(X), len(X))
        xb = X[idx]
        mv_ws[b], ms_ws[b] = pick(W, xb.mean(0), np.cov(xb.T), rfv[idx].mean())
    for name, ws in [("최소분산", mv_ws), ("최대샤프", ms_ws)]:
        log(f"  {name}")
        for j, a in enumerate(ASSETS):
            q = np.percentile(ws[:, j], [5, 50, 95])
            log(f"    {a:5s}: 5% {q[0]:>4.0%}  중앙 {q[1]:>4.0%}  95% {q[2]:>4.0%}  "
                f"(0% 인 경우 {np.mean(ws[:, j] < 0.005):.0%})")
    spread_mv = np.mean([np.percentile(mv_ws[:, j], 95) - np.percentile(mv_ws[:, j], 5) for j in range(4)])
    spread_ms = np.mean([np.percentile(ms_ws[:, j], 95) - np.percentile(ms_ws[:, j], 5) for j in range(4)])
    log(f"  자산별 90% 범위 폭 평균: 최소분산 {spread_mv:.0%}p, 최대샤프 {spread_ms:.0%}p")
    log()

    # ----- 5. 워크포워드 -----
    log("=" * 70)
    log(f"5. 워크포워드: 직전 {WINDOW}개월로 비중을 정하고 1년 운용, 매년 다시")
    log("=" * 70)
    W5 = simplex_grid(step=0.02)          # 속도를 위해 2% 간격
    starts = [i for i in range(WINDOW, len(df)) if df.index[i].month == 1]
    tgt = {k: pd.DataFrame(index=df.index[WINDOW:], columns=ASSETS, dtype=float)
           for k in ["최소분산", "최대샤프"]}
    for s in starts:
        win = X[s - WINDOW:s]
        a, b = pick(W5, win.mean(0), np.cov(win.T), rfv[s - WINDOW:s].mean())
        end = min(s + 12, len(df))
        tgt["최소분산"].iloc[s - WINDOW:end - WINDOW] = a
        tgt["최대샤프"].iloc[s - WINDOW:end - WINDOW] = b
    first = df.index[starts[0]]
    Ro = R.loc[first:]
    rfo = rf.loc[first:]
    res, turn = {}, {}
    for name in ["최소분산", "최대샤프"]:
        w = tgt[name].loc[first:]
        res[name] = (Ro * w).sum(axis=1)
        yearly = w[w.index.month == 1]
        turn[name] = yearly.diff().abs().sum(axis=1).iloc[1:].mean() / 2
    res["균등 1/N"] = Ro @ eq
    res["60/40"] = Ro @ sixty
    turn["균등 1/N"] = turn["60/40"] = 0.0
    log(f"  운용 구간: {first:%Y-%m} ~ {Ro.index[-1]:%Y-%m} ({len(Ro)}개월)")
    tab = pd.DataFrame({k: perf(v, rfo) for k, v in res.items()}).T
    tab["연 회전율"] = pd.Series(turn)
    log(tab.round(4).to_string())
    log()
    avg = {k: tgt[k].loc[first:].mean() for k in tgt}
    for k in tgt:
        log(f"  {k} 평균 비중: {fmt_w(avg[k].to_numpy())}")
    log()

    # ----- 6. 왜 평균은 흔들리고 분산은 버티나 -----
    log("=" * 70)
    log("6. 추정 오차: 평균과 변동성 중 어느 쪽이 더 불확실한가")
    log("=" * 70)
    yrs = len(R) / 12
    for a in ASSETS:
        m = R[a].mean() * 12
        se = R[a].std() * np.sqrt(12) / np.sqrt(yrs)
        log(f"  {a:5s}: 연평균 {m:.2%}, 표준오차 {se:.2%}p, 95% 구간 {m - 1.96 * se:.1%} ~ {m + 1.96 * se:.1%}")
    d = R["long"] - R["mid"]
    log(f"  long - mid 연평균 차이 {d.mean() * 12:+.2%}, 표준오차 {d.std() * np.sqrt(12) / np.sqrt(yrs):.2%}p")
    log(f"  변동성의 상대 표준오차 약 {1 / np.sqrt(2 * len(R)):.1%} (평균보다 훨씬 정확하게 잡힌다)")
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GREEN, GRAY, RED = "#1f5fbf", "#c45f00", "#1f8a70", "#9a9a9a", "#b22222"

        m, s = port_stats(W, mu, cov)
        ann_m, ann_s = (1 + m) ** 12 - 1, s * np.sqrt(12)
        sub = rng.choice(len(W), 20000, replace=False)
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.scatter(ann_s[sub] * 100, ann_m[sub] * 100, s=2, color=GRAY, alpha=0.35,
                   label="all long-only mixes")
        order = np.argsort(ann_s)
        best = np.maximum.accumulate(ann_m[order])
        keep = np.r_[True, np.diff(best) > 1e-9]
        ax.plot(ann_s[order][keep] * 100, best[keep] * 100, color=BLUE, linewidth=2,
                label="efficient frontier")
        for name, w, c, mk in [("min variance", w_mv, GREEN, "o"), ("max Sharpe", w_ms, ORANGE, "*"),
                               ("1/N", eq, RED, "s"), ("60/40", sixty, "black", "D")]:
            mm, ss = port_stats(w[None, :], mu, cov)
            ax.scatter(ss * np.sqrt(12) * 100, ((1 + mm) ** 12 - 1) * 100, color=c, s=110,
                       marker=mk, zorder=5, label=name, edgecolor="white")
        for j, a in enumerate(ASSETS):
            e = np.eye(4)[j]
            mm, ss = port_stats(e[None, :], mu, cov)
            ax.annotate(a, (ss[0] * np.sqrt(12) * 100, ((1 + mm[0]) ** 12 - 1) * 100),
                        xytext=(6, -4), textcoords="offset points", fontsize=10)
        ax.set_xlabel("Annual volatility (%)")
        ax.set_ylabel("Annual return (%)")
        ax.set_title(f"Mean-variance frontier, {df.index[0]:%Y}-{df.index[-1]:%Y}")
        ax.legend(frameon=False, loc="lower right")
        ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "36_frontier.png"), dpi=120); plt.close(fig)

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
        for ax, (name, ws, c) in zip(axes, [("Min variance", mv_ws, GREEN), ("Max Sharpe", ms_ws, ORANGE)]):
            ax.boxplot([ws[:, j] * 100 for j in range(4)], tick_labels=ASSETS, widths=0.55,
                       patch_artist=True, boxprops=dict(facecolor=c, alpha=0.45),
                       medianprops=dict(color="black"), flierprops=dict(markersize=2, alpha=0.4))
            ax.set_title(f"{name}: weights over 500 bootstrap histories")
            ax.grid(alpha=0.3, axis="y")
        axes[0].set_ylabel("Weight (%)")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "37_bootstrap_weights.png"), dpi=120); plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 4.5))
        for name, c in [("최소분산", GREEN), ("최대샤프", ORANGE), ("균등 1/N", RED), ("60/40", "black")]:
            lab = {"최소분산": "min variance", "최대샤프": "max Sharpe",
                   "균등 1/N": "1/N", "60/40": "60/40"}[name]
            ax.plot(res[name].index, (1 + res[name]).cumprod(), color=c, linewidth=1.6, label=lab)
        ax.set_yscale("log")
        ax.set_ylabel("Growth of 1 (log scale)")
        ax.set_title(f"Walk-forward, {WINDOW}-month estimation window, re-estimated every January")
        ax.legend(frameon=False, loc="upper left")
        ax.grid(alpha=0.3, which="both")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "38_mv_walkforward.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/36_frontier.png, 37_bootstrap_weights.png, 38_mv_walkforward.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "mean_variance_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/mean_variance_results.txt")


if __name__ == "__main__":
    main()
