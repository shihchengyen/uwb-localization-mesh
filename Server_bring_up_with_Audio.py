"""
Server bring-up script that coordinates MQTT, binning, and PGO, audio control.
Maintains global state and orchestrates the full processing pipeline.
"""

import json
import logging
import threading
import time
import datetime
from datetime import timezone
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
from packages.uwb_mqtt_server.server import UWBMQTTServer
from packages.uwb_mqtt_server.config import MQTTConfig
from packages.audio_mqtt_server.follow_me_audio_server import AdaptiveAudioServer, clamp

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



class ServerBringUpProMax:
    """
    Central server that coordinates:
    1. MQTT measurement ingestion
    2. Binning and edge creation
    3. PGO solving
    4. State management
    """
    
    def __init__(
        self,
        mqtt_config: MQTTConfig,
        window_size_seconds: float = 1.0,
        jitter_std: float = 0.0  # Standard deviation for anchor position jitter (cm)
    ):
        """Initialize the server with configuration."""
        
        # Ground truth anchor positions (cm)
        # Anchors are mounted at 239 cm (2.39m) height
        self.true_nodes = {
            0: np.array([480, 600, 0]),  # top-right
            1: np.array([0, 600, 0]),    # top-left
            2: np.array([480, 0, 0]),    # bottom-right
            3: np.array([0, 0, 0])       # bottom-left (origin in XY, but at sensor height in Z)
        }

        # self.region_boundaries = {
        #     "front": np.array([0, 300, 0]),
        #     "back": np.array([0, -300, 0]),
        #     "left": np.array([-300, 0, 0]),
        #     "right": np.array([300, 0, 0]),
        # }        
        
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
        
        # Audio server
        self.adaptive_audio_server = AdaptiveAudioServer()
        

        """Initialize audio server with MQTT connection."""
        
        # Audio MQTT setup
        client_id = f"server_bring_up_pro_max_{uuid.uuid4()}"
        self.audio_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self.audio_client.username_pw_set(username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD)

        self.audio_topic = "audio/commands"

        # Start MQTT server
        self.uwb_mqtt_server = UWBMQTTServer(
            config=mqtt_config,
            on_measurement=self._handle_measurement
        )

        # State of speakers
        self.current_pair: Optional[str] = None  # "front" or "back"
        self.started_for_pair: Optional[str] = None
        self.volumes = {0: 70, 1: 70, 2: 70, 3: 70}
        self._last_position = None

        # Connect MQTT for audio
        self.audio_client.connect(mqtt_config.broker, mqtt_config.port, mqtt_config.keepalive)
        self.audio_client.loop_start()
        
        print("🎛️ Follow-Me Audio Server initialized")

        # Processing thread control
        self._stop_event = threading.Event()
        self._processor_thread = threading.Thread(
            target=self._process_measurements,
            daemon=True
        )
        
        logger.info(json.dumps({
            "event": "server_initialized",
            "n_anchors": len(self.nodes),
            "window_size": window_size_seconds
        }))
        
    def _get_or_create_filtered_binner(self, phone_id: int) -> SlidingWindowBinner:
        """Thread-safe access to per-phone filtered binners (for PGO processing)."""
        with self._binners_lock:
            if phone_id not in self._filtered_binners:
                self._filtered_binners[phone_id] = SlidingWindowBinner(
                    window_size_seconds=self.window_size_seconds
                )
            return self._filtered_binners[phone_id]
        
    def _publish(self, topic: str, payload_obj: dict) -> None:
        payload = json.dumps(payload_obj, separators=(",", ":"))
        self.audio_client.publish(topic, payload, qos=1)
                
    def start(self):
        """Start the server and processing thread."""
        # Start MQTT
        self.uwb_mqtt_server.start()

        # Start processor
        self._processor_thread.start()

        logger.info(json.dumps({
            "event": "server_started"
        }))
    
    def adaptive_audio_demo(self):
        """Start the adaptive audio demo in a background thread."""
        with self._position_lock:
            position = self.user_position
        if position is not None:
            self.adaptive_audio_server.start_all()


    def stop_adaptive_audio_demo(self):
        """Stop the adaptive audio demo background thread."""
        self.adaptive_audio_server.pause_all()

    def _adaptive_audio_loop(self):
        """Background loop for adaptive audio demo."""
    
    def zone_dj_demo(self):
        """Start the zone DJ demo in a background thread."""
        # play 70% at all speakers
        self.adaptive_audio_server.zone_dj_start()

    def stop_zone_dj_demo(self):
        """Stop the zone DJ demo background thread."""
        self.adaptive_audio_server.zone_dj_pause()


    def set_playlist(self, playlist_number: int):
        """Set the current playlist by number (1-5)."""
        self.adaptive_audio_server.set_playlist(playlist_number)
        logger.info(json.dumps({
            "event": "playlist_set",
            "playlist_number": playlist_number
        }))
        
    def stop(self):
        """Stop all processing."""
        self._stop_event.set()
        self.uwb_mqtt_server.stop()

        # Audio server shutdown
        self.adaptive_audio_server.pause_all()
        self.adaptive_audio_server.shutdown()
        self.adaptive_audio_server.shutdown()

        logger.info(json.dumps({
            "event": "server_stopped"
        }))
        
    def _handle_measurement(self, measurement: Measurement):
        """
        Callback from MQTT server for new measurements.
        Adds to filtered binner for PGO processing.
        Only filtered measurements are queued for PGO processing.
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

        # Log individual rejections for debugging (can be disabled later)
        if not was_added_filtered and filtered_metrics.rejected_measurements <= 50:  # Log first 50 rejections
            logger.debug(json.dumps({
                "event": "measurement_rejected",
                "phone_id": measurement.phone_node_id,
                "anchor_id": measurement.anchor_id,
                "rejection_count": filtered_metrics.rejected_measurements,
                "distance": float(np.linalg.norm(measurement.local_vector))
            }))
            
    def _process_measurements(self):
        """
        Main processing loop that runs in a separate thread.
        Uses binned data to create edges and run PGO.
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
                        
                        # # Apply per-solve jitter to anchor positions (commented out)
                        # if self.jitter_std > 0:
                        #     # Temporarily jitter nodes for this solve
                        #     temp_nodes = self.true_nodes.copy()
                        #     for anchor_id in temp_nodes:
                        #         jitter = np.random.normal(0, self.jitter_std, size=3)
                        #         temp_nodes[anchor_id] = self.true_nodes[anchor_id] + jitter
                        #     
                        #     # Create temporary anchor config and edges with jittered positions
                        #     temp_anchor_config = AnchorConfig(positions=temp_nodes)
                        #     temp_anchor_edges = create_anchor_anchor_edges(temp_anchor_config)
                        # else:
                        #     # Use non-jittered edges
                        #     temp_anchor_edges = self._anchor_edges

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


    def _apply_state(self, pair: str, left_vol: int, right_vol: int) -> None:
        """Send MQTT commands to apply the given pair and volumes."""
        """Calls _send_audio_command for each speaker."""
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

    def _send_audio_command(self, command: str, rpi_id: Optional[int] = None, volume: Optional[int] = None) -> None:
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
            msg["target_volume"] = clamp(volume)

        if rpi_id is None:
            topic = f"{self.audio_topic}/broadcast"
        else:
            topic = f"{self.audio_topic}/rpi_{rpi_id}"
        self._publish(topic, msg)

        # Track local volume state (for live monitoring)
        if command == "volume" and rpi_id is not None and volume is not None:
            self.volumes[rpi_id] = clamp(volume)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='UWB Server')
    parser.add_argument('--broker', type=str, default='localhost',
                      help='MQTT broker IP address')
    parser.add_argument('--port', type=int, default=1884,
                      help='MQTT broker port')
    args = parser.parse_args()
    
    # Configure MQTT with command line arguments
    mqtt_config = MQTTConfig(
        broker=args.broker,
        port=args.port
    )
    
    logger.info(json.dumps({
        "event": "server_config",
        "broker": args.broker,
        "port": args.port
    }))
    
    # Start server (jitter temporarily disabled)
    server = ServerBringUpProMax(
        mqtt_config=mqtt_config,
        jitter_std=0.0  # Jittering disabled
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