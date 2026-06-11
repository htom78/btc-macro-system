# 强势小币合约策略系统

这个目录是 `btc-macro-system` 旁边的强势小币研究系统。它的目标不是喊单, 也不是自动下单, 而是把每天/每小时发现的强势小币沉淀成可前测、可证伪、可复盘的策略样本。

## 核心原则

- 只使用 Binance USD-M Futures 公共接口。
- 不读取账户, 不保存 API key, 不下单。
- 所有策略先进入状态机, 默认只做观察和纸面前测。
- 每个信号都必须有证伪条件。
- 先证明策略有 edge, 再讨论自动执行。

## 数据产物

- `data/latest.json`: 当前候选、策略状态、成熟度评分。
- `data/signal_events.jsonl`: 状态从 `watch` 进入 `alert` / `confirm_wait` / `paper_entry` 时追加一条事件。
- `data/forward_outcomes.jsonl`: 信号经过 `1h / 6h / 24h / 72h` 后追加纸面表现。
- `data/raw_snapshots/*.json`: 可选的时间戳快照, 用于排查。

每个候选还会记录 top-20 订单簿的执行风险:

- `spread_bps`: 最优买卖价差。
- `bid_depth_1pct_usdt` / `ask_depth_1pct_usdt`: 当前中间价上下 1% 内的可见深度。
- `thin_book`: spread 或 1% 深度不合格时标记为 true。

## 策略模型

第一版只保留 4 个模型, 避免系统过早复杂化:

- `rush_fade_short`: 高位冲高回落做空。
- `fake_break_long`: 假跌破反杀做多。
- `whale_long_squeeze`: 大户多头挤空。
- `crowded_reversal`: 高 Funding/OI 拥挤反转。

每个模型输出统一状态:

```text
idle -> watch -> alert -> confirm_wait -> paper_entry
```

后续如果被证伪或达到目标, 会通过事件和前测结果复盘, 而不是修改历史解释。

## 使用

更新一次:

```bash
python3 smallcap-futures-system/scripts/update_smallcap_system.py
```

强制包含关注标的:

```bash
python3 smallcap-futures-system/scripts/update_smallcap_system.py --focus ALLOUSDT,LABUSDT
```

查看摘要:

```bash
python3 smallcap-futures-system/scripts/update_smallcap_system.py --show
```

运行 agent harness:

```bash
python3 smallcap-futures-system/scripts/run_agent_harness.py --no-update --dry-run
python3 smallcap-futures-system/scripts/run_agent_harness.py --raw
python3 smallcap-futures-system/scripts/validate_harness.py
```

harness 规则放在 `harness/config.json`; 最新决策写入 `data/harness_state.json`, 并追加到 `data/harness_decisions.jsonl`。

打开页面:

```text
smallcap-futures-system/index.html
```

## 成熟度评分

页面里的成熟度不是策略胜率, 而是系统工程成熟度:

- 是否只使用公共数据。
- 是否有状态机。
- 是否写入 JSONL 历史。
- 是否已有前测结果。
- 是否覆盖足够多候选。
- 是否没有数据错误。
- 是否已经记录盘口执行风险。

90 分以上才代表系统足够稳定地进入长期前测; 不代表可以自动下单。

## 下一阶段

- 把现有 `tools/binance_smallcap_cli.py` 的评分和新系统特征库进一步合并, 避免 Python/前端双实现漂移。
- 加入更严格的滑点、手续费、资金费率和容量约束。
- 加入 BTC/ETH 环境噪音过滤。
- 做 30 天前测统计页面, 对每个模型分别统计命中率和最大不利波动。
