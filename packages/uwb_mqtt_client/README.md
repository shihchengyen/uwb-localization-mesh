# uwb_mqtt_client

Client-side MQTT handling for UWB measurements (RPi).

## Overview

This package provides MQTT communication for UWB localization systems with two main components:

- **`client.py`**: MQTT client that handles network communication and publishing
- **`uwb_hardware.py`**: Hardware interface that reads from UWB serial devices and processes measurements

The system supports two usage modes:
- **Programmatic API**: Manual measurement publishing
- **Hardware-Integrated Mode**: Automatic publishing from UWB hardware

## Key Components

### UWBMQTTClient (client.py)
- Handles MQTT broker connections and publishing
- Supports reconnection with exponential backoff
- Can work with or without hardware integration
- Publishes to topic: `uwb/anchor/{anchor_id}/vector` (anchor-centric architecture)

### UWBHardwareInterface (uwb_hardware.py)
- Reads serial data from UWB modules (preserves exact parsing logic)
- Converts spherical coordinates (distance, azimuth, elevation) to Cartesian local vectors
- Processes measurements asynchronously with proper buffering
- Provides local vectors only (global transformation handled elsewhere)

## Installation & Setup

### 1. Install Dependencies
```bash
pip install paho-mqtt numpy
sudo apt-get install -y python3-serial  # For pyserial
```

### 2. Install Package
```bash
cd packages/uwb_mqtt_client
pip install -e .
```

## Usage

This package is designed to be used through the main `Anchor_bring_up.py` script in the project root. For detailed setup instructions, see `Anchor_bring_up.md`.

### Direct API Usage (Advanced)

For programmatic usage without the consolidated bring-up script:

```python
from uwb_mqtt_client import UWBMQTTClient, MQTTConfig, UWBConfig

# Configure MQTT
mqtt_config = MQTTConfig(
    broker="192.168.1.100",
    port=1884,
    base_topic="uwb"
)

# Configure UWB hardware
uwb_config = UWBConfig(
    serial_port="/dev/ttyUSB0",
    baud_rate=3_000_000,
    anchor_id=0  # This anchor's ID
)

# Create client with hardware integration
client = UWBMQTTClient(
    config=mqtt_config,
    phone_node_id=0,  # Always 0 since tracking 1 phone
    uwb_config=uwb_config
)

# Connect and start
client.connect()
client.start_uwb_interface()

# Keep running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    client.disconnect()
```

## Programmatic API (Advanced Usage)

For manual measurement publishing without hardware integration:

```python
from uwb_mqtt_client import UWBMQTTClient, MQTTConfig
import numpy as np

# Configure client
config = MQTTConfig(
    broker="192.168.1.100",
    port=1884,
    base_topic="uwb"
)

# Create and connect client
client = UWBMQTTClient(
    config=config,
    phone_node_id=0
)

client.connect()

# Publish measurements programmatically
client.publish_measurement(
    anchor_id=0,
    local_vector=np.array([100.5, 200.3, 15.2])  # cm
)
```

## Data Flow

```
UWB Hardware → Serial Parsing → Local Vector Conversion → MQTT Publish
                      ↓
              (x, y, z in cm, anchor-local frame)
                      ↓
         uwb/anchor/{anchor_id}/vector (anchor-centric topics)
```

## Configuration Options

### MQTTConfig
- `broker`: MQTT broker hostname/IP
- `port`: MQTT broker port (default: 1884)
- `username`/`password`: Authentication (optional)
- `base_topic`: Base topic (default: "uwb")
- `qos`: Quality of Service (default: 1)
- `reconnect_delay_min/max`: Reconnection settings

### UWBConfig
- `serial_port`: Serial device path (default: "/dev/ttyUSB0")
- `baud_rate`: Serial baud rate (default: 3_000_000)
- `anchor_id`: This anchor's ID (0-3)

## Features
- No side effects on import
- Exponential backoff reconnection
- Thread-safe operation
- Proper error handling
- JSON logging
- Hardware-agnostic MQTT publishing

## Dependencies
- paho-mqtt
- numpy
- pyserial (for hardware interface)
