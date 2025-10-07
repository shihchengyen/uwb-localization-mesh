# 🚀 Project Hub — Overview & High‑Level Architecture

This repository contains **reusable packages** (e.g., `PGO`, `localization‑algos`, MQTT clients/servers, audio control) plus **bring‑up scripts** and **demos** that run across **RPi clients** and a **Laptop server**.

- **Packages**: import‑safe libraries with no side effects on import (pure modules).
- **Bring‑ups**: scripts that instantiate device roles (RPi client / Laptop server) and wire MQTT + state.
- **Demos**: thin scripts that call into running components to visualize or sonify results.
- **Data_collection**: follows the same pattern as a demo for capturing data for evaluation.

> Folder names may contain hyphens today, but **Python package names should be snake_case** when you refactor (e.g., `uwb_mqtt_client`).

---

## 📦 Packages (what each does)

**`packages/uwb-mqtt-client`**  
Client‑side publish of UWB measurements from RPi. Handles reconnect, keep‑alive, and simple backoff.  
_Main entry points:_ `UwbMqttClient.connect()`, `publish_measurement(measurement)`.

**`packages/uwb-mqtt-server`**  
Server‑side subscribe/ingestion of measurements from all RPis. Emits per‑phone **binned** data and invokes localization callbacks.  
_Main entry points:_ `UwbMqttServer.start()`, callback `on_measurement(measurement)` → binning pipeline.

**`packages/localization-algos`**  
Transforms binned local vectors into **relative edges** (anchor→phone), applies optional filters/weights, and prepares inputs for PGO.  
_Main entry points:_ `make_edges(binned_data)`, `apply_azimuth_correction(vec, yaw_deg)`.

**`packages/PGO` (being refactored into a pure package)**  
Pose Graph Optimization over anchors + phone nodes; outputs consistent **global positions** for rendering and audio routing.  
_Main entry points:_ `PGOSolver.add_edges(edges)`, `solve() -> GraphSolution`.

**`packages/audio-mqtt-server` / `packages/audio-mqtt-client`**  
MQTT topics for high‑level audio control (e.g., follow‑me, adaptive mixing).  
_Main entry points:_ `AudioMqttServer.start()`, `AudioMqttClient.send(route_cmd)`.

---

## 🧯 Bring‑ups (device roles)

**Client (RPi) — `Client_bring_up.py`**  
Instantiates an RPi node that publishes measurements and (optionally) consumes audio commands.
- `node_id = <int>`
- `uwb_mqtt_client = UwbMqttClient()`
- `audio_mqtt_client = AudioMqttClient()`
- `position = [x, y, z]` (optional local telemetry)

**Server (Laptop) — `Server_bring_up.py`**  
Central ingest + processing + outputs for demos.
- `nodes = {0:[x,y,z], 1:[x,y,z], ...}` (ground truth anchors)
- `uwb_mqtt_server = UwbMqttServer()` → **bin** measurements per phone
- `data = {phone_id: BinnedData, ...}` (rolling 1‑second windows)
- `localization_algos` → edges → `PGO` → `GraphSolution`
- `audio_mqtt_server = AudioMqttServer()` + `audio_player = ... (TBD)`
- `user_position = [x, y, z]` (derived from PGO)

---

## ▶️ Demos (run after bring‑ups)

**`Demos/Basic_render_graph`** — plots the PGO graph on a grid (anchors + phone).  
**`Demos/Follow_me_audio`** — uses user position to route audio (via audio MQTT).  
**`Demos/Adaptive_audio`** — adjusts playback based on zones or proximity.  
**`Demos/Speaker_setup`** — utility flows to register speaker positions & sanity‑check.  
**`Data_collection`** — captures raw measurements and solver outputs for evaluation.

**Run order (base case):**
```bash
# 1) Start MQTT broker on laptop
echo "listener 1883
allow_anonymous true" > mosquitto.conf
mosquitto -c mosquitto.conf

# 2) Start server (in new terminal)
# Replace with your laptop's IP
python Server_bring_up.py --broker 192.168.68.66

# 3) Start anchors on RPis (in separate terminals)
# Replace with your laptop's IP
python Anchor_bring_up.py --anchor-id 0 --broker 192.168.68.66
python Anchor_bring_up.py --anchor-id 1 --broker 192.168.68.66
python Anchor_bring_up.py --anchor-id 2 --broker 192.168.68.66
python Anchor_bring_up.py --anchor-id 3 --broker 192.168.68.66

# 4) Run a demo (in new terminal)
python Demos/Basic_render_graph/run.py
# or
python Demos/Follow_me_audio/run.py
```

> **Important**: Always start the MQTT broker first, then server, then anchors.

> If you use `uv`, the same commands work with `uv run …`

---

## 🧠 High‑Level Data & Control Flow (Mermaid)

```mermaid
flowchart LR
  subgraph Clients [RPi Clients]
    C0[Client 0] -->|UWB measurement| MQTTC[(MQTT Broker)]
    C1[Client 1] -->|UWB measurement| MQTTC
  end

  MQTTC -->|subscribe| S[Server Bring-up]
  S -->|bin 1s windows\navg per anchor| L[localization-algos]
  L -->|edges (anchor→phone)| PGO[PGO Solver]
  PGO -->|graph solution\n(global positions)| OUT[Outputs]

  subgraph Outputs
    R[Basic_render_graph]:::demo
    F[Follow_me_audio]:::demo
    A[Adaptive_audio]:::demo
  end

  OUT --> R
  OUT --> F
  OUT --> A

  classDef demo fill:#eef,stroke:#99f;
```

---

## 📚 Reference Repositories

| Repo | Scope / What it’s for | Link |
|---|---|---|
| **Embedded Firmware** | Low‑level firmware for the hardware platform | https://github.com/Hong-yiii/location_intelligence_embedded |
| **RPI Code** | RPi‑side code for Murata 2BP UWB module | https://github.com/jionggg/bang-olufsen_rpi |
| **UWB Phone App** | iPhone app for UWB module control & tests | https://github.com/Hong-yiii/Bang_and_olufsen_UWB_Testing |
| **Evals/Data Collections** | (TBD) iPhone‑side eval/data capture | TODO |
| **MQTT Topics** | Topic conventions (reference) | https://github.com/anitej1/UWB-MQTT |
| **Optimisation Code** | Global grid coordinates + middleware demos | https://github.com/jionggg/location_intelligence_optimisation |

---

## ✅ TL;DR

- **Bring‑ups** start device roles and wire MQTT + state.  
- **Packages** are pure and reused across demos.  
- **Demos** visualize or sonify the solver outputs.  
- **Order**: Server → Clients → Demo.
