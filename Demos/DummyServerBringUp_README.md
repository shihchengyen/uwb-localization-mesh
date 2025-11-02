# Dummy Server Bring-up

A simulation version of the UWB localization server that generates fake measurements without requiring physical hardware.

## Overview

The `DummyServerBringUp` class provides the same interface as `ServerBringUp` but simulates user movement and generates synthetic UWB measurements. This allows testing and development of demos without needing the physical UWB setup.

## Features

- **Realistic Simulation**: Simulates a user moving in a figure-8 pattern around the 4.8m × 6m space
- **Same Interface**: Drop-in replacement for `ServerBringUp` in demos
- **Configurable**: Adjustable simulation speed and phone ID
- **Full Pipeline**: Uses the same binning, edge creation, and PGO processing as real hardware

## Usage

### Standalone Testing

```python
from DummyServerBringUp import DummyServerBringUp

# Create dummy server
server = DummyServerBringUp(
    simulation_speed=2.0,  # 2x real-time speed
    phone_node_id=0        # Simulated phone ID
)

# Start simulation
server.start()

# Monitor position updates
while True:
    if server.user_position is not None:
        print(f"Position: {server.user_position}")
    time.sleep(1)
```

### Command Line

```bash
# Run with default settings
python DummyServerBringUp.py

# Run with custom speed and phone ID
python DummyServerBringUp.py --speed 0.5 --phone-id 1
```

### In Demos

The UnifiedDemo supports automatic switching between real and dummy servers:

```bash
# Use dummy server for simulation
python main_demo.py --dummy

# Use real server (default, requires hardware)
python main_demo.py
```

## Simulation Details

### Space Layout
- **Dimensions**: 480cm × 600cm (4.8m × 6m)
- **Anchors**:
  - Anchor 0: (480, 600, 0) - top-right
  - Anchor 1: (0, 600, 0) - top-left
  - Anchor 2: (480, 0, 0) - bottom-right
  - Anchor 3: (0, 0, 0) - bottom-left

### Movement Pattern
- **Figure-8 Pattern**: Lissajous curve covering the full space
- **Speed**: Configurable multiplier (default: 1.0)
- **Bounds**: 50cm margin from edges to stay within realistic range

### Measurement Generation
- **Rate**: 10Hz (same as real anchors)
- **Noise**: ±2cm Gaussian noise (realistic UWB accuracy)
- **Anchors**: Measurements from all 4 anchors per timestamp

## Output

The dummy server produces the same logs as the real server:

```json
{"event": "simulated_position", "position": [240.0, 300.0, 0.0], "time": 2.0}
{"event": "position_updated", "phone_id": 0, "position": [245.1, 298.3, -2.1], "error": 123456.7}
{"event": "binning_metrics", "phone_id": 0, "metrics": {...}}
```

## Integration

The dummy server integrates seamlessly with existing components:

- **MQTT Service**: Not used (no network I/O)
- **Binning**: Uses `SlidingWindowBinner` for temporal aggregation
- **Edge Creation**: Creates phone-anchor and anchor-anchor edges
- **PGO Solver**: Uses `PGOSolver` for position optimization
- **Widgets**: Works with all demo widgets (PGO Data, Adaptive Audio, Zone DJ)

## Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `simulation_speed` | 1.0 | Speed multiplier for simulation |
| `phone_node_id` | 0 | Simulated phone identifier |
| `window_size_seconds` | 1.0 | Binning window size |
| `jitter_std` | 0.0 | Anchor position jitter (disabled) |

## Troubleshooting

### PGO Not Converging
- Check that measurements are being generated (look for "simulated_position" logs)
- Verify anchor positions match real setup
- Ensure sufficient time for PGO to accumulate measurements

### No Position Updates
- Wait for binning window to fill (default 1 second)
- Check that all anchors are providing measurements
- Verify PGO solver is running without errors

### Performance Issues
- Reduce `simulation_speed` for slower movement
- Increase sleep intervals in processing loop
- Check system resources (PGO can be computationally intensive)

## Comparison with Real Hardware

| Aspect | Dummy Server | Real Hardware |
|--------|-------------|----------------|
| **Setup** | No hardware needed | Requires UWB anchors + MQTT |
| **Accuracy** | Perfect (noisy by design) | Real UWB measurements |
| **Timing** | Deterministic simulation | Real-time measurements |
| **Network** | No MQTT traffic | Full MQTT communication |
| **Testing** | Reproducible scenarios | Variable real-world conditions |

## Development Notes

The dummy server is located at `Demos/DummyServerBringUp.py` and can be imported by the UnifiedDemo. The simulation uses mathematical patterns to ensure:

1. **Coverage**: User visits all areas of the space
2. **Realism**: Measurements include realistic noise
3. **Compatibility**: Same data structures and processing pipeline

For development, you can modify:
- `_get_simulated_position()`: Change movement patterns
- `_generate_measurement()`: Adjust noise characteristics
- Simulation parameters: Speed, bounds, measurement rate
