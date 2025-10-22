#!/usr/bin/env python3
"""
Laptop Audio Controller - MQTT Publisher
Sends synchronized audio commands to RPi speakers with global timing
"""

import json
import time
import threading
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
from typing import Dict, Any
import sys
import os

# Add packages to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from uwb_mqtt_server.config import MQTTConfig

# ====== NETWORK CONFIGURATION ======
# DEFAULT_BROKER_IP = "192.168.1.100"  # Your laptop's IP address
DEFAULT_BROKER_IP = "172.20.10.3"  # MSI's ip addr on iphone hotspot
DEFAULT_BROKER_PORT = 1884
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"
# ====================================


class AudioController:
    def __init__(self, broker_ip: str = DEFAULT_BROKER_IP, broker_port: int = DEFAULT_BROKER_PORT):
        self.broker_ip = broker_ip
        self.broker_port = broker_port
        self.target_delay = 0.5  # 500ms delay from keyboard interrupt to execution
        
        # MQTT setup
        self.config = MQTTConfig(
            broker=broker_ip,
            port=broker_port,
            client_id="audio_controller_laptop"
        )
        
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.config.client_id)
        self.client.username_pw_set(username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD)
        
        # Topic for audio commands
        self.audio_topic = "audio/commands"
        
        # Connect to MQTT
        self.connect_mqtt()
        
        # Current volume tracking
        self.volumes = {0: 70, 1: 70, 2: 70, 3: 70}  # RPi ID -> current volume
        
    def connect_mqtt(self):
        """Connect to MQTT broker."""
        try:
            self.client.connect(self.config.broker, self.config.port, self.config.keepalive)
            print(f"✅ Connected to MQTT broker at {self.config.broker}:{self.config.port}")
        except Exception as e:
            print(f"❌ Failed to connect to MQTT broker: {e}")
            sys.exit(1)
    
    def get_global_time(self) -> float:
        """Get current global time in seconds since epoch."""
        return time.time()
    
    def send_command(self, command: str, rpi_id: int = None):
        """Send audio command with global timing."""
        global_time = self.get_global_time()
        execute_time = global_time + self.target_delay
        
        # Create command message
        message = {
            "command": command,
            "execute_time": execute_time,
            "global_time": global_time,
            "delay_ms": int(self.target_delay * 1000),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rpi_id": rpi_id  # None means broadcast to all
        }
        
        # Update volume tracking for left/right commands
        if command in ["left", "right"] and rpi_id is not None:
            if command == "left":
                if rpi_id in [1, 2]:  # Left speakers get louder
                    self.volumes[rpi_id] = min(100, self.volumes[rpi_id] + 10)
                else:  # Right speakers get quieter
                    self.volumes[rpi_id] = max(0, self.volumes[rpi_id] - 10)
            elif command == "right":
                if rpi_id in [1, 2]:  # Left speakers get quieter
                    self.volumes[rpi_id] = max(0, self.volumes[rpi_id] - 15)
                else:  # Right speakers get louder
                    self.volumes[rpi_id] = min(100, self.volumes[rpi_id] + 15)
            
            message["target_volume"] = self.volumes[rpi_id]
        
        # Publish to MQTT
        payload = json.dumps(message, indent=None)
        
        if rpi_id:
            topic = f"{self.audio_topic}/rpi_{rpi_id}"
            print(f"📤 {command.upper()} → RPi {rpi_id} (vol: {message.get('target_volume', 'N/A')})")
        else:
            topic = f"{self.audio_topic}/broadcast"
            print(f"📤 {command.upper()} → ALL RPIs")
        
        print(f"   Topic: {topic}")
        print(f"   Execute at: {execute_time:.3f} (in {self.target_delay}s)")
        print(f"   Global time: {global_time:.3f}")
        
        self.client.publish(topic, payload, qos=1)
        self.client.loop_write()  # Ensure message is sent
    
    def keyboard_loop(self):
        """Main keyboard input loop."""
        print("\n🎹 Audio Controller Ready!")
        print("Keyboard Commands:")
        print("  s = START (broadcast to all RPIs)")
        print("  a = LEFT (pan left - RPi 1,2 louder; RPi 0,3 quieter)")
        print("  d = RIGHT (pan right - RPi 1,2 quieter; RPi 0,3 louder)")
        print("  q = QUIT")
        print("\nPress keys and Enter...")
        
        while True:
            try:
                user_input = input().strip().lower()
                
                if user_input == 'q':
                    print("👋 Shutting down...")
                    break
                elif user_input == 's':
                    self.send_command("start")
                elif user_input == 'a':
                    print("Choose RPi (1,2=left; 0,3=right; or press Enter for all):")
                    rpi_choice = input().strip()
                    if rpi_choice in ["1", "2"]:
                        self.send_command("left", rpi_id=int(rpi_choice))
                    elif rpi_choice in ["0", "3"]:
                        self.send_command("left", rpi_id=int(rpi_choice))
                    else:
                        # Send to all RPIs
                        for rpi_id in [0, 1, 2, 3]:
                            self.send_command("left", rpi_id=rpi_id)
                elif user_input == 'd':
                    print("Choose RPi (1,2=left; 0,3=right; or press Enter for all):")
                    rpi_choice = input().strip()
                    if rpi_choice in ["1", "2"]:
                        self.send_command("right", rpi_id=int(rpi_choice))
                    elif rpi_choice in ["0", "3"]:
                        self.send_command("right", rpi_id=int(rpi_choice))
                    else:
                        # Send to all RPIs
                        for rpi_id in [0, 1, 2, 3]:
                            self.send_command("right", rpi_id=rpi_id)
                else:
                    print(f"❌ Unknown command: {user_input}")
                    print("Valid commands: s, a, d, q")
                    
            except KeyboardInterrupt:
                print("\n👋 Shutting down...")
                break
            except EOFError:
                print("\n👋 Shutting down...")
                break
    
    def run(self):
        """Run the audio controller."""
        try:
            self.keyboard_loop()
        finally:
            self.client.disconnect()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Laptop Audio Controller")
    parser.add_argument("--broker", default=DEFAULT_BROKER_IP, help="MQTT broker IP")
    parser.add_argument("--port", type=int, default=1884, help="MQTT broker port")
    parser.add_argument("--delay", type=float, default=0.5, help="Target execution delay in seconds")
    
    args = parser.parse_args()
    
    controller = AudioController(args.broker, args.port)
    controller.target_delay = args.delay
    controller.run()


if __name__ == "__main__":
    main()
