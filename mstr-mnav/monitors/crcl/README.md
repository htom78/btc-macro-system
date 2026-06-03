# CRCL Interest Floor Monitor

This is a child monitor under the MSTR mNAV system. It tracks the lowest-level
cash-flow support for Circle/CRCL:

```text
USDC circulation * short Treasury yield * Circle net retention ratio
```

## Data Sources

- USDC circulation: DefiLlama stablecoin API, asset id `2`.
- Short rate: FRED `DGS3MO`.
- CRCL close: Stooq `crcl.us`, optional context only.
- Net retention: `config.json`, currently `0.414` from Circle Q1 2026 RLDC
  margin. Update this after new earnings.

## Run

From the repo root:

```bash
make crcl-monitor
```

Or from this directory:

```bash
../.venv/bin/python monitor.py
```

Outputs:

- `data/latest.json`
- `data/history/observations.jsonl`
- `data.db`
- `reports/report.html`
- `../static/crcl-floor-report.html` for the deployed Streamlit site

Install a daily macOS LaunchAgent:

```bash
./install_launchd.sh 8 20
```

## Interpretation

This monitor only measures the interest-floor layer. It does not prove the
platform thesis. CPN, Other Revenue, CCTP, Arc, and AI Agent usage should be
tracked separately as growth/optionality indicators.
