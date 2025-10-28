# Unified PyQt Demo — Proposal (Ready to Share)

## Overview

This demo (under `Demos/UnifiedDemo/`) is a **single PyQt application** that mounts three independent, package-scoped widgets into a tabbed UI:

1. **PGO Data** — live plots and diagnostics

2. **Adaptive Audio (Follow-Me)** — fixed 2-zone floor plan with follow-me playback

3. **Zone DJ** — user-defined zones with per-zone playlists

All GUI elements are **subclassed `QWidget`s** provided by separate packages. The demo owns the **only** `QApplication` and composes the widgets. Networking (MQTT) and services are centralized and injected into the widgets.

---

## Key Constraints (applies to Tab 2 & 3)

- **World size:** **4.80 m (X) × 6.00 m (Y)**

- **Cell size:** **0.60 m** → **8 × 10** grid (X×Y)

- **Axes:** origin at top-left; +X → right, +Y → down

- **Homography:** 4-corner mapping from image to world; all pointer/zone logic runs in meters

---

## Packaging & Interfaces

Each widget ships as its **own package** exposing a single, embeddable subclass:

```text
packages/
  viz_floorplan/          # shared floorplan scene utilities (optional common code)
  pgo_data_widget/        # Tab 1
  adaptive_audio_widget/  # Tab 2
  zone_dj_widget/         # Tab 3
```

**Common constructor signature (dependency injection)**  
`WidgetName(app_bus: QObject, services: dict, settings: QSettings|dict, parent: QWidget|None = None)`

**Common signals (as relevant)**

- `statusChanged(str)`

- `zoneRegistered(int|str idx, float x_m, float y_m, float ts, str source)`

- `zoneDeregistered(int|str idx, float x_m, float y_m, float ts, str source)`

**Lifecycle hooks (optional but consistent)**

- `start()`, `stop()`, `applySettings(settings)`

---

## App Composition

**Main app:** `Demos/UnifiedDemo/main_demo.py`

- Creates `QApplication` (main thread) and a `QTabWidget`

- Starts **ServerBringUp** (existing repo component) before wiring widgets

- Builds a shared **AppBus** (Qt signals hub) and **MQTT service** (Paho wrapper)

- Instantiates the three widget packages, injects services/settings, mounts tabs

- Status bar shows MQTT state, FPS, pointer latency

**AppBus (signals)**

- `pointerUpdated(float x_m, float y_m, float ts, str source)`

- `zoneRegistered(...)`, `zoneDeregistered(...)`

- `audioCommand(str device_id, str cmd, dict payload)`

- `mqttStatusChanged(str)`

**MQTT service (shared)**

- Subscribes: `tracking/position` → emits `pointerUpdated(...)`

- Publishes: `zones/registered`, `zones/deregistered`, `audio/player/<device_id>/control`

- Normalizes inbound `{x,y,z,units,ts}` to **meters** and drops `z`

---

## Tabs (Modules)

### 1) PGO Data (package: `pgo_data_widget`)

**Purpose:** visual diagnostics using Matplotlib (or PyQtGraph later).  
**Inputs:** `pointerUpdated`, optional UWB frames, zone events.  
**Behavior:**

- Plots respect **4.80 × 6.00 m** bounds and **8×10** grid

- Capped refresh (≤30–60 FPS), pause/resume, export plot/CSV  
  **Outputs:** none (read-only)

**Acceptance**

- Axes and any background grid line up with 0.60 m cells

- No UI jank at target refresh rate

---

### 2) Adaptive Audio (Follow-Me) — fixed zones (package: `adaptive_audio_widget`)

**Purpose:** floor plan with **fixed 2-zone split** + follow-me audio control.

**Zones (fixed):**

- **Zone A (top):** `0.00 m ≤ y < 3.00 m`

- **Zone B (bottom):** `3.00 m ≤ y ≤ 6.00 m`

- Midline is drawn at **Y = 3.00 m** (between rows 5 and 6)

**Inputs:** `pointerUpdated(x_m, y_m, ts, source="mqtt")`  
**Behavior:**

- Uses existing 3 s **register** / 1 s **deregister** timers with fade in/out

- Determines zone by the **3.00 m** threshold and drives timers accordingly

- Optional sidebar mini-player (for quick verification)  
  **Outputs (publish via MQTT service):**

- `zones/registered` / `zones/deregistered`
  
  ```json
  { "zone": "A"|"B", "x_m": ..., "y_m": ..., "ts": ..., "source": "pointer" }
  ```

- Audio control commands to `audio/player/<device_id>/control` as configured

**Config (tab-scoped defaults)**

```
adaptive.area_width_m   = 4.80
adaptive.area_height_m  = 6.00
adaptive.grid_cols      = 8
adaptive.grid_rows      = 10
adaptive.cell_size_m    = 0.60
adaptive.fixed_split_y  = 3.00
adaptive.zones          = ["A","B"]
adaptive.device_map     = {"A":"<devA>", "B":"<devB>"}   # optional
adaptive.t_register_ms  = 3000
adaptive.t_deregister_ms= 1000
```

**Acceptance**

- Hovering/lingering in A for ~3 s registers A (with fade); leaving A starts dereg (~1 s), crossing midline registers B after ~3 s (no flapping)

- Events and audio commands match active zone

---

### 3) Zone DJ — arbitrary zones with queues (package: `zone_dj_widget`)

**Purpose:** operator-defined zones; each zone has its own **song queue** and device routing.

**Behavior**

- Reuses floor plan visualization and homography; **user draws** zones (circle/rect)

- For each newly created zone **n**, initialize a **unique queue** (distinct first song).

- On `zoneRegistered(n, ...)`:
  
  - policy: `play(first_song)` or `queue_next` on the mapped device

- On `zoneDeregistered(n, ...)`:
  
  - policy: `pause` or `keep_playing` (config)

- Sidebar shows current queues + controls (play/pause/skip/vol)

**Config (examples)**

```
zonedj.device_map  = { 0:"<devA>", 1:"<devB>", 2:"<devC>" }
zonedj.playlists   = { 0:["Song A1","A2"], 1:["B1","B2"], ... }
zonedj.on_enter    = "play"        # or "queue_next"
zonedj.on_leave    = "pause"       # or "keep_playing"
zonedj.debounce_ms = 1000
```

**Acceptance**

- Creating N zones yields N distinct queues (unique first item per zone)

- Entering/leaving zones triggers correct, **de-bounced** MQTT commands to the right device

---

## Topics & Payloads (summary)

- **Inbound to GUI (pointer):** `tracking/position`  
  Payload: `{ "x": float, "y": float, "z": float, "units": "m|cm|mm", "ts": float }`

- **Outbound zone events:** `zones/registered`, `zones/deregistered`  
  Payload (Tab 2 uses `"A"/"B"`; Tab 3 uses numeric IDs):
  
  ```json
  { "zone": <id>, "x_m": <float>, "y_m": <float>, "ts": <float>, "source": "pointer" }
  ```

- **Audio control (to Pis):** `audio/player/<device_id>/control`  
  Payload: `{ "cmd": "play|pause|skip|inc_vol|dec_vol|queue_next|volume|current_song|show_queue", "song": "Artist - Title"?, "ts": <float> }`

---

## Dependencies & Startup

- **ServerBringUp**: imported and executed before tabs start (ensures sensors/brokers ready)

- **MQTT**: Paho client wrapper (`services["mqtt"]`) started by main app; widgets do **not** create their own MQTT clients

- **Settings**: `QSettings` (INI) or YAML with sensible defaults; pass to widgets in ctor

**Main app order**

1. Start `ServerBringUp`

2. Start MQTT service; connect topics ↔ AppBus

3. Create widgets with DI; mount tabs

4. `start()` each widget (if implemented)

5. Enter Qt event loop

---

## File Layout (proposed)

```
Demos/
  UnifiedDemo/
    main_demo.py
    appbus.py
    services/
      mqtt_service.py
      settings.py
    README.md  # quick run + config notes
packages/
  pgo_data_widget/
  adaptive_audio_widget/
  zone_dj_widget/
  viz_floorplan/        # optional shared scene utilities
```

---

## Acceptance (system level)

- World & grid are consistent: **4.80 × 6.00 m**, **8×10** at **0.60 m**

- Tab 2 uses **fixed** two-zone split at **Y = 3.00 m**

- Tab 3 supports arbitrary zones and unique per-zone queues

- MQTT events/commands align with the active tab logic

- App starts via `ServerBringUp`, stays responsive, and shuts down cleanly

---

## Next Steps (implementation order)

1. **Create tab shell & services**: `main_demo.py`, `appbus.py`, `mqtt_service.py`, `settings.py`

2. **Port Adaptive Audio** to `adaptive_audio_widget` (apply 4.80×6.00, 8×10, fixed split)

3. **Wire MQTT pointer** → Tab 2 presence → event publish

4. **Add Zone DJ widget** with queues and routing policies

5. **Add PGO Data widget** with capped-FPS plotting

6. Polish: settings dialog, status bar indicators, logging

---


