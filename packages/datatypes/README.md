# datatypes

Core data structures for UWB localization system.

## Overview
This package provides the fundamental data types used across the UWB localization system:
- `Measurement`: Raw UWB measurements
- `BinnedData`: Time-windowed measurement aggregation
- `AnchorConfig`: Anchor position management

## Usage

```python
from datatypes import Measurement, BinnedData, AnchorConfig

# Create a measurement
measurement = Measurement(
    timestamp=time.time(),
    anchor_id=0,
    phone_node_id=1,
    local_vector=np.array([100, 200, 0])  # cm
)

# Create anchor config
anchor_config = AnchorConfig(positions={
    0: np.array([440, 550, 0]),
    1: np.array([0, 550, 0]),
    2: np.array([440, 0, 0]),
    3: np.array([0, 0, 0])
})
```

## Data Classes

### Measurement
Single UWB measurement from one anchor:
- `timestamp`: NTP epoch seconds (UTC)
- `anchor_id`: Anchor identifier
- `phone_node_id`: Phone node identifier
- `local_vector`: [x, y, z] in cm, local frame

### BinnedData
Time-windowed collection of measurements:
- `bin_start_time`: Window start (UTC)
- `bin_end_time`: Window end (UTC)
- `phone_node_id`: Phone identifier
- `measurements`: Map of anchor_id -> vectors

### AnchorConfig
Ground truth anchor positions:
- `positions`: Map of anchor_id -> [x, y, z]
- Support for getting individual or all positions
