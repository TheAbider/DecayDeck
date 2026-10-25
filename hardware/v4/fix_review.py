"""Pre-order review fixes (2026-10-25), found by checking the board against datasheets and vendor designs:

- J2 battery polarity. Adafruit's and SparkFun's LiPo plugs would have landed reversed. Two Adafruit board files
  (Feather ESP32-S3, Feather nRF52840 Sense) put VBAT on the right-hand pin and GND on the left, seen from the
  connector's open side. Ours had + on the left. (The old "pin 2 = +" check compared pad numbers only, and
  Adafruit's footprint numbers its pads the other way round from ours.) Swap the nets (pad 1 = BAT_RAW, pad 2 = GND)
  and re-route BAT_RAW under the connector body to Q1's drain.
- SW1-3 (Alps SKRTLAE010). Alps' land drawing prohibits copper tracks in the area between the front legs, and
  fanout had put pad 2's GND via there, with the top pour around it. Pads 1 and 3 are joined inside the switch
  (Alps circuit diagram), so only pad 3 stays wired. That removes the loop round the back that joined pad 1 and frees
  room behind pad 2 for its GND connection. Top-layer keepout regions (no wires, fills or pours) cover the 3 areas.

usage: python fix_review.py check | apply
"""
import json
import sys

from shapely import affinity
from shapely.geometry import LineString, Point, box

from eda import run
from place_pcb import HV_NETS, PLACE, abs_pads
from design import PARTS

MM = 0.0254
CLEAR = 0.2
VIA_D = 0.6
BACKUP = "fix_review_ripped.json"   # what apply removed, to restore by hand if ever needed

# primitive id -> net it must have (a guard against deleting the wrong thing)
DELETE_LINES = {
    "a7718bfe69cd3ef8": "GND", "0e7020049dbef22c": "BAT_RAW", "150ba2388794e6ae": "BAT_RAW",   # J2
    "74012f8aa3fd1bcf": "GND", "04a5628adb6bcb6f": "PWR_BTN_N", "9193a1078b795a54": "PWR_BTN_N",  # SW1
    "1b19a2c3c30305e8": "PWR_BTN_N", "c585108de868cbb2": "PWR_BTN_N", "788b586889a72ad7": "PWR_BTN_N",
    "f057328858780beb": "PWR_BTN_N",
    "c0a69ca42114ffe3": "GND", "ca8a59c8547d6ef8": "BTN_A", "a7567eb865d02bd5": "BTN_A",  # SW2
    "11fe999d3fef087e": "BTN_A",
    "01001d951c50def3": "GND", "8d3d832d6ac1535c": "BTN_B", "4e8bfbb5bca5d225": "BTN_B",  # SW3
    "90ac5d2ba7319d8c": "BTN_B", "0a15e2dbcede7214": "BTN_B", "cd1a7cd8872cfe59": "BTN_B",
    "094019f6b99777a1": "BTN_B",
}
DELETE_VIAS = {"52d3ec72eb979ba4": "GND", "aa07e76b64f4d463": "GND", "31e8ffcf1b74fa14": "GND",
               "5c651a76c134d87b": "GND"}
PAD_NETS = {("J2", "1"): "BAT_RAW", ("J2", "2"): "GND", ("SW1", "1"): "", ("SW2", "1"): "", ("SW3", "1"): ""}
NEW_TRACKS = [  # (net, layer, width, points)
    ("BAT_RAW", 1, 0.5, [(-26.40, -61.50), (-26.40, -63.40), (-18.75, -63.40), (-17.95, -62.60), (-17.55, -62.60)]),
    ("GND", 1, 0.3, [(-24.40, -59.10), (-23.15, -59.10)]),
    ("PWR_BTN_N", 1, 0.25, [(28.17, 28.30), (29.10, 29.23), (30.03, 29.23)]),
    ("GND", 1, 0.3, [(28.60, 27.65), (28.95, 28.01), (30.03, 28.01)]),
    ("GND", 1, 0.3, [(28.25, 13.20), (29.05, 14.00), (30.03, 14.02)]),
    ("GND", 1, 0.3, [(28.25, 1.20), (29.05, 2.00), (30.03, 2.01)]),
]
NEW_VIAS = [("GND", -23.15, -59.10), ("GND", 28.60, 27.65)]


def zone(ref):
    """Alps 'prohibited area of copper tracks': x within +-1.0 of the switch centre line, from the front legs' outer
    edge back to the terminal pads (footprint y -1.426 .. 0.075; the drawing's 1.2 mm read generously)."""
    x, y, rot = PLACE[ref]
    assert rot == 90   # footprint (lx, ly) -> board (x - ly, y + lx)
    return box(x - 0.075, y - 1.0, x + 1.426, y + 1.0)


ZONES = {r: zone(r) for r in ("SW1", "SW2", "SW3")}
LIVE = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
return { L: (await eda.pcb_PrimitiveLine.getAll()).map(l => [l.getState_PrimitiveId(), l.getState_Net(), l.getState_Layer(), l.getState_StartX(), l.getState_StartY(), l.getState_EndX(), l.getState_EndY(), l.getState_LineWidth()]),
         V: (await eda.pcb_PrimitiveVia.getAll()).map(v => [v.getState_PrimitiveId(), v.getState_Net(), v.getState_X(), v.getState_Y(), v.getState_HoleDiameter(), v.getState_Diameter()]) };
"""


def pad_geom(p):
    """True pad outline: ELLIPSE -> ellipse, OVAL -> stadium, otherwise box."""
    x, y, w, h = p["ax"], p["ay"], p["aw"], p["ah"]
    if p.get("shape") == "ELLIPSE":
        return affinity.scale(Point(x, y).buffer(0.5, 64), w, h)
    if p.get("shape") == "OVAL":
        r = min(w, h) / 2
        dx, dy = (w / 2 - r, 0) if w >= h else (0, h / 2 - r)
        return LineString([(x - dx, y - dy), (x + dx, y + dy)]).buffer(r, 32) if (dx or dy) else Point(x, y).buffer(r, 32)
    return box(x - w / 2, y - h / 2, x + w / 2, y + h / 2)


def check(live):
    ok = True
    lines = {l[0]: l for l in live["L"]}
    vias = {v[0]: v for v in live["V"]}
    for pid, net in DELETE_LINES.items():
        if pid not in lines or lines[pid][1] != net:
            print("delete guard: track", pid, "missing or not", net)
            ok = False
    for pid, net in DELETE_VIAS.items():
        if pid not in vias or vias[pid][1] != net:
            print("delete guard: via", pid, "missing or not", net)
            ok = False
    obstacles = []   # (net, layers, geometry, label)
    for ref in PLACE:
        if ref not in PARTS:
            continue
        for p in abs_pads(ref):
            net = PAD_NETS.get((ref, p["num"]), p["net"] or "")
            obstacles.append((net, {1, 2} if p.get("hole") else {1}, pad_geom(p), f"pad {ref}.{p['num']}"))
    for pid, n, lay, a, b, c, d, w in live["L"]:
        if pid not in DELETE_LINES:
            obstacles.append((n, {lay}, LineString([(a * MM, b * MM), (c * MM, d * MM)]).buffer(w * MM / 2), f"track {n}"))
    for pid, n, x, y, hole, dia in live["V"]:
        if pid not in DELETE_VIAS:
            obstacles.append((n, {1, 2}, Point(x * MM, y * MM).buffer(dia * MM / 2), f"via {n} ({x * MM:.2f},{y * MM:.2f})"))
    new = [(n, {lay}, LineString(pts).buffer(w / 2), f"{n} track {pts[0]}..{pts[-1]}") for n, lay, w, pts in NEW_TRACKS]
    new += [(n, {1, 2}, Point(x, y).buffer(VIA_D / 2), f"{n} via ({x},{y})") for n, x, y in NEW_VIAS]
    for net, lays, g, label in new:
        d, lbl, onet = min((g.distance(og), olbl, n) for n, ls, og, olbl in obstacles if n != net and lays & ls)
        need = 2.5 if onet in HV_NETS else CLEAR
        print(f"{label}: closest other-net copper {lbl} ({onet or 'no net'}) at {d:.3f} mm (needs {need})")
        ok &= d >= need
    # each new track must start or end on its own pad/via (no floating stubs)
    for net, lays, g, label in new:
        if "track" in label:
            touch = [olbl for n, ls, og, olbl in obstacles + new if n == net and og is not g and og.intersects(g)]
            if not touch:
                print("floating:", label)
                ok = False
    for ref, z in ZONES.items():
        inside = [olbl for n, ls, og, olbl in obstacles + new if 1 in ls and "pad" not in olbl and og.intersects(z)]
        print(f"{ref} no-copper zone {[round(c, 3) for c in z.bounds]}: {inside or 'clear'}")
        ok &= not inside
    return ok


def apply(live):
    lines = [l for l in live["L"] if l[0] in DELETE_LINES]
    vias = [v for v in live["V"] if v[0] in DELETE_VIAS]
    json.dump({"lines": lines, "vias": vias, "pad_nets_before": {"J2.1": "GND", "J2.2": "BAT_RAW", "SW1.1": "PWR_BTN_N",
                                                                  "SW2.1": "BTN_A", "SW3.1": "BTN_B"}},
              open(BACKUP, "w"), indent=1)
    print("removed copper saved to", BACKUP)
    mil = 1 / MM
    js = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const out = {};
out.linesDeleted = await eda.pcb_PrimitiveLine.delete(__LINES__);
out.viasDeleted = await eda.pcb_PrimitiveVia.delete(__VIAS__);
const want = __PADNETS__;
const comps = await eda.pcb_PrimitiveComponent.getAll();
out.pads = [];
for (const c of comps) {
  const des = c.getState_Designator();
  const pads = (await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId())) || [];
  for (const p of pads) {
    const k = des + '.' + p.getState_PadNumber();
    if (!(k in want)) continue;
    const a = p.toAsync();
    a.setState_Net(want[k]);
    await a.done();
    const again = await eda.pcb_PrimitivePad.get(p.getState_PrimitiveId());
    out.pads.push([k, again ? again.getState_Net() : 'reread failed']);
  }
}
let nt = 0, nv = 0, nr = 0;
for (const t of __TRACKS__) {
  for (let i = 0; i + 1 < t.p.length; i++) {
    if (await eda.pcb_PrimitiveLine.create(t.net, t.layer, t.p[i][0], t.p[i][1], t.p[i + 1][0], t.p[i + 1][1], t.w)) nt++;
  }
}
for (const v of __NEWVIAS__) { if (await eda.pcb_PrimitiveVia.create(v[0], v[1], v[2], 11.811, 23.622)) nv++; }
for (const z of __ZONES__) {
  const r = await eda.pcb_PrimitiveRegion.create(1, eda.pcb_MathPolygon.createPolygon(z), [5, 6, 7], 'SW_NO_COPPER');
  if (r) nr++;
}
out.created = { trackSegments: nt, vias: nv, regions: nr };
out.saved = await eda.pcb_Document.save();
return out;
"""

    def rect(z):
        x0, y0, x1, y1 = z.bounds
        return ["R", round(x0 * mil, 2), round(y1 * mil, 2), round((x1 - x0) * mil, 2), round((y1 - y0) * mil, 2), 0, 0]

    js = (js.replace("__LINES__", json.dumps([l[0] for l in lines])).replace("__VIAS__", json.dumps([v[0] for v in vias]))
          .replace("__PADNETS__", json.dumps({f"{r}.{n}": net for (r, n), net in PAD_NETS.items()}))
          .replace("__TRACKS__", json.dumps([{"net": n, "layer": lay, "w": w * mil, "p": [[x * mil, y * mil] for x, y in pts]}
                                             for n, lay, w, pts in NEW_TRACKS]))
          .replace("__NEWVIAS__", json.dumps([[n, x * mil, y * mil] for n, x, y in NEW_VIAS]))
          .replace("__ZONES__", json.dumps([rect(z) for z in ZONES.values()])))
    print(json.dumps(run(js, timeout=120, retry_on_drop=False), indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    live = run(LIVE)["result"]
    ok = check(live)
    print("PASS" if ok else "FAIL")
    if sys.argv[1] == "apply":
        if not ok:
            raise SystemExit("not applied")
        apply(live)
