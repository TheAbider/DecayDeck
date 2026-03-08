# DecayDeck GC-20 v2

Open-source handheld Geiger counter with dual GM tubes, touchscreen display, WiFi, and LiPo battery.

## Hardware

- **MCU:** ESP8266 (Wemos D1 Mini)
- **Display:** Adafruit 2090 (2.8" ILI9341 TFT + FT6206 capacitive touch)
- **GM Tubes:** STS-5 (gamma) + SI-3BG (beta+gamma)
- **HV Supply:** 555-based boost converter (~400V DC)
- **Power:** Single-cell 3.7V LiPo (103450, ~1800mAh) with TP4056 USB-C charging
- **Battery Monitoring:** MAX17048 fuel gauge + INA219 current monitor
- **PCB:** 65mm x 108mm, 2-layer FR4 (JLCPCB)

## Features

- Dual-tube radiation measurement (CPM, CPS, µSv/h)
- 240x320 TFT with touch navigation
- Real-time dose rate graph (4-hour history)
- Buzzer click on each count, WS2812 LED flash
- Vibration motor alarm on dose threshold
- WiFi AP mode with web dashboard and REST API
- MicroSD data logging (CSV)
- USB-C charging with battery level display

## Firmware

Built with [PlatformIO](https://platformio.org/) (Arduino framework).

```
cd firmware
pio run
pio run -t upload
```

### Web API

When connected to the DecayDeck WiFi AP (`DecayDeck` / `geiger20`), open `http://192.168.4.1` for a live dashboard, or hit `/api/data` for JSON:

```json
{
  "cpm1": 22,
  "cpm2": 15,
  "cpmTotal": 37,
  "usvh": 0.14,
  "cps": 0,
  "bat_pct": 87.5,
  "bat_mv": 3850,
  "hv_mv": 401
}
```

## Project Structure

```
firmware/           PlatformIO project
  src/main.cpp      Main firmware
  include/config.h  Configuration constants
  include/pins.h    GPIO pin mapping
hardware/           EasyEDA Pro design files + notes
docs/               Assembly guide, pinout reference
```

## Docs

- [Assembly Guide](docs/assembly.md) — build instructions, HV safety, calibration
- [Pinout Reference](docs/pinout.md) — ESP8266 GPIO map, connector pinouts, I2C addresses

## Safety

The HV section generates ~400V DC. Current is extremely low (microamps), but:
- Do not touch HV components while powered on
- HV capacitors may retain charge briefly after power off
- See the [Assembly Guide](docs/assembly.md) for calibration and handling

## License

[MIT](LICENSE)
