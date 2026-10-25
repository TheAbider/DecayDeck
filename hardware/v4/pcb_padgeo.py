"""Dump every pad's position (relative to its part origin at rotation 0) for chosen parts.

usage: python pcb_padgeo.py REF [REF ...]
Reads pcb_pads.json (from verify_pcb.py) for part ids/positions and fetches pad geometry.
"""
import json
import math
import sys

from eda import run

JS = r"""
const ids = __IDS__;
const out = {};
for (const id of ids) {
  const pins = await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(id);
  out[id] = (pins || []).map(p => ({ num: p.getState_PadNumber(), net: p.getState_Net(), x: p.getState_X(), y: p.getState_Y(),
    pad: p.getState_Pad(), hole: p.getState_Hole(), layer: p.getState_Layer(), rot: p.getState_Rotation() }));
}
return out;
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    comps = {c["des"]: c for c in json.load(open("pcb_pads.json", encoding="utf-8"))}
    refs = sys.argv[1:]
    r = run(JS.replace("__IDS__", json.dumps([comps[x]["id"] for x in refs])))
    for ref in refs:
        c = comps[ref]
        a = -math.radians(c["rot"] or 0)
        print(f"{ref} fp={c['fp']} at ({c['x']:.1f},{c['y']:.1f}) rot={c['rot']} layer={c['layer']}")
        for p in sorted(r["result"][c["id"]], key=lambda p: str(p["num"])):
            dx, dy = p["x"] - c["x"], p["y"] - c["y"]
            lx, ly = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
            print(f"   pad {p['num']:>5} net={p['net']!s:12} local=({lx*0.0254:6.2f},{ly*0.0254:6.2f})mm pad={p['pad']} hole={p['hole']}")


if __name__ == "__main__":
    main()
