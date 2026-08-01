# trading/bots/hedge_bot/hedge_bot_data_outlier.py
# Advanced Outlier Detection & Anomaly Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Outlier Module - Module avancé de détection d'outliers et de gestion des anomalies
pour le Hedge Bot. Détecte les valeurs aberrantes, les anomalies de marché, les pics de volatilité,
les erreurs de données et les comportements anormaux dans les données de hedging.
"""

import asyncio
import json
import math
import time
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
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM
import warnings
warnings.filterwarnings('ignore')

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_outlier")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)


# ============== ENUMS & TYPES ==============

class OutlierMethod(Enum):
    """Méthodes de détection d'outliers."""
    ZSCORE = "zscore"                  # Méthode du Z-score
    IQR = "iqr"                        # Interquartile Range
    MAD = "mad"                        # Median Absolute Deviation
    PERCENTILE = "percentile"          # Méthode des percentiles
    ISOLATION_FOREST = "isolation_forest"  # Isolation Forest
    LOF = "lof"                        # Local Outlier Factor
    ONE_CLASS_SVM = "one_class_svm"    # One-Class SVM
    DBSCAN = "dbscan"                  # DBSCAN clustering
    AUTOENCODER = "autoencoder"        # Autoencoder
    GRUBBS = "grubbs"                  # Test de Grubbs
    CHAUVENET = "chauvenet"            # Critère de Chauvenet


class OutlierSeverity(Enum):
    """Sévérité des outliers."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OutlierType(Enum):
    """Types d'outliers."""
    POINT = "point"                    # Outlier ponctuel
    CONTEXTUAL = "contextual"          # Outlier contextuel
    COLLECTIVE = "collective"          # Outlier collectif
    SEASONAL = "seasonal"              # Outlier saisonnier
    TREND = "trend"                    # Outlier de tendance


# ============== DATA MODELS ==============

@dataclass
class OutlierDetection:
    """Détection d'outlier."""
    detection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    method: OutlierMethod = OutlierMethod.ZSCORE
    data_type: DataType = DataType.MARKET
    symbol: str = ""
    field: str = ""
    value: float = 0.0
    expected: float = 0.0
    deviation: float = 0.0
    z_score: float = 0.0
    severity: OutlierSeverity = OutlierSeverity.MEDIUM
    outlier_type: OutlierType = OutlierType.POINT
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    resolved: bool = False
    resolution_note: Optional[str] = None
    resolved_at: Optional[datetime] = None


@dataclass
class OutlierConfig:
    """Configuration de détection d'outliers."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    method: OutlierMethod = OutlierMethod.ZSCORE
    threshold: float = 3.0
    window: int = 100
    sensitivity: float = 0.5
    data_types: List[DataType] = field(default_factory=list)
    fields: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    auto_resolve: bool = False
    notify: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OutlierStats:
    """Statistiques d'outliers."""
    stats_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_detections: int = 0
    resolved_detections: int = 0
    unresolved_detections: int = 0
    severity_counts: Dict[str, int] = field(default_factory=dict)
    method_counts: Dict[str, int] = field(default_factory=dict)
    type_counts: Dict[str, int] = field(default_factory=dict)
    avg_deviation: float = 0.0
    max_deviation: float = 0.0
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=30))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class OutlierEngineInterface(ABC):
    """Interface abstraite pour le moteur d'outliers."""
    
    @abstractmethod
    async def detect(self, data: Any, config: OutlierConfig) -> List[OutlierDetection]:
        """Détecte les outliers."""
        pass
    
    @abstractmethod
    async def create_config(self, config: OutlierConfig) -> str:
        """Crée une configuration de détection."""
        pass
    
    @abstractmethod
    async def get_detections(self, config_id: str) -> List[OutlierDetection]:
        """Récupère les détections d'une configuration."""
        pass


# ============== IMPLÉMENTATION ==============

class OutlierEngine(OutlierEngineInterface):
    """
    Moteur de détection d'outliers avancé pour le Hedge Bot.
    Détecte les anomalies et les valeurs aberrantes dans les données.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des détections
        self._detections: Dict[str, List[OutlierDetection]] = defaultdict(list)
        self._detections_lock = threading.RLock()
        
        # Gestion des configurations
        self._configs: Dict[str, OutlierConfig] = {}
        self._configs_lock = threading.RLock()
        
        # Gestion des statistiques
        self._stats: Dict[str, OutlierStats] = {}
        self._stats_lock = threading.RLock()
        
        # Modèles ML
        self._models: Dict[str, Any] = {}
        self._models_lock = threading.RLock()
        
        # Statistiques
        self._global_stats: Dict[str, Any] = {
            "total_detections": 0,
            "resolved_detections": 0,
            "unresolved_detections": 0,
            "high_severity": 0,
            "critical_severity": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("OutlierEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_method": OutlierMethod.ZSCORE,
            "default_threshold": 3.0,
            "default_window": 100,
            "default_sensitivity": 0.5,
            "auto_resolve": False,
            "notify": True,
            "batch_size": 1000,
            "enable_ml": True,
            "ml_training_interval": 86400,
            "retention_days": 30,
            "max_detections": 10000,
            "zscore_threshold": 3.0,
            "iqr_multiplier": 1.5,
            "mad_threshold": 3.5,
            "isolation_forest_contamination": 0.1,
            "lof_neighbors": 20,
            "one_class_svm_nu": 0.1
        }
    
    async def start(self) -> None:
        """Démarre le moteur d'outliers."""
        logger.info("OutlierEngine starting...")
        self._is_running = True
        
        # Chargement des configurations
        await self._load_configs()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cleanup_loop())
        asyncio.create_task(self._metrics_collector())
        asyncio.create_task(self._ml_training_loop())
        
        logger.info("OutlierEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur d'outliers."""
        logger.info("OutlierEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("OutlierEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def detect(self, data: Any, config: OutlierConfig) -> List[OutlierDetection]:
        """Détecte les outliers."""
        detections = []
        
        try:
            # Préparation des données
            processed_data = await self._prepare_data(data, config)
            
            if not processed_data:
                return detections
            
            # Sélection de la méthode
            if config.method == OutlierMethod.ZSCORE:
                detections = await self._detect_zscore(processed_data, config)
            elif config.method == OutlierMethod.IQR:
                detections = await self._detect_iqr(processed_data, config)
            elif config.method == OutlierMethod.MAD:
                detections = await self._detect_mad(processed_data, config)
            elif config.method == OutlierMethod.PERCENTILE:
                detections = await self._detect_percentile(processed_data, config)
            elif config.method == OutlierMethod.ISOLATION_FOREST:
                detections = await self._detect_isolation_forest(processed_data, config)
            elif config.method == OutlierMethod.LOF:
                detections = await self._detect_lof(processed_data, config)
            elif config.method == OutlierMethod.ONE_CLASS_SVM:
                detections = await self._detect_one_class_svm(processed_data, config)
            else:
                detections = await self._detect_zscore(processed_data, config)
            
            # Enregistrement des détections
            with self._detections_lock:
                self._detections[config.config_id].extend(detections)
                self._global_stats["total_detections"] += len(detections)
            
            # Mise à jour des statistiques
            await self._update_stats(config, detections)
            
            logger.info(f"Outlier detection completed: {len(detections)} outliers found")
            return detections
            
        except Exception as e:
            logger.error(f"Outlier detection error: {e}")
            return detections
    
    async def create_config(self, config: OutlierConfig) -> str:
        """Crée une configuration de détection."""
        with self._configs_lock:
            self._configs[config.config_id] = config
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"outlier:config:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Outlier config created: {config.name}")
        return config.config_id
    
    async def get_detections(self, config_id: str) -> List[OutlierDetection]:
        """Récupère les détections d'une configuration."""
        with self._detections_lock:
            return self._detections.get(config_id, [])
    
    # ========== MÉTHODES PRIVÉES - DÉTECTION ==========
    
    async def _prepare_data(self, data: Any, config: OutlierConfig) -> pd.DataFrame:
        """Prépare les données pour la détection."""
        if isinstance(data, pd.DataFrame):
            return data
        
        if isinstance(data, (list, dict)):
            return pd.DataFrame(data)
        
        if isinstance(data, (int, float)):
            return pd.DataFrame({"value": [data]})
        
        return pd.DataFrame()
    
    async def _detect_zscore(self, data: pd.DataFrame, config: OutlierConfig) -> List[OutlierDetection]:
        """Détection par Z-score."""
        detections = []
        threshold = config.threshold or self.config["zscore_threshold"]
        
        for col in data.select_dtypes(include=[np.number]).columns:
            values = data[col].dropna().values
            if len(values) < 2:
                continue
            
            mean = np.mean(values)
            std = np.std(values)
            
            for idx, value in enumerate(values):
                if std > 0:
                    z_score = abs((value - mean) / std)
                    if z_score > threshold:
                        detection = OutlierDetection(
                            method=OutlierMethod.ZSCORE,
                            field=col,
                            value=value,
                            expected=mean,
                            deviation=value - mean,
                            z_score=z_score,
                            severity=self._determine_severity(z_score),
                            outlier_type=OutlierType.POINT,
                            context={"index": idx, "mean": mean, "std": std}
                        )
                        detections.append(detection)
        
        return detections
    
    async def _detect_iqr(self, data: pd.DataFrame, config: OutlierConfig) -> List[OutlierDetection]:
        """Détection par IQR."""
        detections = []
        multiplier = config.sensitivity * 3 or self.config["iqr_multiplier"]
        
        for col in data.select_dtypes(include=[np.number]).columns:
            values = data[col].dropna().values
            if len(values) < 4:
                continue
            
            q1 = np.percentile(values, 25)
            q3 = np.percentile(values, 75)
            iqr = q3 - q1
            lower_bound = q1 - multiplier * iqr
            upper_bound = q3 + multiplier * iqr
            
            for idx, value in enumerate(values):
                if value < lower_bound or value > upper_bound:
                    detection = OutlierDetection(
                        method=OutlierMethod.IQR,
                        field=col,
                        value=value,
                        expected=(q1 + q3) / 2,
                        deviation=value - (q1 + q3) / 2,
                        z_score=0,
                        severity=OutlierSeverity.MEDIUM,
                        outlier_type=OutlierType.POINT,
                        context={"index": idx, "q1": q1, "q3": q3, "iqr": iqr}
                    )
                    detections.append(detection)
        
        return detections
    
    async def _detect_mad(self, data: pd.DataFrame, config: OutlierConfig) -> List[OutlierDetection]:
        """Détection par MAD."""
        detections = []
        threshold = config.threshold or self.config["mad_threshold"]
        
        for col in data.select_dtypes(include=[np.number]).columns:
            values = data[col].dropna().values
            if len(values) < 2:
                continue
            
            median = np.median(values)
            mad = np.median(np.abs(values - median))
            
            for idx, value in enumerate(values):
                if mad > 0:
                    mad_score = abs((value - median) / mad)
                    if mad_score > threshold:
                        detection = OutlierDetection(
                            method=OutlierMethod.MAD,
                            field=col,
                            value=value,
                            expected=median,
                            deviation=value - median,
                            z_score=0,
                            severity=self._determine_severity(mad_score),
                            outlier_type=OutlierType.POINT,
                            context={"index": idx, "median": median, "mad": mad}
                        )
                        detections.append(detection)
        
        return detections
    
    async def _detect_percentile(self, data: pd.DataFrame, config: OutlierConfig) -> List[OutlierDetection]:
        """Détection par percentile."""
        detections = []
        lower_pct = config.sensitivity * 5
        upper_pct = 100 - lower_pct
        
        for col in data.select_dtypes(include=[np.number]).columns:
            values = data[col].dropna().values
            if len(values) < 10:
                continue
            
            lower_bound = np.percentile(values, lower_pct)
            upper_bound = np.percentile(values, upper_pct)
            
            for idx, value in enumerate(values):
                if value < lower_bound or value > upper_bound:
                    detection = OutlierDetection(
                        method=OutlierMethod.PERCENTILE,
                        field=col,
                        value=value,
                        expected=np.percentile(values, 50),
                        deviation=value - np.percentile(values, 50),
                        z_score=0,
                        severity=OutlierSeverity.MEDIUM,
                        outlier_type=OutlierType.POINT,
                        context={"index": idx, "lower_pct": lower_pct, "upper_pct": upper_pct}
                    )
                    detections.append(detection)
        
        return detections
    
    async def _detect_isolation_forest(self, data: pd.DataFrame, config: OutlierConfig) -> List[OutlierDetection]:
        """Détection par Isolation Forest."""
        detections = []
        contamination = config.sensitivity * 0.2 or self.config["isolation_forest_contamination"]
        
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            return detections
        
        X = data[numeric_cols].dropna().values
        
        if len(X) < 10:
            return detections
        
        # Entraînement du modèle
        model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        predictions = model.fit_predict(X)
        scores = model.score_samples(X)
        
        for idx, (pred, score) in enumerate(zip(predictions, scores)):
            if pred == -1:
                detection = OutlierDetection(
                    method=OutlierMethod.ISOLATION_FOREST,
                    field="multi",
                    value=score,
                    expected=0,
                    deviation=score,
                    z_score=0,
                    severity=self._determine_severity(abs(score)),
                    outlier_type=OutlierType.COLLECTIVE,
                    context={"index": idx, "score": score, "prediction": pred}
                )
                detections.append(detection)
        
        return detections
    
    async def _detect_lof(self, data: pd.DataFrame, config: OutlierConfig) -> List[OutlierDetection]:
        """Détection par Local Outlier Factor."""
        detections = []
        n_neighbors = config.sensitivity * 40 or self.config["lof_neighbors"]
        
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            return detections
        
        X = data[numeric_cols].dropna().values
        
        if len(X) < n_neighbors:
            return detections
        
        # Détection LOF
        model = LocalOutlierFactor(
            n_neighbors=n_neighbors,
            contamination=config.sensitivity * 0.2
        )
        predictions = model.fit_predict(X)
        
        for idx, pred in enumerate(predictions):
            if pred == -1:
                detection = OutlierDetection(
                    method=OutlierMethod.LOF,
                    field="multi",
                    value=0,
                    expected=0,
                    deviation=0,
                    z_score=0,
                    severity=OutlierSeverity.MEDIUM,
                    outlier_type=OutlierType.CONTEXTUAL,
                    context={"index": idx, "prediction": pred}
                )
                detections.append(detection)
        
        return detections
    
    async def _detect_one_class_svm(self, data: pd.DataFrame, config: OutlierConfig) -> List[OutlierDetection]:
        """Détection par One-Class SVM."""
        detections = []
        nu = config.sensitivity * 0.2 or self.config["one_class_svm_nu"]
        
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            return detections
        
        X = data[numeric_cols].dropna().values
        
        if len(X) < 10:
            return detections
        
        # Détection SVM
        model = OneClassSVM(nu=nu, kernel="rbf", gamma="auto")
        predictions = model.fit_predict(X)
        
        for idx, pred in enumerate(predictions):
            if pred == -1:
                detection = OutlierDetection(
                    method=OutlierMethod.ONE_CLASS_SVM,
                    field="multi",
                    value=0,
                    expected=0,
                    deviation=0,
                    z_score=0,
                    severity=OutlierSeverity.MEDIUM,
                    outlier_type=OutlierType.COLLECTIVE,
                    context={"index": idx, "prediction": pred}
                )
                detections.append(detection)
        
        return detections
    
    # ========== MÉTHODES PRIVÉES - UTILITAIRES ==========
    
    def _determine_severity(self, score: float) -> OutlierSeverity:
        """Détermine la sévérité d'un outlier."""
        if score > 5.0:
            return OutlierSeverity.CRITICAL
        elif score > 3.0:
            return OutlierSeverity.HIGH
        elif score > 2.0:
            return OutlierSeverity.MEDIUM
        else:
            return OutlierSeverity.LOW
    
    async def _update_stats(self, config: OutlierConfig, detections: List[OutlierDetection]) -> None:
        """Met à jour les statistiques."""
        with self._stats_lock:
            if config.config_id not in self._stats:
                self._stats[config.config_id] = OutlierStats()
            
            stats = self._stats[config.config_id]
            stats.total_detections += len(detections)
            
            for detection in detections:
                stats.severity_counts[detection.severity.value] = (
                    stats.severity_counts.get(detection.severity.value, 0) + 1
                )
                stats.method_counts[detection.method.value] = (
                    stats.method_counts.get(detection.method.value, 0) + 1
                )
                stats.type_counts[detection.outlier_type.value] = (
                    stats.type_counts.get(detection.outlier_type.value, 0) + 1
                )
                stats.avg_deviation = (
                    stats.avg_deviation * 0.9 + abs(detection.deviation) * 0.1
                )
                stats.max_deviation = max(stats.max_deviation, abs(detection.deviation))
            
            # Mise à jour des statistiques globales
            self._global_stats["resolved_detections"] = 0
            self._global_stats["unresolved_detections"] = 0
            self._global_stats["high_severity"] = 0
            self._global_stats["critical_severity"] = 0
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _cleanup_loop(self) -> None:
        """Nettoie les détections anciennes."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=self.config["retention_days"])
                
                with self._detections_lock:
                    for config_id in list(self._detections.keys()):
                        detections = self._detections[config_id]
                        kept = [d for d in detections if d.timestamp > cutoff]
                        
                        if len(kept) < len(detections):
                            self._detections[config_id] = kept
                            logger.debug(f"Cleaned up {len(detections) - len(kept)} old detections")
                
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._detections_lock:
                    total = sum(len(d) for d in self._detections.values())
                    self._global_stats["total_detections"] = total
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "outlier:metrics",
                        self._global_stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    async def _ml_training_loop(self) -> None:
        """Boucle d'entraînement des modèles ML."""
        if not self.config["enable_ml"]:
            return
        
        while self._is_running:
            await asyncio.sleep(self.config["ml_training_interval"])
            
            try:
                # Réentraînement des modèles
                # Dans un système réel, on réentraînerait les modèles ML
                logger.debug("ML models retrained")
                
            except Exception as e:
                logger.error(f"ML training error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_configs(self) -> None:
        """Charge les configurations existantes."""
        try:
            if self.data_manager:
                configs_data = await self.data_manager.retrieve(
                    "outlier:configs",
                    DataType.CONFIG
                )
                
                if configs_data:
                    for config_dict in configs_data:
                        config = self._deserialize_config(config_dict)
                        if config:
                            with self._configs_lock:
                                self._configs[config.config_id] = config
                            
                            # Chargement des détections
                            detections = await self.data_manager.retrieve(
                                f"outlier:detections:{config.config_id}",
                                DataType.DETECTION
                            )
                            if detections:
                                with self._detections_lock:
                                    self._detections[config.config_id] = detections
            
            logger.info(f"Loaded {len(self._configs)} outlier configs")
            
        except Exception as e:
            logger.error(f"Load configs error: {e}")
    
    def _deserialize_config(self, data: Dict) -> Optional[OutlierConfig]:
        """Désérialise une configuration."""
        try:
            return OutlierConfig(
                config_id=data.get("config_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                method=OutlierMethod(data.get("method", "zscore")),
                threshold=data.get("threshold", 3.0),
                window=data.get("window", 100),
                sensitivity=data.get("sensitivity", 0.5),
                data_types=[DataType(dt) for dt in data.get("data_types", [])],
                fields=data.get("fields", []),
                symbols=data.get("symbols", []),
                auto_resolve=data.get("auto_resolve", False),
                notify=data.get("notify", True),
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
    
    async def get_config(self, config_id: str) -> Optional[OutlierConfig]:
        """Récupère une configuration."""
        with self._configs_lock:
            return self._configs.get(config_id)
    
    async def get_configs(self) -> List[OutlierConfig]:
        """Récupère les configurations."""
        with self._configs_lock:
            return list(self._configs.values())
    
    async def resolve_detection(self, detection_id: str, note: str = "") -> bool:
        """Résout une détection."""
        with self._detections_lock:
            for config_id, detections in self._detections.items():
                for detection in detections:
                    if detection.detection_id == detection_id and not detection.resolved:
                        detection.resolved = True
                        detection.resolution_note = note
                        detection.resolved_at = datetime.now(timezone.utc)
                        self._global_stats["resolved_detections"] += 1
                        return True
        return False
    
    async def get_stats(self, config_id: str) -> Optional[OutlierStats]:
        """Récupère les statistiques d'une configuration."""
        with self._stats_lock:
            return self._stats.get(config_id)
    
    def get_global_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques globales."""
        return self._global_stats.copy()


# ============== OUTLIER DETECTION BUILDER ==============

class OutlierDetectionBuilder:
    """
    Constructeur de détection d'outliers.
    Facilite la création de configurations de détection.
    """
    
    def __init__(self):
        self._config = OutlierConfig()
    
    def name(self, name: str) -> 'OutlierDetectionBuilder':
        """Définit le nom."""
        self._config.name = name
        return self
    
    def method(self, method: OutlierMethod) -> 'OutlierDetectionBuilder':
        """Définit la méthode."""
        self._config.method = method
        return self
    
    def threshold(self, threshold: float) -> 'OutlierDetectionBuilder':
        """Définit le seuil."""
        self._config.threshold = threshold
        return self
    
    def sensitivity(self, sensitivity: float) -> 'OutlierDetectionBuilder':
        """Définit la sensibilité."""
        self._config.sensitivity = sensitivity
        return self
    
    def data_types(self, data_types: List[DataType]) -> 'OutlierDetectionBuilder':
        """Définit les types de données."""
        self._config.data_types = data_types
        return self
    
    def fields(self, fields: List[str]) -> 'OutlierDetectionBuilder':
        """Définit les champs."""
        self._config.fields = fields
        return self
    
    def symbols(self, symbols: List[str]) -> 'OutlierDetectionBuilder':
        """Définit les symboles."""
        self._config.symbols = symbols
        return self
    
    def auto_resolve(self, auto_resolve: bool) -> 'OutlierDetectionBuilder':
        """Définit l'auto-résolution."""
        self._config.auto_resolve = auto_resolve
        return self
    
    def build(self) -> OutlierConfig:
        """Construit la configuration."""
        return self._config


# ============== FACTORY ==============

class OutlierFactory:
    """Factory pour créer des composants d'outliers."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> OutlierEngine:
        """Crée un moteur d'outliers."""
        engine = OutlierEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_builder() -> OutlierDetectionBuilder:
        """Crée un constructeur de détection."""
        return OutlierDetectionBuilder()


# ============== EXPORT ==============

__all__ = [
    "OutlierMethod",
    "OutlierSeverity",
    "OutlierType",
    "OutlierDetection",
    "OutlierConfig",
    "OutlierStats",
    "OutlierEngineInterface",
    "OutlierEngine",
    "OutlierDetectionBuilder",
    "OutlierFactory"
]
