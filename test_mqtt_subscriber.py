#!/usr/bin/env python3
"""
Simple MQTT subscriber to test what data is being published.
"""

import paho.mqtt.client as mqtt
import json
import time

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[OK] Connected to MQTT broker")
        # Subscribe to all topics to see what's being published
        client.subscribe("uwb/#", qos=0)
        print(f"[OK] Subscribed to: uwb/#")
    else:
        print(f"[ERROR] Connection failed with code: {rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        print(f"[MSG] Topic: {msg.topic}")
        print(f"[MSG] Payload: {json.dumps(payload, indent=2)}")
        print("-" * 50)
    except Exception as e:
        print(f"[ERROR] Failed to parse message: {e}")
        print(f"[MSG] Raw topic: {msg.topic}")
        print(f"[MSG] Raw payload: {msg.payload.decode()}")

def main():
    print("Starting MQTT subscriber to test data flow...")
    
    client = mqtt.Client(
        client_id="test_subscriber",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect("localhost", 1884, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
        client.disconnect()

if __name__ == "__main__":
    main()
