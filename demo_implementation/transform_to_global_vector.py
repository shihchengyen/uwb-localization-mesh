import numpy as np
import os
import sys

# Add current directory to path for relative imports (bc this script is in /Data_collection)
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from create_anchor_edges import ANCHORS

# transformation from local anchor coordinates to global XYZ coordinates
# 45° "facing into the room" yaw for each board (=rotate about z axis); 45° pitch downwards from ceiling (=rotate about y axis).
# local x points along heading into the room,
# local y is left of the board,
# local z is up. 

def Rz(deg: float) -> np.ndarray:
    """Rotation matrix about Z axis (yaw)"""
    rad = np.deg2rad(deg); c, s = np.cos(rad), np.sin(rad)
    return np.array([[c, -s, 0.0],
                     [s,  c, 0.0],
                     [0.0, 0.0, 1.0]], dtype=float)

def Ry(deg: float) -> np.ndarray:
    """Rotation matrix about Y axis (pitch)"""
    rad = np.deg2rad(deg); c, s = np.cos(rad), np.sin(rad)
    return np.array([[c,  0.0, s],
                     [0.0, 1.0, 0.0],
                     [-s, 0.0, c]], dtype=float)

# Combined rotation: 45° yaw in XY plane + 45° downward pitch
ANCHOR_R = {
    0: Ry(-45.0) @ Rz(225.0),  # top-right faces bottom-left, + downward pitch
    1: Ry(-45.0) @ Rz(315.0),  # top-left  faces bottom-right, + downward pitch
    2: Ry(-45.0) @ Rz(135.0),  # bottom-right faces top-left, + downward pitch
    3: Ry(-45.0) @ Rz(45.0),   # bottom-left  faces top-right, + downward pitch
}

def create_relative_measurement(anchor_id: int, phone_node_id: str, local_vector: np.ndarray) -> tuple:
    """
    Create a relative measurement (edge) between an anchor and phone node.

    Args:
        anchor_id (int): ID of the anchor (0-3)
        phone_node_id (str): Identifier for the phone pose node (e.g., 'phone_t1')
        local_vector (np.ndarray): Local vector in anchor's coordinate system (x, y, z) in cm

    Returns:
        tuple: (anchor_node, phone_node, displacement_vector) where displacement_vector
               is the relative displacement from anchor to phone in global coordinates

    Raises:
        ValueError: If anchor_id is not in range 0-3 or local_vector is not 3D
    """
    if anchor_id not in ANCHORS:
        raise ValueError(f"Invalid anchor_id: {anchor_id}. Must be 0-3.")

    if local_vector.shape != (3,):
        raise ValueError(f"local_vector must be shape (3,), got {local_vector.shape}")

    # Rotate from local anchor coordinates to global XY
    v_global = ANCHOR_R[anchor_id] @ local_vector

    # Return relative measurement: (anchor_node, phone_node, displacement)
    anchor_node = f"anchor_{anchor_id}"
    return (anchor_node, phone_node_id, v_global)


# Example usage
if __name__ == "__main__":
    # Example: create relative measurement from anchor 3 to phone at time 1
    local_vec = np.array([10.0, 20.0, 5.0])  # cm
    relative_edge = create_relative_measurement(3, "phone_t1", local_vec)
    print(f"Local vector from anchor 3: {local_vec}")
    print(f"Relative measurement: {relative_edge}")

    # Test all anchors
    print("\nAnchor-phone relative measurements:")
    for anchor_id in range(4):
        relative_edge = create_relative_measurement(anchor_id, "phone_t1", local_vec)
        print(f"Anchor {anchor_id}: {relative_edge}")
