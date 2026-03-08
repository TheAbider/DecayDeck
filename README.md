# DecayDeck

Open-source handheld Geiger counter with dual GM tubes, capacitive touchscreen, WiFi, and LiPo battery.

## Hardware

- **MCU:** ESP32-S3-WROOM-1-N4 (dual-core 240MHz, native USB, WiFi + BLE 5.0)
- **Display:** Adafruit 2090 (2.8" ILI9341 TFT + FT6206 capacitive touch)
- **GM Tubes:** STS-5 (gamma) + SI-3BG (beta+gamma)
- **HV Supply:** 555-based boost converter (~400V DC)
- **Power:** Single-cell 3.7V LiPo (103450, ~1800mAh) with TP4056 USB-C charging (1A)
- **Regulator:** AP2112K-3.3 (600mA LDO)
- **Battery Monitoring:** MAX17048 fuel gauge
- **PCB:** 65mm x 108mm, 2-layer FR4 (JLCPCB)

## Features

- Dual-tube radiation measurement (CPM, CPS, µSv/h)
- 240x320 capacitive touchscreen (portrait mode)
- Real-time dose rate graph (4-hour history)
- Buzzer click on each count, WS2812 RGB LED flash
- Vibration motor alarm on dose threshold
- WiFi AP mode with web dashboard and REST API
- MicroSD data logging (CSV)
- USB-C charging (1A) + native USB programming
- Zero GPIO pin conflicts (every function on a dedicated pin)

## Firmware

Built with [PlatformIO](https://platformio.org/) (Arduino framework, ESP32-S3).

```
cd firmware
pio run
pio run -t upload
```

Programming uses the ESP32-S3's native USB — no external USB-UART chip needed. Just plug in USB-C and upload.

### Web API

Connect to the DecayDeck WiFi AP (`DecayDeck` / `geiger20`), open `http://192.168.4.1` for a live dashboard, or hit `/api/data` for JSON:

```json
{
  "usvh": 0.14,
  "cpm1": 22,
  "cpm2": 15,
  "cps": 0.6,
  "hv": 401,
  "bat": 87,
  "totalDose": 0.42,
  "uptime": "2h 15m"
}
```

## Project Structure

```
firmware/                     PlatformIO project
  src/main.cpp                Main firmware
  include/config.h            Configuration constants
  include/pins.h              GPIO pin mapping (zero conflicts)
hardware/                     EasyEDA Pro design files
  schematic-guide.md          Complete component list + wiring
  pcb-design-notes.txt        Board layout reference
  component-placement.txt     Component coordinates
docs/                         Documentation
  assembly.md                 Build instructions, HV safety, calibration
  pinout.md                   GPIO map, connector pinouts, I2C addresses
```

## Docs

- [Schematic Guide](hardware/schematic-guide.md) — complete BOM and wiring reference
- [Assembly Guide](docs/assembly.md) — build instructions, HV safety, calibration
- [Pinout Reference](docs/pinout.md) — ESP32-S3 GPIO map, connector pinouts, I2C addresses

## Safety

The HV section generates ~400V DC. Current is extremely low (microamps), but:
- Do not touch HV components while powered on
- HV capacitors may retain charge briefly after power off
- PCB has ground pour isolation gap around HV zone
- See the [Assembly Guide](docs/assembly.md) for calibration and handling

## License

[MIT](LICENSE)
