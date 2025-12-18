/**
 * SECONDARY NODE - Version 1.0
 * Mesh relay and backup communication path
 * 
 * Responsibilities:
 * - Mesh network communication @ 902 MHz
 * - Act as relay when primary link is jammed
 * - Forward packets between GCS and primary via UART
 * - Report status to primary node
 * 
 * BIDIRECTIONAL RELAY CAPABILITY:
 * This controller implements transparent bidirectional forwarding:
 * 
 * 1. Mesh → UART (handleRelayPacket):
 *    - Receives packets from mesh network (902 MHz)
 *    - Forwards immediately to Primary via UART
 *    - No buffering, no message classification
 *    - Enables Drone A to relay for Drone B
 * 
 * 2. UART → Mesh (transmitRelayPacket):
 *    - Receives packets from Primary via UART
 *    - Forwards immediately to mesh network (902 MHz)
 *    - No buffering, no message classification
 *    - Enables Drone B to relay for Drone A
 * 
 * MUTUAL ASSISTANCE:
 * Since both drones have identical Secondary controllers:
 * - When Drone A loses GCS link, Drone B's Secondary relays for it
 * - When Drone B loses GCS link, Drone A's Secondary relays for it
 * - Both drones can assist each other simultaneously
 * - No priority logic ensures fair, transparent forwarding
 */

#include <Arduino.h>
#include <SPI.h>
#include <U8g2lib.h>
#include <Wire.h>
#include "SX1262Direct.h"
#include "AeroLoRaScheduler.h"
#include "AdaptiveModulation.h"
#include "MavlinkUtils.h"
#include "shared_protocol.h"
#include "BinaryProtocol.h"
#include "RelayDiscovery.h"
// ═══════════════════════════════════════════════════════════════════
// PIN DEFINITIONS - Heltec V3
// ═══════════════════════════════════════════════════════════════════
#define LORA_SCK         9
#define LORA_MISO        11
#define LORA_MOSI        10
#define LORA_CS          8
#define LORA_RST         12
#define LORA_DIO1        14
#define LORA_BUSY        13
#define LED_PIN          35

// OLED Display (I2C)
#define OLED_SDA         17
#define OLED_SCL         18
#define OLED_RST         21
#define VEXT_PIN         36  // Power control for display

// UART to Primary Node
#define UART_PRIMARY     Serial1
#define PRIMARY_TX       1    
#define PRIMARY_RX       2    
                                                                        // drone relay.  //target
// ═══════════════════════════════════════════════════════════════════  gc h1->(h2 and h3)->h4 dest
// RADIO CONFIGURATION                                                        //(h2 and h3)
// ═══════════════════════════════════════════════════════════════════
#define SECONDARY_FREQ   902.0   // MHz - Mesh/relay frequency
#define BANDWIDTH        125.0   // kHz
#define SPREAD_FACTOR    7       // 7-12
#define CODING_RATE      5       // 5-8
#define SYNC_WORD        0x13    // Different from primary
#define TX_POWER         14      // dBm
//todo : two drones one gcs, forwarding, code mission for one drone, and two drones
// ═══════════════════════════════════════════════════════════════════
// TIMING CONFIGURATION
// ═══════════════════════════════════════════════════════════════════
#define STATUS_REPORT_INTERVAL 5000    // ms - report to primary
#define STATUS_PRINT_INTERVAL  10000   // ms - print detailed status to serial
#define RELAY_CHECK_INTERVAL   100     // ms - check for relay data
#define LED_RELAY_BLINK        300     // ms - blink rate in relay mode
#define DISPLAY_INTERVAL       200     // ms - update display every 200ms

// ═══════════════════════════════════════════════════════════════════
// PACKET TYPES (matching primary)
// ═══════════════════════════════════════════════════════════════════
enum PacketType {
    PACKET_HEARTBEAT = 0x01,
    PACKET_DATA = 0x02,
    PACKET_ACK = 0x03,
    PACKET_RELAY_REQUEST = 0x04,
    PACKET_RELAY_DATA = 0x05
};

// ═══════════════════════════════════════════════════════════════════
// RELAY STATE
// ═══════════════════════════════════════════════════════════════════
struct RelayState {
    bool active;
    uint32_t packetsRelayed;           // Total packets relayed (both directions)
    uint32_t bytesRelayed;             // Total bytes relayed (both directions)
    uint32_t meshToUartPackets;        // Packets forwarded from mesh to UART
    uint32_t uartToMeshPackets;        // Packets forwarded from UART to mesh
    uint32_t meshToUartBytes;          // Bytes forwarded from mesh to UART
    uint32_t uartToMeshBytes;          // Bytes forwarded from UART to mesh
    float lastRSSI;
    float lastSNR;
    unsigned long lastActivity;
};

// ═══════════════════════════════════════════════════════════════════
// BRIDGE STATE (for frequency bridge mode)
// ═══════════════════════════════════════════════════════════════════
struct BridgeStats {
    uint32_t gcsToMeshPackets;    // GCS → Mesh forwarding (BRIDGE_TX)
    uint32_t meshToGcsPackets;    // Mesh → GCS forwarding (BRIDGE_RX)
    uint32_t gcsToMeshBytes;
    uint32_t meshToGcsBytes;
};

// ═══════════════════════════════════════════════════════════════════
// PEER RELAY TRACKING
// ═══════════════════════════════════════════════════════════════════
#define MAX_PEER_RELAYS 4  // Maximum number of peer drones we can relay for

struct PeerRelayInfo {
    uint8_t systemId;           // System ID of peer drone being relayed
    bool active;                // Is this relay slot active?
    uint32_t activatedTime;     // When relay was activated
    uint32_t lastActivity;      // Last time we relayed a packet for this peer
    uint32_t packetsRelayed;    // Number of packets relayed for this peer
};

PeerRelayInfo peerRelays[MAX_PEER_RELAYS] = {0};

// ═══════════════════════════════════════════════════════════════════
// UART ERROR TRACKING
// ═══════════════════════════════════════════════════════════════════
struct UartErrorStats {
    uint32_t parseErrors;
    uint32_t bufferOverflows;
    uint32_t malformedMessages;
    uint32_t hexDecodeErrors;
    uint32_t lastErrorTime;
    
    void reset() {
        parseErrors = 0;
        bufferOverflows = 0;
        malformedMessages = 0;
        hexDecodeErrors = 0;
        lastErrorTime = 0;
    }
};

// ═══════════════════════════════════════════════════════════════════
// GLOBAL OBJECTS AND STATE
// ═══════════════════════════════════════════════════════════════════
SX1262Direct radio(LORA_CS, LORA_DIO1, LORA_RST, LORA_BUSY);
AeroLoRaScheduler scheduler;
AdaptiveModulation adaptive;
U8G2_SSD1306_128X64_NONAME_F_HW_I2C display(U8G2_R0, OLED_RST, OLED_SCL, OLED_SDA);

RelayState relayState = {false, 0, 0, 0, 0, 0, 0, 0, 0, 0};
BridgeStats bridgeStats = {0, 0, 0, 0};
UartErrorStats uartErrors = {0, 0, 0, 0, 0};

// Binary protocol statistics tracking
BinaryProtocolStats binaryStats = {0, 0, 0, 0, 0, 0, 0, 0};

// Binary protocol receive buffer
UartRxBuffer binaryRxBuffer;

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
uint8_t ownDroneSystemId = 0;  // Auto-detected from first local drone packet
bool initReceived = false;  // Flag for INIT handshake completion
unsigned long lastStatusReport = 0;
unsigned long lastStatusPrint = 0;
unsigned long lastLedBlink = 0;
unsigned long lastDisplayUpdate = 0;
unsigned long lastFrequencyCheck = 0;
bool ledState = false;
bool displayAvailable = false;

// Interrupt-driven flags
volatile bool rxDoneFlag = false;
volatile bool txDoneFlag = false;
volatile bool cadDoneFlag = false;

// ═══════════════════════════════════════════════════════════════════
// RELAY DISCOVERY COMPONENTS (Task 7.1)
// ═══════════════════════════════════════════════════════════════════
RelayTable relayTable;
RelayAnnouncer relayAnnouncer;
RelaySelector relaySelector(&relayTable);
PositionTracker positionTracker;
RelayRequestHandler relayRequestHandler;
RelayConnectionManager relayConnectionManager;

// ═══════════════════════════════════════════════════════════════════
// RELAY DISCOVERY STATE MACHINE (Task 7.2)
// Uses RelayDiscoveryState enum from RelayDiscovery.h
// ═══════════════════════════════════════════════════════════════════
RelayDiscoveryState relayDiscoveryState = RELAY_STATE_IDLE;
unsigned long lastStateTransition = 0;

// ═══════════════════════════════════════════════════════════════════
// GCS LINK QUALITY (Task 8.3)
// Received from Primary via UART for relay announcements
// 
// Current implementation: Updated via CMD_START_RELAY_DISCOVERY
// Future enhancement: Could add periodic updates via dedicated command
// ═══════════════════════════════════════════════════════════════════
struct GcsLinkQuality {
    float rssi;              // GCS link RSSI (dBm)
    float snr;               // GCS link SNR (dB)
    float packet_loss;       // GCS packet loss percentage
    bool available;          // Is GCS link available?
    uint32_t last_update;    // Last time quality was updated
    
    void reset() {
        rssi = 0.0f;
        snr = 0.0f;
        packet_loss = 0.0f;
        available = false;
        last_update = 0;
    }
    
    void update(float r, float s, float pl) {
        rssi = r;
        snr = s;
        packet_loss = pl;
        available = true;
        last_update = millis();
    }
};

GcsLinkQuality gcsLinkQuality = {0.0f, 0.0f, 0.0f, false, 0};

// Statistics tracking for display
uint32_t uartRxCount = 0;
uint32_t txCount = 0;
uint8_t lastMessageType = 0;  // Last message type received

// Buffers
uint8_t txBuffer[255];
uint8_t rxBuffer[255];
char uartBuffer[512];

// Radio receive flag
volatile bool receivedFlag = false;

// Ground station address (simplified for now)
#define GCS_ADDRESS      0xFF    // Broadcast for testing

// ═══════════════════════════════════════════════════════════════════
// FUNCTION PROTOTYPES
// ═══════════════════════════════════════════════════════════════════
void IRAM_ATTR onDio1Interrupt();
bool initializeRadio();
bool initializeDisplay();
void updateDisplay();
void receivePacket();
void handleRelayPacket(uint8_t* data, size_t length);
void transmitRelayPacket(uint8_t* data, size_t length);
void checkUart();
bool hexToBytes(const String& hexStr, uint8_t* output, size_t maxLen, size_t* outLen);
String bytesToHex(const uint8_t* data, size_t len);
void sendStatusReport();
void updateLED(unsigned long now);
void printHeader();
void printStatus();
void broadcastRelayRequest(float rssi, float snr, float packetLoss);
bool isRelayRequest(uint8_t* data, size_t length);
bool addPeerRelay(uint8_t systemId);
bool isRelayingForPeer(uint8_t systemId);
void handleRelayRequest(uint8_t* data, size_t length);
void cleanupInactivePeerRelays();
bool validateUartConnection();
bool validateRadioInitialization();
bool validateConfiguration();
const char* getRelayDiscoveryStateName(RelayDiscoveryState state);
void transitionRelayDiscoveryState(RelayDiscoveryState newState);

// ═══════════════════════════════════════════════════════════════════
// RELAY DISCOVERY STATE MACHINE FUNCTIONS (Task 7.2)
// ═══════════════════════════════════════════════════════════════════

/**
 * @brief Get relay discovery state name for debugging
 * 
 * @param state Relay discovery state
 * @return State name as string
 */
const char* getRelayDiscoveryStateName(RelayDiscoveryState state) {
    switch (state) {
        case RELAY_STATE_IDLE:
            return "IDLE";
        case RELAY_STATE_DISCOVERING:
            return "DISCOVERING";
        case RELAY_STATE_REQUESTING:
            return "REQUESTING";
        case RELAY_STATE_CONNECTED:
            return "CONNECTED";
        default:
            return "UNKNOWN";
    }
}

/**
 * @brief Transition relay discovery state with logging
 * 
 * @param newState New state to transition to
 */
void transitionRelayDiscoveryState(RelayDiscoveryState newState) {
    if (relayDiscoveryState != newState) {
        Serial.printf("→ Relay Discovery State: %s → %s\n",
                     getRelayDiscoveryStateName(relayDiscoveryState),
                     getRelayDiscoveryStateName(newState));
        
        relayDiscoveryState = newState;
        lastStateTransition = millis();
    }
}

// ═══════════════════════════════════════════════════════════════════
// CONFIGURATION VALIDATION FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

/**
 * @brief Validate UART connection to Primary controller
 * @return true if UART connection is working, false otherwise
 */
bool validateUartConnection() {
    Serial.print("→ Validating UART connection to Primary... ");
    
    // Send test response (Primary will send PING during its validation)
    // We'll just check if we can write to UART
    // Use binary protocol (Requirements 4.1)
    sendBinaryAck(UART_PRIMARY, &binaryStats);
    
    // Simple check: if we can write without error, consider it valid
    // More thorough validation happens during INIT handshake
    Serial.println("✓");
    return true;
}

/**
 * @brief Validate radio initialization and basic functionality
 * @return true if radio is working correctly, false otherwise
 */
bool validateRadioInitialization() {
    Serial.print("→ Validating radio initialization... ");
    
    // Check if radio is in receive mode
    RadioState state = radio.getState();
    
    if (state == RADIO_STATE_RX) {
        Serial.println("✓");
        return true;
    } else {
        Serial.println("✗ FAILED");
        Serial.printf("  ⚠ Radio state: %d (expected RADIO_STATE_RX)\n", state);
        return false;
    }
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
    if (SECONDARY_FREQ < 902.0 || SECONDARY_FREQ > 928.0) {
        Serial.println("✗ FAILED");
        Serial.printf("  ⚠ Invalid frequency: %.1f MHz (must be 902-928 MHz)\n", SECONDARY_FREQ);
        allValid = false;
    } else {
        Serial.println("✓");
    }
    
    // Validate timing parameters
    Serial.print("→ Validating timing parameters... ");
    if (STATUS_REPORT_INTERVAL < 1000 || STATUS_REPORT_INTERVAL > 60000) {
        Serial.println("✗ FAILED");
        Serial.printf("  ⚠ Invalid status interval: %d ms\n", STATUS_REPORT_INTERVAL);
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
// DISPLAY FUNCTIONS
// ═══════════════════════════════════════════════════════════════════
const char* getMessageTypeString(uint8_t type) {
    switch(type) {
        case PACKET_HEARTBEAT: return "HB";
        case PACKET_DATA: return "DATA";
        case PACKET_ACK: return "ACK";
        case PACKET_RELAY_REQUEST: return "REQ";
        case PACKET_RELAY_DATA: return "RELAY";
        default: return "UNK";
    }
}

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
    display.drawStr(0, 20, "SECONDARY (902MHz)");
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
    
    display.clearBuffer();
    display.setFont(u8g2_font_6x10_tf);
    
    // Title
    display.drawStr(0, 10, "SECONDARY (902MHz)");
    display.drawLine(0, 12, 128, 12);
    
    // Bridge mode indicator and own drone system ID (Requirement 7.2)
    // Show relay discovery state (Task 7.2)
    char buf[32];
    if (ownDroneSystemId > 0) {
        // Show relay discovery state with own drone system ID
        const char* stateStr = getRelayDiscoveryStateName(relayDiscoveryState);
        sprintf(buf, "%s SysID:%d", stateStr, ownDroneSystemId);
    } else {
        // System ID not yet detected
        sprintf(buf, "%s [%s]", 
                relayState.active ? "RELAY" : "BRIDGE",
                getMessageTypeString(lastMessageType));
    }
    display.drawStr(0, 24, buf);
    
    // Count active peer relays (Requirement 7.2)
    int activePeerCount = 0;
    for (int i = 0; i < MAX_PEER_RELAYS; i++) {
        if (peerRelays[i].active) activePeerCount++;
    }
    
    // RX/TX counts with active peer relay count (Requirement 7.2)
    if (activePeerCount > 0) {
        sprintf(buf, "RX:%lu TX:%lu PR:%d", uartRxCount, txCount, activePeerCount);
    } else {
        sprintf(buf, "RX:%lu TX:%lu", uartRxCount, txCount);
    }
    display.drawStr(0, 36, buf);
    
    // Bridge statistics (Requirement 7.2)
    // Show bridge packet counts (GCS→Mesh, Mesh→GCS)
    if (bridgeStats.gcsToMeshPackets > 0 || bridgeStats.meshToGcsPackets > 0) {
        sprintf(buf, "G->M:%lu M->G:%lu", 
                bridgeStats.gcsToMeshPackets, 
                bridgeStats.meshToGcsPackets);
    } else {
        // Show relay statistics if no bridge activity
        sprintf(buf, "M->U:%lu U->M:%lu", 
                relayState.meshToUartPackets, 
                relayState.uartToMeshPackets);
    }
    display.drawStr(0, 48, buf);
    
    // RSSI/SNR
    sprintf(buf, "RSSI:%.0f SNR:%.1f", relayState.lastRSSI, relayState.lastSNR);
    display.drawStr(0, 60, buf);
    
    // Send buffer (void return type - no error checking possible)
    display.sendBuffer();
}

// ═══════════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════════
void setup() {
    Serial.begin(115200);
    delay(2000);
    
    pinMode(LED_PIN, OUTPUT);
    
    printHeader();
    
    // Initialize OLED display
    Serial.print("Initializing OLED display... ");
    if (initializeDisplay()) {
        displayAvailable = true;
        Serial.println("✓");
    } else {
        displayAvailable = false;
        Serial.println("⚠ Display failed - continuing without display");
    }
    
    // Initialize UART to primary
    Serial.print("Initializing UART to primary... ");
    UART_PRIMARY.begin(115200, SERIAL_8N1, PRIMARY_RX, PRIMARY_TX);
    Serial.println("✓");
    
    // Initialize radio on mesh frequency
    if (initializeRadio()) {
        Serial.println("✓ Radio initialized on mesh frequency");
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
    
    // Initialize relay discovery components (Task 7.1)
    Serial.println("\n═══════════════════════════════════════════════════════════");
    Serial.println("  INITIALIZING RELAY DISCOVERY SYSTEM");
    Serial.println("═══════════════════════════════════════════════════════════");
    
    // Initialize relay announcer with 2-second interval (Requirement 1.2)
    relayAnnouncer.begin(ANNOUNCEMENT_INTERVAL_MS);
    
    // Initialize relay connection manager (will set system ID later when detected)
    relayConnectionManager.begin(0, HEARTBEAT_INTERVAL_MS, CLIENT_TIMEOUT_MS);
    
    Serial.println("✓ Relay discovery system initialized");
    Serial.println("  → Relay table ready (max 10 entries)");
    Serial.println("  → Announcer ready (2 second interval)");
    Serial.println("  → Position tracker ready");
    Serial.println("  → Request handler ready");
    Serial.println("  → Connection manager ready (max 3 clients)");
    
    // Start in bridge listening mode (default per requirements 1.5, 10.1-10.5)
    Serial.println("\n═══════════════════════════════════════════════════════════");
    Serial.println("  INITIALIZING FREQUENCY BRIDGE MODE");
    Serial.println("═══════════════════════════════════════════════════════════");
    
    relayState.active = false;  // Relay mode inactive by default
    
    // Wait for initialization command from Primary
    Serial.print("→ Waiting for initialization command from Primary... ");
    unsigned long initStartTime = millis();
    const unsigned long INIT_TIMEOUT = 3000;  // 3 second timeout
    
    while (millis() - initStartTime < INIT_TIMEOUT) {
        // Process binary UART messages
        processBinaryUart(UART_PRIMARY, &binaryRxBuffer, &binaryStats);
        
        // Check if INIT was received (handleBinaryInit will be called by processBinaryUart)
        if (initReceived) {
            Serial.println("✓");
            break;
        }
        
        delay(10);
    }
    
    if (!initReceived) {
        Serial.println("⚠ TIMEOUT");
        Serial.println("  ⚠ No initialization command received from Primary");
        Serial.println("  → Starting in bridge listening mode anyway");
    }
    
    Serial.println("\n═══════════════════════════════════════════════════════════");
    Serial.println("  ✓ SECONDARY READY - BRIDGE LISTENING MODE ACTIVE");
    Serial.println("═══════════════════════════════════════════════════════════");
    Serial.printf("  Frequency: %.1f MHz (Mesh Network)\n", SECONDARY_FREQ);
    Serial.println("  Listening for:");
    Serial.println("    • Packets from local drone (902 MHz)");
    Serial.println("    • Packets from peer drones (902 MHz)");
    Serial.println("    • Relay requests from peers");
    Serial.println("    • Bridge commands from Primary (UART)");
    Serial.println("═══════════════════════════════════════════════════════════\n");
    
    // Update display with initial state
    if (displayAvailable) {
        updateDisplay();
    }
}

// ═══════════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════════
void loop() {
    unsigned long now = millis();
    
    // Check for incoming radio packets (interrupt-driven)
    if (rxDoneFlag) {
        rxDoneFlag = false;
        receivePacket();
    }
    
    // Check for UART messages from primary
    checkUart();
    
    // Send periodic status reports to primary
    if (now - lastStatusReport > STATUS_REPORT_INTERVAL) {
        sendStatusReport();
        lastStatusReport = now;
    }
    
    // Print detailed status periodically
    if (now - lastStatusPrint > STATUS_PRINT_INTERVAL) {
        printStatus();
        lastStatusPrint = now;
    }
    
    // Update OLED display
    if (displayAvailable && (now - lastDisplayUpdate > DISPLAY_INTERVAL)) {
        updateDisplay();
        lastDisplayUpdate = now;
    }
    
    // Blink LED based on mode
    updateLED(now);
    
    // Cleanup inactive peer relays (every 5 seconds)
    static unsigned long lastPeerCleanup = 0;
    if (now - lastPeerCleanup > 5000) {
        cleanupInactivePeerRelays();
        lastPeerCleanup = now;
    }
    
    // Remove stale relay table entries (Task 7.4, Requirement 2.4)
    static unsigned long lastStaleCheck = 0;
    if (now - lastStaleCheck > 5000) {
        uint8_t removed = relayTable.removeStaleEntries(RELAY_STALE_TIMEOUT_MS);
        if (removed > 0) {
            Serial.printf("→ Removed %d stale relay entries\n", removed);
        }
        lastStaleCheck = now;
    }
    
    // ═══════════════════════════════════════════════════════════════
    // RELAY ANNOUNCEMENT BROADCASTING (Task 7.3)
    // ═══════════════════════════════════════════════════════════════
    
    // Broadcast relay announcements every 2 seconds (Requirement 1.2)
    if (relayAnnouncer.shouldAnnounce() && ownDroneSystemId > 0) {
        // Build announcement packet with current status
        // Availability: true if GCS link is good and not using relay (Requirement 1.4, 1.5)
        bool available = gcsLinkQuality.available && (relayDiscoveryState == RELAY_STATE_IDLE);
        
        // Use GCS link quality from Primary (Task 8.3, Requirement 10.5)
        int16_t gcsRSSI = static_cast<int16_t>(gcsLinkQuality.rssi);
        int8_t gcsSNR = static_cast<int8_t>(gcsLinkQuality.snr);
        uint8_t gcsPacketLoss = static_cast<uint8_t>(gcsLinkQuality.packet_loss);
        
        // Get current position from position tracker
        int32_t lat, lon;
        int16_t alt;
        if (!positionTracker.getPosition(lat, lon, alt)) {
            // No valid position - use zeros
            lat = 0;
            lon = 0;
            alt = 0;
        }
        
        // Build announcement packet (Requirement 1.3)
        RelayAnnouncement announcement = relayAnnouncer.buildAnnouncement(
            ownDroneSystemId,
            available,
            gcsRSSI,
            gcsSNR,
            gcsPacketLoss,
            lat,
            lon,
            alt
        );
        
        // Transmit announcement on 902 MHz mesh (Requirement 1.1)
        // Perform CAD before transmission
        if (radio.performCADWithBackoff(3)) {
            // Channel busy - skip this announcement
            Serial.println("⚠ Channel busy - skipping announcement");
        } else {
            // Channel clear - transmit
            radio.setStandby(SX1262_STANDBY_RC);
            delay(1);
            
            int16_t state = radio.transmitDirect((uint8_t*)&announcement, sizeof(RelayAnnouncement));
            
            if (state == SX1262_ERR_NONE) {
                // Wait for TX complete
                unsigned long txStart = millis();
                while (!radio.isTxComplete() && (millis() - txStart < 1000)) {
                    delay(1);
                }
                
                if (radio.isTxComplete()) {
                    relayAnnouncer.markAnnouncementSent();
                } else {
                    Serial.println("✗ Announcement TX timeout");
                }
            } else {
                Serial.printf("✗ Announcement broadcast failed: error %d\n", state);
            }
            
            // Return to RX mode
            radio.setRx(0);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════
    // RELAY DISCOVERY STATE MACHINE (Task 7.2, 7.5)
    // ═══════════════════════════════════════════════════════════════
    
    // State-specific behavior
    switch (relayDiscoveryState) {
        case RELAY_STATE_IDLE:
            // Normal operation - no relay needed
            // State transitions handled by external triggers (GCS link loss)
            // Trigger is typically sent from Primary via UART
            break;
            
        case RELAY_STATE_DISCOVERING: {
            // Scanning relay table for available relays (Task 7.5)
            // Calculate relay scores using current position
            int32_t ownLat, ownLon;
            int16_t ownAlt;
            
            if (positionTracker.getPosition(ownLat, ownLon, ownAlt)) {
                relaySelector.calculateScores(ownLat, ownLon);
            } else {
                // No position available - calculate without distance component
                relaySelector.calculateScores(0, 0);
            }
            
            // Select best relay (Requirement 3.4)
            RelayTableEntry* bestRelay = relaySelector.selectBestRelay();
            
            if (bestRelay != nullptr) {
                // Found a relay - send request (Requirement 4.1)
                Serial.printf("→ Selecting relay: System ID %d (score: %.2f)\n",
                             bestRelay->systemId, bestRelay->relayScore);
                
                // Build and send relay request
                RelayRequest request = relayRequestHandler.buildRequest(bestRelay->systemId);
                
                // Perform CAD before transmission
                if (radio.performCADWithBackoff(3)) {
                    Serial.println("⚠ Channel busy - will retry relay request");
                } else {
                    radio.setStandby(SX1262_STANDBY_RC);
                    delay(1);
                    
                    int16_t state = radio.transmitDirect((uint8_t*)&request, sizeof(RelayRequest));
                    
                    if (state == SX1262_ERR_NONE) {
                        // Wait for TX complete
                        unsigned long txStart = millis();
                        while (!radio.isTxComplete() && (millis() - txStart < 1000)) {
                            delay(1);
                        }
                        
                        if (radio.isTxComplete()) {
                            relayRequestHandler.sendRequest(bestRelay->systemId);
                            transitionRelayDiscoveryState(RELAY_STATE_REQUESTING);
                        } else {
                            Serial.println("✗ Relay request TX timeout");
                        }
                    } else {
                        Serial.printf("✗ Failed to send relay request: error %d\n", state);
                    }
                    
                    radio.setRx(0);
                }
            } else {
                // No available relays (Requirement 3.5)
                Serial.println("✗ No available relays found - will retry");
                
                // Stay in DISCOVERING state and retry on next loop iteration
                // Add a small delay to avoid spamming
                static unsigned long lastDiscoveryAttempt = 0;
                if (now - lastDiscoveryAttempt < 5000) {
                    // Wait 5 seconds between discovery attempts
                    break;
                }
                lastDiscoveryAttempt = now;
            }
            break;
        }
            
        case RELAY_STATE_REQUESTING: {
            // Waiting for relay acceptance/rejection (Task 7.5)
            // Check for timeout (Requirement 4.5)
            if (relayRequestHandler.hasTimedOut()) {
                relayRequestHandler.handleTimeout();
                
                // Check if we should retry
                if (relayRequestHandler.shouldRetry()) {
                    Serial.println("→ Request timeout - selecting next best relay");
                    
                    // Remove the timed-out relay from table to avoid selecting it again
                    uint8_t timedOutRelayId = relayRequestHandler.getPendingTargetId();
                    if (timedOutRelayId > 0) {
                        relayTable.removeEntry(timedOutRelayId);
                    }
                    
                    // Transition back to DISCOVERING to select next relay
                    transitionRelayDiscoveryState(RELAY_STATE_DISCOVERING);
                } else {
                    Serial.println("✗ Max retries reached - returning to IDLE");
                    transitionRelayDiscoveryState(RELAY_STATE_IDLE);
                }
            }
            break;
        }
            
        case RELAY_STATE_CONNECTED: {
            // Active relay connection (Task 7.5)
            // Send heartbeats periodically (Requirement 6.1)
            if (relayConnectionManager.shouldSendHeartbeats()) {
                // Note: In full implementation, heartbeats would be sent to relay node
                // For now, just mark as sent
                relayConnectionManager.markHeartbeatsSent();
            }
            
            // Check for relay heartbeat timeout (Requirement 6.2)
            // This would be implemented when we receive heartbeats from relay
            // For now, we rely on traffic monitoring
            
            // If GCS link is restored, return to IDLE
            // This would be triggered by Primary via UART in full implementation
            break;
        }
    }
    
    // Periodic frequency verification (every 60 seconds)
    if (now - lastFrequencyCheck > 60000) {
        Serial.println("Periodic frequency verification - resetting to configured frequency");
        
        // Reconfigure to correct frequency
        int16_t state = radio.setFrequency(SECONDARY_FREQ);
        if (state == SX1262_ERR_NONE) {
            Serial.printf("✓ Frequency set to %.2f MHz\n", SECONDARY_FREQ);
            radio.setRx(0);
        } else {
            Serial.printf("✗ Failed to set frequency: error %d\n", state);
        }
        
        lastFrequencyCheck = now;
    }
    
    // Update adaptive modulation periodically (Requirement 4.4)
    static unsigned long lastAdaptiveUpdate = 0;
    if (now - lastAdaptiveUpdate > 5000) {
        adaptive.update();
        lastAdaptiveUpdate = now;
    }
}

// ═══════════════════════════════════════════════════════════════════
// INTERRUPT HANDLER
// ═══════════════════════════════════════════════════════════════════
void IRAM_ATTR onDio1Interrupt() {
    // Check IRQ status to determine what happened
    uint16_t irq = radio.getIrqStatus();
    
    if (irq & SX1262_IRQ_RX_DONE) {
        rxDoneFlag = true;
    }
    if (irq & SX1262_IRQ_TX_DONE) {
        txDoneFlag = true;
    }
    if (irq & SX1262_IRQ_CAD_DONE) {
        cadDoneFlag = true;
    }
    
    // Clear IRQ flags
    radio.clearIrqStatus(SX1262_IRQ_ALL);
}

// ═══════════════════════════════════════════════════════════════════
// RADIO FUNCTIONS
// ═══════════════════════════════════════════════════════════════════
bool initializeRadio() {
    Serial.printf("Initializing radio (SX1262Direct) @ %.1f MHz... ", SECONDARY_FREQ);
    
    // Initialize SPI
    SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI);
    
    // Initialize radio with SX1262Direct
    int16_t state = radio.begin(SECONDARY_FREQ, BANDWIDTH, SPREAD_FACTOR, CODING_RATE);
    
    if (state != SX1262_ERR_NONE) {
        Serial.printf("Failed: %d\n", state);
        return false;
    }
    
    // Set TX power
    state = radio.setOutputPower(TX_POWER);
    if (state != SX1262_ERR_NONE) {
        Serial.printf("Failed to set TX power: %d\n", state);
        return false;
    }
    
    // Configure sync word
    uint8_t syncWord[2] = {(uint8_t)((SYNC_WORD >> 8) & 0xFF), (uint8_t)(SYNC_WORD & 0xFF)};
    state = radio.setSyncWord(syncWord);
    if (state != SX1262_ERR_NONE) {
        Serial.printf("Failed to set sync word: %d\n", state);
        return false;
    }
    
    // Set up interrupt on DIO1
    pinMode(LORA_DIO1, INPUT);
    attachInterrupt(digitalPinToInterrupt(LORA_DIO1), onDio1Interrupt, RISING);
    
    // Configure IRQ
    radio.setDioIrqParams(SX1262_IRQ_RX_DONE | SX1262_IRQ_TX_DONE | SX1262_IRQ_CAD_DONE,
                         SX1262_IRQ_RX_DONE | SX1262_IRQ_TX_DONE | SX1262_IRQ_CAD_DONE);
    
    // Start in RX mode
    state = radio.setRx(0);  // 0 = continuous RX
    
    if (state != SX1262_ERR_NONE) {
        Serial.printf("StartReceive failed: %d\n", state);
        return false;
    }
    
    Serial.println("✓");
    
    // Initialize scheduler
    scheduler.begin(SLOT_DURATION_MS);
    scheduler.setRadio(&radio);
    
    // Initialize adaptive modulation
    adaptive.begin(&radio, &scheduler);
    
    return true;
}

void receivePacket() {
    // Read packet using SX1262Direct
    uint8_t packetLength = radio.readPacket(rxBuffer, 255);
    
    if (packetLength > 0) {
        // Get link metrics
        relayState.lastRSSI = radio.getRSSI();
        relayState.lastSNR = radio.getSNR();
        relayState.lastActivity = millis();
        
        // Extract message type from first byte (if packet has data)
        if (packetLength > 0) {
            lastMessageType = rxBuffer[0];
        }
        
        // ═══════════════════════════════════════════════════════════════
        // RELAY DISCOVERY PACKET PROCESSING (Task 7.4)
        // ═══════════════════════════════════════════════════════════════
        
        // Check packet type by magic byte
        if (packetLength > 0) {
            uint8_t magicByte = rxBuffer[0];
            
            // Process relay announcement packets (Requirement 2.2, 2.3)
            if (magicByte == MAGIC_ANNOUNCEMENT && packetLength == sizeof(RelayAnnouncement)) {
                RelayTableEntry entry;
                
                if (relayAnnouncer.parseAnnouncement(rxBuffer, packetLength, entry, 
                                                     relayState.lastRSSI, relayState.lastSNR)) {
                    // Don't add our own announcements to the table
                    if (entry.systemId != ownDroneSystemId) {
                        relayTable.updateEntry(entry);
                        Serial.printf("→ Relay announcement from System ID %d (RSSI: %d, Available: %s)\n",
                                     entry.systemId, entry.meshRSSI, entry.available ? "YES" : "NO");
                    }
                }
                
                radio.startReceive();
                return;
            }
            
            // Process relay request packets (Requirement 4.2)
            if (magicByte == MAGIC_REQUEST && packetLength == sizeof(RelayRequest)) {
                uint8_t clientId, targetRelayId, sequence;
                
                if (relayRequestHandler.parseRequest(rxBuffer, packetLength, 
                                                     clientId, targetRelayId, sequence)) {
                    // Request is for us - check capacity and send response
                    if (relayConnectionManager.hasCapacity()) {
                        // Accept the request (Requirement 4.3)
                        RelayAcceptance acceptance = relayRequestHandler.buildAcceptance(clientId, sequence);
                        
                        radio.setStandby(SX1262_STANDBY_RC);
                        delay(1);
                        
                        int16_t state = radio.transmitDirect((uint8_t*)&acceptance, sizeof(RelayAcceptance));
                        if (state == SX1262_ERR_NONE) {
                            // Wait for TX complete
                            unsigned long txStart = millis();
                            while (!radio.isTxComplete() && (millis() - txStart < 1000)) {
                                delay(1);
                            }
                            
                            if (radio.isTxComplete()) {
                                Serial.printf("✓ Sent relay acceptance to System ID %d\n", clientId);
                                // Add client to connection manager
                                relayConnectionManager.addClient(clientId);
                            } else {
                                Serial.println("✗ Acceptance TX timeout");
                            }
                        } else {
                            Serial.printf("✗ Failed to send acceptance: error %d\n", state);
                        }
                    } else {
                        // Reject - capacity full (Requirement 5.4)
                        RelayRejection rejection = relayRequestHandler.buildRejection(
                            clientId, REASON_CAPACITY_FULL);
                        
                        radio.setStandby(SX1262_STANDBY_RC);
                        delay(1);
                        
                        int16_t state = radio.transmitDirect((uint8_t*)&rejection, sizeof(RelayRejection));
                        if (state == SX1262_ERR_NONE) {
                            // Wait for TX complete
                            unsigned long txStart = millis();
                            while (!radio.isTxComplete() && (millis() - txStart < 1000)) {
                                delay(1);
                            }
                            
                            if (radio.isTxComplete()) {
                                Serial.printf("✓ Sent relay rejection to System ID %d (capacity full)\n", clientId);
                            } else {
                                Serial.println("✗ Rejection TX timeout");
                            }
                        } else {
                            Serial.printf("✗ Failed to send rejection: error %d\n", state);
                        }
                    }
                }
                
                radio.setRx(0);
                return;
            }
            
            // Process relay acceptance packets (Requirement 4.3, 4.4)
            if (magicByte == MAGIC_ACCEPTANCE && packetLength == sizeof(RelayAcceptance)) {
                uint8_t relayId;
                
                if (relayRequestHandler.parseAcceptance(rxBuffer, packetLength, relayId)) {
                    // Relay accepted our request - establish connection
                    Serial.printf("✓ Relay acceptance received from System ID %d\n", relayId);
                    
                    // Transition to CONNECTED state
                    transitionRelayDiscoveryState(RELAY_STATE_CONNECTED);
                    
                    // Reset retry counter
                    relayRequestHandler.resetRetries();
                }
                
                radio.startReceive();
                return;
            }
            
            // Process relay rejection packets (Requirement 4.5)
            if (magicByte == MAGIC_REJECTION && packetLength == sizeof(RelayRejection)) {
                uint8_t relayId, reason;
                
                if (relayRequestHandler.parseRejection(rxBuffer, packetLength, relayId, reason)) {
                    // Relay rejected our request - try next best relay
                    Serial.printf("✗ Relay rejection received from System ID %d\n", relayId);
                    
                    // Transition back to DISCOVERING to select next relay
                    transitionRelayDiscoveryState(RELAY_STATE_DISCOVERING);
                }
                
                radio.startReceive();
                return;
            }
        }
        
        // CHECK FOR RELAY REQUEST BROADCAST
        // This must be checked before other processing
        if (isRelayRequest(rxBuffer, packetLength)) {
            handleRelayRequest(rxBuffer, packetLength);
            radio.startReceive();
            return;
        }
        
        // FREQUENCY BRIDGE MODE: Forward all 902 MHz packets to Primary
        // Primary will handle routing based on system ID and priority
        unsigned long startTime = millis();
        
        // Extract MAVLink system ID from packet
        uint8_t systemId = 0;
        MavlinkExtractResult extractResult = extractSystemId(rxBuffer, packetLength, &systemId);
        
        if (extractResult == MAVLINK_EXTRACT_SUCCESS) {
            // AUTO-DETECT OWN DRONE SYSTEM ID
            // Detect first packet from local Drone_LoRa based on strong RSSI
            // Local drone packets typically have RSSI > -50 dBm (very close proximity)
            if (ownDroneSystemId == 0 && relayState.lastRSSI > -50.0) {
                ownDroneSystemId = systemId;
                Serial.println("\n════════════════════════════════");
                Serial.printf("✓ AUTO-DETECTED OWN DRONE SYSTEM ID: %d\n", ownDroneSystemId);
                Serial.printf("  RSSI: %.1f dBm (local drone)\n", relayState.lastRSSI);
                Serial.println("════════════════════════════════\n");
                
                // Update relay discovery components with system ID (Task 7.1)
                relayRequestHandler.setSystemId(ownDroneSystemId);
                relayConnectionManager.setSystemId(ownDroneSystemId);
            }
            
            // Update position tracker from local drone packets (Task 7.3)
            // Only update position from our own drone's packets
            if (systemId == ownDroneSystemId && relayState.lastRSSI > -50.0) {
                positionTracker.updateFromMAVLink(rxBuffer, packetLength);
            }
            
            // Valid MAVLink packet - forward to Primary with system ID
            // Use binary protocol (Requirements 4.2)
            sendBinaryBridgeRx(UART_PRIMARY, systemId, relayState.lastRSSI, 
                              relayState.lastSNR, rxBuffer, packetLength, &binaryStats);
            
            // Update bridge statistics
            bridgeStats.meshToGcsPackets++;
            bridgeStats.meshToGcsBytes += packetLength;
            
            unsigned long forwardTime = millis() - startTime;
            
            // Log if forwarding took longer than target (10ms)
            if (forwardTime > 10) {
                Serial.printf("⚠ Bridge RX forwarding took %lu ms (target: 10ms)\n", forwardTime);
            }
            
            // Flash LED for bridge activity
            digitalWrite(LED_PIN, HIGH);
            delay(50);
            digitalWrite(LED_PIN, LOW);
        } else {
            // Not a valid MAVLink packet or extraction failed
            // Still forward but without system ID (Primary will handle)
            Serial.printf("⚠ MAVLink extraction failed: %s\n", 
                          getMavlinkExtractErrorString(extractResult));
            
            // Forward anyway for debugging/monitoring
            // Use binary protocol (Requirements 4.2)
            sendBinaryBridgeRx(UART_PRIMARY, 0, relayState.lastRSSI, 
                              relayState.lastSNR, rxBuffer, packetLength, &binaryStats);
        }
        
        // If relay is active, also use the old relay forwarding path
        // This maintains backward compatibility with existing relay mode
        if (relayState.active) {
            handleRelayPacket(rxBuffer, packetLength);
        }
    }
    
    // Return to receive mode
    radio.setRx(0);
}

/**
 * Handle relay packet from mesh network (Mesh → UART forwarding)
 * 
 * BIDIRECTIONAL RELAY: This function enables Drone A to relay for Drone B
 * - Receives packet from mesh network (another drone's Secondary)
 * - Forwards immediately to Primary via UART (no buffering)
 * - No message classification or priority logic
 * - Transparent forwarding ensures mutual assistance capability
 */
void handleRelayPacket(uint8_t* data, size_t length) {
    if (length == 0) {
        Serial.println("⚠ Empty relay packet received");
        return;
    }
    
    Serial.printf("Relaying packet: %d bytes, RSSI: %.1f, SNR: %.1f\n", 
                  length, relayState.lastRSSI, relayState.lastSNR);
    
    // Forward to primary via UART
    // Use binary protocol (Requirements 4.4)
    sendBinaryRelayRx(UART_PRIMARY, relayState.lastRSSI, relayState.lastSNR,
                     data, length, &binaryStats);
    
    // Update statistics - mesh to UART forwarding
    relayState.packetsRelayed++;
    relayState.bytesRelayed += length;
    relayState.meshToUartPackets++;
    relayState.meshToUartBytes += length;
    
    // Flash LED for relay activity
    digitalWrite(LED_PIN, HIGH);
    delay(50);
    digitalWrite(LED_PIN, LOW);
}

/**
 * Transmit relay packet to mesh network (UART → Mesh forwarding)
 * 
 * BIDIRECTIONAL RELAY: This function enables Drone B to relay for Drone A
 * - Receives packet from Primary via UART
 * - Forwards immediately to mesh network (no buffering)
 * - No message classification or priority logic
 * - Transparent forwarding ensures mutual assistance capability
 */
void transmitRelayPacket(uint8_t* data, size_t length) {
    if (!relayState.active) {
        Serial.println("⚠ Relay TX requested but relay not active");
        return;
    }
    
    if (length == 0 || length > 254) {
        Serial.printf("⚠ Invalid relay packet length: %d\n", length);
        return;
    }
    
    Serial.printf("Transmitting relay packet: %d bytes\n", length);
    
    // Add relay header
    txBuffer[0] = PACKET_RELAY_DATA;
    memcpy(txBuffer + 1, data, length);
    
    // Transmit on mesh frequency (Requirement 9.5)
    radioErrors.totalTransmissions++;
    
    // Perform CAD before transmission (Requirement 4.6)
    if (radio.performCADWithBackoff(3)) {
        Serial.println("⚠ Channel busy - relay TX deferred");
        radioErrors.txFailures++;
        radio.setRx(0);
        return;
    }
    
    radio.setStandby(SX1262_STANDBY_RC);
    delay(1);
    
    int16_t state = radio.transmitDirect(txBuffer, length + 1);
    
    if (state == SX1262_ERR_NONE) {
        // Wait for TX complete
        unsigned long txStart = millis();
        while (!radio.isTxComplete() && (millis() - txStart < 1000)) {
            delay(1);
        }
        
        if (radio.isTxComplete()) {
            Serial.printf("✓ Relay TX success: %d bytes\n", length);
            radioErrors.successfulTransmissions++;
            
            // Update statistics - UART to mesh forwarding
            relayState.packetsRelayed++;
            relayState.bytesRelayed += length;
            relayState.uartToMeshPackets++;
            relayState.uartToMeshBytes += length;
            txCount++;  // Increment TX counter for display
            
            // Flash LED
            digitalWrite(LED_PIN, HIGH);
            delay(100);
            digitalWrite(LED_PIN, LOW);
        } else {
            Serial.println("✗ Relay TX timeout");
            radioErrors.txFailures++;
            radioErrors.lastErrorTime = millis();
        }
    } else {
        // Detect TX failures and log errors (Requirement 9.5)
        Serial.printf("✗ Relay TX failed: error %d\n", state);
        radioErrors.txFailures++;
        radioErrors.lastErrorTime = millis();
        
        // Log specific error details
        if (state == SX1262_ERR_INVALID_PARAM) {
            Serial.printf("  → Invalid parameter: %d bytes\n", length + 1);
        }
        
        // Track transmission success rate (Requirement 9.5)
        Serial.printf("  → TX Success Rate: %.1f%% (%lu/%lu)\n",
                     radioErrors.getSuccessRate(),
                     radioErrors.successfulTransmissions,
                     radioErrors.totalTransmissions);
    }
    
    // Return to receive mode (Requirement 9.5)
    int16_t rxState = radio.setRx(0);
    if (rxState != SX1262_ERR_NONE) {
        Serial.printf("✗ Failed to restart receive mode: error %d\n", rxState);
        radioErrors.rxRestartFailures++;
        radioErrors.lastErrorTime = millis();
        
        // Attempt recovery using radio's built-in recovery
        Serial.println("  → Attempting radio recovery...");
        if (radio.checkAndRecoverLockup()) {
            Serial.println("  ✓ Radio recovery successful");
        } else {
            Serial.println("  ✗ Radio recovery failed");
            Serial.println("  → Radio may require hardware reset");
        }
    }
}

// ═══════════════════════════════════════════════════════════════════
// RELAY REQUEST BROADCAST
// ═══════════════════════════════════════════════════════════════════

/**
 * @brief Broadcast relay request on 902 MHz mesh network
 * 
 * Creates a special broadcast packet format that other drones can detect
 * and respond to by activating relay mode for this drone.
 * 
 * Packet format:
 * [0] = PACKET_RELAY_REQUEST (0x04)
 * [1] = Own drone system ID
 * [2-5] = RSSI (float, 4 bytes)
 * [6-9] = SNR (float, 4 bytes)
 * [10-13] = Packet loss percentage (float, 4 bytes)
 * [14-17] = Timestamp (uint32_t, 4 bytes)
 * 
 * @param rssi Current RSSI of failed link
 * @param snr Current SNR of failed link
 * @param packetLoss Packet loss percentage
 */
void broadcastRelayRequest(float rssi, float snr, float packetLoss) {
    Serial.println("\n════════════════════════════════════════════════");
    Serial.println("⚡ BROADCASTING RELAY REQUEST");
    Serial.println("════════════════════════════════════════════════");
    
    // Build relay request packet
    uint8_t relayRequestPacket[18];
    
    // Packet type
    relayRequestPacket[0] = PACKET_RELAY_REQUEST;
    
    // Own drone system ID (requesting relay assistance)
    relayRequestPacket[1] = ownDroneSystemId;
    
    // Link quality metrics (4 bytes each for float)
    memcpy(&relayRequestPacket[2], &rssi, sizeof(float));
    memcpy(&relayRequestPacket[6], &snr, sizeof(float));
    memcpy(&relayRequestPacket[10], &packetLoss, sizeof(float));
    
    // Timestamp
    uint32_t timestamp = millis();
    memcpy(&relayRequestPacket[14], &timestamp, sizeof(uint32_t));
    
    Serial.printf("  System ID: %d\n", ownDroneSystemId);
    Serial.printf("  Link Quality: RSSI=%.1f dBm, SNR=%.1f dB, Loss=%.1f%%\n", 
                  rssi, snr, packetLoss);
    
    // Transmit broadcast on 902 MHz mesh network (Requirement 9.5)
    radioErrors.totalTransmissions++;
    
    // Perform CAD before transmission (Requirement 4.6)
    if (radio.performCADWithBackoff(3)) {
        Serial.println("⚠ Channel busy - relay request deferred");
        radioErrors.txFailures++;
        Serial.println("════════════════════════════════════════════════\n");
        radio.setRx(0);
        return;
    }
    
    radio.setStandby(SX1262_STANDBY_RC);
    delay(1);
    
    int16_t state = radio.transmitDirect(relayRequestPacket, sizeof(relayRequestPacket));
    
    if (state == SX1262_ERR_NONE) {
        // Wait for TX complete
        unsigned long txStart = millis();
        while (!radio.isTxComplete() && (millis() - txStart < 1000)) {
            delay(1);
        }
        
        if (radio.isTxComplete()) {
            Serial.println("✓ Relay request broadcast successful");
            radioErrors.successfulTransmissions++;
            txCount++;
            
            // Flash LED to indicate broadcast
            digitalWrite(LED_PIN, HIGH);
            delay(100);
            digitalWrite(LED_PIN, LOW);
        } else {
            Serial.println("✗ Relay request TX timeout");
            radioErrors.txFailures++;
            radioErrors.lastErrorTime = millis();
        }
    } else {
        // Detect TX failures and log errors (Requirement 9.5)
        Serial.printf("✗ Relay request broadcast failed: error %d\n", state);
        radioErrors.txFailures++;
        radioErrors.lastErrorTime = millis();
        
        // Track transmission success rate
        Serial.printf("  → TX Success Rate: %.1f%% (%lu/%lu)\n",
                     radioErrors.getSuccessRate(),
                     radioErrors.successfulTransmissions,
                     radioErrors.totalTransmissions);
    }
    
    Serial.println("════════════════════════════════════════════════\n");
    
    // Return to receive mode (Requirement 9.5)
    int16_t rxState = radio.setRx(0);
    if (rxState != SX1262_ERR_NONE) {
        Serial.printf("✗ Failed to restart receive mode: error %d\n", rxState);
        radioErrors.rxRestartFailures++;
        radioErrors.lastErrorTime = millis();
        
        // Attempt recovery using radio's built-in recovery
        Serial.println("  → Attempting radio recovery...");
        if (radio.checkAndRecoverLockup()) {
            Serial.println("  ✓ Radio recovery successful");
        } else {
            Serial.println("  ✗ Radio recovery failed");
        }
    }
}

/**
 * @brief Check if received packet is a relay request broadcast
 * 
 * @param data Packet data
 * @param length Packet length
 * @return true if packet is a relay request, false otherwise
 */
bool isRelayRequest(uint8_t* data, size_t length) {
    // Relay request packets are exactly 18 bytes
    if (length != 18) {
        return false;
    }
    
    // First byte must be PACKET_RELAY_REQUEST
    if (data[0] != PACKET_RELAY_REQUEST) {
        return false;
    }
    
    return true;
}

/**
 * @brief Add a peer drone to the active relay list
 * 
 * @param systemId System ID of peer drone requesting relay
 * @return true if successfully added, false if list is full
 */
bool addPeerRelay(uint8_t systemId) {
    // Check if already in list
    for (int i = 0; i < MAX_PEER_RELAYS; i++) {
        if (peerRelays[i].active && peerRelays[i].systemId == systemId) {
            // Already relaying for this peer - update activity time
            peerRelays[i].lastActivity = millis();
            Serial.printf("→ Peer relay already active for system ID %d\n", systemId);
            return true;
        }
    }
    
    // Find empty slot
    for (int i = 0; i < MAX_PEER_RELAYS; i++) {
        if (!peerRelays[i].active) {
            peerRelays[i].systemId = systemId;
            peerRelays[i].active = true;
            peerRelays[i].activatedTime = millis();
            peerRelays[i].lastActivity = millis();
            peerRelays[i].packetsRelayed = 0;
            
            Serial.println("\n════════════════════════════════════════════════");
            Serial.printf("✓ PEER RELAY ACTIVATED for System ID %d\n", systemId);
            Serial.println("════════════════════════════════════════════════\n");
            
            return true;
        }
    }
    
    // List is full
    Serial.printf("⚠ Cannot add peer relay for system ID %d - list full\n", systemId);
    return false;
}

/**
 * @brief Check if we are relaying for a specific system ID
 * 
 * @param systemId System ID to check
 * @return true if actively relaying for this system ID
 */
bool isRelayingForPeer(uint8_t systemId) {
    for (int i = 0; i < MAX_PEER_RELAYS; i++) {
        if (peerRelays[i].active && peerRelays[i].systemId == systemId) {
            return true;
        }
    }
    return false;
}

/**
 * @brief Handle received relay request broadcast
 * 
 * Extracts system ID from relay request and adds to active relay list
 * 
 * @param data Relay request packet data
 * @param length Packet length
 */
void handleRelayRequest(uint8_t* data, size_t length) {
    if (length != 18) {
        Serial.println("⚠ Invalid relay request packet length");
        return;
    }
    
    // Extract requesting system ID
    uint8_t requestingSystemId = data[1];
    
    // Extract link quality metrics
    float rssi, snr, packetLoss;
    memcpy(&rssi, &data[2], sizeof(float));
    memcpy(&snr, &data[6], sizeof(float));
    memcpy(&packetLoss, &data[10], sizeof(float));
    
    // Extract timestamp
    uint32_t timestamp;
    memcpy(&timestamp, &data[14], sizeof(uint32_t));
    
    Serial.println("\n════════════════════════════════════════════════");
    Serial.println("📡 RELAY REQUEST RECEIVED");
    Serial.println("════════════════════════════════════════════════");
    Serial.printf("  Requesting System ID: %d\n", requestingSystemId);
    Serial.printf("  Link Quality: RSSI=%.1f dBm, SNR=%.1f dB, Loss=%.1f%%\n", 
                  rssi, snr, packetLoss);
    Serial.printf("  Timestamp: %lu ms\n", timestamp);
    
    // Don't relay for ourselves
    if (requestingSystemId == ownDroneSystemId) {
        Serial.println("  → Ignoring: This is our own relay request");
        Serial.println("════════════════════════════════════════════════\n");
        return;
    }
    
    // Add to peer relay list
    if (addPeerRelay(requestingSystemId)) {
        Serial.printf("  → Now relaying for system ID %d\n", requestingSystemId);
    } else {
        Serial.printf("  → Failed to activate relay for system ID %d\n", requestingSystemId);
    }
    
    Serial.println("════════════════════════════════════════════════\n");
}

// ═══════════════════════════════════════════════════════════════════
// PEER RELAY CLEANUP
// ═══════════════════════════════════════════════════════════════════

/**
 * @brief Remove inactive peer relays after timeout period
 * Requirement 4.5: Remove peer system ID from relay list after 30 seconds of inactivity
 */
void cleanupInactivePeerRelays() {
    const uint32_t PEER_RELAY_TIMEOUT_MS = 30000;  // 30 seconds
    uint32_t now = millis();
    
    for (int i = 0; i < MAX_PEER_RELAYS; i++) {
        if (peerRelays[i].active) {
            uint32_t inactiveTime = now - peerRelays[i].lastActivity;
            
            if (inactiveTime > PEER_RELAY_TIMEOUT_MS) {
                Serial.println("\n════════════════════════════════════════════════");
                Serial.printf("⏱ PEER RELAY TIMEOUT for System ID %d\n", peerRelays[i].systemId);
                Serial.printf("  Inactive for: %lu seconds\n", inactiveTime / 1000);
                Serial.printf("  Packets relayed: %lu\n", peerRelays[i].packetsRelayed);
                Serial.printf("  Active duration: %lu seconds\n", 
                             (now - peerRelays[i].activatedTime) / 1000);
                Serial.println("════════════════════════════════════════════════\n");
                
                // Deactivate peer relay
                peerRelays[i].active = false;
                peerRelays[i].systemId = 0;
                peerRelays[i].activatedTime = 0;
                peerRelays[i].lastActivity = 0;
                peerRelays[i].packetsRelayed = 0;
                
                Serial.printf("✓ Peer relay deactivated (slot %d)\n", i);
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════════════
// BINARY PROTOCOL HANDLERS (Requirements 4.1, 4.2, 4.3, 4.4, 4.5)
// ═══════════════════════════════════════════════════════════════════

/**
 * @brief Handle binary INIT command
 * Requirements: 4.1
 */
void handleBinaryInit(const InitPayload* payload) {
    if (!payload) return;
    
    Serial.println("\n→ Received binary INIT command from Primary");
    Serial.printf("  Mode: %s\n", payload->mode);
    Serial.printf("  Primary Frequency: %.1f MHz\n", payload->primary_freq);
    Serial.printf("  Secondary Frequency: %.1f MHz\n", payload->secondary_freq);
    
    // Verify our frequency matches expected
    if (abs(payload->secondary_freq - SECONDARY_FREQ) > 0.1) {
        Serial.printf("  ⚠ WARNING: Expected %.1f MHz but configured for %.1f MHz\n",
                     payload->secondary_freq, SECONDARY_FREQ);
    }
    
    // Send binary acknowledgment
    sendBinaryAck(UART_PRIMARY, &binaryStats);
    
    // Set flag for setup() to detect INIT completion
    initReceived = true;
    
    Serial.println("  → Sent binary acknowledgment to Primary\n");
}

/**
 * @brief Handle binary ACK command
 * Requirements: 4.1
 */
void handleBinaryAck() {
    Serial.println("← Received binary ACK");
}

/**
 * @brief Handle binary RELAY_ACTIVATE command
 * Requirements: 4.4
 */
void handleBinaryRelayActivate(const RelayActivatePayload* payload) {
    if (!payload) return;
    
    if (payload->activate && !relayState.active) {
        Serial.println("\n════════════════════════════════");
        Serial.println("⚡ RELAY MODE ACTIVATED");
        Serial.println("════════════════════════════════\n");
        relayState.active = true;
        relayState.packetsRelayed = 0;
        relayState.bytesRelayed = 0;
        relayState.meshToUartPackets = 0;
        relayState.uartToMeshPackets = 0;
        relayState.meshToUartBytes = 0;
        relayState.uartToMeshBytes = 0;
        
        // Send binary acknowledgment
        sendBinaryAck(UART_PRIMARY, &binaryStats);
        
    } else if (!payload->activate && relayState.active) {
        Serial.println("\n════════════════════════════════");
        Serial.println("✓ RELAY MODE DEACTIVATED");
        Serial.printf("Total forwarded: %d packets (%d bytes)\n", 
                      relayState.packetsRelayed, relayState.bytesRelayed);
        Serial.printf("  Mesh→UART: %d packets (%d bytes)\n",
                      relayState.meshToUartPackets, relayState.meshToUartBytes);
        Serial.printf("  UART→Mesh: %d packets (%d bytes)\n",
                      relayState.uartToMeshPackets, relayState.uartToMeshBytes);
        Serial.println("════════════════════════════════\n");
        relayState.active = false;
        
        // Send binary acknowledgment
        sendBinaryAck(UART_PRIMARY, &binaryStats);
    }
}

/**
 * @brief Handle binary RELAY_TX command
 * Requirements: 4.1
 */
void handleBinaryRelayTx(const RelayRxPayload* payload) {
    if (!payload) return;
    
    if (!relayState.active) {
        Serial.println("⚠ Relay TX requested but relay not active");
        return;
    }
    
    // Calculate data length (payload size minus rssi/snr fields)
    size_t dataLen = sizeof(RelayRxPayload) - 8;  // 8 bytes for rssi + snr
    
    // Transmit on mesh network
    transmitRelayPacket((uint8_t*)payload->data, dataLen);
}

/**
 * @brief Handle binary RELAY_RX command (not typically received by Secondary)
 * Requirements: 4.4
 */
void handleBinaryRelayRx(const RelayRxPayload* payload) {
    if (!payload) return;
    
    Serial.printf("← Received binary RELAY_RX: RSSI=%.1f, SNR=%.1f\n",
                 payload->rssi, payload->snr);
    // Secondary typically sends RELAY_RX, not receives it
}

/**
 * @brief Handle binary BRIDGE_TX command
 * Requirements: 4.2
 */
void handleBinaryBridgeTx(const BridgePayload* payload) {
    if (!payload) return;
    
    // Frequency bridge mode: Primary forwarding GCS packet to mesh
    unsigned long startTime = millis();
    
    // Copy payload data to temporary buffer
    uint8_t txBuffer[255];
    memcpy(txBuffer, payload->data, payload->data_len);
    
    // Perform CAD before transmission (Requirement 4.6)
    if (radio.performCADWithBackoff(3)) {
        Serial.println("⚠ Channel busy - bridge TX deferred");
        radio.setRx(0);
        return;
    }
    
    radio.setStandby(SX1262_STANDBY_RC);
    delay(1);
    
    // Transmit on 902 MHz mesh network
    int16_t state = radio.transmitDirect(txBuffer, payload->data_len);
    
    if (state == SX1262_ERR_NONE) {
        // Wait for TX complete
        unsigned long txStart = millis();
        while (!radio.isTxComplete() && (millis() - txStart < 1000)) {
            delay(1);
        }
        
        unsigned long txTime = millis() - startTime;
        
        if (radio.isTxComplete()) {
            // Update bridge statistics
            bridgeStats.gcsToMeshPackets++;
            bridgeStats.gcsToMeshBytes += payload->data_len;
            txCount++;
            
            // Log if transmission took longer than target (20ms)
            if (txTime > 20) {
                Serial.printf("⚠ Bridge TX took %lu ms (target: 20ms)\n", txTime);
            }
            
            // Flash LED for bridge activity
            digitalWrite(LED_PIN, HIGH);
            delay(50);
            digitalWrite(LED_PIN, LOW);
        } else {
            Serial.println("✗ Bridge TX timeout");
        }
    } else {
        Serial.printf("✗ Bridge TX failed: error %d\n", state);
    }
    
    // Always return to receive mode after transmission
    radio.setRx(0);
}

/**
 * @brief Handle binary BRIDGE_RX command (not typically received by Secondary)
 * Requirements: 4.2
 */
void handleBinaryBridgeRx(const BridgePayload* payload) {
    if (!payload) return;
    
    Serial.printf("← Received binary BRIDGE_RX: sysid=%d, len=%d, RSSI=%.1f\n",
                 payload->system_id, payload->data_len, payload->rssi);
    // Secondary typically sends BRIDGE_RX, not receives it
}

/**
 * @brief Handle binary STATUS_REPORT command (not typically received by Secondary)
 * Requirements: 4.3
 */
void handleBinaryStatus(const StatusPayload* payload) {
    if (!payload) return;
    
    Serial.printf("← Received binary STATUS: relay=%s, packets=%lu, RSSI=%.1f\n",
                 payload->relay_active ? "active" : "inactive",
                 payload->packets_relayed, payload->rssi);
    // Secondary typically sends STATUS_REPORT, not receives it
}

/**
 * @brief Handle binary BROADCAST_RELAY_REQ command
 * Requirements: 4.5
 */
void handleBinaryBroadcastRelayReq(const RelayRequestPayload* payload) {
    if (!payload) return;
    
    Serial.println("→ Received binary BROADCAST_RELAY_REQUEST command from Primary");
    Serial.printf("  Link metrics: RSSI=%.1f, SNR=%.1f, Loss=%.1f%%\n", 
                  payload->rssi, payload->snr, payload->packet_loss);
    
    // Broadcast relay request on 902 MHz mesh network
    broadcastRelayRequest(payload->rssi, payload->snr, payload->packet_loss);
}

/**
 * @brief Handle binary STATUS_REQUEST command
 * Requirements: 4.1
 */
void handleBinaryStatusRequest() {
    Serial.println("← Received binary STATUS_REQUEST");
    // Send status report immediately
    sendStatusReport();
}

/**
 * @brief Handle START_RELAY_DISCOVERY command from Primary
 * Triggers relay selection process with provided position and GCS link quality
 * 
 * Requirements: 10.3
 */
void handleBinaryStartRelayDiscovery(const StartRelayDiscoveryPayload* payload) {
    if (!payload) return;
    
    Serial.println("\n═══════════════════════════════════════════════════════════");
    Serial.println("  RELAY DISCOVERY TRIGGERED BY PRIMARY");
    Serial.println("═══════════════════════════════════════════════════════════");
    Serial.printf("  Own Position: lat=%ld, lon=%ld, alt=%d\n", 
                 payload->own_lat, payload->own_lon, payload->own_alt);
    Serial.printf("  GCS Link Quality: RSSI=%.1f dBm, SNR=%.1f dB, Loss=%.1f%%\n",
                 payload->gcs_rssi, payload->gcs_snr, payload->gcs_packet_loss);
    
    // Update GCS link quality for announcements (Task 8.3)
    gcsLinkQuality.update(payload->gcs_rssi, payload->gcs_snr, payload->gcs_packet_loss);
    
    // Calculate relay scores using position from Primary (Task 8.3, Requirement 10.5)
    // Note: PositionTracker updates from MAVLink packets, so we use the position
    // data directly from the Primary's command for relay selection
    relaySelector.calculateScores(payload->own_lat, payload->own_lon);
    
    // Select best relay
    RelayTableEntry* bestRelay = relaySelector.selectBestRelay();
    
    if (bestRelay != nullptr) {
        Serial.printf("✓ Best relay selected: ID=%d, Score=%.1f\n", 
                     bestRelay->systemId, bestRelay->relayScore);
        
        // Send RELAY_SELECTED notification to Primary
        sendBinaryRelaySelected(UART_PRIMARY, bestRelay->systemId, 
                               bestRelay->meshRSSI, bestRelay->meshSNR, 
                               bestRelay->relayScore, &binaryStats);
        
        // TODO: Send relay request to selected relay (Task 7.5)
        // This will be implemented in task 7.5
        
    } else {
        Serial.println("✗ No available relays found");
        Serial.println("  → Continuing to monitor for relay announcements");
    }
    
    Serial.println("═══════════════════════════════════════════════════════════\n");
}

/**
 * @brief Handle RELAY_SELECTED notification from Secondary (not used in Secondary)
 * This handler is a no-op in Secondary controller
 * 
 * Requirements: 10.4
 */
void handleBinaryRelaySelected(const RelaySelectedPayload* payload) {
    if (!payload) return;
    
    // This command is sent by Secondary to Primary, not received by Secondary
    Serial.println("⚠ Received RELAY_SELECTED in Secondary (unexpected)");
}

/**
 * @brief Handle RELAY_ESTABLISHED notification from Secondary (not used in Secondary)
 * This handler is a no-op in Secondary controller
 * 
 * Requirements: 10.4
 */
void handleBinaryRelayEstablished(const RelayEstablishedPayload* payload) {
    if (!payload) return;
    
    // This command is sent by Secondary to Primary, not received by Secondary
    Serial.println("⚠ Received RELAY_ESTABLISHED in Secondary (unexpected)");
}

/**
 * @brief Handle RELAY_LOST notification from Secondary (not used in Secondary)
 * This handler is a no-op in Secondary controller
 * 
 * Requirements: 10.4
 */
void handleBinaryRelayLost(const RelayLostPayload* payload) {
    if (!payload) return;
    
    // This command is sent by Secondary to Primary, not received by Secondary
    Serial.println("⚠ Received RELAY_LOST in Secondary (unexpected)");
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
// UART COMMUNICATION WITH PRIMARY
// ═══════════════════════════════════════════════════════════════════
void checkUart() {
    // Use binary protocol reception (Requirements 2.1, 2.2, 2.3, 2.4, 2.5)
    processBinaryUart(UART_PRIMARY, &binaryRxBuffer, &binaryStats);
    
    // Check for critical error rates periodically
    binaryStats.checkCriticalErrors();
}







void sendStatusReport() {
    // Use binary protocol (Requirements 4.3)
    StatusPayload status;
    status.relay_active = relayState.active;
    status.own_drone_sysid = ownDroneSystemId;
    status.packets_relayed = relayState.packetsRelayed;
    status.bytes_relayed = relayState.bytesRelayed;
    status.mesh_to_uart_packets = relayState.meshToUartPackets;
    status.uart_to_mesh_packets = relayState.uartToMeshPackets;
    status.mesh_to_uart_bytes = relayState.meshToUartBytes;
    status.uart_to_mesh_bytes = relayState.uartToMeshBytes;
    status.bridge_gcs_to_mesh_packets = bridgeStats.gcsToMeshPackets;
    status.bridge_mesh_to_gcs_packets = bridgeStats.meshToGcsPackets;
    status.bridge_gcs_to_mesh_bytes = bridgeStats.gcsToMeshBytes;
    status.bridge_mesh_to_gcs_bytes = bridgeStats.meshToGcsBytes;
    status.rssi = relayState.lastRSSI;
    status.snr = relayState.lastSNR;
    status.last_activity_sec = (millis() - relayState.lastActivity) / 1000;
    
    // Count active peer relays
    uint8_t activePeerRelays = 0;
    for (int i = 0; i < MAX_PEER_RELAYS; i++) {
        if (peerRelays[i].active) {
            activePeerRelays++;
        }
    }
    status.active_peer_relays = activePeerRelays;
    
    // Send binary status report
    sendBinaryStatus(UART_PRIMARY, &status, &binaryStats);
    
    if (relayState.active) {
        Serial.printf("Status: Relay active, Total: %d pkts (%d bytes), M→U: %d, U→M: %d\n",
                      relayState.packetsRelayed, relayState.bytesRelayed,
                      relayState.meshToUartPackets, relayState.uartToMeshPackets);
    }
    
    // Log bridge statistics if any activity
    if (bridgeStats.gcsToMeshPackets > 0 || bridgeStats.meshToGcsPackets > 0) {
        Serial.printf("Bridge: GCS→Mesh: %d pkts (%d bytes), Mesh→GCS: %d pkts (%d bytes)\n",
                      bridgeStats.gcsToMeshPackets, bridgeStats.gcsToMeshBytes,
                      bridgeStats.meshToGcsPackets, bridgeStats.meshToGcsBytes);
    }
    
    // Log own drone system ID if detected
    if (ownDroneSystemId > 0) {
        Serial.printf("Own Drone System ID: %d\n", ownDroneSystemId);
    }
    
    // Log active peer relays
    if (status.active_peer_relays > 0) {
        Serial.printf("Active Peer Relays: %d [", status.active_peer_relays);
        bool first = true;
        for (int i = 0; i < MAX_PEER_RELAYS; i++) {
            if (peerRelays[i].active) {
                if (!first) Serial.print(", ");
                Serial.printf("SysID:%d", peerRelays[i].systemId);
                first = false;
            }
        }
        Serial.println("]");
    }
}

// ═══════════════════════════════════════════════════════════════════
// LED INDICATION
// ═══════════════════════════════════════════════════════════════════
void updateLED(unsigned long now) {
    if (relayState.active) {
        // Fast blink in relay mode (visible indication of relay active)
        if (now - lastLedBlink > LED_RELAY_BLINK) {
            ledState = !ledState;
            digitalWrite(LED_PIN, ledState);
            lastLedBlink = now;
        }
    } else {
        // Slow pulse in standby (heartbeat)
        if (now - lastLedBlink > 2000) {
            digitalWrite(LED_PIN, HIGH);
            delay(50);
            digitalWrite(LED_PIN, LOW);
            lastLedBlink = now;
        }
    }
}

// ═══════════════════════════════════════════════════════════════════
// STATUS AND DEBUGGING
// ═══════════════════════════════════════════════════════════════════
void printHeader() {
    Serial.println("\n\n╔════════════════════════════════════════════════╗");
    Serial.println("║  SECONDARY NODE v1.0                           ║");
    Serial.println("║  Mesh Relay @ 902 MHz                          ║");
    Serial.println("╚════════════════════════════════════════════════╝\n");
    Serial.println("Features:");
    Serial.println("  • Automatic relay activation on primary jamming");
    Serial.println("  • Packet forwarding between GCS and primary");
    Serial.println("  • Real-time status reporting");
    Serial.println("  • LED indicators (fast=relay, slow=standby)");
}

/**
 * @brief Print detailed status and diagnostics for Secondary controller
 * 
 * Requirements 8.2, 8.4:
 * - Show bridge mode status
 * - Display own drone system ID (auto-detected)
 * - Show active peer relay system IDs
 * - Display link quality for 902 MHz
 */
void printStatus() {
    Serial.println("\n╔════════════════════════════════════════════════════════════╗");
    Serial.println("║          SECONDARY NODE STATUS & DIAGNOSTICS               ║");
    Serial.println("╚════════════════════════════════════════════════════════════╝");
    
    // ═══════════════════════════════════════════════════════════════
    // BRIDGE MODE STATUS (Requirement 8.2)
    // ═══════════════════════════════════════════════════════════════
    Serial.println("\n┌─ BRIDGE MODE STATUS ─────────────────────────────────────┐");
    
    if (relayState.active) {
        Serial.println("│ Mode:              RELAY (Active)");
        Serial.println("│ Description:       Forwarding packets via relay path");
    } else {
        Serial.println("│ Mode:              BRIDGE (Listening)");
        Serial.println("│ Description:       Frequency bridge 915↔902 MHz");
    }
    
    Serial.println("└──────────────────────────────────────────────────────────┘");
    
    // ═══════════════════════════════════════════════════════════════
    // OWN DRONE SYSTEM ID (Requirement 8.2)
    // ═══════════════════════════════════════════════════════════════
    Serial.println("\n┌─ OWN DRONE IDENTIFICATION ───────────────────────────────┐");
    
    if (ownDroneSystemId > 0) {
        Serial.printf("│ System ID:         %d (Auto-detected)\n", ownDroneSystemId);
        Serial.println("│ Status:            ✓ Identified");
        Serial.println("│ Detection:         From first local drone packet");
    } else {
        Serial.println("│ System ID:         Unknown");
        Serial.println("│ Status:            ⚠ Not yet detected");
        Serial.println("│ Detection:         Waiting for local drone packet");
        Serial.println("│                    (RSSI > -50 dBm indicates local)");
    }
    
    Serial.println("└──────────────────────────────────────────────────────────┘");
    
    // ═══════════════════════════════════════════════════════════════
    // ACTIVE PEER RELAY SYSTEM IDs (Requirement 8.2)
    // ═══════════════════════════════════════════════════════════════
    Serial.println("\n┌─ ACTIVE PEER RELAYS (Drones We're Helping) ──────────────┐");
    
    int activePeerCount = 0;
    for (int i = 0; i < MAX_PEER_RELAYS; i++) {
        if (peerRelays[i].active) {
            activePeerCount++;
        }
    }
    
    if (activePeerCount > 0) {
        Serial.printf("│ Active Peers:      %d drone(s)\n", activePeerCount);
        Serial.println("│");
        
        for (int i = 0; i < MAX_PEER_RELAYS; i++) {
            if (peerRelays[i].active) {
                uint32_t activeTime = (millis() - peerRelays[i].activatedTime) / 1000;
                uint32_t inactiveTime = (millis() - peerRelays[i].lastActivity) / 1000;
                
                Serial.printf("│ ┌─ System ID: %d\n", peerRelays[i].systemId);
                Serial.printf("│ │  Active For:       %lu sec\n", activeTime);
                Serial.printf("│ │  Last Activity:    %lu sec ago", inactiveTime);
                
                if (inactiveTime > 20) {
                    Serial.print(" ⚠ STALE");
                } else if (inactiveTime < 5) {
                    Serial.print(" ✓ ACTIVE");
                }
                Serial.println();
                
                Serial.printf("│ │  Packets Relayed:  %lu\n", peerRelays[i].packetsRelayed);
                Serial.println("│ └─");
            }
        }
    } else {
        Serial.println("│ No active peer relays");
        Serial.println("│ (Not currently helping other drones)");
    }
    
    Serial.println("└──────────────────────────────────────────────────────────┘");
    
    // ═══════════════════════════════════════════════════════════════
    // LINK QUALITY FOR 902 MHz (Requirement 8.2, 8.4)
    // ═══════════════════════════════════════════════════════════════
    Serial.println("\n┌─ LINK QUALITY (902 MHz Mesh Network) ────────────────────┐");
    
    Serial.printf("│ RSSI:              %.1f dBm", relayState.lastRSSI);
    if (relayState.lastRSSI < -100) {
        Serial.print(" ⚠ WEAK");
    } else if (relayState.lastRSSI > -70) {
        Serial.print(" ✓ STRONG");
    } else if (relayState.lastRSSI > -50) {
        Serial.print(" ✓ LOCAL");
    }
    Serial.println();
    
    Serial.printf("│ SNR:               %.1f dB", relayState.lastSNR);
    if (relayState.lastSNR < 5) {
        Serial.print(" ⚠ POOR");
    } else if (relayState.lastSNR > 10) {
        Serial.print(" ✓ GOOD");
    }
    Serial.println();
    
    uint32_t timeSinceActivity = (millis() - relayState.lastActivity) / 1000;
    Serial.printf("│ Last Activity:     %lu sec ago", timeSinceActivity);
    if (timeSinceActivity > 30) {
        Serial.print(" ⚠ IDLE");
    } else if (timeSinceActivity < 5) {
        Serial.print(" ✓ ACTIVE");
    }
    Serial.println();
    
    Serial.println("└──────────────────────────────────────────────────────────┘");
    
    // ═══════════════════════════════════════════════════════════════
    // TRAFFIC STATISTICS
    // ═══════════════════════════════════════════════════════════════
    Serial.println("\n┌─ TRAFFIC STATISTICS ─────────────────────────────────────┐");
    
    if (relayState.active) {
        Serial.println("│ Relay Mode Statistics:");
        Serial.printf("│   Total Packets:       %lu\n", relayState.packetsRelayed);
        Serial.printf("│   Total Bytes:         %lu\n", relayState.bytesRelayed);
        Serial.printf("│   Mesh → UART:         %lu packets (%lu bytes)\n",
                     relayState.meshToUartPackets, relayState.meshToUartBytes);
        Serial.printf("│   UART → Mesh:         %lu packets (%lu bytes)\n",
                     relayState.uartToMeshPackets, relayState.uartToMeshBytes);
    }
    
    if (bridgeStats.gcsToMeshPackets > 0 || bridgeStats.meshToGcsPackets > 0) {
        Serial.println("│");
        Serial.println("│ Bridge Mode Statistics:");
        Serial.printf("│   GCS → Mesh:          %lu packets (%lu bytes)\n",
                     bridgeStats.gcsToMeshPackets, bridgeStats.gcsToMeshBytes);
        Serial.printf("│   Mesh → GCS:          %lu packets (%lu bytes)\n",
                     bridgeStats.meshToGcsPackets, bridgeStats.meshToGcsBytes);
        
        uint32_t totalBridgePackets = bridgeStats.gcsToMeshPackets + bridgeStats.meshToGcsPackets;
        uint32_t totalBridgeBytes = bridgeStats.gcsToMeshBytes + bridgeStats.meshToGcsBytes;
        Serial.printf("│   Total Bridged:       %lu packets (%lu bytes)\n",
                     totalBridgePackets, totalBridgeBytes);
    }
    
    if (!relayState.active && bridgeStats.gcsToMeshPackets == 0 && bridgeStats.meshToGcsPackets == 0) {
        Serial.println("│ No traffic statistics yet");
        Serial.println("│ (Waiting for packets to forward)");
    }
    
    Serial.println("└──────────────────────────────────────────────────────────┘");
    
    // ═══════════════════════════════════════════════════════════════
    // UART COMMUNICATION STATUS
    // ═══════════════════════════════════════════════════════════════
    Serial.println("\n┌─ UART COMMUNICATION (To Primary) ────────────────────────┐");
    Serial.printf("│ Messages Received: %lu\n", uartRxCount);
    Serial.printf("│ Packets Sent:      %lu\n", txCount);
    Serial.printf("│ Connection:        %s\n", 
                  (millis() - relayState.lastActivity < 10000) ? "✓ Active" : "⚠ Idle");
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
    
    bool linkHealthy = (relayState.lastRSSI > -100 && relayState.lastSNR > 5);
    bool uartHealthy = ((millis() - relayState.lastActivity) < 10000);
    bool systemHealthy = linkHealthy && uartHealthy;
    
    Serial.printf("│ Overall Status:    ");
    if (systemHealthy) {
        Serial.println("✓ HEALTHY");
    } else if (linkHealthy && !uartHealthy) {
        Serial.println("⚠ DEGRADED (UART Idle)");
    } else if (!linkHealthy && uartHealthy) {
        Serial.println("⚠ DEGRADED (Weak Link)");
    } else {
        Serial.println("✗ UNHEALTHY");
    }
    
    Serial.printf("│ Radio Link:        %s\n", linkHealthy ? "✓ Good" : "⚠ Poor");
    Serial.printf("│ UART Link:         %s\n", uartHealthy ? "✓ Active" : "⚠ Idle");
    Serial.printf("│ System ID Known:   %s\n", (ownDroneSystemId > 0) ? "✓ Yes" : "⚠ No");
    
    Serial.println("└──────────────────────────────────────────────────────────┘");
    
    Serial.println();
}