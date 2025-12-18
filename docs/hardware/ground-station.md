---
layout: default
title: Ground Station Setup
---

# Ground Station Setup

This guide covers setting up the ground station that connects to QGroundControl.

## Overview

The ground station bridges MAVLink between your computer (QGC) and the drone(s) over LoRa. For the full relay configuration, you'll need two ground stations on different frequencies.

```
┌──────────────┐     USB Serial     ┌──────────────┐     LoRa 930 MHz
│    QGC       │◄──────────────────►│   Ground     │◄───────────────────►  Drone 1
│  (Computer)  │     57600 baud     │   Station    │
└──────────────┘                    └──────────────┘
                                           │
                                           │ ESP-NOW 2.4 GHz (backup)
                                           ▼
                                      Drone 1
```

## Hardware Requirements

### Single Ground Station
| Component | Quantity |
|-----------|----------|
| Heltec WiFi LoRa 32 V3 | 1 |
| USB-C Cable | 1 |

### Dual Ground Station (with Relay)
| Component | Quantity |
|-----------|----------|
| Heltec WiFi LoRa 32 V3 | 2 |
| USB-C Cables | 2 |

## Firmware Environments

### Standard Ground Station (930 MHz)

```ini
[env:aero_ground]
build_flags =
    -DAERO_GROUND
    -DFREQ_PRIMARY=930.0
    -DENABLE_FLIGHT_LOGGER
```

### Relay Receiver (902 MHz)

For receiving relayed packets from Drone 2:

```ini
[env:qgc_radio2_902mhz]
build_flags =
    -DAERO_GROUND
    -DFREQ_PRIMARY=902
    -DFREQ_902MHZ_MODE
    -DENABLE_FLIGHT_LOGGER
```

## Flashing

```bash
# Standard Ground Station
pio run -e aero_ground -t upload

# Relay Receiver Ground Station
pio run -e qgc_radio2_902mhz -t upload
```

## QGroundControl Configuration

### Serial Connection Settings

1. Open QGroundControl
2. Navigate to **Application Settings** → **Comm Links**
3. Click **Add** to create new link
4. Configure:

| Setting | Value |
|---------|-------|
| Type | Serial |
| Port | `/dev/ttyUSB0` (Linux) or `COMx` (Windows) |
| Baud Rate | 57600 |
| Data Bits | 8 |
| Stop Bits | 1 |
| Parity | None |
| Flow Control | None |

### Auto-Connect

Enable auto-connect for convenience:
- Check "Automatically Connect on Start"

## MAC Address Configuration

The ground station needs to know the drone's ESP-NOW MAC address. This is configured at compile time:

```cpp
// In aero_lora_ground.cpp
uint8_t drone_mac[6] = {0x48, 0xCA, 0x43, 0x3A, 0xEF, 0x04};  // Drone1 actual MAC
```

### Finding Your Drone's MAC Address

Flash the `get_mac` utility to find your device's MAC:

```bash
pio run -e get_mac -t upload
pio device monitor
```

Output:
```
ESP32 MAC Address: 48:CA:43:3A:EF:04
```

## OLED Display Information

The ground station display shows:

| Line | Information |
|------|-------------|
| 1 | ESP-NOW DEBUG |
| 2 | Peer MAC (last 3 bytes) |
| 3 | WiFi Channel |
| 4 | Connection Status + RSSI |
| 5 | TX/RX Packet Counts |

## Flight Logging

With `ENABLE_FLIGHT_LOGGER` enabled, logs are saved to:
- `/ground_log.csv` on the device's LittleFS

### Downloading Logs

Use the serial commands:
- Type `DUMP` → Outputs log contents to serial
- Type `CLEAR` → Clears the log file

Or use the provided Python script:
```bash
python download_flight_logs.py --port /dev/ttyUSB0
```

## Troubleshooting

### No Connection to Drone
1. Verify both devices are powered
2. Check frequency match (both on 930 MHz)
3. Verify antennas are connected
4. Check serial baud rate (57600)

### ESP-NOW "OUT OF RANGE"
1. ESP-NOW range is ~50m
2. Check MAC address matches drone
3. Verify WiFi channel (should be 1)

### Poor LoRa Signal
1. Increase TX power in `platformio.ini`
2. Use external antenna
3. Clear line of sight to drone

---

[← Relay Drone Build](relay-drone-build) | [Next: PlatformIO Guide →](../configuration/platformio-guide)
