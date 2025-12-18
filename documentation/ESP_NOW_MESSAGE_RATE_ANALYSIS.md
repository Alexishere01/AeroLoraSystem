# ESP-NOW Message Rate Analysis - Direct Scenario (Drone1 to QGC 930)

## Current Implementation Summary

### What ESP-NOW Sends Currently

Based on code analysis of [aero_lora_drone.cpp](file:///Users/alex/Projects/Antigravity/SeniorDesignInitRelay/src/aero_lora_drone.cpp) and [DualBandTransport.cpp](file:///Users/alex/Projects/Antigravity/SeniorDesignInitRelay/src/DualBandTransport.cpp):

**ESP-NOW sends ALL MAVLink messages from the drone to QGC**, including:

1. **All telemetry streams from the autopilot** (Heartbeat, Attitude, GPS, Battery, etc.)
2. **All parameter requests and responses**
3. **All mission waypoints**
4. **All system status messages**

### Message Routing Logic (DualBandTransport)

```cpp
// From DualBandTransport::send() line 115-150
bool DualBandTransport::send(uint8_t* data, uint8_t len, uint8_t dest_id) {
    uint8_t msgId = extractMavlinkMsgId(data, len);
    
    // 1. ALWAYS send via ESP-NOW (all messages)
    espnow_sent = _espnow->send(data, len);
    
    // 2. Add 5ms spacing between transports
    if (espnow_sent) {
        delay(5);
    }
    
    // 3. Send via LoRa ONLY if message is essential
    if (_filter.isEssential(msgId)) {
        lora_sent = _lora->send(data, len, false, dest_id);
    }
    
    return espnow_sent || lora_sent;
}
```

## CSV Analysis - Why Rates Appear Low

### Drone1.csv Analysis

Looking at the CSV data, I see two important patterns:

1. **TX_ESPNOW events are relatively sparse** (lines 71-76 show bunches of TX_ESPNOW)
2. **The logging is event-driven, not continuous**

#### Key CSV Lines from drone1.csv:
```csv
timestamp_ms,sequence_number,message_id,system_id,event,packet_size
13173,0,0,1,TX_ESPNOW,20      # First ESP-NOW transmission
13265,0,0,1,TX_ESPNOW,34      # 92ms later
13341,0,0,1,TX_ESPNOW,34      # 76ms later
...
```

### Root Causes of Low ESP-NOW Rate in CSV

#### 1. **Logging Only Occurs When Packets Are SENT**

The logging happens in [aero_lora_drone.cpp:703-715](file:///Users/alex/Projects/Antigravity/SeniorDesignInitRelay/src/aero_lora_drone.cpp#L703-L715):

```cpp
logger.logPacket(
    seq, msgId, sysId,
    0.0, 0.0, relayRequestActive,
    event,  // This will be "TX_ESPNOW" if ESP-NOW is reachable
    packetLen,
    millis(),
    queueDepth,
    stats.packets_dropped
);
```

**Problem**: Logging only happens when **complete MAVLink packets** are detected in the UART buffer.

#### 2. **UART Buffer Processing Has 40ms Timeout**

From [aero_lora_drone.cpp:631](file:///Users/alex/Projects/Antigravity/SeniorDesignInitRelay/src/aero_lora_drone.cpp#L631):

```cpp
// Process UART buffer for complete MAVLink packets after timeout (40ms)
if (uartRxIndex > 0 && (now - lastUartRx) >= 40) {
    // Process packet...
}
```

**Impact**: Messages are batched and only processed every 40ms, creating artificial spacing between transmissions.

#### 3. **FC Baud Rate Mismatch** 

Drone configuration shows:
```cpp
#define FC_BAUD 115200  // Line 60
```

But the note says:
```cpp
#define MAVLINK_SERIAL_BAUD 57600  // Line 75
```

**Potential Issue**: If the actual FC is sending at 57600 baud but you're receiving at 115200, you may be getting corrupted data or missing messages.

#### 4. **Missing Parameter Messages**

For QGC to have the drone "ready", it needs:
- **PARAM_VALUE messages** (message ID 22) - ALL parameters
- **HEARTBEAT** (message ID 0) - at 1Hz
- **SYSTEM_TIME** (message ID 2)
- **GPS_RAW_INT** (message ID 24)
- **ATTITUDE** (message ID 30)

## Recommendations to Increase ESP-NOW Rate

### Option 1: Remove 40ms UART Timeout (Immediate Processing)

**Change**: Process MAVLink packets as soon as they arrive, not after 40ms timeout.

**File**: [aero_lora_drone.cpp:631](file:///Users/alex/Projects/Antigravity/SeniorDesignInitRelay/src/aero_lora_drone.cpp#L631)

```cpp
// OLD:
if (uartRxIndex > 0 && (now - lastUartRx) >= 40) {

// NEW:
if (uartRxIndex > 0 && (now - lastUartRx) >= 5) {  // Process after 5ms idle
```

**Impact**: Reduces latency from 40ms to 5ms, allowing faster message forwarding.

---

### Option 2: Remove 5ms Inter-Transport Delay (For Direct Scenario)

**Change**: Remove the 5ms delay between ESP-NOW and LoRa transmissions when ESP-NOW is the only active transport.

**File**: [DualBandTransport.cpp:131-135](file:///Users/alex/Projects/Antigravity/SeniorDesignInitRelay/src/DualBandTransport.cpp#L131-L135)

```cpp
// OLD:
if (espnow_sent) {
    delay(5);  // 5ms spacing between transports
}

// NEW (for direct scenario only):
// Don't delay if LoRa won't be used
if (espnow_sent && _filter.isEssential(msgId)) {
    delay(5);  // Only delay if we're about to use LoRa too
}
```

**Impact**: Removes 5ms delay when only using ESP-NOW, allowing back-to-back transmissions.

---

### Option 3: Increase FC Telemetry Rates (ArduPilot Configuration)

**Change**: Configure the autopilot to send telemetry at higher rates.

**ArduPilot Parameters** (set via QGC or Mission Planner):
```
SR1_EXTRA1    = 10  # Attitude/RC channels at 10Hz
SR1_EXTRA2    = 10  # VFR_HUD at 10Hz  
SR1_EXTRA3    = 5   # GPS/Battery at 5Hz
SR1_POSITION  = 10  # Position at 10Hz
SR1_RAW_SENS  = 5   # IMU at 5Hz
SR1_RC_CHAN   = 5   # RC inputs at 5Hz
```

**Impact**: More messages from FC = more ESP-NOW transmissions logged.

---

### Option 4: Fix UART Baud Rate Configuration

**Change**: Match the UART baud rate to what the FC is actually sending.

**File**: [aero_lora_drone.cpp:60](file:///Users/alex/Projects/Antigravity/SeniorDesignInitRelay/src/aero_lora_drone.cpp#L60)

```cpp
// If FC is sending at 57600:
#define FC_BAUD 57600

// OR if FC is sending at 115200, make sure it's configured that way
```

**Check**: On the autopilot side, verify `SERIAL1_BAUD` parameter matches.

**Impact**: Ensures reliable message reception from FC.

---

### Option 5: Parameter Request at Startup (Auto-Request All Parameters)

**Change**: Add automatic parameter request on connection to QGC.

**New Code** (add to setup() after ESP-NOW init):

```cpp
// Request all parameters from ground station
// This speeds up QGC connection and makes drone "ready" faster
void requestAllParameters() {
    // MAVLink PARAM_REQUEST_LIST message (ID 21)
    uint8_t buf[22];
    buf[0] = 0xFE;           // MAVLink v1
    buf[1] = 4;              // Payload length
    buf[2] = 0;              // Sequence
    buf[3] = 1;              // System ID (drone)
    buf[4] = 0;              // Component ID
    buf[5] = 21;             // Message ID (PARAM_REQUEST_LIST)
    
    // Payload: target_system=255 (GCS), target_component=0
    buf[6] = 255;            // Target system
    buf[7] = 0;              // Target component
    buf[8] = 0;              // Reserved
    buf[9] = 0;              // Reserved
    
    // TODO: Add CRC
    
    dualBandTransport.send(buf, 22, NODE_GROUND);
}
```

**Call in setup()** after line 479:

```cpp
delay(2000);

// Request parameters to speed up QGC connection
Serial.println("[DRONE] Requesting parameters from GCS");
requestAllParameters();

digitalWrite(LED_PIN, LOW);
```

---

## Expected Message Rates After Fix

### Theoretical Maximum (ESP-NOW)

- **ESP-NOW bandwidth**: 200-500 kbps
- **Typical MAVLink message**: 20-60 bytes
- **Theoretical max rate**: ~1000-5000 messages/second

### Realistic Rate (with FC telemetry)

With standard ArduPilot telemetry at 10Hz streams:
- **Heartbeat**: 1 Hz
- **Attitude**: 10 Hz
- **GPS**: 5 Hz  
- **Battery**: 2 Hz
- **VFR_HUD**: 10 Hz
- **RC_CHANNELS**: 5 Hz
- **System Status**: 1 Hz

**Total**: ~35-40 messages/second = **one message every 25-30ms**

### What CSV Should Show After Fix

Instead of:
```csv
13173,TX_ESPNOW  # Sparse, 40ms+ gaps
13265,TX_ESPNOW
13341,TX_ESPNOW
```

You should see:
```csv
1025,TX_ESPNOW   # Regular 25-30ms spacing
1050,TX_ESPNOW
1080,TX_ESPNOW
1105,TX_ESPNOW
```

## Verification Steps

1. **Check actual CSV timestamps** - Calculate time delta between consecutive TX_ESPNOW events
2. **Check FC UART traffic** - Add debug logging to see raw bytes received from FC
3. **Monitor ESP-NOW stats** - Check `espnow_packets_sent` counter in display
4. **Verify QGC connection time** - Should connect and be "ready" within 5-10 seconds

## Next Steps

Which approach would you like to implement first?

1. **Quick fix**: Reduce UART timeout from 40ms → 5ms (Option 1)
2. **Optimize**: Remove 5ms inter-transport delay (Option 2)  
3. **Deep fix**: Verify and fix UART baud rate (Option 4)
4. **FC config**: Increase telemetry rates on autopilot (Option 3)
5. **Smart init**: Add parameter auto-request (Option 5)

I recommend starting with **Option 1 + Option 4** as they address the most likely root causes.
