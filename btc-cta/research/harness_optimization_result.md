# 自优化 Harness 实跑结果:跨策略族搜索 + holdout 验收

> 引擎:`src/harness_optimize.py`(Optuna TPE 120 trials/族 + 三段锁死 walk-forward)。
> 这是 pwb-alphaevolve 范式里"不依赖 LLM"的核心闭环。日期 2026-06-07。
> 数据三段:train 2015–2019 / select(OOS) 2020–2022 / holdout(锁死) 2023-01+。

---

## 1. 各策略族:train 优化 → select(OOS) 泛化

| 策略族 | train Sharpe | train Calmar | **select Sharpe** | select Calmar | select CAGR% | select MaxDD% |
|---|---|---|---|---|---|---|
| **ma_envelope** | 1.70 | 2.26 | **1.35** | 1.81 | 70.1 | −38.7 |
| donchian | 1.67 | 2.17 | 1.27 | 1.43 | 64.6 | −45.3 |
| momentum | 1.84 | 2.81 | 0.92 | 0.65 | 39.0 | −60.3 |
| dual_ma | 1.67 | 2.04 | 0.90 | 0.68 | 38.3 | −56.7 |
| bollinger | 1.69 | 2.14 | 0.45 | 0.17 | 10.7 | −64.8 |

最优参数:
- ma_envelope: **n=119, band=0.041**(≈ 你最初的 MA95±4%!)
- donchian n=68 · momentum n=18 · dual_ma 49/104 · bollinger n=10,k=1.05

**Champion(按 select OOS Sharpe)= ma_envelope n=119 band=0.041**

---

## 2. HOLDOUT 验收(2023+,全程锁死,只看一次)

| 指标 | Champion(优化版 n=119) | 原始 MA95±4% | buy&hold |
|---|---|---|---|
| CAGR% | 21.9 | **24.7** | 46.2 |
| Sharpe | 0.76 | **0.82** | — |
| MaxDD% | −28.3 | −30.2 | −51.1 |
| Calmar | 0.77 | **0.82** | — |
| 胜率% | 57.1 | 37.5 | — |

---

## 3. 三个核心结论

### ① 你的直觉选对了策略族
自优化在 5 个策略族里独立搜索,**MA Envelope(包络带突破)胜出**,且最优带宽 0.041 几乎正中你最初拍的 **±4%**,周期 95→119 仅略长。通道突破型(ma_envelope / donchian)在 OOS 泛化最稳;均值回归型(bollinger)和裸动量在 OOS 直接崩。**说明 MA95±4% 不是瞎蒙,方向是对的。**

### ② 优化版在 holdout 上反而输给原始 MA95±4% —— 过拟合的活样本
即使有 train/select 两段防护,在 select 段调出的 n=119 到了真正没见过的 2023+ 泛化**更差**(Sharpe 0.76 < 0.82,Calmar 0.77 < 0.82)。这是 harness_research.md 里 **goal drift / 过拟合**的活体演示:**参数微调带来的"提升"是拟合历史的幻觉,holdout 一照就现形。** 这正是为什么 holdout 必须锁死、只看一次。

### ③ alpha 在 2023+ 确实衰减,但"砍回撤"价值还在
holdout 段所有趋势策略的 CAGR 都跑输 buy&hold(21.9/24.7 vs 46.2)——2023+ 是顺畅单边牛,趋势择时反而踏空部分涨幅。**但** MaxDD 大幅更优(−28~30% vs BH −51%)。即:这套策略在 2023+ **不再提供超额收益,只提供回撤保护**。和 strategy_evaluation.md 的"alpha 收缩"结论一致并量化了它。

---

## 4. Harness 这次到底产出了什么

不是"找到更牛的策略"。harness 的真正价值是**用纪律戳穿自欺**:
1. 证明策略族选对了(MA Envelope 客观夺冠)
2. 证明参数优化是过拟合幻觉(holdout 戳穿)
3. 量化了 alpha 衰减(2023+ 只剩回撤保护)

这就是 OpenAI/Anthropic harness 方法论的落点:**环境(三段锁死 + 多目标 + champion 验收)比聪明的优化更重要**。一个没有 holdout 的"自我优化"系统,只会越优化越自欺。

---

## 5. 复跑
```bash
.venv/bin/python src/harness_optimize.py
```
## 6. 下一步(若要接 LLM 提假设层)
- 装 `pwb-alphaevolve`(需 o3 / OpenAI 兼容 API key),用 EVOLVE-BLOCK 让 LLM 提新策略
- 把本脚本的三段锁死 + 多目标评估器作为它的 evaluator(护栏已就位)
- 真正要提升 2023+ 表现,方向不是调参,是换维度:波动率目标仓位 / 多市场分散 / 另类数据
