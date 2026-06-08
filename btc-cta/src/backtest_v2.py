"""基于评估结论的新策略假设 —— 全部过 holdout 验证。

痛点:MA95±4% 是 0/1 二元仓位,2023+ 单边牛市里"离场=空仓"踏空 beta,跑输 buy&hold。
方向:不调参(过拟合老路),换维度 —— 仓位连续化 + 不彻底踏空。

新假设(都基于已夺冠的 MA Envelope 趋势信号):
  base        : MA119±4.1% 0/1 (上一轮 champion,对照基准)
  vol_target  : 趋势在多头时,仓位=目标波动/实际波动,clip[0,1] (高波动减仓)
  core_overlay: 永远 w_core 底仓 + (1-w_core) 趋势择时 (保 beta)
  continuous  : 仓位随 (close-MA)/MA 距离线性 [0,1] (趋势越强仓越重)
  regime      : 高波动期才趋势择时,低波动期持有满仓 (按 regime 切 beta)
  combo       : core_overlay + vol_target 叠加
"""
from __future__ import annotations

import warnings
import numpy as np
import pandas as pd
from backtest_vector import load, _metrics

warnings.filterwarnings("ignore")
COMM = 0.001
N, BAND = 119, 0.041
TGT_VOL = 0.60          # 年化目标波动 60% (BTC 高波动,设低了过度减仓)
VOL_WIN = 20
W_CORE = 0.5


def trend01(close):
    ma = close.rolling(N).mean()
    pos = pd.Series(np.nan, index=close.index)
    pos[close > ma * (1 + BAND)] = 1.0
    pos[close < ma * (1 - BAND)] = 0.0
    pos = pos.ffill().fillna(0.0)
    pos[ma.isna()] = 0.0
    return pos, ma


def position(df, variant):
    close = df["close"]
    t, ma = trend01(close)
    ret = close.pct_change()
    rvol = (ret.rolling(VOL_WIN).std() * np.sqrt(365)).shift(1)  # shift 防未来函数
    vol_scale = (TGT_VOL / rvol).clip(0, 1).fillna(0.0)

    if variant == "base":
        pos = t
    elif variant == "vol_target":
        pos = t * vol_scale
    elif variant == "core_overlay":
        pos = W_CORE + (1 - W_CORE) * t
    elif variant == "continuous":
        dist = (close - ma) / ma
        pos = (dist / (2 * BAND)).clip(0, 1)           # 离 MA +8.2% 满仓,MA 处半仓
        pos[ma.isna()] = 0.0
    elif variant == "regime":
        hi_vol = (rvol > rvol.rolling(180).median())   # 高波动 regime
        pos = np.where(hi_vol, t, 1.0)                 # 高波动择时,低波动满仓
        pos = pd.Series(pos, index=close.index).fillna(0.0)
        pos[ma.isna()] = 0.0
    elif variant == "combo":
        pos = (W_CORE + (1 - W_CORE) * t) * vol_scale.clip(0.3, 1)  # 底仓也受波动调节但留 0.3 地板
    else:
        raise ValueError(variant)
    return pos.clip(0, 1)


def run(df, variant):
    close = df["close"]
    ret = close.pct_change().fillna(0.0)
    pos = position(df, variant)
    net = pos.shift(1).fillna(0.0) * ret - pos.diff().abs().fillna(0.0) * COMM
    equity = (1 + net).cumprod()
    bh = (1 + ret).cumprod()
    return _metrics(equity, bh, net, pos, df.index)


def main():
    df = load()
    variants = ["base", "vol_target", "core_overlay", "continuous", "regime", "combo"]
    segs = {"select(2020-2022)": ("2020-01-01", "2022-12-31"),
            "HOLDOUT(2023+)": ("2023-01-01", None)}
    cols = ["CAGR%", "BH_CAGR%", "Sharpe", "Sortino", "MaxDD%", "BH_MaxDD%", "Calmar", "持仓占比%"]
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)

    for sname, (a, b) in segs.items():
        sub = df.loc[a:b] if b else df.loc[a:]
        print(f"\n########## {sname}  ({sub.index.min().date()}→{sub.index.max().date()}) ##########")
        rows = [{"变体": v, **{c: run(sub, v)[c] for c in cols}} for v in variants]
        print(pd.DataFrame(rows).set_index("变体").to_string())


if __name__ == "__main__":
    main()
