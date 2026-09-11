"""
밸류 팩터 — 싼 주식은 정말 더 오르나 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python scripts/value_factor.py

데이터: 케네스 프렌치 교수가 공개하는 Fama-French 3팩터 월별 수익률.
        (원본은 프렌치 교수 데이터 라이브러리. 여기서는 공개 저장소의 사본을 읽는다.)
        HML = 장부가/시가 비율이 높은(싼) 주식 롱 - 낮은(비싼) 주식 숏
결과:   scripts/output/value_results.txt 와 차트 PNG
(--synthetic 옵션을 주면 실제 데이터 대신 난수 데이터로 동작 확인만 한다)
"""
import io
import os
import sys
import numpy as np
import pandas as pd

URL = ("https://raw.githubusercontent.com/QuantConnect/Tutorials/master/"
       "Data/F-F_Research_Data_Factors.CSV")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


def load(synthetic=False):
    """월별 팩터 수익률(소수)로 반환. 파일은 월별 블록 뒤에 연간 블록이 이어진다."""
    if synthetic:
        rng = np.random.default_rng(0)
        idx = pd.period_range("1926-07", "2020-06", freq="M")
        n = len(idx)
        return pd.DataFrame({
            "Mkt-RF": rng.normal(0.006, 0.05, n),
            "SMB": rng.normal(0.002, 0.03, n),
            "HML": rng.normal(0.003, 0.03, n),
            "RF": np.full(n, 0.003),
        }, index=idx.to_timestamp("M"))

    import urllib.request
    raw = urllib.request.urlopen(URL).read().decode("utf-8", "ignore")
    body = raw.split(",Mkt-RF,SMB,HML,RF", 1)[1]
    rows = []
    for line in body.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 5 or not parts[0].isdigit():
            continue
        if len(parts[0]) != 6:      # 연간 블록(YYYY)에 닿으면 중단
            break
        rows.append([parts[0]] + [float(x) for x in parts[1:]])
    df = pd.DataFrame(rows, columns=["ym", "Mkt-RF", "SMB", "HML", "RF"])
    df.index = pd.to_datetime(df.pop("ym"), format="%Y%m") + pd.offsets.MonthEnd(0)
    return df / 100.0


def ann_return(x):
    return (1 + x).prod() ** (12 / len(x)) - 1


def stats(x, label):
    cum = (1 + x).cumprod()
    dd = cum / cum.cummax() - 1
    under = run = longest = 0
    for f in (dd < 0):
        run = run + 1 if f else 0
        longest = max(longest, run)
    t = x.mean() / x.std() * np.sqrt(len(x))       # 평균이 0인지에 대한 t값
    return pd.Series({
        "연평균": ann_return(x),
        "연변동성": x.std() * np.sqrt(12),
        "MDD": dd.min(),
        "t값": t,
        "최장침체(개월)": longest,
    }, name=label)


def main():
    synthetic = "--synthetic" in sys.argv
    df = load(synthetic)
    hml, mkt = df["HML"], df["Mkt-RF"]
    log(f"데이터: {'합성' if synthetic else 'Fama-French 3팩터(월별)'}, "
        f"{df.index[0]:%Y-%m} ~ {df.index[-1]:%Y-%m}, {len(df)}개월")
    log()

    # ----- 1. 전체 기간 -----
    log("=" * 64)
    log("1. 전체 기간 성과 (HML = 싼 주식 롱 / 비싼 주식 숏)")
    log("=" * 64)
    log(pd.concat([stats(hml, "HML(밸류)"), stats(mkt, "시장-무위험")], axis=1)
        .round(4).to_string())
    log(f"HML 누적: {(1+hml).prod():.1f}배 (같은 기간 시장초과 {(1+mkt).prod():.1f}배)")
    log()

    # ----- 2. 10년 단위 -----
    log("=" * 64)
    log("2. 10년 단위 HML 연평균 수익률")
    log("=" * 64)
    for d0 in range(1930, df.index[-1].year + 1, 10):
        seg = hml[f"{d0}":f"{d0+9}"]
        if len(seg) >= 24:
            log(f"  {d0}년대 ({len(seg):3d}개월): {ann_return(seg):+7.2%}")
    log()

    # ----- 3. 논문 발표 전후 -----
    log("=" * 64)
    log("3. Fama-French 논문(1992) 발표 전후")
    log("=" * 64)
    for a, b, name in [(None, "1991", "1926~1991 (발표 전)"),
                       ("1992", "2006", "1992~2006"),
                       ("2007", None, "2007~ (최근)")]:
        seg = hml[a:b] if (a or b) else hml
        s = stats(seg, name)
        log(f"  {name:20s} 연평균 {s['연평균']:+7.2%}  t값 {s['t값']:5.2f}  "
            f"MDD {s['MDD']:7.1%}  ({len(seg)}개월)")
    log()

    # ----- 4. 최악의 침체 -----
    log("=" * 64)
    log("4. HML 의 최대 낙폭 구간")
    log("=" * 64)
    cum = (1 + hml).cumprod()
    dd = cum / cum.cummax() - 1
    trough = dd.idxmin()
    peak = cum[:trough].idxmax()
    rec = dd[trough:]
    recovered = rec[rec >= -1e-9]
    log(f"  고점 {peak:%Y-%m} -> 저점 {trough:%Y-%m} ({dd.min():.1%})")
    log(f"  회복 시점: {'아직 회복 못함(데이터 끝까지)' if len(recovered) == 0 else f'{recovered.index[0]:%Y-%m}'}")
    log(f"  고점부터 데이터 끝까지 {(trough - peak).days // 30}개월 하락")
    log()

    # ----- 5. 롤링 10년 -----
    log("=" * 64)
    log("5. 10년(120개월) 롤링 연평균 수익률이 마이너스였던 비율")
    log("=" * 64)
    roll = (1 + hml).rolling(120).apply(np.prod, raw=True) ** (1 / 10) - 1
    roll = roll.dropna()
    log(f"  HML: 전체 {len(roll)}개 구간 중 마이너스 {int((roll < 0).sum())}개 "
        f"({(roll < 0).mean():.1%})")
    rollm = (1 + mkt).rolling(120).apply(np.prod, raw=True) ** (1 / 10) - 1
    rollm = rollm.dropna()
    log(f"  시장: 전체 {len(rollm)}개 구간 중 마이너스 {int((rollm < 0).sum())}개 "
        f"({(rollm < 0).mean():.1%})")
    log(f"  HML 롤링 10년 최저 {roll.min():+.2%} ({roll.idxmin():%Y-%m} 종료 구간)")
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GRAY = "#1f5fbf", "#c45f00", "#9a9a9a"

        # 11: HML 누적 (로그)
        fig, ax = plt.subplots(figsize=(11, 4.5))
        ax.plot(cum.index, cum, color=BLUE, linewidth=1.6)
        ax.set_yscale("log")
        ax.set_ylabel("Growth of 1 (log scale)")
        ax.set_title("HML (value minus growth): cumulative return, log scale")
        ax.axvspan(pd.Timestamp("2007-01-01"), cum.index[-1], color=ORANGE, alpha=0.12)
        ax.annotate("2007 onward", xy=(pd.Timestamp("2007-06-01"), cum.min() * 1.15),
                    fontsize=9, color=ORANGE)
        ax.grid(alpha=0.3, which="both")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "11_hml_cumulative.png"), dpi=120); plt.close(fig)

        # 12: 롤링 10년
        fig, ax = plt.subplots(figsize=(11, 4))
        ax.axhline(0, color=GRAY, linewidth=1.2)
        ax.fill_between(roll.index, roll * 100, 0, where=(roll < 0),
                        color=ORANGE, alpha=0.25, linewidth=0)
        ax.plot(roll.index, roll * 100, color=BLUE, linewidth=1.5)
        ax.set_ylabel("Annualized return (%)")
        ax.set_title("HML: trailing 10-year annualized return")
        ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "12_hml_rolling10y.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/11_hml_cumulative.png, 12_hml_rolling10y.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "value_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/value_results.txt")


if __name__ == "__main__":
    main()
