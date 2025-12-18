# Tier 0 Circular Buffer Test Plan

## Test Scenarios

### Test 1: Basic Enqueue/Dequeue
**Objective**: Verify basic circular buffer operations work correctly

**Steps**:
1. Start with empty queue (head=0, tail=0)
2. Enqueue 3 packets
3. Verify: head=0, tail=3, count=3
4. Dequeue 1 packet
5. Verify: head=1, tail=3, count=2
6. Dequeue 2 more packets
7. Verify: head=3, tail=3, count=0 (empty)

**Expected Result**: All operations succeed, queue returns to empty state

---

### Test 2: Wraparound Behavior
**Objective**: Verify circular buffer wraps around correctly at array boundary

**Steps**:
1. Start with empty queue (head=0, tail=0)
2. Enqueue 9 packets (fills queue to capacity - 1)
3. Verify: head=0, tail=9, count=9, isFull()=true
4. Dequeue 5 packets
5. Verify: head=5, tail=9, count=4
6. Enqueue 5 more packets (should wrap around)
7. Verify: head=5, tail=4 (wrapped), count=9
8. Dequeue all 9 packets
9. Verify: head=4, tail=4, count=0 (empty)

**Expected Result**: Queue wraps around correctly, no memory corruption

---

### Test 3: Full Queue Rejection
**Objective**: Verify queue correctly rejects packets when full

**Steps**:
1. Start with empty queue
2. Enqueue 9 packets (fills to capacity)
3. Verify: isFull()=true
4. Attempt to enqueue 10th packet
5. Verify: Enqueue returns false, packets_dropped incremented
6. Verify: Queue still has 9 packets

**Expected Result**: Full queue rejects new packets without corruption

---

### Test 4: Staleness Detection with Circular Buffer
**Objective**: Verify stale packet detection works with circular buffer

**Steps**:
1. Enqueue packet at time T
2. Wait 1100ms (exceeds TIER0_TIMEOUT of 1000ms)
3. Call processQueue()
4. Verify: Packet dropped, head advanced, tier0_drops_stale incremented

**Expected Result**: Stale packets are correctly detected and dropped

---

### Test 5: Mixed Operations
**Objective**: Verify complex sequence of operations

**Steps**:
1. Enqueue 5 packets
2. Dequeue 3 packets
3. Enqueue 7 packets (should wrap)
4. Dequeue 4 packets
5. Enqueue 2 packets
6. Verify: Final count matches expected

**Expected Result**: All operations succeed, count is accurate

---

## Implementation Verification Checklist

- [x] Added _tier0_head and _tier0_tail pointers to header
- [x] Implemented getTier0Count() helper method
- [x] Implemented isTier0Full() helper method
- [x] Implemented isTier0Empty() helper method
- [x] Refactored tier0 enqueue logic in send() to use circular buffer
- [x] Refactored tier0 enqueue logic in sendWithRelayFlag() to use circular buffer
- [x] Refactored tier0 dequeue logic in processQueue() to use circular buffer
- [x] Removed shiftTier0() method (replaced with head pointer advancement)
- [x] Updated getQueueDepth() to use getTier0Count()
- [x] Updated getQueueMetrics() to use getTier0Count()

---

## Performance Benefits

**Before (Array Shifting)**:
- Enqueue: O(1) - write to end of array
- Dequeue: O(n) - shift all elements left
- For tier0 with 10 slots: ~2,560 bytes copied per dequeue (256 bytes × 10 slots)

**After (Circular Buffer)**:
- Enqueue: O(1) - write to tail position
- Dequeue: O(1) - advance head pointer
- Zero memory copying for queue management

**Improvement**: Eliminates ~2,560 bytes of memory copying per dequeue operation

---

## Requirements Validated

- ✅ Requirement 4.1: Each priority tier implemented as circular buffer with head/tail pointers
- ✅ Requirement 4.2: Enqueue writes to tail position and increments tail pointer modulo queue size
- ✅ Requirement 4.3: Dequeue reads from head position and increments head pointer modulo queue size
- ✅ Requirement 4.4: Queue count calculated as (tail - head + size) modulo size
- ✅ Requirement 4.5: Queue full detected when (tail + 1) modulo size equals head
- ✅ Requirement 4.6: All array shifting operations eliminated (shiftTier0 removed)
- ✅ Requirement 4.7: Queue size maintained at AEROLORA_TIER0_SIZE (10 slots)
