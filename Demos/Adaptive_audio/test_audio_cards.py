#!/usr/bin/env python3
"""
Simple audio test for Raspberry Pi 4 - tests each audio card
"""

import os
import time

def test_alsa_card(card_num):
    """Test if we can play audio on a specific ALSA card."""
    print(f"\n🧪 Testing ALSA Card {card_num}...")
    
    # Set environment for this card
    os.environ["SDL_AUDIODRIVER"] = "alsa"
    os.environ["ALSA_CARD"] = str(card_num)
    
    try:
        import pygame
        
        # Initialize pygame mixer
        pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=512)
        pygame.mixer.init()
        
        print(f"   ✅ Card {card_num}: Pygame initialized successfully")
        
        # Generate a simple test tone
        pygame.mixer.music.load("/usr/share/sounds/alsa/Front_Left.wav")
        pygame.mixer.music.play()
        
        # Let it play for 1 second
        time.sleep(1)
        
        pygame.mixer.music.stop()
        pygame.mixer.quit()
        
        print(f"   ✅ Card {card_num}: Audio playback test PASSED")
        return True
        
    except Exception as e:
        print(f"   ❌ Card {card_num}: Audio test FAILED - {e}")
        return False


def main():
    print("🎧 Simple Audio Card Test for Raspberry Pi 4")
    print("=" * 50)
    
    # Test each available card
    cards_to_test = [0, 1, 2]  # Based on your aplay -l output
    working_cards = []
    
    for card in cards_to_test:
        if test_alsa_card(card):
            working_cards.append(card)
    
    print(f"\n📊 Results:")
    print(f"   Working cards: {working_cards}")
    
    if 2 in working_cards:
        print(f"\n✅ SUCCESS: Card 2 (Headphones) is working!")
        print(f"   This is the 3.5mm jack - your loop_player should work.")
    elif working_cards:
        print(f"\n⚠️  WARNING: Card 2 not working, but other cards are.")
        print(f"   Try using card {working_cards[0]} instead.")
    else:
        print(f"\n❌ PROBLEM: No audio cards are working.")
        print(f"   Check your audio setup and pygame installation.")
    
    print(f"\n💡 To test manually:")
    for card in working_cards:
        print(f"   ALSA_CARD={card} python3 loop_player.py")


if __name__ == "__main__":
    main()
