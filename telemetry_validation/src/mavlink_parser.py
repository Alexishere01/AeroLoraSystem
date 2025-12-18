"""
MAVLink Parser Module

This module provides MAVLink packet parsing capabilities with buffer management,
statistics tracking, and RSSI/SNR extraction from RADIO_STATUS messages.
"""

from pymavlink import mavutil
from dataclasses import dataclass, field
from typing import Optional, List
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ParsedMessage:
    """
    Structured representation of a parsed MAVLink message.
    
    Attributes:
        timestamp: Unix timestamp when message was parsed
        msg_type: MAVLink message type name (e.g., 'HEARTBEAT', 'GPS_RAW_INT')
        msg_id: Numeric message ID
        system_id: Source system ID
        component_id: Source component ID
        sequence: MAVLink packet sequence number (0-255)
        fields: Dictionary of message fields and their values
        rssi: Received Signal Strength Indicator (dBm), if available
        snr: Signal-to-Noise Ratio (dB), if available
        raw_bytes: Raw MAVLink packet bytes
    """
    timestamp: float
    msg_type: str
    msg_id: int
    system_id: int
    component_id: int
    sequence: int
    fields: dict
    rssi: Optional[float] = None
    snr: Optional[float] = None
    raw_bytes: bytes = b''


class MAVLinkParser:
    """
    MAVLink packet parser with buffer management and statistics tracking.
    
    This parser handles continuous streams of MAVLink data, extracting and
    validating packets while tracking parse errors and link quality metrics.
    """
    
    def __init__(self):
        """Initialize the MAVLink parser with statistics tracking."""
        # Create MAVLink parser instance
        self.mav = mavutil.mavlink.MAVLink(None)
        
        # Statistics tracking
        self.stats = {
            'total_packets': 0,
            'parse_errors': 0,
            'checksum_errors': 0,
            'unknown_messages': 0,
            'bytes_processed': 0
        }
        
        # RSSI/SNR tracking from RADIO_STATUS messages
        self.last_rssi: Optional[float] = None
        self.last_snr: Optional[float] = None
        self.last_radio_status_time: Optional[float] = None
        
        logger.info("MAVLink parser initialized")
    
    def parse_stream(self, data: bytes) -> List[ParsedMessage]:
        """
        Parse incoming data stream and return list of complete messages.
        
        This method processes a chunk of data, which may contain partial or
        multiple MAVLink packets. It maintains an internal buffer to handle
        incomplete packets across multiple calls.
        
        Args:
            data: Raw bytes from serial port or UDP socket
            
        Returns:
            List of ParsedMessage objects for all complete packets found
        """
        if not data:
            return []
        
        self.stats['bytes_processed'] += len(data)
        messages = []
        
        # Process each byte through the MAVLink parser
        for byte in data:
            try:
                # Parse one byte at a time through pymavlink
                msg = self.mav.parse_char(bytes([byte]))
                
                if msg:
                    # Successfully parsed a complete message
                    parsed = self._create_parsed_message(msg)
                    messages.append(parsed)
                    self.stats['total_packets'] += 1
                    
                    # Update RSSI/SNR if this is a RADIO_STATUS message
                    if msg.get_type() == 'RADIO_STATUS':
                        self._extract_radio_status(msg)
                    
                    logger.debug(f"Parsed {msg.get_type()} from system {msg.get_srcSystem()}")
                    
            except mavutil.mavlink.MAVError as e:
                # MAVLink-specific error (checksum, etc.)
                self.stats['checksum_errors'] += 1
                logger.warning(f"MAVLink error: {e}")
                
            except Exception as e:
                # General parsing error
                self.stats['parse_errors'] += 1
                logger.error(f"Parse error: {e}")
        
        return messages
    
    def _create_parsed_message(self, msg) -> ParsedMessage:
        """
        Create a ParsedMessage object from a pymavlink message.
        
        Args:
            msg: pymavlink message object
            
        Returns:
            ParsedMessage with all fields populated
        """
        try:
            # Extract message fields
            msg_dict = msg.to_dict()
            
            # Get raw bytes if available
            raw_bytes = b''
            try:
                raw_bytes = msg.get_msgbuf()
            except:
                pass
            
            # Get sequence number from MAVLink packet header
            sequence = 0
            try:
                sequence = msg.get_seq()
            except:
                pass
            
            # Create parsed message with current RSSI/SNR
            parsed = ParsedMessage(
                timestamp=time.time(),
                msg_type=msg.get_type(),
                msg_id=msg.get_msgId(),
                system_id=msg.get_srcSystem(),
                component_id=msg.get_srcComponent(),
                sequence=sequence,
                fields=msg_dict,
                rssi=self.last_rssi,
                snr=self.last_snr,
                raw_bytes=raw_bytes
            )
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error creating parsed message: {e}")
            # Return minimal message on error
            return ParsedMessage(
                timestamp=time.time(),
                msg_type='UNKNOWN',
                msg_id=0,
                system_id=0,
                component_id=0,
                sequence=0,
                fields={},
                raw_bytes=b''
            )
    
    def _extract_radio_status(self, msg):
        """
        Extract RSSI and SNR from RADIO_STATUS message.
        
        RADIO_STATUS messages contain link quality metrics that apply to
        subsequent messages until a new RADIO_STATUS is received.
        
        Args:
            msg: pymavlink RADIO_STATUS message
        """
        try:
            msg_dict = msg.to_dict()
            
            # Extract RSSI (typically in dBm, negative values)
            if 'rssi' in msg_dict:
                self.last_rssi = float(msg_dict['rssi'])
            
            # Extract remote RSSI if available
            if 'remrssi' in msg_dict:
                # Use remote RSSI as it represents the link quality
                # from the remote end
                remote_rssi = float(msg_dict['remrssi'])
                if remote_rssi != 0:
                    self.last_rssi = remote_rssi
            
            # Extract SNR (Signal-to-Noise Ratio)
            if 'noise' in msg_dict and 'rssi' in msg_dict:
                # Calculate SNR from RSSI and noise floor
                noise = float(msg_dict['noise'])
                rssi = float(msg_dict['rssi'])
                if noise != 0:
                    self.last_snr = rssi - noise
            
            # Some implementations provide SNR directly
            if 'remnoise' in msg_dict and 'remrssi' in msg_dict:
                noise = float(msg_dict['remnoise'])
                rssi = float(msg_dict['remrssi'])
                if noise != 0 and rssi != 0:
                    self.last_snr = rssi - noise
            
            self.last_radio_status_time = time.time()
            
            logger.debug(f"Updated link quality: RSSI={self.last_rssi}, SNR={self.last_snr}")
            
        except Exception as e:
            logger.warning(f"Error extracting RADIO_STATUS: {e}")
    
    def get_stats(self) -> dict:
        """
        Get parser statistics.
        
        Returns:
            Dictionary containing:
                - total_packets: Total successfully parsed packets
                - parse_errors: Number of parse errors encountered
                - checksum_errors: Number of checksum validation failures
                - unknown_messages: Number of unknown message types
                - bytes_processed: Total bytes processed
                - last_rssi: Most recent RSSI value
                - last_snr: Most recent SNR value
        """
        stats = self.stats.copy()
        stats['last_rssi'] = self.last_rssi
        stats['last_snr'] = self.last_snr
        
        # Calculate error rate
        total_attempts = stats['total_packets'] + stats['parse_errors'] + stats['checksum_errors']
        if total_attempts > 0:
            stats['error_rate'] = (stats['parse_errors'] + stats['checksum_errors']) / total_attempts * 100
        else:
            stats['error_rate'] = 0.0
        
        return stats
    
    def reset_stats(self):
        """Reset all statistics counters."""
        self.stats = {
            'total_packets': 0,
            'parse_errors': 0,
            'checksum_errors': 0,
            'unknown_messages': 0,
            'bytes_processed': 0
        }
        logger.info("Parser statistics reset")
    
    def clear_buffer(self):
        """
        Reset the MAVLink parser state.
        
        This recreates the MAVLink parser instance, clearing any internal
        state. Useful for recovering from errors or synchronization issues.
        """
        self.mav = mavutil.mavlink.MAVLink(None)
        logger.info("MAVLink parser state cleared")
