# feat/dummyserver Branch Contents

## Core DummyServer Files
- `Demos/DummyServerBringUp.py` - Main dummy server implementation
- `Demos/DummyServerBringUp_README.md` - DummyServer documentation

## UnifiedDemo Application
- `Demos/UnifiedDemo/main_demo.py` - Main application entry point
- `Demos/UnifiedDemo/README.md` - UnifiedDemo documentation
- `Demos/UnifiedDemo/QUICK_START.md` - Quick start guide
- `Demos/UnifiedDemo/assets/` - Floorplan assets (if any)

## Packages Required for UnifiedDemo
- `packages/appbus.py` - Signal hub for inter-component communication
- `packages/services/` - Settings service
- `packages/mini_player/` - Shared mini player widget
- `packages/viz_floorplan/` - Floorplan visualization widget
- `packages/pgo_data_widget/` - PGO data plotting widget
- `packages/adaptive_audio_widget/` - Adaptive audio widget
- `packages/zone_dj_widget/` - Zone DJ widget

## Packages Required for DummyServerBringUp
- `packages/datatypes/` - Data type definitions (Measurement, BinnedData, etc.)
- `packages/localization_algos/` - Localization algorithms (binning, PGO, edge creation)
- `packages/uwb_mqtt_server/` - UWB MQTT server config (for MQTTConfig)
- `packages/audio_mqtt_server/` - Audio MQTT server (optional, for audio features)

## Documentation
- `Demos/UnifiedDemo_Planning/UnifiedDemo_plan.md` - Architecture planning document
- `Demos/UnifiedDemo_Planning/Implementation_Summary.md` - Implementation summary
- `Demos/UnifiedDemo_Planning/UI_Design_Proposal.md` - UI design proposal
- `Demos/UnifiedDemo_Planning/DummyServer_TODO.md` - DummyServer TODOs

## Configuration Files
- `requirements.txt` - Python dependencies
- `setup.py` - Package setup (if exists)
- `pyproject.toml` - Project configuration (if exists)

## Diagnostic Files (Optional - may exclude)
- `DIAGNOSIS_FIGURE8_ISSUES.md` - Diagnostic report (can be excluded if not needed)

