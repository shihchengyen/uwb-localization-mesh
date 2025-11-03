#!/usr/bin/env python3
"""
Adaptive Audio Controller

Controls speaker volumes and pairs based on user position.
Receives position updates and sends MQTT commands to audio players.

Logic:
- If y >= 300 → play on speakers 1 and 0 (back pair)
- If y < 300  → play on speakers 2 and 3 (front pair)
- For x-axis panning around x == 240:
  - At x == 240 → both speakers volume = 70
  - Move left  → increase RIGHT speaker volume, decrease LEFT speaker volume
  - Move right → increase LEFT speaker volume, decrease RIGHT speaker volume

"""

import json
import time
import logging
import threading
from datetime import datetime, timezone
from typing import Optional, Tuple
import numpy as np

import paho.mqtt.client as mqtt
import sys
import os
import uuid

# Suppress noisy logs
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("Server_bring_up").setLevel(logging.WARNING)
logging.getLogger("packages.uwb_mqtt_server").setLevel(logging.WARNING)

# Add repo root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from packages.uwb_mqtt_server.config import MQTTConfig
from packages.audio_mqtt_server.playlist_controller.playlist_controller import PlaylistController

# Defaults
DEFAULT_BROKER_IP = "localhost"
DEFAULT_BROKER_PORT = 1884
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"


def clamp(value: float, lo: int = 0, hi: int = 100) -> int:
    """Clamp value between lo and hi."""
    v = int(round(value))
    return max(lo, min(hi, v))


class AdaptiveAudioController:
    """
    Controller that adapts audio based on user position.

    Receives position updates and sends audio commands via MQTT.
    """

    def __init__(self, broker: str, port: int):
        """Initialize audio controller.

        Args:
            broker: MQTT broker IP
            port: MQTT broker port
        """

        self.audio_config = MQTTConfig(
            broker=broker,
            port=port,
            client_id=f"adaptive_audio_controller_{uuid.uuid4()}"
        )
        self.audio_client = mqtt.Client(client_id=self.audio_config.client_id)
        self.audio_client.username_pw_set(username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD)

        self.audio_topic = "audio/commands"

        # Audio control logic inside PlaylistController
        self.playlist_controller = PlaylistController()

        # State
        self.current_pair: Optional[str] = None  # "front" or "back"
        self.started_for_pair: Optional[str] = None
        self.volumes = {0: 70, 1: 70, 2: 70, 3: 70}
        self._last_position = None
        self.song_queue = []

        # Connect MQTT
        self._connect_audio_mqtt()

        print("🎛️ Adaptive Audio Controller initialized")
        print(f"   MQTT: {broker}:{port}")
    
    def _connect_audio_mqtt(self) -> None:
        """Connect to MQTT broker."""
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
    
    def _apply_state(self, pair: str, left_vol: int, right_vol: int) -> None:
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
    
    def update_position(self, position: np.ndarray) -> None:
        """
        Update audio based on new user position.
        
        Args:
            position: numpy array [x, y, z] in cm
        """
        # Check if position actually changed (avoid redundant updates)
        if self._last_position is not None:
            if np.linalg.norm(position - self._last_position) < 1.0:
                return  # Position hasn't changed enough
        
        self._last_position = position.copy()
        
        # Compute pair and volumes
        pair, (left_vol, right_vol) = self._compute_pair_and_volumes(position)
        
        # Apply audio changes
        self._apply_state(pair, left_vol, right_vol)
        
        # Print status
        self._print_status()

    def update_playlist_for_position(self, user_position: np.ndarray) -> None:
        """
        Update the playlist based on user position.
        This is called by the server when position changes.

        Args:
            user_position: numpy array [x, y, z] in cm
        """
        # Update playlist based on position
        self.song_queue = self.playlist_controller.update_playlist_based_on_position(user_position)

        # Also update audio hardware positioning
        self.update_position(user_position)
        

    def next_song(self) -> None:
        """
        Returns the next song in the playlist. Removes the song from the queue.
        Sends the command to the audio player to play the song.
        """
        song = self.song_queue.pop(0)
        # missing implementation to send the command to the audio player to play the song.
        return 
    
    def _print_status(self) -> None:
        """Print current status."""
        vols = self.volumes
        pair = self.current_pair or "unknown"
        line = f"Pair:{pair:>5} | Vols -> R0:{vols[0]:3d}  R1:{vols[1]:3d}  R2:{vols[2]:3d}  R3:{vols[3]:3d}"
        print(f"\r{line}", end="", flush=True)
    
    def start_all(self) -> None:
        """Start all speakers (manual control)."""
        for r in [0, 1, 2, 3]:
            self._send_audio_command("start", rpi_id=r)
    
    def pause_all(self) -> None:
        """Pause all speakers (manual control)."""
        for r in [0, 1, 2, 3]:
            self._send_audio_command("pause", rpi_id=r)
    
    def shutdown(self) -> None:
        """Shutdown audio controller."""
        # Shutdown MQTT
        self.audio_client.loop_stop()
        self.audio_client.disconnect()
        print("\n👋 Audio controller shut down")


def main() -> None:
    """
    Standalone test of audio controller.
    
    Usage:
        python adaptive_audio_controller.py --broker localhost --port 1884
    """
    import argparse
    parser = argparse.ArgumentParser(description="Adaptive Audio Controller")
    parser.add_argument("--broker", default=DEFAULT_BROKER_IP, help="MQTT broker IP")
    parser.add_argument("--port", type=int, default=DEFAULT_BROKER_PORT, help="MQTT broker port")
    args = parser.parse_args()
    
    # Create controller
    controller = AdaptiveAudioController(broker=args.broker, port=args.port)
    
    print("\n🎛️ Adaptive Audio Controller (Standalone)")
    print("   Logic: Y>=300 → back (1,0); Y<300 → front (2,3); X pans volumes around 240.")
    print("Keyboard: 's' START ALL, 'p' PAUSE ALL, 'q' QUIT")
    
    # Keyboard control
    import threading
    shutdown = False
    
    def keyboard_loop():
        nonlocal shutdown
        while not shutdown:
            try:
                cmd = input().strip().lower()
                if cmd == "q":
                    shutdown = True
                    break
                elif cmd == "s":
                    controller.start_all()
                    print("✅ Started all speakers")
                elif cmd == "p":
                    controller.pause_all()
                    print("⏸️  Paused all speakers")
            except (EOFError, KeyboardInterrupt):
                shutdown = True
                break
    
    threading.Thread(target=keyboard_loop, daemon=True).start()
    
    # Test with simulated positions
    try:
        import numpy as np
        while not shutdown:
            # Simulate user moving around
            test_positions = [
                np.array([240, 150, 0]),  # Front center
                np.array([300, 150, 0]),  # Front right
                np.array([180, 150, 0]),  # Front left
                np.array([240, 350, 0]),  # Back center
                np.array([300, 350, 0]),  # Back right
                np.array([180, 350, 0]),  # Back left
            ]
            
            for pos in test_positions:
                if shutdown:
                    break
                controller.update_position(pos)
                time.sleep(3)
                if shutdown:
                    break
                
    except KeyboardInterrupt:
        pass
    finally:
        shutdown = True
        controller.shutdown()


if __name__ == "__main__":
    main()
