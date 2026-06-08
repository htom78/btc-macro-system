"""MA95 ±4% 包络带突破策略回测 (引擎: backtesting.py)。

策略:
  上轨 = MA(N) * (1 + band)
  下轨 = MA(N) * (1 - band)
  close 上穿上轨 -> 做多
  close 下穿下轨 -> 做空(可关闭,只做多模式)

输出: 全样本绩效 + 与 buy&hold 对比 + 手续费敏感性。
"""
from __future__ import annotations

import argparse
import pandas as pd
from backtesting import Backtest, Strategy


def load() -> pd.DataFrame:
    df = pd.read_csv("data/btcusd_1d.csv", parse_dates=["date"])
    df = df.set_index("date")
    # backtesting.py 需要首字母大写列名
    df = df.rename(columns={"open": "Open", "high": "High",
                            "low": "Low", "close": "Close", "volume": "Volume"})
    return df[["Open", "High", "Low", "Close", "Volume"]]


def SMA(arr: pd.Series, n: int) -> pd.Series:
    return pd.Series(arr).rolling(n).mean()


def make_strategy(n: int, band: float, allow_short: bool):
    class MAEnvelope(Strategy):
        def init(self):
            self.ma = self.I(SMA, self.data.Close, n)

        def next(self):
            price = self.data.Close[-1]
            ma = self.ma[-1]
            if ma != ma:  # NaN 预热期
                return
            upper = ma * (1 + band)
            lower = ma * (1 - band)
            if price > upper:
                if not self.position.is_long:
                    self.position.close()
                    self.buy()
            elif price < lower:
                if allow_short:
                    if not self.position.is_short:
                        self.position.close()
                        self.sell()
                else:
                    self.position.close()  # 只做多: 跌破下轨平多离场
    return MAEnvelope


def run(df, n, band, allow_short, commission, cash=100_000):
    bt = Backtest(df, make_strategy(n, band, allow_short),
                  cash=cash, commission=commission,
                  trade_on_close=True, exclusive_orders=True)
    return bt.run()


def fmt(stats) -> dict:
    keys = ["Return [%]", "Buy & Hold Return [%]", "CAGR [%]",
            "Sharpe Ratio", "Sortino Ratio", "Max. Drawdown [%]",
            "# Trades", "Win Rate [%]", "Profit Factor",
            "Avg. Trade [%]", "Exposure Time [%]"]
    return {k: stats.get(k) for k in keys}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=95)
    ap.add_argument("--band", type=float, default=0.04)
    ap.add_argument("--commission", type=float, default=0.001)
    args = ap.parse_args()

    df = load()
    print(f"数据: {df.index.min().date()} → {df.index.max().date()} "
          f"({len(df)} 根日线)\n")
    print(f"策略: MA({args.n}) ±{args.band:.0%} 包络带, 手续费 {args.commission:.2%}/边\n")

    rows = []
    for label, short in [("多空双向", True), ("仅做多", False)]:
        st = run(df, args.n, args.band, short, args.commission)
        d = fmt(st)
        d["模式"] = label
        rows.append(d)

    res = pd.DataFrame(rows).set_index("模式")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print(res.round(2).T.to_string())

    # 手续费敏感性 (多空双向)
    print("\n=== 手续费敏感性 (多空双向, 总收益%) ===")
    for c in [0.0, 0.0005, 0.001, 0.0025, 0.005]:
        st = run(df, args.n, args.band, True, c)
        print(f"  手续费 {c:.2%}/边 -> 总收益 {st['Return [%]']:.1f}% | "
              f"Sharpe {st['Sharpe Ratio']:.2f} | "
              f"交易 {int(st['# Trades'])} 笔")


if __name__ == "__main__":
    main()
