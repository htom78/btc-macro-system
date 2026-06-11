#!/usr/bin/env python3
"""Agent harness layer for the Binance small-cap futures system."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SYSTEM_ROOT = SCRIPT_DIR.parent
DATA_DIR = SYSTEM_ROOT / "data"
DEFAULT_CONFIG = SYSTEM_ROOT / "harness" / "config.json"
LATEST_PATH = DATA_DIR / "latest.json"
STATE_PATH = DATA_DIR / "harness_state.json"
DECISIONS_PATH = DATA_DIR / "harness_decisions.jsonl"

sys.path.insert(0, str(SCRIPT_DIR))
import update_smallcap_system as updater  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def as_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def zone_contains(price: float | None, zone: list[float] | None) -> bool:
    if price is None or not zone or len(zone) != 2:
        return False
    low, high = min(zone), max(zone)
    return low <= price <= high


def zone_text(zone: list[float] | None) -> str:
    if not zone or len(zone) != 2:
        return "n/a"
    if zone[0] == zone[1]:
        return f"{zone[0]:g}"
    return f"{zone[0]:g}-{zone[1]:g}"


def metric(item: dict[str, Any]) -> dict[str, Any]:
    derivatives = item.get("derivatives") or {}
    ratios = item.get("ratios") or {}
    klines = item.get("klines") or {}
    k5 = klines.get("5m") or {}
    k15 = klines.get("15m") or {}
    k1h = klines.get("1h") or {}
    return {
        "price": as_float(item.get("last")),
        "pct24": as_float(item.get("pct24")),
        "funding": as_float(derivatives.get("funding_rate")),
        "oi_change_1h": as_float(derivatives.get("oi_change_1h")),
        "oi_change_4h": as_float(derivatives.get("oi_change_4h")),
        "global_long_account": as_float(ratios.get("global_long_account")),
        "global_short_account": as_float(ratios.get("global_short_account")),
        "top_long_position": as_float(ratios.get("top_long_position")),
        "taker_buy_sell_ratio": as_float(ratios.get("taker_buy_sell_ratio")),
        "close_5m": as_float(k5.get("close")),
        "high_5m_20": as_float(k5.get("high_20")),
        "low_5m_20": as_float(k5.get("low_20")),
        "close_15m": as_float(k15.get("close")),
        "change_15m": as_float(k15.get("change")),
        "high_15m_20": as_float(k15.get("high_20")),
        "low_15m_20": as_float(k15.get("low_20")),
        "high_1h_20": as_float(k1h.get("high_20")),
        "low_1h_20": as_float(k1h.get("low_20")),
    }


def is_short_crowded(m: dict[str, Any], thresholds: dict[str, float]) -> bool:
    global_short = m.get("global_short_account")
    funding = m.get("funding")
    return (
        global_short is not None
        and global_short >= thresholds["short_crowded_account_ratio"]
        and funding is not None
        and funding <= thresholds["negative_funding"]
    )


def base_decision(symbol: str, item: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    m = metric(item)
    return {
        "symbol": symbol,
        "decision": "DONT_NOTIFY",
        "event_type": "no_actionable_event",
        "current_price": m["price"],
        "funding": m["funding"],
        "oi_trend": {
            "oi_change_1h": m["oi_change_1h"],
            "oi_change_4h": m["oi_change_4h"],
        },
        "long_short_context": {
            "global_short_account": m["global_short_account"],
            "top_long_position": m["top_long_position"],
            "taker_buy_sell_ratio": m["taker_buy_sell_ratio"],
        },
        "reason": "No configured thesis validation, invalidation, or learning event is confirmed.",
        "observation_zone": "wait",
        "risk_note": "Not financial advice; use as research workflow output only.",
        "thesis": cfg.get("thesis"),
    }


def notify(decision: dict[str, Any], event_type: str, reason: str, observation_zone: str) -> dict[str, Any]:
    decision.update(
        {
            "decision": "NOTIFY",
            "event_type": event_type,
            "reason": reason,
            "observation_zone": observation_zone,
        }
    )
    return decision


def classify_allo(symbol: str, item: dict[str, Any], cfg: dict[str, Any], thresholds: dict[str, float]) -> dict[str, Any]:
    d = base_decision(symbol, item, cfg)
    m = metric(item)
    zones = cfg.get("zones") or {}
    price = m["price"]
    oi1h = m["oi_change_1h"]
    taker = m["taker_buy_sell_ratio"]
    high_1h_20 = m["high_1h_20"]

    in_rebound = zone_contains(price, zones.get("rebound_lower")) or zone_contains(price, zones.get("rebound_upper"))
    if in_rebound and taker is not None and taker <= thresholds["taker_sell_ratio"] and (oi1h or 0) >= thresholds["oi_stable_min"]:
        return notify(
            d,
            "bearish_rebound_rollover",
            "Price is back in the configured rebound zone while taker flow is sell-effective and OI is not flushing out.",
            f"short observation: {zone_text(zones.get('rebound_lower'))} / {zone_text(zones.get('rebound_upper'))}",
        )

    if price is not None and price >= 0.218 and taker is not None and taker >= thresholds["taker_buy_ratio"] and (oi1h or 0) >= thresholds["oi_stable_min"]:
        return notify(
            d,
            "short_momentum_weakening",
            "Price reclaimed 0.2050 and 0.2180 with buy-effective flow, weakening the post-break short thesis.",
            "avoid fresh short until 0.2180 reclaim fails again",
        )

    if price is not None and price <= 0.205 and is_short_crowded(m, thresholds) and (oi1h or 0) >= thresholds["oi_stable_min"]:
        return notify(
            d,
            "crowded_short_squeeze_risk",
            "Funding and account positioning are short-crowded while price is no longer extending down cleanly.",
            "watch 0.2050 reclaim, then 0.2180",
        )

    high_failure = zones.get("post_squeeze_high_failure")
    reclaim_pressure = zones.get("reclaim_pressure")
    first_retest = zones.get("first_retest_pressure")
    major_retest = zones.get("major_retest_pressure")
    deleveraging = zones.get("deleveraging_pressure")
    tagged_high_failure = high_1h_20 is not None and high_failure and high_1h_20 >= min(high_failure)

    if (
        tagged_high_failure
        and zone_contains(price, deleveraging)
        and (oi1h or 0) <= thresholds["oi_stable_min"]
    ):
        return notify(
            d,
            "deleveraging_tail_watch",
            "Failed high squeeze has already unwound into the deleveraging pressure zone with OI contracting; this is a profit-management or retest-watch state, not a fresh chase signal.",
            f"deleveraging tail: {zone_text(deleveraging)}; wait for retest failure",
        )

    if (
        tagged_high_failure
        and zone_contains(price, major_retest)
        and taker is not None
        and taker <= thresholds["taker_sell_ratio"]
    ):
        return notify(
            d,
            "major_retest_failure_watch",
            "Price is back in the major retest-pressure band after a failed high squeeze and taker flow is sell-effective.",
            f"short observation: {zone_text(major_retest)}",
        )

    if (
        tagged_high_failure
        and zone_contains(price, first_retest)
        and (oi1h or 0) <= thresholds["oi_stable_min"]
    ):
        return notify(
            d,
            "first_retest_failure_watch",
            "After the failed high squeeze, price is retesting the first pressure band with OI not expanding; this is the cleaner short-observation area than chasing the low.",
            f"short observation: {zone_text(first_retest)}",
        )

    if (
        tagged_high_failure
        and price is not None
        and reclaim_pressure
        and price < min(reclaim_pressure)
        and (oi1h or 0) <= thresholds["oi_stable_min"]
    ):
        return notify(
            d,
            "post_squeeze_high_failure",
            "Later crowded-short squeeze tagged the high-failure zone but fell back below reclaim pressure while OI contracted; the squeeze failed instead of becoming a stable trend.",
            f"failed high retest: {zone_text(high_failure)}; reclaim pressure: {zone_text(reclaim_pressure)}",
        )

    return d


def classify_lab(symbol: str, item: dict[str, Any], cfg: dict[str, Any], thresholds: dict[str, float]) -> dict[str, Any]:
    d = base_decision(symbol, item, cfg)
    m = metric(item)
    zones = cfg.get("zones") or {}
    price = m["price"]
    oi1h = m["oi_change_1h"]
    taker = m["taker_buy_sell_ratio"]
    high_1h_20 = m["high_1h_20"]

    if price is not None and price < 13.8 and (oi1h or 0) >= thresholds["oi_rising_min"] and (taker or 1) <= thresholds["taker_sell_ratio"]:
        return notify(
            d,
            "whale_long_invalidation",
            "Price lost the deeper breakdown band with rising/stable OI and sell-effective taker flow, which looks more like real weakness than controlled squeeze setup.",
            f"invalidation retest: {zone_text(zones.get('deep_breakdown'))}",
        )

    if price is not None and price < 14.8 and (taker or 1) <= thresholds["taker_sell_ratio"]:
        return notify(
            d,
            "support_loss_invalidation",
            "Price lost 14.8 short-term support with sell-effective flow; the whale-long thesis needs a reclaim before it is usable again.",
            "reclaim watch: 14.8-15.1",
        )

    if price is not None and price >= 16.4 and (oi1h or 0) >= thresholds["oi_stable_min"] and (taker or 0) >= thresholds["taker_buy_ratio"]:
        return notify(
            d,
            "squeeze_validation",
            "Price broke above 16.4 with buy-effective taker flow and OI not contracting, matching the squeeze-validation path.",
            "validation follow-through: 16.4 hold, then 17.05+",
        )

    if (
        price is not None
        and high_1h_20 is not None
        and high_1h_20 >= 18.0
        and price < 17.05
        and is_short_crowded(m, thresholds)
        and (taker or 1) <= thresholds["taker_sell_ratio"]
    ):
        return notify(
            d,
            "learning_event_failed_squeeze",
            "Recent squeeze attempt reached the upper pressure area but failed back below 17.05 while shorts remain crowded; negative funding alone did not sustain follow-through.",
            "lesson zone: 16.2-16.4 reclaim or 14.8-15.1 defense",
        )

    return d


def classify_opn(symbol: str, item: dict[str, Any], cfg: dict[str, Any], thresholds: dict[str, float]) -> dict[str, Any]:
    d = base_decision(symbol, item, cfg)
    m = metric(item)
    zones = cfg.get("zones") or {}
    price = m["price"]
    oi1h = m["oi_change_1h"]
    taker = m["taker_buy_sell_ratio"]

    if zone_contains(price, zones.get("retest_pressure")) and (oi1h or 0) >= thresholds["oi_stable_min"] and (taker or 1) <= thresholds["taker_sell_ratio"]:
        return notify(
            d,
            "distribution_retest_failure",
            "Price is in retest pressure while taker flow is sell-effective and OI is not leaving, which fits distribution-watch conditions.",
            f"short observation: {zone_text(zones.get('retest_pressure'))}",
        )

    if price is not None and price < 0.188 and (oi1h or 0) >= thresholds["oi_rising_min"] and (taker or 1) <= thresholds["taker_sell_ratio"]:
        return notify(
            d,
            "support_loss_distribution",
            "Support absorption failed with sell-effective flow and OI stable/rising, favoring distribution over accumulation.",
            f"invalidation retest: {zone_text(zones.get('support_absorption'))}",
        )

    if price is not None and price >= 0.215 and (oi1h or 0) >= thresholds["oi_stable_min"] and (taker or 0) >= thresholds["taker_buy_ratio"]:
        return notify(
            d,
            "potential_reclaim_validation",
            "Price reclaimed the retest pressure band with buy-effective flow and OI support, shifting from distribution watch to potential validation.",
            "validation: 0.215 hold, then 0.227 breakout",
        )

    return d


CLASSIFIERS = {
    "ALLOUSDT": classify_allo,
    "LABUSDT": classify_lab,
    "OPNUSDT": classify_opn,
}


def evaluate(latest: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    candidates = {item.get("symbol"): item for item in latest.get("candidates", [])}
    decisions: list[dict[str, Any]] = []
    thresholds = config.get("thresholds") or {}

    for symbol, symbol_cfg in (config.get("symbols") or {}).items():
        item = candidates.get(symbol)
        if not item:
            decisions.append(
                {
                    "symbol": symbol,
                    "decision": "DONT_NOTIFY",
                    "event_type": "symbol_missing",
                    "reason": "Symbol was not present in the latest scan output.",
                    "risk_note": "Not financial advice; use as research workflow output only.",
                }
            )
            continue
        classifier = CLASSIFIERS.get(symbol)
        if classifier:
            decisions.append(classifier(symbol, item, symbol_cfg, thresholds))
        else:
            decisions.append(base_decision(symbol, item, symbol_cfg))

    notify_count = sum(1 for d in decisions if d.get("decision") == "NOTIFY")
    return {
        "updated_at": utc_now(),
        "harness": {
            "name": config.get("name"),
            "version": config.get("version"),
        },
        "source_snapshot": latest.get("updated_at"),
        "notify": notify_count > 0,
        "notify_count": notify_count,
        "decisions": decisions,
    }


def run_update(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    runtime = config.get("runtime") or {}
    focus = args.focus or ",".join(runtime.get("focus") or [])
    update_args = SimpleNamespace(
        limit=args.limit if args.limit is not None else runtime.get("limit", 24),
        focus=focus,
        min_pct=args.min_pct if args.min_pct is not None else runtime.get("min_pct", 8.0),
        min_quote_volume=args.min_quote_volume
        if args.min_quote_volume is not None
        else runtime.get("min_quote_volume", 5000000.0),
        sleep=args.sleep if args.sleep is not None else runtime.get("sleep", 0.06),
        raw=args.raw,
    )
    return updater.run(update_args)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the small-cap futures agent harness.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--no-update", action="store_true", help="Evaluate the existing latest.json without calling Binance.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write harness_state.json or harness_decisions.jsonl.")
    parser.add_argument("--show", action="store_true", help="Show the last harness state.")
    parser.add_argument("--raw", action="store_true", help="Pass through raw snapshot writing to the scanner.")
    parser.add_argument("--focus", help="Comma-separated symbols overriding config runtime.focus.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--min-pct", type=float)
    parser.add_argument("--min-quote-volume", type=float)
    parser.add_argument("--sleep", type=float)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.show:
        if not STATE_PATH.exists():
            print("No harness state found yet.")
            return 1
        print(json.dumps(load_json(STATE_PATH), ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    config = load_json(args.config)
    if args.no_update:
        if not LATEST_PATH.exists():
            print(f"Missing latest scan: {LATEST_PATH}", file=sys.stderr)
            return 1
        latest = load_json(LATEST_PATH)
    else:
        latest = run_update(config, args)

    state = evaluate(latest, config)
    if not args.dry_run:
        write_json(STATE_PATH, state)
        append_jsonl(DECISIONS_PATH, state)

    print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
