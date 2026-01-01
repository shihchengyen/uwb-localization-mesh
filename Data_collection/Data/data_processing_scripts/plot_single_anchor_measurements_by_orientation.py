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
    or
    
    uv run data_processing_scripts\plot_single_anchor_measurements_by_orientation.py 28oct\datapoints28oct.csv all
    or

    uv run data_processing_scripts\plot_single_anchor_measurements_by_orientation.py 28oct\datapoints28oct.csv all 120.0,180.0,0.0
    or

    uv run data_processing_scripts\plot_single_anchor_measurements_by_orientation.py 28oct\datapoints28oct.csv all 120.0,180.0,0.0 --raw
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

def extract_anchor_measurements(row, anchor_id: int, use_raw: bool = False) -> List[np.ndarray]:
    """
    Extract and transform measurements from a specific anchor.
    
    Args:
        row: DataFrame row containing measurement data
        anchor_id: ID of the anchor to extract measurements from
        use_raw: If True, use raw_binned_data_json; if False, use filtered_binned_data_json
        
    Returns:
        List of global measurement vectors (X, Y only)
    """
    # Parse measurement data
    data_column = 'raw_binned_data_json' if use_raw else 'filtered_binned_data_json'
    binned_data = json.loads(row[data_column])
    measurements = binned_data['measurements']
    
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

def extract_all_anchor_measurements(row, use_raw: bool = False) -> List[Tuple[int, np.ndarray]]:
    """
    Extract and transform measurements from all anchors.
    
    Args:
        row: DataFrame row containing measurement data
        use_raw: If True, use raw_binned_data_json; if False, use filtered_binned_data_json
        
    Returns:
        List of tuples (anchor_id, global_measurement_vector) for all anchors
    """
    # Parse measurement data
    data_column = 'raw_binned_data_json' if use_raw else 'filtered_binned_data_json'
    binned_data = json.loads(row[data_column])
    measurements = binned_data['measurements']
    
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

def create_visualizations_by_orientation(df: pd.DataFrame, anchor_id: Optional[int], output_dir: Path, coord_filter: Optional[Tuple[float, float, float]] = None, use_raw: bool = False):
    """
    Create visualization plots for measurements, colored by phone orientation.
    
    Args:
        df: DataFrame with measurement data (already filtered if coord_filter was provided)
        anchor_id: ID of anchor to plot, or None for all anchors combined
        output_dir: Directory to save output files
        coord_filter: Optional tuple (x, y, z) indicating filtered coordinates
        use_raw: If True, use raw_binned_data_json; if False, use filtered_binned_data_json
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
            all_measurements = extract_all_anchor_measurements(row, use_raw)
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
            global_measurements = extract_anchor_measurements(row, anchor_id, use_raw)
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
    
    # Use tab10 colormap to assign colors to orientations
    try:
        # Use the recommended approach for newer matplotlib versions
        cmap = plt.colormaps['tab10']
    except (AttributeError, KeyError):
        # Fallback for older matplotlib versions
        import matplotlib.cm as cm
        cmap = cm.get_cmap('tab10')
    
    orientation_colors = {}
    for idx, orient in enumerate(unique_orientations):
        # Normalize index to 0-1 range for colormap (using modulo to cycle through colors)
        orientation_colors[orient] = cmap((idx % 10) / 9.0)
    
    # Anchor colors by tab10 indices
    anchor_color_indices = [4, 5, 6, 7]  # purple, brown, pink, grey
    anchor_colors = [cmap(idx / 9.0) for idx in anchor_color_indices]
    
    # Create a combined plot showing all orientations together (same style as position-based plot)
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Plot all anchor positions with distinct colors
    # Note: These are the 4 fixed anchor positions, shown as colored squares for reference
    # They are NOT measurement dots - they are the fixed anchor locations
    for aid, anchor_pos in ANCHOR_POSITIONS.items():
        ax.scatter([anchor_pos[0]], [anchor_pos[1]], c=anchor_colors[aid], marker='s', s=100, 
                  zorder=5, edgecolors='black', linewidths=1.2, alpha=0.9)
    
    # Circle the specified anchor with a thin red circle (if anchor_id is specified)
    if anchor_id is not None:
        specified_anchor_pos = ANCHOR_POSITIONS[anchor_id]
        circle = Circle((specified_anchor_pos[0], specified_anchor_pos[1]), radius=40, 
                       fill=False, edgecolor='red', linewidth=1.0, zorder=8)
        ax.add_patch(circle)
    
    # Plot all ground truth positions as black stars (once, not per orientation)
    for gt_x, gt_y in all_gt_positions:
        ax.scatter([gt_x], [gt_y], c='black', marker='*', s=170, 
                  zorder=6, edgecolors='black', linewidths=0.2, alpha=0.4)
    
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
    
    # Build title
    if anchor_id is None:
        title = 'All Measurements from All Anchors by Phone Orientation'
    else:
        title = f'All Measurements from Anchor {anchor_id} by Phone Orientation'
    
    if coord_filter is not None:
        filter_x, filter_y, filter_z = coord_filter
        title += f'\nFiltered: GT=({filter_x}, {filter_y}, {filter_z})'
    
    ax.set_title(title, fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    ax.set_xlim(-100, 600)
    
    # Add legend
    ax.legend(loc='best', fontsize=10)
    
    plt.tight_layout()
    
    # Build output filename
    if anchor_id is None:
        base_name = 'all_anchors_all_measurements_by_orientation'
    else:
        base_name = f'anchor_{anchor_id}_all_measurements_by_orientation'
    
    if coord_filter is not None:
        filter_x, filter_y, filter_z = coord_filter
        # Format coordinates for filename (replace dots with underscores)
        coord_str = f'_{filter_x}_{filter_y}_{filter_z}'.replace('.', '_')
        base_name += coord_str
    
    output_file = output_dir / f'{base_name}.png'
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
    if len(sys.argv) < 3 or len(sys.argv) > 5:
        print("Usage: uv run plot_single_anchor_measurements_by_orientation.py <csv_file> <anchor_id|all> [x,y,z] [--raw]")
        print("Example: uv run plot_single_anchor_measurements_by_orientation.py datapoints28oct.csv 0")
        print("Example: uv run plot_single_anchor_measurements_by_orientation.py datapoints28oct.csv all")
        print("Example: uv run plot_single_anchor_measurements_by_orientation.py datapoints28oct.csv 3 0,0,0")
        print("Example: uv run plot_single_anchor_measurements_by_orientation.py datapoints28oct.csv all 120.0,180.0,0.0")
        print("Example: uv run plot_single_anchor_measurements_by_orientation.py datapoints28oct.csv 0 --raw")
        sys.exit(1)
    
    csv_file = Path(sys.argv[1])
    anchor_arg = sys.argv[2].lower()
    
    # Check for --raw flag
    use_raw = '--raw' in sys.argv or '-r' in sys.argv
    
    # Parse optional coordinate filter
    coord_filter: Optional[Tuple[float, float, float]] = None
    for arg in sys.argv[3:]:
        if arg not in ['--raw', '-r']:
            coord_str = arg
            try:
                coords = [float(x.strip()) for x in coord_str.split(',')]
                if len(coords) != 3:
                    raise ValueError("Must provide exactly 3 coordinates")
                coord_filter = (coords[0], coords[1], coords[2])
            except ValueError as e:
                if ',' in coord_str:  # Only show error if it looks like coordinates
                    print(f"Error: Invalid coordinate format '{coord_str}'. Expected format: x,y,z (e.g., 0,0,0 or 120.0,180.0,0.0)")
                    print(f"Details: {e}")
                    sys.exit(1)
            break
    
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
    
    # Apply coordinate filter if provided
    if coord_filter is not None:
        filter_x, filter_y, filter_z = coord_filter
        original_count = len(df)
        df_filtered = df[
            (df['ground_truth_x'] == filter_x) &
            (df['ground_truth_y'] == filter_y) &
            (df['ground_truth_z'] == filter_z)
        ]
        # Ensure it's a DataFrame (not a Series)
        if isinstance(df_filtered, pd.Series):
            df_filtered = df_filtered.to_frame().T
        df_filtered = df_filtered.copy()
        filtered_count = len(df_filtered)
        print(f"Filtered to coordinates ({filter_x}, {filter_y}, {filter_z}): {filtered_count} rows (from {original_count})")
        if filtered_count == 0:
            print(f"Warning: No data points found for coordinates ({filter_x}, {filter_y}, {filter_z})")
            sys.exit(1)
        df = df_filtered
    
    data_type = "raw" if use_raw else "filtered"
    if anchor_id is None:
        print(f"Analyzing {data_type} measurements from all anchors by orientation...")
    else:
        print(f"Analyzing {data_type} measurements from anchor {anchor_id} by orientation...")
    
    # Create visualizations colored by orientation
    create_visualizations_by_orientation(df, anchor_id, output_dir, coord_filter, use_raw)
    
    print(f"\nAnalysis complete! Results saved to {output_dir}")

if __name__ == "__main__":
    main()

