#!/usr/bin/env python3
"""
UWB Anchor Client - Hardware-integrated MQTT publisher for UWB anchors.

This script replaces rpi_node_mod.py functionality with a clean, modular design.
Each anchor runs this script with its specific anchor_id.
Provides local coordinate vectors only - global transformation handled by localization pipeline.

Usage:
    python example_anchor.py --anchor-id 0 --broker localhost
    python example_anchor.py --anchor-id 1 --broker localhost
    python example_anchor.py --anchor-id 2 --broker localhost
    python example_anchor.py --anchor-id 3 --broker localhost
"""

import argparse
import signal
import sys
import time

from uwb_mqtt_client import UWBMQTTClient, MQTTConfig, UWBConfig


def main():
    parser = argparse.ArgumentParser(description='UWB Anchor MQTT Client')
    parser.add_argument('--anchor-id', type=int, required=True,
                       help='Anchor ID (0-3)')
    parser.add_argument('--broker', type=str, default='localhost',
                       help='MQTT broker hostname/IP')
    parser.add_argument('--port', type=int, default=1884,
                       help='MQTT broker port')
    parser.add_argument('--serial-port', type=str, default='/dev/ttyUSB0',
                       help='Serial port for UWB hardware')
    parser.add_argument('--baud-rate', type=int, default=3_000_000,
                       help='Serial baud rate')

    args = parser.parse_args()

    # Validate anchor ID
    if args.anchor_id not in [0, 1, 2, 3]:
        print(f"Error: anchor-id must be 0-3, got {args.anchor_id}")
        sys.exit(1)

    print(f"Starting UWB Anchor {args.anchor_id}")
    print(f"MQTT Broker: {args.broker}:{args.port}")
    print(f"Serial Port: {args.serial_port} @ {args.baud_rate} baud")

    # Configure MQTT
    mqtt_config = MQTTConfig(
        broker=args.broker,
        port=args.port,
        base_topic="uwb"
    )

    # Configure UWB hardware
    uwb_config = UWBConfig(
        serial_port=args.serial_port,
        baud_rate=args.baud_rate,
        anchor_id=args.anchor_id
    )

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
        client.disconnect()
        sys.exit(1)

    print("✓ UWB hardware interface started")
    print(f"✓ Anchor {args.anchor_id} is now publishing measurements")
    print("Press Ctrl+C to stop...")

    # Set up signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\nStopping...")
        client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        client.disconnect()


if __name__ == "__main__":
    main()
