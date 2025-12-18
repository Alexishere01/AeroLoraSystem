"""
MAVLink Parser Example

This example demonstrates how to use the MAVLinkParser class to parse
MAVLink telemetry data from a serial connection or UDP socket.
"""

import sys
import time
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.connection_manager import ConnectionManager, ConnectionType
from src.mavlink_parser import MAVLinkParser


def main():
    """Main example function."""
    print("=" * 60)
    print("MAVLink Parser Example")
    print("=" * 60)
    
    # Initialize parser
    parser = MAVLinkParser()
    print("\n✓ MAVLink parser initialized")
    
    # Initialize connection (using UDP for this example)
    print("\nConnecting to MAVLink stream on UDP port 14550...")
    conn = ConnectionManager(
        ConnectionType.UDP,
        host='0.0.0.0',
        port=14550
    )
    
    if not conn.connect():
        print("✗ Failed to connect. Make sure a MAVLink source is available.")
        print("\nTo test this example:")
        print("  1. Start QGroundControl or another MAVLink source")
        print("  2. Configure it to send MAVLink to UDP port 14550")
        print("  3. Run this script again")
        return
    
    print("✓ Connected successfully")
    
    # Parse messages for 30 seconds
    print("\nParsing MAVLink messages for 30 seconds...")
    print("Press Ctrl+C to stop early\n")
    
    start_time = time.time()
    message_count = 0
    last_stats_time = start_time
    
    try:
        while time.time() - start_time < 30:
            # Read data from connection
            data = conn.read(1024)
            
            if data:
                # Parse the data
                messages = parser.parse_stream(data)
                
                # Process each message
                for msg in messages:
                    message_count += 1
                    
                    # Print interesting messages
                    if msg.msg_type in ['HEARTBEAT', 'GPS_RAW_INT', 'ATTITUDE', 'RADIO_STATUS']:
                        print(f"[{msg.timestamp:.2f}] {msg.msg_type} from system {msg.system_id}")
                        
                        # Show RSSI/SNR if available
                        if msg.rssi is not None:
                            print(f"  └─ Link Quality: RSSI={msg.rssi} dBm, SNR={msg.snr} dB")
                        
                        # Show some key fields
                        if msg.msg_type == 'GPS_RAW_INT':
                            lat = msg.fields.get('lat', 0) / 1e7
                            lon = msg.fields.get('lon', 0) / 1e7
                            alt = msg.fields.get('alt', 0) / 1000
                            sats = msg.fields.get('satellites_visible', 0)
                            print(f"  └─ Position: {lat:.6f}°, {lon:.6f}°, {alt:.1f}m, {sats} sats")
                        
                        elif msg.msg_type == 'ATTITUDE':
                            roll = msg.fields.get('roll', 0)
                            pitch = msg.fields.get('pitch', 0)
                            yaw = msg.fields.get('yaw', 0)
                            print(f"  └─ Attitude: Roll={roll:.2f}, Pitch={pitch:.2f}, Yaw={yaw:.2f}")
            
            # Print statistics every 5 seconds
            if time.time() - last_stats_time >= 5:
                stats = parser.get_stats()
                print("\n" + "─" * 60)
                print("Parser Statistics:")
                print(f"  Total packets: {stats['total_packets']}")
                print(f"  Parse errors: {stats['parse_errors']}")
                print(f"  Checksum errors: {stats['checksum_errors']}")
                print(f"  Error rate: {stats['error_rate']:.2f}%")
                print(f"  Bytes processed: {stats['bytes_processed']}")
                print(f"  Buffer size: {stats['buffer_size']}")
                if stats['last_rssi'] is not None:
                    print(f"  Last RSSI: {stats['last_rssi']} dBm")
                if stats['last_snr'] is not None:
                    print(f"  Last SNR: {stats['last_snr']} dB")
                print("─" * 60 + "\n")
                last_stats_time = time.time()
            
            # Small delay to prevent CPU spinning
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    
    finally:
        # Clean up
        conn.disconnect()
        
        # Print final statistics
        print("\n" + "=" * 60)
        print("Final Statistics")
        print("=" * 60)
        stats = parser.get_stats()
        print(f"Total messages parsed: {message_count}")
        print(f"Total packets: {stats['total_packets']}")
        print(f"Parse errors: {stats['parse_errors']}")
        print(f"Checksum errors: {stats['checksum_errors']}")
        print(f"Error rate: {stats['error_rate']:.2f}%")
        print(f"Bytes processed: {stats['bytes_processed']}")
        
        if message_count > 0:
            duration = time.time() - start_time
            print(f"\nAverage rate: {message_count / duration:.1f} messages/second")
        
        print("\n✓ Example completed")


if __name__ == '__main__':
    main()
