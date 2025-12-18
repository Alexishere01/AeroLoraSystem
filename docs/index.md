---
layout: default
title: AeroLoRa Relay System
---

# AeroLoRa Relay System

A robust, long-range drone telemetry system using LoRa radio with anti-jamming relay capabilities. This senior design project implements a dual-band communication architecture that maintains MAVLink connectivity even under RF interference conditions.

![Architecture Overview](assets/architecture.png)

## Key Features

- **Dual-Band Transport**: Simultaneous ESP-NOW (2.4 GHz) and LoRa (900 MHz) communication
- **Anti-Jamming Relay**: Secondary drone acts as relay when primary link is jammed
- **Three-Tier Priority Queue**: Critical commands (ARM/DISARM) always get priority
- **Hardware CRC**: SX1262 radio chip handles error detection automatically
- **Web-Based Dashboard**: Real-time monitoring via WebSerial API
- **Flight Logging**: On-device logging to LittleFS with CSV export

## System Architecture

```
┌─────────────────┐     LoRa 930 MHz      ┌─────────────────┐
│   Ground        │◄────────────────────► │   Drone 1       │
│   Station       │                       │   (Target)      │
│   (QGC)         │                       │                 │
│                 │◄── ESP-NOW 2.4 GHz ─► │                 │
└─────────────────┘                       └─────────────────┘
        │                                         │
        │          If jammed, failover:           │
        ▼                                         ▼
┌─────────────────┐     LoRa 930 MHz      ┌─────────────────┐
│   Ground 902    │◄────────────────────► │   Drone 2       │
│   (Backup RX)   │                       │   (Relay)       │
└─────────────────┘     LoRa 902 MHz      └─────────────────┘
```

## Hardware Requirements

| Component | Model | Quantity |
|-----------|-------|----------|
| Microcontroller | Heltec WiFi LoRa 32 V3 | 3-4 |
| Flight Controller | ArduPilot-compatible | 1 |
| USB Cable | USB-C | 1 per device |

## Quick Links

- [Getting Started](getting-started/prerequisites)
- [Hardware Build Guides](hardware/drone-build)
- [Configuration](configuration/platformio-guide)
- [Protocol Documentation](protocol/aerolora-overview)

## Documentation Sections

### 🚀 Getting Started
- [Prerequisites](getting-started/prerequisites) - Hardware and software requirements
- [Quick Start](getting-started/quick-start) - Get up and running in 10 minutes

### 🔧 Hardware Guides
- [Target Drone Build (Drone 1)](hardware/drone-build) - Single Heltec drone setup
- [Relay Drone Build (Drone 2)](hardware/relay-drone-build) - Dual Heltec relay node
- [Ground Station Setup](hardware/ground-station) - QGroundControl integration

### ⚙️ Configuration
- [PlatformIO Guide](configuration/platformio-guide) - Build environments explained
- [Frequency Setup](configuration/frequency-setup) - Radio frequency allocation
- [Firmware Flashing](configuration/firmware-flashing) - How to flash devices

### 📡 Protocol
- [AeroLoRa Overview](protocol/aerolora-overview) - Protocol design philosophy
- [Priority Queues](protocol/priority-queues) - Three-tier queue system
- [Relay Architecture](protocol/relay-architecture) - Asymmetric relay design

### 🧪 Testing & Tools
- [Web Dashboard](testing/web-dashboard) - Real-time monitoring tool

## License

This project is open source under the MIT License.

## Acknowledgments

This project was developed as a Senior Design project at [Your University]. Special thanks to the faculty advisors and team members who contributed to this work.
