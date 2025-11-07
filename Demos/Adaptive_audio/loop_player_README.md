# 🎧 Raspberry Pi WAV Loop Player (Keyboard Volume Control)

This script continuously plays the fixed `.wav` audio file u saved, on the Raspberry Pi 4’s **3.5 mm AUX jack**,  
and lets you control playback volume in real time using your keyboard.

---

## 🧩 Features

- Plays a `.wav` file in an infinite loop  
- Uses Raspberry Pi’s built-in 3.5 mm analog audio output  
- Keyboard controls:  
  - `a` → decrease volume by 15 %  
  - `d` → increase volume by 15 %  
  - `q` → quit playback  
- Default starting volume: **50 %**  
- Built-in volume control via pygame (no system permissions needed)

---

## ⚙️ Setup Instructions

### 1️⃣ Enable Headphone Jack Audio Output (Raspberry Pi 4)

**Option A: Use raspi-config (recommended)**
```bash
sudo raspi-config
# Navigate to: Advanced Options → Audio → Force 3.5mm jack
```

**Option B: Manual setup (if needed):**
```bash
# Check current audio output
aplay -l

# You should see card 2: Headphones [bcm2835 Headphones]
# This is your 3.5mm jack - the script is configured to use this
```

**For Raspberry Pi 4 with multiple audio outputs:**
The script automatically uses **card 2 (Headphones)** which is your 3.5mm jack. If you have multiple audio devices, this ensures it uses the correct one.

### 2️⃣ Install Dependencies

Update your system and install required packages:
```bash
sudo apt-get update
sudo apt-get install -y python3-pygame alsa-utils
```

### 4️⃣ RUN the Player from the right directory:
```bash
python3 loop_player.py
```

---

**Troubleshooting:**

1. **Test which audio card works:**
   ```bash
   python3 test_audio_simple.py
   ```

2. **If no sound plays:**
   - Make sure your WAV file is in the parent directory
   - Check that pygame is installed: `sudo apt install python3-pygame`
   - Try different audio cards manually:
     ```bash
     ALSA_CARD=0 python3 loop_player.py  # HDMI audio
     ALSA_CARD=2 python3 loop_player.py  # 3.5mm jack (default)
     ```

3. **Full audio diagnosis:**
   ```bash
   python3 audio_setup_troubleshoot.py
   ```

4. **If still having issues:**
   ```bash
   sudo reboot
   # Then test again
   ```

To stop the program from a frozen terminal, press Ctrl + C or type reset.


---

Thats it cuz it's just testing this segment before porting over to adaptive audio application.
