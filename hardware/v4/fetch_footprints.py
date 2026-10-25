"""Fetch every PCB part's pads relative to its origin (rotation 0) -> footprints.json.

Each entry: ref -> {fp, pads: [{num, net, x, y, w, h, shape, hole}]} in mm. Used by place_pcb.py for
collision checks and pin-aware placement.
"""
import json
import math
import sys

from eda import run

PCB = "6098964f68a86131"
JS = r"""
await eda.dmt_EditorControl.openDocument('__PCB__');
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = {};
for (const c of comps.slice(__FROM__, __TO__)) {
  const pins = await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
  out[c.getState_Designator()] = { id: c.getState_PrimitiveId(), x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(),
    fp: (c.getState_Footprint() || {}).name,
    pads: (pins || []).map(p => ({ num: p.getState_PadNumber(), net: p.getState_Net(), x: p.getState_X(), y: p.getState_Y(), pad: p.getState_Pad(), hole: p.getState_Hole(), layer: p.getState_Layer(), prot: p.getState_Rotation() })) };
}
return { n: comps.length, out };
"""
MIL = 0.0254


def pad_size(pad):
    """(w, h) in mm from the API pad descriptor; polygons use their bounding box."""
    kind = pad[0]
    if kind in ("RECT", "OVAL", "ELLIPSE"):
        return pad[1] * MIL, pad[2] * MIL
    if kind == "POLYGON":
        pts = [v for v in pad[1] if isinstance(v, (int, float))]
        xs, ys = pts[0::2], pts[1::2]
        return (max(xs) - min(xs)) * MIL, (max(ys) - min(ys)) * MIL
    return 1.0, 1.0


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result, start = {}, 0
    while True:
        r = run(JS.replace("__PCB__", PCB).replace("__FROM__", str(start)).replace("__TO__", str(start + 25)))
        if not r.get("success"):
            raise SystemExit(r.get("error"))
        n = r["result"]["n"]
        for ref, c in r["result"]["out"].items():
            a = -math.radians(c["rot"] or 0)
            pads = []
            for p in c["pads"]:
                dx, dy = (p["x"] - c["x"]) * MIL, (p["y"] - c["y"]) * MIL
                lx, ly = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
                w, h = pad_size(p["pad"]) if p["pad"] else (0.5, 0.5)
                local_rot = ((p.get("prot") or 0) - (c["rot"] or 0)) % 180
                if p["pad"] and p["pad"][0] != "POLYGON" and abs(local_rot - 90) < 1:
                    w, h = h, w   # pad turned 90 degrees inside its footprint
                # only multi-layer pads (12) are drilled; some library SMD pads keep a leftover hole spec that
                # EasyEDA ignores (the BQ24075 thermal pad), which made fanout skip it as through-hole
                pads.append({"num": p["num"], "net": p["net"], "x": round(lx, 4), "y": round(ly, 4),
                             "w": round(w, 4), "h": round(h, 4), "shape": p["pad"][0] if p["pad"] else None,
                             "hole": p["hole"] if p.get("layer") == 12 else None})
            result[ref] = {"fp": c["fp"], "pads": pads}
        start += 25
        print(f"fetched {min(start, n)}/{n}")
        if start >= n:
            break
    json.dump(result, open("footprints.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
