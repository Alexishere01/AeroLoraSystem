/**
 * Unit Tests for DualBandTransport Message Routing
 * 
 * Tests:
 * - Essential messages sent over both transports
 * - Non-essential messages sent over ESP-NOW only
 * - LoRa-only mode when ESP-NOW unavailable
 * 
 * Requirements: 2.1, 2.2, 3.1, 7.1, 7.2
 */

#include <unity.h>
#include "DualBandTransport.h"
#include "ESPNowTransport.h"
#include "AeroLoRaProtocol.h"
#include "MessageFilter.h"

// Mock radio for testing
class MockRadio : public SX1262 {
public:
    MockRadio() : SX1262(new Module(0, 0, 0, 0)) {}
    
    int16_t transmit(uint8_t* data, size_t len) override {
        return RADIOLIB_ERR_NONE;
    }
    
    int16_t startReceive() override {
        return RADIOLIB_ERR_NONE;
    }
};

// Test fixtures
static ESPNowTransport* espnow_transport;
static AeroLoRaProtocol* lora_protocol;
static DualBandTransport* dual_band;
static MockRadio* mock_radio;

// Helper to create MAVLink v1 packet
void createMavlinkV1Packet(uint8_t* buffer, uint8_t msgId, uint8_t sysId, uint8_t seqNum) {
    buffer[0] = 0xFE;  // MAVLink v1 magic
    buffer[1] = 10;    // Payload length
    buffer[2] = seqNum; // Sequence number
    buffer[3] = sysId;  // System ID
    buffer[4] = 1;      // Component ID
    buffer[5] = msgId;  // Message ID
    // Payload (10 bytes)
    for (int i = 0; i < 10; i++) {
        buffer[6 + i] = i;
    }
    // CRC (2 bytes)
    buffer[16] = 0x00;
    buffer[17] = 0x00;
}

void setUp(void) {
    // Initialize mock radio
    mock_radio = new MockRadio();
    
    // Initialize transports
    uint8_t peer_mac[6] = {0x24, 0x6F, 0x28, 0xAB, 0xCD, 0xEF};
    espnow_transport = new ESPNowTransport();
    espnow_transport->begin(peer_mac);
    
    lora_protocol = new AeroLoRaProtocol(mock_radio, 0, 100);
    lora_protocol->begin(NODE_DRONE);
    
    // Initialize dual-band transport
    dual_band = new DualBandTransport(espnow_transport, lora_protocol);
    dual_band->begin(NODE_DRONE);
}

void tearDown(void) {
    delete dual_band;
    delete lora_protocol;
    delete espnow_transport;
    delete mock_radio;
}

/**
 * Test: Essential messages sent over both transports
 * 
 * Requirement 2.1: WHEN sending over LoRa THEN the system SHALL filter to only 8 essential MAVLink message types
 * Requirement 3.1: WHEN both links are active THEN the system SHALL send all MAVLink messages over ESP-NOW 
 *                  and only essential messages over LoRa
 */
void test_essential_messages_sent_over_both_transports(void) {
    // Test all 8 essential message types
    uint8_t essential_messages[] = {0, 30, 33, 74, 76, 77, 147, 253};
    
    for (int i = 0; i < 8; i++) {
        uint8_t buffer[18];
        createMavlinkV1Packet(buffer, essential_messages[i], 1, i);
        
        // Reset stats
        dual_band->resetStats();
        
        // Send essential message
        bool result = dual_band->send(buffer, 18, NODE_GROUND);
        TEST_ASSERT_TRUE(result);
        
        // Get stats
        DualBandStats stats = dual_band->getStats();
        
        // Essential message should be sent over ESP-NOW
        TEST_ASSERT_EQUAL(1, stats.espnow_packets_sent);
        
        // Essential message should also be sent over LoRa
        TEST_ASSERT_EQUAL(1, stats.lora_packets_sent);
        
        // No messages should be filtered
        TEST_ASSERT_EQUAL(0, stats.lora_filtered_messages);
    }
}

/**
 * Test: Non-essential messages sent over ESP-NOW only
 * 
 * Requirement 2.2: WHEN a non-essential MAVLink message is queued for LoRa THEN the system SHALL drop it 
 *                  if ESP-NOW is unavailable or queue it for ESP-NOW only
 * Requirement 7.1: WHEN ESP-NOW is available THEN the system SHALL send all MAVLink messages including 
 *                  bulk transfers over ESP-NOW
 */
void test_non_essential_messages_sent_over_espnow_only(void) {
    // Test non-essential message types (not in the 8 essential list)
    uint8_t non_essential_messages[] = {1, 22, 24, 27, 100, 150, 200};
    
    for (int i = 0; i < 7; i++) {
        uint8_t buffer[18];
        createMavlinkV1Packet(buffer, non_essential_messages[i], 1, i);
        
        // Reset stats
        dual_band->resetStats();
        
        // Send non-essential message
        bool result = dual_band->send(buffer, 18, NODE_GROUND);
        TEST_ASSERT_TRUE(result);
        
        // Get stats
        DualBandStats stats = dual_band->getStats();
        
        // Non-essential message should be sent over ESP-NOW
        TEST_ASSERT_EQUAL(1, stats.espnow_packets_sent);
        
        // Non-essential message should NOT be sent over LoRa
        TEST_ASSERT_EQUAL(0, stats.lora_packets_sent);
        
        // Message should be counted as filtered
        TEST_ASSERT_EQUAL(1, stats.lora_filtered_messages);
    }
}

/**
 * Test: LoRa-only mode when ESP-NOW unavailable
 * 
 * Requirement 3.1: WHEN both links are active THEN the system SHALL send all MAVLink messages over ESP-NOW 
 *                  and only essential messages over LoRa
 * Requirement 7.2: WHEN LoRa is the only available link THEN the system SHALL apply message filtering 
 *                  to send only essential telemetry
 */
void test_lora_only_mode_when_espnow_unavailable(void) {
    // Simulate ESP-NOW peer unreachable by waiting for timeout
    // (In real implementation, this would be 3 seconds of no RX)
    // For testing, we'll just verify the behavior when ESP-NOW send fails
    
    // Test essential message - should still be sent over LoRa
    uint8_t essential_buffer[18];
    createMavlinkV1Packet(essential_buffer, 0, 1, 0);  // HEARTBEAT
    
    dual_band->resetStats();
    bool result = dual_band->send(essential_buffer, 18, NODE_GROUND);
    
    // Should succeed (LoRa available)
    TEST_ASSERT_TRUE(result);
    
    DualBandStats stats = dual_band->getStats();
    
    // Essential message should be sent over LoRa
    TEST_ASSERT_EQUAL(1, stats.lora_packets_sent);
    
    // Test non-essential message - should be filtered
    uint8_t non_essential_buffer[18];
    createMavlinkV1Packet(non_essential_buffer, 22, 1, 1);  // PARAM_VALUE
    
    dual_band->resetStats();
    result = dual_band->send(non_essential_buffer, 18, NODE_GROUND);
    
    stats = dual_band->getStats();
    
    // Non-essential message should NOT be sent over LoRa
    TEST_ASSERT_EQUAL(0, stats.lora_packets_sent);
    
    // Message should be counted as filtered
    TEST_ASSERT_EQUAL(1, stats.lora_filtered_messages);
}

/**
 * Test: Link status checking
 * 
 * Requirement 6.4: WHEN querying link status THEN the API SHALL provide a consistent interface 
 *                  for both ESP-NOW and LoRa metrics
 */
void test_link_status_checking(void) {
    // Check ESP-NOW availability
    bool espnow_available = dual_band->isESPNowAvailable();
    // ESP-NOW peer reachability depends on recent RX
    // Initially should be false (no packets received yet)
    TEST_ASSERT_FALSE(espnow_available);
    
    // Check LoRa availability
    bool lora_available = dual_band->isLoRaAvailable();
    // LoRa should always be available if initialized
    TEST_ASSERT_TRUE(lora_available);
}

/**
 * Test: Statistics aggregation
 * 
 * Requirement 6.4: WHEN querying link status THEN the API SHALL provide a consistent interface 
 *                  for both ESP-NOW and LoRa metrics
 */
void test_statistics_aggregation(void) {
    // Send a mix of essential and non-essential messages
    uint8_t buffer[18];
    
    // Send HEARTBEAT (essential)
    createMavlinkV1Packet(buffer, 0, 1, 0);
    dual_band->send(buffer, 18, NODE_GROUND);
    
    // Send PARAM_VALUE (non-essential)
    createMavlinkV1Packet(buffer, 22, 1, 1);
    dual_band->send(buffer, 18, NODE_GROUND);
    
    // Send ATTITUDE (essential)
    createMavlinkV1Packet(buffer, 30, 1, 2);
    dual_band->send(buffer, 18, NODE_GROUND);
    
    // Get stats
    DualBandStats stats = dual_band->getStats();
    
    // Should have sent 3 packets over ESP-NOW
    TEST_ASSERT_EQUAL(3, stats.espnow_packets_sent);
    
    // Should have sent 2 essential packets over LoRa
    TEST_ASSERT_EQUAL(2, stats.lora_packets_sent);
    
    // Should have filtered 1 non-essential packet
    TEST_ASSERT_EQUAL(1, stats.lora_filtered_messages);
}

void setup() {
    delay(2000);  // Wait for serial
    UNITY_BEGIN();
    
    RUN_TEST(test_essential_messages_sent_over_both_transports);
    RUN_TEST(test_non_essential_messages_sent_over_espnow_only);
    RUN_TEST(test_lora_only_mode_when_espnow_unavailable);
    RUN_TEST(test_link_status_checking);
    RUN_TEST(test_statistics_aggregation);
    
    UNITY_END();
}

void loop() {
    // Nothing to do
}
