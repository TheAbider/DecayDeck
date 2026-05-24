# DecayDeck — Assembly Guide

## PCB Specifications

- **Board size:** 65 mm × 108 mm
- **Layers:** 2 (FR4)
- **Fabrication:** JLCPCB
- **MCU:** ESP32-S3-WROOM-1-N4 (surface-mount module, castellated pads)
- **Total components:** 83

## Component Zones

### Below-Display Strip (visible, tall components)

Accessible from the front of the finished unit.

- **J1** (USB-C) — bottom edge, center
- **J2** (JST-PH battery) — left edge, rotated
- **SW1** (power slide switch) — right edge
- **BZ1** (piezo buzzer, 9 mm through-hole) — upper-left area
- **SW2, SW3** (6×6 tactile buttons) — center, front-facing
- **LED1, LED2** (0805 SMD charging indicators) — near TP4056
- **R14** (SMD trimmer, HV sense calibration) — upper-right, accessible from top

### Under-Display (SMD, low-profile ≤4 mm)

All SMD components under the Adafruit 2090 with ~6–8 mm standoff clearance.

- **MCU (center):** U1 ESP32-S3-WROOM-1-N4 (18×25.5×3.1 mm), C9 100 nF + C10 10 µF bypass
- **USB-C + ESD (near J1):** U2 USBLC6-2SC6, R1/R2 CC pulldowns, C1 bypass
- **Charging (lower-left):** U3 TP4056, R3 PROG, R4/R5 LED limit
- **LDO (near TP4056):** U4 AP2112K-3.3, C3/C4 decoupling
- **Battery monitor:** U5 MAX17048, C11 bypass, R8/R9 I²C pullups
- **Environmental:** U6 BME280 near U5, C20 bypass
- **Output drivers (left-center):** Q4 (buzzer), Q6 (vibrate), R28/R29 base resistors, LED3 WS2812B, R27 data series, C22 LED bypass, D5 motor flyback
- **GM interface (right-center):** Q3, Q5 sense transistors, R17–R24 + C18/C19 pulse amplification network
- **HV section (upper-left, isolated):** U7 TLC555, **C21 (100 nF VCC bypass at U7)**, L1 1 mH, Q1 MMBTA44, Q2 S8050, D3/D4 1N4007, C12/C13/C16 10 nF 1 kV MLCC, R15A/B/C 10 MΩ chain, R11/R12/R14/R16/R25/R26, R17A+R17B (4.7 MΩ each, series), R22A+R22B (510 kΩ each, series)

**HV isolation:** ~1.7 mm minimum ground-pour gap between HV nets and signal/GND traces. Meets IPC-2221 Class B (internal / conformal-coated) at 500 V with 2× margin. For B1 (uncoated external) compliance in humid environments, apply conformal coating to the HV zone after assembly — see HV Section Warning below.

## Assembly Order

### 1. SMD components (reflow or hand solder)

Work from smallest to largest:

1. All 0805 resistors (R1–R12, R14–R16, R15A/B/C, R17A/B, R18–R21, R22A/B, R23–R31)
2. All 0805 capacitors (C1, C2, C3, C4, C5, C9, C10, C11, C12, C13, C14, C15, C16, C18, C19, C20, C21, C22)
3. Tiny SMD parts:
   - SOT-23 NPN (Q1 MMBTA44, Q2–Q6 S8050)
   - SOT-23-6L (U2 USBLC6-2SC6)
   - SOT-25-5 (U4 AP2112K-3.3)
   - DFN-8 (U5 MAX17048) — 2×2 mm, tight
   - LGA-8 (U6 BME280) — 2.5×2.5 mm, the trickiest part on the board
4. Medium SMD:
   - SOIC-8 (U7 TLC555CDR)
   - ESOP-8 (U3 TP4056) — has thermal pad, ensure good paste coverage
   - DO-214AC/SMA (D3, D4 1N4007)
   - SOD-323 (D5 1N4148WS)
   - IND-SMD 6×6 (L1 1 mH shielded)
5. 0805 LEDs (LED1, LED2)
6. WS2812B RGB LED (LED3)
7. Trimmer (R14, TC33X-2-504E)

### 2. ESP32-S3 module (U1)

Solder U1 — 1.27 mm pitch castellated pads. Use ample flux, drag-solder both long edges, then touch up individual pads. Verify every pad with a continuity check against known nets (GND to pin 1, 3V3 to pin 2, etc.). **Most common failure:** cold joints on the GND thermal pad — reflow if the module feels loose.

### 3. Through-hole / tall components

1. Pin headers J3, J4 (2.54 mm 1×20 male)
2. USB-C connector J1 (mid-mount 2MD-073 variant)
3. JST-PH 2.0 mm battery connector J2
4. GM tube headers J5, J6 (1×2 pin)
5. Motor header J7 (1×2 pin)
6. Slide switch SW1 (MSK12C02)
7. Tactile buttons SW2, SW3 (6×6 mm TH)
8. Piezo buzzer BZ1 (9 mm TH, through-hole)

### 4. Mechanical / display

1. Install M2.5 standoffs through the four plated 2.69 mm mounting holes (at X = ±28.575 mm, Y = +48.260 mm and Y = −27.940 mm), 6–8 mm height.
2. **Configure the Adafruit 2090 for SPI mode before plugging in.** The shield ships in 8-bit parallel mode; the firmware drives SPI. On the back of the Adafruit 2090, find the three solder jumpers labeled **IM1**, **IM2**, **IM3** and bridge each with a solder blob. (The silkscreen note on the shield reads *"Close IM1/IM2/IM3 for SPI."*) Without this step the display will not respond.
3. Plug the Adafruit 2090 into J3 + J4. The display board centerline sits at Y = +10.16 mm relative to the DecayDeck board centerline — verify pin 1 of the shield (silk: GND) lines up with pin 1 of J3/J4 (also GND) before pressing down.
4. Secure display with M2.5 nuts.

## HV Section Warning

The HV boost generates approximately **400 V DC**. Current is microamps (the tube draws ~1 µA average), but:

- **Do not touch HV components while powered on.** HV_OUT, the divider chain (R15A/B/C, R14), D3/D4, C13, C16, and the Q1 collector node are all at 200–400 V.
- **C12, C13, and C16** can retain residual charge after power-off. Let the board sit 60 seconds before probing.
- **Keep the HV zone isolated** — the PCB has a 2.5 mm ground pour gap; do not bridge it with probes, wires, or debug clips.
- **Wire the GM tubes with HV-rated wire.** Short leads, no exposed conductor.
- **The HV moat is uncoated copper.** For deployments in humid environments, apply a conformal coating (acrylic spray, MG Chemicals 419D or similar) across the HV zone before sealing the enclosure. For indoor use in dry air the bare 2.5 mm gap is sufficient per IPC-2221 B1.

## HV Calibration

After assembly and before installing tubes:

1. Power the board from USB only (no battery) to minimize sagging.
2. Enable HV via firmware or hold HV_EN high.
3. Measure HV_OUT at J5 pin 1 **relative to GND** using a ≥1 kV rated DMM on DC volts. Use 10 MΩ or higher input impedance — a normal DMM will load the divider and read low.
4. Adjust **R14** (SMD trimmer) until the firmware HV_SENSE reading reports your target voltage.
5. Target: **400 V ± 10 V** for STS-5. The SI-3BG is fine at this voltage as well (its operating range is 290–330 V plateau, 380–460 V beginning-of-count, so 400 V sits comfortably within spec for both tubes).

## GM Tube Installation

### J5 — STS-5 (gamma)

- **Pin 1 (+)** → tube anode (top cap)
- **Pin 2 (−)** → tube cathode (metal body)
- Use high-voltage-rated wire, keep leads short (<15 cm) to minimize pickup
- The STS-5 is a long glass tube (110 mm × 12 mm) — mount in a shock-absorbing cradle

### J6 — SI-3BG (high-dose beta/gamma)

- **Pin 1 (+)** → tube anode
- **Pin 2 (−)** → tube cathode
- The SI-3BG is a small pen-shaped tube; mount near the board or with short leads

Both tubes are halogen-quenched and can tolerate direct soldering to their leads, but **never** solder to a powered tube. Use silicone or closed-cell foam to cushion against vibration in the final enclosure.

## Battery

- **Planned cell:** 105070 LiPo, ~3500 mAh, JST-PH 2.0 mm 2-pin
- **Previous cell:** 103450, ~1800 mAh — same connector, same polarity, smaller
- **Polarity:** J2 pin 1 = VBAT+ (red), pin 2 = GND (black).
- **Verify polarity before plugging in** — MAX17048 has no reverse protection and will be destroyed by a backwards cell. Order packs from EEMB or Adafruit for known-good polarity, or measure with a DMM before connecting.
- **Charge rate:** R3 = 2.4 kΩ sets 500 mA charge current. ~7 h full charge for the 3500 mAh pack, ~0.65 W dissipation in U3 — comfortable thermally without dedicated thermal vias.

## Programming

The ESP32-S3 uses **native USB** via GPIO19/GPIO20, routed through USBLC6-2SC6 ESD protection to J1. No external USB-UART chip is needed.

1. Connect USB-C cable to J1
2. ESP32-S3 enumerates as a USB-Serial-JTAG composite device
3. PlatformIO (or esptool.py) auto-detects the port
4. Flash: `pio run -t upload`
5. Monitor: `pio device monitor`

**First-time flashing:** ESP32-S3 native USB-JTAG handles flashing automatically in normal operation. If the module ever fails to enumerate (e.g., after a firmware crash that breaks the USB stack), you can manually enter ROM bootloader mode by holding GPIO0 low while plugging in USB. There is no dedicated BOOT button on this board — short the R7-to-GPIO0 trace to a nearby GND pad with a fine probe to pull GPIO0 low.

After the first successful flash, subsequent uploads work automatically via USB-JTAG without manual intervention.

## First Power-On Checklist

1. [ ] **Close IM1/IM2/IM3 jumpers on the Adafruit 2090** (do this before stacking the shield).
2. [ ] Visual inspection — look for solder bridges, especially on U1 (1.27 mm pitch pads) and U5/U6 (DFN/LGA).
3. [ ] Continuity check: 3V3 and GND must not be shorted.
4. [ ] Continuity check: VIN_SW and GND must not be shorted.
5. [ ] Continuity check: HV_OUT and GND (should read ≥30 MΩ through the divider, not a short).
6. [ ] **Plug in USB-C only, no battery.** Measure 5 V on USB_5V and 3.3 V on 3V3 (probe at C9 / C20 / any 3V3 cap).
7. [ ] Flash firmware over USB (see Programming section).
8. [ ] Disconnect USB, plug in battery. Verify SW1 toggles VIN_SW on/off (measure at J4 pin 2).
9. [ ] Power on — display should show the DecayDeck splash screen. **If the screen stays dark, the most common cause is unclosed IM1/IM2/IM3 jumpers on the Adafruit 2090** — pop the shield off and check.
10. [ ] Measure HV output with a high-impedance DMM (~400 V on J5/J6 pin 1). Use a 10 MΩ-input DMM or a 1000:1 HV probe; a normal DMM will load the divider chain and read low.
11. [ ] Calibrate HV via R14 trimmer if needed.
12. [ ] Connect one GM tube — verify CPM counts appear on display.
13. [ ] Connect both tubes — verify separate CPM for each.
14. [ ] Test WiFi AP mode (SSID `DecayDeck`, password `geiger20`).
15. [ ] Test buttons, buzzer, vibration, RGB LED. The WS2812 is powered from 3V3 — color should be stable across the full LiPo discharge curve.
16. [ ] Run overnight to verify no brown-outs or thermal issues.
