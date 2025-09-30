"""
Sliding window binning for UWB measurements.
"""

import time
from collections import deque
from typing import List, Dict, Optional
from dataclasses import dataclass

import numpy as np
from datatypes.datatypes import Measurement, BinnedData

@dataclass
class BinningMetrics:
    """Metrics for binning performance and data quality."""
    late_drops: int          # Number of measurements dropped for being too old
    total_measurements: int  # Total measurements processed
    measurements_per_anchor: Dict[int, int]  # Count per anchor
    window_span_sec: float  # Actual time span of the window

class SlidingWindowBinner:
    """
    Maintains a sliding window of measurements and creates bins.
    Handles late data and tracks metrics.
    """
    
    def __init__(self, window_size_seconds: float = 1.0):
        """
        Initialize the binner.
        
        Args:
            window_size_seconds: Size of sliding window in seconds
        """
        self.window_size_seconds = window_size_seconds
        self.measurements_buffer = deque()  # Sliding window of raw measurements
        self.bin_counter = 0  # For generating unique phone node IDs
        self.metrics = BinningMetrics(
            late_drops=0,
            total_measurements=0,
            measurements_per_anchor={},
            window_span_sec=0.0
        )
        
    def add_measurement(self, measurement: Measurement) -> None:
        """
        Add a new measurement to the buffer.
        Drops measurements that are too old.
        
        Args:
            measurement: New measurement to add
        """
        current_time = time.time()
        window_start = current_time - self.window_size_seconds
        
        # Check if measurement is too old
        if measurement.timestamp < window_start:
            self.metrics.late_drops += 1
            return
            
        # Add to buffer
        self.measurements_buffer.append(measurement)
        self.metrics.total_measurements += 1
        
        # Update per-anchor counts
        self.metrics.measurements_per_anchor[measurement.anchor_id] = \
            self.metrics.measurements_per_anchor.get(measurement.anchor_id, 0) + 1
            
        # Remove old measurements
        while self.measurements_buffer and \
              self.measurements_buffer[0].timestamp < window_start:
            self.measurements_buffer.popleft()
            
    def create_binned_data(self, phone_node_id: int) -> Optional[BinnedData]:
        """
        Create binned data from current measurements in the sliding window.
        
        Args:
            phone_node_id: ID of the phone node
            
        Returns:
            BinnedData if there are measurements, None otherwise
        """
        if not self.measurements_buffer:
            return None
            
        # Get time range
        current_time = time.time()
        window_start = current_time - self.window_size_seconds
        
        # Group by anchor
        anchor_measurements: Dict[int, List[np.ndarray]] = {}
        
        for measurement in self.measurements_buffer:
            if measurement.phone_node_id == phone_node_id:
                if measurement.anchor_id not in anchor_measurements:
                    anchor_measurements[measurement.anchor_id] = []
                anchor_measurements[measurement.anchor_id].append(
                    measurement.local_vector
                )
                
        if not anchor_measurements:
            return None
            
        # Update metrics
        self.metrics.window_span_sec = current_time - window_start
        
        return BinnedData(
            bin_start_time=window_start,
            bin_end_time=current_time,
            phone_node_id=phone_node_id,
            measurements=anchor_measurements
        )
        
    def get_metrics(self) -> BinningMetrics:
        """Get current binning metrics."""
        return self.metrics