"""
Data collection server that extends ServerBringUp with data collection capabilities.
"""

import csv
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from packages.datatypes.datatypes import BinnedData
from packages.uwb_mqtt_server.config import MQTTConfig
from Server_bring_up import ServerBringUp

# Custom handler that only keeps last N records
class LastNHandler(logging.Handler):
    def __init__(self, n=5):
        super().__init__()
        self.n = n
        self.records = []
        
    def emit(self, record):
        try:
            self.records.append(self.format(record))
            if len(self.records) > self.n:
                self.records.pop(0)
        except Exception:
            self.handleError(record)
            
    def get_records(self):
        return self.records

class DataCollectionServer(ServerBringUp):
    """
    Extends ServerBringUp to add:
    1. Interactive command processing
    2. Data point collection
    3. Variance analysis
    4. CSV/JSON data storage
    """
    
    def __init__(
        self,
        mqtt_config: MQTTConfig,
        data_dir: str = "Data",
        window_size_seconds: float = 1.0,
    ):
        """Initialize the data collection server."""
        # Setup minimal console logging
        self._setup_logging()
        
        # Initialize base server
        super().__init__(mqtt_config, window_size_seconds)
        
        # Setup data storage
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.datapoints_file = self.data_dir / "datapoints.csv"
        self.variance_file = self.data_dir / "variance.csv"
        
        self._init_csv_files()
        
        # Add command processing thread
        self._command_thread = threading.Thread(
            target=self._process_commands,
            daemon=True
        )
    
    @staticmethod
    def _binned_data_to_json_dict(binned_data: BinnedData) -> dict:
        """Convert BinnedData to a JSON-serializable dictionary."""
        return {
            'bin_start_time': binned_data.bin_start_time,
            'bin_end_time': binned_data.bin_end_time,
            'phone_node_id': binned_data.phone_node_id,
            'measurements': {
                anchor_id: [vec.tolist() for vec in vectors]
                for anchor_id, vectors in binned_data.measurements.items()
            }
        }
        
    def _setup_logging(self):
        """Setup custom logging configuration."""
        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # File handler for full logs
        file_handler = logging.FileHandler(
            log_dir / f"data_collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter('{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}')
        )
        
        # Console handler for last N records
        console_handler = LastNHandler(n=5)
        console_handler.setLevel(logging.WARNING)  # Only show warnings and errors
        console_handler.setFormatter(
            logging.Formatter('%(levelname)s: %(message)s')
        )
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Remove any existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # Add our handlers
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Store console handler for later use
        self._console_handler = console_handler

    def _show_recent_logs(self):
        """Display the most recent log messages."""
        records = self._console_handler.get_records()
        if records:
            print("\nRecent logs:")
            for record in records:
                print(record)

    def _init_csv_files(self):
        """Initialize CSV files with headers if they don't exist."""
        # Datapoints CSV headers
        if not self.datapoints_file.exists():
            with open(self.datapoints_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'ground_truth_x', 'ground_truth_y', 'ground_truth_z',
                    'pgo_x', 'pgo_y', 'pgo_z',
                    'orientation',
                    'binned_data_json'
                ])
        
        # Variance CSV headers
        if not self.variance_file.exists():
            with open(self.variance_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'ground_truth_x', 'ground_truth_y', 'ground_truth_z',
                    'pgo_x', 'pgo_y', 'pgo_z',
                    'orientation',
                    'variance_x', 'variance_y', 'variance_z',
                    'covariance_xy', 'covariance_xz', 'covariance_yz'
                ])

    def collect_datapoint(
        self,
        ground_truth: np.ndarray,
        orientation: str,
    ) -> Tuple[np.ndarray, BinnedData]:
        """
        Capture a labeled datapoint using the most recent PGO solution.
        
        Args:
            ground_truth: (x, y, z) in cm, global frame
            orientation: Device orientation label (A, B, C...)
            
        Returns:
            (pgo_measurement, binned_data) tuple
        """
        # Get current position and binned data
        if self.user_position is None:
            raise RuntimeError("No PGO solution available yet")
            
        # Get latest binned data for the first phone
        if not self.data:
            raise RuntimeError("No binned data available yet")
        latest_binned = next(iter(self.data.values()))
        
        # Create measurement array
        pgo_measurement = self.user_position.copy()
        
        # Save to CSV
        timestamp = datetime.utcnow().timestamp()
        with open(self.datapoints_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                ground_truth[0], ground_truth[1], ground_truth[2],
                pgo_measurement[0], pgo_measurement[1], pgo_measurement[2],
                orientation,
                json.dumps(self._binned_data_to_json_dict(latest_binned))
            ])
            
        return pgo_measurement, latest_binned

    def collect_variance(
        self,
        ground_truth: np.ndarray,
        orientation: str,
        window_seconds: float = 10.0
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Collect variance statistics over a time window.
        
        Args:
            ground_truth: (x, y, z) in cm, global frame
            orientation: Device orientation label
            window_seconds: Time window to collect variance over
            
        Returns:
            (current_position, variance_stats) tuple
        """
        # Collect positions over window
        positions: List[np.ndarray] = []
        start_time = datetime.utcnow().timestamp()
        
        while (datetime.utcnow().timestamp() - start_time) < window_seconds:
            if self.user_position is not None:
                positions.append(self.user_position.copy())
            import time
            time.sleep(0.1)  # Sample at 10Hz
            
        if not positions:
            raise RuntimeError("No positions collected in window")
            
        # Calculate statistics
        positions_array = np.array(positions)
        current_pos = positions_array[-1]  # Latest position
        
        # Calculate variances
        variances = np.var(positions_array, axis=0)
        
        # Calculate covariances
        covariances = np.cov(positions_array.T)
        
        # Create stats dict
        stats = {
            'variance_x': float(variances[0]),
            'variance_y': float(variances[1]),
            'variance_z': float(variances[2]),
            'covariance_xy': float(covariances[0,1]),
            'covariance_xz': float(covariances[0,2]),
            'covariance_yz': float(covariances[1,2])
        }
        
        # Save to CSV
        timestamp = datetime.utcnow().timestamp()
        with open(self.variance_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                ground_truth[0], ground_truth[1], ground_truth[2],
                current_pos[0], current_pos[1], current_pos[2],
                orientation,
                stats['variance_x'], stats['variance_y'], stats['variance_z'],
                stats['covariance_xy'], stats['covariance_xz'], stats['covariance_yz']
            ])
            
        return current_pos, stats

    def _process_commands(self):
        """Interactive command processing loop."""
        print("\nData Collection Server Ready!")
        print("Available commands:")
        print("  collect_datapoint <x> <y> <z> <orientation>")
        print("  variance <x> <y> <z> <orientation> [window_seconds=10]")
        print("  logs - Show recent logs")
        print("  quit")
        
        # Check if stdin is available (interactive mode)
        import sys
        if sys.stdin.isatty():
            # Interactive mode - can use input()
            self._interactive_mode()
        else:
            # Non-interactive mode - just keep running
            self._background_mode()
    
    def _interactive_mode(self):
        """Interactive command processing."""
        while not self._stop_event.is_set():
            try:
                cmd = input("\nEnter command: ").strip()
                
                if cmd == "quit":
                    self.stop()
                    break
                    
                if cmd == "logs":
                    self._show_recent_logs()
                    continue
                    
                parts = cmd.split()
                if not parts:
                    continue
                    
                self._execute_command(parts)
                    
            except EOFError:
                print("\nSwitching to background mode...")
                self._background_mode()
                break
            except Exception as e:
                print(f"Error processing command: {e}")
    
    def _background_mode(self):
        """Background mode - just keep running and log status."""
        import time
        while not self._stop_event.is_set():
            try:
                time.sleep(5)  # Check every 5 seconds
                if self.user_position is not None:
                    print(f"\r[STATUS] Position: ({self.user_position[0]:.1f}, {self.user_position[1]:.1f}, {self.user_position[2]:.1f}) - Ready for data collection", end="", flush=True)
            except Exception as e:
                print(f"\nError in background mode: {e}")
    
    def _execute_command(self, parts):
        """Execute a command given its parts."""
        if parts[0] == "collect_datapoint":
            if len(parts) != 5:
                print("Usage: collect_datapoint <x> <y> <z> <orientation>")
                return
                
            try:
                x, y, z = map(float, parts[1:4])
                ground_truth = np.array([x, y, z])
                orientation = parts[4]
                
                pos, data = self.collect_datapoint(
                    ground_truth,
                    orientation
                )
                print(f"\nDatapoint collected!")
                print(f"Ground truth: ({x}, {y}, {z})")
                print(f"PGO position: ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})")
                
            except Exception as e:
                print(f"Error collecting datapoint: {e}")
                
        elif parts[0] == "variance":
            if len(parts) not in (5, 6):
                print("Usage: variance <x> <y> <z> <orientation> [window_seconds=10]")
                return
                
            try:
                x, y, z = map(float, parts[1:4])
                ground_truth = np.array([x, y, z])
                orientation = parts[4]
                window = float(parts[5]) if len(parts) == 6 else 10.0
                
                print(f"\nCollecting variance over {window} seconds...")
                pos, stats = self.collect_variance(
                    ground_truth,
                    orientation,
                    window
                )
                
                print("\nVariance collection complete!")
                print(f"Ground truth: ({x}, {y}, {z})")
                print(f"Final position: ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})")
                print("\nStatistics:")
                for k, v in stats.items():
                    print(f"  {k}: {v:.6f}")
                    
            except Exception as e:
                print(f"Error collecting variance: {e}")
                
        else:
            print("Unknown command")

    def start(self):
        """Start the server and processing threads."""
        # Start base server
        super().start()
        
        # Start command processing
        self._command_thread.start()

if __name__ == "__main__":
    # Example usage
    mqtt_config = MQTTConfig(
        broker="localhost",
        port=1884
    )
    
    server = DataCollectionServer(
        mqtt_config=mqtt_config,
        data_dir="Data"  # Will create if doesn't exist
    )
    
    try:
        server.start()
        
        # Main thread will process commands until quit
        server._command_thread.join()
        
    except KeyboardInterrupt:
        server.stop()