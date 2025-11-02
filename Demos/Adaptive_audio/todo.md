## Current features of ```adaptive_audio_controller.py```:
[x] takes in mqtt logs from ```ServerBringUp.py``` but also prints all in terminal
[x] tracks whether user is in 'front' or 'back' of room, and plays to the correct pair
[x] 'back' speaker pair pans audio correctly (further stereo speaker gets louder)

## Implementation to test next:
[] rm all live logs terminal print

## Todo
[] 'front' speaker currently does 'follow me audio' rather than stereo panning (further stereo speaker gets softer instead of louder)
[] check if playing stereo music 
[] increase volume
[] try other audio tracks