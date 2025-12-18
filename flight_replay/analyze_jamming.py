import pandas as pd
import numpy as np
import os

def analyze_file(filepath, label):
    print(f"--- Analyzing {label} ({os.path.basename(filepath)}) ---")
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return

    # Filter for reception events
    rx_events = df[df['event'].isin(['RX_LORA', 'RX_DUALBAND', 'RX_ESPNOW'])]
    
    if len(rx_events) == 0:
        print("No RX events found.")
        return

    # Calculate basic stats
    count = len(rx_events)
    start_time = df['timestamp_ms'].min()
    end_time = df['timestamp_ms'].max()
    duration_sec = (end_time - start_time) / 1000.0
    
    rate = count / duration_sec if duration_sec > 0 else 0
    
    mean_rssi = rx_events['rssi_dbm'].mean()
    mean_snr = rx_events['snr_db'].mean()
    
    print(f"Total Packets Received: {count}")
    print(f"Duration: {duration_sec:.2f} s")
    print(f"Average Message Rate: {rate:.2f} msgs/s")
    print(f"Average RSSI: {mean_rssi:.2f} dBm")
    print(f"Average SNR: {mean_snr:.2f} dB")

    # Sequence number analysis for packet loss
    # Assuming sequence number is per system_id and message_id? Or just a global sequence?
    # Usually sequence_number in these logs is the MAVLink sequence number (0-255).
    # We need to group by system_id and maybe component_id (not in CSV?) to track sequences correctly.
    # For simplicity, let's look at system_id=1 (Drone)
    
    drone_msgs = rx_events[rx_events['system_id'] == 1].copy()
    if len(drone_msgs) > 0:
        drone_msgs = drone_msgs.sort_values('timestamp_ms')
        # Calculate gaps
        # seq is 0-255. Gap = (current - prev) % 256 - 1
        # If Gap > 0, we missed packets.
        
        drone_msgs['prev_seq'] = drone_msgs['sequence_number'].shift(1)
        drone_msgs = drone_msgs.dropna(subset=['prev_seq'])
        
        def calc_gap(row):
            diff = (row['sequence_number'] - row['prev_seq']) % 256
            return diff - 1 if diff > 0 else 0 # diff=1 means consecutive (0 gap)
            
        drone_msgs['gaps'] = drone_msgs.apply(calc_gap, axis=1)
        total_gaps = drone_msgs['gaps'].sum()
        
        # Total expected packets = received + gaps
        total_expected = len(drone_msgs) + total_gaps + 1 # +1 for the first packet
        loss_rate = (total_gaps / total_expected) * 100 if total_expected > 0 else 0
        
        print(f"Estimated Packet Loss (Seq Gap Analysis): {loss_rate:.2f}% ({int(total_gaps)} lost)")
    else:
        print("No messages from System ID 1 (Drone) found for seq analysis.")

    # Timeline Analysis (10s buckets)
    print("\nTimeline (RX Events only, 10s buckets):")
    rx_events['time_bucket'] = (rx_events['timestamp_ms'] - start_time) // 10000
    timeline = rx_events.groupby('time_bucket').size()
    
    # Fill missing buckets with 0
    max_bucket = int(duration_sec // 10)
    for i in range(max_bucket + 1):
        count = timeline.get(i, 0)
        print(f"T+{i*10:03d}s: {count:3d} msgs ({count/10:.1f} Hz)")

    print("\n")

def main():
    base_dir = "/Users/alex/Projects/Antigravity/SeniorDesignInitRelay/flight_replay"
    files = [
        ("G5 Ground (Direct Jamming)", os.path.join(base_dir, "G5Ground.csv")),
        ("G6 Ground 902 (Relay Dest)", os.path.join(base_dir, "G6Ground902.csv")),
        ("G6 Ground 930 (Direct Monitor?)", os.path.join(base_dir, "G6Ground930.csv")),
        ("G6 Relay (Drone2)", os.path.join(base_dir, "G6Drone2.csv")),
        ("G5 Drone1 (Source)", os.path.join(base_dir, "G5Drone1.csv")),
        ("R7 Ground 930 (Direct)", os.path.join(base_dir, "R7Ground930.csv")),
        ("R7 Ground 902 (Relay)", os.path.join(base_dir, "R7Ground902.csv")),
        ("R7 Drone1 (Source)", os.path.join(base_dir, "R7Drone1.csv")),
        ("R7 Drone2 (Relay)", os.path.join(base_dir, "R7Drone2.csv")),
    ]

    for label, filepath in files:
        if os.path.exists(filepath):
            analyze_file(filepath, label)
        else:
            print(f"File not found: {filepath}")

if __name__ == "__main__":
    main()
