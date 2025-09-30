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
Time-window based measurement processing:
- Sliding window implementation
- Late data handling
- Performance metrics

```python
from localization_algos.binning import SlidingWindowBinner

binner = SlidingWindowBinner(window_size_seconds=1.0)
binner.add_measurement(measurement)
binned_data = binner.create_binned_data(phone_node_id=1)

# Get metrics
metrics = binner.get_metrics()
print(f"Late drops: {metrics.late_drops}")
```

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
