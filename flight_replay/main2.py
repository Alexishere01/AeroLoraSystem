#!/usr/bin/env python3
"""
Flight Replay v2 - Enhanced with Per-Node Metrics
PyQt6 + PyQtGraph with individual node metric boxes
"""

import sys
import pandas as pd
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QPushButton, QSlider, QComboBox, 
                              QLabel, QFileDialog, QGridLayout, QGroupBox,
                              QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QPalette, QColor
import pyqtgraph as pg

# Configure PyQtGraph for performance
pg.setConfigOptions(antialias=True, enableExperimental=False)

# ============================================================================
# CONSTANTS
# ============================================================================

NEON_GREEN = '#00FF00'
NEON_RED = '#FF0000'
NEON_CYAN = '#00FFFF'
NEON_YELLOW = '#FFFF00'
BG_COLOR = '#000000'
GRID_COLOR = '#1a1a1a'

MAVLINK_MSGS = {
    0: "Heartbeat", 1: "Sys Status", 2: "System Time", 11: "Set Mode", 
    20: "Param Request Read", 21: "Param Request List", 22: "Param Value", 
    23: "Param Set", 24: "GPS Raw", 25: "GPS Status", 27: "Raw IMU", 
    29: "Scaled Pressure", 30: "Attitude", 31: "Attitude Quaternion", 
    32: "Local Pos NED", 33: "Global Pos", 42: "Mission Current", 
    43: "Mission Request", 44: "Mission Set Current", 62: "Nav Controller Output",
    65: "RC Channels", 66: "RC Request", 69: "Manual Control", 74: "VFR HUD", 
    75: "Command Long", 76: "Command Ack", 77: "Command Int", 
    87: "Position Target", 100: "Optical Flow Rad", 105: "HIL GPS", 
    109: "Radio Status", 110: "HIL State", 111: "Timesync", 125: "Power Status", 
    130: "Scaled IMU2", 132: "Scaled IMU3", 136: "Terrain Request", 
    147: "Battery Status", 152: "Autopilot Version", 163: "RC Channels Override",
    168: "Camera Feedback", 178: "Camera Settings", 193: "Video Stream Info",
    230: "Estimator Status", 241: "Vibration", 242: "Home Position",
    253: "StatusText", 300: "Protocol Version", 310: "Logging Data", 
    311: "Logging Ack"
}

# ============================================================================
# DATA LOADER
# ============================================================================

class TelemetryData:
    def __init__(self):
        self.drone_df = None
        self.ground902_df = None
        self.ground930_df = None
        self.relay_df = None
        self.master_df = None
        self.max_time = 0.0
    
    def _find_csv_header(self, filepath):
        """Find the line number where the actual CSV header starts (skipping ESP boot messages)."""
        with open(filepath, 'r') as f:
            for i, line in enumerate(f):
                if 'timestamp_ms' in line:
                    return list(range(i))  # Skip all lines before the header
        return None  # No skip if header is on first line
        
    def load_files(self, drone_path=None, ground902_path=None, ground930_path=None, 
                   relay_path=None):
        """Load CSV files and synchronize timestamps."""
        
        dfs = {}
        start_times = []
        
        # Load each file
        if drone_path:
            # Skip ESP boot messages - find the line with timestamp_ms header
            skip_rows = self._find_csv_header(drone_path)
            self.drone_df = pd.read_csv(drone_path, skiprows=skip_rows)
            self.drone_df['timestamp_ms'] = pd.to_numeric(self.drone_df['timestamp_ms'], errors='coerce')
            self.drone_df['source'] = 'Drone'
            dfs['drone'] = self.drone_df
            start_times.append(self.drone_df['timestamp_ms'].min())
            
        if ground902_path:
            skip_rows = self._find_csv_header(ground902_path)
            self.ground902_df = pd.read_csv(ground902_path, skiprows=skip_rows)
            self.ground902_df['timestamp_ms'] = pd.to_numeric(self.ground902_df['timestamp_ms'], errors='coerce')
            self.ground902_df['source'] = 'Ground 902'
            dfs['ground902'] = self.ground902_df
            start_times.append(self.ground902_df['timestamp_ms'].min())
            
        if ground930_path:
            skip_rows = self._find_csv_header(ground930_path)
            self.ground930_df = pd.read_csv(ground930_path, skiprows=skip_rows)
            self.ground930_df['timestamp_ms'] = pd.to_numeric(self.ground930_df['timestamp_ms'], errors='coerce')
            self.ground930_df['source'] = 'Ground 930'
            dfs['ground930'] = self.ground930_df
            start_times.append(self.ground930_df['timestamp_ms'].min())
            
        # Load relay file
        if relay_path:
            skip_rows = self._find_csv_header(relay_path)
            self.relay_df = pd.read_csv(relay_path, skiprows=skip_rows)
            self.relay_df['timestamp_ms'] = pd.to_numeric(self.relay_df['timestamp_ms'], errors='coerce')
            self.relay_df['source'] = 'Relay'
            dfs['relay'] = self.relay_df
            start_times.append(self.relay_df['timestamp_ms'].min())
        
        if not start_times:
            return False
            
        # Normalize timestamps
        global_start = min(start_times)
        
        # Calculate time_s for each dataframe
        for key, df in dfs.items():
            df['time_s'] = (df['timestamp_ms'] - global_start) / 1000.0
            
        # Combine for event log
        self.master_df = pd.concat(dfs.values(), ignore_index=True).sort_values('time_s')
        self.max_time = self.master_df['time_s'].max()
        
        print(f"Loaded {len(self.master_df)} events. Duration: {self.max_time:.1f}s")
        return True

# ============================================================================
# MAIN WINDOW
# ============================================================================

class FlightReplayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data = TelemetryData()
        self.current_time = 0.0
        self.playing = False
        self.playback_speed = 1.0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        
        # Metric labels dict
        self.metric_labels = {}
        
        # Last known values (persist instead of showing N/A)
        self.last_values = {
            'drone_rssi': 0,
            'ground902_rssi': 0,
            'ground902_snr': 0,
            'ground930_rssi': 0,
            'ground930_snr': 0
        }
        
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Flight Replay v2 - Per-Node Metrics")
        self.setGeometry(100, 100, 1400, 900)
        
        # Dark theme
        self.set_dark_theme()
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        # Top: Control bar
        control_layout = self.create_control_bar()
        main_layout.addLayout(control_layout)
        
        # Per-Node Metric Boxes
        node_metrics_layout = self.create_node_metrics()
        main_layout.addLayout(node_metrics_layout)
        
        # Event log table - Expanded to fill space
        event_group = QGroupBox("📡 Event Log (Recent Packets)")
        event_layout = QVBoxLayout()
        
        self.event_table = QTableWidget()
        self.event_table.setColumnCount(5)
        self.event_table.setHorizontalHeaderLabels(['Time (s)', 'Source', 'Event', 'Message', 'RSSI'])
        self.event_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Removed fixed height to allow expanding
        self.event_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.event_table.setStyleSheet("background-color: #0a0a0a; color: #00FF00;")
        
        event_layout.addWidget(self.event_table)
        event_group.setLayout(event_layout)
        main_layout.addWidget(event_group)
        
    def set_dark_theme(self):
        """Apply cyberpunk dark theme."""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 255, 65))
        palette.setColor(QPalette.ColorRole.Base, QColor(10, 10, 10))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(20, 20, 20))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, QColor(0, 255, 65))
        palette.setColor(QPalette.ColorRole.Button, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 255, 65))
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 100, 0))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        self.setPalette(palette)
        
    def create_control_bar(self):
        """Create playback controls."""
        layout = QVBoxLayout()
        
        # File selection section
        file_group = QGroupBox("📁 Log Files")
        file_layout = QGridLayout()
        
        self.file_paths = {}
        self.file_labels = {}
        
        nodes = [
            ("Drone", "Drone1 (Target)"),
            ("Ground_902", "Ground 902 MHz"),
            ("Ground_930", "Ground 930 MHz (QGC)"),
            ("Relay", "Relay (Drone2)")
        ]
        
        row = 0
        for key, label in nodes:
            # Label
            lbl = QLabel(f"{label}:")
            file_layout.addWidget(lbl, row, 0)
            
            # File path display
            path_label = QLabel("Not loaded")
            path_label.setStyleSheet("color: #666666; font-style: italic;")
            file_layout.addWidget(path_label, row, 1)
            self.file_labels[key] = path_label
            
            # Browse button
            btn = QPushButton("Browse...")
            btn.clicked.connect(lambda checked, k=key: self.browse_file(k))
            file_layout.addWidget(btn, row, 2)
            
            row += 1
            
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # Playback controls
        playback_layout = QHBoxLayout()
        
        # Load button
        self.load_btn = QPushButton("🚀 Load & Start")
        self.load_btn.clicked.connect(self.load_data)
        self.load_btn.setMinimumHeight(40)
        self.load_btn.setStyleSheet("font-size: 14pt; font-weight: bold;")
        playback_layout.addWidget(self.load_btn)
        
        # Play/Pause
        self.play_btn = QPushButton("▶️ Play")
        self.play_btn.clicked.connect(self.toggle_playback)
        self.play_btn.setEnabled(False)
        self.play_btn.setMinimumHeight(40)
        playback_layout.addWidget(self.play_btn)
        
        # Speed selector
        speed_label = QLabel("Speed:")
        playback_layout.addWidget(speed_label)
        
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1x", "2x", "5x", "10x"])
        self.speed_combo.setCurrentIndex(1)
        self.speed_combo.currentTextChanged.connect(self.change_speed)
        playback_layout.addWidget(self.speed_combo)
        
        # Time slider
        time_label = QLabel("Time:")
        playback_layout.addWidget(time_label)
        
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(1000)
        self.time_slider.valueChanged.connect(self.slider_changed)
        self.time_slider.setEnabled(False)
        playback_layout.addWidget(self.time_slider, 10)
        
        self.time_label = QLabel("0.0s / 0.0s")
        self.time_label.setMinimumWidth(150)
        playback_layout.addWidget(self.time_label)
        
        layout.addLayout(playback_layout)
        
        return layout
    
    def create_node_metrics(self):
        """Create per-node metric boxes."""
        layout = QGridLayout()
        
        # Create 4 node boxes in 2x2 grid
        nodes = [
            ("Drone", "🎯 DRONE (TARGET)", 0, 0),
            ("Ground902", "📡 GROUND 902 MHz", 0, 1),
            ("Ground930", "📡 GROUND 930 MHz", 1, 0),
            ("Relay", "🔄 RELAY", 1, 1)
        ]
        
        for node_key, node_title, row, col in nodes:
            box = self.create_metric_box(node_key, node_title)
            layout.addWidget(box, row, col)
        
        return layout
    
    def create_metric_box(self, node_key, title):
        """Create a single metric box for a node."""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #00FF41;
                border-radius: 8px;
                margin-top: 1ex;
                font-weight: bold;
                font-size: 12pt;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #00FFFF;
            }
        """)
        
        layout = QGridLayout()
        
        # Define metrics based on node type
        if node_key == "Drone":
            metrics = [
                ("TX", "Packets TX:"),
                ("RX", "Packets RX:"),
                ("Queue", "Queue Depth:"),
                ("Drops", "Drops:"),
                ("RSSI", "Signal:")
            ]
        elif "Ground" in node_key:
            metrics = [
                ("RX", "Packets RX:"),
                ("RSSI", "RSSI:"),
                ("SNR", "SNR:"),
                ("Loss", "Loss Rate:"),
                ("Status", "Status:")
            ]
        else:  # Relay
            metrics = [
                ("Forwarded", "Forwarded:"),
                ("Queue", "Queue Depth:"),
                ("Drops", "Drops:"),
                ("Status", "Status:"),
                ("Active", "Link Quality:")
            ]
        
        row = 0
        for metric_key, metric_label in metrics:
            # Label
            lbl = QLabel(metric_label)
            lbl.setStyleSheet("color: #a0a0a0; font-size: 10pt;")
            layout.addWidget(lbl, row, 0)
            
            # Value
            value_lbl = QLabel("--")
            value_lbl.setStyleSheet("color: #00FF00; font-size: 11pt; font-weight: bold;")
            layout.addWidget(value_lbl, row, 1)
            
            # Store reference
            self.metric_labels[f"{node_key}_{metric_key}"] = value_lbl
            
            row += 1
        
        group.setLayout(layout)
        return group
    

    
    # ========================================================================
    # DATA LOADING
    # ========================================================================
    
    def browse_file(self, key):
        """Browse for a specific log file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            f"Select {key} Log", 
            "", 
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            self.file_paths[key] = file_path
            # Show filename only
            import os
            self.file_labels[key].setText(os.path.basename(file_path))
            self.file_labels[key].setStyleSheet("color: #00FF00;")
    
    def load_data(self):
        """Load telemetry files."""
        from PyQt6.QtWidgets import QMessageBox
        
        # Map UI keys to data loader parameters
        drone_path = self.file_paths.get("Drone")
        ground902_path = self.file_paths.get("Ground_902")
        ground930_path = self.file_paths.get("Ground_930")
        relay_path = self.file_paths.get("Relay")
        
        # Validation: Either all nodes OR minimum of Drone1 + Ground 930
        has_minimum = drone_path and ground930_path
        has_all = drone_path and ground902_path and ground930_path and relay_path
        
        if not (has_minimum or has_all):
            QMessageBox.warning(self, "Insufficient Files", 
                              "Please load either:\n" +
                              "• All nodes (Drone1, Ground 902, Ground 930, Relay), OR\n" +
                              "• Minimum setup (Drone1 + Ground 930)")
            return
        
        success = self.data.load_files(drone_path, ground902_path, ground930_path, relay_path)
        
        if success:
            self.time_slider.setEnabled(True)
            self.play_btn.setEnabled(True)
            self.time_slider.setMaximum(int(self.data.max_time * 10))  # 0.1s resolution
            self.time_label.setText(f"0.0s / {self.data.max_time:.1f}s")
            QMessageBox.information(self, "Success", f"Loaded {len(self.data.master_df)} events\nDuration: {self.data.max_time:.1f}s")
        else:
            QMessageBox.warning(self, "Error", "Failed to load data")
            
    # ========================================================================
    # PLAYBACK CONTROL
    # ========================================================================
    
    def toggle_playback(self):
        """Start/stop animation."""
        self.playing = not self.playing
        
        if self.playing:
            self.play_btn.setText("⏸ Pause")
            self.timer.start(33)  # 30 FPS
        else:
            self.play_btn.setText("▶️ Play")
            self.timer.stop()
            
    def change_speed(self, text):
        """Update playback speed."""
        self.playback_speed = float(text.replace('x', ''))
        
    def slider_changed(self, value):
        """Manual slider control."""
        if not self.playing:
            self.current_time = value / 10.0
            self.update_visualizations()
            
    def update_frame(self):
        """Called by timer at 30 FPS."""
        # Advance time
        self.current_time += (0.033 * self.playback_speed)
        
        # Loop or stop
        if self.current_time > self.data.max_time:
            self.current_time = 0.0
            
        # Update slider
        self.time_slider.blockSignals(True)
        self.time_slider.setValue(int(self.current_time * 10))
        self.time_slider.blockSignals(False)
        
        # Update visuals
        self.update_visualizations()
        
    # ========================================================================
    # VISUALIZATION UPDATE
    # ========================================================================
    
    def update_visualizations(self):
        """Render current frame."""
        t = self.current_time
        self.time_label.setText(f"{t:.1f}s / {self.data.max_time:.1f}s")
        
        # Update node metrics
        self.update_node_metrics(t)
        
        # Update event log
        self.update_event_log(t)
    
    def update_node_metrics(self, t):
        """Update all node metric boxes."""
        # Drone metrics
        if self.data.drone_df is not None:
            drone_data = self.data.drone_df[self.data.drone_df['time_s'] <= t]
            if not drone_data.empty:
                tx = len(drone_data[drone_data['event'].str.contains('TX', na=False)])
                rx = len(drone_data[drone_data['event'].str.contains('RX', na=False)])
                queue = drone_data.iloc[-1].get('queue_depth', 0)
                
                # Calculate drops from tier drop columns - use last valid value
                drops = 0
                tier_cols = ['tier0_drops_full', 'tier0_drops_stale', 'tier1_drops_full', 
                            'tier1_drops_stale', 'tier2_drops_full', 'tier2_drops_stale']
                for col in tier_cols:
                    if col in drone_data.columns:
                        # Get last non-NaN value
                        valid_values = drone_data[col].dropna()
                        if len(valid_values) > 0:
                            drops += int(valid_values.iloc[-1])
                
                rssi = drone_data.iloc[-1].get('rssi_dbm', self.last_values['drone_rssi'])
                if not pd.isna(rssi) and rssi != 0:
                    self.last_values['drone_rssi'] = rssi
                else:
                    rssi = self.last_values['drone_rssi']
                
                self.metric_labels['Drone_TX'].setText(str(tx))
                self.metric_labels['Drone_RX'].setText(str(rx))
                self.metric_labels['Drone_Queue'].setText(f"{int(queue)} / 30")
                self.metric_labels['Drone_Drops'].setText(str(drops))
                self.metric_labels['Drone_RSSI'].setText(f"{rssi:.0f} dBm")
        
        # Ground 902 MHz metrics
        if self.data.ground902_df is not None:
            g902_data = self.data.ground902_df[self.data.ground902_df['time_s'] <= t]
            if not g902_data.empty:
                rx = len(g902_data[g902_data['event'].str.contains('RX', na=False)])
                latest = g902_data.iloc[-1]
                
                rssi = latest.get('rssi_dbm', self.last_values['ground902_rssi'])
                if not pd.isna(rssi) and rssi != 0:
                    self.last_values['ground902_rssi'] = rssi
                else:
                    rssi = self.last_values['ground902_rssi']
                
                snr = latest.get('snr_db', self.last_values['ground902_snr'])
                if not pd.isna(snr) and snr != 0:
                    self.last_values['ground902_snr'] = snr
                else:
                    snr = self.last_values['ground902_snr']
                
                self.metric_labels['Ground902_RX'].setText(str(rx))
                self.metric_labels['Ground902_RSSI'].setText(f"{rssi:.0f} dBm")
                self.metric_labels['Ground902_SNR'].setText(f"{snr:.1f} dB")
                self.metric_labels['Ground902_Loss'].setText("--")  # Calculate if needed
                
                # Status with color coding
                status = "🟢 Good" if rssi > -85 else "🟡 Weak" if rssi > -100 else "🔴 Jammed"
                self.metric_labels['Ground902_Status'].setText(status)
        
        # Ground 930 MHz metrics
        if self.data.ground930_df is not None:
            g930_data = self.data.ground930_df[self.data.ground930_df['time_s'] <= t]
            if not g930_data.empty:
                rx = len(g930_data[g930_data['event'].str.contains('RX', na=False)])
                latest = g930_data.iloc[-1]
                
                rssi = latest.get('rssi_dbm', self.last_values['ground930_rssi'])
                if not pd.isna(rssi) and rssi != 0:
                    self.last_values['ground930_rssi'] = rssi
                else:
                    rssi = self.last_values['ground930_rssi']
                
                snr = latest.get('snr_db', self.last_values['ground930_snr'])
                if not pd.isna(snr) and snr != 0:
                    self.last_values['ground930_snr'] = snr
                else:
                    snr = self.last_values['ground930_snr']
                
                self.metric_labels['Ground930_RX'].setText(str(rx))
                self.metric_labels['Ground930_RSSI'].setText(f"{rssi:.0f} dBm")
                self.metric_labels['Ground930_SNR'].setText(f"{snr:.1f} dB")
                self.metric_labels['Ground930_Loss'].setText("--")
                
                status = "🟢 Good" if rssi > -85 else "🟡 Weak" if rssi > -100 else "🔴 Jammed"
                self.metric_labels['Ground930_Status'].setText(status)
        
        # Relay metrics
        if self.data.relay_df is not None:
            relay_data = self.data.relay_df[self.data.relay_df['time_s'] <= t]
            if not relay_data.empty:
                # Count both TX and FORWARD events
                forwarded = len(relay_data[relay_data['event'].str.contains('TX|FORWARD', na=False, regex=True)])
                latest = relay_data.iloc[-1]
                queue = latest.get('queue_depth', 0)
                
                # Calculate drops from tier drop columns - use last valid value
                drops = 0
                tier_cols = ['tier0_drops_full', 'tier0_drops_stale', 'tier1_drops_full', 
                            'tier1_drops_stale', 'tier2_drops_full', 'tier2_drops_stale']
                for col in tier_cols:
                    if col in relay_data.columns:
                        valid_values = relay_data[col].dropna()
                        if len(valid_values) > 0:
                            drops += int(valid_values.iloc[-1])
                
                self.metric_labels['Relay_Forwarded'].setText(str(forwarded))
                self.metric_labels['Relay_Queue'].setText(f"{int(queue)} / 30")
                self.metric_labels['Relay_Drops'].setText(str(drops))
                self.metric_labels['Relay_Status'].setText("🟢 Active")
                self.metric_labels['Relay_Active'].setText("Good")
            else:
                self.metric_labels['Relay_Status'].setText("⚫ Inactive")
    

    
    def update_event_log(self, t):
        """Update event log table with recent packets."""
        if self.data.master_df is None or self.data.master_df.empty:
            return
            
        # Get recent events (last 5 seconds)
        recent = self.data.master_df[
            (self.data.master_df['time_s'] <= t) &
            (self.data.master_df['time_s'] >= t - 5.0)
        ].sort_values('time_s', ascending=False).head(20)
        
        # Update table
        self.event_table.setRowCount(len(recent))
        
        for i, (idx, row) in enumerate(recent.iterrows()):
            # Time
            self.event_table.setItem(i, 0, QTableWidgetItem(f"{row['time_s']:.2f}"))
            
            # Source
            self.event_table.setItem(i, 1, QTableWidgetItem(str(row['source'])))
            
            # Event
            event_str = str(row.get('event', 'N/A'))
            self.event_table.setItem(i, 2, QTableWidgetItem(event_str))
            
            # Message (decode MAVLink ID)
            msg_id = row.get('message_id', 0)
            msg_name = MAVLINK_MSGS.get(int(msg_id), f"Msg {msg_id}")
            self.event_table.setItem(i, 3, QTableWidgetItem(msg_name))
            
            # RSSI
            rssi = row.get('rssi_dbm', 0)
            self.event_table.setItem(i, 4, QTableWidgetItem(f"{rssi:.0f} dBm"))

# ============================================================================
# MAIN
# ============================================================================

def main():
    app = QApplication(sys.argv)
    window = FlightReplayWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
