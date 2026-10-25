"""Read EasyEDA's computed copper fills (the pours' poured copper) as shapely geometry in mm.

python fills.py dump [file.json]   -> fetch every pour's fill pieces from the live PCB into file.json (default fills.json)
python fills.py where X Y [LAYER]  -> which fill piece(s) contain the point (mm), per layer
python fills.py png X0 X1 Y0 Y1 LAYER out.png -> draw one layer's fill over the pads and live tracks/vias in that window

A piece's path is {"complexPolygon": [ring, ring, ...]}: ring = [x0, y0, ("L", x, y, x, y...) | ("ARC", sweep_deg, x, y) ...]
in 10-mil units; the first ring is the outline, the rest are cut-outs. Pieces with fill=false are stroked lines of
width lw (the thermal-relief spokes into through-hole pads), not areas.
"""
import json
import math
import sys

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

MM = 0.0254          # API primitives: mil
FU = 0.254           # fill paths: 10 mil
DUMP = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const out = {};
for (const p of await eda.pcb_PrimitivePoured.getAll()) {
  const pour = await eda.pcb_PrimitivePour.get(p.getState_PourPrimitiveId());
  const name = pour ? pour.getState_PourName() : p.getState_PourPrimitiveId();
  out[name] = { layer: pour ? pour.getState_Layer() : null, net: pour ? pour.getState_Net() : null,
    fills: p.getState_PourFills().map(f => ({ id: f.id, fill: f.fill, lw: f.lineWidth, path: f.path })) };
}
return out;
"""


def ring_points(ring, arc_step_deg=15.0):
    """Flatten one ring (10 mil, with L/ARC commands) to a list of (x, y) mm points."""
    pts = [(ring[0] * FU, ring[1] * FU)]
    i, mode = 2, "L"
    while i < len(ring):
        tok = ring[i]
        if tok in ("L", "ARC", "CARC"):
            mode = tok
            i += 1
            continue
        if mode == "L":
            pts.append((ring[i] * FU, ring[i + 1] * FU))
            i += 2
        else:   # ARC sweep x y: arc from the last point to (x, y) sweeping `sweep` degrees
            sweep, ex, ey = ring[i], ring[i + 1] * FU, ring[i + 2] * FU
            sx, sy = pts[-1]
            th = math.radians(sweep)
            n = max(1, int(abs(sweep) / arc_step_deg))
            c = math.dist((sx, sy), (ex, ey))
            if abs(th) < 1e-6 or c < 1e-9:
                pts.append((ex, ey))
            else:
                r = c / (2 * math.sin(abs(th) / 2))
                mx, my = (sx + ex) / 2, (sy + ey) / 2
                h = math.sqrt(max(r * r - (c / 2) ** 2, 0.0))
                ux, uy = (ex - sx) / c, (ey - sy) / c
                sgn = 1 if (th > 0) == (abs(th) < math.pi) else -1   # centre side for the given sweep direction
                cx, cy = mx - uy * h * sgn, my + ux * h * sgn
                a0 = math.atan2(sy - cy, sx - cx)
                for k in range(1, n):
                    a = a0 + th * k / n
                    pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
                pts.append((ex, ey))
            i += 3
    return pts


def piece_geom(path, fill=True, lw=0.0):
    rings = path["complexPolygon"] if isinstance(path, dict) else path
    if rings and not isinstance(rings[0], list):
        rings = [rings]
    if not fill:   # stroked line (thermal spoke)
        return unary_union([LineString(ring_points(r)).buffer(max(lw * FU / 2, 0.01)) for r in rings if len(r) >= 4])
    polys = [Polygon(ring_points(r)).buffer(0) for r in rings if len(r) >= 6]
    if not polys:
        return Polygon()
    outer = max(polys, key=lambda p: p.area)
    holes = [p for p in polys if p is not outer]
    return outer.difference(unary_union(holes)) if holes else outer


def load(fn="fills.json"):
    d = json.load(open(fn))
    d = d.get("result", d)
    out = {}
    for name, v in d.items():
        out[name] = {"layer": v["layer"], "net": v["net"],
                     "pieces": [piece_geom(f["path"], f.get("fill", True), f.get("lw", 0)) for f in v["fills"]]}
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cmd = sys.argv[1]
    if cmd == "dump":
        from eda import run
        fn = sys.argv[2] if len(sys.argv) > 2 else "fills.json"
        r = run(DUMP, timeout=120)
        json.dump(r["result"], open(fn, "w"))
        for name, v in r["result"].items():
            print(name, "layer", v["layer"], v["net"], len(v["fills"]), "pieces")
    elif cmd == "where":
        from shapely.geometry import Point
        x, y = float(sys.argv[2]), float(sys.argv[3])
        lay = int(sys.argv[4]) if len(sys.argv) > 4 else None
        for name, v in load().items():
            if lay is not None and v["layer"] != lay:
                continue
            hits = [(i, g.area) for i, g in enumerate(v["pieces"]) if g.buffer(1e-3).contains(Point(x, y))]
            print(name, "L%s" % v["layer"], "piece(s) containing point:", [(i, round(a, 2)) for i, a in hits],
                  "| largest piece area", round(max(g.area for g in v["pieces"]), 1))
    elif cmd == "png":
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Circle, Rectangle
        from matplotlib.patches import Polygon as MPoly
        import place_pcb as P
        from eda import run
        x0, x1, y0, y1 = map(float, sys.argv[2:6])
        lay, fn = int(sys.argv[6]), sys.argv[7]
        live = run(r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
return { L: (await eda.pcb_PrimitiveLine.getAll()).map(l => [l.getState_Net(), l.getState_Layer(), l.getState_StartX(), l.getState_StartY(), l.getState_EndX(), l.getState_EndY(), l.getState_LineWidth()]),
         V: (await eda.pcb_PrimitiveVia.getAll()).map(v => [v.getState_Net(), v.getState_X(), v.getState_Y(), v.getState_Diameter()]) };
""")["result"]
        fig, ax = plt.subplots(figsize=(8, 8 * (y1 - y0) / (x1 - x0)), dpi=120)
        cols = ["#2e7d32", "#558b2f", "#00838f", "#6a1b9a", "#ad1457", "#ef6c00", "#4e342e", "#283593"]
        for name, v in load().items():
            if v["layer"] != lay:
                continue
            for i, g in enumerate(v["pieces"]):
                for poly in getattr(g, "geoms", [g]):
                    if poly.is_empty:
                        continue
                    ax.add_patch(MPoly(list(poly.exterior.coords), fc=cols[i % len(cols)], ec="k", lw=0.3, alpha=0.55))
                    for h in poly.interiors:
                        ax.add_patch(MPoly(list(h.coords), fc="#111", ec="none"))
                    c = poly.representative_point()
                    if x0 <= c.x <= x1 and y0 <= c.y <= y1:
                        ax.text(c.x, c.y, str(i), fontsize=6, color="w")
        for r in P.PLACE:
            for p in P.abs_pads(r):
                if lay in (1,) or p.get("hole"):
                    ax.add_patch(Rectangle((p["ax"] - p["aw"] / 2, p["ay"] - p["ah"] / 2), p["aw"], p["ah"], fc="#c8a040", ec="none", alpha=0.6))
        for n, l, a, b, c, d, w in live["L"]:
            if l == lay:
                ax.plot([a * MM, c * MM], [b * MM, d * MM], color="#ff5050", lw=1.0)
        for n, x, y, dia in live["V"]:
            ax.add_patch(Circle((x * MM, y * MM), dia * MM / 2, fc="#ddd" if n != "GND" else "#80ff80", ec="k", lw=0.2))
            if x0 <= x * MM <= x1 and y0 <= y * MM <= y1:
                ax.text(x * MM, y * MM + 0.35, n, fontsize=4, color="w", ha="center")
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect("equal")
        ax.set_facecolor("#111")
        fig.tight_layout()
        fig.savefig(fn)
        print("wrote", fn)


if __name__ == "__main__":
    main()
