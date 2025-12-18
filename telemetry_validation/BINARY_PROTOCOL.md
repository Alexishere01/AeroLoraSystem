# Binary Protocol Specification

This document describes the custom binary UART protocol used for communication between Primary and Secondary controllers in the dual-controller LoRa relay system.

## Overview

The binary protocol wraps MAVLink packets in a structured format with metadata (RSSI, SNR) and error detection (Fletcher-16 checksum). This protocol is used for UART communication between:

- **Primary Controller** ↔ **Secondary Controller** (drone-side)
- **Primary Controller** ↔ **Secondary Controller** (ground-side)

The Telemetry Validation System parses this binary protocol to extract MAVLink messages and monitor protocol health.

## Protocol Structure

### Packet Format

Every packet follows this structure:

```
┌──────────┬─────────┬────────┬─────────────┬──────────┐
│ START    │ COMMAND │ LENGTH │   PAYLOAD   │ CHECKSUM │
│ (1 byte) │ (1 byte)│(2 bytes)│ (0-255 bytes)│ (2 bytes)│
└──────────┴─────────┴────────┴─────────────┴──────────┘
```

| Field | Size | Description |
|-------|------|-------------|
| START | 1 byte | Start marker: `0xAA` |
| COMMAND | 1 byte | Command type (see Command Types) |
| LENGTH | 2 bytes | Payload length (little-endian, 0-255) |
| PAYLOAD | 0-255 bytes | Command-specific payload data |
| CHECKSUM | 2 bytes | Fletcher-16 checksum (little-endian) |

**Total packet size**: 6 + payload_length bytes (minimum 6, maximum 261)

### Start Marker

All packets begin with the start byte `0xAA` (170 decimal). The parser uses this to synchronize with the byte stream.

### Command Types

Commands are defined in the `UartCommand` enum:

| Command | Value | Description | Payload Type |
|---------|-------|-------------|--------------|
| `CMD_INIT` | 0x01 | Initialization handshake | `InitPayload` |
| `CMD_BRIDGE_TX` | 0x02 | Bridge transmit (Primary→Secondary) | `BridgePayload` |
| `CMD_BRIDGE_RX` | 0x03 | Bridge receive (Secondary→Primary) | `BridgePayload` |
| `CMD_STATUS_REPORT` | 0x04 | System status report | `StatusPayload` |
| `CMD_RELAY_ACTIVATE` | 0x05 | Activate relay mode | `RelayActivatePayload` |
| `CMD_RELAY_DEACTIVATE` | 0x06 | Deactivate relay mode | Empty |
| `CMD_RELAY_RX` | 0x07 | Relay receive data | `RelayRxPayload` |
| `CMD_ACK` | 0x08 | Acknowledgment | `AckPayload` |
| `CMD_ERROR` | 0x09 | Error report | `ErrorPayload` |

### Payload Structures

#### InitPayload (CMD_INIT)

Sent during initialization to establish communication.

```c
struct InitPayload {
    uint8_t protocol_version;  // Protocol version (currently 1)
    uint8_t node_type;         // 0=Primary, 1=Secondary
    uint8_t capabilities;      // Capability flags
};
```

**Size**: 3 bytes

#### BridgePayload (CMD_BRIDGE_TX, CMD_BRIDGE_RX)

Contains MAVLink packet with signal quality metadata.

```c
struct BridgePayload {
    uint8_t system_id;         // MAVLink system ID
    int16_t rssi;              // RSSI in dBm (little-endian)
    int16_t snr;               // SNR in dB (little-endian)
    uint8_t data_len;          // MAVLink packet length (1-245)
    uint8_t data[245];         // MAVLink packet data
};
```

**Size**: 1 + 2 + 2 + 1 + data_len = 6 + data_len bytes (max 251 bytes)

**Fields**:
- `system_id`: MAVLink system ID of the source
- `rssi`: Received Signal Strength Indicator in dBm (e.g., -80 dBm)
- `snr`: Signal-to-Noise Ratio in dB (e.g., 10 dB)
- `data_len`: Length of MAVLink packet (1-245 bytes)
- `data`: Raw MAVLink packet bytes

#### StatusPayload (CMD_STATUS_REPORT)

System status and metrics.

```c
struct StatusPayload {
    uint32_t uptime_ms;           // System uptime in milliseconds
    uint8_t relay_active;         // 1 if relay mode active, 0 otherwise
    uint16_t packets_relayed;     // Count of packets relayed
    uint8_t active_peer_relays;   // Number of active peer relays
    int16_t avg_rssi;             // Average RSSI (dBm)
    int16_t avg_snr;              // Average SNR (dB)
    uint16_t buffer_usage;        // Buffer usage percentage (0-100)
};
```

**Size**: 15 bytes

#### RelayActivatePayload (CMD_RELAY_ACTIVATE)

Activate relay mode for a specific system.

```c
struct RelayActivatePayload {
    uint8_t target_system_id;  // System ID to relay for
    uint8_t relay_priority;    // Relay priority (0-255)
};
```

**Size**: 2 bytes

#### RelayRxPayload (CMD_RELAY_RX)

Relay received data with metadata.

```c
struct RelayRxPayload {
    uint8_t source_system_id;  // Original source system ID
    uint8_t relay_hop_count;   // Number of relay hops
    int16_t rssi;              // RSSI at relay node
    int16_t snr;               // SNR at relay node
    uint8_t data_len;          // Data length
    uint8_t data[245];         // Relayed data
};
```

**Size**: 1 + 1 + 2 + 2 + 1 + data_len = 7 + data_len bytes (max 252 bytes)

#### AckPayload (CMD_ACK)

Acknowledgment response.

```c
struct AckPayload {
    uint8_t acked_command;  // Command being acknowledged
    uint8_t status;         // 0=success, non-zero=error code
};
```

**Size**: 2 bytes

#### ErrorPayload (CMD_ERROR)

Error report.

```c
struct ErrorPayload {
    uint8_t error_code;     // Error code
    uint8_t error_context;  // Context-specific data
};
```

**Size**: 2 bytes

**Error Codes**:
- `0x01`: Checksum error
- `0x02`: Invalid command
- `0x03`: Buffer overflow
- `0x04`: Timeout
- `0x05`: Parse error

### Fletcher-16 Checksum

The protocol uses Fletcher-16 checksum for error detection. The checksum is calculated over the COMMAND, LENGTH, and PAYLOAD fields (excluding START and CHECKSUM itself).

**Algorithm**:
```python
def fletcher16(data: bytes) -> int:
    sum1 = 0
    sum2 = 0
    for byte in data:
        sum1 = (sum1 + byte) % 255
        sum2 = (sum2 + sum1) % 255
    return (sum2 << 8) | sum1
```

**Checksum Format**: 2 bytes, little-endian
- Byte 0: `sum1` (low byte)
- Byte 1: `sum2` (high byte)

## Parsing State Machine

The binary protocol parser uses a state machine to handle byte-by-byte parsing:

```
┌──────────────┐
│  WAIT_START  │◄─────────────────────┐
└──────┬───────┘                      │
       │ Found 0xAA                   │
       ▼                              │
┌──────────────┐                      │
│ READ_HEADER  │                      │
└──────┬───────┘                      │
       │ Read COMMAND + LENGTH        │
       ▼                              │
┌──────────────┐                      │
│ READ_PAYLOAD │                      │
└──────┬───────┘                      │
       │ Read LENGTH bytes            │
       ▼                              │
┌──────────────┐                      │
│READ_CHECKSUM │                      │
└──────┬───────┘                      │
       │ Read 2 bytes                 │
       ▼                              │
┌──────────────┐                      │
│   VALIDATE   │                      │
└──────┬───────┘                      │
       │                              │
       ├─ Valid ──► Emit Packet       │
       │                              │
       └─ Invalid ─► Error ───────────┘
```

### States

1. **WAIT_START**: Looking for start byte (0xAA)
2. **READ_HEADER**: Reading command (1 byte) and length (2 bytes)
3. **READ_PAYLOAD**: Reading payload data (length bytes)
4. **READ_CHECKSUM**: Reading checksum (2 bytes)
5. **VALIDATE**: Validating checksum and emitting packet

## Python Parser Implementation

The `BinaryProtocolParser` class in `src/binary_protocol_parser.py` implements the protocol parser:

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
    print(f"Payload: {packet.payload}")
    
    # Extract MAVLink if BRIDGE command
    if packet.command in ['CMD_BRIDGE_TX', 'CMD_BRIDGE_RX']:
        mavlink_msg = parser.extract_mavlink(packet)
        if mavlink_msg:
            print(f"MAVLink: {mavlink_msg.msg_type}")
            print(f"RSSI: {mavlink_msg.rssi} dBm")
            print(f"SNR: {mavlink_msg.snr} dB")

# Get parser statistics
stats = parser.get_stats()
print(f"Packets received: {stats['packets_received']}")
print(f"Checksum errors: {stats['checksum_errors']}")
print(f"Success rate: {stats['success_rate']:.1f}%")
```

## Protocol Health Monitoring

The parser tracks protocol health metrics:

| Metric | Description |
|--------|-------------|
| `packets_received` | Total valid packets received |
| `checksum_errors` | Packets with invalid checksums |
| `parse_errors` | Packets with parsing errors |
| `timeout_errors` | Timeouts waiting for data |
| `unknown_commands` | Packets with unknown command types |
| `buffer_overflow` | Buffer overflow events |
| `success_rate` | Percentage of valid packets |

**Alerts**:
- Checksum error rate > 5%: WARNING
- Checksum error rate > 10%: CRITICAL
- Buffer overflow: CRITICAL
- Success rate < 90%: WARNING

## MAVLink Extraction

MAVLink packets are embedded in `BridgePayload` structures. The parser extracts them:

1. Parse binary protocol packet
2. Check command type is `CMD_BRIDGE_TX` or `CMD_BRIDGE_RX`
3. Extract `BridgePayload` structure
4. Extract MAVLink data from `data` field
5. Parse MAVLink using pymavlink
6. Attach RSSI/SNR metadata from `BridgePayload`

**Example**:
```python
# Packet structure:
# [0xAA][0x02][0x0C 0x00][system_id][rssi_lo rssi_hi][snr_lo snr_hi][data_len][mavlink_data...][cksum_lo cksum_hi]

# After parsing:
packet.command = 'CMD_BRIDGE_TX'
packet.payload = {
    'system_id': 1,
    'rssi': -85,
    'snr': 12,
    'data_len': 8,
    'data': b'\xfe\x09\x00\x01\x01\x00...'  # MAVLink packet
}

# Extract MAVLink:
mavlink_msg = parser.extract_mavlink(packet)
mavlink_msg.msg_type = 'HEARTBEAT'
mavlink_msg.rssi = -85  # From BridgePayload
mavlink_msg.snr = 12    # From BridgePayload
```

## Example Packets

### INIT Packet

```
Hex: AA 01 03 00 01 00 00 04 05
     │  │  │  │  └──┴──┴─ Payload: version=1, type=0, caps=0
     │  │  └──┴───────── Length: 3 bytes
     │  └────────────── Command: CMD_INIT (0x01)
     └───────────────── Start: 0xAA
                        └──┴─ Checksum: 0x0504
```

### BRIDGE_TX Packet with MAVLink HEARTBEAT

```
Hex: AA 02 0C 00 01 AB FF 0A 00 09 FE 09 00 01 01 00 00 00 00 00 00 00 00 03 03 8C 9A
     │  │  │  │  │  │  │  │  │  │  └──────────────────────────────────┘ │  │  └──┴─ Checksum
     │  │  │  │  │  │  │  │  │  └─ MAVLink HEARTBEAT (9 bytes)          │  └───── data_len: 9
     │  │  │  │  │  │  │  └──┴─ SNR: 10 dB (0x000A)                      └─────── RSSI: -85 dBm (0xFFAB)
     │  │  │  │  └─ system_id: 1
     │  │  └──┴─ Length: 12 bytes
     │  └────── Command: CMD_BRIDGE_TX (0x02)
     └───────── Start: 0xAA
```

### STATUS_REPORT Packet

```
Hex: AA 04 0F 00 10 27 00 00 01 05 00 02 AB FF 0C 00 32 00 1E 20
     │  │  │  │  └──┴──┴──┴─ uptime_ms: 10000 (0x00002710)
     │  │  │  │           └─ relay_active: 1
     │  │  │  │              └──┴─ packets_relayed: 5
     │  │  │  │                    └─ active_peer_relays: 2
     │  │  │  │                       └──┴─ avg_rssi: -85 dBm
     │  │  │  │                             └──┴─ avg_snr: 12 dB
     │  │  │  │                                   └──┴─ buffer_usage: 50%
     │  │  └──┴─ Length: 15 bytes                       └──┴─ Checksum
     │  └────── Command: CMD_STATUS_REPORT (0x04)
     └───────── Start: 0xAA
```

## Error Handling

### Checksum Errors

When checksum validation fails:
1. Increment `checksum_errors` counter
2. Discard packet
3. Log error with packet details
4. Return to WAIT_START state
5. Alert if error rate exceeds threshold

### Parse Errors

When parsing fails (invalid length, buffer overflow):
1. Increment `parse_errors` counter
2. Discard partial packet
3. Log error with context
4. Return to WAIT_START state
5. Attempt to resynchronize

### Timeout Errors

When no data received for timeout period:
1. Increment `timeout_errors` counter
2. Log timeout event
3. Maintain connection state
4. Alert if timeouts frequent

### Unknown Commands

When unknown command type received:
1. Increment `unknown_commands` counter
2. Log command value
3. Skip packet
4. Continue parsing

## Performance Considerations

### Buffer Management
- Use circular buffer for incoming data
- Limit buffer size to prevent memory exhaustion
- Flush old data if buffer full

### Parsing Efficiency
- State machine avoids backtracking
- Minimal memory allocations
- Efficient checksum calculation

### Error Recovery
- Quick resynchronization on errors
- No blocking operations
- Graceful degradation

## Debugging

### Enable Debug Logging

```python
parser = BinaryProtocolParser(debug=True)
```

### Packet Logging

Log raw packets to file for analysis:

```python
from src.telemetry_logger import TelemetryLogger

logger = TelemetryLogger()
logger.log_binary_packet(packet)  # Logs to .binlog file
```

### Replay Packets

Replay logged packets for debugging:

```python
with open('telemetry.binlog', 'rb') as f:
    data = f.read()
    packets = parser.parse_stream(data)
```

### Checksum Verification

Manually verify checksum:

```python
from src.binary_protocol_parser import fletcher16

data = b'\x02\x0C\x00\x01\xAB\xFF\x0A\x00\x09...'  # CMD + LEN + PAYLOAD
checksum = fletcher16(data)
print(f"Checksum: 0x{checksum:04X}")
```

## See Also

- [../include/BinaryProtocol.h](../include/BinaryProtocol.h) - C++ implementation
- [../include/shared_protocol.h](../include/shared_protocol.h) - Protocol structures
- [../include/README_BinaryProtocol.md](../include/README_BinaryProtocol.md) - C++ documentation
- [src/README_BinaryProtocolParser.md](src/README_BinaryProtocolParser.md) - Parser implementation
- [config/BINARY_PROTOCOL.md](config/BINARY_PROTOCOL.md) - Configuration reference
- [examples/binary_protocol_parser_example.py](examples/binary_protocol_parser_example.py) - Example code
