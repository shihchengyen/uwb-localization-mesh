"""
Raw sensor data inspector - see what the sensors are actually reporting.

This script subscribes to MQTT and shows:
1. Raw sensor readings (distance, azimuth, elevation)
2. Converted local vectors (x, y, z in local frame)
3. What those would be in global frame with current transformations

Use this to understand if the rotation matrices are correct.
"""

import json
import time
import signal
import sys
import os
from collections import defaultdict, deque
from datetime import datetime

import paho.mqtt.client as mqtt
import numpy as np

# Import rotation matrices
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # parent folder to path, but independent of laptop

from demo_implementation.transform_to_global_vector import ANCHOR_R, Rz, Ry
from demo_implementation.create_anchor_edges import ANCHORS

# MQTT Configuration
MQTT_BROKER = "localhost"  # Changed from 192.168.99.3 to localhost
MQTT_PORT = 1884
MQTT_USERNAME = "laptop"
MQTT_PASSWORD = "laptop"
MQTT_CLIENT_ID = "raw_data_inspector"
MQTT_BASE_TOPIC = "uwb"

# Store recent readings
recent_readings = defaultdict(lambda: deque(maxlen=10))
total_messages = 0
last_display_time = 0  # Global update time instead of per-anchor
last_readings = {}  # Store most recent reading for each anchor

# ANSI escape codes for cursor positioning
CLEAR_SCREEN = "\033[2J"
HOME_CURSOR = "\033[H"
SAVE_CURSOR = "\033[s"
RESTORE_CURSOR = "\033[u"

def update_display():
    """Update all anchor boxes with their most recent readings."""
    for anchor_id in range(4):
        if anchor_id in last_readings:
            reading = last_readings[anchor_id]
            display_anchor_box(anchor_id, reading['local'], reading['global'])
        else:
            # Display empty box for anchors we haven't heard from
            display_empty_box(anchor_id)
    
    # Update total messages
    print(f"\033[38;1H\033[KTotal messages: {total_messages}", end="")

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        topic = f"{MQTT_BASE_TOPIC}/anchor/+/vector"
        client.subscribe(topic, qos=0)
        print(f"[OK1] Connected to MQTT broker")
        print(f"[OK2] Subscribed to: {topic}")
        print()
    else:
        print(f"[ERROR] Connection failed with code: {rc}")

def display_empty_box(anchor_id):
    """Display an empty box for an anchor we haven't heard from."""
    line_offset = anchor_id * 4 + 22
    
    # Move cursor and clear lines for this anchor's box
    for i in range(4):
        print(f"\033[{line_offset + i};1H\033[K", end="")

    # Move back to start of box and print content
    print(f"\033[{line_offset};1H", end="")
    print(f"┌─ Anchor {anchor_id} @ [{ANCHORS[anchor_id][0]:.0f}, {ANCHORS[anchor_id][1]:.0f}, {ANCHORS[anchor_id][2]:.0f}] ────────────── WAIT ─┐")
    print(f"│ Local:   [  ----  ,   ----  ,   ----  ] cm")
    print(f"│ Global:  [  ----  ,   ----  ,   ----  ] cm")
    print(f"└{'─'*65}┘")

def display_anchor_box(anchor_id, local_vector, global_vector):
    """Display data for a specific anchor in a fixed box format."""
    phone_position = ANCHORS[anchor_id] + global_vector

    # Check bounds
    x_ok = 0 <= phone_position[0] <= 480
    y_ok = 0 <= phone_position[1] <= 600
    z_ok = 0 <= phone_position[2] <= 239
    bounds_ok = x_ok and y_ok and z_ok

    # Create status indicator
    status = "✓ OK" if bounds_ok else "✗ ERR"

    # Position cursor for this anchor (anchors 0,1,2,3)
    # Each anchor gets 4 lines: header + 3 data lines + footer
    # Header takes 21 lines, first anchor starts at line 22
    line_offset = anchor_id * 4 + 22

    # Move cursor and clear lines for this anchor's box
    for i in range(4):
        print(f"\033[{line_offset + i};1H\033[K", end="")

    # Move back to start of box and print content
    print(f"\033[{line_offset};1H", end="")
    print(f"┌─ Anchor {anchor_id} @ [{ANCHORS[anchor_id][0]:.0f}, {ANCHORS[anchor_id][1]:.0f}, {ANCHORS[anchor_id][2]:.0f}] ────────────── {status} ─┐")
    print(f"│ Local:   [{local_vector[0]:7.2f}, {local_vector[1]:7.2f}, {local_vector[2]:7.2f}] cm")
    print(f"│ Global:  [{global_vector[0]:7.2f}, {global_vector[1]:7.2f}, {global_vector[2]:7.2f}] cm")
    print(f"└{'─'*65}┘")

def on_message(client, userdata, msg):
    global total_messages, last_display_time

    try:
        # Parse topic
        parts = msg.topic.split('/')
        if len(parts) >= 4 and parts[-1] == 'vector' and parts[-3] == 'anchor':
            anchor_id = int(parts[-2])
        else:
            return

        # Parse payload
        payload = json.loads(msg.payload.decode('utf-8'))

        # Extract vector data
        vector_data = payload.get('vector_local', {})
        if not all(k in vector_data for k in ['x', 'y', 'z']):
            return

        local_vector = np.array([
            float(vector_data['x']),
            float(vector_data['y']),
            float(vector_data['z'])
        ])

        # Transform to global
        global_vector = ANCHOR_R[anchor_id] @ local_vector

        # Store reading
        reading = {
            'timestamp': time.time(),
            'local': local_vector,
            'global': global_vector
        }
        recent_readings[anchor_id].append(reading)
        last_readings[anchor_id] = reading  # Update most recent reading
        total_messages += 1

        # Update display periodically (throttled to avoid excessive updates)
        current_time = time.time()
        if current_time - last_display_time > 0.1:
            update_display()  # Update all anchor boxes at once
            last_display_time = current_time

    except Exception as e:
        # Print errors at bottom without disrupting the display
        print(f"\033[39;1H\033[K[ERROR] {e}", end="")
        import traceback
        traceback.print_exc()

def signal_handler(sig, frame):
    print("\n\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Total messages received: {total_messages}")
    print(f"Anchors seen: {sorted(recent_readings.keys())}")
    
    for anchor_id in sorted(recent_readings.keys()):
        readings = list(recent_readings[anchor_id])
        if readings:
            print(f"\nAnchor {anchor_id}: {len(readings)} readings")
            # Show average
            local_avg = np.mean([r['local'] for r in readings], axis=0)
            global_avg = np.mean([r['global'] for r in readings], axis=0)
            print(f"  Avg local:  [{local_avg[0]:7.2f}, {local_avg[1]:7.2f}, {local_avg[2]:7.2f}]")
            print(f"  Avg global: [{global_avg[0]:7.2f}, {global_avg[1]:7.2f}, {global_avg[2]:7.2f}]")
    
    print("\n" + "="*70)
    print("Stopped.")
    sys.exit(0)

def print_header():
    """Print the fixed header information."""
    print(CLEAR_SCREEN + HOME_CURSOR, end="")
    print("="*70)
    print("RAW SENSOR DATA INSPECTOR")
    print("="*70)
    print()
    print("Monitoring anchors 0, 1, 2, 3 with fixed display boxes.")
    print("Use this to verify if rotation matrices are correct.")
    print()
    print("Room setup:")
    print("  Room size: 480cm x 600cm, height: 239cm")
    print("  Anchor positions:")
    for i in range(4):
        print(f"    Anchor {i}: [{ANCHORS[i][0]:.0f}, {ANCHORS[i][1]:.0f}, {ANCHORS[i][2]:.0f}]")
    print()
    print("Current rotation matrices: Rz(yaw) @ Ry(+45°)")
    print("  (boards tilted 45° down, facing room center)")
    print()
    print("Press Ctrl+C to stop and see summary.")
    print("="*70)
    print()

def main():
    # Print initial header
    print_header()

    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Show initial empty boxes
    update_display()

    # Create MQTT client
    client = mqtt.Client(
        client_id=MQTT_CLIENT_ID,
        protocol=mqtt.MQTTv311
    )

    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"\033[39;1H\033[K[ERROR] Failed to connect: {e}", end="")
        sys.exit(1)

if __name__ == "__main__":
    main()

