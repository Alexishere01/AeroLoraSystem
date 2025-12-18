# main2.py Updates - Dual Relay Support

## Changes Made

### 1. Split Relay File Upload (2 Fields)

**Before**: Single "Relay" file upload
**After**: Two separate fields:
- `Relay (D2Primary)` - For drone2_primary.csv
- `Relay (D2Secondary)` - For drone2_secondary.csv

### 2. Relay Data Combination

Both relay CSV files are:
1. Loaded separately as `relay_primary_df` and `relay_secondary_df`
2. Combined using `pd.concat()` into single `relay_df`
3. Sorted by timestamp
4. Displayed in the single **🔄 RELAY** metric box

### 3. Smart Load Validation

Load button now accepts **two valid scenarios**:

**Option A - Full System** (all nodes):
- ✅ Drone1
- ✅ Ground 902 MHz
- ✅ Ground 930 MHz (QGC)
- ✅ Relay (D2Primary)
- ✅ Relay (D2Secondary)

**Option B - Minimum Viable** (testing without relay):
- ✅ Drone1
- ✅ Ground 930 MHz (QGC)

If neither scenario is met, user sees warning:
```
Please load either:
• All nodes (Drone1, Ground 902, Ground 930, both Relays), OR
• Minimum setup (Drone1 + Ground 930)
```

## File Upload UI

```
📁 Log Files
┌──────────────────────────────────────────────┐
│ Drone1 (Target):     [Browse...] Not loaded │
│ Ground 902 MHz:      [Browse...] Not loaded │
│ Ground 930 MHz (QGC):[Browse...] Not loaded │
│ Relay (D2Primary):   [Browse...] Not loaded │
│ Relay (D2Secondary): [Browse...] Not loaded │
└──────────────────────────────────────────────┘
```

## How Relay Data Combines

```python
# Step 1: Load both files
relay_primary_df = pd.read_csv("drone2_primary.csv")  
relay_secondary_df = pd.read_csv("drone2_secondary.csv")

# Step 2: Combine and sort
relay_df = pd.concat([relay_primary_df, relay_secondary_df])
relay_df = relay_df.sort_values('timestamp_ms')

# Step 3: Use in single Relay metric box
# Shows combined TX, Queue, Drops from both sources
```

## Testing

To test with full system:
```bash
python3 main2.py
# Load all 5 files:
# - JammedDrone3.csv
# - JammedGround1.csv (902)
# - JammedGround2.csv (930)
# - drone2_primary.csv
# - drone2_secondary.csv
# Click "Load & Start"
```

To test minimum setup:
```bash
python3 main2.py
# Load only 2 files:
# - JammedDrone3.csv
# - JammedGround2.csv (930)
# Click "Load & Start" - should work!
```

## Benefits

1. **Flexibility**: Test with or without relay
2. **Complete data**: Both relay radios tracked
3. **Unified view**: Single metric box shows combined relay stats
4. **Clear labeling**: Users know which relay file to upload where
