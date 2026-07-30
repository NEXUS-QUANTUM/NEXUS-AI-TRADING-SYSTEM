# trading/bots/hedge_bot/hedge_bot_data_gcp_iot.py
# Advanced Google Cloud IoT Integration for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot GCP IoT Integration Module - Module d'intégration avancé avec Google Cloud IoT Core
pour le Hedge Bot. Permet la gestion des appareils IoT, la collecte de données en temps réel,
le monitoring, et l'intégration avec les services GCP pour l'infrastructure de trading.
"""

import asyncio
import json
import time
import base64
import hashlib
import hmac
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
from google.cloud import iot_v1
from google.cloud import pubsub_v1
from google.cloud import monitoring_v3
from google.cloud import storage
from google.oauth2 import service_account
import jwt
import aiohttp
import asyncio

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_gcp_iot")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class GCPIoTDeviceState(Enum):
    """États des appareils IoT GCP."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    OFFLINE = "offline"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class GCPIoTTelemetryType(Enum):
    """Types de télémétrie IoT."""
    MARKET_DATA = "market_data"
    TRADING_SIGNAL = "trading_signal"
    SYSTEM_METRIC = "system_metric"
    RISK_METRIC = "risk_metric"
    PERFORMANCE_METRIC = "performance_metric"
    ALERT = "alert"
    POSITION_UPDATE = "position_update"
    ORDER_UPDATE = "order_update"


class GCPIoTDataFormat(Enum):
    """Formats de données IoT."""
    JSON = "json"
    PROTOBUF = "protobuf"
    AVRO = "avro"
    CSV = "csv"
    BINARY = "binary"


# ============== DATA MODELS ==============

@dataclass
class GCPIoTDevice:
    """Modèle d'appareil IoT GCP."""
    device_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    registry_id: str = ""
    name: str = ""
    state: GCPIoTDeviceState = GCPIoTDeviceState.ACTIVE
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    telemetry_count: int = 0
    last_telemetry: Optional[datetime] = None
    credentials: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    location: str = ""
    firmware_version: str = ""
    hardware_version: str = ""
    configuration: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "device_id": self.device_id,
            "project_id": self.project_id,
            "registry_id": self.registry_id,
            "name": self.name,
            "state": self.state.value,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "telemetry_count": self.telemetry_count,
            "last_telemetry": self.last_telemetry.isoformat() if self.last_telemetry else None,
            "credentials": self.credentials,
            "metadata": self.metadata,
            "tags": self.tags,
            "location": self.location,
            "firmware_version": self.firmware_version,
            "hardware_version": self.hardware_version,
            "configuration": self.configuration
        }


@dataclass
class GCPIoTTelemetry:
    """Modèle de télémétrie IoT."""
    telemetry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str = ""
    telemetry_type: GCPIoTTelemetryType = GCPIoTTelemetryType.SYSTEM_METRIC
    format: GCPIoTDataFormat = GCPIoTDataFormat.JSON
    data: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sequence_number: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    signature: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "telemetry_id": self.telemetry_id,
            "device_id": self.device_id,
            "telemetry_type": self.telemetry_type.value,
            "format": self.format.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "sequence_number": self.sequence_number,
            "metadata": self.metadata,
            "signature": self.signature
        }


@dataclass
class GCPIoTCommand:
    """Commande IoT."""
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str = ""
    command_type: str = ""
    payload: Any = None
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    delivered_at: Optional[datetime] = None
    acknowledged: bool = False
    status: str = "pending"  # pending, delivered, acknowledged, failed
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GCPIoTSubscription:
    """Subscription Pub/Sub."""
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    name: str = ""
    push_endpoint: Optional[str] = None
    ack_deadline: int = 10
    filter: Optional[str] = None
    retry_policy: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    active: bool = True


# ============== INTERFACES ==============

class GCPIoTEngineInterface(ABC):
    """Interface abstraite pour le moteur GCP IoT."""
    
    @abstractmethod
    async def register_device(self, device: GCPIoTDevice) -> bool:
        """Enregistre un appareil IoT."""
        pass
    
    @abstractmethod
    async def send_telemetry(self, telemetry: GCPIoTTelemetry) -> bool:
        """Envoie une télémétrie."""
        pass
    
    @abstractmethod
    async def send_command(self, command: GCPIoTCommand) -> bool:
        """Envoie une commande."""
        pass
    
    @abstractmethod
    async def subscribe(self, subscription: GCPIoTSubscription) -> bool:
        """S'abonne à un topic."""
        pass


# ============== IMPLÉMENTATION ==============

class GCPIoTEngine(GCPIoTEngineInterface):
    """
    Moteur d'intégration GCP IoT avancé pour le Hedge Bot.
    Gère les appareils IoT, la télémétrie, les commandes et l'intégration avec GCP.
    """
    
    def __init__(
        self,
        project_id: str,
        credentials_path: str,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.project_id = project_id
        self.credentials_path = credentials_path
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Clients GCP
        self._iot_client = None
        self._pubsub_client = None
        self._monitoring_client = None
        self._storage_client = None
        
        # Gestion des appareils
        self._devices: Dict[str, GCPIoTDevice] = {}
        self._devices_lock = threading.RLock()
        
        # Gestion des télémétries
        self._telemetries: Dict[str, GCPIoTTelemetry] = {}
        self._telemetry_lock = threading.RLock()
        
        # Gestion des commandes
        self._commands: Dict[str, GCPIoTCommand] = {}
        self._commands_lock = threading.RLock()
        
        # Gestion des abonnements
        self._subscriptions: Dict[str, GCPIoTSubscription] = {}
        self._sub_lock = threading.RLock()
        
        # Streaming
        self._telemetry_stream: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "devices_registered": 0,
            "telemetry_sent": 0,
            "commands_sent": 0,
            "subscriptions_created": 0,
            "errors": 0
        }
        
        # État
        self._is_running = False
        
        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Load credentials
        self._credentials = None
        
        logger.info("GCPIoTEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "region": "us-central1",
            "registry_id": "nexus-hedge-bot-registry",
            "telemetry_batch_size": 100,
            "command_timeout": 30,
            "heartbeat_interval": 60,
            "retry_count": 3,
            "retry_delay": 1.0,
            "enable_compression": True,
            "enable_encryption": True,
            "default_data_format": GCPIoTDataFormat.JSON,
            "pubsub_timeout": 10,
            "max_telemetry_size": 1024 * 1024,  # 1 MB
            "cache_size": 1000
        }
    
    async def start(self) -> None:
        """Démarre le moteur GCP IoT."""
        logger.info("GCPIoTEngine starting...")
        self._is_running = True
        
        try:
            # Chargement des credentials
            self._credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path
            )
            
            # Initialisation des clients
            self._iot_client = iot_v1.DeviceManagerClient(credentials=self._credentials)
            self._pubsub_client = pubsub_v1.PublisherClient(credentials=self._credentials)
            self._monitoring_client = monitoring_v3.MetricServiceClient(credentials=self._credentials)
            self._storage_client = storage.Client(credentials=self._credentials, project=self.project_id)
            
            logger.info("GCP clients initialized")
            
            # Création de la session HTTP
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config["command_timeout"])
            )
            
            # Chargement des appareils existants
            await self._load_devices()
            
            # Démarrage des tâches de fond
            asyncio.create_task(self._telemetry_processor())
            asyncio.create_task(self._heartbeat_loop())
            asyncio.create_task(self._subscriber_loop())
            asyncio.create_task(self._cache_cleaner())
            
            logger.info("GCPIoTEngine started")
            
        except Exception as e:
            logger.error(f"Failed to start GCP IoT Engine: {e}")
            raise
    
    async def stop(self) -> None:
        """Arrête le moteur GCP IoT."""
        logger.info("GCPIoTEngine stopping...")
        self._is_running = False
        
        # Fermeture des clients
        if self._session:
            await self._session.close()
        
        # Vidage de la queue
        await self._drain_queue()
        
        logger.info("GCPIoTEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def register_device(self, device: GCPIoTDevice) -> bool:
        """Enregistre un appareil IoT."""
        try:
            # Construction de la requête
            parent = self._iot_client.registry_path(
                self.project_id, self.config["region"], self.config["registry_id"]
            )
            
            # Création de l'appareil
            gcp_device = iot_v1.Device(
                id=device.device_id,
                name=device.name,
                credentials=self._build_credentials(device.credentials),
                metadata=device.metadata
            )
            
            # Enregistrement
            result = self._iot_client.create_device(parent=parent, device=gcp_device)
            
            device.project_id = self.project_id
            device.registry_id = self.config["registry_id"]
            
            with self._devices_lock:
                self._devices[device.device_id] = device
                self._stats["devices_registered"] += 1
            
            logger.info(f"Device registered: {device.device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Device registration error: {e}")
            return False
    
    async def send_telemetry(self, telemetry: GCPIoTTelemetry) -> bool:
        """Envoie une télémétrie."""
        self._stats["telemetry_sent"] += 1
        
        try:
            # Mise en queue
            await self._telemetry_stream.put(telemetry)
            
            # Mise à jour des stats de l'appareil
            with self._devices_lock:
                device = self._devices.get(telemetry.device_id)
                if device:
                    device.telemetry_count += 1
                    device.last_telemetry = telemetry.timestamp
            
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Telemetry send error: {e}")
            return False
    
    async def send_command(self, command: GCPIoTCommand) -> bool:
        """Envoie une commande."""
        self._stats["commands_sent"] += 1
        
        try:
            # Envoi de la commande
            device_path = self._iot_client.device_path(
                self.project_id,
                self.config["region"],
                self.config["registry_id"],
                command.device_id
            )
            
            command.payload = json.dumps(command.payload) if isinstance(command.payload, dict) else command.payload
            
            # Envoi
            self._iot_client.send_command_to_device(
                name=device_path,
                binary_data=command.payload.encode() if command.payload else b""
            )
            
            command.sent_at = datetime.now(timezone.utc)
            command.status = "delivered"
            
            with self._commands_lock:
                self._commands[command.command_id] = command
            
            logger.info(f"Command sent: {command.command_id} -> {command.device_id}")
            return True
            
        except Exception as e:
            command.status = "failed"
            self._stats["errors"] += 1
            logger.error(f"Command send error: {e}")
            return False
    
    async def subscribe(self, subscription: GCPIoTSubscription) -> bool:
        """S'abonne à un topic."""
        try:
            # Création de la subscription
            topic_path = self._pubsub_client.topic_path(self.project_id, subscription.topic)
            subscription_path = self._pubsub_client.subscription_path(
                self.project_id, subscription.subscription_id
            )
            
            # Configuration
            push_config = None
            if subscription.push_endpoint:
                push_config = pubsub_v1.types.PushConfig(
                    push_endpoint=subscription.push_endpoint
                )
            
            # Création
            self._pubsub_client.create_subscription(
                request={
                    "name": subscription_path,
                    "topic": topic_path,
                    "push_config": push_config,
                    "ack_deadline_seconds": subscription.ack_deadline
                }
            )
            
            with self._sub_lock:
                self._subscriptions[subscription.subscription_id] = subscription
                self._stats["subscriptions_created"] += 1
            
            logger.info(f"Subscription created: {subscription.subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Subscription creation error: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - TRAITEMENT ==========
    
    async def _telemetry_processor(self) -> None:
        """Traite les télémétries en batch."""
        while self._is_running:
            try:
                batch = []
                batch_size = self.config["telemetry_batch_size"]
                
                # Collecte des télémétries
                while len(batch) < batch_size:
                    try:
                        telemetry = await asyncio.wait_for(
                            self._telemetry_stream.get(),
                            timeout=1.0
                        )
                        batch.append(telemetry)
                    except asyncio.TimeoutError:
                        break
                
                if batch:
                    await self._process_telemetry_batch(batch)
                
            except Exception as e:
                logger.error(f"Telemetry processor error: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_telemetry_batch(self, batch: List[GCPIoTTelemetry]) -> None:
        """Traite un batch de télémétries."""
        try:
            # Formatage des données
            telemetry_data = []
            for telemetry in batch:
                data = {
                    "device_id": telemetry.device_id,
                    "type": telemetry.telemetry_type.value,
                    "data": telemetry.data,
                    "timestamp": telemetry.timestamp.isoformat(),
                    "sequence": telemetry.sequence_number
                }
                telemetry_data.append(data)
            
            # Envoi à GCP IoT Core
            if self._iot_client:
                # Publication sur Pub/Sub
                topic_path = self._pubsub_client.topic_path(
                    self.project_id, "nexus-telemetry"
                )
                
                for data in telemetry_data:
                    message = json.dumps(data).encode()
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        self._pubsub_client.publish,
                        topic_path,
                        message
                    )
            
            # Stockage local
            if self.data_manager:
                for telemetry in batch:
                    await self.data_manager.store(
                        f"gcp:telemetry:{telemetry.telemetry_id}",
                        telemetry.to_dict(),
                        DataType.TELEMETRY
                    )
            
            logger.debug(f"Telemetry batch processed: {len(batch)} messages")
            
        except Exception as e:
            logger.error(f"Telemetry batch processing error: {e}")
    
    async def _subscriber_loop(self) -> None:
        """Boucle de réception des messages."""
        while self._is_running:
            try:
                # Récupération des messages
                if self._pubsub_client:
                    subscription_path = self._pubsub_client.subscription_path(
                        self.project_id, "nexus-subscriber"
                    )
                    
                    # Pull des messages
                    response = self._pubsub_client.pull(
                        request={
                            "subscription": subscription_path,
                            "max_messages": 100
                        }
                    )
                    
                    for received_message in response.received_messages:
                        message = received_message.message
                        
                        # Traitement du message
                        await self._process_message(message)
                        
                        # ACK
                        self._pubsub_client.acknowledge(
                            request={
                                "subscription": subscription_path,
                                "ack_ids": [received_message.ack_id]
                            }
                        )
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Subscriber loop error: {e}")
                await asyncio.sleep(1)
    
    async def _process_message(self, message: Any) -> None:
        """Traite un message reçu."""
        try:
            data = json.loads(message.data.decode())
            logger.debug(f"Message received: {data}")
            
            # Classification du message
            msg_type = data.get("type", "unknown")
            
            if msg_type == "command":
                # Traitement d'une commande
                await self._process_command(data)
            elif msg_type == "telemetry":
                # Traitement d'une télémétrie
                await self._process_telemetry(data)
            elif msg_type == "alert":
                # Traitement d'une alerte
                await self._process_alert(data)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
                
        except Exception as e:
            logger.error(f"Message processing error: {e}")
    
    async def _process_command(self, data: Dict[str, Any]) -> None:
        """Traite une commande."""
        command = GCPIoTCommand(
            device_id=data.get("device_id", ""),
            command_type=data.get("command_type", ""),
            payload=data.get("payload"),
            metadata=data.get("metadata", {})
        )
        command.delivered_at = datetime.now(timezone.utc)
        
        with self._commands_lock:
            self._commands[command.command_id] = command
        
        logger.info(f"Command processed: {command.command_id}")
    
    async def _process_telemetry(self, data: Dict[str, Any]) -> None:
        """Traite une télémétrie."""
        telemetry = GCPIoTTelemetry(
            device_id=data.get("device_id", ""),
            telemetry_type=GCPIoTTelemetryType(data.get("type", "system_metric")),
            data=data.get("data"),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
            sequence_number=data.get("sequence", 0)
        )
        
        with self._telemetry_lock:
            self._telemetries[telemetry.telemetry_id] = telemetry
        
        # Mise à jour de l'appareil
        with self._devices_lock:
            device = self._devices.get(telemetry.device_id)
            if device:
                device.telemetry_count += 1
                device.last_telemetry = telemetry.timestamp
        
        logger.debug(f"Telemetry processed: {telemetry.telemetry_id}")
    
    async def _process_alert(self, data: Dict[str, Any]) -> None:
        """Traite une alerte."""
        logger.warning(f"Alert received: {data}")
        
        # Stockage de l'alerte
        if self.data_manager:
            await self.data_manager.store(
                f"gcp:alert:{datetime.now(timezone.utc).timestamp()}",
                data,
                DataType.ALERT
            )
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    def _build_credentials(self, creds: Dict[str, Any]) -> List[Any]:
        """Construit les credentials pour GCP IoT."""
        # Dans un système réel, on construir les credentials
        return []
    
    async def _load_devices(self) -> None:
        """Charge les appareils existants."""
        try:
            parent = self._iot_client.registry_path(
                self.project_id, self.config["region"], self.config["registry_id"]
            )
            
            # Liste des appareils
            devices = self._iot_client.list_devices(request={"parent": parent})
            
            for device in devices:
                gcp_device = GCPIoTDevice(
                    device_id=device.id,
                    name=device.name,
                    state=GCPIoTDeviceState.ACTIVE,
                    metadata=device.metadata
                )
                
                with self._devices_lock:
                    self._devices[gcp_device.device_id] = gcp_device
            
            logger.info(f"Loaded {len(self._devices)} devices")
            
        except Exception as e:
            logger.error(f"Load devices error: {e}")
    
    async def _heartbeat_loop(self) -> None:
        """Boucle de heartbeat."""
        while self._is_running:
            await asyncio.sleep(self.config["heartbeat_interval"])
            
            try:
                now = datetime.now(timezone.utc)
                
                with self._devices_lock:
                    for device_id, device in self._devices.items():
                        # Vérification du dernier heartbeat
                        age = (now - device.last_heartbeat).total_seconds()
                        if age > self.config["heartbeat_interval"] * 2:
                            device.state = GCPIoTDeviceState.OFFLINE
                        else:
                            device.state = GCPIoTDeviceState.ACTIVE
                        
                        # Envoi d'un heartbeat
                        telemetry = GCPIoTTelemetry(
                            device_id=device_id,
                            telemetry_type=GCPIoTTelemetryType.SYSTEM_METRIC,
                            data={"status": "alive", "state": device.state.value},
                            timestamp=now
                        )
                        await self.send_telemetry(telemetry)
                        
                        device.last_heartbeat = now
                
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                # Nettoyage des télémétries
                with self._telemetry_lock:
                    if len(self._telemetries) > self.config["cache_size"]:
                        keys = sorted(self._telemetries.keys())
                        for key in keys[:len(self._telemetries) - self.config["cache_size"]]:
                            del self._telemetries[key]
                
                # Nettoyage des commandes
                with self._commands_lock:
                    if len(self._commands) > self.config["cache_size"] // 2:
                        keys = sorted(self._commands.keys())
                        for key in keys[:len(self._commands) - self.config["cache_size"] // 2]:
                            del self._commands[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _drain_queue(self) -> None:
        """Vide la queue des télémétries."""
        while not self._telemetry_stream.empty():
            try:
                telemetry = await self._telemetry_stream.get()
                await self._process_telemetry_batch([telemetry])
            except Exception:
                break
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_device(self, device_id: str) -> Optional[GCPIoTDevice]:
        """Récupère un appareil."""
        with self._devices_lock:
            return self._devices.get(device_id)
    
    async def get_devices(self, state: Optional[GCPIoTDeviceState] = None) -> List[GCPIoTDevice]:
        """Récupère les appareils."""
        with self._devices_lock:
            devices = list(self._devices.values())
            if state:
                devices = [d for d in devices if d.state == state]
            return devices
    
    async def get_telemetry(self, telemetry_id: str) -> Optional[GCPIoTTelemetry]:
        """Récupère une télémétrie."""
        with self._telemetry_lock:
            return self._telemetries.get(telemetry_id)
    
    async def get_telemetry_for_device(
        self,
        device_id: str,
        limit: int = 100
    ) -> List[GCPIoTTelemetry]:
        """Récupère les télémétries d'un appareil."""
        with self._telemetry_lock:
            telemetries = [
                t for t in self._telemetries.values()
                if t.device_id == device_id
            ]
            return sorted(telemetries, key=lambda t: t.timestamp, reverse=True)[:limit]
    
    async def get_command(self, command_id: str) -> Optional[GCPIoTCommand]:
        """Récupère une commande."""
        with self._commands_lock:
            return self._commands.get(command_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._devices_lock:
            self._stats["total_devices"] = len(self._devices)
        with self._telemetry_lock:
            self._stats["cached_telemetries"] = len(self._telemetries)
        with self._commands_lock:
            self._stats["cached_commands"] = len(self._commands)
        
        return self._stats.copy()


# ============== IOT DEVICE SIMULATOR ==============

class IoTDeviceSimulator:
    """
    Simulateur d'appareil IoT pour le test et le développement.
    Simule des appareils IoT envoyant des données de trading.
    """
    
    def __init__(
        self,
        engine: GCPIoTEngine,
        device_id: str,
        config: Optional[Dict[str, Any]] = None
    ):
        self.engine = engine
        self.device_id = device_id
        self.config = config or self._default_config()
        
        # État
        self._is_running = False
        self._telemetry_counter = 0
        
        logger.info(f"IoTDeviceSimulator initialized for {device_id}")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "telemetry_interval": 1.0,  # secondes
            "market_symbols": ["BTC-USD", "ETH-USD", "AAPL", "SPX"],
            "telemetry_types": [
                "market_data", "system_metric", "risk_metric"
            ],
            "price_volatility": 0.02,
            "volume_base": 1000000
        }
    
    async def start(self) -> None:
        """Démarre le simulateur."""
        self._is_running = True
        logger.info(f"IoTDeviceSimulator started for {self.device_id}")
        
        # Enregistrement de l'appareil
        device = GCPIoTDevice(
            device_id=self.device_id,
            name=f"Simulator_{self.device_id}",
            metadata={"type": "simulator", "version": "1.0"}
        )
        await self.engine.register_device(device)
        
        # Boucle de génération de télémétrie
        while self._is_running:
            try:
                await self._generate_telemetry()
                await asyncio.sleep(self.config["telemetry_interval"])
            except Exception as e:
                logger.error(f"Simulator error: {e}")
                await asyncio.sleep(1)
    
    async def stop(self) -> None:
        """Arrête le simulateur."""
        self._is_running = False
        logger.info(f"IoTDeviceSimulator stopped for {self.device_id}")
    
    async def _generate_telemetry(self) -> None:
        """Génère une télémétrie aléatoire."""
        self._telemetry_counter += 1
        
        # Sélection aléatoire du type
        telemetry_type = random.choice(self.config["telemetry_types"])
        
        if telemetry_type == "market_data":
            data = await self._generate_market_data()
        elif telemetry_type == "system_metric":
            data = await self._generate_system_metric()
        elif telemetry_type == "risk_metric":
            data = await self._generate_risk_metric()
        else:
            data = {"status": "alive"}
        
        # Création de la télémétrie
        telemetry = GCPIoTTelemetry(
            device_id=self.device_id,
            telemetry_type=GCPIoTTelemetryType(telemetry_type),
            data=data,
            sequence_number=self._telemetry_counter
        )
        
        # Envoi
        await self.engine.send_telemetry(telemetry)
    
    async def _generate_market_data(self) -> Dict[str, Any]:
        """Génère des données de marché."""
        symbol = random.choice(self.config["market_symbols"])
        base_price = {
            "BTC-USD": 50000,
            "ETH-USD": 3000,
            "AAPL": 180,
            "SPX": 4500
        }.get(symbol, 100)
        
        price = base_price * (1 + random.gauss(0, self.config["price_volatility"]))
        volume = self.config["volume_base"] * (0.5 + random.random())
        
        return {
            "symbol": symbol,
            "price": price,
            "volume": volume,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bid": price * (1 - 0.0005 * random.random()),
            "ask": price * (1 + 0.0005 * random.random())
        }
    
    async def _generate_system_metric(self) -> Dict[str, Any]:
        """Génère une métrique système."""
        return {
            "cpu_usage": random.random() * 100,
            "memory_usage": random.random() * 100,
            "disk_usage": random.random() * 100,
            "network_io": random.random() * 1000,
            "temperature": 20 + random.random() * 30,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def _generate_risk_metric(self) -> Dict[str, Any]:
        """Génère une métrique de risque."""
        return {
            "var": random.random() * 0.05,
            "sharpe": random.random() * 2,
            "drawdown": random.random() * 0.15,
            "volatility": random.random() * 0.3,
            "correlation": random.random() * 2 - 1,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# ============== FACTORY ==============

class GCPIoTFactory:
    """Factory pour créer des composants GCP IoT."""
    
    @staticmethod
    async def create_engine(
        project_id: str,
        credentials_path: str,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> GCPIoTEngine:
        """Crée un moteur GCP IoT."""
        engine = GCPIoTEngine(
            project_id=project_id,
            credentials_path=credentials_path,
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    async def create_simulator(
        engine: GCPIoTEngine,
        device_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> IoTDeviceSimulator:
        """Crée un simulateur d'appareil IoT."""
        return IoTDeviceSimulator(engine, device_id, config)


# ============== EXPORT ==============

__all__ = [
    "GCPIoTDeviceState",
    "GCPIoTTelemetryType",
    "GCPIoTDataFormat",
    "GCPIoTDevice",
    "GCPIoTTelemetry",
    "GCPIoTCommand",
    "GCPIoTSubscription",
    "GCPIoTEngineInterface",
    "GCPIoTEngine",
    "IoTDeviceSimulator",
    "GCPIoTFactory"
]
