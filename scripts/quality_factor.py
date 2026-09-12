"""
퀄리티 팩터 — 좋은 회사와 좋은 주식은 다르다 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python scripts/quality_factor.py

데이터: Fama-French 5팩터 월별 수익률 (1963-07 ~ 2020-07).
        RMW = 영업이익률이 높은(robust) 주식 롱 - 낮은(weak) 주식 숏. 퀄리티의 대리 지표.
        HML = 싼 주식 롱 - 비싼 주식 숏 (밸류).
결과:   scripts/output/quality_results.txt 와 차트 PNG
(--synthetic 옵션을 주면 실제 데이터 대신 난수 데이터로 동작 확인만 한다)
"""
import os
import sys
import numpy as np
import pandas as pd

URL = ("https://raw.githubusercontent.com/QuantConnect/Tutorials/master/"
       "Data/F-F_Research_Data_5_Factors_2x3.CSV")
COLS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


def load(synthetic=False):
    """월별 팩터 수익률(소수). 월별 블록 뒤에 연간 블록이 이어지므로 날짜 자릿수로 끊는다."""
    if synthetic:
        rng = np.random.default_rng(0)
        idx = pd.date_range("1963-07-31", "2020-07-31", freq="ME")
        n = len(idx)
        return pd.DataFrame({c: rng.normal(0.003, 0.03, n) for c in COLS}, index=idx)

    import urllib.request
    raw = urllib.request.urlopen(URL).read().decode("utf-8", "ignore")
    body = raw.split("," + ",".join(COLS), 1)[1]
    rows = []
    for line in body.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 7 or not parts[0].isdigit():
            continue
        if len(parts[0]) != 6:      # 연간 블록(YYYY)에 닿으면 중단
            break
        rows.append([parts[0]] + [float(x) for x in parts[1:]])
    df = pd.DataFrame(rows, columns=["ym"] + COLS)
    df.index = pd.to_datetime(df.pop("ym"), format="%Y%m") + pd.offsets.MonthEnd(0)
    return df / 100.0


def ann(x):
    return (1 + x).prod() ** (12 / len(x)) - 1


def stats(x):
    cum = (1 + x).cumprod()
    dd = cum / cum.cummax() - 1
    run = longest = 0
    for f in (dd < 0):
        run = run + 1 if f else 0
        longest = max(longest, run)
    return pd.Series({
        "연평균": ann(x),
        "연변동성": x.std() * np.sqrt(12),
        "MDD": dd.min(),
        "샤프": x.mean() / x.std() * np.sqrt(12),
        "t값": x.mean() / x.std() * np.sqrt(len(x)),
        "최장침체(개월)": longest,
    })


def main():
    synthetic = "--synthetic" in sys.argv
    df = load(synthetic)
    log(f"데이터: {'합성' if synthetic else 'Fama-French 5팩터(월별)'}, "
        f"{df.index[0]:%Y-%m} ~ {df.index[-1]:%Y-%m}, {len(df)}개월")
    log()

    rmw, hml, mkt = df["RMW"], df["HML"], df["Mkt-RF"]

    # ----- 1. 전체 기간 -----
    log("=" * 66)
    log("1. 전체 기간 (RMW = 고수익성 롱 / 저수익성 숏)")
    log("=" * 66)
    log(pd.DataFrame({"RMW(퀄리티)": stats(rmw), "HML(밸류)": stats(hml),
                      "시장-무위험": stats(mkt)}).round(4).to_string())
    log()

    # ----- 2. 10년 단위 -----
    log("=" * 66)
    log("2. 10년 단위 연평균")
    log("=" * 66)
    log(f"  {'연대':10s}{'RMW':>10s}{'HML':>10s}")
    for d0 in range(1970, df.index[-1].year + 1, 10):
        a, b = f"{d0}", f"{d0+9}"
        if len(rmw[a:b]) >= 24:
            log(f"  {d0}년대{'':4s}{ann(rmw[a:b]):>9.2%}{ann(hml[a:b]):>10.2%}")
    log()

    # ----- 3. 밸류가 무너진 구간에서 퀄리티는 -----
    log("=" * 66)
    log("3. 2007년 이후 (밸류가 무너진 구간)")
    log("=" * 66)
    for name, seg in [("RMW", rmw["2007":]), ("HML", hml["2007":])]:
        s = stats(seg)
        log(f"  {name}: 연평균 {s['연평균']:+7.2%}  t값 {s['t값']:5.2f}  MDD {s['MDD']:7.1%}")
    log()

    # ----- 4. 두 팩터의 상관관계 -----
    log("=" * 66)
    log("4. RMW 와 HML 의 상관계수")
    log("=" * 66)
    log(f"  전체 기간: {rmw.corr(hml):+.3f}")
    for a, b in [("1963", "1989"), ("1990", "2006"), ("2007", None)]:
        seg_r, seg_h = rmw[a:b], hml[a:b]
        log(f"  {a}~{b or '끝'}: {seg_r.corr(seg_h):+.3f}")
    log()

    # ----- 5. 섞으면 -----
    log("=" * 66)
    log("5. 밸류 단독 vs 밸류+퀄리티 반반 (월별 균등)")
    log("=" * 66)
    combo = 0.5 * hml + 0.5 * rmw
    tab = pd.DataFrame({"HML만": stats(hml), "RMW만": stats(rmw),
                        "HML+RMW 반반": stats(combo)})
    log(tab.round(4).to_string())
    log()
    log("  2007년 이후만:")
    tab2 = pd.DataFrame({"HML만": stats(hml["2007":]), "RMW만": stats(rmw["2007":]),
                         "HML+RMW 반반": stats(combo["2007":])})
    log(tab2.round(4).to_string())
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GREEN, GRAY = "#1f5fbf", "#c45f00", "#1f8a70", "#9a9a9a"

        # 13: RMW vs HML 누적
        fig, ax = plt.subplots(figsize=(11, 4.5))
        for s, c, lab in [(rmw, BLUE, "RMW (quality)"), (hml, ORANGE, "HML (value)")]:
            ax.plot(s.index, (1 + s).cumprod(), color=c, linewidth=1.6, label=lab)
        ax.set_yscale("log")
        ax.set_ylabel("Growth of 1 (log scale)")
        ax.set_title("Quality vs value: cumulative factor return")
        ax.legend(frameon=False, loc="upper left")
        ax.grid(alpha=0.3, which="both")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "13_rmw_vs_hml.png"), dpi=120); plt.close(fig)

        # 14: 2007년 이후만 다시 1에서 출발
        fig, ax = plt.subplots(figsize=(11, 4))
        seg = df["2007":]
        for s, c, lab in [(seg["RMW"], BLUE, "RMW (quality)"),
                          (seg["HML"], ORANGE, "HML (value)"),
                          (0.5 * seg["HML"] + 0.5 * seg["RMW"], GREEN, "half and half")]:
            ax.plot(s.index, ((1 + s).cumprod() - 1) * 100, color=c, linewidth=1.7, label=lab)
        ax.axhline(0, color=GRAY, linewidth=1.2)
        ax.set_ylabel("Cumulative return (%)")
        ax.set_title("2007 onward: quality held up while value did not")
        ax.legend(frameon=False, loc="lower left")
        ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "14_since2007.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/13_rmw_vs_hml.png, 14_since2007.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "quality_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/quality_results.txt")


if __name__ == "__main__":
    main()
