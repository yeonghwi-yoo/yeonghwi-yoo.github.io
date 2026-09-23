"""
몬테카를로 — 백테스트 결과가 운이었을 확률 재기 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python scripts/montecarlo.py
    python scripts/montecarlo.py --trials 5000
    python scripts/montecarlo.py --synthetic     # 난수 데이터로 동작 확인

데이터: scripts/data/krx/ 의 월말 스냅샷 22개와 구간별 등락률 21개 (실전 ③ 과 같음)
결과:  scripts/output/montecarlo_results.txt 와 차트 PNG

네 가지를 잰다.
  1) 같은 유니버스에서 20종목을 무작위로 뽑으면 어떤 성적 분포가 나오나
  2) 월별 수익률을 부트스트랩하면 누적 수익률이 얼마나 흔들리나
  3) 월 순서만 섞으면 MDD 가 얼마나 달라지나 (누적은 그대로)
  4) 설정 32개를 돌려 1등을 고를 때, 순전한 운으로 얼마까지 나오나
  5) 시장 방향을 빼고 초과수익만 보면 t값이 얼마나 나오나
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import walkforward as wf                                          # noqa: E402

OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)
lines = []

N_PICK = 20            # 실전 ②·③ 과 같은 종목 수
N_SETTINGS = 32        # 실전 ③ 에서 돌린 설정 개수
SEED = 20260923


def log(s=""):
    print(s)
    lines.append(str(s))


def panel(snaps, rets):
    """구간별 (유니버스 종목의 수익률 배열) 목록. 무작위 추출의 모집단이 된다."""
    out = []
    for d0, d1 in sorted(rets):
        if d0 not in snaps:
            continue
        u = wf.universe(snaps[d0])
        r = rets[(d0, d1)].reindex(u.index).dropna()
        out.append(r.to_numpy())
    return out


def random_paths(pop, trials, rng, n_pick=N_PICK):
    """무작위 n_pick 종목 동일비중을 매 구간 새로 뽑는 경로들. (trials, 구간수)"""
    paths = np.empty((trials, len(pop)))
    for i, arr in enumerate(pop):
        idx = rng.integers(0, len(arr), size=(trials, n_pick))
        paths[:, i] = arr[idx].mean(axis=1)
    return paths


def cum(paths):
    return (1 + paths).prod(axis=-1) - 1


def mdd(path):
    c = np.cumprod(1 + np.asarray(path))
    return float((c / np.maximum.accumulate(c) - 1).min())


def pct_rank(value, sample):
    """value 가 sample 분포에서 상위 몇 %인지 (작을수록 드물다)."""
    return float((sample >= value).mean())


def main():
    synthetic = "--synthetic" in sys.argv
    trials = 2000
    if "--trials" in sys.argv:
        trials = int(sys.argv[sys.argv.index("--trials") + 1])
    rng = np.random.default_rng(SEED)

    snaps, rets = wf.load_snapshots(synthetic)
    tab, _ = wf.build_table(snaps, rets)
    strat = tab["밸류3|20|전체"]                 # 실전 ③ 의 기준 전략
    uni = tab["유니버스 동일비중"]
    cands = [c for c in tab.columns if c != "유니버스 동일비중"]
    best_actual = tab[cands].apply(wf.cum).max()

    log(f"데이터: {'합성' if synthetic else 'KRX 월말 스냅샷'}, 구간 {len(tab)}개, 시행 {trials:,}회")
    log(f"검증 대상: 밸류3 20종목 매달 재선정, 누적 {wf.cum(strat):+.1%} "
        f"(유니버스 {wf.cum(uni):+.1%})")
    log()

    pop = panel(snaps, rets)
    log(f"모집단 크기(구간별 종목 수): 최소 {min(len(a) for a in pop)}, "
        f"최대 {max(len(a) for a in pop)}")
    log()

    # ----- 1. 무작위 20종목 -----
    log("=" * 70)
    log(f"1. 같은 유니버스에서 {N_PICK}종목을 무작위로 뽑으면")
    log("=" * 70)
    rp = random_paths(pop, trials, rng)
    rc = cum(rp)
    s = wf.cum(strat)
    log(f"  무작위 누적수익률 분포: 5% {np.percentile(rc,5):+.1%}  "
        f"25% {np.percentile(rc,25):+.1%}  중앙값 {np.median(rc):+.1%}  "
        f"75% {np.percentile(rc,75):+.1%}  95% {np.percentile(rc,95):+.1%}")
    log(f"  실제 전략 {s:+.1%} 을(를) 무작위가 넘어선 비율: {pct_rank(s, rc):.1%}")
    log(f"  무작위 최고 {rc.max():+.1%}, 최저 {rc.min():+.1%}")
    log()

    # ----- 2. 부트스트랩 -----
    log("=" * 70)
    log("2. 전략의 월별 수익률을 부트스트랩하면 (같은 분포, 다른 추첨)")
    log("=" * 70)
    m = strat.to_numpy()
    bs = cum(m[rng.integers(0, len(m), size=(trials, len(m)))])
    log(f"  누적수익률 90% 구간: {np.percentile(bs,5):+.1%} ~ {np.percentile(bs,95):+.1%}")
    log(f"  중앙값 {np.median(bs):+.1%} (실제 {s:+.1%})")
    log(f"  손실로 끝날 확률: {(bs < 0).mean():.1%}")
    log(f"  유니버스({wf.cum(uni):+.1%})보다 못할 확률: {(bs < wf.cum(uni)).mean():.1%}")
    log()

    # ----- 3. 순서만 섞기 -----
    log("=" * 70)
    log("3. 월 순서만 섞으면 (누적수익률은 그대로, MDD 만 달라짐)")
    log("=" * 70)
    mdds = np.array([mdd(rng.permutation(m)) for _ in range(trials)])
    log(f"  실제 MDD: {mdd(m):.1%}")
    log(f"  섞었을 때 MDD 분포: 5% {np.percentile(mdds,5):.1%}  "
        f"중앙값 {np.median(mdds):.1%}  95% {np.percentile(mdds,95):.1%}")
    log(f"  최악 {mdds.min():.1%}, 최선 {mdds.max():.1%}")
    log(f"  누적수익률은 모두 {wf.cum(strat):+.1%} 로 동일 (곱셈의 순서는 결과를 바꾸지 않는다)")
    log()

    # ----- 4. 32개 중 1등 고르기의 함정 -----
    log("=" * 70)
    log(f"4. 설정 {N_SETTINGS}개를 돌려 1등을 고르면, 순전한 운으로 얼마까지 나오나")
    log("=" * 70)
    best = np.empty(trials)
    block = max(1, 200_000 // (N_SETTINGS * len(pop)))
    done = 0
    while done < trials:
        k = min(block, trials - done)
        paths = random_paths(pop, k * N_SETTINGS, rng)
        best[done:done + k] = cum(paths).reshape(k, N_SETTINGS).max(axis=1)
        done += k
    log(f"  무작위 전략 1개의 누적수익률 중앙값 : {np.median(rc):+.1%}")
    log(f"  무작위 {N_SETTINGS}개 중 1등의 중앙값   : {np.median(best):+.1%}")
    log(f"  그 1등의 90% 구간              : {np.percentile(best,5):+.1%} ~ {np.percentile(best,95):+.1%}")
    log(f"  실전 ③ 의 32개 중 1등 실제값     : {best_actual:+.1%}")
    log(f"  운만으로 그만큼 나올 확률        : {pct_rank(best_actual, best):.1%}")
    log()
    # 이 검정이 공정한지 점검: 실제 32개 설정은 서로 겹치는 종목을 담아 상관이 높다.
    # 무작위 32개도 같은 시장을 타므로 상관이 있지만, 둘이 비슷해야 비교가 성립한다.
    C = tab[cands].corr().to_numpy()
    iu = np.triu_indices_from(C, 1)
    rp32 = random_paths(pop, 32, rng)
    R = np.corrcoef(rp32)
    iu2 = np.triu_indices_from(R, 1)
    log(f"  [검정 공정성] 실제 32개 설정끼리의 월별 상관 평균 {C[iu].mean():.3f}, "
        f"무작위 32개 {R[iu2].mean():.3f}")
    log("   상관이 낮을수록 1등이 더 높이 튄다. 둘이 비슷해야 위 확률을 믿을 수 있다.")
    log()

    # ----- 5. 시장을 빼고 보면 -----
    log("=" * 70)
    log("5. 유니버스 대비 초과수익만 보면 (시장 방향을 지우고)")
    log("=" * 70)
    ex = strat - uni
    t = ex.mean() / ex.std() * np.sqrt(len(ex))
    log(f"  전략의 월별 초과수익: 평균 {ex.mean():+.2%}, 표준편차 {ex.std():.2%}, "
        f"플러스 {int((ex > 0).sum())}/{len(ex)}개월")
    log(f"  t값: {t:.2f}  (보통 2 를 넘어야 '우연이라 보기 어렵다'고 말한다)")
    ex_rand = (rp - uni.to_numpy()).mean(axis=1)
    log(f"  무작위 포트폴리오의 월평균 초과수익: 5% {np.percentile(ex_rand,5):+.2%}, "
        f"중앙값 {np.median(ex_rand):+.2%}, 95% {np.percentile(ex_rand,95):+.2%}")
    log(f"  전략의 {ex.mean():+.2%} 를 무작위가 넘어선 비율: {(ex_rand >= ex.mean()).mean():.1%}")
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        BLUE, ORANGE, GRAY, GREEN = "#1f5fbf", "#c45f00", "#9a9a9a", "#1f8a70"

        fig, ax = plt.subplots(figsize=(11, 4.2))
        ax.hist(rc * 100, bins=60, color=BLUE, alpha=0.75, edgecolor="none")
        ax.axvline(s * 100, color=ORANGE, linewidth=2, label=f"screened portfolio {s*100:.1f}%")
        ax.axvline(wf.cum(uni) * 100, color=GRAY, linewidth=1.6, linestyle="--",
                   label=f"universe {wf.cum(uni)*100:.1f}%")
        ax.set_xlabel("Cumulative return over 21 months (%)")
        ax.set_ylabel("Number of random portfolios")
        ax.set_title(f"{trials:,} random {N_PICK}-stock portfolios from the same universe")
        ax.legend(frameon=False)
        ax.grid(alpha=0.25)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "33_random_portfolios.png"), dpi=120); plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 4))
        ax.hist(bs * 100, bins=60, color=GREEN, alpha=0.75, edgecolor="none")
        ax.axvline(s * 100, color=ORANGE, linewidth=2, label="actual path")
        ax.axvline(0, color=GRAY, linewidth=1.4)
        ax.set_xlabel("Cumulative return (%)")
        ax.set_ylabel("Number of bootstrap paths")
        ax.set_title("Same monthly returns, different draw order and repetition")
        ax.legend(frameon=False)
        ax.grid(alpha=0.25)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "34_bootstrap.png"), dpi=120); plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 4))
        ax.hist(best * 100, bins=60, color=BLUE, alpha=0.7, edgecolor="none",
                label=f"best of {N_SETTINGS} random")
        ax.hist(rc * 100, bins=60, color=GRAY, alpha=0.55, edgecolor="none",
                label="a single random portfolio")
        ax.axvline(best_actual * 100, color=ORANGE, linewidth=2,
                   label=f"actual best of {N_SETTINGS} ({best_actual*100:.1f}%)")
        ax.set_xlabel("Cumulative return over 21 months (%)")
        ax.set_ylabel("Number of trials")
        ax.set_title("Picking the winner out of 32 raises the bar for luck")
        ax.legend(frameon=False)
        ax.grid(alpha=0.25)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "35_best_of_32.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/33_random_portfolios.png, 34_bootstrap.png, 35_best_of_32.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "montecarlo_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/montecarlo_results.txt")


if __name__ == "__main__":
    main()
