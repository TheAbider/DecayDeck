"""DecayDeck v4 board placement: positions in mm (board origin = display centre, y up), plus offline
checks (part overlap, HV clearance, board edge) and a PNG render.

usage: python place_pcb.py check     -> checks + layout.png
       python place_pcb.py push      -> move the parts on the EasyEDA PCB (after a clean check)
"""
import json
import math
import sys

from design import PARTS

FP = json.load(open("footprints.json", encoding="utf-8"))

# Board: 66 x 111 mm, display (Adafruit 2090, 62.48 x 81.28) centred at the origin; the chin below it holds the ESP32.
BOARD = (-33.0, -69.0, 33.0, 42.0)       # x0, y0, x1, y1
CORNER_R = 3.0
DISPLAY = (-31.24, -40.64, 31.24, 40.64)
HOLES = {"MH1": (-28.575, 38.1), "MH2": (28.575, 38.1), "MH3": (-28.575, -38.1), "MH4": (28.575, -38.1)}
HOLE_KEEPOUT_R = 2.9                      # M2.5 standoff / nut footprint radius
ANTENNA_KEEPOUT = (9.0, -69.0, 30.0, -62.4)  # no copper (module antenna at the bottom edge)
HV_NETS = {"HV_SW", "HV_V1", "HV_M", "HV_OUT", "HV_D1", "HV_D2", "HV_B1", "HV_B2", "GM1_AM", "GM1_ANODE",
           "GM2_AM", "GM2_ANODE"}
HV_CLEAR = 2.5
OVERHANG = {"U1", "SW1", "SW2", "SW3", "J1", "J2"}  # intended to reach the board edge
EXTRA_BODY = {  # half-extents of bodies that reach past their pads (mm, at rotation 0)
    "U1": (-9.0, -9.6, 9.0, 15.9),       # WROOM-1: antenna extends +y (local)
    "J3": (-25.4, -1.27, 25.4, 1.27), "J4": (-25.4, -1.27, 25.4, 1.27),
    "L2": (-3.0, -3.0, 3.0, 3.0),
    "J1": (-4.5, -4.2, 4.5, 3.4),
    "J2": (-4.0, -4.9, 4.0, 3.2),
    "BZ1": (-4.25, -4.25, 4.25, 4.25),
    "D4": (-2.15, -1.3, 2.15, 1.3), "D5": (-2.15, -1.3, 2.15, 1.3), "D6": (-2.15, -1.3, 2.15, 1.3),
    "D7": (-2.15, -1.3, 2.15, 1.3),   # SMA bodies are taller than their pads
    "SW1": (-2.25, -2.9, 2.25, 1.9), "SW2": (-2.25, -2.9, 2.25, 1.9), "SW3": (-2.25, -2.9, 2.25, 1.9),
}

# ref: (x, y, rot)   rotations are CCW degrees, top side only
PLACE = {
    # ---------------- display headers (front view: 2090 is mirrored vs its Eagle top view -> pin 1 at -x) ----------------
    "J3": (0.0, 38.1, 0), "J4": (0.0, -38.1, 0),
    "C32": (-22.4, -34.6, 0), "C33": (-18.6, -34.6, 0), "R47": (-5.0, -34.8, 0), "R48": (19.0, -34.8, 0),

    # ---------------- ESP32 module in the chin, antenna at the bottom-right edge ----------------
    "U1": (19.5, -53.1, 180),
    "C15": (31.0, -60.4, 90), "C14": (31.0, -56.2, 90),
    "R22": (31.0, -64.2, 90), "C13": (31.0, -67.0, 90),
    "R45": (18.2, -41.6, 0), "R46": (22.4, -41.6, 0),          # SPI series, just above the module's SPI pins
    "R49": (6.8, -47.6, 90), "R50": (8.6, -47.6, 90),           # I2C pull-ups by IO36/IO37

    # ---------------- chin, left of the module: USB-C, battery, buzzer, LEDs, light + environment ----------------
    "J1": (-5.0, -65.2, 0), "U12": (-5.0, -58.6, 90),
    "R1": (-9.8, -58.0, 90), "R3": (-11.6, -58.0, 90), "C1": (-13.4, -58.0, 90),
    "R2": (-0.2, -58.0, 90), "R4": (1.6, -58.0, 90), "C2": (3.4, -58.0, 90),
    "C3": (-6.6, -54.4, 0), "C4": (-3.0, -54.4, 0),
    "J2": (-25.4, -63.6, 0), "Q1": (-16.4, -62.6, 0), "R13": (-16.4, -65.8, 0),
    "BZ1": (-17.0, -50.0, 0),
    "LED1": (-4.6, -47.4, 0), "R57": (-8.0, -47.4, 0), "C41": (-1.6, -47.4, 90),
    "LED2": (2.6, -47.4, 0), "R8": (2.6, -50.0, 0),
    "U8": (-27.6, -46.2, 0), "C39": (-25.0, -46.2, 90),
    "U5": (-28.8, -52.8, 90), "C34": (-26.4, -52.8, 90),
    "D8": (-11.6, -43.4, 0), "Q6": (-7.6, -43.4, 0), "R53": (-4.0, -43.4, 0), "R54": (-1.0, -43.4, 0), "C40": (2.6, -43.4, 0),

    # ---------------- right edge buttons (actuators push in from +x) ----------------
    "SW1": (31.0, 28.0, 90), "D1": (26.2, 26.6, 0), "R15": (26.2, 23.8, 0), "R16": (26.2, 21.8, 0),
    "SW2": (31.0, 14.0, 90), "R23": (26.6, 15.2, 0), "C16": (26.6, 13.2, 0),
    "SW3": (31.0, 2.0, 90), "R24": (26.6, 3.2, 0), "C17": (26.6, 1.2, 0),

    # ---------------- motor pads + driver, right edge lower (wires to the coin motor in the case) ----------------
    "J9": (29.8, -21.0, 0), "J10": (29.8, -27.0, 0), "D9": (29.8, -24.0, 0), "Q7": (25.6, -27.0, 0),
    "R55": (25.6, -30.0, 0), "R56": (25.6, -32.0, 0),

    # ---------------- sensors, centre-right ----------------
    "U7": (12.0, 14.0, 0), "C37": (14.8, 14.0, 90), "C38": (9.2, 14.6, 90),
    "U6": (12.0, 6.0, 0), "C35": (15.0, 6.0, 90), "R51": (8.4, 6.6, 90), "C36": (6.6, 6.6, 90), "R52": (12.0, 3.4, 0),
    "NTC1": (12.0, -6.0, 0),
    "U4": (4.0, -6.0, 0), "C7": (4.0, -8.8, 0),

    # ---------------- HV supply: upper-left under the display ----------------
    # boost (bottom) -> doubler (left column) -> HV_OUT stack (C26/C27/D7, HV_OUT pads on the left, GND on the right)
    # -> anode chains to the edge pads J5/J7, divider + bleeder columns, comparator below them
    "R21": (-30.6, -3.6, 90), "C18": (-26.0, -4.0, 0), "C19": (-26.0, -6.2, 0),
    "L2": (-26.0, 2.6, 0),
    "Q3": (-19.6, 2.6, 0),
    "R25": (-18.6, -0.8, 0), "C20": (-18.6, -2.6, 0), "R26": (-16.4, -2.6, 90),
    "U10": (-13.0, -2.0, 0), "C21": (-13.0, -5.0, 0), "R27": (-9.6, -2.8, 90),
    "D4": (-23.5, 9.6, 270), "C24": (-28.6, 13.2, 180),
    "D5": (-23.5, 16.8, 270), "C25": (-17.6, 13.4, 90),
    "D6": (-17.6, 21.6, 180),
    "C26": (-10.6, 21.6, 0), "C27": (-10.6, 17.6, 0), "D7": (-10.7, 14.0, 0),
    "J5": (-28.6, 32.4, 0), "R36": (-22.4, 32.4, 180), "R35": (-16.8, 32.4, 180),
    "J7": (-28.6, 26.0, 0), "R41": (-22.4, 26.0, 180), "R40": (-16.8, 26.0, 180),
    "R30": (-4.0, 31.0, 270), "R31": (-4.0, 26.0, 270), "R32": (-4.0, 21.0, 270),
    "R58": (0.6, 31.0, 270), "R59": (0.6, 26.0, 270), "R60": (0.6, 21.0, 270),
    "R33": (-6.6, 16.8, 270), "C28": (-4.8, 16.8, 270), "R34": (-3.0, 16.8, 270),
    "U9": (-4.0, 12.4, 0), "C22": (-6.4, 12.4, 270),
    "R28": (-1.0, 13.0, 180), "R29": (-1.0, 11.4, 0), "C23": (-1.0, 9.8, 0),

    # ---------------- GM detectors + cathode pads, lower left ----------------
    "J8": (-28.6, -14.0, 0), "R42": (-24.4, -13.0, 0), "R43": (-24.4, -15.2, 0), "C30": (-21.6, -17.8, 0),
    "Q5": (-19.0, -14.2, 0), "R44": (-15.6, -12.6, 0),
    "J6": (-28.6, -28.0, 0), "R37": (-24.4, -27.0, 0), "R38": (-24.4, -29.2, 0), "C29": (-21.6, -31.8, 0),
    "Q4": (-19.0, -28.2, 0), "R39": (-15.6, -26.6, 0),
    "U11": (-12.0, -20.4, 0), "C31": (-9.6, -20.4, 90),

    # ---------------- charger + battery path, lower middle under the display ----------------
    "U2": (-2.0, -22.0, 0), "R5": (-2.0, -26.0, 0), "R6": (-5.4, -26.0, 0), "R7": (1.4, -26.0, 0),
    "C5": (2.4, -20.0, 90), "C6": (-6.0, -19.6, 90), "C3_": None,
    "D3": (-2.6, -29.6, 0), "R9": (1.4, -29.6, 0),
    "R10": (4.8, -24.2, 90), "R11": (6.6, -24.2, 90), "Q8": (5.6, -28.4, 0), "R12": (2.4, -31.8, 0),

    # ---------------- soft power + 3V3 buck-boost, lower right under the display ----------------
    "Q2": (16.0, -14.0, 0), "R14": (16.0, -10.8, 0), "D2": (20.4, -14.0, 0), "R17": (20.4, -17.2, 0),
    "R18": (16.0, -17.2, 0),
    "U3": (16.0, -24.0, 90), "L1": (16.0, -20.4, 180),
    "C8": (12.8, -23.8, 270), "C9": (11.0, -23.8, 270),
    "C10": (19.2, -23.8, 270), "C11": (21.2, -23.8, 270), "C12": (23.0, -23.8, 270),
    "R19": (17.6, -27.4, 0), "R20": (14.4, -27.4, 0),
}
PLACE = {k: v for k, v in PLACE.items() if v is not None}


def rot(x, y, deg):
    a = math.radians(deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def abs_pads(ref):
    x0, y0, r = PLACE[ref]
    out = []
    for p in FP[ref]["pads"]:
        x, y = rot(p["x"], p["y"], r)
        w, h = (p["w"], p["h"]) if r % 180 == 0 else (p["h"], p["w"])
        out.append({**p, "ax": x0 + x, "ay": y0 + y, "aw": w, "ah": h})
    return out


def part_box(ref, margin=0.2):
    pads = abs_pads(ref)
    xs = [p["ax"] - p["aw"] / 2 for p in pads] + [p["ax"] + p["aw"] / 2 for p in pads]
    ys = [p["ay"] - p["ah"] / 2 for p in pads] + [p["ay"] + p["ah"] / 2 for p in pads]
    if ref in EXTRA_BODY:
        bx0, by0, bx1, by1 = EXTRA_BODY[ref]
        x0, y0, r = PLACE[ref]
        pts = [rot(px, py, r) for px, py in ((bx0, by0), (bx1, by1), (bx0, by1), (bx1, by0))]
        xs += [x0 + px for px, _ in pts]
        ys += [y0 + py for _, py in pts]
    return min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin


def rect_gap(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0)
    dy = max(b[1] - a[3], a[1] - b[3], 0)
    return math.hypot(dx, dy)


def pad_gap(p, q):
    a = (p["ax"] - p["aw"] / 2, p["ay"] - p["ah"] / 2, p["ax"] + p["aw"] / 2, p["ay"] + p["ah"] / 2)
    b = (q["ax"] - q["aw"] / 2, q["ay"] - q["ah"] / 2, q["ax"] + q["aw"] / 2, q["ay"] + q["ah"] / 2)
    return rect_gap(a, b)


def check():
    problems = []
    missing = [r for r in PARTS if r not in PLACE]
    extra = [r for r in PLACE if r not in PARTS]
    if missing:
        problems.append(f"unplaced: {missing}")
    if extra:
        problems.append(f"placed but not in design: {extra}")
    refs = [r for r in PLACE if r in PARTS and r in FP]
    boxes = {r: part_box(r) for r in refs}
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            if rect_gap(boxes[a], boxes[b]) <= 0:
                problems.append(f"overlap {a} / {b}")
        bx = boxes[a]
        if a not in OVERHANG and (bx[0] < BOARD[0] or bx[1] < BOARD[1] or bx[2] > BOARD[2] or bx[3] > BOARD[3]):
            problems.append(f"{a} off board {tuple(round(v, 2) for v in bx)}")
        for h, (hx, hy) in HOLES.items():
            if rect_gap(bx, (hx - HOLE_KEEPOUT_R, hy - HOLE_KEEPOUT_R, hx + HOLE_KEEPOUT_R, hy + HOLE_KEEPOUT_R)) <= 0:
                problems.append(f"{a} in keepout of {h}")
        if a != "U1" and rect_gap(bx, ANTENNA_KEEPOUT) <= 0:
            problems.append(f"{a} in antenna keepout")
    # HV pad clearance to every other net's pads
    pads = [(r, p) for r in refs for p in abs_pads(r)]
    for i, (ra, pa) in enumerate(pads):
        for rb, pb in pads[i + 1:]:
            na, nb = pa["net"] or "", pb["net"] or ""
            if na == nb or not (na in HV_NETS or nb in HV_NETS):
                continue
            if ra == rb:
                continue   # pads of one HV part: set by the footprint (reported separately)
            g = pad_gap(pa, pb)
            if g < HV_CLEAR:
                problems.append(f"HV clearance {g:.2f} mm: {ra}.{pa['num']}({na}) - {rb}.{pb['num']}({nb})")
    for r, p in pads:
        if (p["net"] or "") not in HV_NETS:
            continue
        x0, y0 = p["ax"] - p["aw"] / 2, p["ay"] - p["ah"] / 2
        x1, y1 = p["ax"] + p["aw"] / 2, p["ay"] + p["ah"] / 2
        edge = min(x0 - BOARD[0], y0 - BOARD[1], BOARD[2] - x1, BOARD[3] - y1)
        if edge < HV_CLEAR:
            problems.append(f"HV pad {r}.{p['num']} {edge:.2f} mm from board edge")
        for h, (hx, hy) in HOLES.items():
            d = rect_gap((x0, y0, x1, y1), (hx, hy, hx, hy)) - 1.35
            if d < HV_CLEAR:
                problems.append(f"HV pad {r}.{p['num']} {d:.2f} mm from hole {h}")
    return problems


def render(path="layout.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
    fig, ax = plt.subplots(figsize=(9, 14), dpi=110)
    ax.add_patch(FancyBboxPatch((BOARD[0] + CORNER_R, BOARD[1] + CORNER_R), BOARD[2] - BOARD[0] - 2 * CORNER_R,
                                BOARD[3] - BOARD[1] - 2 * CORNER_R, boxstyle=f"round,pad={CORNER_R}",
                                fc="#0b3d1c", ec="k", lw=1.5))
    ax.add_patch(Rectangle(DISPLAY[:2], DISPLAY[2] - DISPLAY[0], DISPLAY[3] - DISPLAY[1], fill=False, ec="#88aaff", ls="--"))
    ax.add_patch(Rectangle(ANTENNA_KEEPOUT[:2], ANTENNA_KEEPOUT[2] - ANTENNA_KEEPOUT[0],
                           ANTENNA_KEEPOUT[3] - ANTENNA_KEEPOUT[1], fc="#553300", ec="orange", alpha=0.6))
    for h, (hx, hy) in HOLES.items():
        ax.add_patch(Circle((hx, hy), 1.35, fc="white", ec="k"))
        ax.add_patch(Circle((hx, hy), HOLE_KEEPOUT_R, fill=False, ec="w", ls=":"))
    for r in PLACE:
        if r not in FP:
            continue
        bx = part_box(r, margin=0)
        hv = any((p["net"] or "") in HV_NETS for p in FP[r]["pads"])
        ax.add_patch(Rectangle(bx[:2], bx[2] - bx[0], bx[3] - bx[1], fill=False, ec="#ff5555" if hv else "#dddddd", lw=0.6))
        for p in abs_pads(r):
            col = "#ff3030" if (p["net"] or "") in HV_NETS else ("#999999" if p["net"] == "GND" else "#e0b030")
            ax.add_patch(Rectangle((p["ax"] - p["aw"] / 2, p["ay"] - p["ah"] / 2), p["aw"], p["ah"], fc=col, ec="none"))
        ax.text((bx[0] + bx[2]) / 2, bx[3] + 0.2, r, color="w", fontsize=5, ha="center", va="bottom")
    ax.set_xlim(BOARD[0] - 2, BOARD[2] + 2)
    ax.set_ylim(BOARD[1] - 2, BOARD[3] + 2)
    ax.set_aspect("equal")
    ax.set_facecolor("#202020")
    ax.grid(True, color="#444", lw=0.3)
    ax.set_xticks(range(-34, 35, 2))
    ax.set_yticks(range(-70, 45, 2))
    ax.tick_params(labelsize=5)
    fig.tight_layout()
    fig.savefig(path)


def push():
    from eda import run
    comps = {c["des"]: c for c in json.load(open("pcb_pads.json", encoding="utf-8"))}
    items = [{"id": comps[r]["id"], "x": x / 0.0254, "y": y / 0.0254, "rot": rt} for r, (x, y, rt) in PLACE.items()
             if r in comps]
    js = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const res = [];
for (const it of __ITEMS__) {
  const r = await eda.pcb_PrimitiveComponent.modify(it.id, { x: it.x, y: it.y, rotation: it.rot, layer: 1 });
  res.push(r ? 1 : 0);
}
return res.reduce((a, b) => a + b, 0);
"""
    for i in range(0, len(items), 30):
        r = run(js.replace("__ITEMS__", json.dumps(items[i:i + 30])))
        print("moved", r.get("result"), r.get("error") or "")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.argv[1] == "check":
        probs = check()
        for p in probs:
            print(p)
        print(len(probs), "problems")
        render()
    elif sys.argv[1] == "push":
        push()
