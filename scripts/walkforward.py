"""
워크포워드 검증 — 과거로 고른 설정이 다음 달에도 통하는가 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python scripts/walkforward.py

데이터: scripts/data/krx/snapshot_YYYYMMDD.csv.gz  (전 종목 재무 스냅샷, 2024-12 ~ 2026-09)
        scripts/data/krx/returns_<from>_<to>.csv.gz (구간별 전 종목 등락률, 수정주가·상폐 포함)
결과:   scripts/output/walkforward_results.txt 와 차트 PNG
(--synthetic 을 주면 난수 데이터로 로직만 확인한다)
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from krx_snapshot import clean                                    # noqa: E402
from screener import is_financial, rank_score                     # noqa: E402

DATA = os.path.join(HERE, "data", "krx")
OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)
lines = []

# 후보 설정: (이름, 점수에 쓸 지표, 그룹 내 순위 여부, 종목 수)
METRICS = {
    "밸류3": ["이익수익률", "_pbr_inv", "DIV"],
    "이익수익률만": ["이익수익률"],
    "저PBR만": ["_pbr_inv"],
    "고배당만": ["DIV"],
}
SIZES = [10, 20, 30, 50]
MIN_CAP = 1000e8


def log(s=""):
    print(s)
    lines.append(str(s))


def load_snapshots(synthetic=False):
    """{날짜: 정제된 스냅샷} 과 {(d0,d1): 등락률 Series(소수)} 를 돌려준다."""
    if synthetic:
        return synthetic_panel()
    snaps, rets = {}, {}
    for p in sorted(glob.glob(os.path.join(DATA, "snapshot_*.csv.gz"))):
        d = os.path.basename(p).split("_")[1].split(".")[0]
        snaps[d] = clean(pd.read_csv(p, index_col=0, dtype={"티커": str}))
    for p in sorted(glob.glob(os.path.join(DATA, "returns_*.csv.gz"))):
        d0, d1 = os.path.basename(p).replace(".csv.gz", "").split("_")[1:3]
        r = pd.read_csv(p, index_col=0, dtype={"티커": str})
        rets[(d0, d1)] = r["등락률"] / 100.0
    return snaps, rets


def synthetic_panel(n=400, months=21, seed=0):
    """실제 데이터 없이 로직만 확인할 때 쓰는 난수 패널."""
    rng = np.random.default_rng(seed)
    tickers = [f"{i:06d}0"[-6:] for i in range(n)]
    dates = [d.strftime("%Y%m%d")
             for d in pd.date_range("2024-12-31", periods=months + 1, freq="ME")]
    snaps, rets = {}, {}
    for d in dates:
        price = rng.uniform(1000, 50000, n)
        eps = np.where(rng.random(n) < 0.4, 0, price * rng.uniform(0.02, 0.3, n))
        bps = price * rng.uniform(0.3, 5, n)
        dps = np.where(rng.random(n) < 0.5, 0, price * rng.uniform(0.01, 0.08, n))
        raw = pd.DataFrame({
            "BPS": bps.round(), "PER": np.where(eps > 0, price / np.maximum(eps, 1), 0),
            "PBR": (price / bps).round(2), "EPS": eps.round(),
            "DIV": (dps / price * 100).round(2), "DPS": dps.round(),
            "종가": price.round(), "시가총액": price * rng.uniform(1e6, 1e8, n),
            "종목명": [f"종목{i:03d}" for i in range(n)],
            "시장": "KOSPI",
        }, index=pd.Index(tickers, name="티커"))
        snaps[d] = clean(raw)
    for d0, d1 in zip(dates[:-1], dates[1:]):
        rets[(d0, d1)] = pd.Series(rng.normal(0.01, 0.12, n), index=tickers)
    return snaps, rets


def universe(df, min_cap=MIN_CAP):
    u = df[df.index.str.endswith("0")]
    u = u[~u["종목명"].str.contains("스팩|SPAC", na=False)]
    u = u[u["시가총액"] >= min_cap]
    return u.dropna(subset=["BPS"])


def pick(df, metric, n, grouped, min_cap=MIN_CAP):
    """한 시점의 스냅샷에서 상위 n 종목의 티커를 고른다."""
    u = universe(df, min_cap).copy()
    u["_pbr_inv"] = 1 / u["PBR"]
    by = None
    if grouped:
        u["_g"] = np.where(is_financial(u["종목명"]), "금융·지주", "일반")
        by = "_g"
    u["_score"] = rank_score(u, metric, by=by)
    return u.nlargest(n, "_score").index


def period_return(tickers, r, drop_delisted=False):
    """동일비중 보유 수익률. 데이터가 없는 종목은 제외하고 개수를 함께 돌려준다.

    상장폐지 종목은 등락률 -100 으로 들어 있다. drop_delisted=True 로 두면
    그 종목을 아예 빼고 계산한다(= 살아남은 종목만 본다 = 생존 편향).
    """
    s = r.reindex(tickers)
    if drop_delisted:
        s = s[s > -0.999]
    return float(s.mean()) if s.notna().any() else np.nan, int(s.isna().sum())


def build_table(snaps, rets):
    """설정별·월별 수익률 표. 행=구간, 열=설정 이름."""
    periods = sorted(rets.keys())
    rows, missing = {}, 0
    for d0, d1 in periods:
        if d0 not in snaps:
            continue
        row = {}
        for mname, cols in METRICS.items():
            for n in SIZES:
                for grouped in (False, True):
                    key = f"{mname}|{n}|{'그룹' if grouped else '전체'}"
                    tick = pick(snaps[d0], cols, n, grouped)
                    ret, miss = period_return(tick, rets[(d0, d1)])
                    row[key] = ret
                    missing += miss
        u = universe(snaps[d0])
        row["유니버스 동일비중"] = float(rets[(d0, d1)].reindex(u.index).mean())
        rows[d1] = row
    return pd.DataFrame(rows).T.sort_index(), missing


def walk_forward(tab, warmup=6):
    """직전 구간들에서 1등이던 설정을 다음 구간에 쓴다."""
    cands = [c for c in tab.columns if c != "유니버스 동일비중"]
    out = []
    for i in range(warmup, len(tab)):
        hist = tab.iloc[:i][cands]
        best = hist.mean().idxmax()
        out.append({
            "구간": tab.index[i],
            "선택한 설정": best,
            "그 설정의 과거 평균": hist.mean().max(),
            "다음 구간 실현": tab.iloc[i][best],
            "그 구간 전체 설정 평균": tab.iloc[i][cands].mean(),
            "유니버스": tab.iloc[i]["유니버스 동일비중"],
        })
    return pd.DataFrame(out).set_index("구간")


def cum(x):
    return float((1 + pd.Series(x).dropna()).prod() - 1)


def main():
    synthetic = "--synthetic" in sys.argv
    snaps, rets = load_snapshots(synthetic)
    log(f"데이터: {'합성' if synthetic else 'KRX 월말 스냅샷'}, "
        f"스냅샷 {len(snaps)}개, 구간 {len(rets)}개")
    if not synthetic:
        ds = sorted(snaps)
        log(f"기간: {ds[0]} ~ {ds[-1]}")
    log()

    tab, missing = build_table(snaps, rets)
    log(f"설정 {len(tab.columns) - 1}개 x 구간 {len(tab)}개 계산 완료 "
        f"(수익률 없는 종목 슬롯 {missing}개)")
    log()

    # ----- 1. 전체 기간 1등 설정 (사후에 고른 것) -----
    log("=" * 70)
    log("1. 전체 기간을 다 보고 고른 1등 설정")
    log("=" * 70)
    cands = [c for c in tab.columns if c != "유니버스 동일비중"]
    tot = tab[cands].apply(cum).sort_values(ascending=False)
    log(f"  최고: {tot.index[0]}  누적 {tot.iloc[0]:+.1%}")
    log(f"  최저: {tot.index[-1]}  누적 {tot.iloc[-1]:+.1%}")
    log(f"  유니버스 동일비중: {cum(tab['유니버스 동일비중']):+.1%}")
    log(f"  설정 {len(cands)}개의 누적수익률 중앙값: {tot.median():+.1%}")
    log()
    log("  상위 5개:")
    for k, v in tot.head(5).items():
        log(f"    {k:28s} {v:+8.1%}")
    log("  하위 3개:")
    for k, v in tot.tail(3).items():
        log(f"    {k:28s} {v:+8.1%}")
    log()

    # ----- 2. 워크포워드 -----
    log("=" * 70)
    log("2. 워크포워드: 직전 구간들의 1등을 다음 구간에 쓴다")
    log("=" * 70)
    wf = walk_forward(tab)
    log(wf.round(4).to_string())
    log()
    log(f"  워크포워드 누적        : {cum(wf['다음 구간 실현']):+.1%}")
    log(f"  같은 구간 전체 설정 평균: {cum(wf['그 구간 전체 설정 평균']):+.1%}")
    log(f"  같은 구간 유니버스      : {cum(wf['유니버스']):+.1%}")
    log(f"  과거 평균의 평균        : {wf['그 설정의 과거 평균'].mean():+.2%}/월")
    log(f"  실현 수익률의 평균      : {wf['다음 구간 실현'].mean():+.2%}/월")
    log(f"  설정이 바뀐 횟수        : {(wf['선택한 설정'] != wf['선택한 설정'].shift()).sum() - 1}"
        f" / {len(wf) - 1}")
    log()

    # ----- 3. 과거 순위와 다음 달 순위의 관계 -----
    log("=" * 70)
    log("3. 과거 성적 순위가 다음 구간 순위를 예측하는가 (순위 상관)")
    log("=" * 70)
    cors = []
    for i in range(6, len(tab)):
        past = tab.iloc[:i][cands].mean()
        nxt = tab.iloc[i][cands]
        cors.append(past.rank().corr(nxt.rank()))   # 순위끼리의 상관 = 스피어만
    cs = pd.Series(cors, index=tab.index[6:])
    log(f"  구간별 상관계수 평균: {cs.mean():+.3f}  (중앙값 {cs.median():+.3f})")
    log(f"  양수인 구간: {(cs > 0).sum()} / {len(cs)}")
    log()

    # ----- 4. 한 번 고르고 버티기 vs 매달 다시 고르기 -----
    log("=" * 70)
    log("4. 2024-12 에 한 번 고르고 버티기 vs 매달 다시 고르기 (밸류3, 20종목)")
    log("=" * 70)
    d0 = sorted(snaps)[0]
    fixed = pick(snaps[d0], METRICS["밸류3"], 20, False)
    per_fixed, per_roll, dropped = [], [], []
    for (a, b) in sorted(rets):
        if a not in snaps:
            continue
        r = rets[(a, b)]
        f, miss = period_return(fixed, r)
        per_fixed.append(f)
        dropped.append(miss)
        per_roll.append(tab.loc[b, "밸류3|20|전체"])
    log(f"  고정 보유 누적   : {cum(per_fixed):+.1%}  (수익률 없는 종목 누적 {sum(dropped)}개)")
    log(f"  매달 재선정 누적 : {cum(per_roll):+.1%}")
    log(f"  유니버스 누적    : {cum(tab['유니버스 동일비중']):+.1%}")
    keep = len(set(fixed) & set(pick(snaps[sorted(snaps)[-1]], METRICS["밸류3"], 20, False)))
    log(f"  처음 20종목 중 마지막 시점에도 상위 20에 남은 종목: {keep}개")
    log()

    # ----- 5. 상장폐지를 빼면 (생존 편향) -----
    log("=" * 70)
    log("5. 상장폐지 종목을 빼고 계산하면 (생존 편향의 크기)")
    log("=" * 70)
    with_d, without_d, n_delist = [], [], 0
    for (a, b) in sorted(rets):
        if a not in snaps:
            continue
        tick = pick(snaps[a], METRICS["밸류3"], 20, False)
        r = rets[(a, b)]
        with_d.append(period_return(tick, r)[0])
        without_d.append(period_return(tick, r, drop_delisted=True)[0])
        n_delist += int((r.reindex(tick) <= -0.999).sum())
    uni_d = 0
    for (a, b) in sorted(rets):
        if a in snaps:
            u = universe(snaps[a])
            uni_d += int((rets[(a, b)].reindex(u.index) <= -0.999).sum())
    log(f"  상폐 포함 누적 : {cum(with_d):+.1%}")
    log(f"  상폐 제외 누적 : {cum(without_d):+.1%}")
    log(f"  차이           : {cum(without_d) - cum(with_d):+.1%}p")
    log(f"  선정 종목 중 상폐 건수: {n_delist}  (유니버스 전체 상폐 슬롯 {uni_d}건)")
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GRAY, GREEN = "#1f5fbf", "#c45f00", "#9a9a9a", "#1f8a70"
        idx = pd.to_datetime(wf.index, format="%Y%m%d")

        fig, ax = plt.subplots(figsize=(11, 4.3))
        ax.plot(idx, (1 + wf["다음 구간 실현"]).cumprod(), color=BLUE,
                linewidth=1.8, label="walk-forward pick")
        ax.plot(idx, (1 + wf["그 구간 전체 설정 평균"]).cumprod(), color=ORANGE,
                linewidth=1.6, label="average of all settings")
        ax.plot(idx, (1 + wf["유니버스"]).cumprod(), color=GRAY,
                linewidth=1.5, linestyle="--", label="universe equal weight")
        ax.axhline(1, color=GRAY, linewidth=0.8)
        ax.set_ylabel("Growth of 1")
        ax.set_title("Walk-forward: picking last period's winner")
        ax.legend(frameon=False, loc="upper left")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "30_walkforward.png"), dpi=120)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 4))
        ax.scatter(wf["그 설정의 과거 평균"] * 100, wf["다음 구간 실현"] * 100,
                   color=BLUE, s=42, zorder=3)
        ax.axhline(0, color=GRAY, linewidth=1)
        ax.axvline(0, color=GRAY, linewidth=1)
        ax.set_xlabel("Past average monthly return of the chosen setting (%)")
        ax.set_ylabel("Realized next-period return (%)")
        ax.set_title("What the past promised vs what came next")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "31_promise_vs_reality.png"), dpi=120)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 4))
        ax.plot(pd.to_datetime(tab.index, format="%Y%m%d"),
                (1 + pd.Series(per_fixed, index=tab.index)).cumprod(),
                color=ORANGE, linewidth=1.7, label="hold the 2024-12 picks")
        ax.plot(pd.to_datetime(tab.index, format="%Y%m%d"),
                (1 + tab["밸류3|20|전체"]).cumprod(),
                color=BLUE, linewidth=1.7, label="re-screen every month")
        ax.plot(pd.to_datetime(tab.index, format="%Y%m%d"),
                (1 + tab["유니버스 동일비중"]).cumprod(),
                color=GRAY, linewidth=1.4, linestyle="--", label="universe equal weight")
        ax.axhline(1, color=GRAY, linewidth=0.8)
        ax.set_ylabel("Growth of 1")
        ax.set_title("Hold once versus re-screen monthly")
        ax.legend(frameon=False, loc="upper left")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "32_hold_vs_rescreen.png"), dpi=120)
        plt.close(fig)
        log(f"차트 저장: {OUT}/30_walkforward.png, 31_promise_vs_reality.png, 32_hold_vs_rescreen.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "walkforward_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/walkforward_results.txt")


if __name__ == "__main__":
    main()
