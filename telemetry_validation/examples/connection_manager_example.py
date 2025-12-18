"""
Example usage of ConnectionManager

Demonstrates how to use the ConnectionManager for both serial and UDP connections.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from connection_manager import ConnectionManager, ConnectionType


def example_serial_connection():
    """Example: Connect to Ground Station via serial port"""
    print("=" * 60)
    print("Example 1: Serial Connection")
    print("=" * 60)
    
    # Create connection manager for serial
    manager = ConnectionManager(
        ConnectionType.SERIAL,
        port='/dev/ttyUSB0',  # Adjust for your system
        baudrate=115200,
        timeout=1.0
    )
    
    # Connect
    print("\nAttempting to connect...")
    if manager.connect():
        print("✅ Connected successfully!")
        
        # Get status
        status = manager.get_status()
        print(f"\nConnection Status:")
        print(f"  Type: {status['type']}")
        print(f"  Port: {status['port']}")
        print(f"  Baudrate: {status['baudrate']}")
        print(f"  Connected: {status['connected']}")
        
        # Read some data
        print("\nReading data for 5 seconds...")
        start_time = time.time()
        bytes_received = 0
        
        while time.time() - start_time < 5:
            data = manager.read(1024)
            if data:
                bytes_received += len(data)
                print(f"  Received {len(data)} bytes")
            time.sleep(0.1)
        
        print(f"\nTotal bytes received: {bytes_received}")
        
        # Disconnect
        manager.disconnect()
        print("✅ Disconnected")
    else:
        print("❌ Connection failed")


def example_udp_connection():
    """Example: Connect to Ground Station via UDP"""
    print("\n" + "=" * 60)
    print("Example 2: UDP Connection")
    print("=" * 60)
    
    # Create connection manager for UDP
    manager = ConnectionManager(
        ConnectionType.UDP,
        host='0.0.0.0',
        port=14550,
        timeout=1.0
    )
    
    # Connect
    print("\nAttempting to bind UDP socket...")
    if manager.connect():
        print("✅ UDP socket bound successfully!")
        
        # Get status
        status = manager.get_status()
        print(f"\nConnection Status:")
        print(f"  Type: {status['type']}")
        print(f"  Host: {status['host']}")
        print(f"  Port: {status['port']}")
        print(f"  Connected: {status['connected']}")
        
        # Listen for data
        print("\nListening for UDP packets for 5 seconds...")
        start_time = time.time()
        packets_received = 0
        
        while time.time() - start_time < 5:
            data = manager.read(1024)
            if data:
                packets_received += 1
                print(f"  Received packet {packets_received}: {len(data)} bytes")
            time.sleep(0.1)
        
        print(f"\nTotal packets received: {packets_received}")
        
        # Disconnect
        manager.disconnect()
        print("✅ Disconnected")
    else:
        print("❌ Connection failed")


def example_auto_reconnect():
    """Example: Auto-reconnect on connection loss"""
    print("\n" + "=" * 60)
    print("Example 3: Auto-Reconnect")
    print("=" * 60)
    
    # Create connection manager
    manager = ConnectionManager(
        ConnectionType.SERIAL,
        port='/dev/ttyUSB0',
        baudrate=115200,
        reconnect_interval=2  # Shorter interval for demo
    )
    
    print("\nStarting connection with auto-reconnect...")
    print("(This will attempt to reconnect every 2 seconds if disconnected)")
    
    # Try to connect with auto-reconnect
    for attempt in range(3):
        print(f"\nAttempt {attempt + 1}:")
        
        if manager.auto_reconnect():
            print("✅ Connected!")
            
            # Check health
            if manager.is_healthy():
                print("✅ Connection is healthy")
            else:
                print("⚠️  Connection may have issues")
            
            break
        else:
            print("❌ Connection failed, will retry...")
    
    if manager.connected:
        manager.disconnect()


def example_health_monitoring():
    """Example: Monitor connection health"""
    print("\n" + "=" * 60)
    print("Example 4: Health Monitoring")
    print("=" * 60)
    
    # Create connection manager
    manager = ConnectionManager(
        ConnectionType.SERIAL,
        port='/dev/ttyUSB0',
        baudrate=115200
    )
    
    if manager.connect():
        print("✅ Connected")
        
        # Monitor health for 10 seconds
        print("\nMonitoring connection health...")
        for i in range(10):
            status = manager.get_status()
            health = "✅ Healthy" if status['healthy'] else "❌ Unhealthy"
            time_since_read = status.get('time_since_last_read', 0)
            
            print(f"  [{i+1}/10] {health} - Last read: {time_since_read:.1f}s ago")
            
            # Try to read data
            data = manager.read(1024)
            if data:
                print(f"         Received {len(data)} bytes")
            
            time.sleep(1)
        
        manager.disconnect()
    else:
        print("❌ Connection failed")


if __name__ == '__main__':
    print("\nConnectionManager Usage Examples")
    print("=" * 60)
    print("\nNote: These examples require actual hardware connections.")
    print("Modify the port/host settings to match your setup.")
    print("\nUncomment the example you want to run:\n")
    
    # Uncomment the example you want to run:
    # example_serial_connection()
    # example_udp_connection()
    # example_auto_reconnect()
    # example_health_monitoring()
    
    print("\nTo run an example, uncomment it in the script and run again.")
