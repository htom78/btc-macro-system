# 大币合约策略系统

这个目录跟踪 `BTCUSDT / ETHUSDT / SOLUSDT / BNBUSDT` 的 Binance USD-M Futures 公共数据, 用于合约策略观察和复盘训练。

它不读取账户、不保存 API key、不下单。目标是把大币合约交易拆成可验证的剧本:

- BTC 做方向锚。
- ETH/SOL 做 beta 强弱轮动。
- BNB 做抗跌和交易所 beta 观察。
- 只在 `反抽失败空` 和 `reclaim 确认多` 两种剧本里行动。

更新一次:

```bash
python3 major-futures-system/scripts/update_major_futures.py
```

查看摘要:

```bash
python3 major-futures-system/scripts/update_major_futures.py --show
```

页面入口:

```text
major-futures-system/index.html
```

核心肌肉记忆:

- 价格低于 1h/4h 均线时, 不追多。
- 破位后等第一次回踩失败, 不追低。
- BTC 先 reclaim, ETH/SOL/BNB 才有 beta 多头观察价值。
- 负 funding 是燃料, 不是点火。
