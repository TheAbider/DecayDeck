# DecayDeck GC-20 v2 — Pinout Reference

## ESP8266 (Wemos D1 Mini) GPIO Assignments

| U8 Pin | GPIO | Wemos | Function | Net Name |
|--------|------|-------|----------|----------|
| 1 | GND | GND | Ground | GND |
| 2 | 3.3V | 3V3 | Power | 3V3 |
| 4 | GPIO4 | D2 | GM tube 1 interrupt | GM_INT1 |
| 5 | GPIO4 | D2 | I2C data | I2C_SDA |
| 6 | GPIO5 | D1 | I2C clock | I2C_SCL |
| 7 | GPIO3 | RX | Touch interrupt | TOUCH_INT |
| 8 | GPIO16 | D0 | TFT backlight PWM | TFT_BL |
| 9 | GPIO14 | D5 | Vibration motor | VIBRATE |
| 10 | GPIO9 | SD2 | Buzzer driver | BUZZER |
| 11 | GPIO15 | D8 | WS2812 LED data | LED_DATA |
| 12 | - | RST | TFT reset | TFT_RST |
| 13 | GPIO3 | RX | USB D- (programming) | USB_DN |
| 14 | GPIO1 | TX | USB D+ (programming) | USB_DP |
| 15 | GPIO12 | D6 | GM tube 2 interrupt | GM_INT2 |
| 17 | GPIO2 | D4 | TFT data/command | TFT_DC |
| 18 | GPIO15 | D8 | TFT chip select | TFT_CS |
| 19 | GPIO13 | D7 | SPI MOSI | SPI_MOSI |
| 20 | GPIO14 | D5 | SPI clock | SPI_SCK |
| 21 | GPIO12 | D6 | SPI MISO | SPI_MISO |
| 22 | GPIO0 | D3 | SD card chip select | SD_CS |
| 31 | GPIO10 | SD3 | HV boost enable | HV_EN |
| 38 | ADC0 | A0 | HV voltage sense | HV_SENSE |
| 39 | GPIO1 | TX | Battery alert | BAT_ALRT |

## Display (Adafruit 2090)

J6 bottom header (active), J5 top header (mechanical only).

| J6 Pin | Signal | Connection |
|--------|--------|------------|
| 1 | GND | Ground |
| 2 | Vin | VIN_SW (battery through switch) |
| 4 | CLK | SPI_SCK (GPIO14) |
| 5 | MISO | SPI_MISO (GPIO12) |
| 6 | MOSI | SPI_MOSI (GPIO13) |
| 7 | CS | TFT_CS (GPIO15) |
| 8 | D/C | TFT_DC (GPIO2) |
| 9 | RST | TFT_RST |
| 10 | Lite | TFT_BL (GPIO16) |
| 12 | IRQ | TOUCH_INT (GPIO3) |
| 13 | SDA | I2C_SDA (GPIO4) |
| 14 | SCL | I2C_SCL (GPIO5) |
| 19 | CCS | SD_CS (GPIO0) |

## Connectors

| Connector | Pin 1 | Pin 2 | Notes |
|-----------|-------|-------|-------|
| J1 (USB-C) | GND | USB_5V | Charging + programming |
| J2 (JST) | BAT+ | GND | LiPo battery |
| J3 (STS-5) | + HV_OUT | - Cathode sense | GM tube anode/cathode |
| J4 (SI-3BG) | + HV_OUT | - Cathode sense | GM tube anode/cathode |
| J7 (Motor) | + 3V3 | - Q6 collector | Vibration motor |

## I2C Devices

| Address | Device | Function |
|---------|--------|----------|
| 0x36 | MAX17048 (U3) | Fuel gauge (battery SOC) |
| 0x48 | INA219 (U4) | Battery voltage/current monitor |
| 0x38 | FT6206 | Capacitive touch controller (on display) |
