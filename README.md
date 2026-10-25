# DecayDeck

Open-source handheld Geiger counter with two GM tubes (STS-5 and SI-3BG), a 2.8" capacitive touchscreen, WiFi,
and a LiPo with a proper power path. The current hardware is **v4**, in [`hardware/v4`](hardware/v4).

## Status

| Part | State |
|---|---|
| v4 hardware | Done and checked:<br>• DRC clean; every net connected, checked against the real poured copper.<br>• Pinouts checked against datasheets; display fit proven.<br>• Fab files for JLCPCB in [`hardware/v4/fab/2026-10-25`](hardware/v4/fab/2026-10-25), with the [order settings](hardware/v4/README.md#ordering-jlcpcb-one-order). |
| Schematic | Being redrawn for people on an A1 sheet ([`sch_pretty.py`](hardware/v4/sch_pretty.py)). |
| Firmware | The code in [`firmware/`](firmware) is for v3 and does not match v4's pins or power design. A v4 rewrite is next. |
| Case | 3D-printed, designed around the board and the tubes. Next after firmware. |

## v4 hardware

- **MCU:** ESP32-S3-WROOM-1-N16R2: 16 MB flash, 2 MB PSRAM, WiFi + BLE, native USB.
- **Display:** Adafruit 2090, a 2.8" 320×240 ILI9341 with FT6206 capacitive touch and microSD. It plugs into two
  headers with no jumpers; its IM pins are tied for SPI mode on the board.
- **Tubes:**
  - STS-5 (beta/gamma) with a 9.4 MΩ anode resistor, and SI-3BG (high-dose gamma) with 4.4 MΩ.
  - Both are cathode-sensed, and their pulses go to hardware counters (PCNT).
  - The tubes mount in the case's left bay.
- **High voltage:**
  - A boost plus voltage doubler (FMMT458, 1 mH, US1M diodes) gives about 400 V.
  - Regulation is in hardware: a TLV7011 comparator gates the drive, so a firmware hang can't run the HV away.
  - The set point is a PWM reference with a hardware ceiling of 436 V.
  - SMAJ440A clamp; a bleeder empties the HV in about 2 s.
- **Power:**
  - BQ24075 power path: it runs and charges at the same time, at 0.81 A.
  - TPS63802 buck-boost to 3.38 V.
  - Soft-power latch: the POWER button or USB turns it on, and firmware holds it on.
  - Reverse-battery P-FET, and a MAX17048 fuel gauge.
- **USB-C:** 5 V sink with CC sensing, so firmware can see how much current the charger offers. ESD protection.
- **Sensors:** BME280 (temperature, humidity, pressure), RV-3032-C7 temperature-compensated RTC kept alive by the
  LiPo, LIS2DH12 accelerometer, OPT3001 ambient light.
- **Feedback:** magnetic buzzer, vibration motor, WS2812B RGB LED, red charge LED, three side buttons (POWER, A/BOOT, B).
- **PCB:** 66 × 111 mm, 4 layers (inner GND and 3V3 planes), all parts on one side. JLCPCB assembles it.

The design is code. [`hardware/v4/design.py`](hardware/v4/design.py) is the netlist, and the scripts next to it
build the EasyEDA Pro project from it and check it: placement, display fit, DRC, connectivity, pour clearance,
fab export. [`hardware/v4/README.md`](hardware/v4/README.md) has the design details, the pipeline, the review
results and what's left.

## Firmware goals (v4)

- Dose rate from both tubes (CPM, µSv/h) with dead-time correction, plus a total dose.
- A touch UI (LVGL): live rate, history graph, alarms, settings.
- HV set point and monitoring, with the hardware regulator as the safety net.
- Click / LED / vibration on counts and alarms.
- Data logging to microSD, with time from the RTC.
- A WiFi dashboard and JSON API.
- Battery state from the fuel gauge, and a charge-aware power-off mode.

## Project layout

```
hardware/v4/            v4 board, designed as code (EasyEDA Pro)
  design.py             netlist: the source of truth
  README.md             design notes, pipeline, review results, ordering settings
  fab/2026-10-25/       Gerber zip, BOM and pick-and-place for JLCPCB
  *.py                  build / check / export scripts (pipeline in the v4 README)
docs/
  pinout.md             v4 GPIO map, display headers, I²C addresses, off-board pads
  assembly.md           ordering, what to build by hand, first power-on, HV safety
hardware/schematic-guide.md   v4 schematic, block by block
firmware/               v3 firmware (PlatformIO); being rewritten for v4
```

## Safety

The tube supply runs at about 400 V DC. The current is microamps, but it can still give a sharp shock and damage
things.

- Don't touch the HV area (the upper-left part of the board, under the display) or the tube pads while it's on.
- The HV capacitors bleed down in about 2 s after power-off.
- The tubes' anode pads carry the full HV through their anode resistors.

[`docs/assembly.md`](docs/assembly.md) covers handling and the first power-on.

## License

[MIT](LICENSE)
