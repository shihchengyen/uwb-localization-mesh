# 🎵 Synchronized Audio Panning System

This system provides synchronized audio panning across multiple Raspberry Pi speakers controlled by a laptop via MQTT.

## 🏗️ System Architecture

```
Laptop (MQTT Publisher)
    ↓ MQTT Commands
MQTT Broker (Mosquitto)
    ↓ MQTT Commands  
RPi 1 (Left Speaker)    RPi 2 (Right Speaker)
```

## 📋 Components

### 1. **Laptop Controller** (`audio_controller_laptop.py`)
- Publishes MQTT commands with global timing
- Keyboard controls: `s` (start), `a` (left), `d` (right), `q` (quit)
- 500ms delay from keyboard press to execution
- Tracks volume levels for each RPi

### 2. **RPi Audio Players** (`audio_player_rpi.py`)
- Subscribe to MQTT commands
- Execute commands at synchronized global times
- Volume control based on RPi ID and command:
  - **RPi 1 (Left)**: Left commands increase volume, Right commands decrease
  - **RPi 2 (Right)**: Left commands decrease volume, Right commands increase

## 🚀 Setup Instructions

### 📋 **Prerequisites**
- Laptop with Python 3.7+
- 2x Raspberry Pi 4s with Python 3.7+
- All devices on same network
- MQTT broker (mosquitto) running on laptop

---

### 1️⃣ **Configure Network Settings**

**Edit both scripts to match your network:**

**In `synchronized_audio_controller_laptop.py` (lines 21-24):**
```python
# ====== NETWORK CONFIGURATION ======
# DEFAULT_BROKER_IP = "192.168.1.100"  # Your laptop's IP address
DEFAULT_BROKER_IP = "172.20.20.3"  # MSI's ip addr on iphone hotspot
DEFAULT_BROKER_PORT = 1884
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"
```

**In `synchronized_audio_player_rpi.py` (lines 23-26):**
```python
# ====== NETWORK CONFIGURATION ======
# DEFAULT_BROKER_IP = "192.168.1.100"  # Your laptop's IP address
DEFAULT_BROKER_IP = "172.20.20.3"  # MSI's ip addr on iphone hotspot
DEFAULT_BROKER_PORT = 1884
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"
```

---

### 2️⃣ **Laptop Setup**

1. **Install dependencies:**
   ```bash
   uv add pyserial pygame
   ```

2. **Start MQTT broker:**
   ```bash
   # Option A: If mosquitto is installed
   mosquitto -p 1884
   
   # Option B: If using Docker
   docker run -it -p 1884:1884 eclipse-mosquitto
   
   # Option C: If using systemd service
   sudo systemctl start mosquitto
   ```

3. **Find your laptop's IP address:**
   ```bash
   # Windows
   ipconfig
   
   # macOS/Linux
   ifconfig
   # or
   ip addr show
   ```

4. **Run the laptop controller:**
   ```bash
   cd Demos/Adaptive_audio
   python3 synchronized_audio_controller_laptop.py
   ```

---

### 3️⃣ **RPi Setup (repeat for both RPis)**

1. **Install dependencies:**
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-pygame
   pip3 install paho-mqtt
   ```

2. **Copy files to RPi:**
   ```bash
   # Copy the entire Demos/Adaptive_audio folder to each RPi (for current use of playing the particular WAV file.)
   scp -r Demos/Adaptive_audio/ pi@rpi1-ip:/home/pi/
   scp -r Demos/Adaptive_audio/ pi@rpi2-ip:/home/pi/
   ```

3. **Copy WAV file to each RPi:**
   ```bash
   # On each RPi, put your WAV file in the Demos/Adaptive_audio folder
   cp /path/to/your/audio.wav Demos/Adaptive_audio/crazy-carls-brickhouse-tavern.wav
   ```

4. **Test audio on RPi (optional):**
   ```bash
   cd Demos/Adaptive_audio
   python3 test_audio_cards.py
   ```

---

### 4️⃣ **Running the System**

#### **Step 1: Start Laptop Controller**
On your laptop:
```bash
cd Demos/Adaptive_audio
python3 synchronized_audio_controller_laptop.py
```

You should see:
```
✅ Connected to MQTT broker at 192.168.1.100:1884

🎹 Audio Controller Ready!
Keyboard Commands:
  s = START (broadcast to all RPIs)
  a = LEFT (pan left - RPi 1 louder, RPi 2 quieter)
  d = RIGHT (pan right - RPi 1 quieter, RPi 2 louder)
  q = QUIT

Press keys and Enter...
```

#### **Step 2: Start RPi 1 (Left Speaker)**
On RPi 1:
```bash
cd Demos/Adaptive_audio
python3 synchronized_audio_player_rpi.py --id 1
```

You should see:
```
✅ Audio initialized successfully
✅ Connected to MQTT broker at 192.168.1.100:1884
✅ MQTT Connected successfully
📡 Subscribed to: audio/commands/broadcast
📡 Subscribed to: audio/commands/rpi_1
🎵 RPi 1 Audio Player Ready
   WAV file: crazy-carls-brickhouse-tavern.wav
   Position: LEFT
   Initial volume: 20%
```

#### **Step 3: Start RPi 2 (Right Speaker)**
On RPi 2:
```bash
cd Demos/Adaptive_audio
python3 synchronized_audio_player_rpi.py --id 2
```

You should see:
```
✅ Audio initialized successfully
✅ Connected to MQTT broker at 192.168.1.100:1884
✅ MQTT Connected successfully
📡 Subscribed to: audio/commands/broadcast
📡 Subscribed to: audio/commands/rpi_2
🎵 RPi 2 Audio Player Ready
   WAV file: crazy-carls-brickhouse-tavern.wav
   Position: RIGHT
   Initial volume: 20%
```

#### **Step 4: Control Audio**
On the laptop controller, type commands:
- `s` + Enter: Start audio on both speakers
- `q` + Enter: Quit
- `a` + Enter: Pan left (left speaker louder)
- `d` + Enter: Pan right (right speaker louder)


## 🎹 Usage

### **Laptop Controls:**
- `s` + Enter: **START** - Start playing audio on all RPis at 20% volume
- `a` + Enter: **LEFT** - Pan audio left (RPi 1 louder, RPi 2 quieter)
- `d` + Enter: **RIGHT** - Pan audio right (RPi 1 quieter, RPi 2 louder)
- `q` + Enter: **QUIT** - Exit the controller

### **Volume Changes:**
- **Left command**: RPi 1 gets +10%, RPi 2 gets -10%
- **Right command**: RPi 1 gets -15%, RPi 2 gets +15%

### **Timing:**
- All commands execute 500ms after keyboard press
- Commands are synchronized across all RPis using global time

## 🔧 Configuration

### **MQTT Topics:**
- `audio/commands/broadcast` - Commands for all RPis
- `audio/commands/rpi_1` - Commands specifically for RPi 1
- `audio/commands/rpi_2` - Commands specifically for RPi 2

### **Command Format:**
```json
{
  "command": "start|left|right",
  "execute_time": 1234567890.123,
  "global_time": 1234567890.623,
  "delay_ms": 500,
  "timestamp": "2024-01-01T12:00:00Z",
  "rpi_id": 1,
  "target_volume": 30
}
```

## 🐛 Troubleshooting

### **Connection Issues:**
1. **Check network connectivity:**
   ```bash
   ping 192.168.1.100  # Replace with your laptop IP
   ```

2. **Verify MQTT broker is running:**
   ```bash
   # On laptop, check if mosquitto is running
   netstat -an | grep 1884
   # or
   ps aux | grep mosquitto
   ```

3. **Check firewall settings:**
   ```bash
   # Allow MQTT traffic on port 1884
   sudo ufw allow 1884
   ```

### **Audio Issues on RPi:**
1. **Test audio hardware:**
   ```bash
   cd Demos/Adaptive_audio
   python3 test_audio_cards.py
   ```

2. **Check WAV file:**
   ```bash
   ls -la crazy-carls-brickhouse-tavern.wav
   file crazy-carls-brickhouse-tavern.wav
   ```

3. **Test manual audio:**
   ```bash
   python3 loop_player.py
   ```

### **Synchronization Issues:**
1. **Check system clocks:**
   ```bash
   # On all devices
   date
   ```

2. **Adjust timing delay:**
   ```bash
   python3 audio_controller_laptop.py --delay 0.3  # 300ms instead of 500ms
   ```

3. **Monitor execution logs:**
   - Watch for "EXECUTING" messages with timing info
   - Check delay values in logs

### **Volume Issues:**
1. **Check pygame installation:**
   ```bash
   python3 -c "import pygame; print('Pygame OK')"
   ```

2. **Verify ALSA configuration:**
   ```bash
   aplay -l
   amixer scontrols
   ```

## 📋 Quick Reference

### **Start Order:**
1. Start MQTT broker on laptop
2. Start laptop controller
3. Start RPi 1 audio player
4. Start RPi 2 audio player
5. Control from laptop

### **Common Commands:**
```bash
# Laptop
python3 audio_controller_laptop.py

# RPi 1 (Left)
python3 audio_player_rpi.py --id 1

# RPi 2 (Right)  
python3 audio_player_rpi.py --id 2

# Test audio
python3 test_audio_cards.py

# Single RPi loop player
python3 loop_player.py
```

### **Network Configuration:**
Edit these lines in both scripts:
```python
DEFAULT_BROKER_IP = "YOUR_LAPTOP_IP"  # Change this!
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"
```

## 📊 Monitoring

Each component provides detailed logging:
- **Laptop**: Shows sent commands and timing
- **RPi**: Shows received commands, execution timing, and volume changes

## 🔄 Advanced Usage

### **Custom Delay:**
```bash
python3 audio_controller_laptop.py --delay 0.3  # 300ms delay
```

### **Custom WAV File:**
```bash
python3 audio_player_rpi.py --id 1 --wav my_custom_audio.wav
```

### **Network Configuration:**
```bash
python3 audio_controller_laptop.py --broker 192.168.1.100 --port 1884
```

## 🎯 Example Session

1. **Start laptop controller**
2. **Start RPi 1 audio player** (left speaker)
3. **Start RPi 2 audio player** (right speaker)
4. **Press `s`** → Both RPis start playing at 20% volume
5. **Press `a`** → Audio pans left (RPi 1: 30%, RPi 2: 10%)
6. **Press `d`** → Audio pans right (RPi 1: 15%, RPi 2: 25%)
7. **Press `q`** → Stop controller

The system provides smooth, synchronized audio panning across multiple speakers with precise timing control!
