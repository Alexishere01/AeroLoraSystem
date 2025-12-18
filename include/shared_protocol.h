/**
 * Shared UART Protocol for Primary-Secondary Node Communication
 * 
 * This protocol is used for UART communication between primary and secondary nodes
 * in a relay configuration. It is separate from the AeroLoRa protocol which handles
 * LoRa radio communication.
 * 
 * Purpose:
 * - Enable relay mode where secondary node forwards LoRa packets to primary node
 * - Exchange status information between nodes
 * - Coordinate relay activation/deactivation
 * 
 * Note: This is NOT the AeroLoRa protocol. The AeroLoRa protocol handles LoRa
 * radio communication with hardware CRC and priority queuing. This protocol
 * handles UART communication between nodes with Fletcher-16 checksums.
 */

#pragma once
#include <Arduino.h>

// This start byte is used to mark the beginning of a new packet frame.
#define PACKET_START_BYTE 0xAA

/**
 * @brief Defines the type of command being sent over UART.
 * This replaces the "cmd" field from the old JSON protocol.
 */
enum UartCommand : uint8_t {
    CMD_NONE = 0x00,
    CMD_INIT = 0x01,              // Primary -> Secondary: Sent on startup
    CMD_ACK = 0x02,               // Generic acknowledgment
    CMD_RELAY_ACTIVATE = 0x03,    // Primary -> Secondary: Activate/deactivate relay mode
    CMD_RELAY_TX = 0x04,          // Primary -> Secondary: Request to transmit a LoRa packet
    CMD_RELAY_RX = 0x05,          // Secondary -> Primary: A LoRa packet was received via relay
    CMD_STATUS_REPORT = 0x06,     // Secondary -> Primary: Periodic status update
    CMD_STATUS_REQUEST = 0x07     // Primary -> Secondary: Request an immediate status update
};

/**
 * @brief Payload for a status report (CMD_STATUS_REPORT).
 * Contains the secondary node's operational status.
 */
struct __attribute__((packed)) StatusPayload {
    bool relayActive;
    float lastRSSI;
    float lastSNR;
    uint32_t packetsRelayed;
};

/**
 * @brief Payload for a received relay packet (CMD_RELAY_RX).
 * Contains the LoRa link metrics along with the packet data.
 */
struct __attribute__((packed)) RelayRxPayload {
    float rssi;
    float snr;
    uint8_t data[245]; // Max LoRa data that fits with RSSI/SNR
};


/**
 * @brief The main UART packet structure for all communication.
 * This is a fixed-size header followed by a variable-length payload.
 */
struct __attribute__((packed)) UartPacket {
    uint8_t startByte;
    UartCommand command;
    uint16_t length;
    uint8_t payload[255]; // Max LoRa packet size
    uint16_t checksum;
};

/**
 * @brief Calculates the Fletcher-16 checksum, which is more robust than a simple sum.
 * Defined as 'inline' here to ensure both primary and secondary nodes compile
 * the exact same function, preventing linker errors and mismatches.
 * @param data Pointer to the data buffer.
 * @param len The number of bytes to process.
 * @return The 16-bit checksum.
 */
inline uint16_t fletcher16(const uint8_t* data, size_t len) {
    uint16_t sum1 = 0;
    uint16_t sum2 = 0;
    for (size_t i = 0; i < len; ++i) {
        sum1 = (sum1 + data[i]) % 255;
        sum2 = (sum2 + sum1) % 255;
    }
    return (sum2 << 8) | sum1;
}

