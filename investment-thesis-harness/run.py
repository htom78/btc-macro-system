#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clamp_score(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(5.0, parsed))


def weighted_score(scores: dict[str, Any], weights: dict[str, float]) -> float:
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("score weights must sum to a positive number")
    raw = 0.0
    for key, weight in weights.items():
        raw += clamp_score(scores.get(key)) / 5.0 * weight
    return round(raw / total_weight * 100, 1)


def decision_for(score: float, bands: list[dict[str, Any]]) -> dict[str, str]:
    ordered = sorted(bands, key=lambda item: float(item["min_score"]), reverse=True)
    for band in ordered:
        if score >= float(band["min_score"]):
            return {
                "label": str(band["label"]),
                "description": str(band.get("description", "")),
            }
    return {"label": "unclassified", "description": "No matching decision band."}


def evidence_summary(thesis: dict[str, Any]) -> dict[str, Any]:
    evidence = thesis.get("evidence", [])
    counter = thesis.get("counter_evidence", [])
    strengths = [clamp_score(item.get("strength")) for item in evidence if isinstance(item, dict)]
    return {
        "evidence_count": len(evidence),
        "counter_evidence_count": len(counter),
        "avg_evidence_strength": round(sum(strengths) / len(strengths), 2) if strengths else 0.0,
        "has_primary_evidence": any(item.get("type") == "primary" for item in evidence if isinstance(item, dict)),
    }


def enrich_topic(topic: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    weights = {key: float(value) for key, value in config["weights"].items()}
    bands = list(config["decision_bands"])
    enriched_theses = []
    for thesis in topic.get("theses", []):
        score = weighted_score(thesis.get("scores", {}), weights)
        decision = decision_for(score, bands)
        enriched = dict(thesis)
        enriched["investability_score"] = score
        enriched["decision"] = decision
        enriched["evidence_summary"] = evidence_summary(thesis)
        enriched_theses.append(enriched)

    enriched_theses.sort(key=lambda item: item["investability_score"], reverse=True)
    result = dict(topic)
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    result["weights"] = weights
    result["theses"] = enriched_theses
    return result


def load_topic(topic_id: str) -> dict[str, Any]:
    return load_json(ROOT / "data" / "topics" / f"{topic_id}.json")


def load_cases(topic_id: str) -> list[dict[str, Any]]:
    case_dir = ROOT / "data" / "cases"
    if not case_dir.exists():
        return []

    cases: list[dict[str, Any]] = []
    for path in sorted(case_dir.glob("*.json")):
        case = load_json(path)
        if case.get("topic_id") == topic_id:
            cases.append(case)
    return cases


def load_asset_cards(topic_id: str) -> list[dict[str, Any]]:
    asset_dir = ROOT / "data" / "assets"
    if not asset_dir.exists():
        return []

    assets: list[dict[str, Any]] = []
    for path in sorted(asset_dir.glob("*.json")):
        payload = load_json(path)
        if payload.get("topic_id") != topic_id:
            continue
        group_title = payload.get("title", "")
        thesis_id = payload.get("thesis_id", "")
        as_of = payload.get("as_of", "")
        for asset in payload.get("assets", []):
            enriched = dict(asset)
            enriched["group_title"] = group_title
            enriched["thesis_id"] = thesis_id
            enriched["as_of"] = as_of
            assets.append(enriched)
    assets.sort(key=lambda item: float(item.get("priority_score", 0)), reverse=True)
    return assets


def load_portfolio_rules(topic_id: str) -> list[dict[str, Any]]:
    rules_dir = ROOT / "data" / "portfolio"
    if not rules_dir.exists():
        return []

    rules: list[dict[str, Any]] = []
    for path in sorted(rules_dir.glob("*.json")):
        payload = load_json(path)
        if payload.get("topic_id") == topic_id:
            rules.append(payload)
    return rules


def load_contract_models(topic_id: str) -> list[dict[str, Any]]:
    model_dir = ROOT / "data" / "models"
    if not model_dir.exists():
        return []

    models: list[dict[str, Any]] = []
    for path in sorted(model_dir.glob("*.json")):
        payload = load_json(path)
        if payload.get("topic_id") == topic_id:
            models.append(payload)
    return models


def upsert_history(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    key = (snapshot["as_of"], snapshot["topic_id"])
    rows: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            row_key = (row.get("as_of"), row.get("topic_id"))
            if row_key != key:
                rows.append(row)
    rows.append(snapshot)
    rows.sort(key=lambda item: (str(item.get("as_of", "")), str(item.get("topic_id", ""))))
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def build_snapshot(topic: dict[str, Any]) -> dict[str, Any]:
    return {
        "as_of": topic.get("as_of") or date.today().isoformat(),
        "generated_at": topic["generated_at"],
        "topic_id": topic["id"],
        "topic_title": topic["title"],
        "thesis_count": len(topic["theses"]),
        "theses": [
            {
                "id": thesis["id"],
                "title": thesis["title"],
                "score": thesis["investability_score"],
                "decision": thesis["decision"]["label"],
                "status": thesis.get("status", ""),
                "candidate_assets": [asset["ticker"] for asset in thesis.get("candidate_assets", [])],
                "evidence_summary": thesis["evidence_summary"],
            }
            for thesis in topic["theses"]
        ],
        "cases": [
            {
                "id": case["id"],
                "title": case["title"],
                "source_type": case.get("source_type", ""),
                "case_decision": case.get("case_decision", {}).get("label", ""),
            }
            for case in topic.get("cases", [])
        ],
        "asset_cards": [
            {
                "ticker": asset["ticker"],
                "name": asset["name"],
                "decision": asset.get("decision", ""),
                "priority_score": asset.get("priority_score", 0),
                "thesis_id": asset.get("thesis_id", ""),
            }
            for asset in topic.get("asset_cards", [])
        ],
        "portfolio_rules": [
            {
                "title": rules.get("title", ""),
                "principle": rules.get("principle", ""),
                "next_decision_required": rules.get("next_decision_required", ""),
            }
            for rules in topic.get("portfolio_rules", [])
        ],
        "contract_models": [
            {
                "title": model.get("title", ""),
                "model_type": model.get("model_type", ""),
                "decision": model.get("decision", {}).get("label", ""),
                "company_valuation_decision": model.get("company_valuation_bridge", {})
                .get("decision", {})
                .get("label", ""),
            }
            for model in topic.get("contract_models", [])
        ],
    }


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def score_class(score: float) -> str:
    if score >= 75:
        return "score-strong"
    if score >= 60:
        return "score-watch"
    if score >= 45:
        return "score-backlog"
    return "score-avoid"


def render_list(items: list[Any]) -> str:
    if not items:
        return "<p class=\"muted\">No entries yet.</p>"
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def render_evidence(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p class=\"muted\">No evidence recorded yet.</p>"
    rows = []
    for item in items:
        title = esc(item.get("title", "Untitled evidence"))
        url = item.get("url")
        link = f"<a href=\"{esc(url)}\">source</a>" if url else ""
        rows.append(
            "<tr>"
            f"<td>{esc(item.get('type', 'source'))}</td>"
            f"<td>{esc(item.get('strength', ''))}</td>"
            f"<td>{title} {link}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Type</th><th>Strength</th><th>Evidence</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_assets(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p class=\"muted\">No assets recorded yet.</p>"
    cards = []
    for asset in items:
        cards.append(
            "<div class=\"asset\">"
            f"<strong>{esc(asset.get('ticker', ''))}</strong>"
            f"<span>{esc(asset.get('name', ''))}</span>"
            f"<p>{esc(asset.get('role', ''))}</p>"
            f"<em>{esc(asset.get('tradability_note', ''))}</em>"
            "</div>"
        )
    return f"<div class=\"assets\">{''.join(cards)}</div>"


def render_cases(cases: list[dict[str, Any]]) -> str:
    if not cases:
        return ""

    rendered = []
    for case in cases:
        translations = "".join(
            "<tr>"
            f"<td>{esc(item.get('thesis_id', ''))}</td>"
            f"<td>{esc(item.get('impact', ''))}</td>"
            f"<td>{esc(item.get('rationale', ''))}</td>"
            "</tr>"
            for item in case.get("investment_translation", [])
        )
        rendered.append(
            "<section class=\"case-memo\">"
            f"<div class=\"section-head\"><h2>{esc(case.get('title', 'Case Memo'))}</h2>"
            f"<a href=\"{esc(case.get('url', '#'))}\">source</a></div>"
            f"<p class=\"muted\">{esc(case.get('source_type', ''))} · {esc(case.get('author', ''))} · {esc(case.get('published_at', ''))}</p>"
            f"<h3>Input Summary</h3><p>{esc(case.get('input_summary', ''))}</p>"
            f"<h3>Market Signal</h3><p>{esc(case.get('market_signal', ''))}</p>"
            f"<h3>Extracted Claims</h3>{render_list(case.get('extracted_claims', []))}"
            "<h3>Investment Translation</h3>"
            "<table><thead><tr><th>Thesis</th><th>Impact</th><th>Rationale</th></tr></thead>"
            f"<tbody>{translations}</tbody></table>"
            f"<h3>Red Flags</h3>{render_list(case.get('red_flags', []))}"
            f"<h3>Case Decision</h3><p><strong>{esc(case.get('case_decision', {}).get('label', ''))}</strong> · {esc(case.get('case_decision', {}).get('action', ''))}</p>"
            f"<h3>Next Actions</h3>{render_list(case.get('next_actions', []))}"
            "</section>"
        )
    return "".join(rendered)


def render_asset_cards(asset_cards: list[dict[str, Any]]) -> str:
    if not asset_cards:
        return ""

    rows = []
    sections = []
    for asset in asset_cards:
        score = float(asset.get("priority_score", 0))
        market = asset.get("market_snapshot", {})
        market_cap = market.get("market_cap_usd")
        market_cap_text = f"${market_cap / 1_000_000_000:.1f}B" if isinstance(market_cap, (int, float)) else "--"
        price = market.get("price_usd")
        price_text = f"${price:.2f}" if isinstance(price, (int, float)) else "--"
        rows.append(
            "<tr>"
            f"<td><a href=\"#asset-{esc(asset.get('ticker', '').lower())}\">{esc(asset.get('ticker', ''))}</a></td>"
            f"<td>{esc(asset.get('decision', ''))}</td>"
            f"<td><span class=\"mini-score\">{score:.0f}</span></td>"
            f"<td>{price_text}</td>"
            f"<td>{market_cap_text}</td>"
            f"<td>{esc(asset.get('contract_status', ''))}</td>"
            "</tr>"
        )
        score_items = "".join(
            f"<div><span>{esc(key.replace('_', ' '))}</span><strong>{clamp_score(value):.1f}</strong></div>"
            for key, value in asset.get("scores", {}).items()
        )
        sections.append(
            "<section class=\"asset-card\" "
            f"id=\"asset-{esc(asset.get('ticker', '').lower())}\">"
            f"<div class=\"section-head\"><h2>{esc(asset.get('ticker', ''))} · {esc(asset.get('name', ''))}</h2>"
            f"<span class=\"mini-score\">{score:.0f}</span></div>"
            f"<p class=\"decision\"><strong>{esc(asset.get('decision', ''))}</strong> · {esc(asset.get('thesis_read', ''))}</p>"
            "<div class=\"grid two\">"
            f"<div><h3>Contract Status</h3><p>{esc(asset.get('contract_status', ''))}</p></div>"
            f"<div><h3>Power / Capacity</h3><p>{esc(asset.get('power_and_capacity', ''))}</p></div>"
            "</div>"
            "<div class=\"grid two\">"
            f"<div><h3>Key Facts</h3>{render_list(asset.get('key_facts', []))}</div>"
            f"<div><h3>Red Flags</h3>{render_list(asset.get('red_flags', []))}</div>"
            "</div>"
            "<h3>Evidence</h3>"
            f"{render_evidence(asset.get('evidence', []))}"
            "<div class=\"grid two\">"
            f"<div><h3>Next Checks</h3>{render_list(asset.get('next_checks', []))}</div>"
            f"<div><h3>Asset Scores</h3><div class=\"score-grid\">{score_items}</div></div>"
            "</div>"
            "</section>"
        )

    return (
        "<section class=\"summary asset-summary\">"
        "<h2>Asset Cards · AI Power / Miner Hosting</h2>"
        "<table><thead><tr><th>Ticker</th><th>Decision</th><th>Priority</th><th>Price</th><th>Market Cap</th><th>Contract Status</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        "</section>"
        f"{''.join(sections)}"
    )


def render_portfolio_rules(rule_sets: list[dict[str, Any]]) -> str:
    if not rule_sets:
        return ""

    rendered = []
    for rules in rule_sets:
        core_rows = []
        for item in rules.get("core_holdings", []):
            snap = item.get("current_snapshot", {})
            price = snap.get("price_usd")
            price_text = f"${price:,.2f}" if isinstance(price, (int, float)) else "--"
            core_rows.append(
                "<tr>"
                f"<td>{esc(item.get('ticker', ''))}</td>"
                f"<td>{esc(item.get('role', ''))}</td>"
                f"<td>{price_text}</td>"
                f"<td>{esc(item.get('rule', ''))}</td>"
                "</tr>"
            )

        bucket_rows = []
        for bucket in rules.get("tactical_buckets", []):
            weight = bucket.get("max_portfolio_weight")
            weight_text = f"{float(weight) * 100:.1f}%" if isinstance(weight, (int, float)) else "--"
            bucket_rows.append(
                "<tr>"
                f"<td>{esc(bucket.get('name', ''))}</td>"
                f"<td>{weight_text}</td>"
                f"<td>{esc(bucket.get('use_for', ''))}</td>"
                f"<td>{esc(bucket.get('entry_gate', ''))}</td>"
                "</tr>"
            )

        action_rows = "".join(
            "<tr>"
            f"<td>{esc(item.get('ticker', ''))}</td>"
            f"<td>{esc(item.get('action', ''))}</td>"
            f"<td>{esc(item.get('position_rule', ''))}</td>"
            "</tr>"
            for item in rules.get("asset_actions", [])
        )

        rendered.append(
            "<section class=\"portfolio-rules\">"
            f"<div class=\"section-head\"><h2>{esc(rules.get('title', 'Portfolio Rules'))}</h2>"
            f"<span class=\"muted\">{esc(rules.get('as_of', ''))}</span></div>"
            f"<p class=\"decision\"><strong>Principle</strong> · {esc(rules.get('principle', ''))}</p>"
            "<h3>Core Holdings</h3>"
            "<table><thead><tr><th>Ticker</th><th>Role</th><th>Snapshot</th><th>Rule</th></tr></thead>"
            f"<tbody>{''.join(core_rows)}</tbody></table>"
            "<h3>Tactical Buckets</h3>"
            "<table><thead><tr><th>Bucket</th><th>Max Weight</th><th>Use For</th><th>Entry Gate</th></tr></thead>"
            f"<tbody>{''.join(bucket_rows)}</tbody></table>"
            "<h3>Asset Actions</h3>"
            "<table><thead><tr><th>Ticker</th><th>Action</th><th>Position Rule</th></tr></thead>"
            f"<tbody>{action_rows}</tbody></table>"
            f"<h3>Kill Switches</h3>{render_list(rules.get('kill_switches', []))}"
            f"<h3>Next Decision</h3><p>{esc(rules.get('next_decision_required', ''))}</p>"
            "</section>"
        )
    return "".join(rendered)


def fmt_money(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "--"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:,.0f}"


def fmt_value(value: Any) -> str:
    return "--" if value is None else esc(value)


def fmt_percent(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "--"
    return f"{value * 100:.1f}%"


def fmt_multiple(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "--"
    return f"{value:.1f}x"


def render_key_values(payload: dict[str, Any]) -> str:
    if not payload:
        return "<p class=\"muted\">No assumptions recorded yet.</p>"
    rows = []
    for key, value in payload.items():
        if isinstance(value, list):
            if "margin" in key or "ratio" in key:
                formatted = ", ".join(fmt_percent(item) if isinstance(item, (int, float)) else esc(item) for item in value)
            else:
                formatted = ", ".join(fmt_money(item) if isinstance(item, (int, float)) else esc(item) for item in value)
        elif isinstance(value, (int, float)) and ("margin" in key or "cap" in key and value <= 1):
            formatted = fmt_percent(value)
        elif isinstance(value, (int, float)) and ("usd" in key or "cost" in key or "revenue" in key):
            formatted = fmt_money(value)
        else:
            formatted = esc(value)
        rows.append(
            "<tr>"
            f"<td>{esc(key.replace('_', ' '))}</td>"
            f"<td>{formatted}</td>"
            "</tr>"
        )
    return f"<table><tbody>{''.join(rows)}</tbody></table>"


def render_company_scenarios(company: dict[str, Any]) -> str:
    cash_scenarios = company.get("cash_margin_scenarios", [])
    option_scenarios = company.get("option_scenarios", [])
    if cash_scenarios:
        rows = []
        for scenario in cash_scenarios:
            margin = (
                scenario.get("margin_after_power_opex_financing")
                or scenario.get("gross_cash_margin_before_gpu_recovery")
                or scenario.get("margin_after_power_opex_credit_drag")
            )
            screened_cash = (
                scenario.get("screened_cash_usd")
                or scenario.get("five_year_gross_cash_usd")
                or scenario.get("gross_cash_after_equipment_purchase_usd")
            )
            yield_value = scenario.get("screened_cash_yield_on_market_cap")
            after_equipment = scenario.get("gross_cash_after_equipment_purchase_usd")
            rows.append(
                "<tr>"
                f"<td>{esc(scenario.get('case', ''))}</td>"
                f"<td>{fmt_percent(margin)}</td>"
                f"<td>{fmt_money(screened_cash)}</td>"
                f"<td>{fmt_percent(yield_value)}</td>"
                f"<td>{fmt_money(after_equipment)}</td>"
                "</tr>"
            )
        return (
            "<table><thead><tr><th>Case</th><th>Margin</th><th>Screened Cash</th><th>Cash Yield</th><th>After Equipment</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    if option_scenarios:
        rows = []
        for scenario in option_scenarios:
            rows.append(
                "<tr>"
                f"<td>{esc(scenario.get('case', ''))}</td>"
                f"<td>{fmt_value(scenario.get('screened_mw'))}</td>"
                f"<td>{fmt_money(scenario.get('potential_annual_revenue_low_usd'))}</td>"
                f"<td>{fmt_money(scenario.get('potential_annual_revenue_base_usd'))}</td>"
                f"<td>{fmt_money(scenario.get('potential_annual_revenue_high_usd'))}</td>"
                f"<td>{fmt_multiple(scenario.get('market_cap_to_base_revenue'))}</td>"
                "</tr>"
            )
        return (
            "<table><thead><tr><th>Case</th><th>MW</th><th>Low Revenue</th><th>Base Revenue</th><th>High Revenue</th><th>Mkt Cap / Base Rev</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    return "<p class=\"muted\">No scenarios recorded yet.</p>"


def render_company_valuation_bridge(bridge: dict[str, Any]) -> str:
    if not bridge:
        return ""

    rows = []
    details = []
    for company in bridge.get("companies", []):
        rows.append(
            "<tr>"
            f"<td><a href=\"#valuation-{esc(company.get('ticker', '').lower())}\">{esc(company.get('ticker', ''))}</a></td>"
            f"<td>{esc(company.get('model_bucket', ''))}</td>"
            f"<td>{fmt_money(company.get('market_cap_usd'))}</td>"
            f"<td>{fmt_value(company.get('contracted_or_screened_mw'))}</td>"
            f"<td>{fmt_money(company.get('annualized_revenue_usd'))}</td>"
            f"<td>{fmt_multiple(company.get('market_cap_to_annualized_revenue'))}</td>"
            f"<td>{esc(company.get('decision', ''))}</td>"
            "</tr>"
        )
        details.append(
            "<div class=\"model-detail\" "
            f"id=\"valuation-{esc(company.get('ticker', '').lower())}\">"
            f"<h3>{esc(company.get('ticker', ''))} · {esc(company.get('name', ''))}</h3>"
            f"<p>{esc(company.get('read', ''))}</p>"
            "<h3>Scenario Screen</h3>"
            f"{render_company_scenarios(company)}"
            "<h3>Next Required Inputs</h3>"
            f"{render_list(company.get('next_required_inputs', []))}"
            "</div>"
        )

    ranking = "".join(
        "<tr>"
        f"<td>{fmt_value(item.get('rank'))}</td>"
        f"<td>{esc(item.get('ticker', ''))}</td>"
        f"<td>{esc(item.get('reason', ''))}</td>"
        "</tr>"
        for item in bridge.get("ranking", [])
    )
    decision = bridge.get("decision", {})
    return (
        "<div class=\"company-valuation\">"
        f"<div class=\"section-head\"><h2>{esc(bridge.get('title', 'Company Valuation Bridge'))}</h2>"
        f"<span class=\"muted\">{esc(bridge.get('model_type', ''))} · {esc(bridge.get('as_of', ''))}</span></div>"
        f"<p class=\"decision\"><strong>Warning</strong> · {esc(bridge.get('warning', ''))}</p>"
        f"<h3>Method</h3>{render_list(bridge.get('method', []))}"
        "<table><thead><tr><th>Ticker</th><th>Bucket</th><th>Market Cap</th><th>MW</th><th>Annual Rev</th><th>Mkt Cap / Rev</th><th>Decision</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        f"<h3>Ranking</h3><table><thead><tr><th>Rank</th><th>Ticker</th><th>Reason</th></tr></thead><tbody>{ranking}</tbody></table>"
        f"<h3>Decision</h3><p><strong>{esc(decision.get('label', ''))}</strong> · {esc(decision.get('summary', ''))}</p>"
        f"<p>{esc(decision.get('position_rule', ''))}</p>"
        f"{''.join(details)}"
        "</div>"
    )


def render_valuation_bridge(bridge: dict[str, Any]) -> str:
    if not bridge:
        return ""

    rows = []
    details = []
    for case in bridge.get("screening_cases", []):
        rows.append(
            "<tr>"
            f"<td>{esc(case.get('ticker', ''))}</td>"
            f"<td>{esc(case.get('business_model', ''))}</td>"
            f"<td>{fmt_money(case.get('headline_annual_revenue_usd'))}</td>"
            f"<td>{fmt_money(case.get('headline_annual_revenue_per_mw_usd'))}</td>"
            f"<td>{esc(case.get('position_gate', ''))}</td>"
            "</tr>"
        )
        details.append(
            "<div class=\"model-detail\">"
            f"<h3>{esc(case.get('ticker', ''))} · {esc(case.get('contract_ref', ''))}</h3>"
            f"<p>{esc(case.get('read', ''))}</p>"
            "<h3>Sensitivity Inputs</h3>"
            f"{render_key_values(case.get('sensitivity', {}))}"
            "</div>"
        )

    conclusion = bridge.get("current_conclusion", {})
    return (
        "<div class=\"valuation-bridge\">"
        f"<div class=\"section-head\"><h2>{esc(bridge.get('title', 'Valuation Bridge'))}</h2>"
        "<span class=\"muted\">screening model</span></div>"
        f"<p class=\"decision\"><strong>Method</strong> · {esc(bridge.get('method', ''))}</p>"
        "<table><thead><tr><th>Ticker</th><th>Model</th><th>Annual Revenue</th><th>Annual/MW</th><th>Position Gate</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        f"<h3>Current Conclusion</h3><p><strong>{esc(conclusion.get('label', ''))}</strong> · {esc(conclusion.get('summary', ''))}</p>"
        f"<p>{esc(conclusion.get('next_build', ''))}</p>"
        f"{''.join(details)}"
        "</div>"
    )


def render_contract_models(models: list[dict[str, Any]]) -> str:
    if not models:
        return ""

    rendered = []
    for model in models:
        rows = []
        for contract in model.get("contracts", []):
            derived = contract.get("derived", {})
            rows.append(
                "<tr>"
                f"<td>{esc(contract.get('ticker', ''))}</td>"
                f"<td>{esc(contract.get('contract', ''))}</td>"
                f"<td>{esc(contract.get('status', ''))}</td>"
                f"<td>{fmt_money(contract.get('contract_value_usd'))}</td>"
                f"<td>{fmt_value(contract.get('critical_it_load_mw'))}</td>"
                f"<td>{fmt_value(contract.get('term_years'))}</td>"
                f"<td>{fmt_money(derived.get('headline_value_per_mw_usd'))}</td>"
                f"<td>{fmt_money(derived.get('annual_value_per_mw_usd'))}</td>"
                "</tr>"
            )

        detail_blocks = []
        for contract in model.get("contracts", []):
            source_url = contract.get("source_url")
            source = f" · <a href=\"{esc(source_url)}\">source</a>" if source_url else ""
            known_adjustments = contract.get("known_adjustments", [])
            known_adjustment_block = (
                f"<h3>Known Adjustments</h3>{render_list(known_adjustments)}"
                if known_adjustments
                else ""
            )
            detail_blocks.append(
                "<div class=\"model-detail\">"
                f"<h3>{esc(contract.get('ticker', ''))} · {esc(contract.get('contract', ''))}{source}</h3>"
                f"<p class=\"muted\">{esc(contract.get('basis', ''))}</p>"
                f"<p>{esc(contract.get('interpretation', ''))}</p>"
                f"{known_adjustment_block}"
                "<h3>Missing Inputs</h3>"
                f"{render_list(contract.get('missing_inputs', []))}"
                "</div>"
            )

        decision = model.get("decision", {})
        rendered.append(
            "<section class=\"contract-model\">"
            f"<div class=\"section-head\"><h2>{esc(model.get('title', 'Contract Model'))}</h2>"
            f"<span class=\"muted\">{esc(model.get('model_type', ''))} · {esc(model.get('as_of', ''))}</span></div>"
            f"<p class=\"decision\"><strong>Warning</strong> · {esc(model.get('warning', ''))}</p>"
            "<table><thead><tr><th>Ticker</th><th>Contract</th><th>Status</th><th>Value</th><th>MW</th><th>Years</th><th>Value/MW</th><th>Annual/MW</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            f"<h3>Decision</h3><p><strong>{esc(decision.get('label', ''))}</strong> · {esc(decision.get('summary', ''))}</p>"
            f"<p>{esc(decision.get('next_required_model', ''))}</p>"
            f"{''.join(detail_blocks)}"
            f"{render_valuation_bridge(model.get('valuation_bridge', {}))}"
            f"{render_company_valuation_bridge(model.get('company_valuation_bridge', {}))}"
            "</section>"
        )
    return "".join(rendered)


def render_report(topic: dict[str, Any], output_path: Path) -> None:
    rows = []
    sections = []
    for thesis in topic["theses"]:
        score = thesis["investability_score"]
        decision = thesis["decision"]
        rows.append(
            "<tr>"
            f"<td><a href=\"#{esc(thesis['id'])}\">{esc(thesis['title'])}</a></td>"
            f"<td><span class=\"score {score_class(score)}\">{score:.1f}</span></td>"
            f"<td>{esc(decision['label'])}</td>"
            f"<td>{esc(thesis.get('status', ''))}</td>"
            f"<td>{esc(thesis['evidence_summary']['evidence_count'])} / {esc(thesis['evidence_summary']['counter_evidence_count'])}</td>"
            "</tr>"
        )
        score_items = "".join(
            f"<div><span>{esc(key.replace('_', ' '))}</span><strong>{clamp_score(value):.1f}</strong></div>"
            for key, value in thesis.get("scores", {}).items()
        )
        sections.append(
            "<section class=\"thesis\" "
            f"id=\"{esc(thesis['id'])}\">"
            f"<div class=\"section-head\"><h2>{esc(thesis['title'])}</h2>"
            f"<span class=\"score {score_class(score)}\">{score:.1f}</span></div>"
            f"<p class=\"decision\"><strong>{esc(decision['label'])}</strong> · {esc(decision['description'])}</p>"
            "<div class=\"grid two\">"
            f"<div><h3>Investment Question</h3><p>{esc(thesis.get('investment_question', ''))}</p></div>"
            f"<div><h3>Market Mispricing</h3><p>{esc(thesis.get('market_mispricing', ''))}</p></div>"
            "</div>"
            "<h3>Candidate Assets</h3>"
            f"{render_assets(thesis.get('candidate_assets', []))}"
            "<div class=\"grid two\">"
            f"<div><h3>Claims</h3>{render_list(thesis.get('claims', []))}</div>"
            f"<div><h3>Counter Evidence</h3>{render_list(thesis.get('counter_evidence', []))}</div>"
            "</div>"
            "<h3>Evidence Stack</h3>"
            f"{render_evidence(thesis.get('evidence', []))}"
            "<div class=\"grid two\">"
            f"<div><h3>Watch Triggers</h3>{render_list(thesis.get('watch_triggers', []))}</div>"
            f"<div><h3>Score Breakdown</h3><div class=\"score-grid\">{score_items}</div></div>"
            "</div>"
            "</section>"
        )

    source_links = "".join(
        f"<li><a href=\"{esc(item.get('url', '#'))}\">{esc(item.get('title', 'Source'))}</a> · {esc(item.get('use', ''))}</li>"
        for item in topic.get("source_notes", [])
    )
    css = """
    :root { color-scheme: light; --ink:#261f1a; --muted:#71675f; --line:#e7d8c9; --paper:#fbf6ee; --panel:#fffaf3; --accent:#b7532a; --gold:#c99d5c; --green:#3f7f5f; --red:#a5483c; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--paper); color: var(--ink); line-height: 1.55; }
    .wrap { max-width: 1180px; margin: 0 auto; padding: 32px 22px 56px; }
    header { border-bottom: 1px solid var(--line); padding-bottom: 22px; margin-bottom: 24px; display: grid; gap: 10px; }
    h1 { font-size: clamp(32px, 6vw, 62px); line-height: 1; margin: 0; letter-spacing: 0; }
    h2, h3 { letter-spacing: 0; }
    h2 { margin: 0; font-size: 25px; }
    h3 { margin: 20px 0 8px; font-size: 15px; color: var(--accent); text-transform: uppercase; }
    p { margin: 0 0 10px; }
    a { color: var(--accent); }
    .muted { color: var(--muted); }
    .summary, .thesis, .case-memo, .asset-card, .portfolio-rules, .contract-model { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; margin: 18px 0; box-shadow: 0 8px 24px rgba(62, 38, 22, 0.05); }
    .case-memo { border-color: rgba(183, 83, 42, 0.42); }
    .asset-card { border-color: rgba(63, 127, 95, 0.38); }
    .summary table { margin-top: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { text-align: left; vertical-align: top; border-bottom: 1px solid var(--line); padding: 10px 8px; }
    th { color: var(--muted); font-size: 12px; text-transform: uppercase; }
    ul { margin: 0; padding-left: 20px; }
    li { margin: 5px 0; }
    .section-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line); padding-bottom: 12px; margin-bottom: 12px; }
    .decision { color: var(--muted); }
    .score { display: inline-flex; align-items: center; justify-content: center; min-width: 58px; height: 34px; border-radius: 999px; font-weight: 800; color: white; font-variant-numeric: tabular-nums; }
    .mini-score { display: inline-flex; align-items: center; justify-content: center; min-width: 48px; height: 30px; border-radius: 999px; background: #181914; color: #fffaf3; font-weight: 800; font-variant-numeric: tabular-nums; }
    .score-strong { background: var(--green); }
    .score-watch { background: var(--accent); }
    .score-backlog { background: var(--gold); }
    .score-avoid { background: var(--red); }
    .grid { display: grid; gap: 16px; }
    .grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .assets { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
    .asset { border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fffdf8; min-height: 150px; }
    .asset strong { display:block; font-size: 18px; color: var(--accent); }
    .asset span { display:block; font-weight: 700; margin: 2px 0 8px; }
    .asset em { display:block; color: var(--muted); font-size: 12px; font-style: normal; }
    .score-grid { display: grid; gap: 8px; }
    .score-grid div { display:flex; justify-content: space-between; gap: 10px; border-bottom: 1px dashed var(--line); padding-bottom: 6px; }
    .model-detail { border-top: 1px solid var(--line); margin-top: 12px; padding-top: 2px; }
    .valuation-bridge { border-top: 2px solid var(--line); margin-top: 18px; padding-top: 16px; }
    .company-valuation { border-top: 2px solid var(--line); margin-top: 18px; padding-top: 16px; }
    footer { color: var(--muted); font-size: 13px; margin-top: 24px; }
    @media (max-width: 820px) { .grid.two, .assets { grid-template-columns: 1fr; } .wrap { padding: 22px 14px 40px; } table { font-size: 13px; } }
    """
    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(topic['title'])}</title>
  <style>{css}</style>
</head>
<body>
  <main class="wrap">
    <header>
      <p class="muted">Investment Thesis Harness · {esc(topic.get('as_of', ''))}</p>
      <h1>{esc(topic['title'])}</h1>
      <p>{esc(topic.get('subtitle', ''))}</p>
      <p><strong>Research question:</strong> {esc(topic.get('research_question', ''))}</p>
    </header>
    <section class="summary">
      <h2>Decision Board</h2>
      <table>
        <thead><tr><th>Thesis</th><th>Score</th><th>Decision</th><th>Status</th><th>Evidence / Counter</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
    {render_portfolio_rules(topic.get('portfolio_rules', []))}
    {render_cases(topic.get('cases', []))}
    {render_asset_cards(topic.get('asset_cards', []))}
    {render_contract_models(topic.get('contract_models', []))}
    {''.join(sections)}
    <section class="summary">
      <h2>Source Notes</h2>
      <ul>{source_links}</ul>
    </section>
    <footer>
      This report is a research artifact, not investment advice. Scores are a discipline for comparing hypotheses, not a prediction engine.
    </footer>
  </main>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an investment thesis harness report.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--topic", default=None, help="Topic id under data/topics.")
    parser.add_argument("--no-history", action="store_true", help="Skip JSONL history update.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    topic_id = args.topic or config.get("default_topic")
    if not topic_id:
        raise SystemExit("No topic specified and config.default_topic is missing.")

    topic = enrich_topic(load_topic(str(topic_id)), config)
    topic["cases"] = load_cases(str(topic_id))
    topic["asset_cards"] = load_asset_cards(str(topic_id))
    topic["portfolio_rules"] = load_portfolio_rules(str(topic_id))
    topic["contract_models"] = load_contract_models(str(topic_id))
    output_dir = ROOT / str(config.get("output_dir", "outputs"))
    report_path = output_dir / "report.html"
    latest_path = output_dir / "latest.json"
    snapshot = build_snapshot(topic)

    render_report(topic, report_path)
    dump_json(latest_path, {"topic": topic, "snapshot": snapshot})

    if not args.no_history:
        upsert_history(ROOT / str(config["history_path"]), snapshot)

    print(f"report: {report_path}")
    print(f"latest: {latest_path}")
    if not args.no_history:
        print(f"history: {ROOT / str(config['history_path'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
