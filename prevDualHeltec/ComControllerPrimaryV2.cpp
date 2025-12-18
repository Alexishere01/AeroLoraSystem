/**
 * PRIMARY NODE - Version 2.0
 * Direct radio control with custom scheduler
 * 
 * Responsibilities:
 * - Direct link to GCS @ 915 MHz using SX1262Direct
 * - Custom TDMA scheduler with adaptive modulation
 * - Dual radio coordination (Radio 1: GCS, Radio 2: Mesh)
 * - Monitor link quality and adapt modulation
 * - Coordinate with secondary for relay mode
 * - Automatic failover when jamming detected
 */

#include <Arduino.h>
#include <U8g2lib.h>
#include <Wire.h>
#include <vector>
#include <RadioLib.h>
#include "FeatureFlags.h"
#include "AeroLoRaScheduler.h"
#include "AdaptiveModulation.h"
#include "DualRadioManager.h"
#include "MavlinkUtils.h"
#include "shared_protocol.h"
#include "BinaryProtocol.h"

// ═══════════════════════════════════════════════════════════════════
// PIN DEFINITIONS - Heltec V3
// ═══════════════════════════════════════════════════════════════════
// Radio 1 (915 MHz - GCS Link)
#define LORA1_SCK        9
#define LORA1_MISO       11
#define LORA1_MOSI       10
#define LORA1_CS         8
#define LORA1_RST        12
#define LORA1_BUSY       13
#define LORA1_DIO1       14

// Radio 2 (902 MHz - Mesh/Relay) - Using second SPI bus
#define LORA2_SCK        5
#define LORA2_MISO       3
#define LORA2_MOSI       6
#define LORA2_CS         7
#define LORA2_RST        4
#define LORA2_BUSY       15
#define LORA2_DIO1       16

#define LED_PIN          35

// UART to Secondary Node
#define UART_SECONDARY   Serial1
#define SECONDARY_TX     1   
#define SECONDARY_RX     2

// OLED Display (I2C) - Heltec V3 pins
#define OLED_SDA         17
#define OLED_SCL         18
#define OLED_RST         21
#define VEXT_PIN         36  // Power control for display    

// ═══════════════════════════════════════════════════════════════════
// RADIO CONFIGURATION
// ═══════════════════════════════════════════════════════════════════
// Radio 1 (915 MHz - GCS Link)
#define RADIO1_FREQ      915.0   // MHz - Direct GCS link
#define RADIO1_BW        125.0   // kHz
#define RADIO1_SF        7       // 7-12
#define RADIO1_CR        5       // 5-8
#define RADIO1_SYNC      0x12    // Private network
#define RADIO1_POWER     14      // dBm

// Radio 2 (902 MHz - Mesh/Relay)
#define RADIO2_FREQ      902.0   // MHz - Mesh network
#define RADIO2_BW        125.0   // kHz
#define RADIO2_SF        7       // 7-12
#define RADIO2_CR        5       // 5-8
#define RADIO2_SYNC      0x12    // Private network
#define RADIO2_POWER     14      // dBm

// ═══════════════════════════════════════════════════════════════════
// JAMMING DETECTION THRESHOLDS
// ═══════════════════════════════════════════════════════════════════
#define RSSI_THRESHOLD        -100    // dBm - below this = weak signal
#define SNR_THRESHOLD         5       // dB - below this = poor quality
#define PACKET_LOSS_THRESHOLD 30    // % - above this = link problems
#define JAMMING_DETECT_COUNT  5       // consecutive bad readings = jammed

// ═══════════════════════════════════════════════════════════════════
// TIMING CONFIGURATION
// ═══════════════════════════════════════════════════════════════════
#define HEARTBEAT_INTERVAL   1000    // ms - link quality check rate
#define RELAY_TIMEOUT        5000    // ms - timeout for relay response
#define STATUS_INTERVAL      3000    // ms - print status rate
#define DISPLAY_INTERVAL     200     // ms - OLED update rate (5 Hz)

// ═══════════════════════════════════════════════════════════════════
// PACKET TYPES
// ═══════════════════════════════════════════════════════════════════
enum PacketType {
    PACKET_HEARTBEAT = 0x01,
    PACKET_DATA = 0x02,
    PACKET_ACK = 0x03,
    PACKET_RELAY_REQUEST = 0x04,
    PACKET_RELAY_DATA = 0x05
};

// ═══════════════════════════════════════════════════════════════════
// SYSTEM STATES
// ═══════════════════════════════════════════════════════════════════
enum SystemMode {
    MODE_DIRECT,            // Normal: GCS <-> Primary
    MODE_RELAY,             // Jammed: GCS <-> Secondary <-> Primary
    MODE_SWITCHING,         // Transitioning between modes
    MODE_FREQUENCY_BRIDGE   // Frequency bridge: GCS (915) <-> Primary <-> Secondary <-> Drone (902)
};

// ═══════════════════════════════════════════════════════════════════
// RELAY STATE MACHINE WITH ENHANCED ERROR HANDLING
// ═══════════════════════════════════════════════════════════════════
enum RelayTransitionState {
    TRANSITION_IDLE,
    TRANSITION_ACTIVATING,
    TRANSITION_DEACTIVATING,
    TRANSITION_WAITING_ACK
};

struct RelayStateMachine {
    SystemMode currentMode;
    SystemMode previousMode;  // For reverting on failure (Requirement 6.3)
    RelayTransitionState transitionState;
    uint32_t transitionStartTime;
    uint32_t watchdogStartTime;  // Watchdog timer for stuck transitions (Requirement 6.3)
    bool secondaryReady;
    uint32_t transitionFailures;  // Track transition failures
    
    void startActivation();
    void startDeactivation();
    void completeTransition();
    void handleTimeout();
    void revertToPreviousMode();  // Revert on transition failure (Requirement 6.3)
    void checkWatchdog();  // Watchdog timer for stuck transitions (Requirement 6.3)
};

// ═══════════════════════════════════════════════════════════════════
// MULTI-DRONE RELAY TRACKING
// ═══════════════════════════════════════════════════════════════════
#define MAX_RELAY_TARGETS 4  // Maximum number of peer drones we can relay for

struct RelayTarget {
    uint8_t systemId;           // System ID of drone being relayed
    bool active;                // Is this relay slot active?
    uint32_t lastActivity;      // Last time we received/transmitted packet for this drone
    uint32_t packetsRelayed;    // Number of packets relayed for this drone
};

RelayTarget relayTargets[MAX_RELAY_TARGETS] = {0};

// ═══════════════════════════════════════════════════════════════════
// LINK QUALITY METRICS
// ═══════════════════════════════════════════════════════════════════
struct LinkQuality {
    float rssi;
    float snr;
    uint32_t packetsExpected;
    uint32_t packetsReceived;
    uint32_t consecutiveLost;
    bool isJammed;
    
    float getPacketLossPercent() {
        if (packetsExpected == 0) return 0;
        return ((packetsExpected - packetsReceived) * 100.0) / packetsExpected;
    }
    
    void reset() {
        rssi = 0;
        snr = 0;
        packetsExpected = 0;
        packetsReceived = 0;
        consecutiveLost = 0;
        isJammed = false;
    }
};

// ═══════════════════════════════════════════════════════════════════
// UART COMMAND TRACKING AND ERROR HANDLING
// ═══════════════════════════════════════════════════════════════════
struct PendingCommand {
    String command;
    String payload;
    uint32_t sentTime;
    uint8_t retryCount;
    bool requiresAck;
};

const uint32_t UART_ACK_TIMEOUT = 500;  // ms
const uint8_t MAX_UART_RETRIES = 3;
std::vector<PendingCommand> pendingCommands;

// UART error tracking
struct UartErrorStats {
    uint32_t parseErrors;
    uint32_t bufferOverflows;
    uint32_t timeouts;
    uint32_t malformedMessages;
    uint32_t hexDecodeErrors;
    uint32_t lastErrorTime;
    
    void reset() {
        parseErrors = 0;
        bufferOverflows = 0;
        timeouts = 0;
        malformedMessages = 0;
        hexDecodeErrors = 0;
        lastErrorTime = 0;
    }
};

UartErrorStats uartErrors = {0, 0, 0, 0, 0, 0};

// Radio transmission error tracking (Requirement 9.5)
struct RadioErrorStats {
    uint32_t txFailures;
    uint32_t rxRestartFailures;
    uint32_t totalTransmissions;
    uint32_t successfulTransmissions;
    uint32_t lastErrorTime;
    
    float getSuccessRate() {
        if (totalTransmissions == 0) return 100.0f;
        return (successfulTransmissions * 100.0f) / totalTransmissions;
    }
    
    void reset() {
        txFailures = 0;
        rxRestartFailures = 0;
        totalTransmissions = 0;
        successfulTransmissions = 0;
        lastErrorTime = 0;
    }
};

RadioErrorStats radioErrors = {0, 0, 0, 0, 0};

// Bridge statistics tracking (for frequency bridge mode)
struct BridgeStats {
    uint32_t gcsToMeshPackets;    // GCS → Mesh forwarding (packets sent to Secondary)
    uint32_t meshToGcsPackets;    // Mesh → GCS forwarding (packets received from Secondary)
    uint32_t gcsToMeshBytes;
    uint32_t meshToGcsBytes;
    
    void reset() {
        gcsToMeshPackets = 0;
        meshToGcsPackets = 0;
        gcsToMeshBytes = 0;
        meshToGcsBytes = 0;
    }
};

BridgeStats bridgeStats = {0, 0, 0, 0};

// Binary protocol statistics tracking
BinaryProtocolStats binaryStats = {0, 0, 0, 0, 0, 0, 0, 0};

// Binary protocol receive buffer
UartRxBuffer binaryRxBuffer;

// ═══════════════════════════════════════════════════════════════════
// GLOBAL OBJECTS AND STATE
// ═══════════════════════════════════════════════════════════════════
// Radio objects - RadioLib SX1262
SX1262 radio1 = new Module(LORA1_CS, LORA1_DIO1, LORA1_RST, LORA1_BUSY);  // 915 MHz - GCS link
SX1262 radio2 = new Module(LORA2_CS, LORA2_DIO1, LORA2_RST, LORA2_BUSY);  // 902 MHz - Mesh/Relay

#if ENABLE_DUAL_RADIO
DualRadioManager radioManager;
#endif

U8G2_SSD1306_128X64_NONAME_F_HW_I2C display(U8G2_R0, OLED_RST, OLED_SCL, OLED_SDA);

// Scheduler and adaptive modulation
#if ENABLE_SCHEDULER
AeroLoRaScheduler scheduler;
#endif

#if ENABLE_ADAPTIVE_MOD
AdaptiveModulation adaptiveMod;
#endif

SystemMode currentMode = MODE_DIRECT;
LinkQuality linkQuality;
uint32_t sequenceNumber = 0;
uint32_t jammingDetectCounter = 0;
uint32_t consecutiveGoodPackets = 0;  // For hysteresis in mode switching

// Relay state machine with enhanced error handling
RelayStateMachine relayStateMachine = {MODE_DIRECT, MODE_DIRECT, TRANSITION_IDLE, 0, 0, false, 0};

// Timing
unsigned long lastHeartbeat = 0;
unsigned long lastStatusPrint = 0;
unsigned long modeSwitchStartTime = 0;
unsigned long lastStatsOutput = 0;
unsigned long lastDisplayUpdate = 0;
unsigned long lastFrequencyCheck = 0;

// Display statistics tracking
uint32_t autopilotRxCount = 0;
uint32_t txCount = 0;
uint8_t lastTxTier = 0;
bool displayAvailable = false;

// Buffers
uint8_t txBuffer[255];
uint8_t rxBuffer[255];
char uartBuffer[512];
const uint16_t AUTOPILOT_BUFFER_SIZE = 512;  // Increased from 256
uint8_t autopilotRxBuffer[512];
uint16_t autopilotRxIndex = 0;
unsigned long lastAutopilotRx = 0;
const uint32_t PACKET_TIMEOUT = 50;  // ms - increased from 40ms

// Radio interrupt flags
volatile bool radio1RxDoneFlag = false;
volatile bool radio1TxDoneFlag = false;
volatile bool radio1CadDoneFlag = false;
volatile bool radio2RxDoneFlag = false;
volatile bool radio2TxDoneFlag = false;
volatile bool radio2CadDoneFlag = false;

// ═══════════════════════════════════════════════════════════════════
// FUNCTION PROTOTYPES
// ═══════════════════════════════════════════════════════════════════
void radio1ISR(void);
void radio2ISR(void);
bool initializeRadio();
bool initializeDisplay();
void updateDisplay();
void handleRxDone();
void handleTxDone();
void handleCadDone();
void handleRadio2RxDone();
void handleRadio2TxDone();
void handleRadio2CadDone();
void sendPacket(uint8_t* data, size_t length);
void sendHeartbeat();
void processPacket(uint8_t* data, size_t length);
void checkUart();
void sendUartCommand(String command, String payload, bool requiresAck = false);
void checkPendingCommands();
bool hexToBytes(const String& hexStr, uint8_t* output, size_t maxLen, size_t* outLen);
String bytesToHex(const uint8_t* data, size_t len);
void forwardToSecondary(uint8_t* data, size_t length);
void evaluateLinkQuality();
void switchToRelayMode();
void switchToDirectMode();
void printHeader();
void printStatus();
void processAutopilotSerial();
void processScheduler();
int16_t findCompleteMavlinkPacket(uint8_t* buffer, uint16_t bufferLen);
void addRelayTarget(uint8_t systemId);
void updateRelayActivity(uint8_t systemId);
void cleanupInactiveRelays();
bool isRelayingForPeer(uint8_t systemId);
bool validateUartConnection();
bool validateRadioInitialization();
bool validateConfiguration();

// ═══════════════════════════════════════════════════════════════════
// CONFIGURATION VALIDATION FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

/**
 * @brief Validate UART connection to Secondary controller
 * @return true if UART connection is working, false otherwise
 */
bool validateUartConnection() {
    Serial.print("→ Validating UART connection to Secondary... ");
    
    // Binary protocol: Send STATUS_REQUEST and wait for response
    sendBinaryStatusRequest(UART_SECONDARY, &binaryStats);
    
    // Wait for response with timeout
    unsigned long startTime = millis();
    const unsigned long UART_TEST_TIMEOUT = 1000;  // 1 second
    bool receivedResponse = false;
    
    while (millis() - startTime < UART_TEST_TIMEOUT) {
        // Process incoming binary packets
        processBinaryUart(UART_SECONDARY, &binaryRxBuffer, &binaryStats);
        
        // Check if we received any packet (ACK or STATUS_REPORT)
        if (binaryStats.packets_received > 0) {
            receivedResponse = true;
            break;
        }
        
        delay(10);
    }
    
    if (receivedResponse) {
        Serial.println("✓");
        return true;
    }
    
    Serial.println("✗ FAILED");
    Serial.println("  ⚠ No response from Secondary controller");
    return false;
}

/**
 * @brief Validate radio initialization and basic functionality
 * @return true if radios are working correctly, false otherwise
 */
bool validateRadioInitialization() {
    bool allValid = true;
    
    // Validate Radio 1
    Serial.print("→ Validating Radio 1 initialization... ");
    float rssi1 = radio1.getRSSI();
    
    // RSSI should be a reasonable value (between -140 and 0)
    if (rssi1 >= -140.0 && rssi1 <= 0.0) {
        Serial.println("✓");
        Serial.printf("  → Radio 1 RSSI: %.1f dBm\n", rssi1);
    } else {
        Serial.println("✗ FAILED");
        Serial.printf("  ⚠ Invalid Radio 1 RSSI reading: %.1f dBm\n", rssi1);
        allValid = false;
    }
    
    // Validate Radio 2
    Serial.print("→ Validating Radio 2 initialization... ");
    float rssi2 = radio2.getRSSI();
    
    // RSSI should be a reasonable value (between -140 and 0)
    if (rssi2 >= -140.0 && rssi2 <= 0.0) {
        Serial.println("✓");
        Serial.printf("  → Radio 2 RSSI: %.1f dBm\n", rssi2);
    } else {
        Serial.println("✗ FAILED");
        Serial.printf("  ⚠ Invalid Radio 2 RSSI reading: %.1f dBm\n", rssi2);
        Serial.println("  → Radio 2 may not be available - continuing with Radio 1 only");
        // Don't fail validation if Radio 2 is not available
    }
    
    return allValid;
}

/**
 * @brief Validate complete system configuration
 * @return true if all validations pass, false otherwise
 */
bool validateConfiguration() {
    Serial.println("\n═══════════════════════════════════════════════════════════");
    Serial.println("  CONFIGURATION VALIDATION");
    Serial.println("═══════════════════════════════════════════════════════════");
    
    bool allValid = true;
    
    // Validate UART connection
    if (!validateUartConnection()) {
        allValid = false;
        Serial.println("  ✗ UART validation failed");
    }
    
    // Validate radio initialization
    if (!validateRadioInitialization()) {
        allValid = false;
        Serial.println("  ✗ Radio validation failed");
    }
    
    // Validate frequency configuration
    Serial.print("→ Validating frequency configuration... ");
    if (RADIO1_FREQ < 902.0 || RADIO1_FREQ > 928.0) {
        Serial.println("✗ FAILED");
        Serial.printf("  ⚠ Invalid Radio 1 frequency: %.1f MHz (must be 902-928 MHz)\n", RADIO1_FREQ);
        allValid = false;
    } else if (RADIO2_FREQ < 902.0 || RADIO2_FREQ > 928.0) {
        Serial.println("✗ FAILED");
        Serial.printf("  ⚠ Invalid Radio 2 frequency: %.1f MHz (must be 902-928 MHz)\n", RADIO2_FREQ);
        allValid = false;
    } else {
        Serial.println("✓");
    }
    
    // Validate timing parameters
    Serial.print("→ Validating timing parameters... ");
    if (HEARTBEAT_INTERVAL < 100 || HEARTBEAT_INTERVAL > 10000) {
        Serial.println("✗ FAILED");
        Serial.printf("  ⚠ Invalid heartbeat interval: %d ms\n", HEARTBEAT_INTERVAL);
        allValid = false;
    } else {
        Serial.println("✓");
    }
    
    Serial.println("═══════════════════════════════════════════════════════════");
    if (allValid) {
        Serial.println("  ✓ ALL VALIDATIONS PASSED");
    } else {
        Serial.println("  ✗ SOME VALIDATIONS FAILED");
        Serial.println("  → System may not operate correctly");
    }
    Serial.println("═══════════════════════════════════════════════════════════\n");
    
    return allValid;
}

// ═══════════════════════════════════════════════════════════════════
// RELAY STATE MACHINE IMPLEMENTATION WITH ENHANCED ERROR HANDLING
// ═══════════════════════════════════════════════════════════════════
void RelayStateMachine::startActivation() {
    Serial.println("→ Starting relay activation sequence");
    previousMode = currentMode;  // Save for potential revert (Requirement 6.3)
    transitionState = TRANSITION_ACTIVATING;
    transitionStartTime = millis();
    watchdogStartTime = millis();  // Start watchdog timer (Requirement 6.3)
    secondaryReady = false;
    currentMode = MODE_SWITCHING;
}

void RelayStateMachine::startDeactivation() {
    Serial.println("→ Starting relay deactivation sequence");
    previousMode = currentMode;  // Save for potential revert (Requirement 6.3)
    transitionState = TRANSITION_DEACTIVATING;
    transitionStartTime = millis();
    watchdogStartTime = millis();  // Start watchdog timer (Requirement 6.3)
    secondaryReady = false;
    currentMode = MODE_SWITCHING;
}

void RelayStateMachine::completeTransition() {
    if (transitionState == TRANSITION_ACTIVATING) {
        Serial.println("✓ Relay activation complete");
        currentMode = MODE_RELAY;
        previousMode = MODE_RELAY;  // Update previous mode on success
        transitionState = TRANSITION_IDLE;
        secondaryReady = true;
    } else if (transitionState == TRANSITION_DEACTIVATING) {
        Serial.println("✓ Relay deactivation complete");
        currentMode = MODE_DIRECT;
        previousMode = MODE_DIRECT;  // Update previous mode on success
        transitionState = TRANSITION_IDLE;
        secondaryReady = false;
    }
}

/**
 * @brief Handle timeout for Secondary acknowledgments (Requirement 6.3)
 * 
 * Implements timeout detection and reversion to previous mode on failure
 */
void RelayStateMachine::handleTimeout() {
    uint32_t elapsed = millis() - transitionStartTime;
    
    // Timeout for Secondary acknowledgments (Requirement 6.3)
    if (elapsed > 1000) {  // 1 second timeout
        Serial.printf("✗ Relay transition timeout after %dms\n", elapsed);
        transitionFailures++;
        
        // Revert to previous mode on transition failure (Requirement 6.3)
        if (transitionState == TRANSITION_ACTIVATING) {
            Serial.println("  → Failed to activate relay mode");
            Serial.printf("  → Reverting to previous mode: %s\n", 
                         previousMode == MODE_DIRECT ? "DIRECT" :
                         previousMode == MODE_FREQUENCY_BRIDGE ? "BRIDGE" : "UNKNOWN");
            revertToPreviousMode();
        } else if (transitionState == TRANSITION_DEACTIVATING) {
            Serial.println("  → Failed to deactivate relay mode");
            Serial.printf("  → Reverting to previous mode: %s\n",
                         previousMode == MODE_RELAY ? "RELAY" : "UNKNOWN");
            revertToPreviousMode();
        }
        
        transitionState = TRANSITION_IDLE;
        secondaryReady = false;
        
        Serial.printf("  → Total transition failures: %lu\n", transitionFailures);
    }
}

/**
 * @brief Revert to previous mode on transition failure (Requirement 6.3)
 */
void RelayStateMachine::revertToPreviousMode() {
    Serial.println("→ Reverting to previous mode due to transition failure");
    currentMode = previousMode;
    transitionState = TRANSITION_IDLE;
    
    // Log the reversion
    const char* modeStr = (currentMode == MODE_DIRECT) ? "DIRECT" :
                          (currentMode == MODE_RELAY) ? "RELAY" :
                          (currentMode == MODE_FREQUENCY_BRIDGE) ? "BRIDGE" : "UNKNOWN";
    Serial.printf("✓ Reverted to %s mode\n", modeStr);
}

/**
 * @brief Watchdog timer for stuck transitions (Requirement 6.3)
 * 
 * Forces completion of stuck transitions after 2 seconds
 */
void RelayStateMachine::checkWatchdog() {
    if (transitionState == TRANSITION_IDLE) {
        return;  // No transition in progress
    }
    
    uint32_t elapsed = millis() - watchdogStartTime;
    
    // Watchdog timeout: 2 seconds (Requirement 6.3)
    if (elapsed > 2000) {
        Serial.printf("⚠ WATCHDOG: Transition stuck for %dms - forcing completion\n", elapsed);
        transitionFailures++;
        
        // Force revert to previous mode
        Serial.println("  → Watchdog forcing revert to previous mode");
        revertToPreviousMode();
        
        Serial.printf("  → Total transition failures: %lu\n", transitionFailures);
    }
}

// ═══════════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════════
void setup() {
    Serial.begin(115200);
    delay(2000);
    
    pinMode(LED_PIN, OUTPUT);
    printHeader();
    
    // Initialize UART to secondary
    Serial.print("Initializing UART to secondary... ");
    UART_SECONDARY.begin(115200, SERIAL_8N1, SECONDARY_RX, SECONDARY_TX);
    Serial.println("✓");
    
    // Initialize OLED display
    if (initializeDisplay()) {
        displayAvailable = true;
        Serial.println("✓ Display initialized");
    } else {
        displayAvailable = false;
        Serial.println("⚠ Display failed - continuing without display");
    }
    
    // Initialize radio
    if (initializeRadio()) {
        Serial.println("✓ Radio initialized");
    } else {
        Serial.println("✗ Radio failed - check hardware!");
        Serial.println("  → Cannot continue without radio");
        while(1) { 
            digitalWrite(LED_PIN, HIGH);
            delay(100);
            digitalWrite(LED_PIN, LOW);
            delay(100);
        }
    }
    
    // Validate configuration before proceeding
    bool configValid = validateConfiguration();
    if (!configValid) {
        Serial.println("⚠ WARNING: Configuration validation failed");
        Serial.println("  → Continuing with limited functionality");
        Serial.println("  → Some features may not work correctly\n");
        
        // Flash LED to indicate warning state
        for (int i = 0; i < 3; i++) {
            digitalWrite(LED_PIN, HIGH);
            delay(200);
            digitalWrite(LED_PIN, LOW);
            delay(200);
        }
    }
    
    #if ENABLE_SCHEDULER
    // Initialize scheduler
    Serial.print("Initializing scheduler... ");
    scheduler.begin(100);  // 100ms slots
    Serial.println("✓");
    #else
    Serial.println("⚠ Scheduler disabled (barebones mode)");
    #endif
    
    #if ENABLE_ADAPTIVE_MOD
    // Initialize adaptive modulation
    Serial.print("Initializing adaptive modulation... ");
    #if ENABLE_SCHEDULER
    adaptiveMod.begin(&radio1, &scheduler);
    #else
    adaptiveMod.begin(&radio1, nullptr);
    #endif
    Serial.println("✓");
    #else
    Serial.println("⚠ Adaptive modulation disabled (barebones mode)");
    #endif
    
    // Start in frequency bridge mode (default per requirements 1.5, 10.1-10.5)
    Serial.println("\n═══════════════════════════════════════════════════════════");
    Serial.println("  INITIALIZING FREQUENCY BRIDGE MODE");
    Serial.println("═══════════════════════════════════════════════════════════");
    
    currentMode = MODE_FREQUENCY_BRIDGE;
    linkQuality.reset();
    
    // Initialize relay state machine
    relayStateMachine.currentMode = MODE_FREQUENCY_BRIDGE;
    relayStateMachine.transitionState = TRANSITION_IDLE;
    relayStateMachine.secondaryReady = false;
    
    // Configure Radio 2 for bridge mode (standby RC for fast wake)
    Serial.print("→ Configuring Radio 2 for bridge mode... ");
    #if ENABLE_DUAL_RADIO
    radioManager.setRelayActive(true);  // Bridge mode = relay active
    radioManager.setRadio2Mode(RADIO_MODE_RX_CONTINUOUS);  // Listen for mesh traffic
    #endif
    Serial.println("✓");
    
    // Send initialization command to Secondary with frequency info
    Serial.print("→ Sending initialization command to Secondary... ");
    
    // Binary protocol: Send INIT command
    sendBinaryInit(UART_SECONDARY, "FREQUENCY_BRIDGE", RADIO1_FREQ, RADIO2_FREQ, &binaryStats);
    
    // Wait for Secondary acknowledgment with timeout
    unsigned long initStartTime = millis();
    const unsigned long INIT_TIMEOUT = 2000;  // 2 second timeout
    bool secondaryAcknowledged = false;
    
    while (millis() - initStartTime < INIT_TIMEOUT) {
        // Binary protocol: Process incoming packets
        processBinaryUart(UART_SECONDARY, &binaryRxBuffer, &binaryStats);
        
        // Check if we received an ACK (handled by binary packet processor)
        // The handleBinaryAck() function sets g_secondaryAcknowledged
        extern bool g_secondaryAcknowledged;
        if (g_secondaryAcknowledged) {
            secondaryAcknowledged = true;
            relayStateMachine.secondaryReady = true;
            Serial.println("✓");
            Serial.println("  Secondary acknowledged");
            break;
        }
        delay(10);
    }
    
    if (!secondaryAcknowledged) {
        Serial.println("⚠ TIMEOUT");
        Serial.println("  ⚠ Secondary did not acknowledge initialization");
        Serial.println("  → Continuing anyway - check Secondary connection");
        relayStateMachine.secondaryReady = false;
    }
    
    Serial.println("\n═══════════════════════════════════════════════════════════");
    Serial.println("  ✓ PRIMARY READY - FREQUENCY BRIDGE MODE ACTIVE");
    Serial.println("═══════════════════════════════════════════════════════════");
    Serial.printf("  Radio 1 Frequency: %.1f MHz (GCS Link)\n", RADIO1_FREQ);
    Serial.printf("  Radio 2 Frequency: %.1f MHz (Mesh Network)\n", RADIO2_FREQ);
    Serial.printf("  Secondary Status: %s\n", 
                  relayStateMachine.secondaryReady ? "READY" : "NOT RESPONDING");
    Serial.println("  Mode: Transparent bidirectional bridge");
    Serial.println("═══════════════════════════════════════════════════════════\n");
}

// ═══════════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════════
void loop() {
    unsigned long now = millis();
    
    #if ENABLE_DUAL_RADIO
    // Update dual radio manager state machine
    radioManager.update();
    #endif
    
    // Handle Radio 1 interrupts with priority ordering
    if (radio1RxDoneFlag) {
        radio1RxDoneFlag = false;
        handleRxDone();
    }
    
    if (radio1TxDoneFlag) {
        radio1TxDoneFlag = false;
        handleTxDone();
    }
    
    if (radio1CadDoneFlag) {
        radio1CadDoneFlag = false;
        handleCadDone();
    }
    
    // Handle Radio 2 interrupts (for mesh/relay traffic)
    if (radio2RxDoneFlag) {
        radio2RxDoneFlag = false;
        handleRadio2RxDone();
    }
    
    if (radio2TxDoneFlag) {
        radio2TxDoneFlag = false;
        handleRadio2TxDone();
    }
    
    if (radio2CadDoneFlag) {
        radio2CadDoneFlag = false;
        handleRadio2CadDone();
    }
    
    // Process autopilot serial data
    processAutopilotSerial();
    
    // Process scheduler and transmit
    processScheduler();
    
    // Check for UART messages from secondary
    checkUart();
    
    // Check pending commands for timeouts and retries
    checkPendingCommands();
    
    // Check relay state machine for timeouts (Requirement 6.3)
    if (relayStateMachine.transitionState != TRANSITION_IDLE) {
        relayStateMachine.handleTimeout();
        relayStateMachine.checkWatchdog();  // Watchdog timer for stuck transitions
        currentMode = relayStateMachine.currentMode;  // Sync global mode
    }
    
    // Send periodic heartbeats to monitor link
    if (now - lastHeartbeat > HEARTBEAT_INTERVAL) {
        sendHeartbeat();
        lastHeartbeat = now;
    }
    
    // Evaluate link quality and switch modes if needed
    evaluateLinkQuality();
    
    // Cleanup inactive relay targets (every 5 seconds)
    static unsigned long lastRelayCleanup = 0;
    if (now - lastRelayCleanup > 5000) {
        cleanupInactiveRelays();
        lastRelayCleanup = now;
    }
    
    // Print status periodically
    if (now - lastStatusPrint > STATUS_INTERVAL) {
        printStatus();
        lastStatusPrint = now;
    }
    
    // Update OLED display
    if (displayAvailable && (now - lastDisplayUpdate > DISPLAY_INTERVAL)) {
        updateDisplay();
        lastDisplayUpdate = now;
    }
    
    // Periodic frequency verification (every 60 seconds)
    // Note: SX1262 doesn't have getFrequency() method, so we skip verification
    // The frequency is set during initialization and remains stable
    if (now - lastFrequencyCheck > 60000) {
        // Just log that we're still operating at the configured frequencies
        Serial.printf("✓ Operating at configured frequencies: Radio1=%.1f MHz, Radio2=%.1f MHz\n", 
                     RADIO1_FREQ, RADIO2_FREQ);
        lastFrequencyCheck = now;
    }
}

// ═══════════════════════════════════════════════════════════════════
// DISPLAY FUNCTIONS
// ═══════════════════════════════════════════════════════════════════
bool initializeDisplay() {
    // Enable Vext to power OLED
    pinMode(VEXT_PIN, OUTPUT);
    digitalWrite(VEXT_PIN, LOW);  // LOW = ON for Heltec V3
    delay(100);
    
    // Initialize U8g2
    if (!display.begin()) {
        Serial.println("⚠ Display initialization failed - continuing without display");
        return false;
    }
    
    display.clearBuffer();
    display.setFont(u8g2_font_6x10_tf);
    
    // Show startup message
    display.drawStr(0, 20, "PRIMARY (915MHz)");
    display.drawStr(0, 35, "Initializing...");
    
    // Send buffer (void return type - no error checking possible)
    display.sendBuffer();
    
    return true;
}

void updateDisplay() {
    // Ensure displayAvailable flag is checked before all updates
    if (!displayAvailable) {
        return;
    }
    
    #if ENABLE_SCHEDULER
    // Get scheduler queue depths
    uint16_t criticalDepth = scheduler.getQueueDepth(SLOT_CRITICAL);
    uint16_t telemetryDepth = scheduler.getQueueDepth(SLOT_TELEMETRY);
    uint16_t relayDepth = scheduler.getQueueDepth(SLOT_RELAY);
    uint16_t adaptiveDepth = scheduler.getQueueDepth(SLOT_ADAPTIVE);
    uint16_t totalDepth = criticalDepth + telemetryDepth + relayDepth + adaptiveDepth;
    #else
    uint16_t totalDepth = 0;  // No queue in barebones mode
    #endif
    
    display.clearBuffer();
    display.setFont(u8g2_font_6x10_tf);
    
    // Title
    display.drawStr(0, 10, "PRIMARY (915MHz)");
    display.drawLine(0, 12, 128, 12);
    
    // Mode with bridge indicator (Requirement 7.1)
    char buf[32];
    const char* modeStr = (currentMode == MODE_DIRECT) ? "DIRECT" :
                          (currentMode == MODE_RELAY) ? "RELAY" :
                          (currentMode == MODE_FREQUENCY_BRIDGE) ? "BRIDGE" : "SWITCH";
    sprintf(buf, "MODE: %s", modeStr);
    display.drawStr(0, 24, buf);
    
    // RX/TX and queues - mode-specific formatting
    if (currentMode == MODE_DIRECT) {
        // Direct mode: Show queue depth by slot type
        sprintf(buf, "RX:%lu Q:%d", autopilotRxCount, totalDepth);
        display.drawStr(0, 36, buf);
        
        // TX count with current profile
        #if ENABLE_ADAPTIVE_MOD
        uint8_t profile = adaptiveMod.getCurrentProfile();
        sprintf(buf, "TX:%lu SF%d", txCount, profile + 6);  // SF6-SF12
        #else
        sprintf(buf, "TX:%lu SF7", txCount);  // Fixed SF7 in barebones mode
        #endif
        display.drawStr(0, 48, buf);
    } else if (currentMode == MODE_FREQUENCY_BRIDGE) {
        // Bridge mode: Show bridge packet counts (GCS→Mesh, Mesh→GCS)
        sprintf(buf, "G->M:%lu M->G:%lu", bridgeStats.gcsToMeshPackets, bridgeStats.meshToGcsPackets);
        display.drawStr(0, 36, buf);
        
        // Show number of active peer relays
        int activeRelayCount = 0;
        for (int i = 0; i < MAX_RELAY_TARGETS; i++) {
            if (relayTargets[i].active) activeRelayCount++;
        }
        sprintf(buf, "Q:%d PR:%d TX:%lu", totalDepth, activeRelayCount, txCount);
        display.drawStr(0, 48, buf);
    } else {
        // Relay mode: Show queue depth
        sprintf(buf, "RX:%lu Q:%d", autopilotRxCount, totalDepth);
        display.drawStr(0, 36, buf);
        
        // TX count with current profile
        #if ENABLE_ADAPTIVE_MOD
        uint8_t profile = adaptiveMod.getCurrentProfile();
        sprintf(buf, "TX:%lu SF%d", txCount, profile + 6);
        #else
        sprintf(buf, "TX:%lu SF7", txCount);  // Fixed SF7 in barebones mode
        #endif
        display.drawStr(0, 48, buf);
    }
    
    // RSSI/SNR
    sprintf(buf, "RSSI:%.0f SNR:%.1f", linkQuality.rssi, linkQuality.snr);
    display.drawStr(0, 60, buf);
    
    // Send buffer (void return type - no error checking possible)
    display.sendBuffer();
}

// ═══════════════════════════════════════════════════════════════════
// RADIO FUNCTIONS
// ═══════════════════════════════════════════════════════════════════
bool initializeRadio() {
    Serial.printf("Initializing Radio 1 @ %.1f MHz... ", RADIO1_FREQ);
    
    // Initialize Radio 1 (GCS link) with RadioLib
    int16_t state = radio1.begin(RADIO1_FREQ, RADIO1_BW, RADIO1_SF, RADIO1_CR, 
                                  RADIO1_SYNC, RADIO1_POWER);
    if (state != RADIOLIB_ERR_NONE) {
        Serial.printf("Failed! Error code: %d\n", state);
        return false;
    }
    
    // Set up interrupt for Radio 1
    radio1.setDio1Action(radio1ISR);
    
    // Start receiving on Radio 1
    state = radio1.startReceive();
    if (state != RADIOLIB_ERR_NONE) {
        Serial.printf("Failed to start RX! Error code: %d\n", state);
        return false;
    }
    
    Serial.println("✓");
    
    Serial.printf("Initializing Radio 2 @ %.1f MHz... ", RADIO2_FREQ);
    
    // Initialize Radio 2 (Mesh/Relay) with RadioLib
    state = radio2.begin(RADIO2_FREQ, RADIO2_BW, RADIO2_SF, RADIO2_CR, 
                        RADIO2_SYNC, RADIO2_POWER);
    if (state != RADIOLIB_ERR_NONE) {
        Serial.printf("Failed! Error code: %d\n", state);
        Serial.println("⚠ Radio 2 initialization failed - continuing with Radio 1 only");
        
        #if ENABLE_DUAL_RADIO
        // Initialize dual radio manager with only Radio 1
        Serial.print("Initializing dual radio manager (Radio 1 only)... ");
        radioManager.begin(&radio1, nullptr);
        radioManager.setRadio1Mode(RADIO_MODE_RX_CONTINUOUS);
        Serial.println("✓");
        #endif
        
        return true;  // Continue with Radio 1 only
    }
    
    // Set up interrupt for Radio 2
    radio2.setDio1Action(radio2ISR);
    
    // Start receiving on Radio 2
    state = radio2.startReceive();
    if (state != RADIOLIB_ERR_NONE) {
        Serial.printf("Failed to start RX! Error code: %d\n", state);
        Serial.println("⚠ Radio 2 RX start failed - continuing with Radio 1 only");
        
        #if ENABLE_DUAL_RADIO
        // Initialize dual radio manager with only Radio 1
        Serial.print("Initializing dual radio manager (Radio 1 only)... ");
        radioManager.begin(&radio1, nullptr);
        radioManager.setRadio1Mode(RADIO_MODE_RX_CONTINUOUS);
        Serial.println("✓");
        #endif
        
        return true;  // Continue with Radio 1 only
    }
    
    Serial.println("✓");
    
    #if ENABLE_DUAL_RADIO
    // Initialize dual radio manager with both radios
    Serial.print("Initializing dual radio manager (both radios)... ");
    radioManager.begin(&radio1, &radio2);
    
    // Set Radio 1 to continuous RX for GCS communication
    radioManager.setRadio1Mode(RADIO_MODE_RX_CONTINUOUS);
    
    // Set Radio 2 to deep sleep initially (relay inactive)
    radioManager.setRadio2Mode(RADIO_MODE_SLEEP);
    radioManager.setRelayActive(false);
    
    Serial.println("✓");
    #endif
    
    return true;
}

// Radio ISRs for RadioLib interrupt-driven operation
void radio1ISR(void) {
    // Set flag for main loop processing
    radio1RxDoneFlag = true;
}

void radio2ISR(void) {
    // Set flag for main loop processing
    radio2RxDoneFlag = true;
}

void handleRxDone() {
    // Read packet from radio using RadioLib
    int16_t state = radio1.readData(rxBuffer, sizeof(rxBuffer));
    
    if (state > 0) {
        // state contains the number of bytes read
        uint8_t packetLength = state;
        
        // Get link metrics
        linkQuality.rssi = radio1.getRSSI();
        linkQuality.snr = radio1.getSNR();
        linkQuality.packetsReceived++;
        linkQuality.consecutiveLost = 0;
        
        #if ENABLE_ADAPTIVE_MOD
        // Update adaptive modulation with link quality
        adaptiveMod.updateLinkQuality(linkQuality.rssi, linkQuality.snr, true);
        #endif
        
        // Reset jamming counter on good packet reception
        if (jammingDetectCounter > 0) {
            Serial.printf("✓ Jamming counter reset (was %d) - good packet received\n", jammingDetectCounter);
        }
        jammingDetectCounter = 0;
        
        // Track consecutive good packets for hysteresis
        consecutiveGoodPackets++;
        
        // Process packet based on type
        processPacket(rxBuffer, packetLength);
        
        // Flash LED
        digitalWrite(LED_PIN, HIGH);
        delay(20);
        digitalWrite(LED_PIN, LOW);
    } else if (state == RADIOLIB_ERR_CRC_MISMATCH) {
        Serial.println("⚠ CRC error on Radio 1");
    }
    
    // Restart receiving
    radio1.startReceive();
}

void handleTxDone() {
    // Update scheduler state
    // Transmission complete - scheduler will handle next packet
    
    // Radio automatically returns to RX mode in SX1262Direct
}

void handleCadDone() {
    // CAD done - RadioLib handles this internally with scanChannel()
    // This function is kept for compatibility but not actively used
    // RadioLib's scanChannel() returns RADIOLIB_CHANNEL_FREE or PREAMBLE_DETECTED
}

// ═══════════════════════════════════════════════════════════════════
// RADIO 2 HANDLERS (902 MHz - Mesh/Relay)
// ═══════════════════════════════════════════════════════════════════

void handleRadio2RxDone() {
    // Read packet from Radio 2 using RadioLib
    int16_t state = radio2.readData(rxBuffer, sizeof(rxBuffer));
    
    if (state > 0) {
        // state contains the number of bytes read
        uint8_t packetLength = state;
        
        // Get link metrics
        float rssi = radio2.getRSSI();
        float snr = radio2.getSNR();
        
        Serial.printf("← Radio 2 RX: %d bytes, RSSI=%.1f, SNR=%.1f\n", 
                     packetLength, rssi, snr);
        
        // In frequency bridge mode, forward mesh packets to GCS via Radio 1
        if (currentMode == MODE_FREQUENCY_BRIDGE) {
            // Extract system ID from MAVLink packet
            uint8_t systemId = 0;
            MavlinkExtractResult result = extractSystemId(rxBuffer, packetLength, &systemId);
            
            if (result == MAVLINK_EXTRACT_SUCCESS) {
                // Track relay activity
                if (!isRelayingForPeer(systemId)) {
                    addRelayTarget(systemId);
                } else {
                    updateRelayActivity(systemId);
                }
            }
            
            #if ENABLE_SCHEDULER
            // Schedule packet for transmission to GCS on Radio 1
            scheduler.schedule(rxBuffer, packetLength);
            #endif
            
            // Update bridge statistics
            bridgeStats.meshToGcsPackets++;
            bridgeStats.meshToGcsBytes += packetLength;
            
            Serial.printf("✓ Forwarded mesh packet to GCS: %d bytes (sysid=%d)\n", 
                         packetLength, systemId);
        }
        
        // Flash LED
        digitalWrite(LED_PIN, HIGH);
        delay(20);
        digitalWrite(LED_PIN, LOW);
    } else if (state == RADIOLIB_ERR_CRC_MISMATCH) {
        Serial.println("⚠ CRC error on Radio 2");
    }
    
    // Restart receiving
    radio2.startReceive();
}

void handleRadio2TxDone() {
    // Radio 2 transmission complete
    Serial.println("✓ Radio 2 TX complete");
    
    // Radio automatically returns to RX mode in SX1262Direct
}

void handleRadio2CadDone() {
    // CAD done - RadioLib handles this internally with scanChannel()
    // This function is kept for compatibility but not actively used
    // RadioLib's scanChannel() returns RADIOLIB_CHANNEL_FREE or PREAMBLE_DETECTED
}

void sendPacket(uint8_t* data, size_t length) {
    // In relay mode, forward through secondary
    if (currentMode == MODE_RELAY) {
        forwardToSecondary(data, length);
        return;
    }
    
    // Direct mode or bridge mode - transmit using RadioLib
    radioErrors.totalTransmissions++;
    
    #if ENABLE_CAD
    // Perform CAD before transmission if enabled
    int16_t cadState = radio1.scanChannel();
    if (cadState == RADIOLIB_CHANNEL_FREE) {
        // Channel is free, proceed with transmission
    } else if (cadState == PREAMBLE_DETECTED) {
        Serial.println("⚠ CAD: Channel busy - deferring transmission");
        radioErrors.txFailures++;
        return;
    }
    #endif
    
    // Transmit packet using RadioLib
    int16_t state = radio1.transmit(data, length);
    
    if (state == RADIOLIB_ERR_NONE) {
        radioErrors.successfulTransmissions++;
        
        digitalWrite(LED_PIN, HIGH);
        delay(50);
        digitalWrite(LED_PIN, LOW);
        
        // Restart receiving after transmission
        radio1.startReceive();
    } else {
        Serial.printf("✗ Radio 1 TX failed: %d\n", state);
        radioErrors.txFailures++;
        radioErrors.lastErrorTime = millis();
        
        // Track transmission success rate
        Serial.printf("  → TX Success Rate: %.1f%% (%lu/%lu)\n",
                     radioErrors.getSuccessRate(),
                     radioErrors.successfulTransmissions,
                     radioErrors.totalTransmissions);
        
        // Restart receiving after failed transmission
        radio1.startReceive();
    }
}

void sendHeartbeat() {
    txBuffer[0] = PACKET_HEARTBEAT;
    txBuffer[1] = (sequenceNumber >> 8) & 0xFF;
    txBuffer[2] = sequenceNumber & 0xFF;
    txBuffer[3] = currentMode;
    
    sendPacket(txBuffer, 4);
    linkQuality.packetsExpected++;
    sequenceNumber++;
    
    // Track consecutive losses
    if (linkQuality.packetsExpected > linkQuality.packetsReceived) {
        linkQuality.consecutiveLost++;
    }
}

// ═══════════════════════════════════════════════════════════════════
// MAVLINK PRIORITY DETECTION
// ═══════════════════════════════════════════════════════════════════

/**
 * @brief Determine MAVLink message priority tier based on message ID
 * 
 * Priority tiers:
 * - Tier 1 (Highest): Commands, mode changes, parameter sets
 * - Tier 2 (Medium): Mission items, acknowledgments, requests
 * - Tier 3 (Lowest): Telemetry, status messages, heartbeats
 * 
 * @param packet Pointer to MAVLink packet data
 * @param length Length of packet in bytes
 * @return Priority tier (1-3), or 3 if unable to determine
 */
uint8_t getMavlinkPriority(const uint8_t* packet, size_t length) {
    // Extract message ID from packet
    MavlinkPacketInfo info = extractPacketInfo(packet, length);
    
    if (info.result != MAVLINK_EXTRACT_SUCCESS) {
        // Unable to parse - default to lowest priority
        return 3;
    }
    
    uint32_t msgId = info.messageId;
    
    // Tier 1: Critical commands and control messages
    // These must be delivered immediately for safety and control
    if (msgId == 76 ||    // COMMAND_LONG
        msgId == 11 ||    // SET_MODE
        msgId == 23 ||    // PARAM_SET
        msgId == 81 ||    // MANUAL_CONTROL
        msgId == 82 ||    // RC_CHANNELS_OVERRIDE
        msgId == 84 ||    // ACTUATOR_CONTROL_TARGET
        msgId == 85 ||    // SET_ACTUATOR_CONTROL_TARGET
        msgId == 511 ||   // COMMAND_INT
        msgId == 512) {   // COMMAND_CANCEL
        return 1;
    }
    
    // Tier 2: Mission items, acknowledgments, and requests
    // Important but can tolerate slight delay
    if (msgId == 39 ||    // MISSION_ITEM
        msgId == 40 ||    // MISSION_REQUEST
        msgId == 41 ||    // MISSION_SET_CURRENT
        msgId == 43 ||    // MISSION_REQUEST_LIST
        msgId == 44 ||    // MISSION_COUNT
        msgId == 45 ||    // MISSION_CLEAR_ALL
        msgId == 47 ||    // MISSION_ACK
        msgId == 51 ||    // MISSION_REQUEST_INT
        msgId == 73 ||    // MISSION_ITEM_INT
        msgId == 77 ||    // COMMAND_ACK
        msgId == 20 ||    // PARAM_REQUEST_READ
        msgId == 21 ||    // PARAM_REQUEST_LIST
        msgId == 22 ||    // PARAM_VALUE
        msgId == 254) {   // STATUSTEXT
        return 2;
    }
    
    // Tier 3: Telemetry and status messages (default)
    // Can tolerate delay, sent frequently
    // Includes: HEARTBEAT, ATTITUDE, GLOBAL_POSITION_INT, GPS_RAW_INT, etc.
    return 3;
}

// ═══════════════════════════════════════════════════════════════════
// PACKET PROCESSING
// ═══════════════════════════════════════════════════════════════════
void processPacket(uint8_t* data, size_t length) {
    if (length < 1) return;
    
    // In frequency bridge mode, forward all GCS packets to Secondary
    if (currentMode == MODE_FREQUENCY_BRIDGE) {
        // Binary protocol: Send BRIDGE_TX command
        sendBinaryBridgeTx(UART_SECONDARY, 0, linkQuality.rssi, linkQuality.snr, 
                          data, length, &binaryStats);
        
        // Update bridge statistics (Requirement 7.1)
        bridgeStats.gcsToMeshPackets++;
        bridgeStats.gcsToMeshBytes += length;
        
        Serial.printf("→ Forwarded GCS packet to Secondary: %d bytes\n", length);
        return;
    }
    
    // Legacy packet processing for other modes
    uint8_t packetType = data[0];
    
    switch(packetType) {
        case PACKET_HEARTBEAT:
            // Heartbeat response from GCS
            Serial.println("Heartbeat ACK from GCS");
            break;
            
        case PACKET_DATA:
            // Data packet - will forward to FC when MAVLink added
            Serial.printf("Data packet received: %d bytes\n", length);
            break;
            
        case PACKET_ACK:
            // Acknowledgment 
            break;
            
        case PACKET_RELAY_DATA:
            // Data relayed through secondary
            Serial.println("Received relay data from secondary");
            break;
    }
}

// ═══════════════════════════════════════════════════════════════════
// HEX ENCODING/DECODING WITH VALIDATION
// ═══════════════════════════════════════════════════════════════════
bool hexToBytes(const String& hexStr, uint8_t* output, size_t maxLen, size_t* outLen) {
    if (hexStr.length() % 2 != 0) {
        Serial.println("⚠ Invalid hex string length");
        return false;
    }
    
    *outLen = hexStr.length() / 2;
    if (*outLen > maxLen) {
        Serial.println("⚠ Hex data exceeds buffer size");
        return false;
    }
    
    for (size_t i = 0; i < *outLen; i++) {
        String byteStr = hexStr.substring(i * 2, i * 2 + 2);
        char* endPtr;
        long val = strtol(byteStr.c_str(), &endPtr, 16);
        
        if (*endPtr != '\0' || val < 0 || val > 255) {
            Serial.printf("⚠ Invalid hex byte at position %d: %s\n", i, byteStr.c_str());
            return false;
        }
        
        output[i] = (uint8_t)val;
    }
    
    return true;
}

String bytesToHex(const uint8_t* data, size_t len) {
    String hexStr = "";
    hexStr.reserve(len * 2);
    
    for (size_t i = 0; i < len; i++) {
        char hex[3];
        sprintf(hex, "%02X", data[i]);
        hexStr += hex;
    }
    
    return hexStr;
}

// ═══════════════════════════════════════════════════════════════════
// UART COMMUNICATION WITH SECONDARY
// ═══════════════════════════════════════════════════════════════════
void checkUart() {
    // Binary protocol: Use state machine to process incoming packets
    processBinaryUart(UART_SECONDARY, &binaryRxBuffer, &binaryStats);
}


void sendUartCommand(String command, String payload, bool requiresAck) {
    // Binary protocol: Map command strings to binary commands
    if (command == "ACTIVATE_RELAY") {
        bool activate = (payload == "true");
        sendBinaryRelayActivate(UART_SECONDARY, activate, &binaryStats);
    } else if (command == "BROADCAST_RELAY_REQUEST") {
        // Extract RSSI, SNR, packet loss from context
        float packetLoss = linkQuality.getPacketLossPercent();
        sendBinaryBroadcastRelayReq(UART_SECONDARY, linkQuality.rssi, 
                                   linkQuality.snr, packetLoss, &binaryStats);
    } else {
        Serial.printf("⚠ Unknown binary command: %s\n", command.c_str());
        return;
    }
    
    // Track command if it requires acknowledgment
    if (requiresAck) {
        PendingCommand pending;
        pending.command = command;
        pending.payload = payload;
        pending.sentTime = millis();
        pending.retryCount = 0;
        pending.requiresAck = true;
        pendingCommands.push_back(pending);
        
        Serial.printf("→ Sent UART command: %s (awaiting ACK)\n", command.c_str());
    } else {
        Serial.printf("→ Sent UART command: %s\n", command.c_str());
    }
}

void checkPendingCommands() {
    unsigned long now = millis();
    
    for (auto it = pendingCommands.begin(); it != pendingCommands.end(); ) {
        // Check if command has timed out (Requirement 6.4)
        if (now - it->sentTime > UART_ACK_TIMEOUT) {
            if (it->retryCount < MAX_UART_RETRIES) {
                // Retry with exponential backoff (Requirement 6.4)
                uint32_t backoff = UART_ACK_TIMEOUT * (1 << it->retryCount);  // 500ms, 1s, 2s
                
                Serial.printf("⚠ UART command timeout: %s (retry %d/%d, backoff: %dms)\n", 
                              it->command.c_str(), it->retryCount + 1, MAX_UART_RETRIES, backoff);
                
                uartErrors.timeouts++;
                uartErrors.lastErrorTime = millis();
                
                // Resend command using binary protocol
                if (it->command == "ACTIVATE_RELAY") {
                    bool activate = (it->payload == "true");
                    sendBinaryRelayActivate(UART_SECONDARY, activate, &binaryStats);
                } else if (it->command == "BROADCAST_RELAY_REQUEST") {
                    float packetLoss = linkQuality.getPacketLossPercent();
                    sendBinaryBroadcastRelayReq(UART_SECONDARY, linkQuality.rssi, 
                                               linkQuality.snr, packetLoss, &binaryStats);
                }
                
                // Update retry tracking
                it->sentTime = now;
                it->retryCount++;
                ++it;
            } else {
                // Max retries exceeded (Requirement 6.4)
                Serial.printf("✗ UART command failed after %d retries: %s\n", 
                              MAX_UART_RETRIES, it->command.c_str());
                Serial.println("  → Command will not be retried further");
                Serial.printf("  → Total UART errors: Parse=%lu, Overflow=%lu, Timeout=%lu, Malformed=%lu\n",
                             uartErrors.parseErrors, uartErrors.bufferOverflows, 
                             uartErrors.timeouts, uartErrors.malformedMessages);
                
                uartErrors.timeouts++;
                uartErrors.lastErrorTime = millis();
                
                it = pendingCommands.erase(it);
            }
        } else {
            ++it;
        }
    }
}

void forwardToSecondary(uint8_t* data, size_t length) {
    // Binary protocol: Send RELAY_TX command
    sendBinaryRelayTx(UART_SECONDARY, data, length, &binaryStats);
}

// ═══════════════════════════════════════════════════════════════════
// JAMMING DETECTION AND MODE SWITCHING
// ═══════════════════════════════════════════════════════════════════
void evaluateLinkQuality() {
    bool poorSignal = false;
    
    // Check RSSI
    if (linkQuality.rssi < RSSI_THRESHOLD && linkQuality.rssi != 0) {
        poorSignal = true;
    }
    
    // Check SNR
    if (linkQuality.snr < SNR_THRESHOLD && linkQuality.snr != 0) {
        poorSignal = true;
    }
    
    // Check packet loss
    float packetLoss = linkQuality.getPacketLossPercent();
    if (packetLoss > PACKET_LOSS_THRESHOLD && linkQuality.packetsExpected > 10) {
        poorSignal = true;
    }
    
    // Check consecutive losses
    if (linkQuality.consecutiveLost > JAMMING_DETECT_COUNT) {
        poorSignal = true;
    }
    
    // Update jamming detection
    if (poorSignal) {
        jammingDetectCounter++;
        consecutiveGoodPackets = 0;  // Reset good packet counter
        
        if (jammingDetectCounter >= JAMMING_DETECT_COUNT && currentMode == MODE_DIRECT) {
            Serial.println("\n⚠️  JAMMING DETECTED - Switching to relay mode");
            Serial.printf("  → RSSI: %.1f dBm, SNR: %.1f dB, Loss: %.1f%%\n",
                         linkQuality.rssi, linkQuality.snr, packetLoss);
            switchToRelayMode();
        }
        // In frequency bridge mode, broadcast relay request when jamming detected
        else if (jammingDetectCounter >= JAMMING_DETECT_COUNT && currentMode == MODE_FREQUENCY_BRIDGE) {
            Serial.println("\n⚠️  JAMMING DETECTED IN BRIDGE MODE - Broadcasting relay request");
            Serial.printf("  → RSSI: %.1f dBm, SNR: %.1f dB, Loss: %.1f%%\n",
                         linkQuality.rssi, linkQuality.snr, packetLoss);
            
            // Binary protocol: Send BROADCAST_RELAY_REQ command
            sendBinaryBroadcastRelayReq(UART_SECONDARY, linkQuality.rssi, 
                                       linkQuality.snr, packetLoss, &binaryStats);
            
            // Add small delay to ensure UART transmission completes
            delay(5);
            
            Serial.println("→ Relay request broadcast command sent to Secondary");
        }
    } else {
        // Good signal - reset jamming counter
        jammingDetectCounter = 0;
        
        // If in relay mode and signal recovered with hysteresis (5 good packets)
        if (currentMode == MODE_RELAY && 
            linkQuality.rssi > RSSI_THRESHOLD + 10 && 
            consecutiveGoodPackets >= 5) {
            Serial.println("\n✓ Signal recovered with hysteresis - Switching to direct mode");
            Serial.printf("  → RSSI: %.1f dBm, SNR: %.1f dB, Good packets: %d\n",
                         linkQuality.rssi, linkQuality.snr, consecutiveGoodPackets);
            switchToDirectMode();
            consecutiveGoodPackets = 0;  // Reset after mode switch
        }
    }
}

void switchToRelayMode() {
    // Start activation sequence using state machine
    relayStateMachine.startActivation();
    currentMode = relayStateMachine.currentMode;  // Sync global mode
    
    // Notify secondary to activate relay with ACK requirement
    sendUartCommand("ACTIVATE_RELAY", "true", true);
    
    // Set state to waiting for ACK
    relayStateMachine.transitionState = TRANSITION_WAITING_ACK;
    
    Serial.println("⏳ Waiting for secondary acknowledgment...");
}

void switchToDirectMode() {
    // Start deactivation sequence using state machine
    relayStateMachine.startDeactivation();
    currentMode = relayStateMachine.currentMode;  // Sync global mode
    
    // Notify secondary to deactivate relay with ACK requirement
    sendUartCommand("ACTIVATE_RELAY", "false", true);
    
    // Set state to waiting for ACK
    relayStateMachine.transitionState = TRANSITION_WAITING_ACK;
    
    Serial.println("⏳ Waiting for secondary acknowledgment...");
}

// ═══════════════════════════════════════════════════════════════════
// AUTOPILOT SERIAL PROCESSING
// ═══════════════════════════════════════════════════════════════════

/**
 * @brief Process buffered data to extract complete MAVLink packets
 * Handles multiple packets in buffer and preserves incomplete packets
 * Uses MavlinkUtils.h for packet detection and parsing
 */
void processBufferedPackets() {
    uint16_t processedBytes = 0;
    
    while (processedBytes < autopilotRxIndex) {
        // Search for MAVLink start marker from current position
        uint16_t searchStart = processedBytes;
        bool foundStart = false;
        uint16_t startPos = 0;
        
        for (uint16_t i = searchStart; i < autopilotRxIndex; i++) {
            if (isValidMavlinkStart(&autopilotRxBuffer[i], autopilotRxIndex - i)) {
                foundStart = true;
                startPos = i;
                break;
            }
        }
        
        if (!foundStart) {
            // No MAVLink start marker found in remaining data
            if (processedBytes == 0 && autopilotRxIndex > 100) {
                // Too much invalid data at start of buffer - discard it
                Serial.printf("⚠ Invalid MAVLink data detected: discarding %d bytes\n", autopilotRxIndex);
                
                // Log first few bytes for debugging
                Serial.print("  → First bytes: ");
                for (int i = 0; i < min(16, (int)autopilotRxIndex); i++) {
                    Serial.printf("%02X ", autopilotRxBuffer[i]);
                }
                Serial.println();
                
                autopilotRxIndex = 0;
                return;
            }
            // Otherwise keep waiting for more data
            break;
        }
        
        // Found start marker - check if we have complete packet
        uint16_t expectedLen = getExpectedPacketLength(&autopilotRxBuffer[startPos], autopilotRxIndex - startPos);
        
        if (expectedLen == 0) {
            // Not enough data to determine packet length
            break;
        }
        
        if (startPos + expectedLen > autopilotRxIndex) {
            // Incomplete packet - need more data
            break;
        }
        
        // Complete packet found - validate and enqueue
        if (expectedLen < 8 || expectedLen > 280) {
            Serial.printf("⚠ Invalid MAVLink packet length: %d bytes - discarding\n", expectedLen);
            processedBytes = startPos + 1;  // Skip this byte and continue
            continue;
        }
        
        // Extract packet info for logging
        MavlinkPacketInfo info = extractPacketInfo(&autopilotRxBuffer[startPos], expectedLen);
        
        #if ENABLE_SCHEDULER
        // Schedule packet for transmission
        scheduler.schedule(&autopilotRxBuffer[startPos], expectedLen);
        #else
        // Barebones mode: Direct transmission
        sendPacket(&autopilotRxBuffer[startPos], expectedLen);
        #endif
        
        autopilotRxCount++;
        Serial.printf("✓ MAVLink v%d packet: %d bytes%s\n", 
                     info.version, 
                     expectedLen,
                     info.hasSignature ? " (signed)" : "");
        
        // Move to next position after this packet
        processedBytes = startPos + expectedLen;
    }
    
    // Shift remaining unprocessed data to start of buffer
    if (processedBytes > 0 && processedBytes < autopilotRxIndex) {
        uint16_t remainingBytes = autopilotRxIndex - processedBytes;
        memmove(autopilotRxBuffer, 
                &autopilotRxBuffer[processedBytes],
                remainingBytes);
        autopilotRxIndex = remainingBytes;
        
        Serial.printf("→ Buffer shifted: %d bytes remaining\n", remainingBytes);
    } 
    else if (processedBytes >= autopilotRxIndex) {
        // All data processed
        autopilotRxIndex = 0;
    }
}

void processAutopilotSerial() {
    unsigned long now = millis();
    
    // Read available data with overflow protection
    while (Serial.available() && autopilotRxIndex < AUTOPILOT_BUFFER_SIZE) {
        autopilotRxBuffer[autopilotRxIndex++] = Serial.read();
        lastAutopilotRx = now;
    }
    
    // Handle buffer overflow - flush and reset
    if (Serial.available() && autopilotRxIndex >= AUTOPILOT_BUFFER_SIZE) {
        Serial.printf("⚠ Autopilot buffer overflow: %d bytes in buffer, %d bytes waiting\n", 
                     autopilotRxIndex, Serial.available());
        
        // Log first few bytes for debugging
        Serial.print("  → Buffer start: ");
        for (int i = 0; i < min(16, (int)autopilotRxIndex); i++) {
            Serial.printf("%02X ", autopilotRxBuffer[i]);
        }
        Serial.println();
        
        // Flush remaining serial data
        int flushed = 0;
        while (Serial.available()) {
            Serial.read();
            flushed++;
        }
        Serial.printf("  → Flushed %d bytes from serial buffer\n", flushed);
        
        // Reset buffer
        autopilotRxIndex = 0;
        lastAutopilotRx = now;
        return;
    }
    
    // Process buffer after timeout (50ms - allows complete packet reception)
    if (autopilotRxIndex > 0 && (now - lastAutopilotRx > PACKET_TIMEOUT)) {
        processBufferedPackets();
    }
    
    // Additional timeout check for incomplete packets (100ms max)
    if (autopilotRxIndex > 0 && (now - lastAutopilotRx > 100)) {
        Serial.printf("⚠ Incomplete packet timeout: %d bytes waiting for %dms\n", 
                     autopilotRxIndex, (int)(now - lastAutopilotRx));
        
        // Log buffer contents for debugging
        Serial.print("  → Buffer contents: ");
        for (int i = 0; i < min(16, (int)autopilotRxIndex); i++) {
            Serial.printf("%02X ", autopilotRxBuffer[i]);
        }
        Serial.println();
        
        // Try to process what we have
        processBufferedPackets();
        
        // If still data remaining after processing, it's likely corrupt - flush it
        if (autopilotRxIndex > 0) {
            Serial.printf("⚠ Flushing %d bytes of stale/corrupt data\n", autopilotRxIndex);
            autopilotRxIndex = 0;
        }
        
        lastAutopilotRx = now;
    }
}

// ═══════════════════════════════════════════════════════════════════
// RELAY TARGET MANAGEMENT
// ═══════════════════════════════════════════════════════════════════

/**
 * @brief Add a peer drone to the relay target list
 * @param systemId MAVLink system ID of the peer drone
 */
void addRelayTarget(uint8_t systemId) {
    // Check if already in list
    for (int i = 0; i < MAX_RELAY_TARGETS; i++) {
        if (relayTargets[i].active && relayTargets[i].systemId == systemId) {
            // Already relaying for this drone - update activity time
            relayTargets[i].lastActivity = millis();
            Serial.printf("→ Relay target %d already active - updated activity\n", systemId);
            return;
        }
    }
    
    // Find empty slot
    for (int i = 0; i < MAX_RELAY_TARGETS; i++) {
        if (!relayTargets[i].active) {
            relayTargets[i].systemId = systemId;
            relayTargets[i].active = true;
            relayTargets[i].lastActivity = millis();
            relayTargets[i].packetsRelayed = 0;
            
            Serial.printf("✓ Added relay target: System ID %d (slot %d)\n", systemId, i);
            return;
        }
    }
    
    // No empty slots - log warning
    Serial.printf("⚠ Cannot add relay target %d - all slots full\n", systemId);
}

/**
 * @brief Update last activity time for a relay target
 * @param systemId MAVLink system ID of the peer drone
 */
void updateRelayActivity(uint8_t systemId) {
    for (int i = 0; i < MAX_RELAY_TARGETS; i++) {
        if (relayTargets[i].active && relayTargets[i].systemId == systemId) {
            relayTargets[i].lastActivity = millis();
            relayTargets[i].packetsRelayed++;
            return;
        }
    }
}

/**
 * @brief Check if we are currently relaying for a specific peer drone
 * @param systemId MAVLink system ID to check
 * @return true if relaying for this system ID
 */
bool isRelayingForPeer(uint8_t systemId) {
    for (int i = 0; i < MAX_RELAY_TARGETS; i++) {
        if (relayTargets[i].active && relayTargets[i].systemId == systemId) {
            return true;
        }
    }
    return false;
}

/**
 * @brief Remove inactive relay targets after timeout period
 * Requirement 4.5: Remove system ID from relay list after 30 seconds of inactivity
 */
void cleanupInactiveRelays() {
    const uint32_t RELAY_TIMEOUT_MS = 30000;  // 30 seconds
    uint32_t now = millis();
    
    for (int i = 0; i < MAX_RELAY_TARGETS; i++) {
        if (relayTargets[i].active) {
            uint32_t inactiveTime = now - relayTargets[i].lastActivity;
            
            if (inactiveTime > RELAY_TIMEOUT_MS) {
                Serial.printf("⏱ Relay timeout for System ID %d after %d seconds\n", 
                             relayTargets[i].systemId, inactiveTime / 1000);
                Serial.printf("  → Relayed %d packets total\n", relayTargets[i].packetsRelayed);
                
                // Deactivate relay
                relayTargets[i].active = false;
                relayTargets[i].systemId = 0;
                relayTargets[i].lastActivity = 0;
                relayTargets[i].packetsRelayed = 0;
                
                Serial.printf("✓ Relay deactivated for System ID %d (slot %d)\n", 
                             relayTargets[i].systemId, i);
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════════════
// QUEUE PROCESSING
// ═══════════════════════════════════════════════════════════════════

/**
 * @brief Helper function to transmit a packet on the radio
 * @param data Packet data to transmit
 * @param len Length of packet
 * @param tier Priority tier of the packet
 * 
 * Implements direct radio control with CAD and error handling
 */
void transmitPacket(uint8_t* data, uint16_t len, uint8_t tier) {
    // Transmit on radio with optional CAD
    radioErrors.totalTransmissions++;
    
    #if ENABLE_CAD
    // Perform CAD before transmission if enabled
    int16_t cadState = radio1.scanChannel();
    if (cadState == RADIOLIB_CHANNEL_FREE) {
        // Channel is free, proceed with transmission
    } else if (cadState == PREAMBLE_DETECTED) {
        Serial.printf("⚠ CAD: Channel busy - deferring transmission (tier %d)\n", tier);
        radioErrors.txFailures++;
        return;
    }
    #endif
    
    // Transmit packet using RadioLib
    int16_t state = radio1.transmit(data, len);
    
    if (state == RADIOLIB_ERR_NONE) {
        radioErrors.successfulTransmissions++;
        txCount++;
        lastTxTier = tier;
        
        // LED indication
        digitalWrite(LED_PIN, HIGH);
        delay(50);
        digitalWrite(LED_PIN, LOW);
        
        // Restart receiving after transmission
        radio1.startReceive();
    } else {
        // TX failed
        Serial.printf("✗ Radio TX failed (tier %d): %d\n", tier, state);
        radioErrors.txFailures++;
        radioErrors.lastErrorTime = millis();
        
        // Track transmission success rate
        Serial.printf("  → TX Success Rate: %.1f%% (%lu/%lu)\n",
                     radioErrors.getSuccessRate(),
                     radioErrors.successfulTransmissions,
                     radioErrors.totalTransmissions);
        
        // Restart receiving after failed transmission
        radio1.startReceive();
    }
}

/**
 * @brief Process scheduler and transmit packets
 * 
 * Uses TDMA scheduler with adaptive modulation for optimal performance.
 * Handles slot-based transmission with CAD before each packet.
 */
void processScheduler() {
    #if ENABLE_SCHEDULER
    // Tick the scheduler - it handles slot timing and transmission internally
    scheduler.tick();
    #else
    // Barebones mode: Simple FIFO transmission (no scheduler)
    // This would be implemented if needed for barebones mode
    #endif
}

// ═══════════════════════════════════════════════════════════════════
// BINARY PROTOCOL HANDLERS
// ═══════════════════════════════════════════════════════════════════


// Global flag for ACK handling during initialization
bool g_secondaryAcknowledged = false;

/**
 * @brief Handle binary INIT command
 * Not typically received by Primary, but included for completeness
 */
void handleBinaryInit(const InitPayload* payload) {
    if (!payload) return;
    
    Serial.printf("← Received binary INIT: mode=%s, primary=%.1f MHz, secondary=%.1f MHz\n",
                 payload->mode, payload->primary_freq, payload->secondary_freq);
    
    // Primary doesn't typically receive INIT, but we can log it
}

/**
 * @brief Handle binary BRIDGE_TX command
 * Not typically received by Primary (Primary sends this to Secondary)
 */
void handleBinaryBridgeTx(const BridgePayload* payload) {
    if (!payload) return;
    
    Serial.printf("← Received binary BRIDGE_TX: sysid=%d, len=%d\n",
                 payload->system_id, payload->data_len);
    
    // Primary doesn't typically receive BRIDGE_TX
}

/**
 * @brief Handle binary BRIDGE_RX command
 * Received from Secondary when mesh network has data for GCS
 */
void handleBinaryBridgeRx(const BridgePayload* payload) {
    if (!payload) return;
    
    Serial.printf("← Received binary BRIDGE_RX: sysid=%d, len=%d, RSSI=%.1f\n",
                 payload->system_id, payload->data_len, payload->rssi);
    
    // Validate data length
    if (payload->data_len == 0 || payload->data_len > 245) {
        Serial.printf("⚠ Invalid BRIDGE_RX data length: %d\n", payload->data_len);
        return;
    }
    
    // Extract system ID from MAVLink packet if not provided
    uint8_t systemId = payload->system_id;
    if (systemId == 0) {
        MavlinkExtractResult result = extractSystemId(payload->data, payload->data_len, &systemId);
        if (result != MAVLINK_EXTRACT_SUCCESS) {
            Serial.printf("⚠ Failed to extract system ID: %s\n", getMavlinkExtractErrorString(result));
            // Continue anyway - system ID is optional for basic forwarding
        }
    }
    
    // Determine MAVLink message priority
    uint8_t priority = getMavlinkPriority(payload->data, payload->data_len);
    
    // Track relay activity if this is from a peer drone
    if (systemId > 0) {
        if (!isRelayingForPeer(systemId)) {
            addRelayTarget(systemId);
        } else {
            updateRelayActivity(systemId);
        }
    }
    
    #if ENABLE_SCHEDULER
    // Schedule packet for transmission to GCS
    scheduler.schedule(payload->data, payload->data_len);
    Serial.printf("✓ Scheduled bridge packet for GCS: %d bytes (sysid=%d, tier=%d)\n", 
                 payload->data_len, systemId, priority);
    #else
    // Barebones mode: Direct transmission
    // Need to copy to non-const buffer for sendPacket
    uint8_t tempBuffer[256];
    if (payload->data_len <= sizeof(tempBuffer)) {
        memcpy(tempBuffer, payload->data, payload->data_len);
        sendPacket(tempBuffer, payload->data_len);
        Serial.printf("✓ Sent bridge packet to GCS: %d bytes (sysid=%d)\n", 
                     payload->data_len, systemId);
    }
    #endif
    
    // Update bridge statistics
    bridgeStats.meshToGcsPackets++;
    bridgeStats.meshToGcsBytes += payload->data_len;
    
    // Update link quality metrics from bridge packets
    linkQuality.rssi = payload->rssi;
    linkQuality.snr = payload->snr;
    linkQuality.packetsReceived++;
    linkQuality.consecutiveLost = 0;
}

/**
 * @brief Handle binary STATUS_REPORT command
 * Received from Secondary with its status information
 */
void handleBinaryStatus(const StatusPayload* payload) {
    if (!payload) return;
    
    Serial.printf("← Received binary STATUS: relay=%s, packets=%lu, RSSI=%.1f\n",
                 payload->relay_active ? "active" : "inactive",
                 payload->packets_relayed, payload->rssi);
    
    // Update Secondary status tracking
    // (Could be used for monitoring Secondary health)
}

/**
 * @brief Handle binary RELAY_ACTIVATE command
 * Not typically received by Primary (Primary sends this to Secondary)
 */
void handleBinaryRelayActivate(const RelayActivatePayload* payload) {
    if (!payload) return;
    
    Serial.printf("← Received binary RELAY_ACTIVATE: %s\n",
                 payload->activate ? "ACTIVATE" : "DEACTIVATE");
    
    // Primary doesn't typically receive RELAY_ACTIVATE
}

/**
 * @brief Handle binary RELAY_TX command
 * Not typically received by Primary (Primary sends this to Secondary)
 */
void handleBinaryRelayTx(const RelayRxPayload* payload) {
    if (!payload) return;
    
    Serial.println("← Received binary RELAY_TX");
    
    // Primary doesn't typically receive RELAY_TX
}

/**
 * @brief Handle binary RELAY_RX command
 * Received from Secondary when relay path has data
 */
void handleBinaryRelayRx(const RelayRxPayload* payload) {
    if (!payload) return;
    
    // Calculate data length (payload struct size minus the data array, plus actual data)
    // The payload contains rssi (4 bytes) + snr (4 bytes) + data[245]
    // We need to determine actual data length from the packet
    // For now, we'll use a conservative approach and scan for valid MAVLink
    
    Serial.printf("← Received binary RELAY_RX: RSSI=%.1f, SNR=%.1f\n",
                 payload->rssi, payload->snr);
    
    // Find the actual data length by looking for valid MAVLink packet
    uint16_t dataLen = 0;
    if (isValidMavlinkStart(payload->data, 245)) {
        dataLen = getExpectedPacketLength(payload->data, 245);
    }
    
    if (dataLen == 0 || dataLen > 245) {
        Serial.printf("⚠ Invalid RELAY_RX data length: %d\n", dataLen);
        return;
    }
    
    #if ENABLE_SCHEDULER
    // Schedule packet for transmission to GCS
    scheduler.schedule(payload->data, dataLen);
    Serial.printf("✓ Scheduled relay packet: %d bytes\n", dataLen);
    #else
    // Barebones mode: Direct transmission
    // Need to copy to non-const buffer for sendPacket
    uint8_t tempBuffer[256];
    if (dataLen <= sizeof(tempBuffer)) {
        memcpy(tempBuffer, payload->data, dataLen);
        sendPacket(tempBuffer, dataLen);
        Serial.printf("✓ Sent relay packet: %d bytes\n", dataLen);
    }
    #endif
    
    // Update link quality metrics from relay packets
    linkQuality.rssi = payload->rssi;
    linkQuality.snr = payload->snr;
    linkQuality.packetsReceived++;
    linkQuality.consecutiveLost = 0;
    
    // Reset jamming counter on good packet reception
    jammingDetectCounter = 0;
}

/**
 * @brief Handle binary BROADCAST_RELAY_REQ command
 * Not typically received by Primary (Primary sends this to Secondary)
 */
void handleBinaryBroadcastRelayReq(const RelayRequestPayload* payload) {
    if (!payload) return;
    
    Serial.printf("← Received binary BROADCAST_RELAY_REQ: RSSI=%.1f, SNR=%.1f, loss=%.1f%%\n",
                 payload->rssi, payload->snr, payload->packet_loss);
    
    // Primary doesn't typically receive BROADCAST_RELAY_REQ
}

/**
 * @brief Handle binary ACK command
 * Received from Secondary to acknowledge commands
 */
void handleBinaryAck() {
    Serial.println("← Received binary ACK");
    
    // Set global flag for initialization sequence
    g_secondaryAcknowledged = true;
    
    // Remove from pending commands (if any)
    if (!pendingCommands.empty()) {
        // Remove the oldest pending command
        pendingCommands.erase(pendingCommands.begin());
    }
    
    // Complete state machine transition if waiting for ACK
    if (relayStateMachine.transitionState == TRANSITION_WAITING_ACK) {
        relayStateMachine.completeTransition();
        currentMode = relayStateMachine.currentMode;  // Sync global mode
        
        // Additional cleanup for mode transitions
        if (currentMode == MODE_RELAY) {
            linkQuality.reset();
        } else if (currentMode == MODE_DIRECT) {
            // Radio configuration handled by initialization
            // SX1262Direct doesn't support runtime frequency changes
            linkQuality.reset();
        }
    }
}

/**
 * @brief Handle binary STATUS_REQUEST command
 * Not typically received by Primary (Secondary requests status from Primary)
 */
void handleBinaryStatusRequest() {
    Serial.println("← Received binary STATUS_REQUEST");
    
    // Primary doesn't typically receive STATUS_REQUEST
    // But we could send our status if requested
}

/**
 * @brief Handle START_RELAY_DISCOVERY command (not used in Primary)
 * This handler is a no-op in Primary controller
 * 
 * Requirements: 10.3
 */
void handleBinaryStartRelayDiscovery(const StartRelayDiscoveryPayload* payload) {
    if (!payload) return;
    
    // This command is sent by Primary to Secondary, not received by Primary
    Serial.println("⚠ Received START_RELAY_DISCOVERY in Primary (unexpected)");
}

/**
 * @brief Handle RELAY_SELECTED notification from Secondary
 * Received when Secondary has selected a relay after discovery
 * 
 * Requirements: 10.4
 */
void handleBinaryRelaySelected(const RelaySelectedPayload* payload) {
    if (!payload) return;
    
    Serial.println("\n═══════════════════════════════════════════════════════════");
    Serial.println("  RELAY SELECTED BY SECONDARY");
    Serial.println("═══════════════════════════════════════════════════════════");
    Serial.printf("  Relay ID: %d\n", payload->relay_id);
    Serial.printf("  Mesh Link: RSSI=%.1f dBm, SNR=%.1f dB\n", 
                 payload->relay_rssi, payload->relay_snr);
    Serial.printf("  Relay Score: %.1f\n", payload->relay_score);
    Serial.println("  → Waiting for relay connection establishment...");
    Serial.println("═══════════════════════════════════════════════════════════\n");
    
    // TODO: Update state machine or tracking (Task 7.5)
    // For now, just log the event
}

/**
 * @brief Handle RELAY_ESTABLISHED notification from Secondary
 * Received when Secondary has successfully established relay connection
 * 
 * Requirements: 10.4
 */
void handleBinaryRelayEstablished(const RelayEstablishedPayload* payload) {
    if (!payload) return;
    
    Serial.println("\n═══════════════════════════════════════════════════════════");
    Serial.println("  ✓ RELAY CONNECTION ESTABLISHED");
    Serial.println("═══════════════════════════════════════════════════════════");
    Serial.printf("  Active Relay: ID=%d\n", payload->relay_id);
    Serial.println("  → Relay path is now active");
    Serial.println("  → Traffic will be forwarded through relay");
    Serial.println("═══════════════════════════════════════════════════════════\n");
    
    // TODO: Update state machine to relay mode (Task 7.5)
    // For now, just log the event
}

/**
 * @brief Handle RELAY_LOST notification from Secondary
 * Received when Secondary loses connection to active relay
 * 
 * Requirements: 10.4
 */
void handleBinaryRelayLost(const RelayLostPayload* payload) {
    if (!payload) return;
    
    const char* reason_str = "UNKNOWN";
    switch (static_cast<RelayLostReason>(payload->reason)) {
        case RELAY_LOST_HEARTBEAT_TIMEOUT: reason_str = "HEARTBEAT_TIMEOUT"; break;
        case RELAY_LOST_LINK_QUALITY: reason_str = "LINK_QUALITY"; break;
        case RELAY_LOST_REJECTION: reason_str = "REJECTION"; break;
        case RELAY_LOST_GCS_RESTORED: reason_str = "GCS_RESTORED"; break;
    }
    
    Serial.println("\n═══════════════════════════════════════════════════════════");
    Serial.println("  ✗ RELAY CONNECTION LOST");
    Serial.println("═══════════════════════════════════════════════════════════");
    Serial.printf("  Lost Relay: ID=%d\n", payload->relay_id);
    Serial.printf("  Reason: %s\n", reason_str);
    
    if (payload->reason == RELAY_LOST_GCS_RESTORED) {
        Serial.println("  → GCS link restored - relay no longer needed");
    } else {
        Serial.println("  → Attempting to find new relay...");
    }
    
    Serial.println("═══════════════════════════════════════════════════════════\n");
    
    // TODO: Trigger new relay discovery if needed (Task 7.5)
    // For now, just log the event
}


// ═══════════════════════════════════════════════════════════════════
// STATUS AND DEBUGGING
// ═══════════════════════════════════════════════════════════════════
void printHeader() {
    Serial.println("\n\n╔════════════════════════════════════════════════╗");
    Serial.println("║  PRIMARY NODE v1.0                             ║");
    Serial.println("║  Full Control + Relay Switching                ║");
    Serial.println("╚════════════════════════════════════════════════╝\n");
}

void printStatus() {
    Serial.println("\n╔════════════════════════════════════════════════════════════╗");
    Serial.println("║           PRIMARY NODE STATUS & DIAGNOSTICS                ║");
    Serial.println("╚════════════════════════════════════════════════════════════╝");
    
    // ═══════════════════════════════════════════════════════════════
    // OPERATING MODE (Requirement 8.1)
    // ═══════════════════════════════════════════════════════════════
    Serial.println("\n┌─ OPERATING MODE ─────────────────────────────────────────┐");
    
    const char* modeStr = "UNKNOWN";
    const char* modeDesc = "";
    
    switch(currentMode) {
        case MODE_DIRECT:
            modeStr = "DIRECT";
            modeDesc = "Normal GCS link @ 915 MHz";
            break;
        case MODE_RELAY:
            modeStr = "SELF_RELAY";
            modeDesc = "Using peer relay (jammed)";
            break;
        case MODE_FREQUENCY_BRIDGE:
            modeStr = "BRIDGE";
            modeDesc = "915↔902 MHz frequency bridge";
            break;
        case MODE_SWITCHING:
            modeStr = "SWITCHING";
            modeDesc = "Transitioning between modes";
            break;
    }
    
    Serial.printf("│ Current Mode: %s\n", modeStr);
    Serial.printf("│ Description:  %s\n", modeDesc);
    
    // Count active peer relays
    int activeRelayCount = 0;
    for (int i = 0; i < MAX_RELAY_TARGETS; i++) {
        if (relayTargets[i].active) {
            activeRelayCount++;
        }
    }
    
    // Determine combined mode status
    if (currentMode == MODE_FREQUENCY_BRIDGE && activeRelayCount > 0) {
        Serial.println("│ Sub-Mode:     COMBINED (Bridge + Peer Relay)");
    } else if (activeRelayCount > 0) {
        Serial.println("│ Sub-Mode:     PEER_RELAY (Helping others)");
    }
    
    Serial.println("└──────────────────────────────────────────────────────────┘");
    
    // ═══════════════════════════════════════════════════════════════
    // LINK QUALITY FOR 915 MHz (Requirement 8.1, 8.4)
    // ═══════════════════════════════════════════════════════════════
    Serial.println("\n┌─ LINK QUALITY (915 MHz GCS Link) ────────────────────────┐");
    Serial.printf("│ RSSI:              %.1f dBm", linkQuality.rssi);
    if (linkQuality.rssi < RSSI_THRESHOLD) {
        Serial.print(" ⚠ WEAK");
    } else if (linkQuality.rssi > -70) {
        Serial.print(" ✓ STRONG");
    }
    Serial.println();
    
    Serial.printf("│ SNR:               %.1f dB", linkQuality.snr);
    if (linkQuality.snr < SNR_THRESHOLD) {
        Serial.print(" ⚠ POOR");
    } else if (linkQuality.snr > 10) {
        Serial.print(" ✓ GOOD");
    }
    Serial.println();
    
    float packetLoss = linkQuality.getPacketLossPercent();
    Serial.printf("│ Packet Loss:       %.1f%% (%d/%d)", 
                  packetLoss,
                  linkQuality.packetsExpected - linkQuality.packetsReceived,
                  linkQuality.packetsExpected);
    if (packetLoss > PACKET_LOSS_THRESHOLD) {
        Serial.print(" ⚠ HIGH");
    } else if (packetLoss < 5) {
        Serial.print(" ✓ LOW");
    }
    Serial.println();
    
    Serial.printf("│ Consecutive Lost:  %d", linkQuality.consecutiveLost);
    if (linkQuality.consecutiveLost > 3) {
        Serial.print(" ⚠");
    }
    Serial.println();
    
    Serial.printf("│ Jamming Counter:   %d/%d", jammingDetectCounter, JAMMING_DETECT_COUNT);
    if (jammingDetectCounter >= JAMMING_DETECT_COUNT) {
        Serial.print(" ⚠ JAMMED");
    } else if (jammingDetectCounter > 0) {
        Serial.print(" ⚠ DEGRADED");
    } else {
        Serial.print(" ✓ CLEAR");
    }
    Serial.println();
    
    Serial.printf("│ Good Packets:      %d consecutive\n", consecutiveGoodPackets);
    Serial.println("└──────────────────────────────────────────────────────────┘");
    
    // ═══════════════════════════════════════════════════════════════
    // RADIO 2 STATUS (902 MHz Mesh/Relay)
    // ═══════════════════════════════════════════════════════════════
    Serial.println("\n┌─ RADIO 2 STATUS (902 MHz Mesh/Relay) ────────────────────┐");
    
    #if ENABLE_DUAL_RADIO
    RadioMode radio2Mode = radioManager.getRadio2Mode();
    const char* radio2ModeStr = "UNKNOWN";
    switch (radio2Mode) {
        case RADIO_MODE_SLEEP:          radio2ModeStr = "SLEEP"; break;
        case RADIO_MODE_STANDBY:        radio2ModeStr = "STANDBY"; break;
        case RADIO_MODE_RX_CONTINUOUS:  radio2ModeStr = "RX_CONTINUOUS"; break;
        case RADIO_MODE_RX_DUTY_CYCLE:  radio2ModeStr = "RX_DUTY_CYCLE"; break;
        case RADIO_MODE_TX:             radio2ModeStr = "TX"; break;
        case RADIO_MODE_CAD:            radio2ModeStr = "CAD"; break;
    }
    
    Serial.printf("│ Mode:              %s\n", radio2ModeStr);
    Serial.printf("│ Relay Active:      %s\n", radioManager.isRelayActive() ? "YES" : "NO");
    
    RadioStats radio2Stats = radioManager.getRadio2Stats();
    Serial.printf("│ TX Count:          %lu\n", radio2Stats.txCount);
    Serial.printf("│ RX Count:          %lu\n", radio2Stats.rxCount);
    Serial.printf("│ State Transitions: %lu\n", radio2Stats.stateTransitions);
    Serial.printf("│ Interference Prev: %lu\n", radio2Stats.interferenceEvents);
    Serial.printf("│ Power Save Events: %lu\n", radio2Stats.powerSaveEvents);
    #else
    Serial.println("│ Dual Radio Manager: DISABLED (barebones mode)");
    Serial.println("│ Radio 2 operating independently");
    #endif
    
    Serial.println("└──────────────────────────────────────────────────────────┘");
    
    // Get slot statistics (used in multiple sections below)
    #if ENABLE_SCHEDULER
    SlotStats criticalStats = scheduler.getSlotStats(SLOT_CRITICAL);
    SlotStats telemetryStats = scheduler.getSlotStats(SLOT_TELEMETRY);
    SlotStats relayStats = scheduler.getSlotStats(SLOT_RELAY);
    SlotStats adaptiveStats = scheduler.getSlotStats(SLOT_ADAPTIVE);
    
    uint32_t criticalTx = criticalStats.txCount;
    uint32_t criticalDrop = criticalStats.dropCount;
    uint32_t telemetryTx = telemetryStats.txCount;
    uint32_t telemetryDrop = telemetryStats.dropCount;
    uint32_t relayTx = relayStats.txCount;
    uint32_t relayDrop = relayStats.dropCount;
    uint32_t adaptiveTx = adaptiveStats.txCount;
    uint32_t adaptiveDrop = adaptiveStats.dropCount;
    #else
    // Barebones mode: No slot statistics
    uint32_t criticalTx = 0;
    uint32_t criticalDrop = 0;
    uint32_t telemetryTx = 0;
    uint32_t telemetryDrop = 0;
    uint32_t relayTx = 0;
    uint32_t relayDrop = 0;
    uint32_t adaptiveTx = 0;
    uint32_t adaptiveDrop = 0;
    #endif
    
    // ═══════════════════════════════════════════════════════════════
    // BRIDGE STATISTICS (Requirement 8.3)
    // ═══════════════════════════════════════════════════════════════
    if (currentMode == MODE_FREQUENCY_BRIDGE || activeRelayCount > 0) {
        Serial.println("\n┌─ BRIDGE STATISTICS ──────────────────────────────────────┐");
        
        uint32_t totalForwarded = criticalTx + telemetryTx + relayTx + adaptiveTx;
        
        Serial.printf("│ Packets Forwarded: %lu total\n", totalForwarded);
        Serial.printf("│   ├─ CRITICAL:    %lu\n", criticalTx);
        Serial.printf("│   ├─ TELEMETRY:   %lu\n", telemetryTx);
        Serial.printf("│   ├─ RELAY:       %lu\n", relayTx);
        Serial.printf("│   └─ ADAPTIVE:    %lu\n", adaptiveTx);
        
        #if ENABLE_SCHEDULER
        // Get queue depths
        uint16_t criticalDepth = scheduler.getQueueDepth(SLOT_CRITICAL);
        uint16_t telemetryDepth = scheduler.getQueueDepth(SLOT_TELEMETRY);
        uint16_t relayDepth = scheduler.getQueueDepth(SLOT_RELAY);
        uint16_t adaptiveDepth = scheduler.getQueueDepth(SLOT_ADAPTIVE);
        uint16_t totalQueued = criticalDepth + telemetryDepth + relayDepth + adaptiveDepth;
        #else
        uint16_t totalQueued = 0;
        #endif
        
        // Estimate latency based on slot timing (100ms per slot)
        uint32_t estimatedLatency = 30 + (totalQueued * 100);  // Base 30ms + 100ms per queued packet
        
        Serial.printf("│ Est. Latency:      ~%lu ms", estimatedLatency);
        if (estimatedLatency > 200) {
            Serial.print(" ⚠ HIGH");
        } else if (estimatedLatency < 100) {
            Serial.print(" ✓ LOW");
        }
        Serial.println();
        
        Serial.printf("│ Queue Depth:       %d packets\n", totalQueued);
        Serial.printf("│ Packets Dropped:   %lu total\n", 
                     criticalDrop + telemetryDrop + relayDrop + adaptiveDrop);
        
        Serial.println("└──────────────────────────────────────────────────────────┘");
    }
    
    // ═══════════════════════════════════════════════════════════════
    // ACTIVE RELAY SYSTEM IDs (Requirement 8.1, 8.3)
    // ═══════════════════════════════════════════════════════════════
    Serial.println("\n┌─ ACTIVE RELAY TARGETS (Peer Drones) ─────────────────────┐");
    
    if (activeRelayCount > 0) {
        Serial.printf("│ Active Relays:     %d peer drone(s)\n", activeRelayCount);
        Serial.println("│");
        
        for (int i = 0; i < MAX_RELAY_TARGETS; i++) {
            if (relayTargets[i].active) {
                uint32_t inactiveTime = millis() - relayTargets[i].lastActivity;
                uint32_t inactiveSec = inactiveTime / 1000;
                
                Serial.printf("│ ┌─ System ID: %d\n", relayTargets[i].systemId);
                Serial.printf("│ │  Packets Relayed:  %lu\n", relayTargets[i].packetsRelayed);
                Serial.printf("│ │  Last Activity:    %lu sec ago", inactiveSec);
                
                if (inactiveSec > 20) {
                    Serial.print(" ⚠ STALE");
                } else if (inactiveSec < 5) {
                    Serial.print(" ✓ ACTIVE");
                }
                Serial.println();
                
                // Calculate timeout remaining
                uint32_t timeoutRemaining = 30 - inactiveSec;
                if (inactiveSec < 30) {
                    Serial.printf("│ │  Timeout In:       %lu sec\n", timeoutRemaining);
                }
                
                Serial.println("│ └─");
            }
        }
    } else {
        Serial.println("│ No active peer relays");
        Serial.println("│ (Not currently relaying for other drones)");
    }
    
    Serial.println("└──────────────────────────────────────────────────────────┘");
    
    // ═══════════════════════════════════════════════════════════════
    // SCHEDULER STATISTICS
    // ═══════════════════════════════════════════════════════════════
    Serial.println("\n┌─ SCHEDULER STATISTICS ───────────────────────────────────┐");
    
    #if ENABLE_SCHEDULER
    // Get queue depths (slot stats already retrieved above)
    uint16_t criticalDepth = scheduler.getQueueDepth(SLOT_CRITICAL);
    uint16_t telemetryDepth = scheduler.getQueueDepth(SLOT_TELEMETRY);
    uint16_t relayDepth = scheduler.getQueueDepth(SLOT_RELAY);
    uint16_t adaptiveDepth = scheduler.getQueueDepth(SLOT_ADAPTIVE);
    
    Serial.println("│ Slot Statistics:");
    Serial.printf("│   CRITICAL (40%%):   TX:%5lu  Drop:%4lu  Queue:%2d\n",
                 criticalTx, criticalDrop, criticalDepth);
    Serial.printf("│   TELEMETRY (30%%):  TX:%5lu  Drop:%4lu  Queue:%2d\n",
                 telemetryTx, telemetryDrop, telemetryDepth);
    Serial.printf("│   RELAY (20%%):      TX:%5lu  Drop:%4lu  Queue:%2d\n",
                 relayTx, relayDrop, relayDepth);
    Serial.printf("│   ADAPTIVE (10%%):   TX:%5lu  Drop:%4lu  Queue:%2d\n",
                 adaptiveTx, adaptiveDrop, adaptiveDepth);
    #else
    Serial.println("│ Scheduler: DISABLED (barebones mode)");
    Serial.println("│ Using simple FIFO transmission");
    #endif
    
    Serial.println("└──────────────────────────────────────────────────────────┘");
    
    // ═══════════════════════════════════════════════════════════════
    // ADAPTIVE MODULATION STATISTICS
    // ═══════════════════════════════════════════════════════════════
    Serial.println("\n┌─ ADAPTIVE MODULATION ────────────────────────────────────┐");
    
    #if ENABLE_ADAPTIVE_MOD
    uint8_t currentProfile = adaptiveMod.getCurrentProfile();
    const ModProfile& profile = adaptiveMod.getProfile(currentProfile);
    
    Serial.printf("│ Current Profile:   %s\n", profile.name);
    Serial.printf("│ Spreading Factor:  SF%d\n", profile.sf);
    Serial.printf("│ Bandwidth:         %lu kHz\n", profile.bw / 1000);
    Serial.printf("│ Data Rate:         %d bps\n", profile.dataRate);
    Serial.printf("│ Sensitivity:       %d dBm\n", profile.sensitivity);
    Serial.printf("│ Profile Switches:  %lu\n", adaptiveMod.getProfileSwitchCount());
    #else
    Serial.println("│ Adaptive Modulation: DISABLED (barebones mode)");
    Serial.println("│ Using fixed SF7, 250kHz BW");
    #endif
    
    Serial.println("└──────────────────────────────────────────────────────────┘");
    
    // ═══════════════════════════════════════════════════════════════
    // BINARY PROTOCOL STATISTICS (Requirement 7.1, 7.2, 7.3, 7.4, 7.5)
    // ═══════════════════════════════════════════════════════════════
    Serial.println("\n┌─ BINARY PROTOCOL STATISTICS ─────────────────────────────┐");
    
    Serial.printf("│ Packets Sent:      %lu\n", binaryStats.packets_sent);
    Serial.printf("│ Packets Received:  %lu\n", binaryStats.packets_received);
    Serial.printf("│ Bytes Sent:        %lu\n", binaryStats.bytes_sent);
    Serial.printf("│ Bytes Received:    %lu\n", binaryStats.bytes_received);
    
    Serial.println("│");
    Serial.println("│ Error Counters:");
    Serial.printf("│   Checksum Errors: %lu\n", binaryStats.checksum_errors);
    Serial.printf("│   Parse Errors:    %lu\n", binaryStats.parse_errors);
    Serial.printf("│   Timeout Errors:  %lu\n", binaryStats.timeout_errors);
    Serial.printf("│   Buffer Overflow: %lu\n", binaryStats.buffer_overflow);
    Serial.printf("│   Unknown Commands:%lu\n", binaryStats.unknown_commands);
    
    // Calculate success rate
    float successRate = binaryStats.getSuccessRate();
    Serial.println("│");
    Serial.printf("│ Success Rate:      %.1f%%", successRate);
    if (successRate >= 99.0f) {
        Serial.print(" ✓ EXCELLENT");
    } else if (successRate >= 95.0f) {
        Serial.print(" ✓ GOOD");
    } else if (successRate >= 90.0f) {
        Serial.print(" ⚠ FAIR");
    } else {
        Serial.print(" ✗ POOR");
    }
    Serial.println();
    
    // Calculate average message sizes
    if (binaryStats.packets_sent > 0) {
        uint32_t avgSent = binaryStats.bytes_sent / binaryStats.packets_sent;
        Serial.printf("│ Avg Msg Size (TX): %lu bytes\n", avgSent);
    }
    if (binaryStats.packets_received > 0) {
        uint32_t avgRecv = binaryStats.bytes_received / binaryStats.packets_received;
        Serial.printf("│ Avg Msg Size (RX): %lu bytes\n", avgRecv);
    }
    
    Serial.println("└──────────────────────────────────────────────────────────┘");
    
    // ═══════════════════════════════════════════════════════════════
    // SYSTEM HEALTH SUMMARY
    // ═══════════════════════════════════════════════════════════════
    Serial.println("\n┌─ SYSTEM HEALTH ──────────────────────────────────────────┐");
    
    // Determine overall health status
    bool linkHealthy = (linkQuality.rssi > RSSI_THRESHOLD && 
                        linkQuality.snr > SNR_THRESHOLD && 
                        packetLoss < PACKET_LOSS_THRESHOLD);
    
    // Check queue health based on total drops across all queues
    uint32_t totalDrops = criticalDrop + telemetryDrop + relayDrop + adaptiveDrop;
    bool queueHealthy = (totalDrops < 10);
    
    bool systemHealthy = linkHealthy && queueHealthy && (jammingDetectCounter == 0);
    
    Serial.printf("│ Overall Status:    ");
    if (systemHealthy) {
        Serial.println("✓ HEALTHY");
    } else if (linkHealthy && !queueHealthy) {
        Serial.println("⚠ DEGRADED (Queue Issues)");
    } else if (!linkHealthy && queueHealthy) {
        Serial.println("⚠ DEGRADED (Link Issues)");
    } else {
        Serial.println("✗ UNHEALTHY");
    }
    
    Serial.printf("│ Link Status:       %s\n", linkHealthy ? "✓ Good" : "⚠ Poor");
    Serial.printf("│ Queue Status:      %s\n", queueHealthy ? "✓ Good" : "⚠ Dropping");
    Serial.printf("│ Secondary Ready:   %s\n", relayStateMachine.secondaryReady ? "✓ Yes" : "✗ No");
    
    Serial.println("└──────────────────────────────────────────────────────────┘");
    
    Serial.println();
}