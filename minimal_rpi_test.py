#!/usr/bin/env python3
"""
Minimal MQTT test script for RPi - no authentication, simple callbacks.
"""

import paho.mqtt.client as mqtt
import json
import time
import sys

def on_connect(client, userdata, flags, rc):
    print(f"[OK] Connected to MQTT broker (rc: {rc})")
    if rc == 0:
        # Publish a test message
        test_message = {
            "timestamp": time.time(),
            "anchor_id": 999,
            "vector_local": {"x": 100.0, "y": 200.0, "z": 50.0},
            "test": True
        }
        
        topic = "uwb/anchor/999/vector"
        client.publish(topic, json.dumps(test_message), qos=0)
        print(f"[OK] Published test message to: {topic}")
        print(f"[OK] Message: {json.dumps(test_message, indent=2)}")
        
        # Disconnect after publishing
        client.disconnect()
    else:
        print(f"[ERROR] Connection failed with code: {rc}")

def on_publish(client, userdata, mid):
    print(f"[OK] Message published successfully (mid: {mid})")

def on_disconnect(client, userdata, rc):
    print(f"[OK] Disconnected from broker (rc: {rc})")

def main():
    print("RPi Minimal MQTT Test")
    print("=" * 40)
    
    # Use the same broker IP as your anchors
    broker_ip = "172.20.10.3"
    broker_port = 1884
    
    print(f"Connecting to: {broker_ip}:{broker_port}")
    
    # Use the simplest possible client initialization
    client = mqtt.Client()
    
    client.on_connect = on_connect
    client.on_publish = on_publish
    client.on_disconnect = on_disconnect
    
    try:
        client.connect(broker_ip, broker_port, 60)
        client.loop_forever()
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
