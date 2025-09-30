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