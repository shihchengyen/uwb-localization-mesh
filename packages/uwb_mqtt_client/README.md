# uwb_mqtt_client

Client-side MQTT handling for UWB measurements (RPi).

## Overview
Pure MQTT client implementation that:
- Publishes UWB measurements
- Handles reconnection with backoff
- Maintains keep-alive

## Usage

```python
from uwb_mqtt_client import UWBMQTTClient, MQTTConfig
import numpy as np

# Configure client
config = MQTTConfig(
    broker="server_ip",
    port=1883,
    base_topic="uwb"
)

# Create and connect client
client = UWBMQTTClient(
    config=config,
    phone_node_id=0
)

client.connect()

# Publish measurements
client.publish_measurement(
    anchor_id=0,
    local_vector=np.array([100, 200, 0])  # cm
)
```

## Configuration
Via `MQTTConfig`:
- Broker settings
- Authentication
- Topic patterns
- Reconnection settings
- QoS levels

## Features
- No side effects on import
- Exponential backoff reconnection
- Thread-safe operation
- Proper error handling
- JSON logging

## Dependencies
- paho-mqtt
- numpy
- datatypes package
