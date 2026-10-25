"""Plane fanout: drop a via next to every top-side SMD pad on a plane net (GND -> Inner1, 3V3 -> Inner2)
and join it to the pad with a short track. Candidate spots are tested against every other pad, track and
via with shapely; thermal pads get vias inside the pad.

usage: python fanout.py plan   -> fanout.json + fanout.png (nothing sent to EasyEDA)
       python fanout.py push   -> create the tracks and vias in EasyEDA
"""
import json
import math
import sys

from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

from place_pcb import ANTENNA_KEEPOUT, BOARD, HOLES, HOLE_KEEPOUT_R, HV_NETS, PLACE, abs_pads
from design import PARTS

PLANE_NETS = {"GND", "3V3"}
VIA_D, VIA_HOLE = 0.6, 0.3
TRACK_W = 0.3
CLEAR = 0.2                # copper to other-net copper
HV_CLEAR = 2.5
NO_VIA_PADS = set()
THERMAL = {  # ref, pad -> via offsets (mm) from the pad centre (applied to every copy of a split pad)
    ("U2", "17"): [(-0.45, -0.45), (0.45, -0.45), (-0.45, 0.45), (0.45, 0.45)],   # BQ24075 thermal pad
    ("U1", "41"): [(0.0, 0.0)],                                                  # WROOM EPAD, 9 sub-pads
    ("U4", "9"): [(0.0, 0.0)],                                                   # MAX17048 EP
    ("U8", "7"): [(0.0, 0.0)],                                                   # OPT3001 EP
}
FAR = {("Q3", "2"), ("C24", "2"), ("C26", "2"), ("C27", "2"), ("D7", "2"), ("R60", "2")}   # GND pads beside HV copper
BRIDGES = {("U3", "2"): ("U3", "3")}   # boxed-in plane pad -> same-net neighbour pad that has a via (TPS63802 MODE->AGND)
REUSE_R = 1.8                          # join an already planned same-net via this close instead of adding one
SKIP_REFS = set()


def pad_shape(p, grow=0.0):
    return box(p["ax"] - p["aw"] / 2 - grow, p["ay"] - p["ah"] / 2 - grow,
               p["ax"] + p["aw"] / 2 + grow, p["ay"] + p["ah"] / 2 + grow)


def main(mode):
    pads = [(r, p) for r in PLACE if r in PARTS for p in abs_pads(r)]
    obstacles = []  # (net, geometry, ref)
    for r, p in pads:
        obstacles.append((p["net"] or "", pad_shape(p), r))
    for hx, hy in HOLES.values():
        obstacles.append(("#HOLE", Point(hx, hy).buffer(HOLE_KEEPOUT_R), None))
    obstacles.append(("#KEEPOUT", box(*ANTENNA_KEEPOUT), None))      # no copper under the module's antenna
    ux, uy, _ = PLACE["U1"]                                            # no vias under the module body: only
    obstacles.append(("#U1BODY", box(ux - 7.5, uy - 9.0, ux + 7.5, uy + 8.1), None))   # its EPAD vias (THERMAL)
    edge = box(*BOARD).buffer(-0.6)
    planned = []   # dicts: {net, via:(x,y), track:[x1,y1,x2,y2] or None}
    placed_geo = []  # (net, geometry)

    def blocked(net, geo, own=None):
        if not edge.contains(geo):
            return True
        for onet, og, oref in obstacles + placed_geo:
            if onet == net or (own is not None and oref == own and onet in HV_NETS):
                continue   # a part's own HV pads sit at footprint spacing already
            need = HV_CLEAR if (onet in HV_NETS) else CLEAR
            if onet == "#HOLE":
                need = 0.0
            if geo.distance(og) < need:
                return True
        return False

    misses = []
    for r, p in pads:
        net = p["net"] or ""
        if net not in PLANE_NETS or r in SKIP_REFS:
            continue
        key = (r, p["num"])
        if key in THERMAL:   # before the hole test: a listed thermal pad must never be skipped
            for dx, dy in THERMAL[key]:
                v = (p["ax"] + dx, p["ay"] + dy)
                planned.append({"ref": r, "pad": p["num"], "net": net, "via": v, "track": None})
                placed_geo.append((net, Point(v).buffer(VIA_D / 2), r))
            continue
        if p.get("hole"):
            continue   # through-hole pad already reaches the planes
        if key in NO_VIA_PADS:
            continue
        if key in BRIDGES:
            q = next(q for rr, q in pads if (rr, q["num"]) == BRIDGES[key])
            planned.append({"ref": r, "pad": p["num"], "net": net, "via": None,
                            "track": [p["ax"], p["ay"], q["ax"], q["ay"]], "w": 0.25})
            continue
        reuse = None
        for v in planned:
            if v["net"] == net and v["via"] and math.dist(v["via"], (p["ax"], p["ay"])) <= REUSE_R:
                trk = LineString([(p["ax"], p["ay"]), v["via"]]).buffer(TRACK_W / 2)
                if not blocked(net, trk, own=r if key in FAR else None):
                    reuse = v["via"]
                    break
        if reuse:
            planned.append({"ref": r, "pad": p["num"], "net": net, "via": None,
                            "track": [p["ax"], p["ay"], reuse[0], reuse[1]]})
            placed_geo.append((net, LineString([(p["ax"], p["ay"]), reuse]).buffer(TRACK_W / 2), r))
            continue
        # try spots around the pad, nearest first
        cx, cy = p["ax"], p["ay"]
        best = None
        for dist in ((0.55, 0.75, 1.0, 1.3, 1.7, 2.2) + ((2.8, 3.4, 4.0, 4.8) if key in FAR else ())):
            for ang in range(0, 360, 15):
                a = math.radians(ang)
                ex = p["aw"] / 2 * abs(math.cos(a)) + p["ah"] / 2 * abs(math.sin(a))
                d = ex + dist
                vx, vy = cx + d * math.cos(a), cy + d * math.sin(a)
                via = Point(vx, vy).buffer(VIA_D / 2)
                trk = LineString([(cx, cy), (vx, vy)]).buffer(TRACK_W / 2)
                if blocked(net, via) or blocked(net, trk, own=r if key in FAR else None):
                    continue
                best = (vx, vy)
                break
            if best:
                break
        if not best:
            misses.append(f"{r}.{p['num']} ({net})")
            continue
        planned.append({"ref": r, "pad": p["num"], "net": net, "via": best, "track": [cx, cy, best[0], best[1]]})
        placed_geo.append((net, Point(best).buffer(VIA_D / 2), r))
        placed_geo.append((net, LineString([(cx, cy), best]).buffer(TRACK_W / 2), r))
    json.dump(planned, open("fanout.json", "w"), indent=1)
    nv = sum(1 for v in planned if v["via"])
    print(f"{nv} vias + {len(planned) - nv} shared/bridged pads planned, {len(misses)} pads without a spot: {misses}")
    if mode == "push":
        push(planned)
    else:
        render(planned)


def render(planned):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle
    fig, ax = plt.subplots(figsize=(9, 14), dpi=110)
    for r in PLACE:
        if r not in PARTS:
            continue
        for p in abs_pads(r):
            col = "#ff3030" if (p["net"] or "") in HV_NETS else ("#888" if p["net"] == "GND" else ("#3399ff" if p["net"] == "3V3" else "#e0b030"))
            ax.add_patch(Rectangle((p["ax"] - p["aw"] / 2, p["ay"] - p["ah"] / 2), p["aw"], p["ah"], fc=col, ec="none"))
    for v in planned:
        col = "#ffffff" if v["net"] == "GND" else "#00e5ff"
        if v["track"]:
            ax.plot([v["track"][0], v["track"][2]], [v["track"][1], v["track"][3]], color=col, lw=0.8)
        if v["via"]:
            ax.add_patch(Circle(v["via"], VIA_D / 2, fc=col, ec="k", lw=0.3))
    ax.set_xlim(BOARD[0] - 1, BOARD[2] + 1)
    ax.set_ylim(BOARD[1] - 1, BOARD[3] + 1)
    ax.set_aspect("equal")
    ax.set_facecolor("#1b2b1b")
    fig.tight_layout()
    fig.savefig("fanout.png")


def push(planned):
    from eda import run
    mil = 1 / 0.0254
    items = [{"net": v["net"], "v": [v["via"][0] * mil, v["via"][1] * mil] if v["via"] else None,
              "t": [c * mil for c in v["track"]] if v["track"] else None, "w": v.get("w", TRACK_W) * mil}
             for v in planned]
    js = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
let nv = 0, nt = 0;
for (const it of __ITEMS__) {
  if (it.v) { const v = await eda.pcb_PrimitiveVia.create(it.net, it.v[0], it.v[1], 11.811, 23.622); if (v) nv++; }
  if (it.t) { const t = await eda.pcb_PrimitiveLine.create(it.net, 1, it.t[0], it.t[1], it.t[2], it.t[3], it.w); if (t) nt++; }
}
return [nv, nt];
"""
    for i in range(0, len(items), 40):
        r = run(js.replace("__ITEMS__", json.dumps(items[i:i + 40])))
        print("created", r.get("result"), r.get("error") or "")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main(sys.argv[1])
