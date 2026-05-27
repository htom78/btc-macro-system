# BTC Macro System

This repository contains a small research system for watching the relationship between Bitcoin, U.S. macro conditions, and U.S. fiscal pressure.

Start here:

```bash
python3 btc-macro-system/run.py
open btc-macro-system/outputs/report.html
```

For long-run local updates:

```bash
btc-macro-system/scripts/install_launchd.sh
```

For free hosted updates, this repo includes a GitHub Actions workflow that runs the updater and publishes the report to GitHub Pages.

The first version uses public, no-key data sources:

- FRED for inflation, rates, liquidity, credit stress, and federal debt indicators.
- CoinGecko for BTC daily market price.

It is an observation and research tool, not a trading signal or investment recommendation.

## Binance Small-Cap Futures CLI

For the contract small-coin ladder idea:

```bash
python3 tools/binance_smallcap_cli.py scan --limit 10
python3 tools/binance_smallcap_cli.py simulate PLAYUSDT --strategy both
python3 tools/binance_smallcap_cli.py plan PLAYUSDT --notional 20
```

See `docs/binance-smallcap-cli.md`. The CLI defaults to dry-run / simulation mode; live order submission requires explicit flags and Binance Futures API credentials.
