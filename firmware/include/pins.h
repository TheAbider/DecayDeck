#pragma once

// =============================================================
// DecayDeck — Pin Definitions
// ESP32-S3-WROOM-1-N4 — Zero pin conflicts
// =============================================================

// SPI Display (ILI9341 via Adafruit 2090)
#define TFT_CS      10  // Chip select
#define TFT_DC      11  // Data/command
#define TFT_RST     12  // Reset
#define TFT_BL      13  // Backlight (LEDC PWM)

// SPI Bus (shared: display + SD card)
#define SPI_MOSI    14  // Master Out Slave In
#define SPI_SCK     15  // Clock
#define SPI_MISO    16  // Master In Slave Out

// SD Card (on Adafruit 2090, shares SPI bus)
#define SD_CS       17  // SD card chip select

// I2C Bus
#define I2C_SDA      1  // Data
#define I2C_SCL      2  // Clock

// Touch (FT6206 on Adafruit 2090)
#define TOUCH_INT    3  // Touch interrupt (active low)

// GM Tube Pulse Inputs (dedicated interrupt pins)
#define GM_INT1      4  // STS-5 cathode sense
#define GM_INT2      5  // SI-3BG cathode sense

// HV Boost Control
#define HV_EN        6  // Enable boost converter
#define HV_SENSE     7  // ADC1_CH6, HV voltage feedback

// Output Drivers
#define BUZZER_PIN   8  // Drives Q4 → buzzer
#define VIBRATE_PIN  9  // Drives Q6 → vibration motor
#define LED_DATA    21  // WS2812 RGB LED data

// Buttons (active low, external 10k pullups to 3V3)
#define BTN1_PIN    47  // SW2
#define BTN2_PIN    48  // SW3

// Battery
#define BAT_ALRT    18  // MAX17048 alert interrupt

// Charge Status (active low, accent LEDs also show these)
#define CHRG_STAT   36  // TP4056 charging indicator
#define STDBY_STAT  37  // TP4056 charge complete

// SD Card Detect (active low with 10k pullup)
#define SD_DETECT   38  // SD card inserted

// USB (native, hardware-fixed — do not reassign)
// GPIO19 = USB_D-
// GPIO20 = USB_D+

// Environmental Sensor (BME280, I2C — uses same SDA/SCL as above)
// I2C address: 0x76 (SDO pin tied to GND)

// Boot/Reset (active during boot only)
// EN:    10k pullup to 3V3 + 1µF cap to GND
// GPIO0: 10k pullup to 3V3 (boot mode select)

// =============================================================
// FREE GPIOs for future expansion (ESP32-S3-WROOM-1-N4 only):
// GPIO35, GPIO39, GPIO40, GPIO41, GPIO42, GPIO45, GPIO46
// GPIO43 (TX0), GPIO44 (RX0) — UART0 if needed
// Note: GPIO26-32 are internal SPI flash, NOT available on the module.
// Note: GPIO33, GPIO34, GPIO36, GPIO37 are in use on this board.
// =============================================================
