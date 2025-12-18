"""
Binary Protocol Parser for Telemetry Validation System

This module implements a parser for the custom binary UART protocol used
between the Primary and Secondary controllers in the dual-controller LoRa
relay system. The protocol wraps MAVLink packets in BridgePayload structures
with RSSI/SNR metadata.

Protocol Specification:
- Start byte: 0xAA
- Command: 1 byte (UartCommand enum)
- Length: 2 bytes (little-endian, 0-255)
- Payload: 0-255 bytes (variable)
- Checksum: 2 bytes (Fletcher-16, little-endian)

Requirements: 1.2, 2.1, 8.1
"""

import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, List, Dict, Any


# Protocol constants
PACKET_START_BYTE = 0xAA
PROTOCOL_VERSION_1_0 = 0x0100
MAX_PAYLOAD_SIZE = 255
MAX_MAVLINK_DATA_SIZE = 245


class UartCommand(IntEnum):
    """
    Defines the type of command being sent over UART.
    Ported from C++ enum in shared_protocol.h
    """
    CMD_NONE = 0x00
    CMD_INIT = 0x01                 # Primary -> Secondary: Sent on startup
    CMD_ACK = 0x02                  # Generic acknowledgment
    CMD_RELAY_ACTIVATE = 0x03       # Primary -> Secondary: Activate/deactivate relay mode
    CMD_RELAY_TX = 0x04             # Primary -> Secondary: Request to transmit a LoRa packet
    CMD_RELAY_RX = 0x05             # Secondary -> Primary: A LoRa packet was received via relay
    CMD_BRIDGE_TX = 0x06            # Primary -> Secondary: Bridge packet from GCS to mesh
    CMD_BRIDGE_RX = 0x07            # Secondary -> Primary: Bridge packet from mesh to GCS
    CMD_STATUS_REPORT = 0x08        # Secondary -> Primary: Periodic status update
    CMD_BROADCAST_RELAY_REQ = 0x09  # Primary -> Secondary: Broadcast relay request
    CMD_STATUS_REQUEST = 0x0A       # Primary -> Secondary: Request an immediate status update


@dataclass
class InitPayload:
    """
    Payload for initialization (CMD_INIT).
    Sent by Primary to Secondary on startup to establish communication.
    
    C++ struct size: 16 + 4 + 4 + 4 = 28 bytes
    """
    mode: str                    # Operating mode: "FREQUENCY_BRIDGE", "RELAY", etc. (16 bytes)
    primary_freq: float          # Primary frequency in MHz (4 bytes)
    secondary_freq: float        # Secondary frequency in MHz (4 bytes)
    timestamp: int               # Milliseconds since boot (4 bytes, uint32_t)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'InitPayload':
        """Parse InitPayload from binary data"""
        if len(data) < 28:
            raise ValueError(f"InitPayload requires 28 bytes, got {len(data)}")
        
        # mode: 16 bytes (null-terminated string)
        mode_bytes = data[0:16]
        mode = mode_bytes.split(b'\x00')[0].decode('utf-8', errors='ignore')
        
        # primary_freq: 4 bytes (float, little-endian)
        primary_freq = struct.unpack('<f', data[16:20])[0]
        
        # secondary_freq: 4 bytes (float, little-endian)
        secondary_freq = struct.unpack('<f', data[20:24])[0]
        
        # timestamp: 4 bytes (uint32_t, little-endian)
        timestamp = struct.unpack('<I', data[24:28])[0]
        
        return cls(mode, primary_freq, secondary_freq, timestamp)


@dataclass
class BridgePayload:
    """
    Payload for bridge commands (CMD_BRIDGE_TX and CMD_BRIDGE_RX).
    Contains MAVLink packet data with link metrics.
    
    C++ struct size: 1 + 4 + 4 + 2 + 245 = 256 bytes (max)
    Actual size varies based on data_len
    """
    system_id: int               # MAVLink system ID (0 if unknown) (1 byte, uint8_t)
    rssi: float                  # RSSI in dBm (4 bytes)
    snr: float                   # SNR in dB (4 bytes)
    data_len: int                # Length of MAVLink data (2 bytes, uint16_t)
    data: bytes                  # Raw MAVLink packet (max 245 bytes)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'BridgePayload':
        """Parse BridgePayload from binary data"""
        if len(data) < 11:
            raise ValueError(f"BridgePayload requires at least 11 bytes, got {len(data)}")
        
        # system_id: 1 byte (uint8_t)
        system_id = data[0]
        
        # rssi: 4 bytes (float, little-endian)
        rssi = struct.unpack('<f', data[1:5])[0]
        
        # snr: 4 bytes (float, little-endian)
        snr = struct.unpack('<f', data[5:9])[0]
        
        # data_len: 2 bytes (uint16_t, little-endian)
        data_len = struct.unpack('<H', data[9:11])[0]
        
        # Validate data_len
        if data_len > MAX_MAVLINK_DATA_SIZE:
            raise ValueError(f"BridgePayload data_len {data_len} exceeds max {MAX_MAVLINK_DATA_SIZE}")
        
        # data: variable length (up to 245 bytes)
        if len(data) < 11 + data_len:
            raise ValueError(f"BridgePayload data truncated: expected {11 + data_len} bytes, got {len(data)}")
        
        mavlink_data = data[11:11 + data_len]
        
        return cls(system_id, rssi, snr, data_len, mavlink_data)


@dataclass
class StatusPayload:
    """
    Payload for a status report (CMD_STATUS_REPORT).
    Contains the secondary node's operational status.
    
    C++ struct size: 1 + 1 + 4*10 + 4 + 4 + 4 + 1 = 55 bytes
    """
    relay_active: bool                      # 1 byte
    own_drone_sysid: int                    # 1 byte (uint8_t)
    packets_relayed: int                    # 4 bytes (uint32_t)
    bytes_relayed: int                      # 4 bytes (uint32_t)
    mesh_to_uart_packets: int               # 4 bytes (uint32_t)
    uart_to_mesh_packets: int               # 4 bytes (uint32_t)
    mesh_to_uart_bytes: int                 # 4 bytes (uint32_t)
    uart_to_mesh_bytes: int                 # 4 bytes (uint32_t)
    bridge_gcs_to_mesh_packets: int         # 4 bytes (uint32_t)
    bridge_mesh_to_gcs_packets: int         # 4 bytes (uint32_t)
    bridge_gcs_to_mesh_bytes: int           # 4 bytes (uint32_t)
    bridge_mesh_to_gcs_bytes: int           # 4 bytes (uint32_t)
    rssi: float                             # 4 bytes
    snr: float                              # 4 bytes
    last_activity_sec: int                  # 4 bytes (uint32_t)
    active_peer_relays: int                 # 1 byte (uint8_t)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'StatusPayload':
        """Parse StatusPayload from binary data"""
        if len(data) < 55:
            raise ValueError(f"StatusPayload requires 55 bytes, got {len(data)}")
        
        # Unpack all fields using struct
        # Format: B B I I I I I I I I I I f f I B
        values = struct.unpack('<BB10IffIB', data[0:55])
        
        return cls(
            relay_active=bool(values[0]),
            own_drone_sysid=values[1],
            packets_relayed=values[2],
            bytes_relayed=values[3],
            mesh_to_uart_packets=values[4],
            uart_to_mesh_packets=values[5],
            mesh_to_uart_bytes=values[6],
            uart_to_mesh_bytes=values[7],
            bridge_gcs_to_mesh_packets=values[8],
            bridge_mesh_to_gcs_packets=values[9],
            bridge_gcs_to_mesh_bytes=values[10],
            bridge_mesh_to_gcs_bytes=values[11],
            rssi=values[12],
            snr=values[13],
            last_activity_sec=values[14],
            active_peer_relays=values[15]
        )


@dataclass
class RelayActivatePayload:
    """
    Payload for relay activation (CMD_RELAY_ACTIVATE).
    Controls whether relay mode is active or inactive.
    
    C++ struct size: 1 byte
    """
    activate: bool               # true = activate, false = deactivate (1 byte)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'RelayActivatePayload':
        """Parse RelayActivatePayload from binary data"""
        if len(data) < 1:
            raise ValueError(f"RelayActivatePayload requires 1 byte, got {len(data)}")
        
        activate = bool(data[0])
        return cls(activate)


@dataclass
class RelayRequestPayload:
    """
    Payload for broadcast relay request (CMD_BROADCAST_RELAY_REQ).
    Requests relay activation with link quality metrics.
    
    C++ struct size: 4 + 4 + 4 = 12 bytes
    """
    rssi: float                  # 4 bytes
    snr: float                   # 4 bytes
    packet_loss: float           # 4 bytes
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'RelayRequestPayload':
        """Parse RelayRequestPayload from binary data"""
        if len(data) < 12:
            raise ValueError(f"RelayRequestPayload requires 12 bytes, got {len(data)}")
        
        # Unpack three floats (little-endian)
        rssi, snr, packet_loss = struct.unpack('<fff', data[0:12])
        
        return cls(rssi, snr, packet_loss)


@dataclass
class RelayRxPayload:
    """
    Payload for a received relay packet (CMD_RELAY_RX and CMD_RELAY_TX).
    Contains the LoRa link metrics along with the packet data.
    
    C++ struct size: 4 + 4 + 245 = 253 bytes (max)
    Actual size varies based on data length
    """
    rssi: float                  # 4 bytes
    snr: float                   # 4 bytes
    data: bytes                  # Max 245 bytes
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'RelayRxPayload':
        """Parse RelayRxPayload from binary data"""
        if len(data) < 8:
            raise ValueError(f"RelayRxPayload requires at least 8 bytes, got {len(data)}")
        
        # rssi: 4 bytes (float, little-endian)
        rssi = struct.unpack('<f', data[0:4])[0]
        
        # snr: 4 bytes (float, little-endian)
        snr = struct.unpack('<f', data[4:8])[0]
        
        # data: remaining bytes (up to 245 bytes)
        relay_data = data[8:]
        
        if len(relay_data) > MAX_MAVLINK_DATA_SIZE:
            raise ValueError(f"RelayRxPayload data length {len(relay_data)} exceeds max {MAX_MAVLINK_DATA_SIZE}")
        
        return cls(rssi, snr, relay_data)


@dataclass
class ParsedBinaryPacket:
    """
    Represents a parsed binary protocol packet with all metadata.
    
    Requirements: 1.2, 2.1, 8.1
    """
    timestamp: float                        # Python timestamp (seconds since epoch)
    command: UartCommand                    # Command type
    payload: Optional[Any]                  # Parsed payload object (type depends on command)
    raw_bytes: bytes                        # Complete raw packet including headers and checksum
    payload_bytes: bytes = b''              # Raw payload bytes only
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return (f"ParsedBinaryPacket(timestamp={self.timestamp:.3f}, "
                f"command={self.command.name}, "
                f"payload_type={type(self.payload).__name__}, "
                f"raw_size={len(self.raw_bytes)} bytes)")


def fletcher16(data: bytes) -> int:
    """
    Calculate Fletcher-16 checksum.
    
    This is a more robust checksum than a simple sum, providing better
    error detection. Ported from C++ implementation in shared_protocol.h
    
    Args:
        data: Bytes to calculate checksum over
        
    Returns:
        16-bit checksum value
        
    Requirements: 1.5, 3.1
    """
    sum1 = 0
    sum2 = 0
    
    for byte in data:
        sum1 = (sum1 + byte) % 255
        sum2 = (sum2 + sum1) % 255
    
    return (sum2 << 8) | sum1


def validate_checksum(packet_data: bytes, expected_checksum: int) -> bool:
    """
    Validate Fletcher-16 checksum for a packet.
    
    Args:
        packet_data: Packet data (header + payload, excluding checksum bytes)
        expected_checksum: Expected checksum value from packet
        
    Returns:
        True if checksum is valid, False otherwise
        
    Requirements: 2.5, 3.1
    """
    calculated = fletcher16(packet_data)
    return calculated == expected_checksum



class RxState(IntEnum):
    """
    Receive state machine states for binary packet reception.
    Ported from C++ enum in BinaryProtocol.h
    
    Requirements: 2.1, 2.2, 2.5, 6.1
    """
    WAIT_START = 0      # Waiting for start byte (0xAA)
    READ_HEADER = 1     # Reading command and length fields
    READ_PAYLOAD = 2    # Reading payload bytes
    READ_CHECKSUM = 3   # Reading checksum bytes
    VALIDATE = 4        # Validating and processing packet


class BinaryProtocolParser:
    """
    State machine-based parser for binary UART protocol packets.
    
    This parser processes incoming byte streams and extracts complete,
    validated binary protocol packets. It maintains internal state to
    handle partial packets and implements timeout detection.
    
    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.2, 3.3, 6.2, 6.3
    """
    
    def __init__(self, timeout_ms: int = 100):
        """
        Initialize the binary protocol parser.
        
        Args:
            timeout_ms: Timeout in milliseconds for incomplete packets
        """
        self.state = RxState.WAIT_START
        self.buffer = bytearray()
        self.bytes_received = 0
        self.last_byte_time = 0.0
        self.timeout_ms = timeout_ms / 1000.0  # Convert to seconds
        
        # Statistics
        self.stats = {
            'packets_received': 0,
            'checksum_errors': 0,
            'parse_errors': 0,
            'timeout_errors': 0,
            'unknown_commands': 0,
            'buffer_overflow': 0,
            'bytes_received': 0
        }
        
        # Packet buffer (max packet size: 1 + 1 + 2 + 255 + 2 = 261 bytes)
        self.max_packet_size = 261
        self.buffer = bytearray(self.max_packet_size)
    
    def parse_stream(self, data: bytes) -> List[ParsedBinaryPacket]:
        """
        Parse incoming data stream and return list of complete, validated packets.
        
        This method implements a state machine that processes bytes one at a time,
        accumulating data until a complete packet is received and validated.
        
        Args:
            data: Incoming byte stream from UART or network connection
            
        Returns:
            List of successfully parsed and validated packets
            
        Requirements: 2.1, 2.2, 2.5
        """
        packets = []
        now = time.time()
        
        for byte in data:
            # Timeout detection - reset if no data for timeout period
            if self.state != RxState.WAIT_START and self.last_byte_time > 0:
                if (now - self.last_byte_time) > self.timeout_ms:
                    self.stats['timeout_errors'] += 1
                    self._reset_state()
            
            self.last_byte_time = now
            
            # State machine processing
            if self.state == RxState.WAIT_START:
                # Look for start byte (0xAA)
                if byte == PACKET_START_BYTE:
                    self.buffer[0] = byte
                    self.bytes_received = 1
                    self.state = RxState.READ_HEADER
            
            elif self.state == RxState.READ_HEADER:
                # Read command (byte 1) and length (bytes 2-3)
                self.buffer[self.bytes_received] = byte
                self.bytes_received += 1
                
                if self.bytes_received == 4:
                    # Extract length from bytes 2-3 (little-endian)
                    payload_len = self.buffer[2] | (self.buffer[3] << 8)
                    
                    # Validate packet length
                    if payload_len > MAX_PAYLOAD_SIZE:
                        self.stats['parse_errors'] += 1
                        self._reset_state()
                    elif payload_len == 0:
                        # No payload - go straight to checksum
                        self.state = RxState.READ_CHECKSUM
                    else:
                        # Has payload - read it
                        self.state = RxState.READ_PAYLOAD
            
            elif self.state == RxState.READ_PAYLOAD:
                # Accumulate payload bytes
                self.buffer[self.bytes_received] = byte
                self.bytes_received += 1
                
                # Check if we've read all payload bytes
                payload_len = self.buffer[2] | (self.buffer[3] << 8)
                if self.bytes_received == 4 + payload_len:
                    self.state = RxState.READ_CHECKSUM
            
            elif self.state == RxState.READ_CHECKSUM:
                # Read checksum bytes (2 bytes)
                self.buffer[self.bytes_received] = byte
                self.bytes_received += 1
                
                # Check if we've read both checksum bytes
                payload_len = self.buffer[2] | (self.buffer[3] << 8)
                if self.bytes_received == 6 + payload_len:
                    self.state = RxState.VALIDATE
            
            # Validate packet if we're in the validate state
            if self.state == RxState.VALIDATE:
                packet = self._validate_and_parse_packet()
                if packet:
                    packets.append(packet)
                    self.stats['packets_received'] += 1
                    self.stats['bytes_received'] += self.bytes_received
                
                # Reset for next packet
                self._reset_state()
        
        return packets
    
    def _validate_and_parse_packet(self) -> Optional[ParsedBinaryPacket]:
        """
        Validate checksum and parse a complete packet.
        
        Returns:
            ParsedBinaryPacket if valid, None if validation fails
            
        Requirements: 2.5, 3.1
        """
        # Extract packet components
        payload_len = self.buffer[2] | (self.buffer[3] << 8)
        
        # Extract received checksum (little-endian)
        checksum_offset = 4 + payload_len
        received_checksum = self.buffer[checksum_offset] | (self.buffer[checksum_offset + 1] << 8)
        
        # Calculate expected checksum over header + payload
        packet_data = bytes(self.buffer[0:4 + payload_len])
        expected_checksum = fletcher16(packet_data)
        
        if expected_checksum != received_checksum:
            # Checksum mismatch
            self.stats['checksum_errors'] += 1
            return None
        
        # Valid packet - parse it
        command_byte = self.buffer[1]
        
        # Validate command
        try:
            command = UartCommand(command_byte)
        except ValueError:
            self.stats['unknown_commands'] += 1
            return None
        
        # Extract payload bytes
        payload_bytes = bytes(self.buffer[4:4 + payload_len])
        
        # Parse payload based on command type
        payload = self._parse_payload(command, payload_bytes)
        
        # Extract complete raw packet
        total_len = 6 + payload_len
        raw_bytes = bytes(self.buffer[0:total_len])
        
        return ParsedBinaryPacket(
            timestamp=time.time(),
            command=command,
            payload=payload,
            raw_bytes=raw_bytes,
            payload_bytes=payload_bytes
        )
    
    def _parse_payload(self, command: UartCommand, payload_bytes: bytes) -> Optional[Any]:
        """
        Parse payload bytes based on command type.
        
        Args:
            command: Command type
            payload_bytes: Raw payload bytes
            
        Returns:
            Parsed payload object or None if parsing fails
            
        Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
        """
        try:
            if command == UartCommand.CMD_INIT:
                return InitPayload.from_bytes(payload_bytes)
            
            elif command == UartCommand.CMD_ACK:
                return None  # ACK has no payload
            
            elif command == UartCommand.CMD_RELAY_ACTIVATE:
                return RelayActivatePayload.from_bytes(payload_bytes)
            
            elif command == UartCommand.CMD_RELAY_TX:
                return RelayRxPayload.from_bytes(payload_bytes)
            
            elif command == UartCommand.CMD_RELAY_RX:
                return RelayRxPayload.from_bytes(payload_bytes)
            
            elif command == UartCommand.CMD_BRIDGE_TX:
                return BridgePayload.from_bytes(payload_bytes)
            
            elif command == UartCommand.CMD_BRIDGE_RX:
                return BridgePayload.from_bytes(payload_bytes)
            
            elif command == UartCommand.CMD_STATUS_REPORT:
                return StatusPayload.from_bytes(payload_bytes)
            
            elif command == UartCommand.CMD_BROADCAST_RELAY_REQ:
                return RelayRequestPayload.from_bytes(payload_bytes)
            
            elif command == UartCommand.CMD_STATUS_REQUEST:
                return None  # STATUS_REQUEST has no payload
            
            elif command == UartCommand.CMD_NONE:
                return None
            
            else:
                self.stats['unknown_commands'] += 1
                return None
        
        except Exception as e:
            self.stats['parse_errors'] += 1
            return None
    
    def _reset_state(self):
        """Reset state machine to wait for next packet"""
        self.state = RxState.WAIT_START
        self.bytes_received = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive parser statistics.
        
        Returns:
            Dictionary of statistics counters including:
            - packets_received: Number of successfully parsed packets
            - checksum_errors: Number of checksum validation failures
            - parse_errors: Number of payload parsing errors
            - timeout_errors: Number of timeout events
            - unknown_commands: Number of unrecognized command bytes
            - buffer_overflow: Number of buffer overflow events
            - bytes_received: Total bytes successfully processed
            - success_rate: Percentage of successful packet receptions
            
        Requirements: 2.1, 3.2
        """
        stats = self.stats.copy()
        
        # Calculate success rate (packets_received / total_attempts)
        total_attempts = (stats['packets_received'] + 
                         stats['checksum_errors'] + 
                         stats['parse_errors'])
        
        if total_attempts > 0:
            stats['success_rate'] = (stats['packets_received'] / total_attempts) * 100.0
        else:
            stats['success_rate'] = 100.0
        
        # Calculate error rates
        if stats['packets_received'] > 0:
            stats['checksum_error_rate'] = (stats['checksum_errors'] / stats['packets_received']) * 100.0
            stats['parse_error_rate'] = (stats['parse_errors'] / stats['packets_received']) * 100.0
        else:
            stats['checksum_error_rate'] = 0.0
            stats['parse_error_rate'] = 0.0
        
        return stats
    
    def reset_stats(self):
        """Reset all statistics counters"""
        for key in self.stats:
            self.stats[key] = 0



@dataclass
class ParsedMAVLinkMessage:
    """
    Represents a MAVLink message extracted from a binary protocol packet.
    
    This combines the parsed MAVLink message with RSSI/SNR metadata from
    the binary protocol BridgePayload.
    
    Requirements: 1.2, 5.1
    """
    timestamp: float                        # Python timestamp (seconds since epoch)
    msg_type: str                          # MAVLink message type name
    msg_id: int                            # MAVLink message ID
    system_id: int                         # MAVLink system ID
    component_id: int                      # MAVLink component ID
    fields: Dict[str, Any]                 # Decoded message fields
    rssi: Optional[float] = None           # RSSI in dBm (from BridgePayload)
    snr: Optional[float] = None            # SNR in dB (from BridgePayload)
    raw_mavlink_bytes: bytes = b''         # Raw MAVLink packet bytes
    binary_command: Optional[UartCommand] = None  # Original binary protocol command
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return (f"ParsedMAVLinkMessage(msg_type={self.msg_type}, "
                f"system_id={self.system_id}, "
                f"rssi={self.rssi:.1f if self.rssi else 'N/A'}, "
                f"snr={self.snr:.1f if self.snr else 'N/A'})")


class MAVLinkExtractor:
    """
    Extracts and parses MAVLink messages from binary protocol packets.
    
    This class handles CMD_BRIDGE_TX and CMD_BRIDGE_RX commands, extracting
    the embedded MAVLink packet from the BridgePayload and parsing it using
    pymavlink. RSSI/SNR metadata from the BridgePayload is attached to the
    parsed MAVLink message.
    
    Requirements: 1.2, 5.1
    """
    
    def __init__(self):
        """Initialize the MAVLink extractor"""
        try:
            from pymavlink import mavutil
            self.mavutil = mavutil
            self.mav = mavutil.mavlink.MAVLink(None)
            self.mavlink_available = True
        except ImportError:
            self.mavlink_available = False
            self.mav = None
        
        self.stats = {
            'mavlink_extracted': 0,
            'mavlink_parse_errors': 0,
            'bridge_packets_processed': 0
        }
    
    def extract_mavlink(self, packet: ParsedBinaryPacket) -> Optional[ParsedMAVLinkMessage]:
        """
        Extract and parse MAVLink message from a binary protocol packet.
        
        This method handles CMD_BRIDGE_TX and CMD_BRIDGE_RX commands,
        extracting the BridgePayload and parsing the embedded MAVLink data.
        
        Args:
            packet: Parsed binary protocol packet
            
        Returns:
            ParsedMAVLinkMessage if successful, None otherwise
            
        Requirements: 1.2, 5.1
        """
        if not self.mavlink_available:
            return None
        
        # Only process bridge commands
        if packet.command not in (UartCommand.CMD_BRIDGE_TX, UartCommand.CMD_BRIDGE_RX):
            return None
        
        # Ensure payload is BridgePayload
        if not isinstance(packet.payload, BridgePayload):
            return None
        
        self.stats['bridge_packets_processed'] += 1
        bridge_payload = packet.payload
        
        # Extract MAVLink data from BridgePayload
        mavlink_data = bridge_payload.data
        
        if not mavlink_data or len(mavlink_data) == 0:
            return None
        
        # Parse MAVLink packet
        try:
            parsed_msg = self._parse_mavlink_bytes(mavlink_data)
            
            if parsed_msg:
                # Attach RSSI/SNR from BridgePayload
                parsed_msg.rssi = bridge_payload.rssi
                parsed_msg.snr = bridge_payload.snr
                parsed_msg.binary_command = packet.command
                parsed_msg.timestamp = packet.timestamp
                
                self.stats['mavlink_extracted'] += 1
                return parsed_msg
        
        except Exception as e:
            self.stats['mavlink_parse_errors'] += 1
        
        return None
    
    def _parse_mavlink_bytes(self, data: bytes) -> Optional[ParsedMAVLinkMessage]:
        """
        Parse raw MAVLink bytes into a ParsedMAVLinkMessage.
        
        Args:
            data: Raw MAVLink packet bytes
            
        Returns:
            ParsedMAVLinkMessage if successful, None otherwise
            
        Requirements: 1.2, 5.1
        """
        if not self.mavlink_available or not data:
            return None
        
        # Parse MAVLink packet byte by byte
        for byte in data:
            msg = self.mav.parse_char(bytes([byte]))
            
            if msg:
                # Successfully parsed a complete MAVLink message
                return ParsedMAVLinkMessage(
                    timestamp=time.time(),
                    msg_type=msg.get_type(),
                    msg_id=msg.get_msgId(),
                    system_id=msg.get_srcSystem(),
                    component_id=msg.get_srcComponent(),
                    fields=msg.to_dict(),
                    raw_mavlink_bytes=msg.get_msgbuf()
                )
        
        return None
    
    def get_stats(self) -> Dict[str, int]:
        """Get MAVLink extraction statistics"""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset all statistics counters"""
        for key in self.stats:
            self.stats[key] = 0



class BinaryProtocolStatistics:
    """
    Comprehensive statistics tracking for binary protocol communication.
    
    Tracks packets, bytes, errors, and command distribution for diagnostics
    and health monitoring of the binary UART protocol.
    
    Requirements: 2.1, 3.2
    """
    
    def __init__(self):
        """Initialize statistics tracking"""
        self.packets_received = 0
        self.checksum_errors = 0
        self.parse_errors = 0
        self.timeout_errors = 0
        self.unknown_commands = 0
        self.buffer_overflow = 0
        self.bytes_received = 0
        
        # Command distribution tracking
        self.command_counts = {cmd: 0 for cmd in UartCommand}
        
        # Timing
        self.start_time = time.time()
        self.last_packet_time = 0.0
    
    def update_from_parser(self, parser: BinaryProtocolParser):
        """
        Update statistics from a parser instance.
        
        Args:
            parser: BinaryProtocolParser instance
        """
        parser_stats = parser.get_stats()
        self.packets_received = parser_stats['packets_received']
        self.checksum_errors = parser_stats['checksum_errors']
        self.parse_errors = parser_stats['parse_errors']
        self.timeout_errors = parser_stats['timeout_errors']
        self.unknown_commands = parser_stats['unknown_commands']
        self.buffer_overflow = parser_stats['buffer_overflow']
        self.bytes_received = parser_stats['bytes_received']
    
    def record_packet(self, packet: ParsedBinaryPacket):
        """
        Record a successfully parsed packet.
        
        Args:
            packet: Parsed binary protocol packet
        """
        self.command_counts[packet.command] += 1
        self.last_packet_time = packet.timestamp
    
    def get_success_rate(self) -> float:
        """
        Calculate the success rate of received packets.
        
        Returns:
            Success rate as a percentage (0.0 - 100.0)
            
        Requirements: 2.1, 3.2
        """
        total_attempts = (self.packets_received + 
                         self.checksum_errors + 
                         self.parse_errors)
        
        if total_attempts == 0:
            return 100.0
        
        return (self.packets_received / total_attempts) * 100.0
    
    def get_command_distribution(self) -> Dict[str, int]:
        """
        Get distribution of received commands.
        
        Returns:
            Dictionary mapping command names to counts
        """
        return {cmd.name: count for cmd, count in self.command_counts.items() if count > 0}
    
    def get_uptime(self) -> float:
        """
        Get uptime in seconds since statistics started.
        
        Returns:
            Uptime in seconds
        """
        return time.time() - self.start_time
    
    def get_packet_rate(self) -> float:
        """
        Calculate average packet rate.
        
        Returns:
            Packets per second
        """
        uptime = self.get_uptime()
        if uptime == 0:
            return 0.0
        return self.packets_received / uptime
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics summary.
        
        Returns:
            Dictionary with all statistics and calculated metrics
            
        Requirements: 2.1, 3.2
        """
        uptime = self.get_uptime()
        
        return {
            'packets_received': self.packets_received,
            'checksum_errors': self.checksum_errors,
            'parse_errors': self.parse_errors,
            'timeout_errors': self.timeout_errors,
            'unknown_commands': self.unknown_commands,
            'buffer_overflow': self.buffer_overflow,
            'bytes_received': self.bytes_received,
            'success_rate': self.get_success_rate(),
            'packet_rate': self.get_packet_rate(),
            'uptime_seconds': uptime,
            'command_distribution': self.get_command_distribution(),
            'last_packet_time': self.last_packet_time
        }
    
    def reset(self):
        """Reset all statistics counters"""
        self.packets_received = 0
        self.checksum_errors = 0
        self.parse_errors = 0
        self.timeout_errors = 0
        self.unknown_commands = 0
        self.buffer_overflow = 0
        self.bytes_received = 0
        self.command_counts = {cmd: 0 for cmd in UartCommand}
        self.start_time = time.time()
        self.last_packet_time = 0.0



class BinaryCommandHandler:
    """
    Handler for non-MAVLink binary protocol commands.
    
    This class processes and stores parsed payloads from commands like
    CMD_STATUS_REPORT, CMD_RELAY_RX, and CMD_INIT for metrics and logging.
    
    Requirements: 1.2, 5.1
    """
    
    def __init__(self):
        """Initialize the command handler"""
        self.latest_status = None           # Latest StatusPayload
        self.latest_init = None             # Latest InitPayload
        self.relay_requests = []            # List of RelayRequestPayload
        self.relay_activations = []         # List of RelayActivatePayload with timestamps
        
        # Statistics
        self.stats = {
            'status_reports_received': 0,
            'init_commands_received': 0,
            'relay_requests_received': 0,
            'relay_activations_received': 0,
            'relay_rx_packets_received': 0,
            'relay_tx_packets_received': 0,
            'ack_received': 0,
            'status_requests_received': 0
        }
    
    def handle_packet(self, packet: ParsedBinaryPacket):
        """
        Process a binary protocol packet and store relevant data.
        
        Args:
            packet: Parsed binary protocol packet
            
        Requirements: 1.2, 5.1
        """
        if packet.command == UartCommand.CMD_STATUS_REPORT:
            self._handle_status_report(packet)
        
        elif packet.command == UartCommand.CMD_INIT:
            self._handle_init(packet)
        
        elif packet.command == UartCommand.CMD_BROADCAST_RELAY_REQ:
            self._handle_relay_request(packet)
        
        elif packet.command == UartCommand.CMD_RELAY_ACTIVATE:
            self._handle_relay_activate(packet)
        
        elif packet.command == UartCommand.CMD_RELAY_RX:
            self._handle_relay_rx(packet)
        
        elif packet.command == UartCommand.CMD_RELAY_TX:
            self._handle_relay_tx(packet)
        
        elif packet.command == UartCommand.CMD_ACK:
            self.stats['ack_received'] += 1
        
        elif packet.command == UartCommand.CMD_STATUS_REQUEST:
            self.stats['status_requests_received'] += 1
    
    def _handle_status_report(self, packet: ParsedBinaryPacket):
        """
        Handle CMD_STATUS_REPORT command.
        
        Stores the latest status payload for system metrics tracking.
        
        Args:
            packet: Parsed packet with StatusPayload
        """
        if isinstance(packet.payload, StatusPayload):
            self.latest_status = packet.payload
            self.stats['status_reports_received'] += 1
    
    def _handle_init(self, packet: ParsedBinaryPacket):
        """
        Handle CMD_INIT command.
        
        Stores initialization data for system configuration tracking.
        
        Args:
            packet: Parsed packet with InitPayload
        """
        if isinstance(packet.payload, InitPayload):
            self.latest_init = packet.payload
            self.stats['init_commands_received'] += 1
    
    def _handle_relay_request(self, packet: ParsedBinaryPacket):
        """
        Handle CMD_BROADCAST_RELAY_REQ command.
        
        Stores relay request with link quality metrics.
        
        Args:
            packet: Parsed packet with RelayRequestPayload
        """
        if isinstance(packet.payload, RelayRequestPayload):
            self.relay_requests.append({
                'timestamp': packet.timestamp,
                'payload': packet.payload
            })
            self.stats['relay_requests_received'] += 1
            
            # Keep only last 100 requests
            if len(self.relay_requests) > 100:
                self.relay_requests.pop(0)
    
    def _handle_relay_activate(self, packet: ParsedBinaryPacket):
        """
        Handle CMD_RELAY_ACTIVATE command.
        
        Tracks relay mode activation/deactivation events.
        
        Args:
            packet: Parsed packet with RelayActivatePayload
        """
        if isinstance(packet.payload, RelayActivatePayload):
            self.relay_activations.append({
                'timestamp': packet.timestamp,
                'activate': packet.payload.activate
            })
            self.stats['relay_activations_received'] += 1
            
            # Keep only last 100 activations
            if len(self.relay_activations) > 100:
                self.relay_activations.pop(0)
    
    def _handle_relay_rx(self, packet: ParsedBinaryPacket):
        """
        Handle CMD_RELAY_RX command.
        
        Tracks relay receive packets with telemetry.
        
        Args:
            packet: Parsed packet with RelayRxPayload
        """
        if isinstance(packet.payload, RelayRxPayload):
            self.stats['relay_rx_packets_received'] += 1
    
    def _handle_relay_tx(self, packet: ParsedBinaryPacket):
        """
        Handle CMD_RELAY_TX command.
        
        Tracks relay transmit packets.
        
        Args:
            packet: Parsed packet with RelayRxPayload
        """
        if isinstance(packet.payload, RelayRxPayload):
            self.stats['relay_tx_packets_received'] += 1
    
    def get_latest_status(self) -> Optional[StatusPayload]:
        """
        Get the most recent status report.
        
        Returns:
            Latest StatusPayload or None if no status received
        """
        return self.latest_status
    
    def get_latest_init(self) -> Optional[InitPayload]:
        """
        Get the most recent initialization data.
        
        Returns:
            Latest InitPayload or None if no init received
        """
        return self.latest_init
    
    def is_relay_active(self) -> bool:
        """
        Check if relay mode is currently active based on latest status.
        
        Returns:
            True if relay is active, False otherwise
        """
        if self.latest_status:
            return self.latest_status.relay_active
        return False
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get system metrics from latest status report.
        
        Returns:
            Dictionary of system metrics or empty dict if no status available
            
        Requirements: 5.1
        """
        if not self.latest_status:
            return {}
        
        status = self.latest_status
        
        return {
            'relay_active': status.relay_active,
            'own_drone_sysid': status.own_drone_sysid,
            'packets_relayed': status.packets_relayed,
            'bytes_relayed': status.bytes_relayed,
            'mesh_to_uart_packets': status.mesh_to_uart_packets,
            'uart_to_mesh_packets': status.uart_to_mesh_packets,
            'mesh_to_uart_bytes': status.mesh_to_uart_bytes,
            'uart_to_mesh_bytes': status.uart_to_mesh_bytes,
            'bridge_gcs_to_mesh_packets': status.bridge_gcs_to_mesh_packets,
            'bridge_mesh_to_gcs_packets': status.bridge_mesh_to_gcs_packets,
            'bridge_gcs_to_mesh_bytes': status.bridge_gcs_to_mesh_bytes,
            'bridge_mesh_to_gcs_bytes': status.bridge_mesh_to_gcs_bytes,
            'rssi': status.rssi,
            'snr': status.snr,
            'last_activity_sec': status.last_activity_sec,
            'active_peer_relays': status.active_peer_relays
        }
    
    def get_stats(self) -> Dict[str, int]:
        """Get command handler statistics"""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset all statistics counters"""
        for key in self.stats:
            self.stats[key] = 0
