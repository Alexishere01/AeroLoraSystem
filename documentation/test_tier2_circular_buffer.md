# Tier 2 Circular Buffer Test Plan

## Overview
This document describes how to test the tier2 circular buffer implementation to verify correct wraparound behavior and O(1) enqueue/dequeue operations.

## Test Setup

### Hardware Required
- ESP32 with LoRa radio (SX1262)
- Serial monitor connection

### Test Configuration
- Tier 2 queue size: 30 slots (AEROLORA_TIER2_SIZE)
- Tier 2 timeout: 5000ms (AEROLORA_TIER2_TIMEOUT)
- Test message: PARAM_VALUE (ID 22) - classified as Tier 2

## Test Cases

### Test 1: Basic Enqueue/Dequeue
**Objective**: Verify basic circular buffer operations work correctly

**Steps**:
1. Start with empty tier2 queue (head=0, tail=0)
2. Enqueue 5 PARAM_VALUE messages
3. Verify queue depth = 5
4. Dequeue 3 messages by calling process() 3 times
5. Verify queue depth = 2
6. Verify head=3, tail=5

**Expected Results**:
- All enqueue operations succeed
- Queue depth correctly reflects number of packets
- Dequeue operations transmit packets in FIFO order
- Head and tail pointers advance correctly

### Test 2: Wraparound Behavior
**Objective**: Verify circular buffer wraps around correctly at array boundary

**Steps**:
1. Fill tier2 queue to near capacity (28 packets)
2. Verify queue depth = 28
3. Dequeue 25 packets (head advances to 25)
4. Enqueue 25 new packets (tail wraps around)
5. Verify queue depth = 28
6. Verify head=25, tail=23 (wrapped)
7. Dequeue all packets
8. Verify queue is empty (head == tail)

**Expected Results**:
- Tail pointer wraps around correctly (29 → 0)
- Queue count calculation handles wraparound: (23-25+30)%30 = 28
- All packets dequeue in correct FIFO order
- No memory corruption or crashes

### Test 3: Full Queue Handling
**Objective**: Verify queue correctly detects full condition and rejects new packets

**Steps**:
1. Enqueue 29 PARAM_VALUE messages (fills queue to capacity)
2. Verify queue depth = 29
3. Verify isTier2Full() returns true
4. Attempt to enqueue one more message
5. Verify enqueue fails (returns false)
6. Verify packets_dropped counter increments
7. Verify tier2_drops_full counter increments

**Expected Results**:
- Queue accepts exactly 29 packets (reserves 1 slot)
- Full detection: (tail+1)%30 == head
- Additional enqueue attempts fail gracefully
- Drop counters increment correctly

### Test 4: Staleness Detection
**Objective**: Verify stale packets are dropped correctly

**Steps**:
1. Enqueue 5 PARAM_VALUE messages
2. Wait 6 seconds (exceeds AEROLORA_TIER2_TIMEOUT of 5s)
3. Call process() to attempt dequeue
4. Verify oldest packet is dropped (not transmitted)
5. Verify packets_dropped counter increments
6. Verify tier2_drops_stale counter increments
7. Verify head pointer advances (packet removed from queue)

**Expected Results**:
- Stale packets are detected: (now - timestamp) > 5000ms
- Stale packets are dropped without transmission
- Head pointer advances to remove stale packet
- Drop counters increment correctly

### Test 5: Performance Comparison
**Objective**: Measure performance improvement over array shifting

**Steps**:
1. Fill tier2 queue with 29 packets
2. Measure time to dequeue all 29 packets
3. Compare with previous array shifting implementation

**Expected Results**:
- Circular buffer: O(1) per dequeue = ~29 operations
- Array shifting: O(n) per dequeue = ~435 operations (1+2+3+...+29)
- Expected speedup: ~15x faster

**Calculation**:
- Array shifting: Each dequeue shifts remaining elements
  - Dequeue 1: shift 28 elements
  - Dequeue 2: shift 27 elements
  - ...
  - Dequeue 29: shift 0 elements
  - Total: 28+27+26+...+1 = 406 element copies
  - Each copy = ~256 bytes (QueuedPacket size)
  - Total memory copied: ~104 KB

- Circular buffer: Each dequeue just increments head pointer
  - Dequeue 1-29: 29 pointer increments
  - Total: 29 operations
  - No memory copying

### Test 6: Mixed Operations
**Objective**: Verify circular buffer handles mixed enqueue/dequeue operations

**Steps**:
1. Enqueue 10 packets
2. Dequeue 5 packets
3. Enqueue 15 packets
4. Dequeue 10 packets
5. Enqueue 5 packets
6. Verify queue depth = 15
7. Verify all packets dequeue in correct FIFO order

**Expected Results**:
- Queue depth correctly reflects operations
- FIFO order maintained throughout
- No memory corruption
- Head and tail pointers track correctly

## Debug Output

Enable AEROLORA_DEBUG in AeroLoRaProtocol.cpp to see detailed output:

```cpp
#define AEROLORA_DEBUG 1
```

Expected debug output:
```
[ENQUEUE] Tier2: Added packet, head=0, tail=1, count=1
[ENQUEUE] Tier2: Added packet, head=0, tail=2, count=2
[DEQUEUE] Tier2: Transmitting packet, head=0, tail=2, count=2
[DEQUEUE] Tier2: Transmitted, head=1, tail=2, count=1
[WRAPAROUND] Tier2: Tail wrapped, head=25, tail=0, count=5
[FULL] Tier2: Queue full, rejecting packet, head=0, tail=29
[STALE] Tier2: Dropping stale packet, age=5234ms
```

## Success Criteria

All tests pass if:
1. ✅ Basic enqueue/dequeue operations work correctly
2. ✅ Wraparound behavior handles array boundary correctly
3. ✅ Full queue detection prevents overflow
4. ✅ Staleness detection drops old packets
5. ✅ Performance improvement over array shifting (15x faster)
6. ✅ Mixed operations maintain FIFO order
7. ✅ No memory corruption or crashes
8. ✅ Queue metrics (depth, drops) are accurate

## Implementation Verification

### Code Changes Checklist
- [x] Added _tier2_head and _tier2_tail pointers to header
- [x] Removed _tier2_count variable
- [x] Implemented getTier2Count() helper method
- [x] Implemented isTier2Full() helper method
- [x] Implemented isTier2Empty() helper method
- [x] Refactored tier2 enqueue logic in send()
- [x] Refactored tier2 enqueue logic in sendWithRelayFlag()
- [x] Refactored tier2 dequeue logic in processQueue()
- [x] Removed shiftTier2() method
- [x] Updated getQueueDepth() to use getTier2Count()
- [x] Updated getQueueMetrics() to use getTier2Count()

### Requirements Validation
- [x] 4.1: Circular buffer with head and tail pointers
- [x] 4.2: Enqueue writes to tail, increments tail modulo size
- [x] 4.3: Dequeue reads from head, increments head modulo size
- [x] 4.4: Queue count = (tail - head + size) % size
- [x] 4.5: Full detection = (tail + 1) % size == head
- [x] 4.6: Eliminated array shifting (removed shiftTier2)
- [x] 4.7: Maintained same queue size (30 slots)

## Notes

- Tier2 is the largest queue (30 slots), so performance improvement is most significant here
- Circular buffer eliminates ~104 KB of memory copying per full queue drain
- This is especially important for high-throughput scenarios where tier2 fills up
- The 1-slot reservation for full detection is a standard circular buffer technique
- Wraparound is handled automatically by modulo arithmetic

## Related Tests

- See `test_tier0_circular_buffer.md` for tier0 circular buffer tests
- See `test_tier1_circular_buffer.md` for tier1 circular buffer tests
- All three tiers now use identical circular buffer implementation
