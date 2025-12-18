/**
 * PRIMARY NODE - Version 1.0
 * Full coordination and switching logic
 * * Responsibilities:
 * - Direct link to GCS @ 915 MHz
 * - Monitor link quality (RSSI, SNR, packet loss)
 * - Coordinate with secondary for relay mode
 * - Automatic failover when jamming detected
 */

#include <Arduino.h>
#include <RadioLib.h>
#include <ArduinoJson.h>

// ═══════════════════════════════════════════════════════════════════
// PIN DEFINITIONS - Heltec V3
// ═══════════════════════════════════════════════════════════════════
#define LORA_SCK         9
#define LORA_MISO        11
#define LORA_MOSI        10
#define LORA_CS          8
#define LORA_RST         12
#define LORA_BUSY        13
#define LORA_DIO1        14
#define LED_PIN          35

// UART to Secondary Node
#define UART_SECONDARY   Serial1
#define SECONDARY_TX     1   
#define SECONDARY_RX     2    

// ═══════════════════════════════════════════════════════════════════
// RADIO CONFIGURATION
// ═══════════════════════════════════════════════════════════════════
#define PRIMARY_FREQ     915.0   // MHz - Direct GCS link
#define BANDWIDTH        125.0   // kHz
#define SPREAD_FACTOR    7       // 7-12
#define CODING_RATE      5       // 5-8
#define SYNC_WORD        0x12    // Private network
#define TX_POWER         14      // dBm

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
    MODE_DIRECT,       // Normal: GCS <-> Primary
    MODE_RELAY,        // Jammed: GCS <-> Secondary <-> Primary
    MODE_SWITCHING     // Transitioning between modes
};

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
// GLOBAL OBJECTS AND STATE
// ═══════════════════════════════════════════════════════════════════
SX1262 radio = new Module(LORA_CS, LORA_DIO1, LORA_RST, LORA_BUSY);

SystemMode currentMode = MODE_DIRECT;
LinkQuality linkQuality;
uint32_t sequenceNumber = 0;
uint32_t jammingDetectCounter = 0;

// Timing
unsigned long lastHeartbeat = 0;
unsigned long lastStatusPrint = 0;
unsigned long modeSwitchStartTime = 0;

// Buffers
uint8_t txBuffer[255];
uint8_t rxBuffer[255];
char uartBuffer[512];

// Radio receive flag
volatile bool receivedFlag = false;

// ═══════════════════════════════════════════════════════════════════
// FUNCTION PROTOTYPES
// ═══════════════════════════════════════════════════════════════════
void setFlag(void);
bool initializeRadio();
void receivePacket();
void sendPacket(uint8_t* data, size_t length);
void sendHeartbeat();
void processPacket(uint8_t* data, size_t length);
void checkUart();
void processUartMessage(String message);
void sendUartCommand(String command, String payload);
void forwardToSecondary(uint8_t* data, size_t length);
void evaluateLinkQuality();
void switchToRelayMode();
void switchToDirectMode();
void printHeader();
void printStatus();

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
    
    // Initialize radio
    if (initializeRadio()) {
        Serial.println("✓ Radio initialized");
    } else {
        Serial.println("✗ Radio failed - check hardware!");
        while(1) { delay(1000); }
    }
    
    // Initialize secondary node
    sendUartCommand("INIT", String(PRIMARY_FREQ));
    delay(500);
    
    // Start in direct mode
    currentMode = MODE_DIRECT;
    linkQuality.reset();
    
    Serial.println("\n✓ PRIMARY READY - Direct Mode Active\n");
}

// ═══════════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════════
void loop() {
    unsigned long now = millis();
    
    // Check for incoming radio packets
    if (receivedFlag) {
        receivedFlag = false;
        receivePacket();
    }
    
    // Check for UART messages from secondary
    checkUart();
    
    // Send periodic heartbeats to monitor link
    if (now - lastHeartbeat > HEARTBEAT_INTERVAL) {
        sendHeartbeat();
        lastHeartbeat = now;
    }
    
    // Evaluate link quality and switch modes if needed
    evaluateLinkQuality();
    
    // Print status periodically
    if (now - lastStatusPrint > STATUS_INTERVAL) {
        printStatus();
        lastStatusPrint = now;
    }
}

// ═══════════════════════════════════════════════════════════════════
// RADIO FUNCTIONS
// ═══════════════════════════════════════════════════════════════════
bool initializeRadio() {
    Serial.printf("Initializing radio @ %.1f MHz... ", PRIMARY_FREQ);
    
    int state = radio.begin(PRIMARY_FREQ, BANDWIDTH, SPREAD_FACTOR,
                            CODING_RATE, SYNC_WORD, TX_POWER);
    
    if (state != RADIOLIB_ERR_NONE) {
        Serial.printf("Failed: %d\n", state);
        return false;
    }
    
    // Set radio parameters
    radio.setDio1Action(setFlag);
    state = radio.startReceive();
    
    if (state != RADIOLIB_ERR_NONE) {
        Serial.printf("StartReceive failed: %d\n", state);
        return false;
    }
    
    return true;
}

void setFlag(void) {
    receivedFlag = true;
}

void receivePacket() {
    int state = radio.readData(rxBuffer, 255);
    
    if (state == RADIOLIB_ERR_NONE) {
        int packetLength = radio.getPacketLength();
        
        // Get link metrics
        linkQuality.rssi = radio.getRSSI();
        linkQuality.snr = radio.getSNR();
        linkQuality.packetsReceived++;
        linkQuality.consecutiveLost = 0;
        
        // Process packet based on type
        processPacket(rxBuffer, packetLength);
        
        // Flash LED
        digitalWrite(LED_PIN, HIGH);
        delay(20);
        digitalWrite(LED_PIN, LOW);
    }
    
    // Restart receive
    radio.startReceive();
}

void sendPacket(uint8_t* data, size_t length) {
    // In relay mode, forward through secondary
    if (currentMode == MODE_RELAY) {
        forwardToSecondary(data, length);
        return;
    }
    
    // Direct mode - transmit on radio
    radio.transmit(data, length);
    digitalWrite(LED_PIN, HIGH);
    delay(50);
    digitalWrite(LED_PIN, LOW);
    radio.startReceive();
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
// PACKET PROCESSING
// ═══════════════════════════════════════════════════════════════════
void processPacket(uint8_t* data, size_t length) {
    if (length < 1) return;
    
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
// UART COMMUNICATION WITH SECONDARY
// ═══════════════════════════════════════════════════════════════════
void checkUart() {
    if (UART_SECONDARY.available()) {
        String message = UART_SECONDARY.readStringUntil('\n');
        processUartMessage(message);
    }
}

void processUartMessage(String message) {
    // Parse JSON command from secondary
    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, message);
    
    if (error) {
        Serial.printf("UART parse error: %s\n", error.c_str());
        return;
    }
    
    String cmd = doc["cmd"];
    
    if (cmd == "STATUS") {
        // Secondary reporting its status
        bool relayActive = doc["relay"];
        float relayRSSI = doc["rssi"];
        Serial.printf("Secondary status - Relay: %s, RSSI: %.1f\n", 
                      relayActive ? "Active" : "Standby", relayRSSI);
                      
    } else if (cmd == "RELAY_RX") {
        // Secondary received data via relay path
        size_t dataLen = doc["len"];
        Serial.printf("Secondary relayed %d bytes\n", dataLen);
        
        // In relay mode, this is data from GCS via secondary
        if (currentMode == MODE_RELAY) {
            linkQuality.packetsReceived++;
            linkQuality.rssi = doc["rssi"];
            linkQuality.snr = doc["snr"];
            linkQuality.consecutiveLost = 0;
        }
        
    } else if (cmd == "RELAY_ACK") {
        // Secondary acknowledged relay request
        Serial.println("Secondary ready for relay mode");
    }
}

void sendUartCommand(String command, String payload) {
    StaticJsonDocument<256> doc;
    doc["cmd"] = command;
    doc["payload"] = payload;
    doc["ts"] = millis();
    
    String output;
    serializeJson(doc, output);
    UART_SECONDARY.println(output);
}

void forwardToSecondary(uint8_t* data, size_t length) {
    // Send data to secondary for relay transmission
    StaticJsonDocument<512> doc;
    doc["cmd"] = "RELAY_TX";
    doc["len"] = length;
    
    // Convert data to hex string for JSON transport
    String hexData = "";
    for (size_t i = 0; i < length; i++) {
        char hex[3];
        sprintf(hex, "%02X", data[i]);
        hexData += hex;
    }
    doc["data"] = hexData;
    
    String output;
    serializeJson(doc, output);
    UART_SECONDARY.println(output);
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
        if (jammingDetectCounter >= JAMMING_DETECT_COUNT && currentMode == MODE_DIRECT) {
            Serial.println("\n⚠️  JAMMING DETECTED - Switching to relay mode");
            switchToRelayMode();
        }
    } else {
        jammingDetectCounter = 0;
        
        // If in relay mode and signal recovered, switch back
        if (currentMode == MODE_RELAY && linkQuality.rssi > RSSI_THRESHOLD + 10) {
            Serial.println("\n✓ Signal recovered - Switching to direct mode");
            switchToDirectMode();
        }
    }
}

void switchToRelayMode() {
    currentMode = MODE_SWITCHING;
    
    // Notify secondary to activate relay
    sendUartCommand("ACTIVATE_RELAY", "true");
    
    // Wait for acknowledgment
    unsigned long timeout = millis() + 1000;
    while (millis() < timeout) {
        checkUart();
        delay(10);
    }
    
    currentMode = MODE_RELAY;
    linkQuality.reset();
    
    Serial.println("✓ Relay mode active");
}

void switchToDirectMode() {
    currentMode = MODE_SWITCHING;
    
    // Notify secondary to deactivate relay
    sendUartCommand("ACTIVATE_RELAY", "false");
    
    // Reconfigure radio for direct mode
    radio.setFrequency(PRIMARY_FREQ);
    radio.startReceive();
    
    currentMode = MODE_DIRECT;
    linkQuality.reset();
    
    Serial.println("✓ Direct mode active");
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
    Serial.println("\n--- Status Update ---");
    Serial.printf("Mode: %s\n", 
                  currentMode == MODE_DIRECT ? "DIRECT" : 
                  currentMode == MODE_RELAY ? "RELAY" : "SWITCHING");
    Serial.printf("Link Quality - RSSI: %.1f dBm, SNR: %.1f dB\n", 
                  linkQuality.rssi, linkQuality.snr);
    Serial.printf("Packets: %d/%d (%.1f%% loss)\n",
                  linkQuality.packetsReceived,
                  linkQuality.packetsExpected,
                  linkQuality.getPacketLossPercent());
    Serial.printf("Consecutive Lost: %d\n", linkQuality.consecutiveLost);
    Serial.printf("Jamming Counter: %d/%d\n", 
                  jammingDetectCounter, JAMMING_DETECT_COUNT);
}