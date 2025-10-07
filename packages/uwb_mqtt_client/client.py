"""
UWB MQTT Client - Publishes UWB measurements from RPi.
Supports both programmatic API and integrated hardware interface.
"""

import json
import logging
import threading
import time
from typing import Optional, Dict

import paho.mqtt.client as mqtt
import numpy as np

from .config import MQTTConfig
from .uwb_hardware import UWBHardwareInterface, UWBConfig, ProcessedUWBMeasurement

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
    Supports both programmatic API and integrated UWB hardware interface.
    """

    def __init__(
        self,
        config: MQTTConfig,
        phone_node_id: int,
        uwb_config: Optional[UWBConfig] = None
    ):
        """
        Initialize the MQTT client.

        Args:
            config: MQTT configuration
            phone_node_id: Identifier for this phone node
            uwb_config: Optional UWB hardware configuration for integrated hardware interface
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
        self._client.on_publish = self._on_publish

        # Enable automatic reconnect
        self._client.reconnect_delay_set(min_delay=1, max_delay=5)

        # Set auth if provided
        if config.username and config.password:
            self._client.username_pw_set(config.username, config.password)
            
        # Connection status
        self._connected = False
        self._connection_lock = threading.Lock()

        # Reconnection state
        self._reconnect_delay = self.config.reconnect_delay_min
        self._stop_event = threading.Event()

        # UWB hardware interface (optional)
        self.uwb_interface = None
        if uwb_config:
            self.uwb_interface = UWBHardwareInterface(uwb_config)
            self.uwb_interface.set_measurement_callback(self._on_uwb_measurement)
        
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
        """Disconnect from the MQTT broker and stop UWB interface."""
        self._stop_event.set()

        # Stop UWB interface if running
        if self.uwb_interface:
            self.uwb_interface.stop()

        self._client.loop_stop()
        self._client.disconnect()

        logger.info(json.dumps({
            "event": "client_disconnected",
            "phone_node_id": self.phone_node_id
        }))

    def start_uwb_interface(self) -> bool:
        """Start the UWB hardware interface if configured."""
        if not self.uwb_interface:
            logger.warning("No UWB interface configured")
            return False

        return self.uwb_interface.start()

    def _on_uwb_measurement(self, measurement: ProcessedUWBMeasurement):
        """Handle incoming measurements from UWB hardware interface."""
        # Convert to numpy array and publish
        local_vector = np.array(measurement.vector_local)
        timestamp = measurement.timestamp_ns / 1e9  # Convert ns to seconds

        self.publish_measurement(
            anchor_id=measurement.anchor_id,
            local_vector=local_vector,
            timestamp=timestamp
        )
        
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
        
        # Publish to anchor-centric topic (compatible with server)
        topic = f"{self.config.base_topic}/anchor/{anchor_id}/vector"
        self._client.publish(
            topic,
            json.dumps(payload),
            qos=self.config.qos
        )

        logger.debug(json.dumps({
            "event": "measurement_published",
            "anchor_id": anchor_id,
            "topic": topic
        }))
        
    def _on_connect(self, client: mqtt.Client, userdata: Dict, flags: Dict, rc: int):
        """Handle successful connection."""
        if rc == 0:
            with self._connection_lock:
                self._connected = True
                self._reconnect_delay = self.config.reconnect_delay_min
            
            logger.info(json.dumps({
                "event": "mqtt_connected",
                "phone_node_id": self.phone_node_id,
                "qos": self.config.qos
            }))
        else:
            with self._connection_lock:
                self._connected = False
            
            logger.error(json.dumps({
                "event": "mqtt_connect_failed",
                "rc": rc,
                "reason": mqtt.connack_string(rc)
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
