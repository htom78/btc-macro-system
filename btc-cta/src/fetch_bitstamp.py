"""抓取 Bitstamp BTC/USD 全历史日线 OHLC 数据。

Bitstamp OHLC API:
  GET /api/v2/ohlc/{pair}/?step={秒}&limit={<=1000}&start={unix}
  - step=86400 表示日线
  - limit 单次最多 1000 根
  - 用 start 游标向前翻页,直到没有新数据

数据从 2012-01-01 起。输出 data/btcusd_1d.csv。
"""
from __future__ import annotations

import time
import sys
import requests
import pandas as pd

API = "https://www.bitstamp.net/api/v2/ohlc/btcusd/"
STEP = 86400          # 日线
LIMIT = 1000          # 单次上限
START = 1325376000    # 2012-01-01 00:00 UTC


def fetch_all() -> pd.DataFrame:
    rows: list[dict] = []
    cursor = START
    now = int(time.time())
    page = 0
    while cursor < now:
        params = {"step": STEP, "limit": LIMIT, "start": cursor}
        r = requests.get(API, params=params, timeout=30)
        r.raise_for_status()
        ohlc = r.json().get("data", {}).get("ohlc", [])
        if not ohlc:
            break
        rows.extend(ohlc)
        last_ts = int(ohlc[-1]["timestamp"])
        page += 1
        print(f"  page {page}: {len(ohlc)} bars, "
              f"up to {pd.to_datetime(last_ts, unit='s').date()}", file=sys.stderr)
        if last_ts <= cursor:        # 防御:游标没前进就停
            break
        cursor = last_ts + STEP
        time.sleep(0.4)              # 礼貌限速
    return _to_frame(rows)


def _to_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["timestamp"] = pd.to_numeric(df["timestamp"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="s")
    df = (df.drop_duplicates(subset="timestamp")
            .sort_values("timestamp")
            .reset_index(drop=True))
    return df[["date", "timestamp", "open", "high", "low", "close", "volume"]]


def main() -> None:
    print("拉取 Bitstamp BTC/USD 日线...", file=sys.stderr)
    df = fetch_all()
    out = "data/btcusd_1d.csv"
    df.to_csv(out, index=False)
    # 质量摘要
    print(f"\n总根数: {len(df)}", file=sys.stderr)
    print(f"区间: {df['date'].min().date()} → {df['date'].max().date()}", file=sys.stderr)
    print(f"零成交量天数: {(df['volume'] == 0).sum()}", file=sys.stderr)
    # 缺口检测(日线应连续)
    gaps = df["timestamp"].diff().iloc[1:]
    n_gap = (gaps > STEP).sum()
    print(f"日期缺口数(>1天): {n_gap}", file=sys.stderr)
    print(f"已保存 -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
