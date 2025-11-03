"""
Object that controls the playlist of songs for the audio server.
"""

import numpy as np
import random

class PlaylistController:
    def __init__(self):
        self.playlist1 = []
        self.playlist2 = []
        self.playlist3 = []
        self.playlist4 = []
        self.playlist5 = []

    def get_playlist(self, playlist_number: int):
        """Returns the shuffled playlist by number (1-5)."""
        if playlist_number == 1:
            random.shuffle(self.playlist1)
            return self.playlist1
        elif playlist_number == 2:
            random.shuffle(self.playlist2)
            return self.playlist2
        elif playlist_number == 3:
            random.shuffle(self.playlist3)
            return self.playlist3
        elif playlist_number == 4:
            random.shuffle(self.playlist4)
            return self.playlist4
        elif playlist_number == 5:
            random.shuffle(self.playlist5)
            return self.playlist5
        else:
            # Default to playlist 1 if invalid number
            random.shuffle(self.playlist1)
            return self.playlist1

    def update_queue_with_random_song(self, playlist: list[str]):
        """
        Queues a random song from combination of all playlists
        """
        combined_playlist = self.playlist1 + self.playlist2 + self.playlist3 + self.playlist4 + self.playlist5
        random.shuffle(combined_playlist)
        return combined_playlist