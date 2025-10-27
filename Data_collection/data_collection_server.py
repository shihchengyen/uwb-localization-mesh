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
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, FloatPrompt, IntPrompt
from rich.table import Table
from rich.text import Text

from packages.datatypes.datatypes import Measurement, BinnedData
from packages.localization_algos.binning.sliding_window import SlidingWindowBinner
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

        # Initialize rich console for better UI
        self.console = Console()

        # Initialize base server
        super().__init__(mqtt_config, window_size_seconds)

        # Initialize raw binners for complete data logging/analysis
        self._raw_binners: Dict[int, SlidingWindowBinner] = {}

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

    def _get_or_create_raw_binner(self, phone_id: int) -> SlidingWindowBinner:
        """Thread-safe access to per-phone raw binners (for logging/analysis)."""
        with self._binners_lock:
            if phone_id not in self._raw_binners:
                # Raw binner uses same window size but no filtering parameters
                self._raw_binners[phone_id] = SlidingWindowBinner(
                    window_size_seconds=self.window_size_seconds,
                    outlier_threshold_sigma=float('inf'),  # Disable filtering
                    max_anchor_variance=float('inf')       # Disable variance check
                )
            return self._raw_binners[phone_id]

    # Default behaviour in server_bringup doesn't instatiate the raw data collection hence handling is done here
    def _handle_measurement(self, measurement: Measurement):
        """
        Override base class to handle both filtered and raw data collection.
        Filtered data goes to PGO, raw data goes to logging/analysis.
        """
        # Always add to raw binner for complete data logging
        raw_binner = self._get_or_create_raw_binner(measurement.phone_node_id)
        raw_binner.add_measurement_raw(measurement)

        # Call parent implementation for filtered binner processing
        super()._handle_measurement(measurement)
    
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

        # Get both filtered and raw binned data
        filtered_binned = latest_binned

        # Get phone_id from the binned data
        phone_id = latest_binned.phone_node_id

        # Get raw binned data from the raw binner
        raw_binned = None
        if phone_id in self._raw_binners:
            raw_binner = self._raw_binners[phone_id]
            raw_binned = raw_binner.create_binned_data(phone_id)

        with open(self.datapoints_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                ground_truth[0], ground_truth[1], ground_truth[2],
                pgo_measurement[0], pgo_measurement[1], pgo_measurement[2],
                orientation,
                json.dumps(self._binned_data_to_json_dict(filtered_binned)) if filtered_binned else "{}",
                json.dumps(self._binned_data_to_json_dict(raw_binned)) if raw_binned else "{}"
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
        # Check if stdin is available (interactive mode)
        import sys
        if sys.stdin.isatty():
            # Interactive mode - use rich menu interface
            self._interactive_menu_mode()
        else:
            # Non-interactive mode - just keep running
            self._background_mode()
    
    def _interactive_menu_mode(self):
        """Interactive menu-driven command processing."""
        self.console.clear()

        # Welcome message
        welcome_panel = Panel.fit(
            "[bold blue]Data Collection Server[/bold blue]\n"
            "[green]Ready for data collection![/green]\n"
            "[dim]Use arrow keys or number keys to select options[/dim]",
            title="Welcome"
        )
        self.console.print(welcome_panel)
        self.console.print()

        while not self._stop_event.is_set():
            try:
                # Show menu
                choice = self._show_menu()

                if choice == "1":
                    self._handle_collect_datapoint()
                elif choice == "2":
                    self._handle_collect_variance()
                elif choice == "3":
                    self._handle_show_logs()
                elif choice == "4":
                    self._handle_quit()
                    break
                elif choice == "clear":
                    self.console.clear()
                else:
                    self.console.print("[red]Invalid choice. Please try again.[/red]")

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted. Use menu to quit properly.[/yellow]")
            except EOFError:
                self.console.print("\n[yellow]Switching to background mode...[/yellow]")
                self._background_mode()
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
    
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
    
    def _show_menu(self):
        """Display the main menu and get user choice."""
        # Show current status
        if self.user_position is not None:
            status = f"[green]Position: ({self.user_position[0]:.1f}, {self.user_position[1]:.1f}, {self.user_position[2]:.1f})[/green]"
        else:
            status = "[yellow]Position: Not available yet[/yellow]"

        status_panel = Panel.fit(status, title="Current Status")
        self.console.print(status_panel)

        # Show menu options
        table = Table(title="Available Actions")
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Action", style="magenta")
        table.add_column("Description", style="white")

        table.add_row("1", "Collect Datapoint", "Capture current position with ground truth coordinates")
        table.add_row("2", "Collect Variance", "Measure position variance over time window")
        table.add_row("3", "Show Logs", "Display recent error/warning logs")
        table.add_row("4", "Quit", "Stop the data collection server")
        table.add_row("c", "Clear Screen", "Clear the terminal screen")

        self.console.print(table)
        self.console.print()

        # Get choice
        choice = Prompt.ask(
            "[bold cyan]Select an action[/bold cyan]",
            choices=["1", "2", "3", "4", "c", "clear"],
            default="1"
        ).lower()

        return choice

    def _handle_collect_datapoint(self):
        """Handle datapoint collection with rich prompts."""
        self.console.print("\n[bold]Collect Datapoint[/bold]")

        try:
            # Get ground truth coordinates
            x = FloatPrompt.ask("Ground truth X coordinate (cm)")
            y = FloatPrompt.ask("Ground truth Y coordinate (cm)")
            z = FloatPrompt.ask("Ground truth Z coordinate (cm)")

            # Get orientation
            orientation = Prompt.ask(
                "Device orientation",
                choices=["A", "B", "C", "a", "b", "c"],
                default="A"
            ).upper()

            ground_truth = np.array([x, y, z])

            # Collect the datapoint
            with self.console.status("[bold green]Collecting datapoint...[/bold green]"):
                pos, data = self.collect_datapoint(ground_truth, orientation)

            # Show results
            result_table = Table(title="Datapoint Collected Successfully")
            result_table.add_column("Field", style="cyan")
            result_table.add_column("Ground Truth", style="yellow")
            result_table.add_column("PGO Position", style="green")

            result_table.add_row("X", f"{x:.2f}", f"{pos[0]:.2f}")
            result_table.add_row("Y", f"{y:.2f}", f"{pos[1]:.2f}")
            result_table.add_row("Z", f"{z:.2f}", f"{pos[2]:.2f}")
            result_table.add_row("Orientation", orientation, orientation)

            self.console.print(result_table)

        except Exception as e:
            self.console.print(f"[red]Error collecting datapoint: {e}[/red]")

    def _handle_collect_variance(self):
        """Handle variance collection with rich prompts."""
        self.console.print("\n[bold]Collect Variance[/bold]")

        try:
            # Get ground truth coordinates
            x = FloatPrompt.ask("Ground truth X coordinate (cm)")
            y = FloatPrompt.ask("Ground truth Y coordinate (cm)")
            z = FloatPrompt.ask("Ground truth Z coordinate (cm)")

            # Get orientation
            orientation = Prompt.ask(
                "Device orientation",
                choices=["A", "B", "C", "a", "b", "c"],
                default="A"
            ).upper()

            # Get window size
            window = FloatPrompt.ask("Time window (seconds)", default=10.0)

            ground_truth = np.array([x, y, z])

            # Collect variance
            with self.console.status(f"[bold green]Collecting variance over {window} seconds...[/bold green]"):
                pos, stats = self.collect_variance(ground_truth, orientation, window)

            # Show results
            self.console.print("\n[bold green]Variance collection complete![/bold green]")

            result_table = Table(title="Results")
            result_table.add_column("Field", style="cyan")
            result_table.add_column("Value", style="white")

            result_table.add_row("Ground Truth", f"({x:.2f}, {y:.2f}, {z:.2f})")
            result_table.add_row("Final Position", f"({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})")
            result_table.add_row("Orientation", orientation)

            self.console.print(result_table)

            # Show statistics
            stats_table = Table(title="Variance Statistics")
            stats_table.add_column("Statistic", style="cyan")
            stats_table.add_column("Value", style="yellow")

            for key, value in stats.items():
                stats_table.add_row(key.replace('_', ' ').title(), f"{value:.6f}")

            self.console.print(stats_table)

        except Exception as e:
            self.console.print(f"[red]Error collecting variance: {e}[/red]")

    def _handle_show_logs(self):
        """Handle showing recent logs."""
        self.console.print("\n[bold]Recent Logs[/bold]")
        records = self._console_handler.get_records()
        if records:
            for record in records[-10:]:  # Show last 10 records
                self.console.print(record)
        else:
            self.console.print("[dim]No recent logs available[/dim]")

    def _handle_quit(self):
        """Handle quit command."""
        if Prompt.ask("\n[bold red]Are you sure you want to quit?[/bold red]", choices=["y", "n"], default="n") == "y":
            self.console.print("[yellow]Stopping server...[/yellow]")
            self.stop()
        else:
            self.console.print("[green]Cancelled.[/green]")

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