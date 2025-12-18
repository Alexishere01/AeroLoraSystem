#include "DualBandTransport.h"

DualBandTransport::DualBandTransport(ESPNowTransport* espnow, AeroLoRaProtocol* lora, FlightLogger* logger)
    : _espnow(espnow), _lora(lora), _logger(logger), _my_node_id(0), 
      _last_espnow_state(false), _last_stats_log_time(0) {
    
    // Initialize deduplication tracking
    for (uint16_t i = 0; i < 256; i++) {
        _last_seq_num[i] = 0xFF;  // Invalid initial value
    }
    
    // Initialize statistics
    memset(&_stats, 0, sizeof(DualBandStats));
}

bool DualBandTransport::begin(uint8_t node_id) {
    _my_node_id = node_id;
    
    // Both transports should already be initialized
    // This method just sets up the dual-band coordination
    
    #if DEBUG_LOGGING
    Serial.println("[DualBand] Transport manager initialized");
    Serial.printf("[DualBand] Node ID: %d\n", _my_node_id);
    #endif
    
    return true;
}

uint8_t DualBandTransport::extractMavlinkMsgId(uint8_t* data, uint8_t len) {
    if (len < 6) {
        return 0xFF;  // Invalid packet
    }
    
    // Check for MAVLink v1 (0xFE) or v2 (0xFD)
    if (data[0] == 0xFE) {
        // MAVLink v1: msgId at byte 5
        return data[5];
    } else if (data[0] == 0xFD) {
        // MAVLink v2: msgId at bytes 9-11 (24-bit), we use low byte
        if (len >= 10) {
            return data[9];
        }
    }
    
    return 0xFF;  // Invalid or unknown format
}

uint8_t DualBandTransport::extractMavlinkSysId(uint8_t* data, uint8_t len) {
    if (len < 4) {
        return 0xFF;  // Invalid packet
    }
    
    // Check for MAVLink v1 (0xFE) or v2 (0xFD)
    if (data[0] == 0xFE) {
        // MAVLink v1: sysId at byte 3
        return data[3];
    } else if (data[0] == 0xFD) {
        // MAVLink v2: sysId at byte 5
        if (len >= 6) {
            return data[5];
        }
    }
    
    return 0xFF;  // Invalid or unknown format
}

uint8_t DualBandTransport::extractMavlinkSeqNum(uint8_t* data, uint8_t len) {
    if (len < 3) {
        return 0xFF;  // Invalid packet
    }
    
    // Check for MAVLink v1 (0xFE) or v2 (0xFD)
    if (data[0] == 0xFE) {
        // MAVLink v1: seq at byte 2
        return data[2];
    } else if (data[0] == 0xFD) {
        // MAVLink v2: seq at byte 4
        if (len >= 5) {
            return data[4];
        }
    }
    
    return 0xFF;  // Invalid or unknown format
}

bool DualBandTransport::isDuplicate(uint8_t sysId, uint8_t seqNum) {
    // Handle sequence number wraparound
    // MAVLink sequence numbers are 8-bit (0-255)
    
    if (_last_seq_num[sysId] == 0xFF) {
        // First packet from this system - not a duplicate
        _last_seq_num[sysId] = seqNum;
        return false;
    }
    
    // Calculate sequence distance (handles wraparound)
    uint8_t seq_distance = (seqNum - _last_seq_num[sysId]) & 0xFF;
    
    if (seq_distance == 0) {
        // Exact duplicate
        return true;
    } else if (seq_distance < 128) {
        // New packet (forward sequence)
        _last_seq_num[sysId] = seqNum;
        return false;
    } else {
        // Old packet (backward sequence) or wraparound
        // Keep it to handle wraparound case
        _last_seq_num[sysId] = seqNum;
        return false;
    }
}

bool DualBandTransport::send(uint8_t* data, uint8_t len, uint8_t dest_id) {
    bool espnow_sent = false;
    bool lora_sent = false;
    
    // Extract MAVLink message ID for filtering
    uint8_t msgId = extractMavlinkMsgId(data, len);
    
    // Always try ESP-NOW (even if peer not yet marked reachable)
    // This allows the first packet to establish the connection
    espnow_sent = _espnow->send(data, len);
    if (espnow_sent) {
        _stats.espnow_packets_sent++;
    } else {
        _stats.espnow_send_failures++;
    }
    
    // Add 5ms inter-transport spacing to prevent power supply voltage drop
    // when both radios transmit in quick succession
    // OPTIMIZED: Only delay if we're about to transmit on LoRa too
    bool will_use_lora = _filter.isEssential(msgId);
    if (espnow_sent && will_use_lora) {
        delay(5);
    }
    
    // Send over LoRa only if message is essential
    // CSMA/CA is handled by AeroLoRaProtocol layer
    if (_filter.isEssential(msgId)) {
        lora_sent = _lora->send(data, len, false, dest_id);
        if (lora_sent) {
            _stats.lora_packets_sent++;
        }
    } else {
        // Non-essential message filtered from LoRa
        _stats.lora_filtered_messages++;
    }
    
    // Success if either transport succeeded
    return espnow_sent || lora_sent;
}

uint8_t DualBandTransport::receive(uint8_t* buffer, uint8_t max_len) {
    uint8_t rxLen = 0;
    
    // Try ESP-NOW first (higher priority for close-range)
    if (_espnow->available()) {
        rxLen = _espnow->receive(buffer, max_len);
        
        if (rxLen > 0) {
            // Extract sequence info for deduplication
            uint8_t sysId = extractMavlinkSysId(buffer, rxLen);
            uint8_t seqNum = extractMavlinkSeqNum(buffer, rxLen);
            
            if (sysId != 0xFF && seqNum != 0xFF) {
                if (isDuplicate(sysId, seqNum)) {
                    // Duplicate packet - drop it
                    _stats.duplicate_packets_dropped++;
                    return 0;  // No data
                }
            }
            
            _stats.espnow_packets_received++;
            
            /*
            if (_logger) {
                _logger->logPacket(
                    seqNum,
                    extractMavlinkMsgId(buffer, rxLen),
                    sysId,
                    _espnow->getLastRSSI(),
                    0, false,
                    "RX_ESPNOW",
                    rxLen,
                    millis(),
                    0, 0
                );
            }
            */
            
            return rxLen;
        }
    }
    
    // Try LoRa
    if (_lora->available()) {
        rxLen = _lora->receive(buffer, max_len);
        
        if (rxLen > 0) {
            // Extract sequence info for deduplication
            uint8_t sysId = extractMavlinkSysId(buffer, rxLen);
            uint8_t seqNum = extractMavlinkSeqNum(buffer, rxLen);
            
            if (sysId != 0xFF && seqNum != 0xFF) {
                if (isDuplicate(sysId, seqNum)) {
                    // Duplicate packet - drop it
                    _stats.duplicate_packets_dropped++;
                    return 0;  // No data
                }
            }
            
            _stats.lora_packets_received++;
            return rxLen;
        }
    }
    
    return 0;  // No data available
}

bool DualBandTransport::isESPNowAvailable() {
    return _espnow->isPeerReachable();
}

bool DualBandTransport::isLoRaAvailable() {
    // LoRa is always available if initialized
    // (No peer reachability concept for LoRa)
    return true;
}

DualBandStats DualBandTransport::getStats() {
    // Update ESP-NOW stats
    _stats.espnow_peer_reachable = _espnow->isPeerReachable();
    _stats.espnow_last_rssi = _espnow->getLastRSSI();
    
    // Update LoRa stats from AeroLoRaProtocol
    AeroLoRaStats loraStats = _lora->getStats();
    _stats.lora_avg_rssi = loraStats.avg_rssi;
    
    // Update filter stats
    _stats.lora_filtered_messages = _filter.getFilteredCount();
    
    return _stats;
}

void DualBandTransport::resetStats() {
    memset(&_stats, 0, sizeof(DualBandStats));
    _filter.resetStats();
    _lora->resetStats();
    // Note: ESPNowTransport doesn't have resetStats() method
}

void DualBandTransport::process() {
    // Process LoRa queue
    _lora->process();
    
    // Track ESP-NOW link state transitions
    bool current_espnow_state = _espnow->isPeerReachable();
    
    if (current_espnow_state != _last_espnow_state) {
        // Link state changed
        if (current_espnow_state) {
            // LoRa -> ESP-NOW transition
            _stats.lora_to_espnow_transitions++;
            #if DEBUG_LOGGING
            Serial.println("[DualBand] Link transition: LoRa-only -> ESP-NOW available");
            #endif
            
            // Log transition to flight log (Requirement 5.3)
            if (_logger) {
                _logger->logPacket(
                    0,                              // seq (not applicable)
                    0,                              // msgId (not applicable)
                    _my_node_id,                    // sysId
                    _espnow->getLastRSSI(),         // RSSI
                    0.0,                            // SNR (not applicable for ESP-NOW)
                    false,                          // relay not active
                    "ESPNOW_IN_RANGE",              // event
                    0,                              // packet size
                    millis(),                       // timestamp
                    0,                              // queue depth
                    0                               // errors
                );
            }
        } else {
            // ESP-NOW -> LoRa transition
            _stats.espnow_to_lora_transitions++;
            _stats.espnow_peer_unreachable_count++;
            #if DEBUG_LOGGING
            Serial.println("[DualBand] Link transition: ESP-NOW lost -> LoRa-only");
            #endif
            
            // Log transition to flight log (Requirement 5.3)
            if (_logger) {
                _logger->logPacket(
                    0,                              // seq (not applicable)
                    0,                              // msgId (not applicable)
                    _my_node_id,                    // sysId
                    _espnow->getLastRSSI(),         // Last known RSSI
                    0.0,                            // SNR (not applicable for ESP-NOW)
                    false,                          // relay not active
                    "ESPNOW_OUT_OF_RANGE",          // event
                    0,                              // packet size
                    millis(),                       // timestamp
                    0,                              // queue depth
                    0                               // errors
                );
            }
        }
        
        _stats.last_transition_timestamp = millis();
        _last_espnow_state = current_espnow_state;
    }
    
    // Periodic statistics logging (every 10 seconds) - Requirements 5.4, 5.5
    if (_logger && (millis() - _last_stats_log_time >= 10000)) {
        logStatistics();
        _last_stats_log_time = millis();
    }
}

void DualBandTransport::setLogger(FlightLogger* logger) {
    _logger = logger;
    #if DEBUG_LOGGING
    Serial.println("[DualBand] Flight logger attached");
    #endif
}

void DualBandTransport::logStatistics() {
    if (!_logger) return;
    
    // Get current statistics
    DualBandStats stats = getStats();
    
    // Log ESP-NOW link status (Requirement 5.3, 5.5)
    _logger->logPacket(
        0,                                  // seq (not applicable)
        0,                                  // msgId (not applicable)
        _my_node_id,                        // sysId
        stats.espnow_last_rssi,             // ESP-NOW RSSI
        0.0,                                // SNR (not applicable)
        false,                              // relay not active
        stats.espnow_peer_reachable ? "ESPNOW_STATUS_REACHABLE" : "ESPNOW_STATUS_UNREACHABLE",
        0,                                  // packet size
        millis(),                           // timestamp
        0,                                  // queue depth
        stats.espnow_send_failures          // ESP-NOW send failures as error count
    );
    
    // Log LoRa link status (Requirement 5.5)
    _logger->logPacket(
        0,                                  // seq (not applicable)
        0,                                  // msgId (not applicable)
        _my_node_id,                        // sysId
        stats.lora_avg_rssi,                // LoRa RSSI
        0.0,                                // SNR (could be added from LoRa stats)
        false,                              // relay not active
        "LORA_STATUS",                      // event
        0,                                  // packet size
        millis(),                           // timestamp
        0,                                  // queue depth
        0                                   // errors
    );
    
    // Log message filter statistics (Requirement 5.4, 5.5)
    _logger->logPacket(
        0,                                  // seq (not applicable)
        0,                                  // msgId (not applicable)
        _my_node_id,                        // sysId
        0.0,                                // RSSI (not applicable)
        0.0,                                // SNR (not applicable)
        false,                              // relay not active
        "FILTER_STATS",                     // event
        stats.lora_filtered_messages,       // Use packet_size field for filtered count
        millis(),                           // timestamp
        0,                                  // queue depth
        0                                   // errors
    );
    
    // Log deduplication statistics (Requirement 5.5)
    _logger->logPacket(
        0,                                  // seq (not applicable)
        0,                                  // msgId (not applicable)
        _my_node_id,                        // sysId
        0.0,                                // RSSI (not applicable)
        0.0,                                // SNR (not applicable)
        false,                              // relay not active
        "DEDUP_STATS",                      // event
        stats.duplicate_packets_dropped,    // Use packet_size field for duplicate count
        millis(),                           // timestamp
        0,                                  // queue depth
        0                                   // errors
    );
    
    // Log link transition counts (Requirement 5.5)
    _logger->logPacket(
        0,                                  // seq (not applicable)
        0,                                  // msgId (not applicable)
        _my_node_id,                        // sysId
        0.0,                                // RSSI (not applicable)
        0.0,                                // SNR (not applicable)
        false,                              // relay not active
        "TRANSITION_STATS",                 // event
        stats.espnow_to_lora_transitions,   // Use packet_size for ESP-NOW->LoRa count
        millis(),                           // timestamp
        stats.lora_to_espnow_transitions,   // Use queue_depth for LoRa->ESP-NOW count
        0                                   // errors
    );
    
    // Log packet counts for both transports (Requirement 5.5)
    _logger->logPacket(
        0,                                  // seq (not applicable)
        0,                                  // msgId (not applicable)
        _my_node_id,                        // sysId
        0.0,                                // RSSI (not applicable)
        0.0,                                // SNR (not applicable)
        false,                              // relay not active
        "PACKET_COUNTS",                    // event
        stats.espnow_packets_sent,          // Use packet_size for ESP-NOW TX count
        millis(),                           // timestamp
        stats.espnow_packets_received,      // Use queue_depth for ESP-NOW RX count
        0                                   // errors
    );
    
    _logger->logPacket(
        0,                                  // seq (not applicable)
        0,                                  // msgId (not applicable)
        _my_node_id,                        // sysId
        0.0,                                // RSSI (not applicable)
        0.0,                                // SNR (not applicable)
        false,                              // relay not active
        "LORA_PACKET_COUNTS",               // event
        stats.lora_packets_sent,            // Use packet_size for LoRa TX count
        millis(),                           // timestamp
        stats.lora_packets_received,        // Use queue_depth for LoRa RX count
        0                                   // errors
    );
}

void DualBandTransport::logFilterStatistics() {
    if (!_logger) return;
    
    // Log per-message-ID filter statistics (Requirement 5.4)
    // This provides detailed insight into which message types are being filtered
    
    // Log the top filtered message IDs (to avoid logging 256 entries)
    // We'll log any message ID that has been filtered at least once
    for (uint16_t msgId = 0; msgId < 256; msgId++) {
        uint32_t count = _filter.getFilteredCount((uint8_t)msgId);
        
        if (count > 0) {
            _logger->logPacket(
                0,                          // seq (not applicable)
                (uint8_t)msgId,             // The message ID that was filtered
                _my_node_id,                // sysId
                0.0,                        // RSSI (not applicable)
                0.0,                        // SNR (not applicable)
                false,                      // relay not active
                "FILTER_MSG_ID",            // event
                count,                      // Use packet_size for filtered count
                millis(),                   // timestamp
                0,                          // queue depth
                0                           // errors
            );
        }
    }
}
