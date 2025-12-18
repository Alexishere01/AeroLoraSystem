#include "MessageFilter.h"

// Define the 8 essential MAVLink message types
const uint8_t MessageFilter::ESSENTIAL_MESSAGES[] = {
    0,    // HEARTBEAT - System status, 1Hz
    30,   // ATTITUDE - Roll, pitch, yaw
    33,   // GLOBAL_POSITION_INT - Lat, lon, alt
    74,   // VFR_HUD - Airspeed, altitude
    76,   // COMMAND_LONG - Commands (ARM, DISARM, etc.)
    77,   // COMMAND_ACK - Command acknowledgments
    147,  // BATTERY_STATUS - Battery voltage, current
    253   // STATUSTEXT - Status messages
};

MessageFilter::MessageFilter() {
    resetStats();
}

bool MessageFilter::isEssential(uint8_t msgId) {
    // Check if message ID is in the essential list
    for (uint8_t i = 0; i < ESSENTIAL_COUNT; i++) {
        if (ESSENTIAL_MESSAGES[i] == msgId) {
            return true;  // Essential message - should be sent over LoRa
        }
    }
    
    // Not essential - count it as filtered
    _filtered_count++;
    _filtered_by_id[msgId]++;
    
    return false;  // Non-essential - should be filtered from LoRa
}

void MessageFilter::resetStats() {
    _filtered_count = 0;
    
    // Reset all per-message-ID counts
    for (uint16_t i = 0; i < 256; i++) {
        _filtered_by_id[i] = 0;
    }
}
