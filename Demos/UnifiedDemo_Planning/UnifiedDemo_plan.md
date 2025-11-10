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

- **Inbound (Server → Widgets)**: MainWindow polls `server.user_position`, emits `AppBus.pointerUpdated` to widgets
- **Outbound (Widgets → Server)**: Widgets emit audio commands to AppBus, MainWindow routes to server methods
- **Cross-Widget**: Widgets emit event callbacks to AppBus for inter-widget communication
- **Thread Safety**: Qt signal system ensures all server calls happen on main thread
- Self-contained Python application (no external brokers needed)

**Core Features:**

- ✅ PGO Data Widget (real-time position plotting)
- ✅ Adaptive Audio Widget (2-zone visualization + simulated audio control)
- ✅ Zone DJ Widget (user-defined zones + simulated audio control)
- ✅ FloorplanView (homography, zones, pointer tracking)
- ✅ DummyServer simulation (figure-8 pattern)
- ✅ Audio demo methods (`adaptive_audio_demo()`, `zone_dj_demo()`, `set_playlist()`)
- ✅ AppBus signal routing for ALL communication (position, commands, events)
- ✅ Thread-safe via Qt signal system (automatic main thread delivery)
- ✅ MainWindow routes AppBus signals to server methods
- ✅ Cross-widget communication via AppBus event callbacks
- ✅ Status bar showing position and server status

**Implementation Notes:**

- Audio control is simulated (commands are logged only)
- No external hardware integration in this design
- ALL communication flows through AppBus (consistent pattern)
- Position data via polling + Qt signals
- Audio commands via Qt signals + MainWindow routing

**Thread Safety (Solved via AppBus):**

- ✅ **Recommended**: Route all audio commands through AppBus signals
- ✅ MainWindow receives AppBus signals on main thread, then calls server methods
- ✅ Qt signal system automatically ensures thread-safe delivery
- ✅ Audio state variables in DummyServer accessed only from main thread
- ✅ No locks needed when using AppBus pattern
- ⚠️ **Deprecated**: Direct widget→server calls (bypasses AppBus, not thread-safe if called from timers/threads)

---

## 1. System Overview

### 1.0 Package Structure

The application follows a strict hierarchical structure with NO duplication:

```
packages/
├── mini_player/                    # SHARED SUBWIDGET (single implementation)
│   └── mini_player.py             # Compact audio player UI component
│
├── viz_floorplan/                  # SHARED SUBWIDGET (single implementation)
│   └── floorplan_view.py          # Floorplan visualization with homography
│
├── adaptive_audio_widget/          # WIDGET LAYER
│   └── adaptive_audio_widget.py   # Instantiates: viz_floorplan, mini_player
│
├── zone_dj_widget/                 # WIDGET LAYER
│   └── zone_dj_widget.py          # Instantiates: viz_floorplan, mini_player
│
├── pgo_data_widget/                # WIDGET LAYER
│   └── pgo_plot_widget.py         # Real-time position plotting
│
└── [other packages: datatypes, localization_algos, etc.]

Demos/
└── UnifiedDemo/
    └── main_demo.py                # TOP LAYER (MainWindow)
                                    # Instantiates all widgets
```

**Critical Rules:**

1. ❌ NO `adaptive_audio_widget/mini_player.py` 
2. ❌ NO `zone_dj_widget/mini_player.py`
3. ✅ Only ONE `packages/mini_player/mini_player.py`
4. ✅ Widgets import and instantiate with different parameters

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
          │  Direct attribute polling for position      │
          │  AppBus signals for ALL commands/events     │
          │  DummyServer runs in same Python process    │
          │  Thread-safe: Qt signals + attribute locks  │
          │  MainWindow routes AppBus → Server calls    │
          └─────────────────────────────────────────────┘
```

### 1.2 Component Responsibilities

| Component                    | Responsibility                                         | Dependencies                                   | Layer          |
| ---------------------------- | ------------------------------------------------------ | ---------------------------------------------- | -------------- |
| **MainWindow (main_demo)**   | Application shell, server polling, widget coordination | QApplication, AppBus, DummyServerBringUpProMax | Top Layer      |
| **AppBus**                   | Event routing, decoupling widgets from data source     | Qt Core (QObject, Signal)                      | Infrastructure |
| **SettingsService**          | Configuration management                               | QSettings                                      | Infrastructure |
| **PgoPlotWidget**            | Real-time position plotting, diagnostics               | AppBus, matplotlib/pyqtgraph                   | Widget Layer   |
| **AdaptiveAudioWidget**      | Fixed 2-zone follow-me visualization + audio control   | AppBus, viz_floorplan, mini_player             | Widget Layer   |
| **ZoneDjWidget**             | User-defined zones + audio control                     | AppBus, viz_floorplan, mini_player             | Widget Layer   |
| **FloorplanView**            | Floorplan visualization, homography, zones             | PyQt5, OpenCV, numpy                           | Subwidget      |
| **MiniPlayer**               | Compact audio player UI (shared component)             | PyQt5                                          | Subwidget      |
| **DummyServerBringUpProMax** | UWB simulation, PGO processing, audio demo simulation  | numpy, scipy, packages.*                       | Data Source    |

### 1.3 Component Hierarchy

The application follows a three-layer widget architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│  TOP LAYER: main_demo.py (MainWindow)                           │
│  - Creates widgets, passes data down                            │
│  - Polls DummyServerBringUp, emits AppBus signals               │
│  - Receives widget callbacks/events, routes to server           │
└─────────────────────────────────────────────────────────────────┘
                              ↓ data flow
                              ↑ events/callbacks
┌─────────────────────────────────────────────────────────────────┐
│  WIDGET LAYER: adaptive_audio_widget, zone_dj_widget, pgo_data │
│  - Implement specific visualization/interaction paradigms       │
│  - Invoke subwidgets with specific parameters                   │
│  - Emit events back to main_demo                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓ instantiate & configure
                              ↑ UI events
┌─────────────────────────────────────────────────────────────────┐
│  SUBWIDGET LAYER: viz_floorplan, mini_player (SHARED)          │
│  - Reusable UI components (NO duplication)                      │
│  - Parameterized by parent widgets                              │
│  - Single implementation per component                          │
└─────────────────────────────────────────────────────────────────┘
```

**Key Principles:**

- **No Duplication**: `mini_player` and `viz_floorplan` are single shared implementations
- **Parameterization**: Widgets configure subwidgets with specific parameters
- **Data Down, Events Up**: Data flows down the hierarchy, events/callbacks flow up
- **Clear Separation**: Each layer has distinct responsibilities

---

## 2. Communication Architecture

### 2.1 AppBus Pattern

The **AppBus** is a Qt signal hub that implements a publish-subscribe pattern for intra-application communication. It decouples producers (MainWindow polling server) from consumers (widgets) and ensures thread-safe event delivery.

**Implementation:**

```python
class AppBus(QObject):
    # ============================================================
    # POSITION & TRACKING DATA (Server → Widgets)
    # ============================================================
    pointerUpdated = Signal(float, float, float, str)  # x_m, y_m, ts, source

    # ============================================================
    # ZONE EVENTS (Widgets → AppBus → Logging/Status)
    # ============================================================
    zoneRegistered = Signal(object, float, float, float, str)  # idx, x_m, y_m, ts, source
    zoneDeregistered = Signal(object, float, float, float, str)
    zoneSelected = Signal(object)  # zone object
    zoneCreated = Signal(object)  # zone object
    zoneDeleted = Signal(object)  # zone object
    zoneMoved = Signal(object, float, float)  # zone, new_x, new_y

    # ============================================================
    # PLAYBACK CONTROL COMMANDS (Widgets → MainWindow → Server)
    # ============================================================
    playRequested = Signal(str)           # source widget_id
    pauseRequested = Signal(str)          # source widget_id
    stopRequested = Signal(str)           # source widget_id
    skipRequested = Signal(str)           # source widget_id (next track)
    previousRequested = Signal(str)       # source widget_id (previous track)
    seekRequested = Signal(str, float)    # source, position (0.0-1.0)

    # ============================================================
    # AUDIO MODE COMMANDS (Widgets → MainWindow → Server)
    # ============================================================
    audioStartRequested = Signal(str, dict)  # mode ("adaptive"|"zone_dj"), params
    audioStopRequested = Signal(str)  # mode ("adaptive"|"zone_dj")
    adaptiveAudioEnabled = Signal(bool)   # enable/disable adaptive audio
    zoneDjEnabled = Signal(bool)          # enable/disable zone DJ
    bypassAudioRequested = Signal(bool)   # bypass all audio processing

    # ============================================================
    # PLAYLIST & VOLUME COMMANDS (Widgets → MainWindow → Server)
    # ============================================================
    playlistChangeRequested = Signal(int)  # playlist_number (1-5)
    playlistSelected = Signal(int)         # playlist_id
    shuffleToggled = Signal(bool)          # shuffle on/off
    repeatToggled = Signal(bool)           # repeat on/off
    volumeChangeRequested = Signal(int, int)  # device_id, volume (0-100); device_id=-1 for all
    globalVolumeChanged = Signal(int)      # master volume (0-100)

    # ============================================================
    # PLAYBACK STATE UPDATES (MainWindow → Widgets, bidirectional)
    # ============================================================
    playbackStateChanged = Signal(str, bool)  # widget_id, is_playing
    trackChanged = Signal(str, int)        # track_name, track_index
    playbackProgressChanged = Signal(float)  # progress 0.0-1.0
    queueUpdated = Signal(list, str)       # queue_preview (list of songs), current_track

    # ============================================================
    # VOLUME STATE UPDATES (MainWindow → Widgets)
    # ============================================================
    volumeUpdated = Signal(int, int)       # device_id, volume
    globalVolumeUpdated = Signal(int)      # master volume
    speakerVolumesUpdated = Signal(dict)   # {speaker_id: volume, ...} - all speaker volumes at once

    # ============================================================
    # SERVER & SIMULATION STATUS
    # ============================================================
    serverStatusChanged = Signal(str)      # "running", "stopped", "error", "audio_playing"
    simulationSpeedChanged = Signal(float)  # speed multiplier

    # ============================================================
    # FLOORPLAN INTERACTION EVENTS
    # ============================================================
    floorplanCornerMarked = Signal(int, float, float)  # corner_idx, x_px, y_px
    floorplanImageLoaded = Signal(str)     # image_path
    homographyComputed = Signal(object)    # homography_matrix (np.ndarray)

    # ============================================================
    # SETTINGS & CONFIGURATION
    # ============================================================
    settingsChanged = Signal(str, object)  # setting_key, value
```

**Usage Pattern:**

**Data Flow (Server → Widgets):**

1. **MainWindow** creates and starts `DummyServerBringUpProMax` instance
2. **QTimer** (in MainWindow) polls `server.user_position` attribute periodically (50ms = 20Hz)
3. When position changes, **MainWindow** emits `AppBus.pointerUpdated(x_m, y_m, ts, "server")`
4. **Widgets** connect to `pointerUpdated` and update their visualizations

**Command Flow (Widgets → Server):**

1. **Widgets** emit audio command signals to AppBus (e.g., `audioStartRequested.emit("adaptive", {})`)
2. **MainWindow** connects AppBus signals to server methods (acts as router)
3. **MainWindow** calls server methods on main thread (thread-safe)
4. **Widgets** emit event callbacks to AppBus for cross-widget communication

**Benefits:**

- **Loose Coupling**: Widgets don't know about server implementation
- **Testability**: Widgets can be tested with mock AppBus
- **Thread Safety**: ALL communication through Qt signals (automatic thread-safe delivery)
- **Consistency**: Same pattern for both inbound data and outbound commands
- **Extensibility**: New widgets can be added without modifying existing code
- **Simplicity**: Self-contained application, no external dependencies
- **Cross-Widget Communication**: Widgets can communicate via AppBus without direct references

### 2.2 Data Flow Patterns

#### 2.2.1 Complete Data Flow: Down and Up

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA FLOW DOWN (Polling)                      │
└─────────────────────────────────────────────────────────────────┘

DummyServerBringUpProMax (background threads)
    │
    │ - Simulates user movement (figure-8 pattern)
    │ - Processes UWB measurements
    │ - Runs PGO solver
    │ - Updates self.user_position attribute (thread-safe with lock)
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
    │   └─→ matplotlib/pyqtgraph subwidgets
    │
    ├─→ AdaptiveAudioWidget (updates floorplan pointer)
    │   ├─→ FloorplanView subwidget (render pointer)
    │   └─→ MiniPlayer subwidget (display state)
    │
    └─→ ZoneDjWidget (updates floorplan pointer)
        ├─→ FloorplanView subwidget (render pointer)
        └─→ MiniPlayer subwidget (display state)

┌─────────────────────────────────────────────────────────────────┐
│              EVENT FLOW UP (Callbacks/Events/Commands)           │
└─────────────────────────────────────────────────────────────────┘

User Interaction (button click, slider, etc.)
    ↓
Subwidget (MiniPlayer, FloorplanView)
    │ - Emits Qt signal (e.g., playRequested, volumeChanged)
    ↓
Widget Layer (AdaptiveAudioWidget, ZoneDjWidget)
    │ - Receives signal from subwidget
    │ - Processes event (determine which action needed)
    │ - Emits to AppBus (for ALL commands and callbacks)
    ↓
AppBus (signal routing hub)
    │ - audioStartRequested, playlistChangeRequested, etc.
    │ - playbackStateChanged, zoneSelected (for cross-widget communication)
    ↓
MainWindow (connected to AppBus signals)
    │ - Receives AppBus signals on main thread
    │ - Routes to appropriate handler
    │ - Calls server methods (thread-safe, on main thread)
    ↓
DummyServerBringUpProMax
    │ - adaptive_audio_demo()
    │ - zone_dj_demo()
    │ - set_playlist()
    └─→ Logs audio commands (simulated control)

Example: Play Button Click (Recommended Pattern)
    User clicks "Play" in MiniPlayer
    → MiniPlayer.playRequested.emit()
    → AdaptiveAudioWidget._on_play() receives signal
    → self.bus.audioStartRequested.emit("adaptive", {})  # Emit to AppBus
    → MainWindow._on_audio_start_requested("adaptive", {})  # Receives on main thread
    → self.server.adaptive_audio_demo()  # Thread-safe call
    → DummyServer logs audio command
    → (Optional) self.bus.playbackStateChanged.emit("adaptive_widget", True)

Example: Cross-Widget Communication
    User marks corner in AdaptiveAudioWidget
    → FloorplanView.cornerMarked.emit(0, 100.5, 200.3)
    → AdaptiveAudioWidget._on_corner_marked(...)
    → self.bus.floorplanCornerMarked.emit(0, 100.5, 200.3)  # Broadcast
    → ZoneDjWidget._on_corner_marked(...) receives update
    → ZoneDjWidget updates its floorplan accordingly
```

**Implementation in MainWindow:**

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Create AppBus
        self.bus = AppBus()

        # Start server
        self.server = DummyServerBringUpProMax(
            simulation_speed=1.0,
            phone_node_id=0
        )
        self.server.start()

        # Connect AppBus audio command signals to server methods
        self.bus.audioStartRequested.connect(self._on_audio_start_requested)
        self.bus.audioStopRequested.connect(self._on_audio_stop_requested)
        self.bus.playlistChangeRequested.connect(self._on_playlist_change_requested)
        self.bus.volumeChangeRequested.connect(self._on_volume_change_requested)

        # Setup polling timer for position data
        self._last_position = None
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_server_position)
        self._poll_timer.start(50)  # 20Hz polling

    def _poll_server_position(self):
        """Poll server position and emit to AppBus (data down)."""
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

    # Audio command handlers (route AppBus → Server)
    @pyqtSlot(str, dict)
    def _on_audio_start_requested(self, mode: str, params: dict):
        """Handle audio start request from widgets via AppBus."""
        if mode == "adaptive":
            self.server.adaptive_audio_demo()
        elif mode == "zone_dj":
            self.server.zone_dj_demo()
        # Update status
        self.bus.serverStatusChanged.emit("audio_playing")

    @pyqtSlot(str)
    def _on_audio_stop_requested(self, mode: str):
        """Handle audio stop request from widgets via AppBus."""
        if mode == "adaptive":
            self.server.stop_adaptive_audio_demo()
        elif mode == "zone_dj":
            self.server.stop_zone_dj_demo()
        self.bus.serverStatusChanged.emit("audio_stopped")

    @pyqtSlot(int)
    def _on_playlist_change_requested(self, playlist_number: int):
        """Handle playlist change request from widgets via AppBus."""
        self.server.set_playlist(playlist_number)

    @pyqtSlot(int, int)
    def _on_volume_change_requested(self, device_id: int, volume: int):
        """Handle volume change request from widgets via AppBus."""
        # Could add volume control method to server if needed
        pass
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

**Complete Integration Example (AdaptiveAudioWidget):**

```python
class AdaptiveAudioWidget(QWidget):
    def __init__(self, app_bus, services, settings, parent=None):
        super().__init__(parent)
        self.bus = app_bus
        self.settings = settings
        # Note: No direct server access needed!

        # Create subwidgets
        self._setup_ui()

        # Connect subwidget signals to handlers
        self._connect_mini_player_signals()

        # Subscribe to AppBus state updates
        self._connect_appbus_signals()

    def _setup_ui(self):
        """Create UI components."""
        # Create floorplan view
        from packages.viz_floorplan import FloorplanView
        self.floorplan = FloorplanView(parent=self)

        # Create mini player
        from packages.mini_player import MiniPlayer
        self.mini_player = MiniPlayer(
            mode="adaptive",
            show_queue=True,
            parent=self
        )

        # Create enable/bypass controls
        self.enable_checkbox = QCheckBox("Enable Adaptive Audio")
        self.bypass_checkbox = QCheckBox("Bypass Audio Processing")

        # Layout
        layout = QHBoxLayout()
        layout.addWidget(self.floorplan, stretch=3)

        sidebar = QVBoxLayout()
        sidebar.addWidget(self.enable_checkbox)
        sidebar.addWidget(self.bypass_checkbox)
        sidebar.addWidget(self.mini_player)
        layout.addLayout(sidebar, stretch=1)

        self.setLayout(layout)

    def _connect_mini_player_signals(self):
        """Connect mini_player signals to handlers."""
        # Playback controls
        self.mini_player.playRequested.connect(self._on_play)
        self.mini_player.pauseRequested.connect(self._on_pause)
        self.mini_player.stopRequested.connect(self._on_stop)
        self.mini_player.skipRequested.connect(self._on_skip)
        self.mini_player.previousRequested.connect(self._on_previous)
        self.mini_player.seekRequested.connect(self._on_seek)

        # Volume control
        self.mini_player.volumeChanged.connect(self._on_volume_changed)

        # Playlist control
        self.mini_player.playlistSelected.connect(self._on_playlist_selected)

        # Enable/bypass controls
        self.enable_checkbox.toggled.connect(self._on_enable_toggled)
        self.bypass_checkbox.toggled.connect(self._on_bypass_toggled)

    def _connect_appbus_signals(self):
        """Subscribe to AppBus state updates."""
        # Position updates
        self.bus.pointerUpdated.connect(self._on_pointer_updated)

        # Playback state updates
        self.bus.queueUpdated.connect(self._on_queue_updated)
        self.bus.trackChanged.connect(self._on_track_changed)
        self.bus.playbackProgressChanged.connect(self._on_progress_changed)
        self.bus.playbackStateChanged.connect(self._on_playback_state_changed)

        # Volume updates
        self.bus.volumeUpdated.connect(self._on_volume_updated)

        # Zone events
        self.bus.zoneRegistered.connect(self._on_zone_registered)
        self.bus.zoneDeregistered.connect(self._on_zone_deregistered)

    # ================================================================
    # CONTROL HANDLERS (Emit to AppBus)
    # ================================================================
    def _on_play(self):
        """Handle play button click."""
        self.bus.playRequested.emit("adaptive_widget")
        # Start adaptive audio demo
        self.bus.audioStartRequested.emit("adaptive", {})

    def _on_pause(self):
        """Handle pause button click."""
        self.bus.pauseRequested.emit("adaptive_widget")

    def _on_stop(self):
        """Handle stop button click."""
        self.bus.stopRequested.emit("adaptive_widget")
        # Stop adaptive audio demo
        self.bus.audioStopRequested.emit("adaptive")

    def _on_skip(self):
        """Handle skip button click."""
        self.bus.skipRequested.emit("adaptive_widget")

    def _on_previous(self):
        """Handle previous button click."""
        self.bus.previousRequested.emit("adaptive_widget")

    def _on_seek(self, position: float):
        """Handle seek slider."""
        self.bus.seekRequested.emit("adaptive_widget", position)

    def _on_volume_changed(self, volume: int):
        """Handle volume slider change."""
        # Set volume for all speakers in adaptive mode
        self.bus.volumeChangeRequested.emit(-1, volume)

    def _on_playlist_selected(self, playlist_id: int):
        """Handle playlist selection."""
        self.bus.playlistChangeRequested.emit(playlist_id)

    def _on_enable_toggled(self, checked: bool):
        """Handle enable adaptive audio checkbox."""
        self.bus.adaptiveAudioEnabled.emit(checked)

    def _on_bypass_toggled(self, checked: bool):
        """Handle bypass audio processing checkbox."""
        self.bus.bypassAudioRequested.emit(checked)

    # ================================================================
    # STATE UPDATE HANDLERS (Receive from AppBus)
    # ================================================================
    def _on_pointer_updated(self, x_m: float, y_m: float, ts: float, source: str):
        """Update floorplan pointer."""
        self.floorplan.map_pointer(x_m, y_m)

        # Determine zone (Adaptive: split at y=3.0m)
        if y_m < 3.0:
            zone_id = "A"
        else:
            zone_id = "B"
        # Zone registration logic here...

    def _on_queue_updated(self, queue_preview: list, current_track: str):
        """Update mini_player queue display."""
        self.mini_player.update_queue_list(queue_preview)
        self.mini_player.update_current_track(current_track)

    def _on_track_changed(self, track_name: str, track_index: int):
        """Update current track display."""
        self.mini_player.set_track_name(track_name)

    def _on_progress_changed(self, progress: float):
        """Update playback progress bar."""
        self.mini_player.set_progress(progress)

    def _on_playback_state_changed(self, widget_id: str, is_playing: bool):
        """Update play/pause button state."""
        if widget_id == "adaptive_widget" or widget_id == "main":
            self.mini_player.set_playing_state(is_playing)

    def _on_volume_updated(self, device_id: int, volume: int):
        """Update volume slider."""
        # Update if it's our device or all devices
        if device_id == -1 or device_id in self.active_speakers:
            self.mini_player.set_volume_slider(volume)

    def _on_zone_registered(self, zone_id, x_m, y_m, ts, source):
        """Handle zone registration event."""
        # Update visual feedback
        pass

    def _on_zone_deregistered(self, zone_id, x_m, y_m, ts, source):
        """Handle zone deregistration event."""
        # Update visual feedback
        pass
```

**Why This Architecture is Better:**

- ✅ Thread-safe (Qt signals ensure main thread delivery)
- ✅ Widgets don't need server reference
- ✅ Testable (mock AppBus)
- ✅ Consistent pattern (all communication via AppBus)
- ✅ Complete control surface (all playback features)
- ✅ Bidirectional updates (commands out, state in)

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

**Integration via AppBus (Recommended):**

```python
class ZoneDjWidget(QWidget):
    def __init__(self, app_bus, services, settings, parent=None):
        super().__init__(parent)
        self.bus = app_bus
        # Note: No direct server access needed!

        # Connect to internal zone events
        self.bus.zoneRegistered.connect(self._on_zone_registered)
        self.bus.zoneDeregistered.connect(self._on_zone_deregistered)

    def _on_zone_registered(self, zone_id, x_m, y_m, ts, source):
        """When user enters a zone, emit audio command to AppBus."""
        params = {"zone_id": zone_id, "position": (x_m, y_m)}
        self.bus.audioStartRequested.emit("zone_dj", params)
        # Emit callback for cross-widget communication
        self.bus.zoneSelected.emit(zone_id)

    def _on_zone_deregistered(self, zone_id, x_m, y_m, ts, source):
        """When user leaves a zone, emit stop command to AppBus."""
        self.bus.audioStopRequested.emit("zone_dj")
```

**Why This is Better:**

- ✅ Thread-safe (Qt signals ensure main thread delivery)
- ✅ Widgets don't need server reference
- ✅ Other widgets can listen to `zoneSelected` signal
- ✅ Consistent pattern (all communication via AppBus)

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
- Rectangular zone support (for Adaptive Audio)
- Pointer visualization (red dot, world coordinates)
- Zone registration/deregistration timers
- Fade animations for zone state changes
- Speaker volume visualization (Adaptive Audio only)
  - Speaker icons at corner positions (anchor locations)
  - Real-time volume bars with percentage display
  - Automatic positioning and cleanup

**API:**

```python
class FloorplanView(QGraphicsView):
    def load_image(self, filename: str) -> bool
    def start_marking_corners(self)
    def auto_detect_corners(self) -> bool
    def map_pointer(self, x_m: float, y_m: float)
    def place_zone(self, x_m: float, y_m: float, radius_m: float) -> Zone
    def place_rectangular_zone(self, x1_m: float, y1_m: float, x2_m: float, y2_m: float, zone_id=None) -> RectangularZone
    def clear_zones(self)
    def set_speaker_volumes(self, volumes: dict)  # {speaker_id: volume}
    def set_speaker_positions(self, positions: dict)  # {speaker_id: [x_m, y_m, z_m]}
    def set_show_speakers(self, show: bool)  # Enable/disable speaker visualization
    pointerMapped = Signal(float, float)  # x_m, y_m when user clicks
    zoneRegistered = Signal(Zone)
    zoneDeregistered = Signal(Zone)
    homographyComputed = Signal()  # Emitted when homography is computed
```

**World Coordinate System:**

- Origin: Top-left corner
- X-axis: Increases rightward (0.0 → 4.80 m)
- Y-axis: Increases downward (0.0 → 6.00 m)
- Units: Meters (all internal calculations use meters)

### 5.2 MiniPlayer (Shared Subwidget)

**Package:** `packages/mini_player/mini_player.py` (single shared implementation)

**Purpose:** Compact audio player control widget for sidebar display. This is a reusable subwidget instantiated by parent widgets with specific parameters.

**Features:**

- Current song display (artist - title)
- Play/pause button
- Skip button (next song)
- Volume slider (0-100)
- Queue display (scrollable list)
- Progress indicator (optional)

**Complete MiniPlayer API:**

```python
class MiniPlayer(QWidget):
    # ============================================================
    # SIGNALS (Emitted to parent widget)
    # ============================================================
    # Playback control signals
    playRequested = Signal()
    pauseRequested = Signal()
    stopRequested = Signal()
    skipRequested = Signal()           # Next track
    previousRequested = Signal()       # Previous track
    seekRequested = Signal(float)      # Seek to position (0.0-1.0)

    # Volume control signals
    volumeChanged = Signal(int)        # Volume 0-100

    # Playlist control signals
    playlistSelected = Signal(int)     # Playlist ID
    shuffleToggled = Signal(bool)      # Shuffle on/off
    repeatToggled = Signal(bool)       # Repeat on/off

    # ============================================================
    # PUBLIC METHODS (Called by parent widget)
    # ============================================================
    def update_queue_list(self, queue_preview: list) -> None:
        """Update the displayed queue with list of track names."""

    def update_current_track(self, track_name: str) -> None:
        """Update the currently playing track display."""

    def set_track_name(self, track_name: str) -> None:
        """Set the track name label."""

    def set_progress(self, progress: float) -> None:
        """Set playback progress bar (0.0-1.0)."""

    def set_volume_slider(self, volume: int) -> None:
        """Set volume slider position (0-100)."""

    def set_playing_state(self, is_playing: bool) -> None:
        """Update play/pause button state."""

    def set_playlist_dropdown(self, playlist_id: int) -> None:
        """Set selected playlist in dropdown."""

    def clear_queue(self) -> None:
        """Clear the queue display."""
```

**Usage Pattern:**

```python
# In AdaptiveAudioWidget
class AdaptiveAudioWidget(QWidget):
    def __init__(self, app_bus, services, settings, parent=None):
        super().__init__(parent)
        # Import shared mini_player
        from packages.mini_player import MiniPlayer

        # Instantiate with specific configuration for adaptive audio
        self.mini_player = MiniPlayer(
            mode="adaptive",
            show_queue=False,
            parent=self
        )
        self.mini_player.playRequested.connect(self._on_play)
        self.mini_player.volumeChanged.connect(self._on_volume_changed)

# In ZoneDjWidget
class ZoneDjWidget(QWidget):
    def __init__(self, app_bus, services, settings, parent=None):
        super().__init__(parent)
        # Import same shared mini_player
        from packages.mini_player import MiniPlayer

        # Instantiate with different configuration for zone DJ
        self.mini_player = MiniPlayer(
            mode="zone_dj",
            show_queue=True,
            parent=self
        )
        self.mini_player.playRequested.connect(self._on_zone_play)
```

**Key Points:**

- **Single Implementation**: Only ONE `mini_player.py` file in the codebase
- **Parameterized**: Different widgets pass different parameters to customize behavior
- **No Duplication**: Avoid creating `adaptive_audio_widget/mini_player.py` and `zone_dj_widget/mini_player.py`

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

        # Connect AppBus signals to server methods (routing layer)
        self._connect_appbus_signals()

        # Build services dictionary (passed to widgets)
        # Note: widgets don't need server reference anymore (use AppBus instead)
        self.services = {
            "settings": self.settings
        }

        # Setup polling timers
        self._last_position = None
        self._last_volumes = {}

        # Position polling (20Hz)
        self._position_timer = QTimer()
        self._position_timer.timeout.connect(self._poll_server_position)
        poll_interval_ms = 1000 // self.settings.value("server/poll_rate_hz", 20, type=int)
        self._position_timer.start(poll_interval_ms)  # Default: 50ms = 20Hz

        # Queue/playback state polling (1Hz - less frequent)
        self._queue_timer = QTimer()
        self._queue_timer.timeout.connect(self._poll_playback_state)
        self._queue_timer.start(1000)  # 1Hz

    def _connect_appbus_signals(self):
        """Connect all AppBus signals to their handlers."""
        # Playback control
        self.bus.playRequested.connect(self._on_play_requested)
        self.bus.pauseRequested.connect(self._on_pause_requested)
        self.bus.stopRequested.connect(self._on_stop_requested)
        self.bus.skipRequested.connect(self._on_skip_requested)
        self.bus.previousRequested.connect(self._on_previous_requested)
        self.bus.seekRequested.connect(self._on_seek_requested)

        # Audio mode control
        self.bus.audioStartRequested.connect(self._on_audio_start_requested)
        self.bus.audioStopRequested.connect(self._on_audio_stop_requested)
        self.bus.adaptiveAudioEnabled.connect(self._on_adaptive_audio_enabled)
        self.bus.zoneDjEnabled.connect(self._on_zone_dj_enabled)
        self.bus.bypassAudioRequested.connect(self._on_bypass_audio_requested)

        # Playlist & volume control
        self.bus.playlistChangeRequested.connect(self._on_playlist_change_requested)
        self.bus.volumeChangeRequested.connect(self._on_volume_change_requested)
        self.bus.globalVolumeChanged.connect(self._on_global_volume_changed)

        # Settings
        self.bus.simulationSpeedChanged.connect(self._on_simulation_speed_changed)

        # Build widgets (they communicate via AppBus)
        self._build_tabs()

    def _build_tabs(self):
        # Widgets receive AppBus, not server directly
        self.tab_pgo = PgoPlotWidget(self.bus, self.services, self.settings)
        self.tab_adaptive = AdaptiveAudioWidget(self.bus, self.services, self.settings)
        self.tab_zonedj = ZoneDjWidget(self.bus, self.services, self.settings)

        self.tabs.addTab(self.tab_pgo, "PGO Data")
        self.tabs.addTab(self.tab_adaptive, "Adaptive Audio")
        self.tabs.addTab(self.tab_zonedj, "Zone DJ")

    # ================================================================
    # APPBUS SIGNAL HANDLERS (Route to server methods)
    # ================================================================

    # --- Playback Control Handlers ---
    @pyqtSlot(str)
    def _on_play_requested(self, source: str):
        """Handle play request from widgets."""
        self.server.play()
        self.bus.playbackStateChanged.emit(source, True)
        self.bus.serverStatusChanged.emit("playing")

    @pyqtSlot(str)
    def _on_pause_requested(self, source: str):
        """Handle pause request from widgets."""
        self.server.pause()
        self.bus.playbackStateChanged.emit(source, False)
        self.bus.serverStatusChanged.emit("paused")

    @pyqtSlot(str)
    def _on_stop_requested(self, source: str):
        """Handle stop request from widgets."""
        self.server.stop_playback()
        self.bus.playbackStateChanged.emit(source, False)
        self.bus.serverStatusChanged.emit("stopped")

    @pyqtSlot(str)
    def _on_skip_requested(self, source: str):
        """Handle skip to next track request."""
        self.server.skip_track()
        # Emit track change
        current_track = self.server.get_current_track()
        self.bus.trackChanged.emit(current_track, self.server.current_track_index)

    @pyqtSlot(str)
    def _on_previous_requested(self, source: str):
        """Handle previous track request."""
        self.server.previous_track()
        current_track = self.server.get_current_track()
        self.bus.trackChanged.emit(current_track, self.server.current_track_index)

    @pyqtSlot(str, float)
    def _on_seek_requested(self, source: str, position: float):
        """Handle seek request."""
        self.server.seek(position)

    # --- Audio Mode Handlers ---
    @pyqtSlot(str, dict)
    def _on_audio_start_requested(self, mode: str, params: dict):
        """Handle audio mode start request (adaptive/zone_dj)."""
        if mode == "adaptive":
            self.server.adaptive_audio_demo()
        elif mode == "zone_dj":
            self.server.zone_dj_demo(**params)
        self.bus.serverStatusChanged.emit("audio_playing")

    @pyqtSlot(str)
    def _on_audio_stop_requested(self, mode: str):
        """Handle audio mode stop request."""
        if mode == "adaptive":
            self.server.stop_adaptive_audio_demo()
        elif mode == "zone_dj":
            self.server.stop_zone_dj_demo()
        self.bus.serverStatusChanged.emit("audio_stopped")

    @pyqtSlot(bool)
    def _on_adaptive_audio_enabled(self, enabled: bool):
        """Enable/disable adaptive audio mode."""
        self.server.enable_adaptive_audio(enabled)

    @pyqtSlot(bool)
    def _on_zone_dj_enabled(self, enabled: bool):
        """Enable/disable zone DJ mode."""
        self.server.enable_zone_dj(enabled)

    @pyqtSlot(bool)
    def _on_bypass_audio_requested(self, bypass: bool):
        """Bypass all audio processing."""
        self.server.bypass_audio_processing(bypass)

    # --- Playlist & Volume Handlers ---
    @pyqtSlot(int)
    def _on_playlist_change_requested(self, playlist_number: int):
        """Handle playlist change request."""
        self.server.set_playlist(playlist_number)
        # Emit queue update
        self._poll_playback_state()

    @pyqtSlot(int, int)
    def _on_volume_change_requested(self, device_id: int, volume: int):
        """Handle volume change for specific device or all devices."""
        if device_id == -1:
            # Set volume for all devices
            self.server.set_global_volume(volume)
            self.bus.globalVolumeUpdated.emit(volume)
        else:
            self.server.set_volume(device_id, volume)
            self.bus.volumeUpdated.emit(device_id, volume)

    @pyqtSlot(int)
    def _on_global_volume_changed(self, volume: int):
        """Handle global volume change."""
        self.server.set_global_volume(volume)
        self.bus.globalVolumeUpdated.emit(volume)

    # --- Settings Handlers ---
    @pyqtSlot(float)
    def _on_simulation_speed_changed(self, speed: float):
        """Handle simulation speed change."""
        self.server.simulation_speed = speed
        self.bus.simulationSpeedChanged.emit(speed)

    # ================================================================
    # POLLING METHODS (Server state → AppBus)
    # ================================================================

    def _poll_playback_state(self):
        """Poll queue and playback state, emit to AppBus (1Hz)."""
        # Queue preview
        queue_preview = self.server.get_queue_preview(5)
        current_track = self.server.get_current_track()
        self.bus.queueUpdated.emit(queue_preview, current_track)

        # Playback progress (only if playing)
        if self.server.is_playing():
            progress = self.server.get_playback_progress()
            self.bus.playbackProgressChanged.emit(progress)

        # Volume states (emit only if changed)
        speaker_states = self.server.get_speaker_states()
        for device_id, state in speaker_states.items():
            volume = state.get('volume', 0)
            if device_id not in self._last_volumes or volume != self._last_volumes[device_id]:
                self.bus.volumeUpdated.emit(device_id, volume)
                self._last_volumes[device_id] = volume
```

**Accessible Attributes:**

- `server.user_position` - np.ndarray [x, y, z] in cm (thread-safe with `_position_lock`)
- `server.data` - Dict[int, BinnedData] - latest binned measurement data
- `server.nodes` - Dict[int, np.ndarray] - anchor positions in cm
- `server.simulation_speed` - float - simulation speed multiplier
- `server.volumes` - Dict[int, int] - speaker volumes {speaker_id: volume} (thread-safe with `_volumes_lock`)

**Speaker Volume Methods:**

- `server.get_speaker_volumes() -> Dict[int, int]` - Get current speaker volumes (thread-safe)
- `server.get_speaker_positions() -> Dict[int, np.ndarray]` - Get speaker positions in meters (from anchor positions)

**Complete DummyServer API Reference:**

```python
class DummyServerBringUpProMax:
    # ============================================================
    # LIFECYCLE METHODS
    # ============================================================
    def start(self) -> None
        """Start the dummy server simulation and processing threads."""

    def stop(self) -> None
        """Stop all processing, simulation, and audio demo threads."""

    # ============================================================
    # AUDIO DEMO MODES (High-level control)
    # ============================================================
    def adaptive_audio_demo(self) -> None
        """Start adaptive audio demo (position-based 2-zone audio)."""

    def stop_adaptive_audio_demo(self) -> None
        """Stop adaptive audio demo."""

    def zone_dj_demo(self, **params) -> None
        """Start zone DJ demo (multi-zone audio with parameters)."""

    def stop_zone_dj_demo(self) -> None
        """Stop zone DJ demo."""

    def enable_adaptive_audio(self, enabled: bool) -> None
        """Enable or disable adaptive audio processing."""

    def enable_zone_dj(self, enabled: bool) -> None
        """Enable or disable zone DJ mode."""

    def bypass_audio_processing(self, bypass: bool) -> None
        """Bypass all audio DSP processing (passthrough mode)."""

    # ============================================================
    # PLAYBACK CONTROL METHODS
    # ============================================================
    def play(self) -> None
        """Resume playback (or start if stopped)."""

    def pause(self) -> None
        """Pause current playback."""

    def stop_playback(self) -> None
        """Stop playback completely."""

    def skip_track(self) -> None
        """Skip to next track in queue."""

    def previous_track(self) -> None
        """Go back to previous track."""

    def seek(self, position: float) -> None
        """Seek to position in current track (0.0-1.0)."""

    def is_playing(self) -> bool
        """Return True if currently playing."""

    # ============================================================
    # PLAYLIST & QUEUE METHODS
    # ============================================================
    def set_playlist(self, playlist_number: int) -> None
        """Set current playlist (1-5)."""

    def get_playlist(self, playlist_id: int) -> list
        """Get playlist by ID (returns list of track names)."""

    def get_current_track(self) -> str
        """Get currently playing track name."""

    def get_queue_preview(self, count: int = 5) -> list
        """Get next N tracks in queue."""

    def get_playback_progress(self) -> float
        """Get current track progress (0.0-1.0)."""

    # ============================================================
    # VOLUME CONTROL METHODS
    # ============================================================
    def set_volume(self, device_id: int, volume: int) -> None
        """Set volume for specific device (0-100)."""

    def set_global_volume(self, volume: int) -> None
        """Set master volume for all devices (0-100)."""

    def get_volume(self, device_id: int) -> int
        """Get current volume for device."""

    def get_speaker_states(self) -> dict
        """Get all speaker states (volumes, active status)."""

    # ============================================================
    # STATE QUERY METHODS
    # ============================================================
    def get_audio_state(self) -> dict
        """Get complete audio state (mode, playback, volumes)."""

    def get_zone_state(self) -> dict
        """Get current zone activation state."""

    # ============================================================
    # ATTRIBUTES (Read-only, use with locks where indicated)
    # ============================================================
    # user_position: np.ndarray  # [x, y, z] in cm (use _position_lock)
    # data: Dict[int, BinnedData]  # latest binned measurement data
    # nodes: Dict[int, np.ndarray]  # anchor positions in cm
    # simulation_speed: float  # simulation speed multiplier
    # current_playlist: list  # current playlist tracks
    # current_track_index: int  # index in current_playlist
    # volumes: Dict[int, int]  # speaker volumes {device_id: volume}
```

**Implementation Notes:**

- All audio methods log commands to console (simulated audio control)
- DSP coordination happens within DummyServer (widgets only trigger state changes)
- Thread safety: Call audio methods only from main thread (via MainWindow routing)
- Position data: Always access `user_position` with `_position_lock`

**Thread Safety Solution (AppBus Pattern):**

The recommended approach is to route all audio commands through AppBus:

1. **Widgets emit to AppBus** (from any thread, Qt handles queueing):
   
   ```python
   # In widget (any thread)
   self.bus.audioStartRequested.emit("adaptive", {})
   ```

2. **MainWindow receives on main thread** and calls server:
   
   ```python
   # In MainWindow (always main thread)
   @pyqtSlot(str, dict)
   def _on_audio_start_requested(self, mode: str, params: dict):
       self.server.adaptive_audio_demo()  # Safe: main thread only
   ```

3. **Benefits:**
   
   - ✅ Qt signal system ensures main thread delivery
   - ✅ No locks needed in DummyServer audio methods
   - ✅ Thread-safe even if widgets call from timers/backgrounds threads
   - ✅ Consistent with position data flow pattern
   - ✅ Testable (mock AppBus)

**Alternative (Deprecated):** Direct widget→server calls work only if called from main thread (button handlers). Not recommended for production.

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

**Thread Safety: Solved via AppBus Pattern ✅**

The architecture routes all audio commands through AppBus, solving thread safety issues:

**Pattern:**

1. **Widgets** → emit to AppBus (any thread)
2. **AppBus** → Qt signal system (automatic queuing)
3. **MainWindow** → receives on main thread
4. **MainWindow** → calls DummyServer methods (thread-safe)

**Code Example:**

```python
# Widget (any thread)
class AdaptiveAudioWidget(QWidget):
    def _on_button_clicked(self):
        self.bus.audioStartRequested.emit("adaptive", {})  # Thread-safe

# MainWindow (main thread only)
class MainWindow(QMainWindow):
    def __init__(self):
        self.bus.audioStartRequested.connect(self._on_audio_start_requested)

    @pyqtSlot(str, dict)
    def _on_audio_start_requested(self, mode: str, params: dict):
        self.server.adaptive_audio_demo()  # Always called from main thread
```

**Benefits:**

- ✅ No locks needed in DummyServer
- ✅ Works from any thread (timers, backgrounds, button handlers)
- ✅ Qt guarantees main thread delivery
- ✅ Consistent architecture (all communication via AppBus)

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

- **AppBus:** Qt signal hub for ALL intra-application communication (position, commands, events)
- **Audio Command Signals:** AppBus signals for audio control (audioStartRequested, audioStopRequested, playlistChangeRequested)
- **Event Callback Signals:** AppBus signals for cross-widget communication (playbackStateChanged, zoneSelected, floorplanCornerMarked)
- **DummyServerBringUpProMax:** Simulation server providing UWB position data and audio demo methods
- **MainWindow Router:** MainWindow connects AppBus signals to server method calls (thread-safe routing layer)
- **Homography:** 3×3 transformation matrix mapping world coordinates to image pixels
- **PGO:** Pose Graph Optimization, algorithm for estimating user position from UWB measurements
- **Zone:** A defined region in world space (circular or rectangular) that triggers events when user enters/exits
- **Registration:** Event triggered when user enters a zone (after hover threshold)
- **Deregistration:** Event triggered when user exits a zone (after leave threshold)
- **FloorplanView:** Reusable widget for displaying floorplan images with world coordinate mapping
- **MiniPlayer:** Compact audio player control widget (shared subwidget, single implementation)
- **Services Dictionary:** Dict passed to widgets (settings only; no server reference needed)
- **Polling:** MainWindow QTimer-based reading of server.user_position attribute (20Hz)
- **Subwidget:** Reusable UI component at the lowest hierarchy (viz_floorplan, mini_player)
- **Widget Layer:** Mid-level components that instantiate subwidgets (adaptive_audio_widget, zone_dj_widget)
- **Data Down, Events Up:** Data flows from main_demo → widgets → subwidgets; events/callbacks flow upward via AppBus
- **Parameterization:** Widgets configure subwidgets with specific parameters instead of duplicating code
- **Thread-Safe Communication:** All AppBus signals delivered to main thread by Qt, ensuring safe server method calls

---

## 13. References

- [PR #15 - DummyServer Implementation](https://github.com/Hong-yiii/uwb-localization-mesh/pull/15) - feat/dummyserver branch with audio demo functionality
- [DummyServerBringUp.py](../DummyServerBringUp.py) - Simulation server implementation
- [PyQt5 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt5/)
- [Unified Demo Proposal](../unified_demo_proposal.md)

---

## 14. Integration Summary

### Data Flow: Unified Pattern via AppBus

**Pattern 1: Position Updates (Server → Widgets)**

```
DummyServer → MainWindow polls → AppBus.pointerUpdated → Widgets subscribe
(background)   (QTimer 20Hz)    (signal)               (visualization)
```

**Pattern 2: Audio Commands (Widgets → Server)**

```
Widget UI → AppBus.audioStartRequested → MainWindow routes → DummyServer.method()
(buttons)   (emit signal)               (@pyqtSlot handler)  (logs simulation)
```

**Pattern 3: Event Callbacks (Widget ↔ Widget)**

```
WidgetA → AppBus.playbackStateChanged → WidgetB subscribes
          AppBus.zoneSelected
          AppBus.floorplanCornerMarked
```

### Key Architectural Decisions

1. **Unified Communication**: ALL communication flows through AppBus (position, commands, events)
2. **Thread Safety**: Qt signal system ensures thread-safe delivery to main thread
3. **Decoupling**: Widgets don't hold server references (except MainWindow)
4. **MainWindow as Router**: Connects AppBus signals to server method calls
5. **No Direct Calls**: Widgets emit signals, never call server methods directly
6. **Cross-Widget Communication**: Widgets can communicate via AppBus without direct references
7. **Testability**: Mock AppBus for unit testing widgets

### Widget-AppBus Integration

All widgets receive AppBus instance:

```python
def __init__(self, app_bus, services, settings, parent=None):
    self.bus = app_bus  # AppBus for ALL communication
    # No server reference needed!
```

Widgets can:

- **Subscribe** to `AppBus.pointerUpdated` for position data
- **Emit** `AppBus.audioStartRequested` for audio control
- **Emit** `AppBus.playlistChangeRequested` for playlist changes
- **Emit/Subscribe** to event callbacks for cross-widget communication
- **Never** access `server` directly (MainWindow handles routing)

---

## 15. API Quick Reference

### AppBus Signals Summary

| Category             | Signal                    | Parameters                   | Direction        |
| -------------------- | ------------------------- | ---------------------------- | ---------------- |
| **Position**         | `pointerUpdated`          | x_m, y_m, ts, source         | Server → Widgets |
| **Playback Control** | `playRequested`           | source                       | Widget → Server  |
|                      | `pauseRequested`          | source                       | Widget → Server  |
|                      | `stopRequested`           | source                       | Widget → Server  |
|                      | `skipRequested`           | source                       | Widget → Server  |
|                      | `previousRequested`       | source                       | Widget → Server  |
|                      | `seekRequested`           | source, position             | Widget → Server  |
| **Audio Modes**      | `audioStartRequested`     | mode, params                 | Widget → Server  |
|                      | `audioStopRequested`      | mode                         | Widget → Server  |
|                      | `adaptiveAudioEnabled`    | enabled                      | Widget → Server  |
|                      | `zoneDjEnabled`           | enabled                      | Widget → Server  |
|                      | `bypassAudioRequested`    | bypass                       | Widget → Server  |
| **Volume**           | `volumeChangeRequested`   | device_id, volume            | Widget → Server  |
|                      | `globalVolumeChanged`     | volume                       | Widget → Server  |
|                      | `volumeUpdated`           | device_id, volume            | Server → Widgets |
|                      | `globalVolumeUpdated`     | volume                       | Server → Widgets |
|                      | `speakerVolumesUpdated`   | {speaker_id: volume, ...}    | Server → Widgets |
| **Playlist**         | `playlistChangeRequested` | playlist_number              | Widget → Server  |
|                      | `playlistSelected`        | playlist_id                  | Widget → Server  |
|                      | `queueUpdated`            | queue_preview, current_track | Server → Widgets |
| **Playback State**   | `playbackStateChanged`    | widget_id, is_playing        | Bidirectional    |
|                      | `trackChanged`            | track_name, track_index      | Server → Widgets |
|                      | `playbackProgressChanged` | progress                     | Server → Widgets |
| **Zones**            | `zoneRegistered`          | idx, x_m, y_m, ts, source    | Widget → AppBus  |
|                      | `zoneDeregistered`        | idx, x_m, y_m, ts, source    | Widget → AppBus  |
|                      | `zoneSelected`            | zone                         | Widget → AppBus  |
|                      | `zoneCreated`             | zone                         | Widget → AppBus  |
|                      | `zoneDeleted`             | zone                         | Widget → AppBus  |
|                      | `zoneMoved`               | zone, new_x, new_y           | Widget → AppBus  |
| **Floorplan**        | `floorplanCornerMarked`   | corner_idx, x_px, y_px       | Widget → AppBus  |
|                      | `floorplanImageLoaded`    | image_path                   | Widget → AppBus  |
|                      | `homographyComputed`      | homography_matrix            | Widget → AppBus  |
| **System**           | `serverStatusChanged`     | status                       | Server → Widgets |
|                      | `simulationSpeedChanged`  | speed                        | Bidirectional    |
|                      | `settingsChanged`         | key, value                   | Bidirectional    |

### DummyServer Methods Summary

| Category        | Method                            | Parameters      | Returns               |
| --------------- | --------------------------------- | --------------- | --------------------- |
| **Lifecycle**   | `start()`                         | -               | None                  |
|                 | `stop()`                          | -               | None                  |
| **Audio Modes** | `adaptive_audio_demo()`           | -               | None                  |
|                 | `stop_adaptive_audio_demo()`      | -               | None                  |
|                 | `zone_dj_demo(**params)`          | params dict     | None                  |
|                 | `stop_zone_dj_demo()`             | -               | None                  |
|                 | `enable_adaptive_audio(enabled)`  | bool            | None                  |
|                 | `enable_zone_dj(enabled)`         | bool            | None                  |
|                 | `bypass_audio_processing(bypass)` | bool            | None                  |
| **Playback**    | `play()`                          | -               | None                  |
|                 | `pause()`                         | -               | None                  |
|                 | `stop_playback()`                 | -               | None                  |
|                 | `skip_track()`                    | -               | None                  |
|                 | `previous_track()`                | -               | None                  |
|                 | `seek(position)`                  | float (0.0-1.0) | None                  |
|                 | `is_playing()`                    | -               | bool                  |
|                 | `get_playback_progress()`         | -               | float (0.0-1.0)       |
| **Playlist**    | `set_playlist(number)`            | int (1-5)       | None                  |
|                 | `get_playlist(id)`                | int             | list                  |
|                 | `get_current_track()`             | -               | str                   |
|                 | `get_queue_preview(count)`        | int             | list                  |
| **Volume**      | `set_volume(device_id, volume)`   | int, int        | None                  |
|                 | `set_global_volume(volume)`       | int             | None                  |
|                 | `get_volume(device_id)`           | int             | int                   |
|                 | `get_speaker_states()`            | -               | dict                  |
|                 | `get_speaker_volumes()`           | -               | Dict[int, int]        |
|                 | `get_speaker_positions()`         | -               | Dict[int, np.ndarray] |
| **State**       | `get_audio_state()`               | -               | dict                  |
|                 | `get_zone_state()`                | -               | dict                  |
| **Attributes**  | `user_position`                   | -               | np.ndarray (use lock) |
|                 | `current_playlist`                | -               | list                  |
|                 | `current_track_index`             | -               | int                   |
|                 | `volumes`                         | -               | dict                  |
|                 | `simulation_speed`                | -               | float                 |

### MiniPlayer Methods Summary

| Category           | Signal/Method                   | Parameters | Type   |
| ------------------ | ------------------------------- | ---------- | ------ |
| **Signals**        | `playRequested`                 | -          | Signal |
|                    | `pauseRequested`                | -          | Signal |
|                    | `stopRequested`                 | -          | Signal |
|                    | `skipRequested`                 | -          | Signal |
|                    | `previousRequested`             | -          | Signal |
|                    | `seekRequested`                 | float      | Signal |
|                    | `volumeChanged`                 | int        | Signal |
|                    | `playlistSelected`              | int        | Signal |
|                    | `shuffleToggled`                | bool       | Signal |
|                    | `repeatToggled`                 | bool       | Signal |
| **Update Methods** | `update_queue_list(queue)`      | list       | Method |
|                    | `update_current_track(track)`   | str        | Method |
|                    | `set_track_name(name)`          | str        | Method |
|                    | `set_progress(progress)`        | float      | Method |
|                    | `set_volume_slider(volume)`     | int        | Method |
|                    | `set_playing_state(is_playing)` | bool       | Method |
|                    | `set_playlist_dropdown(id)`     | int        | Method |
|                    | `clear_queue()`                 | -          | Method |

### MainWindow Polling Strategy

| Timer                  | Frequency    | Polls                            | Emits                     |
| ---------------------- | ------------ | -------------------------------- | ------------------------- |
| `_position_timer`      | 20Hz (50ms)  | `server.user_position`           | `pointerUpdated`          |
| `_queue_timer`         | 1Hz (1000ms) | `server.get_queue_preview()`     | `queueUpdated`            |
| `_speaker_volumes_timer` | 5Hz (200ms) | `server.get_speaker_volumes()`   | `speakerVolumesUpdated`   |
|                   |              | `server.get_current_track()`     | `trackChanged`            |
|                   |              | `server.get_playback_progress()` | `playbackProgressChanged` |
|                   |              | `server.get_speaker_states()`    | `volumeUpdated`           |

### Data Flow Patterns

**Pattern 1: User Action → Server Method**

```
User clicks button → MiniPlayer emits signal → Widget handler → 
AppBus.emit() → MainWindow handler → Server method call → State change
```

**Pattern 2: Server State → UI Update**

```
MainWindow polls server (1Hz/20Hz) → Read state → 
AppBus.emit() → Widget handler → Update UI component
```

**Pattern 3: Cross-Widget Communication**

```
WidgetA action → AppBus.emit(callback signal) → 
WidgetB handler → Update WidgetB state
```

---

**Document Version:** 4.0  
**Last Updated:** 2025-01-11  
**Author:** Architecture Planning Team  
**References:** [PR #15 - DummyServer Implementation](https://github.com/Hong-yiii/uwb-localization-mesh/pull/15)

**Change Log:**

- v4.0: **COMPREHENSIVE API DOCUMENTATION** - Complete reference for all methods, signals, and patterns
  - ✅ Complete AppBus Signal Reference (~30 signals organized by category)
  - ✅ Complete DummyServer API Reference (all lifecycle, playback, volume, playlist methods)
  - ✅ Complete MainWindow Routing Table (all signal handlers with code examples)
  - ✅ Dual Polling Strategy (position @ 20Hz, queue/playback @ 1Hz)
  - ✅ Complete MiniPlayer API (all signals and update methods)
  - ✅ Complete Widget Integration Example (AdaptiveAudioWidget with all controls)
  - ✅ Playback Control Patterns (play, pause, stop, skip, previous, seek)
  - ✅ Queue Management (display, updates, synchronization via polling)
  - ✅ Volume Control Patterns (per-device and global volume)
  - ✅ Audio Mode Controls (enable/disable adaptive, zone_dj, bypass)
  - ✅ Bidirectional Data Flow (commands out, state updates in)
- v3.0: **MAJOR**: Unified architecture - ALL communication via AppBus (audio commands, event callbacks)
  - Added audio command signals to AppBus (audioStartRequested, playlistChangeRequested, etc.)
  - Added event callback signals for cross-widget communication
  - MainWindow routes AppBus audio signals to server methods (thread-safe)
  - Widgets no longer call server methods directly
  - Solved thread safety issues via Qt signal system
  - Updated all code examples to use AppBus pattern
- v2.3: Clarified component hierarchy (3 layers), emphasized NO duplication of mini_player/viz_floorplan
- v2.2: Removed remaining MQTT references from testing and glossary
- v2.1: Added thread safety limitations for audio method calls
- v2.0: Removed all MQTT references - direct integration only
- v1.1: Added audio demo methods from PR #15
- v1.0: Initial architecture plan
