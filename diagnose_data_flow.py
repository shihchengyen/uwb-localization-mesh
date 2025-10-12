#!/usr/bin/env python3
"""
Diagnose data flow between RPi anchors and laptop.
"""

import paho.mqtt.client as mqtt
import json
import time
import sys
from datetime import datetime

class DataFlowDiagnostic:
    def __init__(self):
        self.message_count = 0
        self.last_message_time = None
        self.start_time = time.time()
        
    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Connected to MQTT broker")
            # Subscribe to all UWB topics
            client.subscribe("uwb/#", qos=0)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Subscribed to: uwb/#")
            print("Waiting for messages...")
            print("-" * 60)
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Connection failed with code: {rc}")

    def on_message(self, client, userdata, msg):
        self.message_count += 1
        self.last_message_time = time.time()
        
        try:
            payload = json.loads(msg.payload.decode())
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Message #{self.message_count}")
            print(f"  Topic: {msg.topic}")
            print(f"  Anchor ID: {payload.get('anchor_id', 'N/A')}")
            print(f"  Vector: {payload.get('vector_local', 'N/A')}")
            print(f"  Timestamp: {payload.get('timestamp', 'N/A')}")
            print("-" * 60)
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Message #{self.message_count} (Parse Error)")
            print(f"  Topic: {msg.topic}")
            print(f"  Raw: {msg.payload.decode()}")
            print(f"  Error: {e}")
            print("-" * 60)

    def on_disconnect(self, client, userdata, rc):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Disconnected from broker (rc={rc})")

    def run(self):
        print("UWB Data Flow Diagnostic Tool")
        print("=" * 60)
        
        client = mqtt.Client(
            client_id="diagnostic_tool",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.on_disconnect = self.on_disconnect
        
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Connecting to localhost:1884...")
            client.connect("localhost", 1884, 60)
            
            # Run for 30 seconds or until interrupted
            client.loop_start()
            
            while True:
                time.sleep(5)
                elapsed = time.time() - self.start_time
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Status: {self.message_count} messages in {elapsed:.1f}s")
                
                if self.last_message_time and (time.time() - self.last_message_time) > 10:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] WARNING: No messages for 10+ seconds")
                
        except KeyboardInterrupt:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Stopping...")
            print(f"Total messages received: {self.message_count}")
            client.disconnect()

if __name__ == "__main__":
    diagnostic = DataFlowDiagnostic()
    diagnostic.run()
