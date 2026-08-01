# trading/bots/hedge_bot/hedge_bot_data_lineage.py
# Advanced Data Lineage & Metadata Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Lineage Module - Module avancé de traçabilité des données et de gestion des métadonnées
pour le Hedge Bot. Assure la traçabilité des données, la provenance, l'impact analysis,
la gouvernance et la qualité des données pour l'ensemble du système de hedging.
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
import hashlib
import threading
import concurrent.futures
from collections import defaultdict, deque

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_lineage")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class LineageNodeType(Enum):
    """Types de nœuds de traçabilité."""
    SOURCE = "source"
    PROCESS = "process"
    SINK = "sink"
    TRANSFORMATION = "transformation"
    AGGREGATION = "aggregation"
    FILTER = "filter"
    JOIN = "join"
    UNION = "union"
    DEDUP = "dedup"
    VALIDATION = "validation"
    ENRICHMENT = "enrichment"
    ANONYMIZATION = "anonymization"
    EXTRACT = "extract"
    LOAD = "load"


class LineageRelationshipType(Enum):
    """Types de relations de traçabilité."""
    INPUT = "input"
    OUTPUT = "output"
    DEPENDENCY = "dependency"
    PRECEDES = "precedes"
    FOLLOWS = "follows"
    DERIVED_FROM = "derived_from"
    TRANSFORMS = "transforms"
    AGGREGATES = "aggregates"
    FILTERS = "filters"
    JOINS = "joins"
    LOADS = "loads"


class MetadataType(Enum):
    """Types de métadonnées."""
    TECHNICAL = "technical"
    BUSINESS = "business"
    OPERATIONAL = "operational"
    QUALITY = "quality"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    LINEAGE = "lineage"


# ============== DATA MODELS ==============

@dataclass
class LineageNode:
    """Nœud de traçabilité."""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    node_type: LineageNodeType = LineageNodeType.PROCESS
    data_type: DataType = DataType.MARKET
    properties: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "node_type": self.node_type.value,
            "data_type": self.data_type.value,
            "properties": self.properties,
            "metadata": self.metadata,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version
        }


@dataclass
class LineageEdge:
    """Arête de traçabilité."""
    edge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_node_id: str = ""
    target_node_id: str = ""
    relationship_type: LineageRelationshipType = LineageRelationshipType.DERIVED_FROM
    properties: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    weight: float = 1.0
    
    def to_dict(self) -> Dict:
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "relationship_type": self.relationship_type.value,
            "properties": self.properties,
            "metadata": self.metadata,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "weight": self.weight
        }


@dataclass
class LineagePath:
    """Chemin de traçabilité."""
    path_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_node_id: str = ""
    target_node_id: str = ""
    nodes: List[str] = field(default_factory=list)
    edges: List[str] = field(default_factory=list)
    length: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetadataEntry:
    """Entrée de métadonnées."""
    metadata_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    metadata_type: MetadataType = MetadataType.TECHNICAL
    key: str = ""
    value: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class ImpactAnalysis:
    """Analyse d'impact."""
    analysis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_node_id: str = ""
    impacted_nodes: List[str] = field(default_factory=list)
    impacted_edges: List[str] = field(default_factory=list)
    depth: int = 0
    severity: str = "medium"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class LineageEngineInterface(ABC):
    """Interface abstraite pour le moteur de traçabilité."""
    
    @abstractmethod
    async def create_node(self, node: LineageNode) -> str:
        """Crée un nœud de traçabilité."""
        pass
    
    @abstractmethod
    async def create_edge(self, edge: LineageEdge) -> str:
        """Crée une arête de traçabilité."""
        pass
    
    @abstractmethod
    async def get_lineage(self, node_id: str, depth: int = 10) -> LineagePath:
        """Récupère la traçabilité d'un nœud."""
        pass
    
    @abstractmethod
    async def impact_analysis(self, node_id: str) -> ImpactAnalysis:
        """Analyse l'impact d'un nœud."""
        pass


# ============== IMPLÉMENTATION ==============

class LineageEngine(LineageEngineInterface):
    """
    Moteur de traçabilité avancé pour le Hedge Bot.
    Gère la provenance des données, l'impact analysis et les métadonnées.
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
        
        # Gestion des nœuds
        self._nodes: Dict[str, LineageNode] = {}
        self._nodes_lock = threading.RLock()
        
        # Gestion des arêtes
        self._edges: Dict[str, LineageEdge] = {}
        self._edges_lock = threading.RLock()
        
        # Gestion des chemins
        self._paths: Dict[str, LineagePath] = {}
        self._paths_lock = threading.RLock()
        
        # Gestion des métadonnées
        self._metadata: Dict[str, List[MetadataEntry]] = defaultdict(list)
        self._metadata_lock = threading.RLock()
        
        # Cache des analyses d'impact
        self._impact_cache: Dict[str, ImpactAnalysis] = {}
        self._cache_lock = threading.RLock()
        
        # Index inversé
        self._reverse_index: Dict[str, Set[str]] = defaultdict(set)
        self._index_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "nodes_created": 0,
            "edges_created": 0,
            "paths_found": 0,
            "analyses_performed": 0,
            "metadata_entries": 0,
            "avg_lineage_depth": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("LineageEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "max_lineage_depth": 10,
            "enable_caching": True,
            "cache_ttl": 3600,
            "max_cache_size": 1000,
            "max_metadata_per_resource": 100,
            "auto_create_edges": True,
            "enable_reverse_index": True,
            "impact_analysis_interval": 3600,
            "metadata_retention_days": 365
        }
    
    async def start(self) -> None:
        """Démarre le moteur de traçabilité."""
        logger.info("LineageEngine starting...")
        self._is_running = True
        
        # Chargement des nœuds existants
        await self._load_nodes()
        
        # Chargement des arêtes existantes
        await self._load_edges()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._impact_analysis_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("LineageEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de traçabilité."""
        logger.info("LineageEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("LineageEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_node(self, node: LineageNode) -> str:
        """Crée un nœud de traçabilité."""
        with self._nodes_lock:
            self._nodes[node.node_id] = node
            self._stats["nodes_created"] += 1
        
        # Mise à jour de l'index
        if self.config["enable_reverse_index"]:
            with self._index_lock:
                self._reverse_index[node.data_type.value].add(node.node_id)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"lineage:node:{node.node_id}",
                node.to_dict(),
                DataType.LINEAGE
            )
        
        logger.info(f"Lineage node created: {node.name} (id={node.node_id})")
        return node.node_id
    
    async def create_edge(self, edge: LineageEdge) -> str:
        """Crée une arête de traçabilité."""
        # Validation des nœuds
        with self._nodes_lock:
            if edge.source_node_id not in self._nodes:
                raise ValueError(f"Source node {edge.source_node_id} not found")
            if edge.target_node_id not in self._nodes:
                raise ValueError(f"Target node {edge.target_node_id} not found")
        
        with self._edges_lock:
            self._edges[edge.edge_id] = edge
            self._stats["edges_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"lineage:edge:{edge.edge_id}",
                edge.to_dict(),
                DataType.LINEAGE
            )
        
        # Invalidation du cache
        with self._cache_lock:
            self._impact_cache.clear()
        
        logger.debug(f"Lineage edge created: {edge.source_node_id} -> {edge.target_node_id}")
        return edge.edge_id
    
    async def get_lineage(self, node_id: str, depth: int = 10) -> LineagePath:
        """Récupère la traçabilité d'un nœud."""
        # Vérification du nœud
        with self._nodes_lock:
            if node_id not in self._nodes:
                raise ValueError(f"Node {node_id} not found")
        
        # Construction du chemin
        path = await self._build_lineage_path(node_id, depth)
        
        # Stockage du chemin
        with self._paths_lock:
            self._paths[path.path_id] = path
            self._stats["paths_found"] += 1
        
        logger.debug(f"Lineage path built for {node_id}: {path.length} nodes")
        return path
    
    async def impact_analysis(self, node_id: str) -> ImpactAnalysis:
        """Analyse l'impact d'un nœud."""
        # Vérification du cache
        cache_key = node_id
        with self._cache_lock:
            if cache_key in self._impact_cache:
                return self._impact_cache[cache_key]
        
        # Analyse d'impact
        analysis = await self._perform_impact_analysis(node_id)
        
        # Mise en cache
        if self.config["enable_caching"]:
            with self._cache_lock:
                if len(self._impact_cache) < self.config["max_cache_size"]:
                    self._impact_cache[cache_key] = analysis
        
        self._stats["analyses_performed"] += 1
        
        logger.info(f"Impact analysis completed for {node_id}: {len(analysis.impacted_nodes)} nodes affected")
        return analysis
    
    # ========== MÉTHODES PRIVÉES - TRACABILITÉ ==========
    
    async def _build_lineage_path(self, node_id: str, depth: int) -> LineagePath:
        """Construit un chemin de traçabilité."""
        nodes = []
        edges = []
        visited = set()
        
        # BFS pour trouver le chemin
        queue = deque([(node_id, [])])
        
        while queue and len(nodes) < depth:
            current_id, path = queue.popleft()
            
            if current_id in visited:
                continue
            
            visited.add(current_id)
            
            # Récupération des nœuds
            with self._nodes_lock:
                if current_id in self._nodes:
                    nodes.append(current_id)
            
            # Récupération des arêtes sortantes
            with self._edges_lock:
                outgoing = [e for e in self._edges.values() if e.source_node_id == current_id]
                
                for edge in outgoing:
                    if edge.target_node_id not in visited:
                        edges.append(edge.edge_id)
                        queue.append((edge.target_node_id, path + [edge.edge_id]))
        
        # Création du chemin
        path_obj = LineagePath(
            source_node_id=node_id,
            target_node_id=nodes[-1] if nodes else node_id,
            nodes=nodes,
            edges=edges,
            length=len(nodes)
        )
        
        # Mise à jour de la profondeur moyenne
        self._stats["avg_lineage_depth"] = (
            self._stats["avg_lineage_depth"] * 0.9 + len(nodes) * 0.1
        )
        
        return path_obj
    
    # ========== MÉTHODES PRIVÉES - IMPACT ==========
    
    async def _perform_impact_analysis(self, node_id: str) -> ImpactAnalysis:
        """Exécute une analyse d'impact."""
        impacted_nodes = set()
        impacted_edges = set()
        queue = deque([node_id])
        depth = 0
        
        while queue:
            current_id = queue.popleft()
            
            if current_id in impacted_nodes:
                continue
            
            impacted_nodes.add(current_id)
            
            # Récupération des dépendances
            with self._edges_lock:
                outgoing = [e for e in self._edges.values() if e.source_node_id == current_id]
                
                for edge in outgoing:
                    impacted_edges.add(edge.edge_id)
                    if edge.target_node_id not in impacted_nodes:
                        queue.append(edge.target_node_id)
            
            depth += 1
        
        # Détermination de la sévérité
        severity = "low"
        if len(impacted_nodes) > 10:
            severity = "high"
        elif len(impacted_nodes) > 5:
            severity = "medium"
        
        analysis = ImpactAnalysis(
            source_node_id=node_id,
            impacted_nodes=list(impacted_nodes),
            impacted_edges=list(impacted_edges),
            depth=depth,
            severity=severity,
            metadata={"impact_count": len(impacted_nodes)}
        )
        
        return analysis
    
    # ========== MÉTHODES PRIVÉES - MÉTADONNÉES ==========
    
    async def add_metadata(self, entry: MetadataEntry) -> str:
        """Ajoute des métadonnées."""
        with self._metadata_lock:
            self._metadata[entry.resource_id].append(entry)
            self._stats["metadata_entries"] += 1
            
            # Limitation du nombre d'entrées
            if len(self._metadata[entry.resource_id]) > self.config["max_metadata_per_resource"]:
                self._metadata[entry.resource_id] = self._metadata[entry.resource_id][-self.config["max_metadata_per_resource"]:]
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"lineage:metadata:{entry.metadata_id}",
                entry.to_dict(),
                DataType.METADATA
            )
        
        return entry.metadata_id
    
    async def get_metadata(self, resource_id: str) -> List[MetadataEntry]:
        """Récupère les métadonnées d'une ressource."""
        with self._metadata_lock:
            return self._metadata.get(resource_id, [])
    
    # ========== MÉTHODES PRIVÉES - CHARGEMENT ==========
    
    async def _load_nodes(self) -> None:
        """Charge les nœuds existants."""
        try:
            if self.data_manager:
                nodes_data = await self.data_manager.retrieve(
                    "lineage:nodes",
                    DataType.LINEAGE
                )
                
                if nodes_data:
                    for node_dict in nodes_data:
                        node = self._deserialize_node(node_dict)
                        if node:
                            with self._nodes_lock:
                                self._nodes[node.node_id] = node
            
            logger.info(f"Loaded {len(self._nodes)} lineage nodes")
            
        except Exception as e:
            logger.error(f"Load nodes error: {e}")
    
    async def _load_edges(self) -> None:
        """Charge les arêtes existantes."""
        try:
            if self.data_manager:
                edges_data = await self.data_manager.retrieve(
                    "lineage:edges",
                    DataType.LINEAGE
                )
                
                if edges_data:
                    for edge_dict in edges_data:
                        edge = self._deserialize_edge(edge_dict)
                        if edge:
                            with self._edges_lock:
                                self._edges[edge.edge_id] = edge
            
            logger.info(f"Loaded {len(self._edges)} lineage edges")
            
        except Exception as e:
            logger.error(f"Load edges error: {e}")
    
    def _deserialize_node(self, data: Dict) -> Optional[LineageNode]:
        """Désérialise un nœud."""
        try:
            return LineageNode(
                node_id=data.get("node_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                node_type=LineageNodeType(data.get("node_type", "process")),
                data_type=DataType(data.get("data_type", "market")),
                properties=data.get("properties", {}),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                version=data.get("version", 1)
            )
        except Exception as e:
            logger.error(f"Error deserializing node: {e}")
            return None
    
    def _deserialize_edge(self, data: Dict) -> Optional[LineageEdge]:
        """Désérialise une arête."""
        try:
            return LineageEdge(
                edge_id=data.get("edge_id", str(uuid.uuid4())),
                source_node_id=data.get("source_node_id", ""),
                target_node_id=data.get("target_node_id", ""),
                relationship_type=LineageRelationshipType(data.get("relationship_type", "derived_from")),
                properties=data.get("properties", {}),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                weight=data.get("weight", 1.0)
            )
        except Exception as e:
            logger.error(f"Error deserializing edge: {e}")
            return None
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _impact_analysis_loop(self) -> None:
        """Boucle d'analyse d'impact périodique."""
        while self._is_running:
            await asyncio.sleep(self.config["impact_analysis_interval"])
            
            try:
                # Analyse d'impact pour les nœuds critiques
                with self._nodes_lock:
                    critical_nodes = [
                        node for node in self._nodes.values()
                        if "critical" in node.tags
                    ]
                
                for node in critical_nodes:
                    await self.impact_analysis(node.node_id)
                
            except Exception as e:
                logger.error(f"Impact analysis loop error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._impact_cache) > self.config["max_cache_size"]:
                        keys = list(self._impact_cache.keys())
                        for key in keys[:len(self._impact_cache) - self.config["max_cache_size"]]:
                            del self._impact_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._nodes_lock:
                    self._stats["total_nodes"] = len(self._nodes)
                with self._edges_lock:
                    self._stats["total_edges"] = len(self._edges)
                with self._metadata_lock:
                    self._stats["metadata_resources"] = len(self._metadata)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "lineage:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_node(self, node_id: str) -> Optional[LineageNode]:
        """Récupère un nœud."""
        with self._nodes_lock:
            return self._nodes.get(node_id)
    
    async def get_nodes(self, data_type: Optional[DataType] = None) -> List[LineageNode]:
        """Récupère les nœuds."""
        with self._nodes_lock:
            nodes = list(self._nodes.values())
            if data_type:
                nodes = [n for n in nodes if n.data_type == data_type]
            return nodes
    
    async def get_edge(self, edge_id: str) -> Optional[LineageEdge]:
        """Récupère une arête."""
        with self._edges_lock:
            return self._edges.get(edge_id)
    
    async def get_edges(self, node_id: str) -> List[LineageEdge]:
        """Récupère les arêtes d'un nœud."""
        with self._edges_lock:
            return [
                e for e in self._edges.values()
                if e.source_node_id == node_id or e.target_node_id == node_id
            ]
    
    async def get_path(self, path_id: str) -> Optional[LineagePath]:
        """Récupère un chemin."""
        with self._paths_lock:
            return self._paths.get(path_id)
    
    async def delete_node(self, node_id: str) -> bool:
        """Supprime un nœud."""
        with self._nodes_lock:
            if node_id not in self._nodes:
                return False
            
            del self._nodes[node_id]
            
            # Suppression des arêtes associées
            with self._edges_lock:
                to_delete = [
                    eid for eid, edge in self._edges.items()
                    if edge.source_node_id == node_id or edge.target_node_id == node_id
                ]
                for eid in to_delete:
                    del self._edges[eid]
            
            # Suppression des métadonnées
            with self._metadata_lock:
                if node_id in self._metadata:
                    del self._metadata[node_id]
            
            # Invalidation du cache
            with self._cache_lock:
                self._impact_cache.pop(node_id, None)
        
        logger.info(f"Node deleted: {node_id}")
        return True
    
    async def export_lineage(self, node_id: str, format: str = "json") -> str:
        """Exporte la traçabilité d'un nœud."""
        lineage = await self.get_lineage(node_id)
        
        if format == "json":
            data = {
                "path": lineage.to_dict(),
                "nodes": [],
                "edges": []
            }
            
            for nid in lineage.nodes:
                node = await self.get_node(nid)
                if node:
                    data["nodes"].append(node.to_dict())
            
            for eid in lineage.edges:
                edge = await self.get_edge(eid)
                if edge:
                    data["edges"].append(edge.to_dict())
            
            return json.dumps(data, indent=2)
        
        elif format == "graphviz":
            # Génération de DOT
            lines = ["digraph Lineage {"]
            lines.append('  rankdir="LR";')
            
            for nid in lineage.nodes:
                node = await self.get_node(nid)
                if node:
                    lines.append(f'  "{nid}" [label="{node.name}"];')
            
            for eid in lineage.edges:
                edge = await self.get_edge(eid)
                if edge:
                    lines.append(f'  "{edge.source_node_id}" -> "{edge.target_node_id}" [label="{edge.relationship_type.value}"];')
            
            lines.append("}")
            return "\n".join(lines)
        
        return json.dumps(lineage.to_dict(), indent=2)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._nodes_lock:
            self._stats["total_nodes"] = len(self._nodes)
        with self._edges_lock:
            self._stats["total_edges"] = len(self._edges)
        
        return self._stats.copy()


# ============== FACTORY ==============

class LineageFactory:
    """Factory pour créer des composants de traçabilité."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> LineageEngine:
        """Crée un moteur de traçabilité."""
        engine = LineageEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "LineageNodeType",
    "LineageRelationshipType",
    "MetadataType",
    "LineageNode",
    "LineageEdge",
    "LineagePath",
    "MetadataEntry",
    "ImpactAnalysis",
    "LineageEngineInterface",
    "LineageEngine",
    "LineageFactory"
]
