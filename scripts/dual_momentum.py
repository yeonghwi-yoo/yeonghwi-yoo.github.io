"""
듀얼 모멘텀 — 상대와 절대를 결합하기 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python scripts/dual_momentum.py

데이터:
  - 미국 주식/채권 월별 수익률: Shiller 데이터 (asset_allocation_basics.py 가 읽는 파일).
  - 무위험수익률(1개월 T-bill): Fama-French 3팩터 파일의 RF.
결과: scripts/output/dual_momentum_results.txt 와 차트 PNG
(--synthetic 옵션을 주면 실제 데이터 대신 난수 데이터로 동작 확인만 한다)
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asset_allocation_basics import load as load_shiller, stock_returns, bond_returns
from value_factor import load as load_ff3

LOOKBACK = 12
COST = 0.001            # 스위치 1회당 편도 0.1%
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


def load(synthetic=False):
    """주식·채권·무위험 월별 수익률을 한 표로."""
    sh = load_shiller(synthetic)
    st = stock_returns(sh)
    bd = bond_returns(sh)
    ff = load_ff3(synthetic)
    d = pd.DataFrame({"stock": st, "bond": bd})
    d.index = d.index + pd.offsets.MonthEnd(0)
    rf = ff["RF"]
    rf.index = rf.index + pd.offsets.MonthEnd(0)
    return d.join(rf.rename("rf"), how="inner").dropna()


def trailing(r, n=LOOKBACK):
    """직전 n개월 누적 수익률. 신호는 그 달 말에 확정되고 다음 달에 적용된다."""
    return (1 + r).rolling(n).apply(np.prod, raw=True) - 1


def prep(base, lb=LOOKBACK):
    """룩백 수익률 열을 붙이고, 계산이 안 되는 앞부분을 잘라낸다."""
    d = base.copy()
    d["st"] = trailing(d["stock"], lb)
    d["bd"] = trailing(d["bond"], lb)
    d["rfm"] = trailing(d["rf"], lb)
    return d.dropna()


def run(d, rule, cost=COST, start=None):
    """rule(t행) -> 'stock' 또는 'bond'. 신호는 한 달 밀어서 적용한다."""
    sig = d.apply(rule, axis=1).shift(1).dropna()
    if start is not None:
        sig = sig[sig.index >= start]
    ret = pd.Series(index=sig.index, dtype=float)
    prev = None
    switches = 0
    for t, pick in sig.items():
        r = d.loc[t, pick]
        if prev is not None and pick != prev:
            r -= cost
            switches += 1
        ret[t] = r
        prev = pick
    return ret, switches


def stats(r, rf=None):
    """샤프는 무위험수익률을 뺀 초과수익 기준으로 계산한다."""
    cum = (1 + r).cumprod()
    dd = cum / cum.cummax() - 1
    run_ = longest = 0
    for f in (dd < 0):
        run_ = run_ + 1 if f else 0
        longest = max(longest, run_)
    ex = r - rf.reindex(r.index) if rf is not None else r
    return pd.Series({
        "연평균": (1 + r).prod() ** (12 / len(r)) - 1,
        "연변동성": r.std() * np.sqrt(12),
        "샤프": ex.mean() / ex.std() * np.sqrt(12),
        "MDD": dd.min(),
        "최장침체(개월)": longest,
    })


def main():
    synthetic = "--synthetic" in sys.argv
    base = load(synthetic)
    d = prep(base, LOOKBACK)
    log(f"데이터: {'합성' if synthetic else '미국 주식(S&P500 총수익) · 10년물 · 1개월 T-bill'}, "
        f"{d.index[0]:%Y-%m} ~ {d.index[-1]:%Y-%m}, {len(d)}개월")
    log(f"룩백 {LOOKBACK}개월, 스위치 1회당 비용 {COST:.1%}")
    log()

    # ----- 전략 정의 -----
    rel = lambda r: "stock" if r["st"] > r["bd"] else "bond"                # 상대 모멘텀
    absm = lambda r: "stock" if r["st"] > r["rfm"] else "bond"              # 절대 모멘텀
    dual = lambda r: ("stock" if (r["st"] > r["bd"] and r["st"] > r["rfm"])
                      else "bond")                                        # 듀얼

    res, sw = {}, {}
    for name, rule in [("상대 모멘텀", rel), ("절대 모멘텀", absm), ("듀얼 모멘텀", dual)]:
        res[name], sw[name] = run(d, rule)
    idx = res["듀얼 모멘텀"].index
    res["주식 100%"] = d.loc[idx, "stock"]
    res["채권 100%"] = d.loc[idx, "bond"]
    res["60/40"] = 0.6 * d.loc[idx, "stock"] + 0.4 * d.loc[idx, "bond"]
    sw.update({"주식 100%": 0, "채권 100%": 0, "60/40": 0})

    order = ["주식 100%", "채권 100%", "60/40", "상대 모멘텀", "절대 모멘텀", "듀얼 모멘텀"]

    log("=" * 74)
    log("1. 전략 비교")
    log("=" * 74)
    tab = pd.DataFrame({k: stats(res[k], d["rf"]) for k in order})
    log(tab.round(4).to_string())
    log()
    log("  스위치 횟수: " + ", ".join(f"{k} {sw[k]}회" for k in order if sw[k]))
    log(f"  (전체 {len(idx)}개월 = {len(idx)/12:.0f}년)")
    log()

    # ----- 2. 주식 비중 -----
    log("=" * 74)
    log("2. 각 전략이 주식에 있었던 기간 비율")
    log("=" * 74)
    for name, rule in [("상대 모멘텀", rel), ("절대 모멘텀", absm), ("듀얼 모멘텀", dual)]:
        s = d.apply(rule, axis=1).shift(1).dropna()
        s = s[s.index >= idx[0]]
        log(f"  {name:10s} 주식 {(s=='stock').mean():.1%}  채권 {(s=='bond').mean():.1%}")
    log()

    # ----- 3. 위기 구간 -----
    log("=" * 74)
    log("3. 위기 구간 누적 수익률")
    log("=" * 74)
    crises = [("1973-01", "1974-12", "1차 오일쇼크"),
              ("2000-03", "2002-09", "IT 거품 붕괴"),
              ("2007-11", "2009-02", "금융위기"),
              ("2020-01", "2020-04", "코로나")]
    log(f"  {'구간':22s}" + "".join(f"{k:>12s}" for k in order))
    for a, b, label in crises:
        seg = {k: res[k].loc[a:b] for k in order}
        if len(seg["듀얼 모멘텀"]) < 2:
            continue
        log(f"  {label:18s}" + "".join(f"{(1+seg[k]).prod()-1:>12.1%}" for k in order))
    log()

    # ----- 4. 10년 단위 -----
    log("=" * 74)
    log("4. 10년 단위 연평균")
    log("=" * 74)
    log(f"  {'연대':8s}" + "".join(f"{k:>12s}" for k in order))
    for y0 in range(1960, d.index[-1].year + 1, 10):
        seg = {k: res[k].loc[f"{y0}":f"{y0+9}"] for k in order}
        if len(seg["듀얼 모멘텀"]) < 24:
            continue
        log(f"  {y0}s{'':3s}" + "".join(
            f"{(1+seg[k]).prod()**(12/len(seg[k]))-1:>12.1%}" for k in order))
    log()

    # ----- 5. 룩백 민감도 -----
    log("=" * 74)
    log("5. 룩백 기간을 바꾸면 (듀얼 모멘텀, 시작 시점을 통일해 비교)")
    log("=" * 74)
    sens = {}
    LBS = [3, 6, 9, 12, 15, 18, 24]
    common = prep(base, max(LBS)).index[1]      # 가장 긴 룩백에 맞춰 시작을 통일한다
    log(f"  (모두 {common:%Y-%m} 부터. 위 표보다 시작이 늦어 수치가 조금 다르다)")
    log(f"  {'룩백':8s}{'연평균':>10s}{'변동성':>9s}{'샤프':>8s}{'MDD':>9s}{'스위치':>8s}")
    for lb in LBS:
        r, n = run(prep(base, lb), dual, start=common)
        s = stats(r, base["rf"])
        sens[lb] = s
        log(f"  {lb:>2d}개월  {s['연평균']:>9.2%}{s['연변동성']:>9.1%}"
            f"{s['샤프']:>8.2f}{s['MDD']:>9.1%}{n:>8d}")
    log()
    vals = [sens[l]["연평균"] for l in sens]
    log(f"  연평균 범위 {min(vals):.2%} ~ {max(vals):.2%} (폭 {max(vals)-min(vals):.2%}p)")
    log()

    # ----- 6. 비용 민감도 -----
    log("=" * 74)
    log("6. 거래 비용을 바꾸면 (듀얼 모멘텀, 룩백 12개월)")
    log("=" * 74)
    for c in [0.0, 0.001, 0.003, 0.005, 0.01]:
        r, n = run(d, dual, cost=c)
        log(f"  편도 {c:.1%}: 연평균 {stats(r, d['rf'])['연평균']:.2%}  (스위치 {n}회)")
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GREEN, GRAY = "#1f5fbf", "#c45f00", "#1f8a70", "#9a9a9a"

        # 23: 누적 수익
        fig, ax = plt.subplots(figsize=(11, 4.8))
        for k, col, lw in [("주식 100%", GRAY, 1.2), ("60/40", GREEN, 1.4),
                           ("듀얼 모멘텀", BLUE, 2.0)]:
            lab = {"주식 100%": "Stocks 100%", "60/40": "60/40",
                   "듀얼 모멘텀": "Dual momentum"}[k]
            ax.plot(idx, (1 + res[k]).cumprod(), color=col, linewidth=lw, label=lab)
        ax.set_yscale("log")
        ax.set_ylabel("Growth of 1 (log scale)")
        ax.set_title("Dual momentum vs holding stocks and vs 60/40")
        ax.legend(frameon=False, loc="upper left")
        ax.grid(alpha=0.3, which="both")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "23_dual_momentum.png"), dpi=120); plt.close(fig)

        # 24: 낙폭
        fig, ax = plt.subplots(figsize=(11, 4))
        for k, col, lw in [("주식 100%", ORANGE, 1.3), ("듀얼 모멘텀", BLUE, 1.7)]:
            lab = "Stocks 100%" if k == "주식 100%" else "Dual momentum"
            cum = (1 + res[k]).cumprod()
            ax.plot(idx, (cum / cum.cummax() - 1) * 100, color=col, linewidth=lw, label=lab)
        ax.set_ylabel("Drawdown (%)")
        ax.set_title("The point of the rule is the bottom of this chart")
        ax.legend(frameon=False, loc="lower left")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "24_dual_drawdown.png"), dpi=120); plt.close(fig)

        # 25: 룩백 민감도
        fig, ax = plt.subplots(figsize=(8.5, 4.2))
        lbs = list(sens.keys())
        ax.plot(lbs, [sens[l]["연평균"] * 100 for l in lbs], color=BLUE,
                marker="o", markersize=8, linewidth=2)
        for l in lbs:
            ax.annotate(f"{sens[l]['연평균']*100:.1f}", (l, sens[l]["연평균"] * 100),
                        textcoords="offset points", xytext=(0, 9), ha="center", fontsize=8.5)
        ax.set_xticks(lbs)
        ax.set_xlabel("Lookback window (months)")
        ax.set_ylabel("Annualized return (%)")
        ax.set_title("Changing the lookback changes the answer")
        ax.grid(alpha=0.3)
        ax.margins(y=0.18)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "25_lookback_sensitivity.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/23_dual_momentum.png, 24_dual_drawdown.png, 25_lookback_sensitivity.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "dual_momentum_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/dual_momentum_results.txt")


if __name__ == "__main__":
    main()
