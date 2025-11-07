
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QListWidget, QHBoxLayout, QSlider
from PyQt5.QtCore import Qt, pyqtSignal

class MiniPlayer(QWidget):
    playClicked = pyqtSignal()
    pauseClicked = pyqtSignal()
    skipClicked = pyqtSignal()
    volumeChanged = pyqtSignal(int)

    def __init__(self, title='Player', parent=None):
        super().__init__(parent)
        self.setMinimumWidth(240)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f'<b>{title}</b>', self))
        self.queue = QListWidget(self); lay.addWidget(self.queue, 1)
        btns = QHBoxLayout()
        self.btn_play = QPushButton('Play'); self.btn_pause = QPushButton('Pause'); self.btn_skip = QPushButton('Skip')
        btns.addWidget(self.btn_play); btns.addWidget(self.btn_pause); btns.addWidget(self.btn_skip)
        lay.addLayout(btns)
        vol = QHBoxLayout(); vol.addWidget(QLabel('Vol')); self.vol = QSlider(Qt.Horizontal, self); self.vol.setRange(0,100); self.vol.setValue(60); vol.addWidget(self.vol, 1)
        lay.addLayout(vol)
        self.btn_play.clicked.connect(self.playClicked.emit)
        self.btn_pause.clicked.connect(self.pauseClicked.emit)
        self.btn_skip.clicked.connect(self.skipClicked.emit)
        self.vol.valueChanged.connect(self.volumeChanged.emit)

    def set_queue(self, items):
        self.queue.clear()
        if items: self.queue.addItems(items)
