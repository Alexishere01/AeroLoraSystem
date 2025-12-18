/**
 * AeroLoRa Ground Station Bridge
 * 
 * Connects QGroundControl to drone via AeroLoRa protocol over LoRa radio.
 * 
 * Features:
 * - Hardware CRC error detection (SX1262 radio chip)
 * - Three-tier priority queuing (critical commands, important telemetry, routine telemetry)
 * - Automatic staleness detection (drops old packets)
 * - MAVLink reliability (command ACKs handled by MAVLink, not transport layer)
 * - Link quality monitoring (RSSI, SNR)
 * 
 * Protocol Design:
 * - Minimal overhead: 2 bytes per packet (header + length)
 * - Hardware CRC: Radio automatically validates packets before interrupt
 * - Priority-based: Commands never blocked by telemetry streams
 * - No ACK/NACK: MAVLink handles reliability at application layer
 * - No retries: Packets sent once only (MAVLink retries commands if needed)
 * 
 * TDMA (Time Division Multiple Access):
 * - Currently disabled for testing (always transmit)
 * - Future: Ground uses ODD slots (40, 120, 200ms...)
 * - Future: Drone uses EVEN slots (0, 80, 160ms...)
 */

#include <Arduino.h>
#include <RadioLib.h>
#include <SPI.h>
#include <U8g2lib.h>
#include <Wire.h>
#include "AeroLoRaProtocol.h"
#include "DualBandTransport.h"

// ═══════════════════════════════════════════════════════════════════
// SAFE MODE DEBUGGING
// ═══════════════════════════════════════════════════════════════════
// Set to 1 to disable ALL non-essential subsystems (Display, Radio, LED patterns)
// This isolates the crash to the bare minimum (RTOS + Heartbeat)
#define SAFE_MODE 0
#include "ESPNowTransport.h"
#include "esp_wifi.h"  // For WiFi channel debugging

#ifdef ENABLE_FLIGHT_LOGGER
#include "flight_logger.h"
#endif

// ═══════════════════════════════════════════════════════════════════
// PIN DEFINITIONS - Heltec WiFi LoRa 32 (V3)
// ═══════════════════════════════════════════════════════════════════
#define LORA_SCK         9
#define LORA_MISO        11
#define LORA_MOSI        10
#define LORA_CS          8
#define LORA_RST         12
#define LORA_DIO1        14
#define LORA_BUSY        13
#define LED_PIN          35

// OLED Display (I2C) - Heltec V3 pins from factory example
#define OLED_SDA         17
#define OLED_SCL         18
#define OLED_RST         21
#define VEXT_PIN         36  // Power control for display

// ═══════════════════════════════════════════════════════════════════
// RADIO CONFIGURATION
// ═══════════════════════════════════════════════════════════════════
#ifndef FREQ_PRIMARY
#define FREQ_PRIMARY 930.0 // Default to 930.0 if not defined
#endif
#define FREQ_MHZ            FREQ_PRIMARY   // Use build flag or default
#define LORA_BANDWIDTH      500.0   // 500 kHz for maximum speed
#define LORA_SPREAD_FACTOR  6       // SF7 for speed
#define LORA_CODING_RATE    5       // 4/5 coding rate
#define LORA_SYNC_WORD      0x34    // Private network
#define LORA_TX_POWER       4        // 4 dBm (~2.5 mW) - reduced to make jammer more effective

// ═══════════════════════════════════════════════════════════════════
// PROTOCOL CONFIGURATION
// ═══════════════════════════════════════════════════════════════════
#define MAVLINK_SERIAL_BAUD     57600
#define TDMA_SLOT_DURATION_MS   40      // 40ms slots
#define GROUND_SLOT_OFFSET      1       // ODD slots (40, 120, 200ms...)

// MAVLink message IDs (for reference)
// Note: Priority is now automatically determined by the protocol layer
// based on message ID. These definitions are kept for reference only.
#define MAVLINK_MSG_ID_COMMAND_LONG     76
#define MAVLINK_MSG_ID_COMMAND_ACK      77
#define MAVLINK_MSG_ID_SET_MODE         11
#define MAVLINK_MSG_ID_MISSION_ITEM     39
#define MAVLINK_MSG_ID_MISSION_COUNT    44
#define MAVLINK_MSG_ID_PARAM_SET        23

// ═══════════════════════════════════════════════════════════════════
// GLOBAL OBJECTS
// ═══════════════════════════════════════════════════════════════════
SX1262 radio = new Module(LORA_CS, LORA_DIO1, LORA_RST, LORA_BUSY);
AeroLoRaProtocol protocol(&radio, GROUND_SLOT_OFFSET, TDMA_SLOT_DURATION_MS);
U8G2_SSD1306_128X64_NONAME_F_HW_I2C display(U8G2_R0, OLED_RST, OLED_SCL, OLED_SDA);

// Dual-Band Transport Components
ESPNowTransport espnowTransport;
DualBandTransport dualBandTransport(&espnowTransport, &protocol);

// Drone MAC Address (configure per deployment)
// TODO: Move to EEPROM/Preferences for runtime configuration
#ifdef FREQ_902MHZ_MODE
uint8_t drone_mac[6] = {0xF0, 0xF5, 0xBD, 0x4F, 0xA6, 0x98};  // Drone2 Secondary (Relay) MAC
#else
uint8_t drone_mac[6] = {0x48, 0xCA, 0x43, 0x3A, 0xEF, 0x04};  // Drone1 actual MAC
#endif

// Buffers
uint8_t serialRxBuffer[256];
uint16_t serialRxIndex = 0;
unsigned long lastSerialRx = 0;

// Radio interrupt flag
volatile bool radioPacketReceived = false;

// LED debug patterns
unsigned long lastLedUpdate = 0;
uint8_t ledPattern = 0;  // 0=idle, 1=tx, 2=rx_good

// Statistics
unsigned long lastStatsprint = 0;
#define STATS_INTERVAL 10000  // Print stats every 10 seconds

#ifdef ENABLE_FLIGHT_LOGGER
// Flight logger instance
FlightLogger logger("/ground_log.csv");
#endif

// Display update
unsigned long lastDisplayUpdate = 0;
#define DISPLAY_INTERVAL 200  // Update display every 200ms

// Parameter sync statistics reporting
unsigned long lastParamSyncStats = 0;
#define PARAM_SYNC_STATS_INTERVAL 2000  // Print param sync stats every 2 seconds

// Queue metrics logging (Requirements 6.1, 6.2)
unsigned long lastQueueMetricsLog = 0;
#define QUEUE_METRICS_LOG_INTERVAL 5000  // Log queue metrics every 5 seconds

// Dual-band statistics printing
unsigned long lastDualBandStats = 0;
#define DUAL_BAND_STATS_INTERVAL 10000  // Print dual-band stats every 10 seconds

// Noise Floor Logging (Requirement for Jammer Analysis)
unsigned long lastNoiseFloorLog = 0;
#define NOISE_FLOOR_LOG_INTERVAL 200  // Log noise floor every 200ms (5Hz)

// ═══════════════════════════════════════════════════════════════════
// RADIO INTERRUPT
// ═══════════════════════════════════════════════════════════════════
void IRAM_ATTR onRadioReceive() {
    radioPacketReceived = true;
}

// ═══════════════════════════════════════════════════════════════════
// OLED DISPLAY UPDATE
// ═══════════════════════════════════════════════════════════════════
void updateDisplay() {
    DualBandStats stats = dualBandTransport.getStats();
    
    display.clearBuffer();
    display.setFont(u8g2_font_6x10_tf);
    
    // ESP-NOW DEBUG INFO
    char buf[32];
    
    // Line 1: Title
    display.drawStr(0, 10, "ESP-NOW DEBUG");
    
    // Line 2: Peer MAC
    sprintf(buf, "Peer:%02X:%02X:%02X", drone_mac[3], drone_mac[4], drone_mac[5]);
    display.drawStr(0, 22, buf);
    
    // Line 3: WiFi Channel
    uint8_t channel;
    wifi_second_chan_t second;
    esp_wifi_get_channel(&channel, &second);
    sprintf(buf, "Chan:%d", channel);
    display.drawStr(0, 34, buf);
    
    // Line 4: ESP-NOW Status
    if (stats.espnow_peer_reachable) {
        sprintf(buf, "REACH %ddBm", stats.espnow_last_rssi);
    } else {
        sprintf(buf, "OUT OF RANGE");
    }
    display.drawStr(0, 46, buf);
    
    // Line 5: Packet counts
    sprintf(buf, "TX:%lu RX:%lu", stats.espnow_packets_sent, stats.espnow_packets_received);
    display.drawStr(0, 58, buf);
    
    display.sendBuffer();
}

// ═══════════════════════════════════════════════════════════════════
// LED DEBUG PATTERNS
// ═══════════════════════════════════════════════════════════════════
void updateLedPattern() {
    unsigned long now = millis();
    
    switch(ledPattern) {
        case 1: // TX - rapid flash
            digitalWrite(LED_PIN, (now / 100) % 2);
            break;
            
        case 2: // RX good - solid for 500ms then off
            if (now - lastLedUpdate < 500) {
                digitalWrite(LED_PIN, HIGH);
            } else {
                digitalWrite(LED_PIN, LOW);
                ledPattern = 0;
            }
            break;
            
        default: // Idle - brief pulse every 2 seconds (heartbeat)
            digitalWrite(LED_PIN, ((now / 2000) % 2) && ((now % 2000) < 50));
            break;
    }
}

// ═══════════════════════════════════════════════════════════════════
// MAVLINK DETECTION
// ═══════════════════════════════════════════════════════════════════

int16_t findCompleteMavlinkPacket(uint8_t* buffer, uint16_t bufferLen) {
    if (bufferLen < 8) return 0;
    
    for (uint16_t i = 0; i < bufferLen; i++) {
        if (buffer[i] == 0xFE || buffer[i] == 0xFD) {
            uint16_t packetLen = 0;
            
            if (buffer[i] == 0xFE && (i + 1) < bufferLen) {
                packetLen = buffer[i + 1] + 8;
            } else if (buffer[i] == 0xFD && (i + 1) < bufferLen) {
                packetLen = buffer[i + 1] + 12;
                if ((i + 2) < bufferLen && (buffer[i + 2] & 0x01)) {
                    packetLen += 13;
                }
            }
            
            if (packetLen > 0 && (i + packetLen) <= bufferLen) {
                return i + packetLen;
            }
            
            if (packetLen > 0) {
                return 0;  // Incomplete
            }
            
            return -1;  // Invalid
        }
    }
    
    if (bufferLen > 100) {
        return -1;  // Too much data without MAVLink marker
    }
    
    return 0;  // Wait for more data
}

// ═══════════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════════

void setup() {
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, HIGH);
    
    // Turn on Vext to power OLED display
    pinMode(VEXT_PIN, OUTPUT);
    digitalWrite(VEXT_PIN, LOW);  // LOW = ON for Vext
    delay(100);
    
    // Initialize OLED Display
    display.begin();
    display.clearBuffer();
    display.setFont(u8g2_font_6x10_tf);
    display.drawStr(0, 20, "AeroLoRa Ground");
    display.drawStr(0, 35, "Initializing...");
    display.sendBuffer();
    delay(500);
    
    // Initialize USB Serial for QGroundControl
    // WARNING: Do NOT print to Serial - it's used for MAVLink to QGC!
    Serial.begin(MAVLINK_SERIAL_BAUD);
    while (!Serial && millis() < 3000);
    
    // Initialize SPI
    SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI);
    
    // Initialize radio
    int state = radio.begin(FREQ_MHZ, LORA_BANDWIDTH, LORA_SPREAD_FACTOR,
                            LORA_CODING_RATE, LORA_SYNC_WORD, LORA_TX_POWER);
    
    if (state != RADIOLIB_ERR_NONE) {
        // Radio init failed - show on display and halt
        display.clearBuffer();
        display.drawStr(0, 20, "RADIO INIT FAIL");
        char buf[16];
        sprintf(buf, "Error: %d", state);
        display.drawStr(0, 35, buf);
        display.sendBuffer();
        
        while (true) {
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            delay(100);
        }
    }
    
    // Set up radio interrupt
    radio.setDio1Action(onRadioReceive);
    
    // Enable hardware CRC
    radio.setCRC(true);
    
    // Start receiving
    radio.startReceive();
    
    // Initialize protocol with NODE_GROUND identity
    protocol.begin(NODE_GROUND);
    
    // Initialize ESP-NOW Transport
    if (!espnowTransport.begin(drone_mac)) {
        // ESP-NOW init failed - show on display
        display.clearBuffer();
        display.drawStr(0, 20, "ESP-NOW FAILED");
        display.drawStr(0, 35, "LoRa only mode");
        display.sendBuffer();
        delay(2000);
    } else {
        // ESP-NOW init success - show MAC address on display briefly
        display.clearBuffer();
        display.setFont(u8g2_font_8x13_tf);
        display.drawStr(0, 15, "Ground MAC:");
        
        // Get MAC address and split across two lines
        String macStr = WiFi.macAddress();
        // First 3 bytes: XX:XX:XX
        String mac1 = macStr.substring(0, 8);
        // Last 3 bytes: XX:XX:XX
        String mac2 = macStr.substring(9);
        
        display.drawStr(0, 35, mac1.c_str());
        display.drawStr(0, 50, mac2.c_str());
        
        display.sendBuffer();
        delay(1000);  // Show MAC for 1 second only
    }
    
    // Initialize Dual-Band Transport
    if (!dualBandTransport.begin(NODE_GROUND)) {
        // Dual-band init failed - show on display and halt
        display.clearBuffer();
        display.drawStr(0, 20, "DUAL-BAND FAIL");
        display.drawStr(0, 35, "Check config");
        display.sendBuffer();
        
        while(true) {
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            delay(200);
        }
    }
    
#ifdef ENABLE_FLIGHT_LOGGER
    // Initialize flight logger
    if (logger.begin()) {
        Serial.println("[INFO] FlightLogger initialized successfully");
    } else {
        Serial.println("[ERROR] FlightLogger initialization failed!");
    }
#endif
    
    // Show ready on display (no Serial prints - MAVLink stream!)
    display.clearBuffer();
    display.drawStr(0, 10, "Ground Ready");
    display.drawStr(0, 25, "ESP-NOW: 2.4GHz");
    display.drawStr(0, 40, "LoRa: 930MHz");
    display.drawStr(0, 55, "Dual-Band Active");
    display.sendBuffer();
    delay(1000);
    
    digitalWrite(LED_PIN, LOW);
}

// ═══════════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════════

void loop() {
    unsigned long now = millis();
    
#if SAFE_MODE
    // Safe Mode: Simple heartbeat blink (1 Hz)
    // If this runs without crashing, the core system is stable.
    digitalWrite(LED_PIN, (now / 500) % 2);
    
    // Process NOTHING else.
    // No Display. No Radio. No Protocol.
    
#else
    // Update LED pattern
    updateLedPattern();
    
    // Update display (every 100ms)
    if (now - lastDisplayUpdate > 100) {
        updateDisplay();
        lastDisplayUpdate = now;
    }
    
    // Process dual-band transport (handles both ESP-NOW and LoRa)
    dualBandTransport.process();
    
    // Process LoRa protocol queue (retransmission, timeouts)
    protocol.process();
#endif
    

    
#if !SAFE_MODE
    // Handle radio reception
    if (radioPacketReceived) {
        radioPacketReceived = false;
        
        // Read packet
        uint8_t rxBuffer[256];
        int packetSize = radio.getPacketLength();
        if (packetSize > 0 && packetSize <= 256) {
            int state = radio.readData(rxBuffer, packetSize);
            
            if (state == RADIOLIB_ERR_NONE) {//no errors
                // Get RSSI and SNR
                float rssi = radio.getRSSI();
                float snr = radio.getSNR();
                
                // Pass to protocol for processing
                // Note: Hardware CRC already validated by radio before interrupt
                AeroLoRaPacket* packet = (AeroLoRaPacket*)rxBuffer;
                protocol.handleReceivedPacket(packet);
                
#ifdef ENABLE_FLIGHT_LOGGER
                // Log the RX event
                // Extract MAVLink fields from payload for logging
                uint8_t msgId = 0;
                uint8_t sysId = 0;
                uint32_t seq = 0;
                
                if (packet->payload_len >= 6) {
                    // MAVLink v1 or v2 packet
                    if (packet->payload[0] == 0xFE) {
                        // MAVLink v1: seq at byte 2, sysId at byte 3, msgId at byte 5
                        seq = packet->payload[2];
                        sysId = packet->payload[3];
                        msgId = packet->payload[5];
                    } else if (packet->payload[0] == 0xFD) {
                        // MAVLink v2: seq at byte 4, sysId at byte 5, msgId at bytes 7-9
                        seq = packet->payload[4];
                        sysId = packet->payload[5];
                        msgId = packet->payload[7];  // Low byte of message ID
                    }
                }
                
                AeroLoRaStats stats = protocol.getStats();
                uint8_t queueDepth = protocol.getQueueDepth();  // Get current queue depth (Requirement 6.1)
                logger.logPacket(
                    seq,                        // sequence_number
                    msgId,                      // message_id
                    sysId,                      // system_id
                    rssi,                       // rssi_dbm
                    snr,                        // snr_db
                    false,                      // relay_active (not used in direct mode)
                    "RX_LORA",                  // event
                    packetSize,                 // packet_size
                    0,                          // tx_timestamp (not available for RX)
                    queueDepth,                 // queue_depth (Requirement 6.1)
                    stats.packets_dropped       // errors
                );
#endif
            } else if (state == RADIOLIB_ERR_CRC_MISMATCH) {
#ifdef ENABLE_FLIGHT_LOGGER
                // Log CRC Error
                // Get RSSI and SNR for the corrupted packet
                float rssi = radio.getRSSI();
                float snr = radio.getSNR();
                
                logger.logPacket(
                    0,                          // sequence_number
                    0,                          // message_id
                    0,                          // system_id
                    rssi,                       // rssi_dbm
                    snr,                        // snr_db
                    false,                      // relay_active
                    "CRC_ERROR",                // event
                    packetSize,                 // packet_size
                    millis(),                   // tx_timestamp
                    0,                          // queue_depth
                    0                           // errors
                );
#endif
            }
        }
        
        // Return to RX mode
        radio.startReceive();
    }
    
    // Process dual-band transport (handles both ESP-NOW and LoRa)
    // dualBandTransport.process(); // REMOVED: Redundant (called above) and unsafe in Safe Mode
#endif
    
    // Handle serial data from QGC
    while (Serial.available() && serialRxIndex < sizeof(serialRxBuffer)) {
        uint8_t byte = Serial.read();
        
#ifdef ENABLE_FLIGHT_LOGGER
        // Check for DUMP command (simple text command)
        static char cmdBuffer[10];
        static uint8_t cmdIndex = 0;
        
        if (byte == '\n' || byte == '\r') {
            cmdBuffer[cmdIndex] = '\0';
            if (strcmp(cmdBuffer, "DUMP") == 0) {
                logger.dumpToSerial();
                // Serial.println("[DEBUG] DUMP command ignored (logger disabled)");
                cmdIndex = 0;
                continue;
            } else if (strcmp(cmdBuffer, "CLEAR") == 0) {
                logger.clearLog();
                cmdIndex = 0;
                continue;
            }
            cmdIndex = 0;
        } else if (cmdIndex < sizeof(cmdBuffer) - 1) {
            cmdBuffer[cmdIndex++] = byte;
        }
#endif
        
        serialRxBuffer[serialRxIndex++] = byte;
        lastSerialRx = now;
    }
    
    // Process serial buffer for complete MAVLink packets after timeout
    // Reduced from 40ms to 5ms for faster ESP-NOW message forwarding
    if (serialRxIndex > 0 && (now - lastSerialRx > 5)) {
        int16_t packetLen = findCompleteMavlinkPacket(serialRxBuffer, serialRxIndex);
        
        if (packetLen > 0) {
            // Complete packet found
            // Send via Dual-Band Transport to NODE_DRONE
            // Routing is automatic: all messages over ESP-NOW, essential only over LoRa
            if (dualBandTransport.send(serialRxBuffer, packetLen, NODE_DRONE)) {
                ledPattern = 1;  // TX pattern
                lastLedUpdate = now;
                
#ifdef ENABLE_FLIGHT_LOGGER
                // Log the TX event
                // Extract MAVLink fields for logging
                uint8_t msgId = (serialRxBuffer[0] == 0xFE) ? serialRxBuffer[5] : serialRxBuffer[7];
                uint8_t sysId = (serialRxBuffer[0] == 0xFE) ? serialRxBuffer[3] : serialRxBuffer[5];
                uint32_t seq = (serialRxBuffer[0] == 0xFE) ? serialRxBuffer[2] : serialRxBuffer[4];
                
                DualBandStats stats = dualBandTransport.getStats();
                uint8_t queueDepth = protocol.getQueueDepth();  // Get current queue depth (Requirement 6.1)
                
                // Determine event type based on ESP-NOW availability
                const char* event = "TX_LORA";
                if (stats.espnow_peer_reachable) {
                    event = "TX_ESPNOW";
                }

                // Only log LoRa packets to reduce load, OR rate-limited ESP-NOW packets
                bool shouldLog = false;
                
                if (strcmp(event, "TX_LORA") == 0) {
                    shouldLog = true; // Always log LoRa (low rate)
                } else {
                    // Rate limit ESP-NOW/DualBand logging to 5Hz
                    static unsigned long lastTxLog = 0;
                    if (millis() - lastTxLog > 200) {
                        shouldLog = true;
                        lastTxLog = millis();
                    }
                }

                if (shouldLog) {
                    logger.logPacket(
                        seq,                        // sequence_number
                        msgId,                      // message_id
                        sysId,                      // system_id
                        0.0,                        // rssi_dbm (not available at TX time)
                        0.0,                        // snr_db (not available at TX time)
                        false,                      // relay_active (not used in direct mode)
                        event,                      // event
                        packetLen,                  // packet_size
                        millis(),                   // tx_timestamp (current time)
                        queueDepth,                 // queue_depth (Requirement 6.1)
                        0                           // errors
                    );
                }
#endif
            }
            
            // Remove sent data from buffer
            if (packetLen < serialRxIndex) {
                memmove(serialRxBuffer, &serialRxBuffer[packetLen], 
                        serialRxIndex - packetLen);
                serialRxIndex -= packetLen;
            } else {
                serialRxIndex = 0;
            }
        } else if (packetLen == -1) {
            // Invalid data
            serialRxIndex = 0;
        }
    }
    
    // Handle received data from drone (deduplicated from both transports)
    uint8_t rxBuffer[256];
    uint8_t len = dualBandTransport.receive(rxBuffer, 255);  // Max 255 bytes (uint8_t limit)
    
    if (len > 0) {
        // Forward all received messages to QGC
        // Dual-band transport has already deduplicated packets
        Serial.write(rxBuffer, len);
        ledPattern = 2;  // RX pattern
        lastLedUpdate = now;
        
#ifdef ENABLE_FLIGHT_LOGGER
        // Log forwarding to QGC (RX via ESP-NOW or LoRa - deduplicated)
        // Since RX_LORA is logged separately, we can infer RX_ESPNOW if we log here
        // But dualBandTransport hides the source. 
        // Ideally, we should modify DualBandTransport to return the source.
        // For now, let's assume if it's here and NOT in RX_LORA, it's ESP-NOW?
        // No, RX_LORA logs on interrupt. This loop processes the queue.
        
        // Better approach: Log as "RX_DUALBAND" to indicate successful delivery to QGC
        // RATE LIMIT: Only log every 200ms (5Hz) to prevent crashing due to high ESP-NOW rate
        static unsigned long lastDualBandLog = 0;
        if (now - lastDualBandLog > 200) {
            uint8_t msgId = 0;
            uint8_t sysId = 0;
            uint32_t seq = 0;
            
            if (len >= 6) {
                 if (rxBuffer[0] == 0xFE) {
                    seq = rxBuffer[2];
                    sysId = rxBuffer[3];
                    msgId = rxBuffer[5];
                } else if (rxBuffer[0] == 0xFD) {
                    seq = rxBuffer[4];
                    sysId = rxBuffer[5];
                    msgId = rxBuffer[7];
                }
            }
            
            logger.logPacket(
                seq,
                msgId,
                sysId,
                0, 0, false,
                "RX_DUALBAND", // Indicates packet reached QGC (via either path)
                len,
                millis(),
                0, 0
            );
            lastDualBandLog = now;
        }
#endif
    }
    
    // Noise Floor Logging (Requirement for Jammer Analysis)
#ifdef ENABLE_FLIGHT_LOGGER
    if (now - lastNoiseFloorLog > NOISE_FLOOR_LOG_INTERVAL) {
        // Get instantaneous RSSI (best effort)
        float currentRssi = radio.getRSSI();
        
        // Log with special event "NOISE_FLOOR"
        // Use 0 for most fields as they are not applicable
        logger.logPacket(
            0,                          // sequence_number
            0,                          // message_id
            0,                          // system_id
            currentRssi,                // rssi_dbm
            0,                          // snr_db
            false,                      // relay_active
            "NOISE_FLOOR",              // event
            0,                          // packet_size
            millis(),                   // tx_timestamp (current time)
            protocol.getQueueDepth(),   // queue_depth
            0                           // errors
        );
        lastNoiseFloorLog = now;
    }
#endif

    // Periodic queue metrics logging (Requirements 6.2, 6.3, 6.4, 6.5)
#ifdef ENABLE_FLIGHT_LOGGER
    if (now - lastQueueMetricsLog > QUEUE_METRICS_LOG_INTERVAL) {
        QueueMetrics metrics = protocol.getQueueMetrics();
        logger.logQueueMetrics(
            metrics.tier0_depth,
            metrics.tier1_depth,
            metrics.tier2_depth,
            metrics.tier0_drops_full,
            metrics.tier0_drops_stale,
            metrics.tier1_drops_full,
            metrics.tier1_drops_stale,
            metrics.tier2_drops_full,
            metrics.tier2_drops_stale
        );
        lastQueueMetricsLog = now;
    }
#endif
    
    // Statistics are shown on OLED display (updateDisplay function)
    // No Serial prints - Serial is used for MAVLink to QGC!
}
