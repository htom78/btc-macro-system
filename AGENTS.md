# Agent Map

This repository is a public GitHub Pages research system for BTC macro, mNAV,
investment-thesis monitoring, market-temperature analysis, and tactical labs.
Future agents should treat it as an executable research harness, not a folder of
standalone static pages.

## Source Of Truth

- `home.html`: public site entry and navigation map.
- `tools/build_pages_site.sh`: Pages artifact builder.
- `tools/check_site_links.py`: generated-site internal link validator.
- `btc-macro-system/`: macro data generator and `latest.json`.
- `dao-system/`: BTC / macro / MSTR reflexivity state.
- `investment-thesis-harness/`: thesis extraction, scoring, and research report.
- `agent-harness/`: agent iteration contracts, scenarios, and repo-level checks.

## Required Loop

Before claiming that a system change is done, run:

```bash
bash agent-harness/scripts/run_harness.sh
```

For narrower work, run the closest deterministic validator:

```bash
python3 investment-thesis-harness/scripts/validate.py
bash tools/build_pages_site.sh _site
python3 tools/check_site_links.py --root _site
python3 agent-harness/scripts/validate.py --site-root _site
```

## Rules For Future Agents

- Read existing pages and generators before editing.
- Keep `AGENTS.md` as a map; put detailed contracts and eval rules under
  `agent-harness/`.
- Prefer deterministic checks before model judgment.
- If adding a first-class public page, update `home.html`,
  `tools/build_pages_site.sh`, and the harness scenarios/validator when needed.
- Do not touch unrelated untracked research artifacts unless the task explicitly
  asks for them.
