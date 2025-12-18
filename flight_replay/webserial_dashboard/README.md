# AeroLoRa WebSerial Telemetry Dashboard

A modern, browser-based telemetry dashboard for the AeroLoRa drone communication system with dual ground station receiver visualization.

## Features

### 📊 System-Wide Metrics
- **Overall Throughput**: Total bandwidth across all communication links
- **System Delivery Rate**: Percentage of successfully delivered packets (color-coded)
- **Total Dropped Packets**: Aggregate drops with breakdown
- **Communication Mode**: DIRECT or RELAY indicator

### 📡 Per-Node Visualization
- **Drone (Target)**: TX/RX counts, queue depth, drops, signal strength
- **Ground 902 MHz**: Packets received, signal quality, RSSI/SNR, jamming indicator
- **Ground 930 MHz**: Packets received, signal quality, RSSI/SNR, jamming indicator
- **Relay Drone**: Forwarded packets, link quality, queue metrics

### 📈 Real-Time Charts
- **Signal Quality**: Dual-receiver RSSI comparison over time
- **Throughput**: Bandwidth usage timeline
- **Delivery Rate**: Success rate with jamming events highlighted
- **Queue Depth**: Multi-node queue visualization

### 🌐 Network Topology
- Live SVG visualization showing active communication paths
- Automatic switching between DIRECT and RELAY modes
- Animated link indicators

## Usage

### Option 1: CSV Replay Mode (Recommended for Demo)

1. **Open the dashboard**:
   ```bash
   cd flight_replay/webserial_dashboard
   open index.html  # macOS
   # or just double-click index.html in your file browser
   ```

2. **Upload CSV files**:
   - Click "📁 Upload CSV Files"
   - Select multiple files:
     - Drone log (e.g., `JammedDrone3.csv`)
     - Ground 902 MHz log (e.g., `JammedGround1.csv`)
     - Ground 930 MHz log (e.g., `JammedGround2.csv`)
     - Optional: Relay log files

3. **Control playback**:
   - Click **▶️ Play** to start replay
   - Use speed selector (0.5x to 10x)
   - Drag time slider to jump to specific moments
   - Click **⏸ Pause** to freeze at current time
   - Click **⏹ Reset** to return to start

### Option 2: Live WebSerial Connection

1. **Connect hardware**:
   - Connect Heltec ground station to computer via USB
   - Ensure ground station is logging to serial

2. **Open dashboard in Chrome or Edge** (WebSerial required)

3. **Connect**:
   - Click "🔌 Connect Serial"
   - Select the COM port in browser dialog
   - Data will stream in real-time

> **Note**: WebSerial API only works in Chromium-based browsers (Chrome, Edge, Opera). Safari and Firefox are not supported.

## Answering Professor's Question

This dashboard directly addresses the feedback:

> "you have 2 receivers on the ground station. why do not you show the 'packets received' and 'signal quality' from each receiver separately so that we understand how the receiver that is in the same frequency with the jammer gets affected"

**Solution**:
- **Separate cards** for 902 MHz and 930 MHz receivers
- **Independent signal quality metrics** (RSSI, SNR, packet counts)
- **Jamming indicators** (⚠️) that activate when signal degrades
- **Side-by-side comparison** makes jamming effects obvious

**Demo narrative**:
1. Load jammed scenario CSVs
2. Play timeline - both receivers show normal operation
3. When jamming starts, one receiver degrades (red signal, ⚠️ indicator)
4. Other receiver maintains connection (green signal)
5. System fails over to RELAY mode automatically
6. **Clear visual proof** that jamming affects specific frequency

## File Structure

```
webserial_dashboard/
├── index.html              # Main dashboard interface
├── dashboard_styles.css    # Premium dark-mode styling
├── webserial_app.js        # Application logic & data processing
└── README.md              # This file
```

## Technology Stack

- **HTML5** - Structure
- **CSS3** - Glassmorphism styling, neon accents
- **Vanilla JavaScript** - No framework dependencies
- **Chart.js** - Real-time charting (loaded from CDN)
- **WebSerial API** - Live hardware connection (Chrome/Edge only)

## Differences from Qt Implementation

| Aspect | Qt (main.py) | WebSerial Dashboard |
|--------|--------------|-------------------|
| Platform | Desktop app (Python) | Browser-based |
| Dependencies | PyQt6, pyqtgraph, pandas | Zero local dependencies |
| Installation | Python + pip packages | None - just open HTML |
| Real-time | CSV replay only | WebSerial + CSV |
| Receivers | Combined into single "Ground" | **Separate 902/930 MHz cards** |
| Deployment | Run Python script | Static files - works offline |
| Updates | Code changes + restart | Refresh browser |

## Browser Compatibility

✅ **Supported** (WebSerial):
- Chrome 89+
- Edge 89+
- Opera 76+

⚠️ **CSV-only** (no WebSerial):
- Safari (any version)
- Firefox (any version)

## Tips for Demo Day

### For Maximum Impact:
1. **Use CSV replay mode** - More reliable than live hardware during presentation
2. **Pre-load jamming scenario** - Show before/during/after jamming
3. **Highlight dual receivers** - Point out separate 902/930 cards
4. **Watch jamming indicators** - ⚠️ symbols show affected frequency
5. **Explain delivery rate drop** - System metrics show impact
6. **Show relay activation** - Topology changes, mode indicator switches

### Practice Script:
```
"Here's our system running normally - both receivers showing green signal quality.
Now the jammer activates [point to timestamp] - watch the 902 MHz receiver.
Signal drops to red, jamming indicator appears, packets stop arriving.
But the 930 MHz receiver? Still green, still receiving.
System automatically fails over to relay mode [point to topology].
Communication continues with 89% delivery rate despite jamming."
```

## Troubleshooting

**Dashboard won't load?**
- Ensure you're using a modern browser (Chrome 89+ or Edge 89+)
- Check browser console for errors (F12)

**CSV files won't upload?**
- Verify files are valid CSV format
- Check that filenames contain identifying keywords (drone, ground, 902, 930, relay)

**WebSerial won't connect?**
- Only works in Chrome/Edge - not Safari/Firefox
- Device must be compatible with WebSerial API
- Try different USB cable/port

**Charts not updating?**
- Ensure Chart.js CDN loaded (check internet connection on first load)
- Try refreshing page

## Future Enhancements

- WebSocket support for remote telemetry streaming
- Configurable alert thresholds
- Export metrics to CSV/PDF
- Multi-session comparison view
- Playback annotations and markers

## Credits

Built for Senior Design 2 - AeroLoRa Communication System
Author: Alex Zurita & Team
