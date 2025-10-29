# Services (Unified Demo)

## `services/settings.py`

- Wraps `QSettings` and primes defaults:
  - `world.width_m = 4.80`
  - `world.height_m = 6.00`
  - `grid.cols = 8`
  - `grid.rows = 10`
  - `grid.cell_m = 0.60`
  - `adaptive.split_y_m = 3.00`
  - `mqtt.host = localhost`, `mqtt.port = 1883`
  - `topics.tracking = tracking/position`
  - `topics.zone_registered = zones/registered`
  - `topics.zone_deregistered = zones/deregistered`
  - `topics.audio_control = audio/player/{device_id}/control`
  - `units.inbound = m`

> Use `settings.value(key, default, type=...)` in any widget/service to read these.

## `services/mqtt_service.py`

A small Paho→Qt bridge owned by `MainWindow`:

- `start()` / `stop()` manage the client connection
- **Subscribes**:
  - `tracking/position` → payload `{x,y,z,units,ts}` (drops `z`, normalizes to meters) → `AppBus.pointerUpdated`
- **Publishes**:
  - `zones/registered` / `zones/deregistered` → `{zone, x_m, y_m, ts, source}`
  - `audio/player/<device_id>/control` → `{cmd, ...payload}`

All cross-thread UI interactions happen via **AppBus signals** (Qt queued connections).

### Security & stability

- Placeholders for **TLS** and **username/password** exist; extend as needed.
- Reconnect with backoff is recommended for production environments.
