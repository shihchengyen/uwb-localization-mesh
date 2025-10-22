import pandas as pd
import json
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Import the transformation functions from the localization package
import sys
sys.path.append(str(Path(__file__).parent.parent / 'packages'))
from localization_algos.edge_creation.transforms import ANCHOR_R

def load_and_plot_data_with_anchors(csv_path):
    """
    Load data from CSV and create plots comparing ground truth vs PGO positions
    with individual anchor measurements in global coordinates.
    """
    # Define anchor positions (from Server_bring_up.md)
    anchor_positions = {
        0: np.array([480, 600, 0]),  # top-right
        1: np.array([0, 600, 0]),    # top-left
        2: np.array([480, 0, 0]),    # bottom-right
        3: np.array([0, 0, 0])       # bottom-left
    }

    # Read CSV file
    df = pd.read_csv(csv_path)

    # Extract relevant columns
    ground_truth_x = df['ground_truth_x'].values
    ground_truth_y = df['ground_truth_y'].values
    pgo_x = df['pgo_x'].values
    pgo_y = df['pgo_y'].values

    # Create figure with 2 subplots (X and Y comparisons)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))

    # Node colors for anchor measurements
    node_colors = {0: 'red', 1: 'blue', 2: 'green', 3: 'orange'}

    # Plot 1: Ground truth X vs PGO X with individual anchor measurements
    # First plot individual anchor-derived X positions
    for idx, row in df.iterrows():
        gt_x = row['ground_truth_x']
        pgo_x_val = row['pgo_x']

        # Parse measurements for this row
        try:
            binned_data = json.loads(row['binned_data_json'])
            measurements = binned_data['measurements']

            for node_id_str, node_measurements in measurements.items():
                node_id = int(node_id_str)

                # Calculate phone positions from anchor measurements
                for measurement in node_measurements:
                    local_vec = np.array(measurement)
                    # Transform local vector to global coordinates
                    global_vec = ANCHOR_R[node_id] @ local_vec
                    # Add anchor position to get absolute phone position
                    phone_pos = anchor_positions[node_id] + global_vec

                    # Plot X coordinate
                    ax1.scatter(gt_x, phone_pos[0], color=node_colors[node_id],
                              alpha=0.3, s=20, marker='o')

        except (json.JSONDecodeError, KeyError):
            continue

    # Plot PGO results
    ax1.scatter(ground_truth_x, pgo_x, alpha=0.8, color='purple', s=60, marker='s',
               label='PGO Results', zorder=5)

    # Plot perfect correlation line
    all_x = np.concatenate([ground_truth_x, pgo_x])
    x_range = [all_x.min(), all_x.max()]
    ax1.plot(x_range, x_range, 'r--', alpha=0.7, label='Perfect correlation', linewidth=2)

    ax1.set_xlabel('Ground Truth X (cm)')
    ax1.set_ylabel('Estimated X (cm)')
    ax1.set_title('Ground Truth X vs Estimated X\n(PGO + Individual Anchor Measurements)')
    ax1.grid(True, alpha=0.3)

    # Create legend elements
    legend_elements = [
        plt.Line2D([0], [0], marker='s', color='purple', markerfacecolor='purple',
                  markersize=10, label='PGO Results', linestyle='None'),
        plt.Line2D([0], [0], marker='o', color='red', markerfacecolor='red',
                  markersize=6, label='Anchor 0 Measurements', linestyle='None', alpha=0.6),
        plt.Line2D([0], [0], marker='o', color='blue', markerfacecolor='blue',
                  markersize=6, label='Anchor 1 Measurements', linestyle='None', alpha=0.6),
        plt.Line2D([0], [0], marker='o', color='green', markerfacecolor='green',
                  markersize=6, label='Anchor 2 Measurements', linestyle='None', alpha=0.6),
        plt.Line2D([0], [0], marker='o', color='orange', markerfacecolor='orange',
                  markersize=6, label='Anchor 3 Measurements', linestyle='None', alpha=0.6),
        plt.Line2D([0], [0], color='red', linestyle='--', linewidth=2, label='Perfect correlation')
    ]
    ax1.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.02, 1.0))

    # Plot 2: Ground truth Y vs PGO Y with individual anchor measurements
    # First plot individual anchor-derived Y positions
    for idx, row in df.iterrows():
        gt_y = row['ground_truth_y']
        pgo_y_val = row['pgo_y']

        # Parse measurements for this row
        try:
            binned_data = json.loads(row['binned_data_json'])
            measurements = binned_data['measurements']

            for node_id_str, node_measurements in measurements.items():
                node_id = int(node_id_str)

                # Calculate phone positions from anchor measurements
                for measurement in node_measurements:
                    local_vec = np.array(measurement)
                    # Transform local vector to global coordinates
                    global_vec = ANCHOR_R[node_id] @ local_vec
                    # Add anchor position to get absolute phone position
                    phone_pos = anchor_positions[node_id] + global_vec

                    # Plot Y coordinate
                    ax2.scatter(gt_y, phone_pos[1], color=node_colors[node_id],
                              alpha=0.3, s=20, marker='o')

        except (json.JSONDecodeError, KeyError):
            continue

    # Plot PGO results
    ax2.scatter(ground_truth_y, pgo_y, alpha=0.8, color='purple', s=60, marker='s',
               label='PGO Results', zorder=5)

    # Plot perfect correlation line
    all_y = np.concatenate([ground_truth_y, pgo_y])
    y_range = [all_y.min(), all_y.max()]
    ax2.plot(y_range, y_range, 'r--', alpha=0.7, label='Perfect correlation', linewidth=2)

    ax2.set_xlabel('Ground Truth Y (cm)')
    ax2.set_ylabel('Estimated Y (cm)')
    ax2.set_title('Ground Truth Y vs Estimated Y\n(PGO + Individual Anchor Measurements)')
    ax2.grid(True, alpha=0.3)

    # Add legend to second plot too
    ax2.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.02, 1.0))

    plt.tight_layout()

    # Save the plot
    output_path = csv_path.parent / 'ground_truth_vs_pgo_with_anchors.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Plot saved to: {output_path}")

    # Print some statistics
    print("\n=== Statistics ===")
    print(f"Number of data points: {len(df)}")
    print(f"Ground Truth X range: {ground_truth_x.min():.2f} to {ground_truth_x.max():.2f}")
    print(f"Ground Truth Y range: {ground_truth_y.min():.2f} to {ground_truth_y.max():.2f}")
    print(f"PGO X range: {pgo_x.min():.2f} to {pgo_x.max():.2f}")
    print(f"PGO Y range: {pgo_y.min():.2f} to {pgo_y.max():.2f}")

    error_x = pgo_x - ground_truth_x
    error_y = pgo_y - ground_truth_y
    total_error = np.sqrt(error_x**2 + error_y**2)

    print(f"Mean X error: {error_x.mean():.2f}")
    print(f"Mean Y error: {error_y.mean():.2f}")
    print(f"Mean total error: {total_error.mean():.2f}")
    print(f"Std X error: {error_x.std():.2f}")
    print(f"Std Y error: {error_y.std():.2f}")
    print(f"Std total error: {total_error.std():.2f}")

    return fig, df

def create_individual_plots(csv_path):
    """
    Create separate individual plots for better detail.
    """
    df = pd.read_csv(csv_path)
    ground_truth_x = df['ground_truth_x'].values
    ground_truth_y = df['ground_truth_y'].values
    pgo_x = df['pgo_x'].values
    pgo_y = df['pgo_y'].values

    # Individual X comparison
    plt.figure(figsize=(10, 8))
    plt.scatter(ground_truth_x, pgo_x, alpha=0.7, color='blue', s=50)
    plt.plot([ground_truth_x.min(), ground_truth_x.max()],
             [ground_truth_x.min(), ground_truth_x.max()],
             'r--', alpha=0.7, label='Perfect correlation')

    # Add point labels
    for i, (gt_x, p_x) in enumerate(zip(ground_truth_x, pgo_x)):
        plt.annotate(f'{i+1}', (gt_x, p_x), xytext=(5, 5), textcoords='offset points', fontsize=8)

    plt.xlabel('Ground Truth X')
    plt.ylabel('PGO X')
    plt.title('Ground Truth X vs PGO X (Detailed)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(csv_path.parent / 'x_comparison_detailed.png', dpi=300, bbox_inches='tight')
    plt.close()

    # Individual Y comparison
    plt.figure(figsize=(10, 8))
    plt.scatter(ground_truth_y, pgo_y, alpha=0.7, color='green', s=50)
    plt.plot([ground_truth_y.min(), ground_truth_y.max()],
             [ground_truth_y.min(), ground_truth_y.max()],
             'r--', alpha=0.7, label='Perfect correlation')

    # Add point labels
    for i, (gt_y, p_y) in enumerate(zip(ground_truth_y, pgo_y)):
        plt.annotate(f'{i+1}', (gt_y, p_y), xytext=(5, 5), textcoords='offset points', fontsize=8)

    plt.xlabel('Ground Truth Y')
    plt.ylabel('PGO Y')
    plt.title('Ground Truth Y vs PGO Y (Detailed)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(csv_path.parent / 'y_comparison_detailed.png', dpi=300, bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    # Path to the data file
    data_path = Path(__file__).parent / "Data" / "datapoints(unsure).csv"

    print(f"Loading data from: {data_path}")

    # Create comprehensive comparison plot with anchor measurements
    fig, df = load_and_plot_data_with_anchors(data_path)

    print("\nPlot generated successfully!")
    print("- ground_truth_vs_pgo_with_anchors.png: Ground truth vs estimated positions")
    print("  (X and Y comparisons with PGO results and individual anchor measurements)")

    # Don't show plot interactively (for headless environments)
    # plt.show()  # Uncomment if running in an environment with display
