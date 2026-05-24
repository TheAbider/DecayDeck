// =============================================================
// DecayDeck — Main Firmware
// ESP32-S3 + Dual GM tubes + ILI9341 TFT + WiFi
// =============================================================

#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <SD.h>
#include <time.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
#include <Adafruit_FT6206.h>
#include <Adafruit_NeoPixel.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <Adafruit_BME280.h>

#include "pins.h"
#include "config.h"

// =============================================================
// GLOBALS
// =============================================================

Adafruit_ILI9341 tft(TFT_CS, TFT_DC, TFT_RST);
Adafruit_FT6206 touch;
Adafruit_NeoPixel statusLED(1, LED_DATA, NEO_GRB + NEO_KHZ800);
WebServer server(WEB_PORT);
Adafruit_BME280 bme;

// --- Pulse counting (ISR-safe) ---
volatile uint32_t pulseCount1 = 0;  // STS-5
volatile uint32_t pulseCount2 = 0;  // SI-3BG
volatile uint32_t lastPulseTime1 = 0;
volatile uint32_t lastPulseTime2 = 0;

// --- Rolling window for CPM ---
#define RING_SIZE 60
uint16_t ringBuffer1[RING_SIZE] = {0};
uint16_t ringBuffer2[RING_SIZE] = {0};
uint8_t ringIndex = 0;

// --- Measurement state ---
float cpm1 = 0, cpm2 = 0;
float cps1 = 0, cps2 = 0;
float usvh1 = 0, usvh2 = 0;
float usvhTotal = 0;
float totalDose = 0;
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
uint32_t vibrateEnd = 0;

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

// --- Environmental (BME280) ---
bool bmeReady = false;
float envTemp = 0;      // °C
float envHumidity = 0;  // %RH
float envPressure = 0;  // hPa
uint32_t lastEnvRead = 0;

// --- SD Card / Logging ---
bool sdReady = false;
bool timeValid = false;
char currentLogDate[16] = "";
uint32_t lastLogTime = 0;
uint32_t lastSDMaint = 0;
uint16_t logRetainDays = LOG_RETAIN_DAYS;

// =============================================================
// ISR — Geiger tube pulse handlers
// =============================================================

void IRAM_ATTR onPulse1() {
    uint32_t now = micros();
    if (now - lastPulseTime1 > 200) {  // 200µs dead time
        pulseCount1++;
        lastPulseTime1 = now;
    }
}

void IRAM_ATTR onPulse2() {
    uint32_t now = micros();
    if (now - lastPulseTime2 > 200) {
        pulseCount2++;
        lastPulseTime2 = now;
    }
}

// =============================================================
// BACKLIGHT (LEDC PWM)
// =============================================================

void setBacklight(uint8_t level) {
    ledcWrite(BL_CHANNEL, level);
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
    // ESP32-S3 ADC: 12-bit (0-4095), 0-3.3V with 11dB attenuation (default)
    float senseV = (raw / 4095.0f) * 3.3f;
    return (uint16_t)(senseV / HV_ADC_RATIO);
}

void hvRegulate() {
    if (!hvEnabled) return;
    uint16_t hv = readHV();
    if (hv < HV_TARGET_V - 10) {
        digitalWrite(HV_EN, HIGH);
    } else if (hv > HV_TARGET_V + 10) {
        digitalWrite(HV_EN, LOW);
    }
}

// =============================================================
// BATTERY
// =============================================================

void batteryCheck() {
    Wire.beginTransmission(0x36);  // MAX17048
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
// DISPLAY (Portrait 240x320)
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

void drawMiniGraph(int x, int y, int w, int h) {
    tft.fillRect(x, y, w, h, COLOR_GRAPH_BG);
    tft.drawRect(x, y, w, h, COLOR_TEXT_DIM);

    float maxVal = 0.1f;
    for (int i = 0; i < min((int)historyCount, HISTORY_POINTS); i++) {
        if (history[i] > maxVal) maxVal = history[i];
    }

    tft.setTextSize(1);
    tft.setTextColor(COLOR_TEXT_DIM);
    tft.setCursor(x + 2, y + 2);
    tft.print(maxVal, 2);
    tft.print(" uSv/h");

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

void drawMainScreen() {
    tft.fillScreen(COLOR_BG);
    drawHeader();

    // Large dose rate
    tft.setTextSize(3);
    tft.setTextColor(usvhTotal > DOSE_ALARM_USV ? COLOR_ALARM :
                     usvhTotal > DOSE_WARN_USV ? COLOR_WARN : COLOR_TEXT);
    tft.setCursor(10, 35);
    tft.print(usvhTotal, 3);
    tft.setTextSize(2);
    tft.print(" uSv/h");

    tft.drawFastHLine(0, 65, SCREEN_WIDTH, COLOR_TEXT_DIM);

    // Per-tube readings
    tft.setTextSize(1);
    tft.setTextColor(COLOR_TEXT);
    tft.setCursor(10, 75);
    tft.print("STS-5:  ");
    tft.print(cpm1, 0);
    tft.print(" CPM  ");
    tft.print(usvh1, 3);
    tft.print(" uSv/h");

    tft.setCursor(10, 90);
    tft.print("SI-3BG: ");
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

    uint16_t barLen = constrain((uint16_t)((cps1 + cps2) * 10), 0, SCREEN_WIDTH - 60);
    tft.fillRect(55, 113, SCREEN_WIDTH - 60, 12, COLOR_GRAPH_BG);
    if (barLen > 0) {
        uint16_t barColor = COLOR_GRAPH;
        if (cps1 + cps2 > 10) barColor = COLOR_WARN;
        if (cps1 + cps2 > 50) barColor = COLOR_ALARM;
        tft.fillRect(55, 113, barLen, 12, barColor);
    }

    // Mini graph (taller in portrait mode)
    drawMiniGraph(0, 135, SCREEN_WIDTH, 140);

    // Bottom status bar
    tft.fillRect(0, SCREEN_HEIGHT - 20, SCREEN_WIDTH, 20, COLOR_HEADER);
    tft.setTextColor(0xFFFF);
    tft.setTextSize(1);
    tft.setCursor(4, SCREEN_HEIGHT - 16);
    tft.print("Dose:");
    tft.print(totalDose, 2);
    tft.print("uSv HV:");
    tft.print(readHV());
    tft.print("V Up:");
    tft.print(uptime / 60);
    tft.print("m");
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
        default:
            drawMainScreen();
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

void startVibrate(uint16_t ms) {
    digitalWrite(VIBRATE_PIN, HIGH);
    vibrateEnd = millis() + ms;
}

void updateVibrate() {
    if (vibrateEnd > 0 && millis() >= vibrateEnd) {
        digitalWrite(VIBRATE_PIN, LOW);
        vibrateEnd = 0;
    }
}

// =============================================================
// ENVIRONMENTAL SENSOR (BME280)
// =============================================================

bool bmeInit() {
    if (!bme.begin(BME280_ADDR, &Wire)) {
        Serial.println("BME280: not found");
        return false;
    }
    // Weather monitoring mode: low power, 1Hz forced measurements
    bme.setSampling(Adafruit_BME280::MODE_FORCED,
                    Adafruit_BME280::SAMPLING_X1,  // temp
                    Adafruit_BME280::SAMPLING_X1,  // pressure
                    Adafruit_BME280::SAMPLING_X1,  // humidity
                    Adafruit_BME280::FILTER_X4,
                    Adafruit_BME280::STANDBY_MS_1000);
    Serial.println("BME280: OK");
    return true;
}

void readEnvironment() {
    if (!bmeReady) return;
    bme.takeForcedMeasurement();
    envTemp = bme.readTemperature();
    envHumidity = bme.readHumidity();
    envPressure = bme.readPressure() / 100.0f;  // Pa → hPa
}

// =============================================================
// SD CARD / DATA LOGGING
// =============================================================

struct LogFileInfo {
    char name[20];
    uint32_t size;
};

bool sdInit() {
    if (!SD.begin(SD_CS, SPI)) {
        Serial.println("SD: not found");
        return false;
    }
    if (!SD.exists(LOG_DIR)) {
        SD.mkdir(LOG_DIR);
    }
    Serial.printf("SD: %lluMB total, %lluMB used\n",
        SD.totalBytes() / 1048576ULL, SD.usedBytes() / 1048576ULL);
    return true;
}

uint64_t sdFreeMB() {
    return (SD.totalBytes() - SD.usedBytes()) / 1048576ULL;
}

void getDateStr(char* buf, size_t len) {
    struct tm t;
    if (getLocalTime(&t, 100)) {
        strftime(buf, len, "%Y-%m-%d", &t);
        timeValid = true;
    } else {
        // No RTC sync yet — use boot-relative day counter
        snprintf(buf, len, "session-%05lu", uptime / 86400);
        timeValid = false;
    }
}

void getTimestampStr(char* buf, size_t len) {
    struct tm t;
    if (getLocalTime(&t, 100)) {
        strftime(buf, len, "%Y-%m-%d %H:%M:%S", &t);
    } else {
        unsigned long h = uptime / 3600;
        unsigned long m = (uptime % 3600) / 60;
        unsigned long s = uptime % 60;
        snprintf(buf, len, "%03lu:%02lu:%02lu", h, m, s);
    }
}

int listLogs(LogFileInfo* files, int maxFiles) {
    File dir = SD.open(LOG_DIR);
    if (!dir || !dir.isDirectory()) return 0;

    int count = 0;
    File entry;
    while ((entry = dir.openNextFile()) && count < maxFiles) {
        if (!entry.isDirectory()) {
            const char* name = entry.name();
            const char* slash = strrchr(name, '/');
            if (slash) name = slash + 1;
            strncpy(files[count].name, name, sizeof(files[count].name) - 1);
            files[count].name[sizeof(files[count].name) - 1] = '\0';
            files[count].size = entry.size();
            count++;
        }
        entry.close();
    }
    dir.close();

    // Sort by name (date-based filenames sort chronologically)
    for (int i = 0; i < count - 1; i++) {
        for (int j = i + 1; j < count; j++) {
            if (strcmp(files[i].name, files[j].name) > 0) {
                LogFileInfo tmp = files[i];
                files[i] = files[j];
                files[j] = tmp;
            }
        }
    }
    return count;
}

void deleteLog(const char* filename) {
    String path = String(LOG_DIR) + "/" + filename;
    if (SD.exists(path.c_str())) {
        SD.remove(path.c_str());
        Serial.printf("SD: deleted %s\n", filename);
    }
}

void logData() {
    if (!sdReady) return;

    char date[16];
    getDateStr(date, sizeof(date));
    String path = String(LOG_DIR) + "/" + date + ".csv";
    bool newFile = !SD.exists(path.c_str());

    File f = SD.open(path.c_str(), FILE_APPEND);
    if (!f) {
        Serial.println("SD: write failed");
        return;
    }

    if (newFile) {
        f.println("timestamp,cpm_sts5,cpm_si3bg,usvh_sts5,usvh_si3bg,usvh_total,dose_total_usv,hv_volts,battery_pct,temp_c,humidity_pct,pressure_hpa");
        strncpy(currentLogDate, date, sizeof(currentLogDate));
    }

    char ts[24];
    getTimestampStr(ts, sizeof(ts));
    f.printf("%s,%.0f,%.0f,%.3f,%.3f,%.3f,%.2f,%u,%u,%.1f,%.1f,%.1f\n",
        ts, cpm1, cpm2, usvh1, usvh2, usvhTotal, totalDose, readHV(), batteryPercent,
        envTemp, envHumidity, envPressure);
    f.flush();
    f.close();
}

// Delete logs older than retention policy
void cleanupByAge() {
    if (logRetainDays == 0 || !timeValid) return;

    struct tm now;
    if (!getLocalTime(&now, 100)) return;
    time_t nowEpoch = mktime(&now);

    LogFileInfo files[365];
    int count = listLogs(files, 365);

    for (int i = 0; i < count; i++) {
        struct tm fd = {0};
        if (sscanf(files[i].name, "%d-%d-%d", &fd.tm_year, &fd.tm_mon, &fd.tm_mday) == 3) {
            fd.tm_year -= 1900;
            fd.tm_mon -= 1;
            time_t fileEpoch = mktime(&fd);
            int ageDays = (nowEpoch - fileEpoch) / 86400;
            if (ageDays > logRetainDays) {
                deleteLog(files[i].name);
            }
        }
    }
}

// Emergency cleanup when SD card is nearly full
void cleanupBySpace() {
    while (sdFreeMB() < SD_AUTO_CLEAN_MB) {
        LogFileInfo files[365];
        int count = listLogs(files, 365);
        if (count <= 1) break;  // Never delete the current day's file
        deleteLog(files[0].name);  // Delete oldest
    }
}

void sdMaintenance() {
    if (!sdReady) return;
    cleanupByAge();
    cleanupBySpace();
    if (sdFreeMB() < SD_WARN_MB) {
        Serial.printf("SD: LOW SPACE — %lluMB free\n", sdFreeMB());
    }
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
        "var e=document.getElementById('env');"
        "if(d.temp)e.innerHTML='Temp: '+d.temp+'&deg;C | Humidity: '+d.humidity+'% | Pressure: '+d.pressure+' hPa';"
        "else e.innerHTML='BME280: not connected';"
        "var b=document.getElementById('bar');"
        "b.style.width=Math.min(d.cps*5,100)+'%';"
        "});"
        "setTimeout(update,1000);}"
        "fetch('/api/settime?epoch='+Math.floor(Date.now()/1000));"
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
        "<div class='card' id='env'></div>"
        "<div class='card'><a href='/data'>Data Manager</a> — download, export, cleanup logs</div>"
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
    if (bmeReady) {
        doc["temp"] = serialized(String(envTemp, 1));
        doc["humidity"] = serialized(String(envHumidity, 1));
        doc["pressure"] = serialized(String(envPressure, 1));
    }

    uint32_t mins = uptime / 60;
    uint32_t hrs = mins / 60;
    String uptimeStr = String(hrs) + "h " + String(mins % 60) + "m";
    doc["uptime"] = uptimeStr;

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

// --- Time sync (phone pushes its clock to the device) ---
void handleSetTime() {
    if (server.hasArg("epoch")) {
        time_t epoch = (time_t)server.arg("epoch").toInt();
        struct timeval tv = { .tv_sec = epoch, .tv_usec = 0 };
        settimeofday(&tv, NULL);
        timeValid = true;
        server.send(200, "application/json", "{\"ok\":true}");
    } else {
        server.send(400, "application/json", "{\"error\":\"Missing epoch\"}");
    }
}

// --- SD info ---
void handleSDInfo() {
    if (!sdReady) {
        server.send(503, "application/json", "{\"error\":\"SD not available\"}");
        return;
    }
    JsonDocument doc;
    doc["total_mb"] = (uint32_t)(SD.totalBytes() / 1048576ULL);
    doc["used_mb"] = (uint32_t)(SD.usedBytes() / 1048576ULL);
    doc["free_mb"] = (uint32_t)sdFreeMB();
    doc["retain_days"] = logRetainDays;
    doc["time_valid"] = timeValid;

    String resp;
    serializeJson(doc, resp);
    server.send(200, "application/json", resp);
}

// --- List log files ---
void handleLogList() {
    if (!sdReady) {
        server.send(503, "application/json", "{\"error\":\"SD not available\"}");
        return;
    }
    LogFileInfo files[365];
    int count = listLogs(files, 365);

    JsonDocument doc;
    JsonArray arr = doc["files"].to<JsonArray>();
    uint32_t totalSize = 0;
    for (int i = 0; i < count; i++) {
        JsonObject obj = arr.add<JsonObject>();
        obj["name"] = files[i].name;
        obj["size"] = files[i].size;
        totalSize += files[i].size;
    }
    doc["count"] = count;
    doc["total_bytes"] = totalSize;

    String resp;
    serializeJson(doc, resp);
    server.send(200, "application/json", resp);
}

// --- Download single log file ---
void handleLogDownload() {
    if (!sdReady) {
        server.send(503, "text/plain", "SD not available");
        return;
    }
    if (!server.hasArg("file")) {
        server.send(400, "text/plain", "Missing ?file= parameter");
        return;
    }
    String filename = server.arg("file");
    for (unsigned int i = 0; i < filename.length(); i++) {
        char c = filename[i];
        if (!isalnum(c) && c != '-' && c != '.') {
            server.send(400, "text/plain", "Invalid filename");
            return;
        }
    }
    String path = String(LOG_DIR) + "/" + filename;
    if (!SD.exists(path.c_str())) {
        server.send(404, "text/plain", "File not found");
        return;
    }
    File f = SD.open(path.c_str(), FILE_READ);
    if (!f) {
        server.send(500, "text/plain", "Open failed");
        return;
    }
    server.sendHeader("Content-Disposition", "attachment; filename=" + filename);
    server.streamFile(f, "text/csv");
    f.close();
}

// --- Export all logs as single CSV ---
void handleExportAll() {
    if (!sdReady) {
        server.send(503, "text/plain", "SD not available");
        return;
    }
    LogFileInfo files[365];
    int count = listLogs(files, 365);
    if (count == 0) {
        server.send(200, "text/plain", "No log files");
        return;
    }

    server.sendHeader("Content-Disposition", "attachment; filename=decaydeck_export.csv");
    server.setContentLength(CONTENT_LENGTH_UNKNOWN);
    server.send(200, "text/csv", "");
    server.sendContent("timestamp,cpm_sts5,cpm_si3bg,usvh_sts5,usvh_si3bg,usvh_total,dose_total_usv,hv_volts,battery_pct,temp_c,humidity_pct,pressure_hpa\n");

    for (int i = 0; i < count; i++) {
        String path = String(LOG_DIR) + "/" + files[i].name;
        File f = SD.open(path.c_str(), FILE_READ);
        if (!f) continue;
        f.readStringUntil('\n');  // Skip per-file header
        while (f.available()) {
            String line = f.readStringUntil('\n');
            if (line.length() > 0) {
                server.sendContent(line + "\n");
            }
        }
        f.close();
    }
}

// --- Delete single log ---
void handleLogDelete() {
    if (!sdReady) {
        server.send(503, "application/json", "{\"error\":\"SD not available\"}");
        return;
    }
    if (!server.hasArg("file")) {
        server.send(400, "application/json", "{\"error\":\"Missing ?file=\"}");
        return;
    }
    String filename = server.arg("file");
    for (unsigned int i = 0; i < filename.length(); i++) {
        char c = filename[i];
        if (!isalnum(c) && c != '-' && c != '.') {
            server.send(400, "application/json", "{\"error\":\"Invalid filename\"}");
            return;
        }
    }
    deleteLog(filename.c_str());
    server.send(200, "application/json", "{\"ok\":true}");
}

// --- Cleanup logs (by age or all) ---
void handleCleanup() {
    if (!sdReady) {
        server.send(503, "application/json", "{\"error\":\"SD not available\"}");
        return;
    }
    if (server.hasArg("days")) {
        int days = server.arg("days").toInt();
        if (days > 0) {
            uint16_t saved = logRetainDays;
            logRetainDays = days;
            cleanupByAge();
            logRetainDays = saved;
        }
    } else if (server.hasArg("all")) {
        LogFileInfo files[365];
        int count = listLogs(files, 365);
        for (int i = 0; i < count; i++) {
            deleteLog(files[i].name);
        }
    }
    server.send(200, "application/json", "{\"ok\":true}");
}

// --- Settings (get/set retention) ---
void handleSettings() {
    if (server.hasArg("retain_days")) {
        logRetainDays = server.arg("retain_days").toInt();
    }
    JsonDocument doc;
    doc["retain_days"] = logRetainDays;
    doc["click_sound"] = clickEnabled;
    doc["firmware"] = FIRMWARE_VERSION;

    String resp;
    serializeJson(doc, resp);
    server.send(200, "application/json", resp);
}

// --- Data management web page ---
void handleDataPage() {
    String html = "<!DOCTYPE html><html><head>"
        "<meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>DecayDeck Data</title>"
        "<style>"
        "body{font-family:monospace;background:#111;color:#0f0;padding:20px;max-width:600px;margin:0 auto;}"
        "h1{color:#0ff;}h2{color:#0ff;font-size:1.2em;}"
        ".c{background:#1a1a1a;border:1px solid #333;padding:15px;margin:10px 0;border-radius:8px;}"
        "a{color:#0ff;}button{background:#333;color:#0f0;border:1px solid #0f0;"
        "padding:8px 16px;margin:4px;cursor:pointer;font-family:monospace;border-radius:4px;}"
        "button:hover{background:#0f0;color:#111;}.dng{border-color:#f00;color:#f00;}"
        ".dng:hover{background:#f00;color:#111;}"
        "table{width:100%;border-collapse:collapse;}td,th{padding:6px;text-align:left;border-bottom:1px solid #333;}"
        ".sz{color:#888;}.bar{height:12px;background:#020;margin:4px 0;}.bf{height:100%;background:#0f0;}"
        "</style></head><body>"
        "<h1><a href='/' style='text-decoration:none;color:#0ff'>DecayDeck</a> &gt; Data</h1>"
        "<div class='c' id='sd'>Loading...</div>"
        "<div class='c'><h2>Log Files</h2><div id='fl'>Loading...</div><br>"
        "<button onclick=\"dl('/api/export','decaydeck_export.csv')\">Export All CSV</button></div>"
        "<div class='c'><h2>Cleanup</h2>"
        "<button onclick=\"cu('days=30')\">Older than 30d</button>"
        "<button onclick=\"cu('days=7')\">Older than 7d</button>"
        "<button class='dng' onclick=\"if(confirm('Delete ALL logs?'))cu('all=1')\">Delete All</button></div>"
        "<div class='c'><h2>Retention</h2>"
        "<input id='rd' type='number' value='90' min='0' max='999' style='width:60px;"
        "background:#222;color:#0f0;border:1px solid #333;padding:4px;font-family:monospace;'> days "
        "<button onclick=\"fetch('/api/settings?retain_days='+document.getElementById('rd').value)"
        ".then(()=>ld())\">Save</button> <span class='sz'>(0 = keep forever)</span></div>"
        "<script>"
        "fetch('/api/settime?epoch='+Math.floor(Date.now()/1000));"
        "function kb(b){return b<1024?b+'B':b<1048576?(b/1024).toFixed(1)+'KB':(b/1048576).toFixed(1)+'MB';}"
        "function ld(){"
        "fetch('/api/sd').then(r=>r.json()).then(d=>{"
        "var p=((d.used_mb/(d.total_mb||1))*100).toFixed(1);"
        "document.getElementById('sd').innerHTML="
        "'<b>SD Card:</b> '+d.used_mb+'MB / '+d.total_mb+'MB ('+d.free_mb+'MB free)<br>'"
        "+'<div class=\"bar\"><div class=\"bf\" style=\"width:'+p+'%\"></div></div>'"
        "+'Retention: '+d.retain_days+'d | Clock: '+(d.time_valid?'synced':'uptime only');"
        "document.getElementById('rd').value=d.retain_days;"
        "});"
        "fetch('/api/logs').then(r=>r.json()).then(d=>{"
        "if(!d.files.length){document.getElementById('fl').innerHTML='No logs yet.';return;}"
        "var h='<table><tr><th>Date</th><th>Size</th><th></th></tr>';"
        "d.files.forEach(f=>{"
        "h+='<tr><td>'+f.name+'</td><td class=\"sz\">'+kb(f.size)+'</td>'"
        "+'<td><a href=\"/api/download?file='+f.name+'\">DL</a> '"
        "+'<a href=\"#\" onclick=\"rm(\\''+f.name+'\\');return false\" style=\"color:#f00\">X</a></td></tr>';});"
        "h+='</table><br>'+d.count+' files, '+kb(d.total_bytes)+' total';"
        "document.getElementById('fl').innerHTML=h;});}"
        "function rm(f){if(confirm('Delete '+f+'?'))fetch('/api/delete?file='+f).then(()=>ld());}"
        "function cu(q){fetch('/api/cleanup?'+q).then(()=>ld());}"
        "function dl(u,n){var a=document.createElement('a');a.href=u;a.download=n;a.click();}"
        "ld();</script></body></html>";
    server.send(200, "text/html", html);
}

void setupWebServer() {
    // Main UI
    server.on("/", handleRoot);
    server.on("/data", handleDataPage);
    // Real-time API
    server.on("/api/data", handleAPI);
    server.on("/api/settime", handleSetTime);
    server.on("/api/settings", handleSettings);
    // SD / Log management API
    server.on("/api/sd", handleSDInfo);
    server.on("/api/logs", handleLogList);
    server.on("/api/download", handleLogDownload);
    server.on("/api/export", handleExportAll);
    server.on("/api/delete", handleLogDelete);
    server.on("/api/cleanup", handleCleanup);
    server.begin();
}

// =============================================================
// MEASUREMENT ENGINE
// =============================================================

void processSecond() {
    noInterrupts();
    countsThisSec1 = pulseCount1;
    countsThisSec2 = pulseCount2;
    pulseCount1 = 0;
    pulseCount2 = 0;
    interrupts();

    ringBuffer1[ringIndex] = countsThisSec1;
    ringBuffer2[ringIndex] = countsThisSec2;
    ringIndex = (ringIndex + 1) % RING_SIZE;

    cpm1 = 0; cpm2 = 0;
    for (int i = 0; i < RING_SIZE; i++) {
        cpm1 += ringBuffer1[i];
        cpm2 += ringBuffer2[i];
    }

    cps1 = cps1 * 0.7f + countsThisSec1 * 0.3f;
    cps2 = cps2 * 0.7f + countsThisSec2 * 0.3f;

    usvh1 = cpm1 / STS5_CPM_PER_USV;
    usvh2 = cpm2 / SI3BG_CPM_PER_USV;
    usvhTotal = usvh1;  // STS-5 as primary (more accurate for gamma)

    totalDose += usvhTotal / 3600.0f;
    uptime++;

    if (countsThisSec1 > 0 || countsThisSec2 > 0) {
        clickBuzzer();
        flashLED(0, 20, 0);
    } else {
        ledOff();
    }

    if (usvhTotal > DOSE_ALARM_USV) {
        if (!alarmActive) {
            alarmActive = true;
            flashLED(50, 0, 0);
            if (VIBRATE_ON_ALARM) startVibrate(200);
        }
    } else {
        alarmActive = false;
    }
}

void processMinute() {
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
        setBacklight(BACKLIGHT_DEFAULT);
        return;
    }

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
        setBacklight(BACKLIGHT_DIM);
    }
}

// =============================================================
// SETUP
// =============================================================

void setup() {
    Serial.begin(115200);
    Serial.println();
    Serial.println("DecayDeck v" FIRMWARE_VERSION " (ESP32-S3)");
    Serial.println("Initializing...");

    // Output pins
    pinMode(BUZZER_PIN, OUTPUT);
    pinMode(VIBRATE_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);
    digitalWrite(VIBRATE_PIN, LOW);

    // Backlight (LEDC PWM)
    ledcSetup(BL_CHANNEL, 5000, 8);
    ledcAttachPin(TFT_BL, BL_CHANNEL);
    setBacklight(BACKLIGHT_DEFAULT);

    // SPI bus with custom pins
    SPI.begin(SPI_SCK, SPI_MISO, SPI_MOSI);

    // I2C
    Wire.begin(I2C_SDA, I2C_SCL);

    // Display
    tft.begin();
    tft.setRotation(TFT_ROTATION);
    tft.fillScreen(COLOR_BG);
    tft.setTextColor(COLOR_TEXT);
    tft.setTextSize(2);
    tft.setCursor(50, 120);
    tft.println("DecayDeck");
    tft.setTextSize(1);
    tft.setCursor(70, 150);
    tft.println("v" FIRMWARE_VERSION);
    tft.setCursor(50, 170);
    tft.println("Starting HV boost...");

    // Touch
    if (touch.begin(40, &Wire)) {
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

    tft.setCursor(50, 185);
    tft.print("HV: ");
    tft.print(readHV());
    tft.println("V");

    // GM tube interrupts (dedicated pins, no conflicts!)
    pinMode(GM_INT1, INPUT);
    pinMode(GM_INT2, INPUT);
    attachInterrupt(digitalPinToInterrupt(GM_INT1), onPulse1, FALLING);
    attachInterrupt(digitalPinToInterrupt(GM_INT2), onPulse2, FALLING);

    // BME280 (I2C, same bus as touch + fuel gauge)
    bmeReady = bmeInit();
    tft.setCursor(50, 200);
    tft.print("ENV: ");
    tft.println(bmeReady ? "BME280 OK" : "not found");

    // SD card (shares SPI bus with display)
    sdReady = sdInit();
    tft.setCursor(50, 215);
    tft.print("SD: ");
    if (sdReady) {
        tft.printf("OK %lluMB free", sdFreeMB());
    } else {
        tft.print("not found");
    }

    // WiFi AP
    setupWiFiAP();
    setupWebServer();
    tft.setCursor(50, 230);
    tft.print("WiFi: ");
    tft.println(WIFI_AP_SSID);
    tft.setCursor(50, 245);
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

    // Environmental sensor
    if (bmeReady && now - lastEnvRead >= ENV_READ_MS) {
        lastEnvRead = now;
        readEnvironment();
    }

    // SD logging
    if (sdReady && now - lastLogTime >= (uint32_t)LOG_INTERVAL_SEC * 1000) {
        lastLogTime = now;
        logData();
    }

    // SD maintenance (cleanup old files, check space)
    if (sdReady && now - lastSDMaint >= SD_CHECK_MS) {
        lastSDMaint = now;
        sdMaintenance();
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

    // Non-blocking vibrate
    updateVibrate();

    // WiFi
    server.handleClient();
}
