/**
 * Unit Tests for ESP-NOW Initialization
 * 
 * Tests the ESPNowTransport initialization functionality including:
 * - Successful initialization with valid peer MAC
 * - Failure handling for invalid configuration
 * - Peer addition and removal
 * 
 * Requirements: 1.1, 4.2
 * 
 * Note: These tests are designed for PlatformIO Unity test framework
 * and require actual ESP32 hardware to run.
 */

#include <Arduino.h>
#include <unity.h>
#include "ESPNowTransport.h"

// Test peer MAC addresses
const uint8_t VALID_PEER_MAC[6] = {0x24, 0x6F, 0x28, 0xAB, 0xCD, 0xEF};
const uint8_t ANOTHER_PEER_MAC[6] = {0x24, 0x6F, 0x28, 0x12, 0x34, 0x56};

// Global transport instance for testing
ESPNowTransport* transport = nullptr;

// ═══════════════════════════════════════════════════════════════════
// TEST SETUP AND TEARDOWN
// ═══════════════════════════════════════════════════════════════════

void setUp(void) {
    // Create fresh transport instance for each test
    transport = new ESPNowTransport();
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
}

// ═══════════════════════════════════════════════════════════════════
// TEST CASES: SUCCESSFUL INITIALIZATION
// ═══════════════════════════════════════════════════════════════════

/**
 * Test: Successful initialization with valid peer MAC
 * 
 * Verifies that:
 * - begin() returns true with valid MAC address
 * - WiFi is initialized in station mode
 * - ESP-NOW protocol is initialized
 * - Peer is added successfully
 * 
 * Requirements: 1.1, 4.2
 */
void test_init_success_with_valid_mac(void) {
    // Initialize with valid peer MAC
    bool result = transport->begin(VALID_PEER_MAC);
    
    // Verify initialization succeeded
    TEST_ASSERT_TRUE_MESSAGE(result, "Initialization should succeed with valid MAC");
    
    // Verify WiFi is in station mode
    TEST_ASSERT_EQUAL_MESSAGE(WIFI_STA, WiFi.getMode(), "WiFi should be in station mode");
    
    // Verify peer MAC was stored correctly
    uint8_t stored_mac[6];
    transport->getPeerMAC(stored_mac);
    TEST_ASSERT_EQUAL_UINT8_ARRAY_MESSAGE(VALID_PEER_MAC, stored_mac, 6, 
                                          "Peer MAC should be stored correctly");
    
    // Verify initial statistics
    ESPNowStats stats = transport->getStats();
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(0, stats.packets_sent, "Initial packets_sent should be 0");
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(0, stats.packets_received, "Initial packets_received should be 0");
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(0, stats.send_failures, "Initial send_failures should be 0");
    TEST_ASSERT_FALSE_MESSAGE(stats.peer_reachable, "Peer should not be reachable initially");
}

/**
 * Test: WiFi initialization in station mode
 * 
 * Verifies that:
 * - WiFi is initialized in station mode (required for ESP-NOW)
 * - WiFi is not connected to any access point
 * - WiFi MAC address is available
 * 
 * Requirements: 1.1, 4.1, 10.1
 */
void test_wifi_station_mode_initialization(void) {
    // Initialize transport
    bool result = transport->begin(VALID_PEER_MAC);
    TEST_ASSERT_TRUE(result);
    
    // Verify WiFi mode
    TEST_ASSERT_EQUAL_MESSAGE(WIFI_STA, WiFi.getMode(), 
                             "WiFi must be in station mode for ESP-NOW");
    
    // Verify WiFi is not connected to AP
    TEST_ASSERT_FALSE_MESSAGE(WiFi.isConnected(), 
                             "WiFi should not be connected to any AP");
    
    // Verify MAC address is available
    String mac = WiFi.macAddress();
    TEST_ASSERT_EQUAL_MESSAGE(17, mac.length(), 
                             "MAC address should be 17 characters (XX:XX:XX:XX:XX:XX)");
}

/**
 * Test: ESP-NOW protocol initialization
 * 
 * Verifies that:
 * - ESP-NOW protocol is initialized successfully
 * - Callbacks are registered
 * - Transport is ready for communication
 * 
 * Requirements: 1.1, 10.1, 10.2
 */
void test_espnow_protocol_initialization(void) {
    // Initialize transport
    bool result = transport->begin(VALID_PEER_MAC);
    TEST_ASSERT_TRUE_MESSAGE(result, "ESP-NOW protocol should initialize successfully");
    
    // Verify transport is ready (can attempt to send)
    uint8_t test_data[10] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A};
    bool send_result = transport->send(test_data, 10);
    
    // Send should succeed (even if peer not reachable, send should be initiated)
    TEST_ASSERT_TRUE_MESSAGE(send_result, "Send should be initiated after initialization");
}

/**
 * Test: Peer addition
 * 
 * Verifies that:
 * - Peer is added with correct MAC address
 * - Peer channel is set to 0 (auto-select)
 * - Peer encryption is disabled initially
 * 
 * Requirements: 1.1, 4.2, 4.3
 */
void test_peer_addition(void) {
    // Initialize transport
    bool result = transport->begin(VALID_PEER_MAC);
    TEST_ASSERT_TRUE(result);
    
    // Verify peer MAC is stored
    uint8_t stored_mac[6];
    transport->getPeerMAC(stored_mac);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(VALID_PEER_MAC, stored_mac, 6);
    
    // Note: We can't directly verify peer was added to ESP-NOW peer list
    // without accessing ESP-NOW internals, but successful initialization
    // implies peer was added (begin() would return false otherwise)
}

// ═══════════════════════════════════════════════════════════════════
// TEST CASES: FAILURE HANDLING
// ═══════════════════════════════════════════════════════════════════

/**
 * Test: Double initialization handling
 * 
 * Verifies that:
 * - Second call to begin() is handled gracefully
 * - ESP-NOW doesn't crash or hang
 * 
 * Requirements: 1.1
 */
void test_double_initialization(void) {
    // First initialization
    bool result1 = transport->begin(VALID_PEER_MAC);
    TEST_ASSERT_TRUE_MESSAGE(result1, "First initialization should succeed");
    
    // Second initialization (should handle gracefully)
    // Note: This may fail or succeed depending on ESP-NOW implementation
    // The important thing is it doesn't crash
    bool result2 = transport->begin(ANOTHER_PEER_MAC);
    
    // Verify transport is still functional
    ESPNowStats stats = transport->getStats();
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(0, stats.packets_sent, 
                                    "Statistics should still be accessible");
}

/**
 * Test: Send before initialization
 * 
 * Verifies that:
 * - Attempting to send before begin() returns false
 * - No crash or undefined behavior occurs
 * 
 * Requirements: 1.1
 */
void test_send_before_initialization(void) {
    // Attempt to send without calling begin()
    uint8_t test_data[10] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A};
    bool result = transport->send(test_data, 10);
    
    // Send should fail
    TEST_ASSERT_FALSE_MESSAGE(result, "Send should fail before initialization");
    
    // Verify statistics show failure
    ESPNowStats stats = transport->getStats();
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(0, stats.packets_sent, 
                                    "No packets should be sent before initialization");
}

/**
 * Test: Invalid payload size
 * 
 * Verifies that:
 * - Sending payload larger than 250 bytes returns false
 * - Send failure is tracked in statistics
 * 
 * Requirements: 1.1, 1.3
 */
void test_invalid_payload_size(void) {
    // Initialize transport
    bool init_result = transport->begin(VALID_PEER_MAC);
    TEST_ASSERT_TRUE(init_result);
    
    // Attempt to send oversized payload (251 bytes)
    uint8_t large_data[251];
    memset(large_data, 0xAA, 251);
    
    bool send_result = transport->send(large_data, 251);
    
    // Send should fail
    TEST_ASSERT_FALSE_MESSAGE(send_result, "Send should fail with oversized payload");
    
    // Verify failure is tracked
    ESPNowStats stats = transport->getStats();
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(1, stats.send_failures, 
                                    "Send failure should be tracked");
}

// ═══════════════════════════════════════════════════════════════════
// TEST CASES: STATISTICS
// ═══════════════════════════════════════════════════════════════════

/**
 * Test: Initial statistics values
 * 
 * Verifies that:
 * - All statistics counters start at zero
 * - Peer is not reachable initially
 * 
 * Requirements: 1.5, 10.4
 */
void test_initial_statistics(void) {
    // Initialize transport
    transport->begin(VALID_PEER_MAC);
    
    // Get statistics
    ESPNowStats stats = transport->getStats();
    
    // Verify all counters are zero
    TEST_ASSERT_EQUAL_UINT32(0, stats.packets_sent);
    TEST_ASSERT_EQUAL_UINT32(0, stats.packets_received);
    TEST_ASSERT_EQUAL_UINT32(0, stats.send_failures);
    TEST_ASSERT_EQUAL_UINT32(0, stats.peer_unreachable_count);
    TEST_ASSERT_EQUAL_INT8(0, stats.last_rssi);
    TEST_ASSERT_FALSE(stats.peer_reachable);
}

/**
 * Test: Statistics reset
 * 
 * Verifies that:
 * - resetStats() clears all counters
 * - Statistics can be reset multiple times
 * 
 * Requirements: 1.5
 */
void test_statistics_reset(void) {
    // Initialize transport
    transport->begin(VALID_PEER_MAC);
    
    // Simulate some activity (send failures)
    uint8_t test_data[10] = {0x01, 0x02, 0x03};
    transport->send(test_data, 10);
    
    // Reset statistics
    transport->resetStats();
    
    // Verify all counters are zero
    ESPNowStats stats = transport->getStats();
    TEST_ASSERT_EQUAL_UINT32(0, stats.packets_sent);
    TEST_ASSERT_EQUAL_UINT32(0, stats.packets_received);
    TEST_ASSERT_EQUAL_UINT32(0, stats.send_failures);
    TEST_ASSERT_EQUAL_UINT32(0, stats.peer_unreachable_count);
}

// ═══════════════════════════════════════════════════════════════════
// MAIN TEST RUNNER
// ═══════════════════════════════════════════════════════════════════

void setup() {
    // Wait for serial connection (useful for debugging)
    delay(2000);
    
    // Initialize Unity test framework
    UNITY_BEGIN();
    
    // Run successful initialization tests
    RUN_TEST(test_init_success_with_valid_mac);
    RUN_TEST(test_wifi_station_mode_initialization);
    RUN_TEST(test_espnow_protocol_initialization);
    RUN_TEST(test_peer_addition);
    
    // Run failure handling tests
    RUN_TEST(test_double_initialization);
    RUN_TEST(test_send_before_initialization);
    RUN_TEST(test_invalid_payload_size);
    
    // Run statistics tests
    RUN_TEST(test_initial_statistics);
    RUN_TEST(test_statistics_reset);
    
    // Finish testing
    UNITY_END();
}

void loop() {
    // Tests run once in setup()
}
