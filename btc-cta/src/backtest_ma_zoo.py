"""MA 策略动物园 —— 自构思 6 个不同机理的 MA 策略 + 基准,统一三段交叉测试。

目的:不是挑最优(=过拟合),是看不同机理的 MA 策略哪些稳健、哪些只在某段灵光。
全部仅做多。交叉测试三段:全样本 / 2020+ / holdout 2023+。

策略机理:
  reddit_200_5   : MA200±5% 包络带 0/1            (reddit 原版,基准)
  user_95_4      : MA95±4% 包络带 0/1             (用户变体,基准)
  continuous     : 价格距 MA95 连续仓位 [0,1]      (前面验证的赢家)
  dual_cross     : MA50 > MA200 金叉满仓           (经典趋势)
  triple_align   : MA20>MA60>MA120 多头排列        (多重确认,更钝)
  slope_filter   : close>MA100 且 MA100 斜率向上    (价格+斜率双确认)
  keltner        : EMA20 ± 2·ATR20 波动率通道突破   (波动率自适应)
  dual_envelope  : close>MA50×1.03 且 close>MA200  (快线触发+慢线过滤)
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
from backtest_vector import load, _metrics

warnings.filterwarnings("ignore")
COMM = 0.001


def _ff(pos, warm):
    pos = pos.ffill().fillna(0.0); pos[warm.isna()] = 0.0
    return pos.clip(0, 1)


def envelope(close, n, band):
    ma = close.rolling(n).mean()
    p = pd.Series(np.nan, index=close.index)
    p[close > ma*(1+band)] = 1.0; p[close < ma*(1-band)] = 0.0
    return _ff(p, ma)


def continuous(close, n=95, band=0.04):
    ma = close.rolling(n).mean()
    p = ((close-ma)/(2*band*ma) + 0.5).clip(0, 1)   # MA 处 0.5 仓,±band 处 0/1
    return _ff(p, ma)


def dual_cross(close, f=50, s=200):
    mf, ms = close.rolling(f).mean(), close.rolling(s).mean()
    p = (mf > ms).astype(float); p[ms.isna()] = 0.0
    return p


def triple_align(close, a=20, b=60, c=120):
    ma, mb, mc = (close.rolling(x).mean() for x in (a, b, c))
    p = ((ma > mb) & (mb > mc)).astype(float); p[mc.isna()] = 0.0
    return p


def slope_filter(close, n=100, look=20):
    ma = close.rolling(n).mean()
    p = ((close > ma) & (ma > ma.shift(look))).astype(float); p[ma.isna()] = 0.0
    return p


def keltner(df, n=20, k=2.0):
    close, high, low = df["close"], df["high"], df["low"]
    ema = close.ewm(span=n, adjust=False).mean()
    pc = close.shift(1)
    tr = pd.concat([high-low, (high-pc).abs(), (low-pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(n).mean()
    p = pd.Series(np.nan, index=close.index)
    p[close > ema + k*atr] = 1.0; p[close < ema - k*atr] = 0.0
    return _ff(p, atr)


def dual_envelope(close, f=50, s=200, band=0.03):
    mf, ms = close.rolling(f).mean(), close.rolling(s).mean()
    p = pd.Series(np.nan, index=close.index)
    p[(close > mf*(1+band)) & (close > ms)] = 1.0
    p[close < mf*(1-band)] = 0.0
    return _ff(p, ms)


STRATS = {
    "reddit_200_5":  lambda df: envelope(df["close"], 200, 0.05),
    "user_95_4":     lambda df: envelope(df["close"], 95, 0.04),
    "continuous":    lambda df: continuous(df["close"]),
    "dual_cross":    lambda df: dual_cross(df["close"]),
    "triple_align":  lambda df: triple_align(df["close"]),
    "slope_filter":  lambda df: slope_filter(df["close"]),
    "keltner":       lambda df: keltner(df),
    "dual_envelope": lambda df: dual_envelope(df["close"]),
}


def run(df, posfn):
    close = df["close"]; ret = close.pct_change().fillna(0.0)
    pos = posfn(df)
    net = pos.shift(1).fillna(0)*ret - pos.diff().abs().fillna(0)*COMM
    eq = (1+net).cumprod(); bh = (1+ret).cumprod()
    return _metrics(eq, bh, net, pos, df.index)


def main():
    df = load()
    segs = {"全样本 2012+": None, "2020+": "2020-01-01", "HOLDOUT 2023+": "2023-01-01"}
    cols = ["CAGR%", "Sharpe", "MaxDD%", "Calmar", "胜率%", "换仓次数"]
    pd.set_option("display.width", 200)

    # 收集每段结果 + 计算跨段稳健性(Calmar 的 min,惩罚只在某段灵光的)
    allseg = {}
    for sname, start in segs.items():
        sub = df if start is None else df.loc[start:]
        rows = [{"策略": k, **{c: run(sub, f)[c] for c in cols}} for k, f in STRATS.items()]
        allseg[sname] = pd.DataFrame(rows).set_index("策略")
        print(f"\n########## {sname}  ({sub.index.min().date()}→{sub.index.max().date()}) ##########")
        print(allseg[sname].to_string())

    # 跨段稳健性排名:三段 Calmar 的最小值(越高=越稳,不靠单段)
    print(f"\n{'='*60}\n  跨段稳健性 (三段 Calmar 的最小值,越高越稳健)\n{'='*60}")
    rob = pd.DataFrame({s: allseg[s]["Calmar"] for s in segs})
    rob["最差段Calmar"] = rob.min(axis=1)
    rob["全段均值"] = rob[list(segs)].mean(axis=1)
    print(rob.sort_values("最差段Calmar", ascending=False).round(2).to_string())


if __name__ == "__main__":
    main()
