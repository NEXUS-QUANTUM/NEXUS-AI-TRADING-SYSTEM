# trading/bots/hedge_bot/hedge_bot_data_lineaged.py
# Advanced Data Lineage Tracking & Provenance Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Lineage Tracked Module - Module avancé de traçabilité et de provenance des données
pour le Hedge Bot. Assure le suivi complet de la provenance des données, la traçabilité des transformations,
l'historique des modifications et l'audit complet des données pour la conformité et la gouvernance.
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
import pandas as pd
import numpy as np
from collections import defaultdict, deque
import threading
import concurrent.futures
import pickle
import zlib

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_lineaged")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class LineageOperation(Enum):
    """Opérations de traçabilité."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    MERGE = "merge"
    SPLIT = "split"
    TRANSFORM = "transform"
    AGGREGATE = "aggregate"
    FILTER = "filter"
    JOIN = "join"
    EXTRACT = "extract"
    LOAD = "load"


class LineageSource(Enum):
    """Sources de traçabilité."""
    SYSTEM = "system"
    USER = "user"
    API = "api"
    STREAM = "stream"
    BATCH = "batch"
    EXTERNAL = "external"
    INTERNAL = "internal"


class ProvenanceLevel(Enum):
    """Niveaux de provenance."""
    NONE = "none"                      # Pas de provenance
    BASIC = "basic"                    # Provenance de base
    STANDARD = "standard"              # Provenance standard
    DETAILED = "detailed"              # Provenance détaillée
    COMPLETE = "complete"              # Provenance complète


# ============== DATA MODELS ==============

@dataclass
class LineageRecord:
    """Enregistrement de traçabilité."""
    lineage_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data_id: str = ""
    data_type: DataType = DataType.MARKET
    operation: LineageOperation = LineageOperation.CREATE
    source: LineageSource = LineageSource.SYSTEM
    previous_version: Optional[str] = None
    next_version: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user: str = ""
    description: str = ""
    changes: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    provenance_level: ProvenanceLevel = ProvenanceLevel.STANDARD
    signature: Optional[str] = None
    version: int = 1
    
    def to_dict(self) -> Dict:
        return {
            "lineage_id": self.lineage_id,
            "data_id": self.data_id,
            "data_type": self.data_type.value,
            "operation": self.operation.value,
            "source": self.source.value,
            "previous_version": self.previous_version,
            "next_version": self.next_version,
            "timestamp": self.timestamp.isoformat(),
            "user": self.user,
            "description": self.description,
            "changes": self.changes,
            "metadata": self.metadata,
            "tags": self.tags,
            "provenance_level": self.provenance_level.value,
            "signature": self.signature,
            "version": self.version
        }


@dataclass
class DataProvenance:
    """Provenance des données."""
    provenance_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data_id: str = ""
    data_type: DataType = DataType.MARKET
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""
    created_from: Optional[str] = None
    lineage_chain: List[str] = field(default_factory=list)
    transformation_history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    hash: Optional[str] = None
    verified: bool = False


@dataclass
class LineageQuery:
    """Requête de traçabilité."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data_id: str = ""
    data_type: Optional[DataType] = None
    operation: Optional[LineageOperation] = None
    source: Optional[LineageSource] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    user: Optional[str] = None
    limit: int = 100
    offset: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageGraph:
    """Graphe de traçabilité."""
    graph_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    root_data_id: str = ""
    nodes: List[LineageRecord] = field(default_factory=list)
    edges: List[Tuple[str, str]] = field(default_factory=list)
    depth: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class LineageTrackedEngineInterface(ABC):
    """Interface abstraite pour le moteur de traçabilité."""
    
    @abstractmethod
    async def record_lineage(self, record: LineageRecord) -> str:
        """Enregistre une trace de traçabilité."""
        pass
    
    @abstractmethod
    async def get_lineage(self, data_id: str) -> List[LineageRecord]:
        """Récupère la traçabilité d'une donnée."""
        pass
    
    @abstractmethod
    async def get_provenance(self, data_id: str) -> DataProvenance:
        """Récupère la provenance d'une donnée."""
        pass
    
    @abstractmethod
    async def trace_lineage_graph(self, data_id: str, depth: int = 10) -> LineageGraph:
        """Récupère le graphe de traçabilité."""
        pass


# ============== IMPLÉMENTATION ==============

class LineageTrackedEngine(LineageTrackedEngineInterface):
    """
    Moteur de traçabilité avancé pour le Hedge Bot.
    Gère la provenance, l'historique et l'audit des données.
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
        
        # Gestion des enregistrements de traçabilité
        self._lineage: Dict[str, List[LineageRecord]] = defaultdict(list)
        self._lineage_lock = threading.RLock()
        
        # Gestion de la provenance
        self._provenance: Dict[str, DataProvenance] = {}
        self._provenance_lock = threading.RLock()
        
        # Gestion des graphes
        self._graphs: Dict[str, LineageGraph] = {}
        self._graphs_lock = threading.RLock()
        
        # Cache des requêtes
        self._query_cache: Dict[str, List[LineageRecord]] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "lineage_records": 0,
            "provenance_records": 0,
            "graphs_generated": 0,
            "queries_executed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "verification_passed": 0,
            "verification_failed": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("LineageTrackedEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_provenance_level": ProvenanceLevel.STANDARD,
            "cache_size": 1000,
            "cache_ttl": 3600,
            "enable_caching": True,
            "enable_signature": True,
            "max_lineage_depth": 50,
            "graph_cache_size": 100,
            "signing_key": "nexus_lineage_secret",
            "retention_days": 365,
            "audit_enabled": True
        }
    
    async def start(self) -> None:
        """Démarre le moteur de traçabilité."""
        logger.info("LineageTrackedEngine starting...")
        self._is_running = True
        
        # Chargement des enregistrements existants
        await self._load_lineage()
        
        # Chargement de la provenance
        await self._load_provenance()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        asyncio.create_task(self._lineage_compactor())
        
        logger.info("LineageTrackedEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de traçabilité."""
        logger.info("LineageTrackedEngine stopping...")
        self._is_running = False
        
        # Sauvegarde des données
        await self._save_lineage()
        await self._save_provenance()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("LineageTrackedEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def record_lineage(self, record: LineageRecord) -> str:
        """Enregistre une trace de traçabilité."""
        # Signature
        if self.config["enable_signature"]:
            record.signature = await self._sign_lineage(record)
        
        with self._lineage_lock:
            self._lineage[record.data_id].append(record)
            self._stats["lineage_records"] += 1
            
            # Limitation de l'historique
            if len(self._lineage[record.data_id]) > self.config["max_lineage_depth"]:
                self._lineage[record.data_id] = self._lineage[record.data_id][-self.config["max_lineage_depth"]:]
        
        # Mise à jour de la provenance
        await self._update_provenance(record)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"lineage:{record.data_id}",
                record.to_dict(),
                DataType.LINEAGE
            )
        
        # Invalidation du cache
        with self._cache_lock:
            self._query_cache.pop(record.data_id, None)
            self._query_cache.pop(f"graph_{record.data_id}", None)
        
        logger.debug(f"Lineage recorded: {record.data_id} operation={record.operation.value}")
        return record.lineage_id
    
    async def get_lineage(self, data_id: str) -> List[LineageRecord]:
        """Récupère la traçabilité d'une donnée."""
        self._stats["queries_executed"] += 1
        
        # Vérification du cache
        if self.config["enable_caching"] and data_id in self._query_cache:
            self._stats["cache_hits"] += 1
            return self._query_cache[data_id]
        
        self._stats["cache_misses"] += 1
        
        with self._lineage_lock:
            records = self._lineage.get(data_id, [])
        
        # Mise en cache
        if self.config["enable_caching"]:
            with self._cache_lock:
                if len(self._query_cache) < self.config["cache_size"]:
                    self._query_cache[data_id] = records
        
        return records
    
    async def get_provenance(self, data_id: str) -> DataProvenance:
        """Récupère la provenance d'une donnée."""
        with self._provenance_lock:
            if data_id in self._provenance:
                return self._provenance[data_id]
        
        # Création de la provenance
        provenance = await self._build_provenance(data_id)
        
        with self._provenance_lock:
            self._provenance[data_id] = provenance
            self._stats["provenance_records"] += 1
        
        return provenance
    
    async def trace_lineage_graph(self, data_id: str, depth: int = 10) -> LineageGraph:
        """Récupère le graphe de traçabilité."""
        # Vérification du cache
        cache_key = f"graph_{data_id}"
        with self._cache_lock:
            if cache_key in self._query_cache:
                return self._query_cache[cache_key]
        
        nodes = []
        edges = []
        visited = set()
        
        # BFS pour construire le graphe
        queue = deque([(data_id, 0)])
        visited.add(data_id)
        
        while queue:
            current_id, current_depth = queue.popleft()
            
            if current_depth > depth:
                break
            
            # Récupération de la traçabilité
            lineage = await self.get_lineage(current_id)
            
            for record in lineage:
                nodes.append(record)
                
                if record.previous_version:
                    edges.append((record.previous_version, current_id))
                    if record.previous_version not in visited:
                        visited.add(record.previous_version)
                        queue.append((record.previous_version, current_depth + 1))
                
                if record.next_version:
                    edges.append((current_id, record.next_version))
                    if record.next_version not in visited:
                        visited.add(record.next_version)
                        queue.append((record.next_version, current_depth + 1))
        
        # Création du graphe
        graph = LineageGraph(
            root_data_id=data_id,
            nodes=nodes,
            edges=edges,
            depth=depth,
            metadata={"node_count": len(nodes), "edge_count": len(edges)}
        )
        
        with self._graphs_lock:
            self._graphs[graph.graph_id] = graph
            self._stats["graphs_generated"] += 1
        
        # Mise en cache
        with self._cache_lock:
            if len(self._query_cache) < self.config["cache_size"]:
                self._query_cache[cache_key] = graph
        
        return graph
    
    # ========== MÉTHODES PRIVÉES - PROVENANCE ==========
    
    async def _update_provenance(self, record: LineageRecord) -> None:
        """Met à jour la provenance d'une donnée."""
        with self._provenance_lock:
            if record.data_id not in self._provenance:
                self._provenance[record.data_id] = DataProvenance(
                    data_id=record.data_id,
                    data_type=record.data_type,
                    created_at=record.timestamp,
                    created_by=record.user
                )
            
            provenance = self._provenance[record.data_id]
            
            # Ajout à la chaîne de traçabilité
            provenance.lineage_chain.append(record.lineage_id)
            
            # Ajout à l'historique des transformations
            if record.operation != LineageOperation.CREATE:
                provenance.transformation_history.append({
                    "operation": record.operation.value,
                    "timestamp": record.timestamp.isoformat(),
                    "user": record.user,
                    "description": record.description,
                    "changes": record.changes
                })
            
            # Mise à jour du hash
            provenance.hash = hashlib.md5(
                json.dumps(provenance.to_dict()).encode()
            ).hexdigest()
    
    async def _build_provenance(self, data_id: str) -> DataProvenance:
        """Construit la provenance d'une donnée."""
        lineage = await self.get_lineage(data_id)
        
        if not lineage:
            return DataProvenance(
                data_id=data_id,
                created_at=datetime.now(timezone.utc),
                metadata={"status": "unknown"}
            )
        
        # Premier enregistrement
        first = lineage[0]
        
        provenance = DataProvenance(
            data_id=data_id,
            data_type=first.data_type,
            created_at=first.timestamp,
            created_by=first.user,
            lineage_chain=[r.lineage_id for r in lineage],
            metadata={"record_count": len(lineage)}
        )
        
        # Historique des transformations
        for record in lineage:
            if record.operation != LineageOperation.CREATE:
                provenance.transformation_history.append({
                    "operation": record.operation.value,
                    "timestamp": record.timestamp.isoformat(),
                    "user": record.user,
                    "description": record.description,
                    "changes": record.changes
                })
        
        return provenance
    
    # ========== MÉTHODES PRIVÉES - SIGNATURE ==========
    
    async def _sign_lineage(self, record: LineageRecord) -> str:
        """Signe un enregistrement de traçabilité."""
        data = f"{record.data_id}{record.operation.value}{record.timestamp.isoformat()}{record.user}"
        signature = hashlib.sha256(
            (data + self.config["signing_key"]).encode()
        ).hexdigest()
        return signature
    
    async def _verify_lineage(self, record: LineageRecord) -> bool:
        """Vérifie la signature d'un enregistrement."""
        if not record.signature:
            return False
        
        expected = await self._sign_lineage(record)
        return record.signature == expected
    
    # ========== MÉTHODES PRIVÉES - CHARGEMENT ==========
    
    async def _load_lineage(self) -> None:
        """Charge les enregistrements de traçabilité."""
        try:
            if self.data_manager:
                lineage_data = await self.data_manager.retrieve(
                    "lineage:all",
                    DataType.LINEAGE
                )
                
                if lineage_data:
                    for record_dict in lineage_data:
                        record = self._deserialize_lineage(record_dict)
                        if record:
                            with self._lineage_lock:
                                self._lineage[record.data_id].append(record)
            
            logger.info(f"Loaded {self._stats['lineage_records']} lineage records")
            
        except Exception as e:
            logger.error(f"Load lineage error: {e}")
    
    async def _load_provenance(self) -> None:
        """Charge la provenance."""
        try:
            if self.data_manager:
                provenance_data = await self.data_manager.retrieve(
                    "lineage:provenance",
                    DataType.PROVENANCE
                )
                
                if provenance_data:
                    for p_dict in provenance_data:
                        provenance = self._deserialize_provenance(p_dict)
                        if provenance:
                            with self._provenance_lock:
                                self._provenance[provenance.data_id] = provenance
            
            logger.info(f"Loaded {len(self._provenance)} provenance records")
            
        except Exception as e:
            logger.error(f"Load provenance error: {e}")
    
    def _deserialize_lineage(self, data: Dict) -> Optional[LineageRecord]:
        """Désérialise un enregistrement de traçabilité."""
        try:
            return LineageRecord(
                lineage_id=data.get("lineage_id", str(uuid.uuid4())),
                data_id=data.get("data_id", ""),
                data_type=DataType(data.get("data_type", "market")),
                operation=LineageOperation(data.get("operation", "create")),
                source=LineageSource(data.get("source", "system")),
                previous_version=data.get("previous_version"),
                next_version=data.get("next_version"),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                user=data.get("user", ""),
                description=data.get("description", ""),
                changes=data.get("changes", {}),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                provenance_level=ProvenanceLevel(data.get("provenance_level", "standard")),
                signature=data.get("signature"),
                version=data.get("version", 1)
            )
        except Exception as e:
            logger.error(f"Error deserializing lineage: {e}")
            return None
    
    def _deserialize_provenance(self, data: Dict) -> Optional[DataProvenance]:
        """Désérialise une provenance."""
        try:
            return DataProvenance(
                provenance_id=data.get("provenance_id", str(uuid.uuid4())),
                data_id=data.get("data_id", ""),
                data_type=DataType(data.get("data_type", "market")),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                created_by=data.get("created_by", ""),
                created_from=data.get("created_from"),
                lineage_chain=data.get("lineage_chain", []),
                transformation_history=data.get("transformation_history", []),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                hash=data.get("hash"),
                verified=data.get("verified", False)
            )
        except Exception as e:
            logger.error(f"Error deserializing provenance: {e}")
            return None
    
    async def _save_lineage(self) -> None:
        """Sauvegarde les enregistrements de traçabilité."""
        try:
            if self.data_manager:
                with self._lineage_lock:
                    for data_id, records in self._lineage.items():
                        for record in records:
                            await self.data_manager.store(
                                f"lineage:{data_id}",
                                record.to_dict(),
                                DataType.LINEAGE
                            )
            
            logger.info("Lineage saved")
            
        except Exception as e:
            logger.error(f"Save lineage error: {e}")
    
    async def _save_provenance(self) -> None:
        """Sauvegarde la provenance."""
        try:
            if self.data_manager:
                with self._provenance_lock:
                    for provenance in self._provenance.values():
                        await self.data_manager.store(
                            f"lineage:provenance:{provenance.data_id}",
                            provenance.to_dict(),
                            DataType.PROVENANCE
                        )
            
            logger.info("Provenance saved")
            
        except Exception as e:
            logger.error(f"Save provenance error: {e}")
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._query_cache) > self.config["cache_size"]:
                        keys = list(self._query_cache.keys())
                        for key in keys[:len(self._query_cache) - self.config["cache_size"]]:
                            del self._query_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._lineage_lock:
                    self._stats["total_lineage_records"] = sum(len(v) for v in self._lineage.values())
                with self._provenance_lock:
                    self._stats["total_provenance"] = len(self._provenance)
                with self._graphs_lock:
                    self._stats["total_graphs"] = len(self._graphs)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "lineage:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    async def _lineage_compactor(self) -> None:
        """Compacte les anciens enregistrements de traçabilité."""
        while self._is_running:
            await asyncio.sleep(86400)  # 1 jour
            
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=self.config["retention_days"])
                
                with self._lineage_lock:
                    for data_id in list(self._lineage.keys()):
                        records = self._lineage[data_id]
                        kept = [r for r in records if r.timestamp > cutoff]
                        
                        if len(kept) < len(records):
                            self._lineage[data_id] = kept
                            logger.debug(f"Compacted lineage for {data_id}: {len(records)} -> {len(kept)}")
                
            except Exception as e:
                logger.error(f"Lineage compactor error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def verify_lineage(self, data_id: str) -> bool:
        """Vérifie l'intégrité de la traçabilité."""
        lineage = await self.get_lineage(data_id)
        
        verified = True
        for record in lineage:
            if not await self._verify_lineage(record):
                verified = False
                logger.warning(f"Lineage verification failed: {record.lineage_id}")
                self._stats["verification_failed"] += 1
            else:
                self._stats["verification_passed"] += 1
        
        return verified
    
    async def query_lineage(self, query: LineageQuery) -> List[LineageRecord]:
        """Exécute une requête de traçabilité."""
        results = []
        
        with self._lineage_lock:
            for data_id, records in self._lineage.items():
                if query.data_id and data_id != query.data_id:
                    continue
                
                for record in records:
                    if query.data_type and record.data_type != query.data_type:
                        continue
                    
                    if query.operation and record.operation != query.operation:
                        continue
                    
                    if query.source and record.source != query.source:
                        continue
                    
                    if query.user and record.user != query.user:
                        continue
                    
                    if query.start_time and record.timestamp < query.start_time:
                        continue
                    
                    if query.end_time and record.timestamp > query.end_time:
                        continue
                    
                    results.append(record)
        
        # Pagination
        if query.limit > 0:
            results = results[query.offset:query.offset + query.limit]
        
        return results
    
    async def get_lineage_graph(self, graph_id: str) -> Optional[LineageGraph]:
        """Récupère un graphe de traçabilité."""
        with self._graphs_lock:
            return self._graphs.get(graph_id)
    
    async def export_lineage(self, data_id: str, format: str = "json") -> str:
        """Exporte la traçabilité."""
        lineage = await self.get_lineage(data_id)
        provenance = await self.get_provenance(data_id)
        graph = await self.trace_lineage_graph(data_id)
        
        if format == "json":
            data = {
                "lineage": [r.to_dict() for r in lineage],
                "provenance": provenance.to_dict(),
                "graph": graph.to_dict()
            }
            return json.dumps(data, indent=2)
        else:
            return json.dumps([r.to_dict() for r in lineage], indent=2)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._lineage_lock:
            self._stats["lineage_records_count"] = sum(len(v) for v in self._lineage.values())
        with self._provenance_lock:
            self._stats["provenance_records_count"] = len(self._provenance)
        
        return self._stats.copy()


# ============== FACTORY ==============

class LineageTrackedFactory:
    """Factory pour créer des composants de traçabilité."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> LineageTrackedEngine:
        """Crée un moteur de traçabilité."""
        engine = LineageTrackedEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "LineageOperation",
    "LineageSource",
    "ProvenanceLevel",
    "LineageRecord",
    "DataProvenance",
    "LineageQuery",
    "LineageGraph",
    "LineageTrackedEngineInterface",
    "LineageTrackedEngine",
    "LineageTrackedFactory"
]
