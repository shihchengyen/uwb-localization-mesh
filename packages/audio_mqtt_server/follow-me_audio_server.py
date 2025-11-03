#!/usr/bin/env python3
"""
Follow-Me Audio Server

Coordinates UWB positioning (via ServerBringUp) and adaptive audio control.
ServerBringUp tracks user position and adapts audio accordingly.

Architecture:
- ServerBringUp: Handles UWB measurements, PGO, position tracking
- FollowMeAudioServer: Controls RPi speakers based on position
- FollowMeAudioClient: Receives and plays audio on RPi

Logic:
- If y >= 300 → play on speakers 1 and 0 (back pair)
- If y < 300  → play on speakers 2 and 3 (front pair)
- For x-axis panning around x == 240:
  - At x == 240 → both speakers volume = 70
  - Move left  → increase RIGHT speaker volume, decrease LEFT speaker volume
  - Move right → increase LEFT speaker volume, decrease RIGHT speaker volume

Usage:
    python follow-me_audio_server.py --broker localhost --port 1884

"""

import json
import time
import logging
from datetime import datetime, timezone
from typing import Tuple, Optional
import numpy as np
import paho.mqtt.client as mqtt
import uuid

import sys
import os

# Suppress noisy logs
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("Server_bring_up").setLevel(logging.WARNING)
logging.getLogger("packages.uwb_mqtt_server").setLevel(logging.WARNING)

# Add repo root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from packages.uwb_mqtt_server.config import MQTTConfig
from Server_bring_up import ServerBringUp

# Defaults
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"


def clamp(value: float, lo: int = 0, hi: int = 100) -> int:
    """Clamp value between lo and hi."""
    v = int(round(value))
    return max(lo, min(hi, v))


class FollowMeAudioServer(ServerBringUp):
    """
    ServerBringUp with integrated audio control.
    
    Tracks user position via UWB and controls RPi speakers based on position.
    """
    
    def __init__(
        self,
        broker: str,
        port: int,
        window_size_seconds: float = 1.0,
        enable_audio: bool = True
    ):
        """Initialize server with audio control."""
        
        # Initialize ServerBringUp (UWB positioning)
        mqtt_config = MQTTConfig(broker=broker, port=port)
        super().__init__(mqtt_config=mqtt_config, window_size_seconds=window_size_seconds)
        
        # Audio MQTT setup (separate from UWB MQTT)
        self.audio_config = MQTTConfig(
            broker=broker,
            port=port,
            client_id=f"follow_me_audio_server_{uuid.uuid4()}"
        )
        self.audio_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.audio_config.client_id)
        self.audio_client.username_pw_set(username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD)
        
        self.audio_topic = "audio/commands"
        self.enable_audio = enable_audio
        
        # Audio state
        self.current_pair: Optional[str] = None  # "front" or "back"
        self.started_for_pair: Optional[str] = None
        self.volumes = {0: 70, 1: 70, 2: 70, 3: 70}
        
        # Track last reported position to avoid duplicate updates
        self._last_position = None
        
        # Connect audio MQTT if enabled
        if self.enable_audio:
            self._connect_audio_mqtt()
        
        print("🎛️ Follow-Me Audio Server initialized")
        print(f"   UWB MQTT: {broker}:{port}")
        print(f"   Audio control: {'enabled' if enable_audio else 'disabled'}")
    
    def _connect_audio_mqtt(self) -> None:
        """Connect to MQTT broker for audio commands."""
        self.audio_client.connect(self.audio_config.broker, self.audio_config.port, self.audio_config.keepalive)
        self.audio_client.loop_start()
    
    def _publish(self, topic: str, payload_obj: dict) -> None:
        """Publish MQTT message."""
        payload = json.dumps(payload_obj, separators=(",", ":"))
        self.audio_client.publish(topic, payload, qos=1)
    
    def _send_audio_command(self, command: str, rpi_id: Optional[int] = None, volume: Optional[int] = None) -> None:
        """Send audio command via MQTT."""
        now = time.time()
        execute_time = now + 0.5  # 500ms lookahead
        
        msg = {
            "command": command,
            "execute_time": execute_time,
            "global_time": now,
            "delay_ms": 500,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rpi_id": rpi_id,
            "command_id": str(uuid.uuid4()),
        }
        
        if volume is not None:
            msg["target_volume"] = clamp(volume)
        
        if rpi_id is None:
            topic = f"{self.audio_topic}/broadcast"
        else:
            topic = f"{self.audio_topic}/rpi_{rpi_id}"
        
        self._publish(topic, msg)
        
        # Track local volume state (for monitoring)
        if command == "volume" and rpi_id is not None and volume is not None:
            self.volumes[rpi_id] = clamp(volume)
    
    def _compute_pair_and_volumes(self, position: np.ndarray) -> Tuple[str, Tuple[int, int]]:
        """
        Compute speaker pair and volumes based on position.
        
        Returns (pair, (left_vol, right_vol)) where:
        - pair == "front" → speakers (2,3)
        - pair == "back"  → speakers (1,0)
        - Volumes are for LEFT vs RIGHT speaker in the selected pair
        """
        x = float(position[0])
        y = float(position[1])
        
        # Pair by Y threshold
        pair = "back" if y >= 300.0 else "front"
        
        # Pan by X around center x == 240
        center_x = 240.0
        delta = x - center_x  # >0 → right; <0 → left
        
        base = 70.0
        k = 0.1  # volume change per cm offset from center
        
        # Moving right (delta>0): increase LEFT, decrease RIGHT
        left_vol = base + k * delta
        right_vol = base - k * delta
        
        left_vol = clamp(left_vol)
        right_vol = clamp(right_vol)
        
        return pair, (left_vol, right_vol)
    
    def _apply_audio_state(self, pair: str, left_vol: int, right_vol: int) -> None:
        """Send MQTT commands to apply the given pair and volumes."""
        if pair == "front":
            # Active: speakers 2 (LEFT), 3 (RIGHT). Inactive: 0,1
            # Ensure active pair is started at least once
            if self.started_for_pair != pair:
                # Unmute all first to ensure START is heard
                for r in [0, 1, 2, 3]:
                    self._send_audio_command("volume", rpi_id=r, volume=70)
                for r in [0, 1, 2, 3]:
                    self._send_audio_command("start", rpi_id=r)
                self.started_for_pair = pair
            
            # Set active volumes
            self._send_audio_command("volume", rpi_id=2, volume=left_vol)
            self._send_audio_command("volume", rpi_id=3, volume=right_vol)
            # Mute inactive
            self._send_audio_command("volume", rpi_id=0, volume=0)
            self._send_audio_command("volume", rpi_id=1, volume=0)
        
        else:  # back
            # Active: speakers 1 (LEFT), 0 (RIGHT). Inactive: 2,3
            if self.started_for_pair != pair:
                for r in [0, 1, 2, 3]:
                    self._send_audio_command("volume", rpi_id=r, volume=70)
                for r in [0, 1, 2, 3]:
                    self._send_audio_command("start", rpi_id=r)
                self.started_for_pair = pair
            
            self._send_audio_command("volume", rpi_id=1, volume=left_vol)
            self._send_audio_command("volume", rpi_id=0, volume=right_vol)
            # Mute inactive
            self._send_audio_command("volume", rpi_id=2, volume=0)
            self._send_audio_command("volume", rpi_id=3, volume=0)
        
        self.current_pair = pair
    
    def _on_position_updated(self):
        """Called when user position changes."""
        if not self.enable_audio or self.user_position is None:
            return
        
        # Check if position actually changed (avoid redundant updates)
        if self._last_position is not None:
            if np.linalg.norm(self.user_position - self._last_position) < 1.0:
                return  # Position hasn't changed enough
        
        self._last_position = self.user_position.copy()
        
        # Compute pair and volumes
        pair, (left_vol, right_vol) = self._compute_pair_and_volumes(self.user_position)
        
        # Apply audio changes
        self._apply_audio_state(pair, left_vol, right_vol)
        
        # Print status
        self._print_status()
    
    def _print_status(self) -> None:
        """Print current audio status."""
        vols = self.volumes
        pair = self.current_pair or "unknown"
        line = f"Pair:{pair:>5} | Vols -> R0:{vols[0]:3d}  R1:{vols[1]:3d}  R2:{vols[2]:3d}  R3:{vols[3]:3d}"
        print(f"\r{line}", end="", flush=True)
    
    def run(self):
        """Run the server with position monitoring."""
        # Start ServerBringUp
        self.start()
        
        print("\n🎵 Follow-Me Audio Server running...")
        print("   Logic: Y>=300 → back (1,0); Y<300 → front (2,3); X pans volumes around 240")
        print("   Press Ctrl+C to stop")
        
        try:
            while True:
                # Check if position changed
                if self.user_position is not None:
                    # Trigger position update callback
                    self._on_position_updated()
                
                time.sleep(0.1)  # Check at ~10 Hz
                
        except KeyboardInterrupt:
            print("\n👋 Shutting down Follow-Me Audio Server...")
        finally:
            self.stop()
            if self.enable_audio:
                self.audio_client.loop_stop()
                self.audio_client.disconnect()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Follow-Me Audio Server")
    parser.add_argument("--broker", default="localhost", help="MQTT broker IP")
    parser.add_argument("--port", type=int, default=1884, help="MQTT broker port")
    parser.add_argument("--window", type=float, default=1.0, help="Position window size (seconds)")
    parser.add_argument("--no-audio", action="store_true", help="Disable audio control (position only)")
    
    args = parser.parse_args()
    
    # Create and run server
    server = FollowMeAudioServer(
        broker=args.broker,
        port=args.port,
        window_size_seconds=args.window,
        enable_audio=not args.no_audio
    )
    
    server.run()


if __name__ == "__main__":
    main()

