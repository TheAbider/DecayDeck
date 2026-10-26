"""Turn design.py into a SPICE netlist, so a simulation runs the board's own connectivity: every resistor, capacitor,
inductor, diode, transistor and logic chip of the chosen blocks, with its design.py value, wired by design.py's nets.
Whatever lies outside those blocks (the ESP32, the 3V3 regulator, the tubes on their pads) the test bench supplies
as sources and loads; netlist() returns those boundary nets so a bench can't silently leave one floating.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
V4 = os.path.dirname(HERE)
_cwd = os.getcwd()
os.chdir(V4)                     # check_spec / design read their JSON relative to hardware/v4
sys.path.insert(0, V4)
from check_spec import resolved_nets, pins_of
from design import PARTS
os.chdir(_cwd)

NETS, _errs = resolved_nets()
SPEC = {m: n for n, ms in NETS.items() for m in ms}

# semiconductors by the value's first token: (element letter, model or subckt)
SEMIS = {
    "FMMT458TA": ("Q", "FMMT458"),
    "BC847C": ("Q", "BC847C"),
    "US1M": ("D", "us1m"),
    "SMAJ440A": ("X", "SMAJ440A"),
    "TLV7011": ("X", "TLV7011"),
    "SN74LVC1G08": ("X", "SN74LVC1G08"),
    "74LVC2G17": ("X", "74LVC2G17"),
}
INDUCTORS = {"C2997659": (6.0, "10p")}     # PNLS6045-102M: DCR 6 ohm, Isat 400 mA (LCSC); ~10 pF self-capacitance
BJT_PINS = {"C": "3", "B": "1", "E": "2"}  # SOT-23 BJT: 1 B, 2 E, 3 C
UNITS = {"p": "p", "n": "n", "u": "u", "m": "m", "k": "k", "M": "Meg", "G": "G", "R": ""}


def spice_value(text):
    """'10R 1206 0.5W' -> '10', '4.7M 1206' -> '4.7Meg', '10nF 1kV' -> '10n', '1mH' -> '1m', '2R2' -> '2.2'."""
    tok = text.split()[0]
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([pnumkMGR]?)(\d*)(F|H)?", tok)
    if not m:
        raise ValueError(f"can't read value {text!r}")
    num, unit, frac, _ = m.groups()
    if frac:
        num = f"{num}.{frac}"
    return num + UNITS.get(unit, "")


def node(net):
    return "0" if net == "GND" else net


def pin_node(ref, num):
    return node(SPEC.get((ref, num), f"NC_{ref}_{num}"))


def netlist(blocks, scale=None):
    """SPICE lines for every part in `blocks`, plus {boundary net: [(ref, pin), ...] outside the blocks}.
    scale: {ref: factor} applied to a part's value (e.g. ceramic DC-bias derating)."""
    scale = scale or {}
    refs = sorted(r for r, (lcsc, val, blk, bom) in PARTS.items() if blk in blocks and lcsc != "PAD_TH")
    lines, used = [], set()
    for ref in refs:
        lcsc, val, blk, bom = PARTS[ref]
        pins = sorted(pins_of(ref), key=lambda p: int(p["num"]))
        nodes = {p["num"]: pin_node(ref, p["num"]) for p in pins}
        names = {p["name"]: pin_node(ref, p["num"]) for p in pins}
        used.update((ref, p["num"]) for p in pins)
        k = scale.get(ref, 1.0)
        kind = ref.rstrip("0123456789")
        if kind in ("R", "C") and lcsc in INDUCTORS:
            raise ValueError(ref)
        if kind == "R":
            lines.append(f"R{ref[1:]} {nodes['1']} {nodes['2']} {{{spice_value(val)}*{k}}}  ; {val}")
        elif kind == "C":
            lines.append(f"C{ref[1:]} {nodes['1']} {nodes['2']} {{{spice_value(val)}*{k}}}  ; {val}")
        elif kind == "L":
            dcr, cpar = INDUCTORS[lcsc]
            mid = f"{ref}_dcr"
            lines += [f"L{ref[1:]} {nodes['1']} {mid} {spice_value(val)}  ; {val}",
                      f"R{ref}dcr {mid} {nodes['2']} {dcr}",
                      f"C{ref}par {nodes['1']} {nodes['2']} {cpar}"]
        else:
            letter, model = SEMIS[val.split()[0]]
            if letter == "Q":
                lines.append(f"Q{ref[1:]} {nodes[BJT_PINS['C']]} {nodes[BJT_PINS['B']]} {nodes[BJT_PINS['E']]} {model}  ; {val}")
            elif letter == "D":
                lines.append(f"D{ref[1:]} {names['A']} {names['K']} {model}  ; {val}")
            else:
                lines.append(f"X{ref} {' '.join(nodes[p['num']] for p in pins)} {model}  ; {val}")
    boundary = {}
    for (ref, num) in used:
        net = SPEC.get((ref, num))
        if net is None or net == "GND":
            continue
        outside = [m for m in NETS[net] if m[0] not in refs]
        if outside:
            boundary[net] = sorted(outside)
    return lines, boundary


if __name__ == "__main__":
    lines, boundary = netlist({"hv", "gm"})
    print("\n".join(lines))
    print("* boundary:", boundary)
