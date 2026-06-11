#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "btc-macro-system" / "outputs" / "latest.json"
SVG_OUT = ROOT / "btc-macro-gravity-map-2026.svg"
PNG_OUT = ROOT / "btc-macro-gravity-map-2026.png"


W = 2000
H = 2600


def esc(value: object) -> str:
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def num(value: float | None, digits: int = 0) -> str:
    if value is None:
        return "n/a"
    return f"{value:,.{digits}f}"


def pp(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.{digits}f}pp"


def lines(text: str, width: int) -> list[str]:
    out: list[str] = []
    for part in text.split("\n"):
        out.extend(textwrap.wrap(part, width=width, break_long_words=True, break_on_hyphens=False) or [""])
    return out


def text_block(
    x: int,
    y: int,
    text: str,
    *,
    width: int = 28,
    size: int = 28,
    klass: str = "muted",
    line_height: int | None = None,
) -> str:
    dy = line_height or int(size * 1.45)
    chunks = []
    for idx, line in enumerate(lines(text, width)):
        chunks.append(f'<text class="{klass}" x="{x}" y="{y + idx * dy}" style="font-size:{size}px">{esc(line)}</text>')
    return "\n".join(chunks)


def card(
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    subtitle: str,
    score: str,
    body: str,
    *,
    tone: str,
    width: int = 23,
) -> str:
    return f"""
    <g class="card-wrap">
      <rect class="glass {tone}-stroke" x="{x}" y="{y}" width="{w}" height="{h}" rx="26"/>
      <rect class="{tone}" x="{x + 26}" y="{y + 26}" width="10" height="{h - 52}" rx="5"/>
      <text class="label" x="{x + 58}" y="{y + 62}">{esc(title)}</text>
      <text class="tiny" x="{x + 58}" y="{y + 100}">{esc(subtitle)}</text>
      <text class="score {tone}-fill" x="{x + w - 126}" y="{y + 74}">{esc(score)}</text>
      {text_block(x + 58, y + 152, body, width=width, size=25, klass="body")}
    </g>
    """


def metric(x: int, y: int, label: str, value: str, detail: str, tone: str) -> str:
    return f"""
      <g>
        <rect class="metric {tone}-stroke" x="{x}" y="{y}" width="350" height="128" rx="20"/>
        <text class="tiny" x="{x + 26}" y="{y + 40}">{esc(label)}</text>
        <text class="metric-value {tone}-fill" x="{x + 26}" y="{y + 84}">{esc(value)}</text>
        <text class="tiny" x="{x + 26}" y="{y + 112}">{esc(detail)}</text>
      </g>
    """


def render(data: dict[str, Any]) -> str:
    indicators = data["indicators"]
    btc = indicators["btc"]
    inflation = indicators["inflation"]
    policy = indicators["policy_rates"]
    liquidity = indicators["liquidity"]
    risk = indicators["dollar_risk"]
    debt = indicators["debt"]
    regime = data["regime"]
    history = data.get("history", {})
    generated = data.get("generated_at", "")
    try:
        generated_display = datetime.fromisoformat(generated.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        generated_display = generated

    price = btc["price"]
    ma200 = btc["ma200"]
    ma_gap = price / ma200 - 1 if price and ma200 else None
    center_score = regime["score"]
    center_label = regime["label"]

    orbit_dash = "24 18"
    liquidity_body = (
        f"M2 3个月年化 {pct(liquidity['m2_3m_annualized'])}\n"
        f"联储资产负债表13周 {pct(liquidity['fed_balance_sheet_13w_change'])}\n"
        "钱的水位在回升，\n"
        "这是当前最强支撑。"
    )
    risk_body = (
        f"VIX {num(risk['vix'], 2)}\n"
        f"高收益债利差13周 {pp(risk['high_yield_oas_13w_delta'])}\n"
        "信用压力没有升温，\n"
        "风险资产仍有呼吸空间。"
    )
    inflation_body = (
        f"CPI同比 {pct(inflation['cpi_yoy'])}\n"
        f"3个月年化 {pct(inflation['cpi_3m_annualized'])}\n"
        "它把降息门槛抬高，\n"
        "让流动性支撑难以释放。"
    )
    real_rate_body = (
        f"10年期实际收益率 {num(policy['real_yield_10y'], 2)}%\n"
        f"13周上行 {pp(policy['real_yield_13w_delta'])}\n"
        "这是 BTC 估值最直接的\n"
        "折现率压力。"
    )
    trend_body = (
        "BTC 仍低于200日均线\n"
        f"30日 {pct(btc['change_30d'])}\n"
        f"广义美元13周 {pct(risk['dollar_index_13w_change'])}\n"
        "价格趋势还没确认转强。"
    )
    debt_body = (
        f"公众持有债务/GDP {num(debt['public_debt_gdp'],2)}%\n"
        f"利息支出/GDP {num(debt['interest_outlays_gdp'],2)}%\n"
        "长期支持硬通货叙事，\n"
        "短期可能放大真实利率压力。"
    )

    force_paths = """
      <path class="force support" d="M 445 625 C 660 520, 765 565, 890 795"/>
      <path class="force support" d="M 420 1055 C 620 1045, 755 1010, 900 900"/>
      <path class="force hostile" d="M 1560 610 C 1320 550, 1220 620, 1078 792"/>
      <path class="force hostile" d="M 1570 920 C 1360 918, 1225 900, 1090 865"/>
      <path class="force mixed-line" d="M 1520 1215 C 1340 1140, 1200 1010, 1080 910"/>
      <path class="force debt-line" d="M 1000 1445 C 995 1255, 995 1085, 995 950"/>
    """

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <radialGradient id="bgGrad" cx="50%" cy="28%" r="75%">
      <stop offset="0%" stop-color="#223126"/>
      <stop offset="42%" stop-color="#121815"/>
      <stop offset="100%" stop-color="#0b100e"/>
    </radialGradient>
    <radialGradient id="btcGlow" cx="42%" cy="34%" r="70%">
      <stop offset="0%" stop-color="#f5b65f"/>
      <stop offset="42%" stop-color="#b87825"/>
      <stop offset="100%" stop-color="#3d2716"/>
    </radialGradient>
    <filter id="softShadow" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="28" stdDeviation="32" flood-color="#020403" flood-opacity="0.52"/>
    </filter>
    <filter id="fineNoise" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3" stitchTiles="stitch"/>
      <feColorMatrix type="saturate" values="0"/>
      <feComponentTransfer>
        <feFuncA type="table" tableValues="0 0.035"/>
      </feComponentTransfer>
    </filter>
    <marker id="arrowSupport" viewBox="0 0 14 14" refX="12" refY="7" markerWidth="11" markerHeight="11" orient="auto">
      <path d="M0 0 L14 7 L0 14 Z" fill="#76b48b"/>
    </marker>
    <marker id="arrowHostile" viewBox="0 0 14 14" refX="12" refY="7" markerWidth="11" markerHeight="11" orient="auto">
      <path d="M0 0 L14 7 L0 14 Z" fill="#d98064"/>
    </marker>
    <style>
      .bg {{ fill:url(#bgGrad); }}
      .grain {{ filter:url(#fineNoise); opacity:.9; }}
      .grid {{ stroke:#e6d8bd; stroke-opacity:.045; stroke-width:1; }}
      .h1 {{ fill:#f2eadf; font: 850 76px "Avenir Next","PingFang SC","Microsoft YaHei",sans-serif; letter-spacing:0; }}
      .h2 {{ fill:#f2eadf; font: 780 42px "Avenir Next","PingFang SC","Microsoft YaHei",sans-serif; }}
      .label {{ fill:#f2eadf; font: 780 32px "Avenir Next","PingFang SC","Microsoft YaHei",sans-serif; }}
      .body {{ fill:#c7c5bb; font-family:"Avenir Next","PingFang SC","Microsoft YaHei",sans-serif; }}
      .muted {{ fill:#a3a69c; font-family:"Avenir Next","PingFang SC","Microsoft YaHei",sans-serif; }}
      .tiny {{ fill:#9da59b; font: 500 22px "SF Mono","JetBrains Mono",Menlo,monospace; }}
      .mono {{ fill:#ebe2d1; font-family:"SF Mono","JetBrains Mono",Menlo,monospace; }}
      .score {{ font: 820 34px "SF Mono","JetBrains Mono",Menlo,monospace; }}
      .glass {{ fill:rgba(22,28,24,.72); stroke:#2f3d34; stroke-width:2; filter:url(#softShadow); }}
      .metric {{ fill:rgba(17,23,20,.74); stroke-width:2; }}
      .metric-value {{ font: 840 34px "SF Mono","JetBrains Mono",Menlo,monospace; }}
      .support {{ stroke:#76b48b; stroke-width:5; fill:none; stroke-linecap:round; marker-end:url(#arrowSupport); opacity:.82; }}
      .hostile {{ stroke:#d98064; stroke-width:5; fill:none; stroke-linecap:round; marker-end:url(#arrowHostile); opacity:.82; }}
      .mixed-line {{ stroke:#c6ad68; stroke-width:4; fill:none; stroke-linecap:round; stroke-dasharray:18 14; opacity:.72; }}
      .debt-line {{ stroke:#bdb080; stroke-width:4; fill:none; stroke-linecap:round; stroke-dasharray:8 16; opacity:.68; }}
      .ring {{ fill:none; stroke:#e7d6ad; stroke-opacity:.16; stroke-width:2; stroke-dasharray:{orbit_dash}; }}
      .ring-strong {{ fill:none; stroke:#d9a34a; stroke-opacity:.48; stroke-width:3; }}
      .axis {{ stroke:#d8c6a3; stroke-opacity:.18; stroke-width:2; }}
      .support-fill {{ fill:#85c79d; }}
      .hostile-fill {{ fill:#df8b6e; }}
      .mixed-fill {{ fill:#d0b56b; }}
      .debt-fill {{ fill:#c2b58e; }}
      .support-stroke {{ stroke:#618f72; }}
      .hostile-stroke {{ stroke:#a25e4c; }}
      .mixed-stroke {{ stroke:#9c8548; }}
      .debt-stroke {{ stroke:#887d5e; }}
      .amber {{ fill:#d69c47; }}
      .caption {{ fill:#7f877f; font: 500 20px "Avenir Next","PingFang SC","Microsoft YaHei",sans-serif; }}
    </style>
  </defs>

  <rect class="bg" width="{W}" height="{H}"/>
  <g opacity="1">
    {''.join(f'<line class="grid" x1="{x}" y1="0" x2="{x}" y2="{H}"/>' for x in range(80, W, 80))}
    {''.join(f'<line class="grid" x1="0" y1="{y}" x2="{W}" y2="{y}"/>' for y in range(80, H, 80))}
  </g>
  <rect class="grain" width="{W}" height="{H}"/>

  <text class="tiny" x="110" y="94">BTC MACRO GRAVITY MAP · DATA AS OF {esc(btc['date'])}</text>
  <text class="h1" x="110" y="180">BTC 与宏观的引力关系</text>
  <text class="muted" x="114" y="232" style="font-size:30px">不是预测价格，而是看 BTC 现在被哪些宏观力量拉住，哪些力量在托底。</text>
  <text class="tiny" x="114" y="278">generated {esc(generated_display)} · public data · research only</text>

  <g transform="translate(0,0)">
    <line class="axis" x1="1000" y1="390" x2="1000" y2="1510"/>
    <line class="axis" x1="315" y1="860" x2="1685" y2="860"/>
    <circle class="ring" cx="1000" cy="860" r="410"/>
    <circle class="ring" cx="1000" cy="860" r="300"/>
    <circle class="ring" cx="1000" cy="860" r="200"/>
    <circle class="ring-strong" cx="1000" cy="860" r="114"/>
    {force_paths}

    <g filter="url(#softShadow)">
      <circle cx="1000" cy="860" r="150" fill="url(#btcGlow)"/>
      <circle cx="1000" cy="860" r="151" fill="none" stroke="#ffd28a" stroke-opacity=".42" stroke-width="3"/>
      <circle cx="1000" cy="860" r="90" fill="#17130e" fill-opacity=".34"/>
    </g>
    <text class="mono" x="918" y="830" style="font-size:42px;font-weight:900">BTC</text>
    <text class="mono" x="886" y="886" style="font-size:42px;font-weight:900">${num(price)}</text>
    <text class="tiny" x="889" y="930">regime {esc(center_label)} / score {center_score:+d}</text>
    <text class="tiny" x="870" y="965">MA200 gap {pct(ma_gap)}</text>

    {card(120, 470, 520, 300, "美元流动性", "USD liquidity", "+2", liquidity_body, tone="support", width=18)}
    {card(110, 940, 520, 300, "风险偏好", "Risk appetite", "+2", risk_body, tone="support", width=18)}
    {card(1360, 470, 520, 300, "通胀约束", "Inflation constraint", "-2", inflation_body, tone="hostile", width=18)}
    {card(1370, 835, 520, 290, "实际利率", "Real-rate pressure", "-2", real_rate_body, tone="hostile", width=18)}
    {card(1350, 1195, 540, 300, "趋势与美元", "Trend / dollar", "-1 / 0", trend_body, tone="mixed", width=18)}
    {card(670, 1430, 660, 300, "财政压力", "Debt pressure", "0", debt_body, tone="debt", width=24)}
  </g>

  <g transform="translate(110,1840)">
    <text class="h2" x="0" y="0">今日读法：支撑与压制并存</text>
    <text class="muted" x="0" y="48" style="font-size:27px">流动性和信用环境在托底，但通胀和真实利率把 BTC 的上行弹性扣住。</text>
    {metric(0, 105, "支撑一 / liquidity", f"{pct(liquidity['m2_3m_annualized'])}", "M2 3M annualized", "support")}
    {metric(390, 105, "支撑二 / credit", f"{pp(risk['high_yield_oas_13w_delta'])}", "HY OAS 13w", "support")}
    {metric(780, 105, "压制一 / inflation", f"{pct(inflation['cpi_3m_annualized'])}", "CPI 3M annualized", "hostile")}
    {metric(1170, 105, "压制二 / real yield", f"{num(policy['real_yield_10y'], 2)}%", "10Y real yield", "hostile")}
    <rect class="glass mixed-stroke" x="0" y="290" width="1780" height="250" rx="28"/>
    <text class="label" x="42" y="360">核心结论</text>
    {text_block(42, 415, "这不是单边牛市环境，也不是流动性枯竭环境。更像是“水位上升，但阀门还被通胀和真实利率卡住”。如果 CPI 3个月年化降下来、实际利率停止上行，BTC 的宏观阻力会明显减轻；如果油价/关税/供给冲击让通胀重新上行，流动性支撑会被 Fed 反应函数抵消。", width=58, size=31, klass="body", line_height=47)}
  </g>

  <g transform="translate(110,2440)">
    <text class="h2" x="0" y="0">下一步只盯五个闸门</text>
    <text class="caption" x="0" y="52">1. CPI 3个月年化是否回落  2. 10Y实际利率是否下行  3. 美元是否转弱  4. 信用利差是否扩大  5. BTC 能否收复 MA200</text>
    <text class="caption" x="0" y="104">数据源：BTC macro system latest.json / FRED / Blockchain.com public price chart。研究用途，不构成投资建议。</text>
  </g>
</svg>
"""


def main() -> int:
    data = json.loads(LATEST.read_text(encoding="utf-8"))
    SVG_OUT.write_text(render(data), encoding="utf-8")
    subprocess.run(
        [
            "rsvg-convert",
            "-w",
            str(W),
            "-h",
            str(H),
            "-o",
            str(PNG_OUT),
            str(SVG_OUT),
        ],
        check=True,
    )
    print(SVG_OUT)
    print(PNG_OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
