# TelemetryLogger Module

## Overview

The `TelemetryLogger` module provides comprehensive logging capabilities for MAVLink telemetry data. It supports multiple output formats (CSV, JSON, .tlog) with automatic file rotation and buffered writes for optimal performance.

## Features

- **Multi-format logging**: Simultaneously logs to CSV, JSON, .tlog, and .binlog formats
- **Binary protocol support**: Logs raw binary protocol packets to .binlog files for debugging and replay
- **Timestamped filenames**: Automatic filename generation with timestamps
- **File rotation**: Automatic rotation when files reach configurable size limit
- **Buffered writes**: JSON data is buffered in memory for performance
- **QGC compatibility**: .tlog format is compatible with QGroundControl and MAVProxy
- **Statistics tracking**: Tracks message counts and file information
- **Graceful shutdown**: Flushes all buffers and writes summary on close

## Requirements Addressed

This implementation addresses the following requirements from the specification:

- **Requirement 1.1**: Creates timestamped log files in CSV format
- **Requirement 1.2**: Parses and logs MAVLink packets with all relevant fields
- **Requirement 1.3**: Implements file rotation at 100 MB (configurable)
- **Requirement 1.4**: Closes files and writes summary on shutdown
- **Requirement 1.5**: Buffers writes to minimize performance impact
- **Requirement 10.3**: Exports to JSON with structured nested objects
- **Requirement 10.4**: Exports to .tlog format for QGC/MAVProxy compatibility

## Usage

### Basic Usage

```python
from src.telemetry_logger import TelemetryLogger
from src.mavlink_parser import MAVLinkParser, ParsedMessage

# Initialize logger
logger = TelemetryLogger(
    log_dir='./telemetry_logs',
    max_file_size_mb=100
)

# Log a message
msg = ParsedMessage(
    timestamp=time.time(),
    msg_type='HEARTBEAT',
    msg_id=0,
    system_id=1,
    component_id=1,
    fields={'type': 2, 'autopilot': 3},
    rssi=-50.0,
    snr=10.0,
    raw_bytes=b'\xfe\x09\x00\x01\x01\x00'
)

logger.log_message(msg)

# Close logger when done
logger.close()
```

### Integration with Parser and Connection Manager

```python
from src.connection_manager import ConnectionManager, ConnectionType
from src.mavlink_parser import MAVLinkParser
from src.telemetry_logger import TelemetryLogger

# Initialize components
conn = ConnectionManager(ConnectionType.UDP, port=14550)
parser = MAVLinkParser()
logger = TelemetryLogger(log_dir='./logs')

# Connect
conn.connect()

# Main loop
try:
    while True:
        # Read data
        data = conn.read(1024)
        
        # Parse messages
        messages = parser.parse_stream(data)
        
        # Log each message
        for msg in messages:
            logger.log_message(msg)
            
except KeyboardInterrupt:
    pass
finally:
    conn.disconnect()
    logger.close()
```

### Custom Configuration

```python
# Custom log directory and file size limit
logger = TelemetryLogger(
    log_dir='/var/log/telemetry',
    max_file_size_mb=50  # Rotate at 50 MB
)

# Get statistics
stats = logger.get_stats()
print(f"Messages logged: {stats['message_count']}")
print(f"Current CSV file: {stats['csv_file']}")
print(f"File sequence: {stats['file_sequence']}")
```

## Output Formats

### CSV Format

The CSV file contains the following columns:

- `timestamp`: Unix timestamp when message was received
- `msg_type`: MAVLink message type name (e.g., 'HEARTBEAT')
- `msg_id`: Numeric message ID
- `system_id`: Source system ID
- `component_id`: Source component ID
- `fields`: JSON string containing all message fields
- `rssi`: Received Signal Strength Indicator (dBm)
- `snr`: Signal-to-Noise Ratio (dB)

Example CSV content:
```csv
timestamp,msg_type,msg_id,system_id,component_id,fields,rssi,snr
1698765432.123,HEARTBEAT,0,1,1,"{""type"": 2, ""autopilot"": 3}",-50.0,10.0
1698765432.456,GPS_RAW_INT,24,1,1,"{""lat"": 37000000, ""lon"": -122000000}",-52.0,9.5
```

### JSON Format

The JSON file contains an array of message objects with nested field structures:

```json
[
  {
    "timestamp": 1698765432.123,
    "msg_type": "HEARTBEAT",
    "msg_id": 0,
    "system_id": 1,
    "component_id": 1,
    "fields": {
      "type": 2,
      "autopilot": 3,
      "base_mode": 81
    },
    "rssi": -50.0,
    "snr": 10.0
  },
  {
    "timestamp": 1698765432.456,
    "msg_type": "GPS_RAW_INT",
    "msg_id": 24,
    "system_id": 1,
    "component_id": 1,
    "fields": {
      "lat": 37000000,
      "lon": -122000000,
      "alt": 100000
    },
    "rssi": -52.0,
    "snr": 9.5
  }
]
```

### .tlog Format

The .tlog file contains raw MAVLink packet bytes in binary format. This format is compatible with:

- QGroundControl (for replay and analysis)
- MAVProxy (for mission replay)
- Other MAVLink analysis tools

The .tlog file is a simple concatenation of raw MAVLink packets with no additional headers or metadata.

### .binlog Format

The .binlog file contains raw binary protocol packets in their complete form, including:

- Start byte (0xAA)
- Command byte
- Length field (2 bytes, little-endian)
- Payload (0-255 bytes)
- Fletcher-16 checksum (2 bytes, little-endian)

This format enables:
- **Debugging**: Inspect complete binary protocol communication
- **Replay**: Re-parse logged packets for testing
- **Analysis**: Verify protocol implementation and checksum validation

Example usage:
```python
from src.binary_protocol_parser import BinaryProtocolParser

# Log binary protocol packets
parser = BinaryProtocolParser()
packets = parser.parse_stream(serial_data)

for packet in packets:
    logger.log_binary_packet(packet)

# Later, replay from .binlog file
with open('telemetry_20241024_143022.binlog', 'rb') as f:
    data = f.read()

replay_parser = BinaryProtocolParser()
replayed_packets = replay_parser.parse_stream(data)
```

See [Binary Packet Logging Documentation](README_BinaryPacketLogging.md) for more details.

## File Rotation

Files are automatically rotated when the CSV file size exceeds the configured limit:

1. Current files are closed
2. JSON buffer is flushed
3. File sequence number is incremented
4. New files are created with updated sequence number

Example filename progression:
```
telemetry_20241024_143022.csv       # Initial file
telemetry_20241024_143022.json
telemetry_20241024_143022.tlog
telemetry_20241024_143022.binlog

telemetry_20241024_144530_1.csv     # After first rotation
telemetry_20241024_144530_1.json
telemetry_20241024_144530_1.tlog
telemetry_20241024_144530_1.binlog

telemetry_20241024_150045_2.csv     # After second rotation
telemetry_20241024_150045_2.json
telemetry_20241024_150045_2.tlog
telemetry_20241024_150045_2.binlog
```

## Performance Considerations

### Buffered Writes

- **CSV**: Flushed every 10 messages for real-time viewing
- **JSON**: Buffered in memory (100 messages) and flushed periodically
- **.tlog**: Flushed every 10 messages for data integrity
- **.binlog**: Flushed every 10 packets for data integrity

### Memory Usage

- JSON buffer holds up to 100 messages in memory (~10-50 KB typical)
- CSV and .tlog use minimal buffering (OS-level)
- File rotation prevents unbounded disk usage

### CPU Impact

The logger is designed to have minimal CPU impact:
- Simple CSV writing with minimal formatting
- Batch JSON writes reduce I/O operations
- Direct binary writes for .tlog format
- No complex processing or transformations

## Error Handling

The logger handles errors gracefully:

- **File I/O errors**: Logged and operation continues if possible
- **Disk full**: Rotation may fail, but logging continues to current files
- **Permission errors**: Logged at initialization, exception raised
- **Invalid messages**: Logged as errors, but don't stop logging

## Summary File

When the logger is closed, a summary file is generated:

```
Telemetry Logging Summary
==================================================

Total MAVLink messages logged: 12543
Total binary protocol packets logged: 15678
File rotations: 2
Log directory: ./telemetry_logs
Session ended: 2024-10-24 14:35:22
```

## API Reference

### TelemetryLogger Class

#### Constructor

```python
TelemetryLogger(log_dir: str = './telemetry_logs', max_file_size_mb: int = 100)
```

**Parameters:**
- `log_dir`: Directory to store log files (created if doesn't exist)
- `max_file_size_mb`: Maximum file size in MB before rotation

#### Methods

##### log_message(msg: ParsedMessage)

Log a parsed MAVLink message to all formats.

**Parameters:**
- `msg`: ParsedMessage object to log

##### close()

Close all log files and flush buffered data. Writes a summary file.

##### get_stats() -> dict

Get logging statistics.

**Returns:**
Dictionary containing:
- `message_count`: Total messages logged
- `file_sequence`: Current file sequence number
- `csv_file`: Path to current CSV file
- `json_file`: Path to current JSON file
- `tlog_file`: Path to current .tlog file
- `json_buffer_size`: Number of messages in JSON buffer

## Testing

### Unit Tests

Run the unit tests:

```bash
cd telemetry_validation
python -m pytest tests/test_telemetry_logger.py -v
```

### Validation Script

Run the comprehensive validation:

```bash
cd telemetry_validation
python validate_telemetry_logger.py
```

### Example Script

Run the example to see the logger in action:

```bash
cd telemetry_validation
python examples/telemetry_logger_example.py
```

## Integration with Other Components

The TelemetryLogger integrates seamlessly with:

- **ConnectionManager**: Receives data from serial or UDP connections
- **MAVLinkParser**: Logs ParsedMessage objects from the parser
- **ValidationEngine**: Can log validation violations (future)
- **MetricsCalculator**: Can log calculated metrics (future)

## Future Enhancements

Potential improvements for future versions:

1. **Compression**: Compress rotated files to save disk space
2. **Remote logging**: Send logs to remote server or cloud storage
3. **Filtering**: Log only specific message types or systems
4. **Encryption**: Encrypt sensitive telemetry data
5. **Database backend**: Store logs in SQLite or other database
6. **Real-time streaming**: Stream logs to web dashboard

## Troubleshooting

### Files not being created

- Check that log directory exists and is writable
- Verify sufficient disk space
- Check file permissions

### File rotation not working

- Verify max_file_size_mb is set appropriately
- Check that enough messages are being logged to exceed limit
- Monitor file sizes manually

### JSON file empty or incomplete

- Ensure logger.close() is called before program exit
- Check that _flush_json() is being called periodically
- Verify no exceptions during JSON serialization

### .tlog file not compatible with QGC

- Ensure raw_bytes are being captured by parser
- Verify MAVLink packets are valid
- Check that .tlog file is not corrupted

## License

This module is part of the Telemetry Validation System for the dual-controller LoRa relay project.
