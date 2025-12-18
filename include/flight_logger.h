#ifndef FLIGHT_LOGGER_H
#define FLIGHT_LOGGER_H

#include <Arduino.h>
#include <LittleFS.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>

// Log Entry Structure for Queue
struct LogEntry {
    uint32_t seq;
    uint8_t msgId;
    uint8_t sysId;
    float rssi;
    float snr;
    bool relayActive;
    char event[16];      // Fixed size string
    uint16_t packetSize;
    uint32_t txTimestamp;
    uint8_t queueDepth;
    uint32_t errors;
    
    // Queue metrics (optional, can be 0 if not a metrics event)
    bool isMetrics;
    uint8_t t0_depth, t1_depth, t2_depth;
    uint32_t t0_full, t0_stale, t1_full, t1_stale, t2_full, t2_stale;
};

// Global Queue Handle
extern QueueHandle_t logQueue;

// Forward declaration of the task function
void loggingTask(void *pvParameters);

class FlightLogger {
public:
    FlightLogger(const char* filename) : _filename(filename), _enabled(false), _bootTime(0) {}
    
    /**
     * Initialize LittleFS, create log file, and start background task
     * @return true if successful
     */
    bool begin() {
        if (!LittleFS.begin(true)) {
            Serial.println("[LOGGER] ERROR: LittleFS mount failed!");
            Serial.println("[LOGGER] Try erasing flash or uploading filesystem image");
            return false;
        }
        
        #if DEBUG_LOGGING
        Serial.println("[LOGGER] LittleFS mounted");
        #endif
        _bootTime = millis();
        _enabled = true;
        
        // Open file in APPEND mode and keep it open
        _file = LittleFS.open(_filename, FILE_APPEND);
        if (!_file) {
            // If file doesn't exist, create it with header
            _file = LittleFS.open(_filename, FILE_WRITE);
            if (_file) {
                _file.println("timestamp_ms,sequence_number,message_id,system_id,rssi_dbm,snr_db,relay_active,event,packet_size,tx_timestamp,queue_depth,errors,tier0_depth,tier1_depth,tier2_depth,tier0_drops_full,tier0_drops_stale,tier1_drops_full,tier1_drops_stale,tier2_drops_full,tier2_drops_stale");
                _file.flush();
            }
        }
        
        if (_file) {
            #if DEBUG_LOGGING
            Serial.printf("[LOGGER] Log file opened: %s\n", _filename);
            #endif
        } else {
            #if DEBUG_LOGGING
            Serial.println("[LOGGER] Failed to create log file");
            #endif
            return false;
        }

        // Create FreeRTOS Queue
        logQueue = xQueueCreate(50, sizeof(LogEntry)); // Buffer 50 items
        if (logQueue == NULL) {
            #if DEBUG_LOGGING
            Serial.println("[LOGGER] Failed to create queue");
            #endif
            return false;
        }

        // Create Background Task on Core 0 (Radio/Main is on Core 1)
        xTaskCreatePinnedToCore(
            loggingTask,   // Task function
            "FlightLogger", // Name
            8192,          // Stack size (increased from 4096 to prevent overflow)
            (void*)this,   // Parameter (pass 'this' pointer)
            0,             // Priority (Low)
            NULL,          // Handle
            1              // Core 1 (Loop Core) - Move off Core 0 (WiFi/ESP-NOW)
        );

        return true;
    }
    
    /**
     * Log a packet event (Non-blocking: Pushes to Queue)
     */
    void logPacket(uint32_t seq, uint8_t msgId, uint8_t sysId, float rssi, float snr, 
                   bool relayActive, const char* event, uint16_t packetSize = 0, 
                   uint32_t txTimestamp = 0, uint8_t queueDepth = 0, uint32_t errors = 0) {
        if (!_enabled) return;
        
        LogEntry entry;
        entry.seq = seq;
        entry.msgId = msgId;
        entry.sysId = sysId;
        entry.rssi = rssi;
        entry.snr = snr;
        entry.relayActive = relayActive;
        strncpy(entry.event, event, sizeof(entry.event) - 1);
        entry.event[sizeof(entry.event) - 1] = '\0';
        entry.packetSize = packetSize;
        entry.txTimestamp = txTimestamp;
        entry.queueDepth = queueDepth;
        entry.errors = errors;
        entry.isMetrics = false;

        // Send to queue (Wait 0 ticks = Non-blocking drop if full)
        xQueueSend(logQueue, &entry, 0);
    }
    
    /**
     * Log queue metrics (Non-blocking: Pushes to Queue)
     */
    void logQueueMetrics(uint8_t tier0_depth, uint8_t tier1_depth, uint8_t tier2_depth,
                        uint32_t tier0_drops_full, uint32_t tier0_drops_stale,
                        uint32_t tier1_drops_full, uint32_t tier1_drops_stale,
                        uint32_t tier2_drops_full, uint32_t tier2_drops_stale) {
        if (!_enabled) return;
        
        LogEntry entry;
        entry.isMetrics = true;
        strcpy(entry.event, "QUEUE_METRICS");
        entry.t0_depth = tier0_depth;
        entry.t1_depth = tier1_depth;
        entry.t2_depth = tier2_depth;
        entry.t0_full = tier0_drops_full;
        entry.t0_stale = tier0_drops_stale;
        entry.t1_full = tier1_drops_full;
        entry.t1_stale = tier1_drops_stale;
        entry.t2_full = tier2_drops_full;
        entry.t2_stale = tier2_drops_stale;

        xQueueSend(logQueue, &entry, 0);
    }

    /**
     * Log relay event (Compatibility wrapper)
     */
    void logRelayEvent(const char* event, uint32_t overheard, uint32_t forwarded, float rssi, uint32_t errors) {
        // Map relay stats to standard log packet fields
        // seq -> overheard count
        // txTimestamp -> forwarded count
        logPacket(overheard, 0, 0, rssi, 0, true, event, 0, forwarded, 0, errors);
    }
    
    // Internal method for the task to call
    void writeEntryToFile(const LogEntry& entry) {
        if (!_file) return;
        
        if (entry.isMetrics) {
             _file.print(millis() - _bootTime);
             _file.print(",0,0,0,0.0,0.0,0,QUEUE_METRICS,0,0,0,0,");
             _file.print(entry.t0_depth); _file.print(",");
             _file.print(entry.t1_depth); _file.print(",");
             _file.print(entry.t2_depth); _file.print(",");
             _file.print(entry.t0_full); _file.print(",");
             _file.print(entry.t0_stale); _file.print(",");
             _file.print(entry.t1_full); _file.print(",");
             _file.print(entry.t1_stale); _file.print(",");
             _file.print(entry.t2_full); _file.print(",");
             _file.println(entry.t2_stale);
        } else {
            _file.print(millis() - _bootTime); _file.print(",");
            _file.print(entry.seq); _file.print(",");
            _file.print(entry.msgId); _file.print(",");
            _file.print(entry.sysId); _file.print(",");
            _file.print(entry.rssi, 1); _file.print(",");
            _file.print(entry.snr, 1); _file.print(",");
            _file.print(entry.relayActive ? 1 : 0); _file.print(",");
            _file.print(entry.event); _file.print(",");
            _file.print(entry.packetSize); _file.print(",");
            _file.print(entry.txTimestamp); _file.print(",");
            _file.print(entry.queueDepth); _file.print(",");
            _file.print(entry.errors);
            _file.println(",0,0,0,0,0,0,0,0,0");
        }
    }

    void flush() {
        if (_file) _file.flush();
    }
    
    void close() {
        if (_file) {
            _file.close();
            _enabled = false;
            #if DEBUG_LOGGING
            Serial.println("[LOGGER] File closed safely");
            #endif
        }
    }
    
    bool isEnabled() { return _enabled; }
    
    unsigned long getBootTime() { return _bootTime; }

    /**
     * Dump entire log file to USB Serial (Watchdog Safe)
     */
    void dumpToSerial() {
        // Close file first to ensure everything is written
        if (_file) _file.close();
        
        Serial.println("\n========== LOG DUMP START ==========");
        
        File file = LittleFS.open(_filename, FILE_READ);
        if (file) {
            uint32_t bytesRead = 0;
            while (file.available()) {
                Serial.write(file.read());
                bytesRead++;
                // Feed watchdog every 64 bytes
                if (bytesRead % 64 == 0) {
                    yield();
                }
            }
            file.close();
        } else {
            Serial.println("ERROR: Log file not found");
        }
        
        Serial.println("========== LOG DUMP END ==========\n");
        
        // Re-open for appending if we were enabled
        if (_enabled) {
            _file = LittleFS.open(_filename, FILE_APPEND);
        }
    }
    
    /**
     * Clear log file
     */
    void clearLog() {
        if (_file) _file.close();
        
        LittleFS.remove(_filename);
        Serial.printf("[LOGGER] Cleared log: %s\n", _filename);
        
        // Re-create and keep open
        _file = LittleFS.open(_filename, FILE_WRITE);
        if (_file) {
            _file.println("timestamp_ms,sequence_number,message_id,system_id,rssi_dbm,snr_db,relay_active,event,packet_size,tx_timestamp,queue_depth,errors,tier0_depth,tier1_depth,tier2_depth,tier0_drops_full,tier0_drops_stale,tier1_drops_full,tier1_drops_stale,tier2_drops_full,tier2_drops_stale");
            _file.flush();
        }
    }
    
    size_t getLogSize() {
        // Flush first to get accurate size
        if (_file) _file.flush();
        
        File file = LittleFS.open(_filename, FILE_READ);
        if (file) {
            size_t size = file.size();
            file.close();
            return size;
        }
        return 0;
    }
    
    uint32_t getLogLines() {
        if (_file) _file.flush();
        
        File file = LittleFS.open(_filename, FILE_READ);
        if (file) {
            uint32_t lines = 0;
            while (file.available()) {
                if (file.read() == '\n') lines++;
                if (lines % 10 == 0) yield(); // Safety
            }
            file.close();
            return lines;
        }
        return 0;
    }
    
    void handleSerialCommands() {
        if (Serial.available()) {
            String cmd = Serial.readStringUntil('\n');
            cmd.trim();
            cmd.toUpperCase();
            
            if (cmd == "DUMP") {
                dumpToSerial();
            }
            else if (cmd == "SIZE") {
                Serial.printf("Log size: %d bytes (%d lines)\n", getLogSize(), getLogLines());
            }
            else if (cmd == "CLEAR") {
                clearLog();
                Serial.println("Log cleared");
            }
            else if (cmd == "HELP") {
                Serial.println("DUMP, SIZE, CLEAR, HELP");
            }
        }
    }

private:
    const char* _filename;
    bool _enabled;
    unsigned long _bootTime;
    File _file;  // Keep file handle open
};

// Global Queue Handle
extern QueueHandle_t logQueue;

// Forward declaration of the task function
void loggingTask(void *pvParameters);

#endif // FLIGHT_LOGGER_H
