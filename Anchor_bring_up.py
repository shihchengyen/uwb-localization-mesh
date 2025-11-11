#!/usr/bin/env python3
"""
UWB Anchor Bring-Up Script

This script runs on each Raspberry Pi connected to a UWB anchor.
It automatically detects which anchor it is based on the ANCHOR_ID environment variable
or command-line argument, and publishes UWB measurements to MQTT.

Usage:
    # Set environment variable (recommended)
    export ANCHOR_ID=0
    python Anchor_bring_up.py

    # Or use command line argument
    uv run Anchor_bring_up.py --anchor-id 0 --broker 192.168.68.65

    # Override MQTT broker [use this]
    uv run Anchor_bring_up.py --broker 192.168.68.65

Environment Variables:
    ANCHOR_ID: Anchor ID (0-3) - REQUIRED
    MQTT_BROKER: MQTT broker IP (default: localhost)
    SERIAL_PORT: Serial device path (default: /dev/ttyUSB0)

Dependencies:
    pip install paho-mqtt numpy
    sudo apt-get install -y python3-serial
"""

import argparse
import os
import signal
import socket
import sys
import time

from packages.uwb_mqtt_client.client import UWBMQTTClient
from packages.uwb_mqtt_client.config import MQTTConfig, UWBConfig


# Configuration per anchor
ANCHOR_CONFIGS = {
    0: {"name": "Anchor 0", "description": "Top-right anchor"},
    1: {"name": "Anchor 1", "description": "Top-left anchor"},
    2: {"name": "Anchor 2", "description": "Bottom-right anchor"},
    3: {"name": "Anchor 3", "description": "Bottom-left anchor (origin)"},
}


def get_anchor_id():
    """Get anchor ID from environment variable or command line."""
    # Try environment variable first
    env_id = os.environ.get('ANCHOR_ID')
    if env_id is not None:
        try:
            return int(env_id)
        except ValueError:
            pass

    # Fall back to hostname-based detection
    hostname = socket.gethostname().lower()
    for anchor_id in [0, 1, 2, 3]:
        if f"anchor{anchor_id}" in hostname or f"rpi{anchor_id}" in hostname:
            print(f"Auto-detected anchor ID {anchor_id} from hostname '{hostname}'")
            return anchor_id

    return None


def create_mqtt_config(broker_ip=None, anchor_id=None):
    """Create MQTT configuration."""
    broker = broker_ip or os.environ.get('MQTT_BROKER', 'localhost')
    
    # Use anchor ID if provided, otherwise fall back to hostname
    if anchor_id is not None:
        client_id = f"uwb_anchor_{anchor_id}"
    else:
        client_id = f"uwb_anchor_{socket.gethostname()}"

    return MQTTConfig(
        broker=broker,
        port=1884,
        base_topic="uwb",
        client_id=client_id
    )


def create_uwb_config(anchor_id):
    """Create UWB hardware configuration."""
    serial_port = os.environ.get('SERIAL_PORT', '/dev/ttyUSB0')

    return UWBConfig(
        serial_port=serial_port,
        baud_rate=3_000_000,
        anchor_id=anchor_id
    )


def main():
    parser = argparse.ArgumentParser(
        description='UWB Anchor MQTT Publisher',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using environment variable (recommended)
  export ANCHOR_ID=0
  python Anchor_bring_up.py

  # Using command line argument
  python Anchor_bring_up.py --anchor-id 1

  # Override MQTT broker
  python Anchor_bring_up.py --broker 192.168.1.100

Environment Variables:
  ANCHOR_ID     - Anchor ID (0-3) [REQUIRED]
  MQTT_BROKER   - MQTT broker IP (default: localhost)
  SERIAL_PORT   - Serial device path (default: /dev/ttyUSB0)
        """
    )

    parser.add_argument('--anchor-id', type=int, choices=[0, 1, 2, 3],
                       help='Anchor ID (0-3). Can also be set with ANCHOR_ID environment variable.')
    parser.add_argument('--broker', type=str,
                       help='MQTT broker IP. Can also be set with MQTT_BROKER environment variable.')
    parser.add_argument('--serial-port', type=str, default='/dev/ttyUSB0',
                       help='Serial port for UWB hardware. Can also be set with SERIAL_PORT environment variable.')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show configuration and exit without starting.')

    args = parser.parse_args()

    # Determine anchor ID
    anchor_id = args.anchor_id or get_anchor_id()
    if anchor_id is None:
        print("ERROR: Could not determine anchor ID.")
        print("Please set ANCHOR_ID environment variable or use --anchor-id argument.")
        print("\nExample:")
        print("  export ANCHOR_ID=0")
        print("  python Anchor_bring_up.py")
        sys.exit(1)

    if anchor_id not in [0, 1, 2, 3]:
        print(f"ERROR: Invalid anchor ID {anchor_id}. Must be 0-3.")
        sys.exit(1)

    # Get anchor info
    anchor_info = ANCHOR_CONFIGS[anchor_id]

    # Create configurations
    mqtt_config = create_mqtt_config(args.broker, anchor_id)
    uwb_config = create_uwb_config(anchor_id)

    # Override serial port if specified
    if args.serial_port != '/dev/ttyUSB0':
        uwb_config = UWBConfig(
            serial_port=args.serial_port,
            baud_rate=3_000_000,
            anchor_id=anchor_id
        )

    print("=" * 60)
    print(f"Anchor {anchor_id}: {anchor_info['name']}")
    print(f"Description: {anchor_info['description']}")
    print("=" * 60)
    print()
    print()
    print("Configuration:")
    print(f"  Anchor ID:     {anchor_id}")
    print(f"  MQTT Broker:   {mqtt_config.broker}:{mqtt_config.port}")
    print(f"  Serial Port:   {uwb_config.serial_port}")
    print(f"  Baud Rate:     {uwb_config.baud_rate}")
    print(f"  Client ID:     {mqtt_config.client_id}")
    print()

    if args.dry_run:
        print("Dry run - exiting.")
        return

    print("Starting UWB measurement publishing...")
    print("Press Ctrl+C to stop.")
    print()

    # Create client with integrated hardware
    client = UWBMQTTClient(
        config=mqtt_config,
        phone_node_id=0,  # Always 0 since we're tracking 1 phone
        uwb_config=uwb_config
    )

    # Connect to MQTT
    try:
        client.connect()
        print("✓ Connected to MQTT broker")
    except Exception as e:
        print(f"✗ Failed to connect to MQTT broker: {e}")
        sys.exit(1)

    # Start UWB hardware interface
    if not client.start_uwb_interface():
        print("✗ Failed to start UWB hardware interface")
        print("Check that the UWB device is connected and serial port is correct.")
        client.disconnect()
        sys.exit(1)

    print("✓ UWB hardware interface started")
    print("✓ Publishing measurements to MQTT")
    print()

    # Status tracking
    class Stats:
        """Simple class to hold mutable state."""
        def __init__(self):
            self.start_time = time.time()
            self.count = 0
    
    stats = Stats()

    # Hook to count measurements
    original_callback = client.uwb_interface.measurement_callback
    def counting_callback(measurement):
        stats.count += 1
        if original_callback:
            original_callback(measurement)
    client.uwb_interface.measurement_callback = counting_callback

    def status_update():
        elapsed = time.time() - stats.start_time
        if elapsed > 0:
            rate = stats.count / elapsed
            print(f"📊 Status: {stats.count} measurements in {elapsed:.1f}s (Rate: {rate:.1f} msg/s)")

    # Set up signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\nStopping...")
        status_update()  # Final status
        client.disconnect()
        print("✓ Shutdown complete")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Keep running and show periodic status
    last_status_time = time.time()
    try:
        while True:
            time.sleep(0.1)  # Short sleep to prevent busy waiting

            # Periodic status update every 30 seconds
            if time.time() - last_status_time >= 30:
                status_update()
                last_status_time = time.time()
                # Reset stats for next period
                stats.count = 0
                stats.start_time = time.time()

    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)


if __name__ == "__main__":
    main()
