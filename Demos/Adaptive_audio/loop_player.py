#!/usr/bin/env python3
import curses
import pathlib
import time
import sys
import os

# ---- config ----
FILENAME = "crazy-carls-brickhouse-tavern.wav"  # in parent folder of this script
STEP = 15                                       # volume step
START_VOL = 50                                  # 0..100
# --------------

def set_pygame_volume(pct):
    """Set pygame mixer volume (0..100%) - no system permissions needed."""
    pct = max(0, min(100, pct))
    volume = pct / 100.0  # pygame uses 0.0 to 1.0
    try:
        import pygame
        pygame.mixer.music.set_volume(volume)
        return True
    except:
        return False

def get_audio_path():
    here = pathlib.Path(__file__).resolve().parent
    return (here.parent / FILENAME).resolve()

def main(stdscr):
    # lazy-import pygame after curses owns the TTY
    # Force pygame to use the 3.5mm headphones jack (card 2)
    os.environ["SDL_AUDIODRIVER"] = "alsa"
    os.environ["ALSA_CARD"] = "2"  # Use card 2 (Headphones)
    import pygame

    # locate file
    audio_path = get_audio_path()
    if not audio_path.exists():
        print(f"File not found: {audio_path}")
        print("Put the WAV in the parent folder of this script, or update FILENAME.")
        sys.exit(1)

    # init audio - use pygame.mixer.music for better looping
    # Specify audio device explicitly for Pi 4
    pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=512)
    pygame.mixer.init()
    pygame.mixer.music.load(str(audio_path))
    pygame.mixer.music.play(-1)  # loop forever

    # start volume
    vol = START_VOL
    set_pygame_volume(vol)

    # curses set up
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(100)  # ms

    def draw():
        stdscr.erase()
        stdscr.addstr(0, 0, "RPi WAV Loop Player (3.5mm jack)")
        stdscr.addstr(2, 0, f"File: {audio_path.name}")
        stdscr.addstr(3, 0, f"Volume: {vol}%   (a = -{STEP}, d = +{STEP})")
        stdscr.addstr(5, 0, "Press q to quit.")
        stdscr.refresh()

    draw()

    # main loop
    while True:
        try:
            key = stdscr.getch()
        except KeyboardInterrupt:
            break

        if key == ord('q'):
            break
        elif key == ord('a'):
            vol = max(0, vol - STEP)
            set_pygame_volume(vol)
            draw()
        elif key == ord('d'):
            vol = min(100, vol + STEP)
            set_pygame_volume(vol)
            draw()

        # keep the loop gentle on CPU
        time.sleep(0.05)

    pygame.mixer.music.stop()
    pygame.mixer.quit()

if __name__ == "__main__":
    curses.wrapper(main)
