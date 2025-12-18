/**
 * SECONDARY NODE - Version 1.0
 * Mesh relay and backup communication path
 * * Responsibilities:
 * - Mesh network communication @ 902 MHz
 * - Act as relay when primary link is jammed
 * - Forward packets between GCS and primary via UART
 * - Report status to primary node
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
#define LORA_DIO1        14
#define LED_PIN          35

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
#define RELAY_CHECK_INTERVAL   100     // ms - check for relay data
#define LED_RELAY_BLINK        300     // ms - blink rate in relay mode

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
    uint32_t packetsRelayed;
    uint32_t bytesRelayed;
    float lastRSSI;
    float lastSNR;
    unsigned long lastActivity;
};

// ═══════════════════════════════════════════════════════════════════
// GLOBAL OBJECTS AND STATE
// ═══════════════════════════════════════════════════════════════════
SX1262 radio = new Module(LORA_CS, LORA_DIO1, LORA_RST, LORA_DIO1);

RelayState relayState = {false, 0, 0, 0, 0, 0};
unsigned long lastStatusReport = 0;
unsigned long lastLedBlink = 0;
bool ledState = false;

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
void setFlag(void);
bool initializeRadio();
void receivePacket();
void handleRelayPacket(uint8_t* data, size_t length);
void transmitRelayPacket(uint8_t* data, size_t length);
void checkUart();
void processUartMessage(String message);
void sendUartResponse(String command, String payload);
void sendStatusReport();
void updateLED(unsigned long now);
void printHeader();

// ═══════════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════════
void setup() {
    Serial.begin(115200);
    delay(2000);
    
    pinMode(LED_PIN, OUTPUT);
    
    printHeader();
    
    // Initialize UART to primary
    Serial.print("Initializing UART to primary... ");
    UART_PRIMARY.begin(115200, SERIAL_8N1, PRIMARY_RX, PRIMARY_TX);
    Serial.println("✓");
    
    // Initialize radio on mesh frequency
    if (initializeRadio()) {
        Serial.println("✓ Radio initialized on mesh frequency");
    } else {
        Serial.println("✗ Radio failed - check hardware!");
        while(1) { delay(1000); }
    }
    
    // Start in standby mode
    relayState.active = false;
    
    Serial.println("\n✓ SECONDARY READY - Standby Mode\n");
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
    
    // Check for UART messages from primary
    checkUart();
    
    // Send periodic status reports to primary
    if (now - lastStatusReport > STATUS_REPORT_INTERVAL) {
        sendStatusReport();
        lastStatusReport = now;
    }
    
    // Blink LED based on mode
    updateLED(now);
}

// ═══════════════════════════════════════════════════════════════════
// RADIO FUNCTIONS
// ═══════════════════════════════════════════════════════════════════
bool initializeRadio() {
    Serial.printf("Initializing radio @ %.1f MHz... ", SECONDARY_FREQ);
    
    int state = radio.begin(SECONDARY_FREQ, BANDWIDTH, SPREAD_FACTOR,
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
        relayState.lastRSSI = radio.getRSSI();
        relayState.lastSNR = radio.getSNR();
        relayState.lastActivity = millis();
        
        // If relay is active, forward to primary
        if (relayState.active) {
            handleRelayPacket(rxBuffer, packetLength);
        } else {
            // In standby, just monitor mesh traffic
            Serial.printf("Mesh traffic detected: %d bytes, RSSI: %.1f\n", 
                          packetLength, relayState.lastRSSI);
        }
    }
    
    // Restart receive
    radio.startReceive();
}

void handleRelayPacket(uint8_t* data, size_t length) {
    Serial.printf("Relaying packet: %d bytes, RSSI: %.1f, SNR: %.1f\n", 
                  length, relayState.lastRSSI, relayState.lastSNR);
    
    // Forward to primary via UART
    StaticJsonDocument<512> doc;
    doc["cmd"] = "RELAY_RX";
    doc["len"] = length;
    doc["rssi"] = relayState.lastRSSI;
    doc["snr"] = relayState.lastSNR;
    
    // Convert data to hex string
    String hexData = "";
    for (size_t i = 0; i < length; i++) {
        char hex[3];
        sprintf(hex, "%02X", data[i]);
        hexData += hex;
    }
    doc["data"] = hexData;
    
    String output;
    serializeJson(doc, output);
    UART_PRIMARY.println(output);
    
    // Update statistics
    relayState.packetsRelayed++;
    relayState.bytesRelayed += length;
    
    // Flash LED for relay activity
    digitalWrite(LED_PIN, HIGH);
    delay(50);
    digitalWrite(LED_PIN, LOW);
}

void transmitRelayPacket(uint8_t* data, size_t length) {
    if (!relayState.active) {
        Serial.println("Warning: Relay TX requested but relay not active");
        return;
    }
    
    Serial.printf("Transmitting relay packet: %d bytes\n", length);
    
    // Add relay header
    txBuffer[0] = PACKET_RELAY_DATA;
    memcpy(txBuffer + 1, data, length);
    
    // Transmit on mesh frequency
    int state = radio.transmit(txBuffer, length + 1);
    
    if (state == RADIOLIB_ERR_NONE) {
        Serial.printf("Relay TX success: %d bytes\n", length);
        relayState.packetsRelayed++;
        relayState.bytesRelayed += length;
        
        // Flash LED
        digitalWrite(LED_PIN, HIGH);
        delay(100);
        digitalWrite(LED_PIN, LOW);
    } else {
        Serial.printf("Relay TX failed: %d\n", state);
    }
    
    // Back to receive mode
    radio.startReceive();
}

// ═══════════════════════════════════════════════════════════════════
// UART COMMUNICATION WITH PRIMARY
// ═══════════════════════════════════════════════════════════════════
void checkUart() {
    if (UART_PRIMARY.available()) {
        String message = UART_PRIMARY.readStringUntil('\n');
        processUartMessage(message);
    }
}

void processUartMessage(String message) {
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, message);
    
    if (error) {
        Serial.printf("UART parse error: %s\n", error.c_str());
        return;
    }
    
    String cmd = doc["cmd"];
    
    if (cmd == "INIT") {
        // Primary node initialization
        float primaryFreq = doc["payload"];
        Serial.printf("Primary initialized on %.1f MHz\n", primaryFreq);
        sendUartResponse("ACK", "INIT_OK");
        
    } else if (cmd == "ACTIVATE_RELAY") {
        // Enable/disable relay mode
        String activate = doc["payload"];
        
        if (activate == "true" && !relayState.active) {
            Serial.println("\n════════════════════════════════");
            Serial.println("⚡ RELAY MODE ACTIVATED");
            Serial.println("════════════════════════════════\n");
            relayState.active = true;
            relayState.packetsRelayed = 0;
            relayState.bytesRelayed = 0;
            sendUartResponse("RELAY_ACK", "ACTIVE");
            
        } else if (activate == "false" && relayState.active) {
            Serial.println("\n════════════════════════════════");
            Serial.println("✓ RELAY MODE DEACTIVATED");
            Serial.println("════════════════════════════════\n");
            relayState.active = false;
            sendUartResponse("RELAY_ACK", "STANDBY");
        }
        
    } else if (cmd == "RELAY_TX") {
        // Primary wants to transmit via relay
        if (!relayState.active) {
            Serial.println("Error: Relay TX requested but relay not active");
            return;
        }
        
        size_t dataLen = doc["len"];
        String hexData = doc["data"];
        
        // Convert hex string back to bytes
        uint8_t relayData[255];
        for (size_t i = 0; i < dataLen; i++) {
            String byteString = hexData.substring(i * 2, i * 2 + 2);
            relayData[i] = strtol(byteString.c_str(), NULL, 16);
        }
        
        // Transmit on mesh network
        transmitRelayPacket(relayData, dataLen);
        
    } else if (cmd == "STATUS_REQ") {
        // Primary requesting immediate status
        sendStatusReport();
    }
}

void sendUartResponse(String command, String payload) {
    StaticJsonDocument<256> doc;
    doc["cmd"] = command;
    doc["payload"] = payload;
    doc["ts"] = millis();
    
    String output;
    serializeJson(doc, output);
    UART_PRIMARY.println(output);
}

void sendStatusReport() {
    StaticJsonDocument<256> doc;
    doc["cmd"] = "STATUS";
    doc["relay"] = relayState.active;
    doc["packets"] = relayState.packetsRelayed;
    doc["bytes"] = relayState.bytesRelayed;
    doc["rssi"] = relayState.lastRSSI;
    doc["snr"] = relayState.lastSNR;
    doc["last_activity"] = (millis() - relayState.lastActivity) / 1000; // seconds ago
    
    String output;
    serializeJson(doc, output);
    UART_PRIMARY.println(output);
    
    if (relayState.active) {
        Serial.printf("Status sent: Relay active, %d packets, %d bytes\n",
                      relayState.packetsRelayed, relayState.bytesRelayed);
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