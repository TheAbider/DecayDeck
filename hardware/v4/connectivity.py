"""Copper connectivity check: for every net, are all its pads joined by tracks, vias and (for GND/3V3) the inner
planes? Reads the live PCB; independent of the router's own success report.

usage: python connectivity.py [--pours] [NET ...]   -> nets with more than one island, and which pads are in each island
  --pours: use EasyEDA's actual poured copper (all four pours) instead of assuming the inner planes join every
           GND/3V3 via; catches plane islands and pads that only the top/bottom pours reach.
"""
import json
import sys

from shapely import STRtree
from shapely.geometry import LineString, Point, box

from eda import run
from place_pcb import PLACE, abs_pads
from design import PARTS

JS = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const L = (await eda.pcb_PrimitiveLine.getAll()).map(l => [l.getState_Net(), l.getState_Layer(), l.getState_StartX(), l.getState_StartY(), l.getState_EndX(), l.getState_EndY(), l.getState_LineWidth()]);
const V = (await eda.pcb_PrimitiveVia.getAll()).map(v => [v.getState_Net(), v.getState_X(), v.getState_Y(), v.getState_Diameter()]);
return { L, V };
"""
MM = 0.0254
PLANES = {"GND", "3V3"}     # Inner1 / Inner2: every via and TH pad on these nets is joined by the plane


def main(only, pours=False):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    r = run(JS)
    if not r.get("success"):
        raise SystemExit(r.get("error"))
    lines, vias = r["result"]["L"], r["result"]["V"]
    nodes = []   # (net, layers, geometry, label)
    if pours:
        import fills
        poured = run(fills.DUMP, timeout=120)["result"]
        if not any(v["fills"] for v in poured.values()):
            raise SystemExit("no poured copper: rebuild the pours first")
        for v in poured.values():
            for f in v["fills"]:
                g = fills.piece_geom(f["path"], f["fill"], f["lw"])
                if not g.is_empty:
                    nodes.append((v["net"], {v["layer"]}, g, None))
    for ref in PLACE:
        if ref not in PARTS:
            continue
        for p in abs_pads(ref):
            if not p["net"]:
                continue
            g = box(p["ax"] - p["aw"] / 2, p["ay"] - p["ah"] / 2, p["ax"] + p["aw"] / 2, p["ay"] + p["ah"] / 2)
            lay = {1, 2, 15, 16} if p.get("hole") else {1}
            nodes.append((p["net"], lay, g, f"{ref}.{p['num']}"))
    for n, lay, x1, y1, x2, y2, w in lines:
        g = LineString([(x1 * MM, y1 * MM), (x2 * MM, y2 * MM)]).buffer(max(w * MM / 2, 0.01))
        nodes.append((n, {lay}, g, None))
    for n, x, y, d in vias:
        nodes.append((n, {1, 2, 15, 16}, Point(x * MM, y * MM).buffer(d * MM / 2), "via"))
    parent = list(range(len(nodes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_net = {}
    for i, nd in enumerate(nodes):
        by_net.setdefault(nd[0], []).append(i)
    bad = 0
    for net, idx in sorted(by_net.items()):
        if only and net not in only:
            continue
        tree = STRtree([nodes[i][2] for i in idx])
        for a, i in enumerate(idx):
            for b in tree.query(nodes[i][2], predicate="intersects"):
                j = idx[b]
                if b > a and nodes[i][1] & nodes[j][1]:
                    parent[find(i)] = find(j)
        if net in PLANES and not pours:   # assume the plane layer joins everything that reaches it
            plane = [i for i in idx if (15 in nodes[i][1] or 16 in nodes[i][1])]
            for i in plane[1:]:
                parent[find(i)] = find(plane[0])
        islands = {}
        for i in idx:
            if nodes[i][3] and nodes[i][3] != "via":
                islands.setdefault(find(i), []).append(nodes[i][3])
        if len(islands) > 1:
            bad += 1
            print(f"{net}: {len(islands)} islands: " + " | ".join(" ".join(sorted(v)) for v in islands.values()))
    print(f"{bad} nets not fully connected")
    return 1 if bad else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    sys.exit(main({a for a in args if a != "--pours"}, pours="--pours" in args))
