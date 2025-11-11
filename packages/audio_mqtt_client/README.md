# Audio MQTT Client

Raspberry Pi audio player that receives and executes synchronized audio commands.

## Components

### `follow-me_audio_client.py`
Main RPi audio client for the follow-me audio system.

**Usage:**
```bash
python packages/audio_mqtt_client/follow-me_audio_client.py --id 0 --wav crazy-carls-brickhouse-tavern.wav --broker localhost
```

### `synchronized_audio_player_rpi.py`
Original RPi audio player (older implementation).

## Speaker Configuration

- **RPi 0, 3:** RIGHT channel (play right channel of stereo audio)
- **RPi 1, 2:** LEFT channel (play left channel of stereo audio)

**Front/Back Pairing:**
- **Front:** RPi 2 (LEFT), RPi 3 (RIGHT)
- **Back:** RPi 1 (LEFT), RPi 0 (RIGHT)

## Audio Setup

Configured for Raspberry Pi 3.5mm headphone jack:
- Uses ALSA driver
- ALSA card 2 (3.5mm jack)
- Sample rate: 22050 Hz
- Stereo (2 channels)
- Buffer: 512

## Commands

- `start`: Start playing audio (loops forever)
- `pause`: Pause audio
- `volume`: Set volume (0-100)
- `load_track`: Load and switch to a new audio file

## MQTT Subscriptions

- `audio/commands/broadcast`: All speakers
- `audio/commands/rpi_{id}`: Specific speaker

