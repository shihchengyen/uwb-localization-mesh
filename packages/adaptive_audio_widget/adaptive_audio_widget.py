"""
AdaptiveAudioWidget - Fixed 2-Zone Follow-Me Audio System

Provides a visualization and control interface for adaptive audio with two fixed zones.
Uses shared subwidgets: FloorplanView and MiniPlayer.

Features:
- Fixed 2-zone split at Y = 3.00 m
- Zone registration/deregistration with timers
- Floorplan visualization with homography
- Audio control via MiniPlayer
- All communication via AppBus (thread-safe)

Zone Logic:
- Zone A (Top): 0.00 m ≤ y < 3.00 m
- Zone B (Bottom): 3.00 m ≤ y ≤ 6.00 m
- Registration: Hover ≥3s
- Deregistration: Leave ≥1s
"""

import time
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QGroupBox
from PyQt5.QtCore import QTimer


class AdaptiveAudioWidget(QWidget):
    """
    Adaptive Audio widget with fixed 2-zone split.
    
    Subscribes to AppBus for position updates and state changes.
    Emits to AppBus for audio commands and event callbacks.
    """
    
    def __init__(self, app_bus, services, settings, parent=None):
        """
        Initialize AdaptiveAudioWidget.
        
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
        self.world_width_m = settings.value("world/width_m", 4.80, type=float)
        self.world_height_m = settings.value("world/height_m", 6.00, type=float)
        self.split_y_m = settings.value("adaptive/split_y_m", 3.00, type=float)
        self.t_register_ms = settings.value("adaptive/t_register_ms", 3000, type=int)
        self.t_deregister_ms = settings.value("adaptive/t_deregister_ms", 1000, type=int)
        
        # State
        self.current_zone = None  # "A" or "B"
        self.zone_entry_time = None
        self.zone_exit_time = None
        self.zone_registered = False
        self.is_bypassed = False
        self.active_speakers = []  # List of active device IDs
        
        # Store reference to shared floorplan if provided
        self._shared_floorplan = services.get("shared_floorplan", None)
        
        # Setup UI
        self._setup_ui()
        
        # Connect signals
        self._connect_mini_player_signals()
        self._connect_appbus_signals()
        
        # Enable speaker visualization (only for Adaptive Audio)
        self.floorplan.set_show_speakers(True)
        
        # Create zones if homography is already available
        if self.floorplan.homography_matrix is not None:
            self._setup_adaptive_zones()
        
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
            # Clear zones when switching to Adaptive Audio (it uses fixed zones, not placed zones)
            self.floorplan.clear_zones()
        else:
            # Create new instance if no shared floorplan provided
            from viz_floorplan.floorplan_view import FloorplanView
            self.floorplan = FloorplanView(
                world_width_m=self.settings.value("world/width_m", 4.80, type=float),
                world_height_m=self.settings.value("world/height_m", 6.00, type=float),
                grid_cols=self.settings.value("grid/cols", 8, type=int),
                grid_rows=self.settings.value("grid/rows", 10, type=int),
                parent=self
            )
        layout.addWidget(self.floorplan, stretch=1)
        
        # Create rectangular zones for Adaptive Audio (Zone A and Zone B)
        # Note: Zones will be drawn once homography is computed
        self.adaptive_zones = {}  # Will be populated in _setup_adaptive_zones
        
        # Right sidebar (fixed width via MiniPlayer)
        sidebar = QVBoxLayout()
        sidebar.setSpacing(12)
        sidebar.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title = QLabel("Adaptive Audio")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        sidebar.addWidget(title)
        
        # Control checkboxes
        controls_group = QGroupBox("Controls")
        controls_layout = QVBoxLayout()
        
        self.bypass_checkbox = QCheckBox("Bypass Audio Processing")
        self.bypass_checkbox.toggled.connect(self._on_bypass_toggled)
        controls_layout.addWidget(self.bypass_checkbox)
        
        controls_group.setLayout(controls_layout)
        sidebar.addWidget(controls_group)
        
        # Zone info
        zone_group = QGroupBox("Zone Status")
        zone_layout = QVBoxLayout()
        
        self.zone_label = QLabel("Current Zone: --")
        zone_layout.addWidget(self.zone_label)
        
        self.registration_label = QLabel("Status: Not registered")
        zone_layout.addWidget(self.registration_label)
        
        zone_group.setLayout(zone_layout)
        sidebar.addWidget(zone_group)
        
        # Mini player
        from mini_player.mini_player import MiniPlayer
        self.mini_player = MiniPlayer(
            mode="adaptive",
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
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #666666;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background: #00ff88;
                border-color: #00ff88;
            }
            QCheckBox::indicator:hover {
                border-color: #888888;
            }
        """)
    
    def _setup_adaptive_zones(self):
        """Create rectangular zones for Adaptive Audio (Zone A and Zone B)."""
        # Only create zones if homography is available
        if self.floorplan.homography_matrix is None:
            # Zones will be created when homography is computed
            return
        
        # Zone A (Top): 0.00 m ≤ y < split_y_m
        # Zone B (Bottom): split_y_m ≤ y ≤ world_height_m
        self.zone_a = self.floorplan.place_rectangular_zone(
            0.0, 0.0, 
            self.world_width_m, self.split_y_m,
            zone_id="A"
        )
        self.zone_b = self.floorplan.place_rectangular_zone(
            0.0, self.split_y_m,
            self.world_width_m, self.world_height_m,
            zone_id="B"
        )
        # Store reference to zones for easy access
        self.adaptive_zones = {"A": self.zone_a, "B": self.zone_b}
        
        # Disable FloorplanView's automatic zone registration for these zones
        # Adaptive Audio handles its own zone registration logic
        # We don't want FloorplanView's timer to register these zones automatically
        # because that would trigger zone_dj_demo() via ZoneDjWidget's signal handler
        for zone in [self.zone_a, self.zone_b]:
            # Mark zones so FloorplanView's _check_zone_registration skips them
            zone._skip_auto_registration = True
    
    def clear_adaptive_zones(self):
        """Clear Adaptive Audio zones from the floorplan."""
        if not hasattr(self, 'adaptive_zones') or not self.adaptive_zones:
            return
        
        # Remove zones from floorplan
        from viz_floorplan.floorplan_view import RectangularZone
        zones_to_remove = []
        for zone in self.floorplan.zones:
            if isinstance(zone, RectangularZone) and zone.id in ["A", "B"]:
                zones_to_remove.append(zone)
        
        # Remove graphics items and zones
        for zone in zones_to_remove:
            if zone.graphics_item:
                self.floorplan.scene.removeItem(zone.graphics_item)
            if zone in self.floorplan.zones:
                self.floorplan.zones.remove(zone)
        
        # Clear references
        self.adaptive_zones = {}
        self.zone_a = None
        self.zone_b = None
        
        # Reset zone state
        self.current_zone = None
        self.zone_registered = False
        self.zone_entry_time = None
        if hasattr(self, 'registration_label'):
            self.registration_label.setText("Status: Not registered")
        if hasattr(self, 'current_zone_label'):
            self.current_zone_label.setText("Current Zone: None")
    
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
        
        # Connect to floorplan signals to create zones when homography is ready
        self.floorplan.homographyComputed.connect(self._on_homography_computed)
        
        # Playback state updates
        self.bus.queueUpdated.connect(self._on_queue_updated)
        self.bus.trackChanged.connect(self._on_track_changed)
        self.bus.playbackProgressChanged.connect(self._on_progress_changed)
        self.bus.playbackStateChanged.connect(self._on_playback_state_changed)
        
        # Volume updates
        self.bus.volumeUpdated.connect(self._on_volume_updated)
        self.bus.speakerVolumesUpdated.connect(self._on_speaker_volumes_updated)
    
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
    
    def _on_shuffle_toggled(self, checked: bool):
        """Handle shuffle toggle."""
        self.bus.shuffleToggled.emit(checked)
    
    def _on_bypass_toggled(self, checked: bool):
        """Handle bypass audio processing checkbox."""
        self.is_bypassed = checked
        self.bus.bypassAudioRequested.emit(checked)
    
    def _on_homography_computed(self):
        """Handle homography computation - create zones now."""
        # Create zones once homography is available
        if not self.adaptive_zones:
            self._setup_adaptive_zones()
    
    # ================================================================
    # STATE UPDATE HANDLERS (Receive from AppBus)
    # ================================================================
    
    def _on_pointer_updated(self, x_m: float, y_m: float, ts: float, source: str):
        """Update floorplan pointer and determine zone."""
        # Update floorplan visualization
        self.floorplan.map_pointer(x_m, y_m)
        
        # Determine zone (Adaptive: split at y=3.0m)
        if y_m < self.split_y_m:
            zone_id = "A"
        else:
            zone_id = "B"
        
        # Update zone state
        if zone_id != self.current_zone:
            # If we were in a different zone, mark exit time
            if self.current_zone is not None:
                self.zone_exit_time = time.time()
            self.current_zone = zone_id
            self.zone_entry_time = time.time()
            self.zone_exit_time = None
            self.zone_label.setText(f"Current Zone: {zone_id}")
        
        # Zone registration is handled by timer (_check_zone_state)
    
    def _check_zone_state(self):
        """Check zone registration timers."""
        if self.current_zone is None:
            return
        
        current_time = time.time()
        
        # Registration logic
        if not self.zone_registered and self.zone_entry_time:
            time_in_zone = (current_time - self.zone_entry_time) * 1000  # ms
            if time_in_zone >= self.t_register_ms:
                # Register zone
                self.zone_registered = True
                self.registration_label.setText(f"Status: Registered to Zone {self.current_zone}")
                
                # Update zone visualization (turn green)
                if self.current_zone in self.adaptive_zones:
                    zone = self.adaptive_zones[self.current_zone]
                    zone.is_active = True
                    # Redraw zone to show green tint
                    if zone.graphics_item:
                        self.floorplan.scene.removeItem(zone.graphics_item)
                        zone.graphics_item = None
                    from viz_floorplan.floorplan_view import RectangularZone
                    if isinstance(zone, RectangularZone):
                        self.floorplan._draw_rectangular_zone(zone)
                
                # Calculate zone center position for the event
                if self.current_zone in self.adaptive_zones:
                    zone = self.adaptive_zones[self.current_zone]
                    zone_x = (zone.x1 + zone.x2) / 2.0
                    zone_y = (zone.y1 + zone.y2) / 2.0
                else:
                    zone_x = 0.0
                    zone_y = 0.0
                
                # Emit zone registered event
                self.bus.zoneRegistered.emit(
                    self.current_zone, zone_x, zone_y, current_time, "adaptive_widget"
                )
                
                # Start adaptive audio for this zone (send event and position to server)
                params = {
                    "zone_id": self.current_zone,
                    "position": (zone_x, zone_y)
                }
                self.bus.audioStartRequested.emit("adaptive", params)
        
        # Deregistration logic
        if self.zone_registered and self.zone_exit_time:
            time_out_zone = (current_time - self.zone_exit_time) * 1000  # ms
            if time_out_zone >= self.t_deregister_ms:
                # Deregister zone
                old_zone = self.current_zone
                self.zone_registered = False
                self.registration_label.setText("Status: Not registered")
                self.registration_label.setStyleSheet("color: #888888;")
                
                # Update zone visualization (turn gray)
                if old_zone in self.adaptive_zones:
                    zone = self.adaptive_zones[old_zone]
                    zone.is_active = False
                    # Redraw zone to show gray tint
                    if zone.graphics_item:
                        self.floorplan.scene.removeItem(zone.graphics_item)
                        zone.graphics_item = None
                    from viz_floorplan.floorplan_view import RectangularZone
                    if isinstance(zone, RectangularZone):
                        self.floorplan._draw_rectangular_zone(zone)
                
                # Emit zone deregistered event
                self.bus.zoneDeregistered.emit(
                    old_zone, 0.0, 0.0, current_time, "adaptive_widget"
                )
    
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
    
    def _on_speaker_volumes_updated(self, volumes: dict):
        """Handle speaker volumes update from AppBus."""
        # Update floorplan speaker visualization
        if self.floorplan:
            self.floorplan.set_speaker_volumes(volumes)
