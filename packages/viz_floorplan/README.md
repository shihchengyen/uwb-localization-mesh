# viz-floorplan

Reusable `FloorplanView` widget for PyQt5 that supports:
- Loading a floorplan image (QGraphicsView)
- Manual corner marking (TL, TR, BR, BL) and **Auto Transform**
- World↔Image **homography** and **grid projection** (8×10 by default)
- Draggable circular **zones** with **3s/1s** presence logic and opacity **fade**
- A "virtual pointer" for mapping world positions onto the image
- **Speaker volume visualization** (Adaptive Audio mode)
  - Speaker icons at corner positions
  - Real-time volume bars and percentage display
  - Automatic positioning based on anchor locations

## Install (editable)

```bash
pip install -e packages/viz_floorplan
```

## API (high level)

```python
from viz_floorplan import FloorplanView

plan = FloorplanView(parent, world_w_m=4.80, world_h_m=6.00, grid_cols=8, grid_rows=10)
plan.load_image("assets/floorplan.png")
plan.start_marking_corners()
plan.auto_transform()  # optional
plan.toggle_place_zones(True)  # click to add circular zones
plan.clear_zones()
plan.clear_mapping()
plan.map_pointer(x_m, y_m)  # map world coordinates to image

# Speaker visualization (Adaptive Audio)
plan.set_show_speakers(True)  # Enable speaker visualization
plan.set_speaker_positions({0: [4.8, 6.0, 0], 1: [0, 6.0, 0], 2: [4.8, 0, 0], 3: [0, 0, 0]})
plan.set_speaker_volumes({0: 70, 1: 50, 2: 80, 3: 60})  # Update volumes
```

## Signals

- `zoneRegistered(idx, x_m, y_m, ts, source)`
- `zoneDeregistered(idx, x_m, y_m, ts, source)`
- `zoneMoved(idx, x_m, y_m)`
- `pointerMapped(x_m, y_m, ts, source)`

## Notes

- Scene units are **pixels** (image space). Homography lets you map from **meters** to pixels and back.
- Grid is drawn by projecting world-space lines via the homography, so it aligns with perspective in the image.
