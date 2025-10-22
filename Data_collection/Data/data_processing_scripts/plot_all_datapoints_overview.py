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
sys.path.append(str(Path(__file__).parent.parent.parent.parent / 'packages'))
from localization_algos.edge_creation.transforms import ANCHOR_R

def plot_all_datapoints_overview(csv_path):
    """Create a comprehensive plot showing all data points from the CSV file."""
    # Define anchor positions (from Server_bring_up.md)
    anchor_positions = {
        0: np.array([480, 600, 0]),  # top-right
        1: np.array([0, 600, 0]),    # top-left
        2: np.array([480, 0, 0]),    # bottom-right
        3: np.array([0, 0, 0])       # bottom-left
    }

    # Read CSV file
    df = pd.read_csv(csv_path)

    # Create figure
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))

    # Colors for different nodes
    node_colors = {0: 'red', 1: 'blue', 2: 'green', 3: 'orange'}
    node_labels = {0: 'Node 0', 1: 'Node 1', 2: 'Node 2', 3: 'Node 3'}

    # Plot anchor positions
    for anchor_id, pos in anchor_positions.items():
        ax.scatter(pos[0], pos[1], color='gray', marker='s', s=200,
                  label=f'Anchor {anchor_id}', zorder=1, alpha=0.8, edgecolors='black', linewidth=2)

    # Process each row in the CSV
    for idx, row in df.iterrows():
        row_num = idx + 1  # 1-indexed row number for labeling

        # Extract ground truth and PGO result
        ground_truth = np.array([row['ground_truth_x'], row['ground_truth_y'], row['ground_truth_z']])
        pgo_result = np.array([row['pgo_x'], row['pgo_y'], row['pgo_z']])

        # Plot ground truth position
        ax.scatter(ground_truth[0], ground_truth[1], color='black', marker='*', s=200,
                  zorder=8, edgecolors='white', linewidth=2)

        # Plot PGO result
        ax.scatter(pgo_result[0], pgo_result[1], color='purple', marker='s', s=150,
                  zorder=7, edgecolors='white', linewidth=2)

        # Parse measurements and plot them
        try:
            binned_data = json.loads(row['binned_data_json'])
            measurements = binned_data['measurements']

            for node_id_str, node_measurements in measurements.items():
                node_id = int(node_id_str)

                # Transform measurements to global coordinates and plot
                for measurement in node_measurements:
                    local_vec = np.array(measurement)
                    global_vec = ANCHOR_R[node_id] @ local_vec
                    phone_pos = anchor_positions[node_id] + global_vec

                    ax.scatter(phone_pos[0], phone_pos[1], color=node_colors[node_id],
                              alpha=0.3, s=30, marker='o', zorder=2)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not parse measurements for row {row_num}: {e}")
            continue

    # Add legend
    legend_elements = [
        plt.Line2D([0], [0], marker='*', color='black', markerfacecolor='black',
                  markersize=15, label='Ground Truth', linestyle='None'),
        plt.Line2D([0], [0], marker='s', color='purple', markerfacecolor='purple',
                  markersize=12, label='PGO Result', linestyle='None'),
        plt.Line2D([0], [0], marker='s', color='gray', markerfacecolor='gray',
                  markersize=12, label='Anchors', linestyle='None'),
    ]

    # Add node measurement legends
    for node_id in [0, 1, 2, 3]:
        legend_elements.append(
            plt.Line2D([0], [0], marker='o', color=node_colors[node_id],
                      markerfacecolor=node_colors[node_id], markersize=8,
                      label=f'{node_labels[node_id]} Measurements', linestyle='None', alpha=0.6)
        )

    ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.0, 1.0))

    # Formatting
    ax.set_xlabel('Global X Position (cm)')
    ax.set_ylabel('Global Y Position (cm)')
    ax.set_title('All Data Points Overview\nGround Truth, PGO Results, and Individual Node Measurements')
    ax.grid(True, alpha=0.3)
    ax.axis('equal')

    # Save the plot
    output_path = Path(__file__).parent.parent / 'all_datapoints_overview.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"All datapoints overview plot saved to: {output_path}")

    return fig

def create_error_summary_plot(csv_path):
    """Create a summary plot showing errors for all data points."""
    # Define anchor positions
    anchor_positions = {
        0: np.array([480, 600, 0]),  # top-right
        1: np.array([0, 600, 0]),    # top-left
        2: np.array([480, 0, 0]),    # bottom-right
        3: np.array([0, 0, 0])       # bottom-left
    }

    # Read CSV file
    df = pd.read_csv(csv_path)

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()

    row_nums = []
    pgo_errors = []
    node_errors = {0: [], 1: [], 2: [], 3: []}

    # Process each row
    for idx, row in df.iterrows():
        row_num = idx + 1
        row_nums.append(row_num)

        # Calculate PGO error
        ground_truth = np.array([row['ground_truth_x'], row['ground_truth_y'], row['ground_truth_z']])
        pgo_result = np.array([row['pgo_x'], row['pgo_y'], row['pgo_z']])
        pgo_error = np.sqrt(np.sum((pgo_result - ground_truth)**2))
        pgo_errors.append(pgo_error)

        # Calculate individual node errors
        try:
            binned_data = json.loads(row['binned_data_json'])
            measurements = binned_data['measurements']

            for node_id_str, node_measurements in measurements.items():
                node_id = int(node_id_str)

                # Calculate average position for this node
                phone_positions = []
                for measurement in node_measurements:
                    local_vec = np.array(measurement)
                    global_vec = ANCHOR_R[node_id] @ local_vec
                    phone_pos = anchor_positions[node_id] + global_vec
                    phone_positions.append(phone_pos)

                if phone_positions:
                    avg_pos = np.mean(phone_positions, axis=0)
                    node_error = np.sqrt(np.sum((avg_pos - ground_truth)**2))
                    node_errors[node_id].append(node_error)
                else:
                    node_errors[node_id].append(np.nan)

        except (json.JSONDecodeError, KeyError):
            for node_id in [0, 1, 2, 3]:
                node_errors[node_id].append(np.nan)

    # Plot 1: PGO error over time
    axes[0].plot(row_nums, pgo_errors, 'o-', color='purple', linewidth=2, markersize=8)
    axes[0].set_xlabel('Row Number')
    axes[0].set_ylabel('Error (cm)')
    axes[0].set_title('PGO Positioning Error by Row')
    axes[0].set_ylim(0, 400)
    axes[0].grid(True, alpha=0.3)

    # Plot 2: Individual node errors
    node_colors = {0: 'red', 1: 'blue', 2: 'green', 3: 'orange'}
    for node_id in [0, 1, 2, 3]:
        valid_errors = [e for e in node_errors[node_id] if not np.isnan(e)]
        valid_rows = [row_nums[i] for i, e in enumerate(node_errors[node_id]) if not np.isnan(e)]
        if valid_errors:
            axes[1].plot(valid_rows, valid_errors, 'o-', color=node_colors[node_id],
                        linewidth=2, markersize=6, label=f'Node {node_id}')

    axes[1].set_xlabel('Row Number')
    axes[1].set_ylabel('Error (cm)')
    axes[1].set_title('Individual Node Positioning Error by Row')
    axes[1].set_ylim(0, 400)
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    # Plot 3: Error comparison box plot
    all_pgo_errors = [e for e in pgo_errors if not np.isnan(e)]
    node_error_lists = []
    node_labels = []

    for node_id in [0, 1, 2, 3]:
        valid_errors = [e for e in node_errors[node_id] if not np.isnan(e)]
        if valid_errors:
            node_error_lists.append(valid_errors)
            node_labels.append(f'Node {node_id}')

    if node_error_lists:
        bp = axes[2].boxplot(node_error_lists, labels=node_labels, patch_artist=True)
        for patch, color in zip(bp['boxes'], ['red', 'blue', 'green', 'orange'][:len(node_error_lists)]):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        # Add PGO error line
        axes[2].axhline(y=np.mean(all_pgo_errors), color='purple', linestyle='--',
                       linewidth=2, label=f'PGO Mean: {np.mean(all_pgo_errors):.1f} cm')
        axes[2].legend()

    axes[2].set_ylabel('Error (cm)')
    axes[2].set_title('Error Distribution Comparison')
    axes[2].grid(True, alpha=0.3)

    # Plot 4: Error statistics summary
    axes[3].axis('off')

    stats_text = f"Dataset Summary (10 data points):\n\n"
    stats_text += f"PGO Errors:\n"
    stats_text += f"  Mean: {np.mean(pgo_errors):.1f} cm\n"
    stats_text += f"  Std: {np.std(pgo_errors):.1f} cm\n"
    stats_text += f"  Min: {np.min(pgo_errors):.1f} cm\n"
    stats_text += f"  Max: {np.max(pgo_errors):.1f} cm\n\n"

    for node_id in [0, 1, 2, 3]:
        valid_errors = [e for e in node_errors[node_id] if not np.isnan(e)]
        if valid_errors:
            stats_text += f"Node {node_id} Errors:\n"
            stats_text += f"  Mean: {np.mean(valid_errors):.1f} cm\n"
            stats_text += f"  Std: {np.std(valid_errors):.1f} cm\n"
            stats_text += f"  Available: {len(valid_errors)}/10 points\n\n"

    axes[3].text(0.05, 0.95, stats_text, transform=axes[3].transAxes,
                fontsize=10, verticalalignment='top', fontfamily='monospace')

    plt.tight_layout()

    # Save the error summary plot
    output_path = Path(__file__).parent.parent / 'all_datapoints_error_summary.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Error summary plot saved to: {output_path}")

    return fig

if __name__ == "__main__":
    # Path to the data file
    data_path = Path(__file__).parent.parent / "datapoints(unsure).csv"

    print(f"Creating comprehensive overview from: {data_path}")

    # Create the main overview plot
    fig_overview = plot_all_datapoints_overview(data_path)

    # Create the error summary plot
    fig_errors = create_error_summary_plot(data_path)

    print("\nPlots generated successfully!")
    print("- all_datapoints_overview.png: Comprehensive view of all measurements")
    print("- all_datapoints_error_summary.png: Error analysis across all data points")
