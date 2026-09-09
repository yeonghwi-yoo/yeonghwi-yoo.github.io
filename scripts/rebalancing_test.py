"""
리밸런싱은 정말 효과가 있을까 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python scripts/rebalancing_test.py

데이터: asset_allocation_basics.py 와 동일 (Shiller 미국 월별 데이터).
결과:   scripts/output/rebal_results.txt 와 차트 PNG
(--synthetic 옵션을 주면 실제 데이터 대신 난수 데이터로 동작 확인만 한다)
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asset_allocation_basics import load, stock_returns, bond_returns, drawdown, longest_underwater

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


def simulate(r, target=0.6, rule="monthly", band=0.05, cost=0.0):
    """비중을 굴려가며 리밸런싱 규칙을 적용한다.

    rule: 'none'(방치) / 'monthly' / 'quarterly' / 'annual' / 'band'(±band 이탈 시)
    cost: 편도 거래 비용 비율. 매매한 금액에만 부과한다.
    반환: (월별 포트폴리오 수익률, 매월 말 주식 비중, 리밸런싱 횟수)
    """
    w = target                      # 현재 주식 비중
    rets, weights, n_rebal = [], [], 0
    for i, (date, row) in enumerate(r.iterrows()):
        # 이번 달 수익률 (직전 말 비중으로 결정)
        gross = w * (1 + row["Stock"]) + (1 - w) * (1 + row["Bond"])
        # 수익률 차이로 비중이 저절로 움직인다(드리프트)
        w_drift = w * (1 + row["Stock"]) / gross

        due = (
            rule == "monthly"
            or (rule == "quarterly" and (i + 1) % 3 == 0)
            or (rule == "annual" and (i + 1) % 12 == 0)
            or (rule == "band" and abs(w_drift - target) > band)
        )
        turnover = abs(w_drift - target) if due else 0.0
        w_new = target if due else w_drift
        if due and turnover > 0:
            n_rebal += 1

        rets.append(gross - 1 - turnover * cost)
        weights.append(w_new)
        w = w_new
    return (pd.Series(rets, index=r.index, name=rule),
            pd.Series(weights, index=r.index, name=rule),
            n_rebal)


def summary(x, rf_annual=0.03):
    cum = (1 + x).cumprod()
    cagr = cum.iloc[-1] ** (12 / len(x)) - 1
    vol = x.std() * np.sqrt(12)
    dd = drawdown(cum)
    rf = (1 + rf_annual) ** (1 / 12) - 1
    ex = x - rf
    return pd.Series({
        "CAGR": cagr,
        "Volatility": vol,
        "MDD": dd.min(),
        "Sharpe": ex.mean() / ex.std() * np.sqrt(12),
        "Longest DD (months)": longest_underwater(dd),
    })


def main():
    synthetic = "--synthetic" in sys.argv
    df = load(synthetic)
    r = pd.concat([stock_returns(df).rename("Stock"),
                   bond_returns(df).rename("Bond")], axis=1).dropna()
    log(f"데이터: {'합성' if synthetic else 'S&P500 + 미국 10년물'}, "
        f"{r.index[0]:%Y-%m} ~ {r.index[-1]:%Y-%m}, {len(r)}개월, 목표 비중 60/40")
    log()

    rules = ["none", "monthly", "quarterly", "annual", "band"]

    # ----- 1. 비용 없을 때 -----
    res, wts, counts = {}, {}, {}
    for rule in rules:
        ret, w, n = simulate(r, rule=rule, cost=0.0)
        res[rule], wts[rule], counts[rule] = ret, w, n
    res = pd.DataFrame(res)
    wts = pd.DataFrame(wts)
    table = pd.DataFrame({k: summary(res[k]) for k in rules})
    log("=" * 68)
    log("1. 리밸런싱 규칙별 성과 (비용 0, 무위험수익률 3% 가정)")
    log("=" * 68)
    log(table.round(4).to_string())
    log()
    log("리밸런싱 횟수: " + ", ".join(f"{k}={counts[k]}회" for k in rules))
    log()

    # ----- 2. 방치했을 때 비중이 어디까지 가나 -----
    log("=" * 68)
    log("2. 방치(none)했을 때 주식 비중의 변화")
    log("=" * 68)
    wn = wts["none"]
    log(f"최소 {wn.min():.1%}, 최대 {wn.max():.1%}, 마지막 {wn.iloc[-1]:.1%}, 평균 {wn.mean():.1%}")
    log("연도별 말 비중(10년 간격):")
    for yr in range(r.index[0].year // 10 * 10 + 10, r.index[-1].year + 1, 10):
        sub = wn[wn.index.year == yr]
        if len(sub):
            log(f"  {yr}년 말: {sub.iloc[-1]:.1%}")
    log()

    # ----- 3. 거래 비용을 넣으면 -----
    log("=" * 68)
    log("3. 거래 비용(편도 0.2%) 반영 시 CAGR")
    log("=" * 68)
    rows = {}
    for rule in rules:
        gross = summary(res[rule])["CAGR"]
        net_ret, _, _ = simulate(r, rule=rule, cost=0.002)
        net = summary(net_ret)["CAGR"]
        rows[rule] = pd.Series({"비용 전": gross, "비용 후": net, "차이(%p)": (net - gross) * 100})
    log(pd.DataFrame(rows).round(4).to_string())
    log()

    # ----- 4. 하락장 구간에서의 차이 -----
    log("=" * 68)
    log("4. 주요 하락장에서 방치 vs 매년 리밸런싱 (누적 수익률)")
    log("=" * 68)
    for a, b, name in [("1973", "1974", "1차 오일쇼크"), ("2000", "2002", "IT 거품 붕괴"),
                       ("2007", "2009", "금융위기"), ("2020", "2020", "코로나"),
                       ("2022", "2022", "인플레이션")]:
        if a > str(r.index[-1].year) or b < str(r.index[0].year):
            continue
        seg = res.loc[a:b]
        if len(seg) < 2:
            continue
        cum = (1 + seg).prod() - 1
        log(f"{name} ({a}~{b}): 방치 {cum['none']:+.1%}, 매년 {cum['annual']:+.1%}, "
            f"매월 {cum['monthly']:+.1%}")
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GREEN, GRAY = "#1f5fbf", "#c45f00", "#1f8a70", "#9a9a9a"

        # 07: 방치 시 주식 비중 표류
        fig, ax = plt.subplots(figsize=(11, 3.8))
        ax.axhline(60, color=GRAY, linewidth=1.2, linestyle="--")
        ax.plot(wn.index, wn * 100, color=BLUE, linewidth=1.5)
        ax.set_ylabel("Stock weight (%)")
        ax.set_title("Never rebalanced: stock weight drifts away from the 60% target")
        ax.annotate("target 60%", xy=(wn.index[len(wn) // 8], 60), xytext=(0, 6),
                    textcoords="offset points", color=GRAY, fontsize=9)
        ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "07_weight_drift.png"), dpi=120); plt.close(fig)

        # 08: 방치 vs 매년 낙폭
        fig, ax = plt.subplots(figsize=(11, 3.8))
        dd_none = drawdown((1 + res["none"]).cumprod()) * 100
        dd_ann = drawdown((1 + res["annual"]).cumprod()) * 100
        ax.fill_between(dd_none.index, dd_none, 0, color=ORANGE, alpha=0.22, linewidth=0)
        ax.plot(dd_none.index, dd_none, color=ORANGE, linewidth=1.3, label="never rebalanced")
        ax.plot(dd_ann.index, dd_ann, color=GREEN, linewidth=1.5, label="annual")
        ax.set_ylabel("Drawdown (%)")
        ax.set_title("Drawdown: never rebalanced vs annual")
        ax.legend(loc="lower left", frameon=False)
        ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "08_rebal_drawdown.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/07_weight_drift.png, 08_rebal_drawdown.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "rebal_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/rebal_results.txt")


if __name__ == "__main__":
    main()
