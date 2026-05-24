# DecayDeck — Pinout Reference

Generated from the EasyEDA Pro board source and `firmware/include/pins.h`. Every row below was cross-checked against the actual board netlist.

## ESP32-S3-WROOM-1-N4 GPIO Assignments

| GPIO | Module pin | Function | Net Name | Direction |
|---|---|---|---|---|
| 0 | 27 | Boot select | BOOT | Input (strap) |
| 1 | 39 | I²C data | I2C_SDA | Bidir |
| 2 | 38 | I²C clock | I2C_SCL | Output |
| 3 | 15 | Touch interrupt | TOUCH_INT | Input |
| 4 | 4 | GM tube 1 pulse (STS-5) | GM_INT1 | Input (ISR) |
| 5 | 5 | GM tube 2 pulse (SI-3BG) | GM_INT2 | Input (ISR) |
| 6 | 6 | HV boost enable | HV_EN | Output |
| 7 | 7 | HV voltage sense | HV_SENSE | ADC Input |
| 8 | 12 | Buzzer driver | BUZZER | Output |
| 9 | 17 | Vibration motor | VIBRATE | Output |
| 10 | 18 | TFT chip select | TFT_CS | Output |
| 11 | 19 | TFT data/command | TFT_DC | Output |
| 12 | 20 | TFT reset | TFT_RST | Output |
| 13 | 21 | TFT backlight | TFT_BL | PWM Output |
| 14 | 22 | SPI MOSI | SPI_MOSI | Output |
| 15 | 8 | SPI clock | SPI_SCK | Output |
| 16 | 9 | SPI MISO | SPI_MISO | Input |
| 17 | 10 | SD card CS | SD_CS | Output |
| 18 | 11 | Battery alert | BAT_ALRT | Input |
| 19 | 13 | USB D− | USB_DN | Fixed (USB PHY) |
| 20 | 14 | USB D+ | USB_DP | Fixed (USB PHY) |
| 21 | 23 | WS2812 LED data | LED_DATA | Output |
| 36 | 29 | TP4056 charging status | CHRG_STAT | Input |
| 37 | 30 | TP4056 standby status | STDBY_STAT | Input |
| 38 | 31 | SD card detect | SD_CD | Input (pullup) |
| 47 | 24 | Button 1 | BTN1 | Input (pullup) |
| 48 | 25 | Button 2 | BTN2 | Input (pullup) |

**Strapping pins used:** GPIO0 (boot select, pulled high via R7 10 kΩ), GPIO3 (TOUCH_INT, JTAG_SEL — acceptable because FT6206 IRQ is open-drain and idles high).

**Available / unused GPIOs on the ESP32-S3-WROOM-1-N4 module:** GPIO35, GPIO39, GPIO40, GPIO41, GPIO42, GPIO45, GPIO46, plus UART0 pins GPIO43 (TX) and GPIO44 (RX).

**Not available on the module (internal flash SPI — do not use):** GPIO26, GPIO27, GPIO28, GPIO29, GPIO30, GPIO31, GPIO32.

## Display (Adafruit 2090)

J4 is the bottom header (active signals). J3 is the top header (mechanical support only — pins 1 and 12 are GND, all others NC).

| J4 Pin | Signal | Connection |
|---|---|---|
| 1 | GND | Ground |
| 2 | Vin | VIN_SW (battery through switch) |
| 3 | 3Vo | NC (display's internal 3.3 V not used) |
| 4 | CLK | SPI_SCK (GPIO15) |
| 5 | MISO | SPI_MISO (GPIO16) |
| 6 | MOSI | SPI_MOSI (GPIO14) |
| 7 | CS | TFT_CS (GPIO10) |
| 8 | D/C | TFT_DC (GPIO11) |
| 9 | RST | TFT_RST (GPIO12) |
| 10 | Lite | TFT_BL (GPIO13) |
| 11 | GND | Ground |
| 12 | IRQ | TOUCH_INT (GPIO3) |
| 13 | SDA | I2C_SDA (GPIO1) |
| 14 | SCL | I2C_SCL (GPIO2) |
| 15–18 | IM0–3 | NC on host. **Close jumpers IM1 / IM2 / IM3 on the back of the Adafruit 2090 to select SPI mode** — the shield ships in 8-bit parallel mode and the firmware drives SPI. |
| 19 | CCS | SD_CS (GPIO17) |
| 20 | CD | SD_CD (GPIO38) |

## External Connectors

| Connector | Pin 1 | Pin 2 | Notes |
|---|---|---|---|
| J1 (USB-C) | See USB-C pinout | — | Full 14-pad Type-C: VBUS, GND, CC1, CC2, D+, D−, shield. Supports charging AND native USB programming. |
| J2 (JST-PH 2.0) | VBAT (+) | GND (−) | Single-cell LiPo. Planned: 105070 3500 mAh. |
| J5 (STS-5 header) | Anode (HV via R17A + R17B series, 9.4 MΩ) | Cathode sense (R18 + C18) | 2-pin 2.54 mm. Two 4.7 MΩ 0805 in series — each sees ~200 V across, well inside the 0805 working-voltage rating. |
| J6 (SI-3BG header) | Anode (HV via R22A + R22B series, 1.02 MΩ) | Cathode sense (R23 + C19) | 2-pin 2.54 mm. Two 510 kΩ 0805 in series — each sees ~200 V across. |
| J7 (Motor header) | Q6 collector (−) | VIN_SW (+) | 2-pin 2.54 mm. 1030 coin motor, flyback diode D5 on board. |

## I²C Bus Devices

All on shared bus (GPIO1/GPIO2), 4.7 kΩ pullups to 3V3 (R8, R9).

| Address | Device | Function |
|---|---|---|
| 0x36 | MAX17048 (U5) | Battery fuel gauge (SOC, alert) |
| 0x38 | FT6206 (on Adafruit 2090) | Capacitive touch controller |
| 0x76 | BME280 (U6) | Temperature / humidity / pressure |

No address conflicts.

## Power Domains

| Net | Source | Consumers | Voltage range |
|---|---|---|---|
| USB_5V | J1 VBUS | U3 (TP4056), U2 (USBLC6), C1 | 4.75–5.25 V |
| VBAT | J2 battery or TP4056 BAT pin | U5 (MAX17048), SW1 | 3.0–4.2 V |
| VIN_SW | SW1 output | U4 (LDO in), J4 pin 2, U7 (555) + C21 bypass, BZ1, J7 (motor), D5 cathode | 3.0–4.2 V |
| 3V3 | U4 (LDO out) | U1 (ESP32-S3), U6 (BME280), LED3 (WS2812), all pullups, I²C pulls | 3.3 V |
| HV_OUT | U7 boost stage | R15A (divider), C16, R17A, R22A | ~400 V DC |
