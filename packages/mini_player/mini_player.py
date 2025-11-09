"""
MiniPlayer - Compact Audio Player Control Widget

A reusable, shared subwidget for audio playback controls. This is instantiated
by parent widgets (AdaptiveAudioWidget, ZoneDjWidget) with specific parameters.

Features:
- Play/Pause/Stop/Skip controls
- Volume slider
- Progress bar
- Current track display
- Queue display (optional)
- Playlist selector
"""

import os

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QSlider, QListWidget, QComboBox, QProgressBar,
                             QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal as Signal, QSize
from PyQt5.QtGui import QFont, QIcon


class MiniPlayer(QWidget):
    """
    Compact audio player control widget.
    
    Signals:
        Playback control signals - emitted when user interacts with controls
        Parent widgets connect to these and emit to AppBus
    """
    
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
    
    def __init__(self, mode="adaptive", show_queue=True, parent=None):
        """
        Initialize MiniPlayer.
        
        Args:
            mode: "adaptive" or "zone_dj" - affects UI presentation
            show_queue: Whether to show queue list
            parent: Parent widget
        """
        super().__init__(parent)
        self.mode = mode
        self.show_queue = show_queue
        self._is_playing = False
        self._icon_size = QSize(22, 22)
        
        # Set fixed width for consistency
        self.setMinimumWidth(350)
        self.setMaximumWidth(350)
        
        self._setup_ui()
        self._apply_stylesheet()
    
    def _load_icon(self, filename: str) -> QIcon:
        """Load an icon from the assets folder, returning an empty icon if missing."""
        icon_path = os.path.join(os.path.dirname(__file__), "assets", filename)
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            if not icon.isNull():
                return icon
        return QIcon()

    def _setup_ui(self):
        """Build the UI components matching UI_Design_Mockup.html"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Current track display (structured: icon + title/artist/album/time)
        track_display = QVBoxLayout()
        track_display.setSpacing(4)
        
        # Title row with music icon
        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)
        music_icon = QLabel("♪")
        music_icon.setStyleSheet("font-size: 14pt; color: #000000;")
        title_layout.addWidget(music_icon)
        
        self.track_title_label = QLabel("Song Title - Artist Name")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.track_title_label.setFont(font)
        title_layout.addWidget(self.track_title_label, stretch=1)
        track_display.addLayout(title_layout)
        
        # Album name
        self.track_album_label = QLabel("Album Name")
        font_album = QFont()
        font_album.setPointSize(10)
        self.track_album_label.setFont(font_album)
        self.track_album_label.setStyleSheet("color: #000000;")
        track_display.addWidget(self.track_album_label)
        
        # Time display
        self.track_time_label = QLabel("3:45 / 5:23")
        font_time = QFont()
        font_time.setPointSize(10)
        self.track_time_label.setFont(font_time)
        self.track_time_label.setStyleSheet("color: #888888;")
        track_display.addWidget(self.track_time_label)
        
        layout.addLayout(track_display)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        layout.addWidget(self.progress_bar)
        
        # Progress time labels (current / total)
        progress_time_layout = QHBoxLayout()
        self.progress_current_label = QLabel("3:45")
        self.progress_current_label.setStyleSheet("font-size: 9pt; color: #888888;")
        progress_time_layout.addWidget(self.progress_current_label)
        progress_time_layout.addStretch()
        self.progress_total_label = QLabel("5:23")
        self.progress_total_label.setStyleSheet("font-size: 9pt; color: #888888;")
        progress_time_layout.addWidget(self.progress_total_label)
        layout.addLayout(progress_time_layout)
        
        # Playback controls (Previous | Play/Pause | Next) - simplified
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(12)
        controls_layout.setContentsMargins(0, 8, 0, 8)
        
        # Add stretch to center buttons
        controls_layout.addStretch()
        
        # Previous button
        self.previous_button = QPushButton("")
        self.previous_button.setObjectName("previousButton")
        self.previous_button.setFixedSize(48, 48)
        self.previous_button.clicked.connect(self.previousRequested.emit)
        prev_icon = self._load_icon("skip_previous.svg")
        if not prev_icon.isNull():
            self.previous_button.setIcon(prev_icon)
            self.previous_button.setIconSize(self._icon_size)
        else:
            self.previous_button.setText("⏮")
        controls_layout.addWidget(self.previous_button)
        
        # Play/Pause button (white background)
        self.play_pause_button = QPushButton("▶")
        self.play_pause_button.setObjectName("playButton")
        self.play_pause_button.setFixedSize(48, 48)
        self.play_pause_button.clicked.connect(self._on_play_pause_clicked)
        controls_layout.addWidget(self.play_pause_button)
        
        # Next button
        self.next_button = QPushButton("")
        self.next_button.setObjectName("nextButton")
        self.next_button.setFixedSize(48, 48)
        self.next_button.clicked.connect(self.skipRequested.emit)
        next_icon = self._load_icon("skip_next.svg")
        if not next_icon.isNull():
            self.next_button.setIcon(next_icon)
            self.next_button.setIconSize(self._icon_size)
        else:
            self.next_button.setText("⏭")
        controls_layout.addWidget(self.next_button)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Volume control (label on top, slider below, value below slider)
        volume_group = QVBoxLayout()
        volume_group.setSpacing(8)
        
        # Volume label with icon
        volume_header = QHBoxLayout()
        volume_header.setSpacing(8)
        volume_icon = QLabel("◉")
        volume_icon.setStyleSheet("font-size: 14pt; color: #000000;")
        volume_header.addWidget(volume_icon)
        volume_text = QLabel("Volume")
        volume_text.setStyleSheet("font-size: 10pt; color: #000000;")
        volume_header.addWidget(volume_text)
        volume_header.addStretch()
        volume_group.addLayout(volume_header)
        
        # Volume slider
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.valueChanged.connect(self.volumeChanged.emit)
        volume_group.addWidget(self.volume_slider)
        
        # Volume percentage
        self.volume_label_val = QLabel("70%")
        self.volume_label_val.setStyleSheet("font-size: 9pt; color: #888888;")
        self.volume_slider.valueChanged.connect(lambda v: self.volume_label_val.setText(f"{v}%"))
        volume_group.addWidget(self.volume_label_val)
        
        layout.addLayout(volume_group)
        
        # Playlist selector (icon + dropdown)
        playlist_layout = QHBoxLayout()
        playlist_layout.setSpacing(8)
        playlist_icon = QLabel("|||")  # Vertical bars icon (simplified)
        playlist_icon.setStyleSheet("font-size: 12pt; color: #000000;")
        playlist_layout.addWidget(playlist_icon)
        
        self.playlist_combo = QComboBox()
        self.playlist_combo.addItems([
            "Playlist 1",
            "Playlist 2",
            "Playlist 3",
            "Playlist 4",
            "Playlist 5"
        ])
        self.playlist_combo.currentIndexChanged.connect(lambda idx: self.playlistSelected.emit(idx + 1))
        playlist_layout.addWidget(self.playlist_combo, stretch=1)
        
        layout.addLayout(playlist_layout)
        
        # Queue display (optional)
        if self.show_queue:
            queue_label = QLabel("Queue Preview")
            font_queue = QFont()
            font_queue.setPointSize(10)
            font_queue.setWeight(600)
            queue_label.setFont(font_queue)
            queue_label.setStyleSheet("color: #000000; margin-top: 8px;")
            layout.addWidget(queue_label)
            
            self.queue_list = QListWidget()
            self.queue_list.setMinimumHeight(150)
            layout.addWidget(self.queue_list)
        
        layout.addStretch()
    
    def _apply_stylesheet(self):
        """Apply light theme stylesheet"""
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
            
            QLabel {
                color: #000000;
            }
            
            /* Playback Buttons - transparent background, pure black icons */
            QPushButton#previousButton,
            QPushButton#nextButton {
                background-color: transparent;
                border: none;
                border-radius: 24px;
                width: 48px;
                height: 48px;
                min-width: 48px;
                min-height: 48px;
                max-width: 48px;
                max-height: 48px;
                color: #000000;
                font-size: 16pt;
            }
            
            QPushButton#previousButton:hover,
            QPushButton#nextButton:hover {
                background-color: rgba(0, 0, 0, 0.05);
            }
            
            QPushButton#previousButton:pressed,
            QPushButton#nextButton:pressed {
                background-color: rgba(0, 0, 0, 0.1);
            }
            
            /* Play/Pause Button - black circle on white */
            QPushButton#playButton,
            QPushButton#pauseButton {
                background-color: #000000;
                border: none;
                border-radius: 24px;
                width: 48px;
                height: 48px;
                min-width: 48px;
                min-height: 48px;
                max-width: 48px;
                max-height: 48px;
                color: #ffffff;
                font-size: 16pt;
            }
            
            QPushButton#playButton:hover,
            QPushButton#pauseButton:hover {
                background-color: #333333;
            }
            
            QPushButton#playButton:pressed,
            QPushButton#pauseButton:pressed {
                background-color: #555555;
            }
            
            /* Progress Bar */
            QProgressBar {
                background-color: rgba(0, 0, 0, 0.15);
                border: none;
                border-radius: 2px;
                height: 4px;
            }
            
            QProgressBar::chunk {
                background-color: #000000;
                border-radius: 2px;
            }
            
            /* Volume Slider */
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(0, 0, 0, 0.15);
                border-radius: 2px;
            }
            
            QSlider::handle:horizontal {
                background: #000000;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            
            QSlider::handle:horizontal:hover {
                width: 14px;
                height: 14px;
                margin: -5px 0;
            }
            
            QSlider::sub-page:horizontal {
                background: #000000;
                border-radius: 2px;
            }
            
            /* Playlist Dropdown */
            QComboBox {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid rgba(0, 0, 0, 0.2);
                border-radius: 4px;
                padding: 6px 8px;
            }
            
            QComboBox:hover {
                border: 1px solid rgba(0, 0, 0, 0.4);
            }
            
            QComboBox::drop-down {
                border: none;
            }
            
            QComboBox QAbstractItemView {
                background-color: #f5f5f5;
                color: #000000;
                selection-background-color: #000000;
                selection-color: #ffffff;
            }
            
            /* Queue List */
            QListWidget {
                background-color: transparent;
                color: #666666;
                border: none;
            }
            
            QListWidget::item {
                padding: 8px;
                color: #666666;
            }
            
            QListWidget::item:hover {
                color: #000000;
                background-color: rgba(0, 0, 0, 0.05);
            }
        """)
    
    def _on_play_pause_clicked(self):
        """Handle play/pause button click."""
        if self._is_playing:
            self.pauseRequested.emit()
        else:
            self.playRequested.emit()
    
    # ============================================================
    # PUBLIC METHODS (Called by parent widget)
    # ============================================================
    
    def update_queue_list(self, queue_preview: list) -> None:
        """Update the displayed queue with list of track names."""
        if self.show_queue:
            self.queue_list.clear()
            # Add items with icons: ▶ for next track, ✓ for upcoming tracks
            for i, track_name in enumerate(queue_preview):
                if i == 0:
                    icon = "▶ "  # Next track
                else:
                    icon = "✓ "  # Upcoming tracks
                self.queue_list.addItem(icon + track_name)
    
    def update_current_track(self, track_name: str) -> None:
        """Update the currently playing track display."""
        self.track_title_label.setText(track_name)
    
    def set_track_name(self, track_name: str) -> None:
        """Set the track name label."""
        self.track_title_label.setText(track_name)
    
    def set_progress(self, progress: float) -> None:
        """Set playback progress bar (0.0-1.0)."""
        self.progress_bar.setValue(int(progress * 1000))
    
    def set_volume_slider(self, volume: int) -> None:
        """Set volume slider position (0-100)."""
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(volume)
        self.volume_slider.blockSignals(False)
        self.volume_label_val.setText(f"{volume}%")
    
    def set_playing_state(self, is_playing: bool) -> None:
        """Update play/pause button state."""
        print(f"[MiniPlayer] set_playing_state called: {is_playing}")  # Debug
        self._is_playing = is_playing
        if is_playing:
            self.play_pause_button.setText("⏸")
            self.play_pause_button.setObjectName("pauseButton")
        else:
            self.play_pause_button.setText("▶")
            self.play_pause_button.setObjectName("playButton")
        
        # Force style refresh
        self.play_pause_button.setStyleSheet("")  # Clear first
        self._apply_stylesheet()  # Reapply
        self.play_pause_button.update()  # Force repaint
    
    def set_playlist_dropdown(self, playlist_id: int) -> None:
        """Set selected playlist in dropdown."""
        self.playlist_combo.blockSignals(True)
        self.playlist_combo.setCurrentIndex(playlist_id - 1)
        self.playlist_combo.blockSignals(False)
    
    def clear_queue(self) -> None:
        """Clear the queue display."""
        if self.show_queue:
            self.queue_list.clear()

