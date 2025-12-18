#!/usr/bin/env python3
"""
Flight Log Downloader - Download LittleFS logs from Heltec modules

Downloads flight logs from drone Heltec modules via USB Serial.
Logs are in CSV format matching telemetry_validation app for easy comparison.

Usage:
    python3 download_flight_logs.py <port> <output_file>
    
Examples:
    python3 download_flight_logs.py /dev/cu.usbserial-0 drone1_log.csv
    python3 download_flight_logs.py /dev/cu.usbserial-1 drone2_primary_log.csv
    python3 download_flight_logs.py /dev/cu.usbserial-2 drone2_secondary_log.csv

Commands sent to device:
    DUMP  - Download entire log file
    SIZE  - Show log file size
    CLEAR - Delete log file
    HELP  - Show available commands
"""

import serial
import time
import sys
import argparse
import os

# Import format detection utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'telemetry_validation', 'src'))
try:
    from csv_utils import detect_csv_format
except ImportError:
    # Fallback if csv_utils not available
    def detect_csv_format(header_line):
        """Fallback format detection"""
        fields = [f.strip() for f in header_line.strip().split(',')]
        if len(fields) == 12 and 'packet_size' in fields:
            return 'enhanced'
        elif len(fields) == 8 and 'event' in fields:
            return 'legacy'
        return 'unknown'

def send_command(ser, command):
    """Send command to device and wait for response"""
    ser.write(f"{command}\n".encode())
    time.sleep(0.2)

def download_log(port, output_file, baudrate=115200):
    """Download log file from device"""
    try:
        print(f"Connecting to {port} @ {baudrate} baud...")
        ser = serial.Serial(port, baudrate, timeout=2)
        time.sleep(2)  # Wait for connection to stabilize
        
        # Clear any pending data
        ser.reset_input_buffer()
        
        # Get log size first
        print("Checking log size...")
        send_command(ser, "SIZE")
        time.sleep(0.5)
        
        # Read size response
        while ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                print(f"  {line}")
        
        # Send DUMP command
        print(f"\nDownloading log from {port}...")
        send_command(ser, "DUMP")
        time.sleep(0.5)
        
        # Read log data
        log_data = []
        in_dump = False
        line_count = 0
        
        while True:
            if not ser.in_waiting:
                time.sleep(0.1)
                continue
                
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            
            if "LOG DUMP START" in line:
                in_dump = True
                print("  Receiving data...")
                continue
            elif "LOG DUMP END" in line:
                print(f"  Received {line_count} lines")
                break
            elif in_dump and line:
                log_data.append(line)
                line_count += 1
                if line_count % 100 == 0:
                    print(f"  Progress: {line_count} lines...")
        
        # Write to file
        if log_data:
            with open(output_file, 'w') as f:
                f.write('\n'.join(log_data))
                f.write('\n')  # Add final newline
            
            print(f"\n✓ Successfully saved {line_count} lines to {output_file}")
            print(f"  File size: {len('\n'.join(log_data))} bytes")
            
            # Validate format after download completes
            if log_data:
                format_type = detect_csv_format(log_data[0])
                print(f"  Detected format: {format_type}")
                
                if format_type == 'enhanced':
                    print("  ✓ Enhanced 12-field format detected")
                    print("    Available metrics: throughput, latency, queue depth, errors")
                elif format_type == 'legacy':
                    print("  ⚠ Legacy 8-field format detected")
                    print("    Limited metrics: RSSI, SNR, packet rate only")
                elif format_type == 'unknown':
                    print("  ⚠ WARNING: Unrecognized CSV format")
                    print("    Expected formats:")
                    print("      - Enhanced: 12 fields with packet_size, tx_timestamp, queue_depth, errors")
                    print("      - Legacy: 8 fields ending with event")
        else:
            print("\n✗ No log data received (log file may be empty)")
        
        ser.close()
        return True
        
    except serial.SerialException as e:
        print(f"\n✗ Serial error: {e}")
        print(f"  Make sure {port} is correct and device is connected")
        return False
    except KeyboardInterrupt:
        print("\n\n✗ Download cancelled by user")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return False

def list_ports():
    """List available serial ports"""
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        if ports:
            print("\nAvailable serial ports:")
            for port in ports:
                print(f"  {port.device} - {port.description}")
        else:
            print("\nNo serial ports found")
    except ImportError:
        print("Install pyserial to list ports: pip3 install pyserial")

def main():
    parser = argparse.ArgumentParser(
        description='Download flight logs from Heltec modules',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s /dev/cu.usbserial-0 drone1_log.csv
  %(prog)s /dev/cu.usbserial-1 drone2_primary_log.csv
  %(prog)s --list

Commands you can send manually via serial monitor:
  DUMP  - Download entire log file
  SIZE  - Show log file size
  CLEAR - Delete log file
  HELP  - Show available commands
        '''
    )
    
    parser.add_argument('port', nargs='?', help='Serial port (e.g., /dev/cu.usbserial-0)')
    parser.add_argument('output', nargs='?', help='Output CSV file')
    parser.add_argument('-b', '--baud', type=int, default=115200, help='Baud rate (default: 115200)')
    parser.add_argument('-l', '--list', action='store_true', help='List available serial ports')
    
    args = parser.parse_args()
    
    if args.list:
        list_ports()
        return
    
    if not args.port or not args.output:
        parser.print_help()
        print("\nTip: Use --list to see available ports")
        sys.exit(1)
    
    success = download_log(args.port, args.output, args.baud)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
