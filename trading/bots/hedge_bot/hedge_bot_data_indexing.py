# trading/bots/hedge_bot/hedge_bot_data_indexing.py
# Advanced Data Indexing & Query Optimization Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Indexing Module - Module avancé d'indexation de données et d'optimisation des requêtes
pour le Hedge Bot. Gère les index B-tree, les index bitmap, les index composites, la recherche
full-text, et l'optimisation des performances des requêtes.
"""

import asyncio
import json
import math
import time
import bisect
import struct
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
import mmap
import os

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_indexing")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class IndexType(Enum):
    """Types d'index."""
    BTREE = "btree"                    # Arbre B
    BITMAP = "bitmap"                  # Index bitmap
    HASH = "hash"                      # Index de hachage
    COMPOSITE = "composite"            # Index composite
    FULLTEXT = "fulltext"              # Recherche full-text
    SPATIAL = "spatial"                # Index spatial
    INVERTED = "inverted"              # Index inversé
    RANGE = "range"                    # Index par plage
    GIN = "gin"                        # GIN (Generalized Inverted Index)
    GIST = "gist"                      # GiST (Generalized Search Tree)


class IndexScope(Enum):
    """Portées d'index."""
    GLOBAL = "global"                  # Index global
    LOCAL = "local"                    # Index local
    PARTITION = "partition"            # Index par partition
    TABLE = "table"                    # Index par table
    FIELD = "field"                    # Index par champ
    CUSTOM = "custom"                  # Index personnalisé


class QueryOptimizationLevel(Enum):
    """Niveaux d'optimisation des requêtes."""
    NONE = "none"                      # Pas d'optimisation
    BASIC = "basic"                    # Optimisation de base
    ADVANCED = "advanced"              # Optimisation avancée
    FULL = "full"                      # Optimisation complète


# ============== DATA MODELS ==============

@dataclass
class DataIndex:
    """Modèle d'index de données."""
    index_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    index_type: IndexType = IndexType.BTREE
    scope: IndexScope = IndexScope.TABLE
    fields: List[str] = field(default_factory=list)
    data_type: DataType = DataType.MARKET
    unique: bool = False
    case_sensitive: bool = True
    fill_factor: float = 0.9
    storage_path: str = ""
    size_bytes: int = 0
    entries: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "index_id": self.index_id,
            "name": self.name,
            "index_type": self.index_type.value,
            "scope": self.scope.value,
            "fields": self.fields,
            "data_type": self.data_type.value,
            "unique": self.unique,
            "case_sensitive": self.case_sensitive,
            "fill_factor": self.fill_factor,
            "storage_path": self.storage_path,
            "size_bytes": self.size_bytes,
            "entries": self.entries,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags,
            "active": self.active
        }


@dataclass
class IndexEntry:
    """Entrée d'index."""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    index_id: str = ""
    key: Any = None
    value: Any = None
    record_id: str = ""
    position: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class QueryPlan:
    """Plan de requête optimisé."""
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query: str = ""
    index_ids: List[str] = field(default_factory=list)
    estimated_cost: float = 0.0
    estimated_rows: int = 0
    actual_rows: int = 0
    execution_time_ms: float = 0.0
    steps: List[Dict[str, Any]] = field(default_factory=list)
    optimizations: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============== INTERFACES ==============

class IndexingEngineInterface(ABC):
    """Interface abstraite pour le moteur d'indexation."""
    
    @abstractmethod
    async def create_index(self, config: Dict[str, Any]) -> DataIndex:
        """Crée un index."""
        pass
    
    @abstractmethod
    async def drop_index(self, index_id: str) -> bool:
        """Supprime un index."""
        pass
    
    @abstractmethod
    async def query(self, query: DataQuery) -> DataQuery:
        """Exécute une requête optimisée."""
        pass


# ============== IMPLÉMENTATION ==============

class IndexingEngine(IndexingEngineInterface):
    """
    Moteur d'indexation avancé pour le Hedge Bot.
    Gère l'indexation des données et l'optimisation des requêtes.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des index
        self._indices: Dict[str, DataIndex] = {}
        self._indices_lock = threading.RLock()
        
        # Gestion des index B-tree
        self._btree_indices: Dict[str, Dict[Any, List[str]]] = {}
        self._btree_lock = threading.RLock()
        
        # Gestion des index bitmap
        self._bitmap_indices: Dict[str, Dict[Any, Set[str]]] = {}
        self._bitmap_lock = threading.RLock()
        
        # Gestion des index hash
        self._hash_indices: Dict[str, Dict[Any, List[str]]] = {}
        self._hash_lock = threading.RLock()
        
        # Gestion des index full-text
        self._fulltext_indices: Dict[str, Dict[str, Set[str]]] = {}
        self._fulltext_lock = threading.RLock()
        
        # Cache des plans de requête
        self._query_cache: Dict[str, QueryPlan] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "indices_created": 0,
            "indices_dropped": 0,
            "queries_optimized": 0,
            "index_hits": 0,
            "index_misses": 0,
            "avg_query_time": 0.0,
            "cache_hit_rate": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("IndexingEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_index_type": IndexType.BTREE,
            "default_scope": IndexScope.TABLE,
            "max_index_size": 100 * 1024 * 1024,  # 100 MB
            "cache_size": 1000,
            "cache_ttl": 3600,
            "enable_caching": True,
            "enable_auto_index": True,
            "enable_query_optimization": True,
            "optimization_level": QueryOptimizationLevel.ADVANCED,
            "btree_order": 64,
            "fill_factor": 0.9,
            "min_index_entries": 100,
            "max_index_entries": 1000000
        }
    
    async def start(self) -> None:
        """Démarre le moteur d'indexation."""
        logger.info("IndexingEngine starting...")
        self._is_running = True
        
        # Chargement des index existants
        await self._load_indices()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        asyncio.create_task(self._index_builder_loop())
        
        logger.info("IndexingEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur d'indexation."""
        logger.info("IndexingEngine stopping...")
        self._is_running = False
        
        # Sauvegarde des index
        await self._save_indices()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("IndexingEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_index(self, config: Dict[str, Any]) -> DataIndex:
        """Crée un index."""
        index = DataIndex(
            name=config.get("name", f"Index_{uuid.uuid4().hex[:8]}"),
            index_type=IndexType(config.get("index_type", self.config["default_index_type"])),
            scope=IndexScope(config.get("scope", self.config["default_scope"])),
            fields=config.get("fields", []),
            data_type=DataType(config.get("data_type", "market")),
            unique=config.get("unique", False),
            case_sensitive=config.get("case_sensitive", True),
            fill_factor=config.get("fill_factor", self.config["fill_factor"]),
            storage_path=config.get("storage_path", f"./indices/{uuid.uuid4().hex[:8]}.idx"),
            metadata=config.get("metadata", {}),
            tags=config.get("tags", [])
        )
        
        # Vérification des champs
        if not index.fields:
            raise ValueError("At least one field is required for indexing")
        
        # Création de l'index en mémoire
        await self._build_index(index)
        
        # Stockage de l'index
        with self._indices_lock:
            self._indices[index.index_id] = index
            self._stats["indices_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"index:{index.index_id}",
                index.to_dict(),
                DataType.INDEX
            )
        
        logger.info(f"Index created: {index.name} (type={index.index_type.value}, fields={index.fields})")
        return index
    
    async def drop_index(self, index_id: str) -> bool:
        """Supprime un index."""
        with self._indices_lock:
            index = self._indices.get(index_id)
            if not index:
                return False
            
            del self._indices[index_id]
            self._stats["indices_dropped"] += 1
        
        # Suppression des données d'index
        if index.index_type == IndexType.BTREE:
            with self._btree_lock:
                if index_id in self._btree_indices:
                    del self._btree_indices[index_id]
        elif index.index_type == IndexType.BITMAP:
            with self._bitmap_lock:
                if index_id in self._bitmap_indices:
                    del self._bitmap_indices[index_id]
        elif index.index_type == IndexType.HASH:
            with self._hash_lock:
                if index_id in self._hash_indices:
                    del self._hash_indices[index_id]
        elif index.index_type == IndexType.FULLTEXT:
            with self._fulltext_lock:
                if index_id in self._fulltext_indices:
                    del self._fulltext_indices[index_id]
        
        # Suppression du fichier
        if index.storage_path and os.path.exists(index.storage_path):
            try:
                os.remove(index.storage_path)
            except:
                pass
        
        logger.info(f"Index dropped: {index.name}")
        return True
    
    async def query(self, query: DataQuery) -> DataQuery:
        """Exécute une requête optimisée."""
        start_time = time.time()
        self._stats["queries_optimized"] += 1
        
        try:
            # Vérification du cache
            cache_key = self._compute_cache_key(query)
            with self._cache_lock:
                if cache_key in self._query_cache:
                    cached = self._query_cache[cache_key]
                    age = (datetime.now(timezone.utc) - cached.created_at).total_seconds()
                    if age < self.config["cache_ttl"]:
                        self._stats["index_hits"] += 1
                        logger.debug(f"Query cache hit: {cache_key}")
                        return await self._execute_cached_query(query, cached)
                    else:
                        del self._query_cache[cache_key]
            
            self._stats["index_misses"] += 1
            
            # Analyse de la requête
            analyzed = await self._analyze_query(query)
            
            # Sélection des index
            selected_indices = await self._select_indices(analyzed)
            
            # Création du plan de requête
            plan = await self._create_query_plan(analyzed, selected_indices)
            
            # Exécution optimisée
            result = await self._execute_query_plan(query, plan)
            
            # Mise en cache
            if self.config["enable_caching"]:
                with self._cache_lock:
                    if len(self._query_cache) < self.config["cache_size"]:
                        self._query_cache[cache_key] = plan
            
            # Mise à jour des statistiques
            execution_time = time.time() - start_time
            self._stats["avg_query_time"] = (
                self._stats["avg_query_time"] * 0.9 + execution_time * 0.1
            )
            
            logger.debug(f"Query optimized: {query.query_id} "
                       f"time={execution_time*1000:.2f}ms indices={len(selected_indices)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Query optimization error: {e}")
            # Fallback: exécution directe
            if self.data_manager:
                return await self.data_manager.query(query)
            raise
    
    # ========== MÉTHODES PRIVÉES - INDEXATION ==========
    
    async def _build_index(self, index: DataIndex) -> None:
        """Construit un index."""
        if index.index_type == IndexType.BTREE:
            await self._build_btree_index(index)
        elif index.index_type == IndexType.BITMAP:
            await self._build_bitmap_index(index)
        elif index.index_type == IndexType.HASH:
            await self._build_hash_index(index)
        elif index.index_type == IndexType.FULLTEXT:
            await self._build_fulltext_index(index)
        elif index.index_type == IndexType.COMPOSITE:
            await self._build_composite_index(index)
        else:
            await self._build_btree_index(index)
    
    async def _build_btree_index(self, index: DataIndex) -> None:
        """Construit un index B-tree."""
        if not self.data_manager:
            return
        
        # Récupération des données
        data = await self.data_manager.retrieve_all(index.data_type)
        
        btree = {}
        
        for record in data:
            if not record.value:
                continue
            
            # Extraction de la clé
            key = self._extract_key(record.value, index.fields)
            
            if key is None:
                continue
            
            # Conversion en clé hashable
            key_hash = self._hash_key(key)
            
            if key_hash not in btree:
                btree[key_hash] = []
            btree[key_hash].append(record.record_id)
        
        # Stockage de l'index
        with self._btree_lock:
            self._btree_indices[index.index_id] = btree
        
        # Mise à jour des métadonnées
        index.entries = sum(len(v) for v in btree.values())
        index.size_bytes = len(pickle.dumps(btree))
        
        logger.info(f"B-tree index built: {index.name} entries={index.entries}")
    
    async def _build_bitmap_index(self, index: DataIndex) -> None:
        """Construit un index bitmap."""
        if not self.data_manager:
            return
        
        data = await self.data_manager.retrieve_all(index.data_type)
        
        bitmap = defaultdict(set)
        
        for record in data:
            if not record.value:
                continue
            
            key = self._extract_key(record.value, index.fields)
            
            if key is None:
                continue
            
            key_hash = self._hash_key(key)
            bitmap[key_hash].add(record.record_id)
        
        with self._bitmap_lock:
            self._bitmap_indices[index.index_id] = dict(bitmap)
        
        index.entries = sum(len(v) for v in bitmap.values())
        index.size_bytes = len(pickle.dumps(bitmap))
        
        logger.info(f"Bitmap index built: {index.name} entries={index.entries}")
    
    async def _build_hash_index(self, index: DataIndex) -> None:
        """Construit un index hash."""
        if not self.data_manager:
            return
        
        data = await self.data_manager.retrieve_all(index.data_type)
        
        hash_index = {}
        
        for record in data:
            if not record.value:
                continue
            
            key = self._extract_key(record.value, index.fields)
            
            if key is None:
                continue
            
            key_hash = self._hash_key(key)
            hash_index[key_hash] = record.record_id
        
        with self._hash_lock:
            self._hash_indices[index.index_id] = hash_index
        
        index.entries = len(hash_index)
        index.size_bytes = len(pickle.dumps(hash_index))
        
        logger.info(f"Hash index built: {index.name} entries={index.entries}")
    
    async def _build_fulltext_index(self, index: DataIndex) -> None:
        """Construit un index full-text."""
        if not self.data_manager:
            return
        
        data = await self.data_manager.retrieve_all(index.data_type)
        
        fulltext = defaultdict(set)
        
        for record in data:
            if not record.value:
                continue
            
            # Extraction du texte
            text = self._extract_text(record.value, index.fields)
            
            if not text:
                continue
            
            # Tokenisation
            tokens = self._tokenize(text)
            
            for token in tokens:
                fulltext[token].add(record.record_id)
        
        with self._fulltext_lock:
            self._fulltext_indices[index.index_id] = dict(fulltext)
        
        index.entries = sum(len(v) for v in fulltext.values())
        index.size_bytes = len(pickle.dumps(fulltext))
        
        logger.info(f"Full-text index built: {index.name} entries={index.entries}")
    
    async def _build_composite_index(self, index: DataIndex) -> None:
        """Construit un index composite."""
        # Utilisation de B-tree pour l'index composite
        await self._build_btree_index(index)
    
    def _extract_key(self, record: Dict[str, Any], fields: List[str]) -> Any:
        """Extrait une clé d'un enregistrement."""
        if len(fields) == 1:
            return record.get(fields[0])
        else:
            # Clé composite
            return tuple(record.get(field) for field in fields)
    
    def _extract_text(self, record: Dict[str, Any], fields: List[str]) -> str:
        """Extrait le texte d'un enregistrement."""
        texts = []
        for field in fields:
            value = record.get(field)
            if value:
                texts.append(str(value))
        return " ".join(texts)
    
    def _hash_key(self, key: Any) -> str:
        """Hache une clé."""
        if isinstance(key, (list, tuple, dict)):
            key_str = json.dumps(key, sort_keys=True)
        else:
            key_str = str(key)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenise un texte pour l'index full-text."""
        # Nettoyage
        text = text.lower()
        # Suppression de la ponctuation
        import re
        text = re.sub(r'[^\w\s]', '', text)
        # Tokenisation
        return text.split()
    
    # ========== MÉTHODES PRIVÉES - OPTIMISATION ==========
    
    async def _analyze_query(self, query: DataQuery) -> Dict[str, Any]:
        """Analyse une requête."""
        analysis = {
            "query_id": query.query_id,
            "data_type": query.data_type,
            "fields": query.filter_criteria,
            "keys": query.keys,
            "has_index": False,
            "estimated_rows": len(query.keys) if query.keys else 0,
            "complexity": "simple"
        }
        
        # Analyse des filtres
        if query.filter_criteria:
            analysis["has_index"] = True
            
            # Comptage des critères
            filter_count = len(query.filter_criteria)
            if filter_count > 3:
                analysis["complexity"] = "complex"
            elif filter_count > 1:
                analysis["complexity"] = "medium"
        
        # Analyse des clés
        if query.keys:
            analysis["estimated_rows"] = len(query.keys)
        
        return analysis
    
    async def _select_indices(self, analyzed: Dict[str, Any]) -> List[DataIndex]:
        """Sélectionne les index appropriés."""
        selected = []
        
        with self._indices_lock:
            for index in self._indices.values():
                if not index.active:
                    continue
                
                if index.data_type != analyzed["data_type"]:
                    continue
                
                # Vérification de la pertinence de l'index
                relevance = await self._calculate_relevance(index, analyzed)
                if relevance > 0.5:
                    selected.append(index)
        
        # Tri par pertinence
        selected.sort(key=lambda idx: self._calculate_relevance(idx, analyzed), reverse=True)
        
        return selected[:3]  # Limite de 3 index
    
    async def _calculate_relevance(self, index: DataIndex, analyzed: Dict[str, Any]) -> float:
        """Calcule la pertinence d'un index."""
        relevance = 0.0
        
        # Vérification des champs
        if analyzed["fields"]:
            matching_fields = [f for f in index.fields if f in analyzed["fields"]]
            if matching_fields:
                relevance += 0.5 * (len(matching_fields) / len(index.fields))
        
        # Taille de l'index
        if index.entries > 0:
            # Plus l'index est grand, plus il est pertinent
            relevance += 0.2 * min(1.0, index.entries / 1000)
        
        # Type d'index
        if index.index_type == IndexType.BTREE:
            relevance += 0.1
        elif index.index_type == IndexType.BITMAP:
            relevance += 0.15  # Très efficace pour les cardinalités faibles
        
        return min(1.0, relevance)
    
    async def _create_query_plan(
        self,
        analyzed: Dict[str, Any],
        indices: List[DataIndex]
    ) -> QueryPlan:
        """Crée un plan de requête."""
        plan = QueryPlan(
            query=analyzed["query_id"],
            index_ids=[idx.index_id for idx in indices],
            estimated_cost=0.0,
            estimated_rows=analyzed["estimated_rows"],
            steps=[],
            optimizations=[]
        )
        
        if indices:
            # Utilisation des index
            plan.optimizations.append(f"Using {len(indices)} indices")
            
            # Estimation du coût
            total_entries = sum(idx.entries for idx in indices)
            plan.estimated_cost = total_entries / 1000 if total_entries > 0 else 0.1
        else:
            # Scan complet
            plan.optimizations.append("Full table scan")
            plan.estimated_cost = 1.0
        
        # Optimisations avancées
        if self.config["optimization_level"] in [QueryOptimizationLevel.ADVANCED, QueryOptimizationLevel.FULL]:
            if analyzed["complexity"] == "complex":
                plan.optimizations.append("Complex query optimization")
            
            # Prédiction des index
            plan.optimizations.append("Predicted index usage")
        
        return plan
    
    async def _execute_query_plan(self, query: DataQuery, plan: QueryPlan) -> DataQuery:
        """Exécute un plan de requête."""
        # Utilisation des index pour la recherche
        if plan.index_ids:
            results = set()
            
            for index_id in plan.index_ids:
                # Récupération de l'index
                with self._indices_lock:
                    index = self._indices.get(index_id)
                    if not index:
                        continue
                
                # Recherche dans l'index approprié
                if index.index_type == IndexType.BTREE:
                    records = await self._search_btree(index, query)
                elif index.index_type == IndexType.BITMAP:
                    records = await self._search_bitmap(index, query)
                elif index.index_type == IndexType.HASH:
                    records = await self._search_hash(index, query)
                elif index.index_type == IndexType.FULLTEXT:
                    records = await self._search_fulltext(index, query)
                else:
                    records = []
                
                results.update(records)
            
            # Si des résultats ont été trouvés
            if results:
                # Récupération des enregistrements complets
                records = []
                if self.data_manager:
                    for record_id in results:
                        record = await self.data_manager.retrieve_by_id(record_id)
                        if record:
                            records.append(record)
                
                # Mise à jour de la requête
                query.records = records
                query.total_count = len(records)
                
                return query
        
        # Fallback: requête directe
        if self.data_manager:
            return await self.data_manager.query(query)
        
        return query
    
    async def _search_btree(self, index: DataIndex, query: DataQuery) -> Set[str]:
        """Recherche dans un index B-tree."""
        with self._btree_lock:
            btree = self._btree_indices.get(index.index_id, {})
        
        results = set()
        
        for key in query.keys:
            key_hash = self._hash_key(key)
            if key_hash in btree:
                results.update(btree[key_hash])
        
        return results
    
    async def _search_bitmap(self, index: DataIndex, query: DataQuery) -> Set[str]:
        """Recherche dans un index bitmap."""
        with self._bitmap_lock:
            bitmap = self._bitmap_indices.get(index.index_id, {})
        
        results = set()
        
        for key in query.keys:
            key_hash = self._hash_key(key)
            if key_hash in bitmap:
                results.update(bitmap[key_hash])
        
        return results
    
    async def _search_hash(self, index: DataIndex, query: DataQuery) -> Set[str]:
        """Recherche dans un index hash."""
        with self._hash_lock:
            hash_index = self._hash_indices.get(index.index_id, {})
        
        results = set()
        
        for key in query.keys:
            key_hash = self._hash_key(key)
            if key_hash in hash_index:
                results.add(hash_index[key_hash])
        
        return results
    
    async def _search_fulltext(self, index: DataIndex, query: DataQuery) -> Set[str]:
        """Recherche dans un index full-text."""
        with self._fulltext_lock:
            fulltext = self._fulltext_indices.get(index.index_id, {})
        
        results = set()
        
        for key in query.keys:
            if isinstance(key, str):
                tokens = self._tokenize(key)
                for token in tokens:
                    if token in fulltext:
                        results.update(fulltext[token])
        
        return results
    
    async def _execute_cached_query(self, query: DataQuery, plan: QueryPlan) -> DataQuery:
        """Exécute une requête depuis le cache."""
        return query
    
    def _compute_cache_key(self, query: DataQuery) -> str:
        """Calcule une clé de cache."""
        key_data = {
            "data_type": query.data_type.value if hasattr(query.data_type, 'value') else str(query.data_type),
            "keys": sorted(query.keys),
            "filters": query.filter_criteria
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _index_builder_loop(self) -> None:
        """Boucle de construction d'index."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                # Reconstruction des index si nécessaire
                with self._indices_lock:
                    for index in self._indices.values():
                        if index.entries > self.config["max_index_entries"]:
                            logger.info(f"Rebuilding large index: {index.name}")
                            await self._build_index(index)
                
            except Exception as e:
                logger.error(f"Index builder error: {e}")
    
    async def _load_indices(self) -> None:
        """Charge les index existants."""
        try:
            if self.data_manager:
                indices_data = await self.data_manager.retrieve_all(DataType.INDEX)
                
                for data in indices_data:
                    if data.value:
                        index = self._deserialize_index(data.value)
                        if index:
                            with self._indices_lock:
                                self._indices[index.index_id] = index
                            
                            # Rechargement de l'index en mémoire
                            await self._load_index_data(index)
            
            logger.info(f"Loaded {len(self._indices)} indices")
            
        except Exception as e:
            logger.error(f"Load indices error: {e}")
    
    async def _load_index_data(self, index: DataIndex) -> None:
        """Charge les données d'un index."""
        if index.storage_path and os.path.exists(index.storage_path):
            try:
                with open(index.storage_path, 'rb') as f:
                    data = pickle.load(f)
                
                if index.index_type == IndexType.BTREE:
                    with self._btree_lock:
                        self._btree_indices[index.index_id] = data
                elif index.index_type == IndexType.BITMAP:
                    with self._bitmap_lock:
                        self._bitmap_indices[index.index_id] = data
                elif index.index_type == IndexType.HASH:
                    with self._hash_lock:
                        self._hash_indices[index.index_id] = data
                elif index.index_type == IndexType.FULLTEXT:
                    with self._fulltext_lock:
                        self._fulltext_indices[index.index_id] = data
                
            except Exception as e:
                logger.error(f"Load index data error: {e}")
    
    async def _save_indices(self) -> None:
        """Sauvegarde les index."""
        # Sauvegarde des index B-tree
        with self._btree_lock:
            for index_id, btree in self._btree_indices.items():
                try:
                    with self._indices_lock:
                        index = self._indices.get(index_id)
                        if index:
                            with open(index.storage_path, 'wb') as f:
                                pickle.dump(btree, f)
                except Exception as e:
                    logger.error(f"Save B-tree index error: {e}")
        
        # Sauvegarde des autres index...
    
    def _deserialize_index(self, data: Dict) -> Optional[DataIndex]:
        """Désérialise un index."""
        try:
            return DataIndex(
                index_id=data.get("index_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                index_type=IndexType(data.get("index_type", "btree")),
                scope=IndexScope(data.get("scope", "table")),
                fields=data.get("fields", []),
                data_type=DataType(data.get("data_type", "market")),
                unique=data.get("unique", False),
                case_sensitive=data.get("case_sensitive", True),
                fill_factor=data.get("fill_factor", 0.9),
                storage_path=data.get("storage_path", ""),
                size_bytes=data.get("size_bytes", 0),
                entries=data.get("entries", 0),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True)
            )
        except Exception as e:
            logger.error(f"Error deserializing index: {e}")
            return None
    
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
                with self._indices_lock:
                    self._stats["total_indices"] = len(self._indices)
                
                # Calcul du taux de hits
                total = self._stats["index_hits"] + self._stats["index_misses"]
                if total > 0:
                    self._stats["cache_hit_rate"] = self._stats["index_hits"] / total
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "indexing:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_index(self, index_id: str) -> Optional[DataIndex]:
        """Récupère un index."""
        with self._indices_lock:
            return self._indices.get(index_id)
    
    async def get_indices(self, data_type: Optional[DataType] = None) -> List[DataIndex]:
        """Récupère les index."""
        with self._indices_lock:
            indices = list(self._indices.values())
            if data_type:
                indices = [i for i in indices if i.data_type == data_type]
            return indices
    
    async def rebuild_index(self, index_id: str) -> bool:
        """Reconstruit un index."""
        with self._indices_lock:
            index = self._indices.get(index_id)
            if not index:
                return False
        
        try:
            await self._build_index(index)
            return True
        except Exception as e:
            logger.error(f"Index rebuild error: {e}")
            return False
    
    async def optimize_indexes(self) -> Dict[str, Any]:
        """Optimise tous les index."""
        results = {
            "optimized": 0,
            "failed": 0,
            "details": []
        }
        
        with self._indices_lock:
            for index in self._indices.values():
                try:
                    # Vérification de l'index
                    if await self._check_index_health(index):
                        # Réorganisation si nécessaire
                        await self._rebuild_index(index.index_id)
                        results["optimized"] += 1
                        results["details"].append(f"Index {index.name} optimized")
                    else:
                        results["failed"] += 1
                        results["details"].append(f"Index {index.name} needs rebuild")
                except Exception as e:
                    results["failed"] += 1
                    results["details"].append(f"Index {index.name} failed: {e}")
        
        return results
    
    async def _check_index_health(self, index: DataIndex) -> bool:
        """Vérifie la santé d'un index."""
        # Vérification de la taille
        if index.entries > self.config["max_index_entries"]:
            return False
        
        # Vérification du facteur de remplissage
        if index.fill_factor < 0.5:
            return False
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._indices_lock:
            self._stats["total_indices"] = len(self._indices)
        
        return self._stats.copy()


# ============== INDEX TOOLS ==============

class IndexTools:
    """Outils pour la gestion des index."""
    
    @staticmethod
    def estimate_index_size(entries: int, avg_key_size: int = 50, avg_value_size: int = 100) -> int:
        """Estime la taille d'un index."""
        # Estimation approximative
        overhead = 1024  # 1 KB
        entry_size = avg_key_size + avg_value_size + 64  # Overhead
        return overhead + entries * entry_size
    
    @staticmethod
    def get_index_health(index: DataIndex) -> Dict[str, Any]:
        """Analyse la santé d'un index."""
        return {
            "entries": index.entries,
            "size_mb": index.size_bytes / (1024 * 1024),
            "fill_factor": index.fill_factor,
            "health_score": min(1.0, index.entries / 10000),
            "recommendations": []
        }


# ============== FACTORY ==============

class IndexingFactory:
    """Factory pour créer des composants d'indexation."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> IndexingEngine:
        """Crée un moteur d'indexation."""
        engine = IndexingEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "IndexType",
    "IndexScope",
    "QueryOptimizationLevel",
    "DataIndex",
    "IndexEntry",
    "QueryPlan",
    "IndexingEngineInterface",
    "IndexingEngine",
    "IndexTools",
    "IndexingFactory"
]
