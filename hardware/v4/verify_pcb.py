"""Check the PCB's pad nets against design.py. The board must match the spec pin-for-pin.

usage: python verify_pcb.py   (writes pcb_pads.json)
Exit 1 on any mismatch, missing part, or extra part.
"""
import json
import sys

from check_spec import resolved_nets
from design import PARTS
from eda import run

PCB = "6098964f68a86131"
JS = r"""
await eda.dmt_EditorControl.openDocument('__PCB__');
const comps = await eda.pcb_PrimitiveComponent.getAll();
return comps.map(c => ({ des: c.getState_Designator(), id: c.getState_PrimitiveId(), x: c.getState_X(), y: c.getState_Y(),
  rot: c.getState_Rotation(), layer: c.getState_Layer(), fp: (c.getState_Footprint() || {}).name, pads: c.getState_Pads() }));
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    r = run(JS.replace("__PCB__", PCB))
    if not r.get("success"):
        print("fetch failed:", r.get("error"))
        return 1
    comps = r["result"]
    json.dump(comps, open("pcb_pads.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    nets, errors = resolved_nets()
    want = {}
    for net, members in nets.items():
        for m in members:
            want[m] = net
    have = {}
    seen = {}
    for c in comps:
        seen.setdefault(c["des"], 0)
        seen[c["des"]] += 1
        for p in c["pads"] or []:
            key = (c["des"], p["padNumber"])
            # a pad number can repeat (multi-pad pins); all copies must agree
            if key in have and have[key] != (p["net"] or ""):
                errors.append(f"{key} pads disagree: {have[key]!r} vs {p['net']!r}")
            have[key] = p["net"] or ""
    for d, n in seen.items():
        if n > 1:
            errors.append(f"{d} appears {n} times on the PCB")
        if d not in PARTS:
            errors.append(f"extra part on PCB: {d}")
    for d in PARTS:
        if d not in seen:
            errors.append(f"missing on PCB: {d}")
    for key, net in sorted(want.items()):
        if key not in have:
            errors.append(f"spec pin {key} ({net}) has no PCB pad")
        elif have[key] != net:
            errors.append(f"{key}: PCB net {have[key]!r} != spec {net!r}")
    for key, net in sorted(have.items()):
        if net and key not in want:
            errors.append(f"{key}: PCB has net {net!r} but spec leaves it unconnected")
    for e in errors:
        print("MISMATCH", e)
    print(f"{len(comps)} parts, {len(have)} pads checked against {len(want)} spec pins: "
          f"{'OK' if not errors else str(len(errors)) + ' problems'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
