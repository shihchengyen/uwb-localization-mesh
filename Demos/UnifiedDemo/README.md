# Unified Demo (PGO Data • Adaptive Audio • Zone DJ)

This demo launches a tabbed PyQt5 application that stitches together three widgets and shared services:

- **PGO Data** — Matplotlib-based path plotting of pointer positions in meters.
- **Adaptive Audio** — Floorplan visualizer with homography + fixed two-zone logic (split at 3.00 m) and a mini player.
- **Zone DJ** — Floorplan visualizer with draggable circular zones, per-zone demo queues and the same mini player.

The app wires MQTT in/out, a global signal bus, and file toolbar actions (open image, mark/auto transform, place/clear zones, clear mapping).

## Run

```bash
python Demos/UnifiedDemo/main_demo.py
```

On startup the app auto-loads the first image found in:

```
Demos/UnifiedDemo/assets/floorplans/
```

Drop your PNG/JPG here to use it as the base floorplan.

## Toolbar actions

- **Open Image…** — Choose a floorplan image to load into the current floorplan tab.
- **Mark Corners** — Click TL, TR, BR, BL in the image to compute homography from world (meters) → image (pixels).
- **Auto Transform** — Automatic rectangular feature detection to estimate the four corners.
- **Place Zones** (toggle) — Click to place circular zones (Zone DJ tab). Automatically disabled on Adaptive Audio tab (uses fixed rectangular zones).
- **Clear Zones** — Remove all user-placed zones.
- **Clear Mapping** — Remove homography + grid + zones.
- **Load Default Floorplan (📋)** — Load the default floorplan path configured in settings (falls back to demo assets if empty).
- **Settings (⚙)** — Open the settings dialog to adjust default zone radius and default floorplan path.

## Tabs and responsibilities

- **PGO Data** (`pgo_data_widget.PgoPlotWidget`)
  
  - Consumes `AppBus.pointerUpdated(x_m, y_m, ts, source)`
  - Plots the path in a 4.80 m × 6.00 m space, 8×10 grid (60 cm cells)
  - Inverts y-axis so meters increase downward to match image coordinates

- **Adaptive Audio** (`adaptive_audio_widget.AdaptiveAudioWidget`)
  
  - Embeds `viz_floorplan.FloorplanView` and a `MiniPlayer`
  - Uses fixed split: Zone A `y < 3.00 m`, Zone B `y ≥ 3.00 m` and renders half-room rectangular zones (A/B)
  - Displays translucent zones that tint green when the pointer is registered inside
  - Shows speaker icons at anchor locations with live volume bars and percentages (5 Hz updates; Adaptive Audio tab only)
  - Emits/bridges zone events to MQTT while coordinating speaker visualization

- **Zone DJ** (`zone_dj_widget.ZoneDjWidget`)
  
  - Embeds `viz_floorplan.FloorplanView` and a `MiniPlayer`
  - User-placed circular zones scale proportionally with radius and homography; 1.5× hitbox with 3s register / 1s deregister timers
  - Zones render translucent and tint green while registered
  - Per-zone demo queues; emits audio commands for the “active” zone

## Feature highlights

- **Settings dialog** (Edit → Settings… or toolbar ⚙)
  - Configure default zone radius for Zone DJ (0.01 m – 10.0 m)
  - Set a default floorplan path (used by the 📋 “Load Default Floorplan” action)
- **Coordinate display**
  - Clicking the floorplan emits pixel→meter mapping; status bar shows `Pixel:` and `Meter:` readouts
  - Live pointer updates keep both coordinate systems in sync while tracking
- **Adaptive Audio tab controls**
  - Shared floorplan switches to rectangular zones; zones are recreated automatically when the homography is ready
  - Speaker positions load from the dummy server and remain visible only while Adaptive Audio is active
- **Tab-aware toolbar state**
  - Place Zones toggle auto-disables outside Zone DJ
  - Adaptive Audio clears its half-room zones when you leave the tab and restores them on return
- **Speaker telemetry**
  - Main window polls speaker volumes at 5 Hz and broadcasts `speakerVolumesUpdated` via AppBus
  - Floorplan renders blue speaker icons with vertical volume bars and numeric percentages

## MQTT wiring (out-of-the-box)

The **MQTT client wrapper** lives in `services/mqtt_service.py`:

- **Inbound**: subscribes to `tracking/position` → emits `AppBus.pointerUpdated(x_m, y_m, ts, 'mqtt')`
- **Outbound (zones)**: publishes `zones/registered` / `zones/deregistered` with `{zone, x_m, y_m, ts, source}`
- **Outbound (audio)**: publishes to `audio/player/<device_id>/control` with `{cmd, ...payload}`

Configure host/port/topics via `QSettings` (see **Services** docs below).

## Settings (defaults)

- World rectangle: `4.80 m × 6.00 m`
- Grid: `8 × 10` (`0.60 m` cells)
- Adaptive split: `3.00 m` (top/bottom in meters)
- Zone DJ default radius: `0.25 m` (`zonedj/default_zone_radius_m`)
- Default floorplan directory: `Demos/UnifiedDemo/assets/floorplans/`
- Default floorplan path: empty string (`floorplan/default_path`) — set via Settings dialog to pick a specific image

Use **Settings (⚙)** in the toolbar (or Edit → Settings…) to adjust these values; they persist via `QSettings`.

## Troubleshooting

- **No grid appears** — You must mark corners or run Auto Transform to create the world→image homography (needed for coordinate display & zone scaling).
- **Place Zones disabled** — Switch to the Zone DJ tab; Adaptive Audio uses fixed rectangular zones.
- **Speaker icons missing** — Speaker visualization is only enabled on the Adaptive Audio tab and requires the dummy server to provide positions/volumes.
- **Pointer doesn’t move** — Check your MQTT topic and payload schema; verify timestamps and units (meters).

## License

MIT (see individual package READMEs for details).
