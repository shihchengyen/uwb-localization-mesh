"""
UWB MQTT Server - Pure message handler that emits measurements via callbacks.
No state management or side effects.
"""

import json
import logging
import threading
import time
from typing import Dict, Callable, Any

import paho.mqtt.client as mqtt
import numpy as np

from packages.datatypes.datatypes import Measurement
from .config import MQTTConfig

# Setup JSON logging
logging.basicConfig(
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class UWBMQTTServer:
    """
    Pure MQTT server for UWB measurements.
    Only handles MQTT connection and message parsing.
    Emits measurements via callback without maintaining state.
    """
    
    def __init__(
        self,
        config: MQTTConfig,
        on_measurement: Callable[[Measurement], None]
    ):
        """
        Initialize the MQTT server.
        
        Args:
            config: MQTT configuration
            on_measurement: Callback for new measurements
                          Called with each new Measurement object
        """
        self.config = config
        self.on_measurement = on_measurement
        
        # MQTT client with unique ID to prevent duplicate connections
        import uuid
        unique_id = str(uuid.uuid4())
        self._client = mqtt.Client(
            client_id=f"{config.client_id}_{unique_id}",
            userdata={'server': self},
            protocol=mqtt.MQTTv311,
            clean_session=True
        )
        
        # Set callbacks
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
        
        # Enable automatic reconnect
        self._client.reconnect_delay_set(min_delay=1, max_delay=5)
        
        # Set auth if provided
        if config.username and config.password:
            self._client.username_pw_set(config.username, config.password)
            
        # Connection status
        self._connected = False
        self._connection_lock = threading.Lock()
            
    def start(self):
        """Start the MQTT client."""
        try:
            # Set longer timeout for initial connection
            self._client._connect_timeout = 10.0  # 10 seconds
            self._client.connect(
                self.config.broker,
                self.config.port,
                self.config.keepalive
            )
            self._client.loop_start()
            
            logger.info(json.dumps({
                "event": "server_started",
                "broker": self.config.broker,
                "port": self.config.port
            }))
            
        except Exception as e:
            logger.error(json.dumps({
                "event": "start_failed",
                "error": str(e)
            }))
            raise
            
    def stop(self):
        """Stop the MQTT client."""
        self._client.loop_stop()
        self._client.disconnect()
        
        logger.info(json.dumps({
            "event": "server_stopped"
        }))
        
    def _on_connect(self, client: mqtt.Client, userdata: Dict, flags: Dict, rc: int):
        """Handle MQTT connection."""
        if rc == 0:
            with self._connection_lock:
                if self._connected:
                    # Already connected, don't subscribe again
                    return
                self._connected = True
            
            # Subscribe to all anchor vectors
            topic = "uwb/anchor/+/vector"  # + is wildcard for anchor_id
            client.subscribe(topic, qos=self.config.qos)
            
            logger.info(json.dumps({
                "event": "mqtt_connected",
                "topic": topic,
                "broker": self.config.broker,
                "qos": self.config.qos,
                "client_id": client._client_id.decode('utf-8')
            }))
        else:
            with self._connection_lock:
                self._connected = False
            
            logger.error(json.dumps({
                "event": "mqtt_connect_failed",
                "rc": rc,
                "reason": mqtt.connack_string(rc),
                "client_id": client._client_id.decode('utf-8')
            }))
            
    def _on_disconnect(self, client: mqtt.Client, userdata: Dict, rc: int):
        """Handle MQTT disconnection."""
        logger.warning(json.dumps({
            "event": "mqtt_disconnected",
            "rc": rc
        }))
        
    def _on_message(self, client: mqtt.Client, userdata: Dict, msg: mqtt.MQTTMessage):
        """Parse message and emit via callback."""
        try:
            # Parse topic to get anchor_id (format: uwb/anchor/{anchor_id}/vector)
            parts = msg.topic.split('/')
            if len(parts) < 4 or parts[1] != 'anchor' or parts[3] != 'vector':
                raise ValueError(f"Invalid topic format: {msg.topic}. Expected: uwb/anchor/{{anchor_id}}/vector")
            anchor_id = int(parts[2])

            # Parse payload (anchor publishes measurements about the phone)
            payload = json.loads(msg.payload.decode('utf-8'))

            # Convert timestamp from nanoseconds to seconds if present
            timestamp = time.time()  # default fallback
            if 't_unix_ns' in payload:
                timestamp = payload['t_unix_ns'] / 1e9  # nanoseconds to seconds
            elif 'timestamp' in payload:
                timestamp = payload['timestamp']

            # For single-phone setup, phone_node_id is always 0
            phone_node_id = 0

            measurement = Measurement(
                timestamp=timestamp,
                anchor_id=anchor_id,
                phone_node_id=phone_node_id,
                local_vector=np.array([
                    payload['vector_local']['x'],
                    payload['vector_local']['y'],
                    payload['vector_local']['z']
                ])
            )

            # Emit via callback
            self.on_measurement(measurement)

            logger.debug(json.dumps({
                "event": "measurement_received",
                "phone_node_id": phone_node_id,
                "anchor_id": measurement.anchor_id,
                "topic": msg.topic
            }))

        except Exception as e:
            logger.error(json.dumps({
                "event": "message_processing_failed",
                "error": str(e),
                "topic": msg.topic,
                "payload_preview": msg.payload.decode('utf-8')[:200] + "..." if len(msg.payload) > 200 else msg.payload.decode('utf-8')
            }))