import pandas as pd
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
from pathlib import Path
from typing import Dict, List
import sys

# Import the transformation functions from the localization package
sys.path.append(str(Path(__file__).parent.parent.parent.parent / 'packages'))
from localization_algos.edge_creation.transforms import ANCHOR_R

def plot_all_datapoints_overview(csv_path, position_filter=None):
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

    # Filter by position if specified
    if position_filter:
        df = df[df['orientation'] == position_filter]
        if df.empty:
            print(f"No data found for position {position_filter}")
            return None

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

        # Parse filtered measurements and plot them
        try:
            binned_data = json.loads(row['filtered_binned_data_json'])
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
    ax.set_title('All Data Points Overview\nGround Truth, PGO Results (from Filtered Data), and Filtered Node Measurements')
    ax.grid(True, alpha=0.3)
    ax.axis('equal')

    # Save the plot
    output_path = Path(__file__).parent.parent / 'all_datapoints_overview.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"All datapoints overview plot saved to: {output_path}")

    return fig

def plot_filtering_metrics(csv_path, position_filter=None):
    """Create a plot showing filtering metrics over time."""
    # Read CSV file
    df = pd.read_csv(csv_path)

    # Filter by position if specified
    if position_filter:
        df = df[df['orientation'] == position_filter]
        if df.empty:
            print(f"No data found for position {position_filter}")
            return None

    # Create figure with subplots for different metrics
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    fig.suptitle('Filtering Metrics Over Time', fontsize=16)

    # Row numbers for x-axis
    row_nums = range(1, len(df) + 1)

    # Plot metrics
    axes[0].plot(row_nums, df['total_measurements'], 'b-', label='Total Measurements', linewidth=2)
    axes[0].plot(row_nums, df['rejected_measurements'], 'r-', label='Rejected Measurements', linewidth=2)
    axes[0].set_ylabel('Count')
    axes[0].set_title('Measurement Counts')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(row_nums, df['late_drops'], 'orange', label='Late Drops', linewidth=2)
    axes[1].set_ylabel('Count')
    axes[1].set_title('Late Drops (Measurements Too Old)')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    # Calculate rejection rate
    rejection_rate = df['rejected_measurements'] / df['total_measurements'] * 100
    axes[2].plot(row_nums, rejection_rate, 'purple', linewidth=2)
    axes[2].set_ylabel('Rejection Rate (%)')
    axes[2].set_xlabel('Data Point Number')
    axes[2].set_title('Measurement Rejection Rate')
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()

    # Save the plot
    output_path = Path(__file__).parent.parent / 'filtering_metrics.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Filtering metrics plot saved to: {output_path}")

    return fig

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Generate data processing plots')
    parser.add_argument('csv_path', help='Path to the CSV file')
    parser.add_argument('--position', '-p', help='Filter by position (A, B, C, etc.)', default=None)

    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"CSV file not found: {csv_path}")
        sys.exit(1)

    print(f"Processing {csv_path} with position filter: {args.position}")

    # Generate plots
    fig1 = plot_all_datapoints_overview(str(csv_path), args.position)
    fig2 = plot_filtering_metrics(str(csv_path), args.position)

    if fig1 is not None and fig2 is not None:
        print("Plots generated successfully!")
    else:
        print("No data found for the specified filter")
