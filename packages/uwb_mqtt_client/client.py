"""
UWB MQTT Client - Publishes UWB measurements from RPi.
"""

import json
import logging
import threading
import time
from typing import Optional

import paho.mqtt.client as mqtt
import numpy as np

from .config import MQTTConfig

# Setup JSON logging
logging.basicConfig(
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class UWBMQTTClient:
    """
    MQTT client for publishing UWB measurements.
    Handles reconnection and backoff.
    """
    
    def __init__(
        self,
        config: MQTTConfig,
        phone_node_id: int
    ):
        """
        Initialize the MQTT client.
        
        Args:
            config: MQTT configuration
            phone_node_id: Identifier for this phone node
        """
        self.config = config
        self.phone_node_id = phone_node_id
        
        # MQTT client
        self._client = mqtt.Client(
            client_id=f"{config.client_id}_{phone_node_id}",
            userdata={'client': self},
            protocol=mqtt.MQTTv311
        )
        
        # Set callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        
        # Set auth if provided
        if config.username and config.password:
            self._client.username_pw_set(config.username, config.password)
            
        # Reconnection state
        self._reconnect_delay = self.config.reconnect_delay_min
        self._stop_event = threading.Event()
        
    def connect(self):
        """Connect to the MQTT broker."""
        try:
            self._client.connect(
                self.config.broker,
                self.config.port,
                self.config.keepalive
            )
            self._client.loop_start()
            
            logger.info(json.dumps({
                "event": "client_connected",
                "phone_node_id": self.phone_node_id,
                "broker": self.config.broker
            }))
            
        except Exception as e:
            logger.error(json.dumps({
                "event": "connect_failed",
                "error": str(e)
            }))
            raise
            
    def disconnect(self):
        """Disconnect from the MQTT broker."""
        self._stop_event.set()
        self._client.loop_stop()
        self._client.disconnect()
        
        logger.info(json.dumps({
            "event": "client_disconnected",
            "phone_node_id": self.phone_node_id
        }))
        
    def publish_measurement(
        self,
        anchor_id: int,
        local_vector: np.ndarray,
        timestamp: Optional[float] = None
    ):
        """
        Publish a UWB measurement.
        
        Args:
            anchor_id: Identifier for the anchor
            local_vector: [x, y, z] vector in local coordinates (cm)
            timestamp: Optional timestamp (if not provided, uses current time)
        """
        if local_vector.shape != (3,):
            raise ValueError(f"local_vector must be shape (3,), got {local_vector.shape}")
            
        # Create payload
        payload = {
            "timestamp": timestamp or time.time(),
            "anchor_id": anchor_id,
            "vector_local": {
                "x": float(local_vector[0]),
                "y": float(local_vector[1]),
                "z": float(local_vector[2])
            }
        }
        
        # Publish
        topic = f"{self.config.base_topic}/{self.phone_node_id}/measurements"
        self._client.publish(
            topic,
            json.dumps(payload),
            qos=self.config.qos
        )
        
        logger.debug(json.dumps({
            "event": "measurement_published",
            "phone_node_id": self.phone_node_id,
            "anchor_id": anchor_id
        }))
        
    def _on_connect(self, client: mqtt.Client, userdata: Dict, flags: Dict, rc: int):
        """Handle successful connection."""
        if rc == 0:
            # Reset reconnection delay on successful connect
            self._reconnect_delay = self.config.reconnect_delay_min
            
            logger.info(json.dumps({
                "event": "mqtt_connected",
                "phone_node_id": self.phone_node_id
            }))
        else:
            logger.error(json.dumps({
                "event": "mqtt_connect_failed",
                "rc": rc
            }))
            
    def _on_disconnect(self, client: mqtt.Client, userdata: Dict, rc: int):
        """Handle disconnection with exponential backoff."""
        logger.warning(json.dumps({
            "event": "mqtt_disconnected",
            "rc": rc
        }))
        
        # Only try to reconnect if we haven't been explicitly stopped
        if not self._stop_event.is_set():
            # Exponential backoff
            time.sleep(self._reconnect_delay)
            self._reconnect_delay = min(
                self._reconnect_delay * 2,
                self.config.reconnect_delay_max
            )
            
            try:
                client.reconnect()
            except Exception as e:
                logger.error(json.dumps({
                    "event": "reconnect_failed",
                    "error": str(e)
                }))
