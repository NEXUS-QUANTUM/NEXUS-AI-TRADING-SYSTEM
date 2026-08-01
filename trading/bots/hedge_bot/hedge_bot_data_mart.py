# trading/bots/hedge_bot/hedge_bot_data_mart.py
# Advanced Data Mart & Analytical Data Processing Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Mart Module - Module avancé de data mart et de traitement analytique des données
pour le Hedge Bot. Gère la création de data marts, l'agrégation de données, les vues analytiques,
les cubes OLAP, et les requêtes optimisées pour les rapports et l'analyse du système de hedging.
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
import pandas as pd
import numpy as np
from collections import defaultdict, deque
import threading
import concurrent.futures
import hashlib
import pickle
import zlib

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_mart")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionResult
)
from trading.bots.hedge_bot.hedge_bot_data_execution import (
    Order, ExecutionResult
)


# ============== ENUMS & TYPES ==============

class DataMartType(Enum):
    """Types de data marts."""
    TRADING = "trading"                  # Trading data mart
    RISK = "risk"                        # Risk data mart
    PERFORMANCE = "performance"          # Performance data mart
    HEDGE = "hedge"                      # Hedge data mart
    PORTFOLIO = "portfolio"              # Portfolio data mart
    MARKET = "market"                    # Market data mart
    COMPLIANCE = "compliance"            # Compliance data mart
    OPERATIONS = "operations"            # Operations data mart
    ANALYTICS = "analytics"              # Analytics data mart


class DataMartAggregation(Enum):
    """Types d'agrégation."""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    STD = "std"
    VAR = "var"
    MEDIAN = "median"
    PERCENTILE = "percentile"
    FIRST = "first"
    LAST = "last"
    CUSTOM = "custom"


class DataMartGranularity(Enum):
    """Granularités des data marts."""
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class DataMartRefresh(Enum):
    """Modes de rafraîchissement."""
    INCREMENTAL = "incremental"
    FULL = "full"
    SCHEDULED = "scheduled"
    ON_DEMAND = "on_demand"
    CONTINUOUS = "continuous"


# ============== DATA MODELS ==============

@dataclass
class DataMart:
    """Modèle de data mart."""
    mart_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    mart_type: DataMartType = DataMartType.TRADING
    description: str = ""
    source_data_type: DataType = DataType.MARKET
    dimensions: List[str] = field(default_factory=list)
    measures: List[Dict[str, Any]] = field(default_factory=list)
    granularity: DataMartGranularity = DataMartGranularity.DAY
    refresh_mode: DataMartRefresh = DataMartRefresh.SCHEDULED
    refresh_interval: int = 86400  # 1 day in seconds
    retention_days: int = 365
    last_refresh: Optional[datetime] = None
    row_count: int = 0
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DataMartQuery:
    """Requête sur un data mart."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mart_id: str = ""
    dimensions: List[str] = field(default_factory=list)
    measures: List[Dict[str, Any]] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    granularity: Optional[DataMartGranularity] = None
    limit: int = 1000
    offset: int = 0
    order_by: List[Tuple[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataMartResult:
    """Résultat de requête de data mart."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query_id: str = ""
    mart_id: str = ""
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    row_count: int = 0
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataMartCube:
    """Cube OLAP."""
    cube_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mart_id: str = ""
    name: str = ""
    dimensions: List[str] = field(default_factory=list)
    measures: List[Dict[str, Any]] = field(default_factory=list)
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class DataMartEngineInterface(ABC):
    """Interface abstraite pour le moteur de data mart."""
    
    @abstractmethod
    async def create_mart(self, mart: DataMart) -> str:
        """Crée un data mart."""
        pass
    
    @abstractmethod
    async def refresh_mart(self, mart_id: str) -> bool:
        """Rafraîchit un data mart."""
        pass
    
    @abstractmethod
    async def query_mart(self, query: DataMartQuery) -> DataMartResult:
        """Exécute une requête sur un data mart."""
        pass
    
    @abstractmethod
    async def build_cube(self, mart_id: str, dimensions: List[str]) -> DataMartCube:
        """Construit un cube OLAP."""
        pass


# ============== IMPLÉMENTATION ==============

class DataMartEngine(DataMartEngineInterface):
    """
    Moteur de data mart avancé pour le Hedge Bot.
    Gère les data marts, les requêtes analytiques et les cubes OLAP.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des data marts
        self._marts: Dict[str, DataMart] = {}
        self._marts_lock = threading.RLock()
        
        # Gestion des données des marts
        self._mart_data: Dict[str, pd.DataFrame] = {}
        self._data_lock = threading.RLock()
        
        # Gestion des cubes
        self._cubes: Dict[str, DataMartCube] = {}
        self._cubes_lock = threading.RLock()
        
        # Cache des requêtes
        self._query_cache: Dict[str, DataMartResult] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "marts_created": 0,
            "marts_refreshed": 0,
            "queries_executed": 0,
            "cubes_built": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_rows_processed": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # Queue de rafraîchissement
        self._refresh_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        
        # État
        self._is_running = False
        
        logger.info("DataMartEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_granularity": DataMartGranularity.DAY,
            "default_refresh_mode": DataMartRefresh.SCHEDULED,
            "default_refresh_interval": 86400,
            "cache_size": 100,
            "cache_ttl": 3600,
            "enable_cache": True,
            "max_query_results": 10000,
            "min_data_points": 10,
            "aggregation_batch_size": 10000,
            "cube_cache_size": 20,
            "retention_days": 365,
            "refresh_check_interval": 3600
        }
    
    async def start(self) -> None:
        """Démarre le moteur de data mart."""
        logger.info("DataMartEngine starting...")
        self._is_running = True
        
        # Chargement des marts existants
        await self._load_marts()
        
        # Chargement des cubes existants
        await self._load_cubes()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._refresh_processor())
        asyncio.create_task(self._refresh_scheduler())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("DataMartEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de data mart."""
        logger.info("DataMartEngine stopping...")
        self._is_running = False
        
        # Sauvegarde des marts
        await self._save_marts()
        
        # Sauvegarde des cubes
        await self._save_cubes()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("DataMartEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_mart(self, mart: DataMart) -> str:
        """Crée un data mart."""
        with self._marts_lock:
            self._marts[mart.mart_id] = mart
            self._stats["marts_created"] += 1
        
        # Création du data mart
        await self._build_mart(mart)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"mart:{mart.mart_id}",
                mart.to_dict(),
                DataType.METADATA
            )
        
        logger.info(f"Data mart created: {mart.name} (id={mart.mart_id})")
        return mart.mart_id
    
    async def refresh_mart(self, mart_id: str) -> bool:
        """Rafraîchit un data mart."""
        with self._marts_lock:
            mart = self._marts.get(mart_id)
            if not mart:
                return False
        
        try:
            # Rafraîchissement
            await self._build_mart(mart)
            
            # Mise à jour des métadonnées
            mart.last_refresh = datetime.now(timezone.utc)
            mart.updated_at = datetime.now(timezone.utc)
            self._stats["marts_refreshed"] += 1
            
            # Invalidation du cache
            with self._cache_lock:
                self._query_cache.clear()
            
            logger.info(f"Data mart refreshed: {mart.name} (id={mart_id})")
            return True
            
        except Exception as e:
            logger.error(f"Refresh mart error: {e}")
            return False
    
    async def query_mart(self, query: DataMartQuery) -> DataMartResult:
        """Exécute une requête sur un data mart."""
        start_time = time.time()
        self._stats["queries_executed"] += 1
        
        # Vérification du cache
        cache_key = self._compute_cache_key(query)
        if self.config["enable_cache"] and cache_key in self._query_cache:
            self._stats["cache_hits"] += 1
            return self._query_cache[cache_key]
        
        self._stats["cache_misses"] += 1
        
        try:
            with self._marts_lock:
                mart = self._marts.get(query.mart_id)
                if not mart:
                    raise ValueError(f"Mart {query.mart_id} not found")
            
            # Récupération des données
            with self._data_lock:
                data = self._mart_data.get(query.mart_id)
                if data is None or data.empty:
                    raise ValueError(f"No data for mart {query.mart_id}")
            
            # Filtrage
            if query.filters:
                data = self._apply_filters(data, query.filters)
            
            # Filtrage temporel
            if query.start_time:
                data = data[data["timestamp"] >= query.start_time]
            if query.end_time:
                data = data[data["timestamp"] <= query.end_time]
            
            # Agrégation
            if query.dimensions and query.measures:
                data = await self._aggregate_data(data, query)
            
            # Tri
            if query.order_by:
                for col, direction in reversed(query.order_by):
                    data = data.sort_values(col, ascending=direction == "asc")
            
            # Limitation
            if query.limit > 0:
                data = data.iloc[query.offset:query.offset + query.limit]
            
            # Création du résultat
            result = DataMartResult(
                query_id=query.query_id,
                mart_id=query.mart_id,
                data=data,
                row_count=len(data),
                execution_time_ms=(time.time() - start_time) * 1000,
                metadata={"query": query.to_dict()}
            )
            
            # Mise en cache
            if self.config["enable_cache"]:
                with self._cache_lock:
                    if len(self._query_cache) < self.config["cache_size"]:
                        self._query_cache[cache_key] = result
            
            self._stats["total_rows_processed"] += len(data)
            logger.debug(f"Query executed: {query.query_id} rows={len(data)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Query error: {e}")
            raise
    
    async def build_cube(self, mart_id: str, dimensions: List[str]) -> DataMartCube:
        """Construit un cube OLAP."""
        # Récupération des données
        with self._data_lock:
            data = self._mart_data.get(mart_id)
            if data is None or data.empty:
                raise ValueError(f"No data for mart {mart_id}")
        
        # Construction du cube
        cube_data = data.copy()
        
        # Aggrégation par dimensions
        if dimensions:
            cube_data = await self._aggregate_by_dimensions(cube_data, dimensions)
        
        # Création du cube
        cube = DataMartCube(
            mart_id=mart_id,
            name=f"cube_{mart_id}_{'_'.join(dimensions)}",
            dimensions=dimensions,
            data=cube_data
        )
        
        with self._cubes_lock:
            self._cubes[cube.cube_id] = cube
            self._stats["cubes_built"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"cube:{cube.cube_id}",
                cube.to_dict(),
                DataType.CUBE
            )
        
        logger.info(f"Cube built: {cube.name} dimensions={dimensions}")
        return cube
    
    # ========== MÉTHODES PRIVÉES - CONSTRUCTION ==========
    
    async def _build_mart(self, mart: DataMart) -> None:
        """Construit un data mart."""
        if not self.data_manager:
            raise ValueError("Data manager not available")
        
        # Récupération des données sources
        source_data = await self.data_manager.retrieve_all(mart.source_data_type)
        
        if not source_data:
            logger.warning(f"No source data for mart {mart.name}")
            return
        
        # Conversion en DataFrame
        data = pd.DataFrame([r.value for r in source_data if r.value])
        
        if data.empty:
            logger.warning(f"Empty data for mart {mart.name}")
            return
        
        # Ajout des colonnes temporelles
        if "timestamp" in data.columns:
            data["timestamp"] = pd.to_datetime(data["timestamp"])
            data["date"] = data["timestamp"].dt.date
            data["hour"] = data["timestamp"].dt.hour
            data["day_of_week"] = data["timestamp"].dt.dayofweek
            data["month"] = data["timestamp"].dt.month
            data["quarter"] = data["timestamp"].dt.quarter
            data["year"] = data["timestamp"].dt.year
        
        # Calcul des mesures
        for measure in mart.measures:
            if measure["type"] == "agg":
                if "column" in measure and "method" in measure:
                    if measure["method"] == "sum":
                        data[measure["name"]] = data.groupby("date")[measure["column"]].transform("sum")
                    elif measure["method"] == "avg":
                        data[measure["name"]] = data.groupby("date")[measure["column"]].transform("mean")
                    elif measure["method"] == "count":
                        data[measure["name"]] = data.groupby("date")[measure["column"]].transform("count")
        
        # Mise à jour de la granularité
        if mart.granularity != DataMartGranularity.SECOND:
            # Agrégation à la granularité souhaitée
            granularity_map = {
                DataMartGranularity.MINUTE: "1min",
                DataMartGranularity.HOUR: "1h",
                DataMartGranularity.DAY: "1d",
                DataMartGranularity.WEEK: "1w",
                DataMartGranularity.MONTH: "1M",
                DataMartGranularity.QUARTER: "1Q",
                DataMartGranularity.YEAR: "1Y"
            }
            
            freq = granularity_map.get(mart.granularity)
            if freq and "timestamp" in data.columns:
                data.set_index("timestamp", inplace=True)
                data = data.resample(freq).agg(self._get_aggregation_dict(mart.measures))
                data.reset_index(inplace=True)
        
        # Stockage des données
        with self._data_lock:
            self._mart_data[mart.mart_id] = data
        
        # Mise à jour des métriques
        mart.row_count = len(data)
        mart.size_bytes = len(pickle.dumps(data))
        mart.last_refresh = datetime.now(timezone.utc)
    
    def _get_aggregation_dict(self, measures: List[Dict]) -> Dict:
        """Construit le dictionnaire d'agrégation."""
        agg_dict = {}
        for measure in measures:
            if "column" in measure and "method" in measure:
                agg_dict[measure["column"]] = measure["method"]
        return agg_dict
    
    # ========== MÉTHODES PRIVÉES - AGRÉGATION ==========
    
    async def _aggregate_data(self, data: pd.DataFrame, query: DataMartQuery) -> pd.DataFrame:
        """Agrège les données selon la requête."""
        if not query.dimensions or not query.measures:
            return data
        
        # Construction du dictionnaire d'agrégation
        agg_dict = {}
        for measure in query.measures:
            if "column" in measure and "method" in measure:
                agg_dict[measure["column"]] = measure["method"]
        
        if not agg_dict:
            return data
        
        # Agrégation
        result = data.groupby(query.dimensions).agg(agg_dict).reset_index()
        
        # Renommage des colonnes
        for measure in query.measures:
            if "name" in measure and "column" in measure:
                result.rename(columns={measure["column"]: measure["name"]}, inplace=True)
        
        return result
    
    async def _aggregate_by_dimensions(self, data: pd.DataFrame, dimensions: List[str]) -> pd.DataFrame:
        """Agrège les données par dimensions."""
        if not dimensions:
            return data
        
        # Colonnes numériques pour l'agrégation
        numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
        
        if not numeric_cols:
            return data
        
        # Agrégation
        result = data.groupby(dimensions)[numeric_cols].sum().reset_index()
        
        return result
    
    # ========== MÉTHODES PRIVÉES - FILTRAGE ==========
    
    def _apply_filters(self, data: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
        """Applique des filtres aux données."""
        result = data.copy()
        
        for key, value in filters.items():
            if key not in result.columns:
                continue
            
            if isinstance(value, (list, tuple)):
                result = result[result[key].isin(value)]
            elif isinstance(value, dict):
                op = value.get("operator", "eq")
                val = value.get("value")
                
                if op == "eq":
                    result = result[result[key] == val]
                elif op == "ne":
                    result = result[result[key] != val]
                elif op == "gt":
                    result = result[result[key] > val]
                elif op == "gte":
                    result = result[result[key] >= val]
                elif op == "lt":
                    result = result[result[key] < val]
                elif op == "lte":
                    result = result[result[key] <= val]
                elif op == "contains":
                    result = result[result[key].str.contains(val, na=False)]
            else:
                result = result[result[key] == value]
        
        return result
    
    # ========== MÉTHODES PRIVÉES - CACHE ==========
    
    def _compute_cache_key(self, query: DataMartQuery) -> str:
        """Calcule une clé de cache."""
        key_data = {
            "mart_id": query.mart_id,
            "dimensions": sorted(query.dimensions),
            "measures": sorted([m.get("name", "") for m in query.measures]),
            "filters": query.filters,
            "start_time": query.start_time.isoformat() if query.start_time else None,
            "end_time": query.end_time.isoformat() if query.end_time else None,
            "granularity": query.granularity.value if query.granularity else None
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    # ========== MÉTHODES PRIVÉES - CHARGEMENT ==========
    
    async def _load_marts(self) -> None:
        """Charge les data marts existants."""
        try:
            if self.data_manager:
                marts_data = await self.data_manager.retrieve(
                    "marts:all",
                    DataType.METADATA
                )
                
                if marts_data:
                    for mart_dict in marts_data:
                        mart = self._deserialize_mart(mart_dict)
                        if mart:
                            with self._marts_lock:
                                self._marts[mart.mart_id] = mart
                                
                            # Chargement des données
                            if self.data_manager:
                                data = await self.data_manager.retrieve(
                                    f"mart_data:{mart.mart_id}",
                                    DataType.MART_DATA
                                )
                                if data:
                                    with self._data_lock:
                                        self._mart_data[mart.mart_id] = pd.DataFrame(data)
            
            logger.info(f"Loaded {len(self._marts)} data marts")
            
        except Exception as e:
            logger.error(f"Load marts error: {e}")
    
    async def _load_cubes(self) -> None:
        """Charge les cubes existants."""
        try:
            if self.data_manager:
                cubes_data = await self.data_manager.retrieve(
                    "cubes:all",
                    DataType.CUBE
                )
                
                if cubes_data:
                    for cube_dict in cubes_data:
                        cube = self._deserialize_cube(cube_dict)
                        if cube:
                            with self._cubes_lock:
                                self._cubes[cube.cube_id] = cube
            
            logger.info(f"Loaded {len(self._cubes)} cubes")
            
        except Exception as e:
            logger.error(f"Load cubes error: {e}")
    
    async def _save_marts(self) -> None:
        """Sauvegarde les data marts."""
        try:
            if self.data_manager:
                with self._marts_lock:
                    for mart in self._marts.values():
                        await self.data_manager.store(
                            f"mart:{mart.mart_id}",
                            mart.to_dict(),
                            DataType.METADATA
                        )
                
                with self._data_lock:
                    for mart_id, data in self._mart_data.items():
                        await self.data_manager.store(
                            f"mart_data:{mart_id}",
                            data.to_dict(orient="records"),
                            DataType.MART_DATA
                        )
            
            logger.info("Marts saved")
            
        except Exception as e:
            logger.error(f"Save marts error: {e}")
    
    async def _save_cubes(self) -> None:
        """Sauvegarde les cubes."""
        try:
            if self.data_manager:
                with self._cubes_lock:
                    for cube in self._cubes.values():
                        await self.data_manager.store(
                            f"cube:{cube.cube_id}",
                            cube.to_dict(),
                            DataType.CUBE
                        )
            
            logger.info("Cubes saved")
            
        except Exception as e:
            logger.error(f"Save cubes error: {e}")
    
    def _deserialize_mart(self, data: Dict) -> Optional[DataMart]:
        """Désérialise un data mart."""
        try:
            return DataMart(
                mart_id=data.get("mart_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                mart_type=DataMartType(data.get("mart_type", "trading")),
                description=data.get("description", ""),
                source_data_type=DataType(data.get("source_data_type", "market")),
                dimensions=data.get("dimensions", []),
                measures=data.get("measures", []),
                granularity=DataMartGranularity(data.get("granularity", "day")),
                refresh_mode=DataMartRefresh(data.get("refresh_mode", "scheduled")),
                refresh_interval=data.get("refresh_interval", 86400),
                retention_days=data.get("retention_days", 365),
                last_refresh=datetime.fromisoformat(data.get("last_refresh")) if data.get("last_refresh") else None,
                row_count=data.get("row_count", 0),
                size_bytes=data.get("size_bytes", 0),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing mart: {e}")
            return None
    
    def _deserialize_cube(self, data: Dict) -> Optional[DataMartCube]:
        """Désérialise un cube."""
        try:
            return DataMartCube(
                cube_id=data.get("cube_id", str(uuid.uuid4())),
                mart_id=data.get("mart_id", ""),
                name=data.get("name", ""),
                dimensions=data.get("dimensions", []),
                measures=data.get("measures", []),
                data=pd.DataFrame(data.get("data", [])),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                metadata=data.get("metadata", {})
            )
        except Exception as e:
            logger.error(f"Error deserializing cube: {e}")
            return None
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _refresh_processor(self) -> None:
        """Traite les jobs de rafraîchissement."""
        while self._is_running:
            try:
                mart_id = await self._refresh_queue.get()
                asyncio.create_task(self.refresh_mart(mart_id))
                
            except Exception as e:
                logger.error(f"Refresh processor error: {e}")
                await asyncio.sleep(1)
    
    async def _refresh_scheduler(self) -> None:
        """Planifie les rafraîchissements."""
        while self._is_running:
            await asyncio.sleep(self.config["refresh_check_interval"])
            
            try:
                now = datetime.now(timezone.utc)
                
                with self._marts_lock:
                    for mart in self._marts.values():
                        if not mart.active:
                            continue
                        
                        if mart.refresh_mode == DataMartRefresh.CONTINUOUS:
                            await self._refresh_queue.put(mart.mart_id)
                        
                        elif mart.refresh_mode == DataMartRefresh.SCHEDULED:
                            if mart.last_refresh:
                                age = (now - mart.last_refresh).total_seconds()
                                if age >= mart.refresh_interval:
                                    await self._refresh_queue.put(mart.mart_id)
                            else:
                                await self._refresh_queue.put(mart.mart_id)
                
            except Exception as e:
                logger.error(f"Refresh scheduler error: {e}")
    
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
                with self._marts_lock:
                    self._stats["total_marts"] = len(self._marts)
                    active_marts = len([m for m in self._marts.values() if m.active])
                    self._stats["active_marts"] = active_marts
                
                with self._data_lock:
                    self._stats["mart_data_size"] = sum(len(v) for v in self._mart_data.values())
                
                with self._cubes_lock:
                    self._stats["total_cubes"] = len(self._cubes)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "mart:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_mart(self, mart_id: str) -> Optional[DataMart]:
        """Récupère un data mart."""
        with self._marts_lock:
            return self._marts.get(mart_id)
    
    async def get_marts(self) -> List[DataMart]:
        """Récupère les data marts."""
        with self._marts_lock:
            return list(self._marts.values())
    
    async def get_cube(self, cube_id: str) -> Optional[DataMartCube]:
        """Récupère un cube."""
        with self._cubes_lock:
            return self._cubes.get(cube_id)
    
    async def get_cubes(self, mart_id: str) -> List[DataMartCube]:
        """Récupère les cubes d'un mart."""
        with self._cubes_lock:
            return [c for c in self._cubes.values() if c.mart_id == mart_id]
    
    async def delete_mart(self, mart_id: str) -> bool:
        """Supprime un data mart."""
        with self._marts_lock:
            if mart_id not in self._marts:
                return False
            del self._marts[mart_id]
        
        with self._data_lock:
            if mart_id in self._mart_data:
                del self._mart_data[mart_id]
        
        # Suppression des cubes associés
        with self._cubes_lock:
            cube_ids = [cid for cid, c in self._cubes.items() if c.mart_id == mart_id]
            for cid in cube_ids:
                del self._cubes[cid]
        
        logger.info(f"Data mart deleted: {mart_id}")
        return True
    
    async def export_mart(self, mart_id: str, format: str = "csv") -> str:
        """Exporte un data mart."""
        with self._data_lock:
            data = self._mart_data.get(mart_id)
            if data is None:
                return ""
        
        if format == "csv":
            return data.to_csv(index=False)
        elif format == "json":
            return data.to_json(orient="records", indent=2)
        elif format == "parquet":
            return data.to_parquet()
        else:
            return data.to_csv(index=False)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._marts_lock:
            self._stats["total_marts"] = len(self._marts)
        with self._data_lock:
            self._stats["total_rows"] = sum(len(v) for v in self._mart_data.values())
        
        return self._stats.copy()


# ============== FACTORY ==============

class DataMartFactory:
    """Factory pour créer des composants de data mart."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> DataMartEngine:
        """Crée un moteur de data mart."""
        engine = DataMartEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "DataMartType",
    "DataMartAggregation",
    "DataMartGranularity",
    "DataMartRefresh",
    "DataMart",
    "DataMartQuery",
    "DataMartResult",
    "DataMartCube",
    "DataMartEngineInterface",
    "DataMartEngine",
    "DataMartFactory"
]
