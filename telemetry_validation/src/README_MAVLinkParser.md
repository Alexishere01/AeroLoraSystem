# MAVLink Parser Module

## Overview

The MAVLink Parser module provides robust parsing capabilities for MAVLink telemetry data streams. It handles continuous data streams from serial ports or UDP sockets, managing packet fragmentation, validation, and link quality metrics extraction.

## Features

- **Continuous Stream Parsing**: Handles fragmented packets across multiple data chunks
- **Buffer Management**: Maintains internal buffer for incomplete packets
- **Statistics Tracking**: Monitors parse success, errors, and data throughput
- **RSSI/SNR Extraction**: Automatically extracts and attaches link quality metrics from RADIO_STATUS messages
- **Error Handling**: Gracefully handles malformed packets and checksum errors
- **MAVLink v1/v2 Support**: Compatible with both MAVLink protocol versions

## Classes

### ParsedMessage

A dataclass representing a parsed MAVLink message with all relevant metadata.

**Attributes:**
- `timestamp` (float): Unix timestamp when message was parsed
- `msg_type` (str): MAVLink message type name (e.g., 'HEARTBEAT', 'GPS_RAW_INT')
- `msg_id` (int): Numeric message ID
- `system_id` (int): Source system ID
- `component_id` (int): Source component ID
- `fields` (dict): Dictionary of message fields and their values
- `rssi` (Optional[float]): Received Signal Strength Indicator in dBm
- `snr` (Optional[float]): Signal-to-Noise Ratio in dB
- `raw_bytes` (bytes): Raw MAVLink packet bytes

### MAVLinkParser

Main parser class for processing MAVLink data streams.

**Methods:**

#### `__init__()`
Initialize the parser with empty buffer and statistics.

```python
parser = MAVLinkParser()
```

#### `parse_stream(data: bytes) -> List[ParsedMessage]`
Parse incoming data and return list of complete messages.

**Parameters:**
- `data`: Raw bytes from serial port or UDP socket

**Returns:**
- List of ParsedMessage objects for all complete packets found

**Example:**
```python
data = serial_port.read(1024)
messages = parser.parse_stream(data)

for msg in messages:
    print(f"Received {msg.msg_type} from system {msg.system_id}")
    if msg.rssi is not None:
        print(f"  RSSI: {msg.rssi} dBm")
```

#### `get_stats() -> dict`
Get current parser statistics.

**Returns:**
Dictionary containing:
- `total_packets`: Total successfully parsed packets
- `parse_errors`: Number of parse errors encountered
- `checksum_errors`: Number of checksum validation failures
- `unknown_messages`: Number of unknown message types
- `bytes_processed`: Total bytes processed
- `buffer_size`: Current buffer size
- `last_rssi`: Most recent RSSI value
- `last_snr`: Most recent SNR value
- `error_rate`: Percentage of failed parse attempts

**Example:**
```python
stats = parser.get_stats()
print(f"Parsed {stats['total_packets']} packets")
print(f"Error rate: {stats['error_rate']:.2f}%")
```

#### `reset_stats()`
Reset all statistics counters to zero.

```python
parser.reset_stats()
```

#### `clear_buffer()`
Clear the internal buffer. Useful for recovering from errors.

```python
parser.clear_buffer()
```

## Usage Examples

### Basic Parsing

```python
from src.mavlink_parser import MAVLinkParser
from src.connection_manager import ConnectionManager, ConnectionType

# Initialize parser
parser = MAVLinkParser()

# Connect to data source
conn = ConnectionManager(ConnectionType.SERIAL, port='/dev/ttyUSB0', baudrate=57600)
conn.connect()

# Parse data
while True:
    data = conn.read(1024)
    messages = parser.parse_stream(data)
    
    for msg in messages:
        print(f"{msg.msg_type}: {msg.fields}")
```

### Monitoring Link Quality

```python
# Parse messages and monitor RSSI/SNR
while True:
    data = conn.read(1024)
    messages = parser.parse_stream(data)
    
    for msg in messages:
        if msg.rssi is not None:
            print(f"Link quality: RSSI={msg.rssi} dBm, SNR={msg.snr} dB")
            
            if msg.rssi < -100:
                print("WARNING: Weak signal!")
```

### Statistics Monitoring

```python
import time

start_time = time.time()

while time.time() - start_time < 60:  # Run for 60 seconds
    data = conn.read(1024)
    messages = parser.parse_stream(data)
    
    # Process messages...

# Print final statistics
stats = parser.get_stats()
print(f"Total packets: {stats['total_packets']}")
print(f"Parse errors: {stats['parse_errors']}")
print(f"Error rate: {stats['error_rate']:.2f}%")
```

### Handling Fragmented Packets

The parser automatically handles packets split across multiple reads:

```python
# Packet may be split across multiple reads
data1 = conn.read(100)  # First part of packet
messages1 = parser.parse_stream(data1)  # Returns []

data2 = conn.read(100)  # Rest of packet
messages2 = parser.parse_stream(data2)  # Returns [complete_message]
```

## RSSI/SNR Extraction

The parser automatically extracts RSSI and SNR values from RADIO_STATUS messages and attaches them to subsequent messages until a new RADIO_STATUS is received.

**RADIO_STATUS Fields Used:**
- `rssi`: Local RSSI value
- `remrssi`: Remote RSSI value (preferred)
- `noise`: Local noise floor
- `remnoise`: Remote noise floor

**SNR Calculation:**
```
SNR = RSSI - Noise Floor
```

**Example:**
```python
# RADIO_STATUS message arrives
# Parser extracts: RSSI=-80 dBm, Noise=-95 dBm
# Calculated SNR: 15 dB

# Next HEARTBEAT message will have:
# msg.rssi = -80
# msg.snr = 15

# These values persist until next RADIO_STATUS
```

## Error Handling

The parser handles various error conditions gracefully:

1. **Invalid Start Bytes**: Discarded and parsing continues
2. **Checksum Errors**: Logged and counted in statistics
3. **Parse Errors**: Logged and counted in statistics
4. **Incomplete Packets**: Buffered until complete

**Example:**
```python
# Mixed valid and invalid data
data = b'\x00\x01\x02' + valid_mavlink_packet + b'\xFF\xFF'

messages = parser.parse_stream(data)
# Returns only the valid message, invalid bytes are discarded

stats = parser.get_stats()
print(f"Errors encountered: {stats['parse_errors']}")
```

## Performance Considerations

- **Buffer Size**: The internal buffer grows as needed for incomplete packets
- **Memory Usage**: Minimal - only incomplete packets are buffered
- **CPU Usage**: Efficient byte-by-byte parsing with early rejection of invalid data
- **Throughput**: Can handle typical MAVLink data rates (10-100 Hz) with ease

## Integration with Other Modules

The MAVLink Parser integrates seamlessly with other telemetry validation components:

```python
from src.connection_manager import ConnectionManager, ConnectionType
from src.mavlink_parser import MAVLinkParser
from src.telemetry_logger import TelemetryLogger
from src.validation_engine import ValidationEngine

# Set up pipeline
conn = ConnectionManager(ConnectionType.SERIAL, port='/dev/ttyUSB0')
parser = MAVLinkParser()
logger = TelemetryLogger()
validator = ValidationEngine()

conn.connect()

while True:
    # Read and parse
    data = conn.read(1024)
    messages = parser.parse_stream(data)
    
    # Process each message
    for msg in messages:
        logger.log_message(msg)
        violations = validator.validate_message(msg)
        
        if violations:
            print(f"Validation violations: {violations}")
```

## Testing

Run the unit tests:

```bash
cd telemetry_validation
python -m pytest tests/test_mavlink_parser.py -v
```

Run the example:

```bash
cd telemetry_validation
python examples/mavlink_parser_example.py
```

## Troubleshooting

### No Messages Parsed

**Problem**: `parse_stream()` returns empty list

**Solutions:**
1. Verify data source is sending MAVLink packets
2. Check that data is not empty: `if data: messages = parser.parse_stream(data)`
3. Verify MAVLink protocol version matches (v1 or v2)
4. Check statistics for errors: `parser.get_stats()`

### High Error Rate

**Problem**: `error_rate` in statistics is high

**Solutions:**
1. Check physical connection quality
2. Verify baud rate matches data source
3. Check for electromagnetic interference
4. Review error logs for specific error types

### Buffer Growing Indefinitely

**Problem**: `buffer_size` keeps increasing

**Solutions:**
1. Data source may not be sending valid MAVLink
2. Clear buffer periodically: `parser.clear_buffer()`
3. Check for synchronization issues

### Missing RSSI/SNR

**Problem**: `msg.rssi` and `msg.snr` are None

**Solutions:**
1. Verify data source sends RADIO_STATUS messages
2. Check that RADIO_STATUS contains rssi/noise fields
3. Some systems don't provide RADIO_STATUS - this is normal

## References

- [MAVLink Protocol Documentation](https://mavlink.io/en/)
- [pymavlink Library](https://github.com/ArduPilot/pymavlink)
- [MAVLink Message Definitions](https://mavlink.io/en/messages/common.html)
