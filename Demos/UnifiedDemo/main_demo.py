
import sys, os, glob, time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel,
    QFileDialog, QAction, QToolBar, QMessageBox
)
from PyQt5.QtCore import Qt

from appbus import AppBus
from services.settings import load_settings
from services.mqtt_service import MqttService

def _start_server_bringup():
    sb = None
    try:
        from Demos.ServerBringUp import ServerBringUp
        sb = ServerBringUp()
        if hasattr(sb, "start"): sb.start()
        return sb
    except Exception:
        pass
    try:
        from ServerBringUp import ServerBringUp
        sb = ServerBringUp()
        if hasattr(sb, "start"): sb.start()
        return sb
    except Exception:
        print("[UnifiedDemo] ServerBringUp not found. Continuing without it.")
        return None

def _import_pkg_fallback():
    # Allow running from a repo where 'packages' are siblings of Demos/
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", ".."))
    pkgs_path = os.path.join(repo_root, "packages")
    if os.path.isdir(pkgs_path) and pkgs_path not in sys.path:
        sys.path.insert(0, pkgs_path)

_import_pkg_fallback()

def _load_pgo_widget(app_bus, services, settings):
    try:
        from pgo_data_widget import PgoPlotWidget
        return PgoPlotWidget(app_bus, services, settings)
    except Exception as e:
        w = QWidget(); QVBoxLayout(w).addWidget(QLabel(f"PGO Data widget not installed.\n{e}", w))
        return w

def _load_adaptive_widget(app_bus, services, settings):
    try:
        from adaptive_audio_widget import AdaptiveAudioWidget
        return AdaptiveAudioWidget(app_bus, services, settings)
    except Exception as e:
        w = QWidget(); QVBoxLayout(w).addWidget(QLabel(f"Adaptive Audio widget not installed.\n{e}", w))
        return w

def _load_zonedj_widget(app_bus, services, settings):
    try:
        from zone_dj_widget import ZoneDjWidget
        return ZoneDjWidget(app_bus, services, settings)
    except Exception as e:
        w = QWidget(); QVBoxLayout(w).addWidget(QLabel(f"Zone DJ widget not installed.\n{e}", w))
        return w

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Unified Demo • PGO Data | Adaptive Audio | Zone DJ")
        self.resize(1400, 900)

        self.settings = load_settings()
        self.bus = AppBus()
        self.services = {}

        # Services
        self.mqtt = MqttService(self.bus, self.settings)
        self.services["mqtt"] = self.mqtt

        # UI
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        self._build_tabs()
        self._build_toolbar()

        # Status & start
        self.bus.mqttStatusChanged.connect(self._on_mqtt_status)
        self.statusBar().showMessage("MQTT: starting…")
        self._server_bringup = _start_server_bringup()
        self.mqtt.start()

        # Default floorplan load (same folder as main demo)
        self._default_load_floorplan()

    # ---- Tabs ----
    def _build_tabs(self):
        self.tab_pgo = _load_pgo_widget(self.bus, self.services, self.settings)
        self.tab_adaptive = _load_adaptive_widget(self.bus, self.services, self.settings)
        self.tab_zonedj = _load_zonedj_widget(self.bus, self.services, self.settings)

        self.tabs.addTab(self.tab_pgo, "PGO Data")
        self.tabs.addTab(self.tab_adaptive, "Adaptive Audio")
        self.tabs.addTab(self.tab_zonedj, "Zone DJ")

        # Bridge zone events & audio command to MQTT publisher
        self.bus.zoneRegistered.connect(self._publish_zone_registered)
        self.bus.zoneDeregistered.connect(self._publish_zone_deregistered)
        self.bus.audioCommand.connect(self._publish_audio_command)

    # ---- Toolbar ----
    def _build_toolbar(self):
        tb = QToolBar("Floorplan", self)
        tb.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, tb)

        act_open = QAction("Open Image…", self)
        act_mark = QAction("Mark Corners", self)
        act_auto = QAction("Auto Transform", self)
        act_place = QAction("Place Zones", self); act_place.setCheckable(True)
        act_clear_z = QAction("Clear Zones", self)
        act_clear_h = QAction("Clear Mapping", self)

        act_open.triggered.connect(self._open_image)
        act_mark.triggered.connect(lambda: self._call_plan("start_marking_corners"))
        act_auto.triggered.connect(lambda: self._call_plan("auto_transform"))
        act_place.triggered.connect(lambda chk: self._call_plan("toggle_place_zones", chk))
        act_clear_z.triggered.connect(lambda: self._call_plan("clear_zones"))
        act_clear_h.triggered.connect(lambda: self._call_plan("clear_mapping"))

        tb.addAction(act_open)
        tb.addSeparator()
        tb.addAction(act_mark)
        tb.addAction(act_auto)
        tb.addSeparator()
        tb.addAction(act_place)
        tb.addAction(act_clear_z)
        tb.addAction(act_clear_h)

    def _current_plan(self):
        w = self.tabs.currentWidget()
        # Our two audio tabs expose .plan (FloorplanView). PGO tab does not.
        return getattr(w, "plan", None)

    def _call_plan(self, method, *args):
        plan = self._current_plan()
        if plan is None:
            QMessageBox.information(self, "No floorplan", "Switch to Adaptive Audio or Zone DJ to use this action.")
            return
        fn = getattr(plan, method, None)
        if not fn:
            QMessageBox.warning(self, "Not available", f"Current plan does not support '{method}'.")
            return
        try:
            fn(*args)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"{method} failed:\n{e}")

    # ---- File ops ----
    def _default_floorplan_dir(self):
        # same directory as this file, /assets/floorplans
        here = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(here, "assets", "floorplans")

    def _default_load_floorplan(self):
        plan = self._current_plan()
        # Load into both floorplan tabs so they share the same background
        candidates = []
        fdir = self._default_floorplan_dir()
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp"):
            candidates.extend(glob.glob(os.path.join(fdir, ext)))
        if not candidates:
            self.statusBar().showMessage(f"No floorplan image found in {fdir}.")
            return
        img = sorted(candidates)[0]
        for w in (self.tab_adaptive, self.tab_zonedj):
            plan = getattr(w, "plan", None)
            if plan:
                try:
                    ok = plan.load_image(img)
                    if ok:
                        self.statusBar().showMessage(f"Loaded floorplan: {os.path.basename(img)}")
                except Exception as e:
                    self.statusBar().showMessage(f"Failed to load default image: {e}")

    def _open_image(self):
        plan = self._current_plan()
        if plan is None:
            QMessageBox.information(self, "No floorplan", "Switch to Adaptive Audio or Zone DJ to use this action.")
            return
        start_dir = self._default_floorplan_dir()
        fn, _ = QFileDialog.getOpenFileName(self, "Open floorplan image", start_dir, "Images (*.png *.jpg *.jpeg *.bmp)")
        if not fn:
            return
        try:
            if plan.load_image(fn):
                self.statusBar().showMessage(f"Loaded: {os.path.basename(fn)}")
        except Exception as e:
            QMessageBox.critical(self, "Open failed", str(e))

    # ---- MQTT bridges ----
    def _publish_zone_registered(self, idx, x_m, y_m, ts, source):
        payload = {"zone": idx, "x_m": x_m, "y_m": y_m, "ts": ts, "source": source}
        self.mqtt.publish_zone_registered(payload)

    def _publish_zone_deregistered(self, idx, x_m, y_m, ts, source):
        payload = {"zone": idx, "x_m": x_m, "y_m": y_m, "ts": ts, "source": source}
        self.mqtt.publish_zone_deregistered(payload)

    def _publish_audio_command(self, device_id, cmd, payload):
        self.mqtt.publish_audio_command(device_id, cmd, payload)

    def _on_mqtt_status(self, s: str):
        self.statusBar().showMessage(f"MQTT: {s}")

    def closeEvent(self, event):
        try:
            self.mqtt.stop()
        except Exception:
            pass
        try:
            sb = self._server_bringup
            if sb and hasattr(sb, "stop"):
                sb.stop()
        except Exception:
            pass
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
