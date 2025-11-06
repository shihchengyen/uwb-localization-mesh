# DummyServerBringUp Interface Guide

## Overview

The `DummyServerBringUpProMax` class provides a complete simulation environment for UWB localization systems without requiring physical hardware. This guide explains how to interface with the dummy server to build PyQt applications and integrate it into your localization demos.

## Table of Contents

1. [Core Interface](#core-interface)
2. [PyQt Application Integration](#pyqt-application-integration)
3. [Audio Demo Integration](#audio-demo-integration)
4. [Position Data Access](#position-data-access)
5. [Configuration Options](#configuration-options)
6. [Error Handling](#error-handling)
7. [Complete Examples](#complete-examples)

## Core Interface

### Class Initialization

```python
from Demos.DummyServerBringUp import DummyServerBringUpProMax
from packages.uwb_mqtt_server.config import MQTTConfig

# Basic initialization (no audio features)
server = DummyServerBringUpProMax()

# With audio features enabled
mqtt_config = MQTTConfig(broker="localhost", port=1884)
server = DummyServerBringUpProMax(
    mqtt_config=mqtt_config,
    simulation_speed=1.0,      # Real-time simulation
    phone_node_id=0,           # Simulated phone ID
    window_size_seconds=1.0    # Binning window size
)
```

### Essential Methods

#### Server Control
```python
# Start the simulation and processing
server.start()

# Stop all processing and cleanup
server.stop()
```

#### Audio Demo Control
```python
# Start adaptive audio demo
server.adaptive_audio_demo()

# Stop adaptive audio demo
server.stop_adaptive_audio_demo()

# Start zone DJ demo (all speakers at 70%)
server.zone_dj_demo()

# Stop zone DJ demo
server.stop_zone_dj_demo()

# Set playlist (1-5)
server.set_playlist(3)
```

#### Position Access
```python
# Thread-safe position access
with server._position_lock:
    current_position = server.user_position  # numpy array [x, y, z] in cm
```

## PyQt Application Integration

### Method 1: Direct Integration

```python
import sys
import time
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton
from PyQt5.QtCore import QTimer
from Demos.DummyServerBringUp import DummyServerBringUpProMax

class LocalizationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UWB Localization Demo")
        self.resize(800, 600)
        
        # Initialize dummy server
        self.server = DummyServerBringUpProMax(simulation_speed=2.0)
        
        # Setup UI
        self.setup_ui()
        
        # Setup position update timer
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_position_display)
        self.position_timer.start(100)  # Update every 100ms
        
        # Start server
        self.server.start()
    
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Position display
        self.position_label = QLabel("Position: Not available")
        layout.addWidget(self.position_label)
        
        # Audio control buttons
        self.adaptive_btn = QPushButton("Start Adaptive Audio")
        self.adaptive_btn.clicked.connect(self.toggle_adaptive_audio)
        layout.addWidget(self.adaptive_btn)
        
        self.zone_dj_btn = QPushButton("Start Zone DJ")
        self.zone_dj_btn.clicked.connect(self.toggle_zone_dj)
        layout.addWidget(self.zone_dj_btn)
    
    def update_position_display(self):
        """Update position display from server"""
        with self.server._position_lock:
            pos = self.server.user_position
        
        if pos is not None:
            self.position_label.setText(f"Position: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}) cm")
        else:
            self.position_label.setText("Position: Waiting for PGO convergence...")
    
    def toggle_adaptive_audio(self):
        # Implementation depends on your audio state tracking
        self.server.adaptive_audio_demo()
    
    def toggle_zone_dj(self):
        # Implementation depends on your audio state tracking
        self.server.zone_dj_demo()
    
    def closeEvent(self, event):
        """Cleanup on application close"""
        self.server.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LocalizationApp()
    window.show()
    sys.exit(app.exec_())
```

### Method 2: Using the UnifiedDemo Framework

The dummy server integrates seamlessly with the existing UnifiedDemo framework:

```bash
# Run with dummy server
python Demos/UnifiedDemo/main_demo.py --dummy

# Run with real hardware (default)
python Demos/UnifiedDemo/main_demo.py
```

The UnifiedDemo automatically detects the `--dummy` flag and switches to simulation mode:

```python
# In your application
def _start_server_bringup(use_dummy=False):
    if use_dummy:
        from Demos.DummyServerBringUp import DummyServerBringUpProMax
        return DummyServerBringUpProMax()
    else:
        from ServerBringUp import ServerBringUpProMax
        return ServerBringUpProMax()

# Usage
server = _start_server_bringup(use_dummy=True)
server.start()
```

## Audio Demo Integration

### Adaptive Audio Demo

The adaptive audio demo simulates position-based audio control:

```python
class AdaptiveAudioWidget(QWidget):
    def __init__(self, server):
        super().__init__()
        self.server = server
        self.audio_active = False
        
        # Setup UI
        self.start_btn = QPushButton("Start Adaptive Audio")
        self.start_btn.clicked.connect(self.toggle_adaptive_audio)
        
        # Playlist controls
        self.playlist_btns = []
        for i in range(1, 6):
            btn = QPushButton(f"Playlist {i}")
            btn.clicked.connect(lambda checked, p=i: self.set_playlist(p))
            self.playlist_btns.append(btn)
    
    def toggle_adaptive_audio(self):
        if not self.audio_active:
            self.server.adaptive_audio_demo()
            self.start_btn.setText("Stop Adaptive Audio")
            self.audio_active = True
        else:
            self.server.stop_adaptive_audio_demo()
            self.start_btn.setText("Start Adaptive Audio")
            self.audio_active = False
    
    def set_playlist(self, playlist_number):
        self.server.set_playlist(playlist_number)
```

### Zone DJ Demo

The zone DJ demo provides zone-based audio control:

```python
class ZoneDJWidget(QWidget):
    def __init__(self, server):
        super().__init__()
        self.server = server
        self.dj_active = False
        
        # Setup UI
        self.dj_btn = QPushButton("Start Zone DJ")
        self.dj_btn.clicked.connect(self.toggle_zone_dj)
    
    def toggle_zone_dj(self):
        if not self.dj_active:
            self.server.zone_dj_demo()
            self.dj_btn.setText("Stop Zone DJ")
            self.dj_active = True
        else:
            self.server.stop_zone_dj_demo()
            self.dj_btn.setText("Start Zone DJ")
            self.dj_active = False
```

## Position Data Access

### Real-time Position Monitoring

```python
class PositionMonitor(QWidget):
    def __init__(self, server):
        super().__init__()
        self.server = server
        
        # Position history for visualization
        self.position_history = []
        self.max_history = 1000
        
        # Update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_position)
        self.timer.start(50)  # 20Hz update rate
    
    def update_position(self):
        """Get latest position and update visualization"""
        with self.server._position_lock:
            pos = self.server.user_position
        
        if pos is not None:
            # Add to history
            self.position_history.append(pos.copy())
            if len(self.position_history) > self.max_history:
                self.position_history.pop(0)
            
            # Update visualization
            self.update_display(pos)
    
    def update_display(self, position):
        """Override this method to implement your visualization"""
        pass
```

### Position-based Logic

```python
def check_position_zones(self, position):
    """Example: Check if user is in specific zones"""
    x, y, z = position
    
    # Define zones (in cm)
    zones = {
        "entrance": (50, 50, 100, 100),    # x1, y1, x2, y2
        "stage": (200, 400, 350, 550),
        "bar": (400, 100, 480, 200)
    }
    
    current_zones = []
    for zone_name, (x1, y1, x2, y2) in zones.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            current_zones.append(zone_name)
    
    return current_zones
```

## Configuration Options

### Simulation Parameters

```python
server = DummyServerBringUpProMax(
    # MQTT configuration for audio features
    mqtt_config=MQTTConfig(broker="localhost", port=1884),
    
    # Simulation speed multiplier (1.0 = real-time)
    simulation_speed=2.0,
    
    # Simulated phone node ID
    phone_node_id=0,
    
    # Binning window size for measurements
    window_size_seconds=1.0,
    
    # Anchor position jitter (disabled by default)
    jitter_std=0.0
)
```

### Space Configuration

The dummy server simulates a 4.8m × 6m space with anchors at:
- Anchor 0: (480, 600, 0) cm - top-right
- Anchor 1: (0, 600, 0) cm - top-left  
- Anchor 2: (480, 0, 0) cm - bottom-right
- Anchor 3: (0, 0, 0) cm - bottom-left

### Movement Pattern

The simulation uses a figure-8 Lissajous pattern:
```python
def _get_simulated_position(self, t: float) -> np.ndarray:
    scale_t = t * self.simulation_speed * 0.5
    
    # Figure-8 parameters
    a = 200  # Width (cm)
    b = 150  # Height (cm)
    
    # Center in space
    center_x = 240  # cm
    center_y = 300  # cm
    
    # Lissajous curve
    x = center_x + a * math.sin(scale_t)
    y = center_y + b * math.sin(2 * scale_t)
    z = 0.0
    
    return np.array([x, y, z])
```

## Error Handling

### Graceful Degradation

The dummy server handles missing dependencies gracefully:

```python
try:
    from packages.audio_mqtt_server.adaptive_audio_controller import AdaptiveAudioController
    audio_available = True
except ImportError:
    audio_available = False
    print("Audio features disabled - AdaptiveAudioController not available")

# Your application should check audio availability
if hasattr(server, 'adaptive_audio_server') and server.adaptive_audio_server:
    # Audio features available
    server.adaptive_audio_demo()
else:
    # Fallback behavior
    print("Audio demo not available in this configuration")
```

### Connection Handling

```python
def safe_server_operation(server, operation):
    """Safely execute server operations with error handling"""
    try:
        operation()
        return True
    except Exception as e:
        print(f"Server operation failed: {e}")
        return False

# Usage
success = safe_server_operation(server, lambda: server.adaptive_audio_demo())
if not success:
    # Handle failure
    show_error_message("Audio demo failed to start")
```

## Complete Examples

### Minimal Localization Viewer

```python
import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from Demos.DummyServerBringUp import DummyServerBringUpProMax

class MinimalViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minimal UWB Viewer")
        
        # Server setup
        self.server = DummyServerBringUpProMax(simulation_speed=1.5)
        
        # UI setup
        self.setup_ui()
        
        # Start everything
        self.server.start()
        
        # Position update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(100)
    
    def setup_ui(self):
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)
        
        # Position display
        self.pos_label = QLabel("Position: Initializing...")
        self.pos_label.setFont(QFont("Arial", 14))
        layout.addWidget(self.pos_label)
        
        # Simple visualization area
        self.viz_area = QLabel()
        self.viz_area.setMinimumSize(480, 600)
        self.viz_area.setStyleSheet("border: 1px solid black; background: white;")
        layout.addWidget(self.viz_area)
    
    def update_display(self):
        with self.server._position_lock:
            pos = self.server.user_position
        
        if pos is not None:
            self.pos_label.setText(f"Position: ({pos[0]:.1f}, {pos[1]:.1f}) cm")
            self.draw_position(pos)
        else:
            self.pos_label.setText("Position: Waiting for convergence...")
    
    def draw_position(self, pos):
        """Draw current position on visualization area"""
        pixmap = QPixmap(480, 600)
        pixmap.fill(Qt.white)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw anchors
        painter.setBrush(QBrush(Qt.red))
        anchor_positions = [(480, 0), (0, 0), (480, 600), (0, 600)]  # Flipped Y
        for ax, ay in anchor_positions:
            painter.drawEllipse(ax-5, ay-5, 10, 10)
        
        # Draw user position
        painter.setBrush(QBrush(Qt.blue))
        x, y = int(pos[0]), int(600 - pos[1])  # Flip Y coordinate
        painter.drawEllipse(x-8, y-8, 16, 16)
        
        painter.end()
        self.viz_area.setPixmap(pixmap)
    
    def closeEvent(self, event):
        self.server.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = MinimalViewer()
    viewer.show()
    sys.exit(app.exec_())
```

### Advanced Integration with Floorplan

```python
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from Demos.DummyServerBringUp import DummyServerBringUpProMax

class FloorplanViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Floorplan Localization Demo")
        self.resize(1000, 800)
        
        # Server with audio
        from packages.uwb_mqtt_server.config import MQTTConfig
        mqtt_config = MQTTConfig(broker="localhost", port=1884)
        self.server = DummyServerBringUpProMax(
            mqtt_config=mqtt_config,
            simulation_speed=1.0
        )
        
        self.setup_ui()
        self.server.start()
        
        # Update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_position)
        self.timer.start(50)  # 20Hz
    
    def setup_ui(self):
        # Main widget with tabs
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        
        # Visualization tab
        viz_tab = QWidget()
        tabs.addTab(viz_tab, "Visualization")
        
        viz_layout = QVBoxLayout(viz_tab)
        
        # Controls
        controls = QHBoxLayout()
        
        self.adaptive_btn = QPushButton("Start Adaptive Audio")
        self.adaptive_btn.clicked.connect(self.toggle_adaptive_audio)
        controls.addWidget(self.adaptive_btn)
        
        self.zone_dj_btn = QPushButton("Start Zone DJ")
        self.zone_dj_btn.clicked.connect(self.toggle_zone_dj)
        controls.addWidget(self.zone_dj_btn)
        
        # Playlist buttons
        for i in range(1, 6):
            btn = QPushButton(f"Playlist {i}")
            btn.clicked.connect(lambda checked, p=i: self.server.set_playlist(p))
            controls.addWidget(btn)
        
        viz_layout.addLayout(controls)
        
        # Graphics view for floorplan
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        viz_layout.addWidget(self.view)
        
        # Load floorplan background
        self.load_floorplan()
        
        # Position indicator
        self.position_item = None
    
    def load_floorplan(self):
        """Load floorplan image as background"""
        # You would load your actual floorplan image here
        # For demo, create a simple background
        pixmap = QPixmap(480, 600)
        pixmap.fill(Qt.lightGray)
        
        painter = QPainter(pixmap)
        painter.setPen(QPen(Qt.black, 2))
        painter.drawRect(0, 0, 479, 599)
        painter.drawText(10, 20, "Simulated Space: 4.8m × 6m")
        painter.end()
        
        self.scene.addPixmap(pixmap)
        self.scene.setSceneRect(0, 0, 480, 600)
    
    def update_position(self):
        with self.server._position_lock:
            pos = self.server.user_position
        
        if pos is not None:
            self.draw_user_position(pos)
    
    def draw_user_position(self, pos):
        """Draw user position on floorplan"""
        if self.position_item:
            self.scene.removeItem(self.position_item)
        
        x, y = pos[0], 600 - pos[1]  # Flip Y coordinate
        self.position_item = self.scene.addEllipse(
            x-10, y-10, 20, 20,
            QPen(Qt.blue, 2),
            QBrush(Qt.blue)
        )
    
    def toggle_adaptive_audio(self):
        # Toggle adaptive audio demo
        if self.adaptive_btn.text() == "Start Adaptive Audio":
            self.server.adaptive_audio_demo()
            self.adaptive_btn.setText("Stop Adaptive Audio")
        else:
            self.server.stop_adaptive_audio_demo()
            self.adaptive_btn.setText("Start Adaptive Audio")
    
    def toggle_zone_dj(self):
        # Toggle zone DJ demo
        if self.zone_dj_btn.text() == "Start Zone DJ":
            self.server.zone_dj_demo()
            self.zone_dj_btn.setText("Stop Zone DJ")
        else:
            self.server.stop_zone_dj_demo()
            self.zone_dj_btn.setText("Start Zone DJ")
    
    def closeEvent(self, event):
        self.server.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = FloorplanViewer()
    viewer.show()
    sys.exit(app.exec_())
```

## Summary

The `DummyServerBringUpProMax` provides a complete interface for building PyQt localization applications without requiring physical hardware. Key integration points:

1. **Server Lifecycle**: Use `start()` and `stop()` methods
2. **Position Access**: Thread-safe access via `_position_lock`
3. **Audio Integration**: Built-in demo methods for adaptive audio and zone DJ
4. **Configuration**: Flexible simulation parameters
5. **Error Handling**: Graceful degradation when dependencies are missing

The dummy server maintains the same interface as the real `ServerBringUpProMax`, making it a true drop-in replacement for development and testing.
