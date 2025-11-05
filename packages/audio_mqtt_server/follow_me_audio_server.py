#!/usr/bin/env python3
"""
Follow-Me Methods for audio control

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
    uv run follow-me_audio_server.py --broker localhost --port 1884

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


# Defaults
DEFAULT_BROKER_IP = "localhost"
DEFAULT_BROKER_PORT = 1884
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"


def clamp(value: float, lo: int = 0, hi: int = 100) -> int:
    v = int(round(value))
    return max(lo, min(hi, v))


class AdaptiveAudioServer:
    """
    Audio controller that sends commands to RPi speakers based on position.
    
    Should be called from ServerBringUp where position updates are processed.
    """


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
        # self._print_status()
    
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
    

    def compute_pair_and_volumes(self, position) -> Tuple[str, Tuple[int, int]]:
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

    # # def get_status(self) -> dict:
    #     """
    #     Get current audio status.
        
    #     Returns:
    #         dict with keys:
    #         - 'current_pair': "front" or "back"
    #         - 'volumes': dict {0: vol, 1: vol, 2: vol, 3: vol}
    #         - 'active_speakers': list of active RPi IDs
    #         - 'inactive_speakers': list of inactive RPi IDs
    #     """
    #     active = []
    #     inactive = []
    #     if self.current_pair == "front":
    #         active = [2, 3]  # Front pair
    #         inactive = [0, 1]
    #     elif self.current_pair == "back":
    #         active = [1, 0]  # Back pair
    #         inactive = [2, 3]
        
    #     return {
    #         "current_pair": self.current_pair,
    #         "volumes": self.volumes.copy(),
    #         "active_speakers": active,
    #         "inactive_speakers": inactive
    #     }
    
    def zone_dj_start(self) -> None:
        """Start Zone DJ mode: play 70%, all speakers."""
        for r in [0, 1, 2, 3]:
            self._send_audio_command("volume", rpi_id=r, volume=70)
        for r in [0, 1, 2, 3]:
            self._send_audio_command("start", rpi_id=r)

    def zone_dj_pause(self) -> None:
        """Pause Zone DJ mode: pause all speakers."""
        for r in [0, 1, 2, 3]:
            self._send_audio_command("pause", rpi_id=r)

    def shutdown(self) -> None:
        """Shutdown audio server."""
        self.audio_client.loop_stop()
        self.audio_client.disconnect()
        print("\n👋 Follow-Me Audio Server shut down")
