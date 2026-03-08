#pragma once

// =============================================================
// DecayDeck GC-20 v3 — Configuration
// =============================================================

#define FIRMWARE_VERSION "0.2.0"
#define DEVICE_NAME "DecayDeck"

// --- GM Tube Calibration ---
// STS-5: ~158 CPM per µSv/h (gamma only, thick glass wall)
// SI-3BG: ~11 CPM per µSv/h (beta + gamma, mica window)
// Adjust with known calibration source (Cs-137 for gamma, Sr-90 for beta)
#define STS5_CPM_PER_USV    158.0f
#define SI3BG_CPM_PER_USV   11.0f

// --- HV Boost ---
#define HV_TARGET_MV        400      // Target HV in volts (label says mV, actually V)
#define HV_ADC_RATIO         0.00234f // Voltage divider: R16 / (R15A + R15B + R16)
#define HV_REGULATE_MS       100     // HV regulation loop interval
#define HV_STARTUP_MS        2000    // Time to let HV stabilize at boot

// --- Display ---
#define SCREEN_WIDTH         240
#define SCREEN_HEIGHT        320
#define TFT_ROTATION           0     // Portrait mode (phone orientation)
#define BACKLIGHT_DEFAULT    200     // PWM 0-255
#define BACKLIGHT_DIM         50     // Dimmed level
#define SCREEN_TIMEOUT_MS  30000     // Auto-dim after 30s

// --- Measurement ---
#define CPM_WINDOW_SEC        60     // Rolling window for CPM calculation
#define CPS_UPDATE_MS       1000     // CPS display refresh rate
#define HISTORY_POINTS       240     // Graph history (4 hours at 1/min)
#define DOSE_ALARM_USV       0.5f    // Alarm threshold µSv/h
#define DOSE_WARN_USV        0.3f    // Warning threshold µSv/h

// --- Data Logging ---
#define LOG_INTERVAL_SEC      60     // Log to SD every 60 seconds
#define LOG_FILENAME     "/decaydeck.csv"

// --- WiFi ---
#define WIFI_AP_SSID     "DecayDeck"
#define WIFI_AP_PASS     "geiger20"  // Min 8 chars for AP mode
#define WIFI_CONNECT_TIMEOUT 10000   // ms to wait for STA connection
#define WEB_PORT             80

// --- Battery ---
#define BAT_LOW_MV          3300     // Low battery warning (mV)
#define BAT_CRITICAL_MV     3100     // Critical, shutdown display
#define BAT_CHECK_MS        5000     // Check battery every 5s

// --- UI ---
#define CLICK_SOUND         true     // Buzzer click on each count
#define CLICK_DURATION_US     50     // Click pulse length
#define VIBRATE_ON_ALARM    true     // Vibrate on dose alarm
#define LED_FLASH_ON_COUNT  true     // Flash WS2812 on each count

// --- Colors (RGB565) ---
#define COLOR_BG          0x0000     // Black
#define COLOR_TEXT        0x07E0     // Green (Geiger counter aesthetic)
#define COLOR_TEXT_DIM    0x0320     // Dark green
#define COLOR_WARN        0xFDE0     // Yellow
#define COLOR_ALARM       0xF800     // Red
#define COLOR_ACCENT      0x07FF     // Cyan
#define COLOR_GRAPH       0x07E0     // Green
#define COLOR_GRAPH_BG    0x0120     // Very dark green
#define COLOR_HEADER      0x001F     // Blue
#define COLOR_BATTERY     0x07E0     // Green (changes to warn/alarm)

// --- LEDC ---
#define BL_CHANNEL           0      // LEDC channel for backlight PWM
