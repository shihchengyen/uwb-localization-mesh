"""
UWB Hardware Interface - Handles serial communication with UWB modules.
Preserves the exact serial decoding logic from the original implementation.
"""

import json
import logging
import math
import re
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Callable, Tuple

try:
    import serial
except ImportError:
    serial = None

from .config import MQTTConfig, UWBConfig

# Setup JSON logging
logging.basicConfig(
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
    level=logging.INFO
)
logger = logging.getLogger(__name__)




@dataclass
class RawUWBMeasurement:
    """Raw measurement data from UWB hardware."""
    anchor_id: int
    distance_m: float
    azimuth_deg: float
    elevation_deg: float
    timestamp_ns: int


@dataclass
class ProcessedUWBMeasurement:
    """Processed measurement with local coordinate transformation."""
    anchor_id: int
    timestamp_ns: int
    vector_local: Tuple[float, float, float]  # (x, y, z) in cm, local frame
    raw: RawUWBMeasurement


class UWBHardwareInterface:
    """
    Hardware interface for UWB modules.
    Handles serial communication and data parsing.
    Provides local coordinate vectors only - global transformation handled elsewhere.
    """

    def __init__(self, config: UWBConfig):
        """
        Initialize UWB hardware interface.

        Args:
            config: UWB configuration
        """
        self.config = config
        self.serial_conn = None
        self.running = False
        self.measurement_callback: Optional[Callable[[ProcessedUWBMeasurement], None]] = None

        # Regex patterns for parsing UART data (MUST preserve exact logic)
        self.re_dist = re.compile(r"TWR\[(\d+)\]\.distance\s*:\s*([-\d.]+)")
        self.re_azimu = re.compile(r"TWR\[(\d+)\]\.aoa_azimuth\s*:\s*([-\d.]+)")
        self.re_elev = re.compile(r"TWR\[(\d+)\]\.aoa_elevation\s*:\s*([-\d.]+)")

        # Pending measurements buffer (anchor_id -> partial measurement data)
        self.pending_measurements: Dict[int, Dict[str, float]] = {}

    def set_measurement_callback(self, callback: Callable[[ProcessedUWBMeasurement], None]):
        """Set callback for processed measurements."""
        self.measurement_callback = callback

    def start(self) -> bool:
        """Start the UWB hardware interface."""
        try:
            if serial is None:
                raise ImportError("pyserial not available")

            self.serial_conn = serial.Serial(
                self.config.serial_port,
                self.config.baud_rate
            )
            self.running = True

            # Start reading thread
            self.read_thread = threading.Thread(target=self._read_serial_loop, daemon=True)
            self.read_thread.start()

            logger.info(json.dumps({
                "event": "uwb_interface_started",
                "serial_port": self.config.serial_port,
                "baud_rate": self.config.baud_rate,
                "anchor_id": self.config.anchor_id
            }))

            return True

        except Exception as e:
            logger.error(json.dumps({
                "event": "uwb_interface_start_failed",
                "error": str(e),
                "serial_port": self.config.serial_port
            }))
            return False

    def stop(self):
        """Stop the UWB hardware interface."""
        self.running = False
        if self.serial_conn:
            self.serial_conn.close()

        logger.info(json.dumps({
            "event": "uwb_interface_stopped"
        }))

    def _read_serial_loop(self):
        """Main serial reading loop."""
        while self.running:
            try:
                if not self.serial_conn or not self.serial_conn.is_open:
                    time.sleep(0.1)
                    continue

                # Read line from serial
                line = self.serial_conn.readline().decode(errors="ignore").strip()

                # Process the line
                self._process_serial_line(line)

            except Exception as e:
                logger.error(json.dumps({
                    "event": "serial_read_error",
                    "error": str(e)
                }))
                time.sleep(0.1)

    def _process_serial_line(self, line: str):
        """Process a single line from serial (preserving exact original logic)."""
        # Parse distance
        m = self.re_dist.search(line)
        if m:
            aid, val = int(m.group(1)), float(m.group(2))
            st = self.pending_measurements.setdefault(aid, {})
            st["r"] = val

        # Parse azimuth
        m = self.re_azimu.search(line)
        if m:
            aid, val = int(m.group(1)), float(m.group(2))
            st = self.pending_measurements.setdefault(aid, {})
            st["az"] = val

        # Parse elevation
        m = self.re_elev.search(line)
        if m:
            aid, val = int(m.group(1)), float(m.group(2))
            st = self.pending_measurements.setdefault(aid, {})
            st["el"] = val

        # Process complete measurements
        to_clear = []
        for aid, st in self.pending_measurements.items():
            if all(k in st for k in ("r", "az", "el")):
                self._process_complete_measurement(aid, st)
                to_clear.append(aid)

        for aid in to_clear:
            self.pending_measurements.pop(aid, None)

    def _process_complete_measurement(self, anchor_id: int, measurement_data: Dict[str, float]):
        """Process a complete measurement to local coordinates only."""
        r, az, el = measurement_data["r"], measurement_data["az"], measurement_data["el"]

        # Convert spherical to Cartesian (local frame only)
        v_local = self._r_local_from_az_el(r, az, el)

        # Use the configured anchor_id instead of the parsed one from serial data (like TWR[0] makes the topic uwb/anchor/0/vector even for rpi1)
        configured_anchor_id = self.config.anchor_id

        # Create measurement objects
        raw_measurement = RawUWBMeasurement(
            anchor_id=configured_anchor_id,
            distance_m=r,
            azimuth_deg=az,
            elevation_deg=el,
            timestamp_ns=time.time_ns()
        )

        processed_measurement = ProcessedUWBMeasurement(
            anchor_id=configured_anchor_id,
            timestamp_ns=time.time_ns(),
            vector_local=v_local,
            raw=raw_measurement
        )

        # Emit via callback if set
        if self.measurement_callback:
            self.measurement_callback(processed_measurement)

    # ===== COORDINATE TRANSFORMATION FUNCTIONS (PRESERVE EXACT LOGIC) =====

    @staticmethod
    def _deg2rad(d: float) -> float:
        """Convert degrees to radians."""
        return d * math.pi / 180.0

    def _r_local_from_az_el(self, dist_m: float, az_deg: float, el_deg: float) -> Tuple[float, float, float]:
        """
        Convert spherical coordinates to Cartesian (preserving exact original logic).

        Convention:
          +az = right, -az = left; 0 = forward (board normal)
          +el = down,  -el = up;   0 = horizontal
          local axes: x=forward, y=left, z=up
          
        Note: Despite parameter name, dist_m is already in cm from sensor!
        """
        th = self._deg2rad(az_deg)
        ph = self._deg2rad(el_deg)
        cph, sph = math.cos(ph), math.sin(ph)
        cth, sth = math.cos(th), math.sin(th)

        x = dist_m * cph * cth
        y = -dist_m * cph * sth   # minus because +az is to the RIGHT
        z = -dist_m * sph         # minus because +el is DOWN

        return (x, y, z)  # Already in cm - no conversion needed!
