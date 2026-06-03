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

## BTC Dao Console（天 / 地 / 人）

`dao-system/` adds the root-level trading state layer:

- **天 / Macro liquidity**: reuses `btc-macro-system/outputs/latest.json`.
- **地 / Market structure**: BTC MA95/MA200, RSI/drawdown, and ETF-flow seed data.
- **人 / Treasury reflexivity**: local MSTR mNAV monitor DB or CSV fallback, including mNAV, BTC yield, and filing redlines.

Build the state JSON:

```bash
python3 dao-system/scripts/build_dao.py
open dao-system/index.html
```

The page reads `dao-system/data/dao-latest.json`. On GitHub Actions, mNAV data gracefully degrades if the private local DB is unavailable. Locally, the default DB path is `/Volumes/PortableSSD/Codes/mstr-mnav-monitor/data.db`, or set `MSTR_MNAV_DB=/path/to/data.db`.

The first version uses public, no-key data sources:

- FRED for inflation, rates, liquidity, credit stress, and federal debt indicators.
- CoinGecko for BTC daily market price.

It is an observation and research tool, not a trading signal or investment recommendation.

## Investment Thesis Harness

For AI physical bottleneck and asset-card research:

```bash
python3 investment-thesis-harness/run.py
open investment-thesis-harness/outputs/report.html
```

The GitHub Pages workflow publishes this report as `investment-research.html`, with machine-readable output at `investment-latest.json` and history at `thesis-snapshots.jsonl`.

## EveryDayZen Macro Notes

Static content system for macro essays, voiceover scripts, and infographic assets:

```bash
open everydayzen-macro/index.html
```

The GitHub Pages workflow publishes it under `everydayzen-macro/`.

## Binance Small-Cap Futures CLI

For the contract small-coin ladder idea:

```bash
python3 tools/binance_smallcap_cli.py scan --limit 10
python3 tools/binance_smallcap_cli.py long-scan --limit 12
python3 tools/binance_smallcap_cli.py simulate PLAYUSDT --strategy both
python3 tools/binance_smallcap_cli.py plan PLAYUSDT --notional 20
```

See `docs/binance-smallcap-cli.md`. The CLI defaults to dry-run / simulation mode; live order submission requires explicit flags and Binance Futures API credentials.

## Strong Small-Cap Futures System

For the multi-model small-cap futures strategy monitor:

```bash
python3 smallcap-futures-system/scripts/update_smallcap_system.py --limit 12 --focus ALLOUSDT,LABUSDT
open smallcap-futures-system/index.html
```

The GitHub Pages workflow publishes it under `smallcap-futures-system/`. It uses Binance Futures public APIs only and keeps strategy states, event history, forward outcomes, and execution-risk snapshots for research; it is not an auto-trading system.

## AI-SaaS 信号台（`saas-signals/`）

BTC 之外的扩展子栏目：把 **Datadog (DDOG) / Snowflake (SNOW)** 尽调里「要盯的三条硬信号」做成可逐季更新的跟踪系统。线上：<https://htom78.github.io/btc-macro-system/saas-signals/>。

三条信号，每条给 `基线 / 守住线 / 证伪线 / 状态灯`：

1. **营收增速维持** —— 不滑向指引隐含的减速
2. **毛利率方向** —— AI mix 上升却不降毛利（SNOW 守 75% 是关键证伪点）
3. **NRR 净留存** —— 用量飞轮的体温计

财报后逐季更新（自动写历史 + 更新看板状态，push 触发 Pages 部署）：

```bash
python3 saas-signals/scripts/update_signal.py \
  --ticker SNOW --signal grossmargin --value "74.2%" --status amber \
  --asof 2026-08-26 --source "Q2 FY27" --note "..."
python3 saas-signals/scripts/update_signal.py --show   # 看当前状态
```

数据接口：`saas-signals/data/signals.json`（看板源）· `saas-signals/data/observations.jsonl`（观测历史）。
下一季节点：DDOG Q2 FY26 = 2026-08-06，SNOW Q2 FY27 = 2026-08-26。详见 `saas-signals/README.md`。研究与跟踪用途，不构成投资建议。
