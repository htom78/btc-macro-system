"""MA 周期 × 带宽网格 —— 对比 reddit MA200±5% 原版 vs MA95±4% 变体,并看参数稳健性。

忠实 reddit 策略:0/1 二元,仅做多。
  close > MA(N)*(1+band) -> 满仓 (buy)
  close < MA(N)*(1-band) -> 空仓 (sell everything)
  中间 -> 维持上一仓位

重点不是挑最高分(=过拟合),是看:
  ① reddit(200,5%) vs user(95,4%) 谁更稳
  ② 两者周围参数是否平滑(稳健区) 还是孤立尖峰(过拟合)
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
from backtest_vector import load, signals, _metrics

warnings.filterwarnings("ignore")
COMM = 0.001
PERIODS = [50, 95, 100, 150, 200, 250]
BANDS = [0.00, 0.02, 0.04, 0.05, 0.08]


def bt(df, n, band):
    close = df["close"]
    ret = close.pct_change().fillna(0.0)
    pos = signals(close, n, band, allow_short=False)
    net = pos.shift(1).fillna(0)*ret - pos.diff().abs().fillna(0)*COMM
    eq = (1+net).cumprod(); bh = (1+ret).cumprod()
    return _metrics(eq, bh, net, pos, df.index)


def grid(df, metric):
    rows = []
    for n in PERIODS:
        row = {"MA": n}
        for b in BANDS:
            row[f"±{int(b*100)}%"] = bt(df, n, b)[metric]
        rows.append(row)
    return pd.DataFrame(rows).set_index("MA")


def main():
    df = load()
    segs = {"全样本 2012+": None, "2020+": "2020-01-01", "HOLDOUT 2023+": "2023-01-01"}
    pd.set_option("display.width", 200)

    for metric in ["Calmar", "Sharpe"]:
        print(f"\n{'='*64}\n  网格:{metric}  (行=MA周期, 列=带宽, 仅做多 0/1)\n{'='*64}")
        for sname, start in segs.items():
            sub = df if start is None else df.loc[start:]
            g = grid(sub, metric)
            print(f"\n--- {sname} ---")
            print(g.round(2).to_string())

    # 重点对比 reddit vs user
    print(f"\n{'='*64}\n  reddit MA200±5%  vs  user MA95±4%  逐段对比\n{'='*64}")
    cfgs = [("reddit MA200±5%", 200, 0.05), ("user MA95±4%", 95, 0.04)]
    for sname, start in segs.items():
        sub = df if start is None else df.loc[start:]
        print(f"\n--- {sname} ---")
        rows = []
        for label, n, b in cfgs:
            m = bt(sub, n, b)
            rows.append({"策略": label, **{k: m[k] for k in
                        ["CAGR%","BH_CAGR%","Sharpe","MaxDD%","BH_MaxDD%","Calmar","胜率%","换仓次数"]}})
        print(pd.DataFrame(rows).set_index("策略").to_string())


if __name__ == "__main__":
    main()
