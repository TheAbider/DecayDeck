"""Write results.md from the last runs' JSON (results/sweep.json, hv_startup.json, hv_faults.json) and gm.py's log.

usage: python report.py [gm.log]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "results")


def load(name):
    try:
        return json.load(open(os.path.join(R, name)))
    except OSError:
        return None


def main():
    out = ["# Simulation results", "",
           "Written by `report.py` from the last run of each bench. Currents are what the HV supply takes from the 3V3 "
           "rail, base drive included; the battery sees about the same divided by the buck-boost's ~90 % efficiency.",
           ""]
    rows = [load(f"compare_{d}_{t}.json") for d in range(6) for t in range(5)]
    rows = [r for r in rows if r]
    if rows:
        out += ["## Headline: as designed vs R25 at 150 Ω", "",
                "Steady state at 400 V over a 160 ms window (enough pulses to trust the averages). Tubes connected, idle.", "",
                "| Base drive | HV_PWM | 3V3 current | Efficiency | Ripple | Pulses used | False counts |",
                "|---|---|---|---|---|---|---|"]
        for r in rows:
            out.append(f"| {r['drive']} | {r['pwm_hz'] / 1e3:.0f} kHz, {r['ton_us']:.0f} µs | {r['iin_ma']:.2f} mA | "
                       f"{r['eff'] * 100:.0f} % | {r['ripple']:.1f} V | {r['pass'] * 100:.0f} % | {r['false_counts']} |")
        out += ["", "The sweep below uses a 30 ms window: at 2 kHz only a handful of pulses land in it, so differences "
                "under ~10 % between rows there are noise.", ""]
    sweep = []
    for i in range(20):
        sweep += load(f"sweep_{i}.json") or []
    if sweep:
        out += ["## HV supply at 400 V: base drive and pulse timing", "",
                "Each row is a steady-state run at 400 V with both tubes connected and idle. *Pulses used* is the share of "
                "HV_PWM pulses the comparator lets through: the rest is headroom for high count rates.", "",
                "| Base drive | HV_PWM | 3V3 current | Efficiency | Ripple | Pulses used | L2 peak | Q3 VCE peak | False counts |",
                "|---|---|---|---|---|---|---|---|---|"]
        for r in sweep:
            out.append(f"| {r['drive']} | {r['pwm_hz'] / 1e3:.0f} kHz, {r['ton_us']:.0f} µs | {r['iin_ma']:.2f} mA | "
                       f"{r['eff'] * 100:.0f} % | {r['ripple']:.1f} V | {r['pass'] * 100:.0f} % | {r['il_max_ma']:.0f} mA | "
                       f"{r['vsw_max']:.0f} V | {r.get('false_counts', '-')} |")
        out.append("")
    for d in range(20):
        st = load(f"hv_startup_{d}.json")
        if not st:
            continue
        s, t = st["steady"], st["startup"]
        out += [f"## Start-up and one pulse: {st['drive']}", "",
                f"- From 0 V: 95 % of 400 V in {t['t95_ms']:.0f} ms, settling at {t['final']:.1f} V with "
                f"{t['overshoot']:.1f} V overshoot. Every pulse passes until 400 V, so the rise is the boost's own "
                f"limit (the bench sets the target from t = 0; on the board HV_REF's 43 ms filter ramps it too).",
                f"- Steady: {s['hv_mean']:.1f} V, {s['ripple']:.2f} V ripple, {s['iin_ma']:.2f} mA from 3V3, "
                f"{s['eff'] * 100:.0f} % efficient; tube cathode pickup from the switching {s['k_peak_mv']:.0f} mV "
                f"(a count needs ~600 mV); {s['false_counts']} false counts.", "",
                f"![start-up](results/hv_startup_{d}.png)", "", f"![one pulse](results/hv_pulse_{d}.png)", ""]
    for d in range(20):
        ft = load(f"hv_faults_{d}.json")
        if not ft:
            continue
        out += [f"## Faults: {ft['drive']}", "", "| Case | HV max | Q3 VCE max | L2 peak | 3V3 draw | R21 | Q3 |",
                "|---|---|---|---|---|---|---|"]
        for r in ft["faults"]:
            out.append(f"| {r['case']} | {r['hv_max']:.0f} V | {r['vce_max']:.0f} V | {r['il_max_ma']:.0f} mA | "
                       f"{r['i3v3_ma']:.1f} mA | {r['p_r21_mw']:.0f} mW | {r['p_q3_mw']:.0f} mW |")
        out.append("")
    out += ["Ratings: FMMT458 VCEO 400 V, 500 mW, base 200 mA; R21 0.5 W; L2 Isat 400 mA; SMAJ440A clamps from 492 V; "
            "SN74LVC1G08 output 24 mA recommended; STS-5 working 360-440 V, SI-3BG 380-410 V.", ""]
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        out += ["## Tube pulses (`gm.py`)", "", "```", open(sys.argv[1], encoding="utf-8").read().rstrip(), "```", ""]
    open(os.path.join(HERE, "results.md"), "w", encoding="utf-8").write("\n".join(out))
    print("results.md written")


if __name__ == "__main__":
    main()
