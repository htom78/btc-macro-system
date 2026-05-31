# 美股见顶 · 硬触发跟踪（market-top-triggers）

BTC 工作台的扩展子栏目：把"美股见顶"的判断，从一堆**永久偏高的软指标**里，提炼出少数**真正有择时价值的硬触发**，只盯它们翻红。

> 研究 / 跟踪用途，**非投资建议**。基于《刘翔·美股见顶10个信号》deep-research 核查。线上：<https://htom78.github.io/btc-macro-system/market-top-triggers/>

## 核心思路
网传「10 个见顶信号」里多数是估值/集中度/情绪类的**软指标**（席勒 CAPE ~43x、巴菲特指标 ~236%、集中度 48%）——已偏高多年、年年闪烁却长期不兑现，**择时无效**。真正能择时的是少数**硬触发**：

| 硬触发 | 为什么有择时价值 |
|---|---|
| **美联储实际加息/抽水** | 历史上唯一可靠的硬触发（2000、2007；Dalio）|
| **信用利差扩大（HY OAS）** | Dalio：危险先现于信用市场 |
| **盈利增速转负** | 真正的基本面触发（估值高只要盈利涨就能消化）|
| **长端实际利率突破** | 美债大跌＝代替美联储加息 |
| **市场广度恶化** | 指数新高但上涨股减少＝顶部结构 |

状态：`green 未触发 · amber 临界/预警 · red 已触发`。**只有硬触发翻红才是实质风险。**

## 更新
```bash
python3 market-top-triggers/scripts/update_trigger.py \
  --id credit --value "HY OAS 扩至 420bp" --status red \
  --asof 2026-08-15 --source FRED --note "信用报警"
python3 market-top-triggers/scripts/update_trigger.py --show
git add market-top-triggers && git commit -m "triggers: credit red" && git push
```
`id`: fed / credit / earnings / realrate / breadth。数据：`data/triggers.json`（看板源）+ `data/observations.jsonl`（历史）。
