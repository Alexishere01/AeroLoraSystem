---
layout: default
title: Web Dashboard
---

# Web Serial Dashboard

A browser-based real-time monitoring tool using the WebSerial API.

## Overview

The Web Dashboard provides live telemetry visualization directly in your browser without installing any software.

![Dashboard Screenshot](../assets/dashboard.png)

## Browser Requirements

| Browser | Minimum Version | Support |
|---------|-----------------|---------|
| Chrome | 89+ | ✅ Full |
| Edge | 89+ | ✅ Full |
| Opera | 75+ | ✅ Full |
| Firefox | - | ❌ None |
| Safari | - | ❌ None |

## Quick Start

### 1. Open the Dashboard

Navigate to `flight_replay/webserial_dashboard/index.html` in your browser:

```bash
# Using Python's built-in server
cd flight_replay/webserial_dashboard
python3 -m http.server 8000
# Open http://localhost:8000
```

Or simply open the HTML file directly:
```
file:///path/to/project/flight_replay/webserial_dashboard/index.html
```

### 2. Connect Device

1. Connect your Heltec device via USB
2. Click **"Connect Serial Port"** button
3. Select the device from the popup dialog
4. Click **Connect**

### 3. View Live Data

The dashboard will display:
- Real-time RSSI and SNR
- Packet counts (TX/RX)
- Queue depths
- Event log

## Features

### Live Telemetry Display

| Metric | Description |
|--------|-------------|
| RSSI | Received Signal Strength (dBm) |
| SNR | Signal-to-Noise Ratio (dB) |
| Packets Sent | Total transmitted packets |
| Packets Received | Total received packets |
| Queue Depth | Current items in transmit queue |
| Drop Count | Packets dropped due to queue full or staleness |

### Event Log

Real-time scrolling log of:
- RX events with message ID and RSSI
- TX events with destination
- Relay activation/deactivation
- Errors and warnings

### Data Export

Click **"Export Log"** to download the session data as CSV for later analysis.

## Dashboard Files

```
flight_replay/webserial_dashboard/
├── index.html           # Main HTML structure
├── dashboard_styles.css # Styling
└── README.md           # Usage instructions
```

## Customization

### Changing Baud Rate

Edit the connection code in `index.html`:

```javascript
const port = await navigator.serial.requestPort();
await port.open({ baudRate: 115200 });  // Change this value
```

### Adding New Metrics

To display additional data, modify the parsing function:

```javascript
function parseSerialData(line) {
    // Parse your custom log format
    const match = line.match(/\[CUSTOM\] value=(\d+)/);
    if (match) {
        updateDisplay('custom-metric', match[1]);
    }
}
```

## Log Format

The dashboard expects log lines in this format:

```
[DRONE] ESP:10/5 R:-45
[DRONE] LoRa:50/48 F:12
[INFO] RX_LORA seq=123 msg=0 rssi=-67.5 snr=9.2
```

## Troubleshooting

### "No Serial Port Available"
- Ensure device is connected via USB
- Check for driver issues (Device Manager on Windows)
- Try a different USB port

### "Permission Denied"
- Close other programs using the serial port
- On Linux, add user to `dialout` group: `sudo usermod -a -G dialout $USER`

### Data Not Updating
- Verify device is transmitting (check OLED display)
- Check baud rate matches device configuration
- Verify log format matches parser expectations

### Browser Compatibility
- WebSerial only works in Chromium-based browsers
- Use Chrome, Edge, or Opera

---

[← Relay Architecture](../protocol/relay-architecture) | [Back to Home →](/)
