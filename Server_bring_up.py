"""
Server bring-up script that coordinates MQTT, binning, and PGO.
Maintains global state and orchestrates the full processing pipeline.
"""

import json
import logging
import threading
import time
from collections import defaultdict
from queue import Queue
from typing import Dict, Optional

import numpy as np

from packages.datatypes.datatypes import Measurement, BinnedData, AnchorConfig
from packages.localization_algos.binning.sliding_window import SlidingWindowBinner, BinningMetrics
from packages.localization_algos.edge_creation.transforms import create_relative_measurement
from packages.localization_algos.edge_creation.anchor_edges import create_anchor_anchor_edges
from packages.localization_algos.pgo.solver import PGOSolver
from packages.uwb_mqtt_server.server import UWBMQTTServer
from packages.uwb_mqtt_server.config import MQTTConfig

# Setup JSON logging
logging.basicConfig(
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class ServerBringUp:
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
        self.true_nodes = {
            0: np.array([440, 550, 0]),  # top-right
            1: np.array([0, 550, 0]),    # top-left
            2: np.array([440, 0, 0]),    # bottom-right
            3: np.array([0, 0, 0])       # bottom-left (origin)
        }
        
        # Working copy of nodes that can be jittered (jittering temporarily disabled)
        self.nodes = self.true_nodes.copy()
        self.jitter_std = jitter_std
        
        # if jitter_std > 0:
        #     self._apply_jitter()
        
        # Create anchor config for edge creation (using true positions for now)
        self.anchor_config = AnchorConfig(positions=self.nodes)
        
        # Latest state
        self.data: Dict[int, BinnedData] = {}  # phone_node_id -> latest binned data
        self.user_position: Optional[np.ndarray] = None  # User position
        
        # Processing settings
        self.window_size_seconds = window_size_seconds
        
        # Thread-safe measurement storage
        self._measurements_lock = threading.Lock()
        self._measurements: Dict[int, Queue[Measurement]] = defaultdict(Queue)
        
        # Binning system (one per phone)
        self._binners_lock = threading.Lock()
        self._binners: Dict[int, SlidingWindowBinner] = {}
        
        # PGO solver
        self._pgo_solver = PGOSolver()
        
        # Pre-compute anchor-anchor edges
        self._anchor_edges = create_anchor_anchor_edges(self.anchor_config)
        
        # Start MQTT server
        self.uwb_mqtt_server = UWBMQTTServer(
            config=mqtt_config,
            on_measurement=self._handle_measurement
        )
        
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
        
    def _get_or_create_binner(self, phone_id: int) -> SlidingWindowBinner:
        """Thread-safe access to per-phone binners."""
        with self._binners_lock:
            if phone_id not in self._binners:
                self._binners[phone_id] = SlidingWindowBinner(
                    window_size_seconds=self.window_size_seconds
                )
            return self._binners[phone_id]
        
    def start(self):
        """Start the server and processing thread."""
        # Start MQTT
        self.uwb_mqtt_server.start()
        
        # Start processor
        self._processor_thread.start()
        
        logger.info(json.dumps({
            "event": "server_started"
        }))
        
    def stop(self):
        """Stop all processing."""
        self._stop_event.set()
        self.uwb_mqtt_server.stop()
        
        logger.info(json.dumps({
            "event": "server_stopped"
        }))
        
    def _handle_measurement(self, measurement: Measurement):
        """
        Callback from MQTT server for new measurements.
        Adds to both queue and binner.
        """
        # Add to binner
        binner = self._get_or_create_binner(measurement.phone_node_id)
        binner.add_measurement(measurement)
        
        # Also queue for processing
        with self._measurements_lock:
            self._measurements[measurement.phone_node_id].put(measurement)
            
        # Log metrics periodically
        metrics = binner.get_metrics()
        if metrics.total_measurements % 100 == 0:  # Every 100 measurements
            logger.info(json.dumps({
                "event": "binning_metrics",
                "phone_id": measurement.phone_node_id,
                "metrics": {
                    "late_drops": metrics.late_drops,
                    "total": metrics.total_measurements,
                    "per_anchor": metrics.measurements_per_anchor,
                    "window_span": metrics.window_span_sec
                }
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
                    # Get binned data
                    binner = self._get_or_create_binner(phone_id)
                    binned = binner.create_binned_data(phone_id)
                    
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

                        nodes = {
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
                                # Update user position from anchored results
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
    # Example usage
    mqtt_config = MQTTConfig(
        broker="localhost",
        port=1883
    )
    
    # Start server (jitter temporarily disabled)
    server = ServerBringUp(
        mqtt_config=mqtt_config,
        jitter_std=0.0  # Jittering disabled
    )
    
    try:
        server.start()
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        server.stop()