#!/usr/bin/env python3
"""
AI-SaaS 信号台 · 逐季更新工具
财报出来后跑一次,把新读数写进历史(observations.jsonl)并更新看板状态(signals.json)。

用法:
  python3 saas-signals/scripts/update_signal.py \
      --ticker SNOW --signal grossmargin \
      --value "74.2%" --status amber --asof 2026-08-26 \
      --source "Q2 FY27 财报" --note "AWS 降本对冲减弱"

signal: growth | grossmargin | nrr
status: green | amber | red
查看当前: python3 .../update_signal.py --show
"""
import argparse, json, pathlib, datetime, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SIG = ROOT / "data" / "signals.json"
OBS = ROOT / "data" / "observations.jsonl"
VALID_SIG = {"growth", "grossmargin", "nrr"}
VALID_ST = {"green", "amber", "red"}

def show():
    d = json.loads(SIG.read_text(encoding="utf-8"))
    print(f"# {d['title']} · 更新 {d['updated']}\n")
    for s in d["signals"]:
        print(f"[{s['id']}] {s['name']} — {s['question']}")
        for tk, m in s["by"].items():
            print(f"  {tk:5} {m['status']:5} 最新 {m['latest']:8} (守 {m['hold']} / 证伪 {m['falsify']}) @{m['asof']}")
        print()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--ticker"); ap.add_argument("--signal")
    ap.add_argument("--value"); ap.add_argument("--status")
    ap.add_argument("--asof"); ap.add_argument("--source", default="财报")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if a.show:
        return show()
    req = [a.ticker, a.signal, a.value, a.status]
    if not all(req):
        sys.exit("缺参数。需 --ticker --signal --value --status（见脚本头部用法）。--show 看当前。")
    if a.signal not in VALID_SIG: sys.exit(f"signal 须为 {VALID_SIG}")
    if a.status not in VALID_ST:  sys.exit(f"status 须为 {VALID_ST}")
    tk = a.ticker.upper()
    asof = a.asof or datetime.date.today().isoformat()

    d = json.loads(SIG.read_text(encoding="utf-8"))
    if tk not in d["companies"]:
        sys.exit(f"未知 ticker {tk}（当前 {list(d['companies'])}）")
    sig = next((s for s in d["signals"] if s["id"] == a.signal), None)
    if not sig or tk not in sig["by"]:
        sys.exit("信号或公司不匹配")
    m = sig["by"][tk]
    m.update(latest=a.value, status=a.status, asof=asof)
    if a.note: m["note"] = a.note
    d["updated"] = datetime.date.today().isoformat()
    SIG.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rec = {"date": asof, "ticker": tk, "signal": a.signal, "value": a.value,
           "status": a.status, "source": a.source, "note": a.note}
    with OBS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"✓ {tk}/{a.signal} → {a.value} ({a.status}) @{asof}　已写历史+更新看板")
    print("  记得 git add saas-signals && git commit && git push（push 会触发 Pages 部署）")

if __name__ == "__main__":
    main()
