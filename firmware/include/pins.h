#pragma once

// =============================================================
// DecayDeck GC-20 v2 — Pin Definitions
// ESP8266 Wemos D1 Mini GPIO mapping
// =============================================================

// SPI Display (ILI9341 via Adafruit 2090)
#define TFT_CS      15  // GPIO15 - D8
#define TFT_DC       2  // GPIO2  - D4
#define TFT_RST     -1  // Connected to RST pin, use -1 for auto
#define TFT_BL      16  // GPIO16 - D0 (backlight PWM)
#define SD_CS        0  // GPIO0  - D3 (MicroSD chip select)

// SPI bus (hardware SPI)
// MOSI = GPIO13 (D7), MISO = GPIO12 (D6), SCK = GPIO14 (D5)

// I2C bus
#define I2C_SDA      4  // GPIO4  - D2
#define I2C_SCL      5  // GPIO5  - D1

// Touch
#define TOUCH_INT    3  // GPIO3  - RX (touch interrupt from FT6206)

// GM tube pulse inputs (interrupt-capable)
#define GM_INT1      4  // GPIO4  - shared with I2C_SDA (see note)
#define GM_INT2     12  // GPIO12 - D6 (shared with MISO, ok when not reading SD)

// NOTE: Pin mapping from U8 schematic (41-pin Wemos module):
// U8 pin 4  = GM_INT1 → This maps to Wemos D2/GPIO4
// U8 pin 15 = GM_INT2 → This maps to Wemos D6/GPIO12
// There is a pin conflict: GM_INT1 shares GPIO4 with I2C_SDA.
// In practice, GM pulses are very short (~100µs) and I2C transactions
// are brief. The ISR just increments a counter. Works but not ideal.

// HV boost control
#define HV_EN       10  // GPIO10 - SD3 (enable HV boost converter)
#define HV_SENSE    A0  // ADC0 (HV voltage feedback via R15A/R15B/R16 divider)

// Output drivers
#define BUZZER_PIN   9  // GPIO9  - SD2 (drives Q4 → buzzer)
#define VIBRATE_PIN 14  // GPIO14 - D5 (drives Q6 → vibration motor)
// NOTE: VIBRATE shares GPIO14 with SPI_SCK. Only pulse when not doing SPI.
#define LED_DATA    15  // GPIO15 - D8 (WS2812 data via R27)
// NOTE: LED_DATA shares GPIO15 with TFT_CS. WS2812 updates when TFT_CS is high.

// Buttons (active low, external pullup via R8/R9)
#define BTN1_PIN     3  // GPIO3  - RX (SW2, shared with TOUCH_INT)
#define BTN2_PIN    10  // GPIO10 - SD3 (SW3, shared with HV_EN)

// Battery
#define BAT_ALRT     1  // GPIO1  - TX (battery alert interrupt from U3)

// =============================================================
// PIN CONFLICT SUMMARY (ESP8266 has limited GPIOs):
//
// GPIO4:  I2C_SDA + GM_INT1 (manage in software)
// GPIO12: SPI_MISO + GM_INT2 (ok, MISO only during SD reads)
// GPIO14: SPI_SCK + VIBRATE (pulse motor only between SPI ops)
// GPIO15: TFT_CS + LED_DATA (update LED when CS high)
// GPIO10: HV_EN + BTN2 (read button state, then set HV)
// GPIO3:  TOUCH_INT + BTN1 (touch and button are alternate inputs)
//
// This is expected on an 11-GPIO chip driving this much hardware.
// The firmware manages conflicts through careful timing.
// =============================================================
