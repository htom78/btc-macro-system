# AI-SaaS 信号台（saas-signals）

BTC 工作台的扩展子栏目：把 **Datadog (DDOG) / Snowflake (SNOW)** 尽调里"要盯的三条硬信号"做成可逐季更新的跟踪系统。

> 研究与跟踪用途，**非买卖建议**。基线源自 2026-05 财报季 deep-research 尽调。

## 三条信号
1. **营收增速维持** —— 不滑向指引隐含的减速
2. **毛利率方向** —— AI mix 上升却不降毛利（SNOW 守 75% 是关键证伪点）
3. **NRR 净留存** —— 用量飞轮的体温计

每条给 `基线 / 守住线 / 证伪线 / 最新读数 / 状态灯（green·amber·red）`。

## 文件
```
saas-signals/
├── index.html                 看板(读 data/*,暖纸调,财报倒计时+状态灯+历史)
├── data/
│   ├── signals.json           当前状态(看板数据源)
│   └── observations.jsonl     观测历史(append-only)
└── scripts/update_signal.py   逐季更新工具
```

## 更新（财报后）
```bash
python3 saas-signals/scripts/update_signal.py \
  --ticker SNOW --signal grossmargin \
  --value "74.2%" --status amber --asof 2026-08-26 \
  --source "Q2 FY27" --note "AWS 降本对冲减弱"

python3 saas-signals/scripts/update_signal.py --show   # 看当前
git add saas-signals && git commit -m "saas-signals: SNOW Q2" && git push
```
`signal`: growth / grossmargin / nrr · `status`: green / amber / red。push 触发 Pages 自动部署。

## 部署
本目录由根 `.github/workflows/update-and-pages.yml` 的 `cp -R saas-signals _site/saas-signals` 步骤纳入 Pages，线上地址 `https://htom78.github.io/btc-macro-system/saas-signals/`。

## 下一季节点
- DDOG Q2 FY26：2026-08-06
- SNOW Q2 FY27：2026-08-26
