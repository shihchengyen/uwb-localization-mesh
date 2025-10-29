# adaptive-audio-widget

`AdaptiveAudioWidget` embeds a `FloorplanView` plus a right-hand **MiniPlayer**.

## Behavior

- Loads floorplan images and computes homography (manual/auto).
- Uses the same zone presence logic (3s register / 1s deregister) if you place zones.
- For a **fixed 2-zone split** (e.g., at 3.00 m), read pointer world coords from `pointerMapped` and apply your own A/B logic in the main app.

## Signals (bridged via AppBus)

- Receives `pointerUpdated` and calls `plan.map_pointer(...)`.
- Re-emits `zoneRegistered` / `zoneDeregistered` to AppBus.
- The **MiniPlayer** emits play/pause/skip/volume intents; main app turns them into MQTT control messages.

## Install

```bash
pip install -e packages/adaptive_audio_widget
```
