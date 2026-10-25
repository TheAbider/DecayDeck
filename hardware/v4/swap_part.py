"""Replace one part on the schematic in place: delete the old instance and the stubs on its old pins,
place the new device (per design.py) at the same layout position, and set its designator.
Run build_sch.py wire afterwards to add the new part's stubs.

usage: python swap_part.py REF OLD_KEY
"""
import json
import sys

from build_sch import SCH_PAGE, STUB, SYMS
from design import DEVICES, PARTS
from eda import run

JS = r"""
await eda.dmt_EditorControl.openDocument('__PAGE__');
const ref = '__REF__';
const comps = (await eda.sch_PrimitiveComponent.getAll('part')).filter(c => c.getState_Designator() === ref);
const oldLines = __OLDLINES__;
const wires = await eda.sch_PrimitiveWire.getAll();
const kill = wires.filter(w => { const l = w.getState_Line(); const k1 = [l[0], l[1], l[2], l[3]].join(','); const k2 = [l[2], l[3], l[0], l[1]].join(','); return oldLines.includes(k1) || oldLines.includes(k2); }).map(w => w.getState_PrimitiveId());
if (kill.length) await eda.sch_PrimitiveWire.delete(kill);
if (comps.length) await eda.sch_PrimitiveComponent.delete(comps.map(c => c.getState_PrimitiveId()));
const want = __WANT__;
let d = want.dev;
if (!d) { const f = await eda.lib_Device.getByLcscIds([want.key], undefined, false); d = f && f[0]; }
const c = await eda.sch_PrimitiveComponent.create({ libraryUuid: d.libraryUuid, uuid: d.uuid }, want.x, want.y, '', 0, false, want.bom, true);
await eda.sch_PrimitiveComponent.modify(c.getState_PrimitiveId(), { designator: ref, addIntoBom: want.bom });
return { removedWires: kill.length, removedParts: comps.length, placed: c.getState_PrimitiveId() };
"""


def main():
    ref, old_key = sys.argv[1], sys.argv[2]
    lay = json.load(open("layout.json"))
    x, y = lay["pos"][ref]
    old_lines = []
    for p in SYMS[old_key]["pins"]:
        px, py = x + p["dx"], y + p["dy"]
        dx, dy = {0: (STUB, 0), 90: (0, STUB), 180: (-STUB, 0), 270: (0, -STUB)}[int(p["rot"] or 0) % 360]
        old_lines.append(",".join(str(round(v, 3)) for v in (px, py, px + dx, py + dy)))
    key = PARTS[ref][0]
    want = {"key": key, "dev": DEVICES.get(key), "x": x, "y": y, "bom": PARTS[ref][3]}
    js = (JS.replace("__PAGE__", SCH_PAGE).replace("__REF__", ref).replace("__OLDLINES__", json.dumps(old_lines))
          .replace("__WANT__", json.dumps(want)))
    print(run(js, retry_on_drop=False))


if __name__ == "__main__":
    main()
