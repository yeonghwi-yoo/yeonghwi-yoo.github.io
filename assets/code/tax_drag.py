"""
세금과 거래 현실 — 같은 전략이 계좌와 상품에 따라 세후 얼마나 달라지나 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python tax_drag.py
    python tax_drag.py --synthetic     # 난수 데이터로 동작 확인

데이터: Shiller 미국 주식(S&P500 가격+배당)과 Fama-French 무위험수익률 (올웨더 글과 같은 파일)
결과:  output/tax_drag_results.txt 와 차트 PNG

미국 주식에 투자하는 한국 거주자를 가정하고, 두 전략을 네 가지 방식으로 굴린다.
  전략: 매수 후 보유 / 10개월 이동평균(월말 지수가 10개월 평균 위면 보유, 아래면 현금)
  방식:
    세전          세금 없음
    해외 직접     미국 상장 ETF를 일반 계좌에서. 양도차익은 해마다 손익을 합쳐 250만 원 공제 후 22%,
                  배당·이자는 금융소득
    국내 상장     국내 상장 해외지수 ETF를 일반 계좌에서. 매도할 때마다 이익을 배당소득으로 과세(손실 상계 없음),
                  배당·이자와 합쳐 금융소득
    연금 계좌     국내 상장 ETF를 연금저축에서. 중간 과세 없이 끝에 운용수익의 5.5%(연금 수령 가정)
  금융소득은 연 2,000만 원까지 15.4%, 넘으면 종합과세(다른 소득이 없다고 가정한 근사).

단순화: 환율 변동과 매매 비용은 넣지 않는다(세금 효과만 보기 위해). 세금은 해마다 연말에 계좌에서 낸다.
원화 금액은 초기 1억 원 기준이다. 세법은 자주 바뀌므로 실제 적용 전 현행 규정을 확인할 것.
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)

SHILLER = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
START, END = "1972-01", "2020-07"      # 무위험수익률이 있는 구간
YEARS = 20                              # 한 사람의 투자 기간으로 잡은 창 길이
INITIAL = 100_000_000
FIN_THRESHOLD = 20_000_000              # 금융소득종합과세 기준
OVERSEAS_DEDUCTION = 2_500_000          # 해외주식 양도소득 기본공제
OVERSEAS_RATE = 0.22                    # 양도소득세 20% + 지방소득세 2%
FIN_RATE = 0.154                        # 이자·배당소득세 14% + 지방소득세 1.4%
PENSION_RATE = 0.055                    # 연금 수령 시 연금소득세(70세 미만)
BRACKETS = [(14_000_000, 0.06), (50_000_000, 0.15), (88_000_000, 0.24), (150_000_000, 0.35),
            (300_000_000, 0.38), (500_000_000, 0.40), (1_000_000_000, 0.42), (np.inf, 0.45)]
REGIMES = ["세전", "해외 직접", "국내 상장", "연금 계좌"]
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


def load(synthetic=False):
    """월별 가격수익률, 배당수익률, 무위험수익률, 10개월 이동평균 신호."""
    if synthetic:
        rng = np.random.default_rng(5)
        idx = pd.date_range("1971-01-31", "2020-07-31", freq="ME")
        p = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.006, 0.045, len(idx)))), index=idx)
        d = p * 0.03
        rf = pd.Series(0.003, index=idx)
    else:
        from value_factor import load as load_ff3
        sh = pd.read_csv(SHILLER, parse_dates=["Date"], index_col="Date")
        sh = sh[sh["Dividend"] > 0]
        sh.index = sh.index + pd.offsets.MonthEnd(0)
        p, d = sh["SP500"], sh["Dividend"]
        rf = load_ff3()["RF"]
        rf.index = rf.index + pd.offsets.MonthEnd(0)
    df = pd.DataFrame({
        "pr": p / p.shift(1) - 1,
        "dy": d / 12 / p.shift(1),          # Dividend 는 연율화된 12개월 배당
        "rf": rf,
        # 이번 달 말 지수가 10개월 평균 위면 다음 달 보유 → 한 칸 밀어서 '이번 달 보유 여부'로
        "hold": (p > p.rolling(10).mean()).shift(1),
    })
    return df.loc[START:END].dropna()


def progressive(x):
    tax, lo = 0.0, 0.0
    for hi, rate in BRACKETS:
        if x <= lo:
            break
        tax += (min(x, hi) - lo) * rate
        lo = hi
    return tax


def fin_tax(f):
    """연간 금융소득 f 에 대한 세금. 2,000만 원 초과분은 종합과세(다른 소득 없음 가정, 비교과세 반영)."""
    if f <= FIN_THRESHOLD:
        return f * FIN_RATE
    comprehensive = FIN_THRESHOLD * 0.14 + progressive(f - FIN_THRESHOLD)
    return max(comprehensive, f * 0.14) * 1.1


def simulate(win, regime, timing):
    """win: 한 창의 월별 데이터. 끝에 전부 팔았을 때의 세후 금액."""
    v, basis, inside = float(INITIAL), float(INITIAL), True
    fin = gains = 0.0                       # 올해 금융소득, 올해 해외 양도손익 합계
    taxed = regime in ("해외 직접", "국내 상장")

    def realize():
        nonlocal fin, gains
        g = v - basis
        if regime == "해외 직접":
            gains += g
        elif regime == "국내 상장" and g > 0:
            fin += g

    for t, (date, r) in enumerate(win.iterrows()):
        want = bool(r["hold"]) if timing else True
        if t == 0:
            inside = want
        elif want != inside:
            if inside:
                realize()
            inside = want
            basis = v
        if inside:
            div = v * r["dy"]
            v = v * (1 + r["pr"]) + div         # 배당은 재투자, 취득가에 더한다
            basis += div
            fin += div
        else:
            inc = v * r["rf"]
            v += inc
            fin += inc
            basis = v
        last = t == len(win) - 1
        if last and inside:
            realize()                             # 기간 끝에 전부 판다
        if taxed and (date.month == 12 or last):
            tax = fin_tax(fin)
            if regime == "해외 직접":
                tax += max(gains - OVERSEAS_DEDUCTION, 0) * OVERSEAS_RATE
            if inside and not last:
                basis -= basis * tax / v          # 세금만큼 줄어든 평가액에 취득가도 비례해 줄인다
            v -= tax
            fin = gains = 0.0
    if regime == "연금 계좌":
        v -= max(v - INITIAL, 0) * PENSION_RATE
    return v


def cagr(v, years=YEARS):
    return (v / INITIAL) ** (1 / years) - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args()
    df = load(a.synthetic)
    n = YEARS * 12
    starts = [d for d in df.index if d.month == 1 and df.index.get_loc(d) + n <= len(df)]
    log(f"데이터 {df.index[0]:%Y-%m} ~ {df.index[-1]:%Y-%m}, {YEARS}년 창 {len(starts)}개 "
        f"(시작 {starts[0]:%Y-%m} ~ {starts[-1]:%Y-%m}), 초기 {INITIAL:,}원")

    rows = []
    for s in starts:
        i = df.index.get_loc(s)
        win = df.iloc[i:i + n]
        for timing in (False, True):
            for reg in REGIMES:
                rows.append({"start": s.year, "strategy": "10개월 이동평균" if timing else "매수 후 보유",
                             "regime": reg, "final": simulate(win, reg, timing)})
    res = pd.DataFrame(rows)
    res["cagr"] = cagr(res["final"])
    res.to_csv(os.path.join(OUT, "tax_drag_windows.csv"), index=False)

    log("\n[20년 창 세후 CAGR] 중앙값 (최저 ~ 최고)")
    piv = res.pivot_table(index=["strategy", "start"], columns="regime", values="cagr")
    for strat in ["매수 후 보유", "10개월 이동평균"]:
        p = piv.loc[strat]
        log(f"  {strat}")
        for reg in REGIMES:
            log(f"    {reg:<8}{p[reg].median():7.2%}  ({p[reg].min():6.2%} ~ {p[reg].max():6.2%})")
        for reg in REGIMES[1:]:
            drag = (p["세전"] - p[reg])
            log(f"    세금으로 깎인 연수익률 {reg:<8} 중앙값 {drag.median():5.2%}p")

    log("\n[세전으로는 이동평균이 이긴 창에서, 세후에도 이겼나]")
    bh = piv.loc["매수 후 보유"]
    ma = piv.loc["10개월 이동평균"]
    for reg in REGIMES:
        log(f"  {reg:<8} 이동평균 승리 {int((ma[reg] > bh[reg]).sum())}/{len(bh)}개 창")

    log("\n[최종 금액 예시] 단위 백만 원")
    for yr in [1980, 1990, 2000]:
        if yr not in bh.index:
            continue
        sub = res[res["start"] == yr]
        log(f"  {yr}~{yr + YEARS - 1}")
        for strat in ["매수 후 보유", "10개월 이동평균"]:
            s2 = sub[sub["strategy"] == strat].set_index("regime")["final"] / 1e6
            log(f"    {strat:<10}" + "  ".join(f"{reg}:{s2[reg]:7.0f}" for reg in REGIMES))

    # 매수 후 보유를 국내 상장 ETF로 20년 들고 한 번에 팔 때 종합과세의 영향
    log("\n[국내 상장 ETF, 매수 후 보유 20년 뒤 한 번에 매도할 때] 매도 이익과 그 해 세금")
    for yr in [1980, 1990, 2000]:
        if yr not in bh.index:
            continue
        i = df.index.get_loc(pd.Timestamp(f"{yr}-01-31"))
        win = df.iloc[i:i + n]
        v, basis = float(INITIAL), float(INITIAL)
        for _, r in win.iterrows():
            div = v * r["dy"]
            v = v * (1 + r["pr"]) + div
            basis += div
        g = v - basis
        log(f"  {yr}~{yr + YEARS - 1}: 평가액 {v / 1e6:,.0f}백만, 매도 이익 {g / 1e6:,.0f}백만, "
            f"15.4% 분리과세면 {g * FIN_RATE / 1e6:,.0f}백만, 종합과세 반영 {fin_tax(g) / 1e6:,.0f}백만 "
            f"(실효 {fin_tax(g) / g:.1%})")

    with open(os.path.join(OUT, "tax_drag_results.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        colors = {"세전": "#9a9a9a", "해외 직접": "#1f5fbf", "국내 상장": "#b22222", "연금 계좌": "#1f8a70"}
        labels = {"세전": "pre-tax", "해외 직접": "US-listed ETF (22% CGT)",
                  "국내 상장": "KR-listed ETF (div. income tax)", "연금 계좌": "pension account"}
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
        for ax, strat, title in [(axes[0], "매수 후 보유", "Buy & hold"),
                                 (axes[1], "10개월 이동평균", "10-month MA timing")]:
            p = piv.loc[strat]
            for reg in REGIMES:
                ax.plot(p.index, p[reg] * 100, marker="o", markersize=3, linewidth=1.5,
                        color=colors[reg], label=labels[reg])
            ax.set_title(f"{title}: 20-year CAGR by start year")
            ax.set_xlabel("start year"); ax.grid(alpha=0.3)
        axes[0].set_ylabel("CAGR (%)"); axes[0].legend(fontsize=8)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "47_tax_windows.png"), dpi=120); plt.close(fig)
    except ImportError:
        pass


if __name__ == "__main__":
    main()
