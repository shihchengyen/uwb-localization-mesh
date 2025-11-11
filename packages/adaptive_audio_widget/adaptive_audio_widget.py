"""
AdaptiveAudioWidget - Position-Based Audio Panning System

Provides a visualization and control interface for adaptive audio based purely on user position.
Uses shared subwidgets: FloorplanView and MiniPlayer.

Features:
- Position-based audio panning (no zones)
- Floorplan visualization with homography
- Audio control via MiniPlayer
- Always plays from Playlist 1
- All communication via AppBus (thread-safe)

Audio Logic:
- Front/back speaker selection based on Y position
- Left/right panning based on X position
- No zone registration - immediate response to position changes
"""

import time
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QGroupBox
from PyQt5.QtCore import QTimer


class AdaptiveAudioWidget(QWidget):
    """
    Adaptive Audio widget with position-based audio panning.
    
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
        
        # Configuration - updated for new coordinate system
        self.world_width_m = settings.value("world/width_m", 6.00, type=float)
        self.world_height_m = settings.value("world/height_m", 4.80, type=float)
        # Remove zone-based configuration - adaptive audio no longer uses zones
        
        # State - simplified for non-zone based adaptive audio
        self.is_bypassed = False
        self.active_speakers = []  # List of active device IDs
        
        # Store reference to shared floorplan if provided
        self._shared_floorplan = services.get("shared_floorplan", None)
        
        # Store reference to server for direct access
        self.server = services.get("server", None)
        
        # Setup UI
        self._setup_ui()
        
        # Connect signals
        self._connect_mini_player_signals()
        self._connect_appbus_signals()
        
        # Enable speaker visualization (only for Adaptive Audio)
        self.floorplan.set_show_speakers(True)
        
        # Queue polling timer for direct server access
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self._poll_queue_state)
        self.queue_timer.start(1000)  # Poll every 1 second
        
        # Set default playlist to 1 as requested
        if self.server and hasattr(self.server, 'set_playlist'):
            self.server.set_playlist(1)
    
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
            # Clear any existing zones - adaptive audio doesn't use zones
            self.floorplan.clear_zones()
            # Disable zone placement for adaptive audio
            self.floorplan.placing_zones = False
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
        
        # No zones needed for simplified adaptive audio
        
        # Right sidebar (fixed width via MiniPlayer)
        sidebar = QVBoxLayout()
        sidebar.setSpacing(12)
        sidebar.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title = QLabel("Adaptive Audio")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        sidebar.addWidget(title)
        
        # Remove bypass audio processing and zone info as requested
        # Adaptive audio now works without zones - just position-based panning
        
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
    
    # Removed zone setup methods - adaptive audio no longer uses zones
    
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
        
        # No playlist control - adaptive audio always uses Playlist 1
        # self.mini_player.playlistSelected.connect(self._on_playlist_selected)  # Removed
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
        # Direct access to server for song skipping
        if self.server and hasattr(self.server, 'skip_track'):
            self.server.skip_track()
        else:
            # Fallback to AppBus if server not available
            self.bus.skipRequested.emit("adaptive_widget")
    
    def _on_previous(self):
        """Handle previous button click."""
        # Direct access to server for previous track
        if self.server and hasattr(self.server, 'previous_track'):
            self.server.previous_track()
        else:
            # Fallback to AppBus if server not available
            self.bus.previousRequested.emit("adaptive_widget")
    
    def _on_seek(self, position: float):
        """Handle seek slider."""
        self.bus.seekRequested.emit("adaptive_widget", position)
    
    def _on_volume_changed(self, volume: int):
        """Handle volume slider change."""
        # Direct access to server for volume control
        if self.server and hasattr(self.server, 'set_global_volume'):
            self.server.set_global_volume(volume)
        else:
            # Fallback to AppBus if server not available
            self.bus.volumeChangeRequested.emit(-1, volume)
    
    # Removed playlist selection - adaptive audio always uses Playlist 1
    # def _on_playlist_selected(self, playlist_id: int):
    #     """Handle playlist selection."""
    #     # Adaptive audio always uses Playlist 1 - no manual selection needed
    
    def _on_shuffle_toggled(self, checked: bool):
        """Handle shuffle toggle."""
        self.bus.shuffleToggled.emit(checked)
    
    # Removed bypass audio processing and zone methods as requested
    
    # ================================================================
    # STATE UPDATE HANDLERS (Receive from AppBus)
    # ================================================================
    
    def _on_pointer_updated(self, x_m: float, y_m: float, ts: float, source: str):
        """Update floorplan pointer - simplified for non-zone adaptive audio."""
        # Update floorplan visualization
        self.floorplan.map_pointer(x_m, y_m)
        
        # No zone logic needed - adaptive audio now works purely on position-based panning
    
    # Removed zone checking methods - adaptive audio no longer uses zones
    
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
    
    def _poll_queue_state(self):
        """Poll queue state directly from server."""
        if self.server and hasattr(self.server, 'adaptive_audio_server'):
            adaptive_server = self.server.adaptive_audio_server
            if adaptive_server:
                # Get queue preview and current track directly
                queue_preview = adaptive_server.get_queue_preview(5)
                current_track = adaptive_server.get_current_song()
                
                # Update mini player directly
                self.mini_player.update_queue_list(queue_preview)
                self.mini_player.update_current_track(current_track)
