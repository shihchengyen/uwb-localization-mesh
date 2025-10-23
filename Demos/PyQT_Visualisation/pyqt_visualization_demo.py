"""
image_grid_zones_enhanced.py

Extends homography + auto-transform example with:
 - Mark Zone(s) and Clear Zone(s)
 - Visible draggable handle for each zone
 - Tooltip-like small text showing world coords while dragging / hovering
 - Fade in/out registration animation (VaraintAnimation driving opacity)
 - Console debug prints for zone create/move/register/deregister
"""

import sys
import math
import numpy as np
import cv2
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QTimer, QObject, QVariantAnimation
)
from PyQt5.QtGui import (
    QPixmap, QPainter, QPen, QColor, QFont, QImage, QPainterPath
)
from PyQt5.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsItem, QGraphicsEllipseItem, QGraphicsSimpleTextItem,
    QFileDialog, QMainWindow, QAction, QLabel, QVBoxLayout,
    QWidget, QPushButton, QHBoxLayout, QGraphicsRectItem
)

# ----- Physical area and grid spec -----
AREA_WIDTH_M = 6.00    # meters (600 cm) -> LONG side (10 cells)
AREA_HEIGHT_M = 4.80   # meters (480 cm) -> SHORT side (8 cells)
GRID_COLS = 10
GRID_ROWS = 8
CELL_SIZE_M = AREA_WIDTH_M / GRID_COLS  # expected 0.55 m

# ----- Zone default -----
ZONE_RADIUS_M = 0.25  # default radius in meters for each zone (adjustable)

# ----- Utility: apply homography to Nx2 points using numpy -----
def apply_homography(H, pts):
    pts = np.asarray(pts, dtype=np.float64)
    if pts.ndim == 1:
        pts = pts.reshape(1, 2)
    n = pts.shape[0]
    homo = np.ones((n, 3), dtype=np.float64)
    homo[:, 0:2] = pts
    res = homo @ H.T
    # safe division
    res[:, 0] = res[:, 0] / np.where(res[:, 2] == 0, 1e-9, res[:, 2])
    res[:, 1] = res[:, 1] / np.where(res[:, 2] == 0, 1e-9, res[:, 2])
    return res[:, :2]

# ----- order points utility (returns TL, TR, BR, BL) -----
def order_quad_points(pts):
    pts = np.array(pts, dtype=np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).flatten()
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float64)

# ----- ProjectedGridItem (uses QPainterPath for polylines) -----
class ProjectedGridItem(QGraphicsItem):
    def __init__(self, scene_rect: QRectF, H_world_to_img=None):
        super().__init__()
        self.scene_rect = scene_rect
        self.H = H_world_to_img  # 3x3 numpy matrix mapping world meters -> image pixels
        self.setZValue(3)

    def boundingRect(self):
        return self.scene_rect

    def paint(self, painter: QPainter, option, widget=None):
        if self.H is None:
            return

        pen = QPen(QColor(200, 10, 10, 200))
        pen.setWidthF(1.0)
        painter.setPen(pen)

        # compute world grid lines (in meters)
        vert_lines = []
        for c in range(GRID_COLS + 1):
            x_m = c * CELL_SIZE_M
            ys = np.linspace(0, AREA_HEIGHT_M, 200)
            pts_world = np.column_stack((np.full_like(ys, x_m), ys))
            proj = apply_homography(self.H, pts_world)
            vert_lines.append(proj)

        hor_lines = []
        for r in range(GRID_ROWS + 1):
            y_m = r * CELL_SIZE_M
            xs = np.linspace(0, AREA_WIDTH_M, 200)
            pts_world = np.column_stack((xs, np.full_like(xs, y_m)))
            proj = apply_homography(self.H, pts_world)
            hor_lines.append(proj)

        # Draw vertical lines as QPainterPath polylines
        for pl in vert_lines:
            path = QPainterPath()
            started = False
            for (x, y) in pl:
                if math.isfinite(x) and math.isfinite(y):
                    if not started:
                        path.moveTo(x, y)
                        started = True
                    else:
                        path.lineTo(x, y)
                else:
                    if started:
                        painter.drawPath(path)
                        path = QPainterPath()
                        started = False
            if started:
                painter.drawPath(path)

        # Draw horizontal lines as QPainterPath polylines
        for pl in hor_lines:
            path = QPainterPath()
            started = False
            for (x, y) in pl:
                if math.isfinite(x) and math.isfinite(y):
                    if not started:
                        path.moveTo(x, y)
                        started = True
                    else:
                        path.lineTo(x, y)
                else:
                    if started:
                        painter.drawPath(path)
                        path = QPainterPath()
                        started = False
            if started:
                painter.drawPath(path)

# ----- Zone hitbox item (captures hover events and is draggable) -----
class ZoneHitboxItem(QGraphicsEllipseItem):
    def __init__(self, center_x, center_y, hit_r_px, zone):
        # create an ellipse centered at (0,0) and then position the item at center_x,center_y
        rect = QRectF(-hit_r_px, -hit_r_px, hit_r_px * 2, hit_r_px * 2)
        super().__init__(rect)

        self.zone = zone
        self.setAcceptHoverEvents(True)

        # use QPen/QBrush objects (avoid passing enums directly to setPen/setBrush)
        pen = QPen()
        pen.setStyle(Qt.NoPen)
        self.setPen(pen)

        brush = QColor(0, 0, 0, 0)  # fully transparent
        self.setBrush(brush)

        self.setZValue(50)

        # make the hitbox movable and notify on geometry changes
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

        # position the item so its local center is at the requested center coordinates
        self.setPos(center_x, center_y)

        # show a hand cursor to indicate draggable
        self.setCursor(Qt.OpenHandCursor)

    def hoverEnterEvent(self, event):
        try:
            self.zone._on_hover_enter()
        except Exception:
            pass
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        try:
            self.zone._on_hover_leave()
        except Exception:
            pass
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        # change cursor style while dragging
        self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        """
        Catch ItemPositionHasChanged so we can update the zone's stored center
        and any external UI. `value` is a QPointF with the new item position.
        """
        if change == QGraphicsItem.ItemPositionHasChanged:
            try:
                pos = value
                self.zone._on_moved(pos.x(), pos.y())
            except Exception:
                pass
        return super().itemChange(change, value)

# ----- Zone container (visual + hitbox + handle + tooltip + state + timers + animations) -----
class Zone(QObject):
    def __init__(self, view, center_x_px, center_y_px, radius_m, idx):
        super().__init__()
        self.view = view
        self.center = (center_x_px, center_y_px)
        self.radius_m = radius_m
        self.idx = idx

        # compute pixel radius using homography if available
        r_px = self._radius_m_to_px(radius_m)
        if r_px < 3:
            r_px = 3.0
        self.radius_px = float(r_px)
        self.hit_radius_px = float(self.radius_px * 1.5)

        # create hitbox item (invisible) positioned at center
        self.hitbox_item = ZoneHitboxItem(center_x_px, center_y_px, self.hit_radius_px, self)

        # visual circle is a child of the hitbox (local coordinates centered on (0,0))
        self.visual_item = QGraphicsEllipseItem(-self.radius_px, -self.radius_px,
                                                2 * self.radius_px, 2 * self.radius_px,
                                                parent=self.hitbox_item)
        brush = QColor(200, 200, 200, 140)  # light gray semi-transparent
        self.visual_item.setBrush(brush)
        self.visual_item.setPen(QPen(QColor(80, 80, 80, 160)))
        self.visual_item.setZValue(60)  # above hitbox
        self.visual_item.setOpacity(0.6)

        # draggable visible handle (small circle) so user knows they can drag
        handle_r = max(4.0, self.radius_px * 0.15)
        # place handle centered at (0,0) in the hitbox local coords so it aligns with the circle centroid
        self.handle_item = QGraphicsEllipseItem(-handle_r, -handle_r, handle_r * 2, handle_r * 2, parent=self.hitbox_item)
        self.handle_item.setBrush(QColor(100, 100, 255, 200))
        self.handle_item.setPen(QPen(QColor(40, 40, 120, 200)))
        self.handle_item.setZValue(70)
        # cursor hint over handle
        self.handle_item.setCursor(Qt.OpenHandCursor)

        # small index label (also child so it moves with hitbox)
        self.label = QGraphicsSimpleTextItem(str(idx), parent=self.hitbox_item)
        self.label.setPos(self.radius_px + 4, -6)
        self.label.setZValue(61)

        # floating tooltip text that shows world coords while dragging or hovering
        self.tooltip = QGraphicsSimpleTextItem("", parent=self.hitbox_item)
        # make tooltip text larger & readable
        font = QFont()
        font.setPointSize(20)          # <- change this to taste (e.g. 10, 12, 14)
        self.tooltip.setZValue(80)
        # position slightly above the zone
        self._update_tooltip_pos()
        self.tooltip.setVisible(False)

        # registration state
        self.registered = False

        # timers (cancellable)
        self._reg_timer = QTimer()
        self._reg_timer.setSingleShot(True)
        self._reg_timer.timeout.connect(self._do_register)

        self._dereg_timer = QTimer()
        self._dereg_timer.setSingleShot(True)
        self._dereg_timer.timeout.connect(self._do_deregister)

        # animations using QVariantAnimation (since QGraphicsItem is not a QObject property-target)
        self._anim = QVariantAnimation()
        self._anim.valueChanged.connect(self._on_anim_value)
        self._anim.setDuration(360)  # ms

        # debug print
        print(f"[Zone CREATED] #{self.idx} px=({self.center[0]:.1f},{self.center[1]:.1f}) r_m={self.radius_m} r_px={self.radius_px:.1f}")

    def add_to_scene(self, scene):
        scene.addItem(self.hitbox_item)

    def remove_from_scene(self, scene):
        try:
            scene.removeItem(self.hitbox_item)
        except Exception:
            pass

    def _radius_m_to_px(self, m):
        # try homography mapping: map (0,0) and (m,0) then compute distance
        if self.view.H_world_to_img is not None:
            p0 = apply_homography(self.view.H_world_to_img, [[0.0, 0.0]])[0]
            p1 = apply_homography(self.view.H_world_to_img, [[m, 0.0]])[0]
            return math.hypot(float(p1[0]) - float(p0[0]), float(p1[1]) - float(p0[1]))
        else:
            # fallback px_per_m
            if self.view.img_w and AREA_WIDTH_M > 0:
                px_per_m = float(self.view.img_w) / float(AREA_WIDTH_M)
                return m * px_per_m
            else:
                return m * 100.0  # fallback heuristic

    def _on_hover_enter(self):
        # entering the hitbox
        if self._dereg_timer.isActive():
            self._dereg_timer.stop()
        # show tooltip with coords immediately
        self._show_tooltip(True)
        # if already registered do nothing
        if self.registered:
            return
        # otherwise start registration countdown (3s)
        if not self._reg_timer.isActive():
            self._reg_timer.start(3000)

    def _on_hover_leave(self):
        # leaving the hitbox
        # hide tooltip after a short delay
        QTimer.singleShot(250, lambda: self._show_tooltip(False))
        # if registration countdown is active, cancel it
        if self._reg_timer.isActive():
            self._reg_timer.stop()
            return
        # if registered, schedule deregister after 1s
        if self.registered and not self._dereg_timer.isActive():
            self._dereg_timer.start(1000)

    def _do_register(self):
        # animate to registered (green + higher opacity)
        self.registered = True
        self._start_fade(to_opacity=1.0)
        self.visual_item.setBrush(QColor(120, 220, 120, 200))
        px = self.center
        world = self._pixel_to_world(px[0], px[1])
        print(f"[Zone REGISTERED] #{self.idx} px=({px[0]:.1f},{px[1]:.1f}) world=({world[0]:.3f}m,{world[1]:.3f}m)")
        if hasattr(self.view, "zone_registered"):
            self.view.zone_registered(self)

    def _do_deregister(self):
        self.registered = False
        self._start_fade(to_opacity=0.6)
        self.visual_item.setBrush(QColor(200, 200, 200, 140))
        px = self.center
        world = self._pixel_to_world(px[0], px[1])
        print(f"[Zone DEREGISTERED] #{self.idx} px=({px[0]:.1f},{px[1]:.1f}) world=({world[0]:.3f}m,{world[1]:.3f}m)")
        if hasattr(self.view, "zone_deregistered"):
            self.view.zone_deregistered(self)

    def _start_fade(self, to_opacity=1.0):
        # start an animation from current opacity to to_opacity
        try:
            cur = self.visual_item.opacity()
        except Exception:
            cur = 1.0
        self._anim.stop()
        self._anim.setStartValue(cur)
        self._anim.setEndValue(to_opacity)
        self._anim.start()

    def _on_anim_value(self, v):
        # QVariantAnimation.value gives floats
        self.visual_item.setOpacity(float(v))

    def _on_moved(self, new_x_px, new_y_px):
        """
        Called when the hitbox item position changes (user dragged it).
        Update stored center and optionally notify the view.
        """
        self.center = (float(new_x_px), float(new_y_px))
        # update label pos if radius changed or for aesthetics
        self.label.setPos(self.radius_px + 4, -6)
        # reposition tooltip
        self._update_tooltip_pos()
        # debug print pixel + world coords
        world = self._pixel_to_world(self.center[0], self.center[1])
        print(f"[Zone MOVED] #{self.idx} px=({self.center[0]:.1f},{self.center[1]:.1f}) world=({world[0]:.3f}m,{world[1]:.3f}m)")
        if hasattr(self.view, "zone_moved"):
            self.view.zone_moved(self)

    def _pixel_to_world(self, x_px, y_px):
        # uses H_img_to_world if available; otherwise estimate via px_per_m with origin at (0,0)
        if self.view.H_img_to_world is not None:
            res = apply_homography(self.view.H_img_to_world, [[x_px, y_px]])[0]
            return (float(res[0]), float(res[1]))
        else:
            if self.view.img_w and AREA_WIDTH_M > 0:
                px_per_m = float(self.view.img_w) / float(AREA_WIDTH_M)
                return (x_px / px_per_m, y_px / px_per_m)
            else:
                return (0.0, 0.0)

    def _show_tooltip(self, show: bool):
        if show:
            world = self._pixel_to_world(self.center[0], self.center[1])
            self.tooltip.setText(f"{world[0]:.3f} m, {world[1]:.3f} m")
            self.tooltip.setVisible(True)
        else:
            self.tooltip.setVisible(False)

    def _update_tooltip_pos(self):
        # place tooltip above the circle: local coords (centered origin)
        px = -self.tooltip.boundingRect().width() / 2
        py = -self.radius_px - 18
        self.tooltip.setPos(px, py)

# ----- The main view that supports marking corners, mapping, auto-detect, and zones -----
class ImageGridView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.pix_item = None
        self.img_w = 0
        self.img_h = 0
        self.current_image_path = None

        # homography mapping world meters -> image pixels
        self.H_world_to_img = None
        self.H_img_to_world = None

        # corner marking state
        self.marking = False
        self.marked_pts = []  # image pixel points (list of tuples (x_px,y_px))

        # overlay items
        self.grid_overlay = None
        self.corner_markers = []

        # zones
        self.zones = []
        self.placing_zones = False
        self.next_zone_idx = 1

        # UI feedback
        self.coord_label = None

        # zoom state
        self._zoom = 0

    def load_image(self, filename):
        pix = QPixmap(filename)
        if pix.isNull():
            return False
        self.scene.clear()
        self.pix_item = QGraphicsPixmapItem(pix)
        self.pix_item.setZValue(0)
        self.pix_item.setPos(0, 0)
        self.scene.addItem(self.pix_item)

        self.img_w = pix.width()
        self.img_h = pix.height()
        self.current_image_path = filename
        self.scene.setSceneRect(0, 0, self.img_w, self.img_h)

        # clear homography & overlays & zones
        self.H_world_to_img = None
        self.H_img_to_world = None
        self.marked_pts = []
        self._remove_corner_markers()
        if self.grid_overlay:
            self.scene.removeItem(self.grid_overlay)
            self.grid_overlay = None
        self.clear_zones()

        self.fitInView(self.pix_item.boundingRect(), Qt.KeepAspectRatio)
        self._zoom = 0
        return True

    def start_marking_corners(self):
        if not self.pix_item:
            return
        self.marking = True
        self.marked_pts = []
        self._remove_corner_markers()
        self._show_hint("Click 4 image points: TL, TR, BR, BL (in order)")

    def _remove_corner_markers(self):
        for m in self.corner_markers:
            try:
                self.scene.removeItem(m)
            except Exception:
                pass
        self.corner_markers = []

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            scene_pt = self.mapToScene(event.pos())
            x = scene_pt.x()
            y = scene_pt.y()

            # out-of-image check
            if not (0 <= x < self.img_w and 0 <= y < self.img_h):
                super().mousePressEvent(event)
                return

            if self.placing_zones:
                # place a zone at this location
                z = Zone(self, float(x), float(y), ZONE_RADIUS_M, self.next_zone_idx)
                z.add_to_scene(self.scene)
                self.zones.append(z)
                self.next_zone_idx += 1
                # print to console
                world = z._pixel_to_world(x, y)
                print(f"[Zone PLACED] #{z.idx} px=({x:.1f},{y:.1f}) world=({world[0]:.3f}m,{world[1]:.3f}m)")
                self._show_hint(f"Placed zone #{z.idx} at ({x:.1f}, {y:.1f})")
                return  # consume event (don't do corner marking while placing zones)
            if self.marking:
                # add corner
                self.marked_pts.append((x, y))
                self._add_corner_marker(x, y, len(self.marked_pts))
                if len(self.marked_pts) == 4:
                    self.marking = False
                    self._compute_homography_from_marked()
                else:
                    self._show_hint(f"Marked corner {len(self.marked_pts)} / 4")
            else:
                # normal click: if transform exists, map to world and compute grid cell
                if self.H_img_to_world is not None:
                    px_pt = np.array([[x, y]], dtype=np.float64)
                    world_pt = apply_homography(self.H_img_to_world, px_pt)[0]  # x_m, y_m
                    x_m, y_m = world_pt[0], world_pt[1]

                    # clamp to world rectangle
                    if x_m < 0 or y_m < 0 or x_m > AREA_WIDTH_M or y_m > AREA_HEIGHT_M:
                        self._show_hint("Clicked outside world rectangle")
                    else:
                        col = int(x_m // CELL_SIZE_M)
                        row = int(y_m // CELL_SIZE_M)
                        msg = (f"Pixel: ({x:.1f}, {y:.1f})  → World: ({x_m:.3f} m, {y_m:.3f} m)  "
                               f"Cell: ({col}, {row})")
                        print(msg)
                        self._show_hint(msg)
                else:
                    self._show_hint("No corner mapping set. Click 'Mark Corners' or 'Auto Transform' first.")
        else:
            super().mousePressEvent(event)

    def _add_corner_marker(self, x, y, idx):
        r = 6
        ell = QGraphicsEllipseItem(x - r, y - r, r * 2, r * 2)
        color = QColor(20, 160, 20) if idx == 1 else QColor(160, 20, 20) if idx == 3 else QColor(20, 20, 160)
        pen = QPen(QColor(0, 0, 0))
        ell.setBrush(color)
        ell.setPen(pen)
        ell.setZValue(120)
        lbl = QGraphicsSimpleTextItem(str(idx))
        lbl.setPos(x + 6, y - 6)
        lbl.setZValue(121)
        self.scene.addItem(ell)
        self.scene.addItem(lbl)
        self.corner_markers.append(ell)
        self.corner_markers.append(lbl)

    def _compute_homography_from_marked(self):
        if len(self.marked_pts) != 4:
            return

        # Ensure the points are ordered TL,TR,BR,BL first
        img_pts_ordered = order_quad_points(np.array(self.marked_pts, dtype=np.float64))

        # compute edge lengths for consecutive edges
        def dist(a, b):
            return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))
        edges = [
            dist(img_pts_ordered[0], img_pts_ordered[1]),
            dist(img_pts_ordered[1], img_pts_ordered[2]),
            dist(img_pts_ordered[2], img_pts_ordered[3]),
            dist(img_pts_ordered[3], img_pts_ordered[0]),
        ]
        # find index of longest edge (0..3)
        k = int(np.argmax(edges))

        # rotate points so that the longest edge becomes the world width edge
        idxs = [(k + i) % 4 for i in range(4)]
        img_pts_rot = img_pts_ordered[idxs]

        # clamp into image bounds
        img_pts_rot[:, 0] = np.clip(img_pts_rot[:, 0], 0, max(0, self.img_w - 1))
        img_pts_rot[:, 1] = np.clip(img_pts_rot[:, 1], 0, max(0, self.img_h - 1))

        # world rectangle points in meters (maps to the long edge = AREA_WIDTH_M)
        world_pts = np.array([
            [0.0, 0.0],
            [AREA_WIDTH_M, 0.0],
            [AREA_WIDTH_M, AREA_HEIGHT_M],
            [0.0, AREA_HEIGHT_M]
        ], dtype=np.float32)

        # compute homography mapping world -> img (using rotated points)
        H = cv2.getPerspectiveTransform(world_pts.astype(np.float32), img_pts_rot.astype(np.float32))
        H = H.astype(np.float64)
        H_inv = np.linalg.inv(H)

        self.H_world_to_img = H
        self.H_img_to_world = H_inv

        # commit rotated points back into marked_pts and refresh markers (so labels match)
        self.marked_pts = [(float(x), float(y)) for (x, y) in img_pts_rot]
        self._remove_corner_markers()
        for i, (x, y) in enumerate(self.marked_pts, start=1):
            self._add_corner_marker(x, y, i)

        # create / update projected grid overlay
        if self.grid_overlay:
            try:
                self.scene.removeItem(self.grid_overlay)
            except Exception:
                pass
            self.grid_overlay = None
        self.grid_overlay = ProjectedGridItem(self.scene.sceneRect(), H_world_to_img=H)
        self.scene.addItem(self.grid_overlay)

        self._show_hint("Homography computed — long edge mapped to AREA_WIDTH_M (10 cells). Grid projected.")
        print("Computed homography (world -> img):\n", H)

    def _show_hint(self, text):
        if self.coord_label:
            self.coord_label.setText(text)
        if self.window():
            self.window().statusBar().showMessage(text, 6000)

    def wheelEvent(self, event):
        # zoom control
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0:
            factor = zoom_in_factor
            self._zoom += 1
        else:
            factor = zoom_out_factor
            self._zoom -= 1
        if self._zoom > 30:
            self._zoom = 30
            return
        if self._zoom < -15:
            self._zoom = -15
            return
        self.scale(factor, factor)

    # ------------------------- Auto-detection -------------------------
    def auto_detect_corners(self, debug=True):
        """
        Improved auto-detect for a dominant rectangular contour.
        Returns True on success (and sets marked_pts + homography), False otherwise.

        debug: if True will draw a red polygon overlay showing the chosen quad.
        """
        if not self.pix_item:
            self._show_hint("Load an image first")
            return False

        # read image (prefer disk path for better fidelity)
        img_cv = None
        if self.current_image_path:
            img_cv = cv2.imread(self.current_image_path)
        if img_cv is None and self.pix_item:
            qimg = self.pix_item.pixmap().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            w = qimg.width(); h = qimg.height()
            ptr = qimg.bits()
            ptr.setsize(qimg.byteCount())
            arr = np.frombuffer(ptr, np.uint8).reshape((h, w, 4))
            img_cv = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)

        if img_cv is None:
            self._show_hint("Could not access image pixels for auto-detect")
            return False

        img_h, img_w = img_cv.shape[:2]
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        # 1) Preprocess: CLAHE to improve contrast in uneven lighting
        try:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray_eq = clahe.apply(gray)
        except Exception:
            gray_eq = gray.copy()

        # 2) Blur slightly to reduce noise
        gray_blur = cv2.GaussianBlur(gray_eq, (5, 5), 0)

        # 3) Automatic Canny thresholds based on median
        v = np.median(gray_blur)
        sigma = 0.33
        lower = int(max(0, (1.0 - sigma) * v))
        upper = int(min(255, (1.0 + sigma) * v))
        if lower >= upper:
            lower = max(0, int(v * 0.5))
            upper = min(255, int(v * 1.5))
        edges = cv2.Canny(gray_blur, lower, upper)

        # 4) Morphological closing (connect broken edges)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        edges_closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        # optional dilate to fill small gaps
        edges_closed = cv2.dilate(edges_closed, kernel, iterations=1)

        # 5) Find contours and score quad candidates
        contours, _ = cv2.findContours(edges_closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if not contours or len(contours) == 0:
            self._show_hint("No contours found")
            return False

        img_area = float(img_w * img_h)
        cand_quads = []
        # consider only large contours, sort by area descending
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        for cnt in contours[:200]:
            area = cv2.contourArea(cnt)
            if area < img_area * 0.002:  # skip very small contours (tweak if needed)
                continue
            peri = cv2.arcLength(cnt, True)
            # try a few approximation epsilons (sometimes 0.02 misses)
            for eps_factor in (0.02, 0.015, 0.025, 0.03):
                approx = cv2.approxPolyDP(cnt, eps_factor * peri, True)
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    pts = approx.reshape(4, 2).astype(np.float32)
                    # area of bounding box (minAreaRect) to measure rectangularity
                    rect = cv2.minAreaRect(pts)
                    box = cv2.boxPoints(rect)
                    box_area = abs(cv2.contourArea(box)) + 1e-9
                    rect_ratio = float(area) / float(box_area)
                    # score favors large area and high rectangularity (closer to 1)
                    score = float(area) * (rect_ratio ** 2)
                    cand_quads.append((score, pts))
                    break  # stop trying epsilons for this contour

        # If we found any candidates, pick best; else fallback to older detection
        chosen_pts = None
        if cand_quads:
            cand_quads.sort(key=lambda x: x[0], reverse=True)
            chosen_pts = cand_quads[0][1]  # (4,2) float32

            # refine corner points using cornerSubPix for subpixel accuracy
            try:
                # need initial corners in shape (N,1,2) float32
                init = chosen_pts.reshape(-1, 1, 2).astype(np.float32)
                # create a small window area around each corner
                gray_for_refine = gray_blur.copy()
                gray_for_refine = cv2.cvtColor(gray_for_refine, cv2.COLOR_GRAY2BGR) if gray_for_refine.ndim == 3 else gray_for_refine
                # cornerSubPix expects single-channel float32 or uint8
                gray_f = np.float32(gray_blur)
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)
                refined = cv2.cornerSubPix(gray_f, init, winSize=(11, 11), zeroZone=(-1, -1), criteria=criteria)
                if refined is not None and refined.shape[0] == 4:
                    chosen_pts = refined.reshape(4, 2)
            except Exception:
                pass

            # order points to TL,TR,BR,BL
            ordered = order_quad_points(chosen_pts)
            # clamp to image bounds
            ordered[:, 0] = np.clip(ordered[:, 0], 0, img_w - 1)
            ordered[:, 1] = np.clip(ordered[:, 1], 0, img_h - 1)
        else:
            # fallback: the older approach (threshold -> approx)
            # this is essentially your older code but with CLAHE + better edges
            _, th = cv2.threshold(gray_blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=2)
            contours2, _ = cv2.findContours(th, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            contours2 = sorted(contours2, key=cv2.contourArea, reverse=True)
            found = None
            for cnt in contours2[:100]:
                area = cv2.contourArea(cnt)
                if area < img_area * 0.002:
                    continue
                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    found = approx.reshape(4, 2).astype(np.float32)
                    break
            if found is not None:
                ordered = order_quad_points(found)
                ordered[:, 0] = np.clip(ordered[:, 0], 0, img_w - 1)
                ordered[:, 1] = np.clip(ordered[:, 1], 0, img_h - 1)
            else:
                self._show_hint("Auto-transform failed: no rectangular contour found")
                return False

        # At this point we have 'ordered' as TL,TR,BR,BL in image px
        self.marked_pts = [(float(x), float(y)) for (x, y) in ordered]
        self._remove_corner_markers()
        for i, (x, y) in enumerate(self.marked_pts, start=1):
            self._add_corner_marker(x, y, i)

        # If debug, show the chosen polygon overlay
        if debug:
            try:
                self._show_debug_contour(ordered)
            except Exception:
                pass

        # compute homography and update overlays (reuse your existing method)
        self._compute_homography_from_marked()
        self._show_hint("Auto-transform succeeded: corners detected and homography set")
        return True
    
    def _show_debug_contour(self, pts):
        """
        pts: ndarray shape (4,2) float - ordered TL,TR,BR,BL in image px
        Draw a red polygon overlay (temporary) so you can see detection.
        """
        # remove previous
        if hasattr(self, "_debug_item") and self._debug_item is not None:
            try:
                self.scene.removeItem(self._debug_item)
            except Exception:
                pass
            self._debug_item = None

        from PyQt5.QtGui import QPolygonF
        from PyQt5.QtCore import QPointF
        from PyQt5.QtWidgets import QGraphicsPathItem
        from PyQt5.QtGui import QPainterPath, QPen, QColor

        path = QPainterPath()
        path.moveTo(float(pts[0, 0]), float(pts[0, 1]))
        for p in pts[1:]:
            path.lineTo(float(p[0]), float(p[1]))
        path.closeSubpath()

        item = QGraphicsPathItem(path)
        pen = QPen(QColor(255, 0, 0, 200))
        pen.setWidthF(2.5)
        item.setPen(pen)
        item.setBrush(QColor(255, 0, 0, 40))
        item.setZValue(110)
        self._debug_item = item
        self.scene.addItem(item)

        # auto-remove debug overlay after a few seconds
        QTimer.singleShot(3000, lambda: (self.scene.removeItem(item) if item.scene() else None))
   

    # ------------------------- Zones management -------------------------
    def toggle_place_zones(self, enable: bool):
        self.placing_zones = bool(enable)
        if self.placing_zones:
            self._show_hint("Zone placement mode: click to place zones. Click 'Mark Zone(s)' again to exit.")
        else:
            self._show_hint("Exited zone placement mode.")

    def clear_zones(self):
        # remove zone graphics and stop their timers and animations
        for z in self.zones:
            try:
                if z._reg_timer.isActive():
                    z._reg_timer.stop()
                if z._dereg_timer.isActive():
                    z._dereg_timer.stop()
                if z._anim.isRunning():
                    z._anim.stop()
            except Exception:
                pass
            z.remove_from_scene(self.scene)
        self.zones = []
        self.next_zone_idx = 1
        print("[Zones CLEARED]")

    # optional callbacks when zone registered/deregistered/moved
    def zone_registered(self, zone):
        self._show_hint(f"Zone #{zone.idx} registered")
        # print already done inside Zone

    def zone_deregistered(self, zone):
        self._show_hint(f"Zone #{zone.idx} deregistered")

    def zone_moved(self, zone):
        # show world coords in statusbar as well
        world = zone._pixel_to_world(zone.center[0], zone.center[1])
        self._show_hint(f"Zone #{zone.idx} at {world[0]:.3f} m, {world[1]:.3f} m")

# ----- Main window and controls (adds zone buttons) -----
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image → World mapping + Zones (enhanced)")

        self.view = ImageGridView(self)
        info_label = QLabel("Load image then: Mark Corners OR Auto Transform. Use Mark Zone(s) to place circular zones.")
        info_label.setWordWrap(True)
        self.view.coord_label = info_label

        # buttons
        btn_open = QPushButton("Open Image")
        btn_mark = QPushButton("Mark Corners")
        btn_auto = QPushButton("Auto Transform")
        btn_zone = QPushButton("Mark Zone(s)")
        btn_clear_z = QPushButton("Clear Zone(s)")
        btn_clear = QPushButton("Clear Mapping")

        btn_open.clicked.connect(self.open_image)
        btn_mark.clicked.connect(self.start_marking)
        btn_auto.clicked.connect(self.auto_transform)
        btn_zone.setCheckable(True)
        btn_zone.toggled.connect(self.toggle_mark_zones)
        btn_clear_z.clicked.connect(self.clear_zones)
        btn_clear.clicked.connect(self.clear_mapping)

        hbox = QHBoxLayout()
        hbox.addWidget(btn_open)
        hbox.addWidget(btn_mark)
        hbox.addWidget(btn_auto)
        hbox.addWidget(btn_zone)
        hbox.addWidget(btn_clear_z)
        hbox.addWidget(btn_clear)
        hbox.addStretch()

        central = QWidget()
        vbox = QVBoxLayout(central)
        vbox.addLayout(hbox)
        vbox.addWidget(self.view)
        vbox.addWidget(info_label)
        self.setCentralWidget(central)

        open_act = QAction("Open Image...", self, triggered=self.open_image)
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        file_menu.addAction(open_act)

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open image", "", "Images (*.png *.jpg *.bmp *.tif)")
        if path:
            ok = self.view.load_image(path)
            if not ok:
                self.statusBar().showMessage("Failed to load image")
            else:
                self.statusBar().showMessage(f"Loaded {path}")

    def start_marking(self):
        if not self.view.pix_item:
            self.statusBar().showMessage("Load image first")
            return
        self.view.start_marking_corners()

    def auto_transform(self):
        if not self.view.pix_item:
            self.statusBar().showMessage("Load image first")
            return
        self.statusBar().showMessage("Running Auto Transform...")
        QApplication.processEvents()
        ok = self.view.auto_detect_corners()
        if ok:
            self.statusBar().showMessage("Auto Transform succeeded", 3000)
        else:
            self.statusBar().showMessage("Auto Transform failed — try manual marking", 5000)

    def toggle_mark_zones(self, checked):
        if not self.view.pix_item:
            self.statusBar().showMessage("Load image first")
            return
        self.view.toggle_place_zones(checked)
        if checked:
            self.statusBar().showMessage("Zone placement: ON", 2000)
        else:
            self.statusBar().showMessage("Zone placement: OFF", 2000)

    def clear_zones(self):
        self.view.clear_zones()
        self.statusBar().showMessage("Cleared all zones", 2000)

    def clear_mapping(self):
        self.view.H_world_to_img = None
        self.view.H_img_to_world = None
        self.view.marked_pts = []
        self.view.marking = False
        self.view._remove_corner_markers()
        if self.view.grid_overlay:
            try:
                self.view.scene.removeItem(self.view.grid_overlay)
            except Exception:
                pass
            self.view.grid_overlay = None
        self.view.clear_zones()
        self.statusBar().showMessage("Cleared corner mapping and zones", 4000)

# ----- run -----
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    sys.exit(app.exec_())
