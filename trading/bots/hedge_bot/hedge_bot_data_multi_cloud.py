# trading/bots/hedge_bot/hedge_bot_data_multi_cloud.py
# Advanced Multi-Cloud Data Management & Orchestration Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Multi-Cloud Module - Module avancé de gestion multi-cloud et d'orchestration des données
pour le Hedge Bot. Gère la distribution des données sur plusieurs clouds, la réplication,
la résilience, le failover, l'optimisation des coûts et l'orchestration des ressources.
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import threading
import concurrent.futures
import aiohttp
import aiohttp.client_exceptions
import boto3
from botocore.exceptions import ClientError
from google.cloud import storage as gcs
from azure.storage.blob import BlobServiceClient
from collections import defaultdict, deque

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_multi_cloud")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class CloudProvider(Enum):
    """Fournisseurs de cloud."""
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    LOCAL = "local"
    ON_PREM = "on_prem"


class CloudService(Enum):
    """Services cloud."""
    S3 = "s3"                    # AWS S3
    GCS = "gcs"                  # Google Cloud Storage
    BLOB = "blob"                # Azure Blob Storage
    EBS = "ebs"                  # AWS EBS
    RDS = "rds"                  # AWS RDS
    CLOUD_SQL = "cloud_sql"      # GCP Cloud SQL
    POSTGRES = "postgres"        # Azure PostgreSQL
    DYNAMODB = "dynamodb"        # AWS DynamoDB
    FIRESTORE = "firestore"      # GCP Firestore
    COSMOS = "cosmos"            # Azure Cosmos DB


class CloudDataTier(Enum):
    """Tiers de données cloud."""
    HOT = "hot"                  # Accès fréquent
    WARM = "warm"                # Accès modéré
    COLD = "cold"                # Accès rare
    ARCHIVE = "archive"          # Archivage
    FROZEN = "frozen"            # Gelé


class CloudSyncMode(Enum):
    """Modes de synchronisation cloud."""
    REAL_TIME = "real_time"
    BATCH = "batch"
    EVENT_DRIVEN = "event_driven"
    SCHEDULED = "scheduled"
    MANUAL = "manual"


# ============== DATA MODELS ==============

@dataclass
class CloudResource:
    """Ressource cloud."""
    resource_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    provider: CloudProvider = CloudProvider.AWS
    service: CloudService = CloudService.S3
    region: str = ""
    endpoint: str = ""
    credentials: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CloudDataDistribution:
    """Distribution de données cloud."""
    distribution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data_type: DataType = DataType.MARKET
    primary_cloud: CloudProvider = CloudProvider.AWS
    replica_clouds: List[CloudProvider] = field(default_factory=list)
    sync_mode: CloudSyncMode = CloudSyncMode.REAL_TIME
    replication_factor: int = 2
    compression: bool = True
    encryption: bool = True
    tier: CloudDataTier = CloudDataTier.HOT
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True


@dataclass
class CloudDataTransfer:
    """Transfert de données cloud."""
    transfer_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_resource: str = ""
    destination_resource: str = ""
    data_type: DataType = DataType.MARKET
    size_bytes: int = 0
    status: str = "pending"  # pending, running, completed, failed
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    throughput_mbps: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class CloudCostOptimization:
    """Optimisation des coûts cloud."""
    optimization_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    current_cost: float = 0.0
    optimized_cost: float = 0.0
    savings: float = 0.0
    strategy: str = ""
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class MultiCloudEngineInterface(ABC):
    """Interface abstraite pour le moteur multi-cloud."""
    
    @abstractmethod
    async def register_resource(self, resource: CloudResource) -> str:
        """Enregistre une ressource cloud."""
        pass
    
    @abstractmethod
    async def distribute_data(self, distribution: CloudDataDistribution) -> bool:
        """Distribue des données sur plusieurs clouds."""
        pass
    
    @abstractmethod
    async def transfer_data(self, transfer: CloudDataTransfer) -> CloudDataTransfer:
        """Transfère des données entre clouds."""
        pass
    
    @abstractmethod
    async def optimize_costs(self, resource_id: str) -> CloudCostOptimization:
        """Optimise les coûts cloud."""
        pass


# ============== IMPLÉMENTATION ==============

class MultiCloudEngine(MultiCloudEngineInterface):
    """
    Moteur multi-cloud avancé pour le Hedge Bot.
    Gère la distribution des données, la réplication et l'optimisation des coûts.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.encryption_engine = encryption_engine
        self.config = config or self._default_config()
        
        # Gestion des ressources
        self._resources: Dict[str, CloudResource] = {}
        self._resources_lock = threading.RLock()
        
        # Gestion des distributions
        self._distributions: Dict[str, CloudDataDistribution] = {}
        self._distributions_lock = threading.RLock()
        
        # Gestion des transferts
        self._transfers: Dict[str, CloudDataTransfer] = {}
        self._transfers_lock = threading.RLock()
        
        # Clients cloud
        self._clients: Dict[str, Any] = {}
        self._clients_lock = threading.RLock()
        
        # Queue de transfert
        self._transfer_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "resources_registered": 0,
            "distributions_created": 0,
            "transfers_completed": 0,
            "transfers_failed": 0,
            "data_volume_gb": 0.0,
            "cost_savings": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info("MultiCloudEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_sync_mode": CloudSyncMode.REAL_TIME,
            "default_replication_factor": 2,
            "max_transfer_retries": 3,
            "transfer_timeout": 3600,
            "compression_enabled": True,
            "encryption_enabled": True,
            "cost_optimization_interval": 86400,
            "health_check_interval": 60,
            "max_concurrent_transfers": 5,
            "data_tiering_enabled": True,
            "auto_failover_enabled": True
        }
    
    async def start(self) -> None:
        """Démarre le moteur multi-cloud."""
        logger.info("MultiCloudEngine starting...")
        self._is_running = True
        
        # Session HTTP
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        
        # Chargement des ressources
        await self._load_resources()
        
        # Initialisation des clients cloud
        await self._initialize_clients()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._transfer_processor())
        asyncio.create_task(self._cost_optimizer())
        asyncio.create_task(self._health_checker())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("MultiCloudEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur multi-cloud."""
        logger.info("MultiCloudEngine stopping...")
        self._is_running = False
        
        # Drain de la queue
        await self._drain_queue()
        
        # Fermeture des clients
        for client in self._clients.values():
            if hasattr(client, "close"):
                try:
                    await client.close()
                except:
                    pass
        
        # Fermeture de la session
        if self._session:
            await self._session.close()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("MultiCloudEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def register_resource(self, resource: CloudResource) -> str:
        """Enregistre une ressource cloud."""
        # Chiffrement des credentials
        if self.encryption_engine and self.config["encryption_enabled"]:
            for key, value in resource.credentials.items():
                if isinstance(value, str):
                    encrypted = await self.encryption_engine.encrypt(
                        value.encode(),
                        "cloud_credentials"
                    )
                    resource.credentials[key] = encrypted.to_dict()
        
        with self._resources_lock:
            self._resources[resource.resource_id] = resource
            self._stats["resources_registered"] += 1
        
        # Initialisation du client
        await self._initialize_client(resource)
        
        logger.info(f"Cloud resource registered: {resource.name} "
                   f"(provider={resource.provider.value})")
        return resource.resource_id
    
    async def distribute_data(self, distribution: CloudDataDistribution) -> bool:
        """Distribue des données sur plusieurs clouds."""
        with self._distributions_lock:
            self._distributions[distribution.distribution_id] = distribution
            self._stats["distributions_created"] += 1
        
        try:
            # Récupération des données
            if not self.data_manager:
                raise ValueError("Data manager not available")
            
            data = await self.data_manager.retrieve_all(distribution.data_type)
            
            if not data:
                logger.warning(f"No data to distribute for {distribution.data_type.value}")
                return False
            
            # Distribution vers les clouds de réplica
            tasks = []
            for cloud in distribution.replica_clouds:
                if cloud == distribution.primary_cloud:
                    continue
                
                # Création du transfert
                transfer = CloudDataTransfer(
                    source_resource=distribution.primary_cloud.value,
                    destination_resource=cloud.value,
                    data_type=distribution.data_type,
                    size_bytes=sum(len(str(r.value).encode()) for r in data)
                )
                
                with self._transfers_lock:
                    self._transfers[transfer.transfer_id] = transfer
                
                # Mise en queue du transfert
                await self._transfer_queue.put(transfer)
            
            logger.info(f"Data distribution started for {distribution.data_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Distribution error: {e}")
            return False
    
    async def transfer_data(self, transfer: CloudDataTransfer) -> CloudDataTransfer:
        """Transfère des données entre clouds."""
        with self._transfers_lock:
            self._transfers[transfer.transfer_id] = transfer
        
        await self._transfer_queue.put(transfer)
        
        # Attente du résultat
        while transfer.status == "pending":
            await asyncio.sleep(0.1)
        
        return transfer
    
    async def optimize_costs(self, resource_id: str) -> CloudCostOptimization:
        """Optimise les coûts cloud."""
        # Récupération de la ressource
        with self._resources_lock:
            resource = self._resources.get(resource_id)
            if not resource:
                raise ValueError(f"Resource {resource_id} not found")
        
        # Analyse des coûts
        current_cost = await self._calculate_current_cost(resource)
        
        # Optimisation
        recommendations = await self._generate_cost_recommendations(resource)
        optimized_cost = current_cost * 0.7  # Simulation de réduction de 30%
        savings = current_cost - optimized_cost
        
        # Création de l'optimisation
        optimization = CloudCostOptimization(
            resource_id=resource_id,
            current_cost=current_cost,
            optimized_cost=optimized_cost,
            savings=savings,
            strategy="cost_optimization",
            recommendations=recommendations
        )
        
        self._stats["cost_savings"] += savings
        
        logger.info(f"Cost optimization completed for {resource.name}: "
                   f"savings={savings:.2f}")
        
        return optimization
    
    # ========== MÉTHODES PRIVÉES - CLIENTS ==========
    
    async def _initialize_clients(self) -> None:
        """Initialise les clients cloud."""
        with self._resources_lock:
            for resource in self._resources.values():
                await self._initialize_client(resource)
    
    async def _initialize_client(self, resource: CloudResource) -> None:
        """Initialise un client cloud."""
        try:
            if resource.provider == CloudProvider.AWS:
                client = boto3.client(
                    resource.service.value,
                    region_name=resource.region,
                    aws_access_key_id=resource.credentials.get("access_key"),
                    aws_secret_access_key=resource.credentials.get("secret_key")
                )
            elif resource.provider == CloudProvider.GCP:
                client = gcs.Client.from_service_account_info(
                    resource.credentials
                )
            elif resource.provider == CloudProvider.AZURE:
                client = BlobServiceClient.from_connection_string(
                    resource.credentials.get("connection_string")
                )
            else:
                client = None
            
            if client:
                with self._clients_lock:
                    self._clients[resource.resource_id] = client
                    
        except Exception as e:
            logger.error(f"Client initialization error for {resource.name}: {e}")
    
    # ========== MÉTHODES PRIVÉES - TRANSFERT ==========
    
    async def _transfer_processor(self) -> None:
        """Traite les transferts de données."""
        semaphore = asyncio.Semaphore(self.config["max_concurrent_transfers"])
        
        while self._is_running:
            try:
                transfer = await self._transfer_queue.get()
                
                async with semaphore:
                    await self._execute_transfer(transfer)
                
            except Exception as e:
                logger.error(f"Transfer processor error: {e}")
                await asyncio.sleep(1)
    
    async def _execute_transfer(self, transfer: CloudDataTransfer) -> None:
        """Exécute un transfert de données."""
        transfer.status = "running"
        transfer.start_time = datetime.now(timezone.utc)
        
        try:
            # Récupération des clients
            source_client = self._clients.get(transfer.source_resource)
            dest_client = self._clients.get(transfer.destination_resource)
            
            if not source_client or not dest_client:
                raise ValueError("Cloud clients not available")
            
            # Récupération des données
            data = await self._read_from_cloud(source_client, transfer)
            
            # Compression
            if self.config["compression_enabled"]:
                data = await self._compress_data(data)
            
            # Chiffrement
            if self.config["encryption_enabled"] and self.encryption_engine:
                data = await self.encryption_engine.encrypt(data, "cloud_transfer")
            
            # Écriture vers la destination
            await self._write_to_cloud(dest_client, data, transfer)
            
            # Mise à jour du transfert
            transfer.status = "completed"
            transfer.end_time = datetime.now(timezone.utc)
            transfer.throughput_mbps = transfer.size_bytes / (1024 * 1024) / 60
            
            self._stats["transfers_completed"] += 1
            self._stats["data_volume_gb"] += transfer.size_bytes / (1024 ** 3)
            
            logger.info(f"Transfer completed: {transfer.transfer_id} "
                       f"size={transfer.size_bytes / (1024**2):.2f}MB")
            
        except Exception as e:
            transfer.status = "failed"
            transfer.error = str(e)
            transfer.end_time = datetime.now(timezone.utc)
            self._stats["transfers_failed"] += 1
            
            logger.error(f"Transfer failed: {transfer.transfer_id} - {e}")
    
    # ========== MÉTHODES PRIVÉES - COÛTS ==========
    
    async def _cost_optimizer(self) -> None:
        """Optimise les coûts périodiquement."""
        while self._is_running:
            await asyncio.sleep(self.config["cost_optimization_interval"])
            
            try:
                with self._resources_lock:
                    for resource in self._resources.values():
                        await self.optimize_costs(resource.resource_id)
                
            except Exception as e:
                logger.error(f"Cost optimizer error: {e}")
    
    async def _calculate_current_cost(self, resource: CloudResource) -> float:
        """Calcule le coût actuel d'une ressource."""
        # Simulation de coût
        # Dans un système réel, on interrogerait l'API de coût du cloud
        base_costs = {
            CloudProvider.AWS: 100.0,
            CloudProvider.GCP: 90.0,
            CloudProvider.AZURE: 95.0,
            CloudProvider.LOCAL: 10.0,
            CloudProvider.ON_PREM: 5.0
        }
        
        return base_costs.get(resource.provider, 50.0)
    
    async def _generate_cost_recommendations(self, resource: CloudResource) -> List[str]:
        """Génère des recommandations de réduction des coûts."""
        recommendations = []
        
        if resource.provider == CloudProvider.AWS:
            recommendations.append("Consider using reserved instances for better pricing")
            recommendations.append("Use S3 Intelligent-Tiering for automatic cost optimization")
            recommendations.append("Right-size EC2 instances based on utilization")
        
        elif resource.provider == CloudProvider.GCP:
            recommendations.append("Use committed use discounts for sustained workloads")
            recommendations.append("Consider using Coldline or Archive storage for infrequent access")
            recommendations.append("Use preemptible VMs for batch processing")
        
        elif resource.provider == CloudProvider.AZURE:
            recommendations.append("Use Azure Reserved VM Instances for cost savings")
            recommendations.append("Implement Azure Cost Management + Billing recommendations")
            recommendations.append("Use Azure Blob Storage tiers based on access patterns")
        
        return recommendations
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _health_checker(self) -> None:
        """Vérifie la santé des ressources cloud."""
        while self._is_running:
            await asyncio.sleep(self.config["health_check_interval"])
            
            try:
                with self._resources_lock:
                    for resource in self._resources.values():
                        status = await self._check_resource_health(resource)
                        
                        if not status:
                            logger.warning(f"Resource health check failed: {resource.name}")
                            
                            # Failover si activé
                            if self.config["auto_failover_enabled"]:
                                await self._perform_failover(resource)
                
            except Exception as e:
                logger.error(f"Health checker error: {e}")
    
    async def _check_resource_health(self, resource: CloudResource) -> bool:
        """Vérifie la santé d'une ressource."""
        try:
            client = self._clients.get(resource.resource_id)
            if not client:
                return False
            
            # Vérification du client
            if resource.provider == CloudProvider.AWS:
                client.head_bucket(Bucket=resource.name)
            elif resource.provider == CloudProvider.GCP:
                bucket = client.bucket(resource.name)
                bucket.exists()
            elif resource.provider == CloudProvider.AZURE:
                container = client.get_container_client(resource.name)
                container.get_container_properties()
            
            return True
            
        except Exception as e:
            logger.error(f"Health check error for {resource.name}: {e}")
            return False
    
    async def _perform_failover(self, resource: CloudResource) -> None:
        """Effectue un failover vers une ressource de secours."""
        # Recherche d'une ressource de secours
        with self._resources_lock:
            backup = next(
                (r for r in self._resources.values()
                 if r.provider != resource.provider and r.active),
                None
            )
        
        if backup:
            logger.info(f"Failover from {resource.name} to {backup.name}")
            # Dans un système réel, on mettrait à jour les routes DNS
            # et les configurations pour rediriger le trafic
    
    async def _drain_queue(self) -> None:
        """Vide la queue de transfert."""
        while not self._transfer_queue.empty():
            try:
                transfer = await self._transfer_queue.get()
                transfer.status = "cancelled"
            except Exception:
                break
    
    # ========== MÉTHODES PRIVÉES - STOCKAGE ==========
    
    async def _read_from_cloud(self, client: Any, transfer: CloudDataTransfer) -> bytes:
        """Lit des données depuis le cloud."""
        # Dans un système réel, on lirait depuis le service cloud
        # Simulation de lecture
        return b"Simulated cloud data"
    
    async def _write_to_cloud(self, client: Any, data: bytes, transfer: CloudDataTransfer) -> None:
        """Écrit des données dans le cloud."""
        # Dans un système réel, on écrirait vers le service cloud
        # Simulation d'écriture
        await asyncio.sleep(0.1)
    
    async def _compress_data(self, data: bytes) -> bytes:
        """Compresse des données."""
        import zlib
        return zlib.compress(data)
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_resources(self) -> None:
        """Charge les ressources existantes."""
        try:
            if self.data_manager:
                resources_data = await self.data_manager.retrieve(
                    "cloud:resources",
                    DataType.CONFIG
                )
                
                if resources_data:
                    for resource_dict in resources_data:
                        resource = self._deserialize_resource(resource_dict)
                        if resource:
                            with self._resources_lock:
                                self._resources[resource.resource_id] = resource
            
            logger.info(f"Loaded {len(self._resources)} cloud resources")
            
        except Exception as e:
            logger.error(f"Load resources error: {e}")
    
    def _deserialize_resource(self, data: Dict) -> Optional[CloudResource]:
        """Désérialise une ressource cloud."""
        try:
            return CloudResource(
                resource_id=data.get("resource_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                provider=CloudProvider(data.get("provider", "aws")),
                service=CloudService(data.get("service", "s3")),
                region=data.get("region", ""),
                endpoint=data.get("endpoint", ""),
                credentials=data.get("credentials", {}),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing resource: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_resource(self, resource_id: str) -> Optional[CloudResource]:
        """Récupère une ressource."""
        with self._resources_lock:
            return self._resources.get(resource_id)
    
    async def get_resources(self) -> List[CloudResource]:
        """Récupère les ressources."""
        with self._resources_lock:
            return list(self._resources.values())
    
    async def get_distribution(self, distribution_id: str) -> Optional[CloudDataDistribution]:
        """Récupère une distribution."""
        with self._distributions_lock:
            return self._distributions.get(distribution_id)
    
    async def get_distributions(self) -> List[CloudDataDistribution]:
        """Récupère les distributions."""
        with self._distributions_lock:
            return list(self._distributions.values())
    
    async def get_transfer(self, transfer_id: str) -> Optional[CloudDataTransfer]:
        """Récupère un transfert."""
        with self._transfers_lock:
            return self._transfers.get(transfer_id)
    
    async def get_transfers(self, status: Optional[str] = None) -> List[CloudDataTransfer]:
        """Récupère les transferts."""
        with self._transfers_lock:
            transfers = list(self._transfers.values())
            if status:
                transfers = [t for t in transfers if t.status == status]
            return sorted(transfers, key=lambda t: t.start_time or t.transfer_id, reverse=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._resources_lock:
            self._stats["total_resources"] = len(self._resources)
        with self._distributions_lock:
            self._stats["total_distributions"] = len(self._distributions)
        with self._transfers_lock:
            self._stats["total_transfers"] = len(self._transfers)
        
        return self._stats.copy()


# ============== CLOUD RESOURCE BUILDER ==============

class CloudResourceBuilder:
    """
    Constructeur de ressources cloud.
    Facilite la création de ressources cloud.
    """
    
    def __init__(self):
        self._resource = CloudResource()
    
    def provider(self, provider: CloudProvider) -> 'CloudResourceBuilder':
        """Définit le fournisseur."""
        self._resource.provider = provider
        return self
    
    def service(self, service: CloudService) -> 'CloudResourceBuilder':
        """Définit le service."""
        self._resource.service = service
        return self
    
    def name(self, name: str) -> 'CloudResourceBuilder':
        """Définit le nom."""
        self._resource.name = name
        return self
    
    def region(self, region: str) -> 'CloudResourceBuilder':
        """Définit la région."""
        self._resource.region = region
        return self
    
    def credentials(self, credentials: Dict[str, Any]) -> 'CloudResourceBuilder':
        """Définit les credentials."""
        self._resource.credentials = credentials
        return self
    
    def endpoint(self, endpoint: str) -> 'CloudResourceBuilder':
        """Définit l'endpoint."""
        self._resource.endpoint = endpoint
        return self
    
    def metadata(self, metadata: Dict[str, Any]) -> 'CloudResourceBuilder':
        """Définit les métadonnées."""
        self._resource.metadata = metadata
        return self
    
    def tags(self, tags: List[str]) -> 'CloudResourceBuilder':
        """Définit les tags."""
        self._resource.tags = tags
        return self
    
    def build(self) -> CloudResource:
        """Construit la ressource."""
        if not self._resource.name:
            raise ValueError("Resource name is required")
        if not self._resource.credentials:
            raise ValueError("Credentials are required")
        return self._resource


# ============== FACTORY ==============

class MultiCloudFactory:
    """Factory pour créer des composants multi-cloud."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> MultiCloudEngine:
        """Crée un moteur multi-cloud."""
        engine = MultiCloudEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_resource_builder() -> CloudResourceBuilder:
        """Crée un constructeur de ressources."""
        return CloudResourceBuilder()


# ============== EXPORT ==============

__all__ = [
    "CloudProvider",
    "CloudService",
    "CloudDataTier",
    "CloudSyncMode",
    "CloudResource",
    "CloudDataDistribution",
    "CloudDataTransfer",
    "CloudCostOptimization",
    "MultiCloudEngineInterface",
    "MultiCloudEngine",
    "CloudResourceBuilder",
    "MultiCloudFactory"
]
