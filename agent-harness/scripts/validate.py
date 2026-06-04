#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


REQUIRED_PUBLIC_ROUTES = {
    "index.html": "BTC 策略工作台",
    "macro-report.html": "BTC",
    "market-temperature.html": "资本周期温度计",
    "investment-thesis-rerun.html": "Investment Thesis Monitor",
    "investment-research.html": "Investment Thesis",
    "mstr-mnav/index.html": "MSTR",
    "dao-system/index.html": "Dao",
}


REQUIRED_HOME_LINKS = [
    "dao-system/",
    "mstr-mnav/",
    "macro-report.html",
    "market-temperature.html",
    "investment-research.html",
    "investment-thesis-rerun.html",
    "saas-signals/",
    "market-top-triggers/",
]


SCENARIO_REQUIRED_KEYS = [
    "id",
    "title",
    "task_type",
    "risk",
    "prompt",
    "target_files",
    "required_commands",
    "deterministic_checks",
    "done_criteria",
    "judge_questions",
]


def read_text(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{path.relative_to(ROOT)}: cannot read: {exc}")
        return ""


def load_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
    except OSError as exc:
        errors.append(f"{path.relative_to(ROOT)}: cannot read: {exc}")
    return None


def require_file(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing required file: {path.relative_to(ROOT)}")


def require_contains(path: Path, needles: list[str], errors: list[str]) -> None:
    text = read_text(path, errors)
    if not text:
        return
    for needle in needles:
        if needle not in text:
            errors.append(f"{path.relative_to(ROOT)}: missing required text `{needle}`")


def require_dict_keys(label: str, payload: dict[str, Any], keys: list[str], errors: list[str]) -> None:
    for key in keys:
        if key not in payload:
            errors.append(f"{label}: missing required key `{key}`")


def validate_agent_map(errors: list[str]) -> None:
    agents = ROOT / "AGENTS.md"
    require_file(agents, errors)
    require_contains(
        agents,
        [
            "agent-harness/",
            "bash agent-harness/scripts/run_harness.sh",
            "tools/build_pages_site.sh",
            "tools/check_site_links.py",
        ],
        errors,
    )


def validate_scenarios(errors: list[str]) -> None:
    scenario_dir = ROOT / "agent-harness" / "scenarios"
    scenarios = sorted(scenario_dir.glob("*.json"))
    if len(scenarios) < 3:
        errors.append("agent-harness/scenarios: expected at least 3 scenario fixtures")
    for path in scenarios:
        payload = load_json(path, errors)
        if not isinstance(payload, dict):
            continue
        label = str(path.relative_to(ROOT))
        require_dict_keys(label, payload, SCENARIO_REQUIRED_KEYS, errors)
        for list_key in ["target_files", "required_commands", "deterministic_checks", "done_criteria", "judge_questions"]:
            value = payload.get(list_key)
            if not isinstance(value, list) or not value:
                errors.append(f"{label}: `{list_key}` must be a non-empty list")
        for target in payload.get("target_files", []):
            if not isinstance(target, str) or not target:
                errors.append(f"{label}: target_files entries must be strings")
                continue
            if target.endswith("/"):
                if not (ROOT / target).exists():
                    errors.append(f"{label}: target directory does not exist: {target}")
            elif not any(char in target for char in "*?[") and not (ROOT / target).exists():
                errors.append(f"{label}: target file does not exist: {target}")


def validate_source_contract(errors: list[str]) -> None:
    require_file(ROOT / "agent-harness" / "contracts" / "system-iteration-contract.md", errors)
    require_contains(
        ROOT / "agent-harness" / "contracts" / "system-iteration-contract.md",
        ["Map updated", "Data contract preserved", "Research contract preserved", "Judge run"],
        errors,
    )
    require_contains(
        ROOT / "tools" / "build_pages_site.sh",
        [
            'copy_file market-temperature.html "$out_dir/market-temperature.html"',
            'copy_file investment-thesis-rerun.html "$out_dir/investment-thesis-rerun.html"',
            'copy_file investment-thesis-harness/outputs/report.html "$out_dir/investment-research.html"',
        ],
        errors,
    )
    require_contains(ROOT / "home.html", REQUIRED_HOME_LINKS, errors)
    require_contains(
        ROOT / "market-temperature.html",
        [
            'fetch("latest.json"',
            "清算期",
            "实现危机",
            "再集中/早周期",
            "扩张期",
            "过热期",
            "市场温度",
        ],
        errors,
    )


def validate_site_artifact(site_root: Path, errors: list[str]) -> None:
    if not site_root.exists():
        errors.append(f"site root does not exist: {site_root}")
        return
    for route, marker in REQUIRED_PUBLIC_ROUTES.items():
        path = site_root / route
        if not path.exists():
            errors.append(f"generated site missing route: {route}")
            continue
        text = read_text(path, errors)
        if marker not in text:
            errors.append(f"{path.relative_to(ROOT)}: missing marker `{marker}`")

    latest = load_json(site_root / "latest.json", errors)
    if isinstance(latest, dict):
        require_dict_keys("_site/latest.json", latest, ["generated_at", "indicators", "signals", "regime"], errors)
        indicators = latest.get("indicators", {})
        if isinstance(indicators, dict):
            for key in ["btc", "policy_rates", "liquidity", "dollar_risk", "debt"]:
                if key not in indicators:
                    errors.append(f"_site/latest.json indicators: missing `{key}`")
        else:
            errors.append("_site/latest.json: indicators must be an object")

    investment = load_json(site_root / "investment-latest.json", errors)
    if isinstance(investment, dict):
        require_dict_keys("_site/investment-latest.json", investment, ["topic", "snapshot"], errors)
        snapshot = investment.get("snapshot", {})
        if isinstance(snapshot, dict):
            if not snapshot:
                errors.append("_site/investment-latest.json: snapshot must not be empty")
        else:
            errors.append("_site/investment-latest.json: snapshot must be an object")

    dao = load_json(site_root / "dao-system" / "data" / "dao-latest.json", errors)
    if isinstance(dao, dict):
        require_dict_keys("_site/dao-system/data/dao-latest.json", dao, ["schema_version", "generated_at", "state", "axes"], errors)


def validate_workflow(errors: list[str]) -> None:
    require_contains(
        ROOT / ".github" / "workflows" / "update-and-pages.yml",
        [
            "Validate agent harness",
            "python3 agent-harness/scripts/validate.py --site-root _site",
        ],
        errors,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the repo-level agent harness.")
    parser.add_argument("--site-root", default="_site", help="Generated Pages site root.")
    args = parser.parse_args()

    errors: list[str] = []
    site_root = (ROOT / args.site_root).resolve()

    validate_agent_map(errors)
    validate_scenarios(errors)
    validate_source_contract(errors)
    validate_site_artifact(site_root, errors)
    validate_workflow(errors)

    if errors:
        print("agent harness validation failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("agent harness validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
