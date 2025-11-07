# Architecture

## Overview

```
QApplication
└─ MainWindow
   ├─ AppBus (signals)
   ├─ Services
   │  └─ MqttService (Paho→Qt bridge)
   └─ QTabWidget
      ├─ PgoPlotWidget
      ├─ AdaptiveAudioWidget
      └─ ZoneDjWidget
```

**AppBus** decouples widgets and services using Qt signals:
- `pointerUpdated(x_m, y_m, ts, source)`
- `zoneRegistered(idx, x_m, y_m, ts, source)`
- `zoneDeregistered(idx, x_m, y_m, ts, source)`
- `audioCommand(device_id, cmd, payload)`
- `mqttStatusChanged(state)`

**MqttService** bridges MQTT topics to/from AppBus (thread-safe).

**FloorplanView** (from `viz_floorplan`) provides:
- Image loading, **corner marking**, **auto-transform**.
- World↔Image **homography (H, H⁻¹)** and **grid projection**.
- Draggable circular **zones** with **3s register / 1s deregister** and **fade animation**.
- A **virtual pointer** mapped from world meters.

## Data flow

- **Inbound tracking**: MQTT `tracking/position` `{x,y,z,units,ts}` → normalize to meters → `AppBus.pointerUpdated()`
- **Pointer rendering**: `AdaptiveAudioWidget` / `ZoneDjWidget` call `FloorplanView.map_pointer()` → draw red dot
- **Zone presence**: When dot hovers ≥3 s within a zone’s 1.5× radius hitbox → `zoneRegistered` (fade up). Leave ≥1 s → `zoneDeregistered` (fade down).
- **Outbound events**: MainWindow listens and publishes to `zones/*`; player actions emit `audioCommand`.

## Extension points

- Replace the MiniPlayer with your real player or attach an audio backend on the RPi side; keep the UI signals.
- Use `pointerMapped` signal in `FloorplanView` for world-meter reads from pixel positions.
- Swap the auto-corner detector with a marker-based or ArUco-based detector if your scenes vary.
