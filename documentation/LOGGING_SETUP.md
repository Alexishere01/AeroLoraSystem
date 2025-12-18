# Flight Logging Setup Summary

## Overview

All modules now log to LittleFS (internal flash) in the enhanced 12-field CSV format.

## Logging Locations

### Drone1 (aero_lora_drone.cpp)
- **File**: `/drone1_log.csv`
- **Logs**:
  - **TX events**: When sending MAVLink from FC to ground
  - **RX events**: When receiving packets from ground
- **DUMP command**: Type `DUMP` in serial monitor to download log

### Ground Station (aero_lora_ground.cpp)
- **File**: `/ground_log.csv`
- **Logs**:
  - **RX events**: When receiving LoRa packets from drones (with RSSI/SNR)
  - **TX events**: When sending packets to drones
- **DUMP command**: Type `DUMP` in serial monitor to download log

### Drone2 Primary (drone2_primary.cpp)
- **File**: `/primary_log.csv`
- **Logs**: Relay operations and packet forwarding
- **DUMP command**: Type `DUMP` in serial monitor to download log

### Drone2 Secondary (drone2_secondary.cpp)
- **File**: `/secondary_log.csv`
- **Logs**: UART bridge and relay operations
- **DUMP command**: Type `DUMP` in serial monitor to download log

## CSV Format (Enhanced 12-field)

```csv
timestamp_ms,sequence_number,message_id,system_id,rssi_dbm,snr_db,relay_active,event,packet_size,tx_timestamp,queue_depth,errors
```

### Fields:
1. **timestamp_ms**: Milliseconds since boot
2. **sequence_number**: Packet sequence number
3. **message_id**: MAVLink message ID
4. **system_id**: MAVLink system ID
5. **rssi_dbm**: Received Signal Strength Indicator (dBm)
6. **snr_db**: Signal-to-Noise Ratio (dB)
7. **relay_active**: 1 if relay mode active, 0 otherwise
8. **event**: Event type (TX, RX, RELAY_*, etc.)
9. **packet_size**: Size of packet in bytes
10. **tx_timestamp**: Timestamp when packet was transmitted
11. **queue_depth**: Current queue depth
12. **errors**: Cumulative error count

## How to Download Logs

### Via Serial Monitor

1. Connect module via USB
2. Open PlatformIO Serial Monitor (or any serial terminal at 115200 baud)
3. Type: `DUMP`
4. Press Enter
5. Copy the output between `========== LOG DUMP START ==========` and `========== LOG DUMP END ==========`
6. Save to a `.csv` file

### Via Python Script

```python
import serial
import time

ser = serial.Serial('/dev/cu.usbserial-XXXX', 115200, timeout=1)
time.sleep(2)
ser.write(b'DUMP\n')

with open('drone1_log.csv', 'w') as f:
    while True:
        line = ser.readline().decode('utf-8')
        if 'LOG DUMP END' in line:
            break
        if 'LOG DUMP START' not in line:
            f.write(line)

ser.close()
```

## Analysis Scripts

After downloading logs, use the analysis scripts:

### Individual Analysis

```bash
# Throughput analysis
python telemetry_validation/examples/analyze_throughput.py \
    drone1_log.csv ground_log.csv

# Latency analysis
python telemetry_validation/examples/analyze_latency.py \
    drone1_log.csv ground_log.csv

# Queue congestion analysis
python telemetry_validation/examples/analyze_queue_congestion.py \
    drone1_log.csv ground_log.csv

# Error correlation analysis
python telemetry_validation/examples/analyze_error_correlation.py \
    drone1_log.csv ground_log.csv
```

### Comprehensive Analysis

```bash
# Run all analyses and generate PDF report
python telemetry_validation/examples/comprehensive_analysis.py \
    drone1_log.csv ground_log.csv primary_log.csv
```

## Real-Time Monitoring

For real-time monitoring via QGroundControl:

```bash
cd telemetry_validation
source venv/bin/activate
python main.py --connection-type udp --port 14445 --protocol-mode mavlink --log-prefix test_flight
```

This monitors MAVLink packets forwarded by QGroundControl and provides:
- Real-time metrics display
- Automatic CSV logging
- Live visualizations

## Build Environments

All environments now have `ENABLE_FLIGHT_LOGGER` and LittleFS enabled:

- `drone1` - Drone1 with logging @ 930 MHz
- `aero_ground` - Ground station with logging @ 930 MHz
- `qgc_radio2_902mhz` - Ground station with logging @ 902 MHz (relay link)
- `qgc_dual_radio` - Dual radio ground station with logging @ 930 + 902 MHz
- `drone2_primary` - Drone2 Primary with logging @ 930 MHz
- `drone2_secondary` - Drone2 Secondary with logging @ 902 MHz

## Storage Capacity

LittleFS on ESP32 typically has ~1.5MB available. At approximately:
- 100 bytes per log entry
- ~15,000 entries can be stored
- At 10 packets/second, this is ~25 minutes of flight time

For longer flights, periodically dump and clear logs, or reduce logging frequency.
