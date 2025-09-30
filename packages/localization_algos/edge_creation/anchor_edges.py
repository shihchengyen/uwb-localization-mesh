"""
Pure functions for creating anchor-to-anchor edges from ground truth positions.
"""

import numpy as np
from typing import List, Tuple
from datatypes.datatypes import AnchorConfig

def create_anchor_anchor_edges(anchor_config: AnchorConfig) -> List[Tuple[str, str, np.ndarray]]:
    """
    Create edges between all pairs of anchors based on their ground truth positions.
    
    Args:
        anchor_config: Ground truth anchor positions
        
    Returns:
        List of (from_node, to_node, relative_vector) tuples
    """
    edges = []
    positions = anchor_config.get_all_positions()
    
    # Create edges between all pairs of anchors
    for anchor_i in positions:
        pos_i = positions[anchor_i]
        for anchor_j in positions:
            if anchor_i < anchor_j:  # Only create one edge between each pair
                pos_j = positions[anchor_j]
                # Relative vector from anchor i to anchor j
                relative_vec = pos_j - pos_i
                
                from_node = f"anchor_{anchor_i}"
                to_node = f"anchor_{anchor_j}"
                edges.append((from_node, to_node, relative_vec))
                
                # Add reverse edge with negative vector
                edges.append((to_node, from_node, -relative_vec))
    
    return edges
