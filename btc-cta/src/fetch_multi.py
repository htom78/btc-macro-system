"""抓取多币种日线(用 end 参数往前翻页,无需预知起点)。"""
from __future__ import annotations
import sys, time, urllib.request, json
import pandas as pd

API = "https://www.bitstamp.net/api/v2/ohlc/{}/?step=86400&limit=1000&end={}"
PAIRS = ["btcusd", "ethusd", "xrpusd", "ltcusd", "bchusd"]
END0 = 1780704000  # 2026-06-06


def fetch(pair: str) -> pd.DataFrame:
    end, rows = END0, []
    for _ in range(30):
        url = API.format(pair, end)
        d = json.load(urllib.request.urlopen(url, timeout=30))["data"]["ohlc"]
        if not d:
            break
        rows.extend(d)
        earliest = min(int(x["timestamp"]) for x in d)
        if len(d) < 1000:
            break
        end = earliest - 86400
        time.sleep(0.3)
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_numeric(df["timestamp"])
    df["close"] = pd.to_numeric(df["close"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="s")
    return (df.drop_duplicates("timestamp").sort_values("timestamp")
              .set_index("date")["close"].rename(pair))


def main():
    series = []
    for p in PAIRS:
        s = fetch(p)
        print(f"{p}: {len(s)} 根, {s.index.min().date()}→{s.index.max().date()}", file=sys.stderr)
        series.append(s)
    df = pd.concat(series, axis=1)
    df.to_csv("data/multi_close.csv")
    print(f"\n合并 -> data/multi_close.csv  shape={df.shape}", file=sys.stderr)


if __name__ == "__main__":
    main()
