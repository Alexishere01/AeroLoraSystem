# AeroLoRa System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PlatformIO](https://img.shields.io/badge/PlatformIO-ESP32-orange.svg)](https://platformio.org/)

A robust, long-range drone telemetry system using LoRa radio with anti-jamming relay capabilities. Developed as a Senior Design project to demonstrate resilient communication under RF interference conditions.

## 🌟 Key Features

- **Dual-Band Transport**: Simultaneous ESP-NOW (2.4 GHz) and LoRa (900 MHz) communication
- **Anti-Jamming Relay**: Secondary drone acts as relay when primary link is jammed
- **Three-Tier Priority Queue**: Critical commands (ARM/DISARM) always get priority
- **Hardware CRC**: SX1262 radio chip handles error detection automatically
- **Web-Based Dashboard**: Real-time monitoring via WebSerial API
- **Flight Logging**: On-device logging to LittleFS with CSV export

## 📡 System Architecture

```
                              NORMAL OPERATION
    ┌────────────┐        LoRa 930 MHz        ┌────────────┐
    │   Ground   │◄──────────────────────────►│  Drone 1   │
    │   Station  │                            │  (Target)  │
    │    (QGC)   │◄─── ESP-NOW 2.4 GHz ──────►│            │
    └────────────┘                            └────────────┘

                              IF JAMMED (Relay Activated)
    ┌────────────┐        LoRa 902 MHz        ┌────────────┐        LoRa 930 MHz
    │  Ground    │◄──────────────────────────►│  Drone 2   │◄──────────────────────►  Drone 1
    │    902     │                            │  (Relay)   │
    └────────────┘                            └────────────┘
```

## 🛠️ Hardware Requirements

| Component | Model | Quantity |
|-----------|-------|----------|
| Microcontroller | Heltec WiFi LoRa 32 V3 | 2-4 |
| Flight Controller | ArduPilot-compatible | 1 |
| USB Cable | USB-C | 1 per device |

## 🚀 Quick Start

```bash
# Clone the repository
git clone git@github.com:Alexishere01/AeroLoraSystem.git
cd AeroLoraSystem

# Flash ground station
pio run -e aero_ground -t upload

# Flash drone
pio run -e drone1 -t upload
```

Connect the ground station to QGroundControl via USB at 57600 baud.

## 📚 Documentation

Full documentation is available at: **[GitHub Pages](https://alexishere01.github.io/AeroLoraSystem/)**

- [Prerequisites](docs/getting-started/prerequisites.md)
- [Quick Start Guide](docs/getting-started/quick-start.md)
- [Hardware Build Guides](docs/hardware/drone-build.md)
- [Protocol Documentation](docs/protocol/aerolora-overview.md)

## 📁 Project Structure

```
├── src/                      # Source files
│   ├── aero_lora_drone.cpp   # Drone firmware
│   ├── aero_lora_ground.cpp  # Ground station firmware
│   ├── drone2_primary.cpp    # Relay coordinator
│   ├── drone2_secondary.cpp  # Relay bridge
│   └── AeroLoRaProtocol.cpp  # Protocol implementation
├── include/                  # Header files
│   ├── AeroLoRaProtocol.h    # Protocol definitions
│   └── DualBandTransport.h   # Transport layer
├── docs/                     # GitHub Pages documentation
├── flight_replay/            # Analysis tools
│   └── webserial_dashboard/  # Web-based monitor
└── platformio.ini            # Build configuration
```

## 🔧 Build Environments

| Environment | Purpose |
|-------------|---------|
| `aero_ground` | Standard ground station (930 MHz) |
| `drone1` | Target drone (930 MHz) |
| `drone2_primary` | Relay coordinator (930 MHz) |
| `drone2_secondary` | Relay bridge (902 MHz) |
| `qgc_radio2_902mhz` | Backup ground station (902 MHz) |

## 📊 Protocol Highlights

- **Minimal overhead**: Only 4 bytes per packet
- **Priority queuing**: 3 tiers with automatic staleness detection
- **Message filtering**: Blacklist high-frequency messages unsuitable for LoRa
- **Rate limiting**: Prevents queue flooding from telemetry streams

## 🔬 Technologies Used

- **ESP32-S3** (Heltec WiFi LoRa 32 V3)
- **SX1262** LoRa transceiver
- **ESP-NOW** for 2.4 GHz backup link
- **MAVLink** protocol for drone communication
- **PlatformIO** build system
- **RadioLib** LoRa library

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

This project was developed as a Senior Design project. Special thanks to:
- Faculty advisors for their guidance
- The ArduPilot and MAVLink communities
- RadioLib and PlatformIO maintainers

---

**[📖 Read the Full Documentation](https://alexishere01.github.io/AeroLoraSystem/)**
