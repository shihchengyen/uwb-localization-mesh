# Main data collection functions

```python 
def collect_datapoint(
    ground_truth: Vector3,
    orientation: str,
) -> Tuple[Vector3, BinnedData]:
    """
    Capture a labeled datapoint using the most recent PGO solution and the
    current sliding-window bin.

    Inputs
    ------
    ground_truth: (x, y, z) in cm, global frame.
    orientation:  Device/rig orientation label, eg. A, B, C ...

    Returns
    -------
    (
      pgo_measurement,   # (x, y, z) in cm from latest PGO at call time
      binned_data        # realized bin used to produce edges for that PGO tick
    )

    Timing
    ------
    - Uses NTP-corrected wall clock for all timestamps.
    - The returned BinnedData’s [bin_start_time, bin_end_time] reflect the
      window used to generate the edges consumed by the latest PGO solve.
    """


def collect_variance(
    ground_truth: Vector3,
    orientation: Orientation,
) -> Tuple[Vector3, FilterOutput]:
    """
    Assess short-horizon jitter and filter diagnostics over the latest ~10 PGO
    updates (≈10 s) plus runtime effects.

    Inputs
    ------
    ground_truth: (x, y, z) in cm, global frame.
    orientation:  Device/rig orientation label, eg. A, B, C ...

    Returns
    -------
    (
      pgo_measurement,   # (x, y, z) in cm from latest PGO at call time
      filter_output      # variance/covariance and filter stats (TypedDict)
    )

    Notes
    -----
    - The function black-boxes the specific filter (e.g., Kalman) and windowing.
    - Field names in FilterOutput are stable so CSV schemas remain consistent.
    """

```

the output of these will be appended with the time and simply added to a CSV


## Refresher on the BinnedData dataclass
```python
@dataclass(frozen=True)
class Measurement:
    """Single UWB measurement from one anchor at one timestamp."""
    timestamp: float               # NTP epoch seconds (UTC)
    anchor_id: int                 # 0-3 typically
    local_vector: np.ndarray       # [x, y, z] in cm

@dataclass(frozen=True)
class BinnedData:
    """
    A realized 1-second (default) sliding-window bin.

    Contains all anchor-phone measurements for one phone node within [bin_start, bin_end).
    """
    bin_start_time: float          # NTP epoch seconds (UTC)
    bin_end_time: float            # NTP epoch seconds (UTC)
    phone_node_id: str             # e.g., "phone_bin_23"
    measurements: Mapping[int, List[np.ndarray]]  # anchor_id -> list of vectors
```