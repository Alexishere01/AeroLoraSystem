"""
Mode Tracker Module

This module provides mode detection and tracking for the telemetry validation
system. It monitors operating mode changes (direct vs relay) from binary protocol
status reports and logs mode transitions with timestamps.

Requirements: 6.1, 6.2, 6.3, 6.4
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any
import time
import logging

# Handle both relative and absolute imports
try:
    from .binary_protocol_parser import ParsedBinaryPacket, UartCommand, StatusPayload
except ImportError:
    from binary_protocol_parser import ParsedBinaryPacket, UartCommand, StatusPayload

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OperatingMode(Enum):
    """
    Operating modes for the telemetry system.
    
    Requirements: 6.1
    """
    UNKNOWN = 0      # Mode not yet determined
    DIRECT = 1       # Direct communication (relay_active = False)
    RELAY = 2        # Relay communication (relay_active = True)


@dataclass
class ModeTransition:
    """
    Represents a mode transition event.
    
    Tracks when the system changes between direct and relay modes,
    including timestamp and mode details.
    
    Requirements: 6.1
    """
    timestamp: float                    # Python timestamp (seconds since epoch)
    from_mode: OperatingMode           # Previous mode
    to_mode: OperatingMode             # New mode
    relay_active: bool                 # relay_active field from StatusPayload
    packets_relayed: int               # Total packets relayed at transition
    active_peer_relays: int            # Number of active peer relays
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return (f"ModeTransition(timestamp={self.timestamp:.3f}, "
                f"{self.from_mode.name} -> {self.to_mode.name}, "
                f"packets_relayed={self.packets_relayed})")


class ModeTracker:
    """
    Tracks operating mode changes from binary protocol status reports.
    
    This class monitors CMD_STATUS_REPORT packets to detect when the system
    switches between direct and relay modes. It logs all mode transitions
    with timestamps and provides access to mode history.
    
    Features:
    - Automatic mode detection from relay_active field
    - Mode transition logging with timestamps
    - Mode history tracking
    - Current mode query
    
    Requirements: 6.1
    """
    
    def __init__(self):
        """Initialize the mode tracker."""
        self.current_mode = OperatingMode.UNKNOWN
        self.mode_transitions: List[ModeTransition] = []
        self.last_status_timestamp = 0.0
        
        # Statistics
        self.stats = {
            'total_transitions': 0,
            'direct_mode_count': 0,
            'relay_mode_count': 0,
            'status_reports_processed': 0
        }
        
        # Timing
        self.start_time = time.time()
        self.direct_mode_start_time: Optional[float] = None
        self.relay_mode_start_time: Optional[float] = None
        self.total_direct_time = 0.0
        self.total_relay_time = 0.0
        
        logger.info("Mode tracker initialized")
    
    def update(self, packet: ParsedBinaryPacket):
        """
        Update mode tracking with a binary protocol packet.
        
        Processes CMD_STATUS_REPORT packets to detect mode changes and
        log transitions.
        
        Args:
            packet: Parsed binary protocol packet
            
        Requirements: 6.1
        """
        # Only process status report commands
        if packet.command != UartCommand.CMD_STATUS_REPORT:
            return
        
        # Ensure payload is StatusPayload
        if not isinstance(packet.payload, StatusPayload):
            return
        
        self.stats['status_reports_processed'] += 1
        status = packet.payload
        
        # Detect mode from relay_active field
        new_mode = OperatingMode.RELAY if status.relay_active else OperatingMode.DIRECT
        
        # Check for mode transition
        if new_mode != self.current_mode and self.current_mode != OperatingMode.UNKNOWN:
            self._record_transition(packet.timestamp, new_mode, status)
        
        # Update current mode
        if self.current_mode == OperatingMode.UNKNOWN:
            # First mode detection
            self.current_mode = new_mode
            logger.info(f"Initial mode detected: {new_mode.name}")
            
            # Start timing for this mode
            if new_mode == OperatingMode.DIRECT:
                self.direct_mode_start_time = packet.timestamp
            elif new_mode == OperatingMode.RELAY:
                self.relay_mode_start_time = packet.timestamp
        
        self.last_status_timestamp = packet.timestamp
    
    def _record_transition(self, timestamp: float, new_mode: OperatingMode, 
                          status: StatusPayload):
        """
        Record a mode transition event.
        
        Logs the transition and updates statistics and timing.
        
        Args:
            timestamp: Timestamp of the transition
            new_mode: New operating mode
            status: StatusPayload with mode details
            
        Requirements: 6.1
        """
        # Update timing for previous mode
        if self.current_mode == OperatingMode.DIRECT and self.direct_mode_start_time:
            self.total_direct_time += (timestamp - self.direct_mode_start_time)
            self.direct_mode_start_time = None
        elif self.current_mode == OperatingMode.RELAY and self.relay_mode_start_time:
            self.total_relay_time += (timestamp - self.relay_mode_start_time)
            self.relay_mode_start_time = None
        
        # Create transition record
        transition = ModeTransition(
            timestamp=timestamp,
            from_mode=self.current_mode,
            to_mode=new_mode,
            relay_active=status.relay_active,
            packets_relayed=status.packets_relayed,
            active_peer_relays=status.active_peer_relays
        )
        
        self.mode_transitions.append(transition)
        self.stats['total_transitions'] += 1
        
        # Update mode counts
        if new_mode == OperatingMode.DIRECT:
            self.stats['direct_mode_count'] += 1
            self.direct_mode_start_time = timestamp
        elif new_mode == OperatingMode.RELAY:
            self.stats['relay_mode_count'] += 1
            self.relay_mode_start_time = timestamp
        
        # Log transition
        logger.info(f"Mode transition: {self.current_mode.name} -> {new_mode.name} "
                   f"at {timestamp:.3f}, packets_relayed={status.packets_relayed}, "
                   f"active_peer_relays={status.active_peer_relays}")
        
        # Update current mode
        self.current_mode = new_mode
    
    def get_current_mode(self) -> OperatingMode:
        """
        Get the current operating mode.
        
        Returns:
            Current OperatingMode
            
        Requirements: 6.1
        """
        return self.current_mode
    
    def get_mode_transitions(self) -> List[ModeTransition]:
        """
        Get all recorded mode transitions.
        
        Returns:
            List of ModeTransition objects in chronological order
            
        Requirements: 6.1
        """
        return self.mode_transitions.copy()
    
    def get_mode_duration(self, mode: OperatingMode) -> float:
        """
        Get total time spent in a specific mode.
        
        Args:
            mode: Operating mode to query
            
        Returns:
            Total time in seconds spent in the specified mode
            
        Requirements: 6.1
        """
        now = time.time()
        
        if mode == OperatingMode.DIRECT:
            total = self.total_direct_time
            # Add current session if in direct mode
            if self.current_mode == OperatingMode.DIRECT and self.direct_mode_start_time:
                total += (now - self.direct_mode_start_time)
            return total
        
        elif mode == OperatingMode.RELAY:
            total = self.total_relay_time
            # Add current session if in relay mode
            if self.current_mode == OperatingMode.RELAY and self.relay_mode_start_time:
                total += (now - self.relay_mode_start_time)
            return total
        
        return 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get mode tracking statistics.
        
        Returns:
            Dictionary with mode tracking statistics
            
        Requirements: 6.1
        """
        uptime = time.time() - self.start_time
        direct_time = self.get_mode_duration(OperatingMode.DIRECT)
        relay_time = self.get_mode_duration(OperatingMode.RELAY)
        
        return {
            'current_mode': self.current_mode.name,
            'total_transitions': self.stats['total_transitions'],
            'direct_mode_count': self.stats['direct_mode_count'],
            'relay_mode_count': self.stats['relay_mode_count'],
            'status_reports_processed': self.stats['status_reports_processed'],
            'direct_mode_time_seconds': direct_time,
            'relay_mode_time_seconds': relay_time,
            'direct_mode_percentage': (direct_time / uptime * 100.0) if uptime > 0 else 0.0,
            'relay_mode_percentage': (relay_time / uptime * 100.0) if uptime > 0 else 0.0,
            'uptime_seconds': uptime
        }
    
    def reset_stats(self):
        """Reset all statistics and mode history."""
        self.current_mode = OperatingMode.UNKNOWN
        self.mode_transitions.clear()
        self.last_status_timestamp = 0.0
        
        for key in self.stats:
            self.stats[key] = 0
        
        self.start_time = time.time()
        self.direct_mode_start_time = None
        self.relay_mode_start_time = None
        self.total_direct_time = 0.0
        self.total_relay_time = 0.0
        
        logger.info("Mode tracker statistics reset")
