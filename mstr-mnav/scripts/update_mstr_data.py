#!/usr/bin/env python3
"""每日刷新 MSTR mNAV 静态数据 — GitHub Actions 专用,纯标准库。

抓取逻辑移植自私有仓库 mstr-mnav-monitor/monitor.py(VPS 实时版的同一口径):
  - BTC 价格:   CoinGecko simple/price
  - MSTR 价格:  Yahoo Finance chart API
  - basic 股数: SEC XBRL dei:EntityCommonStockSharesOutstanding(封面页,最新)
  - diluted:    SEC XBRL us-gaap WeightedAverageNumberOfDilutedSharesOutstanding
                取 max(basic, xbrl_diluted),与 monitor.py 一致
  - BTC 持仓:   strategy.com/purchases 正则 → bitcointreasuries.net
                → 本仓库 history 最后一条 → holdings-timeline 最后一条

输出:
  - data/mstr-latest.json   覆盖写,index.html 实时读
  - data/mstr-history.jsonl 追加(每天一条)

阈值口径与 mstr-mnav-monitor/constants.py THRESHOLDS 锁步,
不要单边改动(education.html §3 阈值表也要手动同步)。
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # mstr-mnav/
DATA = HERE / "data"
LATEST = DATA / "mstr-latest.json"
HISTORY = DATA / "mstr-history.jsonl"

SEC_UA = "mnav-monitor htom78@gmail.com"
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# 与 mstr-mnav-monitor/constants.py 锁步
THRESHOLDS = {
    "P3_high_premium": 2.00,
    "P2_observe": 1.50,
    "P1_entry": 1.20,
    "P1_extreme": 1.00,
    "P0_deep_discount": 0.85,
}


def log(msg: str) -> None:
    print(msg, flush=True)


def fetch_json(url: str, ua: str, timeout: int = 20) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_text(url: str, ua: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def get_btc_price() -> float:
    params = urllib.parse.urlencode({"ids": "bitcoin", "vs_currencies": "usd"})
    data = fetch_json(f"https://api.coingecko.com/api/v3/simple/price?{params}", "mnav-monitor/1.0")
    return float(data["bitcoin"]["usd"])


def _mstr_from_yahoo(host: str) -> float:
    # Yahoo 对裸 "Mozilla/5.0" 放行;完整 Chrome UA 或带 Accept: application/json
    # 反而触发 429(2026-06-11 实测),不要"完善"这个 UA。
    req = urllib.request.Request(
        f"https://{host}/v8/finance/chart/MSTR?range=1d&interval=1d",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    meta = data["chart"]["result"][0]["meta"]
    return float(meta["regularMarketPrice"])


def get_mstr_price() -> float:
    for name, fn in (
        ("yahoo query1", lambda: _mstr_from_yahoo("query1.finance.yahoo.com")),
        ("yahoo query2", lambda: _mstr_from_yahoo("query2.finance.yahoo.com")),
    ):
        try:
            px = fn()
            if px > 0:
                log(f"  MSTR price source = {name}: ${px:.2f}")
                return px
        except Exception as e:
            log(f"  MSTR price source {name} failed: {e}")
    raise RuntimeError("MSTR price: all sources failed")


def _sec_concept(path: str) -> list[dict]:
    data = fetch_json(f"https://data.sec.gov/api/xbrl/companyconcept/CIK0001050446/{path}", SEC_UA)
    return data.get("units", {}).get("shares", [])


def get_basic_shares() -> tuple[float, str]:
    """最近一期 10-Q/10-K 的加权平均 basic 股数。
    注意:封面页现值股数(dei)和 CommonStockSharesOutstanding 在 SEC
    companyconcept/companyfacts 里都拿不到(2026-06-11 实测 404/缺失),
    加权平均是免密钥源里最新的。ATM 持续增发会让它略低于真实现值,
    因此 mNAV 略被低估 —— 数据消费端按保守方向理解。"""
    units = _sec_concept("us-gaap/WeightedAverageNumberOfSharesOutstandingBasic.json")
    filings = [u for u in units if u.get("form") in ("10-Q", "10-K")]
    if not filings:
        raise RuntimeError("SEC basic shares: empty units")
    latest = max(filings, key=lambda x: (x.get("end", ""), x.get("filed", "")))
    log(f"  basic shares (weighted avg): {latest['val']:,} (period end {latest['end']})")
    return float(latest["val"]), latest["end"]


def get_diluted_shares() -> float | None:
    try:
        units = _sec_concept("us-gaap/WeightedAverageNumberOfDilutedSharesOutstanding.json")
        filings = [u for u in units if u.get("form") in ("10-Q", "10-K")]
        if not filings:
            return None
        latest = max(filings, key=lambda x: (x.get("end", ""), x.get("filed", "")))
        log(f"  XBRL diluted shares: {latest['val']:,} (period end {latest['end']})")
        return float(latest["val"])
    except Exception as e:
        log(f"  XBRL diluted shares fetch failed: {e}")
        return None


HODL_DATED_RE = re.compile(
    r"As of (\d{1,2}/\d{1,2}/\d{4}),?\s*we\s+hodl\s+([\d,]+)\s*\$?BTC", re.I
)
TABLE_RE = re.compile(r"₿\s*([\d,]{7,})")


def _from_strategy_dot_com() -> float | None:
    html = fetch_text("https://www.strategy.com/purchases", BROWSER_UA)
    parsed = []
    for ds, ns in HODL_DATED_RE.findall(html):
        try:
            parsed.append((datetime.strptime(ds, "%m/%d/%Y"), int(ns.replace(",", ""))))
        except ValueError:
            continue
    if parsed:
        d, n = max(parsed)
        log(f"  strategy.com latest hodl entry: {d.date()} → {n:,} BTC")
        return float(n)
    nums = [int(x.replace(",", "")) for x in TABLE_RE.findall(html)]
    return float(max(nums)) if nums else None


def _from_bitcointreasuries() -> float | None:
    data = fetch_json("https://bitcointreasuries.net/embed/table.json", "mnav-monitor/1.0")
    rows = data.get("data") or data.get("entities") or []
    for row in rows:
        name = (row.get("name") or row.get("entity") or "").lower()
        if "strategy" in name or "microstrategy" in name:
            btc = row.get("btc") or row.get("amount") or row.get("holdings")
            if btc:
                return float(btc)
    return None


def _last_known_holdings() -> float | None:
    """实时源全挂时的兜底:history 最后一条 → holdings-timeline 最后一条。"""
    if HISTORY.exists():
        lines = [l for l in HISTORY.read_text().splitlines() if l.strip()]
        if lines:
            try:
                return float(json.loads(lines[-1])["btc_holdings"])
            except (json.JSONDecodeError, KeyError, ValueError):
                pass
    timeline_file = DATA / "mstr-holdings-timeline.json"
    if timeline_file.exists():
        timeline = json.loads(timeline_file.read_text()).get("timeline", {})
        dates = sorted(k for k in timeline if not k.startswith("_"))
        if dates:
            v = timeline[dates[-1]]
            btc = v.get("btc") if isinstance(v, dict) else v
            if btc:
                return float(btc)
    return None


def get_btc_holdings() -> tuple[float, str]:
    for name, fn in (("strategy.com", _from_strategy_dot_com),
                     ("bitcointreasuries", _from_bitcointreasuries)):
        try:
            v = fn()
            if v and v > 100_000:  # sanity floor
                log(f"  holdings source = {name}: {v:,.0f} BTC")
                return v, name
            log(f"  holdings source {name} returned {v}, trying next")
        except Exception as e:
            log(f"  holdings source {name} failed: {e}")
    last = _last_known_holdings()
    if last and last > 100_000:
        log(f"  holdings live sources failed; reusing last known: {last:,.0f} BTC")
        return last, "last_known"
    raise RuntimeError("holdings: all sources failed and no local fallback")


def classify(mnav: float) -> str | None:
    if mnav >= THRESHOLDS["P3_high_premium"]:
        return "P3_high_premium"
    if mnav < THRESHOLDS["P0_deep_discount"]:
        return "P0_deep_discount"
    if mnav < THRESHOLDS["P1_extreme"]:
        return "P1_extreme"
    if mnav < THRESHOLDS["P1_entry"]:
        return "P1_entry"
    if mnav < THRESHOLDS["P2_observe"]:
        return "P2_observe"
    return None


def main() -> int:
    latest_only = "--latest-only" in sys.argv[1:]
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log(f"update_mstr_data @ {now_iso}{' (latest-only)' if latest_only else ''}")

    btc_px = get_btc_price()
    mstr_px = get_mstr_price()
    basic_shares, shares_asof = get_basic_shares()
    xbrl_diluted = get_diluted_shares()
    holdings, holdings_source = get_btc_holdings()

    # 与 monitor.py 一致:diluted = max(basic 现值, 最近申报加权平均 diluted)
    diluted_shares = max(basic_shares, xbrl_diluted or 0)

    btc_nav = holdings * btc_px
    mcap_basic = mstr_px * basic_shares
    mcap_diluted = mstr_px * diluted_shares
    mnav_basic = mcap_basic / btc_nav
    mnav_diluted = mcap_diluted / btc_nav
    nav_per_share = btc_nav / basic_shares

    snapshot = {
        "ts": now_iso,
        "btc_price_usd": round(btc_px, 2),
        "mstr_price_usd": round(mstr_px, 2),
        "basic_shares": int(basic_shares),
        "shares_asof": shares_asof,
        "diluted_shares": int(diluted_shares),
        "btc_holdings": int(holdings),
        "holdings_source": holdings_source,
        "btc_nav_usd": round(btc_nav),
        "mcap_basic_usd": round(mcap_basic),
        "mcap_diluted_usd": round(mcap_diluted),
        "mnav_basic": round(mnav_basic, 4),
        "mnav_diluted": round(mnav_diluted, 4),
        "nav_per_share_usd": round(nav_per_share, 2),
        "premium_pct_diluted": round((mnav_diluted - 1) * 100, 2),
        "level": classify(mnav_diluted),
        "thresholds": THRESHOLDS,
        "_doc": "GitHub Actions 每日快照,口径与 VPS 实时版 monitor.py 锁步。"
                "level 按 mNAV diluted 分级。股数为最近申报期加权平均,"
                "ATM 增发会使 mNAV 略被低估(保守方向)。",
    }

    log(
        f"BTC=${btc_px:,.0f} MSTR=${mstr_px:.2f} holdings={holdings:,.0f} "
        f"mNAV_basic={mnav_basic:.3f} mNAV_diluted={mnav_diluted:.3f} level={snapshot['level']}"
    )

    DATA.mkdir(exist_ok=True)
    LATEST.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")

    if latest_only:
        # 盘中 30 分钟级刷新只更新 latest,历史序列保持每日一条
        log(f"wrote {LATEST.relative_to(HERE)} (history skipped)")
        return 0

    history_line = json.dumps(
        {k: v for k, v in snapshot.items() if k not in ("thresholds", "_doc")},
        ensure_ascii=False,
    )
    with HISTORY.open("a") as f:
        f.write(history_line + "\n")

    log(f"wrote {LATEST.relative_to(HERE)} + appended {HISTORY.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
