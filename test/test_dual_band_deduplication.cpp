/**
 * Unit Tests for DualBandTransport Deduplication
 * 
 * Tests:
 * - Duplicate detection by MAVLink sequence number
 * - Sequence number wraparound handling
 * - Deduplication statistics
 * 
 * Requirements: 3.2
 */

#include <unity.h>
#include "DualBandTransport.h"
#include "ESPNowTransport.h"
#include "AeroLoRaProtocol.h"

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

// Helper to simulate packet reception via ESP-NOW
void simulateESPNowRx(DualBandTransport* transport, ESPNowTransport* espnow, 
                      uint8_t* data, uint8_t len) {
    // Directly inject packet into ESP-NOW receive buffer
    espnow->injectTestPacket(data, len);
}

// Helper to simulate packet reception via LoRa
void simulateLoRaRx(DualBandTransport* transport, AeroLoRaProtocol* lora,
                    uint8_t* data, uint8_t len) {
    // Create AeroLoRa packet
    AeroLoRaPacket packet;
    packet.header = AEROLORA_HEADER;
    packet.src_id = NODE_GROUND;
    packet.dest_id = NODE_DRONE;
    packet.payload_len = len;
    memcpy(packet.payload, data, len);
    
    // Inject into LoRa protocol
    lora->handleReceivedPacket(&packet);
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
 * Test: Duplicate detection by MAVLink sequence number
 * 
 * Requirement 3.2: WHEN receiving duplicate messages on both links THEN the system SHALL 
 *                  deduplicate based on MAVLink sequence numbers
 */
void test_duplicate_detection_by_sequence_number(void) {
    uint8_t buffer[18];
    uint8_t rxBuffer[256];
    
    // Create a HEARTBEAT packet with sequence number 5
    createMavlinkV1Packet(buffer, 0, 1, 5);
    
    // Simulate receiving the same packet via ESP-NOW
    simulateESPNowRx(dual_band, espnow_transport, buffer, 18);
    
    // First reception should succeed
    uint8_t len = dual_band->receive(rxBuffer, 256);
    TEST_ASSERT_EQUAL(18, len);
    TEST_ASSERT_EQUAL_MEMORY(buffer, rxBuffer, 18);
    
    // Simulate receiving the same packet again via LoRa (duplicate)
    simulateLoRaRx(dual_band, lora_protocol, buffer, 18);
    
    // Second reception should be filtered (duplicate)
    len = dual_band->receive(rxBuffer, 256);
    TEST_ASSERT_EQUAL(0, len);  // No data (duplicate dropped)
    
    // Check statistics
    DualBandStats stats = dual_band->getStats();
    TEST_ASSERT_EQUAL(1, stats.duplicate_packets_dropped);
}

/**
 * Test: Different sequence numbers are not duplicates
 * 
 * Requirement 3.2: WHEN receiving duplicate messages on both links THEN the system SHALL 
 *                  deduplicate based on MAVLink sequence numbers
 */
void test_different_sequence_numbers_not_duplicates(void) {
    uint8_t buffer1[18];
    uint8_t buffer2[18];
    uint8_t rxBuffer[256];
    
    // Create two HEARTBEAT packets with different sequence numbers
    createMavlinkV1Packet(buffer1, 0, 1, 5);
    createMavlinkV1Packet(buffer2, 0, 1, 6);
    
    // Simulate receiving first packet via ESP-NOW
    simulateESPNowRx(dual_band, espnow_transport, buffer1, 18);
    
    // First reception should succeed
    uint8_t len = dual_band->receive(rxBuffer, 256);
    TEST_ASSERT_EQUAL(18, len);
    
    // Simulate receiving second packet via LoRa (different sequence)
    simulateLoRaRx(dual_band, lora_protocol, buffer2, 18);
    
    // Second reception should also succeed (not a duplicate)
    len = dual_band->receive(rxBuffer, 256);
    TEST_ASSERT_EQUAL(18, len);
    
    // Check statistics - no duplicates
    DualBandStats stats = dual_band->getStats();
    TEST_ASSERT_EQUAL(0, stats.duplicate_packets_dropped);
}

/**
 * Test: Sequence number wraparound handling
 * 
 * Requirement 3.2: WHEN receiving duplicate messages on both links THEN the system SHALL 
 *                  deduplicate based on MAVLink sequence numbers
 * 
 * MAVLink sequence numbers are 8-bit (0-255) and wrap around.
 * The deduplication logic must handle: 253, 254, 255, 0, 1, 2
 */
void test_sequence_number_wraparound_handling(void) {
    uint8_t buffer[18];
    uint8_t rxBuffer[256];
    
    // Test sequence: 253, 254, 255, 0, 1, 2
    uint8_t sequences[] = {253, 254, 255, 0, 1, 2};
    
    for (int i = 0; i < 6; i++) {
        createMavlinkV1Packet(buffer, 0, 1, sequences[i]);
        
        // Simulate receiving via ESP-NOW
        simulateESPNowRx(dual_band, espnow_transport, buffer, 18);
        
        // Should receive successfully (not a duplicate)
        uint8_t len = dual_band->receive(rxBuffer, 256);
        TEST_ASSERT_EQUAL(18, len);
        TEST_ASSERT_EQUAL(sequences[i], rxBuffer[2]);  // Verify sequence number
    }
    
    // Check statistics - no duplicates despite wraparound
    DualBandStats stats = dual_band->getStats();
    TEST_ASSERT_EQUAL(0, stats.duplicate_packets_dropped);
}

/**
 * Test: Wraparound duplicate detection
 * 
 * Requirement 3.2: WHEN receiving duplicate messages on both links THEN the system SHALL 
 *                  deduplicate based on MAVLink sequence numbers
 * 
 * Test that duplicates are still detected across wraparound boundary
 */
void test_wraparound_duplicate_detection(void) {
    uint8_t buffer[18];
    uint8_t rxBuffer[256];
    
    // Receive sequence 255
    createMavlinkV1Packet(buffer, 0, 1, 255);
    simulateESPNowRx(dual_band, espnow_transport, buffer, 18);
    uint8_t len = dual_band->receive(rxBuffer, 256);
    TEST_ASSERT_EQUAL(18, len);
    
    // Receive sequence 0 (wraparound)
    createMavlinkV1Packet(buffer, 0, 1, 0);
    simulateESPNowRx(dual_band, espnow_transport, buffer, 18);
    len = dual_band->receive(rxBuffer, 256);
    TEST_ASSERT_EQUAL(18, len);
    
    // Receive sequence 0 again (duplicate)
    simulateLoRaRx(dual_band, lora_protocol, buffer, 18);
    len = dual_band->receive(rxBuffer, 256);
    TEST_ASSERT_EQUAL(0, len);  // Should be dropped as duplicate
    
    // Check statistics
    DualBandStats stats = dual_band->getStats();
    TEST_ASSERT_EQUAL(1, stats.duplicate_packets_dropped);
}

/**
 * Test: Per-system-ID deduplication
 * 
 * Requirement 3.2: WHEN receiving duplicate messages on both links THEN the system SHALL 
 *                  deduplicate based on MAVLink sequence numbers
 * 
 * Different system IDs should have independent sequence tracking
 */
void test_per_system_id_deduplication(void) {
    uint8_t buffer1[18];
    uint8_t buffer2[18];
    uint8_t rxBuffer[256];
    
    // Create packets from two different systems with same sequence number
    createMavlinkV1Packet(buffer1, 0, 1, 5);  // System ID 1, seq 5
    createMavlinkV1Packet(buffer2, 0, 2, 5);  // System ID 2, seq 5
    
    // Receive from system 1
    simulateESPNowRx(dual_band, espnow_transport, buffer1, 18);
    uint8_t len = dual_band->receive(rxBuffer, 256);
    TEST_ASSERT_EQUAL(18, len);
    
    // Receive from system 2 (different system, same sequence)
    simulateLoRaRx(dual_band, lora_protocol, buffer2, 18);
    len = dual_band->receive(rxBuffer, 256);
    TEST_ASSERT_EQUAL(18, len);  // Should NOT be duplicate (different system)
    
    // Receive from system 1 again (duplicate)
    simulateLoRaRx(dual_band, lora_protocol, buffer1, 18);
    len = dual_band->receive(rxBuffer, 256);
    TEST_ASSERT_EQUAL(0, len);  // Should be duplicate
    
    // Check statistics
    DualBandStats stats = dual_band->getStats();
    TEST_ASSERT_EQUAL(1, stats.duplicate_packets_dropped);
}

/**
 * Test: Deduplication statistics
 * 
 * Requirement 3.2: WHEN receiving duplicate messages on both links THEN the system SHALL 
 *                  deduplicate based on MAVLink sequence numbers
 */
void test_deduplication_statistics(void) {
    uint8_t buffer[18];
    uint8_t rxBuffer[256];
    
    // Send 10 packets, each duplicated once
    for (int i = 0; i < 10; i++) {
        createMavlinkV1Packet(buffer, 0, 1, i);
        
        // First reception via ESP-NOW
        simulateESPNowRx(dual_band, espnow_transport, buffer, 18);
        dual_band->receive(rxBuffer, 256);
        
        // Duplicate via LoRa
        simulateLoRaRx(dual_band, lora_protocol, buffer, 18);
        dual_band->receive(rxBuffer, 256);
    }
    
    // Check statistics
    DualBandStats stats = dual_band->getStats();
    
    // Should have received 10 unique packets
    TEST_ASSERT_EQUAL(10, stats.espnow_packets_received);
    
    // Should have dropped 10 duplicates
    TEST_ASSERT_EQUAL(10, stats.duplicate_packets_dropped);
}

/**
 * Test: MAVLink v2 deduplication
 * 
 * Requirement 3.2: WHEN receiving duplicate messages on both links THEN the system SHALL 
 *                  deduplicate based on MAVLink sequence numbers
 * 
 * Test deduplication with MAVLink v2 packets (different header format)
 */
void test_mavlink_v2_deduplication(void) {
    uint8_t buffer[20];
    uint8_t rxBuffer[256];
    
    // Create MAVLink v2 packet
    buffer[0] = 0xFD;  // MAVLink v2 magic
    buffer[1] = 10;    // Payload length
    buffer[2] = 0;     // Incompatibility flags
    buffer[3] = 0;     // Compatibility flags
    buffer[4] = 5;     // Sequence number
    buffer[5] = 1;     // System ID
    buffer[6] = 1;     // Component ID
    buffer[7] = 0;     // Message ID (low byte)
    buffer[8] = 0;     // Message ID (mid byte)
    buffer[9] = 0;     // Message ID (high byte)
    // Payload (10 bytes)
    for (int i = 0; i < 10; i++) {
        buffer[10 + i] = i;
    }
    
    // Simulate receiving via ESP-NOW
    simulateESPNowRx(dual_band, espnow_transport, buffer, 20);
    uint8_t len = dual_band->receive(rxBuffer, 256);
    TEST_ASSERT_EQUAL(20, len);
    
    // Simulate receiving duplicate via LoRa
    simulateLoRaRx(dual_band, lora_protocol, buffer, 20);
    len = dual_band->receive(rxBuffer, 256);
    TEST_ASSERT_EQUAL(0, len);  // Should be dropped as duplicate
    
    // Check statistics
    DualBandStats stats = dual_band->getStats();
    TEST_ASSERT_EQUAL(1, stats.duplicate_packets_dropped);
}

void setup() {
    delay(2000);  // Wait for serial
    UNITY_BEGIN();
    
    RUN_TEST(test_duplicate_detection_by_sequence_number);
    RUN_TEST(test_different_sequence_numbers_not_duplicates);
    RUN_TEST(test_sequence_number_wraparound_handling);
    RUN_TEST(test_wraparound_duplicate_detection);
    RUN_TEST(test_per_system_id_deduplication);
    RUN_TEST(test_deduplication_statistics);
    RUN_TEST(test_mavlink_v2_deduplication);
    
    UNITY_END();
}

void loop() {
    // Nothing to do
}
