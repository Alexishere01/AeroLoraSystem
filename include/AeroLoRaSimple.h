/**
 * AeroLoRa Simple Protocol - CSMA/CA-based 3-Node Relay System
 * 
 * A simple relay protocol for drone communication using CSMA/CA (Carrier Sense
 * Multiple Access with Collision Avoidance) instead of TDMA. Designed for a
 * 3-node system: Ground Station, Drone Node, and Relay Node.
 * 
 * Key Features:
 * - Simple packet structure with explicit addressing (source, destination)
 * - CSMA/CA with priority-based backoff for collision avoidance
 * - Three-tier priority queue (critical commands, important telemetry, routine)
 * - Automatic relay forwarding for extended range
 * - No time synchronization required (self-organizing)
 * - Built on proven working code
 * 
 * Design Philosophy:
 * - Simplicity first: minimal complexity, maximum reliability
 * - Self-organizing: no configuration or synchronization needed
 * - Priority-aware: critical commands always get through first
 * - Observable: rich statistics for debugging and monitoring
 * 
 * Node Types:
 * - Ground Station (ID=0): Bridges QGroundControl to LoRa
 * - Drone Node (ID=1): Bridges flight controller to LoRa
 * - Relay Node (ID=2): Forwards packets between ground and drone
 */

#ifndef AEROLORA_SIMPLE_H
#define AEROLORA_SIMPLE_H

#include <Arduino.h>
#include <RadioLib.h>

// ═══════════════════════════════════════════════════════════════════
// PROTOCOL CONSTANTS
// ═══════════════════════════════════════════════════════════════════

// Packet structure
#define AERO_MAGIC_BYTE         0xAE    // Protocol identifier
#define AERO_MAX_PAYLOAD        250     // Maximum payload size (bytes)
#define AERO_BROADCAST          0xFF    // Broadcast address

// Node IDs
#define NODE_GROUND             0       // Ground station node
#define NODE_DRONE              1       // Drone node
#define NODE_RELAY              2       // Relay node

// Queue sizes for three-tier priority system
#define AERO_TIER0_SIZE         10      // Critical commands (ARM, DISARM, SET_MODE)
#define AERO_TIER1_SIZE         20      // Important telemetry (HEARTBEAT, GPS, ATTITUDE)
#define AERO_TIER2_SIZE         30      // Routine telemetry (everything else)

// Staleness timeouts (milliseconds) - packets older than this are dropped
#define AERO_TIER0_TIMEOUT      1000    // 1 second for critical commands
#define AERO_TIER1_TIMEOUT      2000    // 2 seconds for important telemetry
#define AERO_TIER2_TIMEOUT      5000    // 5 seconds for routine telemetry

// CSMA/CA parameters
#define CARRIER_THRESHOLD       -80     // RSSI threshold for channel clear (dBm)
#define BACKOFF_MIN_MS          2       // Minimum backoff time
#define BACKOFF_MAX_MS          10      // Maximum backoff time
#define CHANNEL_WAIT_TIMEOUT    50      // Max time to wait for channel clear (ms)
#define RELAY_FORWARD_DELAY     10      // Delay before relay forwards packet (ms)

// MAVLink message IDs for priority classification
#define MAVLINK_MSG_HEARTBEAT           0
#define MAVLINK_MSG_COMMAND_LONG        76
#define MAVLINK_MSG_SET_MODE            11
#define MAVLINK_MSG_GPS_RAW_INT         24
#define MAVLINK_MSG_ATTITUDE            30
#define MAVLINK_MSG_GLOBAL_POSITION_INT 33

// ═══════════════════════════════════════════════════════════════════
// PACKET STRUCTURE
// ═══════════════════════════════════════════════════════════════════

/**
 * Simple Packet Structure
 * 
 * Total overhead: 5 bytes (magic + src + dest + flags + length)
 * 
 * Fields:
 * - magic: 0xAE protocol identifier (for quick validation)
 * - src_id: Source node ID (who sent this packet)
 * - dest_id: Destination node ID (who should receive this packet)
 * - flags: Priority and relay status flags
 * - length: Payload length (0-250 bytes)
 * - payload: MAVLink packet data
 * 
 * Hardware CRC:
 * - The SX1262 radio automatically appends and validates CRC
 * - Invalid packets are discarded by hardware before reaching application
 */
struct __attribute__((packed)) SimplePacket {
    uint8_t magic;                          // 0xAE protocol identifier
    uint8_t src_id;                         // Source node ID
    uint8_t dest_id;                        // Destination node ID
    uint8_t flags;                          // Priority and status flags
    uint8_t length;                         // Payload length
    uint8_t payload[AERO_MAX_PAYLOAD];      // MAVLink data
};

// ═══════════════════════════════════════════════════════════════════
// STATISTICS
// ═══════════════════════════════════════════════════════════════════

/**
 * Protocol Statistics
 * 
 * Tracks communication metrics for monitoring and debugging:
 * - tx_success: Successfully transmitted packets
 * - tx_failed: Failed transmissions (channel busy, timeout)
 * - rx_packets: Successfully received packets (CRC valid)
 * - relayed: Packets forwarded by relay node
 * - avg_rssi: Rolling average signal strength
 * - avg_snr: Rolling average signal-to-noise ratio
 */
struct SimpleStats {
    uint32_t tx_success;        // Successful transmissions
    uint32_t tx_failed;         // Failed transmissions
    uint32_t rx_packets;        // Received packets
    uint32_t relayed;           // Forwarded packets (relay only)
    float avg_rssi;             // Average RSSI (dBm)
    float avg_snr;              // Average SNR (dB)
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
 * - data: MAVLink packet data
 * - len: Length of data
 * - dest: Destination node ID
 * - timestamp: Time packet was enqueued (for staleness detection)
 */
struct QueueEntry {
    uint8_t data[AERO_MAX_PAYLOAD];     // MAVLink packet data
    uint16_t len;                        // Data length
    uint8_t dest;                        // Destination node ID
    uint32_t timestamp;                  // Enqueue time (for staleness check)
};

// ═══════════════════════════════════════════════════════════════════
// AEROLORA SIMPLE PROTOCOL CLASS
// ═══════════════════════════════════════════════════════════════════

/**
 * AeroLoRa Simple Protocol Class
 * 
 * Provides a simple relay protocol with CSMA/CA for 3-node communication.
 * 
 * Key responsibilities:
 * 1. Packet framing with addressing (source, destination)
 * 2. CSMA/CA channel sensing and collision avoidance
 * 3. Priority-based queuing (critical commands before routine telemetry)
 * 4. Automatic relay forwarding for extended range
 * 5. Statistics tracking (packets sent/received/relayed, RSSI, SNR)
 * 
 * Usage:
 * 1. Initialize: AeroLoRaSimple protocol(&radio);
 * 2. Set node ID: protocol.begin(NODE_GROUND);
 * 3. Enable relay (if relay node): protocol.enableRelay(true);
 * 4. Send data: protocol.send(dest_id, data, length);
 * 5. Process queue: protocol.process(); (call in main loop)
 * 6. Receive data: len = protocol.receive(buffer, max_len);
 */
class AeroLoRaSimple {
public:
    /**
     * Constructor
     * @param radio Pointer to initialized SX1262 radio object
     */
    AeroLoRaSimple(SX1262* radio);
    
    /**
     * Initialize protocol with node identity
     * @param node_id Node ID (0=Ground, 1=Drone, 2=Relay)
     * 
     * Sets the node identity and initializes queues and statistics.
     * Call this once during setup after radio initialization.
     */
    void begin(uint8_t node_id);
    
    /**
     * Send data (enqueue to appropriate priority tier)
     * @param dest Destination node ID
     * @param data MAVLink packet data
     * @param len Length of data (max 250 bytes)
     * @return true if enqueued successfully, false if queue full
     * 
     * Priority is automatically determined by extracting the MAVLink message ID:
     * - Tier 0: Critical commands (COMMAND_LONG, SET_MODE)
     * - Tier 1: Important telemetry (HEARTBEAT, GPS_RAW_INT, ATTITUDE)
     * - Tier 2: Routine telemetry (everything else)
     */
    bool send(uint8_t dest, uint8_t* data, uint16_t len);
    
    /**
     * Send packet immediately (bypass queue)
     * @param dest Destination node ID
     * @param data Packet data
     * @param len Length of data
     * @return true if sent successfully
     * 
     * Uses CSMA/CA to wait for channel clear, applies backoff, then transmits.
     * Used internally by process() and for relay forwarding.
     */
    bool sendDirect(uint8_t dest, uint8_t* data, uint16_t len);
    
    /**
     * Receive data from radio
     * @param buffer Destination buffer
     * @param max_len Maximum bytes to copy
     * @return Number of bytes copied (0 if packet not for us)
     * 
     * Validates packet structure, checks addressing, updates statistics.
     * If relay mode enabled and packet not for us, forwards to destination.
     */
    uint16_t receive(uint8_t* buffer, uint16_t max_len);
    
    /**
     * Process transmit queue
     * 
     * Call this in main loop to dequeue and transmit packets.
     * Processes queues in priority order: Tier 0 -> Tier 1 -> Tier 2
     * Drops stale packets based on tier-specific timeouts.
     * Only processes one packet per call to avoid blocking.
     */
    void process();
    
    /**
     * Enable or disable relay mode
     * @param enable true to enable relay forwarding
     * 
     * When enabled, packets not addressed to this node are forwarded
     * to their destination. Only used by relay node.
     */
    void enableRelay(bool enable);
    
    /**
     * Get protocol statistics
     * @return Pointer to statistics structure
     */
    SimpleStats* getStats();
    
    /**
     * Get queue depth for a specific tier
     * @param tier Priority tier (0, 1, or 2)
     * @return Number of packets in queue
     */
    uint8_t getQueueDepth(uint8_t tier);
    
private:
    // Radio hardware
    SX1262* _radio;
    
    // Node identity
    uint8_t _my_node_id;
    bool _relay_enabled;
    
    // Three-tier priority queues
    QueueEntry _tier0_queue[AERO_TIER0_SIZE];   // Critical commands
    QueueEntry _tier1_queue[AERO_TIER1_SIZE];   // Important telemetry
    QueueEntry _tier2_queue[AERO_TIER2_SIZE];   // Routine telemetry
    
    uint8_t _tier0_count;       // Number of packets in tier0 queue
    uint8_t _tier1_count;       // Number of packets in tier1 queue
    uint8_t _tier2_count;       // Number of packets in tier2 queue
    
    // Statistics
    SimpleStats _stats;
    
    // Timing
    uint32_t _last_tx_time;     // Last transmission time
    uint32_t _last_rx_time;     // Last reception time
    
    // Internal methods
    
    /**
     * Check if channel is clear for transmission
     * @return true if RSSI below threshold and no recent RX
     */
    bool channelClear();
    
    /**
     * Calculate backoff time based on node ID and priority
     * @param priority Priority tier (0=critical, 1=important, 2=routine)
     * @return Backoff time in milliseconds
     */
    uint16_t getBackoffTime(uint8_t priority);
    
    /**
     * Extract MAVLink message ID from packet data
     * @param data MAVLink packet data
     * @return Message ID (supports MAVLink v1 and v2)
     */
    uint8_t extractMavlinkMsgId(uint8_t* data);
    
    /**
     * Classify MAVLink message priority
     * @param data MAVLink packet data
     * @return Priority tier (0=critical, 1=important, 2=routine)
     */
    uint8_t classifyPriority(uint8_t* data);
    
    /**
     * Shift tier0 queue left (remove first element)
     */
    void shiftTier0();
    
    /**
     * Shift tier1 queue left (remove first element)
     */
    void shiftTier1();
    
    /**
     * Shift tier2 queue left (remove first element)
     */
    void shiftTier2();
};

#endif // AEROLORA_SIMPLE_H
