# Binary Protocol Packet Logging

## Overview

The Binary Protocol Packet Logging feature provides comprehensive logging of raw binary protocol packets to `.binlog` files. This enables debugging, replay, and analysis of the custom UART protocol used between Primary and Secondary controllers.

**Requirements:** 1.1, 10.4

## Features

- **Complete Packet Logging**: Logs full binary packets including start byte, command, length, payload, and checksum
- **Replay Support**: Logged packets can be replayed for debugging and analysis
- **File Rotation**: Automatic rotation when file size exceeds configured limit
- **Minimal Overhead**: Efficient binary format with periodic flushing

## File Format

The `.binlog` format is a simple binary format that stores complete binary protocol packets sequentially:

```
[Packet 1][Packet 2][Packet 3]...
```

Each packet has the structure:
```
[Start Byte (0xAA)][Command (1 byte)][Length (2 bytes LE)][Payload (0-255 bytes)][Checksum (2 bytes LE)]
```

## Usage

### Basic Logging

```python
from src.telemetry_logger import TelemetryLogger
from src.binary_protocol_parser import BinaryProtocolParser

# Initialize logger
logger = TelemetryLogger(log_dir='./logs', max_file_size_mb=100)

# Initialize parser
parser = BinaryProtocolParser()

# Parse and log packets
data = serial_port.read(1024)
packets = parser.parse_stream(data)

for packet in packets:
    logger.log_binary_packet(packet)
```

### Logging Raw Bytes

You can also log raw bytes directly without parsing:

```python
# Log raw binary packet
raw_packet = b'\xaa\x01\x00\x00\x12\x34'
logger.log_binary_packet(raw_packet)
```

### Replay Logged Packets

```python
from src.binary_protocol_parser import BinaryProtocolParser

# Read binlog file
with open('telemetry_20241026_120000.binlog', 'rb') as f:
    data = f.read()

# Parse packets
parser = BinaryProtocolParser()
packets = parser.parse_stream(data)

# Process replayed packets
for packet in packets:
    print(f"Command: {packet.command.name}")
    print(f"Payload: {packet.payload}")
```

## API Reference

### TelemetryLogger.log_binary_packet()

```python
def log_binary_packet(self, packet)
```

Log a raw binary protocol packet to .binlog file.

**Parameters:**
- `packet`: ParsedBinaryPacket object or raw bytes

**Example:**
```python
# Log parsed packet
logger.log_binary_packet(parsed_packet)

# Log raw bytes
logger.log_binary_packet(raw_bytes)
```

### File Statistics

```python
stats = logger.get_stats()
print(f"Binary packets logged: {stats['binary_packet_count']}")
print(f"Binlog file: {stats['binlog_file']}")
```

## File Rotation

Binary log files are automatically rotated when the CSV file exceeds the configured size limit. When rotation occurs:

1. Current `.binlog` file is closed
2. New `.binlog` file is created with incremented sequence number
3. Logging continues to new file

Example file sequence:
```
telemetry_20241026_120000.binlog
telemetry_20241026_120530_1.binlog
telemetry_20241026_121045_2.binlog
```

## Performance Considerations

- **Buffering**: Packets are flushed to disk every 10 packets
- **File Size**: Binary format is very compact (no overhead beyond packet structure)
- **Memory**: Minimal memory usage as packets are written directly to disk

## Debugging with Binlog Files

### Verify Packet Structure

```python
import struct

with open('telemetry.binlog', 'rb') as f:
    # Read first packet
    start = f.read(1)
    if start[0] == 0xAA:
        command = f.read(1)[0]
        length = struct.unpack('<H', f.read(2))[0]
        payload = f.read(length)
        checksum = struct.unpack('<H', f.read(2))[0]
        
        print(f"Command: 0x{command:02X}")
        print(f"Length: {length}")
        print(f"Checksum: 0x{checksum:04X}")
```

### Compare with C++ Implementation

The `.binlog` format matches the binary protocol used in the C++ firmware, allowing direct comparison:

```cpp
// C++ side (BinaryProtocol.h)
sendBinaryPacket(uart, CMD_BRIDGE_TX, &payload, sizeof(payload), &stats);

// Python side (replay)
parser = BinaryProtocolParser()
packets = parser.parse_stream(binlog_data)
# Verify packet matches C++ transmission
```

## Integration with Other Components

### With Connection Manager

```python
from src.connection_manager import ConnectionManager, ConnectionType

conn = ConnectionManager(ConnectionType.SERIAL, port='/dev/ttyUSB0')
conn.connect()

while True:
    data = conn.read(1024)
    packets = parser.parse_stream(data)
    
    for packet in packets:
        logger.log_binary_packet(packet)
```

### With MAVLink Extraction

```python
from src.binary_protocol_parser import MAVLinkExtractor

extractor = MAVLinkExtractor()

for packet in packets:
    # Log binary packet
    logger.log_binary_packet(packet)
    
    # Extract MAVLink if present
    mavlink_msg = extractor.extract_mavlink(packet)
    if mavlink_msg:
        logger.log_message(mavlink_msg)
```

## Troubleshooting

### Binlog File Not Created

**Problem**: `.binlog` file is not created

**Solution**: Ensure logger is initialized and `log_binary_packet()` is called:
```python
logger = TelemetryLogger(log_dir='./logs')
logger.log_binary_packet(packet)  # Must call this method
```

### Replay Fails

**Problem**: Cannot parse replayed packets

**Solution**: Verify file integrity and checksum:
```python
parser = BinaryProtocolParser()
packets = parser.parse_stream(data)

stats = parser.get_stats()
if stats['checksum_errors'] > 0:
    print("Warning: Checksum errors detected in binlog file")
```

### File Size Growing Too Fast

**Problem**: `.binlog` files are very large

**Solution**: Reduce max file size or implement filtering:
```python
# Only log specific commands
if packet.command in [UartCommand.CMD_BRIDGE_TX, UartCommand.CMD_BRIDGE_RX]:
    logger.log_binary_packet(packet)
```

## Examples

See `examples/binary_packet_logging_example.py` for complete working examples.

## Related Documentation

- [Binary Protocol Parser](README_BinaryProtocolParser.md)
- [Telemetry Logger](README_TelemetryLogger.md)
- [Connection Manager](README_ConnectionManager.md)
- [Binary Protocol Specification](../../include/README_BinaryProtocol.md)
