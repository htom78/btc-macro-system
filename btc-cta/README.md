# BTC_CTA · 一个 MA 策略到底值不值

> Bitstamp BTC/USD 全历史日线(2012–2026,5271 根)上,从评估 **MA95±4%** 出发,
> 一路走到自优化 harness、与 HODL 对决、再到心性与信念。
> 一次每个假设都过 holdout 的诚实研究——**包括那些被证伪的**。

这个项目最终的产出,不是某个"更好的策略",而是一条从**术**到**道**的认知链。
下面四节就是它的骨架。

---

## 一、术:MA95±4 良好不卓越,它卖的是回撤保险,不是 alpha

- 用稳健性视角(看最差段),MA95±4 在 8 个 MA 策略里**夺冠**——三段都不掉链子,是个瞎选不出来的稳健解。
- 但它**不是 HODL 的"更优替代"**:
  - 历史(2012–2022)择时全面胜(熊市回撤保护极值钱:把 −77% 砍到 −35%)
  - 2023+ 顺畅单边牛市,**HODL 反超**(择时踏空 beta)
- 一系列负面结论澄清了边界:做空腿是拖累(砍)、交易 RSI 整合负向、参数调优=过拟合、
  crypto 内部多市场是伪分散。唯一真增量是 **continuous 连续仓位**(零新参数的结构性改进)。

> **一句话:** 无法预知行情的前提下,MA 择时相对 HODL 的全部价值 =
> **用确定的牛市收益损失,买熊市回撤保护 + 防止自己割在底部。**

## 二、法:别在"找策略"上缘木求鱼

- 6 轮迭代、Optuna 跨 5 策略族搜索、加 RSI、加币种——结论高度一致地收敛到:
  **在单一 BTC 价格序列上,技术择时的 alpha 天花板很低,一挖深就撞过拟合。**
- **holdout 是唯一照妖镜**:全样本调出的"最优参数",到没见过的数据上系统性塌陷。
- **调参 = 过拟合幻觉;结构性改进(零自由度)才是真增量。** 环境设计 > 聪明的优化——
  这正是 OpenAI / Anthropic harness engineering 的落点。
- 不停换策略找圣杯,**本质常是焦虑驱动**,不是技术问题。

## 三、心:心性是执行任何策略的前提,且弱点可工程化外包

- 同一个策略给两个心性不同的人,结果天差地别。**瓶颈从来不在策略,在持有它的那个人。**
- "强者心理"别玄学化,落到三件能验证的事:**把"要什么"定义对 · 诚实知道认知边界 · 活得久 > 赢得快**。
- 反直觉且最实用的一点:**心性弱点可以用机械纪律外包,不必靠"修炼成强者"**。
  MA 趋势策略当"纪律外骨骼",让会手抖的普通人用规则替代意志力,避免在最痛的点做最蠢的决定。
  **强者不是不会怕,是给恐惧上了护栏。**

## 四、道:买卖看 thesis,不看价格——对 BTC,这就是信念问题

- Howard Marks《Selling Out》的核心:**卖出/持有的正当理由必须来自前景(thesis),不是价格涨跌。**
- 纠正常见误读:**不是"看好=无条件长期持有"**(那会滑向"把标的当孩子养"的陷阱),
  而是**有条件**的持有——
  - 当初看好的理由还成立 + 没有更好的去处 → 持有
  - 该卖的唯一正当理由 = thesis 坏了 / 出现更好机会,**不是价格变了**
- **BTC 的特殊难点**:没有基本面锚(无现金流/估值),thesis 是叙事(数字黄金/抗通胀/网络采用)。
  所以"回到初衷"比股票更难也更重要——它逼你直面赤裸的信念问题。

> **孩子值得无条件的爱;标的只值得有条件的持有。** 区别就在这一个词:**有条件**。
> 对 BTC:别盯价格,定期回去问那个叙事还成不成立——成立就拿住(哪怕 −80%),不成立就走(哪怕在涨)。

---

## 怎么读这个项目

### 🌐 网站(推荐入口)
```bash
open index.html
```
- `index.html` — 概览 / 入口
- `report.html` — 全景报告(6 轮迭代 + harness 架构)
- `vs_hodl.html` — 择时 vs HODL(三段对比 + 信念旋钮 + 心性)

### 📄 研究文档(`research/`)
| 文档 | 内容 |
|---|---|
| strategy_evaluation.md | MA95±4% 评估 + 交易 RSI(负面) |
| ma_comparison_result.md | 8 策略横向 + 交叉测试 |
| vs_hodl_result.md | MA vs HODL 终极对比(含套牢煎熬期) |
| new_strategies_result.md | continuous 等新策略 holdout 验证 |
| multimarket_result.md | 多市场分散(负面) |
| harness_optimization_result.md | Optuna 自优化实跑 |
| harness_research.md | 3 篇 harness 文章 deep-research |
| rsi_self_improvement.md | 自优化(Recursive Self-Improvement)开源调研 |
| marks_selling_out_notes.md | Howard Marks《Selling Out》对撞 |

### ⚙️ 复跑(`src/`)
```bash
.venv/bin/python src/fetch_bitstamp.py      # 抓数据
.venv/bin/python src/backtest_vector.py     # 分段评估(主引擎)
.venv/bin/python src/harness_optimize.py    # 自优化 harness
.venv/bin/python src/backtest_vs_hodl.py    # MA vs HODL
.venv/bin/python src/backtest_ma_zoo.py     # 8 策略交叉测试
```

详细技术状态见 `PROJECT_CONTEXT.md`。

---

## 方法论来源
OpenAI *Harness Engineering* · Anthropic *Effective Harnesses for Long-Running Agents* ·
arXiv 2603.03329 *AutoHarness* · Howard Marks, Oaktree *Selling Out*

## 免责
本项目为研究记录,**非投资建议**。所有回测含历史假设(早期低价幻觉已分段标注),
过往业绩不代表未来。BTC 是否具备长期正期望是信念问题,数据替代不了这个判断。
