---
layout: default
title: Relay Drone Build (Drone 2)
---

# Relay Drone Build (Drone 2)

This guide covers setting up the relay drone using dual Heltec WiFi LoRa 32 V3 devices. The relay enables communication when the direct link between Drone 1 and the Ground Station is jammed or out of range.

## Architecture Overview

Drone 2 uses two Heltec devices connected via UART to bridge different frequencies:

```
                      ┌─────────────────────────────────────────────┐
                      │               DRONE 2 (RELAY)               │
                      │                                             │
  From Drone 1        │  ┌──────────────┐      ┌──────────────┐     │   To Ground 902
  LoRa 930 MHz        │  │   PRIMARY    │ UART │  SECONDARY   │     │   LoRa 902 MHz
 ◄───────────────────►│  │  (930 MHz)   │◄────►│  (902 MHz)   │     │◄───────────────────►
                      │  │              │      │              │     │
                      │  └──────────────┘      └──────────────┘     │
                      │                                             │
                      └─────────────────────────────────────────────┘
```

## Hardware Requirements

| Component | Quantity | Notes |
|-----------|----------|-------|
| Heltec WiFi LoRa 32 V3 | 2 | One Primary, one Secondary |
| Jumper Wires | 3 | TX, RX, GND |
| Power Supply | 1-2 | 5V for each device |

## UART Interconnection

The Primary and Secondary devices communicate over UART:

### Primary → Secondary Wiring

| Primary (930 MHz) | Secondary (902 MHz) | Notes |
|-------------------|---------------------|-------|
| GPIO 45 (TX) | GPIO 46 (RX) | Relay data |
| GPIO 46 (RX) | GPIO 45 (TX) | Relay data |
| GND | GND | Common ground |

```cpp
// In drone2_primary.cpp
#define RELAY_TX_PIN     45  // To Secondary RX
#define RELAY_RX_PIN     46  // From Secondary TX
#define RELAY_BAUD       115200
```

## Firmware Environments

### Primary (930 MHz)

Receives messages from Drone 1 on 930 MHz and forwards via UART to Secondary:

```ini
[env:drone2_primary]
build_flags =
    -DAERO_DRONE
    -DNODE_ID=2
    -DFREQ_PRIMARY=930.0
    -DENABLE_RELAY
    -DALWAYS_RELAY_MODE
    -DRELAY_DEBUG
```

### Secondary (902 MHz)

Receives messages from Primary via UART and transmits to Ground Station 902:

```ini
[env:drone2_secondary]
build_flags =
    -DAERO_DRONE
    -DNODE_ID=3
    -DFREQ_PRIMARY=902
    -DENABLE_RELAY
    -DALWAYS_RELAY_MODE
    -DRELAY_DEBUG
```

## Build Flags Explained

| Flag | Description |
|------|-------------|
| `ENABLE_RELAY` | Activates relay functionality |
| `ALWAYS_RELAY_MODE` | Relay always active (bypasses passive detection) |
| `RELAY_DEBUG` | Enables verbose relay logging |
| `NODE_ID=2` | Primary relay node identifier |
| `NODE_ID=3` | Secondary relay node identifier |

## Flashing Procedure

### 1. Flash Primary Device

```bash
# Connect Primary Heltec via USB
pio run -e drone2_primary -t upload
```

Display shows: `RELAY PRIMARY` then `READY!`

### 2. Flash Secondary Device

```bash
# Connect Secondary Heltec via USB
pio run -e drone2_secondary -t upload
```

Display shows: `RELAY SECONDARY` then `READY!`

### 3. Connect Devices via UART

Wire the UART connection as described above, then power both devices.

## Operation Modes

### Always Relay Mode (Default)

With `ALWAYS_RELAY_MODE` defined, the relay is always active. This is useful for testing and demonstrations.

### Passive Detection Mode (Future)

When `ALWAYS_RELAY_MODE` is not defined, the relay only activates when:
- Ground station indicates it's receiving with poor RSSI
- Drone 1 indicates it's receiving with poor RSSI
- Link quality falls below threshold

## Signal Flow

```
1. Drone 1 transmits on 930 MHz
     │
     ▼
2. Drone 2 Primary receives (930 MHz)
     │
     ▼  (UART)
3. Drone 2 Secondary receives
     │
     ▼
4. Drone 2 Secondary transmits on 902 MHz
     │
     ▼
5. Ground Station 902 receives
```

## Debugging

Monitor relay activity via USB Serial:

```bash
# Connect to Primary
pio device monitor -e drone2_primary

# Connect to Secondary (different terminal)
pio device monitor -e drone2_secondary
```

Look for messages like:
```
[RELAY] Forwarding packet to Secondary via UART
[RELAY] Received from Primary, transmitting on 902 MHz
```

---

[← Target Drone Build](drone-build) | [Next: Ground Station →](ground-station)
