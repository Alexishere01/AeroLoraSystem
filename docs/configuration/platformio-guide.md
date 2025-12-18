---
layout: default
title: PlatformIO Guide
---

# PlatformIO Build Environments

This project uses PlatformIO with multiple build environments for different device configurations.

## Available Environments

| Environment | Device | Frequency | Purpose |
|-------------|--------|-----------|---------|
| `aero_ground` | Ground Station | 930 MHz | Standard GCS |
| `qgc_radio2_902mhz` | Ground Station | 902 MHz | Relay receiver |
| `aero_drone` | Drone | 930 MHz | Basic drone (legacy) |
| `drone1` | Target Drone | 930 MHz | Primary target aircraft |
| `drone1_no_espnow` | Target Drone | 930 MHz | LoRa-only mode for jammer testing |
| `drone2_primary` | Relay Primary | 930 MHz | Relay coordinator |
| `drone2_secondary` | Relay Secondary | 902 MHz | Relay bridge |
| `get_mac` | Utility | N/A | Read device MAC address |

## Build Flags Reference

### Device Type Flags

| Flag | Description |
|------|-------------|
| `AERO_GROUND` | Enables ground station code paths |
| `AERO_DRONE` | Enables drone code paths |

### Node Identity

| Flag | Value | Description |
|------|-------|-------------|
| `NODE_ID` | 0 | Ground station |
| `NODE_ID` | 1 | Drone 1 (target) |
| `NODE_ID` | 2 | Drone 2 Primary (relay) |
| `NODE_ID` | 3 | Drone 2 Secondary (relay) |

### Radio Configuration

| Flag | Values | Description |
|------|--------|-------------|
| `FREQ_PRIMARY` | 902.0, 930.0 | Primary frequency in MHz |
| `FREQ_902MHZ_MODE` | (defined) | Use 902 MHz MAC addresses |

### Relay System

| Flag | Description |
|------|-------------|
| `ENABLE_RELAY` | Enables relay functionality |
| `ALWAYS_RELAY_MODE` | Relay always active (testing) |
| `RELAY_DEBUG` | Verbose relay logging |

### Optional Features

| Flag | Description |
|------|-------------|
| `ENABLE_FLIGHT_LOGGER` | Enables LittleFS logging |
| `DEBUG_LOGGING` | Verbose serial debug output (0 or 1) |
| `DISABLE_ESPNOW` | Disables 2.4 GHz ESP-NOW transport |

## Radio Parameters

All environments use these default radio settings:

```cpp
#define LORA_BANDWIDTH      500.0   // 500 kHz for maximum speed
#define LORA_SPREAD_FACTOR  6       // SF6 for speed
#define LORA_CODING_RATE    5       // 4/5 coding rate
#define LORA_SYNC_WORD      0x34    // Private network
#define LORA_TX_POWER       4       // 4 dBm (reduced for testing)
```

### Modifying TX Power

To increase range, edit `platformio.ini`:

```ini
build_flags =
    -DLORA_TX_POWER=14   # Up to 20 dBm for SX1262
```

⚠️ **Warning**: Higher power = more current draw. Ensure adequate power supply.

## Building and Uploading

### Via VS Code

1. Click the PlatformIO icon (alien head) in sidebar
2. Expand your desired environment (e.g., `drone1`)
3. Click **Upload**

### Via Command Line

```bash
# Build only
pio run -e drone1

# Build and upload
pio run -e drone1 -t upload

# Open serial monitor
pio device monitor -e drone1
```

## Library Dependencies

All environments use these libraries (automatically managed):

```ini
lib_deps =
    jgromes/RadioLib@^6.4.0    # LoRa radio driver
    olikraus/U8g2@^2.35.9      # OLED display driver
```

## Custom Environment Example

To create a custom configuration:

```ini
[env:my_custom_config]
platform = espressif32
board = heltec_wifi_lora_32_V3
framework = arduino
build_src_filter = 
    +<aero_lora_drone.cpp>
    +<AeroLoRaProtocol.cpp>
    +<ESPNowTransport.cpp>
    +<DualBandTransport.cpp>
    +<MessageFilter.cpp>
    +<flight_logger.cpp>
build_flags =
    -DAERO_DRONE
    -DNODE_ID=1
    -DFREQ_PRIMARY=915.0    # Different frequency
    -DLORA_TX_POWER=20      # Max power
    -DENABLE_FLIGHT_LOGGER
lib_deps =
    jgromes/RadioLib@^6.4.0
    olikraus/U8g2@^2.35.9
```

---

[← Ground Station](../hardware/ground-station) | [Next: Frequency Setup →](frequency-setup)
