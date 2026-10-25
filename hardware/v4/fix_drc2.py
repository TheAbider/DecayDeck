"""DRC round 2 fixes (2026-10-25), once the pours were filled:
- U2 (BQ24075) thermal pad had no vias, so it was unconnected and had no heat path. Its library footprint keeps a
  leftover hole spec on that top-layer SMD pad; fanout.py took it for a through-hole pad and skipped it, and the
  router then ran BQ_EN2 and BQ_ILIM diagonally under it on the bottom layer. Rip up those two nets, put the
  planned 2x2 thermal vias in the pad, re-route the two nets with the autorouter.
- USB-C GND pins A1B12 / B1A12 reached ground through one 0.25 mm pour spoke each. Tie each to the shell pad
  beside it (plated slot, straight into both inner planes) with a 0.5 mm track.

usage: python fix_drc2.py check | apply
"""
import json
import sys

from shapely.geometry import LineString, Point, box

from eda import run
from place_pcb import HV_NETS, PLACE, abs_pads
from design import PARTS

MM = 0.0254
RIP_NETS = ["BQ_EN2", "BQ_ILIM"]
VIA_D = 0.6
EP = next(p for p in abs_pads("U2") if p["num"] == "17")
EP_VIAS = [(EP["ax"] + dx, EP["ay"] + dy) for dx in (-0.45, 0.45) for dy in (-0.45, 0.45)]
J1 = {p["num"]: p for p in abs_pads("J1")}
LINK_Y = -62.95   # inside both the USB pin and the shell pad
LINKS = [(0.5, [(J1["A1B12"]["ax"], LINK_Y), (J1["4"]["ax"], LINK_Y)]),
         (0.5, [(J1["B1A12"]["ax"], LINK_Y), (J1["1"]["ax"], LINK_Y)])]
CLEAR = 0.2
BACKUP = "fix_drc2_ripped.json"   # what apply removed, to restore by hand if ever needed
LIVE = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
return { L: (await eda.pcb_PrimitiveLine.getAll()).map(l => [l.getState_PrimitiveId(), l.getState_Net(), l.getState_Layer(), l.getState_StartX(), l.getState_StartY(), l.getState_EndX(), l.getState_EndY(), l.getState_LineWidth()]),
         V: (await eda.pcb_PrimitiveVia.getAll()).map(v => [v.getState_PrimitiveId(), v.getState_Net(), v.getState_X(), v.getState_Y(), v.getState_HoleDiameter(), v.getState_Diameter()]) };
"""


def check(live):
    obstacles = []   # (net, layers, geometry, label)
    for ref in PLACE:
        if ref not in PARTS:
            continue
        for p in abs_pads(ref):
            g = box(p["ax"] - p["aw"] / 2, p["ay"] - p["ah"] / 2, p["ax"] + p["aw"] / 2, p["ay"] + p["ah"] / 2)
            obstacles.append((p["net"] or "", {1, 2} if p.get("hole") else {1}, g, f"{ref}.{p['num']}"))
    for pid, n, lay, a, b, c, d, w in live["L"]:
        if n not in RIP_NETS:
            obstacles.append((n, {lay}, LineString([(a * MM, b * MM), (c * MM, d * MM)]).buffer(w * MM / 2), f"track {n}"))
    for pid, n, x, y, hole, dia in live["V"]:
        if n not in RIP_NETS:
            obstacles.append((n, {1, 2}, Point(x * MM, y * MM).buffer(dia * MM / 2), f"via {n}"))
    new = [(f"EP via {v}", {1, 2}, Point(v).buffer(VIA_D / 2)) for v in EP_VIAS]
    new += [(f"J1 link {pts}", {1}, LineString(pts).buffer(w / 2)) for w, pts in LINKS]
    ok = True
    for label, lays, g in new:
        d, lbl, net = min((g.distance(og), olbl, n) for n, ls, og, olbl in obstacles if n != "GND" and lays & ls)
        need = 2.5 if net in HV_NETS else CLEAR
        print(f"{label}: closest other-net copper {lbl} at {d:.3f} mm (needs {need})")
        ok &= d >= need
    inside = all(box(EP["ax"] - EP["aw"] / 2, EP["ay"] - EP["ah"] / 2, EP["ax"] + EP["aw"] / 2, EP["ay"] + EP["ah"] / 2)
                 .contains(Point(v).buffer(VIA_D / 2)) for v in EP_VIAS)
    print("EP vias inside the thermal pad:", inside)
    rip = [l for l in live["L"] if l[1] in RIP_NETS], [v for v in live["V"] if v[1] in RIP_NETS]
    print(f"to rip up: {len(rip[0])} track segments, {len(rip[1])} vias on {RIP_NETS}")
    return ok and inside, rip


def apply(rip):
    json.dump({"lines": rip[0], "vias": rip[1]}, open(BACKUP, "w"))
    print("ripped-up copper saved to", BACKUP)
    mil = 1 / MM
    js = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const dl = __LINES__.length ? await eda.pcb_PrimitiveLine.delete(__LINES__) : true;
const dv = __VIAS__.length ? await eda.pcb_PrimitiveVia.delete(__VIAS__) : true;
let nv = 0, nt = 0;
for (const v of __EPV__) { if (await eda.pcb_PrimitiveVia.create('GND', v[0], v[1], 11.811, 23.622)) nv++; }
for (const t of __LINKS__) { if (await eda.pcb_PrimitiveLine.create('GND', 1, t.p[0][0], t.p[0][1], t.p[1][0], t.p[1][1], t.w)) nt++; }
return { linesDeleted: dl, viasDeleted: dv, epVias: nv, links: nt };
"""
    js = (js.replace("__LINES__", json.dumps([l[0] for l in rip[0]])).replace("__VIAS__", json.dumps([v[0] for v in rip[1]]))
          .replace("__EPV__", json.dumps([[x * mil, y * mil] for x, y in EP_VIAS]))
          .replace("__LINKS__", json.dumps([{"w": w * mil, "p": [[x * mil, y * mil] for x, y in pts]} for w, pts in LINKS])))
    print(run(js, retry_on_drop=False))
    import route
    route.route({"RoutingNets": RIP_NETS, "layers": [1, 2]})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ok, rip = check(run(LIVE)["result"])
    print("PASS" if ok else "FAIL")
    if sys.argv[1] == "apply":
        if not ok:
            raise SystemExit("not applied")
        apply(rip)
