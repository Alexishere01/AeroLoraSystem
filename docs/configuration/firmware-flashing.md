---
layout: default
title: Firmware Flashing
---

# Firmware Flashing Guide

This guide covers how to flash firmware to the Heltec devices.

## Prerequisites

- VS Code with PlatformIO extension installed
- USB-C cable
- Heltec WiFi LoRa 32 V3 device

## Flashing via VS Code

### Step 1: Select Environment

1. Click the PlatformIO icon in the sidebar
2. Navigate to **Project Tasks** → **[environment name]**
3. Click **Upload**

### Step 2: Put Device in Boot Mode (if needed)

If upload fails, put the device in bootloader mode:

1. Hold **BOOT** button
2. Press and release **RST** button
3. Release **BOOT** button
4. Retry upload

## Flashing via Command Line

```bash
# Flash drone1
pio run -e drone1 -t upload

# Flash ground station
pio run -e aero_ground -t upload

# Flash with specific port
pio run -e drone1 -t upload --upload-port /dev/ttyUSB0
```

## Verify Flash Success

After flashing, the OLED display should show the device type:

| Device | Display Message |
|--------|-----------------|
| Ground Station | "Ground Ready" |
| Drone 1 | "Dual-Band Drone", "READY!" |
| Drone 2 Primary | "RELAY PRIMARY", "READY!" |
| Drone 2 Secondary | "RELAY SECONDARY", "READY!" |

## Serial Monitor

Open serial monitor to verify operation:

```bash
pio device monitor -e drone1 --baud 115200
```

> ⚠️ **Note**: The ground station uses 57600 baud for MAVLink, but debug output (if enabled) uses 115200.

## Erasing Flash

To completely erase the device:

```bash
pio run -e drone1 -t erase
```

## Uploading Filesystem (LittleFS)

If your device uses LittleFS for logging:

```bash
pio run -e drone1 -t uploadfs
```

## Troubleshooting

### Upload Fails with Timeout
- Try bootloader mode (BOOT + RST)
- Check USB cable (data cable, not charge-only)
- Try different USB port
- Check if another program has the port open

### Device Not Detected
- Install CH340/CP2102 driver if needed
- Check Device Manager (Windows) or `ls /dev/tty*` (Linux/Mac)

### Wrong Environment Flashed
- Simply re-flash with correct environment
- Settings are in firmware, not EEPROM

## Batch Flashing

For flashing multiple devices:

```bash
#!/bin/bash
# flash_all.sh

echo "Connect Ground Station..."
read -p "Press enter when ready"
pio run -e aero_ground -t upload

echo "Connect Drone 1..."
read -p "Press enter when ready"
pio run -e drone1 -t upload

echo "Done!"
```

---

[← Frequency Setup](frequency-setup) | [Next: AeroLoRa Protocol →](../protocol/aerolora-overview)
