# main2.py - Recent Fixes Summary

## Changes Applied

### 1. ✅ Fixed N/A Display Issue
**Problem**: Metrics showed "N/A" when RSSI/SNR had no value
**Solution**: 
- Added `self.last_values` dictionary to persist last known values
- Metrics now show last valid value until updated
- Values only change when new valid data arrives

### 2. ✅ Fixed Packet Drops Not Showing
**Problem**: Drops showed 0 because code searched for 'DROP' in event column
**Solution**:
- Changed to sum tier drop columns: `tier0_drops_full`, `tier0_drops_stale`, `tier1_drops_full`, `tier1_drops_stale`, `tier2_drops_full`, `tier2_drops_stale`
- Now correctly shows cumulative drops from all tiers
- Applied to both Drone and Relay nodes

### 3. ✅ DualBandRx Augmentations Included
**Answer**: YES! The CSV files already have the new augmentations:

**Tier System** (from your CSV):
- `tier0_depth`, `tier1_depth`, `tier2_depth` - Queue depths per priority tier
- `tier0_drops_full`, `tier0_drops_stale` - Tier 0 drop counts
- `tier1_drops_full`, `tier1_drops_stale` - Tier 1 drop counts  
- `tier2_drops_full`, `tier2_drops_stale` - Tier 2 drop counts

**Other columns** in your CSV:
- `timestamp_ms` - Timestamp in milliseconds
- `sequence_number` - Packet sequence number
- `message_id` - MAVLink message ID
- `system_id` - System ID
- `rssi_dbm` - Received signal strength
- `snr_db` - Signal-to-noise ratio
- `relay_active` - Relay mode indicator
- `event` - Event type (TX_LORA, RX_LORA, etc.)
- `packet_size` - Packet size in bytes
- `tx_timestamp` - Transmission timestamp
- `queue_depth` - Total queue depth
- `errors` - Error count

**DualBandRx**: The ground station CSVs (902 MHz and 930 MHz) are separate files, which IS the dual-band implementation - the dashboard shows them separately in metric boxes!

## Code Changes

```python
# Added to __init__:
self.last_values = {
    'drone_rssi': 0,
    'ground902_rssi': 0,
    'ground902_snr': 0,
    'ground930_rssi': 0,
    'ground930_snr': 0
}

# Updated drops calculation:
drops = 0
for col in ['tier0_drops_full', 'tier0_drops_stale', 'tier1_drops_full', 
           'tier1_drops_stale', 'tier2_drops_full', 'tier2_drops_stale']:
    if col in latest:
        drops += int(latest[col]) if not pd.isna(latest[col]) else 0

# Updated RSSI persistence:
rssi = latest.get('rssi_dbm', self.last_values['ground902_rssi'])
if not pd.isna(rssi) and rssi != 0:
    self.last_values['ground902_rssi'] = rssi
else:
    rssi = self.last_values['ground902_rssi']
```

## Result

- ✅ No more "N/A" - values persist
- ✅ Drops now display correctly from tier columns
- ✅ All augmentation data is being used (tiers, dual-band receivers)
