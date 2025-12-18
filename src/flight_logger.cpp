#include "flight_logger.h"

// Define global queue handle
QueueHandle_t logQueue;

// Task Implementation
void loggingTask(void *pvParameters) {
    FlightLogger* logger = (FlightLogger*)pvParameters;
    LogEntry entry;
    
    // Flush timer
    unsigned long lastFlush = millis();
    const unsigned long FLUSH_INTERVAL = 5000; // Flush every 5 seconds
    
    // Safety timeout (auto-close after 5 minutes of operation)
    // This prevents corruption if power is pulled after a flight
    const unsigned long SAFETY_TIMEOUT = 5 * 60 * 1000; 

    while (true) {
        // Wait for data with short timeout (100ms) to allow periodic tasks
        if (xQueueReceive(logQueue, &entry, pdMS_TO_TICKS(100)) == pdTRUE) {
            logger->writeEntryToFile(entry);
        }
        
        // Check if we need to flush
        unsigned long now = millis();
        if (now - lastFlush > FLUSH_INTERVAL) {
            logger->flush();
            lastFlush = now;
        }
        
        // Check safety timeout
        if (logger->isEnabled() && (now - logger->getBootTime() > SAFETY_TIMEOUT)) {
            logger->close();
            #if DEBUG_LOGGING
            Serial.println("[LOGGER] Safety timeout reached - File closed");
            #endif
        }
    }
}
