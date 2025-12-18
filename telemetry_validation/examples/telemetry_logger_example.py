"""
Example usage of TelemetryLogger module.

This script demonstrates how to use the TelemetryLogger to capture and log
MAVLink telemetry data in multiple formats (CSV, JSON, .tlog).
"""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.connection_manager import ConnectionManager, ConnectionType
from src.mavlink_parser import MAVLinkParser
from src.telemetry_logger import TelemetryLogger


def main():
    """Main example function."""
    print("=" * 60)
    print("TelemetryLogger Example")
    print("=" * 60)
    print()
    
    # Configuration
    log_dir = './example_logs'
    max_file_size_mb = 10  # Rotate files at 10 MB
    
    # Initialize logger
    print(f"Initializing telemetry logger...")
    print(f"  Log directory: {log_dir}")
    print(f"  Max file size: {max_file_size_mb} MB")
    logger = TelemetryLogger(log_dir=log_dir, max_file_size_mb=max_file_size_mb)
    print(f"✓ Logger initialized")
    print()
    
    # Initialize parser
    print("Initializing MAVLink parser...")
    parser = MAVLinkParser()
    print("✓ Parser initialized")
    print()
    
    # Initialize connection (example with UDP)
    print("Initializing connection...")
    print("  Type: UDP")
    print("  Port: 14550")
    conn = ConnectionManager(ConnectionType.UDP, port=14550)
    
    if not conn.connect():
        print("✗ Failed to connect")
        print("\nNote: This example requires a MAVLink source on UDP port 14550")
        print("You can test with QGroundControl or a simulated drone")
        return
    
    print("✓ Connected")
    print()
    
    # Main logging loop
    print("Starting telemetry logging...")
    print("Press Ctrl+C to stop")
    print("-" * 60)
    
    try:
        message_count = 0
        start_time = time.time()
        
        while True:
            # Read data from connection
            data = conn.read(1024)
            
            if data:
                # Parse MAVLink messages
                messages = parser.parse_stream(data)
                
                # Log each message
                for msg in messages:
                    logger.log_message(msg)
                    message_count += 1
                    
                    # Print summary every 10 messages
                    if message_count % 10 == 0:
                        elapsed = time.time() - start_time
                        rate = message_count / elapsed if elapsed > 0 else 0
                        
                        print(f"\rMessages logged: {message_count} | "
                              f"Rate: {rate:.1f} msg/s | "
                              f"Type: {msg.msg_type:20s} | "
                              f"System: {msg.system_id}", end='')
                
                # Display stats every 100 messages
                if message_count % 100 == 0 and message_count > 0:
                    print()
                    print("-" * 60)
                    
                    # Logger stats
                    logger_stats = logger.get_stats()
                    print(f"Logger Statistics:")
                    print(f"  Messages logged: {logger_stats['message_count']}")
                    print(f"  File sequence: {logger_stats['file_sequence']}")
                    print(f"  JSON buffer: {logger_stats['json_buffer_size']} messages")
                    print(f"  CSV file: {Path(logger_stats['csv_file']).name}")
                    print()
                    
                    # Parser stats
                    parser_stats = parser.get_stats()
                    print(f"Parser Statistics:")
                    print(f"  Total packets: {parser_stats['total_packets']}")
                    print(f"  Parse errors: {parser_stats['parse_errors']}")
                    print(f"  Checksum errors: {parser_stats['checksum_errors']}")
                    print(f"  Error rate: {parser_stats['error_rate']:.2f}%")
                    print(f"  Last RSSI: {parser_stats['last_rssi']} dBm")
                    print(f"  Last SNR: {parser_stats['last_snr']} dB")
                    print("-" * 60)
            
            # Small delay to prevent CPU spinning
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\n")
        print("-" * 60)
        print("Stopping telemetry logging...")
    
    finally:
        # Clean up
        print()
        print("Closing connection...")
        conn.disconnect()
        print("✓ Connection closed")
        
        print()
        print("Closing logger...")
        logger.close()
        print("✓ Logger closed")
        
        # Final statistics
        print()
        print("=" * 60)
        print("Final Statistics")
        print("=" * 60)
        
        logger_stats = logger.get_stats()
        parser_stats = parser.get_stats()
        
        elapsed = time.time() - start_time
        avg_rate = message_count / elapsed if elapsed > 0 else 0
        
        print(f"Session duration: {elapsed:.1f} seconds")
        print(f"Total messages: {message_count}")
        print(f"Average rate: {avg_rate:.1f} msg/s")
        print(f"File rotations: {logger_stats['file_sequence']}")
        print(f"Parse errors: {parser_stats['parse_errors']}")
        print(f"Checksum errors: {parser_stats['checksum_errors']}")
        print()
        print(f"Log files saved to: {log_dir}")
        print(f"  - {Path(logger_stats['csv_file']).name}")
        print(f"  - {Path(logger_stats['json_file']).name}")
        print(f"  - {Path(logger_stats['tlog_file']).name}")
        print()


def example_with_serial():
    """Example using serial connection instead of UDP."""
    print("=" * 60)
    print("TelemetryLogger Example (Serial)")
    print("=" * 60)
    print()
    
    # Configuration
    serial_port = '/dev/ttyUSB0'  # Adjust for your system
    baudrate = 57600
    log_dir = './serial_logs'
    
    # Initialize components
    logger = TelemetryLogger(log_dir=log_dir)
    parser = MAVLinkParser()
    conn = ConnectionManager(
        ConnectionType.SERIAL,
        port=serial_port,
        baudrate=baudrate
    )
    
    if not conn.connect():
        print(f"✗ Failed to connect to {serial_port}")
        return
    
    print(f"✓ Connected to {serial_port} at {baudrate} baud")
    print("Logging telemetry... Press Ctrl+C to stop")
    
    try:
        while True:
            data = conn.read(1024)
            if data:
                messages = parser.parse_stream(data)
                for msg in messages:
                    logger.log_message(msg)
                    print(f"Logged: {msg.msg_type} from system {msg.system_id}")
            
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\nStopping...")
    
    finally:
        conn.disconnect()
        logger.close()
        print(f"Logs saved to: {log_dir}")


if __name__ == '__main__':
    # Run main UDP example
    main()
    
    # Uncomment to run serial example instead:
    # example_with_serial()
