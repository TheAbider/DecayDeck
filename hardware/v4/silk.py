"""Assembly silkscreen: tube / motor / battery polarity at their pads, an HV warning, the board name.
Every label's box is checked against all pads (0.3 mm) and the board edge (0.5 mm) before anything is sent.
Re-running replaces the labels this script made (matched by text).

usage: python silk.py check | push
"""
import json
import sys

from eda import run
from place_pcb import BOARD, PLACE, abs_pads
from design import PARTS

LABELS = [   # (text, x, y, height mm) centred
    ("STS-5 +", -28.6, 30.0, 0.9), ("SI-3BG +", -28.6, 23.4, 0.9),
    ("STS-5 -", -28.6, -30.4, 0.9), ("SI-3BG -", -29.0, -16.6, 0.9),
    ("M+", 29.8, -18.6, 0.9), ("M-", 29.8, -29.5, 0.9),
    ("+", -26.4, -57.9, 0.9), ("-", -24.4, -57.9, 0.9),   # J2: pad 1 = +, pad 2 = GND (see fix_review.py)
    ("HV 400V", -12.0, 6.6, 1.27),
    ("DecayDeck v4", -15.0, -67.6, 1.0),
]
CHAR_W = 0.78     # default stroke font: advance per character, as a fraction of the height
MIL = 1 / 0.0254


def text_box(text, x, y, h):
    w = len(text) * CHAR_W * h
    return x - w / 2, y - h / 2, x + w / 2, y + h / 2


def gap(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0)
    dy = max(b[1] - a[3], a[1] - b[3], 0)
    return (dx * dx + dy * dy) ** 0.5


def check():
    pads = [(f"{r}.{p['num']}", (p["ax"] - p["aw"] / 2, p["ay"] - p["ah"] / 2, p["ax"] + p["aw"] / 2, p["ay"] + p["ah"] / 2))
            for r in PLACE if r in PARTS for p in abs_pads(r)]
    bad = []
    for text, x, y, h in LABELS:
        b = text_box(text, x, y, h)
        near = min(pads, key=lambda pb: gap(b, pb[1]))
        edge = min(b[0] - BOARD[0], b[1] - BOARD[1], BOARD[2] - b[2], BOARD[3] - b[3])
        ok = gap(b, near[1]) >= 0.3 and edge >= 0.5
        print(f"{text:14} nearest pad {near[0]:7} {gap(b, near[1]):.2f} mm, edge {edge:.2f} mm  {'OK' if ok else 'BAD'}")
        if not ok:
            bad.append(text)
    return not bad


def push():
    items = [[t, x * MIL, y * MIL, h * MIL] for t, x, y, h in LABELS]
    js = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const items = __ITEMS__;
const texts = new Set(items.map(i => i[0]));
const old = (await eda.pcb_PrimitiveString.getAll()).filter(s => s.getState_Layer() === 3 && texts.has(s.getState_Text()));
if (old.length) await eda.pcb_PrimitiveString.delete(old.map(s => s.getState_PrimitiveId()));
let n = 0;
for (const [t, x, y, h] of items) {
  const s = await eda.pcb_PrimitiveString.create(3, x, y, t, 'default', h, 6, 5, 0, false, 0, false, false);
  if (s) n++;
}
return { replaced: old.length, created: n };
"""
    print(run(js.replace("__ITEMS__", json.dumps(items))))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ok = check()
    print("PASS" if ok else "FAIL")
    if sys.argv[1] == "push":
        if not ok:
            raise SystemExit("not pushed")
        push()
