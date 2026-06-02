# Investment Thesis Harness

目标：把文章、X 长帖、财报、行业数据和价格异动，转成可跟踪、可证伪、可行动的投资假设。

This is an investment research harness, not an academic research system. It does not try to prove a topic is interesting. It tries to answer:

- Can this become a tradable thesis?
- What would prove it right or wrong?
- Is the payoff worth the timing, liquidity, and evidence risk?
- What should be watched next?

## Quick Start

```bash
python3 investment-thesis-harness/run.py
open investment-thesis-harness/outputs/report.html
```

运行后生成：

- `outputs/report.html`：可直接打开的投资研究 dashboard。
- `outputs/latest.json`：机器可读的最新 thesis 评分、决策和证据状态。
- `data/history/thesis_snapshots.jsonl`：按日期和主题去重的长期研究状态。

提交或部署前先跑校验：

```bash
python3 investment-thesis-harness/scripts/validate.py
```

## Harness Shape

The harness follows an investment lifecycle:

```text
Signal intake
  -> thesis extraction
  -> evidence stack
  -> counter-evidence / red team
  -> investability scoring
  -> decision state
  -> watch triggers
  -> historical updates
```

每个 thesis 都必须包含：

- `investment_question`：这是不是一个可下注问题。
- `market_mispricing`：市场为什么可能还没定价。
- `claims`：需要成立的核心判断。
- `evidence`：支持证据，优先官方、财报、SEC、行业数据。
- `counter_evidence`：反证和失效条件。
- `scores`：从 0 到 5 的投资可行性评分。
- `watch_triggers`：之后要观察什么变化。

## Current Seed Topic

`ai-physical-bottlenecks` covers the research line from recent Serenity / Leopold articles:

- CPO / silicon photonics
- optical modules and external laser sources
- SOI, MBE, high-purity materials
- AI power and data center constraints
- BTC miners pivoting into AI hosting
- humanoid robotics and rare earth bottlenecks

## Case Memos

文章、X 长帖、财报或新闻先进入 `data/cases/`，作为单次实战输入。Case memo 不直接改变投资结论，而是把一条市场叙事翻译成：

- extracted claims
- investment translation
- red flags
- case decision
- next actions

当前第一条实战 case：

- `data/cases/bruceblue-serenity-chokepoint-2026-05-25.json`
- source: `https://x.com/BruceBlue/status/2058901845402325243`

## Scoring

Each thesis is scored from 0 to 100 using weighted investment dimensions:

- demand_strength
- bottleneck_power
- evidence_quality
- market_mispricing
- catalyst_clarity
- tradability
- risk_control

Decision bands:

- `>= 75`: active candidate
- `60-74`: watchlist
- `45-59`: research backlog
- `< 45`: avoid until evidence improves

This is not investment advice. It is a repeatable research discipline for turning market narratives into falsifiable investment theses.

## Current Decision Layer

The system now has three layers:

1. `thesis board`：判断哪条市场假设值得跟踪。
2. `asset cards`：判断哪些股票/资产是该 thesis 的实际表达。
3. `contract economics / valuation bridge`：把 headline contract 变成年化收入、单位 MW 收入、已知调整项和 position gate。

当前结论：APLD、IREN、CORZ 可以留在 priority watchlist，但还不能自动买入。下一步必须补 company-level valuation bridge：EV/MW、net debt、融资成本、capex、稀释和 per-share capture。

当前矿股筛选结论：

- `CORZ`：最适合继续精算，合同最清楚，但扣 capex credits 后不算明显便宜。
- `APLD`：最好的合同增长故事，核心问题是融资、capex 和股东稀释。
- `IREN`：验证最强，但 GPU cloud 模型资本开支重，估值已拥挤。
- `CLSK`：最便宜的 power option，但没有 named AI tenant 前只能 research-only。
- `RIOT`：电力资源大，但当前 AMD 25MW 太小，至少等 200MW+ 绑定收入。

系统当前总判断是 `no_buy_signal_after_screening`：五个标的都算完后，仍是 watchlist，不是自动买入信号。

## Templates

新文章或新合同优先复制模板，不要从零写 JSON：

- `templates/case-memo.template.json`
- `templates/contract-model.template.json`

## Deployment Recommendation

当前建议双层部署：

- BTC macro 主站继续作为入口和索引，把本系统发布到 `investment-research.html`。
- 同时保留一个独立 repo / Pages 站点，方便以后把投资研究 harness 单独演进、授权、私有化或迁移到 Cloudflare Pages。

Public first choice:

```text
GitHub repo -> GitHub Actions -> GitHub Pages
```

Private later choice:

```text
GitHub repo -> Cloudflare Pages -> Cloudflare Access
```

独立 repo 里运行方式应改成：

```bash
python3 run.py
open outputs/report.html
```
