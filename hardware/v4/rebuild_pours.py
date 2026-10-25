"""Rebuild every copper pour: EasyEDA's own "Rebuild All Copper Area" (Shift+B).

The API can't fill pours that were made through the API: rebuildCopperRegion() returns nothing for them (the
EasyEDA 3.2 API docs say as much), so this sends the PCB editor its own Shift+B shortcut. If the editor's copper
worker has stopped answering, the editor logs "buildCopper received no worker response" and fills nothing; then
the PCB is saved, its tab closed and reopened (which starts a fresh worker) and the shortcut sent again.

usage: python rebuild_pours.py
"""
import sys
import time

from eda import run

PCB = "6098964f68a86131"
SHIFT_B = r"""
const PCB = '__PCB__';
await eda.dmt_EditorControl.openDocument(PCB);
const f = document.querySelector('iframe[id^="frame_' + PCB + '"]');
if (!f) return { error: 'PCB editor frame not found' };
const W = f.contentWindow, D = W.document;
const wait = (ms) => new Promise(r => setTimeout(r, ms));
const sig = async () => { let n = 0, s = 0; for (const p of await eda.pcb_PrimitivePoured.getAll()) for (const q of p.getState_PourFills()) { n++; s += JSON.stringify(q.path).length; } return n + ':' + s; };
const before = await sig();
const errors = [], orig = W.console.error;
W.console.error = function (...a) { try { errors.push(a.map(String).join(' ').slice(0, 200)); } catch (e) {} return orig.apply(this, a); };
const key = (type, k, code, kc, shift) => { const ev = new W.KeyboardEvent(type, { key: k, code, shiftKey: shift, bubbles: true, cancelable: true, composed: true, view: W });
  Object.defineProperty(ev, 'keyCode', { get: () => kc }); Object.defineProperty(ev, 'which', { get: () => kc }); return ev; };
const el = D.querySelector('canvas#canvas') || D.body;
el.dispatchEvent(key('keydown', 'Shift', 'ShiftLeft', 16, true));
el.dispatchEvent(key('keydown', 'B', 'KeyB', 66, true));
el.dispatchEvent(key('keyup', 'B', 'KeyB', 66, true));
el.dispatchEvent(key('keyup', 'Shift', 'ShiftLeft', 16, false));
let last = null, now = before;
const t0 = Date.now();
while (Date.now() - t0 < 20000) {
  await wait(1000);
  if (errors.some(e => /buildCopper/.test(e))) break;
  now = await sig();
  if (now === last && now !== before) break;
  last = now;
}
W.console.error = orig;
return { before, after: await sig(), errors };
"""
REOPEN = r"""
const PCB = '__PCB__';
const tab = await eda.dmt_EditorControl.openDocument(PCB);
if (await eda.pcb_Document.save() !== true) return { error: 'save failed; not closing the tab' };
await new Promise(r => setTimeout(r, 1500));
const closed = await eda.dmt_EditorControl.closeDocument(tab);
await new Promise(r => setTimeout(r, 2500));
return { closed, reopened: await eda.dmt_EditorControl.openDocument(PCB) };
"""


def attempt():
    r = run(SHIFT_B.replace("__PCB__", PCB), timeout=45, retry_on_drop=False)
    if not r.get("success"):
        raise SystemExit(r.get("error"))
    return r["result"]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    res = attempt()
    stuck = any("buildCopper" in e for e in res.get("errors", [])) or res.get("after", "0:0").startswith("0:")
    if stuck:
        print("copper worker not answering:", res.get("errors"), "-> saving and reopening the PCB tab")
        print(run(REOPEN.replace("__PCB__", PCB), timeout=60, retry_on_drop=False).get("result"))
        time.sleep(5)
        res = attempt()
    n = int(res.get("after", "0:0").split(":")[0])
    state = "rebuilt" if res.get("after") != res.get("before") else "unchanged (same copper as before)"
    print(f"pours {state}: {n} fill pieces", res.get("errors") or "")
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
