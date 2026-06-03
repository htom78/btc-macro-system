#!/usr/bin/env python3
from __future__ import annotations

import argparse
import bisect
import csv
import html
import io
import json
import math
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
HISTORY_DIR = ROOT / "data" / "history"
DEFAULT_HISTORY_PATH = HISTORY_DIR / "observations.jsonl"
OUT_DIR = ROOT / "outputs"


@dataclass(frozen=True)
class Point:
    date: date
    value: float


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def http_get(url: str, retries: int = 3) -> bytes:
    curl = shutil.which("curl")
    if curl:
        last_stderr = ""
        for attempt in range(retries):
            result = subprocess.run(
                [
                    curl,
                    "-L",
                    "--connect-timeout",
                    "10",
                    "--max-time",
                    "45",
                    "--silent",
                    "--show-error",
                    url,
                ],
                check=False,
                capture_output=True,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
            last_stderr = result.stderr.decode("utf-8", errors="replace").strip()
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"failed to fetch {url}: {last_stderr or 'curl returned no data'}")

    headers = {
        "User-Agent": "btc-macro-system/0.1 (+local research tool)",
        "Accept": "text/csv,application/json,text/plain,*/*",
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=40) as resp:
                return resp.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_fred_csv(series_id: str, text: str) -> list[Point]:
    points: list[Point] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        raw_value = row.get(series_id, "")
        if raw_value in ("", "."):
            continue
        try:
            points.append(Point(parse_date(row["observation_date"]), float(raw_value)))
        except (KeyError, ValueError):
            continue
    return points


def read_fred_cache(series_id: str) -> list[Point]:
    cache_path = RAW_DIR / f"{series_id}.csv"
    return parse_fred_csv(series_id, cache_path.read_text(encoding="utf-8-sig"))


def write_fred_cache(series_id: str, points: list[Point]) -> None:
    cache_path = RAW_DIR / f"{series_id}.csv"
    with cache_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["observation_date", series_id])
        for point in points:
            writer.writerow([point.date.isoformat(), f"{point.value:.12g}"])


def merge_points(*series: list[Point]) -> list[Point]:
    by_day: dict[date, float] = {}
    for points in series:
        for point in points:
            by_day[point.date] = point.value
    return [Point(day, by_day[day]) for day in sorted(by_day)]


def with_fred_start(url: str, start: date) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}cosd={start.isoformat()}"


def fetch_fred_series(series_id: str, url_template: str, force: bool = False) -> list[Point]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_DIR / f"{series_id}.csv"
    if force or not cache_path.exists():
        cached = read_fred_cache(series_id) if cache_path.exists() else []
        url = url_template.format(series_id=series_id)
        if cached:
            refresh_start = cached[-1].date - timedelta(days=45)
            url = with_fred_start(url, refresh_start)
        data = http_get(url)
        fetched = parse_fred_csv(series_id, data.decode("utf-8-sig"))
        if cached:
            points = merge_points(cached, fetched)
            write_fred_cache(series_id, points)
            return points
        cache_path.write_bytes(data)

    return read_fred_cache(series_id)


def parse_coingecko_prices(payload: dict[str, Any]) -> list[Point]:
    if "prices" not in payload:
        error = payload.get("error", "response did not include prices")
        raise RuntimeError(f"CoinGecko response error: {error}")

    by_day: dict[date, float] = {}
    for millis, price in payload["prices"]:
        day = datetime.fromtimestamp(millis / 1000, tz=timezone.utc).date()
        by_day[day] = float(price)
    return [Point(day, by_day[day]) for day in sorted(by_day)]


def parse_blockchain_info_prices(payload: dict[str, Any]) -> list[Point]:
    if payload.get("status") != "ok" or "values" not in payload:
        raise RuntimeError("Blockchain.com chart response did not include values")

    by_day: dict[date, float] = {}
    for item in payload["values"]:
        day = datetime.fromtimestamp(int(item["x"]), tz=timezone.utc).date()
        by_day[day] = float(item["y"])
    return [Point(day, by_day[day]) for day in sorted(by_day)]


def fetch_btc_prices(config: dict[str, Any], force: bool = False) -> list[Point]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    source = config.get("source", "blockchain_info")
    cache_path = RAW_DIR / f"btc_usd_{source}.json"
    if force or not cache_path.exists():
        cache_path.write_bytes(http_get(config["url"]))

    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    if source == "blockchain_info":
        return parse_blockchain_info_prices(payload)
    if source == "coingecko":
        return parse_coingecko_prices(payload)
    raise RuntimeError(f"unsupported BTC source: {source}")


def fetch_btc_prices_with_fallback(config: dict[str, Any], force: bool = False) -> list[Point]:
    try:
        return fetch_btc_prices(config, force=force)
    except Exception:
        fallback_url = config.get("fallback_url")
        if not fallback_url:
            raise
        fallback_config = {"source": "coingecko", "url": fallback_url}
        return fetch_btc_prices(fallback_config, force=force)


def filter_since(points: list[Point], start: date) -> list[Point]:
    return [p for p in points if p.date >= start]


def latest(points: list[Point]) -> Point | None:
    return points[-1] if points else None


def point_on_or_before(points: list[Point], target: date) -> Point | None:
    if not points:
        return None
    dates = [p.date for p in points]
    idx = bisect.bisect_right(dates, target) - 1
    if idx < 0:
        return None
    return points[idx]


def point_periods_back(points: list[Point], periods: int) -> Point | None:
    if len(points) <= periods:
        return None
    return points[-1 - periods]


def pct_change(current: Point | None, previous: Point | None) -> float | None:
    if not current or not previous or previous.value == 0:
        return None
    return current.value / previous.value - 1


def delta(current: Point | None, previous: Point | None) -> float | None:
    if not current or not previous:
        return None
    return current.value - previous.value


def annualized_change(current: Point | None, previous: Point | None, periods_per_year: float) -> float | None:
    raw = pct_change(current, previous)
    if raw is None:
        return None
    return (1 + raw) ** periods_per_year - 1


def moving_average(points: list[Point], window: int) -> float | None:
    if len(points) < window:
        return None
    return statistics.fmean(p.value for p in points[-window:])


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 8 or len(xs) != len(ys):
        return None
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def series_change(kind: str, a: Point, b: Point) -> float | None:
    if kind == "rate":
        return b.value - a.value
    if a.value <= 0 or b.value <= 0:
        return None
    return math.log(b.value / a.value)


def lagged_correlations(
    macro: list[Point],
    btc: list[Point],
    kind: str,
    lags: list[int],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for lag in lags:
        xs: list[float] = []
        ys: list[float] = []
        for prev, cur in zip(macro, macro[1:]):
            macro_move = series_change(kind, prev, cur)
            btc_prev = point_on_or_before(btc, prev.date + timedelta(days=lag))
            btc_cur = point_on_or_before(btc, cur.date + timedelta(days=lag))
            if macro_move is None or not btc_prev or not btc_cur:
                continue
            if btc_prev.value <= 0 or btc_cur.value <= 0:
                continue
            xs.append(macro_move)
            ys.append(math.log(btc_cur.value / btc_prev.value))
        corr = pearson(xs, ys)
        result[str(lag)] = {
            "correlation": corr,
            "pairs": len(xs),
        }
    return result


def fmt_pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def fmt_num(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value:,.{digits}f}"


def fmt_corr(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}"


SIGNAL_TITLES = {
    "USD liquidity": ("美元流动性", "USD liquidity"),
    "Inflation constraint": ("通胀约束", "Inflation constraint"),
    "Real-rate pressure": ("实际利率压力", "Real-rate pressure"),
    "Dollar pressure": ("美元压力", "Dollar pressure"),
    "Risk appetite": ("风险偏好", "Risk appetite"),
    "BTC trend": ("BTC 趋势", "BTC trend"),
    "Fiscal pressure": ("财政压力", "Fiscal pressure"),
}


STANCE_LABELS = {
    "supportive": ("支撑", "supportive"),
    "mildly supportive": ("温和支撑", "mildly supportive"),
    "mixed": ("混合", "mixed"),
    "hostile": ("压制", "hostile"),
}


SERIES_ZH = {
    "CPIAUCSL": "CPI",
    "FEDFUNDS": "联邦基金利率",
    "DGS10": "10年期美债收益率",
    "DFII10": "10年期实际收益率",
    "T10YIE": "10年期通胀预期",
    "T10Y2Y": "10年-2年收益率曲线",
    "M2SL": "M2 货币供应",
    "WALCL": "美联储资产负债表",
    "DTWEXBGS": "广义美元指数",
    "VIXCLS": "VIX",
    "BAMLH0A0HYM2": "高收益债利差",
    "GFDEGDQ188S": "联邦总债务/GDP",
    "FYGFGDQ188S": "公众持有联邦债务/GDP",
    "FYOIGDA188S": "联邦利息支出/GDP",
}


def bilingual(primary: str, secondary: str, class_name: str = "bi") -> str:
    return (
        f'<span class="{class_name}">'
        f'<span>{html.escape(primary)}</span>'
        f'<small>{html.escape(secondary)}</small>'
        "</span>"
    )


def stance_text(value: str) -> str:
    zh, en = STANCE_LABELS.get(value, (value, value))
    return f"{zh} / {en}"


def classify_signal(name: str, score: int, detail: str) -> dict[str, Any]:
    if score > 0:
        stance = "supportive"
    elif score < 0:
        stance = "hostile"
    else:
        stance = "mixed"
    return {"name": name, "score": score, "stance": stance, "detail": detail}


def build_indicators(series: dict[str, list[Point]], btc: list[Point]) -> dict[str, Any]:
    btc_last = latest(btc)
    btc_30 = point_on_or_before(btc, btc_last.date - timedelta(days=30)) if btc_last else None
    btc_90 = point_on_or_before(btc, btc_last.date - timedelta(days=90)) if btc_last else None
    btc_365 = point_on_or_before(btc, btc_last.date - timedelta(days=365)) if btc_last else None
    btc_ma200 = moving_average(btc, 200)

    cpi = series.get("CPIAUCSL", [])
    cpi_last = latest(cpi)
    cpi_yoy = pct_change(cpi_last, point_periods_back(cpi, 12))
    cpi_3m_ann = annualized_change(cpi_last, point_periods_back(cpi, 3), 4)

    m2 = series.get("M2SL", [])
    m2_last = latest(m2)
    m2_yoy = pct_change(m2_last, point_periods_back(m2, 12))
    m2_3m_ann = annualized_change(m2_last, point_periods_back(m2, 3), 4)

    walcl = series.get("WALCL", [])
    walcl_last = latest(walcl)
    walcl_13w = pct_change(walcl_last, point_on_or_before(walcl, walcl_last.date - timedelta(days=91)) if walcl_last else None)

    dollar = series.get("DTWEXBGS", [])
    dollar_last = latest(dollar)
    dollar_13w = pct_change(dollar_last, point_on_or_before(dollar, dollar_last.date - timedelta(days=91)) if dollar_last else None)

    real_yield = series.get("DFII10", [])
    real_yield_last = latest(real_yield)
    real_yield_13w = delta(real_yield_last, point_on_or_before(real_yield, real_yield_last.date - timedelta(days=91)) if real_yield_last else None)

    ten_year = latest(series.get("DGS10", []))
    fedfunds = latest(series.get("FEDFUNDS", []))
    breakeven = latest(series.get("T10YIE", []))
    curve = latest(series.get("T10Y2Y", []))
    vix = latest(series.get("VIXCLS", []))

    hy_oas = series.get("BAMLH0A0HYM2", [])
    hy_last = latest(hy_oas)
    hy_13w = delta(hy_last, point_on_or_before(hy_oas, hy_last.date - timedelta(days=91)) if hy_last else None)

    gross_debt = latest(series.get("GFDEGDQ188S", []))
    public_debt = latest(series.get("FYGFGDQ188S", []))
    interest_gdp = latest(series.get("FYOIGDA188S", []))

    return {
        "btc": {
            "date": str(btc_last.date) if btc_last else None,
            "price": btc_last.value if btc_last else None,
            "change_30d": pct_change(btc_last, btc_30),
            "change_90d": pct_change(btc_last, btc_90),
            "change_365d": pct_change(btc_last, btc_365),
            "ma200": btc_ma200,
            "above_ma200": (btc_last.value > btc_ma200) if btc_last and btc_ma200 else None,
        },
        "inflation": {
            "cpi_date": str(cpi_last.date) if cpi_last else None,
            "cpi_yoy": cpi_yoy,
            "cpi_3m_annualized": cpi_3m_ann,
            "breakeven_10y": breakeven.value if breakeven else None,
            "breakeven_10y_date": str(breakeven.date) if breakeven else None,
        },
        "policy_rates": {
            "fedfunds": fedfunds.value if fedfunds else None,
            "fedfunds_date": str(fedfunds.date) if fedfunds else None,
            "ten_year": ten_year.value if ten_year else None,
            "ten_year_date": str(ten_year.date) if ten_year else None,
            "real_yield_10y": real_yield_last.value if real_yield_last else None,
            "real_yield_10y_date": str(real_yield_last.date) if real_yield_last else None,
            "real_yield_13w_delta": real_yield_13w,
            "yield_curve_10y2y": curve.value if curve else None,
            "yield_curve_10y2y_date": str(curve.date) if curve else None,
        },
        "liquidity": {
            "m2_date": str(m2_last.date) if m2_last else None,
            "m2_yoy": m2_yoy,
            "m2_3m_annualized": m2_3m_ann,
            "fed_balance_sheet_date": str(walcl_last.date) if walcl_last else None,
            "fed_balance_sheet_13w_change": walcl_13w,
        },
        "dollar_risk": {
            "dollar_index_date": str(dollar_last.date) if dollar_last else None,
            "dollar_index_13w_change": dollar_13w,
            "vix": vix.value if vix else None,
            "vix_date": str(vix.date) if vix else None,
            "high_yield_oas": hy_last.value if hy_last else None,
            "high_yield_oas_date": str(hy_last.date) if hy_last else None,
            "high_yield_oas_13w_delta": hy_13w,
        },
        "debt": {
            "gross_debt_gdp": gross_debt.value if gross_debt else None,
            "gross_debt_gdp_date": str(gross_debt.date) if gross_debt else None,
            "public_debt_gdp": public_debt.value if public_debt else None,
            "public_debt_gdp_date": str(public_debt.date) if public_debt else None,
            "interest_outlays_gdp": interest_gdp.value if interest_gdp else None,
            "interest_outlays_gdp_date": str(interest_gdp.date) if interest_gdp else None,
        },
    }


def build_signals(indicators: dict[str, Any]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []

    m2_3m = indicators["liquidity"]["m2_3m_annualized"]
    walcl_13w = indicators["liquidity"]["fed_balance_sheet_13w_change"]
    liquidity_score = 0
    liquidity_bits: list[str] = []
    if m2_3m is not None:
        liquidity_score += 1 if m2_3m > 0.02 else -1 if m2_3m < -0.02 else 0
        liquidity_bits.append(f"M2 3个月年化 {fmt_pct(m2_3m)} / M2 3m annualized {fmt_pct(m2_3m)}")
    if walcl_13w is not None:
        liquidity_score += 1 if walcl_13w > 0.01 else -1 if walcl_13w < -0.01 else 0
        liquidity_bits.append(f"联储资产负债表13周 {fmt_pct(walcl_13w)} / Fed balance sheet 13w {fmt_pct(walcl_13w)}")
    signals.append(classify_signal("USD liquidity", liquidity_score, "; ".join(liquidity_bits) or "n/a"))

    cpi_yoy = indicators["inflation"]["cpi_yoy"]
    cpi_3m = indicators["inflation"]["cpi_3m_annualized"]
    inflation_score = 0
    if cpi_yoy is not None and cpi_3m is not None:
        if cpi_yoy > 0.03 and cpi_3m > cpi_yoy:
            inflation_score = -2
        elif cpi_yoy < 0.025 and cpi_3m < 0.025:
            inflation_score = 1
        elif cpi_yoy > 0.03:
            inflation_score = -1
    signals.append(
        classify_signal(
            "Inflation constraint",
            inflation_score,
            f"CPI同比 {fmt_pct(cpi_yoy)} / CPI YoY {fmt_pct(cpi_yoy)}; 3个月年化 {fmt_pct(cpi_3m)} / 3m annualized {fmt_pct(cpi_3m)}",
        )
    )

    real_yield_delta = indicators["policy_rates"]["real_yield_13w_delta"]
    real_yield_level = indicators["policy_rates"]["real_yield_10y"]
    rate_score = 0
    if real_yield_delta is not None:
        rate_score += 1 if real_yield_delta < -0.15 else -1 if real_yield_delta > 0.15 else 0
    if real_yield_level is not None:
        rate_score += -1 if real_yield_level > 2.0 else 1 if real_yield_level < 0.5 else 0
    signals.append(
        classify_signal(
            "Real-rate pressure",
            rate_score,
            f"10年期实际收益率 {fmt_num(real_yield_level)}% / 10Y real yield {fmt_num(real_yield_level)}%; 13周变化 {fmt_num(real_yield_delta)}百分点 / 13w delta {fmt_num(real_yield_delta)} pp",
        )
    )

    dollar_13w = indicators["dollar_risk"]["dollar_index_13w_change"]
    dollar_score = 0
    if dollar_13w is not None:
        dollar_score = 1 if dollar_13w < -0.01 else -1 if dollar_13w > 0.01 else 0
    signals.append(classify_signal("Dollar pressure", dollar_score, f"广义美元13周 {fmt_pct(dollar_13w)} / Broad dollar 13w {fmt_pct(dollar_13w)}"))

    vix = indicators["dollar_risk"]["vix"]
    hy_delta = indicators["dollar_risk"]["high_yield_oas_13w_delta"]
    risk_score = 0
    if vix is not None:
        risk_score += 1 if vix < 18 else -1 if vix > 25 else 0
    if hy_delta is not None:
        risk_score += 1 if hy_delta < -0.25 else -1 if hy_delta > 0.25 else 0
    signals.append(
        classify_signal(
            "Risk appetite",
            risk_score,
            f"VIX {fmt_num(vix)}; 高收益债利差13周变化 {fmt_num(hy_delta)}百分点 / HY OAS 13w delta {fmt_num(hy_delta)} pp",
        )
    )

    btc = indicators["btc"]
    btc_score = 0
    if btc["above_ma200"] is True:
        btc_score = 1
    elif btc["above_ma200"] is False:
        btc_score = -1
    signals.append(
        classify_signal(
            "BTC trend",
            btc_score,
            f"价格 ${fmt_num(btc['price'], 0)} / Price ${fmt_num(btc['price'], 0)}; 200日均线 ${fmt_num(btc['ma200'], 0)} / 200d MA ${fmt_num(btc['ma200'], 0)}",
        )
    )

    public_debt = indicators["debt"]["public_debt_gdp"]
    interest_gdp = indicators["debt"]["interest_outlays_gdp"]
    debt_score = 0
    detail = f"公众持有债务/GDP {fmt_num(public_debt)}% / Public debt/GDP {fmt_num(public_debt)}%; 利息支出/GDP {fmt_num(interest_gdp)}% / interest outlays/GDP {fmt_num(interest_gdp)}%"
    signals.append(classify_signal("Fiscal pressure", debt_score, detail + "; 长期支撑硬通货叙事，但短期会放大利率压力 / structural BTC narrative support, but rate pressure risk"))

    return signals


def regime(signals: list[dict[str, Any]]) -> dict[str, Any]:
    score = sum(int(s["score"]) for s in signals)
    if score >= 3:
        label = "supportive"
    elif score >= 1:
        label = "mildly supportive"
    elif score >= -1:
        label = "mixed"
    else:
        label = "hostile"
    return {"score": score, "label": label}


def svg_line_chart(points: list[Point], width: int, height: int, log_scale: bool = False) -> str:
    if len(points) < 2:
        return ""
    values = [math.log(p.value) if log_scale and p.value > 0 else p.value for p in points]
    min_v, max_v = min(values), max(values)
    if min_v == max_v:
        max_v = min_v + 1
    coords = []
    for idx, value in enumerate(values):
        x = 10 + idx * (width - 20) / (len(points) - 1)
        y = height - 10 - (value - min_v) * (height - 20) / (max_v - min_v)
        coords.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="line chart">'
        f'<path d="M10 {height - 10}H{width - 10}" stroke="#d9dee7" stroke-width="1" />'
        f'<polyline fill="none" stroke="currentColor" stroke-width="2" points="{" ".join(coords)}" />'
        "</svg>"
    )


def normalized_overlay_svg(a: list[Point], b: list[Point], width: int, height: int) -> str:
    if len(a) < 2 or len(b) < 2:
        return ""
    start = max(a[0].date, b[0].date)
    end = min(a[-1].date, b[-1].date)
    if start >= end:
        return ""
    sample_dates = [start + timedelta(days=round(i * (end - start).days / 180)) for i in range(181)]
    a_vals: list[float] = []
    b_vals: list[float] = []
    for day in sample_dates:
        av = point_on_or_before(a, day)
        bv = point_on_or_before(b, day)
        if av and bv and av.value > 0 and bv.value > 0:
            a_vals.append(math.log(av.value / a[0].value))
            b_vals.append(math.log(bv.value / b[0].value))
        else:
            a_vals.append(float("nan"))
            b_vals.append(float("nan"))
    all_vals = [v for v in a_vals + b_vals if not math.isnan(v)]
    if not all_vals:
        return ""
    min_v, max_v = min(all_vals), max(all_vals)
    if min_v == max_v:
        max_v = min_v + 1

    def path(vals: list[float]) -> str:
        coords = []
        for idx, value in enumerate(vals):
            if math.isnan(value):
                continue
            x = 10 + idx * (width - 20) / (len(vals) - 1)
            y = height - 10 - (value - min_v) * (height - 20) / (max_v - min_v)
            coords.append(f"{x:.1f},{y:.1f}")
        return " ".join(coords)

    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="normalized overlay chart">'
        f'<polyline fill="none" stroke="#f7931a" stroke-width="2" points="{path(a_vals)}" />'
        f'<polyline fill="none" stroke="#475569" stroke-width="2" points="{path(b_vals)}" />'
        "</svg>"
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                entries.append(item)
    return entries


def write_jsonl(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def build_history_entry(latest_json: dict[str, Any]) -> dict[str, Any]:
    indicators = latest_json["indicators"]
    return {
        "schema_version": 1,
        "generated_at": latest_json["generated_at"],
        "market_date": indicators["btc"]["date"],
        "regime": latest_json["regime"],
        "btc": {
            "price": indicators["btc"]["price"],
            "change_30d": indicators["btc"]["change_30d"],
            "change_90d": indicators["btc"]["change_90d"],
            "change_365d": indicators["btc"]["change_365d"],
            "ma200": indicators["btc"]["ma200"],
            "above_ma200": indicators["btc"]["above_ma200"],
        },
        "macro": {
            "cpi_yoy": indicators["inflation"]["cpi_yoy"],
            "cpi_3m_annualized": indicators["inflation"]["cpi_3m_annualized"],
            "fedfunds": indicators["policy_rates"]["fedfunds"],
            "real_yield_10y": indicators["policy_rates"]["real_yield_10y"],
            "m2_yoy": indicators["liquidity"]["m2_yoy"],
            "m2_3m_annualized": indicators["liquidity"]["m2_3m_annualized"],
            "dollar_index_13w_change": indicators["dollar_risk"]["dollar_index_13w_change"],
            "vix": indicators["dollar_risk"]["vix"],
            "high_yield_oas": indicators["dollar_risk"]["high_yield_oas"],
        },
        "debt": {
            "gross_debt_gdp": indicators["debt"]["gross_debt_gdp"],
            "public_debt_gdp": indicators["debt"]["public_debt_gdp"],
            "interest_outlays_gdp": indicators["debt"]["interest_outlays_gdp"],
        },
        "signals": [
            {
                "name": signal["name"],
                "score": signal["score"],
                "stance": signal["stance"],
            }
            for signal in latest_json["signals"]
        ],
        "fetch_errors": latest_json["fetch_errors"],
    }


def upsert_history(path: Path, entry: dict[str, Any]) -> list[dict[str, Any]]:
    market_date = entry.get("market_date")
    entries = [item for item in read_jsonl(path) if item.get("market_date") != market_date]
    entries.append(entry)
    entries.sort(key=lambda item: str(item.get("market_date", "")))
    write_jsonl(path, entries)
    return entries


def summarize_history(entries: list[dict[str, Any]], path: Path | None) -> dict[str, Any]:
    if not entries:
        return {
            "path": display_path(path),
            "count": 0,
            "first_market_date": None,
            "last_market_date": None,
            "last_generated_at": None,
            "latest_regime": None,
            "latest_score": None,
            "recent_entries": [],
        }

    latest_entry = entries[-1]
    return {
        "path": display_path(path),
        "count": len(entries),
        "first_market_date": entries[0].get("market_date"),
        "last_market_date": latest_entry.get("market_date"),
        "last_generated_at": latest_entry.get("generated_at"),
        "latest_regime": latest_entry.get("regime", {}).get("label"),
        "latest_score": latest_entry.get("regime", {}).get("score"),
        "recent_entries": entries[-18:],
    }


def history_regime_svg(entries: list[dict[str, Any]], width: int, height: int) -> str:
    usable = [entry for entry in entries if isinstance(entry.get("regime", {}).get("score"), (int, float))]
    if len(usable) < 2:
        return '<div class="empty-history">等待更多观测点 / waiting for more observations</div>'

    recent = usable[-90:]
    scores = [float(entry["regime"]["score"]) for entry in recent]
    min_v = min(min(scores), -6)
    max_v = max(max(scores), 6)
    if min_v == max_v:
        max_v = min_v + 1

    coords = []
    for index, value in enumerate(scores):
        x = 10 + index * (width - 20) / (len(scores) - 1)
        y = height - 10 - (value - min_v) * (height - 20) / (max_v - min_v)
        coords.append(f"{x:.1f},{y:.1f}")

    zero_y = height - 10 - (0 - min_v) * (height - 20) / (max_v - min_v)
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="regime history chart">'
        f'<path d="M10 {zero_y:.1f}H{width - 10}" stroke="#ded8ce" stroke-width="1" stroke-dasharray="4 5" />'
        f'<polyline fill="none" stroke="#f7931a" stroke-width="2" points="{" ".join(coords)}" />'
        "</svg>"
    )


def make_history_trail(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return '<span class="history-pill">暂无历史 / no history yet</span>'

    items = []
    for entry in entries[-10:]:
        regime_value = entry.get("regime", {}).get("label", "mixed")
        score = entry.get("regime", {}).get("score")
        date_value = entry.get("market_date", "n/a")
        items.append(
            f'<span class="history-pill {html.escape(str(regime_value))}">'
            f'{html.escape(str(date_value))} <b>{html.escape(str(score))}</b>'
            "</span>"
        )
    return "\n".join(items)


def make_indicator_rows(indicators: dict[str, Any]) -> str:
    rows = [
        ("BTC 价格", "BTC price", "$" + fmt_num(indicators["btc"]["price"], 0), indicators["btc"]["date"]),
        ("BTC 30日 / 90日 / 1年", "BTC 30d / 90d / 1y", f"{fmt_pct(indicators['btc']['change_30d'])} / {fmt_pct(indicators['btc']['change_90d'])} / {fmt_pct(indicators['btc']['change_365d'])}", indicators["btc"]["date"]),
        ("CPI 同比", "CPI YoY", fmt_pct(indicators["inflation"]["cpi_yoy"]), indicators["inflation"]["cpi_date"]),
        ("CPI 3个月年化", "CPI 3m annualized", fmt_pct(indicators["inflation"]["cpi_3m_annualized"]), indicators["inflation"]["cpi_date"]),
        ("联邦基金利率", "Fed funds", fmt_num(indicators["policy_rates"]["fedfunds"]) + "%", indicators["policy_rates"]["fedfunds_date"]),
        ("10年美债 / 10年实际利率", "10Y / real 10Y", f"{fmt_num(indicators['policy_rates']['ten_year'])}% / {fmt_num(indicators['policy_rates']['real_yield_10y'])}%", indicators["policy_rates"]["ten_year_date"]),
        ("M2 同比 / 3个月年化", "M2 YoY / 3m ann.", f"{fmt_pct(indicators['liquidity']['m2_yoy'])} / {fmt_pct(indicators['liquidity']['m2_3m_annualized'])}", indicators["liquidity"]["m2_date"]),
        ("联储资产负债表13周", "Fed balance sheet 13w", fmt_pct(indicators["liquidity"]["fed_balance_sheet_13w_change"]), indicators["liquidity"]["fed_balance_sheet_date"]),
        ("美元指数13周", "Dollar 13w", fmt_pct(indicators["dollar_risk"]["dollar_index_13w_change"]), indicators["dollar_risk"]["dollar_index_date"]),
        ("VIX / 高收益债利差", "VIX / HY OAS", f"{fmt_num(indicators['dollar_risk']['vix'])} / {fmt_num(indicators['dollar_risk']['high_yield_oas'])}%", indicators["dollar_risk"]["vix_date"]),
        ("联邦总债务/GDP", "Gross debt/GDP", fmt_num(indicators["debt"]["gross_debt_gdp"]) + "%", indicators["debt"]["gross_debt_gdp_date"]),
        ("公众持有债务/GDP", "Public debt/GDP", fmt_num(indicators["debt"]["public_debt_gdp"]) + "%", indicators["debt"]["public_debt_gdp_date"]),
        ("利息支出/GDP", "Interest outlays/GDP", fmt_num(indicators["debt"]["interest_outlays_gdp"]) + "%", indicators["debt"]["interest_outlays_gdp_date"]),
    ]
    return "\n".join(
        f"<tr><th>{bilingual(zh, en)}</th><td class=\"num\">{html.escape(value)}</td><td class=\"num muted-cell\">{html.escape(str(asof))}</td></tr>"
        for zh, en, value, asof in rows
    )


def make_signal_cards(signals: list[dict[str, Any]]) -> str:
    cards = []
    for index, signal in enumerate(signals):
        stance = signal["stance"]
        title_zh, title_en = SIGNAL_TITLES.get(signal["name"], (signal["name"], signal["name"]))
        cards.append(
            f'<article class="signal" style="--i:{index}">'
            f'<div class="signal-head"><h3>{bilingual(title_zh, title_en, "bi heading-bi")}</h3><span class="pill {html.escape(stance)}">{html.escape(stance_text(stance))}</span></div>'
            f'<p>{html.escape(signal["detail"])}</p>'
            f'<strong>分数 / score {int(signal["score"]):+d}</strong>'
            "</article>"
        )
    return "\n".join(cards)


def make_correlation_table(correlations: dict[str, Any], config: dict[str, Any]) -> str:
    rows = []
    for sid, lag_map in correlations.items():
        meta = config["fred"]["series"].get(sid, {})
        zh_label = SERIES_ZH.get(sid, meta.get("label", sid))
        en_label = meta.get("label", sid)
        best_lag = None
        best_abs = -1.0
        cells = []
        for lag, item in lag_map.items():
            corr = item["correlation"]
            if corr is not None and abs(corr) > best_abs:
                best_abs = abs(corr)
                best_lag = lag
            cells.append(f"<td>{fmt_corr(corr)} <small>n={item['pairs']}</small></td>")
        rows.append(
            f"<tr><th>{bilingual(zh_label, en_label)}</th>"
            + "".join(cells)
            + f"<td class=\"num\">{html.escape(str(best_lag))}d</td></tr>"
        )
    headings = "".join(f"<th>{lag}天滞后<br><small>{lag}d lag</small></th>" for lag in config["correlation_lags_days"])
    return f"<table><thead><tr><th>宏观序列<br><small>Macro series</small></th>{headings}<th>最大绝对值<br><small>best abs</small></th></tr></thead><tbody>{''.join(rows)}</tbody></table>"


def render_report(
    indicators: dict[str, Any],
    signals: list[dict[str, Any]],
    regime_state: dict[str, Any],
    correlations: dict[str, Any],
    series: dict[str, list[Point]],
    btc: list[Point],
    config: dict[str, Any],
    history_summary: dict[str, Any],
) -> str:
    btc_chart = svg_line_chart(btc[-365:] if len(btc) > 365 else btc, 900, 220, log_scale=False)
    m2 = series.get("M2SL", [])
    overlay = normalized_overlay_svg(btc[-1200:] if len(btc) > 1200 else btc, m2[-60:] if len(m2) > 60 else m2, 900, 240)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    regime_label = stance_text(regime_state["label"])
    ma_state = "高于200日均线 / above 200d MA" if indicators["btc"]["above_ma200"] else "低于200日均线 / below 200d MA"
    history_entries = history_summary.get("recent_entries", [])
    history_chart = history_regime_svg(history_entries, 900, 150)
    history_path = history_summary.get("path") or "disabled"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BTC Macro Observatory</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f3ee;
      --surface: #fffdfa;
      --surface-soft: #f1ede6;
      --ink: #181a1f;
      --muted: #6f716f;
      --line: #ded8ce;
      --accent: #f7931a;
      --accent-deep: #9c5511;
      --good: #1f6d62;
      --bad: #a33a2b;
      --mixed: #86621b;
      --mono: "SF Mono", "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace;
      --sans: "Avenir Next", "SF Pro Display", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", ui-sans-serif, system-ui, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    html {{ background: var(--bg); }}
    body {{
      margin: 0;
      font-family: var(--sans);
      background:
        linear-gradient(90deg, rgba(24,26,31,0.045) 1px, transparent 1px) 0 0 / 42px 42px,
        linear-gradient(180deg, rgba(24,26,31,0.035) 1px, transparent 1px) 0 0 / 42px 42px,
        radial-gradient(circle at 78% 12%, rgba(247,147,26,0.16), transparent 28rem),
        var(--bg);
      color: var(--ink);
      line-height: 1.5;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image: linear-gradient(rgba(255,255,255,0.18), rgba(255,255,255,0));
    }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 28px 22px 64px; }}
    header {{ display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.55fr); gap: 28px; align-items: end; min-height: 280px; padding: 26px 0 20px; }}
    h1 {{ margin: 0; font-size: clamp(42px, 6.3vw, 86px); line-height: 0.94; letter-spacing: 0; max-width: 880px; }}
    h2 {{ margin: 0 0 14px; font-size: 22px; letter-spacing: 0; }}
    h3 {{ margin: 0; font-size: 15px; letter-spacing: 0; }}
    p {{ margin: 0; color: var(--muted); }}
    section {{ margin-top: 26px; }}
    .eyebrow {{ font-family: var(--mono); font-size: 12px; text-transform: uppercase; color: var(--accent-deep); margin-bottom: 14px; }}
    .subtitle {{ max-width: 650px; margin-top: 20px; font-size: 16px; color: #4b4d4d; }}
    .meta-stack {{ display: grid; gap: 10px; justify-items: end; }}
    .meta-chip {{
      display: inline-flex;
      width: fit-content;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--line);
      background: rgba(255,253,250,0.74);
      border-radius: 999px;
      padding: 8px 12px;
      font-family: var(--mono);
      font-size: 12px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.72);
    }}
    a.meta-chip {{
      color: inherit;
      text-decoration: none;
      transition: border-color 160ms ease, background 160ms ease, transform 160ms ease;
    }}
    a.meta-chip:hover {{
      transform: translateY(-1px);
      border-color: rgba(24,26,31,0.28);
      background: rgba(255,255,255,0.92);
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.55fr) minmax(260px, 0.45fr);
      gap: 16px;
      align-items: end;
    }}
    .surface {{
      background: rgba(255,253,250,0.82);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 24px 70px -42px rgba(70, 50, 25, 0.36), inset 0 1px 0 rgba(255,255,255,0.88);
      backdrop-filter: blur(14px);
    }}
    .market-panel {{ padding: 24px; }}
    .price-row {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 18px; align-items: end; }}
    .hero-number {{ font-family: var(--mono); font-size: clamp(42px, 7vw, 86px); font-weight: 760; letter-spacing: 0; line-height: 0.95; margin-top: 10px; }}
    .live-quote {{ margin-top: 18px; }}
    .live-label {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      color: var(--muted);
      font-size: 13px;
    }}
    .live-status {{
      font-family: var(--mono);
      font-size: 12px;
      color: var(--accent-deep);
      white-space: nowrap;
    }}
    .live-subline {{
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px 12px;
      min-height: 28px;
      margin-top: 8px;
      font-family: var(--mono);
      color: #4b4d4d;
      font-size: 12px;
    }}
    .live-change {{ color: var(--muted); }}
    .live-change.up {{ color: var(--good); }}
    .live-change.down {{ color: var(--bad); }}
    .live-refresh {{
      appearance: none;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,0.62);
      color: #343637;
      cursor: pointer;
      font-family: var(--mono);
      font-size: 12px;
      padding: 5px 9px;
      transition: border-color 160ms ease, background 160ms ease, transform 160ms ease;
    }}
    .live-refresh:hover {{ transform: translateY(-1px); border-color: rgba(247,147,26,0.48); background: rgba(255,255,255,0.9); }}
    .live-refresh:disabled {{ cursor: wait; opacity: 0.62; transform: none; }}
    .regime {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
    .pill {{
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 5px 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      font-family: var(--mono);
      font-size: 12px;
      font-weight: 700;
      background: rgba(255,255,255,0.56);
      white-space: nowrap;
    }}
    .market-strip {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      border-top: 1px solid var(--line);
      margin-top: 22px;
      padding-top: 14px;
      gap: 12px;
    }}
    .metric-label {{ display: block; color: var(--muted); font-size: 12px; }}
    .metric-value {{ display: block; font-family: var(--mono); font-size: 17px; margin-top: 3px; }}
    .read-panel {{ padding: 22px; align-self: stretch; display: grid; align-content: space-between; gap: 18px; }}
    .read-panel p {{ color: #3f4142; }}
    .section-head {{ display: flex; justify-content: space-between; gap: 20px; align-items: end; margin-bottom: 12px; }}
    .section-head p {{ max-width: 640px; font-size: 14px; }}
    .signal-grid {{ display: grid; grid-template-columns: minmax(0, 1.28fr) minmax(270px, 0.72fr); gap: 12px; }}
    .signal {{
      background: rgba(255,253,250,0.78);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      min-height: 142px;
      animation: rise 540ms cubic-bezier(0.16, 1, 0.3, 1) both;
      animation-delay: calc(var(--i) * 58ms);
      transition: transform 260ms cubic-bezier(0.16, 1, 0.3, 1), border-color 260ms cubic-bezier(0.16, 1, 0.3, 1), background 260ms cubic-bezier(0.16, 1, 0.3, 1);
    }}
    .signal:nth-child(3n + 1) {{ transform-origin: left center; }}
    .signal:nth-child(4) {{ grid-row: span 2; }}
    .signal:nth-child(7) {{ grid-column: 1 / -1; min-height: 118px; }}
    .signal:hover {{ transform: translateY(-3px); border-color: rgba(247,147,26,0.46); background: rgba(255,255,255,0.94); }}
    .signal:active {{ transform: translateY(-1px) scale(0.995); }}
    .signal-head {{ display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; margin-bottom: 14px; }}
    .signal p {{ font-size: 14px; }}
    .signal strong {{ display: inline-block; margin-top: 16px; font-family: var(--mono); font-size: 12px; color: #3d3f42; }}
    .supportive {{ color: var(--good); }}
    .hostile {{ color: var(--bad); }}
    .mixed {{ color: var(--mixed); }}
    .chart-shell {{ padding: 18px; overflow: hidden; }}
    .chart {{ color: var(--accent); width: 100%; min-height: 220px; }}
    .chart svg {{ display: block; width: 100%; height: auto; }}
    .history-layout {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr); gap: 14px; }}
    .history-panel {{ padding: 18px; }}
    .history-chart {{ color: var(--accent); min-height: 150px; }}
    .history-chart svg {{ width: 100%; height: auto; display: block; }}
    .history-stats {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
    .history-stat {{
      border-top: 1px solid var(--line);
      padding-top: 10px;
      min-height: 72px;
    }}
    .history-stat strong {{ display: block; font-family: var(--mono); font-size: 20px; letter-spacing: 0; }}
    .history-stat span {{ color: var(--muted); font-size: 12px; }}
    .history-trail {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }}
    .history-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 9px;
      background: rgba(255,255,255,0.58);
      font-family: var(--mono);
      font-size: 12px;
    }}
    .history-pill b {{ font-weight: 800; }}
    .empty-history {{
      min-height: 150px;
      display: grid;
      place-items: center;
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 8px;
      font-size: 14px;
    }}
    .legend {{ display: flex; gap: 16px; margin-top: 10px; font-size: 13px; color: var(--muted); }}
    .dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }}
    .orange {{ background: var(--accent); }}
    .slate {{ background: #475569; }}
    .table-shell {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; background: rgba(255,253,250,0.82); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
    th, td {{ text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{ font-size: 13px; color: #323436; min-width: 160px; }}
    td {{ color: #1f2328; }}
    tr:last-child th, tr:last-child td {{ border-bottom: 0; }}
    tbody tr:hover {{ background: rgba(247,147,26,0.055); }}
    small {{ color: var(--muted); }}
    .bi {{ display: inline-grid; gap: 2px; }}
    .bi > span {{ font-weight: 720; }}
    .bi > small {{ font-weight: 500; font-size: 12px; }}
    .heading-bi > span {{ font-size: 16px; }}
    .heading-bi > small {{ font-family: var(--mono); }}
    .num {{ font-family: var(--mono); }}
    .muted-cell {{ color: var(--muted); }}
    .note {{ font-size: 13px; color: var(--muted); margin-top: 10px; max-width: 820px; }}
    .rule {{ height: 1px; background: var(--line); margin: 18px 0; }}
    @keyframes rise {{
      from {{ opacity: 0; transform: translateY(12px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      .signal {{ animation: none; transition: none; }}
    }}
    @media (max-width: 900px) {{
      header, .summary-grid, .signal-grid, .history-layout {{ grid-template-columns: 1fr; }}
      .meta-stack {{ justify-items: start; }}
      .market-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .signal:nth-child(4), .signal:nth-child(7) {{ grid-row: auto; grid-column: auto; }}
      main {{ padding: 22px 14px 48px; }}
      header {{ min-height: auto; gap: 18px; }}
    }}
    @media (max-width: 560px) {{
      .market-strip {{ grid-template-columns: 1fr; }}
      .price-row {{ grid-template-columns: 1fr; }}
      th, td {{ padding: 10px; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <div class="eyebrow">Macro Bitcoin Observatory</div>
      <h1>宏观约束下的 BTC<br>BTC Under Macro Constraints</h1>
      <p class="subtitle">把通胀、利率、债务、流动性、美元与 BTC 价格压到同一个观察平面里。This report compresses inflation, rates, debt, liquidity, the dollar, and BTC into one research surface.</p>
    </div>
    <div class="meta-stack">
      <a class="meta-chip" href="./">返回首页 / home</a>
      <span class="meta-chip">生成时间 / generated {html.escape(generated)}</span>
      <span class="meta-chip">非投资建议 / not investment advice</span>
      <span class="meta-chip">公开数据 / public data</span>
    </div>
  </header>

  <section class="summary-grid">
    <div class="surface market-panel">
      <div class="price-row">
        <div>
          <h2>市场状态 / Market State</h2>
          <div class="regime">
            <span class="pill {html.escape(regime_state["label"])}">{html.escape(regime_label)}</span>
            <span class="pill">分数 / score {int(regime_state["score"]):+d}</span>
            <span class="pill">{html.escape(ma_state)}</span>
          </div>
        </div>
        <span class="meta-chip">as of {html.escape(str(indicators["btc"]["date"]))}</span>
      </div>
      <div class="live-quote" aria-live="polite">
        <div class="live-label">
          <span>实时现货价 / Live spot BTC-USD</span>
          <span class="live-status" data-live-btc-status>connecting</span>
        </div>
        <div class="hero-number" data-live-btc-price data-fallback="${fmt_num(indicators["btc"]["price"], 0)}">${fmt_num(indicators["btc"]["price"], 0)}</div>
        <div class="live-subline">
          <span data-live-btc-source data-static-label="日线宏观参考 / daily macro reference">日线宏观参考 / daily macro reference</span>
          <span data-live-btc-age>as of {html.escape(str(indicators["btc"]["date"]))}</span>
          <span class="live-change" data-live-btc-change hidden></span>
          <button class="live-refresh" type="button" data-live-btc-refresh>刷新 / refresh</button>
        </div>
      </div>
      <div class="market-strip">
        <span><span class="metric-label">日线参考 / daily ref</span><span class="metric-value">${fmt_num(indicators["btc"]["price"], 0)}</span></span>
        <span><span class="metric-label">30日 / 30d</span><span class="metric-value">{fmt_pct(indicators["btc"]["change_30d"])}</span></span>
        <span><span class="metric-label">90日 / 90d</span><span class="metric-value">{fmt_pct(indicators["btc"]["change_90d"])}</span></span>
        <span><span class="metric-label">1年 / 1y</span><span class="metric-value">{fmt_pct(indicators["btc"]["change_365d"])}</span></span>
        <span><span class="metric-label">200日均线 / 200d MA</span><span class="metric-value">${fmt_num(indicators["btc"]["ma200"], 0)}</span></span>
      </div>
    </div>
    <div class="surface read-panel">
      <h2>核心读法 / Core Read</h2>
      <p>当美元流动性扩张、实际利率下行、美元走弱且信用压力受控时，BTC 的宏观环境通常更友好。Persistent inflation can block easing, and high debt can shift from a long-term hard-money narrative into a short-term rate-pressure problem.</p>
      <div class="rule"></div>
      <p>这个系统判断的是环境，不是给出买卖点。It reads the regime, not a trade entry.</p>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>信号矩阵 / Signal Matrix</h2>
      <p>每个信号都用同一套分数压缩宏观压力与支撑。Each signal compresses one macro channel into a comparable score.</p>
    </div>
    <div class="signal-grid">{make_signal_cards(signals)}</div>
  </section>

  <section>
    <div class="section-head">
      <h2>长期更新轨迹 / Long-Run Update Trail</h2>
      <p>每次运行会按 BTC 市场日期去重写入本地 JSONL 历史库。Each run upserts one local JSONL observation by BTC market date.</p>
    </div>
    <div class="history-layout">
      <div class="surface history-panel">
        <div class="history-chart">{history_chart}</div>
        <div class="history-trail">{make_history_trail(history_entries)}</div>
      </div>
      <div class="surface history-panel">
        <div class="history-stats">
          <div class="history-stat"><strong>{int(history_summary.get("count", 0))}</strong><span>累计观测 / observations</span></div>
          <div class="history-stat"><strong>{html.escape(str(history_summary.get("latest_score", "n/a")))}</strong><span>最新分数 / latest score</span></div>
          <div class="history-stat"><strong>{html.escape(str(history_summary.get("first_market_date") or "n/a"))}</strong><span>起始日期 / first date</span></div>
          <div class="history-stat"><strong>{html.escape(str(history_summary.get("last_market_date") or "n/a"))}</strong><span>最新日期 / last date</span></div>
        </div>
        <p class="note">历史文件 / history file: <span class="num">{html.escape(str(history_path))}</span></p>
      </div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>BTC 价格，最近365天 / BTC Price, Last 365 Days</h2>
      <p>价格图保留为轻量 SVG，方便直接分享 HTML。The chart stays as lightweight inline SVG.</p>
    </div>
    <div class="surface chart-shell"><div class="chart">{btc_chart}</div></div>
  </section>

  <section>
    <div class="section-head">
      <h2>BTC 与 M2 标准化对照 / BTC vs M2, Normalized</h2>
      <p>用于观察流动性背景，不把它当作机械领先指标。Use this as liquidity context, not a mechanical lead-lag proof.</p>
    </div>
    <div class="surface chart-shell"><div class="chart">{overlay}</div></div>
    <div class="legend"><span><i class="dot orange"></i>BTC</span><span><i class="dot slate"></i>M2</span></div>
  </section>

  <section>
    <div class="section-head">
      <h2>最新指标 / Latest Indicators</h2>
      <p>债务类指标发布频率较低，适合判断结构性压力，不适合短线择时。Debt series are slower-moving and better for structural context than timing.</p>
    </div>
    <div class="table-shell">
      <table>
        <thead><tr><th>指标<br><small>Indicator</small></th><th>数值<br><small>Value</small></th><th>截至<br><small>As of</small></th></tr></thead>
        <tbody>{make_indicator_rows(indicators)}</tbody>
      </table>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>宏观变化与 BTC 收益相关性 / Macro Change vs BTC Return Correlations</h2>
      <p>相关性不是因果关系，尤其是债务这种低频序列。Correlation is not causation, especially for sparse fiscal series.</p>
    </div>
    <div class="table-shell">{make_correlation_table(correlations, config)}</div>
    <p class="note">计算方式：宏观指标按相邻观察点变化，BTC 用对应窗口收益，并测试不同滞后。Method: macro observation-to-observation changes versus BTC returns over matching shifted windows.</p>
  </section>
</main>
<script>
(() => {{
  const priceEl = document.querySelector("[data-live-btc-price]");
  if (!priceEl) return;

  const statusEl = document.querySelector("[data-live-btc-status]");
  const sourceEl = document.querySelector("[data-live-btc-source]");
  const ageEl = document.querySelector("[data-live-btc-age]");
  const changeEl = document.querySelector("[data-live-btc-change]");
  const refreshEl = document.querySelector("[data-live-btc-refresh]");
  const staticSource = sourceEl ? sourceEl.dataset.staticLabel : "daily macro reference";

  const money = new Intl.NumberFormat("en-US", {{
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }});
  const pct = new Intl.NumberFormat("en-US", {{
    signDisplay: "always",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }});
  const time = new Intl.DateTimeFormat(undefined, {{
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }});

  const providers = [
    {{
      name: "Coinbase spot",
      url: "https://api.coinbase.com/v2/prices/BTC-USD/spot",
      read(data) {{
        return {{
          price: Number(data && data.data && data.data.amount),
          at: Date.now(),
          change24h: null,
        }};
      }},
    }},
    {{
      name: "CoinGecko spot",
      url: "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true&include_last_updated_at=true",
      read(data) {{
        const quote = data && data.bitcoin ? data.bitcoin : {{}};
        return {{
          price: Number(quote.usd),
          at: Number(quote.last_updated_at) * 1000,
          change24h: Number(quote.usd_24h_change),
        }};
      }},
    }},
  ];

  function setText(el, value) {{
    if (el) el.textContent = value;
  }}

  async function fetchProvider(provider) {{
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    try {{
      const response = await fetch(provider.url, {{
        cache: "no-store",
        signal: controller.signal,
      }});
      if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
      const data = await response.json();
      const quote = provider.read(data);
      if (!Number.isFinite(quote.price) || quote.price <= 0) {{
        throw new Error("invalid price");
      }}
      return {{ provider, quote }};
    }} finally {{
      window.clearTimeout(timeout);
    }}
  }}

  function applyQuote(provider, quote) {{
    priceEl.textContent = money.format(quote.price);
    setText(statusEl, "live");
    setText(sourceEl, provider.name);
    setText(ageEl, `updated ${{time.format(new Date(quote.at || Date.now()))}}`);

    if (changeEl && Number.isFinite(quote.change24h)) {{
      changeEl.hidden = false;
      changeEl.textContent = `24h ${{pct.format(quote.change24h)}}%`;
      changeEl.classList.toggle("up", quote.change24h >= 0);
      changeEl.classList.toggle("down", quote.change24h < 0);
    }} else if (changeEl) {{
      changeEl.hidden = true;
      changeEl.textContent = "";
      changeEl.classList.remove("up", "down");
    }}
  }}

  function applyFallback() {{
    priceEl.textContent = priceEl.dataset.fallback || priceEl.textContent;
    setText(statusEl, "fallback");
    setText(sourceEl, staticSource);
    setText(ageEl, "实时源暂不可用 / live feed unavailable");
    if (changeEl) {{
      changeEl.hidden = true;
      changeEl.textContent = "";
      changeEl.classList.remove("up", "down");
    }}
  }}

  async function updateLivePrice() {{
    setText(statusEl, "updating");
    if (refreshEl) refreshEl.disabled = true;
    try {{
      for (const provider of providers) {{
        try {{
          const result = await fetchProvider(provider);
          applyQuote(result.provider, result.quote);
          return;
        }} catch (error) {{
          continue;
        }}
      }}
      applyFallback();
    }} finally {{
      if (refreshEl) refreshEl.disabled = false;
    }}
  }}

  if (refreshEl) {{
    refreshEl.addEventListener("click", updateLivePrice);
  }}

  updateLivePrice();
  window.setInterval(updateLivePrice, 60 * 1000);
}})();
</script>
</body>
</html>
"""
def main() -> int:
    parser = argparse.ArgumentParser(description="Build a BTC macro observation report.")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--force", action="store_true", help="refresh cached raw data")
    parser.add_argument("--history-path", type=Path, default=DEFAULT_HISTORY_PATH, help="JSONL history file for long-run observations")
    parser.add_argument("--no-history", action="store_true", help="do not write or read long-run history")
    args = parser.parse_args()

    config = load_config(args.config)
    start = parse_date(config["start_date"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    fred_url = config["fred"]["base_url"]
    macro_series: dict[str, list[Point]] = {}
    fetch_errors: dict[str, str] = {}
    for series_id in config["fred"]["series"]:
        try:
            print(f"fetch FRED {series_id}", flush=True)
            macro_series[series_id] = filter_since(fetch_fred_series(series_id, fred_url, force=args.force), start)
        except Exception as exc:
            try:
                cached = filter_since(read_fred_cache(series_id), start)
            except Exception:
                cached = []
            if cached:
                fetch_errors[series_id] = f"{exc}; using cached data through {cached[-1].date}"
                macro_series[series_id] = cached
            else:
                fetch_errors[series_id] = str(exc)
                macro_series[series_id] = []

    print(f"fetch BTC {config['btc'].get('source', 'unknown')}", flush=True)
    btc = filter_since(fetch_btc_prices_with_fallback(config["btc"], force=args.force), start)
    if not btc:
        raise RuntimeError("no BTC price data available")

    indicators = build_indicators(macro_series, btc)
    signals = build_signals(indicators)
    regime_state = regime(signals)

    correlations: dict[str, Any] = {}
    for series_id, points in macro_series.items():
        if len(points) < 8:
            continue
        kind = config["fred"]["series"][series_id]["kind"]
        correlations[series_id] = lagged_correlations(points, btc, kind, config["correlation_lags_days"])

    generated_at = datetime.now(timezone.utc).isoformat()
    latest_json = {
        "generated_at": generated_at,
        "start_date": config["start_date"],
        "fetch_errors": fetch_errors,
        "indicators": indicators,
        "signals": signals,
        "regime": regime_state,
        "correlations": correlations,
        "disclaimer": "Research dashboard only. Not investment advice.",
    }

    if args.no_history:
        history_entries = []
        history_summary = summarize_history(history_entries, None)
    else:
        history_entry = build_history_entry(latest_json)
        history_entries = upsert_history(args.history_path, history_entry)
        history_summary = summarize_history(history_entries, args.history_path)

    latest_json["history"] = {
        "enabled": not args.no_history,
        "path": history_summary["path"],
        "count": history_summary["count"],
        "first_market_date": history_summary["first_market_date"],
        "last_market_date": history_summary["last_market_date"],
    }

    report = render_report(indicators, signals, regime_state, correlations, macro_series, btc, config, history_summary)
    (OUT_DIR / "report.html").write_text(report, encoding="utf-8")
    (OUT_DIR / "latest.json").write_text(json.dumps(latest_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Report: {OUT_DIR / 'report.html'}")
    print(f"JSON:   {OUT_DIR / 'latest.json'}")
    if not args.no_history:
        print(f"History: {args.history_path} ({history_summary['count']} observations)")
    print(f"Regime: {regime_state['label']} ({regime_state['score']:+d})")
    if fetch_errors:
        print("Fetch warnings:")
        for series_id, error in fetch_errors.items():
            print(f"  - {series_id}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
