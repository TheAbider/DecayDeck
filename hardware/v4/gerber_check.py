"""Check the copper JLC will etch: draw the four copper layers from the Gerber zip (25 um pixels), join them through
the plated holes, and look up every pad of the flying-probe netlist that ships in the same zip. Each net must be one
piece of copper (else OPEN), no piece may carry two nets (else SHORT), and the netlist must match design.py pin for
pin. It reads only the files that get uploaded, so it doesn't trust EasyEDA's export any more than its connectivity.

usage: python gerber_check.py [ZIP] [--open NET] [--short NET_A NET_B] [--no-vias]
The three options damage the copper on purpose: each must make the check fail, which proves it can.
The export renames any net name longer than 10 characters to NET_<n> (PWR_BTN_SNS): same pins, reported as renamed.
"""
import json
import math
import re
import sys
import zipfile

import cv2
import numpy as np

from check_spec import resolved_nets

ZIP = "fab/2026-10-25/DecayDeck_v4_Gerber.zip"
S = 40                      # pixels per mm (25 um); the tightest copper gap on the board is 0.15 mm
X0, Y1 = -34.0, 43.0        # raster origin: the board is -33..33 x -69..42 mm, plus 1 mm
W, H = 68 * S, 113 * S
SH = 4                      # cv2 fixed point: 1/16 px
LAYERS = ["Gerber_TopLayer.GTL", "Gerber_InnerLayer1.G1", "Gerber_InnerLayer2.G2", "Gerber_BottomLayer.GBL"]
MIL = 0.0254


def px(x, y):
    return int(round((x - X0) * S * 16)), int(round((Y1 - y) * S * 16))


def r16(mm):
    return int(round(mm * S * 16))


def arc_points(x0, y0, x1, y1, i, j, cw):
    cx, cy = x0 + i, y0 + j
    r = math.hypot(x0 - cx, y0 - cy)
    a0, a1 = math.atan2(y0 - cy, x0 - cx), math.atan2(y1 - cy, x1 - cx)
    if cw and a1 >= a0 - 1e-12:
        a1 -= 2 * math.pi
    elif not cw and a1 <= a0 + 1e-12:
        a1 += 2 * math.pi
    n = max(4, math.ceil(abs(a1 - a0) * r / 0.02))
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(1, n + 1)]


def render(src):
    """One copper layer as a 0/255 image. Handles what EasyEDA Pro writes: C/R/O apertures, outline macros, tracks,
    flashes and G36 regions (pour holes are cut-ins, so there is no clear polarity); anything else stops the check."""
    img = np.zeros((H, W), np.uint8)
    assert "%MOMM*%" in src and "%LPC" not in src, "expected millimetres and no clear polarity"
    div = 10 ** int(re.search(r"%FSLAX\d(\d)Y\d\d\*%", src).group(1))
    macros = {}
    for name, body in re.findall(r"%AM([^*]+)\*([^%]*)%", src):
        macros[name] = []
        for prim in filter(None, (p.strip() for p in body.split("*"))):
            v = [float(t) for t in prim.split(",")]
            assert v[0] == 4, f"macro {name}: only outline primitives are handled"
            n = int(v[2])
            rot = math.radians(v[5 + 2 * n])
            macros[name].append([(u * math.cos(rot) - w * math.sin(rot), u * math.sin(rot) + w * math.cos(rot))
                                 for u, w in zip(v[3:5 + 2 * n:2], v[4:5 + 2 * n:2])])
    aps = {int(num): (kind, [float(t) for t in params.split("X")] if params else [])
           for num, kind, params in re.findall(r"%ADD(\d+)([A-Za-z_][A-Za-z_0-9]*),?([^*]*)\*%", src)}
    x = y = 0.0
    ap, interp, region, contour = None, "G01", False, []

    def fill(points):
        cv2.fillPoly(img, [np.array([px(*p) for p in points], np.int32)], 255, cv2.LINE_8, SH)

    def stroke(pts):
        kind, p = aps[ap]
        assert kind == "C", f"draw with a {kind} aperture"
        for a, b in zip(pts, pts[1:]):
            cv2.line(img, px(*a), px(*b), 255, max(1, round(p[0] * S)), cv2.LINE_8, SH)
        for a in (pts[0], pts[-1]):
            cv2.circle(img, px(*a), r16(p[0] / 2), 255, -1, cv2.LINE_8, SH)

    def flash(cx, cy):
        kind, p = aps[ap]
        if kind == "C":
            cv2.circle(img, px(cx, cy), r16(p[0] / 2), 255, -1, cv2.LINE_8, SH)
        elif kind == "R":
            w, h = p[0] / 2, p[1] / 2
            fill([(cx - w, cy - h), (cx + w, cy - h), (cx + w, cy + h), (cx - w, cy + h)])
        elif kind == "O":
            r = min(p) / 2
            a, b = ((cx - p[0] / 2 + r, cy), (cx + p[0] / 2 - r, cy)) if p[0] >= p[1] else ((cx, cy - p[1] / 2 + r), (cx, cy + p[1] / 2 - r))
            cv2.line(img, px(*a), px(*b), 255, max(1, round(2 * r * S)), cv2.LINE_8, SH)
            for q in (a, b):
                cv2.circle(img, px(*q), r16(r), 255, -1, cv2.LINE_8, SH)
        elif kind in macros:
            for poly in macros[kind]:
                fill([(cx + u, cy + w) for u, w in poly])
        else:
            raise SystemExit(f"flash with aperture {kind}")

    for stmt in re.sub(r"%[^%]*%", "", src).split("*"):
        stmt = stmt.strip()
        if not stmt or stmt.startswith("G04") or stmt in ("G75", "M02"):
            continue
        if stmt in ("G36", "G37"):
            if stmt == "G37" and len(contour) >= 3:
                fill(contour)
            region, contour = stmt == "G36", []
            continue
        d = re.fullmatch(r"(?:G54)?D(\d+)", stmt)
        if d and int(d.group(1)) >= 10:
            ap = int(d.group(1))
            continue
        m = re.fullmatch(r"(G0[123])?(?:X(-?\d+))?(?:Y(-?\d+))?(?:I(-?\d+))?(?:J(-?\d+))?(D0[123])?", stmt)
        if not m:
            raise SystemExit(f"unhandled Gerber statement: {stmt[:60]}")
        g, sx, sy, si, sj, op = m.groups()
        interp = g or interp
        nx = int(sx) / div if sx else x
        ny = int(sy) / div if sy else y
        if op == "D02" and region:
            if len(contour) >= 3:
                fill(contour)
            contour = [(nx, ny)]
        elif op == "D01":
            pts = [(nx, ny)] if interp == "G01" else arc_points(x, y, nx, ny, int(si or 0) / div, int(sj or 0) / div, interp == "G02")
            if region:
                contour = (contour or [(x, y)]) + pts
            else:
                stroke([(x, y)] + pts)
        elif op == "D03":
            flash(nx, ny)
        x, y = nx, ny
    return img


def drills(src):
    """Excellon holes as (start, end, diameter): end == start except for G85 slots."""
    tools, cur, holes = {}, None, []
    for line in src.splitlines():
        line = line.strip()
        if t := re.fullmatch(r"T(\d+)C([\d.]+)", line):
            tools[int(t.group(1))] = float(t.group(2))
        elif t := re.fullmatch(r"T(\d+)", line):
            cur = int(t.group(1))
        elif h := re.fullmatch(r"X(-?[\d.]+)Y(-?[\d.]+)(?:G85X(-?[\d.]+)Y(-?[\d.]+))?", line):
            a = (float(h.group(1)), float(h.group(2)))
            holes.append((a, (float(h.group(3)), float(h.group(4))) if h.group(3) else a, tools[cur]))
    return holes


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    z = zipfile.ZipFile(args[0] if args and not args[0].startswith("--") else ZIP)
    probe = json.loads(z.read("FlyingProbeTesting.json"))
    assert probe["lengthUnit"] == "mil"
    pins = [dict(zip(probe["pins"]["fields"], r)) for r in probe["pins"]["rows"]]
    by_net = {}
    for p in pins:
        p["x"], p["y"] = p["PIN_X"] * MIL, p["PIN_Y"] * MIL
        by_net.setdefault(p["NET_NAME"], []).append(p)
    imgs = {name: render(z.read(name).decode("utf-8", "replace")) for name in LAYERS}
    plated = drills(z.read("Drill_PTH_Through.DRL").decode())        # every plated hole, the vias included
    vias = {h[0] for h in drills(z.read("Drill_PTH_Through_Via.DRL").decode())}
    assert vias <= {h[0] for h in plated}, "a via is missing from the PTH drill file"
    for a, b, dia in drills(z.read("Drill_NPTH_Through.DRL").decode()):    # no copper survives a non-plated hole
        for img in imgs.values():
            cv2.line(img, px(*a), px(*b), 0, max(1, round(dia * S)), cv2.LINE_8, SH)
            for q in (a, b):
                cv2.circle(img, px(*q), r16(dia / 2), 0, -1, cv2.LINE_8, SH)
    top = imgs[LAYERS[0]]
    if "--open" in args:
        net = args[args.index("--open") + 1]
        p = next(q for q in by_net[net] if q["PIN_TYPE"] == "SMD")
        ring = max(p["PAD_SIZEX"], p["PAD_SIZEY"]) * MIL / 2 + 0.3
        cv2.circle(top, px(p["x"], p["y"]), r16(ring), 0, round(0.3 * S), cv2.LINE_8, SH)
        print(f"DAMAGED ON PURPOSE: a ring cut round {p['PIN_NAME']} ({net})")
    if "--short" in args:
        na, nb = args[args.index("--short") + 1:args.index("--short") + 3]
        pa, pb = min(((a, b) for a in by_net[na] for b in by_net[nb]), key=lambda ab: math.dist((ab[0]["x"], ab[0]["y"]), (ab[1]["x"], ab[1]["y"])))
        cv2.line(top, px(pa["x"], pa["y"]), px(pb["x"], pb["y"]), 255, round(0.2 * S), cv2.LINE_8, SH)
        print(f"DAMAGED ON PURPOSE: a track from {pa['PIN_NAME']} ({na}) to {pb['PIN_NAME']} ({nb})")
    if "--no-vias" in args:
        plated = [h for h in plated if h[0] not in vias]
        print("DAMAGED ON PURPOSE: the vias left out")
    labels = {name: cv2.connectedComponents(img, connectivity=8, ltype=cv2.CV_32S)[1] for name, img in imgs.items()}
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def at(name, x, y):
        cx, cy = round((x - X0) * S), round((Y1 - y) * S)
        return int(labels[name][cy, cx]) if 0 <= cx < W and 0 <= cy < H else 0

    bare_holes = 0
    for a, b, dia in plated:
        nodes = {(name, at(name, *q)) for name in LAYERS for q in (a, b, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))}
        nodes = [nd for nd in nodes if nd[1]]
        bare_holes += not nodes
        for nd in nodes[1:]:
            parent[find(nd)] = find(nodes[0])
    piece_nets, bare_pins = {}, []
    for p in pins:
        lab = at(LAYERS[0], p["x"], p["y"])
        if lab:
            p["piece"] = find((LAYERS[0], lab))
            piece_nets.setdefault(p["piece"], set()).add(p["NET_NAME"])
        else:
            bare_pins.append(p["PIN_NAME"])
    shorts = sorted(sorted(v) for v in piece_nets.values() if len(v) > 1)
    opens = sorted(net for net, ps in by_net.items() if len({p["piece"] for p in ps if "piece" in p}) > 1)

    nets, errors = resolved_nets()             # the export's netlist against design.py
    export = {}
    for p in pins:
        if not p["PIN_NAME"].startswith("PAD"):   # PAD<n>: the probe's own test points, already in the copper check
            ref, num = p["PIN_NAME"].rsplit("_", 1)
            export.setdefault((ref, num), set()).add(p["NET_NAME"])
    renamed, mismatches = [], list(errors)
    for net, members in nets.items():
        names = set().union(*(export.get(m, {"(no pad)"}) for m in members))
        if names == {net}:
            continue
        if len(names) == 1 and re.fullmatch(r"NET_\d+", next(iter(names))) and len(net) > 10:
            renamed.append(f"{net} -> {next(iter(names))}")
        else:
            mismatches.append(f"{net}: export has {sorted(names)}")
    owned = set().union(*nets.values())
    stray = sorted(f"{r}.{n} on {sorted(v)}" for (r, n), v in export.items()
                   if (r, n) not in owned and not all(x == "" or re.fullmatch(r"NET_\d+", x) for x in v))

    print(f"copper: {len(pins)} probe pins on {len(by_net)} nets, {len(plated)} plated holes ({bare_holes} on no copper)")
    print("  pins on no copper:", bare_pins or "none")
    print("  SHORTS:", shorts or "none")
    print("  OPENS:", opens or "none")
    print(f"netlist: {len(owned)} design.py pins on {len(nets)} nets against the export")
    print("  mismatches:", mismatches or "none")
    print("  export pins on a net that design.py leaves open:", stray or "none")
    print("  renamed by the export (same pins):", renamed or "none")
    return 1 if bare_holes or bare_pins or shorts or opens or mismatches or stray else 0


if __name__ == "__main__":
    sys.exit(main())
