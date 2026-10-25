"""Design rules: HV spacing class, HV and power track widths, and the per-net assignments.
Builds on the PCB's current rule configuration.

HV class (IPC-2221B table 6-1, 301-500 V, uncoated): 2.5 mm conductor-to-conductor (B2) everywhere, except where a
pad is involved, which IPC rates as a component termination (A7, 1.5 mm): SMD pad to track 1.5 mm, SMD pad to SMD pad
1.4 mm. Those two exist so the parts' own footprints pass (1206 pads 1.69-1.75 mm apart, the FMMT458's SOT-23
collector 1.44 mm from its base, and a track leaving a 1206 pad ~2.15 mm from the other pad). Placement
(place_pcb.py check) still holds every HV pad 2.5 mm from every other part's pads.

usage: python setup_rules.py
"""
import copy
import json
import sys

from eda import run
from place_pcb import HV_NETS

POWER_NETS = ["VBUS", "VSYS", "VBAT_P", "BAT_RAW", "3V3", "GND", "HV_VIN", "BB_L1", "BB_L2"]
HV_CLEAR_MM = 2.5
HV_PAD_TRACK_MM = 1.5     # IPC-2221B A7, 301-500 V
HV_PAD_PAD_MM = 1.4       # tightest HV footprint: FMMT458 SOT-23, 1.44 mm
TRACK, SMD_PAD, SLOT = 0, 1, 8   # row / column order of the Safe Spacing table
# The only slot regions on the board are the boss holes inside the LCSC footprint of the Alps SKRTLAE010 side buttons
# (C110293), drawn 0.075 mm from that same switch's terminals. That is the part's own land pattern, not a routing
# clearance (JLC clips copper at NPTH); track-to-slot stays at the default 0.3 mm.
SLOT_SMD_MM = 0.07

GET = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
return { cfg: await eda.pcb_Drc.getCurrentRuleConfiguration(), net: await eda.pcb_Drc.getNetRules() };
"""
SET = r"""
await eda.dmt_EditorControl.openDocument('6098964f68a86131');
const a = await eda.pcb_Drc.overwriteCurrentRuleConfiguration(__CFG__.config);
const b = await eda.pcb_Drc.overwriteNetRules(__NET__);
return { cfg: a, net: b, name: await eda.pcb_Drc.getCurrentRuleConfigurationName() };
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    r = run(GET)
    if not r.get("success"):
        raise SystemExit(r.get("error"))
    cfg, net_rules = r["result"]["cfg"], r["result"]["net"]
    cfg = copy.deepcopy(cfg)
    cfg["name"] = "DecayDeck v4"
    ss = cfg["config"]["Spacing"]["Safe Spacing"]
    base = next(v for v in ss.values() if v.get("isSetDefault"))
    hv = copy.deepcopy(base)
    hv["editName"], hv["isSetDefault"] = "HV", False
    assert hv["row"][TRACK] == "Track" and hv["row"][SMD_PAD] == "SMD Pad", hv["row"]
    for t in hv["tables"].values():
        t["content"] = [[HV_CLEAR_MM] * len(row) for row in t["content"]]
        t["content"][SMD_PAD][TRACK] = HV_PAD_TRACK_MM
        t["content"][SMD_PAD][SMD_PAD] = HV_PAD_PAD_MM
    ss["HV"] = hv
    assert base["row"][SLOT] == "Slot Region", base["row"]
    for t in base["tables"].values():
        t["content"][SLOT][SMD_PAD] = SLOT_SMD_MM
    track = cfg["config"]["Physics"]["Track"]
    tbase = next(v for v in track.values() if v.get("isSetDefault"))
    for name, (mn, df) in {"PWR": (0.3, 0.5), "HV": (0.3, 0.4)}.items():
        t = copy.deepcopy(tbase)
        t["editName"], t["isSetDefault"] = name, False
        for d in t["form"]["data"].values():
            d["minValue"], d["defaultValue"] = mn, df
        track[name] = t
    changed = 0
    for nr in net_rules:
        if nr.get("type") != "net":
            continue
        if nr["name"] in HV_NETS:
            nr["Safe Spacing"], nr["Track"] = "HV", "HV"
            changed += 1
        elif nr["name"] in POWER_NETS:
            nr["Track"] = "PWR"
            changed += 1
    r = run(SET.replace("__CFG__", json.dumps(cfg)).replace("__NET__", json.dumps(net_rules)))
    print(r, f"({changed} nets assigned)")


if __name__ == "__main__":
    main()
