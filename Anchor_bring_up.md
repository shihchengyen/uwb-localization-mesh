# UWB Anchor Bring-Up Guide

This guide explains how to set up and run the UWB anchor system on 4 Raspberry Pis for real-time localization.

## Overview

The UWB localization system consists of:
- **4 Raspberry Pis** (one per anchor)
- **4 UWB anchors** (numbered 0-3)
- **1 phone** being tracked
- **1 MQTT broker** for communication
- **1 server** running the localization algorithm

Each Raspberry Pi runs the same `Anchor_bring_up.py` script, which automatically detects which anchor it is and publishes UWB measurements to MQTT.


## Prerequisites

### 1. Hardware Setup
- 4 Raspberry Pis (one per anchor)
- 4 UWB anchor modules connected via USB serial
- Network connectivity to MQTT broker

- Time syncing to external server
```bash 
sudo apt-get install -y chrony
sudo chronyd -q 'server pool.ntp.org iburst'
```
- time syncing on mac
```bash
sudo sntp -sS pool.ntp.org
```

### 2. Software Dependencies
```bash
# On each Raspberry Pi
pip install paho-mqtt numpy
sudo apt-get install -y python3-serial
```

### 3. MQTT Broker
Set up an MQTT broker (Mosquitto) accessible from all RPis:
```bash
sudo apt-get install mosquitto mosquitto-clients
sudo systemctl start mosquitto
```

## Quick Start

### Step 1: Configure Each RPi

**On RPi 0 (Anchor 0):**
```bash
export ANCHOR_ID=0
export MQTT_BROKER="192.168.68.63"  # Your MQTT broker IP
```

**On RPi 1 (Anchor 1):**
```bash
export ANCHOR_ID=1
export MQTT_BROKER="192.168.68.63"
```

**On RPi 2 (Anchor 2):**
```bash
export ANCHOR_ID=2
export MQTT_BROKER="192.168.68.63"
```

**On RPi 3 (Anchor 3):**
```bash
export ANCHOR_ID=3
export MQTT_BROKER="192.168.68.63"
```

### Step 2: Run on Each RPi

```bash
python Anchor_bring_up.py
```

You should see output like:
```
╔══════════════════════════════════════════════════════════════╗
║                     Anchor 0                               ║
║               Top-right anchor                             ║
╚══════════════════════════════════════════════════════════════╝

Configuration:
  Anchor ID:     0
  MQTT Broker:   192.168.1.100:1883
  Serial Port:   /dev/ttyUSB0
  Baud Rate:     3000000
  Client ID:     uwb_anchor_rpi0

Starting UWB measurement publishing...
✓ Connected to MQTT broker
✓ UWB hardware interface started
✓ Publishing measurements to MQTT
```

## Configuration Options

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ANCHOR_ID` | Anchor ID (0-3) | Auto-detected | Yes |
| `MQTT_BROKER` | MQTT broker IP | localhost | No |
| `SERIAL_PORT` | UWB serial device | /dev/ttyUSB0 | No |

### Command Line Arguments

```bash
python Anchor_bring_up.py [options]

Options:
  --anchor-id {0,1,2,3}    Anchor ID (overrides ANCHOR_ID env var)
  --broker BROKER_IP       MQTT broker IP (overrides MQTT_BROKER env var)
  --serial-port PORT       Serial device path (overrides SERIAL_PORT env var)
  --dry-run                Show configuration without starting
  --help                   Show help message
```

## Auto-Detection Features

The script automatically detects the anchor ID using:

1. **Environment variable** `ANCHOR_ID`
2. **Hostname detection** (looks for "anchor0", "rpi0", etc. in hostname)
3. **Command line argument** `--anchor-id`

### Recommended: Hostname-Based Setup

Set hostnames on each RPi for automatic detection:

```bash
# On RPi 0
sudo hostnamectl set-hostname anchor0

# On RPi 1
sudo hostnamectl set-hostname anchor1

# On RPi 2
sudo hostnamectl set-hostname anchor2

# On RPi 3
sudo hostnamectl set-hostname anchor3
```

Then you only need to set `MQTT_BROKER` and the script will auto-detect the anchor ID.

## Troubleshooting

### Common Issues

**1. "Clock synchronization issues"**

**2. "Could not determine anchor ID"**
- Ensure MQTT broker is running and accessible

**3. "Failed to start UWB hardware interface"**
- Check USB serial device is connected: `ls /dev/ttyUSB*`
- Verify serial port in `SERIAL_PORT`
- Check device permissions: `sudo usermod -a -G dialout $USER`

### Testing

**Dry Run (check configuration):**
```bash
export ANCHOR_ID=0
python Anchor_bring_up.py --dry-run
```

**Test MQTT Connection:**
```bash
mosquitto_sub -h localhost -t "uwb/0/measurements"
```

**Monitor Measurements:**
```bash
# On another terminal, subscribe to measurements
mosquitto_sub -h localhost -t "uwb/0/measurements" | jq .
```

## Anchor Positions

The system assumes standard anchor positions (can be modified in localization server):

- **Anchor 0**: Top-right (440, 550, 0) cm
- **Anchor 1**: Top-left (0, 550, 0) cm
- **Anchor 2**: Bottom-right (440, 0, 0) cm
- **Anchor 3**: Bottom-left (origin) (0, 0, 0) cm

## Next Steps

After anchors are running and publishing measurements:

1. **Start the localization server** using `Server_bring_up.py`
2. **Verify measurements** are being received
3. **Tune anchor positions** if needed
4. **Test phone tracking** with the localization pipeline

## Files Overview

- `Anchor_bring_up.py` - Main script (this file)
- `Anchor_bring_up.md` - This documentation
- `packages/uwb_mqtt_client/` - MQTT client package
- `Server_bring_up.py` - Localization server script

The UWB anchor system is now ready to provide real-time positioning data! 📍
