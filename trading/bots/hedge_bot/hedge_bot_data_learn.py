# trading/bots/hedge_bot/hedge_bot_data_learn.py
# Advanced Machine Learning & Adaptive Learning Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Learning Module - Module avancé d'apprentissage automatique et adaptatif pour le Hedge Bot.
Gère l'entraînement des modèles ML, l'apprentissage par renforcement, l'adaptation continue,
le transfer learning et l'optimisation des modèles pour le hedging.
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
import joblib
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge, Lasso, ElasticNet
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_learn")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)


# ============== ENUMS & TYPES ==============

class LearningModelType(Enum):
    """Types de modèles d'apprentissage."""
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    LSTM = "lstm"
    GRU = "gru"
    TRANSFORMER = "transformer"
    DQN = "dqn"
    PPO = "ppo"
    SAC = "sac"
    LINEAR_REGRESSION = "linear_regression"
    RIDGE = "ridge"
    LASSO = "lasso"
    ELASTIC_NET = "elastic_net"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    ENSEMBLE = "ensemble"


class LearningTask(Enum):
    """Tâches d'apprentissage."""
    REGRESSION = "regression"
    CLASSIFICATION = "classification"
    REINFORCEMENT = "reinforcement"
    UNSUPERVISED = "unsupervised"
    TRANSFER = "transfer"
    ONLINE = "online"


class LearningState(Enum):
    """États d'apprentissage."""
    IDLE = "idle"
    TRAINING = "training"
    EVALUATING = "evaluating"
    DEPLOYED = "deployed"
    UPDATING = "updating"
    FAILED = "failed"
    PAUSED = "paused"


# ============== DATA MODELS ==============

@dataclass
class LearningModel:
    """Modèle d'apprentissage."""
    model_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    model_type: LearningModelType = LearningModelType.RANDOM_FOREST
    task: LearningTask = LearningTask.REGRESSION
    features: List[str] = field(default_factory=list)
    target: str = ""
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    state: LearningState = LearningState.IDLE
    accuracy: float = 0.0
    loss: float = 0.0
    train_score: float = 0.0
    test_score: float = 0.0
    val_score: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trained_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    version: int = 1
    model_path: str = ""
    feature_importance: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "model_type": self.model_type.value,
            "task": self.task.value,
            "features": self.features,
            "target": self.target,
            "hyperparameters": self.hyperparameters,
            "state": self.state.value,
            "accuracy": self.accuracy,
            "loss": self.loss,
            "train_score": self.train_score,
            "test_score": self.test_score,
            "val_score": self.val_score,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "trained_at": self.trained_at.isoformat() if self.trained_at else None,
            "metadata": self.metadata,
            "tags": self.tags,
            "active": self.active,
            "version": self.version,
            "model_path": self.model_path,
            "feature_importance": self.feature_importance
        }


@dataclass
class TrainingJob:
    """Job d'entraînement."""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    status: str = "pending"  # pending, running, completed, failed
    progress: float = 0.0
    epochs: int = 0
    batch_size: int = 32
    learning_rate: float = 0.001
    train_size: int = 0
    val_size: int = 0
    test_size: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)


@dataclass
class PredictionResult:
    """Résultat de prédiction."""
    prediction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    input_data: Any = None
    output: Any = None
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class LearningEngineInterface(ABC):
    """Interface abstraite pour le moteur d'apprentissage."""
    
    @abstractmethod
    async def create_model(self, config: Dict[str, Any]) -> LearningModel:
        """Crée un modèle d'apprentissage."""
        pass
    
    @abstractmethod
    async def train_model(self, model_id: str, data: pd.DataFrame) -> TrainingJob:
        """Entraîne un modèle."""
        pass
    
    @abstractmethod
    async def predict(self, model_id: str, data: Any) -> PredictionResult:
        """Exécute une prédiction."""
        pass


# ============== IMPLÉMENTATION ==============

class LearningEngine(LearningEngineInterface):
    """
    Moteur d'apprentissage avancé pour le Hedge Bot.
    Gère les modèles ML, l'entraînement, les prédictions et l'adaptation continue.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des modèles
        self._models: Dict[str, LearningModel] = {}
        self._models_lock = threading.RLock()
        
        # Modèles entraînés (objets)
        self._trained_models: Dict[str, Any] = {}
        self._trained_lock = threading.RLock()
        
        # Scalers
        self._scalers: Dict[str, StandardScaler] = {}
        self._scaler_lock = threading.RLock()
        
        # Gestion des jobs
        self._jobs: Dict[str, TrainingJob] = {}
        self._jobs_lock = threading.RLock()
        
        # Cache des prédictions
        self._prediction_cache: Dict[str, PredictionResult] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "models_created": 0,
            "models_trained": 0,
            "predictions_made": 0,
            "training_jobs": 0,
            "avg_accuracy": 0.0,
            "avg_loss": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # Queue d'entraînement
        self._training_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        
        # État
        self._is_running = False
        
        # Device pour PyTorch
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        logger.info(f"LearningEngine initialized (device={self._device})")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_model_type": LearningModelType.RANDOM_FOREST,
            "default_task": LearningTask.REGRESSION,
            "train_test_split": 0.2,
            "val_split": 0.1,
            "max_epochs": 100,
            "batch_size": 32,
            "learning_rate": 0.001,
            "early_stopping_patience": 10,
            "min_delta": 0.001,
            "cache_size": 1000,
            "cache_ttl": 3600,
            "enable_cache": True,
            "enable_gpu": True,
            "model_dir": "./models",
            "max_models": 100
        }
    
    async def start(self) -> None:
        """Démarre le moteur d'apprentissage."""
        logger.info("LearningEngine starting...")
        self._is_running = True
        
        # Création du dossier des modèles
        Path(self.config["model_dir"]).mkdir(parents=True, exist_ok=True)
        
        # Chargement des modèles existants
        await self._load_models()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._training_processor())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("LearningEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur d'apprentissage."""
        logger.info("LearningEngine stopping...")
        self._is_running = False
        
        # Sauvegarde des modèles
        await self._save_models()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("LearningEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_model(self, config: Dict[str, Any]) -> LearningModel:
        """Crée un modèle d'apprentissage."""
        model = LearningModel(
            name=config.get("name", f"Model_{uuid.uuid4().hex[:8]}"),
            model_type=LearningModelType(config.get("model_type", "random_forest")),
            task=LearningTask(config.get("task", "regression")),
            features=config.get("features", []),
            target=config.get("target", ""),
            hyperparameters=config.get("hyperparameters", {}),
            metadata=config.get("metadata", {}),
            tags=config.get("tags", [])
        )
        
        with self._models_lock:
            self._models[model.model_id] = model
            self._stats["models_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"learn:model:{model.model_id}",
                model.to_dict(),
                DataType.MODEL
            )
        
        logger.info(f"Learning model created: {model.name} (id={model.model_id})")
        return model
    
    async def train_model(self, model_id: str, data: pd.DataFrame) -> TrainingJob:
        """Entraîne un modèle."""
        with self._models_lock:
            model = self._models.get(model_id)
            if not model:
                raise ValueError(f"Model {model_id} not found")
        
        # Création du job
        job = TrainingJob(
            model_id=model_id,
            epochs=self.config["max_epochs"],
            batch_size=self.config["batch_size"],
            learning_rate=self.config["learning_rate"],
            train_size=int(len(data) * (1 - self.config["train_test_split"] - self.config["val_split"])),
            val_size=int(len(data) * self.config["val_split"]),
            test_size=int(len(data) * self.config["train_test_split"])
        )
        
        with self._jobs_lock:
            self._jobs[job.job_id] = job
            self._stats["training_jobs"] += 1
        
        # Mise en queue
        await self._training_queue.put((job.job_id, model_id, data))
        
        return job
    
    async def predict(self, model_id: str, data: Any) -> PredictionResult:
        """Exécute une prédiction."""
        self._stats["predictions_made"] += 1
        
        # Vérification du cache
        cache_key = self._compute_prediction_cache_key(model_id, data)
        if self.config["enable_cache"] and cache_key in self._prediction_cache:
            logger.debug(f"Prediction cache hit: {cache_key}")
            return self._prediction_cache[cache_key]
        
        # Récupération du modèle
        with self._models_lock:
            model = self._models.get(model_id)
            if not model:
                raise ValueError(f"Model {model_id} not found")
        
        # Récupération du modèle entraîné
        with self._trained_lock:
            trained_model = self._trained_models.get(model_id)
            if not trained_model:
                raise ValueError(f"Model {model_id} not trained")
        
        # Prédiction
        if model.model_type in [LearningModelType.RANDOM_FOREST, LearningModelType.GRADIENT_BOOSTING,
                                LearningModelType.XGBOOST, LearningModelType.LIGHTGBM]:
            # Scikit-learn models
            scaler = self._scalers.get(model_id)
            if scaler:
                data_scaled = scaler.transform([data])
            else:
                data_scaled = [data]
            
            prediction = trained_model.predict(data_scaled)[0]
        
        elif model.model_type in [LearningModelType.LSTM, LearningModelType.GRU, LearningModelType.TRANSFORMER]:
            # PyTorch models
            data_tensor = torch.tensor(data, dtype=torch.float32).to(self._device)
            trained_model.eval()
            with torch.no_grad():
                prediction = trained_model(data_tensor).cpu().numpy()[0]
        
        else:
            raise ValueError(f"Unsupported model type: {model.model_type}")
        
        # Calcul de la confiance
        confidence = model.accuracy
        
        # Création du résultat
        result = PredictionResult(
            model_id=model_id,
            input_data=data,
            output=float(prediction),
            confidence=confidence
        )
        
        # Mise en cache
        if self.config["enable_cache"]:
            with self._cache_lock:
                if len(self._prediction_cache) < self.config["cache_size"]:
                    self._prediction_cache[cache_key] = result
        
        return result
    
    # ========== MÉTHODES PRIVÉES - ENTRAÎNEMENT ==========
    
    async def _training_processor(self) -> None:
        """Traite les jobs d'entraînement."""
        while self._is_running:
            try:
                job_id, model_id, data = await self._training_queue.get()
                
                # Exécution de l'entraînement
                asyncio.create_task(self._execute_training(job_id, model_id, data))
                
            except Exception as e:
                logger.error(f"Training processor error: {e}")
                await asyncio.sleep(1)
    
    async def _execute_training(self, job_id: str, model_id: str, data: pd.DataFrame) -> None:
        """Exécute l'entraînement d'un modèle."""
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                return
        
        job.status = "running"
        job.start_time = datetime.now(timezone.utc)
        
        with self._models_lock:
            model = self._models.get(model_id)
            if not model:
                job.status = "failed"
                job.logs.append("Model not found")
                return
        
        try:
            # Préparation des données
            X, y = await self._prepare_data(data, model)
            
            # Split des données
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=self.config["train_test_split"], random_state=42
            )
            X_train, X_val, y_train, y_val = train_test_split(
                X_train, y_train, test_size=self.config["val_split"], random_state=42
            )
            
            # Normalisation
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_val_scaled = scaler.transform(X_val)
            X_test_scaled = scaler.transform(X_test)
            
            with self._scaler_lock:
                self._scalers[model_id] = scaler
            
            # Entraînement selon le type
            if model.model_type == LearningModelType.RANDOM_FOREST:
                trained_model = await self._train_random_forest(X_train_scaled, y_train, model)
            elif model.model_type == LearningModelType.GRADIENT_BOOSTING:
                trained_model = await self._train_gradient_boosting(X_train_scaled, y_train, model)
            elif model.model_type in [LearningModelType.LSTM, LearningModelType.GRU]:
                trained_model = await self._train_rnn(X_train_scaled, y_train, model)
            elif model.model_type == LearningModelType.TRANSFORMER:
                trained_model = await self._train_transformer(X_train_scaled, y_train, model)
            else:
                trained_model = await self._train_default(X_train_scaled, y_train, model)
            
            # Évaluation
            train_score = trained_model.score(X_train_scaled, y_train)
            val_score = trained_model.score(X_val_scaled, y_val)
            test_score = trained_model.score(X_test_scaled, y_test)
            
            # Mise à jour du modèle
            model.train_score = train_score
            model.val_score = val_score
            model.test_score = test_score
            model.accuracy = test_score
            model.loss = 1 - test_score
            model.state = LearningState.DEPLOYED
            model.trained_at = datetime.now(timezone.utc)
            model.updated_at = datetime.now(timezone.utc)
            
            # Feature importance
            if hasattr(trained_model, 'feature_importances_'):
                model.feature_importance = dict(zip(
                    model.features,
                    trained_model.feature_importances_.tolist()
                ))
            
            # Stockage du modèle
            with self._trained_lock:
                self._trained_models[model_id] = trained_model
            
            # Sauvegarde du modèle
            model_path = Path(self.config["model_dir"]) / f"{model_id}.pkl"
            joblib.dump(trained_model, model_path)
            model.model_path = str(model_path)
            
            # Mise à jour du job
            job.status = "completed"
            job.progress = 1.0
            job.end_time = datetime.now(timezone.utc)
            job.logs.append(f"Training completed: train={train_score:.4f}, val={val_score:.4f}, test={test_score:.4f}")
            
            self._stats["models_trained"] += 1
            self._stats["avg_accuracy"] = (
                self._stats["avg_accuracy"] * 0.9 + test_score * 0.1
            )
            
            logger.info(f"Model trained: {model.name} accuracy={test_score:.4f}")
            
        except Exception as e:
            job.status = "failed"
            job.logs.append(f"Training failed: {str(e)}")
            logger.error(f"Training error: {e}")
    
    # ========== MÉTHODES PRIVÉES - PRÉPARATION ==========
    
    async def _prepare_data(self, data: pd.DataFrame, model: LearningModel) -> Tuple[np.ndarray, np.ndarray]:
        """Prépare les données pour l'entraînement."""
        if not model.features:
            model.features = [col for col in data.columns if col != model.target]
        
        X = data[model.features].values
        y = data[model.target].values
        
        return X, y
    
    # ========== MÉTHODES PRIVÉES - MODÈLES ==========
    
    async def _train_random_forest(self, X, y, model: LearningModel) -> Any:
        """Entraîne un Random Forest."""
        params = model.hyperparameters.copy()
        rf = RandomForestRegressor(
            n_estimators=params.get("n_estimators", 100),
            max_depth=params.get("max_depth", 10),
            random_state=42,
            n_jobs=-1
        )
        rf.fit(X, y)
        return rf
    
    async def _train_gradient_boosting(self, X, y, model: LearningModel) -> Any:
        """Entraîne un Gradient Boosting."""
        params = model.hyperparameters.copy()
        gb = GradientBoostingRegressor(
            n_estimators=params.get("n_estimators", 100),
            learning_rate=params.get("learning_rate", 0.1),
            max_depth=params.get("max_depth", 3),
            random_state=42
        )
        gb.fit(X, y)
        return gb
    
    async def _train_rnn(self, X, y, model: LearningModel) -> Any:
        """Entraîne un RNN (LSTM/GRU)."""
        import torch.nn as nn
        
        # Préparation des données séquentielles
        sequence_length = min(10, len(X) // 2)
        X_seq, y_seq = [], []
        
        for i in range(len(X) - sequence_length):
            X_seq.append(X[i:i+sequence_length])
            y_seq.append(y[i+sequence_length])
        
        X_tensor = torch.tensor(np.array(X_seq), dtype=torch.float32).to(self._device)
        y_tensor = torch.tensor(np.array(y_seq), dtype=torch.float32).to(self._device)
        
        # Définition du modèle
        class RNNModel(nn.Module):
            def __init__(self, input_size, hidden_size=64, num_layers=2, rnn_type='lstm'):
                super().__init__()
                if rnn_type == 'lstm':
                    self.rnn = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
                else:
                    self.rnn = nn.GRU(input_size, hidden_size, num_layers, batch_first=True)
                self.fc = nn.Linear(hidden_size, 1)
            
            def forward(self, x):
                out, _ = self.rnn(x)
                return self.fc(out[:, -1, :])
        
        rnn_model = RNNModel(
            input_size=X.shape[1],
            hidden_size=model.hyperparameters.get("hidden_size", 64),
            num_layers=model.hyperparameters.get("num_layers", 2),
            rnn_type='lstm' if model.model_type == LearningModelType.LSTM else 'gru'
        ).to(self._device)
        
        # Entraînement
        optimizer = optim.Adam(rnn_model.parameters(), lr=self.config["learning_rate"])
        criterion = nn.MSELoss()
        
        dataset = TensorDataset(X_tensor, y_tensor)
        dataloader = DataLoader(dataset, batch_size=self.config["batch_size"], shuffle=True)
        
        for epoch in range(self.config["max_epochs"]):
            for batch_X, batch_y in dataloader:
                optimizer.zero_grad()
                output = rnn_model(batch_X)
                loss = criterion(output.squeeze(), batch_y)
                loss.backward()
                optimizer.step()
        
        return rnn_model
    
    async def _train_transformer(self, X, y, model: LearningModel) -> Any:
        """Entraîne un Transformer."""
        # Placeholder pour Transformer
        # Dans un système réel, on implémenterait un modèle Transformer
        return await self._train_random_forest(X, y, model)
    
    async def _train_default(self, X, y, model: LearningModel) -> Any:
        """Modèle par défaut."""
        return await self._train_random_forest(X, y, model)
    
    # ========== MÉTHODES PRIVÉES - CACHE ==========
    
    def _compute_prediction_cache_key(self, model_id: str, data: Any) -> str:
        """Calcule une clé de cache pour les prédictions."""
        data_str = json.dumps(data, sort_keys=True) if isinstance(data, dict) else str(data)
        return hashlib.md5(f"{model_id}:{data_str}".encode()).hexdigest()
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._prediction_cache) > self.config["cache_size"]:
                        keys = list(self._prediction_cache.keys())
                        for key in keys[:len(self._prediction_cache) - self.config["cache_size"]]:
                            del self._prediction_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_models(self) -> None:
        """Charge les modèles existants."""
        try:
            if self.data_manager:
                models_data = await self.data_manager.retrieve(
                    "learn:models",
                    DataType.MODEL
                )
                
                if models_data:
                    for model_dict in models_data:
                        model = self._deserialize_model(model_dict)
                        if model:
                            with self._models_lock:
                                self._models[model.model_id] = model
                            
                            # Chargement du modèle entraîné
                            model_path = Path(self.config["model_dir"]) / f"{model.model_id}.pkl"
                            if model_path.exists():
                                trained_model = joblib.load(model_path)
                                with self._trained_lock:
                                    self._trained_models[model.model_id] = trained_model
            
            logger.info(f"Loaded {len(self._models)} learning models")
            
        except Exception as e:
            logger.error(f"Load models error: {e}")
    
    async def _save_models(self) -> None:
        """Sauvegarde les modèles."""
        try:
            for model_id, model in self._models.items():
                if self.data_manager:
                    await self.data_manager.store(
                        f"learn:model:{model_id}",
                        model.to_dict(),
                        DataType.MODEL
                    )
            
            logger.info("Models saved")
            
        except Exception as e:
            logger.error(f"Save models error: {e}")
    
    def _deserialize_model(self, data: Dict) -> Optional[LearningModel]:
        """Désérialise un modèle."""
        try:
            return LearningModel(
                model_id=data.get("model_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                model_type=LearningModelType(data.get("model_type", "random_forest")),
                task=LearningTask(data.get("task", "regression")),
                features=data.get("features", []),
                target=data.get("target", ""),
                hyperparameters=data.get("hyperparameters", {}),
                state=LearningState(data.get("state", "idle")),
                accuracy=data.get("accuracy", 0.0),
                loss=data.get("loss", 0.0),
                train_score=data.get("train_score", 0.0),
                test_score=data.get("test_score", 0.0),
                val_score=data.get("val_score", 0.0),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                trained_at=datetime.fromisoformat(data.get("trained_at")) if data.get("trained_at") else None,
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True),
                version=data.get("version", 1),
                model_path=data.get("model_path", ""),
                feature_importance=data.get("feature_importance", {})
            )
        except Exception as e:
            logger.error(f"Error deserializing model: {e}")
            return None
    
    # ========== MÉTHODES DE MAINTENANCE ==========
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._models_lock:
                    self._stats["total_models"] = len(self._models)
                    active_models = len([m for m in self._models.values() if m.state == LearningState.DEPLOYED])
                    self._stats["active_models"] = active_models
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "learn:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_model(self, model_id: str) -> Optional[LearningModel]:
        """Récupère un modèle."""
        with self._models_lock:
            return self._models.get(model_id)
    
    async def get_models(self, state: Optional[LearningState] = None) -> List[LearningModel]:
        """Récupère les modèles."""
        with self._models_lock:
            models = list(self._models.values())
            if state:
                models = [m for m in models if m.state == state]
            return models
    
    async def get_job(self, job_id: str) -> Optional[TrainingJob]:
        """Récupère un job d'entraînement."""
        with self._jobs_lock:
            return self._jobs.get(job_id)
    
    async def get_jobs(self) -> List[TrainingJob]:
        """Récupère les jobs d'entraînement."""
        with self._jobs_lock:
            return list(self._jobs.values())
    
    async def cancel_training(self, job_id: str) -> bool:
        """Annule un job d'entraînement."""
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job or job.status in ["completed", "failed"]:
                return False
            
            job.status = "cancelled"
            job.end_time = datetime.now(timezone.utc)
            job.logs.append("Training cancelled")
            return True
    
    async def delete_model(self, model_id: str) -> bool:
        """Supprime un modèle."""
        with self._models_lock:
            if model_id not in self._models:
                return False
            
            del self._models[model_id]
        
        # Suppression du modèle entraîné
        with self._trained_lock:
            if model_id in self._trained_models:
                del self._trained_models[model_id]
        
        # Suppression du scaler
        with self._scaler_lock:
            if model_id in self._scalers:
                del self._scalers[model_id]
        
        # Suppression du fichier
        model_path = Path(self.config["model_dir"]) / f"{model_id}.pkl"
        if model_path.exists():
            model_path.unlink()
        
        logger.info(f"Model deleted: {model_id}")
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._models_lock:
            self._stats["models"] = len(self._models)
        with self._jobs_lock:
            self._stats["jobs"] = len(self._jobs)
        
        return self._stats.copy()


# ============== FACTORY ==============

class LearningFactory:
    """Factory pour créer des composants d'apprentissage."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> LearningEngine:
        """Crée un moteur d'apprentissage."""
        engine = LearningEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "LearningModelType",
    "LearningTask",
    "LearningState",
    "LearningModel",
    "TrainingJob",
    "PredictionResult",
    "LearningEngineInterface",
    "LearningEngine",
    "LearningFactory"
]
