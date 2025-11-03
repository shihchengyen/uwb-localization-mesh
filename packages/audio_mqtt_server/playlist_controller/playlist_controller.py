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

    def update_playlist_based_on_position(self, user_position: np.ndarray):
        # takes in user position and updates the playlist based on the position 
        # user_position is a numpy array [x, y, z] in cm (current stub implementation)
        if user_position[1] > 300:
            # shuffle the playlist2
            random.shuffle(self.playlist2)
            return self.playlist2
        else:
            random.shuffle(self.playlist1)
            return self.playlist1
        
