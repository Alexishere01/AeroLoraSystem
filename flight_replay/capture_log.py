import serial
import serial.tools.list_ports
import time
import sys
import threading
from datetime import datetime
import os

def list_ports():
    ports = serial.tools.list_ports.comports()
    return ports

def read_from_port(ser, output_file):
    """Read from serial port and write to file and console."""
    print(f"Listening on {ser.port} at {ser.baudrate}...")
    print(f"Saving to {output_file.name}")
    print("Type 'DUMP' to request log dump, 'CLEAR' to clear log, 'EXIT' to quit.")
    
    while True:
        try:
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='replace')
                print(line, end='') # Print to console
                output_file.write(line) # Write to file
                output_file.flush()
        except serial.SerialException:
            print("\nSerial connection lost.")
            break
        except Exception as e:
            print(f"\nError: {e}")
            break

def main():
    # List ports
    ports = list_ports()
    if not ports:
        print("No serial ports found.")
        return

    print("Available ports:")
    for i, p in enumerate(ports):
        print(f"{i}: {p.device} - {p.description}")

    # Select port
    try:
        selection = int(input("Select port (number): "))
        port = ports[selection].device
    except (ValueError, IndexError):
        print("Invalid selection.")
        return

    # Select baud rate
    baud_rate = 115200
    print(f"Default baud rate: {baud_rate}")
    use_default = input("Use default? (y/n): ").lower()
    if use_default == 'n':
        try:
            baud_rate = int(input("Enter baud rate: "))
        except ValueError:
            print("Invalid baud rate.")
            return

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"log_{timestamp}.csv"
    
    try:
        # Open serial port
        ser = serial.Serial(port, baud_rate, timeout=1)
        ser.dtr = False
        ser.rts = False
        
        # Open output file
        with open(filename, 'w') as f:
            # Start reader thread
            reader_thread = threading.Thread(target=read_from_port, args=(ser, f))
            reader_thread.daemon = True
            reader_thread.start()
            
            # Main loop for user input
            while True:
                user_input = input()
                if user_input.upper() == 'EXIT':
                    break
                elif user_input.upper() in ['DUMP', 'CLEAR', 'SIZE', 'HELP']:
                    # Send with both CR and LF to be safe
                    cmd = user_input + '\r\n'
                    ser.write(cmd.encode())
                    print(f"Sent command: {user_input}")
                else:
                    pass
                    
        ser.close()
        print("Closed.")
        
    except serial.SerialException as e:
        print(f"Could not open port {port}: {e}")
    except KeyboardInterrupt:
        print("\nInterrupted.")

if __name__ == "__main__":
    main()
