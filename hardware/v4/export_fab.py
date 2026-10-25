"""Export the JLCPCB fabrication set from EasyEDA: Gerber zip, BOM (csv) and pick-and-place (csv).
Files land in hardware/v4/fab/<date>/.

usage: python export_fab.py
"""
import base64
import datetime
import os
import sys

from eda import run

JS = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const f = await __CALL__;
if (!f) return null;
const buf = new Uint8Array(await f.arrayBuffer());
let s = '';
for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
return { name: f.name, size: buf.length, b64: btoa(s) };
"""
CALLS = {
    "gerber": "eda.pcb_ManufactureData.getGerberFile('DecayDeck_v4_Gerber')",
    "bom": "eda.pcb_ManufactureData.getBomFile('DecayDeck_v4_BOM', 'csv')",
    "cpl": "eda.pcb_ManufactureData.getPickAndPlaceFile('DecayDeck_v4_CPL', 'csv', 'mm')",
}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out = os.path.join("fab", datetime.date.today().isoformat())
    os.makedirs(out, exist_ok=True)
    for key, call in CALLS.items():
        r = run(JS.replace("__CALL__", call), timeout=120)
        res = r.get("result")
        if not r.get("success") or not res:
            print(key, "FAILED", r.get("error"))
            continue
        name = res["name"]
        if not os.path.splitext(name)[1]:   # EasyEDA leaves the Gerber zip and the CPL without an extension
            name += {"gerber": ".zip", "bom": ".csv", "cpl": ".csv"}[key]
        path = os.path.join(out, name)
        with open(path, "wb") as f:
            f.write(base64.b64decode(res["b64"]))
        print(key, path, res["size"], "bytes")


if __name__ == "__main__":
    main()
