"""
Sliding window binning for UWB measurements.
"""

import time
from collections import deque
from typing import List, Dict, Optional
from dataclasses import dataclass

import numpy as np
from packages.datatypes.datatypes import Measurement, BinnedData

@dataclass
class BinningMetrics:
    """Metrics for binning performance and data quality."""
    late_drops: int          # Number of measurements dropped for being too old
    rejected_measurements: int  # Number of measurements rejected by filters
    total_measurements: int  # Total measurements successfully added
    measurements_per_anchor: Dict[int, int]  # Count per anchor
    rejection_reasons: Dict[str, int]  # Count per rejection reason
    window_span_sec: float  # Actual time span of the window

class SlidingWindowBinner:
    """
    Maintains a sliding window of measurements and creates bins.
    Handles late data and tracks metrics.
    """
    
    def __init__(
        self,
        window_size_seconds: float = 2.0,
        outlier_threshold_sigma: float = 2.0,
        min_samples_for_outlier_detection: int = 5,
        max_anchor_variance: float = 10000.0  # cm^2 per anchor
    ):
        """
        Initialize the binner.

        Args:
            window_size_seconds: Size of sliding window in seconds
            outlier_threshold_sigma: Number of std deviations for outlier rejection
            min_samples_for_outlier_detection: Minimum samples needed before applying outlier filter
            max_anchor_variance: Maximum allowed variance per anchor (cm^2). Measurements that would exceed this are rejected.
        """
        self.window_size_seconds = window_size_seconds
        self.outlier_threshold_sigma = outlier_threshold_sigma
        self.min_samples_for_outlier_detection = min_samples_for_outlier_detection
        self.max_anchor_variance = max_anchor_variance
        
        self.measurements_buffer = deque()  # Sliding window of raw measurements
        self.bin_counter = 0  # For generating unique phone node IDs
        self.metrics = BinningMetrics(
            late_drops=0,
            rejected_measurements=0,
            total_measurements=0,
            measurements_per_anchor={},
            rejection_reasons={},
            window_span_sec=0.0
        )
        
    def add_measurement(self, measurement: Measurement) -> bool:
        """
        Add a new measurement to the buffer after validation.
        Drops measurements that are too old or fail validation filters.
        
        Args:
            measurement: New measurement to add
            
        Returns:
            True if measurement was added, False if rejected
        """
        current_time = time.time()
        window_start = current_time - self.window_size_seconds
        
        # Check if measurement is too old
        if measurement.timestamp < window_start:
            self.metrics.late_drops += 1
            return False
        
        # Validate measurement using filters
        is_valid, rejection_reason = self._validate_measurement(measurement)
        if not is_valid:
            self.metrics.rejected_measurements += 1
            self.metrics.rejection_reasons[rejection_reason] = \
                self.metrics.rejection_reasons.get(rejection_reason, 0) + 1
            return False
            
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
            
        return True
            
    def create_binned_data(self, phone_node_id: int) -> Optional[BinnedData]:
        """
        Create binned data from current measurements in the sliding window.
        Rejects bins with variance exceeding max_bin_variance.
        
        Args:
            phone_node_id: ID of the phone node
            
        Returns:
            BinnedData if there are measurements and variance is acceptable, None otherwise
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
    
    def _validate_measurement(self, measurement: Measurement) -> tuple[bool, str]:
        """
        Validate a measurement using statistical outlier detection and variance checks.

        Args:
            measurement: The measurement to validate

        Returns:
            (is_valid, rejection_reason): Tuple indicating if valid and why if not
        """
        # Statistical outlier detection (cluster-based)
        is_outlier, reason = self._check_statistical_outlier(measurement)
        if is_outlier:
            return False, reason

        # Per-anchor variance check
        would_exceed_variance, variance_reason = self._check_anchor_variance(measurement)
        if would_exceed_variance:
            return False, variance_reason

        return True, ""
    
    def _check_statistical_outlier(self, measurement: Measurement) -> tuple[bool, str]:
        """
        Check if measurement is a statistical outlier compared to recent measurements
        from the same anchor using clustering/distance-based approach.
        
        This implements a simple form of online outlier detection by comparing
        the new measurement to the "cluster" of recent measurements from the same anchor.
        
        Args:
            measurement: The measurement to check
            
        Returns:
            (is_outlier, reason): Tuple indicating if outlier and descriptive reason
        """
        # Get recent measurements from the same anchor and phone
        recent_same_anchor = [
            m for m in self.measurements_buffer
            if m.anchor_id == measurement.anchor_id 
            and m.phone_node_id == measurement.phone_node_id
        ]
        
        # Need minimum samples to establish a cluster
        if len(recent_same_anchor) < self.min_samples_for_outlier_detection:
            return False, ""  # Not enough data, accept measurement
        
        # Calculate distances of recent measurements
        recent_distances = np.array([
            np.linalg.norm(m.local_vector) for m in recent_same_anchor
        ])
        
        # Calculate distance of new measurement
        new_distance = np.linalg.norm(measurement.local_vector)
        
        # Statistical outlier detection using z-score on distances
        mean_distance = np.mean(recent_distances)
        std_distance = np.std(recent_distances)
        
        # Avoid division by zero
        if std_distance < 1e-6:  # Very small std (measurements very consistent)
            # Check if new measurement is very different from the tight cluster
            if abs(new_distance - mean_distance) > 50.0:  # 50cm threshold
                return True, f"outlier_from_tight_cluster_diff_{int(abs(new_distance - mean_distance))}cm"
            return False, ""
        
        # Calculate z-score
        z_score = abs(new_distance - mean_distance) / std_distance
        
        if z_score > self.outlier_threshold_sigma:
            return True, f"statistical_outlier_z{z_score:.1f}_anchor{measurement.anchor_id}"

        return False, ""

    def _check_anchor_variance(self, measurement: Measurement) -> tuple[bool, str]:
        """
        Check if adding this measurement would cause the anchor's variance to exceed the threshold.

        Args:
            measurement: The measurement to check

        Returns:
            (would_exceed, reason): Tuple indicating if variance would be exceeded and why
        """
        # Get recent measurements from the same anchor and phone
        recent_same_anchor = [
            m for m in self.measurements_buffer
            if m.anchor_id == measurement.anchor_id
            and m.phone_node_id == measurement.phone_node_id
        ]

        # Need at least 2 measurements to calculate variance
        if len(recent_same_anchor) < 2:
            return False, ""  # Not enough data to check variance

        # Calculate distances including the new measurement
        distances = np.array([np.linalg.norm(m.local_vector) for m in recent_same_anchor])
        new_distance = np.linalg.norm(measurement.local_vector)

        # Calculate variance with the new measurement added
        all_distances = np.append(distances, new_distance)
        variance = np.var(all_distances)

        if variance > self.max_anchor_variance:
            return True, f"anchor_variance_too_high_{int(variance)}_anchor{measurement.anchor_id}"

        return False, ""