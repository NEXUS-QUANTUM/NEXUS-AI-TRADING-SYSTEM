# trading/bots/hedge_bot/hedge_bot_data_hybrid.py
# Advanced Hybrid Cloud & Multi-Data Integration Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Hybrid Data Module - Module d'intégration hybride avancé pour le Hedge Bot.
Gère l'intégration multi-cloud, le data mesh, la fédération de données,
l'orchestration de données hybrides et l'optimisation des coûts de données.
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
import pandas as pd
import numpy as np
from collections import defaultdict, deque
import threading
import concurrent.futures
import hashlib
import aiohttp
import aiohttp.client_exceptions

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_hybrid")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DistributedDataManager
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
    EDGE = "edge"
    HYBRID = "hybrid"


class DataMeshDomain(Enum):
    """Domaines du data mesh."""
    TRADING = "trading"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    MARKET = "market"
    EXECUTION = "execution"
    COMPLIANCE = "compliance"
    AI_ML = "ai_ml"
    OPERATIONS = "operations"
    CUSTOMER = "customer"


class HybridQueryMode(Enum):
    """Modes de requête hybride."""
    LOCAL_ONLY = "local_only"
    CLOUD_ONLY = "cloud_only"
    HYBRID = "hybrid"
    FEDERATED = "federated"
    CACHED = "cached"


class DataFederationStrategy(Enum):
    """Stratégies de fédération de données."""
    PUSH = "push"              # Pousser les données vers le consommateur
    PULL = "pull"              # Tirer les données depuis la source
    HYBRID = "hybrid"          # Hybride
    EVENT_DRIVEN = "event_driven"  # Piloté par événements
    BATCH = "batch"            # Par batch


# ============== DATA MODELS ==============

@dataclass
class HybridDataSource:
    """Source de données hybride."""
    source_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    provider: CloudProvider = CloudProvider.AWS
    endpoint: str = ""
    credentials: Dict[str, Any] = field(default_factory=dict)
    data_types: List[DataType] = field(default_factory=list)
    latency_ms: float = 0.0
    throughput: float = 0.0
    cost_per_request: float = 0.0
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    priority: int = 1
    region: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "provider": self.provider.value,
            "endpoint": self.endpoint,
            "credentials": self.credentials,
            "data_types": [dt.value for dt in self.data_types],
            "latency_ms": self.latency_ms,
            "throughput": self.throughput,
            "cost_per_request": self.cost_per_request,
            "status": self.status,
            "metadata": self.metadata,
            "tags": self.tags,
            "priority": self.priority,
            "region": self.region,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "active": self.active
        }


@dataclass
class DataMeshProduct:
    """Produit de data mesh."""
    product_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    domain: DataMeshDomain = DataMeshDomain.TRADING
    name: str = ""
    description: str = ""
    datasets: List[str] = field(default_factory=list)
    schema: Dict[str, Any] = field(default_factory=dict)
    owner: str = ""
    quality_score: float = 0.0
    freshness: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class HybridQuery:
    """Requête hybride."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mode: HybridQueryMode = HybridQueryMode.HYBRID
    sources: List[str] = field(default_factory=list)
    query: Any = None
    priority: int = 1
    timeout: float = 30.0
    cache_ttl: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    result: Optional[Any] = None
    execution_time_ms: float = 0.0
    cost: float = 0.0


@dataclass
class FederationConfig:
    """Configuration de fédération."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy: DataFederationStrategy = DataFederationStrategy.PUSH
    source_domains: List[DataMeshDomain] = field(default_factory=list)
    target_domain: DataMeshDomain = DataMeshDomain.TRADING
    schedule: Optional[str] = None
    transformations: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    active: bool = True


# ============== INTERFACES ==============

class HybridDataEngineInterface(ABC):
    """Interface abstraite pour le moteur de données hybride."""
    
    @abstractmethod
    async def register_source(self, source: HybridDataSource) -> str:
        """Enregistre une source de données."""
        pass
    
    @abstractmethod
    async def execute_query(self, query: HybridQuery) -> HybridQuery:
        """Exécute une requête hybride."""
        pass
    
    @abstractmethod
    async def publish_product(self, product: DataMeshProduct) -> str:
        """Publie un produit de data mesh."""
        pass


# ============== IMPLÉMENTATION ==============

class HybridDataEngine(HybridDataEngineInterface):
    """
    Moteur de données hybride avancé pour le Hedge Bot.
    Gère l'intégration multi-cloud, le data mesh, la fédération et l'orchestration.
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
        
        # Gestion des sources
        self._sources: Dict[str, HybridDataSource] = {}
        self._sources_lock = threading.RLock()
        
        # Gestion des produits
        self._products: Dict[str, DataMeshProduct] = {}
        self._products_lock = threading.RLock()
        
        # Gestion des requêtes
        self._queries: Dict[str, HybridQuery] = {}
        self._queries_lock = threading.RLock()
        
        # Gestion des fédérations
        self._federations: Dict[str, FederationConfig] = {}
        self._fed_lock = threading.RLock()
        
        # Cache des données
        self._data_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        
        # Sessions HTTP
        self._sessions: Dict[str, aiohttp.ClientSession] = {}
        self._sessions_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "sources_registered": 0,
            "products_published": 0,
            "queries_executed": 0,
            "federations_active": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_cost": 0.0,
            "avg_latency_ms": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("HybridDataEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "cache_size": 10000,
            "cache_ttl": 3600,
            "enable_cache": True,
            "enable_encryption": True,
            "enable_federation": True,
            "enable_cost_optimization": True,
            "query_timeout": 30.0,
            "max_query_sources": 5,
            "cost_threshold": 0.01,
            "latency_threshold": 100,
            "session_timeout": 60,
            "retry_count": 3,
            "retry_delay": 1.0,
            "federation_interval": 300,
            "health_check_interval": 60,
            "default_provider": CloudProvider.AWS
        }
    
    async def start(self) -> None:
        """Démarre le moteur de données hybride."""
        logger.info("HybridDataEngine starting...")
        self._is_running = True
        
        # Chargement des sources existantes
        await self._load_sources()
        
        # Chargement des produits existants
        await self._load_products()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._federation_loop())
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("HybridDataEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de données hybride."""
        logger.info("HybridDataEngine stopping...")
        self._is_running = False
        
        # Fermeture des sessions
        with self._sessions_lock:
            for session in self._sessions.values():
                await session.close()
            self._sessions.clear()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("HybridDataEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def register_source(self, source: HybridDataSource) -> str:
        """Enregistre une source de données."""
        # Chiffrement des credentials
        if self.encryption_engine and self.config["enable_encryption"]:
            encrypted_creds = {}
            for key, value in source.credentials.items():
                if isinstance(value, str):
                    encrypted = await self.encryption_engine.encrypt(
                        value.encode(),
                        "data_source_credentials"
                    )
                    encrypted_creds[key] = encrypted.to_dict()
            source.credentials = encrypted_creds
        
        with self._sources_lock:
            self._sources[source.source_id] = source
            self._stats["sources_registered"] += 1
        
        # Création de la session HTTP
        await self._create_session(source)
        
        logger.info(f"Data source registered: {source.name} (provider={source.provider.value})")
        return source.source_id
    
    async def execute_query(self, query: HybridQuery) -> HybridQuery:
        """Exécute une requête hybride."""
        start_time = time.time()
        self._stats["queries_executed"] += 1
        
        with self._queries_lock:
            self._queries[query.query_id] = query
        
        try:
            query.status = "running"
            query.executed_at = datetime.now(timezone.utc)
            
            # Vérification du cache
            cache_key = self._compute_cache_key(query)
            if self.config["enable_cache"] and cache_key in self._data_cache:
                self._stats["cache_hits"] += 1
                query.result = self._data_cache[cache_key]
                query.status = "completed"
                query.completed_at = datetime.now(timezone.utc)
                query.execution_time_ms = (time.time() - start_time) * 1000
                return query
            
            self._stats["cache_misses"] += 1
            
            # Sélection des sources
            sources = await self._select_sources(query)
            
            # Exécution selon le mode
            if query.mode == HybridQueryMode.LOCAL_ONLY:
                result = await self._query_local(sources, query)
            elif query.mode == HybridQueryMode.CLOUD_ONLY:
                result = await self._query_cloud(sources, query)
            elif query.mode == HybridQueryMode.FEDERATED:
                result = await self._query_federated(sources, query)
            else:
                result = await self._query_hybrid(sources, query)
            
            # Mise en cache
            if self.config["enable_cache"] and query.cache_ttl:
                with self._cache_lock:
                    if len(self._data_cache) < self.config["cache_size"]:
                        self._data_cache[cache_key] = result
            
            query.result = result
            query.status = "completed"
            query.completed_at = datetime.now(timezone.utc)
            query.execution_time_ms = (time.time() - start_time) * 1000
            
            # Calcul des coûts
            query.cost = await self._calculate_cost(sources, query)
            self._stats["total_cost"] += query.cost
            
            # Mise à jour des métriques
            self._stats["avg_latency_ms"] = (
                self._stats["avg_latency_ms"] * 0.9 + query.execution_time_ms * 0.1
            )
            
            logger.info(f"Query executed: {query.query_id} "
                       f"mode={query.mode.value} sources={len(sources)} "
                       f"time={query.execution_time_ms:.2f}ms cost={query.cost:.6f}")
            
            return query
            
        except Exception as e:
            query.status = "failed"
            query.completed_at = datetime.now(timezone.utc)
            query.execution_time_ms = (time.time() - start_time) * 1000
            query.metadata["error"] = str(e)
            
            logger.error(f"Query execution failed: {query.query_id} - {e}")
            return query
    
    async def publish_product(self, product: DataMeshProduct) -> str:
        """Publie un produit de data mesh."""
        with self._products_lock:
            self._products[product.product_id] = product
            self._stats["products_published"] += 1
        
        # Enregistrement du produit
        if self.data_manager:
            await self.data_manager.store(
                f"mesh:product:{product.product_id}",
                product.to_dict(),
                DataType.PRODUCT
            )
        
        logger.info(f"Data mesh product published: {product.name} "
                   f"(domain={product.domain.value})")
        return product.product_id
    
    # ========== MÉTHODES PRIVÉES - REQUÊTES ==========
    
    async def _select_sources(self, query: HybridQuery) -> List[HybridDataSource]:
        """Sélectionne les sources pour une requête."""
        with self._sources_lock:
            sources = list(self._sources.values())
            
            # Filtrage par type de données
            data_type = query.metadata.get("data_type")
            if data_type:
                sources = [s for s in sources if data_type in [dt.value for dt in s.data_types]]
            
            # Priorisation
            sources.sort(key=lambda s: (s.priority, -s.throughput, s.latency_ms))
            
            # Limitation
            max_sources = self.config["max_query_sources"]
            if len(sources) > max_sources:
                sources = sources[:max_sources]
            
            return sources
    
    async def _query_local(self, sources: List[HybridDataSource], query: HybridQuery) -> Any:
        """Exécute une requête locale."""
        # Utilisation du data manager local
        if self.data_manager:
            # Construction de la requête
            data_query = DataQuery(
                query_id=query.query_id,
                data_type=DataType(query.metadata.get("data_type", "market")),
                filter_criteria=query.metadata.get("filters", {})
            )
            result = await self.data_manager.query(data_query)
            return result
        
        return {"message": "No local data manager available"}
    
    async def _query_cloud(self, sources: List[HybridDataSource], query: HybridQuery) -> Any:
        """Exécute une requête cloud."""
        results = []
        
        for source in sources:
            if source.provider in [CloudProvider.AWS, CloudProvider.GCP, CloudProvider.AZURE]:
                try:
                    result = await self._query_cloud_source(source, query)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Cloud query error for {source.name}: {e}")
        
        # Agrégation des résultats
        if len(results) == 1:
            return results[0]
        elif results:
            return await self._aggregate_results(results, query)
        else:
            return {"message": "No results from cloud sources"}
    
    async def _query_cloud_source(self, source: HybridDataSource, query: HybridQuery) -> Any:
        """Interroge une source cloud spécifique."""
        session = await self._get_session(source)
        
        try:
            # Construction de la requête
            endpoint = source.endpoint
            params = query.metadata.get("params", {})
            
            # Envoi de la requête
            async with session.get(endpoint, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Cloud source error: {response.status}")
                    
        except Exception as e:
            logger.error(f"Cloud source query error: {e}")
            raise
    
    async def _query_federated(self, sources: List[HybridDataSource], query: HybridQuery) -> Any:
        """Exécute une requête fédérée."""
        results = []
        
        # Requête parallèle sur toutes les sources
        tasks = []
        for source in sources:
            task = asyncio.create_task(self._query_source(source, query))
            tasks.append(task)
        
        # Attente des résultats
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                results.append(result)
            except Exception as e:
                logger.error(f"Federated query error: {e}")
        
        # Agrégation
        return await self._aggregate_results(results, query)
    
    async def _query_hybrid(self, sources: List[HybridDataSource], query: HybridQuery) -> Any:
        """Exécute une requête hybride."""
        # Stratégie hybride: local d'abord, puis cloud
        try:
            # Essai local
            local_result = await self._query_local(sources, query)
            if local_result:
                return local_result
        except Exception as e:
            logger.debug(f"Local query failed, falling back to cloud: {e}")
        
        # Fallback cloud
        return await self._query_cloud(sources, query)
    
    async def _query_source(self, source: HybridDataSource, query: HybridQuery) -> Any:
        """Interroge une source unique."""
        if source.provider == CloudProvider.LOCAL:
            return await self._query_local([source], query)
        else:
            return await self._query_cloud_source(source, query)
    
    async def _aggregate_results(self, results: List[Any], query: HybridQuery) -> Any:
        """Agrège les résultats des différentes sources."""
        if not results:
            return {"message": "No results"}
        
        # Si tous les résultats sont des listes
        if all(isinstance(r, list) for r in results):
            return [item for sublist in results for item in sublist]
        
        # Si tous les résultats sont des dictionnaires
        if all(isinstance(r, dict) for r in results):
            aggregated = {}
            for r in results:
                aggregated.update(r)
            return aggregated
        
        # Par défaut, retourner le premier résultat
        return results[0]
    
    # ========== MÉTHODES PRIVÉES - SESSIONS ==========
    
    async def _create_session(self, source: HybridDataSource) -> None:
        """Crée une session HTTP pour une source."""
        with self._sessions_lock:
            if source.source_id not in self._sessions:
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                
                # Ajout des headers d'authentification
                if "api_key" in source.credentials:
                    headers["X-API-Key"] = source.credentials["api_key"]
                elif "bearer_token" in source.credentials:
                    headers["Authorization"] = f"Bearer {source.credentials['bearer_token']}"
                
                self._sessions[source.source_id] = aiohttp.ClientSession(
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.config["session_timeout"])
                )
    
    async def _get_session(self, source: HybridDataSource) -> aiohttp.ClientSession:
        """Récupère la session pour une source."""
        with self._sessions_lock:
            if source.source_id not in self._sessions:
                await self._create_session(source)
            return self._sessions[source.source_id]
    
    # ========== MÉTHODES PRIVÉES - UTILITAIRES ==========
    
    def _compute_cache_key(self, query: HybridQuery) -> str:
        """Calcule une clé de cache."""
        key_data = {
            "mode": query.mode.value,
            "sources": sorted(query.sources),
            "query": str(query.query),
            "metadata": query.metadata
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    async def _calculate_cost(self, sources: List[HybridDataSource], query: HybridQuery) -> float:
        """Calcule le coût d'une requête."""
        total_cost = 0.0
        
        for source in sources:
            # Estimation basée sur le nombre de requêtes et le coût par requête
            total_cost += source.cost_per_request
        
        # Optimisation des coûts
        if self.config["enable_cost_optimization"]:
            # Réduction du coût pour les sources locales
            local_sources = [s for s in sources if s.provider == CloudProvider.LOCAL]
            if local_sources:
                total_cost *= 0.5
        
        return total_cost
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _federation_loop(self) -> None:
        """Boucle de fédération de données."""
        while self._is_running:
            await asyncio.sleep(self.config["federation_interval"])
            
            try:
                # Traitement des fédérations actives
                with self._fed_lock:
                    for federation in self._federations.values():
                        if federation.active:
                            await self._process_federation(federation)
                
            except Exception as e:
                logger.error(f"Federation loop error: {e}")
    
    async def _process_federation(self, federation: FederationConfig) -> None:
        """Traite une fédération."""
        # Récupération des données des sources
        sources = []
        with self._sources_lock:
            for source in self._sources.values():
                domain = source.metadata.get("domain")
                if domain and domain in [d.value for d in federation.source_domains]:
                    sources.append(source)
        
        if not sources:
            return
        
        # Exécution de la fédération
        query = HybridQuery(
            mode=HybridQueryMode.FEDERATED,
            sources=[s.source_id for s in sources],
            metadata={"federation_id": federation.config_id}
        )
        
        result = await self.execute_query(query)
        
        # Stockage du résultat fédéré
        if self.data_manager:
            await self.data_manager.store(
                f"federation:{federation.config_id}:result",
                result,
                DataType.FEDERATED
            )
    
    async def _health_check_loop(self) -> None:
        """Boucle de vérification de santé."""
        while self._is_running:
            await asyncio.sleep(self.config["health_check_interval"])
            
            try:
                # Vérification des sources
                with self._sources_lock:
                    for source in self._sources.values():
                        try:
                            # Test de connexion
                            session = await self._get_session(source)
                            async with session.head(source.endpoint) as response:
                                if response.status >= 400:
                                    source.status = "degraded"
                                else:
                                    source.status = "active"
                        except Exception as e:
                            source.status = "unreachable"
                            logger.warning(f"Health check failed for {source.name}: {e}")
                
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                with self._cache_lock:
                    if len(self._data_cache) > self.config["cache_size"]:
                        keys = list(self._data_cache.keys())
                        for key in keys[:len(self._data_cache) - self.config["cache_size"]]:
                            del self._data_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._sources_lock:
                    self._stats["sources_count"] = len(self._sources)
                    active_sources = sum(1 for s in self._sources.values() if s.status == "active")
                    self._stats["active_sources"] = active_sources
                
                with self._products_lock:
                    self._stats["products_count"] = len(self._products)
                
                with self._fed_lock:
                    self._stats["federations_count"] = len(self._federations)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "hybrid:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_sources(self) -> None:
        """Charge les sources existantes."""
        try:
            if self.data_manager:
                sources_data = await self.data_manager.retrieve(
                    "hybrid:sources",
                    DataType.CONFIG
                )
                
                if sources_data:
                    for source_dict in sources_data:
                        source = self._deserialize_source(source_dict)
                        if source:
                            with self._sources_lock:
                                self._sources[source.source_id] = source
                                await self._create_session(source)
            
            logger.info(f"Loaded {len(self._sources)} data sources")
            
        except Exception as e:
            logger.error(f"Load sources error: {e}")
    
    async def _load_products(self) -> None:
        """Charge les produits existants."""
        try:
            if self.data_manager:
                products_data = await self.data_manager.retrieve(
                    "mesh:products",
                    DataType.PRODUCT
                )
                
                if products_data:
                    for product_dict in products_data:
                        product = self._deserialize_product(product_dict)
                        if product:
                            with self._products_lock:
                                self._products[product.product_id] = product
            
            logger.info(f"Loaded {len(self._products)} data mesh products")
            
        except Exception as e:
            logger.error(f"Load products error: {e}")
    
    # ========== MÉTHODES DE DÉSÉRIALISATION ==========
    
    def _deserialize_source(self, data: Dict) -> Optional[HybridDataSource]:
        """Désérialise une source de données."""
        try:
            return HybridDataSource(
                source_id=data.get("source_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                provider=CloudProvider(data.get("provider", "aws")),
                endpoint=data.get("endpoint", ""),
                credentials=data.get("credentials", {}),
                data_types=[DataType(dt) for dt in data.get("data_types", [])],
                latency_ms=data.get("latency_ms", 0.0),
                throughput=data.get("throughput", 0.0),
                cost_per_request=data.get("cost_per_request", 0.0),
                status=data.get("status", "active"),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                priority=data.get("priority", 1),
                region=data.get("region", ""),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                active=data.get("active", True)
            )
        except Exception as e:
            logger.error(f"Error deserializing source: {e}")
            return None
    
    def _deserialize_product(self, data: Dict) -> Optional[DataMeshProduct]:
        """Désérialise un produit de data mesh."""
        try:
            return DataMeshProduct(
                product_id=data.get("product_id", str(uuid.uuid4())),
                domain=DataMeshDomain(data.get("domain", "trading")),
                name=data.get("name", ""),
                description=data.get("description", ""),
                datasets=data.get("datasets", []),
                schema=data.get("schema", {}),
                owner=data.get("owner", ""),
                quality_score=data.get("quality_score", 0.0),
                freshness=datetime.fromisoformat(data.get("freshness", datetime.now(timezone.utc).isoformat())),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing product: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_source(self, source_id: str) -> Optional[HybridDataSource]:
        """Récupère une source de données."""
        with self._sources_lock:
            return self._sources.get(source_id)
    
    async def get_sources(self, provider: Optional[CloudProvider] = None) -> List[HybridDataSource]:
        """Récupère les sources de données."""
        with self._sources_lock:
            sources = list(self._sources.values())
            if provider:
                sources = [s for s in sources if s.provider == provider]
            return sources
    
    async def get_product(self, product_id: str) -> Optional[DataMeshProduct]:
        """Récupère un produit de data mesh."""
        with self._products_lock:
            return self._products.get(product_id)
    
    async def get_products(self, domain: Optional[DataMeshDomain] = None) -> List[DataMeshProduct]:
        """Récupère les produits de data mesh."""
        with self._products_lock:
            products = list(self._products.values())
            if domain:
                products = [p for p in products if p.domain == domain]
            return products
    
    async def get_query(self, query_id: str) -> Optional[HybridQuery]:
        """Récupère une requête hybride."""
        with self._queries_lock:
            return self._queries.get(query_id)
    
    async def get_queries(self, status: Optional[str] = None) -> List[HybridQuery]:
        """Récupère les requêtes hybrides."""
        with self._queries_lock:
            queries = list(self._queries.values())
            if status:
                queries = [q for q in queries if q.status == status]
            return sorted(queries, key=lambda q: q.created_at, reverse=True)
    
    async def create_federation(self, config: FederationConfig) -> str:
        """Crée une configuration de fédération."""
        with self._fed_lock:
            self._federations[config.config_id] = config
        
        logger.info(f"Federation configuration created: {config.name}")
        return config.config_id
    
    async def get_federation(self, config_id: str) -> Optional[FederationConfig]:
        """Récupère une configuration de fédération."""
        with self._fed_lock:
            return self._federations.get(config_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._sources_lock:
            self._stats["total_sources"] = len(self._sources)
        with self._products_lock:
            self._stats["total_products"] = len(self._products)
        with self._fed_lock:
            self._stats["total_federations"] = len(self._federations)
        with self._cache_lock:
            self._stats["cache_entries"] = len(self._data_cache)
        
        return self._stats.copy()


# ============== DATA MESH PRODUCT BUILDER ==============

class DataMeshProductBuilder:
    """
    Constructeur de produits de data mesh.
    Facilite la création de produits de data mesh.
    """
    
    def __init__(self):
        self._product = DataMeshProduct()
    
    def domain(self, domain: DataMeshDomain) -> 'DataMeshProductBuilder':
        """Définit le domaine."""
        self._product.domain = domain
        return self
    
    def name(self, name: str) -> 'DataMeshProductBuilder':
        """Définit le nom."""
        self._product.name = name
        return self
    
    def description(self, description: str) -> 'DataMeshProductBuilder':
        """Définit la description."""
        self._product.description = description
        return self
    
    def datasets(self, datasets: List[str]) -> 'DataMeshProductBuilder':
        """Définit les datasets."""
        self._product.datasets = datasets
        return self
    
    def schema(self, schema: Dict[str, Any]) -> 'DataMeshProductBuilder':
        """Définit le schéma."""
        self._product.schema = schema
        return self
    
    def owner(self, owner: str) -> 'DataMeshProductBuilder':
        """Définit le propriétaire."""
        self._product.owner = owner
        return self
    
    def quality_score(self, score: float) -> 'DataMeshProductBuilder':
        """Définit le score de qualité."""
        self._product.quality_score = score
        return self
    
    def tags(self, tags: List[str]) -> 'DataMeshProductBuilder':
        """Définit les tags."""
        self._product.tags = tags
        return self
    
    def metadata(self, metadata: Dict[str, Any]) -> 'DataMeshProductBuilder':
        """Définit les métadonnées."""
        self._product.metadata = metadata
        return self
    
    def build(self) -> DataMeshProduct:
        """Construit le produit."""
        if not self._product.name:
            raise ValueError("Product name is required")
        return self._product


# ============== FACTORY ==============

class HybridDataFactory:
    """Factory pour créer des composants de données hybrides."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> HybridDataEngine:
        """Crée un moteur de données hybride."""
        engine = HybridDataEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_product_builder() -> DataMeshProductBuilder:
        """Crée un constructeur de produits de data mesh."""
        return DataMeshProductBuilder()


# ============== EXPORT ==============

__all__ = [
    "CloudProvider",
    "DataMeshDomain",
    "HybridQueryMode",
    "DataFederationStrategy",
    "HybridDataSource",
    "DataMeshProduct",
    "HybridQuery",
    "FederationConfig",
    "HybridDataEngineInterface",
    "HybridDataEngine",
    "DataMeshProductBuilder",
    "HybridDataFactory"
]
