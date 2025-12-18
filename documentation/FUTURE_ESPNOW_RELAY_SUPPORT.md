# Future ESP-NOW Relay Support Plan

## Overview

Plan for implementing smart message filtering at relay nodes to enable high-bandwidth ESP-NOW telemetry alongside existing LoRa communication.

## Current Architecture

```
Drone FC → ESP-NOW (1 Mbps) → Relay → LoRa (SF6 500kHz ~5-10 kbps) → Ground
         ↓
      ESP-NOW → Ground (when in range)
```

**Bottleneck:** LoRa bandwidth (5-10 kbps) limits message rate from FC

## Problem Statement

- ESP-NOW can handle 1 Mbps bandwidth
- LoRa can only handle 5-10 kbps (SF6, 500kHz BW)
- ArduPilot FC appears as single serial port (one Heltec device)
- Cannot split streams at FC level (no dual-port configuration)
- Need to increase FC message rate for ESP-NOW without overwhelming LoRa

## Proposed Solution: Smart Filtering at Relay (Option 1)

### Architecture

**Two message categories:**

1. **LoRa-Forwarded Messages** (Critical, Low-Rate)
   - Relayed via **BOTH** ESP-NOW AND LoRa
   - Uses existing 3-tier priority queue
   
2. **ESP-NOW-Only Messages** (Accessory, High-Rate)
   - Relayed via **ESP-NOW ONLY**
   - Not forwarded to LoRa queue
   - Separate filtering logic

### Message Classification

#### LoRa-Forwarded Messages (Existing Tier System)

**Tier 0 (Critical - 1s timeout):**
- `76`: COMMAND_LONG (ARM/DISARM/etc)
- `11`: SET_MODE
- `176`: DO_SET_MODE
- `23`: PARAM_SET
- `39`: MISSION_ITEM
- `44`: MISSION_COUNT

**Tier 1 (Important - 2s timeout):**
- `0`: HEARTBEAT (1Hz)
- `24`: GPS_RAW_INT (2-5Hz)
- `30`: ATTITUDE (2-5Hz)
- `33`: GLOBAL_POSITION_INT (2-5Hz)

**Tier 2 (Routine - 5s timeout):**
- `1`: SYS_STATUS (1Hz)
- `147`: BATTERY_STATUS (0.5-1Hz)
- `253`: STATUSTEXT (event-driven)
- `42`: MISSION_CURRENT (0.5Hz)
- Other essential telemetry

#### ESP-NOW-Only Messages (High-Rate Accessory)

**Proposed additions to blacklist for LoRa:**
- `65`: RC_CHANNELS (2-10Hz) - RC input monitoring
- `31`: ATTITUDE_QUATERNION (10-30Hz) - High-rate attitude
- `32`: LOCAL_POSITION_NED (10Hz) - Local position
- `152`: AUTOPILOT_VERSION (one-time)
- `163`: RC_CHANNELS_OVERRIDE (event-driven)
- `62`: NAV_CONTROLLER_OUTPUT (5-10Hz)
- `178`: CAMERA_SETTINGS
- `168`: CAMERA_FEEDBACK
- `193`: VIDEO_STREAM_INFO

**Already blacklisted from LoRa:**
- `27`: RAW_IMU (50Hz)
- `88`: HIL_OPTICAL_FLOW
- `100`: OPTICAL_FLOW
- `106`: HIL_SENSOR
- `129`: SCALED_IMU3
- `132`: Unknown (6.2Hz)
- `241`: DISTANCE_SENSOR (or VIBRATION?)

### Implementation Requirements

#### 1. Relay Node Filtering Logic

In relay nodes (`drone2_primary.cpp`, `drone2_secondary.cpp`):

```cpp
bool shouldForwardToLoRa(uint8_t msgId) {
    // Check if message is in ESP-NOW-only list
    if (isEspNowOnly(msgId)) {
        return false;  // Only relay via ESP-NOW
    }
    return true;  // Forward to LoRa queue
}

void onEspNowReceive(const uint8_t *mac, const uint8_t *data, int len) {
    uint8_t msgId = extractMavlinkMsgId(data);
    
    // Always forward via ESP-NOW to ground (if in range)
    espNowSendToGround(data, len);
    
    // Conditionally forward to LoRa
    if (shouldForwardToLoRa(msgId)) {
        aeroLora.send(data, len);  // Uses existing tier system
    }
}
```

#### 2. MAC Address Configuration

**Known MAC Addresses:**
- Drone1: `[ACTUAL_MAC_FROM_DEVICE]`
- QGC 930MHz: `[ACTUAL_MAC_FROM_DEVICE]`

**Unknown MAC Addresses (TO BE DETERMINED):**
- Relay Primary: `00:11:22:33:44:55` ⚠️ PLACEHOLDER
- Relay Secondary: `00:11:22:33:44:66` ⚠️ PLACEHOLDER

**Action Required:**
1. Flash relay nodes with MAC discovery sketch
2. Record actual MAC addresses
3. Update configuration in code

#### 3. Queue Behavior

**When LoRa queue is full:**
- Option A: Drop ESP-NOW-only messages first (preserve critical LoRa messages)
- Option B: Drop oldest messages regardless of type
- **Recommendation:** Option A - prioritize LoRa reliability

**Separate Queue Architecture:**
- LoRa uses existing 3-tier queue (Tier0=10, Tier1=20, Tier2=30)
- ESP-NOW has separate transmission path (no queuing, immediate send)

#### 4. Relay-to-Relay Behavior

ESP-NOW messages should behave similar to LoRa:
- Relay nodes forward ESP-NOW to each other
- Relay nodes forward ESP-NOW to ground when in range
- No duplicate filtering needed (MAVLink handles this)

### ArduPilot Stream Rate Configuration

**Increase overall message rate** (single serial port config):

```python
# For combined link (Heltec appears as one serial port)
# Messages will be filtered at relay based on category

SR1_POSITION = 5      # Position (5 Hz) - some via LoRa, some ESP-NOW only
SR1_EXTRA1 = 10       # Attitude (10 Hz) - filtered to 2-5Hz for LoRa
SR1_EXTRA2 = 10       # VFR_HUD (10 Hz)
SR1_EXTRA3 = 2        # AHRS, etc (2 Hz)
SR1_EXT_STAT = 2      # Extended status (2 Hz)
SR1_RAW_SENS = 10     # Raw sensors (10 Hz) - ESP-NOW only (blacklisted)
SR1_RC_CHAN = 5       # RC channels (5 Hz) - ESP-NOW only (new blacklist)
```

**Effect:**
- Total throughput increases from FC
- ESP-NOW handles high-rate messages (RAW_IMU, RC_CHANNELS, etc.)
- LoRa only gets filtered critical/important messages
- No queue overflow on relay nodes

## Benefits

✅ **Higher Telemetry Rate:** ESP-NOW can deliver 10-50Hz data when in range  
✅ **LoRa Reliability:** LoRa queue not overwhelmed by high-rate messages  
✅ **No FC Changes:** Single serial port remains, filtering at relay  
✅ **Graceful Degradation:** Out of ESP-NOW range? LoRa still works  
✅ **Existing Priority System:** Reuses proven 3-tier LoRa queue  

## Risks & Considerations

⚠️ **ESP-NOW Less Resilient:** High-rate data only available in close range  
⚠️ **Relay Complexity:** More filtering logic = more potential bugs  
⚠️ **MAC Address Management:** Must track multiple relay node MACs  
⚠️ **Testing Required:** Ensure no critical messages accidentally filtered  

## Testing Plan

### Phase 1: Static Testing
1. Verify message classification (print which path each message takes)
2. Test LoRa queue doesn't overflow with increased FC rate
3. Verify ESP-NOW forwarding works for high-rate messages

### Phase 2: Range Testing
1. Test ESP-NOW cutoff distance
2. Verify LoRa continues working beyond ESP-NOW range
3. Measure actual throughput on both links

### Phase 3: Flight Testing
1. Full flight with both links active
2. Monitor packet drops on both ESP-NOW and LoRa
3. Verify QGC receives all critical data

## Future Enhancements

- **Dynamic Filtering:** Adjust ESP-NOW-only list based on link quality
- **Rate Adaptation:** If LoRa queue fills, temporarily expand blacklist
- **Dual-Band Ground:** Receive ESP-NOW + LoRa simultaneously at ground station

## Related Code Files

### To Modify:
- `src/drone2_primary.cpp` - Add ESP-NOW filtering logic
- `src/drone2_secondary.cpp` - Add ESP-NOW filtering logic
- `include/AeroLoRaProtocol.h` - Expand blacklist array

### Reference:
- `src/AeroLoRaProtocol.cpp` - Existing tier system (line 964-1023)
- `include/AeroLoRaProtocol.h` - Existing blacklist (line 121-129)

## Questions for Future Implementation

1. Should RC_CHANNELS go to ESP-NOW only or stay in LoRa Tier 2?
2. What's the actual ESP-NOW range in flight conditions?
3. Should we add a "hybrid" category (ESP-NOW at high rate, LoRa at low rate)?
4. How to handle message deduplication at ground station?

## Status

**Current:** Planning phase, documented for future implementation  
**Next Steps:** Determine relay node MAC addresses, then implement filtering logic  
**Blocked On:** Other priorities, will revisit when ESP-NOW relay needed
