/**
 * Drone2 Secondary - UART-to-LoRa Bridge @ 902 MHz
 * 
 * Simple bridge between Drone2 Primary (via UART) and QGC (via LoRa @ 902 MHz).
 * This firmware runs on the Secondary Heltec V3 module in Drone2's dual-Heltec configuration.
 * 
 * Purpose:
 * - Receive packets from Primary via UART (packets overheard from Drone1 @ 915 MHz)
 * - Relay packets to QGC @ 902 MHz using AeroLoRa protocol with CSMA/CA
 * - Receive packets from QGC @ 902 MHz
 * - Forward packets to Primary via UART (for delivery to Drone1)
 * 
 * Design Philosophy:
 * - Transparent forwarding (no MAVLink processing)
 * - Simple UART-to-LoRa bridge
 * - Minimal latency (<10ms per hop)
 * - Priority queue integration for relayed packets
 * - CSMA/CA collision avoidance @ 902 MHz
 * 
 * Hardware Configuration:
 * - Heltec WiFi LoRa 32 V3 @ 902 MHz
 * - UART to Primary: Serial1 (GPIO 2=TX, GPIO 1=RX) @ 115200 baud
 * - LoRa to QGC: 902 MHz, SF7, BW125, CR5
 * 
 * UART Connection (crossover to Primary):
 * - Secondary GPIO 2 (TX) → Primary GPIO 2 (RX)
 * - Secondary GPIO 1 (RX) → Primary GPIO 1 (TX)
 * - GND → GND
 * 
 * NOTE: This entire file requires ENABLE_RELAY to be defined.
 * Without ENABLE_RELAY, this firmware should not be compiled.
 * 
 * Compile Flags:
 * - NODE_ID=3 (NODE_RELAY)
 * - ENABLE_RELAY (REQUIRED)
 * - ALWAYS_RELAY_MODE (for testing)
 */

#ifndef ENABLE_RELAY
#error "drone2_secondary.cpp requires ENABLE_RELAY to be defined. Use env:drone2_secondary build environment."
#endif

#include <Arduino.h>
#include <RadioLib.h>
#include <SPI.h>
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

// UART to Primary (Serial1) - Crossover connection
#define PRIMARY_TX       2   // GPIO 2 = TX (connects to Primary's GPIO 2 = RX)
#define PRIMARY_RX       1   // GPIO 1 = RX (connects to Primary's GPIO 1 = TX)
#define PRIMARY_BAUD     115200

// ═══════════════════════════════════════════════════════════════════
// RADIO CONFIGURATION - 902 MHz Relay Link
// ═══════════════════════════════════════════════════════════════════
#define FREQ_MHZ            902.0   // Keep at 902 MHz (separate from 930 MHz direct link)
#define LORA_BANDWIDTH      125.0   // 125 kHz bandwidth
#define LORA_SPREAD_FACTOR  7       // SF7 for balance of speed and range
#define LORA_CODING_RATE    5       // 4/5 coding rate
#define LORA_SYNC_WORD      0x12    // Same sync word as main network
#define LORA_TX_POWER       4       // 4 dBm (~2.5 mW) - reduced to make jammer more effective

// ═══════════════════════════════════════════════════════════════════
// PROTOCOL CONFIGURATION
// ═══════════════════════════════════════════════════════════════════
#define TDMA_SLOT_DURATION_MS   0       // No TDMA for relay (always transmit)
#define RELAY_SLOT_OFFSET       0       // No slot offset

// ═══════════════════════════════════════════════════════════════════
// GLOBAL OBJECTS
// ═══════════════════════════════════════════════════════════════════
SX1262 radio = new Module(LORA_CS, LORA_DIO1, LORA_RST, LORA_BUSY);
AeroLoRaProtocol protocol(&radio, RELAY_SLOT_OFFSET, TDMA_SLOT_DURATION_MS);

// Dual-Band Transport Components
ESPNowTransport espnowTransport;
DualBandTransport dualBandTransport(&espnowTransport, &protocol);

// Ground MAC Address (QGC 902 MHz)
uint8_t ground_mac[6] = {0x24, 0x58, 0x7C, 0x5C, 0xB9, 0xC0};

// Relay statistics
RelayStats stats = {0};

#ifdef ENABLE_FLIGHT_LOGGER
// Flight logger
FlightLogger logger("/secondary_log.csv");
#endif

// Radio interrupt flag
volatile bool radioPacketReceived = false;

// Watchdog timers (Requirements 13.1, 13.5)
WatchdogTimers watchdogTimers;

// LED status
unsigned long lastLedUpdate = 0;
uint8_t ledPattern = 0;  // 0=idle, 1=tx, 2=rx

// Statistics display
unsigned long lastStatsTime = 0;
#define STATS_INTERVAL 10000  // Print stats every 10 seconds

// Queue metrics logging (Requirements 6.1, 6.2)
unsigned long lastQueueMetricsLog = 0;
#define QUEUE_METRICS_LOG_INTERVAL 5000  // Log queue metrics every 5 seconds

// CSMA/CA configuration
#define CSMA_RSSI_THRESHOLD     -90.0   // dBm - channel busy if RSSI above this
#define CSMA_BACKOFF_MIN_MS     10      // Minimum backoff time
#define CSMA_BACKOFF_MAX_MS     50      // Maximum backoff time
#define CSMA_MAX_ATTEMPTS       5       // Maximum backoff attempts

// ═══════════════════════════════════════════════════════════════════
// FORWARD DECLARATIONS
// ═══════════════════════════════════════════════════════════════════
void processUartToLoRa();
void processLoRaToUart();
void handleRadioInterrupt();
void updateLed();

// ═══════════════════════════════════════════════════════════════════
// RADIO INTERRUPT HANDLER
// ═══════════════════════════════════════════════════════════════════
void IRAM_ATTR onRadioReceive() {
    radioPacketReceived = true;
}

// ═══════════════════════════════════════════════════════════════════
// CSMA/CA COLLISION AVOIDANCE
// ═══════════════════════════════════════════════════════════════════
/**
 * Check if channel is clear for transmission (CSMA/CA)
 * 
 * Implements Carrier Sense Multiple Access with Collision Avoidance.
 * Checks if the channel is busy by measuring RSSI. If channel is busy,
 * waits for a random backoff period and retries.
 * 
 * Algorithm:
 * 1. Check channel RSSI
 * 2. If RSSI < threshold (-90 dBm), channel is clear → transmit
 * 3. If RSSI >= threshold, channel is busy → backoff
 * 4. Wait random time (10-50 ms)
 * 5. Retry up to 5 times
 * 6. If all attempts fail, give up (packet will be dropped)
 * 
 * Requirements: 3.2, 10.3, 10.4, 10.5
 * 
 * @return true if channel is clear, false if channel busy after max attempts
 */
bool checkChannelClear() {
    for (int attempt = 0; attempt < CSMA_MAX_ATTEMPTS; attempt++) {
        // Check channel RSSI
        float rssi = radio.getRSSI();
        
        if (rssi < CSMA_RSSI_THRESHOLD) {
            // Channel is clear
            if (attempt > 0) {
                #ifdef RELAY_DEBUG
                Serial.print("[CSMA/CA] Channel clear after ");
                Serial.print(attempt);
                Serial.println(" backoff attempts");
                #endif
            }
            return true;
        }
        
        // Channel is busy - backoff
        #ifdef RELAY_DEBUG
        Serial.print("[CSMA/CA] Channel busy (RSSI=");
        Serial.print(rssi, 1);
        Serial.print(" dBm), attempt ");
        Serial.print(attempt + 1);
        Serial.print("/");
        Serial.println(CSMA_MAX_ATTEMPTS);
        #endif
        
        // Random backoff (10-50 ms)
        int backoff_ms = random(CSMA_BACKOFF_MIN_MS, CSMA_BACKOFF_MAX_MS + 1);
        delay(backoff_ms);
    }
    
    // Max attempts reached - channel still busy
    Serial.println("[CSMA/CA] WARNING: Channel busy after max attempts, giving up");
    return false;
}

// ═══════════════════════════════════════════════════════════════════
// RADIO ERROR HANDLING
// ═══════════════════════════════════════════════════════════════════
/**
 * Radio error statistics
 * Track consecutive failures for radio reset logic
 */
struct RadioErrorStats {
    uint32_t transmission_failures;
    uint32_t consecutive_failures;
    uint32_t radio_resets;
    unsigned long last_reset_time;
};

RadioErrorStats radioErrors = {0};

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

// ═══════════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════════
void setup() {
    // Initialize debug serial
    Serial.begin(115200);
    delay(1000);
    
    #if DEBUG_LOGGING
    Serial.println("═══════════════════════════════════════════════════════");
    Serial.println("Drone2 Secondary - UART-to-LoRa Bridge @ 902 MHz");
    Serial.println("═══════════════════════════════════════════════════════");
    #endif
    
    // Initialize LED
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);
    
    // Initialize UART to Primary (Serial1)
    // GPIO 2=TX, GPIO 1=RX (crossover connection to Primary)
    Serial1.begin(PRIMARY_BAUD, SERIAL_8N1, PRIMARY_RX, PRIMARY_TX);
    #if DEBUG_LOGGING
    Serial.println("[UART] Initialized Serial1 @ 115200 baud");
    Serial.println("[UART] GPIO 2=TX (to Primary RX), GPIO 1=RX (from Primary TX)");
    #endif
    
    // Initialize SPI for LoRa radio
    SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_CS);
    
    // Initialize LoRa radio @ 902 MHz
    #if DEBUG_LOGGING
    Serial.print("[RADIO] Initializing SX1262 @ ");
    Serial.print(FREQ_MHZ, 1);
    Serial.println(" MHz...");
    #endif
    
    int state = radio.begin(FREQ_MHZ, LORA_BANDWIDTH, LORA_SPREAD_FACTOR, 
                           LORA_CODING_RATE, LORA_SYNC_WORD, LORA_TX_POWER);
    
    if (state != RADIOLIB_ERR_NONE) {
        #if DEBUG_LOGGING
        Serial.print("[ERROR] Radio initialization failed: ");
        Serial.println(state);
        #endif
        while (true) {
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            delay(100);
        }
    }
    
    #if DEBUG_LOGGING
    Serial.println("[RADIO] SX1262 initialized successfully");
    #endif
    
    // Enable hardware CRC
    radio.setCRC(true);
    #if DEBUG_LOGGING
    Serial.println("[RADIO] Hardware CRC enabled");
    #endif
    
    // Set up interrupt-driven receive
    radio.setDio1Action(onRadioReceive);
    state = radio.startReceive();
    
    if (state != RADIOLIB_ERR_NONE) {
        #if DEBUG_LOGGING
        Serial.print("[ERROR] Failed to start receive: ");
        Serial.println(state);
        #endif
        while (true) {
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            delay(100);
        }
    }
    
    #if DEBUG_LOGGING
    Serial.println("[RADIO] Interrupt-driven receive enabled");
    #endif
    
    // Initialize AeroLoRa protocol
    protocol.begin(NODE_RELAY);  // Special node ID for relay
    #if DEBUG_LOGGING
    Serial.println("[PROTOCOL] AeroLoRa protocol initialized (NODE_RELAY=3)");
    #endif
    
    // Initialize ESP-NOW Transport
    #if DEBUG_LOGGING
    Serial.println("[SECONDARY] Initializing ESP-NOW...");
    #endif
    if (!espnowTransport.begin(ground_mac)) {
        #if DEBUG_LOGGING
        Serial.println("[SECONDARY] ERROR: ESP-NOW initialization failed");
        Serial.println("[SECONDARY] Continuing with LoRa only");
        #endif
    } else {
        #if DEBUG_LOGGING
        Serial.println("[SECONDARY] ESP-NOW initialized successfully");
        Serial.print("[SECONDARY] Peer MAC: ");
        for (int i = 0; i < 6; i++) {
            Serial.printf("%02X", ground_mac[i]);
            if (i < 5) Serial.print(":");
        }
        Serial.println();
        #endif
    }
    
    // Initialize Dual-Band Transport
    #if DEBUG_LOGGING
    Serial.println("[SECONDARY] Initializing Dual-Band Transport...");
    #endif
    if (!dualBandTransport.begin(NODE_RELAY)) {
        #if DEBUG_LOGGING
        Serial.println("[SECONDARY] ERROR: Dual-Band Transport initialization failed");
        #endif
        while(true) {
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            delay(200);
        }
    }
    #if DEBUG_LOGGING
    Serial.println("[SECONDARY] Dual-Band Transport initialized successfully");
    #endif
    
    // Initialize watchdog timers
    initWatchdogTimers(&watchdogTimers);
    
    #ifdef ENABLE_FLIGHT_LOGGER
    // Initialize flight logger
    #if DEBUG_LOGGING
    Serial.println("[LOGGER] Initializing flight logger...");
    #endif
    if (logger.begin()) {
        #if DEBUG_LOGGING
        Serial.println("[LOGGER] Flight logger initialized successfully");
        #endif
    } else {
        #if DEBUG_LOGGING
        Serial.println("[LOGGER] WARNING: Flight logger initialization failed");
        #endif
    }
    #endif
    
    // Print configuration summary
    #if DEBUG_LOGGING
    Serial.println("═══════════════════════════════════════════════════════");
    Serial.println("Configuration:");
    Serial.print("  Frequency:        "); Serial.print(FREQ_MHZ, 1); Serial.println(" MHz");
    Serial.print("  Bandwidth:        "); Serial.print(LORA_BANDWIDTH, 0); Serial.println(" kHz");
    Serial.print("  Spreading Factor: SF"); Serial.println(LORA_SPREAD_FACTOR);
    Serial.print("  Coding Rate:      4/"); Serial.println(LORA_CODING_RATE);
    Serial.print("  Sync Word:        0x"); Serial.println(LORA_SYNC_WORD, HEX);
    Serial.print("  TX Power:         "); Serial.print(LORA_TX_POWER); Serial.println(" dBm");
    Serial.print("  UART Baud:        "); Serial.println(PRIMARY_BAUD);
    Serial.println("═══════════════════════════════════════════════════════");
    #endif
    
    #ifdef ALWAYS_RELAY_MODE
    #if DEBUG_LOGGING
    Serial.println("[MODE] ALWAYS_RELAY_MODE ACTIVE");
    Serial.println("[MODE] All packets from Primary will be relayed to QGC");
    #endif
    #endif
    
    #if DEBUG_LOGGING
    Serial.println("[READY] Secondary bridge ready");
    Serial.println("═══════════════════════════════════════════════════════");
    #endif
    
    // Blink LED to indicate ready
    for (int i = 0; i < 3; i++) {
        digitalWrite(LED_PIN, HIGH);
        delay(100);
        digitalWrite(LED_PIN, LOW);
        delay(100);
    }
}

// ═══════════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════════
void loop() {
    // Process dual-band transport (handles ESP-NOW and LoRa coordination)
    dualBandTransport.process();
    
    // Process UART → LoRa (from Primary to QGC)
    // Receives packets from Primary and enqueues them to AeroLoRa protocol
    // Priority is automatically determined by extracting MAVLink message ID
    processUartToLoRa();
    
    // Process LoRa → UART (from QGC to Primary)
    // Receives packets from QGC and forwards them to Primary via UART
    processLoRaToUart();
    
    // Process radio interrupt
    // Handles received packets from QGC @ 902 MHz
    if (radioPacketReceived) {
        handleRadioInterrupt();
    }
    
    // Process AeroLoRa protocol queue
    // Dequeues and transmits packets in priority order:
    // - Tier 0 (Critical): HEARTBEAT, COMMAND_LONG, SET_MODE, etc. - 1s timeout
    // - Tier 1 (Important): GPS_RAW_INT, ATTITUDE, GLOBAL_POSITION_INT - 2s timeout
    // - Tier 2 (Routine): All other telemetry - 5s timeout
    // 
    // Priority queue ensures critical commands are never blocked by telemetry.
    // Staleness detection automatically drops old packets that exceed timeout.
    // 
    // Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
    protocol.process();
    
    // Update LED status
    updateLed();
    
    // Check watchdog timers (Requirements 13.1, 13.5)
    checkUartWatchdog(&watchdogTimers);
    
    #ifdef ENABLE_FLIGHT_LOGGER
    // Handle flight logger serial commands (DUMP, SIZE, CLEAR, HELP)
    // Uses USB Serial (Serial) only - no interference with Primary UART (Serial1)
    logger.handleSerialCommands();
    #endif
    
    // Print statistics periodically
    if (millis() - lastStatsTime > STATS_INTERVAL) {
        #if DEBUG_LOGGING
        printRelayStats(stats, "Secondary");
        #endif
        lastStatsTime = millis();
    }
    
#ifdef ENABLE_FLIGHT_LOGGER
    // Periodic queue metrics logging
    if (millis() - lastQueueMetricsLog > QUEUE_METRICS_LOG_INTERVAL) {
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
        lastQueueMetricsLog = millis();
    }
#endif
}

// ═══════════════════════════════════════════════════════════════════
// UART → LoRa FORWARDING (Primary to QGC)
// ═══════════════════════════════════════════════════════════════════
/**
 * Process UART → LoRa forwarding
 * 
 * Receives UART packets from Primary (packets overheard from Drone1 @ 915 MHz)
 * and relays them to QGC @ 902 MHz using AeroLoRa protocol with CSMA/CA.
 * 
 * Flow:
 * 1. Receive UART packet from Primary using receiveUartPacket()
 * 2. Validate checksum (done by receiveUartPacket)
 * 3. Extract payload (MAVLink data)
 * 4. Enqueue to AeroLoRa protocol (priority queuing based on MAVLink message ID)
 * 5. Track statistics
 * 
 * CSMA/CA Integration:
 * - The AeroLoRa protocol's process() method will dequeue and transmit packets
 * - CSMA/CA is implemented at the protocol level (existing AeroLoRa behavior)
 * - Channel sensing happens before each transmission attempt
 * - Random backoff (10-50 ms) when channel is busy
 * - Maximum 5 backoff attempts before giving up
 * 
 * Error handling:
 * - Checksum errors: Logged by receiveUartPacket, packet discarded
 * - Buffer overflows: Logged by receiveUartPacket, state machine reset
 * - Invalid payload: Logged and discarded
 * - Queue full: Packet dropped, logged
 * 
 * Requirements: 3.2, 3.3, 4.4, 10.3, 10.4, 10.5, 12.2
 */
void processUartToLoRa() {
    uint8_t src_id, dest_id;
    uint8_t payload[UART_MAX_PAYLOAD];
    
    // Receive UART packet from Primary
    uint8_t len = receiveUartPacket(Serial1, src_id, dest_id, payload, UART_MAX_PAYLOAD, &stats);
    
    if (len > 0) {
        // Valid packet received from Primary
        // This is a packet that Primary overheard from Drone1 and wants us to relay
        
        // Update watchdog timers
        updateUartActivity(&watchdogTimers);
        
        #ifdef ENABLE_FLIGHT_LOGGER
        // Log UART RX event
        logger.logPacket(
            0,                              // sequence_number (unknown from UART)
            0,                              // message_id (unknown, raw UART)
            src_id,                         // system_id (from UART packet)
            0.0,                            // rssi_dbm (N/A for UART)
            0.0,                            // snr_db (N/A for UART)
            true,                           // relay_active (always true)
            "UART_RX",                      // event
            len,                            // packet_size
            0,                              // tx_timestamp (unknown)
            0,                              // queue_depth (N/A)
            stats.uart_checksum_errors      // errors
        );
        #endif
        
        #ifdef RELAY_DEBUG
        #if DEBUG_LOGGING
        Serial.print("[UART→LoRa] Received packet from Primary: ");
        Serial.print("src="); Serial.print(src_id);
        Serial.print(" dest="); Serial.print(dest_id);
        Serial.print(" len="); Serial.println(len);
        #endif
        #endif
        
        // Enqueue to AeroLoRa protocol for transmission to QGC @ 902 MHz
        // The protocol will:
        // 1. Determine priority based on MAVLink message ID
        // 2. Enqueue to appropriate tier (0=critical, 1=important, 2=routine)
        // 3. Transmit from highest priority tier first
        // 
        // Send via Dual-Band Transport (ESP-NOW + LoRa with CSMA/CA)
        // - ESP-NOW: All messages when in range
        // - LoRa: Essential messages only with CSMA/CA collision avoidance
        // - Automatic deduplication on receive side
        bool sent = dualBandTransport.send(payload, len, dest_id);
        
        if (sent) {
            stats.packets_relayed_to_qgc++;
            
            #ifdef ENABLE_FLIGHT_LOGGER
            // Log TX event
            DualBandStats dbStats = dualBandTransport.getStats();
            const char* event = "TX_LORA";
            if (dbStats.espnow_peer_reachable) {
                event = "TX_ESPNOW";
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
                    0,                              // sequence_number (unknown)
                    0,                              // message_id (unknown)
                    dest_id,                        // system_id (destination)
                    radio.getRSSI(),                // rssi_dbm
                    radio.getSNR(),                 // snr_db
                    true,                           // relay_active (always true)
                    event,                          // event
                    len,                            // packet_size
                    0,                              // tx_timestamp (unknown)
                    protocol.getQueueDepth(),       // queue_depth
                    stats.uart_checksum_errors      // errors
                );
            }
            #endif
            
            // Update LED to indicate TX
            ledPattern = 1;
            lastLedUpdate = millis();
            
            #ifdef RELAY_DEBUG
            #if DEBUG_LOGGING
            Serial.println("[UART→LoRa] Packet enqueued for transmission to QGC");
            #endif
            #endif
        } else {
            // Queue full - packet dropped
            #if DEBUG_LOGGING
            Serial.println("[UART→LoRa] WARNING: Queue full, packet dropped");
            #endif
        }
    }
}

// ═══════════════════════════════════════════════════════════════════
// LoRa → UART FORWARDING (QGC to Primary)
// ═══════════════════════════════════════════════════════════════════
/**
 * Process LoRa → UART forwarding
 * 
 * Receives packets from QGC @ 902 MHz and forwards them to Primary via UART
 * for delivery to Drone1 @ 915 MHz.
 * 
 * Flow:
 * 1. Check if AeroLoRa protocol has received packet
 * 2. Extract payload (MAVLink data)
 * 3. Build UART packet with checksum
 * 4. Send to Primary via Serial1
 * 5. Track statistics
 * 
 * Error handling:
 * - UART send failure: Logged (rare, UART is reliable)
 * - Invalid packet: Logged and discarded
 * 
 * Requirements: 3.4, 4.4, 12.2
 */
void processLoRaToUart() {
    // Check if Dual-Band Transport has received packet from Ground (deduplicated)
    uint8_t buffer[255];
    uint8_t len = dualBandTransport.receive(buffer, 255);
    
    if (len > 0) {
        // Valid packet received from Ground via dual-band transport
        // Forward to Primary via UART for delivery to Drone1
        
        #ifdef RELAY_DEBUG
        #if DEBUG_LOGGING
        Serial.print("[DualBand→UART] Received packet from Ground: len=");
        Serial.println(len);
        #endif
        #endif
        
        // Build and send UART packet to Primary
        // src_id = NODE_GROUND (packet is from Ground)
        // dest_id = NODE_DRONE1 (packet is for Drone1)
        bool sent = sendUartPacket(Serial1, NODE_GROUND, NODE_DRONE1, buffer, len, &stats);
        
        if (sent) {
            stats.packets_received_from_qgc++;
            
            // Update watchdog timers
            updateUartActivity(&watchdogTimers);
            
            #ifdef RELAY_DEBUG
            #if DEBUG_LOGGING
            Serial.println("[DualBand→UART] Packet forwarded to Primary via UART");
            #endif
            
            #ifdef ENABLE_FLIGHT_LOGGER
            // Log RX_DUALBAND (Packet received from Ground via LoRa or ESP-NOW)
            // RATE LIMIT: Only log every 200ms (5Hz)
            static unsigned long lastDualBandLog = 0;
            if (millis() - lastDualBandLog > 200) {
                logger.logPacket(
                    0,                              // sequence_number (unknown)
                    0,                              // message_id (unknown)
                    NODE_GROUND,                    // system_id (source)
                    0, 0,                           // rssi, snr (N/A at this point)
                    true,                           // relay_active
                    "RX_DUALBAND",                  // event
                    len,                            // packet_size
                    0,                              // tx_timestamp
                    0,                              // queue_depth
                    0                               // errors
                );
                lastDualBandLog = millis();
            }

            // Log TX event to Primary
            logger.logPacket(
                0,                              // sequence_number (unknown)
                0,                              // message_id (unknown)
                NODE_DRONE1,                    // system_id (destination)
                0, 0,                           // rssi, snr (N/A)
                true,                           // relay_active
                "TX_SERIAL",                    // event
                len,                            // packet_size
                millis(),                       // tx_timestamp
                0,                              // queue_depth
                0                               // errors
            );
            #endif
            #endif
        } else {
            // Send failed (payload too large)
            #if DEBUG_LOGGING
            Serial.print("[DualBand→UART] ERROR: Failed to send UART packet (len=");
            Serial.print(len);
            Serial.println(")");
            #endif
        }
    }
}

// ═══════════════════════════════════════════════════════════════════
// RADIO INTERRUPT HANDLER
// ═══════════════════════════════════════════════════════════════════
void handleRadioInterrupt() {
    radioPacketReceived = false;
    
    // Read received packet
    uint8_t buffer[256];
    int state = radio.readData(buffer, 256);
    
    if (state == RADIOLIB_ERR_NONE) {
        // Get RSSI and SNR
        float rssi = radio.getRSSI();
        float snr = radio.getSNR();
        
        // Parse as AeroLoRa packet
        AeroLoRaPacket* packet = (AeroLoRaPacket*)buffer;
        
        // Validate packet header
        if (packet->header == AEROLORA_HEADER) {
            // Pass to protocol for processing
            protocol.handleReceivedPacket(packet);
            
#ifdef ENABLE_FLIGHT_LOGGER
            // Log LoRa RX event (from QGC @ 902 MHz)
            // RATE LIMIT: Only log every 200ms (5Hz) to prevent crashing
            static unsigned long lastRxLog = 0;
            if (millis() - lastRxLog > 200) {
                logger.logPacket(
                    0,                              // sequence_number (not available)
                    0,                              // message_id (not available)
                    packet->src_id,                 // system_id
                    rssi,                           // rssi_dbm
                    snr,                            // snr_db
                    true,                           // relay_active (always true)
                    "RX_LORA",                      // event
                    packet->payload_len,            // packet_size
                    0,                              // tx_timestamp (unknown)
                    0,                              // queue_depth (N/A for RX)
                    stats.uart_checksum_errors      // errors
                );
                lastRxLog = millis();
            }
#endif
        } else {
            // Invalid header
            #ifdef ENABLE_FLIGHT_LOGGER
            logger.logPacket(0, 0, 0, rssi, snr, true, "CRC_ERROR", 0, 0, 0, 0);
            #endif
        }
    } else if (state == RADIOLIB_ERR_CRC_MISMATCH) {
        // CRC Error
        #ifdef ENABLE_FLIGHT_LOGGER
        logger.logPacket(0, 0, 0, radio.getRSSI(), radio.getSNR(), true, "CRC_ERROR", 0, 0, 0, 0);
        #endif
    } else {
        // Other error or Noise Floor check
        #ifdef ENABLE_FLIGHT_LOGGER
        // Log NOISE_FLOOR every 200ms
        static unsigned long lastNoiseLog = 0;
        if (millis() - lastNoiseLog > 200) {
            logger.logPacket(0, 0, 0, radio.getRSSI(), 0, true, "NOISE_FLOOR", 0, 0, 0, 0);
            lastNoiseLog = millis();
        }
        #endif
    }
            
            // Update LED
            ledPattern = 2;  // RX
            lastLedUpdate = millis();


    
    // Return to receive mode
    radio.startReceive();
}

// ═══════════════════════════════════════════════════════════════════
// PRIORITY QUEUE INTEGRATION
// ═══════════════════════════════════════════════════════════════════
/**
 * Priority queue integration for relayed packets
 * 
 * The AeroLoRa protocol automatically classifies packets into three priority tiers
 * based on the MAVLink message ID extracted from the payload:
 * 
 * Tier 0 (Critical) - 10 slots, 1 second timeout:
 * - HEARTBEAT (0): Maintains QGC connection
 * - COMMAND_LONG (76): Critical commands (ARM, DISARM, etc.)
 * - SET_MODE (11): Flight mode changes
 * - DO_SET_MODE (176): Alternative mode command
 * - PARAM_SET (23): Parameter changes
 * - MISSION_ITEM (39): Mission waypoints
 * - MISSION_COUNT (44): Mission metadata
 * 
 * Tier 1 (Important) - 20 slots, 2 second timeout:
 * - GPS_RAW_INT (24): GPS position data
 * - ATTITUDE (30): Aircraft orientation
 * - GLOBAL_POSITION_INT (33): Global position
 * - RC_CHANNELS (65): RC input
 * - VFR_HUD (74): HUD data
 * 
 * Tier 2 (Routine) - 30 slots, 5 second timeout:
 * - All other telemetry messages
 * - PARAM_VALUE (22): Parameter values (rate limited to 2/sec)
 * - System status messages
 * - Extended telemetry
 * 
 * The protocol's send() method:
 * 1. Extracts MAVLink message ID from payload
 * 2. Calls getPriority(msgId) to determine tier
 * 3. Enqueues to appropriate tier array
 * 4. Returns false if queue is full
 * 
 * The protocol's process() method:
 * 1. Checks tier 0 first (critical commands)
 * 2. Checks tier 1 second (important telemetry)
 * 3. Checks tier 2 last (routine telemetry)
 * 4. Drops stale packets based on tier timeout
 * 5. Transmits highest priority packet available
 * 
 * This ensures:
 * - HEARTBEAT messages are transmitted at 1 Hz minimum (Tier 0)
 * - Commands are never blocked by telemetry streams (Tier 0)
 * - Important telemetry is prioritized over routine data (Tier 1)
 * - Old packets are automatically dropped (staleness detection)
 * 
 * Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
 */

// ═══════════════════════════════════════════════════════════════════

// LED STATUS UPDATE
// ═══════════════════════════════════════════════════════════════════
void updateLed() {
    // LED patterns:
    // - Idle: OFF
    // - TX: ON for 50ms
    // - RX: ON for 50ms
    
    if (ledPattern > 0 && (millis() - lastLedUpdate > 50)) {
        ledPattern = 0;
        digitalWrite(LED_PIN, LOW);
    }
    
    if (ledPattern > 0) {
        digitalWrite(LED_PIN, HIGH);
    } else {
        digitalWrite(LED_PIN, LOW);
    }
}
