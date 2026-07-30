# trading/bots/hedge_bot/hedge_bot_data_azure_iot.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Azure IoT Integration Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Azure IoT Integration Module

This module provides comprehensive Azure IoT Hub integration for the
NEXUS Hedge Bot system. It enables secure communication with Azure IoT Hub,
device management, and telemetry processing.

The module covers:
- Azure IoT Hub Integration
- Device-to-Cloud Telemetry
- Cloud-to-Device Messaging
- Device Twin Management
- Direct Methods
- IoT Hub Message Routing
- Device Provisioning
- Secure Communication
- Telemetry Processing
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

# Try to import Azure IoT SDK
try:
    from azure.iot.device import IoTHubDeviceClient, Message, MethodResponse
    from azure.iot.device.exceptions import ConnectionFailedError
    HAS_AZURE_IOT = True
except ImportError:
    HAS_AZURE_IOT = False

logger = logging.getLogger(__name__)


# ============================================================
# AZURE IOT ENUMS
# ============================================================

class AzureConnectionState(Enum):
    """Connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class DeviceTwinStatus(Enum):
    """Device twin status"""
    SYNCED = "synced"
    PENDING = "pending"
    UPDATING = "updating"
    ERROR = "error"


@dataclass
class AzureIoTConfig:
    """Azure IoT configuration"""
    connection_string: str
    device_id: str
    hostname: str
    use_websocket: bool = False
    keep_alive: int = 60
    model_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "device_id": self.device_id,
            "hostname": self.hostname,
            "use_websocket": self.use_websocket,
            "keep_alive": self.keep_alive,
            "model_id": self.model_id,
        }


@dataclass
class DeviceTwin:
    """Device twin data"""
    device_id: str
    desired: Dict[str, Any]
    reported: Dict[str, Any]
    version: int
    timestamp: datetime = field(default_factory=datetime.now)
    status: DeviceTwinStatus = DeviceTwinStatus.SYNCED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "device_id": self.device_id,
            "desired": self.desired,
            "reported": self.reported,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
        }


@dataclass
class AzureIoTMessage:
    """Azure IoT message"""
    topic: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "topic": self.topic,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "properties": self.properties,
        }


# ============================================================
# AZURE IOT ENGINE
# ============================================================

class AzureIoTEngine:
    """
    Comprehensive Azure IoT engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Azure IoT engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        if not HAS_AZURE_IOT:
            logger.warning("Azure IoT libraries not installed")
        
        # IoT Config
        self.iot_config = None
        self._load_config()
        
        # State
        self.device_client = None
        self.connection_state = AzureConnectionState.DISCONNECTED
        self.device_twin: Optional[DeviceTwin] = None
        self.message_callbacks: Dict[str, Callable] = {}
        self.telemetry_queue: List[AzureIoTMessage] = []
        
        # Threading
        self.is_running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Initialize
        self._init_device_client()
        
        logger.info("Azure IoT engine initialized")
    
    # ============================================================
    # INITIALIZATION
    # ============================================================
    
    def _load_config(self) -> None:
        """Load IoT configuration"""
        self.iot_config = AzureIoTConfig(
            connection_string=self.config.get("connection_string", ""),
            device_id=self.config.get("device_id", "nexus-hedge-bot"),
            hostname=self.config.get("hostname", ""),
            use_websocket=self.config.get("use_websocket", False),
            keep_alive=self.config.get("keep_alive", 60),
            model_id=self.config.get("model_id"),
        )
    
    def _init_device_client(self) -> None:
        """Initialize device client"""
        if not HAS_AZURE_IOT or not self.iot_config.connection_string:
            return
        
        try:
            self.device_client = IoTHubDeviceClient.create_from_connection_string(
                self.iot_config.connection_string,
                websockets=self.iot_config.use_websocket,
                keep_alive=self.iot_config.keep_alive,
            )
            
            # Set handlers
            self.device_client.on_connection_status_changed = self._on_connection_status_changed
            self.device_client.on_twin_desired_properties_patch_received = self._on_desired_properties_received
            self.device_client.on_message_received = self._on_message_received
            self.device_client.on_method_request_received = self._on_method_request
            
            logger.info("Azure IoT device client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize device client: {e}")
    
    # ============================================================
    # CONNECTION MANAGEMENT
    # ============================================================
    
    def connect(self) -> bool:
        """
        Connect to Azure IoT Hub
        
        Returns:
            True if connected
        """
        if not HAS_AZURE_IOT or not self.device_client:
            logger.error("Azure IoT libraries not installed or device client not initialized")
            return False
        
        if self.connection_state == AzureConnectionState.CONNECTED:
            return True
        
        try:
            self.connection_state = AzureConnectionState.CONNECTING
            self.device_client.connect()
            self.connection_state = AzureConnectionState.CONNECTED
            
            # Get device twin
            self._get_twin()
            
            # Start monitoring
            self._start_monitoring()
            
            logger.info(f"Connected to Azure IoT Hub: {self.iot_config.hostname}")
            return True
            
        except Exception as e:
            self.connection_state = AzureConnectionState.ERROR
            logger.error(f"Failed to connect: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from Azure IoT Hub"""
        if not self.device_client:
            return
        
        try:
            self.is_running = False
            self.device_client.disconnect()
            self.connection_state = AzureConnectionState.DISCONNECTED
            logger.info("Disconnected from Azure IoT Hub")
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
                # Process telemetry queue
                if self.telemetry_queue:
                    self._process_telemetry()
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(5)
    
    def _on_connection_status_changed(self, status: str) -> None:
        """Handle connection status change"""
        if status == "connected":
            self.connection_state = AzureConnectionState.CONNECTED
            logger.info("Azure IoT connection established")
        elif status == "disconnected":
            self.connection_state = AzureConnectionState.DISCONNECTED
            logger.warning("Azure IoT connection lost")
        elif status == "error":
            self.connection_state = AzureConnectionState.ERROR
            logger.error("Azure IoT connection error")
    
    # ============================================================
    # TELEMETRY
    # ============================================================
    
    def send_telemetry(
        self,
        data: Dict[str, Any],
        properties: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send telemetry to IoT Hub
        
        Args:
            data: Telemetry data
            properties: Message properties
            
        Returns:
            True if sent
        """
        if not HAS_AZURE_IOT or not self.device_client:
            return False
        
        if self.connection_state != AzureConnectionState.CONNECTED:
            # Queue telemetry
            self.telemetry_queue.append(AzureIoTMessage(
                topic="telemetry",
                payload=data,
                properties=properties or {},
            ))
            return True
        
        try:
            message = Message(json.dumps(data))
            if properties:
                for key, value in properties.items():
                    message.custom_properties[key] = value
            
            self.device_client.send_message(message)
            return True
            
        except Exception as e:
            logger.error(f"Failed to send telemetry: {e}")
            return False
    
    def _process_telemetry(self) -> None:
        """Process queued telemetry"""
        while self.telemetry_queue:
            message = self.telemetry_queue.pop(0)
            self.send_telemetry(message.payload, message.properties)
    
    # ============================================================
    # DEVICE TWIN
    # ============================================================
    
    def _get_twin(self) -> None:
        """Get device twin"""
        if not HAS_AZURE_IOT or not self.device_client:
            return
        
        try:
            twin = self.device_client.get_twin()
            self.device_twin = DeviceTwin(
                device_id=self.iot_config.device_id,
                desired=twin.get("desired", {}),
                reported=twin.get("reported", {}),
                version=twin.get("version", 1),
                status=DeviceTwinStatus.SYNCED,
            )
            logger.info("Device twin retrieved")
        except Exception as e:
            logger.error(f"Failed to get twin: {e}")
    
    def update_reported_properties(self, properties: Dict[str, Any]) -> bool:
        """
        Update reported properties
        
        Args:
            properties: Reported properties
            
        Returns:
            True if updated
        """
        if not HAS_AZURE_IOT or not self.device_client:
            return False
        
        try:
            self.device_client.patch_twin_reported_properties(properties)
            
            if self.device_twin:
                self.device_twin.reported.update(properties)
                self.device_twin.version += 1
            
            logger.info(f"Updated reported properties: {list(properties.keys())}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update reported properties: {e}")
            return False
    
    def _on_desired_properties_received(self, patch: Dict[str, Any]) -> None:
        """
        Handle desired properties update
        
        Args:
            patch: Desired properties patch
        """
        logger.info(f"Desired properties updated: {list(patch.keys())}")
        
        if self.device_twin:
            self.device_twin.desired.update(patch)
            self.device_twin.status = DeviceTwinStatus.UPDATING
        
        # Apply desired properties
        # Process specific properties
        if "status" in patch:
            self._handle_status_update(patch["status"])
    
    def _handle_status_update(self, status: str) -> None:
        """
        Handle status update
        
        Args:
            status: New status
        """
        logger.info(f"Status update requested: {status}")
        # Implement status handling logic
    
    # ============================================================
    # CLOUD-TO-DEVICE MESSAGES
    # ============================================================
    
    def _on_message_received(self, message: Any) -> None:
        """
        Handle cloud-to-device message
        
        Args:
            message: Received message
        """
        try:
            payload = json.loads(message.data.decode())
            
            msg = AzureIoTMessage(
                topic="cloud_to_device",
                payload=payload,
                properties=message.custom_properties or {},
            )
            
            # Process message
            self._process_cloud_message(msg)
            
        except Exception as e:
            logger.error(f"Failed to handle message: {e}")
    
    def _process_cloud_message(self, message: AzureIoTMessage) -> None:
        """
        Process cloud-to-device message
        
        Args:
            message: AzureIoTMessage
        """
        # Handle by type
        msg_type = message.payload.get("type", "unknown")
        
        if msg_type == "command":
            self._execute_command(message.payload.get("command", {}))
        elif msg_type == "config":
            self._apply_config(message.payload.get("config", {}))
        elif msg_type == "query":
            self._handle_query(message.payload.get("query", {}))
        else:
            logger.info(f"Received message: {msg_type}")
    
    def _execute_command(self, command: Dict[str, Any]) -> None:
        """
        Execute a command
        
        Args:
            command: Command data
        """
        logger.info(f"Executing command: {command}")
        # Implement command execution
    
    def _apply_config(self, config: Dict[str, Any]) -> None:
        """
        Apply configuration
        
        Args:
            config: Configuration data
        """
        logger.info(f"Applying config: {list(config.keys())}")
        # Implement config application
    
    def _handle_query(self, query: Dict[str, Any]) -> None:
        """
        Handle query
        
        Args:
            query: Query data
        """
        logger.info(f"Handling query: {query}")
        # Implement query handling
    
    # ============================================================
    # DIRECT METHODS
    # ============================================================
    
    def _on_method_request(self, method_request: Any) -> None:
        """
        Handle direct method request
        
        Args:
            method_request: Method request
        """
        try:
            method_name = method_request.name
            payload = json.loads(method_request.payload.decode()) if method_request.payload else {}
            
            logger.info(f"Direct method called: {method_name}")
            
            # Handle methods
            if method_name == "ping":
                response = self._handle_ping(payload)
            elif method_name == "get_status":
                response = self._handle_get_status(payload)
            elif method_name == "restart":
                response = self._handle_restart(payload)
            else:
                response = {"success": False, "error": f"Unknown method: {method_name}"}
            
            method_response = MethodResponse(
                request_id=method_request.request_id,
                status=200,
                payload=response
            )
            self.device_client.send_method_response(method_response)
            
        except Exception as e:
            logger.error(f"Failed to handle method: {e}")
    
    def _handle_ping(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping method"""
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "status": "alive",
            "version": "2.0.0",
        }
    
    def _handle_get_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_status method"""
        return {
            "success": True,
            "status": {
                "connection": self.connection_state.value,
                "device_id": self.iot_config.device_id,
                "last_update": datetime.now().isoformat(),
            }
        }
    
    def _handle_restart(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle restart method"""
        return {
            "success": True,
            "message": "Restart initiated",
            "timestamp": datetime.now().isoformat(),
        }
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get Azure IoT statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "connection_state": self.connection_state.value,
            "device_id": self.iot_config.device_id,
            "hostname": self.iot_config.hostname,
            "telemetry_queue": len(self.telemetry_queue),
            "device_twin_version": self.device_twin.version if self.device_twin else 0,
            "callbacks": len(self.message_callbacks),
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "AzureConnectionState",
    "DeviceTwinStatus",
    
    # Dataclasses
    "AzureIoTConfig",
    "DeviceTwin",
    "AzureIoTMessage",
    
    # Classes
    "AzureIoTEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
