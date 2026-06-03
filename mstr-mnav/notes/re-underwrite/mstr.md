# MSTR re-underwrite

**Conviction #2 (2026-05-26) — 但仓位 40% 是组合最大头。BTC↔MSTR 顶端错位的另一半。**

## MSTR 特有的复核字段(Q2 补充)

MSTR 不是普通股票,是 BTC 杠杆衍生品 + 公司风险溢价。每次复核必过:

- **mNAV 状态**:当前值 + 历史分位(本仓库 monitor 已自动算 — 复核时直接看 dashboard)
  - 持续 mNAV > 1 → 飞轮 working,ATM 增发是 BTC-accretive
  - 持续 mNAV < 1 → 飞轮反转,继续增发反而稀释 BTC/share
  - 当前(2026-05-26)mNAV = 0.87,**飞轮处于反转状态**
- **资本结构**:债务到期 schedule / 转债条款 / preferred stock 余额 / ATM 剩余额度
  - 看 `notes/saylor_state.json`(每周自动 fetch)
- **管理层信号**:Saylor 公开发言频率 / 内部人交易 / 8-K 披露节奏
  - 本仓库 monitor 已抓 8-K(strategic 买卖 cue)
- **替代品 / 竞品**:BTC ETF(IBIT / FBTC)规模 + 流入趋势 — ETF 越成熟,MSTR 的"机构 BTC proxy"溢价就越没意义
- **税务 / 会计变化**:FASB ASU 2023-08(crypto fair value)的影响、公司是否被纳入 / 移出主要指数

## thesis 反转触发条件(预先想清楚)

**什么情况下你会卖 MSTR?**(不是降仓,是退出 thesis)预先写下来,避免到时被情绪左右:

- [ ] mNAV 持续 < 1 超过 X 个月,且 Saylor 继续 ATM 增发(说明管理层无视稀释信号)
- [ ] Saylor 离场 / CFO 变更 / 公司宣布出售 BTC 持仓
- [ ] BTC ETF 完全替代了 MSTR 的机构需求(衡量:MSTR 30-day vol vs BTC 30-day vol 收敛到接近 1)
- [ ] 你自己想加的其他条件

(复核时填这个清单,不要留空。10-year OG 不等于"任何条件下都不卖"。)

## 跟 BTC 仓位关系

跟 `btc.md` 互相校准 — 这两个标的的 thesis 强耦合,不要分开看。

---

## 2026-05-26 — 待复核(P1,1 个月内)
