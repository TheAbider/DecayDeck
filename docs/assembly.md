# DecayDeck GC-20 v2 — Assembly Guide

## PCB Specifications

- **Board size:** 65mm x 108mm (2560 x 4250 mils)
- **Layers:** 2 (FR4)
- **Fabrication:** JLCPCB
- **Components:** 82 total (69 under-display SMD, 8 below-display, 5 display/mounting)

## Component Zones

### Below-Display Strip (visible, tall components)
Accessible from the front. Includes connectors, buttons, buzzer, LEDs.

- J1 (USB-C) — bottom center, board edge
- J2 (JST battery) — left edge, rotated 90°
- SW1 (power toggle) — right edge, rotated 270°
- BZ1 (buzzer) — upper-left
- SW2, SW3 (buttons) — center, front-facing
- LED1 (charge LED) — left side
- R14 (HV trimmer) — right side, adjustment access

### Under-Display (SMD, low-profile)
All components under the Adafruit 2090 display with ~6mm standoff clearance.
Maximum component height: 4mm.

**Power/Charging (lower-left):** U1 (TP4056), U7 (USB ESD), associated passives
**Voltage Regulation (left):** U2 (ME6210A30PG 3.3V), C3, C4
**Battery Monitoring (lower-right):** U3 (fuel gauge), U4 (monitor), I2C pullups
**MCU (center):** U8 (ESP8266 module), bypass caps C8-C10, C15-C18
**Output Drivers (left-center):** Q4 (buzzer), Q6 (vibrate), LED2 (WS2812)
**GM Interface (right):** Q3, Q5, signal conditioning resistors
**HV Section (upper-right, ISOLATED):** U6 (555), L1, Q1, Q2, Q7, D3, D4

## Assembly Order

### 1. SMD Components (reflow or hand solder)
Start with the smallest components and work up:
1. All 1206 resistors and capacitors
2. SOT-23 transistors (Q1-Q7)
3. SOT-89 regulator (U2)
4. SOIC-8 ICs (U6 555 timer, U9)
5. TP4056 (U1), USB ESD (U7)
6. Fuel gauge (U3), battery monitor (U4)
7. WS2812 LED (LED2)
8. C4 (CASE-B tantalum)

### 2. Through-Hole / Tall Components
1. Pin headers J5, J6 (2.54mm 1x20 male)
2. USB-C connector (J1)
3. JST connector (J2)
4. GM tube headers (J3, J4) — 1x2 pin headers
5. Motor header (J7) — 1x2 pin header
6. Toggle switch (SW1)
7. Tactile buttons (SW2, SW3)
8. Buzzer (BZ1)
9. 3mm LED (LED1)
10. Trimmer potentiometer (R14)

### 3. ESP8266 Module
Solder U8 (Wemos D1 Mini module) last — it's the tallest under-display component.

### 4. Mounting Hardware
1. Install M2.5 standoffs in MH1-MH4 (set display height ~6-8mm)
2. Plug display into J5 and J6 headers
3. Secure display with M2.5 nuts on standoffs

## HV Section Warning

The HV section generates approximately **400V DC**. While the current is extremely low
(microamps), take care:
- Do not touch HV components while powered on
- The HV capacitors (C11, C12) may retain charge briefly after power off
- Keep the HV section isolated from digital section (ground pour gap on PCB)
- R14 trimmer adjusts HV sense calibration — set with multimeter on HV_OUT

## HV Calibration

1. Power on the board (without GM tubes connected)
2. Measure voltage at J3 pin 1 or J4 pin 1 relative to GND
3. Adjust R14 trimmer until HV_SENSE reads correctly in firmware
4. Target: 400V ±10V (adjust in firmware config.h if needed)

## GM Tube Installation

**STS-5 (J3):**
- Pin 1 (+) = Anode (HV_OUT, ~400V)
- Pin 2 (-) = Cathode (sense circuit)
- Wire with high-voltage rated wire, keep leads short

**SI-3BG (J4):**
- Pin 1 (+) = Anode (HV_OUT, ~400V)
- Pin 2 (-) = Cathode (sense circuit)

Both tubes mount in the 3D-printed case alongside the PCB. Use silicone or foam
to cushion tubes against vibration.

## Battery

- Single-cell 3.7V LiPo, JST PH 2.0mm connector
- Recommended: 103450 cell (~1800mAh, 10x34x50mm)
- Verify polarity: J2 Pin 1 = BAT+ (red), Pin 2 = GND (black)
- TP4056 handles charging via USB-C at up to 1A (set by R1)

## First Power-On Checklist

1. [ ] Visual inspection — no solder bridges, all components oriented correctly
2. [ ] Continuity check: 3V3 and GND should NOT be shorted
3. [ ] Connect USB-C (no battery yet) — check 5V on USB_5V, 3.3V on 3V3
4. [ ] Connect battery — verify SW1 switches VIN_SW on/off
5. [ ] Power on — display should show DecayDeck splash screen
6. [ ] Check HV output with multimeter (~400V on J3/J4 pin 1)
7. [ ] Connect one GM tube — verify counts on display
8. [ ] Connect WiFi (AP mode: "DecayDeck" / "geiger20")
9. [ ] Calibrate HV via R14 trimmer if needed
