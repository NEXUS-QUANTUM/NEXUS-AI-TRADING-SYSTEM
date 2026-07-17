"""
NEXUS AI TRADING SYSTEM - Base Model for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/models/base_model.py
Description: Classe de base pour tous les modèles AI du bot.
             Définit l'interface standard pour l'entraînement, l'inférence,
             la sauvegarde, le chargement et l'évaluation des modèles.
             Supporte PyTorch, TensorFlow, XGBoost et scikit-learn.
"""

import logging
import os
import json
import time
import hashlib
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
import pandas as pd

from shared.exceptions import ModelError
from shared.helpers.number_helpers import round_decimal
from shared.helpers.date_helpers import timestamp_to_datetime

# Configuration du logging
logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Types de modèles supportés."""
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    XGBOOST = "xgboost"
    SKLEARN = "sklearn"
    LIGHTGBM = "lightgbm"
    CATBOOST = "catboost"
    ONNX = "onnx"
    CUSTOM = "custom"


class ModelTask(Enum):
    """Tâches des modèles."""
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    FORECASTING = "forecasting"
    REINFORCEMENT = "reinforcement"
    ANOMALY_DETECTION = "anomaly_detection"
    CLUSTERING = "clustering"
    ENSEMBLE = "ensemble"


@dataclass
class ModelConfig:
    """
    Configuration de base d'un modèle.
    """
    # Identifiants
    name: str = ""
    model_type: ModelType = ModelType.PYTORCH
    task: ModelTask = ModelTask.FORECASTING
    version: str = "1.0.0"
    
    # Paramètres
    params: Dict[str, Any] = field(default_factory=dict)
    
    # Données
    input_shape: Optional[Tuple[int, ...]] = None
    output_shape: Optional[Tuple[int, ...]] = None
    
    # Entraînement
    batch_size: int = 32
    epochs: int = 100
    learning_rate: float = 0.001
    validation_split: float = 0.2
    early_stopping: bool = True
    patience: int = 10
    
    # Hardware
    device: str = "cpu"  # 'cpu' ou 'cuda'
    use_gpu: bool = False
    
    # Sauvegarde
    checkpoint_dir: str = "data/models/checkpoints/"
    save_best: bool = True
    save_frequency: int = 10
    
    # Métadonnées
    description: str = ""
    author: str = "NEXUS QUANTUM LTD"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validation des paramètres."""
        if not self.name:
            self.name = self.__class__.__name__
        
        if self.batch_size < 1:
            raise ModelError("batch_size doit être >= 1")
        
        if self.epochs < 1:
            raise ModelError("epochs doit être >= 1")
        
        if self.learning_rate <= 0:
            raise ModelError("learning_rate doit être > 0")
        
        if self.validation_split < 0 or self.validation_split >= 1:
            raise ModelError("validation_split doit être entre 0 et 1")
        
        # Création du répertoire de checkpoints
        Path(self.checkpoint_dir).mkdir(parents=True, exist_ok=True)


@dataclass
class ModelMetrics:
    """
    Métriques d'un modèle.
    """
    # Métriques d'entraînement
    train_loss: List[float] = field(default_factory=list)
    train_accuracy: List[float] = field(default_factory=list)
    val_loss: List[float] = field(default_factory=list)
    val_accuracy: List[float] = field(default_factory=list)
    
    # Métriques de performance
    inference_time_ms: float = 0.0
    training_time_s: float = 0.0
    total_epochs: int = 0
    
    # Métriques de qualité
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    loss: float = 0.0
    mae: float = 0.0
    mse: float = 0.0
    r2_score: float = 0.0
    
    # Métriques de prédiction
    prediction_count: int = 0
    correct_predictions: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'train_loss': self.train_loss[-10:] if self.train_loss else [],  # Limiter
            'train_accuracy': self.train_accuracy[-10:] if self.train_accuracy else [],
            'val_loss': self.val_loss[-10:] if self.val_loss else [],
            'val_accuracy': self.val_accuracy[-10:] if self.val_accuracy else [],
            'inference_time_ms': round(self.inference_time_ms, 4),
            'training_time_s': round(self.training_time_s, 4),
            'total_epochs': self.total_epochs,
            'accuracy': round(self.accuracy, 4),
            'precision': round(self.precision, 4),
            'recall': round(self.recall, 4),
            'f1_score': round(self.f1_score, 4),
            'loss': round(self.loss, 6),
            'mae': round(self.mae, 4),
            'mse': round(self.mse, 4),
            'r2_score': round(self.r2_score, 4),
            'prediction_count': self.prediction_count,
            'correct_predictions': self.correct_predictions,
            'false_positives': self.false_positives,
            'false_negatives': self.false_negatives
        }


@dataclass
class PredictionResult:
    """
    Résultat de prédiction.
    """
    # Prédictions
    predictions: np.ndarray
    probabilities: Optional[np.ndarray] = None
    confidence: Optional[float] = None
    
    # Métadonnées
    timestamp: datetime = field(default_factory=datetime.now)
    input_shape: Tuple[int, ...] = (0,)
    inference_time_ms: float = 0.0
    
    # Métriques
    is_valid: bool = True
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'predictions': self.predictions.tolist() if self.predictions is not None else [],
            'probabilities': self.probabilities.tolist() if self.probabilities is not None else [],
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'inference_time_ms': round(self.inference_time_ms, 4),
            'is_valid': self.is_valid,
            'error': self.error
        }


class BaseModel(ABC):
    """
    Classe de base pour tous les modèles AI.
    """
    
    def __init__(self, config: ModelConfig):
        """
        Initialise le modèle.
        
        Args:
            config: Configuration du modèle.
        """
        self.config = config
        self.metrics = ModelMetrics()
        self._is_trained = False
        self._is_loaded = False
        
        # Vérification du device
        if self.config.use_gpu:
            self._check_gpu()
        
        logger.info(f"BaseModel initialisé: {self.config.name}")
        logger.info(f"Type: {self.config.model_type.value}, Task: {self.config.task.value}")
        logger.info(f"Device: {self.config.device}")
    
    def _check_gpu(self) -> None:
        """
        Vérifie la disponibilité GPU.
        """
        try:
            import torch
            if torch.cuda.is_available():
                self.config.device = "cuda"
                logger.info("GPU disponible, utilisation de CUDA")
            else:
                logger.warning("GPU non disponible, utilisation CPU")
                self.config.device = "cpu"
        except ImportError:
            logger.warning("PyTorch non installé, utilisation CPU")
            self.config.device = "cpu"
    
    # ============================================================
    # MÉTHODES ABSTRAITES
    # ============================================================
    
    @abstractmethod
    def build(self, input_shape: Tuple[int, ...]) -> None:
        """
        Construit l'architecture du modèle.
        
        Args:
            input_shape: Forme des données d'entrée.
        """
        pass
    
    @abstractmethod
    def train(
        self,
        X_train: Union[np.ndarray, pd.DataFrame],
        y_train: Union[np.ndarray, pd.DataFrame],
        X_val: Optional[Union[np.ndarray, pd.DataFrame]] = None,
        y_val: Optional[Union[np.ndarray, pd.DataFrame]] = None
    ) -> ModelMetrics:
        """
        Entraîne le modèle.
        
        Args:
            X_train: Données d'entraînement.
            y_train: Labels d'entraînement.
            X_val: Données de validation.
            y_val: Labels de validation.
            
        Returns:
            Métriques d'entraînement.
        """
        pass
    
    @abstractmethod
    def predict(
        self,
        X: Union[np.ndarray, pd.DataFrame]
    ) -> PredictionResult:
        """
        Effectue une prédiction.
        
        Args:
            X: Données à prédire.
            
        Returns:
            Résultat de la prédiction.
        """
        pass
    
    @abstractmethod
    def save(self, filepath: str) -> None:
        """
        Sauvegarde le modèle.
        
        Args:
            filepath: Chemin de sauvegarde.
        """
        pass
    
    @abstractmethod
    def load(self, filepath: str) -> None:
        """
        Charge le modèle.
        
        Args:
            filepath: Chemin de chargement.
        """
        pass
    
    @abstractmethod
    def get_params(self) -> Dict[str, Any]:
        """
        Retourne les paramètres du modèle.
        
        Returns:
            Paramètres du modèle.
        """
        pass
    
    # ============================================================
    # MÉTHODES CONCRÈTES
    # ============================================================
    
    def evaluate(
        self,
        X_test: Union[np.ndarray, pd.DataFrame],
        y_test: Union[np.ndarray, pd.DataFrame]
    ) -> ModelMetrics:
        """
        Évalue le modèle sur des données de test.
        
        Args:
            X_test: Données de test.
            y_test: Labels de test.
            
        Returns:
            Métriques d'évaluation.
        """
        if not self._is_trained and not self._is_loaded:
            raise ModelError("Modèle non entraîné ou chargé")
        
        logger.info(f"Évaluation du modèle {self.config.name}")
        
        start_time = time.time()
        
        # Prédiction
        result = self.predict(X_test)
        
        # Calcul des métriques
        y_pred = result.predictions
        y_true = self._to_array(y_test)
        
        metrics = self._calculate_metrics(y_true, y_pred)
        metrics.inference_time_ms = result.inference_time_ms
        metrics.prediction_count = len(y_true)
        
        self.metrics = metrics
        
        logger.info(f"Évaluation terminée: Accuracy={metrics.accuracy:.4f}")
        
        return metrics
    
    def _calculate_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> ModelMetrics:
        """
        Calcule les métriques d'évaluation.
        
        Args:
            y_true: Valeurs réelles.
            y_pred: Valeurs prédites.
            
        Returns:
            Métriques d'évaluation.
        """
        metrics = ModelMetrics()
        
        if len(y_true) == 0:
            return metrics
        
        # Pour la régression
        if self.config.task in [ModelTask.REGRESSION, ModelTask.FORECASTING]:
            metrics.mae = np.mean(np.abs(y_true - y_pred))
            metrics.mse = np.mean((y_true - y_pred) ** 2)
            metrics.r2_score = 1 - (np.sum((y_true - y_pred) ** 2) / np.sum((y_true - np.mean(y_true)) ** 2))
            metrics.loss = metrics.mse
        
        # Pour la classification
        else:
            # Conversion en classes si nécessaire
            if len(y_pred.shape) > 1 and y_pred.shape[1] > 1:
                y_pred = np.argmax(y_pred, axis=1)
            
            if len(y_true.shape) > 1 and y_true.shape[1] > 1:
                y_true = np.argmax(y_true, axis=1)
            
            # Métriques de classification
            metrics.accuracy = np.mean(y_true == y_pred)
            
            # Matrice de confusion
            from sklearn.metrics import confusion_matrix
            cm = confusion_matrix(y_true, y_pred)
            
            if cm.shape[0] == 2:  # Binaire
                tp = cm[1, 1]
                tn = cm[0, 0]
                fp = cm[0, 1]
                fn = cm[1, 0]
                
                metrics.precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                metrics.recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                metrics.f1_score = 2 * (metrics.precision * metrics.recall) / (metrics.precision + metrics.recall) if (metrics.precision + metrics.recall) > 0 else 0
                metrics.false_positives = fp
                metrics.false_negatives = fn
                metrics.correct_predictions = tp + tn
        
        return metrics
    
    def _to_array(self, data: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """
        Convertit les données en array numpy.
        
        Args:
            data: Données à convertir.
            
        Returns:
            Array numpy.
        """
        if isinstance(data, pd.DataFrame):
            return data.values
        return np.array(data)
    
    def save_checkpoint(
        self,
        epoch: int,
        metrics: Optional[ModelMetrics] = None,
        is_best: bool = False
    ) -> str:
        """
        Sauvegarde un checkpoint du modèle.
        
        Args:
            epoch: Époque actuelle.
            metrics: Métriques du modèle.
            is_best: Si c'est le meilleur modèle.
            
        Returns:
            Chemin du checkpoint.
        """
        checkpoint_path = Path(self.config.checkpoint_dir) / f"{self.config.name}_epoch_{epoch}"
        
        if is_best:
            checkpoint_path = Path(self.config.checkpoint_dir) / f"{self.config.name}_best"
        
        checkpoint_path = str(checkpoint_path) + ".pth"
        
        # Sauvegarde
        self.save(checkpoint_path)
        
        # Sauvegarde des métadonnées
        metadata = {
            'name': self.config.name,
            'version': self.config.version,
            'epoch': epoch,
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics.to_dict() if metrics else {}
        }
        
        metadata_path = checkpoint_path.replace('.pth', '_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Checkpoint sauvegardé: {checkpoint_path}")
        
        return checkpoint_path
    
    def load_checkpoint(self, filepath: str) -> Dict[str, Any]:
        """
        Charge un checkpoint.
        
        Args:
            filepath: Chemin du checkpoint.
            
        Returns:
            Métadonnées du checkpoint.
        """
        # Chargement du modèle
        self.load(filepath)
        
        # Chargement des métadonnées
        metadata_path = filepath.replace('.pth', '_metadata.json')
        metadata = {}
        
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        
        logger.info(f"Checkpoint chargé: {filepath}")
        
        return metadata
    
    def get_checkpoints(self) -> List[Dict[str, Any]]:
        """
        Liste les checkpoints disponibles.
        
        Returns:
            Liste des checkpoints.
        """
        checkpoints = []
        pattern = f"{self.config.name}_*.pth"
        
        for filepath in Path(self.config.checkpoint_dir).glob(pattern):
            stats = os.stat(filepath)
            checkpoints.append({
                'path': str(filepath),
                'name': filepath.stem,
                'size_mb': round(stats.st_size / (1024 * 1024), 2),
                'modified': datetime.fromtimestamp(stats.st_mtime)
            })
        
        return sorted(checkpoints, key=lambda x: x['modified'], reverse=True)
    
    def get_best_checkpoint(self) -> Optional[str]:
        """
        Retourne le meilleur checkpoint.
        
        Returns:
            Chemin du meilleur checkpoint ou None.
        """
        best_path = Path(self.config.checkpoint_dir) / f"{self.config.name}_best.pth"
        if best_path.exists():
            return str(best_path)
        return None
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    def get_name(self) -> str:
        """Retourne le nom du modèle."""
        return self.config.name
    
    def get_version(self) -> str:
        """Retourne la version du modèle."""
        return self.config.version
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques du modèle."""
        return self.metrics.to_dict()
    
    def is_trained(self) -> bool:
        """Vérifie si le modèle est entraîné."""
        return self._is_trained
    
    def is_loaded(self) -> bool:
        """Vérifie si le modèle est chargé."""
        return self._is_loaded
    
    def reset(self) -> None:
        """
        Réinitialise le modèle.
        """
        self._is_trained = False
        self._is_loaded = False
        self.metrics = ModelMetrics()
        logger.info(f"Modèle {self.config.name} réinitialisé")
    
    def summary(self) -> str:
        """
        Retourne un résumé du modèle.
        
        Returns:
            Résumé du modèle.
        """
        lines = []
        lines.append("=" * 60)
        lines.append(f"MODEL: {self.config.name}")
        lines.append("=" * 60)
        lines.append(f"Type: {self.config.model_type.value}")
        lines.append(f"Task: {self.config.task.value}")
        lines.append(f"Version: {self.config.version}")
        lines.append(f"Device: {self.config.device}")
        lines.append(f"Trained: {self._is_trained}")
        lines.append(f"Loaded: {self._is_loaded}")
        lines.append("")
        lines.append("PARAMETERS:")
        for key, value in self.get_params().items():
            lines.append(f"  {key}: {value}")
        lines.append("")
        lines.append("METRICS:")
        for key, value in self.metrics.to_dict().items():
            if isinstance(value, (int, float)):
                lines.append(f"  {key}: {value:.4f}")
            else:
                lines.append(f"  {key}: {value}")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convertit le modèle en dictionnaire.
        
        Returns:
            Dictionnaire du modèle.
        """
        return {
            'name': self.config.name,
            'type': self.config.model_type.value,
            'task': self.config.task.value,
            'version': self.config.version,
            'params': self.get_params(),
            'metrics': self.metrics.to_dict(),
            'is_trained': self._is_trained,
            'is_loaded': self._is_loaded,
            'device': self.config.device,
            'description': self.config.description,
            'author': self.config.author
        }
    
    def to_json(self) -> str:
        """
        Convertit le modèle en JSON.
        
        Returns:
            JSON du modèle.
        """
        return json.dumps(self.to_dict(), indent=2, default=str)


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def validate_model(model: BaseModel) -> bool:
    """
    Valide un modèle.
    
    Args:
        model: Modèle à valider.
        
    Returns:
        True si valide.
    """
    if model is None:
        return False
    
    # Vérification des méthodes
    required_methods = ['build', 'train', 'predict', 'save', 'load', 'get_params']
    for method in required_methods:
        if not hasattr(model, method):
            return False
    
    return True


def compare_models(
    model1: BaseModel,
    model2: BaseModel,
    X_test: Union[np.ndarray, pd.DataFrame],
    y_test: Union[np.ndarray, pd.DataFrame]
) -> Dict[str, Any]:
    """
    Compare deux modèles.
    
    Args:
        model1: Premier modèle.
        model2: Deuxième modèle.
        X_test: Données de test.
        y_test: Labels de test.
        
    Returns:
        Résultats de la comparaison.
    """
    metrics1 = model1.evaluate(X_test, y_test)
    metrics2 = model2.evaluate(X_test, y_test)
    
    return {
        'model1': {
            'name': model1.get_name(),
            'metrics': metrics1.to_dict()
        },
        'model2': {
            'name': model2.get_name(),
            'metrics': metrics2.to_dict()
        },
        'comparison': {
            'accuracy_diff': metrics1.accuracy - metrics2.accuracy,
            'loss_diff': metrics1.loss - metrics2.loss,
            'inference_time_diff': metrics1.inference_time_ms - metrics2.inference_time_ms
        }
    }


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'BaseModel',
    'ModelConfig',
    'ModelMetrics',
    'PredictionResult',
    'ModelType',
    'ModelTask',
    'validate_model',
    'compare_models'
]

# ============================================================
# FIN DU FICHIER
# ============================================================
