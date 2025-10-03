"""
Configuration for UWB MQTT server.
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
    client_id: str = "uwb_mqtt_server"
    qos: int = 1
    keepalive: int = 60
    
    # Topic patterns
    base_topic: str = "uwb"
    measurement_topic: str = "uwb/anchor/+/vector"  # + is anchor_id wildcard (anchor-centric architecture)
    
    # Processing settings
    window_size_seconds: float = 1.0  # Default 1s sliding window
