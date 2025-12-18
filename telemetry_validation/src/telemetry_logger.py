"""
Telemetry Logger Module

This module provides comprehensive logging capabilities for MAVLink telemetry data,
supporting CSV, JSON, and .tlog formats with automatic file rotation.
"""

import csv
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

from .mavlink_parser import ParsedMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TelemetryLogger:
    """
    Multi-format telemetry logger with automatic file rotation.
    
    This logger captures MAVLink telemetry data and writes it to multiple
    formats simultaneously:
    - CSV: Human-readable format with decoded fields
    - JSON: Structured format for programmatic access
    - .tlog: Binary format compatible with QGC and MAVProxy
    
    Features:
    - Timestamped filenames for easy organization
    - Automatic file rotation at configurable size limit
    - Buffered JSON writes for performance
    - Graceful error handling and recovery
    """
    
    def __init__(self, log_dir: str = './telemetry_logs', max_file_size_mb: int = 100, log_prefix: str = None):
        """
        Initialize the telemetry logger.
        
        Args:
            log_dir: Directory to store log files (created if doesn't exist)
            max_file_size_mb: Maximum file size in MB before rotation (default: 100)
            log_prefix: Optional prefix for log filenames (e.g., "ground" or "drone")
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.log_prefix = log_prefix if log_prefix else ""
        
        # File sequence counter for rotation
        self.file_sequence = 0
        
        # JSON buffer for batch writes
        self.json_buffer = []
        self.json_buffer_size = 100  # Flush after this many messages
        
        # Message counter
        self.message_count = 0
        
        # Binary protocol packet counter
        self.binary_packet_count = 0
        
        # Initialize log files
        self._create_log_files()
        
        logger.info(f"Telemetry logger initialized in {self.log_dir}")
    
    def _create_log_files(self):
        """Create timestamped log files for all formats."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Build base name with optional prefix
        if self.log_prefix:
            prefix_part = f'{self.log_prefix}_'
        else:
            prefix_part = ''
        
        # Add sequence number if this is a rotation
        if self.file_sequence > 0:
            base_name = f'{prefix_part}telemetry_{timestamp}_{self.file_sequence}'
        else:
            base_name = f'{prefix_part}telemetry_{timestamp}'
        
        # Define file paths
        self.csv_file = self.log_dir / f'{base_name}.csv'
        self.json_file = self.log_dir / f'{base_name}.json'
        self.tlog_file = self.log_dir / f'{base_name}.tlog'
        self.binlog_file = self.log_dir / f'{base_name}.binlog'
        
        # Initialize CSV file
        self._init_csv()
        
        # Initialize .tlog file
        self._init_tlog()
        
        # Initialize .binlog file
        self._init_binlog()
        
        logger.info(f"Created log files: {base_name}.*")
    
    def _init_csv(self):
        """Initialize CSV file with headers."""
        try:
            self.csv_handle = open(self.csv_file, 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_handle)
            
            # Write CSV headers
            self.csv_writer.writerow([
                'timestamp',
                'msg_type',
                'msg_id',
                'system_id',
                'component_id',
                'fields',
                'rssi',
                'snr'
            ])
            
            # Flush to ensure headers are written
            self.csv_handle.flush()
            
            logger.debug(f"CSV file initialized: {self.csv_file}")
            
        except Exception as e:
            logger.error(f"Failed to initialize CSV file: {e}")
            raise
    
    def _init_tlog(self):
        """Initialize .tlog file for binary MAVLink data."""
        try:
            self.tlog_handle = open(self.tlog_file, 'wb')
            logger.debug(f".tlog file initialized: {self.tlog_file}")
            
        except Exception as e:
            logger.error(f"Failed to initialize .tlog file: {e}")
            raise
    
    def _init_binlog(self):
        """Initialize .binlog file for binary protocol packets."""
        try:
            self.binlog_handle = open(self.binlog_file, 'wb')
            logger.debug(f".binlog file initialized: {self.binlog_file}")
            
        except Exception as e:
            logger.error(f"Failed to initialize .binlog file: {e}")
            raise
    
    def log_message(self, msg: ParsedMessage):
        """
        Log a parsed MAVLink message to all formats.
        
        This method writes the message to CSV immediately, buffers it for
        JSON output, and writes raw bytes to .tlog format.
        
        Args:
            msg: ParsedMessage object to log
        """
        try:
            # Log to CSV
            self._log_csv(msg)
            
            # Buffer for JSON
            self._buffer_json(msg)
            
            # Log to .tlog
            self._log_tlog(msg)
            
            # Increment message counter
            self.message_count += 1
            
            # Check if file rotation is needed
            self._check_rotation()
            
        except Exception as e:
            logger.error(f"Error logging message: {e}")
    
    def _log_csv(self, msg: ParsedMessage):
        """
        Write message to CSV file.
        
        Args:
            msg: ParsedMessage to write
        """
        try:
            # Convert fields dict to JSON string for CSV storage
            fields_json = json.dumps(msg.fields)
            
            # Write row to CSV
            self.csv_writer.writerow([
                msg.timestamp,
                msg.msg_type,
                msg.msg_id,
                msg.system_id,
                msg.component_id,
                fields_json,
                msg.rssi if msg.rssi is not None else '',
                msg.snr if msg.snr is not None else ''
            ])
            
            # Flush periodically for real-time viewing
            if self.message_count % 10 == 0:
                self.csv_handle.flush()
            
        except Exception as e:
            logger.error(f"Error writing to CSV: {e}")
    
    def _buffer_json(self, msg: ParsedMessage):
        """
        Buffer message for JSON output.
        
        Messages are buffered in memory and flushed periodically to
        improve performance.
        
        Args:
            msg: ParsedMessage to buffer
        """
        try:
            # Create JSON-serializable dict
            json_entry = {
                'timestamp': msg.timestamp,
                'msg_type': msg.msg_type,
                'msg_id': msg.msg_id,
                'system_id': msg.system_id,
                'component_id': msg.component_id,
                'fields': msg.fields,
                'rssi': msg.rssi,
                'snr': msg.snr
            }
            
            self.json_buffer.append(json_entry)
            
            # Flush if buffer is full
            if len(self.json_buffer) >= self.json_buffer_size:
                self._flush_json()
            
        except Exception as e:
            logger.error(f"Error buffering JSON: {e}")
    
    def _flush_json(self):
        """
        Write buffered JSON data to file.
        
        This creates a structured JSON file with nested message objects.
        The entire buffer is written as a JSON array.
        """
        if not self.json_buffer:
            return
        
        try:
            # Read existing data if file exists
            existing_data = []
            if self.json_file.exists():
                try:
                    with open(self.json_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except json.JSONDecodeError:
                    # File might be empty or corrupted, start fresh
                    existing_data = []
            
            # Append new data
            existing_data.extend(self.json_buffer)
            
            # Write back to file
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2)
            
            logger.debug(f"Flushed {len(self.json_buffer)} messages to JSON")
            
            # Clear buffer
            self.json_buffer = []
            
        except Exception as e:
            logger.error(f"Error flushing JSON: {e}")
    
    def _log_tlog(self, msg: ParsedMessage):
        """
        Write raw MAVLink bytes to .tlog file.
        
        The .tlog format is a simple binary format that stores raw MAVLink
        packets sequentially. This format is compatible with QGroundControl
        and MAVProxy for replay and analysis.
        
        Args:
            msg: ParsedMessage containing raw_bytes
        """
        try:
            if msg.raw_bytes:
                self.tlog_handle.write(msg.raw_bytes)
                
                # Flush periodically
                if self.message_count % 10 == 0:
                    self.tlog_handle.flush()
            
        except Exception as e:
            logger.error(f"Error writing to .tlog: {e}")
    
    def log_binary_packet(self, packet):
        """
        Log a raw binary protocol packet to .binlog file.
        
        This method writes complete binary protocol packets (including headers,
        payload, and checksums) to a separate .binlog file for debugging and
        replay purposes. The packet can be either a ParsedBinaryPacket object
        or raw bytes.
        
        Args:
            packet: ParsedBinaryPacket object or raw bytes to log
            
        Requirements: 1.1, 10.4
        """
        try:
            # Extract raw bytes from packet
            if hasattr(packet, 'raw_bytes'):
                raw_bytes = packet.raw_bytes
            elif isinstance(packet, bytes):
                raw_bytes = packet
            else:
                logger.warning(f"Cannot log binary packet: unsupported type {type(packet)}")
                return
            
            if not raw_bytes:
                return
            
            # Write raw packet to .binlog file
            self.binlog_handle.write(raw_bytes)
            
            # Increment binary packet counter
            self.binary_packet_count += 1
            
            # Flush periodically
            if self.binary_packet_count % 10 == 0:
                self.binlog_handle.flush()
            
            # Check if file rotation is needed
            self._check_rotation()
            
        except Exception as e:
            logger.error(f"Error logging binary packet: {e}")
    
    def _check_rotation(self):
        """
        Check if file rotation is needed based on file size.
        
        When the CSV file exceeds the maximum size, all files are rotated
        to new files with incremented sequence numbers.
        """
        try:
            # Check CSV file size (typically the largest)
            if self.csv_file.exists():
                file_size = self.csv_file.stat().st_size
                
                if file_size >= self.max_file_size:
                    logger.info(f"File size {file_size / 1024 / 1024:.2f} MB exceeds limit, rotating files")
                    self._rotate_files()
        
        except Exception as e:
            logger.error(f"Error checking file rotation: {e}")
    
    def _rotate_files(self):
        """
        Rotate log files when size limit is reached.
        
        This closes current files, flushes any buffered data, increments
        the sequence counter, and creates new files.
        """
        try:
            # Flush JSON buffer before closing
            self._flush_json()
            
            # Close current files
            if hasattr(self, 'csv_handle') and self.csv_handle:
                self.csv_handle.close()
            
            if hasattr(self, 'tlog_handle') and self.tlog_handle:
                self.tlog_handle.close()
            
            if hasattr(self, 'binlog_handle') and self.binlog_handle:
                self.binlog_handle.close()
            
            # Increment sequence counter
            self.file_sequence += 1
            
            # Create new files
            self._create_log_files()
            
            logger.info(f"Files rotated to sequence {self.file_sequence}")
            
        except Exception as e:
            logger.error(f"Error rotating files: {e}")
            raise
    
    def close(self):
        """
        Close all log files and flush buffered data.
        
        This should be called when shutting down to ensure all data is
        written to disk.
        """
        try:
            logger.info(f"Closing telemetry logger. Total messages logged: {self.message_count}, binary packets: {self.binary_packet_count}")
            
            # Flush JSON buffer
            self._flush_json()
            
            # Close CSV file
            if hasattr(self, 'csv_handle') and self.csv_handle:
                self.csv_handle.close()
                logger.debug("CSV file closed")
            
            # Close .tlog file
            if hasattr(self, 'tlog_handle') and self.tlog_handle:
                self.tlog_handle.close()
                logger.debug(".tlog file closed")
            
            # Close .binlog file
            if hasattr(self, 'binlog_handle') and self.binlog_handle:
                self.binlog_handle.close()
                logger.debug(".binlog file closed")
            
            # Write summary
            self._write_summary()
            
        except Exception as e:
            logger.error(f"Error closing logger: {e}")
    
    def _write_summary(self):
        """
        Write a summary file with logging statistics.
        
        This creates a text file with information about the logging session.
        """
        try:
            summary_file = self.log_dir / f'summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write("Telemetry Logging Summary\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Total MAVLink messages logged: {self.message_count}\n")
                f.write(f"Total binary protocol packets logged: {self.binary_packet_count}\n")
                f.write(f"File rotations: {self.file_sequence}\n")
                f.write(f"Log directory: {self.log_dir}\n")
                f.write(f"Session ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            logger.info(f"Summary written to {summary_file}")
            
        except Exception as e:
            logger.error(f"Error writing summary: {e}")
    
    def get_stats(self) -> dict:
        """
        Get logging statistics.
        
        Returns:
            Dictionary containing:
                - message_count: Total MAVLink messages logged
                - binary_packet_count: Total binary protocol packets logged
                - file_sequence: Current file sequence number
                - csv_file: Path to current CSV file
                - json_file: Path to current JSON file
                - tlog_file: Path to current .tlog file
                - binlog_file: Path to current .binlog file
                - json_buffer_size: Number of messages in JSON buffer
        """
        return {
            'message_count': self.message_count,
            'binary_packet_count': self.binary_packet_count,
            'file_sequence': self.file_sequence,
            'csv_file': str(self.csv_file),
            'json_file': str(self.json_file),
            'tlog_file': str(self.tlog_file),
            'binlog_file': str(self.binlog_file),
            'json_buffer_size': len(self.json_buffer)
        }
