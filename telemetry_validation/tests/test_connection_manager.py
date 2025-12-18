"""
Unit tests for ConnectionManager

Tests serial and UDP connection functionality, error handling,
and auto-reconnect logic.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import socket
import serial
from src.connection_manager import ConnectionManager, ConnectionType


class TestConnectionManagerSerial(unittest.TestCase):
    """Test serial connection functionality"""
    
    @patch('serial.Serial')
    def test_serial_connect_success(self, mock_serial):
        """Test successful serial connection"""
        # Setup mock
        mock_conn = Mock()
        mock_conn.is_open = True
        mock_serial.return_value = mock_conn
        
        # Create manager and connect
        manager = ConnectionManager(
            ConnectionType.SERIAL,
            port='/dev/ttyUSB0',
            baudrate=115200
        )
        result = manager.connect()
        
        # Verify
        self.assertTrue(result)
        self.assertTrue(manager.connected)
        mock_serial.assert_called_once_with(
            port='/dev/ttyUSB0',
            baudrate=115200,
            timeout=1.0,
            write_timeout=1.0
        )
    
    @patch('serial.Serial')
    def test_serial_connect_failure(self, mock_serial):
        """Test serial connection failure"""
        # Setup mock to raise exception
        mock_serial.side_effect = serial.SerialException("Port not found")
        
        # Create manager and attempt connect
        manager = ConnectionManager(
            ConnectionType.SERIAL,
            port='/dev/ttyUSB0',
            baudrate=115200
        )
        result = manager.connect()
        
        # Verify
        self.assertFalse(result)
        self.assertFalse(manager.connected)
    
    @patch('serial.Serial')
    def test_serial_read_success(self, mock_serial):
        """Test reading data from serial connection"""
        # Setup mock
        mock_conn = Mock()
        mock_conn.is_open = True
        mock_conn.read.return_value = b'\xfe\x09\x00\x00'
        mock_serial.return_value = mock_conn
        
        # Create manager, connect, and read
        manager = ConnectionManager(ConnectionType.SERIAL, port='/dev/ttyUSB0')
        manager.connect()
        data = manager.read(1024)
        
        # Verify
        self.assertEqual(data, b'\xfe\x09\x00\x00')
        mock_conn.read.assert_called_once_with(1024)
    
    @patch('serial.Serial')
    def test_serial_read_error(self, mock_serial):
        """Test serial read error handling"""
        # Setup mock
        mock_conn = Mock()
        mock_conn.is_open = True
        mock_conn.read.side_effect = serial.SerialException("Read error")
        mock_serial.return_value = mock_conn
        
        # Create manager, connect, and read
        manager = ConnectionManager(ConnectionType.SERIAL, port='/dev/ttyUSB0')
        manager.connect()
        data = manager.read(1024)
        
        # Verify
        self.assertEqual(data, b'')
        self.assertFalse(manager.connected)
    
    @patch('serial.Serial')
    def test_serial_disconnect(self, mock_serial):
        """Test serial disconnection"""
        # Setup mock
        mock_conn = Mock()
        mock_conn.is_open = True
        mock_serial.return_value = mock_conn
        
        # Create manager, connect, and disconnect
        manager = ConnectionManager(ConnectionType.SERIAL, port='/dev/ttyUSB0')
        manager.connect()
        manager.disconnect()
        
        # Verify
        self.assertFalse(manager.connected)
        self.assertIsNone(manager.connection)
        mock_conn.close.assert_called_once()


class TestConnectionManagerUDP(unittest.TestCase):
    """Test UDP connection functionality"""
    
    @patch('socket.socket')
    def test_udp_connect_success(self, mock_socket):
        """Test successful UDP connection"""
        # Setup mock
        mock_conn = Mock()
        mock_socket.return_value = mock_conn
        
        # Create manager and connect
        manager = ConnectionManager(
            ConnectionType.UDP,
            host='0.0.0.0',
            port=14550
        )
        result = manager.connect()
        
        # Verify
        self.assertTrue(result)
        self.assertTrue(manager.connected)
        mock_conn.bind.assert_called_once_with(('0.0.0.0', 14550))
        mock_conn.settimeout.assert_called_once_with(1.0)
    
    @patch('socket.socket')
    def test_udp_connect_failure(self, mock_socket):
        """Test UDP connection failure"""
        # Setup mock to raise exception
        mock_conn = Mock()
        mock_conn.bind.side_effect = socket.error("Address already in use")
        mock_socket.return_value = mock_conn
        
        # Create manager and attempt connect
        manager = ConnectionManager(
            ConnectionType.UDP,
            host='0.0.0.0',
            port=14550
        )
        result = manager.connect()
        
        # Verify
        self.assertFalse(result)
        self.assertFalse(manager.connected)
    
    @patch('socket.socket')
    def test_udp_read_success(self, mock_socket):
        """Test reading data from UDP connection"""
        # Setup mock
        mock_conn = Mock()
        mock_conn.recvfrom.return_value = (b'\xfd\x09\x00\x00', ('127.0.0.1', 12345))
        mock_socket.return_value = mock_conn
        
        # Create manager, connect, and read
        manager = ConnectionManager(ConnectionType.UDP, port=14550)
        manager.connect()
        data = manager.read(1024)
        
        # Verify
        self.assertEqual(data, b'\xfd\x09\x00\x00')
        mock_conn.recvfrom.assert_called_once_with(1024)
    
    @patch('socket.socket')
    def test_udp_read_timeout(self, mock_socket):
        """Test UDP read timeout handling"""
        # Setup mock
        mock_conn = Mock()
        mock_conn.recvfrom.side_effect = socket.timeout()
        mock_socket.return_value = mock_conn
        
        # Create manager, connect, and read
        manager = ConnectionManager(ConnectionType.UDP, port=14550)
        manager.connect()
        data = manager.read(1024)
        
        # Verify - timeout should return empty bytes but keep connection alive
        self.assertEqual(data, b'')
        self.assertTrue(manager.connected)
    
    @patch('socket.socket')
    def test_udp_disconnect(self, mock_socket):
        """Test UDP disconnection"""
        # Setup mock
        mock_conn = Mock()
        mock_socket.return_value = mock_conn
        
        # Create manager, connect, and disconnect
        manager = ConnectionManager(ConnectionType.UDP, port=14550)
        manager.connect()
        manager.disconnect()
        
        # Verify
        self.assertFalse(manager.connected)
        self.assertIsNone(manager.connection)
        mock_conn.close.assert_called_once()


class TestConnectionManagerReconnect(unittest.TestCase):
    """Test auto-reconnect functionality"""
    
    @patch('serial.Serial')
    @patch('time.sleep')
    def test_auto_reconnect_success(self, mock_sleep, mock_serial):
        """Test successful auto-reconnect"""
        # Setup mock
        mock_conn = Mock()
        mock_conn.is_open = True
        mock_serial.return_value = mock_conn
        
        # Create manager
        manager = ConnectionManager(
            ConnectionType.SERIAL,
            port='/dev/ttyUSB0',
            reconnect_interval=5
        )
        
        # Simulate disconnection
        manager.connected = False
        
        # Attempt reconnect
        result = manager.auto_reconnect()
        
        # Verify
        self.assertTrue(result)
        self.assertTrue(manager.connected)
        mock_sleep.assert_called_once_with(5)
    
    @patch('serial.Serial')
    def test_is_healthy_connected(self, mock_serial):
        """Test health check on connected manager"""
        # Setup mock
        mock_conn = Mock()
        mock_conn.is_open = True
        mock_serial.return_value = mock_conn
        
        # Create manager and connect
        manager = ConnectionManager(ConnectionType.SERIAL, port='/dev/ttyUSB0')
        manager.connect()
        
        # Verify health
        self.assertTrue(manager.is_healthy())
    
    def test_is_healthy_disconnected(self):
        """Test health check on disconnected manager"""
        # Create manager without connecting
        manager = ConnectionManager(ConnectionType.SERIAL, port='/dev/ttyUSB0')
        
        # Verify not healthy
        self.assertFalse(manager.is_healthy())
    
    @patch('serial.Serial')
    def test_get_status(self, mock_serial):
        """Test status information retrieval"""
        # Setup mock
        mock_conn = Mock()
        mock_conn.is_open = True
        mock_serial.return_value = mock_conn
        
        # Create manager and connect
        manager = ConnectionManager(
            ConnectionType.SERIAL,
            port='/dev/ttyUSB0',
            baudrate=115200
        )
        manager.connect()
        
        # Get status
        status = manager.get_status()
        
        # Verify
        self.assertTrue(status['connected'])
        self.assertEqual(status['type'], 'SERIAL')
        self.assertEqual(status['port'], '/dev/ttyUSB0')
        self.assertEqual(status['baudrate'], 115200)
        self.assertTrue(status['is_open'])


if __name__ == '__main__':
    unittest.main()
