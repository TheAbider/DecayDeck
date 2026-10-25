"""Export the schematic from EasyEDA: SVG / PNG picture or the netlist, run detached so a slow export can outlast
the bridge's 30 s request limit.

usage: python sch_export.py svg|png|pdf|netlist OUT_FILE
"""
import base64
import json
import sys
import time

from eda import run

SCH_PAGE = "78286f62bfd019a0"
CALLS = {
    "svg": "eda.sch_ManufactureData.getSvgFile('DecayDeck_v4_schematic')",
    "png": "eda.sch_ManufactureData.getPngFile('DecayDeck_v4_schematic')",
    "netlist": "eda.sch_ManufactureData.getNetlistFile('DecayDeck_v4_netlist')",
    "pdf": "eda.sch_ManufactureData.getExportDocumentFile('DecayDeck_v4_schematic', 'PDF', "
           "{ theme: 'Default', size: 'Original Size' }, 'Current Schematic Page')",
}
START = r"""
await eda.dmt_EditorControl.openDocument('__PAGE__');
globalThis.__ddExport = { started: Date.now(), done: false };
(async () => {
  const f = await __CALL__;
  if (!f) return null;
  const buf = new Uint8Array(await f.arrayBuffer());
  let s = '';
  for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  return { name: f.name, size: buf.length, b64: btoa(s) };
})().then(r => { globalThis.__ddExport.result = r; globalThis.__ddExport.done = true; })
   .catch(e => { globalThis.__ddExport.error = String(e); globalThis.__ddExport.done = true; });
return 'started';
"""
POLL = r"""
const s = globalThis.__ddExport;
if (!s) return null;
if (!s.done) return { done: false, secs: Math.round((Date.now() - s.started) / 1000) };
return { done: true, error: s.error, result: s.result };
"""


def export(kind, out):
    print(run(START.replace("__PAGE__", SCH_PAGE).replace("__CALL__", CALLS[kind]), retry_on_drop=False).get("result"))
    for _ in range(80):
        time.sleep(3)
        st = (run(POLL, timeout=60) or {}).get("result")
        if not st:
            raise SystemExit("lost the export state")
        if st["done"]:
            if st.get("error") or not st.get("result"):
                raise SystemExit(f"export failed: {st.get('error')}")
            data = base64.b64decode(st["result"]["b64"])
            open(out, "wb").write(data)
            print(f"{kind}: {out} ({len(data)} bytes, EasyEDA name {st['result']['name']})")
            return out
    raise SystemExit("export timed out")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    export(sys.argv[1], sys.argv[2])
