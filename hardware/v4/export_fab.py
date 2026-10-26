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


def align_cpl(out):
    """The CPL's Device column names the library device each part was placed from. A part re-valued in place keeps
    its old device's name there (R25: 330R -> 150R), so wherever that name's part number (before any _Cxxxx
    suffix) disagrees with the BOM, write the BOM's. Everything else in the file is left byte for byte."""
    bom = open(os.path.join(out, "DecayDeck_v4_BOM.csv"), "rb").read().decode("utf-16").split("\n")
    mpn = {}
    for line in bom[1:]:
        f = line.split("\t")
        if len(f) > 6:
            for d in f[3].split(","):
                mpn[d.strip()] = f[6]
    path = os.path.join(out, "DecayDeck_v4_CPL.csv")
    lines = open(path, "rb").read().decode("utf-16").split("\n")
    for i, line in enumerate(lines[1:], 1):
        f = line.split("\t")             # the CPL quotes every field; the BOM quotes none
        if len(f) < 2:
            continue
        ref, dev = f[0].strip('"'), f[1].strip('"')
        if ref in mpn and dev.split("_C")[0] != mpn[ref]:
            print(f"CPL {ref}: device {dev} -> {mpn[ref]} (as the BOM)")
            f[1] = f'"{mpn[ref]}"' if f[1].startswith('"') else mpn[ref]
            lines[i] = "\t".join(f)
    open(path, "wb").write("\n".join(lines).encode("utf-16"))


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
    align_cpl(out)


if __name__ == "__main__":
    main()
