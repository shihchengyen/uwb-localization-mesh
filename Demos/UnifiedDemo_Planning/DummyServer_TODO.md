# DummyServerBringUp.py TODO - Missing Methods

## Cross-Check: AppBus Signals → DummyServer Methods

### ✅ **IMPLEMENTED & ALIGNED**

| AppBus Signal             | MainWindow Handler                | DummyServer Method             | Status                                         |
| ------------------------- | --------------------------------- | ------------------------------ | ---------------------------------------------- |
| `playRequested`           | `_on_play_requested()`            | ❌ **MISSING**                  | Need `play()`                                  |
| `pauseRequested`          | `_on_pause_requested()`           | ❌ **MISSING**                  | Need `pause()`                                 |
| `stopRequested`           | `_on_stop_requested()`            | ❌ **MISSING**                  | Need `stop_playback()`                         |
| `skipRequested`           | `_on_skip_requested()`            | ❌ **MISSING**                  | Need `skip_track()`                            |
| `previousRequested`       | `_on_previous_requested()`        | ❌ **MISSING**                  | Need `previous_track()`                        |
| `seekRequested`           | `_on_seek_requested()`            | ❌ **MISSING**                  | Need `seek(position)`                          |
| `audioStartRequested`     | `_on_audio_start_requested()`     | ✅ `adaptive_audio_demo()`      | **OK**                                         |
|                           |                                   | ✅ `zone_dj_demo()`             | **OK**                                         |
| `audioStopRequested`      | `_on_audio_stop_requested()`      | ✅ `stop_adaptive_audio_demo()` | **OK**                                         |
|                           |                                   | ✅ `stop_zone_dj_demo()`        | **OK**                                         |
| `adaptiveAudioEnabled`    | `_on_adaptive_audio_enabled()`    | ❌ **MISSING**                  | Need `enable_adaptive_audio(enabled)`          |
| `zoneDjEnabled`           | `_on_zone_dj_enabled()`           | ❌ **MISSING**                  | Need `enable_zone_dj(enabled)`                 |
| `bypassAudioRequested`    | `_on_bypass_audio_requested()`    | ❌ **MISSING**                  | Need `bypass_audio_processing(bypass)`         |
| `playlistChangeRequested` | `_on_playlist_change_requested()` | ✅ `set_playlist(number)`       | **OK**                                         |
| `volumeChangeRequested`   | `_on_volume_change_requested()`   | ❌ **MISSING**                  | Need `set_volume(device_id, volume)`           |
|                           |                                   | ❌ **MISSING**                  | Need `set_global_volume(volume)`               |
| `globalVolumeChanged`     | `_on_global_volume_changed()`     | ❌ **MISSING**                  | Need `set_global_volume(volume)`               |
| `simulationSpeedChanged`  | `_on_simulation_speed_changed()`  | ✅ Direct attribute             | **OK** (via `server.simulation_speed = speed`) |

### ✅ **POLLING METHODS NEEDED**

| MainWindow Polling        | DummyServer Method            | Status      |
| ------------------------- | ----------------------------- | ----------- |
| `_poll_playback_state()`  | ❌ `get_queue_preview(count)`  | **MISSING** |
|                           | ❌ `get_current_track()`       | **MISSING** |
|                           | ❌ `get_playback_progress()`   | **MISSING** |
|                           | ❌ `is_playing()`              | **MISSING** |
|                           | ❌ `get_speaker_states()`      | **MISSING** |
| `_poll_server_position()` | ✅ `user_position` (attribute) | **OK**      |

---

## 📋 **TODO: Methods to Implement**

### **Priority 1: Playback Control (Critical)**

```python
def play(self) -> None:
    """Resume playback (or start if stopped)."""
    # TODO: Implement
    #  - Set self._is_playing = True
    #  - Log playback state change
    #  - If adaptive_audio_server exists, resume playback
    pass

def pause(self) -> None:
    """Pause current playback."""
    # TODO: Implement
    #  - Set self._is_playing = False
    #  - Log playback state change
    #  - If adaptive_audio_server exists, pause playback
    pass

def stop_playback(self) -> None:
    """Stop playback completely."""
    # TODO: Implement
    #  - Set self._is_playing = False
    #  - Reset self.current_track_index to 0
    #  - Log playback state change
    pass

def skip_track(self) -> None:
    """Skip to next track in queue."""
    # TODO: Implement
    #  - Increment self.current_track_index
    #  - Wrap around if at end of playlist
    #  - Log track change
    pass

def previous_track(self) -> None:
    """Go back to previous track."""
    # TODO: Implement
    #  - Decrement self.current_track_index
    #  - Clamp at 0 (don't wrap around)
    #  - Log track change
    pass

def seek(self, position: float) -> None:
    """Seek to position in current track (0.0-1.0)."""
    # TODO: Implement
    #  - Set self._playback_progress = position
    #  - Log seek action (simulated)
    pass

def is_playing(self) -> bool:
    """Return True if currently playing."""
    # TODO: Implement
    #  - Return self._is_playing
    return False  # Placeholder

def get_playback_progress(self) -> float:
    """Get current track progress (0.0-1.0)."""
    # TODO: Implement
    #  - Return self._playback_progress
    #  - Could simulate progress based on elapsed time
    return 0.0  # Placeholder
```

### **Priority 2: Playlist & Queue Management (High)**

```python
def get_current_track(self) -> str:
    """Get currently playing track name."""
    # TODO: Implement
    #  - Return self.current_playlist[self.current_track_index]
    #  - Handle edge cases (empty playlist, index out of range)
    return "Unknown Track"  # Placeholder

def get_queue_preview(self, count: int = 5) -> list:
    """Get next N tracks in queue."""
    # TODO: Implement
    #  - Return slice of self.current_playlist starting from current_track_index
    #  - Return next `count` tracks
    return []  # Placeholder

def get_playlist(self, playlist_id: int) -> list:
    """Get playlist by ID (returns list of track names)."""
    # TODO: Implement
    #  - Define 5 playlists with sample tracks
    #  - Return playlist based on ID (1-5)
    playlists = {
        1: ["Track 1.1 - Artist A", "Track 1.2 - Artist B", "Track 1.3 - Artist C"],
        2: ["Track 2.1 - Artist D", "Track 2.2 - Artist E", "Track 2.3 - Artist F"],
        3: ["Track 3.1 - Artist G", "Track 3.2 - Artist H", "Track 3.3 - Artist I"],
        4: ["Track 4.1 - Artist J", "Track 4.2 - Artist K", "Track 4.3 - Artist L"],
        5: ["Track 5.1 - Artist M", "Track 5.2 - Artist N", "Track 5.3 - Artist O"],
    }
    return playlists.get(playlist_id, [])
```

### **Priority 3: Volume Control (High)**

```python
def set_volume(self, device_id: int, volume: int) -> None:
    """Set volume for specific device (0-100)."""
    # TODO: Implement
    #  - Update self.volumes[device_id] = volume
    #  - Clamp volume to 0-100
    #  - Log volume change
    #  - Call _send_audio_command if needed
    pass

def set_global_volume(self, volume: int) -> None:
    """Set master volume for all devices (0-100)."""
    # TODO: Implement
    #  - Update all entries in self.volumes dict
    #  - Clamp volume to 0-100
    #  - Log volume change
    pass

def get_volume(self, device_id: int) -> int:
    """Get current volume for device."""
    # TODO: Implement
    #  - Return self.volumes.get(device_id, 0)
    return 0  # Placeholder

def get_speaker_states(self) -> dict:
    """Get all speaker states (volumes, active status)."""
    # TODO: Implement
    #  - Return dict with device states
    #  - Include: device_id, volume, active status
    return {}  # Placeholder
    # Example return:
    # {
    #     0: {"volume": 70, "active": True},
    #     1: {"volume": 70, "active": True},
    #     2: {"volume": 0, "active": False},
    #     3: {"volume": 0, "active": False},
    # }
```

### **Priority 4: Audio Mode Control (Medium)**

```python
def enable_adaptive_audio(self, enabled: bool) -> None:
    """Enable or disable adaptive audio processing."""
    # TODO: Implement
    #  - Set self._adaptive_audio_enabled = enabled
    #  - If enabled, start adaptive_audio_demo()
    #  - If disabled, stop_adaptive_audio_demo()
    #  - Log state change
    pass

def enable_zone_dj(self, enabled: bool) -> None:
    """Enable or disable zone DJ mode."""
    # TODO: Implement
    #  - Set self._zone_dj_enabled = enabled
    #  - If enabled, start zone_dj_demo()
    #  - If disabled, stop_zone_dj_demo()
    #  - Log state change
    pass

def bypass_audio_processing(self, bypass: bool) -> None:
    """Bypass all audio DSP processing (passthrough mode)."""
    # TODO: Implement
    #  - Set self._audio_bypass = bypass
    #  - Log bypass state change
    #  - If bypassed, disable all audio processing
    pass
```

### **Priority 5: State Query Methods (Low)**

```python
def get_audio_state(self) -> dict:
    """Get complete audio state (mode, playback, volumes)."""
    # TODO: Implement
    #  - Return comprehensive state dict
    return {
        "is_playing": False,  # self._is_playing
        "current_track": "",  # self.get_current_track()
        "track_index": 0,     # self.current_track_index
        "progress": 0.0,      # self._playback_progress
        "volumes": {},        # self.volumes
        "adaptive_enabled": False,  # self._adaptive_audio_enabled
        "zone_dj_enabled": False,   # self._zone_dj_enabled
        "bypass": False,      # self._audio_bypass
    }

def get_zone_state(self) -> dict:
    """Get current zone activation state."""
    # TODO: Implement
    #  - Return zone-related state
    #  - Current pair (front/back)
    #  - Active zones
    return {
        "current_pair": None,  # self.current_pair
        "started_for_pair": None,  # self.started_for_pair
    }
```

---

## 📋 **TODO: Attributes to Add**

### **Required Attributes**

```python
def __init__(self, ...):
    # ... existing init code ...

    # TODO: Add playback state attributes
    self._is_playing = False
    self._playback_progress = 0.0  # 0.0-1.0

    # TODO: Add playlist management attributes
    self.current_playlist = [
        "Demo Track 1 - Artist A",
        "Demo Track 2 - Artist B",
        "Demo Track 3 - Artist C",
        "Demo Track 4 - Artist D",
        "Demo Track 5 - Artist E",
    ]
    self.current_track_index = 0

    # TODO: Add audio mode state attributes
    self._adaptive_audio_enabled = False
    self._zone_dj_enabled = False
    self._audio_bypass = False

    # FIX: Make volumes always initialized (not conditional)
    if not hasattr(self, 'volumes') or not self.volumes:
        self.volumes = {0: 70, 1: 70, 2: 70, 3: 70}
```

---

## ⚠️ **ISSUES & FIXES NEEDED**

### Issue 1: Conditional `volumes` Initialization

**Problem:** `self.volumes` is only initialized if `mqtt_config` is provided.

**Current Code (lines 132-152):**

```python
if mqtt_config:
    # ... volumes initialized here
    self.volumes = {0: 70, 1: 70, 2: 70, 3: 70}
else:
    self.volumes = {}
```

**Fix:**

```python
# ALWAYS initialize volumes (widgets need it regardless of MQTT)
self.volumes = {0: 70, 1: 70, 2: 70, 3: 70}

if mqtt_config:
    # ... MQTT-specific setup ...
```

### Issue 2: Missing Playlist State

**Problem:** No playlist management state.

**Fix:** Add attributes in `__init__`:

```python
self.current_playlist = self.get_playlist(1)  # Default to playlist 1
self.current_track_index = 0
```

### Issue 3: Missing Playback State

**Problem:** No tracking of playing/paused state.

**Fix:** Add attributes in `__init__`:

```python
self._is_playing = False
self._playback_progress = 0.0
```

---

## 🔄 **Implementation Priority**

### **Sprint 1: Core Playback (Must Have)**

1. ✅ `play()`, `pause()`, `stop_playback()` - Basic playback control
2. ✅ `skip_track()`, `previous_track()` - Track navigation
3. ✅ `is_playing()` - State query
4. ✅ Add `_is_playing`, `current_playlist`, `current_track_index` attributes

### **Sprint 2: Queue & Volume (Must Have)**

5. ✅ `get_current_track()`, `get_queue_preview()` - Queue display
6. ✅ `set_volume()`, `set_global_volume()`, `get_volume()` - Volume control
7. ✅ `get_speaker_states()` - State polling
8. ✅ Fix `volumes` initialization (always init, not conditional)

### **Sprint 3: Advanced Features (Nice to Have)**

9. ✅ `seek()`, `get_playback_progress()` - Seek control
10. ✅ `enable_adaptive_audio()`, `enable_zone_dj()`, `bypass_audio_processing()` - Mode control
11. ✅ `get_audio_state()`, `get_zone_state()` - Complete state query
12. ✅ `get_playlist()` - Playlist management

---

## 📊 **Summary**

| Category             | Implemented | Missing   | Total  |
| -------------------- | ----------- | --------- | ------ |
| **Lifecycle**        | 2/2         | 0         | 2      |
| **Audio Modes**      | 4/7         | 3         | 7      |
| **Playback Control** | 0/8         | 8         | 8      |
| **Playlist/Queue**   | 1/5         | 4         | 5      |
| **Volume Control**   | 0/4         | 4         | 4      |
| **State Query**      | 0/2         | 2         | 2      |
| **Attributes**       | 4/7         | 3         | 7      |
| **TOTAL**            | **11/35**   | **24/35** | **35** |

**Coverage: 31.4%** (11 out of 35 methods/attributes implemented)

---

## ✅ **Validation Checklist**

After implementing missing methods, verify:

- [ ] All AppBus signals have corresponding DummyServer methods
- [ ] All MainWindow handlers can successfully call DummyServer methods
- [ ] All polling methods have corresponding DummyServer query methods
- [ ] All attributes documented in API are present
- [ ] `volumes` dict is always initialized (not conditional)
- [ ] Playback state (`_is_playing`, `current_track_index`) is tracked
- [ ] All methods log their actions (JSON format)
- [ ] Thread safety considered (add locks if needed for new state)
- [ ] Methods are callable from main thread only (via AppBus routing)

---

**Created:** 2025-01-11  
**Based on:** UnifiedDemo_plan.md v4.0
