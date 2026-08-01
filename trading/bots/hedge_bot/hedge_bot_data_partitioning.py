# trading/bots/hedge_bot/hedge_bot_data_partitioning.py
# Advanced Data Partitioning & Sharding Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Partitioning Module - Module avancé de partitionnement et de sharding des données
pour le Hedge Bot. Gère le partitionnement des données, le sharding, l'équilibrage de charge,
la distribution des données, et l'optimisation des requêtes pour le système de hedging.
"""

import asyncio
import json
import time
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import concurrent.futures
import zlib
import pickle
from pathlib import Path

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_partitioning")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class PartitionStrategy(Enum):
    """Stratégies de partitionnement."""
    RANGE = "range"                    # Partitionnement par plage
    HASH = "hash"                      # Partitionnement par hachage
    LIST = "list"                      # Partitionnement par liste
    ROUND_ROBIN = "round_robin"        # Partitionnement en round-robin
    COMPOSITE = "composite"            # Partitionnement composite
    TIME_BASED = "time_based"          # Partitionnement temporel
    KEY_BASED = "key_based"            # Partitionnement par clé
    CUSTOM = "custom"                  # Partitionnement personnalisé


class ShardType(Enum):
    """Types de shards."""
    HORIZONTAL = "horizontal"          # Sharding horizontal
    VERTICAL = "vertical"              # Sharding vertical
    DIRECTORY = "directory"            # Sharding par répertoire
    HYBRID = "hybrid"                  # Sharding hybride


class RebalanceStrategy(Enum):
    """Stratégies de rééquilibrage."""
    NO_REBALANCE = "no_rebalance"      # Pas de rééquilibrage
    MANUAL = "manual"                  # Rééquilibrage manuel
    AUTOMATIC = "automatic"            # Rééquilibrage automatique
    THRESHOLD = "threshold"            # Rééquilibrage par seuil
    SCHEDULED = "scheduled"            # Rééquilibrage programmé


# ============== DATA MODELS ==============

@dataclass
class Partition:
    """Modèle de partition."""
    partition_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy: PartitionStrategy = PartitionStrategy.RANGE
    key: str = ""
    min_value: Any = None
    max_value: Any = None
    shard_id: str = ""
    data_type: DataType = DataType.MARKET
    row_count: int = 0
    size_bytes: int = 0
    location: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True


@dataclass
class Shard:
    """Modèle de shard."""
    shard_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    shard_type: ShardType = ShardType.HORIZONTAL
    partitions: List[str] = field(default_factory=list)
    node_id: str = ""
    host: str = ""
    port: int = 0
    status: str = "active"
    load: float = 0.0
    capacity: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PartitionQuery:
    """Requête de partition."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data_type: DataType = DataType.MARKET
    partition_key: str = ""
    partition_value: Any = None
    shard_id: Optional[str] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: int = 1000
    offset: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PartitionStats:
    """Statistiques de partition."""
    stats_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_partitions: int = 0
    total_shards: int = 0
    total_rows: int = 0
    total_size_bytes: int = 0
    avg_partition_size: float = 0.0
    max_partition_size: float = 0.0
    min_partition_size: float = 0.0
    distribution: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============== INTERFACES ==============

class PartitionEngineInterface(ABC):
    """Interface abstraite pour le moteur de partitionnement."""
    
    @abstractmethod
    async def create_partition(self, partition: Partition) -> str:
        """Crée une partition."""
        pass
    
    @abstractmethod
    async def create_shard(self, shard: Shard) -> str:
        """Crée un shard."""
        pass
    
    @abstractmethod
    async def get_partition(self, key: str, value: Any) -> Optional[Partition]:
        """Récupère la partition pour une clé."""
        pass
    
    @abstractmethod
    async def rebalance(self, strategy: RebalanceStrategy) -> bool:
        """Rééquilibre les partitions."""
        pass


# ============== IMPLÉMENTATION ==============

class PartitionEngine(PartitionEngineInterface):
    """
    Moteur de partitionnement avancé pour le Hedge Bot.
    Gère le partitionnement des données, le sharding et l'équilibrage.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des partitions
        self._partitions: Dict[str, Partition] = {}
        self._partitions_lock = threading.RLock()
        
        # Gestion des shards
        self._shards: Dict[str, Shard] = {}
        self._shards_lock = threading.RLock()
        
        # Index des partitions
        self._partition_index: Dict[str, Dict[Any, str]] = defaultdict(dict)
        self._index_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "partitions_created": 0,
            "shards_created": 0,
            "rebalances_performed": 0,
            "total_rows": 0,
            "total_size_mb": 0.0,
            "avg_partition_load": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        # Base path
        self._base_path = Path(self.config.get("base_path", "./partition_data"))
        self._base_path.mkdir(parents=True, exist_ok=True)
        
        logger.info("PartitionEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "base_path": "./partition_data",
            "default_strategy": PartitionStrategy.RANGE,
            "default_shard_type": ShardType.HORIZONTAL,
            "rebalance_threshold": 0.8,
            "min_partition_size": 1000,
            "max_partition_size": 1000000,
            "hash_partitions": 16,
            "enable_auto_rebalance": True,
            "rebalance_interval": 3600,
            "cache_size": 1000,
            "enable_cache": True
        }
    
    async def start(self) -> None:
        """Démarre le moteur de partitionnement."""
        logger.info("PartitionEngine starting...")
        self._is_running = True
        
        # Chargement des partitions existantes
        await self._load_partitions()
        
        # Chargement des shards existants
        await self._load_shards()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._rebalance_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("PartitionEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de partitionnement."""
        logger.info("PartitionEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("PartitionEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_partition(self, partition: Partition) -> str:
        """Crée une partition."""
        with self._partitions_lock:
            self._partitions[partition.partition_id] = partition
            self._stats["partitions_created"] += 1
        
        # Création du dossier
        partition_path = self._base_path / partition.partition_id
        partition_path.mkdir(parents=True, exist_ok=True)
        
        # Mise à jour de l'index
        with self._index_lock:
            self._partition_index[partition.data_type.value][partition.key] = partition.partition_id
        
        # Stockage des métadonnées
        metadata_path = partition_path / "_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(partition.to_dict(), f, indent=2)
        
        logger.info(f"Partition created: {partition.name} (id={partition.partition_id})")
        return partition.partition_id
    
    async def create_shard(self, shard: Shard) -> str:
        """Crée un shard."""
        with self._shards_lock:
            self._shards[shard.shard_id] = shard
            self._stats["shards_created"] += 1
        
        # Création du dossier
        shard_path = self._base_path / shard.shard_id
        shard_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Shard created: {shard.name} (id={shard.shard_id})")
        return shard.shard_id
    
    async def get_partition(self, key: str, value: Any) -> Optional[Partition]:
        """Récupère la partition pour une clé."""
        # Vérification du cache
        cache_key = f"{key}_{value}"
        with self._index_lock:
            if cache_key in self._partition_index:
                partition_id = self._partition_index[cache_key]
                with self._partitions_lock:
                    return self._partitions.get(partition_id)
        
        # Recherche dans les partitions
        with self._partitions_lock:
            for partition in self._partitions.values():
                if partition.key == key:
                    # Vérification selon la stratégie
                    if partition.strategy == PartitionStrategy.RANGE:
                        if partition.min_value <= value <= partition.max_value:
                            return partition
                    elif partition.strategy == PartitionStrategy.HASH:
                        if hash(value) % len(self._partitions) == int(partition.partition_id[-1]):
                            return partition
                    elif partition.strategy == PartitionStrategy.LIST:
                        if value in partition.metadata.get("values", []):
                            return partition
        
        return None
    
    async def rebalance(self, strategy: RebalanceStrategy) -> bool:
        """Rééquilibre les partitions."""
        self._stats["rebalances_performed"] += 1
        
        try:
            # Analyse de la distribution
            distribution = await self._analyze_distribution()
            
            if strategy == RebalanceStrategy.AUTOMATIC:
                return await self._auto_rebalance(distribution)
            elif strategy == RebalanceStrategy.THRESHOLD:
                return await self._threshold_rebalance(distribution)
            elif strategy == RebalanceStrategy.MANUAL:
                return await self._manual_rebalance()
            else:
                return False
                
        except Exception as e:
            logger.error(f"Rebalance error: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - RÉÉQUILIBRAGE ==========
    
    async def _analyze_distribution(self) -> Dict[str, float]:
        """Analyse la distribution des données."""
        distribution = {}
        
        with self._partitions_lock:
            for partition in self._partitions.values():
                distribution[partition.partition_id] = partition.row_count
        
        return distribution
    
    async def _auto_rebalance(self, distribution: Dict[str, float]) -> bool:
        """Rééquilibrage automatique."""
        # Calcul de la moyenne
        avg = sum(distribution.values()) / len(distribution) if distribution else 0
        
        # Identification des partitions déséquilibrées
        over = [pid for pid, count in distribution.items() if count > avg * 1.5]
        under = [pid for pid, count in distribution.items() if count < avg * 0.5]
        
        if not over or not under:
            return True
        
        # Rééquilibrage
        for over_id in over:
            for under_id in under:
                # Transfert de données
                await self._transfer_data(over_id, under_id, int(avg * 0.5))
        
        return True
    
    async def _threshold_rebalance(self, distribution: Dict[str, float]) -> bool:
        """Rééquilibrage par seuil."""
        threshold = self.config["rebalance_threshold"]
        
        for pid, count in distribution.items():
            with self._partitions_lock:
                partition = self._partitions.get(pid)
                if not partition:
                    continue
                
                # Vérification du seuil
                if count > partition.max_value * threshold:
                    # Split de la partition
                    await self._split_partition(pid)
                elif count < partition.min_value * (1 - threshold):
                    # Merge de la partition
                    await self._merge_partition(pid)
        
        return True
    
    async def _manual_rebalance(self) -> bool:
        """Rééquilibrage manuel."""
        # Dans un système réel, on attendrait des instructions manuelles
        return True
    
    async def _transfer_data(self, source_id: str, dest_id: str, amount: int) -> bool:
        """Transfère des données entre partitions."""
        # Dans un système réel, on déplacerait les données
        logger.info(f"Transferring {amount} rows from {source_id} to {dest_id}")
        return True
    
    async def _split_partition(self, partition_id: str) -> bool:
        """Split une partition."""
        # Dans un système réel, on diviserait la partition
        logger.info(f"Splitting partition {partition_id}")
        return True
    
    async def _merge_partition(self, partition_id: str) -> bool:
        """Merge une partition."""
        # Dans un système réel, on fusionnerait la partition
        logger.info(f"Merging partition {partition_id}")
        return True
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _rebalance_loop(self) -> None:
        """Boucle de rééquilibrage automatique."""
        if not self.config["enable_auto_rebalance"]:
            return
        
        while self._is_running:
            await asyncio.sleep(self.config["rebalance_interval"])
            
            try:
                await self.rebalance(RebalanceStrategy.AUTOMATIC)
                
            except Exception as e:
                logger.error(f"Rebalance loop error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._partitions_lock:
                    self._stats["total_partitions"] = len(self._partitions)
                    total_rows = sum(p.row_count for p in self._partitions.values())
                    self._stats["total_rows"] = total_rows
                
                with self._shards_lock:
                    self._stats["total_shards"] = len(self._shards)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "partition:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_partitions(self) -> None:
        """Charge les partitions existantes."""
        try:
            for partition_dir in self._base_path.iterdir():
                if partition_dir.is_dir():
                    metadata_path = partition_dir / "_metadata.json"
                    if metadata_path.exists():
                        with open(metadata_path, 'r') as f:
                            data = json.load(f)
                        
                        partition = self._deserialize_partition(data)
                        if partition:
                            with self._partitions_lock:
                                self._partitions[partition.partition_id] = partition
                            
                            # Mise à jour de l'index
                            with self._index_lock:
                                self._partition_index[partition.data_type.value][partition.key] = partition.partition_id
            
            logger.info(f"Loaded {len(self._partitions)} partitions")
            
        except Exception as e:
            logger.error(f"Load partitions error: {e}")
    
    async def _load_shards(self) -> None:
        """Charge les shards existants."""
        try:
            # Dans un système réel, on chargerait les shards depuis une base de données
            pass
            
        except Exception as e:
            logger.error(f"Load shards error: {e}")
    
    def _deserialize_partition(self, data: Dict) -> Optional[Partition]:
        """Désérialise une partition."""
        try:
            return Partition(
                partition_id=data.get("partition_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                strategy=PartitionStrategy(data.get("strategy", "range")),
                key=data.get("key", ""),
                min_value=data.get("min_value"),
                max_value=data.get("max_value"),
                shard_id=data.get("shard_id", ""),
                data_type=DataType(data.get("data_type", "market")),
                row_count=data.get("row_count", 0),
                size_bytes=data.get("size_bytes", 0),
                location=data.get("location", ""),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                active=data.get("active", True)
            )
        except Exception as e:
            logger.error(f"Error deserializing partition: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_partition_by_id(self, partition_id: str) -> Optional[Partition]:
        """Récupère une partition par son ID."""
        with self._partitions_lock:
            return self._partitions.get(partition_id)
    
    async def get_partitions(self, data_type: Optional[DataType] = None) -> List[Partition]:
        """Récupère les partitions."""
        with self._partitions_lock:
            partitions = list(self._partitions.values())
            if data_type:
                partitions = [p for p in partitions if p.data_type == data_type]
            return partitions
    
    async def get_shard(self, shard_id: str) -> Optional[Shard]:
        """Récupère un shard."""
        with self._shards_lock:
            return self._shards.get(shard_id)
    
    async def get_shards(self) -> List[Shard]:
        """Récupère les shards."""
        with self._shards_lock:
            return list(self._shards.values())
    
    async def assign_partition_to_shard(self, partition_id: str, shard_id: str) -> bool:
        """Assigne une partition à un shard."""
        with self._partitions_lock:
            partition = self._partitions.get(partition_id)
            if not partition:
                return False
            
            partition.shard_id = shard_id
            partition.updated_at = datetime.now(timezone.utc)
            
            with self._shards_lock:
                shard = self._shards.get(shard_id)
                if shard:
                    if partition_id not in shard.partitions:
                        shard.partitions.append(partition_id)
            
            return True
    
    async def get_partition_stats(self) -> PartitionStats:
        """Récupère les statistiques des partitions."""
        with self._partitions_lock:
            partitions = list(self._partitions.values())
        
        stats = PartitionStats(
            total_partitions=len(partitions),
            total_shards=len(self._shards),
            total_rows=sum(p.row_count for p in partitions),
            total_size_bytes=sum(p.size_bytes for p in partitions),
            avg_partition_size=np.mean([p.row_count for p in partitions]) if partitions else 0,
            max_partition_size=max([p.row_count for p in partitions]) if partitions else 0,
            min_partition_size=min([p.row_count for p in partitions]) if partitions else 0
        )
        
        # Distribution par type de données
        for p in partitions:
            stats.distribution[p.data_type.value] = stats.distribution.get(p.data_type.value, 0) + p.row_count
        
        return stats
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._partitions_lock:
            self._stats["total_partitions"] = len(self._partitions)
        with self._shards_lock:
            self._stats["total_shards"] = len(self._shards)
        
        return self._stats.copy()


# ============== PARTITION STRATEGY BUILDER ==============

class PartitionStrategyBuilder:
    """
    Constructeur de stratégies de partitionnement.
    Facilite la création de stratégies de partitionnement.
    """
    
    def __init__(self):
        self._partition = Partition()
    
    def name(self, name: str) -> 'PartitionStrategyBuilder':
        """Définit le nom."""
        self._partition.name = name
        return self
    
    def strategy(self, strategy: PartitionStrategy) -> 'PartitionStrategyBuilder':
        """Définit la stratégie."""
        self._partition.strategy = strategy
        return self
    
    def key(self, key: str) -> 'PartitionStrategyBuilder':
        """Définit la clé."""
        self._partition.key = key
        return self
    
    def range(self, min_val: Any, max_val: Any) -> 'PartitionStrategyBuilder':
        """Définit une plage."""
        self._partition.min_value = min_val
        self._partition.max_value = max_val
        return self
    
    def data_type(self, data_type: DataType) -> 'PartitionStrategyBuilder':
        """Définit le type de données."""
        self._partition.data_type = data_type
        return self
    
    def metadata(self, metadata: Dict[str, Any]) -> 'PartitionStrategyBuilder':
        """Définit les métadonnées."""
        self._partition.metadata = metadata
        return self
    
    def tags(self, tags: List[str]) -> 'PartitionStrategyBuilder':
        """Définit les tags."""
        self._partition.tags = tags
        return self
    
    def build(self) -> Partition:
        """Construit la partition."""
        if not self._partition.key:
            raise ValueError("Partition key is required")
        return self._partition


# ============== FACTORY ==============

class PartitionFactory:
    """Factory pour créer des composants de partitionnement."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PartitionEngine:
        """Crée un moteur de partitionnement."""
        engine = PartitionEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_strategy_builder() -> PartitionStrategyBuilder:
        """Crée un constructeur de stratégies."""
        return PartitionStrategyBuilder()


# ============== EXPORT ==============

__all__ = [
    "PartitionStrategy",
    "ShardType",
    "RebalanceStrategy",
    "Partition",
    "Shard",
    "PartitionQuery",
    "PartitionStats",
    "PartitionEngineInterface",
    "PartitionEngine",
    "PartitionStrategyBuilder",
    "PartitionFactory"
]
