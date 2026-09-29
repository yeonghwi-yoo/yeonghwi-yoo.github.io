"""
추세추종과 손절 규칙 — 손절은 정말 손실을 줄이나 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib finance-datareader
    python scripts/stop_loss.py
    python scripts/stop_loss.py --trials 2000
    python scripts/stop_loss.py --synthetic     # 난수 데이터로 동작 확인

데이터: FinanceDataReader 의 코스피(KS11)·코스닥(KQ11) 일별 종가. 배당 미포함 가격지수.
결과:  scripts/output/stop_loss_results.txt 와 차트 PNG

규칙 (모두 종가로 판단하고 다음 날 수익률부터 반영, 현금 이자 0):
  - 추세 필터: 종가가 200일 이동평균 위면 보유, 아래면 현금
  - 추적 손절 X%: 보유 중 진입 후 최고 종가에서 X% 빠지면 매도,
    현금일 때는 매도 후 최저 종가에서 X% 오르면 재매수 (Alexander 필터 규칙과 같은 꼴)
  - 매매 한 번(편도)마다 비용 COST 를 뺀다

그리고 일별 수익률 순서를 무작위로 섞은 가상의 역사에서 같은 규칙을 돌려,
실제 성과가 '추세가 없는 세상'에서 나오는 분포의 어디쯤인지 잰다.
"""
import argparse
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)
SEED = 20260929
COST = 0.001            # 편도 0.1% (지수 ETF 매매를 가정한 수수료+슬리피지)
STOPS = [0.05, 0.10, 0.15, 0.20]
lines = []


def log(s=""):
    print(s)
    lines.append(str(s))


def load(synthetic=False):
    if synthetic:
        rng = np.random.default_rng(1)
        idx = pd.bdate_range("1996-01-01", "2026-09-17")
        out = {}
        for k in ["KS11", "KQ11"]:
            r = rng.normal(0.0003, 0.015, len(idx))
            out[k] = pd.Series(1000 * np.exp(np.cumsum(r)), index=idx)
        return out
    import FinanceDataReader as fdr
    return {k: fdr.DataReader(k, "1995-01-01")["Close"].dropna() for k in ["KS11", "KQ11"]}


def pos_ma(close, n=200):
    """종가가 n일 이동평균 위면 1. 이동평균이 생기기 전에는 보유(1)로 둔다."""
    ma = close.rolling(n).mean()
    return np.where(ma.isna(), 1.0, (close > ma).astype(float))


def pos_trailing(close, x):
    """추적 손절 x 와 같은 폭의 재진입. 첫날은 보유로 시작."""
    c = np.asarray(close, dtype=float)
    pos = np.empty(len(c))
    inside, ref = True, c[0]
    for t, p in enumerate(c):
        if inside:
            ref = max(ref, p)
            if p <= ref * (1 - x):
                inside, ref = False, p
        else:
            ref = min(ref, p)
            if p >= ref * (1 + x):
                inside, ref = True, p
        pos[t] = 1.0 if inside else 0.0
    return pos


def run(ret, pos, cost=COST):
    """pos[t] 는 t일 종가 기준 결정 → t+1일 수익률에 적용. 결정이 바뀐 날 비용."""
    ret = np.asarray(ret, dtype=float)
    held = np.r_[1.0, pos[:-1]]                 # 첫날은 보유 상태로 출발
    trades = np.abs(np.diff(np.r_[1.0, held]))
    strat = held * ret - trades * cost
    return strat, held, int(trades.sum())


def years(index):
    """달력 기준 햇수. 1998년까지는 토요일에도 장이 열려 거래일 수로 나누면 기간이 부풀려진다."""
    return (index[-1] - index[0]).days / 365.25


def stats(r, yrs):
    r = np.asarray(r)
    eq = np.cumprod(1 + r)
    cagr = eq[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(len(r) / yrs)
    peak = np.maximum.accumulate(np.r_[1.0, eq])[1:]
    mdd = (eq / peak - 1).min()
    return cagr, vol, mdd, eq


def rules(close):
    out = {"200일 이동평균": pos_ma(close)}
    for x in STOPS:
        out[f"추적 손절 {x:.0%}"] = pos_trailing(close, x)
    return out


def table(name, close):
    ret = close.pct_change().fillna(0).to_numpy()
    yrs = years(close.index)
    bh = stats(ret, yrs)
    log(f"\n[{name}] {close.index[0].date()} ~ {close.index[-1].date()}  ({len(ret)}거래일, {yrs:.1f}년)")
    log(f"{'규칙':<14}{'CAGR':>8}{'변동성':>8}{'MDD':>9}{'보유비율':>9}{'매매/년':>8}{'비용/년':>8}")
    log(f"{'매수 후 보유':<14}{bh[0]:8.2%}{bh[1]:8.2%}{bh[2]:9.2%}{1:9.0%}{0:8.1f}{0:8.2%}")
    res = {"매수 후 보유": bh[3]}
    for k, p in rules(close).items():
        s, held, n = run(ret, p)
        c, v, m, eq = stats(s, yrs)
        log(f"{k:<14}{c:8.2%}{v:8.2%}{m:9.2%}{held.mean():9.0%}{n / yrs:8.1f}{n / yrs * COST:8.2%}")
        res[k] = eq
    return ret, res


def shuffle_test(close, trials, rng):
    """일별 수익률 순서를 섞은 가상 역사에서 (규칙 CAGR - 보유 CAGR) 의 분포."""
    ret = close.pct_change().fillna(0).to_numpy()
    base = close.iloc[0]
    yrs = years(close.index)
    bh = stats(ret, yrs)[0]      # 순서를 섞어도 보유 CAGR 은 같다
    names = list(rules(close).keys())
    sims = {k: np.empty(trials) for k in names}
    for i in range(trials):
        r = rng.permutation(ret)
        c = pd.Series(base * np.cumprod(1 + r))
        for k, p in rules(c).items():
            sims[k][i] = stats(run(r, p)[0], yrs)[0] - bh
    actual = {k: stats(run(ret, p)[0], yrs)[0] - bh for k, p in rules(close).items()}
    return actual, sims


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=1000)
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args()
    data = load(a.synthetic)
    rng = np.random.default_rng(SEED)

    log(f"편도 비용 {COST:.1%}, 현금 이자 0, 배당 미포함 가격지수")
    curves = {}
    for k, name in [("KS11", "코스피"), ("KQ11", "코스닥")]:
        close = data[k]
        ret, res = table(name, close)
        curves[k] = (close.index, res)
        # 구간별
        for lo, hi in [("1995", "2008"), ("2009", "2026")]:
            sub = close.loc[lo:hi]
            table(f"{name} {lo}~{hi}", sub)

    # 비용 민감도 (코스피)
    close = data["KS11"]
    ret = close.pct_change().fillna(0).to_numpy()
    yrs = years(close.index)
    log("\n[코스피 비용 민감도] 편도 비용별 CAGR")
    for k, p in rules(close).items():
        row = "  ".join(f"{c:.1%}:{stats(run(ret, p, c)[0], yrs)[0]:6.2%}" for c in [0, 0.001, 0.003])
        log(f"  {k:<14}{row}")

    # 하락장 구간 성적 (코스피)
    log("\n[코스피 주요 하락 구간 수익률] 보유 / 200일선 / 손절10%")
    rl = rules(close)
    s_ma = pd.Series(run(ret, rl["200일 이동평균"])[0], index=close.index)
    s_10 = pd.Series(run(ret, rl["추적 손절 10%"])[0], index=close.index)
    s_bh = pd.Series(ret, index=close.index)
    for lo, hi, lab in [("1997-06", "1998-06", "외환위기"), ("2000-01", "2001-09", "IT 버블 붕괴"),
                        ("2007-11", "2008-10", "금융위기"), ("2011-05", "2011-09", "2011 유럽 위기"),
                        ("2020-01", "2020-03", "코로나"), ("2021-07", "2022-09", "2021~22 하락"),
                        ("2020-04", "2021-06", "코로나 이후 반등")]:
        f = lambda s: (1 + s.loc[lo:hi]).prod() - 1
        log(f"  {lab:<14}{f(s_bh):8.1%}{f(s_ma):8.1%}{f(s_10):8.1%}")

    # 셔플 검정
    log(f"\n[순서 섞기 검정] 코스피 일별 수익률 순서를 {a.trials}번 섞음. 값은 (규칙 CAGR - 보유 CAGR)")
    actual, sims = shuffle_test(close, a.trials, rng)
    for k in actual:
        s = sims[k]
        pct = (s < actual[k]).mean()
        log(f"  {k:<14} 실제 {actual[k]:+6.2%}p   섞은 역사 평균 {s.mean():+6.2%}p "
            f"(5~95% {np.percentile(s, 5):+6.2%}p ~ {np.percentile(s, 95):+6.2%}p)  실제보다 나쁜 비율 {pct:.0%}")

    # 자기상관
    for k, name in [("KS11", "코스피"), ("KQ11", "코스닥")]:
        c = data[k]
        r1 = c.pct_change().dropna()
        rm = c.resample("ME").last().pct_change().dropna()
        log(f"\n[{name}] 일간 수익률 1차 자기상관 {r1.autocorr():+.3f}, 월간 {rm.autocorr():+.3f}, "
            f"연간 일평균 {r1.mean() * 250:.2%}")

    with open(os.path.join(OUT, "stop_loss_results.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        BLUE, ORANGE, GREEN, GRAY, RED = "#1f5fbf", "#c45f00", "#1f8a70", "#9a9a9a", "#b22222"
        idx, res = curves["KS11"]
        fig, ax = plt.subplots(figsize=(11, 5))
        for lab, key, col in [("Buy & hold", "매수 후 보유", GRAY), ("200-day MA", "200일 이동평균", BLUE),
                              ("Trailing stop 10%", "추적 손절 10%", ORANGE), ("Trailing stop 20%", "추적 손절 20%", GREEN)]:
            ax.plot(idx, res[key], color=col, linewidth=1.4 if key != "매수 후 보유" else 1.8, label=lab)
        ax.set_yscale("log"); ax.set_title("KOSPI daily, 1995-2026 (cost 0.1% per trade, cash yields 0)")
        ax.set_ylabel("growth of 1 (log)"); ax.legend(); ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "45_stop_kospi_curve.png"), dpi=120); plt.close(fig)

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
        for ax, key, lab in [(axes[0], "200일 이동평균", "200-day MA"), (axes[1], "추적 손절 10%", "Trailing stop 10%")]:
            ax.hist(sims[key] * 100, bins=40, color=GRAY, alpha=0.8)
            ax.axvline(actual[key] * 100, color=RED, linewidth=2, label="actual KOSPI")
            ax.axvline(0, color="black", linewidth=0.8)
            ax.set_title(f"{lab}: CAGR minus buy & hold, shuffled histories")
            ax.set_xlabel("%p per year"); ax.legend()
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "46_stop_shuffle.png"), dpi=120); plt.close(fig)
    except ImportError:
        pass


if __name__ == "__main__":
    main()
