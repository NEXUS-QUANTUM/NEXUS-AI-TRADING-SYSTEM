# trading/bots/hedge_bot/hedge_bot_data_imputation.py
# Advanced Data Imputation & Missing Value Handling Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Imputation Module - Module avancé d'imputation de données et de gestion des valeurs manquantes
pour le Hedge Bot. Implémente des techniques d'imputation avancées, la détection des valeurs manquantes,
la correction des données et la préservation de l'intégrité des séries temporelles.
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
from scipy import interpolate
from scipy.stats import norm
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_imputation")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class ImputationMethod(Enum):
    """Méthodes d'imputation."""
    # Méthodes simples
    MEAN = "mean"
    MEDIAN = "median"
    MODE = "mode"
    CONSTANT = "constant"
    ZERO = "zero"
    
    # Méthodes de remplissage
    FORWARD_FILL = "forward_fill"
    BACKWARD_FILL = "backward_fill"
    INTERPOLATION = "interpolation"
    
    # Méthodes statistiques
    LINEAR_REGRESSION = "linear_regression"
    RANDOM_FOREST = "random_forest"
    KNN = "knn"
    MICE = "mice"
    
    # Méthodes avancées
    SPLINE = "spline"
    POLYNOMIAL = "polynomial"
    SEASONAL = "seasonal"
    ARIMA = "arima"
    DEEP_LEARNING = "deep_learning"
    GAN = "gan"
    
    # Méthodes spécialisées
    LAST_OBSERVATION = "last_observation"
    NEXT_OBSERVATION = "next_observation"
    LINEAR_TREND = "linear_trend"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"


class ImputationStrategy(Enum):
    """Stratégies d'imputation."""
    SIMPLE = "simple"
    SEQUENTIAL = "sequential"
    MULTIVARIATE = "multivariate"
    TEMPORAL = "temporal"
    HYBRID = "hybrid"
    ENSEMBLE = "ensemble"


class MissingPattern(Enum):
    """Patterns de valeurs manquantes."""
    MCAR = "mcar"  # Missing Completely At Random
    MAR = "mar"    # Missing At Random
    MNAR = "mnar"  # Missing Not At Random
    CLUSTERED = "clustered"
    SEASONAL = "seasonal"
    RANDOM = "random"
    STRUCTURAL = "structural"


# ============== DATA MODELS ==============

@dataclass
class ImputationConfig:
    """Configuration d'imputation."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    method: ImputationMethod = ImputationMethod.MEAN
    strategy: ImputationStrategy = ImputationStrategy.SIMPLE
    parameters: Dict[str, Any] = field(default_factory=dict)
    columns: List[str] = field(default_factory=list)
    threshold: float = 0.5  # Seuil de valeurs manquantes acceptables
    max_missing_pct: float = 0.3  # Pourcentage max de valeurs manquantes
    preserve_trend: bool = True
    preserve_seasonality: bool = True
    seed: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "config_id": self.config_id,
            "name": self.name,
            "method": self.method.value,
            "strategy": self.strategy.value,
            "parameters": self.parameters,
            "columns": self.columns,
            "threshold": self.threshold,
            "max_missing_pct": self.max_missing_pct,
            "preserve_trend": self.preserve_trend,
            "preserve_seasonality": self.preserve_seasonality,
            "seed": self.seed,
            "metadata": self.metadata,
            "tags": self.tags,
            "active": self.active
        }


@dataclass
class ImputationResult:
    """Résultat d'imputation."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config_id: str = ""
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    missing_values_filled: int = 0
    missing_values_detected: int = 0
    columns_processed: List[str] = field(default_factory=list)
    method_used: ImputationMethod = ImputationMethod.MEAN
    execution_time_ms: float = 0.0
    accuracy_score: float = 0.0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "result_id": self.result_id,
            "config_id": self.config_id,
            "missing_values_filled": self.missing_values_filled,
            "missing_values_detected": self.missing_values_detected,
            "columns_processed": self.columns_processed,
            "method_used": self.method_used.value,
            "execution_time_ms": self.execution_time_ms,
            "accuracy_score": self.accuracy_score,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags
        }


@dataclass
class MissingDataAnalysis:
    """Analyse des données manquantes."""
    analysis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_missing: int = 0
    missing_by_column: Dict[str, int] = field(default_factory=dict)
    missing_by_row: Dict[int, int] = field(default_factory=dict)
    missing_patterns: Dict[str, float] = field(default_factory=dict)
    pattern_type: MissingPattern = MissingPattern.RANDOM
    columns_affected: List[str] = field(default_factory=list)
    rows_affected: List[int] = field(default_factory=list)
    missing_percentage: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class ImputationEngineInterface(ABC):
    """Interface abstraite pour le moteur d'imputation."""
    
    @abstractmethod
    async def analyze_missing(self, data: pd.DataFrame) -> MissingDataAnalysis:
        """Analyse les valeurs manquantes."""
        pass
    
    @abstractmethod
    async def impute(self, data: pd.DataFrame, config: ImputationConfig) -> ImputationResult:
        """Impute les valeurs manquantes."""
        pass
    
    @abstractmethod
    async def get_config(self, config_id: str) -> Optional[ImputationConfig]:
        """Récupère une configuration."""
        pass


# ============== IMPLÉMENTATION ==============

class ImputationEngine(ImputationEngineInterface):
    """
    Moteur d'imputation avancé pour le Hedge Bot.
    Implémente des techniques d'imputation sophistiquées pour les données de hedging.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des configurations
        self._configs: Dict[str, ImputationConfig] = {}
        self._configs_lock = threading.RLock()
        
        # Gestion des résultats
        self._results: Dict[str, ImputationResult] = {}
        self._results_lock = threading.RLock()
        
        # Cache des analyses
        self._analysis_cache: Dict[str, MissingDataAnalysis] = {}
        self._cache_lock = threading.RLock()
        
        # Modèles d'imputation
        self._models: Dict[str, Any] = {}
        self._models_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "imputations_performed": 0,
            "missing_values_filled": 0,
            "avg_accuracy": 0.0,
            "errors": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("ImputationEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_method": ImputationMethod.INTERPOLATION,
            "default_strategy": ImputationStrategy.TEMPORAL,
            "default_threshold": 0.5,
            "default_max_missing_pct": 0.3,
            "cache_size": 100,
            "enable_cache": True,
            "parallel_imputation": True,
            "auto_detect_pattern": True,
            "validation_split": 0.2,
            "seed": 42
        }
    
    async def start(self) -> None:
        """Démarre le moteur d'imputation."""
        logger.info("ImputationEngine starting...")
        self._is_running = True
        
        # Chargement des configurations
        await self._load_configs()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("ImputationEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur d'imputation."""
        logger.info("ImputationEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("ImputationEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def analyze_missing(self, data: pd.DataFrame) -> MissingDataAnalysis:
        """Analyse les valeurs manquantes."""
        try:
            # Statistiques de base
            total_cells = data.shape[0] * data.shape[1]
            total_missing = data.isnull().sum().sum()
            missing_percentage = (total_missing / total_cells) * 100 if total_cells > 0 else 0
            
            # Par colonne
            missing_by_column = data.isnull().sum().to_dict()
            columns_affected = [col for col, count in missing_by_column.items() if count > 0]
            
            # Par ligne
            missing_by_row = data.isnull().sum(axis=1).to_dict()
            rows_affected = [idx for idx, count in missing_by_row.items() if count > 0]
            
            # Détection du pattern
            pattern_type = await self._detect_missing_pattern(data)
            
            # Recommandations
            recommendations = await self._generate_recommendations(data, pattern_type)
            
            # Création de l'analyse
            analysis = MissingDataAnalysis(
                total_missing=total_missing,
                missing_by_column=missing_by_column,
                missing_by_row=missing_by_row,
                missing_patterns={},
                pattern_type=pattern_type,
                columns_affected=columns_affected,
                rows_affected=list(rows_affected),
                missing_percentage=missing_percentage,
                recommendations=recommendations
            )
            
            # Cache
            with self._cache_lock:
                self._analysis_cache[analysis.analysis_id] = analysis
                if len(self._analysis_cache) > self.config["cache_size"]:
                    keys = list(self._analysis_cache.keys())
                    for key in keys[:len(self._analysis_cache) - self.config["cache_size"]]:
                        del self._analysis_cache[key]
            
            logger.info(f"Missing data analysis completed: {total_missing} missing values "
                       f"({missing_percentage:.2f}%) pattern={pattern_type.value}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            raise
    
    async def impute(self, data: pd.DataFrame, config: ImputationConfig) -> ImputationResult:
        """Impute les valeurs manquantes."""
        start_time = time.time()
        self._stats["imputations_performed"] += 1
        
        try:
            # Validation
            await self._validate_data(data, config)
            
            # Détection des valeurs manquantes
            missing_mask = data.isnull()
            missing_count = missing_mask.sum().sum()
            
            if missing_count == 0:
                return ImputationResult(
                    config_id=config.config_id,
                    data=data,
                    missing_values_detected=0,
                    missing_values_filled=0,
                    columns_processed=config.columns or list(data.columns),
                    method_used=config.method,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    accuracy_score=1.0
                )
            
            # Sélection des colonnes à traiter
            columns_to_impute = config.columns or list(data.columns)
            
            # Imputation selon la stratégie
            if config.strategy == ImputationStrategy.SIMPLE:
                imputed_data = await self._impute_simple(data, config, columns_to_impute)
            elif config.strategy == ImputationStrategy.SEQUENTIAL:
                imputed_data = await self._impute_sequential(data, config, columns_to_impute)
            elif config.strategy == ImputationStrategy.MULTIVARIATE:
                imputed_data = await self._impute_multivariate(data, config, columns_to_impute)
            elif config.strategy == ImputationStrategy.TEMPORAL:
                imputed_data = await self._impute_temporal(data, config, columns_to_impute)
            elif config.strategy == ImputationStrategy.HYBRID:
                imputed_data = await self._impute_hybrid(data, config, columns_to_impute)
            elif config.strategy == ImputationStrategy.ENSEMBLE:
                imputed_data = await self._impute_ensemble(data, config, columns_to_impute)
            else:
                raise ValueError(f"Unsupported strategy: {config.strategy}")
            
            # Calcul de l'exactitude (simulée)
            accuracy = await self._calculate_imputation_accuracy(data, imputed_data)
            
            # Création du résultat
            result = ImputationResult(
                config_id=config.config_id,
                data=imputed_data,
                missing_values_filled=missing_count,
                missing_values_detected=missing_count,
                columns_processed=columns_to_impute,
                method_used=config.method,
                execution_time_ms=(time.time() - start_time) * 1000,
                accuracy_score=accuracy,
                metadata={"config": config.to_dict()}
            )
            
            # Mise à jour des statistiques
            self._stats["missing_values_filled"] += missing_count
            self._stats["avg_accuracy"] = (
                self._stats["avg_accuracy"] * 0.9 + accuracy * 0.1
            )
            
            # Stockage du résultat
            with self._results_lock:
                self._results[result.result_id] = result
            
            logger.info(f"Imputation completed: {missing_count} values filled "
                       f"accuracy={accuracy:.2%} time={result.execution_time_ms:.2f}ms")
            
            return result
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Imputation error: {e}")
            raise
    
    async def get_config(self, config_id: str) -> Optional[ImputationConfig]:
        """Récupère une configuration."""
        with self._configs_lock:
            return self._configs.get(config_id)
    
    # ========== MÉTHODES PRIVÉES - IMPUTATION ==========
    
    async def _impute_simple(
        self,
        data: pd.DataFrame,
        config: ImputationConfig,
        columns: List[str]
    ) -> pd.DataFrame:
        """Imputation simple."""
        result = data.copy()
        
        for col in columns:
            if col in result.columns:
                if result[col].isnull().sum() == 0:
                    continue
                
                if config.method == ImputationMethod.MEAN:
                    result[col].fillna(result[col].mean(), inplace=True)
                elif config.method == ImputationMethod.MEDIAN:
                    result[col].fillna(result[col].median(), inplace=True)
                elif config.method == ImputationMethod.MODE:
                    result[col].fillna(result[col].mode()[0] if not result[col].mode().empty else 0, inplace=True)
                elif config.method == ImputationMethod.CONSTANT:
                    value = config.parameters.get("constant_value", 0)
                    result[col].fillna(value, inplace=True)
                elif config.method == ImputationMethod.ZERO:
                    result[col].fillna(0, inplace=True)
                else:
                    # Par défaut: moyenne
                    result[col].fillna(result[col].mean(), inplace=True)
        
        return result
    
    async def _impute_sequential(
        self,
        data: pd.DataFrame,
        config: ImputationConfig,
        columns: List[str]
    ) -> pd.DataFrame:
        """Imputation séquentielle."""
        result = data.copy()
        
        for col in columns:
            if col in result.columns:
                if result[col].isnull().sum() == 0:
                    continue
                
                if config.method in [ImputationMethod.FORWARD_FILL, ImputationMethod.LAST_OBSERVATION]:
                    result[col].fillna(method='ffill', inplace=True)
                    # Si des NaN persistent, utiliser backward fill
                    result[col].fillna(method='bfill', inplace=True)
                elif config.method in [ImputationMethod.BACKWARD_FILL, ImputationMethod.NEXT_OBSERVATION]:
                    result[col].fillna(method='bfill', inplace=True)
                    result[col].fillna(method='ffill', inplace=True)
                elif config.method == ImputationMethod.INTERPOLATION:
                    result[col].interpolate(method='linear', limit_direction='both', inplace=True)
                elif config.method == ImputationMethod.SPLINE:
                    result[col].interpolate(method='spline', order=3, limit_direction='both', inplace=True)
                elif config.method == ImputationMethod.POLYNOMIAL:
                    result[col].interpolate(method='polynomial', order=2, limit_direction='both', inplace=True)
                else:
                    # Par défaut: forward fill
                    result[col].fillna(method='ffill', inplace=True)
                    result[col].fillna(method='bfill', inplace=True)
        
        return result
    
    async def _impute_multivariate(
        self,
        data: pd.DataFrame,
        config: ImputationConfig,
        columns: List[str]
    ) -> pd.DataFrame:
        """Imputation multivariée."""
        result = data.copy()
        
        # Séparation des colonnes
        numeric_cols = result.select_dtypes(include=[np.number]).columns
        cols_to_impute = [c for c in columns if c in numeric_cols]
        
        for col in cols_to_impute:
            if result[col].isnull().sum() == 0:
                continue
            
            # Préparation des données
            missing_mask = result[col].isnull()
            train_data = result[~missing_mask]
            test_data = result[missing_mask]
            
            if len(train_data) < 10:
                # Pas assez de données pour l'apprentissage
                result[col].fillna(result[col].mean(), inplace=True)
                continue
            
            # Features pour la régression
            feature_cols = [c for c in numeric_cols if c != col and c in result.columns]
            if not feature_cols:
                result[col].fillna(result[col].mean(), inplace=True)
                continue
            
            X_train = train_data[feature_cols].values
            y_train = train_data[col].values
            X_test = test_data[feature_cols].values
            
            # Normalisation
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test) if len(X_test) > 0 else X_test
            
            # Modèle
            if config.method == ImputationMethod.LINEAR_REGRESSION:
                model = LinearRegression()
            elif config.method == ImputationMethod.RANDOM_FOREST:
                model = RandomForestRegressor(n_estimators=100, random_state=self.config["seed"])
            else:
                model = LinearRegression()
            
            model.fit(X_train_scaled, y_train)
            
            # Prédiction
            if len(X_test) > 0:
                predictions = model.predict(X_test_scaled)
                result.loc[missing_mask, col] = predictions
        
        return result
    
    async def _impute_temporal(
        self,
        data: pd.DataFrame,
        config: ImputationConfig,
        columns: List[str]
    ) -> pd.DataFrame:
        """Imputation temporelle."""
        result = data.copy()
        
        # Vérification de l'index temporel
        if not isinstance(result.index, pd.DatetimeIndex):
            try:
                # Tentative de conversion
                result.index = pd.to_datetime(result.index)
            except:
                logger.warning("Cannot convert index to datetime, using sequential imputation")
                return await self._impute_sequential(data, config, columns)
        
        for col in columns:
            if col in result.columns:
                if result[col].isnull().sum() == 0:
                    continue
                
                # Détection de la saisonnalité
                has_seasonality = await self._detect_seasonality(result, col)
                
                if config.method == ImputationMethod.SEASONAL and has_seasonality:
                    # Imputation avec saisonnalité
                    result[col] = await self._impute_with_seasonality(result, col)
                elif config.method == ImputationMethod.ARIMA:
                    # Imputation ARIMA
                    result[col] = await self._impute_with_arima(result, col)
                elif config.method == ImputationMethod.LINEAR_TREND:
                    # Imputation avec tendance linéaire
                    result[col] = await self._impute_with_trend(result, col)
                elif config.method == ImputationMethod.EXPONENTIAL_SMOOTHING:
                    # Lissage exponentiel
                    result[col] = await self._impute_with_exp_smoothing(result, col)
                else:
                    # Par défaut: interpolation
                    result[col].interpolate(method='time', limit_direction='both', inplace=True)
        
        return result
    
    async def _impute_hybrid(
        self,
        data: pd.DataFrame,
        config: ImputationConfig,
        columns: List[str]
    ) -> pd.DataFrame:
        """Imputation hybride."""
        result = data.copy()
        
        for col in columns:
            if col in result.columns:
                if result[col].isnull().sum() == 0:
                    continue
                
                missing_pct = result[col].isnull().sum() / len(result)
                
                if missing_pct < 0.1:
                    # Peu de valeurs manquantes: interpolation
                    result[col].interpolate(method='linear', limit_direction='both', inplace=True)
                elif missing_pct < 0.3:
                    # Moyen: imputation séquentielle
                    result[col].fillna(method='ffill', inplace=True)
                    result[col].fillna(method='bfill', inplace=True)
                else:
                    # Beaucoup de valeurs manquantes: imputation multivariée
                    # Création d'une configuration pour multivariée
                    multi_config = ImputationConfig(
                        method=ImputationMethod.LINEAR_REGRESSION,
                        strategy=ImputationStrategy.MULTIVARIATE,
                        columns=[col]
                    )
                    temp_result = await self._impute_multivariate(result, multi_config, [col])
                    if col in temp_result.columns:
                        result[col] = temp_result[col]
        
        return result
    
    async def _impute_ensemble(
        self,
        data: pd.DataFrame,
        config: ImputationConfig,
        columns: List[str]
    ) -> pd.DataFrame:
        """Imputation par ensemble de méthodes."""
        result = data.copy()
        
        # Définition des méthodes à utiliser
        methods = [
            ImputationMethod.MEAN,
            ImputationMethod.INTERPOLATION,
            ImputationMethod.LINEAR_REGRESSION,
            ImputationMethod.FORWARD_FILL
        ]
        
        for col in columns:
            if col in result.columns:
                if result[col].isnull().sum() == 0:
                    continue
                
                # Imputation avec chaque méthode
                imputations = []
                
                for method in methods:
                    temp_config = ImputationConfig(
                        method=method,
                        strategy=ImputationStrategy.SIMPLE,
                        columns=[col]
                    )
                    temp_result = await self._impute_simple(result, temp_config, [col])
                    if col in temp_result.columns:
                        imputations.append(temp_result[col].values)
                
                # Moyenne des imputations
                if imputations:
                    ensemble_values = np.array(imputations)
                    result[col] = np.mean(ensemble_values, axis=0)
        
        return result
    
    # ========== MÉTHODES PRIVÉES - IMPUTATION SPÉCIFIQUE ==========
    
    async def _impute_with_seasonality(
        self,
        data: pd.DataFrame,
        col: str
    ) -> pd.Series:
        """Imputation avec prise en compte de la saisonnalité."""
        # Détection de la période
        period = await self._detect_seasonal_period(data, col)
        
        if period:
            # Création d'une série avec les valeurs manquantes
            series = data[col].copy()
            
            # Groupement par saison
            groups = series.groupby(series.index % period)
            seasonal_means = groups.mean()
            
            # Remplissage
            for idx in series[series.isnull()].index:
                season = idx % period
                if season in seasonal_means.index:
                    series[idx] = seasonal_means[season]
            
            # Remplissage des valeurs restantes par interpolation
            series.fillna(method='ffill', inplace=True)
            series.fillna(method='bfill', inplace=True)
            
            return series
        
        # Fallback: interpolation
        return data[col].interpolate(method='time', limit_direction='both')
    
    async def _impute_with_arima(
        self,
        data: pd.DataFrame,
        col: str
    ) -> pd.Series:
        """Imputation ARIMA."""
        # Simulation d'imputation ARIMA
        # Dans un système réel, on utiliserait statsmodels
        series = data[col].copy()
        
        # Simple interpolation pour l'exemple
        series.interpolate(method='time', limit_direction='both', inplace=True)
        series.fillna(method='ffill', inplace=True)
        series.fillna(method='bfill', inplace=True)
        
        return series
    
    async def _impute_with_trend(
        self,
        data: pd.DataFrame,
        col: str
    ) -> pd.Series:
        """Imputation avec tendance linéaire."""
        series = data[col].copy()
        
        # Création d'un index numérique
        x = np.arange(len(series))
        not_nan = ~series.isnull()
        
        if not_nan.sum() > 1:
            # Régression linéaire
            slope, intercept = np.polyfit(x[not_nan], series[not_nan], 1)
            
            # Remplissage
            for idx in series[series.isnull()].index:
                series[idx] = slope * x[idx] + intercept
        
        # Remplissage des valeurs restantes
        series.fillna(method='ffill', inplace=True)
        series.fillna(method='bfill', inplace=True)
        
        return series
    
    async def _impute_with_exp_smoothing(
        self,
        data: pd.DataFrame,
        col: str
    ) -> pd.Series:
        """Imputation par lissage exponentiel."""
        series = data[col].copy()
        
        # Simple lissage exponentiel
        alpha = 0.3
        for i in range(1, len(series)):
            if pd.isna(series.iloc[i]):
                if not pd.isna(series.iloc[i-1]):
                    series.iloc[i] = series.iloc[i-1] * (1 - alpha) + series.iloc[i-1] * alpha
        
        # Remplissage des valeurs restantes
        series.fillna(method='ffill', inplace=True)
        series.fillna(method='bfill', inplace=True)
        
        return series
    
    # ========== MÉTHODES PRIVÉES - DÉTECTION ==========
    
    async def _detect_missing_pattern(self, data: pd.DataFrame) -> MissingPattern:
        """Détecte le pattern des valeurs manquantes."""
        if not self.config["auto_detect_pattern"]:
            return MissingPattern.RANDOM
        
        missing = data.isnull()
        
        # Vérification MCAR
        if missing.sum().sum() > 0:
            # Test de corrélation entre les valeurs manquantes et les données
            # Simulation simplifiée
            random_pct = missing.sum().sum() / (data.shape[0] * data.shape[1])
            
            if random_pct < 0.1:
                return MissingPattern.RANDOM
            
            # Vérification de la structure
            for col in data.columns:
                if missing[col].sum() > 0:
                    # Si les valeurs manquantes sont dans des blocs
                    diff = missing[col].astype(int).diff().fillna(0)
                    if (diff == 1).sum() > 0:
                        return MissingPattern.STRUCTURAL
        
        return MissingPattern.RANDOM
    
    async def _detect_seasonality(self, data: pd.DataFrame, col: str) -> bool:
        """Détecte la saisonnalité dans une colonne."""
        try:
            series = data[col].dropna()
            if len(series) < 24:  # Pas assez de points
                return False
            
            # ACF simplifié
            acf = [1.0]
            for lag in range(1, min(24, len(series) // 2)):
                corr = np.corrcoef(series[:-lag], series[lag:])[0, 1]
                if not np.isnan(corr):
                    acf.append(corr)
            
            # Détection de pics
            if len(acf) > 6:
                peaks = [i for i in range(2, len(acf)) if acf[i] > 0.3]
                return len(peaks) > 0
            
            return False
            
        except:
            return False
    
    async def _detect_seasonal_period(self, data: pd.DataFrame, col: str) -> Optional[int]:
        """Détecte la période saisonnière."""
        try:
            series = data[col].dropna()
            if len(series) < 24:
                return None
            
            # ACF
            acf = []
            for lag in range(1, min(24, len(series) // 2)):
                corr = np.corrcoef(series[:-lag], series[lag:])[0, 1]
                if not np.isnan(corr):
                    acf.append(corr)
            
            # Recherche du pic maximal
            if acf:
                max_lag = np.argmax(acf[1:]) + 1
                if max_lag >= 2 and acf[max_lag] > 0.3:
                    return max_lag
            
            return None
            
        except:
            return None
    
    async def _generate_recommendations(
        self,
        data: pd.DataFrame,
        pattern: MissingPattern
    ) -> List[str]:
        """Génère des recommandations pour l'imputation."""
        recommendations = []
        
        total_missing = data.isnull().sum().sum()
        
        if total_missing == 0:
            recommendations.append("No missing values detected")
            return recommendations
        
        missing_pct = total_missing / (data.shape[0] * data.shape[1])
        
        if missing_pct > 0.5:
            recommendations.append("High percentage of missing values (>50%) - Consider data quality review")
        elif missing_pct > 0.3:
            recommendations.append("Significant missing values (>30%) - Consider multivariate imputation")
        else:
            recommendations.append("Consider temporal imputation for time series data")
        
        if pattern == MissingPattern.RANDOM:
            recommendations.append("Random missing pattern detected - Simple imputation methods may be sufficient")
        elif pattern == MissingPattern.STRUCTURAL:
            recommendations.append("Structural missing pattern detected - Consider sequential or temporal imputation")
        
        # Recommandations par colonne
        for col in data.columns:
            missing_col = data[col].isnull().sum()
            if missing_col > 0:
                pct_col = missing_col / len(data)
                if pct_col > 0.3:
                    recommendations.append(f"Column '{col}' has {pct_col:.1%} missing values - Consider multivariate imputation")
                elif pct_col > 0.1:
                    recommendations.append(f"Column '{col}' has {pct_col:.1%} missing values - Consider interpolation")
        
        return recommendations
    
    # ========== MÉTHODES PRIVÉES - VALIDATION ==========
    
    async def _validate_data(self, data: pd.DataFrame, config: ImputationConfig) -> None:
        """Valide les données avant imputation."""
        if data.empty:
            raise ValueError("Data is empty")
        
        if config.max_missing_pct > 0:
            missing_pct = data.isnull().sum().sum() / (data.shape[0] * data.shape[1])
            if missing_pct > config.max_missing_pct:
                raise ValueError(f"Missing values exceed threshold: {missing_pct:.1%} > {config.max_missing_pct:.1%}")
        
        if config.columns:
            for col in config.columns:
                if col not in data.columns:
                    logger.warning(f"Column '{col}' not found in data")
    
    async def _calculate_imputation_accuracy(
        self,
        original: pd.DataFrame,
        imputed: pd.DataFrame
    ) -> float:
        """Calcule l'exactitude de l'imputation."""
        # Simulation de l'exactitude
        # Dans un système réel, on utiliserait un ensemble de validation
        # ou on comparerait avec des valeurs connues
        
        # Simulation basée sur la qualité de l'imputation
        missing_original = original.isnull().sum().sum()
        missing_imputed = imputed.isnull().sum().sum()
        
        if missing_original == 0:
            return 1.0
        
        # Proportion de valeurs remplies
        filled = missing_original - missing_imputed
        if filled == 0:
            return 0.0
        
        # Simulation d'exactitude (en vrai, on utiliserait des métriques)
        accuracy = 0.7 + 0.25 * (filled / missing_original)
        accuracy = min(1.0, accuracy)
        
        return accuracy
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _load_configs(self) -> None:
        """Charge les configurations."""
        try:
            if self.data_manager:
                configs_data = await self.data_manager.retrieve(
                    "imputation:configs",
                    DataType.CONFIG
                )
                
                if configs_data:
                    for config_dict in configs_data:
                        config = self._deserialize_config(config_dict)
                        if config:
                            with self._configs_lock:
                                self._configs[config.config_id] = config
            
            logger.info(f"Loaded {len(self._configs)} imputation configurations")
            
        except Exception as e:
            logger.error(f"Load configs error: {e}")
    
    def _deserialize_config(self, data: Dict) -> Optional[ImputationConfig]:
        """Désérialise une configuration."""
        try:
            return ImputationConfig(
                config_id=data.get("config_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                method=ImputationMethod(data.get("method", "mean")),
                strategy=ImputationStrategy(data.get("strategy", "simple")),
                parameters=data.get("parameters", {}),
                columns=data.get("columns", []),
                threshold=data.get("threshold", 0.5),
                max_missing_pct=data.get("max_missing_pct", 0.3),
                preserve_trend=data.get("preserve_trend", True),
                preserve_seasonality=data.get("preserve_seasonality", True),
                seed=data.get("seed"),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True)
            )
        except Exception as e:
            logger.error(f"Error deserializing config: {e}")
            return None
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._analysis_cache) > self.config["cache_size"]:
                        keys = list(self._analysis_cache.keys())
                        for key in keys[:len(self._analysis_cache) - self.config["cache_size"]]:
                            del self._analysis_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._results_lock:
                    self._stats["total_results"] = len(self._results)
                with self._configs_lock:
                    self._stats["total_configs"] = len(self._configs)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "imputation:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def create_config(self, config: ImputationConfig) -> str:
        """Crée une configuration d'imputation."""
        with self._configs_lock:
            self._configs[config.config_id] = config
        
        if self.data_manager:
            await self.data_manager.store(
                f"imputation:config:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Imputation configuration created: {config.name}")
        return config.config_id
    
    async def get_result(self, result_id: str) -> Optional[ImputationResult]:
        """Récupère un résultat d'imputation."""
        with self._results_lock:
            return self._results.get(result_id)
    
    async def get_results(self) -> List[ImputationResult]:
        """Récupère les résultats d'imputation."""
        with self._results_lock:
            return list(self._results.values())
    
    async def get_analysis(self, analysis_id: str) -> Optional[MissingDataAnalysis]:
        """Récupère une analyse."""
        with self._cache_lock:
            return self._analysis_cache.get(analysis_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._results_lock:
            self._stats["results_count"] = len(self._results)
        with self._configs_lock:
            self._stats["configs_count"] = len(self._configs)
        
        return self._stats.copy()


# ============== FACTORY ==============

class ImputationFactory:
    """Factory pour créer des composants d'imputation."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ImputationEngine:
        """Crée un moteur d'imputation."""
        engine = ImputationEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "ImputationMethod",
    "ImputationStrategy",
    "MissingPattern",
    "ImputationConfig",
    "ImputationResult",
    "MissingDataAnalysis",
    "ImputationEngineInterface",
    "ImputationEngine",
    "ImputationFactory"
]
