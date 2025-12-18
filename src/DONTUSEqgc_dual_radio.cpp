/**
 * QGC Dual Radio Ground Station
 * 
 * Monitors both 915 MHz (direct) and 902 MHz (relay) frequencies.
 * Automatically switches to relay mode when direct link is lost.
 * 
 * Features:
 * - Dual SX1262 radios (radio1 @ 915 MHz, radio2 @ 902 MHz)
 * - Automatic relay mode activation (3 second timeout)
 * - Automatic return to direct mode (5 consecutive packets)
 * - Hardware CRC on both radios
 * - Three-tier priority queuing on both frequencies
 * - ALWAYS_RELAY_MODE for testing
 * 
 * Hardware Configuration:
 * - Radio1: 915 MHz for direct Drone1/Drone2 communication
 * - Radio2: 902 MHz for relay communication via Drone2 Secondary
 * - Both radios use same LoRa parameters (SF7, BW125, CR5)
 * - USB Serial to PC/QGroundControl
 * 
 * NOTE: This entire file requires ENABLE_RELAY to be defined.
 * Without ENABLE_RELAY, use aero_lora_ground.cpp instead.
 */

#ifndef ENABLE_RELAY
#error "qgc_dual_radio.cpp requires ENABLE_RELAY to be defined. Use env:qgc_dual_radio build environment."
#endif

#include <Arduino.h>
#include <RadioLib.h>
#include <SPI.h>
#include <U8g2lib.h>
#include <Wire.h>
#include "AeroLoRaProtocol.h"
#include "relay_uart_protocol.h"

#ifdef ENABLE_FLIGHT_LOGGER
#include "flight_logger.h"
#endif

// ═══════════════════════════════════════════════════════════════════
// PIN DEFINITIONS - Dual Heltec WiFi LoRa 32 (V3)
// ═══════════════════════════════════════════════════════════════════

// Radio 1 (915 MHz - Direct Link)
#define LORA1_SCK         9
#define LORA1_MISO        11
#define LORA1_MOSI        10
#define LORA1_CS          8
#define LORA1_RST         12
#define LORA1_DIO1        14
#define LORA1_BUSY        13

// Radio 2 (902 MHz - Relay Link)
// Note: These pins need to be configured for second Heltec module
// For now, using placeholder values - adjust based on actual hardware setup
#define LORA2_SCK         9    // Shared SPI bus
#define LORA2_MISO        11   // Shared SPI bus
#define LORA2_MOSI        10   // Shared SPI bus
#define LORA2_CS          7    // Different CS pin
#define LORA2_RST         6    // Different RST pin
#define LORA2_DIO1        5    // Different DIO1 pin
#define LORA2_BUSY        4    // Different BUSY pin

// LED and Display
#define LED_PIN           35
#define OLED_SDA          17
#define OLED_SCL          18
#define OLED_RST          21
#define VEXT_PIN          36

// ═══════════════════════════════════════════════════════════════════
// RADIO CONFIGURATION
// ═══════════════════════════════════════════════════════════════════

// Radio 1: 915 MHz (Direct Link)
#define FREQ1_MHZ            915.0
#define LORA1_BANDWIDTH      125.0   // 125 kHz
#define LORA1_SPREAD_FACTOR  7        // SF7
#define LORA1_CODING_RATE    5        // 4/5
#define LORA1_SYNC_WORD      0x12     // Network ID
#define LORA1_TX_POWER       14       // 14 dBm

// Radio 2: 902 MHz (Relay Link)
#define FREQ2_MHZ            902.0
#define LORA2_BANDWIDTH      125.0   // 125 kHz
#define LORA2_SPREAD_FACTOR  7        // SF7
#define LORA2_CODING_RATE    5        // 4/5
#define LORA2_SYNC_WORD      0x12     // Network ID (same as radio1)
#define LORA2_TX_POWER       14       // 14 dBm

// ═══════════════════════════════════════════════════════════════════
// PROTOCOL CONFIGURATION
// ═══════════════════════════════════════════════════════════════════

#define MAVLINK_SERIAL_BAUD     57600
#define TDMA_SLOT_DURATION_MS   40
#define GROUND_SLOT_OFFSET      1       // ODD slots

// Relay mode thresholds
#define RELAY_ACTIVATE_TIMEOUT_MS   3000    // 3 seconds without Drone1 packets
#define DIRECT_PACKET_COUNT         5       // 5 consecutive packets to deactivate relay

// ═══════════════════════════════════════════════════════════════════
// GLOBAL OBJECTS
// ═══════════════════════════════════════════════════════════════════

// Dual radios
SX1262 radio1 = new Module(LORA1_CS, LORA1_DIO1, LORA1_RST, LORA1_BUSY);
SX1262 radio2 = new Module(LORA2_CS, LORA2_DIO1, LORA2_RST, LORA2_BUSY);

// Dual protocols
AeroLoRaProtocol protocol1(&radio1, GROUND_SLOT_OFFSET, TDMA_SLOT_DURATION_MS);
AeroLoRaProtocol protocol2(&radio2, GROUND_SLOT_OFFSET, TDMA_SLOT_DURATION_MS);

// Display
U8G2_SSD1306_128X64_NONAME_F_HW_I2C display(U8G2_R0, OLED_RST, OLED_SCL, OLED_SDA);

// Relay state
bool relayModeActive = false;
unsigned long lastDrone1DirectPacket = 0;
uint8_t consecutiveDirectPackets = 0;

// Statistics
RelayStats relayStats = {0};

// Buffers
uint8_t serialRxBuffer[256];
uint16_t serialRxIndex = 0;
unsigned long lastSerialRx = 0;

// Radio interrupt flags
volatile bool radio1PacketReceived = false;
volatile bool radio2PacketReceived = false;

// LED and display
unsigned long lastLedUpdate = 0;
uint8_t ledPattern = 0;  // 0=idle, 1=tx, 2=rx_direct, 3=rx_relay
unsigned long lastDisplayUpdate = 0;
#define DISPLAY_INTERVAL 200

// Statistics printing
unsigned long lastStatsprint = 0;
#define STATS_INTERVAL 10000

// Radio error tracking (Requirements 13.2, 13.3)
struct RadioErrorStats {
    uint32_t transmission_failures;
    uint32_t consecutive_failures;
    uint32_t radio_resets;
    unsigned long last_reset_time;
};

RadioErrorStats radio1Errors = {0};
RadioErrorStats radio2Errors = {0};

// Watchdog timers (Requirements 13.1, 13.5)
WatchdogTimers watchdogTimers;

// ═══════════════════════════════════════════════════════════════════
// RADIO INTERRUPTS
// ═══════════════════════════════════════════════════════════════════

void IRAM_ATTR onRadio1Receive() {
    radio1PacketReceived = true;
}

void IRAM_ATTR onRadio2Receive() {
    radio2PacketReceived = true;
}

// ═══════════════════════════════════════════════════════════════════
// RADIO ERROR HANDLING
// ═══════════════════════════════════════════════════════════════════
/**
 * Handle radio transmission with error recovery for Radio 1
 * 
 * Requirements: 13.2, 13.3
 */
template<typename RadioType>
bool transmitWithErrorHandling(RadioType* radio, RadioErrorStats& errors, 
                               uint8_t* data, size_t len,
                               float freq, float bw, int sf, int cr, uint8_t sw, int pwr) {
    const int MAX_RETRIES = 3;
    const int INITIAL_BACKOFF_MS = 50;
    const int MAX_CONSECUTIVE_FAILURES = 5;
    
    int backoff_ms = INITIAL_BACKOFF_MS;
    
    // Attempt transmission with exponential backoff
    for (int attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        int state = radio->transmit(data, len);
        
        if (state == RADIOLIB_ERR_NONE) {
            // Success - reset consecutive failure counter
            errors.consecutive_failures = 0;
            return true;
        }
        
        // Transmission failed
        errors.transmission_failures++;
        errors.consecutive_failures++;
        
        // Get RSSI and SNR for error context
        float rssi = radio->getRSSI();
        float snr = radio->getSNR();
        
        // Log radio error (Requirement 12.4)
        logRadioError(state, rssi, snr, attempt + 1, MAX_RETRIES + 1);
        
        // Check if we should reset radio after too many failures
        if (errors.consecutive_failures >= MAX_CONSECUTIVE_FAILURES) {
            Serial.println("[RADIO ERROR] 5 consecutive failures - resetting radio");
            
            // Reset radio
            radio->reset();
            delay(100);
            
            // Re-initialize radio
            int initState = radio->begin(freq, bw, sf, cr, sw, pwr);
            
            if (initState == RADIOLIB_ERR_NONE) {
                radio->setCRC(true);
                
                Serial.println("[RADIO] Reset successful");
                errors.radio_resets++;
                errors.last_reset_time = millis();
                errors.consecutive_failures = 0;
            } else {
                Serial.print("[RADIO ERROR] Reset failed: ");
                Serial.println(initState);
            }
            
            return false;
        }
        
        // If not last attempt, wait with exponential backoff
        if (attempt < MAX_RETRIES) {
            delay(backoff_ms);
            backoff_ms *= 2;  // Exponential backoff
        }
    }
    
    // All retries exhausted
    Serial.println("[RADIO ERROR] All retries exhausted");
    return false;
}

// ═══════════════════════════════════════════════════════════════════
// FORWARD DECLARATIONS
// ═══════════════════════════════════════════════════════════════════

void processRadio1();
void processRadio2();
void checkRelayMode();
void forwardFromPC();
void updateDisplay();
void updateLedPattern();
int16_t findCompleteMavlinkPacket(uint8_t* buffer, uint16_t bufferLen);

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
    display.drawStr(0, 20, "QGC Dual Radio");
    display.drawStr(0, 35, "Initializing...");
    display.sendBuffer();
    delay(500);
    
    // Initialize USB Serial for QGroundControl
    Serial.begin(MAVLINK_SERIAL_BAUD);
    while (!Serial && millis() < 3000);
    
    Serial.println("\n=== QGC Dual Radio Ground Station ===");
    
    // Initialize SPI
    SPI.begin(LORA1_SCK, LORA1_MISO, LORA1_MOSI);
    
    // Initialize Radio 1 (915 MHz - Direct Link)
    Serial.print("Initializing Radio1 @ 915 MHz... ");
    int state1 = radio1.begin(FREQ1_MHZ, LORA1_BANDWIDTH, LORA1_SPREAD_FACTOR,
                              LORA1_CODING_RATE, LORA1_SYNC_WORD, LORA1_TX_POWER);
    
    if (state1 == RADIOLIB_ERR_NONE) {
        Serial.println("OK!");
    } else {
        Serial.print("FAILED: ");
        Serial.println(state1);
        while (true) {
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            delay(100);
        }
    }
    
    // Configure Radio 1
    radio1.setDio1Action(onRadio1Receive);
    radio1.setCRC(true);
    radio1.startReceive();
    protocol1.begin(NODE_GROUND);
    
    // Initialize Radio 2 (902 MHz - Relay Link)
    Serial.print("Initializing Radio2 @ 902 MHz... ");
    int state2 = radio2.begin(FREQ2_MHZ, LORA2_BANDWIDTH, LORA2_SPREAD_FACTOR,
                              LORA2_CODING_RATE, LORA2_SYNC_WORD, LORA2_TX_POWER);
    
    if (state2 == RADIOLIB_ERR_NONE) {
        Serial.println("OK!");
    } else {
        Serial.print("FAILED: ");
        Serial.println(state2);
        while (true) {
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            delay(200);
        }
    }
    
    // Configure Radio 2
    radio2.setDio1Action(onRadio2Receive);
    radio2.setCRC(true);
    radio2.startReceive();
    protocol2.begin(NODE_GROUND);
    
    Serial.println("\nDual radio initialized!");
    Serial.println("Radio1: 915 MHz (direct link)");
    Serial.println("Radio2: 902 MHz (relay link)");
    Serial.printf("Node ID: %d (GROUND)\n", NODE_GROUND);
    
    #ifdef ALWAYS_RELAY_MODE
    relayModeActive = true;
    relayStats.relay_mode_active = true;
    Serial.println("\n*** ALWAYS_RELAY_MODE ACTIVE ***");
    Serial.println("Listening on 902 MHz for relay traffic");
    #else
    Serial.println("Relay mode: AUTOMATIC");
    Serial.println("Will activate after 3s without direct packets");
    #endif
    
    Serial.println("\nQGC Dual Radio ready!");
    
    // Initialize watchdog timers
    initWatchdogTimers(&watchdogTimers);
    
    // Show ready on display
    display.clearBuffer();
    display.drawStr(0, 10, "QGC Dual Radio");
    display.drawLine(0, 12, 128, 12);
    display.drawStr(0, 24, "915MHz: DIRECT");
    display.drawStr(0, 36, "902MHz: RELAY");
    #ifdef ALWAYS_RELAY_MODE
    display.drawStr(0, 48, "Mode: ALWAYS RELAY");
    #else
    display.drawStr(0, 48, "Mode: AUTO");
    #endif
    display.sendBuffer();
    delay(1000);
    
    digitalWrite(LED_PIN, LOW);
    lastDrone1DirectPacket = millis();  // Initialize timestamp
}

// ═══════════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════════

void loop() {
    unsigned long now = millis();
    
    // Update LED pattern
    updateLedPattern();
    
    // Update OLED display
    if (now - lastDisplayUpdate > DISPLAY_INTERVAL) {
        updateDisplay();
        lastDisplayUpdate = now;
    }
    
    // Process both radios
    processRadio1();  // 915 MHz direct link
    processRadio2();  // 902 MHz relay link
    
    // Check relay mode activation/deactivation
    checkRelayMode();
    
    // Process protocol queues
    protocol1.process();
    protocol2.process();
    
    // Forward MAVLink from PC to appropriate radio
    forwardFromPC();
    
    // Check watchdog timers (Requirements 13.1, 13.5)
    // Note: QGC doesn't use UART watchdog, but monitors relay activity
    if (relayModeActive) {
        checkRelayWatchdog(&watchdogTimers);
    }
    
    // Print statistics
    if (now - lastStatsprint > STATS_INTERVAL) {
        printRelayStats(relayStats, "QGC");
        lastStatsprint = now;
    }
}

// ═══════════════════════════════════════════════════════════════════
// RADIO PROCESSING FUNCTIONS (Implemented in sub-tasks 4.2 and 4.3)
// ═══════════════════════════════════════════════════════════════════

/**
 * Process Radio 1 (915 MHz - Direct Link)
 * 
 * Handles packets received on the direct 915 MHz link from Drone1 and Drone2.
 * Tracks Drone1 packets to determine if direct link is healthy.
 * Updates relay mode state based on direct packet reception.
 * 
 * Requirements: 5.1, 5.4
 */
void processRadio1() {
    // Handle radio interrupt
    if (radio1PacketReceived) {
        radio1PacketReceived = false;
        
        // Read packet
        uint8_t rxBuffer[256];
        int packetSize = radio1.getPacketLength();
        if (packetSize > 0 && packetSize <= 256) {
            int state = radio1.readData(rxBuffer, packetSize);
            
            if (state == RADIOLIB_ERR_NONE) {
                // Pass to protocol for processing
                AeroLoRaPacket* packet = (AeroLoRaPacket*)rxBuffer;
                protocol1.handleReceivedPacket(packet);
            }
        }
        
        // Return to RX mode
        radio1.startReceive();
    }
    
    // Check for received data from protocol
    if (protocol1.available()) {
        uint8_t rxBuffer[AEROLORA_MAX_PAYLOAD];
        uint8_t len = protocol1.receive(rxBuffer, AEROLORA_MAX_PAYLOAD);
        
        if (len > 0) {
            // Update statistics
            relayStats.packets_from_915mhz++;
            
            // Check if packet is from Drone1 (system ID = 1)
            // MAVLink v1: byte 3 is system ID
            // MAVLink v2: byte 5 is system ID
            bool isDrone1Packet = false;
            if (len >= 4 && (rxBuffer[0] == 0xFE || rxBuffer[0] == 0xFD)) {
                uint8_t sysId = 0;
                if (rxBuffer[0] == 0xFE && len >= 4) {
                    sysId = rxBuffer[3];  // MAVLink v1
                } else if (rxBuffer[0] == 0xFD && len >= 6) {
                    sysId = rxBuffer[5];  // MAVLink v2
                }
                
                if (sysId == 1) {  // Drone1
                    isDrone1Packet = true;
                    lastDrone1DirectPacket = millis();
                    consecutiveDirectPackets++;
                    
                    // Visual feedback for direct packet
                    ledPattern = 2;
                    lastLedUpdate = millis();
                }
            }
            
            // Forward to PC (QGroundControl)
            Serial.write(rxBuffer, len);
        }
    }
}

/**
 * Process Radio 2 (902 MHz - Relay Link)
 * 
 * Handles packets received on the 902 MHz relay link from Drone2 Secondary.
 * Prioritizes relay packets when relay mode is active.
 * Logs relay packet reception for debugging.
 * 
 * Requirements: 5.3, 5.5
 */
void processRadio2() {
    // Handle radio interrupt
    if (radio2PacketReceived) {
        radio2PacketReceived = false;
        
        // Read packet
        uint8_t rxBuffer[256];
        int packetSize = radio2.getPacketLength();
        if (packetSize > 0 && packetSize <= 256) {
            int state = radio2.readData(rxBuffer, packetSize);
            
            if (state == RADIOLIB_ERR_NONE) {
                // Pass to protocol for processing
                AeroLoRaPacket* packet = (AeroLoRaPacket*)rxBuffer;
                protocol2.handleReceivedPacket(packet);
            }
        }
        
        // Return to RX mode
        radio2.startReceive();
    }
    
    // Check for received data from protocol
    if (protocol2.available()) {
        uint8_t rxBuffer[AEROLORA_MAX_PAYLOAD];
        uint8_t len = protocol2.receive(rxBuffer, AEROLORA_MAX_PAYLOAD);
        
        if (len > 0) {
            // Update statistics
            relayStats.packets_from_902mhz++;
            
            // If relay mode is active, prioritize these packets
            if (relayModeActive) {
                // Forward to PC (QGroundControl)
                Serial.write(rxBuffer, len);
                
                // Update watchdog timer for relay activity
                updateRelayActivity(&watchdogTimers);
                
                // Log relay reception (Requirement 12.5)
                Serial.print("[QGC] Received via RELAY @ 902 MHz from Drone2 (len=");
                Serial.print(len);
                Serial.println(" bytes)");
                
                // Visual feedback for relay packet
                ledPattern = 3;
                lastLedUpdate = millis();
            } else {
                // Not in relay mode, but still forward (might be test traffic)
                Serial.write(rxBuffer, len);
                Serial.println("[QGC] Received @ 902 MHz (relay mode inactive)");
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════════════
// RELAY MODE MANAGEMENT (Implemented in sub-task 4.4)
// ═══════════════════════════════════════════════════════════════════

/**
 * Check and manage relay mode activation/deactivation
 * 
 * In ALWAYS_RELAY_MODE: Relay is permanently active
 * In automatic mode:
 * - Activate relay if no Drone1 packets for 3 seconds
 * - Deactivate relay if 5 consecutive direct packets received
 * 
 * Logs all mode transitions for debugging.
 * 
 * Requirements: 5.2, 5.4, 7.1, 7.2, 7.3
 */
void checkRelayMode() {
    #ifdef ALWAYS_RELAY_MODE
    // In ALWAYS_RELAY_MODE, relay is permanently active
    if (!relayModeActive) {
        relayModeActive = true;
        relayStats.relay_mode_active = true;
        relayStats.relay_activations++;
        Serial.println("[QGC] ALWAYS_RELAY_MODE - Relay permanently active");
    }
    return;
    #endif
    
    // Automatic relay mode management
    unsigned long now = millis();
    
    // Check if we should activate relay mode
    if (!relayModeActive) {
        // Activate if no Drone1 packets for 3 seconds
        if (now - lastDrone1DirectPacket > RELAY_ACTIVATE_TIMEOUT_MS) {
            relayModeActive = true;
            relayStats.relay_mode_active = true;
            relayStats.relay_activations++;
            consecutiveDirectPackets = 0;
            
            // Log relay mode transition (Requirement 12.4)
            Serial.println("═══════════════════════════════════════════════════════");
            logRelayModeTransition(true, "no direct packets from Drone1 for 3 seconds");
            Serial.println("Now listening on 902 MHz for relay traffic");
            Serial.println("═══════════════════════════════════════════════════════");
        }
    } else {
        // Check if we should deactivate relay mode
        // Deactivate if we've received 5 consecutive direct packets
        if (consecutiveDirectPackets >= DIRECT_PACKET_COUNT) {
            relayModeActive = false;
            relayStats.relay_mode_active = false;
            consecutiveDirectPackets = 0;
            
            // Log relay mode transition (Requirement 12.4)
            Serial.println("═══════════════════════════════════════════════════════");
            logRelayModeTransition(false, "direct link restored (5 consecutive packets)");
            Serial.println("Now prioritizing 915 MHz direct link");
            Serial.println("═══════════════════════════════════════════════════════");
        }
    }
}

// ═══════════════════════════════════════════════════════════════════
// PC TO RADIO FORWARDING (Implemented in sub-task 4.5)
// ═══════════════════════════════════════════════════════════════════

/**
 * Forward MAVLink packets from PC to appropriate radio
 * 
 * Routing logic:
 * - Drone1 + relayModeActive: Send via protocol2 @ 902 MHz (relay path)
 * - Drone1 + !relayModeActive: Send via protocol1 @ 915 MHz (direct path)
 * - Drone2: Always send via protocol1 @ 915 MHz (direct path)
 * - Broadcast: Send via both radios
 * 
 * Extracts destination system ID from MAVLink packet to determine routing.
 * 
 * Requirements: 5.3, 9.4
 */
void forwardFromPC() {
    unsigned long now = millis();
    
    // Read serial data from PC
    while (Serial.available() && serialRxIndex < sizeof(serialRxBuffer)) {
        serialRxBuffer[serialRxIndex++] = Serial.read();
        lastSerialRx = now;
    }
    
    // Process serial buffer when we have data and a timeout has occurred
    if (serialRxIndex > 0 && (now - lastSerialRx > 40)) {
        int16_t packetLen = findCompleteMavlinkPacket(serialRxBuffer, serialRxIndex);
        
        if (packetLen > 0) {
            // Complete MAVLink packet found
            
            // Extract destination system ID
            uint8_t destSysId = 0;
            if (serialRxBuffer[0] == 0xFE && packetLen >= 4) {
                // MAVLink v1: system ID at byte 3
                destSysId = serialRxBuffer[3];
            } else if (serialRxBuffer[0] == 0xFD && packetLen >= 6) {
                // MAVLink v2: system ID at byte 5
                destSysId = serialRxBuffer[5];
            }
            
            // Determine routing based on destination and relay mode
            bool sentViaRelay = false;
            
            if (destSysId == 1) {
                // Packet for Drone1
                if (relayModeActive) {
                    // Send via 902 MHz relay path
                    if (protocol2.send(serialRxBuffer, packetLen, false, NODE_DRONE1)) {
                        sentViaRelay = true;
                        ledPattern = 1;
                        lastLedUpdate = now;
                    }
                } else {
                    // Send via 915 MHz direct path
                    if (protocol1.send(serialRxBuffer, packetLen, false, NODE_DRONE1)) {
                        ledPattern = 1;
                        lastLedUpdate = now;
                    }
                }
            } else if (destSysId == 2) {
                // Packet for Drone2 - always send direct @ 915 MHz
                if (protocol1.send(serialRxBuffer, packetLen, false, NODE_DRONE2)) {
                    ledPattern = 1;
                    lastLedUpdate = now;
                }
            } else if (destSysId == 0 || destSysId == 255) {
                // Broadcast packet - send on both radios
                protocol1.send(serialRxBuffer, packetLen, false, AERO_BROADCAST);
                protocol2.send(serialRxBuffer, packetLen, false, AERO_BROADCAST);
                ledPattern = 1;
                lastLedUpdate = now;
            } else {
                // Unknown destination - send on primary radio
                protocol1.send(serialRxBuffer, packetLen, false, destSysId);
                ledPattern = 1;
                lastLedUpdate = now;
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
            // Invalid data - clear buffer
            serialRxIndex = 0;
        }
        // If packetLen == 0, wait for more data
    }
}

// ═══════════════════════════════════════════════════════════════════
// DISPLAY UPDATE
// ═══════════════════════════════════════════════════════════════════
/**
 * Update OLED display with QGC relay status
 * 
 * Shows:
 * - Active frequency (915 MHz or 902 MHz)
 * - Relay source node (Drone2)
 * - Packet counts from each frequency
 * - Relay mode transitions
 * 
 * Updates every 200ms (DISPLAY_INTERVAL)
 * 
 * Requirements: 12.5
 */
void updateDisplay() {
    display.clearBuffer();
    display.setFont(u8g2_font_6x10_tf);
    
    // Title
    display.drawStr(0, 10, "QGC DUAL RADIO");
    display.drawLine(0, 12, 128, 12);
    
    // Active frequency and relay mode status
    // Requirement 12.5: Show active frequency (915 MHz or 902 MHz)
    if (relayModeActive) {
        display.drawStr(0, 24, "Active: 902MHz");
        
        // Requirement 12.5: Show relay source node (Drone2)
        display.drawStr(0, 36, "Relay: Drone2");
    } else {
        display.drawStr(0, 24, "Active: 915MHz");
        display.drawStr(0, 36, "Mode: DIRECT");
    }
    
    // Packet counts from each frequency
    // Requirement 12.5: Show packet counts from each frequency
    char buf[32];
    sprintf(buf, "915:%lu 902:%lu", 
            relayStats.packets_from_915mhz,
            relayStats.packets_from_902mhz);
    display.drawStr(0, 48, buf);
    
    // Relay activations (shows how many times relay mode has been activated)
    // Requirement 12.5: Log relay mode transitions (displayed as count)
    sprintf(buf, "Transitions:%lu", relayStats.relay_activations);
    display.drawStr(0, 60, buf);
    
    display.sendBuffer();
}

// ═══════════════════════════════════════════════════════════════════
// LED PATTERN UPDATE
// ═══════════════════════════════════════════════════════════════════

void updateLedPattern() {
    unsigned long now = millis();
    
    switch(ledPattern) {
        case 1: // TX - rapid flash
            digitalWrite(LED_PIN, (now / 100) % 2);
            break;
            
        case 2: // RX direct - solid for 500ms
            if (now - lastLedUpdate < 500) {
                digitalWrite(LED_PIN, HIGH);
            } else {
                digitalWrite(LED_PIN, LOW);
                ledPattern = 0;
            }
            break;
            
        case 3: // RX relay - double blink
            if (now - lastLedUpdate < 100) {
                digitalWrite(LED_PIN, HIGH);
            } else if (now - lastLedUpdate < 200) {
                digitalWrite(LED_PIN, LOW);
            } else if (now - lastLedUpdate < 300) {
                digitalWrite(LED_PIN, HIGH);
            } else if (now - lastLedUpdate < 500) {
                digitalWrite(LED_PIN, LOW);
            } else {
                ledPattern = 0;
            }
            break;
            
        default: // Idle - heartbeat pulse
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
                // MAVLink v1
                packetLen = buffer[i + 1] + 8;
            } else if (buffer[i] == 0xFD && (i + 1) < bufferLen) {
                // MAVLink v2
                packetLen = buffer[i + 1] + 12;
                if ((i + 2) < bufferLen && (buffer[i + 2] & 0x01)) {
                    packetLen += 13;  // Signature
                }
            }
            
            if (packetLen > 0 && (i + packetLen) <= bufferLen) {
                return i + packetLen;
            }
            
            if (packetLen > 0) {
                return 0;  // Incomplete packet
            }
            
            return -1;  // Invalid packet
        }
    }
    
    if (bufferLen > 100) {
        return -1;  // Too much data without MAVLink marker
    }
    
    return 0;  // Wait for more data
}
