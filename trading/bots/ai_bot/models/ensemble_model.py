"""
NEXUS AI TRADING SYSTEM - Ensemble Model for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/models/ensemble_model.py
Description: Modèle d'ensemble pour le bot AI.
             Supporte le stacking, le bagging, le boosting,
             le voting (hard/soft) et les ensembles pondérés.
             Intègre des modèles de différents frameworks
             (PyTorch, XGBoost, scikit-learn, etc.)
"""

import asyncio
import logging
import time
import json
import pickle
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from trading.bots.ai_bot.models.base_model import (
    BaseModel,
    ModelConfig,
    ModelMetrics,
    PredictionResult,
    ModelType,
    ModelTask
)
from trading.bots.ai_bot.models.model_factory import ModelFactory
from shared.exceptions import ModelError

# Configuration du logging
logger = logging.getLogger(__name__)


class EnsembleMethod(Enum):
    """Méthodes d'ensemble."""
    VOTING = "voting"              # Vote (hard/soft)
    AVERAGE = "average"            # Moyenne
    WEIGHTED = "weighted"          # Moyenne pondérée
    STACKING = "stacking"          # Stacking
    BAGGING = "bagging"            # Bagging (Bootstrap Aggregating)
    BOOSTING = "boosting"          # Boosting
    RANDOM_FOREST = "random_forest" # Random Forest
    GRADIENT_BOOSTING = "gradient_boosting" # Gradient Boosting


class EnsembleMode(Enum):
    """Modes d'ensemble."""
    PARALLEL = "parallel"          # Parallèle
    SEQUENTIAL = "sequential"      # Séquentiel
    CASCADE = "cascade"            # Cascade
    HIERARCHICAL = "hierarchical"  # Hiérarchique


@dataclass
class EnsembleConfig(ModelConfig):
    """
    Configuration du modèle d'ensemble.
    """
    # Méthode d'ensemble
    ensemble_method: EnsembleMethod = EnsembleMethod.VOTING
    ensemble_mode: EnsembleMode = EnsembleMode.PARALLEL
    
    # Modèles membres
    member_models: List[Dict[str, Any]] = field(default_factory=list)
    member_weights: Optional[List[float]] = None
    
    # Paramètres de vote
    voting_type: str = "soft"  # 'hard' ou 'soft'
    vote_threshold: float = 0.5
    
    # Paramètres de stacking
    stacking_meta_model: Optional[str] = None
    stacking_meta_params: Dict[str, Any] = field(default_factory=dict)
    stacking_cv_folds: int = 5
    
    # Paramètres de bagging
    bagging_samples: int = 100
    bagging_features: Optional[int] = None
    bagging_bootstrap: bool = True
    
    # Paramètres de boosting
    boosting_rounds: int = 100
    boosting_learning_rate: float = 0.1
    
    # Paramètres d'exécution
    parallel: bool = True
    max_workers: int = 4
    use_gpu: bool = False
    
    def __post_init__(self):
        """Validation des paramètres."""
        super().__post_init__()
        
        if self.ensemble_method == EnsembleMethod.VOTING:
            if not self.member_models:
                raise ModelError("Au moins un modèle membre requis pour le voting")
        
        if self.ensemble_method == EnsembleMethod.STACKING:
            if not self.stacking_meta_model:
                raise ModelError("Méta-modèle requis pour le stacking")
        
        if self.member_weights:
            if len(self.member_weights) != len(self.member_models):
                raise ModelError("Nombre de poids différent du nombre de modèles")


@dataclass
class EnsembleMetrics(ModelMetrics):
    """
    Métriques du modèle d'ensemble.
    """
    # Métriques des membres
    member_metrics: Dict[str, ModelMetrics] = field(default_factory=dict)
    
    # Métriques d'ensemble
    ensemble_method: str = ""
    n_members: int = 0
    diversity_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        data = super().to_dict()
        data.update({
            'ensemble_method': self.ensemble_method,
            'n_members': self.n_members,
            'diversity_score': round(self.diversity_score, 4),
            'member_metrics': {
                k: v.to_dict() for k, v in self.member_metrics.items()
            }
        })
        return data


class EnsembleModel(BaseModel):
    """
    Modèle d'ensemble pour le trading.
    """
    
    def __init__(self, config: EnsembleConfig):
        """
        Initialise le modèle d'ensemble.
        
        Args:
            config: Configuration du modèle d'ensemble.
        """
        super().__init__(config)
        self.ensemble_config = config
        
        # Membres de l'ensemble
        self._members: List[BaseModel] = []
        self._member_names: List[str] = []
        self._member_weights: List[float] = []
        self._meta_model: Optional[BaseModel] = None
        
        # Pour le stacking
        self._stacking_features: Optional[np.ndarray] = None
        
        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=config.max_workers)
        
        logger.info(f"EnsembleModel initialisé: {config.ensemble_method.value}")
        logger.info(f"Mode: {config.ensemble_mode.value}")
        logger.info(f"Nombre de membres: {len(config.member_models)}")
    
    # ============================================================
    # CONSTRUCTION DE L'ENSEMBLE
    # ============================================================
    
    def build(self, input_shape: Tuple[int, ...]) -> None:
        """
        Construit l'ensemble de modèles.
        
        Args:
            input_shape: Forme des données d'entrée.
        """
        logger.info(f"Construction de l'ensemble avec input_shape={input_shape}")
        
        self.config.input_shape = input_shape
        
        # Construction des membres
        for member_config in self.ensemble_config.member_models:
            try:
                # Création du modèle membre
                model = ModelFactory.create(
                    name=member_config.get('name', ''),
                    model_type=member_config.get('type', 'pytorch'),
                    task=self.config.task,
                    params=member_config.get('params', {})
                )
                
                # Construction du modèle
                model.build(input_shape)
                
                # Ajout à la liste
                self._members.append(model)
                self._member_names.append(model.get_name())
                
                logger.info(f"Membre ajouté: {model.get_name()}")
                
            except Exception as e:
                logger.error(f"Erreur de construction du membre {member_config}: {e}")
                raise ModelError(f"Erreur de construction du membre: {e}")
        
        # Poids des membres
        if self.ensemble_config.member_weights:
            self._member_weights = self.ensemble_config.member_weights
        else:
            self._member_weights = [1.0 / len(self._members)] * len(self._members)
        
        # Construction du méta-modèle pour le stacking
        if self.ensemble_config.ensemble_method == EnsembleMethod.STACKING:
            self._build_meta_model(input_shape)
        
        self._is_built = True
        logger.info(f"Ensemble construit avec {len(self._members)} membres")
    
    def _build_meta_model(self, input_shape: Tuple[int, ...]) -> None:
        """
        Construit le méta-modèle pour le stacking.
        
        Args:
            input_shape: Forme des données d'entrée.
        """
        if not self.ensemble_config.stacking_meta_model:
            raise ModelError("Méta-modèle requis pour le stacking")
        
        # Création du méta-modèle
        meta_config = ModelConfig(
            name=f"{self.config.name}_meta",
            model_type=ModelType(self.ensemble_config.stacking_meta_model),
            task=self.config.task,
            params=self.ensemble_config.stacking_meta_params
        )
        
        # Utilisation de ModelFactory pour créer le méta-modèle
        try:
            self._meta_model = ModelFactory.create_from_config(meta_config)
            self._meta_model.build(input_shape)
            logger.info(f"Méta-modèle construit: {self._meta_model.get_name()}")
        except Exception as e:
            logger.error(f"Erreur de construction du méta-modèle: {e}")
            raise ModelError(f"Erreur de construction du méta-modèle: {e}")
    
    # ============================================================
    # ENTRAÎNEMENT
    # ============================================================
    
    def train(
        self,
        X_train: Union[np.ndarray, pd.DataFrame],
        y_train: Union[np.ndarray, pd.DataFrame],
        X_val: Optional[Union[np.ndarray, pd.DataFrame]] = None,
        y_val: Optional[Union[np.ndarray, pd.DataFrame]] = None
    ) -> EnsembleMetrics:
        """
        Entraîne l'ensemble de modèles.
        
        Args:
            X_train: Données d'entraînement.
            y_train: Labels d'entraînement.
            X_val: Données de validation.
            y_val: Labels de validation.
            
        Returns:
            Métriques d'entraînement.
        """
        logger.info(f"Entraînement de l'ensemble avec {len(self._members)} membres")
        
        start_time = time.time()
        
        # Conversion en numpy
        X_train = self._to_array(X_train)
        y_train = self._to_array(y_train)
        
        if X_val is not None:
            X_val = self._to_array(X_val)
        if y_val is not None:
            y_val = self._to_array(y_val)
        
        # Entraînement selon la méthode
        if self.ensemble_config.ensemble_method == EnsembleMethod.VOTING:
            metrics = self._train_voting(X_train, y_train, X_val, y_val)
        elif self.ensemble_config.ensemble_method == EnsembleMethod.AVERAGE:
            metrics = self._train_average(X_train, y_train, X_val, y_val)
        elif self.ensemble_config.ensemble_method == EnsembleMethod.WEIGHTED:
            metrics = self._train_weighted(X_train, y_train, X_val, y_val)
        elif self.ensemble_config.ensemble_method == EnsembleMethod.STACKING:
            metrics = self._train_stacking(X_train, y_train, X_val, y_val)
        elif self.ensemble_config.ensemble_method == EnsembleMethod.BAGGING:
            metrics = self._train_bagging(X_train, y_train, X_val, y_val)
        elif self.ensemble_config.ensemble_method == EnsembleMethod.BOOSTING:
            metrics = self._train_boosting(X_train, y_train, X_val, y_val)
        else:
            raise ModelError(f"Méthode d'ensemble non supportée: {self.ensemble_config.ensemble_method}")
        
        # Métriques
        metrics.training_time_s = time.time() - start_time
        metrics.total_epochs = self.ensemble_config.epochs
        metrics.ensemble_method = self.ensemble_config.ensemble_method.value
        metrics.n_members = len(self._members)
        
        # Diversité des membres
        metrics.diversity_score = self._calculate_diversity(X_train)
        
        # Métriques des membres
        for name, member in zip(self._member_names, self._members):
            if hasattr(member, 'metrics'):
                metrics.member_metrics[name] = member.metrics
        
        self.metrics = metrics
        self._is_trained = True
        
        logger.info(f"Entraînement terminé: Accuracy={metrics.accuracy:.4f}")
        
        return metrics
    
    def _train_voting(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray],
        y_val: Optional[np.ndarray]
    ) -> EnsembleMetrics:
        """
        Entraîne les modèles pour le voting.
        
        Args:
            X_train: Données d'entraînement.
            y_train: Labels d'entraînement.
            X_val: Données de validation.
            y_val: Labels de validation.
            
        Returns:
            Métriques d'entraînement.
        """
        logger.info("Entraînement des modèles pour le voting")
        
        # Entraînement des membres
        if self.ensemble_config.parallel:
            return self._train_parallel(X_train, y_train, X_val, y_val)
        else:
            return self._train_sequential(X_train, y_train, X_val, y_val)
    
    def _train_average(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray],
        y_val: Optional[np.ndarray]
    ) -> EnsembleMetrics:
        """
        Entraîne les modèles pour la moyenne.
        
        Args:
            X_train: Données d'entraînement.
            y_train: Labels d'entraînement.
            X_val: Données de validation.
            y_val: Labels de validation.
            
        Returns:
            Métriques d'entraînement.
        """
        logger.info("Entraînement des modèles pour la moyenne")
        return self._train_voting(X_train, y_train, X_val, y_val)
    
    def _train_weighted(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray],
        y_val: Optional[np.ndarray]
    ) -> EnsembleMetrics:
        """
        Entraîne les modèles pour la moyenne pondérée.
        
        Args:
            X_train: Données d'entraînement.
            y_train: Labels d'entraînement.
            X_val: Données de validation.
            y_val: Labels de validation.
            
        Returns:
            Métriques d'entraînement.
        """
        logger.info("Entraînement des modèles pour la moyenne pondérée")
        
        # Entraînement initial
        metrics = self._train_voting(X_train, y_train, X_val, y_val)
        
        # Optimisation des poids sur la validation
        if X_val is not None and y_val is not None:
            logger.info("Optimisation des poids sur la validation")
            self._optimize_weights(X_val, y_val)
        
        return metrics
    
    def _train_stacking(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray],
        y_val: Optional[np.ndarray]
    ) -> EnsembleMetrics:
        """
        Entraîne les modèles pour le stacking.
        
        Args:
            X_train: Données d'entraînement.
            y_train: Labels d'entraînement.
            X_val: Données de validation.
            y_val: Labels de validation.
            
        Returns:
            Métriques d'entraînement.
        """
        logger.info("Entraînement des modèles pour le stacking")
        
        # Entraînement des membres de base
        member_metrics = self._train_sequential(X_train, y_train, X_val, y_val)
        
        # Génération des features pour le méta-modèle
        logger.info("Génération des features pour le méta-modèle")
        
        # Utilisation de la validation croisée pour éviter le sur-apprentissage
        if self.ensemble_config.stacking_cv_folds > 1:
            meta_features = self._generate_cv_features(X_train)
        else:
            meta_features = self._get_member_predictions(X_train)
        
        # Entraînement du méta-modèle
        if self._meta_model:
            logger.info("Entraînement du méta-modèle")
            self._meta_model.train(meta_features, y_train)
            self._meta_model._is_trained = True
        
        return member_metrics
    
    def _train_bagging(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray],
        y_val: Optional[np.ndarray]
    ) -> EnsembleMetrics:
        """
        Entraîne les modèles pour le bagging.
        
        Args:
            X_train: Données d'entraînement.
            y_train: Labels d'entraînement.
            X_val: Données de validation.
            y_val: Labels de validation.
            
        Returns:
            Métriques d'entraînement.
        """
        logger.info("Entraînement des modèles pour le bagging")
        
        n_samples = self.ensemble_config.bagging_samples
        n_features = self.ensemble_config.bagging_features or X_train.shape[1]
        
        # Création des sous-échantillons
        for i, model in enumerate(self._members):
            # Bootstrap des échantillons
            if self.ensemble_config.bagging_bootstrap:
                indices = np.random.choice(len(X_train), n_samples, replace=True)
            else:
                indices = np.random.choice(len(X_train), n_samples, replace=False)
            
            X_sample = X_train[indices]
            y_sample = y_train[indices]
            
            # Bootstrap des features
            if n_features < X_train.shape[1]:
                feature_indices = np.random.choice(X_train.shape[1], n_features, replace=False)
                X_sample = X_sample[:, feature_indices]
                model.config.input_shape = (n_features,)
                model.build((n_features,))
            
            # Entraînement du modèle
            logger.info(f"Entraînement du membre {i+1}/{len(self._members)}")
            model.train(X_sample, y_sample)
            model._is_trained = True
        
        return EnsembleMetrics()
    
    def _train_boosting(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray],
        y_val: Optional[np.ndarray]
    ) -> EnsembleMetrics:
        """
        Entraîne les modèles pour le boosting.
        
        Args:
            X_train: Données d'entraînement.
            y_train: Labels d'entraînement.
            X_val: Données de validation.
            y_val: Labels de validation.
            
        Returns:
            Métriques d'entraînement.
        """
        logger.info("Entraînement des modèles pour le boosting")
        
        # Poids des échantillons
        sample_weights = np.ones(len(X_train)) / len(X_train)
        
        for i, model in enumerate(self._members):
            # Entraînement avec les poids actuels
            logger.info(f"Entraînement du membre {i+1}/{len(self._members)}")
            model.train(X_train, y_train)
            model._is_trained = True
            
            # Prédiction sur l'entraînement
            predictions = model.predict(X_train)
            y_pred = predictions.predictions
            
            # Calcul des erreurs
            errors = y_pred != y_train
            error_rate = np.mean(errors)
            
            # Mise à jour des poids
            if error_rate < 0.5:
                alpha = 0.5 * np.log((1 - error_rate) / (error_rate + 1e-8))
                sample_weights = sample_weights * np.exp(alpha * errors)
                sample_weights = sample_weights / np.sum(sample_weights)
                
                # Mise à jour du poids du modèle
                self._member_weights[i] = alpha
            else:
                self._member_weights[i] = 0.0
        
        # Normalisation des poids
        total_weight = sum(self._member_weights)
        if total_weight > 0:
            self._member_weights = [w / total_weight for w in self._member_weights]
        
        return EnsembleMetrics()
    
    # ============================================================
    # PRÉDICTION
    # ============================================================
    
    def predict(self, X: Union[np.ndarray, pd.DataFrame]) -> PredictionResult:
        """
        Effectue une prédiction avec l'ensemble.
        
        Args:
            X: Données à prédire.
            
        Returns:
            Résultat de la prédiction.
        """
        if not self._is_trained and not self._is_loaded:
            raise ModelError("Modèle non entraîné ou chargé")
        
        start_time = time.time()
        
        X = self._to_array(X)
        
        # Prédiction selon la méthode
        if self.ensemble_config.ensemble_method == EnsembleMethod.VOTING:
            predictions = self._predict_voting(X)
        elif self.ensemble_config.ensemble_method == EnsembleMethod.AVERAGE:
            predictions = self._predict_average(X)
        elif self.ensemble_config.ensemble_method == EnsembleMethod.WEIGHTED:
            predictions = self._predict_weighted(X)
        elif self.ensemble_config.ensemble_method == EnsembleMethod.STACKING:
            predictions = self._predict_stacking(X)
        elif self.ensemble_config.ensemble_method == EnsembleMethod.BAGGING:
            predictions = self._predict_bagging(X)
        elif self.ensemble_config.ensemble_method == EnsembleMethod.BOOSTING:
            predictions = self._predict_boosting(X)
        else:
            raise ModelError(f"Méthode d'ensemble non supportée: {self.ensemble_config.ensemble_method}")
        
        # Calcul de la confiance
        confidence = self._calculate_confidence(predictions)
        
        result = PredictionResult(
            predictions=predictions,
            confidence=confidence,
            timestamp=datetime.now(),
            input_shape=X.shape,
            inference_time_ms=(time.time() - start_time) * 1000
        )
        
        return result
    
    def _predict_voting(self, X: np.ndarray) -> np.ndarray:
        """
        Prédiction par voting.
        
        Args:
            X: Données à prédire.
            
        Returns:
            Prédictions.
        """
        if self.ensemble_config.parallel:
            predictions = self._predict_parallel(X)
        else:
            predictions = self._predict_sequential(X)
        
        # Voting hard ou soft
        if self.ensemble_config.voting_type == "hard":
            # Vote majoritaire
            if len(predictions.shape) > 1:
                # Classification multiclasse
                return np.apply_along_axis(lambda x: np.bincount(x).argmax(), axis=0, predictions)
            else:
                # Classification binaire
                return np.where(predictions.mean(axis=0) > self.ensemble_config.vote_threshold, 1, 0)
        else:
            # Soft voting (moyenne)
            return predictions.mean(axis=0)
    
    def _predict_average(self, X: np.ndarray) -> np.ndarray:
        """
        Prédiction par moyenne.
        
        Args:
            X: Données à prédire.
            
        Returns:
            Prédictions.
        """
        predictions = self._predict_parallel(X)
        return predictions.mean(axis=0)
    
    def _predict_weighted(self, X: np.ndarray) -> np.ndarray:
        """
        Prédiction par moyenne pondérée.
        
        Args:
            X: Données à prédire.
            
        Returns:
            Prédictions.
        """
        predictions = self._predict_parallel(X)
        return np.average(predictions, axis=0, weights=self._member_weights)
    
    def _predict_stacking(self, X: np.ndarray) -> np.ndarray:
        """
        Prédiction par stacking.
        
        Args:
            X: Données à prédire.
            
        Returns:
            Prédictions.
        """
        # Prédictions des membres
        member_predictions = self._predict_parallel(X)
        
        # Features pour le méta-modèle
        if len(member_predictions.shape) == 3:
            # Classification multiclasse
            meta_features = member_predictions.reshape(member_predictions.shape[0], -1)
        else:
            meta_features = member_predictions.T
        
        # Prédiction du méta-modèle
        if self._meta_model and self._meta_model._is_trained:
            result = self._meta_model.predict(meta_features)
            return result.predictions
        else:
            # Fallback à la moyenne pondérée
            return self._predict_weighted(X)
    
    def _predict_bagging(self, X: np.ndarray) -> np.ndarray:
        """
        Prédiction par bagging.
        
        Args:
            X: Données à prédire.
            
        Returns:
            Prédictions.
        """
        predictions = self._predict_parallel(X)
        
        # Moyenne des prédictions
        if self.ensemble_config.voting_type == "hard":
            return np.where(predictions.mean(axis=0) > self.ensemble_config.vote_threshold, 1, 0)
        else:
            return predictions.mean(axis=0)
    
    def _predict_boosting(self, X: np.ndarray) -> np.ndarray:
        """
        Prédiction par boosting.
        
        Args:
            X: Données à prédire.
            
        Returns:
            Prédictions.
        """
        predictions = self._predict_sequential(X)
        return np.average(predictions, axis=0, weights=self._member_weights)
    
    def _predict_parallel(self, X: np.ndarray) -> np.ndarray:
        """
        Prédiction parallèle des membres.
        
        Args:
            X: Données à prédire.
            
        Returns:
            Prédictions des membres.
        """
        def predict_member(model):
            try:
                result = model.predict(X)
                return result.predictions
            except Exception as e:
                logger.error(f"Erreur de prédiction pour {model.get_name()}: {e}")
                return np.zeros_like(X[:, 0])
        
        if self.ensemble_config.parallel:
            with ThreadPoolExecutor(max_workers=self.ensemble_config.max_workers) as executor:
                futures = [executor.submit(predict_member, model) for model in self._members]
                predictions = [future.result() for future in futures]
        else:
            predictions = [predict_member(model) for model in self._members]
        
        return np.array(predictions)
    
    def _predict_sequential(self, X: np.ndarray) -> np.ndarray:
        """
        Prédiction séquentielle des membres.
        
        Args:
            X: Données à prédire.
            
        Returns:
            Prédictions des membres.
        """
        predictions = []
        for model in self._members:
            try:
                result = model.predict(X)
                predictions.append(result.predictions)
            except Exception as e:
                logger.error(f"Erreur de prédiction pour {model.get_name()}: {e}")
                predictions.append(np.zeros_like(X[:, 0]))
        return np.array(predictions)
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    def _calculate_diversity(self, X: np.ndarray) -> float:
        """
        Calcule la diversité des membres.
        
        Args:
            X: Données pour le calcul.
            
        Returns:
            Score de diversité.
        """
        if len(self._members) < 2:
            return 1.0
        
        predictions = self._predict_parallel(X)
        
        # Calcul de la diversité comme la variance des prédictions
        diversity = np.var(predictions, axis=0).mean()
        
        # Normalisation
        if self.config.task == ModelTask.CLASSIFICATION:
            diversity = diversity / 0.25  # Maximum pour binaire
        
        return min(diversity, 1.0)
    
    def _calculate_confidence(self, predictions: np.ndarray) -> Optional[float]:
        """
        Calcule la confiance de la prédiction.
        
        Args:
            predictions: Prédictions.
            
        Returns:
            Confiance de la prédiction.
        """
        if len(self._members) < 2:
            return None
        
        # Variation des prédictions
        if self.config.task == ModelTask.CLASSIFICATION:
            # Pour la classification, confiance = proportion de votes
            if len(predictions.shape) > 1:
                # Multiclasse
                confidence = np.max(predictions, axis=1).mean()
            else:
                # Binaire
                confidence = np.abs(predictions.mean() - 0.5) * 2
        else:
            # Pour la régression, confiance = inverse de la variance
            variance = np.var(predictions, axis=0).mean()
            confidence = 1 / (1 + variance)
        
        return min(max(confidence, 0), 1)
    
    def _optimize_weights(self, X_val: np.ndarray, y_val: np.ndarray) -> None:
        """
        Optimise les poids des membres sur la validation.
        
        Args:
            X_val: Données de validation.
            y_val: Labels de validation.
        """
        try:
            from scipy.optimize import minimize
            
            predictions = self._predict_parallel(X_val)
            
            def objective(weights):
                weights = np.clip(weights, 0, 1)
                weights = weights / np.sum(weights)
                
                if self.config.task == ModelTask.CLASSIFICATION:
                    # Pour la classification, utiliser l'accuracy
                    if self.ensemble_config.voting_type == "soft":
                        # Soft voting
                        y_pred = np.average(predictions, axis=0, weights=weights)
                        y_pred = np.where(y_pred > self.ensemble_config.vote_threshold, 1, 0)
                    else:
                        # Hard voting
                        weighted_votes = np.average(predictions, axis=0, weights=weights)
                        y_pred = np.where(weighted_votes > self.ensemble_config.vote_threshold, 1, 0)
                    
                    return -np.mean(y_pred == y_val)
                else:
                    # Pour la régression, utiliser MSE
                    y_pred = np.average(predictions, axis=0, weights=weights)
                    return np.mean((y_pred - y_val) ** 2)
            
            # Optimisation
            n_members = len(self._members)
            initial_weights = np.ones(n_members) / n_members
            
            result = minimize(
                objective,
                initial_weights,
                method='L-BFGS-B',
                bounds=[(0, 1)] * n_members
            )
            
            if result.success:
                self._member_weights = np.clip(result.x, 0, 1)
                self._member_weights = self._member_weights / np.sum(self._member_weights)
                logger.info(f"Poids optimisés: {self._member_weights}")
            else:
                logger.warning("Optimisation des poids échouée")
                
        except ImportError:
            logger.warning("scipy non disponible, optimisation des poids ignorée")
        except Exception as e:
            logger.error(f"Erreur d'optimisation des poids: {e}")
    
    def _generate_cv_features(self, X: np.ndarray) -> np.ndarray:
        """
        Génère des features de validation croisée pour le stacking.
        
        Args:
            X: Données d'entraînement.
            
        Returns:
            Features pour le méta-modèle.
        """
        from sklearn.model_selection import KFold
        
        n_folds = self.ensemble_config.stacking_cv_folds
        kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
        
        meta_features = np.zeros((len(X), len(self._members)))
        
        for fold_idx, (train_idx, val_idx) in enumerate(kf.split(X)):
            X_train_fold = X[train_idx]
            X_val_fold = X[val_idx]
            
            # Entraînement des membres sur le fold
            for member_idx, model in enumerate(self._members):
                model.train(X_train_fold, X_val_fold)
                predictions = model.predict(X_val_fold)
                meta_features[val_idx, member_idx] = predictions.predictions
            
            logger.info(f"Fold {fold_idx+1}/{n_folds} terminé")
        
        return meta_features
    
    def _get_member_predictions(self, X: np.ndarray) -> np.ndarray:
        """
        Récupère les prédictions des membres.
        
        Args:
            X: Données d'entrée.
            
        Returns:
            Prédictions des membres.
        """
        predictions = self._predict_parallel(X)
        return predictions.T
    
    # ============================================================
    # SAUVEGARDE ET CHARGEMENT
    # ============================================================
    
    def save(self, filepath: str) -> None:
        """
        Sauvegarde le modèle d'ensemble.
        
        Args:
            filepath: Chemin de sauvegarde.
        """
        logger.info(f"Sauvegarde de l'ensemble: {filepath}")
        
        # Sauvegarde de la configuration
        config_path = filepath.replace('.pth', '_config.json')
        with open(config_path, 'w') as f:
            json.dump(self.ensemble_config.__dict__, f, indent=2, default=str)
        
        # Sauvegarde des membres
        for i, model in enumerate(self._members):
            member_path = f"{filepath}_member_{i}.pth"
            model.save(member_path)
        
        # Sauvegarde du méta-modèle
        if self._meta_model:
            meta_path = f"{filepath}_meta.pth"
            self._meta_model.save(meta_path)
        
        # Sauvegarde des métadonnées
        metadata = {
            'name': self.config.name,
            'version': self.config.version,
            'timestamp': datetime.now().isoformat(),
            'n_members': len(self._members),
            'member_names': self._member_names,
            'member_weights': self._member_weights.tolist() if self._member_weights else [],
            'ensemble_method': self.ensemble_config.ensemble_method.value
        }
        
        metadata_path = filepath.replace('.pth', '_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        logger.info(f"Ensemble sauvegardé: {filepath}")
    
    def load(self, filepath: str) -> None:
        """
        Charge le modèle d'ensemble.
        
        Args:
            filepath: Chemin de chargement.
        """
        logger.info(f"Chargement de l'ensemble: {filepath}")
        
        # Chargement des métadonnées
        metadata_path = filepath.replace('.pth', '_metadata.json')
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                self._member_names = metadata.get('member_names', [])
                self._member_weights = metadata.get('member_weights', [])
        
        # Chargement des membres
        self._members = []
        for i in range(len(self._member_names)):
            member_path = f"{filepath}_member_{i}.pth"
            try:
                model = ModelFactory.load(member_path)
                self._members.append(model)
                logger.info(f"Membre {i} chargé: {model.get_name()}")
            except Exception as e:
                logger.error(f"Erreur de chargement du membre {i}: {e}")
        
        # Chargement du méta-modèle
        meta_path = f"{filepath}_meta.pth"
        if os.path.exists(meta_path):
            try:
                self._meta_model = ModelFactory.load(meta_path)
                logger.info(f"Méta-modèle chargé: {self._meta_model.get_name()}")
            except Exception as e:
                logger.error(f"Erreur de chargement du méta-modèle: {e}")
        
        self._is_loaded = True
        self._is_trained = True
        
        logger.info(f"Ensemble chargé: {filepath}")
    
    def get_params(self) -> Dict[str, Any]:
        """
        Retourne les paramètres du modèle.
        
        Returns:
            Paramètres du modèle.
        """
        params = {
            'ensemble_method': self.ensemble_config.ensemble_method.value,
            'n_members': len(self._members),
            'member_names': self._member_names,
            'member_weights': self._member_weights,
            'voting_type': self.ensemble_config.voting_type
        }
        
        # Ajout des paramètres des membres
        for i, model in enumerate(self._members):
            params[f'member_{i}_params'] = model.get_params()
        
        return params
    
    # ============================================================
    # MÉTHODES DE CONVERSION
    # ============================================================
    
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


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_ensemble(
    member_models: List[Dict[str, Any]],
    method: str = "voting",
    weights: Optional[List[float]] = None,
    **kwargs
) -> EnsembleModel:
    """
    Crée un modèle d'ensemble.
    
    Args:
        member_models: Liste des configurations des membres.
        method: Méthode d'ensemble.
        weights: Poids des membres.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Modèle d'ensemble.
    """
    method_map = {
        'voting': EnsembleMethod.VOTING,
        'average': EnsembleMethod.AVERAGE,
        'weighted': EnsembleMethod.WEIGHTED,
        'stacking': EnsembleMethod.STACKING,
        'bagging': EnsembleMethod.BAGGING,
        'boosting': EnsembleMethod.BOOSTING
    }
    
    config = EnsembleConfig(
        ensemble_method=method_map.get(method, EnsembleMethod.VOTING),
        member_models=member_models,
        member_weights=weights,
        **kwargs
    )
    
    return EnsembleModel(config)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'EnsembleModel',
    'EnsembleConfig',
    'EnsembleMetrics',
    'EnsembleMethod',
    'EnsembleMode',
    'create_ensemble'
]

# ============================================================
# FIN DU FICHIER
# ============================================================
