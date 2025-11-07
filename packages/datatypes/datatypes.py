"""
Core datatypes for UWB localization system.
All dataclasses are frozen to ensure immutability.
"""

from dataclasses import dataclass
from typing import Dict, List, Mapping
import numpy as np

@dataclass(frozen=True)
class Measurement:
    """Single UWB measurement from one anchor at one timestamp."""
    timestamp: float          # NTP epoch seconds (UTC)
    anchor_id: int           # Anchor identifier
    phone_node_id: int       # Phone node identifier
    local_vector: np.ndarray # [x, y, z] in cm, local frame

@dataclass(frozen=True)
class BinnedData:
    """
    A realized 1-second (default) sliding-window bin.
    Contains all anchor-phone measurements for one phone node within [bin_start, bin_end).
    """
    bin_start_time: float    # NTP epoch seconds (UTC)
    bin_end_time: float      # NTP epoch seconds (UTC)
    phone_node_id: int       # Phone node identifier
    measurements: Mapping[int, List[np.ndarray]]  # anchor_id -> list of vectors

@dataclass(frozen=True)
class AnchorConfig:
    """Ground truth anchor positions with optional jittering."""
    positions: Dict[int, np.ndarray]  # anchor_id -> [x, y, z] position in cm

    def get_position(self, anchor_id: int) -> np.ndarray:
        """Get the position of a specific anchor."""
        if anchor_id not in self.positions:
            raise ValueError(f"Anchor {anchor_id} not found in config")
        return self.positions[anchor_id]

    def get_all_positions(self) -> Dict[int, np.ndarray]:
        """Get all anchor positions."""
        return dict(self.positions)  # Return a copy to prevent modification