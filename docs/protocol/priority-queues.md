---
layout: default
title: Priority Queue System
---

# Three-Tier Priority Queue System

AeroLoRa implements a three-tier priority queue to ensure critical commands are never blocked by routine telemetry.

## Queue Overview

| Tier | Name | Size | Timeout | Purpose |
|------|------|------|---------|---------|
| 0 | Critical | 10 slots | 1 second | Commands only (ARM, DISARM, SET_MODE) |
| 1 | Important | 20 slots | 2 seconds | HEARTBEAT + essential telemetry |
| 2 | Routine | 30 slots | 5 seconds | Everything else |

**Total memory**: 60 slots × 256 bytes = 15,360 bytes (under 20KB ESP32 limit)

## Message Classification

### Tier 0: Critical Commands (1s timeout)

These messages require immediate delivery for responsive drone control:

| Message ID | Name | Description |
|------------|------|-------------|
| 76 | COMMAND_LONG | ARM, DISARM, takeoff, land |
| 11 | SET_MODE | Flight mode changes |
| 176 | DO_SET_MODE | Mission command mode change |
| 23 | PARAM_SET | Parameter changes |
| 39 | MISSION_ITEM | Waypoint upload |
| 44 | MISSION_COUNT | Mission upload initiation |

### Tier 1: Important Telemetry (2s timeout)

Essential for situational awareness:

| Message ID | Name | Description |
|------------|------|-------------|
| 0 | HEARTBEAT | System status (1 Hz) |
| 24 | GPS_RAW_INT | GPS position and fix status |
| 30 | ATTITUDE | Roll, pitch, yaw |
| 33 | GLOBAL_POSITION_INT | Global position estimate |

### Tier 2: Routine Telemetry (5s timeout)

Nice-to-have information that can tolerate delay:

- Battery status
- System status text
- Parameter values
- Sensor data
- All other messages

## How Processing Works

```cpp
void process() {
    // 1. Check Tier 0 first (critical commands)
    if (!isTier0Empty()) {
        packet = dequeue_tier0();
        if (!isStale(packet, 1000)) {  // 1s timeout
            transmit(packet);
            return;
        }
        // Stale - drop and try next
    }
    
    // 2. Check Tier 1 (important telemetry)
    if (!isTier1Empty()) {
        packet = dequeue_tier1();
        if (!isStale(packet, 2000)) {  // 2s timeout
            transmit(packet);
            return;
        }
    }
    
    // 3. Check Tier 2 (routine)
    if (!isTier2Empty()) {
        packet = dequeue_tier2();
        if (!isStale(packet, 5000)) {  // 5s timeout
            transmit(packet);
            return;
        }
    }
}
```

## Staleness Detection

Packets that exceed their tier's timeout are dropped automatically:

```
┌─────────────────────────────────────────────────────────────────┐
│                        TIME                                     │
├─────────────────────────────────────────────────────────────────┤
│ 0s              1s              2s              5s              │
│ │               │               │               │               │
│ ├───────────────┤ Tier 0 valid  │               │               │
│ │               ├───────────────┤ Tier 1 valid  │               │
│ │               │               ├───────────────┤ Tier 2 valid  │
└─────────────────────────────────────────────────────────────────┘
```

**Why drop stale packets?**
- Old commands are dangerous (late ARM command)
- Old telemetry is misleading (GPS from 10 seconds ago)
- Frees queue space for fresh data

## Queue Metrics

The protocol tracks queue health:

```cpp
struct QueueMetrics {
    uint8_t tier0_depth;      // Current packets in Tier 0
    uint8_t tier1_depth;      // Current packets in Tier 1
    uint8_t tier2_depth;      // Current packets in Tier 2
    
    uint32_t tier0_drops_full;    // Dropped (queue full)
    uint32_t tier0_drops_stale;   // Dropped (too old)
    // ... same for tier1 and tier2
};
```

## Configuration

Queue sizes and timeouts are compile-time constants:

```cpp
// In AeroLoRaProtocol.h
#define AEROLORA_TIER0_SIZE      10     // Critical commands
#define AEROLORA_TIER1_SIZE      20     // Important telemetry
#define AEROLORA_TIER2_SIZE      30     // Routine telemetry

#define AEROLORA_TIER0_TIMEOUT   1000   // 1 second
#define AEROLORA_TIER1_TIMEOUT   2000   // 2 seconds
#define AEROLORA_TIER2_TIMEOUT   5000   // 5 seconds
```

### Static Validation

The code includes compile-time checks:

```cpp
// Verify memory usage
static_assert((TIER0_SIZE + TIER1_SIZE + TIER2_SIZE) * 256 < 20480,
    "Total queue memory exceeds 20KB limit");

// Verify timeout ordering
static_assert(TIER0_TIMEOUT <= TIER1_TIMEOUT,
    "Critical timeout must be <= Important timeout");
```

---

[← AeroLoRa Overview](aerolora-overview) | [Next: Relay Architecture →](relay-architecture)
