#!/usr/bin/env python3
"""
Investigate Throughput Drop Script

This script analyzes CSV logs to find where throughput drops to 0
and inspects the surrounding log entries to understand why.
"""

import sys
import os
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.csv_utils import load_flight_log
from src.metrics_calculator import MetricsCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def investigate_drop(log_file: str):
    logger.info(f"Investigating {log_file}...")
    
    try:
        entries, format_type = load_flight_log(log_file)
    except Exception as e:
        logger.error(f"Failed to load {log_file}: {e}")
        return

    if not entries:
        logger.warning("No entries found.")
        return

    # Sort entries by timestamp
    entries.sort(key=lambda x: x.timestamp_ms)

    # Calculate throughput in 1-second windows
    calculator = MetricsCalculator()
    # We need to access the raw calculation to map back to timestamps
    # The calculator returns a list of values, but we want to know *which* window corresponds to 0.
    
    # Let's manually calculate to have better control
    window_size_ms = 1000
    start_time = entries[0].timestamp_ms
    end_time = entries[-1].timestamp_ms
    
    current_window_start = start_time
    current_window_bytes = 0
    
    windows = []
    
    # Group entries by window
    window_entries = []
    
    for entry in entries:
        while entry.timestamp_ms >= current_window_start + window_size_ms:
            # Window finished
            throughput_bps = current_window_bytes * 8 # bits per second (approx, if window is 1s)
            windows.append({
                'start_ms': current_window_start,
                'throughput_bps': throughput_bps,
                'entries': window_entries
            })
            
            # Move to next window
            current_window_start += window_size_ms
            current_window_bytes = 0
            window_entries = []
            
        if entry.timestamp_ms >= current_window_start:
            current_window_bytes += entry.packet_size
            window_entries.append(entry)
            
    # Check for drops to 0
    drops = [w for w in windows if w['throughput_bps'] == 0]
    
    logger.info(f"Found {len(drops)} windows with 0 throughput out of {len(windows)} total windows.")
    
    if drops:
        # Inspect the first few drops
        for i, drop in enumerate(drops[:5]):
            logger.info(f"\nDrop #{i+1} at {drop['start_ms']} ms:")
            logger.info(f"  Entries in this window: {len(drop['entries'])}")
            for entry in drop['entries']:
                logger.info(f"    Time: {entry.timestamp_ms}, Event: {entry.event}, Size: {entry.packet_size}, Seq: {entry.sequence_number}")
                
        # Check if there are long periods of 0 throughput
        consecutive_zeros = 0
        max_consecutive_zeros = 0
        start_zero_seq = 0
        max_start_zero_seq = 0
        
        for w in windows:
            if w['throughput_bps'] == 0:
                if consecutive_zeros == 0:
                    start_zero_seq = w['start_ms']
                consecutive_zeros += 1
            else:
                if consecutive_zeros > max_consecutive_zeros:
                    max_consecutive_zeros = consecutive_zeros
                    max_start_zero_seq = start_zero_seq
                consecutive_zeros = 0
        
        if consecutive_zeros > max_consecutive_zeros:
             max_consecutive_zeros = consecutive_zeros
             max_start_zero_seq = start_zero_seq
             
        logger.info(f"Longest zero sequence: {max_consecutive_zeros} seconds, starting at {max_start_zero_seq} ms")

        # Check for suspicious zero-size packets
        suspicious_packets = []
        for entry in entries:
            if entry.packet_size == 0 and entry.event != 'QUEUE_METRICS':
                suspicious_packets.append(entry)
        
        if suspicious_packets:
            logger.info(f"Found {len(suspicious_packets)} suspicious zero-size packets (not QUEUE_METRICS):")
            for p in suspicious_packets[:10]:
                logger.info(f"  Time: {p.timestamp_ms}, Event: {p.event}, Size: {p.packet_size}")
        else:
            logger.info("No suspicious zero-size packets found (all zero-size are QUEUE_METRICS).")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python investigate_drop.py <log_file>")
        sys.exit(1)
        
    investigate_drop(sys.argv[1])
