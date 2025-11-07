# zone-dj-widget

`ZoneDjWidget` embeds a `FloorplanView` and a right-side **MiniPlayer**. Users can place circular zones and each zone gets a demo queue. When a zone registers (hover ≥3 s, 1.5× hitbox), the next song in that zone’s queue is “played” (emitted as an audio command via AppBus). Leaving for ≥1 s pauses.

## Behavior

- Click **Place Zones** on the toolbar to add circular zones.
- Fades on register/deregister.
- Maintains per-zone queues; the **active zone** is last one registered.

## Signals (bridged via AppBus)

- Emits `zoneRegistered` / `zoneDeregistered`
- Emits `audioCommand(device_id=f"device_{idx}", cmd, payload)` for play/pause/skip/volume

## Install

```bash
pip install -e packages/zone_dj_widget
```
