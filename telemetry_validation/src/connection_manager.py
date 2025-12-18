"""
Connection Manager for Telemetry Validation System

Handles serial and UDP connections to the Ground Control Station with
auto-reconnect capabilities and connection health monitoring.
"""

import serial
import socket
import time
import logging
from enum import Enum
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConnectionType(Enum):
    """Supported connection types"""
    SERIAL = 1
    UDP = 2


class ConnectionManager:
    """
    Manages connections to the Ground Control Station via serial or UDP.
    
    Supports:
    - Serial port connections with configurable baud rate
    - UDP socket connections for network telemetry
    - Automatic reconnection with configurable interval
    - Connection health monitoring
    """
    
    def __init__(self, conn_type: ConnectionType, **kwargs):
        """
        Initialize connection manager.
        
        Args:
            conn_type: Type of connection (SERIAL or UDP)
            **kwargs: Connection-specific parameters
                For SERIAL: port (str), baudrate (int), timeout (float)
                For UDP: host (str), port (int), timeout (float)
        """
        self.conn_type = conn_type
        self.connection = None
        self.connected = False
        self.reconnect_interval = kwargs.get('reconnect_interval', 5)  # seconds
        self.last_read_time = 0
        self.connection_attempts = 0
        
        # Serial-specific parameters
        if conn_type == ConnectionType.SERIAL:
            self.port = kwargs.get('port', '/dev/ttyUSB0')
            self.baudrate = kwargs.get('baudrate', 115200)
            self.timeout = kwargs.get('timeout', 1.0)
            logger.info(f"Initialized for SERIAL: port={self.port}, baudrate={self.baudrate}")
        
        # UDP-specific parameters
        elif conn_type == ConnectionType.UDP:
            self.host = kwargs.get('host', '0.0.0.0')
            self.udp_port = kwargs.get('port', 14550)
            self.timeout = kwargs.get('timeout', 1.0)
            logger.info(f"Initialized for UDP: host={self.host}, port={self.udp_port}")
    
    def connect(self) -> bool:
        """
        Establish connection to the Ground Control Station.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        self.connection_attempts += 1
        
        try:
            if self.conn_type == ConnectionType.SERIAL:
                logger.info(f"Attempting serial connection to {self.port} at {self.baudrate} baud...")
                self.connection = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    write_timeout=self.timeout
                )
                
                # Validate connection by checking if port is open
                if not self.connection.is_open:
                    raise serial.SerialException("Port failed to open")
                
                logger.info(f"Serial connection established (attempt {self.connection_attempts})")
            
            elif self.conn_type == ConnectionType.UDP:
                logger.info(f"Attempting UDP connection on {self.host}:{self.udp_port}...")
                self.connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.connection.bind((self.host, self.udp_port))
                self.connection.settimeout(self.timeout)
                logger.info(f"UDP socket bound and listening (attempt {self.connection_attempts})")
            
            self.connected = True
            self.last_read_time = time.time()
            self.connection_attempts = 0  # Reset on successful connection
            return True
            
        except serial.SerialException as e:
            logger.error(f"Serial connection failed: {e}")
            self.connected = False
            return False
        except socket.error as e:
            logger.error(f"UDP connection failed: {e}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected connection error: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Close the connection gracefully."""
        if self.connection:
            try:
                if self.conn_type == ConnectionType.SERIAL:
                    self.connection.close()
                    logger.info("Serial connection closed")
                elif self.conn_type == ConnectionType.UDP:
                    self.connection.close()
                    logger.info("UDP socket closed")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            finally:
                self.connection = None
                self.connected = False
    
    def read(self, size: int = 1024) -> bytes:
        """
        Read data from the connection.
        
        Args:
            size: Maximum number of bytes to read
            
        Returns:
            bytes: Data read from connection, empty bytes if error or no data
        """
        if not self.connected:
            return b''
        
        try:
            if self.conn_type == ConnectionType.SERIAL:
                # Read available data up to size
                data = self.connection.read(size)
                if data:
                    self.last_read_time = time.time()
                return data
            
            elif self.conn_type == ConnectionType.UDP:
                # Receive UDP packet
                data, addr = self.connection.recvfrom(size)
                if data:
                    self.last_read_time = time.time()
                    logger.debug(f"Received {len(data)} bytes from {addr}")
                return data
                
        except serial.SerialException as e:
            logger.error(f"Serial read error: {e}")
            self.connected = False
            return b''
        except socket.timeout:
            # Timeout is normal, just return empty
            return b''
        except socket.error as e:
            logger.error(f"UDP read error: {e}")
            self.connected = False
            return b''
        except Exception as e:
            logger.error(f"Unexpected read error: {e}")
            self.connected = False
            return b''
    
    def is_healthy(self) -> bool:
        """
        Check connection health.
        
        Returns:
            bool: True if connection is healthy, False otherwise
        """
        if not self.connected:
            return False
        
        # Check if we've received data recently (within 30 seconds)
        time_since_last_read = time.time() - self.last_read_time
        if time_since_last_read > 30:
            logger.warning(f"No data received for {time_since_last_read:.1f} seconds")
            return False
        
        # For serial, check if port is still open
        if self.conn_type == ConnectionType.SERIAL:
            try:
                if not self.connection.is_open:
                    logger.warning("Serial port is no longer open")
                    self.connected = False
                    return False
            except Exception:
                self.connected = False
                return False
        
        return True
    
    def auto_reconnect(self) -> bool:
        """
        Attempt to reconnect if disconnected.
        
        This method will block until connection is established or can be
        called periodically in a loop.
        
        Returns:
            bool: True if reconnected successfully, False if still disconnected
        """
        if self.connected and self.is_healthy():
            return True
        
        # Disconnect cleanly if partially connected
        if self.connection:
            self.disconnect()
        
        logger.info(f"Attempting to reconnect in {self.reconnect_interval} seconds...")
        time.sleep(self.reconnect_interval)
        
        return self.connect()
    
    def get_status(self) -> dict:
        """
        Get current connection status information.
        
        Returns:
            dict: Status information including connection state, type, and parameters
        """
        status = {
            'connected': self.connected,
            'type': self.conn_type.name,
            'healthy': self.is_healthy() if self.connected else False,
            'last_read_time': self.last_read_time,
            'time_since_last_read': time.time() - self.last_read_time if self.last_read_time > 0 else None
        }
        
        if self.conn_type == ConnectionType.SERIAL:
            status.update({
                'port': self.port,
                'baudrate': self.baudrate,
                'is_open': self.connection.is_open if self.connection else False
            })
        elif self.conn_type == ConnectionType.UDP:
            status.update({
                'host': self.host,
                'port': self.udp_port
            })
        
        return status
