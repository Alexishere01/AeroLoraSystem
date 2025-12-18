---
layout: default
title: Frequency Setup
---

# Frequency Allocation

This guide explains the frequency allocation strategy used in the AeroLoRa system.

## Frequency Plan

| Frequency | Band | Usage |
|-----------|------|-------|
| 930 MHz | LoRa | Primary link (Drone 1 ↔ Ground) |
| 902 MHz | LoRa | Relay link (Drone 2 ↔ Ground 902) |
| 2.4 GHz | WiFi | ESP-NOW backup transport |

## Why 930 MHz?

The original design used 915 MHz, but this was changed to **930 MHz** to avoid interference with ExpressLRS (ELRS):

```cpp
// ELRS typically uses 902-928 MHz
// We moved to 930 MHz to avoid interference
#define FREQ_PRIMARY 930.0
```

### ELRS Frequency Bands
- **US**: 902-928 MHz
- **EU**: 868 MHz

By operating at 930 MHz, we:
- Avoid ELRS interference in the US band
- Maintain legal operation in ISM band (902-928 MHz extends to 930 MHz in some regulations)
- Get cleaner spectrum for our telemetry

## Dual Frequency for Relay

The relay system uses two frequencies to avoid self-interference:

```
Drone 1 ◄────► Ground (930 MHz)   PRIMARY LINK
    │
    │ If jammed:
    ▼
Drone 2 Primary (930 MHz) receives
    │
    │ UART
    ▼
Drone 2 Secondary (902 MHz) transmits
    │
    ▼
Ground 902 (902 MHz) receives   BACKUP LINK
```

### Why Different Frequencies?

1. **Isolation**: Primary and relay links don't interfere
2. **Jamming resilience**: Jamming one frequency doesn't block both
3. **Simultaneous operation**: Both links can work together

## Radio Parameters

### LoRa Settings (All Devices)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Bandwidth | 500 kHz | Maximum for speed |
| Spreading Factor | 6 | Fast but shorter range |
| Coding Rate | 4/5 | Good error correction |
| Sync Word | 0x34 | Private network |
| TX Power | 4 dBm | Reduced for testing |

### Trade-offs

| Setting | Higher Value | Lower Value |
|---------|--------------|-------------|
| Bandwidth | Faster, shorter range | Slower, longer range |
| Spreading Factor | Longer range, slower | Shorter range, faster |
| TX Power | Longer range, more current | Shorter range, less current |

## Changing Frequencies

### Compile-Time Configuration

Frequencies are set via build flags in `platformio.ini`:

```ini
[env:drone1]
build_flags =
    -DFREQ_PRIMARY=930.0   # Change this

[env:drone2_secondary]
build_flags =
    -DFREQ_PRIMARY=902     # Relay uses 902
```

### Valid Frequency Ranges

| Chip | Range | Notes |
|------|-------|-------|
| SX1262 | 150-960 MHz | Check local regulations |

### Regional Considerations

| Region | ISM Band | Notes |
|--------|----------|-------|
| US | 902-928 MHz | Up to 1W allowed (with spread spectrum) |
| EU | 868 MHz | Different power limits apply |
| AU | 915-928 MHz | Similar to US |

> ⚠️ **Important**: Always verify local regulations before choosing frequencies and power levels.

## ESP-NOW (2.4 GHz)

ESP-NOW operates on WiFi channel 1 (2.412 GHz) by default:

```cpp
// WiFi channel is set automatically during ESP-NOW init
// Default: Channel 1
```

ESP-NOW provides:
- **Low latency**: < 10ms
- **Higher bandwidth**: Can carry all MAVLink messages
- **Shorter range**: ~50m reliable

---

[← PlatformIO Guide](platformio-guide) | [Next: Firmware Flashing →](firmware-flashing)
