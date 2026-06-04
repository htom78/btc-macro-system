# Agent Harness

This harness turns the BTC macro / investment research site into a system that
future agents can iterate without relying on vibes.

## Harness Goal

Given a new research idea, earnings update, monitoring page, or dashboard change,
an agent should be able to:

1. Find the durable source of truth.
2. Make the smallest useful implementation.
3. Build the public Pages artifact.
4. Prove the important routes, data contracts, and research framework survived.
5. Leave a clear trail for the next iteration.

## Load-Bearing Components

- `../AGENTS.md`: repo map and required loop.
- `contracts/system-iteration-contract.md`: done criteria for any agent change.
- `scenarios/*.json`: battle/eval fixtures for recurring task types.
- `scripts/validate.py`: deterministic structural judge.
- `scripts/run_harness.sh`: local one-command harness runner.
- Existing validators:
  - `../investment-thesis-harness/scripts/validate.py`
  - `../tools/check_site_links.py`
  - `../tools/build_pages_site.sh`

## Harness Loop

```text
Contract
  -> implementation
  -> deterministic validators
  -> scenario/battle check
  -> build artifact
  -> link/data validation
  -> concise evidence report
```

## Current Deterministic Checks

The validator checks:

- repo-level agent map exists and points to this harness;
- scenario fixtures have the required schema;
- key first-class public pages are copied into `_site`;
- `home.html` exposes required routes;
- `market-temperature.html` reads `latest.json` and keeps the capital-cycle
  stage language;
- generated `_site/latest.json`, `_site/investment-latest.json`, and
  `_site/dao-system/data/dao-latest.json` preserve minimal data contracts.

## What Not To Automate Yet

- Do not add an LLM judge until deterministic rules catch the common regressions.
- Do not auto-generate buy/sell decisions from the harness.
- Do not scrape private or unstable data in CI.
- Do not make every research note public by default; first decide whether it is
  a public site artifact, local memo, or private monitor.
