
# ai/optimization/hyperopt.py
"""
NEXUS AI TRADING SYSTEM - Hyperopt Integration Module
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
    from hyperopt import fmin, tpe, rand, atpe, anneal, Trials, STATUS_OK, STATUS_FAIL
    from hyperopt.pyll import scope
    from hyperopt.space_eval import space_eval
    HYPEROPT_AVAILABLE = True
except ImportError:
    HYPEROPT_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class HyperoptConfig:
    """Configuration pour Hyperopt"""
    max_evals: int = 100
    algorithm: str = 'tpe'  # 'tpe', 'rand', 'atpe', 'anneal'
    early_stopping: bool = True
    patience: int = 20
    loss_threshold: Optional[float] = None
    show_progressbar: bool = True
    verbose: bool = False
    random_state: Optional[int] = 42
    n_initial_points: int = 10
    gamma: float = 0.25
    n_startup_jobs: int = 10

    def __post_init__(self):
        if not HYPEROPT_AVAILABLE:
            raise ImportError("Hyperopt n'est pas installé")
        if self.max_evals <= 0:
            raise ValueError("max_evals doit être > 0")
        if self.n_initial_points <= 0:
            raise ValueError("n_initial_points doit être > 0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'max_evals': self.max_evals,
            'algorithm': self.algorithm,
            'early_stopping': self.early_stopping,
            'patience': self.patience,
            'loss_threshold': self.loss_threshold,
            'show_progressbar': self.show_progressbar,
            'verbose': self.verbose,
            'random_state': self.random_state,
            'n_initial_points': self.n_initial_points,
            'gamma': self.gamma,
            'n_startup_jobs': self.n_startup_jobs,
        }


@dataclass
class HyperoptResult:
    """Résultat de Hyperopt"""
    best_params: Dict[str, Any]
    best_loss: float
    n_trials: int
    total_time: float
    timestamp: datetime = field(default_factory=datetime.now)
    trials: Optional[Any] = None
    history: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'best_params': self.best_params,
            'best_loss': self.best_loss,
            'n_trials': self.n_trials,
            'total_time': self.total_time,
            'timestamp': self.timestamp.isoformat(),
            'history': self.history,
        }


class HyperoptOptimizer:
    """
    Hyperopt pour l'optimisation des hyperparamètres.

    Features:
    - Algorithmes TPE, Random, ATPE, Anneal
    - Arrêt précoce
    - Historique complet
    - Sauvegarde/Chargement
    - Visualisation

    Example:
        ```python
        from hyperopt import hp

        def objective(params):
            return params['x1']**2 + params['x2']**2

        space = {
            'x1': hp.uniform('x1', -5, 5),
            'x2': hp.uniform('x2', -5, 5),
        }

        config = HyperoptConfig(
            max_evals=100,
            algorithm='tpe'
        )
        optimizer = HyperoptOptimizer(config)

        result = optimizer.optimize(objective, space)
        ```
    """

    def __init__(self, config: Optional[HyperoptConfig] = None):
        if not HYPEROPT_AVAILABLE:
            raise ImportError("Hyperopt est requis. Installez avec: pip install hyperopt")

        self.config = config or HyperoptConfig()
        self.trials = Trials()
        self.history: List[Dict[str, Any]] = []
        self.best_params: Optional[Dict[str, Any]] = None
        self.best_loss: Optional[float] = None
        self.space: Optional[Dict[str, Any]] = None
        self.is_fitted = False

        # Initialisation du générateur aléatoire
        if self.config.random_state is not None:
            np.random.seed(self.config.random_state)

        logger.info(f"HyperoptOptimizer initialisé avec {self.config.algorithm}")

    def _get_algorithm(self):
        """Retourne l'algorithme Hyperopt configuré"""
        if self.config.algorithm == 'tpe':
            return tpe.suggest
        elif self.config.algorithm == 'rand':
            return rand.suggest
        elif self.config.algorithm == 'atpe':
            return atpe.suggest
        elif self.config.algorithm == 'anneal':
            return anneal.suggest
        else:
            raise ValueError(f"Algorithme non supporté: {self.config.algorithm}")

    def _objective_wrapper(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wrapper pour la fonction objectif.

        Args:
            params: Paramètres à évaluer

        Returns:
            Dict[str, Any]: Résultat de l'évaluation
        """
        try:
            loss = self.objective(params)
            self.history.append({
                'params': params,
                'loss': loss,
                'status': STATUS_OK,
                'time': time.time(),
            })
            return {'loss': loss, 'status': STATUS_OK}
        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation: {e}")
            self.history.append({
                'params': params,
                'loss': float('inf'),
                'status': STATUS_FAIL,
                'time': time.time(),
                'error': str(e),
            })
            return {'loss': float('inf'), 'status': STATUS_FAIL}

    def optimize(
        self,
        objective: Callable,
        space: Dict[str, Any],
        **kwargs
    ) -> HyperoptResult:
        """
        Effectue l'optimisation avec Hyperopt.

        Args:
            objective: Fonction objectif
            space: Espace de recherche Hyperopt
            **kwargs: Arguments supplémentaires

        Returns:
            HyperoptResult: Résultat de l'optimisation
        """
        self.objective = objective
        self.space = space
        self.trials = Trials()
        self.history = []

        algorithm = self._get_algorithm()

        start_time = time.time()

        # Optimisation
        best = fmin(
            fn=self._objective_wrapper,
            space=space,
            algo=algorithm,
            max_evals=self.config.max_evals,
            trials=self.trials,
            verbose=self.config.verbose,
            show_progressbar=self.config.show_progressbar,
            early_stop_fn=self._early_stop_fn if self.config.early_stopping else None,
        )

        total_time = time.time() - start_time

        # Meilleurs paramètres
        self.best_params = space_eval(space, best)
        self.best_loss = self.trials.best_trial['result']['loss']
        self.is_fitted = True

        logger.info(f"Optimisation terminée en {total_time:.2f}s")
        logger.info(f"Meilleurs paramètres: {self.best_params}")
        logger.info(f"Meilleure perte: {self.best_loss:.6f}")

        result = HyperoptResult(
            best_params=self.best_params,
            best_loss=self.best_loss,
            n_trials=len(self.trials.trials),
            total_time=total_time,
            trials=self.trials,
            history=self.history,
        )

        return result

    def _early_stop_fn(self, trials, best_loss):
        """
        Fonction d'arrêt précoce.

        Args:
            trials: Objet Trials
            best_loss: Meilleure perte actuelle

        Returns:
            bool: True si l'arrêt est demandé
        """
        if self.config.loss_threshold is not None and best_loss <= self.config.loss_threshold:
            logger.info(f"Arrêt précoce: meilleure perte {best_loss:.6f} <= seuil {self.config.loss_threshold}")
            return True

        if len(self.history) >= self.config.patience * 2:
            recent_losses = [h['loss'] for h in self.history[-self.config.patience:] if h['status'] == STATUS_OK]
            if len(recent_losses) >= self.config.patience:
                if min(recent_losses) >= best_loss:
                    logger.info(f"Arrêt précoce: pas d'amélioration depuis {self.config.patience} itérations")
                    return True

        return False

    def get_history(self) -> pd.DataFrame:
        """
        Retourne l'historique de l'optimisation.

        Returns:
            pd.DataFrame: Historique
        """
        return pd.DataFrame(self.history)

    def get_best_params(self) -> Dict[str, Any]:
        """Retourne les meilleurs paramètres"""
        return self.best_params

    def get_best_loss(self) -> Optional[float]:
        """Retourne la meilleure perte"""
        return self.best_loss

    def plot_convergence(self, figsize: Tuple[int, int] = (12, 6)) -> None:
        """
        Affiche la convergence de l'optimisation.

        Args:
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        try:
            df = self.get_history()
            df_valid = df[df['status'] == STATUS_OK]

            if len(df_valid) == 0:
                logger.warning("Aucune donnée valide à afficher")
                return

            fig, axes = plt.subplots(2, 1, figsize=figsize)

            # Loss
            axes[0].plot(df_valid.index, df_valid['loss'], 'b-', label='Loss')
            axes[0].plot(df_valid.index, df_valid['loss'].cummin(), 'r-', label='Meilleure loss')
            axes[0].set_xlabel('Itération')
            axes[0].set_ylabel('Loss')
            axes[0].set_title('Convergence de l\'optimisation')
            axes[0].legend()
            axes[0].grid(True, alpha=0.3)

            # Distribution des paramètres
            if len(self.best_params) > 0:
                for i, (key, value) in enumerate(self.best_params.items()):
                    if i >= 3:  # Limiter à 3 paramètres
                        break
                    values = df_valid['params'].apply(lambda x: x.get(key, 0))
                    axes[1].scatter(df_valid.index, values, label=key, alpha=0.5)
                axes[1].set_xlabel('Itération')
                axes[1].set_ylabel('Valeurs des paramètres')
                axes[1].set_title('Évolution des paramètres')
                axes[1].legend()
                axes[1].grid(True, alpha=0.3)

            plt.tight_layout()
            plt.show()

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

            if self.is_fitted:
                result = HyperoptResult(
                    best_params=self.best_params,
                    best_loss=self.best_loss,
                    n_trials=len(self.trials.trials) if self.trials else 0,
                    total_time=0,  # Non stocké
                    trials=None,  # Non sérialisable
                    history=self.history,
                )
                result_dict = result.to_dict()
            else:
                result_dict = None

            data = {
                'config': self.config.to_dict(),
                'result': result_dict,
                'space': self.space,
                'history': self.history,
                'is_fitted': self.is_fitted,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Résultat sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'HyperoptOptimizer':
        """
        Charge un résultat d'optimisation.

        Args:
            filepath: Chemin du fichier

        Returns:
            HyperoptOptimizer: Instance chargée
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = HyperoptConfig(**data['config'])
            optimizer = cls(config)

            optimizer.space = data.get('space')
            optimizer.history = data.get('history', [])
            optimizer.is_fitted = data.get('is_fitted', False)

            result = data.get('result')
            if result:
                optimizer.best_params = result['best_params']
                optimizer.best_loss = result['best_loss']

            logger.info(f"Résultat chargé: {filepath}")
            return optimizer

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_hyperopt_optimizer(
    max_evals: int = 100,
    algorithm: str = 'tpe',
    early_stopping: bool = True,
    patience: int = 20,
    **kwargs
) -> HyperoptOptimizer:
    """
    Factory pour créer un optimiseur Hyperopt.

    Args:
        max_evals: Nombre maximum d'évaluations
        algorithm: Algorithme ('tpe', 'rand', 'atpe', 'anneal')
        early_stopping: Arrêt précoce
        patience: Patience pour l'arrêt précoce
        **kwargs: Arguments supplémentaires

    Returns:
        HyperoptOptimizer: Optimiseur Hyperopt
    """
    config = HyperoptConfig(
        max_evals=max_evals,
        algorithm=algorithm,
        early_stopping=early_stopping,
        patience=patience,
        **kwargs
    )
    return HyperoptOptimizer(config)


__all__ = [
    'HyperoptOptimizer',
    'HyperoptConfig',
    'HyperoptResult',
    'create_hyperopt_optimizer',
]
