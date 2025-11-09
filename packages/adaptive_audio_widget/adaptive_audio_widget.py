
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt5.QtCore import pyqtSlot
from viz_floorplan import FloorplanView
from .mini_player import MiniPlayer

class AdaptiveAudioWidget(QWidget):
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
        side.addWidget(QLabel('Adaptive Audio: load image, mark/auto transform, use midline zones.', self))
        self.player = MiniPlayer('Adaptive Player', self); side.addWidget(self.player, 1)
        root.addLayout(side, 0)
        self.plan.zoneRegistered.connect(self._on_zone_registered)
        self.plan.zoneDeregistered.connect(self._on_zone_deregistered)
        self.player.playClicked.connect(lambda: self.bus.audioCommand.emit('adaptive', 'play', {}))
        self.player.pauseClicked.connect(lambda: self.bus.audioCommand.emit('adaptive', 'pause', {}))
        self.player.skipClicked.connect(lambda: self.bus.audioCommand.emit('adaptive', 'skip', {}))
        self.player.volumeChanged.connect(lambda v: self.bus.audioCommand.emit('adaptive', 'volume', {'level': int(v)}))
        self.bus.pointerUpdated.connect(self._on_pointer)

    @pyqtSlot(float, float, float, str)
    def _on_pointer(self, x_m, y_m, ts, source):
        self.plan.map_pointer(x_m, y_m, ts, source)

    def _on_zone_registered(self, idx, x_m, y_m, ts, src):
        self.bus.zoneRegistered.emit(idx, x_m, y_m, ts, src)

    def _on_zone_deregistered(self, idx, x_m, y_m, ts, src):
        self.bus.zoneDeregistered.emit(idx, x_m, y_m, ts, src)
