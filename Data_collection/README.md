# Main data collection functions

```python 
def collect_datapoint(
    ground_truth: np.ndarray,  # [x, y, z] in cm
    orientation: str,
) -> Tuple[np.ndarray, BinnedData]:
    """
    Capture a labeled datapoint using the most recent PGO solution and the
    current sliding-window bin.

    Inputs
    ------
    ground_truth: [x, y, z] array in cm, global frame.
    orientation:  Device/rig orientation label, eg. A, B, C ...

    Returns
    -------
    (
      pgo_measurement,   # [x, y, z] array in cm from latest PGO at call time
      binned_data        # realized bin used to produce edges for that PGO tick
    )

    Timing
    ------
    - Uses NTP-corrected wall clock for all timestamps.
    - The returned BinnedData's [bin_start_time, bin_end_time] reflect the
      window used to generate the edges consumed by the latest PGO solve.
    """


def collect_variance(
    ground_truth: np.ndarray,  # [x, y, z] in cm
    orientation: str,
    window_seconds: float = 10.0
) -> Tuple[np.ndarray, Dict[str, float]]:
    """
    Assess short-horizon jitter and filter diagnostics over the latest ~10 PGO
    updates (≈10 s) plus runtime effects.

    Inputs
    ------
    ground_truth: [x, y, z] array in cm, global frame.
    orientation:  Device/rig orientation label, eg. A, B, C ...
    window_seconds: Time window to collect variance over (default: 10s)

    Returns
    -------
    (
      pgo_measurement,   # [x, y, z] array in cm from latest PGO at call time
      filter_output      # variance/covariance and filter stats dictionary:
                        # {
                        #   'variance_x': float,
                        #   'variance_y': float,
                        #   'variance_z': float,
                        #   'covariance_xy': float,
                        #   'covariance_xz': float,
                        #   'covariance_yz': float
                        # }
    )

    Notes
    -----
    - The function black-boxes the specific filter (e.g., Kalman) and windowing.
    - Field names in filter_output are stable so CSV schemas remain consistent.
    """

```

The output of these will be appended with the time and simply added to a CSV.

## Dual-Binner Data Collection

The `DataCollectionServer` extends the base `ServerBringUp` with dual-binner functionality:

- **Filtered Binner**: Quality-controlled data for PGO positioning (inherited from base)
- **Raw Binner**: Complete unfiltered data for logging and analysis

### CSV Export Format

Data points are exported to CSV with both filtered and raw binned data:

```csv
timestamp,ground_truth_x,ground_truth_y,ground_truth_z,pgo_x,pgo_y,pgo_z,orientation,filtered_binned_data_json,raw_binned_data_json
1761086998.505,0.0,0.0,150.0,60.9,25.4,-51.5,A,"{...filtered data...}","{...raw data...}"
```

### Binner Usage

**Filtered Data (for PGO):**
- Contains only measurements that passed quality filters
- Used for position optimization
- May have fewer measurements per anchor if some were filtered out

**Raw Data (for Analysis):**
- Contains ALL measurements received
- Used for debugging and research
- Includes rejected measurements for comparison studies


## Refresher on the BinnedData dataclass
```python
@dataclass(frozen=True)
class Measurement:
    """Single UWB measurement from one anchor at one timestamp."""
    timestamp: float               # NTP epoch seconds (UTC)
    anchor_id: int                # 0-3 typically
    phone_node_id: int            # Phone node identifier
    local_vector: np.ndarray      # [x, y, z] in cm

@dataclass(frozen=True)
class BinnedData:
    """
    A realized 1-second (default) sliding-window bin.

    Contains all anchor-phone measurements for one phone node within [bin_start, bin_end).
    """
    bin_start_time: float          # NTP epoch seconds (UTC)
    bin_end_time: float           # NTP epoch seconds (UTC)
    phone_node_id: int            # Phone node identifier
    measurements: Mapping[int, List[np.ndarray]]  # anchor_id -> list of vectors
```