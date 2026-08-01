# trading/bots/hedge_bot/hedge_bot_data_profiling.py
# Advanced Data Profiling & Quality Assessment Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Profiling Module - Module avancé de profilage des données et d'évaluation de la qualité
pour le Hedge Bot. Analyse la qualité des données, détecte les anomalies, profile les distributions,
et génère des rapports de qualité pour les données de hedging.
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
from scipy import stats
from sklearn.preprocessing import StandardScaler

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_profiling")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class ProfileType(Enum):
    """Types de profils."""
    DATA_QUALITY = "data_quality"
    STATISTICAL = "statistical"
    PATTERN = "pattern"
    ANOMALY = "anomaly"
    DISTRIBUTION = "distribution"
    CORRELATION = "correlation"
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"


class QualityMetric(Enum):
    """Métriques de qualité."""
    COMPLETENESS = "completeness"
    UNIQUENESS = "uniqueness"
    VALIDITY = "validity"
    ACCURACY = "accuracy"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    RELEVANCE = "relevance"
    INTEGRITY = "integrity"


class AnomalySeverity(Enum):
    """Sévérité des anomalies."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============== DATA MODELS ==============

@dataclass
class DataProfile:
    """Profil de données."""
    profile_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data_type: DataType = DataType.MARKET
    profile_type: ProfileType = ProfileType.STATISTICAL
    name: str = ""
    description: str = ""
    statistics: Dict[str, Any] = field(default_factory=dict)
    distributions: Dict[str, Any] = field(default_factory=dict)
    patterns: Dict[str, Any] = field(default_factory=dict)
    quality_scores: Dict[str, float] = field(default_factory=dict)
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    row_count: int = 0
    column_count: int = 0
    size_bytes: int = 0


@dataclass
class QualityReport:
    """Rapport de qualité."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    profile_id: str = ""
    overall_score: float = 0.0
    metric_scores: Dict[str, float] = field(default_factory=dict)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    severity_summary: Dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnomalyDetection:
    """Détection d'anomalie."""
    anomaly_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data_type: DataType = DataType.MARKET
    field: str = ""
    value: Any = None
    expected: Any = None
    deviation: float = 0.0
    severity: AnomalySeverity = AnomalySeverity.MEDIUM
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False


# ============== INTERFACES ==============

class ProfilingEngineInterface(ABC):
    """Interface abstraite pour le moteur de profilage."""
    
    @abstractmethod
    async def profile_data(self, data: pd.DataFrame, data_type: DataType) -> DataProfile:
        """Profile des données."""
        pass
    
    @abstractmethod
    async def assess_quality(self, profile: DataProfile) -> QualityReport:
        """Évalue la qualité des données."""
        pass
    
    @abstractmethod
    async def detect_anomalies(self, data: pd.DataFrame) -> List[AnomalyDetection]:
        """Détecte des anomalies."""
        pass


# ============== IMPLÉMENTATION ==============

class ProfilingEngine(ProfilingEngineInterface):
    """
    Moteur de profilage avancé pour le Hedge Bot.
    Analyse la qualité des données et détecte les anomalies.
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
        
        # Gestion des profils
        self._profiles: Dict[str, DataProfile] = {}
        self._profiles_lock = threading.RLock()
        
        # Gestion des rapports
        self._reports: Dict[str, QualityReport] = {}
        self._reports_lock = threading.RLock()
        
        # Gestion des anomalies
        self._anomalies: Dict[str, AnomalyDetection] = {}
        self._anomalies_lock = threading.RLock()
        
        # Cache des statistiques
        self._stats_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._global_stats: Dict[str, Any] = {
            "profiles_created": 0,
            "quality_reports": 0,
            "anomalies_detected": 0,
            "anomalies_resolved": 0,
            "avg_quality_score": 0.0,
            "critical_anomalies": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("ProfilingEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "quality_threshold": 0.8,
            "anomaly_threshold": 3.0,
            "profile_batch_size": 10000,
            "cache_size": 100,
            "cache_ttl": 3600,
            "enable_caching": True,
            "auto_profile": True,
            "auto_quality_check": True,
            "anomaly_detection_interval": 3600,
            "max_profile_size": 100000,
            "min_data_points": 10
        }
    
    async def start(self) -> None:
        """Démarre le moteur de profilage."""
        logger.info("ProfilingEngine starting...")
        self._is_running = True
        
        # Chargement des profils
        await self._load_profiles()
        
        # Chargement des rapports
        await self._load_reports()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._anomaly_detection_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("ProfilingEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de profilage."""
        logger.info("ProfilingEngine stopping...")
        self._is_running = False
        
        # Sauvegarde des profils
        await self._save_profiles()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("ProfilingEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def profile_data(self, data: pd.DataFrame, data_type: DataType) -> DataProfile:
        """Profile des données."""
        self._global_stats["profiles_created"] += 1
        
        try:
            # Validation des données
            if data.empty:
                raise ValueError("Empty data provided")
            
            # Statistiques de base
            statistics = await self._calculate_statistics(data)
            distributions = await self._calculate_distributions(data)
            patterns = await self._detect_patterns(data)
            
            # Création du profil
            profile = DataProfile(
                data_type=data_type,
                profile_type=ProfileType.STATISTICAL,
                name=f"Profile_{data_type.value}_{int(time.time())}",
                statistics=statistics,
                distributions=distributions,
                patterns=patterns,
                row_count=len(data),
                column_count=len(data.columns),
                size_bytes=data.memory_usage(deep=True).sum(),
                metadata={"source": "profiling_engine"}
            )
            
            # Évaluation de la qualité
            quality_scores = await self._calculate_quality_scores(data)
            profile.quality_scores = quality_scores
            
            # Détection d'anomalies
            anomalies = await self._detect_anomalies_in_data(data)
            profile.anomalies = anomalies
            
            # Stockage du profil
            with self._profiles_lock:
                self._profiles[profile.profile_id] = profile
            
            # Stockage persistant
            if self.data_manager:
                await self.data_manager.store(
                    f"profile:{profile.profile_id}",
                    profile.to_dict(),
                    DataType.PROFILE
                )
            
            logger.info(f"Data profile created: {profile.name} rows={profile.row_count}")
            return profile
            
        except Exception as e:
            logger.error(f"Profiling error: {e}")
            raise
    
    async def assess_quality(self, profile: DataProfile) -> QualityReport:
        """Évalue la qualité des données."""
        self._global_stats["quality_reports"] += 1
        
        try:
            # Calcul des scores par métrique
            metric_scores = {}
            for metric in QualityMetric:
                score = await self._calculate_metric_score(profile, metric)
                metric_scores[metric.value] = score
            
            # Score global
            overall_score = np.mean(list(metric_scores.values()))
            
            # Identification des problèmes
            issues = await self._identify_issues(profile, metric_scores)
            
            # Génération des recommandations
            recommendations = await self._generate_recommendations(issues)
            
            # Résumé des sévérités
            severity_summary = defaultdict(int)
            for issue in issues:
                severity_summary[issue.get("severity", "low")] += 1
            
            # Création du rapport
            report = QualityReport(
                profile_id=profile.profile_id,
                overall_score=overall_score,
                metric_scores=metric_scores,
                issues=issues,
                recommendations=recommendations,
                severity_summary=dict(severity_summary),
                metadata={"profile_name": profile.name}
            )
            
            with self._reports_lock:
                self._reports[report.report_id] = report
            
            # Mise à jour des statistiques
            self._global_stats["avg_quality_score"] = (
                self._global_stats["avg_quality_score"] * 0.9 + overall_score * 0.1
            )
            
            logger.info(f"Quality report generated: {report.report_id} score={overall_score:.2f}")
            return report
            
        except Exception as e:
            logger.error(f"Quality assessment error: {e}")
            raise
    
    async def detect_anomalies(self, data: pd.DataFrame) -> List[AnomalyDetection]:
        """Détecte des anomalies."""
        self._global_stats["anomalies_detected"] += 1
        
        try:
            anomalies = await self._detect_anomalies_in_data(data)
            
            for anomaly in anomalies:
                with self._anomalies_lock:
                    self._anomalies[anomaly.anomaly_id] = anomaly
                    
                    if anomaly.severity == AnomalySeverity.CRITICAL:
                        self._global_stats["critical_anomalies"] += 1
            
            logger.info(f"Anomaly detection completed: {len(anomalies)} anomalies found")
            return anomalies
            
        except Exception as e:
            logger.error(f"Anomaly detection error: {e}")
            return []
    
    # ========== MÉTHODES PRIVÉES - CALCULS ==========
    
    async def _calculate_statistics(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Calcule les statistiques des données."""
        stats = {}
        
        for col in data.columns:
            if data[col].dtype in [np.float64, np.int64]:
                stats[col] = {
                    "count": data[col].count(),
                    "mean": data[col].mean(),
                    "std": data[col].std(),
                    "min": data[col].min(),
                    "max": data[col].max(),
                    "median": data[col].median(),
                    "q25": data[col].quantile(0.25),
                    "q75": data[col].quantile(0.75),
                    "skew": data[col].skew(),
                    "kurtosis": data[col].kurtosis(),
                    "missing": data[col].isnull().sum(),
                    "unique": data[col].nunique()
                }
            else:
                stats[col] = {
                    "count": data[col].count(),
                    "unique": data[col].nunique(),
                    "mode": data[col].mode().iloc[0] if not data[col].mode().empty else None,
                    "missing": data[col].isnull().sum(),
                    "dtype": str(data[col].dtype)
                }
        
        return stats
    
    async def _calculate_distributions(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Calcule les distributions des données."""
        distributions = {}
        
        for col in data.columns:
            if data[col].dtype in [np.float64, np.int64]:
                # Histogramme
                hist, bins = np.histogram(data[col].dropna(), bins=10)
                distributions[col] = {
                    "histogram": hist.tolist(),
                    "bins": bins.tolist(),
                    "min": data[col].min(),
                    "max": data[col].max()
                }
        
        return distributions
    
    async def _detect_patterns(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Détecte les patterns dans les données."""
        patterns = {}
        
        for col in data.columns:
            if data[col].dtype == "object":
                # Patterns de texte
                unique_values = data[col].value_counts()
                patterns[col] = {
                    "most_frequent": unique_values.head(5).to_dict(),
                    "unique_count": len(unique_values)
                }
            elif data[col].dtype in [np.float64, np.int64]:
                # Patterns numériques
                patterns[col] = {
                    "is_constant": data[col].std() == 0,
                    "is_integer": (data[col] == data[col].round()).all(),
                    "range": data[col].max() - data[col].min()
                }
        
        return patterns
    
    async def _calculate_quality_scores(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calcule les scores de qualité."""
        scores = {}
        
        # Complétude
        completeness = 1 - data.isnull().sum().sum() / (data.shape[0] * data.shape[1])
        scores["completeness"] = completeness
        
        # Unicité
        unique_ratio = data.nunique().sum() / (data.shape[0] * data.shape[1])
        scores["uniqueness"] = unique_ratio
        
        # Validité (simulée)
        scores["validity"] = 0.9
        
        # Consistance (simulée)
        scores["consistency"] = 0.85
        
        return scores
    
    async def _calculate_metric_score(self, profile: DataProfile, metric: QualityMetric) -> float:
        """Calcule le score d'une métrique de qualité."""
        if metric == QualityMetric.COMPLETENESS:
            return profile.quality_scores.get("completeness", 0.8)
        elif metric == QualityMetric.UNIQUENESS:
            return profile.quality_scores.get("uniqueness", 0.7)
        elif metric == QualityMetric.VALIDITY:
            return profile.quality_scores.get("validity", 0.9)
        elif metric == QualityMetric.CONSISTENCY:
            return profile.quality_scores.get("consistency", 0.85)
        else:
            return 0.8
    
    # ========== MÉTHODES PRIVÉES - ANOMALIES ==========
    
    async def _detect_anomalies_in_data(self, data: pd.DataFrame) -> List[AnomalyDetection]:
        """Détecte les anomalies dans les données."""
        anomalies = []
        threshold = self.config["anomaly_threshold"]
        
        for col in data.columns:
            if data[col].dtype in [np.float64, np.int64]:
                values = data[col].dropna()
                if len(values) < self.config["min_data_points"]:
                    continue
                
                mean = values.mean()
                std = values.std()
                
                for idx, value in values.items():
                    if std > 0:
                        z_score = abs((value - mean) / std)
                        if z_score > threshold:
                            severity = self._determine_severity(z_score)
                            anomaly = AnomalyDetection(
                                data_type=DataType.MARKET,
                                field=col,
                                value=value,
                                expected=mean,
                                deviation=z_score,
                                severity=severity,
                                context={"index": idx, "z_score": z_score}
                            )
                            anomalies.append(anomaly)
        
        return anomalies
    
    def _determine_severity(self, z_score: float) -> AnomalySeverity:
        """Détermine la sévérité d'une anomalie."""
        if z_score > 5.0:
            return AnomalySeverity.CRITICAL
        elif z_score > 4.0:
            return AnomalySeverity.HIGH
        elif z_score > 3.0:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW
    
    async def _identify_issues(self, profile: DataProfile, metric_scores: Dict[str, float]) -> List[Dict[str, Any]]:
        """Identifie les problèmes de qualité."""
        issues = []
        
        for metric, score in metric_scores.items():
            if score < self.config["quality_threshold"]:
                issues.append({
                    "metric": metric,
                    "score": score,
                    "threshold": self.config["quality_threshold"],
                    "severity": "high" if score < 0.5 else "medium",
                    "description": f"Low {metric} score: {score:.2f}"
                })
        
        # Problèmes d'anomalies
        for anomaly in profile.anomalies:
            issues.append({
                "metric": "anomaly",
                "value": anomaly["value"],
                "expected": anomaly["expected"],
                "severity": anomaly["severity"],
                "field": anomaly["field"],
                "description": f"Anomaly detected in {anomaly['field']}: {anomaly['value']}"
            })
        
        return issues
    
    async def _generate_recommendations(self, issues: List[Dict[str, Any]]) -> List[str]:
        """Génère des recommandations."""
        recommendations = []
        
        for issue in issues:
            if issue.get("metric") == "completeness":
                recommendations.append("Improve data completeness by handling missing values")
            elif issue.get("metric") == "uniqueness":
                recommendations.append("Check for duplicate records and improve uniqueness")
            elif issue.get("metric") == "validity":
                recommendations.append("Validate data against business rules and constraints")
            elif issue.get("metric") == "anomaly":
                recommendations.append(f"Investigate anomaly in {issue.get('field')}")
        
        if not recommendations:
            recommendations.append("Data quality is satisfactory. Continue monitoring.")
        
        return recommendations
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _anomaly_detection_loop(self) -> None:
        """Boucle de détection d'anomalies."""
        while self._is_running:
            await asyncio.sleep(self.config["anomaly_detection_interval"])
            
            try:
                # Récupération des données récentes
                if self.data_manager:
                    for data_type in DataType:
                        data = await self.data_manager.retrieve_all(data_type)
                        if data:
                            # Conversion en DataFrame
                            df = pd.DataFrame([r.value for r in data if r.value])
                            if not df.empty:
                                await self.detect_anomalies(df)
                
            except Exception as e:
                logger.error(f"Anomaly detection loop error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._stats_cache) > self.config["cache_size"]:
                        keys = list(self._stats_cache.keys())
                        for key in keys[:len(self._stats_cache) - self.config["cache_size"]]:
                            del self._stats_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._profiles_lock:
                    self._global_stats["total_profiles"] = len(self._profiles)
                with self._reports_lock:
                    self._global_stats["total_reports"] = len(self._reports)
                with self._anomalies_lock:
                    self._global_stats["total_anomalies"] = len(self._anomalies)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "profiling:metrics",
                        self._global_stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_profiles(self) -> None:
        """Charge les profils existants."""
        try:
            if self.data_manager:
                profiles_data = await self.data_manager.retrieve(
                    "profiles:all",
                    DataType.PROFILE
                )
                
                if profiles_data:
                    for p_dict in profiles_data:
                        profile = self._deserialize_profile(p_dict)
                        if profile:
                            with self._profiles_lock:
                                self._profiles[profile.profile_id] = profile
            
            logger.info(f"Loaded {len(self._profiles)} profiles")
            
        except Exception as e:
            logger.error(f"Load profiles error: {e}")
    
    async def _load_reports(self) -> None:
        """Charge les rapports existants."""
        try:
            if self.data_manager:
                reports_data = await self.data_manager.retrieve(
                    "profiling:reports",
                    DataType.REPORT
                )
                
                if reports_data:
                    for r_dict in reports_data:
                        report = self._deserialize_report(r_dict)
                        if report:
                            with self._reports_lock:
                                self._reports[report.report_id] = report
            
            logger.info(f"Loaded {len(self._reports)} quality reports")
            
        except Exception as e:
            logger.error(f"Load reports error: {e}")
    
    async def _save_profiles(self) -> None:
        """Sauvegarde les profils."""
        try:
            if self.data_manager:
                with self._profiles_lock:
                    for profile in self._profiles.values():
                        await self.data_manager.store(
                            f"profile:{profile.profile_id}",
                            profile.to_dict(),
                            DataType.PROFILE
                        )
            
            logger.info("Profiles saved")
            
        except Exception as e:
            logger.error(f"Save profiles error: {e}")
    
    def _deserialize_profile(self, data: Dict) -> Optional[DataProfile]:
        """Désérialise un profil."""
        try:
            return DataProfile(
                profile_id=data.get("profile_id", str(uuid.uuid4())),
                data_type=DataType(data.get("data_type", "market")),
                profile_type=ProfileType(data.get("profile_type", "statistical")),
                name=data.get("name", ""),
                description=data.get("description", ""),
                statistics=data.get("statistics", {}),
                distributions=data.get("distributions", {}),
                patterns=data.get("patterns", {}),
                quality_scores=data.get("quality_scores", {}),
                anomalies=data.get("anomalies", []),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                row_count=data.get("row_count", 0),
                column_count=data.get("column_count", 0),
                size_bytes=data.get("size_bytes", 0)
            )
        except Exception as e:
            logger.error(f"Error deserializing profile: {e}")
            return None
    
    def _deserialize_report(self, data: Dict) -> Optional[QualityReport]:
        """Désérialise un rapport."""
        try:
            return QualityReport(
                report_id=data.get("report_id", str(uuid.uuid4())),
                profile_id=data.get("profile_id", ""),
                overall_score=data.get("overall_score", 0.0),
                metric_scores=data.get("metric_scores", {}),
                issues=data.get("issues", []),
                recommendations=data.get("recommendations", []),
                severity_summary=data.get("severity_summary", {}),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                metadata=data.get("metadata", {})
            )
        except Exception as e:
            logger.error(f"Error deserializing report: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_profile(self, profile_id: str) -> Optional[DataProfile]:
        """Récupère un profil."""
        with self._profiles_lock:
            return self._profiles.get(profile_id)
    
    async def get_profiles(self) -> List[DataProfile]:
        """Récupère les profils."""
        with self._profiles_lock:
            return list(self._profiles.values())
    
    async def get_report(self, report_id: str) -> Optional[QualityReport]:
        """Récupère un rapport."""
        with self._reports_lock:
            return self._reports.get(report_id)
    
    async def get_reports(self) -> List[QualityReport]:
        """Récupère les rapports."""
        with self._reports_lock:
            return list(self._reports.values())
    
    async def get_anomaly(self, anomaly_id: str) -> Optional[AnomalyDetection]:
        """Récupère une anomalie."""
        with self._anomalies_lock:
            return self._anomalies.get(anomaly_id)
    
    async def get_anomalies(self, resolved: bool = False) -> List[AnomalyDetection]:
        """Récupère les anomalies."""
        with self._anomalies_lock:
            anomalies = list(self._anomalies.values())
            if not resolved:
                anomalies = [a for a in anomalies if not a.resolved]
            return sorted(anomalies, key=lambda a: a.timestamp, reverse=True)
    
    async def resolve_anomaly(self, anomaly_id: str, note: str = "") -> bool:
        """Résout une anomalie."""
        with self._anomalies_lock:
            anomaly = self._anomalies.get(anomaly_id)
            if not anomaly or anomaly.resolved:
                return False
            
            anomaly.resolved = True
            anomaly.metadata["resolution_note"] = note
            self._global_stats["anomalies_resolved"] += 1
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._profiles_lock:
            self._global_stats["total_profiles"] = len(self._profiles)
        with self._reports_lock:
            self._global_stats["total_reports"] = len(self._reports)
        with self._anomalies_lock:
            self._global_stats["total_anomalies"] = len(self._anomalies)
        
        return self._global_stats.copy()


# ============== PROFILE VISUALIZER ==============

class ProfileVisualizer:
    """
    Visualiseur de profils.
    Génère des visualisations pour les profils de données.
    """
    
    def __init__(self, engine: ProfilingEngine):
        self.engine = engine
    
    async def generate_profile_report(self, profile_id: str) -> Dict[str, Any]:
        """Génère un rapport visuel pour un profil."""
        profile = await self.engine.get_profile(profile_id)
        if not profile:
            return {"error": "Profile not found"}
        
        # Création du rapport
        report = {
            "profile_id": profile.profile_id,
            "name": profile.name,
            "timestamp": profile.timestamp.isoformat(),
            "statistics": profile.statistics,
            "quality_scores": profile.quality_scores,
            "anomalies": profile.anomalies,
            "summary": {
                "total_rows": profile.row_count,
                "total_columns": profile.column_count,
                "size_mb": profile.size_bytes / (1024 * 1024),
                "completeness": profile.quality_scores.get("completeness", 0),
                "uniqueness": profile.quality_scores.get("uniqueness", 0)
            }
        }
        
        return report


# ============== FACTORY ==============

class ProfilingFactory:
    """Factory pour créer des composants de profilage."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ProfilingEngine:
        """Crée un moteur de profilage."""
        engine = ProfilingEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_visualizer(engine: ProfilingEngine) -> ProfileVisualizer:
        """Crée un visualiseur de profils."""
        return ProfileVisualizer(engine)


# ============== EXPORT ==============

__all__ = [
    "ProfileType",
    "QualityMetric",
    "AnomalySeverity",
    "DataProfile",
    "QualityReport",
    "AnomalyDetection",
    "ProfilingEngineInterface",
    "ProfilingEngine",
    "ProfileVisualizer",
    "ProfilingFactory"
]
