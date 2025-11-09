
from PyQt5.QtCore import (Qt, QRectF, QPointF, QTimer, QObject, QVariantAnimation, pyqtSignal)
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGraphicsView, QLabel, QGraphicsScene, QGraphicsEllipseItem, QGraphicsItem, QGraphicsPixmapItem, QGraphicsSimpleTextItem)
from PyQt5.QtGui import (QPainter, QPen, QColor, QFont, QImage, QPainterPath, QPixmap)
import numpy as np, math, cv2, time

AREA_WIDTH_M = 4.80
AREA_HEIGHT_M = 6.00
GRID_COLS = 8
GRID_ROWS = 10
CELL_SIZE_M = AREA_WIDTH_M / GRID_COLS

def apply_homography(H, pts):
    pts = np.asarray(pts, dtype=np.float64)
    if pts.ndim == 1:
        pts = pts.reshape(1, 2)
    n = pts.shape[0]
    homo = np.ones((n, 3), dtype=np.float64)
    homo[:, 0:2] = pts
    res = homo @ H.T
    res[:, 0] = res[:, 0] / np.where(res[:, 2] == 0, 1e-9, res[:, 2])
    res[:, 1] = res[:, 1] / np.where(res[:, 2] == 0, 1e-9, res[:, 2])
    return res[:, :2]

def order_quad_points(pts):
    pts = np.array(pts, dtype=np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).flatten()
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float64)

class ProjectedGridItem(QGraphicsItem):
    def __init__(self, scene_rect: QRectF, H_world_to_img=None):
        super().__init__()
        self.scene_rect = scene_rect
        self.H = H_world_to_img
        self.setZValue(3)

    def boundingRect(self):
        return self.scene_rect

    def paint(self, painter: QPainter, option, widget=None):
        if self.H is None:
            return
        pen = QPen(QColor(200, 10, 10, 200))
        pen.setWidthF(1.0)
        painter.setPen(pen)

        for c in range(GRID_COLS + 1):
            x_m = c * CELL_SIZE_M
            ys = np.linspace(0, AREA_HEIGHT_M, 160)
            pts_world = np.column_stack((np.full_like(ys, x_m), ys))
            proj = apply_homography(self.H, pts_world)
            path = QPainterPath(); started = False
            for (x, y) in proj:
                if math.isfinite(x) and math.isfinite(y):
                    if not started: path.moveTo(x, y); started = True
                    else: path.lineTo(x, y)
                else:
                    if started: painter.drawPath(path); path = QPainterPath(); started = False
            if started: painter.drawPath(path)

        for r in range(GRID_ROWS + 1):
            y_m = r * CELL_SIZE_M
            xs = np.linspace(0, AREA_WIDTH_M, 160)
            pts_world = np.column_stack((xs, np.full_like(xs, y_m)))
            proj = apply_homography(self.H, pts_world)
            path = QPainterPath(); started = False
            for (x, y) in proj:
                if math.isfinite(x) and math.isfinite(y):
                    if not started: path.moveTo(x, y); started = True
                    else: path.lineTo(x, y)
                else:
                    if started: painter.drawPath(path); path = QPainterPath(); started = False
            if started: painter.drawPath(path)

class FloorplanView(QWidget):
    zoneRegistered = pyqtSignal(object, float, float, float, str)
    zoneDeregistered = pyqtSignal(object, float, float, float, str)
    zoneMoved = pyqtSignal(object, float, float)
    pointerMapped = pyqtSignal(float, float, float, str)

    def __init__(self, parent=None, world_w_m=AREA_WIDTH_M, world_h_m=AREA_HEIGHT_M, grid_cols=GRID_COLS, grid_rows=GRID_ROWS):
        super().__init__(parent)
        global AREA_WIDTH_M, AREA_HEIGHT_M, GRID_COLS, GRID_ROWS, CELL_SIZE_M
        AREA_WIDTH_M = world_w_m; AREA_HEIGHT_M = world_h_m
        GRID_COLS = grid_cols; GRID_ROWS = grid_rows
        CELL_SIZE_M = AREA_WIDTH_M / GRID_COLS

        self.view = _ImageGridView(self)
        self.info = QLabel("", self); self.info.setWordWrap(True)
        lay = QVBoxLayout(self); lay.addWidget(self.view); lay.addWidget(self.info)
        self.view.coord_label = self.info
        self.view._signal_emit = self._emit_proxy

    def _emit_proxy(self, kind, *args):
        if kind == "registered": self.zoneRegistered.emit(*args)
        elif kind == "deregistered": self.zoneDeregistered.emit(*args)
        elif kind == "moved": self.zoneMoved.emit(*args)
        elif kind == "mapped": self.pointerMapped.emit(*args)

    def load_image(self, path: str): return self.view.load_image(path)
    def start_marking_corners(self): self.view.start_marking_corners()
    def auto_transform(self): return self.view.auto_detect_corners()
    def toggle_place_zones(self, enable: bool): self.view.toggle_place_zones(enable)
    def clear_mapping(self): self.view.clear_mapping()
    def clear_zones(self): self.view.clear_zones()

    def map_pointer(self, x_m, y_m, ts, source="mqtt"):
        if self.view.H_world_to_img is not None:
            pt = apply_homography(self.view.H_world_to_img, [[x_m, y_m]])[0]
            self.view.set_virtual_pointer_pixel(float(pt[0]), float(pt[1]), ts, source)
        else:
            self.pointerMapped.emit(x_m, y_m, ts, source)

class _ZoneHitboxItem(QGraphicsEllipseItem):
    def __init__(self, center_x, center_y, hit_r_px, zone):
        rect = QRectF(-hit_r_px, -hit_r_px, hit_r_px*2, hit_r_px*2)
        super().__init__(rect)
        self.zone = zone
        self.setAcceptHoverEvents(True)
        p = QPen(); p.setStyle(Qt.NoPen); self.setPen(p)
        self.setBrush(QColor(0,0,0,0))
        self.setZValue(50)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setPos(center_x, center_y)
        self.setCursor(Qt.OpenHandCursor)

    def hoverEnterEvent(self, e):
        self.zone._on_hover_enter(); super().hoverEnterEvent(e)
    def hoverLeaveEvent(self, e):
        self.zone._on_hover_leave(); super().hoverLeaveEvent(e)
    def mousePressEvent(self, e):
        self.setCursor(Qt.ClosedHandCursor); super().mousePressEvent(e)
    def mouseReleaseEvent(self, e):
        self.setCursor(Qt.OpenHandCursor); super().mouseReleaseEvent(e)
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            pos = value; self.zone._on_moved(pos.x(), pos.y())
        return super().itemChange(change, value)

class _Zone(QObject):
    def __init__(self, view, x_px, y_px, radius_m, idx):
        super().__init__()
        self.view = view; self.idx = idx
        self.center = (x_px, y_px); self.radius_m = radius_m
        r_px = self._m_to_px(radius_m); r_px = max(3.0, r_px)
        self.radius_px = float(r_px); self.hit_radius_px = float(self.radius_px*1.5)
        self.hitbox = _ZoneHitboxItem(x_px, y_px, self.hit_radius_px, self)
        self.visual = QGraphicsEllipseItem(-self.radius_px, -self.radius_px, 2*self.radius_px, 2*self.radius_px, parent=self.hitbox)
        self.visual.setBrush(QColor(200,200,200,140)); self.visual.setPen(QPen(QColor(80,80,80,160))); self.visual.setZValue(60); self.visual.setOpacity(0.6)
        h = max(4.0, self.radius_px*0.15)
        self.handle = QGraphicsEllipseItem(-h, -h, 2*h, 2*h, parent=self.hitbox)
        self.handle.setBrush(QColor(100,100,255,200)); self.handle.setPen(QPen(QColor(40,40,120,200))); self.handle.setZValue(70); self.handle.setCursor(Qt.OpenHandCursor)
        self.label = QGraphicsSimpleTextItem(str(idx), parent=self.hitbox); self.label.setPos(self.radius_px+4, -6); self.label.setZValue(61)
        self.tooltip = QGraphicsSimpleTextItem("", parent=self.hitbox); f = QFont(); f.setPointSize(12); self.tooltip.setFont(f); self.tooltip.setZValue(80); self.tooltip.setVisible(False); self._update_tip_pos()
        self.registered = False
        self._reg = QTimer(); self._reg.setSingleShot(True); self._reg.timeout.connect(self._do_register)
        self._dereg = QTimer(); self._dereg.setSingleShot(True); self._dereg.timeout.connect(self._do_deregister)
        self._anim = QVariantAnimation(); self._anim.valueChanged.connect(lambda v: self.visual.setOpacity(float(v))); self._anim.setDuration(300)

    def add(self, scene): scene.addItem(self.hitbox)
    def remove(self, scene): 
        try: scene.removeItem(self.hitbox)
        except Exception: pass

    def _m_to_px(self, m):
        if self.view.H_world_to_img is not None:
            p0 = apply_homography(self.view.H_world_to_img, [[0.0, 0.0]])[0]
            p1 = apply_homography(self.view.H_world_to_img, [[m, 0.0]])[0]
            return math.hypot(float(p1[0])-float(p0[0]), float(p1[1])-float(p0[1]))
        if self.view.img_w and AREA_WIDTH_M>0: return m * (float(self.view.img_w)/float(AREA_WIDTH_M))
        return m*100.0

    def _on_hover_enter(self):
        if self._dereg.isActive(): self._dereg.stop()
        self._show_tip(True)
        if self.registered: return
        if not self._reg.isActive(): self._reg.start(3000)

    def _on_hover_leave(self):
        QTimer.singleShot(250, lambda: self._show_tip(False))
        if self._reg.isActive():
            self._reg.stop(); return
        if self.registered and not self._dereg.isActive():
            self._dereg.start(1000)

    def _do_register(self):
        self.registered = True
        self._anim.stop(); self._anim.setStartValue(self.visual.opacity()); self._anim.setEndValue(1.0); self._anim.start()
        self.visual.setBrush(QColor(120,220,120,200))
        world = self._px_to_m(*self.center)
        if self.view._signal_emit: self.view._signal_emit("registered", self.idx, world[0], world[1], time.time(), "pointer")

    def _do_deregister(self):
        self.registered = False
        self._anim.stop(); self._anim.setStartValue(self.visual.opacity()); self._anim.setEndValue(0.6); self._anim.start()
        self.visual.setBrush(QColor(200,200,200,140))
        world = self._px_to_m(*self.center)
        if self.view._signal_emit: self.view._signal_emit("deregistered", self.idx, world[0], world[1], time.time(), "pointer")

    def _on_moved(self, x_px, y_px):
        self.center = (float(x_px), float(y_px)); self.label.setPos(self.radius_px+4,-6); self._update_tip_pos()
        world = self._px_to_m(*self.center)
        if self.view._signal_emit: self.view._signal_emit("moved", self.idx, world[0], world[1])

    def _px_to_m(self, x_px, y_px):
        if self.view.H_img_to_world is not None:
            res = apply_homography(self.view.H_img_to_world, [[x_px, y_px]])[0]
            return (float(res[0]), float(res[1]))
        if self.view.img_w and AREA_WIDTH_M>0:
            ppm = float(self.view.img_w)/float(AREA_WIDTH_M); return (x_px/ppm, y_px/ppm)
        return (0.0,0.0)

    def _show_tip(self, show):
        if show:
            w = self._px_to_m(*self.center)
            self.tooltip.setText(f"{w[0]:.3f} m, {w[1]:.3f} m"); self.tooltip.setVisible(True)
        else:
            self.tooltip.setVisible(False)

    def _update_tip_pos(self):
        self.tooltip.setPos(-self.tooltip.boundingRect().width()/2, -self.radius_px-16)

class _ImageGridView(QGraphicsView):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.scene = QGraphicsScene(self); self.setScene(self.scene)

        self.pix_item = None; self.img_w = 0; self.img_h = 0; self.current_image_path = None
        self.H_world_to_img = None; self.H_img_to_world = None
        self.marking = False; self.marked_pts = []; self.grid_overlay=None; self.corner_markers=[]
        self.zones = []; self.placing_zones = False; self.next_zone_idx=1
        self._zoom = 0
        self._signal_emit = None

        self.pointer = QGraphicsEllipseItem(-4, -4, 8, 8)
        self.pointer.setBrush(QColor(255,0,0,220)); self.pointer.setPen(QPen(Qt.NoPen)); self.pointer.setZValue(200)
        self.pointer.setVisible(False); self.scene.addItem(self.pointer)

    def load_image(self, filename):
        pix = QPixmap(filename)
        if pix.isNull(): return False
        self.scene.clear()
        self.scene.addItem(self.pointer); self.pointer.setVisible(False)
        self.pix_item = QGraphicsPixmapItem(pix); self.pix_item.setZValue(0); self.pix_item.setPos(0,0)
        self.scene.addItem(self.pix_item)

        self.img_w = pix.width(); self.img_h = pix.height()
        self.current_image_path = filename
        self.scene.setSceneRect(0,0,self.img_w,self.img_h)

        self.H_world_to_img = None; self.H_img_to_world=None; self.marked_pts=[]
        self._remove_corner_markers()
        if self.grid_overlay: self.scene.removeItem(self.grid_overlay); self.grid_overlay=None
        self.clear_zones()

        self.fitInView(self.pix_item.boundingRect(), Qt.KeepAspectRatio); self._zoom=0
        return True

    def start_marking_corners(self):
        if not self.pix_item: return
        self.marking = True; self.marked_pts = []; self._remove_corner_markers()
        self._hint("Click 4 image points: TL, TR, BR, BL (in order)")

    def set_virtual_pointer_pixel(self, x_px, y_px, ts, source):
        self.pointer.setVisible(True); self.pointer.setPos(float(x_px), float(y_px))
        if self._signal_emit and self.H_img_to_world is not None:
            res = apply_homography(self.H_img_to_world, [[x_px, y_px]])[0]
            self._signal_emit("mapped", float(res[0]), float(res[1]), ts, source)

    def clear_mapping(self):
        self.H_world_to_img = None; self.H_img_to_world=None; self.marked_pts=[]
        self._remove_corner_markers()
        if self.grid_overlay: self.scene.removeItem(self.grid_overlay); self.grid_overlay=None
        self.clear_zones()

    def toggle_place_zones(self, enable: bool):
        self.placing_zones = bool(enable)
        if self.placing_zones: self._hint("Zone placement mode: click to place zones.")
        else: self._hint("Exited zone placement.")

    def clear_zones(self):
        for z in self.zones:
            try:
                if z._reg.isActive(): z._reg.stop()
                if z._dereg.isActive(): z._dereg.stop()
                if z._anim.isRunning(): z._anim.stop()
            except Exception: pass
            z.remove(self.scene)
        self.zones=[]; self.next_zone_idx=1

    def mousePressEvent(self, event):
        if event.button()==Qt.LeftButton:
            pt = self.mapToScene(event.pos()); x=float(pt.x()); y=float(pt.y())
            if not (0<=x<self.img_w and 0<=y<self.img_h): return super().mousePressEvent(event)
            if self.placing_zones:
                z = _Zone(self, x, y, 0.25, self.next_zone_idx); z.add(self.scene); self.zones.append(z); self.next_zone_idx += 1
                self._hint(f"Placed zone #{z.idx}"); return
            if self.marking:
                self.marked_pts.append((x, y)); self._add_corner_marker(x, y, len(self.marked_pts))
                if len(self.marked_pts)==4:
                    self.marking=False; self._compute_homography_from_marked()
                else:
                    self._hint(f"Marked corner {len(self.marked_pts)}/4")
                return
        return super().mousePressEvent(event)

    def wheelEvent(self, event):
        zf = 1.25; factor = zf if event.angleDelta().y()>0 else 1/zf
        self._zoom += (1 if factor>1 else -1)
        if self._zoom>30 or self._zoom<-15: return
        self.scale(factor, factor)

    def _remove_corner_markers(self):
        for m in getattr(self, "corner_markers", []):
            try: self.scene.removeItem(m)
            except Exception: pass
        self.corner_markers=[]

    def _add_corner_marker(self, x, y, idx):
        r=6; ell = QGraphicsEllipseItem(x-r, y-r, r*2, r*2)
        color = QColor(20,160,20) if idx==1 else QColor(160,20,20) if idx==3 else QColor(20,20,160)
        pen = QPen(QColor(0,0,0)); ell.setBrush(color); ell.setPen(pen); ell.setZValue(120)
        lbl = QGraphicsSimpleTextItem(str(idx)); lbl.setPos(x+6, y-6); lbl.setZValue(121)
        self.scene.addItem(ell); self.scene.addItem(lbl)
        self.corner_markers += [ell, lbl]

    def _compute_homography_from_marked(self):
        if len(self.marked_pts)!=4: return
        img_pts_ordered = order_quad_points(np.array(self.marked_pts, dtype=np.float64))
        def dist(a,b): return math.hypot(float(a[0])-float(b[0]), float(a[1])-float(b[1]))
        edges=[dist(img_pts_ordered[0],img_pts_ordered[1]),dist(img_pts_ordered[1],img_pts_ordered[2]),dist(img_pts_ordered[2],img_pts_ordered[3]),dist(img_pts_ordered[3],img_pts_ordered[0])]
        k=int(np.argmax(edges)); idxs=[(k+i)%4 for i in range(4)]; img_pts_rot = img_pts_ordered[idxs]
        img_pts_rot[:,0]=np.clip(img_pts_rot[:,0],0,max(0,self.img_w-1)); img_pts_rot[:,1]=np.clip(img_pts_rot[:,1],0,max(0,self.img_h-1))
        world_pts = np.array([[0.0,0.0],[AREA_WIDTH_M,0.0],[AREA_WIDTH_M,AREA_HEIGHT_M],[0.0,AREA_HEIGHT_M]], dtype=np.float32)
        H = cv2.getPerspectiveTransform(world_pts.astype(np.float32), img_pts_rot.astype(np.float32))
        H = H.astype(np.float64); H_inv = np.linalg.inv(H)
        self.H_world_to_img = H; self.H_img_to_world = H_inv
        self.marked_pts = [(float(x), float(y)) for (x,y) in img_pts_rot]
        self._remove_corner_markers()
        for i,(x,y) in enumerate(self.marked_pts, start=1): self._add_corner_marker(x,y,i)
        if self.grid_overlay: self.scene.removeItem(self.grid_overlay); self.grid_overlay=None
        self.grid_overlay = ProjectedGridItem(self.scene.sceneRect(), H_world_to_img=H); self.scene.addItem(self.grid_overlay)
        self._hint("Homography computed and grid projected.")

    def auto_detect_corners(self, debug=True):
        if not self.pix_item: self._hint("Load an image first"); return False
        img_cv = cv2.imread(self.current_image_path) if self.current_image_path else None
        if img_cv is None:
            qimg = self.pix_item.pixmap().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            w=qimg.width(); h=qimg.height(); ptr=qimg.bits(); ptr.setsize(qimg.byteCount())
            arr=np.frombuffer(ptr, np.uint8).reshape((h,w,4)); img_cv=cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)

        img_h, img_w = img_cv.shape[:2]; gray=cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        try:
            clahe=cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)); gray_eq=clahe.apply(gray)
        except Exception: gray_eq=gray.copy()
        blur=cv2.GaussianBlur(gray_eq,(5,5),0)
        v=np.median(blur); sigma=0.33; lower=int(max(0,(1.0-sigma)*v)); upper=int(min(255,(1.0+sigma)*v))
        if lower>=upper: lower=max(0,int(v*0.5)); upper=min(255,int(v*1.5))
        edges=cv2.Canny(blur, lower, upper)
        kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(5,5))
        edges=cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2); edges=cv2.dilate(edges, kernel, iterations=1)
        contours,_=cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if not contours: self._hint("No contours found"); return False
        img_area=float(img_w*img_h); contours=sorted(contours, key=cv2.contourArea, reverse=True)
        cand=[]
        for cnt in contours[:200]:
            area=cv2.contourArea(cnt)
            if area<img_area*0.002: continue
            peri=cv2.arcLength(cnt,True)
            for eps in (0.02,0.015,0.025,0.03):
                approx=cv2.approxPolyDP(cnt, eps*peri, True)
                if len(approx)==4 and cv2.isContourConvex(approx):
                    pts=approx.reshape(4,2).astype(np.float32)
                    rect=cv2.minAreaRect(pts); box=cv2.boxPoints(rect); box_area=abs(cv2.contourArea(box))+1e-9
                    rect_ratio=float(area)/float(box_area); score=float(area)*(rect_ratio**2)
                    cand.append((score, pts)); break
        if not cand:
            self._hint("Auto-transform failed"); return False
        cand.sort(key=lambda x:x[0], reverse=True); chosen=cand[0][1]
        ordered=order_quad_points(chosen); ordered[:,0]=np.clip(ordered[:,0],0,img_w-1); ordered[:,1]=np.clip(ordered[:,1],0,img_h-1)
        self.marked_pts=[(float(x),float(y)) for (x,y) in ordered]
        self._remove_corner_markers()
        for i,(x,y) in enumerate(self.marked_pts, start=1): self._add_corner_marker(x,y,i)
        self._compute_homography_from_marked(); self._hint("Auto-transform succeeded"); return True

    def _hint(self, text):
        if getattr(self.host, "info", None): self.host.info.setText(text)
        if self.window(): self.window().statusBar().showMessage(text, 4000)
