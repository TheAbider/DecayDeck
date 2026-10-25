"""Phase 0: place one instance of every unique part far off-sheet, record its pin geometry relative to
the part origin, then remove the probes. Writes symbols.json: key -> {pins: [{num, name, dx, dy, rot}], lcsc...}.

usage: python probe_symbols.py   (run from hardware/v4; needs the bridge and DecayDeck V4 open on its schematic)
"""
import json
import os
import sys

sys.path.insert(0, os.environ.get("EDA_TOOLS", "."))
from eda import run  # noqa: E402

from design import DEVICES, PARTS  # noqa: E402

SCH_PAGE = "78286f62bfd019a0"
BATCH = 5

JS = r"""
await eda.dmt_EditorControl.openDocument('__PAGE__');
const keys = __KEYS__;
const devmap = __DEVMAP__;
const lcsc = keys.filter(k => !devmap[k]);
const found = lcsc.length ? await eda.lib_Device.getByLcscIds(lcsc, undefined, false) : [];
const byCode = {};
for (const d of found || []) byCode[d.supplierId] = d;
const out = {};
let x = 20000;
for (const k of keys) {
  const d = devmap[k] || byCode[k];
  if (!d) { out[k] = { missing: true }; continue; }
  const c = await eda.sch_PrimitiveComponent.create({ libraryUuid: d.libraryUuid, uuid: d.uuid }, x, 20000, '', 0, false, true, true);
  x += 500;
  if (!c) { out[k] = { failed: true }; continue; }
  const id = c.getState_PrimitiveId();
  const cx = c.getState_X(), cy = c.getState_Y();
  const pins = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(id);
  out[k] = {
    mpn: d.manufacturerId || null, lcsc: d.supplierId || null, footprint: d.footprintName || null,
    libraryUuid: d.libraryUuid, uuid: d.uuid,
    pins: (pins || []).map(p => ({ num: p.getState_PinNumber(), name: p.getState_PinName(),
      dx: p.getState_X() - cx, dy: p.getState_Y() - cy, rot: p.getState_Rotation() })),
  };
  await eda.sch_PrimitiveComponent.delete([id]);
}
return out;
"""


def main():
    keys = sorted({p[0] for p in PARTS.values()})
    result = {}
    if os.path.exists("symbols.json"):
        result = json.load(open("symbols.json", encoding="utf-8"))
    todo = [k for k in keys if k not in result or result[k].get("missing") or result[k].get("failed")]
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        devmap = {k: DEVICES[k] for k in batch if k in DEVICES}
        code = (JS.replace("__PAGE__", SCH_PAGE).replace("__KEYS__", json.dumps(batch))
                .replace("__DEVMAP__", json.dumps(devmap)))
        r = run(code)
        if not r.get("success"):
            print("batch failed:", batch, r.get("error"))
            continue
        result.update(r["result"])
        json.dump(result, open("symbols.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"probed {len(batch)}: {', '.join(batch)}")
    bad = [k for k in keys if k not in result or result[k].get("missing") or result[k].get("failed")]
    print("missing/failed:", bad)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
