#!/usr/bin/env python3
"""
Single Anchor Analysis for Middle Point (120, 180)

This script creates a plot showing how bad single anchor localization is
for just the middle point position. It shows:
1. The worst performing single anchor
2. All individual position estimates (not averaged)
3. Range bars showing min/max spread instead of standard deviation
4. Average error and standard deviation in the legend
"""

import csv
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import sys
import os

# Add packages to path
sys.path.append('/Users/hongyilin/projects/uwb-localization-mesh/packages')
sys.path.append('/Users/hongyilin/projects/uwb-localization-mesh')

from packages.datatypes.datatypes import AnchorConfig
from packages.localization_algos.edge_creation.transforms import create_relative_measurement, ANCHOR_R

# Default anchor positions (from datatypes README)
DEFAULT_ANCHOR_POSITIONS = {
    0: np.array([480, 600, 0]),  # top-right
    1: np.array([0, 600, 0]),    # top-left  
    2: np.array([480, 0, 0]),    # bottom-right
    3: np.array([0, 0, 0])       # bottom-left
}

# Target position - changed to (0, 0) to check for wider range
TARGET_POINT = (0.0, 0.0)

def load_data(csv_path: str) -> List[Dict]:
    """Load and parse the CSV data."""
    data = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Parse the raw_binned_data_json (non-filtered version)
                raw_data = json.loads(row['raw_binned_data_json'])
                row['raw_data'] = raw_data
                
                # Parse numeric fields
                row['ground_truth_x'] = float(row['ground_truth_x'])
                row['ground_truth_y'] = float(row['ground_truth_y'])
                row['ground_truth_z'] = float(row['ground_truth_z'])
                row['pgo_x'] = float(row['pgo_x'])
                row['pgo_y'] = float(row['pgo_y'])
                row['pgo_z'] = float(row['pgo_z'])
                
                data.append(row)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"Warning: Skipping row due to parsing error: {e}")
                continue
    return data

def estimate_positions_single_anchor(measurements: Dict[str, List[List[float]]], 
                                   anchor_id: int,
                                   ground_truth: Tuple[float, float]) -> List[np.ndarray]:
    """
    Estimate multiple positions using a single anchor to capture measurement variability.
    For 1-anchor case, we transform each measurement to global coordinates and place
    the phone at the measured distance in the direction of ground truth.
    This captures the variability within the bin for proper range calculation.
    """
    anchor_id_str = str(anchor_id)
    if anchor_id_str not in measurements:
        return []
    
    vectors = measurements[anchor_id_str]
    if not vectors:
        return []
    
    # Transform measurements to global coordinates
    global_vectors = []
    for vector in vectors:
        local_vector = np.array(vector)
        try:
            _, _, global_vector = create_relative_measurement(anchor_id, 0, local_vector)
            global_vectors.append(global_vector)
        except ValueError:
            continue
    
    if not global_vectors:
        return []
    
    # Estimate position for each measurement to capture variability
    anchor_pos_2d = DEFAULT_ANCHOR_POSITIONS[anchor_id][:2]
    ground_truth_2d = np.array(ground_truth)
    
    # Direction from anchor to ground truth
    direction = ground_truth_2d - anchor_pos_2d
    if np.linalg.norm(direction) > 0:
        direction = direction / np.linalg.norm(direction)
    else:
        # If ground truth is at anchor position, use arbitrary direction
        direction = np.array([1.0, 0.0])
    
    # Create position estimates for each measurement
    estimated_positions = []
    for global_vector in global_vectors:
        distance = np.linalg.norm(global_vector)
        # Place phone at measured distance in ground truth direction
        estimated_pos = anchor_pos_2d + direction * distance
        estimated_positions.append(estimated_pos)
    
    return estimated_positions

def analyze_single_anchor_performance(data_group: List[Dict], 
                                    ground_truth: Tuple[float, float]) -> Dict[int, Dict]:
    """Analyze single anchor performance for each available anchor."""
    
    # Get all available anchors from the data
    all_available_anchors = set()
    for row in data_group:
        available_anchors = list(map(int, row['raw_data']['measurements'].keys()))
        all_available_anchors.update(available_anchors)
    
    all_anchor_ids = sorted(list(all_available_anchors))
    print(f"Available anchors for target point: {all_anchor_ids}")
    
    anchor_performance = {}
    
    for anchor_id in all_anchor_ids:
        all_positions = []
        all_errors = []
        
        for row in data_group:
            available_anchors = list(map(int, row['raw_data']['measurements'].keys()))
            if anchor_id not in available_anchors:
                continue
            
            pos_estimates = estimate_positions_single_anchor(
                row['raw_data']['measurements'], 
                anchor_id, 
                ground_truth
            )
            
            for pos_estimate in pos_estimates:
                all_positions.append(pos_estimate)
                error = np.sqrt((pos_estimate[0] - ground_truth[0])**2 + 
                               (pos_estimate[1] - ground_truth[1])**2)
                all_errors.append(error)
        
        if all_positions and all_errors:
            positions_array = np.array(all_positions)
            
            # Calculate statistics
            mean_x = np.mean(positions_array[:, 0])
            mean_y = np.mean(positions_array[:, 1])
            min_x = np.min(positions_array[:, 0])
            max_x = np.max(positions_array[:, 0])
            min_y = np.min(positions_array[:, 1])
            max_y = np.max(positions_array[:, 1])
            
            avg_error = np.mean(all_errors)
            std_error = np.std(all_errors)
            
            anchor_performance[anchor_id] = {
                'positions': positions_array,
                'mean_pos': (mean_x, mean_y),
                'x_range': (min_x, max_x),
                'y_range': (min_y, max_y),
                'avg_error': avg_error,
                'std_error': std_error,
                'num_estimates': len(all_positions)
            }
            
            print(f"Anchor {anchor_id}: {len(all_positions)} estimates, avg error: {avg_error:.1f}±{std_error:.1f}cm")
            print(f"  X range: {min_x:.1f} to {max_x:.1f} cm (span: {max_x-min_x:.1f}cm)")
            print(f"  Y range: {min_y:.1f} to {max_y:.1f} cm (span: {max_y-min_y:.1f}cm)")
    
    return anchor_performance

def create_single_anchor_plot(orientation: str, data: List[Dict], output_dir: str):
    """Create a plot showing single anchor performance for the target point."""
    
    # Filter data for target point and specified orientation
    target_point_data = []
    for row in data:
        if (abs(row['ground_truth_x'] - TARGET_POINT[0]) < 0.1 and 
            abs(row['ground_truth_y'] - TARGET_POINT[1]) < 0.1 and
            row['orientation'] == orientation):
            target_point_data.append(row)
    
    if not target_point_data:
        print(f"Warning: No data found for target point {TARGET_POINT} with orientation {orientation}")
        return
    
    print(f"\nProcessing target point {TARGET_POINT} for orientation {orientation}:")
    print(f"Found {len(target_point_data)} data points")
    
    # Analyze single anchor performance
    anchor_performance = analyze_single_anchor_performance(target_point_data, TARGET_POINT)
    
    if not anchor_performance:
        print("No anchor performance data available")
        return
    
    # Find the worst performing anchor
    worst_anchor = max(anchor_performance.keys(), 
                      key=lambda aid: anchor_performance[aid]['avg_error'])
    worst_perf = anchor_performance[worst_anchor]
    
    print(f"\nWorst performing anchor: {worst_anchor} (avg error: {worst_perf['avg_error']:.1f}cm)")
    
    # Set up the plot
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Plot anchor positions
    for anchor_id, pos in DEFAULT_ANCHOR_POSITIONS.items():
        color = 'red' if anchor_id == worst_anchor else 'lightcoral'
        size = 15 if anchor_id == worst_anchor else 10
        ax.plot(pos[0], pos[1], 's', markersize=size, color=color, 
                label='Worst Anchor' if anchor_id == worst_anchor else '', zorder=10)
        ax.annotate(f'A{anchor_id}', (pos[0], pos[1]), xytext=(8, 8), 
                   textcoords='offset points', fontsize=12, color=color, 
                   fontweight='bold' if anchor_id == worst_anchor else 'normal', zorder=11)
    
    # Plot ground truth position
    ax.plot(TARGET_POINT[0], TARGET_POINT[1], 'ko', markersize=10, 
            label='Ground Truth', zorder=8)
    ax.annotate(f'GT({TARGET_POINT[0]:.0f},{TARGET_POINT[1]:.0f})', 
               (TARGET_POINT[0], TARGET_POINT[1]), xytext=(10, -20), 
               textcoords='offset points', fontsize=12, 
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.9),
               zorder=9)
    
    # Plot all individual measurements from raw data (like in overview plot)
    node_colors = {0: 'red', 1: 'blue', 2: 'lightgreen', 3: 'orange'}
    node_labels = {0: 'Node 0', 1: 'Node 1', 2: 'Node 2', 3: 'Node 3'}
    
    for row in target_point_data:
        try:
            measurements = row['raw_data']['measurements']
            
            for node_id_str, node_measurements in measurements.items():
                node_id = int(node_id_str)
                
                # Transform measurements to global coordinates and plot
                for measurement in node_measurements:
                    local_vec = np.array(measurement)
                    global_vec = ANCHOR_R[node_id] @ local_vec
                    phone_pos = DEFAULT_ANCHOR_POSITIONS[node_id] + global_vec
                    
                    # Highlight worst anchor measurements
                    alpha = 0.8 if node_id == worst_anchor else 0.3
                    size = 40 if node_id == worst_anchor else 20
                    zorder = 6 if node_id == worst_anchor else 4
                    
                    ax.scatter(phone_pos[0], phone_pos[1], 
                              color=node_colors[node_id], alpha=alpha, s=size, 
                              zorder=zorder)
        
        except (KeyError, ValueError) as e:
            print(f"Warning: Could not parse measurements: {e}")
            continue
    
    # Add legend entries for measurements
    legend_elements = []
    for node_id in sorted(node_colors.keys()):
        if any(str(node_id) in row['raw_data']['measurements'] for row in target_point_data):
            alpha = 0.8 if node_id == worst_anchor else 0.6
            label_suffix = ' (Worst)' if node_id == worst_anchor else ''
            legend_elements.append(
                plt.Line2D([0], [0], marker='o', color=node_colors[node_id],
                          markerfacecolor=node_colors[node_id], markersize=8,
                          label=f'{node_labels[node_id]} Measurements{label_suffix}', 
                          linestyle='None', alpha=alpha)
            )
    
    # Plot mean position with range bars (not standard deviation)
    mean_x, mean_y = worst_perf['mean_pos']
    min_x, max_x = worst_perf['x_range']
    min_y, max_y = worst_perf['y_range']
    
    # Calculate range extents
    x_range_extent = max_x - min_x
    y_range_extent = max_y - min_y
    
    # Plot range bars showing full spread of ALL individual measurements (not averages)
    # This shows the complete min/max range across all bins for this position
    ax.errorbar(mean_x, mean_y, 
               xerr=[[mean_x - min_x], [max_x - mean_x]], 
               yerr=[[mean_y - min_y], [max_y - mean_y]], 
               fmt='D', markersize=8, color='red', 
               capsize=6, capthick=2, elinewidth=2,
               label=f'Mean ± Complete Range (Anchor {worst_anchor})', zorder=7)
    
    # Add error statistics text
    stats_text = (f"Single Anchor {worst_anchor} Analysis:\n"
                 f"• {worst_perf['num_estimates']} position estimates\n"
                 f"• Avg Error: {worst_perf['avg_error']:.1f} ± {worst_perf['std_error']:.1f} cm\n"
                 f"• X Range: {x_range_extent:.1f} cm\n"
                 f"• Y Range: {y_range_extent:.1f} cm")
    
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=11,
            verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', 
            facecolor='lightgray', alpha=0.9))
    
    # Formatting
    ax.set_xlabel('X Position (cm)', fontsize=14)
    ax.set_ylabel('Y Position (cm)', fontsize=14)
    ax.set_title(f'Single Anchor Performance (Raw Data) - Position {TARGET_POINT} - Orientation {orientation}\n'
                f'Worst Case: Anchor {worst_anchor} (Avg Error: {worst_perf["avg_error"]:.1f}cm)', 
                fontsize=16)
    ax.grid(True, alpha=0.3)
    
    # Create combined legend
    anchor_legend = ax.get_legend_handles_labels()
    all_legend_elements = anchor_legend[0] + legend_elements
    all_legend_labels = anchor_legend[1] + [elem.get_label() for elem in legend_elements]
    ax.legend(all_legend_elements, all_legend_labels, loc='upper right', fontsize=10)
    
    # Set equal aspect ratio and fixed limits to avoid text blocking
    ax.set_aspect('equal')
    
    # Set fixed plot limits as requested
    ax.set_xlim(0, 800)
    ax.set_ylim(0, 700)
    
    # Save plot
    output_path = os.path.join(output_dir, f'single_anchor_position_0_0_raw_orientation_{orientation}.png')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"\nSaved single anchor plot (raw data) for orientation {orientation} to {output_path}")

def main():
    """Main function to generate single anchor analysis for target point."""
    
    # Paths
    csv_path = '/Users/hongyilin/projects/uwb-localization-mesh/Data_collection/Data/28oct/datapoints28oct.csv'
    output_dir = '/Users/hongyilin/projects/uwb-localization-mesh/Data_collection/Data/28oct'
    
    print("Loading data...")
    data = load_data(csv_path)
    print(f"Loaded {len(data)} data points")
    
    # Get unique orientations
    orientations = sorted(set(row['orientation'] for row in data))
    print(f"Found orientations: {orientations}")
    
    # Generate single anchor plot for each orientation
    for orientation in orientations:
        print(f"\n{'='*60}")
        print(f"Generating single anchor analysis for orientation {orientation}...")
        print(f"{'='*60}")
        create_single_anchor_plot(orientation, data, output_dir)
    
    print(f"\n{'='*60}")
    print(f"All single anchor plots generated successfully in {output_dir}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
