# pgo-data-widget

`PgoPlotWidget` plots pointer positions in meters over a 4.80 m × 6.00 m space with an 8×10 grid.

## Behavior

- Subscribes to `AppBus.pointerUpdated(x_m, y_m, ts, source)`
- Plots path with y-down axis to match images/floorplans
- Rate-limited redraw at ~30 FPS

## Install

```bash
pip install -e packages/pgo_data_widget
```
