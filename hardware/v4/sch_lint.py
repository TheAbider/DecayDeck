"""Read the schematic the way a person sees it: from the PDF EasyEDA exports, not from the layout's own estimates.
Reports anything that doesn't read clean:
  - text outside the sheet frame's inner border,
  - text on top of other text,
  - a line (wire, symbol outline, pin, block frame) running through text.
The title block is the frame symbol's own artwork and is left alone.

usage: python sch_lint.py [schematic.pdf]   (no argument: export a fresh PDF first)
       python sch_lint.py --api            (ask EasyEDA for every symbol's, text's and label's real bounding box
                                             instead; works while the window is hidden, when PDF export stalls;
                                             saves it to sch_geometry.json)
       python sch_lint.py --cached         (re-check the last saved geometry)
       python sch_lint.py --pintext X.pdf  (record where the pin numbers and names are drawn: sch_pintext.json)
Exit 1 when anything is found.
"""
import os
import sys
import tempfile

import fitz   # PyMuPDF

SCALE = 0.72                                  # PDF points per drawing unit
SHEET_W, SHEET_H = 3304, 2338                 # A1 frame, drawing units
INNER = (20, 20, 3284, 2318)
TITLE_BLOCK = (2580, 10, 3294, 205)
SHRINK_Y, SHRINK_X = 0.22, 0.5                # text boxes include line spacing: test the ink band only
GRID = 40


def load(fn):
    page = fitz.open(fn)[0]
    drawings = page.get_drawings()
    frame = next((g["rect"] for g in drawings
                  if abs(g["rect"].width - SHEET_W * SCALE) < 3 and abs(g["rect"].height - SHEET_H * SCALE) < 3), None)
    if frame is None:
        raise SystemExit("no A1 sheet frame found in the PDF")

    def u(p):
        return ((p.x - frame.x0) / SCALE, (frame.y1 - p.y) / SCALE)

    segs = []
    for g in drawings:
        if g["rect"] == frame:
            continue
        for it in g["items"]:
            if it[0] == "l":
                segs.append((u(it[1]), u(it[2])))
            elif it[0] == "re":
                r = it[1]
                c = [u(fitz.Point(r.x0, r.y0)), u(fitz.Point(r.x1, r.y0)), u(fitz.Point(r.x1, r.y1)), u(fitz.Point(r.x0, r.y1))]
                segs += [(c[i], c[(i + 1) % 4]) for i in range(4)]
            elif it[0] == "qu":
                q = it[1]
                c = [u(q.ul), u(q.ur), u(q.lr), u(q.ll)]
                segs += [(c[i], c[(i + 1) % 4]) for i in range(4)]
            elif it[0] == "c":
                pts = [u(p) for p in it[1:5]]
                segs += [(pts[i], pts[i + 1]) for i in range(3)]
    texts = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                t = s["text"].strip()
                if not t:
                    continue
                x0, y0 = u(fitz.Point(s["bbox"][0], s["bbox"][3]))
                x1, y1 = u(fitz.Point(s["bbox"][2], s["bbox"][1]))
                texts.append((t, (x0, y0, x1, y1)))
    return texts, segs


API_JS = r"""
const bb = async (id) => { const b = await eda.sch_Primitive.getPrimitivesBBox([id]); return b ? [b.minX, b.minY, b.maxX, b.maxY] : null; };
const out = { bodies: [], pins: [], texts: [], wires: [], rects: [] };
const comps = await eda.sch_PrimitiveComponent.getAll();
const wires = await eda.sch_PrimitiveWire.getAll();
job.total = comps.length + wires.length;
for (const c of comps) {
  const kind = c.getState_ComponentType();
  if (kind !== 'sheet') {
    const id = c.getState_PrimitiveId(), ref = c.getState_Designator() || kind;
    out.bodies.push([ref, kind, await bb(id), c.getState_X(), c.getState_Y(), c.getState_Rotation(), !!c.getState_Mirror()]);
    if (kind === 'part')        // a part's box is its body only: its pins (and their numbers) reach beyond it
      for (const p of (await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(id)) || [])
        out.pins.push([ref, p.getState_PinNumber(), p.getState_Rotation(), await bb(p.getState_PrimitiveId())]);
    for (const a of await eda.sch_PrimitiveAttribute.getAll(id))
      if (a.getState_ValueVisible() || a.getState_KeyVisible()) out.texts.push([ref + ' ' + a.getState_Key(), kind, await bb(a.getState_PrimitiveId())]);
  }
  job.n += 1;
}
for (const w of wires) {
  out.wires.push(w.getState_Line());
  for (const a of await eda.sch_PrimitiveAttribute.getAll(w.getState_PrimitiveId()))
    if (a.getState_Key() === 'Name' && a.getState_ValueVisible()) out.texts.push(['net label ' + w.getState_Net(), 'label', await bb(a.getState_PrimitiveId())]);
  job.n += 1;
}
for (const t of await eda.sch_PrimitiveText.getAll()) out.texts.push(['note ' + String(t.getState_Content()).slice(0, 30), 'note', await bb(t.getState_PrimitiveId())]);
for (const r of await eda.sch_PrimitiveRectangle.getAll()) out.rects.push(await bb(r.getState_PrimitiveId()));
return out;
"""


GEOMETRY = "sch_geometry.json"   # last real geometry read from EasyEDA (sch_pretty.py places text against it)


def load_api(cached=False):
    """Real geometry from EasyEDA: (texts [(name, box, owner kind)], line pieces, symbol bodies [(ref, kind, box)])."""
    import json
    if cached and os.path.exists(GEOMETRY):
        d = json.load(open(GEOMETRY, encoding="utf-8"))
    else:
        from sch_pretty import OPEN, _detached
        d = _detached(OPEN + API_JS, "geometry")
        json.dump(d, open(GEOMETRY, "w", encoding="utf-8"))
    texts = [(name, tuple(b), kind) for name, kind, b in d["texts"] if b]
    segs = []
    for line in d["wires"]:
        if line and isinstance(line[0], list):
            for l in line:
                segs += [((l[i], l[i + 1]), (l[i + 2], l[i + 3])) for i in range(0, len(l) - 3, 2)]
        else:
            segs += [((line[i], line[i + 1]), (line[i + 2], line[i + 3])) for i in range(0, len(line) - 3, 4)]
    for x0, y0, x1, y1 in (r for r in d["rects"] if r):
        c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        segs += [(c[i], c[(i + 1) % 4]) for i in range(4)]
    bodies = [(b[0], b[1], tuple(b[2])) for b in d["bodies"] if b[2]]
    return texts, segs, bodies


PINTEXT = "sch_pintext.json"   # pin numbers and names as drawn (EasyEDA reports no box for them)


def _dist(p, a, b):
    ax, ay, bx, by, px, py = a[0], a[1], b[0], b[1], p[0], p[1]
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def pin_texts(pdf):
    """Pin numbers and names from an exported PDF: each text span equal to a pin's number or name and within 12
    units of that pin. Pin text never moves when names, values or labels do, so one export serves every later
    re-placement. Needs the pins in sch_geometry.json (sch_lint.py --api)."""
    import json
    from design import PARTS
    geo = json.load(open(GEOMETRY, encoding="utf-8"))
    syms = json.load(open("symbols.json", encoding="utf-8"))
    pins = []
    for ref, num, rot, b in geo.get("pins", []):
        if not b or ref not in PARTS:
            continue
        labels = {num} | {p["name"] for p in syms[PARTS[ref][0]]["pins"] if p["num"] == num}
        x0, y0, x1, y1 = b
        if y1 - y0 > x1 - x0:
            seg = (((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1))
        else:
            seg = ((x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2))
        pins.append((ref, labels, seg))
    texts, _ = load(pdf)
    out = []
    for t, box in texts:
        c = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        hits = sorted((_dist(c, *seg), ref) for ref, labels, seg in pins if t in labels)
        if hits and hits[0][0] <= 12:
            out.append([hits[0][1], t, [round(v, 2) for v in box]])
    json.dump(out, open(PINTEXT, "w", encoding="utf-8"))
    return out


def pin_obstacles(geo=None):
    """(ref, kind, box) for every pin line and every pin number / name, from sch_geometry.json + sch_pintext.json."""
    import json
    geo = geo or json.load(open(GEOMETRY, encoding="utf-8"))
    out = [(ref, "pin", tuple(b)) for ref, num, rot, b in geo.get("pins", []) if b]
    if os.path.exists(PINTEXT):
        out += [(ref, f"pin text {t}", tuple(b)) for ref, t, b in json.load(open(PINTEXT, encoding="utf-8"))]
    return out


def ink(box):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if w >= h:   # horizontal text
        return x0 + SHRINK_X, y0 + h * SHRINK_Y, x1 - SHRINK_X, y1 - h * SHRINK_Y
    return x0 + w * SHRINK_Y, y0 + SHRINK_X, x1 - w * SHRINK_Y, y1 - SHRINK_X


def inside(box, area):
    return area[0] <= box[0] and area[1] <= box[1] and box[2] <= area[2] and box[3] <= area[3]


def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def seg_through(p, q, box):
    """Liang-Barsky: does segment p-q pass through the box's interior?"""
    x0, y0, x1, y1 = box
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pk, qk in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pk == 0:
            if qk <= 0:
                return False
        else:
            t = qk / pk
            if pk < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 >= t1:
                return False
    return True


def cells(box):
    for gx in range(int(box[0] // GRID), int(box[2] // GRID) + 1):
        for gy in range(int(box[1] // GRID), int(box[3] // GRID) + 1):
            yield gx, gy


def lint(texts, segs, bodies=()):
    """texts: [(text, box)]; segs: line pieces; bodies: [(ref, kind, box)] symbol outlines (API mode), which no text
    may touch except a net symbol's own name."""
    problems = []
    texts = [(t[0], t[1]) for t in texts if not inside(t[1], TITLE_BLOCK)]
    for t, b in texts:
        tb = ink(b)
        for ref, kind, sb in bodies:
            own = t.split(" ")[0] == ref and kind in ("netflag", "netport")
            box = sb if kind == "pin" else (sb[0] + 0.5, sb[1] + 0.5, sb[2] - 0.5, sb[3] - 0.5)  # a pin is a line
            if not own and overlap(tb, box):
                problems.append(("text on a symbol", t, b, f"{ref} ({kind})"))
    for t, b in texts:
        if not inside(b, INNER):
            problems.append(("outside the frame", t, b, None))
    for ref, kind, sb in bodies:   # wires end on a symbol's pin tips, at its box edge: none may run inside it
        # a pin number is text standing on its own pin line, and the wire leaving that pin carries the line on
        # (USB-C's A1B12 runs past the tip): test its ink band, as for any other text
        core = ink(sb) if kind.startswith("pin text") else (sb[0] + 1, sb[1] + 1, sb[2] - 1, sb[3] - 1)
        if core[0] >= core[2] or core[1] >= core[3]:
            continue
        for p, q in segs:
            if seg_through(p, q, core):
                problems.append(("line through a symbol", ref, sb, f"line {round(p[0])},{round(p[1])}-{round(q[0])},{round(q[1])}"))
                break
    grid = {}
    for i, (p, q) in enumerate(segs):
        for c in cells((min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1]))):
            grid.setdefault(c, []).append(i)
    boxes = [ink(b) for _, b in texts]
    tgrid = {}
    for i, b in enumerate(boxes):
        for c in cells(b):
            tgrid.setdefault(c, []).append(i)
    seen = set()
    for i, b in enumerate(boxes):
        near = {j for c in cells(b) for j in tgrid.get(c, []) if j > i}
        for j in sorted(near):
            if overlap(b, boxes[j]) and (i, j) not in seen:
                seen.add((i, j))
                problems.append(("text on text", texts[i][0], texts[i][1], texts[j][0]))
        hit = {k for c in cells(b) for k in grid.get(c, [])}
        for k in sorted(hit):
            if seg_through(*segs[k], b):
                p, q = segs[k]
                problems.append(("line through text", texts[i][0], texts[i][1],
                                 f"line {round(p[0])},{round(p[1])}-{round(q[0])},{round(q[1])}"))
                break
    return texts, problems


def main(fn=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    bodies = ()
    if fn == "--pintext":                            # python sch_lint.py --pintext exported.pdf
        print(len(pin_texts(sys.argv[2])), "pin numbers / names found in", sys.argv[2])
        return 0
    if fn in ("--api", "--cached"):
        texts, segs, bodies = load_api(cached=fn == "--cached")
        bodies = list(bodies) + pin_obstacles()
    else:
        if not fn:
            from sch_export import export
            fn = export("pdf", os.path.join(tempfile.gettempdir(), "decaydeck_v4_lint.pdf"))
        texts, segs = load(fn)
    texts, problems = lint(texts, segs, bodies)
    kinds = {}
    for k, *_ in problems:
        kinds[k] = kinds.get(k, 0) + 1
    print(f"{len(texts)} texts, {len(segs)} line pieces checked: {len(problems)} problems {kinds or ''}")
    shown = {}
    for k, t, b, other in problems:
        shown[k] = shown.get(k, 0) + 1
        if shown[k] <= 25:
            print(f"   {k}: '{t}' at {round(b[0])},{round(b[1])}" + (f" / {other}" if other else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
