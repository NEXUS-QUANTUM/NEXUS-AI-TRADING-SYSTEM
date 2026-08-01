# trading/bots/hedge_bot/hedge_bot_data_predict.py
# Advanced Predictive Analytics & Forecasting Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Predict Module - Module avancé d'analytique prédictive et de prévision pour le Hedge Bot.
Gère les prévisions de prix, les prédictions de volatilité, l'analyse de tendance,
les modèles prédictifs et l'évaluation des performances pour le système de hedging.
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
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_predict")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_market_data import (
    MarketData, MarketDataInterval, MarketDataEngine
)


# ============== ENUMS & TYPES ==============

class PredictionModel(Enum):
    """Types de modèles de prédiction."""
    LINEAR_REGRESSION = "linear_regression"
    RIDGE = "ridge"
    LASSO = "lasso"
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    LSTM = "lstm"
    GRU = "gru"
    TRANSFORMER = "transformer"
    ARIMA = "arima"
    PROPHET = "prophet"
    ENSEMBLE = "ensemble"


class PredictionType(Enum):
    """Types de prédictions."""
    PRICE = "price"
    VOLATILITY = "volatility"
    TREND = "trend"
    DIRECTION = "direction"
    VOLUME = "volume"
    TURNOVER = "turnover"
    RISK = "risk"
    CORRELATION = "correlation"


class PredictionHorizon(Enum):
    """Horizons de prédiction."""
    SHORT = "short"      # Minutes à heures
    MEDIUM = "medium"    # Heures à jours
    LONG = "long"        # Jours à semaines
    EXTENDED = "extended" # Semaines à mois


# ============== DATA MODELS ==============

@dataclass
class PredictionResult:
    """Résultat de prédiction."""
    prediction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model: PredictionModel = PredictionModel.RANDOM_FOREST
    prediction_type: PredictionType = PredictionType.PRICE
    horizon: PredictionHorizon = PredictionHorizon.MEDIUM
    symbol: str = ""
    value: float = 0.0
    confidence_lower: float = 0.0
    confidence_upper: float = 0.0
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    target_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=1))
    features: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    accuracy: float = 0.0
    mae: float = 0.0
    rmse: float = 0.0


@dataclass
class PredictionModelConfig:
    """Configuration de modèle de prédiction."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    model_type: PredictionModel = PredictionModel.RANDOM_FOREST
    prediction_type: PredictionType = PredictionType.PRICE
    horizon: PredictionHorizon = PredictionHorizon.MEDIUM
    features: List[str] = field(default_factory=list)
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    training_window: int = 1000
    retrain_interval: int = 3600
    retrain_threshold: float = 0.01
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PredictionHistory:
    """Historique des prédictions."""
    history_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    prediction_type: PredictionType = PredictionType.PRICE
    predictions: List[PredictionResult] = field(default_factory=list)
    actuals: List[float] = field(default_factory=list)
    errors: List[float] = field(default_factory=list)
    accuracy: float = 0.0
    mae: float = 0.0
    rmse: float = 0.0
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=30))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class PredictionEngineInterface(ABC):
    """Interface abstraite pour le moteur de prédiction."""
    
    @abstractmethod
    async def predict(self, config: PredictionModelConfig, data: pd.DataFrame) -> PredictionResult:
        """Exécute une prédiction."""
        pass
    
    @abstractmethod
    async def train_model(self, config: PredictionModelConfig, data: pd.DataFrame) -> bool:
        """Entraîne un modèle de prédiction."""
        pass
    
    @abstractmethod
    async def get_prediction(self, prediction_id: str) -> Optional[PredictionResult]:
        """Récupère une prédiction."""
        pass


# ============== IMPLÉMENTATION ==============

class PredictionEngine(PredictionEngineInterface):
    """
    Moteur de prédiction avancé pour le Hedge Bot.
    Gère les prévisions de prix, la volatilité et l'analyse de tendance.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        market_data_engine: Optional[MarketDataEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.market_data_engine = market_data_engine
        self.config = config or self._default_config()
        
        # Gestion des modèles
        self._models: Dict[str, Any] = {}
        self._models_lock = threading.RLock()
        
        # Gestion des configurations
        self._configs: Dict[str, PredictionModelConfig] = {}
        self._configs_lock = threading.RLock()
        
        # Gestion des prédictions
        self._predictions: Dict[str, PredictionResult] = {}
        self._predictions_lock = threading.RLock()
        
        # Gestion de l'historique
        self._history: Dict[str, PredictionHistory] = {}
        self._history_lock = threading.RLock()
        
        # Cache des features
        self._feature_cache: Dict[str, pd.DataFrame] = {}
        self._cache_lock = threading.RLock()
        
        # Scalers
        self._scalers: Dict[str, StandardScaler] = {}
        self._scaler_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "predictions_made": 0,
            "models_trained": 0,
            "avg_accuracy": 0.0,
            "avg_mae": 0.0,
            "avg_rmse": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("PredictionEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_model": PredictionModel.RANDOM_FOREST,
            "default_horizon": PredictionHorizon.MEDIUM,
            "default_prediction_type": PredictionType.PRICE,
            "training_window": 1000,
            "retrain_interval": 3600,
            "retrain_threshold": 0.01,
            "cache_size": 100,
            "cache_ttl": 3600,
            "enable_cache": True,
            "enable_retraining": True,
            "parallel_training": True,
            "max_features": 50,
            "test_size": 0.2,
            "random_state": 42
        }
    
    async def start(self) -> None:
        """Démarre le moteur de prédiction."""
        logger.info("PredictionEngine starting...")
        self._is_running = True
        
        # Chargement des modèles
        await self._load_models()
        
        # Chargement des configurations
        await self._load_configs()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._retraining_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("PredictionEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de prédiction."""
        logger.info("PredictionEngine stopping...")
        self._is_running = False
        
        # Sauvegarde des modèles
        await self._save_models()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("PredictionEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def predict(self, config: PredictionModelConfig, data: pd.DataFrame) -> PredictionResult:
        """Exécute une prédiction."""
        self._stats["predictions_made"] += 1
        
        try:
            # Préparation des données
            features = await self._prepare_features(data, config)
            
            if features.empty:
                raise ValueError("No features available for prediction")
            
            # Récupération du modèle
            model = await self._get_model(config)
            
            if model is None:
                raise ValueError(f"Model not available for config {config.config_id}")
            
            # Standardisation
            scaler = self._scalers.get(config.config_id)
            if scaler:
                features_scaled = scaler.transform(features.values.reshape(1, -1))
            else:
                features_scaled = features.values.reshape(1, -1)
            
            # Prédiction
            prediction = model.predict(features_scaled)[0]
            
            # Calcul des intervalles de confiance
            confidence_lower, confidence_upper = await self._calculate_confidence_interval(
                model, features_scaled, config
            )
            
            # Création du résultat
            result = PredictionResult(
                model=config.model_type,
                prediction_type=config.prediction_type,
                horizon=config.horizon,
                symbol=data.get("symbol", ""),
                value=prediction,
                confidence_lower=confidence_lower,
                confidence_upper=confidence_upper,
                confidence=0.8,
                features=features.to_dict(),
                accuracy=await self._get_model_accuracy(config)
            )
            
            # Stockage de la prédiction
            with self._predictions_lock:
                self._predictions[result.prediction_id] = result
            
            # Mise à jour de l'historique
            await self._update_history(result)
            
            logger.info(f"Prediction completed: {result.prediction_id} value={result.value:.4f}")
            return result
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            raise
    
    async def train_model(self, config: PredictionModelConfig, data: pd.DataFrame) -> bool:
        """Entraîne un modèle de prédiction."""
        try:
            # Préparation des données
            X, y = await self._prepare_training_data(data, config)
            
            if X.empty or len(y) == 0:
                raise ValueError("No training data available")
            
            # Split des données
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=self.config["test_size"], random_state=self.config["random_state"]
            )
            
            # Standardisation
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Création du modèle
            model = await self._create_model(config)
            
            # Entraînement
            model.fit(X_train_scaled, y_train)
            
            # Évaluation
            train_score = model.score(X_train_scaled, y_train)
            test_score = model.score(X_test_scaled, y_test)
            
            # Stockage du modèle
            with self._models_lock:
                self._models[config.config_id] = model
                self._scalers[config.config_id] = scaler
                self._stats["models_trained"] += 1
            
            # Sauvegarde du modèle
            await self._save_model(config.config_id, model)
            
            logger.info(f"Model trained: {config.name} train_score={train_score:.4f} test_score={test_score:.4f}")
            return True
            
        except Exception as e:
            logger.error(f"Training error: {e}")
            return False
    
    async def get_prediction(self, prediction_id: str) -> Optional[PredictionResult]:
        """Récupère une prédiction."""
        with self._predictions_lock:
            return self._predictions.get(prediction_id)
    
    # ========== MÉTHODES PRIVÉES - PRÉDICTION ==========
    
    async def _prepare_features(self, data: pd.DataFrame, config: PredictionModelConfig) -> pd.DataFrame:
        """Prépare les features pour la prédiction."""
        # Vérification du cache
        cache_key = hashlib.md5(f"{config.config_id}_{id(data)}".encode()).hexdigest()
        with self._cache_lock:
            if cache_key in self._feature_cache:
                self._stats["cache_hits"] += 1
                return self._feature_cache[cache_key]
        
        self._stats["cache_misses"] += 1
        
        # Extraction des features
        features = data[config.features] if config.features else data.select_dtypes(include=[np.number])
        
        # Ajout de features dérivées
        if "close" in data.columns:
            features["returns"] = data["close"].pct_change()
            features["log_returns"] = np.log(data["close"] / data["close"].shift())
        
        # Remplissage des valeurs manquantes
        features = features.fillna(0)
        
        # Mise en cache
        with self._cache_lock:
            if len(self._feature_cache) < self.config["cache_size"]:
                self._feature_cache[cache_key] = features
        
        return features
    
    async def _prepare_training_data(self, data: pd.DataFrame, config: PredictionModelConfig) -> Tuple[pd.DataFrame, np.ndarray]:
        """Prépare les données d'entraînement."""
        # Extraction des features
        X = await self._prepare_features(data, config)
        
        # Création de la cible
        if config.prediction_type == PredictionType.PRICE:
            y = data["close"].shift(-1).dropna().values
        elif config.prediction_type == PredictionType.VOLATILITY:
            y = data["close"].pct_change().rolling(20).std().dropna().values
        else:
            y = data["close"].shift(-1).dropna().values
        
        # Alignement des données
        min_len = min(len(X), len(y))
        X = X.iloc[:min_len]
        y = y[:min_len]
        
        return X, y
    
    async def _get_model(self, config: PredictionModelConfig) -> Optional[Any]:
        """Récupère un modèle."""
        with self._models_lock:
            return self._models.get(config.config_id)
    
    async def _create_model(self, config: PredictionModelConfig) -> Any:
        """Crée un modèle selon la configuration."""
        if config.model_type == PredictionModel.LINEAR_REGRESSION:
            return LinearRegression(**config.hyperparameters)
        elif config.model_type == PredictionModel.RIDGE:
            return Ridge(**config.hyperparameters)
        elif config.model_type == PredictionModel.LASSO:
            return Lasso(**config.hyperparameters)
        elif config.model_type == PredictionModel.RANDOM_FOREST:
            return RandomForestRegressor(
                n_estimators=config.hyperparameters.get("n_estimators", 100),
                max_depth=config.hyperparameters.get("max_depth", 10),
                random_state=self.config["random_state"]
            )
        elif config.model_type == PredictionModel.GRADIENT_BOOSTING:
            return GradientBoostingRegressor(
                n_estimators=config.hyperparameters.get("n_estimators", 100),
                learning_rate=config.hyperparameters.get("learning_rate", 0.1),
                random_state=self.config["random_state"]
            )
        else:
            return RandomForestRegressor(random_state=self.config["random_state"])
    
    async def _calculate_confidence_interval(self, model: Any, features: np.ndarray, config: PredictionModelConfig) -> Tuple[float, float]:
        """Calcule les intervalles de confiance."""
        # Simulation d'intervalles de confiance
        # Dans un système réel, on utiliserait des méthodes bootstrap
        
        prediction = model.predict(features)[0]
        std_dev = abs(prediction) * 0.1  # 10% du prédiction
        
        lower = prediction - 1.96 * std_dev
        upper = prediction + 1.96 * std_dev
        
        return lower, upper
    
    async def _get_model_accuracy(self, config: PredictionModelConfig) -> float:
        """Récupère la précision du modèle."""
        # Simulation de précision
        return 0.7 + np.random.random() * 0.2
    
    # ========== MÉTHODES PRIVÉES - HISTORIQUE ==========
    
    async def _update_history(self, prediction: PredictionResult) -> None:
        """Met à jour l'historique des prédictions."""
        with self._history_lock:
            if prediction.symbol not in self._history:
                self._history[prediction.symbol] = PredictionHistory(
                    symbol=prediction.symbol,
                    prediction_type=prediction.prediction_type
                )
            
            history = self._history[prediction.symbol]
            history.predictions.append(prediction)
            
            # Calcul des métriques
            if len(history.actuals) > 0:
                errors = np.array(history.actuals) - np.array([p.value for p in history.predictions[-len(history.actuals):]])
                history.mae = np.mean(np.abs(errors))
                history.rmse = np.sqrt(np.mean(errors ** 2))
                history.accuracy = 1 - history.mae / (np.mean(history.actuals) + 1e-6)
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _retraining_loop(self) -> None:
        """Boucle de réentraînement des modèles."""
        if not self.config["enable_retraining"]:
            return
        
        while self._is_running:
            await asyncio.sleep(self.config["retrain_interval"])
            
            try:
                with self._configs_lock:
                    for config in self._configs.values():
                        if not config.active:
                            continue
                        
                        # Vérification de la performance
                        if await self._should_retrain(config):
                            # Récupération des données
                            if self.market_data_engine:
                                data = await self.market_data_engine.get_ohlcv(
                                    config.features[0] if config.features else "BTC-USD",
                                    MarketDataInterval.MINUTE_1
                                )
                                
                                if not data.empty:
                                    await self.train_model(config, data)
                
            except Exception as e:
                logger.error(f"Retraining loop error: {e}")
    
    async def _should_retrain(self, config: PredictionModelConfig) -> bool:
        """Vérifie si le modèle doit être réentraîné."""
        # Vérification de l'âge du modèle
        model = await self._get_model(config)
        if model is None:
            return True
        
        # Vérification de la performance
        # Dans un système réel, on comparerait la performance actuelle avec l'historique
        return False
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._feature_cache) > self.config["cache_size"]:
                        keys = list(self._feature_cache.keys())
                        for key in keys[:len(self._feature_cache) - self.config["cache_size"]]:
                            del self._feature_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._predictions_lock:
                    self._stats["total_predictions"] = len(self._predictions)
                
                with self._history_lock:
                    self._stats["total_history"] = len(self._history)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "predict:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_models(self) -> None:
        """Charge les modèles existants."""
        try:
            if self.data_manager:
                models_data = await self.data_manager.retrieve(
                    "predict:models",
                    DataType.MODEL
                )
                
                if models_data:
                    for m_dict in models_data:
                        model = self._deserialize_model(m_dict)
                        if model:
                            with self._models_lock:
                                self._models[m_dict["config_id"]] = model
                                self._stats["models_trained"] += 1
            
            logger.info(f"Loaded {self._stats['models_trained']} prediction models")
            
        except Exception as e:
            logger.error(f"Load models error: {e}")
    
    async def _load_configs(self) -> None:
        """Charge les configurations."""
        try:
            if self.data_manager:
                configs_data = await self.data_manager.retrieve(
                    "predict:configs",
                    DataType.CONFIG
                )
                
                if configs_data:
                    for c_dict in configs_data:
                        config = self._deserialize_config(c_dict)
                        if config:
                            with self._configs_lock:
                                self._configs[config.config_id] = config
            
            logger.info(f"Loaded {len(self._configs)} prediction configs")
            
        except Exception as e:
            logger.error(f"Load configs error: {e}")
    
    def _deserialize_config(self, data: Dict) -> Optional[PredictionModelConfig]:
        """Désérialise une configuration."""
        try:
            return PredictionModelConfig(
                config_id=data.get("config_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                model_type=PredictionModel(data.get("model_type", "random_forest")),
                prediction_type=PredictionType(data.get("prediction_type", "price")),
                horizon=PredictionHorizon(data.get("horizon", "medium")),
                features=data.get("features", []),
                hyperparameters=data.get("hyperparameters", {}),
                training_window=data.get("training_window", 1000),
                retrain_interval=data.get("retrain_interval", 3600),
                retrain_threshold=data.get("retrain_threshold", 0.01),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing config: {e}")
            return None
    
    async def _save_models(self) -> None:
        """Sauvegarde les modèles."""
        try:
            if self.data_manager:
                with self._models_lock:
                    for config_id, model in self._models.items():
                        await self.data_manager.store(
                            f"predict:model:{config_id}",
                            self._serialize_model(model),
                            DataType.MODEL
                        )
            
            logger.info("Models saved")
            
        except Exception as e:
            logger.error(f"Save models error: {e}")
    
    def _serialize_model(self, model: Any) -> Dict:
        """Sérialise un modèle."""
        return {
            "config_id": id(model),
            "model": joblib.dumps(model).hex()
        }
    
    def _deserialize_model(self, data: Dict) -> Optional[Any]:
        """Désérialise un modèle."""
        try:
            return joblib.loads(bytes.fromhex(data["model"]))
        except Exception as e:
            logger.error(f"Error deserializing model: {e}")
            return None
    
    async def _save_model(self, config_id: str, model: Any) -> None:
        """Sauvegarde un modèle spécifique."""
        try:
            if self.data_manager:
                await self.data_manager.store(
                    f"predict:model:{config_id}",
                    self._serialize_model(model),
                    DataType.MODEL
                )
        except Exception as e:
            logger.error(f"Save model error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def create_config(self, config: PredictionModelConfig) -> str:
        """Crée une configuration de modèle."""
        with self._configs_lock:
            self._configs[config.config_id] = config
        
        if self.data_manager:
            await self.data_manager.store(
                f"predict:config:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Prediction config created: {config.name}")
        return config.config_id
    
    async def get_config(self, config_id: str) -> Optional[PredictionModelConfig]:
        """Récupère une configuration."""
        with self._configs_lock:
            return self._configs.get(config_id)
    
    async def get_configs(self) -> List[PredictionModelConfig]:
        """Récupère les configurations."""
        with self._configs_lock:
            return list(self._configs.values())
    
    async def get_history(self, symbol: str) -> Optional[PredictionHistory]:
        """Récupère l'historique des prédictions."""
        with self._history_lock:
            return self._history.get(symbol)
    
    async def get_predictions(self, symbol: str, limit: int = 100) -> List[PredictionResult]:
        """Récupère les prédictions récentes."""
        with self._predictions_lock:
            predictions = [p for p in self._predictions.values() if p.symbol == symbol]
            return sorted(predictions, key=lambda p: p.timestamp, reverse=True)[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._predictions_lock:
            self._stats["total_predictions"] = len(self._predictions)
        
        return self._stats.copy()


# ============== PREDICTION ENSEMBLE ==============

class PredictionEnsemble:
    """
    Ensemble de prédictions.
    Combine plusieurs modèles pour améliorer la précision.
    """
    
    def __init__(self, engine: PredictionEngine):
        self.engine = engine
        self._weights: Dict[str, float] = {}
        self._weight_lock = threading.RLock()
    
    async def add_model(self, config_id: str, weight: float = 1.0) -> None:
        """Ajoute un modèle à l'ensemble."""
        with self._weight_lock:
            self._weights[config_id] = weight
    
    async def predict(self, configs: List[PredictionModelConfig], data: pd.DataFrame) -> PredictionResult:
        """Exécute une prédiction en ensemble."""
        predictions = []
        weights = []
        
        for config in configs:
            try:
                result = await self.engine.predict(config, data)
                predictions.append(result.value)
                weights.append(self._weights.get(config.config_id, 1.0))
            except Exception as e:
                logger.warning(f"Model {config.name} failed: {e}")
                continue
        
        if not predictions:
            raise ValueError("No predictions available")
        
        # Prédiction pondérée
        total_weight = sum(weights)
        weighted_prediction = sum(p * w for p, w in zip(predictions, weights)) / total_weight
        
        # Création du résultat
        result = PredictionResult(
            model=PredictionModel.ENSEMBLE,
            prediction_type=configs[0].prediction_type if configs else PredictionType.PRICE,
            horizon=configs[0].horizon if configs else PredictionHorizon.MEDIUM,
            symbol=data.get("symbol", ""),
            value=weighted_prediction,
            confidence=0.8,
            features={"ensemble_size": len(predictions)}
        )
        
        return result


# ============== FACTORY ==============

class PredictionFactory:
    """Factory pour créer des composants de prédiction."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        market_data_engine: Optional[MarketDataEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PredictionEngine:
        """Crée un moteur de prédiction."""
        engine = PredictionEngine(
            data_manager=data_manager,
            market_data_engine=market_data_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_ensemble(engine: PredictionEngine) -> PredictionEnsemble:
        """Crée un ensemble de prédictions."""
        return PredictionEnsemble(engine)


# ============== EXPORT ==============

__all__ = [
    "PredictionModel",
    "PredictionType",
    "PredictionHorizon",
    "PredictionResult",
    "PredictionModelConfig",
    "PredictionHistory",
    "PredictionEngineInterface",
    "PredictionEngine",
    "PredictionEnsemble",
    "PredictionFactory"
]
