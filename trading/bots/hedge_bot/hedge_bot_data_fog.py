# trading/bots/hedge_bot/hedge_bot_data_fog.py
# Advanced Fog Computing & Edge Intelligence Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Fog Computing Module - Module de calcul en brume et d'intelligence en périphérie avancé
pour le Hedge Bot. Étend les capacités de l'edge computing avec une couche de fog pour le traitement
distribué, la réduction de latence, l'agrégation de données et l'optimisation des ressources
dans les environnements de trading à haute fréquence.
"""

import asyncio
import json
import time
import math
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
import hashlib
import pickle
import zlib
import socket
import psutil
import os
import platform

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_fog")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DataQuery, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_edge import (
    EdgeNode, EdgeTask, EdgeComputeNode, EdgeOrchestrator,
    EdgeNodeType, EdgeProcessingMode, EdgeDataPriority
)


# ============== ENUMS & TYPES ==============

class FogNodeType(Enum):
    """Types de nœuds de brume."""
    GATEWAY = "gateway"
    AGGREGATOR = "aggregator"
    ANALYTICS = "analytics"
    STORAGE = "storage"
    COMPUTE = "compute"
    ORCHESTRATOR = "orchestrator"
    ML_ENGINE = "ml_engine"
    DATA_LAKE = "data_lake"
    CACHE = "cache"
    MONITOR = "monitor"


class FogTier(Enum):
    """Niveaux de la hiérarchie de brume."""
    TIER_1 = "tier_1"  # Proche des capteurs (edge)
    TIER_2 = "tier_2"  # Agregation locale
    TIER_3 = "tier_3"  # Analytics régional
    TIER_4 = "tier_4"  # Cloud proche
    TIER_5 = "tier_5"  # Cloud central


class FogSyncMode(Enum):
    """Modes de synchronisation Fog."""
    REAL_TIME = "real_time"
    BATCH = "batch"
    EVENT_DRIVEN = "event_driven"
    SCHEDULED = "scheduled"
    HYBRID = "hybrid"


# ============== DATA MODELS ==============

@dataclass
class FogNode:
    """Modèle de nœud de brume."""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_type: FogNodeType = FogNodeType.COMPUTE
    tier: FogTier = FogTier.TIER_2
    name: str = ""
    host: str = ""
    port: int = 0
    upstream_nodes: List[str] = field(default_factory=list)
    downstream_nodes: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    resources: Dict[str, float] = field(default_factory=dict)
    status: str = "active"
    load: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    bandwidth_usage: float = 0.0
    latency_ms: float = 0.0
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    region: str = ""
    zone: str = ""
    sync_mode: FogSyncMode = FogSyncMode.HYBRID
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "tier": self.tier.value,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "upstream_nodes": self.upstream_nodes,
            "downstream_nodes": self.downstream_nodes,
            "capabilities": self.capabilities,
            "resources": self.resources,
            "status": self.status,
            "load": self.load,
            "memory_usage": self.memory_usage,
            "cpu_usage": self.cpu_usage,
            "bandwidth_usage": self.bandwidth_usage,
            "latency_ms": self.latency_ms,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags,
            "region": self.region,
            "zone": self.zone,
            "sync_mode": self.sync_mode.value
        }


@dataclass
class FogTask:
    """Tâche de traitement en brume."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = ""
    priority: EdgeDataPriority = EdgeDataPriority.MEDIUM
    data: Any = None
    processing_mode: EdgeProcessingMode = EdgeProcessingMode.REAL_TIME
    deadline: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    result: Any = None
    error: Optional[str] = None
    assigned_node: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    parent_task_id: Optional[str] = None
    child_tasks: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    execution_tier: FogTier = FogTier.TIER_2
    sync_required: bool = True


@dataclass
class FogDataChunk:
    """Chunk de données en brume."""
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data: Any = None
    source: str = ""
    destination: str = ""
    size_bytes: int = 0
    compressed: bool = False
    checksum: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    ttl: int = 3600
    priority: int = 0


@dataclass
class FogAggregation:
    """Agrégation de données en brume."""
    aggregation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    input_nodes: List[str] = field(default_factory=list)
    output_node: str = ""
    function: str = ""  # sum, avg, max, min, count, custom
    window: int = 60  # secondes
    sliding: int = 10  # secondes
    data_type: DataType = DataType.MARKET
    last_run: Optional[datetime] = None
    result: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    active: bool = True


# ============== INTERFACES ==============

class FogEngineInterface(ABC):
    """Interface abstraite pour le moteur de brume."""
    
    @abstractmethod
    async def register_node(self, node: FogNode) -> bool:
        """Enregistre un nœud de brume."""
        pass
    
    @abstractmethod
    async def submit_task(self, task: FogTask) -> str:
        """Soumet une tâche de brume."""
        pass
    
    @abstractmethod
    async def process_data(self, data: Any, node: FogNode) -> Any:
        """Traite des données sur un nœud de brume."""
        pass


# ============== IMPLÉMENTATION ==============

class FogEngine(FogEngineInterface):
    """
    Moteur de brume avancé pour le Hedge Bot.
    Orchestre le traitement distribué des données entre les nœuds de brume,
    optimise la latence, gère les ressources et assure la synchronisation.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        edge_orchestrator: Optional[EdgeOrchestrator] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.edge_orchestrator = edge_orchestrator
        self.config = config or self._default_config()
        
        # Gestion des nœuds
        self._nodes: Dict[str, FogNode] = {}
        self._nodes_lock = threading.RLock()
        
        # Gestion des tâches
        self._tasks: Dict[str, FogTask] = {}
        self._tasks_lock = threading.RLock()
        
        # File d'attente des tâches
        self._task_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Agrégations
        self._aggregations: Dict[str, FogAggregation] = {}
        self._agg_lock = threading.RLock()
        
        # Cache de données
        self._data_cache: Dict[str, FogDataChunk] = {}
        self._cache_lock = threading.RLock()
        self._cache_hits = 0
        self._cache_misses = 0
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "nodes_registered": 0,
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "data_processed": 0,
            "data_volume_mb": 0.0,
            "avg_latency_ms": 0.0,
            "throughput": 0.0
        }
        
        # Métriques de performance
        self._latency_histogram: deque = deque(maxlen=1000)
        self._throughput_counter = 0
        
        # État
        self._is_running = False
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 8)
        )
        
        logger.info("FogEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 8,
            "task_timeout": 60,
            "max_queue_size": 10000,
            "cache_size": 10000,
            "cache_ttl": 300,  # 5 minutes
            "aggregation_interval": 10,  # secondes
            "sync_interval": 30,  # secondes
            "health_check_interval": 15,  # secondes
            "max_data_chunk_mb": 10,
            "compression_enabled": True,
            "enable_auto_scaling": True,
            "min_nodes": 2,
            "max_nodes": 10
        }
    
    async def start(self) -> None:
        """Démarre le moteur de brume."""
        logger.info("FogEngine starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._task_processor())
        asyncio.create_task(self._aggregation_loop())
        asyncio.create_task(self._sync_loop())
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("FogEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de brume."""
        logger.info("FogEngine stopping...")
        self._is_running = False
        
        # Attente des tâches en cours
        await self._drain_queue()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("FogEngine stopped")
    
    async def register_node(self, node: FogNode) -> bool:
        """Enregistre un nœud de brume."""
        with self._nodes_lock:
            self._nodes[node.node_id] = node
            self._stats["nodes_registered"] += 1
        
        # Synchronisation avec l'orchestrateur Edge
        if self.edge_orchestrator and node.node_type == FogNodeType.GATEWAY:
            # Création d'un nœud Edge correspondant
            edge_node = EdgeNode(
                node_id=node.node_id,
                node_type=EdgeNodeType.GATEWAY,
                name=node.name,
                host=node.host,
                port=node.port,
                capabilities=node.capabilities,
                region=node.region,
                zone=node.zone
            )
            # Conversion en EdgeComputeNode
            compute_node = EdgeComputeNode(
                node_id=edge_node.node_id,
                host=edge_node.host,
                port=edge_node.port,
                node_type=edge_node.node_type,
                capabilities=edge_node.capabilities
            )
            await self.edge_orchestrator.register_node(compute_node)
        
        logger.info(f"Fog node registered: {node.node_id} (type={node.node_type.value}, tier={node.tier.value})")
        return True
    
    async def unregister_node(self, node_id: str) -> bool:
        """Désenregistre un nœud de brume."""
        with self._nodes_lock:
            if node_id not in self._nodes:
                return False
            del self._nodes[node_id]
        
        logger.info(f"Fog node unregistered: {node_id}")
        return True
    
    async def get_node(self, node_id: str) -> Optional[FogNode]:
        """Récupère un nœud de brume."""
        with self._nodes_lock:
            return self._nodes.get(node_id)
    
    async def get_nodes(
        self,
        node_type: Optional[FogNodeType] = None,
        tier: Optional[FogTier] = None
    ) -> List[FogNode]:
        """Récupère les nœuds de brume."""
        with self._nodes_lock:
            nodes = list(self._nodes.values())
            if node_type:
                nodes = [n for n in nodes if n.node_type == node_type]
            if tier:
                nodes = [n for n in nodes if n.tier == tier]
            return nodes
    
    async def submit_task(self, task: FogTask) -> str:
        """Soumet une tâche de brume."""
        with self._tasks_lock:
            self._tasks[task.task_id] = task
            self._stats["tasks_submitted"] += 1
        
        await self._task_queue.put(task)
        logger.debug(f"Fog task submitted: {task.task_id} (type={task.task_type})")
        return task.task_id
    
    async def get_task(self, task_id: str) -> Optional[FogTask]:
        """Récupère une tâche de brume."""
        with self._tasks_lock:
            return self._tasks.get(task_id)
    
    async def get_tasks(self, status: Optional[str] = None) -> List[FogTask]:
        """Récupère les tâches de brume."""
        with self._tasks_lock:
            tasks = list(self._tasks.values())
            if status:
                tasks = [t for t in tasks if t.status == status]
            return sorted(tasks, key=lambda t: t.created_at, reverse=True)
    
    async def process_data(self, data: Any, node: FogNode) -> Any:
        """Traite des données sur un nœud de brume."""
        start_time = time.time()
        self._stats["data_processed"] += 1
        
        try:
            # Création d'un chunk de données
            chunk = await self._create_data_chunk(data, node)
            
            # Cache
            await self._cache_chunk(chunk)
            
            # Traitement selon le type de nœud
            if node.node_type == FogNodeType.AGGREGATOR:
                result = await self._process_aggregator(data, node)
            elif node.node_type == FogNodeType.ANALYTICS:
                result = await self._process_analytics(data, node)
            elif node.node_type == FogNodeType.ML_ENGINE:
                result = await self._process_ml(data, node)
            elif node.node_type == FogNodeType.STORAGE:
                result = await self._process_storage(data, node)
            else:
                result = data
            
            # Métriques
            latency = (time.time() - start_time) * 1000
            self._latency_histogram.append(latency)
            self._stats["avg_latency_ms"] = (
                self._stats["avg_latency_ms"] * 0.9 + latency * 0.1
            )
            self._throughput_counter += 1
            
            # Métriques de volume
            data_size = len(str(data).encode()) if data else 0
            self._stats["data_volume_mb"] += data_size / (1024 * 1024)
            
            return result
            
        except Exception as e:
            logger.error(f"Data processing error on node {node.node_id}: {e}")
            raise
    
    # ========== MÉTHODES PRIVÉES - TRAITEMENT ==========
    
    async def _task_processor(self) -> None:
        """Traite les tâches en file d'attente."""
        while self._is_running:
            try:
                # Récupération de la tâche
                task = await self._task_queue.get()
                
                # Sélection du nœud
                node = await self._select_node(task)
                
                if not node:
                    # Réessayer plus tard
                    if task.retry_count < task.max_retries:
                        task.retry_count += 1
                        await self._task_queue.put(task)
                    else:
                        task.status = "failed"
                        task.error = "No suitable node available"
                        self._stats["tasks_failed"] += 1
                    continue
                
                # Exécution
                asyncio.create_task(self._execute_task(task, node))
                
            except Exception as e:
                logger.error(f"Task processor error: {e}")
                await asyncio.sleep(0.1)
    
    async def _execute_task(self, task: FogTask, node: FogNode) -> None:
        """Exécute une tâche sur un nœud."""
        task.started_at = datetime.now(timezone.utc)
        task.status = "running"
        task.assigned_node = node.node_id
        task.execution_tier = node.tier
        
        try:
            # Traitement
            result = await self.process_data(task.data, node)
            
            # Mise à jour de la tâche
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)
            task.result = result
            self._stats["tasks_completed"] += 1
            
            # Synchronisation
            if task.sync_required:
                await self._sync_result(task, node)
            
            logger.debug(f"Task executed: {task.task_id} on {node.node_id}")
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            self._stats["tasks_failed"] += 1
            
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = "pending"
                await self._task_queue.put(task)
            
            logger.error(f"Task execution failed: {task.task_id} - {e}")
    
    async def _select_node(self, task: FogTask) -> Optional[FogNode]:
        """Sélectionne un nœud pour une tâche."""
        with self._nodes_lock:
            # Filtrer les nœuds disponibles
            available_nodes = [
                n for n in self._nodes.values()
                if n.status == "active"
                and n.load < 0.8
                and any(cap in n.capabilities for cap in task.tags)
            ]
            
            if not available_nodes:
                return None
            
            # Sélection selon le tier
            tier_order = [FogTier.TIER_1, FogTier.TIER_2, FogTier.TIER_3, FogTier.TIER_4]
            if task.execution_tier in tier_order:
                tier_nodes = [n for n in available_nodes if n.tier == task.execution_tier]
                if tier_nodes:
                    available_nodes = tier_nodes
            
            # Sélection du moins chargé
            return min(available_nodes, key=lambda n: n.load)
    
    # ========== MÉTHODES PRIVÉES - TRAITEMENT PAR TYPE ==========
    
    async def _process_aggregator(self, data: Any, node: FogNode) -> Any:
        """Traite des données sur un agrégateur."""
        # Agrégation basée sur la configuration
        aggregation = await self._get_aggregation(node)
        if not aggregation:
            return data
        
        if isinstance(data, pd.DataFrame):
            if aggregation.function == "sum":
                return data.sum()
            elif aggregation.function == "avg":
                return data.mean()
            elif aggregation.function == "max":
                return data.max()
            elif aggregation.function == "min":
                return data.min()
            elif aggregation.function == "count":
                return data.count()
            else:
                return data
        elif isinstance(data, dict):
            # Agrégation de dictionnaire
            result = {}
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    if aggregation.function == "sum":
                        result[key] = value
                    elif aggregation.function == "avg":
                        result[key] = value
                    else:
                        result[key] = value
            return result
        else:
            return data
    
    async def _process_analytics(self, data: Any, node: FogNode) -> Any:
        """Traite des données pour l'analytique."""
        if isinstance(data, pd.DataFrame):
            # Analyse statistique
            result = {
                "shape": data.shape,
                "columns": list(data.columns),
                "dtypes": data.dtypes.to_dict(),
                "describe": data.describe().to_dict() if len(data) > 0 else {},
                "missing": data.isnull().sum().to_dict()
            }
            return result
        elif isinstance(data, dict):
            # Analyse de dictionnaire
            result = {
                "keys": list(data.keys()),
                "types": {k: type(v).__name__ for k, v in data.items()},
                "length": len(data)
            }
            return result
        else:
            return {"type": type(data).__name__, "value": data}
    
    async def _process_ml(self, data: Any, node: FogNode) -> Any:
        """Traite des données avec un modèle ML."""
        # Simulation d'inférence ML
        # Dans un système réel, on utiliserait des modèles entraînés
        if isinstance(data, pd.DataFrame):
            # Prédiction simulée
            predictions = np.random.randn(len(data))
            return {"predictions": predictions.tolist(), "confidence": 0.75}
        elif isinstance(data, dict):
            return {"prediction": random.random(), "confidence": 0.7}
        else:
            return {"prediction": 0.5, "confidence": 0.5}
    
    async def _process_storage(self, data: Any, node: FogNode) -> Any:
        """Traite des données pour le stockage."""
        # Stockage local
        storage_path = f"/tmp/fog_storage/{node.node_id}/{int(time.time())}"
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        
        # Sauvegarde
        with open(storage_path, 'wb') as f:
            pickle.dump(data, f)
        
        return {"stored_at": storage_path, "size": os.path.getsize(storage_path)}
    
    # ========== MÉTHODES PRIVÉES - CACHE ==========
    
    async def _create_data_chunk(self, data: Any, node: FogNode) -> FogDataChunk:
        """Crée un chunk de données."""
        data_bytes = pickle.dumps(data)
        compressed = False
        
        if self.config["compression_enabled"] and len(data_bytes) > 1024 * 1024:  # >1MB
            data_bytes = zlib.compress(data_bytes)
            compressed = True
        
        return FogDataChunk(
            data=data_bytes,
            source=node.node_id,
            size_bytes=len(data_bytes),
            compressed=compressed,
            checksum=hashlib.md5(data_bytes).hexdigest()
        )
    
    async def _cache_chunk(self, chunk: FogDataChunk) -> None:
        """Cache un chunk de données."""
        with self._cache_lock:
            if len(self._data_cache) >= self.config["cache_size"]:
                # Éviction LRU
                oldest = min(self._data_cache.keys())
                del self._data_cache[oldest]
            
            self._data_cache[chunk.chunk_id] = chunk
            self._cache_hits += 1
    
    async def _get_cached_chunk(self, chunk_id: str) -> Optional[FogDataChunk]:
        """Récupère un chunk du cache."""
        with self._cache_lock:
            chunk = self._data_cache.get(chunk_id)
            if chunk:
                # Vérification TTL
                age = (datetime.now(timezone.utc) - chunk.timestamp).total_seconds()
                if age > chunk.ttl:
                    del self._data_cache[chunk_id]
                    self._cache_misses += 1
                    return None
                self._cache_hits += 1
                return chunk
        
        self._cache_misses += 1
        return None
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                with self._cache_lock:
                    now = datetime.now(timezone.utc)
                    expired = [
                        cid for cid, chunk in self._data_cache.items()
                        if (now - chunk.timestamp).total_seconds() > chunk.ttl
                    ]
                    for cid in expired:
                        del self._data_cache[cid]
                    
                    if expired:
                        logger.debug(f"Cleaned up {len(expired)} expired cache entries")
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    # ========== MÉTHODES PRIVÉES - AGRÉGATION ==========
    
    async def _get_aggregation(self, node: FogNode) -> Optional[FogAggregation]:
        """Récupère l'agrégation pour un nœud."""
        with self._agg_lock:
            for agg in self._aggregations.values():
                if node.node_id in agg.input_nodes or node.node_id == agg.output_node:
                    return agg
        return None
    
    async def _aggregation_loop(self) -> None:
        """Boucle d'agrégation des données."""
        while self._is_running:
            await asyncio.sleep(self.config["aggregation_interval"])
            
            try:
                with self._agg_lock:
                    for agg in self._aggregations.values():
                        if not agg.active:
                            continue
                        
                        # Exécution de l'agrégation
                        result = await self._execute_aggregation(agg)
                        agg.last_run = datetime.now(timezone.utc)
                        agg.result = result
                        
                        # Distribution du résultat
                        await self._distribute_aggregation(agg, result)
                
            except Exception as e:
                logger.error(f"Aggregation loop error: {e}")
    
    async def _execute_aggregation(self, agg: FogAggregation) -> Any:
        """Exécute une agrégation."""
        # Collecte des données des nœuds d'entrée
        data_points = []
        
        for node_id in agg.input_nodes:
            with self._nodes_lock:
                node = self._nodes.get(node_id)
                if not node:
                    continue
            
            # Récupération des données du nœud
            if self.data_manager:
                data = await self.data_manager.retrieve(
                    f"fog:node:{node_id}:data",
                    agg.data_type
                )
                if data:
                    data_points.append(data)
        
        if not data_points:
            return None
        
        # Agrégation
        if agg.function == "sum":
            return sum(data_points)
        elif agg.function == "avg":
            return sum(data_points) / len(data_points)
        elif agg.function == "max":
            return max(data_points)
        elif agg.function == "min":
            return min(data_points)
        elif agg.function == "count":
            return len(data_points)
        else:
            return data_points
    
    async def _distribute_aggregation(self, agg: FogAggregation, result: Any) -> None:
        """Distribue le résultat d'une agrégation."""
        if not result:
            return
        
        # Envoi vers le nœud de sortie
        with self._nodes_lock:
            node = self._nodes.get(agg.output_node)
            if not node:
                return
        
        # Stockage du résultat
        if self.data_manager:
            await self.data_manager.store(
                f"fog:aggregation:{agg.aggregation_id}:result",
                result,
                agg.data_type
            )
    
    # ========== MÉTHODES PRIVÉES - SYNCHRONISATION ==========
    
    async def _sync_loop(self) -> None:
        """Boucle de synchronisation des données."""
        while self._is_running:
            await asyncio.sleep(self.config["sync_interval"])
            
            try:
                # Synchronisation entre les nœuds
                with self._nodes_lock:
                    for node in self._nodes.values():
                        if node.sync_mode == FogSyncMode.REAL_TIME:
                            await self._sync_real_time(node)
                        elif node.sync_mode == FogSyncMode.BATCH:
                            await self._sync_batch(node)
                        elif node.sync_mode == FogSyncMode.EVENT_DRIVEN:
                            await self._sync_event_driven(node)
                
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
    
    async def _sync_real_time(self, node: FogNode) -> None:
        """Synchronisation en temps réel."""
        # Simulation de synchronisation en temps réel
        pass
    
    async def _sync_batch(self, node: FogNode) -> None:
        """Synchronisation par batch."""
        # Simulation de synchronisation par batch
        pass
    
    async def _sync_event_driven(self, node: FogNode) -> None:
        """Synchronisation événementielle."""
        # Simulation de synchronisation événementielle
        pass
    
    async def _sync_result(self, task: FogTask, node: FogNode) -> None:
        """Synchronise le résultat d'une tâche."""
        # Synchronisation vers les nœuds upstream
        for upstream_id in node.upstream_nodes:
            with self._nodes_lock:
                upstream = self._nodes.get(upstream_id)
                if upstream:
                    # Envoi du résultat
                    if self.data_manager:
                        await self.data_manager.store(
                            f"fog:result:{task.task_id}",
                            task.result,
                            DataType.RESULT
                        )
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _health_check_loop(self) -> None:
        """Boucle de vérification de santé."""
        while self._is_running:
            await asyncio.sleep(self.config["health_check_interval"])
            
            try:
                with self._nodes_lock:
                    now = datetime.now(timezone.utc)
                    for node_id, node in list(self._nodes.items()):
                        # Vérification du heartbeat
                        age = (now - node.last_heartbeat).total_seconds()
                        if age > 60:  # 1 minute
                            node.status = "inactive"
                            logger.warning(f"Node {node_id} is inactive")
                        
                        # Vérification des ressources
                        if node.memory_usage > 0.9 or node.cpu_usage > 0.9:
                            node.status = "degraded"
                            logger.warning(f"Node {node_id} is degraded: "
                                         f"memory={node.memory_usage:.2f}, cpu={node.cpu_usage:.2f}")
                
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques de performance."""
        while self._is_running:
            await asyncio.sleep(30)
            
            try:
                # Calcul du throughput
                self._stats["throughput"] = self._throughput_counter / 30.0
                self._throughput_counter = 0
                
                # Métriques des nœuds
                with self._nodes_lock:
                    for node in self._nodes.values():
                        # Collecte des métriques système
                        if node.host == "localhost":
                            node.cpu_usage = psutil.cpu_percent() / 100
                            node.memory_usage = psutil.virtual_memory().percent / 100
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    async def _drain_queue(self) -> None:
        """Vide la file d'attente des tâches."""
        while not self._task_queue.empty():
            try:
                task = await self._task_queue.get()
                task.status = "cancelled"
                task.error = "Engine stopping"
            except Exception:
                break
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def create_aggregation(self, config: Dict[str, Any]) -> FogAggregation:
        """Crée une agrégation."""
        aggregation = FogAggregation(
            name=config.get("name", f"Aggregation_{uuid.uuid4().hex[:8]}"),
            input_nodes=config.get("input_nodes", []),
            output_node=config.get("output_node", ""),
            function=config.get("function", "avg"),
            window=config.get("window", 60),
            sliding=config.get("sliding", 10),
            data_type=DataType(config.get("data_type", "market")),
            metadata=config.get("metadata", {})
        )
        
        with self._agg_lock:
            self._aggregations[aggregation.aggregation_id] = aggregation
        
        logger.info(f"Aggregation created: {aggregation.name} (id={aggregation.aggregation_id})")
        return aggregation
    
    async def get_aggregations(self) -> List[FogAggregation]:
        """Récupère toutes les agrégations."""
        with self._agg_lock:
            return list(self._aggregations.values())
    
    async def delete_aggregation(self, aggregation_id: str) -> bool:
        """Supprime une agrégation."""
        with self._agg_lock:
            if aggregation_id not in self._aggregations:
                return False
            del self._aggregations[aggregation_id]
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._nodes_lock:
            self._stats["active_nodes"] = len([
                n for n in self._nodes.values()
                if n.status == "active"
            ])
        with self._tasks_lock:
            self._stats["pending_tasks"] = len([
                t for t in self._tasks.values()
                if t.status == "pending"
            ])
        with self._cache_lock:
            self._stats["cache_entries"] = len(self._data_cache)
            self._stats["cache_hit_ratio"] = (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0 else 0.0
            )
        
        return self._stats.copy()


# ============== FOG HIERARCHY ==============

class FogHierarchy:
    """
    Hiérarchie de brume pour l'organisation des nœuds.
    Gère les relations entre les différents niveaux de la brume.
    """
    
    def __init__(self, engine: FogEngine):
        self.engine = engine
        self._hierarchy: Dict[FogTier, List[FogNode]] = defaultdict(list)
        self._hierarchy_lock = threading.RLock()
    
    async def build_hierarchy(self) -> None:
        """Construit la hiérarchie à partir des nœuds."""
        nodes = await self.engine.get_nodes()
        
        with self._hierarchy_lock:
            self._hierarchy.clear()
            for node in nodes:
                self._hierarchy[node.tier].append(node)
        
        logger.info(f"Hierarchy built: {len(nodes)} nodes across {len(self._hierarchy)} tiers")
    
    async def get_tier_nodes(self, tier: FogTier) -> List[FogNode]:
        """Récupère les nœuds d'un tier."""
        with self._hierarchy_lock:
            return self._hierarchy.get(tier, [])
    
    async def get_downstream_nodes(self, node: FogNode) -> List[FogNode]:
        """Récupère les nœuds downstream."""
        downstream = []
        with self._hierarchy_lock:
            for tier in [FogTier.TIER_1, FogTier.TIER_2, FogTier.TIER_3]:
                if node.tier.value < tier.value:
                    continue
                for n in self._hierarchy.get(tier, []):
                    if node.node_id in n.upstream_nodes:
                        downstream.append(n)
        return downstream
    
    async def get_upstream_nodes(self, node: FogNode) -> List[FogNode]:
        """Récupère les nœuds upstream."""
        upstream = []
        with self._hierarchy_lock:
            for tier in [FogTier.TIER_2, FogTier.TIER_3, FogTier.TIER_4, FogTier.TIER_5]:
                if node.tier.value > tier.value:
                    continue
                for n in self._hierarchy.get(tier, []):
                    if node.node_id in n.downstream_nodes:
                        upstream.append(n)
        return upstream
    
    async def get_path(
        self,
        source: FogNode,
        destination: FogNode
    ) -> List[FogNode]:
        """Calcule le chemin entre deux nœuds."""
        # BFS simple dans la hiérarchie
        visited = set()
        queue = [(source, [source])]
        
        while queue:
            current, path = queue.pop(0)
            
            if current.node_id == destination.node_id:
                return path
            
            visited.add(current.node_id)
            
            # Vérifier les nœuds connectés
            for next_id in current.downstream_nodes + current.upstream_nodes:
                if next_id not in visited:
                    with self._hierarchy_lock:
                        for tier_nodes in self._hierarchy.values():
                            for node in tier_nodes:
                                if node.node_id == next_id:
                                    queue.append((node, path + [node]))
                                    break
        
        return []


# ============== FACTORY ==============

class FogFactory:
    """Factory pour créer des composants de brume."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        edge_orchestrator: Optional[EdgeOrchestrator] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> FogEngine:
        """Crée un moteur de brume."""
        engine = FogEngine(
            data_manager=data_manager,
            edge_orchestrator=edge_orchestrator,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_node(
        node_type: FogNodeType = FogNodeType.COMPUTE,
        tier: FogTier = FogTier.TIER_2,
        name: str = "",
        host: str = "localhost",
        port: int = 0,
        capabilities: Optional[List[str]] = None
    ) -> FogNode:
        """Crée un nœud de brume."""
        return FogNode(
            node_type=node_type,
            tier=tier,
            name=name or f"{node_type.value}_{uuid.uuid4().hex[:8]}",
            host=host,
            port=port or 0,
            capabilities=capabilities or [node_type.value],
            resources={
                "cpu": psutil.cpu_count(),
                "memory": psutil.virtual_memory().total / (1024**3),
                "disk": psutil.disk_usage('/').total / (1024**3)
            }
        )
    
    @staticmethod
    async def create_hierarchy(engine: FogEngine) -> FogHierarchy:
        """Crée une hiérarchie de brume."""
        hierarchy = FogHierarchy(engine)
        await hierarchy.build_hierarchy()
        return hierarchy


# ============== EXPORT ==============

__all__ = [
    "FogNodeType",
    "FogTier",
    "FogSyncMode",
    "FogNode",
    "FogTask",
    "FogDataChunk",
    "FogAggregation",
    "FogEngineInterface",
    "FogEngine",
    "FogHierarchy",
    "FogFactory"
]
