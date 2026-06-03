#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sqlite3
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
DAO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MACRO = ROOT / "btc-macro-system" / "outputs" / "latest.json"
DEFAULT_MNAV_DB = Path("/Volumes/PortableSSD/Codes/mstr-mnav-monitor/data.db")
DEFAULT_MNAV_CSV = Path("/Users/tom/Downloads/mstr-mnav-history-20260522.csv")
DEFAULT_MNAV_SNAPSHOT = DAO_ROOT / "data" / "mnav-snapshot.json"
DEFAULT_MARKET = DAO_ROOT / "data" / "market-structure.json"
DEFAULT_OUT = DAO_ROOT / "data" / "dao-latest.json"


@dataclass(frozen=True)
class Candle:
    ts: int
    low: float
    high: float
    open: float
    close: float
    volume: float

    @property
    def date(self) -> str:
        return datetime.fromtimestamp(self.ts, tz=timezone.utc).date().isoformat()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def public_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return path.name


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def http_json(url: str, timeout: int = 20) -> Any:
    req = Request(
        url,
        headers={
            "User-Agent": "btc-dao-system/0.1 (+local research dashboard)",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_coinbase_candles(days: int = 220) -> tuple[list[Candle], str | None]:
    end = int(time.time())
    start = end - days * 86400
    url = (
        "https://api.exchange.coinbase.com/products/BTC-USD/candles"
        f"?granularity=86400&start={datetime.fromtimestamp(start, tz=timezone.utc).isoformat()}"
        f"&end={datetime.fromtimestamp(end, tz=timezone.utc).isoformat()}"
    )
    try:
        raw = http_json(url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return [], f"coinbase candles unavailable: {exc}"
    candles = [
        Candle(
            ts=int(row[0]),
            low=float(row[1]),
            high=float(row[2]),
            open=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]) if len(row) > 5 else 0.0,
        )
        for row in raw
        if isinstance(row, list) and len(row) >= 5
    ]
    candles.sort(key=lambda item: item.ts)
    return candles, None


def moving_average(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return statistics.fmean(values[-window:])


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains = 0.0
    losses = 0.0
    for index in range(len(values) - period, len(values)):
        move = values[index] - values[index - 1]
        if move >= 0:
            gains += move
        else:
            losses -= move
    if losses == 0:
        return 100.0
    rs = gains / losses
    return 100 - (100 / (1 + rs))


def atr(candles: list[Candle], period: int = 14) -> float | None:
    if len(candles) <= period:
        return None
    trs: list[float] = []
    for prev, cur in zip(candles, candles[1:]):
        trs.append(max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close)))
    if len(trs) < period:
        return None
    return statistics.fmean(trs[-period:])


def build_btc_technical(macro: dict[str, Any], candles: list[Candle]) -> dict[str, Any]:
    macro_btc = macro.get("indicators", {}).get("btc", {})
    if candles:
        closes = [c.close for c in candles]
        latest = candles[-1]
        high_30 = max(c.high for c in candles[-30:]) if len(candles) >= 30 else max(c.high for c in candles)
        low_30 = min(c.low for c in candles[-30:]) if len(candles) >= 30 else min(c.low for c in candles)
        ma95 = moving_average(closes, 95)
        ma200 = moving_average(closes, 200) or macro_btc.get("ma200")
        price = latest.close
        return {
            "source": "coinbase",
            "date": latest.date,
            "price": price,
            "ma95": ma95,
            "ma200": ma200,
            "above_ma95": price > ma95 if ma95 else None,
            "above_ma200": price > ma200 if ma200 else macro_btc.get("above_ma200"),
            "rsi14": rsi(closes, 14),
            "atr14": atr(candles, 14),
            "high_30d": high_30,
            "low_30d": low_30,
            "drawdown_from_30d_high": price / high_30 - 1 if high_30 else None,
        }

    price = macro_btc.get("price")
    ma200 = macro_btc.get("ma200")
    return {
        "source": "macro-latest",
        "date": macro_btc.get("date"),
        "price": price,
        "ma95": None,
        "ma200": ma200,
        "above_ma95": None,
        "above_ma200": macro_btc.get("above_ma200"),
        "rsi14": None,
        "atr14": None,
        "high_30d": None,
        "low_30d": None,
        "drawdown_from_30d_high": None,
    }


def read_mnav_from_db(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "mNAV db not found"
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        snap = conn.execute("SELECT * FROM snapshots ORDER BY ts DESC LIMIT 1").fetchone()
        yield_row = conn.execute("SELECT * FROM btc_yield_history ORDER BY seen_at DESC LIMIT 1").fetchone()
        filings = conn.execute("SELECT * FROM filings ORDER BY seen_at DESC LIMIT 8").fetchall()
    except sqlite3.Error as exc:
        return None, f"mNAV db read error: {exc}"
    finally:
        if conn is not None:
            conn.close()
    if not snap:
        return None, "mNAV db has no snapshots"

    latest_filings = [dict(row) for row in filings]
    sell_filings = [row for row in latest_filings if str(row.get("kind", "")).lower() in {"btc_sale", "sell", "sale"}]
    return {
        "source": "local mstr-mnav-monitor sqlite db",
        "ts": snap["ts"],
        "btc_price": snap["btc_price"],
        "mstr_price": snap["mstr_price"],
        "basic_shares": snap["basic_shares"],
        "diluted_shares": snap["diluted_shares"],
        "holdings_btc": snap["holdings_btc"],
        "btc_nav_usd": snap["btc_nav_usd"],
        "mcap_basic_usd": snap["mcap_basic_usd"],
        "mcap_diluted_usd": snap["mcap_diluted_usd"],
        "mnav_basic": snap["mnav_basic"],
        "mnav_diluted": snap["mnav_diluted"],
        "snapshot_source": snap["source"],
        "btc_yield_ytd_pct": yield_row["ytd_pct"] if yield_row else None,
        "btc_yield_seen_at": yield_row["seen_at"] if yield_row else None,
        "recent_filings": latest_filings,
        "recent_btc_sale_filings": sell_filings,
    }, None


def read_mnav_from_csv(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "mNAV csv not found"
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError as exc:
        return None, f"mNAV csv read error: {exc}"
    if not rows:
        return None, "mNAV csv has no rows"
    row = rows[-1]
    return {
        "source": "local mNAV CSV fallback",
        "ts": row.get("ts"),
        "btc_price": to_float(row.get("btc_price")),
        "mstr_price": to_float(row.get("mstr_price")),
        "basic_shares": to_float(row.get("basic_shares")),
        "diluted_shares": to_float(row.get("diluted_shares")),
        "holdings_btc": to_float(row.get("holdings_btc")),
        "btc_nav_usd": to_float(row.get("btc_nav_usd")),
        "mcap_basic_usd": to_float(row.get("mcap_basic_usd")),
        "mcap_diluted_usd": to_float(row.get("mcap_diluted_usd")),
        "mnav_basic": to_float(row.get("mnav_basic")),
        "mnav_diluted": to_float(row.get("mnav_diluted")),
        "snapshot_source": row.get("source"),
        "btc_yield_ytd_pct": None,
        "btc_yield_seen_at": None,
        "recent_filings": [],
        "recent_btc_sale_filings": [],
    }, None


def read_mnav_from_snapshot(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "mNAV snapshot not found"
    try:
        data = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"mNAV snapshot read error: {exc}"
    if not data.get("ts"):
        return None, "mNAV snapshot missing ts"
    data["source"] = data.get("source") or "sanitized mNAV snapshot"
    data.setdefault("recent_filings", [])
    data.setdefault("recent_btc_sale_filings", [])
    return data, None


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def stale_days(ts: str | None) -> float | None:
    dt = parse_date(ts)
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)


def score_macro(macro: dict[str, Any]) -> dict[str, Any]:
    regime = macro.get("regime", {})
    raw = int(regime.get("score") or 0)
    score = int(clamp(raw, -4, 4))
    label = "supportive" if score >= 2 else "mixed" if score >= -1 else "hostile"
    signals = macro.get("signals", [])
    detail = f"macro score {raw:+d}; regime {regime.get('label', 'unknown')}"
    return {
        "id": "heaven",
        "name": "天",
        "en": "Macro liquidity",
        "score": score,
        "stance": label,
        "detail": detail,
        "inputs": [
            {
                "name": item.get("name"),
                "score": item.get("score"),
                "stance": item.get("stance"),
                "detail": item.get("detail"),
            }
            for item in signals
        ],
    }


def score_market(btc: dict[str, Any], market: dict[str, Any]) -> dict[str, Any]:
    score = 0
    inputs: list[dict[str, Any]] = []

    above_ma95 = btc.get("above_ma95")
    above_ma200 = btc.get("above_ma200")
    rsi14_value = btc.get("rsi14")
    drawdown = btc.get("drawdown_from_30d_high")
    etf_flow = market.get("etf_flow", {})
    etf_total = to_float(etf_flow.get("total_usd_m"))

    if above_ma95 is not None:
        score += 1 if above_ma95 else -1
        inputs.append({"name": "MA95 trend", "score": 1 if above_ma95 else -1, "detail": "above MA95" if above_ma95 else "below MA95"})
    if above_ma200 is not None:
        score += 1 if above_ma200 else -1
        inputs.append({"name": "MA200 regime", "score": 1 if above_ma200 else -1, "detail": "above MA200" if above_ma200 else "below MA200"})
    if rsi14_value is not None:
        rsi_score = 1 if rsi14_value < 25 else -1 if rsi14_value > 75 else 0
        score += rsi_score
        inputs.append({"name": "RSI washout", "score": rsi_score, "detail": f"RSI14 {rsi14_value:.1f}"})
    if drawdown is not None:
        drawdown_score = 1 if drawdown <= -0.18 else -1 if drawdown >= -0.03 else 0
        score += drawdown_score
        inputs.append({"name": "30d drawdown", "score": drawdown_score, "detail": f"{drawdown * 100:.1f}% from 30d high"})
    if etf_total is not None:
        etf_score = 2 if etf_total > 1500 else 1 if etf_total > 0 else -1 if etf_total > -3000 else -2
        score += etf_score
        inputs.append({"name": "ETF flow", "score": etf_score, "detail": f"{etf_total:,.1f} US$m over seed window"})

    final_score = int(clamp(score, -4, 4))
    stance = "supportive" if final_score >= 2 else "mixed" if final_score >= -1 else "hostile"
    return {
        "id": "earth",
        "name": "地",
        "en": "Market structure",
        "score": final_score,
        "stance": stance,
        "detail": "trend, washout, ETF flow, and reserved derivatives inputs",
        "inputs": inputs,
    }


def score_human(mnav: dict[str, Any] | None, mnav_error: str | None) -> dict[str, Any]:
    inputs: list[dict[str, Any]] = []
    score = 0
    if not mnav:
        return {
            "id": "human",
            "name": "人",
            "en": "Treasury reflexivity",
            "score": 0,
            "stance": "mixed",
            "detail": mnav_error or "mNAV source unavailable",
            "inputs": [{"name": "mNAV adapter", "score": 0, "detail": mnav_error or "unavailable"}],
        }

    diluted = to_float(mnav.get("mnav_diluted"))
    if diluted is not None:
        if diluted < 0.9:
            mnav_score = -2
            mnav_detail = "mNAV below 0.9; flywheel disabled and stress is visible"
        elif diluted < 1.0:
            mnav_score = -1
            mnav_detail = "mNAV below 1.0; accretive ATM window closed"
        elif diluted <= 2.5:
            mnav_score = 1
            mnav_detail = "mNAV premium is usable but not euphoric"
        else:
            mnav_score = -1
            mnav_detail = "mNAV premium is elevated; reflexive risk rises"
        score += mnav_score
        inputs.append({"name": "MSTR mNAV", "score": mnav_score, "detail": f"{diluted:.2f}; {mnav_detail}"})

    ytd = to_float(mnav.get("btc_yield_ytd_pct"))
    if ytd is not None:
        yield_score = 1 if ytd > 0 else -1
        score += yield_score
        inputs.append({"name": "BTC yield", "score": yield_score, "detail": f"{ytd:.1f}% YTD"})

    if mnav.get("recent_btc_sale_filings"):
        score -= 4
        inputs.append({"name": "BTC sale filing", "score": -4, "detail": "recent filing classified as BTC sale"})

    age = stale_days(mnav.get("ts"))
    if age is not None and age > 7:
        score -= 1
        inputs.append({"name": "mNAV staleness", "score": -1, "detail": f"snapshot is {age:.1f} days old"})

    final_score = int(clamp(score, -4, 4))
    stance = "supportive" if final_score >= 2 else "mixed" if final_score >= -1 else "hostile"
    return {
        "id": "human",
        "name": "人",
        "en": "Treasury reflexivity",
        "score": final_score,
        "stance": stance,
        "detail": "MSTR mNAV, BTC yield, filings, and source freshness",
        "inputs": inputs,
    }


def decide_state(axes: list[dict[str, Any]], btc: dict[str, Any], mnav: dict[str, Any] | None) -> dict[str, Any]:
    by_id = {axis["id"]: axis for axis in axes}
    total = sum(int(axis["score"]) for axis in axes)
    heaven = int(by_id["heaven"]["score"])
    earth = int(by_id["earth"]["score"])
    human = int(by_id["human"]["score"])
    sale_redline = bool(mnav and mnav.get("recent_btc_sale_filings"))
    drawdown = btc.get("drawdown_from_30d_high")
    rsi_value = btc.get("rsi14")

    if sale_redline:
        key = "redline_freeze"
        zh = "红线冻结"
        action = "MSTR 风险优先，暂停新增风险，复核 8-K。"
    elif total >= 4 and heaven >= 1 and earth >= 1:
        key = "tailwind_attack"
        zh = "顺风进攻"
        action = "战术仓允许恢复 DCA 和回撤买回，核心仓不动。"
    elif total <= -5 or (heaven <= -2 and earth <= -2):
        key = "defensive_pause"
        zh = "逆风防守"
        action = "核心仓不动，战术仓暂停买回，等待 ETF/趋势修复。"
    elif earth <= -2 and rsi_value is not None and rsi_value < 25 and drawdown is not None and drawdown <= -0.12:
        key = "washout_probe"
        zh = "恐慌小探"
        action = "只允许小额、分批、观察性 DCA；不追反弹。"
    elif earth >= 2 and heaven <= 0:
        key = "technical_rebound"
        zh = "技术修复"
        action = "只恢复战术仓的一部分，等待宏观确认。"
    else:
        key = "balanced_hold"
        zh = "平衡持有"
        action = "维持核心仓，战术仓按阶梯，不因单条新闻改变方向。"

    confidence = "medium"
    if any(axis["id"] == "human" and "unavailable" in str(axis.get("detail", "")).lower() for axis in axes):
        confidence = "low"
    if mnav and (stale_days(mnav.get("ts")) or 0) > 7:
        confidence = "medium-low"

    return {
        "key": key,
        "label": zh,
        "score": total,
        "confidence": confidence,
        "action": action,
        "score_formula": "天 + 地 + 人",
    }


def build_ladder(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "zone": "核心仓",
            "default": "60%-70% BTC",
            "rule": "不因 MA95/ETF/MSTR 单点信号清仓；只在个人资产配置层面再平衡。",
        },
        {
            "zone": "战术仓",
            "default": "30%-40% BTC/USDT",
            "rule": "由 Dao 状态决定是否恢复 DCA、暂停买回或按 ATH 阶梯卖出。",
        },
        {
            "zone": "红线",
            "default": "MSTR BTC sale / 强制融资压力",
            "rule": "先复核公司财库飞轮，再决定是否降低 MSTR 暴露；不要把 MSTR 事件机械等同 BTC 本体。",
        },
        {
            "zone": "当前动作",
            "default": state["label"],
            "rule": state["action"],
        },
    ]


def build(args: argparse.Namespace) -> dict[str, Any]:
    macro = read_json(Path(args.macro))
    market = read_json(Path(args.market))
    candles, candle_error = load_coinbase_candles()
    btc = build_btc_technical(macro, candles)

    mnav_path = Path(os.environ.get("MSTR_MNAV_DB", args.mnav_db))
    mnav, mnav_error = read_mnav_from_db(mnav_path)
    if not mnav:
        csv_path = Path(os.environ.get("MSTR_MNAV_CSV", args.mnav_csv))
        mnav, csv_error = read_mnav_from_csv(csv_path)
        mnav_error = f"{mnav_error}; {csv_error}" if mnav_error and csv_error else mnav_error or csv_error
    if not mnav:
        snapshot_path = Path(os.environ.get("MSTR_MNAV_SNAPSHOT", args.mnav_snapshot))
        mnav, snapshot_error = read_mnav_from_snapshot(snapshot_path)
        mnav_error = f"{mnav_error}; {snapshot_error}" if mnav_error and snapshot_error else mnav_error or snapshot_error

    axes = [
        score_macro(macro),
        score_market(btc, market),
        score_human(mnav, mnav_error),
    ]
    state = decide_state(axes, btc, mnav)

    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "state": state,
        "axes": axes,
        "btc": btc,
        "market_structure": market,
        "mstr_reflexivity": mnav or {"source": None, "error": mnav_error},
        "action_ladder": build_ladder(state),
        "source_health": {
            "macro_latest": public_path(Path(args.macro)),
            "market_structure": public_path(Path(args.market)),
            "coinbase_candles": "ok" if not candle_error else candle_error,
            "mnav": "ok" if mnav else mnav_error,
        },
        "disclaimer": "Research and strategy-state dashboard only. Not investment advice.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC Dao state JSON")
    parser.add_argument("--macro", default=str(DEFAULT_MACRO))
    parser.add_argument("--market", default=str(DEFAULT_MARKET))
    parser.add_argument("--mnav-db", default=str(DEFAULT_MNAV_DB))
    parser.add_argument("--mnav-csv", default=str(DEFAULT_MNAV_CSV))
    parser.add_argument("--mnav-snapshot", default=str(DEFAULT_MNAV_SNAPSHOT))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    output = build(args)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"state={output['state']['label']} score={output['state']['score']} confidence={output['state']['confidence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
