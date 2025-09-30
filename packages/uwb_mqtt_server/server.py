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
        
        # MQTT client
        self._client = mqtt.Client(
            client_id=config.client_id,
            userdata={'server': self},
            protocol=mqtt.MQTTv311
        )
        
        # Set callbacks
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
        
        # Set auth if provided
        if config.username and config.password:
            self._client.username_pw_set(config.username, config.password)
            
    def start(self):
        """Start the MQTT client."""
        try:
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
            client.subscribe(self.config.measurement_topic, qos=self.config.qos)
            logger.info(json.dumps({
                "event": "mqtt_connected",
                "topic": self.config.measurement_topic
            }))
        else:
            logger.error(json.dumps({
                "event": "mqtt_connect_failed",
                "rc": rc
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
            # Parse topic to get phone_node_id
            parts = msg.topic.split('/')
            if len(parts) < 2:
                raise ValueError(f"Invalid topic format: {msg.topic}")
            phone_node_id = int(parts[1])
            
            # Parse payload
            payload = json.loads(msg.payload.decode('utf-8'))
            measurement = Measurement(
                timestamp=payload.get('timestamp', time.time()),
                anchor_id=payload['anchor_id'],
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
                "anchor_id": measurement.anchor_id
            }))
            
        except Exception as e:
            logger.error(json.dumps({
                "event": "message_processing_failed",
                "error": str(e),
                "topic": msg.topic
            }))