#ifndef DUAL_BAND_TRANSPORT_H
#define DUAL_BAND_TRANSPORT_H

#include <Arduino.h>
#include "ESPNowTransport.h"
#include "AeroLoRaProtocol.h"
#include "MessageFilter.h"
#include "flight_logger.h"

/**
 * @brief Dual-Band Transport Statistics
 * 
 * Aggregates statistics from both ESP-NOW and LoRa transports
 */
struct DualBandStats {
    // ESP-NOW statistics
    uint32_t espnow_packets_sent;
    uint32_t espnow_packets_received;
    uint32_t espnow_send_failures;
    uint32_t espnow_peer_unreachable_count;
    int8_t   espnow_last_rssi;
    bool     espnow_peer_reachable;
    
    // LoRa statistics
    uint32_t lora_packets_sent;
    uint32_t lora_packets_received;
    uint32_t lora_filtered_messages;  // Non-essential dropped
    float    lora_avg_rssi;
    
    // Deduplication statistics
    uint32_t duplicate_packets_dropped;
    
    // Link transition events
    uint32_t espnow_to_lora_transitions;
    uint32_t lora_to_espnow_transitions;
    uint32_t last_transition_timestamp;
};

/**
 * @brief Dual-Band Transport Manager
 * 
 * Coordinates ESP-NOW and LoRa transports, handling:
 * - Message routing (all messages over ESP-NOW, essential only over LoRa)
 * - Deduplication (based on MAVLink sequence numbers)
 * - Link status monitoring
 * - Statistics aggregation
 */
class DualBandTransport {
private:
    ESPNowTransport* _espnow;
    AeroLoRaProtocol* _lora;
    MessageFilter _filter;
    FlightLogger* _logger;  // Optional flight logger
    
    // Deduplication tracking (per system ID)
    uint8_t _last_seq_num[256];
    
    // Statistics
    DualBandStats _stats;
    
    // Node identity
    uint8_t _my_node_id;
    
    // Link state tracking
    bool _last_espnow_state;  // Track ESP-NOW state for transition detection
    unsigned long _last_stats_log_time;  // For periodic statistics logging
    
    /**
     * @brief Extract MAVLink message ID from packet data
     * @param data MAVLink packet data
     * @param len Length of data
     * @return Message ID (0-255), or 0xFF if invalid
     */
    uint8_t extractMavlinkMsgId(uint8_t* data, uint8_t len);
    
    /**
     * @brief Extract MAVLink system ID from packet data
     * @param data MAVLink packet data
     * @param len Length of data
     * @return System ID (0-255), or 0xFF if invalid
     */
    uint8_t extractMavlinkSysId(uint8_t* data, uint8_t len);
    
    /**
     * @brief Extract MAVLink sequence number from packet data
     * @param data MAVLink packet data
     * @param len Length of data
     * @return Sequence number (0-255), or 0xFF if invalid
     */
    uint8_t extractMavlinkSeqNum(uint8_t* data, uint8_t len);
    
    /**
     * @brief Check if packet is a duplicate based on sequence number
     * @param sysId System ID of sender
     * @param seqNum Sequence number of packet
     * @return true if duplicate, false if new packet
     */
    bool isDuplicate(uint8_t sysId, uint8_t seqNum);
    
public:
    /**
     * @brief Constructor
     * @param espnow Pointer to initialized ESPNowTransport
     * @param lora Pointer to initialized AeroLoRaProtocol
     * @param logger Optional pointer to FlightLogger for logging dual-band metrics
     */
    DualBandTransport(ESPNowTransport* espnow, AeroLoRaProtocol* lora, FlightLogger* logger = nullptr);
    
    /**
     * @brief Initialize dual-band transport
     * @param node_id Node identifier (NODE_GROUND, NODE_DRONE, etc.)
     * @return true if successful
     */
    bool begin(uint8_t node_id);
    
    /**
     * @brief Send packet via appropriate transport(s)
     * 
     * Routing logic:
     * - If ESP-NOW available: Send all messages over ESP-NOW
     * - If message is essential: Also send over LoRa
     * - If message is non-essential: Filter from LoRa
     * 
     * @param data MAVLink packet data
     * @param len Length of data
     * @param dest_id Destination node ID
     * @return true if sent successfully on at least one transport
     */
    bool send(uint8_t* data, uint8_t len, uint8_t dest_id);
    
    /**
     * @brief Receive packet (deduplicated)
     * 
     * Checks both transports for received packets and deduplicates
     * based on MAVLink sequence numbers.
     * 
     * @param buffer Destination buffer
     * @param max_len Maximum bytes to copy
     * @return Number of bytes received (0 if no data)
     */
    uint8_t receive(uint8_t* buffer, uint8_t max_len);
    
    /**
     * @brief Check if ESP-NOW link is available
     * @return true if ESP-NOW peer is reachable
     */
    bool isESPNowAvailable();
    
    /**
     * @brief Check if LoRa link is available
     * @return true if LoRa is operational
     */
    bool isLoRaAvailable();
    
    /**
     * @brief Get aggregated statistics from both transports
     * @return DualBandStats structure
     */
    DualBandStats getStats();
    
    /**
     * @brief Reset statistics counters
     */
    void resetStats();
    
    /**
     * @brief Process both transports (call in main loop)
     * 
     * Handles:
     * - ESP-NOW packet processing
     * - LoRa queue processing
     * - Link state transition detection
     * - Periodic statistics logging
     */
    void process();
    
    /**
     * @brief Set flight logger for dual-band metrics
     * @param logger Pointer to FlightLogger instance
     * 
     * Enables logging of:
     * - ESP-NOW link transitions (in-range/out-of-range)
     * - Message filter statistics (filtered count per message ID)
     * - Deduplication statistics
     * - Link status for both transports
     * 
     * Requirements: 5.3, 5.4, 5.5
     */
    void setLogger(FlightLogger* logger);
    
    /**
     * @brief Log current dual-band statistics to flight log
     * 
     * Logs:
     * - ESP-NOW link status and RSSI
     * - LoRa link status and RSSI
     * - Message filter statistics
     * - Deduplication statistics
     * - Link transition counts
     * 
     * Should be called periodically (e.g., every 10 seconds)
     * 
     * Requirements: 5.3, 5.4, 5.5
     */
    void logStatistics();
    
    /**
     * @brief Log per-message-ID filter statistics to flight log
     * 
     * Logs the count of filtered messages for each message ID that has been filtered.
     * This provides detailed insight into which message types are being filtered from LoRa.
     * 
     * Should be called periodically or on demand for detailed analysis.
     * 
     * Requirements: 5.4
     */
    void logFilterStatistics();
};

#endif // DUAL_BAND_TRANSPORT_H
