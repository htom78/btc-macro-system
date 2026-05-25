# BTC Macro Observation System

目标：把 BTC 价格、通胀、利率、美元、流动性、信用压力和美国债务压力放在同一个框架里，形成可复跑的中英双语观察系统。

Goal: place BTC price, inflation, rates, the dollar, liquidity, credit stress, and U.S. debt pressure into one bilingual repeatable research system.

## Quick Start

```bash
python3 btc-macro-system/run.py
open btc-macro-system/outputs/report.html
```

运行后会生成：

- `outputs/report.html`：可直接打开的中英双语静态报告。
- `outputs/latest.json`：机器可读的最新指标、信号和相关性结果。
- `data/history/observations.jsonl`：按 BTC 市场日期去重的长期观测历史。
- `data/raw/`：自动缓存的原始数据，已被 `.gitignore` 忽略。

## Long-Run Updates

手动更新一次：

```bash
btc-macro-system/scripts/update_once.sh
```

安装 macOS 每日自动更新，默认每天本地时间 08:10：

```bash
btc-macro-system/scripts/install_launchd.sh
```

指定时间，例如每天 07:30：

```bash
btc-macro-system/scripts/install_launchd.sh 7 30
```

查看调度日志：

```bash
tail -n 80 btc-macro-system/logs/update.log
tail -n 80 btc-macro-system/logs/update.err
```

历史文件是 JSONL，一行一个市场日期。重复运行同一天会更新同一行，不会重复追加。

English: run `scripts/update_once.sh` for a single refresh, or `scripts/install_launchd.sh` to install a daily macOS launchd job. The history store is `data/history/observations.jsonl`, with one deduplicated row per BTC market date.

## GitHub Pages Deployment

`.github/workflows/update-and-pages.yml` can run the same updater on GitHub Actions and publish the static report to GitHub Pages.

The hosted site exposes:

- `/`：latest report
- `/latest.json`：latest machine-readable data
- `/observations.jsonl`：long-run history, when available

The workflow runs on manual dispatch, daily schedule, and push to `main`.

## Data Sources

默认配置在 `config.json`。

宏观与债务数据来自 FRED CSV：

- `CPIAUCSL`：CPI
- `FEDFUNDS`：联邦基金有效利率
- `DGS10`：10 年期美债收益率
- `DFII10`：10 年期实际收益率
- `T10YIE`：10 年期通胀预期
- `T10Y2Y`：10 年减 2 年收益率曲线
- `M2SL`：M2
- `WALCL`：美联储资产负债表
- `DTWEXBGS`：广义美元指数
- `VIXCLS`：VIX
- `BAMLH0A0HYM2`：高收益债利差
- `GFDEGDQ188S`：联邦总债务/GDP
- `FYGFGDQ188S`：公众持有联邦债务/GDP
- `FYOIGDA188S`：联邦利息支出/GDP

BTC 价格默认来自 Blockchain.com public chart API；如果接口不可用，脚本可以 fallback 到 CoinGecko 最近 365 天价格。

## Reading The System

系统分三层：

1. 宏观流动性：M2、美联储资产负债表、美元、实际利率。
2. 政策约束：CPI、通胀预期、联邦基金利率、收益率曲线。
3. 财政压力：债务/GDP、公众持有债务/GDP、利息支出/GDP。

`Regime score` 只是状态压缩，不是价格预测。它的含义是：

- `supportive`：流动性、利率、美元和风险偏好整体更有利于 BTC。
- `mixed`：信号互相抵消，BTC 更容易受链上结构、ETF flow 或新闻冲击影响。
- `hostile`：实际利率、美元、通胀或信用压力压制风险资产。

## Extension Points

下一步可以接：

- Glassnode/CryptoQuant API：MVRV、SOPR、LTH/STH、交易所净流入。
- ETF flow：现货 ETF 净流入、成交量、持仓。
- 自动化：每天或每周跑一次，把 `latest.json` 用作提醒条件。
