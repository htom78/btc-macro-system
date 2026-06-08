"""向量化回测引擎 (纯 pandas/numpy) —— 交叉验证 backtesting.py 结果。

按比例全仓(无整数 BTC 限制),next-bar 信号在当根收盘成交。
重点: 分段回测,剔除 2012-2013 早期超低价的复利幻觉。

仓位逻辑 (MA-N ±band 包络带):
  close > MA*(1+band) -> 目标仓位 +1 (满多)
  close < MA*(1-band) -> 目标仓位 -1 (满空) 或 0 (仅做多)
  其余    -> 维持上一仓位 (突破后持有,不在带内频繁进出)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 365  # 加密 7x24


def load() -> pd.DataFrame:
    df = pd.read_csv("data/btcusd_1d.csv", parse_dates=["date"]).set_index("date")
    return df


def signals(close: pd.Series, n: int, band: float, allow_short: bool) -> pd.Series:
    ma = close.rolling(n).mean()
    upper, lower = ma * (1 + band), ma * (1 - band)
    pos = pd.Series(np.nan, index=close.index)
    pos[close > upper] = 1.0
    pos[close < lower] = -1.0 if allow_short else 0.0
    pos = pos.ffill().fillna(0.0)
    pos[ma.isna()] = 0.0           # 预热期空仓
    return pos


def backtest(df: pd.DataFrame, n: int, band: float, allow_short: bool,
             commission: float = 0.001) -> dict:
    close = df["close"]
    ret = close.pct_change().fillna(0.0)
    pos = signals(close, n, band, allow_short)
    # 当根收盘定仓 -> 次根生效
    pos_eff = pos.shift(1).fillna(0.0)
    gross = pos_eff * ret
    # 换手成本: 仓位变动幅度 * 手续费
    turnover = pos.diff().abs().fillna(0.0)
    cost = turnover * commission
    net = gross - cost
    equity = (1 + net).cumprod()
    bh_equity = (1 + ret).cumprod()
    return _metrics(equity, bh_equity, net, pos, df.index)


def _metrics(equity, bh_equity, net, pos, idx) -> dict:
    years = (idx[-1] - idx[0]).days / 365.25
    total = equity.iloc[-1] - 1
    bh_total = bh_equity.iloc[-1] - 1
    cagr = equity.iloc[-1] ** (1 / years) - 1
    bh_cagr = bh_equity.iloc[-1] ** (1 / years) - 1
    vol = net.std() * np.sqrt(TRADING_DAYS)
    sharpe = (net.mean() * TRADING_DAYS) / vol if vol else 0.0
    downside = net[net < 0].std() * np.sqrt(TRADING_DAYS)
    sortino = (net.mean() * TRADING_DAYS) / downside if downside else 0.0
    dd = equity / equity.cummax() - 1
    maxdd = dd.min()
    bh_dd = (bh_equity / bh_equity.cummax() - 1).min()
    calmar = cagr / abs(maxdd) if maxdd else 0.0
    # 交易统计 (一次仓位切换算一笔)
    switches = (pos.diff().abs() > 0).sum()
    # 按"持仓段"算胜率
    seg = (pos != pos.shift()).cumsum()
    seg_ret = net.groupby(seg).apply(lambda s: (1 + s).prod() - 1)
    active = pos.groupby(seg).first() != 0
    trade_rets = seg_ret[active.values]
    win = (trade_rets > 0).mean() if len(trade_rets) else 0.0
    exposure = (pos != 0).mean()
    return {
        "区间": f"{idx[0].date()}→{idx[-1].date()}",
        "年数": round(years, 1),
        "总收益%": round(total * 100, 1),
        "BH总收益%": round(bh_total * 100, 1),
        "CAGR%": round(cagr * 100, 1),
        "BH_CAGR%": round(bh_cagr * 100, 1),
        "Sharpe": round(sharpe, 2),
        "Sortino": round(sortino, 2),
        "MaxDD%": round(maxdd * 100, 1),
        "BH_MaxDD%": round(bh_dd * 100, 1),
        "Calmar": round(calmar, 2),
        "换仓次数": int(switches),
        "胜率%": round(win * 100, 1),
        "持仓占比%": round(exposure * 100, 1),
    }


def main():
    df = load()
    n, band, comm = 95, 0.04, 0.001
    print(f"=== MA({n}) ±{band:.0%} 包络带 | 手续费 {comm:.2%}/边 | 向量化引擎 ===\n")

    # 分段: 全样本 + 剔除早期低价幻觉的各阶段
    segments = {
        "全样本 2012+": None,
        "2015+": "2015-01-01",
        "2017+": "2017-01-01",
        "2020+": "2020-01-01",
        "2022+": "2022-01-01",
    }
    for short_label, short in [("多空双向", True), ("仅做多", False)]:
        print(f"\n########## {short_label} ##########")
        rows = []
        for name, start in segments.items():
            sub = df if start is None else df.loc[start:]
            m = backtest(sub, n, band, short, comm)
            m = {"分段": name, **m}
            rows.append(m)
        out = pd.DataFrame(rows).set_index("分段")
        pd.set_option("display.width", 240)
        pd.set_option("display.max_columns", 30)
        print(out.to_string())


if __name__ == "__main__":
    main()
