"""
저변동성 팩터 — 덜 흔들리는 주식의 역설 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python scripts/low_volatility_factor.py

데이터:
  - 베타 정렬 포트폴리오 월별 수익률 (프렌치 교수 데이터 라이브러리의
    Portfolios_Formed_on_BETA, 값가중 블록). 공개 저장소의 사본을 읽는다.
  - 시장·무위험 수익률은 quality_factor.py 가 읽는 Fama-French 5팩터 파일.
결과: scripts/output/lowvol_results.txt 와 차트 PNG
(--synthetic 옵션을 주면 실제 데이터 대신 난수 데이터로 동작 확인만 한다)
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quality_factor import load as load_ff

BETA_URL = ("https://raw.githubusercontent.com/a91quaini/reproduceTFRP/main/"
            "data-raw/Portfolios_Formed_on_BETA.csv")
QUINTILES = ["Lo 20", "Qnt 2", "Qnt 3", "Qnt 4", "Hi 20"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


def load_beta_portfolios(synthetic=False):
    """베타 오분위 포트폴리오 월별 수익률(소수)."""
    if synthetic:
        rng = np.random.default_rng(0)
        idx = pd.date_range("1963-07-31", "2020-07-31", freq="ME")
        cols = {}
        for i, c in enumerate(QUINTILES + ["Lo 10", "Hi 10"]):
            cols[c] = rng.normal(0.008, 0.03 + 0.01 * i, len(idx))
        return pd.DataFrame(cols, index=idx)

    df = pd.read_csv(BETA_URL)
    df.columns = [c.strip() for c in df.columns]
    df = df[df["Date"].astype(str).str.len() == 6]
    df.index = pd.to_datetime(df.pop("Date").astype(str), format="%Y%m") + pd.offsets.MonthEnd(0)
    return df.astype(float) / 100.0


def capm(excess, mkt):
    """시장에 대한 베타와 연율화 알파, 알파의 t값."""
    beta = np.cov(excess, mkt)[0, 1] / mkt.var()
    alpha = excess - beta * mkt
    t = alpha.mean() / alpha.std() * np.sqrt(len(alpha))
    return beta, alpha.mean() * 12, t


def ann(x):
    return (1 + x).prod() ** (12 / len(x)) - 1


def main():
    synthetic = "--synthetic" in sys.argv
    beta_ports = load_beta_portfolios(synthetic)
    ff = load_ff(synthetic)
    d = beta_ports.join(ff[["Mkt-RF", "RF"]], how="inner").dropna()
    mkt = d["Mkt-RF"]
    log(f"데이터: {'합성' if synthetic else '베타 정렬 포트폴리오(값가중) + FF 시장/무위험'}, "
        f"{d.index[0]:%Y-%m} ~ {d.index[-1]:%Y-%m}, {len(d)}개월")
    log()

    # ----- 1. 베타 오분위 -----
    log("=" * 72)
    log("1. 베타로 5등분한 포트폴리오 (낮은 베타 -> 높은 베타)")
    log("=" * 72)
    log(f"  {'분위':8s}{'연평균':>9s}{'연변동성':>10s}{'베타':>7s}{'샤프':>7s}{'CAPM알파':>10s}{'t값':>7s}")
    rows = {}
    for c in QUINTILES:
        ex = d[c] - d["RF"]
        b, a, t = capm(ex, mkt)
        rows[c] = dict(ret=ann(d[c]), vol=d[c].std() * np.sqrt(12), beta=b,
                       sharpe=ex.mean() / ex.std() * np.sqrt(12), alpha=a, t=t)
        r = rows[c]
        log(f"  {c:8s}{r['ret']:>9.2%}{r['vol']:>10.1%}{r['beta']:>7.2f}"
            f"{r['sharpe']:>7.2f}{r['alpha']:>+10.2%}{r['t']:>7.2f}")
    lo, hi = rows["Lo 20"], rows["Hi 20"]
    log()
    log(f"  저베타 대비 고베타: 베타 {hi['beta']/lo['beta']:.1f}배, 변동성 {hi['vol']/lo['vol']:.1f}배, "
        f"수익률 {hi['ret']-lo['ret']:+.2%}p")
    log()

    # ----- 2. 십분위 양 끝 -----
    if "Lo 10" in d.columns and "Hi 10" in d.columns:
        log("=" * 72)
        log("2. 십분위 양 끝 (더 극단으로 가면)")
        log("=" * 72)
        for c in ["Lo 10", "Hi 10"]:
            ex = d[c] - d["RF"]
            b, a, t = capm(ex, mkt)
            log(f"  {c:6s} 연평균 {ann(d[c]):>7.2%}  변동성 {d[c].std()*np.sqrt(12):>6.1%}  "
                f"베타 {b:5.2f}  샤프 {ex.mean()/ex.std()*np.sqrt(12):5.2f}  알파 {a:+.2%} (t {t:.2f})")
        log()

    # ----- 3. CAPM 이 예측한 값과 비교 -----
    log("=" * 72)
    log("3. CAPM 예측 vs 실제 (초과수익률 기준, 연율)")
    log("=" * 72)
    mkt_prem = mkt.mean() * 12
    log(f"  시장 위험프리미엄: {mkt_prem:+.2%}")
    log(f"  {'분위':8s}{'베타':>7s}{'CAPM예측':>11s}{'실제':>10s}{'차이':>10s}")
    for c in QUINTILES:
        r = rows[c]
        actual = (d[c] - d["RF"]).mean() * 12
        pred = r["beta"] * mkt_prem
        log(f"  {c:8s}{r['beta']:>7.2f}{pred:>+11.2%}{actual:>+10.2%}{actual-pred:>+10.2%}")
    log()

    # ----- 4. 레버리지를 쓰면 -----
    log("=" * 72)
    log("4. 저베타를 시장 베타(1.0)까지 레버리지하면 (조달금리 = 무위험수익률)")
    log("=" * 72)
    k = 1.0 / lo["beta"]
    lev = k * (d["Lo 20"] - d["RF"]) + d["RF"]
    log(f"  배수 {k:.2f}배 (베타 {lo['beta']:.2f} -> 1.00)")
    log(f"  레버리지 저베타: 연평균 {ann(lev):>7.2%}  변동성 {lev.std()*np.sqrt(12):>6.1%}  "
        f"샤프 {(lev-d['RF']).mean()/(lev-d['RF']).std()*np.sqrt(12):5.2f}")
    log(f"  시장          : 연평균 {ann(mkt+d['RF']):>7.2%}  변동성 {(mkt+d['RF']).std()*np.sqrt(12):>6.1%}  "
        f"샤프 {mkt.mean()/mkt.std()*np.sqrt(12):5.2f}")
    log("  (현실에서는 조달금리가 무위험수익률보다 높고 증거금 제약도 있다)")
    log()

    # ----- 5. 구간별 -----
    log("=" * 72)
    log("5. 20년 단위로 끊어보면 (고베타 - 저베타 연평균 차이)")
    log("=" * 72)
    for a0, b0 in [("1963", "1979"), ("1980", "1999"), ("2000", "2020")]:
        seg = d.loc[a0:b0]
        if len(seg) < 24:
            continue
        log(f"  {a0}~{b0}: 저베타 {ann(seg['Lo 20']):>7.2%}  고베타 {ann(seg['Hi 20']):>7.2%}  "
            f"차이 {ann(seg['Hi 20'])-ann(seg['Lo 20']):>+7.2%}p")
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GRAY = "#1f5fbf", "#c45f00", "#9a9a9a"

        # 15: 증권시장선 — CAPM 예측선 vs 실제
        fig, ax = plt.subplots(figsize=(8, 5.5))
        bs = [rows[c]["beta"] for c in QUINTILES]
        acts = [(d[c] - d["RF"]).mean() * 12 * 100 for c in QUINTILES]
        xs = np.linspace(0.5, 1.65, 50)
        ax.plot(xs, xs * mkt_prem * 100, color=GRAY, linewidth=1.6, linestyle="--")
        ax.annotate("CAPM prediction", xy=(1.45, 1.45 * mkt_prem * 100), color=GRAY,
                    fontsize=9, xytext=(-30, 8), textcoords="offset points")
        ax.plot(bs, acts, color=BLUE, linewidth=2, marker="o", markersize=9)
        for c, x, y in zip(QUINTILES, bs, acts):
            ax.annotate(c, (x, y), textcoords="offset points", xytext=(8, -14), fontsize=9)
        ax.set_xlabel("Beta")
        ax.set_ylabel("Realized excess return, annualized (%)")
        ax.set_title("The security market line is flat, not upward sloping")
        ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "15_flat_sml.png"), dpi=120); plt.close(fig)

        # 16: 누적 수익 (저베타 vs 고베타)
        fig, ax = plt.subplots(figsize=(11, 4.5))
        for c, col in [("Lo 20", BLUE), ("Hi 20", ORANGE)]:
            ax.plot(d.index, (1 + d[c]).cumprod(), color=col, linewidth=1.6,
                    label=f"{c} (beta {rows[c]['beta']:.2f}, vol {rows[c]['vol']:.0%})")
        ax.set_yscale("log")
        ax.set_ylabel("Growth of 1 (log scale)")
        ax.set_title("Low-beta stocks ended ahead, with half the volatility")
        ax.legend(frameon=False, loc="upper left")
        ax.grid(alpha=0.3, which="both")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "16_lowbeta_cumulative.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/15_flat_sml.png, 16_lowbeta_cumulative.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "lowvol_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/lowvol_results.txt")


if __name__ == "__main__":
    main()
