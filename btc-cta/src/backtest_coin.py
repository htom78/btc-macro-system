"""币本位回测 —— 目标不是美元收益,是"让 BTC 数量变多"(stack sats)。

记账单位 = BTC。
  持 BTC 时:BTC 数量不变(币本位日收益 0)
  持 USDT 时:BTC 价格跌 -> 同样的 USDT 能买更多 BTC(币本位日收益 = -ret_btc)
  一次成功的"卖高买回":新 BTC = 旧 BTC × (卖价/买价) × (1-fee)²

基准 HODL 永远 = 1.0 BTC(币本位 0% 收益)。
策略 > 1.0 = 成功让 BTC 变多;< 1.0 = 择时反而亏了币(踏空/假信号买高卖低)。

口径换算: 币本位净值 = 美元净值 / 价格 × 初始价格(归一化起点=1)。
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
from backtest_vector import load

warnings.filterwarnings("ignore")
COMM = 0.001


def envelope(close, n, band):
    ma = close.rolling(n).mean()
    p = pd.Series(np.nan, index=close.index)
    p[close > ma*(1+band)] = 1.0; p[close < ma*(1-band)] = 0.0
    p = p.ffill().fillna(0.0); p[ma.isna()] = 0.0
    return p


def continuous(close, n=95, band=0.04):
    ma = close.rolling(n).mean()
    p = ((close-ma)/(2*band*ma)).clip(0, 1); p[ma.isna()] = 0.0
    return p


STRATS = {
    "HODL": None,
    "MA95±4%": lambda c: envelope(c, 95, 0.04),
    "MA200±5%": lambda c: envelope(c, 200, 0.05),
    "continuous": continuous,
}


def coin_metrics(df, posfn, label):
    close = df["close"]; ret = close.pct_change().fillna(0.0)
    if posfn is None:
        pos = pd.Series(1.0, index=close.index)
    else:
        pos = posfn(close)
    net_usd = pos.shift(1).fillna(0)*ret - pos.diff().abs().fillna(0)*COMM
    eq_usd = (1+net_usd).cumprod()
    # 币本位净值 = 美元净值 / 价格,归一化起点=1
    eq_btc = eq_usd / close * close.iloc[0]
    eq_btc = eq_btc / eq_btc.iloc[0]
    final = eq_btc.iloc[-1]
    maxdd_btc = (eq_btc/eq_btc.cummax()-1).min()
    switches = int((pos.diff().abs() > 0).sum()) if posfn else 0
    # 同时给美元倍数作对照
    usd_mult = eq_usd.iloc[-1]
    return {"策略": label, "最终BTC倍数": round(final, 3),
            "币本位收益%": round((final-1)*100, 1),
            "币本位最大回撤%": round(maxdd_btc*100, 1),
            "美元倍数": round(usd_mult, 1), "换仓次数": switches}


def main():
    df = load()
    ath_price = df["close"].max()
    ath_date = df["close"].idxmax()
    print(f"全样本 ATH: ${ath_price:,.0f} @ {ath_date.date()}")
    print(f"当前价: ${df['close'].iloc[-1]:,.0f} @ {df.index[-1].date()} "
          f"(距 ATH {df['close'].iloc[-1]/ath_price-1:+.1%})\n")

    segs = {
        "全样本 2012+": (None, None),
        "牛熊周期 2017.12–2019.12": ("2017-12-01", "2019-12-31"),
        "牛熊周期 2021.11–2023.06": ("2021-11-01", "2023-06-30"),
        "ATH 至今": (str(ath_date.date()), None),
        "近 2 年 2024.06+": ("2024-06-01", None),
    }
    pd.set_option("display.width", 200)
    for sname, (a, b) in segs.items():
        sub = df.loc[a:b] if (a or b) else df
        if len(sub) < 200:
            continue
        rows = [coin_metrics(sub, f, k) for k, f in STRATS.items()]
        out = pd.DataFrame(rows).set_index("策略")
        print(f"########## {sname}  ({sub.index.min().date()}→{sub.index.max().date()}) ##########")
        print(out.to_string())
        # 谁赢 HODL(>1 且最高)
        best = out["最终BTC倍数"].drop("HODL").idxmax()
        bval = out.loc[best, "最终BTC倍数"]
        verdict = f"{best} 让 BTC ×{bval}" if bval > 1 else f"全部 <1,择时反亏币(最好 {best} ×{bval})"
        print(f"  → 币本位最优: {verdict}\n")


if __name__ == "__main__":
    main()
