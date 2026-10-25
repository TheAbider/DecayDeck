"""Copper pours: Inner1 = GND plane, Inner2 = 3V3 plane, Top/Bottom = GND, plus an inner-layer keepout
under the GM anode chains (keeps stray capacitance off the high-impedance anode nodes).

usage: python pours.py create   -> (re)create pours + keepout, then rebuild
       python pours.py rebuild  -> rebuild existing pours only
"""
import sys

from eda import run
from place_pcb import BOARD, CORNER_R

MIL = 1 / 0.0254
INSET = 0.4                               # pour edge to board edge
ANODE_KEEPOUT = (-31.0, 24.0, -17.0, 35.0)  # x0, y0, x1, y1 (mm): J5/J7 + R36/R41 + the GM*_AM ends of R35/R40
POURS = [("GND", 15, "PLANE_GND", 1), ("3V3", 16, "PLANE_3V3", 1), ("GND", 1, "TOP_GND", 2), ("GND", 2, "BOT_GND", 2)]


def rect(x0, y0, x1, y1, r=0.0):
    return ["R", round(x0 * MIL, 2), round(y1 * MIL, 2), round((x1 - x0) * MIL, 2), round((y1 - y0) * MIL, 2), 0, round(r * MIL, 2)]


CREATE = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const names = new Set(__NAMES__);
const old = (await eda.pcb_PrimitivePour.getAll()).filter(p => names.has(p.getState_PourName ? p.getState_PourName() : ''));
if (old.length) await eda.pcb_PrimitivePour.delete(old.map(p => p.getState_PrimitiveId()));
const regs = (await eda.pcb_PrimitiveRegion.getAll()).filter(r => [15, 16].includes(r.getState_Layer()) && String(r.getState_RuleType()) === '6,7,8');
if (regs.length) await eda.pcb_PrimitiveRegion.delete(regs.map(r => r.getState_PrimitiveId()));
const out = { pours: [], keepout: [] };
for (const lay of [15, 16]) {
  const k = await eda.pcb_PrimitiveRegion.create(lay, eda.pcb_MathPolygon.createPolygon(__KEEP__), [6, 7, 8], 'ANODE_KEEPOUT');
  out.keepout.push(k ? k.getState_PrimitiveId() : null);
}
for (const [net, layer, name, prio] of __POURS__) {
  const p = await eda.pcb_PrimitivePour.create(net, layer, eda.pcb_MathPolygon.createPolygon(__OUTLINE__), undefined, false, name, prio, 10);
  out.pours.push([name, p ? p.getState_PrimitiveId() : null]);
}
return out;
"""
REBUILD = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const pours = await eda.pcb_PrimitivePour.getAll();
const res = [];
for (const p of pours) { try { const r = await p.rebuildCopperRegion(); res.push(!!r); } catch (e) { res.push('ERR ' + e); } }
return res;
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import json
    if sys.argv[1] == "create":
        x0, y0, x1, y1 = BOARD
        outline = rect(x0 + INSET, y0 + INSET, x1 - INSET, y1 - INSET, CORNER_R - INSET)
        js = (CREATE.replace("__NAMES__", json.dumps([p[2] for p in POURS]))
              .replace("__KEEP__", json.dumps(rect(*ANODE_KEEPOUT)))
              .replace("__POURS__", json.dumps(POURS)).replace("__OUTLINE__", json.dumps(outline)))
        print(run(js))
    print(run(REBUILD, timeout=120))


if __name__ == "__main__":
    main()
