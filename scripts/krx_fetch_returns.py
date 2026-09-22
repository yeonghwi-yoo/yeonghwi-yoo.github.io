"""
KRX 월간 수익률 수집 — 스냅샷 날짜 사이의 전 종목 등락률(수정주가 기준, 상장폐지 종목 포함)

사용법:
    export KRX_ID="..." KRX_PW="..."
    python scripts/krx_fetch_returns.py

저장: scripts/data/krx/returns_<from>_<to>.csv.gz
스냅샷(snapshot_YYYYMMDD.csv.gz)이 있는 날짜들을 순서대로 이어 구간을 만든다.
수정주가(adjusted=True)를 쓰므로 액면분할·무상증자가 가짜 수익률로 잡히지 않고,
delist=True 라 구간 중 상장폐지된 종목도 남는다(생존 편향 점검용).
"""
import contextlib
import glob
import io
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "krx")
os.makedirs(OUT, exist_ok=True)


def quiet():
    """pykrx 는 로그인 시 아이디를 stdout 에 찍는다."""
    return contextlib.redirect_stdout(io.StringIO())


def snapshot_dates():
    return sorted(os.path.basename(p).split("_")[1].split(".")[0]
                  for p in glob.glob(os.path.join(OUT, "snapshot_*.csv.gz")))


def fetch_period(d0: str, d1: str) -> pd.DataFrame:
    from pykrx import stock
    with quiet():
        df = stock.get_market_price_change_by_ticker(d0, d1, market="ALL",
                                                     adjusted=True, delist=True)
    return df


def main():
    if not (os.getenv("KRX_ID") and os.getenv("KRX_PW")):
        sys.exit("KRX_ID, KRX_PW 환경 변수가 필요합니다.")
    dates = snapshot_dates()
    if len(dates) < 2:
        sys.exit("스냅샷이 2개 이상 있어야 합니다.")
    for d0, d1 in zip(dates[:-1], dates[1:]):
        path = os.path.join(OUT, f"returns_{d0}_{d1}.csv.gz")
        if os.path.exists(path):
            print(f"{d0}->{d1}: 있음, 건너뜀")
            continue
        try:
            df = fetch_period(d0, d1)
        except Exception as e:                        # noqa: BLE001
            print(f"{d0}->{d1}: 실패 {type(e).__name__}: {str(e)[:80]}")
            continue
        if df.empty:
            print(f"{d0}->{d1}: 빈 표")
            continue
        df.to_csv(path, encoding="utf-8", compression="gzip")
        print(f"{d0}->{d1}: {len(df)}종목, 등락률 중앙값 {df['등락률'].median():.2f}%")
        time.sleep(2)


if __name__ == "__main__":
    main()
