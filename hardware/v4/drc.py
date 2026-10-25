"""Run EasyEDA's DRC and summarise the errors (writes drc.json).

The check runs detached and is polled, because a full DRC can outlast the bridge's 30 s request limit.
EasyEDA reports positions and distances in 10-mil units; they are printed here in mm.

usage: python drc.py [max examples per group, default 6]
"""
import json
import sys
import time

from eda import run

START = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
globalThis.__ddDrc = { started: Date.now(), done: false };
eda.pcb_Drc.check(true, false, true)
  .then(r => { globalThis.__ddDrc.result = r; globalThis.__ddDrc.done = true; })
  .catch(e => { globalThis.__ddDrc.error = String(e); globalThis.__ddDrc.done = true; });
return 'started';
"""
POLL = r"""
const s = globalThis.__ddDrc;
return s ? { done: s.done, secs: Math.round((Date.now() - s.started) / 1000), error: s.error, result: s.done ? s.result : null } : null;
"""
U = 0.254   # EasyEDA DRC unit (10 mil) in mm


def leaves(node, path=()):
    """Yield (group path, error entry) for every error in the nested DRC tree."""
    if isinstance(node, list):
        for n in node:
            yield from leaves(n, path)
    elif isinstance(node, dict):
        if "list" in node:
            yield from leaves(node["list"], path + (node.get("name", "?"),))
        else:
            yield path, node


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    print(run(START, retry_on_drop=False).get("result"))
    while True:
        time.sleep(5)
        st = run(POLL).get("result")
        if st is None:
            raise SystemExit("lost the DRC state")
        if st["done"]:
            break
    if st.get("error"):
        raise SystemExit("DRC error: " + st["error"])
    res = st["result"]
    json.dump(res, open("drc.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    if not isinstance(res, list):
        print("DRC result:", res)
        return 0 if res is True else 1
    groups = {}
    for path, e in leaves(res):
        groups.setdefault(" / ".join(path), []).append(e)
    total = sum(len(v) for v in groups.values())
    print(f"DRC finished in {st['secs']} s: {total} errors in {len(groups)} groups")
    for g, es in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f"\n{len(es):4}  {g}")
        for e in es[:per]:
            ed = (e.get("explanation") or {}).get("errData") or {}
            pos = ed.get("position") or e.get("pos") or {}
            o1 = (e.get("obj1") or {}).get("typeName", "") + (e.get("obj1") or {}).get("suffix", "")
            o2 = (e.get("obj2") or {}).get("typeName", "") + (e.get("obj2") or {}).get("suffix", "")
            dist = ""
            if "minDistance" in ed:
                dist = f"  {ed['minDistance'] * U:.3f} mm < {ed.get('clearance', 0) * U:.3f} mm"
            where = f"({pos.get('x', 0) * U:7.2f},{pos.get('y', 0) * U:7.2f})" if pos else ""
            print(f"      {where} {e.get('layer', '')}: {o1}  <->  {o2}{dist}  [{e.get('ruleName', '')}]")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
