"""
pykrx 로 한국 상장 종목의 재무 스냅샷(PER/PBR/배당수익률 + 시가총액) 받아오기

사용법:
    pip install pykrx pandas
    export KRX_ID="..." KRX_PW="..."      # KRX 정보데이터시스템 계정 (pykrx 1.2 이후 필수)
    python scripts/krx_snapshot.py 20260630
    python scripts/krx_snapshot.py 20260630 --market KOSDAQ
    python scripts/krx_snapshot.py --synthetic   # 접속 없이 파이프라인 동작만 확인

결과: scripts/output/krx_snapshot_<date>_<market>.csv
"""
import os
import sys
import time
import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)


def fetch_snapshot(date: str, market: str = "KOSPI") -> pd.DataFrame:
    """특정 일자의 전 종목 펀더멘털 + 시가총액을 한 표로 합친다."""
    from pykrx import stock

    # 휴일이면 직전 영업일로 대체 (alternative=True)
    fund = stock.get_market_fundamental_by_ticker(date, market=market, alternative=True)
    time.sleep(1)                                    # 연속 호출 사이에 쉬어 준다
    cap = stock.get_market_cap_by_ticker(date, market=market, alternative=True)
    time.sleep(1)
    names = pd.Series({t: stock.get_market_ticker_name(t) for t in fund.index}, name="종목명")

    df = fund.join(cap[["종가", "시가총액", "상장주식수"]], how="inner").join(names)
    df.index.name = "티커"
    return df


def synthetic_snapshot(n: int = 60, seed: int = 0) -> pd.DataFrame:
    """pykrx 가 돌려주는 것과 같은 열 구조의 난수 표. 접속 없이 후처리 로직을 시험할 때 쓴다."""
    rng = np.random.default_rng(seed)
    tickers = [f"{rng.integers(0, 999999):06d}" for _ in range(n)]
    eps = rng.normal(2000, 3000, n).round()
    bps = np.abs(rng.normal(30000, 15000, n)).round()
    price = np.abs(rng.normal(40000, 30000, n)).round(-2) + 1000
    per = np.where(eps > 0, price / eps, 0.0)        # KRX 는 적자 종목 PER 을 0 으로 준다
    pbr = np.where(bps > 0, price / bps, 0.0)
    dps = np.where(rng.random(n) < 0.6, rng.integers(0, 1500, n), 0)
    shares = rng.integers(5_000_000, 600_000_000, n)
    df = pd.DataFrame({
        "BPS": bps, "PER": per.round(2), "PBR": pbr.round(2), "EPS": eps,
        "DIV": (dps / price * 100).round(2), "DPS": dps,
        "종가": price, "시가총액": price * shares, "상장주식수": shares,
        "종목명": [f"종목{i:02d}" for i in range(n)],
    }, index=pd.Index(tickers, name="티커"))
    # 실제 데이터에도 섞여 있는 형태: BPS 가 0 인 종목 몇 개
    df.loc[df.index[:3], ["BPS", "PBR"]] = 0
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """KRX 의 '0 = 없음' 관례를 NaN 으로 바꾸고, 스크리닝에 쓸 파생 열을 만든다."""
    out = df.copy()
    out.loc[out["EPS"] <= 0, "PER"] = np.nan      # 적자 종목: PER 0 은 값이 아니라 표시
    out.loc[out["BPS"] <= 0, ["BPS", "PBR"]] = np.nan
    out.loc[out["DPS"] <= 0, "DIV"] = 0.0
    out["시총(억)"] = (out["시가총액"] / 1e8).round(0)
    out["이익수익률"] = (out["EPS"] / out["종가"]).where(out["EPS"] > 0)   # 1/PER
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    synthetic = "--synthetic" in sys.argv
    market = "KOSPI"
    if "--market" in sys.argv:
        market = sys.argv[sys.argv.index("--market") + 1]

    if synthetic:
        raw, date = synthetic_snapshot(), "synthetic"
    else:
        if not args:
            sys.exit("사용법: python scripts/krx_snapshot.py YYYYMMDD [--market KOSPI|KOSDAQ|ALL]")
        if not (os.getenv("KRX_ID") and os.getenv("KRX_PW")):
            sys.exit("KRX_ID, KRX_PW 환경 변수가 필요합니다 (KRX 정보데이터시스템 계정).")
        date = args[0]
        raw = fetch_snapshot(date, market)

    df = clean(raw)
    path = os.path.join(OUT, f"krx_snapshot_{date}_{market}.csv")
    df.to_csv(path, encoding="utf-8-sig")

    print(f"{len(df)} 종목, 열: {list(df.columns)}")
    print(f"PER 결측(적자): {df['PER'].isna().sum()}  BPS 결측: {df['BPS'].isna().sum()}")
    print(df.sort_values("시가총액", ascending=False)
            .head(5)[["종목명", "종가", "시총(억)", "PER", "PBR", "DIV"]].to_string())
    print(f"저장: {path}")


if __name__ == "__main__":
    main()
