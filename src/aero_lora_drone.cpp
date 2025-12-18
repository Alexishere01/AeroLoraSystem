/**
 * AeroLoRa Drone/Air Bridge
 * 
 * Connects Autopilot to ground station via AeroLoRa protocol over LoRa radio.
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
 * - Future: Drone uses EVEN slots (0, 80, 160ms...)
 * - Future: Ground uses ODD slots (40, 120, 200ms...)
 */

#include <Arduino.h>
#include <RadioLib.h>
#include <SPI.h>
#include <U8g2lib.h>
#include <Wire.h>
#include "AeroLoRaProtocol.h"
#include "DualBandTransport.h"
#include "ESPNowTransport.h"

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

// UART for Flight Controller (Serial1)
#define FC_TX            45  // GPIO45 - connects to FC RX8
#define FC_RX            46  // GPIO46 - connects to FC TX8
// NOTE: Match this with FC SERIAL port baud rate (typically SERIAL1_BAUD parameter)
// Common values: 57600 (default), 115200 (faster), 921600 (highest)
#define FC_BAUD          115200  // Must match FC SERIAL port configuration!

// ═══════════════════════════════════════════════════════════════════
// RADIO CONFIGURATION
// ═══════════════════════════════════════════════════════════════════
#define FREQ_MHZ            930.0   // Changed from 915.0 to avoid ELRS interference
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
#define AIR_SLOT_OFFSET         0       // EVEN slots (0, 80, 160ms...)
#define ENABLE_BRIDGE_MODE      false   // Enable USB-UART bridge mode

// ═══════════════════════════════════════════════════════════════════
// GLOBAL OBJECTS
// ═══════════════════════════════════════════════════════════════════
SX1262 radio = new Module(LORA_CS, LORA_DIO1, LORA_RST, LORA_BUSY);
AeroLoRaProtocol protocol(&radio, AIR_SLOT_OFFSET, TDMA_SLOT_DURATION_MS);
U8G2_SSD1306_128X64_NONAME_F_HW_I2C display(U8G2_R0, OLED_RST, OLED_SCL, OLED_SDA);

// Dual-Band Transport Components
ESPNowTransport espnowTransport;
DualBandTransport dualBandTransport(&espnowTransport, &protocol);

// Ground Station MAC Address (configure per deployment)
// TODO: Move to EEPROM/Preferences for runtime configuration
// CORRECTED: Was 24:58:7C:5C:B9:C0, actual device is 24:58:7C:5B:3F:94
uint8_t qgc_mac[6] = {0x24, 0x58, 0x7C, 0x5B, 0x3F, 0x94};  // Ground Station actual MAC

#ifdef ENABLE_FLIGHT_LOGGER
FlightLogger logger("/drone1_log.csv");
#endif

// Buffers - UART Serial1 (Flight Controller)
uint8_t uartRxBuffer[256];
uint16_t uartRxIndex = 0;
unsigned long lastUartRx = 0;

// Message throttling
unsigned long lastHeartbeatSent = 0;
#define HEARTBEAT_INTERVAL 1000  // Only send heartbeat every 1 second

// UART Statistics
struct UartStats {
    uint32_t fc_packets_sent;      // Packets sent to FC via UART
    uint32_t fc_packets_received;  // Packets received from FC via UART
    uint32_t fc_bytes_sent;        // Total bytes sent to FC
    uint32_t fc_bytes_received;    // Total bytes received from FC
    unsigned long last_fc_rx;      // Timestamp of last FC RX activity
    bool fc_connected;             // True if FC activity detected recently
};

UartStats uartStats;

// Radio interrupt flag
volatile bool radioPacketReceived = false;

// Relay request flag (for weak link detection)
bool relayRequestActive = false;
unsigned long lastLinkQualityCheck = 0;
#define LINK_QUALITY_CHECK_INTERVAL 1000  // Check every 1 second

// LED debug patterns
unsigned long lastLedUpdate = 0;
uint8_t ledPattern = 0;  // 0=idle, 1=tx, 2=rx_good

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
    
    // Title
    display.drawStr(0, 10, "DUAL-BAND DRONE");
    display.drawLine(0, 12, 128, 12);
    
    // ESP-NOW status line
    char buf[32];
    if (stats.espnow_peer_reachable) {
        sprintf(buf, "ESP:%d/%d R:%d", 
                stats.espnow_packets_sent, 
                stats.espnow_packets_received,
                stats.espnow_last_rssi);
    } else {
        sprintf(buf, "ESP: OUT OF RANGE");
    }
    display.drawStr(0, 24, buf);
    
    // LoRa packet counts and filtered count
    sprintf(buf, "LoRa:%lu/%lu F:%lu", 
            stats.lora_packets_sent, 
            stats.lora_packets_received,
            stats.lora_filtered_messages);
    display.drawStr(0, 36, buf);
    
    // Flight Controller UART status
    sprintf(buf, "FC TX:%lu RX:%lu", uartStats.fc_packets_sent, uartStats.fc_packets_received);
    display.drawStr(0, 48, buf);
    
    // Warning if no FC activity for 5+ seconds
    if (!uartStats.fc_connected && uartStats.last_fc_rx > 0) {
        display.drawStr(0, 60, "FC: NO DATA");
    } else if (relayRequestActive) {
        // Show relay request status if active
        sprintf(buf, "RELAY REQ (%.0f)", stats.lora_avg_rssi);
        display.drawStr(0, 60, buf);
    } else {
        // Show deduplication count
        sprintf(buf, "DUP:%lu", stats.duplicate_packets_dropped);
        display.drawStr(0, 60, buf);
    }
    
    display.sendBuffer();
}

// ═══════════════════════════════════════════════════════════════════
// LINK QUALITY MONITORING
// ═══════════════════════════════════════════════════════════════════
/**
 * Check link quality and set relay request flag
 * 
 * Monitors average RSSI from LoRa statistics:
 * - If RSSI < -100 dBm: Set relay request flag (weak link)
 * - If RSSI > -90 dBm: Clear relay request flag (good link)
 * 
 * This implements hysteresis to prevent rapid toggling of relay mode.
 */
void checkLinkQuality() {
    DualBandStats stats = dualBandTransport.getStats();
    
    // Check if we have valid RSSI data (avg_rssi will be 0 if no packets received)
    if (stats.lora_avg_rssi != 0.0) {
        if (stats.lora_avg_rssi < -100.0) {
            // Weak link detected - request relay assistance
            if (!relayRequestActive) {
                relayRequestActive = true;
                Serial.print("[DRONE] Weak LoRa link detected (RSSI: ");
                Serial.print(stats.lora_avg_rssi);
                Serial.println(" dBm) - Relay request ACTIVE");
            }
        } else if (stats.lora_avg_rssi > -90.0) {
            // Good link restored - clear relay request
            if (relayRequestActive) {
                relayRequestActive = false;
                Serial.print("[DRONE] LoRa link quality restored (RSSI: ");
                Serial.print(stats.lora_avg_rssi);
                Serial.println(" dBm) - Relay request CLEARED");
            }
        }
        // Between -100 and -90 dBm: maintain current state (hysteresis)
    }
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
    
    // Skip garbage bytes at the start - look for MAVLink marker
    uint16_t startIdx = 0;
    while (startIdx < bufferLen && buffer[startIdx] != 0xFE && buffer[startIdx] != 0xFD) {
        startIdx++;
    }
    
    // If we skipped garbage, return negative offset to indicate how much to skip
    if (startIdx > 0 && startIdx < bufferLen) {
        // Found MAVLink marker after garbage - return negative to signal skip
        return -(int16_t)startIdx;
    }
    
    // No MAVLink marker found at all
    if (startIdx >= bufferLen) {
        return -1;  // All garbage, clear buffer
    }
    
    // MAVLink marker at start of buffer - check if complete packet
    if (buffer[0] == 0xFE || buffer[0] == 0xFD) {
        uint16_t packetLen = 0;
        
        if (buffer[0] == 0xFE && bufferLen > 1) {
            packetLen = buffer[1] + 8;
        } else if (buffer[0] == 0xFD && bufferLen > 1) {
            packetLen = buffer[1] + 12;
            if (bufferLen > 2 && (buffer[2] & 0x01)) {
                packetLen += 13;
            }
        }
        
        if (packetLen > 0 && packetLen <= bufferLen) {
            return packetLen;  // Complete packet
        }
        
        if (packetLen > 0) {
            return 0;  // Incomplete, wait for more data
        }
    }
    
    return -1;  // Invalid
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
    display.drawStr(0, 20, "AeroLoRa Drone");
    display.drawStr(0, 35, "Initializing...");
    display.sendBuffer();
    delay(500);
    
    // Initialize USB Serial for debugging
    Serial.begin(115200);
    delay(100);
    
    // Initialize Serial1 UART for Flight Controller
    Serial1.begin(FC_BAUD, SERIAL_8N1, FC_RX, FC_TX);
    delay(100);  // Allow UART to stabilize
    
    // Verify Serial1 initialization
    if (Serial1) {
        display.clearBuffer();
        display.setFont(u8g2_font_6x10_tf);
        display.drawStr(0, 20, "AeroLoRa Drone");
        display.drawStr(0, 35, "FC UART: OK");
        display.sendBuffer();
        delay(500);
    } else {
        display.clearBuffer();
        display.setFont(u8g2_font_6x10_tf);
        display.drawStr(0, 20, "AeroLoRa Drone");
        display.drawStr(0, 35, "FC UART: FAILED");
        display.sendBuffer();
        delay(1000);
    }
    
    // Initialize UART buffer variables
    uartRxIndex = 0;
    lastUartRx = 0;
    memset(uartRxBuffer, 0, sizeof(uartRxBuffer));
    
    // Initialize UART statistics
    uartStats.fc_packets_sent = 0;
    uartStats.fc_packets_received = 0;
    uartStats.fc_bytes_sent = 0;
    uartStats.fc_bytes_received = 0;
    uartStats.last_fc_rx = 0;
    uartStats.fc_connected = false;
    
    // Initialize SPI
    SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI);
    
    // Initialize radio
    int state = radio.begin(FREQ_MHZ, LORA_BANDWIDTH, LORA_SPREAD_FACTOR,
                            LORA_CODING_RATE, LORA_SYNC_WORD, LORA_TX_POWER);
    
    if (state != RADIOLIB_ERR_NONE) {
        // Radio initialization failed - blink LED rapidly
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
    
    // Initialize protocol with NODE_DRONE identity
    protocol.begin(NODE_DRONE);
    
    // Initialize ESP-NOW Transport (optional - can be disabled for jammer testing)
#ifndef DISABLE_ESPNOW
    #if DEBUG_LOGGING
    Serial.println("[DRONE] Initializing ESP-NOW...");
    #endif
    if (!espnowTransport.begin(qgc_mac)) {
        #if DEBUG_LOGGING
        Serial.println("[DRONE] ERROR: ESP-NOW initialization failed");
        Serial.println("[DRONE] Continuing with LoRa only");
        #endif
        
        display.clearBuffer();
        display.drawStr(0, 20, "ESP-NOW FAILED");
        display.drawStr(0, 35, "LoRa only mode");
        display.sendBuffer();
        delay(2000);
    } else {
        #if DEBUG_LOGGING
        Serial.println("[DRONE] ESP-NOW initialized successfully");
        Serial.print("[DRONE] Peer MAC: ");
        for (int i = 0; i < 6; i++) {
            Serial.printf("%02X", qgc_mac[i]);
            if (i < 5) Serial.print(":");
        }
        Serial.println();
        #endif
    }
#else
    // ESP-NOW explicitly disabled via compile flag (for jammer testing)
    #if DEBUG_LOGGING
    Serial.println("[DRONE] ESP-NOW DISABLED via DISABLE_ESPNOW flag");
    Serial.println("[DRONE] Operating in LoRa-only mode for jammer testing");
    #endif
    
    display.clearBuffer();
    display.drawStr(0, 20, "JAMMER TEST MODE");
    display.drawStr(0, 35, "ESP-NOW: DISABLED");
    display.drawStr(0, 50, "LoRa @ 930 MHz only");
    display.sendBuffer();
    delay(2000);
#endif
    
    // Initialize Dual-Band Transport
    #if DEBUG_LOGGING
    Serial.println("[DRONE] Initializing Dual-Band Transport...");
    #endif
    if (!dualBandTransport.begin(NODE_DRONE)) {
        #if DEBUG_LOGGING
        Serial.println("[DRONE] ERROR: Dual-Band Transport initialization failed");
        #endif
        while(true) {
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            delay(200);
        }
    }
    #if DEBUG_LOGGING
    Serial.println("[DRONE] Dual-Band Transport initialized successfully");
    #endif
    
    // Initialize Flight Logger
#ifdef ENABLE_FLIGHT_LOGGER
    #if DEBUG_LOGGING
    Serial.println("[DRONE] ENABLE_FLIGHT_LOGGER is defined");
    #endif
    if (logger.begin()) {
        #if DEBUG_LOGGING
        Serial.println("[DRONE] Flight logger initialized successfully");
        #endif
    } else {
        #if DEBUG_LOGGING
        Serial.println("[DRONE] ERROR: Flight logger initialization FAILED");
        #endif
    }
#else
    #if DEBUG_LOGGING
    Serial.println("[DRONE] WARNING: ENABLE_FLIGHT_LOGGER is NOT defined - no logging!");
    #endif
#endif
    
    // Show ready on display
    display.clearBuffer();
    display.drawStr(0, 10, "Dual-Band Drone");
    display.drawStr(0, 25, "READY!");
    display.drawStr(0, 40, "ESP-NOW: 2.4GHz");
    display.drawStr(0, 55, "LoRa: 915MHz SF7");
    display.sendBuffer();
    delay(2000);
    
    digitalWrite(LED_PIN, LOW);
}

// ═══════════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════════

void loop() {
    unsigned long now = millis();
    
    // Process dual-band transport (handles ESP-NOW and LoRa)
    dualBandTransport.process();
    
    // Check link quality and update relay request flag
    if (now - lastLinkQualityCheck > LINK_QUALITY_CHECK_INTERVAL) {
        checkLinkQuality();
        lastLinkQualityCheck = now;
    }
    
    // Update LED pattern
    updateLedPattern();
    
    // Update OLED display
    if (now - lastDisplayUpdate > DISPLAY_INTERVAL) {
        updateDisplay();
        lastDisplayUpdate = now;
    }
    
    // Print dual-band statistics every 10 seconds
    if (now - lastDualBandStats > DUAL_BAND_STATS_INTERVAL) {
        DualBandStats stats = dualBandTransport.getStats();
        
        #if DEBUG_LOGGING
        Serial.println("\n========== DUAL-BAND STATISTICS ==========");
        Serial.printf("[ESP-NOW] TX: %lu, RX: %lu, Failures: %lu\n",
                     stats.espnow_packets_sent,
                     stats.espnow_packets_received,
                     stats.espnow_send_failures);
        Serial.printf("[ESP-NOW] Peer: %s, RSSI: %d dBm\n",
                     stats.espnow_peer_reachable ? "REACHABLE" : "OUT OF RANGE",
                     stats.espnow_last_rssi);
        Serial.printf("[LoRa] TX: %lu, RX: %lu, Filtered: %lu\n",
                     stats.lora_packets_sent,
                     stats.lora_packets_received,
                     stats.lora_filtered_messages);
        Serial.printf("[LoRa] Avg RSSI: %.1f dBm\n", stats.lora_avg_rssi);
        Serial.printf("[Dedup] Duplicates dropped: %lu\n", stats.duplicate_packets_dropped);
        Serial.printf("[Transitions] ESP->LoRa: %lu, LoRa->ESP: %lu\n",
                     stats.espnow_to_lora_transitions,
                     stats.lora_to_espnow_transitions);
        Serial.println("==========================================\n");
        #endif
        
        lastDualBandStats = now;
    }
    
    // Handle radio reception (LoRa)
    // Note: ESP-NOW reception is handled automatically by callbacks
    if (radioPacketReceived) {
        radioPacketReceived = false;
        
        // Read packet
        uint8_t rxBuffer[256];
        int packetSize = radio.getPacketLength();
        if (packetSize > 0 && packetSize <= 256) {
            int state = radio.readData(rxBuffer, packetSize);
            
            if (state == RADIOLIB_ERR_NONE) {
                // Get RSSI and SNR
                float rssi = radio.getRSSI();
                float snr = radio.getSNR();
                
                // Pass to protocol for processing
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
                    false,                      // relay_active (Drone1 doesn't use relay)
                    "RX_LORA",                  // event (specify LoRa RX)
                    packetSize,                 // packet_size
                    0,                          // tx_timestamp (not available for RX)
                    queueDepth,                 // queue_depth (Requirement 6.1)
                    stats.packets_dropped       // errors
                );
#endif
            }
        }
        
        // Return to RX mode
        radio.startReceive();
    }
    
    // Process protocol multiple times to drain queue faster (prevents QUEUE FULL)
    // With FC sending at 1Hz per stream, we need to drain faster than we enqueue
    // Calling process() 10x per loop ensures queue stays empty
    for (int i = 0; i < 10; i++) {
        protocol.process();
    }
    
    // Handle UART data from Flight Controller (Serial1)
    while (Serial1.available() && uartRxIndex < sizeof(uartRxBuffer)) {
        // Buffer overflow protection - check index before writing
        if (uartRxIndex >= 256) {
            #if DEBUG_LOGGING
            Serial.println("[DRONE] UART buffer full!");
            #endif
            break;  // Buffer full, stop reading
        }
        
        uartRxBuffer[uartRxIndex++] = Serial1.read();
        lastUartRx = now;
        
        // Update UART statistics - increment bytes received and update timestamp
        uartStats.fc_bytes_received++;
        uartStats.last_fc_rx = now;
    }
    
    // Update fc_connected status based on activity within 5 seconds
    uartStats.fc_connected = (now - uartStats.last_fc_rx) < 5000;
    
    // Process UART buffer for complete MAVLink packets after timeout
    // Reduced from 40ms to 5ms for faster ESP-NOW message forwarding
    if (uartRxIndex > 0 && (now - lastUartRx) >= 5) {
        #if DEBUG_LOGGING
        Serial.print("[DRONE] Processing UART buffer: ");
        Serial.print(uartRxIndex);
        Serial.print(" bytes. First 16 bytes: ");
        
        // Print first 16 bytes in hex
        for (int i = 0; i < min(16, (int)uartRxIndex); i++) {
            if (uartRxBuffer[i] < 0x10) Serial.print("0");
            Serial.print(uartRxBuffer[i], HEX);
            Serial.print(" ");
        }
        Serial.println();
        #endif
        
        int16_t result = findCompleteMavlinkPacket(uartRxBuffer, uartRxIndex);
        
        #if DEBUG_LOGGING
        Serial.print("MAVLink detection result: ");
        Serial.println(result);
        #endif
        
        if (result > 0) {
            // Complete packet found - extract and send via DualBandTransport
            uint16_t packetLen = (uint16_t)result;
            
            // Send packet to ground station via dual-band transport
            // DualBandTransport automatically routes to ESP-NOW (all messages) and LoRa (essential only)
            bool sent = dualBandTransport.send(uartRxBuffer, packetLen, NODE_GROUND);
            
            // Debug output
            #if DEBUG_LOGGING
            Serial.print("[DRONE] Sent MAVLink packet (");
            Serial.print(packetLen);
            Serial.print(" bytes) to NODE_GROUND: ");
            Serial.println(sent ? "SUCCESS" : "FAILED");
            #endif
            
            // Log TX event (log ALL attempts, not just successful ones)
#ifdef ENABLE_FLIGHT_LOGGER
            // Extract MAVLink message ID and sequence number from packet
            uint8_t msgId = 0;
            uint32_t seq = 0;
            uint8_t sysId = 0;
            
            // Parse MAVLink packet to extract fields
            if (packetLen >= 6) {
                if (uartRxBuffer[0] == 0xFE) {  // MAVLink v1
                    seq = uartRxBuffer[2];
                    sysId = uartRxBuffer[3];
                    msgId = uartRxBuffer[5];
                } else if (uartRxBuffer[0] == 0xFD && packetLen >= 10) {  // MAVLink v2
                    sysId = uartRxBuffer[5];
                    msgId = uartRxBuffer[9];
                    // MAVLink v2 doesn't have a simple sequence field in the same location
                    seq = 0;  // Not easily accessible in v2
                }
            }
            
            // Get current stats for queue depth and errors
            AeroLoRaStats stats = protocol.getStats();
            uint8_t queueDepth = protocol.getQueueDepth();  // Get current queue depth (Requirement 6.1)
            DualBandStats dbStats = dualBandTransport.getStats();
            
            // Determine event type based on ESP-NOW availability and message filtering
            const char* event = sent ? "TX_DUAL" : "TX_DROP";
            if (sent && dbStats.espnow_peer_reachable) {
                event = "TX_ESPNOW";  // Sent via ESP-NOW (and possibly LoRa if essential)
            } else if (sent) {
                event = "TX_LORA";  // Sent via LoRa only (ESP-NOW out of range)
            }
            
            // Only log LoRa packets to reduce log size, OR rate-limited ESP-NOW packets
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
                    seq,                    // sequence_number
                    msgId,                  // message_id
                    sysId,                  // system_id
                    0.0,                    // rssi_dbm (not available at TX time)
                    0.0,                    // snr_db (not available at TX time)
                    relayRequestActive,     // relay_active
                    event,                  // event (TX_ESPNOW, TX_LORA, or TX_DROP)
                    packetLen,              // packet_size
                    millis(),               // tx_timestamp (current time)
                    queueDepth,             // queue_depth (Requirement 6.1)
                    stats.packets_dropped   // errors (use dropped packets as error count)
                );
            }
#endif
            
            // Update UART statistics - increment packets received from FC
            uartStats.fc_packets_received++;
            
            // Remove processed packet from buffer using memmove
            if (packetLen < uartRxIndex) {
                // More data remains in buffer - shift it to the beginning
                memmove(uartRxBuffer, uartRxBuffer + packetLen, uartRxIndex - packetLen);
                uartRxIndex -= packetLen;
            } else {
                // Buffer completely processed
                uartRxIndex = 0;
            }
            
            // Update LED to show TX activity
            ledPattern = 1;
            lastLedUpdate = now;
            
        } else if (result < -1) {
            // Negative value means garbage bytes to skip
            uint16_t skipBytes = (uint16_t)(-result);
            #if DEBUG_LOGGING
            Serial.print("[DRONE] Skipping ");
            Serial.print(skipBytes);
            Serial.println(" garbage bytes before MAVLink marker");
            #endif
            
            // Shift buffer to remove garbage
            memmove(uartRxBuffer, uartRxBuffer + skipBytes, uartRxIndex - skipBytes);
            uartRxIndex -= skipBytes;
            
        } else if (result == -1) {
            // Invalid packet or all garbage - clear buffer
            #if DEBUG_LOGGING
            Serial.println("[DRONE] Invalid data or all garbage, clearing buffer");
            #endif
            uartRxIndex = 0;
            memset(uartRxBuffer, 0, sizeof(uartRxBuffer));
            
        } else {
            // result == 0, incomplete packet
            // If buffer is full and stuck, clear it
            if (uartRxIndex >= 250) {
                #if DEBUG_LOGGING
                Serial.println("[DRONE] Buffer nearly full with incomplete packet, clearing");
                #endif
                uartRxIndex = 0;
                memset(uartRxBuffer, 0, sizeof(uartRxBuffer));
            } else {
                #if DEBUG_LOGGING
                Serial.println("[DRONE] Incomplete MAVLink packet, waiting for more data");
                #endif
            }
        }
    }
    
    // Handle received data from ground (via dual-band transport)
    // DualBandTransport automatically deduplicates packets from ESP-NOW and LoRa
    uint8_t rxBuffer[256];
    uint8_t len = dualBandTransport.receive(rxBuffer, 256);
    
    if (len > 0) {
        // Forward received data to flight controller via UART
        Serial1.write(rxBuffer, len);
        
#ifdef ENABLE_FLIGHT_LOGGER
        // Log forwarding to Flight Controller
        // RATE LIMIT: Only log every 200ms (5Hz) to prevent crashing due to high ESP-NOW rate
        static unsigned long lastDualBandLog = 0;
        if (millis() - lastDualBandLog > 200) {
            uint8_t msgId = (rxBuffer[0] == 0xFE) ? rxBuffer[5] : rxBuffer[7];
            uint8_t sysId = (rxBuffer[0] == 0xFE) ? rxBuffer[3] : rxBuffer[5];
            uint32_t seq = (rxBuffer[0] == 0xFE) ? rxBuffer[2] : rxBuffer[4];
            
            logger.logPacket(
                seq,
                msgId,
                sysId,
                0, 0, false,
                "RX_DUALBAND", // Indicates packet reached Drone (via either path)
                len,
                millis(),
                0, 0
            );
            lastDualBandLog = millis();
        }
#endif
        
        // Update UART statistics - increment packets and bytes sent to FC
        uartStats.fc_packets_sent++;
        uartStats.fc_bytes_sent += len;
        
        // Update LED to show RX activity
        ledPattern = 2;
        lastLedUpdate = now;
    }
    
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
    
    // Handle flight logger serial commands (DUMP, SIZE, CLEAR, HELP)
#ifdef ENABLE_FLIGHT_LOGGER
    logger.handleSerialCommands();
#endif
}
