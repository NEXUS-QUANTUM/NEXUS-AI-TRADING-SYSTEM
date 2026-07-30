# trading/bots/hedge_bot/hedge_bot_data_forecast.py
# Advanced Forecasting & Predictive Analytics Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Forecast Module - Module de prévision et d'analyse prédictive avancé pour le Hedge Bot.
Fournit des capacités de prévision de séries temporelles, d'analyse prédictive, de détection de tendances,
et de modélisation probabiliste pour l'optimisation des décisions de hedging.
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
import hashlib
import pickle
import zlib
import random
from scipy import stats
from scipy.optimize import minimize
from scipy.signal import find_peaks, argrelextrema

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_forecast")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    DecisionContext, MarketRegime
)


# ============== ENUMS & TYPES ==============

class ForecastMethod(Enum):
    """Méthodes de prévision disponibles."""
    ARIMA = "arima"
    SARIMA = "sarima"
    ETS = "ets"
    PROPHET = "prophet"
    LSTM = "lstm"
    GRU = "gru"
    TRANSFORMER = "transformer"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    RANDOM_FOREST = "random_forest"
    ENSEMBLE = "ensemble"
    BAYESIAN = "bayesian"
    NEURAL_PROPHET = "neural_prophet"
    NBEATS = "nbeats"
    AUTO = "auto"


class ForecastHorizon(Enum):
    """Horizons de prévision."""
    SHORT = "short"      # Minutes à heures
    MEDIUM = "medium"    # Heures à jours
    LONG = "long"        # Jours à semaines
    EXTENDED = "extended" # Semaines à mois


class ForecastConfidence(Enum):
    """Niveaux de confiance pour les prévisions."""
    LOW = 0.6
    MEDIUM = 0.8
    HIGH = 0.95
    VERY_HIGH = 0.99


class TrendDirection(Enum):
    """Directions de tendance."""
    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"
    REVERSAL = "reversal"


# ============== DATA MODELS ==============

@dataclass
class ForecastResult:
    """Résultat de prévision."""
    forecast_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    method: ForecastMethod = ForecastMethod.AUTO
    horizon: ForecastHorizon = ForecastHorizon.MEDIUM
    confidence: float = 0.8
    predictions: List[float] = field(default_factory=list)
    lower_bound: List[float] = field(default_factory=list)
    upper_bound: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)
    accuracy: float = 0.0
    mae: float = 0.0
    rmse: float = 0.0
    mape: float = 0.0
    trend_direction: TrendDirection = TrendDirection.UNKNOWN
    trend_strength: float = 0.0
    seasonality: Dict[str, float] = field(default_factory=dict)
    residuals: List[float] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    feature_importance: Dict[str, float] = field(default_factory=dict)


@dataclass
class ForecastInput:
    """Entrée pour la prévision."""
    input_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    target_column: str = "close"
    feature_columns: List[str] = field(default_factory=list)
    exogenous_columns: List[str] = field(default_factory=list)
    horizon_steps: int = 24
    frequency: str = "1H"
    method: ForecastMethod = ForecastMethod.AUTO
    confidence: float = 0.8
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ForecastEnsemble:
    """Ensemble de prévisions."""
    ensemble_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    forecasts: List[ForecastResult] = field(default_factory=list)
    weights: List[float] = field(default_factory=list)
    aggregated_result: Optional[ForecastResult] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnomalyDetectionResult:
    """Résultat de détection d'anomalies."""
    detection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    value: float = 0.0
    expected: float = 0.0
    deviation: float = 0.0
    z_score: float = 0.0
    is_anomaly: bool = False
    severity: str = "low"  # low, medium, high, critical
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class ForecastEngineInterface(ABC):
    """Interface abstraite pour le moteur de prévision."""
    
    @abstractmethod
    async def forecast(self, input_data: ForecastInput) -> ForecastResult:
        """Exécute une prévision."""
        pass
    
    @abstractmethod
    async def ensemble_forecast(self, inputs: List[ForecastInput]) -> ForecastEnsemble:
        """Exécute une prévision par ensemble."""
        pass
    
    @abstractmethod
    async def detect_anomalies(self, data: pd.DataFrame, threshold: float = 3.0) -> List[AnomalyDetectionResult]:
        """Détecte des anomalies dans les données."""
        pass


# ============== IMPLÉMENTATION ==============

class ForecastEngine(ForecastEngineInterface):
    """
    Moteur de prévision avancé pour le Hedge Bot.
    Implémente plusieurs méthodes de prévision pour l'analyse prédictive des marchés.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Cache des prévisions
        self._forecast_cache: Dict[str, ForecastResult] = {}
        self._cache_lock = threading.RLock()
        
        # Historique des prévisions
        self._forecast_history: Dict[str, List[ForecastResult]] = defaultdict(list)
        self._history_lock = threading.RLock()
        
        # Modèles entraînés (simulés)
        self._models: Dict[str, Any] = {}
        self._model_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "forecasts_completed": 0,
            "forecasts_failed": 0,
            "ensemble_forecasts": 0,
            "anomalies_detected": 0,
            "avg_accuracy": 0.0,
            "avg_mae": 0.0,
            "avg_rmse": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("ForecastEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_method": ForecastMethod.AUTO,
            "default_horizon": ForecastHorizon.MEDIUM,
            "default_confidence": 0.8,
            "cache_size": 1000,
            "cache_ttl": 3600,  # 1 heure
            "enable_cache": True,
            "enable_ensemble": True,
            "ensemble_weights": "uniform",  # uniform, performance, dynamic
            "max_forecast_steps": 1000,
            "min_data_points": 30,
            "seasonality_periods": [7, 14, 30, 90],
            "anomaly_threshold": 3.0,
            "anomaly_window": 20
        }
    
    async def start(self) -> None:
        """Démarre le moteur de prévision."""
        logger.info("ForecastEngine starting...")
        self._is_running = True
        
        # Chargement des modèles pré-entraînés
        await self._load_models()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._performance_monitor())
        
        logger.info("ForecastEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de prévision."""
        logger.info("ForecastEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("ForecastEngine stopped")
    
    async def forecast(self, input_data: ForecastInput) -> ForecastResult:
        """Exécute une prévision."""
        start_time = time.time()
        
        try:
            # Validation des données
            self._validate_input(input_data)
            
            # Vérification du cache
            cache_key = self._compute_cache_key(input_data)
            if self.config["enable_cache"] and cache_key in self._forecast_cache:
                cached = self._forecast_cache[cache_key]
                age = (datetime.now(timezone.utc) - cached.created_at).total_seconds()
                if age < self.config["cache_ttl"]:
                    logger.debug(f"Forecast cache hit: {cache_key}")
                    return cached
            
            # Préparation des données
            prepared_data = await self._prepare_data(input_data)
            
            # Sélection de la méthode
            method = await self._select_method(input_data, prepared_data)
            
            # Exécution de la prévision
            result = await self._execute_forecast(prepared_data, method, input_data)
            
            # Validation du résultat
            result = await self._validate_forecast(result)
            
            # Mise en cache
            if self.config["enable_cache"]:
                with self._cache_lock:
                    if len(self._forecast_cache) < self.config["cache_size"]:
                        self._forecast_cache[cache_key] = result
            
            # Historique
            with self._history_lock:
                self._forecast_history[input_data.symbol].append(result)
            
            # Mise à jour des statistiques
            self._stats["forecasts_completed"] += 1
            self._stats["avg_accuracy"] = (
                self._stats["avg_accuracy"] * 0.9 + result.accuracy * 0.1
            )
            self._stats["avg_mae"] = (
                self._stats["avg_mae"] * 0.9 + result.mae * 0.1
            )
            self._stats["avg_rmse"] = (
                self._stats["avg_rmse"] * 0.9 + result.rmse * 0.1
            )
            
            # Stockage du résultat
            if self.data_manager:
                await self.data_manager.store(
                    f"forecast:{result.forecast_id}",
                    result.to_dict(),
                    DataType.FORECAST
                )
            
            execution_time = time.time() - start_time
            logger.info(f"Forecast completed: {result.forecast_id} "
                       f"method={result.method.value} "
                       f"accuracy={result.accuracy:.4f} "
                       f"time={execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            self._stats["forecasts_failed"] += 1
            logger.error(f"Forecast error: {e}")
            raise
    
    async def ensemble_forecast(self, inputs: List[ForecastInput]) -> ForecastEnsemble:
        """Exécute une prévision par ensemble."""
        self._stats["ensemble_forecasts"] += 1
        
        try:
            forecasts = []
            weights = []
            
            # Exécution des prévisions individuelles
            for input_data in inputs:
                try:
                    result = await self.forecast(input_data)
                    forecasts.append(result)
                    
                    # Calcul du poids basé sur la performance
                    if self.config["ensemble_weights"] == "performance":
                        weight = max(0.1, result.accuracy)
                    elif self.config["ensemble_weights"] == "dynamic":
                        weight = max(0.1, 1 / (result.mae + 0.01))
                    else:
                        weight = 1.0
                    weights.append(weight)
                    
                except Exception as e:
                    logger.warning(f"Ensemble member failed: {e}")
                    continue
            
            if not forecasts:
                raise ValueError("No successful forecasts in ensemble")
            
            # Normalisation des poids
            total_weight = sum(weights)
            weights = [w / total_weight for w in weights]
            
            # Agrégation des prévisions
            aggregated = await self._aggregate_forecasts(forecasts, weights)
            
            # Création de l'ensemble
            ensemble = ForecastEnsemble(
                forecasts=forecasts,
                weights=weights,
                aggregated_result=aggregated,
                metadata={
                    "num_models": len(forecasts),
                    "aggregation_method": "weighted_average",
                    "weights": weights
                }
            )
            
            logger.info(f"Ensemble forecast completed: {ensemble.ensemble_id} "
                       f"num_models={len(forecasts)}")
            
            return ensemble
            
        except Exception as e:
            logger.error(f"Ensemble forecast error: {e}")
            raise
    
    async def detect_anomalies(
        self,
        data: pd.DataFrame,
        threshold: float = 3.0
    ) -> List[AnomalyDetectionResult]:
        """Détecte des anomalies dans les données."""
        anomalies = []
        
        try:
            if len(data) < self.config["min_data_points"]:
                return anomalies
            
            # Calcul des métriques statistiques
            values = data.select_dtypes(include=[np.number]).values.flatten()
            mean = np.mean(values)
            std = np.std(values)
            
            # Détection par Z-score
            for idx, row in data.iterrows():
                for col in data.select_dtypes(include=[np.number]).columns:
                    value = row[col]
                    z_score = abs((value - mean) / std) if std > 0 else 0
                    
                    if z_score > threshold:
                        # Vérification du contexte (tendance, saisonnalité)
                        expected = await self._predict_expected_value(data, idx, col)
                        deviation = abs(value - expected) / (expected + 0.01)
                        
                        severity = "low"
                        if deviation > 0.5:
                            severity = "high"
                        elif deviation > 0.2:
                            severity = "medium"
                        
                        anomaly = AnomalyDetectionResult(
                            timestamp=idx if isinstance(idx, datetime) else datetime.now(timezone.utc),
                            value=value,
                            expected=expected,
                            deviation=deviation,
                            z_score=z_score,
                            is_anomaly=True,
                            severity=severity,
                            context={
                                "column": col,
                                "index": str(idx),
                                "mean": mean,
                                "std": std,
                                "threshold": threshold
                            }
                        )
                        anomalies.append(anomaly)
                        self._stats["anomalies_detected"] += 1
            
            logger.info(f"Anomaly detection completed: {len(anomalies)} anomalies found")
            return anomalies
            
        except Exception as e:
            logger.error(f"Anomaly detection error: {e}")
            return []
    
    # ========== MÉTHODES PRIVÉES - PRÉPARATION ==========
    
    def _validate_input(self, input_data: ForecastInput) -> None:
        """Valide les données d'entrée."""
        if input_data.data.empty:
            raise ValueError("Input data is empty")
        
        if len(input_data.data) < self.config["min_data_points"]:
            raise ValueError(f"Input data has insufficient points: {len(input_data.data)} < {self.config['min_data_points']}")
        
        if input_data.target_column not in input_data.data.columns:
            raise ValueError(f"Target column '{input_data.target_column}' not found in data")
        
        if input_data.horizon_steps <= 0:
            raise ValueError(f"Invalid horizon steps: {input_data.horizon_steps}")
        
        if input_data.confidence <= 0 or input_data.confidence >= 1:
            raise ValueError(f"Invalid confidence: {input_data.confidence}")
    
    async def _prepare_data(self, input_data: ForecastInput) -> pd.DataFrame:
        """Prépare les données pour la prévision."""
        data = input_data.data.copy()
        
        # Gestion des valeurs manquantes
        data = data.interpolate(method="linear", limit_direction="both")
        data = data.fillna(method="ffill").fillna(method="bfill")
        
        # Vérification de la fréquence
        if not isinstance(data.index, pd.DatetimeIndex):
            try:
                date_cols = data.select_dtypes(include=['datetime64']).columns
                if len(date_cols) > 0:
                    data.index = pd.DatetimeIndex(data[date_cols[0]])
                else:
                    # Création d'un index temporel
                    data.index = pd.date_range(
                        end=datetime.now(timezone.utc),
                        periods=len(data),
                        freq=input_data.frequency
                    )
            except:
                data.index = pd.RangeIndex(start=0, stop=len(data))
        
        # Normalisation
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if col != input_data.target_column:
                # Normalisation des features
                mean = data[col].mean()
                std = data[col].std()
                if std > 0:
                    data[col] = (data[col] - mean) / std
        
        return data
    
    async def _select_method(
        self,
        input_data: ForecastInput,
        data: pd.DataFrame
    ) -> ForecastMethod:
        """Sélectionne la méthode de prévision optimale."""
        if input_data.method != ForecastMethod.AUTO:
            return input_data.method
        
        # Sélection automatique basée sur les caractéristiques des données
        n_points = len(data)
        n_features = len(data.select_dtypes(include=[np.number]).columns)
        
        # Détection de saisonnalité
        has_seasonality = await self._detect_seasonality(data)
        
        # Sélection
        if n_points < 100:
            # Petites données: méthodes simples
            if has_seasonality:
                return ForecastMethod.ETS
            else:
                return ForecastMethod.ARIMA
        
        elif n_points < 500:
            # Données moyennes
            if has_seasonality:
                return ForecastMethod.SARIMA
            else:
                return ForecastMethod.PROPHET
        
        elif n_points < 2000:
            # Grandes données
            if n_features > 5:
                return ForecastMethod.XGBOOST
            else:
                return ForecastMethod.LSTM
        
        else:
            # Très grandes données
            if n_features > 10:
                return ForecastMethod.TRANSFORMER
            else:
                return ForecastMethod.NBEATS
    
    async def _detect_seasonality(self, data: pd.DataFrame) -> bool:
        """Détecte la saisonnalité dans les données."""
        target_col = data.select_dtypes(include=[np.number]).columns[0]
        values = data[target_col].values
        
        if len(values) < 30:
            return False
        
        # ACF simplifié
        acf = [1.0]
        max_lag = min(30, len(values) // 2)
        
        for lag in range(1, max_lag + 1):
            if lag >= len(values):
                break
            corr = np.corrcoef(values[:-lag], values[lag:])[0, 1]
            acf.append(corr if not np.isnan(corr) else 0)
        
        # Détection de pics significatifs
        peaks = []
        threshold = 2 / np.sqrt(len(values))
        
        for i in range(1, len(acf) - 1):
            if acf[i] > threshold and acf[i] > acf[i-1] and acf[i] > acf[i+1]:
                peaks.append(i)
        
        return len(peaks) > 0
    
    # ========== MÉTHODES PRIVÉES - EXÉCUTION ==========
    
    async def _execute_forecast(
        self,
        data: pd.DataFrame,
        method: ForecastMethod,
        input_data: ForecastInput
    ) -> ForecastResult:
        """Exécute la prévision avec la méthode sélectionnée."""
        # Simulation des différentes méthodes
        # Dans un système réel, on utiliserait des bibliothèques comme statsmodels, prophet, etc.
        
        if method == ForecastMethod.ARIMA:
            result = await self._forecast_arima(data, input_data)
        elif method == ForecastMethod.SARIMA:
            result = await self._forecast_sarima(data, input_data)
        elif method == ForecastMethod.ETS:
            result = await self._forecast_ets(data, input_data)
        elif method == ForecastMethod.PROPHET:
            result = await self._forecast_prophet(data, input_data)
        elif method == ForecastMethod.LSTM:
            result = await self._forecast_lstm(data, input_data)
        elif method == ForecastMethod.XGBOOST:
            result = await self._forecast_xgboost(data, input_data)
        elif method == ForecastMethod.TRANSFORMER:
            result = await self._forecast_transformer(data, input_data)
        else:
            # Par défaut: ARIMA
            result = await self._forecast_arima(data, input_data)
        
        return result
    
    async def _forecast_arima(self, data: pd.DataFrame, input_data: ForecastInput) -> ForecastResult:
        """Prévision ARIMA."""
        # Simulation ARIMA
        target = data[input_data.target_column].values
        n = len(target)
        steps = input_data.horizon_steps
        
        # Calcul des paramètres ARIMA simulés
        trend = np.polyfit(range(n), target, 1)[0]
        seasonal = 0.1 * np.sin(np.linspace(0, 4*np.pi, n))
        noise = 0.05 * np.random.randn(n)
        
        # Simulation des prédictions
        predictions = []
        lower_bound = []
        upper_bound = []
        
        last_value = target[-1]
        for i in range(steps):
            # Tendance + bruit
            pred = last_value + trend + 0.5 * np.random.randn()
            predictions.append(pred)
            
            # Intervalles de confiance
            std_error = 0.1 * (1 + i / steps)
            lower_bound.append(pred - 1.96 * std_error)
            upper_bound.append(pred + 1.96 * std_error)
            last_value = pred
        
        # Création des timestamps
        last_timestamp = data.index[-1] if isinstance(data.index, pd.DatetimeIndex) else datetime.now(timezone.utc)
        timestamps = [last_timestamp + timedelta(hours=i) for i in range(steps)]
        
        # Métriques de performance (simulées)
        accuracy = max(0, min(1, 0.7 + 0.2 * random.random()))
        mae = 0.1 * random.random()
        rmse = 0.15 * random.random()
        mape = 1.0 * random.random()
        
        # Analyse de tendance
        trend_direction, trend_strength = await self._analyze_trend(predictions)
        
        # Détection de saisonnalité
        seasonality = await self._detect_seasonality_periods(predictions)
        
        return ForecastResult(
            method=ForecastMethod.ARIMA,
            horizon=input_data.horizon,
            confidence=input_data.confidence,
            predictions=predictions,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            timestamps=timestamps,
            accuracy=accuracy,
            mae=mae,
            rmse=rmse,
            mape=mape,
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            seasonality=seasonality,
            residuals=[0.05 * np.random.randn() for _ in range(steps)],
            metadata={"model": "ARIMA", "order": (2, 1, 2)},
            tags=["arima", "time_series"]
        )
    
    async def _forecast_sarima(self, data: pd.DataFrame, input_data: ForecastInput) -> ForecastResult:
        """Prévision SARIMA."""
        # Simulation SARIMA (similaire à ARIMA avec saisonnalité)
        result = await self._forecast_arima(data, input_data)
        result.method = ForecastMethod.SARIMA
        result.seasonality = {"period": 24, "strength": 0.3}
        result.metadata = {"model": "SARIMA", "order": (1, 1, 1), "seasonal_order": (1, 0, 1, 24)}
        result.tags = ["sarima", "seasonal"]
        return result
    
    async def _forecast_ets(self, data: pd.DataFrame, input_data: ForecastInput) -> ForecastResult:
        """Prévision ETS (Exponential Smoothing)."""
        # Simulation ETS
        target = data[input_data.target_column].values
        n = len(target)
        steps = input_data.horizon_steps
        
        # Lissage exponentiel simulé
        alpha = 0.3
        level = target[-1]
        predictions = []
        
        for i in range(steps):
            pred = level + 0.5 * np.random.randn()
            predictions.append(pred)
            level = alpha * pred + (1 - alpha) * level
        
        # Intervalles de confiance
        lower_bound = [p - 0.2 for p in predictions]
        upper_bound = [p + 0.2 for p in predictions]
        
        # Création des timestamps
        last_timestamp = data.index[-1] if isinstance(data.index, pd.DatetimeIndex) else datetime.now(timezone.utc)
        timestamps = [last_timestamp + timedelta(hours=i) for i in range(steps)]
        
        return ForecastResult(
            method=ForecastMethod.ETS,
            horizon=input_data.horizon,
            confidence=input_data.confidence,
            predictions=predictions,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            timestamps=timestamps,
            accuracy=0.65 + 0.2 * random.random(),
            mae=0.08 * random.random(),
            rmse=0.12 * random.random(),
            mape=0.8 * random.random(),
            trend_direction=TrendDirection.SIDEWAYS,
            trend_strength=0.2,
            seasonality={},
            residuals=[0.04 * np.random.randn() for _ in range(steps)],
            metadata={"model": "ETS", "alpha": alpha},
            tags=["ets", "exponential_smoothing"]
        )
    
    async def _forecast_prophet(self, data: pd.DataFrame, input_data: ForecastInput) -> ForecastResult:
        """Prévision Prophet."""
        # Simulation Prophet
        target = data[input_data.target_column].values
        n = len(target)
        steps = input_data.horizon_steps
        
        # Tendance + saisonnalité + bruit
        trend = np.polyfit(range(n), target, 2)[0] * 0.01
        seasonal = 0.2 * np.sin(np.linspace(0, 6*np.pi, n))
        
        predictions = []
        for i in range(steps):
            pred = target[-1] + trend * (i + 1) + seasonal[-1] * (1 + 0.1 * i)
            predictions.append(pred)
        
        # Intervalles de confiance
        lower_bound = [p * 0.9 for p in predictions]
        upper_bound = [p * 1.1 for p in predictions]
        
        # Création des timestamps
        last_timestamp = data.index[-1] if isinstance(data.index, pd.DatetimeIndex) else datetime.now(timezone.utc)
        timestamps = [last_timestamp + timedelta(hours=i) for i in range(steps)]
        
        return ForecastResult(
            method=ForecastMethod.PROPHET,
            horizon=input_data.horizon,
            confidence=input_data.confidence,
            predictions=predictions,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            timestamps=timestamps,
            accuracy=0.75 + 0.15 * random.random(),
            mae=0.05 * random.random(),
            rmse=0.08 * random.random(),
            mape=0.5 * random.random(),
            trend_direction=TrendDirection.UP if predictions[-1] > predictions[0] else TrendDirection.DOWN,
            trend_strength=abs(predictions[-1] - predictions[0]) / (predictions[0] + 0.01),
            seasonality={"daily": 0.2, "weekly": 0.1},
            residuals=[0.03 * np.random.randn() for _ in range(steps)],
            metadata={"model": "Prophet", "growth": "linear"},
            tags=["prophet", "facebook"]
        )
    
    async def _forecast_lstm(self, data: pd.DataFrame, input_data: ForecastInput) -> ForecastResult:
        """Prévision LSTM."""
        # Simulation LSTM
        target = data[input_data.target_column].values
        steps = input_data.horizon_steps
        
        # Modèle LSTM simulé
        predictions = []
        window = 10
        for i in range(steps):
            if len(target) > window:
                recent = target[-window:]
                pred = np.mean(recent) + 0.1 * np.random.randn()
            else:
                pred = target[-1] + 0.1 * np.random.randn()
            predictions.append(pred)
            target = np.append(target, [pred]) if len(target) < 1000 else target
        
        # Intervalles de confiance
        lower_bound = [p - 0.15 for p in predictions]
        upper_bound = [p + 0.15 for p in predictions]
        
        # Création des timestamps
        last_timestamp = data.index[-1] if isinstance(data.index, pd.DatetimeIndex) else datetime.now(timezone.utc)
        timestamps = [last_timestamp + timedelta(hours=i) for i in range(steps)]
        
        return ForecastResult(
            method=ForecastMethod.LSTM,
            horizon=input_data.horizon,
            confidence=input_data.confidence,
            predictions=predictions,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            timestamps=timestamps,
            accuracy=0.8 + 0.1 * random.random(),
            mae=0.04 * random.random(),
            rmse=0.06 * random.random(),
            mape=0.4 * random.random(),
            trend_direction=TrendDirection.UP if predictions[-1] > predictions[0] else TrendDirection.DOWN,
            trend_strength=0.3,
            seasonality={},
            residuals=[0.02 * np.random.randn() for _ in range(steps)],
            metadata={"model": "LSTM", "layers": [64, 32], "epochs": 100},
            tags=["lstm", "deep_learning"]
        )
    
    async def _forecast_xgboost(self, data: pd.DataFrame, input_data: ForecastInput) -> ForecastResult:
        """Prévision XGBoost."""
        # Simulation XGBoost
        target = data[input_data.target_column].values
        steps = input_data.horizon_steps
        
        # Features simulées
        n_features = len(input_data.feature_columns) or 5
        feature_importance = {}
        for i in range(n_features):
            feature_importance[f"feature_{i}"] = random.uniform(0.05, 0.3)
        
        # Prédictions
        predictions = []
        for i in range(steps):
            pred = target[-1] + 0.05 * np.random.randn()
            predictions.append(pred)
        
        # Intervalles de confiance
        lower_bound = [p - 0.12 for p in predictions]
        upper_bound = [p + 0.12 for p in predictions]
        
        # Création des timestamps
        last_timestamp = data.index[-1] if isinstance(data.index, pd.DatetimeIndex) else datetime.now(timezone.utc)
        timestamps = [last_timestamp + timedelta(hours=i) for i in range(steps)]
        
        return ForecastResult(
            method=ForecastMethod.XGBOOST,
            horizon=input_data.horizon,
            confidence=input_data.confidence,
            predictions=predictions,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            timestamps=timestamps,
            accuracy=0.85 + 0.05 * random.random(),
            mae=0.03 * random.random(),
            rmse=0.05 * random.random(),
            mape=0.3 * random.random(),
            trend_direction=TrendDirection.SIDEWAYS,
            trend_strength=0.1,
            seasonality={},
            residuals=[0.02 * np.random.randn() for _ in range(steps)],
            feature_importance=feature_importance,
            metadata={"model": "XGBoost", "n_estimators": 100, "max_depth": 6},
            tags=["xgboost", "ensemble"]
        )
    
    async def _forecast_transformer(self, data: pd.DataFrame, input_data: ForecastInput) -> ForecastResult:
        """Prévision Transformer."""
        # Simulation Transformer
        steps = input_data.horizon_steps
        
        # Prédictions avec pattern plus complexe
        predictions = []
        base = data[input_data.target_column].iloc[-1] if len(data) > 0 else 100
        
        for i in range(steps):
            pred = base * (1 + 0.001 * i + 0.01 * np.sin(i / 10))
            predictions.append(pred)
        
        # Intervalles de confiance
        lower_bound = [p * 0.95 for p in predictions]
        upper_bound = [p * 1.05 for p in predictions]
        
        # Création des timestamps
        last_timestamp = data.index[-1] if isinstance(data.index, pd.DatetimeIndex) else datetime.now(timezone.utc)
        timestamps = [last_timestamp + timedelta(hours=i) for i in range(steps)]
        
        return ForecastResult(
            method=ForecastMethod.TRANSFORMER,
            horizon=input_data.horizon,
            confidence=input_data.confidence,
            predictions=predictions,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            timestamps=timestamps,
            accuracy=0.9 + 0.05 * random.random(),
            mae=0.02 * random.random(),
            rmse=0.03 * random.random(),
            mape=0.2 * random.random(),
            trend_direction=TrendDirection.UP,
            trend_strength=0.5,
            seasonality={"pattern": "sine"},
            residuals=[0.01 * np.random.randn() for _ in range(steps)],
            metadata={"model": "Transformer", "layers": 6, "heads": 8},
            tags=["transformer", "attention"]
        )
    
    # ========== MÉTHODES PRIVÉES - AGRÉGATION ==========
    
    async def _aggregate_forecasts(
        self,
        forecasts: List[ForecastResult],
        weights: List[float]
    ) -> ForecastResult:
        """Agrège plusieurs prévisions."""
        if len(forecasts) == 1:
            return forecasts[0]
        
        # Agrégation des prédictions
        max_steps = min(len(f.forecast_id) for f in forecasts)
        aggregated_predictions = []
        aggregated_lower = []
        aggregated_upper = []
        aggregated_timestamps = forecasts[0].timestamps[:max_steps]
        
        for i in range(max_steps):
            pred_sum = 0
            lower_sum = 0
            upper_sum = 0
            weight_sum = 0
            
            for f, w in zip(forecasts, weights):
                if i < len(f.predictions):
                    pred_sum += f.predictions[i] * w
                    lower_sum += f.lower_bound[i] * w
                    upper_sum += f.upper_bound[i] * w
                    weight_sum += w
            
            if weight_sum > 0:
                aggregated_predictions.append(pred_sum / weight_sum)
                aggregated_lower.append(lower_sum / weight_sum)
                aggregated_upper.append(upper_sum / weight_sum)
        
        # Métriques agrégées
        avg_accuracy = np.mean([f.accuracy for f in forecasts])
        avg_mae = np.mean([f.mae for f in forecasts])
        avg_rmse = np.mean([f.rmse for f in forecasts])
        
        # Analyse de tendance
        trend_direction, trend_strength = await self._analyze_trend(aggregated_predictions)
        
        return ForecastResult(
            method=ForecastMethod.ENSEMBLE,
            horizon=forecasts[0].horizon,
            confidence=np.mean([f.confidence for f in forecasts]),
            predictions=aggregated_predictions,
            lower_bound=aggregated_lower,
            upper_bound=aggregated_upper,
            timestamps=aggregated_timestamps,
            accuracy=avg_accuracy,
            mae=avg_mae,
            rmse=avg_rmse,
            mape=np.mean([f.mape for f in forecasts]),
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            seasonality=forecasts[0].seasonality,
            residuals=[0.01 * np.random.randn() for _ in range(len(aggregated_predictions))],
            metadata={
                "num_models": len(forecasts),
                "weights": weights,
                "methods": [f.method.value for f in forecasts]
            },
            tags=["ensemble", "aggregated"]
        )
    
    # ========== MÉTHODES PRIVÉES - ANALYSE ==========
    
    async def _analyze_trend(self, values: List[float]) -> Tuple[TrendDirection, float]:
        """Analyse la tendance d'une série de valeurs."""
        if len(values) < 2:
            return TrendDirection.UNKNOWN, 0.0
        
        # Régression linéaire
        x = np.arange(len(values))
        slope, intercept = np.polyfit(x, values, 1)
        
        # Direction
        if slope > 0.01:
            direction = TrendDirection.UP
        elif slope < -0.01:
            direction = TrendDirection.DOWN
        else:
            direction = TrendDirection.SIDEWAYS
        
        # Force de la tendance
        r2 = np.corrcoef(x, values)[0, 1] ** 2 if len(x) > 1 else 0
        
        return direction, r2
    
    async def _detect_seasonality_periods(self, values: List[float]) -> Dict[str, float]:
        """Détecte les périodes de saisonnalité."""
        if len(values) < 30:
            return {}
        
        periods = self.config["seasonality_periods"]
        seasonality = {}
        
        for period in periods:
            if len(values) < period * 2:
                continue
            
            # ACF à la période
            corr = np.corrcoef(values[:-period], values[period:])[0, 1]
            if not np.isnan(corr) and abs(corr) > 0.2:
                seasonality[f"period_{period}"] = abs(corr)
        
        return seasonality
    
    async def _predict_expected_value(
        self,
        data: pd.DataFrame,
        idx: Union[int, datetime],
        column: str
    ) -> float:
        """Prédit la valeur attendue pour une détection d'anomalie."""
        if isinstance(idx, int):
            # Série temporelle
            values = data[column].values
            window = min(self.config["anomaly_window"], len(values) // 2)
            
            if idx < window:
                return np.mean(values[:idx+1]) if idx > 0 else values[0]
            
            # Moyenne mobile simple
            return np.mean(values[idx-window:idx])
        else:
            # Index datetime
            window = self.config["anomaly_window"]
            mask = data.index <= idx
            recent = data[mask].tail(window)
            if len(recent) > 0:
                return recent[column].mean()
            return data[column].mean()
    
    async def _validate_forecast(self, result: ForecastResult) -> ForecastResult:
        """Valide le résultat de la prévision."""
        # Vérification des intervalles de confiance
        if len(result.lower_bound) != len(result.predictions):
            result.lower_bound = [p * 0.9 for p in result.predictions]
            result.upper_bound = [p * 1.1 for p in result.predictions]
        
        # Vérification des timestamps
        if len(result.timestamps) != len(result.predictions):
            last_ts = datetime.now(timezone.utc)
            result.timestamps = [last_ts + timedelta(hours=i) for i in range(len(result.predictions))]
        
        return result
    
    # ========== MÉTHODES PRIVÉES - CACHE ==========
    
    def _compute_cache_key(self, input_data: ForecastInput) -> str:
        """Calcule une clé de cache."""
        key_data = {
            "symbol": input_data.symbol,
            "target": input_data.target_column,
            "horizon": input_data.horizon_steps,
            "method": input_data.method.value,
            "confidence": input_data.confidence,
            "data_hash": hashlib.md5(input_data.data.to_json().encode()).hexdigest()[:10]
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                with self._cache_lock:
                    if len(self._forecast_cache) > self.config["cache_size"]:
                        # Suppression des plus anciens
                        keys = sorted(self._forecast_cache.keys())
                        for key in keys[:len(self._forecast_cache) - self.config["cache_size"]]:
                            del self._forecast_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    # ========== MÉTHODES PRIVÉES - MODÈLES ==========
    
    async def _load_models(self) -> None:
        """Charge les modèles pré-entraînés."""
        try:
            if self.data_manager:
                models_data = await self.data_manager.retrieve(
                    "forecast:models",
                    DataType.MODEL
                )
                if models_data:
                    self._models = models_data
            
            logger.info(f"Loaded {len(self._models)} forecast models")
            
        except Exception as e:
            logger.warning(f"Could not load models: {e}")
    
    async def _performance_monitor(self) -> None:
        """Monitor les performances des prévisions."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                # Mise à jour des statistiques
                total = self._stats["forecasts_completed"]
                if total > 0:
                    self._stats["avg_accuracy"] = min(1, self._stats["avg_accuracy"])
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "forecast:stats",
                        self._stats,
                        DataType.PERFORMANCE
                    )
                
            except Exception as e:
                logger.error(f"Performance monitor error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_forecast(self, forecast_id: str) -> Optional[ForecastResult]:
        """Récupère une prévision par ID."""
        with self._cache_lock:
            for result in self._forecast_cache.values():
                if result.forecast_id == forecast_id:
                    return result
        
        if self.data_manager:
            data = await self.data_manager.retrieve(
                f"forecast:{forecast_id}",
                DataType.FORECAST
            )
            if data:
                return self._deserialize_forecast(data)
        
        return None
    
    async def get_forecast_history(self, symbol: str, limit: int = 100) -> List[ForecastResult]:
        """Récupère l'historique des prévisions pour un symbole."""
        with self._history_lock:
            history = self._forecast_history.get(symbol, [])
            return history[-limit:]
    
    def _deserialize_forecast(self, data: Dict) -> ForecastResult:
        """Désérialise une prévision."""
        try:
            return ForecastResult(
                forecast_id=data.get("forecast_id", str(uuid.uuid4())),
                method=ForecastMethod(data.get("method", "auto")),
                horizon=ForecastHorizon(data.get("horizon", "medium")),
                confidence=data.get("confidence", 0.8),
                predictions=data.get("predictions", []),
                lower_bound=data.get("lower_bound", []),
                upper_bound=data.get("upper_bound", []),
                timestamps=[datetime.fromisoformat(ts) for ts in data.get("timestamps", [])],
                accuracy=data.get("accuracy", 0.0),
                mae=data.get("mae", 0.0),
                rmse=data.get("rmse", 0.0),
                mape=data.get("mape", 0.0),
                trend_direction=TrendDirection(data.get("trend_direction", "unknown")),
                trend_strength=data.get("trend_strength", 0.0),
                seasonality=data.get("seasonality", {}),
                residuals=data.get("residuals", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                feature_importance=data.get("feature_importance", {})
            )
        except Exception as e:
            logger.error(f"Error deserializing forecast: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._cache_lock:
            self._stats["cache_size"] = len(self._forecast_cache)
        with self._history_lock:
            self._stats["history_size"] = sum(len(h) for h in self._forecast_history.values())
        
        return self._stats.copy()


# ============== FACTORY ==============

class ForecastFactory:
    """Factory pour créer des composants de prévision."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ForecastEngine:
        """Crée un moteur de prévision."""
        engine = ForecastEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_input(
        symbol: str,
        data: pd.DataFrame,
        target_column: str = "close",
        horizon_steps: int = 24,
        **kwargs
    ) -> ForecastInput:
        """Crée une entrée de prévision."""
        return ForecastInput(
            symbol=symbol,
            data=data,
            target_column=target_column,
            horizon_steps=horizon_steps,
            **kwargs
        )


# ============== EXPORT ==============

__all__ = [
    "ForecastMethod",
    "ForecastHorizon",
    "ForecastConfidence",
    "TrendDirection",
    "ForecastResult",
    "ForecastInput",
    "ForecastEnsemble",
    "AnomalyDetectionResult",
    "ForecastEngineInterface",
    "ForecastEngine",
    "ForecastFactory"
]
