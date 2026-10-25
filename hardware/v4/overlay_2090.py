"""Overlay Adafruit's own 2090 board (from their Eagle .brd) on the live DecayDeck v4 PCB, true scale, and prove
the fit pin for pin: hole positions, JP1 -> J3 and JP2 -> J4 pad positions, and the net on every pin.

The 2090's TFT (CONN1) is on Adafruit's BOTTOM layer and the microSD / buffers / regulator are on their TOP layer,
overlapping the glass area, so the top layer is the back of the display and faces our board. Seen from above our
board we look at the 2090's bottom side: Adafruit's x is mirrored (x -> -x), y is unchanged (JP2 stays at -38.1).

usage: python overlay_2090.py   -> overlay_2090.png, exit 1 on any mismatch
"""
import math
import sys
import xml.etree.ElementTree as ET

from eda import run
from place_pcb import BOARD, CORNER_R

BRD = r"C:\Users\Abider\Documents\Projects\DecayDeck\adafruit2090.brd"
JS = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const pads = await eda.pcb_PrimitivePad.getAll();
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const p of pads) out.push([p.getState_X() * 0.0254, p.getState_Y() * 0.0254, 'HOLE', '', '']);
for (const c of comps) {
  const des = c.getState_Designator();
  for (const p of await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId()) || [])
    out.push([p.getState_X() * 0.0254, p.getState_Y() * 0.0254, des, p.getState_PadNumber(), p.getState_Net() || '']);
}
return out;
"""
# what our socket pin must carry for each 2090 signal ('' = must stay unconnected on our side)
WANT = {"GND": "GND", "+5V": "3V3", "VCC": "DISP_3VO", "LCD_RS_5V": "SPI_SCK_D", "SDO": "SPI_MISO",
        "SDI_5V": "SPI_MOSI_D", "LCD_CS_5V": "TFT_CS", "LCD_WR_5V": "TFT_DC", "LCD_RST_5V": "TFT_RST",
        "LCD_LITE": "TFT_BL", "CTP_IRQ": "TOUCH_INT", "SDA_5V": "I2C_SDA", "SCL_5V": "I2C_SCL",
        "IM3": "DISP_3VO", "IM2": "DISP_3VO", "IM1": "DISP_3VO", "IM0": "", "SD_CS_5V": "SD_CS",
        "CARDDET": "SD_CD"}
J3_USED = {"GND", "+5V"}   # JP1 duplicates JP2's bus; only its power pins are wired, the rest are mechanical


def xform(rot, px, py, ex, ey):
    """Eagle element transform (mirror about y first, then rotate, then translate), then our mirror x -> -x."""
    rot = rot or "R0"
    if "M" in rot:
        px = -px
    a = math.radians(float(rot.lstrip("MSR")))
    x, y = px * math.cos(a) - py * math.sin(a), px * math.sin(a) + py * math.cos(a)
    return -(ex + x), ey + y


def adafruit():
    r = ET.parse(BRD).getroot()
    out = {"outline": [], "holes": [], "jp1": [], "jp2": []}
    for w in r.findall(".//board/plain/wire"):
        if w.get("layer") == "20":
            x1, y1, x2, y2 = (float(w.get(k)) for k in ("x1", "y1", "x2", "y2"))
            out["outline"].append((-x1, y1, -x2, y2))
    sig = {}
    for s in r.findall(".//board/signals/signal"):
        for c in s.findall("contactref"):
            sig[(c.get("element"), c.get("pad"))] = s.get("name")
    pkgs = {(lib.get("name"), p.get("name")): p for lib in r.findall(".//board/libraries/library")
            for p in lib.findall(".//package")}
    for e in r.findall(".//board/elements/element"):
        ex, ey, rot = float(e.get("x")), float(e.get("y")), e.get("rot")
        if e.get("package", "").startswith("MOUNTINGHOLE"):
            out["holes"].append(xform(rot, 0, 0, ex, ey))
        if e.get("name") in ("JP1", "JP2"):
            for pad in pkgs[(e.get("library"), e.get("package"))].findall("pad"):
                x, y = xform(rot, float(pad.get("x")), float(pad.get("y")), ex, ey)
                out[e.get("name").lower()].append((x, y, pad.get("name"), sig.get((e.get("name"), pad.get("name")), "")))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyBboxPatch
    pads = run(JS)["result"]
    ada = adafruit()
    ours = {(ref, num): (x, y, net) for x, y, ref, num, net in pads if ref != "HOLE"}
    holes = [(x, y) for x, y, ref, num, net in pads if ref == "HOLE"]
    holes = [h for h in holes if not any(abs(h[0] - x) < 1e-6 and abs(h[1] - y) < 1e-6 for x, y, *_ in ours.values())]

    problems, worst = [], {"J3": 0.0, "J4": 0.0}
    for hdr, ref in (("jp1", "J3"), ("jp2", "J4")):
        for x, y, n, s in ada[hdr]:
            if (ref, n) not in ours:
                problems.append(f"{ref}.{n} missing")
                continue
            ox, oy, net = ours[(ref, n)]
            d = math.hypot(ox - x, oy - y)
            worst[ref] = max(worst[ref], d)
            want = WANT.get(s, "?") if ref == "J4" else (WANT[s] if s in J3_USED else "")
            ok = d < 0.05 and net == want
            if not ok:
                problems.append(f"{ref}.{n}: 2090 {hdr.upper()}.{n}={s}, ours {net or '-'} (want {want or '-'}), offset {d:.3f} mm")
            print(f"{ref}.{n:>2} @({ox:7.2f},{oy:6.2f})  2090 {hdr.upper()}.{n:>2} {s:11} -> ours {net or '-':11} "
                  f"{'OK' if ok else 'BAD'}  {d:.3f} mm")
    worst_hole = max(min(math.hypot(hx - x, hy - y) for x, y in holes) for hx, hy in ada["holes"])
    if worst_hole > 0.05:
        problems.append(f"hole offset {worst_hole:.3f} mm")

    fig, ax = plt.subplots(figsize=(8, 13), dpi=120)
    ax.add_patch(FancyBboxPatch((BOARD[0] + CORNER_R, BOARD[1] + CORNER_R), BOARD[2] - BOARD[0] - 2 * CORNER_R,
                                BOARD[3] - BOARD[1] - 2 * CORNER_R, boxstyle=f"round,pad={CORNER_R}",
                                fc="#0d3b1e", ec="#c080ff", lw=2))
    for (ref, num), (x, y, net) in ours.items():
        col = {"J3": "#00e5ff", "J4": "#00e5ff", "U1": "#ff9040"}.get(ref, "#e0b030")
        ax.add_patch(Circle((x, y), 0.45, fc=col, ec="none", zorder=2))
    for x, y in holes:
        ax.add_patch(Circle((x, y), 1.35, fc="white", ec="k", zorder=3))
    for x1, y1, x2, y2 in ada["outline"]:
        ax.plot([x1, x2], [y1, y2], color="#ff3030", lw=2.2, zorder=5)
    for hx, hy in ada["holes"]:
        ax.add_patch(Circle((hx, hy), 1.5, fill=False, ec="#ff3030", lw=2.2, zorder=6))
    for hdr in ("jp1", "jp2"):
        for x, y, n, s in ada[hdr]:
            ax.add_patch(Circle((x, y), 0.9, fill=False, ec="#ff3030", lw=1.3, zorder=6))
            if n in ("1", "20"):
                ax.annotate(f"{hdr.upper()}.{n} {s}", (x, y), (x + (1 if n == "1" else -14), y + (3 if hdr == "jp1" else -4.5)),
                            color="#ff9090", fontsize=7, arrowprops=dict(arrowstyle="->", color="#ff9090"))
    ax.text(0, -44.5, "J4 (cyan) under 2090 JP2 (red rings): pin 1 = GND at the LEFT (x = -24.13)", color="#9ff",
            fontsize=7, ha="center")
    ax.text(0, 43.2, "J3 (cyan) under 2090 JP1: GND / Vin / GND wired, rest mechanical", color="#9ff", fontsize=7,
            ha="center")
    ax.text(-31, -55, "red = Adafruit 2090 from their Eagle file,\nmirrored: their back faces our board\n"
            "white = our mounting holes\norange = ESP32 (chin, clear of the display)", color="w", fontsize=7)
    ax.set_xlim(-36, 36)
    ax.set_ylim(BOARD[1] - 3, BOARD[3] + 4)
    ax.set_aspect("equal")
    ax.set_facecolor("#111")
    ax.grid(True, color="#333", lw=0.4)
    ax.set_title("Adafruit 2090 (red) on DecayDeck v4 PCB1, true scale (mm), top view")
    fig.tight_layout()
    fig.savefig("overlay_2090.png")
    print(f"worst pin offset J3 {worst['J3']:.3f} mm, J4 {worst['J4']:.3f} mm; worst hole offset {worst_hole:.3f} mm")
    for p in problems:
        print("PROBLEM", p)
    print("PASS" if not problems else f"FAIL ({len(problems)})")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
