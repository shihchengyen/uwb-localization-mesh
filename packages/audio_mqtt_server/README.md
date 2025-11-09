# Audio MQTT Server
# Audio control: adapt speakers based on new position
# FollowMeAudioServer automatically:
# - Switches between front/back speaker pairs (Y threshold)
# - Adjusts left/right volumes (X-axis panning)
# - Sends MQTT commands to RPi clients
Server-side components for adaptive audio control based on user position.

## Components

### `follow-me_audio_server.py`
Main server that coordinates UWB positioning and audio control.

**Architecture:**
- Inherits from `ServerBringUp` to track user position via UWB measurements
- Controls RPi speakers directly based on position
- No external dependencies; all logic integrated

**Usage:**
```bash
python packages/audio_mqtt_server/follow-me_audio_server.py --broker localhost --port 1884
```

**Features:**
- Monitors user position at ~10 Hz
- Automatically switches between front/back speaker pairs
- Adjusts left/right volume based on horizontal position
- Optional `--no-audio` flag to disable audio control (position tracking only)

**Audio Logic:**
- **Front/Back:** Y >= 300 → back speakers (1,0); Y < 300 → front speakers (2,3)
- **Left/Right Panning:** Volume varies around X=240 center
  - Moving right: increase LEFT speaker, decrease RIGHT speaker
  - Moving left: increase RIGHT speaker, decrease LEFT speaker

### `adaptive_audio_controller.py` (DEPRECATED)
Old standalone audio controller. This logic has been integrated into `follow-me_audio_server.py`.

## Audio Files

- `crazy-carls-brickhouse-tavern.wav`: Test audio file
- `funky-bossanova-guitar.wav`: Test audio file
- `guitar-on-loop.mp3`: Test audio file

## MQTT Topics

- `audio/commands/broadcast`: Commands for all speakers
- `audio/commands/rpi_{id}`: Commands for specific RPi (0-3)

## Message Format

```json
{
  "command": "start|pause|volume",
  "execute_time": 1234567890.123,
  "global_time": 1234567890.0,
  "delay_ms": 500,
  "timestamp": "2024-01-01T00:00:00Z",
  "rpi_id": 0,
  "command_id": "uuid",
  "target_volume": 70  // Only for "volume" command
}
```

## Architecture Flow

```
ServerBringUp (UWB positioning)
    ↓ tracks position
FollowMeAudioServer (extends ServerBringUp)
    ↓ controls audio based on position
FollowMeAudioClient (on RPi)
    ↓ plays audio
```
