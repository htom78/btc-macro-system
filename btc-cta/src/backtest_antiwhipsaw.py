"""抗假信号(anti-whipsaw)研究 —— 币本位口径。

基线 = MA200±5%(reddit 原版),近 2 年被假信号坑到 ×0.89 币。
叠加 6 种抗假信号增强,看能否在保持/提升币本位收益的同时减少换仓、救回震荡市。

假信号 = 突破后立刻反转,让你卖低买高/买高卖低,白白付手续费 + 亏币。
增强思路:
  confirm_Nd  : 突破后连续 N 天确认才动(过滤一日假突破)
  wide_band   : 带子加宽到 ±8%(噪音要更大才触发)
  cooldown_N  : 一次交易后锁 N 天不反向(防来回扇)
  slope       : 突破 且 均线斜率同向(逆势突破不算)
  atr_band    : MA ± k·ATR 波动率自适应带(波动大时带子自动加宽)
  combo       : confirm_3d + slope (确认 + 趋势方向双过滤)
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
from backtest_vector import load

warnings.filterwarnings("ignore")
COMM = 0.001
N, BAND = 200, 0.05


def _ff(p, warm):
    p = p.ffill().fillna(0.0); p[warm.isna()] = 0.0
    return p


def base(close):
    ma = close.rolling(N).mean()
    p = pd.Series(np.nan, index=close.index)
    p[close > ma*(1+BAND)] = 1.0; p[close < ma*(1-BAND)] = 0.0
    return _ff(p, ma)


def confirm(close, days):
    ma = close.rolling(N).mean()
    above = (close > ma*(1+BAND)).rolling(days).sum() == days
    below = (close < ma*(1-BAND)).rolling(days).sum() == days
    p = pd.Series(np.nan, index=close.index)
    p[above] = 1.0; p[below] = 0.0
    return _ff(p, ma)


def wide(close, band=0.08):
    ma = close.rolling(N).mean()
    p = pd.Series(np.nan, index=close.index)
    p[close > ma*(1+band)] = 1.0; p[close < ma*(1-band)] = 0.0
    return _ff(p, ma)


def slope(close, look=20):
    ma = close.rolling(N).mean()
    up = ma > ma.shift(look)
    p = pd.Series(np.nan, index=close.index)
    p[(close > ma*(1+BAND)) & up] = 1.0
    p[(close < ma*(1-BAND)) | (~up)] = 0.0     # 跌破 或 均线掉头 都离场
    return _ff(p, ma)


def atr_band(df, k=4.0):
    close, high, low = df["close"], df["high"], df["low"]
    ma = close.rolling(N).mean()
    pc = close.shift(1)
    tr = pd.concat([high-low, (high-pc).abs(), (low-pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(20).mean()
    p = pd.Series(np.nan, index=close.index)
    p[close > ma + k*atr] = 1.0; p[close < ma - k*atr] = 0.0
    return _ff(p, ma)


def cooldown(close, days=15):
    """基线信号 + 一次交易后锁 days 天不反向。"""
    raw = base(close).values
    out = np.zeros(len(raw)); lock = 0; cur = 0.0
    for i in range(len(raw)):
        if lock > 0:
            lock -= 1
            out[i] = cur
            continue
        if raw[i] != cur:
            cur = raw[i]; lock = days
        out[i] = cur
    return pd.Series(out, index=close.index)


def combo(close):
    """confirm_3d + slope 双过滤。"""
    c = confirm(close, 3); s = slope(close)
    return ((c > 0) & (s > 0)).astype(float)


STRATS = {
    "base MA200±5": lambda df: base(df["close"]),
    "confirm_3d": lambda df: confirm(df["close"], 3),
    "confirm_5d": lambda df: confirm(df["close"], 5),
    "wide ±8%": lambda df: wide(df["close"]),
    "cooldown_15d": lambda df: cooldown(df["close"], 15),
    "slope 过滤": lambda df: slope(df["close"]),
    "atr_band ±4ATR": lambda df: atr_band(df),
    "combo(confirm+slope)": lambda df: combo(df["close"]),
}


def coin_stats(df, posfn, label):
    close = df["close"]; ret = close.pct_change().fillna(0.0)
    pos = posfn(df)
    net = pos.shift(1).fillna(0)*ret - pos.diff().abs().fillna(0)*COMM
    eq = (1+net).cumprod()
    eq_btc = eq/close*close.iloc[0]; eq_btc /= eq_btc.iloc[0]
    return {"策略": label, "BTC倍数": round(eq_btc.iloc[-1], 3),
            "币本位回撤%": round((eq_btc/eq_btc.cummax()-1).min()*100, 1),
            "换仓次数": int((pos.diff().abs() > 0).sum())}


def main():
    df = load()
    segs = {"全样本 2012+": None, "牛熊 2021.11+": "2021-11-01",
            "ATH 至今 2025.10+": "2025-10-06", "近2年(震荡) 2024.06+": "2024-06-01"}
    pd.set_option("display.width", 200)
    for sname, start in segs.items():
        sub = df if start is None else df.loc[start:]
        rows = [coin_stats(sub, f, k) for k, f in STRATS.items()]
        out = pd.DataFrame(rows).set_index("策略")
        print(f"\n########## {sname}  ({sub.index.min().date()}→{sub.index.max().date()}) ##########")
        print(out.to_string())


if __name__ == "__main__":
    main()
