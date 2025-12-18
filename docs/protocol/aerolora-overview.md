---
layout: default
title: AeroLoRa Protocol Overview
---

# AeroLoRa Protocol Overview

AeroLoRa is a lightweight transport protocol designed specifically for MAVLink communication over LoRa radio.

## Design Philosophy

The protocol follows these core principles:

| Principle | Implementation |
|-----------|----------------|
| **Minimal overhead** | Only 4 bytes per packet (header + src + dest + length) |
| **Hardware reliability** | SX1262 radio handles CRC, no software CRC needed |
| **MAVLink handles retries** | No ACK/NACK mechanism - MAVLink already has this |
| **Priority-based** | Critical commands never blocked by telemetry |

## Packet Structure

```
┌─────────┬─────────┬─────────┬─────────┬────────────────────┐
│ Header  │ Src ID  │ Dest ID │ Length  │      Payload       │
│ (1 byte)│ (1 byte)│ (1 byte)│ (1 byte)│   (0-250 bytes)    │
└─────────┴─────────┴─────────┴─────────┴────────────────────┘
     0xAE      0-3       0-3      N         MAVLink data
```

### Header Byte

| Value | Meaning |
|-------|---------|
| 0xAE | Standard AeroLoRa packet |
| 0x2E | Packet with relay request flag (0xAE \| 0x80) |

### Node IDs

| ID | Node |
|----|------|
| 0 | Ground Station |
| 1 | Drone 1 (Target) |
| 2 | Drone 2 Primary |
| 3 | Drone 2 Secondary |
| 0xFF | Broadcast (all nodes) |

## Hardware CRC

The SX1262 LoRa radio provides hardware CRC:

- **On TX**: Radio calculates and appends CRC automatically
- **On RX**: Radio validates CRC, only interrupts if valid
- **Application layer**: Never sees packets with bad CRC

```cpp
// Enable hardware CRC during initialization
radio.setCRC(true);
```

## Comparison with Previous Version

| Feature | Old Version | Current Version |
|---------|-------------|-----------------|
| Overhead | 6 bytes | 4 bytes |
| CRC | Software CRC16 | Hardware (SX1262) |
| ACK/NACK | Yes | No (MAVLink handles) |
| Retries | Yes | No (MAVLink handles) |
| Sequence Numbers | Yes | No |

**Result**: 67% less overhead

## Message Flow Example

```
1. Flight Controller sends MAVLink HEARTBEAT via UART
     │
     ▼
2. Drone receives, identifies as Tier 1 (HEARTBEAT)
     │
     ▼
3. Drone enqueues to Tier 1 priority queue
     │
     ▼
4. process() dequeues, builds AeroLoRa packet:
   [0xAE][0x01][0x00][0x09][MAVLink HEARTBEAT data]
     │
     ▼
5. Radio transmits, hardware adds CRC
     │
     ▼
6. Ground station radio receives, validates CRC
     │
     ▼
7. Protocol extracts MAVLink payload
     │
     ▼
8. Ground station forwards to QGC via USB Serial
```

## Blacklisted Messages

Some MAVLink messages are too high-frequency for LoRa and provide minimal value:

```cpp
const uint8_t AEROLORA_MESSAGE_BLACKLIST[] = {
    88,   // HIL_OPTICAL_FLOW
    100,  // OPTICAL_FLOW
    106,  // HIL_SENSOR
    27,   // RAW_IMU (use ATTITUDE instead)
    129,  // SCALED_IMU3
    132,  // Unknown (6.2 Hz)
    241   // DISTANCE_SENSOR
};
```

These messages are silently dropped before queuing.

## Rate Limiting

High-frequency messages are rate-limited to prevent queue flooding:

| Message | Default Rate | Limited To |
|---------|--------------|------------|
| ATTITUDE (30) | 10+ Hz | 2 Hz |
| GPS_RAW_INT (24) | 5 Hz | 2 Hz |
| GLOBAL_POSITION_INT (33) | 5 Hz | 3 Hz |

---

[← Firmware Flashing](../configuration/firmware-flashing) | [Next: Priority Queues →](priority-queues)
