"""Autorouting passes with EasyEDA's router.

usage: python route.py hv       -> HV nets only, top layer (keeps whatever already exists)
       python route.py rest     -> everything else on top + bottom, planes excluded
Each pass starts the router detached (it can run up to EasyEDA's 15 min cap, past the bridge's 30 s request limit)
and polls until it reports its result.
"""
import json
import sys
import time

from eda import run
from place_pcb import HV_NETS

PLANE_NETS = ["GND", "3V3"]
ROUTE = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
globalThis.__ddRoute = { started: Date.now(), done: false };
eda.pcb_Document.autoRouting(__PROPS__)
  .then(r => { globalThis.__ddRoute.result = r; globalThis.__ddRoute.done = true; })
  .catch(e => { globalThis.__ddRoute.error = String(e); globalThis.__ddRoute.done = true; });
return 'started';
"""
POLL = r"""
const s = globalThis.__ddRoute;
return s ? { done: s.done, secs: Math.round((Date.now() - s.started) / 1000), result: s.result, error: s.error } : null;
"""


def route(props):
    print(run(ROUTE.replace("__PROPS__", json.dumps(props)), retry_on_drop=False))
    while True:
        time.sleep(15)
        r = run(POLL)
        st = r.get("result")
        if not st:
            print("lost the router state:", r)
            return None
        if st["done"]:
            print(f"router finished after {st['secs']} s:", json.dumps(st.get("result"))[:1500], st.get("error") or "")
            return st
        print(f"  routing... {st['secs']} s", flush=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cmd = sys.argv[1]
    if cmd == "hv":
        props = {"RoutingNets": sorted(HV_NETS), "layers": [1]}
    elif cmd == "rest":
        props = {"layers": [1, 2], "ignoreNets": sorted(HV_NETS) + PLANE_NETS}
    else:
        props = None
    if props is not None:
        route(props)


if __name__ == "__main__":
    main()
