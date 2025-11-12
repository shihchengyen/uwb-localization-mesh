# Refactor task 

# Theyre 3 main goals
1. make it such that the whole system is functional as a whole, all the buttons on the pyqt front end should work
2. Remove uncessary parts from pyqt - minimal interfaces and functions that pyqt will be calling
3. Ensure that all functions are passed downstream all the way until the hardware


# The architecture
1. The highest level should be the pyqt, here only high level logic is handled 
2. AdaptiveAudioServer, this is instatiated by ServerBringUpProMax, it is through this object that it can communicate with the hardware, this object should also be where all the stateful information such as the current playlist and the song should be stored, PYQT should observe attributes such as the self.song_queue = []
3. Say i request to skip a song from the PYQT front end, you should be calling the AdaptiveAudioServer
4. The AdaptiveAudioServer interfaces with hardware using the _send_audio_command() method
5. the hardware layer interfaces it with packages/audio_mqtt_client/synchronized_audio_player_rpi.py through commands

# Functionality that needs to be implemented from the front end (PYQT)
1. set volume based off the slider in the front end this is based off the mini_player.py and pause and play
- This is the strategy, once again its the same pattern of interfacing with the AdaptiveAudioServer, through sending audio commands to the client


2. the constant polling of the user position in all 3 views (I believe this is a pyqt signal) 

3. Skipping of songs from the mini player
- This is the strategy, once again its the same pattern of interfacing with the AdaptiveAudioServer, calling next_song()
- next_song() should then send pop one from the list then send a audio command over to the client on the rpi

4. showing the Queue preview of the nxt song
- Here the pyqt layer should observe the AdaptiveAudioServer's song_queue, this will be a list of strings which are the exact names of the .wav files 


5. playlist management
- the playlists are hard coded, kept inside and controlled by the playlist_controller

6. Adaptive audio
- In this demo, you can keep the overall init from the pyqt from what has been built somewhat similar, the main action should be that it calls adaptive_audio_start(), then does all the observing, 
- the playlist should just be playlist 1
- the ability to skip should still be there

4. Zone DJ
This is slightly more complicated due to the logic on the PYQT side and implemented in packages/zone_dj_widget/zone_dj_widget.py
- main logic is that you should be that the change in a zone changes the next songs in the Queue Preview, 
- once again, this pyqt layer should be calling the methods from the AudioController to interface and veiw the observables 


# Functionality to be removed 
- No need to show a preview of the song album 
- Remove the time slider bar for the length of the song 
- No need to be able to click and manually select playlists 
- Album name can be removed 
- Bypass Audio Processing

# Additional Changes (Phase 2)

## Coordinate System Update
1. Rearrange the coordinate system:
   - Bottom left corner should be (0,0)
   - Bottom right should be (600,0) 
   - Top left should be (0,480)
   - Top right should be (600,480)
   - This creates a 600x480 coordinate system with origin at bottom-left

## Zone System Redesign
2. Remove default adaptive audio zones (top/bottom half split):
   - Remove the automatic Zone A/Zone B rectangular zones in adaptive audio
   - All zones should be user-designated circular zones
   - Zone placement should be in global coordinates (0,0) to (600,480)
   - Zone coordinates should be independent of rendered image coordinates
   - Zone 1 plays playlist 1, Zone 2 plays playlist 2, etc. (up to 5 zones max)

## Adaptive Audio Simplification  
3. Adaptive Audio screen changes:
   - Remove zone-based logic completely
   - Just play from playlist 1 continuously
   - No zone registration/deregistration needed
   - Simplified position-based audio panning without zones

## Additional Updates (Phase 3)

### PGO Widget Coordinate System Update
4. Updated PGO plot widget to use new 600x480 coordinate system:
   - Changed world dimensions from 4.80x6.00 to 6.00x4.80 meters
   - Updated grid from 8x10 to 10x8 cells
   - Removed Y-axis inversion (origin now at bottom-left)
   - Updated documentation and comments

### Anchor Position Updates  
5. Updated anchor positions across all files:
   - Server_bring_up_with_Audio.py: Updated to new coordinate system
   - DummyServerBringUp.py: Updated anchor positions to match
   - Anchor_bring_up.py: Descriptions already match new system

### Auto-Detect Corners Fix
6. Fixed auto-detect corners functionality:
   - Added auto-centering for default floorplan loading
   - Implemented _center_default_floorplan() method
   - Applied centering to both specific and fallback floorplan loading
   - Uses 10% margins for proper centering within coordinate bounds

### Zone Activation Debugging
7. Added comprehensive debug logging for zone activation:
   - FloorplanView: Logs when zones register/deregister with visual feedback status
   - ZoneDjWidget: Logs playlist changes and server state verification
   - Clear console output shows zone activation flow and playlist switching
   - Helps verify the 3-second activation timer and playlist changes are working

### Zone Transition Fix
8. Fixed zone transition logic for direct zone-to-zone movement:
   - Detects when user moves directly from Zone 1 to Zone 3 without exiting
   - Immediately deactivates old zone when transitioning to new zone
   - Cancels conflicting timers during zone transitions
   - Starts new 3-second timer for the new zone
   - Prevents multiple active zones and ensures proper playlist switching

### Zone System Simplification
9. Simplified zone system to only two clear states:
   - **Current Zone**: Zone user is currently in (immediate detection, light green)
   - **Active Zone**: Zone that's been active for 3+ seconds (bright green, controls playlist)
   - When any zone becomes active, ALL other zones are immediately deactivated
   - Only one zone can be active at a time - clean and predictable behavior
   - Removed complex timer management and state conflicts

### Adaptive Audio Complete Simplification
10. Removed all zone functionality from Adaptive Audio widget:
   - No zones displayed on floorplan in adaptive audio mode
   - No playlist switching - always uses Playlist 1
   - Pure position-based audio panning (front/back, left/right)
   - Immediate response to position changes without zone timers
   - Disabled zone placement functionality in adaptive audio mode
   - Clean separation between Zone DJ (user zones) and Adaptive Audio (position-only)

### Song Switching Implementation
11. Implemented complete song switching functionality:
   - Added `load_track` command to RPi audio player (synchronized_audio_player_rpi.py)
   - Updated AdaptiveAudioServer with `get_load_track_commands()` method
   - Modified ServerBringUpProMax `skip_track()` and `previous_track()` to send load commands
   - Updated MQTT command publishing to support `track_file` parameter
   - Created `audio_files/` directory for storing audio tracks
   - Updated all playlists to use proper file paths (audio_files/filename.wav)
   - Song switching now works: PyQt → Server → AdaptiveAudioServer → MQTT → RPi players

