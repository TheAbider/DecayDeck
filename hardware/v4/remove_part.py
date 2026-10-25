"""Remove one part from the schematic together with the stubs on its pins (it must already be gone
from design.py).

usage: python remove_part.py REF OLD_KEY
"""
import json
import sys

from build_sch import SCH_PAGE, STUB, SYMS
from eda import run

JS = r"""
await eda.dmt_EditorControl.openDocument('__PAGE__');
const comps = (await eda.sch_PrimitiveComponent.getAll('part')).filter(c => c.getState_Designator() === '__REF__');
const oldLines = __OLDLINES__;
const wires = await eda.sch_PrimitiveWire.getAll();
const kill = wires.filter(w => { const l = w.getState_Line(); const k1 = [l[0], l[1], l[2], l[3]].join(','); const k2 = [l[2], l[3], l[0], l[1]].join(','); return oldLines.includes(k1) || oldLines.includes(k2); }).map(w => w.getState_PrimitiveId());
if (kill.length) await eda.sch_PrimitiveWire.delete(kill);
if (comps.length) await eda.sch_PrimitiveComponent.delete(comps.map(c => c.getState_PrimitiveId()));
return { removedWires: kill.length, removedParts: comps.length };
"""


def main():
    ref, old_key = sys.argv[1], sys.argv[2]
    x, y = json.load(open("layout.json"))["pos"][ref]
    lines = []
    for p in SYMS[old_key]["pins"]:
        px, py = x + p["dx"], y + p["dy"]
        dx, dy = {0: (STUB, 0), 90: (0, STUB), 180: (-STUB, 0), 270: (0, -STUB)}[int(p["rot"] or 0) % 360]
        lines.append(",".join(str(round(v, 3)) for v in (px, py, px + dx, py + dy)))
    print(run(JS.replace("__PAGE__", SCH_PAGE).replace("__REF__", ref).replace("__OLDLINES__", json.dumps(lines)),
              retry_on_drop=False))


if __name__ == "__main__":
    main()
