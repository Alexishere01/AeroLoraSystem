---
layout: default
title: Target Drone Build (Drone 1)
---

# Target Drone Build (Drone 1)

This guide covers setting up the primary target drone with a single Heltec WiFi LoRa 32 V3.

## Overview

Drone 1 is the main aircraft that communicates with the ground station. It bridges the flight controller's MAVLink telemetry to the AeroLoRa radio system.

```
┌──────────────┐      UART        ┌──────────────┐
│   ArduPilot  │◄────────────────►│   Heltec V3  │
│   Flight     │   TX8/RX8        │   (Drone 1)  │
│   Controller │   115200 baud    │              │
└──────────────┘                  └──────────────┘
                                         │
                                         │ LoRa 930 MHz
                                         ▼
                                  ┌──────────────┐
                                  │   Ground     │
                                  │   Station    │
                                  └──────────────┘
```

## Hardware Connections

### Pin Mapping

| Heltec V3 Pin | Connect To | Notes |
|---------------|------------|-------|
| GPIO 45 (TX) | FC RX8 | Telemetry transmit |
| GPIO 46 (RX) | FC TX8 | Telemetry receive |
| GND | FC GND | Common ground |
| 5V (opt) | FC 5V | Or use USB power |

### UART Configuration

The default UART baud rate is 115200. This must match your flight controller's serial port configuration.

```cpp
// In aero_lora_drone.cpp
#define FC_TX            45  // GPIO45 - connects to FC RX8
#define FC_RX            46  // GPIO46 - connects to FC TX8
#define FC_BAUD          115200
```

## Flight Controller Setup

### ArduPilot Configuration

Configure SERIAL8 (or your chosen port) for MAVLink:

```
SERIAL8_PROTOCOL = 2  (MAVLink2)
SERIAL8_BAUD = 111    (115200 baud)
```

### Telemetry Streams

The AeroLoRa protocol automatically prioritizes messages:

| Stream | Messages | Recommended Rate |
|--------|----------|------------------|
| SR8_RAW_SENS | Sensors | 0 (disabled) |
| SR8_POSITION | GPS, Attitude | 2 Hz |
| SR8_EXT_STAT | Battery, Status | 1 Hz |
| SR8_RC_CHAN | RC Inputs | 0 (disabled) |
| SR8_EXTRA1 | Attitude | 2 Hz |
| SR8_EXTRA2 | VFR_HUD | 1 Hz |
| SR8_EXTRA3 | AHRS | 0 (disabled) |

## Firmware Environment

Build using the `drone1` PlatformIO environment:

```ini
[env:drone1]
build_flags =
    -DAERO_DRONE
    -DNODE_ID=1
    -DFREQ_PRIMARY=930.0
    -DENABLE_FLIGHT_LOGGER
```

### Key Build Flags

| Flag | Description |
|------|-------------|
| `AERO_DRONE` | Enables drone-specific code paths |
| `NODE_ID=1` | Unique identifier for this node |
| `FREQ_PRIMARY=930.0` | Operating frequency in MHz |
| `ENABLE_FLIGHT_LOGGER` | Enables on-board logging to LittleFS |

## Jammer Test Mode

For testing jamming resilience, use the `drone1_no_espnow` environment which disables the 2.4 GHz ESP-NOW fallback:

```ini
[env:drone1_no_espnow]
build_flags =
    -DAERO_DRONE
    -DNODE_ID=1
    -DFREQ_PRIMARY=930.0
    -DDISABLE_ESPNOW  # ESP-NOW disabled!
```

## Physical Installation

### Mounting Guidelines

1. **Antenna orientation**: Keep LoRa antenna vertical for best omnidirectional pattern
2. **Separation**: Mount Heltec at least 5cm from GPS antenna
3. **Vibration isolation**: Use foam mounting to reduce vibration
4. **Cable routing**: Keep UART cable short and away from power wires

### Power Options

| Power Source | Voltage | Notes |
|--------------|---------|-------|
| FC 5V rail | 5V | Cleanest option |
| BEC | 5V | Ensure isolated from motors |
| USB powerbank | 5V | For bench testing only |

---

[← Quick Start](../getting-started/quick-start) | [Next: Relay Drone Build →](relay-drone-build)
