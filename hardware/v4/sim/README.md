# DecayDeck v4 — circuit simulation

The analog half of the board, simulated in [ngspice](https://ngspice.sourceforge.io) before anything is built.
The netlist is not redrawn by hand: `netgen.py` builds it straight from [`../design.py`](../design.py), with every
part's design value and every net as the PCB has it. If the board changes, the simulation changes with it.

What runs here and what doesn't:

| Simulated | How |
|---|---|
| HV boost + doubler + comparator regulation (Q3, L2, D4-D6, C24-C27, U9, U10, the dividers, the clamp) | Transistor-level, real part models |
| Tube pulse chain (anode resistors, cathode loads, BC847C, 74LVC2G17) | Transistor-level, behavioural GM tube |
| Firmware drive (HV_PWM pulses, HV_REF set point) | Sources standing in for the ESP32's pins |
| Not here: ESP32 firmware, display, I²C sensors | That's the firmware simulator (Wokwi), see the firmware README |
| Not here: soldering, parts placed wrong, a dead tube | Only the bring-up checklist in [`../../../docs/assembly.md`](../../../docs/assembly.md) finds those |

## Running it

```
python fit_models.py           # transistor models vs their datasheet tables (all rows must pass)
python hv.py sweep [i]         # HV supply: base drive i (index into hv.DRIVES, all if omitted) x pulse timing
python hv.py startup [i]       # start-up from 0 V, and one pulse in detail (plots in results/)
python hv.py faults [i]        # maximum set point, comparator dead, HV_PWM stuck high
python hv.py compare i t       # one drive x one timing over a long window: the numbers to quote
python gm.py > results/gm.log  # tube pulses across a wide range of tube behaviour
python report.py results/gm.log   # writes results.md from all of the above
```

Each run takes a few minutes; they're independent, so run them side by side.

ngspice 47 for Windows is a 14 MB download that unpacks anywhere. `spice.py` finds it via `$NGSPICE`, then
`PATH`, then `%LOCALAPPDATA%/Programs/ngspice-47`. The Vishay US1M model is fetched from vishay.com on first run
and kept in `vendor/` (not committed).

## Models

| Part | Model | Checked against |
|---|---|---|
| FMMT458 (Q3) | Gummel-Poon fitted to the Diodes datasheet (their model file can't be fetched by script) | `fit_models.py`: VCE(sat), VBE(sat), hFE at 1/50/100 mA, ton, toff |
| BC847C (Q4, Q5) | Gummel-Poon fitted to the datasheet | `fit_models.py`: hFE, VCE(sat) |
| US1M (D4-D6) | Vishay's own SPICE model | vendor file |
| SMAJ440A (D7) | Breakdown 515 V with 320 Ω slope (VC 713 V at 0.6 A), 4 GΩ leakage | datasheet numbers |
| TLV7011 (U9) | Behavioural: 260 ns, 4.2 mV hysteresis, 100 Ω push-pull | datasheet numbers |
| SN74LVC1G08 (U10), 74LVC2G17 (U11) | Behavioural: thresholds, ~25 Ω outputs | datasheet numbers |
| L2 PNLS6045-102M | 1 mH + 6 Ω DCR + 10 pF | LCSC data (Isat 400 mA) |
| GM tubes | Discharge toward an extinction voltage while triggered, then open | swept, see `gm.py` |

## Results

See [`results.md`](results.md) (written from the last run).
