#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
    except OSError as exc:
        errors.append(f"{path.relative_to(ROOT)}: cannot read: {exc}")
    return None


def require_keys(label: str, payload: dict[str, Any], keys: list[str], errors: list[str]) -> None:
    for key in keys:
        if key not in payload:
            errors.append(f"{label}: missing required key `{key}`")


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def close_enough(actual: Any, expected: float, tolerance: float = 0.01) -> bool:
    return is_number(actual) and abs(float(actual) - expected) <= max(1.0, abs(expected)) * tolerance


def validate_all_json(errors: list[str]) -> None:
    for path in sorted(ROOT.rglob("*.json")):
        load_json(path, errors)


def validate_topic(config: dict[str, Any], errors: list[str]) -> set[str]:
    topic_ids: set[str] = set()
    score_keys = set(config.get("weights", {}))
    topic_dir = ROOT / "data" / "topics"
    for path in sorted(topic_dir.glob("*.json")):
        topic = load_json(path, errors)
        if not isinstance(topic, dict):
            continue
        require_keys(str(path.relative_to(ROOT)), topic, ["id", "title", "as_of", "theses"], errors)
        topic_id = str(topic.get("id", path.stem))
        topic_ids.add(topic_id)
        for thesis in topic.get("theses", []):
            if not isinstance(thesis, dict):
                errors.append(f"{path.relative_to(ROOT)}: thesis must be an object")
                continue
            label = f"{path.relative_to(ROOT)} thesis `{thesis.get('id', '<missing>')}`"
            require_keys(
                label,
                thesis,
                ["id", "title", "investment_question", "market_mispricing", "claims", "evidence", "counter_evidence", "scores"],
                errors,
            )
            scores = thesis.get("scores", {})
            if isinstance(scores, dict):
                missing_scores = sorted(score_keys - set(scores))
                if missing_scores:
                    errors.append(f"{label}: missing score keys {', '.join(missing_scores)}")
                for key, value in scores.items():
                    if not is_number(value) or not 0 <= float(value) <= 5:
                        errors.append(f"{label}: score `{key}` must be a number from 0 to 5")
            for item in thesis.get("evidence", []):
                if isinstance(item, dict) and item.get("type") in {"primary", "filing"} and not item.get("url"):
                    errors.append(f"{label}: primary evidence `{item.get('title', '')}` needs a URL")
    return topic_ids


def validate_cases(topic_ids: set[str], errors: list[str]) -> None:
    for path in sorted((ROOT / "data" / "cases").glob("*.json")):
        case = load_json(path, errors)
        if not isinstance(case, dict):
            continue
        label = str(path.relative_to(ROOT))
        require_keys(label, case, ["id", "topic_id", "title", "url", "input_summary", "case_decision"], errors)
        if case.get("topic_id") not in topic_ids:
            errors.append(f"{label}: unknown topic_id `{case.get('topic_id')}`")


def validate_assets(topic_ids: set[str], errors: list[str]) -> None:
    for path in sorted((ROOT / "data" / "assets").glob("*.json")):
        payload = load_json(path, errors)
        if not isinstance(payload, dict):
            continue
        label = str(path.relative_to(ROOT))
        require_keys(label, payload, ["topic_id", "thesis_id", "assets"], errors)
        if payload.get("topic_id") not in topic_ids:
            errors.append(f"{label}: unknown topic_id `{payload.get('topic_id')}`")
        for asset in payload.get("assets", []):
            if not isinstance(asset, dict):
                errors.append(f"{label}: asset must be an object")
                continue
            asset_label = f"{label} asset `{asset.get('ticker', '<missing>')}`"
            require_keys(asset_label, asset, ["ticker", "name", "decision", "priority_score", "scores"], errors)
            if not is_number(asset.get("priority_score")) or not 0 <= float(asset.get("priority_score", 0)) <= 100:
                errors.append(f"{asset_label}: priority_score must be 0 to 100")


def validate_models(topic_ids: set[str], errors: list[str]) -> None:
    for path in sorted((ROOT / "data" / "models").glob("*.json")):
        model = load_json(path, errors)
        if not isinstance(model, dict):
            continue
        label = str(path.relative_to(ROOT))
        require_keys(label, model, ["topic_id", "title", "as_of", "model_type", "contracts", "decision"], errors)
        if model.get("topic_id") not in topic_ids:
            errors.append(f"{label}: unknown topic_id `{model.get('topic_id')}`")
        for contract in model.get("contracts", []):
            if not isinstance(contract, dict):
                errors.append(f"{label}: contract must be an object")
                continue
            contract_label = f"{label} contract `{contract.get('ticker', '<missing>')}`"
            require_keys(contract_label, contract, ["ticker", "contract", "status", "derived", "interpretation"], errors)
            value = contract.get("contract_value_usd")
            mw = contract.get("critical_it_load_mw")
            years = contract.get("term_years")
            derived = contract.get("derived", {})
            if is_number(value) and is_number(mw) and float(mw) > 0:
                expected_per_mw = float(value) / float(mw)
                if not close_enough(derived.get("headline_value_per_mw_usd"), expected_per_mw):
                    errors.append(f"{contract_label}: headline_value_per_mw_usd does not match value / MW")
                if is_number(years) and float(years) > 0:
                    expected_annual = expected_per_mw / float(years)
                    if not close_enough(derived.get("annual_value_per_mw_usd"), expected_annual):
                        errors.append(f"{contract_label}: annual_value_per_mw_usd does not match value / MW / years")
        bridge = model.get("valuation_bridge", {})
        if bridge:
            require_keys(f"{label} valuation_bridge", bridge, ["title", "method", "screening_cases", "current_conclusion"], errors)
            for case in bridge.get("screening_cases", []):
                if not isinstance(case, dict):
                    errors.append(f"{label}: valuation bridge case must be an object")
                    continue
                case_label = f"{label} valuation `{case.get('ticker', '<missing>')}`"
                require_keys(
                    case_label,
                    case,
                    ["ticker", "contract_ref", "business_model", "headline_annual_revenue_usd", "headline_annual_revenue_per_mw_usd", "read", "position_gate"],
                    errors,
                )
        company_bridge = model.get("company_valuation_bridge", {})
        if company_bridge:
            require_keys(
                f"{label} company_valuation_bridge",
                company_bridge,
                ["title", "as_of", "model_type", "companies", "ranking", "decision"],
                errors,
            )
            for company in company_bridge.get("companies", []):
                if not isinstance(company, dict):
                    errors.append(f"{label}: company valuation entry must be an object")
                    continue
                company_label = f"{label} company valuation `{company.get('ticker', '<missing>')}`"
                require_keys(company_label, company, ["ticker", "name", "market_cap_usd", "model_bucket", "read", "decision"], errors)
                if not is_number(company.get("market_cap_usd")) or float(company.get("market_cap_usd", 0)) <= 0:
                    errors.append(f"{company_label}: market_cap_usd must be a positive number")
                for scenario in company.get("cash_margin_scenarios", []):
                    if not isinstance(scenario, dict):
                        errors.append(f"{company_label}: cash margin scenario must be an object")
                        continue
                    if not scenario.get("case"):
                        errors.append(f"{company_label}: cash margin scenario missing case")
                for scenario in company.get("option_scenarios", []):
                    if not isinstance(scenario, dict):
                        errors.append(f"{company_label}: option scenario must be an object")
                        continue
                    require_keys(
                        f"{company_label} option scenario `{scenario.get('case', '<missing>')}`",
                        scenario,
                        ["case", "screened_mw", "potential_annual_revenue_base_usd", "market_cap_to_base_revenue"],
                        errors,
                    )


def main() -> int:
    errors: list[str] = []
    config = load_json(ROOT / "config.json", errors)
    if not isinstance(config, dict):
        print("validation failed: config.json is missing or invalid")
        return 1

    validate_all_json(errors)
    topic_ids = validate_topic(config, errors)
    validate_cases(topic_ids, errors)
    validate_assets(topic_ids, errors)
    validate_models(topic_ids, errors)

    if errors:
        print("validation failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
