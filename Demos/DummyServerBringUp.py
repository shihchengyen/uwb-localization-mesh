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
from collections import defaultdict
from queue import Queue
from typing import Dict, Optional, Union

import numpy as np
import uuid
import paho.mqtt.client as mqtt

from packages.datatypes.datatypes import Measurement, BinnedData, AnchorConfig
from packages.localization_algos.binning.sliding_window import SlidingWindowBinner, BinningMetrics
from packages.localization_algos.edge_creation.transforms import create_relative_measurement
from packages.localization_algos.edge_creation.anchor_edges import create_anchor_anchor_edges
from packages.localization_algos.pgo.solver import PGOSolver
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
        simulation_speed: float = 1.0,  # Speed multiplier for simulation
        phone_node_id: int = 0  # Simulated phone ID
    ):
        """Initialize the dummy server with configuration."""

        # Ground truth anchor positions (cm)
        # Anchors are mounted at 239 cm (2.39m) height
        self.true_nodes = {
            0: np.array([480, 600, 0]),  # top-right
            1: np.array([0, 600, 0]),    # top-left
            2: np.array([480, 0, 0]),    # bottom-right
            3: np.array([0, 0, 0])       # bottom-left (origin in XY, but at sensor height in Z)
        }

        # Working copy of nodes that can be jittered (jittering temporarily disabled)
        self.nodes = self.true_nodes.copy()
        self.jitter_std = jitter_std

        # Create anchor config for edge creation (using true positions for now)
        self.anchor_config = AnchorConfig(positions=self.nodes)

        # Latest state
        self.data: Dict[int, BinnedData] = {}  # phone_node_id -> latest binned data
        self.user_position: Optional[np.ndarray] = None  # User position
        self._position_lock = threading.Lock()  # Thread-safe access to user_position

        # Processing settings
        self.window_size_seconds = window_size_seconds
        self.simulation_speed = simulation_speed
        self.phone_node_id = phone_node_id

        # Thread-safe measurement storage
        self._measurements_lock = threading.Lock()
        self._measurements: Dict[int, Queue[Measurement]] = defaultdict(Queue)

        # Binning system (one per phone) - filtered binners for PGO processing
        self._binners_lock = threading.Lock()
        self._filtered_binners: Dict[int, SlidingWindowBinner] = {}

        # PGO solver
        self._pgo_solver = PGOSolver()

        # Pre-compute anchor-anchor edges
        self._anchor_edges = create_anchor_anchor_edges(self.anchor_config)
        
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

        # Processing thread control
        self._stop_event = threading.Event()
        self._processor_thread = threading.Thread(
            target=self._process_measurements,
            daemon=True
        )

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
        # Space dimensions: 480cm x 600cm (4.8m x 6m)
        # Create a figure-8 pattern that covers the space
        scale_t = t * self.simulation_speed * 0.5  # Adjust speed

        # Figure-8 pattern parameters
        a = 200  # Width of figure-8 (cm)
        b = 150  # Height of figure-8 (cm)

        # Center the pattern in the space
        center_x = 240  # Center of 480cm width
        center_y = 300  # Center of 600cm height

        # Lissajous figure-8: x = A*sin(t), y = B*sin(2t)
        x = center_x + a * math.sin(scale_t)
        y = center_y + b * math.sin(2 * scale_t)

        # Add some height variation (user at ~170cm height, but we'll use 0 for simplicity)
        z = 0.0

        # Ensure we stay within bounds with some margin
        x = np.clip(x, 50, 430)  # 50cm margin from edges
        y = np.clip(y, 50, 550)  # 50cm margin from edges

        return np.array([x, y, z])

    def _generate_measurement(self, anchor_id: int, user_pos: np.ndarray, timestamp: float) -> Measurement:
        """
        Generate a fake UWB measurement from user position to anchor.
        """
        anchor_pos = self.true_nodes[anchor_id]

        # Calculate true distance vector
        true_vector = user_pos - anchor_pos

        # Add some realistic noise (UWB distance error ~1-5cm)
        noise_std = 2.0  # cm
        noise = np.random.normal(0, noise_std, size=3)
        measured_vector = true_vector + noise

        # Create measurement
        measurement = Measurement(
            timestamp=timestamp,
            anchor_id=anchor_id,
            phone_node_id=self.phone_node_id,
            local_vector=measured_vector
        )

        return measurement

    def _simulation_loop(self):
        """Main simulation loop that generates fake measurements."""
        logger.info(json.dumps({"event": "simulation_started"}))

        measurement_interval = 0.1  # 10Hz measurement rate (same as real anchors)
        next_measurement_time = time.time()

        while not self._simulation_stop_event.is_set():
            current_time = time.time()
            sim_time = current_time - self._simulation_start_time

            # Generate measurements at regular intervals
            if current_time >= next_measurement_time:
                # Get simulated user position
                user_pos = self._get_simulated_position(sim_time)

                # Generate measurement from each anchor
                for anchor_id in self.true_nodes.keys():
                    measurement = self._generate_measurement(anchor_id, user_pos, current_time)

                    # Process the measurement (same as real server)
                    self._handle_measurement(measurement)

                next_measurement_time = current_time + measurement_interval

                # Log position every few seconds
                if int(sim_time) % 2 == 0 and int(sim_time * 10) % 20 == 0:
                    logger.info(json.dumps({
                        "event": "simulated_position",
                        "position": user_pos.tolist(),
                        "time": sim_time
                    }))

            time.sleep(0.01)  # Small sleep to prevent tight loop

        logger.info(json.dumps({"event": "simulation_stopped"}))

    def _get_or_create_filtered_binner(self, phone_id: int) -> SlidingWindowBinner:
        """Thread-safe access to per-phone filtered binners (for PGO processing)."""
        with self._binners_lock:
            if phone_id not in self._filtered_binners:
                self._filtered_binners[phone_id] = SlidingWindowBinner(
                    window_size_seconds=self.window_size_seconds
                )
            return self._filtered_binners[phone_id]

    def start(self):
        """Start the dummy server and simulation."""
        # Start processor thread
        self._processor_thread.start()

        # Start simulation thread
        self._simulation_thread = threading.Thread(
            target=self._simulation_loop,
            daemon=True
        )
        self._simulation_thread.start()

        logger.info(json.dumps({
            "event": "dummy_server_started"
        }))

    def stop(self):
        """Stop all processing and simulation."""
        self._simulation_stop_event.set()
        self._stop_event.set()

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

    def _handle_measurement(self, measurement: Measurement):
        """
        Process a measurement (same as real server).
        Adds to filtered binner for PGO processing.
        """
        # Add to filtered binner for PGO processing
        filtered_binner = self._get_or_create_filtered_binner(measurement.phone_node_id)
        was_added_filtered = filtered_binner.add_measurement(measurement)

        # Only queue for processing if it was accepted
        if was_added_filtered:
            with self._measurements_lock:
                self._measurements[measurement.phone_node_id].put(measurement)

        # Log metrics periodically from filtered binner
        filtered_metrics = filtered_binner.get_metrics()
        total_processed = (filtered_metrics.total_measurements +
                          filtered_metrics.rejected_measurements +
                          filtered_metrics.late_drops)

        if total_processed % 100 == 0:  # Every 100 measurements processed
            logger.info(json.dumps({
                "event": "binning_metrics",
                "phone_id": measurement.phone_node_id,
                "metrics": {
                    "accepted": filtered_metrics.total_measurements,
                    "rejected": filtered_metrics.rejected_measurements,
                    "late_drops": filtered_metrics.late_drops,
                    "rejection_rate": f"{100 * filtered_metrics.rejected_measurements / total_processed:.1f}%",
                    "rejection_reasons": filtered_metrics.rejection_reasons,
                    "per_anchor": filtered_metrics.measurements_per_anchor,
                    "window_span": filtered_metrics.window_span_sec
                }
            }))

    def _process_measurements(self):
        """
        Main processing loop that runs in a separate thread.
        Uses binned data to create edges and run PGO (same as real server).
        """
        while not self._stop_event.is_set():
            try:
                # Process each phone's data
                with self._measurements_lock:
                    phone_ids = list(self._measurements.keys())

                for phone_id in phone_ids:
                    # Get filtered binned data for PGO processing
                    filtered_binner = self._get_or_create_filtered_binner(phone_id)
                    binned = filtered_binner.create_binned_data(phone_id)

                    if binned:
                        # Update state
                        self.data[phone_id] = binned

                        # Create phone-anchor edges
                        phone_edges = []
                        for anchor_id, vectors in binned.measurements.items():
                            if vectors:  # Only if we have measurements
                                avg_vector = np.mean(vectors, axis=0)
                                edge = create_relative_measurement(
                                    anchor_id,
                                    phone_id,
                                    avg_vector
                                )
                                phone_edges.append(edge)

                        # Prepare PGO inputs
                        nodes: Dict[str, Optional[np.ndarray]] = {
                            # Start with floating anchors
                            'anchor_0': None,
                            'anchor_1': None,
                            'anchor_2': None,
                            'anchor_3': None,
                            f'phone_{phone_id}': None  # Phone to optimize
                        }

                        # Combine all edges (using non-jittered edges for now)
                        edges = phone_edges + self._anchor_edges

                        # Run PGO with anchoring
                        try:
                            pgo_result = self._pgo_solver.solve(
                                nodes=nodes,
                                edges=edges,
                                anchor_positions=self.true_nodes  # Anchor to TRUE positions
                            )

                            if pgo_result.success:
                                # Update user position from anchored results (thread-safe)
                                with self._position_lock:
                                    self.user_position = pgo_result.node_positions[f'phone_{phone_id}']

                                logger.info(json.dumps({
                                    "event": "position_updated",
                                    "phone_id": phone_id,
                                    "position": self.user_position.tolist(),
                                    "error": pgo_result.error,
                                    "metrics": {
                                        "n_edges": len(edges),
                                        "n_phone_edges": len(phone_edges),
                                        "n_anchor_edges": len(self._anchor_edges)
                                    }
                                }))

                        except Exception as e:
                            logger.error(json.dumps({
                                "event": "pgo_failed",
                                "error": str(e)
                            }))

            except Exception as e:
                logger.error(json.dumps({
                    "event": "processing_error",
                    "error": str(e)
                }))

            # Sleep briefly to prevent tight loop
            time.sleep(0.01)
    
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

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Dummy UWB Server')
    parser.add_argument('--speed', type=float, default=1.0,
                      help='Simulation speed multiplier')
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
