#!/usr/bin/env python3
"""
Audio setup troubleshooting script for Raspberry Pi
Helps diagnose audio configuration issues and provides working alternatives.
"""

import subprocess
import sys
import os


def run_command(cmd, description):
    """Run a command and return success/failure with output."""
    print(f"\n🔍 {description}")
    print(f"Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ SUCCESS")
            if result.stdout.strip():
                print(f"Output: {result.stdout.strip()}")
        else:
            print("❌ FAILED")
            if result.stderr.strip():
                print(f"Error: {result.stderr.strip()}")
            if result.stdout.strip():
                print(f"Output: {result.stdout.strip()}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def check_audio_system():
    """Diagnose the audio system configuration."""
    print("🎧 Raspberry Pi Audio System Diagnosis")
    print("=" * 50)
    
    # Check if we're on a Raspberry Pi
    if not os.path.exists('/proc/device-tree/model'):
        print("⚠️  This doesn't appear to be a Raspberry Pi")
        return False
    
    # Read Pi model
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().strip()
        print(f"📱 Raspberry Pi Model: {model}")
    except:
        print("📱 Raspberry Pi Model: Unknown")
    
    # Check audio devices
    print("\n🔍 Checking audio devices...")
    run_command("lsusb | grep -i audio", "USB Audio devices")
    run_command("lsmod | grep snd", "Sound modules loaded")
    
    # Check ALSA
    print("\n🔍 ALSA Audio System:")
    run_command("aplay -l", "ALSA playback devices")
    run_command("arecord -l", "ALSA recording devices")
    
    # Check PulseAudio
    print("\n🔍 PulseAudio (if available):")
    pulse_available = run_command("which pactl", "PulseAudio control available")
    if pulse_available:
        run_command("pactl list short sinks", "PulseAudio sinks")
        run_command("pactl list short sources", "PulseAudio sources")
        run_command("pactl info", "PulseAudio server info")
    
    # Check ALSA mixer controls
    print("\n🔍 ALSA Mixer Controls:")
    run_command("amixer scontrols", "Available mixer controls")
    
    # Check current audio settings
    print("\n🔍 Current Audio Configuration:")
    run_command("amixer sget Master", "Master volume")
    run_command("amixer sget PCM", "PCM volume")
    run_command("amixer sget Headphone", "Headphone volume (if exists)")
    
    # Test pygame audio
    print("\n🔍 Testing Pygame Audio:")
    test_pygame_audio()
    
    return True


def test_pygame_audio():
    """Test if pygame can initialize and play audio."""
    try:
        import pygame
        print("✅ Pygame is available")
        
        # Test pygame mixer initialization
        pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=512)
        pygame.mixer.init()
        print("✅ Pygame mixer initialized successfully")
        
        # Test with different ALSA cards
        for card in [0, 1, 2]:
            print(f"\n🧪 Testing ALSA card {card}:")
            os.environ["ALSA_CARD"] = str(card)
            try:
                pygame.mixer.quit()
                pygame.mixer.init()
                print(f"   ✅ Card {card} works")
            except Exception as e:
                print(f"   ❌ Card {card} failed: {e}")
        
        pygame.mixer.quit()
        return True
        
    except ImportError:
        print("❌ Pygame not installed - run: sudo apt install python3-pygame")
        return False
    except Exception as e:
        print(f"❌ Pygame audio test failed: {e}")
        return False


def suggest_working_commands():
    """Suggest working commands based on the system diagnosis."""
    print("\n💡 Suggested Working Commands")
    print("=" * 50)
    
    print("\n1️⃣ Try these audio setup commands (in order):")
    print("   sudo raspi-config nonint do_audio 1")
    print("   sudo amixer cset numid=3 1")
    print("   sudo alsactl store")
    
    print("\n2️⃣ Alternative PulseAudio setup (if PulseAudio is installed):")
    print("   pactl set-sink-mute @DEFAULT_SINK@ false")
    print("   pactl set-sink-volume @DEFAULT_SINK@ 50%")
    
    print("\n3️⃣ Test audio output:")
    print("   speaker-test -t wav -c 2")
    print("   aplay /usr/share/sounds/alsa/Front_Left.wav")
    
    print("\n4️⃣ Manual volume control:")
    print("   amixer set Master 50%")
    print("   amixer set PCM 50%")
    
    print("\n5️⃣ If nothing works, try:")
    print("   sudo reboot")
    print("   # Then test again after reboot")


def create_working_audio_script():
    """Create a robust audio control script that works with different Pi setups."""
    script_content = '''#!/usr/bin/env python3
"""
Robust audio control for Raspberry Pi - works with different audio setups
"""

import subprocess
import time
import sys


class PiAudioController:
    def __init__(self):
        self.volume_control = self._detect_volume_control()
        
    def _detect_volume_control(self):
        """Detect which volume control method works on this Pi."""
        # Try different volume control methods
        controls_to_try = [
            ("Master", "amixer set Master"),
            ("PCM", "amixer set PCM"), 
            ("Headphone", "amixer set Headphone"),
            ("Speaker", "amixer set Speaker"),
            ("PulseAudio", "pactl set-sink-volume @DEFAULT_SINK@")
        ]
        
        for name, cmd in controls_to_try:
            if self._test_volume_control(cmd):
                print(f"✅ Using {name} for volume control")
                return cmd
        
        print("⚠️  No volume control method found - audio may not work")
        return None
    
    def _test_volume_control(self, cmd):
        """Test if a volume control command works."""
        try:
            result = subprocess.run(f"{cmd} 50%", shell=True, capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def set_volume(self, percentage):
        """Set system volume to percentage (0-100)."""
        if not self.volume_control:
            print("No volume control available")
            return False
            
        try:
            if "pactl" in self.volume_control:
                cmd = f"pactl set-sink-volume @DEFAULT_SINK@ {percentage}%"
            else:
                cmd = f"{self.volume_control} {percentage}%"
                
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def test_audio(self):
        """Test audio output."""
        test_commands = [
            "speaker-test -t wav -c 2 -l 1",
            "aplay /usr/share/sounds/alsa/Front_Left.wav",
            "aplay /usr/share/sounds/alsa/Front_Right.wav"
        ]
        
        for cmd in test_commands:
            print(f"Testing: {cmd}")
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, timeout=3)
                if result.returncode == 0:
                    print("✅ Audio test successful")
                    return True
            except:
                continue
        
        print("❌ No audio test succeeded")
        return False


if __name__ == "__main__":
    controller = PiAudioController()
    
    print("🎧 Raspberry Pi Audio Controller")
    print("Commands: u=up, d=down, t=test, q=quit")
    
    try:
        while True:
            cmd = input("Audio> ").lower().strip()
            
            if cmd == 'q':
                break
            elif cmd == 'u':
                controller.set_volume(75)
                print("Volume: 75%")
            elif cmd == 'd':
                controller.set_volume(25)
                print("Volume: 25%")
            elif cmd == 't':
                controller.test_audio()
            else:
                print("Commands: u=up, d=down, t=test, q=quit")
                
    except KeyboardInterrupt:
        print("\\nGoodbye!")
'''
    
    with open('Demos/Adaptive_audio/working_audio_controller.py', 'w') as f:
        f.write(script_content)
    
    print("\n✅ Created: Demos/Adaptive_audio/working_audio_controller.py")
    print("   Run this script to test and control audio on your Pi")


if __name__ == "__main__":
    if check_audio_system():
        suggest_working_commands()
        create_working_audio_script()
    
    print("\n🔧 Next Steps:")
    print("1. Run the diagnosis above to see what's available")
    print("2. Try the suggested commands")
    print("3. Use the working_audio_controller.py script")
    print("4. If still having issues, try: sudo reboot")
