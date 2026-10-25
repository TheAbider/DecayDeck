"""Vertical clearance between our top-side parts and the underside of the Adafruit 2090 stacked above them.

Stack: our PCB -> 8.5 mm female sockets (J3/J4, KH-2.54FH-1X20P-H8.5) -> 2.5 mm plastic of the 2090's male header
-> 2090 PCB. Board-to-board gap 11.0 mm nominal (M2.5 x 11 mm nylon standoffs); 10.7 mm used here as the worst case
(socket -0.2, header plastic -0.1).
The 2090's underside is Adafruit's TOP layer (microSD, buffers, regulator, EYESPI); its coordinates are mirrored in x
into our top view (see overlay_2090.py). Heights are datasheet maxima, rounded up.

usage: python height_check.py   -> table + height_check.png; exit 1 if any clearance < 1.0 mm
"""
import math
import sys
import xml.etree.ElementTree as ET

import place_pcb as P
from design import PARTS

BRD = r"C:\Users\Abider\Documents\Projects\DecayDeck\adafruit2090.brd"
GAP = 10.7
MIN_CLEAR = 1.0
XY_MARGIN = 0.5   # placement / outline tolerance around every body
# 2090 underside parts, max height (mm)
THEIRS_H = {"MICROSD": 2.0, "EYE_SPI_DISPLAY_BOTCONTACT": 2.5, "TSSOP20": 1.2, "SOT23-WIDE": 1.3, "SOT23-5": 1.45,
            "0603-NO": 1.0, "0805-NO": 1.45, "SOLDERJUMPER_ARROW_NOPASTE": 0.1, "TP06R": 0.1}
CUTOUT_H = 3.0    # allowance for the TFT flex / touch-controller fold showing through the 2090's board cutout
# our parts, max height (mm) by footprint, with per-part overrides
OURS_H = {"C0603": 1.0, "C0805": 1.45, "C1206": 1.8, "C1812": 2.5, "R0603": 1.0, "R1206": 0.7,
          "DFN-8_L3.2-W1.5-P0.9-BL": 0.8, "IND-SMD_L4.0-W4.0_XFL4020-102MEB": 1.6, "IND-SMD_L6.0-W6.0": 4.7,
          "KEY-SMD_SKRTLAE010": 3.5, "LGA-12_L2.0-W2.0-P0.50-BL": 1.0, "QFN-16_L3.0-W3.0-P0.50-TL-EP1.7": 1.0,
          "SMA_L4.3-W2.6-LS5.2-RD": 2.44, "SOD-323_L1.8-W1.3-LS2.5-RD": 1.1, "SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR": 1.3,
          "SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR": 1.3, "SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR": 1.45,
          "SOT-23_L2.9-W1.3-P1.90-LS2.4-BR": 1.3, "SOT-363_L2.1-W1.3-P0.65-LS2.2-BL": 1.1,
          "TDFN-8_L2.0-W2.0-P0.50-BL-EP1.2": 0.8, "TESTPOINT-TH_BD3.2-D1.6": 3.0,   # wire + solder fillet
          "TSOT-23-5_L2.9-W1.6-P0.95-LS2.8-BL": 1.0, "VSON-10_L3.0-W2.0-P0.50-TL": 1.0}
STACKING = {"J3", "J4"}   # the sockets the 2090 plugs into


def xform(rot, px, py, ex, ey):
    rot = rot or "R0"
    if "M" in rot:
        px = -px
    a = math.radians(float(rot.lstrip("MSR")))
    x, y = px * math.cos(a) - py * math.sin(a), px * math.sin(a) + py * math.cos(a)
    return -(ex + x), ey + y


def theirs():
    """[(name, package, height, (x0, y0, x1, y1))] for the 2090's underside, plus the board cutout as polygons."""
    r = ET.parse(BRD).getroot()
    pk = {(lib.get("name"), p.get("name")): p for lib in r.findall(".//board/libraries/library")
          for p in lib.findall(".//package")}
    out = []
    for e in r.findall(".//board/elements/element"):
        rot = e.get("rot") or "R0"
        if "M" in rot or e.get("package") not in THEIRS_H:
            continue
        p = pk[(e.get("library"), e.get("package"))]
        pts = []
        for s in p.findall("smd"):
            x, y, dx, dy = (float(s.get(k)) for k in ("x", "y", "dx", "dy"))
            if (s.get("rot") or "R0") in ("R90", "R270"):
                dx, dy = dy, dx
            pts += [(x - dx / 2, y - dy / 2), (x + dx / 2, y + dy / 2)]
        for w in list(p.findall("wire")) + list(p.findall("rectangle")):
            if w.get("layer") in ("21", "51", "39"):
                pts += [(float(w.get("x1")), float(w.get("y1"))), (float(w.get("x2")), float(w.get("y2")))]
        xs, ys = [p_[0] for p_ in pts], [p_[1] for p_ in pts]
        corners = [xform(rot, cx, cy, float(e.get("x")), float(e.get("y")))
                   for cx in (min(xs), max(xs)) for cy in (min(ys), max(ys))]
        box = (min(c[0] for c in corners), min(c[1] for c in corners), max(c[0] for c in corners), max(c[1] for c in corners))
        out.append((e.get("name"), e.get("package"), THEIRS_H[e.get("package")], box))
    # board cutouts: closed loops of layer-20 wires other than the outer outline
    segs = [tuple(-float(w.get(k)) if k[0] == "x" else float(w.get(k)) for k in ("x1", "y1", "x2", "y2"))
            for w in r.findall(".//board/plain/wire") if w.get("layer") == "20"]
    loops, used = [], set()
    for i in range(len(segs)):
        if i in used:
            continue
        loop, used_now = [segs[i][:2], segs[i][2:]], {i}
        while True:
            end = loop[-1]
            nxt = next((j for j in range(len(segs)) if j not in used_now and
                        (math.dist(segs[j][:2], end) < 0.01 or math.dist(segs[j][2:], end) < 0.01)), None)
            if nxt is None:
                break
            used_now.add(nxt)
            s = segs[nxt]
            loop.append(s[2:] if math.dist(s[:2], end) < 0.01 else s[:2])
        used |= used_now
        loops.append(loop)
    loops.sort(key=lambda lp: -(max(p_[0] for p_ in lp) - min(p_[0] for p_ in lp)))
    return out, loops[1:]


def inside(pt, poly):
    x, y = pt
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def box_hits_poly(box, poly, step=0.25):
    x0, y0, x1, y1 = box
    nx, ny = max(2, int((x1 - x0) / step) + 1), max(2, int((y1 - y0) / step) + 1)
    return any(inside((x0 + (x1 - x0) * i / (nx - 1), y0 + (y1 - y0) * j / (ny - 1)), poly)
               for i in range(nx) for j in range(ny))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    above, cutouts = theirs()
    rows, bad = [], []
    for ref in sorted(PARTS):
        if ref in STACKING or ref not in P.PLACE:
            continue
        box = P.part_box(ref, margin=0)
        if P.rect_gap(box, P.DISPLAY) > 0:
            continue   # not under the display
        fp = P.FP[ref]["fp"]
        h = OURS_H.get(ref, OURS_H.get(fp))
        if h is None:
            bad.append(f"{ref}: no height for footprint {fp}")
            continue
        grown = (box[0] - XY_MARGIN, box[1] - XY_MARGIN, box[2] + XY_MARGIN, box[3] + XY_MARGIN)
        hits = [(n, hh) for n, pkg, hh, b in above if P.rect_gap(grown, b) <= 0]
        hits += [("cutout", CUTOUT_H) for poly in cutouts if box_hits_poly(grown, poly)]
        top = max((hh for _, hh in hits), default=0.0)
        clear = GAP - h - top
        rows.append((clear, ref, fp, h, hits))
        if clear < MIN_CLEAR:
            bad.append(f"{ref}: clearance {clear:.2f} mm")
    rows.sort()
    print(f"gap {GAP} mm (worst case); {len(rows)} of our parts sit under the display\n")
    print(f"{'part':6} {'height':>6}  {'2090 part above (height)':40} {'clearance':>9}")
    for clear, ref, fp, h, hits in rows[:25]:
        above_s = ", ".join(f"{n} ({hh})" for n, hh in hits) or "-"
        print(f"{ref:6} {h:6.2f}  {above_s[:40]:40} {clear:8.2f} mm")
    if len(rows) > 25:
        print(f"... {len(rows) - 25} more, all with more clearance")
    tallest_ours = max(rows, key=lambda r_: r_[3])
    tallest_theirs = max([hh for _, _, hh, _ in above] + [CUTOUT_H])
    print(f"\nminimum clearance: {rows[0][0]:.2f} mm ({rows[0][1]})")
    print(f"even stacking the tallest of each ({tallest_ours[1]} {tallest_ours[3]} mm + {tallest_theirs} mm) leaves "
          f"{GAP - tallest_ours[3] - tallest_theirs:.2f} mm")
    render(rows, above, cutouts)
    for b in bad:
        print("PROBLEM", b)
    print("PASS" if not bad else "FAIL")
    return 1 if bad else 0


def render(rows, above, cutouts):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle
    fig, ax = plt.subplots(figsize=(8, 10), dpi=120)
    ax.add_patch(Rectangle(P.DISPLAY[:2], P.DISPLAY[2] - P.DISPLAY[0], P.DISPLAY[3] - P.DISPLAY[1], fc="#151515", ec="#88aaff"))
    cmap = plt.get_cmap("RdYlGn")
    for clear, ref, fp, h, hits in rows:
        b = P.part_box(ref, margin=0)
        ax.add_patch(Rectangle(b[:2], b[2] - b[0], b[3] - b[1], fc=cmap(min(1, (clear - 1) / 8)), ec="none", alpha=0.85))
        if h >= 2.0:
            ax.text((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, f"{ref}\n{h}", fontsize=5, ha="center", va="center")
    for n, pkg, hh, b in above:
        ax.add_patch(Rectangle(b[:2], b[2] - b[0], b[3] - b[1], fill=False, ec="#ff4040", lw=1))
        if hh >= 1.2:
            ax.text(b[0], b[3] + 0.3, f"2090 {n} {hh}", color="#ff8080", fontsize=5)
    for poly in cutouts:
        ax.add_patch(Polygon(poly, closed=True, fill=False, ec="#ff40ff", ls="--", lw=1))
        ax.text(poly[0][0], poly[0][1] - 1.5, f"2090 board cutout ({CUTOUT_H} mm allowance)", color="#ff80ff", fontsize=5)
    ax.set_xlim(-33, 33)
    ax.set_ylim(-42, 42)
    ax.set_aspect("equal")
    ax.set_facecolor("#000")
    ax.set_title(f"Parts under the 2090: colour = clearance to its underside (min {rows[0][0]:.1f} mm)", fontsize=9)
    fig.tight_layout()
    fig.savefig("height_check.png")


if __name__ == "__main__":
    sys.exit(main())
