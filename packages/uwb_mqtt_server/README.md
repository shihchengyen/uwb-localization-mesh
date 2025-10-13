# uwb_mqtt_server

Server-side MQTT handling for UWB measurements.

## Overview
Pure MQTT server implementation that:
- Subscribes to anchor measurements (anchor-centric architecture)
- Emits measurements via callbacks
- No state management (handled by bring-up)

## Architecture
This server is designed for an **anchor-centric** UWB localization system where:
- Multiple anchors (fixed positions) publish measurements about a single phone
- Each anchor publishes to topic: `uwb/anchor/{anchor_id}/vector`
- All measurements are attributed to phone_node_id = 0 (single phone tracking)

## Usage

```python
from uwb_mqtt_server import UWBMQTTServer, MQTTConfig

def handle_measurement(measurement):
    print(f"Got measurement from anchor {measurement.anchor_id} about phone {measurement.phone_node_id}")
    print(f"Vector: {measurement.local_vector}")

# Configure server
config = MQTTConfig(
    broker="localhost",
    port=1884,
    base_topic="uwb"
)

# Create and start server
server = UWBMQTTServer(
    config=config,
    on_measurement=handle_measurement
)

server.start()
```

## Configuration
Via `MQTTConfig`:
- Broker settings (host, port)
- Authentication
- Topic patterns
- QoS settings

## Features
- No side effects on import
- Pure callback-based design
- Thread-safe operation
- Proper error handling
- JSON logging
- Reconnection handling

## Dependencies
- paho-mqtt
- datatypes package
