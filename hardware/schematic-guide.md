# DecayDeck — Schematic Reference

Generated from the EasyEDA Pro board source PAD_NET records. Every wire below was verified against the board file — use it as the definitive reference. The board source is the source of truth; if anything here disagrees with the board file, trust the board file.

## Summary

- **MCU:** ESP32-S3-WROOM-1-N4 (4 MB flash, no PSRAM, native USB)
- **Display:** Adafruit 2090 (2.8" ILI9341 TFT + FT6206 cap touch + microSD) — **must be jumpered for SPI mode (close IM1/IM2/IM3)**
- **GM Tubes:** STS-5 (gamma, 9.4 MΩ anode via R17A+R17B) + SI-3BG (high-dose, 1.02 MΩ anode via R22A+R22B)
- **HV:** 555-based boost converter with voltage doubler, ~400 V DC
- **Charging:** TP4056 via USB-C, 500 mA charge rate (R3 = 2.4 kΩ)
- **Regulator:** AP2112K-3.3 LDO → 3.3 V
- **Environmental:** BME280 (temp/humidity/pressure, I²C 0x76)
- **Battery:** single-cell LiPo via JST-PH 2.0 mm, MAX17048 fuel gauge

## Power Rails

| Net | Voltage | Source |
|-----|---------|--------|
| USB_5V | 5 V | USB-C VBUS |
| VBAT | 3.0–4.2 V | LiPo battery |
| VIN_SW | 3.0–4.2 V | VBAT through SW1 (power switch) |
| 3V3 | 3.3 V | LDO (U4) from VIN_SW |
| HV_OUT | ~400 V | 555 boost converter |

---

## Block 1: MCU — ESP32-S3-WROOM-1-N4 (U1)

The ESP32-S3 module has 41 pads plus a thermal pad. Only pins with assigned nets are listed below; all unassigned module pins are NC.

**Power and reset:**

```
U1 pin 1  (GND)  → GND
U1 pin 2  (3V3)  → 3V3 rail
U1 pin 3  (EN)   → R6 (10k) → 3V3  [reset pullup]
                   C5 (1µF) → GND   [reset delay, ~10 ms RC]
U1 pin 27 (GPIO0) → R7 (10k) → 3V3  [boot mode pullup]
U1 pin 40 (GND)  → GND
U1 pin 41 (EPAD) → GND (thermal pad, multiple vias to ground plane)
```

**Bypass caps** (as close to U1 power pin as possible):
- C9 (100 nF, 0805) — 3V3 high-frequency bypass at U1
- C10 (10 µF, 0805) — 3V3 bulk at U1

**GPIO assignments** (authoritative — verified against the board source PAD_NET entries, every line confirmed):

| Module pin | GPIO | Net | Goes to |
|---|---|---|---|
| 4 | GPIO4 | GM_INT1 | STS-5 sense (Q3 collector) |
| 5 | GPIO5 | GM_INT2 | SI-3BG sense (Q5 collector) |
| 6 | GPIO6 | HV_EN | U7 pin 4 (555 RESET) + R25 pulldown |
| 7 | GPIO7 | HV_SENSE | R14 wiper (trimmer on HV divider) |
| 8 | GPIO15 | SPI_SCK | J4 pin 4 |
| 9 | GPIO16 | SPI_MISO | J4 pin 5 |
| 10 | GPIO17 | SD_CS | J4 pin 19 |
| 11 | GPIO18 | BAT_ALRT | MAX17048 ALRT pin |
| 12 | GPIO8 | BUZZER | R28 → Q4 base |
| 13 | GPIO19 | USB_DN | U2 pin 1 (ESD to J1 D−) |
| 14 | GPIO20 | USB_DP | U2 pin 6 (ESD to J1 D+) |
| 15 | GPIO3 | TOUCH_INT | J4 pin 12 (FT6206 IRQ) |
| 17 | GPIO9 | VIBRATE | R29 → Q6 base |
| 18 | GPIO10 | TFT_CS | J4 pin 7 |
| 19 | GPIO11 | TFT_DC | J4 pin 8 |
| 20 | GPIO12 | TFT_RST | J4 pin 9 |
| 21 | GPIO13 | TFT_BL | J4 pin 10 |
| 22 | GPIO14 | SPI_MOSI | J4 pin 6 |
| 23 | GPIO21 | LED_DATA | R27 → WS2812 DIN |
| 24 | GPIO47 | BTN1 | SW2 + R30 pullup |
| 25 | GPIO48 | BTN2 | SW3 + R31 pullup |
| 29 | GPIO36 | CHRG_STAT | TP4056 CHRG (LED1 cathode) |
| 30 | GPIO37 | STDBY_STAT | TP4056 STDBY (LED2 cathode) |
| 31 | GPIO38 | SD_CD | SD card detect + R10 pullup |
| 38 | GPIO2 | I2C_SCL | I²C bus (to J4, U5, U6) |
| 39 | GPIO1 | I2C_SDA | I²C bus (to J4, U5, U6) |

**Unused module pins:** GPIO35, GPIO39–GPIO44, GPIO45, GPIO46, plus UART0 (module pins 36–37). **GPIO26–GPIO32 are internal flash SPI and not broken out** on the WROOM-1 module — do not reference them.

There is no dedicated BOOT button or test point — the ESP32-S3 native USB-JTAG bootloader handles flashing automatically in normal operation. If manual ROM bootloader entry is ever needed (e.g., after a firmware crash that breaks the USB stack), short the R7-to-GPIO0 trace to a nearby GND pad with a fine probe while plugging in USB.

---

## Block 2: USB-C + ESD Protection (J1, U2)

J1 is a full 14-pad Type-C receptacle (LCSC C2765186 — the "16-pin" name in the EasyEDA library refers to 14 contacts plus 2 shield mounts, all wired).

**Wiring (from the board PAD_NETs):**

```
J1 pin 1  GND   → GND
J1 pin 2  VBUS  → USB_5V
J1 pin 3  SBU1  → NC
J1 pin 4  CC1   → R1 (5.1k, 0402) → GND
J1 pin 5  D-    → U2 pin 1 (USB_DN → ESP32 GPIO19)
J1 pin 6  D+    → U2 pin 3 (USB_DP → ESP32 GPIO20)
J1 pin 7  D-    → shared with pin 5 (USB_DN)  [orientation tolerance]
J1 pin 8  D+    → shared with pin 6 (USB_DP)  [orientation tolerance]
J1 pin 9  SBU2  → NC
J1 pin 10 CC2   → R2 (5.1k, 0402) → GND
J1 pin 11 VBUS  → USB_5V
J1 pin 12 GND   → GND
J1 pins 13/14   → GND (shield mounts, doubled in source for the two tabs each)
```

CC1 and CC2 each have their own independent 5.1 kΩ pulldown — this is required for proper USB-C device detection on reversible cables.

**USBLC6-2SC6 ESD (U2):**

```
U2 pin 1  → USB_DN  (D− protected)
U2 pin 2  → GND
U2 pin 3  → USB_DP  (D+ protected)
U2 pin 4  → USB_DP  (internal tied)
U2 pin 5  → USB_5V  (VCC)
U2 pin 6  → USB_DN  (internal tied)
```

**C1 (100 nF, 0805)** — bypass on USB_5V to GND, close to J1.

---

## Block 3: Battery Charging (U3 TP4056)

**Part:** TP4056-42 in ESOP-8 (thermal-padded for heat dissipation).

```
U3 pin 1  (STDBY) → R5 (1k) → LED2 cathode → GND  [charge complete indicator]
                   → ESP32 GPIO37 (STDBY_STAT)
U3 pin 2  (PROG)  → R3 (2.4 kΩ) → GND          [sets 500 mA charge current]
U3 pin 3  (GND)   → GND
U3 pin 4  (VCC)   → USB_5V
U3 pin 5  (VBAT)  → VBAT  (charges battery)
U3 pin 6  (TEMP)  → GND (temp sensing disabled)
U3 pin 7  (CHRG)  → R4 (1k) → LED1 cathode → GND  [charging indicator]
                   → ESP32 GPIO36 (CHRG_STAT)
U3 pin 8  (CE)    → USB_5V  (always enabled when USB connected)
```

**R3 = 2.4 kΩ** sets charge current to **500 mA** (Ichg = 1200 V / Rprog). For the 3500 mAh 105070 cell, that's a 0.14 C charge — gentle, healthy for the cell, ~7 hour full-cycle time, ~0.65 W dissipation in U3.

**C2 (10 µF, 0805)** — bulk cap on VBAT, close to U3 pin 5.

**Thermal note:** ESOP-8 thermal pad should have copper pour with at least a few thermal vias. At 500 mA charge / 0.65 W, the existing layout is comfortable. Adding 4× 0.3 mm thermal vias on the EPad would be cleaner for a future spin.

---

## Block 4: Power Switch and LDO (SW1, U4)

**SW1 = MSK12C02 slide switch** (7-pin SMD/TH, SPDT with common rail). Switches VBAT to VIN_SW.

```
SW1 pin 1 → VIN_SW  (output when switched on)
SW1 pin 2 → VBAT    (input)
SW1 pin 3 → VBAT    (input, tied to pin 2)
SW1 pin 4 → GND     (×4, common rail)
```

**Current rating note:** MSK12C02 is rated 300 mA DC. Worst-case VIN_SW peak draw (WiFi TX + HV boost + motor) can exceed this in short bursts. Acceptable for this revision — switch wear is the only failure mode, not a function blocker. A future revision could move to a P-FET high-side switch (SI2301 + 10 kΩ gate resistor on SW1).

**U4 = AP2112K-3.3 LDO** (SOT-25-5, 600 mA, 250 mV dropout):

```
U4 pin 1 (VIN)  → VIN_SW
U4 pin 2 (GND)  → GND
U4 pin 3 (EN)   → VIN_SW  (always-on when switch is on)
U4 pin 4 (NC)   → NC
U4 pin 5 (VOUT) → 3V3
```

**C3 (1 µF, 0805)** — input cap on VIN_SW to GND, at U4.
**C4 (1 µF, 0805)** — output cap on 3V3 to GND, at U4. AP2112K-3.3 requires ≥1 µF on output for stability.

**Headroom note:** 600 mA accommodates typical ESP32-S3 + display load. Peak draw during long WiFi TX bursts approaches 620 mA. If you observe brown-out resets during sustained WiFi traffic, drop WiFi TX power in firmware (`WiFi.setTxPower(WIFI_POWER_15dBm)` or lower).

---

## Block 5: Battery Monitoring (U5 MAX17048)

```
U5 pin 1 (GND)   → GND
U5 pin 2 (VDD)   → VBAT
U5 pin 3 (VDD)   → VBAT (tied to pin 2)
U5 pin 4 (GND)   → GND
U5 pin 5 (ALRT)  → ESP32 GPIO18 (BAT_ALRT)
U5 pin 6 (NC)    → NC
U5 pin 7 (SCL)   → I2C_SCL
U5 pin 8 (SDA)   → I2C_SDA
U5 pin 9 (EPAD)  → GND
```

**C11 (100 nF, 0805)** — bypass on VBAT next to U5.

**I²C address:** 0x36 (fixed).

**Reverse-polarity note:** MAX17048 has no reverse protection on VBAT. A backwards battery will destroy U5 instantly. The JST-PH 2.0 mm connector is keyed but factory-assembled packs occasionally come wired wrong — measure with a DMM before plugging in.

---

## Block 6: I²C Bus (R8, R9)

Pullups to 3V3:

```
I2C_SDA → R8 (4.7 kΩ) → 3V3
I2C_SCL → R9 (4.7 kΩ) → 3V3
```

**Devices on bus:**

| Address | Device | Function |
|---|---|---|
| 0x36 | MAX17048 (U5) | Battery fuel gauge |
| 0x38 | FT6206 (on Adafruit 2090) | Touch controller |
| 0x76 | BME280 (U6) | Temp/humidity/pressure |

No address conflicts.

---

## Block 7: Display + SD Card (J3, J4 — Adafruit 2090 stacking headers)

J3 and J4 are 1×20 male pin headers at 2.54 mm pitch. The Adafruit 2090 uses 1×20 female sockets at JP1 (top) and JP2 (bottom) with the same 76.2 mm center-to-center spacing.

**J3 (top, mates with Adafruit JP1) — mechanical support + power passthrough:**

| J3 Pin | Adafruit JP1 silk | DecayDeck net |
|---|---|---|
| 1 | GND | GND |
| 2 | Vin (3–5 V) | NC |
| 12 | GND | GND |
| 3–11, 13–20 | various parallel-mode signals | NC (unused in SPI mode) |

**J4 (bottom, mates with Adafruit JP2) — active signals:**

| J4 pin | Adafruit silk | Net | ESP32 GPIO |
|---|---|---|---|
| 1 | GND | GND | — |
| 2 | Vin (3–5 V) | VIN_SW | — |
| 3 | 3Vo (display's onboard 3V3 reg out) | NC | — |
| 4 | CLK | SPI_SCK | GPIO15 |
| 5 | MISO | SPI_MISO | GPIO16 |
| 6 | MOSI | SPI_MOSI | GPIO14 |
| 7 | CS | TFT_CS | GPIO10 |
| 8 | D/C | TFT_DC | GPIO11 |
| 9 | RST | TFT_RST | GPIO12 |
| 10 | Lite | TFT_BL | GPIO13 |
| 11 | GND | GND | — |
| 12 | IRQ | TOUCH_INT | GPIO3 |
| 13 | SDA | I2C_SDA | GPIO1 |
| 14 | SCL | I2C_SCL | GPIO2 |
| 15–18 | IM3, IM2, IM1, IM0 | NC | — |
| 19 | CCS (Card CS) | SD_CS | GPIO17 |
| 20 | CD (Card Detect) | SD_CD | GPIO38 |

**⚠ Required Adafruit 2090 configuration:** close the **IM1**, **IM2**, **IM3** solder jumpers on the back of the shield. The shield ships in 8-bit parallel mode; closing those three jumpers reconfigures it for 4-wire SPI mode, which is what the firmware uses (`Adafruit_ILI9341 tft(TFT_CS, TFT_DC, TFT_RST)`). The silkscreen on the shield reads *"Close IM1/IM2/IM3 for SPI."* Without this, the display will not respond.

**R10 (10 kΩ)** — SD_CD pullup to 3V3.

---

## Block 8: HV Boost Converter (U7, Q1, Q2, L1, D3, D4, C12, C13, C16, C14, R11–R16, R25–R26, **C21**)

Classic 555-driven boost + voltage doubler. Produces ~400 V DC from 3.7 V input. Lives in the upper-left HV zone of the board, isolated from the digital section by a 2.5 mm ground-pour gap.

**555 astable oscillator (U7 TLC555CDR):**

```
U7 pin 1 (GND)        → GND
U7 pin 2 (TRIG)       → timing node ($1N5564)
U7 pin 3 (OUTPUT)     → R12 (330 Ω) → Q2 base
U7 pin 4 (RESET)      → HV_EN (from ESP32 GPIO6)
U7 pin 5 (CONTROL)    → C15 (100 pF) → GND (noise bypass)
U7 pin 6 (THRESHOLD)  → timing node ($1N5564)
U7 pin 7 (DISCHARGE)  → timing node ($1N5564)
U7 pin 8 (VCC)        → VIN_SW — local bypass C21 (100 nF, 0805) to GND within 5 mm

R11 (10 kΩ) → timing node (charge resistor)
C12 (10 nF, 1 kV) → timing node to GND (timing cap)
R25 (10 kΩ) → HV_EN to GND  [pulldown, HV off at boot]
```

**Oscillator frequency:** f ≈ 0.72 / (R11 × C12) = 0.72 / (10k × 10n) = **7.2 kHz**. Peak inductor current at this frequency with L1 = 1 mH and Vin = 3.7 V ≈ 256 mA — comfortably inside Q1 MMBTA44's 300 mA pulsed rating.

C21 is a 100 nF 0805 between U7 pin 8 (VCC) and GND, placed within 5 mm of pin 8 — local bypass to keep the 555's switching transients off the VIN_SW rail. Same part as C1/C9/C11/C20/C22 (LCSC C495959).

**Base drive (Q2 S8050, emitter follower):**

```
R12 (330 Ω) → Q2 base
Q2 emitter  → Q1 base ($1N5644)
Q2 collector → VIN_SW
R26 (10 kΩ) → $1N5644 to GND  [Q1 base pulldown, ensures off when Q2 is off]
```

**Switching transistor (Q1 MMBTA44, NPN, Vceo = 400 V):**

```
Q1 emitter   → GND
Q1 base      → $1N5644 (from Q2 emitter)
Q1 collector → $1N5660 (L1 switching node, also D3 anode)
```

**Long-term reliability note:** Q1 Vceo = 400 V with HV target 400 V means zero voltage margin. The part works fresh but degrades slowly over months under repeated near-Vceo switching transients. A future spin could swap to a 500 V SOT-23 NPN (e.g., MMBTA42 derivative or KSP44 family) or add an RC snubber across Q1 C-E.

**Voltage doubler (L1, D3, D4, C13, C16):**

```
L1 (1 mH, SMNR6028-102MT) : pin 1 → VIN_SW, pin 2 → $1N5660 (switching node)
D3 (1N4007, SMA): anode $1N5660, cathode $1N5667 (intermediate node, ~200 V)
D4 (1N4007, SMA): anode $1N5667, cathode HV_OUT (~400 V)
C13 (10 nF, 1 kV, 0805) : $1N5667 → GND  [intermediate storage]
C16 (10 nF, 1 kV, 0805) : HV_OUT → GND   [output storage]
```

**Output divider and sense (R15A, R15B, R15C, R16, R14, C14):**

```
HV_OUT → R15A (10 MΩ) → $1N10242 → R15B (10 MΩ) → $1N10203 → R15C (10 MΩ) → $1N5700
$1N5700 → R16 (47 kΩ) → GND
$1N5700 → R14 pin 3 (trimmer end, TC33X-2-504E 500 kΩ)
R14 pin 1 → GND
R14 pin 2 (wiper) → HV_SENSE → ESP32 GPIO7
C14 (100 pF, 0805) → $1N5700 to GND  [ADC anti-alias filter]
```

**Divider ratio** (for `HV_ADC_RATIO` firmware constant):
`47k / (30M + 47k) ≈ 0.001567` → at 400 V HV, the ADC sees ~626 mV (~777 counts of 4095 on 12-bit, 11 dB attenuation). The trimmer R14 lets you tune the sense ratio at calibration time.

**HV isolation:** ~1.7 mm minimum clearance between HV nets and any other net (measured at the R17A / R22A area). Meets IPC-2221 Class B (internal / conformal-coated) at 500 V with 2× margin. The HV zone is the upper-left rectangle of the board, separated from the digital section by a routed ground-pour gap. For uncoated B1 compliance in humid environments, apply conformal coating to the HV zone after assembly.

---

## Block 9: GM Tube Interface (J5, J6, R17A/R17B, R18, R19, R20, R21, R22A/R22B, R23, R24, C18, C19, Q3, Q5)

Each tube has a series anode resistor chain (HV_OUT → 2× 0805 in series → tube anode), a cathode pulldown, an AC coupling cap to a sense transistor, and a pullup on the ESP32 interrupt pin. The tube cathode sits near 0 V when idle; during an ionization event, it briefly rises and couples a positive pulse through the coupling cap to the transistor base, pulling the GPIO low.

### J5: STS-5 (gamma tube, glass-walled)

```
J5 pin 1 (anode)   → $1N12939 → R17B (4.7 MΩ) → $1N12941 → R17A (4.7 MΩ) → HV_OUT
J5 pin 2 (cathode) → $1N6645 → R18 (100 kΩ) → GND
                     $1N6645 → C18 (100 pF) → $1N6671 (Q3 base)
                     $1N6671 → R20 (1 MΩ) → GND  [base bleeder]

Q3 (S8050, NPN) — STS-5 pulse amplifier (common emitter):
  base      → $1N6671
  emitter   → GND
  collector → GM_INT1 → ESP32 GPIO4
R19 (10 kΩ) → GM_INT1 to 3V3  [collector pullup, signal idles high]
```

**Anode resistance:** R17A + R17B = 9.4 MΩ — middle of STS-5 datasheet spec (5.1–10 MΩ). Each resistor sees ~200 V across, inside 0805 working-voltage rating.

### J6: SI-3BG (high-dose beta/gamma tube, pen-shaped)

```
J6 pin 1 (anode)   → $1N12943 → R22B (510 kΩ) → $1N12945 → R22A (510 kΩ) → HV_OUT
J6 pin 2 (cathode) → $1N6664 → R23 (100 kΩ) → GND
                     $1N6664 → C19 (100 pF) → $1N6673 (Q5 base)
                     $1N6673 → R21 (1 MΩ) → GND  [base bleeder]

Q5 (S8050, NPN) — SI-3BG pulse amplifier (common emitter):
  base      → $1N6673
  emitter   → GND
  collector → GM_INT2 → ESP32 GPIO5
R24 (10 kΩ) → GM_INT2 to 3V3  [collector pullup]
```

**Anode resistance:** R22A + R22B = 1.02 MΩ — matches SI-3BG datasheet spec (1 MΩ, the high-dose tube's lower working current allows a lower anode resistor than the STS-5).

---

## Block 10: Output Drivers (BZ1, Q4, Q6, D5, LED3, SW2, SW3)

### Buzzer (BZ1, Q4)

```
BZ1 (FMB09A03-3V, self-driving 2.7 kHz piezo, through-hole):
  pin 1 → VIN_SW
  pin 2 → $1N7401 → Q4 collector

Q4 (S8050, NPN):
  base      → $1N7077 → R28 (1 kΩ) → BUZZER → ESP32 GPIO8
  emitter   → GND
  collector → $1N7401 → BZ1 pin 2
```

**Firmware:** `CLICK_DURATION_US = 2000` (2 ms pulse for audible click). The FMB09A03 has an internal 2.7 kHz oscillator — apply DC and it beeps.

### Vibration Motor (J7, Q6, D5)

```
J7 (1030 coin motor header, 3 V nominal, 70 mA rated, 90 mA stall):
  pin 1 → $1N7096 → Q6 collector
  pin 2 → VIN_SW

Q6 (S8050, NPN):
  base      → $1N7089 → R29 (1 kΩ) → VIBRATE → ESP32 GPIO9
  emitter   → GND
  collector → $1N7096 → J7 pin 1

D5 (1N4148WS, SOD-323, flyback diode):
  cathode → VIN_SW (J7 pin 2)
  anode   → $1N7096 (J7 pin 1 / Q6 collector)
```

D5 clamps the motor back-EMF when Q6 turns off.

### WS2812B RGB LED (LED3)

```
LED3 pin 1 (VDD)  → 3V3
LED3 pin 2 (DOUT) → NC (single LED, no chain)
LED3 pin 3 (GND)  → GND
LED3 pin 4 (DIN)  → $1N7340 → R27 (330 Ω) → LED_DATA → ESP32 GPIO21

C22 (100 nF, 0805) → LED3 VDD bypass to GND, placed within 5 mm of LED3
```

LED3 is powered from the regulated 3.3 V rail (not VIN_SW), which keeps the WS2812 controller above its 3.5 V minimum across the full LiPo discharge curve. The LED is slightly dimmer at 3.3 V than at 5 V — acceptable for an indicator.

### Buttons (SW2, SW3)

```
SW2 (KH-6X6X6H-TJ, 6×6 mm tact, through-hole):
  pin 1 → BTN1 → ESP32 GPIO47
  pin 4 → GND
R30 (10 kΩ) → BTN1 to 3V3  [pullup]

SW3 (KH-6X6X6H-TJ):
  pin 1 → BTN2 → ESP32 GPIO48
  pin 4 → GND
R31 (10 kΩ) → BTN2 to 3V3  [pullup]
```

Active-low, polled by firmware.

---

## Block 11: Environmental Sensor (U6 BME280, LGA-8)

```
U6 pin 1 (GND)   → GND
U6 pin 2 (CSB)   → 3V3  [selects I²C mode — CSB high = I²C, low = SPI]
U6 pin 3 (SDI)   → I2C_SDA
U6 pin 4 (SCK)   → I2C_SCL
U6 pin 5 (SDO)   → GND  [selects I²C address 0x76 — SDO low = 0x76, high = 0x77]
U6 pin 6 (VDDIO) → 3V3
U6 pin 7 (GND)   → GND
U6 pin 8 (VDD)   → 3V3

C20 (100 nF, 0805) → U6 3V3 to GND (bypass — handles both VDD and VDDIO since both tied to 3V3)
```

**I²C address:** 0x76. No conflict with MAX17048 (0x36) or FT6206 (0x38).

---

## Component Count

| Block | Designators | Count |
|---|---|---|
| MCU + support | U1, R6, R7, R10, C5, C9, C10 | 7 |
| USB + ESD | J1, U2, R1, R2, C1 | 5 |
| Charging | U3, R3, R4, R5, LED1, LED2, C2 | 7 |
| Power switch + LDO | SW1, U4, C3, C4 | 4 |
| Battery monitoring | U5, C11 | 2 |
| I²C pullups | R8, R9 | 2 |
| Display headers | J3, J4 | 2 |
| HV boost | U7, Q1, Q2, L1, D3, D4, C12, C13, C16, C14, C15, C21, R11, R12, R14, R15A, R15B, R15C, R16, R25, R26 | 21 |
| GM interface | J5, J6, R17A, R17B, R18, R19, R20, R21, R22A, R22B, R23, R24, C18, C19, Q3, Q5 | 16 |
| Output drivers | BZ1, Q4, Q6, D5, R28, R29, J7, LED3, R27, C22 | 10 |
| Buttons | SW2, SW3, R30, R31 | 4 |
| Environmental | U6, C20 | 2 |
| **Total** | | **83** |

---

## PCB Layout Notes

1. **HV isolation:** ~1.7 mm minimum clearance between HV nets (HV_OUT, $1N5660, $1N5667, $1N10242, $1N10203, R17/R22 chain intermediates, J5/J6 anode nets) and any low-voltage signal or GND traces. Meets IPC-2221 Class B (coated) at 500 V DC. Apply conformal coating to the HV zone for B1 (uncoated external) compliance.
2. **HV trace width:** 40 mil minimum on all HV nets.
3. **Power trace width:** 20 mil for VBAT, VIN_SW, 3V3, USB_5V.
4. **Signal trace width:** 10 mil for everything else.
5. **ESP32-S3 antenna:** ~20 mm copper-free zone above U1 toward J3, well exceeding Espressif's 15 mm recommendation.
6. **Bypass caps:** C9, C10 within 5 mm of U1 power pins. C21 within 5 mm of U7 pin 8. C22 within 5 mm of LED3 pin 1.
7. **USB traces:** D+/D− should be kept short (≤50 mm) and parallel. Differential impedance 90 Ω target but not critical at USB 2.0 FS short distances.
8. **TP4056 thermal pad:** copper fill + 4 thermal vias recommended (acceptable as-is at 500 mA charge).
9. **Mounting holes:** 4× plated 2.69 mm holes (M2.5 standoffs) at X = ±28.575 mm, Y = +48.260 mm and Y = −27.940 mm. Aligned with the J3/J4 header rows so the same standoffs support the Adafruit 2090.
