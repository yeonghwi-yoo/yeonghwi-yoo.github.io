"""
멀티팩터 — 팩터를 섞는 방법들 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python scripts/multifactor.py

데이터:
  - Fama-French 5팩터 월별 수익률 (quality_factor.py 가 읽는 파일).
    SMB(사이즈) HML(밸류) RMW(퀄리티) CMA(투자) + 시장·무위험.
  - 모멘텀(Mom) 월별 수익률. 공개 저장소의 프렌치 교수 데이터 사본.
결과: scripts/output/multifactor_results.txt 와 차트 PNG
(--synthetic 옵션을 주면 실제 데이터 대신 난수 데이터로 동작 확인만 한다)
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quality_factor import load as load_ff5

MOM_URL = ("https://raw.githubusercontent.com/a91quaini/intrinsicFRP/main/"
           "data-raw/F-F_Momentum_Factor.CSV")
STYLE = ["SMB", "HML", "RMW", "CMA", "MOM"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


def load_momentum(synthetic=False):
    """모멘텀 팩터 월별 수익률(소수)."""
    if synthetic:
        rng = np.random.default_rng(2)
        idx = pd.date_range("1927-01-31", "2023-12-31", freq="ME")
        return pd.Series(rng.normal(0.006, 0.04, len(idx)), index=idx, name="MOM")

    df = pd.read_csv(MOM_URL)
    df.columns = [c.strip() for c in df.columns]
    df = df[df["Date"].astype(str).str.len() == 6]
    df.index = pd.to_datetime(df.pop("Date").astype(str), format="%Y%m") + pd.offsets.MonthEnd(0)
    return (df.iloc[:, 0].astype(float) / 100.0).rename("MOM")


def ann(x):
    return (1 + x).prod() ** (12 / len(x)) - 1


def mdd(x):
    cum = (1 + x).cumprod()
    return (cum / cum.cummax() - 1).min()


def underwater(x):
    """최장 침체 기간(개월)."""
    cum = (1 + x).cumprod()
    run = longest = 0
    for f in (cum < cum.cummax()):
        run = run + 1 if f else 0
        longest = max(longest, run)
    return longest


def stats(x):
    return pd.Series({
        "연평균": ann(x),
        "연변동성": x.std() * np.sqrt(12),
        "샤프": x.mean() / x.std() * np.sqrt(12),
        "MDD": mdd(x),
        "t값": x.mean() / x.std() * np.sqrt(len(x)),
        "최장침체(개월)": underwater(x),
    })


def max_sharpe_weights(r):
    """비음수 제약 최대샤프 가중치. 음수가 나오면 그 팩터를 빼고 다시 푼다."""
    cols = list(r.columns)
    while cols:
        mu = r[cols].mean().values
        cov = r[cols].cov().values
        w = np.linalg.solve(cov, mu)
        if w.sum() <= 0:
            break
        w = w / w.sum()
        if (w >= -1e-9).all():
            return pd.Series(w, index=cols).reindex(r.columns).fillna(0.0)
        cols.pop(int(np.argmin(w)))
    n = r.shape[1]
    return pd.Series(np.ones(n) / n, index=r.columns)


def main():
    synthetic = "--synthetic" in sys.argv
    ff = load_ff5(synthetic)
    mom = load_momentum(synthetic)
    d = ff.join(mom, how="inner").dropna()
    r = d[STYLE]
    log(f"데이터: {'합성' if synthetic else 'Fama-French 5팩터 + 모멘텀(월별)'}, "
        f"{d.index[0]:%Y-%m} ~ {d.index[-1]:%Y-%m}, {len(d)}개월")
    log()

    # ----- 1. 개별 팩터 -----
    log("=" * 74)
    log("1. 팩터 하나씩 (롱숏 포트폴리오, 연율)")
    log("=" * 74)
    tab = pd.DataFrame({c: stats(r[c]) for c in STYLE})
    tab["시장-무위험"] = stats(d["Mkt-RF"])
    log(tab.round(4).to_string())
    log()

    # ----- 2. 상관계수 -----
    log("=" * 74)
    log("2. 팩터 사이 상관계수")
    log("=" * 74)
    log(r.corr().round(2).to_string())
    log()
    off = r.corr().values[np.triu_indices(len(STYLE), 1)]
    log(f"  평균 상관계수 {off.mean():+.2f} (최소 {off.min():+.2f}, 최대 {off.max():+.2f})")
    log()

    # ----- 3. 균등 혼합 -----
    log("=" * 74)
    log("3. 다섯 팩터를 균등하게 섞으면")
    log("=" * 74)
    eq = r.mean(axis=1)
    cmp_tab = pd.DataFrame({"최고 샤프 개별": stats(r[tab.loc["샤프", STYLE].idxmax()]),
                            "균등 혼합": stats(eq)})
    log(cmp_tab.round(4).to_string())
    log()
    best = tab.loc["샤프", STYLE].idxmax()
    log(f"  개별 최고는 {best} (샤프 {tab.loc['샤프', best]:.2f}), 균등 혼합은 {stats(eq)['샤프']:.2f}")
    log(f"  혼합 수익률은 개별 평균 {r.mean().mean()*12:.2%} 수준인데, "
        f"변동성이 개별 평균 {(r.std()*np.sqrt(12)).mean():.1%} -> {eq.std()*np.sqrt(12):.1%} 로 줄었다")
    log()

    # ----- 4. 가중 방식 -----
    log("=" * 74)
    log("4. 비중을 어떻게 줄 것인가 (전체 기간 기준)")
    log("=" * 74)
    inv_vol = (1 / r.std()) / (1 / r.std()).sum()
    w_opt = max_sharpe_weights(r)
    schemes = {
        "균등": pd.Series(1 / len(STYLE), index=STYLE),
        "변동성 역가중": inv_vol,
        "최대샤프(전체기간)": w_opt,
    }
    for name, w in schemes.items():
        port = (r * w).sum(axis=1)
        s = stats(port)
        ws = " ".join(f"{k} {v:.0%}" for k, v in w.items())
        log(f"  {name:20s} 연평균 {s['연평균']:+6.2%}  변동성 {s['연변동성']:5.1%}  "
            f"샤프 {s['샤프']:.2f}")
        log(f"  {'':20s} 비중: {ws}")
    log()

    # ----- 5. 워크포워드 -----
    log("=" * 74)
    log("5. 최대샤프 가중치를 '그 시점까지의 데이터'로만 구하면 (워크포워드)")
    log("=" * 74)
    start_year = d.index[0].year + 10
    rows = []
    for y in range(start_year, d.index[-1].year + 1):
        past = r.loc[:f"{y-1}"]
        fut = r.loc[f"{y}"]
        if len(past) < 120 or len(fut) == 0:
            continue
        w = max_sharpe_weights(past)
        rows.append(pd.DataFrame({"wf": (fut * w).sum(axis=1),
                                  "eq": fut.mean(axis=1)}))
    wf = pd.concat(rows)
    log(f"  적용 구간: {wf.index[0]:%Y-%m} ~ {wf.index[-1]:%Y-%m} ({len(wf)}개월)")
    log(pd.DataFrame({"워크포워드 최적화": stats(wf["wf"]),
                      "균등 (같은 구간)": stats(wf["eq"])}).round(4).to_string())
    log()
    ins = (r.loc[wf.index[0]:] * w_opt).sum(axis=1)
    log(f"  참고) 전체 기간을 미리 보고 정한 최대샤프 가중치를 같은 구간에 적용하면 "
        f"샤프 {stats(ins)['샤프']:.2f}")
    log("  -> 미래를 본 가중치와 실제로 구할 수 있었던 가중치의 차이가 과최적화의 크기다")
    log()

    # ----- 6. 구간별 -----
    log("=" * 74)
    log("6. 10년 단위로 (연평균)")
    log("=" * 74)
    log(f"  {'연대':8s}" + "".join(f"{c:>9s}" for c in STYLE) + f"{'균등혼합':>11s}")
    for d0 in range(1970, d.index[-1].year + 1, 10):
        seg = r.loc[f"{d0}":f"{d0+9}"]
        if len(seg) < 24:
            continue
        log(f"  {d0}s{'':4s}" + "".join(f"{ann(seg[c]):>9.1%}" for c in STYLE)
            + f"{ann(seg.mean(axis=1)):>11.1%}")
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GREEN, GRAY = "#1f5fbf", "#c45f00", "#1f8a70", "#9a9a9a"

        # 20: 개별 팩터와 균등 혼합 누적
        fig, ax = plt.subplots(figsize=(11, 4.8))
        ends = {}
        for c in STYLE:
            cum_c = (1 + r[c]).cumprod()
            ax.plot(r.index, cum_c, color=GRAY, linewidth=1.1)
            ends[c] = cum_c.iloc[-1]
        # 끝값이 가까운 이름표가 겹치지 않도록 로그축에서 최소 간격을 준다
        ypos, prev = {}, None
        for c, v in sorted(ends.items(), key=lambda kv: -kv[1]):
            y = v if prev is None else min(v, prev / 1.16)
            ypos[c], prev = y, y
        for c in STYLE:
            ax.annotate(c, (r.index[-1], ypos[c]), xytext=(6, -3),
                        textcoords="offset points", color=GRAY, fontsize=8)
        ax.plot(eq.index, (1 + eq).cumprod(), color=BLUE, linewidth=2.2,
                label="equal-weight mix")
        ax.set_yscale("log")
        ax.set_ylabel("Growth of 1 (log scale)")
        ax.set_title("The mix is smoother than any single factor")
        ax.legend(frameon=False, loc="upper left")
        ax.grid(alpha=0.3, which="both")
        ax.set_xlim(r.index[0], r.index[-1] + pd.Timedelta(days=1500))
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "20_factor_mix.png"), dpi=120); plt.close(fig)

        # 21: 낙폭 비교
        fig, ax = plt.subplots(figsize=(11, 4))
        for s, c, lab, lw in [(r[best], ORANGE, f"{best} alone", 1.4),
                              (eq, BLUE, "equal-weight mix", 1.8)]:
            cum = (1 + s).cumprod()
            ax.plot(s.index, (cum / cum.cummax() - 1) * 100, color=c, linewidth=lw, label=lab)
        ax.set_ylabel("Drawdown (%)")
        ax.set_title("Mixing cuts the depth of the holes, it does not remove them")
        ax.legend(frameon=False, loc="lower left")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "21_mix_drawdown.png"), dpi=120); plt.close(fig)

        # 22: 워크포워드 vs 균등
        fig, ax = plt.subplots(figsize=(11, 4))
        for col, c, lab in [("eq", BLUE, "equal weight"),
                            ("wf", ORANGE, "walk-forward max-Sharpe weights")]:
            ax.plot(wf.index, (1 + wf[col]).cumprod(), color=c, linewidth=1.7, label=lab)
        ax.set_yscale("log")
        ax.set_ylabel("Growth of 1 (log scale)")
        ax.set_title("Optimized weights did not beat simply splitting it evenly")
        ax.legend(frameon=False, loc="upper left")
        ax.grid(alpha=0.3, which="both")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "22_walkforward_weights.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/20_factor_mix.png, 21_mix_drawdown.png, 22_walkforward_weights.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "multifactor_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/multifactor_results.txt")


if __name__ == "__main__":
    main()
