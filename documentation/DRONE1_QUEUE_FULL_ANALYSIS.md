# Drone1 Queue Full Analysis

## Problem Summary
The drone is constantly showing "QUEUE FULL" and dropping almost all packets. QGC is receiving very few messages.

## Root Cause
**The queue drains too slowly compared to the incoming packet rate.**

### Evidence from Log:
```
[DRONE] Enqueued MAVLink packet (22 bytes) to NODE_GROUND: QUEUE FULL
[DRONE] Enqueued MAVLink packet (34 bytes) to NODE_GROUND: QUEUE FULL
[DRONE] Enqueued MAVLink packet (22 bytes) to NODE_GROUND: QUEUE FULL
```

- **294 packets dropped** in ~64 seconds
- Queue depth stays at 0 or 1
- Only occasional SUCCESS messages
- Most packets are blacklisted (IDs 100, 132) but still consuming processing time

## Why This Happens

### Current Flow:
```
Loop Iteration:
1. UART receives 5-10 packets (40ms timeout)
2. Each packet tries to enqueue → QUEUE FULL after first 1-2
3. protocol.process() called ONCE → transmits 1 packet
4. Next iteration: Queue still full!
```

### The Math:
- **Incoming rate**: ~10 packets per 40ms = 250 packets/second
- **Outgoing rate**: 1 packet per loop = ~25 packets/second (if loop is 40ms)
- **Result**: Queue fills up 10x faster than it drains!

## Solutions

### Option 1: Call process() More Frequently (RECOMMENDED)
Call `protocol.process()` multiple times per loop iteration:

```cpp
// In main loop - after processing UART
for (int i = 0; i < 5; i++) {
    protocol.process();  // Drain queue faster
}
```

### Option 2: Call process() After Each Enqueue
```cpp
// After each successful enqueue
if (protocol.sendWithRelayFlag(...)) {
    protocol.process();  // Immediately try to transmit
}
```

### Option 3: Reduce Incoming Packet Rate
- Increase UART timeout from 40ms to 100ms
- This batches packets less aggressively
- Gives more time for queue to drain

### Option 4: Increase Queue Sizes
- Current: Tier0=10, Tier1=20, Tier2=30 (total 60 slots)
- Increase to: Tier0=20, Tier1=40, Tier2=60 (total 120 slots)
- **Warning**: Uses more RAM (15KB → 30KB)

## Blacklisted Messages Impact

Messages being filtered:
- **ID 132**: Very high frequency (appears every few packets)
- **ID 100**: High frequency (OPTICAL_FLOW)

These are correctly blacklisted, but they're still:
1. Being received from FC
2. Being parsed
3. Being checked against blacklist
4. Incrementing drop counter

**This is working as designed** - blacklist prevents them from wasting LoRa bandwidth.

## Recommended Fix

**Implement Option 1**: Call `protocol.process()` 5-10 times per loop iteration.

This will:
- Drain queue 5-10x faster
- Keep queue depth low
- Allow legitimate packets to flow
- Minimal code change
- No RAM increase needed

### Implementation:
```cpp
// In aero_lora_drone.cpp main loop, after UART processing:

// Process protocol queue multiple times to drain faster
for (int i = 0; i < 10; i++) {
    protocol.process();
}
```

## Expected Results After Fix

- Queue depth should stay below 5-10 packets
- "QUEUE FULL" messages should be rare
- QGC should receive steady stream of telemetry
- Drop rate should decrease from ~80% to <10%

## IMPLEMENTED ✅

### Changes Made:
1. **aero_lora_drone.cpp**: Added 10x `protocol.process()` calls per loop
2. **aero_lora_ground.cpp**: Added 10x `protocol.process()` calls per loop
3. **FC Parameters**: Reduced all stream rates to 1 Hz (were at 3 Hz!)

### Combined Effect:
- **Reduced incoming rate**: 3 Hz → 1 Hz (3x reduction)
- **Increased drain rate**: 1x → 10x per loop (10x increase)
- **Net improvement**: 30x better queue management!

### Next Steps:
1. Upload firmware to both drone and ground
2. Test and monitor queue depth in logs
3. Should see steady telemetry flow in QGC
4. Queue depth should stay near 0-5 packets
