"""MA95±4% + RSI 增强组合回测。

目标: 验证 RSI 过滤能否改善基线策略在 2022+ 的 alpha 衰减。
基线已确认"仅做多"腿最优,故 RSI 增强都在仅做多基础上做。

变体:
  base      : MA95±4% 仅做多 (基线)
  rsi_gate  : 突破上轨 且 RSI < 70 才进场 (防追高/防顶部接盘)
  rsi_trend : 突破上轨 且 RSI > 50 才进场 (动量确认)
  rsi_exit  : 持多中 RSI > 80 提前离场 (超买止盈)
  combo     : RSI<70 进场 + RSI>80 离场 (双向 RSI 管控)

RSI 口径用 ta 库 (Wilder 平滑),与 TA-Lib 一致。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator

from backtest_vector import load, _metrics

N, BAND, COMM = 95, 0.04, 0.001
RSI_LEN = 14


def base_signal(close, n=N, band=BAND):
    ma = close.rolling(n).mean()
    upper, lower = ma * (1 + band), ma * (1 - band)
    return ma, upper, lower


def make_position(df, variant: str) -> pd.Series:
    close = df["close"]
    ma, upper, lower = base_signal(close)
    rsi = RSIIndicator(close, window=RSI_LEN).rsi()
    pos = pd.Series(np.nan, index=close.index)

    break_up = close > upper
    break_dn = close < lower

    if variant == "base":
        entry = break_up
    elif variant == "rsi_gate":
        entry = break_up & (rsi < 70)
    elif variant == "rsi_trend":
        entry = break_up & (rsi > 50)
    elif variant == "rsi_exit":
        entry = break_up
    elif variant == "combo":
        entry = break_up & (rsi < 70)
    else:
        raise ValueError(variant)

    pos[entry] = 1.0
    pos[break_dn] = 0.0                       # 跌破下轨离场(仅做多)
    if variant in ("rsi_exit", "combo"):
        pos[rsi > 80] = 0.0                   # 超买离场
    pos = pos.ffill().fillna(0.0)
    pos[ma.isna()] = 0.0
    return pos


def run(df, variant, comm=COMM) -> dict:
    close = df["close"]
    ret = close.pct_change().fillna(0.0)
    pos = make_position(df, variant)
    pos_eff = pos.shift(1).fillna(0.0)
    gross = pos_eff * ret
    cost = pos.diff().abs().fillna(0.0) * comm
    net = gross - cost
    equity = (1 + net).cumprod()
    bh = (1 + ret).cumprod()
    return _metrics(equity, bh, net, pos, df.index)


def main():
    df = load()
    variants = ["base", "rsi_gate", "rsi_trend", "rsi_exit", "combo"]
    segments = {"全样本": None, "2020+": "2020-01-01", "2022+": "2022-01-01"}
    pd.set_option("display.width", 240)
    pd.set_option("display.max_columns", 30)

    cols = ["CAGR%", "Sharpe", "Sortino", "MaxDD%", "Calmar", "胜率%", "换仓次数", "持仓占比%"]
    for seg_name, start in segments.items():
        sub = df if start is None else df.loc[start:]
        print(f"\n########## {seg_name}  ({sub.index.min().date()}→{sub.index.max().date()}) ##########")
        rows = []
        for v in variants:
            m = run(sub, v)
            rows.append({"变体": v, **{c: m[c] for c in cols}})
        out = pd.DataFrame(rows).set_index("变体")
        print(out.to_string())


if __name__ == "__main__":
    main()
