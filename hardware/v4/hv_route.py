"""Hand-routed HV copper (top layer). EasyEDA's router only joins pads that touch when the HV class asks 2.5 mm,
so every HV connection the router left open is written out here as straight / 45-degree segments and checked
against all other-net copper before it is sent: tracks, vias, through-hole pads, holes and the board edge 2.5 mm
(IPC-2221B B2, 301-500 V), SMD pads 1.5 mm (A7).

usage: python hv_route.py check   -> clearance report, nothing sent
       python hv_route.py push    -> check, then create the tracks (refuses if any check fails)
"""
import sys

from shapely.geometry import LineString, Point, box

from eda import run
from place_pcb import BOARD, HOLES, HV_NETS, PLACE, abs_pads
from design import PARTS

ROUTES = [   # (net, width mm, [points])
    ("HV_SW", 0.5, [(-21.25, 2.6), (-23.5, 2.6)]),       # Q3 collector (outer end of its pad, away from E/B) -> L2
    ("HV_SW", 0.5, [(-23.5, 7.4), (-19.0, 7.4), (-17.6, 8.8), (-17.6, 11.81)]),      # D4 anode -> pump cap C25
    ("HV_V1", 0.4, [(-27.01, 13.2), (-23.5, 13.2)]),                                 # C24 -> D4/D5
    ("HV_M", 0.4, [(-17.6, 14.99), (-17.6, 17.4), (-19.4, 19.2), (-19.4, 21.6)]),    # C25 -> D6 anode
    ("HV_OUT", 0.4, [(-12.89, 21.6), (-12.89, 32.48)]),                              # output stack -> top
    ("HV_OUT", 0.4, [(-12.89, 26.0), (-15.32, 26.0)]),                               # -> R40 (SI-3BG chain)
    ("HV_OUT", 0.4, [(-15.32, 32.48), (0.6, 32.48)]),                                # -> R35, R30 divider, R58 bleeder
    ("HV_D1", 0.4, [(-4.0, 29.52), (-4.0, 27.48)]),
    ("HV_D2", 0.4, [(-4.0, 24.52), (-4.0, 22.48)]),
    ("HV_B1", 0.4, [(0.6, 29.52), (0.6, 27.48)]),
    ("HV_B2", 0.4, [(0.6, 24.52), (0.6, 22.48)]),
    ("GM1_ANODE", 0.4, [(-28.6, 32.4), (-23.88, 32.4)]),
    ("GM1_AM", 0.4, [(-20.92, 32.4), (-18.28, 32.4)]),
    ("GM2_ANODE", 0.4, [(-28.6, 26.0), (-23.88, 26.0)]),
    ("GM2_AM", 0.4, [(-20.92, 26.0), (-18.28, 26.0)]),
]
HV_TRACK = 2.5
HV_SMD = 1.5
MM = 0.0254
FETCH = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
return { L: (await eda.pcb_PrimitiveLine.getAll()).map(l => [l.getState_Net(), l.getState_Layer(), l.getState_StartX(), l.getState_StartY(), l.getState_EndX(), l.getState_EndY(), l.getState_LineWidth()]),
         V: (await eda.pcb_PrimitiveVia.getAll()).map(v => [v.getState_Net(), v.getState_X(), v.getState_Y(), v.getState_Diameter()]) };
"""


def check():
    live = run(FETCH)["result"]
    obstacles = []   # (net, geometry, required clearance to HV copper, label)
    for ref in PLACE:
        if ref not in PARTS:
            continue
        for p in abs_pads(ref):
            g = box(p["ax"] - p["aw"] / 2, p["ay"] - p["ah"] / 2, p["ax"] + p["aw"] / 2, p["ay"] + p["ah"] / 2)
            obstacles.append((p["net"] or "", g, HV_TRACK if p.get("hole") else HV_SMD, f"{ref}.{p['num']}"))
    for n, lay, x1, y1, x2, y2, w in live["L"]:
        if lay == 1:
            obstacles.append((n, LineString([(x1 * MM, y1 * MM), (x2 * MM, y2 * MM)]).buffer(w * MM / 2), HV_TRACK, f"track {n}"))
    for n, x, y, d in live["V"]:
        obstacles.append((n, Point(x * MM, y * MM).buffer(d * MM / 2), HV_TRACK, f"via {n}"))
    for h, (hx, hy) in HOLES.items():
        obstacles.append(("#HOLE", Point(hx, hy).buffer(1.35), HV_TRACK, h))
    edge = box(*BOARD).exterior
    worst, bad = {}, []
    for net, w, pts in ROUTES:
        assert net in HV_NETS, net
        g = LineString(pts).buffer(w / 2)
        for onet, og, need, label in obstacles:
            if onet == net:
                continue
            d = g.distance(og)
            if d < worst.get(net, (99,))[0]:
                worst[net] = (d, label, need)
            if d < need:
                bad.append(f"{net} {pts[0]}..{pts[-1]}: {d:.3f} mm to {label} (needs {need})")
        de = g.distance(edge)
        if de < HV_TRACK:
            bad.append(f"{net}: {de:.3f} mm to the board edge")
    for net, (d, label, need) in sorted(worst.items()):
        print(f"{net:10} closest other-net copper {d:.3f} mm ({label}, rule {need})")
    for b in bad:
        print("FAIL", b)
    return not bad


def push():
    items = [{"net": n, "w": w / MM, "pts": [[x / MM, y / MM] for x, y in pts]} for n, w, pts in ROUTES]
    js = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
let n = 0;
for (const it of __ITEMS__) for (let i = 0; i + 1 < it.pts.length; i++) {
  const t = await eda.pcb_PrimitiveLine.create(it.net, 1, it.pts[i][0], it.pts[i][1], it.pts[i + 1][0], it.pts[i + 1][1], it.w);
  if (t) n++;
}
return n;
"""
    import json
    print("segments created:", run(js.replace("__ITEMS__", json.dumps(items))).get("result"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ok = check()
    print("PASS" if ok else "FAIL")
    if sys.argv[1] == "push":
        if not ok:
            raise SystemExit("not pushed")
        push()
