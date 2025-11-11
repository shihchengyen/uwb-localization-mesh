"""
Dummy Server Bring-up for testing and demos without physical hardware.
Simulates user movement and generates fake UWB measurements.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import packages
# This allows the script to be run from any directory
script_dir = Path(__file__).parent.resolve()
repo_root = script_dir.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import json
import logging
import threading
import time
import math
import datetime
# Removed defaultdict, Queue imports - no longer needed
from typing import Dict, Optional

import numpy as np
import uuid
import paho.mqtt.client as mqtt

# Removed: Measurement, BinnedData, SlidingWindowBinner, transforms, edge_creation, PGOSolver
# We no longer need these for the simplified dummy server
from packages.uwb_mqtt_server.config import MQTTConfig
try:
    from packages.audio_mqtt_server.adaptive_audio_controller import AdaptiveAudioController as AdaptiveAudioServer, clamp
except ImportError:
    # Fallback if audio server is not available
    AdaptiveAudioServer = None
    def clamp(value: float, lo: int = 0, hi: int = 100) -> int:
        """Clamp value between lo and hi."""
        v = int(round(value))
        return max(lo, min(hi, v))

# Setup JSON logging
logging.basicConfig(
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Defaults
DEFAULT_BROKER_IP = "localhost"
DEFAULT_BROKER_PORT = 1884
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"

class DummyServerBringUpProMax:
    """
    Dummy server that simulates user movement and generates fake measurements.
    Uses the same processing pipeline as the real ServerBringUpProMax.
    Includes audio control functionality for testing demos.
    """

    def __init__(
        self,
        mqtt_config: Optional[MQTTConfig] = None,  # Not used in dummy mode
        window_size_seconds: float = 1.0,
        jitter_std: float = 0.0,  # Standard deviation for anchor position jitter (cm)
        simulation_speed: float = 0.01,  # Speed multiplier for simulation (0.01 = very slow)
        phone_node_id: int = 0  # Simulated phone ID
    ):
        """Initialize the dummy server with configuration."""

        # Ground truth anchor positions (cm) - Consistent with Basic_render_graph
        # Anchors are mounted at 239 cm (2.39m) height
        self.true_nodes = {
            0: np.array([480, 600, 0]),  # top-right
            1: np.array([0, 600, 0]),    # top-left
            2: np.array([480, 0, 0]),    # bottom-right
            3: np.array([0, 0, 0])       # bottom-left (origin)
        }

        # Working copy of nodes that can be jittered (jittering temporarily disabled)
        self.nodes = self.true_nodes.copy()
        self.jitter_std = jitter_std

        # Latest state - just the user position now
        self.user_position: Optional[np.ndarray] = None  # User position
        self._position_lock = threading.Lock()  # Thread-safe access to user_position

        # Simulation settings
        self.simulation_speed = simulation_speed
        
        # Audio server (dummy mode - no actual MQTT connection)
        if mqtt_config and AdaptiveAudioServer:
            try:
                self.adaptive_audio_server = AdaptiveAudioServer(
                    broker=mqtt_config.broker,
                    port=mqtt_config.port
                )
            except Exception as e:
                logger.warning(json.dumps({
                    "event": "audio_server_init_failed",
                    "error": str(e)
                }))
                self.adaptive_audio_server = None
        else:
            self.adaptive_audio_server = None
        
        # Audio MQTT setup (dummy mode - create but don't connect)
        if mqtt_config:
            client_id = f"dummy_server_bring_up_pro_max_{uuid.uuid4()}"
            self.audio_client = mqtt.Client(client_id=client_id)
            self.audio_client.username_pw_set(username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD)
            self.audio_topic = "audio/commands"
            
            # State of speakers (dummy mode)
            self.current_pair: Optional[str] = None  # "front" or "back"
            self.started_for_pair: Optional[str] = None
            self.volumes = {0: 70, 1: 70, 2: 70, 3: 70}
            self._volumes_lock = threading.Lock()  # Thread-safe access to volumes
            self._last_position = None
            
            print("🎛️ Dummy Follow-Me Audio Server initialized (no MQTT connection)")
        else:
            self.audio_client = None
            self.audio_topic = None
            self.current_pair = None
            self.started_for_pair = None
            self.volumes = {}
            self._last_position = None

        # Simulation state
        self._simulation_thread: Optional[threading.Thread] = None
        self._simulation_stop_event = threading.Event()
        self._simulation_start_time = time.time()

        logger.info(json.dumps({
            "event": "dummy_server_initialized",
            "n_anchors": len(self.nodes),
            "window_size": window_size_seconds,
            "simulation_speed": simulation_speed,
            "phone_id": phone_node_id
        }))

    def _get_simulated_position(self, t: float) -> np.ndarray:
        """
        Generate a simulated user position that moves around the space.
        Returns position in cm as [x, y, z].
        """
        # Space dimensions: 480cm x 600cm (4.8m x 6m) - consistent with Basic_render_graph
        # Create a figure-8 pattern that covers the space
        scale_t = t * self.simulation_speed * 0.5  # Adjust speed

        # Figure-8 pattern parameters
        a = 180  # Width of figure-8 (cm) - adjusted for 480cm width
        b = 220  # Height of figure-8 (cm) - adjusted for 600cm height

        # Center the pattern in the space
        center_x = 240  # Center of 480cm width
        center_y = 300  # Center of 600cm height

        # Lissajous figure-8: x = A*sin(t), y = B*sin(2t)
        x = center_x + a * math.sin(scale_t)
        y = center_y + b * math.sin(2 * scale_t)

        # Add some height variation (user at ~170cm height, but we'll use 0 for simplicity)
        z = 0.0

        # Ensure we stay within bounds with some margin
        x = np.clip(x, 50, 430)  # 50cm margin from edges (480-50=430)
        y = np.clip(y, 50, 550)  # 50cm margin from edges (600-50=550)

        return np.array([x, y, z])

    # Removed _generate_measurement method - no longer generating fake UWB measurements

    def _simulation_loop(self):
        """Simple simulation loop that directly updates user position."""
        logger.info(json.dumps({"event": "simulation_started"}))

        position_update_interval = 0.05  # 20Hz position updates (same as real server polling)
        next_update_time = time.time()

        while not self._simulation_stop_event.is_set():
            current_time = time.time()
            sim_time = current_time - self._simulation_start_time

            # Update position at regular intervals
            if current_time >= next_update_time:
                # Get simulated user position (figure-8 pattern)
                user_pos = self._get_simulated_position(sim_time)

                # Directly set the user position (no PGO processing needed)
                with self._position_lock:
                    self.user_position = user_pos

                next_update_time = current_time + position_update_interval

                # Log position every few seconds
                if int(sim_time) % 2 == 0 and int(sim_time * 10) % 20 == 0:
                    logger.info(json.dumps({
                        "event": "simulated_position",
                        "position": user_pos.tolist(),
                        "time": sim_time
                    }))

            time.sleep(0.01)  # Small sleep to prevent tight loop

        logger.info(json.dumps({"event": "simulation_stopped"}))

    # Removed _get_or_create_filtered_binner - no longer using binners

    def start(self):
        """Start the dummy server and simulation."""
        # Start simulation thread (no processor thread needed anymore)
        self._simulation_thread = threading.Thread(
            target=self._simulation_loop,
            daemon=True
        )
        self._simulation_thread.start()

        logger.info(json.dumps({
            "event": "dummy_server_started"
        }))

    def stop(self):
        """Stop simulation."""
        self._simulation_stop_event.set()

        if self._simulation_thread:
            self._simulation_thread.join(timeout=1.0)

        # Audio server shutdown (if initialized)
        if self.adaptive_audio_server:
            self.adaptive_audio_server.pause_all()
            self.adaptive_audio_server.shutdown()

        # Audio MQTT cleanup (if initialized)
        if self.audio_client:
            self.audio_client.loop_stop()
            self.audio_client.disconnect()

        logger.info(json.dumps({
            "event": "dummy_server_stopped"
        }))

    def adaptive_audio_demo(self):
        """Start the adaptive audio demo in a background thread."""
        if self.adaptive_audio_server:
            with self._position_lock:
                position = self.user_position
            if position is not None:
                self.adaptive_audio_server.start_all()
                logger.info(json.dumps({
                    "event": "adaptive_audio_demo_started",
                    "dummy_mode": True
                }))
            else:
                logger.warning(json.dumps({
                    "event": "adaptive_audio_demo_failed",
                    "reason": "no_position_available"
                }))
        else:
            logger.info(json.dumps({
                "event": "adaptive_audio_demo_skipped",
                "reason": "no_mqtt_config"
            }))

    def stop_adaptive_audio_demo(self):
        """Stop the adaptive audio demo background thread."""
        if self.adaptive_audio_server:
            self.adaptive_audio_server.pause_all()
            logger.info(json.dumps({
                "event": "adaptive_audio_demo_stopped",
                "dummy_mode": True
            }))

    def _adaptive_audio_loop(self):
        """Background loop for adaptive audio demo (dummy implementation)."""
        # In dummy mode, this would simulate audio adjustments based on position
        pass
    
    def zone_dj_demo(self):
        """Start the zone DJ demo in a background thread."""
        if self.adaptive_audio_server:
            # Zone DJ functionality not available in AdaptiveAudioController
            # Simulate by starting all speakers at 70% volume
            try:
                self.adaptive_audio_server.start_all()
                logger.info(json.dumps({
                    "event": "zone_dj_demo_started",
                    "dummy_mode": True,
                    "note": "simulated_via_start_all"
                }))
            except AttributeError:
                logger.info(json.dumps({
                    "event": "zone_dj_demo_simulated",
                    "dummy_mode": True,
                    "reason": "method_not_available"
                }))
        else:
            logger.info(json.dumps({
                "event": "zone_dj_demo_skipped",
                "reason": "no_audio_server"
            }))

    def stop_zone_dj_demo(self):
        """Stop the zone DJ demo background thread."""
        if self.adaptive_audio_server:
            try:
                self.adaptive_audio_server.pause_all()
                logger.info(json.dumps({
                    "event": "zone_dj_demo_stopped",
                    "dummy_mode": True
                }))
            except AttributeError:
                logger.info(json.dumps({
                    "event": "zone_dj_demo_stop_simulated",
                    "dummy_mode": True,
                    "reason": "method_not_available"
                }))

    def set_playlist(self, playlist_number: int):
        """Set the current playlist by number (1-5)."""
        if self.adaptive_audio_server:
            self.adaptive_audio_server.set_playlist(playlist_number)
            logger.info(json.dumps({
                "event": "playlist_set",
                "playlist_number": playlist_number,
                "dummy_mode": True
            }))
        else:
            logger.info(json.dumps({
                "event": "playlist_set_skipped",
                "playlist_number": playlist_number,
                "reason": "no_mqtt_config"
            }))

    def _publish(self, topic: str, payload_obj: dict) -> None:
        """Dummy implementation of MQTT publish (logs instead of sending)."""
        if self.audio_client:
            payload = json.dumps(payload_obj, separators=(",", ":"))
            logger.info(json.dumps({
                "event": "dummy_mqtt_publish",
                "topic": topic,
                "payload": payload_obj
            }))
        
    def _apply_state(self, pair: str, left_vol: int, right_vol: int) -> None:
        """Dummy implementation of speaker state application."""
        logger.info(json.dumps({
            "event": "dummy_apply_state",
            "pair": pair,
            "left_volume": left_vol,
            "right_volume": right_vol
        }))
        
        if pair == "front":
            # Active: speakers 2 (LEFT), 3 (RIGHT). Inactive: 0,1
            if self.started_for_pair != pair:
                logger.info(json.dumps({
                    "event": "dummy_speaker_start",
                    "speakers": [0, 1, 2, 3],
                    "pair": pair
                }))
                self.started_for_pair = pair

            # Simulate setting active volumes
            if self.volumes:
                with self._volumes_lock:
                    self.volumes[2] = left_vol
                    self.volumes[3] = right_vol
                    self.volumes[0] = 0
                    self.volumes[1] = 0

        else:  # back
            # Active: speakers 1 (LEFT), 0 (RIGHT). Inactive: 2,3
            if self.started_for_pair != pair:
                logger.info(json.dumps({
                    "event": "dummy_speaker_start",
                    "speakers": [0, 1, 2, 3],
                    "pair": pair
                }))
                self.started_for_pair = pair

            if self.volumes:
                with self._volumes_lock:
                    self.volumes[1] = left_vol
                    self.volumes[0] = right_vol
                    self.volumes[2] = 0
                    self.volumes[3] = 0

        self.current_pair = pair

    def _send_audio_command(self, command: str, rpi_id: Optional[int] = None, volume: Optional[int] = None) -> None:
        """Dummy implementation of audio command sending."""
        now = time.time()
        execute_time = now + 0.5  # 500ms lookahead
        msg = {
            "command": command,
            "execute_time": execute_time,
            "global_time": now,
            "delay_ms": 500,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "rpi_id": rpi_id,
            "command_id": str(uuid.uuid4()),
        }
        if volume is not None:
            msg["target_volume"] = clamp(volume) if 'clamp' in globals() else max(0, min(100, volume))

        if rpi_id is None:
            topic = f"{self.audio_topic}/broadcast" if self.audio_topic else "audio/commands/broadcast"
        else:
            topic = f"{self.audio_topic}/rpi_{rpi_id}" if self.audio_topic else f"audio/commands/rpi_{rpi_id}"
        
        self._publish(topic, msg)

        # Track local volume state (for live monitoring)
        if command == "volume" and rpi_id is not None and volume is not None and self.volumes:
            with self._volumes_lock:
                self.volumes[rpi_id] = clamp(volume) if 'clamp' in globals() else max(0, min(100, volume))

    # Removed _handle_measurement and _process_measurements methods - no longer processing measurements or running PGO
    
    def get_speaker_volumes(self) -> Dict[int, int]:
        """
        Get current speaker volumes (thread-safe).
        
        Returns:
            Dict mapping speaker_id (0-3) to volume (0-100)
        """
        if not hasattr(self, 'volumes') or not self.volumes:
            return {}
        with self._volumes_lock:
            return self.volumes.copy()
    
    def get_speaker_positions(self) -> Dict[int, np.ndarray]:
        """
        Get speaker positions in world coordinates (meters).
        Speakers are located at anchor positions.
        
        Returns:
            Dict mapping speaker_id (0-3) to position [x_m, y_m, z_m]
        """
        positions = {}
        for speaker_id, pos_cm in self.true_nodes.items():
            # Convert from cm to meters
            positions[speaker_id] = pos_cm / 100.0
        return positions
    
    # ================================================================
    # PLAYBACK CONTROL METHODS (Dummy implementations)
    # ================================================================
    
    def play(self):
        """Start playback (dummy implementation)."""
        logger.info(json.dumps({
            "event": "dummy_play_requested",
            "dummy_mode": True
        }))
    
    def pause(self):
        """Pause playback (dummy implementation)."""
        logger.info(json.dumps({
            "event": "dummy_pause_requested",
            "dummy_mode": True
        }))
    
    def stop_playback(self):
        """Stop playback (dummy implementation)."""
        logger.info(json.dumps({
            "event": "dummy_stop_playback_requested",
            "dummy_mode": True
        }))
    
    def skip_track(self):
        """Skip to next track (dummy implementation)."""
        logger.info(json.dumps({
            "event": "dummy_skip_track_requested",
            "dummy_mode": True
        }))
    
    def previous_track(self):
        """Go to previous track (dummy implementation)."""
        logger.info(json.dumps({
            "event": "dummy_previous_track_requested",
            "dummy_mode": True
        }))
    
    def seek(self, position: float):
        """Seek to position in current track (dummy implementation)."""
        logger.info(json.dumps({
            "event": "dummy_seek_requested",
            "position": position,
            "dummy_mode": True
        }))
    
    # ================================================================
    # AUDIO STATE QUERY METHODS (Dummy implementations)
    # ================================================================
    
    def get_queue_preview(self, limit: int = 5) -> list:
        """Get preview of upcoming tracks (dummy implementation)."""
        return [f"Track {i+1}" for i in range(limit)]
    
    def get_current_track(self) -> str:
        """Get current track name (dummy implementation)."""
        return "Dummy Track"
    
    def is_playing(self) -> bool:
        """Check if currently playing (dummy implementation)."""
        return True  # Always "playing" in dummy mode
    
    def get_playback_progress(self) -> float:
        """Get playback progress 0.0-1.0 (dummy implementation)."""
        # Return a cycling progress based on simulation time
        sim_time = time.time() - self._simulation_start_time
        return (sim_time * self.simulation_speed) % 1.0
    
    def get_speaker_states(self) -> Dict[int, dict]:
        """Get speaker states (dummy implementation)."""
        states = {}
        volumes = self.get_speaker_volumes()
        for speaker_id, volume in volumes.items():
            states[speaker_id] = {
                "volume": volume,
                "playing": True,
                "connected": True
            }
        return states
    
    # ================================================================
    # VOLUME CONTROL METHODS (Dummy implementations)
    # ================================================================
    
    def set_global_volume(self, volume: int):
        """Set volume for all speakers (dummy implementation)."""
        if hasattr(self, 'volumes') and self.volumes:
            with self._volumes_lock:
                for speaker_id in self.volumes:
                    self.volumes[speaker_id] = max(0, min(100, volume))
        logger.info(json.dumps({
            "event": "dummy_global_volume_set",
            "volume": volume,
            "dummy_mode": True
        }))
    
    def set_volume(self, device_id: int, volume: int):
        """Set volume for specific speaker (dummy implementation)."""
        if hasattr(self, 'volumes') and self.volumes and device_id in self.volumes:
            with self._volumes_lock:
                self.volumes[device_id] = max(0, min(100, volume))
        logger.info(json.dumps({
            "event": "dummy_volume_set",
            "device_id": device_id,
            "volume": volume,
            "dummy_mode": True
        }))
    
    # ================================================================
    # AUDIO MODE CONTROL METHODS (Dummy implementations)
    # ================================================================
    
    def enable_adaptive_audio(self, enabled: bool):
        """Enable/disable adaptive audio mode (dummy implementation)."""
        logger.info(json.dumps({
            "event": "dummy_adaptive_audio_enabled",
            "enabled": enabled,
            "dummy_mode": True
        }))
    
    def enable_zone_dj(self, enabled: bool):
        """Enable/disable zone DJ mode (dummy implementation)."""
        logger.info(json.dumps({
            "event": "dummy_zone_dj_enabled",
            "enabled": enabled,
            "dummy_mode": True
        }))
    
    def bypass_audio_processing(self, bypass: bool):
        """Bypass audio processing (dummy implementation)."""
        logger.info(json.dumps({
            "event": "dummy_bypass_audio_processing",
            "bypass": bypass,
            "dummy_mode": True
        }))

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Dummy UWB Server')
    parser.add_argument('--speed', type=float, default=0.01,
                      help='Simulation speed multiplier (0.01 = very slow)')
    parser.add_argument('--phone-id', type=int, default=0,
                      help='Simulated phone node ID')
    args = parser.parse_args()

    logger.info(json.dumps({
        "event": "dummy_server_config",
        "speed": args.speed,
        "phone_id": args.phone_id
    }))

    # Start dummy server
    server = DummyServerBringUpProMax(
        simulation_speed=args.speed,
        phone_node_id=args.phone_id
    )

    try:
        server.start()

        # Keep main thread alive
        while True:
            if server.user_position is not None:
                print(f"Current position: {server.user_position}")
            time.sleep(1)

    except KeyboardInterrupt:
        server.stop()
