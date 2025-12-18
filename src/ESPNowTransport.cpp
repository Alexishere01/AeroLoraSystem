/**
 * ESP-NOW Transport Implementation
 * 
 * This file implements a high-bandwidth transport layer using ESP-NOW protocol.
 * ESP-NOW provides 200-500 kbps throughput at close range (100-400m) without
 * requiring traditional WiFi association.
 * 
 * Key design decisions:
 * 1. Connectionless: No SSID, password, or IP address required
 * 2. Callback-based: Reception handled automatically by ESP32 Core 0
 * 3. Simple peer management: Single peer for drone-to-ground communication
 * 4. Reachability detection: 3-second timeout for peer availability
 * 
 * The transport is intentionally simple to minimize overhead and latency.
 * It's designed to work alongside LoRa for dual-band operation.
 */

// Debug output control
// Set to 1 to enable verbose debug output, 0 to disable
// #define ESPNOW_DEBUG 1  <-- Removed, using global DEBUG_LOGGING instead

#include "ESPNowTransport.h"
#include "esp_wifi.h"  // For esp_wifi_set_channel()

// Static instance pointer for callbacks
ESPNowTransport* ESPNowTransport::_instance = nullptr;

// ═══════════════════════════════════════════════════════════════════
// CONSTRUCTOR
// ═══════════════════════════════════════════════════════════════════

/**
 * Initialize transport with default values
 */
ESPNowTransport::ESPNowTransport() {
    // Initialize peer MAC to zeros
    memset(_peer_mac, 0, 6);
    
    // Initialize reachability tracking
    _peer_reachable = false;
    _last_rx_time = 0;
    
    // Initialize receive buffer
    _rx_len = 0;
    _rx_ready = false;
    
    // Initialize statistics
    memset(&_stats, 0, sizeof(ESPNowStats));
    
    // Not initialized yet
    _initialized = false;
    
    // Set static instance pointer for callbacks
    _instance = this;
}

// ═══════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════

/**
 * Initialize ESP-NOW with peer MAC address
 * 
 * This method performs the following steps:
 * 1. Initialize WiFi in station mode (required for ESP-NOW)
 * 2. Initialize ESP-NOW protocol
 * 3. Register send and receive callbacks
 * 4. Add peer device
 * 
 * Requirements: 1.1, 4.1, 4.2, 10.1, 10.2
 * 
 * @param peer_mac Peer device MAC address (6 bytes)
 * @return true if initialization successful, false otherwise
 */
bool ESPNowTransport::begin(const uint8_t* peer_mac) {
    // Store peer MAC address
    memcpy(_peer_mac, peer_mac, 6);
    
#if DEBUG_LOGGING
    Serial.println("[ESP-NOW] Initializing...");
    Serial.print("[ESP-NOW] Peer MAC: ");
    for (int i = 0; i < 6; i++) {
        Serial.print(_peer_mac[i], HEX);
        if (i < 5) Serial.print(":");
    }
    Serial.println();
#endif
    
    // Step 1: Initialize WiFi in station mode
    // ESP-NOW requires WiFi to be initialized but doesn't need connection
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();  // Don't connect to any AP
    
#if DEBUG_LOGGING
    Serial.print("[ESP-NOW] WiFi initialized, MAC: ");
    Serial.println(WiFi.macAddress());
#endif
    
    // Step 2: Initialize ESP-NOW protocol
    if (esp_now_init() != ESP_OK) {
        Serial.println("[ESP-NOW] ERROR: Init failed");
        return false;
    }
    
#if DEBUG_LOGGING
    Serial.println("[ESP-NOW] Protocol initialized");
#endif
    
    // Step 3: Register callbacks
    // These callbacks are called by ESP32 Core 0 automatically
    esp_now_register_recv_cb(onDataReceivedStatic);
    esp_now_register_send_cb(onDataSentStatic);
    
#if DEBUG_LOGGING
    Serial.println("[ESP-NOW] Callbacks registered");
#endif
    
    // Step 4: Add peer device
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, _peer_mac, 6);
    peerInfo.channel = 1;       // Use channel 1 (must match WiFi.setChannel above)
    peerInfo.encrypt = false;   // No encryption for now (Requirement 8.1)
    peerInfo.ifidx = WIFI_IF_STA;
    
    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
        Serial.println("[ESP-NOW] ERROR: Failed to add peer");
        return false;
    }
    
#if DEBUG_LOGGING
    Serial.println("[ESP-NOW] Peer added successfully");
    Serial.print("[ESP-NOW] Peer exists check: ");
    Serial.println(esp_now_is_peer_exist(_peer_mac) ? "YES" : "NO");
#endif
    
    _initialized = true;
    
    Serial.println("[ESP-NOW] Initialization complete");
    Serial.println("[ESP-NOW] Ready for 2.4 GHz communication");
    
    return true;
}

// ═══════════════════════════════════════════════════════════════════
// SENDING
// ═══════════════════════════════════════════════════════════════════

/**
 * Send packet via ESP-NOW
 * 
 * Transmits data to the configured peer device. This is a non-blocking
 * operation - the actual transmission happens asynchronously and the
 * result is reported via the send callback.
 * 
 * Requirements: 1.1, 1.3, 10.3
 * 
 * @param data Pointer to data buffer
 * @param len Length of data (max 250 bytes)
 * @return true if send initiated successfully, false otherwise
 */
bool ESPNowTransport::send(const uint8_t* data, uint8_t len) {
    if (!_initialized) {
        Serial.println("[ESP-NOW] ERROR: Not initialized");
        return false;
    }
    
    if (len > ESPNOW_MAX_PAYLOAD) {
        Serial.print("[ESP-NOW] ERROR: Payload too large (");
        Serial.print(len);
        Serial.print(" > ");
        Serial.print(ESPNOW_MAX_PAYLOAD);
        Serial.println(")");
        return false;
    }
    
    // Send packet to peer
    // This is non-blocking - result reported via callback
    esp_err_t result = esp_now_send(_peer_mac, data, len);
    
    if (result == ESP_OK) {
        // Send initiated successfully
        // Actual success/failure reported in callback
        return true;
    } else {
        // Failed to initiate send
        _stats.send_failures++;
        
#if DEBUG_LOGGING
        Serial.print("[ESP-NOW] ERROR: Send failed with code ");
        Serial.println(result);
#endif
        
        return false;
    }
}

// ═══════════════════════════════════════════════════════════════════
// RECEIVING
// ═══════════════════════════════════════════════════════════════════

/**
 * Check if received data is available
 * 
 * Requirements: 1.1
 * 
 * @return true if data ready to read, false otherwise
 */
bool ESPNowTransport::available() {
    return _rx_ready;
}

/**
 * Receive data from RX buffer
 * 
 * Copies received data to the provided buffer. Call available() first
 * to check if data is ready.
 * 
 * Requirements: 1.1
 * 
 * @param buffer Destination buffer
 * @param max_len Maximum bytes to copy
 * @return Number of bytes copied (0 if no data available)
 */
uint8_t ESPNowTransport::receive(uint8_t* buffer, uint8_t max_len) {
    if (!_rx_ready) {
        return 0;
    }
    
    // Copy data to output buffer
    uint8_t len = min(_rx_len, max_len);
    memcpy(buffer, _rx_buffer, len);
    
    // Clear RX buffer
    _rx_ready = false;
    _rx_len = 0;
    
    return len;
}

// ═══════════════════════════════════════════════════════════════════
// PEER REACHABILITY
// ═══════════════════════════════════════════════════════════════════

/**
 * Check if peer is reachable
 * 
 * A peer is considered reachable if we've received a packet from them
 * within the last 3 seconds. This provides a simple link quality indicator.
 * 
 * Requirements: 1.5, 10.2
 * 
 * @return true if peer is reachable, false otherwise
 */
bool ESPNowTransport::isPeerReachable() {
    return _peer_reachable;
}

/**
 * Process ESP-NOW (check peer reachability)
 * 
 * Call this periodically in main loop to update peer reachability status.
 * Checks if we've received packets recently and updates the reachable flag.
 * 
 * Requirements: 1.5, 10.2
 */
void ESPNowTransport::process() {
    if (!_initialized) {
        return;
    }
    
    // Check if peer has timed out (3 seconds since last RX)
    unsigned long now = millis();
    
    if (_peer_reachable && (now - _last_rx_time > ESPNOW_PEER_TIMEOUT)) {
        // Peer was reachable but has now timed out
        _peer_reachable = false;
        _stats.peer_unreachable_count++;
        
#if DEBUG_LOGGING
        Serial.println("[ESP-NOW] Peer unreachable (timeout)");
#endif
    }
}

// ═══════════════════════════════════════════════════════════════════
// CALLBACKS
// ═══════════════════════════════════════════════════════════════════

/**
 * Static callback for received packets
 * 
 * This is called by ESP32 Core 0 when a packet is received.
 * It forwards to the instance method for processing.
 * 
 * Requirements: 1.1, 10.2
 * 
 * @param mac Sender MAC address
 * @param data Received data
 * @param len Data length
 */
void ESPNowTransport::onDataReceivedStatic(const uint8_t *mac, const uint8_t *data, int len) {
    if (_instance != nullptr) {
        _instance->onDataReceived(mac, data, len);
    }
}

/**
 * Static callback for sent packets
 * 
 * This is called by ESP32 Core 0 when a packet transmission completes.
 * It forwards to the instance method for processing.
 * 
 * Requirements: 1.1, 10.3
 * 
 * @param mac Destination MAC address
 * @param status Transmission status (ESP_NOW_SEND_SUCCESS or ESP_NOW_SEND_FAIL)
 */
void ESPNowTransport::onDataSentStatic(const uint8_t *mac, esp_now_send_status_t status) {
    if (_instance != nullptr) {
        _instance->onDataSent(mac, status);
    }
}

/**
 * Instance method for received packet processing
 * 
 * Called from static callback to handle received data.
 * Copies data to RX buffer and updates statistics.
 * 
 * Note: This runs on ESP32 Core 0 (WiFi core), so keep it fast!
 * 
 * Requirements: 1.1, 1.5, 10.2
 * 
 * @param mac Sender MAC address
 * @param data Received data
 * @param len Data length
 */
void ESPNowTransport::onDataReceived(const uint8_t *mac, const uint8_t *data, int len) {
    // Update reachability
    _peer_reachable = true;
    _last_rx_time = millis();
    
    // Update statistics
    _stats.packets_received++;
    _stats.peer_reachable = true;
    
    // Copy data to RX buffer (if not already full)
    if (!_rx_ready && len <= ESPNOW_MAX_PAYLOAD) {
        _rx_len = len;
        memcpy(_rx_buffer, data, len);
        _rx_ready = true;
        
#if DEBUG_LOGGING
        Serial.print("[ESP-NOW] RX: ");
        Serial.print(len);
        Serial.print(" bytes from ");
        for (int i = 0; i < 6; i++) {
            Serial.print(mac[i], HEX);
            if (i < 5) Serial.print(":");
        }
        Serial.println();
#endif
    } else {
        // Buffer full or packet too large - drop it
#if DEBUG_LOGGING
        Serial.println("[ESP-NOW] WARNING: RX buffer full, packet dropped");
#endif
    }
}

/**
 * Instance method for sent packet processing
 * 
 * Called from static callback to handle transmission status.
 * Updates statistics based on success/failure.
 * 
 * Note: This runs on ESP32 Core 0 (WiFi core), so keep it fast!
 * 
 * Requirements: 1.1, 1.5, 10.3
 * 
 * @param mac Destination MAC address
 * @param status Transmission status
 */
void ESPNowTransport::onDataSent(const uint8_t *mac, esp_now_send_status_t status) {
    if (status == ESP_NOW_SEND_SUCCESS) {
        // Packet sent successfully
        _stats.packets_sent++;
        
#if DEBUG_LOGGING
        Serial.println("[ESP-NOW] TX: Success");
#endif
    } else {
        // Packet send failed
        _stats.send_failures++;
        
#if DEBUG_LOGGING
        Serial.println("[ESP-NOW] TX: Failed");
#endif
    }
}

// ═══════════════════════════════════════════════════════════════════
// STATISTICS
// ═══════════════════════════════════════════════════════════════════

/**
 * Get ESP-NOW statistics
 * 
 * Requirements: 1.5, 10.4, 11.3
 * 
 * @return Statistics structure with packet counts and signal metrics
 */
ESPNowStats ESPNowTransport::getStats() {
    // Update current peer reachability in stats
    _stats.peer_reachable = _peer_reachable;
    
    return _stats;
}

/**
 * Reset statistics counters
 */
void ESPNowTransport::resetStats() {
    memset(&_stats, 0, sizeof(ESPNowStats));
}

/**
 * Get peer MAC address
 * 
 * @param mac_out Buffer to copy MAC address to (6 bytes)
 */
void ESPNowTransport::getPeerMAC(uint8_t* mac_out) {
    memcpy(mac_out, _peer_mac, 6);
}

/**
 * Get last RSSI value
 * 
 * @return Last RSSI value (-100 to 0 dBm)
 */
int8_t ESPNowTransport::getLastRSSI() {
    return _stats.last_rssi;
}

/**
 * Inject test packet (for unit testing only)
 * 
 * Simulates receiving a packet without actual ESP-NOW transmission.
 * This is used by unit tests to test deduplication logic.
 * 
 * @param data Packet data
 * @param len Data length
 */
void ESPNowTransport::injectTestPacket(const uint8_t* data, uint8_t len) {
    // Simulate packet reception
    uint8_t dummy_mac[6] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
    onDataReceived(dummy_mac, data, len);
}
