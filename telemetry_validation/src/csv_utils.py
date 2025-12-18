"""
CSV Format Detection and Parsing Utilities

This module provides utilities for detecting and parsing both enhanced (12-field)
and legacy (8-field) CSV formats for flight logging data.

Enhanced Format (12 fields):
    timestamp_ms, sequence_number, message_id, system_id, rssi_dbm, snr_db,
    relay_active, event, packet_size, tx_timestamp, queue_depth, errors

Legacy Format (8 fields):
    timestamp_ms, sequence_number, message_id, system_id, rssi_dbm, snr_db,
    relay_active, event
"""

import csv
import logging
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

logger = logging.getLogger(__name__)


def detect_csv_format(header_line: str) -> str:
    """
    Detect CSV format from header line.
    
    Args:
        header_line: The CSV header line as a string
        
    Returns:
        'enhanced' for 12-field format with packet_size, tx_timestamp, queue_depth, errors
        'legacy' for 8-field format ending with event
        'unknown' for unrecognized format
    """
    fields = [f.strip() for f in header_line.strip().split(',')]
    
    # Check for enhanced format (12+ fields)
    if len(fields) >= 12:
        required_enhanced_fields = ['packet_size', 'tx_timestamp', 'queue_depth', 'errors']
        if all(field in fields for field in required_enhanced_fields):
            return 'enhanced'
    
    # Check for legacy format (8 fields)
    if len(fields) == 8:
        required_legacy_fields = ['timestamp_ms', 'sequence_number', 'message_id', 
                                 'system_id', 'rssi_dbm', 'snr_db', 'relay_active', 'event']
        if all(field in fields for field in required_legacy_fields):
            return 'legacy'
    
    return 'unknown'


@dataclass
class EnhancedLogEntry:
    """
    Enhanced log entry with all 12 fields.
    
    Supports both enhanced and legacy formats by providing default values
    for missing fields when parsing legacy format.
    """
    timestamp_ms: int
    sequence_number: int
    message_id: int
    system_id: int
    rssi_dbm: float
    snr_db: float
    relay_active: bool
    event: str
    packet_size: int = 0  # Default for legacy format
    tx_timestamp: int = 0  # Default for legacy format
    queue_depth: int = 0  # Default for legacy format
    errors: int = 0  # Default for legacy format
    
    @classmethod
    def from_csv_row(cls, row: Dict[str, str], format_type: str) -> 'EnhancedLogEntry':
        """
        Create EnhancedLogEntry from CSV row with backward compatibility.
        
        Handles both enhanced and legacy formats by providing default values
        for missing fields in legacy format.
        
        Args:
            row: Dictionary mapping field names to values
            format_type: 'enhanced' or 'legacy'
            
        Returns:
            EnhancedLogEntry instance
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        try:
            # Parse common fields (present in both formats)
            entry = cls(
                timestamp_ms=int(row['timestamp_ms']),
                sequence_number=int(row['sequence_number']),
                message_id=int(row['message_id']),
                system_id=int(row['system_id']),
                rssi_dbm=float(row['rssi_dbm']),
                snr_db=float(row['snr_db']),
                relay_active=bool(int(row['relay_active'])),
                event=row['event'].strip()
            )
            
            # Add enhanced fields if available
            if format_type == 'enhanced':
                entry.packet_size = int(row.get('packet_size', 0))
                entry.tx_timestamp = int(row.get('tx_timestamp', 0))
                entry.queue_depth = int(row.get('queue_depth', 0))
                entry.errors = int(row.get('errors', 0))
            
            return entry
            
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error parsing CSV row: {e}")
            logger.debug(f"Row data: {row}")
            raise ValueError(f"Failed to parse CSV row: {e}")


def safe_get_field(row: Dict[str, str], field: str, default: Any, 
                  field_type: type) -> Any:
    """
    Safely get field from CSV row with type conversion.
    
    Args:
        row: Dictionary mapping field names to values
        field: Field name to retrieve
        default: Default value if field is missing or invalid
        field_type: Type to convert the value to
        
    Returns:
        Converted field value or default
    """
    try:
        value = row.get(field, default)
        if value == '' or value is None:
            return default
        return field_type(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Error parsing field '{field}': {e}, using default {default}")
        return default


def load_flight_log(filename: str) -> Tuple[List[EnhancedLogEntry], str]:
    """
    Load flight log CSV file with automatic format detection.
    
    Automatically detects whether the file is in enhanced (12-field) or
    legacy (8-field) format and parses accordingly.
    
    Args:
        filename: Path to CSV file
        
    Returns:
        Tuple of (log_entries, format_type)
        - log_entries: List of EnhancedLogEntry objects
        - format_type: 'enhanced', 'legacy', or 'unknown'
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If format is unrecognized or parsing fails
    """
    entries = []
    format_type = 'unknown'
    
    try:
        with open(filename, 'r') as f:
            reader = csv.DictReader(f)
            
            # Detect format from header
            if reader.fieldnames:
                header_line = ','.join(reader.fieldnames)
                format_type = detect_csv_format(header_line)
                
                if format_type == 'unknown':
                    raise ValueError(f"Unrecognized CSV format in {filename}")
                
                if format_type == 'legacy':
                    logger.warning(f"Loading legacy 8-field format from {filename}")
                    logger.warning("Enhanced metrics not available:")
                    logger.warning("  - Throughput calculation (requires packet_size)")
                    logger.warning("  - End-to-end latency (requires tx_timestamp)")
                    logger.warning("  - Queue congestion analysis (requires queue_depth)")
                    logger.warning("  - Error correlation (requires errors field)")
                else:
                    logger.info(f"Loading enhanced 12-field format from {filename}")
            
            # Parse rows
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                try:
                    entry = EnhancedLogEntry.from_csv_row(row, format_type)
                    entries.append(entry)
                except ValueError as e:
                    logger.warning(f"Skipping row {row_num} in {filename}: {e}")
                    continue
        
        logger.info(f"Loaded {len(entries)} entries from {filename} ({format_type} format)")
        return entries, format_type
        
    except FileNotFoundError:
        logger.error(f"File not found: {filename}")
        raise
    except Exception as e:
        logger.error(f"Error loading flight log from {filename}: {e}")
        raise


def handle_unknown_format(filename: str):
    """
    Handle unrecognized CSV format by logging detailed error information.
    
    Args:
        filename: Path to the file with unknown format
        
    Raises:
        ValueError: Always raises with detailed format information
    """
    logger.error(f"Unrecognized CSV format in {filename}")
    logger.info("Expected formats:")
    logger.info("  Enhanced: 12 fields with packet_size, tx_timestamp, queue_depth, errors")
    logger.info("  Legacy: 8 fields ending with event")
    raise ValueError(f"Unrecognized CSV format in {filename}")


def warn_legacy_format(filename: str):
    """
    Warn user about legacy format limitations.
    
    Args:
        filename: Path to the legacy format file
    """
    logger.warning(f"Loading legacy 8-field format from {filename}")
    logger.warning("Enhanced metrics not available:")
    logger.warning("  - Throughput calculation (requires packet_size)")
    logger.warning("  - End-to-end latency (requires tx_timestamp)")
    logger.warning("  - Queue congestion analysis (requires queue_depth)")
    logger.warning("  - Error correlation (requires errors field)")
