"""Check the datasheet-fitted transistor models against their datasheet tables (the test conditions are the
datasheet's own). A model only goes into a bench after its row here passes.

usage: python fit_models.py
"""
import sys

import numpy as np

import spice


def dc_point(model, ic, ib=None, vce=None):
    """Solve for VBE at a forced IC / IB (saturation) or IC / VCE (gain): returns (vbe, vce, hfe)."""
    if ib is not None:
        body = [f"Q1 c b 0 {model}", f"Ib 0 b {ib}", f"Ic 0 c {ic}"]
        vec = ["v(b)", "v(c)"]
    else:
        body = [f"Q1 c b 0 {model}", f"Vc c 0 {vce}", "Ib 0 b 1u"]
        vec = ["v(b)", "v(c)", "vc#branch", "@q1[ib]"]
    if ib is None:
        # sweep base current to find the one giving ic
        body = [f"Q1 c b 0 {model}", f"Vc c 0 {vce}", "Ib 0 b PWL(0 0 1 5m)"]
        cols, _ = spice.run("hfe", body, "1m 1 0 1m", ["v(b)", "vc#branch"])
        icv = -cols["vc#branch"]
        ibv = cols["time"] * 5e-3
        k = np.searchsorted(icv, ic)
        return cols["v(b)"][k], vce, icv[k] / ibv[k]
    cols, _ = spice.run("sat", body, "1u 10u", vec)
    return cols["v(b)"][-1], cols["v(c)"][-1], ic / ib


def switching(model, vcc, rc, ib1, ib2, rb_on=None):
    """Datasheet switching test: base current ib1 on, then pulled to ib2 (negative) for turn-off.
    Returns (ton, toff) between 10 % / 90 % collector current points."""
    body = [f"Q1 c b 0 {model}", f"Vcc vcc 0 {vcc}", f"Rc vcc c {rc}",
            f"Ib 0 b PWL(0 0 1u 0 1.001u {ib1} 11u {ib1} 11.001u {ib2} 30u {ib2})", "Db 0 b DCLAMP",
            ".model DCLAMP D(IS=1e-15 N=1)"]
    cols, _ = spice.run("switch", body, "1n 30u 0 2n", ["v(c)"])
    t, vc = cols["time"], cols["v(c)"]
    ic = (vcc - vc) / rc
    hi = ic[(t > 9e-6) & (t < 11e-6)].mean()
    on = t[(t > 1e-6) & (ic >= 0.9 * hi)][0] - 1.001e-6
    off = t[(t > 11.001e-6) & (ic <= 0.1 * hi)][0] - 11.001e-6
    return on, off


def main():
    rows = []
    vbe, vce, _ = dc_point("FMMT458", 20e-3, ib=2e-3)
    rows.append(("FMMT458 VCE(sat) 20 mA / 2 mA", f"{vce * 1e3:.0f} mV", "<= 200 mV", vce <= 0.2))
    vbe, vce, _ = dc_point("FMMT458", 50e-3, ib=6e-3)
    rows.append(("FMMT458 VCE(sat) 50 mA / 6 mA", f"{vce * 1e3:.0f} mV", "<= 500 mV", vce <= 0.5))
    vbe, vce, _ = dc_point("FMMT458", 50e-3, ib=5e-3)
    rows.append(("FMMT458 VBE(sat) 50 mA / 5 mA", f"{vbe:.2f} V", "<= 0.90 V", vbe <= 0.9))
    for ic, lo, hi in ((1e-3, 100, 1e9), (50e-3, 100, 300), (100e-3, 15, 1e9)):
        _, _, hfe = dc_point("FMMT458", ic, vce=10)
        rows.append((f"FMMT458 hFE {ic * 1e3:.0f} mA, 10 V", f"{hfe:.0f}", f"{lo}-{hi if hi < 1e9 else ''}", lo <= hfe <= hi))
    ton, toff = switching("FMMT458", 100, 2000, 5e-3, -10e-3)
    rows.append(("FMMT458 ton (100 V, 50 mA, 5 mA)", f"{ton * 1e9:.0f} ns", "135 ns typ", 50e-9 < ton < 400e-9))
    rows.append(("FMMT458 toff (IB2 -10 mA)", f"{toff * 1e9:.0f} ns", "2260 ns typ", 1.3e-6 < toff < 3.4e-6))
    _, _, hfe = dc_point("BC847C", 2e-3, vce=5)
    rows.append(("BC847C hFE 2 mA, 5 V", f"{hfe:.0f}", "420-800", 420 <= hfe <= 800))
    vbe, vce, _ = dc_point("BC847C", 10e-3, ib=0.5e-3)
    rows.append(("BC847C VCE(sat) 10 mA / 0.5 mA", f"{vce * 1e3:.0f} mV", "<= 250 mV", vce <= 0.25))
    w = max(len(r[0]) for r in rows)
    for name, got, want, ok in rows:
        print(f"  {'ok ' if ok else 'BAD'} {name:<{w}}  model {got:>9}   datasheet {want}")
    return 0 if all(r[3] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
