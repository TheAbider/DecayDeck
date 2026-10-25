"""Check the schematic's netlist against design.py, pin for pin (the schematic counterpart of verify_pcb.py).
Exports the netlist from EasyEDA (sch_export.py), then compares every component pin's net with the spec:
a spec pin must carry its spec net, and a pin the spec leaves out must be unconnected.

usage: python sch_check.py [netlist.enet]   (no argument: export a fresh one)
Exit 1 on any mismatch.
"""
import json
import os
import sys
import tempfile

from check_spec import resolved_nets
from design import PARTS


def main(fn=None):
    if not fn:
        from sch_export import export
        fn = export("netlist", os.path.join(tempfile.gettempdir(), "decaydeck_v4_check.enet"))
    data = json.load(open(fn, encoding="utf-8"))
    nets, errors = resolved_nets()
    if errors:
        print("spec errors:", errors)
        return 1
    want = {m: net for net, members in nets.items() for m in members}
    seen, bad = {}, []
    for comp in data["components"].values():
        ref = comp["props"].get("Designator", "")
        if ref not in PARTS:
            continue   # net flags, ports and other non-part symbols
        seen[ref] = seen.get(ref, 0) + 1
        for num, pin in comp["pinInfoMap"].items():
            have = pin.get("net") or ""
            exp = want.get((ref, num), "")
            if have != exp:
                bad.append(f"{ref}.{num} ({pin.get('name')}): schematic {have or '-'} / spec {exp or '-'}")
    missing = sorted(set(PARTS) - set(seen))
    dupes = sorted(r for r, n in seen.items() if n > 1)
    pins = sum(len(c["pinInfoMap"]) for c in data["components"].values() if c["props"].get("Designator") in PARTS)
    print(f"{len(seen)} parts, {pins} pins checked against {len(want)} spec pins: "
          f"{len(bad)} mismatches, {len(missing)} missing, {len(dupes)} duplicated")
    for b in bad[:40]:
        print("  ", b)
    if missing:
        print("   missing:", missing)
    if dupes:
        print("   duplicated:", dupes)
    return 1 if (bad or missing or dupes) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
