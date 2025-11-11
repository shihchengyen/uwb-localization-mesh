"""
ZoneDjWidget - User-Defined Multi-Zone Audio System

Provides visualization and control interface for zone-based audio with user-placed zones.
Uses shared subwidgets: FloorplanView and MiniPlayer.

Features:
- User-defined circular zones (draggable)
- Per-zone playlist assignment
- Zone registration/deregistration with timers
- Floorplan visualization with homography
- Audio control via MiniPlayer
- All communication via AppBus (thread-safe)

Zone Behavior:
- User places zones by clicking on floorplan
- Registration: Hover in zone ≥3s
- Deregistration: Leave zone ≥1s
- Each zone can have its own playlist
"""

import time
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QGroupBox)
from PyQt5.QtCore import Qt, QTimer


class ZoneDjWidget(QWidget):
    """
    Zone DJ widget with user-defined zones.
    
    Subscribes to AppBus for position updates and state changes.
    Emits to AppBus for audio commands and event callbacks.
    """
    
    def __init__(self, app_bus, services, settings, parent=None):
        """
        Initialize ZoneDjWidget.
        
        Args:
            app_bus: AppBus instance for communication
            services: Services dictionary (may contain "shared_floorplan")
            settings: QSettings instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.bus = app_bus
        self.settings = settings
        
        # Configuration
        self.default_zone_radius_m = settings.value("zonedj/default_zone_radius_m", 0.25, type=float)
        self.t_register_ms = settings.value("zonedj/t_register_ms", 3000, type=int)
        self.t_deregister_ms = settings.value("zonedj/t_deregister_ms", 1000, type=int)
        
        # State
        self.current_zone = None  # Currently occupied zone
        self.active_zone = None  # Zone with registered audio
        self.is_placing_zones = False
        self.zone_playlists = {}  # {zone_id: playlist_id}
        
        # Store reference to shared floorplan if provided
        self._shared_floorplan = services.get("shared_floorplan", None)
        
        # Store reference to server for direct access
        self.server = services.get("server", None)
        
        # Setup UI
        self._setup_ui()
        
        # Connect signals
        self._connect_mini_player_signals()
        self._connect_appbus_signals()
        self._connect_floorplan_signals()
        
        # Zone check timer
        self.zone_timer = QTimer()
        self.zone_timer.timeout.connect(self._check_zone_state)
        self.zone_timer.start(100)  # Check every 100ms
    
    def _setup_ui(self):
        """Build the UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Left side: Floorplan (use shared instance if available, otherwise create new)
        if self._shared_floorplan is not None:
            # Use shared floorplan instance
            self.floorplan = self._shared_floorplan
            # Reparent to this widget
            self.floorplan.setParent(self)
            # Update default zone radius if needed
            self.floorplan.default_zone_radius_m = self.default_zone_radius_m
        else:
            # Create new instance if no shared floorplan provided
            from viz_floorplan.floorplan_view import FloorplanView
            self.floorplan = FloorplanView(
                world_width_m=self.settings.value("world/width_m", 4.80, type=float),
                world_height_m=self.settings.value("world/height_m", 6.00, type=float),
                grid_cols=self.settings.value("grid/cols", 8, type=int),
                grid_rows=self.settings.value("grid/rows", 10, type=int),
                default_zone_radius_m=self.default_zone_radius_m,
                parent=self
            )
        layout.addWidget(self.floorplan, stretch=1)
        
        # Right sidebar (fixed width via MiniPlayer)
        sidebar = QVBoxLayout()
        sidebar.setSpacing(12)
        sidebar.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title = QLabel("Zone DJ")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        sidebar.addWidget(title)
        
        # Active zone info
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        
        self.current_zone_label = QLabel("Current Zone: --")
        status_layout.addWidget(self.current_zone_label)
        
        self.active_zone_label = QLabel("Active Zone: --")
        status_layout.addWidget(self.active_zone_label)
        
        status_group.setLayout(status_layout)
        sidebar.addWidget(status_group)
        
        # Mini player
        from mini_player.mini_player import MiniPlayer
        self.mini_player = MiniPlayer(
            mode="zone_dj",
            show_queue=True,
            parent=self
        )
        sidebar.addWidget(self.mini_player)
        
        sidebar.addStretch()
        
        layout.addLayout(sidebar, stretch=0)
        
        # Expose floorplan as .plan for toolbar compatibility
        self.plan = self.floorplan
        
        # Apply theme-neutral styling (inherits from MainWindow)
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid rgba(128, 128, 128, 0.2);
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 12px;
                background-color: transparent;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                font-size: 10pt;
                font-weight: 600;
            }
        """)
    
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
        self.mini_player.shuffleToggled.connect(self._on_shuffle_toggled)
    
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
    
    def _connect_floorplan_signals(self):
        """Connect floorplan signals."""
        self.floorplan.zoneRegistered.connect(self._on_zone_registered)
        self.floorplan.zoneDeregistered.connect(self._on_zone_deregistered)
    
    # ================================================================
    # CONTROL HANDLERS (Emit to AppBus)
    # ================================================================
    
    def _on_play(self):
        """Handle play button click."""
        self.bus.playRequested.emit("zone_dj_widget")
        # Start zone DJ demo if in a zone
        if self.active_zone:
            params = {"zone_id": self.active_zone.id}
            self.bus.audioStartRequested.emit("zone_dj", params)
    
    def _on_pause(self):
        """Handle pause button click."""
        self.bus.pauseRequested.emit("zone_dj_widget")
    
    def _on_stop(self):
        """Handle stop button click."""
        self.bus.stopRequested.emit("zone_dj_widget")
        # Stop zone DJ demo
        self.bus.audioStopRequested.emit("zone_dj")
    
    def _on_skip(self):
        """Handle skip button click."""
        # Direct access to server for song skipping
        if self.server and hasattr(self.server, 'skip_track'):
            self.server.skip_track()
        else:
            # Fallback to AppBus if server not available
            self.bus.skipRequested.emit("zone_dj_widget")
    
    def _on_previous(self):
        """Handle previous button click."""
        # Direct access to server for previous track
        if self.server and hasattr(self.server, 'previous_track'):
            self.server.previous_track()
        else:
            # Fallback to AppBus if server not available
            self.bus.previousRequested.emit("zone_dj_widget")
    
    def _on_seek(self, position: float):
        """Handle seek slider."""
        self.bus.seekRequested.emit("zone_dj_widget", position)
    
    def _on_volume_changed(self, volume: int):
        """Handle volume slider change."""
        # Direct access to server for volume control
        if self.server and hasattr(self.server, 'set_global_volume'):
            self.server.set_global_volume(volume)
        elif self.active_zone:
            # Fallback: Set volume for active zone's speakers
            device_id = self.active_zone.id  # Simplified: use zone ID as device ID
            self.bus.volumeChangeRequested.emit(device_id, volume)
    
    def _on_playlist_selected(self, playlist_id: int):
        """Handle playlist selection."""
        # Direct access to server for playlist setting
        if self.server and hasattr(self.server, 'set_playlist'):
            self.server.set_playlist(playlist_id)
        else:
            # Fallback to AppBus if server not available
            self.bus.playlistChangeRequested.emit(playlist_id)
        
        # Associate with current active zone
        if self.active_zone:
            self.zone_playlists[self.active_zone.id] = playlist_id
    
    def _on_shuffle_toggled(self, checked: bool):
        """Handle shuffle toggle."""
        self.bus.shuffleToggled.emit(checked)
    
    def _toggle_place_zones(self, checked: bool):
        """Toggle zone placement mode."""
        self.is_placing_zones = checked
        self.floorplan.placing_zones = checked
        
        if checked:
            # Update radius for new zones
            self.floorplan.next_zone_id = len(self.floorplan.zones) + 1
    
    def _clear_zones(self):
        """Clear all zones."""
        self.floorplan.clear_zones()
        self.zone_playlists = {}
        self.current_zone = None
        self.active_zone = None
        self.current_zone_label.setText("Current Zone: --")
        self.active_zone_label.setText("Active Zone: --")
    
    # ================================================================
    # STATE UPDATE HANDLERS (Receive from AppBus)
    # ================================================================
    
    def _on_pointer_updated(self, x_m: float, y_m: float, ts: float, source: str):
        """Update floorplan pointer and check zone containment."""
        # Update floorplan visualization
        self.floorplan.map_pointer(x_m, y_m)
        
        # Find zone containing pointer
        zone_found = None
        for zone in self.floorplan.zones:
            if zone.contains(x_m, y_m):
                zone_found = zone
                break
        
        # Update current zone
        if zone_found != self.current_zone:
            self.current_zone = zone_found
            if zone_found:
                self.current_zone_label.setText(f"Current Zone: {zone_found.id}")
            else:
                self.current_zone_label.setText("Current Zone: --")
    
    def _check_zone_state(self):
        """Check zone state (called by timer)."""
        # Zone registration is handled by FloorplanView's internal timers
        # and signals (zoneRegistered/zoneDeregistered)
        pass
    
    def _on_zone_registered(self, zone):
        """Handle zone registration from FloorplanView."""
        self.active_zone = zone
        self.active_zone_label.setText(f"Active Zone: {zone.id}")
        
        # Get zone center coordinates (handle both circular and rectangular zones)
        from viz_floorplan.floorplan_view import RectangularZone
        if isinstance(zone, RectangularZone):
            # For rectangular zones, use center point
            zone_x = (zone.x1 + zone.x2) / 2.0
            zone_y = (zone.y1 + zone.y2) / 2.0
        else:
            # For circular zones, use center point
            zone_x = zone.x
            zone_y = zone.y
        
        # Emit to AppBus for logging/cross-widget communication
        self.bus.zoneRegistered.emit(zone.id, zone_x, zone_y, time.time(), "zone_dj_widget")
        
        # Start audio for this zone
        params = {"zone_id": zone.id}
        self.bus.audioStartRequested.emit("zone_dj", params)
    
    def _on_zone_deregistered(self, zone):
        """Handle zone deregistration from FloorplanView."""
        if self.active_zone and self.active_zone.id == zone.id:
            self.active_zone = None
            self.active_zone_label.setText("Active Zone: --")
            
            # Get zone center coordinates (handle both circular and rectangular zones)
            from viz_floorplan.floorplan_view import RectangularZone
            if isinstance(zone, RectangularZone):
                # For rectangular zones, use center point
                zone_x = (zone.x1 + zone.x2) / 2.0
                zone_y = (zone.y1 + zone.y2) / 2.0
            else:
                # For circular zones, use center point
                zone_x = zone.x
                zone_y = zone.y
            
            # Emit to AppBus
            self.bus.zoneDeregistered.emit(zone.id, zone_x, zone_y, time.time(), "zone_dj_widget")
            
            # Stop audio
            self.bus.audioStopRequested.emit("zone_dj")
    
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
        if widget_id == "zone_dj_widget" or widget_id == "main":
            self.mini_player.set_playing_state(is_playing)
    
    def _on_volume_updated(self, device_id: int, volume: int):
        """Update volume slider."""
        # Update if it's our zone's device
        if self.active_zone and device_id == self.active_zone.id:
            self.mini_player.set_volume_slider(volume)
