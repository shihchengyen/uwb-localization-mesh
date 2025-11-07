import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

import matplotlib
matplotlib.use('Agg')  # non-interactive backend for saving figures
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Make `packages/` importable
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent / 'packages'))

from datatypes.datatypes import AnchorConfig  # type: ignore[reportMissingImports]
from localization_algos.pgo import PGOSolver  # type: ignore[reportMissingImports]
from localization_algos.edge_creation.anchor_edges import create_anchor_anchor_edges  # type: ignore[reportMissingImports]
from localization_algos.edge_creation.transforms import create_relative_measurement  # type: ignore[reportMissingImports]

# to run:
#   uv run Data_collection/Data/data_processing_scripts/run_pgo_on_binned_data.py Data_collection/Data/28oct/datapoints28oct.csv --positions A,B,C --anchors 0,1,2,3
# vary orientations and anchors accordingly in cmd args


def get_default_anchor_config() -> AnchorConfig:
    """Ground-truth anchor positions (cm) in room frame.
    Matches docs used elsewhere in this repo.
    """
    positions: Dict[int, np.ndarray] = {
        0: np.array([480.0, 600.0, 0.0]),  # top-right
        1: np.array([0.0,   600.0, 0.0]),  # top-left
        2: np.array([480.0,   0.0, 0.0]),  # bottom-right
        3: np.array([0.0,     0.0, 0.0]),  # bottom-left
    }
    return AnchorConfig(positions=positions)


def build_graph_from_binned(
    binned: Dict,
    allowed_anchor_ids: Optional[Set[int]] = None,
) -> Tuple[Dict[str, Optional[np.ndarray]], List[Tuple[str, str, np.ndarray]], Dict[int, np.ndarray]]:
    """Create nodes and edges suitable for PGOSolver from one binned-data dict.

    Returns
    -------
    nodes: dict of node_id -> initial position (anchors known, phone unknown/None)
    edges: list of (from_node, to_node, relative_vector) in global frame
    anchor_positions: dict anchor_id -> position for anchoring
    """
    anchor_cfg = get_default_anchor_config()
    anchor_positions = anchor_cfg.get_all_positions()

    phone_node_id: int = int(binned["phone_node_id"])  # e.g. 0

    # Known nodes: anchors; unknown: phone
    nodes: Dict[str, Optional[np.ndarray]] = {f"anchor_{aid}": pos for aid, pos in anchor_positions.items()}
    nodes[f"phone_{phone_node_id}"] = None  # unknown initial

    edges: List[Tuple[str, str, np.ndarray]] = []

    # Add anchor-anchor edges to rigidify the graph
    edges.extend(create_anchor_anchor_edges(anchor_cfg))

    # Add anchor->phone relative measurement edges (optionally filtered by anchors)
    # binned['measurements'] is a mapping of anchor_id (as string) -> list of local vectors
    meas: Dict[str, List[List[float]]] = binned.get("measurements", {})
    for anchor_id_str, vectors in meas.items():
        anchor_id = int(anchor_id_str)
        if allowed_anchor_ids is not None and anchor_id not in allowed_anchor_ids:
            continue
        for vec in vectors:
            local_vec = np.array(vec, dtype=float)
            edge = create_relative_measurement(anchor_id, phone_node_id, local_vec)
            edges.append(edge)

    return nodes, edges, anchor_positions


def run_single_row_series(row: pd.Series, allowed_anchor_ids: Optional[Set[int]] = None) -> Dict:
    # Ground truth (if present)
    gt = np.array([
        row.get('ground_truth_x', np.nan),
        row.get('ground_truth_y', np.nan),
        row.get('ground_truth_z', np.nan)
    ], dtype=float)

    # Parse filtered binned json
    binned = json.loads(str(row['filtered_binned_data_json']))

    nodes, edges, anchor_positions = build_graph_from_binned(binned, allowed_anchor_ids=allowed_anchor_ids)

    solver = PGOSolver()
    result = solver.solve(nodes=nodes, edges=edges, anchor_positions=anchor_positions)

    phone_node_id = int(binned['phone_node_id'])
    phone_key = f"phone_{phone_node_id}"
    phone_pos = result.node_positions[phone_key]

    out = {
        "ground_truth": gt,
        "optimized_phone": phone_pos,
        "anchors": anchor_positions,
        "node_positions": result.node_positions,
        "error": float(result.error),
        "iterations": int(result.iterations),
    }
    return out


def plot_result(anchors: Dict[int, np.ndarray], optimized_phone: np.ndarray, ground_truth: np.ndarray, title_suffix: str, out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 7))

    # Plot anchors
    for aid, pos in anchors.items():
        ax.scatter(pos[0], pos[1], marker='s', s=40, color='#9e9e9e', alpha=0.8, zorder=1)
        ax.text(pos[0] + 6, pos[1] + 6, f"A{aid}", color='#757575', fontsize=7, alpha=0.8)

    # Plot PGO point as a small pastel circle (no outline)
    ax.scatter(optimized_phone[0], optimized_phone[1], marker='o', s=50, color='#b39ddb', 
               linewidths=0, label='PGO point', zorder=5)

    # Plot ground truth as a star
    if np.all(np.isfinite(ground_truth)):
        # Ground truth as a hollow star: transparent fill, dark grey outline
        ax.scatter(
            ground_truth[0], ground_truth[1],
            marker='*', s=70,
            facecolors='none', edgecolors='#424242', linewidths=0.8,
            label='Ground truth', zorder=6
        )

    ax.set_xlabel('X (cm)')
    ax.set_ylabel('Y (cm)')
    ax.set_aspect('equal', adjustable='box')
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_title(f'PGO Optimization Result{title_suffix}')

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"pgo_single_bin{title_suffix.replace(' ', '_')}.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return out_path


def plot_all_results(anchors: Dict[int, np.ndarray], all_results: List[Dict], title_suffix: str, out_dir: Path) -> Path:
    """Plot multiple PGO results on a single plot."""
    fig, ax = plt.subplots(figsize=(10, 8))

    # Plot anchors
    for aid, pos in anchors.items():
        ax.scatter(pos[0], pos[1], marker='s', s=40, color='#9e9e9e', alpha=0.8, zorder=1)
        ax.text(pos[0] + 6, pos[1] + 6, f"A{aid}", color='#757575', fontsize=7, alpha=0.8)

    # Assign colors by unique ground-truth (x,y); same GT gets same color
    # Pastel/muted palette
    palette = [
        '#b39ddb',  # pastel purple
        '#90caf9',  # pastel blue
        '#a5d6a7',  # pastel green
        '#ffcc80',  # pastel orange
        '#ef9a9a',  # pastel red
        '#bcaaa4',  # pastel brown/gray
        '#f48fb1',  # pastel pink
        '#80deea',  # pastel cyan
    ]
    gt_key_to_color: Dict[Tuple[float, float], str] = {}
    next_color_idx = 0
    used_labels: Dict[Tuple[float, float], bool] = {}

    def gt_key(gt_arr: np.ndarray) -> Tuple[float, float]:
        if not np.all(np.isfinite(gt_arr)):
            return (float('nan'), float('nan'))
        # Round to avoid tiny float differences splitting colors
        return (float(np.round(gt_arr[0], 2)), float(np.round(gt_arr[1], 2)))

    # Plot all PGO points and ground truth points
    for result in all_results:
        pos = result['optimized_phone']
        gt = result['ground_truth']
        row_num = result['row_num']

        key = gt_key(gt)
        if key not in gt_key_to_color:
            color = palette[next_color_idx % len(palette)]
            gt_key_to_color[key] = color
            next_color_idx += 1
        color = gt_key_to_color[key]

        # Labels: one per unique GT for legend clarity
        pgo_label = None
        gt_label = None
        if key not in used_labels:
            if np.all(np.isfinite(gt)):
                gt_label = f'GT ({key[0]:.2f},{key[1]:.2f})'
                pgo_label = f'PGO for GT ({key[0]:.2f},{key[1]:.2f})'
            else:
                gt_label = 'GT (unknown)'
                pgo_label = 'PGO (unknown GT)'
            used_labels[key] = True

        # Plot PGO point as a small pastel circle (no outline)
        ax.scatter(pos[0], pos[1], marker='o', s=45, color=color,
                   linewidths=0, label=pgo_label, zorder=5)

        # Plot ground truth as a star
        if np.all(np.isfinite(gt)):
            ax.scatter(
                gt[0], gt[1],
                marker='*', s=70,
                facecolors='none', edgecolors='#424242', linewidths=0.8,
                label=gt_label, zorder=6
            )

    ax.set_xlabel('X (cm)')
    ax.set_ylabel('Y (cm)')
    ax.set_aspect('equal', adjustable='box')
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_title(f'PGO Optimization Results - All Rows{title_suffix}')

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"pgo_all_rows{title_suffix.replace(' ', '_')}.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return out_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Run PGO on binned-data row(s) and plot result(s).')
    parser.add_argument('csv', type=str, help='Path to datapoints CSV (e.g., Data/28oct/datapoints(28oct).csv)')
    parser.add_argument('--row', type=int, default=None, help='0-based row index to use (if --range not specified)')
    parser.add_argument('--range', type=str, default=None, help='Range of rows (1-based, e.g., "1-3" for rows 1, 2, 3)')
    parser.add_argument('--positions', type=str, default=None, help='Comma-separated orientations to include (e.g., "A,B,C")')
    parser.add_argument('--outdir', type=str, default=str(Path(__file__).parent.parent), help='Directory to save plot')
    parser.add_argument('--anchors', type=str, default=None, help='Comma-separated anchor ids to use (e.g., "0,1")')

    args = parser.parse_args()
    csv_path = Path(args.csv)
    out_dir = Path(args.outdir)

    df = pd.read_csv(csv_path)
    # Filter by orientations if requested
    if args.positions is not None and len(args.positions.strip()) > 0:
        wanted_positions = [tok.strip() for tok in args.positions.split(',') if tok.strip() != '']
        df = df[df['orientation'].isin(wanted_positions)]
        if df.empty:
            print(f"No rows with orientations in {wanted_positions}")
            return

    # Determine which rows to process
    if args.range:
        # Parse range like "1-3" (1-based) to get row indices 0, 1, 2
        parts = args.range.split('-')
        if len(parts) != 2:
            print(f"Invalid range format: {args.range}. Expected format: 'start-end' (1-based)")
            return
        start_row = int(parts[0]) - 1  # Convert to 0-based
        end_row = int(parts[1])        # Still 1-based
        row_indices = list(range(start_row, end_row))  # Python range excludes end, so this gives 0,1,2
    elif args.row is not None:
        row_indices = [args.row]
    else:
        # Default to all rows
        row_indices = list(range(len(df)))

    # Process each row and collect results
    all_results = []
    anchors = None
    
    allowed_anchor_ids: Optional[Set[int]] = None
    if args.anchors is not None and len(args.anchors.strip()) > 0:
        try:
            allowed_anchor_ids = {int(tok.strip()) for tok in args.anchors.split(',') if tok.strip() != ''}
        except ValueError:
            print(f"Invalid --anchors value: {args.anchors}. Expected comma-separated integers like '0,1'.")
            return

    for row_idx in row_indices:
        # Bounds check
        if row_idx < 0 or row_idx >= len(df):
            print(f"Row index {row_idx} out of range (0..{len(df)-1}), skipping...")
            continue

        row = df.iloc[row_idx]
        result = run_single_row_series(row, allowed_anchor_ids=allowed_anchor_ids)

        gt = result['ground_truth']
        pos = result['optimized_phone']
        if anchors is None:
            anchors = result['anchors']  # Use anchors from first row (they're all the same)

        # Store result with row number for plotting
        result_with_row = {
            'ground_truth': gt,
            'optimized_phone': pos,
            'row_num': row_idx + 1,
        }
        all_results.append(result_with_row)

        # Print concise summary
        print(f"\n--- Row {row_idx + 1} ---")
        if np.all(np.isfinite(gt)):
            err_xy = float(np.linalg.norm(pos[:2] - gt[:2]))
            err_3d = float(np.linalg.norm(pos - gt))
            print(f"Optimized phone (x,y,z): {pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}")
            print(f"Ground truth (x,y,z):  {gt[0]:.2f}, {gt[1]:.2f}, {gt[2]:.2f}")
            print(f"Errors: XY={err_xy:.2f} cm, 3D={err_3d:.2f} cm")
        else:
            print(f"Optimized phone (x,y,z): {pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}")

    # Plot results
    if anchors is None or len(all_results) == 0:
        print("No valid results to plot.")
        return

    title_suffix = ''
    if args.positions is not None and len(args.positions.strip()) > 0:
        title_suffix += f" - positions {args.positions}"
    
    if len(all_results) > 1:
        # Plot all rows on a single plot
        out_path = plot_all_results(anchors, all_results, title_suffix, out_dir)
        print(f"\nCombined plot saved to: {out_path}")
    else:
        # Plot single row
        result = all_results[0]
        title_suffix += f' - row {result["row_num"]}'
        out_path = plot_result(anchors, result['optimized_phone'], result['ground_truth'], title_suffix, out_dir)
        print(f"\nPlot saved to: {out_path}")


if __name__ == '__main__':
    main()


