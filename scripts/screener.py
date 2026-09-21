"""
종목 스크리닝 시스템 만들기 (실험 스크립트)

사용법:
    pip install pandas numpy matplotlib
    python scripts/screener.py                 # 공개 스냅샷(2024-12-13, KRX 전 종목)으로 실행
    python scripts/screener.py --file my.csv   # krx_snapshot.py 로 받은 CSV 로 실행
    python scripts/screener.py --synthetic     # 접속 없이 동작 확인

데이터: pykrx 와 같은 열 구조의 전 종목 스냅샷. 기본값은 공개 저장소에 올라온 2024-12-13 자료를 읽는다.
       (종목코드, 종목명, 종가, 시가총액, BPS, PER, PBR, EPS, DIV, DPS)
결과:  scripts/output/screener_results.txt 와 차트 PNG
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from krx_snapshot import clean, synthetic_snapshot

URL = ("https://raw.githubusercontent.com/Jehoshaphat-kr/tdatlib/"
       "f9ad95572bf692f74d5512e3a6e66e65b8ad47dd/snob/market/archive/common/basis.csv")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)
lines = []

MIN_CAP = 1000e8          # 시가총액 하한 1,000억
FIN_WORDS = "지주|홀딩스|금융|은행|증권|보험|캐피탈|카드|생명|화재|인베스트"


def log(s=""):
    print(s)
    lines.append(str(s))


def load(path=None, synthetic=False):
    if synthetic:
        return synthetic_snapshot(400, seed=1)
    df = pd.read_csv(path or URL, dtype={"종목코드": str, "티커": str})
    if "종목코드" in df.columns:
        df = df.rename(columns={"종목코드": "티커"})
    return df.set_index("티커")


def universe(df):
    """스크리닝 대상: 보통주, 시총 하한 이상, 재무 값이 있는 종목."""
    u = df.copy()
    u = u[u.index.str.endswith("0")]                      # 우선주(끝자리 5·7·9 등) 제외
    u = u[~u["종목명"].str.contains("스팩|SPAC", na=False)]
    u = u[u["시가총액"] >= MIN_CAP]
    u = u.dropna(subset=["BPS"])                          # BPS 없음 = 재무 없음
    return u


def rank_score(u, cols, by=None):
    """여러 지표의 순위를 평균한 점수 (0~1, 클수록 좋음). 결측은 최하위로 둔다.

    na_option="top" 이 핵심이다. pandas 의 rank 는 큰 값에 큰 순위를 주므로
    결측을 "top"(순위 1 쪽)에 두어야 점수가 가장 낮아진다. "bottom" 으로 두면
    결측이 가장 높은 순위를 받아 적자 기업이 맨 위로 올라온다.
    """
    src = u.groupby(by)[cols] if by is not None else u[cols]
    ranks = src.rank(pct=True, na_option="top")
    return ranks.mean(axis=1)


def is_financial(names):
    return names.str.contains(FIN_WORDS, na=False)


def main():
    synthetic = "--synthetic" in sys.argv
    path = sys.argv[sys.argv.index("--file") + 1] if "--file" in sys.argv else None
    raw = load(path, synthetic)
    df = clean(raw)
    log(f"데이터: {'합성' if synthetic else (path or '공개 스냅샷 2024-12-13')}, 전체 {len(df)} 종목")
    log()

    # ----- 1. 유니버스 -----
    log("=" * 70)
    log("1. 유니버스 좁히기")
    log("=" * 70)
    n0 = len(df)
    u = df[df.index.str.endswith("0")]; log(f"  우선주 제외        : {n0} -> {len(u)}")
    u = u[~u["종목명"].str.contains("스팩|SPAC", na=False)]; log(f"  스팩 제외          : -> {len(u)}")
    u = u[u["시가총액"] >= MIN_CAP]; log(f"  시총 {MIN_CAP/1e8:,.0f}억 이상   : -> {len(u)}")
    u = u.dropna(subset=["BPS"]); log(f"  재무 없는 종목 제외 : -> {len(u)}")
    log(f"  적자(PER 결측)     : {u['PER'].isna().sum()} 종목은 남긴다 (이익수익률로 음수 처리)")
    log()

    # ----- 2. 지표 하나로 줄 세우기 -----
    log("=" * 70)
    log("2. PBR 하나로 줄 세우면 (낮은 순 상위 20)")
    log("=" * 70)
    top_pbr = u.nsmallest(20, "PBR")
    log(top_pbr[["종목명", "PBR", "PER", "DIV", "시총(억)"]].to_string())
    fin_share = is_financial(top_pbr["종목명"]).mean()
    log(f"  -> 20개 중 금융·지주 이름: {is_financial(top_pbr['종목명']).sum()}개 ({fin_share:.0%})")
    log()

    # ----- 3. 순위 평균 결합 -----
    log("=" * 70)
    log("3. 이익수익률 + 저PBR + 배당수익률, 순위 평균")
    log("=" * 70)
    u = u.assign(_pbr_inv=1 / u["PBR"])                    # 낮을수록 좋은 PBR 을 뒤집는다
    u["점수"] = rank_score(u, ["이익수익률", "_pbr_inv", "DIV"])
    top = u.nlargest(20, "점수")
    log(top[["종목명", "점수", "이익수익률", "PBR", "DIV", "시총(억)"]].round(3).to_string())
    log(f"  -> 20개 중 금융·지주 이름: {is_financial(top['종목명']).sum()}개 "
        f"({is_financial(top['종목명']).mean():.0%})")
    log()

    # ----- 4. 왜 그런가: 업종별 PBR 분포 -----
    log("=" * 70)
    log("4. 금융·지주 vs 나머지의 PBR 분포")
    log("=" * 70)
    fin = is_financial(u["종목명"])
    for label, grp in [("금융·지주", u[fin]), ("나머지", u[~fin])]:
        q = grp["PBR"].quantile([0.1, 0.25, 0.5, 0.75])
        log(f"  {label:6s} {len(grp):4d}개  PBR 10% {q[0.1]:.2f}  25% {q[0.25]:.2f}  "
            f"중앙값 {q[0.5]:.2f}  75% {q[0.75]:.2f}")
    log("  -> 같은 PBR 0.5 라도 금융에서는 보통이고 제조업에서는 드물다")
    log()

    # ----- 5. 그룹 안에서 줄 세우기 -----
    log("=" * 70)
    log("5. 금융·지주와 나머지를 따로 줄 세운 뒤 합치면")
    log("=" * 70)
    u["그룹"] = np.where(fin, "금융·지주", "일반")
    u["점수_그룹내"] = rank_score(u, ["이익수익률", "_pbr_inv", "DIV"], by="그룹")
    top_n = u.nlargest(20, "점수_그룹내")
    log(top_n[["종목명", "그룹", "점수_그룹내", "이익수익률", "PBR", "DIV", "시총(억)"]].round(3).to_string())
    log(f"  -> 20개 중 금융·지주: {is_financial(top_n['종목명']).sum()}개")
    log()

    # ----- 6. 시총 하한을 바꾸면 -----
    log("=" * 70)
    log("6. 시총 하한을 바꾸면 상위 20의 구성이 어떻게 변하나")
    log("=" * 70)
    base = df[df.index.str.endswith("0")]
    base = base[~base["종목명"].str.contains("스팩|SPAC", na=False)].dropna(subset=["BPS"])
    for cap in [300e8, 1000e8, 5000e8, 20000e8]:
        v = base[base["시가총액"] >= cap].copy()
        v["_pbr_inv"] = 1 / v["PBR"]
        s = rank_score(v, ["이익수익률", "_pbr_inv", "DIV"])
        t = v.loc[s.nlargest(20).index]
        log(f"  하한 {cap/1e8:>6,.0f}억: 후보 {len(v):4d}  상위20 중앙 시총 {t['시총(억)'].median():>8,.0f}억  "
            f"금융·지주 {is_financial(t['종목명']).sum():2d}개  적자 {t['PER'].isna().sum()}개")
    log()

    # ----- 차트 -----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        BLUE, ORANGE, GRAY = "#1f5fbf", "#c45f00", "#9a9a9a"

        # 29: PBR 분포 (금융·지주 vs 나머지)
        fig, ax = plt.subplots(figsize=(9, 4.2))
        bins = np.linspace(0, 4, 41)
        ax.hist(u.loc[~fin, "PBR"].clip(upper=4), bins=bins, color=GRAY, alpha=0.9,
                density=True, label=f"Others (n={int((~fin).sum())})")
        ax.hist(u.loc[fin, "PBR"].clip(upper=4), bins=bins, color=BLUE, alpha=0.65,
                density=True, label=f"Financials & holdings (n={int(fin.sum())})")
        ax.set_xlabel("PBR (clipped at 4)")
        ax.set_ylabel("Density")
        ax.set_title("A low PBR means something different by industry")
        ax.legend(frameon=False)
        ax.grid(alpha=0.3, axis="y")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "29_pbr_by_group.png"), dpi=120); plt.close(fig)
        log(f"차트 저장: {OUT}/29_pbr_by_group.png")
    except ImportError:
        log("(matplotlib 미설치: 차트 생략)")

    with open(os.path.join(OUT, "screener_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"결과 저장: {OUT}/screener_results.txt")


if __name__ == "__main__":
    main()
