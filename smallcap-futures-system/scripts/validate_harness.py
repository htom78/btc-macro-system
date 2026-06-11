#!/usr/bin/env python3
"""Structural validation for the small-cap futures agent harness."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


SYSTEM_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = SYSTEM_ROOT / "harness" / "config.json"
STATE_PATH = SYSTEM_ROOT / "data" / "harness_state.json"
LATEST_PATH = SYSTEM_ROOT / "data" / "latest.json"
RUNNER_PATH = SYSTEM_ROOT / "scripts" / "run_agent_harness.py"

sys.path.insert(0, str(RUNNER_PATH.parent))
import run_agent_harness as harness  # noqa: E402


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_config(errors: list[str]) -> None:
    require(CONFIG_PATH.exists(), f"missing config: {CONFIG_PATH}", errors)
    if not CONFIG_PATH.exists():
        return

    config = load_json(CONFIG_PATH)
    require(bool(config.get("name")), "config.name is required", errors)
    require(bool(config.get("version")), "config.version is required", errors)
    require(RUNNER_PATH.exists(), f"missing runner: {RUNNER_PATH}", errors)

    source_policy = config.get("source_policy") or {}
    require(source_policy.get("no_private_keys") is True, "source_policy.no_private_keys must be true", errors)
    require(source_policy.get("no_order_execution") is True, "source_policy.no_order_execution must be true", errors)
    require(source_policy.get("no_financial_advice") is True, "source_policy.no_financial_advice must be true", errors)

    runtime = config.get("runtime") or {}
    require(isinstance(runtime.get("focus"), list) and runtime["focus"], "runtime.focus must be a non-empty list", errors)

    thresholds = config.get("thresholds") or {}
    for key in [
        "short_crowded_account_ratio",
        "taker_buy_ratio",
        "taker_sell_ratio",
        "oi_stable_min",
        "negative_funding",
    ]:
        require(key in thresholds, f"thresholds.{key} is required", errors)

    symbols = config.get("symbols") or {}
    require(bool(symbols), "config.symbols must not be empty", errors)
    for symbol, symbol_cfg in symbols.items():
        require(bool(symbol_cfg.get("thesis")), f"{symbol}.thesis is required", errors)
        require(bool(symbol_cfg.get("zones")), f"{symbol}.zones is required", errors)
        require(bool(symbol_cfg.get("event_gates")), f"{symbol}.event_gates is required", errors)
        for zone_name, zone in (symbol_cfg.get("zones") or {}).items():
            require(
                isinstance(zone, list) and len(zone) == 2 and all(isinstance(v, (int, float)) for v in zone),
                f"{symbol}.zones.{zone_name} must be [low, high]",
                errors,
            )


def validate_latest(errors: list[str]) -> None:
    if not LATEST_PATH.exists():
        return
    latest = load_json(LATEST_PATH)
    require("updated_at" in latest, "latest.json.updated_at is required", errors)
    require(isinstance(latest.get("candidates"), list), "latest.json.candidates must be a list", errors)
    require(isinstance(latest.get("models", {}), dict), "latest.json.models must be an object when present", errors)
    require(isinstance(latest.get("maturity", {}), dict), "latest.json.maturity must be an object when present", errors)


def validate_state(errors: list[str]) -> None:
    if not STATE_PATH.exists():
        return
    state = load_json(STATE_PATH)
    require("updated_at" in state, "harness_state.updated_at is required", errors)
    require("notify" in state, "harness_state.notify is required", errors)
    require(isinstance(state.get("decisions"), list), "harness_state.decisions must be a list", errors)
    for index, decision in enumerate(state.get("decisions") or []):
        for key in ["symbol", "decision", "event_type", "reason", "risk_note"]:
            require(key in decision, f"harness_state.decisions[{index}].{key} is required", errors)


def candidate(
    symbol: str,
    price: float,
    *,
    high_1h_20: float,
    oi_change_1h: float,
    taker_buy_sell_ratio: float,
    funding_rate: float = -0.00005,
    global_short_account: float = 0.64,
    top_long_position: float = 0.55,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "last": price,
        "pct24": 0.0,
        "derivatives": {
            "funding_rate": funding_rate,
            "oi_change_1h": oi_change_1h,
            "oi_change_4h": oi_change_1h,
        },
        "ratios": {
            "global_short_account": global_short_account,
            "top_long_position": top_long_position,
            "taker_buy_sell_ratio": taker_buy_sell_ratio,
        },
        "klines": {
            "5m": {"close": price, "high_20": high_1h_20, "low_20": price},
            "15m": {"close": price, "change": -0.05, "high_20": high_1h_20, "low_20": price},
            "1h": {"high_20": high_1h_20, "low_20": price},
        },
    }


def validate_classifier_regressions(errors: list[str]) -> None:
    if not CONFIG_PATH.exists():
        return
    config = load_json(CONFIG_PATH)
    thresholds = config.get("thresholds") or {}
    allo_cfg = (config.get("symbols") or {}).get("ALLOUSDT") or {}
    if not thresholds or not allo_cfg:
        return

    deleveraging_decision = harness.classify_allo(
        "ALLOUSDT",
        candidate(
            "ALLOUSDT",
            0.356,
            high_1h_20=0.48577,
            oi_change_1h=-0.048,
            taker_buy_sell_ratio=0.93,
        ),
        allo_cfg,
        thresholds,
    )
    require(
        deleveraging_decision.get("event_type") == "deleveraging_tail_watch",
        "ALLO failed-squeeze deleveraging regression must classify as deleveraging_tail_watch",
        errors,
    )

    retest_decision = harness.classify_allo(
        "ALLOUSDT",
        candidate(
            "ALLOUSDT",
            0.432,
            high_1h_20=0.48577,
            oi_change_1h=-0.01,
            taker_buy_sell_ratio=0.95,
        ),
        allo_cfg,
        thresholds,
    )
    require(
        retest_decision.get("event_type") == "first_retest_failure_watch",
        "ALLO first retest regression must classify as first_retest_failure_watch",
        errors,
    )


def main() -> int:
    errors: list[str] = []
    validate_config(errors)
    validate_latest(errors)
    validate_state(errors)
    validate_classifier_regressions(errors)

    if errors:
        print("harness validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("harness validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
