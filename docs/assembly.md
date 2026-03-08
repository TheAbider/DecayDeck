# DecayDeck — Assembly Guide

## PCB Specifications

- **Board size:** 65mm x 108mm (2560 x 4250 mils)
- **Layers:** 2 (FR4)
- **Fabrication:** JLCPCB
- **MCU:** ESP32-S3-WROOM-1-N4 (soldered directly to PCB)
- **Components:** ~82 total

## Component Zones

### Below-Display Strip (visible, tall components)
Accessible from the front. Includes connectors, buttons, buzzer, LEDs.

- J1 (USB-C) — bottom center, board edge
- J2 (JST battery) — left edge, rotated 90°
- SW1 (power toggle) — right edge, rotated 270°
- BZ1 (buzzer) — upper-left
- SW2, SW3 (buttons) — center, front-facing
- LED1, LED2 (charge LEDs) — left side
- R14 (HV trimmer) — right side, adjustment access

### Under-Display (SMD, low-profile)
All components under the Adafruit 2090 display with ~6mm standoff clearance.
Maximum component height: 4mm.

**MCU (center):** U1 (ESP32-S3, 18x25.5x3.1mm), bypass caps C6-C10
**Power/Charging (lower-left):** U3 (TP4056), U2 (USB ESD), associated passives
**Voltage Regulation (left):** U4 (AP2112K-3.3 600mA), C3, C4
**Battery Monitoring (lower-right):** U5 (MAX17048 fuel gauge), I2C pullups
**Output Drivers (left-center):** Q4 (buzzer), Q6 (vibrate), LED3 (WS2812)
**GM Interface (right):** Q3, Q5, signal conditioning resistors
**HV Section (upper-right, ISOLATED):** U7 (555), L1, Q1, Q2, Q7, D3, D4

## Assembly Order

### 1. SMD Components (reflow or hand solder)
Start with the smallest components and work up:
1. All 0805 resistors and capacitors
2. SOT-23 transistors (Q1-Q7)
3. SOT-23-5 regulator (U4 AP2112K)
4. SOIC-8 IC (U7 555 timer)
5. SOP-8 (U3 TP4056)
6. SOT-23-6L (U2 USBLC6 ESD)
7. DFN-8 fuel gauge (U5 MAX17048)
8. 0805 LEDs (LED1, LED2)
9. WS2812B LED (LED3)
10. SOD-323 diodes (D5 flyback)

### 2. ESP32-S3 Module
Solder U1 (ESP32-S3-WROOM-1-N4) — 1.27mm pitch castellated pads.
Use flux and drag-solder technique. Verify all pads with continuity tester.
**This is the most critical soldering step.**

### 3. Through-Hole / Tall Components
1. Pin headers J3, J4 (2.54mm 1x20 male)
2. USB-C connector (J1)
3. JST connector (J2)
4. GM tube headers (J5, J6) — 1x2 pin headers
5. Motor header (J7) — 1x2 pin header
6. Toggle switch (SW1)
7. Tactile buttons (SW2, SW3)
8. Buzzer (BZ1)
9. Trimmer potentiometer (R14)
10. HV capacitors (C12, C13 — radial, 630V rated)

### 4. Mounting Hardware
1. Install M2.5 standoffs in MH1-MH4 (set display height ~6-8mm)
2. Plug display into J3 and J4 headers
3. Secure display with M2.5 nuts on standoffs

## HV Section Warning

The HV section generates approximately **400V DC**. While the current is extremely low
(microamps), take care:
- Do not touch HV components while powered on
- The HV capacitors (C12, C13) may retain charge briefly after power off
- Keep the HV section isolated from digital section (ground pour gap on PCB, ≥100mil)
- R14 trimmer adjusts HV sense calibration — set with multimeter on HV_OUT

## HV Calibration

1. Power on the board (without GM tubes connected)
2. Measure voltage at J5 pin 1 or J6 pin 1 relative to GND
3. Adjust R14 trimmer until HV_SENSE reads correctly in firmware
4. Target: 400V ±10V (adjust in firmware config.h if needed)

## GM Tube Installation

**STS-5 (J5):**
- Pin 1 (+) = Anode (HV_OUT, ~400V)
- Pin 2 (-) = Cathode (sense circuit)
- Wire with high-voltage rated wire, keep leads short

**SI-3BG (J6):**
- Pin 1 (+) = Anode (HV_OUT, ~400V)
- Pin 2 (-) = Cathode (sense circuit)

Both tubes mount in the 3D-printed case alongside the PCB. Use silicone or foam
to cushion tubes against vibration.

## Battery

- Single-cell 3.7V LiPo, JST PH 2.0mm connector
- Recommended: 103450 cell (~1800mAh, 10x34x50mm)
- Verify polarity: J2 Pin 1 = BAT+ (red), Pin 2 = GND (black)
- TP4056 charges via USB-C at 1A (set by R3 = 1.2kΩ)

## Programming

The ESP32-S3 uses **native USB** — no external USB-UART chip needed.

1. Connect USB-C cable to J1
2. The ESP32-S3 appears as a USB-Serial-JTAG device
3. PlatformIO auto-detects the port
4. Upload: `pio run -t upload`
5. Serial monitor: `pio device monitor`

**First-time flashing:** If the module is blank, hold GPIO0 low (connect R7 pad to GND) while plugging in USB. This enters download mode. After first firmware upload, subsequent uploads work automatically via USB-JTAG.

## First Power-On Checklist

1. [ ] Visual inspection — no solder bridges, especially on U1 (ESP32-S3) pads
2. [ ] Continuity check: 3V3 and GND should NOT be shorted
3. [ ] Connect USB-C (no battery yet) — check 5V on USB_5V, 3.3V on 3V3
4. [ ] Flash firmware via USB
5. [ ] Connect battery — verify SW1 switches VIN_SW on/off
6. [ ] Power on — display should show DecayDeck splash screen
7. [ ] Check HV output with multimeter (~400V on J5/J6 pin 1)
8. [ ] Connect one GM tube — verify counts on display
9. [ ] Connect WiFi (AP mode: "DecayDeck" / "geiger20")
10. [ ] Calibrate HV via R14 trimmer if needed
