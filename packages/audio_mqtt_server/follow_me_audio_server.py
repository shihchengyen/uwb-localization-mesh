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
from typing import Optional, Tuple
import numpy as np

import paho.mqtt.client as mqtt
import uuid

# Suppress MQTT and position logs logs after imports (to override basicConfig) - only show WARNING and above
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("Server_bring_up").setLevel(logging.WARNING)
logging.getLogger("packages.uwb_mqtt_server").setLevel(logging.WARNING)

# # Add repo root to path to import packages and ServerBringUp
# sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
# from packages.uwb_mqtt_server.config import MQTTConfig
# from Server_bring_up import ServerBringUp


# Defaults
DEFAULT_BROKER_IP = "localhost"
DEFAULT_BROKER_PORT = 1884
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"


def clamp(value: float, lo: int = 0, hi: int = 100) -> int:
    v = int(round(value))
    return max(lo, min(hi, v))


class FollowMeAudioServer:
    """
    Audio controller that sends commands to RPi speakers based on position.
    
    Should be called from ServerBringUp where position updates are processed.
    """
    
    def __init__(self, broker: str, port: int, keepalive: int = 60):
        """Initialize audio server with MQTT connection."""
        
        # Audio MQTT setup
        client_id = f"follow_me_audio_server_{uuid.uuid4()}"
        self.audio_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self.audio_client.username_pw_set(username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD)

        self.audio_topic = "audio/commands"

        # State
        self.current_pair: Optional[str] = None  # "front" or "back"
        self.started_for_pair: Optional[str] = None
        self.volumes = {0: 70, 1: 70, 2: 70, 3: 70}
        self._last_position = None

        # Connect MQTT for audio
        self.audio_client.connect(broker, port, keepalive)
        self.audio_client.loop_start()
        
        print("🎛️ Follow-Me Audio Server initialized")
        # print(f"   MQTT: {broker}:{port}")

    def _publish(self, topic: str, payload_obj: dict) -> None:
        payload = json.dumps(payload_obj, separators=(",", ":"))
        self.audio_client.publish(topic, payload, qos=1)

    def _send_audio_command(self, command: str, rpi_id: Optional[int] = None, volume: Optional[int] = None) -> None:
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

        # Track local volume state (for live monitoring)
        if command == "volume" and rpi_id is not None and volume is not None:
            self.volumes[rpi_id] = clamp(volume)

    def _compute_pair_and_volumes(self, position) -> Tuple[str, Tuple[int, int]]:
        """
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

    def update_position(self, position) -> None:
        """
        Update audio based on new user position.
        
        This is the main method called by ServerBringUp when position changes.
        
        Args:
            position: numpy array or tuple [x, y, z] in cm
        """
        # Convert to numpy array if needed
        if not isinstance(position, np.ndarray):
            position = np.array(position)
        
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
    
    def _print_status(self) -> None:
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
    
    def get_status(self) -> dict:
        """
        Get current audio status.
        
        Returns:
            dict with keys:
            - 'current_pair': "front" or "back"
            - 'volumes': dict {0: vol, 1: vol, 2: vol, 3: vol}
            - 'active_speakers': list of active RPi IDs
            - 'inactive_speakers': list of inactive RPi IDs
        """
        active = []
        inactive = []
        if self.current_pair == "front":
            active = [2, 3]  # Front pair
            inactive = [0, 1]
        elif self.current_pair == "back":
            active = [1, 0]  # Back pair
            inactive = [2, 3]
        
        return {
            "current_pair": self.current_pair,
            "volumes": self.volumes.copy(),
            "active_speakers": active,
            "inactive_speakers": inactive
        }
    
    def shutdown(self) -> None:
        """Shutdown audio server."""
        self.audio_client.loop_stop()
        self.audio_client.disconnect()
        print("\n👋 Follow-Me Audio Server shut down")
