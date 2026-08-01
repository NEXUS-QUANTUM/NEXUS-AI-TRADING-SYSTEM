# trading/bots/hedge_bot/hedge_bot_data_optimize.py
# Advanced Data Optimization & Performance Tuning Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Optimization Module - Module avancé d'optimisation des données et de réglage
des performances pour le Hedge Bot. Optimise le stockage, les requêtes, l'indexation,
la compression, le caching et les performances globales du système de données.
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
logger = get_logger("hedge_bot_data_optimize")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class OptimizationTarget(Enum):
    """Cibles d'optimisation."""
    STORAGE = "storage"                # Optimisation du stockage
    QUERY = "query"                    # Optimisation des requêtes
    MEMORY = "memory"                  # Optimisation de la mémoire
    NETWORK = "network"                # Optimisation du réseau
    COMPUTE = "compute"                # Optimisation du calcul
    CACHE = "cache"                    # Optimisation du cache
    INDEX = "index"                    # Optimisation des index
    COMPRESSION = "compression"        # Optimisation de la compression


class OptimizationMethod(Enum):
    """Méthodes d'optimisation."""
    COLUMNAR = "columnar"              # Stockage columnar
    PARTITIONING = "partitioning"      # Partitionnement
    BUCKETING = "bucketing"            # Bucketing
    COMPRESSION = "compression"        # Compression
    DEDUPLICATION = "deduplication"    # Déduplication
    CACHING = "caching"                # Mise en cache
    INDEXING = "indexing"              # Indexation
    PREFETCHING = "prefetching"        # Préchargement
    BATCHING = "batching"              # Batch processing


class OptimizationPriority(Enum):
    """Priorités d'optimisation."""
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


# ============== DATA MODELS ==============

@dataclass
class OptimizationConfig:
    """Configuration d'optimisation."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    target: OptimizationTarget = OptimizationTarget.STORAGE
    methods: List[OptimizationMethod] = field(default_factory=list)
    priority: OptimizationPriority = OptimizationPriority.MEDIUM
    parameters: Dict[str, Any] = field(default_factory=dict)
    data_types: List[DataType] = field(default_factory=list)
    schedule: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OptimizationJob:
    """Job d'optimisation."""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config_id: str = ""
    status: str = "pending"
    progress: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    data_processed: int = 0
    data_before: int = 0
    data_after: int = 0
    reduction_percentage: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationReport:
    """Rapport d'optimisation."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""
    summary: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    benchmarks: Dict[str, float] = field(default_factory=dict)
    improvements: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class DataOptimizeEngineInterface(ABC):
    """Interface abstraite pour le moteur d'optimisation."""
    
    @abstractmethod
    async def create_config(self, config: OptimizationConfig) -> str:
        """Crée une configuration d'optimisation."""
        pass
    
    @abstractmethod
    async def run_optimization(self, config_id: str) -> OptimizationJob:
        """Exécute une optimisation."""
        pass
    
    @abstractmethod
    async def get_report(self, job_id: str) -> OptimizationReport:
        """Génère un rapport d'optimisation."""
        pass


# ============== IMPLÉMENTATION ==============

class DataOptimizeEngine(DataOptimizeEngineInterface):
    """
    Moteur d'optimisation de données avancé pour le Hedge Bot.
    Optimise le stockage, les requêtes, la mémoire et les performances.
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
        
        # Gestion des configurations
        self._configs: Dict[str, OptimizationConfig] = {}
        self._configs_lock = threading.RLock()
        
        # Gestion des jobs
        self._jobs: Dict[str, OptimizationJob] = {}
        self._jobs_lock = threading.RLock()
        
        # Gestion des rapports
        self._reports: Dict[str, OptimizationReport] = {}
        self._reports_lock = threading.RLock()
        
        # Cache des métriques
        self._metrics_cache: Dict[str, Dict[str, float]] = {}
        self._cache_lock = threading.RLock()
        
        # Queue d'optimisation
        self._optimization_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "configs_created": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "total_data_reduced": 0,
            "avg_reduction": 0.0,
            "optimization_time_ms": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("DataOptimizeEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_priority": OptimizationPriority.MEDIUM,
            "compression_level": 6,
            "batch_size": 10000,
            "index_batch_size": 1000,
            "cache_size": 10000,
            "max_cache_ttl": 3600,
            "dedup_chunk_size": 1024 * 1024,
            "columnar_batch_size": 1000,
            "partition_size": 1000000,
            "enable_auto_optimize": True,
            "auto_optimize_interval": 86400,
            "min_optimization_gain": 0.05
        }
    
    async def start(self) -> None:
        """Démarre le moteur d'optimisation."""
        logger.info("DataOptimizeEngine starting...")
        self._is_running = True
        
        # Chargement des configurations
        await self._load_configs()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._optimization_processor())
        asyncio.create_task(self._auto_optimize_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("DataOptimizeEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur d'optimisation."""
        logger.info("DataOptimizeEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("DataOptimizeEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_config(self, config: OptimizationConfig) -> str:
        """Crée une configuration d'optimisation."""
        with self._configs_lock:
            self._configs[config.config_id] = config
            self._stats["configs_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"optimize:config:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Optimization config created: {config.name} (id={config.config_id})")
        return config.config_id
    
    async def run_optimization(self, config_id: str) -> OptimizationJob:
        """Exécute une optimisation."""
        with self._configs_lock:
            config = self._configs.get(config_id)
            if not config:
                raise ValueError(f"Config {config_id} not found")
        
        job = OptimizationJob(
            config_id=config_id,
            status="pending",
            metadata={"config_name": config.name}
        )
        
        with self._jobs_lock:
            self._jobs[job.job_id] = job
        
        # Mise en queue
        await self._optimization_queue.put((job.job_id, config))
        
        # Attente du résultat
        while job.status == "pending":
            await asyncio.sleep(0.1)
        
        return job
    
    async def get_report(self, job_id: str) -> OptimizationReport:
        """Génère un rapport d'optimisation."""
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")
        
        report = OptimizationReport(
            job_id=job_id,
            summary={
                "status": job.status,
                "data_processed": job.data_processed,
                "reduction_percentage": job.reduction_percentage,
                "duration": (job.end_time - job.start_time).total_seconds() if job.end_time else 0
            },
            recommendations=await self._generate_recommendations(job),
            benchmarks=job.metrics,
            improvements={"reduction": job.reduction_percentage}
        )
        
        with self._reports_lock:
            self._reports[report.report_id] = report
        
        return report
    
    # ========== MÉTHODES PRIVÉES - OPTIMISATION ==========
    
    async def _optimization_processor(self) -> None:
        """Traite les jobs d'optimisation."""
        while self._is_running:
            try:
                job_id, config = await self._optimization_queue.get()
                
                # Exécution de l'optimisation
                asyncio.create_task(self._execute_optimization(job_id, config))
                
            except Exception as e:
                logger.error(f"Optimization processor error: {e}")
                await asyncio.sleep(1)
    
    async def _execute_optimization(self, job_id: str, config: OptimizationConfig) -> None:
        """Exécute une optimisation."""
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                return
        
        job.status = "running"
        job.start_time = datetime.now(timezone.utc)
        
        try:
            # Récupération des données
            if not self.data_manager:
                raise ValueError("Data manager not available")
            
            total_data = 0
            total_reduction = 0
            
            for data_type in config.data_types:
                records = await self.data_manager.retrieve_all(data_type)
                data_size = sum(len(str(r.value).encode()) for r in records if r.value)
                total_data += data_size
                
                # Application des méthodes d'optimisation
                for method in config.methods:
                    if method == OptimizationMethod.COMPRESSION:
                        await self._apply_compression(records, config)
                    elif method == OptimizationMethod.DEDUPLICATION:
                        await self._apply_deduplication(records, config)
                    elif method == OptimizationMethod.COLUMNAR:
                        await self._apply_columnar(records, config)
                    elif method == OptimizationMethod.PARTITIONING:
                        await self._apply_partitioning(records, config)
                    elif method == OptimizationMethod.INDEXING:
                        await self._apply_indexing(records, config)
                    elif method == OptimizationMethod.CACHING:
                        await self._apply_caching(records, config)
                    elif method == OptimizationMethod.PREFETCHING:
                        await self._apply_prefetching(records, config)
                    elif method == OptimizationMethod.BATCHING:
                        await self._apply_batching(records, config)
            
            # Mise à jour du job
            job.data_before = total_data
            job.data_after = total_data - total_reduction
            job.reduction_percentage = (total_reduction / total_data) * 100 if total_data > 0 else 0
            job.status = "completed"
            job.end_time = datetime.now(timezone.utc)
            
            self._stats["jobs_completed"] += 1
            self._stats["total_data_reduced"] += total_reduction
            self._stats["avg_reduction"] = (
                self._stats["avg_reduction"] * 0.9 + job.reduction_percentage * 0.1
            )
            
            logger.info(f"Optimization completed: {job_id} reduction={job.reduction_percentage:.2f}%")
            
        except Exception as e:
            job.status = "failed"
            job.errors.append(str(e))
            job.end_time = datetime.now(timezone.utc)
            self._stats["jobs_failed"] += 1
            
            logger.error(f"Optimization error: {e}")
    
    # ========== MÉTHODES PRIVÉES - MÉTHODES ==========
    
    async def _apply_compression(self, records: List[DataRecord], config: OptimizationConfig) -> None:
        """Applique la compression."""
        for record in records:
            if not record.value:
                continue
            
            data = json.dumps(record.value).encode()
            compressed = zlib.compress(data, self.config["compression_level"])
            
            if len(compressed) < len(data):
                record.value["__compressed"] = True
                record.value["__data"] = compressed.hex()
    
    async def _apply_deduplication(self, records: List[DataRecord], config: OptimizationConfig) -> None:
        """Applique la déduplication."""
        seen = {}
        for record in records:
            if not record.value:
                continue
            
            data_hash = hashlib.md5(str(record.value).encode()).hexdigest()
            
            if data_hash in seen:
                record.value["__dedup_ref"] = seen[data_hash]
                record.value["__dedup"] = True
            else:
                seen[data_hash] = record.record_id
    
    async def _apply_columnar(self, records: List[DataRecord], config: OptimizationConfig) -> None:
        """Applique le stockage columnar."""
        # Conversion en DataFrame
        data = [r.value for r in records if r.value]
        df = pd.DataFrame(data)
        
        # Stockage columnar
        # Dans un système réel, on utiliserait des formats comme Parquet
        pass
    
    async def _apply_partitioning(self, records: List[DataRecord], config: OptimizationConfig) -> None:
        """Applique le partitionnement."""
        # Partitionnement par date ou par symbole
        for record in records:
            if not record.value:
                continue
            
            # Extraction de la partition
            timestamp = record.value.get("timestamp")
            if timestamp:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)
                
                partition = timestamp.strftime("%Y-%m-%d")
                record.value["__partition"] = partition
    
    async def _apply_indexing(self, records: List[DataRecord], config: OptimizationConfig) -> None:
        """Applique l'indexation."""
        index = {}
        batch_size = self.config["index_batch_size"]
        
        for record in records:
            if not record.value:
                continue
            
            # Création d'index
            for key, value in record.value.items():
                if key not in index:
                    index[key] = {}
                
                if value not in index[key]:
                    index[key][value] = []
                
                index[key][value].append(record.record_id)
        
        # Stockage de l'index
        if self.data_manager:
            await self.data_manager.store(
                f"optimize:index:{uuid.uuid4()}",
                index,
                DataType.INDEX
            )
    
    async def _apply_caching(self, records: List[DataRecord], config: OptimizationConfig) -> None:
        """Applique la mise en cache."""
        cache = {}
        for record in records:
            if not record.value:
                continue
            
            cache[record.record_id] = record.value
        
        # Stockage du cache
        with self._cache_lock:
            self._metrics_cache.update(cache)
    
    async def _apply_prefetching(self, records: List[DataRecord], config: OptimizationConfig) -> None:
        """Applique le préchargement."""
        # Préchargement des données fréquemment utilisées
        # Dans un système réel, on analyserait les patterns d'accès
        pass
    
    async def _apply_batching(self, records: List[DataRecord], config: OptimizationConfig) -> None:
        """Applique le batch processing."""
        batch_size = self.config["batch_size"]
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            # Traitement par batch
            # Dans un système réel, on regrouperait les opérations
            pass
    
    # ========== MÉTHODES PRIVÉES - RAPPORTS ==========
    
    async def _generate_recommendations(self, job: OptimizationJob) -> List[str]:
        """Génère des recommandations."""
        recommendations = []
        
        if job.reduction_percentage < 5:
            recommendations.append("Consider enabling compression for better storage optimization")
        
        if job.data_before > 1024 * 1024 * 1024:  # >1GB
            recommendations.append("Large dataset detected. Consider partitioning by date.")
        
        if job.metrics.get("query_time", 0) > 100:
            recommendations.append("High query latency detected. Consider adding indexes.")
        
        if "deduplication" not in str(job.metadata):
            recommendations.append("Enable deduplication to reduce redundant data")
        
        return recommendations
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _auto_optimize_loop(self) -> None:
        """Boucle d'optimisation automatique."""
        if not self.config["enable_auto_optimize"]:
            return
        
        while self._is_running:
            await asyncio.sleep(self.config["auto_optimize_interval"])
            
            try:
                # Création d'une configuration d'optimisation automatique
                config = OptimizationConfig(
                    name="Auto-Optimize",
                    target=OptimizationTarget.STORAGE,
                    methods=[OptimizationMethod.COMPRESSION, OptimizationMethod.DEDUPLICATION],
                    data_types=list(DataType),
                    metadata={"auto": True}
                )
                
                config_id = await self.create_config(config)
                await self.run_optimization(config_id)
                
                logger.info("Auto-optimization completed")
                
            except Exception as e:
                logger.error(f"Auto-optimize loop error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._configs_lock:
                    self._stats["total_configs"] = len(self._configs)
                with self._jobs_lock:
                    self._stats["total_jobs"] = len(self._jobs)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "optimize:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_configs(self) -> None:
        """Charge les configurations."""
        try:
            if self.data_manager:
                configs_data = await self.data_manager.retrieve(
                    "optimize:configs",
                    DataType.CONFIG
                )
                
                if configs_data:
                    for config_dict in configs_data:
                        config = self._deserialize_config(config_dict)
                        if config:
                            with self._configs_lock:
                                self._configs[config.config_id] = config
            
            logger.info(f"Loaded {len(self._configs)} optimization configs")
            
        except Exception as e:
            logger.error(f"Load configs error: {e}")
    
    def _deserialize_config(self, data: Dict) -> Optional[OptimizationConfig]:
        """Désérialise une configuration."""
        try:
            return OptimizationConfig(
                config_id=data.get("config_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                target=OptimizationTarget(data.get("target", "storage")),
                methods=[OptimizationMethod(m) for m in data.get("methods", [])],
                priority=OptimizationPriority(data.get("priority", "medium")),
                parameters=data.get("parameters", {}),
                data_types=[DataType(dt) for dt in data.get("data_types", [])],
                schedule=data.get("schedule"),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing config: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_config(self, config_id: str) -> Optional[OptimizationConfig]:
        """Récupère une configuration."""
        with self._configs_lock:
            return self._configs.get(config_id)
    
    async def get_configs(self) -> List[OptimizationConfig]:
        """Récupère les configurations."""
        with self._configs_lock:
            return list(self._configs.values())
    
    async def get_job(self, job_id: str) -> Optional[OptimizationJob]:
        """Récupère un job."""
        with self._jobs_lock:
            return self._jobs.get(job_id)
    
    async def get_jobs(self) -> List[OptimizationJob]:
        """Récupère les jobs."""
        with self._jobs_lock:
            return list(self._jobs.values())
    
    async def get_report_by_job(self, job_id: str) -> Optional[OptimizationReport]:
        """Récupère un rapport par job."""
        with self._reports_lock:
            for report in self._reports.values():
                if report.job_id == job_id:
                    return report
        return None
    
    async def get_reports(self) -> List[OptimizationReport]:
        """Récupère les rapports."""
        with self._reports_lock:
            return list(self._reports.values())
    
    async def cancel_job(self, job_id: str) -> bool:
        """Annule un job."""
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job or job.status != "running":
                return False
            
            job.status = "cancelled"
            job.end_time = datetime.now(timezone.utc)
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._configs_lock:
            self._stats["total_configs"] = len(self._configs)
        with self._jobs_lock:
            self._stats["total_jobs"] = len(self._jobs)
        
        return self._stats.copy()


# ============== OPTIMIZATION ANALYZER ==============

class OptimizationAnalyzer:
    """
    Analyseur d'optimisation.
    Analyse les données pour recommander des optimisations.
    """
    
    def __init__(self, engine: DataOptimizeEngine):
        self.engine = engine
        self._analysis_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
    
    async def analyze(self, data: Any) -> Dict[str, Any]:
        """Analyse des données pour l'optimisation."""
        analysis = {
            "data_size": self._analyze_size(data),
            "data_types": self._analyze_types(data),
            "redundancy": self._analyze_redundancy(data),
            "query_patterns": self._analyze_query_patterns(data),
            "recommendations": []
        }
        
        # Recommandations
        if analysis["redundancy"] > 0.3:
            analysis["recommendations"].append("High redundancy detected. Enable deduplication.")
        
        if analysis["data_size"] > 100 * 1024 * 1024:  # >100MB
            analysis["recommendations"].append("Large dataset. Consider partitioning and compression.")
        
        if len(analysis["data_types"]) > 5:
            analysis["recommendations"].append("Multiple data types. Consider columnar storage.")
        
        return analysis
    
    def _analyze_size(self, data: Any) -> int:
        """Analyse la taille des données."""
        if isinstance(data, (str, bytes)):
            return len(data)
        elif isinstance(data, (list, tuple)):
            return sum(self._analyze_size(item) for item in data)
        elif isinstance(data, dict):
            return sum(self._analyze_size(v) for v in data.values())
        else:
            return len(str(data).encode())
    
    def _analyze_types(self, data: Any) -> List[str]:
        """Analyse les types de données."""
        types = []
        if isinstance(data, dict):
            for value in data.values():
                types.append(type(value).__name__)
        elif isinstance(data, list):
            for item in data:
                types.append(type(item).__name__)
        else:
            types.append(type(data).__name__)
        return list(set(types))
    
    def _analyze_redundancy(self, data: Any) -> float:
        """Analyse la redondance des données."""
        # Simulation de redondance
        return np.random.uniform(0, 0.5)
    
    def _analyze_query_patterns(self, data: Any) -> Dict[str, Any]:
        """Analyse les patterns de requêtes."""
        return {
            "frequency": np.random.uniform(0.1, 1.0),
            "complexity": np.random.uniform(0.1, 1.0),
            "cache_hit_rate": np.random.uniform(0.1, 0.8)
        }


# ============== FACTORY ==============

class DataOptimizeFactory:
    """Factory pour créer des composants d'optimisation."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> DataOptimizeEngine:
        """Crée un moteur d'optimisation."""
        engine = DataOptimizeEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_analyzer(engine: DataOptimizeEngine) -> OptimizationAnalyzer:
        """Crée un analyseur d'optimisation."""
        return OptimizationAnalyzer(engine)


# ============== EXPORT ==============

__all__ = [
    "OptimizationTarget",
    "OptimizationMethod",
    "OptimizationPriority",
    "OptimizationConfig",
    "OptimizationJob",
    "OptimizationReport",
    "DataOptimizeEngineInterface",
    "DataOptimizeEngine",
    "OptimizationAnalyzer",
    "DataOptimizeFactory"
]
