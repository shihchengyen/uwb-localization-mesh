# uwb_mqtt_server

Server-side MQTT handling for UWB measurements.

## Overview
Pure MQTT server implementation that:
- Subscribes to RPi measurements
- Emits measurements via callbacks
- No state management (handled by bring-up)

## Usage

```python
from uwb_mqtt_server import UWBMQTTServer, MQTTConfig

def handle_measurement(measurement):
    print(f"Got measurement from phone {measurement.phone_node_id}")
    print(f"Anchor {measurement.anchor_id}: {measurement.local_vector}")

# Configure server
config = MQTTConfig(
    broker="localhost",
    port=1883,
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
