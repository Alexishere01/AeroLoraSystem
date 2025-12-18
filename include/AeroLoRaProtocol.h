/**
 * AeroLoRa Protocol - Lightweight Transport Layer for MAVLink over LoRa
 * 
 * A simplified transport protocol optimized for MAVLink communication over LoRa.
 * 
 * Key Features:
 * - Hardware CRC error detection (SX1262 radio chip handles CRC automatically)
 * - Three-tier priority queue (critical commands, important telemetry, routine telemetry + params)
 * - Automatic staleness detection (drops old packets based on priority tier)
 * - Minimal overhead: Only 4 bytes per packet (header + src_id + dest_id + length)
 * - No encryption (maximum speed and range)

 * 
 * Design Philosophy:
 * - MAVLink handles reliability (command ACKs, retries) at the application layer
 * - Hardware handles error detection (CRC) at the physical layer
 * - This protocol provides lightweight framing and priority-based queuing
 * - No redundant ACK/NACK mechanism (MAVLink already does this)
 * - No sequence numbers (not needed without ACKs)
 * 
 * Packet Overhead Comparison:
 * - Previous version: 6 bytes (header + seq + flags + len + crc16)
 * - Current version: 2 bytes (header + len)
 * - Reduction: 67% less overhead
 * 
 * Priority Queue System:
 * - Tier 0 (10 slots): Critical commands ONLY (ARM, DISARM, SET_MODE, etc.) - 1s timeout
 * - Tier 1 (20 slots): HEARTBEAT + Important telemetry (GPS, ATTITUDE) - 2s timeout
 * - Tier 2 (30 slots): Routine telemetry (everything else) - 5s timeout
 * - Always dequeues from highest priority tier first
 * - Automatically drops stale packets that exceed timeout
 * - HEARTBEAT moved to Tier 1 (only needs 1Hz, frees Tier 0 for urgent commands)
 * 
 * Hardware CRC Operation:
 * - On TX: Radio automatically calculates and appends CRC to transmitted packet
 * - On RX: Radio automatically validates CRC and discards invalid packets
 * - Application layer never sees packets with bad CRC
 * - Enabled via radio.setCRC(true) during initialization
 */

#ifndef AEROLORA_PROTOCOL_H
#define AEROLORA_PROTOCOL_H

#include <Arduino.h>
#include <RadioLib.h>

// ═══════════════════════════════════════════════════════════════════
// PROTOCOL CONSTANTS
// ═══════════════════════════════════════════════════════════════════

#define AEROLORA_HEADER         0xAE    // Packet marker (identifies AeroLoRa packets)
#define AEROLORA_MAX_PAYLOAD    250     // Max payload size (MAVLink packet data)

// Relay request flag (bit 7 of header byte)
// When set, indicates sender is requesting relay assistance due to weak link
#define RELAY_REQUEST_FLAG      0x80    // Bit 7: Relay request flag
#define HEADER_WITH_RELAY       (AEROLORA_HEADER | RELAY_REQUEST_FLAG)  // 0xAE | 0x80 = 0x2E

// Node ID constants for addressing
#define NODE_GROUND             0       // Ground station node ID
#define NODE_DRONE              1       // Drone node ID
#define AERO_BROADCAST          0xFF    // Broadcast address (all nodes)

// Queue sizes for three-tier priority system
// Tier 0: Critical commands ONLY (ARM, DISARM, SET_MODE, etc.)
// Tier 1: HEARTBEAT + Important telemetry (GPS, ATTITUDE)
// Tier 2: Routine telemetry (everything else)
// Total: 10 + 20 + 30 = 60 slots × 256 bytes = 15,360 bytes (under 20KB limit)
#define AEROLORA_TIER0_SIZE      10     // Critical commands ONLY (ARM, DISARM, SET_MODE, etc.)
#define AEROLORA_TIER1_SIZE      20     // HEARTBEAT + Important telemetry (GPS, ATTITUDE)
#define AEROLORA_TIER2_SIZE      30     // Routine telemetry (everything else)

// Staleness timeouts (milliseconds) - packets older than this are dropped
#define AEROLORA_TIER0_TIMEOUT      1000 // 1 second for critical commands
#define AEROLORA_TIER1_TIMEOUT      2000 // 2 seconds for important telemetry
#define AEROLORA_TIER2_TIMEOUT      5000 // 5 seconds for routine telemetry

// Rate limiting (milliseconds) - minimum time between transmissions per message ID
// Prevents high-frequency messages from flooding queues faster than LoRa can transmit
#define RATE_LIMIT_ATTITUDE         500  // 2 Hz for ATTITUDE (ID 30)
#define RATE_LIMIT_GPS              500  // 2 Hz for GPS_RAW_INT (ID 24)
#define RATE_LIMIT_GLOBAL_POS       333  // 3 Hz for GLOBAL_POSITION_INT (ID 33)

// ═══════════════════════════════════════════════════════════════════
// COMPILE-TIME CONFIGURATION VALIDATION
// ═══════════════════════════════════════════════════════════════════

// Validate total queue memory usage is under 20KB
// Each QueuedPacket is approximately 256 bytes (250 payload + 6 overhead)
// Total queue memory = (tier0 + tier1 + tier2) * sizeof(QueuedPacket)
static_assert((AEROLORA_TIER0_SIZE + AEROLORA_TIER1_SIZE + AEROLORA_TIER2_SIZE) * 256 < 20480,
    "ERROR: Total queue memory usage exceeds 20KB limit. "
    "Current configuration will consume too much RAM on ESP32. "
    "Reduce queue sizes: AEROLORA_TIER0_SIZE, AEROLORA_TIER1_SIZE, or AEROLORA_TIER2_SIZE.");

// Validate timeout values are in ascending order
// Shorter timeouts for higher priority tiers ensure critical messages don't linger
// Expected order: tier0 < tier1 < tier2
static_assert(AEROLORA_TIER0_TIMEOUT <= AEROLORA_TIER1_TIMEOUT,
    "ERROR: Timeout configuration invalid. "
    "AEROLORA_TIER0_TIMEOUT must be <= AEROLORA_TIER1_TIMEOUT. "
    "Critical commands (tier0) should timeout before or equal to important telemetry (tier1).");

static_assert(AEROLORA_TIER1_TIMEOUT <= AEROLORA_TIER2_TIMEOUT,
    "ERROR: Timeout configuration invalid. "
    "AEROLORA_TIER1_TIMEOUT must be <= AEROLORA_TIER2_TIMEOUT. "
    "Important telemetry (tier1) should timeout before or equal to routine telemetry (tier2).");

// Legacy constants removed:
// - AEROLORA_MAX_RETRIES: No retry mechanism (MAVLink handles reliability)
// - AEROLORA_ACK_TIMEOUT_MS: No ACK/NACK mechanism
// - AEROLORA_QUEUE_SIZE: Replaced with tier-specific sizes
// - Packet flags: No longer needed (hardware CRC, no ACK/NACK)

// MAVLink message blacklist - messages that should never be transmitted over LoRa
// These are extremely high-bandwidth sensor messages that provide minimal value
// for basic drone control and monitoring over long-range LoRa links.
// Keep this list MINIMAL - only block truly unnecessary messages.
#define AEROLORA_BLACKLIST_SIZE 7

const uint8_t AEROLORA_MESSAGE_BLACKLIST[AEROLORA_BLACKLIST_SIZE] = {
    88,   // HIL_OPTICAL_FLOW - Hardware-in-the-loop optical flow (simulation only)
    100,  // OPTICAL_FLOW - Optical flow sensor data (high frequency, not critical)
    106,  // HIL_SENSOR - Hardware-in-the-loop sensor data (simulation only)
    27,   // RAW_IMU - Very high frequency IMU data (use ATTITUDE instead)
    129,  // SCALED_IMU3 - Tertiary IMU (rarely used)
    132,  // Unknown message - observed at 6.2 Hz (too fast)
    241   // DISTANCE_SENSOR - High frequency distance measurements (not critical)
};

// ═══════════════════════════════════════════════════════════════════
// PACKET STRUCTURE
// ═══════════════════════════════════════════════════════════════════

/**
 * AeroLoRa Packet Structure (With Addressing)
 * 
 * Total overhead: 4 bytes (header + src_id + dest_id + payload_len)
 * 
 * Fields:
 * - header: 0xAE packet marker (identifies AeroLoRa packets)
 * - src_id: Source node ID (who sent this packet)
 * - dest_id: Destination node ID (who should receive this packet)
 * - payload_len: Length of payload data (0-250 bytes)
 * - payload: MAVLink packet data
 * 
 * Addressing:
 * - src_id identifies the sender (NODE_GROUND=0, NODE_DRONE=1, etc.)
 * - dest_id identifies the recipient (or AERO_BROADCAST=0xFF for all nodes)
 * - Nodes filter packets based on dest_id (only process if dest_id matches or is broadcast)
 * 
 * Hardware CRC:
 * - The SX1262 radio automatically appends a 2-byte CRC after the payload
 * - On transmission: CRC is calculated and appended by radio hardware
 * - On reception: CRC is validated by radio hardware before interrupt
 * - Invalid packets are silently discarded by the radio (never reach application)
 * 
 * Priority handling:
 * - Priority is determined by MAVLink message ID (extracted from payload)
 * - Priority is managed at queue level, not transmitted in packet
 * - This keeps packet structure minimal and efficient
 */
struct __attribute__((packed)) AeroLoRaPacket {
    uint8_t  header;        // 0xAE packet marker
    uint8_t  src_id;        // Source node ID
    uint8_t  dest_id;       // Destination node ID
    uint8_t  payload_len;   // Payload length (0-250 bytes)
    uint8_t  payload[AEROLORA_MAX_PAYLOAD];  // MAVLink packet data
};

// ═══════════════════════════════════════════════════════════════════
// STATISTICS
// ═══════════════════════════════════════════════════════════════════

/**
 * Protocol Statistics (Simplified)
 * 
 * Tracks basic communication metrics:
 * - packets_sent: Successfully transmitted packets
 * - packets_received: Successfully received packets (hardware CRC already validated)
 * - packets_dropped: Packets dropped due to queue overflow or staleness timeout
 * - packets_ignored: Packets received but not for us (not relayed)
 * - avg_rssi: Average Received Signal Strength Indicator
 * - avg_snr: Average Signal-to-Noise Ratio
 * 
 * Removed statistics (no longer applicable):
 * - packets_acked: No ACK mechanism
 * - packets_nacked: No NACK mechanism
 * - retries: No retry mechanism (MAVLink handles this)
 * - ack_rate: No ACK mechanism to calculate rate
 * 
 * Note on CRC errors:
 * - Hardware CRC errors are NOT counted in packets_dropped
 * - Invalid packets are silently discarded by the radio before reaching application
 * - Only queue overflows and staleness timeouts increment packets_dropped
 * 
 * Note on packets_ignored:
 * - Counts packets received with dest_id != our node ID and != AERO_BROADCAST
 * - These packets are for other nodes in a multi-node network
 * - Future relay functionality will forward these via UART to external relay
 */
struct AeroLoRaStats {
    uint32_t packets_sent;      // Successfully transmitted packets
    uint32_t packets_received;  // Successfully received packets (CRC valid)
    uint32_t packets_dropped;   // Dropped due to queue full or staleness
    uint32_t packets_ignored;   // Received but not for us (not relayed)
    float    avg_rssi;          // Average signal strength
    float    avg_snr;           // Average signal-to-noise ratio
    
    // Phase 2: CSMA/CA metrics
    uint32_t channel_busy_detections;  // Times channel was detected busy
    uint32_t backoff_events;           // Times we backed off
    uint32_t cad_successes;            // Successful CAD detections (channel clear)
    uint32_t cad_failures;             // Failed CAD attempts
};

// ═══════════════════════════════════════════════════════════════════
// QUEUE METRICS
// ═══════════════════════════════════════════════════════════════════

/**
 * Queue Metrics Structure
 * 
 * Tracks detailed queue behavior for throughput analysis and optimization.
 * 
 * Per-tier metrics:
 * - Queue depth: Current number of packets in each tier
 * - Drops (full): Packets rejected because queue was full
 * - Drops (stale): Packets dropped because they exceeded timeout
 * 
 * Per-message-ID metrics:
 * - Blacklist drops: Count of drops per message type due to blacklist
 * - Rate limit drops: Count of drops per message type due to rate limiting
 * 
 * Time-in-queue tracking:
 * - Average time packets spend in queue before transmission
 * 
 * These metrics enable:
 * - Identifying throughput bottlenecks
 * - Measuring queue utilization
 * - Analyzing drop patterns
 * - Validating optimization effectiveness
 */
struct QueueMetrics {
    // Per-tier queue depth (current number of packets)
    uint8_t tier0_depth;
    uint8_t tier1_depth;
    uint8_t tier2_depth;
    
    // Per-tier drops due to queue full (cumulative)
    uint32_t tier0_drops_full;
    uint32_t tier1_drops_full;
    uint32_t tier2_drops_full;
    
    // Per-tier drops due to staleness (cumulative)
    uint32_t tier0_drops_stale;
    uint32_t tier1_drops_stale;
    uint32_t tier2_drops_stale;
    
    // Per-message-ID blacklist drops (cumulative)
    uint32_t blacklist_drops[256];
    
    // Per-message-ID rate limit drops (cumulative)
    uint32_t rate_limit_drops[256];
    
    // Time-in-queue tracking (rolling average in milliseconds)
    uint32_t avg_time_in_queue_ms;
};

// ═══════════════════════════════════════════════════════════════════
// QUEUED PACKET
// ═══════════════════════════════════════════════════════════════════

/**
 * Queued Packet Structure
 * 
 * Represents a packet waiting in one of the three priority queues.
 * 
 * Fields:
 * - data: MAVLink packet data (up to 250 bytes)
 * - len: Length of data
 * - dest_id: Destination node ID
 * - priority: Priority tier (0=critical, 1=important, 2=routine)
 * - timestamp: Time packet was enqueued (for staleness detection)
 * - relay_requested: If true, set RELAY_REQUEST_FLAG in header when transmitting
 * 
 * Priority tiers:
 * - 0 (Critical): Commands like ARM, DISARM, SET_MODE - must go immediately
 * - 1 (Important): Telemetry like HEARTBEAT, GPS, ATTITUDE - needed for awareness
 * - 2 (Routine): All other telemetry - background traffic
 * 
 * Staleness detection:
 * - Tier 0: Dropped if older than 1 second
 * - Tier 1: Dropped if older than 2 seconds
 * - Tier 2: Dropped if older than 5 seconds
 * 
 * Parameter rate limiting:
 * - PARAM_VALUE messages in Tier 2 are rate limited to 2 per second
 * 
 * Removed fields (no longer needed):
 * - retries: No retry mechanism (MAVLink handles reliability)
 * - waiting_ack: No ACK/NACK mechanism
 */
struct QueuedPacket {
    uint8_t  data[AEROLORA_MAX_PAYLOAD];  // MAVLink packet data
    uint8_t  len;                          // Data length
    uint8_t  dest_id;                      // Destination node ID
    uint8_t  priority;                     // 0=critical, 1=important, 2=routine
    uint32_t timestamp;                    // Enqueue time (for staleness check)
    bool     relay_requested;              // If true, set RELAY_REQUEST_FLAG in header
};

// ═══════════════════════════════════════════════════════════════════
// AEROLORA PROTOCOL CLASS
// ═══════════════════════════════════════════════════════════════════

/**
 * AeroLoRa Protocol Class
 * 
 * Provides a lightweight transport layer for MAVLink communication over LoRa.
 * 
 * Key responsibilities:
 * 1. Packet framing (add header and length to MAVLink packets)
 * 2. Priority-based queuing (critical commands before routine telemetry)
 * 3. Staleness detection (drop old packets that are no longer relevant)
 * 4. Statistics tracking (packets sent/received/dropped, RSSI, SNR)
 * 
 * What this protocol does NOT do:
 * - Reliability (ACK/NACK): MAVLink handles this at application layer
 * - Error detection (CRC): SX1262 hardware handles this at physical layer
 * - Retries: MAVLink handles this for commands that need acknowledgment
 * - Encryption: Not implemented (prioritizes speed and range)
 * 
 * Usage:
 * 1. Initialize: AeroLoRaProtocol protocol(&radio, slot_offset, slot_duration);
 * 2. Enable hardware CRC: radio.setCRC(true);
 * 3. Send data: protocol.send(mavlink_data, length);
 * 4. Process queue: protocol.process(); (call in main loop)
 * 5. Check for received data: if (protocol.available()) { ... }
 * 6. Receive data: protocol.receive(buffer, max_len);
 */
class AeroLoRaProtocol {
public:
    /**
     * Constructor
     * @param radio Pointer to initialized SX1262 radio object
     * @param slot_offset TDMA slot offset (for future use)
     * @param slot_duration TDMA slot duration in ms (for future use)
     */
    AeroLoRaProtocol(SX1262* radio, uint8_t slot_offset, uint16_t slot_duration);
    
    /**
     * Initialize protocol with node identity
     * @param node_id Unique node identifier (NODE_GROUND=0, NODE_DRONE=1, etc.)
     * @return true if successful
     * Note: Radio should already be initialized before calling this
     */
    bool begin(uint8_t node_id);
    
    /**
     * Send data (enqueue to appropriate priority tier)
     * @param dest_id Destination node ID (default AERO_BROADCAST for backward compatibility)
     * @param data MAVLink packet data
     * @param len Length of data (max 250 bytes)
     * @param priority Legacy parameter (ignored - priority determined from MAVLink message ID)
     * @return true if enqueued successfully, false if queue full
     * 
     * Priority is automatically determined by extracting the MAVLink message ID:
     * - Tier 0: Critical commands (COMMAND_LONG, SET_MODE, etc.)
     * - Tier 1: Important telemetry (HEARTBEAT, GPS_RAW_INT, ATTITUDE)
     * - Tier 2: Routine telemetry (everything else)
     */
    bool send(uint8_t* data, uint8_t len, bool priority = false, uint8_t dest_id = AERO_BROADCAST);
    
    /**
     * Send data with relay request flag
     * @param data MAVLink packet data
     * @param len Length of data (max 250 bytes)
     * @param requestRelay If true, set relay request flag in header
     * @param dest_id Destination node ID (default AERO_BROADCAST)
     * @return true if enqueued successfully, false if queue full
     * 
     * When requestRelay is true, the RELAY_REQUEST_FLAG bit is set in the packet header,
     * signaling to relay-capable nodes that this sender needs relay assistance.
     */
    bool sendWithRelayFlag(uint8_t* data, uint8_t len, bool requestRelay, uint8_t dest_id = AERO_BROADCAST);
    
    /**
     * Send immediate (legacy method, no longer bypasses queue)
     * @param data Packet data
     * @param len Length of data
     * @param dest_id Destination node ID (default AERO_BROADCAST)
     * @return true if sent successfully
     * Note: This method is deprecated and will be removed in future versions
     */
    bool sendImmediate(uint8_t* data, uint8_t len, uint8_t dest_id = AERO_BROADCAST);
    
    /**
     * Check if received data is available
     * @return true if data ready to read
     */
    bool available();
    
    /**
     * Receive data from RX buffer
     * @param buffer Destination buffer
     * @param max_len Maximum bytes to copy
     * @return Number of bytes copied
     */
    uint8_t receive(uint8_t* buffer, uint8_t max_len);
    
    /**
     * Process queue and handle transmission
     * Call this in main loop to dequeue and transmit packets
     * 
     * Processing order:
     * 1. Check tier 0 (critical commands) - transmit if not stale
     * 2. Check tier 1 (important telemetry) - transmit if not stale
     * 3. Check tier 2 (routine telemetry) - transmit if not stale
     * 
     * Staleness timeouts:
     * - Tier 0: 1 second
     * - Tier 1: 2 seconds
     * - Tier 2: 5 seconds
     */
    void process();
    
    /**
     * Get protocol statistics
     * @return Statistics structure with packet counts and signal metrics
     */
    AeroLoRaStats getStats();
    
    /**
     * Reset statistics counters
     */
    void resetStats();
    
    /**
     * Get total queue depth across all tiers
     * @return Total number of packets currently in all queues
     */
    uint8_t getQueueDepth();
    
    /**
     * Get detailed queue metrics
     * @return QueueMetrics structure with per-tier statistics
     */
    QueueMetrics getQueueMetrics();
    
    /**
     * Reset queue metrics counters
     * Resets all drop counters and time-in-queue tracking
     * Does not affect current queue depth
     */
    void resetQueueMetrics();
    
    /**
     * Get node ID
     * @return Current node identifier
     */
    uint8_t getNodeId();
    
    /**
     * Check if current time is in our TDMA transmit slot
     * @return true if we can transmit (currently always true for testing)
     */
    bool isMyTxSlot();
    
    /**
     * Get time until next transmit slot
     * @return Milliseconds until next slot (currently always 0 for testing)
     */
    unsigned long getNextTxSlot();
    
    /**
     * Handle received packet (called from radio interrupt handler)
     * @param packet Pointer to received packet
     * 
     * Note: If this method is called, hardware CRC has already been validated.
     * The radio only triggers interrupts for packets with valid CRC.
     */
    void handleReceivedPacket(AeroLoRaPacket* packet);
    

    
private:
    // Radio hardware
    SX1262* _radio;
    
    // Node identity
    uint8_t _my_node_id;
    
    // TDMA configuration (for future use)
    uint8_t _slot_offset;
    uint16_t _slot_duration;
    
    // CSMA/CA configuration
    // Converted to #defines to prevent static const linking issues
    // static const int8_t CSMA_RSSI_THRESHOLD = -90;  // dBm threshold for "busy"
    // static const uint8_t CSMA_LISTEN_TIME_MS = 10;   // Listen period before declaring clear
    // static const uint8_t CSMA_MAX_RETRIES = 3;       // Max channel sense attempts
    // static const uint16_t CSMA_MIN_BACKOFF_MS = 5;   // Minimum backoff delay
    // static const uint16_t CSMA_MAX_BACKOFF_MS = 100; // Maximum backoff delay
    
    #define CSMA_RSSI_THRESHOLD -90
    #define CSMA_LISTEN_TIME_MS 10
    #define CSMA_MAX_RETRIES 3
    #define CSMA_MIN_BACKOFF_MS 5
    #define CSMA_MAX_BACKOFF_MS 100
    
    // CSMA/CA state
    bool _csma_enabled;
    uint8_t _csma_retry_count;
    uint16_t _csma_backoff_window;
    unsigned long _csma_last_tx_time;
    uint8_t _csma_consecutive_tx;
    
    // CSMA/CA statistics
    uint32_t _csma_channel_busy_count;
    uint32_t _csma_backoff_count;
    uint32_t _csma_cad_successes;
    uint32_t _csma_cad_failures;
    
    // Three-tier priority queues
    // Tier 0: Critical commands ONLY (ARM, DISARM, SET_MODE, etc.)
    // Tier 1: HEARTBEAT + Important telemetry (GPS, ATTITUDE)
    // Tier 2: Routine telemetry (everything else)
    QueuedPacket _tier0_queue[AEROLORA_TIER0_SIZE];   // Critical commands ONLY
    QueuedPacket _tier1_queue[AEROLORA_TIER1_SIZE];   // HEARTBEAT + Important telemetry
    QueuedPacket _tier2_queue[AEROLORA_TIER2_SIZE];   // Routine telemetry
    
    // Circular buffer pointers for tier0 (Requirements 4.1, 4.2, 4.3)
    uint8_t _tier0_head;  // Index of first packet (dequeue position)
    uint8_t _tier0_tail;  // Index of next free slot (enqueue position)
    
    // Circular buffer pointers for tier1 (Requirements 4.1, 4.2, 4.3)
    uint8_t _tier1_head;  // Index of first packet (dequeue position)
    uint8_t _tier1_tail;  // Index of next free slot (enqueue position)
    
    // Circular buffer pointers for tier2 (Requirements 4.1, 4.2, 4.3)
    uint8_t _tier2_head;  // Index of first packet (dequeue position)
    uint8_t _tier2_tail;  // Index of next free slot (enqueue position)
    
    // Receive buffer
    uint8_t _rx_buffer[AEROLORA_MAX_PAYLOAD];
    uint8_t _rx_len;
    bool _rx_ready;
    
    // Statistics
    AeroLoRaStats _stats;
    
    // Queue metrics
    QueueMetrics _metrics;
    
    // Rate limiting - track last transmission time per message ID
    uint32_t _last_tx_time[256];  // One per MAVLink message ID
    
    // Timing
    unsigned long _last_tx;
    
    // Internal methods
    
    /**
     * Transmit packet over radio
     * @param packet Pointer to packet to transmit
     * @return true if transmitted successfully
     * 
     * Hardware CRC is automatically appended by the radio during transmission.
     */
    bool transmitPacket(AeroLoRaPacket* packet);
    
    /**
     * Process transmit queue (dequeue and transmit from highest priority tier)
     * Checks tier0 first, then tier1, then tier2.
     * Drops stale packets based on tier-specific timeouts.
     * Applies rate limiting to PARAM_VALUE messages in tier2.
     */
    void processQueue();
    
    /**
     * Extract MAVLink message ID from packet data
     * @param data MAVLink packet data
     * @return Message ID (0-255 for common messages, 0xFF if invalid)
     * 
     * Supports both MAVLink v1 (0xFE) and v2 (0xFD) packet formats.
     */
    uint8_t extractMavlinkMsgId(uint8_t* data);
    
    /**
     * Determine priority tier based on MAVLink message ID
     * @param msgId MAVLink message ID
     * @return Priority tier (0=critical, 1=important, 2=routine)
     * 
     * Priority Classification (Requirements 5.1-5.6):
     * 
     * Tier 0 (Critical Commands ONLY - 1s timeout):
     * - COMMAND_LONG (76): ARM, DISARM, takeoff, land, etc.
     * - SET_MODE (11): Flight mode changes
     * - DO_SET_MODE (176): Mission command to change mode
     * - PARAM_SET (23): Parameter changes
     * - MISSION_ITEM (39): Waypoint upload
     * - MISSION_COUNT (44): Mission upload initiation
     * Rationale: Commands need lowest latency for responsive control
     * 
     * Tier 1 (HEARTBEAT + Important Telemetry - 2s timeout):
     * - HEARTBEAT (0): System status, 1Hz (moved from Tier 0)
     * - GPS_RAW_INT (24): GPS position and fix status
     * - ATTITUDE (30): Roll, pitch, yaw orientation
     * - GLOBAL_POSITION_INT (33): Global position estimate
     * Rationale: Essential for monitoring but can tolerate slight delay
     * 
     * Tier 2 (Routine Telemetry - 5s timeout):
     * - Everything else (battery, status, parameters, sensor data, etc.)
     * Rationale: Nice-to-have information that can tolerate higher latency
     */
    int8_t getPriority(uint8_t msgId);
    
    /**
     * Get number of packets in tier0 circular buffer (Requirement 4.4)
     * @return Number of packets currently in tier0 queue
     */
    uint8_t getTier0Count();
    
    /**
     * Check if tier0 circular buffer is full (Requirement 4.5)
     * @return true if queue is full, false otherwise
     */
    bool isTier0Full();
    
    /**
     * Check if tier0 circular buffer is empty
     * @return true if queue is empty, false otherwise
     */
    bool isTier0Empty();
    
    /**
     * Get number of packets in tier1 circular buffer (Requirement 4.4)
     * @return Number of packets currently in tier1 queue
     */
    uint8_t getTier1Count();
    
    /**
     * Check if tier1 circular buffer is full (Requirement 4.5)
     * @return true if queue is full, false otherwise
     */
    bool isTier1Full();
    
    /**
     * Check if tier1 circular buffer is empty
     * @return true if queue is empty, false otherwise
     */
    bool isTier1Empty();
    
    /**
     * Get number of packets in tier2 circular buffer (Requirement 4.4)
     * @return Number of packets currently in tier2 queue
     */
    uint8_t getTier2Count();
    
    /**
     * Check if tier2 circular buffer is full (Requirement 4.5)
     * @return true if queue is full, false otherwise
     */
    bool isTier2Full();
    
    /**
     * Check if tier2 circular buffer is empty
     * @return true if queue is empty, false otherwise
     */
    bool isTier2Empty();
    
    /**
     * Check if a MAVLink message ID is in the blacklist
     * @param msgId MAVLink message ID to check
     * @return true if message is blacklisted, false otherwise
     */
    bool isBlacklisted(uint8_t msgId);
    
    /**
     * Check if a message should be rate limited
     * @param msgId MAVLink message ID to check
     * @return true if message should be dropped due to rate limiting, false otherwise
     * 
     * Rate limits high-frequency messages to prevent queue flooding:
     * - ATTITUDE (30): 2 Hz maximum
     * - GPS_RAW_INT (24): 2 Hz maximum
     * - GLOBAL_POSITION_INT (33): 2 Hz maximum
     */
    bool shouldRateLimit(uint8_t msgId);
    
    /**
     * Check if LoRa channel is clear for transmission (CSMA/CA)
     * @param listenTimeMs How long to listen (default 10ms)
     * @return true if channel is clear, false if busy
     * 
     * Uses CAD (Channel Activity Detection) if available, falls back to RSSI.
     */
    bool isChannelClear(uint8_t listenTimeMs = CSMA_LISTEN_TIME_MS);
    
    /**
     * Perform Channel Activity Detection using SX1262 CAD feature
     * @return true if channel is clear, false if activity detected
     */
    bool performCAD();
    
    /**
     * Check channel using RSSI threshold (fallback method)
     * @return true if RSSI below threshold (clear), false if above (busy)
     */
    bool checkRSSI();
    
    /**
     * Calculate backoff delay (currently fixed, will be exponential in Phase 2)
     * @return Backoff delay in milliseconds
     */
    uint16_t calculateBackoff();
};

#endif // AEROLORA_PROTOCOL_H
