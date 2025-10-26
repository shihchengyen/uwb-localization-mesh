# localization_algos

Core localization algorithms for UWB-based positioning.

## Components

### edge_creation/
Transform measurements and create edges for PGO:
- `transforms.py`: Local → global coordinate transforms
- `anchor_edges.py`: Create anchor-anchor edges

```python
from localization_algos.edge_creation import create_relative_measurement, create_anchor_anchor_edges

# Create phone-anchor edge
edge = create_relative_measurement(
    anchor_id=0,
    phone_node_id=1,
    local_vector=np.array([100, 200, 0])
)

# Create anchor-anchor edges
edges = create_anchor_anchor_edges(anchor_config)
```

### binning/
Time-window based measurement processing with filtering:
- Sliding window implementation
- Late data handling
- Statistical outlier filtering (z-score based)
- Bin variance filtering
- Performance metrics

```python
from localization_algos.binning import SlidingWindowBinner

# Create binner with filtering
binner = SlidingWindowBinner(
    window_size_seconds=2.0,
    outlier_threshold_sigma=2.5,        # Reject measurements >2.5σ from anchor cluster
    min_samples_for_outlier_detection=4, # Need 4 samples before outlier filtering
    max_anchor_variance=10000.0         # Reject measurements that would make anchor variance >10000 cm^2
)

# Add measurements (returns True if accepted, False if rejected)
was_added = binner.add_measurement(measurement)

# Create binned data (aggregates remaining good measurements)
binned_data = binner.create_binned_data(phone_node_id=1)

# Get metrics
metrics = binner.get_metrics()
print(f"Accepted: {metrics.total_measurements}")
print(f"Rejected: {metrics.rejected_measurements}")
print(f"Reasons: {metrics.rejection_reasons}")
```

#### Filtering Behavior

**All filtering happens during `add_measurement()` - bad data is never added to the buffer.**

**Statistical Outlier Detection:**
- Maintains a cluster of recent measurements per anchor
- Calculates z-score for each new measurement
- Rejects if `|distance - mean| / std > outlier_threshold_sigma`
- First `min_samples_for_outlier_detection` measurements always accepted

**Per-Anchor Variance Control:**
- Checks if adding measurement would make anchor's variance exceed `max_anchor_variance`
- Calculates variance of distances for that anchor including the new measurement
- Rejects if `variance > max_anchor_variance`
- Prevents anchors from having inconsistent measurements

**Default Values:**
- `outlier_threshold_sigma=2.5` (rejects outer 1.2% tail)
- `min_samples_for_outlier_detection=4`
- `max_anchor_variance=10000.0` (100cm std deviation)

### pgo/
Pose Graph Optimization solver:
- Nonlinear least squares optimization
- Global frame anchoring
- Support for jittered testing

```python
from localization_algos.pgo import PGOSolver

solver = PGOSolver()
result = solver.solve(
    nodes=nodes,
    edges=edges,
    anchor_positions=ground_truth
)

# Get optimized positions
positions = result.node_positions
print(f"Error: {result.error}")
```

## Features
- Pure functions (no side effects)
- Thread-safe operations
- Comprehensive metrics
- Type safety throughout
- Proper error handling

## Dependencies
- numpy
- scipy (for PGO)
- datatypes package
