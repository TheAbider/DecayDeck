"""DRC round 1 fixes (2026-10-25):
- 3 duplicate mounting holes left by an earlier setup_board.py run (its id filter missed them): delete the stale three.
- HV_DRV: the router squeezed it between Q3's collector (HV_SW) and base, 0.89 mm from 200 V. Replace that detour
  with C20.1 -> via -> bottom layer -> via -> U10.4, clear of the HV copper.
- U3 MODE->AGND bridge: 0.25 mm violates the power-class 0.3 mm minimum; widen to 0.3 mm.

usage: python fix_drc1.py check | apply
"""
import json
import sys

from shapely.geometry import LineString, Point, box

from eda import run
from place_pcb import HV_NETS, PLACE, abs_pads
from design import PARTS

MM = 0.0254
STALE_HOLES = ["d2a30d33cce23da0", "4c789b2539bd99d9", "ddc8640d846b261b"]   # duplicates at MH2, MH3, MH4
DETOUR = ["b5411ea281f11111", "8e11825a0dd5183f", "5d5728d316e48bc5", "c08939af77b6299f"]   # HV_DRV through Q3
VIA_A, VIA_B = (-19.3, -3.95), (-15.3, -0.55)
NEW_TRACKS = [   # (layer, w mm, points)
    (1, 0.25, [(-19.3, -2.6), VIA_A]),
    (2, 0.25, [VIA_A, (-17.6, -2.25), VIA_B]),
    (1, 0.25, [VIA_B, (-14.3, -1.05)]),
]
BRIDGE = ((15.5, -24.83), (16.0, -24.83))
LIVE = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
return { L: (await eda.pcb_PrimitiveLine.getAll()).map(l => [l.getState_PrimitiveId(), l.getState_Net(), l.getState_Layer(), l.getState_StartX(), l.getState_StartY(), l.getState_EndX(), l.getState_EndY(), l.getState_LineWidth()]),
         V: (await eda.pcb_PrimitiveVia.getAll()).map(v => [v.getState_Net(), v.getState_X(), v.getState_Y(), v.getState_Diameter()]) };
"""


def check(live):
    obstacles = []   # (net, layers, geometry, label, smd_pad)
    for ref in PLACE:
        if ref not in PARTS:
            continue
        for p in abs_pads(ref):
            g = box(p["ax"] - p["aw"] / 2, p["ay"] - p["ah"] / 2, p["ax"] + p["aw"] / 2, p["ay"] + p["ah"] / 2)
            obstacles.append((p["net"] or "", {1, 2} if p.get("hole") else {1}, g, f"{ref}.{p['num']}", not p.get("hole")))
    for pid, n, lay, a, b, c, d, w in live["L"]:
        if pid in DETOUR:
            continue
        obstacles.append((n, {lay}, LineString([(a * MM, b * MM), (c * MM, d * MM)]).buffer(w * MM / 2), f"track {n}", False))
    for n, x, y, dia in live["V"]:
        obstacles.append((n, {1, 2}, Point(x * MM, y * MM).buffer(dia * MM / 2), f"via {n}", False))
    new = [(lay, LineString(pts).buffer(w / 2)) for lay, w, pts in NEW_TRACKS]
    new += [(lay, Point(v).buffer(0.3)) for v in (VIA_A, VIA_B) for lay in (1, 2)]
    ok = True
    for lay, g in new:
        worst = min(((g.distance(og), lbl, n, smd) for n, ls, og, lbl, smd in obstacles if n != "HV_DRV" and lay in ls),
                    key=lambda t: t[0] - (2.5 if t[2] in HV_NETS and not t[3] else 1.5 if t[2] in HV_NETS else 0.2))
        need = (2.5 if worst[2] in HV_NETS and not worst[3] else 1.5 if worst[2] in HV_NETS else 0.2)
        print(f"layer {lay}: closest {worst[1]} at {worst[0]:.3f} mm (needs {need})")
        ok &= worst[0] >= need
    return ok


def apply(live):
    bridge = [l[0] for l in live["L"] if l[1] == "GND" and l[2] == 1 and
              {(round(l[3] * MM, 2), round(l[4] * MM, 2)), (round(l[5] * MM, 2), round(l[6] * MM, 2))} == set(BRIDGE)]
    assert len(bridge) == 1, bridge
    mil = 1 / MM
    js = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const holes = [];
for (const id of __HOLES__) { const p = await eda.pcb_PrimitivePad.get(id); if (p && !p.getState_Net()) holes.push(id); }
const dh = holes.length ? await eda.pcb_PrimitivePad.delete(holes) : false;
const dt = await eda.pcb_PrimitiveLine.delete(__DETOUR__);
let nt = 0, nv = 0;
for (const v of __VIAS__) { if (await eda.pcb_PrimitiveVia.create('HV_DRV', v[0], v[1], 11.811, 23.622)) nv++; }
for (const t of __TRACKS__) for (let i = 0; i + 1 < t.pts.length; i++)
  if (await eda.pcb_PrimitiveLine.create('HV_DRV', t.lay, t.pts[i][0], t.pts[i][1], t.pts[i + 1][0], t.pts[i + 1][1], t.w)) nt++;
const b = await eda.pcb_PrimitiveLine.get('__BRIDGE__');
const bw = b ? await eda.pcb_PrimitiveLine.modify('__BRIDGE__', { lineWidth: 11.811 }) : null;
return { holesDeleted: holes, dh, detourDeleted: dt, vias: nv, tracks: nt, bridgeWidened: !!bw };
"""
    js = (js.replace("__HOLES__", json.dumps(STALE_HOLES)).replace("__DETOUR__", json.dumps(DETOUR))
          .replace("__VIAS__", json.dumps([[x * mil, y * mil] for x, y in (VIA_A, VIA_B)]))
          .replace("__TRACKS__", json.dumps([{"lay": lay, "w": w * mil, "pts": [[x * mil, y * mil] for x, y in pts]} for lay, w, pts in NEW_TRACKS]))
          .replace("__BRIDGE__", bridge[0]))
    print(run(js))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    live = run(LIVE)["result"]
    ok = check(live)
    print("PASS" if ok else "FAIL")
    if sys.argv[1] == "apply":
        if not ok:
            raise SystemExit("not applied")
        apply(live)
