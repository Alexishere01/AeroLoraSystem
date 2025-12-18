---
layout: default
title: Relay Architecture
---

# Asymmetric Relay Architecture

The AeroLoRa relay system uses an asymmetric design with dual frequencies to provide jamming resilience.

## System Overview

```
                         NORMAL OPERATION
┌─────────────┐       LoRa 930 MHz      ┌─────────────┐
│   Ground    │◄───────────────────────►│   Drone 1   │
│   Station   │                         │   (Target)  │
└─────────────┘                         └─────────────┘
                           │
                           │ If jammed...
                           ▼
                      RELAY ACTIVATED
┌─────────────┐       LoRa 930 MHz      ┌─────────────┐
│   Ground    │          ╳ JAMMED       │   Drone 1   │
│   Station   │                         │   (Target)  │
└─────────────┘                         └──────┬──────┘
                                               │
      ┌─────────────┐     LoRa 930 MHz        │
      │  Ground 902 │◄─────────────────┐      │
      │   (Backup)  │                  │      │
      └─────────────┘                  │      │
             ▲                         │      │
             │            ┌────────────┴──────┴──────┐
             │            │        DRONE 2           │
             │  LoRa      │  ┌──────────┐  ┌──────┐  │
             │  902 MHz   │  │ Primary  │──│Second│  │
             └────────────┤  │ (930MHz) │  │(902) │  │
                          │  └──────────┘  └──────┘  │
                          │       UART connection    │
                          └──────────────────────────┘
```

## Why Asymmetric?

**Symmetric relay** (same frequency): Drone 2 would jam itself when transmitting while Drone 1 is transmitting.

**Asymmetric relay** (different frequencies):
- Primary radio (930 MHz) listens to Drone 1
- Secondary radio (902 MHz) transmits to Ground 902
- No self-interference

## Components

### Drone 2 Primary (930 MHz)

- Receives packets from Drone 1 on 930 MHz
- Forwards to Secondary via UART
- Build environment: `drone2_primary`

```cpp
// Key configuration
#define NODE_ID 2
#define FREQ_PRIMARY 930.0
#define ENABLE_RELAY
```

### Drone 2 Secondary (902 MHz)

- Receives from Primary via UART
- Transmits to Ground 902 on 902 MHz
- Build environment: `drone2_secondary`

```cpp
// Key configuration
#define NODE_ID 3
#define FREQ_PRIMARY 902
#define ENABLE_RELAY
```

### Ground 902 (Backup)

- Receives relayed packets on 902 MHz
- Forwards to QGC (can be connected in parallel)
- Build environment: `qgc_radio2_902mhz`

## Relay Activation

### Always-On Mode (Testing)

With `ALWAYS_RELAY_MODE` defined, relay is always active:

```cpp
#define ALWAYS_RELAY_MODE  // Relay always on
```

This is useful for:
- Testing relay functionality
- Demonstrations
- Scenarios where jamming is expected

### Passive Detection Mode (Future)

When `ALWAYS_RELAY_MODE` is not defined, relay activates based on link quality:

```cpp
void checkLinkQuality() {
    if (avg_rssi < -100.0) {
        // Weak link - activate relay request
        relayRequestActive = true;
    } else if (avg_rssi > -90.0) {
        // Good link - deactivate relay
        relayRequestActive = false;
    }
    // Hysteresis between -100 and -90 dBm
}
```

### Relay Request Flag

Packets can include a relay request flag:

```cpp
// Header byte with relay request
#define RELAY_REQUEST_FLAG 0x80
#define HEADER_WITH_RELAY  (0xAE | RELAY_REQUEST_FLAG)  // 0x2E
```

## Data Flow

### Normal (Direct Link)

```
Drone 1 ───LoRa 930───► Ground → QGC
```

### Relay (Jammed Primary)

```
Drone 1 ───LoRa 930───► Drone 2 Primary
                              │ UART
                              ▼
                        Drone 2 Secondary ───LoRa 902───► Ground 902 → QGC
```

## UART Protocol

Primary and Secondary communicate via UART at 115200 baud:

```cpp
// In drone2_primary.cpp and drone2_secondary.cpp
#define RELAY_BAUD 115200
```

The UART carries the raw MAVLink packets (no additional framing needed).

## Latency Impact

| Path | Estimated Latency |
|------|-------------------|
| Direct (Drone 1 → Ground) | ~50ms |
| Relay (Drone 1 → Drone 2 → Ground 902) | ~100-150ms |

The additional latency comes from:
- Second radio hop
- UART transfer between Primary and Secondary
- Processing overhead

## Future Improvements

1. **Bidirectional relay**: Currently relay is unidirectional (drone → ground)
2. **Dynamic activation**: Based on RSSI thresholds
3. **ESP-NOW relay**: Use 2.4 GHz as alternate relay path
4. **Multiple relay nodes**: Mesh network capability

---

[← Priority Queues](priority-queues) | [Next: Web Dashboard →](../testing/web-dashboard)
