/**
 * Relay UART Protocol - Inter-Heltec Communication for Asymmetric Relay
 * 
 * This protocol enables UART communication between Drone2 Primary and Secondary
 * Heltec modules for relay operations. It is separate from the AeroLoRa protocol
 * which handles LoRa radio communication.
 * 
 * Purpose:
 * - Forward packets from Primary (915 MHz) to Secondary (902 MHz) for relay
 * - Forward packets from Secondary (902 MHz) to Primary for delivery to flight controller
 * - Exchange relay statistics and status information
 * 
 * Packet Format:
 * [MARKER][SRC][DEST][LEN][PAYLOAD][CHECKSUM]
 * 
 * - MARKER (1 byte): 0xFE - Distinguishes from MAVLink packets
 * - SRC (1 byte): Source node ID (NODE_DRONE1=1, NODE_DRONE2=2, NODE_GROUND=0)
 * - DEST (1 byte): Destination node ID
 * - LEN (1 byte): Payload length (0-250 bytes)
 * - PAYLOAD (0-250 bytes): Raw packet data (MAVLink or AeroLoRa packet)
 * - CHECKSUM (2 bytes): Fletcher-16 over SRC+DEST+LEN+PAYLOAD
 * 
 * Total overhead: 5 bytes + payload
 * 
 * Design Philosophy:
 * - Simple binary framing for minimal overhead
 * - Fletcher-16 checksum for error detection (more robust than simple sum)
 * - No ACK/NACK mechanism (UART is reliable over short cable)
 * - No retry mechanism (packet loss is tracked but not retried)
 * - Transparent forwarding (no MAVLink processing at UART level)
 */

#ifndef RELAY_UART_PROTOCOL_H
#define RELAY_UART_PROTOCOL_H

#include <Arduino.h>

// ═══════════════════════════════════════════════════════════════════
// PROTOCOL CONSTANTS
// ═══════════════════════════════════════════════════════════════════

// UART packet marker (0xFE distinguishes from MAVLink 0xFD/0xFE magic bytes)
// Note: While MAVLink v1 uses 0xFE, the full packet structure is different
// enough that collision is unlikely, and checksum validation will catch any issues
#define UART_MARKER             0xFE

// Maximum payload size (matches AeroLoRa max payload)
#define UART_MAX_PAYLOAD        250

// UART buffer size (header + max payload + checksum)
#define UART_BUFFER_SIZE        256

// UART timeout for receive state machine (milliseconds)
#define UART_TIMEOUT_MS         1000

// Node ID constants (shared with AeroLoRa protocol)
#define NODE_GROUND             0       // Ground station node ID
#define NODE_DRONE1             1       // Drone1 node ID
#define NODE_DRONE2             2       // Drone2 Primary node ID
#define NODE_RELAY              3       // Drone2 Secondary node ID (special relay ID)

// ═══════════════════════════════════════════════════════════════════
// PACKET STRUCTURE
// ═══════════════════════════════════════════════════════════════════

/**
 * UART Packet Structure
 * 
 * Simple binary framing for inter-Heltec communication.
 * 
 * Fields:
 * - marker: 0xFE packet marker (identifies UART relay packets)
 * - src_id: Source node ID (who sent this packet originally)
 * - dest_id: Destination node ID (who should receive this packet)
 * - payload_len: Length of payload data (0-250 bytes)
 * - payload: Raw packet data (MAVLink or AeroLoRa packet)
 * - checksum: Fletcher-16 checksum over src_id + dest_id + payload_len + payload
 * 
 * Note: Checksum is NOT part of the struct to allow flexible payload sizes.
 * It is calculated and appended during transmission, validated during reception.
 */
struct __attribute__((packed)) UartRelayPacket {
    uint8_t  marker;        // 0xFE packet marker
    uint8_t  src_id;        // Source node ID
    uint8_t  dest_id;       // Destination node ID
    uint8_t  payload_len;   // Payload length (0-250 bytes)
    uint8_t  payload[UART_MAX_PAYLOAD];  // Raw packet data
    // Note: checksum (2 bytes) is appended after payload, not part of struct
};

// ═══════════════════════════════════════════════════════════════════
// RELAY STATISTICS
// ═══════════════════════════════════════════════════════════════════

/**
 * Relay Statistics Structure
 * 
 * Tracks relay operations and UART communication health.
 * 
 * Drone2 Primary stats:
 * - packets_overheard: Packets heard from Drone1 @ 915 MHz
 * - packets_forwarded: Packets forwarded to Secondary via UART
 * - weak_signals_detected: Count of RSSI < -95 dBm detections
 * - relay_mode_duration_ms: Total time in relay mode
 * 
 * Drone2 Secondary stats:
 * - packets_relayed_to_qgc: Packets sent to QGC @ 902 MHz
 * - packets_received_from_qgc: Packets received from QGC @ 902 MHz
 * - uart_tx_packets: UART packets sent to Primary
 * - uart_rx_packets: UART packets received from Primary
 * - uart_checksum_errors: UART checksum failures
 * - uart_buffer_overflows: UART buffer overflow events
 * 
 * QGC stats:
 * - relay_activations: Number of times relay mode activated
 * - packets_from_915mhz: Packets received at 915 MHz
 * - packets_from_902mhz: Packets received at 902 MHz
 * - relay_mode_active: Current relay status
 */
struct RelayStats {
    // Drone2 Primary stats
    uint32_t packets_overheard;         // Packets heard from Drone1
    uint32_t packets_forwarded;         // Packets forwarded to Secondary
    uint32_t weak_signals_detected;     // Count of RSSI < -95 dBm
    uint32_t relay_mode_duration_ms;    // Total time in relay mode
    
    // Drone2 Secondary stats
    uint32_t packets_relayed_to_qgc;    // Packets sent to QGC @ 902 MHz
    uint32_t packets_received_from_qgc; // Packets received from QGC @ 902 MHz
    uint32_t uart_tx_packets;           // UART packets sent to Primary
    uint32_t uart_rx_packets;           // UART packets received from Primary
    uint32_t uart_checksum_errors;      // UART checksum failures
    uint32_t uart_buffer_overflows;     // UART buffer overflow events
    
    // QGC stats
    uint32_t relay_activations;         // Number of times relay mode activated
    uint32_t packets_from_915mhz;       // Packets received at 915 MHz
    uint32_t packets_from_902mhz;       // Packets received at 902 MHz
    bool relay_mode_active;             // Current relay status
};

// ═══════════════════════════════════════════════════════════════════
// CHECKSUM FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

/**
 * Calculate Fletcher-16 checksum
 * 
 * Fletcher-16 is a simple checksum algorithm that is more robust than
 * a simple sum. It catches common errors like transposed bytes and
 * provides good error detection with minimal computational overhead.
 * 
 * Algorithm:
 * - Maintains two running sums (sum1 and sum2)
 * - sum1 = sum of all bytes (mod 255)
 * - sum2 = sum of all sum1 values (mod 255)
 * - Result = (sum2 << 8) | sum1
 * 
 * Properties:
 * - Detects all single-bit errors
 * - Detects all double-bit errors
 * - Detects burst errors up to 16 bits
 * - Detects most transposition errors
 * 
 * @param data Pointer to data buffer
 * @param len Number of bytes to process
 * @return 16-bit checksum value
 */
inline uint16_t fletcher16(const uint8_t* data, size_t len) {
    uint16_t sum1 = 0;
    uint16_t sum2 = 0;
    
    for (size_t i = 0; i < len; i++) {
        sum1 = (sum1 + data[i]) % 255;
        sum2 = (sum2 + sum1) % 255;
    }
    
    return (sum2 << 8) | sum1;
}

// ═══════════════════════════════════════════════════════════════════
// UART HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

/**
 * Send UART packet with checksum
 * 
 * Builds a complete UART packet with marker, addressing, payload, and checksum.
 * Transmits the packet over the specified UART interface.
 * 
 * Packet structure sent:
 * [MARKER][SRC][DEST][LEN][PAYLOAD][CHECKSUM_LOW][CHECKSUM_HIGH]
 * 
 * @param uart UART interface to send on (e.g., Serial2)
 * @param src_id Source node ID
 * @param dest_id Destination node ID
 * @param payload Pointer to payload data
 * @param payload_len Length of payload (0-250 bytes)
 * @param stats Pointer to statistics structure (optional, can be nullptr)
 * @return true if sent successfully, false if payload too large
 */
inline bool sendUartPacket(HardwareSerial& uart, uint8_t src_id, uint8_t dest_id, 
                           const uint8_t* payload, uint8_t payload_len, 
                           RelayStats* stats = nullptr) {
    // Validate payload length
    if (payload_len > UART_MAX_PAYLOAD) {
        return false;
    }
    
    // Build packet in buffer
    uint8_t buffer[UART_BUFFER_SIZE];
    buffer[0] = UART_MARKER;
    buffer[1] = src_id;
    buffer[2] = dest_id;
    buffer[3] = payload_len;
    
    // Copy payload
    if (payload_len > 0 && payload != nullptr) {
        memcpy(&buffer[4], payload, payload_len);
    }
    
    // Calculate Fletcher-16 checksum over SRC+DEST+LEN+PAYLOAD
    uint16_t checksum = fletcher16(&buffer[1], 3 + payload_len);
    buffer[4 + payload_len] = checksum & 0xFF;          // Checksum low byte
    buffer[5 + payload_len] = (checksum >> 8) & 0xFF;   // Checksum high byte
    
    // Send packet
    uart.write(buffer, 6 + payload_len);
    
    // Update statistics
    if (stats != nullptr) {
        stats->uart_tx_packets++;
    }
    
    return true;
}

/**
 * Receive UART packet with checksum validation
 * 
 * Implements a state machine to receive and validate UART packets.
 * Handles framing, checksum validation, and error detection.
 * 
 * State machine:
 * 1. Wait for MARKER byte (0xFE)
 * 2. Read SRC, DEST, LEN bytes
 * 3. Read PAYLOAD bytes (LEN bytes)
 * 4. Read CHECKSUM bytes (2 bytes)
 * 5. Validate checksum
 * 6. Return payload if valid
 * 
 * Error handling (Requirements 4.4, 4.5, 13.4):
 * - Checksum failure: Flush buffer, reset state machine, log error, increment counter
 * - Buffer overflow: Flush buffer, reset state machine, log error, increment counter
 * - Timeout: Reset state machine after 1 second of inactivity, flush buffer
 * - Invalid length: Flush buffer, reset state machine, log error
 * 
 * @param uart UART interface to receive from (e.g., Serial2)
 * @param src_id Output: Source node ID
 * @param dest_id Output: Destination node ID
 * @param payload Output buffer for payload data
 * @param max_payload_len Maximum payload buffer size
 * @param stats Pointer to statistics structure (optional, can be nullptr)
 * @return Number of payload bytes received (0 if no complete packet or error)
 */
inline uint8_t receiveUartPacket(HardwareSerial& uart, uint8_t& src_id, uint8_t& dest_id,
                                 uint8_t* payload, uint8_t max_payload_len,
                                 RelayStats* stats = nullptr) {
    static uint8_t rxBuffer[UART_BUFFER_SIZE];
    static uint8_t rxIndex = 0;
    static bool inPacket = false;
    static unsigned long lastRxTime = 0;
    
    // Check for timeout (reset state machine if no activity for 1 second)
    // Requirement 13.4: Implement 1 second UART timeout
    if (inPacket && (millis() - lastRxTime > UART_TIMEOUT_MS)) {
        #ifdef RELAY_DEBUG
        Serial.println("[UART ERROR] Timeout - resetting state machine");
        #endif
        
        // Flush buffer and reset state machine
        memset(rxBuffer, 0, sizeof(rxBuffer));
        inPacket = false;
        rxIndex = 0;
        
        // Flush any remaining bytes in UART buffer
        while (uart.available()) {
            uart.read();
        }
    }
    
    // Process available bytes
    while (uart.available()) {
        uint8_t byte = uart.read();
        lastRxTime = millis();
        
        // Look for packet start marker
        if (!inPacket && byte == UART_MARKER) {
            rxBuffer[0] = byte;
            rxIndex = 1;
            inPacket = true;
            continue;
        }
        
        // Accumulate packet bytes
        if (inPacket) {
            rxBuffer[rxIndex++] = byte;
            
            // Check if we have enough bytes to read length field
            if (rxIndex >= 4) {
                uint8_t len = rxBuffer[3];
                uint16_t expectedSize = 6 + len;  // MARKER + SRC + DEST + LEN + PAYLOAD + CHECKSUM(2)
                
                // Check for buffer overflow
                // Requirement 4.4: Detect and handle buffer overflows
                if (expectedSize > UART_BUFFER_SIZE || len > UART_MAX_PAYLOAD) {
                    // Payload too large - flush buffer and reset state machine
                    #ifdef RELAY_DEBUG
                    Serial.print("[UART ERROR] Buffer overflow - len=");
                    Serial.print(len);
                    Serial.print(" expectedSize=");
                    Serial.println(expectedSize);
                    #endif
                    
                    if (stats != nullptr) {
                        stats->uart_buffer_overflows++;
                    }
                    
                    // Flush buffer and reset state machine
                    memset(rxBuffer, 0, sizeof(rxBuffer));
                    inPacket = false;
                    rxIndex = 0;
                    
                    // Flush UART buffer
                    while (uart.available()) {
                        uart.read();
                    }
                    
                    continue;
                }
                
                // Check if we have complete packet
                if (rxIndex >= expectedSize) {
                    // Extract checksum from packet
                    uint16_t receivedChecksum = rxBuffer[4 + len] | (rxBuffer[5 + len] << 8);
                    
                    // Calculate checksum over SRC+DEST+LEN+PAYLOAD
                    uint16_t calculatedChecksum = fletcher16(&rxBuffer[1], 3 + len);
                    
                    // Validate checksum
                    // Requirement 4.4: Detect and handle checksum failures
                    if (receivedChecksum == calculatedChecksum) {
                        // Valid packet - extract fields
                        src_id = rxBuffer[1];
                        dest_id = rxBuffer[2];
                        
                        // Copy payload to output buffer
                        uint8_t copyLen = min(len, max_payload_len);
                        if (copyLen > 0 && payload != nullptr) {
                            memcpy(payload, &rxBuffer[4], copyLen);
                        }
                        
                        // Update statistics
                        if (stats != nullptr) {
                            stats->uart_rx_packets++;
                        }
                        
                        // Reset state machine for next packet
                        memset(rxBuffer, 0, sizeof(rxBuffer));
                        inPacket = false;
                        rxIndex = 0;
                        
                        return copyLen;
                    } else {
                        // Checksum failure - flush buffer and reset state machine
                        #ifdef RELAY_DEBUG
                        Serial.print("[UART ERROR] Checksum failure - expected=0x");
                        Serial.print(calculatedChecksum, HEX);
                        Serial.print(" received=0x");
                        Serial.println(receivedChecksum, HEX);
                        #endif
                        
                        if (stats != nullptr) {
                            stats->uart_checksum_errors++;
                        }
                        
                        // Flush buffer and reset state machine
                        memset(rxBuffer, 0, sizeof(rxBuffer));
                        inPacket = false;
                        rxIndex = 0;
                        
                        // Flush UART buffer to recover from error
                        while (uart.available()) {
                            uart.read();
                        }
                    }
                }
            }
            
            // Prevent buffer overflow (should not happen with length check above)
            // Requirement 4.5: Flush buffer and reset state machine on errors
            if (rxIndex >= UART_BUFFER_SIZE) {
                #ifdef RELAY_DEBUG
                Serial.println("[UART ERROR] Buffer index overflow");
                #endif
                
                if (stats != nullptr) {
                    stats->uart_buffer_overflows++;
                }
                
                // Flush buffer and reset state machine
                memset(rxBuffer, 0, sizeof(rxBuffer));
                inPacket = false;
                rxIndex = 0;
                
                // Flush UART buffer
                while (uart.available()) {
                    uart.read();
                }
            }
        }
    }
    
    // No complete packet received yet
    return 0;
}

// ═══════════════════════════════════════════════════════════════════
// WATCHDOG TIMERS
// ═══════════════════════════════════════════════════════════════════

/**
 * Watchdog timer structure
 * 
 * Tracks timeout events for various system components.
 * 
 * Requirements: 13.1, 13.5
 */
struct WatchdogTimers {
    // UART communication watchdog (1 second)
    unsigned long last_uart_activity;
    bool uart_timeout_logged;
    
    // Relay mode inactivity watchdog (30 seconds)
    unsigned long last_relay_activity;
    bool relay_timeout_logged;
    
    // Secondary not responding watchdog (5 seconds)
    unsigned long last_secondary_response;
    bool secondary_timeout_logged;
};

/**
 * Initialize watchdog timers
 * 
 * @param watchdog Pointer to watchdog structure
 */
inline void initWatchdogTimers(WatchdogTimers* watchdog) {
    unsigned long now = millis();
    watchdog->last_uart_activity = now;
    watchdog->uart_timeout_logged = false;
    watchdog->last_relay_activity = now;
    watchdog->relay_timeout_logged = false;
    watchdog->last_secondary_response = now;
    watchdog->secondary_timeout_logged = false;
}

/**
 * Check UART communication watchdog (1 second timeout)
 * 
 * Monitors UART activity and logs timeout events.
 * 
 * Requirements: 13.5
 * 
 * @param watchdog Pointer to watchdog structure
 * @return true if UART is active, false if timeout occurred
 */
inline bool checkUartWatchdog(WatchdogTimers* watchdog) {
    const unsigned long UART_WATCHDOG_MS = 1000;  // 1 second
    unsigned long now = millis();
    
    if (now - watchdog->last_uart_activity > UART_WATCHDOG_MS) {
        if (!watchdog->uart_timeout_logged) {
            Serial.println("[WATCHDOG] UART communication timeout (1 second)");
            watchdog->uart_timeout_logged = true;
        }
        return false;
    }
    
    // Reset timeout flag when activity resumes
    if (watchdog->uart_timeout_logged) {
        Serial.println("[WATCHDOG] UART communication restored");
        watchdog->uart_timeout_logged = false;
    }
    
    return true;
}

/**
 * Update UART activity timestamp
 * 
 * Call this whenever UART activity is detected.
 * 
 * @param watchdog Pointer to watchdog structure
 */
inline void updateUartActivity(WatchdogTimers* watchdog) {
    watchdog->last_uart_activity = millis();
}

/**
 * Check relay mode inactivity watchdog (30 second timeout)
 * 
 * Monitors relay activity and logs timeout events.
 * 
 * Requirements: 13.1
 * 
 * @param watchdog Pointer to watchdog structure
 * @return true if relay is active, false if timeout occurred
 */
inline bool checkRelayWatchdog(WatchdogTimers* watchdog) {
    const unsigned long RELAY_WATCHDOG_MS = 30000;  // 30 seconds
    unsigned long now = millis();
    
    if (now - watchdog->last_relay_activity > RELAY_WATCHDOG_MS) {
        if (!watchdog->relay_timeout_logged) {
            Serial.println("[WATCHDOG] Relay mode inactivity timeout (30 seconds)");
            watchdog->relay_timeout_logged = true;
        }
        return false;
    }
    
    // Reset timeout flag when activity resumes
    if (watchdog->relay_timeout_logged) {
        Serial.println("[WATCHDOG] Relay activity resumed");
        watchdog->relay_timeout_logged = false;
    }
    
    return true;
}

/**
 * Update relay activity timestamp
 * 
 * Call this whenever relay activity is detected.
 * 
 * @param watchdog Pointer to watchdog structure
 */
inline void updateRelayActivity(WatchdogTimers* watchdog) {
    watchdog->last_relay_activity = millis();
}

/**
 * Check Secondary not responding watchdog (5 second timeout)
 * 
 * Monitors Secondary Heltec responses and logs timeout events.
 * 
 * Requirements: 13.5
 * 
 * @param watchdog Pointer to watchdog structure
 * @return true if Secondary is responding, false if timeout occurred
 */
inline bool checkSecondaryWatchdog(WatchdogTimers* watchdog) {
    const unsigned long SECONDARY_WATCHDOG_MS = 5000;  // 5 seconds
    unsigned long now = millis();
    
    if (now - watchdog->last_secondary_response > SECONDARY_WATCHDOG_MS) {
        if (!watchdog->secondary_timeout_logged) {
            Serial.println("[WATCHDOG] Secondary not responding (5 seconds)");
            watchdog->secondary_timeout_logged = true;
        }
        return false;
    }
    
    // Reset timeout flag when activity resumes
    if (watchdog->secondary_timeout_logged) {
        Serial.println("[WATCHDOG] Secondary responding again");
        watchdog->secondary_timeout_logged = false;
    }
    
    return true;
}

/**
 * Update Secondary response timestamp
 * 
 * Call this whenever Secondary response is detected.
 * 
 * @param watchdog Pointer to watchdog structure
 */
inline void updateSecondaryResponse(WatchdogTimers* watchdog) {
    watchdog->last_secondary_response = millis();
}

// ═══════════════════════════════════════════════════════════════════
// RADIO ERROR HANDLING
// ═══════════════════════════════════════════════════════════════════

/**
 * Radio error handling with retry and exponential backoff
 * 
 * Implements robust error handling for RadioLib transmission failures.
 * Uses exponential backoff strategy to handle temporary radio issues.
 * 
 * Algorithm:
 * 1. Attempt transmission
 * 2. If failure, wait backoff_ms and retry
 * 3. Double backoff time for each retry (exponential backoff)
 * 4. Maximum 3 retries
 * 5. If all retries fail, log error and return failure
 * 
 * Radio reset logic:
 * - Track consecutive failures across multiple calls
 * - If 5 consecutive failures occur, reset radio
 * - Reset counter on successful transmission
 * 
 * Requirements: 13.2, 13.3
 * 
 * @param radio Pointer to RadioLib radio object (SX1262)
 * @param data Pointer to data buffer to transmit
 * @param len Length of data to transmit
 * @param max_retries Maximum number of retry attempts (default 3)
 * @param initial_backoff_ms Initial backoff time in milliseconds (default 50ms)
 * @return RadioLib error code (RADIOLIB_ERR_NONE on success)
 */
template<typename RadioType>
inline int transmitWithRetry(RadioType* radio, uint8_t* data, size_t len, 
                             int max_retries = 3, int initial_backoff_ms = 50) {
    static int consecutiveFailures = 0;
    const int MAX_CONSECUTIVE_FAILURES = 5;
    
    int backoff_ms = initial_backoff_ms;
    int lastError = RADIOLIB_ERR_NONE;
    
    // Attempt transmission with exponential backoff
    for (int attempt = 0; attempt <= max_retries; attempt++) {
        // Attempt transmission
        int state = radio->transmit(data, len);
        
        if (state == RADIOLIB_ERR_NONE) {
            // Success - reset consecutive failure counter
            consecutiveFailures = 0;
            return RADIOLIB_ERR_NONE;
        }
        
        // Transmission failed
        lastError = state;
        consecutiveFailures++;
        
        // Get RSSI and SNR for error context
        float rssi = radio->getRSSI();
        float snr = radio->getSNR();
        
        #ifdef RELAY_DEBUG
        Serial.print("[RADIO ERROR] Transmission failed (attempt ");
        Serial.print(attempt + 1);
        Serial.print("/");
        Serial.print(max_retries + 1);
        Serial.print("): error=");
        Serial.print(state);
        Serial.print(" RSSI=");
        Serial.print(rssi, 1);
        Serial.print(" dBm SNR=");
        Serial.print(snr, 1);
        Serial.println(" dB");
        #endif
        
        // Check if we should reset radio after too many failures
        if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
            Serial.println("[RADIO ERROR] Too many consecutive failures - resetting radio");
            
            // Reset radio
            radio->reset();
            delay(100);
            
            // Re-initialize radio (caller should handle re-configuration)
            // Note: Full re-initialization requires frequency, bandwidth, etc.
            // which are not available here. Caller must handle this.
            
            consecutiveFailures = 0;
            return RADIOLIB_ERR_UNKNOWN;  // Signal that reset occurred
        }
        
        // If not last attempt, wait with exponential backoff
        if (attempt < max_retries) {
            delay(backoff_ms);
            backoff_ms *= 2;  // Exponential backoff
        }
    }
    
    // All retries exhausted
    Serial.print("[RADIO ERROR] All retries exhausted - error=");
    Serial.println(lastError);
    
    return lastError;
}

/**
 * Check if radio needs reset based on error code
 * 
 * Determines if a radio error is severe enough to warrant a reset.
 * 
 * @param errorCode RadioLib error code
 * @return true if radio should be reset
 */
inline bool shouldResetRadio(int errorCode) {
    // Reset on severe errors
    switch (errorCode) {
        case RADIOLIB_ERR_CHIP_NOT_FOUND:
        case RADIOLIB_ERR_SPI_CMD_TIMEOUT:
        case RADIOLIB_ERR_SPI_CMD_FAILED:
        case RADIOLIB_ERR_INVALID_FREQUENCY:
        case RADIOLIB_ERR_INVALID_BANDWIDTH:
        case RADIOLIB_ERR_INVALID_SPREADING_FACTOR:
        case RADIOLIB_ERR_INVALID_CODING_RATE:
        case RADIOLIB_ERR_INVALID_OUTPUT_POWER:
            return true;
        default:
            return false;
    }
}

// ═══════════════════════════════════════════════════════════════════
// STATISTICS HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

/**
 * Print relay statistics to serial console
 * 
 * Displays comprehensive relay statistics for debugging and monitoring.
 * Includes packet counts, error rates, and relay mode status.
 * 
 * Requirements: 12.4 - Print statistics every 10 seconds
 * 
 * @param stats Relay statistics structure
 * @param node_name Name of the node (e.g., "Primary", "Secondary", "QGC")
 */
inline void printRelayStats(const RelayStats& stats, const char* node_name) {
    Serial.println("═══════════════════════════════════════════════════════");
    Serial.print("Relay Statistics - ");
    Serial.println(node_name);
    Serial.println("═══════════════════════════════════════════════════════");
    
    // Drone2 Primary stats
    if (stats.packets_overheard > 0 || stats.packets_forwarded > 0) {
        Serial.println("Primary Stats:");
        Serial.print("  Packets overheard:      ");
        Serial.println(stats.packets_overheard);
        Serial.print("  Packets forwarded:      ");
        Serial.println(stats.packets_forwarded);
        Serial.print("  Weak signals detected:  ");
        Serial.println(stats.weak_signals_detected);
        Serial.print("  Relay mode duration:    ");
        Serial.print(stats.relay_mode_duration_ms / 1000.0, 1);
        Serial.println(" seconds");
    }
    
    // Drone2 Secondary stats
    if (stats.packets_relayed_to_qgc > 0 || stats.packets_received_from_qgc > 0) {
        Serial.println("Secondary Stats:");
        Serial.print("  Packets relayed to QGC: ");
        Serial.println(stats.packets_relayed_to_qgc);
        Serial.print("  Packets from QGC:       ");
        Serial.println(stats.packets_received_from_qgc);
    }
    
    // UART stats
    if (stats.uart_tx_packets > 0 || stats.uart_rx_packets > 0) {
        Serial.println("UART Stats:");
        Serial.print("  TX packets:             ");
        Serial.println(stats.uart_tx_packets);
        Serial.print("  RX packets:             ");
        Serial.println(stats.uart_rx_packets);
        Serial.print("  Checksum errors:        ");
        Serial.println(stats.uart_checksum_errors);
        Serial.print("  Buffer overflows:       ");
        Serial.println(stats.uart_buffer_overflows);
        
        // Calculate error rate
        uint32_t total_rx = stats.uart_rx_packets + stats.uart_checksum_errors;
        if (total_rx > 0) {
            float error_rate = (stats.uart_checksum_errors * 100.0) / total_rx;
            Serial.print("  Error rate:             ");
            Serial.print(error_rate, 2);
            Serial.println("%");
        }
    }
    
    // QGC stats
    if (stats.packets_from_915mhz > 0 || stats.packets_from_902mhz > 0) {
        Serial.println("QGC Stats:");
        Serial.print("  Packets from 915 MHz:   ");
        Serial.println(stats.packets_from_915mhz);
        Serial.print("  Packets from 902 MHz:   ");
        Serial.println(stats.packets_from_902mhz);
        Serial.print("  Relay activations:      ");
        Serial.println(stats.relay_activations);
        Serial.print("  Relay mode active:      ");
        Serial.println(stats.relay_mode_active ? "YES" : "NO");
    }
    
    Serial.println("═══════════════════════════════════════════════════════");
}

/**
 * Log relay mode transition
 * 
 * Logs when relay mode is activated or deactivated with timestamp and reason.
 * 
 * Requirements: 12.4 - Log relay mode transitions
 * 
 * @param activated true if relay mode activated, false if deactivated
 * @param reason Reason for transition (e.g., "weak signal", "timeout", "direct link restored")
 */
inline void logRelayModeTransition(bool activated, const char* reason) {
    Serial.print("[RELAY MODE] ");
    Serial.print(millis() / 1000.0, 3);
    Serial.print("s - ");
    
    if (activated) {
        Serial.print("ACTIVATED");
    } else {
        Serial.print("DEACTIVATED");
    }
    
    Serial.print(" - Reason: ");
    Serial.println(reason);
}

/**
 * Log weak signal detection
 * 
 * Logs when a weak signal is detected with RSSI value and source node.
 * 
 * Requirements: 12.4 - Log weak signal detections
 * 
 * @param rssi RSSI value in dBm
 * @param src_id Source node ID
 * @param relay_requested true if relay was explicitly requested via flag
 */
inline void logWeakSignalDetection(float rssi, uint8_t src_id, bool relay_requested) {
    Serial.print("[WEAK SIGNAL] ");
    Serial.print(millis() / 1000.0, 3);
    Serial.print("s - Node ");
    Serial.print(src_id);
    Serial.print(" RSSI=");
    Serial.print(rssi, 1);
    Serial.print(" dBm");
    
    if (relay_requested) {
        Serial.print(" (relay requested by sender)");
    }
    
    Serial.println();
}

/**
 * Log UART error
 * 
 * Logs UART communication errors with error type and context.
 * 
 * Requirements: 12.4 - Log UART errors (checksum, overflow)
 * 
 * @param error_type Error type ("checksum", "overflow", "timeout")
 * @param context Additional context (e.g., packet length, buffer size)
 */
inline void logUartError(const char* error_type, const char* context = nullptr) {
    Serial.print("[UART ERROR] ");
    Serial.print(millis() / 1000.0, 3);
    Serial.print("s - ");
    Serial.print(error_type);
    
    if (context != nullptr) {
        Serial.print(" - ");
        Serial.print(context);
    }
    
    Serial.println();
}

/**
 * Log radio transmission error
 * 
 * Logs radio transmission failures with error code, RSSI, and SNR.
 * 
 * Requirements: 12.4 - Log radio errors (TX failures)
 * 
 * @param error_code RadioLib error code
 * @param rssi Current RSSI in dBm
 * @param snr Current SNR in dB
 * @param attempt Current attempt number
 * @param max_attempts Maximum number of attempts
 */
inline void logRadioError(int error_code, float rssi, float snr, 
                          int attempt, int max_attempts) {
    Serial.print("[RADIO ERROR] ");
    Serial.print(millis() / 1000.0, 3);
    Serial.print("s - TX failed (attempt ");
    Serial.print(attempt);
    Serial.print("/");
    Serial.print(max_attempts);
    Serial.print("): error=");
    Serial.print(error_code);
    Serial.print(" RSSI=");
    Serial.print(rssi, 1);
    Serial.print(" dBm SNR=");
    Serial.print(snr, 1);
    Serial.println(" dB");
}

#endif // RELAY_UART_PROTOCOL_H
