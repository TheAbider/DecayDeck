# DecayDeck v4 — Schematic Guide

The netlist source of truth is [`v4/design.py`](v4/design.py). The EasyEDA schematic is drawn from it
(`v4/sch_pretty.py`) and checked against it pin for pin (`v4/sch_check.py`). The PCB is checked the same way
(`v4/verify_pcb.py`). This guide walks the blocks in the order they appear on the sheet.

## Power rails

| Net | Voltage | Source |
|---|---|---|
| VBUS | 5 V | USB-C |
| VSYS | about 3.0-5.5 V | BQ24075 OUT: the battery, or USB when it is present |
| VBAT_P | 3.0-4.2 V | LiPo after the reverse-polarity P-FET (Q1) |
| 3V3 | 3.38 V | TPS63802 buck-boost (U3) |
| HV_OUT | about 400 V | Boost + doubler, comparator-regulated |

## USB-C input + ESD (J1, U12)

- CC1 and CC2 each have a 5.1 kΩ Rd to GND (R1, R2): a 5 V sink.
- Each CC line is also tapped through 100 kΩ + 1 nF (R3/C1, R4/C2) to an ADC pin (IO2, IO3). Firmware reads the
  advertised source current (default, 1.5 A or 3 A).
- D+ and D− are tied across both plug orientations and pass through a USBLC6-2SC6 to IO20/IO19.

## Charger, battery and fuel gauge (U2 BQ24075, Q1, J2, U4 MAX17048)

- **Power path:** OUT (VSYS) runs the board from USB and charges the cell at the same time.
- **Settings:**
  - ISET 1.1 kΩ (R5): 0.81 A charge.
  - ILIM 1.3 kΩ (R6): 1.24 A input.
  - TMR 56 kΩ (R7): 7.5 h fast-charge timer.
  - TS: 10 kΩ NTC on the board, over the cell.
- **Input limit from firmware:** EN1/EN2 come from one pin, CHG_FAST (IO18), through Q8. CHG_FAST = 0 gives USB
  500 mA (the default, including while the ESP32 is off); 1 gives the ILIM setting.
- **Charge indicator:** #CHG drives the red LED (LED2) from VSYS. A BAT54WS (D3) lets the ESP32 read it on IO35
  without back-powering the 3V3 rail.
- **Battery:** J2 is a JST-PH. Pin 1 is + (silkscreen +), matching Adafruit and SparkFun cells. Q1 (AO3401A,
  gate to GND) blocks a reversed cell.
- **Fuel gauge:** MAX17048 on VBAT_P, I²C 0x36. Its alert output is left open; firmware polls it.

## Soft power + 3V3 (Q2, D1, D2, SW1, U3 TPS63802)

- **Turn-on:** PWR_EN enables the buck-boost. It is the OR (D2) of two sources:
  - Q2, a P-FET from VSYS, which turns on when the POWER button or USB PGOOD pulls its gate low (through D1).
  - PWR_HOLD (IO15), driven by firmware.
- **Hold and turn-off:** firmware raises PWR_HOLD at boot. To turn off it drops PWR_HOLD, which works with the
  button released and no USB.
- **Button sense:** D1 lets the ESP32 read the POWER button (IO16) without the button's VSYS pull-up reaching
  the 3V3 rail.
- **Buck-boost:** TPS63802 with a 0.47 µH XFL4015 and a 511 kΩ / 88.7 kΩ divider, giving 3.38 V (the WS2812B's
  minimum is 3.3 V). Its PG output releases ESP_EN.

## ESP32-S3 + buttons (U1, SW2, SW3)

- ESP32-S3-WROOM-1-N16R2: 22 µF + 100 nF on 3V3, and a 10 kΩ / 1 µF EN delay.
- **Buttons:** Alps SKRTLAE010 side switches with 10 kΩ pull-ups and 100 nF debounce. A/BOOT is on IO0 and B on
  IO42. Pins 1 and 3 are joined inside the switch, so only pin 3 is wired.
- **Pins:** the full GPIO map is in [`docs/pinout.md`](../docs/pinout.md).

## Display: Adafruit 2090 (J4, J3)

- **SPI:** a 4-wire SPI bus to the ILI9341 and the 2090's microSD, with 33 Ω series resistors on SCK and MOSI.
- **Touch:** the FT6206 is on the shared I²C bus. Its IRQ has a 10 kΩ pull-up, and so does the card detect.
- **Mode:** IM1-IM3 are tied to the 2090's own 3Vo, giving 4-wire SPI with no solder jumpers.
- **Mechanical:** J3 is GND/Vin plus mechanical support for the display's other edge.

## I²C sensors (U5, U6, U7, U8)

BME280 (0x76), RV-3032-C7 RTC (0x51), LIS2DH12 accelerometer (0x19) and OPT3001 light sensor (0x44). The bus has
4.7 kΩ pull-ups and each sensor has a 100 nF decoupling cap.

The RTC's backup pin runs from VBAT_P through 1 kΩ + 100 nF, so it keeps time while the board is off. Firmware sets
its backup switchover to level mode once: the factory default disables it.

## HV supply (L2, Q3, D4-D7, C24-C27, U9, U10)

- **Boost:** 3V3 goes through R21 (10 Ω, 0.5 W) to L2 (1 mH). Q3 (FMMT458, 400 V) switches it.
- **Doubler:**
  - D4 charges C24 (V1).
  - C25 pumps the switch node onto D5 / D6.
  - HV_OUT is about 2 × V1, so Q3 only sees about 200 V.
- **Output:** two 10 nF 2 kV caps on HV_OUT, and an SMAJ440A clamp.
- **Feedback:** a 3 × 100 MΩ / 1 MΩ divider (301:1) gives HV_FB. It goes to the ADC (IO1) and to the TLV7011
  comparator.
- **Regulation, in hardware:**
  - The comparator checks HV_FB against HV_REF. HV_REF is a PWM from IO7, filtered by R28/R29/C23, and
    R28/R29 set its ceiling at 3.38 × 75/175 × 301 = 436 V.
  - The SN74LVC1G08 ANDs the comparator output with HV_PWM (IO6), so drive pulses stop as soon as HV reaches the
    reference.
  - The pulses reach Q3's base through R25 330 Ω, with C20 across it to speed up switching.
- **Bleeder:** 3 × 47 MΩ empties the HV in about 2 s after power-off.

## GM tubes (J5-J8, Q4, Q5, U11)

- **Anode resistors:** STS-5 9.4 MΩ (R35 + R36) and SI-3BG 4.4 MΩ (R40 + R41), on 1206 parts to share the voltage.
- **Cathode sensing:** each cathode has a 220 kΩ load to GND. A 1 kΩ + 100 pF filter feeds a BC847C (with a
  10 kΩ collector pull-up), then a 74LVC2G17 Schmitt buffer.
- **Outputs:** GM1_OUT (IO4) and GM2_OUT (IO5), counted by the ESP32's PCNT.

## Outputs (BZ1, Q6, Q7, LED1)

- Magnetic buzzer and vibration motor, each on an AO3400A low-side switch with a 100 Ω gate resistor, a 100 kΩ
  pull-down and a 1N4148WS flyback diode.
- WS2812B-2020 RGB LED on IO47 through 33 Ω, with 100 nF and 10 µF bulk on 3V3.
