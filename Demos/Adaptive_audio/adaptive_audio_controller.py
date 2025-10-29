#!/usr/bin/env python3
"""
Adaptive Audio Controller

Continuously reads user positions from ServerBringUp and:
- If y >= 300 → play on speakers 1 and 0 (back pair)
- If y < 300  → play on speakers 2 and 3 (front pair)
- For x-axis panning around x == 240:
  - At x == 240 → both speakers volume = 70
  - Move left  → increase RIGHT speaker volume, decrease LEFT speaker volume
  - Move right → increase LEFT speaker volume, decrease RIGHT speaker volume


To run: uv run Demos/Adaptive_audio/adaptive_audio_controller.py --broker <ip> --port 1884

"""

import json
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

import paho.mqtt.client as mqtt
import sys
import os
import uuid

# Add repo root to path to import packages and ServerBringUp
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from packages.uwb_mqtt_server.config import MQTTConfig
from Server_bring_up import ServerBringUp


# Defaults
DEFAULT_BROKER_IP = "localhost"
DEFAULT_BROKER_PORT = 1884
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"


def clamp(value: float, lo: int = 0, hi: int = 100) -> int:
    v = int(round(value))
    return max(lo, min(hi, v))


class AdaptiveAudioController(ServerBringUp):
    def __init__(self, broker: str, port: int, window_size_seconds: float = 1.0):
        mqtt_config = MQTTConfig(broker=broker, port=port)
        super().__init__(mqtt_config=mqtt_config, window_size_seconds=window_size_seconds)

        self.audio_config = MQTTConfig(broker=broker, port=port, client_id=f"adaptive_audio_controller_{uuid.uuid4()}" )
        self.audio_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.audio_config.client_id)
        self.audio_client.username_pw_set(username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD)

        self.audio_topic = "audio/commands"

        # State
        self.current_pair: Optional[str] = None  # "front" or "back"
        self.started_for_pair: Optional[str] = None

        # Connect MQTT for audio
        self._connect_audio_mqtt()

    def _connect_audio_mqtt(self) -> None:
        self.audio_client.connect(self.audio_config.broker, self.audio_config.port, self.audio_config.keepalive)
        self.audio_client.loop_start()

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

    def run(self) -> None:
        """Main adaptive loop."""
        # Start position server threads
        super().start()

        print("\n🎛️ Adaptive Audio Controller running...")
        print("Logic: Y>=300 → back (1,0); Y<300 → front (2,3); X pans volumes around 240.")
        try:
            while True:
                pos = self.user_position
                if pos is not None:
                    pair, (left_vol, right_vol) = self._compute_pair_and_volumes(pos)
                    self._apply_state(pair, left_vol, right_vol)
                time.sleep(0.2)  # 5 Hz updates
        except KeyboardInterrupt:
            print("\n👋 Shutting down Adaptive Audio Controller...")
        finally:
            super().stop()
            self.audio_client.loop_stop()
            self.audio_client.disconnect()


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Adaptive Audio Controller")
    parser.add_argument("--broker", default=DEFAULT_BROKER_IP, help="MQTT broker IP")
    parser.add_argument("--port", type=int, default=DEFAULT_BROKER_PORT, help="MQTT broker port")
    parser.add_argument("--window", type=float, default=1.0, help="Position tracking window size (seconds)")
    args = parser.parse_args()

    controller = AdaptiveAudioController(broker=args.broker, port=args.port, window_size_seconds=args.window)
    controller.run()


if __name__ == "__main__":
    main()


