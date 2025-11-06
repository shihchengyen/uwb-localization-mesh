# Unified Demo Application Layer Architecture Plan

## Executive Summary

This document outlines the overall architecture for the **Application Layer** of the UWB Localization Visualization System. The Application Layer is implemented as a PyQt5-based desktop application that provides three distinct visualization and interaction modes (tabs) while sharing a common infrastructure for data communication, services, and state management.

**Key Design Principles:**

- **Separation of Concerns**: Each widget is an independent, package-scoped component
- **Dependency Injection**: Services and configuration are injected, not created internally
- **Event-Driven Communication**: Qt signals (AppBus) decouple components
- **Single Responsibility**: Each widget handles one visualization/interaction paradigm
- **Extensibility**: New widgets can be added without modifying existing code

## Architecture Scope

### ✅ APPLICATION FEATURES

**Data Flow:**

- MainWindow creates and starts `DummyServerBringUpProMax` instance
- QTimer (20Hz) polls `server.user_position` attribute directly
- Position data converted from cm to meters
- `AppBus.pointerUpdated` signal emitted to all widgets
- Self-contained Python application (no external brokers needed)

**Core Features:**

- ✅ PGO Data Widget (real-time position plotting)
- ✅ Adaptive Audio Widget (2-zone visualization + simulated audio control)
- ✅ Zone DJ Widget (user-defined zones + simulated audio control)
- ✅ FloorplanView (homography, zones, pointer tracking)
- ✅ DummyServer simulation (figure-8 pattern)
- ✅ Audio demo methods (`adaptive_audio_demo()`, `zone_dj_demo()`, `set_playlist()`)
- ✅ Widgets call server methods directly via services dict
- ✅ Thread-safe attribute access with locks
- ✅ Status bar showing position and server status

**Implementation Notes:**

- Audio control is simulated (commands are logged only)
- No external hardware integration in this design
- Direct method calls for audio control (no message broker)
- Position data via direct attribute polling (no pub/sub)

**Thread Safety Limitations:**

- ⚠️ Audio methods should only be called from the main Qt thread
- Direct calls to `server.adaptive_audio_demo()` etc. are convenient but lack explicit thread safety
- Audio state variables in DummyServer (e.g., `self.volumes`, `self.current_pair`) are not protected by locks
- For production use, consider using Qt signals or adding locks to audio methods
- Current implementation is adequate for demonstration/development purposes

---

## 1. System Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        QApplication (Main Thread)                │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    MainWindow (QMainWindow)                │  │
│  │                                                            │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │              AppBus (Signal Hub)                    │  │  │
│  │  │  - pointerUpdated(x_m, y_m, ts, source)            │  │  │
│  │  │  - zoneRegistered(idx, x_m, y_m, ts, source)       │  │  │
│  │  │  - zoneDeregistered(idx, x_m, y_m, ts, source)     │  │  │
│  │  │  - serverStatusChanged(state)                      │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │                            ↑                               │  │
│  │                            │ emit signals                  │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │      Position Polling (QTimer, 20Hz)                │  │  │
│  │  │  - Reads: server.user_position (with lock)         │  │  │
│  │  │  - Converts: cm → meters                           │  │  │
│  │  │  - Emits: pointerUpdated on change                 │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │                            ↓ attribute read               │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │    DummyServerBringUpProMax (Background Threads)    │  │  │
│  │  │  - self.user_position: np.ndarray [x,y,z] (cm)    │  │  │
│  │  │  - self.data: Dict[int, BinnedData]               │  │  │
│  │  │  - Thread-safe with _position_lock                │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │                                                            │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │              Services Layer                         │  │  │
│  │  │  ┌──────────────────────────────────────────────┐  │  │  │
│  │  │  │  SettingsService (QSettings wrapper)         │  │  │  │
│  │  │  │  - World dimensions, grid specs              │  │  │  │
│  │  │  │  - Widget preferences                        │  │  │  │
│  │  │  │  - Simulation parameters                     │  │  │  │
│  │  │  └──────────────────────────────────────────────┘  │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │                                                            │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │              QTabWidget (Container)                 │  │  │
│  │  │  ┌──────────────┐ ┌──────────────┐ ┌────────────┐│  │  │
│  │  │  │ PGO Data     │ │ Adaptive     │ │ Zone DJ    ││  │  │
│  │  │  │ Widget       │ │ Audio Widget │ │ Widget     ││  │  │
│  │  │  │              │ │              │ │            ││  │  │
│  │  │  │ (Tab 1)      │ │ (Tab 2)      │ │ (Tab 3)    ││  │  │
│  │  │  └──────────────┘ └──────────────┘ └────────────┘│  │  │
│  │  │       ↑                  ↑                ↑        │  │  │
│  │  │       └──────────────────┴────────────────┘        │  │  │
│  │  │           All subscribe to AppBus signals          │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │                                                            │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │              Status Bar                            │  │  │
│  │  │  - Server status (running/stopped)                 │  │  │
│  │  │  - FPS / update rate                               │  │  │
│  │  │  - Current position (x, y)                         │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │                                                            │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │              Toolbar                                │  │  │
│  │  │  - Open Image, Mark Corners, Auto Transform        │  │  │
│  │  │  - Place Zones, Clear Zones, Clear Mapping         │  │  │
│  │  │  - Start/Stop Simulation                           │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

                       ARCHITECTURE NOTES:
          ┌─────────────────────────────────────────────┐
          │  Direct attribute polling (no broker)       │
          │  DummyServer runs in same Python process    │
          │  Thread-safe attribute access with locks    │
          │  Direct method calls for audio control      │
          └─────────────────────────────────────────────┘
```

### 1.2 Component Responsibilities

| Component                    | Responsibility                                         | Dependencies                                   |
| ---------------------------- | ------------------------------------------------------ | ---------------------------------------------- |
| **MainWindow**               | Application shell, server polling, widget coordination | QApplication, AppBus, DummyServerBringUpProMax |
| **AppBus**                   | Event routing, decoupling widgets from data source     | Qt Core (QObject, Signal)                      |
| **SettingsService**          | Configuration management                               | QSettings                                      |
| **PgoPlotWidget**            | Real-time position plotting, diagnostics               | AppBus, matplotlib/pyqtgraph                   |
| **AdaptiveAudioWidget**      | Fixed 2-zone follow-me visualization + audio control   | AppBus, viz_floorplan, server instance         |
| **ZoneDjWidget**             | User-defined zones + audio control                     | AppBus, viz_floorplan, server instance         |
| **FloorplanView**            | Floorplan visualization, homography, zones             | PyQt5, OpenCV, numpy                           |
| **DummyServerBringUpProMax** | UWB simulation, PGO processing, audio demo simulation  | numpy, scipy, packages.*                       |

---

## 2. Communication Architecture

### 2.1 AppBus Pattern

The **AppBus** is a Qt signal hub that implements a publish-subscribe pattern for intra-application communication. It decouples producers (MainWindow polling server) from consumers (widgets) and ensures thread-safe event delivery.

**Implementation:**

```python
class AppBus(QObject):
    # Position updates (from DummyServerBringUp via polling)
    pointerUpdated = Signal(float, float, float, str)  # x_m, y_m, ts, source

    # Zone events (from widgets)
    zoneRegistered = Signal(object, float, float, float, str)  # idx, x_m, y_m, ts, source
    zoneDeregistered = Signal(object, float, float, float, str)

    # Server status
    serverStatusChanged = Signal(str)  # "running", "stopped", "error"
```

**Usage Pattern:**

1. **MainWindow** creates and starts `DummyServerBringUpProMax` instance
2. **QTimer** (in MainWindow) polls `server.user_position` attribute periodically (50ms = 20Hz)
3. When position changes, **MainWindow** emits `AppBus.pointerUpdated(x_m, y_m, ts, "server")`
4. **Widgets** connect to `pointerUpdated` and update their visualizations
5. **Widgets** emit zone events to AppBus (for logging/status display)

**Benefits:**

- **Loose Coupling**: Widgets don't know about server implementation
- **Testability**: Widgets can be tested with mock AppBus
- **Thread Safety**: Qt signals handle cross-thread communication automatically (server runs in background threads)
- **Extensibility**: New widgets can be added without modifying existing code
- **Simplicity**: Self-contained application, no external dependencies

### 2.2 Data Flow Patterns

#### 2.2.1 Inbound Tracking Data Flow (Direct Attribute Polling)

```
DummyServerBringUpProMax (background threads)
    │
    │ - Simulates user movement (figure-8 pattern)
    │ - Processes UWB measurements
    │ - Runs PGO solver
    │ - Updates self.user_position attribute (thread-safe with lock)
    │ - Provides audio demo methods (adaptive_audio_demo(), zone_dj_demo())
    │
    ↓ (polled via attribute access)

MainWindow._position_poll_timer (QTimer, main thread, 20Hz)
    │
    │ - Read server.user_position (with lock)
    │ - Convert from cm to meters (divide by 100)
    │ - Check if position changed
    │ - Emit Qt signal
    ↓
AppBus.pointerUpdated(x_m, y_m, ts, "server")
    │
    ├─→ PgoPlotWidget (plots point)
    ├─→ AdaptiveAudioWidget (updates floorplan pointer)
    └─→ ZoneDjWidget (updates floorplan pointer)

              ┌────────────────────────────────────┐
              │  Widget → Server Method Calls      │
              │  (Direct, not via AppBus)          │
              └────────────────────────────────────┘
                              ↓
        AdaptiveAudioWidget.button_clicked()
                              ↓
              services["server"].adaptive_audio_demo()
                              ↓
        DummyServerBringUpProMax logs audio commands
```

**Implementation in MainWindow:**

```python
class MainWindow(QMainWindow):
    def __init__(self):
        # ... setup ...

        # Start server
        self.server = DummyServerBringUpProMax(
            simulation_speed=1.0,
            phone_node_id=0
        )
        self.server.start()

        # Setup polling timer
        self._last_position = None
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_server_position)
        self._poll_timer.start(50)  # 20Hz polling

    def _poll_server_position(self):
        # Thread-safe attribute access
        with self.server._position_lock:
            position = self.server.user_position

        if position is not None:
            # Convert from cm to meters
            x_m = position[0] / 100.0
            y_m = position[1] / 100.0

            # Check if changed (avoid redundant updates)
            if self._last_position is None or not np.allclose(position[:2], self._last_position):
                ts = time.time()
                self.bus.pointerUpdated.emit(x_m, y_m, ts, "server")
                self._last_position = position[:2].copy()
```

#### 2.2.2 Zone Registration Flow (Adaptive Audio)

```
AdaptiveAudioWidget (main thread)
    │
    │ - User position (x_m, y_m) received via pointerUpdated
    │ - Determine zone: y < 3.00 m → Zone A, y ≥ 3.00 m → Zone B
    │ - Timer logic: hover ≥3s → register, leave ≥1s → deregister
    │
    ├─→ Visual feedback (fade animation, color change)
    │
    └─→ AppBus.zoneRegistered.emit("A", x_m, y_m, ts, "pointer")
            │
            ├─→ MainWindow (logs event, updates status bar)
            └─→ Other widgets (optional: logging, analytics)
```

**Note:** Zone registration events are emitted to AppBus for logging and status display.

### 2.3 Data Sources and Sinks

**Data Sources:**

- `DummyServerBringUpProMax.user_position` (np.ndarray) - Current user position in cm [x, y, z]
  - Accessed via: Direct attribute read with thread lock
  - Update rate: ~10Hz (server internal simulation)
  - Polling rate: 20Hz (MainWindow QTimer)

**Data Sinks:**

- `AppBus.pointerUpdated` signal → All visualization widgets
- `AppBus.zoneRegistered` / `zoneDeregistered` signals → Logged to console/status bar
- Widget internal state (plots, floorplan views, zone states)
- Server audio demo methods → Console logs (simulated audio control)

---

## 3. Widget Architecture

### 3.1 Common Widget Interface

All widgets follow a consistent interface pattern:

```python
class BaseWidget(QWidget):
    def __init__(self, app_bus: AppBus, services: dict, settings: QSettings, parent: QWidget = None):
        super().__init__(parent)
        self.bus = app_bus
        self.services = services
        self.settings = settings
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Initialize UI components"""
        pass

    def _connect_signals(self):
        """Connect to AppBus signals"""
        pass

    def start(self):
        """Called when widget becomes active (optional lifecycle hook)"""
        pass

    def stop(self):
        """Called when widget becomes inactive (optional lifecycle hook)"""
        pass

    def applySettings(self, settings: QSettings):
        """Update widget configuration (optional)"""
        pass
```

### 3.2 PGO Data Widget (`pgo_data_widget`)

**Purpose:** Real-time visualization of position tracking data with diagnostic capabilities.

**Components:**

- Matplotlib canvas (or PyQtGraph for better performance)
- Path plot (trail of positions)
- Grid overlay (8×10 cells, 0.60 m per cell)
- Axis labels and scaling (4.80 m × 6.00 m bounds)
- Controls: pause/resume, clear, export CSV/PNG

**Data Sources:**

- `AppBus.pointerUpdated(x_m, y_m, ts, source)`

**Configuration:**

- `pgo.world_width_m = 4.80`
- `pgo.world_height_m = 6.00`
- `pgo.grid_cols = 8`
- `pgo.grid_rows = 10`
- `pgo.refresh_rate_fps = 30` (rate limiting)
- `pgo.max_history_points = 1000`

**Implementation Notes:**

- Rate limiting: accumulate updates, redraw at fixed interval (30-60 FPS)
- Y-axis inversion: world coordinates increase downward (matching image coordinates)
- Memory management: limit history buffer to prevent memory growth
- Thread safety: all updates must occur on main thread (Qt signal delivery ensures this)

### 3.3 Adaptive Audio Widget (`adaptive_audio_widget`)

**Purpose:** Fixed 2-zone follow-me audio system with floorplan visualization.

**Components:**

- `FloorplanView` (from `viz_floorplan` package)
  - Floorplan image display
  - Homography-based world↔image mapping
  - Grid overlay (8×10 cells)
  - Pointer visualization (red dot)
  - Fixed zone boundaries (visual split at Y = 3.00 m)
- `MiniPlayer` (sidebar)
  - Current song display
  - Play/pause/skip controls (calls server methods)
  - Volume control
  - Playlist selector (calls `server.set_playlist()`)

**Zone Logic:**

- **Zone A (Top):** `0.00 m ≤ y < 3.00 m`
- **Zone B (Bottom):** `3.00 m ≤ y ≤ 6.00 m`
- Registration: User hovers in zone for ≥3 seconds → emit `zoneRegistered`
- Deregistration: User leaves zone for ≥1 second → emit `zoneDeregistered`
- Visual feedback: Fade animation, color change, zone highlighting

**Data Flow:**

- Receives: `AppBus.pointerUpdated(x_m, y_m, ts, source)`
- Updates: `FloorplanView.map_pointer(x_m, y_m)`
- Determines: Zone A or B based on y-coordinate
- Emits: `AppBus.zoneRegistered("A"|"B", x_m, y_m, ts, "pointer")`
- **Audio Control:** Direct calls to `server.adaptive_audio_demo()` / `server.stop_adaptive_audio_demo()`

**Integration with Server:**

```python
class AdaptiveAudioWidget(QWidget):
    def __init__(self, app_bus, services, settings, parent=None):
        super().__init__(parent)
        self.bus = app_bus
        self.server = services.get("server")  # Access to DummyServerBringUpProMax

    def _on_start_button_clicked(self):
        if self.server:
            self.server.adaptive_audio_demo()  # Direct method call

    def _on_stop_button_clicked(self):
        if self.server:
            self.server.stop_adaptive_audio_demo()

    def _on_playlist_changed(self, playlist_num):
        if self.server:
            self.server.set_playlist(playlist_num)
```

**Configuration:**

- `adaptive.area_width_m = 4.80`
- `adaptive.area_height_m = 6.00`
- `adaptive.split_y_m = 3.00`
- `adaptive.t_register_ms = 3000`
- `adaptive.t_deregister_ms = 1000`

### 3.4 Zone DJ Widget (`zone_dj_widget`)

**Purpose:** User-defined zones with per-zone playlists and queue management.

**Components:**

- `FloorplanView` (shared with Adaptive Audio)
  - Same floorplan visualization capabilities
  - User-placed circular zones (draggable)
  - Zone registration/deregistration with timers
- Zone management UI
  - "Place Zones" mode (toggle)
  - Zone list sidebar (zone ID, current song, queue)
  - Zone editing (radius, position, playlist assignment)
- `MiniPlayer` (shared component)
  - Per-zone queue display
  - Play/pause/skip for active zone (calls server methods)
  - Volume control per device

**Zone Behavior:**

- User places zones by clicking on floorplan (in "Place Zones" mode)
- Each zone has:
  - Unique ID (auto-incrementing integer)
  - Position (x_m, y_m) in world coordinates
  - Radius (default: 0.25 m, adjustable)
  - Playlist (queue of songs) - simulated in this sprint
  - Mapped device ID
- Registration: User hovers in zone for ≥3 seconds → calls `server.zone_dj_demo()`
- Deregistration: User leaves zone for ≥1 second → calls `server.stop_zone_dj_demo()`

**Data Flow:**

- Receives: `AppBus.pointerUpdated(x_m, y_m, ts, source)`
- Updates: `FloorplanView.map_pointer(x_m, y_m)`
- Checks: Which zone(s) contain the pointer (1.5× radius hitbox)
- Emits: `AppBus.zoneRegistered(zone_id, x_m, y_m, ts, "pointer")`
- **Audio Control:** Direct calls to `server.zone_dj_demo()` / `server.stop_zone_dj_demo()`

**Integration with Server:**

```python
class ZoneDjWidget(QWidget):
    def __init__(self, app_bus, services, settings, parent=None):
        super().__init__(parent)
        self.bus = app_bus
        self.server = services.get("server")  # Access to DummyServerBringUpProMax

    def _on_zone_registered(self, zone_id, x_m, y_m, ts, source):
        # When user enters a zone
        if self.server:
            self.server.zone_dj_demo()  # Start zone DJ simulation

    def _on_zone_deregistered(self, zone_id, x_m, y_m, ts, source):
        # When user leaves a zone
        if self.server:
            self.server.stop_zone_dj_demo()
```

**Configuration:**

- `zonedj.default_zone_radius_m = 0.25`
- `zonedj.t_register_ms = 3000`
- `zonedj.t_deregister_ms = 1000`

**Playlist Management (Simulated):**

- Each zone maintains its own queue (UI only)
- Queue is initialized when zone is created (default playlist or user-assigned)
- Audio commands are logged via server methods (no actual playback)
- Commands logged to console for demonstration purposes

---

## 4. Services Architecture

### 4.1 SettingsService

**Purpose:** Centralized configuration management using QSettings (INI file or registry).

**Responsibilities:**

- Load/save application settings
- Provide default values
- Support hierarchical keys (e.g., `world.width_m`)
- Persist user preferences across sessions

**Configuration Structure:**

```ini
[world]
width_m = 4.80
height_m = 6.00

[grid]
cols = 8
rows = 10
cell_m = 0.60

[adaptive]
split_y_m = 3.00
t_register_ms = 3000
t_deregister_ms = 1000

[zonedj]
default_zone_radius_m = 0.25
t_register_ms = 3000
t_deregister_ms = 1000

[pgo]
refresh_rate_fps = 30
max_history_points = 1000

[server]
simulation_speed = 1.0
phone_node_id = 0
poll_rate_hz = 20
```

---

## 5. Shared Components

### 5.1 FloorplanView (`viz_floorplan` package)

**Purpose:** Reusable floorplan visualization component with homography mapping and zone management.

**Features:**

- Image loading and display
- 4-point corner marking (manual or auto-detect)
- Homography computation (world↔image transformation)
- Grid projection (8×10 cells, perspective-correct)
- Circular zone placement and management
- Pointer visualization (red dot, world coordinates)
- Zone registration/deregistration timers
- Fade animations for zone state changes

**API:**

```python
class FloorplanView(QGraphicsView):
    def load_image(self, filename: str) -> bool
    def start_marking_corners(self)
    def auto_detect_corners(self) -> bool
    def map_pointer(self, x_m: float, y_m: float)
    def place_zone(self, x_m: float, y_m: float, radius_m: float) -> Zone
    def clear_zones(self)
    pointerMapped = Signal(float, float)  # x_m, y_m when user clicks
    zoneRegistered = Signal(Zone)
    zoneDeregistered = Signal(Zone)
```

**World Coordinate System:**

- Origin: Top-left corner
- X-axis: Increases rightward (0.0 → 4.80 m)
- Y-axis: Increases downward (0.0 → 6.00 m)
- Units: Meters (all internal calculations use meters)

### 5.2 MiniPlayer (`adaptive_audio_widget` / `zone_dj_widget`)

**Purpose:** Compact audio player control widget for sidebar display.

**Features:**

- Current song display (artist - title)
- Play/pause button
- Skip button (next song)
- Volume slider (0-100)
- Queue display (scrollable list)
- Progress indicator (optional)

**Signals:**

```python
playRequested = Signal()
pauseRequested = Signal()
skipRequested = Signal()
volumeChanged = Signal(int)  # 0-100
```

**Usage:**

- Embedded in Adaptive Audio and Zone DJ widgets
- Connected to AppBus for audio command emission
- Can be replaced with custom player implementation

---

## 6. Integration Points

### 6.1 DummyServerBringUpProMax Integration

**Purpose:** The Application Layer reads position data directly from DummyServerBringUpProMax attributes.

**Integration Pattern:**

1. MainWindow creates `DummyServerBringUpProMax` instance
2. MainWindow calls `server.start()` to begin simulation
3. QTimer polls `server.user_position` attribute (20Hz)
4. MainWindow emits `AppBus.pointerUpdated` when position changes
5. Widgets receive updates via AppBus signals

**Startup Sequence:**

```python
# In MainWindow.__init__
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Load settings
        self.settings = load_settings()

        # Create AppBus
        self.bus = AppBus()

        # Create and start server
        self.server = DummyServerBringUpProMax(
            simulation_speed=self.settings.value("server/simulation_speed", 1.0, type=float),
            phone_node_id=self.settings.value("server/phone_node_id", 0, type=int)
        )
        self.server.start()

        # Build services dictionary (passed to widgets)
        self.services = {
            "server": self.server,  # Widgets can access server for audio methods
            "settings": self.settings
        }

        # Setup position polling
        self._last_position = None
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_server_position)
        poll_interval_ms = 1000 // self.settings.value("server/poll_rate_hz", 20, type=int)
        self._poll_timer.start(poll_interval_ms)  # Default: 50ms = 20Hz

        # Build widgets (they receive server via services dict)
        self._build_tabs()

    def _build_tabs(self):
        # Widgets receive server instance via services
        self.tab_pgo = PgoPlotWidget(self.bus, self.services, self.settings)
        self.tab_adaptive = AdaptiveAudioWidget(self.bus, self.services, self.settings)
        self.tab_zonedj = ZoneDjWidget(self.bus, self.services, self.settings)

        self.tabs.addTab(self.tab_pgo, "PGO Data")
        self.tabs.addTab(self.tab_adaptive, "Adaptive Audio")
        self.tabs.addTab(self.tab_zonedj, "Zone DJ")
```

**Accessible Attributes:**

- `server.user_position` - np.ndarray [x, y, z] in cm (thread-safe with `_position_lock`)
- `server.data` - Dict[int, BinnedData] - latest binned measurement data
- `server.nodes` - Dict[int, np.ndarray] - anchor positions in cm
- `server.simulation_speed` - float - simulation speed multiplier

**Audio Demo Methods (from PR #15):**

- `server.adaptive_audio_demo()` - Start adaptive audio demo (simulates position-based audio)
- `server.stop_adaptive_audio_demo()` - Stop adaptive audio demo
- `server.zone_dj_demo()` - Start zone DJ demo (simulates multi-zone audio)
- `server.stop_zone_dj_demo()` - Stop zone DJ demo
- `server.set_playlist(playlist_number: int)` - Set playlist (1-5)

**Note:** Audio methods log commands instead of actual playback. This provides a simulation/demonstration of audio control functionality.

**Thread Safety Warning:**
These audio methods modify internal state variables (`self.volumes`, `self.current_pair`, etc.) that are **not protected by locks**. They should only be called from the main Qt thread (where widgets run). Since Qt widget event handlers (button clicks, etc.) run on the main thread by default, direct calls from widgets are safe. However, for production use or if calling from background threads, consider:

1. Using Qt signals to invoke methods safely:
   
   ```python
   # Option 1: Add signals to DummyServer (inherit from QObject)
   self.server.audioCommandRequested.emit("adaptive_start", {})
   ```

# Option 2: Use QMetaObject.invokeMethod

QMetaObject.invokeMethod(self.server, "adaptive_audio_demo", Qt.QueuedConnection)

```
2. Adding explicit locks to audio methods:
```python
def adaptive_audio_demo(self):
    with self._audio_lock:  # Add this lock
        # ... audio control logic ...
```

For the current demonstration purposes where widgets call these methods from button click handlers (main thread), the implementation is adequate.

**Thread Safety:**

```python
def _poll_server_position(self):
    # Always use lock when accessing server.user_position
    with self.server._position_lock:
        position = self.server.user_position

    if position is not None:
        # Convert cm to meters
        x_m = position[0] / 100.0
        y_m = position[1] / 100.0

        # Emit only if changed (reduce redundant updates)
        if self._last_position is None or not np.allclose(position[:2], self._last_position):
            ts = time.time()
            self.bus.pointerUpdated.emit(x_m, y_m, ts, "server")
            self._last_position = position[:2].copy()
```

---

## 7. Extension Patterns

### 7.1 Adding a New Widget

**Steps:**

1. Create new package: `packages/my_new_widget/`

2. Implement widget class following `BaseWidget` interface

3. Add widget loading function in `main_demo.py`:
   
   ```python
   def _load_my_widget(app_bus, services, settings):
       from my_new_widget import MyNewWidget
       return MyNewWidget(app_bus, services, settings)
   ```

4. Add tab in `MainWindow._build_tabs()`:
   
   ```python
   self.tab_mynew = _load_my_widget(self.bus, self.services, self.settings)
   self.tabs.addTab(self.tab_mynew, "My New Widget")
   ```

### 7.2 Adding New AppBus Signals

**Steps:**

1. Add signal definition to `AppBus` class
2. Update documentation (this document)
3. Emit signal from appropriate component (service or widget)
4. Connect to signal in widgets that need it

**Example:**

```python
# In appbus.py
class AppBus(QObject):
    # ... existing signals ...
    serverErrorOccurred = Signal(str, str)  # New signal: error_type, message

# In MainWindow (when polling detects error)
if self.server.user_position is None:
    self.bus.serverErrorOccurred.emit("position_unavailable", "Server not ready")

# In widget
self.bus.serverErrorOccurred.connect(self._on_server_error)
```

### 7.3 Adding New Services

**Steps:**

1. Create service class (inherit from `QObject` if needed)
2. Add service to `MainWindow.services` dict
3. Inject service into widgets via constructor
4. Document service API and configuration

**Example:**

```python
# In MainWindow.__init__
self.logging_service = LoggingService(self.bus, self.settings)
self.services["logging"] = self.logging_service

# In widget
def __init__(self, app_bus, services, settings, parent=None):
    self.logger = services.get("logging")
```

---

## 8. Performance Considerations

### 8.1 Update Rate Limiting

**Problem:** High-frequency position updates can cause UI jank.

**Solution:**

- Accumulate updates in widget (queue or latest-value)
- Redraw at fixed interval (30-60 FPS) using `QTimer`
- Drop intermediate updates if queue is full

**Implementation:**

```python
class PgoPlotWidget(QWidget):
    def __init__(self, ...):
        self._update_queue = []
        self._redraw_timer = QTimer()
        self._redraw_timer.timeout.connect(self._redraw_plot)
        self._redraw_timer.start(33)  # ~30 FPS

    def _on_pointer_updated(self, x_m, y_m, ts, source):
        self._update_queue.append((x_m, y_m, ts))
        # Don't redraw immediately

    def _redraw_plot(self):
        # Process all queued updates
        for x_m, y_m, ts in self._update_queue:
            self._add_point(x_m, y_m)
        self._update_queue.clear()
        self.canvas.draw()
```

### 8.2 Memory Management

**Problem:** Unbounded history can cause memory growth.

**Solution:**

- Limit history buffer size (e.g., 1000 points)
- Use circular buffer or FIFO queue
- Periodically clear old data

### 8.3 Thread Safety

**Problem:** Server runs background threads, but Qt widgets must be updated from main thread.

**Solution:**

- Use Qt signals with queued connections (automatic)
- Never access Qt widgets directly from background threads
- Use `QMetaObject.invokeMethod()` if needed for complex operations

**Known Limitation - Audio Method Calls:**

- Audio methods (`adaptive_audio_demo()`, etc.) in `DummyServerBringUpProMax` are not thread-safe
- They modify internal state without locks (`self.volumes`, `self.current_pair`)
- **Safe**: Calling from widget event handlers (main thread) ✅
- **Unsafe**: Calling from timers or background threads without proper synchronization ❌

**Recommendation for production:**

```python
# Add QObject inheritance and signals to DummyServer
class DummyServerBringUpProMax(QObject):
    audioCommandRequested = pyqtSignal(str, dict)

    def __init__(self, ...):
        super().__init__()
        self.audioCommandRequested.connect(self._handle_audio_command)

    @pyqtSlot(str, dict)
    def _handle_audio_command(self, command, params):
        # Thread-safe handler
        pass

# From widget (any thread)
self.server.audioCommandRequested.emit("adaptive_start", {})
```

---

## 9. Testing Strategy

### 9.1 Unit Testing

**Widget Tests:**

- Mock AppBus (create test AppBus with signal spies)
- Mock services (create minimal service implementations with mock server)
- Test widget initialization, signal connections, UI updates
- Test widget responses to `pointerUpdated` signals
- Test direct server method calls (audio control)

**Server Tests:**

- Test DummyServerBringUpProMax initialization
- Test position simulation (figure-8 pattern generation)
- Test thread-safe attribute access (`user_position` with lock)
- Test audio method calls (verify logging output)
- Test PGO processing and position updates

### 9.2 Integration Testing

**End-to-End Tests:**

- Start MainWindow with DummyServerBringUpProMax
- Verify position polling loop (QTimer → AppBus → widgets)
- Inject test AppBus events to verify widget responses
- Test zone registration/deregistration logic
- Verify audio method calls reach server and log correctly
- Test services dictionary injection (widgets can access server)
- Verify thread-safe server attribute access from MainWindow polling

### 9.3 UI Testing

**Manual Testing:**

- Load floorplan images
- Test corner marking and auto-detection
- Test zone placement and dragging
- Test pointer tracking and zone registration
- Test audio control buttons (verify console logs)
- Test playlist selection (verify server method calls)
- Verify position updates in real-time (figure-8 pattern)
- Test simulation speed controls

---

## 10. Deployment Considerations

### 10.1 Dependencies

**Required Packages:**

- PyQt5 (>= 5.15.11)
- numpy (>= 1.24.0)
- scipy (>= 1.10.0)
- matplotlib (>= 3.5.0) or pyqtgraph
- opencv-python (>= 4.11.0.86)

**Installation:**

```bash
# Install from repository root
pip install -e .

# Or install individual packages
pip install -e packages/pgo_data_widget
pip install -e packages/adaptive_audio_widget
pip install -e packages/zone_dj_widget
pip install -e packages/viz_floorplan
pip install -e packages/datatypes
pip install -e packages/localization_algos
```

### 10.2 Configuration

**Settings File Location:**

- Windows: `%APPDATA%/uwb-localization-mesh/settings.ini`
- Linux: `~/.config/uwb-localization-mesh/settings.ini`
- macOS: `~/Library/Preferences/uwb-localization-mesh/settings.ini`

**Default Settings:**

- World dimensions: 4.80 m × 6.00 m
- Grid: 8×10 cells (0.60 m per cell)
- Simulation speed: 1.0x
- Polling rate: 20 Hz
- PGO refresh rate: 30 FPS

### 10.3 Running the Application

**Command Line:**

```bash
# From repository root
python Demos/UnifiedDemo/main_demo.py

# With custom simulation speed
python Demos/UnifiedDemo/main_demo.py --speed 2.0

# With specific settings file
python Demos/UnifiedDemo/main_demo.py --settings /path/to/settings.ini

# Or run from Demos directory with fixed import
cd Demos
python -m UnifiedDemo.main_demo
```

**Architecture:**

- Uses `DummyServerBringUpProMax` for simulation (no hardware needed)
- Self-contained Python application
- Direct attribute polling for data access

---

## 11. Future Enhancements

### 11.1 Potential Improvements

1. **3D Visualization:** Add Z-axis support for multi-floor tracking
2. **Multi-User Support:** Track multiple users simultaneously
3. **Advanced Analytics:** Historical data analysis, heatmaps, path optimization
4. **Custom Zone Shapes:** Support rectangles, polygons, complex shapes
5. **Audio Sync:** Synchronize audio playback across multiple zones
6. **Web Interface:** Add web-based dashboard for remote monitoring
7. **Recording/Playback:** Record position data and replay for testing
8. **Export/Import:** Save/load floorplan configurations and zone definitions

### 11.2 Performance Optimizations

1. **PyQtGraph Migration:** Replace matplotlib with PyQtGraph for better performance
2. **GPU Acceleration:** Use OpenGL for rendering large floorplans
3. **Data Compression:** Compress historical data for long-running sessions
4. **Lazy Loading:** Load floorplan images on-demand

---

## 12. Glossary

- **AppBus:** Qt signal hub for intra-application event routing
- **DummyServerBringUpProMax:** Simulation server providing UWB position data and audio demo methods
- **Homography:** 3×3 transformation matrix mapping world coordinates to image pixels
- **PGO:** Pose Graph Optimization, algorithm for estimating user position from UWB measurements
- **Zone:** A defined region in world space (circular or rectangular) that triggers events when user enters/exits
- **Registration:** Event triggered when user enters a zone (after hover threshold)
- **Deregistration:** Event triggered when user exits a zone (after leave threshold)
- **FloorplanView:** Reusable widget for displaying floorplan images with world coordinate mapping
- **MiniPlayer:** Compact audio player control widget
- **Services Dictionary:** Dict passed to widgets containing server instance and settings
- **Polling:** MainWindow QTimer-based reading of server.user_position attribute (20Hz)

---

## 13. References

- [Unified Demo Proposal](../unified_demo_proposal.md)
- [Architecture Documentation](../UnifiedDemo/docs/Architecture.md)
- [AppBus Documentation](../UnifiedDemo/appbus.md)
- [Services Documentation](../UnifiedDemo/services/README.md)
- [PyQt5 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt5/)

---

---

## 14. Integration Summary

### Data Flow: Two Patterns

**Pattern 1: Position Updates (Polling)**

```
DummyServer → MainWindow polls → AppBus → Widgets subscribe
(background)   (QTimer 20Hz)    (signals)  (visualization)
```

**Pattern 2: Audio Control (Direct Method Calls)**

```
Widget UI → services["server"].method() → DummyServer logs
(buttons)   (direct call)                (simulation)
```

### Key Architectural Decisions

1. **Direct Integration**: Attribute polling and direct method calls (no message broker)
2. **Server in Services Dict**: Widgets access server via `services["server"]`
3. **Dual Communication**: 
   - Position: AppBus signals (decoupled, one-way broadcast)
   - Audio: Direct method calls (simple, synchronous)
4. **Thread Safety**: All server attribute access uses `_position_lock`
5. **Audio Simulation**: Methods log commands for demonstration

### Widget-Server Integration

All widgets receive server instance:

```python
def __init__(self, app_bus, services, settings, parent=None):
    self.server = services.get("server")  # DummyServerBringUpProMax
```

Widgets can:

- Subscribe to `AppBus.pointerUpdated` for position data
- Call `self.server.adaptive_audio_demo()` for audio control
- Call `self.server.set_playlist(n)` for playlist changes
- Access `self.server.user_position` (if needed, with lock)

---

**Document Version:** 2.2  
**Last Updated:** 2025-01-11  
**Author:** Architecture Planning Team  
**References:** [PR #15 - DummyServer Implementation](https://github.com/Hong-yiii/uwb-localization-mesh/pull/15)

**Change Log:**

- v2.1: Added thread safety limitations for audio method calls
- v2.0: Removed all MQTT references - direct integration only
- v1.1: Added audio demo methods from PR #15
- v1.0: Initial architecture plan
