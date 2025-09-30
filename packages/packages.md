# 📦 Package Roles & Responsibilities

## datatypes
Pure data classes that define the core types used across the system:
- `Measurement`: Raw UWB measurements with phone_node_id
- `BinnedData`: Time-windowed measurement aggregation
- `AnchorConfig`: Ground truth anchor positions + jittering utilities

## localization_algos
Core localization logic with pure functions:

### edge_creation/
- Create anchor-anchor edges from ground truth/jittered positions
- Transform phone measurements to relative edges
- Coordinate system transformations

### binning/
- Pure sliding window implementation (1s default)
- Measurement aggregation and validation
- Late data handling

### pgo/
- Pose Graph Optimization solver
- Graph construction utilities
- Optimization parameters and constraints

## uwb_mqtt_client (RPi)
Pure MQTT client for UWB measurements:
- Connect/reconnect handling
- Measurement publishing
- Keep-alive and backoff
- No side effects on import

## uwb_mqtt_server (Laptop)
Pure MQTT server for measurement ingestion:
- Subscribe to all RPi measurements
- Emits per-phone binned data
- Invokes localization callbacks
- Thread-safe queuing

## Usage in Bring-ups

### Client (RPi)
```python
# Client_bring_up.py
self.node_id = 0
self.uwb_mqtt_client = UwbMqttClient()
self.audio_mqtt_client = AudioMqttClient()
self.position = [x, y, z]  # Optional local telemetry
```

### Server (Laptop)
```python
# Server_bring_up.py
self.nodes = {0: [x, y, z], 1: [x, y, z], ...}  # Ground truth
self.uwb_mqtt_server = UwbMqttServer()
self.user_position = [x, y, z]
self.data = {  # Updated via MQTT callbacks
    0: BinnedData,  # Phone 0's data
    1: BinnedData,  # Phone 1's data
    ...
}
```

## Key Principles
1. No side effects on import
2. Pure functions where possible
3. Clear type hints and validation
4. Thread-safe data structures
5. Proper error handling and logging
6. Unit tests for each component
