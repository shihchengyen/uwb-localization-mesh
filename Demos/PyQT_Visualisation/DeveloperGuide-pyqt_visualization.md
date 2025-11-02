# Developer Guide — Image Grid Homography Tool Demo

This document explains the internal architecture, core algorithms, key classes, and common extension points. It is meant for developers who want to maintain, debug, or extend the tool.

---

## Overview

The application is a PyQt5 GUI that renders an image in a `QGraphicsView`, computes a homography between a world rectangle and image pixels, draws a perspective-aware grid, and allows interactive "zones" to be placed, dragged, and registered/deregistered with timers and animations.

**Core dependencies**

- PyQt5 — GUI, scene graph, painting
- NumPy — numeric operations
- OpenCV — homography & vision

**Key design choices**

- A single `QGraphicsScene` holds all visual items: the base image (`QGraphicsPixmapItem`), a custom grid overlay (`ProjectedGridItem`), and per-zone graphics.
- All world→image mapping is centralized through a homography matrix `H_world_to_img` (and its inverse `H_img_to_world`), computed from 4 corresponding points.
- The *long edge* of the detected quadrilateral is always mapped to `AREA_WIDTH_M` (5.50 m) and `GRID_COLS` (10 cells).

---

## Files

- `pyqt_visualization_demo.py` — main GUI containing all classes.

Optional future split:

- `core/homography.py` — mapping & math
- `ui/view.py` — `ImageGridView`
- `ui/zones.py` — zone classes & animations

---

## Constants and world spec

Defined near the top of the script:

```py
AREA_WIDTH_M = 5.50
AREA_HEIGHT_M = 4.40
GRID_COLS = 10
GRID_ROWS = 8
ZONE_RADIUS_M = 0.25
```

- `AREA_WIDTH_M` (long side) is mapped to the longest side of the detected image quadrilateral. This guarantees the 10×8 grid aligns as **10 along the long side** and **8 along the short side**.
- Change these to adapt for other physical setups.

---

## Core classes

### `ImageGridView(QGraphicsView)`

Responsibilities:

- set up `QGraphicsScene` and hold references to items
- load image into `QGraphicsPixmapItem`
- compute & store homography matrices (`H_world_to_img`, `H_img_to_world`)
- render `ProjectedGridItem` overlay
- handle modes: corner marking and zone placement
- event handling (mouse clicks, wheel zoom)

Important methods:

- `load_image(path)` — loads/clears state, sets scene rect
- `start_marking_corners()` — enables manual corner collection
- `_compute_homography_from_marked()` — orders/rotates points so longest edge maps to `AREA_WIDTH_M`, computes `H` & `H_inv`, updates grid
- `auto_detect_corners(debug=True)` — robust detection pipeline (CLAHE, automatic Canny, morphological closing, quad scoring, subpixel refine)
- `_show_debug_contour(pts)` — temporary red overlay to visualize detection choice
- `toggle_place_zones(enable)` / `clear_zones()` — zone placement & management
- Optional callbacks: `zone_registered(zone)`, `zone_deregistered(zone)`, `zone_moved(zone)`

### `ProjectedGridItem(QGraphicsItem)`

- Draws the projected grid using `QPainterPath` polylines.
- For each vertical/horizontal world grid line:
  1. Sample 200 points in world meters along that line.
  2. Map to image pixels via `apply_homography(self.H, pts_world)`.
  3. Draw the resulting polyline.

This approach is fast enough for typical images and correctly follows perspective.

### `Zone(QObject)`

A composite that owns:

- `hitbox_item : ZoneHitboxItem` — invisible `QGraphicsEllipseItem` centered on zone; **draggable**, **hoverable**, and sends geometry changes.
- `visual_item : QGraphicsEllipseItem` — light-gray/green circle (child of hitbox).
- `handle_item : QGraphicsEllipseItem` — visible blue handle (child of hitbox). By default centered at the zone centroid.
- `label : QGraphicsSimpleTextItem` — index label.
- `tooltip : QGraphicsSimpleTextItem` — shows world coords while hovering/dragging.

State & behavior:

- `registered : bool`
- timers: `_reg_timer` (3s) and `_dereg_timer` (1s)
- animation: `_anim : QVariantAnimation` changes `visual_item` opacity for fade in/out

Key methods:

- `_on_hover_enter()` / `_on_hover_leave()` — start/stop timers, show/hide tooltip
- `_do_register()` / `_do_deregister()` — update visuals, print debug, trigger callbacks
- `_on_moved(new_x_px, new_y_px)` — update center, tooltip position; prints pixel+world coords
- `_pixel_to_world(x_px, y_px)` — map pixels to meters (uses `H_img_to_world`)

### `ZoneHitboxItem(QGraphicsEllipseItem)`

- Accepts hover and mouse events; **movable** with `ItemIsMovable` and `ItemSendsGeometryChanges` set.
- On `ItemPositionHasChanged`, calls back to parent `Zone` via `_on_moved`.

---

## Homography & long-edge mapping

### Point ordering and rotation

Manual or auto-detected points are first ordered as TL, TR, BR, BL (`order_quad_points`). Then edge lengths are measured for the four sides; whichever is longest is considered the **world width** edge. The point list is **rotated** so that the longest side becomes `(0,0)→(AREA_WIDTH_M,0)` in world space, i.e. the 10-cell / 5.5 m side.

### Computing H

```py
world_pts = np.array([[0,0], [AREA_WIDTH_M,0], [AREA_WIDTH_M,AREA_HEIGHT_M], [0,AREA_HEIGHT_M]], np.float32)
H = cv2.getPerspectiveTransform(world_pts, img_pts_rot.astype(np.float32))
H_inv = np.linalg.inv(H)
```

- `H` maps world (meters) → image (pixels)
- `H_inv` maps image (pixels) → world (meters)

### Grid projection

The grid is not drawn axis-aligned — each world grid line is sampled and projected through `H`. This preserves perspective and handles arbitrary orientations.

---

## Auto-detection pipeline

Defined in `ImageGridView.auto_detect_corners(debug=True)`:

1. **Preprocess**: grayscale → CLAHE (contrast) → Gaussian blur.
2. **Edges**: automatic Canny (`sigma=0.33` around image median).
3. **Morphology**: closing + dilation to connect edges.
4. **Contours**: find contours, keep top by area; approximate with several `eps_factor`s.
5. **Rectangularity score**: `score = area * (area/minAreaRectArea)^2`.
6. **Subpixel refine**: `cv2.cornerSubPix` refines the chosen quad corners.
7. **Order & clamp**: TL,TR,BR,BL; clamp to image bounds.
8. **Debug overlay**: draw red polygon if `debug=True`.

**Tuning knobs**

- Min area fraction: default `img_area * 0.002`. Increase if too many false quads; decrease if true quad is small.
- Canny sigma: tweak `sigma`. Larger → more edges, smaller → fewer.
- Approx eps factors: try `(0.015–0.03)` for noisy images.
- Add a downscale step for very large images to speed up detection, remembering to scale points back.

---

## Timers, animations, and UX

**Registration**

- Hover inside hitbox → start `_reg_timer` (3s). On timeout, call `_do_register()`.
- When registered, visual fill becomes green and a fade animation runs to 1.0 opacity.

**Deregistration**

- Leaving hitbox: if registered, start `_dereg_timer` (1s). On timeout, call `_do_deregister()` and fade back to 0.6 opacity.

**Tooltip**

- Shown on hover and during drag; displays world coordinates.
- Font size set in `Zone.__init__` (change via `QFont.setPointSize`). Position computed in `_update_tooltip_pos()`.

---

## Extension points

### Export registered zones to CSV

Add a `QAction`/button to iterate `view.zones`:

```py
import csv
with open("zones.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["idx", "x_m", "y_m", "registered"])
    for z in view.zones:
        x_m, y_m = z._pixel_to_world(z.center[0], z.center[1])
        w.writerow([z.idx, f"{x_m:.3f}", f"{y_m:.3f}", int(z.registered)])
```

### Make handle draggable separately

Subclass `QGraphicsEllipseItem` for `handle_item`, enable `ItemIsMovable`, and in `itemChange` forward its movement to `hitbox_item.setPos(...)`.

### Snap zones to grid

In `Zone._on_moved`, compute `(col,row)` from world meters and snap center to the corresponding cell center by mapping back through `H_world_to_img`.

---

## Debugging & troubleshooting

- Enable the detection debug overlay in `auto_detect_corners(debug=True)`.
- Inspect homography matrix values printed in the console after `_compute_homography_from_marked()`.
- If grid looks skewed or flipped, check the point order and the long-edge rotation logic.
- For performance issues on large images, add a downscale factor (e.g., 0.5) in the detection path and rescale points back up.

---

## Performance notes

- Grid drawing samples 200 points per grid line. With 11 vertical + 9 horizontal lines, that's ~4k points — fine for real-time. Reduce samples if needed.
- Animations are short (360 ms) and only affect per-zone opacity.
- Consider downscaling the image for detection on very large images (>4000 px) to speed up contour search.

---

## Testing ideas

- Unit-test roundtrip mapping: pick world points, project via `H`, invert with `H_inv`, assert small error.
- Synthetic images with known homographies to verify grid alignment.
- Images with multiple rectangles to verify scoring picks the large, most-rectangular quad.
- UI tests: place/drag zones and assert center updates & console messages.

---

## Code map (quick reference)

- `apply_homography(H, pts)` — np-array homography application
- `order_quad_points(pts)` — order 4 points TL, TR, BR, BL
- `ProjectedGridItem.paint()` — draw grid by sampling world lines
- `ImageGridView._compute_homography_from_marked()` — compute H/H_inv, rotate so long edge maps to width
- `ImageGridView.auto_detect_corners()` — robust corner detection pipeline
- `ImageGridView._show_debug_contour()` — temporary red overlay of chosen quad
- `ImageGridView.toggle_place_zones()` / `clear_zones()` — zone management
- `Zone` — hitbox, visual, handle, tooltip, timers, fade animation
- `ZoneHitboxItem.itemChange()` — forwards position changes to Zone

---

## License & contributions

Add your preferred license. PRs welcome for:

- Export/Import of zones
- ArUco-based transform
- Accepting live input data
- Publishing events and state changes
- Live-tuning sliders for detection
- Undo/redo for placements
