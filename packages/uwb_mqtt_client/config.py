"""
Configuration for UWB MQTT client.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class MQTTConfig:
    """MQTT broker configuration."""
    broker: str
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: str = "uwb_mqtt_client"
    qos: int = 1
    keepalive: int = 60

    # Topic patterns
    base_topic: str = "uwb"

    # Reconnection settings
    reconnect_delay_min: float = 1.0  # Minimum delay between reconnect attempts
    reconnect_delay_max: float = 60.0  # Maximum delay between reconnect attempts


@dataclass(frozen=True)
class UWBConfig:
    """Configuration for UWB hardware interface."""
    serial_port: str = "/dev/ttyUSB0"
    baud_rate: int = 3_000_000
    anchor_id: int = 0
