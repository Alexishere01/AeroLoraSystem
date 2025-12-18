# Binary Protocol Parser

The Binary Protocol Parser component parses the custom binary UART protocol used for communication between Primary and Secondary controllers in the dual-controller LoRa relay system.

## Overview

The binary protocol wraps MAVLink packets in structured frames with metadata (RSSI, SNR) and error detection (Fletcher-16 checksum). This parser implements a robust state machine to handle byte-by-byte parsing with error recovery.

## Features

- **State Machine Parser**: Robust byte-by-byte parsing with automatic resynchronization
- **Fletcher-16 Checksum**: Validates packet integrity
- **MAVLink Extraction**: Extracts embedded MAVLink messages from BridgePayload
- **Multiple Command Types**: Supports INIT, BRIDGE_TX/RX, STATUS_REPORT, RELAY commands
- **Protocol Health Monitoring**: Tracks checksum errors, parse errors, timeouts
- **Error Recovery**: Automatic resynchronization on parse errors

## Protocol Structure

### Packet Format

```
┌──────────┬─────────┬────────┬─────────────┬──────────┐
│ START    │ COMMAND │ LENGTH │   PAYLOAD   │ CHECKSUM │
│ (1 byte) │ (1 byte)│(2 bytes)│ (0-255 bytes)│ (2 bytes)│
└──────────┴─────────┴────────┴─────────────┴──────────┘
```

- **START**: Always `0xAA`
- **COMMAND**: Command type (see UartCommand enum)
- **LENGTH**: Payload length in bytes (little-endian)
- **PAYLOAD**: Command-specific data
- **CHECKSUM**: Fletcher-16 checksum (little-endian)

### Command Types

| Command | Value | Description |
|---------|-------|-------------|
| `CMD_INIT` | 0x01 | Initialization handshake |
| `CMD_BRIDGE_TX` | 0x06 | Bridge packet from GCS to mesh |
| `CMD_BRIDGE_RX` | 0x07 | Bridge packet from mesh to GCS |
| `CMD_STATUS_REPORT` | 0x08 | Periodic status update |
| `CMD_RELAY_ACTIVATE` | 0x03 | Activate relay mode |
| `CMD_RELAY_RX` | 0x05 | Relay received packet |
| `CMD_ACK` | 0x02 | Acknowledgment |

## Usage

### Basic Usage

```python
from src.binary_protocol_parser import BinaryProtocolParser

# Create parser
parser = BinaryProtocolParser()

# Parse incoming data
data = serial_port.read(1024)
packets = parser.parse_stream(data)

# Process packets
for packet in packets:
    print(f"Command: {packet.command}")
    print(f"Timestamp: {packet.timestamp}")
    print(f"Payload: {packet.payload}")
```

### Extract MAVLink from Bridge Packets

```python
# Parse binary protocol
packets = parser.parse_stream(data)

for packet in packets:
    # Check if packet contains MAVLink
    if packet.command in ['CMD_BRIDGE_TX', 'CMD_BRIDGE_RX']:
        # Extract MAVLink message
        mavlink_msg = parser.extract_mavlink(packet)
        
        if mavlink_msg:
            print(f"MAVLink Type: {mavlink_msg.msg_type}")
            print(f"System ID: {mavlink_msg.system_id}")
            print(f"RSSI: {mavlink_msg.rssi} dBm")
            print(f"SNR: {mavlink_msg.snr} dB")
            print(f"Fields: {mavlink_msg.fields}")
```

### Monitor Protocol Health

```python
# Get parser statistics
stats = parser.get_stats()

print(f"Packets received: {stats['packets_received']}")
print(f"Checksum errors: {stats['checksum_errors']}")
print(f"Parse errors: {stats['parse_errors']}")
print(f"Success rate: {stats['success_rate']:.1f}%")

# Check for issues
if stats['checksum_error_rate'] > 5.0:
    print("WARNING: High checksum error rate!")
if stats['success_rate'] < 90.0:
    print("WARNING: Low success rate!")
```

### Enable Debug Logging

```python
# Enable debug output
parser = BinaryProtocolParser(debug=True)

# Parse data - will print detailed debug info
packets = parser.parse_stream(data)
```

## API Reference

### BinaryProtocolParser

Main parser class.

#### Constructor

```python
BinaryProtocolParser(debug: bool = False)
```

**Parameters**:
- `debug`: Enable debug logging (default: False)

#### Methods

##### parse_stream()

```python
parse_stream(data: bytes) -> List[ParsedBinaryPacket]
```

Parse incoming byte stream and return list of complete packets.

**Parameters**:
- `data`: Raw bytes from serial port or UDP socket

**Returns**:
- List of `ParsedBinaryPacket` objects

**Example**:
```python
data = serial_port.read(1024)
packets = parser.parse_stream(data)
```

##### extract_mavlink()

```python
extract_mavlink(packet: ParsedBinaryPacket) -> Optional[ParsedMessage]
```

Extract MAVLink message from BridgePayload packet.

**Parameters**:
- `packet`: Parsed binary protocol packet

**Returns**:
- `ParsedMessage` object with MAVLink data, or None if extraction fails

**Example**:
```python
if packet.command == 'CMD_BRIDGE_RX':
    mavlink_msg = parser.extract_mavlink(packet)
    if mavlink_msg:
        print(f"MAVLink: {mavlink_msg.msg_type}")
```

##### get_stats()

```python
get_stats() -> Dict[str, Any]
```

Get parser statistics.

**Returns**:
- Dictionary with statistics:
  - `packets_received`: Total valid packets
  - `checksum_errors`: Checksum validation failures
  - `parse_errors`: Parse errors
  - `timeout_errors`: Timeout events
  - `unknown_commands`: Unknown command types
  - `buffer_overflow`: Buffer overflow events
  - `success_rate`: Percentage of valid packets
  - `checksum_error_rate`: Percentage of checksum errors

**Example**:
```python
stats = parser.get_stats()
print(f"Success rate: {stats['success_rate']:.1f}%")
```

##### reset_stats()

```python
reset_stats() -> None
```

Reset parser statistics to zero.

**Example**:
```python
parser.reset_stats()
```

### Data Classes

#### ParsedBinaryPacket

Represents a parsed binary protocol packet.

**Fields**:
- `timestamp`: float - Packet timestamp (seconds since epoch)
- `command`: str - Command type name (e.g., "CMD_BRIDGE_TX")
- `command_value`: int - Command type value (e.g., 0x06)
- `payload`: Dict[str, Any] - Parsed payload data
- `raw_bytes`: bytes - Raw packet bytes
- `checksum_valid`: bool - Checksum validation result

#### ParsedMessage

Represents a parsed MAVLink message (from extract_mavlink).

**Fields**:
- `timestamp`: float - Message timestamp
- `msg_type`: str - MAVLink message type (e.g., "HEARTBEAT")
- `msg_id`: int - MAVLink message ID
- `system_id`: int - MAVLink system ID
- `component_id`: int - MAVLink component ID
- `fields`: Dict[str, Any] - Message fields
- `rssi`: Optional[float] - RSSI in dBm (from BridgePayload)
- `snr`: Optional[float] - SNR in dB (from BridgePayload)
- `raw_bytes`: bytes - Raw MAVLink bytes

## Payload Structures

### InitPayload

Initialization handshake payload.

**Fields**:
- `mode`: str - Operating mode (e.g., "FREQUENCY_BRIDGE")
- `primary_freq`: float - Primary frequency in MHz
- `secondary_freq`: float - Secondary frequency in MHz
- `timestamp`: int - Milliseconds since boot

**Size**: 28 bytes

### BridgePayload

Bridge packet payload containing MAVLink data.

**Fields**:
- `system_id`: int - MAVLink system ID
- `rssi`: float - RSSI in dBm
- `snr`: float - SNR in dB
- `data_len`: int - MAVLink packet length
- `data`: bytes - Raw MAVLink packet

**Size**: 11 + data_len bytes (max 256 bytes)

### StatusPayload

System status report payload.

**Fields**:
- `uptime_ms`: int - System uptime in milliseconds
- `relay_active`: int - 1 if relay mode active, 0 otherwise
- `packets_relayed`: int - Count of packets relayed
- `active_peer_relays`: int - Number of active peer relays
- `avg_rssi`: float - Average RSSI in dBm
- `avg_snr`: float - Average SNR in dB
- `buffer_usage`: int - Buffer usage percentage (0-100)

**Size**: 15 bytes

### RelayActivatePayload

Relay activation payload.

**Fields**:
- `target_system_id`: int - System ID to relay for
- `relay_priority`: int - Relay priority (0-255)

**Size**: 2 bytes

### RelayRxPayload

Relay received packet payload.

**Fields**:
- `source_system_id`: int - Original source system ID
- `relay_hop_count`: int - Number of relay hops
- `rssi`: float - RSSI at relay node
- `snr`: float - SNR at relay node
- `data_len`: int - Data length
- `data`: bytes - Relayed data

**Size**: 7 + data_len bytes (max 252 bytes)

## State Machine

The parser uses a state machine for robust parsing:

```
WAIT_START → READ_HEADER → READ_PAYLOAD → READ_CHECKSUM → VALIDATE
     ↑                                                          │
     └──────────────────────────────────────────────────────────┘
```

### States

1. **WAIT_START**: Looking for start byte (0xAA)
2. **READ_HEADER**: Reading command (1 byte) and length (2 bytes)
3. **READ_PAYLOAD**: Reading payload data (length bytes)
4. **READ_CHECKSUM**: Reading checksum (2 bytes)
5. **VALIDATE**: Validating checksum and emitting packet

### Error Recovery

On parse error or checksum failure:
1. Increment error counter
2. Log error details
3. Return to WAIT_START state
4. Attempt to resynchronize with next start byte

## Fletcher-16 Checksum

The protocol uses Fletcher-16 checksum for error detection.

### Algorithm

```python
def fletcher16(data: bytes) -> int:
    sum1 = 0
    sum2 = 0
    for byte in data:
        sum1 = (sum1 + byte) % 255
        sum2 = (sum2 + sum1) % 255
    return (sum2 << 8) | sum1
```

### Validation

Checksum is calculated over COMMAND + LENGTH + PAYLOAD fields:

```python
# Calculate checksum
checksum_data = command_byte + length_bytes + payload_bytes
calculated_checksum = fletcher16(checksum_data)

# Compare with received checksum
if calculated_checksum == received_checksum:
    # Packet valid
else:
    # Checksum error
```

## Error Handling

### Checksum Errors

When checksum validation fails:
- Increment `checksum_errors` counter
- Log error with packet details
- Discard packet
- Return to WAIT_START state
- Alert if error rate exceeds threshold (>5%)

### Parse Errors

When parsing fails (invalid length, buffer overflow):
- Increment `parse_errors` counter
- Log error with context
- Discard partial packet
- Return to WAIT_START state
- Attempt to resynchronize

### Timeout Errors

When no data received for timeout period:
- Increment `timeout_errors` counter
- Log timeout event
- Maintain connection state
- Alert if timeouts frequent

### Unknown Commands

When unknown command type received:
- Increment `unknown_commands` counter
- Log command value
- Skip packet
- Continue parsing

## Performance Considerations

### Buffer Management
- Uses circular buffer for incoming data
- Limits buffer size to prevent memory exhaustion
- Flushes old data if buffer full

### Parsing Efficiency
- State machine avoids backtracking
- Minimal memory allocations
- Efficient checksum calculation
- No blocking operations

### Memory Usage
- Bounded buffer size
- Efficient data structures
- Automatic cleanup of old packets

## Examples

### Complete Example

```python
from src.binary_protocol_parser import BinaryProtocolParser
from src.connection_manager import ConnectionManager, ConnectionType

# Create connection
conn = ConnectionManager(
    conn_type=ConnectionType.SERIAL,
    port='/dev/ttyUSB0',
    baudrate=115200
)
conn.connect()

# Create parser
parser = BinaryProtocolParser(debug=False)

# Main loop
try:
    while True:
        # Read data
        data = conn.read(1024)
        if not data:
            continue
        
        # Parse packets
        packets = parser.parse_stream(data)
        
        # Process packets
        for packet in packets:
            print(f"\n[{packet.timestamp:.3f}] {packet.command}")
            
            # Handle different command types
            if packet.command == 'CMD_INIT':
                print(f"  Mode: {packet.payload['mode']}")
                print(f"  Primary Freq: {packet.payload['primary_freq']} MHz")
                
            elif packet.command in ['CMD_BRIDGE_TX', 'CMD_BRIDGE_RX']:
                # Extract MAVLink
                mavlink_msg = parser.extract_mavlink(packet)
                if mavlink_msg:
                    print(f"  MAVLink: {mavlink_msg.msg_type}")
                    print(f"  System ID: {mavlink_msg.system_id}")
                    print(f"  RSSI: {mavlink_msg.rssi} dBm")
                    print(f"  SNR: {mavlink_msg.snr} dB")
                    
            elif packet.command == 'CMD_STATUS_REPORT':
                print(f"  Uptime: {packet.payload['uptime_ms']} ms")
                print(f"  Relay Active: {packet.payload['relay_active']}")
                print(f"  Packets Relayed: {packet.payload['packets_relayed']}")
                print(f"  Avg RSSI: {packet.payload['avg_rssi']} dBm")
        
        # Print statistics every 100 packets
        stats = parser.get_stats()
        if stats['packets_received'] % 100 == 0:
            print(f"\nStatistics:")
            print(f"  Packets: {stats['packets_received']}")
            print(f"  Checksum Errors: {stats['checksum_errors']}")
            print(f"  Success Rate: {stats['success_rate']:.1f}%")

except KeyboardInterrupt:
    print("\nStopping...")
finally:
    conn.disconnect()
```

### Packet Logging Example

```python
# Log raw binary packets for debugging
with open('packets.binlog', 'wb') as f:
    for packet in packets:
        f.write(packet.raw_bytes)
```

### Replay Logged Packets

```python
# Replay logged packets
with open('packets.binlog', 'rb') as f:
    data = f.read()
    packets = parser.parse_stream(data)
    
    for packet in packets:
        print(f"{packet.command}: {packet.payload}")
```

## Troubleshooting

### High Checksum Error Rate

**Symptoms**: `checksum_error_rate > 5%`

**Solutions**:
1. Check UART connection quality
2. Reduce baud rate
3. Check for electrical interference
4. Verify protocol version compatibility

### Parse Errors

**Symptoms**: `parse_errors` increasing

**Solutions**:
1. Check protocol synchronization
2. Verify protocol implementation
3. Check buffer size
4. Enable debug logging

### Cannot Extract MAVLink

**Symptoms**: `extract_mavlink()` returns None

**Solutions**:
1. Verify command type is BRIDGE_TX or BRIDGE_RX
2. Check MAVLink packet integrity
3. Verify data_len field
4. Enable MAVLink debug logging

### No Packets Received

**Symptoms**: `packets_received == 0`

**Solutions**:
1. Check connection is active
2. Verify data is being transmitted
3. Check protocol mode (binary vs MAVLink)
4. Enable debug logging

## See Also

- [BINARY_PROTOCOL.md](../../BINARY_PROTOCOL.md) - Protocol specification
- [../include/BinaryProtocol.h](../../include/BinaryProtocol.h) - C++ implementation
- [../include/shared_protocol.h](../../include/shared_protocol.h) - Protocol structures
- [examples/binary_protocol_parser_example.py](../../examples/binary_protocol_parser_example.py) - Example code
- [tests/test_binary_protocol_parser.py](../../tests/test_binary_protocol_parser.py) - Unit tests
