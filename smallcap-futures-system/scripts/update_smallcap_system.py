#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw_snapshots"
LATEST = DATA_DIR / "latest.json"
SIGNAL_EVENTS = DATA_DIR / "signal_events.jsonl"
FORWARD_OUTCOMES = DATA_DIR / "forward_outcomes.jsonl"
BASE_URL = "https://fapi.binance.com"

MAJORS = {
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT",
    "TRXUSDT", "AVAXUSDT", "LINKUSDT", "TONUSDT", "DOTUSDT", "LTCUSDT", "BCHUSDT",
    "UNIUSDT", "AAVEUSDT", "NEARUSDT", "APTUSDT", "SUIUSDT", "OPUSDT", "ARBUSDT",
    "ETCUSDT", "FILUSDT", "ATOMUSDT", "INJUSDT", "HBARUSDT", "XLMUSDT", "MATICUSDT",
    "POLUSDT", "ICPUSDT", "TAOUSDT", "WLDUSDT", "ENAUSDT", "TRUMPUSDT",
}

MODEL_LABELS = {
    "rush_fade_short": "高位冲高回落做空",
    "fake_break_long": "假跌破反杀做多",
    "whale_long_squeeze": "大户多头挤空",
    "crowded_reversal": "高 Funding/OI 拥挤反转",
}


@dataclass(frozen=True)
class Bar:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def request_json(path: str, params: dict[str, Any] | None = None, timeout: int = 20) -> Any:
    url = f"{BASE_URL}{path}"
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"
    req = Request(
        url,
        headers={
            "User-Agent": "smallcap-futures-system/0.1 (+research only)",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET {path} failed: HTTP {exc.code} {body}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"GET {path} failed: {exc}") from exc


def as_float(value: Any, default: float = math.nan) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    multiplier = 2 / (period + 1)
    prev = seed
    for index in range(period, len(values)):
        prev = (values[index] - prev) * multiplier + prev
        out[index] = prev
    return out


def rolling_average(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0:
        return out
    total = 0.0
    for index, value in enumerate(values):
        total += value
        if index >= period:
            total -= values[index - period]
        if index >= period - 1:
            out[index] = total / period
    return out


def last_number(values: list[float | None]) -> float | None:
    for value in reversed(values):
        if value is not None and math.isfinite(value):
            return value
    return None


def previous_number(values: list[float | None]) -> float | None:
    seen = False
    for value in reversed(values):
        if value is None or not math.isfinite(value):
            continue
        if seen:
            return value
        seen = True
    return None


def true_ranges(bars: list[Bar]) -> list[float]:
    out: list[float] = []
    prev_close: float | None = None
    for bar in bars:
        if prev_close is None:
            out.append(bar.high - bar.low)
        else:
            out.append(max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close)))
        prev_close = bar.close
    return out


def macd_state(closes: list[float]) -> dict[str, Any]:
    fast = ema(closes, 12)
    slow = ema(closes, 26)
    line = [
        (a - b) if a is not None and b is not None else None
        for a, b in zip(fast, slow, strict=False)
    ]
    dense = [value for value in line if value is not None]
    signal_dense = ema(dense, 9)
    signal: list[float | None] = [None] * len(line)
    dense_index = 0
    for index, value in enumerate(line):
        if value is None:
            continue
        signal[index] = signal_dense[dense_index]
        dense_index += 1
    hist = [
        (a - b) if a is not None and b is not None else None
        for a, b in zip(line, signal, strict=False)
    ]
    current = last_number(hist)
    previous = previous_number(hist)
    if current is None:
        state = "warming-up"
    elif current < 0:
        state = "bearish"
    elif previous is not None and current < previous:
        state = "momentum-decay"
    else:
        state = "bullish"
    return {"state": state, "histogram": current, "previous_histogram": previous}


def rsi_value(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for before, after in zip(closes[-period - 1 : -1], closes[-period:], strict=False):
        change = after - before
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def kline_summary(bars: list[Bar]) -> dict[str, Any]:
    closes = [bar.close for bar in bars]
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    window_high = max(highs[-20:]) if len(highs) >= 20 else max(highs)
    window_low = min(lows[-20:]) if len(lows) >= 20 else min(lows)
    mid = (window_high + window_low) / 2
    atr = last_number(rolling_average(true_ranges(bars), 14))
    close = closes[-1]
    return {
        "close": close,
        "last_closed": closes[-2] if len(closes) > 1 else close,
        "high": highs[-1],
        "low": lows[-1],
        "high_20": window_high,
        "low_20": window_low,
        "mid_20": mid,
        "structure": "above-mid" if close >= mid else "below-mid",
        "rsi_14": rsi_value(closes),
        "atr_pct": atr / close if atr and close else None,
        "macd": macd_state(closes),
        "last8": closes[-8:],
    }


def fetch_bars(symbol: str, interval: str, limit: int = 160) -> list[Bar]:
    rows = request_json("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit})
    return [
        Bar(
            open_time=int(row[0]),
            open=as_float(row[1]),
            high=as_float(row[2]),
            low=as_float(row[3]),
            close=as_float(row[4]),
            volume=as_float(row[5]),
            quote_volume=as_float(row[7]),
        )
        for row in rows
    ]


def oi_change(rows: list[dict[str, Any]], lookback: int) -> float | None:
    if len(rows) <= lookback:
        return None
    current = as_float(rows[-1].get("sumOpenInterest"))
    previous = as_float(rows[-1 - lookback].get("sumOpenInterest"))
    if not math.isfinite(current) or not math.isfinite(previous) or previous <= 0:
        return None
    return (current / previous) - 1


def oi_value_change(rows: list[dict[str, Any]], lookback: int) -> float | None:
    if len(rows) <= lookback:
        return None
    current = as_float(rows[-1].get("sumOpenInterestValue"))
    previous = as_float(rows[-1 - lookback].get("sumOpenInterestValue"))
    if not math.isfinite(current) or not math.isfinite(previous) or previous <= 0:
        return None
    return (current / previous) - 1


def safe_last_ratio(path: str, symbol: str) -> dict[str, Any] | None:
    try:
        rows = request_json(path, {"symbol": symbol, "period": "15m", "limit": 8})
    except Exception:
        return None
    if not isinstance(rows, list) or not rows:
        return None
    return rows[-1]


def depth_metrics(symbol: str) -> dict[str, Any]:
    try:
        book = request_json("/fapi/v1/depth", {"symbol": symbol, "limit": 20})
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    bids = [(as_float(price), as_float(qty)) for price, qty in book.get("bids", [])]
    asks = [(as_float(price), as_float(qty)) for price, qty in book.get("asks", [])]
    bids = [(price, qty) for price, qty in bids if math.isfinite(price) and math.isfinite(qty)]
    asks = [(price, qty) for price, qty in asks if math.isfinite(price) and math.isfinite(qty)]
    if not bids or not asks:
        return {"ok": False, "error": "empty depth"}
    best_bid = bids[0][0]
    best_ask = asks[0][0]
    mid = (best_bid + best_ask) / 2
    bid_depth_1pct = sum(price * qty for price, qty in bids if price >= mid * 0.99)
    ask_depth_1pct = sum(price * qty for price, qty in asks if price <= mid * 1.01)
    spread_bps = ((best_ask - best_bid) / mid) * 10_000 if mid else None
    return {
        "ok": True,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid": mid,
        "spread_bps": spread_bps,
        "bid_depth_1pct_usdt": bid_depth_1pct,
        "ask_depth_1pct_usdt": ask_depth_1pct,
        "thin_book": spread_bps is not None and (spread_bps > 20 or min(bid_depth_1pct, ask_depth_1pct) < 50_000),
    }


def pressure_score(pct24: float, quote_volume: float, funding: float | None, oi_change_24h: float | None) -> tuple[int, str]:
    has_funding = funding is not None and math.isfinite(funding)
    has_oi = oi_change_24h is not None and math.isfinite(oi_change_24h)
    momentum = clamp((pct24 - 10) * 1.25, 0, 30)
    volume = clamp(math.log10(max(1, quote_volume / 20_000_000)) * 12, 0, 18)
    funding_crowding = clamp((funding or 0) * 100000, -20, 28) if has_funding else 0
    oi_crowding = clamp((oi_change_24h or 0) * 70, -12, 26) if has_oi else 0
    squeeze_penalty = 16 if has_funding and has_oi and pct24 > 18 and (funding or 0) > 0.0003 and (oi_change_24h or 0) > 0.28 else 0
    score = int(round(clamp(38 + momentum + volume + funding_crowding + oi_crowding - squeeze_penalty, 0, 100)))
    if has_funding and (funding or 0) < -0.0001:
        return score, "short-crowded"
    if has_funding and has_oi and (funding or 0) > 0.0003 and (oi_change_24h or 0) > 0.28:
        return score, "squeeze-risk"
    if has_funding and (funding or 0) > 0.0008:
        return score, "hot-funding"
    if has_oi and (oi_change_24h or 0) > 0.22:
        return score, "oi-expansion"
    return score, "crowding-watch"


def classify_scenarios(item: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    funding = item["derivatives"].get("funding_rate")
    oi_1h = item["derivatives"].get("oi_change_1h")
    oi_24h = item["derivatives"].get("oi_value_change_24h")
    global_short = item["ratios"].get("global_short_account")
    top_long = item["ratios"].get("top_long_position")
    taker_ratio = item["ratios"].get("taker_buy_sell_ratio")
    k15 = item["klines"]["15m"]
    k1h = item["klines"]["1h"]

    if item["pct24"] >= 25 and k15["macd"]["state"] in {"bearish", "momentum-decay"} and (taker_ratio or 1) < 1.05:
        labels.append("rush_fade_candidate")
    if (
        item["pct24"] >= 20
        and funding is not None
        and funding < -0.0005
        and (global_short or 0) >= 0.62
        and (top_long or 0) >= 0.50
        and k15["structure"] == "above-mid"
    ):
        labels.append("whale_long_squeeze_candidate")
    if funding is not None and funding > 0.0006 and (oi_24h or 0) > 0.15 and k15["macd"]["state"] != "bullish":
        labels.append("crowded_reversal_candidate")
    if (
        k15["low"] < k15["low_20"] * 1.01
        and k15["close"] > k15["mid_20"]
        and (oi_1h or 0) >= 0
        and (taker_ratio or 0) > 1
    ):
        labels.append("fake_break_long_candidate")
    if item["pct24"] >= 35 and k1h["rsi_14"] and k1h["rsi_14"] >= 78:
        labels.append("overheated_watch")
    return labels or ["watch"]


def strategy_states(item: dict[str, Any]) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    price = item["last"]
    funding = item["derivatives"].get("funding_rate")
    oi_1h = item["derivatives"].get("oi_change_1h") or 0
    oi_24h = item["derivatives"].get("oi_value_change_24h") or 0
    global_short = item["ratios"].get("global_short_account") or 0
    top_long = item["ratios"].get("top_long_position") or 0
    taker = item["ratios"].get("taker_buy_sell_ratio") or 1
    k5 = item["klines"]["5m"]
    k15 = item["klines"]["15m"]
    k1h = item["klines"]["1h"]
    high24 = item["high24"]
    low24 = item["low24"]
    range24 = high24 - low24 if high24 > low24 else 0
    support = high24 - range24 * 0.20 if range24 else None
    deep_support = high24 - range24 * 0.35 if range24 else None

    rush_watch = item["pct24"] >= 25 and (k1h["rsi_14"] or 0) >= 70
    rush_alert = rush_watch and k15["macd"]["state"] in {"bearish", "momentum-decay"} and price < high24 * 0.985
    rush_confirm = rush_alert and k5["structure"] == "below-mid" and taker < 0.95
    states.append({
        "model": "rush_fade_short",
        "label": MODEL_LABELS["rush_fade_short"],
        "status": "confirm_wait" if rush_alert and not rush_confirm else "paper_entry" if rush_confirm else "watch" if rush_watch else "idle",
        "direction": "short",
        "confidence": int(clamp((item["pct24"] - 20) + (80 - (k15["rsi_14"] or 60)) + (1 - taker) * 25, 0, 100)),
        "reason": "高位涨幅大，15m 动能衰减，等待 5m 跌回中轨下方" if rush_alert else "急涨后观察二次冲高失败",
        "invalidation": f"重新站回 24h 高点附近 {high24:.8g} 且 OI 继续扩张",
        "key_levels": {"high24": high24, "support_estimate": support, "deep_support_estimate": deep_support},
    })

    squeeze_watch = (
        item["pct24"] >= 18
        and funding is not None
        and funding < -0.0004
        and global_short >= 0.62
        and top_long >= 0.50
    )
    squeeze_alert = squeeze_watch and price >= (support or price) and k15["structure"] == "above-mid"
    squeeze_confirm = squeeze_alert and price > high24 * 1.002 and taker > 1.05 and oi_1h >= 0
    states.append({
        "model": "whale_long_squeeze",
        "label": MODEL_LABELS["whale_long_squeeze"],
        "status": "paper_entry" if squeeze_confirm else "alert" if squeeze_alert else "watch" if squeeze_watch else "idle",
        "direction": "long",
        "confidence": int(clamp(abs(funding or 0) * 20000 + global_short * 45 + top_long * 25 + max(0, oi_1h) * 500, 0, 100)),
        "reason": "负资金费率、散户空头拥挤，价格仍守支撑；若突破前高才是挤空确认",
        "invalidation": f"跌破支撑估算 {support:.8g} 后反抽失败" if support else "跌破最新支撑后反抽失败",
        "key_levels": {"squeeze_trigger": high24, "support_estimate": support, "deep_support_estimate": deep_support},
    })

    crowded_watch = funding is not None and funding > 0.0005 and oi_24h > 0.10
    crowded_alert = crowded_watch and k15["macd"]["state"] != "bullish" and taker < 1
    states.append({
        "model": "crowded_reversal",
        "label": MODEL_LABELS["crowded_reversal"],
        "status": "confirm_wait" if crowded_alert else "watch" if crowded_watch else "idle",
        "direction": "short",
        "confidence": int(clamp((funding or 0) * 45000 + oi_24h * 80 + (1 - taker) * 25, 0, 100)),
        "reason": "Funding/OI 拥挤，只有价格结构转弱后才允许观察反转",
        "invalidation": "高 funding 但价格继续稳步抬升，说明趋势强于拥挤",
        "key_levels": {"high24": high24, "mid_15m": k15["mid_20"]},
    })

    fake_break_watch = price >= k15["mid_20"] and k15["low"] <= k15["low_20"] * 1.015
    fake_break_alert = fake_break_watch and oi_1h >= 0 and taker > 1
    states.append({
        "model": "fake_break_long",
        "label": MODEL_LABELS["fake_break_long"],
        "status": "alert" if fake_break_alert else "watch" if fake_break_watch else "idle",
        "direction": "long",
        "confidence": int(clamp((price / k15["mid_20"] - 1) * 500 + max(0, oi_1h) * 400 + (taker - 1) * 35, 0, 100)),
        "reason": "跌破/靠近区间下沿后收回，观察追空是否被套",
        "invalidation": f"重新跌回 15m 中轨 {k15['mid_20']:.8g} 下方并停留",
        "key_levels": {"range_low": k15["low_20"], "range_mid": k15["mid_20"], "range_high": k15["high_20"]},
    })
    return states


def market_universe(limit: int, focus: list[str], min_pct: float, min_quote_volume: float) -> list[dict[str, Any]]:
    exchange = request_json("/fapi/v1/exchangeInfo")
    tradable = {
        row["symbol"]
        for row in exchange.get("symbols", [])
        if row.get("status") == "TRADING" and row.get("quoteAsset") == "USDT" and row.get("contractType") == "PERPETUAL"
    }
    tickers = request_json("/fapi/v1/ticker/24hr")
    rows: list[dict[str, Any]] = []
    for row in tickers:
        symbol = str(row.get("symbol", ""))
        if symbol not in tradable or symbol in MAJORS:
            continue
        pct24 = as_float(row.get("priceChangePercent"))
        quote_volume = as_float(row.get("quoteVolume"))
        trades = int(as_float(row.get("count"), 0))
        if pct24 >= min_pct and quote_volume >= min_quote_volume:
            rows.append({
                "symbol": symbol,
                "pct24": pct24,
                "quote_volume": quote_volume,
                "trades": trades,
                "last": as_float(row.get("lastPrice")),
                "high24": as_float(row.get("highPrice")),
                "low24": as_float(row.get("lowPrice")),
            })
    rows.sort(key=lambda item: (item["pct24"], item["quote_volume"], item["trades"]), reverse=True)
    selected = {item["symbol"]: item for item in rows[:limit]}
    ticker_by_symbol = {str(row.get("symbol", "")): row for row in tickers}
    for symbol in focus:
        normalized = symbol.upper()
        if normalized in selected or normalized not in tradable:
            continue
        row = ticker_by_symbol.get(normalized)
        if not row:
            continue
        selected[normalized] = {
            "symbol": normalized,
            "pct24": as_float(row.get("priceChangePercent")),
            "quote_volume": as_float(row.get("quoteVolume")),
            "trades": int(as_float(row.get("count"), 0)),
            "last": as_float(row.get("lastPrice")),
            "high24": as_float(row.get("highPrice")),
            "low24": as_float(row.get("lowPrice")),
        }
    return list(selected.values())


def enrich(row: dict[str, Any]) -> dict[str, Any]:
    symbol = row["symbol"]
    premium = request_json("/fapi/v1/premiumIndex", {"symbol": symbol})
    oi = request_json("/fapi/v1/openInterest", {"symbol": symbol})
    oi_rows = request_json("/futures/data/openInterestHist", {"symbol": symbol, "period": "15m", "limit": 97})
    global_ratio = safe_last_ratio("/futures/data/globalLongShortAccountRatio", symbol)
    top_position = safe_last_ratio("/futures/data/topLongShortPositionRatio", symbol)
    taker = safe_last_ratio("/futures/data/takerlongshortRatio", symbol)
    k5 = kline_summary(fetch_bars(symbol, "5m"))
    k15 = kline_summary(fetch_bars(symbol, "15m"))
    k1h = kline_summary(fetch_bars(symbol, "1h"))
    depth = depth_metrics(symbol)

    funding = as_float(premium.get("lastFundingRate"))
    oi_24h = oi_value_change(oi_rows, 96)
    score, pressure_label = pressure_score(row["pct24"], row["quote_volume"], funding, oi_24h)
    item = {
        **row,
        "mark": as_float(premium.get("markPrice")),
        "index": as_float(premium.get("indexPrice")),
        "pressure_score": score,
        "pressure_label": pressure_label,
        "derivatives": {
            "funding_rate": funding,
            "open_interest": as_float(oi.get("openInterest")),
            "oi_change_1h": oi_change(oi_rows, 4),
            "oi_change_4h": oi_change(oi_rows, 16),
            "oi_value_change_24h": oi_24h,
        },
        "ratios": {
            "global_long_account": as_float(global_ratio.get("longAccount")) if global_ratio else None,
            "global_short_account": as_float(global_ratio.get("shortAccount")) if global_ratio else None,
            "top_long_position": as_float(top_position.get("longAccount")) if top_position else None,
            "top_short_position": as_float(top_position.get("shortAccount")) if top_position else None,
            "taker_buy_sell_ratio": as_float(taker.get("buySellRatio")) if taker else None,
        },
        "execution": depth,
        "klines": {"5m": k5, "15m": k15, "1h": k1h},
    }
    item["scenarios"] = classify_scenarios(item)
    item["strategy_states"] = strategy_states(item)
    return item


def read_json(path: pathlib.Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def append_jsonl(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def state_index(latest: dict[str, Any]) -> dict[tuple[str, str], str]:
    index: dict[tuple[str, str], str] = {}
    for item in latest.get("candidates", []):
        for state in item.get("strategy_states", []):
            index[(item["symbol"], state["model"])] = state["status"]
    return index


def event_id(symbol: str, model: str, status: str, asof: str) -> str:
    bucket = asof[:16]
    return f"{bucket}:{symbol}:{model}:{status}"


def build_signal_events(previous: dict[str, Any], latest: dict[str, Any]) -> list[dict[str, Any]]:
    prev = state_index(previous)
    existing_ids = {row.get("id") for row in read_jsonl(SIGNAL_EVENTS)}
    rows: list[dict[str, Any]] = []
    asof = latest["updated_at"]
    for item in latest["candidates"]:
        for state in item["strategy_states"]:
            status = state["status"]
            if status in {"idle", "watch"}:
                continue
            key = (item["symbol"], state["model"])
            if prev.get(key) == status:
                continue
            row_id = event_id(item["symbol"], state["model"], status, asof)
            if row_id in existing_ids:
                continue
            rows.append({
                "id": row_id,
                "asof": asof,
                "symbol": item["symbol"],
                "model": state["model"],
                "model_label": state["label"],
                "status": status,
                "direction": state["direction"],
                "confidence": state["confidence"],
                "price": item["last"],
                "funding_rate": item["derivatives"]["funding_rate"],
                "oi_change_1h": item["derivatives"]["oi_change_1h"],
                "global_short_account": item["ratios"]["global_short_account"],
                "top_long_position": item["ratios"]["top_long_position"],
                "taker_buy_sell_ratio": item["ratios"]["taker_buy_sell_ratio"],
                "reason": state["reason"],
                "invalidation": state["invalidation"],
                "key_levels": state["key_levels"],
            })
    return rows


def hours_between(start_iso: str, end_iso: str) -> float:
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    return (end - start).total_seconds() / 3600


def outcome_for(event: dict[str, Any], latest_by_symbol: dict[str, dict[str, Any]], horizon: int, asof: str) -> dict[str, Any] | None:
    item = latest_by_symbol.get(event["symbol"])
    if not item:
        return None
    entry = as_float(event.get("price"))
    current = item["last"]
    if not entry or not math.isfinite(entry) or not math.isfinite(current):
        return None
    raw_return = (current / entry) - 1
    direction_return = raw_return if event.get("direction") == "long" else -raw_return
    return {
        "event_id": event["id"],
        "asof": asof,
        "horizon_hours": horizon,
        "symbol": event["symbol"],
        "model": event["model"],
        "direction": event.get("direction"),
        "entry_price": entry,
        "current_price": current,
        "raw_return": raw_return,
        "direction_return": direction_return,
        "verdict": "favorable" if direction_return > 0.015 else "unfavorable" if direction_return < -0.015 else "flat",
    }


def build_forward_outcomes(latest: dict[str, Any]) -> list[dict[str, Any]]:
    events = read_jsonl(SIGNAL_EVENTS)
    existing = {(row.get("event_id"), row.get("horizon_hours")) for row in read_jsonl(FORWARD_OUTCOMES)}
    latest_by_symbol = {item["symbol"]: item for item in latest.get("candidates", [])}
    rows: list[dict[str, Any]] = []
    asof = latest["updated_at"]
    for event in events:
        age = hours_between(event.get("asof", asof), asof)
        for horizon in (1, 6, 24, 72):
            if age < horizon or (event.get("id"), horizon) in existing:
                continue
            outcome = outcome_for(event, latest_by_symbol, horizon, asof)
            if outcome:
                rows.append(outcome)
    return rows


def maturity_report(latest: dict[str, Any]) -> dict[str, Any]:
    signal_count = len(read_jsonl(SIGNAL_EVENTS))
    outcome_count = len(read_jsonl(FORWARD_OUTCOMES))
    candidate_count = len(latest.get("candidates", []))
    depth_count = sum(1 for item in latest.get("candidates", []) if item.get("execution", {}).get("ok"))
    checks = [
        ("public_data_only", True, "只使用 Binance Futures 公共接口"),
        ("state_machine", True, "每个策略输出状态而不是直接喊单"),
        ("jsonl_history", SIGNAL_EVENTS.exists(), "信号事件可追踪"),
        ("forward_outcomes", FORWARD_OUTCOMES.exists() and outcome_count > 0, "已有前测结果样本"),
        ("risk_first", True, "默认不接私钥、不自动下单"),
        ("coverage", candidate_count >= 10, "候选覆盖至少 10 个标的"),
        ("execution_risk", depth_count >= max(1, candidate_count // 2), "已记录 top-20 深度和 spread 风险"),
    ]
    score = 52
    score += 8 if candidate_count >= 10 else 0
    score += 10 if signal_count > 0 else 0
    score += 10 if outcome_count > 0 else 0
    score += 10 if latest.get("data_health", {}).get("errors", 1) == 0 else 0
    score += 10 if len({state["model"] for item in latest.get("candidates", []) for state in item.get("strategy_states", [])}) >= 4 else 0
    score += 6 if depth_count >= max(1, candidate_count // 2) else 0
    return {"score": min(score, 100), "checks": [{"id": c[0], "ok": c[1], "note": c[2]} for c in checks]}


def write_outputs(latest: dict[str, Any], raw: bool) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    previous = read_json(LATEST, {})
    events = build_signal_events(previous, latest)
    append_jsonl(SIGNAL_EVENTS, events)
    append_jsonl(FORWARD_OUTCOMES, build_forward_outcomes(latest))
    latest["maturity"] = maturity_report(latest)
    LATEST.write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if raw:
        stamp = latest["updated_at"].replace(":", "").replace("-", "").replace("+", "Z")
        (RAW_DIR / f"{stamp}.json").write_text(json.dumps(latest, ensure_ascii=False) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = now_iso()
    focus = [symbol.strip().upper() for symbol in args.focus.split(",") if symbol.strip()]
    rows = market_universe(args.limit, focus, args.min_pct, args.min_quote_volume)
    candidates: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for row in rows:
        try:
            candidates.append(enrich(row))
            time.sleep(args.sleep)
        except Exception as exc:
            errors.append({"symbol": row["symbol"], "error": str(exc)})
    candidates.sort(key=lambda item: (max((state["confidence"] for state in item["strategy_states"]), default=0), item["pressure_score"], item["quote_volume"]), reverse=True)
    latest = {
        "title": "强势小币合约策略系统",
        "updated_at": started,
        "universe": {
            "limit": args.limit,
            "focus": focus,
            "min_pct": args.min_pct,
            "min_quote_volume": args.min_quote_volume,
        },
        "models": MODEL_LABELS,
        "data_health": {
            "errors": len(errors),
            "error_items": errors[:8],
            "candidate_count": len(candidates),
        },
        "candidates": candidates,
        "disclaimer": "Research system only. It is not financial advice and does not place orders.",
    }
    write_outputs(latest, raw=args.raw)
    return latest


def show() -> None:
    latest = read_json(LATEST, {})
    if not latest:
        sys.exit("No latest.json yet. Run update first.")
    print(f"# {latest.get('title')} · {latest.get('updated_at')}")
    print(f"maturity: {latest.get('maturity', {}).get('score', '--')}/100")
    for item in latest.get("candidates", [])[:12]:
        active = [s for s in item.get("strategy_states", []) if s.get("status") not in {"idle", "watch"}]
        active_text = ", ".join(f"{s['label']}:{s['status']}" for s in active) or "watch"
        print(f"{item['symbol']:<14} {item['pct24']:>+7.2f}% score={item['pressure_score']:>3} {item['pressure_label']:<15} {active_text}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a small-cap futures research state system from Binance public data.")
    parser.add_argument("--show", action="store_true", help="show latest output summary")
    parser.add_argument("--limit", type=int, default=20, help="hot symbols to enrich")
    parser.add_argument("--focus", default="ALLOUSDT,LABUSDT", help="comma-separated symbols to always include")
    parser.add_argument("--min-pct", type=float, default=10.0, help="minimum 24h pct gain for hot universe")
    parser.add_argument("--min-quote-volume", type=float, default=20_000_000, help="minimum 24h quote volume")
    parser.add_argument("--sleep", type=float, default=0.08, help="polite delay between enriched symbols")
    parser.add_argument("--raw", action="store_true", help="write a raw timestamped snapshot")
    args = parser.parse_args()
    try:
        if args.show:
            show()
            return 0
        latest = run(args)
        print(f"updated {LATEST} with {len(latest['candidates'])} candidates")
        print(f"maturity {latest['maturity']['score']}/100")
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
