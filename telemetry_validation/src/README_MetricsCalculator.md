# Metrics Calculator Module

## Overview

The Metrics Calculator module provides comprehensive metrics tracking and analysis for the telemetry validation system. It tracks both binary protocol packets and MAVLink messages, calculating packet rates, link quality metrics, packet loss, command latency, and protocol health statistics.

## Features

- **Rolling Window Packet Rates**: Track packet rates over 1s, 10s, and 60s windows
- **Link Quality Metrics**: Average RSSI and SNR from binary protocol
- **Packet Loss Detection**: Detect gaps in MAVLink sequence numbers
- **Command Latency Tracking**: Measure round-trip time for COMMAND_LONG/COMMAND_ACK
- **Message Type Distribution**: Track frequency of different message types
- **Binary Protocol Health**: Monitor checksum errors, parse errors, and success rate

## Requirements Addressed

- **5.1**: Calculate and store metrics including packet rate, average RSSI, average SNR, and message type distribution
- **5.4**: Record packet loss events with timestamp and duration
- **5.5**: Compute rolling averages over 1-second, 10-second, and 60-second windows
- **2.4**: Display packet rate, message distribution, and link quality
- **2.5**: Calculate latency between command transmission and acknowledgment
- **6.3**: Track command latency
- **9.2**: Track relay-specific metrics
- **9.4**: Detect packet loss

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MetricsCalculator                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Rolling Windows (deques):                                  │
│  ├─ binary_packets_1s/10s/60s                              │
│  ├─ mavlink_packets_1s/10s/60s                             │
│  ├─ rssi_values (last 100)                                 │
│  ├─ snr_values (last 100)                                  │
│  ├─ latencies (last 100)                                   │
│  ├─ checksum_errors (last 1000)                            │
│  └─ parse_errors (last 1000)                               │
│                                                              │
│  Tracking Dictionaries:                                     │
│  ├─ mavlink_msg_type_counts                                │
│  ├─ binary_cmd_type_counts                                 │
│  ├─ sequence_numbers (per system_id)                       │
│  └─ command_times (for latency)                            │
│                                                              │
│  Methods:                                                    │
│  ├─ update_binary_packet()                                 │
│  ├─ update_mavlink_message()                               │
│  ├─ record_checksum_error()                                │
│  ├─ record_parse_error()                                   │
│  ├─ get_metrics() -> TelemetryMetrics                      │
│  └─ get_stats() -> dict                                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Usage

### Basic Usage

```python
from metrics_calculator import MetricsCalculator
from binary_protocol_parser import BinaryProtocolParser
from mavlink_parser import MAVLinkParser

# Create metrics calculator
calculator = MetricsCalculator()

# Create parsers
binary_parser = BinaryProtocolParser()
mavlink_parser = MAVLinkParser()

# Process binary protocol data
binary_packets = binary_parser.parse_stream(uart_data)
for packet in binary_packets:
    calculator.update_binary_packet(packet)

# Process MAVLink data
mavlink_messages = mavlink_parser.parse_stream(mavlink_data)
for msg in mavlink_messages:
    calculator.update_mavlink_message(msg)

# Get current metrics
metrics = calculator.get_metrics()

print(f"Binary packet rate (1s): {metrics.binary_packet_rate_1s:.2f} pkt/s")
print(f"MAVLink packet rate (1s): {metrics.mavlink_packet_rate_1s:.2f} msg/s")
print(f"Average RSSI: {metrics.avg_rssi:.2f} dBm")
print(f"Average SNR: {metrics.avg_snr:.2f} dB")
print(f"Packet loss rate: {metrics.drop_rate:.2f}%")
print(f"Command latency: {metrics.latency_avg*1000:.2f} ms")
```

### Tracking Binary Protocol Packets

```python
# Update with binary protocol packet
calculator.update_binary_packet(packet)

# The calculator automatically:
# - Tracks packet timestamps for rate calculation
# - Extracts RSSI/SNR from BridgePayload and StatusPayload
# - Counts command types for distribution
# - Updates success counters
```

### Tracking MAVLink Messages

```python
# Update with MAVLink message
calculator.update_mavlink_message(msg)

# The calculator automatically:
# - Tracks message timestamps for rate calculation
# - Detects packet loss from sequence numbers (HEARTBEAT)
# - Tracks command latency (COMMAND_LONG/COMMAND_ACK)
# - Counts message types for distribution
```

### Recording Errors

```python
# Record checksum error from binary parser
calculator.record_checksum_error()

# Record parse error from binary parser
calculator.record_parse_error()

# These are used to calculate error rates and protocol health
```

### Getting Metrics

```python
# Get comprehensive metrics snapshot
metrics = calculator.get_metrics()

# Access individual metrics
print(f"Binary rates: {metrics.binary_packet_rate_1s:.2f} / "
      f"{metrics.binary_packet_rate_10s:.2f} / "
      f"{metrics.binary_packet_rate_60s:.2f} pkt/s")

print(f"MAVLink rates: {metrics.mavlink_packet_rate_1s:.2f} / "
      f"{metrics.mavlink_packet_rate_10s:.2f} / "
      f"{metrics.mavlink_packet_rate_60s:.2f} msg/s")

print(f"Link quality: RSSI={metrics.avg_rssi:.2f} dBm, "
      f"SNR={metrics.avg_snr:.2f} dB")

print(f"Packet loss: {metrics.packets_lost} lost, "
      f"{metrics.packets_received} received, "
      f"{metrics.drop_rate:.2f}% drop rate")

print(f"Latency: avg={metrics.latency_avg*1000:.2f} ms, "
      f"min={metrics.latency_min*1000:.2f} ms, "
      f"max={metrics.latency_max*1000:.2f} ms")

# Message type distributions
for msg_type, count in metrics.mavlink_msg_type_distribution.items():
    print(f"  {msg_type}: {count}")

for cmd_type, count in metrics.binary_cmd_type_distribution.items():
    print(f"  {cmd_type}: {count}")

# Protocol health
print(f"Checksum errors: {metrics.checksum_error_rate:.2f} errors/min")
print(f"Parse errors: {metrics.parse_error_rate:.2f} errors/min")
print(f"Success rate: {metrics.protocol_success_rate:.2f}%")
```

### Getting Statistics Summary

```python
# Get dictionary of all statistics
stats = calculator.get_stats()

# Returns:
# {
#     'binary_packet_rate_1s': 10.5,
#     'binary_packet_rate_10s': 9.8,
#     'binary_packet_rate_60s': 9.2,
#     'mavlink_packet_rate_1s': 8.3,
#     'mavlink_packet_rate_10s': 7.9,
#     'mavlink_packet_rate_60s': 7.5,
#     'avg_rssi': -85.2,
#     'avg_snr': 10.5,
#     'drop_rate': 2.3,
#     'packets_lost': 5,
#     'packets_received': 212,
#     'latency_avg_ms': 145.3,
#     'latency_min_ms': 98.2,
#     'latency_max_ms': 203.7,
#     'latency_samples': 15,
#     'mavlink_msg_types': 8,
#     'binary_cmd_types': 4,
#     'checksum_error_rate': 2.1,
#     'parse_error_rate': 0.5,
#     'protocol_success_rate': 98.7,
#     'uptime_seconds': 125.3
# }
```

## Data Structures

### TelemetryMetrics

Complete metrics snapshot returned by `get_metrics()`:

```python
@dataclass
class TelemetryMetrics:
    # Packet rates (packets per second)
    binary_packet_rate_1s: float
    binary_packet_rate_10s: float
    binary_packet_rate_60s: float
    mavlink_packet_rate_1s: float
    mavlink_packet_rate_10s: float
    mavlink_packet_rate_60s: float
    
    # Link quality metrics
    avg_rssi: float  # dBm
    avg_snr: float   # dB
    
    # Packet loss metrics
    drop_rate: float  # Percentage
    packets_lost: int
    packets_received: int
    
    # Command latency (seconds)
    latency_avg: float
    latency_min: float
    latency_max: float
    latency_samples: int
    
    # Message type distribution
    mavlink_msg_type_distribution: Dict[str, int]
    binary_cmd_type_distribution: Dict[str, int]
    
    # Binary protocol health
    checksum_error_rate: float  # Errors per minute
    parse_error_rate: float     # Errors per minute
    protocol_success_rate: float  # Percentage
    
    # Timestamp
    timestamp: float
```

## Implementation Details

### Rolling Windows

The calculator uses `collections.deque` with `maxlen` to implement efficient rolling windows:

- **1-second window**: Stores up to 10,000 timestamps
- **10-second window**: Stores up to 10,000 timestamps
- **60-second window**: Stores up to 60,000 timestamps

When calculating rates, only timestamps within the window are counted.

### Packet Loss Detection

Packet loss is detected by tracking MAVLink sequence numbers (0-255) in HEARTBEAT messages:

1. Store last sequence number per system_id
2. When new HEARTBEAT arrives, calculate expected sequence (last + 1) % 256
3. If actual sequence != expected, calculate gap
4. Only count gaps < 100 to avoid false positives from sequence wrap-around

### Command Latency Tracking

Command latency is measured by matching COMMAND_LONG with COMMAND_ACK:

1. When COMMAND_LONG received, store timestamp with command_id
2. When COMMAND_ACK received, look up command_id
3. Calculate latency = current_time - stored_time
4. Store latency in rolling window (last 100 samples)

### RSSI/SNR Extraction

RSSI and SNR are extracted from binary protocol payloads:

- **BridgePayload**: Contains RSSI/SNR for bridge packets (CMD_BRIDGE_TX/RX)
- **StatusPayload**: Contains RSSI/SNR for status reports (CMD_STATUS_REPORT)

Values are stored in rolling windows (last 100 samples) and averaged.

### Error Rate Calculation

Error rates are calculated as errors per minute:

1. Store error timestamps in deque (last 1000 errors)
2. Count errors within time window (e.g., 60 seconds)
3. Convert to rate: (count / window_seconds) * 60

## Performance Considerations

- **Memory Usage**: Deques with maxlen prevent unbounded growth
- **Time Complexity**: O(n) for rate calculations where n is window size
- **Thread Safety**: Not thread-safe; use external locking if needed
- **Update Frequency**: Designed for real-time updates (10-100 Hz)

## Integration Example

```python
# Complete integration with parsers
from connection_manager import ConnectionManager, ConnectionType
from binary_protocol_parser import BinaryProtocolParser, MAVLinkExtractor
from mavlink_parser import MAVLinkParser
from metrics_calculator import MetricsCalculator

# Create components
conn = ConnectionManager(ConnectionType.SERIAL, port='/dev/ttyUSB0', baudrate=115200)
binary_parser = BinaryProtocolParser()
mavlink_extractor = MAVLinkExtractor()
calculator = MetricsCalculator()

# Connect
conn.connect()

# Main loop
while True:
    # Read data
    data = conn.read(1024)
    
    # Parse binary protocol
    binary_packets = binary_parser.parse_stream(data)
    
    for packet in binary_packets:
        # Update metrics with binary packet
        calculator.update_binary_packet(packet)
        
        # Extract MAVLink if present
        mavlink_msg = mavlink_extractor.extract_mavlink(packet)
        if mavlink_msg:
            # Update metrics with MAVLink message
            calculator.update_mavlink_message(mavlink_msg)
    
    # Record errors from parser
    parser_stats = binary_parser.get_stats()
    # Note: In real implementation, track delta of errors
    
    # Get metrics periodically
    if time.time() % 5 < 0.1:  # Every 5 seconds
        metrics = calculator.get_metrics()
        print(f"Binary rate: {metrics.binary_packet_rate_1s:.2f} pkt/s")
        print(f"MAVLink rate: {metrics.mavlink_packet_rate_1s:.2f} msg/s")
        print(f"RSSI: {metrics.avg_rssi:.2f} dBm")
        print(f"Drop rate: {metrics.drop_rate:.2f}%")
```

## Testing

Run the example script to see the metrics calculator in action:

```bash
cd telemetry_validation
python examples/metrics_calculator_example.py
```

The example demonstrates:
1. Basic usage with simulated data
2. Packet loss detection
3. Command latency tracking
4. Binary protocol health monitoring
5. Rolling window packet rates

## Error Handling

The calculator is designed to be robust:

- Handles missing RSSI/SNR gracefully (returns 0.0)
- Validates sequence number gaps to avoid false positives
- Handles missing command timestamps (no latency recorded)
- Protects against division by zero in rate calculations
- Logs warnings for unexpected conditions

## Future Enhancements

Potential improvements:

1. **Per-System Metrics**: Track metrics separately for each system_id
2. **Histogram Support**: Track latency and RSSI distributions
3. **Anomaly Detection**: Flag unusual metric patterns
4. **Metric Export**: Export metrics to time-series database
5. **Configurable Windows**: Allow custom window sizes
6. **Metric Alerts**: Trigger callbacks when metrics exceed thresholds

## See Also

- `binary_protocol_parser.py`: Binary protocol packet parsing
- `mavlink_parser.py`: MAVLink message parsing
- `validation_engine.py`: Telemetry validation rules
- `telemetry_logger.py`: Telemetry data logging
