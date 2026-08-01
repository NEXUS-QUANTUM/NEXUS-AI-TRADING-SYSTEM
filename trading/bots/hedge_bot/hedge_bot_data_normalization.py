# trading/bots/hedge_bot/hedge_bot_data_normalization.py
# Advanced Data Normalization & Standardization Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Normalization Module - Module avancé de normalisation et standardisation des données
pour le Hedge Bot. Assure la normalisation des données, la standardisation, la transformation,
la mise à l'échelle et la préparation des données pour l'analyse et le machine learning.
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
from sklearn.preprocessing import (
    StandardScaler, MinMaxScaler, RobustScaler, MaxAbsScaler,
    Normalizer, QuantileTransformer, PowerTransformer, LabelEncoder,
    OneHotEncoder, OrdinalEncoder, KBinsDiscretizer
)
from scipy import stats
import hashlib

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_normalization")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class NormalizationMethod(Enum):
    """Méthodes de normalisation."""
    STANDARD = "standard"              # Standardization (Z-score)
    MINMAX = "minmax"                  # Min-Max scaling
    ROBUST = "robust"                  # Robust scaling (percentile-based)
    MAXABS = "maxabs"                  # Max absolute scaling
    UNIT_VECTOR = "unit_vector"        # Unit vector normalization
    QUANTILE = "quantile"              # Quantile transformation
    POWER = "power"                    # Power transformation (Box-Cox, Yeo-Johnson)
    LOG = "log"                        # Logarithmic transformation
    SQRT = "sqrt"                      # Square root transformation
    CUSTOM = "custom"                  # Custom transformation


class EncodingMethod(Enum):
    """Méthodes d'encodage."""
    LABEL = "label"                    # Label encoding
    ONE_HOT = "one_hot"                # One-hot encoding
    ORDINAL = "ordinal"                # Ordinal encoding
    FREQUENCY = "frequency"            # Frequency encoding
    TARGET = "target"                  # Target encoding
    BINARY = "binary"                  # Binary encoding
    HASH = "hash"                      # Hash encoding


class OutlierMethod(Enum):
    """Méthodes de détection des outliers."""
    ZSCORE = "zscore"                  # Z-score method
    IQR = "iqr"                        # Interquartile range
    MAD = "mad"                        # Median absolute deviation
    PERCENTILE = "percentile"          # Percentile-based
    ISOLATION_FOREST = "isolation_forest"  # Isolation Forest
    DBSCAN = "dbscan"                  # DBSCAN clustering


# ============== DATA MODELS ==============

@dataclass
class NormalizationConfig:
    """Configuration de normalisation."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    method: NormalizationMethod = NormalizationMethod.STANDARD
    columns: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    fit_parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True


@dataclass
class EncodingConfig:
    """Configuration d'encodage."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    method: EncodingMethod = EncodingMethod.ONE_HOT
    columns: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    mapping: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True


@dataclass
class NormalizationResult:
    """Résultat de normalisation."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config_id: str = ""
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    transformed_data: pd.DataFrame = field(default_factory=pd.DataFrame)
    scaler: Optional[Any] = None
    encoder: Optional[Any] = None
    statistics: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class NormalizationEngineInterface(ABC):
    """Interface abstraite pour le moteur de normalisation."""
    
    @abstractmethod
    async def normalize(self, data: pd.DataFrame, config: NormalizationConfig) -> NormalizationResult:
        """Normalise des données."""
        pass
    
    @abstractmethod
    async def encode(self, data: pd.DataFrame, config: EncodingConfig) -> pd.DataFrame:
        """Encode des données catégorielles."""
        pass
    
    @abstractmethod
    async def detect_outliers(self, data: pd.DataFrame, method: OutlierMethod) -> Dict[str, Any]:
        """Détecte les outliers."""
        pass


# ============== IMPLÉMENTATION ==============

class NormalizationEngine(NormalizationEngineInterface):
    """
    Moteur de normalisation avancé pour le Hedge Bot.
    Gère la normalisation, l'encodage et la détection d'outliers.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des configurations
        self._norm_configs: Dict[str, NormalizationConfig] = {}
        self._norm_lock = threading.RLock()
        
        # Gestion des encodages
        self._encode_configs: Dict[str, EncodingConfig] = {}
        self._encode_lock = threading.RLock()
        
        # Cache des scalers
        self._scaler_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "normalizations_performed": 0,
            "encodings_performed": 0,
            "outlier_detections": 0,
            "avg_normalization_time_ms": 0.0,
            "avg_encoding_time_ms": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("NormalizationEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_normalization": NormalizationMethod.STANDARD,
            "default_encoding": EncodingMethod.ONE_HOT,
            "default_outlier": OutlierMethod.ZSCORE,
            "cache_size": 100,
            "cache_ttl": 3600,
            "enable_cache": True,
            "outlier_threshold": 3.0,
            "iqr_multiplier": 1.5,
            "quantile_range": (25, 75),
            "zscore_threshold": 3.0,
            "mad_threshold": 3.5,
            "isolation_forest_contamination": 0.1
        }
    
    async def start(self) -> None:
        """Démarre le moteur de normalisation."""
        logger.info("NormalizationEngine starting...")
        self._is_running = True
        
        # Chargement des configurations
        await self._load_configs()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("NormalizationEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de normalisation."""
        logger.info("NormalizationEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("NormalizationEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def normalize(self, data: pd.DataFrame, config: NormalizationConfig) -> NormalizationResult:
        """Normalise des données."""
        start_time = time.time()
        self._stats["normalizations_performed"] += 1
        
        try:
            # Sélection des colonnes
            columns = config.columns or data.select_dtypes(include=[np.number]).columns.tolist()
            
            # Récupération du scaler du cache
            scaler_key = self._compute_cache_key(config, columns)
            scaler = None
            
            if self.config["enable_cache"]:
                with self._cache_lock:
                    if scaler_key in self._scaler_cache:
                        scaler = self._scaler_cache[scaler_key]
            
            # Création du scaler si nécessaire
            if scaler is None:
                scaler = self._create_scaler(config.method, config.parameters)
                
                # Fit du scaler
                if hasattr(scaler, "fit"):
                    scaler.fit(data[columns])
                
                # Mise en cache
                if self.config["enable_cache"]:
                    with self._cache_lock:
                        if len(self._scaler_cache) < self.config["cache_size"]:
                            self._scaler_cache[scaler_key] = scaler
            
            # Transformation
            transformed = data.copy()
            transformed[columns] = scaler.transform(data[columns])
            
            # Statistiques
            statistics = self._calculate_statistics(data[columns], transformed[columns])
            
            # Création du résultat
            result = NormalizationResult(
                config_id=config.config_id,
                data=data,
                transformed_data=transformed,
                scaler=scaler,
                statistics=statistics,
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
            # Mise à jour des statistiques
            self._stats["avg_normalization_time_ms"] = (
                self._stats["avg_normalization_time_ms"] * 0.9 + result.execution_time_ms * 0.1
            )
            
            logger.info(f"Normalization completed: {config.name} "
                       f"columns={len(columns)} time={result.execution_time_ms:.2f}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"Normalization error: {e}")
            raise
    
    async def encode(self, data: pd.DataFrame, config: EncodingConfig) -> pd.DataFrame:
        """Encode des données catégorielles."""
        start_time = time.time()
        self._stats["encodings_performed"] += 1
        
        try:
            # Sélection des colonnes
            columns = config.columns or data.select_dtypes(include=["object", "category"]).columns.tolist()
            
            if not columns:
                return data
            
            # Encodage selon la méthode
            if config.method == EncodingMethod.LABEL:
                transformed = await self._label_encode(data, columns, config)
            elif config.method == EncodingMethod.ONE_HOT:
                transformed = await self._one_hot_encode(data, columns, config)
            elif config.method == EncodingMethod.ORDINAL:
                transformed = await self._ordinal_encode(data, columns, config)
            elif config.method == EncodingMethod.FREQUENCY:
                transformed = await self._frequency_encode(data, columns, config)
            elif config.method == EncodingMethod.TARGET:
                transformed = await self._target_encode(data, columns, config)
            elif config.method == EncodingMethod.BINARY:
                transformed = await self._binary_encode(data, columns, config)
            elif config.method == EncodingMethod.HASH:
                transformed = await self._hash_encode(data, columns, config)
            else:
                transformed = data
            
            # Mise à jour des statistiques
            encoding_time = (time.time() - start_time) * 1000
            self._stats["avg_encoding_time_ms"] = (
                self._stats["avg_encoding_time_ms"] * 0.9 + encoding_time * 0.1
            )
            
            logger.info(f"Encoding completed: {config.name} "
                       f"columns={len(columns)} method={config.method.value}")
            
            return transformed
            
        except Exception as e:
            logger.error(f"Encoding error: {e}")
            raise
    
    async def detect_outliers(self, data: pd.DataFrame, method: OutlierMethod) -> Dict[str, Any]:
        """Détecte les outliers."""
        start_time = time.time()
        self._stats["outlier_detections"] += 1
        
        try:
            # Sélection des colonnes numériques
            numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
            
            if not numeric_cols:
                return {"outliers": {}, "message": "No numeric columns found"}
            
            results = {}
            total_outliers = 0
            
            for col in numeric_cols:
                values = data[col].dropna().values
                
                if len(values) < 2:
                    continue
                
                # Détection selon la méthode
                if method == OutlierMethod.ZSCORE:
                    outliers = self._detect_zscore_outliers(values)
                elif method == OutlierMethod.IQR:
                    outliers = self._detect_iqr_outliers(values)
                elif method == OutlierMethod.MAD:
                    outliers = self._detect_mad_outliers(values)
                elif method == OutlierMethod.PERCENTILE:
                    outliers = self._detect_percentile_outliers(values)
                else:
                    outliers = self._detect_zscore_outliers(values)
                
                results[col] = {
                    "count": len(outliers),
                    "indices": outliers.tolist(),
                    "percentage": (len(outliers) / len(values)) * 100
                }
                total_outliers += len(outliers)
            
            execution_time = (time.time() - start_time) * 1000
            
            return {
                "results": results,
                "total_outliers": total_outliers,
                "execution_time_ms": execution_time,
                "method": method.value
            }
            
        except Exception as e:
            logger.error(f"Outlier detection error: {e}")
            raise
    
    # ========== MÉTHODES PRIVÉES - NORMALISATION ==========
    
    def _create_scaler(self, method: NormalizationMethod, params: Dict[str, Any]) -> Any:
        """Crée un scaler selon la méthode."""
        if method == NormalizationMethod.STANDARD:
            return StandardScaler(**params)
        elif method == NormalizationMethod.MINMAX:
            return MinMaxScaler(**params)
        elif method == NormalizationMethod.ROBUST:
            return RobustScaler(**params)
        elif method == NormalizationMethod.MAXABS:
            return MaxAbsScaler(**params)
        elif method == NormalizationMethod.UNIT_VECTOR:
            return Normalizer(**params)
        elif method == NormalizationMethod.QUANTILE:
            return QuantileTransformer(**params)
        elif method == NormalizationMethod.POWER:
            return PowerTransformer(**params)
        else:
            return StandardScaler()
    
    def _calculate_statistics(self, original: pd.DataFrame, transformed: pd.DataFrame) -> Dict[str, Any]:
        """Calcule les statistiques de normalisation."""
        stats = {
            "original": {},
            "transformed": {}
        }
        
        for col in original.columns:
            stats["original"][col] = {
                "mean": original[col].mean(),
                "std": original[col].std(),
                "min": original[col].min(),
                "max": original[col].max(),
                "q25": original[col].quantile(0.25),
                "q75": original[col].quantile(0.75),
                "skew": original[col].skew(),
                "kurtosis": original[col].kurtosis()
            }
            
            stats["transformed"][col] = {
                "mean": transformed[col].mean(),
                "std": transformed[col].std(),
                "min": transformed[col].min(),
                "max": transformed[col].max(),
                "q25": transformed[col].quantile(0.25),
                "q75": transformed[col].quantile(0.75)
            }
        
        return stats
    
    # ========== MÉTHODES PRIVÉES - ENCODAGE ==========
    
    async def _label_encode(self, data: pd.DataFrame, columns: List[str], config: EncodingConfig) -> pd.DataFrame:
        """Label encoding."""
        result = data.copy()
        
        for col in columns:
            if col in config.mapping:
                result[col] = data[col].map(config.mapping[col])
            else:
                le = LabelEncoder()
                result[col] = le.fit_transform(data[col].astype(str))
                config.mapping[col] = dict(zip(le.classes_, le.transform(le.classes_)))
        
        return result
    
    async def _one_hot_encode(self, data: pd.DataFrame, columns: List[str], config: EncodingConfig) -> pd.DataFrame:
        """One-hot encoding."""
        result = data.copy()
        
        for col in columns:
            # Vérification du nombre de catégories
            n_categories = data[col].nunique()
            if n_categories > 100:
                logger.warning(f"Column {col} has {n_categories} categories, one-hot may create too many columns")
            
            dummy_cols = pd.get_dummies(data[col], prefix=col)
            result = pd.concat([result, dummy_cols], axis=1)
            result.drop(columns=[col], inplace=True)
        
        return result
    
    async def _ordinal_encode(self, data: pd.DataFrame, columns: List[str], config: EncodingConfig) -> pd.DataFrame:
        """Ordinal encoding."""
        result = data.copy()
        
        for col in columns:
            if col in config.mapping:
                result[col] = data[col].map(config.mapping[col])
            else:
                oe = OrdinalEncoder()
                result[col] = oe.fit_transform(data[[col]]).flatten()
                config.mapping[col] = dict(zip(oe.categories_[0], range(len(oe.categories_[0]))))
        
        return result
    
    async def _frequency_encode(self, data: pd.DataFrame, columns: List[str], config: EncodingConfig) -> pd.DataFrame:
        """Frequency encoding."""
        result = data.copy()
        
        for col in columns:
            freq = data[col].value_counts(normalize=True)
            result[col + "_freq"] = data[col].map(freq)
            result.drop(columns=[col], inplace=True)
        
        return result
    
    async def _target_encode(self, data: pd.DataFrame, columns: List[str], config: EncodingConfig) -> pd.DataFrame:
        """Target encoding."""
        result = data.copy()
        target = config.parameters.get("target")
        
        if not target or target not in data.columns:
            logger.warning("Target column not found for target encoding")
            return result
        
        for col in columns:
            target_mean = data.groupby(col)[target].mean()
            result[col + "_target"] = data[col].map(target_mean)
            result.drop(columns=[col], inplace=True)
        
        return result
    
    async def _binary_encode(self, data: pd.DataFrame, columns: List[str], config: EncodingConfig) -> pd.DataFrame:
        """Binary encoding."""
        result = data.copy()
        
        for col in columns:
            unique_values = data[col].unique()
            n_unique = len(unique_values)
            n_bits = int(np.ceil(np.log2(n_unique)))
            
            value_to_binary = {val: bin(i)[2:].zfill(n_bits) for i, val in enumerate(unique_values)}
            
            for i in range(n_bits):
                result[f"{col}_bit_{i}"] = data[col].map(lambda x: int(value_to_binary[x][i]) if x in value_to_binary else 0)
            
            result.drop(columns=[col], inplace=True)
        
        return result
    
    async def _hash_encode(self, data: pd.DataFrame, columns: List[str], config: EncodingConfig) -> pd.DataFrame:
        """Hash encoding."""
        result = data.copy()
        n_components = config.parameters.get("n_components", 8)
        
        for col in columns:
            for i in range(n_components):
                result[f"{col}_hash_{i}"] = data[col].apply(
                    lambda x: int(hashlib.md5(f"{x}_{i}".encode()).hexdigest(), 16) % 2
                )
            result.drop(columns=[col], inplace=True)
        
        return result
    
    # ========== MÉTHODES PRIVÉES - OUTLIERS ==========
    
    def _detect_zscore_outliers(self, values: np.ndarray) -> np.ndarray:
        """Détection par Z-score."""
        z_scores = np.abs(stats.zscore(values))
        threshold = self.config["zscore_threshold"]
        return np.where(z_scores > threshold)[0]
    
    def _detect_iqr_outliers(self, values: np.ndarray) -> np.ndarray:
        """Détection par IQR."""
        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1
        multiplier = self.config["iqr_multiplier"]
        lower_bound = q1 - multiplier * iqr
        upper_bound = q3 + multiplier * iqr
        return np.where((values < lower_bound) | (values > upper_bound))[0]
    
    def _detect_mad_outliers(self, values: np.ndarray) -> np.ndarray:
        """Détection par MAD."""
        median = np.median(values)
        mad = np.median(np.abs(values - median))
        threshold = self.config["mad_threshold"]
        modified_z_scores = 0.6745 * (values - median) / mad
        return np.where(np.abs(modified_z_scores) > threshold)[0]
    
    def _detect_percentile_outliers(self, values: np.ndarray) -> np.ndarray:
        """Détection par percentile."""
        lower = np.percentile(values, 5)
        upper = np.percentile(values, 95)
        return np.where((values < lower) | (values > upper))[0]
    
    # ========== MÉTHODES PRIVÉES - CACHE ==========
    
    def _compute_cache_key(self, config: NormalizationConfig, columns: List[str]) -> str:
        """Calcule une clé de cache."""
        key_data = {
            "method": config.method.value,
            "columns": sorted(columns),
            "params": config.parameters
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._scaler_cache) > self.config["cache_size"]:
                        keys = list(self._scaler_cache.keys())
                        for key in keys[:len(self._scaler_cache) - self.config["cache_size"]]:
                            del self._scaler_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._norm_lock:
                    self._stats["total_norm_configs"] = len(self._norm_configs)
                with self._encode_lock:
                    self._stats["total_encode_configs"] = len(self._encode_configs)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "normalization:metrics",
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
                norm_data = await self.data_manager.retrieve(
                    "normalization:configs",
                    DataType.CONFIG
                )
                
                if norm_data:
                    for config_dict in norm_data:
                        config = self._deserialize_norm_config(config_dict)
                        if config:
                            with self._norm_lock:
                                self._norm_configs[config.config_id] = config
                
                encode_data = await self.data_manager.retrieve(
                    "encoding:configs",
                    DataType.CONFIG
                )
                
                if encode_data:
                    for config_dict in encode_data:
                        config = self._deserialize_encode_config(config_dict)
                        if config:
                            with self._encode_lock:
                                self._encode_configs[config.config_id] = config
            
            logger.info(f"Loaded {len(self._norm_configs)} normalization configs "
                       f"and {len(self._encode_configs)} encoding configs")
            
        except Exception as e:
            logger.error(f"Load configs error: {e}")
    
    def _deserialize_norm_config(self, data: Dict) -> Optional[NormalizationConfig]:
        """Désérialise une configuration de normalisation."""
        try:
            return NormalizationConfig(
                config_id=data.get("config_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                method=NormalizationMethod(data.get("method", "standard")),
                columns=data.get("columns", []),
                parameters=data.get("parameters", {}),
                fit_parameters=data.get("fit_parameters", {}),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                active=data.get("active", True)
            )
        except Exception as e:
            logger.error(f"Error deserializing norm config: {e}")
            return None
    
    def _deserialize_encode_config(self, data: Dict) -> Optional[EncodingConfig]:
        """Désérialise une configuration d'encodage."""
        try:
            return EncodingConfig(
                config_id=data.get("config_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                method=EncodingMethod(data.get("method", "one_hot")),
                columns=data.get("columns", []),
                parameters=data.get("parameters", {}),
                mapping=data.get("mapping", {}),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True)
            )
        except Exception as e:
            logger.error(f"Error deserializing encode config: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def create_norm_config(self, config: NormalizationConfig) -> str:
        """Crée une configuration de normalisation."""
        with self._norm_lock:
            self._norm_configs[config.config_id] = config
        
        if self.data_manager:
            await self.data_manager.store(
                f"normalization:config:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Normalization config created: {config.name}")
        return config.config_id
    
    async def get_norm_config(self, config_id: str) -> Optional[NormalizationConfig]:
        """Récupère une configuration de normalisation."""
        with self._norm_lock:
            return self._norm_configs.get(config_id)
    
    async def create_encode_config(self, config: EncodingConfig) -> str:
        """Crée une configuration d'encodage."""
        with self._encode_lock:
            self._encode_configs[config.config_id] = config
        
        if self.data_manager:
            await self.data_manager.store(
                f"encoding:config:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Encoding config created: {config.name}")
        return config.config_id
    
    async def get_encode_config(self, config_id: str) -> Optional[EncodingConfig]:
        """Récupère une configuration d'encodage."""
        with self._encode_lock:
            return self._encode_configs.get(config_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._norm_lock:
            self._stats["norm_configs"] = len(self._norm_configs)
        with self._encode_lock:
            self._stats["encode_configs"] = len(self._encode_configs)
        
        return self._stats.copy()


# ============== FACTORY ==============

class NormalizationFactory:
    """Factory pour créer des composants de normalisation."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> NormalizationEngine:
        """Crée un moteur de normalisation."""
        engine = NormalizationEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "NormalizationMethod",
    "EncodingMethod",
    "OutlierMethod",
    "NormalizationConfig",
    "EncodingConfig",
    "NormalizationResult",
    "NormalizationEngineInterface",
    "NormalizationEngine",
    "NormalizationFactory"
]
