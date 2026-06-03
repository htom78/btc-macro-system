# 2026-06-02 Skill Rerun — Investment Thesis Monitor

使用 `investment-thesis-monitor` 对旧标的重跑：MSTR / BTC / NVDA / GOOG / CRCL。

这不是买卖建议。目的只是把每个 thesis 变成可证伪、可监控、可复盘的系统。

## 方法

每个标的按同一结构复核：

1. 一句话 thesis
2. 三层模型：现金流地板 / 平台转折 / 远期期权
3. 核心公式
4. 竞争与替代向量
5. 什么算基本面真的变了
6. 监控变量
7. valuation / reflexivity
8. 资本配置与治理
9. anti-thesis
10. rubric score

## 快速结论

| 标的 | 当前判断 | 最该盯的变量 | 当前主要风险 | Rubric |
|---|---|---|---|---|
| BTC | 核心结构性资产仍成立 | ETF 持仓/净流、实际利率、链上安全预算 | ETF bid 反转、宏观风险资产化 | 95 |
| MSTR | thesis 明显弱于直接 BTC | mNAV、BTC/share、优先股/转债负担 | mNAV 折价下继续融资会伤害普通股 | 96 |
| NVDA | AI 工厂现金流地板极厚 | Data Center YoY、GM、FCF、ASIC 替代 | 客户自研 ASIC + capex 纪律 | 96 |
| GOOG | 搜索现金牛 + AI full-stack 组合成立 | Search growth、Cloud growth/margin、capex ROI | 反垄断 + AI 搜索替代 + capex 过热 | 95 |
| CRCL | 利息地板成立，平台化仍待证明 | USDC supply、short rate、retention、CPN/Other revenue | 降息、分销成本、USDT/PYUSD/银行稳定币 | 95 |

## BTC

### 一句话 thesis

BTC 不是普通风险资产；它是正在被 ETF、公司 treasury 和全球储值需求制度化的非主权货币资产，因为它把稀缺性、结算最终性和抗审查性绑定到同一个开放网络。

### 三层模型

- 现金流地板：没有现金流，地板来自货币化程度、流动性、持有者质量和网络安全预算。
- 平台转折：ETF、托管、衍生品和公司 treasury 把 BTC 从 cypherpunk asset 转成 institutionally reachable collateral。
- 远期期权：主权储备、跨境结算、货币重估、layer-2 支付。

### 核心公式

`BTC 货币化强度 = 持有者质量 × 可接入流动性 × 稀缺性可信度 × 网络安全预算`

当前观察：

- BTC price: about `$68,021`
- U.S. spot Bitcoin ETFs: `1,276,843 BTC`, about `6.08%` of 21M supply, updated `2026-06-01`
- IBIT alone: `784,910.5 BTC`, about `3.738%` of 21M supply

### 竞争与替代

- Gold attacks store-of-value legitimacy.
- Fiat/stablecoins attack payments convenience.
- ETH/SOL attack programmable settlement.
- ETFs do not attack BTC; they attack friction. But they also make BTC more macro-flow-sensitive.

### 基本面真的变坏

- ETF/treasury adoption stalls for multiple quarters while price remains liquidity-dependent.
- Hashrate/security budget weakens structurally after fee market fails to mature.
- Major jurisdictions restrict custody/ETF rails.
- BTC behaves only as high-beta Nasdaq for a full cycle and loses monetary diversification value.

### Anti-thesis

BTC may be maturing into a liquid risk asset rather than a monetary reserve. If ETF holders are momentum allocators, not long-duration believers, institutionalization can increase reflexive drawdowns instead of stabilizing the asset.

### 监控变量

Daily: BTC price, ETF net flows, ETF holdings.
Weekly: real rates, DXY, gold/BTC relative strength.
Quarterly: treasury adoption, custody/regulatory changes, hashrate/security trend.

## MSTR

### 一句话 thesis

MSTR is not a software company; it is a leveraged BTC capital-market vehicle whose value depends on whether its financing flywheel increases BTC per share without trapping common shareholders under a heavier capital stack.

### 三层模型

- 现金流地板：BTC holdings minus capital structure claims.
- 平台转折：premium-to-NAV financing flywheel that can issue expensive equity/credit to buy more BTC.
- 远期期权：becoming the preferred listed Bitcoin credit/equity complex.

### 核心公式

`MSTR common value ≈ BTC holdings value × mNAV premium - debt/preferred/common dilution drag`

Current local/live inputs:

- Holdings: `843,738 BTC`
- BTC price used in latest market snapshot: about `$68,021`
- BTC NAV: about `$57.39B`
- MSTR market cap: about `$45.74B`
- Implied common mNAV: about `0.80x`
- Local Saylor state: BTC Yield YTD `13.3%`, next earnings date `2026-07-31`, ATM remaining about `$26.27B`

### 竞争与替代

- Direct BTC attacks purity and lower fee/friction.
- IBIT/FBTC attack institutional-access premium.
- Other BTC treasury companies attack scarcity of the wrapper.
- Preferred/convertible stack attacks common equity claim from inside the capital structure.

### 基本面真的变坏

- mNAV remains below 1.0 and management still issues common equity for BTC.
- BTC/share stops rising or rises only by adding fragile senior claims.
- Preferred dividends and refinancing needs force asset sales or capex-like cash leakage.
- BTC ETFs fully replace MSTR's access premium.

### Anti-thesis

MSTR may have moved from "BTC/share accretion machine" to "complex capital stack on top of BTC." In that state, the common stock is not cleaner BTC exposure; it is a levered residual claim with refinancing, preferred, governance and dilution risks.

### 监控变量

Daily: mNAV, BTC/share, MSTR/BTC beta.
Weekly: 8-K financing actions, ATM/preferred issuance, debt repurchase/sale.
Quarterly: capital structure, preferred dividends, BTC yield quality, index inclusion odds.

## NVDA

### 一句话 thesis

NVIDIA is not merely a GPU vendor; it is the default AI factory integrator because it converts AI capex into usable intelligent capacity faster and with lower execution risk than alternatives.

### 三层模型

- 现金流地板：Data Center revenue × gross margin × FCF conversion.
- 平台转折：CUDA, NVLink, networking, full-stack rack systems, software and deployment certainty.
- 远期期权：physical AI, robotics, AI-RAN, Omniverse, edge AI.

### 核心公式

`AI factory floor = Data Center revenue × gross margin × FCF conversion × refresh cycle`

Current monitor inputs:

- Q1 FY2027 revenue: `$81.615B`
- Data Center revenue: `$75.2B`, up `92% YoY`
- Non-GAAP gross margin: `75.0%`
- Free cash flow: `$48.554B`
- Next quarter revenue guide: `$91.0B`
- Market cap / annualized FCF: about `28.6x`

### 竞争与替代

- AMD attacks GPU supply and price.
- Broadcom/custom ASICs attack mature, fixed, large-scale inference workloads.
- Google TPU / AWS Trainium / Microsoft Maia attack hyperscaler dependence.
- Power, HBM, CoWoS and networking bottlenecks attack supply, not necessarily demand.

### 基本面真的变坏

- Data Center growth slows while customer capex remains high.
- Gross margin breaks below 70% for more than a transient mix/supply reason.
- Networking attach rate falls.
- Hyperscalers shift incremental inference scale to custom ASICs.
- CUDA migration friction materially declines.

### Anti-thesis

NVIDIA's current economics may be the peak phase of a capex arms race. If model scaling ROI weakens or hyperscalers stabilize workloads on internal ASICs, the market may reprice NVIDIA from AI platform to cyclical capital equipment supplier.

### 监控变量

Daily: market cap / annualized FCF, supply-chain news.
Quarterly: Data Center revenue, GM, FCF margin, guide growth, networking mix.
Annual: hyperscaler ASIC share, CUDA/ROCm migration, capex ROI.

## GOOG

### 一句话 thesis

GOOG is not merely a search cash cow; it is a full-stack AI distribution company because Search, YouTube, Android, Cloud, TPU and Gemini let it both defend old attention markets and monetize new AI compute demand.

### 三层模型

- 现金流地板：Search/YouTube ads plus Google Services operating income.
- 平台转折：Cloud + Gemini + TPU convert internal AI capability into enterprise revenue and lower infrastructure dependency.
- 远期期权：Waymo, DeepMind, agentic search, enterprise AI subscriptions, AI-native devices.

### 核心公式

`GOOG floor = Search durability × ad monetization × Cloud growth/margin × capex ROI`

Current Q1 2026 inputs:

- Alphabet revenue: `$109.9B`, up `22%`
- Google Services revenue: `$89.6B`, up `16%`
- Search & other: `$60.399B`, up about `19%`
- Google Cloud: `$20.028B`, up `63%`
- Operating margin: `36.1%`
- Cloud operating income: `$6.598B`
- Market cap / annualized operating income: about `28.1x`

### 竞争与替代

- ChatGPT/Perplexity/Claude attack query habit and answer interface.
- Amazon/retail media attack commercial search ads.
- Microsoft/OpenAI attack enterprise AI distribution.
- Antitrust remedies attack default search distribution.
- NVIDIA reliance is partly attacked by Google's own TPU stack.

### 基本面真的变坏

- Search revenue growth turns negative or monetization per query deteriorates.
- AI Overviews / answer engines cannibalize ads faster than they expand query volume.
- Cloud growth slows before margins mature.
- Antitrust remedies weaken default distribution materially.
- Capex rises faster than durable AI revenue.

### Anti-thesis

GOOG may be using AI to defend the old Search rent rather than create a genuinely new profit pool. If capex intensity rises while Search monetization compresses, the "safe AI winner" thesis becomes a lower-quality capital-intensive defense story.

### 监控变量

Daily: antitrust headlines, Gemini/Search product adoption.
Quarterly: Search revenue, Cloud revenue/margin, capex, TAC, buybacks/dividend.
Annual: default distribution changes, AI search behavior, Waymo scale.

## CRCL

### 一句话 thesis

CRCL is not an AI stock; it is regulated dollar infrastructure whose floor is USDC reserve economics and whose upside depends on converting trusted circulation into payment-network fees.

### 三层模型

- 现金流地板：USDC circulation × short-rate yield × Circle retention.
- 平台转折：CCTP/CPN/Gateway/agent payments convert stablecoin usage into fee revenue.
- 远期期权：Arc, ARC token ecosystem, AI agent commerce, institutional settlement.

### 核心公式

`Interest floor = USDC circulation × short Treasury yield × Circle net retention`

Current monitor inputs:

- USDC circulation: about `$76.02B`
- 3-month Treasury rate: `3.78%`
- Net retention ratio assumption: `41.4%`
- Annual retained interest floor: about `$1.19B`
- CRCL market cap / retained floor: about `22.3x`
- USDC 30D change: `-1.72%`

### 竞争与替代

- USDT attacks global offshore dollar liquidity and emerging-market distribution.
- PYUSD attacks wallet and merchant distribution.
- Banks attack regulated corporate treasury use cases.
- Coinbase and other distributors attack retention by capturing reserve economics.

### 基本面真的变坏

- USDC share falls while the stablecoin market grows.
- Short rates fall and USDC growth does not offset the yield decline.
- Coinbase/distributor take worsens.
- CPN/Other Revenue fails to become material.
- Regulation narrows reserve economics or blocks key use cases.

### Anti-thesis

CRCL may remain a low-retention reserve-income business with strong social utility but limited shareholder capture. Stablecoin usage can grow while Circle shareholders capture too little of the network value.

### 监控变量

Daily: USDC supply, short rates, CRCL price/market cap.
Monthly: USDC vs USDT share, Visa/Artemis real-use dashboards.
Quarterly: RLDC margin, Other Revenue, CPN, Coinbase economics.

## SkillOpt-lite feedback from this rerun

### What worked

- The three-layer model prevented optionality from polluting the current cash-flow floor.
- The competition-by-attack-vector rule clarified MSTR vs BTC and NVDA vs ASICs.
- Adding valuation/reflexivity forced MSTR and GOOG to be less story-like.

### What still needs improvement

- The skill should explicitly require a "claim hierarchy" for each asset: common equity, senior debt, preferred, token, network, or commodity. This mattered for MSTR and CRCL.
- The skill should require a "who captures the value?" check before platform claims. This mattered for CRCL, BTC and GOOG.
- The skill should require a "capex intensity / reinvestment burden" field for AI companies. This mattered for NVDA and GOOG.

### Candidate bounded skill edits

Do not apply yet; validate on future examples first.

1. Add "claim hierarchy" under completeness modules.
2. Add "value-capture test" to platform transition.
3. Add "reinvestment burden" to monitoring design for capital-intensive AI/infrastructure businesses.

## Sources used

- Circle Q1 2026 results: https://www.circle.com/pressroom/circle-reports-first-quarter-2026-results
- NVIDIA Q1 FY2027 results: https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-first-quarter-fiscal-2027
- Alphabet Q1 2026 results: https://www.sec.gov/Archives/edgar/data/1652044/000165204426000043/googexhibit991q12026.htm
- Strategy Q1 2026 results: https://www.sec.gov/Archives/edgar/data/1050446/000105044626000024/mstr-20260505x8kxex991.htm
- Bitcoin ETF holdings: https://bitbo.io/treasuries/us-etfs/
- Local CRCL monitor: `crcl-floor-monitor/data/latest.json`
- Local NVDA monitor: `nvda-factory-monitor/data/latest.json`
- Local MSTR monitor: `data.db`, `notes/saylor_state.json`
