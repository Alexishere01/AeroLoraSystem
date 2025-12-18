/**
 * Unit Tests for ESP-NOW Send/Receive
 * 
 * Tests the ESPNowTransport send and receive functionality including:
 * - Packet transmission and reception
 * - Callback invocation
 * - Peer reachability detection
 * 
 * Requirements: 1.1, 1.5, 10.2
 * 
 * Note: These tests are designed for PlatformIO Unity test framework
 * and require TWO ESP32 devices to run (one sender, one receiver).
 * 
 * Test Setup:
 * - Device A (Sender): Runs sender tests
 * - Device B (Receiver): Runs receiver tests
 * - Both devices must be within ESP-NOW range (<100m)
 */

#include <Arduino.h>
#include <unity.h>
#include "ESPNowTransport.h"

// Test configuration
// Set this to true on sender device, false on receiver device
#define IS_SENDER true

// Peer MAC addresses (configure for your hardware)
// Device A MAC: 24:6F:28:AB:CD:EF
// Device B MAC: 24:6F:28:12:34:56
const uint8_t DEVICE_A_MAC[6] = {0x24, 0x6F, 0x28, 0xAB, 0xCD, 0xEF};
const uint8_t DEVICE_B_MAC[6] = {0x24, 0x6F, 0x28, 0x12, 0x34, 0x56};

// Global transport instance for testing
ESPNowTransport* transport = nullptr;

// Test data patterns
const uint8_t TEST_PATTERN_1[10] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A};
const uint8_t TEST_PATTERN_2[20] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22, 0x33, 0x44,
                                     0x55, 0x66, 0x77, 0x88, 0x99, 0x00, 0xAB, 0xCD, 0xEF, 0x12};
const uint8_t TEST_PATTERN_MAX[250] = {0xFF};  // 250 bytes of 0xFF

// ═══════════════════════════════════════════════════════════════════
// TEST SETUP AND TEARDOWN
// ═══════════════════════════════════════════════════════════════════

void setUp(void) {
    // Create fresh transport instance for each test
    transport = new ESPNowTransport();
    
    // Initialize with peer MAC based on role
    const uint8_t* peer_mac = IS_SENDER ? DEVICE_B_MAC : DEVICE_A_MAC;
    bool result = transport->begin(peer_mac);
    
    TEST_ASSERT_TRUE_MESSAGE(result, "Transport initialization should succeed");
    
    // Small delay to ensure ESP-NOW is ready
    delay(100);
}

void tearDown(void) {
    // Clean up transport instance after each test
    if (transport != nullptr) {
        delete transport;
        transport = nullptr;
    }
    
    // Deinitialize ESP-NOW to clean state
    esp_now_deinit();
    WiFi.mode(WIFI_OFF);
    
    // Delay between tests
    delay(500);
}

// ═══════════════════════════════════════════════════════════════════
// TEST CASES: PACKET TRANSMISSION
// ═══════════════════════════════════════════════════════════════════

/**
 * Test: Basic packet transmission
 * 
 * Verifies that:
 * - send() returns true for valid packet
 * - Packet is transmitted successfully
 * - Statistics are updated correctly
 * 
 * Requirements: 1.1, 1.3, 10.3
 */
void test_basic_packet_transmission(void) {
    if (!IS_SENDER) {
        TEST_IGNORE_MESSAGE("This test runs on sender device only");
        return;
    }
    
    // Get initial statistics
    ESPNowStats stats_before = transport->getStats();
    
    // Send test packet
    bool result = transport->send(TEST_PATTERN_1, sizeof(TEST_PATTERN_1));
    
    // Verify send initiated successfully
    TEST_ASSERT_TRUE_MESSAGE(result, "Send should succeed");
    
    // Wait for send callback
    delay(100);
    
    // Get updated statistics
    ESPNowStats stats_after = transport->getStats();
    
    // Verify statistics updated
    TEST_ASSERT_GREATER_THAN_MESSAGE(stats_before.packets_sent, stats_after.packets_sent,
                                    "Packets sent counter should increase");
}

/**
 * Test: Multiple packet transmission
 * 
 * Verifies that:
 * - Multiple packets can be sent in sequence
 * - Each packet is transmitted successfully
 * - Statistics track all transmissions
 * 
 * Requirements: 1.1, 1.3
 */
void test_multiple_packet_transmission(void) {
    if (!IS_SENDER) {
        TEST_IGNORE_MESSAGE("This test runs on sender device only");
        return;
    }
    
    const int NUM_PACKETS = 10;
    int successful_sends = 0;
    
    // Send multiple packets
    for (int i = 0; i < NUM_PACKETS; i++) {
        bool result = transport->send(TEST_PATTERN_1, sizeof(TEST_PATTERN_1));
        if (result) {
            successful_sends++;
        }
        delay(50);  // Small delay between packets
    }
    
    // Verify all sends succeeded
    TEST_ASSERT_EQUAL_MESSAGE(NUM_PACKETS, successful_sends,
                             "All packet sends should succeed");
    
    // Wait for all callbacks
    delay(500);
    
    // Verify statistics
    ESPNowStats stats = transport->getStats();
    TEST_ASSERT_GREATER_OR_EQUAL_MESSAGE(NUM_PACKETS, stats.packets_sent,
                                        "At least NUM_PACKETS should be sent");
}

/**
 * Test: Maximum payload size transmission
 * 
 * Verifies that:
 * - 250-byte packets can be sent successfully
 * - Maximum payload size is supported
 * 
 * Requirements: 1.1, 1.3
 */
void test_max_payload_transmission(void) {
    if (!IS_SENDER) {
        TEST_IGNORE_MESSAGE("This test runs on sender device only");
        return;
    }
    
    // Prepare maximum size payload (250 bytes)
    uint8_t max_payload[250];
    for (int i = 0; i < 250; i++) {
        max_payload[i] = i & 0xFF;
    }
    
    // Send maximum size packet
    bool result = transport->send(max_payload, 250);
    
    // Verify send succeeded
    TEST_ASSERT_TRUE_MESSAGE(result, "Maximum payload size should be supported");
    
    // Wait for send callback
    delay(100);
    
    // Verify statistics
    ESPNowStats stats = transport->getStats();
    TEST_ASSERT_GREATER_THAN_MESSAGE(0, stats.packets_sent,
                                    "Packet should be sent successfully");
}

// ═══════════════════════════════════════════════════════════════════
// TEST CASES: PACKET RECEPTION
// ═══════════════════════════════════════════════════════════════════

/**
 * Test: Basic packet reception
 * 
 * Verifies that:
 * - Packets are received successfully
 * - available() returns true when data ready
 * - receive() returns correct data
 * 
 * Requirements: 1.1, 10.2
 * 
 * Note: Requires sender device to be transmitting
 */
void test_basic_packet_reception(void) {
    if (IS_SENDER) {
        TEST_IGNORE_MESSAGE("This test runs on receiver device only");
        return;
    }
    
    Serial.println("[TEST] Waiting for packet from sender...");
    
    // Wait for packet (timeout after 5 seconds)
    unsigned long start = millis();
    while (!transport->available() && (millis() - start < 5000)) {
        delay(10);
    }
    
    // Verify packet received
    TEST_ASSERT_TRUE_MESSAGE(transport->available(), 
                            "Packet should be received within 5 seconds");
    
    // Receive packet
    uint8_t rx_buffer[250];
    uint8_t rx_len = transport->receive(rx_buffer, sizeof(rx_buffer));
    
    // Verify data received
    TEST_ASSERT_GREATER_THAN_MESSAGE(0, rx_len, "Received data length should be > 0");
    
    // Verify statistics
    ESPNowStats stats = transport->getStats();
    TEST_ASSERT_GREATER_THAN_MESSAGE(0, stats.packets_received,
                                    "Packets received counter should increase");
}

/**
 * Test: Multiple packet reception
 * 
 * Verifies that:
 * - Multiple packets can be received in sequence
 * - Each packet is processed correctly
 * - Statistics track all receptions
 * 
 * Requirements: 1.1, 10.2
 * 
 * Note: Requires sender device to be transmitting multiple packets
 */
void test_multiple_packet_reception(void) {
    if (IS_SENDER) {
        TEST_IGNORE_MESSAGE("This test runs on receiver device only");
        return;
    }
    
    Serial.println("[TEST] Waiting for multiple packets from sender...");
    
    const int EXPECTED_PACKETS = 5;
    int received_count = 0;
    
    // Wait for multiple packets (timeout after 10 seconds)
    unsigned long start = millis();
    while (received_count < EXPECTED_PACKETS && (millis() - start < 10000)) {
        if (transport->available()) {
            uint8_t rx_buffer[250];
            uint8_t rx_len = transport->receive(rx_buffer, sizeof(rx_buffer));
            
            if (rx_len > 0) {
                received_count++;
                Serial.printf("[TEST] Received packet %d/%d (%d bytes)\n", 
                             received_count, EXPECTED_PACKETS, rx_len);
            }
        }
        delay(10);
    }
    
    // Verify packets received
    TEST_ASSERT_GREATER_OR_EQUAL_MESSAGE(EXPECTED_PACKETS, received_count,
                                        "Should receive at least EXPECTED_PACKETS");
    
    // Verify statistics
    ESPNowStats stats = transport->getStats();
    TEST_ASSERT_GREATER_OR_EQUAL_MESSAGE(EXPECTED_PACKETS, stats.packets_received,
                                        "Statistics should match received count");
}

/**
 * Test: Data integrity verification
 * 
 * Verifies that:
 * - Received data matches transmitted data
 * - No corruption occurs during transmission
 * 
 * Requirements: 1.1, 10.2
 * 
 * Note: Requires coordinated sender/receiver test
 */
void test_data_integrity(void) {
    if (IS_SENDER) {
        // Sender: Transmit known pattern
        Serial.println("[TEST] Sending test pattern...");
        
        for (int i = 0; i < 5; i++) {
            transport->send(TEST_PATTERN_1, sizeof(TEST_PATTERN_1));
            delay(200);
        }
        
        TEST_PASS_MESSAGE("Test pattern sent");
    } else {
        // Receiver: Verify received pattern
        Serial.println("[TEST] Waiting for test pattern...");
        
        // Wait for packet
        unsigned long start = millis();
        while (!transport->available() && (millis() - start < 5000)) {
            delay(10);
        }
        
        TEST_ASSERT_TRUE_MESSAGE(transport->available(), "Should receive packet");
        
        // Receive and verify
        uint8_t rx_buffer[250];
        uint8_t rx_len = transport->receive(rx_buffer, sizeof(rx_buffer));
        
        TEST_ASSERT_EQUAL_MESSAGE(sizeof(TEST_PATTERN_1), rx_len,
                                 "Received length should match sent length");
        
        TEST_ASSERT_EQUAL_UINT8_ARRAY_MESSAGE(TEST_PATTERN_1, rx_buffer, sizeof(TEST_PATTERN_1),
                                              "Received data should match sent data");
    }
}

// ═══════════════════════════════════════════════════════════════════
// TEST CASES: PEER REACHABILITY
// ═══════════════════════════════════════════════════════════════════

/**
 * Test: Peer reachability detection
 * 
 * Verifies that:
 * - Peer becomes reachable after receiving packet
 * - isPeerReachable() returns true when peer is active
 * - Statistics reflect peer reachability
 * 
 * Requirements: 1.5, 10.2
 */
void test_peer_reachability_detection(void) {
    if (IS_SENDER) {
        TEST_IGNORE_MESSAGE("This test runs on receiver device only");
        return;
    }
    
    // Initially peer should not be reachable
    TEST_ASSERT_FALSE_MESSAGE(transport->isPeerReachable(),
                             "Peer should not be reachable initially");
    
    Serial.println("[TEST] Waiting for packet to establish reachability...");
    
    // Wait for packet
    unsigned long start = millis();
    while (!transport->available() && (millis() - start < 5000)) {
        transport->process();  // Update reachability
        delay(10);
    }
    
    // Receive packet
    if (transport->available()) {
        uint8_t rx_buffer[250];
        transport->receive(rx_buffer, sizeof(rx_buffer));
    }
    
    // Process to update reachability
    transport->process();
    
    // Verify peer is now reachable
    TEST_ASSERT_TRUE_MESSAGE(transport->isPeerReachable(),
                            "Peer should be reachable after receiving packet");
    
    // Verify statistics
    ESPNowStats stats = transport->getStats();
    TEST_ASSERT_TRUE_MESSAGE(stats.peer_reachable,
                            "Statistics should show peer reachable");
}

/**
 * Test: Peer unreachable timeout
 * 
 * Verifies that:
 * - Peer becomes unreachable after 3 second timeout
 * - isPeerReachable() returns false after timeout
 * - Statistics track unreachable events
 * 
 * Requirements: 1.5, 10.2
 */
void test_peer_unreachable_timeout(void) {
    if (IS_SENDER) {
        TEST_IGNORE_MESSAGE("This test runs on receiver device only");
        return;
    }
    
    Serial.println("[TEST] Waiting for packet to establish reachability...");
    
    // Wait for packet to establish reachability
    unsigned long start = millis();
    while (!transport->available() && (millis() - start < 5000)) {
        transport->process();
        delay(10);
    }
    
    if (transport->available()) {
        uint8_t rx_buffer[250];
        transport->receive(rx_buffer, sizeof(rx_buffer));
        transport->process();
    }
    
    // Verify peer is reachable
    TEST_ASSERT_TRUE_MESSAGE(transport->isPeerReachable(),
                            "Peer should be reachable after receiving packet");
    
    Serial.println("[TEST] Waiting for 3 second timeout...");
    Serial.println("[TEST] (Sender should stop transmitting)");
    
    // Wait for timeout (3 seconds + margin)
    unsigned long timeout_start = millis();
    while (millis() - timeout_start < 3500) {
        transport->process();  // Update reachability
        delay(100);
    }
    
    // Verify peer is now unreachable
    TEST_ASSERT_FALSE_MESSAGE(transport->isPeerReachable(),
                             "Peer should be unreachable after 3 second timeout");
    
    // Verify statistics
    ESPNowStats stats = transport->getStats();
    TEST_ASSERT_FALSE_MESSAGE(stats.peer_reachable,
                             "Statistics should show peer unreachable");
    TEST_ASSERT_GREATER_THAN_MESSAGE(0, stats.peer_unreachable_count,
                                    "Unreachable count should increase");
}

// ═══════════════════════════════════════════════════════════════════
// TEST CASES: CALLBACK INVOCATION
// ═══════════════════════════════════════════════════════════════════

/**
 * Test: Send callback invocation
 * 
 * Verifies that:
 * - Send callback is invoked after transmission
 * - Statistics are updated in callback
 * 
 * Requirements: 1.1, 10.3
 */
void test_send_callback_invocation(void) {
    if (!IS_SENDER) {
        TEST_IGNORE_MESSAGE("This test runs on sender device only");
        return;
    }
    
    // Get initial statistics
    ESPNowStats stats_before = transport->getStats();
    uint32_t sent_before = stats_before.packets_sent;
    
    // Send packet
    bool result = transport->send(TEST_PATTERN_1, sizeof(TEST_PATTERN_1));
    TEST_ASSERT_TRUE(result);
    
    // Wait for callback (should be quick)
    delay(100);
    
    // Get updated statistics
    ESPNowStats stats_after = transport->getStats();
    
    // Verify callback was invoked (statistics updated)
    TEST_ASSERT_GREATER_THAN_MESSAGE(sent_before, stats_after.packets_sent,
                                    "Send callback should update statistics");
}

/**
 * Test: Receive callback invocation
 * 
 * Verifies that:
 * - Receive callback is invoked when packet arrives
 * - Data is copied to RX buffer in callback
 * - Statistics are updated in callback
 * 
 * Requirements: 1.1, 10.2
 */
void test_receive_callback_invocation(void) {
    if (IS_SENDER) {
        TEST_IGNORE_MESSAGE("This test runs on receiver device only");
        return;
    }
    
    Serial.println("[TEST] Waiting for packet to trigger receive callback...");
    
    // Get initial statistics
    ESPNowStats stats_before = transport->getStats();
    uint32_t received_before = stats_before.packets_received;
    
    // Wait for packet
    unsigned long start = millis();
    while (!transport->available() && (millis() - start < 5000)) {
        delay(10);
    }
    
    // Verify packet received (callback was invoked)
    TEST_ASSERT_TRUE_MESSAGE(transport->available(),
                            "Receive callback should set data available");
    
    // Get updated statistics
    ESPNowStats stats_after = transport->getStats();
    
    // Verify callback updated statistics
    TEST_ASSERT_GREATER_THAN_MESSAGE(received_before, stats_after.packets_received,
                                    "Receive callback should update statistics");
}

// ═══════════════════════════════════════════════════════════════════
// MAIN TEST RUNNER
// ═══════════════════════════════════════════════════════════════════

void setup() {
    // Wait for serial connection
    delay(2000);
    
    Serial.begin(115200);
    Serial.println("\n\n=== ESP-NOW Send/Receive Tests ===");
    Serial.printf("Device Role: %s\n", IS_SENDER ? "SENDER" : "RECEIVER");
    Serial.printf("My MAC: %s\n", WiFi.macAddress().c_str());
    Serial.println("===================================\n");
    
    // Initialize Unity test framework
    UNITY_BEGIN();
    
    if (IS_SENDER) {
        // Sender tests
        Serial.println("Running SENDER tests...\n");
        RUN_TEST(test_basic_packet_transmission);
        RUN_TEST(test_multiple_packet_transmission);
        RUN_TEST(test_max_payload_transmission);
        RUN_TEST(test_send_callback_invocation);
        RUN_TEST(test_data_integrity);  // Coordinated test
    } else {
        // Receiver tests
        Serial.println("Running RECEIVER tests...\n");
        RUN_TEST(test_basic_packet_reception);
        RUN_TEST(test_multiple_packet_reception);
        RUN_TEST(test_peer_reachability_detection);
        RUN_TEST(test_peer_unreachable_timeout);
        RUN_TEST(test_receive_callback_invocation);
        RUN_TEST(test_data_integrity);  // Coordinated test
    }
    
    // Finish testing
    UNITY_END();
}

void loop() {
    // Tests run once in setup()
}
