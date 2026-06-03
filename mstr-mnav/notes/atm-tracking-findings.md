# ATM 跟踪 — SEC 8-K 数据源验证结论

> 2026-05-27 跑了近 10 份 MSTR 8-K 实测 monitor.py 的 ATM 检测正则,
> 记录这一轮的发现 + 后续优化方向。

## 实测样本(过去 6 周 10 份 8-K)

| # | 日期 | 正文大小 | 检测结果 | 实际内容 |
|---|---|---|---|---|
| 1 | 2026-05-26 | 33K ch | ⚪ ATM cue 命中,无当期卖出额 | Cover 报,提"sales under ATM programs"但不给当期数字 |
| 2 | 2026-05-18 | 7.9K ch | ⚪ | 周报型,买 BTC 公告 + 脚注提 $21B 授权 |
| 3 | 2026-05-15 | 7.7K ch | ⚪ | 同上 |
| 4 | 2026-05-11 | 7.9K ch | ⚪ | 同上 |
| 5 | 2026-05-05 | 40K ch | ✓ $375M(**错检**) | 实际是 STRC daily trading volume,不是 ATM 卖出 |
| 6 | 2026-05-04 | 7.8K ch | ⚪ | 周报型 |
| 7 | 2026-05-01 | 8.6K ch | — | 非 ATM 相关 |
| 8 | 2026-04-27 | 7.9K ch | ⚪ | 周报型 |
| 9 | 2026-04-20 | 8.0K ch | ⚪ | 周报型 |
| 10 | 2026-04-13 | 8.1K ch | ⚪ | 周报型 |

## 核心发现

### 1. Strategy 的 8-K 披露规则
- **周报型 8-K(占 80%)**: 公告"过去 7 天买了 X BTC",**只提"under ATM programs"作为资金来源,不披露当期 ATM 卖出额**
- **月度/季度 cover 8-K(占 20%)**: 给 **YTD 累计** "raised $X.X billion in STRC gross proceeds",但混合多个产品(MSTR + STRC + STRD + STRF)

### 2. 想要精确数字必须看
- **10-Q / 10-K 季报**(精度: 季度,延迟 30-45 天):XBRL 字段
  - `ProceedsFromIssuanceOfCommonStock`
  - `ShareIssuanceProceedsFromAtTheMarketOffering`(如有)
  - 项目里 `fetch_saylor_state.py` 应该已经在干这个,需要扩展接 ATM 字段
- **MSTR Investor Updates 页面**:有时给 weekly/monthly summary,但**没有结构化数据,需要 NLP**

### 3. 当前正则的状态
**已收紧**:必须命中"卖出动作动词 + $X 同句内",避开"may issue up to $21B"。
**结果**:从 8/10 误检 → 1/10 误检(还有改进空间)。
**保守度合适**:宁可漏报,不要污染 db 的 atm_remaining 推导。

## 推荐路径(按优先级)

### P0(已做)
- ✅ 正则严格化,避免误检授权额度
- ✅ `_fetch_url` 加 SEC rate limit(6.6 req/s 安全间隔)
- ✅ 支持 `/ix?doc=` inline XBRL viewer 链接

### P1(下一步,如果要继续做)
- 扩展 `fetch_saylor_state.py` 抓 10-Q XBRL 里的 ATM proceeds 字段
- 改 db.sum_atm_sales_usd() 优先用 10-Q 季度数据,8-K 仅作 cover 报兜底
- 在 `notes/saylor_state.json` 加 `atm_used_ytd_usd` 字段(从 cover 报手动 / 自动)

### P2(野心一点)
- LLM fallback:正则 miss 时,把 8-K body 段落丢给 `analyst.py` 的 LLM 抽 ATM 金额
- 但要 prompt engineer 防止 LLM 把"$21B 授权"当卖出额(同样的坑)

## 设计教训

1. **正则做金融文本抽取脆弱**:措辞每年都在变,周报 vs cover 报格式不同
2. **XBRL 才是 source of truth**:结构化字段,标签明确,不会有"is this authorization or actual sale" 的歧义
3. **8-K 的优势是实时性**(7 天延迟),**但精度差**;10-Q 反过来(季度精度,30-45 天延迟)
4. **混合数据源**: 8-K 抓"event of ATM sale happened" 信号,10-Q 抓"sold $X total" 准确量

## 决定(当前 commit 状态)

保留 8-K 正则检测作为**事件信号**(知道 Saylor 在卖),
**不**依赖它做精确累计 — `saylor_state.atm_remaining_usd` 主要靠 JSON 手动维护 + 季度 10-Q 更新。

待 10-Q 自动化做完后,这条 8-K 正则降级为辅助签到。
