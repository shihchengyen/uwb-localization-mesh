# AppBus (Signal Hub)

Lightweight Qt signal hub used by the Unified Demo to decouple widgets and services.

## Signals

- `pointerUpdated(float x_m, float y_m, float ts, str source)`
- `zoneRegistered(object idx, float x_m, float y_m, float ts, str source)`
- `zoneDeregistered(object idx, float x_m, float y_m, float ts, str source)`
- `audioCommand(str device_id, str cmd, dict payload)`
- `mqttStatusChanged(str state)`

## Usage

Create once in the main app and pass to widgets/services:

```python
self.bus = AppBus()
```

Emit or connect in your component:

```python
self.bus.audioCommand.emit("adaptive", "play", {})
self.bus.zoneRegistered.connect(on_zone)
```
