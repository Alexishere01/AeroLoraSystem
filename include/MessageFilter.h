#ifndef MESSAGE_FILTER_H
#define MESSAGE_FILTER_H

#include <Arduino.h>

/**
 * @brief Filters MAVLink messages to determine which should be sent over LoRa
 * 
 * Only 8 essential MAVLink message types are sent over LoRa to reduce bandwidth:
 * - HEARTBEAT (0): System status, 1Hz
 * - ATTITUDE (30): Roll, pitch, yaw
 * - GLOBAL_POSITION_INT (33): Lat, lon, alt
 * - VFR_HUD (74): Airspeed, altitude
 * - COMMAND_LONG (76): Commands (ARM, DISARM, etc.)
 * - COMMAND_ACK (77): Command acknowledgments
 * - BATTERY_STATUS (147): Battery voltage, current
 * - STATUSTEXT (253): Status messages
 */
class MessageFilter {
private:
    // Essential message IDs
    static const uint8_t ESSENTIAL_MESSAGES[];
    static const uint8_t ESSENTIAL_COUNT = 8;
    
    // Statistics
    uint32_t _filtered_count;           // Total filtered messages
    uint32_t _filtered_by_id[256];      // Per-message-ID counts
    
public:
    /**
     * @brief Constructor - initializes statistics to zero
     */
    MessageFilter();
    
    /**
     * @brief Check if a MAVLink message ID is essential (should go over LoRa)
     * @param msgId MAVLink message ID to check
     * @return true if message is essential, false if it should be filtered
     */
    bool isEssential(uint8_t msgId);
    
    /**
     * @brief Get total count of filtered messages
     * @return Total number of messages filtered
     */
    uint32_t getFilteredCount() const { return _filtered_count; }
    
    /**
     * @brief Get count of filtered messages for a specific message ID
     * @param msgId MAVLink message ID
     * @return Number of times this message ID was filtered
     */
    uint32_t getFilteredCount(uint8_t msgId) const { return _filtered_by_id[msgId]; }
    
    /**
     * @brief Reset all filter statistics to zero
     */
    void resetStats();
};

#endif // MESSAGE_FILTER_H
