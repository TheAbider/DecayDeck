"""Picture of the schematic as EasyEDA draws it: zoom the editor to a region and copy its canvas.
(The SVG/PNG export calls never return in the desktop client, so this reads the live canvas instead.)

usage: python sch_snap.py OUT.png [LEFT RIGHT TOP BOTTOM]   (schematic units; no region = everything)
"""
import base64
import json
import sys
import time

from eda import run

SCH_PAGE = "78286f62bfd019a0"
JS = r"""
const tab = await eda.dmt_EditorControl.openDocument('__PAGE__');
await eda.dmt_EditorControl.activateDocument(tab);
await new Promise(r => setTimeout(r, 800));
const reg = __REGION__;
const z = reg ? await eda.dmt_EditorControl.zoomToRegion(reg[0], reg[1], reg[2], reg[3], tab)
              : await eda.dmt_EditorControl.zoomToAllPrimitives(tab);
await new Promise(r => setTimeout(r, 1500));
// the schematic editor draws into one canvas inside a div (the PCB editor uses an iframe)
const host = Array.from(document.querySelectorAll('div')).find(e => (e.id || '').startsWith('frame___PAGE__'));
const c = host && host.querySelector('canvas');
const out = { zoom: z, host: !!host };
if (c) { out.size = [c.width, c.height]; out.png = c.toDataURL('image/png').split(',')[1]; }
return out;
"""


def snap(out, region=None):
    r = run(JS.replace("__PAGE__", SCH_PAGE).replace("__REGION__", json.dumps(region)), timeout=60)
    res = r.get("result") or {}
    if not res.get("png"):
        raise SystemExit(f"no canvas: {json.dumps({k: v for k, v in res.items() if k != 'png'})} {r.get('error') or ''}")
    open(out, "wb").write(base64.b64decode(res["png"]))
    print(out, res["size"], "zoom", res["zoom"])
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    snap(sys.argv[1], [float(v) for v in sys.argv[2:6]] if len(sys.argv) > 5 else None)
