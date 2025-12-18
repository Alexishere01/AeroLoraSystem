/**
 * Drone2 Primary - Relay Coordinator
 * 
 * This firmware runs on Drone2's Primary Heltec V3 module, which is connected
 * to the flight controller and operates at 915 MHz. It handles normal drone
 * operations while also monitoring for relay opportunities.
 * 
 * Relay Functionality:
 * - Monitors 915 MHz for packets from Drone1
 * - Detects weak signals (RSSI < -95 dBm) or relay request flags
 * - Forwards relay candidates to Secondary Heltec via UART (Serial1)
 * - Receives relayed packets from Secondary and forwards to flight controller
 * 
 * Hardware Configuration:
 * - Radio: SX1262 @ 915 MHz (RadioLib)
 * - Flight Controller: UART (Serial) @ 115200 baud
 * - Secondary Heltec: UART (Serial1) @ 115200 baud, GPIO 1=TX, GPIO 2=RX
 * - OLED Display: I2C (shows relay status)
 * 
 * Compile Flags:
 * - ENABLE_RELAY: Enable relay functionality
 * - ALWAYS_RELAY_MODE: Always forward packets to QGC (testing mode)
 * - RELAY_DEBUG: Enable verbose relay logging
 */

#include <Arduino.h>
#include <RadioLib.h>
#include <SPI.h>
#include <U8g2lib.h>
#include <Wire.h>
#include "AeroLoRaProtocol.h"
#include "relay_uart_protocol.h"
#include "DualBandTransport.h"
#include "ESPNowTransport.h"
#include "MessageFilter.h"

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

// UART for Flight Controller (Serial2)
#define FC_TX            45  // GPIO45 - connects to FC RX8
#define FC_RX            46  // GPIO46 - connects to FC TX8
#define FC_BAUD          115200

// UART for Secondary Heltec (Serial1)
#define SECONDARY_TX     1   // GPIO 1 = TX (connects to Secondary's RX)
#define SECONDARY_RX     2   // GPIO 2 = RX (connects to Secondary's TX)
#define SECONDARY_BAUD   115200



// ═══════════════════════════════════════════════════════════════════
// RADIO CONFIGURATION
// ═══════════════════════════════════════════════════════════════════
#define FREQ_MHZ            930.0   // Changed from 915.0 to avoid ELRS interference
#define LORA_BANDWIDTH      500.0   // 500 kHz for maximum speed
#define LORA_SPREAD_FACTOR  6       // SF7 for speed
#define LORA_CODING_RATE    5       // 4/5 coding rate
#define LORA_SYNC_WORD      0x34    // Private network
#define LORA_TX_POWER       4       // 4 dBm (~2.5 mW) - reduced to make jammer more effective

// ═══════════════════════════════════════════════════════════════════
// RELAY CONFIGURATION
// ═══════════════════════════════════════════════════════════════════
#define RELAY_RSSI_THRESHOLD    -95.0   // dBm - forward packets weaker than this
#define RELAY_TIMEOUT_MS        30000   // 30 seconds - deactivate relay after inactivity

// ═══════════════════════════════════════════════════════════════════
// GLOBAL OBJECTS
// ═══════════════════════════════════════════════════════════════════
SX1262 radio = new Module(LORA_CS, LORA_DIO1, LORA_RST, LORA_BUSY);
AeroLoRaProtocol protocol(&radio, 0, 40);  // EVEN slots for air
U8G2_SSD1306_128X64_NONAME_F_HW_I2C display(U8G2_R0, OLED_RST, OLED_SCL, OLED_SDA);

// Dual-Band Transport Components
ESPNowTransport espnowTransport;
DualBandTransport dualBandTransport(&espnowTransport, &protocol);

// Drone1 MAC Address (Drone1 actual MAC)
uint8_t drone1_mac[6] = {0x48, 0xCA, 0x43, 0x3A, 0xEF, 0x04};

// Buffers - UART Serial (Flight Controller)
uint8_t uartRxBuffer[256];
uint16_t uartRxIndex = 0;
unsigned long lastUartRx = 0;

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

#ifdef ENABLE_RELAY
// Relay state variables
bool relayModeActive = false;
unsigned long lastRelayActivity = 0;
unsigned long relayModeStartTime = 0;
RelayStats relayStats = {0};

// Watchdog timers (Requirements 13.1, 13.5)
WatchdogTimers watchdogTimers;
#endif // ENABLE_RELAY

#ifdef ENABLE_FLIGHT_LOGGER
// Flight logger instance
FlightLogger logger("/primary_log.csv");
#endif

// Radio interrupt flag
volatile bool radioPacketReceived = false;

// LED debug patterns
unsigned long lastLedUpdate = 0;
uint8_t ledPattern = 0;  // 0=idle, 1=tx, 2=rx_good, 3=relay

// Display update
unsigned long lastDisplayUpdate = 0;
#define DISPLAY_INTERVAL 200  // Update display every 200ms

// Statistics reporting
unsigned long lastStatsReport = 0;
#define STATS_REPORT_INTERVAL 10000  // Print stats every 10 seconds

// Queue metrics logging (Requirements 6.1, 6.2)
unsigned long lastQueueMetricsLog = 0;
#define QUEUE_METRICS_LOG_INTERVAL 5000  // Log queue metrics every 5 seconds

// Radio error tracking (Requirements 13.2, 13.3)
struct RadioErrorStats {
    uint32_t transmission_failures;
    uint32_t consecutive_failures;
    uint32_t radio_resets;
    unsigned long last_reset_time;
};

RadioErrorStats radioErrors = {0};

// ═══════════════════════════════════════════════════════════════════
// RADIO INTERRUPT
// ═══════════════════════════════════════════════════════════════════
void IRAM_ATTR onRadioReceive() {
    radioPacketReceived = true;
}

// ═══════════════════════════════════════════════════════════════════
// RADIO ERROR HANDLING
// ═══════════════════════════════════════════════════════════════════
/**
 * Handle radio transmission with error recovery
 * 
 * Wraps radio transmission with retry logic and error handling.
 * Implements exponential backoff and radio reset after persistent failures.
 * 
 * Requirements: 13.2, 13.3
 * 
 * @param data Pointer to data buffer
 * @param len Length of data
 * @return true if transmission successful, false otherwise
 */
bool transmitWithErrorHandling(uint8_t* data, size_t len) {
    const int MAX_RETRIES = 3;
    const int INITIAL_BACKOFF_MS = 50;
    const int MAX_CONSECUTIVE_FAILURES = 5;
    
    int backoff_ms = INITIAL_BACKOFF_MS;
    
    // Attempt transmission with exponential backoff
    for (int attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        int state = radio.transmit(data, len);
        
        if (state == RADIOLIB_ERR_NONE) {
            // Success - reset consecutive failure counter
            radioErrors.consecutive_failures = 0;
            return true;
        }
        
        // Transmission failed
        radioErrors.transmission_failures++;
        radioErrors.consecutive_failures++;
        
        // Get RSSI and SNR for error context
        float rssi = radio.getRSSI();
        float snr = radio.getSNR();
        
        // Log radio error (Requirement 12.4)
        logRadioError(state, rssi, snr, attempt + 1, MAX_RETRIES + 1);
        
        // Check if we should reset radio after too many failures
        if (radioErrors.consecutive_failures >= MAX_CONSECUTIVE_FAILURES) {
            Serial.println("[RADIO ERROR] 5 consecutive failures - resetting radio");
            
            // Reset radio
            radio.reset();
            delay(100);
            
            // Re-initialize radio
            int initState = radio.begin(FREQ_MHZ, LORA_BANDWIDTH, LORA_SPREAD_FACTOR,
                                       LORA_CODING_RATE, LORA_SYNC_WORD, LORA_TX_POWER);
            
            if (initState == RADIOLIB_ERR_NONE) {
                radio.setCRC(true);
                radio.setDio1Action(onRadioReceive);
                radio.startReceive();
                
                Serial.println("[RADIO] Reset successful");
                radioErrors.radio_resets++;
                radioErrors.last_reset_time = millis();
                radioErrors.consecutive_failures = 0;
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

#ifdef ENABLE_RELAY
// ═══════════════════════════════════════════════════════════════════
// RELAY FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

/**
 * Forward packet to Secondary Heltec for relay
 * Builds UART packet with Fletcher-16 checksum and sends via Serial1
 */
void forwardToSecondary(AeroLoRaPacket* packet) {
    // Send UART packet to Secondary
    bool sent = sendUartPacket(Serial1, packet->src_id, packet->dest_id, 
                               packet->payload, packet->payload_len, &relayStats);
    
    if (sent) {
        relayStats.packets_forwarded++;
        lastRelayActivity = millis();
        
        // Update watchdog timers
        updateUartActivity(&watchdogTimers);
        updateRelayActivity(&watchdogTimers);
        
        #ifdef RELAY_DEBUG
        Serial.print("[RELAY] Forwarded packet to Secondary: src=");
        Serial.print(packet->src_id);
        Serial.print(" dest=");
        Serial.print(packet->dest_id);
        Serial.print(" len=");
        Serial.println(packet->payload_len);
        #endif
        
#ifdef ENABLE_FLIGHT_LOGGER
        // Log packet forward event
        logger.logRelayEvent(
            "FORWARD",
            relayStats.packets_overheard,
            relayStats.packets_forwarded,
            radio.getRSSI(),
            relayStats.uart_checksum_errors
        );
#endif
        
        // Activate relay mode if not already active
        if (!relayModeActive) {
            relayModeActive = true;
            relayModeStartTime = millis();
            
            // Log relay mode transition (Requirement 12.4)
            logRelayModeTransition(true, "weak signal or relay request detected");
            
#ifdef ENABLE_FLIGHT_LOGGER
            // Log relay mode activation
            logger.logRelayEvent(
                "ACTIVATED",
                relayStats.packets_overheard,
                relayStats.packets_forwarded,
                radio.getRSSI(),
                0
            );
#endif
        }
        
        // Update LED pattern to show relay activity
        ledPattern = 3;
        lastLedUpdate = millis();
    }
}

/**
 * Process UART data from Secondary Heltec
 * Receives relayed packets from QGC @ 902 MHz and forwards to flight controller
 */
void processSecondaryUart() {
    uint8_t src_id, dest_id;
    uint8_t payload[UART_MAX_PAYLOAD];
    
    // Try to receive a complete UART packet
    uint8_t len = receiveUartPacket(Serial1, src_id, dest_id, payload, UART_MAX_PAYLOAD, &relayStats);
    
    if (len > 0) {
        #ifdef RELAY_DEBUG
        Serial.print("[RELAY] Received from Secondary: src=");
        Serial.print(src_id);
        Serial.print(" dest=");
        Serial.print(dest_id);
        Serial.print(" len=");
        Serial.println(len);
        #endif

#ifdef ENABLE_FLIGHT_LOGGER
        // Log RX event from Secondary (Downlink from QGC)
        // Extract MAVLink fields from payload for logging
        uint8_t msgId = 0;
        uint32_t seq = 0;
        uint8_t sysId = 0;
        
        if (len >= 6) {
            if (payload[0] == 0xFE) {
                seq = payload[2];
                sysId = payload[3];
                msgId = payload[5];
            } else if (payload[0] == 0xFD) {
                seq = payload[4];
                sysId = payload[5];
                msgId = payload[7];
            }
        }
        
        logger.logPacket(
            seq,
            msgId,
            sysId,
            0.0, 0.0, // RSSI/SNR not available via UART
            relayModeActive,
            "RX_RELAY_DL", // Downlink from Relay
            len,
            0,
            protocol.getQueueDepth(),
            0
        );
#endif
        
        // Forward to flight controller via Serial2
        Serial2.write(payload, len);
        
        // Update UART statistics
        uartStats.fc_packets_sent++;
        uartStats.fc_bytes_sent += len;
        
        lastRelayActivity = millis();
        
        // Update watchdog timers
        updateUartActivity(&watchdogTimers);
        updateSecondaryResponse(&watchdogTimers);
        updateRelayActivity(&watchdogTimers);
    }
}

/**
 * Check relay timeout and deactivate if inactive for too long
 * 
 * Uses watchdog timer to monitor relay inactivity.
 * Requirements: 13.1
 */
void checkRelayTimeout() {
    // Check relay watchdog (30 second timeout)
    if (relayModeActive && !checkRelayWatchdog(&watchdogTimers)) {
        relayModeActive = false;
        
        // Update relay mode duration
        relayStats.relay_mode_duration_ms += (millis() - relayModeStartTime);
        
        // Log relay mode transition (Requirement 12.4)
        logRelayModeTransition(false, "30 second inactivity timeout");
        
#ifdef ENABLE_FLIGHT_LOGGER
        // Log relay mode deactivation
        logger.logRelayEvent(
            "DEACTIVATED",
            relayStats.packets_overheard,
            relayStats.packets_forwarded,
            radio.getRSSI(),
            0
        );
#endif
    }
    
    // Check Secondary watchdog (5 second timeout)
    if (relayModeActive && !checkSecondaryWatchdog(&watchdogTimers)) {
        // Secondary not responding - log warning but don't deactivate relay
        // (relay mode can still be useful even if Secondary is temporarily unresponsive)
        Serial.println("[RELAY] WARNING: Secondary not responding");
    }
}
#endif // ENABLE_RELAY

// ═══════════════════════════════════════════════════════════════════
// OLED DISPLAY UPDATE
// ═══════════════════════════════════════════════════════════════════
/**
 * Update OLED display with relay statistics
 * 
 * Shows:
 * - Relay mode status (DIRECT/RELAY)
 * - Relay target node ID (NODE_GROUND)
 * - Packet counts (overheard, forwarded, relayed)
 * - UART error indicators
 * 
 * Updates every 200ms (DISPLAY_INTERVAL)
 * 
 * Requirements: 12.3
 */
void updateDisplay() {
    DualBandStats stats = dualBandTransport.getStats();
    
    display.clearBuffer();
    display.setFont(u8g2_font_6x10_tf);
    
    // Title
    display.drawStr(0, 10, "D2 PRIMARY");
    display.drawLine(0, 12, 128, 12);
    
    char buf[32];
    
    // ESP-NOW status line
    if (stats.espnow_peer_reachable) {
        sprintf(buf, "ESP:%lu/%lu R:%d", 
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
    
    // Deduplication count
    sprintf(buf, "DUP:%lu", stats.duplicate_packets_dropped);
    display.drawStr(0, 60, buf);
    
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
            
        case 3: // Relay - double flash
            if (now - lastLedUpdate < 500) {
                digitalWrite(LED_PIN, ((now - lastLedUpdate) / 100) % 2);
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
    display.drawStr(0, 20, "Drone2 Primary");
    display.drawStr(0, 35, "Initializing...");
    display.sendBuffer();
    delay(500);
    
    // Initialize USB Serial for debugging
    Serial.begin(115200);
    delay(100);
    
#ifdef ENABLE_FLIGHT_LOGGER
    // Initialize flight logger
    if (logger.begin()) {
        #if DEBUG_LOGGING
        Serial.println("[LOGGER] Flight logging enabled");
        #endif
    } else {
        #if DEBUG_LOGGING
        Serial.println("[LOGGER] Flight logging failed to initialize");
        #endif
    }
#endif
    
    // Initialize Serial2 (Flight Controller UART)
    Serial2.begin(FC_BAUD, SERIAL_8N1, FC_RX, FC_TX);
    delay(100);
    
#ifdef ENABLE_RELAY
    // Initialize Serial1 (Secondary Heltec UART)
    Serial1.begin(SECONDARY_BAUD, SERIAL_8N1, SECONDARY_RX, SECONDARY_TX);
    delay(100);
#endif // ENABLE_RELAY
    
    // Verify UART initialization
#ifdef ENABLE_RELAY
    if (Serial2 && Serial1) {
        display.clearBuffer();
        display.setFont(u8g2_font_6x10_tf);
        display.drawStr(0, 20, "Drone2 Primary");
        display.drawStr(0, 35, "FC UART: OK");
        display.drawStr(0, 45, "SEC UART: OK");
#else
    if (Serial2) {
        display.clearBuffer();
        display.setFont(u8g2_font_6x10_tf);
        display.drawStr(0, 20, "Drone2 Primary");
        display.drawStr(0, 35, "FC UART: OK");
#endif // ENABLE_RELAY
        display.sendBuffer();
        delay(500);
    } else {
        display.clearBuffer();
        display.setFont(u8g2_font_6x10_tf);
        display.drawStr(0, 20, "Drone2 Primary");
        display.drawStr(0, 35, "UART INIT FAILED");
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
    
    // Initialize relay state
    relayModeActive = false;
    lastRelayActivity = 0;
    relayModeStartTime = 0;
    memset(&relayStats, 0, sizeof(relayStats));
    
    // Initialize watchdog timers
    initWatchdogTimers(&watchdogTimers);
    
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
    
    // Initialize protocol with NODE_DRONE2 identity
    protocol.begin(NODE_DRONE2);
    
    // Initialize ESP-NOW Transport
    #if DEBUG_LOGGING
    Serial.println("[PRIMARY] Initializing ESP-NOW...");
    #endif
    if (!espnowTransport.begin(drone1_mac)) {
        #if DEBUG_LOGGING
        Serial.println("[PRIMARY] ERROR: ESP-NOW initialization failed");
        Serial.println("[PRIMARY] Continuing with LoRa only");
        #endif
        
        display.clearBuffer();
        display.drawStr(0, 20, "ESP-NOW FAILED");
        display.drawStr(0, 35, "LoRa only mode");
        display.sendBuffer();
        delay(2000);
    } else {
        #if DEBUG_LOGGING
        Serial.println("[PRIMARY] ESP-NOW initialized successfully");
        Serial.print("[PRIMARY] Peer MAC: ");
        for (int i = 0; i < 6; i++) {
            Serial.printf("%02X", drone1_mac[i]);
            if (i < 5) Serial.print(":");
        }
        Serial.println();
        #endif
    }
    
    // Initialize Dual-Band Transport
    #if DEBUG_LOGGING
    Serial.println("[PRIMARY] Initializing Dual-Band Transport...");
    #endif
    if (!dualBandTransport.begin(NODE_RELAY)) {
        #if DEBUG_LOGGING
        Serial.println("[PRIMARY] ERROR: Dual-Band Transport initialization failed");
        #endif
        while(true) {
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            delay(200);
        }
    }
    #if DEBUG_LOGGING
    Serial.println("[PRIMARY] Dual-Band Transport initialized successfully");
    #endif
    
    // Show ready on display
    display.clearBuffer();
    display.drawStr(0, 10, "Drone2 Primary");
    display.drawStr(0, 25, "READY!");
    display.drawStr(0, 40, "ESP-NOW: 2.4GHz");
    display.drawStr(0, 55, "LoRa: 930MHz");
    display.sendBuffer();
    delay(1000);
    
#ifdef ENABLE_RELAY
    #ifdef ALWAYS_RELAY_MODE
    #if DEBUG_LOGGING
    Serial.println("[RELAY] ALWAYS_RELAY_MODE ACTIVE");
    #endif
    #endif
#endif // ENABLE_RELAY
    
    digitalWrite(LED_PIN, LOW);
}

// ═══════════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════════

void loop() {
    unsigned long now = millis();
    
    // Process dual-band transport (handles ESP-NOW and LoRa coordination)
    dualBandTransport.process();
    
    // Check for ESP-NOW packets (RX_DUALBAND)
    uint8_t espNowBuffer[256];
    uint8_t espNowLen = dualBandTransport.receive(espNowBuffer, 256);
    if (espNowLen > 0) {
        // Received ESP-NOW packet from Drone1
        #ifdef ENABLE_FLIGHT_LOGGER
        // RATE LIMIT: Only log every 200ms (5Hz)
        static unsigned long lastEspNowLog = 0;
        if (millis() - lastEspNowLog > 200) {
            logger.logPacket(
                0, 0, NODE_DRONE1, 0, 0, // RSSI/SNR not available via receive()
                relayModeActive, "RX_DUALBAND", espNowLen, 0, 0, 0
            );
            lastEspNowLog = millis();
        }
        #endif
        
        // Forward to FC (if needed) or handle
        // Assuming ESP-NOW packets are same format as LoRa
        AeroLoRaPacket* packet = (AeroLoRaPacket*)espNowBuffer;
        if (packet->dest_id == NODE_DRONE2 || packet->dest_id == AERO_BROADCAST) {
            protocol.handleReceivedPacket(packet);
        }
    }
    
    // Update LED pattern
    updateLedPattern();
    
    // Update OLED display
    if (now - lastDisplayUpdate > DISPLAY_INTERVAL) {
        updateDisplay();
        lastDisplayUpdate = now;
    }
    
    // Handle radio reception
    if (radioPacketReceived) {
        radioPacketReceived = false;
        
        // Read packet
        uint8_t rxBuffer[256];
        int packetSize = radio.getPacketLength();
        if (packetSize > 0 && packetSize <= 256) {
            int state = radio.readData(rxBuffer, packetSize);
            
            if (state == RADIOLIB_ERR_NONE) {
                // Pass to protocol for processing
                AeroLoRaPacket* packet = (AeroLoRaPacket*)rxBuffer;
                
                // Get RSSI and SNR
                float rssi = radio.getRSSI();
                float snr = radio.getSNR();
                
                // Log RX_LORA (Standardized)
                #ifdef ENABLE_FLIGHT_LOGGER
                // RATE LIMIT: Only log every 200ms (5Hz)
                static unsigned long lastRxLog = 0;
                if (millis() - lastRxLog > 200) {
                    logger.logPacket(
                        0, 0, packet->src_id, rssi, snr,
                        relayModeActive, "RX_LORA", packetSize, 0, 0, 0
                    );
                    lastRxLog = millis();
                }
                #endif
                
                // Check if packet is for us (normal processing)
                if (packet->dest_id == NODE_DRONE2 || packet->dest_id == AERO_BROADCAST) {
                    // Normal processing - forward to flight controller
                    protocol.handleReceivedPacket(packet);
                }
                
                #ifdef ENABLE_RELAY
                else {
                    // Packet is NOT for us - check if we should relay it
                    
                    // Check if relay request flag is set in packet header
                    bool relayRequested = (packet->header & RELAY_REQUEST_FLAG) != 0;
                    
                    // Track all packets overheard from other nodes
                    relayStats.packets_overheard++;
                    
                    #ifdef ENABLE_FLIGHT_LOGGER
                    // Log packet overhear event
                    logger.logPacket(
                        0,                              // sequence_number (not available)
                        0,                              // message_id (not available)
                        packet->src_id,                 // system_id
                        rssi,                           // rssi_dbm
                        snr,                            // snr_db
                        relayModeActive,                // relay_active
                        "OVERHEAR",                     // event
                        packet->payload_len,            // packet_size
                        0,                              // tx_timestamp (unknown)
                        0,                              // queue_depth (N/A)
                        relayStats.uart_checksum_errors // errors
                    );
                    #endif
                    
                    #ifdef ALWAYS_RELAY_MODE
                    // In ALWAYS_RELAY_MODE, forward all packets to QGC regardless of RSSI or flags
                    bool shouldRelay = (packet->dest_id == NODE_GROUND);
                    #else
                    // In normal mode (passive detection), relay if:
                    // 1. Packet is addressed to QGC (NODE_GROUND), AND
                    // 2. Either RSSI is weak (< -95 dBm) OR relay was explicitly requested
                    bool shouldRelay = (packet->dest_id == NODE_GROUND) && 
                                      (rssi < RELAY_RSSI_THRESHOLD || relayRequested);
                    #endif
                    
                    if (shouldRelay) {
                        // Forward to Secondary for relay
                        forwardToSecondary(packet);
                        
                        // Track weak signal detections (RSSI-based relay triggers)
                        if (rssi < RELAY_RSSI_THRESHOLD) {
                            relayStats.weak_signals_detected++;
                            
                            #ifdef ENABLE_FLIGHT_LOGGER
                            // Log weak signal detection
                            logger.logRelayEvent(
                                "WEAK_SIGNAL",
                                relayStats.packets_overheard,
                                relayStats.packets_forwarded,
                                rssi,
                                0
                            );
                            #endif
                        }
                        
                        // Log weak signal detection (Requirement 12.4)
                        logWeakSignalDetection(rssi, packet->src_id, relayRequested);
                    }
                }
                #endif // ENABLE_RELAY
            } else if (state == RADIOLIB_ERR_CRC_MISMATCH) {
                // CRC Error
                #ifdef ENABLE_FLIGHT_LOGGER
                logger.logPacket(0, 0, 0, radio.getRSSI(), radio.getSNR(), relayModeActive, "CRC_ERROR", 0, 0, 0, 0);
                #endif
            } else {
                 // Other error or Noise Floor check
                #ifdef ENABLE_FLIGHT_LOGGER
                // Log NOISE_FLOOR every 200ms
                static unsigned long lastNoiseLog = 0;
                if (millis() - lastNoiseLog > 200) {
                    logger.logPacket(0, 0, 0, radio.getRSSI(), 0, relayModeActive, "NOISE_FLOOR", 0, 0, 0, 0);
                    lastNoiseLog = millis();
                }
                #endif
            }
        }
        
        // Return to RX mode
        radio.startReceive();
    }
    
    // Process protocol
    protocol.process();
    
#ifdef ENABLE_RELAY
    // Process UART from Secondary (relayed packets from QGC @ 902 MHz)
    processSecondaryUart();
    
    // Check relay timeout
    checkRelayTimeout();
#endif // ENABLE_RELAY
    
    // Handle UART data from Flight Controller (Serial2)
    while (Serial2.available() && uartRxIndex < sizeof(uartRxBuffer)) {
        // Buffer overflow protection
        if (uartRxIndex >= 256) {
            #if DEBUG_LOGGING
            Serial.println("[PRIMARY] UART buffer full!");
            #endif
            break;
        }
        
        uartRxBuffer[uartRxIndex++] = Serial2.read();
        lastUartRx = now;
        
        // Update UART statistics
        uartStats.fc_bytes_received++;
        uartStats.last_fc_rx = now;
    }
    
    // Update fc_connected status
    uartStats.fc_connected = (now - uartStats.last_fc_rx) < 5000;
    
    // Process UART buffer for complete MAVLink packets
    if (uartRxIndex > 0 && (now - lastUartRx) >= 40) {
        int16_t result = findCompleteMavlinkPacket(uartRxBuffer, uartRxIndex);
        
        if (result > 0) {
            // Complete packet found
            uint16_t packetLen = (uint16_t)result;
            
            // Send packet to Drone1 via Dual-Band Transport (ESP-NOW + LoRa)
            bool sent = dualBandTransport.send(uartRxBuffer, packetLen, NODE_DRONE);
            
#ifdef ENABLE_FLIGHT_LOGGER
            // Log TX event
            uint8_t msgId = 0;
            uint32_t seq = 0;
            uint8_t sysId = 0;
            
            if (packetLen >= 6) {
                if (uartRxBuffer[0] == 0xFE) {
                    seq = uartRxBuffer[2];
                    sysId = uartRxBuffer[3];
                    msgId = uartRxBuffer[5];
                } else if (uartRxBuffer[0] == 0xFD) {
                    sysId = uartRxBuffer[5];
                    msgId = uartRxBuffer[9];
                }
            }
            
            DualBandStats dbStats = dualBandTransport.getStats();
            const char* event = sent ? "TX_DUAL" : "TX_DROP";
            if (sent && dbStats.espnow_peer_reachable) {
                event = "TX_ESPNOW";
            } else if (sent) {
                event = "TX_LORA";
            }
            
            // Rate limit ESP-NOW/DualBand logging to 5Hz
            bool shouldLog = false;
            if (strcmp(event, "TX_LORA") == 0 || strcmp(event, "TX_DROP") == 0) {
                shouldLog = true; // Always log LoRa or Drops
            } else {
                static unsigned long lastTxLog = 0;
                if (millis() - lastTxLog > 200) {
                    shouldLog = true;
                    lastTxLog = millis();
                }
            }

            if (shouldLog) {
                logger.logPacket(
                    seq,
                    msgId,
                    sysId,
                    0, 0,
                    relayModeActive,
                    event,
                    packetLen,
                    millis(),
                    protocol.getQueueDepth(),
                    sent ? 0 : 1
                );
            }
#endif
            
            #if DEBUG_LOGGING
            Serial.print("[PRIMARY] Sent MAVLink packet (");
            Serial.print(packetLen);
            Serial.print(" bytes) to NODE_DRONE: ");
            Serial.println(sent ? "SUCCESS" : "FAILED");
            #endif
            
            // Update UART statistics
            uartStats.fc_packets_received++;
            
            // Remove processed packet from buffer
            if (packetLen < uartRxIndex) {
                memmove(uartRxBuffer, uartRxBuffer + packetLen, uartRxIndex - packetLen);
                uartRxIndex -= packetLen;
            } else {
                uartRxIndex = 0;
            }
            
            // Update LED to show TX activity
            ledPattern = 1;
            lastLedUpdate = now;
            
        } else if (result < -1) {
            // Skip garbage bytes
            uint16_t skipBytes = (uint16_t)(-result);
            memmove(uartRxBuffer, uartRxBuffer + skipBytes, uartRxIndex - skipBytes);
            uartRxIndex -= skipBytes;
            
        } else if (result == -1) {
            // Invalid data - clear buffer
            uartRxIndex = 0;
            memset(uartRxBuffer, 0, sizeof(uartRxBuffer));
            
        } else {
            // Incomplete packet
            if (uartRxIndex >= 250) {
                uartRxIndex = 0;
                memset(uartRxBuffer, 0, sizeof(uartRxBuffer));
            }
        }
    }
    
    // Handle received data from Drone1 (via dual-band transport with deduplication)
    uint8_t rxBuffer[255];
    uint8_t len = dualBandTransport.receive(rxBuffer, 255);
    
    if (len > 0) {
        // Forward received data to flight controller via UART
        Serial2.write(rxBuffer, len);
        
#ifdef ENABLE_FLIGHT_LOGGER
        // Log forwarding to Flight Controller
        uint8_t msgId = (rxBuffer[0] == 0xFE) ? rxBuffer[5] : rxBuffer[7];
        uint8_t sysId = (rxBuffer[0] == 0xFE) ? rxBuffer[3] : rxBuffer[5];
        uint32_t seq = (rxBuffer[0] == 0xFE) ? rxBuffer[2] : rxBuffer[4];
        
        logger.logPacket(
            seq,
            msgId,
            sysId,
            0, 0,
            relayModeActive,
            "TX_FC_SERIAL",
            len,
            millis(),
            0, 0
        );
#endif
        
        // Update UART statistics
        uartStats.fc_packets_sent++;
        uartStats.fc_bytes_sent += len;
        
        digitalWrite(LED_PIN, HIGH);
        delay(1);
        digitalWrite(LED_PIN, LOW);
    }
    
    // Print statistics periodically
    if (now - lastStatsReport > STATS_REPORT_INTERVAL) {
#ifdef ENABLE_RELAY
        #if DEBUG_LOGGING
        printRelayStats(relayStats, "Drone2 Primary");
        #endif
#else
        // Print basic stats without relay info
        AeroLoRaStats stats = protocol.getStats();
        #if DEBUG_LOGGING
        Serial.println("=== Drone2 Primary Stats ===");
        Serial.printf("TX: %lu, RX: %lu, RSSI: %.1f, SNR: %.1f\n",
                     stats.packets_sent, stats.packets_received, 
                     stats.avg_rssi, stats.avg_snr);
        #endif
#endif // ENABLE_RELAY
        lastStatsReport = now;
    }
    
#ifdef ENABLE_FLIGHT_LOGGER
    // Periodic queue metrics logging
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
    
#ifdef ENABLE_FLIGHT_LOGGER
    // Handle serial commands for flight logger (DUMP, SIZE, CLEAR, HELP)
    // Uses USB Serial only - no interference with FC UART or Secondary UART
    logger.handleSerialCommands();
#endif
}
