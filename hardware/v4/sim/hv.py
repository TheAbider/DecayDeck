"""HV supply bench: design.py's HV and tube blocks in ngspice, driven the way the firmware will drive them.

The ESP32 is replaced by what it does to these nets: HV_PWM is a pulse train (GPIO, ~40 ohm), HV_REF_PWM is a PWM
whose average sets the target (R28/R29/C23 filter it with a 43 ms time constant, so its average stands in for it),
HV_FB_ADC is an ADC input. The tubes are the behavioural GM model, idle unless a test fires counts.

usage: python hv.py [startup|sweep [drive index]|faults|all]     (default all; results go to sim/results/)
"""
import os
import re
import sys

import numpy as np

import netgen
import spice

VDD = 3.38                       # 3V3 rail (TPS63802 set point)
RATIO = 301.0                    # HV_OUT / HV_FB
REF_MAX = VDD * 75 / 175         # HV_REF at 100 % duty
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
IDLE_TUBES = ["Vtrg1 trg1 0 0", "Vtrg2 trg2 0 0"]


def tube_lines(trg1="Vtrg1 trg1 0 0", trg2="Vtrg2 trg2 0 0"):
    # STS-5 / SI-3BG, see gm.py for the parameters' sources
    return [trg1, trg2,
            "XT1 GM1_ANODE GM1_K trg1 GMTUBE params: ca=5p vext=330 rd=4Meg",
            "XT2 GM2_ANODE GM2_K trg2 GMTUBE params: ca=3p vext=330 rd=4Meg"]


def bench(pwm_hz, ton, target, comp=None, pwm_dc=None, extra_load=None, scale=None, tubes=None, ic=False):
    lines, boundary = netgen.netlist({"hv", "gm"}, scale)
    if comp is not None:   # fault: comparator output stuck
        lines = [l for l in lines if not l.startswith("XU9 ")] + [f"VCOMP HV_COMP 0 {comp}"]
    duty = target / (REF_MAX * RATIO)
    if duty > 1:
        raise ValueError(f"{target} V is above the hardware ceiling {REF_MAX * RATIO:.0f} V")
    pwm = f"DC {pwm_dc}" if pwm_dc is not None else f"PULSE(0 {VDD} 20u 5n 5n {ton} {1 / pwm_hz})"
    b = ["V3V3 3V3 0 " + str(VDD),
         f"VPWM pwm_src 0 {pwm}", "RPWM pwm_src HV_PWM 40",
         f"VREF ref_src 0 {VDD * duty}", "RREF ref_src HV_REF_PWM 40",
         "CADC HV_FB_ADC 0 10p", "CGM1 GM1_OUT 0 5p", "CGM2 GM2_OUT 0 5p",
         *(tubes or tube_lines())]
    if extra_load:
        b.append(f"RLOAD HV_OUT 0 {extra_load}")
    handled = {"3V3", "HV_PWM", "HV_REF_PWM", "HV_FB_ADC", "GM1_OUT", "GM2_OUT", "GM1_ANODE", "GM1_K", "GM2_ANODE",
               "GM2_K"}
    missing = set(boundary) - handled
    assert not missing, f"bench leaves boundary nets undriven: {missing}"
    if ic:   # start at the operating point to study steady state without simulating the start-up
        v = target
        b.append(f".ic V(HV_OUT)={v} V(HV_V1)={v / 2} V(HV_M)={v / 2} V(HV_REF)={target / RATIO} "
                 f"V(HV_FB)={target / RATIO} V(HV_D1)={v * 201 / 301} V(HV_D2)={v * 101 / 301} "
                 f"V(HV_B1)={v * 2 / 3} V(HV_B2)={v / 3} V(GM1_AM)={v} V(GM1_ANODE)={v} V(GM2_AM)={v} V(GM2_ANODE)={v}")
    return lines + b


VECS = ["v(hv_out)", "v(hv_fb)", "v(hv_ref)", "v(hv_sw)", "v(hv_v1)", "v3v3#branch", "l2#branch", "@q3[ic]",
        "@q3[ib]", "@d6[id]", "v(hv_drv)", "v(gm1_k)", "v(gm2_k)", "v(gm1_out)", "v(gm2_out)"]
MEAS = ["meas tran il_max MAX l2#branch", "meas tran vsw_max MAX v(hv_sw)", "meas tran vout_max MAX v(hv_out)",
        "meas tran vv1_max MAX v(hv_v1)", "meas tran ib_max MAX @q3[ib]", "meas tran ib_min MIN @q3[ib]"]


def meas(stdout):
    return {k: float(v) for k, v in re.findall(r"^(\w+)\s+=\s+([-+0-9.eE]+)", stdout, re.M)}


def steady(pwm_hz, ton, target=400.0, t=40e-3, settle=10e-3, **kw):
    """Steady-state numbers: efficiency, ripple, peaks, the pulse rate the comparator lets through."""
    cols, so = spice.run(f"steady {pwm_hz} Hz {ton * 1e6:.0f} us", bench(pwm_hz, ton, target, ic=True, **kw),
                         f"20n {t} 0 50n", VECS, "\n".join(MEAS))
    m = meas(so)
    tt = cols["time"]
    w = tt >= settle
    vin = VDD
    pin = vin * spice.avg(tt, -cols["v3v3#branch"], settle)
    pout = spice.avg(tt, cols["v(hv_out)"] * cols["@d6[id]"], settle)
    pq3 = spice.avg(tt, cols["v(hv_sw)"] * cols["@q3[ic]"], settle)
    drv = cols["v(hv_drv)"][w] > VDD / 2
    pulses = int(np.sum(drv[1:] & ~drv[:-1]))
    hv = cols["v(hv_out)"][w]
    # the tubes are idle here: any edge on a counter input would be a false count from the switching
    false = sum(int(np.sum((cols[v][w][1:] < VDD / 2) & (cols[v][w][:-1] >= VDD / 2))) for v in ("v(gm1_out)", "v(gm2_out)"))
    return {"pwm_hz": pwm_hz, "ton_us": ton * 1e6, "hv_mean": hv.mean(), "ripple": hv.max() - hv.min(),
            "k_peak_mv": max(cols["v(gm1_k)"][w].max(), cols["v(gm2_k)"][w].max()) * 1e3, "false_counts": false,
            "pin_mw": pin * 1e3, "iin_ma": pin / vin * 1e3, "pout_mw": pout * 1e3, "eff": pout / pin if pin else 0,
            "pq3_mw": pq3 * 1e3, "pulse_hz": pulses / (tt[-1] - settle), "il_max_ma": m.get("il_max", 0) * 1e3,
            "vsw_max": m.get("vsw_max", 0), "ib_max_ma": m.get("ib_max", 0) * 1e3,
            "ib_min_ma": m.get("ib_min", 0) * 1e3, "pass": pulses / (tt[-1] - settle) / pwm_hz}, cols


def startup(pwm_hz, ton, target=400.0, t=0.45, scale=None):
    lin = ["v(hv_out)", "v(hv_fb)", "v(hv_ref)", "v3v3#branch"]
    cols, so = spice.run("startup", bench(pwm_hz, ton, target, scale=scale), f"20n {t} 0 100n", VECS,
                         "\n".join(MEAS) + "\nlinearize " + " ".join(lin), write=lin)
    m = meas(so)
    tt, hv = cols["time"], cols["v(hv_out)"]
    final = hv[tt > t - 0.05].mean()
    t95 = tt[np.argmax(hv >= 0.95 * target)] if (hv >= 0.95 * target).any() else float("nan")
    return {"final": final, "t95_ms": t95 * 1e3, "overshoot": m["vout_max"] - final, "vout_max": m["vout_max"],
            "il_max_ma": m["il_max"] * 1e3, "vsw_max": m["vsw_max"]}, cols


def plot_startup(cols, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    t = cols["time"] * 1e3
    ax[0].plot(t, cols["v(hv_out)"], label="HV_OUT")
    ax[0].plot(t, cols["v(hv_ref)"] * RATIO, "--", label="target (HV_REF x 301)")
    ax[0].plot(t, cols["v(hv_fb)"] * RATIO, ":", label="what the comparator sees (HV_FB x 301)")
    ax[0].set_ylabel("V")
    ax[0].legend()
    ax[0].grid(alpha=0.3)
    ax[0].set_title(title)
    ax[1].plot(t, -cols["v3v3#branch"] * 1e3, lw=0.6)
    ax[1].set_ylabel("3V3 current, mA")
    ax[1].set_xlabel("ms")
    ax[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def plot_pulses(cols, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = cols["time"]
    drv = cols["v(hv_drv)"] > VDD / 2
    first = t[np.argmax((t > 12e-3) & drv)]
    w = (t > first - 5e-6) & (t < first + 60e-6)
    fig, ax = plt.subplots(3, 1, figsize=(9, 7), sharex=True)
    tu = (t[w] - first) * 1e6
    ax[0].plot(tu, cols["v(hv_drv)"][w], label="HV_DRV (gate output)")
    ax[0].set_ylabel("V")
    ax[0].legend()
    ax[1].plot(tu, cols["l2#branch"][w] * 1e3, label="L2 current")
    ax[1].plot(tu, cols["@q3[ic]"][w] * 1e3, "--", label="Q3 collector")
    ax[1].set_ylabel("mA")
    ax[1].legend()
    ax[2].plot(tu, cols["v(hv_sw)"][w], label="HV_SW (Q3 collector)")
    ax[2].plot(tu, cols["v(hv_v1)"][w], "--", label="HV_V1")
    ax[2].set_ylabel("V")
    ax[2].set_xlabel("us from the gate's rising edge")
    ax[2].legend()
    for a in ax:
        a.grid(alpha=0.3)
    ax[0].set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


# Base-drive variants are value-only changes (same 0603 footprints): R25 base resistor, C20 speed-up capacitor.
DRIVES = {"R25 330R, C20 1nF (as designed)": {}, "R25 150R, C20 1nF": {"R25": 150 / 330},
          "R25 100R, C20 1nF": {"R25": 100 / 330}, "R25 330R, C20 4.7nF": {"C20": 4.7},
          "R25 150R, C20 4.7nF": {"R25": 150 / 330, "C20": 4.7}, "R25 100R, C20 4.7nF": {"R25": 100 / 330, "C20": 4.7}}
TIMINGS = [(10e3, 10e-6), (5e3, 20e-6), (2e3, 40e-6), (2e3, 60e-6), (1e3, 100e-6)]


def sweep(only=None):
    """One drive (by its index in DRIVES) or all of them; each drive writes results/sweep_<index>.json."""
    import json
    rows = []
    for i, (name, scale) in enumerate(DRIVES.items()):
        if only is not None and i != only:
            continue
        mine = []
        for hz, ton in (TIMINGS if not scale else TIMINGS[1:4]):
            r, _ = steady(hz, ton, scale=scale)
            r["drive"] = name
            rows.append(r)
            mine.append(r)
            print(f"  {name:<32} {hz / 1e3:>4.0f} kHz {ton * 1e6:>4.0f} us: {r['hv_mean']:6.1f} V, ripple {r['ripple']:4.2f} V, "
                  f"3V3 {r['iin_ma']:5.2f} mA, eff {r['eff'] * 100:4.1f} %, pulses used {r['pass'] * 100:3.0f} %, "
                  f"L2 {r['il_max_ma']:5.1f} mA, VCE {r['vsw_max']:5.1f} V, base {r['ib_min_ma']:6.1f}..{r['ib_max_ma']:5.1f} mA",
                  flush=True)
            json.dump(mine, open(os.path.join(OUT, f"sweep_{i}.json"), "w"), indent=1, default=float)
    return rows


FIRMWARE = (2e3, 40e-6)          # HV_PWM the firmware will use: the sweep's best for the board as built


def faults(scale=None):
    """What the hardware does when something else has gone wrong. Each must stay inside the parts' ratings."""
    hz, ton = FIRMWARE
    rows = []
    cases = [("firmware asks for the maximum (HV_REF at 100 %)", dict(target=436.0), 60e-3),
             ("comparator dead, output stuck high (only the clamp limits HV)", dict(comp=VDD), 0.5),
             ("firmware leaves HV_PWM high (GPIO stuck)", dict(pwm_dc=VDD), 20e-3)]
    for name, kw, t in cases:
        target = kw.pop("target", 400.0)
        cols, so = spice.run(name, bench(hz, ton, target, ic=True, scale=scale, **kw), f"20n {t} 0 100n", VECS,
                             "\n".join(MEAS) + "\nmeas tran v_end FIND v(hv_out) AT=" + str(t * 0.999))
        m = meas(so)
        tt = cols["time"]
        late = tt > t * 0.5
        i3 = -cols["v3v3#branch"]
        p_r21 = spice.avg(tt, i3 ** 2 * 10, t * 0.5)
        p_q3 = spice.avg(tt, cols["v(hv_sw)"] * cols["@q3[ic]"], t * 0.5)
        row = {"case": name, "hv_max": m["vout_max"], "hv_end": m.get("v_end", 0), "vce_max": m["vsw_max"],
               "il_max_ma": m["il_max"] * 1e3, "i3v3_ma": i3[late].mean() * 1e3, "p_r21_mw": p_r21 * 1e3,
               "p_q3_mw": p_q3 * 1e3}
        rows.append(row)
        print(f"  {name}: HV max {row['hv_max']:.0f} V (end {row['hv_end']:.0f} V), Q3 VCE max {row['vce_max']:.0f} V, "
              f"L2 {row['il_max_ma']:.0f} mA, 3V3 draw {row['i3v3_ma']:.1f} mA, R21 {row['p_r21_mw']:.0f} mW, "
              f"Q3 {row['p_q3_mw']:.0f} mW", flush=True)
    return rows


def main():
    """sweep [i]: one base drive (index into DRIVES) or all. startup / faults take the drive index too
    (default 0, as designed), so a value change can be checked end to end before it goes on the board."""
    import json
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    idx = int(sys.argv[2]) if len(sys.argv) > 2 else None
    os.makedirs(OUT, exist_ok=True)
    report = {}
    if what in ("sweep", "all"):
        report["sweep"] = sweep(idx)
    d = idx or 0
    name, scale = list(DRIVES.items())[d]
    if what in ("startup", "all"):
        hz, ton = FIRMWARE
        r, cols = startup(hz, ton, scale=scale)
        plot_startup(cols, os.path.join(OUT, f"hv_startup_{d}.png"),
                     f"HV start-up, {name}, {hz / 1e3:.0f} kHz / {ton * 1e6:.0f} us pulses, target 400 V")
        print(f"  start-up ({name}): 95 % in {r['t95_ms']:.0f} ms, settles at {r['final']:.1f} V, overshoot "
              f"{r['overshoot']:.1f} V, L2 peak {r['il_max_ma']:.0f} mA, Q3 VCE peak {r['vsw_max']:.0f} V", flush=True)
        s, cols = steady(hz, ton, scale=scale)
        plot_pulses(cols, os.path.join(OUT, f"hv_pulse_{d}.png"), f"One boost pulse, {name}, {ton * 1e6:.0f} us at {hz / 1e3:.0f} kHz")
        print(f"  steady: {s['hv_mean']:.1f} V, ripple {s['ripple']:.2f} V, 3V3 {s['iin_ma']:.2f} mA, "
              f"eff {s['eff'] * 100:.1f} %, false counts {s['false_counts']}, tube cathodes peak {s['k_peak_mv']:.0f} mV",
              flush=True)
        json.dump({"drive": name, "startup": r, "steady": s}, open(os.path.join(OUT, f"hv_startup_{d}.json"), "w"),
                  indent=1, default=float)
    if what == "compare":     # the headline numbers: a long window so the pulse count is high enough to trust
        hz, ton = TIMINGS[int(sys.argv[3])]
        r, _ = steady(hz, ton, t=0.17, scale=scale)
        r["drive"] = name
        json.dump(r, open(os.path.join(OUT, f"compare_{d}_{sys.argv[3]}.json"), "w"), indent=1, default=float)
        print(f"  compare {name} {hz / 1e3:.0f} kHz {ton * 1e6:.0f} us: 3V3 {r['iin_ma']:.2f} mA, eff {r['eff'] * 100:.1f} %, "
              f"ripple {r['ripple']:.2f} V, pulses used {r['pass'] * 100:.0f} %, false counts {r['false_counts']}", flush=True)
    if what in ("faults", "all"):
        rows = faults(scale)
        json.dump({"drive": name, "faults": rows}, open(os.path.join(OUT, f"hv_faults_{d}.json"), "w"), indent=1,
                  default=float)
    return report


if __name__ == "__main__":
    main()
