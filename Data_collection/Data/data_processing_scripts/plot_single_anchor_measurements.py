#!/usr/bin/env python3
"""
Single Anchor Measurement Visualization (2D - X,Y only)

This script visualizes measurements from a specified anchor at all ground truth positions.
Measurements are colored by ground truth position (not orientation).
All measurements are transformed to global coordinates using the same transformation as PGO.

Usage:
    uv run plot_single_anchor_measurements.py <csv_file> <anchor_id>
    
Example:
    uv run plot_single_anchor_measurements.py datapoints28oct.csv 0
    in \Data_collection\Data:
    uv run data_processing_scripts\plot_single_anchor_measurements.py 28oct\datapoints28oct.csv 3
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
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

def create_visualizations(df: pd.DataFrame, anchor_id: int, output_dir: Path):
    """Create visualization plots for measurements from specified anchor, colored by ground truth position."""
    
    # Group data by ground truth position (not orientation)
    position_groups = defaultdict(list)
    
    for _, row in df.iterrows():
        gt_x = row['ground_truth_x']
        gt_y = row['ground_truth_y']
        orientation = row['orientation']
        
        # Extract measurements for the specified anchor only
        global_measurements = extract_anchor_measurements(row, anchor_id)
        if global_measurements:
            phone_positions = calculate_phone_positions(anchor_id, global_measurements)
            
            # Group by ground truth position (not orientation)
            key = (int(gt_x), int(gt_y))
            position_groups[key].append({
                'gt_pos': np.array([gt_x, gt_y]),
                'phone_positions': phone_positions,
                'orientation': orientation
            })
    
    if not position_groups:
        print(f"No measurements found for anchor {anchor_id}")
        return
    
    # Create color map for ground truth positions
    unique_positions = sorted(position_groups.keys())
    print(f"Found {len(unique_positions)} unique ground truth positions: {unique_positions}")
    # Use tab10 colormap to assign colors to positions
    try:
        # Use the recommended approach for newer matplotlib versions
        cmap = plt.colormaps['tab10']
    except (AttributeError, KeyError):
        # Fallback for older matplotlib versions
        import matplotlib.cm as cm
        cmap = cm.get_cmap('tab10')
    
    # Position colors: blue, orange, green, red (tab10 indices 0, 1, 2, 3)
    position_color_indices = [0, 1, 2, 3]  # blue, orange, green, red
    position_colors = {}
    for idx, pos_key in enumerate(unique_positions):
        color_idx = position_color_indices[idx % len(position_color_indices)]
        position_colors[pos_key] = cmap(color_idx / 9.0)
    
    # Anchor colors by tab10 indices 
    anchor_color_indices = [4, 5, 6, 7]  # purple, brown, pink, grey
    anchor_colors = [cmap(idx / 9.0) for idx in anchor_color_indices]
    
    # Create figure with subplots for each ground truth position
    sorted_positions = sorted(position_groups.keys())
    n_positions = len(sorted_positions)
    
    # Calculate grid size
    cols = min(4, n_positions)
    rows = (n_positions + cols - 1) // cols
    
    fig, axes = plt.subplots(rows, cols, figsize=(5*cols, 5*rows))
    if n_positions == 1:
        axes = [axes]
    else:
        axes = axes.flatten() if rows > 1 else axes
    
    for idx, pos_key in enumerate(sorted_positions):
        ax = axes[idx]
        gt_x, gt_y = pos_key
        group_data = position_groups[pos_key]
        
        # Get color for this ground truth position
        color = position_colors[pos_key]
        
        # Plot all anchor positions with distinct colors
        # Note: These are the 4 fixed anchor positions, shown as colored squares for reference
        for aid, anchor_pos in ANCHOR_POSITIONS.items():
            ax.scatter([anchor_pos[0]], [anchor_pos[1]], c=anchor_colors[aid], marker='s', s=45, 
                      zorder=6, edgecolors='black', linewidths=1.2, alpha=0.8, label='Anchors' if aid == 0 else '')
            # ax.scatter([anchor_pos[0]], [anchor_pos[1]], c='black', marker='s', s=60, 
            #           zorder=6, edgecolors='black', linewidths=1.2, alpha=0.5, label='Anchors' if aid == 0 else '')
        
        # Circle the specified anchor with a thin red circle
        specified_anchor_pos = ANCHOR_POSITIONS[anchor_id]
        circle = Circle((specified_anchor_pos[0], specified_anchor_pos[1]), radius=60, 
                       fill=False, edgecolor='red', linewidth=1.0, zorder=8)
        ax.add_patch(circle)
        
        # # Plot ground truth position crosses 
        # ax.scatter([gt_x], [gt_y], c=[color], marker='+', s=50, 
        #           zorder=7, linewidths=2)
        
        # Plot ground truth position stars
        ax.scatter([gt_x], [gt_y], c='black', marker='*', s=100, 
                  zorder=5, edgecolors='black', linewidths=0.2, alpha=0.4)
        
        # Plot all phone positions from measurements for the specified anchor
        total_measurements = 0
        for data in group_data:
            phone_positions = data['phone_positions']
            if phone_positions:
                phone_pos_array = np.array(phone_positions)
                # Ensure color is explicitly set (should never be grey for measurements)
                if pos_key not in position_colors:
                    print(f"Warning: Position {pos_key} not in color map!")
                    plot_color = 'red'  # Fallback color
                else:
                    plot_color = position_colors[pos_key]
                ax.scatter(phone_pos_array[:, 0], phone_pos_array[:, 1], 
                          c=[plot_color] * len(phone_pos_array), alpha=0.4, s=15, zorder=3)
                total_measurements += len(phone_positions)
        
        ax.set_xlabel('X (cm)')
        ax.set_ylabel('Y (cm)')
        ax.set_title(f'GT: ({gt_x:.0f}, {gt_y:.0f})\n'
                    f'{total_measurements} measurements')
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal', adjustable='box')
        ax.set_xlim(-200, 680)
        ax.set_ylim(-300, 900)
    
    # Hide unused subplots
    for idx in range(n_positions, len(axes)):
        axes[idx].axis('off')
    
    plt.tight_layout()
    output_file = output_dir / f'anchor_{anchor_id}_measurements_by_position.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Saved plot to {output_file}")
    plt.show()
    
    # Create a combined plot showing all positions together
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Plot all anchor positions with distinct colors
    # Note: These are the 4 fixed anchor positions, shown as colored squares for reference
    for aid, anchor_pos in ANCHOR_POSITIONS.items():
        ax.scatter([anchor_pos[0]], [anchor_pos[1]], c=anchor_colors[aid], marker='s', s=100, 
                  zorder=5, edgecolors='black', linewidths=1.2, alpha=0.9)
        # ax.scatter([anchor_pos[0]], [anchor_pos[1]], c='black', marker='s', s=60, 
        #             zorder=6, edgecolors='black', linewidths=1.2, alpha=0.5, label='Anchors' if aid == 0 else '')

    # Circle the specified anchor with a thin red circle
    specified_anchor_pos = ANCHOR_POSITIONS[anchor_id]
    circle = Circle((specified_anchor_pos[0], specified_anchor_pos[1]), radius=40, 
                   fill=False, edgecolor='red', linewidth=1.0, zorder=8)
    ax.add_patch(circle)
    
    # Plot all measurements grouped by ground truth position
    for pos_key in sorted_positions:
        gt_x, gt_y = pos_key
        group_data = position_groups[pos_key]
        
        color = position_colors[pos_key]
        
        # # Plot ground truth position as a tiny cross in the same color
        # ax.scatter([gt_x], [gt_y], c=[color], marker='+', s=50, 
        #           zorder=6, linewidths=2)
        
        # Plot ground truth position stars
        ax.scatter([gt_x], [gt_y], c='black', marker='*', s=170, 
                  zorder=6, edgecolors='black', linewidths=0.2, alpha=0.4)
        
        # Plot all phone positions from the specified anchor
        for data in group_data:
            phone_positions = data['phone_positions']
            if phone_positions:
                phone_pos_array = np.array(phone_positions)
                # Ensure color is explicitly set (should never be grey for measurements)
                if pos_key not in position_colors:
                    print(f"Warning: Position {pos_key} not in color map!")
                    plot_color = 'red'  # Fallback color
                else:
                    plot_color = position_colors[pos_key]
                ax.scatter(phone_pos_array[:, 0], phone_pos_array[:, 1], 
                          c=[plot_color] * len(phone_pos_array), alpha=0.4, s=20, zorder=3)
    
    ax.set_xlabel('X (cm)', fontsize=12)
    ax.set_ylabel('Y (cm)', fontsize=12)
    ax.set_title(f'All Measurements from Anchor {anchor_id} at All Ground Truth Positions', fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    ax.set_xlim(-200, 680)
    ax.set_ylim(-300, 900)
    
    plt.tight_layout()
    output_file = output_dir / f'anchor_{anchor_id}_all_measurements_combined.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Saved combined plot to {output_file}")
    plt.show()
    
    # Create statistics table
    print("\n" + "="*80)
    print(f"ANCHOR {anchor_id} MEASUREMENT STATISTICS")
    print("="*80)
    print(f"{'Position':<20} {'Count':<8} {'Mean X':<10} {'Mean Y':<10} {'Std X':<10} {'Std Y':<10}")
    print("-"*80)
    
    for pos_key in sorted_positions:
        gt_x, gt_y = pos_key
        group_data = position_groups[pos_key]
        
        all_phone_positions = []
        for data in group_data:
            all_phone_positions.extend(data['phone_positions'])
        
        if all_phone_positions:
            phone_pos_array = np.array(all_phone_positions)
            mean_x = np.mean(phone_pos_array[:, 0])
            mean_y = np.mean(phone_pos_array[:, 1])
            std_x = np.std(phone_pos_array[:, 0])
            std_y = np.std(phone_pos_array[:, 1])
            
            print(f"({gt_x:6.0f}, {gt_y:6.0f})    {len(all_phone_positions):<8} "
                  f"{mean_x:10.2f} {mean_y:10.2f} {std_x:10.2f} {std_y:10.2f}")
    
    print("="*80)

def main():
    if len(sys.argv) != 3:
        print("Usage: python plot_single_anchor_measurements.py <csv_file> <anchor_id>")
        print("Example: python plot_single_anchor_measurements.py datapoints28oct.csv 0")
        sys.exit(1)
    
    csv_file = Path(sys.argv[1])
    try:
        anchor_id = int(sys.argv[2])
    except ValueError:
        print(f"Error: anchor_id must be an integer, got '{sys.argv[2]}'")
        sys.exit(1)
    
    if anchor_id not in ANCHOR_POSITIONS:
        print(f"Error: anchor_id must be one of {list(ANCHOR_POSITIONS.keys())}")
        sys.exit(1)
    
    if not csv_file.exists():
        print(f"Error: File {csv_file} does not exist")
        sys.exit(1)
    
    # Create output directory
    output_dir = csv_file.parent
    
    print(f"Loading data from {csv_file}...")
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} data points")
    print(f"Analyzing measurements from anchor {anchor_id}...")
    
    # Create visualizations filtered by anchor_id
    create_visualizations(df, anchor_id, output_dir)
    
    print(f"\nAnalysis complete! Results saved to {output_dir}")

if __name__ == "__main__":
    main()

