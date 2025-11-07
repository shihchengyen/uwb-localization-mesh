"""
Coordinate transformations for PGO results.
"""

import numpy as np
from typing import Dict

def apply_anchoring_transformation(
    optimized_nodes: Dict[str, np.ndarray],
    anchor_positions: Dict[int, np.ndarray]
) -> Dict[str, np.ndarray]:
    """
    Apply anchoring transformation to align optimized positions with known anchor positions.
    Uses a proper 3D similarity transformation (translation + rotation + scaling) to align
    anchor_3 to origin and anchor_0 to its true position.
    
    Args:
        optimized_nodes: Dict of optimized node positions from PGO
        anchor_positions: Dict of ground truth anchor positions
        
    Returns:
        Dict of anchored positions where known anchors are fixed to their true positions
    """
    # Extract optimized anchor positions
    opt_anchor_3 = optimized_nodes.get('anchor_3')
    opt_anchor_0 = optimized_nodes.get('anchor_0')
    
    if opt_anchor_3 is None or opt_anchor_0 is None:
        raise ValueError("Optimized anchor positions not found")
        
    # Target positions
    target_anchor_3 = anchor_positions[3]  # Origin
    target_anchor_0 = anchor_positions[0]  # Reference for orientation
    
    # Step 1: Translate so anchor_3 is at origin
    translation = -opt_anchor_3
    translated_nodes = {}
    for node_id, position in optimized_nodes.items():
        if position is not None:
            translated_nodes[node_id] = position + translation
            
    # After translation, anchor_3 should be at origin
    translated_anchor_0 = translated_nodes['anchor_0']
    
    # Step 2: Calculate scale factor
    opt_distance = np.linalg.norm(translated_anchor_0)
    true_distance = np.linalg.norm(target_anchor_0 - target_anchor_3)
    
    if opt_distance > 1e-6:  # Avoid division by zero
        scale_factor = true_distance / opt_distance
    else:
        scale_factor = 1.0
        
    # Step 3: Calculate rotation
    if opt_distance > 1e-6:
        # Normalized vectors
        opt_direction = translated_anchor_0 / opt_distance
        target_direction = target_anchor_0 / true_distance
        
        # For 2D case (Z components are 0), use simple 2D rotation
        if abs(opt_direction[2]) < 1e-6 and abs(target_direction[2]) < 1e-6:
            opt_angle = np.arctan2(opt_direction[1], opt_direction[0])
            target_angle = np.arctan2(target_direction[1], target_direction[0])
            rotation_angle = target_angle - opt_angle
            
            cos_theta = np.cos(rotation_angle)
            sin_theta = np.sin(rotation_angle)
            
            rotation_matrix = np.array([
                [cos_theta, -sin_theta, 0],
                [sin_theta,  cos_theta, 0],
                [0,          0,         1]
            ])
        else:
            # 3D rotation using cross product and Rodrigues formula
            v = np.cross(opt_direction, target_direction)
            s = np.linalg.norm(v)
            c = np.dot(opt_direction, target_direction)
            
            if s < 1e-6:  # Vectors are parallel
                rotation_matrix = np.eye(3) if c > 0 else -np.eye(3)
            else:
                vx = np.array([[0, -v[2], v[1]],
                             [v[2], 0, -v[0]],
                             [-v[1], v[0], 0]])
                rotation_matrix = np.eye(3) + vx + np.dot(vx, vx) * ((1 - c) / (s * s))
    else:
        rotation_matrix = np.eye(3)
        
    # Step 4: Apply scale and rotation to all nodes
    transformed_nodes = {}
    for node_id, position in translated_nodes.items():
        if position is not None:
            scaled_pos = position * scale_factor
            rotated_pos = rotation_matrix @ scaled_pos
            transformed_nodes[node_id] = rotated_pos
            
    # Step 5: Force known anchors to their exact positions
    for i in range(4):
        transformed_nodes[f'anchor_{i}'] = anchor_positions[i]
        
    return transformed_nodes
