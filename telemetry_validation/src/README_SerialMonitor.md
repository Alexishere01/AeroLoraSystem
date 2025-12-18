# Serial Monitor Module

## Overview

The Serial Monitor module provides real-time telemetry monitoring with console output, displaying decoded MAVLink messages and binary protocol commands with color-coded highlighting for critical messages.

## Features

- **Real-time Display**: Shows telemetry data as it arrives
- **MAVLink Message Decoding**: Displays key fields from common message types
- **Binary Protocol Support**: Shows binary protocol commands (INIT, STATUS_REPORT, etc.)
- **Critical Message Highlighting**: Color-coded highlighting for important messages
- **RSSI/SNR Display**: Shows link quality metrics from binary protocol
- **Output Throttling**: Prevents buffer overflow by limiting output rate
- **Statistics Display**: Shows comprehensive telemetry statistics on request
- **Color-Coded Output**: Uses ANSI colors for better readability

## Requirements

Implements requirements:
- 2.1: Display decoded MAVLink messages with key fields
- 2.2: Highlight critical messages (HEARTBEAT, GPS, ATTITUDE)
- 2.3: Throttle output to prevent buffer overflow
- 2.4: Display statistics (packet rate, message distribution, link quality)

## Usage

### Basic Usage

```python
from serial_monitor import SerialMonitor, MonitorConfig
from metrics_calculator import MetricsCalculator

# Create metrics calculator
metrics_calc = MetricsCalculator()

# Create monitor with default configuration
monitor = SerialMonitor(metrics_calculator=metrics_calc)

# Display MAVLink message
monitor.display_mavlink_message(parsed_mavlink_msg)

# Display binary protocol packet
monitor.display_binary_packet(parsed_binary_packet)

# Display statistics
monitor.display_statistics()
```

### Custom Configuration

```python
from serial_monitor import SerialMonitor, MonitorConfig
from binary_protocol_parser import UartCommand

# Create custom configuration
config = MonitorConfig(
    show_mavlink=True,
    show_binary=True,
    show_timestamps=True,
    show_rssi_snr=True,
    highlight_critical=True,
    throttle_enabled=True,
    max_messages_per_second=10,
    critical_messages={'HEARTBEAT', 'GPS_RAW_INT', 'ATTITUDE'},
    critical_commands={UartCommand.CMD_INIT, UartCommand.CMD_STATUS_REPORT},
    color_enabled=True
)

# Create monitor with custom configuration
monitor = SerialMonitor(config=config)
```

### Disable Throttling

```python
# Disable throttling for debugging
config = MonitorConfig(throttle_enabled=False)
monitor = SerialMonitor(config=config)
```

### Disable Colors

```python
# Disable colors for logging to file
config = MonitorConfig(color_enabled=False)
monitor = SerialMonitor(config=config)
```

## Configuration Options

### MonitorConfig

- **show_mavlink** (bool): Display MAVLink messages (default: True)
- **show_binary** (bool): Display binary protocol commands (default: True)
- **show_timestamps** (bool): Include timestamps in output (default: True)
- **show_rssi_snr** (bool): Display RSSI/SNR values (default: True)
- **highlight_critical** (bool): Highlight critical messages (default: True)
- **throttle_enabled** (bool): Enable output throttling (default: True)
- **max_messages_per_second** (int): Maximum messages to display per second (default: 10)
- **critical_messages** (Set[str]): Set of critical MAVLink message types
- **critical_commands** (Set[UartCommand]): Set of critical binary commands
- **color_enabled** (bool): Enable color output (default: True)

### Default Critical Messages

- HEARTBEAT
- GPS_RAW_INT
- GLOBAL_POSITION_INT
- ATTITUDE
- SYS_STATUS
- BATTERY_STATUS
- COMMAND_ACK
- STATUSTEXT

### Default Critical Commands

- CMD_INIT
- CMD_STATUS_REPORT
- CMD_RELAY_ACTIVATE
- CMD_BROADCAST_RELAY_REQ

## Output Format

### MAVLink Messages

```
[HH:MM:SS] MAV:HEARTBEAT SYS:1 mode=0 armed=NO RSSI:-85.0dBm SNR:8.5dB
[HH:MM:SS] MAV:GPS_RAW_INT SYS:1 lat=37.123456 lon=-122.123456 alt=100.5m fix=3 sats=12 RSSI:-85.0dBm SNR:8.5dB
[HH:MM:SS] MAV:ATTITUDE SYS:1 roll=0.05 pitch=-0.02 yaw=1.57 RSSI:-85.0dBm SNR:8.5dB
```

### Binary Protocol Commands

```
[HH:MM:SS] BIN:CMD_INIT mode=FREQUENCY_BRIDGE freq1=915.00MHz freq2=868.00MHz
[HH:MM:SS] BIN:CMD_STATUS_REPORT relay=ACTIVE sysid=1 relayed=150 peers=2 RSSI:-82.0dBm SNR:9.2dB
[HH:MM:SS] BIN:CMD_BRIDGE_RX sysid=1 len=32B RSSI:-85.0dBm SNR:8.5dB
```

### Color Coding

- **Critical Messages**: Bold yellow (MAVLink) or bold magenta (Binary)
- **Normal Messages**: Cyan (MAVLink) or blue (Binary)
- **RSSI**: Green (>-80dBm), Yellow (-80 to -100dBm), Red (<-100dBm)
- **Throttle Warning**: Yellow
- **Statistics Headers**: Bold bright cyan

## Statistics Display

The `display_statistics()` method shows:

### Monitor Statistics
- MAVLink messages displayed
- Binary packets displayed
- Critical messages count
- Throttled messages count

### Packet Rates
- Binary protocol packet rates (1s, 10s, 60s windows)
- MAVLink packet rates (1s, 10s, 60s windows)

### Link Quality
- Average RSSI (color-coded)
- Average SNR
- Packet loss rate (color-coded)
- Command latency (average, min, max)

### Message Distribution
- Top 10 MAVLink message types by count
- All binary protocol command types by count

### Binary Protocol Health
- Success rate (color-coded)
- Checksum error rate (errors/min)
- Parse error rate (errors/min)
- Buffer overflow count
- Timeout count

## Throttling Behavior

When throttling is enabled:

1. **Critical messages** are always displayed (never throttled)
2. **Non-critical messages** are throttled when rate exceeds `max_messages_per_second`
3. **Throttle warnings** are displayed every 5 seconds when throttling is active
4. **Throttled count** is shown in the warning message

Example throttle warning:
```
⚠ Output throttled: 45 messages suppressed (limit: 10/s)
```

## Integration Example

```python
from connection_manager import ConnectionManager, ConnectionType
from binary_protocol_parser import BinaryProtocolParser, MAVLinkExtractor
from mavlink_parser import MAVLinkParser
from metrics_calculator import MetricsCalculator
from serial_monitor import SerialMonitor, MonitorConfig

# Create components
conn_mgr = ConnectionManager(ConnectionType.SERIAL, port='/dev/ttyUSB0', baudrate=115200)
binary_parser = BinaryProtocolParser()
mavlink_extractor = MAVLinkExtractor()
mavlink_parser = MAVLinkParser()
metrics_calc = MetricsCalculator()

# Create monitor
config = MonitorConfig(
    throttle_enabled=True,
    max_messages_per_second=10
)
monitor = SerialMonitor(config=config, metrics_calculator=metrics_calc)

# Connect
conn_mgr.connect()

# Main loop
try:
    while True:
        # Read data
        data = conn_mgr.read(1024)
        
        if data:
            # Parse binary protocol
            binary_packets = binary_parser.parse_stream(data)
            
            for packet in binary_packets:
                # Display binary packet
                monitor.display_binary_packet(packet)
                
                # Update metrics
                metrics_calc.update_binary_packet(packet)
                
                # Extract MAVLink if present
                mavlink_msg = mavlink_extractor.extract_mavlink(packet)
                if mavlink_msg:
                    # Display MAVLink message
                    monitor.display_mavlink_message(mavlink_msg)
                    
                    # Update metrics
                    metrics_calc.update_mavlink_message(mavlink_msg)
        
        # Display statistics every 10 seconds
        if time.time() % 10 < 0.1:
            monitor.display_statistics()

except KeyboardInterrupt:
    print("\nShutting down...")
finally:
    conn_mgr.disconnect()
```

## API Reference

### SerialMonitor

#### `__init__(config: Optional[MonitorConfig] = None, metrics_calculator: Optional[MetricsCalculator] = None)`

Initialize the serial monitor.

**Parameters:**
- `config`: Monitor configuration (uses defaults if None)
- `metrics_calculator`: Optional MetricsCalculator for statistics display

#### `display_mavlink_message(msg: ParsedMessage) -> bool`

Display a MAVLink message to the console.

**Parameters:**
- `msg`: Parsed MAVLink message

**Returns:**
- True if message was displayed, False if throttled

#### `display_binary_packet(packet: ParsedBinaryPacket) -> bool`

Display a binary protocol packet to the console.

**Parameters:**
- `packet`: Parsed binary protocol packet

**Returns:**
- True if packet was displayed, False if throttled

#### `display_statistics(metrics: Optional[TelemetryMetrics] = None)`

Display comprehensive statistics to the console.

**Parameters:**
- `metrics`: Optional TelemetryMetrics object (uses internal calculator if None)

#### `get_stats() -> Dict`

Get monitor statistics.

**Returns:**
- Dictionary containing monitor statistics

#### `reset_stats()`

Reset monitor statistics.

## Testing

See `examples/serial_monitor_example.py` for a complete working example.

## Notes

- Critical messages bypass throttling to ensure important data is always visible
- RSSI/SNR values are extracted from both MAVLink RADIO_STATUS messages and binary protocol payloads
- Color output can be disabled for logging to files or non-terminal output
- Statistics display requires a MetricsCalculator instance
- Throttle warnings are rate-limited to once every 5 seconds

## Related Modules

- `binary_protocol_parser.py`: Parses binary protocol packets
- `mavlink_parser.py`: Parses MAVLink messages
- `metrics_calculator.py`: Calculates telemetry metrics
- `connection_manager.py`: Manages serial/UDP connections
