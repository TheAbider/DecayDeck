# DecayDeck GC-20 v3 — Schematic Reference

Complete component list and wiring guide for EasyEDA Pro.

## Summary

- **MCU:** ESP32-S3-WROOM-1-N4 (4MB flash, no PSRAM)
- **Display:** Adafruit 2090 (2.8" ILI9341 + FT6206 cap touch)
- **GM Tubes:** STS-5 + SI-3BG
- **HV:** 555-based boost, ~400V DC
- **Charging:** TP4056, 1A via USB-C
- **Regulator:** AP2112K-3.3 (600mA LDO)
- **Components:** ~81 total

## Power Rails

| Net | Voltage | Source |
|-----|---------|--------|
| USB_5V | 5V | USB-C VBUS |
| BAT+ | 3.0-4.2V | LiPo battery |
| VIN_SW | 3.0-4.2V | BAT+ through SW1 |
| 3V3 | 3.3V | AP2112K LDO output |
| HV_OUT | ~400V | 555 boost converter |

---

## Block 1: MCU — ESP32-S3-WROOM-1-N4

| Ref | Part | Value | Footprint |
|-----|------|-------|-----------|
| U1 | ESP32-S3-WROOM-1-N4 | MCU module | SMD (39-pin) |
| R6 | Resistor | 10kΩ | 0805 |
| R7 | Resistor | 10kΩ | 0805 |
| C5 | Capacitor | 1µF | 0805 |
| C6 | Capacitor | 100nF | 0805 |
| C7 | Capacitor | 100nF | 0805 |
| C8 | Capacitor | 100nF | 0805 |
| C9 | Capacitor | 100nF | 0805 |
| C10 | Capacitor | 10µF | 0805 |

**Wiring:**

```
U1 3V3   → 3V3 rail
U1 GND   → GND
U1 EN    → R6 (10k) → 3V3     (pullup)
U1 EN    → C5 (1µF) → GND     (reset delay)
U1 GPIO0 → R7 (10k) → 3V3     (boot mode pullup)

C6-C9: 100nF each, 3V3 → GND  (bypass, close to U1 power pins)
C10: 10µF, 3V3 → GND          (bulk decoupling)
```

**GPIO assignments (see pins.h for full map):**

| GPIO | Function | Connects To |
|------|----------|-------------|
| 1 | I2C_SDA | I2C bus |
| 2 | I2C_SCL | I2C bus |
| 3 | TOUCH_INT | J4 pin 12 (display IRQ) |
| 4 | GM_INT1 | GM1 sense circuit (Q3) |
| 5 | GM_INT2 | GM2 sense circuit (Q5) |
| 6 | HV_EN | Q7 base via R26 |
| 7 | HV_SENSE | R15B/R16 junction (ADC) |
| 8 | BUZZER | Q4 base via R28 |
| 9 | VIBRATE | Q6 base via R29 |
| 10 | TFT_CS | J4 pin 7 |
| 11 | TFT_DC | J4 pin 8 |
| 12 | TFT_RST | J4 pin 9 |
| 13 | TFT_BL | J4 pin 10 |
| 14 | SPI_MOSI | J4 pin 6 |
| 15 | SPI_SCK | J4 pin 4 |
| 16 | SPI_MISO | J4 pin 5 |
| 17 | SD_CS | J4 pin 19 |
| 18 | BAT_ALRT | U5 ALRT pin |
| 19 | USB_D- | U2 output (fixed pin) |
| 20 | USB_D+ | U2 output (fixed pin) |
| 21 | LED_DATA | R27 → LED3 DIN |
| 47 | BTN1 | SW2 → GND |
| 48 | BTN2 | SW3 → GND |

---

## Block 2: USB-C + ESD Protection

| Ref | Part | Value | Footprint |
|-----|------|-------|-----------|
| J1 | USB-C connector | 16-pin | SMD |
| U2 | USBLC6-2SC6 | ESD diode | SOT-23-6L |
| R1 | Resistor | 5.1kΩ | 0805 |
| R2 | Resistor | 5.1kΩ | 0805 |
| C1 | Capacitor | 100nF | 0805 |

**Wiring:**

```
J1 VBUS → USB_5V
J1 D+   → U2 I/O (pin 3 or 4) → USB_DP → U1 GPIO20
J1 D-   → U2 I/O (pin 1 or 6) → USB_DN → U1 GPIO19
J1 CC1  → R1 (5.1k) → GND
J1 CC2  → R2 (5.1k) → GND
J1 GND  → GND

U2 VCC (pin 5) → USB_5V
U2 GND (pin 2) → GND

C1: USB_5V → GND (close to J1)
```

---

## Block 3: Battery Charging (TP4056)

| Ref | Part | Value | Footprint |
|-----|------|-------|-----------|
| U3 | TP4056 | LiPo charger | SOP-8 |
| R3 | Resistor | 1.2kΩ | 0805 |
| R4 | Resistor | 1kΩ | 0805 |
| R5 | Resistor | 1kΩ | 0805 |
| LED1 | LED | Red | 0805 |
| LED2 | LED | Green | 0805 |
| C2 | Capacitor | 10µF | 0805 |

**Wiring:**

```
U3 VCC  (pin 4) → USB_5V
U3 BAT  (pin 3) → BAT+
U3 GND  (pin 2) → GND
U3 PROG (pin 5) → R3 (1.2k) → GND     (sets 1A charge current)
U3 CHRG (pin 7) → R4 (1k) → LED1 → GND (charging indicator)
U3 STDBY(pin 1) → R5 (1k) → LED2 → GND (charge complete)
U3 CE   (pin 8) → USB_5V               (charge enable)
U3 TEMP (pin 6) → GND                  (disable temp sensing, or add NTC)

C2: BAT+ → GND (close to U3)
```

**R3 sets charge current:** 1.2kΩ = 1A, 2.4kΩ = 500mA, 10kΩ = 130mA

---

## Block 4: Power (Battery + LDO)

| Ref | Part | Value | Footprint |
|-----|------|-------|-----------|
| J2 | JST PH 2.0mm | 2-pin | TH |
| SW1 | Toggle switch | SPST | TH |
| U4 | AP2112K-3.3TRG1 | 600mA LDO | SOT-23-5 |
| C3 | Capacitor | 1µF | 0805 |
| C4 | Capacitor | 1µF | 0805 |

**Wiring:**

```
J2 Pin 1 → BAT+ (red wire)
J2 Pin 2 → GND  (black wire)

SW1: BAT+ → VIN_SW (power switch)

U4 VIN (pin 1) → VIN_SW
U4 GND (pin 2) → GND
U4 EN  (pin 3) → VIN_SW        (always on when switch is on)
U4 NC  (pin 4) → NC
U4 VOUT(pin 5) → 3V3

C3: VIN_SW → GND (close to U4 input)
C4: 3V3 → GND    (close to U4 output)
```

**Note:** AP2112K-3.3 handles 600mA with 250mV dropout. Replaces the ME6210A30PG (300mA was too low for ESP32-S3 WiFi TX peaks).

---

## Block 5: Battery Monitoring

| Ref | Part | Value | Footprint |
|-----|------|-------|-----------|
| U5 | MAX17048 | Fuel gauge | DFN-8 (2×2mm) |
| C11 | Capacitor | 100nF | 0805 |

**Wiring:**

```
U5 VDD  → BAT+ (monitors battery voltage directly)
U5 GND  → GND
U5 SDA  → I2C_SDA
U5 SCL  → I2C_SCL
U5 ALRT → BAT_ALRT → U1 GPIO18
U5 QSTRT → NC
U5 CTG   → GND (LiPo chemistry select)

C11: U5 VDD → GND (close to U5)
```

I2C address: **0x36** (fixed)

---

## Block 6: I2C Bus

| Ref | Part | Value | Footprint |
|-----|------|-------|-----------|
| R8 | Resistor | 4.7kΩ | 0805 |
| R9 | Resistor | 4.7kΩ | 0805 |

**Wiring:**

```
I2C_SDA → R8 (4.7k) → 3V3   (pullup)
I2C_SCL → R9 (4.7k) → 3V3   (pullup)
```

**Devices on I2C bus:**

| Address | Device | Function |
|---------|--------|----------|
| 0x36 | MAX17048 (U5) | Battery fuel gauge |
| 0x38 | FT6206 | Touch controller (on display) |

---

## Block 7: Display (Adafruit 2090)

| Ref | Part | Value | Footprint |
|-----|------|-------|-----------|
| J3 | Pin header | 1×20 male | 2.54mm |
| J4 | Pin header | 1×20 male | 2.54mm |
| MH1 | Mounting hole | M2.5 | TH |
| MH2 | Mounting hole | M2.5 | TH |
| MH3 | Mounting hole | M2.5 | TH |
| MH4 | Mounting hole | M2.5 | TH |

**J3** = top header (all NC, mechanical support only)

**J4** = bottom header, active connections:

| J4 Pin | Signal | Net | ESP32 GPIO |
|--------|--------|-----|------------|
| 1 | GND | GND | — |
| 2 | Vin | VIN_SW | — |
| 3 | 3Vo | NC | — |
| 4 | CLK | SPI_SCK | 15 |
| 5 | MISO | SPI_MISO | 16 |
| 6 | MOSI | SPI_MOSI | 14 |
| 7 | CS | TFT_CS | 10 |
| 8 | D/C | TFT_DC | 11 |
| 9 | RST | TFT_RST | 12 |
| 10 | Lite | TFT_BL | 13 |
| 11 | GND | GND | — |
| 12 | IRQ | TOUCH_INT | 3 |
| 13 | SDA | I2C_SDA | 1 |
| 14 | SCL | I2C_SCL | 2 |
| 15-18 | IM0-3 | NC | — |
| 19 | CCS | SD_CS | 17 |
| 20 | CD | NC | — |

**Mounting holes:** same positions as v2 (see component-placement.txt)

---

## Block 8: HV Boost Converter

**Copy this sub-circuit from the v2 schematic — it's MCU-independent.**

| Ref | Part | Value | Footprint |
|-----|------|-------|-----------|
| U7 | TLC555CDR | 555 timer | SOIC-8 |
| Q1 | MMBTA44 | 400V NPN | SOT-23 |
| Q2 | C1815 | NPN | SOT-23 |
| Q7 | C1815 | NPN | SOT-23 |
| L1 | Inductor | 1mH | radial/SMD |
| D3 | 1N4007 | rectifier | SMA |
| D4 | 1N4007 | rectifier | SMA |
| C12 | Capacitor | 10nF/630V | radial |
| C13 | Capacitor | 10nF/630V | radial |
| C14 | Capacitor | 100pF | 0805 |
| R10 | Resistor | 120kΩ | 0805 |
| R11 | Resistor | 330Ω | 0805 |
| R12 | Resistor | (from v2) | 0805 |
| R13 | Resistor | (from v2) | 0805 |
| R14 | Trimmer pot | 500kΩ | TH |
| R15A | Resistor | 10MΩ | 0805 |
| R15B | Resistor | 10MΩ | 0805 |
| R16 | Resistor | 47kΩ | 0805 |
| R17 | Resistor | (from v2) | 0805 |
| R21 | Resistor | (from v2) | 0805 |
| R25 | Resistor | 10kΩ | 0805 |
| R26 | Resistor | 10kΩ | 0805 |

**Control connections to ESP32-S3:**

```
HV_EN:    U1 GPIO6 → R26 (10k) → Q7 base
          R25 (10k): HV_EN → GND  (pulldown, HV off at boot)

HV_SENSE: HV_OUT → R15A (10M) → R15B (10M) → R16 (47k) → GND
          R14 (trimmer) for calibration adjustment
          Junction R15B/R16 → C14 (100pF) → HV_SENSE → U1 GPIO7
```

**Output:** HV_OUT (~400V) → J5 pin 1, J6 pin 1

**IMPORTANT:** Isolate HV section with ground pour gap on PCB (≥100mil clearance from digital traces).

---

## Block 9: GM Tube Interface

| Ref | Part | Value | Footprint |
|-----|------|-------|-----------|
| J5 | Pin header | 1×2 | 2.54mm |
| J6 | Pin header | 1×2 | 2.54mm |
| Q3 | C1815 | NPN | SOT-23 |
| Q5 | C1815 | NPN | SOT-23 |
| R17-R20 | Resistors | (from v2) | 0805 |
| R22-R24 | Resistors | (from v2) | 0805 |
| C15 | Capacitor | (from v2) | 0805 |
| C16 | Capacitor | (from v2) | 0805 |

**Wiring:**

```
J5 (STS-5):
  Pin 1 (+) → HV_OUT (anode, ~400V)
  Pin 2 (-) → cathode sense → Q3 circuit → GM_INT1 → U1 GPIO4

J6 (SI-3BG):
  Pin 1 (+) → HV_OUT (anode, ~400V)
  Pin 2 (-) → cathode sense → Q5 circuit → GM_INT2 → U1 GPIO5
```

Copy the Q3/Q5 sense circuits from the v2 schematic (resistor networks R17-R24, coupling caps C15/C16).

---

## Block 10: Output Drivers

| Ref | Part | Value | Footprint |
|-----|------|-------|-----------|
| BZ1 | Buzzer | passive/active | SMD 7.5mm |
| Q4 | C1815 | NPN | SOT-23 |
| R28 | Resistor | 1kΩ | 0805 |
| Q6 | C1815 | NPN | SOT-23 |
| R29 | Resistor | 1kΩ | 0805 |
| J7 | Pin header | 1×2 | 2.54mm |
| D5 | 1N4148 | switching diode | SOD-323 |
| LED3 | WS2812B | RGB LED | 5050 |
| R27 | Resistor | 330Ω | 0805 |
| C17 | Capacitor | 100nF | 0805 |

**Wiring:**

```
BUZZER:
  U1 GPIO8 → R28 (1k) → Q4 base
  Q4 collector → BZ1 (-)
  Q4 emitter → GND
  BZ1 (+) → 3V3

VIBRATE MOTOR:
  U1 GPIO9 → R29 (1k) → Q6 base
  Q6 collector → J7 pin 2
  Q6 emitter → GND
  J7 pin 1 → 3V3
  D5: anode → J7 pin 2 (Q6 collector), cathode → J7 pin 1 (3V3)
  ^^^ FLYBACK DIODE — clamps motor back-EMF, prevents Q6 damage

WS2812 LED:
  U1 GPIO21 → R27 (330Ω) → LED3 DIN
  LED3 VDD → 3V3
  LED3 GND → GND
  C17: LED3 VDD → GND (100nF, close to LED)
```

---

## Block 11: Buttons

| Ref | Part | Value | Footprint |
|-----|------|-------|-----------|
| SW2 | Tactile button | NO | SMD |
| SW3 | Tactile button | NO | SMD |
| R30 | Resistor | 10kΩ | 0805 |
| R31 | Resistor | 10kΩ | 0805 |

**Wiring:**

```
SW2: U1 GPIO47 → SW2 → GND
     R30 (10k): GPIO47 → 3V3  (pullup)

SW3: U1 GPIO48 → SW3 → GND
     R31 (10k): GPIO48 → 3V3  (pullup)
```

---

## Component Count

| Block | Count |
|-------|-------|
| MCU + support | 9 |
| USB + ESD | 5 |
| Charging | 7 |
| Power | 5 |
| Battery monitoring | 2 |
| I2C pullups | 2 |
| Display + mounting | 6 |
| HV boost | 22 |
| GM interface | 10 |
| Outputs | 10 |
| Buttons | 4 |
| **Total** | **~82** |

---

## Changes from v2

| What | v2 (ESP8266) | v3 (ESP32-S3) |
|------|--------------|---------------|
| MCU | Wemos D1 Mini (ESP8266) | ESP32-S3-WROOM-1-N4 |
| Pin conflicts | 6 shared GPIOs | Zero conflicts |
| Regulator | ME6210A30PG (300mA) | AP2112K-3.3 (600mA) |
| USB | CH340 on D1 Mini | Native USB on ESP32-S3 |
| Charge rate | R1 dependent | 1A (R3 = 1.2kΩ) |
| Motor protection | None | D5 flyback diode |
| ADC | 10-bit, 0-1V | 12-bit, 0-3.3V |
| Free GPIOs | 0 | 10+ |

---

## PCB Layout Notes

1. **HV isolation:** Ground pour gap ≥100mil around HV zone (Block 8 components)
2. **HV traces:** 40mil width minimum for HV_OUT
3. **Power traces:** 20mil for BAT+, VIN_SW, 3V3, USB_5V
4. **Signal traces:** 10mil for everything else
5. **ESP32-S3 antenna:** Keep copper-free zone around the antenna end of the module (~10mm)
6. **Bypass caps:** Place C6-C10 as close to U1 power pins as possible
7. **USB traces:** Keep D+/D- traces equal length, ≤50mm, 90Ω differential impedance (or just keep them short and parallel)
