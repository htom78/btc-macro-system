"""MA 策略 vs HODL(buy&hold) 终极对比。

HODL 的真正代价不是收益数字,是煎熬。所以除常规指标外,加:
  最长水下天数 : 净值创新高后,要等多久才再创新高(套牢煎熬期)
  最深回撤     : 你要眼睁睁看着账户缩水多少

候选:HODL / reddit MA200±5 / user MA95±4 / continuous(v2定义) / core_overlay(50%底仓)
全部仅做多。三段:全样本 / 2020+ / holdout 2023+。
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
from backtest_vector import load

warnings.filterwarnings("ignore")
COMM = 0.001
TD = 365


def envelope(close, n, band):
    ma = close.rolling(n).mean()
    p = pd.Series(np.nan, index=close.index)
    p[close > ma*(1+band)] = 1.0; p[close < ma*(1-band)] = 0.0
    p = p.ffill().fillna(0.0); p[ma.isna()] = 0.0
    return p


def continuous_v2(close, n=95, band=0.04):
    ma = close.rolling(n).mean()
    p = ((close-ma)/(2*band*ma)).clip(0, 1)   # MA 处 0 仓,+2band 处满仓 (v2 低换手版)
    p[ma.isna()] = 0.0
    return p


def core_overlay(close, n=95, band=0.04, w=0.5):
    return w + (1-w)*envelope(close, n, band)


def longest_underwater(equity):
    peak = equity.cummax()
    underwater = equity < peak * 0.9999
    # 连续 True 的最大长度(天)
    best = cur = 0
    for u in underwater:
        cur = cur+1 if u else 0
        best = max(best, cur)
    return best


def stats(net, idx, label):
    eq = (1+net).cumprod()
    years = (idx[-1]-idx[0]).days/365.25
    cagr = eq.iloc[-1]**(1/years)-1
    vol = net.std()*np.sqrt(TD)
    sharpe = net.mean()*TD/vol if vol else 0
    maxdd = (eq/eq.cummax()-1).min()
    calmar = cagr/abs(maxdd) if maxdd else 0
    uw = longest_underwater(eq)
    return {"策略": label, "CAGR%": round(cagr*100, 1), "Sharpe": round(sharpe, 2),
            "最深回撤%": round(maxdd*100, 1), "Calmar": round(calmar, 2),
            "最长水下(天)": uw, "最长水下(年)": round(uw/365, 1)}


def run(df, posfn):
    close = df["close"]; ret = close.pct_change().fillna(0.0)
    if posfn is None:                       # HODL
        return ret
    pos = posfn(close)
    return pos.shift(1).fillna(0)*ret - pos.diff().abs().fillna(0)*COMM


def main():
    df = load()
    cands = {
        "HODL (buy&hold)": None,
        "reddit MA200±5%": lambda c: envelope(c, 200, 0.05),
        "user MA95±4%": lambda c: envelope(c, 95, 0.04),
        "continuous (v2)": continuous_v2,
        "core_overlay 50%": core_overlay,
    }
    segs = {"全样本 2012+": None, "2020+": "2020-01-01", "HOLDOUT 2023+": "2023-01-01"}
    pd.set_option("display.width", 200)
    for sname, start in segs.items():
        sub = df if start is None else df.loc[start:]
        rows = [stats(run(sub, f), sub.index, k) for k, f in cands.items()]
        print(f"\n########## {sname}  ({sub.index.min().date()}→{sub.index.max().date()}) ##########")
        print(pd.DataFrame(rows).set_index("策略").to_string())


if __name__ == "__main__":
    main()
