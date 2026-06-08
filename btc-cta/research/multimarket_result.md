# 多市场分散趋势组合 —— 验证结果(负面)

> 引擎 `src/backtest_portfolio.py`。5 币(BTC/ETH/XRP/LTC/BCH)各用 continuous 信号
> (N=119, band=4.1%, 零自由度),等权 + 风险平价两种组合。日期 2026-06-07。
> 假设:跨币种分散能突破单 BTC 的 alpha 天花板。**结论:假设被证伪。**

## HOLDOUT(2023+)结果

| 策略 | CAGR% | Sharpe | MaxDD% | Calmar |
|---|---|---|---|---|
| **单 BTC continuous** | 26.0 | **0.92** | −22.9 | **1.13** |
| 组合-等权(continuous) | 9.2 | 0.43 | −31.7 | 0.29 |
| 组合-风险平价(continuous) | 8.9 | 0.44 | −29.9 | 0.30 |
| BTC buy&hold | 46.0 | 1.03 | −51.2 | 0.90 |
| 等权多币 buy&hold | 29.5 | 0.74 | −62.7 | 0.47 |

全段(2018.6+)同样:单 BTC continuous Sharpe 1.23 / Calmar 1.43,远超组合(0.68–0.77 / 0.35–0.44)。

## 为什么分散失败了(反直觉,但有清晰原因)

1. **山寨币本身是劣质资产**。等权多币 buy&hold(29.5)就已跑输 BTC buy&hold(46)——
   根源不是趋势信号,是 ETH/XRP/LTC/BCH 在 2023+ 这轮 BTC 主导行情里普遍弱。
   把负期望的标的等权进组合 = **用 beta 垃圾稀释 alpha**。
2. **crypto 内部是伪分散**。经典 CTA 分散增益来自几十个**低相关、各自正期望**的市场;
   这 5 个币相关性 0.7+,一荣俱荣一损俱损,分散既没降多少风险,又摊薄了唯一的 alpha 源(BTC)。
3. **趋势信号在山寨上更失效**:假突破多、趋势持续性差,continuous 在它们身上 Sharpe 很低。

## 真正的结论(强化而非推翻前面)

- **BTC 是这个篮子里唯一值得做趋势的标的。** 单 BTC continuous(Calmar 1.13)仍是目前全局最优。
- **要真分散,得跨资产类别**(BTC + 黄金/美股/美元/债券/商品的趋势),那才是低相关、
  各自正期望的组合——但需要别的数据源(非 Bitstamp),且引入传统 CTA 的多市场基础设施。
- crypto 内部加币种,只会重复"用劣质 beta 稀释优质 alpha"的错误。

## 净结论(到目前为止的全局最优)
**MA 趋势 + continuous 连续仓位,单做 BTC。** Calmar 1.13、回撤 −22.9%(BH −51%)。
下一步真正的增量在**跨资产类别分散**或**另类数据**(资金费率/链上),不在 crypto 内部堆币种。

## 复跑
```bash
.venv/bin/python src/fetch_multi.py
.venv/bin/python src/backtest_portfolio.py
```
