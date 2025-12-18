#include <unity.h>
#include "MessageFilter.h"

MessageFilter* filter;

void setUp(void) {
    // Create a fresh filter instance for each test
    filter = new MessageFilter();
}

void tearDown(void) {
    // Clean up after each test
    delete filter;
}

/**
 * Test that all 8 essential message types pass the filter
 * Requirements: 2.1, 2.2
 */
void test_essential_messages_pass_filter(void) {
    // Test HEARTBEAT (0)
    TEST_ASSERT_TRUE(filter->isEssential(0));
    
    // Test ATTITUDE (30)
    TEST_ASSERT_TRUE(filter->isEssential(30));
    
    // Test GLOBAL_POSITION_INT (33)
    TEST_ASSERT_TRUE(filter->isEssential(33));
    
    // Test VFR_HUD (74)
    TEST_ASSERT_TRUE(filter->isEssential(74));
    
    // Test COMMAND_LONG (76)
    TEST_ASSERT_TRUE(filter->isEssential(76));
    
    // Test COMMAND_ACK (77)
    TEST_ASSERT_TRUE(filter->isEssential(77));
    
    // Test BATTERY_STATUS (147)
    TEST_ASSERT_TRUE(filter->isEssential(147));
    
    // Test STATUSTEXT (253)
    TEST_ASSERT_TRUE(filter->isEssential(253));
}

/**
 * Test that non-essential messages are filtered
 * Requirements: 2.1, 2.2
 */
void test_non_essential_messages_filtered(void) {
    // Test some common non-essential message types
    
    // PARAM_VALUE (22) - parameter values
    TEST_ASSERT_FALSE(filter->isEssential(22));
    
    // GPS_RAW_INT (24) - raw GPS data
    TEST_ASSERT_FALSE(filter->isEssential(24));
    
    // MISSION_ITEM (39) - mission waypoints
    TEST_ASSERT_FALSE(filter->isEssential(39));
    
    // RC_CHANNELS (65) - RC input channels
    TEST_ASSERT_FALSE(filter->isEssential(65));
    
    // SERVO_OUTPUT_RAW (36) - servo outputs
    TEST_ASSERT_FALSE(filter->isEssential(36));
    
    // SYS_STATUS (1) - system status (not in essential list)
    TEST_ASSERT_FALSE(filter->isEssential(1));
    
    // MISSION_COUNT (44) - mission count
    TEST_ASSERT_FALSE(filter->isEssential(44));
    
    // PARAM_REQUEST_LIST (21) - request parameter list
    TEST_ASSERT_FALSE(filter->isEssential(21));
}

/**
 * Test that filter statistics are accurate for total filtered count
 * Requirements: 2.1, 2.2
 */
void test_filter_statistics_total_count(void) {
    // Initially, no messages should be filtered
    TEST_ASSERT_EQUAL_UINT32(0, filter->getFilteredCount());
    
    // Filter some non-essential messages
    filter->isEssential(22);  // PARAM_VALUE
    TEST_ASSERT_EQUAL_UINT32(1, filter->getFilteredCount());
    
    filter->isEssential(24);  // GPS_RAW_INT
    TEST_ASSERT_EQUAL_UINT32(2, filter->getFilteredCount());
    
    filter->isEssential(39);  // MISSION_ITEM
    TEST_ASSERT_EQUAL_UINT32(3, filter->getFilteredCount());
    
    // Essential messages should NOT increment filtered count
    filter->isEssential(0);   // HEARTBEAT
    TEST_ASSERT_EQUAL_UINT32(3, filter->getFilteredCount());
    
    filter->isEssential(76);  // COMMAND_LONG
    TEST_ASSERT_EQUAL_UINT32(3, filter->getFilteredCount());
    
    // More non-essential messages
    filter->isEssential(65);  // RC_CHANNELS
    TEST_ASSERT_EQUAL_UINT32(4, filter->getFilteredCount());
}

/**
 * Test that per-message-ID statistics are accurate
 * Requirements: 2.1, 2.2
 */
void test_filter_statistics_per_message_id(void) {
    // Initially, all per-ID counts should be zero
    TEST_ASSERT_EQUAL_UINT32(0, filter->getFilteredCount(22));
    TEST_ASSERT_EQUAL_UINT32(0, filter->getFilteredCount(24));
    
    // Filter PARAM_VALUE (22) three times
    filter->isEssential(22);
    filter->isEssential(22);
    filter->isEssential(22);
    TEST_ASSERT_EQUAL_UINT32(3, filter->getFilteredCount(22));
    
    // Filter GPS_RAW_INT (24) twice
    filter->isEssential(24);
    filter->isEssential(24);
    TEST_ASSERT_EQUAL_UINT32(2, filter->getFilteredCount(24));
    
    // Filter MISSION_ITEM (39) once
    filter->isEssential(39);
    TEST_ASSERT_EQUAL_UINT32(1, filter->getFilteredCount(39));
    
    // Total filtered count should be 6
    TEST_ASSERT_EQUAL_UINT32(6, filter->getFilteredCount());
    
    // Essential messages should have zero filtered count
    filter->isEssential(0);   // HEARTBEAT
    filter->isEssential(30);  // ATTITUDE
    filter->isEssential(76);  // COMMAND_LONG
    TEST_ASSERT_EQUAL_UINT32(0, filter->getFilteredCount(0));
    TEST_ASSERT_EQUAL_UINT32(0, filter->getFilteredCount(30));
    TEST_ASSERT_EQUAL_UINT32(0, filter->getFilteredCount(76));
    
    // Total should still be 6
    TEST_ASSERT_EQUAL_UINT32(6, filter->getFilteredCount());
}

/**
 * Test that resetStats() clears all statistics
 * Requirements: 2.1, 2.2
 */
void test_reset_statistics(void) {
    // Filter some messages to build up statistics
    filter->isEssential(22);  // PARAM_VALUE
    filter->isEssential(22);
    filter->isEssential(24);  // GPS_RAW_INT
    filter->isEssential(39);  // MISSION_ITEM
    
    // Verify statistics are non-zero
    TEST_ASSERT_EQUAL_UINT32(4, filter->getFilteredCount());
    TEST_ASSERT_EQUAL_UINT32(2, filter->getFilteredCount(22));
    TEST_ASSERT_EQUAL_UINT32(1, filter->getFilteredCount(24));
    TEST_ASSERT_EQUAL_UINT32(1, filter->getFilteredCount(39));
    
    // Reset statistics
    filter->resetStats();
    
    // Verify all statistics are now zero
    TEST_ASSERT_EQUAL_UINT32(0, filter->getFilteredCount());
    TEST_ASSERT_EQUAL_UINT32(0, filter->getFilteredCount(22));
    TEST_ASSERT_EQUAL_UINT32(0, filter->getFilteredCount(24));
    TEST_ASSERT_EQUAL_UINT32(0, filter->getFilteredCount(39));
}

/**
 * Test edge cases: message ID 0 and 255
 * Requirements: 2.1, 2.2
 */
void test_edge_case_message_ids(void) {
    // Message ID 0 (HEARTBEAT) is essential
    TEST_ASSERT_TRUE(filter->isEssential(0));
    TEST_ASSERT_EQUAL_UINT32(0, filter->getFilteredCount());
    
    // Message ID 255 is not essential (only 253 STATUSTEXT is)
    TEST_ASSERT_FALSE(filter->isEssential(255));
    TEST_ASSERT_EQUAL_UINT32(1, filter->getFilteredCount());
    TEST_ASSERT_EQUAL_UINT32(1, filter->getFilteredCount(255));
}

/**
 * Test that filtering the same message multiple times increments correctly
 * Requirements: 2.1, 2.2
 */
void test_repeated_filtering(void) {
    // Filter the same non-essential message 100 times
    for (int i = 0; i < 100; i++) {
        filter->isEssential(22);  // PARAM_VALUE
    }
    
    TEST_ASSERT_EQUAL_UINT32(100, filter->getFilteredCount());
    TEST_ASSERT_EQUAL_UINT32(100, filter->getFilteredCount(22));
    
    // Check an essential message 50 times
    for (int i = 0; i < 50; i++) {
        filter->isEssential(0);  // HEARTBEAT
    }
    
    // Total should still be 100 (essential messages don't increment)
    TEST_ASSERT_EQUAL_UINT32(100, filter->getFilteredCount());
    TEST_ASSERT_EQUAL_UINT32(0, filter->getFilteredCount(0));
}

void setup() {
    delay(2000);  // Wait for serial monitor
    
    UNITY_BEGIN();
    
    RUN_TEST(test_essential_messages_pass_filter);
    RUN_TEST(test_non_essential_messages_filtered);
    RUN_TEST(test_filter_statistics_total_count);
    RUN_TEST(test_filter_statistics_per_message_id);
    RUN_TEST(test_reset_statistics);
    RUN_TEST(test_edge_case_message_ids);
    RUN_TEST(test_repeated_filtering);
    
    UNITY_END();
}

void loop() {
    // Nothing to do here
}
