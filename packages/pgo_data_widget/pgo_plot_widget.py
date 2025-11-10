"""
PgoPlotWidget - Real-Time Position Plotting

Displays real-time position tracking data with diagnostic capabilities.
Uses matplotlib for plotting with configurable update rates and history limits.

Features:
- Path plot (trail of positions)
- Grid overlay (8×10 cells, 0.60 m per cell)
- Axis labels and scaling (4.80 m × 6.00 m bounds)
- Controls: pause/resume, clear, export CSV/PNG
- Rate limiting for smooth performance
"""

import numpy as np
import time
from collections import deque
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFileDialog, QMessageBox)
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt


class PgoPlotWidget(QWidget):
    """
    Real-time position plotting widget.
    
    Subscribes to AppBus.pointerUpdated and displays position history.
    Includes controls for pause/resume, clear, and export.
    """
    
    def __init__(self, app_bus, services, settings, parent=None):
        """
        Initialize PgoPlotWidget.
        
        Args:
            app_bus: AppBus instance for communication
            services: Services dictionary
            settings: QSettings instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.bus = app_bus
        self.settings = settings
        
        # Configuration
        self.world_width_m = settings.value("world/width_m", 4.80, type=float)
        self.world_height_m = settings.value("world/height_m", 6.00, type=float)
        self.grid_cols = settings.value("grid/cols", 8, type=int)
        self.grid_rows = settings.value("grid/rows", 10, type=int)
        self.refresh_rate_fps = settings.value("pgo/refresh_rate_fps", 30, type=int)
        self.max_history = settings.value("pgo/max_history_points", 1000, type=int)
        
        # Data storage
        self.position_history = deque(maxlen=self.max_history)  # [(x, y, ts), ...]
        self.update_queue = deque()  # Pending updates
        
        # State
        self.is_paused = False
        
        # Setup UI
        self._setup_ui()
        
        # Connect to AppBus
        self._connect_signals()
        
        # Setup redraw timer (rate limiting)
        self.redraw_timer = QTimer()
        self.redraw_timer.timeout.connect(self._redraw_plot)
        self.redraw_timer.start(1000 // self.refresh_rate_fps)  # Convert FPS to ms
    
    def _setup_ui(self):
        """Build the UI components."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Left side: Plot area
        plot_container = QVBoxLayout()
        plot_container.setContentsMargins(16, 16, 16, 16)
        
        # Title
        title = QLabel("PGO Position Data - Real-Time Plot")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        plot_container.addWidget(title)
        
        # Matplotlib figure with preserved aspect ratio
        # Calculate figure size to maintain aspect ratio
        aspect_ratio = self.world_width_m / self.world_height_m
        base_height = 6
        base_width = base_height * aspect_ratio
        
        self.figure = Figure(figsize=(base_width, base_height), facecolor='#ffffff')
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111, facecolor='#f5f5f5')
        plot_container.addWidget(self.canvas, stretch=1)
        
        # Setup plot
        self._setup_plot()
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self._toggle_pause)
        controls_layout.addWidget(self.pause_button)
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._clear_data)
        controls_layout.addWidget(self.clear_button)
        
        self.export_csv_button = QPushButton("Export CSV")
        self.export_csv_button.clicked.connect(self._export_csv)
        controls_layout.addWidget(self.export_csv_button)
        
        self.export_png_button = QPushButton("Export PNG")
        self.export_png_button.clicked.connect(self._export_png)
        controls_layout.addWidget(self.export_png_button)
        
        controls_layout.addStretch()
        
        # Stats label
        self.stats_label = QLabel("Points: 0 | Paused: No")
        controls_layout.addWidget(self.stats_label)
        
        plot_container.addLayout(controls_layout)
        
        # Add plot container to main layout
        plot_widget = QWidget()
        plot_widget.setLayout(plot_container)
        main_layout.addWidget(plot_widget, stretch=1)
        
        # Right sidebar
        sidebar = QVBoxLayout()
        sidebar.setContentsMargins(16, 16, 16, 16)
        sidebar.setSpacing(12)
        
        sidebar_title = QLabel("Statistics")
        sidebar_title.setStyleSheet("font-size: 12pt; font-weight: bold;")
        sidebar.addWidget(sidebar_title)
        
        # Placeholder for future sidebar content
        sidebar.addStretch()
        
        sidebar_widget = QWidget()
        sidebar_widget.setLayout(sidebar)
        sidebar_widget.setMinimumWidth(200)
        sidebar_widget.setMaximumWidth(200)
        sidebar_widget.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-left: 1px solid #d0d0d0;
            }
        """)
        main_layout.addWidget(sidebar_widget, stretch=0)
        
        # Apply light theme
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
            QPushButton {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
    
    def _setup_plot(self):
        """Configure plot appearance."""
        # Set limits
        self.ax.set_xlim(0, self.world_width_m)
        self.ax.set_ylim(0, self.world_height_m)
        
        # Invert Y-axis (world coordinates increase downward)
        self.ax.invert_yaxis()
        
        # Labels
        self.ax.set_xlabel('X (meters)', color='#000000')
        self.ax.set_ylabel('Y (meters)', color='#000000')
        self.ax.set_title('User Position Tracking', color='#000000', fontsize=12)
        
        # Grid
        cell_width = self.world_width_m / self.grid_cols
        cell_height = self.world_height_m / self.grid_rows
        
        x_ticks = np.arange(0, self.world_width_m + cell_width, cell_width)
        y_ticks = np.arange(0, self.world_height_m + cell_height, cell_height)
        
        self.ax.set_xticks(x_ticks)
        self.ax.set_yticks(y_ticks)
        self.ax.grid(True, color='#d0d0d0', linestyle='--', linewidth=0.5)
        
        # Style
        self.ax.tick_params(colors='#000000')
        for spine in self.ax.spines.values():
            spine.set_color('#000000')
        
        # Preserve aspect ratio based on world dimensions
        aspect_ratio = self.world_width_m / self.world_height_m
        self.ax.set_aspect('equal', adjustable='box')
        
        # Initialize line plot
        self.line, = self.ax.plot([], [], 'r-', linewidth=1, alpha=0.7, label='Path')
        self.scatter = self.ax.scatter([], [], c='red', s=20, alpha=0.8, label='Position')
        
        self.ax.legend(facecolor='#1a1a1a', edgecolor='white', labelcolor='white')
        
        self.figure.tight_layout()
    
    def _connect_signals(self):
        """Connect to AppBus signals."""
        self.bus.pointerUpdated.connect(self._on_pointer_updated)
    
    def _on_pointer_updated(self, x_m: float, y_m: float, ts: float, source: str):
        """
        Handle position update from AppBus.
        
        Args:
            x_m: X coordinate in meters
            y_m: Y coordinate in meters
            ts: Timestamp
            source: Source identifier
        """
        if not self.is_paused:
            # Queue update (will be processed in batch during redraw)
            self.update_queue.append((x_m, y_m, ts))
    
    def _redraw_plot(self):
        """Process queued updates and redraw plot (called by timer)."""
        if not self.update_queue:
            return
        
        # Process all queued updates
        while self.update_queue:
            x_m, y_m, ts = self.update_queue.popleft()
            self.position_history.append((x_m, y_m, ts))
        
        # Extract data for plotting
        if len(self.position_history) > 0:
            x_data = [p[0] for p in self.position_history]
            y_data = [p[1] for p in self.position_history]
            
            # Update line plot (trail)
            self.line.set_data(x_data, y_data)
            
            # Update scatter plot (all points)
            self.scatter.set_offsets(np.c_[x_data, y_data])
            
            # Redraw
            self.canvas.draw_idle()
            
            # Update stats
            self._update_stats()
    
    def _update_stats(self):
        """Update statistics label."""
        paused_text = "Yes" if self.is_paused else "No"
        self.stats_label.setText(f"Points: {len(self.position_history)} | Paused: {paused_text}")
    
    def _toggle_pause(self):
        """Toggle pause state."""
        self.is_paused = not self.is_paused
        self.pause_button.setText("Resume" if self.is_paused else "Pause")
        self._update_stats()
    
    def _clear_data(self):
        """Clear all position data."""
        self.position_history.clear()
        self.update_queue.clear()
        self.line.set_data([], [])
        self.scatter.set_offsets(np.empty((0, 2)))
        self.canvas.draw_idle()
        self._update_stats()
    
    def _export_csv(self):
        """Export position data to CSV file."""
        if len(self.position_history) == 0:
            QMessageBox.warning(self, "No Data", "No position data to export.")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "", "CSV Files (*.csv);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write("timestamp,x_m,y_m\n")
                    for x, y, ts in self.position_history:
                        f.write(f"{ts:.6f},{x:.6f},{y:.6f}\n")
                QMessageBox.information(self, "Export Successful", f"Data exported to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Error: {str(e)}")
    
    def _export_png(self):
        """Export plot as PNG image."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export PNG", "", "PNG Files (*.png);;All Files (*)"
        )
        
        if filename:
            try:
                self.figure.savefig(filename, dpi=150, facecolor='#1a1a1a', edgecolor='none')
                QMessageBox.information(self, "Export Successful", f"Plot exported to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Error: {str(e)}")

