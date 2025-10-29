
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt5.QtCore import pyqtSlot
from viz_floorplan import FloorplanView
from .mini_player import MiniPlayer

class ZoneDjWidget(QWidget):
    def __init__(self, app_bus, services, settings, parent=None):
        super().__init__(parent)
        self.bus = app_bus; self.services = services; self.settings = settings
        root = QHBoxLayout(self)
        self.plan = FloorplanView(self,
                                  world_w_m=float(settings.value('world.width_m', 4.80, type=float)),
                                  world_h_m=float(settings.value('world.height_m', 6.00, type=float)),
                                  grid_cols=int(settings.value('grid.cols', 8, type=int)),
                                  grid_rows=int(settings.value('grid.rows', 10, type=int)))
        root.addWidget(self.plan, 1)
        side = QVBoxLayout()
        side.addWidget(QLabel('Zone DJ: add circular zones, queues auto-assigned.', self))
        self.player = MiniPlayer('Zone DJ Player', self); side.addWidget(self.player, 1)
        root.addLayout(side, 0)

        self._queues = {}; self._next_idx = {}; self._active_zone = None
        self.plan.zoneRegistered.connect(self._on_zone_registered)
        self.plan.zoneDeregistered.connect(self._on_zone_deregistered)
        self.plan.zoneMoved.connect(self._on_zone_moved)
        self.player.playClicked.connect(self._play_active)
        self.player.pauseClicked.connect(self._pause_active)
        self.player.skipClicked.connect(self._skip_active)
        self.player.volumeChanged.connect(lambda v: self.bus.audioCommand.emit(f'device_{self._active_zone}' if self._active_zone is not None else 'device_0', 'volume', {'level': int(v)}))
        self.bus.pointerUpdated.connect(lambda x,y,t,s: self.plan.map_pointer(x,y,t,s))

    def _ensure_queue(self, idx):
        if idx not in self._queues:
            self._queues[idx] = [f'Song {idx+1}-A', f'Song {idx+1}-B', f'Song {idx+1}-C']
            self._next_idx[idx] = 0

    @pyqtSlot(object, float, float, float, str)
    def _on_zone_registered(self, idx, x_m, y_m, ts, src):
        self._ensure_queue(idx)
        self._active_zone = idx
        q = self._queues[idx]; i = self._next_idx[idx]; song = q[i % len(q)]; self._next_idx[idx] = i + 1
        self.player.set_queue(q)
        self.bus.zoneRegistered.emit(idx, x_m, y_m, ts, src)
        self.bus.audioCommand.emit(f'device_{idx}', 'play', {'song': song, 'zone': idx})

    @pyqtSlot(object, float, float, float, str)
    def _on_zone_deregistered(self, idx, x_m, y_m, ts, src):
        self.bus.zoneDeregistered.emit(idx, x_m, y_m, ts, src)
        self.bus.audioCommand.emit(f'device_{idx}', 'pause', {'zone': idx})

    @pyqtSlot(object, float, float)
    def _on_zone_moved(self, idx, x_m, y_m):
        pass

    def _play_active(self):
        if self._active_zone is None: return
        self.bus.audioCommand.emit(f'device_{self._active_zone}', 'play', {})

    def _pause_active(self):
        if self._active_zone is None: return
        self.bus.audioCommand.emit(f'device_{self._active_zone}', 'pause', {})

    def _skip_active(self):
        if self._active_zone is None: return
        self.bus.audioCommand.emit(f'device_{self._active_zone}', 'skip', {})
