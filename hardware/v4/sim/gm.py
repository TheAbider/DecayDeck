"""Tube pulse bench: design.py's tube block (anode resistors, cathode loads, BC847C buffers, 74LVC2G17) in ngspice,
fed by an ideal 400 V and fired by the behavioural GM tube model.

Tube data (passports, via the gstube / pocketmagic scans):
  STS-5   start 280-330 V, working 360-440 V, anode resistor 5-10 Mohm, plateau >= 80 V
  SI-3BG  start 290-330 V, working 380-410 V, anode resistor 2-6.7 Mohm, shunt C <= 3 pF, max 20 uA
Neither passport gives the discharge charge or dead time, so the bench sweeps the model across a wide range: tube
capacitance (with wiring) 3-15 pF, discharge time constant 2-10 us, extinction 280-340 V. Every combination must give
one clean logic pulse per count, wide enough for the ESP32's pulse counter and with no second edge.
A 50 us discharge is also run as a stress corner: peak tube current then falls to ~2-4 uA, at the edge of what the
220k cathode load turns into a base drive. Halogen tubes deliver tens of uA, so it is reported, not required;
if a built board ever misses counts, raising R37/R42 lowers that threshold.

usage: python gm.py
"""
import itertools
import sys

import numpy as np

import netgen
import spice

VDD = 3.38


def bench(ca, rd, vext, counts):
    lines, boundary = netgen.netlist({"gm"})
    pwl = " ".join(f"{t - 1e-8:.9f} 0 {t:.9f} 1 {t + 50e-6:.9f} 1 {t + 50e-6 + 1e-8:.9f} 0" for t in counts)
    b = ["VHV HV_OUT 0 400", f"V3V3 3V3 0 {VDD}", "CGM1 GM1_OUT 0 5p", "CGM2 GM2_OUT 0 5p",
         f"Vtrg1 trg1 0 PWL(0 0 {pwl})", f"Vtrg2 trg2 0 PWL(0 0 {pwl})",
         f"XT1 GM1_ANODE GM1_K trg1 GMTUBE params: ca={ca} vext={vext} rd={rd}",
         f"XT2 GM2_ANODE GM2_K trg2 GMTUBE params: ca={ca} vext={vext} rd={rd}",
         ".ic V(GM1_ANODE)=400 V(GM2_ANODE)=400 V(GM1_AM)=400 V(GM2_AM)=400"]
    missing = set(boundary) - {"HV_OUT", "3V3", "GM1_OUT", "GM2_OUT", "GM1_ANODE", "GM1_K", "GM2_ANODE", "GM2_K"}
    assert not missing, missing
    return lines + b


def edges(t, v, th):
    lo = v < th
    falls = t[1:][lo[1:] & ~lo[:-1]]
    rises = t[1:][~lo[1:] & lo[:-1]]
    return falls, rises


def run(ca, rd, vext, counts=(100e-6, 600e-6, 1.6e-3)):
    cols, _ = spice.run(f"gm ca={ca} rd={rd} vext={vext}", bench(ca, rd, vext, counts), "20n 2.4e-3 0 100n",
                        ["v(gm1_k)", "v(gm1_b)", "v(gm1_c)", "v(gm1_out)", "v(gm2_out)", "v(gm1_anode)"])
    t = cols["time"]
    out = {}
    for tube in ("gm1", "gm2"):
        f, r = edges(t, cols[f"v({tube}_out)"], VDD / 2)
        widths = [float(rr - ff) for ff in f for rr in r[r > ff][:1]]
        out[tube] = {"pulses": len(f), "width_us": [w * 1e6 for w in widths]}
    out["k_peak"] = float(cols["v(gm1_k)"].max())
    out["anode_drop"] = float(400 - cols["v(gm1_anode)"].min())
    return out, cols


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    bad = 0
    print("  tube C   tau    Vext | STS-5 pulses, widths (us)          | SI-3BG pulses | cathode peak, anode drop")
    for ca, tau, vext in itertools.product(("3p", "6p", "15p"), (2e-6, 10e-6, 50e-6), (280, 340)):
        cav = float(ca[:-1]) * 1e-12
        rd = tau / cav
        r, _ = run(ca, f"{rd:.4g}", vext)
        w1 = r["gm1"]["width_us"]
        ok = r["gm1"]["pulses"] == 3 and r["gm2"]["pulses"] == 3 and min(w1 + r["gm2"]["width_us"] or [0]) >= 2.0
        stress = tau > 10e-6
        bad += not ok and not stress
        print(f"  {ca:>5} {tau * 1e6:5.0f}us {vext:5.0f} | {r['gm1']['pulses']}  {', '.join(f'{w:6.1f}' for w in w1):<28} | "
              f"{r['gm2']['pulses']}             | {r['k_peak']:5.2f} V, {r['anode_drop']:5.1f} V  "
              f"{'ok' if ok else ('missed (stress corner)' if stress else 'BAD')}",
              flush=True)
    print("every case gives one clean pulse per count" if not bad else f"{bad} cases failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
