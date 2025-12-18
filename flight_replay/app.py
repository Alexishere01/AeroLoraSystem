import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import networkx as nx
import numpy as np
import time

# Set page config
st.set_page_config(
    page_title="Flight Replay Dashboard",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for Cyberpunk/Sci-Fi aesthetic
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
        color: #00ff41;
        font-family: 'Courier New', Courier, monospace;
    }
    .stSlider > div > div > div > div {
        background-color: #00ff41;
    }
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 5px;
        padding: 10px;
        margin-bottom: 10px;
        box-shadow: 0 0 10px rgba(0, 255, 65, 0.1);
    }
    h1, h2, h3 {
        color: #00ff41 !important;
        text-shadow: 0 0 5px rgba(0, 255, 65, 0.5);
    }
    .stDataFrame {
        border: 1px solid #30363d;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# DATA LOADING & PROCESSING
# -----------------------------------------------------------------------------

@st.cache_data
def load_data(drone_file, ground_file, primary_file, secondary_file):
    """Load and process log files."""
    
    logs = {}
    
    # Helper to load single CSV
    def load_csv(file, name):
        if file is None:
            return None
        try:
            df = pd.read_csv(file)
            # Ensure timestamp_ms is numeric
            df['timestamp_ms'] = pd.to_numeric(df['timestamp_ms'], errors='coerce')
            df = df.dropna(subset=['timestamp_ms'])
            df['source'] = name
            return df
        except Exception as e:
            st.error(f"Error loading {name}: {e}")
            return None

    logs['drone'] = load_csv(drone_file, 'Drone')
    logs['ground'] = load_csv(ground_file, 'Ground')
    logs['primary'] = load_csv(primary_file, 'Relay Primary')
    logs['secondary'] = load_csv(secondary_file, 'Relay Secondary')
    
    # Find global start time (minimum timestamp across all logs)
    start_times = []
    for key, df in logs.items():
        if df is not None and not df.empty:
            start_times.append(df['timestamp_ms'].min())
            
    if not start_times:
        return None, None
        
    global_start = min(start_times)
    
    # Normalize timestamps to seconds relative to start
    combined_df = pd.DataFrame()
    
    for key, df in logs.items():
        if df is not None:
            df['time_s'] = (df['timestamp_ms'] - global_start) / 1000.0
            # Add to combined dataframe for event log
            combined_df = pd.concat([combined_df, df])
            logs[key] = df
            
    # Sort combined DF by time
    combined_df = combined_df.sort_values('time_s')
    
    return logs, combined_df

# -----------------------------------------------------------------------------
# VISUALIZATION FUNCTIONS
# -----------------------------------------------------------------------------

def plot_network_topology(current_time, logs):
    """Draw dynamic network topology."""
    G = nx.DiGraph()
    
    # Nodes
    G.add_node("Drone", pos=(0, 1))
    G.add_node("Relay", pos=(1, 1)) # Visual placeholder for both Primary/Secondary
    G.add_node("Ground", pos=(0.5, 0))
    
    # Determine active links based on recent data (last 1 second window)
    window_start = current_time - 1.0
    
    # Check Drone -> Ground (Direct)
    direct_active = False
    relay_active = False
    
    # Check Ground logs for RX from Drone
    if logs['ground'] is not None:
        recent_ground = logs['ground'][
            (logs['ground']['time_s'] >= window_start) & 
            (logs['ground']['time_s'] <= current_time)
        ]
        # If we see packets with relay_active=0, direct link is alive
        if not recent_ground[recent_ground['relay_active'] == 0].empty:
            direct_active = True
        # If we see packets with relay_active=1, relay link is alive
        if not recent_ground[recent_ground['relay_active'] == 1].empty:
            relay_active = True
            
    # Also check Drone logs for TX mode (if available)
    if logs['drone'] is not None:
        recent_drone = logs['drone'][
            (logs['drone']['time_s'] >= window_start) & 
            (logs['drone']['time_s'] <= current_time)
        ]
        # Check for relay request flag in drone logs if available
        # (Assuming relay_active column in drone log reflects request state)
        if not recent_drone.empty:
             # If drone says relay active, visualize it
             if recent_drone['relay_active'].iloc[-1] == 1:
                 relay_active = True

    # Edges
    edge_x = []
    edge_y = []
    edge_colors = []
    
    # Direct Link
    if direct_active:
        edge_x.extend([0, 0.5, None])
        edge_y.extend([1, 0, None])
        edge_colors.append("rgba(0, 255, 65, 0.8)") # Neon Green
    else:
        # Ghost link
        edge_x.extend([0, 0.5, None])
        edge_y.extend([1, 0, None])
        edge_colors.append("rgba(0, 255, 65, 0.1)")

    # Relay Link
    if relay_active:
        # Drone -> Relay
        edge_x.extend([0, 1, None])
        edge_y.extend([1, 1, None])
        edge_colors.append("rgba(0, 255, 255, 0.8)") # Cyan
        
        # Relay -> Ground
        edge_x.extend([1, 0.5, None])
        edge_y.extend([1, 0, None])
        edge_colors.append("rgba(0, 255, 255, 0.8)") # Cyan
    else:
        # Ghost links
        edge_x.extend([0, 1, None])
        edge_y.extend([1, 1, None])
        edge_colors.append("rgba(0, 255, 255, 0.1)")
        
        edge_x.extend([1, 0.5, None])
        edge_y.extend([1, 0, None])
        edge_colors.append("rgba(0, 255, 255, 0.1)")

    # Plot
    fig = go.Figure()
    
    # Draw edges
    # Note: Plotly doesn't support multiple colors in a single Scatter trace easily for lines
    # So we draw active ones separately or use a single color if simple.
    # For this "Cyberpunk" look, let's just draw all segments.
    
    # Direct
    fig.add_trace(go.Scatter(
        x=[0, 0.5], y=[1, 0],
        mode='lines',
        line=dict(width=4, color='#00ff41' if direct_active else 'rgba(0, 255, 65, 0.1)'),
        hoverinfo='none'
    ))
    
    # Relay Path
    fig.add_trace(go.Scatter(
        x=[0, 1, 0.5], y=[1, 1, 0],
        mode='lines',
        line=dict(width=4, color='#00ffff' if relay_active else 'rgba(0, 255, 255, 0.1)'),
        hoverinfo='none'
    ))

    # Nodes
    fig.add_trace(go.Scatter(
        x=[0, 1, 0.5],
        y=[1, 1, 0],
        mode='markers+text',
        marker=dict(size=30, color='#161b22', line=dict(width=2, color='#30363d')),
        text=["Drone", "Relay", "Ground"],
        textposition="top center",
        textfont=dict(color='white'),
        hoverinfo='text'
    ))

    fig.update_layout(
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.2, 1.2]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.2, 1.2]),
        margin=dict(l=0, r=0, t=0, b=0),
        height=300
    )
    
    return fig

def plot_signal_quality(logs, current_time):
    """Plot RSSI and SNR over time."""
    fig = go.Figure()
    
    if logs['ground'] is not None:
        df = logs['ground']
        # Filter up to current time
        mask = df['time_s'] <= current_time
        visible_df = df[mask]
        
        fig.add_trace(go.Scatter(
            x=visible_df['time_s'], y=visible_df['rssi_dbm'],
            mode='lines',
            name='RSSI (dBm)',
            line=dict(color='#00ff41', width=2)
        ))
        
        # Add limit line
        fig.add_hline(y=-95, line_dash="dash", line_color="#ff0000", annotation_text="Sensitivity Limit")

    fig.update_layout(
        template="plotly_dark",
        title="Signal Quality (RSSI)",
        xaxis_title="Time (s)",
        yaxis_title="RSSI (dBm)",
        height=300,
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis=dict(range=[0, max(1, current_time)]), # Auto-expand or fixed? Let's auto-expand
        yaxis=dict(range=[-120, -20])
    )
    return fig

def plot_queue_depth(logs, current_time):
    """Plot Queue Depth over time."""
    fig = go.Figure()
    
    if logs['drone'] is not None:
        df = logs['drone']
        mask = df['time_s'] <= current_time
        visible_df = df[mask]
        
        fig.add_trace(go.Scatter(
            x=visible_df['time_s'], y=visible_df['queue_depth'],
            mode='lines',
            fill='tozeroy',
            name='Queue Depth',
            line=dict(color='#00ffff', width=2)
        ))

    fig.update_layout(
        template="plotly_dark",
        title="Congestion (Queue Depth)",
        xaxis_title="Time (s)",
        yaxis_title="Packets",
        height=300,
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis=dict(range=[0, max(1, current_time)]),
        yaxis=dict(range=[0, 50]) # Assuming max queue 50
    )
    return fig

# -----------------------------------------------------------------------------
# MAIN APP
# -----------------------------------------------------------------------------

st.title("🚁 Flight Replay Dashboard")

# Sidebar
with st.sidebar:
    st.header("Log Files")
    drone_file = st.file_uploader("Drone Log", type=['csv'])
    ground_file = st.file_uploader("Ground Log", type=['csv'])
    primary_file = st.file_uploader("Relay Primary Log", type=['csv'])
    secondary_file = st.file_uploader("Relay Secondary Log", type=['csv'])
    
    st.markdown("---")
    st.markdown("### Controls")
    
    # Load data
    logs, combined_df = load_data(drone_file, ground_file, primary_file, secondary_file)
    
    if logs:
        # Calculate max time
        max_time = 0
        for key, df in logs.items():
            if df is not None and not df.empty:
                max_time = max(max_time, df['time_s'].max())
        
        # Time from query params (for button navigation)
        query_time = st.query_params.get("t", None)
        default_time = float(query_time) if query_time else 0.0
        default_time = min(max_time, max(0.0, default_time))  # Clamp
        
        # Time Slider
        time_slider = st.slider("Flight Time (s)", 0.0, float(max_time), default_time, 0.1)
        
        st.markdown("---")
        st.markdown("### Frame Controls")
        
        col_nav1, col_nav2, col_nav3 = st.columns(3)
        
        with col_nav1:
            if st.button("⏮ -1s"):
                new_time = max(0, time_slider - 1.0)
                st.query_params.update({"t": new_time})
                st.rerun()
        
        with col_nav2:
            if st.button("▶️ +0.1s"):
                new_time = min(max_time, time_slider + 0.1)
                st.query_params.update({"t": new_time})
                st.rerun()
                
        with col_nav3:
            if st.button("⏭ +1s"):
                new_time = min(max_time, time_slider + 1.0)
                st.query_params.update({"t": new_time})
                st.rerun()
        
        st.info("💡 **Recording Tip:** Use the **+0.1s** button repeatedly for smooth frame-by-frame capture (10 FPS). Screen record while clicking.")
    else:
        st.info("Upload logs to begin.")
        st.stop()

# Layout
col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### Network Topology")
    topo_placeholder = st.empty()
    
    st.markdown("### Event Log")
    event_placeholder = st.empty()

with col2:
    st.markdown("### Telemetry")
    signal_placeholder = st.empty()
    queue_placeholder = st.empty()

# Metrics Row
st.markdown("### Live Metrics")
m1, m2, m3, m4 = st.columns(4)
metric_placeholders = [m1.empty(), m2.empty(), m3.empty(), m4.empty()]

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------

def get_signal_quality(rssi):
    if rssi == 0: return "No Signal", "off"
    if rssi > -70: return "Excellent", "normal" # Green
    if rssi > -85: return "Good", "normal"
    if rssi > -100: return "Weak", "off" # Yellow/Grey
    return "Critical", "inverse" # Red

def get_network_status(queue_depth):
    if queue_depth < 5: return "Healthy", "normal"
    if queue_depth < 15: return "Busy", "off"
    return "Congested", "inverse"

def get_message_desc(msg_id):
    # Common MAVLink IDs
    maps = {
        0: "Heartbeat",
        1: "System Status",
        30: "Attitude",
        33: "GPS Global",
        74: "VFR HUD",
        76: "Command Long",
        147: "Battery Status"
    }
    return maps.get(msg_id, f"Msg ID {msg_id}")

def calculate_throughput(df, current_time, window=1.0):
    """Calculate Kbps in the last window seconds."""
    if df is None or df.empty: return 0.0
    
    # Filter window
    mask = (df['time_s'] <= current_time) & (df['time_s'] >= current_time - window)
    window_df = df[mask]
    
    if window_df.empty: return 0.0
    
    total_bytes = window_df['packet_size'].sum()
    bits = total_bytes * 8
    kbps = bits / 1000.0 / window
    return kbps

# -----------------------------------------------------------------------------
# RENDER LOGIC
# -----------------------------------------------------------------------------

def render_dashboard(current_time):
    # 1. Network Topology
    topo_placeholder.plotly_chart(plot_network_topology(current_time, logs), use_container_width=True)
    
    # 2. Event Log
    if not combined_df.empty:
        recent_events = combined_df[
            (combined_df['time_s'] <= current_time) & 
            (combined_df['time_s'] >= current_time - 5.0)
        ].sort_values('time_s', ascending=False)
        
        # Add readable columns
        if not recent_events.empty:
            recent_events['Message'] = recent_events['message_id'].apply(get_message_desc)
            
            event_placeholder.dataframe(
                recent_events[['time_s', 'source', 'event', 'Message', 'rssi_dbm']],
                height=300,
                use_container_width=True,
                hide_index=True
            )
        else:
            event_placeholder.info("No recent events")
    
    # 3. Telemetry
    signal_placeholder.plotly_chart(plot_signal_quality(logs, current_time), use_container_width=True)
    queue_placeholder.plotly_chart(plot_queue_depth(logs, current_time), use_container_width=True)
    
    # 4. Metrics Calculation
    
    # Defaults
    rssi_val = 0
    queue_val = 0
    throughput_val = 0.0
    last_msg = "None"
    
    # Signal (From Ground RX)
    if logs['ground'] is not None:
        # Look for RX events only for valid RSSI
        ground_rx = logs['ground'][
            (logs['ground']['time_s'] <= current_time) & 
            (logs['ground']['event'].str.contains("RX"))
        ]
        if not ground_rx.empty:
            rssi_val = ground_rx.iloc[-1]['rssi_dbm']
            
        # Throughput (All Ground traffic)
        throughput_val = calculate_throughput(logs['ground'], current_time)

    # Queue & Message (From Drone TX)
    if logs['drone'] is not None:
        drone_now = logs['drone'][logs['drone']['time_s'] <= current_time]
        if not drone_now.empty:
            last_pkt = drone_now.iloc[-1]
            queue_val = last_pkt['queue_depth']
            last_msg = get_message_desc(last_pkt['message_id'])

    # 5. Render Metrics with "Human" Labels
    
    # Signal
    sig_label, sig_delta = get_signal_quality(rssi_val)
    metric_placeholders[0].metric(
        "Signal Quality", 
        f"{rssi_val:.0f} dBm", 
        sig_label,
        delta_color=sig_delta
    )
    
    # Network Status (Queue)
    net_label, net_delta = get_network_status(queue_val)
    metric_placeholders[1].metric(
        "Network Status", 
        f"{queue_val} pkts", 
        net_label,
        delta_color=net_delta
    )
    
    # Throughput
    metric_placeholders[2].metric(
        "Throughput", 
        f"{throughput_val:.1f} Kbps",
        "Live Bandwidth"
    )
    
    # Last Message
    metric_placeholders[3].metric(
        "Last Activity", 
        last_msg,
        "MAVLink Message"
    )

# Render dashboard at current slider position
render_dashboard(time_slider)
