#!/usr/bin/env python3
"""
Single/All Anchor Measurement Visualization by Orientation (2D - X,Y only)

This script visualizes measurements from a specified anchor, colored by phone orientation.
All measurements are transformed to global coordinates using the same transformation as PGO.
The plot style matches anchor_{anchor_id}_all_measurements_combined.png but colors indicate orientation.

Usage:
    uv run plot_single_anchor_measurements_by_orientation.py <csv_file> <anchor_id>
    
Example:
in \Data_collection\Data:
    uv run data_processing_scripts\plot_single_anchor_measurements_by_orientation.py 28oct\datapoints28oct.csv 3
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import sys
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from collections import defaultdict

# Set up plotting style
try:
    plt.style.use('seaborn-v0_8')
except OSError:
    try:
        plt.style.use('seaborn')
    except OSError:
        pass  # Use default style

try:
    import seaborn as sns
    sns.set_palette("husl")
except ImportError:
    pass  # seaborn not available, use default matplotlib colors

# Anchor positions from the codebase (in cm)
ANCHOR_POSITIONS = {
    0: np.array([480, 600, 0]),
    1: np.array([0, 600, 0]), 
    2: np.array([480, 0, 0]),
    3: np.array([0, 0, 0])
}

# Anchor rotation matrices for transforming local to global coordinates
def Rz(deg: float) -> np.ndarray:
    """Rotation matrix around Z axis."""
    rad = np.radians(deg)
    c, s = np.cos(rad), np.sin(rad)
    return np.array([
        [c, -s, 0.0],
        [s, c, 0.0],
        [0.0, 0.0, 1.0]
    ], dtype=float)

def Ry(deg: float) -> np.ndarray:
    """Rotation matrix around Y axis."""
    rad = np.radians(deg)
    c, s = np.cos(rad), np.sin(rad)
    return np.array([
        [c, 0.0, s],
        [0.0, 1.0, 0.0],
        [-s, 0.0, c]
    ], dtype=float)

# Anchor transformation matrices (from codebase)
ANCHOR_R = {
    0: Rz(225.0) @ Ry(+45.0),  # top-right faces SW, tilted down
    1: Rz(315.0) @ Ry(+45.0),  # top-left faces SE, tilted down
    2: Rz(135.0) @ Ry(+45.0),  # bottom-right faces NW, tilted down
    3: Rz(45.0) @ Ry(+45.0),   # bottom-left faces NE, tilted down
}

def transform_local_to_global(anchor_id: int, local_vector: np.ndarray) -> np.ndarray:
    """Transform local anchor measurement to global coordinates."""
    return ANCHOR_R[anchor_id] @ local_vector

def extract_anchor_measurements(row, anchor_id: int) -> List[np.ndarray]:
    """
    Extract and transform measurements from a specific anchor.
    
    Args:
        row: DataFrame row containing measurement data
        anchor_id: ID of the anchor to extract measurements from
        
    Returns:
        List of global measurement vectors (X, Y only)
    """
    # Parse measurement data
    filtered_data = json.loads(row['filtered_binned_data_json'])
    measurements = filtered_data['measurements']
    
    # Get measurements for this anchor
    anchor_id_str = str(anchor_id)
    if anchor_id_str not in measurements:
        return []
    
    local_measurements = measurements[anchor_id_str]
    if not local_measurements:
        return []
    
    # Transform all measurements to global frame (only X,Y)
    global_measurements = []
    for local_vec in local_measurements:
        local_array = np.array(local_vec)
        global_vec = transform_local_to_global(anchor_id, local_array)
        global_measurements.append(global_vec[:2])  # Only X,Y
    
    return global_measurements

def extract_all_anchor_measurements(row) -> List[Tuple[int, np.ndarray]]:
    """
    Extract and transform measurements from all anchors.
    
    Args:
        row: DataFrame row containing measurement data
        
    Returns:
        List of tuples (anchor_id, global_measurement_vector) for all anchors
    """
    # Parse measurement data
    filtered_data = json.loads(row['filtered_binned_data_json'])
    measurements = filtered_data['measurements']
    
    all_measurements = []
    for anchor_id in ANCHOR_POSITIONS.keys():
        anchor_id_str = str(anchor_id)
        if anchor_id_str in measurements:
            local_measurements = measurements[anchor_id_str]
            if local_measurements:
                for local_vec in local_measurements:
                    local_array = np.array(local_vec)
                    global_vec = transform_local_to_global(anchor_id, local_array)
                    all_measurements.append((anchor_id, global_vec[:2]))  # Only X,Y
    
    return all_measurements

def calculate_phone_positions(anchor_id: int, global_measurements: List[np.ndarray]) -> List[np.ndarray]:
    """
    Calculate phone positions from global measurement vectors.
    
    Args:
        anchor_id: ID of the anchor
        global_measurements: List of global measurement vectors (X, Y)
        
    Returns:
        List of phone positions (X, Y)
    """
    anchor_pos = ANCHOR_POSITIONS[anchor_id][:2]  # Only X,Y
    phone_positions = [anchor_pos + meas for meas in global_measurements]
    return phone_positions

def create_visualizations_by_orientation(df: pd.DataFrame, anchor_id: Optional[int], output_dir: Path):
    """
    Create visualization plots for measurements, colored by phone orientation.
    
    Args:
        df: DataFrame with measurement data
        anchor_id: ID of anchor to plot, or None for all anchors combined
        output_dir: Directory to save output files
    """
    
    # Group data by orientation
    orientation_groups = defaultdict(list)
    
    # Collect all unique ground truth positions for plotting crosses
    all_gt_positions = set()
    
    for _, row in df.iterrows():
        gt_x = row['ground_truth_x']
        gt_y = row['ground_truth_y']
        orientation = row['orientation']
        all_gt_positions.add((gt_x, gt_y))
        
        if anchor_id is None:
            # Extract measurements from all anchors
            all_measurements = extract_all_anchor_measurements(row)
            if all_measurements:
                phone_positions = []
                for aid, global_meas in all_measurements:
                    anchor_pos = ANCHOR_POSITIONS[aid][:2]
                    phone_pos = anchor_pos + global_meas
                    phone_positions.append(phone_pos)
                
                if phone_positions:
                    orientation_groups[orientation].append({
                        'gt_pos': np.array([gt_x, gt_y]),
                        'phone_positions': phone_positions,
                        'orientation': orientation
                    })
        else:
            # Extract measurements for the specified anchor only
            global_measurements = extract_anchor_measurements(row, anchor_id)
            if global_measurements:
                phone_positions = calculate_phone_positions(anchor_id, global_measurements)
                
                orientation_groups[orientation].append({
                    'gt_pos': np.array([gt_x, gt_y]),
                    'phone_positions': phone_positions,
                    'orientation': orientation
                })
    
    if not orientation_groups:
        anchor_str = "all anchors" if anchor_id is None else f"anchor {anchor_id}"
        print(f"No measurements found for {anchor_str}")
        return
    
    # Create color map for orientations
    unique_orientations = sorted(orientation_groups.keys())
    print(f"Found {len(unique_orientations)} unique orientations: {unique_orientations}")
    
    # Use a colormap to assign colors to orientations
    try:
        import matplotlib.cm as cm
        cmap = cm.get_cmap('tab10')
    except AttributeError:
        # For newer matplotlib versions
        cmap = plt.colormaps['tab10']
    
    orientation_colors = {}
    for idx, orient in enumerate(unique_orientations):
        # Normalize index to 0-1 range for colormap (using modulo to cycle through colors)
        orientation_colors[orient] = cmap((idx % 10) / 9.0)
    
    # Create a combined plot showing all orientations together (same style as position-based plot)
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Plot all anchor positions (grey and small)
    # Note: These are the 4 anchor positions, shown as grey squares for reference
    # They are NOT measurement dots - they are the fixed anchor locations
    for aid, anchor_pos in ANCHOR_POSITIONS.items():
        ax.scatter([anchor_pos[0]], [anchor_pos[1]], c='grey', marker='s', s=100, 
                  zorder=5, edgecolors='black', linewidths=1.5)
    
    # Plot all ground truth positions as grey crosses (once, not per orientation)
    for gt_x, gt_y in all_gt_positions:
        ax.scatter([gt_x], [gt_y], c='grey', marker='+', s=50, 
                  zorder=6, linewidths=2)
    
    # Plot all measurements grouped by orientation
    for orient in unique_orientations:
        group_data = orientation_groups[orient]
        color = orientation_colors[orient]
        
        # Collect all phone positions for this orientation
        all_phone_positions_for_orient = []
        for data in group_data:
            all_phone_positions_for_orient.extend(data['phone_positions'])
        
        # Plot all phone positions for this orientation
        if all_phone_positions_for_orient:
            phone_pos_array = np.array(all_phone_positions_for_orient)
            ax.scatter(phone_pos_array[:, 0], phone_pos_array[:, 1], 
                      c=[color] * len(phone_pos_array), alpha=0.4, s=20, 
                      zorder=3, label=f'Orientation {orient}')
    
    ax.set_xlabel('X (cm)', fontsize=12)
    ax.set_ylabel('Y (cm)', fontsize=12)
    if anchor_id is None:
        ax.set_title(f'All Measurements from All Anchors by Phone Orientation', fontsize=14)
    else:
        ax.set_title(f'All Measurements from Anchor {anchor_id} by Phone Orientation', fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    
    # Add legend
    ax.legend(loc='best', fontsize=10)
    
    plt.tight_layout()
    if anchor_id is None:
        output_file = output_dir / f'all_anchors_all_measurements_by_orientation.png'
    else:
        output_file = output_dir / f'anchor_{anchor_id}_all_measurements_by_orientation.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Saved orientation-based plot to {output_file}")
    plt.show()
    
    # Create statistics table by orientation
    print("\n" + "="*80)
    if anchor_id is None:
        print(f"ALL ANCHORS MEASUREMENT STATISTICS BY ORIENTATION")
    else:
        print(f"ANCHOR {anchor_id} MEASUREMENT STATISTICS BY ORIENTATION")
    print("="*80)
    print(f"{'Orientation':<15} {'Count':<8} {'Mean X':<10} {'Mean Y':<10} {'Std X':<10} {'Std Y':<10}")
    print("-"*80)
    
    for orient in unique_orientations:
        group_data = orientation_groups[orient]
        
        all_phone_positions = []
        for data in group_data:
            all_phone_positions.extend(data['phone_positions'])
        
        if all_phone_positions:
            phone_pos_array = np.array(all_phone_positions)
            mean_x = np.mean(phone_pos_array[:, 0])
            mean_y = np.mean(phone_pos_array[:, 1])
            std_x = np.std(phone_pos_array[:, 0])
            std_y = np.std(phone_pos_array[:, 1])
            
            print(f"{orient:<15} {len(all_phone_positions):<8} "
                  f"{mean_x:10.2f} {mean_y:10.2f} {std_x:10.2f} {std_y:10.2f}")
    
    print("="*80)

def main():
    if len(sys.argv) != 3:
        print("Usage: uv run plot_single_anchor_measurements_by_orientation.py <csv_file> <anchor_id|all>")
        print("Example: uv run plot_single_anchor_measurements_by_orientation.py datapoints28oct.csv 0")
        print("Example: uv run plot_single_anchor_measurements_by_orientation.py datapoints28oct.csv all")
        sys.exit(1)
    
    csv_file = Path(sys.argv[1])
    anchor_arg = sys.argv[2].lower()
    
    # Handle "all" case
    if anchor_arg == 'all':
        anchor_id = None
    else:
        try:
            anchor_id = int(anchor_arg)
        except ValueError:
            print(f"Error: anchor_id must be an integer or 'all', got '{sys.argv[2]}'")
            sys.exit(1)
        
        if anchor_id not in ANCHOR_POSITIONS:
            print(f"Error: anchor_id must be one of {list(ANCHOR_POSITIONS.keys())} or 'all'")
            sys.exit(1)
    
    if not csv_file.exists():
        print(f"Error: File {csv_file} does not exist")
        sys.exit(1)
    
    # Create output directory
    output_dir = csv_file.parent
    
    print(f"Loading data from {csv_file}...")
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} data points")
    if anchor_id is None:
        print(f"Analyzing measurements from all anchors by orientation...")
    else:
        print(f"Analyzing measurements from anchor {anchor_id} by orientation...")
    
    # Create visualizations colored by orientation
    create_visualizations_by_orientation(df, anchor_id, output_dir)
    
    print(f"\nAnalysis complete! Results saved to {output_dir}")

if __name__ == "__main__":
    main()

