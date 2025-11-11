"""
FloorplanView - Floorplan Visualization with Homography

A reusable component for displaying floorplan images with world coordinate mapping.
Supports homography-based transformation, zone management, and pointer tracking.

Features:
- Image loading and display
- 4-point corner marking (manual or auto-detect)
- Homography computation (world ↔ image transformation)
- Grid projection (8×10 cells, perspective-correct)
- Circular zone placement and management
- Pointer visualization (red dot)
- Zone registration/deregistration timers
"""

import cv2
import numpy as np
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsRectItem, QGraphicsItem, QGraphicsTextItem
from PyQt5.QtCore import Qt, pyqtSignal as Signal, QPointF, QTimer, QRectF
from PyQt5.QtGui import QPixmap, QImage, QPen, QBrush, QColor, QPainter, QFont


class Zone:
    """Represents a circular zone in world coordinates."""
    def __init__(self, zone_id, x_m, y_m, radius_m=0.25):
        self.id = zone_id
        self.x = x_m
        self.y = y_m
        self.radius = radius_m
        self.is_active = False
        self.graphics_item = None  # QGraphicsEllipseItem for visualization
    
    def contains(self, x_m, y_m, hitbox_multiplier=1.5):
        """Check if point is within zone (with hitbox multiplier)."""
        distance = np.sqrt((x_m - self.x)**2 + (y_m - self.y)**2)
        return distance <= (self.radius * hitbox_multiplier)


class RectangularZone:
    """Represents a rectangular zone in world coordinates."""
    def __init__(self, zone_id, x1_m, y1_m, x2_m, y2_m):
        self.id = zone_id
        self.x1 = min(x1_m, x2_m)  # Top-left X
        self.y1 = min(y1_m, y2_m)  # Top-left Y
        self.x2 = max(x1_m, x2_m)  # Bottom-right X
        self.y2 = max(y1_m, y2_m)  # Bottom-right Y
        self.is_active = False
        self.graphics_item = None  # QGraphicsRectItem for visualization
    
    def contains(self, x_m, y_m, hitbox_multiplier=1.0):
        """Check if point is within rectangular zone."""
        return (self.x1 <= x_m <= self.x2 and 
                self.y1 <= y_m <= self.y2)


class FloorplanView(QGraphicsView):
    """
    Floorplan visualization widget with homography support.
    
    Signals:
        pointerMapped: Emitted when user clicks on floorplan (x_m, y_m)
        zoneRegistered: Emitted when user enters zone
        zoneDeregistered: Emitted when user leaves zone
        cornerMarked: Emitted when corner is marked (corner_idx, x_px, y_px)
        pixelToMeterMapped: Emitted when user clicks on floorplan or pointer moves (x_px, y_px, x_m, y_m)
    """
    
    pointerMapped = Signal(float, float)  # x_m, y_m when user clicks
    zoneRegistered = Signal(object)  # Zone object
    zoneDeregistered = Signal(object)  # Zone object
    cornerMarked = Signal(int, float, float)  # corner_idx, x_px, y_px
    pixelToMeterMapped = Signal(float, float, float, float)  # x_px, y_px, x_m, y_m when user clicks
    homographyComputed = Signal()  # Emitted when homography is successfully computed
    
    def __init__(self, world_width_m=6.00, world_height_m=4.80, grid_cols=10, grid_rows=8, default_zone_radius_m=0.25, parent=None):
        """
        Initialize FloorplanView.
        
        Args:
            world_width_m: World width in meters
            world_height_m: World height in meters
            grid_cols: Number of grid columns
            grid_rows: Number of grid rows
            default_zone_radius_m: Default radius for zones in meters
            parent: Parent widget
        """
        super().__init__(parent)
        
        # World dimensions
        self.world_width_m = world_width_m
        self.world_height_m = world_height_m
        self.grid_cols = grid_cols
        self.grid_rows = grid_rows
        self.default_zone_radius_m = default_zone_radius_m
        
        # Graphics scene
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # State
        self.image_item = None
        self.image_path = None
        self.homography_matrix = None
        self._homography_inv = None  # Cached inverse homography
        self.corners = []  # List of marked corners [(x_px, y_px), ...]
        self.marking_corners = False
        
        # Zones
        self.zones = []  # List of Zone objects
        self.next_zone_id = 1
        self.placing_zones = False
        self.max_zones = 5  # Maximum number of zones allowed
        self.zone_playlists = {}  # {zone_id: playlist_number}
        
        # Pointer tracking
        self.pointer_item = None
        self.current_pointer_pos = None  # (x_m, y_m)
        
        # Grid visualization
        self.grid_items = []
        
        # Speaker visualization (for Adaptive Audio)
        self.speaker_volumes = {}  # {speaker_id: volume}
        self.speaker_positions = {}  # {speaker_id: (x_m, y_m)}
        self.speaker_items = {}  # {speaker_id: {'icon': QGraphicsItem, 'bar_bg': QGraphicsItem, 'bar_fill': QGraphicsItem, 'text': QGraphicsTextItem}}
        self.show_speakers = False  # Only show in Adaptive Audio widget
        
        # Zone registration timers
        self.current_zone = None
        self.zone_timer = QTimer()
        self.zone_timer.timeout.connect(self._check_zone_registration)
        self.zone_timer.start(100)  # Check every 100ms
        self.zone_hover_start = None  # QTimer for hover start
        self.zone_leave_start = None  # QTimer for leave start
        self.t_register_ms = 3000  # Default registration time
        self.t_deregister_ms = 1000  # Default deregistration time
        
        # View settings
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(QColor(245, 245, 245)))
        
        # Zone dragging
        self.dragging_zone = None
        self.drag_start_pos = None
    
    def load_image(self, filename: str) -> bool:
        """
        Load a floorplan image.
        
        Args:
            filename: Path to image file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load image using OpenCV (for homography calculations)
            self.image_path = filename
            
            # Load for Qt display
            pixmap = QPixmap(filename)
            if pixmap.isNull():
                return False
            
            # Clear scene
            self.scene.clear()
            self.corners = []
            self.homography_matrix = None
            self._homography_inv = None  # Clear cached inverse
            
            # Add image to scene
            self.image_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(self.image_item)
            
            # Fit in view
            self.fitInView(self.image_item, Qt.KeepAspectRatio)
            
            return True
        except Exception as e:
            print(f"[FloorplanView] Error loading image: {e}")
            return False

    def start_marking_corners(self):
        """Enable corner marking mode."""
        self.marking_corners = True
        self.corners = []
        print("[FloorplanView] Click on 4 corners in order: TL, TR, BR, BL")
    
    def auto_detect_corners(self) -> bool:
        """
        Automatically detect floorplan corners using computer vision.
        
        Uses edge detection and contour finding to locate the floorplan rectangle,
        then extracts the 4 corner points.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.image_path:
            print("[FloorplanView] No image loaded. Please load a floorplan image first.")
            return False
        
        try:
            # Load image with OpenCV
            img = cv2.imread(self.image_path)
            if img is None:
                print(f"[FloorplanView] Failed to load image: {self.image_path}")
                return False
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape
            
            # Method 1: Try to find the largest rectangle contour
            # Apply edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Find the largest contour (likely the floorplan boundary)
                largest_contour = max(contours, key=cv2.contourArea)
                
                # Approximate contour to polygon
                epsilon = 0.02 * cv2.arcLength(largest_contour, True)
                approx = cv2.approxPolyDP(largest_contour, epsilon, True)
                
                # If we found a rectangle (4 points), use it
                if len(approx) == 4:
                    # Sort corners: TL, TR, BR, BL
                    corners = approx.reshape(4, 2)
                    # Sort by y-coordinate first, then x
                    corners = corners[corners[:, 1].argsort()]
                    top = corners[:2][corners[:2, 0].argsort()]
                    bottom = corners[2:][corners[2:, 0].argsort()]
                    sorted_corners = [
                        tuple(top[0]),  # TL
                        tuple(top[1]),  # TR
                        tuple(bottom[1]),  # BR
                        tuple(bottom[0])  # BL
                    ]
                    self.corners = sorted_corners
                    if self._compute_homography():
                        print(f"[FloorplanView] Auto-detected 4 corners: {self.corners}")
                        return True
                    else:
                        print("[FloorplanView] Failed to compute homography from detected corners.")
                        return False
            
            # Method 2: Fallback - use image corners if contour detection fails
            print("[FloorplanView] Contour detection failed, using image corners as fallback")
            self.corners = [
                (0, 0),  # TL
                (w, 0),  # TR
                (w, h),  # BR
                (0, h)   # BL
            ]
            if self._compute_homography():
                print(f"[FloorplanView] Using image corners: {self.corners}")
                return True
            else:
                print("[FloorplanView] Failed to compute homography from image corners.")
                return False
            
        except Exception as e:
            print(f"[FloorplanView] Auto-detect failed: {e}")
            import traceback
            traceback.print_exc()
        
        return False
    
    def auto_transform(self) -> bool:
        """Alias for auto_detect_corners (for toolbar compatibility)."""
        return self.auto_detect_corners()
    
    def toggle_place_zones(self, enabled: bool):
        """Toggle zone placement mode (for toolbar compatibility)."""
        self.placing_zones = enabled

    def clear_mapping(self):
        """Clear homography mapping and corners."""
        self.corners = []
        self.homography_matrix = None
        self._homography_inv = None  # Clear cached inverse
        # Clear grid
        for item in self.grid_items:
            self.scene.removeItem(item)
        self.grid_items = []
        print("[FloorplanView] Mapping cleared")
    
    def _compute_homography(self):
        """Compute homography matrix from marked corners.
        
        Returns:
            True if successful, False otherwise
        """
        if len(self.corners) != 4:
            return False
        
        # World coordinates for corners (TL, TR, BR, BL) in meters
        # New coordinate system: origin at bottom-left, Y increases upward
        world_corners = np.array([
            [0.0, self.world_height_m],  # Top-left (0, 480)
            [self.world_width_m, self.world_height_m],  # Top-right (600, 480)
            [self.world_width_m, 0.0],  # Bottom-right (600, 0)
            [0.0, 0.0]  # Bottom-left (0, 0) - origin
        ], dtype=np.float32)
        
        # Image corners in pixels
        image_corners = np.array(self.corners, dtype=np.float32)
        
        # Compute homography
        try:
            self.homography_matrix, _ = cv2.findHomography(world_corners, image_corners)
            if self.homography_matrix is not None:
                print(f"[FloorplanView] Homography computed successfully")
                # Clear cached inverse homography
                self._homography_inv = None
                # Draw grid
                self._draw_grid()
                # Redraw all zones with new homography (to update their sizes)
                # Use QTimer.singleShot to avoid blocking the UI thread
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(0, self.redraw_all_zones)
                # Emit signal that homography is ready
                self.homographyComputed.emit()
                return True
            else:
                print("[FloorplanView] Failed to compute homography matrix")
                return False
        except Exception as e:
            print(f"[FloorplanView] Error computing homography: {e}")
            return False
    
    def _draw_grid(self):
        """Draw perspective-correct grid on floorplan."""
        if self.homography_matrix is None:
            return
        
        # Clear existing grid
        for item in self.grid_items:
            self.scene.removeItem(item)
        self.grid_items = []
        
        pen = QPen(QColor(100, 100, 100, 128))
        pen.setWidth(1)
        
        cell_width = self.world_width_m / self.grid_cols
        cell_height = self.world_height_m / self.grid_rows
        
        # Draw vertical lines
        for i in range(self.grid_cols + 1):
            x_world = i * cell_width
            
            # Map top and bottom points
            top_world = np.array([[x_world, 0.0]], dtype=np.float32).reshape(-1, 1, 2)
            bottom_world = np.array([[x_world, self.world_height_m]], dtype=np.float32).reshape(-1, 1, 2)
            
            top_img = cv2.perspectiveTransform(top_world, self.homography_matrix)[0][0]
            bottom_img = cv2.perspectiveTransform(bottom_world, self.homography_matrix)[0][0]
            
            line = QGraphicsLineItem(top_img[0], top_img[1], bottom_img[0], bottom_img[1])
            line.setPen(pen)
            self.scene.addItem(line)
            self.grid_items.append(line)
        
        # Draw horizontal lines
        for j in range(self.grid_rows + 1):
            y_world = j * cell_height
            
            # Map left and right points
            left_world = np.array([[0.0, y_world]], dtype=np.float32).reshape(-1, 1, 2)
            right_world = np.array([[self.world_width_m, y_world]], dtype=np.float32).reshape(-1, 1, 2)
            
            left_img = cv2.perspectiveTransform(left_world, self.homography_matrix)[0][0]
            right_img = cv2.perspectiveTransform(right_world, self.homography_matrix)[0][0]
            
            line = QGraphicsLineItem(left_img[0], left_img[1], right_img[0], right_img[1])
            line.setPen(pen)
            self.scene.addItem(line)
            self.grid_items.append(line)
    
    def pixel_to_meter(self, x_px: float, y_px: float):
        """
        Convert pixel coordinates to world coordinates (meters).
        
        Args:
            x_px: X coordinate in pixels
            y_px: Y coordinate in pixels
            
        Returns:
            tuple: (x_m, y_m) in meters, or None if homography not available
        """
        if self.homography_matrix is None:
            return None
        
        try:
            # Transform image → world using inverse homography
            image_point = np.array([[x_px, y_px]], dtype=np.float32).reshape(-1, 1, 2)
            # Cache inverse homography to avoid repeated computation
            if not hasattr(self, '_homography_inv') or self._homography_inv is None:
                # Check if matrix is invertible
                det = np.linalg.det(self.homography_matrix)
                if abs(det) < 1e-6:
                    print(f"[FloorplanView] Warning: Homography matrix is near-singular (det={det})")
                    return None
                self._homography_inv = np.linalg.inv(self.homography_matrix)
            world_point = cv2.perspectiveTransform(image_point, self._homography_inv)[0][0]
            return (world_point[0], world_point[1])
        except np.linalg.LinAlgError as e:
            print(f"[FloorplanView] Error inverting homography matrix: {e}")
            self._homography_inv = None  # Clear cache
            return None
        except Exception as e:
            print(f"[FloorplanView] Error converting pixel to meter: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def meter_to_pixel(self, x_m: float, y_m: float):
        """
        Convert world coordinates (meters) to pixel coordinates.
        
        Args:
            x_m: X coordinate in meters
            y_m: Y coordinate in meters
            
        Returns:
            tuple: (x_px, y_px) in pixels, or None if homography not available
        """
        if self.homography_matrix is None:
            return None
        
        try:
            # Transform world → image
            world_point = np.array([[x_m, y_m]], dtype=np.float32).reshape(-1, 1, 2)
            image_point = cv2.perspectiveTransform(world_point, self.homography_matrix)[0][0]
            return (image_point[0], image_point[1])
        except Exception as e:
            print(f"[FloorplanView] Error converting meter to pixel: {e}")
            return None
    
    def map_pointer(self, x_m: float, y_m: float):
        """
        Map world coordinates to image and visualize pointer.
        
        Args:
            x_m: X coordinate in meters
            y_m: Y coordinate in meters
        """
        if self.homography_matrix is None:
            return
        
        # Store current position
        self.current_pointer_pos = (x_m, y_m)
        
        # Transform world → image
        pixel_coords = self.meter_to_pixel(x_m, y_m)
        if pixel_coords is None:
            return
        
        image_point = pixel_coords
        
        # Draw pointer
        if self.pointer_item is None:
            self.pointer_item = QGraphicsEllipseItem(0, 0, 16, 16)
            self.pointer_item.setBrush(QBrush(QColor(255, 0, 0, 200)))
            self.pointer_item.setPen(QPen(Qt.NoPen))
            self.scene.addItem(self.pointer_item)
        
        # Update position (center the circle)
        self.pointer_item.setPos(image_point[0] - 8, image_point[1] - 8)
        
        # Update zone colors based on new pointer position
        self._update_zone_colors_for_pointer()
        
        # Emit signal for status bar update (meters -> pixels)
        self.pixelToMeterMapped.emit(image_point[0], image_point[1], x_m, y_m)
    
    def place_zone(self, x_m: float, y_m: float, radius_m: float = None):
        """
        Place a zone at world coordinates.
        
        Args:
            x_m: X coordinate in meters
            y_m: Y coordinate in meters
            radius_m: Zone radius in meters (defaults to self.default_zone_radius_m)
            
        Returns:
            Zone object or None if max zones reached
        """
        # Check if we've reached the maximum number of zones
        if len(self.zones) >= self.max_zones:
            print(f"[FloorplanView] Maximum number of zones ({self.max_zones}) reached. Cannot place more zones.")
            return None
        
        if radius_m is None:
            radius_m = self.default_zone_radius_m
        zone = Zone(self.next_zone_id, x_m, y_m, radius_m)
        
        # Auto-assign playlist (1-5 based on zone number)
        playlist_number = len(self.zones) + 1  # 1-based playlist numbering
        self.zone_playlists[zone.id] = playlist_number
        zone.playlist = playlist_number  # Store playlist on zone object for easy access
        
        self.next_zone_id += 1
        self.zones.append(zone)
        
        # Visualize zone
        self._draw_zone(zone)
        
        print(f"[FloorplanView] Zone {zone.id} placed with playlist {playlist_number}")
        return zone
    
    def place_rectangular_zone(self, x1_m: float, y1_m: float, x2_m: float, y2_m: float, zone_id=None):
        """
        Place a rectangular zone spanning from (x1_m, y1_m) to (x2_m, y2_m).
        
        Args:
            x1_m: Top-left X coordinate in meters
            y1_m: Top-left Y coordinate in meters
            x2_m: Bottom-right X coordinate in meters
            y2_m: Bottom-right Y coordinate in meters
            zone_id: Optional zone ID (string or int). If None, uses next_zone_id.
            
        Returns:
            RectangularZone object
        """
        if zone_id is None:
            zone_id = self.next_zone_id
            self.next_zone_id += 1
        
        # Create rectangular zone
        rect_zone = RectangularZone(zone_id, x1_m, y1_m, x2_m, y2_m)
        self.zones.append(rect_zone)
        self._draw_rectangular_zone(rect_zone)
        return rect_zone
    
    def _calculate_zone_radius_px(self, x_m: float, y_m: float, radius_m: float) -> float:
        """
        Calculate zone radius in pixels based on homography transformation.
        
        Accounts for perspective distortion by sampling points around the circle
        and calculating the average radius in pixel space.
        
        Args:
            x_m: Zone center X in meters
            y_m: Zone center Y in meters
            radius_m: Zone radius in meters
            
        Returns:
            Radius in pixels, or None if homography not available
        """
        if self.homography_matrix is None:
            return None
        
        try:
            # Transform zone center to pixel coordinates
            center_world = np.array([[x_m, y_m]], dtype=np.float32).reshape(-1, 1, 2)
            center_px = cv2.perspectiveTransform(center_world, self.homography_matrix)[0][0]
            
            # Sample points around the circle in world space (4 points for faster computation)
            # This accounts for perspective distortion while being more efficient
            num_samples = 4  # Reduced from 8 to 4 for better performance
            radii_px = []
            
            for i in range(num_samples):
                angle = 2 * np.pi * i / num_samples
                # Point on circle circumference in world space
                sample_x = x_m + radius_m * np.cos(angle)
                sample_y = y_m + radius_m * np.sin(angle)
                
                # Transform to pixel coordinates
                sample_world = np.array([[sample_x, sample_y]], dtype=np.float32).reshape(-1, 1, 2)
                sample_px = cv2.perspectiveTransform(sample_world, self.homography_matrix)[0][0]
                
                # Calculate distance from center to sample point in pixel space
                dist_px = np.sqrt((sample_px[0] - center_px[0])**2 + (sample_px[1] - center_px[1])**2)
                radii_px.append(dist_px)
            
            # Use average radius (more stable than min/max for perspective correction)
            if radii_px:
                avg_radius_px = np.mean(radii_px)
                return float(avg_radius_px)
            else:
                return None
            
        except Exception as e:
            print(f"[FloorplanView] Error calculating zone radius: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _draw_zone(self, zone: Zone):
        """Draw zone on floorplan with perspective-correct radius scaling."""
        if self.homography_matrix is None:
            return
        
        # Transform zone center to image coordinates
        center_px = self.meter_to_pixel(zone.x, zone.y)
        if center_px is None:
            return
        
        # Calculate radius in pixels using homography (accounts for perspective)
        radius_px = self._calculate_zone_radius_px(zone.x, zone.y, zone.radius)
        if radius_px is None or radius_px <= 0:
            # Fallback to simple approximation if calculation fails
            # Estimate scale from world dimensions to image size
            if self.image_item:
                img_width = self.image_item.pixmap().width()
                img_height = self.image_item.pixmap().height()
                # Rough estimate: assume image covers world area
                scale_x = img_width / self.world_width_m
                scale_y = img_height / self.world_height_m
                scale = (scale_x + scale_y) / 2.0
                radius_px = zone.radius * scale
            else:
                radius_px = zone.radius * 50  # Last resort fallback
        
        # Create circle
        zone.graphics_item = QGraphicsEllipseItem(
            center_px[0] - radius_px,
            center_px[1] - radius_px,
            radius_px * 2,
            radius_px * 2
        )
        
        # Set color based on zone state and pointer position
        # Green tint only when pointer is in zone area, otherwise light translucent box
        pointer_in_zone = False
        if self.current_pointer_pos is not None:
            x_m, y_m = self.current_pointer_pos
            pointer_in_zone = zone.contains(x_m, y_m)
        
        if zone.is_active:
            # Green tint when registered (translucent)
            zone.graphics_item.setPen(QPen(QColor(0, 200, 0, 200), 3))
            zone.graphics_item.setBrush(QBrush(QColor(0, 200, 0, 80)))  # Translucent green
        elif pointer_in_zone:
            # Green tint when pointer is in zone (but not yet registered)
            zone.graphics_item.setPen(QPen(QColor(100, 200, 100, 150), 2))  # Light green border
            zone.graphics_item.setBrush(QBrush(QColor(150, 220, 150, 60)))  # Translucent light green
        else:
            # Light translucent/transparent box when pointer is not in zone
            zone.graphics_item.setPen(QPen(QColor(200, 200, 200, 80), 2))  # Light gray border
            zone.graphics_item.setBrush(QBrush(QColor(240, 240, 240, 30)))  # Very translucent white/gray
        
        self.scene.addItem(zone.graphics_item)
        
        # Add playlist label in the center of the zone
        if hasattr(zone, 'playlist'):
            playlist_text = QGraphicsTextItem(f"P{zone.playlist}")
            playlist_text.setDefaultTextColor(QColor(0, 0, 0))
            font = QFont("Arial", 12, QFont.Bold)
            playlist_text.setFont(font)
            text_rect = playlist_text.boundingRect()
            # Center the text in the zone
            playlist_text.setPos(center_px[0] - text_rect.width()/2, center_px[1] - text_rect.height()/2)
            self.scene.addItem(playlist_text)
            # Store text item for cleanup
            zone.text_item = playlist_text
    
    def _draw_rectangular_zone(self, zone: RectangularZone):
        """Draw rectangular zone on floorplan with perspective-correct scaling."""
        if self.homography_matrix is None:
            return
        
        # Transform rectangle corners to pixel coordinates
        corners_world = np.array([
            [zone.x1, zone.y1],  # Top-left
            [zone.x2, zone.y1],  # Top-right
            [zone.x2, zone.y2],  # Bottom-right
            [zone.x1, zone.y2]   # Bottom-left
        ], dtype=np.float32).reshape(-1, 1, 2)
        
        try:
            corners_px = cv2.perspectiveTransform(corners_world, self.homography_matrix)
            
            # Find bounding box in pixel space
            x_coords = [pt[0][0] for pt in corners_px]
            y_coords = [pt[0][1] for pt in corners_px]
            min_x = min(x_coords)
            max_x = max(x_coords)
            min_y = min(y_coords)
            max_y = max(y_coords)
            
            # Create rectangle
            zone.graphics_item = QGraphicsRectItem(min_x, min_y, max_x - min_x, max_y - min_y)
            
            # Set color based on zone state and pointer position
            # For rectangular zones (Adaptive Audio): green tint only when pointer is in zone
            pointer_in_zone = False
            if self.current_pointer_pos is not None:
                x_m, y_m = self.current_pointer_pos
                pointer_in_zone = zone.contains(x_m, y_m)
            
            if zone.is_active:
                # Brighter green when registered (translucent)
                zone.graphics_item.setPen(QPen(QColor(0, 200, 0, 200), 3))
                zone.graphics_item.setBrush(QBrush(QColor(0, 200, 0, 80)))  # Translucent green
            elif pointer_in_zone:
                # Green tint when pointer is in zone (but not yet registered)
                zone.graphics_item.setPen(QPen(QColor(100, 200, 100, 150), 2))  # Light green border
                zone.graphics_item.setBrush(QBrush(QColor(150, 220, 150, 60)))  # Translucent light green
            else:
                # Light translucent/transparent box when pointer is not in zone
                zone.graphics_item.setPen(QPen(QColor(200, 200, 200, 80), 2))  # Light gray border
                zone.graphics_item.setBrush(QBrush(QColor(240, 240, 240, 30)))  # Very translucent white/gray
            
            self.scene.addItem(zone.graphics_item)
        except Exception as e:
            print(f"[FloorplanView] Error drawing rectangular zone: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_zone_colors_for_pointer(self):
        """Update zone colors based on current pointer position."""
        if self.current_pointer_pos is None:
            return
        
        x_m, y_m = self.current_pointer_pos
        
        # Update all zones that are not active (active zones keep their green color)
        for zone in self.zones:
            if zone.is_active:
                continue  # Skip active zones, they keep their registered green color
            
            # Check if pointer is in zone
            pointer_in_zone = zone.contains(x_m, y_m)
            
            # Only update if graphics item exists
            if zone.graphics_item is None:
                continue
            
            # Determine new colors based on pointer position
            if pointer_in_zone:
                # Green tint when pointer is in zone
                new_pen = QPen(QColor(100, 200, 100, 150), 2)
                new_brush = QBrush(QColor(150, 220, 150, 60))
            else:
                # Light translucent box when pointer is not in zone
                new_pen = QPen(QColor(200, 200, 200, 80), 2)
                new_brush = QBrush(QColor(240, 240, 240, 30))
            
            # Update colors
            zone.graphics_item.setPen(new_pen)
            zone.graphics_item.setBrush(new_brush)
    
    def set_speaker_volumes(self, volumes: dict):
        """
        Update speaker volumes for visualization.
        
        Args:
            volumes: Dict mapping speaker_id (0-3) to volume (0-100)
        """
        self.speaker_volumes = volumes.copy()
        if self.show_speakers:
            self._update_speaker_visualization()
    
    def set_speaker_positions(self, positions: dict):
        """
        Set speaker positions in world coordinates (meters).
        Speakers are located at anchor positions (corners).
        
        Args:
            positions: Dict mapping speaker_id (0-3) to position [x_m, y_m, z_m]
        """
        self.speaker_positions = {}
        for speaker_id, pos in positions.items():
            # Store only x, y (ignore z)
            self.speaker_positions[speaker_id] = (float(pos[0]), float(pos[1]))
        if self.show_speakers:
            self._update_speaker_visualization()
    
    def set_show_speakers(self, show: bool):
        """Enable/disable speaker visualization."""
        self.show_speakers = show
        if not show:
            # Remove all speaker items
            for speaker_id, items in list(self.speaker_items.items()):
                for item in items.values():
                    if item:
                        self.scene.removeItem(item)
            self.speaker_items = {}
        else:
            # Redraw speakers
            self._update_speaker_visualization()
    
    def _update_speaker_visualization(self):
        """Update speaker icons, volume bars, and volume numbers on floorplan."""
        if self.homography_matrix is None:
            return
        
        # Remove old speaker items
        for speaker_id, items in list(self.speaker_items.items()):
            for item in items.values():
                if item:
                    self.scene.removeItem(item)
        self.speaker_items = {}
        
        # Draw speakers at corner positions
        for speaker_id in range(4):  # Speakers 0-3
            if speaker_id not in self.speaker_positions:
                continue
            
            x_m, y_m = self.speaker_positions[speaker_id]
            volume = self.speaker_volumes.get(speaker_id, 0)
            
            # Convert to pixel coordinates
            pixel_pos = self.meter_to_pixel(x_m, y_m)
            if pixel_pos is None:
                continue
            
            px, py = pixel_pos
            
            # Create speaker icon (circle)
            icon_size = 24
            icon = QGraphicsEllipseItem(px - icon_size/2, py - icon_size/2, icon_size, icon_size)
            icon.setPen(QPen(QColor(0, 0, 0), 2))
            icon.setBrush(QBrush(QColor(100, 150, 200, 200)))  # Light blue
            self.scene.addItem(icon)
            
            # Create volume bar (vertical bar next to icon)
            bar_width = 8
            bar_height = 60
            bar_x = px + icon_size/2 + 5
            bar_y = py - bar_height/2
            
            # Background bar (gray)
            bar_bg = QGraphicsRectItem(bar_x, bar_y, bar_width, bar_height)
            bar_bg.setPen(QPen(QColor(200, 200, 200), 1))
            bar_bg.setBrush(QBrush(QColor(240, 240, 240)))
            self.scene.addItem(bar_bg)
            
            # Volume fill (green, height based on volume)
            fill_height = (volume / 100.0) * bar_height
            fill_y = bar_y + (bar_height - fill_height)
            bar_fill = QGraphicsRectItem(bar_x, fill_y, bar_width, fill_height)
            bar_fill.setPen(QPen(Qt.NoPen))
            bar_fill.setBrush(QBrush(QColor(0, 200, 0, 200)))  # Green
            self.scene.addItem(bar_fill)
            
            # Volume text (percentage)
            volume_text = QGraphicsTextItem(f"{volume}%")
            volume_text.setDefaultTextColor(QColor(0, 0, 0))
            font = QFont("Arial", 9)
            volume_text.setFont(font)
            text_rect = volume_text.boundingRect()
            volume_text.setPos(bar_x + bar_width + 3, py - text_rect.height()/2)
            self.scene.addItem(volume_text)
            
            # Store items for cleanup
            self.speaker_items[speaker_id] = {
                'icon': icon,
                'bar_bg': bar_bg,
                'bar_fill': bar_fill,
                'text': volume_text
            }
    
    def update_zone_radius(self, zone: Zone, new_radius_m: float):
        """
        Update zone radius and redraw with correct scaling.
        
        Args:
            zone: Zone object to update
            new_radius_m: New radius in meters
        """
        zone.radius = new_radius_m
        # Redraw zone with new radius
        if zone.graphics_item:
            self.scene.removeItem(zone.graphics_item)
            zone.graphics_item = None
        self._draw_zone(zone)
    
    def redraw_all_zones(self):
        """Redraw all zones (useful after homography changes or radius updates)."""
        for zone in self.zones:
            if zone.graphics_item:
                self.scene.removeItem(zone.graphics_item)
                zone.graphics_item = None
            # Draw based on zone type
            if isinstance(zone, RectangularZone):
                self._draw_rectangular_zone(zone)
            else:
                self._draw_zone(zone)

    def clear_zones(self):
        """Remove all zones."""
        for zone in self.zones:
            if zone.graphics_item:
                self.scene.removeItem(zone.graphics_item)
            if hasattr(zone, 'text_item') and zone.text_item:
                self.scene.removeItem(zone.text_item)
        self.zones = []
        self.zone_playlists = {}
        self.next_zone_id = 1
        self.current_zone = None
    
    def _check_zone_registration(self):
        """Check zone hover/leave timers."""
        if self.current_pointer_pos is None:
            return
        
        x_m, y_m = self.current_pointer_pos
        
        # Find zone containing pointer (skip zones that have auto-registration disabled)
        zone_found = None
        for zone in self.zones:
            # Skip zones that have auto-registration disabled (e.g., Adaptive Audio zones)
            if hasattr(zone, '_skip_auto_registration') and zone._skip_auto_registration:
                continue
            if zone.contains(x_m, y_m):
                zone_found = zone
                break
        
        # Zone registration logic
        if zone_found and not zone_found.is_active:
            # Entering zone - start timer if not already started
            if self.zone_hover_start is None:
                self.zone_hover_start = QTimer()
                self.zone_hover_start.setSingleShot(True)
                # Use a closure to capture the zone
                def register_zone():
                    self._register_zone(zone_found)
                self.zone_hover_start.timeout.connect(register_zone)
                self.zone_hover_start.start(self.t_register_ms)
            # Cancel leave timer if we're back in a zone
            if self.zone_leave_start is not None:
                self.zone_leave_start.stop()
                self.zone_leave_start = None
        elif zone_found and zone_found.is_active:
            # Still in zone - cancel any leave timer
            if self.zone_leave_start is not None:
                self.zone_leave_start.stop()
                self.zone_leave_start = None
        elif self.current_zone and self.current_zone.is_active:
            # Leaving zone - start leave timer if not already started
            if self.zone_leave_start is None:
                self.zone_leave_start = QTimer()
                self.zone_leave_start.setSingleShot(True)
                # Use a closure to capture the current zone
                current_zone_ref = self.current_zone
                def deregister_zone():
                    if current_zone_ref:
                        self._deregister_zone(current_zone_ref)
                self.zone_leave_start.timeout.connect(deregister_zone)
                self.zone_leave_start.start(self.t_deregister_ms)
            # Cancel hover timer since we're leaving
            if self.zone_hover_start is not None:
                self.zone_hover_start.stop()
                self.zone_hover_start = None
        else:
            # Not in any zone - cancel all timers
            if self.zone_hover_start is not None:
                self.zone_hover_start.stop()
                self.zone_hover_start = None
            if self.zone_leave_start is not None:
                self.zone_leave_start.stop()
                self.zone_leave_start = None
    
    def _register_zone(self, zone):
        """Register zone (user entered and stayed)."""
        zone.is_active = True
        self.current_zone = zone
        
        # Update visualization (redraw to update colors and ensure correct size)
        if zone.graphics_item:
            self.scene.removeItem(zone.graphics_item)
            zone.graphics_item = None
        # Draw based on zone type
        if isinstance(zone, RectangularZone):
            self._draw_rectangular_zone(zone)
        else:
            self._draw_zone(zone)
        
        self.zoneRegistered.emit(zone)
    
    def _deregister_zone(self, zone):
        """Deregister zone (user left)."""
        zone.is_active = False
        
        # Update visualization (redraw to update colors and ensure correct size)
        if zone.graphics_item:
            self.scene.removeItem(zone.graphics_item)
            zone.graphics_item = None
        # Draw based on zone type
        if isinstance(zone, RectangularZone):
            self._draw_rectangular_zone(zone)
        else:
            self._draw_zone(zone)
        
        self.zoneDeregistered.emit(zone)
        self.current_zone = None
    
    def _find_zone_at_position(self, x_m: float, y_m: float):
        """Find zone at given world coordinates."""
        for zone in self.zones:
            if isinstance(zone, RectangularZone):
                continue  # Skip rectangular zones for dragging
            if zone.contains(x_m, y_m):
                return zone
        return None
    
    def _move_zone(self, zone: Zone, new_x_m: float, new_y_m: float):
        """Move zone to new position and redraw."""
        zone.x = new_x_m
        zone.y = new_y_m
        
        # Remove old graphics items
        if zone.graphics_item:
            self.scene.removeItem(zone.graphics_item)
            zone.graphics_item = None
        if hasattr(zone, 'text_item') and zone.text_item:
            self.scene.removeItem(zone.text_item)
            zone.text_item = None
        
        # Redraw zone at new position
        self._draw_zone(zone)

    def mousePressEvent(self, event):
        """Handle mouse clicks for corner marking, zone placement, and zone dragging."""
        if event.button() == Qt.LeftButton:
            # Map view coordinates to scene coordinates
            scene_pos = self.mapToScene(event.pos())
            x_px = scene_pos.x()
            y_px = scene_pos.y()
            
            if self.marking_corners and len(self.corners) < 4:
                # Mark corner
                self.corners.append((x_px, y_px))
                print(f"[FloorplanView] Corner {len(self.corners)} marked at ({x_px:.1f}, {y_px:.1f})")
                
                # Draw marker
                marker = QGraphicsEllipseItem(x_px - 5, y_px - 5, 10, 10)
                marker.setBrush(QBrush(QColor(255, 0, 0)))
                self.scene.addItem(marker)
                
                if len(self.corners) == 4:
                    self.marking_corners = False
                    self._compute_homography()
                    print("[FloorplanView] All corners marked, homography computed")
            
            elif self.placing_zones and self.homography_matrix is not None:
                # Place zone - convert image coordinates back to world
                try:
                    meter_coords = self.pixel_to_meter(x_px, y_px)
                    if meter_coords:
                        zone = self.place_zone(meter_coords[0], meter_coords[1])
                        if zone:  # Only if zone was successfully placed (not at max limit)
                            print(f"[FloorplanView] Zone {zone.id} placed at ({meter_coords[0]:.2f}m, {meter_coords[1]:.2f}m)")
                            # Emit pixel-to-meter mapping for status bar (reuse already calculated coords)
                            self.pixelToMeterMapped.emit(x_px, y_px, meter_coords[0], meter_coords[1])
                    else:
                        print(f"[FloorplanView] Warning: Could not convert pixel to meter coordinates")
                except Exception as e:
                    print(f"[FloorplanView] Error placing zone: {e}")
                    import traceback
                    traceback.print_exc()
            
            elif self.homography_matrix is not None and not self.marking_corners:
                # Check if clicking on a zone for dragging
                meter_coords = self.pixel_to_meter(x_px, y_px)
                if meter_coords:
                    zone = self._find_zone_at_position(meter_coords[0], meter_coords[1])
                    if zone:
                        # Start dragging this zone
                        self.dragging_zone = zone
                        self.drag_start_pos = meter_coords
                        self.setDragMode(QGraphicsView.NoDrag)  # Disable view dragging while dragging zone
                        print(f"[FloorplanView] Started dragging zone {zone.id}")
                        return  # Don't emit pixel-to-meter mapping when starting drag
                    else:
                        # Emit pixel-to-meter mapping for status bar display
                        self.pixelToMeterMapped.emit(x_px, y_px, meter_coords[0], meter_coords[1])
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for zone dragging."""
        if self.dragging_zone and self.homography_matrix is not None:
            # Map view coordinates to scene coordinates
            scene_pos = self.mapToScene(event.pos())
            x_px = scene_pos.x()
            y_px = scene_pos.y()
            
            # Convert to world coordinates
            meter_coords = self.pixel_to_meter(x_px, y_px)
            if meter_coords:
                # Move the zone to new position
                self._move_zone(self.dragging_zone, meter_coords[0], meter_coords[1])
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events to end zone dragging."""
        if event.button() == Qt.LeftButton and self.dragging_zone:
            # End dragging
            print(f"[FloorplanView] Finished dragging zone {self.dragging_zone.id} to ({self.dragging_zone.x:.2f}m, {self.dragging_zone.y:.2f}m)")
            self.dragging_zone = None
            self.drag_start_pos = None
            self.setDragMode(QGraphicsView.ScrollHandDrag)  # Re-enable view dragging
        
        super().mouseReleaseEvent(event)
