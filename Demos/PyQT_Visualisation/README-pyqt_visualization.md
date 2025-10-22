# Image Grid Homography Tool Demo

Map a real-world rectangular area (default 5.50 m × 4.40 m) onto a photographed or scanned image, compute a homography, draw a 10×8 grid, and interactively add draggable "zones" with hover-to-register behavior.

This tool is a PyQt5-based GUI that combines OpenCV homography detection with a flexible QGraphicsView scene. It supports:

- auto-detection of the 4 corner points of a rectangular object,
- manual corner marking,
- mapping the long edge of the detected rectangle to the configured long-world side (5.50 m → 10 cells),
- drawing the world grid projected into image space (perspective-aware),
- placing draggable circular zones whose hitboxes register after hovering,
- fade-in/out animations for registration state,
- debug overlays and console debug prints for development.

---

## Quickstart

### Requirements

- Python 3.8+
- Required Python packages:
  - `PyQt5`
  - `numpy`
  - `opencv-python`

Install dependencies (example):

```bash
python -m pip install PyQt5 numpy opencv-python
```

### Run

Save the main script (for example `image_grid_zones_enhanced.py`) and run:

```bash
python pyqt_visualization_demo.py
```

---

## Files & structure

```
project-root/
├─ pyqt_visualization_demo.py    # main GUI script
├─ README.md
└─ docs/
   └─ UserGuide.md
```

---

## Main features

- **Auto Transform**: detect a rectangle (paper/plan) in the image and compute a homography that maps world coordinates (meters) to image pixels.
- **Mark Corners**: manually select top-left, top-right, bottom-right, bottom-left image points to compute homography.
- **Grid projection**: draws a 10×8 grid by projecting world grid lines using the homography (works with perspective photos).
- **Mark Zone(s)**: toggle zone placement mode, click to place circular zones (default radius configurable), zones are draggable.
- **Hitbox / registration**: each zone has a hitbox = 1.5 × radius; hovering within the hitbox for 3s registers the zone; leaving for 1s deregisters it.
- **Animations**: zones fade in/out on register/deregister.
- **Debugging**: console prints for zone create/move/register/deregister; debug overlay for auto-detection.

---

## Key configurable constants

Change these in the script near the top (or expose them via UI in future):

- `AREA_WIDTH_M` — world long side in meters (default `5.50`)
- `AREA_HEIGHT_M` — world short side in meters (default `4.40`)
- `GRID_COLS` — number of columns along the long side (`10`)
- `GRID_ROWS` — number of rows along the short side (`8`)
- `ZONE_RADIUS_M` — default radius of newly placed zones in meters
- Auto-detect thresholds are in the `auto_detect_corners()` function (min area ratio, Canny sigma, approx epsilon). See `docs/DeveloperGuide.md` for details.

---

## Troubleshooting (short)

- **Auto-detect fails or detects the wrong rectangle**  
  - Try cropping the image to the region containing the rectangle or improve contrast. See `docs/UserGuide.md`—section *Tips for better detection*.  
  - Increase the min-area threshold in `auto_detect_corners()` or run `Mark Corners` manually.
- **Grid doesn't line up as expected**  
  - Make sure the detected corners correspond to the real-world rectangle corners. Use manual marking to correct them.
- **Zone hover not registering**  
  - Ensure you hover *inside the hitbox* for 3 seconds. Hitbox = 1.5 × visual radius. You can change timers in the `Zone` class.
