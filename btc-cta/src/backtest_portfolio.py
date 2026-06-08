"""多市场分散趋势组合 —— 验证跨币种分散能否突破单 BTC 的 alpha 天花板。

每个币用已验证的 continuous 仓位信号(N=119, band=4.1%, 零自由度)。
两种组合权重:
  等权      : 每币 1/N
  风险平价  : 波动率倒数加权(1/vol_i 归一,shift 防未来)
对照:单 BTC continuous / BTC buy&hold / 等权多币 buy&hold。
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
N, BAND, COMM = 119, 0.041, 0.001
VOL_WIN = 20
TRADING_DAYS = 365
START = "2018-06-01"   # 保证所有币 MA119 就绪


def load():
    return pd.read_csv("data/multi_close.csv", parse_dates=["date"]).set_index("date")


def continuous_pos(close):
    ma = close.rolling(N).mean()
    dist = (close - ma) / ma
    pos = (dist / (2 * BAND)).clip(0, 1)
    pos[ma.isna()] = 0.0
    return pos


def metrics(net, idx, label):
    equity = (1 + net).cumprod()
    years = (idx[-1] - idx[0]).days / 365.25
    cagr = equity.iloc[-1] ** (1 / years) - 1
    vol = net.std() * np.sqrt(TRADING_DAYS)
    sharpe = net.mean() * TRADING_DAYS / vol if vol else 0
    dn = net[net < 0].std() * np.sqrt(TRADING_DAYS)
    sortino = net.mean() * TRADING_DAYS / dn if dn else 0
    maxdd = (equity / equity.cummax() - 1).min()
    calmar = cagr / abs(maxdd) if maxdd else 0
    return {"策略": label, "CAGR%": round(cagr*100, 1), "Sharpe": round(sharpe, 2),
            "Sortino": round(sortino, 2), "MaxDD%": round(maxdd*100, 1),
            "Calmar": round(calmar, 2)}


def portfolio_net(df, weight_mode):
    rets = df.pct_change()
    cols = df.columns
    pos = pd.DataFrame({c: continuous_pos(df[c]) for c in cols})

    if weight_mode == "equal":
        w = pd.DataFrame(1.0 / len(cols), index=df.index, columns=cols)
    elif weight_mode == "riskparity":
        inv = 1.0 / (rets.rolling(VOL_WIN).std().shift(1))
        inv = inv.replace([np.inf, -np.inf], np.nan)
        w = inv.div(inv.sum(axis=1), axis=0).fillna(1.0/len(cols))
    else:
        raise ValueError(weight_mode)

    eff = (w * pos).shift(1).fillna(0.0)            # 各币有效仓位
    gross = (eff * rets).sum(axis=1)
    turnover = (w * pos).diff().abs().sum(axis=1).fillna(0.0)
    return gross - turnover * COMM


def main():
    df = load().loc[START:]
    df = df.dropna(how="all")
    segs = {"全段 2018.6+": None, "2020+": "2020-01-01", "HOLDOUT 2023+": "2023-01-01"}
    pd.set_option("display.width", 200)

    for sname, start in segs.items():
        sub = df if start is None else df.loc[start:]
        idx = sub.index
        rows = []
        # 组合策略
        rows.append(metrics(portfolio_net(sub, "equal"), idx, "组合-等权(continuous)"))
        rows.append(metrics(portfolio_net(sub, "riskparity"), idx, "组合-风险平价(continuous)"))
        # 单 BTC continuous
        btc = sub["btcusd"]
        btc_pos = continuous_pos(btc)
        btc_net = btc_pos.shift(1).fillna(0)*btc.pct_change().fillna(0) - btc_pos.diff().abs().fillna(0)*COMM
        rows.append(metrics(btc_net, idx, "单BTC continuous"))
        # BTC buy&hold
        rows.append(metrics(btc.pct_change().fillna(0), idx, "BTC buy&hold"))
        # 等权多币 buy&hold
        ewbh = sub.pct_change().mean(axis=1).fillna(0)
        rows.append(metrics(ewbh, idx, "等权多币 buy&hold"))

        print(f"\n########## {sname}  ({idx.min().date()}→{idx.max().date()}) ##########")
        print(pd.DataFrame(rows).set_index("策略").to_string())


if __name__ == "__main__":
    main()
