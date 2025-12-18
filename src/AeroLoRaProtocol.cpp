/**
 * AeroLoRa Protocol Implementation
 * 
 * This file implements a lightweight transport layer for MAVLink over LoRa.
 * 
 * Key design decisions:
 * 1. Hardware CRC: SX1262 radio handles error detection automatically
 * 2. No ACK/NACK: MAVLink already implements reliability at application layer
 * 3. Priority queuing: Critical commands must not be blocked by telemetry
 * 4. Staleness detection: Old packets are automatically dropped
 * 
 * The protocol is intentionally simple to minimize overhead and latency.
 * Reliability is handled by MAVLink where it belongs (application layer).
 */

// Debug output control
// Set to 1 to enable verbose debug output, 0 to disable (prevents serial flooding)
// When disabled, only critical error messages are shown
// #define AEROLORA_DEBUG 1 <-- Removed, using global DEBUG_LOGGING instead

#include "AeroLoRaProtocol.h"

// ═══════════════════════════════════════════════════════════════════
// CONSTRUCTOR
// ═══════════════════════════════════════════════════════════════════

/**
 * Initialize protocol with radio and TDMA parameters
 * 
 * Note: Sequence numbers and ACK/NACK state removed - not needed.
 * MAVLink handles reliability, hardware handles error detection.
 */
AeroLoRaProtocol::AeroLoRaProtocol(SX1262* radio, uint8_t slot_offset, uint16_t slot_duration) {
    _radio = radio;
    _my_node_id = 0xFF;  // Invalid until begin() is called
    _slot_offset = slot_offset;
    _slot_duration = slot_duration;
    
    // Initialize tier0 circular buffer pointers (Requirements 4.1, 4.2)
    _tier0_head = 0;  // Start of queue
    _tier0_tail = 0;  // End of queue (empty when head == tail)
    
    // Initialize tier1 circular buffer pointers (Requirements 4.1, 4.2)
    _tier1_head = 0;  // Start of queue
    _tier1_tail = 0;  // End of queue (empty when head == tail)
    
    // Initialize tier2 circular buffer pointers (Requirements 4.1, 4.2)
    _tier2_head = 0;  // Start of queue
    _tier2_tail = 0;  // End of queue (empty when head == tail)
    
    // Initialize receive buffer
    _rx_len = 0;
    _rx_ready = false;
    
    // Initialize timing
    _last_tx = 0;
    
    // Initialize statistics
    memset(&_stats, 0, sizeof(AeroLoRaStats));
    
    // Initialize queue metrics
    memset(&_metrics, 0, sizeof(QueueMetrics));
    
    // Initialize rate limiting - set all last TX times to 0
    memset(_last_tx_time, 0, sizeof(_last_tx_time));
    
    // Initialize CSMA/CA state
    _csma_enabled = true;  // Enable CSMA/CA with improved exponential backoff
    _csma_retry_count = 0;
    _csma_backoff_window = CSMA_MIN_BACKOFF_MS;
    _csma_last_tx_time = 0;
    _csma_consecutive_tx = 0;
    
    // Initialize CSMA/CA statistics
    _csma_channel_busy_count = 0;
    _csma_backoff_count = 0;
    _csma_cad_successes = 0;
    _csma_cad_failures = 0;
}

// ═══════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════

bool AeroLoRaProtocol::begin(uint8_t node_id) {
    // Store node identity
    _my_node_id = node_id;
    
    // Radio should already be initialized by caller
    return true;
}

// ═══════════════════════════════════════════════════════════════════
// TDMA SLOT MANAGEMENT (DISABLED FOR TESTING)
// ═══════════════════════════════════════════════════════════════════

/**
 * Check if current time is in our transmit slot
 * 
 * Currently disabled for testing - always returns true.
 * In future, this will implement proper TDMA slot management to avoid collisions.
 */
bool AeroLoRaProtocol::isMyTxSlot() {
    return true;  // ALWAYS our slot for testing
}

/**
 * Get time until next transmit slot
 * 
 * Currently disabled for testing - always returns current time.
 * In future, this will calculate next available TDMA slot.
 */
unsigned long AeroLoRaProtocol::getNextTxSlot() {
    return millis();  // Can transmit immediately
}

// ═══════════════════════════════════════════════════════════════════
// SENDING
// ═══════════════════════════════════════════════════════════════════

/**
 * Send data by enqueueing to appropriate priority tier
 * 
 * Priority is automatically determined by extracting the MAVLink message ID
 * from the packet data and classifying it into one of three tiers:
 * - Tier 0: Critical commands (ARM, DISARM, SET_MODE, etc.)
 * - Tier 1: Important telemetry (HEARTBEAT, GPS, ATTITUDE, etc.)
 * - Tier 2: Routine telemetry (everything else)
 * 
 * The 'priority' parameter is ignored (legacy from old implementation).
 * 
 * @param data MAVLink packet data
 * @param len Length of data (max 250 bytes)
 * @param priority Legacy parameter (ignored)
 * @param dest_id Destination node ID (default AERO_BROADCAST for backward compatibility)
 * @return true if enqueued successfully, false if queue full
 */
bool AeroLoRaProtocol::send(uint8_t* data, uint8_t len, bool priority, uint8_t dest_id) {
    if (len > AEROLORA_MAX_PAYLOAD) {
        return false;
    }
    
    // Extract MAVLink message ID from data
    uint8_t msgId = extractMavlinkMsgId(data);
    
    // Check if message is blacklisted (centralized filtering)
    if (isBlacklisted(msgId)) {
        // Message is blacklisted - drop it before enqueueing
        _stats.packets_dropped++;
        _metrics.blacklist_drops[msgId]++;
        
        _metrics.blacklist_drops[msgId]++;
        
#if DEBUG_LOGGING
        // Optional debug output for testing
        Serial.print("[FILTER] Dropped blacklisted message ID: ");
        Serial.println(msgId);
#endif
        
        return false;  // Reject blacklisted message
    }
    
    // Check if message should be rate limited (Requirements 3.1-3.7)
    if (shouldRateLimit(msgId)) {
        // Message arrived too soon - drop it
        _stats.packets_dropped++;
        _metrics.rate_limit_drops[msgId]++;
        
        _metrics.rate_limit_drops[msgId]++;
        
#if DEBUG_LOGGING
        // Optional debug output for testing
        Serial.print("[RATE_LIMIT] Dropped message ID ");
        Serial.print(msgId);
        Serial.print(" (too soon, last TX: ");
        Serial.print(millis() - _last_tx_time[msgId]);
        Serial.println("ms ago)");
#endif
        
        return false;  // Reject rate-limited message
    }
    
    // Determine priority tier based on message ID
    int8_t tier = getPriority(msgId);
    
    // Enqueue to appropriate tier array if space available
    switch(tier) {
        case 0:  // Critical commands (circular buffer - Requirement 4.2)
            if (isTier0Full()) {
                _stats.packets_dropped++;
                _metrics.tier0_drops_full++;
                return false;  // Tier 0 queue full
            }
            
            // Add to tier0 queue at tail position (circular buffer enqueue)
            memcpy(_tier0_queue[_tier0_tail].data, data, len);
            _tier0_queue[_tier0_tail].len = len;
            _tier0_queue[_tier0_tail].dest_id = dest_id;
            _tier0_queue[_tier0_tail].priority = 0;
            _tier0_queue[_tier0_tail].timestamp = millis();
            _tier0_queue[_tier0_tail].relay_requested = false;  // No relay flag by default
            
            // Advance tail pointer (circular - Requirement 4.2)
            if (AEROLORA_TIER0_SIZE > 0) {
                _tier0_tail = (_tier0_tail + 1) % AEROLORA_TIER0_SIZE;
            } else {
                _tier0_tail = 0;
            }
            
            // Update last transmission time for rate limiting
            _last_tx_time[msgId] = millis();
            
            return true;
            
        case 1:  // Important telemetry (circular buffer - Requirement 4.2)
            if (isTier1Full()) {
                _stats.packets_dropped++;
                _metrics.tier1_drops_full++;
                return false;  // Tier 1 queue full
            }
            
            // Add to tier1 queue at tail position (circular buffer enqueue)
            memcpy(_tier1_queue[_tier1_tail].data, data, len);
            _tier1_queue[_tier1_tail].len = len;
            _tier1_queue[_tier1_tail].dest_id = dest_id;
            _tier1_queue[_tier1_tail].priority = 1;
            _tier1_queue[_tier1_tail].timestamp = millis();
            _tier1_queue[_tier1_tail].relay_requested = false;  // No relay flag by default
            
            // Advance tail pointer (circular - Requirement 4.2)
            if (AEROLORA_TIER1_SIZE > 0) {
                _tier1_tail = (_tier1_tail + 1) % AEROLORA_TIER1_SIZE;
            } else {
                _tier1_tail = 0;
            }
            
            // Update last transmission time for rate limiting
            _last_tx_time[msgId] = millis();
            
            return true;
            
        case 2:  // Routine telemetry and parameters (circular buffer - Requirement 4.2)
        default:
            if (isTier2Full()) {
                _stats.packets_dropped++;
                _metrics.tier2_drops_full++;
                return false;  // Tier 2 queue full
            }
            
            // Add to tier2 queue at tail position (circular buffer enqueue)
            memcpy(_tier2_queue[_tier2_tail].data, data, len);
            _tier2_queue[_tier2_tail].len = len;
            _tier2_queue[_tier2_tail].dest_id = dest_id;
            _tier2_queue[_tier2_tail].priority = 2;
            _tier2_queue[_tier2_tail].timestamp = millis();
            _tier2_queue[_tier2_tail].relay_requested = false;  // No relay flag by default
            
            // Advance tail pointer (circular - Requirement 4.2)
            if (AEROLORA_TIER2_SIZE > 0) {
                _tier2_tail = (_tier2_tail + 1) % AEROLORA_TIER2_SIZE;
            } else {
                _tier2_tail = 0;
            }
            
            // Update last transmission time for rate limiting
            _last_tx_time[msgId] = millis();
            
            return true;
    }
}

/**
 * Send data with relay request flag
 * 
 * This method allows the sender to request relay assistance by setting
 * the RELAY_REQUEST_FLAG bit in the packet header. This signals to
 * relay-capable nodes that the sender is experiencing a weak link and
 * needs help forwarding packets to the destination.
 * 
 * The relay request flag is stored in the queued packet and applied
 * during transmission by the processQueue() method.
 * 
 * @param data MAVLink packet data
 * @param len Length of data (max 250 bytes)
 * @param requestRelay If true, set relay request flag in header
 * @param dest_id Destination node ID (default AERO_BROADCAST)
 * @return true if enqueued successfully, false if queue full
 */
bool AeroLoRaProtocol::sendWithRelayFlag(uint8_t* data, uint8_t len, bool requestRelay, uint8_t dest_id) {
    if (len > AEROLORA_MAX_PAYLOAD) {
        return false;
    }
    
    // Extract MAVLink message ID from data
    uint8_t msgId = extractMavlinkMsgId(data);
    
    // Check if message is blacklisted (centralized filtering)
    if (isBlacklisted(msgId)) {
        // Message is blacklisted - drop it before enqueueing
        _stats.packets_dropped++;
        _metrics.blacklist_drops[msgId]++;
        
        _metrics.blacklist_drops[msgId]++;
        
#if DEBUG_LOGGING
        // Optional debug output for testing
        Serial.print("[FILTER] Dropped blacklisted message ID: ");
        Serial.println(msgId);
#endif
        
        return false;  // Reject blacklisted message
    }
    
    // Check if message should be rate limited (Requirements 3.1-3.7)
    if (shouldRateLimit(msgId)) {
        // Message arrived too soon - drop it
        _stats.packets_dropped++;
        _metrics.rate_limit_drops[msgId]++;
        
        _metrics.rate_limit_drops[msgId]++;
        
#if DEBUG_LOGGING
        // Optional debug output for testing
        Serial.print("[RATE_LIMIT] Dropped message ID ");
        Serial.print(msgId);
        Serial.print(" (too soon, last TX: ");
        Serial.print(millis() - _last_tx_time[msgId]);
        Serial.println("ms ago)");
#endif
        
        return false;  // Reject rate-limited message
    }
    
    // Determine priority tier based on message ID
    int8_t tier = getPriority(msgId);
    
    // Enqueue to appropriate tier array if space available
    switch(tier) {
        case 0:  // Critical commands (circular buffer - Requirement 4.2)
            if (isTier0Full()) {
                _stats.packets_dropped++;
                _metrics.tier0_drops_full++;
                return false;  // Tier 0 queue full
            }
            
            // Add to tier0 queue at tail position (circular buffer enqueue)
            memcpy(_tier0_queue[_tier0_tail].data, data, len);
            _tier0_queue[_tier0_tail].len = len;
            _tier0_queue[_tier0_tail].dest_id = dest_id;
            _tier0_queue[_tier0_tail].priority = 0;
            _tier0_queue[_tier0_tail].timestamp = millis();
            _tier0_queue[_tier0_tail].relay_requested = requestRelay;  // Store relay flag
            
            // Advance tail pointer (circular - Requirement 4.2)
            if (AEROLORA_TIER0_SIZE > 0) {
                _tier0_tail = (_tier0_tail + 1) % AEROLORA_TIER0_SIZE;
            } else {
                _tier0_tail = 0;
            }
            
            // Update last transmission time for rate limiting
            _last_tx_time[msgId] = millis();
            
            return true;
            
        case 1:  // Important telemetry (circular buffer - Requirement 4.2)
            if (isTier1Full()) {
                _stats.packets_dropped++;
                _metrics.tier1_drops_full++;
                return false;  // Tier 1 queue full
            }
            
            // Add to tier1 queue at tail position (circular buffer enqueue)
            memcpy(_tier1_queue[_tier1_tail].data, data, len);
            _tier1_queue[_tier1_tail].len = len;
            _tier1_queue[_tier1_tail].dest_id = dest_id;
            _tier1_queue[_tier1_tail].priority = 1;
            _tier1_queue[_tier1_tail].timestamp = millis();
            _tier1_queue[_tier1_tail].relay_requested = requestRelay;  // Store relay flag
            
            // Advance tail pointer (circular - Requirement 4.2)
            if (AEROLORA_TIER1_SIZE > 0) {
                _tier1_tail = (_tier1_tail + 1) % AEROLORA_TIER1_SIZE;
            } else {
                _tier1_tail = 0;
            }
            
            // Update last transmission time for rate limiting
            _last_tx_time[msgId] = millis();
            
            return true;
            
        case 2:  // Routine telemetry and parameters (circular buffer - Requirement 4.2)
        default:
            if (isTier2Full()) {
                _stats.packets_dropped++;
                _metrics.tier2_drops_full++;
                return false;  // Tier 2 queue full
            }
            
            // Add to tier2 queue at tail position (circular buffer enqueue)
            memcpy(_tier2_queue[_tier2_tail].data, data, len);
            _tier2_queue[_tier2_tail].len = len;
            _tier2_queue[_tier2_tail].dest_id = dest_id;
            _tier2_queue[_tier2_tail].priority = 2;
            _tier2_queue[_tier2_tail].timestamp = millis();
            _tier2_queue[_tier2_tail].relay_requested = requestRelay;  // Store relay flag
            
            // Advance tail pointer (circular - Requirement 4.2)
            if (AEROLORA_TIER2_SIZE > 0) {
                _tier2_tail = (_tier2_tail + 1) % AEROLORA_TIER2_SIZE;
            } else {
                _tier2_tail = 0;
            }
            
            // Update last transmission time for rate limiting
            _last_tx_time[msgId] = millis();
            
            return true;
    }
}

/**
 * Send immediate (legacy method)
 * 
 * This method was originally used to bypass the queue for ACK/NACK packets.
 * Since ACK/NACK mechanism has been removed, this method is deprecated.
 * 
 * Currently just builds and transmits a packet immediately.
 * Will be removed in future versions.
 * 
 * @param data Packet data
 * @param len Length of data
 * @param dest_id Destination node ID (default AERO_BROADCAST)
 * @return true if transmitted successfully
 */
bool AeroLoRaProtocol::sendImmediate(uint8_t* data, uint8_t len, uint8_t dest_id) {
    // Legacy method - originally for ACKs/NACKs (now removed)
    AeroLoRaPacket packet;
    packet.header = AEROLORA_HEADER;
    packet.dest_id = dest_id;  // Use provided destination
    packet.payload_len = len;
    
    if (len > 0) {
        memcpy(packet.payload, data, len);
    }
    
    // Hardware CRC is automatically appended by radio
    // src_id will be populated by transmitPacket()
    
    return transmitPacket(&packet);
}

// ═══════════════════════════════════════════════════════════════════
// TRANSMIT PACKET
// ═══════════════════════════════════════════════════════════════════

/**
 * Transmit packet over radio
 * 
 * Packet structure sent over the air:
 * - Application layer: header (1 byte) + src_id (1 byte) + dest_id (1 byte) + payload_len (1 byte) + payload (0-250 bytes)
 * - Hardware layer: CRC (2 bytes) automatically appended by SX1262 radio
 * 
 * Total overhead: 4 bytes application + 2 bytes hardware CRC = 6 bytes
 * Previous version: 2 bytes application + 2 bytes hardware = 4 bytes
 * Note: Added 2 bytes for addressing (src_id + dest_id)
 * 
 * @param packet Pointer to packet to transmit
 * @return true if transmitted successfully
 */
bool AeroLoRaProtocol::transmitPacket(AeroLoRaPacket* packet) {
    if (_radio == nullptr) return false;

    // Populate source ID with our node identity
    packet->src_id = _my_node_id;
    
    // Calculate packet size: header (1) + src_id (1) + dest_id (1) + len (1) + payload
    // Hardware CRC (2 bytes) is automatically appended by radio
    uint16_t packet_size = 4 + packet->payload_len;
    
    // Transmit packet
    int state = _radio->transmit((uint8_t*)packet, packet_size);
    
    // Return to receive mode
    _radio->startReceive();
    
    // Update timing
    _last_tx = millis();
    
    // Update statistics
    if (state == RADIOLIB_ERR_NONE) {
        _stats.packets_sent++;
        return true;
    } else {
        _stats.packets_dropped++;
        return false;
    }
}

// ═══════════════════════════════════════════════════════════════════
// RECEIVING
// ═══════════════════════════════════════════════════════════════════

bool AeroLoRaProtocol::available() {
    return _rx_ready;
}

uint8_t AeroLoRaProtocol::receive(uint8_t* buffer, uint8_t max_len) {
    if (!_rx_ready) {
        return 0;
    }
    
    uint8_t len = min(_rx_len, max_len);
    memcpy(buffer, _rx_buffer, len);
    
    _rx_ready = false;
    _rx_len = 0;
    
    return len;
}

/**
 * Handle received packet (called from radio interrupt handler)
 * 
 * Important: If this method is called, the packet has already been validated
 * by the SX1262 hardware CRC. Invalid packets are silently discarded by the
 * radio and never trigger an interrupt.
 * 
 * This method:
 * 1. Checks if packet is addressed to us (dest_id matches _my_node_id or is AERO_BROADCAST)
 * 2. Filters out packets not addressed to us (for future relay support)
 * 3. Updates LED pattern for visual feedback
 * 4. Increments received packet counter
 * 5. Copies payload to RX buffer for application layer
 * 
 * Packet filtering (Requirements 6.1, 6.2, 6.3, 6.4):
 * - Only process packets where dest_id == _my_node_id or dest_id == AERO_BROADCAST
 * - Silently ignore packets addressed to other nodes (future relay will handle these)
 * - Debug output shows source and destination for all received packets
 * 
 * No ACK/NACK handling - MAVLink handles reliability at application layer.
 * No duplicate detection - not needed without ACK/NACK mechanism.
 * No sequence number checking - removed with ACK/NACK mechanism.
 * 
 * @param packet Pointer to received packet (CRC already validated)
 */
void AeroLoRaProtocol::handleReceivedPacket(AeroLoRaPacket* packet) {
    // Hardware CRC already verified - if we're here, packet is valid
    
    // Hardware CRC already verified - if we're here, packet is valid
    
#if DEBUG_LOGGING
    // Debug output: Show source and destination of received packet
    Serial.print("[RX] From node ");
    Serial.print(packet->src_id);
    Serial.print(" to node ");
    Serial.print(packet->dest_id);
    Serial.print(" (I am node ");
    Serial.print(_my_node_id);
    Serial.print(") - ");
#endif
    
    // Packet filtering: Check if packet is addressed to us
    // Requirements 6.1, 6.2, 6.3: Process packets where dest_id matches our node ID or is broadcast
    if (packet->dest_id != _my_node_id && packet->dest_id != AERO_BROADCAST) {
        // Requirement 6.4: Silently ignore packets not addressed to us
        // Requirement 7.1, 7.2: Placeholder for future relay functionality
        
        // ═══════════════════════════════════════════════════════════════════
        // FUTURE RELAY FORWARDING HOOK (Placeholder)
        // ═══════════════════════════════════════════════════════════════════
        // 
        // This is where transparent relay forwarding will be implemented.
        // 
        // Future relay design (Requirements 7.1, 7.2):
        // - Drone A receives MAVLink packet with sysId != its own
        // - Drone A detects packet is not for local processing
        // - Drone A forwards complete packet via UART to external Relay Heltec
        // - Relay Heltec operates on different frequency to avoid interference
        // - This keeps relay logic simple and avoids same-frequency collisions
        // 
        // Implementation approach:
        // 1. Check if relay mode is enabled (configuration flag)
        // 2. If enabled, forward packet to UART (e.g., Serial2)
        // 3. External relay device receives packet and retransmits on different frequency
        // 4. This avoids complex routing logic and frequency coordination
        // 
        // Example code (to be implemented):
        // if (relay_enabled) {
        //     // Forward packet to external relay via UART
        //     Serial2.write((uint8_t*)packet, 4 + packet->payload_len);
        //     _stats.packets_relayed++;  // Track relay activity
        // } else {
        //     _stats.packets_ignored++;  // Track ignored packets
        // }
        // 
        // Benefits of UART-based relay:
        // - Simple implementation (just forward bytes)
        // - No frequency coordination needed (relay uses different frequency)
        // - No collision risk (separate frequency bands)
        // - Easy to disable/enable relay functionality
        // - External relay can be added/removed without firmware changes
        // 
        // ═══════════════════════════════════════════════════════════════════
        
        // ═══════════════════════════════════════════════════════════════════
        
#if DEBUG_LOGGING
        Serial.println("Not for us, ignoring");
#endif
        _stats.packets_ignored++;  // Track packets not for us
        return;  // Packet not for us, ignore it
    }
    
#if DEBUG_LOGGING
    Serial.println("Processing");
#endif
    
    // Extract MAVLink message ID from payload for blacklist filtering
    uint8_t msgId = extractMavlinkMsgId(packet->payload);
    
    // Check if message is blacklisted (centralized filtering - defense in depth)
    // Even though blacklisted messages shouldn't be transmitted, we filter on receive
    // to protect against misconfigured nodes and ensure QGC never sees them
    if (isBlacklisted(msgId)) {
        // Message is blacklisted - drop it before copying to RX buffer
        _stats.packets_dropped++;
        
        _stats.packets_dropped++;
        
#if DEBUG_LOGGING
        // Debug output for testing and monitoring
        Serial.print("[FILTER] Dropped blacklisted message ID: ");
        Serial.println(msgId);
#endif
        
        return;  // Drop blacklisted message
    }
    
    // Update LED pattern for visual feedback (good RX)
    extern uint8_t ledPattern;
    extern unsigned long lastLedUpdate;
    ledPattern = 2;  // Good RX pattern
    lastLedUpdate = millis();
    
    // Update statistics
    _stats.packets_received++;
    
    // Copy payload to RX buffer for application layer
    _rx_len = packet->payload_len;
    memcpy(_rx_buffer, packet->payload, _rx_len);
    _rx_ready = true;
}

// ═══════════════════════════════════════════════════════════════════
// PROCESS QUEUE
// ═══════════════════════════════════════════════════════════════════

/**
 * Process transmit queue (dequeue and transmit from highest priority tier)
 * 
 * Processing order (always check highest priority first):
 * 1. Tier 0 (critical commands) - timeout 1 second
 * 2. Tier 1 (important telemetry) - timeout 2 seconds
 * 3. Tier 2 (routine telemetry) - timeout 5 seconds
 * 
 * For each tier:
 * - Check if queue is empty (skip to next tier)
 * - Check if oldest packet is stale (drop and increment packets_dropped)
 * - Otherwise, transmit oldest packet and remove from queue
 * 
 * Staleness detection ensures old packets don't clog the queue.
 * For example, a 5-second-old GPS position is no longer relevant.
 * 
 * No retry logic - packets are sent once only. MAVLink handles retries
 * for commands that need acknowledgment.
 */
void AeroLoRaProtocol::processQueue() {
    unsigned long now = millis();
    
    // Phase 2: Inter-packet fairness delay
    // Minimum 10ms between transmissions
    if (now - _csma_last_tx_time < 10) {
        return;  // Too soon, wait longer
    }
    
    // After 5 consecutive TX, enforce 50ms cooldown to give other device a chance
    if (_csma_consecutive_tx >= 5 && now - _csma_last_tx_time < 50) {
        return;  // Cooldown period
    }
    
    // Reset consecutive counter if we've been idle
    if (now - _csma_last_tx_time > 100) {
        _csma_consecutive_tx = 0;
    }
    
    // Check tier0 (critical commands) - circular buffer (Requirement 4.3)
    if (!isTier0Empty()) {
        // Get packet at head position (circular buffer dequeue)
        QueuedPacket* queuedPacket = &_tier0_queue[_tier0_head];
        
        // Check staleness (1000ms = 1 second for tier0)
        // Check staleness (1000ms = 1 second for tier0)
        if (now - queuedPacket->timestamp > AEROLORA_TIER0_TIMEOUT) {
            // Drop stale packet - advance head pointer (circular - Requirement 4.3)
            // Safety check for div by zero
            if (AEROLORA_TIER0_SIZE > 0) {
                _tier0_head = (_tier0_head + 1) % AEROLORA_TIER0_SIZE;
            } else {
                _tier0_head = 0;
            }
            _stats.packets_dropped++;
            _metrics.tier0_drops_stale++;
            return;
        }
        
        // NEW: CSMA/CA before transmission
        for (uint8_t retry = 0; retry < CSMA_MAX_RETRIES; retry++) {
            _csma_retry_count = retry;  // Track retry count for exponential backoff
            
            if (isChannelClear(CSMA_LISTEN_TIME_MS)) {
                // Channel clear - build and transmit packet
                AeroLoRaPacket packet;
                packet.header = queuedPacket->relay_requested ? HEADER_WITH_RELAY : AEROLORA_HEADER;
                packet.dest_id = queuedPacket->dest_id;
                packet.payload_len = queuedPacket->len;
                memcpy(packet.payload, queuedPacket->data, queuedPacket->len);
                
                if (transmitPacket(&packet)) {
                    _tier0_head = (_tier0_head + 1) % AEROLORA_TIER0_SIZE;
                    _csma_retry_count = 0;
                    _csma_last_tx_time = millis();
                    _csma_consecutive_tx++;
                }
                return;
            }
            
            // Channel busy - backoff with exponential delay
            uint16_t backoff = calculateBackoff();
            
            #if DEBUG_LOGGING
            Serial.print("[CSMA] Tier0: Channel busy, backoff ");
            Serial.print(backoff);
            Serial.println("ms");
            #endif
            
            delay(backoff);
            _csma_backoff_count++;
            
#if DEBUG_LOGGING
            Serial.print("[CSMA] Tier0: Channel busy, backoff ");
            Serial.print(backoff);
            Serial.print("ms (retry ");
            Serial.print(retry + 1);
            Serial.print("/");
            Serial.print(CSMA_MAX_RETRIES);
            Serial.println(")");
#endif
        }
        
        // Failed after max retries - leave in queue for next iteration
        // Don't drop the packet, just try again next time
        // Failed after max retries - leave in queue for next iteration
        // Don't drop the packet, just try again next time
#if DEBUG_LOGGING
        Serial.println("[CSMA] Tier0: Max retries exceeded, deferring packet");
#endif
        return;
    }
    
    // Then check tier1 (important telemetry) - circular buffer (Requirement 4.3)
    if (!isTier1Empty()) {
        // Get packet at head position (circular buffer dequeue)
        QueuedPacket* queuedPacket = &_tier1_queue[_tier1_head];
        
        // Check staleness (2000ms = 2 seconds for tier1)
        if (now - queuedPacket->timestamp > AEROLORA_TIER1_TIMEOUT) {
            // Drop stale packet - advance head pointer (circular - Requirement 4.3)
            _tier1_head = (_tier1_head + 1) % AEROLORA_TIER1_SIZE;
            _stats.packets_dropped++;
            _metrics.tier1_drops_stale++;
            return;
        }
        
        // NEW: CSMA/CA before transmission
        for (uint8_t retry = 0; retry < CSMA_MAX_RETRIES; retry++) {
            if (isChannelClear(CSMA_LISTEN_TIME_MS)) {
                // Channel clear - build and transmit packet
                AeroLoRaPacket packet;
                packet.header = queuedPacket->relay_requested ? HEADER_WITH_RELAY : AEROLORA_HEADER;
                packet.dest_id = queuedPacket->dest_id;
                packet.payload_len = queuedPacket->len;
                memcpy(packet.payload, queuedPacket->data, queuedPacket->len);
                
                if (transmitPacket(&packet)) {
                    _tier1_head = (_tier1_head + 1) % AEROLORA_TIER1_SIZE;
                    _csma_retry_count = 0;
                    _csma_last_tx_time = millis();
                    _csma_consecutive_tx++;
                }
                return;
            }
            
            // Channel busy - backoff
            uint16_t backoff = calculateBackoff();
            delay(backoff);
            _csma_backoff_count++;
        }
        
        // Failed after max retries - leave in queue
        return;
    }
    
    // Finally check tier2 (routine telemetry) - circular buffer (Requirement 4.3)
    if (!isTier2Empty()) {
        // Get packet at head position (circular buffer dequeue)
        QueuedPacket* queuedPacket = &_tier2_queue[_tier2_head];
        
        // Check staleness (5000ms = 5 seconds for tier2)
        if (now - queuedPacket->timestamp > AEROLORA_TIER2_TIMEOUT) {
            // Drop stale packet - advance head pointer (circular - Requirement 4.3)
            _tier2_head = (_tier2_head + 1) % AEROLORA_TIER2_SIZE;
            _stats.packets_dropped++;
            _metrics.tier2_drops_stale++;
            return;
        }
        
        // NEW: CSMA/CA before transmission
        for (uint8_t retry = 0; retry < CSMA_MAX_RETRIES; retry++) {
            if (isChannelClear(CSMA_LISTEN_TIME_MS)) {
                // Channel clear - build and transmit packet
                AeroLoRaPacket packet;
                packet.header = queuedPacket->relay_requested ? HEADER_WITH_RELAY : AEROLORA_HEADER;
                packet.dest_id = queuedPacket->dest_id;
                packet.payload_len = queuedPacket->len;
                memcpy(packet.payload, queuedPacket->data, queuedPacket->len);
                
                if (transmitPacket(&packet)) {
                    _tier2_head = (_tier2_head + 1) % AEROLORA_TIER2_SIZE;
                    _csma_retry_count = 0;
                    _csma_last_tx_time = millis();
                    _csma_consecutive_tx++;
                }
                return;
            }
            
            // Channel busy - backoff
            uint16_t backoff = calculateBackoff();
            delay(backoff);
            _csma_backoff_count++;
        }
        
        // Failed after max retries - leave in queue
        return;
    }
    
    // All queues empty - reset consecutive TX counter
    _csma_consecutive_tx = 0;
}

// ═══════════════════════════════════════════════════════════════════
// MAIN PROCESS LOOP
// ═══════════════════════════════════════════════════════════════════

/**
 * Main process loop (call this in Arduino loop())
 * 
 * This method handles all protocol processing:
 * - Dequeues packets from priority queues (tier0 -> tier1 -> tier2)
 * - Drops stale packets based on tier-specific timeouts
 * - Transmits packets over radio
 * 
 * What this method does NOT do (removed for simplification):
 * - Retry processing: No retry mechanism (MAVLink handles reliability)
 * - ACK timeout checking: No ACK/NACK mechanism
 * - ACK rate calculation: Statistics simplified
 * 
 * The protocol is intentionally simple and fast. Reliability is handled
 * by MAVLink at the application layer where it belongs.
 */
void AeroLoRaProtocol::process() {
    // Process TX queue once per call
    processQueue();
}

// ═══════════════════════════════════════════════════════════════════
// MAVLINK MESSAGE ID EXTRACTION
// ═══════════════════════════════════════════════════════════════════

/**
 * Extract MAVLink message ID from packet data
 * 
 * Supports both MAVLink v1 and v2 packet formats:
 * 
 * MAVLink v1 (magic byte 0xFE):
 * [0] = 0xFE (magic)
 * [1] = payload length
 * [2] = sequence
 * [3] = system ID
 * [4] = component ID
 * [5] = message ID (8-bit)
 * 
 * MAVLink v2 (magic byte 0xFD):
 * [0] = 0xFD (magic)
 * [1] = payload length
 * [2] = incompatibility flags
 * [3] = compatibility flags
 * [4] = sequence
 * [5] = system ID
 * [6] = component ID
 * [7] = message ID low byte
 * [8] = message ID mid byte
 * [9] = message ID high byte
 * 
 * For common messages (ID < 256), we only need the low byte.
 * Most MAVLink messages we care about are in the 0-255 range.
 * 
 * @param data MAVLink packet data
 * @return Message ID (0-255 for common messages, 0xFF if invalid)
 */
uint8_t AeroLoRaProtocol::extractMavlinkMsgId(uint8_t* data) {
    // Check if we have enough data for a MAVLink header
    if (data == nullptr) {
        return 0xFF;  // Invalid message ID
    }
    
    // Check MAVLink version by magic byte
    if (data[0] == 0xFE) {
        // MAVLink v1 packet format:
        // [0] = 0xFE (magic)
        // [1] = payload length
        // [2] = sequence
        // [3] = system ID
        // [4] = component ID
        // [5] = message ID (8-bit)
        return data[5];
    } 
    else if (data[0] == 0xFD) {
        // MAVLink v2 packet format:
        // [0] = 0xFD (magic)
        // [1] = payload length
        // [2] = incompatibility flags
        // [3] = compatibility flags
        // [4] = sequence
        // [5] = system ID
        // [6] = component ID
        // [7] = message ID low byte
        // [8] = message ID mid byte
        // [9] = message ID high byte
        // 
        // For common messages (ID < 256), we only need the low byte
        // Most MAVLink messages we care about are in the 0-255 range
        return data[7];
    }
    
    // Not a valid MAVLink packet
    return 0xFF;  // Invalid message ID
}

// ═══════════════════════════════════════════════════════════════════
// PRIORITY CLASSIFICATION
// ═══════════════════════════════════════════════════════════════════

/**
 * Determine priority tier based on MAVLink message ID
 * 
 * This classification ensures critical commands are never blocked by
 * high-frequency telemetry streams. Without priority queuing, a command
 * like ARM or DISARM could get stuck behind hundreds of attitude updates,
 * creating dangerous delays.
 * 
 * Priority Classification (Requirements 5.1-5.6):
 * 
 * Tier 0 (Critical Commands ONLY - 1 second timeout):
 * - COMMAND_LONG (76): ARM, DISARM, takeoff, land, etc.
 * - SET_MODE (11): Flight mode changes (STABILIZE, LOITER, RTL, etc.)
 * - DO_SET_MODE (176): Mission command to change mode
 * - PARAM_SET (23): Parameter changes (critical for configuration)
 * - MISSION_ITEM (39): Waypoint upload (mission planning)
 * - MISSION_COUNT (44): Mission upload initiation
 * Rationale: Commands need lowest latency for responsive control
 * 
 * Tier 1 (HEARTBEAT + Important Telemetry - 2 second timeout):
 * - HEARTBEAT (0): System status, 1Hz (moved from Tier 0 per Requirement 5.1)
 * - GPS_RAW_INT (24): GPS position and fix status
 * - ATTITUDE (30): Roll, pitch, yaw orientation
 * - GLOBAL_POSITION_INT (33): Global position estimate
 * Rationale: Essential for monitoring but can tolerate slight delay.
 *            HEARTBEAT only needs 1Hz, so Tier 1's 2s timeout is sufficient.
 *            Moving HEARTBEAT frees Tier 0 for truly urgent commands.
 * 
 * Tier 2 (Routine Telemetry - 5 second timeout):
 * - Everything else (battery, status, parameters, sensor data, etc.)
 * Rationale: Nice-to-have information that can tolerate higher latency
 * 
 * @param msgId MAVLink message ID
 * @return Priority tier (0=critical, 1=important, 2=routine)
 */
int8_t AeroLoRaProtocol::getPriority(uint8_t msgId) {
    // ═══════════════════════════════════════════════════════════════════
    // TIER 0: CRITICAL COMMANDS ONLY (Requirement 5.2)
    // ═══════════════════════════════════════════════════════════════════
    // These messages require immediate action and must not be delayed.
    // They directly control vehicle behavior and safety.
    // Timeout: 1 second (dropped if not transmitted within 1s)
    //
    // Rationale: Commands need lowest latency to ensure responsive control.
    // Only true commands belong here - no telemetry, even HEARTBEAT.
    
    if (msgId == 76 ||   // COMMAND_LONG - ARM, DISARM, takeoff, land, etc.
        msgId == 11 ||   // SET_MODE - Flight mode changes (STABILIZE, LOITER, RTL, etc.)
        msgId == 176 ||  // DO_SET_MODE - Mission command to change mode
        msgId == 23 ||   // PARAM_SET - Parameter changes (critical for configuration)
        msgId == 39 ||   // MISSION_ITEM - Waypoint upload (mission planning)
        msgId == 44) {   // MISSION_COUNT - Mission upload initiation
        return 0;  // Critical commands - lowest latency
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // TIER 1: HEARTBEAT + IMPORTANT TELEMETRY (Requirements 5.1, 5.3)
    // ═══════════════════════════════════════════════════════════════════
    // HEARTBEAT moved from Tier 0 to Tier 1 (Requirement 5.1):
    // - Only needs 1Hz transmission (once per second)
    // - Tier 1's 2-second timeout is more than sufficient for 1Hz messages
    // - Frees up Tier 0 slots for truly urgent commands
    // - Prevents HEARTBEAT from blocking ARM/DISARM commands
    // - QGC connection remains stable with 1Hz HEARTBEAT in Tier 1
    //
    // Important telemetry provides core situational awareness:
    // - GPS position, vehicle attitude, global position
    // - Needed for monitoring but can tolerate slight delay
    // Timeout: 2 seconds (dropped if not transmitted within 2s)
    //
    // Rationale: These messages are essential for monitoring but not
    // time-critical like commands. Tier 1's 2s timeout is adequate.
    
    if (msgId == 0 ||    // HEARTBEAT - System status, 1Hz (moved from Tier 0)
        msgId == 24 ||   // GPS_RAW_INT - GPS position and fix status
        msgId == 30 ||   // ATTITUDE - Roll, pitch, yaw orientation
        msgId == 33) {   // GLOBAL_POSITION_INT - Global position estimate
        return 1;  // Important telemetry - moderate latency acceptable
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // TIER 2: ROUTINE TELEMETRY (Requirement 5.4)
    // ═══════════════════════════════════════════════════════════════════
    // All other messages fall into routine telemetry:
    // - Battery status, system status, extended status
    // - Parameter values, mission status, sensor data, etc.
    // - Nice-to-have information that can tolerate higher latency
    // Timeout: 5 seconds (dropped if not transmitted within 5s)
    //
    // Rationale: Routine telemetry is important but not time-sensitive.
    // Tier 2's larger queue (30 slots) and longer timeout (5s) handle
    // background traffic without impacting critical messages.
    
    return 2;  // Routine telemetry - highest latency acceptable
}

// ═══════════════════════════════════════════════════════════════════
// TIER0 CIRCULAR BUFFER HELPER METHODS (Requirements 4.1-4.7)
// ═══════════════════════════════════════════════════════════════════

/**
 * Get number of packets in tier0 circular buffer (Requirement 4.4)
 * 
 * Calculates queue count using circular buffer formula:
 * count = (tail - head + size) % size
 * 
 * This handles wraparound correctly. Examples:
 * - Empty: head=0, tail=0 → (0-0+10)%10 = 0
 * - Full: head=0, tail=9 → (9-0+10)%10 = 9
 * - Wrapped: head=8, tail=2 → (2-8+10)%10 = 4
 * 
 * @return Number of packets currently in tier0 queue (0 to AEROLORA_TIER0_SIZE-1)
 */
uint8_t AeroLoRaProtocol::getTier0Count() {
    // Safety check: prevent division by zero
    if (AEROLORA_TIER0_SIZE == 0) {
        return 0;  // Should never happen with proper macro definition
    }
    return (_tier0_tail - _tier0_head + AEROLORA_TIER0_SIZE) % AEROLORA_TIER0_SIZE;
}

/**
 * Check if tier0 circular buffer is full (Requirement 4.5)
 * 
 * A circular buffer is full when advancing the tail would make it equal to head.
 * We reserve one slot to distinguish between full and empty states.
 * 
 * Full condition: (tail + 1) % size == head
 * 
 * Examples:
 * - head=0, tail=9 → (9+1)%10 = 0 → FULL (9 packets, 1 slot reserved)
 * - head=5, tail=4 → (4+1)%10 = 5 → FULL (9 packets, wrapped around)
 * 
 * @return true if queue is full (AEROLORA_TIER0_SIZE-1 packets), false otherwise
 */
bool AeroLoRaProtocol::isTier0Full() {
    // Safety check: prevent division by zero
    if (AEROLORA_TIER0_SIZE == 0) {
        return true;  // Treat as full if size is invalid
    }
    return ((_tier0_tail + 1) % AEROLORA_TIER0_SIZE) == _tier0_head;
}

/**
 * Check if tier0 circular buffer is empty
 * 
 * A circular buffer is empty when head equals tail.
 * 
 * Empty condition: head == tail
 * 
 * @return true if queue is empty (0 packets), false otherwise
 */
bool AeroLoRaProtocol::isTier0Empty() {
    return _tier0_head == _tier0_tail;
}

// ═══════════════════════════════════════════════════════════════════
// TIER1 CIRCULAR BUFFER HELPER METHODS (Requirements 4.1-4.7)
// ═══════════════════════════════════════════════════════════════════

/**
 * Get number of packets in tier1 circular buffer (Requirement 4.4)
 * 
 * Calculates queue count using circular buffer formula:
 * count = (tail - head + size) % size
 * 
 * This handles wraparound correctly. Examples:
 * - Empty: head=0, tail=0 → (0-0+20)%20 = 0
 * - Full: head=0, tail=19 → (19-0+20)%20 = 19
 * - Wrapped: head=18, tail=2 → (2-18+20)%20 = 4
 * 
 * @return Number of packets currently in tier1 queue (0 to AEROLORA_TIER1_SIZE-1)
 */
uint8_t AeroLoRaProtocol::getTier1Count() {
    // Safety check: prevent division by zero
    if (AEROLORA_TIER1_SIZE == 0) {
        return 0;  // Should never happen with proper macro definition
    }
    return (_tier1_tail - _tier1_head + AEROLORA_TIER1_SIZE) % AEROLORA_TIER1_SIZE;
}

/**
 * Check if tier1 circular buffer is full (Requirement 4.5)
 * 
 * A circular buffer is full when advancing the tail would make it equal to head.
 * We reserve one slot to distinguish between full and empty states.
 * 
 * Full condition: (tail + 1) % size == head
 * 
 * Examples:
 * - head=0, tail=19 → (19+1)%20 = 0 → FULL (19 packets, 1 slot reserved)
 * - head=5, tail=4 → (4+1)%20 = 5 → FULL (19 packets, wrapped around)
 * 
 * @return true if queue is full (AEROLORA_TIER1_SIZE-1 packets), false otherwise
 */
bool AeroLoRaProtocol::isTier1Full() {
    // Safety check: prevent division by zero
    if (AEROLORA_TIER1_SIZE == 0) {
        return true;  // Treat as full if size is invalid
    }
    return ((_tier1_tail + 1) % AEROLORA_TIER1_SIZE) == _tier1_head;
}

/**
 * Check if tier1 circular buffer is empty
 * 
 * A circular buffer is empty when head equals tail.
 * 
 * Empty condition: head == tail
 * 
 * @return true if queue is empty (0 packets), false otherwise
 */
bool AeroLoRaProtocol::isTier1Empty() {
    return _tier1_head == _tier1_tail;
}

// ═══════════════════════════════════════════════════════════════════
// TIER2 CIRCULAR BUFFER HELPER METHODS (Requirements 4.1-4.7)
// ═══════════════════════════════════════════════════════════════════

/**
 * Get number of packets in tier2 circular buffer (Requirement 4.4)
 * 
 * Calculates queue count using circular buffer formula:
 * count = (tail - head + size) % size
 * 
 * This handles wraparound correctly. Examples:
 * - Empty: head=0, tail=0 → (0-0+30)%30 = 0
 * - Full: head=0, tail=29 → (29-0+30)%30 = 29
 * - Wrapped: head=28, tail=2 → (2-28+30)%30 = 4
 * 
 * @return Number of packets currently in tier2 queue (0 to AEROLORA_TIER2_SIZE-1)
 */
uint8_t AeroLoRaProtocol::getTier2Count() {
    // Safety check: prevent division by zero
    if (AEROLORA_TIER2_SIZE == 0) {
        return 0;  // Should never happen with proper macro definition
    }
    return (_tier2_tail - _tier2_head + AEROLORA_TIER2_SIZE) % AEROLORA_TIER2_SIZE;
}

/**
 * Check if tier2 circular buffer is full (Requirement 4.5)
 * 
 * A circular buffer is full when advancing the tail would make it equal to head.
 * We reserve one slot to distinguish between full and empty states.
 * 
 * Full condition: (tail + 1) % size == head
 * 
 * Examples:
 * - head=0, tail=29 → (29+1)%30 = 0 → FULL (29 packets, 1 slot reserved)
 * - head=5, tail=4 → (4+1)%30 = 5 → FULL (29 packets, wrapped around)
 * 
 * @return true if queue is full (AEROLORA_TIER2_SIZE-1 packets), false otherwise
 */
bool AeroLoRaProtocol::isTier2Full() {
    // Safety check: prevent division by zero
    if (AEROLORA_TIER2_SIZE == 0) {
        return true;  // Treat as full if size is invalid
    }
    return ((_tier2_tail + 1) % AEROLORA_TIER2_SIZE) == _tier2_head;
}

/**
 * Check if tier2 circular buffer is empty
 * 
 * A circular buffer is empty when head equals tail.
 * 
 * Empty condition: head == tail
 * 
 * @return true if queue is empty (0 packets), false otherwise
 */
bool AeroLoRaProtocol::isTier2Empty() {
    return _tier2_head == _tier2_tail;
}

// ═══════════════════════════════════════════════════════════════════
// STATISTICS
// ═══════════════════════════════════════════════════════════════════

AeroLoRaStats AeroLoRaProtocol::getStats() {
    // Copy base stats
    AeroLoRaStats stats = _stats;
    
    // Add CSMA/CA metrics
    stats.channel_busy_detections = _csma_channel_busy_count;
    stats.backoff_events = _csma_backoff_count;
    stats.cad_successes = _csma_cad_successes;
    stats.cad_failures = _csma_cad_failures;
    
    return stats;
}

void AeroLoRaProtocol::resetStats() {
    memset(&_stats, 0, sizeof(AeroLoRaStats));
}

uint8_t AeroLoRaProtocol::getNodeId() {
    return _my_node_id;
}

// ═══════════════════════════════════════════════════════════════════
// MESSAGE FILTERING
// ═══════════════════════════════════════════════════════════════════

/**
 * Check if a MAVLink message ID is in the blacklist
 * 
 * Performs a linear search through the AEROLORA_MESSAGE_BLACKLIST array
 * to determine if the given message ID should be filtered out.
 * 
 * Blacklisted messages are high-bandwidth sensor messages that consume
 * excessive LoRa radio bandwidth without providing critical value for
 * drone control and monitoring.
 * 
 * Performance: O(n) with n=4, so maximum 4 comparisons per message.
 * This is negligible overhead compared to radio transmission time.
 * 
 * @param msgId MAVLink message ID to check
 * @return true if message is blacklisted (should be filtered), false otherwise
 */
bool AeroLoRaProtocol::isBlacklisted(uint8_t msgId) {
    // Linear search through blacklist array
    for (uint8_t i = 0; i < AEROLORA_BLACKLIST_SIZE; i++) {
        if (msgId == AEROLORA_MESSAGE_BLACKLIST[i]) {
            return true;  // Message is blacklisted
        }
    }
    return false;  // Message is allowed
}

/**
 * Check if a message should be rate limited
 * 
 * Rate limiting prevents high-frequency messages from flooding queues
 * faster than LoRa can transmit. Without rate limiting, messages like
 * ATTITUDE (10Hz) can fill queues and cause critical commands to be dropped.
 * 
 * Rate limits (Requirements 3.1, 3.2, 3.3):
 * - ATTITUDE (30): Maximum 2 Hz (500ms minimum interval)
 * - GPS_RAW_INT (24): Maximum 2 Hz (500ms minimum interval)
 * - GLOBAL_POSITION_INT (33): Maximum 2 Hz (500ms minimum interval)
 * 
 * Implementation:
 * - Tracks last transmission time per message ID in _last_tx_time array
 * - Compares current time against last transmission + minimum interval
 * - Returns true if message arrived too soon (should be dropped)
 * 
 * @param msgId MAVLink message ID to check
 * @return true if message should be dropped due to rate limiting, false otherwise
 */
bool AeroLoRaProtocol::shouldRateLimit(uint8_t msgId) {
    uint32_t now = millis();
    uint16_t minInterval = 0;
    
    // Determine rate limit for this message ID
    switch(msgId) {
        case 30:  // ATTITUDE
            minInterval = RATE_LIMIT_ATTITUDE;
            break;
        case 24:  // GPS_RAW_INT
            minInterval = RATE_LIMIT_GPS;
            break;
        case 33:  // GLOBAL_POSITION_INT
            minInterval = RATE_LIMIT_GLOBAL_POS;
            break;
        default:
            return false;  // No rate limit for this message
    }
    
    // Check if enough time has passed since last transmission
    // Handle millis() rollover correctly (will work even after 49 days)
    uint32_t timeSinceLastTx = now - _last_tx_time[msgId];
    
    if (timeSinceLastTx < minInterval) {
        // Not enough time has passed - rate limit this message
        return true;
    }
    
    // Enough time has passed - allow transmission
    return false;
}

// ═══════════════════════════════════════════════════════════════════
// QUEUE METRICS
// ═══════════════════════════════════════════════════════════════════

/**
 * Get total queue depth across all tiers
 * 
 * Returns the sum of packets currently in all three priority queues.
 * This provides a quick overview of overall queue utilization.
 * 
 * @return Total number of packets in all queues (0-60 for default config)
 */
uint8_t AeroLoRaProtocol::getQueueDepth() {
    return getTier0Count() + getTier1Count() + getTier2Count();  // Use circular buffer counts (Requirement 4.4)
}

/**
 * Get detailed queue metrics
 * 
 * Returns a complete snapshot of queue behavior including:
 * - Current queue depth per tier
 * - Cumulative drop counts per tier (full and stale)
 * - Per-message-ID blacklist drops
 * - Per-message-ID rate limit drops
 * - Average time-in-queue
 * 
 * These metrics enable throughput analysis and optimization validation.
 * 
 * @return QueueMetrics structure with all tracked metrics
 */
QueueMetrics AeroLoRaProtocol::getQueueMetrics() {
    // Update current queue depths
    _metrics.tier0_depth = getTier0Count();  // Use circular buffer count (Requirement 4.4)
    _metrics.tier1_depth = getTier1Count();  // Use circular buffer count (Requirement 4.4)
    _metrics.tier2_depth = getTier2Count();  // Use circular buffer count (Requirement 4.4)
    
    // Return complete metrics structure
    // Drop counters and other metrics are updated as events occur
    return _metrics;
}

/**
 * Reset queue metrics counters
 * 
 * Resets all cumulative counters to zero:
 * - Per-tier drop counters (full and stale)
 * - Per-message-ID blacklist drops
 * - Per-message-ID rate limit drops
 * - Average time-in-queue
 * 
 * Does NOT affect:
 * - Current queue depth (packets remain in queues)
 * - Protocol statistics (_stats)
 * 
 * Use this to start fresh metrics collection for a new test session.
 */
void AeroLoRaProtocol::resetQueueMetrics() {
    memset(&_metrics, 0, sizeof(QueueMetrics));
}



// ═══════════════════════════════════════════════════════════════════
// CSMA/CA CHANNEL SENSING
// ═══════════════════════════════════════════════════════════════════

/**
 * Check if LoRa channel is clear for transmission
 * 
 * Uses SX1262's CAD (Channel Activity Detection) feature as primary method,
 * with RSSI threshold check as fallback. This implements the "listen before talk"
 * mechanism required for CSMA/CA.
 * 
 * @param listenTimeMs How long to listen (default 10ms)
 * @return true if channel is clear, false if busy
 */
bool AeroLoRaProtocol::isChannelClear(uint8_t listenTimeMs) {
    if (!_csma_enabled) {
        return true;  // CSMA/CA disabled, always clear
    }
    
    // Try CAD first (preferred method for LoRa)
    if (performCAD()) {
        return true;  // CAD says channel is clear
    }
    
    // Fallback to RSSI check
    return checkRSSI();
}

/**
 * Perform Channel Activity Detection using SX1262 CAD feature
 * 
 * CAD detects LoRa preambles on the channel, which is more reliable than
 * RSSI for detecting LoRa transmissions. Completes in ~5ms.
 * 
 * IMPORTANT: CAD requires radio to be in STANDBY mode, not RX mode.
 * We must stop RX, perform CAD, then restart RX.
 * 
 * @return true if channel is clear, false if activity detected
 */
bool AeroLoRaProtocol::performCAD() {
    if (_radio == nullptr) {
        return false;
    }

    // CRITICAL: Put radio in standby mode for CAD
    // scanChannel() requires standby, not RX mode
    _radio->standby();
    
    // Use SX1262 Channel Activity Detection
    int16_t result = _radio->scanChannel();
    
    // Return to RX mode immediately after CAD
    _radio->startReceive();
    
    if (result == RADIOLIB_CHANNEL_FREE) {
        // Channel is clear
        _csma_cad_successes++;
        return true;
    } else if (result == RADIOLIB_PREAMBLE_DETECTED) {
        // LoRa preamble detected (channel busy)
        _csma_cad_failures++;
        _csma_channel_busy_count++;
        
#if AEROLORA_DEBUG
        Serial.println("[CSMA] CAD: LoRa preamble detected (busy)");
#endif
        
        return false;
    } else {
        // CAD failed - fall back to RSSI
        _csma_cad_failures++;
        
#if AEROLORA_DEBUG
        Serial.print("[CSMA] CAD failed (error ");
        Serial.print(result);
        Serial.println("), falling back to RSSI");
#endif
        
        return checkRSSI();
    }
}

/**
 * Check channel using RSSI threshold (fallback method)
 * 
 * Measures RF energy on the channel. Less reliable than CAD for LoRa
 * detection (can't distinguish LoRa from noise), but works as fallback.
 * 
 * @return true if RSSI below threshold (clear), false if above (busy)
 */
bool AeroLoRaProtocol::checkRSSI() {
    float rssi = _radio->getRSSI();
    
    if (rssi < CSMA_RSSI_THRESHOLD) {
        // RSSI below threshold - channel clear
        return true;
    } else {
        // RSSI above threshold - channel busy
        _csma_channel_busy_count++;
        
#if AEROLORA_DEBUG
        Serial.print("[CSMA] RSSI: ");
        Serial.print(rssi);
        Serial.print(" dBm > threshold ");
        Serial.print(CSMA_RSSI_THRESHOLD);
        Serial.println(" dBm (busy)");
#endif
        
        return false;
    }
}

/**
 * Calculate backoff delay
 * 
 * Currently returns fixed 20ms backoff.
 * Will be upgraded to exponential backoff in Phase 2.
 * 
 * @return Backoff delay in milliseconds
 */
uint16_t AeroLoRaProtocol::calculateBackoff() {
    // Phase 2: Exponential backoff - window doubles on each retry
    uint16_t window = CSMA_MIN_BACKOFF_MS * (1 << _csma_retry_count);
    
    // Cap at maximum
    if (window > CSMA_MAX_BACKOFF_MS) {
        window = CSMA_MAX_BACKOFF_MS;
    }
    
    // Prevent underflow: if bit shift overflowed to 0, use minimum
    if (window < CSMA_MIN_BACKOFF_MS) {
        window = CSMA_MIN_BACKOFF_MS;
    }
    
    // Random value within window for better collision avoidance
    // Ensure max > min to prevent division by zero in random()
    return random(CSMA_MIN_BACKOFF_MS, window + 1);
}
