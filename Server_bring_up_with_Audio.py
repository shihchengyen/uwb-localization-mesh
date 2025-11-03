"""
Server Bring-Up with Audio Control:

calls MQTT, binning, PGO, and adaptive audio control prom their packages

Architecture:
- ServerBringUp: Processes UWB measurements, bins data, runs PGO to track user position
- FollowMeAudioServer: Controls RPi speakers based on user position
  - Inherits position tracking from ServerBringUp
  - Sends MQTT commands to RPi audio clients
- FollowMeAudioClient: Runs on each RPi, receives commands and plays audio

Audio Control:
- Automatic: Based on user position
  - Y >= 300: Back speakers (RPi 1,0)
  - Y < 300: Front speakers (RPi 2,3)
  - X-axis panning around X=240: Volume varies left/right
- Manual: Keyboard shortcuts
  - 's': Start all speakers
  - 'p': Pause all speakers
  - 'i': Show status (current pair, volumes, active/inactive)
  - 'q': Quit gracefully
  - Ctrl+C: Emergency stop

Usage:
    uv run Server_bring_up_with_Audio.py --broker 192.168.68.70 --port 1884

Components:
- UWB MQTT Server: Receives UWB measurements from anchors
- PGO Solver: Calculates user position
- Follow-Me Audio Server: Adapts audio based on position
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
from packages.audio_mqtt_server.follow_me_audio_server import FollowMeAudioServer

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
    5. Adaptive audio control based on user position
    
    Audio Control:
    - Automatically adjusts speakers as user moves (see docstring at top of file)
    - Manual control via keyboard: 's'=start all, 'p'=pause all, 'i'=status, 'q'=quit
    - FollowMeAudioServer handles MQTT commands to RPi clients
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

        # Initialize Follow-Me Audio Server
        # Controls RPi speakers based on user position (see update_position call in _process_measurements)
        self.follow_me_audio_server = FollowMeAudioServer(
            broker=mqtt_config.broker,
            port=mqtt_config.port
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
        
    def stop(self):
        """Stop all processing."""
        self._stop_event.set()
        self.uwb_mqtt_server.stop()
        self.follow_me_audio_server.shutdown()
        
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
                                # Update user position from anchored results
                                self.user_position = pgo_result.node_positions[f'phone_{phone_id}']
                                
                                # Notify follow-me audio server of position update
                                self.follow_me_audio_server.update_position(self.user_position)
                                
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
    server = ServerBringUp(
        mqtt_config=mqtt_config,
        jitter_std=0.0  # Jittering disabled
    )
    
    try:
        server.start()
        
        #########################################################
        # Keyboard control for audio server
        print("\nKeyboard: 's' START ALL, 'p' PAUSE ALL, 'i' STATUS, 'q' QUIT")
        shutdown_event = threading.Event()
        
        def keyboard_loop():
            while not shutdown_event.is_set():
                try:
                    cmd = input().strip().lower()
                    if cmd == "q":
                        shutdown_event.set()
                        break
                    elif cmd == "s":
                        server.follow_me_audio_server.start_all()
                    elif cmd == "p":
                        server.follow_me_audio_server.pause_all()
                    elif cmd == "i":
                        # Show audio status
                        status = server.follow_me_audio_server.get_status()
                        print(f"\n📊 Audio Status:")
                        print(f"   Pair: {status['current_pair']}")
                        print(f"   Active speakers: {status['active_speakers']}")
                        print(f"   Inactive speakers: {status['inactive_speakers']}")
                        print(f"   Volumes: R0={status['volumes'][0]}%  R1={status['volumes'][1]}%  R2={status['volumes'][2]}%  R3={status['volumes'][3]}%")
                except (EOFError, KeyboardInterrupt):
                    shutdown_event.set()
                    break
        
        threading.Thread(target=keyboard_loop, daemon=True).start()
        #########################################################

        # Keep main thread alive
        while not shutdown_event.is_set():
            if server.user_position is not None:
                print(f"Current position: {server.user_position}")
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.stop()