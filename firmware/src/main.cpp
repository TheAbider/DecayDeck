// =============================================================
// DecayDeck GC-20 v2 — Main Firmware
// Dual GM tube Geiger counter with TFT display + WiFi
// =============================================================

#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
#include <Adafruit_FT6206.h>
#include <Adafruit_NeoPixel.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ArduinoJson.h>

#include "pins.h"
#include "config.h"

// =============================================================
// GLOBALS
// =============================================================

Adafruit_ILI9341 tft(TFT_CS, TFT_DC);
Adafruit_FT6206 touch;
Adafruit_NeoPixel statusLED(1, LED_DATA, NEO_GRB + NEO_KHZ800);
ESP8266WebServer server(WEB_PORT);

// --- Pulse counting (ISR-safe) ---
volatile uint32_t pulseCount1 = 0;  // STS-5
volatile uint32_t pulseCount2 = 0;  // SI-3BG
volatile uint32_t lastPulseTime1 = 0;
volatile uint32_t lastPulseTime2 = 0;

// --- Rolling window for CPM ---
#define RING_SIZE 60
uint16_t ringBuffer1[RING_SIZE] = {0};  // Counts per second, last 60s
uint16_t ringBuffer2[RING_SIZE] = {0};
uint8_t ringIndex = 0;

// --- Measurement state ---
float cpm1 = 0, cpm2 = 0;          // Counts per minute
float cps1 = 0, cps2 = 0;          // Counts per second (smoothed)
float usvh1 = 0, usvh2 = 0;        // µSv/h per tube
float usvhTotal = 0;                // Combined dose rate
float totalDose = 0;                // Accumulated dose (µSv)
uint32_t countsThisSec1 = 0, countsThisSec2 = 0;

// --- Graph history ---
float history[HISTORY_POINTS] = {0};
uint16_t historyIndex = 0;
uint32_t historyCount = 0;

// --- Timing ---
uint32_t lastSecond = 0;
uint32_t lastMinute = 0;
uint32_t lastHVCheck = 0;
uint32_t lastBatCheck = 0;
uint32_t lastScreenUpdate = 0;
uint32_t lastTouchTime = 0;
uint32_t uptime = 0;

// --- State ---
enum Screen { SCREEN_MAIN, SCREEN_GRAPH, SCREEN_SETTINGS, SCREEN_WIFI };
Screen currentScreen = SCREEN_MAIN;
bool backlightDimmed = false;
bool hvEnabled = false;
bool wifiEnabled = false;
bool alarmActive = false;
bool clickEnabled = CLICK_SOUND;
float batteryVoltage = 4.2;
uint8_t batteryPercent = 100;

// --- WiFi ---
bool wifiAP = true;
String wifiSSID = "";
String wifiPass = "";

// =============================================================
// ISR — Geiger tube pulse handlers
// =============================================================

IRAM_ATTR void onPulse1() {
    uint32_t now = micros();
    if (now - lastPulseTime1 > 200) {  // 200µs dead time
        pulseCount1++;
        lastPulseTime1 = now;
    }
}

IRAM_ATTR void onPulse2() {
    uint32_t now = micros();
    if (now - lastPulseTime2 > 200) {
        pulseCount2++;
        lastPulseTime2 = now;
    }
}

// =============================================================
// HV BOOST CONTROL
// =============================================================

void hvInit() {
    pinMode(HV_EN, OUTPUT);
    digitalWrite(HV_EN, LOW);
    hvEnabled = false;
}

void hvEnable() {
    digitalWrite(HV_EN, HIGH);
    hvEnabled = true;
}

void hvDisable() {
    digitalWrite(HV_EN, LOW);
    hvEnabled = false;
}

uint16_t readHV() {
    uint16_t raw = analogRead(HV_SENSE);
    // ESP8266 ADC: 0-1023 = 0-1.0V
    // Voltage divider scales HV_OUT down to 0-1V range
    float voltage = (raw / 1023.0f) / HV_ADC_RATIO;
    return (uint16_t)voltage;
}

void hvRegulate() {
    if (!hvEnabled) return;
    uint16_t hv = readHV();
    if (hv < HV_TARGET_MV - 10) {
        digitalWrite(HV_EN, HIGH);
    } else if (hv > HV_TARGET_MV + 10) {
        digitalWrite(HV_EN, LOW);
    }
}

// =============================================================
// BATTERY
// =============================================================

void batteryCheck() {
    // Read from I2C fuel gauge (U3) if available
    // Fallback: estimate from HV_SENSE ADC when HV is off
    // For now, placeholder using a simple voltage estimate
    Wire.beginTransmission(0x36);  // MAX17048 typical address
    if (Wire.endTransmission() == 0) {
        Wire.beginTransmission(0x36);
        Wire.write(0x02);  // VCELL register
        Wire.endTransmission(false);
        Wire.requestFrom(0x36, 2);
        if (Wire.available() >= 2) {
            uint16_t vcell = (Wire.read() << 8) | Wire.read();
            batteryVoltage = vcell * 78.125f / 1000000.0f;
        }

        Wire.beginTransmission(0x36);
        Wire.write(0x04);  // SOC register
        Wire.endTransmission(false);
        Wire.requestFrom(0x36, 2);
        if (Wire.available() >= 2) {
            uint16_t soc = (Wire.read() << 8) | Wire.read();
            batteryPercent = soc / 256;
        }
    }
}

// =============================================================
// DISPLAY
// =============================================================

void drawHeader() {
    tft.fillRect(0, 0, SCREEN_WIDTH, 24, COLOR_HEADER);
    tft.setTextColor(0xFFFF);
    tft.setTextSize(1);
    tft.setCursor(4, 4);
    tft.print(DEVICE_NAME);
    tft.print(" v");
    tft.print(FIRMWARE_VERSION);

    // Battery indicator
    uint16_t batColor = COLOR_BATTERY;
    if (batteryPercent < 20) batColor = COLOR_ALARM;
    else if (batteryPercent < 40) batColor = COLOR_WARN;
    tft.fillRect(SCREEN_WIDTH - 30, 4, 26, 12, COLOR_BG);
    tft.drawRect(SCREEN_WIDTH - 30, 4, 24, 12, batColor);
    tft.fillRect(SCREEN_WIDTH - 6, 7, 2, 6, batColor);
    uint8_t barWidth = map(batteryPercent, 0, 100, 0, 20);
    tft.fillRect(SCREEN_WIDTH - 28, 6, barWidth, 8, batColor);

    // WiFi indicator
    if (wifiEnabled) {
        tft.setCursor(SCREEN_WIDTH - 50, 4);
        tft.setTextColor(COLOR_ACCENT);
        tft.print("WiFi");
    }

    // HV indicator
    if (hvEnabled) {
        tft.setCursor(SCREEN_WIDTH - 80, 4);
        tft.setTextColor(COLOR_WARN);
        tft.print("HV");
    }
}

void drawMainScreen() {
    tft.fillScreen(COLOR_BG);
    drawHeader();

    // Large dose rate display
    tft.setTextSize(3);
    tft.setTextColor(usvhTotal > DOSE_ALARM_USV ? COLOR_ALARM :
                     usvhTotal > DOSE_WARN_USV ? COLOR_WARN : COLOR_TEXT);
    tft.setCursor(10, 35);
    tft.print(usvhTotal, 3);
    tft.setTextSize(2);
    tft.print(" uSv/h");

    // Separator
    tft.drawFastHLine(0, 65, SCREEN_WIDTH, COLOR_TEXT_DIM);

    // Per-tube readings
    tft.setTextSize(1);
    tft.setTextColor(COLOR_TEXT);

    tft.setCursor(10, 75);
    tft.print("STS-5:   ");
    tft.print(cpm1, 0);
    tft.print(" CPM  ");
    tft.print(usvh1, 3);
    tft.print(" uSv/h");

    tft.setCursor(10, 90);
    tft.print("SI-3BG:  ");
    tft.print(cpm2, 0);
    tft.print(" CPM  ");
    tft.print(usvh2, 3);
    tft.print(" uSv/h");

    // CPS bar
    tft.drawFastHLine(0, 108, SCREEN_WIDTH, COLOR_TEXT_DIM);
    tft.setCursor(10, 115);
    tft.setTextColor(COLOR_ACCENT);
    tft.print("CPS: ");
    tft.print(cps1 + cps2, 1);

    // CPS bar graph
    uint16_t barLen = constrain((uint16_t)((cps1 + cps2) * 10), 0, SCREEN_WIDTH - 60);
    tft.fillRect(55, 113, SCREEN_WIDTH - 60, 12, COLOR_GRAPH_BG);
    if (barLen > 0) {
        uint16_t barColor = COLOR_GRAPH;
        if (cps1 + cps2 > 10) barColor = COLOR_WARN;
        if (cps1 + cps2 > 50) barColor = COLOR_ALARM;
        tft.fillRect(55, 113, barLen, 12, barColor);
    }

    // Mini graph (last 60 readings)
    drawMiniGraph(0, 135, SCREEN_WIDTH, 80);

    // Bottom status bar
    tft.fillRect(0, SCREEN_HEIGHT - 20, SCREEN_WIDTH, 20, COLOR_HEADER);
    tft.setTextColor(0xFFFF);
    tft.setTextSize(1);
    tft.setCursor(4, SCREEN_HEIGHT - 16);
    tft.print("Dose: ");
    tft.print(totalDose, 2);
    tft.print(" uSv  HV:");
    tft.print(readHV());
    tft.print("V  Up:");
    tft.print(uptime / 60);
    tft.print("m");
}

void drawMiniGraph(int x, int y, int w, int h) {
    tft.fillRect(x, y, w, h, COLOR_GRAPH_BG);
    tft.drawRect(x, y, w, h, COLOR_TEXT_DIM);

    // Find max for scaling
    float maxVal = 0.1f;
    for (int i = 0; i < min((int)historyCount, HISTORY_POINTS); i++) {
        if (history[i] > maxVal) maxVal = history[i];
    }

    // Draw scale label
    tft.setTextSize(1);
    tft.setTextColor(COLOR_TEXT_DIM);
    tft.setCursor(x + 2, y + 2);
    tft.print(maxVal, 2);
    tft.print(" uSv/h");

    // Plot points
    int points = min((int)historyCount, min(HISTORY_POINTS, w - 4));
    if (points < 2) return;

    for (int i = 1; i < points; i++) {
        int idx1 = (historyIndex - points + i - 1 + HISTORY_POINTS) % HISTORY_POINTS;
        int idx2 = (historyIndex - points + i + HISTORY_POINTS) % HISTORY_POINTS;
        int y1 = y + h - 2 - (int)((history[idx1] / maxVal) * (h - 6));
        int y2 = y + h - 2 - (int)((history[idx2] / maxVal) * (h - 6));
        y1 = constrain(y1, y + 1, y + h - 2);
        y2 = constrain(y2, y + 1, y + h - 2);
        int x1 = x + 2 + ((i - 1) * (w - 4)) / points;
        int x2 = x + 2 + (i * (w - 4)) / points;
        tft.drawLine(x1, y1, x2, y2, COLOR_GRAPH);
    }
}

void drawGraphScreen() {
    tft.fillScreen(COLOR_BG);
    drawHeader();

    tft.setTextSize(1);
    tft.setTextColor(COLOR_TEXT);
    tft.setCursor(10, 30);
    tft.print("Dose Rate History (");
    tft.print(min((int)historyCount, HISTORY_POINTS));
    tft.print(" min)");

    drawMiniGraph(5, 45, SCREEN_WIDTH - 10, SCREEN_HEIGHT - 70);

    // Bottom nav hint
    tft.setCursor(10, SCREEN_HEIGHT - 16);
    tft.setTextColor(COLOR_ACCENT);
    tft.print("Touch: Main  |  BTN: Settings");
}

void updateDisplay() {
    switch (currentScreen) {
        case SCREEN_MAIN:
            drawMainScreen();
            break;
        case SCREEN_GRAPH:
            drawGraphScreen();
            break;
        case SCREEN_SETTINGS:
        case SCREEN_WIFI:
            drawMainScreen();  // Placeholder
            break;
    }
}

// =============================================================
// BUZZER / VIBRATE / LED
// =============================================================

void clickBuzzer() {
    if (!clickEnabled) return;
    digitalWrite(BUZZER_PIN, HIGH);
    delayMicroseconds(CLICK_DURATION_US);
    digitalWrite(BUZZER_PIN, LOW);
}

void flashLED(uint8_t r, uint8_t g, uint8_t b) {
    statusLED.setPixelColor(0, statusLED.Color(r, g, b));
    statusLED.show();
}

void ledOff() {
    statusLED.setPixelColor(0, 0);
    statusLED.show();
}

void pulseVibrate(uint16_t ms) {
    digitalWrite(VIBRATE_PIN, HIGH);
    delay(ms);
    digitalWrite(VIBRATE_PIN, LOW);
}

// =============================================================
// WIFI + WEB SERVER
// =============================================================

void setupWiFiAP() {
    WiFi.mode(WIFI_AP);
    WiFi.softAP(WIFI_AP_SSID, WIFI_AP_PASS);
    wifiEnabled = true;
}

void handleRoot() {
    String html = "<!DOCTYPE html><html><head>"
        "<meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>DecayDeck</title>"
        "<style>"
        "body{font-family:monospace;background:#111;color:#0f0;padding:20px;}"
        "h1{color:#0ff;} .val{font-size:2em;} .warn{color:#ff0;} .alarm{color:#f00;}"
        ".card{background:#1a1a1a;border:1px solid #333;padding:15px;margin:10px 0;border-radius:8px;}"
        ".bar{height:20px;background:#020;margin:5px 0;position:relative;}"
        ".bar-fill{height:100%;background:#0f0;transition:width 0.5s;}"
        "</style>"
        "<script>"
        "function update(){"
        "fetch('/api/data').then(r=>r.json()).then(d=>{"
        "document.getElementById('dose').textContent=d.usvh.toFixed(3);"
        "document.getElementById('cpm1').textContent=d.cpm1.toFixed(0);"
        "document.getElementById('cpm2').textContent=d.cpm2.toFixed(0);"
        "document.getElementById('cps').textContent=d.cps.toFixed(1);"
        "document.getElementById('hv').textContent=d.hv;"
        "document.getElementById('bat').textContent=d.bat+'%';"
        "document.getElementById('total').textContent=d.totalDose.toFixed(2);"
        "document.getElementById('up').textContent=d.uptime;"
        "var b=document.getElementById('bar');"
        "b.style.width=Math.min(d.cps*5,100)+'%';"
        "});"
        "setTimeout(update,1000);}"
        "update();"
        "</script></head><body>"
        "<h1>DecayDeck</h1>"
        "<div class='card'><div class='val' id='dose'>-</div> &micro;Sv/h</div>"
        "<div class='card'>STS-5: <span id='cpm1'>-</span> CPM<br>"
        "SI-3BG: <span id='cpm2'>-</span> CPM<br>"
        "CPS: <span id='cps'>-</span>"
        "<div class='bar'><div class='bar-fill' id='bar' style='width:0'></div></div></div>"
        "<div class='card'>Total Dose: <span id='total'>-</span> &micro;Sv<br>"
        "HV: <span id='hv'>-</span>V | Battery: <span id='bat'>-</span><br>"
        "Uptime: <span id='up'>-</span></div>"
        "</body></html>";
    server.send(200, "text/html", html);
}

void handleAPI() {
    JsonDocument doc;
    doc["usvh"] = usvhTotal;
    doc["cpm1"] = cpm1;
    doc["cpm2"] = cpm2;
    doc["cps"] = cps1 + cps2;
    doc["hv"] = readHV();
    doc["bat"] = batteryPercent;
    doc["totalDose"] = totalDose;

    uint32_t mins = uptime / 60;
    uint32_t hrs = mins / 60;
    String uptimeStr = String(hrs) + "h " + String(mins % 60) + "m";
    doc["uptime"] = uptimeStr;

    // History array
    JsonArray hist = doc["history"].to<JsonArray>();
    int points = min((int)historyCount, HISTORY_POINTS);
    for (int i = 0; i < points; i++) {
        int idx = (historyIndex - points + i + HISTORY_POINTS) % HISTORY_POINTS;
        hist.add(serialized(String(history[idx], 3)));
    }

    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
}

void setupWebServer() {
    server.on("/", handleRoot);
    server.on("/api/data", handleAPI);
    server.begin();
}

// =============================================================
// MEASUREMENT ENGINE
// =============================================================

void processSecond() {
    // Grab counts atomically
    noInterrupts();
    countsThisSec1 = pulseCount1;
    countsThisSec2 = pulseCount2;
    pulseCount1 = 0;
    pulseCount2 = 0;
    interrupts();

    // Store in ring buffer
    ringBuffer1[ringIndex] = countsThisSec1;
    ringBuffer2[ringIndex] = countsThisSec2;
    ringIndex = (ringIndex + 1) % RING_SIZE;

    // Calculate CPM (sum of last 60 seconds)
    cpm1 = 0; cpm2 = 0;
    for (int i = 0; i < RING_SIZE; i++) {
        cpm1 += ringBuffer1[i];
        cpm2 += ringBuffer2[i];
    }

    // CPS (smoothed)
    cps1 = cps1 * 0.7f + countsThisSec1 * 0.3f;
    cps2 = cps2 * 0.7f + countsThisSec2 * 0.3f;

    // Convert to µSv/h
    usvh1 = cpm1 / STS5_CPM_PER_USV;
    usvh2 = cpm2 / SI3BG_CPM_PER_USV;
    usvhTotal = usvh1;  // Use STS-5 as primary (more accurate for gamma)

    // Accumulate dose
    totalDose += usvhTotal / 3600.0f;  // µSv per second

    uptime++;

    // Click/flash on count
    if (countsThisSec1 > 0 || countsThisSec2 > 0) {
        clickBuzzer();
        flashLED(0, 20, 0);
    } else {
        ledOff();
    }

    // Alarm check
    if (usvhTotal > DOSE_ALARM_USV) {
        if (!alarmActive) {
            alarmActive = true;
            flashLED(50, 0, 0);
            if (VIBRATE_ON_ALARM) pulseVibrate(200);
        }
    } else {
        alarmActive = false;
    }
}

void processMinute() {
    // Store in history for graph
    history[historyIndex] = usvhTotal;
    historyIndex = (historyIndex + 1) % HISTORY_POINTS;
    if (historyCount < HISTORY_POINTS) historyCount++;
}

// =============================================================
// INPUT HANDLING
// =============================================================

void handleTouch() {
    if (!touch.touched()) return;

    TS_Point p = touch.getPoint();
    lastTouchTime = millis();

    if (backlightDimmed) {
        backlightDimmed = false;
        analogWrite(TFT_BL, BACKLIGHT_DEFAULT);
        return;
    }

    // Simple screen cycling on touch
    switch (currentScreen) {
        case SCREEN_MAIN:
            currentScreen = SCREEN_GRAPH;
            break;
        case SCREEN_GRAPH:
            currentScreen = SCREEN_MAIN;
            break;
        default:
            currentScreen = SCREEN_MAIN;
            break;
    }
    updateDisplay();
}

void handleBacklight() {
    if (!backlightDimmed && millis() - lastTouchTime > SCREEN_TIMEOUT_MS) {
        backlightDimmed = true;
        analogWrite(TFT_BL, BACKLIGHT_DIM);
    }
}

// =============================================================
// SETUP
// =============================================================

void setup() {
    Serial.begin(115200);
    Serial.println();
    Serial.println("DecayDeck v" FIRMWARE_VERSION);
    Serial.println("Initializing...");

    // Pins
    pinMode(BUZZER_PIN, OUTPUT);
    pinMode(VIBRATE_PIN, OUTPUT);
    pinMode(TFT_BL, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);
    digitalWrite(VIBRATE_PIN, LOW);
    analogWrite(TFT_BL, BACKLIGHT_DEFAULT);

    // I2C
    Wire.begin(I2C_SDA, I2C_SCL);

    // Display
    tft.begin();
    tft.setRotation(TFT_ROTATION);
    tft.fillScreen(COLOR_BG);
    tft.setTextColor(COLOR_TEXT);
    tft.setTextSize(2);
    tft.setCursor(20, 100);
    tft.println("DecayDeck");
    tft.setTextSize(1);
    tft.setCursor(20, 130);
    tft.println("v" FIRMWARE_VERSION);
    tft.setCursor(20, 150);
    tft.println("Starting HV boost...");

    // Touch
    if (touch.begin(40)) {
        Serial.println("Touch OK");
    } else {
        Serial.println("Touch not found");
    }

    // Status LED
    statusLED.begin();
    statusLED.setBrightness(30);
    flashLED(0, 0, 50);

    // HV boost
    hvInit();
    hvEnable();
    delay(HV_STARTUP_MS);

    tft.setCursor(20, 170);
    tft.print("HV: ");
    tft.print(readHV());
    tft.println("V");

    // GM tube interrupts
    pinMode(GM_INT1, INPUT);
    pinMode(GM_INT2, INPUT);
    attachInterrupt(digitalPinToInterrupt(GM_INT1), onPulse1, FALLING);
    attachInterrupt(digitalPinToInterrupt(GM_INT2), onPulse2, FALLING);

    // WiFi AP
    setupWiFiAP();
    setupWebServer();
    tft.setCursor(20, 190);
    tft.print("WiFi AP: ");
    tft.println(WIFI_AP_SSID);
    tft.setCursor(20, 205);
    tft.print("IP: ");
    tft.println(WiFi.softAPIP());

    // Battery initial check
    batteryCheck();

    // Startup complete
    delay(1500);
    flashLED(0, 50, 0);
    delay(200);
    ledOff();

    lastSecond = millis();
    lastMinute = millis();
    lastTouchTime = millis();
    lastScreenUpdate = millis();

    Serial.println("Ready!");
    updateDisplay();
}

// =============================================================
// MAIN LOOP
// =============================================================

void loop() {
    uint32_t now = millis();

    // 1-second tick
    if (now - lastSecond >= 1000) {
        lastSecond = now;
        processSecond();

        // Update display every second on main screen
        if (now - lastScreenUpdate >= CPS_UPDATE_MS) {
            lastScreenUpdate = now;
            updateDisplay();
        }
    }

    // 1-minute tick
    if (now - lastMinute >= 60000) {
        lastMinute = now;
        processMinute();
    }

    // HV regulation
    if (now - lastHVCheck >= HV_REGULATE_MS) {
        lastHVCheck = now;
        hvRegulate();
    }

    // Battery check
    if (now - lastBatCheck >= BAT_CHECK_MS) {
        lastBatCheck = now;
        batteryCheck();
    }

    // Touch input
    handleTouch();

    // Backlight auto-dim
    handleBacklight();

    // WiFi
    server.handleClient();

    yield();
}
