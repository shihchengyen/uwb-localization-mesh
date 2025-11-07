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
Dual-binner system for parallel filtered and raw data processing:
- **Filtered binner**: Quality-controlled data for PGO positioning
- **Raw binner**: Complete unfiltered data for logging/analysis
- Sliding window implementation with temporal self-healing
- Statistical outlier detection and variance control

```python
from localization_algos.binning import SlidingWindowBinner

# Filtered binner (for PGO processing - applies quality filters)
filtered_binner = SlidingWindowBinner(
    window_size_seconds=2.0,        # 2-second sliding window
    outlier_threshold_sigma=2.0,    # Reject measurements >2.0σ from cluster
    min_samples_for_outlier_detection=5, # Need 5 samples before outlier filtering
    max_anchor_variance=10000.0     # Max variance per anchor (cm²)
)

# Raw binner (for logging/analysis - accepts all measurements)
raw_binner = SlidingWindowBinner(
    window_size_seconds=2.0,
    outlier_threshold_sigma=float('inf'),  # Disable filtering
    max_anchor_variance=float('inf')       # Disable variance check
)

# Add measurements to both binners
measurement = get_uwb_measurement()

# Filtered processing (returns True if accepted for PGO)
was_accepted = filtered_binner.add_measurement(measurement)
if was_accepted:
    # Use for PGO positioning
    binned_data = filtered_binner.create_binned_data(phone_id)
    # ... PGO processing ...

# Raw processing (always accepts for logging)
raw_binner.add_measurement_raw(measurement)
raw_binned_data = raw_binner.create_binned_data(phone_id)
# ... logging/analysis ...

# Get metrics
filtered_metrics = filtered_binner.get_metrics()
print(f"Accepted for PGO: {filtered_metrics.total_measurements}")
print(f"Rejected by filters: {filtered_metrics.rejected_measurements}")
print(f"Rejection reasons: {filtered_metrics.rejection_reasons}")

raw_metrics = raw_binner.get_metrics()
print(f"Total raw measurements: {len(raw_binner.measurements_buffer)}")
```

#### Dual-Binner Architecture

**Filtered Binner (PGO Processing):**
- Applies statistical outlier detection
- Performs per-anchor variance control
- Only high-quality measurements reach PGO
- Tracks rejection metrics and reasons

**Raw Binner (Logging/Analysis):**
- Accepts all valid measurements (no filtering)
- Maintains complete data history
- Used for debugging and post-processing analysis
- No rejection metrics (everything is preserved)

#### Filtering Logic

**Statistical Outlier Detection:**
- Maintains per-anchor cluster of recent measurements
- Calculates z-score: `|distance - mean| / std_deviation`
- Rejects if `z-score > outlier_threshold_sigma` (default: 2.0σ)
- First `min_samples_for_outlier_detection` measurements always accepted

**Per-Anchor Variance Control:**
- Predictive variance checking before adding measurement
- Calculates: `variance = var(existing_distances + new_distance)`
- Rejects if `variance > max_anchor_variance`
- Prevents anchor clusters from becoming too inconsistent

**Temporal Self-Healing:**
- Sliding window automatically removes old measurements
- Bad data "ages out" over time
- Anchors can automatically recover when conditions improve

#### Usage in Server Classes

**Base ServerBringUp (Filtered Only):**
- Uses only filtered binners for production PGO processing
- Lightweight, focused on positioning accuracy

**DataCollectionServer (Dual Binners):**
- Extends ServerBringUp with raw binners for complete data logging
- Preserves all measurements for research and debugging
- Exports both filtered and raw data to CSV

#### Default Values
- `window_size_seconds=2.0` (2-second sliding window)
- `outlier_threshold_sigma=2.0` (rejects ~2.3% statistical outliers)
- `min_samples_for_outlier_detection=5` (warm-up period)
- `max_anchor_variance=10000.0` (100cm std deviation limit)

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
