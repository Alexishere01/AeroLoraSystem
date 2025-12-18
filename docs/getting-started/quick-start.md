---
layout: default
title: Quick Start
---

# Quick Start Guide

Get the AeroLoRa system running in 10 minutes with this step-by-step guide.

## Step 1: Clone the Repository

```bash
git clone git@github.com:Alexishere01/AeroLoRa-Relay-System.git
cd AeroLoRa-Relay-System
```

## Step 2: Open in VS Code with PlatformIO

```bash
code .
```

Wait for PlatformIO to initialize and index the project.

## Step 3: Flash the Ground Station

1. Connect your first Heltec V3 via USB
2. In PlatformIO, select the environment: `aero_ground`
3. Click the **Upload** button (→)

```bash
# Or via command line:
pio run -e aero_ground -t upload
```

The display should show: `Ground Ready`

## Step 4: Flash the Drone

1. Connect your second Heltec V3 via USB
2. Select the environment: `drone1`
3. Click **Upload**

```bash
pio run -e drone1 -t upload
```

The display should show: `DUAL-BAND DRONE` followed by `READY!`

## Step 5: Connect to QGroundControl

1. Connect the Ground Station Heltec to your computer
2. Open QGroundControl
3. Go to **Application Settings** → **Comm Links**
4. Add a new **Serial** link:
   - Port: Select the Heltec's COM/ttyUSB port
   - Baud Rate: **57600**
5. Click **Connect**

## Step 6: Verify Communication

With both devices powered:

1. The Ground Station OLED should show:
   - ESP-NOW status and RSSI
   - LoRa packet counts increasing

2. QGroundControl should show:
   - Vehicle connected (green indicator)
   - Telemetry data flowing

## Troubleshooting

### No Connection in QGC
- Verify baud rate is 57600
- Check correct serial port selected
- Ensure drone has power and is transmitting

### ESP-NOW Shows "OUT OF RANGE"
- Devices must be within ~50m for ESP-NOW
- Check MAC address configuration in source code
- Verify both devices on same WiFi channel

### Weak LoRa Signal
- Ensure antennas are connected
- Increase TX power in `platformio.ini` (max 20 dBm)
- Check for radio interference on 930 MHz

---

[← Prerequisites](prerequisites) | [Next: Hardware Guides →](../hardware/drone-build)
