"""
Server bring-up script that coordinates MQTT, binning, and PGO, audio control.
Maintains global state and orchestrates the full processing pipeline.
"""

import json
import logging
import threading
import time
from collections import defaultdict
from queue import Queue
from typing import Dict, Optional, Union

import numpy as np

from packages.datatypes.datatypes import Measurement, BinnedData, AnchorConfig
from packages.localization_algos.binning.sliding_window import SlidingWindowBinner, BinningMetrics
from packages.localization_algos.edge_creation.transforms import create_relative_measurement
from packages.localization_algos.edge_creation.anchor_edges import create_anchor_anchor_edges
from packages.localization_algos.pgo.solver import PGOSolver
from packages.uwb_mqtt_server.server import UWBMQTTServer
from packages.uwb_mqtt_server.config import MQTTConfig
from packages.audio_mqtt_server.adaptive_audio_controller import AdaptiveAudioController

# Setup JSON logging
logging.basicConfig(
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class DemoServerBringUp:
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
        
        # Start MQTT server
        self.uwb_mqtt_server = UWBMQTTServer(
            config=mqtt_config,
            on_measurement=self._handle_measurement
        )

        # Start audio server
        self.audio_server = AdaptiveAudioController(
            broker=mqtt_config.broker,
            port=mqtt_config.port
        )


        # Processing thread control
        self._stop_event = threading.Event()
        self._processor_thread = threading.Thread(
            target=self._process_measurements,
            daemon=True
        )

        # Zone DJ thread control
        self._zone_dj_stop_event = threading.Event()
        self._zone_dj_thread = None
        
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


    def stop_adaptive_audio_demo(self):
        """Stop the adaptive audio demo background thread."""

    def _adaptive_audio_loop(self):
        """Background loop for adaptive audio demo."""

    
    def start_zone_dj_demo(self):
        """Start the zone DJ demo in a background thread."""
        if self._zone_dj_thread is not None and self._zone_dj_thread.is_alive():
            print("Zone DJ demo already running")
            return

        self._zone_dj_stop_event.clear()
        self._zone_dj_thread = threading.Thread(target=self._zone_dj_loop, daemon=True)
        self._zone_dj_thread.start()
        print("🎵 Zone DJ demo started in background thread")

        logger.info(json.dumps({
            "event": "zone_dj_started"
        }))

    def stop_zone_dj_demo(self):
        """Stop the zone DJ demo background thread."""
        if self._zone_dj_thread is not None:
            self._zone_dj_stop_event.set()
            self._zone_dj_thread.join(timeout=2.0)
            print("🎵 Zone DJ demo stopped")

        logger.info(json.dumps({
            "event": "zone_dj_stopped"
        }))

    def _zone_dj_loop(self):
        """
        Background loop for zone DJ functionality.
        Continuously checks user position and updates audio.
        """
        while not self._zone_dj_stop_event.is_set():
            try:
                # Get current position (thread-safe)
                user_position = None
                with self._position_lock:
                    if self.user_position is not None:
                        user_position = self.user_position.copy()

                if user_position is not None:
                    # Update audio based on position
                    self.audio_server.update_playlist_for_position(user_position)

                # Small delay to prevent tight loop
                time.sleep(0.1)

            except Exception as e:
                print(f"Error in zone DJ loop: {e}")
                time.sleep(1)  # Longer delay on error
        
    def stop(self):
        """Stop all processing."""
        self._stop_event.set()
        self.uwb_mqtt_server.stop()

        # Stop zone DJ demo if running
        self.stop_zone_dj_demo()

        # Audio server shutdown
        self.audio_server.pause_all()
        self.audio_server.shutdown()

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
    server = DemoServerBringUp(
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