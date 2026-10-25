"""Redraw the schematic the way a person would: each IC with its support parts wired round it, power and ground
symbols, net labels between blocks, framed and titled blocks, all inside the A2 sheet frame. The netlist stays
exactly design.py's, and every part keeps its identity (moved, never re-created), so the PCB's link to the schematic
is untouched.

The layout is code. Blocks are drawn with a small "chain" language: start at a pin, go a distance, drop a part
inline, and end in a ground symbol, a power symbol or a net label. Before anything is sent to EasyEDA, check()
rebuilds the connectivity from the drawing (pin tips, wire ends, symbols, labels) and compares it with design.py
pin for pin. It also rejects any overlap between symbols, wires, labels, part names, values and notes, so the sheet
reads clean.

usage: python sch_pretty.py check [preview.png]   -> validate and draw a preview
       python sch_pretty.py push                   -> validate, then rebuild the schematic page in EasyEDA
After a push, `python sch_check.py` re-exports the netlist from EasyEDA and checks it against design.py.
"""
import csv
import io
import json
import sys

from check_spec import resolved_nets
from design import PARTS

SYMS = json.load(open("symbols.json", encoding="utf-8"))
NETS, _ = resolved_nets()
SPEC = {m: n for n, ms in NETS.items() for m in ms}            # (ref, pin) -> net
DIRV = {"R": (1, 0), "L": (-1, 0), "U": (0, 1), "D": (0, -1)}
ANG = {0: "R", 90: "U", 180: "L", 270: "D"}
PIN_LEN = 10
CW, TH = 6, 9                                                  # text box: width per character, height
GND_ROT = {"D": 0, "R": 90, "U": 180, "L": 270}               # ground symbol body points along the chain
PWR_ROT = {"U": 0, "L": 90, "D": 180, "R": 270}
SHEET = (0, 0, 3304, 2338)                                     # A1 frame, drawing units (10 mil)
INNER = (20, 20, 3284, 2318)
TITLE_BLOCK = (2580, 10, 3294, 205)


def _values():
    rows = list(csv.reader(io.StringIO(open("fab/2026-10-25/DecayDeck_v4_BOM.csv", "rb").read().decode("utf-16")),
                           delimiter="\t"))
    out = {}
    for r in rows[1:]:
        for ref in r[3].split(","):
            out[ref.strip()] = r[5] or r[6]
    for ref, (key, val, blk, bom) in PARTS.items():
        out.setdefault(ref, val)
    return out


VALUES = _values()


def sym_pins(ref):
    return SYMS[PARTS[ref][0]]["pins"]


def pin_on(ref, net):
    return next(p["num"] for p in sym_pins(ref) if SPEC.get((ref, p["num"])) == net)


def tf(dx, dy, rot, mirror=False):
    if mirror:
        dx = -dx
    c = {0: 1, 90: 0, 180: -1, 270: 0}[rot % 360]
    s = {0: 0, 90: 1, 180: 0, 270: -1}[rot % 360]
    return dx * c - dy * s, dx * s + dy * c


def tf_ang(a, rot, mirror=False):
    if mirror:
        a = (180 - a) % 360
    return (a + rot) % 360


class Sheet:
    def __init__(self):
        self.parts = {}     # ref -> [x, y, rot, mirror]
        self.segs = []      # [net, (x0, y0), (x1, y1), label]
        self.flags = []     # [kind, net, x, y, rot, d]
        self.texts = []     # [x, y, text, size, bold]
        self.rects = []     # [x0, y0, x1, y1]
        self.attr = {}      # ref -> {"des": (x, y, align), "val": (...)} overrides

    def place(self, ref, x, y, rot=0, mirror=False):
        assert ref in PARTS and ref not in self.parts, ref
        self.parts[ref] = [x, y, rot % 360, mirror]

    def pin(self, ref, num):
        x, y, rot, mir = self.parts[ref]
        p = next(p for p in sym_pins(ref) if p["num"] == num)
        dx, dy = tf(p["dx"], p["dy"], rot, mir)
        return x + dx, y + dy, ANG[tf_ang(int(p["rot"] or 0), rot, mir)]

    def seg(self, net, a, b, label=False):
        if a != b:
            assert a[0] == b[0] or a[1] == b[1], (net, a, b)
            self.segs.append([net, a, b, label])

    def wire(self, net, *pts):
        for a, b in zip(pts, pts[1:]):
            self.seg(net, a, b)

    def flag(self, kind, net, x, y, d):
        rot = (GND_ROT if kind == "Ground" else PWR_ROT)[d]
        self.flags.append([kind, net, x, y, rot, d])

    def text(self, x, y, s, size=8, bold=False):
        self.texts.append([x, y, s, size, bold])

    def chain(self, start, d=None, net=None):
        if isinstance(start[0], str):
            x, y, pd = self.pin(*start)
            return Chain(self, x, y, d or pd, net or SPEC[tuple(start)])
        return Chain(self, start[0], start[1], d, net)

    def lab(self, ref, num, n=15):
        return self.chain((ref, num)).go(n, label=True)

    def decap(self, x, y, ref, rail):
        """Vertical decoupling cap: rail symbol on top, ground symbol below."""
        self.chain((x, y), "U", rail).go(10).pwr()
        self.chain((x, y), "D", rail).go(10).part(ref, pin_on(ref, rail)).go(10).gnd()

    def shift(self, dx, dy):
        for p in self.parts.values():
            p[0] += dx
            p[1] += dy
        self.segs = [[n, (a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy), lab] for n, a, b, lab in self.segs]
        for f in self.flags:
            f[2] += dx
            f[3] += dy
        for t in self.texts:
            t[0] += dx
            t[1] += dy
        self.rects = [[r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy] for r in self.rects]
        self.attr = {r: tuple((a[0] + dx, a[1] + dy, a[2]) for a in v) for r, v in self.attr.items()}

    def merge(self, o):
        for r, p in o.parts.items():
            assert r not in self.parts, r
            self.parts[r] = p
        self.segs += o.segs
        self.flags += o.flags
        self.texts += o.texts
        self.rects += o.rects
        self.attr.update(o.attr)


class Chain:
    def __init__(self, S, x, y, d, net):
        self.S, self.x, self.y, self.d, self.net = S, x, y, d, net

    @property
    def pt(self):
        return (self.x, self.y)

    def go(self, n, label=False):
        dx, dy = DIRV[self.d]
        nx, ny = self.x + dx * n, self.y + dy * n
        self.S.seg(self.net, (self.x, self.y), (nx, ny), label)
        self.x, self.y = nx, ny
        return self

    def to(self, x=None, y=None, label=False):
        n = (x - self.x) * DIRV[self.d][0] if x is not None else (y - self.y) * DIRV[self.d][1]
        assert n >= 0, ("to() goes backwards", self.net, self.pt, x, y, self.d)
        return self.go(n, label)

    def turn(self, d):
        self.d = d
        return self

    def part(self, ref, enter):
        pins = sym_pins(ref)
        ent = next(p for p in pins if p["num"] == enter)
        oth = next(p for p in pins if p["num"] != enter)
        ux, uy = DIRV[self.d]
        for rot in (0, 90, 180, 270):
            ex, ey = tf(ent["dx"], ent["dy"], rot)
            ox, oy = tf(oth["dx"], oth["dy"], rot)
            L = abs(ox - ex) + abs(oy - ey)
            if (ox - ex, oy - ey) == (ux * L, uy * L):
                break
        else:
            raise ValueError(ref)
        assert SPEC.get((ref, enter), "") == self.net, (ref, enter, SPEC.get((ref, enter)), self.net)
        self.S.place(ref, self.x - ex, self.y - ey, rot)
        self.x, self.y = self.x + ox - ex, self.y + oy - ey
        self.net = SPEC.get((ref, oth["num"]), "")
        return self

    def gnd(self):
        assert self.net == "GND", (self.net, self.pt)
        self.S.flag("Ground", "GND", self.x, self.y, self.d)
        return self

    def pwr(self):
        self.S.flag("Power", self.net, self.x, self.y, self.d)
        return self

    def fork(self, d):
        return Chain(self.S, self.x, self.y, d, self.net)


# =====================================================================================================
# Blocks. Each is drawn in its own coordinates; pack() places them on the sheet.
# =====================================================================================================

def block_usb(S):
    S.place("J1", 0, 0, 0, mirror=True)                       # pins face right, shield tabs face left
    for n in ("4", "3", "2", "1"):
        S.chain(("J1", n)).go(15)
    S.wire("GND", (-50, -25), (-50, -35), (-50, -45), (-50, -55), (-50, -70))
    S.chain((-50, -70), "D", "GND").gnd()
    S.chain(("J1", "A1B12")).go(10)                           # GND bus x 45, VBUS bus x 55
    S.chain(("J1", "B1A12")).go(10)
    S.wire("GND", (45, 55), (45, -55), (45, -75))
    S.chain((45, -75), "D", "GND").gnd()
    S.chain(("J1", "A4B9")).go(20)
    S.chain(("J1", "B4A9")).go(20)
    S.wire("VBUS", (55, -45), (55, 45), (55, 80))
    S.chain((55, 80), "U", "VBUS").pwr()
    for pin, ny, rd, rs, cf in (("A5", 100, "R1", "R3", "C1"), ("B5", -110, "R2", "R4", "C2")):
        c = S.chain(("J1", pin)).to(x=75).turn("U" if ny > 0 else "D").to(y=ny).turn("R").go(25)
        c.fork("D").go(10).part(rd, "1").go(10).gnd()
        n = c.go(10).part(rs, "1").go(10)
        n.fork("D").go(10).part(cf, "1").go(10).gnd()
        n.go(20, label=True)
    S.chain(("J1", "B7")).to(x=90)                            # D- pins tied at x 90, D+ at x 100
    S.chain(("J1", "A7")).to(x=90)
    S.wire("USB_DN", (90, -5), (90, 15))
    S.chain(("J1", "A6")).to(x=100)
    S.chain(("J1", "B6")).to(x=100)
    S.wire("USB_DP", (100, -15), (100, 5))
    S.place("U12", 230, -15)
    S.wire("USB_DN", (90, 15), (165, 15))
    S.wire("USB_DP", (100, -15), (100, -45), (165, -45))
    S.chain(("U12", "2")).go(15).gnd()
    S.lab("U12", "6", 20)
    S.lab("U12", "4", 20)
    S.chain(("U12", "5")).go(15).pwr()
    return "USB-C INPUT + ESD", ["5.1k Rd on CC1/CC2: 5 V sink.", "CC levels to the ADC: source current."]


def block_chg(S):
    S.place("U2", 0, 0)
    c = S.chain(("U2", "13")).go(20).turn("U").to(y=150)         # IN: VBUS + bulk caps
    c.fork("U").go(20).pwr()
    g = c.turn("L").go(40)
    g.fork("D").go(10).part("C3", "1").go(10).gnd()
    g.go(60).fork("D").go(10).part("C4", "1").go(10).gnd()
    S.chain(("U2", "1")).go(20).part("NTC1", "1").go(10).turn("D").go(15).gnd()   # TS
    S.chain(("U2", "2")).go(15)                                    # BAT pins tied
    S.chain(("U2", "3")).go(15)
    S.wire("VBAT_P", (-75, 15), (-75, -5))
    v = S.chain((-75, -5), "L", "VBAT_P").go(185)                  # (-260, -5)
    v.fork("D").go(10).part("C6", "1").go(10).gnd()
    v.go(30)                                                       # Q1 source (-290, -5)
    S.place("Q1", -310, -15, 90)                                   # reverse-polarity P-FET: D left, S right
    S.chain(("Q1", "1")).go(10).part("R13", "1").go(10).gnd()
    S.place("J2", -450, -10, 0, mirror=True)
    S.chain(("Q1", "3")).to(x=-435)                                # BAT_RAW to J2 pin 1
    S.chain(("J2", "2")).go(10).turn("D").go(25).gnd()
    S.chain(("J2", "3")).go(15).gnd()
    S.chain(("J2", "4")).go(10).turn("L").go(30).turn("D").to(y=-50).gnd()
    for n, ref, xo in (("16", "R5", -90), ("12", "R6", -150), ("14", "R7", -210)):   # ISET, ILIM, TMR
        S.chain(("U2", n)).to(x=xo).turn("D").go(10).part(ref, "1").go(10).gnd()
    S.chain(("U2", "10")).go(15)                                   # OUT pins tied -> VSYS
    S.chain(("U2", "11")).go(15)
    S.wire("VSYS", (75, 55), (75, 65))
    j = S.chain((75, 65), "U", "VSYS").go(55)
    j.fork("U").go(20).pwr()
    j.turn("R").go(35).turn("D").go(10).part("C5", "1").go(10).gnd()
    k = S.chain(("U2", "9")).to(x=170)                             # #CHG: LED + sense diode
    k.fork("U").go(10).part("LED2", "2").go(10).part("R8", "2").go(10).pwr()
    l = k.go(40).part("D3", "1").go(20)
    l.fork("U").go(10).part("R9", "2").go(10).pwr()
    l.go(20, label=True)
    S.lab("U2", "7", 20)                                           # #PGOOD
    S.lab("U2", "6", 20)                                           # EN1
    S.lab("U2", "5", 20)                                           # EN2
    for n in ("15", "4", "17", "8"):
        S.chain(("U2", n)).go(15)
    S.wire("GND", (75, -25), (75, -35), (75, -55), (75, -65), (75, -80))
    S.chain((75, -80), "D", "GND").gnd()
    S.place("Q8", 300, -90)                                        # EN1 = NOT CHG_FAST
    m = S.chain(("Q8", "1")).go(50)
    m.fork("D").go(10).part("R11", "1").go(10).gnd()
    m.fork("U").go(10).part("R10", "1").go(10).turn("L").go(20, label=True)
    m.go(20, label=True)
    S.chain(("Q8", "2")).go(10).gnd()
    dn = S.chain(("Q8", "3")).go(10)
    dn.fork("R").go(20, label=True)
    dn.go(10).part("R12", "2").go(10).pwr()
    S.place("U4", -300, -230)                                      # fuel gauge
    S.chain(("U4", "2")).go(40)
    S.chain(("U4", "3")).go(40)
    S.wire("VBAT_P", (-390, -240), (-390, -230))
    S.chain((-390, -230), "U", "VBAT_P").go(30).pwr()
    S.chain((-390, -240), "D", "VBAT_P").go(10).part("C7", "1").go(10).gnd()
    S.lab("U4", "1", 15)
    S.chain(("U4", "4")).go(15).turn("D").go(10).gnd()
    for n in ("9", "8", "7", "6", "5"):
        S.lab("U4", n, 15)
    return "CHARGER (BQ24075) + BATTERY + FUEL GAUGE", [
        "ISET 1.1k = 0.81 A charge, ILIM 1.3k = 1.24 A in, TMR 56k = 7.5 h.",
        "CHG_FAST = 0: USB 500 mA; = 1: ILIM.  J2: pin 1 = + (Adafruit / SparkFun LiPo)."]


def block_pwr(S):
    S.place("U3", 0, 0, 0, mirror=True)            # left: VIN L1 GND L2 VOUT; right: EN MODE AGND FB PG
    S.chain(("U3", "9")).go(50).turn("U").go(25).turn("L").part("L1", "1").turn("D").go(45).turn("R").go(90)
    for n in ("10", "8", "6", "1", "2", "3", "5"):
        S.lab("U3", n, 10)
    fb = S.chain(("U3", "4")).go(70)
    fb.fork("U").go(10).part("R19", "2").go(10).pwr()
    fb.turn("D").go(10).part("R20", "1").go(10).gnd()
    for i, (ref, rail) in enumerate((("C8", "VSYS"), ("C9", "VSYS"), ("C10", "3V3"), ("C11", "3V3"), ("C12", "3V3"))):
        S.decap(-170 + 65 * i, -120, ref, rail)
    # soft power: VSYS -> Q2 -> D2 -> PWR_EN, button -> D1
    S.place("Q2", -470, 50, 270)                   # S left, D right, G up
    S.chain(("Q2", "2")).go(10).turn("U").go(15).pwr()
    ng = S.chain(("Q2", "1")).go(15)
    ng.fork("U").go(10).part("R14", "2").go(10).pwr()
    ng.turn("L").go(20, label=True)
    S.place("D2", -390, 30, 180, mirror=True)      # vertical flip: A2 top, A1 bottom
    S.chain(("Q2", "3")).to(x=-415)
    hold = S.chain(("D2", "1")).go(15)
    hold.fork("D").go(10).part("R18", "1").go(10).gnd()
    hold.go(20, label=True)
    en = S.chain(("D2", "3")).go(25)
    en.fork("D").go(10).part("R17", "1").go(10).gnd()
    en.go(20, label=True)
    S.place("D1", -400, -130)                      # A1 PWR_NG, A2 PWR_BTN_SNS, K PWR_BTN_N
    S.lab("D1", "1", 15)
    sns = S.chain(("D1", "2")).go(15).turn("D").go(20)
    sns.fork("L").go(10).part("R16", "2").go(10).turn("U").go(10).pwr()
    sns.go(10).turn("R").go(20, label=True)
    bn = S.chain(("D1", "3")).go(25)
    bn.fork("U").go(10).part("R15", "2").go(10).pwr()
    S.place("SW1", -290, -110, 270)                # pins face left: 1 top (n.c.), 2 GND, 3 PWR_BTN_N
    bn.to(x=-305)
    S.chain(("SW1", "2")).go(15).gnd()
    return "SOFT POWER + 3V3 BUCK-BOOST (TPS63802)", [
        "POWER button or USB (PGOOD) turns Q2 on; firmware holds PWR_HOLD.",
        "511k / 88.7k: 3.38 V.  PG releases ESP_EN."]


def block_mcu(S):
    S.place("U1", 0, 0)
    left, right = [], []
    for p in sym_pins("U1"):
        num = p["num"]
        if not SPEC.get(("U1", num)):
            continue
        x, y, d = S.pin("U1", num)
        if d in ("L", "R"):
            S.lab("U1", num, 20)
        else:
            (left if x < 0 else right).append((x, num))
    for i, (x, num) in enumerate(sorted(left)):                   # bottom pins fan out to the sides
        S.chain(("U1", num)).go(10 + 10 * i).turn("L").to(x=-100, label=True)
    for i, (x, num) in enumerate(sorted(right, reverse=True)):
        S.chain(("U1", num)).go(10 + 10 * i).turn("R").to(x=100, label=True)
    S.decap(-300, 80, "C14", "3V3")
    S.decap(-235, 80, "C15", "3V3")
    S.chain((-300, -90), "U", "ESP_EN").go(10).part("R22", "2").go(10).pwr()
    S.chain((-300, -90), "D", "ESP_EN").go(10).part("C13", "1").go(10).gnd()
    S.chain((-300, -90), "R", "ESP_EN").go(20, label=True)
    for k, (sw, r, c, net) in enumerate((("SW2", "R23", "C16", "BTN_A"), ("SW3", "R24", "C17", "BTN_B"))):
        x0, y0 = 330, 60 - 190 * k
        S.place(sw, x0, y0, 270)
        S.chain((sw, "2")).go(10).gnd()
        nd = S.chain((sw, "3")).go(40)
        nd.fork("U").go(10).part(r, pin_on(r, net)).go(10).pwr()
        nd.fork("D").go(10).part(c, pin_on(c, net)).go(10).gnd()
        nd.go(20, label=True)
    S.text(-110, -215, "IO45/IO46 (strapping) and TXD0/RXD0 left open.  BOOT = SW2 on IO0.")
    return "ESP32-S3 + BUTTONS", ["Flash and console over USB (USB-Serial-JTAG)."]


def block_disp(S):
    S.place("J4", 0, 0)
    for n in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "19", "20"):
        S.lab("J4", n, 30)
    for k, (r, a, b) in enumerate((("R45", "SPI_SCK", "SPI_SCK_D"), ("R46", "SPI_MOSI", "SPI_MOSI_D"))):
        y = 80 - 50 * k
        S.chain((-240, y), "L", a).go(15, label=True)
        S.chain((-240, y), "R", a).go(10).part(r, pin_on(r, a)).go(15, label=True)
    S.chain(("J4", "15")).go(15)
    S.chain(("J4", "16")).go(15)
    S.chain(("J4", "17")).go(15)
    S.wire("DISP_3VO", (-35, -65), (-35, -55), (-35, -45))
    S.chain((-35, -65), "L", "DISP_3VO").go(15, label=True)
    S.place("J3", 0, -260)
    for n in ("1", "2", "12"):
        S.lab("J3", n, 15)
    S.decap(-170, -230, "C32", "3V3")
    S.decap(-110, -230, "C33", "3V3")
    for k, (r, net) in enumerate((("R47", "TOUCH_INT"), ("R48", "SD_CD"))):
        x0 = -320 + 90 * k
        S.chain((x0, -330), "U", net).go(10).part(r, pin_on(r, net)).go(10).pwr()
        S.chain((x0, -330), "D", net).go(10).turn("L").go(15, label=True)
    return "DISPLAY: ADAFRUIT 2090 (4-wire SPI)", ["IM1-3 tied to the module's 3Vo: SPI mode, no jumpers."]


def block_sens(S):
    xs = 0
    S.place("U5", xs, 0)
    for p in sym_pins("U5"):
        S.lab("U5", p["num"], 15)
    S.place("U6", xs + 420, 0)
    for n in ("2", "3", "4", "5", "6", "8"):
        S.lab("U6", n, 15)
    vb = S.chain(("U6", "1")).go(15).turn("U").go(30).turn("L").go(90)
    vb.fork("D").go(10).part("C36", "1").go(10).gnd()
    vb.turn("U").go(10).part("R51", "2").go(10).pwr()
    S.place("U7", xs, -150)
    for p in sym_pins("U7"):
        if SPEC.get(("U7", p["num"])):
            S.lab("U7", p["num"], 15)
    S.place("U8", xs + 420, -150)
    for n in ("1", "2", "3", "4", "6"):
        S.lab("U8", n, 15)
    S.chain(("U8", "7")).go(10).gnd()
    for i, (ref, rail) in enumerate((("C34", "3V3"), ("C35", "3V3"), ("C37", "3V3"), ("C38", "3V3"), ("C39", "3V3"))):
        S.decap(-90 + 65 * i, -300, ref, rail)
    for k, (r, net) in enumerate((("R49", "I2C_SDA"), ("R50", "I2C_SCL"), ("R52", "RTC_INT"))):
        x0 = 320 + 90 * k
        S.chain((x0, -320), "U", net).go(10).part(r, pin_on(r, net)).go(10).pwr()
        S.chain((x0, -320), "D", net).go(10).turn("L").go(15, label=True)
    return "I2C SENSORS: BME280, RTC, IMU, LIGHT", ["Addresses 0x76, 0x51, 0x19, 0x44 (+ gauge 0x36, touch 0x38)."]


def block_hv(S):
    # power path along the top: 3V3 -> R21 -> HV_VIN -> L2 -> HV_SW -> D4 / C25 doubler -> D6 -> HV_OUT
    S.chain((-260, 60), "U", "3V3").go(10).pwr()
    vin = S.chain((-260, 60), "R", "3V3").go(10).part("R21", "1").go(20)
    vin.fork("D").go(10).part("C18", "1").go(10).gnd()
    vin.go(60).fork("D").go(10).part("C19", "1").go(10).gnd()
    sw = vin.go(20).part("L2", "1").go(30)                         # HV_SW node
    S.place("Q3", sw.x - 10, sw.y - 120)                            # collector up, emitter down, base left
    sw.fork("D").to(y=S.pin("Q3", "3")[1])
    pump = sw.fork("U").go(50)
    v1 = sw.go(20).part("D4", "2").go(30)                          # HV_V1 node
    v1.fork("D").go(10).part("C24", "1").go(10).gnd()
    mm = v1.go(30).part("D5", "2").go(30)                          # HV_M node
    pump.turn("R").go(30).part("C25", "1").to(x=mm.x).turn("D").to(y=mm.y)
    out = mm.go(20).part("D6", "2").go(30)                         # HV_OUT rail
    for ref in ("C26", "C27", "D7"):
        out.fork("D").go(10).part(ref, pin_on(ref, "HV_OUT")).go(10).gnd()
        out.go(60)
    d = out.fork("D").go(10)                                       # 3 x 100M / 1M feedback divider
    for ref in ("R30", "R31", "R32"):
        d.part(ref, pin_on(ref, d.net)).go(10)
    d.fork("D").go(10).part("R33", "1").go(10).gnd()
    d.fork("R").go(40, label=True).turn("D").go(10).part("C28", "1").go(10).gnd()
    d.turn("L").go(10).part("R34", "1").go(10, label=True)
    out.go(100)
    b = out.fork("D").go(10)                                       # 3 x 47M bleeder
    for ref in ("R58", "R59", "R60"):
        b.part(ref, pin_on(ref, b.net)).go(10)
    b.gnd()
    out.go(40, label=True)
    # drive: HV_PWM AND HV_COMP -> R25 (with C20 across it) -> Q3 base
    qb = S.chain(("Q3", "1")).go(10)                               # HV_BASE node
    qb.fork("D").go(10).part("R26", "1").go(10).gnd()
    S.chain(("Q3", "2")).go(10).gnd()
    qb.fork("U").go(20).turn("L").part("C20", "2").go(30).turn("D").go(20)
    drv = qb.go(10).part("R25", "2").go(10)                        # HV_DRV node
    S.place("U10", drv.x - 100, drv.y + 10)
    S.wire("HV_DRV", (drv.x, drv.y), S.pin("U10", "4")[:2])
    S.lab("U10", "5", 10)
    S.chain(("U10", "3")).go(5).turn("D").go(15).gnd()
    pw = S.chain(("U10", "1")).go(45)                               # HV_PWM with its pull-down
    pw.fork("D").go(10).part("R27", "1").go(10).gnd()
    pw.go(20, label=True)
    S.place("U9", drv.x - 100, drv.y - 110)
    S.chain(("U9", "1")).go(30).turn("U").to(y=S.pin("U10", "2")[1]).turn("R").to(x=S.pin("U10", "2")[0])
    S.lab("U9", "2", 10)
    S.lab("U9", "5", 10)
    S.chain(("U9", "4")).go(10).turn("D").go(20).turn("R").go(30, label=True)
    node = S.chain(("U9", "3")).go(45)
    node.fork("D").go(10).part("R29", "1").go(10).gnd()
    c23 = node.go(45)
    c23.fork("D").go(10).part("C23", "1").go(10).gnd()
    c23.go(25).part("R28", "2").go(10, label=True)
    S.decap(drv.x + 60, drv.y - 130, "C21", "3V3")
    S.decap(drv.x + 125, drv.y - 130, "C22", "3V3")
    return "HV SUPPLY: BOOST + DOUBLER, COMPARATOR-GATED (~400 V)", [
        "HV_FB = HV_OUT / 301.  HV_REF ceiling 3.38 x 75/175 x 301 = 436 V.",
        "Regulation is in hardware (TLV7011 gates the PWM).  SMAJ440A clamp, 3 x 47M bleeder."]


def block_gm(S):
    S.place("U11", 520, -80)
    for k, (ra, rb, ja, jk, rk, rs, cb, q, rc, gin) in enumerate((
            ("R35", "R36", "J5", "J6", "R37", "R38", "C29", "Q4", "R39", "1"),
            ("R40", "R41", "J7", "J8", "R42", "R43", "C30", "Q5", "R44", "3"))):
        y0 = -160 * k
        S.chain((-20, y0), "L", "HV_OUT").go(20, label=True)
        c = S.chain((-20, y0), "R", "HV_OUT")
        c.go(10).part(ra, "1").go(10).part(rb, pin_on(rb, c.net)).go(10)
        S.place(ja, c.x + 10, y0)
        S.place(jk, c.x + 110, y0, 0, mirror=True)
        S.text(c.x + 25, y0 + 12, ("STS-5" if k == 0 else "SI-3BG") + " tube (case bay)", 7)
        kk = S.chain((jk, "1")).go(20)
        kk.fork("D").go(10).part(rk, "1").go(10).gnd()
        bb = kk.go(10).part(rs, "1").go(10)
        bb.fork("D").go(10).part(cb, "1").go(10).gnd()
        S.place(q, bb.x + 20, bb.y)
        bb.go(10)
        S.chain((q, "2")).go(10).gnd()
        cc = S.chain((q, "3")).go(10)
        cc.fork("U").go(10).part(rc, pin_on(rc, cc.net)).go(10).pwr()
        cc.turn("R").to(x=S.pin("U11", gin)[0] - 20).turn("D" if k == 0 else "U").to(y=S.pin("U11", gin)[1]).turn("R").go(20)
    S.lab("U11", "2", 15)
    S.lab("U11", "5", 15)
    S.lab("U11", "6", 20)
    S.lab("U11", "4", 20)
    S.decap(650, -230, "C31", "3V3")
    return "GM TUBES: STS-5 + SI-3BG (cathode-sensed)", ["Anode: STS-5 9.4 MΩ, SI-3BG 4.4 MΩ.  Pulses to PCNT."]


def block_out(S):
    S.place("BZ1", 60, 0)
    p = S.chain(("BZ1", "1")).go(45)
    p.fork("U").go(20).pwr()
    drv = p.turn("D").go(10).part("D8", "1").go(10)
    S.chain(("BZ1", "2")).go(15).turn("D").to(y=drv.y).turn("L").to(x=drv.x)
    S.place("Q6", drv.x - 10, drv.y - 30)
    drv.go(10)
    S.chain(("Q6", "2")).go(10).gnd()
    g = S.chain(("Q6", "1")).go(10)
    g.fork("D").go(10).part("R54", "1").go(10).gnd()
    g.go(10).part("R53", "2").go(10, label=True)
    S.place("J9", 230, 30, 0)
    S.place("J10", 230, -20, 0)
    S.chain(("J9", "1")).go(20)
    m = S.chain(("J10", "1")).go(20)
    m.fork("U").go(10).part("D9", "2").go(10).pwr()
    S.place("Q7", m.x - 10, m.y - 40)
    m.turn("D").go(20)
    S.chain(("Q7", "2")).go(10).gnd()
    g = S.chain(("Q7", "1")).go(10)
    g.fork("D").go(10).part("R56", "1").go(10).gnd()
    g.go(10).part("R55", "2").go(10, label=True)
    S.text(240, 50, "coin motor", 7)
    S.place("LED1", 420, 0)
    S.chain(("LED1", "3")).go(10).part("R57", "2").go(10, label=True)
    S.lab("LED1", "4", 15)
    S.chain(("LED1", "2")).go(15).turn("D").go(10).gnd()
    S.decap(540, -60, "C40", "3V3")
    S.decap(610, -60, "C41", "3V3")
    return "BUZZER, VIBRATION, RGB LED", []


BLOCKS = {"usb": block_usb, "chg": block_chg, "pwr": block_pwr, "mcu": block_mcu, "disp": block_disp,
          "sens": block_sens, "hv": block_hv, "gm": block_gm, "out": block_out}
ROWS = [["usb", "chg", "pwr"], ["mcu", "disp", "sens"], ["hv", "gm", "out"]]


# =====================================================================================================
# Geometry for the checks
# =====================================================================================================

def part_body(S, ref):
    x, y, rot, mir = S.parts[ref]
    bases = []
    for p in sym_pins(ref):
        px, py, d = S.pin(ref, p["num"])
        ux, uy = DIRV[d]
        bases.append((px - ux * PIN_LEN, py - uy * PIN_LEN))
    xs = [b[0] for b in bases] + [x]
    ys = [b[1] for b in bases] + [y]
    m = 5 if len(bases) > 1 else 6
    return min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m


def is_axial(S, ref):
    pins = sym_pins(ref)
    if len(pins) != 2:
        return None
    a, b = (S.pin(ref, p["num"]) for p in pins)
    return "h" if a[1] == b[1] else "v"


def _abox(px, py, al, w):
    """Text box for an anchor and alignment (1 LT, 2 LM, 3 LB, 4 CT, 5 C, 6 CB, 7 RT, 8 RM, 9 RB)."""
    x0 = px - w / 2 if al in (4, 5, 6) else (px - w if al in (7, 8, 9) else px)
    y0 = py - TH if al in (1, 4, 7) else (py - TH / 2 if al in (2, 5, 8) else py)
    return (x0, y0, x0 + w, y0 + TH)


def attr_candidates(S, ref):
    """Designator / value placements to try, best first: list of ((x, y, align), (x, y, align))."""
    x, y = S.parts[ref][:2]
    b = part_body(S, ref)
    ax = is_axial(S, ref)
    if ax == "h":
        return [((x, y + 6, 6), (x, y - 6, 4)),                         # above / below
                ((x, y + 6 + TH, 6), (x, y + 6, 6)),                     # both above
                ((x, y - 6, 4), (x, y - 6 - TH, 4))]                     # both below
    if ax == "v":
        return [((x + 8, y + 1, 3), (x + 8, y - 1, 1)),                 # right
                ((x - 8, y + 1, 9), (x - 8, y - 1, 7)),                 # left
                ((x + 8, y + 6 + TH, 3), (x + 8, y + 6, 3)),
                ((x - 8, y - 6, 7), (x - 8, y - 6 - TH, 7))]
    x0, y0, x1, y1 = b[0] + 5, b[1] + 5, b[2] - 5, b[3] - 5
    return [((x0, y1 + 3, 3), (x0, y0 - 3, 1)),                       # above / below the body
            ((x0, y1 + 3 + TH, 3), (x0, y1 + 3, 3)),                    # both above
            ((x0, y0 - 3, 1), (x0, y0 - 3 - TH, 1)),                    # both below
            ((x1 + 4, y + 1, 3), (x1 + 4, y - 1, 1)),                   # right
            ((x0 - 4, y + 1, 9), (x0 - 4, y - 1, 7)),                   # left
            ((x1 + 4, y1 + 3, 3), (x1 + 4, y1 + 3 - TH, 3)),            # top right corner
            ((x0 - 4, y0 - 3, 7), (x0 - 4, y0 - 3 - TH, 7)),            # bottom left corner
            ((x1 + 4, y0 - 3, 1), (x1 + 4, y0 - 3 - TH, 1)),            # bottom right corner
            ((x0 - 4, y1 + 3 + TH, 9), (x0 - 4, y1 + 3, 9)),            # top left corner
            ((x1 + 4, y - 8, 1), (x1 + 4, y - 8 - TH, 1)),              # right, lower
            ((x0 - 4, y - 8, 7), (x0 - 4, y - 8 - TH, 7))]              # left, lower


def attr_layout(S, ref):
    """Designator and value text: {"des"|"val": (x, y, align, box)}."""
    wd, wv = CW * len(ref), CW * len(VALUES.get(ref, ""))
    d, v = S.attr.get(ref) or attr_candidates(S, ref)[0]
    return {"des": (*d, _abox(*d, wd)), "val": (*v, _abox(*v, wv))}


def place_attrs(S):
    """Give every part's name and value the first candidate spot that touches nothing else."""
    S.attr = {}
    fixed = [b for b in all_boxes(S, attrs=False)]

    def free(ref, placed):
        wd, wv = CW * len(ref), CW * len(VALUES.get(ref, ""))
        out = []
        for d, v in attr_candidates(S, ref):
            bd, bv = _abox(*d, wd), _abox(*v, wv)
            hit = any(boxes_hit(bx, ob) for bx in (bd, bv) for o, k, ob in fixed if not (o == ref and k == "body"))                 or any(boxes_hit(bx, ob) for bx in (bd, bv) for ob in placed)                 or any(seg_hits_box(a, b, bx) for bx in (bd, bv) for _, a, b, _ in S.segs)
            if not hit:
                out.append((d, v, bd, bv))
        return out

    placed = []
    todo = sorted(S.parts, key=lambda r: (len(free(r, [])), r))   # most constrained first
    for ref in todo:
        ok = free(ref, placed)
        if ok:
            d, v, bd, bv = ok[0]
        else:
            d, v = attr_candidates(S, ref)[0]
            wd, wv = CW * len(ref), CW * len(VALUES.get(ref, ""))
            bd, bv = _abox(*d, wd), _abox(*v, wv)
        S.attr[ref] = (d, v)
        placed += [bd, bv]


def flag_box(kind, net, x, y, rot, d):
    ux, uy = DIRV[d]
    L = 16 if kind == "Ground" else 14 + (CW * len(net) if d in ("L", "R") else TH)
    a = (x + ux * 2, y + uy * 2)
    b = (x + ux * L, y + uy * L)
    w = 10 if kind == "Ground" else max(10, CW * len(net) / 2 + 2) if d in ("U", "D") else 7
    return (min(a[0], b[0]) - (w if uy else 0), min(a[1], b[1]) - (w if ux else 0),
            max(a[0], b[0]) + (w if uy else 0), max(a[1], b[1]) + (w if ux else 0))


def label_box(net, a, b):
    w = CW * len(net)
    if a[1] == b[1]:
        if b[0] > a[0]:
            return b[0] + 2, b[1] - TH / 2, b[0] + 2 + w, b[1] + TH / 2
        return b[0] - 2 - w, b[1] - TH / 2, b[0] - 2, b[1] + TH / 2
    if b[1] > a[1]:
        return b[0] - TH / 2, b[1] + 2, b[0] + TH / 2, b[1] + 2 + w
    return b[0] - TH / 2, b[1] - 2 - w, b[0] + TH / 2, b[1] - 2


def text_box(t):
    x, y, s, size, bold = t
    return x, y, x + len(s) * size * 0.62, y + size * 1.1


def on_seg(p, a, b):
    if p == a or p == b:
        return False
    if a[0] == b[0] == p[0]:
        return min(a[1], b[1]) < p[1] < max(a[1], b[1])
    if a[1] == b[1] == p[1]:
        return min(a[0], b[0]) < p[0] < max(a[0], b[0])
    return False


def boxes_hit(p, q):
    return p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3]


def seg_hits_box(a, b, box):
    x0, y0, x1, y1 = box
    if a[0] == b[0]:
        return x0 < a[0] < x1 and max(min(a[1], b[1]), y0) < min(max(a[1], b[1]), y1)
    return y0 < a[1] < y1 and max(min(a[0], b[0]), x0) < min(max(a[0], b[0]), x1)


def all_boxes(S, attrs=True):
    out = []   # (owner, kind, box)
    for r in S.parts:
        out.append((r, "body", part_body(S, r)))
        if attrs:
            for key, (px, py, al, box) in attr_layout(S, r).items():
                out.append((r, key, box))
    for i, f in enumerate(S.flags):
        out.append((f"flag{i}", f"{f[0]} {f[1]} at {f[2]},{f[3]}", flag_box(*f)))
    for i, s in enumerate(S.segs):
        if s[3]:
            out.append((f"lab{i}", f"label {s[0]} at {s[2]}", label_box(s[0], s[1], s[2])))
    for i, t in enumerate(S.texts):
        out.append((f"text{i}", f"text '{t[2][:20]}'", text_box(t)))
    return out


# =====================================================================================================
# Checks
# =====================================================================================================

def check(S, full=True):
    errs = []
    parent = {}

    def find(k):
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        parent[find(a)] = find(b)

    terms = []
    for ref in S.parts:
        for p in sym_pins(ref):
            x, y, _ = S.pin(ref, p["num"])
            terms.append(((x, y), "pin", (ref, p["num"])))
    for kind, net, x, y, rot, d in S.flags:
        terms.append(((x, y), "flag", net))
    for net, a, b, lab in S.segs:
        union(("pt", a), ("pt", b))
    for pt, kind, pay in terms:
        union(("pt", pt), (kind, pt, pay))
    points = [(pt, f"{kind} {pay}") for pt, kind, pay in terms] + \
             [(s[1], f"{s[0]} wire end") for s in S.segs] + [(s[2], f"{s[0]} wire end") for s in S.segs]
    for net, a, b, lab in S.segs:
        for pt, what in points:
            if on_seg(pt, a, b):
                errs.append(f"{what} at {pt} touches the middle of a {net} wire {a}-{b}")
    names = {}
    for net, a, b, lab in S.segs:
        names.setdefault(find(("pt", a)), set()).add(net)
    for pt, kind, pay in terms:
        if kind == "flag":
            names.setdefault(find(("pt", pt)), set()).add(pay)
    pin_pts = {}
    for pt, kind, pay in terms:
        if kind == "pin":
            pin_pts.setdefault(pt, []).append(pay)
    seg_pts = {s[1] for s in S.segs} | {s[2] for s in S.segs} | {(f[2], f[3]) for f in S.flags}
    for pt, kind, pay in terms:
        if kind != "pin":
            continue
        nm = names.get(find(("pt", pt)), set())
        if len(nm) > 1:
            errs.append(f"pin {pay} joins differently named wires {sorted(nm)}")
        touched = pt in seg_pts or len(pin_pts[pt]) > 1
        drawn = next(iter(nm)) if (nm and touched) else ""
        want = SPEC.get(pay, "")
        if drawn != want:
            errs.append(f"{pay[0]}.{pay[1]}: drawn {drawn or '-'} / spec {want or '-'}")
        if len(pin_pts[pt]) > 1:
            errs.append(f"pins touching each other at {pt}: {pin_pts[pt]}")
    if full:
        missing = sorted(set(PARTS) - set(S.parts))
        if missing:
            errs.append(f"not placed: {missing}")
    # reads clean: nothing overlaps, no wire runs through a symbol, label, name or note
    boxes = all_boxes(S)
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if boxes[i][0] == boxes[j][0]:
                continue
            if boxes_hit(boxes[i][2], boxes[j][2]):
                errs.append(f"overlap: {boxes[i][0]} {boxes[i][1]} / {boxes[j][0]} {boxes[j][1]}")
    own_pins = {}
    for ref in S.parts:
        own_pins[ref] = {S.pin(ref, p["num"])[:2] for p in sym_pins(ref)}
    for net, a, b, lab in S.segs:
        for owner, kind, box in boxes:
            if seg_hits_box(a, b, box):
                errs.append(f"{net} wire {a}-{b} crosses {owner} {kind}")
    return errs


# =====================================================================================================
# Packing onto the sheet
# =====================================================================================================

def bbox(S):
    bs = [b for _, _, b in all_boxes(S)] + [(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
                                           for _, a, b, _ in S.segs]
    return min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)


def build(only=None):
    blocks = []                        # per row: [(name, Sheet, title, notes, w, h, x0, y1)]
    for row in ROWS:
        rb = []
        for name in row:
            if only and name not in only:
                continue
            S = Sheet()
            title, notes = BLOCKS[name](S)
            place_attrs(S)
            x0, y0, x1, y1 = bbox(S)
            pad, head = 18, 22 + 13 * len(notes)
            rb.append([name, S, title, notes, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad + head, x0 - pad, y1 + pad + head])
        blocks.append(rb)
    gap_x = 70
    heights = [max(b[5] for b in rb) for rb in blocks if rb]
    top, bottom = INNER[3] - 20, TITLE_BLOCK[3] + 40
    gap_y = max(40, (top - bottom - sum(heights)) / (len(heights) + 1))
    master, report = Sheet(), []
    y_top = top - gap_y / 2
    for rb, h in zip([rb for rb in blocks if rb], heights):
        width = sum(b[4] for b in rb) + gap_x * (len(rb) - 1)
        x = INNER[0] + ((INNER[2] - INNER[0]) - width) / 2
        for name, S, title, notes, w, bh, bx0, by1 in rb:
            dx, dy = round(x - bx0), round(y_top - by1)
            S.shift(dx, dy)
            fx0, fy1 = round(x), round(y_top)
            S.rects.append([fx0, fy1 - round(bh), fx0 + round(w), fy1])
            S.text(fx0 + 10, fy1 - 20, title, 12, True)
            for i, n in enumerate(notes):
                S.text(fx0 + 10, fy1 - 34 - 13 * i, n, 8)
            master.merge(S)
            report.append((name, round(w), round(bh), fx0, fy1 - round(bh)))
            x += w + gap_x
        y_top -= h + gap_y
    return master, report


def render(S, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, ax = plt.subplots(figsize=(46.8, 33), dpi=50)
    ax.add_patch(Rectangle((SHEET[0], SHEET[1]), SHEET[2], SHEET[3], fill=False, ec="#800000", lw=2))
    ax.add_patch(Rectangle((TITLE_BLOCK[0], TITLE_BLOCK[1]), TITLE_BLOCK[2] - TITLE_BLOCK[0], TITLE_BLOCK[3] - TITLE_BLOCK[1],
                           fill=True, fc="#f0e0e0", ec="#800000"))
    for r in S.rects:
        ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fill=False, ec="#1f4e79", lw=1.2))
    for owner, kind, b in all_boxes(S):
        if kind == "body":
            ax.add_patch(Rectangle((b[0] + 5, b[1] + 5), b[2] - b[0] - 10, b[3] - b[1] - 10, fill=False, ec="#a00000", lw=1))
    for ref in S.parts:
        for p in sym_pins(ref):
            x, y, d = S.pin(ref, p["num"])
            ux, uy = DIRV[d]
            ax.plot([x, x - ux * PIN_LEN], [y, y - uy * PIN_LEN], color="#a00000", lw=0.8)
        for key, (px, py, al, box) in attr_layout(S, ref).items():
            ax.text(box[0], box[1], ref if key == "des" else VALUES.get(ref, ""), fontsize=5,
                    color="#a00000" if key == "des" else "#606060", va="bottom")
    for net, a, b, lab in S.segs:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#008000", lw=1)
        if lab:
            bx = label_box(net, a, b)
            ax.text(bx[0], bx[1], net, fontsize=5, color="#0000a0", va="bottom",
                    rotation=90 if a[0] == b[0] else 0)
    for kind, net, x, y, rot, d in S.flags:
        bx = flag_box(kind, net, x, y, rot, d)
        ax.add_patch(Rectangle((bx[0], bx[1]), bx[2] - bx[0], bx[3] - bx[1], fill=True,
                               fc="#c0c0ff" if kind == "Power" else "#d0d0d0", ec="none"))
        if kind == "Power":
            ax.text((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2, net, fontsize=4, ha="center", va="center")
    for t in S.texts:
        ax.text(t[0], t[1], t[2], fontsize=t[3] * 0.6, fontweight="bold" if t[4] else "normal", color="#1f4e79", va="bottom")
    ax.set_xlim(-20, SHEET[2] + 20)
    ax.set_ylim(-20, SHEET[3] + 20)
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out)
    print("preview:", out)


SCH_PAGE = "78286f62bfd019a0"
OPEN = "await eda.dmt_EditorControl.openDocument('" + SCH_PAGE + "');\n"


def _run(js, what, timeout=60):
    from eda import run
    r = run(OPEN + js, timeout=timeout, retry_on_drop=False)
    if not r.get("success"):
        raise SystemExit(f"{what} failed: {r.get('error')}")
    return r["result"]


CLEAR_JS = r"""
const wires = await eda.sch_PrimitiveWire.getAll();
const comps = await eda.sch_PrimitiveComponent.getAll();
const flags = comps.filter(c => ['netflag', 'netport'].includes(c.getState_ComponentType()));
const texts = await eda.sch_PrimitiveText.getAll();
const rects = await eda.sch_PrimitiveRectangle.getAll();
const out = { wires: wires.length, flags: flags.length, texts: texts.length, rects: rects.length };
if (wires.length) out.dw = await eda.sch_PrimitiveWire.delete(wires.map(w => w.getState_PrimitiveId()));
if (flags.length) out.df = await eda.sch_PrimitiveComponent.delete(flags.map(c => c.getState_PrimitiveId()));
if (texts.length) out.dt = await eda.sch_PrimitiveText.delete(texts.map(t => t.getState_PrimitiveId()));
if (rects.length) out.dr = await eda.sch_PrimitiveRectangle.delete(rects.map(r => r.getState_PrimitiveId()));
return out;
"""
IDS_JS = r"""
const out = {};
for (const c of await eda.sch_PrimitiveComponent.getAll('part')) out[c.getState_Designator()] = c.getState_PrimitiveId();
return out;
"""
MOVE_JS = r"""
let n = 0;
for (const [id, x, y, rot, mir] of __ITEMS__) {
  if (await eda.sch_PrimitiveComponent.modify(id, { x, y, rotation: rot, mirror: mir })) n++;
}
return n;
"""
PINS_JS = r"""
const out = {};
for (const [r, id] of __ITEMS__) {
  out[r] = ((await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(id)) || [])
    .map(p => [p.getState_PinNumber(), p.getState_X(), p.getState_Y()]);
}
return out;
"""
WIRES_JS = r"""
let n = 0;
for (const [net, line, lab, lx, ly, al] of __ITEMS__) {
  const w = await eda.sch_PrimitiveWire.create(line, net);
  if (!w) continue;
  n++;
  const at = (await eda.sch_PrimitiveAttribute.getAll(w.getState_PrimitiveId())).find(a => a.getState_Key() === 'Name');
  if (at) await eda.sch_PrimitiveAttribute.modify(at.getState_PrimitiveId(),
    lab ? { valueVisible: true, x: lx, y: ly, alignMode: al, rotation: 0 } : { valueVisible: false });
}
return n;
"""
FLAGS_JS = r"""
let n = 0;
for (const [kind, net, x, y, rot] of __ITEMS__) {
  if (await eda.sch_PrimitiveComponent.createNetFlag(kind, net, x, y, rot)) n++;
}
return n;
"""
ATTRS_JS = r"""
let n = 0;
for (const [id, d, v] of __ITEMS__) {
  for (const a of await eda.sch_PrimitiveAttribute.getAll(id)) {
    const k = a.getState_Key();
    const t = k === 'Designator' ? d : (k === 'Name' ? v : null);
    if (t) { await eda.sch_PrimitiveAttribute.modify(a.getState_PrimitiveId(), { x: t[0], y: t[1], alignMode: t[2], rotation: 0 }); n++; }
  }
}
return n;
"""
TEXTS_JS = r"""
let n = 0;
for (const [x, y, s, size, bold] of __TEXTS__) {
  if (await eda.sch_PrimitiveText.create(x, y, s, 0, '#1f4e79', null, size, bold, false, false, 3)) n++;
}
for (const [x0, y0, x1, y1] of __RECTS__) {
  if (await eda.sch_PrimitiveRectangle.create(x0, y1, x1 - x0, y1 - y0, 0, 0, '#1f4e79', null, 1)) n++;
}
return n;
"""


def _detached(body, what, total=None):
    """Run a JS body (which returns a value) as a detached job inside EasyEDA and poll it. Slow API calls outlast
    the bridge's 30 s request limit, and the editor can be too busy to answer a poll: both are waited out."""
    import time
    from eda import run
    tag = f"j{int(time.time() * 1000)}"
    # each job writes only to its own state object, so a stale job can never complete a newer one
    start = ("const job = { tag: '" + tag + "', done: false, n: 0 };\nglobalThis.__ddJob = job;\n(async () => {\n" + body +
             "\n})().then(r => { job.result = r; job.done = true; })"
             ".catch(e => { job.error = String(e); job.done = true; });\nreturn 'started';")
    _run(start, what)
    while True:
        time.sleep(3)
        try:
            st = run("return globalThis.__ddJob;", timeout=30).get("result") or {}
        except Exception:
            print(f"  {what}: editor busy", flush=True)
            continue
        if st.get("tag") != tag:
            raise SystemExit(f"{what}: job state replaced by another job")
        if st.get("done"):
            if st.get("error"):
                raise SystemExit(f"{what} failed: {st['error']}")
            return st.get("result")
        if total:
            print(f"  {what}: {st.get('n', 0)}/{total}", flush=True)


def _batches(js, items, what, size=None):
    body = js.replace("let n = 0;", "let n = 0; job.total = __ITEMS__.length;") \
             .replace("n++;", "n++; job.n = n;").replace("__ITEMS__", json.dumps(items))
    return _detached(OPEN + body, what, len(items))


def push(S):
    """Rebuild the page: clear wires / symbols / texts / frames, move every part, verify its pins, then draw."""
    print("clear:", _detached(OPEN + CLEAR_JS, "clear"))
    ids = _detached(OPEN + IDS_JS, "ids")
    refs = sorted(S.parts)
    print("moved:", _batches(MOVE_JS, [[ids[r], *S.parts[r][:3], bool(S.parts[r][3])] for r in refs], "move"))
    bad = []
    got = _detached(OPEN + PINS_JS.replace("__ITEMS__", json.dumps([[r, ids[r]] for r in refs])), "pins")
    for r, pins in got.items():
        for num, x, y in pins:
            want = S.pin(r, num)[:2]
            if (round(x, 2), round(y, 2)) != (round(want[0], 2), round(want[1], 2)):
                bad.append((r, num, (x, y), want))
    if bad:
        raise SystemExit(f"pin positions differ from the layout, nothing drawn: {bad[:10]}")
    print("every pin is where the layout expects it")
    wires = []
    for net, a, b, lab in S.segs:
        if lab:
            assert a[1] == b[1], ("vertical label", net, a, b)
            right = b[0] > a[0]
            wires.append([net, [a[0], a[1], b[0], b[1]], True, b[0] + (3 if right else -3), b[1], 2 if right else 8])
        else:
            wires.append([net, [a[0], a[1], b[0], b[1]], False, 0, 0, 0])
    print("wires:", _batches(WIRES_JS, wires, "wires"))
    print("symbols:", _batches(FLAGS_JS, [f[:5] for f in S.flags], "symbols"))
    attrs = []
    for r in refs:
        lay = attr_layout(S, r)
        attrs.append([ids[r], list(lay["des"][:3]), list(lay["val"][:3])])
    print("names/values:", _batches(ATTRS_JS, attrs, "names"))
    print("texts + frames:", _detached(OPEN + TEXTS_JS.replace("__TEXTS__", json.dumps(S.texts))
                                       .replace("__RECTS__", json.dumps(S.rects)), "texts"))
    print("saved:", _detached(OPEN + "return await eda.sch_Document.save();", "save"))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    only = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
    S, report = build(only)
    for r in report:
        print("block", r)
    errs = check(S, full=not only)
    ext = bbox(S)
    print(f"{len(S.parts)} parts, {len(S.segs)} wires, {len(S.flags)} symbols; extent {[round(v) for v in ext]}; "
          f"{len(errs)} errors")
    if ext[0] < INNER[0] or ext[1] < INNER[1] or ext[2] > INNER[2] or ext[3] > INNER[3]:
        print("   DOES NOT FIT the A2 frame", INNER)
    for e in errs[:80]:
        print("  ", e)
    if sys.argv[1] == "check":
        render(S, sys.argv[2] if len(sys.argv) > 2 else "sch_preview.png")
    if sys.argv[1] == "push":
        if errs or only:
            raise SystemExit("not pushed: the layout must check clean, all blocks")
        push(S)
    return S, errs


if __name__ == "__main__":
    main()
