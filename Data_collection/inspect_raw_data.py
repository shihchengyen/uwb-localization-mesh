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
MQTT_PORT = 1883
MQTT_USERNAME = "laptop"
MQTT_PASSWORD = "laptop"
MQTT_CLIENT_ID = "raw_data_inspector"
MQTT_BASE_TOPIC = "uwb"

# Store recent readings
recent_readings = defaultdict(lambda: deque(maxlen=10))
total_messages = 0

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        topic = f"{MQTT_BASE_TOPIC}/anchor/+/vector"
        client.subscribe(topic, qos=0)
        print(f"[OK1] Connected to MQTT broker")
        print(f"[OK2] Subscribed to: {topic}")
        print()
    else:
        print(f"[ERROR] Connection failed with code: {rc}")

def on_message(client, userdata, msg):
    global total_messages
    
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
        total_messages += 1
        
        # Print reading
        print(f"\n{'='*70}")
        print(f"Anchor {anchor_id} @ {ANCHORS[anchor_id]}")
        print(f"{'='*70}")
        print(f"Local  [X, Y, Z]: [{local_vector[0]:8.2f}, {local_vector[1]:8.2f}, {local_vector[2]:8.2f}] cm")
        print(f"Global [X, Y, Z]: [{global_vector[0]:8.2f}, {global_vector[1]:8.2f}, {global_vector[2]:8.2f}] cm")
        
        # Calculate where the phone would be
        phone_position = ANCHORS[anchor_id] + global_vector
        print(f"\nPhone position (anchor + global vector):")
        print(f"  X = {ANCHORS[anchor_id][0]:.2f} + {global_vector[0]:.2f} = {phone_position[0]:.2f}")
        print(f"  Y = {ANCHORS[anchor_id][1]:.2f} + {global_vector[1]:.2f} = {phone_position[1]:.2f}")
        print(f"  Z = {ANCHORS[anchor_id][2]:.2f} + {global_vector[2]:.2f} = {phone_position[2]:.2f}")
        
        # Check if reasonable
        x_ok = 0 <= phone_position[0] <= 440
        y_ok = 0 <= phone_position[1] <= 550
        z_ok = 0 <= phone_position[2] <= 239
        
        if x_ok and y_ok and z_ok:
            print(f"[OK] REASONABLE - within room bounds")
        else:
            print(f"[ERROR] UNREASONABLE - outside room bounds!")
            if not x_ok:
                print(f"   X out of range: {phone_position[0]:.2f} (should be 0-440)")
            if not y_ok:
                print(f"   Y out of range: {phone_position[1]:.2f} (should be 0-550)")
            if not z_ok:
                print(f"   Z out of range: {phone_position[2]:.2f} (should be 0-239)")
        
        print(f"\nTotal messages: {total_messages}")
        
    except Exception as e:
        print(f"[ERROR] Error processing message: {e}")
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

def main():
    print("="*70)
    print("RAW SENSOR DATA INSPECTOR")
    print("="*70)
    print()
    print("This tool shows raw sensor readings and their transformations.")
    print("Use this to verify if rotation matrices are correct.")
    print()
    print("Room setup:")
    print(f"  Room size: 440cm x 550cm, height: 239cm")
    print(f"  Anchor positions:")
    for i in range(4):
        print(f"    Anchor {i}: {ANCHORS[i]}")
    print()
    print("Current rotation matrices: Rz(yaw) @ Ry(+45°)")
    print("  (boards tilted 45° down, facing room center)")
    print()
    print("Press Ctrl+C to stop and see summary.")
    print("="*70)
    print()
    
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create MQTT client
    client = mqtt.Client(
        client_id=MQTT_CLIENT_ID,
        protocol=mqtt.MQTTv311,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

