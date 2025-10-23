#!/usr/bin/env python3
"""
Position-Aware Audio Controller - MQTT Publisher
Sends synchronized audio commands to RPi speakers based on user position with global timing
"""

import json
import time
import threading
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
from typing import Dict, Any, Optional
import sys
import os
import numpy as np

# Add packages to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from uwb_mqtt_server.config import MQTTConfig
from Server_bring_up import ServerBringUp

# ====== NETWORK CONFIGURATION ======
# DEFAULT_BROKER_IP = "192.168.1.100"  # Your laptop's IP address
DEFAULT_BROKER_IP = "172.20.10.3"  # MSI's ip addr on iphone hotspot
DEFAULT_BROKER_PORT = 1884
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"
# ====================================


class PositionAwareAudioController(ServerBringUp):
    def __init__(
        self, 
        broker_ip: str = DEFAULT_BROKER_IP, 
        broker_port: int = DEFAULT_BROKER_PORT, 
        window_size_seconds: float = 1.0
        ):
        # Initialize base server for position tracking
        mqtt_config = MQTTConfig(broker=broker_ip, port=broker_port)
        super().__init__(mqtt_config, window_size_seconds)
        
        self.broker_ip = broker_ip
        self.broker_port = broker_port
        self.target_delay = 0.5  # 500ms delay from keyboard interrupt to execution
        
        # Audio MQTT setup (separate from position tracking)
        self.audio_config = MQTTConfig(
            broker=broker_ip,
            port=broker_port,
            client_id="audio_controller_laptop"
        )
        
        self.audio_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.audio_config.client_id)
        self.audio_client.username_pw_set(username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD)
        
        # Topic for audio commands
        self.audio_topic = "audio/commands"
        
        # Connect to audio MQTT
        self.connect_audio_mqtt()
        
        # Current volume tracking for each speaker pair
        self.volumes = {0: 70, 1: 70, 2: 70, 3: 70}  # RPi ID -> current volume
        
        # Position-based speaker control
        self.current_speaker_pair = None  # "front" (0,1) or "back" (2,3)
        self.position_threshold = 300.0  # Y axis threshold in cm
        
        # Thread safety
        self.audio_lock = threading.Lock()
        
    def connect_audio_mqtt(self):
        """Connect to audio MQTT broker."""
        try:
            self.audio_client.connect(self.audio_config.broker, self.audio_config.port, self.audio_config.keepalive)
            print(f"✅ Connected to audio MQTT broker at {self.audio_config.broker}:{self.audio_config.port}")
        except Exception as e:
            print(f"❌ Failed to connect to audio MQTT broker: {e}")
            sys.exit(1)
    
    def get_global_time(self) -> float:
        """Get current global time in seconds since epoch."""
        return time.time()
    
    def determine_speaker_pair(self, position: Optional[np.ndarray]) -> str:
        """Determine which speaker pair should be active based on position."""
        if position is None:
            return "back"  # Default to back pair if no position data
        
        y_coord = position[1]  # Y coordinate in cm
        
        if y_coord >= self.position_threshold:
            return "back"   # RPi 1,0 (back speakers)
        else:
            return "front"  # RPi 3,2 (front speakers)
    
    def update_speaker_control(self):
        """Update speaker control based on current position. Control as in mute one of the pairs, enable the other."""
        if self.user_position is None:
            return
        
        new_speaker_pair = self.determine_speaker_pair(self.user_position)
        
        if new_speaker_pair != self.current_speaker_pair:
            with self.audio_lock:
                self.current_speaker_pair = new_speaker_pair
                
                # Mute the inactive pair
                if new_speaker_pair == "front":
                    # Mute back speakers (1,0), enable front speakers (3,2)
                    self._mute_speakers([0, 1])
                    print(f"🎯 Position Y={self.user_position[1]:.1f}cm > {self.position_threshold}cm → Front speakers (RPi 3,2) active")
                else:
                    # Mute front speakers (3,2), enable back speakers (1,0)
                    self._mute_speakers([2, 3])
                    print(f"🎯 Position Y={self.user_position[1]:.1f}cm ≤ {self.position_threshold}cm → Back speakers (RPi 1,0) active")
    
    def _mute_speakers(self, rpi_ids: list):
        """Mute specified speakers by setting volume to 0."""
        for rpi_id in rpi_ids:
            self.send_audio_command("volume", rpi_id=rpi_id, volume=0)
    
    def _unmute_speakers(self, rpi_ids: list):
        """Unmute specified speakers by restoring their tracked volume."""
        for rpi_id in rpi_ids:
            self.send_audio_command("volume", rpi_id=rpi_id, volume=self.volumes[rpi_id])
    
    def send_audio_command(self, command: str, rpi_id: Optional[int] = None, volume: Optional[int] = None):
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
        
        # Add volume if specified
        if volume is not None: # volume is set by the controller, but can be muted (overridden by vol=0)
            message["target_volume"] = volume
            if rpi_id is not None:
                self.volumes[rpi_id] = volume
        
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
        
        self.audio_client.publish(topic, payload, qos=1)
        self.audio_client.loop_write()  # Ensure message is sent
    
    def send_command(self, command: str, rpi_id: Optional[int] = None):
        """Send audio command with position-aware speaker control."""
        # Update speaker control based on current position
        self.update_speaker_control()
        
        # Determine which speakers should receive the command
        if self.current_speaker_pair == "front":
            active_speakers = [2, 3]  # RPi 2,3
        else:
            active_speakers = [0, 1]  # RPi 0,1
        
        # Send command only to active speakers
        if rpi_id is None:
            # Send to all active speakers
            for speaker_id in active_speakers:
                self.send_audio_command(command, rpi_id=speaker_id)
        elif rpi_id in active_speakers:
            # Send to specific active speaker
            self.send_audio_command(command, rpi_id=rpi_id)
        else:
            # Speaker is not active, don't send command
            print(f"⚠️  RPi {rpi_id} is not active (current pair: {self.current_speaker_pair})")
    
    def keyboard_loop(self):
        """Main keyboard input loop."""
        print("\n🎹 Position-Aware Audio Controller Ready!")
        print("Keyboard Commands:")
        print("  s = START (start audio on active speaker pair)")
        print("  p = PAUSE (pause audio on active speaker pair)")
        print("  a = LEFT (pan left - active speakers only)")
        print("  d = RIGHT (pan right - active speakers only)")
        print("  q = QUIT")
        # print(f"\nPosition threshold: Y = {self.position_threshold}cm")
        # print("  Y > 300cm → Back speakers (RPi 0,1) active")
        # print("  Y ≤ 300cm → Front speakers (RPi 2,3) active")
        print("\nPress keys and Enter...")
        
        while True:
            try:
                user_input = input().strip().lower()
                
                if user_input == 'q':
                    print("👋 Shutting down...")
                    break
                elif user_input == 's':
                    self.send_command("start")
                elif user_input == 'p':
                    # Send pause command to all RPIs
                    for rpi_id in [0, 1, 2, 3]:
                        self.send_command("pause", rpi_id=rpi_id)
                elif user_input == 'a':
                    self.send_command("left")
                elif user_input == 'd':
                    self.send_command("right")
                else:
                    print(f"❌ Unknown command: {user_input}")
                    print("Valid commands: s, p, a, d, q")
                    
            except KeyboardInterrupt:
                print("\n👋 Shutting down...")
                break
            except EOFError:
                print("\n👋 Shutting down...")
                break
    
    def start(self):
        """Start both position tracking and audio controller."""
        # Start position tracking server
        super().start()
        
        # Start audio controller
        self.keyboard_loop()
    
    def stop(self):
        """Stop both position tracking and audio controller."""
        # Stop audio MQTT client
        self.audio_client.disconnect()
        
        # Stop base server
        super().stop()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Position-Aware Audio Controller")
    parser.add_argument("--broker", default=DEFAULT_BROKER_IP, help="MQTT broker IP")
    parser.add_argument("--port", type=int, default=1884, help="MQTT broker port")
    parser.add_argument("--delay", type=float, default=0.5, help="Target execution delay in seconds")
    # parser.add_argument("--window", type=float, default=1.0, help="Position tracking window size (seconds)")
    
    args = parser.parse_args()
    
    controller = PositionAwareAudioController(args.broker, args.port, args.window)
    controller.target_delay = args.delay
    
    try:
        controller.start()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
