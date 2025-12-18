# Dual-Controller Relay Communication System - Context Dump

## Project Overview

This project implements a dual-controller communication system for multi-drone operations where each drone has two Heltec V3 LoRa modules (Primary and Secondary) connected via UART. The system provides automatic relay capabilities when one drone loses line-of-sight with the Ground Control Station (QGC).

## Key Objectives

1. **Transparent Relay**: QGC remains unaware of relay operations - sees both drones with original system IDs
2. **Automatic Failover**: When Drone B loses GCS connection, Drone A automatically relays traffic
3. **Bandwidth Management**: Intelligent message filtering during relay to stay within LoRa bandwidth limits
4. **Dual Frequency**: Primary controllers use 915 MHz, Secondary controllers use 902 MHz for mesh

## Hardware Architecture

### Per-Drone Configuration
- **Primary Controller**: Heltec V3 @ 915 MHz (handles GCS communication)
- **Secondary Controller**: Heltec V3 @ 902 MHz (handles mesh/relay)
- **UART Connection**: Primary ↔ Secondary @ 115200 baud
  - Primary TX (GPIO 47) → Secondary RX (GPIO 48)
  - Primary RX (GPIO 48) → Secondary TX (GPIO 47)
- **Autopilot Connection**: Primary ↔ Flight Controller @ 57600 baud
  - Uses Serial (USB) on Heltec V3 by default
  - Can use hardware UART (GPIO 43/44) if needed

### Ground Station
- **Single Heltec V3** @ 915 MHz (no changes from existing aero_lora_ground)

## System Topology

### Normal Operation (Direct Mode)
```
QGC → Ground Station → [915 MHz] → Drone A Primary → Autopilot A
                                 → Drone B Primary → Autopilot B
                                 
Drone A Secondary: SLEEP (902 MHz)
Drone B Secondary: SLEEP (902 MHz)
```

### Relay Operation (Drone B through Drone A)
```
QGC → Ground Station → [915 MHz] → Drone A Primary → [UART] → 
                                                              ↓
Drone A Secondary ← [902 MHz] ← Drone B Secondary ← [UART] ← Drone B Primary ← Autopilot B
      ↓
   [915 MHz]
      ↓
Ground Station → QGC
```

## Operating Modes

### Primary Controller Modes
- **MODE_DIRECT**: Normal operation, direct to GCS
- **MODE_RELAY_ACTIVE**: Relaying for another drone
- **MODE_RELAY_CLIENT**: Being relayed through another drone
- **MODE_SEARCHING**: Lost GCS, searching for relay

### Secondary Controller States
- **STATE_IDLE**: Low power listening
- **STATE_DISTRESS**: Broadcasting distress beacons
- **STATE_RELAY**: Active relay mode
- **STATE_LISTENING**: Listening for distress from others

## Communication Protocols

### UART Protocol (Primary ↔ Secondary)
```
Frame Format: [0xFF][0xFE][LEN_H][LEN_L][PAYLOAD][CHECKSUM]
- Start markers: 0xFF 0xFE
- Length: 2 bytes (big endian)
- Payload: Variable length
- Checksum: XOR of all payload bytes

JSON Commands (newline-terminated):
- {"cmd":"INIT","drone_id":1}
- {"cmd":"DISTRESS","mode":"LOST_GCS"}
- {"cmd":"RELAY_REQUEST","from_drone":2}
- {"cmd":"RELAY_ESTABLISHED","relay_drone":1}
- {"cmd":"STOP_RELAY"}
```

### Radio Protocol (902 MHz Mesh)
```
Distress Beacon: [0xDE][drone_id][type][rssi][timestamp]
Relay Offer:     [0xAC][offering_drone][target_drone]
Relay Data:      [0xRE][payload...]
```

### MAVLink System IDs
- **Drone A**: System ID = 1
- **Drone B**: System ID = 2
- **QGC**: System ID = 255

**Critical**: System IDs are NEVER modified during relay operations.

## Priority Queue Strategy for Bandwidth Management

**Key Insight from MAVLink Expert**: Instead of aiming for 0% drop rate, maximize bandwidth utilization with a priority queue system. Accept 5-10% drop rate for lower priority messages while maintaining 0-1% for critical messages.

### Tier 1: Critical (0-1% drop rate target)
**Purpose**: Keep connection alive and acknowledge commands
- HEARTBEAT (0x00) - Connection keepalive
- COMMAND_ACK (0x4D / 77) - Acknowledge QGC commands immediately
- COMMAND_LONG (0x4C / 76) - Critical commands from QGC
- STATUSTEXT (0xFD / 253) - Important status messages

**Handling**: 
- Always transmit immediately
- Never drop unless buffer completely full
- Highest priority in queue

### Tier 2: Important (2-5% drop rate acceptable)
**Purpose**: Operational telemetry needed for flight
- GPS_RAW_INT (0x21 / 33) - Position data
- ATTITUDE (0x1E / 30) - Orientation
- GLOBAL_POSITION_INT (0x24 / 36) - Global position
- VFR_HUD (0x4A / 74) - Airspeed, altitude, heading
- SYS_STATUS (0x01) - Battery, sensors
- PARAM_VALUE (0x16) - Parameter responses

**Handling**:
- Transmit when Tier 1 queue empty
- Can be dropped if bandwidth saturated
- Implement freshness check: drop if >1 second old

### Tier 3: Optional (5-10% drop rate acceptable)
**Purpose**: Nice-to-have data, can be dropped without impact
- PARAM_REQUEST_READ (0x04) - Can be retried
- PARAM_REQUEST_LIST (0x14) - Can be retried
- RC_CHANNELS (0x23 / 35) - RC input (if available)
- SERVO_OUTPUT_RAW (0x24 / 36) - Servo positions
- RAW_IMU (0x1B / 27) - Raw sensor data
- SCALED_PRESSURE (0x1D / 29) - Barometer data

**Handling**:
- Transmit only when Tier 1 and Tier 2 queues empty
- Aggressively drop stale messages (>500ms old)
- Can be completely dropped during high bandwidth periods

### Stale Message Detection
Messages become "stale" and should be dropped:
- **Tier 1**: Never stale (always send)
- **Tier 2**: Stale after 1 second (position/attitude data)
- **Tier 3**: Stale after 500ms (sensor data)

**Rationale**: Sending old telemetry wastes bandwidth and provides no value. Better to drop and send fresh data.

## Link Quality Monitoring

### Loss Detection Criteria
1. No GCS packet received for 3 seconds
2. Consecutive loss counter > 3
3. Current mode is MODE_DIRECT

### Recovery Criteria
1. Receive direct packet from GCS
2. Reset consecutive loss counter
3. Transition back to MODE_DIRECT

## Project Structure

```
build_examples/AeroLoraDev/
├── src/
│   ├── primary_controller.cpp       # Enhanced aero_lora_drone
│   ├── secondary_controller.cpp     # New mesh/relay controller
│   └── ground_station.cpp           # Enhanced aero_lora_ground
├── include/
│   ├── mavlink_utils.h             # System ID extraction, filtering
│   ├── uart_protocol.h             # UART framing protocol
│   └── relay_protocol.h            # Distress beacon structures
├── platformio.ini                  # Build configuration
└── README.md                       # Build and test instructions
```

## PlatformIO Configuration

### Three Build Environments
1. **primary_controller**: Heltec V3, 915 MHz, drone firmware
2. **secondary_controller**: Heltec V3, 902 MHz, mesh firmware
3. **ground_station**: Heltec V3, 915 MHz, ground firmware

### Build Commands
```bash
# Build Primary Controller for Drone A
pio run -e primary_controller -D THIS_DRONE_ID=1

# Build Primary Controller for Drone B
pio run -e primary_controller -D THIS_DRONE_ID=2

# Build Secondary Controller
pio run -e secondary_controller

# Build Ground Station
pio run -e ground_station
```

## Current Implementation Status

### Completed Tasks (from tasks.md)
- [x] 1. Set up project structure and shared utilities
- [x] 1.1 Create project directory structure
- [x] 1.2 Create shared utility headers
- [-] 2. Implement MAVLink utility functions (partially complete)

### In Progress
- [ ] 2.1 Implement extractSystemId() function
- [ ] 2.2 Implement shouldRelayMessage() function

### Next Steps
1. Complete MAVLink utility functions
2. Implement UART communication protocol
3. Create Primary Controller base from aero_lora_drone
4. Implement link quality monitoring
5. Create Secondary Controller

## Key Design Decisions

### 1. Priority Queue Strategy (Expert Recommendation)
**Source**: MAVLink expert with extensive experience in bandwidth-constrained links

**Key Insight**: Don't aim for 0% drop rate on limited bandwidth links. Instead, maximize spectrum utilization with intelligent prioritization.

**Rationale**:
- LoRa links have limited bandwidth (~5.5 kbps at SF7/500kHz)
- Trying to send everything creates congestion and delays critical messages
- Better to drop low-priority/stale data and ensure critical messages get through
- QGC is designed to handle some packet loss gracefully
- COMMAND_ACK is crucial - lets QGC know we received commands even if we're busy

**Implementation**:
- 3-tier priority queue system
- Tier 1 (Critical): 0-1% drop rate - keeps connection alive
- Tier 2 (Important): 2-5% drop rate - operational telemetry
- Tier 3 (Optional): 5-10% drop rate - nice-to-have data
- Stale message detection prevents wasting bandwidth on old data

**Benefits**:
- Maximizes useful bandwidth utilization
- Ensures critical messages always get through
- Reduces latency for high-priority messages
- More reliable than trying to send everything

### 2. Frequency Separation
- **915 MHz**: Primary controllers ↔ Ground Station (existing)
- **902 MHz**: Secondary controllers ↔ Secondary controllers (new mesh)
- **Rationale**: Avoid TDMA complexity, use frequency separation instead

### 3. No Encryption (Initial)
- Current implementation has no encryption
- Same as existing AeroLoRa system
- Security can be added in future iterations

### 4. Single Relay Hop
- Current design supports exactly 2 drones
- No multi-hop relay (Drone C → Drone B → Drone A)
- Simplifies implementation and testing

### 5. Transparent to QGC
- QGC sees both drones with original system IDs
- No awareness of relay operations
- Seamless failover and recovery

## Testing Strategy

### Bench Tests
1. **Basic Initialization**: Verify UART communication, radio init
2. **Direct Mode**: Both drones communicate with QGC normally
3. **LOS Loss Simulation**: Disconnect antenna, trigger relay
4. **Relay Communication**: Verify telemetry and commands through relay
5. **Bandwidth Monitoring**: Check packet rates and filtering
6. **Automatic Recovery**: Reconnect antenna, return to direct mode

### Field Tests
1. **Actual LOS Obstruction**: Fly behind building
2. **Range Testing**: Measure direct and relay ranges
3. **Multi-Drone Operations**: Coordinate two drones simultaneously

## Dependencies

### Existing
- RadioLib (LoRa radio control)
- U8g2lib (OLED display)
- AeroLoRaProtocol (existing protocol)

### New
- ArduinoJson (for UART JSON commands)
- ESP32 sleep functions (for power management)

## Configuration Parameters

### Compile-Time
```cpp
#define THIS_DRONE_ID        1       // Set to 1 or 2
#define OTHER_DRONE_ID       2       // The other drone
#define GCS_SYSTEM_ID        255     // QGC system ID

// Pin assignments
#define SECONDARY_TX         47
#define SECONDARY_RX         48

// Timing
#define DISTRESS_INTERVAL    500     // ms
#define LINK_LOSS_TIMEOUT    3000    // ms
#define LINK_LOSS_THRESHOLD  3       // consecutive losses
```

## Bandwidth Analysis with Priority Queue

### Direct Mode (Per Drone)
- **Tier 1 (Critical)**: ~0.5 msg/s = ~25 ms/s air time
  - HEARTBEAT: 1 Hz
  - COMMAND_ACK: Sporadic
- **Tier 2 (Important)**: ~1.0 msg/s = ~50 ms/s air time
  - GPS, ATTITUDE, VFR_HUD: ~0.3 Hz each
- **Tier 3 (Optional)**: ~0.5 msg/s = ~25 ms/s air time
  - Various sensor data: As bandwidth allows
- **Commands**: Sporadic, ~10-50 ms per command
- **Total**: ~100 ms/s = ~10-15% bandwidth utilization
- **Target Drop Rate**: Tier 1: 0-1%, Tier 2: 2-5%, Tier 3: 5-10%

### Relay Mode (Drone A relaying for Drone B)
- **Drone A Tier 1**: ~25 ms/s (unchanged)
- **Drone A Tier 2**: ~50 ms/s (unchanged)
- **Drone B Tier 1**: ~25 ms/s (relayed, no drops)
- **Drone B Tier 2**: ~30 ms/s (relayed, some drops acceptable)
- **Drone B Tier 3**: ~10 ms/s (relayed, aggressive drops)
- **Commands**: ~10-50 ms per command (priority)
- **Relay overhead**: ~10 ms/s (coordination)
- **Total**: ~150-200 ms/s = ~20-25% bandwidth utilization
- **Strategy**: Prioritize Tier 1 from both drones, then Tier 2, then Tier 3

### Queue Management Strategy
1. **Separate queues per tier** (3 queues total)
2. **Always service Tier 1 first** (FIFO within tier)
3. **Check Tier 2 only when Tier 1 empty**
4. **Check Tier 3 only when Tier 1 and 2 empty**
5. **Drop stale messages** before transmission
6. **Monitor drop rates** per tier and adjust thresholds

## Latency Analysis

### Direct Mode
- Command latency: 50-100 ms
- Telemetry latency: 100-500 ms

### Relay Mode
- Command latency: 150-300 ms (additional hop)
- Telemetry latency: 200-600 ms (additional hop + decimation)

## Power Consumption

### Primary Controller
- Active (TX/RX): ~120 mA @ 3.3V
- Idle (listening): ~80 mA @ 3.3V

### Secondary Controller
- Active (relay): ~120 mA @ 3.3V
- Listening: ~80 mA @ 3.3V
- Light sleep: ~5 mA @ 3.3V (target)

## Diagnostic Output

### Serial Output Format (Enhanced with Priority Queue Stats)
```
=== System Status ===
Mode: RELAY_ACTIVE | Drone ID: 1
Link: RSSI: -85.2 dBm, SNR: 8.5 dB
TX: 1234 | RX: 987 | ACK: 0
Queue Stats:
  Tier 1: TX:450 Drop:2 (0.4%) Stale:0
  Tier 2: TX:320 Drop:15 (4.5%) Stale:8
  Tier 3: TX:180 Drop:25 (12.2%) Stale:42
Relaying for Drone 2
Secondary: ACTIVE | Mesh RSSI: -78.3 dBm
```

### OLED Display
```
PRIMARY (ID:1)
MODE: RELAY_ACTIVE
TX:1234 RX:987
RSSI:-85 SNR:8.5
Relay: Drone 2
```

### LED Patterns
- Slow pulse: Idle/Direct mode
- Fast pulse: Relay active
- Rapid flash: Transmitting
- Solid: Receiving
- Triple flash: Error

## Related Files

### Specification Files
- `.kiro/specs/dual-controller-relay/requirements.md` - Detailed requirements
- `.kiro/specs/dual-controller-relay/design.md` - Complete design document
- `.kiro/specs/dual-controller-relay/tasks.md` - Implementation task list

### Existing Code (Reference)
- `src/aero_lora_ground.cpp` - Ground station implementation
- `src/aero_lora_drone.cpp` - Drone controller implementation
- `src/AeroLoRaProtocol.h/cpp` - Existing protocol implementation

### New Code (To Be Created)
- `build_examples/AeroLoraDev/src/primary_controller.cpp`
- `build_examples/AeroLoraDev/src/secondary_controller.cpp`
- `build_examples/AeroLoraDev/src/ground_station.cpp`
- `build_examples/AeroLoraDev/include/mavlink_utils.h`
- `build_examples/AeroLoraDev/include/uart_protocol.h`
- `build_examples/AeroLoraDev/include/relay_protocol.h`

## Priority Queue Implementation Details

### Queue Structure
```cpp
struct QueuedMessage {
    uint8_t data[256];
    uint16_t length;
    uint32_t timestamp;  // millis() when queued
    uint8_t tier;        // 1, 2, or 3
};

// Three separate queues
std::deque<QueuedMessage> tier1Queue;  // Max 10 messages
std::deque<QueuedMessage> tier2Queue;  // Max 20 messages
std::deque<QueuedMessage> tier3Queue;  // Max 30 messages
```

### Message Classification Function
```cpp
uint8_t classifyMessage(uint8_t msgId) {
    // Tier 1: Critical (0-1% drop)
    if (msgId == 0x00 ||  // HEARTBEAT
        msgId == 0x4D ||  // COMMAND_ACK
        msgId == 0x4C ||  // COMMAND_LONG
        msgId == 0xFD) {  // STATUSTEXT
        return 1;
    }
    
    // Tier 2: Important (2-5% drop)
    if (msgId == 0x21 ||  // GPS_RAW_INT
        msgId == 0x1E ||  // ATTITUDE
        msgId == 0x24 ||  // GLOBAL_POSITION_INT
        msgId == 0x4A ||  // VFR_HUD
        msgId == 0x01 ||  // SYS_STATUS
        msgId == 0x16) {  // PARAM_VALUE
        return 2;
    }
    
    // Tier 3: Optional (5-10% drop)
    return 3;
}
```

### Stale Message Detection
```cpp
bool isStale(QueuedMessage& msg) {
    uint32_t age = millis() - msg.timestamp;
    
    if (msg.tier == 1) return false;  // Never stale
    if (msg.tier == 2) return age > 1000;  // 1 second
    if (msg.tier == 3) return age > 500;   // 500ms
    
    return false;
}
```

### Queue Processing Logic
```cpp
void processQueues() {
    // 1. Check Tier 1 first
    if (!tier1Queue.empty()) {
        QueuedMessage msg = tier1Queue.front();
        if (transmit(msg)) {
            tier1Queue.pop_front();
            stats.tier1_tx++;
        }
        return;  // Always prioritize Tier 1
    }
    
    // 2. Check Tier 2 if Tier 1 empty
    if (!tier2Queue.empty()) {
        QueuedMessage msg = tier2Queue.front();
        if (isStale(msg)) {
            tier2Queue.pop_front();
            stats.tier2_stale++;
            return;
        }
        if (transmit(msg)) {
            tier2Queue.pop_front();
            stats.tier2_tx++;
        }
        return;
    }
    
    // 3. Check Tier 3 if Tier 1 and 2 empty
    if (!tier3Queue.empty()) {
        QueuedMessage msg = tier3Queue.front();
        if (isStale(msg)) {
            tier3Queue.pop_front();
            stats.tier3_stale++;
            return;
        }
        if (transmit(msg)) {
            tier3Queue.pop_front();
            stats.tier3_tx++;
        }
    }
}
```

### Queue Overflow Handling
```cpp
void enqueueMessage(uint8_t* data, uint16_t len) {
    uint8_t msgId = extractMessageId(data, len);
    uint8_t tier = classifyMessage(msgId);
    
    QueuedMessage msg;
    memcpy(msg.data, data, len);
    msg.length = len;
    msg.timestamp = millis();
    msg.tier = tier;
    
    if (tier == 1) {
        if (tier1Queue.size() >= 10) {
            // Drop oldest Tier 1 (should rarely happen)
            tier1Queue.pop_front();
            stats.tier1_drop++;
        }
        tier1Queue.push_back(msg);
    } else if (tier == 2) {
        if (tier2Queue.size() >= 20) {
            // Drop oldest Tier 2
            tier2Queue.pop_front();
            stats.tier2_drop++;
        }
        tier2Queue.push_back(msg);
    } else {
        if (tier3Queue.size() >= 30) {
            // Drop oldest Tier 3
            tier3Queue.pop_front();
            stats.tier3_drop++;
        }
        tier3Queue.push_back(msg);
    }
}
```

## Important Notes

1. **System ID Preservation**: Never modify MAVLink system IDs during relay
2. **Bandwidth Limits**: Stay within ~5.5 kbps with SF7 @ 500kHz BW
3. **Automatic Recovery**: System automatically returns to direct mode when LOS restored
4. **No QGC Awareness**: QGC should not know relay is happening
5. **Frequency Separation**: 915 MHz for GCS, 902 MHz for mesh
6. **UART Framing**: Use 0xFF 0xFE start markers with XOR checksum
7. **Distress Interval**: 500ms during active search, 2s after 30s timeout
8. **Link Loss Threshold**: 3 seconds timeout, 3 consecutive losses
9. **Priority Queue**: Accept 5-10% drop rate for Tier 3, 2-5% for Tier 2, 0-1% for Tier 1
10. **Stale Messages**: Drop Tier 2 messages >1s old, Tier 3 messages >500ms old

## Next Session Continuation

When continuing work on this project in a different directory:

1. **Navigate to the PlatformIO project**: `build_examples/AeroLoraDev/`
2. **Review current task status**: Check `.kiro/specs/dual-controller-relay/tasks.md`
3. **Continue from last incomplete task**: Currently at task 2.1 (extractSystemId)
4. **Reference design document**: `.kiro/specs/dual-controller-relay/design.md`
5. **Test incrementally**: Build and test each component as completed

## Build and Upload Commands

```bash
# Navigate to project directory
cd build_examples/AeroLoraDev/

# Build Primary Controller for Drone A
pio run -e primary_controller -D THIS_DRONE_ID=1

# Upload to Drone A Primary
pio run -e primary_controller -t upload --upload-port /dev/cu.usbserial-A

# Build Primary Controller for Drone B
pio run -e primary_controller -D THIS_DRONE_ID=2

# Upload to Drone B Primary
pio run -e primary_controller -t upload --upload-port /dev/cu.usbserial-B

# Build and upload Secondary Controller
pio run -e secondary_controller -t upload --upload-port /dev/cu.usbserial-C

# Build and upload Ground Station
pio run -e ground_station -t upload --upload-port /dev/cu.usbserial-D
```

## Troubleshooting

### Secondary Not Responding
- Check UART connections (TX/RX crossed)
- Verify baud rate (115200)
- Check for "READY" response in serial output

### Relay Not Activating
- Verify distress beacon transmission (902 MHz)
- Check antenna connections
- Verify drone IDs are different

### QGC Not Seeing Both Drones
- Check system IDs (should be 1 and 2)
- Verify heartbeat messages
- Check ground station routing logic

### High Packet Drop Rate
- Increase telemetry decimation (1/5 instead of 1/3)
- Reduce non-critical message transmission
- Check for interference on 915 MHz or 902 MHz
