# trading/bots/hedge_bot/hedge_bot_data_private_cloud.py
# Advanced Private Cloud & On-Premise Data Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Private Cloud Module - Module avancé de gestion des données en cloud privé et on-premise
pour le Hedge Bot. Gère le stockage local, la réplication, la haute disponibilité,
la sécurité renforcée et l'optimisation des coûts pour les données de hedging sensibles.
"""

import asyncio
import json
import time
import os
import shutil
import hashlib
import socket
import platform
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
import pickle
import zlib
from pathlib import Path
import aiofiles
import aiofiles.os
import psutil
import resource

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_private_cloud")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class StorageTier(Enum):
    """Tiers de stockage."""
    HOT = "hot"                      # Accès fréquent (SSD)
    WARM = "warm"                    # Accès modéré (HDD)
    COLD = "cold"                    # Accès rare (Archive)
    ARCHIVE = "archive"              # Archivage (Tape/Cloud)
    MEMORY = "memory"                # Cache mémoire


class ReplicationMode(Enum):
    """Modes de réplication."""
    SYNC = "sync"                    # Réplication synchrone
    ASYNC = "async"                  # Réplication asynchrone
    SEMI_SYNC = "semi_sync"          # Réplication semi-synchrone
    QUORUM = "quorum"                # Réplication par quorum


class ConsistencyLevel(Enum):
    """Niveaux de cohérence."""
    STRONG = "strong"                # Cohérence forte
    EVENTUAL = "eventual"            # Cohérence éventuelle
    SESSION = "session"              # Cohérence de session
    MONOTONIC = "monotonic"          # Cohérence monotone


# ============== DATA MODELS ==============

@dataclass
class PrivateCloudNode:
    """Nœud de cloud privé."""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    host: str = ""
    port: int = 0
    storage_path: str = ""
    max_storage_gb: float = 0.0
    used_storage_gb: float = 0.0
    status: str = "active"  # active, degraded, offline
    role: str = "primary"  # primary, secondary, replica
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PrivateCloudCluster:
    """Cluster de cloud privé."""
    cluster_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    nodes: List[str] = field(default_factory=list)
    replication_mode: ReplicationMode = ReplicationMode.ASYNC
    consistency_level: ConsistencyLevel = ConsistencyLevel.EVENTUAL
    replication_factor: int = 2
    health_status: str = "healthy"  # healthy, degraded, critical
    total_storage_gb: float = 0.0
    used_storage_gb: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PrivateCloudData:
    """Données en cloud privé."""
    data_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    key: str = ""
    value: Any = None
    data_type: DataType = DataType.MARKET
    tier: StorageTier = StorageTier.HOT
    node_id: str = ""
    cluster_id: str = ""
    size_bytes: int = 0
    checksum: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_access: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    encrypted: bool = False


# ============== INTERFACES ==============

class PrivateCloudEngineInterface(ABC):
    """Interface abstraite pour le moteur de cloud privé."""
    
    @abstractmethod
    async def create_cluster(self, cluster: PrivateCloudCluster) -> str:
        """Crée un cluster de cloud privé."""
        pass
    
    @abstractmethod
    async def add_node(self, cluster_id: str, node: PrivateCloudNode) -> bool:
        """Ajoute un nœud au cluster."""
        pass
    
    @abstractmethod
    async def store_data(self, data: PrivateCloudData) -> str:
        """Stocke des données dans le cloud privé."""
        pass
    
    @abstractmethod
    async def retrieve_data(self, key: str) -> Optional[PrivateCloudData]:
        """Récupère des données du cloud privé."""
        pass


# ============== IMPLÉMENTATION ==============

class PrivateCloudEngine(PrivateCloudEngineInterface):
    """
    Moteur de cloud privé avancé pour le Hedge Bot.
    Gère le stockage local, la réplication et la haute disponibilité.
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
        
        # Gestion des clusters
        self._clusters: Dict[str, PrivateCloudCluster] = {}
        self._clusters_lock = threading.RLock()
        
        # Gestion des nœuds
        self._nodes: Dict[str, PrivateCloudNode] = {}
        self._nodes_lock = threading.RLock()
        
        # Gestion des données
        self._data: Dict[str, PrivateCloudData] = {}
        self._data_lock = threading.RLock()
        
        # Cache mémoire
        self._memory_cache: Dict[str, PrivateCloudData] = {}
        self._cache_lock = threading.RLock()
        
        # Index
        self._index: Dict[str, Dict[str, str]] = defaultdict(dict)
        self._index_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "clusters_created": 0,
            "nodes_added": 0,
            "data_stored": 0,
            "data_retrieved": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_storage_gb": 0.0,
            "used_storage_gb": 0.0,
            "replication_events": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # Base path
        self._base_path = Path(self.config.get("base_path", "./private_cloud"))
        self._base_path.mkdir(parents=True, exist_ok=True)
        
        # État
        self._is_running = False
        
        logger.info("PrivateCloudEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "base_path": "./private_cloud",
            "replication_factor": 2,
            "storage_tiering": True,
            "enable_cache": True,
            "cache_size_mb": 1024,
            "max_storage_gb": 100,
            "replication_interval": 3600,
            "health_check_interval": 60,
            "auto_tiering_interval": 86400,
            "compression_enabled": True,
            "compression_threshold": 1024,
            "encryption_enabled": True,
            "cache_ttl": 3600,
            "data_retention_days": 365
        }
    
    async def start(self) -> None:
        """Démarre le moteur de cloud privé."""
        logger.info("PrivateCloudEngine starting...")
        self._is_running = True
        
        # Création des dossiers de stockage
        for tier in StorageTier:
            tier_path = self._base_path / tier.value
            tier_path.mkdir(parents=True, exist_ok=True)
        
        # Chargement des clusters
        await self._load_clusters()
        
        # Chargement des nœuds
        await self._load_nodes()
        
        # Chargement des données
        await self._load_data()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._replication_loop())
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._auto_tiering_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("PrivateCloudEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de cloud privé."""
        logger.info("PrivateCloudEngine stopping...")
        self._is_running = False
        
        # Sauvegarde des métadonnées
        await self._save_metadata()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("PrivateCloudEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_cluster(self, cluster: PrivateCloudCluster) -> str:
        """Crée un cluster de cloud privé."""
        with self._clusters_lock:
            self._clusters[cluster.cluster_id] = cluster
            self._stats["clusters_created"] += 1
        
        # Création du dossier du cluster
        cluster_path = self._base_path / "clusters" / cluster.cluster_id
        cluster_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Private cloud cluster created: {cluster.name} (id={cluster.cluster_id})")
        return cluster.cluster_id
    
    async def add_node(self, cluster_id: str, node: PrivateCloudNode) -> bool:
        """Ajoute un nœud au cluster."""
        with self._clusters_lock:
            cluster = self._clusters.get(cluster_id)
            if not cluster:
                return False
            
            cluster.nodes.append(node.node_id)
        
        with self._nodes_lock:
            self._nodes[node.node_id] = node
            self._stats["nodes_added"] += 1
        
        # Création du dossier du nœud
        node_path = self._base_path / "nodes" / node.node_id
        node_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Node added to cluster: {node.name} (id={node.node_id})")
        return True
    
    async def store_data(self, data: PrivateCloudData) -> str:
        """Stocke des données dans le cloud privé."""
        self._stats["data_stored"] += 1
        
        try:
            # Vérification de l'espace disponible
            if not await self._check_available_space(data.size_bytes):
                # Tentative de libération d'espace
                await self._free_space(data.size_bytes)
            
            # Chiffrement
            if self.config["encryption_enabled"] and self.encryption_engine:
                encrypted = await self.encryption_engine.encrypt(
                    pickle.dumps(data.value),
                    "private_cloud_key"
                )
                data.value = encrypted
                data.encrypted = True
            
            # Détermination du tier
            if self.config["storage_tiering"]:
                data.tier = await self._determine_tier(data)
            
            # Stockage selon le tier
            if data.tier == StorageTier.MEMORY:
                await self._store_in_memory(data)
            elif data.tier == StorageTier.HOT:
                await self._store_on_disk(data, "hot")
            elif data.tier == StorageTier.WARM:
                await self._store_on_disk(data, "warm")
            elif data.tier == StorageTier.COLD:
                await self._store_on_disk(data, "cold")
            elif data.tier == StorageTier.ARCHIVE:
                await self._store_on_disk(data, "archive")
            
            # Indexation
            await self._index_data(data)
            
            # Réplication
            await self._replicate_data(data)
            
            # Mise à jour des métriques
            self._stats["total_storage_gb"] += data.size_bytes / (1024 ** 3)
            self._stats["used_storage_gb"] += data.size_bytes / (1024 ** 3)
            
            # Stockage des métadonnées
            with self._data_lock:
                self._data[data.data_id] = data
            
            logger.info(f"Data stored: {data.key} (id={data.data_id}) tier={data.tier.value}")
            return data.data_id
            
        except Exception as e:
            logger.error(f"Store data error: {e}")
            raise
    
    async def retrieve_data(self, key: str) -> Optional[PrivateCloudData]:
        """Récupère des données du cloud privé."""
        self._stats["data_retrieved"] += 1
        
        # Vérification du cache
        with self._cache_lock:
            if key in self._memory_cache:
                self._stats["cache_hits"] += 1
                data = self._memory_cache[key]
                data.access_count += 1
                data.last_access = datetime.now(timezone.utc)
                return data
        
        self._stats["cache_misses"] += 1
        
        # Recherche dans l'index
        with self._index_lock:
            if key in self._index:
                data_id = self._index[key].get("data_id")
                if data_id:
                    with self._data_lock:
                        data = self._data.get(data_id)
                        if data:
                            # Chargement depuis le stockage
                            loaded_data = await self._load_from_storage(data)
                            if loaded_data:
                                # Mise en cache
                                await self._cache_data(loaded_data)
                                return loaded_data
        
        return None
    
    # ========== MÉTHODES PRIVÉES - STOCKAGE ==========
    
    async def _store_in_memory(self, data: PrivateCloudData) -> None:
        """Stocke des données en mémoire."""
        with self._cache_lock:
            self._memory_cache[data.key] = data
            
            # Limitation du cache
            cache_size_mb = self.config["cache_size_mb"]
            current_size_mb = sum(d.size_bytes for d in self._memory_cache.values()) / (1024 ** 2)
            
            if current_size_mb > cache_size_mb:
                # Éviction LRU
                oldest = min(self._memory_cache.items(), key=lambda x: x[1].last_access or x[1].created_at)
                del self._memory_cache[oldest[0]]
    
    async def _store_on_disk(self, data: PrivateCloudData, tier: str) -> None:
        """Stocke des données sur disque."""
        tier_path = self._base_path / tier / data.data_id
        tier_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Sérialisation
        serialized = pickle.dumps(data)
        
        # Compression
        if self.config["compression_enabled"] and len(serialized) > self.config["compression_threshold"]:
            serialized = zlib.compress(serialized)
        
        # Écriture asynchrone
        async with aiofiles.open(tier_path, 'wb') as f:
            await f.write(serialized)
    
    async def _load_from_storage(self, data: PrivateCloudData) -> Optional[PrivateCloudData]:
        """Charge des données depuis le stockage."""
        try:
            tier_path = self._base_path / data.tier.value / data.data_id
            
            if not tier_path.exists():
                # Recherche dans les autres tiers
                for tier in StorageTier:
                    alt_path = self._base_path / tier.value / data.data_id
                    if alt_path.exists():
                        tier_path = alt_path
                        break
                else:
                    return None
            
            # Lecture asynchrone
            async with aiofiles.open(tier_path, 'rb') as f:
                serialized = await f.read()
            
            # Décompression
            try:
                serialized = zlib.decompress(serialized)
            except zlib.error:
                pass  # Pas compressé
            
            # Désérialisation
            loaded_data = pickle.loads(serialized)
            
            # Déchiffrement
            if loaded_data.encrypted and self.encryption_engine:
                decrypted = await self.encryption_engine.decrypt(loaded_data.value)
                loaded_data.value = pickle.loads(decrypted)
            
            return loaded_data
            
        except Exception as e:
            logger.error(f"Load from storage error: {e}")
            return None
    
    async def _cache_data(self, data: PrivateCloudData) -> None:
        """Met en cache des données."""
        if self.config["enable_cache"] and data.tier != StorageTier.MEMORY:
            with self._cache_lock:
                self._memory_cache[data.key] = data
    
    # ========== MÉTHODES PRIVÉES - INDEX ==========
    
    async def _index_data(self, data: PrivateCloudData) -> None:
        """Indexe des données."""
        with self._index_lock:
            self._index[data.key] = {
                "data_id": data.data_id,
                "data_type": data.data_type.value,
                "tier": data.tier.value,
                "node_id": data.node_id,
                "cluster_id": data.cluster_id
            }
    
    # ========== MÉTHODES PRIVÉES - TIERING ==========
    
    async def _determine_tier(self, data: PrivateCloudData) -> StorageTier:
        """Détermine le tier de stockage."""
        # Règles de tiering
        if data.size_bytes < 1024:  # < 1KB
            return StorageTier.MEMORY
        elif data.access_count > 100:
            return StorageTier.HOT
        elif data.access_count > 10:
            return StorageTier.WARM
        elif data.access_count > 1:
            return StorageTier.COLD
        else:
            return StorageTier.ARCHIVE
    
    # ========== MÉTHODES PRIVÉES - RÉPLICATION ==========
    
    async def _replicate_data(self, data: PrivateCloudData) -> None:
        """Réplique des données."""
        with self._clusters_lock:
            cluster = self._clusters.get(data.cluster_id)
            if not cluster:
                return
        
        # Récupération des nœuds de réplication
        with self._nodes_lock:
            replicas = [n for n in self._nodes.values() if n.node_id in cluster.nodes and n.node_id != data.node_id]
        
        # Réplication
        for replica in replicas[:cluster.replication_factor - 1]:
            try:
                # Dans un système réel, on enverrait les données au nœud réplica
                self._stats["replication_events"] += 1
                logger.debug(f"Replicating data to {replica.name}")
            except Exception as e:
                logger.error(f"Replication error: {e}")
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _replication_loop(self) -> None:
        """Boucle de réplication."""
        while self._is_running:
            await asyncio.sleep(self.config["replication_interval"])
            
            try:
                # Vérification de la réplication
                with self._data_lock:
                    for data in self._data.values():
                        # Vérification du nombre de réplicas
                        pass
                
            except Exception as e:
                logger.error(f"Replication loop error: {e}")
    
    async def _health_check_loop(self) -> None:
        """Boucle de vérification de santé."""
        while self._is_running:
            await asyncio.sleep(self.config["health_check_interval"])
            
            try:
                # Vérification des nœuds
                with self._nodes_lock:
                    for node in self._nodes.values():
                        # Vérification de l'espace disponible
                        usage = await self._get_node_usage(node)
                        node.used_storage_gb = usage
                        
                        if usage > node.max_storage_gb * 0.9:
                            node.status = "degraded"
                        elif usage > node.max_storage_gb:
                            node.status = "offline"
                        else:
                            node.status = "active"
                
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
    
    async def _auto_tiering_loop(self) -> None:
        """Boucle de tiering automatique."""
        if not self.config["storage_tiering"]:
            return
        
        while self._is_running:
            await asyncio.sleep(self.config["auto_tiering_interval"])
            
            try:
                # Réévaluation des tiers
                with self._data_lock:
                    for data in self._data.values():
                        new_tier = await self._determine_tier(data)
                        if new_tier != data.tier:
                            # Déplacement des données
                            await self._move_data(data, new_tier)
                
            except Exception as e:
                logger.error(f"Auto-tiering loop error: {e}")
    
    async def _move_data(self, data: PrivateCloudData, new_tier: StorageTier) -> None:
        """Déplace des données entre tiers."""
        old_tier = data.tier
        
        # Chargement des données
        loaded = await self._load_from_storage(data)
        if not loaded:
            return
        
        # Stockage dans le nouveau tier
        data.tier = new_tier
        await self._store_on_disk(data, new_tier.value)
        
        # Suppression de l'ancien tier
        old_path = self._base_path / old_tier.value / data.data_id
        if old_path.exists():
            old_path.unlink()
        
        logger.info(f"Data moved: {data.key} {old_tier.value} -> {new_tier.value}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    # Suppression des entrées expirées
                    now = datetime.now(timezone.utc)
                    expired = [
                        key for key, data in self._memory_cache.items()
                        if data.expires_at and data.expires_at < now
                    ]
                    for key in expired:
                        del self._memory_cache[key]
                    
                    # Limitation de la taille du cache
                    cache_size_mb = self.config["cache_size_mb"]
                    current_size_mb = sum(d.size_bytes for d in self._memory_cache.values()) / (1024 ** 2)
                    
                    if current_size_mb > cache_size_mb:
                        # Éviction LRU
                        sorted_items = sorted(
                            self._memory_cache.items(),
                            key=lambda x: x[1].last_access or x[1].created_at
                        )
                        for key, _ in sorted_items[:len(self._memory_cache) - 100]:
                            del self._memory_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._data_lock:
                    self._stats["total_data"] = len(self._data)
                with self._cache_lock:
                    self._stats["cache_size"] = len(self._memory_cache)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "private_cloud:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PRIVÉES - CHARGEMENT ==========
    
    async def _load_clusters(self) -> None:
        """Charge les clusters existants."""
        try:
            if self.data_manager:
                clusters_data = await self.data_manager.retrieve(
                    "private_cloud:clusters",
                    DataType.CONFIG
                )
                
                if clusters_data:
                    for c_dict in clusters_data:
                        cluster = self._deserialize_cluster(c_dict)
                        if cluster:
                            with self._clusters_lock:
                                self._clusters[cluster.cluster_id] = cluster
            
            logger.info(f"Loaded {len(self._clusters)} clusters")
            
        except Exception as e:
            logger.error(f"Load clusters error: {e}")
    
    async def _load_nodes(self) -> None:
        """Charge les nœuds existants."""
        try:
            if self.data_manager:
                nodes_data = await self.data_manager.retrieve(
                    "private_cloud:nodes",
                    DataType.CONFIG
                )
                
                if nodes_data:
                    for n_dict in nodes_data:
                        node = self._deserialize_node(n_dict)
                        if node:
                            with self._nodes_lock:
                                self._nodes[node.node_id] = node
            
            logger.info(f"Loaded {len(self._nodes)} nodes")
            
        except Exception as e:
            logger.error(f"Load nodes error: {e}")
    
    async def _load_data(self) -> None:
        """Charge les données existantes."""
        try:
            # Parcours des dossiers de stockage
            for tier in StorageTier:
                tier_path = self._base_path / tier.value
                if tier_path.exists():
                    for data_path in tier_path.glob("*"):
                        try:
                            # Lecture des métadonnées
                            async with aiofiles.open(data_path, 'rb') as f:
                                serialized = await f.read()
                            
                            # Désérialisation
                            data = pickle.loads(serialized)
                            if data:
                                with self._data_lock:
                                    self._data[data.data_id] = data
                                
                                # Indexation
                                await self._index_data(data)
                                
                        except Exception as e:
                            logger.error(f"Load data error for {data_path}: {e}")
            
            logger.info(f"Loaded {len(self._data)} data items")
            
        except Exception as e:
            logger.error(f"Load data error: {e}")
    
    async def _save_metadata(self) -> None:
        """Sauvegarde les métadonnées."""
        try:
            if self.data_manager:
                with self._clusters_lock:
                    for cluster in self._clusters.values():
                        await self.data_manager.store(
                            f"private_cloud:cluster:{cluster.cluster_id}",
                            cluster.to_dict(),
                            DataType.CONFIG
                        )
                
                with self._nodes_lock:
                    for node in self._nodes.values():
                        await self.data_manager.store(
                            f"private_cloud:node:{node.node_id}",
                            node.to_dict(),
                            DataType.CONFIG
                        )
            
            logger.info("Metadata saved")
            
        except Exception as e:
            logger.error(f"Save metadata error: {e}")
    
    def _deserialize_cluster(self, data: Dict) -> Optional[PrivateCloudCluster]:
        """Désérialise un cluster."""
        try:
            return PrivateCloudCluster(
                cluster_id=data.get("cluster_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                nodes=data.get("nodes", []),
                replication_mode=ReplicationMode(data.get("replication_mode", "async")),
                consistency_level=ConsistencyLevel(data.get("consistency_level", "eventual")),
                replication_factor=data.get("replication_factor", 2),
                health_status=data.get("health_status", "healthy"),
                total_storage_gb=data.get("total_storage_gb", 0.0),
                used_storage_gb=data.get("used_storage_gb", 0.0),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing cluster: {e}")
            return None
    
    def _deserialize_node(self, data: Dict) -> Optional[PrivateCloudNode]:
        """Désérialise un nœud."""
        try:
            return PrivateCloudNode(
                node_id=data.get("node_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                host=data.get("host", ""),
                port=data.get("port", 0),
                storage_path=data.get("storage_path", ""),
                max_storage_gb=data.get("max_storage_gb", 0.0),
                used_storage_gb=data.get("used_storage_gb", 0.0),
                status=data.get("status", "active"),
                role=data.get("role", "primary"),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing node: {e}")
            return None
    
    # ========== MÉTHODES PRIVÉES - UTILITAIRES ==========
    
    async def _check_available_space(self, required_bytes: int) -> bool:
        """Vérifie l'espace disponible."""
        total, used, free = shutil.disk_usage(self._base_path)
        free_gb = free / (1024 ** 3)
        return free_gb > required_bytes / (1024 ** 3) * 1.1
    
    async def _free_space(self, required_bytes: int) -> None:
        """Libère de l'espace."""
        # Suppression des données expirées
        with self._data_lock:
            now = datetime.now(timezone.utc)
            expired = [
                data_id for data_id, data in self._data.items()
                if data.expires_at and data.expires_at < now
            ]
            for data_id in expired:
                del self._data[data_id]
    
    async def _get_node_usage(self, node: PrivateCloudNode) -> float:
        """Récupère l'utilisation d'un nœud."""
        # Simulation de l'utilisation
        return np.random.uniform(0, node.max_storage_gb)
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_cluster(self, cluster_id: str) -> Optional[PrivateCloudCluster]:
        """Récupère un cluster."""
        with self._clusters_lock:
            return self._clusters.get(cluster_id)
    
    async def get_clusters(self) -> List[PrivateCloudCluster]:
        """Récupère les clusters."""
        with self._clusters_lock:
            return list(self._clusters.values())
    
    async def get_node(self, node_id: str) -> Optional[PrivateCloudNode]:
        """Récupère un nœud."""
        with self._nodes_lock:
            return self._nodes.get(node_id)
    
    async def get_nodes(self) -> List[PrivateCloudNode]:
        """Récupère les nœuds."""
        with self._nodes_lock:
            return list(self._nodes.values())
    
    async def delete_data(self, key: str) -> bool:
        """Supprime des données."""
        with self._data_lock:
            for data_id, data in list(self._data.items()):
                if data.key == key:
                    del self._data[data_id]
                    
                    # Suppression du cache
                    with self._cache_lock:
                        if key in self._memory_cache:
                            del self._memory_cache[key]
                    
                    # Suppression de l'index
                    with self._index_lock:
                        if key in self._index:
                            del self._index[key]
                    
                    # Suppression du stockage
                    tier_path = self._base_path / data.tier.value / data.data_id
                    if tier_path.exists():
                        tier_path.unlink()
                    
                    return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._data_lock:
            self._stats["total_data"] = len(self._data)
        with self._cache_lock:
            self._stats["cache_size"] = len(self._memory_cache)
        
        return self._stats.copy()


# ============== PRIVATE CLOUD NODE BUILDER ==============

class PrivateCloudNodeBuilder:
    """
    Constructeur de nœuds de cloud privé.
    Facilite la création de nœuds de cloud privé.
    """
    
    def __init__(self):
        self._node = PrivateCloudNode()
    
    def name(self, name: str) -> 'PrivateCloudNodeBuilder':
        """Définit le nom."""
        self._node.name = name
        return self
    
    def host(self, host: str) -> 'PrivateCloudNodeBuilder':
        """Définit l'hôte."""
        self._node.host = host
        return self
    
    def port(self, port: int) -> 'PrivateCloudNodeBuilder':
        """Définit le port."""
        self._node.port = port
        return self
    
    def storage_path(self, path: str) -> 'PrivateCloudNodeBuilder':
        """Définit le chemin de stockage."""
        self._node.storage_path = path
        return self
    
    def max_storage_gb(self, max_storage: float) -> 'PrivateCloudNodeBuilder':
        """Définit le stockage maximum."""
        self._node.max_storage_gb = max_storage
        return self
    
    def role(self, role: str) -> 'PrivateCloudNodeBuilder':
        """Définit le rôle."""
        self._node.role = role
        return self
    
    def metadata(self, metadata: Dict[str, Any]) -> 'PrivateCloudNodeBuilder':
        """Définit les métadonnées."""
        self._node.metadata = metadata
        return self
    
    def tags(self, tags: List[str]) -> 'PrivateCloudNodeBuilder':
        """Définit les tags."""
        self._node.tags = tags
        return self
    
    def build(self) -> PrivateCloudNode:
        """Construit le nœud."""
        return self._node


# ============== FACTORY ==============

class PrivateCloudFactory:
    """Factory pour créer des composants de cloud privé."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PrivateCloudEngine:
        """Crée un moteur de cloud privé."""
        engine = PrivateCloudEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_node_builder() -> PrivateCloudNodeBuilder:
        """Crée un constructeur de nœuds."""
        return PrivateCloudNodeBuilder()


# ============== EXPORT ==============

__all__ = [
    "StorageTier",
    "ReplicationMode",
    "ConsistencyLevel",
    "PrivateCloudNode",
    "PrivateCloudCluster",
    "PrivateCloudData",
    "PrivateCloudEngineInterface",
    "PrivateCloudEngine",
    "PrivateCloudNodeBuilder",
    "PrivateCloudFactory"
]
