"""
사이즈 팩터 — 소형주 효과는 살아 있나 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python scripts/size_factor.py

데이터:
  - 시가총액(ME)으로 정렬한 십분위 포트폴리오 월별 수익률 (프렌치 교수 데이터
    라이브러리의 Portfolios_Formed_on_ME, 값가중). 공개 저장소의 사본을 읽는다.
  - SMB(소형주 롱 - 대형주 숏)는 Fama-French 3팩터 / 5팩터 파일.
결과: scripts/output/size_results.txt 와 차트 PNG
(--synthetic 옵션을 주면 실제 데이터 대신 난수 데이터로 동작 확인만 한다)
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from value_factor import load as load_ff3
from quality_factor import load as load_ff5

ME_URL = ("https://raw.githubusercontent.com/a91quaini/reproduceTFRP/main/"
          "data-raw/Portfolios_Formed_on_ME.CSV")
DECILES = ["Lo 10", "Dec 2", "Dec 3", "Dec 4", "Dec 5",
           "Dec 6", "Dec 7", "Dec 8", "Dec 9", "Hi 10"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


def load_size_portfolios(synthetic=False):
    """시가총액 십분위 포트폴리오 월별 수익률(소수)."""
    if synthetic:
        rng = np.random.default_rng(1)
        idx = pd.date_range("1926-07-31", "2024-01-31", freq="ME")
        return pd.DataFrame(
            {c: rng.normal(0.009 - 0.0002 * i, 0.09 - 0.005 * i, len(idx))
             for i, c in enumerate(DECILES)}, index=idx)

    df = pd.read_csv(ME_URL)
    df.columns = [c.strip() for c in df.columns]
    df = df[df["Date"].astype(str).str.len() == 6]
    df.index = pd.to_datetime(df.pop("Date").astype(str), format="%Y%m") + pd.offsets.MonthEnd(0)
    return df.astype(float) / 100.0


def ann(x):
    return (1 + x).prod() ** (12 / len(x)) - 1


def tstat(x):
    return x.mean() / x.std() * np.sqrt(len(x))


def mdd(x):
    cum = (1 + x).cumprod()
    return (cum / cum.cummax() - 1).min()


def regress(y, X):
    """상수항 포함 최소제곱. (알파_연율, 알파t값, 계수들) 반환."""
    A = np.column_stack([np.ones(len(y))] + [X[c].values for c in X.columns])
    coef, *_ = np.linalg.lstsq(A, y.values, rcond=None)
    resid = y.values - A @ coef
    dof = len(y) - A.shape[1]
    s2 = resid @ resid / dof
    se = np.sqrt(np.diag(np.linalg.inv(A.T @ A)) * s2)
    return coef[0] * 12, coef[0] / se[0], dict(zip(X.columns, coef[1:]))


def main():
    synthetic = "--synthetic" in sys.argv
    size = load_size_portfolios(synthetic)
    ff3 = load_ff3(synthetic)
    ff5 = load_ff5(synthetic)

    d = size.join(ff3[["Mkt-RF", "SMB", "RF"]], how="inner").dropna()
    log(f"데이터: {'합성' if synthetic else '시가총액 십분위(값가중) + FF3'}, "
        f"{d.index[0]:%Y-%m} ~ {d.index[-1]:%Y-%m}, {len(d)}개월")
    log()

    # ----- 1. 십분위 -----
    log("=" * 74)
    log("1. 시가총액 십분위 (Lo 10 = 가장 작은 10%, Hi 10 = 가장 큰 10%)")
    log("=" * 74)
    log(f"  {'분위':8s}{'연평균':>9s}{'연변동성':>10s}{'샤프':>7s}{'MDD':>9s}{'베타':>7s}")
    rows = {}
    mkt = d["Mkt-RF"]
    for c in DECILES:
        ex = d[c] - d["RF"]
        beta = np.cov(ex, mkt)[0, 1] / mkt.var()
        rows[c] = dict(ret=ann(d[c]), vol=d[c].std() * np.sqrt(12),
                       sharpe=ex.mean() / ex.std() * np.sqrt(12),
                       mdd=mdd(d[c]), beta=beta)
        r = rows[c]
        log(f"  {c:8s}{r['ret']:>9.2%}{r['vol']:>10.1%}{r['sharpe']:>7.2f}"
            f"{r['mdd']:>9.1%}{r['beta']:>7.2f}")
    lo, hi = rows["Lo 10"], rows["Hi 10"]
    log()
    log(f"  최소분위 - 최대분위: 수익률 {lo['ret']-hi['ret']:+.2%}p, "
        f"변동성 {lo['vol']/hi['vol']:.1f}배, 샤프 {lo['sharpe']:.2f} vs {hi['sharpe']:.2f}")
    log()

    # ----- 2. SMB 장기 -----
    smb = d["SMB"]
    log("=" * 74)
    log("2. SMB (소형 롱 - 대형 숏) 전체 기간")
    log("=" * 74)
    log(f"  연평균 {ann(smb):+.2%}  연변동성 {smb.std()*np.sqrt(12):.1%}  "
        f"t값 {tstat(smb):.2f}  MDD {mdd(smb):.1%}")
    log(f"  비교) 시장-무위험: 연평균 {ann(mkt):+.2%}  t값 {tstat(mkt):.2f}")
    log()

    # ----- 3. 발표 전후 -----
    log("=" * 74)
    log("3. 반즈(1981) 논문 발표 전후")
    log("=" * 74)
    for label, seg in [("1926~1980", smb[:"1980"]), ("1981~현재", smb["1981":])]:
        log(f"  {label}: 연평균 {ann(seg):+7.2%}  t값 {tstat(seg):5.2f}  "
            f"({len(seg)}개월)")
    log()
    log("  10년 단위:")
    for d0 in range(1930, d.index[-1].year + 1, 10):
        seg = smb[f"{d0}":f"{d0+9}"]
        if len(seg) >= 24:
            log(f"    {d0}년대: {ann(seg):+7.2%}  (t {tstat(seg):5.2f})")
    log()

    # ----- 4. 1월 효과 -----
    log("=" * 74)
    log("4. 1월 효과 — SMB 를 1월과 나머지 달로 나누면")
    log("=" * 74)
    jan = smb[smb.index.month == 1]
    rest = smb[smb.index.month != 1]
    log(f"  1월      : 월평균 {jan.mean():+.2%}  ({len(jan)}개월, t {tstat(jan):.2f})")
    log(f"  2~12월   : 월평균 {rest.mean():+.2%}  ({len(rest)}개월, t {tstat(rest):.2f})")
    log(f"  1월 한 달 {jan.mean():+.2%}, 2~12월 11개월을 합쳐도 "
        f"{(1+rest.mean())**11 - 1:+.2%}")
    log()
    log("  1981년 이후만:")
    j2, r2 = jan["1981":], rest["1981":]
    log(f"    1월 {j2.mean():+.2%} (t {tstat(j2):.2f})   2~12월 {r2.mean():+.2%} (t {tstat(r2):.2f})")
    log()

    # ----- 5. 다른 팩터를 통제하면 -----
    log("=" * 74)
    log("5. SMB 를 다른 팩터로 설명하고 남는 알파 (FF5 기간)")
    log("=" * 74)
    f5 = ff5.dropna()
    y = f5["SMB"]
    for name, cols in [("시장만 통제", ["Mkt-RF"]),
                       ("시장+밸류", ["Mkt-RF", "HML"]),
                       ("시장+밸류+퀄리티+투자", ["Mkt-RF", "HML", "RMW", "CMA"])]:
        a, t, b = regress(y, f5[cols])
        bs = "  ".join(f"{k} {v:+.2f}" for k, v in b.items())
        log(f"  {name:22s} 알파 {a:+7.2%} (t {t:5.2f})   {bs}")
    log()
    log(f"  참고) 같은 기간 SMB 원래 수익: 연평균 {ann(y):+.2%} (t {tstat(y):.2f})")
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GREEN, GRAY = "#1f5fbf", "#c45f00", "#1f8a70", "#9a9a9a"
        labels = ["1\n(small)"] + [str(i) for i in range(2, 10)] + ["10\n(large)"]

        # 17: 십분위 수익률과 샤프
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4))
        ax1.plot(range(10), [rows[c]["ret"] * 100 for c in DECILES],
                 color=BLUE, marker="o", markersize=7, linewidth=1.8)
        ax1.set_xticks(range(10)); ax1.set_xticklabels(labels, fontsize=8)
        ax1.set_ylabel("Annualized return (%)")
        ax1.set_title("Raw return: a weak tilt toward small, not monotonic")
        ax1.grid(alpha=0.3)
        ax2.plot(range(10), [rows[c]["sharpe"] for c in DECILES],
                 color=ORANGE, marker="o", markersize=7, linewidth=1.8)
        ax2.set_xticks(range(10)); ax2.set_xticklabels(labels, fontsize=8)
        ax2.set_ylabel("Sharpe ratio")
        ax2.set_title("Risk-adjusted: the smallest decile is the worst")
        ax2.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "17_size_deciles.png"), dpi=120); plt.close(fig)

        # 18: SMB 누적 (1981 표시)
        fig, ax = plt.subplots(figsize=(11, 4.5))
        cum = (1 + smb).cumprod()
        ax.plot(smb.index, cum, color=BLUE, linewidth=1.6)
        ax.axvline(pd.Timestamp("1981-01-31"), color=GRAY, linewidth=1.2, linestyle="--")
        ax.annotate("Banz (1981)", xy=(pd.Timestamp("1981-01-31"), cum.min()),
                    xytext=(8, 4), textcoords="offset points", color=GRAY, fontsize=9)
        ax.set_yscale("log")
        ax.set_yticks([0.6, 1, 2, 3, 4, 6])
        ax.set_yticklabels(["0.6", "1", "2", "3", "4", "6"])
        ax.set_ylabel("Growth of 1 (log scale)")
        ax.set_title("SMB: most of the gain came before the effect was published")
        ax.grid(alpha=0.3, which="both")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "18_smb_cumulative.png"), dpi=120); plt.close(fig)

        # 19: 월별 평균 (1월 효과)
        fig, ax = plt.subplots(figsize=(8.5, 4.2))
        by_month = [smb[smb.index.month == m].mean() * 100 for m in range(1, 13)]
        colors = [ORANGE] + [BLUE] * 11
        ax.bar(range(1, 13), by_month, color=colors)
        ax.axhline(0, color=GRAY, linewidth=1.1)
        ax.set_xticks(range(1, 13))
        ax.set_xlabel("Month")
        ax.set_ylabel("Average SMB return (%/month)")
        ax.set_title("The size premium is mostly a January phenomenon")
        ax.grid(alpha=0.3, axis="y")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "19_smb_by_month.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/17_size_deciles.png, 18_smb_cumulative.png, 19_smb_by_month.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "size_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/size_results.txt")


if __name__ == "__main__":
    main()
