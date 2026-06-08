# RSI = Recursive Self-Improvement:开源实现调研

> 术语澄清:本项目语境下 **RSI 有两义**——
> ① 交易指标 Relative Strength Index(见 strategy_evaluation.md,结论:负向不整合)
> ② **Recursive Self-Improvement 递归自我优化**(本文)。
> 用户原始"找 RSI 方向的开源实现"在 harness 主题下本意指 ②。
> star 数/活跃时间来自 `gh search repos` 实测,抓取于 2026-06-07。

---

## 1. 自我改进 Agent 开源实现

| 仓库 | ★ | 活跃 | 核心自改进回路 | 可运行 |
|---|---|---|---|---|
| **jennyzzt/dgm** (Darwin Gödel Machine, Sakana 官方) | 2088 | 2026-06 | 维护 agent **archive 族谱**,每轮选父代→读失败日志→改自己代码→SWE-bench 评估→存回档案。开放式进化,多分支防局部最优 | 是(需 sandbox) |
| **ShengranHu/ADAS** (ICLR 2025) | 1589 | 2026-06 | Meta Agent Search:元 agent 用代码定义新 agent→评估→写档案→迭代发明更好的 agentic 系统 | 是 |
| **MaximeRobeyns/self_improving_coding_agent** (SICA) | 341 | 2026-06 | 4 步环:评估→存档→**把"改进自己代码"当编码任务做**→用新版重复。强制 Docker 隔离 | 是(Docker) |
| **aiming-lab/AutoHarness** (arXiv 2603.03329 官方) | 309 | 2026-06 | 环境反馈迭代精炼 harness 代码,把运行时 LLM 决策替换成生成的策略代码 | 是 |
| **kayba-ai/autoharness** | 289 | 2026-06 | **control plane**:对 harness repo 提改动→跑 eval→留/弃候选→champion 晋升。`.autoharness/` 目录化状态,可断点续跑 | 是(pipx) |
| **Arvid-pku/Godel_Agent** (官方) | 185 | 2026-06 | 运行时 monkey-patch 自己的 `logic.py`,读自身代码+reward→动态改写逻辑 | 是 |

### 进化式代码优化(改程序而非 agent 自己——对量化最直接)
| 仓库 | ★ | 机制 |
|---|---|---|
| **algorithmicsuperintelligence/openevolve** (AlphaEvolve 开源版) | 6492 | MAP-Elites + island model + cascade evaluation(先便宜后贵筛选)+ 双重选择 + artifacts 错误反馈。LLM 当 mutation operator |
| **SakanaAI/ShinkaEvolve** | 1191 | 样本高效进化:多 patch 类型 + island archive + **多臂老虎机(UCB)选模型** + novelty 生成。Apache-2.0 |
| **SakanaAI/AI-Scientist-v2** | 6494 | agentic tree search 驱动的自动科研(假设→代码→实验→分析→迭代) |

---

## 2. 量化场景直接对口:假设→回测→评估→改进闭环

**最关键发现——已有人把 AlphaEvolve 范式套到交易策略,且自带过拟合护栏:**

| 仓库 | ★ | 闭环 + 护栏 |
|---|---|---|
| **paperswithbacktest/pwb-alphaevolve** | 123 | **遗传算法 + LLM mutation**:策略里 `EVOLVE-BLOCK` 标记可变区,LLM 只改这块。**评估器 = Backtrader + walk-forward**(内置防过拟合),输出 Sharpe/CAGR/Calmar/MaxDD JSON。hall-of-fame + 可选 MAP-Elites。`pip install pwb-alphaevolve` |
| tarsyang/quantevolve (OpenEvolve fork) | 44 | LLM 改策略→Binance 回测→选优。⚠️ **无 walk-forward / 样本外,过拟合敞口大,别抄评估层** |

### 参数选择 / 黑盒优化库(成熟可直接挂)
| 库 | ★ | 用途 |
|---|---|---|
| **optuna/optuna** | 14326 | TPE/贝叶斯优化 + **pruning**(差 trial 提前砍,省回测算力)。连续参数扫描标配 |
| **facebookresearch/nevergrad** | 4193 | 无梯度优化(进化/CMA-ES/遗传),适合离散/含噪目标 |
| **polakowo/vectorbt** | 7792 | 向量化回测,批量跑几千个想法 |

---

## 3. 给本项目的明确路线

**骨架抄 `pwb-alphaevolve`(123★)** —— 唯一把"LLM 进化 + 交易回测 + walk-forward 护栏"全拼好的开源实现,star 不高反而能完整读懂改造。借鉴四个模式:

1. **EVOLVE-BLOCK 标记**:不让 LLM 重写整个策略,只改框出的参数/逻辑块。AlphaEvolve/OpenEvolve/ShinkaEvolve 共同核心约束,大幅降低"改飞"概率。
2. **多指标 JSON 评估(Sharpe/Calmar/MaxDD/CAGR)**,不要单一 reward —— OpenEvolve 明确"No Single Reward Signal"是防 reward-hacking 设计。多目标 = 难过拟合单一指标。
3. **walk-forward 内建进评估器**(非事后补):LLM 看到的分数已是样本外分数,把防过拟合做成**硬约束**。
4. **控制回路状态管理**学 kayba-ai/autoharness:`.autoharness/` 目录存提案/记录/champion,**可断点续跑 + 可回滚**。

**选下一组参数**:别手写遗传算法。连续参数→Optuna(TPE+pruning);离散/含噪→Nevergrad;要"质量+多样性"防早熟→抄 OpenEvolve 的 MAP-Elites + island model。

---

## 4. 必须避开的坑(过拟合 = goal drift)

呼应 harness_research.md 第 3 节:**量化里的"自我优化"最大风险 = 过拟合历史 = 论文里的 goal drift**。优化目标(历史 Sharpe)与真实目标(未来收益)错位,系统越"自我改进"离实盘越远。工程红线:

1. **样本外数据对 LLM 不可见,且只用一次**。三段锁死:训练段(LLM 可见)/ walk-forward 选择段 / 最终 holdout(全程锁死,结束才看一次)。反复在 OOS 上迭代 = OOS 退化成 in-sample。
2. **多目标 + 多样性档案 = 过拟合天然刹车**;单目标 + 贪心选最优 = goal drift 加速器。DGM/OpenEvolve 里都是显式设计。
3. **强制沙箱执行**(SICA 用 Docker,DGM 用 sandbox):LLM 写的回测代码会读写文件/跑 shell,长跑无人值守时沙箱是防误删数据/改坏自己。
4. **保留 champion + 可回滚**:RSI 系统会偶尔自改坏,没有上一个已知好版本快照,一夜跑下来可能比起点更差。

**一句话**:抄 pwb-alphaevolve 的进化+walk-forward 骨架 → 参数选择换 Optuna/Nevergrad → 状态管理参考 kayba-ai/autoharness → 多样性防过拟合参考 OpenEvolve MAP-Elites。OOS 三段锁死、多目标评估、沙箱执行、champion 可回滚 —— 这五条是把"自我优化"和"过拟合自欺"区分开的工程红线。

---

## 链接(均已核实)
- https://github.com/paperswithbacktest/pwb-alphaevolve
- https://github.com/algorithmicsuperintelligence/openevolve
- https://github.com/SakanaAI/ShinkaEvolve
- https://github.com/jennyzzt/dgm
- https://github.com/MaximeRobeyns/self_improving_coding_agent
- https://github.com/kayba-ai/autoharness
- https://github.com/optuna/optuna · https://github.com/facebookresearch/nevergrad
