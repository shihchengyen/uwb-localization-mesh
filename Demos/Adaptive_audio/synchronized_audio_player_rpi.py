#!/usr/bin/env python3
"""
RPi Audio Player - MQTT Subscriber
Receives synchronized audio commands and executes them at specified global times
"""

import json
import time
import threading
import os
import sys
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
import pygame
import pathlib
from typing import Dict, Any

# Add packages to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from uwb_mqtt_client.config import MQTTConfig

# ====== NETWORK CONFIGURATION ======
# DEFAULT_BROKER_IP = "192.168.1.100"  # Your laptop's IP address
DEFAULT_BROKER_IP = "172.20.20.3"  # MSI's ip addr on iphone hotspot
DEFAULT_BROKER_PORT = 1884
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"
# ====================================


class RPiAudioPlayer:
    def __init__(self, rpi_id: int, wav_file: str, broker_ip: str = DEFAULT_BROKER_IP):
        self.rpi_id = rpi_id
        self.wav_file = wav_file
        self.broker_ip = broker_ip
        self.current_volume = 20  # Start at 20%
        self.is_playing = False
        self.audio_ready = False
        
        # MQTT setup
        self.config = MQTTConfig(
            broker=broker_ip,
            port=DEFAULT_BROKER_PORT,
            client_id=f"audio_player_rpi_{rpi_id}"
        )
        
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.config.client_id)
        self.client.username_pw_set(username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD)
        
        # Topics to subscribe to
        self.broadcast_topic = "audio/commands/broadcast"
        self.rpi_topic = f"audio/commands/rpi_{rpi_id}"
        
        # Command queue for synchronized execution
        self.command_queue = []
        self.queue_lock = threading.Lock()
        
        # Initialize audio
        self.init_audio()
        
        # Connect to MQTT
        self.connect_mqtt()
        
        # Start command execution thread
        self.execution_thread = threading.Thread(target=self.command_executor, daemon=True)
        self.execution_thread.start()
        
        print(f"🎵 RPi {rpi_id} Audio Player Ready")
        print(f"   WAV file: {wav_file}")
        print(f"   Position: {'LEFT' if rpi_id == 1 else 'RIGHT'}")
        print(f"   Initial volume: {self.current_volume}%")
    
    def init_audio(self):
        """Initialize pygame audio system."""
        try:
            # Configure for RPi 3.5mm jack
            os.environ["SDL_AUDIODRIVER"] = "alsa"
            os.environ["ALSA_CARD"] = "2"  # Use 3.5mm headphones jack
            
            pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=512)
            pygame.mixer.init()
            
            # Check if WAV file exists
            wav_path = pathlib.Path(self.wav_file)
            if not wav_path.exists():
                raise FileNotFoundError(f"WAV file not found: {wav_path}")
            
            # Load the audio file
            pygame.mixer.music.load(str(wav_path))
            self.audio_ready = True
            
            print(f"✅ Audio initialized successfully")
            
        except Exception as e:
            print(f"❌ Audio initialization failed: {e}")
            self.audio_ready = False
    
    def connect_mqtt(self):
        """Connect to MQTT broker and set up callbacks."""
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        try:
            self.client.connect(self.config.broker, self.config.port, self.config.keepalive)
            print(f"✅ Connected to MQTT broker at {self.config.broker}:{self.config.port}")
        except Exception as e:
            print(f"❌ Failed to connect to MQTT broker: {e}")
            sys.exit(1)
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback."""
        if rc == 0:
            print("✅ MQTT Connected successfully")
            # Subscribe to relevant topics
            client.subscribe(self.broadcast_topic, qos=1)
            client.subscribe(self.rpi_topic, qos=1)
            print(f"📡 Subscribed to: {self.broadcast_topic}")
            print(f"📡 Subscribed to: {self.rpi_topic}")
        else:
            print(f"❌ MQTT Connection failed with code {rc}")
    
    def on_message(self, client, userdata, msg):
        """MQTT message callback."""
        try:
            message = json.loads(msg.payload.decode())
            command = message.get("command")
            execute_time = message.get("execute_time")
            rpi_id = message.get("rpi_id")
            
            # Only process commands intended for this RPi or broadcast commands
            if rpi_id is None or rpi_id == self.rpi_id:
                self.queue_command(command, execute_time, message)
                
        except Exception as e:
            print(f"❌ Error processing MQTT message: {e}")
    
    def queue_command(self, command: str, execute_time: float, message: Dict[str, Any]):
        """Add command to execution queue."""
        with self.queue_lock:
            self.command_queue.append({
                "command": command,
                "execute_time": execute_time,
                "message": message,
                "queued_at": time.time()
            })
            
            # Sort queue by execute time
            self.command_queue.sort(key=lambda x: x["execute_time"])
            
            current_time = time.time()
            delay = execute_time - current_time
            
            print(f"📥 Queued: {command.upper()} (execute in {delay:.3f}s)")
    
    def execute_command(self, command: str, message: Dict[str, Any]):
        """Execute an audio command."""
        if not self.audio_ready:
            print(f"⚠️  Audio not ready, skipping command: {command}")
            return
        
        try:
            if command == "start":
                if not self.is_playing:
                    pygame.mixer.music.play(-1)  # Loop forever
                    self.is_playing = True
                    print(f"🎵 STARTED playing at {self.current_volume}%")
                else:
                    print(f"🎵 Already playing at {self.current_volume}%")
            
            elif command in ["left", "right"]:
                old_volume = self.current_volume
                
                if command == "left":
                    if self.rpi_id == 1:
                        # Left speaker gets louder
                        self.current_volume = min(100, self.current_volume + 10)
                    else:
                        # Right speaker gets quieter
                        self.current_volume = max(0, self.current_volume - 10)
                else:  # command == "right"
                    if self.rpi_id == 1:
                        # Left speaker gets quieter
                        self.current_volume = max(0, self.current_volume - 15)
                    else:
                        # Right speaker gets louder
                        self.current_volume = min(100, self.current_volume + 15)
                
                # Apply volume change
                pygame.mixer.music.set_volume(self.current_volume / 100.0)
                
                print(f"🔊 {command.upper()}: {old_volume}% → {self.current_volume}%")
                
        except Exception as e:
            print(f"❌ Error executing command {command}: {e}")
    
    def command_executor(self):
        """Background thread that executes queued commands at the right time."""
        while True:
            current_time = time.time()
            
            with self.queue_lock:
                # Execute commands that are due
                commands_to_execute = []
                remaining_commands = []
                
                for cmd in self.command_queue:
                    if cmd["execute_time"] <= current_time:
                        commands_to_execute.append(cmd)
                    else:
                        remaining_commands.append(cmd)
                
                self.command_queue = remaining_commands
            
            # Execute commands outside the lock
            for cmd in commands_to_execute:
                actual_delay = current_time - cmd["execute_time"]
                print(f"⚡ EXECUTING: {cmd['command'].upper()} (delay: {actual_delay:+.3f}s)")
                self.execute_command(cmd["command"], cmd["message"])
            
            time.sleep(0.01)  # Small delay to prevent busy waiting
    
    def run(self):
        """Run the audio player."""
        try:
            print(f"🎧 RPi {self.rpi_id} Audio Player running...")
            print("Press Ctrl+C to stop")
            
            # Start MQTT loop
            self.client.loop_start()
            
            # Keep main thread alive
            while True:
                time.sleep(1)
                
                # Print status every 10 seconds
                if int(time.time()) % 10 == 0:
                    with self.queue_lock:
                        queue_size = len(self.command_queue)
                    status = "PLAYING" if self.is_playing else "STOPPED"
                    print(f"📊 Status: {status}, Volume: {self.current_volume}%, Queue: {queue_size}")
                    time.sleep(1)  # Prevent duplicate prints
                    
        except KeyboardInterrupt:
            print(f"\n👋 Shutting down RPi {self.rpi_id} Audio Player...")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            if self.audio_ready:
                pygame.mixer.music.stop()
                pygame.mixer.quit()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="RPi Audio Player")
    parser.add_argument("--id", type=int, required=True, help="RPi ID (1=left, 2=right)")
    parser.add_argument("--wav", default="crazy-carls-brickhouse-tavern.wav", help="WAV file to play")
    parser.add_argument("--broker", default=DEFAULT_BROKER_IP, help="MQTT broker IP")
    
    args = parser.parse_args()
    
    # Validate RPi ID
    if args.id not in [1, 2]:
        print("❌ RPi ID must be 1 (left) or 2 (right)")
        sys.exit(1)
    
    player = RPiAudioPlayer(args.id, args.wav, args.broker)
    player.run()


if __name__ == "__main__":
    main()
