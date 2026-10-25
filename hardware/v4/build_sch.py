"""Build the DecayDeck v4 schematic from design.py: place parts in labelled blocks, then draw a short
net-named wire stub on every connected pin (same name = same net in EasyEDA Pro).

usage: python build_sch.py layout   -> writes layout.json (positions) and prints block sizes
       python build_sch.py place    -> creates missing parts (skips refs already on the sheet)
       python build_sch.py wire     -> creates missing stubs (skips stubs already present)
       python build_sch.py titles   -> block title texts
Safe to re-run after a window drop.
"""
import json
import os
import sys

sys.path.insert(0, os.environ.get("EDA_TOOLS", "."))
from eda import run  # noqa: E402

from check_spec import resolved_nets  # noqa: E402
from design import DEVICES, PARTS  # noqa: E402

SCH_PAGE = "78286f62bfd019a0"
SYMS = json.load(open("symbols.json", encoding="utf-8"))
STUB = 10      # stub length (0.01 in units)
PAD = 30       # clearance around each part's pin box, beyond the stubs
GRID = 5

BLOCKS = [  # (key, title) in reading order; layout() packs them into rows
    ("usb", "USB-C INPUT + ESD"), ("chg", "CHARGER (BQ24075) + BATTERY + FUEL GAUGE"),
    ("pwr", "SOFT POWER + 3V3 BUCK-BOOST (TPS63802)"), ("mcu", "ESP32-S3 + BUTTONS + DEBUG"),
    ("hv", "HV SUPPLY: BOOST + DOUBLER, COMPARATOR-GATED (~400 V)"), ("gm", "GM TUBES: STS-5 + SI-3BG"),
    ("disp", "DISPLAY: ADAFRUIT 2090 (SPI)"), ("sens", "I2C SENSORS: BME280, RTC, IMU, LIGHT"),
    ("out", "BUZZER, VIBRATION, RGB LED"),
]
BLOCK_W = {"usb": 700, "chg": 1100, "pwr": 1000, "mcu": 900, "hv": 1300, "gm": 1000, "disp": 900,
           "sens": 1100, "out": 900}
ROW_BREAKS = {"mcu", "disp"}  # start a new row of blocks after these


def snap(v):
    return int(round(v / GRID)) * GRID


def bbox(key):
    """Pin-extent box of a symbol relative to its origin, grown by the stub and the clearance."""
    pins = SYMS[key]["pins"]
    xs = [p["dx"] for p in pins] or [0]
    ys = [p["dy"] for p in pins] or [0]
    m = STUB + PAD
    return min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m


def layout():
    """Pack parts per block (big parts first), then blocks into rows. Returns {ref: (x, y)} and titles."""
    def ref_key(r):
        head = r.rstrip("0123456789")
        return head, int(r[len(head):] or 0)

    pos, titles, blocks = {}, [], {}
    for key, _ in BLOCKS:
        refs = [r for r, p in PARTS.items() if p[2] == key]
        refs.sort(key=lambda r: (-len(SYMS[PARTS[r][0]]["pins"]) if len(SYMS[PARTS[r][0]]["pins"]) > 4 else 0,
                                 ref_key(r)))
        width = BLOCK_W[key]
        x = y = 0          # cursor: x right, y down (block-local, top edge = 0)
        row_h = 0
        local = {}
        for r in refs:
            x0, y0, x1, y1 = bbox(PARTS[r][0])
            w, h = x1 - x0, y1 - y0
            if x > 0 and x + w > width:
                x, y, row_h = 0, y + row_h, 0
            # origin so that the box's top-left sits at the cursor (y up in EasyEDA: top = y1)
            local[r] = (x - x0, -(y) - y1)
            x += w
            row_h = max(row_h, h)
        blocks[key] = (local, width, y + row_h)
    bx = by = 0
    row_h = 0
    for key, title in BLOCKS:
        local, w, h = blocks[key]
        top = by - 60   # leave room for the title
        for r, (lx, ly) in local.items():
            pos[r] = (snap(bx + lx), snap(top + ly))
        titles.append((title, bx, by - 20))
        print(f"block {key:5} {len(local):3} parts  {w}x{h}  at ({bx},{by})")
        row_h = max(row_h, h + 100)
        bx += w + 150
        if key in ROW_BREAKS:
            bx, by, row_h = 0, by - row_h - 100, 0
    return pos, titles


PLACE_JS = r"""
await eda.dmt_EditorControl.openDocument('__PAGE__');
const want = __WANT__;
const have = new Set((await eda.sch_PrimitiveComponent.getAll('part')).map(c => c.getState_Designator()));
const lcsc = [...new Set(want.filter(w => !w.dev && !have.has(w.ref)).map(w => w.key))];
const found = lcsc.length ? await eda.lib_Device.getByLcscIds(lcsc, undefined, false) : [];
const byCode = {};
for (const d of found || []) byCode[d.supplierId] = d;
const done = [];
for (const w of want) {
  if (have.has(w.ref)) { done.push([w.ref, 'exists']); continue; }
  const d = w.dev || byCode[w.key];
  if (!d) { done.push([w.ref, 'nodevice']); continue; }
  const c = await eda.sch_PrimitiveComponent.create({ libraryUuid: d.libraryUuid, uuid: d.uuid }, w.x, w.y, '', 0, false, w.bom, true);
  if (!c) { done.push([w.ref, 'createfail']); continue; }
  await eda.sch_PrimitiveComponent.modify(c.getState_PrimitiveId(), { designator: w.ref, addIntoBom: w.bom });
  done.push([w.ref, 'ok']);
}
return done;
"""

WIRE_JS = r"""
await eda.dmt_EditorControl.openDocument('__PAGE__');
const stubs = __STUBS__;
const have = new Set((await eda.sch_PrimitiveWire.getAll()).map(w => { const l = w.getState_Line(); return [l[0], l[1], l[2], l[3]].join(',') + '|' + [l[2], l[3], l[0], l[1]].join(','); }).flatMap(s => s.split('|')));
const res = [];
for (const s of stubs) {
  const k = s.line.join(',');
  if (have.has(k)) { res.push('exists'); continue; }
  const w = await eda.sch_PrimitiveWire.create(s.line, s.net);
  res.push(w ? 'ok' : 'fail:' + s.ref + '.' + s.pin + ':' + s.net);
}
return res;
"""


def place(pos):
    items = []
    for r, (x, y) in pos.items():
        if r not in PARTS:
            continue   # removed from the design
        key = PARTS[r][0]
        items.append({"ref": r, "key": key, "dev": DEVICES.get(key), "x": x, "y": y, "bom": PARTS[r][3]})
    for i in range(0, len(items), 8):
        batch = items[i:i + 8]
        js = PLACE_JS.replace("__PAGE__", SCH_PAGE).replace("__WANT__", json.dumps(batch))
        r = run(js, retry_on_drop=False)
        if not r.get("success"):
            print("batch error (re-run to resume):", r.get("error"))
            return False
        print(" ".join(f"{a}:{b}" for a, b in r["result"]))
    return True


def stubs(pos):
    nets, errors = resolved_nets()
    if errors:
        raise SystemExit(f"spec errors: {errors}")
    out = []
    for net, members in nets.items():
        for ref, num in sorted(members):
            x, y = pos[ref]
            pin = next(p for p in SYMS[PARTS[ref][0]]["pins"] if p["num"] == num)
            px, py = x + pin["dx"], y + pin["dy"]
            rot = int(pin["rot"] or 0) % 360
            dx, dy = {0: (STUB, 0), 90: (0, STUB), 180: (-STUB, 0), 270: (0, -STUB)}[rot]
            out.append({"ref": ref, "pin": num, "net": net,
                        "line": [round(px, 3), round(py, 3), round(px + dx, 3), round(py + dy, 3)]})
    return out


def wire(pos):
    all_stubs = stubs(pos)
    ends = {}
    for s in all_stubs:   # sanity: no two stubs of different nets may share an endpoint
        for pt in ((s["line"][0], s["line"][1]), (s["line"][2], s["line"][3])):
            if pt in ends and ends[pt] != s["net"]:
                raise SystemExit(f"stub collision at {pt}: {ends[pt]} vs {s['net']}")
            ends[pt] = s["net"]
    for i in range(0, len(all_stubs), 40):
        batch = all_stubs[i:i + 40]
        js = WIRE_JS.replace("__PAGE__", SCH_PAGE).replace("__STUBS__", json.dumps(batch))
        r = run(js, retry_on_drop=False)
        if not r.get("success"):
            print("batch error (re-run to resume):", r.get("error"))
            return False
        bad = [x for x in r["result"] if x not in ("ok", "exists")]
        print(f"stubs {i}-{i + len(batch) - 1}: {r['result'].count('ok')} new, {r['result'].count('exists')} existed",
              ("FAIL " + str(bad)) if bad else "")
    return True


TITLE_JS = r"""
await eda.dmt_EditorControl.openDocument('__PAGE__');
const have = new Set((await eda.sch_PrimitiveText.getAll()).map(t => t.getState_Content()));
const res = [];
for (const t of __TITLES__) {
  if (have.has(t[0])) { res.push('exists'); continue; }
  const x = await eda.sch_PrimitiveText.create(t[1], t[2], t[0], 0, '#1f4e79', null, 14, true);
  res.push(x ? 'ok' : 'fail');
}
return res;
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cmd = sys.argv[1]
    if cmd == "layout" or not os.path.exists("layout.json"):
        pos, titles = layout()
        json.dump({"pos": pos, "titles": titles}, open("layout.json", "w"), indent=1)
        if cmd == "layout":
            return
    lay = json.load(open("layout.json"))
    pos = {r: tuple(v) for r, v in lay["pos"].items()}
    if cmd == "place":
        place(pos)
    elif cmd == "wire":
        wire(pos)
    elif cmd == "titles":
        js = TITLE_JS.replace("__PAGE__", SCH_PAGE).replace("__TITLES__", json.dumps(lay["titles"]))
        print(run(js))


if __name__ == "__main__":
    main()
