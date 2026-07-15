
# ai/optimization/bayesian_optimization.py
"""
NEXUS AI TRADING SYSTEM - Bayesian Optimization Module
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
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from scipy.stats import norm
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class BayesianOptimizationConfig:
    """Configuration pour l'optimisation bayésienne"""
    n_initial_points: int = 10
    n_iterations: int = 50
    acquisition_function: str = 'ei'  # 'ei', 'ucb', 'poi'
    kappa: float = 2.0  # Pour UCB
    xi: float = 0.01  # Pour EI et POI
    random_state: Optional[int] = 42
    n_restarts: int = 10
    verbose: bool = False
    use_gpu: bool = False

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if not SCIPY_AVAILABLE:
            raise ImportError("SciPy n'est pas installé")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'n_initial_points': self.n_initial_points,
            'n_iterations': self.n_iterations,
            'acquisition_function': self.acquisition_function,
            'kappa': self.kappa,
            'xi': self.xi,
            'random_state': self.random_state,
            'n_restarts': self.n_restarts,
            'verbose': self.verbose,
            'use_gpu': self.use_gpu,
        }


class _GaussianProcess(nn.Module):
    """
    Processus Gaussien pour l'optimisation bayésienne.

    Implémente un GP avec noyau RBF pour la régression.
    """

    def __init__(
        self,
        input_dim: int,
        lengthscale: float = 1.0,
        variance: float = 1.0,
        noise: float = 1e-6,
        use_gpu: bool = False,
    ):
        super().__init__()

        self.input_dim = input_dim
        self.use_gpu = use_gpu

        # Hyperparamètres
        self.lengthscale = nn.Parameter(torch.tensor(lengthscale))
        self.variance = nn.Parameter(torch.tensor(variance))
        self.noise = nn.Parameter(torch.tensor(noise))

        # Cache
        self.X_train = None
        self.y_train = None
        self.K = None
        self.K_inv = None

        self.device = torch.device('cuda' if use_gpu and torch.cuda.is_available() else 'cpu')

    def _rbf_kernel(self, X1: torch.Tensor, X2: torch.Tensor) -> torch.Tensor:
        """Noyau RBF"""
        lengthscale = torch.exp(self.lengthscale)
        variance = torch.exp(self.variance)

        sq_dist = torch.cdist(X1 / lengthscale, X2 / lengthscale, p=2) ** 2
        return variance * torch.exp(-0.5 * sq_dist)

    def fit(self, X: torch.Tensor, y: torch.Tensor):
        """
        Entraîne le GP sur les données.

        Args:
            X: Données d'entrée
            y: Cibles
        """
        self.X_train = X.to(self.device)
        self.y_train = y.to(self.device)

        # Calcul de la matrice de covariance
        self.K = self._rbf_kernel(self.X_train, self.X_train)
        self.K = self.K + torch.exp(self.noise) * torch.eye(len(self.X_train), device=self.device)

        # Factorisation de Cholesky
        try:
            self.L = torch.linalg.cholesky(self.K)
            self.alpha = torch.cholesky_solve(self.y_train, self.L)
            self.K_inv = torch.cholesky_inverse(self.L)
        except:
            # Fallback: inversion directe
            self.K_inv = torch.inverse(self.K + 1e-6 * torch.eye(len(self.X_train), device=self.device))
            self.alpha = self.K_inv @ self.y_train

    def predict(self, X: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Prédit la moyenne et la variance.

        Args:
            X: Points à prédire

        Returns:
            Tuple[torch.Tensor, torch.Tensor]: (Moyenne, Variance)
        """
        X = X.to(self.device)

        # Covariance avec les points d'entraînement
        K_s = self._rbf_kernel(self.X_train, X)
        K_ss = self._rbf_kernel(X, X) + torch.exp(self.noise) * torch.eye(len(X), device=self.device)

        # Moyenne
        mean = K_s.T @ self.alpha

        # Variance
        v = torch.linalg.solve(self.K, K_s)
        variance = torch.diag(K_ss - (K_s.T @ v))

        return mean.squeeze(), variance.squeeze()


class _AcquisitionFunction:
    """Fonctions d'acquisition pour l'optimisation bayésienne"""

    @staticmethod
    def ei(mean: np.ndarray, std: np.ndarray, best: float, xi: float = 0.01) -> np.ndarray:
        """
        Expected Improvement.

        Args:
            mean: Moyenne prédite
            std: Écart-type prédit
            best: Meilleure valeur observée
            xi: Paramètre d'exploration

        Returns:
            np.ndarray: Expected Improvement
        """
        with np.errstate(divide='ignore', invalid='ignore'):
            improvement = mean - best - xi
            Z = improvement / (std + 1e-9)
            ei = improvement * norm.cdf(Z) + (std + 1e-9) * norm.pdf(Z)
            ei[std == 0] = 0
            return ei

    @staticmethod
    def ucb(mean: np.ndarray, std: np.ndarray, kappa: float = 2.0) -> np.ndarray:
        """
        Upper Confidence Bound.

        Args:
            mean: Moyenne prédite
            std: Écart-type prédit
            kappa: Paramètre d'exploration

        Returns:
            np.ndarray: UCB
        """
        return mean + kappa * std

    @staticmethod
    def poi(mean: np.ndarray, std: np.ndarray, best: float, xi: float = 0.01) -> np.ndarray:
        """
        Probability of Improvement.

        Args:
            mean: Moyenne prédite
            std: Écart-type prédit
            best: Meilleure valeur observée
            xi: Paramètre d'exploration

        Returns:
            np.ndarray: POI
        """
        with np.errstate(divide='ignore', invalid='ignore'):
            improvement = mean - best - xi
            Z = improvement / (std + 1e-9)
            poi = norm.cdf(Z)
            poi[std == 0] = 0
            return poi


class BayesianOptimization:
    """
    Optimisation bayésienne pour les hyperparamètres.

    Utilise un processus gaussien pour modéliser la fonction objectif
    et une fonction d'acquisition pour guider la recherche.

    Features:
    - Processus Gaussien avec noyau RBF
    - Multiples fonctions d'acquisition (EI, UCB, POI)
    - Multi-restarts pour l'optimisation
    - Suivi de l'historique
    - GPU acceleration
    - Sauvegarde/Chargement

    Example:
        ```python
        def objective(x):
            return -(x[0]**2 + x[1]**2)

        config = BayesianOptimizationConfig(
            n_initial_points=10,
            n_iterations=50,
            acquisition_function='ei'
        )
        optimizer = BayesianOptimization(config)

        # Définir les bornes
        bounds = [(-5, 5), (-5, 5)]

        # Optimiser
        best_params, best_value = optimizer.optimize(
            objective,
            bounds,
            dimensions=['x1', 'x2']
        )
        ```
    """

    def __init__(self, config: Optional[BayesianOptimizationConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if not SCIPY_AVAILABLE:
            raise ImportError("SciPy n'est pas installé")

        self.config = config or BayesianOptimizationConfig()
        self.gp = None
        self.X = []
        self.y = []
        self.best_params = None
        self.best_value = float('inf')
        self.history: List[Dict[str, Any]] = []
        self.dimensions: List[str] = []
        self.bounds: List[Tuple[float, float]] = []

        logger.info(f"BayesianOptimization initialisé")

    def _initialize_gp(self, input_dim: int):
        """Initialise le processus gaussien"""
        self.gp = _GaussianProcess(
            input_dim=input_dim,
            use_gpu=self.config.use_gpu
        )

    def _objective_to_torch(self, objective: Callable, x: np.ndarray) -> float:
        """Convertit l'objectif pour PyTorch"""
        return objective(x)

    def _sample_initial_points(self, bounds: List[Tuple[float, float]], n_points: int) -> np.ndarray:
        """Échantillonne des points initiaux aléatoires"""
        X = np.zeros((n_points, len(bounds)))
        for i, (low, high) in enumerate(bounds):
            X[:, i] = np.random.uniform(low, high, n_points)
        return X

    def _optimize_acquisition(self, bounds: List[Tuple[float, float]]) -> np.ndarray:
        """
        Optimise la fonction d'acquisition.

        Returns:
            np.ndarray: Point recommandé
        """
        best_x = None
        best_acq = -float('inf')

        # Multi-restarts
        for _ in range(self.config.n_restarts):
            x0 = np.array([np.random.uniform(low, high) for low, high in bounds])

            # Optimisation
            result = minimize(
                lambda x: -self._acquisition(x),
                x0,
                method='L-BFGS-B',
                bounds=bounds
            )

            if result.success and -result.fun > best_acq:
                best_acq = -result.fun
                best_x = result.x

        return best_x

    def _acquisition(self, x: np.ndarray) -> float:
        """
        Calcule la fonction d'acquisition.

        Args:
            x: Point à évaluer

        Returns:
            float: Valeur de l'acquisition
        """
        if self.gp is None or len(self.X) == 0:
            return 0

        x_tensor = torch.FloatTensor(x).unsqueeze(0)
        mean, var = self.gp.predict(x_tensor)

        mean = mean.cpu().detach().numpy()
        std = np.sqrt(var.cpu().detach().numpy())

        best = np.min(self.y)

        if self.config.acquisition_function == 'ei':
            return _AcquisitionFunction.ei(mean, std, best, self.config.xi)
        elif self.config.acquisition_function == 'ucb':
            return _AcquisitionFunction.ucb(mean, std, self.config.kappa)
        elif self.config.acquisition_function == 'poi':
            return _AcquisitionFunction.poi(mean, std, best, self.config.xi)
        else:
            raise ValueError(f"Fonction d'acquisition non supportée: {self.config.acquisition_function}")

    def optimize(
        self,
        objective: Callable,
        bounds: List[Tuple[float, float]],
        dimensions: Optional[List[str]] = None,
        **kwargs
    ) -> Tuple[np.ndarray, float]:
        """
        Effectue l'optimisation bayésienne.

        Args:
            objective: Fonction objectif
            bounds: Bornes des paramètres
            dimensions: Noms des dimensions (optionnel)
            **kwargs: Arguments supplémentaires

        Returns:
            Tuple[np.ndarray, float]: (Meilleurs paramètres, Meilleure valeur)
        """
        self.bounds = bounds
        self.dimensions = dimensions or [f'x{i}' for i in range(len(bounds))]

        # Initialisation du GP
        self._initialize_gp(len(bounds))

        # Points initiaux
        n_initial = self.config.n_initial_points
        X_initial = self._sample_initial_points(bounds, n_initial)

        # Évaluation des points initiaux
        for i, x in enumerate(X_initial):
            y = objective(x)
            self.X.append(x)
            self.y.append(y)

            if y < self.best_value:
                self.best_value = y
                self.best_params = x

            self.history.append({
                'iteration': i,
                'params': dict(zip(self.dimensions, x)),
                'value': y,
                'best_value': self.best_value,
                'type': 'initial',
            })

            if self.config.verbose:
                logger.info(f"Initial {i+1}/{n_initial}: {dict(zip(self.dimensions, x))} -> {y:.6f}")

        # Boucle d'optimisation
        for i in range(self.config.n_iterations):
            # Mise à jour du GP
            X_tensor = torch.FloatTensor(self.X)
            y_tensor = torch.FloatTensor(self.y)

            try:
                self.gp.fit(X_tensor, y_tensor)
            except Exception as e:
                logger.error(f"Erreur de fit du GP: {e}")
                break

            # Optimisation de l'acquisition
            try:
                x_next = self._optimize_acquisition(bounds)
            except Exception as e:
                logger.error(f"Erreur d'optimisation de l'acquisition: {e}")
                break

            # Évaluation
            y_next = objective(x_next)

            # Mise à jour
            self.X.append(x_next)
            self.y.append(y_next)

            if y_next < self.best_value:
                self.best_value = y_next
                self.best_params = x_next

            self.history.append({
                'iteration': n_initial + i,
                'params': dict(zip(self.dimensions, x_next)),
                'value': y_next,
                'best_value': self.best_value,
                'type': 'iteration',
            })

            if self.config.verbose:
                logger.info(f"Iteration {i+1}/{self.config.n_iterations}: {dict(zip(self.dimensions, x_next))} -> {y_next:.6f}")

        return np.array(self.best_params), self.best_value

    def get_history(self) -> pd.DataFrame:
        """
        Retourne l'historique de l'optimisation.

        Returns:
            pd.DataFrame: Historique
        """
        return pd.DataFrame(self.history)

    def get_best_params(self) -> Dict[str, Any]:
        """
        Retourne les meilleurs paramètres.

        Returns:
            Dict[str, Any]: Meilleurs paramètres
        """
        if self.best_params is None:
            return {}
        return dict(zip(self.dimensions, self.best_params))

    def get_best_value(self) -> Optional[float]:
        """Retourne la meilleure valeur"""
        return self.best_value

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

            fig, axes = plt.subplots(2, 1, figsize=figsize)

            # Valeurs
            axes[0].plot(df.index, df['value'], 'b-', label='Valeur')
            axes[0].plot(df.index, df['best_value'], 'r-', label='Meilleure valeur')
            axes[0].set_xlabel('Itération')
            axes[0].set_ylabel('Valeur')
            axes[0].set_title('Convergence de l\'optimisation')
            axes[0].legend()
            axes[0].grid(True, alpha=0.3)

            # Meilleurs paramètres
            if len(self.dimensions) > 0:
                for dim in self.dimensions:
                    axes[1].plot(df.index, df['params'].apply(lambda x: x.get(dim, 0)), label=dim)
                axes[1].set_xlabel('Itération')
                axes[1].set_ylabel('Paramètres')
                axes[1].set_title('Évolution des paramètres')
                axes[1].legend()
                axes[1].grid(True, alpha=0.3)

            plt.tight_layout()
            plt.show()

        except Exception as e:
            logger.error(f"Erreur lors du tracé: {e}")

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde l'optimiseur sur le disque.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si la sauvegarde a réussi
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'X': self.X,
                'y': self.y,
                'best_params': self.best_params,
                'best_value': self.best_value,
                'history': self.history,
                'dimensions': self.dimensions,
                'bounds': self.bounds,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Optimiseur sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'BayesianOptimization':
        """
        Charge un optimiseur depuis le disque.

        Args:
            filepath: Chemin du fichier

        Returns:
            BayesianOptimization: Optimiseur chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = BayesianOptimizationConfig(**data['config'])
            optimizer = cls(config)

            optimizer.X = data.get('X', [])
            optimizer.y = data.get('y', [])
            optimizer.best_params = data.get('best_params')
            optimizer.best_value = data.get('best_value', float('inf'))
            optimizer.history = data.get('history', [])
            optimizer.dimensions = data.get('dimensions', [])
            optimizer.bounds = data.get('bounds', [])

            if optimizer.X:
                optimizer._initialize_gp(len(optimizer.X[0]))

            logger.info(f"Optimiseur chargé: {filepath}")
            return optimizer

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_bayesian_optimization(
    n_initial_points: int = 10,
    n_iterations: int = 50,
    acquisition_function: str = 'ei',
    **kwargs
) -> BayesianOptimization:
    """
    Factory pour créer un optimiseur bayésien.

    Args:
        n_initial_points: Nombre de points initiaux
        n_iterations: Nombre d'itérations
        acquisition_function: Fonction d'acquisition ('ei', 'ucb', 'poi')
        **kwargs: Arguments supplémentaires

    Returns:
        BayesianOptimization: Optimiseur bayésien
    """
    config = BayesianOptimizationConfig(
        n_initial_points=n_initial_points,
        n_iterations=n_iterations,
        acquisition_function=acquisition_function,
        **kwargs
    )
    return BayesianOptimization(config)


__all__ = [
    'BayesianOptimization',
    'BayesianOptimizationConfig',
    'create_bayesian_optimization',
]
