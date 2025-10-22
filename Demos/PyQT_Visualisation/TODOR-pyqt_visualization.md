# Deliverables

1. **Documentation files (saved as real files):**
   
   - `README.md` – quickstart, features, config constants, troubleshooting.  
     → `sandbox:/mnt/data/README.md`
   
   - `docs/UserGuide.md` – workflows (Auto Transform, Mark Corners/Zones), tips, debug.  
     → `sandbox:/mnt/data/docs/UserGuide.md`
   
   - `docs/DeveloperGuide.md` – architecture, homography & grid logic, auto-detect pipeline, zones & animations, extension points.  
     → `sandbox:/mnt/data/docs/DeveloperGuide.md`

2. **Design plans (no code yet):**
   
   - **MQTT integration (GUI side):**
     
     - Use a `Server(QObject)` wrapper (Paho-based) that emits `positionReceived(x_m, y_m, ts)` and `statusChanged(state)`.
     
     - A “virtual pointer” on the scene maps `(x_m, y_m)`→pixels via existing homography and drives the *same* zone register/deregister timers (3s / 1s).
     
     - On zone state changes, publish JSON events (`zones/registered`, `zones/deregistered`) to MQTT.
   
   - **audio_mqtt_client (RPi subscriber)**:
     
     - Config + client skeleton: subscribes to a control topic, parses `{cmd, song?, ts}`, executes `play/pause/skip/inc_vol/dec_vol/queue_next ...` on a local backend, logs only (no publishing for now).
     
     - Headless via `QCoreApplication` and signal/slot wiring; non-blocking backend calls.
   
   - **uwb_mqtt_client (RPi publisher)**:
     
     - Headless worker (`UwbClientWorker` in a `QThread`) that reads UWB frames from a source, optional preprocessing (EMA, outlier rejection), publishes `raw` and optional `filtered` topics, with rate limiting/coalescing and clean shutdown.
   
   - **Threading model guidance:**
     
     - `QCoreApplication` must live in the main thread.
     
     - Workers (MQTT, UWB, audio) in `QThread`s or use Paho’s own thread; cross-thread updates via Qt signals/slots (queued).

3. **Topic & payload contracts (agreed direction):**
   
   - **Inbound to GUI (pointer):** `tracking/position` → `{x, y, z, units, ts}` (GUI drops `z`).
   
   - **Outbound from GUI (zone events):** `zones/registered` / `zones/deregistered` → `{zone, x_m, y_m, x_px?, y_px?, ts, source:"pointer"}`.
   
   - **Audio control (server→Pi):** `audio/player/<device_id>/control` → `{cmd, song?, ts}`.
   
   - **UWB publish (Pi→broker):** `uwb/<device_id>/measurements` (raw) and optional `uwb/<device_id>/filtered` (preprocessed).

---

# TODO — prioritized, actionable

## A) Main PyQt program (GUI)

- **Add MQTT wiring**
  
  - Instantiate `audio_mqtt_server.Server` in `MainWindow`.
  
  - Connect `positionReceived → ImageGridView.on_position_received`.
  
  - Connect zone callbacks to publish events (`zone_registered/deregistered → server.publish_*`).

- **Pointer item & presence**
  
  - Add `pointer_item` to the scene; map world→px on updates.
  
  - Implement `_update_presence_with_pointer(x_px, y_px, ts)` that reuses 3s/1s timers (no mouse needed).
  
  - Optional: smoothing (EMA) + frame-rate throttle (e.g., 60 FPS max).

- **Settings**
  
  - Load/save broker host/port, topics, unit scale/axis flip via `QSettings` or YAML.
  
  - Add stale-timeout behavior: if no pointer updates, let zones naturally deregister.

**Acceptance**: Pointer follows MQTT; zones register after ~3s hover and deregister after ~1s leave; events publish with correct JSON.

---

## B) `audio_mqtt_server` package (Paho client wrapper)

- **`config.py`**
  
  - Define `BROKER`, `TOPICS` (`tracking/position`, `zones/registered`, `zones/deregistered`), `QOS`, `UNITS` (scale/axis), and logging.

- **`server.py`**
  
  - `Server(QObject)` with signals: `positionReceived(float, float, float)`, `statusChanged(str)`.
  
  - API: `start(cfg)`, `stop()`, `publish_zone_registered(payload)`, `publish_zone_deregistered(payload)`.
  
  - Normalize inbound `{x,y,z,units,ts}` → meters, drop `z`, emit signal (thread-safe).
  
  - Reconnect/backoff + minimal logging.

**Acceptance**: Emits normalized `positionReceived` on inbound messages; publishes zone events; clean start/stop.

---

## C) `audio_mqtt_client` (RPi subscriber; headless)

- **`config.py`**
  
  - `BROKER`, `TOPICS.control` (`audio/player/{device_id}/control`), `AUDIO` (backend, volume_step), `DEVICE`, and behavior guards (`ignore_old_msgs_s`).

- **`client.py`**
  
  - `QCoreApplication` headless.
  
  - Paho subscriber with `loop_start()`; parse JSON payloads; dispatch commands (`play/pause/skip/inc_vol/dec_vol/queue_next/song_queue/current_song/volume`).
  
  - Implement **PlayerFacade** interface (choose backend later; stub is OK now).
  
  - Non-blocking handlers; log latency `now - ts`.

**Acceptance**: Receives control messages, executes commands, logs outcomes; remains responsive.

---

## D) `uwb_mqtt_client` (RPi publisher; headless)

- **`config.py`**
  
  - `BROKER`, `TOPICS` (`raw`, `filtered`, `status`, `heartbeat`), `QOS`, `DEVICE`, `SOURCE` (serial/tcp/sdk), `PREPROCESS` (toggle/params), `PUBLISH` (rate_hz/coalesce).

- **`client.py`**
  
  - `UwbClientWorker(QObject)` in a `QThread`.
  
  - Dummy source (synthetic frames) to validate pipeline.
  
  - Optional inline preprocess (EMA + outlier rejection).
  
  - Publish `raw` at sensor or limited rate; include `ts_src`, `ts`, `latency_ms` (configurable).
  
  - Status retained (“online”, error messages), graceful stop.

**Acceptance**: Publishes well-formed raw frames at configured rate; handles start/stop and reconnect cleanly.

---

## E) Cross-cutting (both RPi clients)

- **Time sync**: confirm NTP on Pi; all logs/events include epoch timestamps.

- **Systemd units** (later): create service files with `Restart=always`.

- **Security** (optional now): broker auth/TLS config placeholders.

---

# Decisions captured

- `QCoreApplication` **must** be in the main thread; workers in `QThread`s or Paho’s thread; cross-thread via signals/slots.

- “MQTT server” in your nomenclature = **client wrapper owned by the GUI** (not a broker).

- Reuse zone hover logic for MQTT pointer presence (3s/1s) to avoid duplicate mechanisms.

- Use JSON payloads with explicit schema versioning for UWB streams.

---

# Nice-to-haves (after MVP)

- UI panel or YAML for live tuning (Canny/area for auto-detect, zone timers, pointer smoothing).

- CSV export of registered zones (world + grid indices).

- `zones/state` retained snapshot topic.

- UWB preprocess in `QThreadPool` with drop-latest backpressure policy.

---
