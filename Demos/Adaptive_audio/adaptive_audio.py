import time
import argparse
from typing import Tuple
import numpy as np

from gain_controller import GainController


def main():
    ap = argparse.ArgumentParser(description="Adaptive audio gain controller demo")
    ap.add_argument("--model", choices=["linear", "quadratic"], default="quadratic",
                    help="Distance to gain mapping model")
    ap.add_argument("--alpha", type=float, default=0.25,
                    help="Smoothing alpha (0..1)")
    ap.add_argument("--rate", type=float, default=0.08,
                    help="Max gain delta per update (0..1)")
    ap.add_argument("--min_dist", type=float, default=30.0,
                    help="Near-field clamp distance in cm")
    ap.add_argument("--hz", type=float, default=10.0,
                    help="Update frequency (Hz) for demo trajectory")
    args = ap.parse_args()

    # Import anchor positions from the demo implementation
    from demo_implementation.create_anchor_edges import ANCHORS

    gc = GainController(    #from gain_controller.py
        anchor_positions=ANCHORS,
        distance_model=args.model,
        min_distance_cm=args.min_dist,
        smoothing_alpha=args.alpha,
        max_delta_per_update=args.rate,
    )

    print("Adaptive audio gain controller running. Ctrl+C to stop.")
    print("Columns: t  pair(L,R)  L  R  x  y  z")

    t0 = time.time()
    dt = 1.0 / max(args.hz, 1e-6)

    try:
        while True:
            t = time.time() - t0

            # Simple demo trajectory: a slow circle in XY at z = 0
            r = 150.0  # cm
            cx, cy = 200.0, 275.0
            x = cx + r * np.cos(0.3 * t)
            y = cy + r * np.sin(0.3 * t)
            z = 0.0

            L, R, pair = gc.update_position((x, y, z))

            # In your real app: send L/R gains to the chosen pair's speakers here
            print(f"{t:6.2f}  {pair}  {L:5.2f}  {R:5.2f}  {x:7.1f} {y:7.1f} {z:6.1f}")

            time.sleep(dt)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()


