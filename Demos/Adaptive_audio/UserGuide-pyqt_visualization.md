# User Guide — Image Grid Homography Tool Demo

This guide explains how to use the GUI to load an image, compute a homography (auto or manual), project a 10×8 grid aligned to a 5.50 × 4.40 m world rectangle, and place interactive zones.

---

## Start the app

1. Install dependencies:
   
   ```bash
   python -m pip install PyQt5 numpy opencv-python
   ```
2. Run the app:
   
   ```bash
   python pyqt_visualization_demo.py
   ```

---

## Main window layout

At the top are primary control buttons. Below is the image canvas (QGraphicsView) and a status/info label at the bottom.

**Buttons (left → right)**:

- **Open Image** — open a file dialog and load an image.
- **Mark Corners** — switch to manual corner-marking mode (click 4 image points in order TL, TR, BR, BL).
- **Auto Transform** — attempt automatic rectangle detection and compute homography.
- **Mark Zone(s)** — toggle zone-placement mode. When on: click in the image to place draggable circular zones.
- **Clear Zone(s)** — remove all zones.
- **Clear Mapping** — clear computed homography, remove grid overlay, and clear zones.

---

## Typical workflows

### A. Auto-transform (fast)

1. Click **Open Image** and select the image that contains a rectangular object (floorplan, printed page, rectangular room).
2. Click **Auto Transform**.  
   - The tool will try to detect the largest rectangular contour and compute a homography mapping world coordinates to image pixels.  
   - The **long edge** of the detected rectangle is automatically assigned to the configured world long side (`AREA_WIDTH_M`, default 5.50 m), i.e. `GRID_COLS` (10 cells).
   - The grid will be projected onto the image using the homography.
3. If detection succeeds, you can click on the image to read pixel → world → grid cell at the cursor position. Results appear in the status bar and console.

### B. Manual corner marking (precise)

1. Click **Open Image**.
2. Click **Mark Corners**.
3. Click exactly four points on the image in this order:
   - Top-left (TL)
   - Top-right (TR)
   - Bottom-right (BR)
   - Bottom-left (BL)
4. After the 4th click the homography is computed and the grid is drawn.
5. If corners were clicked in the wrong order, use **Mark Corners** again and redo.

### C. Place and manage zones

1. Toggle **Mark Zone(s)** (button becomes checked) to enable zone placement.
2. Click anywhere on the image to add a zone. Each zone:
   - is drawn as a light-gray circular region (visual radius derived from `ZONE_RADIUS_M` and current homography),
   - has an invisible hitbox 1.5× the visual radius,
   - displays a small index label.
3. Drag zones:
   - Click-and-drag the visible handle (blue small circle) or drag the zone area — the zone center can be moved. The view will print updated coordinates to the console on move.
4. Hover-to-register:
   - Hover the cursor inside a zone's hitbox for **3 seconds** continuously → the zone becomes **registered** (visual turns green, fades in). Console prints registration with pixel/world coords.
5. Leave-to-deregister:
   - After registering, leaving the hitbox starts a **1 second** countdown. If the cursor does not re-enter within 1 second, the zone is deregistered (visual fades back to gray). Console prints deregistration.
6. Click **Clear Zone(s)** to remove all zones.

---

## What the output means

- **Pixel** — pixel coordinates in the image (scene coordinates).
- **World** — coordinates in meters using the homography (origin at the world rectangle corner matching clicked TL).
- **Cell** — integer grid cell indices `(col, row)` where `col` ∈ `[0, GRID_COLS-1]` along the mapped long side, `row` ∈ `[0, GRID_ROWS-1]` along the short side.

---

## Tips for reliable auto-detection

- Use images where the rectangle is clearly visible and dominates the frame (large relative area).
- Minimize clutter around the rectangle edges. If clutter exists, crop to the area containing the rectangle before loading.
- Good lighting / high contrast between rectangle border and background improves detection.
- If detection chooses a different rectangle (e.g., a window or rug), try:
  - cropping the image before loading, or
  - using **Mark Corners** manually.
- If you want more control, open the script and tune:
  - the minimum area fraction in `auto_detect_corners()` (`img_area * 0.002`),
  - the `Canny` sigma in the same function,
  - the `approxPolyDP` epsilon factors.

---

## Debugging features

- The program prints debug events to the console:
  - `[Zone PLACED]`, `[Zone MOVED]`, `[Zone REGISTERED]`, `[Zone DEREGISTERED]`, `[Zones CLEARED]`
  - `Computed homography (world -> img)` matrix printed after computation.
- The `auto_detect_corners(debug=True)` option will briefly draw a red overlay showing the detected quad so you can visually inspect what was found.
- For homography math debugging, add prints around `cv2.getPerspectiveTransform()` and `np.linalg.inv(H)`.

---

## Quick parameter references (edit in script)

- `AREA_WIDTH_M`, `AREA_HEIGHT_M` — world rectangle (meters)
- `GRID_COLS`, `GRID_ROWS` — grid cells (cols maps to `AREA_WIDTH_M`)
- `ZONE_RADIUS_M` — default zone radius (meters)
- `Zone` timers (3s register, 1s deregister) — change in `Zone` class `_reg_timer` and `_dereg_timer`
- Auto-detect tuning — inside `ImageGridView.auto_detect_corners()`

---

## Example usage scenarios

- **Floorplan tagging** — map a photographed floorplan to real-world meters and mark points of interest.
- **Robotics / mapping** — map operations on a physical rectangular area to pixel coordinates for visualization.
- **User studies** — create zones to represent areas of interest, record registration events.

---
