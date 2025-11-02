"""
Dummy Server Bring-up for testing and demos without physical hardware.
Simulates user movement and generates fake UWB measurements.
"""

import json
import logging
import threading
import time
import math
from collections import defaultdict
from queue import Queue
from typing import Dict, Optional, Union

import numpy as np

from packages.datatypes.datatypes import Measurement, BinnedData, AnchorConfig
from packages.localization_algos.binning.sliding_window import SlidingWindowBinner, BinningMetrics
from packages.localization_algos.edge_creation.transforms import create_relative_measurement
from packages.localization_algos.edge_creation.anchor_edges import create_anchor_anchor_edges
from packages.localization_algos.pgo.solver import PGOSolver
from packages.uwb_mqtt_server.config import MQTTConfig

# Setup JSON logging
logging.basicConfig(
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class DummyServerBringUp:
    """
    Dummy server that simulates user movement and generates fake measurements.
    Uses the same processing pipeline as the real ServerBringUp.
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

        logger.info(json.dumps({
            "event": "dummy_server_stopped"
        }))

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
    server = DummyServerBringUp(
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
