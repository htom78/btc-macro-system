#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_URL = "https://fapi.binance.com"
ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]


def get_json(path: str, params: dict[str, Any]) -> Any:
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "major-futures-system/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1) * 100


def ma(values: list[float], length: int) -> float | None:
    if len(values) < length:
        return None
    return sum(values[-length:]) / length


def classify_symbol(symbol: str, row: dict[str, Any]) -> dict[str, Any]:
    price = row["price"]
    h1_ma20 = row["trend"]["h1_ma20"]
    h1_ma60 = row["trend"]["h1_ma60"]
    h4_ma20 = row["trend"]["h4_ma20"]
    h4_ma60 = row["trend"]["h4_ma60"]
    global_long = row["positioning"]["global_long_account"]
    funding = row["derivatives"]["funding_rate"]
    oi_1h = row["derivatives"]["oi_change_1h_pct"]
    taker = row["positioning"]["taker_buy_sell_ratio"]

    below_h1 = price < h1_ma20 < h1_ma60 if h1_ma20 and h1_ma60 else False
    below_h4 = price < h4_ma20 < h4_ma60 if h4_ma20 and h4_ma60 else False
    crowded_long = global_long is not None and global_long >= 0.66
    heavy_crowded_long = global_long is not None and global_long >= 0.72
    negative_funding = funding is not None and funding < 0
    oi_expanding = oi_1h is not None and oi_1h > 0.5
    buy_effective = taker is not None and taker > 1.05

    scripts: list[dict[str, str]] = []
    if below_h1 or below_h4:
        scripts.append(
            {
                "name": "反抽失败空",
                "status": "preferred" if below_h1 and below_h4 else "watch",
                "direction": "short",
                "reason": "价格仍在 1h/4h 均线结构下方, 先等旧支撑或 1h MA20 反抽失败。",
                "observation_zone": "1h MA20 附近或最近 4h 区间上沿。",
                "invalidation": "重新站回 1h MA20 并保持 15m 更高低点。",
            }
        )
    else:
        scripts.append(
            {
                "name": "趋势跟随多",
                "status": "watch",
                "direction": "long",
                "reason": "价格不再处于完整下压均线结构, 可等待回踩不破。",
                "observation_zone": "1h MA20 回踩不破。",
                "invalidation": "跌回 1h MA20 下方且 15m 结构转弱。",
            }
        )

    reclaim_ready = price > h1_ma20 if h1_ma20 else False
    scripts.append(
        {
            "name": "reclaim 确认多",
            "status": "watch" if reclaim_ready else "blocked",
            "direction": "long",
            "reason": "只有先收回 1h MA20, 再看 ETH/SOL/BNB 的 beta 跟随。",
            "observation_zone": "收回 1h MA20 后第一次回踩。",
            "invalidation": "reclaim 后快速跌回均线下方。",
        }
    )

    if crowded_long and below_h1:
        scripts.append(
            {
                "name": "多头拥挤杀多",
                "status": "alert" if heavy_crowded_long or oi_expanding else "watch",
                "direction": "short",
                "reason": "账户多头拥挤而价格低于 1h 均线, 弱势里更容易杀多。",
                "observation_zone": "反抽失败或跌破 15m 区间下沿。",
                "invalidation": "价格收回 1h MA20 且 taker 买盘持续有效。",
            }
        )

    if negative_funding and crowded_long and buy_effective:
        scripts.append(
            {
                "name": "拥挤反身性观察",
                "status": "watch",
                "direction": "two-way",
                "reason": "负 funding 与多头账户拥挤并存, 需要等价格点火, 不能只看 funding。",
                "observation_zone": "关键位 reclaim 或反抽失败二选一。",
                "invalidation": "OI 下降且价格无法收回关键位。",
            }
        )

    return {
        "primary_bias": "反抽失败空" if below_h1 else "等待 reclaim",
        "risk_note": "多头账户拥挤, 弱势里防杀多" if crowded_long and below_h1 else "等待价格确认, 不抢方向",
        "scripts": scripts,
    }


def fetch_symbol(symbol: str) -> dict[str, Any]:
    premium = get_json("/fapi/v1/premiumIndex", {"symbol": symbol})
    ticker = get_json("/fapi/v1/ticker/24hr", {"symbol": symbol})
    open_interest = get_json("/fapi/v1/openInterest", {"symbol": symbol})
    klines_15m = get_json("/fapi/v1/klines", {"symbol": symbol, "interval": "15m", "limit": 96})
    klines_1h = get_json("/fapi/v1/klines", {"symbol": symbol, "interval": "1h", "limit": 120})
    klines_4h = get_json("/fapi/v1/klines", {"symbol": symbol, "interval": "4h", "limit": 120})

    try:
        oi_hist = get_json("/futures/data/openInterestHist", {"symbol": symbol, "period": "5m", "limit": 30})
    except Exception:  # noqa: BLE001 - Binance data endpoint can be intermittently sparse.
        oi_hist = []
    try:
        global_ratio = get_json("/futures/data/globalLongShortAccountRatio", {"symbol": symbol, "period": "5m", "limit": 1})
    except Exception:  # noqa: BLE001
        global_ratio = []
    try:
        top_ratio = get_json("/futures/data/topLongShortPositionRatio", {"symbol": symbol, "period": "5m", "limit": 1})
    except Exception:  # noqa: BLE001
        top_ratio = []
    try:
        taker_ratio = get_json("/futures/data/takerlongshortRatio", {"symbol": symbol, "period": "5m", "limit": 1})
    except Exception:  # noqa: BLE001
        taker_ratio = []

    closes_1h = [as_float(kline[4]) for kline in klines_1h]
    closes_4h = [as_float(kline[4]) for kline in klines_4h]
    closes_1h = [value for value in closes_1h if value is not None]
    closes_4h = [value for value in closes_4h if value is not None]
    last_15m = klines_15m[-16:]
    range_high = max(as_float(kline[2]) or 0 for kline in last_15m)
    range_low = min(as_float(kline[3]) or 0 for kline in last_15m)
    oi_values = [as_float(item.get("sumOpenInterest")) for item in oi_hist]
    oi_values = [value for value in oi_values if value is not None]
    global_last = global_ratio[-1] if global_ratio else {}
    top_last = top_ratio[-1] if top_ratio else {}
    taker_last = taker_ratio[-1] if taker_ratio else {}

    row: dict[str, Any] = {
        "symbol": symbol,
        "price": as_float(premium.get("markPrice")),
        "pct24": as_float(ticker.get("priceChangePercent")),
        "range_15m_4h": {"high": range_high, "low": range_low},
        "trend": {
            "h1_ma20": ma(closes_1h, 20),
            "h1_ma60": ma(closes_1h, 60),
            "h4_ma20": ma(closes_4h, 20),
            "h4_ma60": ma(closes_4h, 60),
        },
        "derivatives": {
            "funding_rate": as_float(premium.get("lastFundingRate")),
            "open_interest": as_float(open_interest.get("openInterest")),
            "oi_change_1h_pct": pct_change(oi_values[-1], oi_values[-13]) if len(oi_values) >= 13 else None,
            "oi_change_window_pct": pct_change(oi_values[-1], oi_values[0]) if len(oi_values) >= 2 else None,
        },
        "positioning": {
            "global_long_account": as_float(global_last.get("longAccount")),
            "global_short_account": as_float(global_last.get("shortAccount")),
            "top_long_position": as_float(top_last.get("longAccount")),
            "top_short_position": as_float(top_last.get("shortAccount")),
            "taker_buy_sell_ratio": as_float(taker_last.get("buySellRatio")),
        },
    }
    row["strategy"] = classify_symbol(symbol, row)
    return row


def build_payload() -> dict[str, Any]:
    rows = [fetch_symbol(symbol) for symbol in SYMBOLS]
    pct_values = [row["pct24"] for row in rows if row["pct24"] is not None]
    below_h1_count = sum(
        1
        for row in rows
        if row["trend"]["h1_ma20"] is not None and row["price"] is not None and row["price"] < row["trend"]["h1_ma20"]
    )
    beta_rank = sorted(rows, key=lambda row: row["pct24"] if row["pct24"] is not None else 0)
    return {
        "schema_version": "2026-06-05.major-futures.v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "symbols": rows,
        "market_state": {
            "median_24h_pct": statistics.median(pct_values) if pct_values else None,
            "symbols_below_h1_ma20": below_h1_count,
            "direction_anchor": "BTCUSDT",
            "weakest_beta": beta_rank[0]["symbol"] if beta_rank else None,
            "strongest_beta": beta_rank[-1]["symbol"] if beta_rank else None,
            "default_playbook": "价格未收回 1h/4h 均线前, 优先等待反抽失败; BTC 先 reclaim 后, 再考虑 ETH/SOL/BNB beta 跟随。",
        },
        "risk_rules": [
            "单笔风险固定, 不因为高胜率叙事加仓。",
            "BTC 是方向锚; ETH/SOL 是 beta 执行标的; BNB 用来观察抗跌和交易所 beta。",
            "价格低于 1h/4h 均线时不追多, 只等反抽失败或 reclaim 确认。",
            "负 funding 不是做多理由; 必须看到关键位收回、OI 稳定和 taker 买盘有效。",
            "如果账户多头拥挤但价格走弱, 先防杀多。"
        ],
        "disclaimer": "Research and education only. Not financial advice.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Update BTC/ETH/SOL/BNB futures strategy snapshot.")
    parser.add_argument("--output", default=str(ROOT / "data" / "latest.json"))
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    payload = build_payload()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.show:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
