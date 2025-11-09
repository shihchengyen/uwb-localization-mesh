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
- **Place Zones** (toggle) — Click to place circular zones (Zone DJ tab).
- **Clear Zones** — Remove all user-placed zones.
- **Clear Mapping** — Remove homography + grid + zones.

## Tabs and responsibilities

- **PGO Data** (`pgo_data_widget.PgoPlotWidget`)
  - Consumes `AppBus.pointerUpdated(x_m, y_m, ts, source)`
  - Plots the path in a 4.80 m × 6.00 m space, 8×10 grid (60 cm cells)
  - Inverts y-axis so meters increase downward to match image coordinates

- **Adaptive Audio** (`adaptive_audio_widget.AdaptiveAudioWidget`)
  - Embeds `viz_floorplan.FloorplanView` and a `MiniPlayer`
  - Uses fixed split: Zone A `y < 3.00 m`, Zone B `y ≥ 3.00 m` (implement your logic in main or via zones)
  - Emits/bridges zone events to MQTT

- **Zone DJ** (`zone_dj_widget.ZoneDjWidget`)
  - Embeds `viz_floorplan.FloorplanView` and a `MiniPlayer`
  - User-placed circular zones with 1.5× hitbox; 3s register / 1s deregister with fades
  - Per-zone demo queues; emits audio commands for the “active” zone

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
- Default floorplan directory: `Demos/UnifiedDemo/assets/floorplans/`

## Troubleshooting

- **No grid appears** — You must mark corners or run Auto Transform to create the world→image homography.
- **Auto Transform fails** — Try Mark Corners manually; ensure the image has a strong rectangular feature (paper/room boundary).
- **Pointer doesn’t move** — Check your MQTT topic and payload schema; verify timestamps and units (meters).

## License

MIT (see individual package READMEs for details).
