"""Compare EasyEDA's actual absolute pad positions with place_pcb.py's predictions.

usage: python verify_place.py   -> max deviation per part; exit 1 if any pad is off by > 0.05 mm
"""
import json
import sys

from eda import run
from place_pcb import PLACE, abs_pads

JS = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = {};
for (const c of comps) {
  const des = c.getState_Designator();
  if (!__WANT__.includes(des)) continue;
  const pins = await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
  out[des] = (pins || []).map(p => [p.getState_PadNumber(), p.getState_X() * 0.0254, p.getState_Y() * 0.0254]);
}
return out;
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    refs = list(PLACE)
    worst, bad = {}, []
    for i in range(0, len(refs), 40):
        chunk = refs[i:i + 40]
        r = run(JS.replace("__WANT__", json.dumps(chunk)))
        if not r.get("success"):
            raise SystemExit(r.get("error"))
        for ref, pads in r["result"].items():
            pred = {}
            for p in abs_pads(ref):
                pred.setdefault(p["num"], []).append((p["ax"], p["ay"]))
            dev = 0.0
            for num, x, y in pads:
                cands = pred.get(num) or [(1e9, 1e9)]
                dev = max(dev, min(((x - px) ** 2 + (y - py) ** 2) ** 0.5 for px, py in cands))
            worst[ref] = dev
            if dev > 0.05:
                bad.append((ref, round(dev, 3)))
    print("parts checked:", len(worst), " max deviation:", round(max(worst.values()), 4))
    print("off:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
