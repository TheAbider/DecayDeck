# DecayDeck v4 — Ordering, Assembly and First Power-On

## 1. Order the board

JLCPCB builds the board with every part fitted: the surface-mount parts plus J1 (USB-C) and the two display
headers J3/J4.

1. Re-check stock right before paying: `cd hardware/v4 && python stock_check.py 5`. A part JLC shows as short is
   decided by hand, never swapped for a substitute.
2. Upload `hardware/v4/fab/2026-10-25/DecayDeck_v4_Gerber.zip`, then the BOM and pick-and-place file from the same
   folder.
3. Pick the options in [the v4 README's Ordering section](../hardware/v4/README.md#ordering-jlcpcb-one-order).
   The ones that matter most:
   - ENIG finish.
   - Tented vias.
   - Standard PCBA.
   - Confirm the production file and the part placement before production.
   - No washing and no conformal coating.
4. In JLC's placement preview, check polarity and pin 1 for:
   - D1-D9 and LED1/LED2.
   - U1-U12 and Q1-Q8.
   - J1, J2 and BZ1.

## 2. Parts you buy separately

| Part | Notes |
|---|---|
| Adafruit 2090 display | 2.8" TFT, capacitive touch, microSD. It comes with the male header strip |
| **Battery: Adafruit #328**, 2500 mAh LiPo (DigiKey 1528-1840-ND, Mouser 485-328) | 50 × 60 × 7.3 mm (drawing max 50.5 × 62.5 × 8.1), 100 mm lead, JST-PH in Adafruit's polarity, which is what J2 is laid out for. Built-in protection. Adafruit rates it to 1.2 A charge; the board charges at 0.81 A. It sits behind the board, under the display. Don't fit a smaller cell than about 1700 mAh: Adafruit's 1200 mAh #258 is rated for 500 mA |
| 3-4 light pipes, **VCC LFB063CTP** (DigiKey LFB063CTP-ND) | 3 mm, frosted dome, 15.9 mm long. Press into 3.0 mm holes in the case front over LED1 (the frosting blends the RGB colours), LED2 and the OPT3001. A 19 mm LFB075CTP is the fallback if the display stack measures taller than expected. Clear printed plastic makes a poor light pipe: layer lines scatter the light |
| STS-5 and SI-3BG tubes | STS-5: 110 ± 2.5 mm overall, body 10-12 mm (sources differ), brass end pins about Ø6 mm. SI-3BG: 56 ± 5 mm, glass body Ø10 max, nickel end caps Ø6.5 × 7.4 mm. The + end (anode) is marked on each tube. Holders are part of the case |
| Silicone hookup wire, 600 V or more | For the tube anodes (J5, J7) |
| 3 V coin vibration motor | Goes on J9 (+) / J10 (−) |
| 4 nylon M2.5 × 11 mm standoffs with screws | Hold the display at the header height |

## 3. Assembly

1. **Inspect** the assembled board under light and magnification:
   - No bridges on the fine-pitch parts (U2, U3, U4, U5, U7, U8).
   - The diodes and LEDs match the silkscreen marks.
2. **Clean the HV area** if flux is visible. The 100 MΩ feedback resistors are sensitive to surface leakage. Use
   isopropyl alcohol on the upper-left area under the display. Keep it away from the three side buttons and the
   buzzer: Alps says no solvent on the buttons.
3. **Display headers.** Put the 2090's male headers in from the microSD side (the back of the display) and solder
   them on the glass side. The long pins then point away from the glass and into J3/J4.
4. **Mount the display.** Plug it into J3/J4, glass up, with J4 (the signal header) toward the chin. Fit the four
   nylon standoffs at its corner holes.
5. **Tubes.** Each tube's + end (anode) goes to its + pad and its − end to the − pad:
   - STS-5: J5 (+) and J6 (−).
   - SI-3BG: J7 (+) and J8 (−).

   The anode leads carry about 400 V: use the HV-rated wire, and keep the anode leads away from the board's
   low-voltage side.
6. **Motor.** Red to J9 (M+), the other lead to J10 (M−).
7. **Battery.** Leave it unplugged until the USB-only checks below pass.

## 4. First power-on

Measure on the capacitor pads; all values are against GND, e.g. a C10 pad or the USB-C shell.

1. **No power: check for shorts.**
   - 3V3 (C10 / C11) should read more than about 100 Ω to GND.
   - VSYS (C5) and VBAT (C6) should not be shorted.
2. **USB-C only (no battery, no display).** USB turns the board on by itself, through PGOOD and Q2.
   - VSYS (C5) is about 5 V.
   - 3V3 (C10) is 3.38 V.
   - The ESP32-S3 shows up as a USB serial / JTAG device.
3. **Flash the firmware** over USB. If the board doesn't enter download mode by itself: unplug, hold A/BOOT (SW2),
   plug USB back in, then release.
4. **Display.** Plug it in and check the screen, touch, backlight PWM and microSD.
5. **High voltage (firmware-controlled).** Start with a low set point and read HV through the firmware's ADC
   (HV_FB / 301), then ramp to about 400 V.
   - The STS-5 works at 360-440 V and the SI-3BG at 380-410 V.
   - Don't measure the 400 V rail with an ordinary 10 MΩ meter: it loads the supply and reads low.
   - The hardware ceiling (R28/R29) is 436 V.
6. **Tubes.** Background should show a few counts per minute on each tube.
7. **Battery.** Plug it in: the red charge LED lights while charging, and the fuel gauge reports the charge.
   - Unplug USB. The board stays on only if the firmware holds PWR_HOLD high.
   - A long press on POWER turns it off.

## 5. High-voltage safety

- The HV is microamps behind tens of megohms, but the caps hold enough to bite. Don't touch the HV area, the tube
  pads or the tube ends while it's on.
- After power-off the 3 × 47 MΩ bleeder empties the HV in about 2 s. Give it a few seconds before handling.
- The board keeps 2.5 mm between HV copper and everything else (IPC-2221B, 301-500 V, uncoated). Keep the case
  plastic, not metal, near the HV area and the tubes.

## 6. Calibration

Calibration lives in firmware and is set on the bench:

- The CPM to µSv/h factor for each tube.
- Dead-time correction at high rates.
- The HV set point for each tube's plateau.
- A known check source (or a calibrated meter side by side) gives the best numbers.
