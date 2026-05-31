#!/usr/bin/env python3
"""
美股见顶硬触发 · 更新工具
盯到某个硬触发有变化时跑一次,写历史(observations.jsonl)并更新看板(triggers.json)。

用法:
  python3 market-top-triggers/scripts/update_trigger.py \
      --id credit --value "HY OAS 扩大至 420bp" --status red \
      --asof 2026-08-15 --source "FRED" --note "信用市场报警"

id: fed | credit | earnings | realrate | breadth
status: green(未触发/正常) | amber(临界/预警) | red(已触发)
查看当前: python3 .../update_trigger.py --show
"""
import argparse, json, pathlib, datetime, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TRG = ROOT / "data" / "triggers.json"
OBS = ROOT / "data" / "observations.jsonl"
VALID_ST = {"green", "amber", "red"}

def show():
    d = json.loads(TRG.read_text(encoding="utf-8"))
    print(f"# {d['title']} · 更新 {d['updated']}\n# {d['thesis']}\n")
    print("硬触发（要盯）:")
    for t in d["hard"]:
        print(f"  [{t['id']:9}] {t['status']:5} {t['name']} — {t['latest']} @{t['asof']}")
    print("\n软指标（背景,不择时）:")
    for s in d["soft"]:
        print(f"  · {s['name']}: {s['latest']}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--id"); ap.add_argument("--value"); ap.add_argument("--status")
    ap.add_argument("--asof"); ap.add_argument("--source", default="")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if a.show: return show()
    if not all([a.id, a.value, a.status]):
        sys.exit("缺参数。需 --id --value --status（见脚本头部）。--show 看当前。")
    if a.status not in VALID_ST: sys.exit(f"status 须为 {VALID_ST}")
    asof = a.asof or datetime.date.today().isoformat()

    d = json.loads(TRG.read_text(encoding="utf-8"))
    t = next((x for x in d["hard"] if x["id"] == a.id), None)
    if not t: sys.exit(f"未知 id {a.id}（当前 {[x['id'] for x in d['hard']]}）")
    t.update(latest=a.value, status=a.status, asof=asof)
    d["updated"] = datetime.date.today().isoformat()
    TRG.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rec = {"date": asof, "kind": "hard", "id": a.id, "value": a.value,
           "status": a.status, "source": a.source, "note": a.note}
    with OBS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"✓ {a.id} → {a.value} ({a.status}) @{asof}　已写历史+更新看板")
    print("  记得 git add market-top-triggers && git commit && git push")

if __name__ == "__main__":
    main()
