# trading/bots/hedge_bot/hedge_bot_data_aws_iot.py
# NEXUS AI TRADING SYSTEM - Hedge Bot AWS IoT Integration Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot AWS IoT Integration Module

This module provides comprehensive AWS IoT integration for the NEXUS Hedge Bot
system. It enables secure communication with AWS IoT Core, device management,
and data synchronization.

The module covers:
- AWS IoT Core Integration
- MQTT Communication
- Thing Management
- Shadow Management
- Rules Engine Integration
- Analytics Integration
- Device Monitoring
- Secure Communication
- Data Synchronization
- IoT Analytics
"""

import os
import sys
import json
import logging
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum

# Try to import AWS SDK
try:
    import boto3
    from awsiot import mqtt_connection_builder
    from awscrt import io, mqtt, auth, http
    HAS_AWS_IOT = True
except ImportError:
    HAS_AWS_IOT = False

logger = logging.getLogger(__name__)


# ============================================================
# AWS IOT ENUMS
# ============================================================

class ConnectionState(Enum):
    """Connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class ThingState(Enum):
    """Thing states"""
    ONLINE = "online"
    OFFLINE = "offline"
    UPDATING = "updating"
    ERROR = "error"


@dataclass
class IoTConfig:
    """IoT configuration"""
    endpoint: str
    client_id: str
    thing_name: str
    certificate_path: str
    private_key_path: str
    ca_cert_path: str
    region: str = "us-east-1"
    port: int = 8883
    use_websocket: bool = False
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "endpoint": self.endpoint,
            "client_id": self.client_id,
            "thing_name": self.thing_name,
            "region": self.region,
            "port": self.port,
            "use_websocket": self.use_websocket,
        }


@dataclass
class IoTShadow:
    """IoT shadow data"""
    thing_name: str
    state: Dict[str, Any]
    metadata: Dict[str, Any]
    version: int
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "thing_name": self.thing_name,
            "state": self.state,
            "metadata": self.metadata,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class IoTMessage:
    """IoT message"""
    topic: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    qos: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "topic": self.topic,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "qos": self.qos,
        }


# ============================================================
# AWS IOT ENGINE
# ============================================================

class AWSIoTEngine:
    """
    Comprehensive AWS IoT engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the AWS IoT engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        if not HAS_AWS_IOT:
            logger.warning("AWS IoT libraries not installed")
        
        # IoT Config
        self.iot_config = None
        self._load_config()
        
        # State
        self.mqtt_connection = None
        self.connection_state = ConnectionState.DISCONNECTED
        self.thing_state = ThingState.OFFLINE
        self.subscriptions: Dict[str, Callable] = {}
        self.message_queue: List[IoTMessage] = []
        self.shadow_cache: Dict[str, IoTShadow] = {}
        
        # Threading
        self.is_running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # AWS Clients
        self.iot_client = None
        self.iot_data_client = None
        
        if HAS_AWS_IOT:
            self._init_aws_clients()
        
        logger.info("AWS IoT engine initialized")
    
    # ============================================================
    # INITIALIZATION
    # ============================================================
    
    def _load_config(self) -> None:
        """Load IoT configuration"""
        self.iot_config = IoTConfig(
            endpoint=self.config.get("endpoint", ""),
            client_id=self.config.get("client_id", "nexus-hedge-bot"),
            thing_name=self.config.get("thing_name", "NexusHedgeBot"),
            certificate_path=self.config.get("certificate_path", ""),
            private_key_path=self.config.get("private_key_path", ""),
            ca_cert_path=self.config.get("ca_cert_path", ""),
            region=self.config.get("region", "us-east-1"),
        )
    
    def _init_aws_clients(self) -> None:
        """Initialize AWS clients"""
        try:
            self.iot_client = boto3.client('iot', region_name=self.iot_config.region)
            self.iot_data_client = boto3.client('iot-data', region_name=self.iot_config.region)
            logger.info("AWS IoT clients initialized")
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
    
    # ============================================================
    # CONNECTION MANAGEMENT
    # ============================================================
    
    def connect(self) -> bool:
        """
        Connect to AWS IoT Core
        
        Returns:
            True if connected
        """
        if not HAS_AWS_IOT:
            logger.error("AWS IoT libraries not installed")
            return False
        
        if self.connection_state == ConnectionState.CONNECTED:
            return True
        
        try:
            self.connection_state = ConnectionState.CONNECTING
            
            # Build connection
            self.mqtt_connection = mqtt_connection_builder.mtls_from_path(
                endpoint=self.iot_config.endpoint,
                port=self.iot_config.port,
                cert_filepath=self.iot_config.certificate_path,
                pri_key_filepath=self.iot_config.private_key_path,
                ca_filepath=self.iot_config.ca_cert_path,
                client_id=self.iot_config.client_id,
                clean_session=False,
                keep_alive_secs=30,
            )
            
            # Connect
            connect_future = self.mqtt_connection.connect()
            connect_future.result()
            
            self.connection_state = ConnectionState.CONNECTED
            self.thing_state = ThingState.ONLINE
            
            # Start monitoring
            self._start_monitoring()
            
            logger.info(f"Connected to AWS IoT Core: {self.iot_config.endpoint}")
            return True
            
        except Exception as e:
            self.connection_state = ConnectionState.ERROR
            logger.error(f"Failed to connect: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from AWS IoT Core"""
        if not self.mqtt_connection:
            return
        
        try:
            self.is_running = False
            self.mqtt_connection.disconnect()
            self.connection_state = ConnectionState.DISCONNECTED
            self.thing_state = ThingState.OFFLINE
            logger.info("Disconnected from AWS IoT Core")
        except Exception as e:
            logger.error(f"Failed to disconnect: {e}")
    
    def _start_monitoring(self) -> None:
        """Start monitoring thread"""
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def _monitor_loop(self) -> None:
        """Monitor connection and process messages"""
        while self.is_running:
            try:
                # Process message queue
                if self.message_queue:
                    self._process_messages()
                
                # Check connection
                if self.mqtt_connection:
                    # Check if connected
                    pass
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(5)
    
    # ============================================================
    # MESSAGE PUBLISHING
    # ============================================================
    
    def publish_message(
        self,
        topic: str,
        payload: Dict[str, Any],
        qos: int = 1
    ) -> bool:
        """
        Publish a message
        
        Args:
            topic: MQTT topic
            payload: Message payload
            qos: QoS level
            
        Returns:
            True if published
        """
        if not self.mqtt_connection:
            return False
        
        if self.connection_state != ConnectionState.CONNECTED:
            # Queue message
            self.message_queue.append(IoTMessage(
                topic=topic,
                payload=payload,
                qos=qos
            ))
            return True
        
        try:
            message_json = json.dumps(payload)
            self.mqtt_connection.publish(
                topic=topic,
                payload=message_json,
                qos=mqtt.QoS.AT_LEAST_ONCE if qos == 1 else mqtt.QoS.AT_MOST_ONCE,
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return False
    
    def _process_messages(self) -> None:
        """Process queued messages"""
        while self.message_queue:
            message = self.message_queue.pop(0)
            self.publish_message(message.topic, message.payload, message.qos)
    
    # ============================================================
    # SUBSCRIPTION MANAGEMENT
    # ============================================================
    
    def subscribe(
        self,
        topic: str,
        callback: Callable[[IoTMessage], None],
        qos: int = 1
    ) -> bool:
        """
        Subscribe to a topic
        
        Args:
            topic: MQTT topic
            callback: Message callback
            qos: QoS level
            
        Returns:
            True if subscribed
        """
        if not self.mqtt_connection:
            return False
        
        try:
            # Store subscription
            self.subscriptions[topic] = callback
            
            # Subscribe
            subscribe_future = self.mqtt_connection.subscribe(
                topic=topic,
                qos=mqtt.QoS.AT_LEAST_ONCE if qos == 1 else mqtt.QoS.AT_MOST_ONCE,
                callback=lambda topic, payload: self._on_message(topic, payload)
            )
            subscribe_future.result()
            
            logger.info(f"Subscribed to topic: {topic}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
            return False
    
    def unsubscribe(self, topic: str) -> bool:
        """
        Unsubscribe from a topic
        
        Args:
            topic: MQTT topic
            
        Returns:
            True if unsubscribed
        """
        if not self.mqtt_connection:
            return False
        
        try:
            self.mqtt_connection.unsubscribe(topic=topic)
            if topic in self.subscriptions:
                del self.subscriptions[topic]
            logger.info(f"Unsubscribed from topic: {topic}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unsubscribe: {e}")
            return False
    
    def _on_message(self, topic: str, payload: bytes) -> None:
        """
        Handle incoming message
        
        Args:
            topic: MQTT topic
            payload: Message payload
        """
        try:
            data = json.loads(payload.decode())
            
            message = IoTMessage(
                topic=topic,
                payload=data,
                timestamp=datetime.now(),
            )
            
            # Call callback if exists
            if topic in self.subscriptions:
                self.subscriptions[topic](message)
            
        except Exception as e:
            logger.error(f"Failed to handle message: {e}")
    
    # ============================================================
    # SHADOW MANAGEMENT
    # ============================================================
    
    def update_shadow(
        self,
        state: Dict[str, Any],
        thing_name: Optional[str] = None
    ) -> bool:
        """
        Update thing shadow
        
        Args:
            state: Shadow state
            thing_name: Thing name
            
        Returns:
            True if updated
        """
        if thing_name is None:
            thing_name = self.iot_config.thing_name
        
        try:
            response = self.iot_data_client.update_thing_shadow(
                thingName=thing_name,
                payload=json.dumps({
                    "state": {
                        "reported": state
                    }
                })
            )
            
            # Parse response
            shadow_data = json.loads(response['payload'].read())
            self.shadow_cache[thing_name] = IoTShadow(
                thing_name=thing_name,
                state=shadow_data.get("state", {}),
                metadata=shadow_data.get("metadata", {}),
                version=shadow_data.get("version", 1),
            )
            
            logger.info(f"Updated shadow for {thing_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update shadow: {e}")
            return False
    
    def get_shadow(self, thing_name: Optional[str] = None) -> Optional[IoTShadow]:
        """
        Get thing shadow
        
        Args:
            thing_name: Thing name
            
        Returns:
            IoTShadow or None
        """
        if thing_name is None:
            thing_name = self.iot_config.thing_name
        
        try:
            response = self.iot_data_client.get_thing_shadow(thingName=thing_name)
            shadow_data = json.loads(response['payload'].read())
            
            shadow = IoTShadow(
                thing_name=thing_name,
                state=shadow_data.get("state", {}),
                metadata=shadow_data.get("metadata", {}),
                version=shadow_data.get("version", 1),
            )
            
            self.shadow_cache[thing_name] = shadow
            return shadow
            
        except Exception as e:
            logger.error(f"Failed to get shadow: {e}")
            return None
    
    # ============================================================
    # THING MANAGEMENT
    # ============================================================
    
    def create_thing(self, thing_name: str) -> bool:
        """
        Create a thing
        
        Args:
            thing_name: Thing name
            
        Returns:
            True if created
        """
        try:
            self.iot_client.create_thing(
                thingName=thing_name,
                thingTypeName="NexusBot"
            )
            logger.info(f"Created thing: {thing_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create thing: {e}")
            return False
    
    def delete_thing(self, thing_name: str) -> bool:
        """
        Delete a thing
        
        Args:
            thing_name: Thing name
            
        Returns:
            True if deleted
        """
        try:
            self.iot_client.delete_thing(thingName=thing_name)
            logger.info(f"Deleted thing: {thing_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete thing: {e}")
            return False
    
    # ============================================================
    # STATE MANAGEMENT
    # ============================================================
    
    def update_state(self, state: str) -> bool:
        """
        Update bot state in shadow
        
        Args:
            state: Bot state
            
        Returns:
            True if updated
        """
        return self.update_shadow({
            "status": state,
            "last_update": datetime.now().isoformat(),
        })
    
    def get_state(self) -> Optional[str]:
        """
        Get bot state from shadow
        
        Returns:
            Bot state or None
        """
        shadow = self.get_shadow()
        if shadow:
            return shadow.state.get("reported", {}).get("status")
        return None
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get AWS IoT statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "connection_state": self.connection_state.value,
            "thing_state": self.thing_state.value,
            "thing_name": self.iot_config.thing_name,
            "subscriptions": len(self.subscriptions),
            "message_queue": len(self.message_queue),
            "shadow_cache": len(self.shadow_cache),
            "region": self.iot_config.region,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "ConnectionState",
    "ThingState",
    
    # Dataclasses
    "IoTConfig",
    "IoTShadow",
    "IoTMessage",
    
    # Classes
    "AWSIoTEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
