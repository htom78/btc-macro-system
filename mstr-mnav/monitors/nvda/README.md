# NVDA AI Factory Monitor

This child monitor tracks the cash-flow floor behind NVIDIA's AI factory thesis:

```text
Data Center revenue * gross margin * free-cash-flow conversion
```

The daily component is market valuation around the latest quarterly floor:

```text
Market cap / annualized free cash flow
```

## Data Sources

- Latest quarterly fundamentals: `config.json`, currently NVIDIA Q1 FY2027.
- NVDA close: Stooq `nvda.us`.
- Capex context: TrendForce 2026 CSP capex estimate.

Quarterly data should be refreshed after each NVIDIA earnings release.

## Run

From the repo root:

```bash
make nvda-monitor
```

Outputs:

- `data/latest.json`
- `data/history/observations.jsonl`
- `data.db`
- `reports/report.html`
- `../static/nvda-factory-report.html` for the deployed Streamlit site

Install a daily macOS LaunchAgent:

```bash
./install_launchd.sh 8 35
```

## Interpretation

This monitor only measures the AI factory cash-flow layer. It does not prove the
robotics, physical AI, Omniverse, AI-RAN, or edge-computing optionality thesis.
