# ConnectionManager Module

## Overview

The ConnectionManager module provides a unified interface for connecting to Ground Control Stations via serial ports or UDP sockets. It includes automatic reconnection, health monitoring, and comprehensive error handling.

## Features

- **Dual Connection Support**: Serial (UART) and UDP network connections
- **Auto-Reconnect**: Automatic reconnection with configurable intervals
- **Health Monitoring**: Track connection state and data freshness
- **Error Handling**: Graceful handling of all connection errors
- **Logging**: Comprehensive logging for debugging and monitoring

## Quick Start

### Serial Connection

```python
from connection_manager import ConnectionManager, ConnectionType

# Create manager for serial connection
manager = ConnectionManager(
    ConnectionType.SERIAL,
    port='/dev/ttyUSB0',      # Linux/Mac
    # port='COM3',            # Windows
    baudrate=115200,
    timeout=1.0
)

# Connect
if manager.connect():
    print("Connected!")
    
    # Read data
    while True:
        data = manager.read(1024)
        if data:
            print(f"Received {len(data)} bytes")
        
        # Check health
        if not manager.is_healthy():
            print("Connection unhealthy, reconnecting...")
            manager.auto_reconnect()
```

### UDP Connection

```python
from connection_manager import ConnectionManager, ConnectionType

# Create manager for UDP connection
manager = ConnectionManager(
    ConnectionType.UDP,
    host='0.0.0.0',
    port=14550,
    timeout=1.0
)

# Connect (bind socket)
if manager.connect():
    print("Listening for UDP packets...")
    
    # Read packets
    while True:
        data = manager.read(1024)
        if data:
            print(f"Received packet: {len(data)} bytes")
```

## API Reference

### ConnectionType Enum

```python
class ConnectionType(Enum):
    SERIAL = 1  # Serial/UART connection
    UDP = 2     # UDP network connection
```

### ConnectionManager Class

#### Constructor

```python
ConnectionManager(conn_type: ConnectionType, **kwargs)
```

**Parameters:**
- `conn_type`: Type of connection (SERIAL or UDP)
- `**kwargs`: Connection-specific parameters

**Serial Parameters:**
- `port` (str): Serial port path (e.g., '/dev/ttyUSB0', 'COM3')
- `baudrate` (int): Baud rate (default: 115200)
- `timeout` (float): Read timeout in seconds (default: 1.0)
- `reconnect_interval` (int): Seconds between reconnect attempts (default: 5)

**UDP Parameters:**
- `host` (str): Host address to bind (default: '0.0.0.0')
- `port` (int): UDP port number (default: 14550)
- `timeout` (float): Read timeout in seconds (default: 1.0)
- `reconnect_interval` (int): Seconds between reconnect attempts (default: 5)

#### Methods

##### connect() -> bool

Establish connection to the Ground Control Station.

**Returns:** `True` if successful, `False` otherwise

**Example:**
```python
if manager.connect():
    print("Connected successfully")
else:
    print("Connection failed")
```

##### disconnect()

Close the connection gracefully.

**Example:**
```python
manager.disconnect()
```

##### read(size: int = 1024) -> bytes

Read data from the connection.

**Parameters:**
- `size` (int): Maximum bytes to read (default: 1024)

**Returns:** Data as bytes, empty bytes if no data or error

**Example:**
```python
data = manager.read(1024)
if data:
    print(f"Received: {data.hex()}")
```

##### is_healthy() -> bool

Check if connection is healthy.

**Returns:** `True` if healthy, `False` otherwise

A connection is considered unhealthy if:
- Not connected
- No data received in last 30 seconds
- Serial port is closed

**Example:**
```python
if not manager.is_healthy():
    print("Connection unhealthy!")
    manager.auto_reconnect()
```

##### auto_reconnect() -> bool

Attempt to reconnect if disconnected.

**Returns:** `True` if reconnected, `False` if still disconnected

This method will:
1. Check if already connected and healthy
2. Disconnect cleanly if partially connected
3. Wait for reconnect_interval seconds
4. Attempt to connect

**Example:**
```python
while not manager.auto_reconnect():
    print("Reconnection failed, retrying...")
```

##### get_status() -> dict

Get current connection status information.

**Returns:** Dictionary with status information

**Status Fields:**
- `connected` (bool): Connection state
- `type` (str): Connection type name
- `healthy` (bool): Health status
- `last_read_time` (float): Timestamp of last read
- `time_since_last_read` (float): Seconds since last read

**Serial-specific fields:**
- `port` (str): Serial port path
- `baudrate` (int): Baud rate
- `is_open` (bool): Port open state

**UDP-specific fields:**
- `host` (str): Bound host address
- `port` (int): Bound port number

**Example:**
```python
status = manager.get_status()
print(f"Connected: {status['connected']}")
print(f"Type: {status['type']}")
print(f"Healthy: {status['healthy']}")
```

## Error Handling

The ConnectionManager handles all connection errors gracefully:

### Serial Errors
- `serial.SerialException`: Port not found, permission denied, etc.
- Connection state set to `False` on error
- Logged at ERROR level

### UDP Errors
- `socket.error`: Address in use, permission denied, etc.
- `socket.timeout`: Normal timeout, returns empty bytes
- Connection state set to `False` on error (except timeout)
- Logged at ERROR level

### General Errors
- All unexpected exceptions caught and logged
- Connection state set to `False` on error

## Logging

The module uses Python's standard logging module:

```python
import logging

# Configure logging level
logging.basicConfig(level=logging.INFO)

# Or get the logger
logger = logging.getLogger('connection_manager')
logger.setLevel(logging.DEBUG)
```

**Log Levels:**
- `INFO`: Connection events (connect, disconnect, reconnect)
- `WARNING`: Connection health issues
- `ERROR`: Connection failures and errors
- `DEBUG`: Detailed operation information

## Best Practices

### 1. Always Check Connection State

```python
if manager.connect():
    # Connection successful
    pass
else:
    # Handle connection failure
    pass
```

### 2. Monitor Health Regularly

```python
while True:
    data = manager.read(1024)
    
    # Check health periodically
    if not manager.is_healthy():
        manager.auto_reconnect()
```

### 3. Handle Disconnection Gracefully

```python
try:
    while True:
        data = manager.read(1024)
        if data:
            process_data(data)
except KeyboardInterrupt:
    manager.disconnect()
    print("Disconnected cleanly")
```

### 4. Use Context Manager Pattern (Future Enhancement)

```python
# Future enhancement - not yet implemented
with ConnectionManager(ConnectionType.SERIAL, port='/dev/ttyUSB0') as manager:
    data = manager.read(1024)
# Automatically disconnects
```

## Common Issues

### Serial Port Permission Denied

**Problem:** `serial.SerialException: [Errno 13] Permission denied`

**Solution:**
```bash
# Linux: Add user to dialout group
sudo usermod -a -G dialout $USER
# Log out and back in

# Or use sudo (not recommended for production)
sudo python3 your_script.py
```

### UDP Port Already in Use

**Problem:** `socket.error: [Errno 48] Address already in use`

**Solution:**
- Check if another process is using port 14550
- Use a different port
- Wait for the port to be released

### No Data Received

**Problem:** Connection successful but no data

**Solution:**
- Verify the Ground Station is transmitting
- Check baud rate matches (serial)
- Check port number matches (UDP)
- Verify cable connections (serial)
- Check firewall settings (UDP)

## Requirements Compliance

This module satisfies the following requirements:

- **8.1**: Connects to Ground Station's serial port or network interface
- **8.2**: Configures serial port with matching baud rate (115200/57600)
- **8.3**: Listens for UDP MAVLink packets on port 14550
- **8.4**: Attempts to reconnect every 5 seconds on connection loss

## Dependencies

- `pyserial>=3.5`: Serial port communication
- Python standard library: `socket`, `time`, `logging`, `enum`, `typing`

## Testing

Run the validation script:
```bash
python3 validate_connection_manager.py
```

Run unit tests (requires pytest):
```bash
pytest tests/test_connection_manager.py -v
```

## Examples

See `examples/connection_manager_example.py` for complete usage examples.

## License

Part of the Telemetry Validation System for dual-controller LoRa relay system.
