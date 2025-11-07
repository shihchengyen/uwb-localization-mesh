"""
Core PGO (Pose Graph Optimization) solver implementation.
Uses nonlinear least squares to optimize node positions based on relative measurements.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scipy.optimize import least_squares

from .transforms import apply_anchoring_transformation

@dataclass(frozen=True)
class PGOResult:
    """Result from PGO optimization."""
    node_positions: Dict[str, np.ndarray]  # node_id -> [x, y, z] position
    success: bool
    iterations: int
    error: float

class PGOSolver:
    """
    Pose Graph Optimization solver for 3D position estimation.
    Optimizes node positions to minimize the error between predicted and measured relative positions.
    """
    
    def __init__(
        self,
        max_iterations: int = 100,
        convergence_threshold: float = 1e-6,
        method: str = 'trf'  # Levenberg-Marquardt-like algorithm
    ):
        """
        Initialize PGO solver.
        
        Args:
            max_iterations: Maximum number of optimization iterations
            convergence_threshold: Threshold for convergence check
            method: Optimization method ('trf', 'dogbox', or 'lm')
        """
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self.method = method
        
    def solve(
        self,
        nodes: Dict[str, Optional[np.ndarray]],
        edges: List[Tuple[str, str, np.ndarray]],
        anchor_positions: Dict[int, np.ndarray]
    ) -> PGOResult:
        """
        Solve the pose graph optimization problem.
        
        Args:
            nodes: Dict of node_id -> initial position (None if unknown)
            edges: List of (from_node, to_node, relative_vector) constraints
            anchor_positions: Ground truth anchor positions for anchoring transformation
            
        Returns:
            PGOResult with optimized positions and metadata
            
        Raises:
            ValueError: If the graph is invalid or optimization fails
        """
        # Extract node IDs and create mapping to indices
        node_ids = list(nodes.keys())
        node_to_idx = {nid: i for i, nid in enumerate(node_ids)}
        
        # Initialize positions for optimization
        n_nodes = len(nodes)
        init_positions = np.zeros((n_nodes, 3))
        
        # Set known positions and initialize unknown ones
        for node_id, pos in nodes.items():
            idx = node_to_idx[node_id]
            if pos is not None:
                init_positions[idx] = pos
            else:
                # Initialize unknown positions to mean of connected nodes
                connected_pos = []
                for from_node, to_node, rel_vec in edges:
                    if node_id == to_node and nodes.get(from_node) is not None:
                        connected_pos.append(nodes[from_node] + rel_vec)
                    elif node_id == from_node and nodes.get(to_node) is not None:
                        connected_pos.append(nodes[to_node] - rel_vec)
                
                if connected_pos:
                    init_positions[idx] = np.mean(connected_pos, axis=0)
        
        # Flatten for optimization
        x0 = init_positions.reshape(-1)
        
        def residuals(x):
            """Compute residuals for all edges."""
            X = x.reshape(-1, 3)
            errs = []
            
            for from_node, to_node, rel_vec in edges:
                from_idx = node_to_idx[from_node]
                to_idx = node_to_idx[to_node]
                
                # Predicted relative vector
                pred_vec = X[to_idx] - X[from_idx]
                
                # Error between predicted and measured
                err = pred_vec - rel_vec
                errs.append(err)
            
            return np.concatenate(errs)
        
        # Run optimization
        result = least_squares(
            residuals,
            x0,
            method=self.method,
            max_nfev=self.max_iterations,
            ftol=self.convergence_threshold
        )
        
        if not result.success:
            raise ValueError("PGO optimization failed to converge")
            
        # Reshape and create initial output
        opt_positions = result.x.reshape(-1, 3)
        initial_positions = {
            node_id: opt_positions[node_to_idx[node_id]]
            for node_id in nodes
        }
        
        # Apply anchoring transformation to align with ground truth
        anchored_positions = apply_anchoring_transformation(
            initial_positions,
            anchor_positions
        )
        
        return PGOResult(
            node_positions=anchored_positions,
            success=result.success,
            iterations=result.nfev,
            error=result.cost
        )