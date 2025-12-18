// ===================================================================
// AeroLoRa Telemetry Dashboard - Main Application Logic
// ===================================================================

// Global state
const state = {
    mode: 'disconnected', // 'disconnected', 'serial', 'csv'
    playing: false,
    playbackSpeed: 1.0,
    currentTime: 0.0,
    maxTime: 0.0,
    
    // Data stores
    droneData: [],
    ground902Data: [],
    ground930Data: [],
    relayData: [],
    
    // Real-time metrics
    metrics: {
        drone: { tx: 0, rx: 0, queue: 0, drops: 0, rssi: 0 },
        ground902: { rx: 0, rssi: 0, snr: 0, loss: 0 },
        ground930: { rx: 0, rssi: 0, snr: 0, loss: 0 },
        relay: { forwarded: 0, queue: 0, drops: 0, active: false },
        system: { throughput: 0, deliveryRate: 0, totalDrops: 0, mode: 'DIRECT' }
    },
    
    // Charts
    charts: {},
    
    // WebSerial
    port: null,
    reader: null
};

// MAVLink message dictionary
const MAVLINK_MSGS = {
    0: "Heartbeat", 24: "GPS Raw", 30: "Attitude", 33: "Global Pos",
    74: "VFR HUD", 75: "Command Long", 76: "Command Ack", 147: "Battery",
    253: "StatusText"
};

// ===================================================================
// Initialization
// ===================================================================

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    initEventListeners();
    updateSignalBars();
    addLogEntry('System initialized. Ready for data.', 'info');
});

// ===================================================================
// Chart.js Initialization
// ===================================================================

function initCharts() {
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { labels: { color: '#00FF41' } }
        },
        scales: {
            x: {
                type: 'linear',
                ticks: { color: '#00FF41' },
                grid: { color: 'rgba(0, 255, 65, 0.1)' }
            },
            y: {
                ticks: { color: '#00FF41' },
                grid: { color: 'rgba(0, 255, 65, 0.1)' }
            }
        }
    };

    // Signal Quality Chart
    state.charts.signal = new Chart(document.getElementById('signalChart'), {
        type: 'line',
        data: {
            datasets: [
                { label: '902 MHz RSSI', data: [], borderColor: '#FF0000', tension: 0.3 },
                { label: '930 MHz RSSI', data: [], borderColor: '#00FF00', tension: 0.3 }
            ]
        },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { ...commonOptions.scales.y, suggestedMin: -120, suggestedMax: -40 } } }
    });

    // Throughput Chart
    state.charts.throughput = new Chart(document.getElementById('throughputChart'), {
        type: 'line',
        data: {
            datasets: [
                { label: 'Throughput (Kbps)', data: [], borderColor: '#00FFFF', fill: true, backgroundColor: 'rgba(0, 255, 255, 0.1)', tension: 0.3 }
            ]
        },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { ...commonOptions.scales.y, suggestedMin: 0 } } }
    });

    // Delivery Rate Chart
    state.charts.delivery = new Chart(document.getElementById('deliveryChart'), {
        type: 'line',
        data: {
            datasets: [
                { label: 'Delivery Rate (%)', data: [], borderColor: '#00FF00', tension: 0.3 }
            ]
        },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { ...commonOptions.scales.y, min: 0, max: 100 } } }
    });

    // Queue Depth Chart
    state.charts.queue = new Chart(document.getElementById('queueChart'), {
        type: 'line',
        data: {
            datasets: [
                { label: 'Drone Queue', data: [], borderColor: '#FFFF00', tension: 0.3 },
                { label: 'Relay Queue', data: [], borderColor: '#00FFFF', tension: 0.3 }
            ]
        },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { ...commonOptions.scales.y, min: 0, suggestedMax: 30 } } }
    });
}

// ===================================================================
// Event Listeners
// ===================================================================

function initEventListeners() {
    // WebSerial connection
    document.getElementById('connectSerialBtn').addEventListener('click', connectSerial);
    
    // CSV upload
    document.getElementById('csvUpload').addEventListener('change', handleCSVUpload);
    
    // Playback controls
    document.getElementById('playBtn').addEventListener('click', () => togglePlayback(true));
    document.getElementById('pauseBtn').addEventListener('click', () => togglePlayback(false));
    document.getElementById('resetBtn').addEventListener('click', resetPlayback);
    document.getElementById('speedSelect').addEventListener('change', (e) => {
        state.playbackSpeed = parseFloat(e.target.value);
    });
    
    // Time slider
    document.getElementById('timeSlider').addEventListener('input', (e) => {
        state.currentTime = (e.target.value / 1000) * state.maxTime;
        updateVisualization();
    });
}

// ===================================================================
// WebSerial Connection
// ===================================================================

async function connectSerial() {
    if (!('serial' in navigator)) {
        alert('WebSerial is not supported in this browser. Please use Chrome or Edge.');
        return;
    }

    try {
        state.port = await navigator.serial.requestPort();
        await state.port.open({ baudRate: 115200 });
        
        state.mode = 'serial';
        updateConnectionStatus(true);
        addLogEntry('Connected to serial port', 'info');
        
        readSerial();
    } catch (error) {
        addLogEntry(`Serial connection error: ${error.message}`, 'error');
    }
}

async function readSerial() {
    const textDecoder = new TextDecoderStream();
    const readableStreamClosed = state.port.readable.pipeTo(textDecoder.writable);
    state.reader = textDecoder.readable.getReader();
    
    let buffer = '';
    
    try {
        while (true) {
            const { value, done } = await state.reader.read();
            if (done) break;
            
            buffer += value;
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line in buffer
            
            for (const line of lines) {
                processSerialLine(line.trim());
            }
        }
    } catch (error) {
        addLogEntry(`Serial read error: ${error.message}`, 'error');
    }
}

function processSerialLine(line) {
    if (!line) return;
    
    // Parse CSV format from serial
    const parts = line.split(',');
    if (parts.length < 5) return;
    
    const entry = {
        timestamp_ms: parseInt(parts[0]),
        message_id: parseInt(parts[2]),
        rssi_dbm: parseFloat(parts[4]),
        snr_db: parseFloat(parts[5]),
        event: parts[7]
    };
    
    // Route to appropriate data store based on frequency or node
    // This is a simplified example - adjust based on your actual data format
    updateMetricsFromEntry(entry);
    updateVisualization();
}

// ===================================================================
// CSV File Handling
// ===================================================================

async function handleCSVUpload(event) {
    const files = Array.from(event.target.files);
    if (files.length === 0) return;
    
    state.mode = 'csv';
    updateConnectionStatus(true);
    
    // Reset data
    state.droneData = [];
    state.ground902Data = [];
    state.ground930Data = [];
    state.relayData = [];
    
    let fileList = [];
    
    for (const file of files) {
        const text = await file.text();
        const data = parseCSV(text);
        
        // Categorize based on filename
        if (file.name.toLowerCase().includes('drone') && !file.name.toLowerCase().includes('relay')) {
            state.droneData = data;
            fileList.push(`✓ ${file.name} (Drone)`);
        } else if (file.name.toLowerCase().includes('902') || file.name.toLowerCase().includes('ground') && file.name.includes('1')) {
            state.ground902Data = data;
            fileList.push(`✓ ${file.name} (Ground 902 MHz)`);
        } else if (file.name.toLowerCase().includes('930') || file.name.toLowerCase().includes('ground') && file.name.includes('2')) {
            state.ground930Data = data;
            fileList.push(`✓ ${file.name} (Ground 930 MHz)`);
        } else if (file.name.toLowerCase().includes('relay')) {
            state.relayData = data;
            fileList.push(`✓ ${file.name} (Relay)`);
        }
    }
    
    // Display loaded files
    document.getElementById('uploadedFiles').innerHTML = fileList.join('<br>');
    
    // Normalize timestamps and set max time
    normalizeTimestamps();
    
    // Enable playback controls
    document.getElementById('playBtn').disabled = false;
    document.getElementById('pauseBtn').disabled = false;
    document.getElementById('resetBtn').disabled = false;
    document.getElementById('speedSelect').disabled = false;
    document.getElementById('timeSlider').disabled = false;
    
    addLogEntry(`Loaded ${files.length} file(s). Duration: ${state.maxTime.toFixed(1)}s`, 'info');
    updateVisualization();
}

function parseCSV(text) {
    const lines = text.trim().split('\n');
    const headers = lines[0].split(',');
    
    return lines.slice(1).map(line => {
        const values = line.split(',');
        const obj = {};
        headers.forEach((header, i) => {
            const value = values[i];
            // Try to parse as number
            obj[header.trim()] = isNaN(value) ? value : parseFloat(value);
        });
        return obj;
    }).filter(row => row.timestamp_ms !== undefined);
}

function normalizeTimestamps() {
    const allData = [
        ...state.droneData,
        ...state.ground902Data,
        ...state.ground930Data,
        ...state.relayData
    ];
    
    if (allData.length === 0) return;
    
    const minTime = Math.min(...allData.map(d => d.timestamp_ms));
    const maxTime = Math.max(...allData.map(d => d.timestamp_ms));
    
    // Add normalized time_s field
    [state.droneData, state.ground902Data, state.ground930Data, state.relayData].forEach(dataset => {
        dataset.forEach(row => {
            row.time_s = (row.timestamp_ms - minTime) / 1000.0;
        });
    });
    
    state.maxTime = (maxTime - minTime) / 1000.0;
    document.getElementById('totalTime').textContent = `${state.maxTime.toFixed(1)}s`;
}

// ===================================================================
// Playback Control
// ===================================================================

function togglePlayback(play) {
    state.playing = play;
    
    if (play) {
        state.playbackTimer = setInterval(() => {
            state.currentTime += (0.033 * state.playbackSpeed); // 30 FPS
            
            if (state.currentTime > state.maxTime) {
                state.currentTime = 0; // Loop
            }
            
            updateVisualization();
            
            // Update slider
            const sliderValue = (state.currentTime / state.maxTime) * 1000;
            document.getElementById('timeSlider').value = sliderValue;
        }, 33);
    } else {
        if (state.playbackTimer) {
            clearInterval(state.playbackTimer);
        }
    }
}

function resetPlayback() {
    state.currentTime = 0;
    state.playing = false;
    if (state.playbackTimer) {
        clearInterval(state.playbackTimer);
    }
    document.getElementById('timeSlider').value = 0;
    updateVisualization();
}

// ===================================================================
// Visualization Updates
// ===================================================================

function updateVisualization() {
    const t = state.currentTime;
    
    // Update time display
    document.getElementById('currentTime').textContent = `${t.toFixed(1)}s`;
    
    // Filter data up to current time
    const droneVisible = state.droneData.filter(d => d.time_s <= t);
    const ground902Visible = state.ground902Data.filter(d => d.time_s <= t);
    const ground930Visible = state.ground930Data.filter(d => d.time_s <= t);
    const relayVisible = state.relayData.filter(d => d.time_s <= t);
    
    // Update metrics
    updateNodeMetrics(droneVisible, ground902Visible, ground930Visible, relayVisible);
    
    // Update charts
    updateCharts(droneVisible, ground902Visible, ground930Visible, relayVisible);
    
    // Update topology
    updateTopology();
    
    // Update event log
    updateEventLog(t);
}

function updateNodeMetrics(drone, g902, g930, relay) {
    // Drone metrics
    const droneTx = drone.filter(d => d.event && d.event.includes('TX')).length;
    const droneRx = drone.filter(d => d.event && d.event.includes('RX')).length;
    const droneQueue = drone.length > 0 ? (drone[drone.length - 1].queue_depth || 0) : 0;
    const droneDrops = drone.filter(d => d.event && d.event.includes('DROP')).length;
    const droneRssi = drone.length > 0 && drone[drone.length - 1].rssi_dbm ? drone[drone.length - 1].rssi_dbm : 0;
    
    document.getElementById('droneTx').textContent = droneTx;
    document.getElementById('droneRx').textContent = droneRx;
    document.getElementById('droneQueue').textContent = droneQueue;
    document.getElementById('droneDrops').textContent = droneDrops;
    document.getElementById('droneRssi').textContent = droneRssi ? `${droneRssi.toFixed(0)} dBm` : '-- dBm';
    
    // Ground 902 MHz metrics
    const g902Rx = g902.filter(d => d.event && d.event.includes('RX')).length;
    const g902Rssi = g902.length > 0 && g902[g902.length - 1].rssi_dbm ? g902[g902.length - 1].rssi_dbm : 0;
    const g902Snr = g902.length > 0 && g902[g902.length - 1].snr_db ? g902[g902.length - 1].snr_db : 0;
    
    document.getElementById('ground902Rx').textContent = g902Rx;
    document.getElementById('ground902Rssi').textContent = g902Rssi ? `${g902Rssi.toFixed(0)} dBm` : '-- dBm';
    document.getElementById('ground902Snr').textContent = g902Snr ? `${g902Snr.toFixed(1)} dB` : '-- dB';
    
    // Check for jamming (RSSI < -100 dBm or very low RX rate)
    updateJammingIndicator('jamming902', g902Rssi < -100 || (g902.length > 100 && g902Rx < 50));
    
    // Ground 930 MHz metrics
    const g930Rx = g930.filter(d => d.event && d.event.includes('RX')).length;
    const g930Rssi = g930.length > 0 && g930[g930.length - 1].rssi_dbm ? g930[g930.length - 1].rssi_dbm : 0;
    const g930Snr = g930.length > 0 && g930[g930.length - 1].snr_db ? g930[g930.length - 1].snr_db : 0;
    
    document.getElementById('ground930Rx').textContent = g930Rx;
    document.getElementById('ground930Rssi').textContent = g930Rssi ? `${g930Rssi.toFixed(0)} dBm` : '-- dBm';
    document.getElementById('ground930Snr').textContent = g930Snr ? `${g930Snr.toFixed(1)} dB` : '-- dB';
    
    updateJammingIndicator('jamming930', g930Rssi < -100 || (g930.length > 100 && g930Rx < 50));
    
    // Relay metrics
    const relayActive = relay.length > 0;
    const relayForwarded = relay.filter(d => d.event && (d.event.includes('TX') || d.event.includes('FORWARD'))).length;
    const relayQueue = relay.length > 0 ? (relay[relay.length - 1].queue_depth || 0) : 0;
    const relayDrops = relay.filter(d => d.event && d.event.includes('DROP')).length;
    
    document.getElementById('relayForwarded').textContent = relayForwarded;
    document.getElementById('relayQueue').textContent = relayQueue;
    document.getElementById('relayDrops').textContent = relayDrops;
    document.getElementById('relayQuality').textContent = relayActive ? 'Active' : 'Inactive';
    
    // Update status indicators
    updateStatusIndicator('droneStatus', droneTx > 0);
    updateStatusIndicator('ground902Status', g902Rx > 0);
    updateStatusIndicator('ground930Status', g930Rx > 0);
    updateStatusIndicator('relayStatus', relayActive);
    
    // System-wide metrics
    const totalThroughput = calculateThroughput(drone, g902, g930, relay);
    const deliveryRate = calculateDeliveryRate(drone, g902, g930);
    const totalDrops = droneDrops + relayDrops;
    const commMode = relayActive ? 'RELAY' : 'DIRECT';
    
    document.getElementById('totalThroughput').innerHTML = `${totalThroughput.toFixed(1)} <span class="unit">Kbps</span>`;
    document.getElementById('deliveryPercent').textContent = deliveryRate.toFixed(0);
    document.getElementById('totalDropped').textContent = totalDrops;
    document.getElementById('commMode').textContent = commMode;
    document.getElementById('commMode').className = `metric-value mode-value ${commMode.toLowerCase()}`;
    
    // Update delivery bar
    const deliveryBar = document.getElementById('deliveryBar');
    deliveryBar.style.width = `${deliveryRate}%`;
    
    // Update signal bars
    updateSignalBars('droneSignalBars', droneRssi);
    updateSignalBars('ground902SignalBars', g902Rssi);
    updateSignalBars('ground930SignalBars', g930Rssi);
}

function calculateThroughput(drone, g902, g930, relay) {
    // Calculate from last 1 second of data
    const window = 1.0;
    const recent = [...drone, ...g902, ...g930, ...relay].filter(d => 
        d.time_s >= state.currentTime - window && d.time_s <= state.currentTime
    );
    
    const totalBytes = recent.reduce((sum, d) => sum + (d.packet_size || 0), 0);
    return (totalBytes * 8) / 1000.0; // Kbps
}

function calculateDeliveryRate(drone, g902, g930) {
    const tx = drone.filter(d => d.event && d.event.includes('TX')).length;
    const rx = g902.filter(d => d.event && d.event.includes('RX')).length +
               g930.filter(d => d.event && d.event.includes('RX')).length;    return tx > 0 ? (rx / tx) * 100 : 0;
}

function updateCharts(drone, g902, g930, relay) {
    // Signal chart
    state.charts.signal.data.datasets[0].data = g902.map(d => ({ x: d.time_s, y: d.rssi_dbm || 0 }));
    state.charts.signal.data.datasets[1].data = g930.map(d => ({ x: d.time_s, y: d.rssi_dbm || 0 }));
    state.charts.signal.update('none');
    
    // Throughput chart (simplified - calculate over time windows)
    const throughputData = [];
    for (let t = 0; t <= state.currentTime; t += 1) {
        const windowData = [...drone, ...g902, ...g930, ...relay].filter(d => 
            d.time_s >= t && d.time_s < t + 1
        );
        const bytes = windowData.reduce((sum, d) => sum + (d.packet_size || 0), 0);
        throughputData.push({ x: t, y: (bytes * 8) / 1000.0 });
    }
    state.charts.throughput.data.datasets[0].data = throughputData;
    state.charts.throughput.update('none');
    
    // Delivery rate chart (calculate over time windows)
    const deliveryData = [];
    for (let t = 0; t <= state.currentTime; t += 1) {
        const windowDrone = drone.filter(d => d.time_s >= t && d.time_s < t + 1);
        const windowGround = [...g902, ...g930].filter(d => d.time_s >= t && d.time_s < t + 1);
        const tx = windowDrone.filter(d => d.event && d.event.includes('TX')).length;
        const rx = windowGround.filter(d => d.event && d.event.includes('RX')).length;
        deliveryData.push({ x: t, y: tx > 0 ? (rx / tx) * 100 : 0 });
    }
    state.charts.delivery.data.datasets[0].data = deliveryData;
    state.charts.delivery.update('none');
    
    // Queue depth chart
    state.charts.queue.data.datasets[0].data = drone.map(d => ({ x: d.time_s, y: d.queue_depth || 0 }));
    state.charts.queue.data.datasets[1].data = relay.map(d => ({ x: d.time_s, y: d.queue_depth || 0 }));
    state.charts.queue.update('none');
}

function updateTopology() {
    const relayActive = state.relayData.filter(d => d.time_s <= state.currentTime).length > 0;
    
    const directLink = document.getElementById('directLink');
    const relayLink1 = document.getElementById('relayLink1');
    const relayLink2 = document.getElementById('relayLink2');
    const relayNode = document.querySelector('#relayNode circle');
    
    if (relayActive) {
        directLink.classList.remove('active');
        directLink.classList.add('inactive');
        relayLink1.classList.add('active', 'relay');
        relayLink2.classList.add('active', 'relay');
        relayNode.classList.remove('inactive');
    } else {
        directLink.classList.add('active');
        directLink.classList.remove('inactive');
        relayLink1.classList.remove('active', 'relay');
        relayLink2.classList.remove('active', 'relay');
        relayNode.classList.add('inactive');
    }
}

function updateEventLog(currentTime) {
    const logContainer = document.getElementById('eventLog');
    const recentWindow = 5.0; // Show last 5 seconds of events
    
    const allEvents = [
        ...state.droneData.map(d => ({ ...d, source: 'Drone' })),
        ...state.ground902Data.map(d => ({ ...d, source: 'Ground 902' })),
        ...state.ground930Data.map(d => ({ ...d, source: 'Ground 930' })),
        ...state.relayData.map(d => ({ ...d, source: 'Relay' }))
    ].filter(e => e.time_s >= currentTime - recentWindow && e.time_s <= currentTime)
     .sort((a, b) => b.time_s - a.time_s)
     .slice(0, 15);
    
    // Only update if events changed
    if (allEvents.length > 0) {
        logContainer.innerHTML = allEvents.map(e => {
            const msgName = MAVLINK_MSGS[e.message_id] || `Msg ${e.message_id}`;
            const eventType = e.event && e.event.includes('TX') ? 'tx' : 
                            e.event && e.event.includes('RX') ? 'rx' : 
                            e.event && e.event.includes('DROP') ? 'error' : 'info';
            return `<div class="log-entry ${eventType}">${e.time_s.toFixed(2)}s [${e.source}] ${e.event || 'EVENT'} - ${msgName}</div>`;
        }).join('');
    }
}

// ===================================================================
// Helper Functions
// ===================================================================

function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('connectionStatus');
    const indicator = statusEl.querySelector('.status-indicator');
    
    if (connected) {
        indicator.classList.add('connected');
        statusEl.querySelector('span:last-child').textContent = state.mode === 'serial' ? 'Serial Connected' : 'CSV Loaded';
    } else {
        indicator.classList.remove('connected');
        statusEl.querySelector('span:last-child').textContent = 'Disconnected';
    }
}

function updateSignalBars(elementId, rssi) {
    const container = document.getElementById(elementId);
    if (!container) return;
    
    // Convert RSSI to 0-5 bars
    let bars = 0;
    if (rssi > -50) bars = 5;
    else if (rssi > -70) bars = 4;
    else if (rssi > -85) bars = 3;
    else if (rssi > -100) bars = 2;
    else if (rssi > -110) bars = 1;
    
    const quality = bars >= 4 ? 'strong' : bars >= 2 ? 'medium' : 'weak';
    
    // Create bars
    container.innerHTML = Array.from({ length: 5 }, (_, i) => {
        const height = (i + 1) * 3;
        const filled = i < bars;
        const className = filled ? (quality === 'weak' ? 'weak' : quality === 'medium' ? 'medium' : '') : '';
        return `<div class="signal-bar ${className}" style="height: ${height}px; opacity: ${filled ? 1 : 0.2}"></div>`;
    }).join('');
}

function updateJammingIndicator(elementId, jammed) {
    const indicator = document.getElementById(elementId);
    if (jammed) {
        indicator.classList.add('active');
    } else {
        indicator.classList.remove('active');
    }
}

function updateStatusIndicator(elementId, active) {
    const indicator = document.getElementById(elementId);
    if (active) {
        indicator.classList.remove('inactive');
        indicator.classList.add('ok');
    } else {
        indicator.classList.remove('ok');
        indicator.classList.add('inactive');
    }
}

function addLogEntry(message, type = 'info') {
    const logContainer = document.getElementById('eventLog');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = `${new Date().toLocaleTimeString()} - ${message}`;
    logContainer.insertBefore(entry, logContainer.firstChild);
    
    // Keep only last 50 entries
    while (logContainer.children.length > 50) {
        logContainer.removeChild(logContainer.lastChild);
    }
}
