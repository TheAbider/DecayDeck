"""Board-level setup on the EasyEDA PCB: 4 copper layers, outline, mounting holes, antenna keepout.
Idempotent: removes its own previous outline/holes/regions (tagged by name or position) before adding.

usage: python setup_board.py
"""
import json
import sys

from eda import run
from place_pcb import ANTENNA_KEEPOUT, BOARD, CORNER_R, HOLES

MIL = 1 / 0.0254
JS = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const out = {};
out.layers = await eda.pcb_Layer.setTheNumberOfCopperLayers(4);
// outline: drop any existing outline primitives on the board-outline layer, then draw ours
const old = await eda.pcb_PrimitivePolyline.getAll(undefined, 11);
if (old.length) await eda.pcb_PrimitivePolyline.delete(old.map(p => p.getState_PrimitiveId()));
const poly = eda.pcb_MathPolygon.createPolygon(['R', __X0__, __Y1__, __W__, __H__, 0, __R__]);
const ol = await eda.pcb_PrimitivePolyline.create('', 11, poly, 8);
out.outline = ol ? ol.getState_PrimitiveId() : null;
// mounting holes: unplated 2.7 mm (nylon M2.5 standoffs), no net
const pads = await eda.pcb_PrimitivePad.getAll();
// standalone pads only (component pads have ids like <component id>e<n>); an earlier filter missed 16-hex ids
const holeIds = pads.filter(p => !p.getState_Net() && p.getState_Hole() && /^([0-9a-f]{16}|e\d+)$/.test(String(p.getState_PrimitiveId()))).map(p => p.getState_PrimitiveId());
if (holeIds.length) await eda.pcb_PrimitivePad.delete(holeIds);
out.holes = [];
for (const h of __HOLES__) {
  const p = await eda.pcb_PrimitivePad.create(12, '', h[0], h[1], 0, ['ELLIPSE', 106.3, 106.3], '', ['ROUND', 106.3], 0, 0, 0, false);
  out.holes.push(p ? p.getState_PrimitiveId() : null);
}
// antenna keepout: no copper on any layer
const regs = await eda.pcb_PrimitiveRegion.getAll();
// region names are not stored, so a keepout is recognised by its rule set (no wires + no pours)
const mine = regs.filter(r => { const t = r.getState_RuleType() || []; return r.getState_Layer() === 12 && t.includes(5) && t.includes(7); }).map(r => r.getState_PrimitiveId());
if (mine.length) await eda.pcb_PrimitiveRegion.delete(mine);
const kpoly = eda.pcb_MathPolygon.createPolygon(['R', __KX0__, __KY1__, __KW__, __KH__, 0, 0]);
const kr = await eda.pcb_PrimitiveRegion.create(12, kpoly, __RULES__, 'ANTENNA_KEEPOUT');
out.keepout = kr ? kr.getState_PrimitiveId() : null;
return out;
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    x0, y0, x1, y1 = BOARD
    kx0, ky0, kx1, ky1 = ANTENNA_KEEPOUT
    js = (JS.replace("__X0__", f"{x0 * MIL:.2f}").replace("__Y1__", f"{y1 * MIL:.2f}")
          .replace("__W__", f"{(x1 - x0) * MIL:.2f}").replace("__H__", f"{(y1 - y0) * MIL:.2f}")
          .replace("__R__", f"{CORNER_R * MIL:.2f}")
          .replace("__HOLES__", json.dumps([[hx * MIL, hy * MIL] for hx, hy in HOLES.values()]))
          .replace("__KX0__", f"{kx0 * MIL:.2f}").replace("__KY1__", f"{ky1 * MIL:.2f}")
          .replace("__KW__", f"{(kx1 - kx0) * MIL:.2f}").replace("__KH__", f"{(ky1 - ky0) * MIL:.2f}")
          .replace("__RULES__", "[5, 6, 7, 8]"))  # no wires, fills, pours, inner planes (the module itself sits in it)
    print(run(js))


if __name__ == "__main__":
    main()
