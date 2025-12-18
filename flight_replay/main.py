#!/usr/bin/env python3
"""
Flight Replay - High-Performance Desktop Application
PyQt6 + PyQtGraph for smooth 30 FPS telemetry visualization
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
        self.ground_df = None
        self.primary_df = None
        self.secondary_df = None
        self.master_df = None
        self.max_time = 0.0
        
    def load_files(self, drone_path=None, ground_path=None, primary_path=None, secondary_path=None):
        """Load CSV files and synchronize timestamps."""
        
        dfs = {}
        start_times = []
        
        # Load each file
        if drone_path:
            self.drone_df = pd.read_csv(drone_path)
            self.drone_df['source'] = 'Drone'
            dfs['drone'] = self.drone_df
            start_times.append(self.drone_df['timestamp_ms'].min())
            
        if ground_path:
            self.ground_df = pd.read_csv(ground_path)
            self.ground_df['source'] = 'Ground'
            dfs['ground'] = self.ground_df
            start_times.append(self.ground_df['timestamp_ms'].min())
            
        if primary_path:
            self.primary_df = pd.read_csv(primary_path)
            self.primary_df['source'] = 'Relay Primary'
            dfs['primary'] = self.primary_df
            start_times.append(self.primary_df['timestamp_ms'].min())
            
        if secondary_path:
            self.secondary_df = pd.read_csv(secondary_path)
            self.secondary_df['source'] = 'Relay Secondary'
            dfs['secondary'] = self.secondary_df
            start_times.append(self.secondary_df['timestamp_ms'].min())
        
        if not start_times:
            return False
            
        # Normalize timestamps
        global_start = min(start_times)
        
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
        
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Flight Replay - AeroLoRa Telemetry")
        self.setGeometry(100, 100, 1600, 900)
        
        # Dark theme
        self.set_dark_theme()
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        # Top: Control bar
        control_layout = self.create_control_bar()
        main_layout.addLayout(control_layout)
        
        # Middle: Main content (Left=Topology, Right=Plots)
        content_layout = QHBoxLayout()
        
        # Left: Topology + Event Log (30%)
        left_layout = QVBoxLayout()
        
        self.topology_widget = self.create_topology()
        left_layout.addWidget(self.topology_widget, 4)
        
        # Event log table
        event_group = QGroupBox("📡 Event Log (Recent Packets)")
        event_layout = QVBoxLayout()
        
        self.event_table = QTableWidget()
        self.event_table.setColumnCount(5)
        self.event_table.setHorizontalHeaderLabels(['Time (s)', 'Source', 'Event', 'Message', 'RSSI'])
        self.event_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.event_table.setMaximumHeight(250)
        self.event_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.event_table.setStyleSheet("background-color: #0a0a0a; color: #00FF00;")
        
        event_layout.addWidget(self.event_table)
        event_group.setLayout(event_layout)
        left_layout.addWidget(event_group, 3)
        
        content_layout.addLayout(left_layout, 3)
        
        # Right: Plots (70%)
        plots_layout = self.create_plots()
        content_layout.addLayout(plots_layout, 7)
        
        main_layout.addLayout(content_layout)
        
        # Bottom: Metrics bar
        metrics_layout = self.create_metrics()
        main_layout.addLayout(metrics_layout)
        
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
            ("Drone1", "Drone1 (Target)"),
            ("Ground_930", "Ground 930 MHz"),
            ("Ground_902", "Ground 902 MHz"),
            ("Relay_Primary", "Relay Primary"),
            ("Relay_Secondary", "Relay Secondary")
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
        
    def create_topology(self):
        """Create network topology visualization."""
        widget = pg.PlotWidget()
        widget.setBackground(BG_COLOR)
        widget.setAspectLocked(True)
        widget.hideAxis('bottom')
        widget.hideAxis('left')
        widget.setTitle("Network Topology", color=NEON_GREEN, size='14pt')
        
        # Store references
        self.topo_plot = widget.getPlotItem()
        
        # Node positions
        self.node_positions = {
            'Drone': (0, 1),
            'Relay': (1, 0.5),
            'Ground': (0.5, 0)
        }
        
        # Create node scatter
        x = [p[0] for p in self.node_positions.values()]
        y = [p[1] for p in self.node_positions.values()]
        self.topo_nodes = pg.ScatterPlotItem(
            x=x, y=y, size=30, 
            brush=pg.mkBrush(30, 30, 30), 
            pen=pg.mkPen(NEON_GREEN, width=2)
        )
        self.topo_plot.addItem(self.topo_nodes)
        
        # Add labels
        for name, (px, py) in self.node_positions.items():
            text = pg.TextItem(name, color=NEON_GREEN, anchor=(0.5, 0.5))
            text.setPos(px, py + 0.15)
            self.topo_plot.addItem(text)
        
        # Link lines (will be updated dynamically)
        self.direct_link = pg.PlotDataItem(pen=pg.mkPen(NEON_GREEN, width=2, style=Qt.PenStyle.DashLine))
        self.relay_link1 = pg.PlotDataItem(pen=pg.mkPen(NEON_CYAN, width=2, style=Qt.PenStyle.DashLine))
        self.relay_link2 = pg.PlotDataItem(pen=pg.mkPen(NEON_CYAN, width=2, style=Qt.PenStyle.DashLine))
        
        self.topo_plot.addItem(self.direct_link)
        self.topo_plot.addItem(self.relay_link1)
        self.topo_plot.addItem(self.relay_link2)
        
        return widget
        
    def create_plots(self):
        """Create telemetry plots."""
        layout = QVBoxLayout()
        
        # Plot 1: Signal Integrity (RSSI/SNR)
        self.signal_plot = pg.PlotWidget()
        self.signal_plot.setBackground(BG_COLOR)
        self.signal_plot.setTitle("Signal Quality", color=NEON_GREEN, size='12pt')
        self.signal_plot.setLabel('left', 'dBm', color=NEON_GREEN)
        self.signal_plot.setLabel('bottom', 'Time (s)', color=NEON_GREEN)
        self.signal_plot.showGrid(x=True, y=True, alpha=0.2)
        
        self.rssi_curve = self.signal_plot.plot(pen=pg.mkPen(NEON_GREEN, width=2), name='RSSI')
        self.snr_curve = self.signal_plot.plot(pen=pg.mkPen(NEON_YELLOW, width=2), name='SNR')
        
        # Sensitivity line
        self.signal_plot.addLine(y=-95, pen=pg.mkPen(NEON_RED, width=1, style=Qt.PenStyle.DashLine))
        
        layout.addWidget(self.signal_plot)
        
        # Plot 2: Queue Depth
        self.queue_plot = pg.PlotWidget()
        self.queue_plot.setBackground(BG_COLOR)
        self.queue_plot.setTitle("Network Congestion", color=NEON_GREEN, size='12pt')
        self.queue_plot.setLabel('left', 'Packets', color=NEON_GREEN)
        self.queue_plot.setLabel('bottom', 'Time (s)', color=NEON_GREEN)
        self.queue_plot.showGrid(x=True, y=True, alpha=0.2)
        
        self.queue_curve = self.queue_plot.plot(
            pen=pg.mkPen(NEON_CYAN, width=2),
            fillLevel=0,
            brush=pg.mkBrush(0, 255, 255, 50)
        )
        
        layout.addWidget(self.queue_plot)
        
        # Plot 3: Throughput
        self.throughput_plot = pg.PlotWidget()
        self.throughput_plot.setBackground(BG_COLOR)
        self.throughput_plot.setTitle("Bandwidth Usage", color=NEON_GREEN, size='12pt')
        self.throughput_plot.setLabel('left', 'Kbps', color=NEON_GREEN)
        self.throughput_plot.setLabel('bottom', 'Time (s)', color=NEON_GREEN)
        self.throughput_plot.showGrid(x=True, y=True, alpha=0.2)
        
        self.throughput_curve = self.throughput_plot.plot(pen=pg.mkPen(NEON_YELLOW, width=2))
        
        layout.addWidget(self.throughput_plot)
        
        return layout
        
    def create_metrics(self):
        """Create live metrics display."""
        layout = QHBoxLayout()
        
        # Create metric boxes
        self.metric_labels = {}
        
        metrics = [
            ("Signal Quality", "N/A"),
            ("Network Status", "N/A"),
            ("Throughput", "0.0 Kbps"),
            ("Last Message", "None")
        ]
        
        for name, default in metrics:
            box = QGroupBox(name)
            box_layout = QVBoxLayout()
            
            label = QLabel(default)
            label.setFont(QFont("Courier", 16, QFont.Weight.Bold))
            label.setStyleSheet(f"color: {NEON_GREEN};")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            box_layout.addWidget(label)
            box.setLayout(box_layout)
            layout.addWidget(box)
            
            self.metric_labels[name] = label
            
        return layout
        
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
        drone_path = self.file_paths.get("Drone1")
        ground_path = self.file_paths.get("Ground_930") or self.file_paths.get("Ground_902")
        primary_path = self.file_paths.get("Relay_Primary")
        secondary_path = self.file_paths.get("Relay_Secondary")
        
        # At least one file required
        if not any([drone_path, ground_path, primary_path, secondary_path]):
            QMessageBox.warning(self, "No Files", "Please select at least one log file.")
            return
        
        success = self.data.load_files(drone_path, ground_path, primary_path, secondary_path)
        
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
        
        # Filter data up to current time
        if self.data.ground_df is not None:
            ground_mask = self.data.ground_df['time_s'] <= t
            ground_visible = self.data.ground_df[ground_mask]
            
            # Update RSSI plot (convert to numpy to avoid pandas index issues)
            if not ground_visible.empty:
                self.rssi_curve.setData(ground_visible['time_s'].values, ground_visible['rssi_dbm'].values)
                self.snr_curve.setData(ground_visible['time_s'].values, ground_visible['snr_db'].values)
                
        if self.data.drone_df is not None:
            drone_mask = self.data.drone_df['time_s'] <= t
            drone_visible = self.data.drone_df[drone_mask]
            
            # Update Queue plot (convert to numpy)
            if not drone_visible.empty:
                self.queue_curve.setData(drone_visible['time_s'].values, drone_visible['queue_depth'].values)
                
        # Update topology
        self.update_topology(t)
        
        # Update event log
        self.update_event_log(t)
        
        # Update metrics
        self.update_metrics(t)
        
    def update_topology(self, t):
        """Update network topology links."""
        # Check relay status
        relay_active = False
        
        if self.data.ground_df is not None:
            recent_ground = self.data.ground_df[
                (self.data.ground_df['time_s'] <= t) & 
                (self.data.ground_df['time_s'] >= t - 1.0)
            ]
            if not recent_ground.empty:
                relay_active = recent_ground['relay_active'].iloc[-1] == 1
                
        # Update link visibility
        drone_pos = self.node_positions['Drone']
        relay_pos = self.node_positions['Relay']
        ground_pos = self.node_positions['Ground']
        
        if relay_active:
            # Relay path active
            self.direct_link.setData([],[])
            self.relay_link1.setData([drone_pos[0], relay_pos[0]], [drone_pos[1], relay_pos[1]])
            self.relay_link2.setData([relay_pos[0], ground_pos[0]], [relay_pos[1], ground_pos[1]])
        else:
            # Direct path active
            self.direct_link.setData([drone_pos[0], ground_pos[0]], [drone_pos[1], ground_pos[1]])
            self.relay_link1.setData([],[])
            self.relay_link2.setData([],[])
    
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
            
    def update_metrics(self, t):
        """Update user-friendly metrics."""
        # Defaults
        rssi = 0
        queue = 0
        throughput = 0.0
        last_msg = "None"
        
        # Signal Quality
        if self.data.ground_df is not None:
            ground_rx = self.data.ground_df[
                (self.data.ground_df['time_s'] <= t) &
                (self.data.ground_df['event'].str.contains("RX", na=False))
            ]
            if not ground_rx.empty:
                rssi = ground_rx.iloc[-1]['rssi_dbm']
                
            # Throughput (last 1 second)
            window = self.data.ground_df[
                (self.data.ground_df['time_s'] <= t) &
                (self.data.ground_df['time_s'] >= t - 1.0)
            ]
            if not window.empty:
                total_bytes = window['packet_size'].sum()
                throughput = (total_bytes * 8) / 1000.0  # Kbps
                
        # Last Message - Use most recent from event log (same as table)
        if self.data.master_df is not None:
            recent = self.data.master_df[self.data.master_df['time_s'] <= t]
            if not recent.empty:
                last_event = recent.iloc[-1]
                msg_id = int(last_event.get('message_id', 0))
                if msg_id > 0:
                    last_msg = MAVLINK_MSGS.get(msg_id, f"Msg {msg_id}")
                    
        # Queue Depth - From drone data
        if self.data.drone_df is not None:
            drone_recent = self.data.drone_df[self.data.drone_df['time_s'] <= t]
            if not drone_recent.empty:
                queue = int(drone_recent.iloc[-1].get('queue_depth', 0))
                
        # Translate to labels
        if rssi == 0:
            sig_quality = "No Signal"
        elif rssi > -70:
            sig_quality = "Excellent"
        elif rssi > -85:
            sig_quality = "Good"
        elif rssi > -100:
            sig_quality = "Weak"
        else:
            sig_quality = "Critical"
            
        if queue < 5:
            net_status = "Healthy"
        elif queue < 15:
            net_status = "Busy"
        else:
            net_status = "Congested"
            
        # Update labels
        self.metric_labels["Signal Quality"].setText(f"{rssi:.0f} dBm\n{sig_quality}")
        self.metric_labels["Network Status"].setText(f"{queue} pkts\n{net_status}")
        self.metric_labels["Throughput"].setText(f"{throughput:.1f} Kbps")
        self.metric_labels["Last Message"].setText(last_msg)

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
