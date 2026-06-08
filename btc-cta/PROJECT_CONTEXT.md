# BTC_CTA — 比特币 CTA 策略回测 / 自优化研究 Harness

## 这个项目在做什么

两条线交汇:
1. **策略评估**:用 Bitstamp BTC/USD 全历史日线,评估 MA95±4% 包络带突破策略是否优秀,
   并基于结论迭代出更好的策略。
2. **harness 工程**:把这个回测器本身,按 OpenAI/Anthropic 的 harness engineering 方法论,
   组织成一个**可自我优化的 long-running 研究系统**(Recursive Self-Improvement)。

严肃程度:自用研究 + 方法论沉淀。

---

## 核心结论(到目前为止的全局最优)

> **MA 趋势 + continuous 连续仓位,单做 BTC。** holdout(2023+)Calmar 1.13、Sharpe 0.92、
> 回撤 −22.9%(buy&hold −51%)。这是对原始 MA95±4% 最干净的升级(零新参数)。

**但诚实的价值主张**(经 Howard Marks《Selling Out》对撞后修正):
> 这套策略卖的是**回撤保险,不是 alpha**。holdout 上所有趋势变体 CAGR 都跑输 buy&hold
> (26 vs 46)——择时踏空了 beta,正如 Marks "time, not timing" 所言,我们的数据替他作证。
> **要不要这笔"用收益损失换回撤封顶 + 规避人性崩盘"的交换,取决于你对 BTC 长期期望的信念,
> 数据替代不了这个判断。**

---

## 策略迭代历程(每一步都过 holdout)

| 轮次 | 做了什么 | 结论 | 文件 |
|---|---|---|---|
| 1 评估 | MA95±4% 双引擎回测 + 分段 | 良好不卓越,做空腿拖累应砍,2022+ 衰减 | strategy_evaluation.md |
| 2 交易 RSI | 叠加 RSI 过滤 5 变体 | **负向**,RSI 与突破型趋势冲突 | strategy_evaluation.md |
| 3 自优化 | Optuna 跨 5 策略族 + holdout | MA Envelope 客观夺冠(验证直觉),但**调参=过拟合**,holdout 输给原始 | harness_optimization_result.md |
| 4 新策略 | 仓位维度换新(vol/core/continuous/regime) | **continuous 连续仓位胜出**(结构性改进,非过拟合) | new_strategies_result.md |
| 5 多市场 | BTC+ETH+XRP+LTC+BCH 组合 | **负向**,crypto 内部是伪分散,劣质币稀释 BTC 的 alpha | multimarket_result.md |
| 6 对撞 | Marks《Selling Out》批判性审视 | 策略本质是"择时大罪",数据印证;价值应定位为回撤保险 | marks_selling_out_notes.md |

---

## 已完成数据/产出

| 产出 | 文件 | 要点 |
|---|---|---|
| 全历史日线 | `data/btcusd_1d.csv` | 5271 根,2012→2026,0 缺口 |
| 多币日线 | `data/multi_close.csv` | BTC/ETH/XRP/LTC/BCH |
| harness 深研 | `research/harness_research.md` | 3 篇一手来源 + 递归自优化方法论 |
| 自优化开源调研 | `research/rsi_self_improvement.md` | 骨架抄 pwb-alphaevolve |
| Marks 研读 | `references/marks_selling_out.pdf` + notes | 何时卖出的批判性对撞 |

---

## Harness 架构:可自我优化的 long-running 系统

> 映射 OpenAI"复利自优化循环" + Anthropic"initializer/worker 拆分" + AutoHarness 树搜索。
> 已落地版本 = `src/harness_optimize.py`(Optuna 搜索 + 三段锁死,不依赖 LLM)。

```
INITIALIZER (一次性,fetch_*.py) ──► 三段锁死: train / select(OOS) / holdout(只看一次)
        │
        ▼
SELF-IMPROVEMENT LOOP (worker,复利飞轮)
  1.提假设 → 2.回测(向量化引擎) → 3.多目标评估(Sharpe/Calmar/MaxDD,绝不单一reward)
  → 4.选择(Optuna/Nevergrad + MAP-Elites 保多样性) → 5.champion 晋升+可回滚
  └─► 暴露下一个 gap → 编码回 harness → 回到 1
        │
        ▼
HOLDOUT 验收 (全程锁死) ──► champion 在没见过的数据上验收,通过才采用
```

### 五条工程红线(区分"自我优化"与"过拟合自欺")
1. OOS 三段锁死(holdout 只看一次)  2. 多目标评估  3. 沙箱执行 LLM 代码
4. champion 可回滚  5. walk-forward 内建进评估器(硬约束)

> **实证教训**(轮次 3):即使有 train/select 两段防护,select 上调出的参数到 holdout 仍轻微
> 过拟合。**holdout 是唯一照妖镜**。这正是 harness 方法论"环境 > 聪明的优化"的落点。

### 借鉴的开源(详见 rsi_self_improvement.md)
- 进化+walk-forward 骨架 → `pwb-alphaevolve`
- 参数选择 → `optuna` / `nevergrad` · 多样性防过拟合 → `openevolve` MAP-Elites
- 控制回路状态管理 → `kayba-ai/autoharness`(目录化、断点续跑、回滚)

---

## 文件结构
```
data/   btcusd_1d.csv / multi_close.csv
src/    fetch_bitstamp.py        BTC 日线抓取(initializer)
        fetch_multi.py           多币抓取(end 翻页)
        backtest_vector.py       向量化主引擎(分段评估)
        backtest_ma.py           backtesting.py 交叉验证
        backtest_rsi.py          交易 RSI 整合(负面)
        harness_optimize.py      ★ 自优化 harness(多策略族+holdout)
        backtest_v2.py           ★ 新策略(continuous 等)
        backtest_portfolio.py    多市场组合(负面)
research/ harness_research.md            harness 方法论深研
          strategy_evaluation.md         MA95±4% 评估 + 交易 RSI
          rsi_self_improvement.md        自优化开源调研
          harness_optimization_result.md 自优化实跑
          new_strategies_result.md       新策略 holdout 验证
          multimarket_result.md          多市场分散(负面)
          marks_selling_out_notes.md     Marks 对撞
references/ marks_selling_out.pdf
```

## 下一步(未做,按价值排序)
- [ ] **回答信念问题**:信 BTC 长期正期望 → core_overlay/buy&hold;不信/怕尾部 → continuous
- [ ] **跨资产类别分散**(BTC + 黄金/美股/债券趋势)——真分散,非 crypto 内部堆币(需别的数据源)
- [ ] 另类数据维度:资金费率 / 链上信号(与价格趋势正交的 alpha)
- [ ] 把 continuous 写成可实盘信号脚本
- [ ] (可选)接 pwb-alphaevolve 的 LLM 提假设层(需 o3 API key,用本项目三段锁死作护栏)

## 环境
- venv: `.venv`(Python 3.9.6),依赖 pandas/numpy/ta/backtesting/optuna/requests/matplotlib
- 数据源:Bitstamp OHLC API(`step=86400`;BTC 用 start 游标,多币用 end 游标翻页)
```bash
.venv/bin/python src/backtest_vector.py     # 评估
.venv/bin/python src/harness_optimize.py    # 自优化
.venv/bin/python src/backtest_v2.py         # 新策略
.venv/bin/python src/backtest_portfolio.py  # 多市场
```
