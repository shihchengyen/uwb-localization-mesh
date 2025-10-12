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
    qos: int = 0  # Changed to QoS 0 for fire-and-forget (no acks needed)
    # keepalive: int = 10  # Reduced keepalive to detect disconnects faster
    keepalive: int = 60  # Increased keepalive for better stability when testing with hotspot 

    # Topic patterns
    base_topic: str = "uwb"

    # Reconnection settings
    reconnect_delay_min: float = 0.1  # Faster initial reconnect
    reconnect_delay_max: float = 5.0   # Cap max delay at 5 seconds


@dataclass(frozen=True)
class UWBConfig:
    """Configuration for UWB hardware interface."""
    serial_port: str = "/dev/ttyUSB0"
    baud_rate: int = 3_000_000
    anchor_id: int = 0
