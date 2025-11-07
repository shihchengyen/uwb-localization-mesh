"""
Pure functions for coordinate transformations and vector operations.
"""

import numpy as np
from typing import Tuple, Dict

def Rz(deg: float) -> np.ndarray:
    """Create a rotation matrix about the Z axis (yaw)."""
    rad = np.deg2rad(deg)
    c, s = np.cos(rad), np.sin(rad)
    return np.array([
        [c, -s, 0.0],
        [s,  c, 0.0],
        [0.0, 0.0, 1.0]
    ], dtype=float)

def Ry(deg: float) -> np.ndarray:
    """Create a rotation matrix about the Y axis (pitch)."""
    rad = np.deg2rad(deg)
    c, s = np.cos(rad), np.sin(rad)
    return np.array([
        [c,  0.0, s],
        [0.0, 1.0, 0.0],
        [-s, 0.0, c]
    ], dtype=float)

# Rotation from sensor's local (board-fixed) frame to global frame
# Sensor's local frame is fixed to the board: x=forward, y=left, z=up (relative to board)
# Boards are physically tilted 45° down from horizontal
# When sensor reports el=0, az=0, it's along the board's forward direction (which is 45° down)
# 
# Transformation: Rz(yaw) @ Ry(+45°)
#   1. Ry(+45°): Tilts board's forward direction 45° down (local x toward global -z)
#   2. Rz(yaw): Rotates in XY plane to face room center
ANCHOR_R: Dict[int, np.ndarray] = {
    0: Rz(225.0) @ Ry(+45.0),  # top-right faces SW, tilted down
    1: Rz(315.0) @ Ry(+45.0),  # top-left faces SE, tilted down
    2: Rz(135.0) @ Ry(+45.0),  # bottom-right faces NW, tilted down
    3: Rz(45.0) @ Ry(+45.0),   # bottom-left faces NE, tilted down
}

def create_relative_measurement(
    anchor_id: int,
    phone_node_id: int,
    local_vector: np.ndarray
) -> Tuple[str, str, np.ndarray]:
    """
    Create a relative measurement edge between an anchor and phone.
    Transforms from local anchor coordinates to global frame.
    
    Args:
        anchor_id: Identifier for the anchor (0-3)
        phone_node_id: Identifier for the phone node
        local_vector: [x, y, z] vector in anchor's local coordinates (cm)
        
    Returns:
        Tuple of (from_node, to_node, relative_vector) where relative_vector
        is in global coordinates
        
    Raises:
        ValueError: If anchor_id is invalid or local_vector is not 3D
    """
    if anchor_id not in ANCHOR_R:
        raise ValueError(f"Invalid anchor_id: {anchor_id}. Must be 0-3.")

    if local_vector.shape != (3,):
        raise ValueError(f"local_vector must be shape (3,), got {local_vector.shape}")

    # Convert IDs to node names
    from_node = f"anchor_{anchor_id}"
    to_node = f"phone_{phone_node_id}"
    
    # Transform local vector to global frame
    v_global = ANCHOR_R[anchor_id] @ local_vector
    
    return from_node, to_node, v_global