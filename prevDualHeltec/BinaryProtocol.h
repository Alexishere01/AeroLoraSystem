#pragma once
#include <Arduino.h>
#include "shared_protocol.h"

/**
 * @brief Send a binary UART packet
 * @param uart UART interface to send on (UART_SECONDARY or UART_PRIMARY)
 * @param command Command type
 * @param payload Pointer to payload data (can be nullptr if payload_len is 0)
 * @param payload_len Length of payload in bytes (0-255)
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 1.1, 1.5, 3.1, 8.1
 */
inline void sendBinaryPacket(HardwareSerial& uart, UartCommand command, 
                             const void* payload, uint16_t payload_len,
                             BinaryProtocolStats* stats = nullptr) {
    // Validate payload length
    if (payload_len > 255) {
        Serial.printf("✗ Binary packet payload too large: %d bytes (max 255)\n", payload_len);
        if (stats) stats->parse_errors++;
        return;
    }
    
    // Build packet header
    uint8_t packet[261];  // 1 + 1 + 2 + 255 + 2 = 261 max
    packet[0] = PACKET_START_BYTE;
    packet[1] = static_cast<uint8_t>(command);
    packet[2] = payload_len & 0xFF;        // Length low byte
    packet[3] = (payload_len >> 8) & 0xFF; // Length high byte
    
    // Copy payload if present
    if (payload && payload_len > 0) {
        memcpy(&packet[4], payload, payload_len);
    }
    
    // Calculate Fletcher-16 checksum over header + payload
    uint16_t checksum = fletcher16(packet, 4 + payload_len);
    packet[4 + payload_len] = checksum & 0xFF;        // Checksum low byte
    packet[4 + payload_len + 1] = (checksum >> 8) & 0xFF; // Checksum high byte
    
    // Transmit packet in single operation
    size_t totalLen = 6 + payload_len;
    uart.write(packet, totalLen);
    
    // Update transmission statistics
    if (stats) {
        stats->packets_sent++;
        stats->bytes_sent += totalLen;
    }
    
#ifdef DEBUG_BINARY_PROTOCOL
    // Debug logging for transmitted packets
    Serial.println("▶ Transmitting packet:");
    printPacketHex(packet, totalLen);
#endif
}

/**
 * @brief Send INIT command (CMD_INIT)
 * @param uart UART interface to send on
 * @param mode Operating mode string (e.g., "FREQUENCY_BRIDGE", "RELAY")
 * @param primary_freq Primary frequency in MHz
 * @param secondary_freq Secondary frequency in MHz
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 4.1
 */
inline void sendBinaryInit(HardwareSerial& uart, const char* mode, 
                          float primary_freq, float secondary_freq,
                          BinaryProtocolStats* stats = nullptr) {
    InitPayload payload;
    
    // Copy mode string (ensure null termination)
    strncpy(payload.mode, mode, sizeof(payload.mode) - 1);
    payload.mode[sizeof(payload.mode) - 1] = '\0';
    
    payload.primary_freq = primary_freq;
    payload.secondary_freq = secondary_freq;
    payload.timestamp = millis();
    
    sendBinaryPacket(uart, CMD_INIT, &payload, sizeof(payload), stats);
    
    Serial.printf("→ Sent binary INIT: mode=%s, primary=%.1f MHz, secondary=%.1f MHz\n",
                 mode, primary_freq, secondary_freq);
}

/**
 * @brief Send BRIDGE_TX command (CMD_BRIDGE_TX)
 * @param uart UART interface to send on
 * @param system_id MAVLink system ID (0 if unknown)
 * @param rssi RSSI in dBm
 * @param snr SNR in dB
 * @param data Raw MAVLink packet data
 * @param data_len Length of MAVLink data
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 4.2
 */
inline void sendBinaryBridgeTx(HardwareSerial& uart, uint8_t system_id,
                               float rssi, float snr,
                               const uint8_t* data, uint16_t data_len,
                               BinaryProtocolStats* stats = nullptr) {
    if (data_len > 245) {
        Serial.printf("✗ BRIDGE_TX data too large: %d bytes (max 245)\n", data_len);
        if (stats) stats->parse_errors++;
        return;
    }
    
    BridgePayload payload;
    payload.system_id = system_id;
    payload.rssi = rssi;
    payload.snr = snr;
    payload.data_len = data_len;
    
    if (data && data_len > 0) {
        memcpy(payload.data, data, data_len);
    }
    
    sendBinaryPacket(uart, CMD_BRIDGE_TX, &payload, 
                    sizeof(BridgePayload) - (245 - data_len), stats);
    
    Serial.printf("→ Sent binary BRIDGE_TX: sysid=%d, len=%d, RSSI=%.1f\n",
                 system_id, data_len, rssi);
}

/**
 * @brief Send BRIDGE_RX command (CMD_BRIDGE_RX)
 * @param uart UART interface to send on
 * @param system_id MAVLink system ID (0 if unknown)
 * @param rssi RSSI in dBm
 * @param snr SNR in dB
 * @param data Raw MAVLink packet data
 * @param data_len Length of MAVLink data
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 4.2
 */
inline void sendBinaryBridgeRx(HardwareSerial& uart, uint8_t system_id,
                               float rssi, float snr,
                               const uint8_t* data, uint16_t data_len,
                               BinaryProtocolStats* stats = nullptr) {
    if (data_len > 245) {
        Serial.printf("✗ BRIDGE_RX data too large: %d bytes (max 245)\n", data_len);
        if (stats) stats->parse_errors++;
        return;
    }
    
    BridgePayload payload;
    payload.system_id = system_id;
    payload.rssi = rssi;
    payload.snr = snr;
    payload.data_len = data_len;
    
    if (data && data_len > 0) {
        memcpy(payload.data, data, data_len);
    }
    
    sendBinaryPacket(uart, CMD_BRIDGE_RX, &payload,
                    sizeof(BridgePayload) - (245 - data_len), stats);
    
    Serial.printf("→ Sent binary BRIDGE_RX: sysid=%d, len=%d, RSSI=%.1f\n",
                 system_id, data_len, rssi);
}

/**
 * @brief Send STATUS_REPORT command (CMD_STATUS_REPORT)
 * @param uart UART interface to send on
 * @param status Pointer to status payload structure
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 4.3
 */
inline void sendBinaryStatus(HardwareSerial& uart, const StatusPayload* status,
                            BinaryProtocolStats* stats = nullptr) {
    if (!status) {
        Serial.println("✗ Cannot send STATUS_REPORT: null payload");
        if (stats) stats->parse_errors++;
        return;
    }
    
    sendBinaryPacket(uart, CMD_STATUS_REPORT, status, sizeof(StatusPayload), stats);
    
    Serial.printf("→ Sent binary STATUS: relay=%s, packets=%lu, RSSI=%.1f\n",
                 status->relay_active ? "active" : "inactive",
                 status->packets_relayed, status->rssi);
}

/**
 * @brief Send RELAY_ACTIVATE command (CMD_RELAY_ACTIVATE)
 * @param uart UART interface to send on
 * @param activate true to activate relay, false to deactivate
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 4.4
 */
inline void sendBinaryRelayActivate(HardwareSerial& uart, bool activate,
                                   BinaryProtocolStats* stats = nullptr) {
    RelayActivatePayload payload;
    payload.activate = activate;
    
    sendBinaryPacket(uart, CMD_RELAY_ACTIVATE, &payload, sizeof(payload), stats);
    
    Serial.printf("→ Sent binary RELAY_ACTIVATE: %s\n", 
                 activate ? "ACTIVATE" : "DEACTIVATE");
}

/**
 * @brief Send BROADCAST_RELAY_REQ command (CMD_BROADCAST_RELAY_REQ)
 * @param uart UART interface to send on
 * @param rssi RSSI in dBm
 * @param snr SNR in dB
 * @param packet_loss Packet loss percentage
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 4.5
 */
inline void sendBinaryBroadcastRelayReq(HardwareSerial& uart, float rssi, 
                                       float snr, float packet_loss,
                                       BinaryProtocolStats* stats = nullptr) {
    RelayRequestPayload payload;
    payload.rssi = rssi;
    payload.snr = snr;
    payload.packet_loss = packet_loss;
    
    sendBinaryPacket(uart, CMD_BROADCAST_RELAY_REQ, &payload, sizeof(payload), stats);
    
    Serial.printf("→ Sent binary BROADCAST_RELAY_REQ: RSSI=%.1f, SNR=%.1f, loss=%.1f%%\n",
                 rssi, snr, packet_loss);
}

/**
 * @brief Send ACK command (CMD_ACK)
 * @param uart UART interface to send on
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 4.1
 */
inline void sendBinaryAck(HardwareSerial& uart, BinaryProtocolStats* stats = nullptr) {
    // ACK has no payload
    sendBinaryPacket(uart, CMD_ACK, nullptr, 0, stats);
    
    Serial.println("→ Sent binary ACK");
}

/**
 * @brief Send RELAY_TX command (CMD_RELAY_TX)
 * @param uart UART interface to send on
 * @param data Raw packet data to relay
 * @param data_len Length of data
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 4.1
 */
inline void sendBinaryRelayTx(HardwareSerial& uart, const uint8_t* data, 
                             uint16_t data_len, BinaryProtocolStats* stats = nullptr) {
    if (data_len > 245) {
        Serial.printf("✗ RELAY_TX data too large: %d bytes (max 245)\n", data_len);
        if (stats) stats->parse_errors++;
        return;
    }
    
    RelayRxPayload payload;
    payload.rssi = 0.0f;  // Not applicable for TX
    payload.snr = 0.0f;   // Not applicable for TX
    
    if (data && data_len > 0) {
        memcpy(payload.data, data, data_len);
    }
    
    sendBinaryPacket(uart, CMD_RELAY_TX, &payload,
                    sizeof(RelayRxPayload) - (245 - data_len), stats);
    
    Serial.printf("→ Sent binary RELAY_TX: len=%d\n", data_len);
}

/**
 * @brief Send RELAY_RX command (CMD_RELAY_RX)
 * @param uart UART interface to send on
 * @param rssi RSSI in dBm
 * @param snr SNR in dB
 * @param data Raw packet data received
 * @param data_len Length of data
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 4.4
 */
inline void sendBinaryRelayRx(HardwareSerial& uart, float rssi, float snr,
                             const uint8_t* data, uint16_t data_len,
                             BinaryProtocolStats* stats = nullptr) {
    if (data_len > 245) {
        Serial.printf("✗ RELAY_RX data too large: %d bytes (max 245)\n", data_len);
        if (stats) stats->parse_errors++;
        return;
    }
    
    RelayRxPayload payload;
    payload.rssi = rssi;
    payload.snr = snr;
    
    if (data && data_len > 0) {
        memcpy(payload.data, data, data_len);
    }
    
    sendBinaryPacket(uart, CMD_RELAY_RX, &payload,
                    sizeof(RelayRxPayload) - (245 - data_len), stats);
    
    Serial.printf("→ Sent binary RELAY_RX: len=%d, RSSI=%.1f\n", data_len, rssi);
}

/**
 * @brief Send STATUS_REQUEST command (CMD_STATUS_REQUEST)
 * @param uart UART interface to send on
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 4.1
 */
inline void sendBinaryStatusRequest(HardwareSerial& uart, 
                                   BinaryProtocolStats* stats = nullptr) {
    // STATUS_REQUEST has no payload
    sendBinaryPacket(uart, CMD_STATUS_REQUEST, nullptr, 0, stats);
    
    Serial.println("→ Sent binary STATUS_REQUEST");
}

/**
 * @brief Send START_RELAY_DISCOVERY command (CMD_START_RELAY_DISCOVERY)
 * @param uart UART interface to send on
 * @param own_lat Own latitude (degrees * 1e7)
 * @param own_lon Own longitude (degrees * 1e7)
 * @param own_alt Own altitude (meters MSL)
 * @param gcs_rssi GCS link RSSI (dBm)
 * @param gcs_snr GCS link SNR (dB)
 * @param gcs_packet_loss GCS packet loss percentage
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 10.3
 */
inline void sendBinaryStartRelayDiscovery(HardwareSerial& uart,
                                         int32_t own_lat, int32_t own_lon, int16_t own_alt,
                                         float gcs_rssi, float gcs_snr, float gcs_packet_loss,
                                         BinaryProtocolStats* stats = nullptr) {
    StartRelayDiscoveryPayload payload;
    payload.own_lat = own_lat;
    payload.own_lon = own_lon;
    payload.own_alt = own_alt;
    payload.gcs_rssi = gcs_rssi;
    payload.gcs_snr = gcs_snr;
    payload.gcs_packet_loss = gcs_packet_loss;
    
    sendBinaryPacket(uart, CMD_START_RELAY_DISCOVERY, &payload, sizeof(payload), stats);
    
    Serial.printf("→ Sent binary START_RELAY_DISCOVERY: lat=%ld, lon=%ld, alt=%d, RSSI=%.1f\n",
                 own_lat, own_lon, own_alt, gcs_rssi);
}

/**
 * @brief Send RELAY_SELECTED command (CMD_RELAY_SELECTED)
 * @param uart UART interface to send on
 * @param relay_id System ID of selected relay
 * @param relay_rssi Mesh link RSSI to relay (dBm)
 * @param relay_snr Mesh link SNR to relay (dB)
 * @param relay_score Calculated relay score
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 10.4
 */
inline void sendBinaryRelaySelected(HardwareSerial& uart,
                                   uint8_t relay_id, float relay_rssi, 
                                   float relay_snr, float relay_score,
                                   BinaryProtocolStats* stats = nullptr) {
    RelaySelectedPayload payload;
    payload.relay_id = relay_id;
    payload.relay_rssi = relay_rssi;
    payload.relay_snr = relay_snr;
    payload.relay_score = relay_score;
    
    sendBinaryPacket(uart, CMD_RELAY_SELECTED, &payload, sizeof(payload), stats);
    
    Serial.printf("→ Sent binary RELAY_SELECTED: relay_id=%d, RSSI=%.1f, SNR=%.1f, score=%.1f\n",
                 relay_id, relay_rssi, relay_snr, relay_score);
}

/**
 * @brief Send RELAY_ESTABLISHED command (CMD_RELAY_ESTABLISHED)
 * @param uart UART interface to send on
 * @param relay_id System ID of active relay
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 10.4
 */
inline void sendBinaryRelayEstablished(HardwareSerial& uart,
                                      uint8_t relay_id,
                                      BinaryProtocolStats* stats = nullptr) {
    RelayEstablishedPayload payload;
    payload.relay_id = relay_id;
    
    sendBinaryPacket(uart, CMD_RELAY_ESTABLISHED, &payload, sizeof(payload), stats);
    
    Serial.printf("→ Sent binary RELAY_ESTABLISHED: relay_id=%d\n", relay_id);
}

/**
 * @brief Send RELAY_LOST command (CMD_RELAY_LOST)
 * @param uart UART interface to send on
 * @param relay_id System ID of lost relay
 * @param reason Reason code for connection loss
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 10.4
 */
inline void sendBinaryRelayLost(HardwareSerial& uart,
                               uint8_t relay_id, uint8_t reason,
                               BinaryProtocolStats* stats = nullptr) {
    RelayLostPayload payload;
    payload.relay_id = relay_id;
    payload.reason = reason;
    
    sendBinaryPacket(uart, CMD_RELAY_LOST, &payload, sizeof(payload), stats);
    
    const char* reason_str = "UNKNOWN";
    switch (static_cast<RelayLostReason>(reason)) {
        case RELAY_LOST_HEARTBEAT_TIMEOUT: reason_str = "HEARTBEAT_TIMEOUT"; break;
        case RELAY_LOST_LINK_QUALITY: reason_str = "LINK_QUALITY"; break;
        case RELAY_LOST_REJECTION: reason_str = "REJECTION"; break;
        case RELAY_LOST_GCS_RESTORED: reason_str = "GCS_RESTORED"; break;
    }
    
    Serial.printf("→ Sent binary RELAY_LOST: relay_id=%d, reason=%s\n", relay_id, reason_str);
}

// ============================================================================
// BINARY PACKET RECEPTION
// ============================================================================

/**
 * @brief Receive state machine states for binary packet reception
 * 
 * Requirements: 2.1, 2.2, 2.5, 6.1
 */
enum RxState {
    RX_WAIT_START,      // Waiting for start byte (0xAA)
    RX_READ_HEADER,     // Reading command and length fields
    RX_READ_PAYLOAD,    // Reading payload bytes
    RX_READ_CHECKSUM,   // Reading checksum bytes
    RX_VALIDATE         // Validating and processing packet
};

/**
 * @brief UART receive buffer and state tracking
 * Maintains state machine state and accumulates partial packets
 * 
 * Requirements: 2.1, 2.2, 2.5, 6.1
 */
struct UartRxBuffer {
    RxState state;              // Current state machine state
    uint8_t buffer[261];        // Raw packet buffer (max packet size)
    uint16_t bytes_received;    // Number of bytes received so far
    uint32_t last_byte_time;    // Timestamp of last received byte (for timeout)
    
    UartRxBuffer() : state(RX_WAIT_START), bytes_received(0), last_byte_time(0) {
        memset(buffer, 0, sizeof(buffer));
    }
};

// Forward declarations for packet processing
void processBinaryPacket(const uint8_t* packet_data, BinaryProtocolStats* stats);
void handleBinaryInit(const InitPayload* payload);
void handleBinaryBridgeTx(const BridgePayload* payload);
void handleBinaryBridgeRx(const BridgePayload* payload);
void handleBinaryStatus(const StatusPayload* payload);
void handleBinaryRelayActivate(const RelayActivatePayload* payload);
void handleBinaryRelayTx(const RelayRxPayload* payload);
void handleBinaryRelayRx(const RelayRxPayload* payload);
void handleBinaryBroadcastRelayReq(const RelayRequestPayload* payload);
void handleBinaryAck();
void handleBinaryStatusRequest();
void handleBinaryStartRelayDiscovery(const StartRelayDiscoveryPayload* payload);
void handleBinaryRelaySelected(const RelaySelectedPayload* payload);
void handleBinaryRelayEstablished(const RelayEstablishedPayload* payload);
void handleBinaryRelayLost(const RelayLostPayload* payload);

/**
 * @brief Process incoming UART data using state machine
 * Call this function repeatedly from the main loop to receive binary packets
 * 
 * @param uart UART interface to read from
 * @param rxBuffer Pointer to receive buffer structure
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.2, 3.3, 6.2, 6.3
 */
inline void processBinaryUart(HardwareSerial& uart, UartRxBuffer* rxBuffer, 
                             BinaryProtocolStats* stats = nullptr) {
    if (!rxBuffer) return;
    
    // Check for UART buffer overflow condition
    // ESP32 UART FIFO is 128 bytes, if we're getting close to full, it's a problem
    int available = uart.available();
    if (available > 120) {
        Serial.printf("⚠ UART buffer overflow detected: %d bytes pending\n", available);
        
        // Flush the UART buffer to prevent data corruption
        while (uart.available()) {
            uart.read();
        }
        
        // Log overflow event and increment counter
        if (stats) stats->buffer_overflow++;
        
        // Reset state machine
        rxBuffer->state = RX_WAIT_START;
        rxBuffer->bytes_received = 0;
        
        Serial.println("✓ UART buffer flushed and state reset");
        return;
    }
    
    while (uart.available()) {
        uint8_t byte = uart.read();
        uint32_t now = millis();
        
        // Timeout detection - reset if no data for 100ms
        if (rxBuffer->state != RX_WAIT_START && 
            (now - rxBuffer->last_byte_time) > 100) {
            Serial.println("⚠ UART timeout - resetting state");
            if (stats) stats->timeout_errors++;
            rxBuffer->state = RX_WAIT_START;
            rxBuffer->bytes_received = 0;
        }
        rxBuffer->last_byte_time = now;
        
        switch (rxBuffer->state) {
            case RX_WAIT_START:
                // Look for start byte
                if (byte == PACKET_START_BYTE) {
                    rxBuffer->buffer[0] = byte;
                    rxBuffer->bytes_received = 1;
                    rxBuffer->state = RX_READ_HEADER;
#ifdef DEBUG_BINARY_PROTOCOL
                    Serial.println("◀ State: WAIT_START → READ_HEADER (found start byte)");
#endif
                }
                break;
                
            case RX_READ_HEADER: {
                // Read command (byte 1) and length (bytes 2-3)
                rxBuffer->buffer[rxBuffer->bytes_received++] = byte;
                
                if (rxBuffer->bytes_received == 4) {
                    // Extract length from bytes 2-3 (little-endian)
                    uint16_t payload_len = rxBuffer->buffer[2] | 
                                          (rxBuffer->buffer[3] << 8);
                    
                    // Validate packet length
                    if (payload_len > 255) {
                        Serial.printf("✗ Invalid packet length: %d (max 255)\n", 
                                     payload_len);
                        if (stats) stats->parse_errors++;
#ifdef DEBUG_BINARY_PROTOCOL
                        printMalformedPacket(rxBuffer->buffer, rxBuffer->bytes_received, 
                                           "Invalid packet length");
#endif
                        rxBuffer->state = RX_WAIT_START;
                        rxBuffer->bytes_received = 0;
                    } else if (payload_len == 0) {
                        // No payload - go straight to checksum
                        rxBuffer->state = RX_READ_CHECKSUM;
#ifdef DEBUG_BINARY_PROTOCOL
                        Serial.println("◀ State: READ_HEADER → READ_CHECKSUM (no payload)");
#endif
                    } else {
                        // Has payload - read it
                        rxBuffer->state = RX_READ_PAYLOAD;
#ifdef DEBUG_BINARY_PROTOCOL
                        Serial.printf("◀ State: READ_HEADER → READ_PAYLOAD (expecting %d bytes)\n", 
                                     payload_len);
#endif
                    }
                }
                break;
            }
                
            case RX_READ_PAYLOAD: {
                // Accumulate payload bytes
                rxBuffer->buffer[rxBuffer->bytes_received++] = byte;
                
                // Check if we've read all payload bytes
                uint16_t payload_len = rxBuffer->buffer[2] | 
                                      (rxBuffer->buffer[3] << 8);
                if (rxBuffer->bytes_received == 4 + payload_len) {
                    rxBuffer->state = RX_READ_CHECKSUM;
#ifdef DEBUG_BINARY_PROTOCOL
                    Serial.println("◀ State: READ_PAYLOAD → READ_CHECKSUM");
#endif
                }
                break;
            }
                
            case RX_READ_CHECKSUM: {
                // Read checksum bytes (2 bytes)
                rxBuffer->buffer[rxBuffer->bytes_received++] = byte;
                
                // Check if we've read both checksum bytes
                uint16_t payload_len2 = rxBuffer->buffer[2] | 
                                       (rxBuffer->buffer[3] << 8);
                if (rxBuffer->bytes_received == 6 + payload_len2) {
                    rxBuffer->state = RX_VALIDATE;
#ifdef DEBUG_BINARY_PROTOCOL
                    Serial.println("◀ State: READ_CHECKSUM → VALIDATE");
#endif
                }
                break;
            }
                
            case RX_VALIDATE:
                // This state should not receive more bytes
                // Fall through to validation below
                break;
        }
        
        // Validate packet if we're in the validate state
        if (rxBuffer->state == RX_VALIDATE) {
            // Extract packet components
            uint16_t payload_len = rxBuffer->buffer[2] | 
                                  (rxBuffer->buffer[3] << 8);
            
            // Extract received checksum (little-endian)
            uint16_t received_checksum = 
                rxBuffer->buffer[4 + payload_len] | 
                (rxBuffer->buffer[4 + payload_len + 1] << 8);
            
            // Calculate expected checksum over header + payload
            uint16_t expected_checksum = fletcher16(rxBuffer->buffer, 
                                                   4 + payload_len);
            
            if (expected_checksum == received_checksum) {
                // Valid packet - process it
#ifdef DEBUG_BINARY_PROTOCOL
                Serial.println("◀ Received valid packet:");
                printPacketHex(rxBuffer->buffer, rxBuffer->bytes_received);
#endif
                processBinaryPacket(rxBuffer->buffer, stats);
                
                // Update reception statistics
                if (stats) {
                    stats->packets_received++;
                    stats->bytes_received += rxBuffer->bytes_received;
                }
            } else {
                // Checksum mismatch
                Serial.printf("✗ Checksum mismatch: expected 0x%04X, got 0x%04X\n",
                             expected_checksum, received_checksum);
                if (stats) stats->checksum_errors++;
#ifdef DEBUG_BINARY_PROTOCOL
                printMalformedPacket(rxBuffer->buffer, rxBuffer->bytes_received,
                                   "Checksum mismatch");
#endif
            }
            
            // Reset for next packet
            rxBuffer->state = RX_WAIT_START;
            rxBuffer->bytes_received = 0;
        }
    }
}

/**
 * @brief Process a validated binary packet by dispatching to appropriate handler
 * 
 * This function extracts the command type and payload from a validated packet
 * and calls the appropriate handler function. Handler functions must be 
 * implemented by the application (Primary or Secondary controller).
 * 
 * @param packet_data Pointer to the raw packet buffer (validated)
 * @param stats Pointer to statistics structure to update
 * 
 * Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 6.1, 9.2
 */
inline void processBinaryPacket(const uint8_t* packet_data, 
                               BinaryProtocolStats* stats) {
    if (!packet_data) return;
    
    // Extract command from byte 1
    UartCommand command = static_cast<UartCommand>(packet_data[1]);
    
    // Extract payload length from bytes 2-3 (little-endian)
    uint16_t payload_len = packet_data[2] | (packet_data[3] << 8);
    
    // Payload starts at byte 4
    const uint8_t* payload = &packet_data[4];
    
    // Dispatch based on command type
    switch (command) {
        case CMD_INIT: {
            if (payload_len == sizeof(InitPayload)) {
                const InitPayload* init = reinterpret_cast<const InitPayload*>(payload);
                Serial.printf("← Received INIT: mode=%s, primary=%.1f MHz, secondary=%.1f MHz\n",
                             init->mode, init->primary_freq, init->secondary_freq);
                handleBinaryInit(init);
            } else {
                Serial.printf("✗ INIT payload size mismatch: expected %d, got %d\n",
                             sizeof(InitPayload), payload_len);
                if (stats) stats->parse_errors++;
            }
            break;
        }
        
        case CMD_ACK: {
            Serial.println("← Received ACK");
            handleBinaryAck();
            break;
        }
        
        case CMD_RELAY_ACTIVATE: {
            if (payload_len == sizeof(RelayActivatePayload)) {
                const RelayActivatePayload* relay = 
                    reinterpret_cast<const RelayActivatePayload*>(payload);
                Serial.printf("← Received RELAY_ACTIVATE: %s\n",
                             relay->activate ? "ACTIVATE" : "DEACTIVATE");
                handleBinaryRelayActivate(relay);
            } else {
                Serial.printf("✗ RELAY_ACTIVATE payload size mismatch: expected %d, got %d\n",
                             sizeof(RelayActivatePayload), payload_len);
                if (stats) stats->parse_errors++;
            }
            break;
        }
        
        case CMD_RELAY_TX: {
            // RelayRxPayload is variable size, validate minimum
            if (payload_len >= 8) {  // rssi + snr = 8 bytes minimum
                const RelayRxPayload* relay = 
                    reinterpret_cast<const RelayRxPayload*>(payload);
                Serial.printf("← Received RELAY_TX: len=%d\n", payload_len - 8);
                handleBinaryRelayTx(relay);
            } else {
                Serial.printf("✗ RELAY_TX payload too small: %d bytes\n", payload_len);
                if (stats) stats->parse_errors++;
            }
            break;
        }
        
        case CMD_RELAY_RX: {
            // RelayRxPayload is variable size, validate minimum
            if (payload_len >= 8) {  // rssi + snr = 8 bytes minimum
                const RelayRxPayload* relay = 
                    reinterpret_cast<const RelayRxPayload*>(payload);
                Serial.printf("← Received RELAY_RX: RSSI=%.1f, SNR=%.1f, len=%d\n",
                             relay->rssi, relay->snr, payload_len - 8);
                handleBinaryRelayRx(relay);
            } else {
                Serial.printf("✗ RELAY_RX payload too small: %d bytes\n", payload_len);
                if (stats) stats->parse_errors++;
            }
            break;
        }
        
        case CMD_BRIDGE_TX: {
            // BridgePayload is variable size, validate minimum
            if (payload_len >= 11) {  // system_id + rssi + snr + data_len = 11 bytes minimum
                const BridgePayload* bridge = 
                    reinterpret_cast<const BridgePayload*>(payload);
                Serial.printf("← Received BRIDGE_TX: sysid=%d, len=%d, RSSI=%.1f\n",
                             bridge->system_id, bridge->data_len, bridge->rssi);
                handleBinaryBridgeTx(bridge);
            } else {
                Serial.printf("✗ BRIDGE_TX payload too small: %d bytes\n", payload_len);
                if (stats) stats->parse_errors++;
            }
            break;
        }
        
        case CMD_BRIDGE_RX: {
            // BridgePayload is variable size, validate minimum
            if (payload_len >= 11) {  // system_id + rssi + snr + data_len = 11 bytes minimum
                const BridgePayload* bridge = 
                    reinterpret_cast<const BridgePayload*>(payload);
                Serial.printf("← Received BRIDGE_RX: sysid=%d, len=%d, RSSI=%.1f\n",
                             bridge->system_id, bridge->data_len, bridge->rssi);
                handleBinaryBridgeRx(bridge);
            } else {
                Serial.printf("✗ BRIDGE_RX payload too small: %d bytes\n", payload_len);
                if (stats) stats->parse_errors++;
            }
            break;
        }
        
        case CMD_STATUS_REPORT: {
            if (payload_len == sizeof(StatusPayload)) {
                const StatusPayload* status = 
                    reinterpret_cast<const StatusPayload*>(payload);
                Serial.printf("← Received STATUS: relay=%s, packets=%lu, RSSI=%.1f\n",
                             status->relay_active ? "active" : "inactive",
                             status->packets_relayed, status->rssi);
                handleBinaryStatus(status);
            } else {
                Serial.printf("✗ STATUS_REPORT payload size mismatch: expected %d, got %d\n",
                             sizeof(StatusPayload), payload_len);
                if (stats) stats->parse_errors++;
            }
            break;
        }
        
        case CMD_BROADCAST_RELAY_REQ: {
            if (payload_len == sizeof(RelayRequestPayload)) {
                const RelayRequestPayload* relay_req = 
                    reinterpret_cast<const RelayRequestPayload*>(payload);
                Serial.printf("← Received BROADCAST_RELAY_REQ: RSSI=%.1f, SNR=%.1f, loss=%.1f%%\n",
                             relay_req->rssi, relay_req->snr, relay_req->packet_loss);
                handleBinaryBroadcastRelayReq(relay_req);
            } else {
                Serial.printf("✗ BROADCAST_RELAY_REQ payload size mismatch: expected %d, got %d\n",
                             sizeof(RelayRequestPayload), payload_len);
                if (stats) stats->parse_errors++;
            }
            break;
        }
        
        case CMD_STATUS_REQUEST: {
            Serial.println("← Received STATUS_REQUEST");
            handleBinaryStatusRequest();
            break;
        }
        
        case CMD_START_RELAY_DISCOVERY: {
            if (payload_len == sizeof(StartRelayDiscoveryPayload)) {
                const StartRelayDiscoveryPayload* discovery = 
                    reinterpret_cast<const StartRelayDiscoveryPayload*>(payload);
                Serial.printf("← Received START_RELAY_DISCOVERY: lat=%ld, lon=%ld, alt=%d, RSSI=%.1f\n",
                             discovery->own_lat, discovery->own_lon, discovery->own_alt, discovery->gcs_rssi);
                handleBinaryStartRelayDiscovery(discovery);
            } else {
                Serial.printf("✗ START_RELAY_DISCOVERY payload size mismatch: expected %d, got %d\n",
                             sizeof(StartRelayDiscoveryPayload), payload_len);
                if (stats) stats->parse_errors++;
            }
            break;
        }
        
        case CMD_RELAY_SELECTED: {
            if (payload_len == sizeof(RelaySelectedPayload)) {
                const RelaySelectedPayload* selected = 
                    reinterpret_cast<const RelaySelectedPayload*>(payload);
                Serial.printf("← Received RELAY_SELECTED: relay_id=%d, RSSI=%.1f, SNR=%.1f, score=%.1f\n",
                             selected->relay_id, selected->relay_rssi, selected->relay_snr, selected->relay_score);
                handleBinaryRelaySelected(selected);
            } else {
                Serial.printf("✗ RELAY_SELECTED payload size mismatch: expected %d, got %d\n",
                             sizeof(RelaySelectedPayload), payload_len);
                if (stats) stats->parse_errors++;
            }
            break;
        }
        
        case CMD_RELAY_ESTABLISHED: {
            if (payload_len == sizeof(RelayEstablishedPayload)) {
                const RelayEstablishedPayload* established = 
                    reinterpret_cast<const RelayEstablishedPayload*>(payload);
                Serial.printf("← Received RELAY_ESTABLISHED: relay_id=%d\n", established->relay_id);
                handleBinaryRelayEstablished(established);
            } else {
                Serial.printf("✗ RELAY_ESTABLISHED payload size mismatch: expected %d, got %d\n",
                             sizeof(RelayEstablishedPayload), payload_len);
                if (stats) stats->parse_errors++;
            }
            break;
        }
        
        case CMD_RELAY_LOST: {
            if (payload_len == sizeof(RelayLostPayload)) {
                const RelayLostPayload* lost = 
                    reinterpret_cast<const RelayLostPayload*>(payload);
                const char* reason_str = "UNKNOWN";
                switch (static_cast<RelayLostReason>(lost->reason)) {
                    case RELAY_LOST_HEARTBEAT_TIMEOUT: reason_str = "HEARTBEAT_TIMEOUT"; break;
                    case RELAY_LOST_LINK_QUALITY: reason_str = "LINK_QUALITY"; break;
                    case RELAY_LOST_REJECTION: reason_str = "REJECTION"; break;
                    case RELAY_LOST_GCS_RESTORED: reason_str = "GCS_RESTORED"; break;
                }
                Serial.printf("← Received RELAY_LOST: relay_id=%d, reason=%s\n", lost->relay_id, reason_str);
                handleBinaryRelayLost(lost);
            } else {
                Serial.printf("✗ RELAY_LOST payload size mismatch: expected %d, got %d\n",
                             sizeof(RelayLostPayload), payload_len);
                if (stats) stats->parse_errors++;
            }
            break;
        }
        
        case CMD_NONE:
            Serial.println("⚠ Received CMD_NONE");
            if (stats) stats->unknown_commands++;
            break;
            
        default:
            Serial.printf("⚠ Unknown command: 0x%02X\n", static_cast<uint8_t>(command));
            if (stats) stats->unknown_commands++;
            break;
    }
}

// ============================================================================
// DEBUG SUPPORT
// ============================================================================

/**
 * @brief Print packet bytes in hex format for debugging
 * 
 * Prints the raw bytes of a binary packet in a readable hex format,
 * including start byte, command, length, payload, and checksum.
 * 
 * @param packet_data Pointer to the raw packet buffer
 * @param total_len Total length of the packet in bytes
 * 
 * Requirements: 10.1, 10.2, 10.3
 */
inline void printPacketHex(const uint8_t* packet_data, uint16_t total_len) {
    if (!packet_data || total_len == 0) {
        Serial.println("✗ Cannot print packet: null or empty");
        return;
    }
    
    // Extract packet components for labeled output
    uint8_t start_byte = packet_data[0];
    uint8_t command = packet_data[1];
    uint16_t payload_len = 0;
    
    if (total_len >= 4) {
        payload_len = packet_data[2] | (packet_data[3] << 8);
    }
    
    // Print header
    Serial.println("┌─ Binary Packet (Hex) ─────────────────────────────");
    
    // Print start byte
    Serial.printf("│ Start:    0x%02X\n", start_byte);
    
    // Print command
    const char* cmd_name = "UNKNOWN";
    switch (static_cast<UartCommand>(command)) {
        case CMD_NONE: cmd_name = "NONE"; break;
        case CMD_INIT: cmd_name = "INIT"; break;
        case CMD_ACK: cmd_name = "ACK"; break;
        case CMD_RELAY_ACTIVATE: cmd_name = "RELAY_ACTIVATE"; break;
        case CMD_RELAY_TX: cmd_name = "RELAY_TX"; break;
        case CMD_RELAY_RX: cmd_name = "RELAY_RX"; break;
        case CMD_BRIDGE_TX: cmd_name = "BRIDGE_TX"; break;
        case CMD_BRIDGE_RX: cmd_name = "BRIDGE_RX"; break;
        case CMD_STATUS_REPORT: cmd_name = "STATUS_REPORT"; break;
        case CMD_BROADCAST_RELAY_REQ: cmd_name = "BROADCAST_RELAY_REQ"; break;
        case CMD_STATUS_REQUEST: cmd_name = "STATUS_REQUEST"; break;
    }
    Serial.printf("│ Command:  0x%02X (%s)\n", command, cmd_name);
    
    // Print length
    if (total_len >= 4) {
        Serial.printf("│ Length:   0x%02X%02X (%d bytes)\n", 
                     packet_data[3], packet_data[2], payload_len);
    }
    
    // Print payload
    if (payload_len > 0 && total_len >= 4 + payload_len) {
        Serial.print("│ Payload:  ");
        for (uint16_t i = 0; i < payload_len; i++) {
            Serial.printf("%02X ", packet_data[4 + i]);
            // Line wrap every 16 bytes for readability
            if ((i + 1) % 16 == 0 && i < payload_len - 1) {
                Serial.print("\n│           ");
            }
        }
        Serial.println();
    } else {
        Serial.println("│ Payload:  (none)");
    }
    
    // Print checksum
    if (total_len >= 6 + payload_len) {
        uint16_t checksum = packet_data[4 + payload_len] | 
                           (packet_data[4 + payload_len + 1] << 8);
        Serial.printf("│ Checksum: 0x%04X\n", checksum);
    }
    
    // Print raw bytes
    Serial.print("│ Raw:      ");
    for (uint16_t i = 0; i < total_len; i++) {
        Serial.printf("%02X ", packet_data[i]);
        // Line wrap every 16 bytes
        if ((i + 1) % 16 == 0 && i < total_len - 1) {
            Serial.print("\n│           ");
        }
    }
    Serial.println();
    
    Serial.printf("│ Total:    %d bytes\n", total_len);
    Serial.println("└───────────────────────────────────────────────────");
}

/**
 * @brief Print malformed packet bytes for debugging
 * 
 * Prints raw bytes of a malformed packet that failed validation,
 * useful for troubleshooting protocol issues.
 * 
 * @param packet_data Pointer to the raw packet buffer
 * @param bytes_received Number of bytes received before error
 * @param error_msg Description of the error
 * 
 * Requirements: 10.2, 10.5
 */
inline void printMalformedPacket(const uint8_t* packet_data, 
                                uint16_t bytes_received,
                                const char* error_msg) {
    if (!packet_data || bytes_received == 0) {
        Serial.println("✗ Cannot print malformed packet: null or empty");
        return;
    }
    
    Serial.println("┌─ MALFORMED PACKET ────────────────────────────────");
    Serial.printf("│ Error:    %s\n", error_msg ? error_msg : "Unknown error");
    Serial.printf("│ Bytes:    %d received\n", bytes_received);
    Serial.print("│ Raw:      ");
    
    for (uint16_t i = 0; i < bytes_received; i++) {
        Serial.printf("%02X ", packet_data[i]);
        // Line wrap every 16 bytes
        if ((i + 1) % 16 == 0 && i < bytes_received - 1) {
            Serial.print("\n│           ");
        }
    }
    Serial.println();
    Serial.println("└───────────────────────────────────────────────────");
}


// ============================================================================
// PROTOCOL COMPARISON LOGGING
// ============================================================================

/**
 * @brief Structure to track protocol comparison metrics
 * 
 * Used to compare JSON vs binary protocol performance in terms of
 * message size and transmission time.
 * 
 * Requirements: 1.3, 1.4, 7.3, 10.4
 */
struct ProtocolComparisonMetrics {
    uint32_t json_bytes;
    uint32_t binary_bytes;
    uint32_t json_time_us;
    uint32_t binary_time_us;
    const char* command_name;
    
    ProtocolComparisonMetrics() : 
        json_bytes(0), binary_bytes(0), 
        json_time_us(0), binary_time_us(0),
        command_name("") {}
};

/**
 * @brief Log protocol comparison for a specific command
 * 
 * Displays side-by-side comparison of JSON vs binary protocol
 * showing message size, transmission time, and savings percentage.
 * 
 * @param metrics Comparison metrics structure
 * 
 * Requirements: 1.3, 1.4, 7.3, 10.4
 */
inline void logProtocolComparison(const ProtocolComparisonMetrics& metrics) {
    Serial.println("┌─ Protocol Comparison ─────────────────────────────");
    Serial.printf("│ Command:  %s\n", metrics.command_name);
    Serial.println("├───────────────────────────────────────────────────");
    
    // Message size comparison
    Serial.println("│ MESSAGE SIZE:");
    Serial.printf("│   JSON:    %lu bytes\n", metrics.json_bytes);
    Serial.printf("│   Binary:  %lu bytes\n", metrics.binary_bytes);
    
    if (metrics.json_bytes > 0) {
        float size_savings = 100.0f * (1.0f - (float)metrics.binary_bytes / (float)metrics.json_bytes);
        Serial.printf("│   Savings: %.1f%%\n", size_savings);
    }
    
    Serial.println("├───────────────────────────────────────────────────");
    
    // Transmission time comparison
    Serial.println("│ TRANSMISSION TIME:");
    Serial.printf("│   JSON:    %lu µs\n", metrics.json_time_us);
    Serial.printf("│   Binary:  %lu µs\n", metrics.binary_time_us);
    
    if (metrics.json_time_us > 0) {
        float time_speedup = (float)metrics.json_time_us / (float)metrics.binary_time_us;
        Serial.printf("│   Speedup: %.1fx faster\n", time_speedup);
    }
    
    Serial.println("└───────────────────────────────────────────────────");
}

/**
 * @brief Calculate and log aggregate protocol statistics
 * 
 * Displays overall statistics comparing JSON vs binary protocol
 * across all messages sent/received.
 * 
 * @param json_total_bytes Total bytes sent using JSON protocol
 * @param binary_total_bytes Total bytes sent using binary protocol
 * @param json_total_time_us Total time spent in JSON serialization (microseconds)
 * @param binary_total_time_us Total time spent in binary serialization (microseconds)
 * @param message_count Number of messages compared
 * 
 * Requirements: 1.3, 1.4, 7.3, 10.4
 */
inline void logAggregateComparison(uint32_t json_total_bytes, 
                                  uint32_t binary_total_bytes,
                                  uint32_t json_total_time_us,
                                  uint32_t binary_total_time_us,
                                  uint32_t message_count) {
    Serial.println("╔═══════════════════════════════════════════════════╗");
    Serial.println("║       AGGREGATE PROTOCOL COMPARISON               ║");
    Serial.println("╠═══════════════════════════════════════════════════╣");
    Serial.printf("║ Messages:     %lu\n", message_count);
    Serial.println("╠═══════════════════════════════════════════════════╣");
    
    // Total bytes comparison
    Serial.println("║ TOTAL BYTES:");
    Serial.printf("║   JSON:       %lu bytes\n", json_total_bytes);
    Serial.printf("║   Binary:     %lu bytes\n", binary_total_bytes);
    
    if (json_total_bytes > 0) {
        uint32_t bytes_saved = json_total_bytes - binary_total_bytes;
        float size_savings = 100.0f * (1.0f - (float)binary_total_bytes / (float)json_total_bytes);
        Serial.printf("║   Saved:      %lu bytes (%.1f%%)\n", bytes_saved, size_savings);
    }
    
    Serial.println("╠═══════════════════════════════════════════════════╣");
    
    // Average message size
    if (message_count > 0) {
        uint32_t json_avg = json_total_bytes / message_count;
        uint32_t binary_avg = binary_total_bytes / message_count;
        
        Serial.println("║ AVERAGE MESSAGE SIZE:");
        Serial.printf("║   JSON:       %lu bytes\n", json_avg);
        Serial.printf("║   Binary:     %lu bytes\n", binary_avg);
        
        if (json_avg > 0) {
            float avg_savings = 100.0f * (1.0f - (float)binary_avg / (float)json_avg);
            Serial.printf("║   Savings:    %.1f%%\n", avg_savings);
        }
    }
    
    Serial.println("╠═══════════════════════════════════════════════════╣");
    
    // Total time comparison
    Serial.println("║ TOTAL TIME:");
    Serial.printf("║   JSON:       %lu µs (%.2f ms)\n", 
                 json_total_time_us, json_total_time_us / 1000.0f);
    Serial.printf("║   Binary:     %lu µs (%.2f ms)\n", 
                 binary_total_time_us, binary_total_time_us / 1000.0f);
    
    if (json_total_time_us > 0) {
        uint32_t time_saved = json_total_time_us - binary_total_time_us;
        float time_speedup = (float)json_total_time_us / (float)binary_total_time_us;
        Serial.printf("║   Saved:      %lu µs (%.2f ms)\n", 
                     time_saved, time_saved / 1000.0f);
        Serial.printf("║   Speedup:    %.1fx faster\n", time_speedup);
    }
    
    Serial.println("╠═══════════════════════════════════════════════════╣");
    
    // Average time per message
    if (message_count > 0) {
        uint32_t json_avg_time = json_total_time_us / message_count;
        uint32_t binary_avg_time = binary_total_time_us / message_count;
        
        Serial.println("║ AVERAGE TIME PER MESSAGE:");
        Serial.printf("║   JSON:       %lu µs\n", json_avg_time);
        Serial.printf("║   Binary:     %lu µs\n", binary_avg_time);
        
        if (json_avg_time > 0) {
            float avg_speedup = (float)json_avg_time / (float)binary_avg_time;
            Serial.printf("║   Speedup:    %.1fx faster\n", avg_speedup);
        }
    }
    
    Serial.println("╚═══════════════════════════════════════════════════╝");
}

/**
 * @brief Helper function to estimate JSON message size
 * 
 * Provides estimated JSON message sizes for comparison purposes.
 * These are typical sizes based on the current JSON implementation.
 * 
 * @param command Command type
 * @param payload_len Payload length in bytes
 * @return Estimated JSON message size in bytes
 * 
 * Requirements: 1.3, 7.3, 10.4
 */
inline uint32_t estimateJsonSize(UartCommand command, uint16_t payload_len) {
    // Base JSON overhead: {"cmd":"","len":0,"data":""}
    uint32_t base_overhead = 30;
    
    switch (command) {
        case CMD_INIT:
            // {"cmd":"INIT","mode":"FREQUENCY_BRIDGE","primary":915.0,"secondary":902.0,"timestamp":12345}
            return 85;
            
        case CMD_ACK:
            // {"cmd":"ACK"}
            return 13;
            
        case CMD_RELAY_ACTIVATE:
            // {"cmd":"RELAY_ACTIVATE","activate":true}
            return 40;
            
        case CMD_RELAY_TX:
        case CMD_RELAY_RX:
            // {"cmd":"RELAY_TX","len":50,"data":"ABCD...","rssi":-80.0,"snr":10.0}
            // Hex encoding doubles the data size
            return base_overhead + 50 + (payload_len * 2);
            
        case CMD_BRIDGE_TX:
        case CMD_BRIDGE_RX:
            // {"cmd":"BRIDGE_TX","sysid":1,"len":50,"data":"ABCD...","rssi":-80.0,"snr":10.0}
            // Hex encoding doubles the data size
            return base_overhead + 60 + (payload_len * 2);
            
        case CMD_STATUS_REPORT:
            // Large JSON with many fields
            return 250;
            
        case CMD_BROADCAST_RELAY_REQ:
            // {"cmd":"BROADCAST_RELAY_REQ","rssi":-80.0,"snr":10.0,"packet_loss":5.0}
            return 75;
            
        case CMD_STATUS_REQUEST:
            // {"cmd":"STATUS_REQUEST"}
            return 25;
            
        case CMD_START_RELAY_DISCOVERY:
            // {"cmd":"START_RELAY_DISCOVERY","lat":37123456,"lon":-122456789,"alt":100,"rssi":-80.0,"snr":10.0,"loss":5.0}
            return 110;
            
        case CMD_RELAY_SELECTED:
            // {"cmd":"RELAY_SELECTED","relay_id":2,"rssi":-75.0,"snr":8.0,"score":78.5}
            return 80;
            
        case CMD_RELAY_ESTABLISHED:
            // {"cmd":"RELAY_ESTABLISHED","relay_id":2}
            return 45;
            
        case CMD_RELAY_LOST:
            // {"cmd":"RELAY_LOST","relay_id":2,"reason":"HEARTBEAT_TIMEOUT"}
            return 65;
            
        default:
            return base_overhead + payload_len;
    }
}
