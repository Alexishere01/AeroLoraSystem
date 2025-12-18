# Binary Protocol Implementation

This document describes the binary protocol used for UART communication between Primary and Secondary controllers.

## Overview

The binary protocol provides a compact, efficient communication format with:
- **3-5x faster** transmission compared to JSON
- **40-60% smaller** message sizes
- **Deterministic timing** for real-time operations
- **Built-in error detection** via Fletcher-16 checksums

**Note:** As of the latest version, the binary protocol is the default and only protocol. The JSON protocol has been removed to save ~17-18KB of flash memory.

## Files

- `include/shared_protocol.h` - Protocol definitions (packet structures, enums, payloads)
- `include/BinaryProtocol.h` - Transmission functions (inline implementations)

## Usage

### 1. Include the Header

```cpp
#include "BinaryProtocol.h"
```

### 2. Send Commands

All send functions follow this pattern:
```cpp
sendBinary<CommandName>(uart, ...params..., &binaryStats);
```

#### Example: Send INIT Command

```cpp
// Primary → Secondary initialization
sendBinaryInit(UART_SECONDARY, "FREQUENCY_BRIDGE", 915.0, 902.0, &binaryStats);
```

#### Example: Send BRIDGE_TX Command

```cpp
// Primary → Secondary: Forward packet to mesh
uint8_t mavlinkData[50];
uint16_t dataLen = 50;
uint8_t systemId = 1;

sendBinaryBridgeTx(UART_SECONDARY, systemId, -85.0, 8.5, 
                   mavlinkData, dataLen, &binaryStats);
```

#### Example: Send STATUS_REPORT

```cpp
// Secondary → Primary: Report status
StatusPayload status;
status.relay_active = true;
status.packets_relayed = 1234;
status.rssi = -75.0;
// ... fill other fields ...

sendBinaryStatus(UART_PRIMARY, &status, &binaryStats);
```

## Available Functions

### Core Transmission

- `sendBinaryPacket()` - Low-level packet transmission (used by all other functions)

### Command-Specific Functions

- `sendBinaryInit()` - CMD_INIT: Initialize communication
- `sendBinaryAck()` - CMD_ACK: Acknowledge command
- `sendBinaryRelayActivate()` - CMD_RELAY_ACTIVATE: Activate/deactivate relay mode
- `sendBinaryRelayTx()` - CMD_RELAY_TX: Request relay transmission
- `sendBinaryRelayRx()` - CMD_RELAY_RX: Relay packet received
- `sendBinaryBridgeTx()` - CMD_BRIDGE_TX: Bridge packet from GCS to mesh
- `sendBinaryBridgeRx()` - CMD_BRIDGE_RX: Bridge packet from mesh to GCS
- `sendBinaryStatus()` - CMD_STATUS_REPORT: Status update
- `sendBinaryBroadcastRelayReq()` - CMD_BROADCAST_RELAY_REQ: Request relay assistance
- `sendBinaryStatusRequest()` - CMD_STATUS_REQUEST: Request immediate status

## Packet Format

```
┌─────────────┬─────────┬────────┬─────────────┬──────────┐
│ Start Byte  │ Command │ Length │   Payload   │ Checksum │
│   (0xAA)    │ (1 byte)│(2 bytes)│ (0-255 bytes)│(2 bytes) │
└─────────────┴─────────┴────────┴─────────────┴──────────┘
     1 byte      1 byte   2 bytes   variable      2 bytes
```

**Total overhead: 6 bytes** (vs 50+ bytes for JSON)

## Statistics Tracking

All send functions accept an optional `BinaryProtocolStats*` parameter to track:
- Packets sent/received
- Bytes sent/received
- Checksum errors
- Parse errors
- Timeout errors
- Unknown commands

Example:
```cpp
BinaryProtocolStats binaryStats = {0};

// Send with statistics tracking
sendBinaryInit(UART_SECONDARY, "BRIDGE", 915.0, 902.0, &binaryStats);

// Check statistics
Serial.printf("Packets sent: %lu\n", binaryStats.packets_sent);
Serial.printf("Bytes sent: %lu\n", binaryStats.bytes_sent);
Serial.printf("Success rate: %.1f%%\n", binaryStats.getSuccessRate());
```

## Error Handling

All functions include built-in error handling:
- **Payload size validation**: Rejects packets exceeding 255 bytes
- **Null pointer checks**: Validates payload pointers
- **Automatic error logging**: Prints errors to Serial
- **Statistics updates**: Increments error counters

Example error output:
```
✗ Binary packet payload too large: 300 bytes (max 255)
✗ BRIDGE_TX data too large: 250 bytes (max 245)
✗ Cannot send STATUS_REPORT: null payload
```

## Binary Protocol Benefits

The binary protocol provides significant improvements over the previous JSON implementation:

**Example: BRIDGE_TX Command**
```cpp
sendBinaryBridgeTx(UART_SECONDARY, systemId, rssi, snr, 
                   data, dataLen, &binaryStats);
```

**Improvements:**
- Message size: ~120 bytes (JSON) → ~68 bytes (Binary) = 43% reduction
- Transmission time: 20-40ms (JSON) → 3-8ms (Binary) = 5x faster
- No hex encoding overhead
- Built-in checksum validation
- Flash memory savings: ~17-18KB (ArduinoJson library removed)

## Performance Comparison

| Command | JSON Size | Binary Size | Savings |
|---------|-----------|-------------|---------|
| INIT | ~85 bytes | ~30 bytes | 65% |
| BRIDGE_TX (50 byte payload) | ~120 bytes | ~68 bytes | 43% |
| STATUS_REPORT | ~250 bytes | ~80 bytes | 68% |
| ACK | ~45 bytes | ~7 bytes | 84% |

**Average savings: ~55%**

## Implementation Status

The binary protocol is fully implemented and is the default (and only) protocol:

- ✓ **Transmission functions** (Task 3): All command-specific send functions
- ✓ **Reception state machine** (Task 4): `processBinaryUart()` with error handling
- ✓ **Controller integration** (Tasks 8-9): Both Primary and Secondary controllers
- ✓ **Testing and validation** (Task 11): Functional and performance testing complete
- ✓ **JSON removal** (Task 12): JSON code and ArduinoJson dependency removed

## Requirements Satisfied

- ✓ 1.1: Binary protocol format with fixed headers
- ✓ 1.5: Deterministic parsing with fixed-size headers
- ✓ 3.1: Fletcher-16 checksum calculation
- ✓ 4.1-4.5: All UART commands supported in binary format
- ✓ 8.1: Stack-allocated buffers (no dynamic allocation)

## Notes

- All functions are `inline` to avoid linker issues with multiple compilation units
- Functions use `HardwareSerial&` to support both `UART_PRIMARY` and `UART_SECONDARY`
- Statistics tracking is optional (pass `nullptr` to disable)
- Payload structures are defined in `shared_protocol.h` with `__attribute__((packed))`
