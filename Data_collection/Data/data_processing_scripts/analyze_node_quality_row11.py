import pandas as pd
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
from pathlib import Path
from typing import Dict, List

# Import the transformation functions from the localization package
import sys
sys.path.append(str(Path(__file__).parent.parent / 'packages'))
from localization_algos.edge_creation.transforms import ANCHOR_R

def extract_row_data(csv_path, row_index=9):
    """Extract data from specified row of the CSV file."""
    df = pd.read_csv(csv_path)

    # Row index in DataFrame (pandas is 0-indexed and there's a header)
    row_data = df.iloc[row_index]

    ground_truth = np.array([
        row_data['ground_truth_x'],
        row_data['ground_truth_y'],
        row_data['ground_truth_z']
    ])

    pgo_result = np.array([
        row_data['pgo_x'],
        row_data['pgo_y'],
        row_data['pgo_z']
    ])

    # Parse the binned data JSON
    binned_data = json.loads(row_data['binned_data_json'])

    return ground_truth, pgo_result, binned_data

def calculate_node_positions(binned_data):
    """
    Calculate position estimates for each node based on measurements.
    For each node, transform all measurements to global coordinates and average them.
    """
    # Define anchor positions (from Server_bring_up.md)
    anchor_positions = {
        0: np.array([480, 600, 0]),  # top-right
        1: np.array([0, 600, 0]),    # top-left
        2: np.array([480, 0, 0]),    # bottom-right
        3: np.array([0, 0, 0])       # bottom-left
    }

    node_positions = {}
    measurements = binned_data['measurements']

    for node_id_str, node_measurements in measurements.items():
        node_id = int(node_id_str)

        # Transform all measurements for this node to global coordinates
        phone_positions = []
        for local_vector in node_measurements:
            local_vec = np.array(local_vector)
            # Transform local vector to global coordinates
            global_vec = ANCHOR_R[node_id] @ local_vec
            # Add anchor position to get absolute phone position
            phone_pos = anchor_positions[node_id] + global_vec
            phone_positions.append(phone_pos)

        # Average the phone positions to get position estimate
        if phone_positions:
            avg_position = np.mean(phone_positions, axis=0)
            node_positions[node_id] = avg_position

    return node_positions

def plot_node_quality(ground_truth, pgo_result, node_positions, row_index):
    """
    Create plots showing the quality comparison between nodes, ground truth, and PGO.
    """
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

    # Colors for different nodes
    node_colors = {0: 'red', 1: 'blue', 2: 'green', 3: 'orange'}
    node_labels = {0: 'Node 0', 1: 'Node 1', 2: 'Node 2', 3: 'Node 3'}

    # Plot 1: XY positions
    ax1.scatter(ground_truth[0], ground_truth[1], color='black', marker='*', s=200,
                label='Ground Truth', zorder=5)
    ax1.scatter(pgo_result[0], pgo_result[1], color='purple', marker='s', s=150,
                label='PGO Result', zorder=4)

    for node_id, position in node_positions.items():
        ax1.scatter(position[0], position[1], color=node_colors[node_id],
                   marker='o', s=100, label=node_labels[node_id], alpha=0.8)

    ax1.set_xlabel('X Position (cm)')
    ax1.set_ylabel('Y Position (cm)')
    ax1.set_title('XY Positions: Ground Truth vs PGO vs Node Estimates')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax1.axis('equal')

    # Plot 2: XZ positions
    ax2.scatter(ground_truth[0], ground_truth[2], color='black', marker='*', s=200,
                label='Ground Truth', zorder=5)
    ax2.scatter(pgo_result[0], pgo_result[2], color='purple', marker='s', s=150,
                label='PGO Result', zorder=4)

    for node_id, position in node_positions.items():
        ax2.scatter(position[0], position[2], color=node_colors[node_id],
                   marker='o', s=100, label=node_labels[node_id], alpha=0.8)

    ax2.set_xlabel('X Position (cm)')
    ax2.set_ylabel('Z Position (cm)')
    ax2.set_title('XZ Positions: Ground Truth vs PGO vs Node Estimates')
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    # Plot 3: YZ positions
    ax3.scatter(ground_truth[1], ground_truth[2], color='black', marker='*', s=200,
                label='Ground Truth', zorder=5)
    ax3.scatter(pgo_result[1], pgo_result[2], color='purple', marker='s', s=150,
                label='PGO Result', zorder=4)

    for node_id, position in node_positions.items():
        ax3.scatter(position[1], position[2], color=node_colors[node_id],
                   marker='o', s=100, label=node_labels[node_id], alpha=0.8)

    ax3.set_xlabel('Y Position (cm)')
    ax3.set_ylabel('Z Position (cm)')
    ax3.set_title('YZ Positions: Ground Truth vs PGO vs Node Estimates')
    ax3.grid(True, alpha=0.3)
    ax3.legend()

    # Plot 4: Error comparison
    gt_x, gt_y, gt_z = ground_truth

    # Calculate errors for each node
    node_ids = []
    x_errors = []
    y_errors = []
    z_errors = []
    total_errors = []

    for node_id, position in node_positions.items():
        node_ids.append(node_id)
        x_err = position[0] - gt_x
        y_err = position[1] - gt_y
        z_err = position[2] - gt_z
        total_err = np.sqrt(x_err**2 + y_err**2 + z_err**2)

        x_errors.append(x_err)
        y_errors.append(y_err)
        z_errors.append(z_err)
        total_errors.append(total_err)

    # PGO errors
    pgo_x_err = pgo_result[0] - gt_x
    pgo_y_err = pgo_result[1] - gt_y
    pgo_z_err = pgo_result[2] - gt_z
    pgo_total_err = np.sqrt(pgo_x_err**2 + pgo_y_err**2 + pgo_z_err**2)

    x_pos = np.arange(len(node_ids))
    width = 0.25

    ax4.bar(x_pos - width, x_errors, width, label='X Error', color='lightcoral', alpha=0.7)
    ax4.bar(x_pos, y_errors, width, label='Y Error', color='lightblue', alpha=0.7)
    ax4.bar(x_pos + width, z_errors, width, label='Z Error', color='lightgreen', alpha=0.7)

    # Add PGO error bars
    ax4.axhline(y=pgo_x_err, color='red', linestyle='--', alpha=0.7, label=f'PGO X Error ({pgo_x_err:.1f})')
    ax4.axhline(y=pgo_y_err, color='blue', linestyle='--', alpha=0.7, label=f'PGO Y Error ({pgo_y_err:.1f})')
    ax4.axhline(y=pgo_z_err, color='orange', linestyle='--', alpha=0.7, label=f'PGO Z Error ({pgo_z_err:.1f})')

    ax4.set_xlabel('Node ID')
    ax4.set_ylabel('Error (cm)')
    ax4.set_title('Positioning Errors by Node')
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels([f'Node {i}' for i in node_ids])
    ax4.grid(True, alpha=0.3)
    ax4.legend()

    plt.tight_layout()

    # Save the plot
    output_path = Path(__file__).parent / 'Data' / f'node_quality_analysis_row{row_index + 1}.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Plot saved to: {output_path}")

    return fig

def print_analysis_summary(ground_truth, pgo_result, node_positions, row_index):
    """Print detailed analysis of the positioning quality."""
    print(f"\n=== Node Quality Analysis for Row {row_index + 1} ===")
    print(f"Ground Truth Position: ({ground_truth[0]:.1f}, {ground_truth[1]:.1f}, {ground_truth[2]:.1f})")
    print(f"PGO Result Position: ({pgo_result[0]:.1f}, {pgo_result[1]:.1f}, {pgo_result[2]:.1f})")

    pgo_error = np.sqrt(np.sum((pgo_result - ground_truth)**2))
    print(f"PGO Total Error: {pgo_error:.1f} cm")
    print("\nIndividual Node Analysis:")
    print("-" * 50)

    for node_id, position in node_positions.items():
        error = np.sqrt(np.sum((position - ground_truth)**2))
        x_err = position[0] - ground_truth[0]
        y_err = position[1] - ground_truth[1]
        z_err = position[2] - ground_truth[2]

        print(f"Node {node_id}:")
        print(f"  Position: ({position[0]:.1f}, {position[1]:.1f}, {position[2]:.1f})")
        print(f"  Errors: X={x_err:.1f}, Y={y_err:.1f}, Z={z_err:.1f}, Total={error:.1f} cm")

def create_detailed_measurement_plot(binned_data, node_positions, ground_truth, pgo_result, row_index):
    """Create plots showing measurements in both local and global coordinate systems."""
    # Define anchor positions (from Server_bring_up.md)
    anchor_positions = {
        0: np.array([480, 600, 0]),  # top-right
        1: np.array([0, 600, 0]),    # top-left
        2: np.array([480, 0, 0]),    # bottom-right
        3: np.array([0, 0, 0])       # bottom-left
    }

    # Create two figures: one for local coordinates, one for global
    fig_local, axes_local = plt.subplots(2, 2, figsize=(16, 12))
    fig_global, ax_global = plt.subplots(1, 1, figsize=(12, 10))

    axes_local = axes_local.flatten()
    measurements = binned_data['measurements']
    node_colors = {0: 'red', 1: 'blue', 2: 'green', 3: 'orange'}
    node_labels = {0: 'Node 0 (SW)', 1: 'Node 1 (SE)', 2: 'Node 2 (NW)', 3: 'Node 3 (NE)'}

    # Plot anchor positions and ground truth and PGO in global coordinates
    for anchor_id, pos in anchor_positions.items():
        ax_global.scatter(pos[0], pos[1], color='gray', marker='s', s=100,
                         label=f'Anchor {anchor_id}', zorder=1, alpha=0.7)

    ax_global.scatter(ground_truth[0], ground_truth[1], color='black', marker='*', s=300,
                     label='Ground Truth', zorder=10, edgecolors='white', linewidth=3)
    ax_global.scatter(pgo_result[0], pgo_result[1], color='purple', marker='s', s=250,
                     label='PGO Result', zorder=9, edgecolors='white', linewidth=3)

    for node_id in range(4):
        ax_local = axes_local[node_id]
        node_id_str = str(node_id)

        # Plot local coordinate system measurements
        if node_id_str in measurements:
            node_measurements = measurements[node_id_str]

            # Plot local coordinates (raw measurements)
            for i, local_vector in enumerate(node_measurements):
                local_vec = np.array(local_vector)
                ax_local.scatter(local_vec[0], local_vec[1], color=node_colors[node_id],
                               alpha=0.6, s=50, label=f'Measurement {i+1}')

            # Calculate and plot average in local coordinates
            if node_measurements:
                local_avg = np.mean([np.array(v) for v in node_measurements], axis=0)
                ax_local.scatter(local_avg[0], local_avg[1], color='black', marker='x', s=150,
                               label='Local Average', zorder=5)

            # Transform to global coordinates and plot on global plot
            # Each measurement gives us: phone_position = anchor_position + (ANCHOR_R[node_id] @ local_vector)
            for i, local_vector in enumerate(node_measurements):
                local_vec = np.array(local_vector)
                # Transform local vector to global coordinates
                global_vec = ANCHOR_R[node_id] @ local_vec
                # Add anchor position to get absolute phone position
                phone_position = anchor_positions[node_id] + global_vec

                ax_global.scatter(phone_position[0], phone_position[1], color=node_colors[node_id],
                                alpha=0.4, s=40, marker='o')

            # Plot node average in global coordinates
            if node_id in node_positions:
                avg_pos = node_positions[node_id]
                ax_global.scatter(avg_pos[0], avg_pos[1], color=node_colors[node_id],
                                marker='X', s=200, label=f'{node_labels[node_id]} Average',
                                zorder=7, edgecolors='white', linewidth=2)

        ax_local.set_xlabel('Local X Position (cm)')
        ax_local.set_ylabel('Local Y Position (cm)')
        ax_local.set_title(f'{node_labels[node_id]} - Local Coordinate System')
        ax_local.grid(True, alpha=0.3)
        ax_local.legend(loc='upper right')
        ax_local.axis('equal')

    # Finalize global coordinates plot
    ax_global.set_xlabel('Global X Position (cm)')
    ax_global.set_ylabel('Global Y Position (cm)')
    ax_global.set_title('All Nodes in Global Coordinate System\nGround Truth vs PGO vs Individual Node Measurements')
    ax_global.grid(True, alpha=0.3)
    ax_global.legend(loc='upper right', bbox_to_anchor=(1.0, 1.0))
    ax_global.axis('equal')

    # Save both plots
    plt.figure(fig_local.number)
    plt.tight_layout()
    output_path_local = Path(__file__).parent / 'Data' / f'local_measurements_row{row_index + 1}.png'
    plt.savefig(output_path_local, dpi=300, bbox_inches='tight')
    print(f"Local measurements plot saved to: {output_path_local}")

    plt.figure(fig_global.number)
    plt.tight_layout()
    output_path_global = Path(__file__).parent / 'Data' / f'global_measurements_row{row_index + 1}.png'
    plt.savefig(output_path_global, dpi=300, bbox_inches='tight')
    print(f"Global measurements plot saved to: {output_path_global}")

    # Close the figures to free memory
    plt.close(fig_local)
    plt.close(fig_global)

if __name__ == "__main__":
    # Path to the data file
    data_path = Path(__file__).parent / "Data" / "datapoints(unsure).csv"

    print(f"Analyzing data from: {data_path}")

    # Extract data from the row with ground truth (240.0, 300.0, 150.0) - index 3
    row_index = 3  # This corresponds to the row with the correct data points
    ground_truth, pgo_result, binned_data = extract_row_data(data_path, row_index)

    # Calculate node positions from measurements
    node_positions = calculate_node_positions(binned_data)

    # Create main analysis plot
    fig = plot_node_quality(ground_truth, pgo_result, node_positions, row_index)

    # Create detailed measurements plot
    create_detailed_measurement_plot(binned_data, node_positions, ground_truth, pgo_result, row_index)

    # Print analysis summary
    print_analysis_summary(ground_truth, pgo_result, node_positions, row_index)

    print("\nPlots generated successfully!")
    print(f"- node_quality_analysis_row{row_index + 1}.png: Main quality comparison")
    print(f"- local_measurements_row{row_index + 1}.png: Individual measurements in local coordinates")
    print(f"- global_measurements_row{row_index + 1}.png: All measurements transformed to global coordinates")
