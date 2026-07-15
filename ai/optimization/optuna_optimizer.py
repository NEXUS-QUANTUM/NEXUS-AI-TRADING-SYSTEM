
# ai/optimization/optuna_optimizer.py
"""
NEXUS AI TRADING SYSTEM - Optuna Optimization Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import time
import warnings
warnings.filterwarnings('ignore')

try:
    import optuna
    from optuna import Trial, create_study
    from optuna.samplers import TPESampler, RandomSampler, CmaEsSampler, NSGAIISampler
    from optuna.pruners import MedianPruner, HyperbandPruner, PatientPruner
    from optuna.visualization import plot_optimization_history, plot_param_importances, plot_parallel_coordinate
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class OptunaConfig:
    """Configuration pour Optuna"""
    n_trials: int = 100
    direction: str = 'minimize'  # 'minimize' ou 'maximize'
    sampler: str = 'tpe'  # 'tpe', 'random', 'cmaes', 'nsgaii'
    pruner: str = 'median'  # 'median', 'hyperband', 'patient'
    n_startup_trials: int = 10
    n_ei_candidates: int = 24
    seed: Optional[int] = 42
    timeout: Optional[int] = None
    storage: Optional[str] = None
    study_name: Optional[str] = None
    load_if_exists: bool = False
    verbose: bool = True
    early_stopping: bool = True
    patience: int = 20

    def __post_init__(self):
        if not OPTUNA_AVAILABLE:
            raise ImportError("Optuna n'est pas installé")
        if self.n_trials <= 0:
            raise ValueError("n_trials doit être > 0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'n_trials': self.n_trials,
            'direction': self.direction,
            'sampler': self.sampler,
            'pruner': self.pruner,
            'n_startup_trials': self.n_startup_trials,
            'n_ei_candidates': self.n_ei_candidates,
            'seed': self.seed,
            'timeout': self.timeout,
            'storage': self.storage,
            'study_name': self.study_name,
            'load_if_exists': self.load_if_exists,
            'verbose': self.verbose,
            'early_stopping': self.early_stopping,
            'patience': self.patience,
        }


@dataclass
class OptunaResult:
    """Résultat de Optuna"""
    best_params: Dict[str, Any]
    best_value: float
    n_trials: int
    total_time: float
    timestamp: datetime = field(default_factory=datetime.now)
    study: Optional[Any] = None
    importance: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'best_params': self.best_params,
            'best_value': self.best_value,
            'n_trials': self.n_trials,
            'total_time': self.total_time,
            'timestamp': self.timestamp.isoformat(),
            'importance': self.importance,
        }


class OptunaOptimizer:
    """
    Optuna pour l'optimisation des hyperparamètres.

    Features:
    - Algorithmes TPE, Random, CMA-ES, NSGA-II
    - Pruners Median, Hyperband, Patient
    - Arrêt précoce
    - Importance des paramètres
    - Visualisation
    - Sauvegarde/Chargement

    Example:
        ```python
        def objective(trial):
            x1 = trial.suggest_float('x1', -5, 5)
            x2 = trial.suggest_float('x2', -5, 5)
            return x1**2 + x2**2

        config = OptunaConfig(
            n_trials=100,
            direction='minimize',
            sampler='tpe'
        )
        optimizer = OptunaOptimizer(config)
        result = optimizer.optimize(objective)
        ```
    """

    def __init__(self, config: Optional[OptunaConfig] = None):
        if not OPTUNA_AVAILABLE:
            raise ImportError("Optuna est requis. Installez avec: pip install optuna")

        self.config = config or OptunaConfig()
        self.study = None
        self.best_params: Optional[Dict[str, Any]] = None
        self.best_value: Optional[float] = None
        self.importance: Optional[Dict[str, float]] = None
        self.is_fitted = False
        self.objective_fn = None

        # Initialisation du générateur aléatoire
        if self.config.seed is not None:
            np.random.seed(self.config.seed)
            optuna.logging.set_verbosity(optuna.logging.ERROR)

        logger.info(f"OptunaOptimizer initialisé")

    def _get_sampler(self):
        """Retourne le sampler configuré"""
        if self.config.sampler == 'tpe':
            return TPESampler(
                n_startup_trials=self.config.n_startup_trials,
                n_ei_candidates=self.config.n_ei_candidates,
                seed=self.config.seed,
            )
        elif self.config.sampler == 'random':
            return RandomSampler(seed=self.config.seed)
        elif self.config.sampler == 'cmaes':
            return CmaEsSampler(seed=self.config.seed)
        elif self.config.sampler == 'nsgaii':
            return NSGAIISampler(seed=self.config.seed)
        else:
            raise ValueError(f"Sampler non supporté: {self.config.sampler}")

    def _get_pruner(self):
        """Retourne le pruner configuré"""
        if self.config.pruner == 'median':
            return MedianPruner(
                n_startup_trials=self.config.n_startup_trials,
                n_warmup_steps=10,
            )
        elif self.config.pruner == 'hyperband':
            return HyperbandPruner(
                min_resource=1,
                max_resource=self.config.n_trials,
            )
        elif self.config.pruner == 'patient':
            return PatientPruner(
                MedianPruner(n_startup_trials=5),
                patience=self.config.patience,
            )
        else:
            raise ValueError(f"Pruner non supporté: {self.config.pruner}")

    def _create_study(self):
        """Crée l'étude Optuna"""
        sampler = self._get_sampler()
        pruner = self._get_pruner()

        if self.config.storage:
            study = create_study(
                direction=self.config.direction,
                sampler=sampler,
                pruner=pruner,
                storage=self.config.storage,
                study_name=self.config.study_name,
                load_if_exists=self.config.load_if_exists,
            )
        else:
            study = create_study(
                direction=self.config.direction,
                sampler=sampler,
                pruner=pruner,
            )

        return study

    def _objective_wrapper(self, trial: Trial) -> float:
        """
        Wrapper pour la fonction objectif.

        Args:
            trial: Objet Trial Optuna

        Returns:
            float: Valeur de l'objectif
        """
        value = self.objective_fn(trial)

        # Vérification de l'arrêt précoce
        if self.config.early_stopping:
            intermediate_value = value
            trial.report(intermediate_value, trial.number)

        return value

    def optimize(
        self,
        objective: Callable,
        **kwargs
    ) -> OptunaResult:
        """
        Effectue l'optimisation avec Optuna.

        Args:
            objective: Fonction objectif (prend un Trial en argument)
            **kwargs: Arguments supplémentaires

        Returns:
            OptunaResult: Résultat de l'optimisation
        """
        self.objective_fn = objective

        # Création de l'étude
        self.study = self._create_study()

        start_time = time.time()

        # Optimisation
        self.study.optimize(
            self._objective_wrapper,
            n_trials=self.config.n_trials,
            timeout=self.config.timeout,
            show_progress_bar=self.config.verbose,
            callbacks=[self._early_stopping_callback] if self.config.early_stopping else None,
        )

        total_time = time.time() - start_time

        # Résultats
        self.best_params = self.study.best_params
        self.best_value = self.study.best_value
        self.importance = self._compute_importance()

        self.is_fitted = True

        logger.info(f"Optimisation terminée en {total_time:.2f}s")
        logger.info(f"Meilleurs paramètres: {self.best_params}")
        logger.info(f"Meilleure valeur: {self.best_value:.6f}")
        logger.info(f"Nombre de trials: {len(self.study.trials)}")

        if self.importance:
            logger.info(f"Importance des paramètres: {self.importance}")

        result = OptunaResult(
            best_params=self.best_params,
            best_value=self.best_value,
            n_trials=len(self.study.trials),
            total_time=total_time,
            study=self.study,
            importance=self.importance,
        )

        return result

    def _early_stopping_callback(self, study: optuna.Study, trial: optuna.Trial) -> None:
        """Callback pour l'arrêt précoce"""
        if self.config.patience > 0 and len(study.trials) > self.config.patience:
            best_value = study.best_value
            recent_values = [t.value for t in study.trials[-self.config.patience:] if t.value is not None]

            if len(recent_values) >= self.config.patience:
                direction = self.config.direction

                if direction == 'minimize':
                    if all(v >= best_value for v in recent_values):
                        logger.info(f"Arrêt précoce: pas d'amélioration depuis {self.config.patience} trials")
                        study.stop()
                else:
                    if all(v <= best_value for v in recent_values):
                        logger.info(f"Arrêt précoce: pas d'amélioration depuis {self.config.patience} trials")
                        study.stop()

    def _compute_importance(self) -> Optional[Dict[str, float]]:
        """Calcule l'importance des paramètres"""
        if not self.study:
            return None

        try:
            from optuna.importance import get_param_importances
            importance = get_param_importances(self.study)
            return {k: float(v) for k, v in importance.items()}
        except Exception as e:
            logger.warning(f"Erreur lors du calcul d'importance: {e}")
            return None

    def get_history(self) -> pd.DataFrame:
        """
        Retourne l'historique de l'optimisation.

        Returns:
            pd.DataFrame: Historique
        """
        if not self.study:
            return pd.DataFrame()

        trials_data = []
        for trial in self.study.trials:
            if trial.value is not None:
                data = {
                    'number': trial.number,
                    'value': trial.value,
                    'datetime_start': trial.datetime_start,
                    'datetime_complete': trial.datetime_complete,
                    'duration': trial.duration.total_seconds() if trial.duration else None,
                    'state': trial.state.name,
                }
                data.update(trial.params)
                trials_data.append(data)

        return pd.DataFrame(trials_data)

    def get_best_params(self) -> Dict[str, Any]:
        """Retourne les meilleurs paramètres"""
        return self.best_params

    def get_best_value(self) -> Optional[float]:
        """Retourne la meilleure valeur"""
        return self.best_value

    def get_importance(self) -> Optional[Dict[str, float]]:
        """Retourne l'importance des paramètres"""
        return self.importance

    def plot_optimization_history(self, figsize: Tuple[int, int] = (12, 6)) -> None:
        """
        Affiche l'historique de l'optimisation.

        Args:
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        if not self.study:
            logger.warning("Aucune étude à visualiser")
            return

        try:
            fig = plot_optimization_history(self.study)
            fig.update_layout(width=figsize[0] * 80, height=figsize[1] * 80)
            fig.show()
        except Exception as e:
            logger.error(f"Erreur lors du tracé: {e}")

    def plot_param_importances(self, figsize: Tuple[int, int] = (12, 6)) -> None:
        """
        Affiche l'importance des paramètres.

        Args:
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        if not self.study:
            logger.warning("Aucune étude à visualiser")
            return

        try:
            fig = plot_param_importances(self.study)
            fig.update_layout(width=figsize[0] * 80, height=figsize[1] * 80)
            fig.show()
        except Exception as e:
            logger.error(f"Erreur lors du tracé: {e}")

    def plot_parallel_coordinate(self, figsize: Tuple[int, int] = (12, 8)) -> None:
        """
        Affiche les coordonnées parallèles.

        Args:
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        if not self.study:
            logger.warning("Aucune étude à visualiser")
            return

        try:
            fig = plot_parallel_coordinate(self.study)
            fig.update_layout(width=figsize[0] * 80, height=figsize[1] * 80)
            fig.show()
        except Exception as e:
            logger.error(f"Erreur lors du tracé: {e}")

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde le résultat de l'optimisation.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si la sauvegarde a réussi
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            result = OptunaResult(
                best_params=self.best_params,
                best_value=self.best_value,
                n_trials=len(self.study.trials) if self.study else 0,
                total_time=0,
                study=None,
                importance=self.importance,
            )

            data = {
                'config': self.config.to_dict(),
                'result': result.to_dict(),
                'study': self.study,
                'is_fitted': self.is_fitted,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            # Sauvegarder l'étude séparément
            if self.study and self.config.storage is None:
                import optuna
                study_path = filepath + '.study.pkl'
                with open(study_path, 'wb') as f:
                    pickle.dump(self.study, f)
                data['study_path'] = study_path

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Résultat sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'OptunaOptimizer':
        """
        Charge un résultat d'optimisation.

        Args:
            filepath: Chemin du fichier

        Returns:
            OptunaOptimizer: Instance chargée
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = OptunaConfig(**data['config'])
            optimizer = cls(config)

            optimizer.is_fitted = data.get('is_fitted', False)

            result = data.get('result')
            if result:
                optimizer.best_params = result['best_params']
                optimizer.best_value = result['best_value']
                optimizer.importance = result.get('importance')

            # Charger l'étude
            study_path = data.get('study_path')
            if study_path and os.path.exists(study_path):
                with open(study_path, 'rb') as f:
                    optimizer.study = pickle.load(f)
            else:
                optimizer.study = data.get('study')

            logger.info(f"Résultat chargé: {filepath}")
            return optimizer

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_optuna_optimizer(
    n_trials: int = 100,
    direction: str = 'minimize',
    sampler: str = 'tpe',
    pruner: str = 'median',
    **kwargs
) -> OptunaOptimizer:
    """
    Factory pour créer un optimiseur Optuna.

    Args:
        n_trials: Nombre de trials
        direction: Direction ('minimize', 'maximize')
        sampler: Sampler ('tpe', 'random', 'cmaes', 'nsgaii')
        pruner: Pruner ('median', 'hyperband', 'patient')
        **kwargs: Arguments supplémentaires

    Returns:
        OptunaOptimizer: Optimiseur Optuna
    """
    config = OptunaConfig(
        n_trials=n_trials,
        direction=direction,
        sampler=sampler,
        pruner=pruner,
        **kwargs
    )
    return OptunaOptimizer(config)


__all__ = [
    'OptunaOptimizer',
    'OptunaConfig',
    'OptunaResult',
    'create_optuna_optimizer',
]
