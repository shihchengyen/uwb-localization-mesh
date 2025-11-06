# Dummy Server Bring-up Pro Max

A simulation version of the UWB localization server that generates fake measurements without requiring physical hardware. Now includes audio control functionality for comprehensive demo testing.

## Overview

The `DummyServerBringUpProMax` class provides the same interface as `ServerBringUpProMax` but simulates user movement and generates synthetic UWB measurements. This allows testing and development of demos without needing the physical UWB setup or MQTT infrastructure.

## Features

- **Realistic Simulation**: Simulates a user moving in a figure-8 pattern around the 4.8m × 6m space
- **Same Interface**: Drop-in replacement for `ServerBringUpProMax` in demos
- **Audio Control**: Includes adaptive audio and zone DJ demo functionality
- **Configurable**: Adjustable simulation speed and phone ID
- **Full Pipeline**: Uses the same binning, edge creation, and PGO processing as real hardware
- **MQTT Simulation**: Logs MQTT commands instead of sending them (dummy mode)

## Usage

### Standalone Testing

```python
from DummyServerBringUp import DummyServerBringUpProMax
from packages.uwb_mqtt_server.config import MQTTConfig

# Create dummy server with optional MQTT config for audio simulation
mqtt_config = MQTTConfig(broker="localhost", port=1884)  # Optional
server = DummyServerBringUpProMax(
    mqtt_config=mqtt_config,   # None to disable audio features
    simulation_speed=2.0,      # 2x real-time speed
    phone_node_id=0            # Simulated phone ID
)

# Start simulation
server.start()

# Test audio features
server.adaptive_audio_demo()
server.zone_dj_demo()
server.set_playlist(3)

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

## New Audio Features

The dummy server now includes all audio control methods from `ServerBringUpProMax`:

### Audio Demo Methods
- **`adaptive_audio_demo()`**: Start adaptive audio based on user position
- **`stop_adaptive_audio_demo()`**: Stop adaptive audio demo
- **`zone_dj_demo()`**: Start zone DJ mode (all speakers at 70%)
- **`stop_zone_dj_demo()`**: Stop zone DJ mode
- **`set_playlist(playlist_number)`**: Set playlist (1-5)

### Audio Simulation
- **MQTT Commands**: Logged instead of sent (dummy mode)
- **Speaker Control**: Simulated state tracking
- **Volume Control**: Virtual volume adjustments
- **Graceful Fallback**: Works even without audio dependencies

## Integration

The dummy server integrates seamlessly with existing components:

- **MQTT Service**: Simulated (logs commands instead of sending)
- **Audio Control**: Optional AdaptiveAudioController integration
- **Binning**: Uses `SlidingWindowBinner` for temporal aggregation
- **Edge Creation**: Creates phone-anchor and anchor-anchor edges
- **PGO Solver**: Uses `PGOSolver` for position optimization
- **Widgets**: Works with all demo widgets (PGO Data, Adaptive Audio, Zone DJ)

## Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `mqtt_config` | None | MQTT configuration for audio features |
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
| **Network** | Simulated MQTT (logs only) | Full MQTT communication |
| **Audio** | Simulated commands | Real speaker control |
| **Testing** | Reproducible scenarios | Variable real-world conditions |

## Development Notes

The dummy server is located at `Demos/DummyServerBringUp.py` and can be imported by the UnifiedDemo. The simulation uses mathematical patterns to ensure:

1. **Coverage**: User visits all areas of the space
2. **Realism**: Measurements include realistic noise
3. **Compatibility**: Same data structures and processing pipeline
4. **Audio Integration**: Full audio demo functionality without hardware

For development, you can modify:
- `_get_simulated_position()`: Change movement patterns
- `_generate_measurement()`: Adjust noise characteristics
- Audio methods: Customize simulation behavior
- Simulation parameters: Speed, bounds, measurement rate

### Audio Dependencies
The dummy server gracefully handles missing audio dependencies:
- If `AdaptiveAudioController` is not available, audio features are disabled
- MQTT client issues are caught and logged
- All audio methods include fallback behavior
