"""稳健囤币(satisficing)研究 —— 币本位。

问题:不追求最优,放宽条件,有没有"随便选个合理参数都能囤币"的稳健策略?
回答三件事:
  Part 1: 扫一大片参数(MA 周期×带宽,都加 3 天确认),统计多少比例能囤币(BTC>1)。
          若大部分都 >1 → 证明不用找最优,稳健区很宽。
  Part 2: 一个"钝策略" = 多均线投票(100/150/200 三条平均,不依赖单一参数)+ 3 天确认。
  Part 3: 钝策略 vs 精确最优 vs HODL,看它拿到最优的几成、稳不稳。

记账单位 = BTC。HODL = 1.0。
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
from backtest_vector import load

warnings.filterwarnings("ignore")
COMM = 0.001


def env_confirm(close, n, band, cdays=3):
    """MA±band 包络带 + 突破后连续 cdays 天确认。"""
    ma = close.rolling(n).mean()
    above = (close > ma*(1+band)).rolling(cdays).sum() == cdays
    below = (close < ma*(1-band)).rolling(cdays).sum() == cdays
    p = pd.Series(np.nan, index=close.index)
    p[above] = 1.0; p[below] = 0.0
    p = p.ffill().fillna(0.0); p[ma.isna()] = 0.0
    return p


def ensemble(close, periods=(100, 150, 200), band=0.05, cdays=3):
    """多均线投票:每条均线给 0/1,取平均 → 0/⅓/⅔/1 四档连续仓位。钝且不依赖单参数。"""
    sigs = [env_confirm(close, n, band, cdays) for n in periods]
    return sum(sigs) / len(sigs)


def coin_mult(df, pos):
    close = df["close"]; ret = close.pct_change().fillna(0.0)
    net = pos.shift(1).fillna(0)*ret - pos.diff().abs().fillna(0)*COMM
    eq = (1+net).cumprod()
    eq_btc = eq/close*close.iloc[0]; eq_btc /= eq_btc.iloc[0]
    return eq_btc.iloc[-1]


SEGS = {
    "全样本 2012+": None,
    "牛熊 2017.12+": "2017-12-01",
    "牛熊 2021.11+": "2021-11-01",
    "ATH 至今 2025.10+": "2025-10-06",
    "近2年 2024.06+": "2024-06-01",
}
PERIODS = [100, 125, 150, 175, 200, 225, 250]
BANDS = [0.0, 0.03, 0.05, 0.08]


def main():
    df = load()

    # ---------- Part 1: 参数稳健性 ----------
    print("="*70)
    print("  Part 1: 放宽参数,多少比例能囤币?(MA×带宽 共 %d 组,都加 3 天确认)" % (len(PERIODS)*len(BANDS)))
    print("="*70)
    print(f"{'分段':<22}{'能囤币%':>8}{'中位数':>9}{'最优':>8}{'最差':>8}")
    for sname, start in SEGS.items():
        sub = df if start is None else df.loc[start:]
        mults = [coin_mult(sub, env_confirm(sub["close"], n, b)) for n in PERIODS for b in BANDS]
        mults = np.array(mults)
        pct = (mults > 1.0).mean()*100
        print(f"{sname:<22}{pct:>7.0f}%{np.median(mults):>9.2f}{mults.max():>8.2f}{mults.min():>8.2f}")

    # ---------- Part 2 & 3: 钝策略 vs 最优 vs 中庸 vs HODL ----------
    print("\n" + "="*70)
    print("  Part 2-3: 钝策略(多均线投票) vs 精确最优 vs 中庸单参数 vs HODL")
    print("="*70)
    print(f"{'分段':<22}{'HODL':>7}{'集成投票':>9}{'中庸150±5':>11}{'精确最优':>9}{'集成/最优':>10}")
    worst = {"集成投票": 9, "中庸150±5": 9, "精确最优": 9}
    for sname, start in SEGS.items():
        sub = df if start is None else df.loc[start:]
        m_ens = coin_mult(sub, ensemble(sub["close"]))
        m_mid = coin_mult(sub, env_confirm(sub["close"], 150, 0.05))  # 中庸:一个钝的中间参数
        m_best = max(coin_mult(sub, env_confirm(sub["close"], n, b)) for n in PERIODS for b in BANDS)
        ratio = m_ens/m_best*100 if m_best > 0 else 0
        worst["集成投票"] = min(worst["集成投票"], m_ens)
        worst["中庸150±5"] = min(worst["中庸150±5"], m_mid)
        worst["精确最优"] = min(worst["精确最优"], m_best)
        print(f"{sname:<22}{1.0:>7.2f}{m_ens:>9.2f}{m_mid:>11.2f}{m_best:>9.2f}{ratio:>9.0f}%")

    print(f"\n最差段表现(满意度,越高越稳):")
    for k, v in worst.items():
        print(f"  {k:<12}最差段 ×{v:.2f}  {'(从不亏币)' if v >= 1 else '(某段亏币)'}")


if __name__ == "__main__":
    main()
