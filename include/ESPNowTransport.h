/**
 * ESP-NOW Transport Layer
 * 
 * Provides high-bandwidth close-range communication using ESP-NOW protocol.
 * Designed to work alongside LoRa for dual-band operation.
 * 
 * Key Features:
 * - 200-500 kbps throughput (50-100x faster than LoRa)
 * - 100-400m range (depending on antenna)
 * - Peer reachability detection (3 second timeout)
 * - Statistics tracking (packets sent/received, failures, RSSI)
 * - Compatible with existing AeroLoRa packet structure
 * 
 * Design Philosophy:
 * - Simple connectionless protocol (no WiFi association required)
 * - Automatic peer management
 * - Callback-based reception (handled by ESP32 Core 0)
 * - Non-blocking transmission
 * 
 * Requirements: 1.1, 1.5, 4.1, 4.2, 4.3, 4.4, 10.1, 10.2, 10.3, 10.4, 11.1, 11.2, 11.3
 */

#ifndef ESPNOW_TRANSPORT_H
#define ESPNOW_TRANSPORT_H

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

// Maximum ESP-NOW payload size (250 bytes to match AeroLoRa)
#define ESPNOW_MAX_PAYLOAD 250

// Peer reachability timeout (3 seconds)
#define ESPNOW_PEER_TIMEOUT 3000

// Maximum number of peers (for future multi-drone support)
#define ESPNOW_MAX_PEERS 5

/**
 * ESP-NOW Statistics
 * 
 * Tracks communication metrics for monitoring and debugging:
 * - packets_sent: Successfully transmitted packets
 * - packets_received: Successfully received packets
 * - send_failures: Failed transmissions (peer unreachable, radio busy, etc.)
 * - peer_unreachable_count: Number of times peer became unreachable
 * - last_rssi: Most recent RSSI value from received packet
 * - peer_reachable: Current peer reachability status
 */
struct ESPNowStats {
    uint32_t packets_sent;              // Successfully transmitted packets
    uint32_t packets_received;          // Successfully received packets
    uint32_t send_failures;             // Failed transmissions
    uint32_t peer_unreachable_count;    // Times peer became unreachable
    int8_t   last_rssi;                 // Most recent RSSI (-100 to 0 dBm)
    bool     peer_reachable;            // Is peer currently reachable?
};

/**
 * ESP-NOW Transport Class
 * 
 * Manages ESP-NOW initialization, peer management, and packet transmission/reception.
 * 
 * Usage:
 * 1. Create instance: ESPNowTransport transport;
 * 2. Initialize: transport.begin(peer_mac);
 * 3. Send data: transport.send(data, len);
 * 4. Check for received data: if (transport.available()) { ... }
 * 5. Receive data: transport.receive(buffer, max_len);
 * 6. Check peer status: transport.isPeerReachable();
 * 
 * Thread Safety:
 * - Receive callbacks run on ESP32 Core 0 (WiFi core)
 * - Send operations run on Core 1 (Arduino loop)
 * - Internal queuing handles cross-core communication safely
 */
class ESPNowTransport {
public:
    /**
     * Constructor
     */
    ESPNowTransport();
    
    /**
     * Initialize ESP-NOW with peer MAC address
     * 
     * Steps:
     * 1. Initialize WiFi in station mode (required for ESP-NOW)
     * 2. Initialize ESP-NOW protocol
     * 3. Register send and receive callbacks
     * 4. Add peer device
     * 
     * @param peer_mac Peer device MAC address (6 bytes)
     * @return true if initialization successful, false otherwise
     * 
     * Requirements: 1.1, 4.1, 4.2, 10.1, 10.2
     */
    bool begin(const uint8_t* peer_mac);
    
    /**
     * Send packet via ESP-NOW
     * 
     * Transmits data to the configured peer device. This is a non-blocking
     * operation - the actual transmission happens asynchronously.
     * 
     * @param data Pointer to data buffer
     * @param len Length of data (max 250 bytes)
     * @return true if send initiated successfully, false otherwise
     * 
     * Requirements: 1.1, 1.3, 10.3
     */
    bool send(const uint8_t* data, uint8_t len);
    
    /**
     * Check if received data is available
     * 
     * @return true if data ready to read, false otherwise
     * 
     * Requirements: 1.1
     */
    bool available();
    
    /**
     * Receive data from RX buffer
     * 
     * Copies received data to the provided buffer. Call available() first
     * to check if data is ready.
     * 
     * @param buffer Destination buffer
     * @param max_len Maximum bytes to copy
     * @return Number of bytes copied (0 if no data available)
     * 
     * Requirements: 1.1
     */
    uint8_t receive(uint8_t* buffer, uint8_t max_len);
    
    /**
     * Check if peer is reachable
     * 
     * A peer is considered reachable if we've received a packet from them
     * within the last 3 seconds. This provides a simple link quality indicator.
     * 
     * @return true if peer is reachable, false otherwise
     * 
     * Requirements: 1.5, 10.2
     */
    bool isPeerReachable();
    
    /**
     * Get ESP-NOW statistics
     * 
     * @return Statistics structure with packet counts and signal metrics
     * 
     * Requirements: 1.5, 10.4, 11.3
     */
    ESPNowStats getStats();
    
    /**
     * Reset statistics counters
     */
    void resetStats();
    
    /**
     * Process ESP-NOW (check peer reachability)
     * 
     * Call this periodically in main loop to update peer reachability status.
     * Checks if we've received packets recently and updates the reachable flag.
     * 
     * Requirements: 1.5, 10.2
     */
    void process();
    
    /**
     * Get peer MAC address
     * 
     * @param mac_out Buffer to copy MAC address to (6 bytes)
     */
    void getPeerMAC(uint8_t* mac_out);
    
    /**
     * Get last RSSI value
     * 
     * @return Last RSSI value (-100 to 0 dBm)
     */
    int8_t getLastRSSI();
    
    /**
     * Inject test packet (for unit testing only)
     * 
     * Simulates receiving a packet without actual ESP-NOW transmission.
     * This is used by unit tests to test deduplication logic.
     * 
     * @param data Packet data
     * @param len Data length
     */
    void injectTestPacket(const uint8_t* data, uint8_t len);
    
private:
    // Peer MAC address
    uint8_t _peer_mac[6];
    
    // Peer reachability tracking
    bool _peer_reachable;
    unsigned long _last_rx_time;
    
    // Statistics
    ESPNowStats _stats;
    
    // Receive buffer
    uint8_t _rx_buffer[ESPNOW_MAX_PAYLOAD];
    uint8_t _rx_len;
    bool _rx_ready;
    
    // Initialization flag
    bool _initialized;
    
    /**
     * Static callback for received packets
     * 
     * This is called by ESP32 Core 0 when a packet is received.
     * It forwards to the instance method for processing.
     * 
     * @param mac Sender MAC address
     * @param data Received data
     * @param len Data length
     * 
     * Requirements: 1.1, 10.2
     */
    static void onDataReceivedStatic(const uint8_t *mac, const uint8_t *data, int len);
    
    /**
     * Static callback for sent packets
     * 
     * This is called by ESP32 Core 0 when a packet transmission completes.
     * It forwards to the instance method for processing.
     * 
     * @param mac Destination MAC address
     * @param status Transmission status (ESP_NOW_SEND_SUCCESS or ESP_NOW_SEND_FAIL)
     * 
     * Requirements: 1.1, 10.3
     */
    static void onDataSentStatic(const uint8_t *mac, esp_now_send_status_t status);
    
    /**
     * Instance method for received packet processing
     * 
     * Called from static callback to handle received data.
     * Copies data to RX buffer and updates statistics.
     * 
     * @param mac Sender MAC address
     * @param data Received data
     * @param len Data length
     * 
     * Requirements: 1.1, 1.5, 10.2
     */
    void onDataReceived(const uint8_t *mac, const uint8_t *data, int len);
    
    /**
     * Instance method for sent packet processing
     * 
     * Called from static callback to handle transmission status.
     * Updates statistics based on success/failure.
     * 
     * @param mac Destination MAC address
     * @param status Transmission status
     * 
     * Requirements: 1.1, 1.5, 10.3
     */
    void onDataSent(const uint8_t *mac, esp_now_send_status_t status);
    
    // Static instance pointer for callbacks
    static ESPNowTransport* _instance;
};

#endif // ESPNOW_TRANSPORT_H
