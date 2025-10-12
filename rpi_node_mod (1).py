#!/usr/bin/env python3
"""
UWB UART → MQTT JSON publisher (RPi)

Reads Dist/m, Azi/deg, Elev/deg from 2BP UART,
converts to Cartesian vector (x,y,z), and publishes to MQTT topics.

Coordinate convention:
- Azimuth θ: angle in XY-plane from +X toward +Y (CCW).
- Elevation φ: angle from horizon (XY-plane) upward (-Z).   

legend:
  x: forward (anchor normal)
  y: left
  z: up     

dependencies: pyserial, paho-mqtt
  sudo apt-get install -y python3-serial 
  pip3 install paho-mqtt
"""

import os, re, json, time, math, serial, threading, socket
from datetime import datetime
import paho.mqtt.client as mqtt

# ====== CONFIG ======
# Serial Config
SERIAL_PORT = "/dev/ttyUSB0"
BAUD        = 3_000_000

# MQTT Config
MQTT_BROKER = "localhost"  # Change to your MQTT broker IP/hostname
MQTT_PORT = 1884
MQTT_USERNAME = None  # Set if authentication required
MQTT_PASSWORD = None  # Set if authentication required

ANCHOR_ID = 0 #Set as 0,1 ,2,3 depending on requirement
try:
    MQTT_CLIENT_ID = socket.gethostname()
except Exception as e:
    MQTT_CLIENT_ID = "uwb_publisher"

# MQTT Topics
MQTT_BASE_TOPIC = "uwb"  # Base topic, will be: uwb/anchor/{id}/vector
MQTT_QOS = 0  # 0=at most once, 1=at least once, 2=exactly once

# Data Config
INCLUDE_RAW   = True
INCLUDE_LOCAL = True  # keep local vector for debugging/PGO
INCLUDE_GLOBAL= True

# Optional: Still save to files for backup/debugging
SAVE_TO_FILES = False
FILE_MAX_SECONDS = 1.0
FILE_MAX_SAMPLES = 200
OUT_DIR = "./uwb_json"

# Connection monitoring
MQTT_KEEPALIVE = 60
RECONNECT_DELAY = 5  # seconds
# ====== END CONFIG ======

# Per-anchor orientation (degrees). 
# yaw: CCW about +Z from global +X; pitch: about +Y; roll: about +X.
ANCHOR_POSE = {
    # id : (yaw_deg, pitch_deg, roll_deg)
    0: (  45.0, 0.0, 0.0),   # example: facing 45° toward room center
    1: ( 135.0, 0.0, 0.0),
    2: (-135.0, 0.0, 0.0),
    3: ( -45.0, 0.0, 0.0),
    # add more as needed
}

# RegEx, uwb data
re_dist  = re.compile(r"TWR\[(\d+)\]\.distance\s*:\s*([-\d.]+)")
re_azimu = re.compile(r"TWR\[(\d+)\]\.aoa_azimuth\s*:\s*([-\d.]+)")
re_elev  = re.compile(r"TWR\[(\d+)\]\.aoa_elevation\s*:\s*([-\d.]+)")

class MQTTPublisher:
    def __init__(self):
        self.client = mqtt.Client(client_id=MQTT_CLIENT_ID)
        self.connected = False
        self.connect_lock = threading.Lock()
        
        # Set up callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_publish = self.on_publish
        
        # Set credentials if provided
        if MQTT_USERNAME and MQTT_PASSWORD:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            print(f"✓ Connected to MQTT broker {MQTT_BROKER}:{MQTT_PORT}")
        else:
            self.connected = False
            print(f"✗ Failed to connect to MQTT broker. Code: {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        self.connected = False
        print("✗ Disconnected from MQTT broker")
        if rc != 0:
            print("Unexpected disconnection. Will attempt to reconnect...")
    
    def on_publish(self, client, userdata, mid):
        # Optional: Track successful publishes
        pass
    
    def connect(self):
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            self.client.loop_start()  # Start background thread for network loop
            
            # Wait for connection with timeout
            timeout = 10
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            return self.connected
        except Exception as e:
            print(f"MQTT connection error: {e}")
            return False
    
    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
    
    def publish_vector(self, anchor_id, sample_data):
        if not self.connected:
            print(f"⚠ MQTT not connected, skipping publish for anchor {anchor_id}")
            return False
        
        topic = f"{MQTT_BASE_TOPIC}/anchor/{anchor_id}/vector"
        payload = json.dumps(sample_data, separators=(",", ":"))
        
        try:
            result = self.client.publish(topic, payload, qos=MQTT_QOS)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"📡 Published anchor {anchor_id} → {topic}")
                return True
            else:
                print(f"✗ Publish failed for anchor {anchor_id}, rc: {result.rc}")
                return False
        except Exception as e:
            print(f"✗ Publish error for anchor {anchor_id}: {e}")
            return False
    
    def publish_status(self, status_msg):
        """Publish system status/health messages"""
        if not self.connected:
            return False
        
        topic = f"{MQTT_BASE_TOPIC}/status"
        payload = json.dumps({
            "timestamp": time.time_ns(),
            "message": status_msg,
            "client_id": MQTT_CLIENT_ID
        }, separators=(",", ":"))
        
        try:
            self.client.publish(topic, payload, qos=1)  # Use QoS 1 for status
            return True
        except Exception as e:
            print(f"Status publish error: {e}")
            return False

def deg2rad(d): return d * math.pi / 180.0

def r_local_from_az_el(dist_m: float, az_deg: float, el_deg: float):
    """
    convention:
      +az = right, -az = left; 0 = forward (board normal)
      +el = down,  -el = up;   0 = horizontal
    local axes: x=forward, y=left, z=up
    """
    th = deg2rad(az_deg)
    ph = deg2rad(el_deg)
    cph, sph = math.cos(ph), math.sin(ph)
    cth, sth = math.cos(th), math.sin(th)

    x = dist_m * cph * cth
    y = -dist_m * cph * sth   # minus bc +az is to the RIGHT
    z = -dist_m * sph         # minus bc +el is DOWN
    return (x, y, z)

def rot_zyx(yaw_deg: float, pitch_deg: float, roll_deg: float):
    """R = Rz(yaw) @ Ry(pitch) @ Rx(roll), all degrees, right-handed, + angles are CCW."""
    cy, sy = math.cos(deg2rad(yaw_deg)),   math.sin(deg2rad(yaw_deg))
    cp, sp = math.cos(deg2rad(pitch_deg)), math.sin(deg2rad(pitch_deg))
    cr, sr = math.cos(deg2rad(roll_deg)),  math.sin(deg2rad(roll_deg))
    # Rz
    r00 = cy;  r01 = -sy; r02 = 0.0
    r10 = sy;  r11 =  cy; r12 = 0.0
    r20 = 0.0; r21 = 0.0; r22 = 1.0
    # Ry
    RzRy = (
        r00*cp + r02*sp,     r01*cp + r02*0,     -r00*sp + r02*cp,
        r10*cp + r12*sp,     r11*cp + r12*0,     -r10*sp + r12*cp,
        r20*cp + r22*sp,     r21*cp + r22*0,     -r20*sp + r22*cp,
    )
    a00,a01,a02,a10,a11,a12,a20,a21,a22 = RzRy
    # Rx
    b00 = a00
    b01 = a01*cr - a02*sr
    b02 = a01*sr + a02*cr
    b10 = a10
    b11 = a11*cr - a12*sr
    b12 = a11*sr + a12*cr
    b20 = a20
    b21 = a21*cr - a22*sr
    b22 = a21*sr + a22*cr
    return ((b00,b01,b02),(b10,b11,b12),(b20,b21,b22))

def apply_R(R, v):
    return (
        R[0][0]*v[0] + R[0][1]*v[1] + R[0][2]*v[2],
        R[1][0]*v[0] + R[1][1]*v[1] + R[1][2]*v[2],
        R[2][0]*v[0] + R[2][1]*v[1] + R[2][2]*v[2],
    )

# File handling functions (optional)
def new_filename():
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return os.path.join(OUT_DIR, f"uwb_vectors_{ts}Z.json")

def ensure_dir(p): 
    os.makedirs(p, exist_ok=True)

def main():
    # Initialize MQTT
    mqtt_pub = MQTTPublisher()
    if not mqtt_pub.connect():
        print("Failed to connect to MQTT broker. Exiting...")
        return
    
    # Publish startup status
    mqtt_pub.publish_status("UWB publisher started")
    
    # Optional file saving
    if SAVE_TO_FILES:
        ensure_dir(OUT_DIR)
        buf = []
        file_start = time.time()
        fname = new_filename()
    
    # Serial setup
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD)
        print(f"✓ UART open on {SERIAL_PORT} @ {BAUD} baud")
    except Exception as e:
        print(f"✗ Failed to open serial port: {e}")
        mqtt_pub.publish_status(f"Serial port error: {e}")
        return
    
    print("Converting (r,az,el) → vectors → MQTT…")

    # per-anchor partials
    pending = {}  # id -> {"r":..., "az":..., "el":...}

    # precompute rotation matrices
    R_anchor = {aid: rot_zyx(*pose) for aid, pose in ANCHOR_POSE.items()}

    # Stats
    publish_count = 0
    last_stats_time = time.time()

    def flush_file():
        nonlocal buf, file_start, fname
        if not SAVE_TO_FILES or not buf: 
            return
        tmp = fname + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(buf, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, fname)
        print(f"📄 Wrote {len(buf)} samples → {fname}")
        buf = []
        file_start = time.time()
        fname = new_filename()

    try:
        while True:
            # Check MQTT connection periodically
            if not mqtt_pub.connected:
                print("⚠ MQTT connection lost, attempting reconnect...")
                mqtt_pub.connect()
            
            # Read serial data
            try:
                s = ser.readline().decode(errors="ignore").strip()
            except Exception as e:
                print(f"Serial read error: {e}")
                time.sleep(0.1)
                continue

            # Parse distance
            m = re_dist.search(s)
            if m:
                aid, val = int(m.group(1)), float(m.group(2))
                st = pending.setdefault(aid, {})
                st["r"] = val

            # Parse azimuth
            m = re_azimu.search(s)
            if m:
                aid, val = int(m.group(1)), float(m.group(2))
                st = pending.setdefault(aid, {})
                st["az"] = val

            # Parse elevation
            m = re_elev.search(s)
            if m:
                aid, val = int(m.group(1)), float(m.group(2))
                st = pending.setdefault(aid, {})
                st["el"] = val

            # Process complete triples
            to_clear = []
            for aid, st in pending.items():
                if all(k in st for k in ("r","az","el")):
                    r, az, el = st["r"], st["az"], st["el"]

                    v_local = r_local_from_az_el(r, az, el)

                    # rotate to global if pose known, else pass-through
                    R = R_anchor.get(aid, ((1,0,0),(0,1,0),(0,0,1)))
                    v_global = apply_R(R, v_local)

                    sample = {
                        "t_unix_ns": time.time_ns(),
                        "anchor_id": aid,
                    }
                    if INCLUDE_LOCAL:
                        sample["vector_local"]  = {"x": v_local[0],  "y": v_local[1],  "z": v_local[2]}
                    if INCLUDE_GLOBAL:
                        sample["vector_global"] = {"x": v_global[0], "y": v_global[1], "z": v_global[2]}
                    if INCLUDE_RAW:
                        sample["raw"] = {
                            "distance_m": r,
                            "azimuth_deg": az,
                            "elevation_deg": el,
                        }
                    
                    # Publish to MQTT
                    if mqtt_pub.publish_vector(ANCHOR_ID, sample):
                        publish_count += 1
                    
                    # Optional: save to file
                    if SAVE_TO_FILES:
                        buf.append(sample)
                    
                    to_clear.append(aid)

            for aid in to_clear:
                pending.pop(aid, None)

            # Optional file flush
            if SAVE_TO_FILES and ((time.time() - file_start) >= FILE_MAX_SECONDS or len(buf) >= FILE_MAX_SAMPLES):
                flush_file()
            
            # Periodic stats
            if time.time() - last_stats_time >= 30:  # Every 30 seconds
                print(f"📊 Published {publish_count} vectors in last 30s")
                mqtt_pub.publish_status(f"Published {publish_count} vectors in last 30s")
                publish_count = 0
                last_stats_time = time.time()

    except KeyboardInterrupt:
        print("Stopping…")
        mqtt_pub.publish_status("UWB publisher stopped")
    except Exception as e:
        print(f"Unexpected error: {e}")
        mqtt_pub.publish_status(f"Error: {e}")
    finally:
        try: 
            if SAVE_TO_FILES:
                flush_file()
        except Exception as e: 
            print("Flush error:", e)
        
        ser.close()
        mqtt_pub.disconnect()
        print("✓ Cleanup completed")

if __name__ == "__main__":
    main()