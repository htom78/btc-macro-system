#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROD_BASE_URL = "https://fapi.binance.com"
TESTNET_BASE_URL = "https://testnet.binancefuture.com"
LIVE_CONFIRMATION = "I_UNDERSTAND_THIS_CAN_PLACE_REAL_FUTURES_ORDERS"

MAJORS = {
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT",
    "TRXUSDT", "AVAXUSDT", "LINKUSDT", "TONUSDT", "DOTUSDT", "LTCUSDT", "BCHUSDT",
    "UNIUSDT", "AAVEUSDT", "NEARUSDT", "APTUSDT", "SUIUSDT", "OPUSDT", "ARBUSDT",
    "ETCUSDT", "FILUSDT", "ATOMUSDT", "INJUSDT", "HBARUSDT", "XLMUSDT", "MATICUSDT",
    "POLUSDT", "ICPUSDT", "TAOUSDT", "WLDUSDT", "ENAUSDT", "TRUMPUSDT",
}


@dataclass(frozen=True)
class SymbolRules:
    symbol: str
    status: str
    quote_asset: str
    contract_type: str
    tick_size: Decimal
    step_size: Decimal
    min_qty: Decimal
    min_notional: Decimal


@dataclass(frozen=True)
class Candidate:
    symbol: str
    pct24: float
    quote_volume: float
    trades: int
    last: float
    high24: float
    low24: float
    funding_rate: float | None
    oi_change: float | None
    oi_value: float | None
    score: int | None
    label: str


@dataclass(frozen=True)
class Bar:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades: int


@dataclass
class SimEntry:
    level_id: int
    entry: float
    size_pct: float
    stop: float
    open_tick: int
    exit: float | None = None
    exit_tick: int | None = None
    exit_reason: str | None = None

    @property
    def closed(self) -> bool:
        return self.exit is not None


class BinanceClient:
    def __init__(self, base_url: str, api_key: str | None = None, api_secret: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret

    def request_json(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
        timeout: int = 30,
    ) -> Any:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        headers = {
            "User-Agent": "btc-macro-smallcap-cli/0.1 (+local research tool)",
            "Accept": "application/json",
        }
        if signed:
            if not self.api_key or not self.api_secret:
                raise RuntimeError("signed request needs BINANCE_FAPI_KEY and BINANCE_FAPI_SECRET")
            headers["X-MBX-APIKEY"] = self.api_key
            params.setdefault("timestamp", self.server_time_ms())
            params.setdefault("recvWindow", 5000)
            query = urlencode(params, doseq=True)
            signature = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            params["signature"] = signature

        data = None
        url = f"{self.base_url}{path}"
        if method == "GET":
            if params:
                url = f"{url}?{urlencode(params, doseq=True)}"
        else:
            data = urlencode(params, doseq=True).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} failed: HTTP {exc.code} {body}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"{method} {path} failed: {exc}") from exc

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self.request_json("GET", path, params=params)

    def post_signed(self, path: str, params: dict[str, Any]) -> Any:
        return self.request_json("POST", path, params=params, signed=True)

    def server_time_ms(self) -> int:
        try:
            payload = self.request_json("GET", "/fapi/v1/time", timeout=10)
            return int(payload["serverTime"])
        except Exception:
            return int(time.time() * 1000)


def as_float(value: Any, default: float = math.nan) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def money(value: float) -> str:
    if not math.isfinite(value):
        return "--"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:,.0f}"


def pct(value: float | None, digits: int = 2) -> str:
    if value is None or not math.isfinite(value):
        return "--"
    return f"{value * 100:+.{digits}f}%"


def price_text(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "--"
    if value >= 100:
        return f"{value:.2f}"
    if value >= 1:
        return f"{value:.4f}"
    if value >= 0.01:
        return f"{value:.5f}"
    return f"{value:.8f}".rstrip("0").rstrip(".")


def account_pct(value: float, digits: int = 2) -> str:
    if not math.isfinite(value):
        return "--"
    return f"{value:+.{digits}f}%"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def get_filter(symbol: dict[str, Any], filter_type: str) -> dict[str, Any]:
    for item in symbol.get("filters", []):
        if item.get("filterType") == filter_type:
            return item
    return {}


def fetch_rules(client: BinanceClient) -> dict[str, SymbolRules]:
    payload = client.get("/fapi/v1/exchangeInfo")
    rules: dict[str, SymbolRules] = {}
    for item in payload.get("symbols", []):
        symbol = item.get("symbol", "")
        price_filter = get_filter(item, "PRICE_FILTER")
        lot_filter = get_filter(item, "LOT_SIZE")
        min_notional_filter = get_filter(item, "MIN_NOTIONAL")
        if not symbol or not price_filter or not lot_filter:
            continue
        rules[symbol] = SymbolRules(
            symbol=symbol,
            status=item.get("status", ""),
            quote_asset=item.get("quoteAsset", ""),
            contract_type=item.get("contractType", ""),
            tick_size=Decimal(str(price_filter.get("tickSize", "0"))),
            step_size=Decimal(str(lot_filter.get("stepSize", "0"))),
            min_qty=Decimal(str(lot_filter.get("minQty", "0"))),
            min_notional=Decimal(str(min_notional_filter.get("notional", "0"))),
        )
    return rules


def funding_rate(client: BinanceClient, symbol: str) -> float | None:
    rows = client.get("/fapi/v1/fundingRate", {"symbol": symbol, "limit": 3})
    if not isinstance(rows, list) or not rows:
        return None
    return as_float(rows[-1].get("fundingRate"), default=math.nan)


def open_interest_change(client: BinanceClient, symbol: str) -> tuple[float | None, float | None]:
    rows = client.get("/futures/data/openInterestHist", {"symbol": symbol, "period": "1h", "limit": 24})
    if not isinstance(rows, list) or len(rows) < 2:
        return None, None
    first = as_float(rows[0].get("sumOpenInterestValue"))
    last = as_float(rows[-1].get("sumOpenInterestValue"))
    if not math.isfinite(first) or first <= 0 or not math.isfinite(last):
        return None, None
    return (last / first) - 1, last


def pressure_score(pct24: float, quote_volume: float, funding: float | None, oi_change: float | None) -> tuple[int | None, str]:
    has_funding = funding is not None and math.isfinite(funding)
    has_oi = oi_change is not None and math.isfinite(oi_change)
    if not has_funding and not has_oi:
        return None, "price-only"

    momentum = clamp((pct24 - 10) * 1.25, 0, 30)
    volume = clamp(math.log10(max(1, quote_volume / 20_000_000)) * 12, 0, 18)
    funding_crowding = clamp((funding or 0) * 100000, -20, 28) if has_funding else 0
    oi_crowding = clamp((oi_change or 0) * 70, -12, 26) if has_oi else 0
    squeeze_penalty = 16 if has_funding and has_oi and pct24 > 18 and (funding or 0) > 0.0003 and (oi_change or 0) > 0.28 else 0
    score = int(round(clamp(38 + momentum + volume + funding_crowding + oi_crowding - squeeze_penalty, 0, 100)))

    if has_funding and (funding or 0) < -0.0001:
        return score, "short-crowded"
    if has_funding and has_oi and (funding or 0) > 0.0003 and (oi_change or 0) > 0.28:
        return score, "squeeze-risk"
    if has_funding and has_oi and (funding or 0) > 0.00015 and (oi_change or 0) <= 0.06:
        return score, "momentum-decay"
    if has_funding and (funding or 0) > 0.0008:
        return score, "hot-funding"
    if has_oi and (oi_change or 0) > 0.22:
        return score, "oi-expansion"
    return score, "crowding-watch"


def average(values: list[float]) -> float | None:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return None
    return sum(clean) / len(clean)


def rolling_average(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if period <= 0:
        return result
    window_sum = 0.0
    for index, value in enumerate(values):
        window_sum += value
        if index >= period:
            window_sum -= values[index - period]
        if index >= period - 1:
            result[index] = window_sum / period
    return result


def ema_series(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return result
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    multiplier = 2 / (period + 1)
    previous = seed
    for index in range(period, len(values)):
        previous = (values[index] - previous) * multiplier + previous
        result[index] = previous
    return result


def rma_series(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return result
    previous = sum(values[:period]) / period
    result[period - 1] = previous
    for index in range(period, len(values)):
        previous = ((previous * (period - 1)) + values[index]) / period
        result[index] = previous
    return result


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
    result: list[float] = []
    previous_close: float | None = None
    for bar in bars:
        if previous_close is None:
            result.append(bar.high - bar.low)
        else:
            result.append(max(bar.high - bar.low, abs(bar.high - previous_close), abs(bar.low - previous_close)))
        previous_close = bar.close
    return result


def rsi_values(closes: list[float], period: int = 14) -> list[float | None]:
    if len(closes) < period + 1:
        return [None] * len(closes)
    changes = [0.0] + [closes[index] - closes[index - 1] for index in range(1, len(closes))]
    gains = [max(0.0, change) for change in changes]
    losses = [max(0.0, -change) for change in changes]
    avg_gains = rma_series(gains[1:], period)
    avg_losses = rma_series(losses[1:], period)
    result: list[float | None] = [None]
    for gain, loss in zip(avg_gains, avg_losses, strict=False):
        if gain is None or loss is None:
            result.append(None)
        elif loss == 0:
            result.append(100.0)
        else:
            rs = gain / loss
            result.append(100 - (100 / (1 + rs)))
    return result[: len(closes)]


def macd_values(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, float | None | str]:
    fast_ema = ema_series(closes, fast)
    slow_ema = ema_series(closes, slow)
    macd_line: list[float | None] = [
        (fast_value - slow_value) if fast_value is not None and slow_value is not None else None
        for fast_value, slow_value in zip(fast_ema, slow_ema, strict=False)
    ]
    dense_macd = [value for value in macd_line if value is not None]
    signal_dense = ema_series(dense_macd, signal)
    signal_line: list[float | None] = [None] * len(macd_line)
    signal_index = 0
    for index, value in enumerate(macd_line):
        if value is None:
            continue
        signal_line[index] = signal_dense[signal_index]
        signal_index += 1
    histogram = [
        (macd - signal_value) if macd is not None and signal_value is not None else None
        for macd, signal_value in zip(macd_line, signal_line, strict=False)
    ]
    hist = last_number(histogram)
    prev_hist = previous_number(histogram)
    if hist is None:
        state = "warming-up"
    elif hist < 0:
        state = "bearish"
    elif prev_hist is not None and hist < prev_hist:
        state = "momentum-decay"
    else:
        state = "bullish"
    return {
        "macd": last_number(macd_line),
        "signal": last_number(signal_line),
        "histogram": hist,
        "previous_histogram": prev_hist,
        "state": state,
    }


def donchian_values(bars: list[Bar], period: int = 20) -> dict[str, float | None | str]:
    if len(bars) < period:
        return {"period": period, "upper": None, "lower": None, "mid": None, "position": None, "state": "warming-up"}
    window = bars[-period:]
    upper = max(bar.high for bar in window)
    lower = min(bar.low for bar in window)
    mid = (upper + lower) / 2
    close = bars[-1].close
    position = (close - lower) / (upper - lower) if upper > lower else 0.5
    if close < mid:
        state = "below-mid"
    elif position > 0.82:
        state = "near-upper"
    else:
        state = "inside-channel"
    return {"period": period, "upper": upper, "lower": lower, "mid": mid, "position": position, "state": state}


def supertrend_values(bars: list[Bar], period: int = 10, multiplier: float = 3.0) -> dict[str, float | None | str]:
    if len(bars) < period + 2:
        return {"period": period, "multiplier": multiplier, "value": None, "direction": "warming-up"}
    atr = rolling_average(true_ranges(bars), period)
    final_upper: list[float | None] = [None] * len(bars)
    final_lower: list[float | None] = [None] * len(bars)
    trend: list[float | None] = [None] * len(bars)
    direction = "up"
    for index, bar in enumerate(bars):
        atr_value = atr[index]
        if atr_value is None:
            continue
        hl2 = (bar.high + bar.low) / 2
        basic_upper = hl2 + multiplier * atr_value
        basic_lower = hl2 - multiplier * atr_value
        if index == 0 or final_upper[index - 1] is None or final_lower[index - 1] is None:
            final_upper[index] = basic_upper
            final_lower[index] = basic_lower
            trend[index] = basic_lower
            direction = "up"
            continue
        prev_close = bars[index - 1].close
        final_upper[index] = basic_upper if basic_upper < final_upper[index - 1] or prev_close > final_upper[index - 1] else final_upper[index - 1]
        final_lower[index] = basic_lower if basic_lower > final_lower[index - 1] or prev_close < final_lower[index - 1] else final_lower[index - 1]
        previous_trend = trend[index - 1]
        if previous_trend == final_upper[index - 1]:
            if bar.close <= final_upper[index]:
                trend[index] = final_upper[index]
                direction = "down"
            else:
                trend[index] = final_lower[index]
                direction = "up"
        else:
            if bar.close >= final_lower[index]:
                trend[index] = final_lower[index]
                direction = "up"
            else:
                trend[index] = final_upper[index]
                direction = "down"
    return {"period": period, "multiplier": multiplier, "value": last_number(trend), "direction": direction}


def mfi_values(bars: list[Bar], period: int = 14) -> list[float | None]:
    result: list[float | None] = [None] * len(bars)
    typical = [(bar.high + bar.low + bar.close) / 3 for bar in bars]
    raw_flow = [typical[index] * bars[index].volume for index in range(len(bars))]
    for index in range(period, len(bars)):
        positive = 0.0
        negative = 0.0
        for inner in range(index - period + 1, index + 1):
            if typical[inner] > typical[inner - 1]:
                positive += raw_flow[inner]
            elif typical[inner] < typical[inner - 1]:
                negative += raw_flow[inner]
        if negative == 0:
            result[index] = 100.0
        else:
            ratio = positive / negative
            result[index] = 100 - (100 / (1 + ratio))
    return result


def technical_confirmation(bars: list[Bar]) -> dict[str, Any]:
    closes = [bar.close for bar in bars]
    atr_series = rolling_average(true_ranges(bars), 14)
    atr = last_number(atr_series)
    close = closes[-1]
    rsi_series = rsi_values(closes, 14)
    rsi = last_number(rsi_series)
    previous_rsi = previous_number(rsi_series)
    macd = macd_values(closes)
    donchian = donchian_values(bars)
    supertrend = supertrend_values(bars)
    mfi_series = mfi_values(bars, 14)
    mfi = last_number(mfi_series)
    previous_mfi = previous_number(mfi_series)

    score = 0
    checks: list[str] = []
    atr_pct = atr / close if atr is not None and close else None
    if atr_pct is not None:
        if atr_pct >= 0.08:
            score += 16
            checks.append("atr-wide")
        elif atr_pct >= 0.045:
            score += 10
            checks.append("atr-active")
    if rsi is not None:
        if rsi >= 78:
            score += 14
            checks.append("rsi-overheated")
        elif rsi >= 62:
            score += 7
            checks.append("rsi-hot")
        if previous_rsi is not None and rsi < previous_rsi and rsi > 55:
            score += 8
            checks.append("rsi-fading")
    if macd["state"] == "bearish":
        score += 18
        checks.append("macd-bearish")
    elif macd["state"] == "momentum-decay":
        score += 13
        checks.append("macd-decay")
    if donchian["state"] == "below-mid":
        score += 14
        checks.append("donchian-lost-mid")
    elif donchian["state"] == "near-upper":
        score += 6
        checks.append("donchian-upper-risk")
    if supertrend["direction"] == "down":
        score += 18
        checks.append("supertrend-down")
    elif supertrend["direction"] == "up":
        score -= 6
        checks.append("supertrend-up")
    if mfi is not None:
        if mfi >= 82:
            score += 10
            checks.append("mfi-overheated")
        if previous_mfi is not None and mfi < previous_mfi and mfi > 55:
            score += 8
            checks.append("mfi-fading")

    score = int(clamp(score, 0, 100))
    if score >= 65:
        label = "short-confirming"
    elif score >= 42:
        label = "wait-pullback"
    elif supertrend["direction"] == "up":
        label = "trend-still-up"
    else:
        label = "low-confirmation"

    return {
        "close": close,
        "atr": {"period": 14, "value": atr, "pct": atr_pct},
        "rsi": {"period": 14, "value": rsi, "previous": previous_rsi},
        "macd": macd,
        "donchian": donchian,
        "supertrend": supertrend,
        "mfi": {"period": 14, "value": mfi, "previous": previous_mfi},
        "short_bias": {"score": score, "label": label, "checks": checks},
    }


def long_potential_score(
    pct24: float,
    quote_volume: float,
    funding: float | None,
    oi_change: float | None,
    bars: list[Bar],
) -> tuple[int, str, dict[str, float | bool]]:
    close = bars[-1].close if bars else math.nan
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    high72 = max(highs) if highs else math.nan
    low72 = min(lows) if lows else math.nan
    prev_high = max((bar.high for bar in bars[:-6]), default=high72)
    recent_volume = average([bar.quote_volume for bar in bars[-12:]]) or 0
    previous_volume = average([bar.quote_volume for bar in bars[-36:-12]]) or recent_volume or 1
    volume_ratio = recent_volume / previous_volume if previous_volume > 0 else 1
    range72 = (high72 / low72 - 1) if low72 and math.isfinite(low72) else 0
    pullback_from_high = (high72 / close - 1) if close and math.isfinite(close) else 0
    near_breakout = math.isfinite(prev_high) and close >= prev_high * 0.995
    pullback_hold = 0.025 <= pullback_from_high <= 0.14 and close >= low72 + (high72 - low72) * 0.55
    base_build = -2 <= pct24 <= 9 and 0.08 <= range72 <= 0.35 and volume_ratio >= 0.9

    liquidity_score = clamp(math.log10(max(1, quote_volume / 10_000_000)) * 10, 0, 18)
    if pct24 < -6:
        momentum_score = 4
    elif pct24 <= 4:
        momentum_score = 14 + pct24
    elif pct24 <= 18:
        momentum_score = 22
    elif pct24 <= 28:
        momentum_score = 12
    else:
        momentum_score = 3

    has_funding = funding is not None and math.isfinite(funding)
    has_oi = oi_change is not None and math.isfinite(oi_change)
    if not has_funding:
        funding_score = 10
    elif funding <= -0.00005:
        funding_score = 19
    elif funding <= 0.00025:
        funding_score = 20
    elif funding <= 0.0008:
        funding_score = 11
    else:
        funding_score = 3

    if not has_oi:
        oi_score = 9
    elif 0.03 <= oi_change <= 0.24:
        oi_score = 20
    elif 0 <= oi_change < 0.03:
        oi_score = 13
    elif 0.24 < oi_change <= 0.45:
        oi_score = 10
    else:
        oi_score = 4

    volume_score = clamp((volume_ratio - 0.75) * 18, 0, 15)
    structure_score = 0
    if near_breakout:
        structure_score += 12
    if pullback_hold:
        structure_score += 10
    if base_build:
        structure_score += 8
    if range72 > 0.7:
        structure_score -= 8
    if pct24 > 32:
        structure_score -= 12
    score = int(round(clamp(liquidity_score + momentum_score + funding_score + oi_score + volume_score + structure_score, 0, 100)))

    if pct24 > 32 or (has_funding and funding > 0.0012):
        label = "overheated-avoid"
    elif near_breakout and volume_ratio >= 1.05:
        label = "breakout-watch"
    elif pullback_hold:
        label = "pullback-long"
    elif base_build:
        label = "accumulation-watch"
    else:
        label = "early-watch"

    factors: dict[str, float | bool] = {
        "close": close,
        "high72": high72,
        "low72": low72,
        "prev_high": prev_high,
        "range72": range72,
        "pullback_from_high": pullback_from_high,
        "volume_ratio": volume_ratio,
        "near_breakout": near_breakout,
        "pullback_hold": pullback_hold,
        "base_build": base_build,
    }
    return score, label, factors


def scan_long_candidates(client: BinanceClient, args: argparse.Namespace) -> list[dict[str, Any]]:
    rules = fetch_rules(client)
    tickers = client.get("/fapi/v1/ticker/24hr")
    if not isinstance(tickers, list):
        raise RuntimeError("ticker response was not a list")

    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        symbol = str(ticker.get("symbol", ""))
        rule = rules.get(symbol)
        if not rule:
            continue
        if rule.status != "TRADING" or rule.quote_asset != "USDT" or rule.contract_type != "PERPETUAL":
            continue
        if not args.include_majors and symbol in MAJORS:
            continue
        pct24 = as_float(ticker.get("priceChangePercent"))
        quote_volume = as_float(ticker.get("quoteVolume"))
        trades = int(as_float(ticker.get("count"), 0))
        if pct24 < args.min_pct or pct24 > args.max_pct or quote_volume < args.min_quote_volume or trades < args.min_trades:
            continue
        rows.append(
            {
                "symbol": symbol,
                "pct24": pct24,
                "quote_volume": quote_volume,
                "trades": trades,
                "last": as_float(ticker.get("lastPrice")),
                "high24": as_float(ticker.get("highPrice")),
                "low24": as_float(ticker.get("lowPrice")),
            }
        )

    rows.sort(key=lambda item: (abs(item["pct24"] - 8), -item["quote_volume"]))
    rows = rows[: args.prefilter_limit]

    candidates: list[dict[str, Any]] = []
    for row in rows:
        funding: float | None = None
        oi_change: float | None = None
        oi_value: float | None = None
        if not args.no_enrich:
            try:
                funding = funding_rate(client, row["symbol"])
            except Exception:
                funding = None
            try:
                oi_change, oi_value = open_interest_change(client, row["symbol"])
            except Exception:
                oi_change, oi_value = None, None
        try:
            bars = fetch_bars(client, row["symbol"], args.interval, args.klines)
            score, label, factors = long_potential_score(row["pct24"], row["quote_volume"], funding, oi_change, bars)
        except Exception:
            score, label, factors = 0, "kline-error", {}
        candidates.append(
            {
                **row,
                "funding_rate": funding,
                "oi_change": oi_change,
                "oi_value": oi_value,
                "score": score,
                "label": label,
                "factors": factors,
            }
        )

    candidates.sort(key=lambda item: (item["score"], item["quote_volume"]), reverse=True)
    return candidates[: args.limit]


def render_long_candidates(candidates: list[dict[str, Any]], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(candidates, ensure_ascii=False, indent=2))
        return

    print(f"{'SYMBOL':<16} {'24H':>8} {'QUOTE':>11} {'FUNDING':>10} {'OI24':>9} {'VOLX':>6} {'SCORE':>7}  LABEL")
    for item in candidates:
        factors = item.get("factors", {})
        volume_ratio = factors.get("volume_ratio")
        volume_text = f"{volume_ratio:.2f}" if isinstance(volume_ratio, (int, float)) and math.isfinite(volume_ratio) else "--"
        print(
            f"{item['symbol']:<16} {item['pct24']:>+7.2f}% {money(item['quote_volume']):>11} "
            f"{pct(item.get('funding_rate'), 4):>10} {pct(item.get('oi_change'), 1):>9} "
            f"{volume_text:>6} {item['score']:>7}  {item['label']}"
        )


def scan_candidates(client: BinanceClient, args: argparse.Namespace) -> list[Candidate]:
    rules = fetch_rules(client)
    tickers = client.get("/fapi/v1/ticker/24hr")
    if not isinstance(tickers, list):
        raise RuntimeError("ticker response was not a list")

    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        symbol = str(ticker.get("symbol", ""))
        rule = rules.get(symbol)
        if not rule:
            continue
        if rule.status != "TRADING" or rule.quote_asset != "USDT" or rule.contract_type != "PERPETUAL":
            continue
        if not args.include_majors and symbol in MAJORS:
            continue
        pct24 = as_float(ticker.get("priceChangePercent"))
        quote_volume = as_float(ticker.get("quoteVolume"))
        trades = int(as_float(ticker.get("count"), 0))
        if pct24 < args.min_pct or quote_volume < args.min_quote_volume or trades < args.min_trades:
            continue
        rows.append(
            {
                "symbol": symbol,
                "pct24": pct24,
                "quote_volume": quote_volume,
                "trades": trades,
                "last": as_float(ticker.get("lastPrice")),
                "high24": as_float(ticker.get("highPrice")),
                "low24": as_float(ticker.get("lowPrice")),
            }
        )

    rows.sort(key=lambda item: (item["pct24"], item["quote_volume"], item["trades"]), reverse=True)
    rows = rows[: args.limit]

    candidates: list[Candidate] = []
    for row in rows:
        funding: float | None = None
        oi_change: float | None = None
        oi_value: float | None = None
        if not args.no_enrich:
            try:
                funding = funding_rate(client, row["symbol"])
            except Exception:
                funding = None
            try:
                oi_change, oi_value = open_interest_change(client, row["symbol"])
            except Exception:
                oi_change, oi_value = None, None
        score, label = pressure_score(row["pct24"], row["quote_volume"], funding, oi_change)
        candidates.append(Candidate(funding_rate=funding, oi_change=oi_change, oi_value=oi_value, score=score, label=label, **row))

    candidates.sort(key=lambda item: ((item.score if item.score is not None else -1), item.pct24, item.quote_volume), reverse=True)
    return candidates


def render_candidates(candidates: list[Candidate], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps([candidate.__dict__ for candidate in candidates], ensure_ascii=False, indent=2))
        return

    print(f"{'SYMBOL':<16} {'24H':>8} {'QUOTE':>11} {'TRADES':>9} {'FUNDING':>10} {'OI24':>9} {'SCORE':>7}  LABEL")
    for item in candidates:
        score = "--" if item.score is None else str(item.score)
        print(
            f"{item.symbol:<16} {item.pct24:>+7.2f}% {money(item.quote_volume):>11} "
            f"{item.trades:>9} {pct(item.funding_rate, 4):>10} {pct(item.oi_change, 1):>9} {score:>7}  {item.label}"
        )


def fetch_bars(client: BinanceClient, symbol: str, interval: str, limit: int) -> list[Bar]:
    rows = client.get("/fapi/v1/klines", {"symbol": symbol.upper(), "interval": interval, "limit": limit})
    if not isinstance(rows, list):
        raise RuntimeError("klines response was not a list")
    bars: list[Bar] = []
    for row in rows:
        bars.append(
            Bar(
                open_time=int(row[0]),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
                quote_volume=float(row[7]),
                trades=int(row[8]),
            )
        )
    if not bars:
        raise RuntimeError(f"{symbol} returned no klines")
    return bars


def build_levels(anchor: float, step_pct: float, layers: int, stop_pct: float) -> list[dict[str, float]]:
    return [
        {
            "id": index,
            "price": anchor * ((1 + step_pct / 100) ** (index + 1)),
            "stop": anchor * ((1 + step_pct / 100) ** (index + 1)) * (1 + stop_pct / 100),
            "peak": 0.0,
        }
        for index in range(layers)
    ]


def close_entry(entry: SimEntry, price: float, tick: int, reason: str) -> None:
    if entry.closed:
        return
    entry.exit = price
    entry.exit_tick = tick
    entry.exit_reason = reason


def entry_pnl(entry: SimEntry, mark: float) -> float:
    exit_price = entry.exit if entry.exit is not None else mark
    return ((entry.entry - exit_price) / entry.entry) * entry.size_pct


def simulate_strategy(
    bars: list[Bar],
    strategy: str,
    step_pct: float,
    layers: int,
    confirm_pct: float,
    unit_account_pct: float,
    stop_pct: float,
    friction_pct: float,
) -> dict[str, Any]:
    anchor = bars[0].close
    levels = build_levels(anchor, step_pct, layers, stop_pct)
    alerted: set[int] = set()
    opened: set[int] = set()
    entries: list[SimEntry] = []
    events: list[str] = []

    for tick, bar in enumerate(bars):
        for entry in entries:
            if not entry.closed and bar.high >= entry.stop:
                close_entry(entry, entry.stop * (1 + friction_pct / 100), tick, "stop")
                events.append(f"T+{tick} L{entry.level_id + 1} stop {price_text(entry.exit or entry.stop)}")

        for level in levels:
            level_id = int(level["id"])
            if level_id not in alerted and bar.high >= level["price"]:
                alerted.add(level_id)
                level["peak"] = bar.high
                events.append(f"T+{tick} L{level_id + 1} alert {price_text(level['price'])}")
                if strategy == "ladder":
                    opened.add(level_id)
                    entry_price = level["price"]
                    entries.append(SimEntry(level_id, entry_price, unit_account_pct, entry_price * (1 + stop_pct / 100), tick))
                    events.append(f"T+{tick} L{level_id + 1} short {price_text(entry_price)} stop {price_text(entry_price * (1 + stop_pct / 100))}")

            if strategy == "pullback" and level_id in alerted and level_id not in opened:
                level["peak"] = max(level["peak"], bar.high)
                if bar.close <= level["peak"] * (1 - confirm_pct / 100):
                    opened.add(level_id)
                    entry_price = bar.close
                    entries.append(SimEntry(level_id, entry_price, unit_account_pct, entry_price * (1 + stop_pct / 100), tick))
                    events.append(f"T+{tick} L{level_id + 1} pullback short {price_text(entry_price)} stop {price_text(entry_price * (1 + stop_pct / 100))}")

    final = bars[-1].close
    realized = sum(entry_pnl(entry, final) for entry in entries if entry.closed)
    unrealized = sum(entry_pnl(entry, final) for entry in entries if not entry.closed)
    exposure = sum(entry.size_pct for entry in entries if not entry.closed)
    avg_entry = (
        sum(entry.entry * entry.size_pct for entry in entries if not entry.closed) / exposure
        if exposure
        else None
    )
    stopped = sum(1 for entry in entries if entry.closed)
    return {
        "strategy": strategy,
        "anchor": anchor,
        "final": final,
        "alerts": len(alerted),
        "entries": len(entries),
        "active_entries": len(entries) - stopped,
        "stopped_entries": stopped,
        "avg_active_entry": avg_entry,
        "realized_pct": realized,
        "unrealized_pct": unrealized,
        "total_pnl_pct": realized + unrealized,
        "plan_max_loss_pct": layers * unit_account_pct * ((stop_pct + friction_pct) / 100),
        "events": events[-12:],
    }


def run_simulate(client: BinanceClient, args: argparse.Namespace) -> list[dict[str, Any]]:
    symbols: list[str]
    if args.auto:
        scan_args = argparse.Namespace(
            min_pct=args.min_pct,
            min_quote_volume=args.min_quote_volume,
            min_trades=args.min_trades,
            include_majors=False,
            limit=args.auto_limit,
            no_enrich=args.no_enrich,
        )
        symbols = [candidate.symbol for candidate in scan_candidates(client, scan_args)[: args.auto_limit]]
    else:
        symbols = [symbol.upper() for symbol in args.symbol]

    strategies = ["ladder", "pullback"] if args.strategy == "both" else [args.strategy]
    results: list[dict[str, Any]] = []
    for symbol in symbols:
        bars = fetch_bars(client, symbol, args.interval, args.klines)
        for strategy in strategies:
            result = simulate_strategy(
                bars,
                strategy,
                args.step_pct,
                args.layers,
                args.confirm_pct,
                args.unit_account_pct,
                args.stop_pct,
                args.friction_pct,
            )
            result["symbol"] = symbol
            results.append(result)
    return results


def render_simulations(results: list[dict[str, Any]], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print(
        f"{'SYMBOL':<16} {'STRATEGY':<9} {'ALERTS':>6} {'ENTRIES':>7} {'STOP':>5} "
        f"{'AVG_ENTRY':>11} {'FINAL':>11} {'PNL':>9} {'MAX_LOSS':>10}"
    )
    for item in results:
        avg_entry = "--" if item["avg_active_entry"] is None else price_text(item["avg_active_entry"])
        print(
            f"{item['symbol']:<16} {item['strategy']:<9} {item['alerts']:>6} {item['entries']:>7} "
            f"{item['stopped_entries']:>5} {avg_entry:>11} {price_text(item['final']):>11} "
            f"{account_pct(item['total_pnl_pct']):>9} {account_pct(item['plan_max_loss_pct']):>10}"
        )


def run_indicators(client: BinanceClient, args: argparse.Namespace) -> dict[str, Any]:
    symbol = args.symbol.upper()
    bars = fetch_bars(client, symbol, args.interval, args.klines)
    result = technical_confirmation(bars)
    result["symbol"] = symbol
    result["interval"] = args.interval
    result["klines"] = len(bars)
    result["open_time"] = bars[0].open_time
    result["close_time"] = bars[-1].open_time

    if not args.no_enrich:
        funding: float | None
        oi_change: float | None
        oi_value: float | None
        try:
            funding = funding_rate(client, symbol)
        except Exception:
            funding = None
        try:
            oi_change, oi_value = open_interest_change(client, symbol)
        except Exception:
            oi_change, oi_value = None, None
        result["derivatives"] = {
            "funding_rate": funding,
            "oi_change_24h": oi_change,
            "oi_value": oi_value,
        }
    return result


def render_indicators(result: dict[str, Any], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    bias = result["short_bias"]
    print(f"{result['symbol']} technical confirmation ({result['interval']}, {result['klines']} klines)")
    print(f"close        {price_text(result['close'])}")
    print(f"ATR(14)      {price_text(result['atr']['value'])}  {pct(result['atr']['pct'])}")
    print(f"RSI(14)      {result['rsi']['value']:.2f}" if result["rsi"]["value"] is not None else "RSI(14)      --")
    print(
        "MACD         "
        f"{result['macd']['macd']:.6f} / signal {result['macd']['signal']:.6f} / hist {result['macd']['histogram']:.6f} "
        f"({result['macd']['state']})"
        if result["macd"]["macd"] is not None and result["macd"]["signal"] is not None and result["macd"]["histogram"] is not None
        else "MACD         --"
    )
    print(
        "Donchian(20) "
        f"upper {price_text(result['donchian']['upper'])} / mid {price_text(result['donchian']['mid'])} / "
        f"lower {price_text(result['donchian']['lower'])} ({result['donchian']['state']})"
    )
    print(
        "SuperTrend   "
        f"{price_text(result['supertrend']['value'])} ({result['supertrend']['direction']})"
    )
    print(f"MFI(14)      {result['mfi']['value']:.2f}" if result["mfi"]["value"] is not None else "MFI(14)      --")
    if "derivatives" in result:
        derivatives = result["derivatives"]
        print(f"Funding      {pct(derivatives.get('funding_rate'), 4)}")
        print(f"OI 24h       {pct(derivatives.get('oi_change_24h'), 1)}")
    print(f"short bias   {bias['score']}/100  {bias['label']}  {', '.join(bias['checks']) or 'no-checks'}")


def decimal_down(value: Decimal, step: Decimal) -> Decimal:
    if step == 0:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text if "." not in text else text.rstrip("0").rstrip(".")


def build_order_plan(
    rules: SymbolRules,
    anchor: Decimal,
    layers: int,
    step_pct: Decimal,
    stop_pct: Decimal,
    notional: Decimal,
    position_side: str,
) -> list[dict[str, Any]]:
    orders: list[dict[str, Any]] = []
    for index in range(layers):
        raw_entry = anchor * ((Decimal("1") + step_pct / Decimal("100")) ** (index + 1))
        entry_price = decimal_down(raw_entry, rules.tick_size)
        raw_qty = notional / entry_price
        qty = decimal_down(raw_qty, rules.step_size)
        stop_price = decimal_down(entry_price * (Decimal("1") + stop_pct / Decimal("100")), rules.tick_size)
        order_notional = qty * entry_price
        if qty < rules.min_qty:
            raise RuntimeError(f"{rules.symbol} L{index + 1} qty {qty} below minQty {rules.min_qty}")
        if rules.min_notional and order_notional < rules.min_notional:
            raise RuntimeError(f"{rules.symbol} L{index + 1} notional {order_notional} below minNotional {rules.min_notional}")

        client_id_base = f"smcap_{rules.symbol.lower()}_{int(time.time())}_{index + 1}"
        entry: dict[str, Any] = {
            "symbol": rules.symbol,
            "side": "SELL",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": decimal_text(qty),
            "price": decimal_text(entry_price),
            "newClientOrderId": f"{client_id_base}_entry"[:36],
        }
        stop: dict[str, Any] = {
            "symbol": rules.symbol,
            "side": "BUY",
            "type": "STOP_MARKET",
            "quantity": decimal_text(qty),
            "stopPrice": decimal_text(stop_price),
            "workingType": "CONTRACT_PRICE",
            "newClientOrderId": f"{client_id_base}_stop"[:36],
        }
        if position_side == "BOTH":
            stop["reduceOnly"] = "true"
        else:
            entry["positionSide"] = position_side
            stop["positionSide"] = position_side

        orders.append(
            {
                "level": index + 1,
                "notional": decimal_text(order_notional),
                "entry_price": decimal_text(entry_price),
                "stop_price": decimal_text(stop_price),
                "quantity": decimal_text(qty),
                "entry_order": entry,
                "stop_order": stop,
            }
        )
    return orders


def run_plan(client: BinanceClient, args: argparse.Namespace) -> list[dict[str, Any]]:
    rules = fetch_rules(client)
    symbol = args.symbol.upper()
    if symbol not in rules:
        raise RuntimeError(f"{symbol} not found in exchangeInfo")
    ticker = client.get("/fapi/v1/ticker/24hr", {"symbol": symbol})
    anchor = Decimal(str(args.anchor if args.anchor is not None else ticker["lastPrice"]))
    return build_order_plan(
        rules[symbol],
        anchor=anchor,
        layers=args.layers,
        step_pct=Decimal(str(args.step_pct)),
        stop_pct=Decimal(str(args.stop_pct)),
        notional=Decimal(str(args.notional)),
        position_side=args.position_side,
    )


def render_plan(symbol: str, orders: list[dict[str, Any]], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps({"symbol": symbol.upper(), "orders": orders}, ensure_ascii=False, indent=2))
        return
    print(f"{symbol.upper()} ladder short plan")
    print(f"{'L':>2} {'ENTRY SELL':>14} {'QTY':>14} {'NOTIONAL':>12} {'BUY STOP':>14}")
    for item in orders:
        print(
            f"{item['level']:>2} {item['entry_price']:>14} {item['quantity']:>14} "
            f"{item['notional']:>12} {item['stop_price']:>14}"
        )


def run_order(client: BinanceClient, args: argparse.Namespace) -> None:
    orders = run_plan(client, args)
    if not args.live:
        print("DRY RUN: no orders were sent.")
        render_plan(args.symbol, orders, as_json=args.json)
        if not args.json:
            print("\nPayload preview:")
            print(json.dumps(orders, ensure_ascii=False, indent=2))
        return

    if args.confirm_live != LIVE_CONFIRMATION:
        raise RuntimeError(f"live order refused; pass --confirm-live {LIVE_CONFIRMATION}")
    if not args.place_stops_now and not args.entry_only:
        raise RuntimeError("live order refused; choose --entry-only or --place-stops-now explicitly")

    responses: list[dict[str, Any]] = []
    for item in orders:
        responses.append({"level": item["level"], "kind": "entry", "response": client.post_signed("/fapi/v1/order", item["entry_order"])})
        if args.place_stops_now and not args.entry_only:
            responses.append({"level": item["level"], "kind": "stop", "response": client.post_signed("/fapi/v1/order", item["stop_order"])})
    print(json.dumps(responses, ensure_ascii=False, indent=2))


def make_client(args: argparse.Namespace) -> BinanceClient:
    base_url = TESTNET_BASE_URL if getattr(args, "testnet", False) else getattr(args, "base_url", None) or PROD_BASE_URL
    return BinanceClient(
        base_url=base_url,
        api_key=os.environ.get("BINANCE_FAPI_KEY"),
        api_secret=os.environ.get("BINANCE_FAPI_SECRET"),
    )


def add_market_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--min-pct", type=float, default=12.0, help="minimum 24h gain percentage")
    parser.add_argument("--min-quote-volume", type=float, default=20_000_000, help="minimum 24h quote volume in USDT")
    parser.add_argument("--min-trades", type=int, default=20_000, help="minimum 24h trade count")
    parser.add_argument("--no-enrich", action="store_true", help="skip funding and open-interest enrichment")


def add_long_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--min-pct", type=float, default=-3.0, help="minimum 24h change percentage")
    parser.add_argument("--max-pct", type=float, default=24.0, help="maximum 24h change percentage before treating it as too hot")
    parser.add_argument("--min-quote-volume", type=float, default=15_000_000, help="minimum 24h quote volume in USDT")
    parser.add_argument("--min-trades", type=int, default=20_000, help="minimum 24h trade count")
    parser.add_argument("--prefilter-limit", type=int, default=36, help="number of liquid candidates to enrich with klines")
    parser.add_argument("--interval", default="1h", help="kline interval")
    parser.add_argument("--klines", type=int, default=72, help="number of klines used for structure score")
    parser.add_argument("--include-majors", action="store_true", help="include large-cap symbols")
    parser.add_argument("--no-enrich", action="store_true", help="skip funding and open-interest enrichment")


def add_strategy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--step-pct", type=float, default=15.0, help="ladder spacing percentage")
    parser.add_argument("--layers", type=int, default=5, help="number of ladder levels")
    parser.add_argument("--confirm-pct", type=float, default=7.0, help="pullback confirmation percentage from post-alert peak")
    parser.add_argument("--unit-account-pct", type=float, default=1.0, help="account percentage per simulated layer")
    parser.add_argument("--stop-pct", type=float, default=15.0, help="single-layer stop percentage above entry")
    parser.add_argument("--friction-pct", type=float, default=0.4, help="slippage and fee buffer percentage")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Binance USD-M small-cap futures scanner, simulator, and guarded order planner.")
    parser.add_argument("--base-url", default=PROD_BASE_URL, help="Binance Futures base URL")
    parser.add_argument("--testnet", action="store_true", help="use Binance Futures testnet base URL")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="find hot USDT perpetual small-cap candidates")
    add_market_filters(scan)
    scan.add_argument("--limit", type=int, default=12, help="number of candidates to display")
    scan.add_argument("--include-majors", action="store_true", help="include large-cap symbols")
    scan.add_argument("--json", action="store_true", help="print JSON")

    long_scan = sub.add_parser("long-scan", help="find small-cap candidates with early long-side potential")
    add_long_filters(long_scan)
    long_scan.add_argument("--limit", type=int, default=12, help="number of candidates to display")
    long_scan.add_argument("--json", action="store_true", help="print JSON")

    sim = sub.add_parser("simulate", help="simulate ladder and pullback short models on recent klines")
    sim.add_argument("symbol", nargs="*", help="symbol(s), e.g. PLAYUSDT")
    sim.add_argument("--auto", action="store_true", help="scan first and simulate the top candidates")
    sim.add_argument("--auto-limit", type=int, default=5, help="number of scanned symbols to simulate")
    sim.add_argument("--strategy", choices=["ladder", "pullback", "both"], default="both")
    sim.add_argument("--interval", default="1h", help="kline interval")
    sim.add_argument("--klines", type=int, default=72, help="number of klines")
    add_market_filters(sim)
    add_strategy_args(sim)
    sim.add_argument("--json", action="store_true", help="print JSON")

    indicators = sub.add_parser("indicators", help="compute technical confirmation indicators for one symbol")
    indicators.add_argument("symbol", help="symbol, e.g. ALLOUSDT")
    indicators.add_argument("--interval", default="1h", help="kline interval")
    indicators.add_argument("--klines", type=int, default=120, help="number of klines used for indicator windows")
    indicators.add_argument("--no-enrich", action="store_true", help="skip funding and open-interest enrichment")
    indicators.add_argument("--json", action="store_true", help="print JSON")

    plan = sub.add_parser("plan", help="create a dry-run ladder order plan for one symbol")
    plan.add_argument("symbol", help="symbol, e.g. PLAYUSDT")
    plan.add_argument("--anchor", type=str, help="manual anchor price; defaults to latest price")
    plan.add_argument("--notional", type=str, default="20", help="USDT notional per layer")
    plan.add_argument("--position-side", choices=["BOTH", "SHORT"], default="BOTH", help="BOTH for one-way mode, SHORT for hedge mode")
    add_strategy_args(plan)
    plan.add_argument("--json", action="store_true", help="print JSON")

    order = sub.add_parser("order", help="send guarded live orders, or dry-run by default")
    order.add_argument("symbol", help="symbol, e.g. PLAYUSDT")
    order.add_argument("--anchor", type=str, help="manual anchor price; defaults to latest price")
    order.add_argument("--notional", type=str, default="20", help="USDT notional per layer")
    order.add_argument("--position-side", choices=["BOTH", "SHORT"], default="BOTH", help="BOTH for one-way mode, SHORT for hedge mode")
    add_strategy_args(order)
    order.add_argument("--live", action="store_true", help="actually submit signed orders")
    order.add_argument("--entry-only", action="store_true", help="live mode: submit entry LIMIT orders only")
    order.add_argument("--place-stops-now", action="store_true", help="live mode: also submit planned BUY STOP_MARKET orders now")
    order.add_argument("--confirm-live", default="", help="required confirmation phrase for live orders")
    order.add_argument("--json", action="store_true", help="print JSON")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client = make_client(args)
    try:
        if args.command == "scan":
            render_candidates(scan_candidates(client, args), as_json=args.json)
        elif args.command == "long-scan":
            render_long_candidates(scan_long_candidates(client, args), as_json=args.json)
        elif args.command == "simulate":
            if not args.auto and not args.symbol:
                raise RuntimeError("simulate needs at least one symbol, or use --auto")
            render_simulations(run_simulate(client, args), as_json=args.json)
        elif args.command == "indicators":
            render_indicators(run_indicators(client, args), as_json=args.json)
        elif args.command == "plan":
            render_plan(args.symbol, run_plan(client, args), as_json=args.json)
        elif args.command == "order":
            run_order(client, args)
        return 0
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
