"""自优化回测 harness:跨多策略族用 Optuna 搜索,walk-forward 防过拟合,选 champion。

这是 pwb-alphaevolve 范式里"不依赖 LLM"的核心闭环:
  搜索(Optuna) → walk-forward 评估 → 多目标 → champion 验收

数据三段锁死(防过拟合红线):
  train   2015-2019  : Optuna 在此优化每族参数(in-sample)
  select  2020-2022  : 用 best params 在此 OOS 选 champion(LLM/搜索不可见的泛化检验)
  holdout 2023-2026+ : 全程锁死,只在最后给 champion 验收一次

所有策略统一"仅做多"(评估已证明做空腿是拖累),公平对比。
"""
from __future__ import annotations

import warnings
import numpy as np
import pandas as pd
import optuna

from backtest_vector import load, _metrics

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

COMM = 0.001
TRAIN = ("2015-01-01", "2019-12-31")
SELECT = ("2020-01-01", "2022-12-31")
HOLDOUT = ("2023-01-01", None)


# ---------- 策略族:每个返回 0/1 仓位序列 ----------
def s_ma_envelope(close, n, band):
    ma = close.rolling(n).mean()
    pos = pd.Series(np.nan, index=close.index)
    pos[close > ma * (1 + band)] = 1.0
    pos[close < ma * (1 - band)] = 0.0
    return _finalize(pos, ma)

def s_dual_ma(close, fast, slow):
    mf, ms = close.rolling(fast).mean(), close.rolling(slow).mean()
    pos = (mf > ms).astype(float)
    pos[ms.isna()] = 0.0
    return pos

def s_donchian(close, n):
    hi = close.rolling(n).max().shift(1)
    lo = close.rolling(n).min().shift(1)
    pos = pd.Series(np.nan, index=close.index)
    pos[close > hi] = 1.0
    pos[close < lo] = 0.0
    return _finalize(pos, hi)

def s_bollinger(close, n, k):
    ma = close.rolling(n).mean()
    sd = close.rolling(n).std()
    pos = pd.Series(np.nan, index=close.index)
    pos[close > ma + k * sd] = 1.0
    pos[close < ma - k * sd] = 0.0
    return _finalize(pos, ma)

def s_momentum(close, n):
    pos = (close > close.shift(n)).astype(float)
    pos.iloc[:n] = 0.0
    return pos

def _finalize(pos, warm):
    pos = pos.ffill().fillna(0.0)
    pos[warm.isna()] = 0.0
    return pos


FAMILIES = {
    "ma_envelope": (s_ma_envelope, lambda t: dict(
        n=t.suggest_int("n", 20, 200), band=t.suggest_float("band", 0.01, 0.10))),
    "dual_ma": (s_dual_ma, lambda t: dict(
        fast=t.suggest_int("fast", 5, 60), slow=t.suggest_int("slow", 70, 250))),
    "donchian": (s_donchian, lambda t: dict(n=t.suggest_int("n", 10, 120))),
    "bollinger": (s_bollinger, lambda t: dict(
        n=t.suggest_int("n", 10, 100), k=t.suggest_float("k", 1.0, 3.0))),
    "momentum": (s_momentum, lambda t: dict(n=t.suggest_int("n", 10, 150))),
}


def evaluate(df, sig_fn, params):
    close = df["close"]
    ret = close.pct_change().fillna(0.0)
    pos = sig_fn(close, **params)
    net = pos.shift(1).fillna(0.0) * ret - pos.diff().abs().fillna(0.0) * COMM
    equity = (1 + net).cumprod()
    bh = (1 + ret).cumprod()
    return _metrics(equity, bh, net, pos, df.index)


def objective(trial, df_train, sig_fn, param_fn):
    params = param_fn(trial)
    if "slow" in params and params["slow"] <= params.get("fast", 0):
        return -10.0  # 非法组合
    m = evaluate(df_train, sig_fn, params)
    if m["持仓占比%"] < 10:        # 防退化:持仓过少的虚高解
        return -10.0
    return m["Sharpe"]            # 优化目标 = train 段 Sharpe


def main():
    df = load()
    tr = df.loc[TRAIN[0]:TRAIN[1]]
    se = df.loc[SELECT[0]:SELECT[1]]
    ho = df.loc[HOLDOUT[0]:]
    print(f"数据三段: train {tr.index.min().date()}→{tr.index.max().date()} ({len(tr)}) | "
          f"select {se.index.min().date()}→{se.index.max().date()} ({len(se)}) | "
          f"holdout {ho.index.min().date()}→{ho.index.max().date()} ({len(ho)})\n")

    results = []
    for name, (sig_fn, param_fn) in FAMILIES.items():
        study = optuna.create_study(direction="maximize",
                                    sampler=optuna.samplers.TPESampler(seed=42))
        study.optimize(lambda t: objective(t, tr, sig_fn, param_fn),
                       n_trials=120, show_progress_bar=False)
        bp = study.best_params
        m_tr = evaluate(tr, sig_fn, bp)
        m_se = evaluate(se, sig_fn, bp)   # OOS 选择段
        results.append({
            "策略族": name, "最优参数": bp,
            "train_Sharpe": m_tr["Sharpe"], "train_Calmar": m_tr["Calmar"],
            "select_Sharpe": m_se["Sharpe"], "select_Calmar": m_se["Calmar"],
            "select_CAGR%": m_se["CAGR%"], "select_MaxDD%": m_se["MaxDD%"],
        })

    res = pd.DataFrame(results)
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)
    print("=== 各策略族:train 优化 → select(OOS) 泛化 ===")
    print(res.drop(columns="最优参数").round(2).to_string(index=False))
    print("\n最优参数:")
    for r in results:
        print(f"  {r['策略族']:12s} {r['最优参数']}")

    # champion = select(OOS) 段 Sharpe 最高(泛化能力,非 in-sample)
    champ = max(results, key=lambda r: r["select_Sharpe"])
    print(f"\n>>> CHAMPION(按 select OOS Sharpe): {champ['策略族']} {champ['最优参数']}")

    # holdout 验收(只看这一次)
    sig_fn = FAMILIES[champ["策略族"]][0]
    m_ho = evaluate(ho, sig_fn, champ["最优参数"])
    print(f"\n=== HOLDOUT 验收({HOLDOUT[0]}+,全程锁死) ===")
    for k in ["CAGR%", "BH_CAGR%", "Sharpe", "Sortino", "MaxDD%", "BH_MaxDD%", "Calmar", "胜率%", "换仓次数"]:
        print(f"  {k:12s} {m_ho[k]}")

    # 对照:你最初的 MA95±4% 在 holdout 的表现
    m_base = evaluate(ho, s_ma_envelope, dict(n=95, band=0.04))
    print(f"\n=== 对照:原始 MA95±4% 在同一 holdout ===")
    for k in ["CAGR%", "Sharpe", "MaxDD%", "Calmar", "胜率%"]:
        print(f"  {k:12s} {m_base[k]}")


if __name__ == "__main__":
    main()
