"""
KRX 월말 스냅샷 수집 — 지정한 날짜들의 전 종목 펀더멘털 + 시가총액 + 시장 구분을 원본 그대로 저장

사용법:
    export KRX_ID="..." KRX_PW="..."
    python scripts/krx_fetch_monthly.py                       # 2024-12 ~ 직전 월말 + 최근 영업일
    python scripts/krx_fetch_monthly.py 20250131 20250228     # 날짜 직접 지정

저장: scripts/data/krx/snapshot_YYYYMMDD.csv.gz  (KRX 가 주는 값 그대로, 0 처리 전)
이미 있는 날짜는 건너뛴다. 정제(0 → NaN)는 krx_snapshot.clean 을 쓴다.
"""
import contextlib
import io
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "krx")
os.makedirs(OUT, exist_ok=True)


def quiet():
    """pykrx 는 로그인 시 아이디를 stdout 에 찍는다. 감싸서 로그에 남기지 않는다."""
    return contextlib.redirect_stdout(io.StringIO())


def default_dates(start="2024-12", extra=("20260918",)):
    ends = pd.date_range(start, pd.Timestamp.today(), freq="ME")
    ds = [d.strftime("%Y%m%d") for d in ends]
    return ds + [e for e in extra if e not in ds]


def fetch_one(date: str) -> pd.DataFrame:
    from pykrx import stock
    with quiet():
        fund = stock.get_market_fundamental_by_ticker(date, market="ALL", alternative=True)
        time.sleep(1)
        cap = stock.get_market_cap_by_ticker(date, market="ALL", alternative=True)
        time.sleep(1)
        mkt = {}
        for m in ("KOSPI", "KOSDAQ", "KONEX"):
            for t in stock.get_market_ticker_list(date, market=m):
                mkt[t] = m
            time.sleep(1)
        names = pd.Series({t: stock.get_market_ticker_name(t) for t in fund.index}, name="종목명")
    df = fund.join(cap, how="inner").join(names)
    df["시장"] = pd.Series(mkt).reindex(df.index)
    df.index.name = "티커"
    return df


def main():
    if not (os.getenv("KRX_ID") and os.getenv("KRX_PW")):
        sys.exit("KRX_ID, KRX_PW 환경 변수가 필요합니다.")
    dates = [a for a in sys.argv[1:] if a.isdigit()] or default_dates()
    for d in dates:
        path = os.path.join(OUT, f"snapshot_{d}.csv.gz")
        if os.path.exists(path):
            print(f"{d}: 있음, 건너뜀")
            continue
        try:
            df = fetch_one(d)
        except Exception as e:                       # noqa: BLE001
            print(f"{d}: 실패 {type(e).__name__}: {str(e)[:80]}")
            continue
        if df.empty:
            print(f"{d}: 빈 표")
            continue
        df.to_csv(path, encoding="utf-8", compression="gzip")
        print(f"{d}: {len(df)}종목 저장 (KOSPI {int((df['시장']=='KOSPI').sum())}, "
              f"KOSDAQ {int((df['시장']=='KOSDAQ').sum())})")
        time.sleep(2)


if __name__ == "__main__":
    main()
