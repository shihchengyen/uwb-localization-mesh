# Quick Start Guide - Running main_demo.py

## Prerequisites

Make sure you have the required dependencies installed:

```bash
pip install PyQt5 numpy scipy matplotlib opencv-python
```

## Running the Application

### Option 1: Run from Repository Root (Recommended)

From the repository root directory (`uwb-localization-mesh-featdummyserver/`):

```bash
python Demos/UnifiedDemo/main_demo.py --dummy
```

### Option 2: Run from Demos/UnifiedDemo Directory

```bash
cd Demos/UnifiedDemo
python main_demo.py --dummy
```

### Option 3: Run as Module

```bash
python -m Demos.UnifiedDemo.main_demo --dummy
```

## Command Line Arguments

- `--dummy`: **Required for simulation** - Uses `DummyServerBringUpProMax` for simulation instead of real hardware
- Other Qt arguments can be passed (e.g., `--style`, `--platform`)

## What Happens When You Run

1. **Application Initialization:**
   - Loads settings from QSettings
   - Creates AppBus signal hub
   - Starts DummyServerBringUpProMax (if `--dummy` flag is used)
   - Sets up polling timers (position @ 20Hz, playback @ 1Hz)

2. **UI Loading:**
   - Creates three tabs: PGO Data, Adaptive Audio, Zone DJ
   - Loads widgets from `packages/` directory
   - Attempts to load default floorplan image from `Demos/UnifiedDemo/assets/floorplans/`

3. **Position Tracking:**
   - Server simulates user movement in a figure-8 pattern
   - MainWindow polls `server.user_position` every 50ms (20Hz)
   - Position updates are emitted via `AppBus.pointerUpdated`
   - All widgets subscribe and update their visualizations

## Toolbar Actions (Top Bar)

- **📁 Open Image…** — Load a floorplan into the current tab.
- **📐 Mark Corners** — Manually mark TL/TR/BR/BL to compute homography.
- **🔍 Auto Transform** — Auto-detect corners (useful starting point).
- **🎯 Place Zones** — Enable/disable zone placement. Only active on the Zone DJ tab (Adaptive Audio uses fixed rectangles).
- **📋 Load Default Floorplan** — Load the path set in Settings (falls back to `assets/floorplans/`).
- **⚙ Settings** — Open the dialog to adjust default zone radius and default floorplan path.

## Troubleshooting

### Import Errors

If you see import errors like `ModuleNotFoundError: No module named 'appbus'`:

1. **Check you're running from the correct directory:**
   - The script automatically adds `packages/` to `sys.path`
   - Make sure `packages/appbus.py` exists

2. **Verify package structure:**
   ```
   packages/
   ├── appbus.py
   ├── services/
   │   └── settings.py
   ├── mini_player/
   ├── viz_floorplan/
   ├── pgo_data_widget/
   ├── adaptive_audio_widget/
   └── zone_dj_widget/
   ```

### Server Not Starting

If you see "Failed to start server":

1. **Make sure you're using `--dummy` flag:**
   ```bash
   python Demos/UnifiedDemo/main_demo.py --dummy
   ```

2. **Check that DummyServerBringUpProMax exists:**
   - File should be at `Demos/DummyServerBringUp.py`
   - Should contain class `DummyServerBringUpProMax`

3. **Check console output for errors:**
   - Look for import errors or initialization errors

### Widgets Not Loading

If widgets show "not installed" messages:

1. **Check that widget packages exist:**
   - `packages/pgo_data_widget/`
   - `packages/adaptive_audio_widget/`
   - `packages/zone_dj_widget/`

2. **Check `__init__.py` files exist:**
   - Each package should have an `__init__.py` file

3. **Check console for import errors:**
   - The error message will show what failed to import

### Floorplan Not Loading

If floorplan doesn't appear:

1. **Check for floorplan images:**
   - Default location: `Demos/UnifiedDemo/assets/floorplans/`
   - Supported formats: `.png`, `.jpg`, `.jpeg`, `.bmp`

2. **Load manually:**
   - Click "Open Image…" in toolbar
   - Select a floorplan image

3. **Mark corners:**
   - Click "Mark Corners" in toolbar
   - Click 4 corners on the image (TL, TR, BR, BL)
   - Or use "Auto Transform" for automatic detection

## Testing the Application

### 1. Test Position Tracking

- Switch to "PGO Data" tab
- You should see a red dot moving in a figure-8 pattern
- Path trail should be visible

### 2. Test Adaptive Audio

- Switch to "Adaptive Audio" tab
- Enable "Enable Adaptive Audio" checkbox
- Watch the pointer move between Zone A (top) and Zone B (bottom) — rectangular half-room zones appear automatically
- Zones are translucent by default and tint green after ~3s inside (1s to deregister)
- Speaker icons appear at anchor corners with live volume bars/percentages (updates every 200 ms)
- Status bar should show Pixel/Meter readouts while hovering or tracking

### 3. Test Zone DJ

- Switch to "Zone DJ" tab
- Click "Place Zones" button
- Click on the floorplan to place zones
- Enable "Enable Zone DJ" checkbox
- Watch zone registration when pointer enters zones
- Verify zones scale with the radius slider and tint green while active
- Status bar updates continue to show Pixel/Meter coordinates as pointer moves

### 4. Test Audio Controls

- In any tab with MiniPlayer:
  - Click Play/Pause button
  - Adjust volume slider
  - Select playlist from dropdown
  - Click Skip/Previous buttons

## Expected Behavior

- **Position Updates:** Red dot moves smoothly in figure-8 pattern
- **Zone Registration:** Takes 3 seconds of hovering to register
- **Zone Deregistration:** Takes 1 second after leaving to deregister
- **Audio Commands:** Logged to console (simulated, no actual playback)
- **Status Bar:** Shows server status plus `Pixel:` & `Meter:` readouts once homography is ready
- **Adaptive Audio:** Rectangular zones (A/B) auto-create, tint green while registered, and show live speaker volumes
- **Zone DJ:** Circular zones scale with radius/homography and tint green during registration

## Settings Configuration

1. Click the **⚙ Settings** toolbar button (or Edit → Settings…).
2. Adjust the **Default Zone Radius** for Zone DJ (0.01 m – 10.0 m). Changes take effect next time zones are placed.
3. Set **Default Floorplan Path** to point at an image you want `📋 Load Default Floorplan` to open automatically (leave blank to use demo assets).
4. Press **OK** to save; values persist via `QSettings`.

## Next Steps

1. **Load a floorplan image** (if not auto-loaded)
2. **Mark corners** or use "Auto Transform"
3. **Place zones** in Zone DJ tab
4. **Test zone registration** by watching pointer movement
5. **Test audio controls** via MiniPlayer

## Debugging Tips

- **Check console output** for error messages
- **Status bar** shows server status plus Pixel/Meter coordinates once homography is ready
- **Widget error messages** appear in tabs if widgets fail to load
- **Use `--dummy` flag** to ensure simulation mode

## Architecture Notes

- All communication flows through **AppBus** (thread-safe Qt signals)
- **MainWindow** polls server and routes commands
- **MainWindow** also polls speaker volumes at 5 Hz and emits `speakerVolumesUpdated`
- **Widgets** subscribe to AppBus for updates, including speaker telemetry and coordinate mapping
- **Subwidgets** (MiniPlayer, FloorplanView) are shared across widgets; FloorplanView drives status-bar pixel/meter display
- **Settings** persist via `QSettings` and are editable through the Settings dialog

---

**Happy Debugging!** 🚀

