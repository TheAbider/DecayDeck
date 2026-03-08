# DecayDeck — Pinout Reference

## ESP32-S3-WROOM-1-N4 GPIO Assignments

| GPIO | Function | Net Name | Direction |
|------|----------|----------|-----------|
| 1 | I2C data | I2C_SDA | Bidir |
| 2 | I2C clock | I2C_SCL | Output |
| 3 | Touch interrupt | TOUCH_INT | Input |
| 4 | GM tube 1 pulse | GM_INT1 | Input (ISR) |
| 5 | GM tube 2 pulse | GM_INT2 | Input (ISR) |
| 6 | HV boost enable | HV_EN | Output |
| 7 | HV voltage sense | HV_SENSE | ADC Input |
| 8 | Buzzer driver | BUZZER | Output |
| 9 | Vibration motor | VIBRATE | Output |
| 10 | TFT chip select | TFT_CS | Output |
| 11 | TFT data/command | TFT_DC | Output |
| 12 | TFT reset | TFT_RST | Output |
| 13 | TFT backlight | TFT_BL | PWM Output |
| 14 | SPI MOSI | SPI_MOSI | Output |
| 15 | SPI clock | SPI_SCK | Output |
| 16 | SPI MISO | SPI_MISO | Input |
| 17 | SD card CS | SD_CS | Output |
| 18 | Battery alert | BAT_ALRT | Input |
| 19 | USB D- | USB_DN | Fixed (USB) |
| 20 | USB D+ | USB_DP | Fixed (USB) |
| 21 | WS2812 LED data | LED_DATA | Output |
| 47 | Button 1 | BTN1 | Input (pullup) |
| 48 | Button 2 | BTN2 | Input (pullup) |

**Zero pin conflicts.** Every function has a dedicated GPIO.

**Free GPIOs:** 0 (boot), 26, 33, 34, 35-42 (N4 only), 38, 43 (TX), 44 (RX)

## Display (Adafruit 2090)

J4 bottom header (active), J3 top header (mechanical only).

| J4 Pin | Signal | Connection |
|--------|--------|------------|
| 1 | GND | Ground |
| 2 | Vin | VIN_SW (battery through switch) |
| 4 | CLK | SPI_SCK (GPIO15) |
| 5 | MISO | SPI_MISO (GPIO16) |
| 6 | MOSI | SPI_MOSI (GPIO14) |
| 7 | CS | TFT_CS (GPIO10) |
| 8 | D/C | TFT_DC (GPIO11) |
| 9 | RST | TFT_RST (GPIO12) |
| 10 | Lite | TFT_BL (GPIO13) |
| 12 | IRQ | TOUCH_INT (GPIO3) |
| 13 | SDA | I2C_SDA (GPIO1) |
| 14 | SCL | I2C_SCL (GPIO2) |
| 19 | CCS | SD_CS (GPIO17) |

## Connectors

| Connector | Pin 1 | Pin 2 | Notes |
|-----------|-------|-------|-------|
| J1 (USB-C) | GND | USB_5V | Charging + programming (native USB) |
| J2 (JST) | BAT+ | GND | LiPo battery |
| J5 (STS-5) | + HV_OUT | - Cathode sense | GM tube anode/cathode |
| J6 (SI-3BG) | + HV_OUT | - Cathode sense | GM tube anode/cathode |
| J7 (Motor) | + 3V3 | - Q6 collector | Vibration motor (D5 flyback) |

## I2C Devices

| Address | Device | Function |
|---------|--------|----------|
| 0x36 | MAX17048 (U5) | Fuel gauge (battery SOC) |
| 0x38 | FT6206 | Capacitive touch controller (on display) |
