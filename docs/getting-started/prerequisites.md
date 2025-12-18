---
layout: default
title: Prerequisites
---

# Prerequisites

Before building the AeroLoRa Relay System, ensure you have the following hardware and software.

## Hardware Requirements

### Required Components

| Component | Quantity | Notes |
|-----------|----------|-------|
| **Heltec WiFi LoRa 32 V3** | 2-4 | ESP32-S3 with SX1262 LoRa radio |
| **USB-C Cables** | 1 per device | For programming and power |
| **ArduPilot Flight Controller** | 1 | Tested with Pixhawk, CubeOrange |
| **JST-GH Cable** | 1 | For UART connection to FC |

### Minimum Configuration (2 Nodes)
- 1x Ground Station Heltec
- 1x Drone Heltec

### Full Relay Configuration (4 Nodes)
- 1x Ground Station 930 MHz (direct link)
- 1x Ground Station 902 MHz (relay receiver)
- 1x Drone 1 (target drone)
- 2x Drone 2 Heltecs (relay node - Primary + Secondary)

## Software Requirements

### Development Tools

| Software | Version | Download |
|----------|---------|----------|
| **VS Code** | Latest | [Download](https://code.visualstudio.com/) |
| **PlatformIO IDE** | Latest | Install via VS Code Extensions |
| **Git** | 2.x+ | [Download](https://git-scm.com/) |
| **Python 3** | 3.8+ | For flight replay tools |

### Ground Control Software

| Software | Version | Notes |
|----------|---------|-------|
| **QGroundControl** | 4.0+ | [Download](https://qgroundcontrol.com/) |
| **Serial Port Driver** | - | Usually auto-installed |

### Browser Requirements (for Web Dashboard)

| Browser | Version | WebSerial Support |
|---------|---------|-------------------|
| Chrome | 89+ | ✅ Full support |
| Edge | 89+ | ✅ Full support |
| Firefox | - | ❌ Not supported |
| Safari | - | ❌ Not supported |

## Knowledge Prerequisites

This project assumes familiarity with:

- **Arduino/ESP32 development** - Basic C++ and PlatformIO
- **Drone systems** - MAVLink protocol, ArduPilot configuration
- **Radio fundamentals** - Frequency, RSSI, modulation basics
- **Git version control** - Clone, checkout, commit

## Antenna Considerations

> ⚠️ **Important**: Never power on the LoRa radio without an antenna connected! This can damage the SX1262 chip.

The Heltec V3 includes an onboard antenna suitable for testing. For extended range:

- Use external 915 MHz antennas (SMA connector)
- Ensure antenna is tuned for your operating frequency (902/930 MHz)
- Consider directional antennas for ground station

---

[← Back to Home](/) | [Next: Quick Start →](quick-start)
