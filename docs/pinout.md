# DecayDeck v4 — Pinout Reference

Generated from `hardware/v4/design.py`, the netlist source of truth. The PCB matches it pin for pin
(`verify_pcb.py`), and so does the schematic (`sch_check.py`).

## ESP32-S3-WROOM-1-N16R2 GPIO map

16 MB flash and 2 MB quad PSRAM. On this variant IO35-IO37 are free; the octal-PSRAM R8 variants use them.
The module pin number is in brackets.

| GPIO | Net | Function |
|---|---|---|
| IO0 [27] | BTN_A | Button A, and BOOT when held at power-up (SW2) |
| IO1 [39] | HV_FB_ADC | HV feedback, ADC1_0 (HV_OUT / 301) |
| IO2 [38] | CC1_SNS | USB-C CC1 level, ADC1_1 (source current rating) |
| IO3 [15] | CC2_SNS | USB-C CC2 level, ADC1_2 |
| IO4 [4] | GM1_OUT | STS-5 pulses (to PCNT) |
| IO5 [5] | GM2_OUT | SI-3BG pulses (to PCNT) |
| IO6 [6] | HV_PWM | HV boost drive (gated in hardware by the comparator) |
| IO7 [7] | HV_REF_PWM | HV set point (PWM through an RC filter) |
| IO8 [12] | BUZZER | Buzzer MOSFET |
| IO9 [17] | VIBRATE | Vibration motor MOSFET |
| IO10 [18] | TFT_CS | Display chip select |
| IO11 [19] | SPI_MOSI | SPI MOSI (33 Ω series) |
| IO12 [20] | SPI_SCK | SPI clock (33 Ω series) |
| IO13 [21] | SPI_MISO | SPI MISO |
| IO14 [22] | TFT_DC | Display data / command |
| IO15 [8] | PWR_HOLD | Soft-power latch. Firmware sets it high first thing at boot |
| IO16 [9] | PWR_BTN_SNS | POWER button sense (low = pressed) |
| IO17 [10] | TFT_BL | Display backlight (PWM) |
| IO18 [11] | CHG_FAST | Charger input limit: 0 = USB 500 mA, 1 = 1.24 A |
| IO19 [13] | USB D− | Native USB |
| IO20 [14] | USB D+ | Native USB |
| IO21 [23] | RTC_INT | RV-3032 interrupt |
| IO35 [28] | CHG_SNS | Charging (low = charging) |
| IO36 [29] | I2C_SDA | I²C data |
| IO37 [30] | I2C_SCL | I²C clock |
| IO38 [31] | TOUCH_INT | Touch controller interrupt |
| IO39 [32] | SD_CS | microSD chip select |
| IO40 [33] | SD_CD | microSD card detect |
| IO41 [34] | TFT_RST | Display reset |
| IO42 [35] | BTN_B | Button B (SW3) |
| IO47 [24] | LED_DATA | WS2812B RGB LED |
| IO48 [25] | IMU_INT | Accelerometer interrupt |
| EN [3] | ESP_EN | Released by the TPS63802 power-good |

The following pins are left open:
- IO45 and IO46, which are strapping pins.
- IO43 and IO44 (UART0). Flashing and the console run over USB (USB-Serial-JTAG).

All analog inputs are on ADC1, so they keep working with WiFi on.

## I²C bus (3.3 V, 4.7 kΩ pull-ups)

| Address | Device |
|---|---|
| 0x19 | LIS2DH12 accelerometer (SA0 high) |
| 0x36 | MAX17048 fuel gauge |
| 0x38 | FT6206 touch controller (on the display) |
| 0x44 | OPT3001 ambient light (ADDR to GND) |
| 0x51 | RV-3032-C7 real-time clock |
| 0x76 | BME280 temperature / humidity / pressure (SDO to GND) |

## Display: Adafruit 2090 on J4 and J3

The 2090 plugs in face up on two 1×20 female headers, 8.5 mm tall, at its two short edges. Nylon M2.5 × 11 mm
standoffs go at its four corner holes. In the table, the 2090 net is Adafruit's net name in their board file, and
the SPI role is the ILI9341's pin function in 4-wire serial mode (IM = 1110).

| J4 pin | 2090 net | SPI role | Our net |
|---|---|---|---|
| 1 | GND | | GND |
| 2 | +5V (Vin) | supply | 3V3 |
| 3 | VCC (3Vo) | regulator output | DISP_3VO |
| 4 | LCD_RS_5V | SPI clock | SPI_SCK_D |
| 5 | SDO | MISO | SPI_MISO |
| 6 | SDI_5V | MOSI | SPI_MOSI_D |
| 7 | LCD_CS_5V | chip select | TFT_CS |
| 8 | LCD_WR_5V | data / command | TFT_DC |
| 9 | LCD_RST_5V | reset | TFT_RST |
| 10 | LCD_LITE | backlight | TFT_BL |
| 11 | GND | | GND |
| 12 | CTP_IRQ | touch interrupt | TOUCH_INT |
| 13 | SDA_5V | touch I²C | I2C_SDA |
| 14 | SCL_5V | touch I²C | I2C_SCL |
| 15, 16, 17 | IM3, IM2, IM1 | mode select, tied high | DISP_3VO (so no solder jumpers on the 2090) |
| 18 | IM0 | mode select, low | open (pulled down on the 2090) |
| 19 | SD_CS_5V | microSD select | SD_CS |
| 20 | CARDDET | card detect | SD_CD |

J3 carries GND (pins 1 and 12) and Vin (pin 2) and holds the display's other edge. Its other pins are the 2090's
parallel bus and stay unconnected.

## Off-board connections

| Pads | Net | Connects to |
|---|---|---|
| J2 pin 1 (silkscreen +) | BAT_RAW | LiPo + (red). Adafruit and SparkFun plugs fit as they come |
| J2 pin 2 (silkscreen −) | GND | LiPo − (black) |
| J5 (STS-5 +) | GM1_ANODE | STS-5 anode, through 9.4 MΩ |
| J6 (STS-5 −) | GM1_K | STS-5 cathode (sensed) |
| J7 (SI-3BG +) | GM2_ANODE | SI-3BG anode, through 4.4 MΩ |
| J8 (SI-3BG −) | GM2_K | SI-3BG cathode (sensed) |
| J9 (M+) | 3V3 | Vibration motor + |
| J10 (M−) | MOT_DRV | Vibration motor − (MOSFET low side) |
| J1 | USB-C | 5 V in (5.1 kΩ Rd), USB 2.0 full-speed data |

The tube anodes carry about 400 V. Use silicone wire rated 600 V or more for J5 and J7.

## Buttons and indicators

| Part | Where | Function |
|---|---|---|
| SW1 | Right edge, top | POWER: hold about 1 s to turn on. Firmware turns off on a long press |
| SW2 | Right edge, middle | A, and BOOT when held at power-up |
| SW3 | Right edge, bottom | B |
| LED1 | Chin, below the display | WS2812B RGB status LED |
| LED2 | Chin, below the display | Red charge LED (on while charging) |
| BZ1 | Chin | Magnetic buzzer (count clicks, alarms) |
