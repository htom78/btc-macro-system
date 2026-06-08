# Harness Engineering 深度研究报告

> 来源:deep-research harness(106 agents / 3.65M tokens)。末段撞 Anthropic 服务端限流,
> 对抗验证未全部跑完。下方按**置信度**分级:
> - 🟢 **已验证(3-0 票)**:对抗验证三票通过
> - 🟡 **有来源未验证**:有一手引用,但因限流未完成对抗验证,按引用采信
> 研究日期 2026-06-06。

---

## 1. 什么是 Harness Engineering(vs 裸 prompt / 裸 agent)

🟢 **核心定义(OpenAI)**:Harness engineering 把软件工程从"写代码"重构为"设计 agent 的运行环境"。工程师的重心从**实现**转向**设计环境、指定意图、提供结构化反馈**。

> "Harness standardizes workflows, reducing reliance on handcrafted scripts and custom tooling. [engineers shift focus toward] designing environments, specifying intent, and providing structured feedback."
> — https://openai.com/index/harness-engineering/

🟢 **与裸 agent 的结构性区别(Anthropic)**:有效的 long-running harness 不是单条 prompt,而是**围绕模型的结构化脚手架**。Anthropic 把职责拆成两个不同角色:

> "an initializer agent that sets up the environment on the first run, and a coding agent that is tasked with making incremental progress in every session."
> — https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

**一句话区分**:
- **Prompt** = 一次性指令
- **Agent** = 模型 + 工具的单次自主循环
- **Harness** = 把 agent 包进可复用、可观测、可恢复、可自我改进的工程环境(环境搭建 / 状态 / 反馈 / 检查点 / 迭代回路)

---

## 2. 长时运行 agent 系统的关键设计模式

🟢 **上下文压缩必要但不充分(Anthropic)**:通用 agent SDK 自带 compaction,但长任务必须在其上叠加**刻意的工作流设计**。

> "The Claude Agent SDK is a powerful, general-purpose agent harness... It has context management capabilities such as compaction." — 但被明确指出"necessary but not sufficient"。
> — https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

提炼出的设计模式清单:

| 模式 | 作用 | 在本项目的对应 |
|---|---|---|
| **角色拆分** (initializer / worker) | 一次性搭建 vs 每次增量 | 数据抓取器(一次) vs 回测器(每次跑) |
| **状态外置 + 检查点** | 跨会话恢复,崩溃不丢进度 | 把每次回测结果/参数/结论落盘成 artifact |
| **上下文压缩 + 摘要** | 长任务不爆 context | 回测结果只回传摘要指标,不回传全 equity 曲线 |
| **结构化反馈回路** | 人给意图+反馈,不手搓 | 评估报告 → 下一轮参数/过滤器假设 |
| **可观测性** | 每步可追溯 | 每次 run 存参数指纹 + 指标 + 数据区间 |
| **错误恢复** | 单点失败可重试/降级 | 限流/抓数失败要可断点续跑 |

---

## 3. Recursive Self-Improvement(递归自我优化)

🟢 **OpenAI 的复利循环定义**(用户重点关注的概念):

> "every improvement to the harness makes subsequent agent runs more capable, which makes it possible to delegate more complex work, which surfaces the next gap, which gets encoded back into the harness."
> — https://openai.com/index/harness-engineering/

即一个**复利飞轮**:
```
改进 harness → agent 更强 → 能委派更难的活 → 暴露下一个 gap → 编码回 harness → (循环)
```
这不是模型自己改权重,而是**人 + agent 把每次暴露的能力缺口固化进环境**。这是"工程上可控"的自我优化。

🟡 **arXiv 2603.03329(AutoHarness)的机制**(有引用,未全验证):
- 用一个**较小的 LLM**(Gemini-2.5-Flash)**自动合成代码 harness**,通过少量"代码精炼轮次"迭代。
- 把 harness 生成 framing 为**在程序空间中搜索**,而非纯迭代 prompting——agent 给自己写胶水/控制回路。
- 具体回路:code hypotheses 放进一棵树,**Thompson sampling** 选下一个节点去精炼,gradient-free 的 LLM **"Refiner"** 根据 Critic/Evaluator 反馈重写代码:
  ```
  Evaluator → Critic → Refiner → New Code → Envs → Rollout → (回到 Evaluator)
  ```
- **极端形态(harness-as-policy)**:合成的代码可编码**整个决策策略**,推理时直接消除 LLM——self-written harness 取代 agent 本身。

> ⚠️ 这些 arXiv 细节因服务端限流未完成 3 票对抗验证,引用自 arxiv.org/abs/2603.03329 与 /pdf。采信前建议人工核对原文。

🟡 **风险与工程边界**(来自 deep-research 捞到的相关论文,未验证):
- **Alignment / Goal Drift**:迭代自改可能产生"目标漂移",有论文提出 Goal Drift Index(GDI)度量。
- **能力-对齐前沿**:早期循环高效改进,后期循环对齐成本上升(如 fluency vs factuality 的张力)。
- **工程边界**:自我优化要有**回归测试 + 约束保持检查**做护栏,否则越改越偏。

---

## 4. arXiv 2603.03329 核心论点(🟡 未全验证)

**论文 = AutoHarness**:核心主张是"**让 LLM 自动合成自己的代码 harness,而非人手搓**"。
- 方法:小模型 + 迭代代码精炼 + 树搜索(Thompson sampling)+ Critic/Refiner 回路。
- 结论(声称,1 票未驳倒):harness-as-policy 形态在 16 个单人游戏上平均 reward 0.745,超过 Gemini-2.5-Pro 和 GPT-5.2-High(0.707)。
- "小模型 + 自动合成 harness 跑赢大模型且更省钱"这一最强主张被 1 票质疑(未达 2/3 驳回阈值,存疑保留)。

---

## 5. 方法论 → 映射到本量化研究 harness

把"反复跑回测、扫参数、自我迭代策略"做成一个可自我优化的 long-running harness:

| Harness 概念 | 本项目落地 |
|---|---|
| **环境设计** > 写代码 | 把回测引擎做成稳定底座(已有 `backtest_vector.py`),人只给"假设" |
| **initializer / worker 拆分** | `fetch_bitstamp.py`(一次性建数据)/ `backtest_*.py`(每次跑) |
| **结构化反馈回路** | 评估报告 → 提出过滤假设(如 RSI)→ 回测验证 → 落盘 → 下一轮 |
| **递归自我优化(OpenAI 复利版)** | 每轮把"暴露的缺口"固化:做空拖累→砍空头;2022后衰减→加 RSI 过滤;再暴露→再加 |
| **AutoHarness 树搜索(进阶)** | 参数空间(N × band × 过滤器)用 Thompson sampling / 贝叶斯优化选下一组,而非网格暴力 |
| **护栏(防 overfit = 防 goal drift)** | walk-forward / 样本外 / 多分段验证,防止"越调越拟合历史" |

**关键洞察**:量化策略的"自我优化"最大风险 == 论文里的 goal drift == **过拟合历史**。
harness 的护栏(回归测试 + 样本外验证)在量化里就是 **walk-forward + out-of-sample**。
这条把 AI harness 工程和量化回测纪律精确对应起来了。

---

## 引用

- OpenAI, *Harness Engineering* — https://openai.com/index/harness-engineering/ 🟢
- Anthropic, *Effective Harnesses for Long-Running Agents* — https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents 🟢
- arXiv 2603.03329 *(AutoHarness)* — https://arxiv.org/abs/2603.03329 🟡 未全验证
- 相关(deep-research 捞到,未验证):arXiv 2605.09998(Continual Harness)、2410.04444(Gödel Agent)、2603.06333(GDI/SAHOO)、2605.27276(SIA)
