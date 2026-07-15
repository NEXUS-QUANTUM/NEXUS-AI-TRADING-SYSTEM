
# ai/optimization/grid_search.py
"""
NEXUS AI TRADING SYSTEM - Grid Search Module
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
import itertools
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    from sklearn.model_selection import ParameterGrid
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class GridSearchConfig:
    """Configuration pour Grid Search"""
    param_grid: Dict[str, List[Any]]
    scoring: Union[str, Callable] = 'neg_mean_squared_error'
    cv: int = 5
    n_jobs: int = -1
    verbose: int = 0
    pre_dispatch: Union[str, int] = '2*n_jobs'
    return_train_score: bool = False
    refit: bool = True
    error_score: float = np.nan
    random_state: Optional[int] = 42

    def __post_init__(self):
        if self.cv < 2:
            raise ValueError("cv doit être >= 2")
        if not self.param_grid:
            raise ValueError("param_grid ne peut pas être vide")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'param_grid': self.param_grid,
            'scoring': self.scoring if isinstance(self.scoring, str) else 'custom',
            'cv': self.cv,
            'n_jobs': self.n_jobs,
            'verbose': self.verbose,
            'pre_dispatch': self.pre_dispatch,
            'return_train_score': self.return_train_score,
            'refit': self.refit,
            'error_score': self.error_score,
            'random_state': self.random_state,
        }


@dataclass
class GridSearchResult:
    """Résultat de Grid Search"""
    best_params: Dict[str, Any]
    best_score: float
    best_index: int
    cv_results: Dict[str, Any]
    n_combinations: int
    total_time: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'best_params': self.best_params,
            'best_score': self.best_score,
            'best_index': self.best_index,
            'cv_results': self.cv_results,
            'n_combinations': self.n_combinations,
            'total_time': self.total_time,
            'timestamp': self.timestamp.isoformat(),
        }


class GridSearch:
    """
    Grid Search pour l'optimisation des hyperparamètres.

    Features:
    - Recherche exhaustive sur une grille de paramètres
    - Validation croisée
    - Parallélisation
    - Score personnalisé
    - Historique complet
    - Sauvegarde/Chargement
    - Visualisation

    Example:
        ```python
        def objective(params):
            return -(params['x1']**2 + params['x2']**2)

        param_grid = {
            'x1': [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5],
            'x2': [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5],
        }

        config = GridSearchConfig(
            param_grid=param_grid,
            scoring='neg_mean_squared_error',
            cv=3
        )
        gs = GridSearch(config)
        result = gs.fit(objective)
        ```
    """

    def __init__(self, config: Optional[GridSearchConfig] = None):
        self.config = config or GridSearchConfig()
        self.results: List[Dict[str, Any]] = []
        self.best_params_: Optional[Dict[str, Any]] = None
        self.best_score_: Optional[float] = None
        self.best_index_: Optional[int] = None
        self.cv_results_: Dict[str, Any] = {}
        self.n_combinations_ = 0
        self.is_fitted = False

        logger.info(f"GridSearch initialisé avec {self._count_combinations()} combinaisons")

    def _count_combinations(self) -> int:
        """Compte le nombre de combinaisons de paramètres"""
        return np.prod([len(v) for v in self.config.param_grid.values()])

    def _generate_combinations(self) -> List[Dict[str, Any]]:
        """Génère toutes les combinaisons de paramètres"""
        keys = self.config.param_grid.keys()
        values = self.config.param_grid.values()
        combinations = list(itertools.product(*values))
        return [dict(zip(keys, combo)) for combo in combinations]

    def _evaluate_combination(
        self,
        params: Dict[str, Any],
        objective: Callable,
        cv: int
    ) -> Dict[str, Any]:
        """
        Évalue une combinaison de paramètres.

        Args:
            params: Paramètres à évaluer
            objective: Fonction objectif
            cv: Nombre de folds

        Returns:
            Dict[str, Any]: Résultats de l'évaluation
        """
        scores = []
        times = []
        start_time = time.time()

        for fold in range(cv):
            try:
                score = objective(params, fold=fold)
                scores.append(score)
                times.append(time.time() - start_time)
            except Exception as e:
                logger.warning(f"Erreur avec params {params}, fold {fold}: {e}")
                scores.append(self.config.error_score)

        mean_score = np.mean(scores)
        std_score = np.std(scores)
        total_time = time.time() - start_time

        return {
            'params': params,
            'scores': scores,
            'mean_score': mean_score,
            'std_score': std_score,
            'total_time': total_time,
        }

    def fit(
        self,
        objective: Callable,
        cv: Optional[int] = None,
        **kwargs
    ) -> 'GridSearch':
        """
        Effectue la recherche sur la grille.

        Args:
            objective: Fonction objectif
            cv: Nombre de folds (optionnel)
            **kwargs: Arguments supplémentaires

        Returns:
            GridSearch: Instance entraînée
        """
        cv = cv or self.config.cv

        # Génération des combinaisons
        combinations = self._generate_combinations()
        self.n_combinations_ = len(combinations)

        logger.info(f"Évaluation de {self.n_combinations_} combinaisons")

        # Parallélisation
        n_jobs = self.config.n_jobs
        if n_jobs == -1:
            import multiprocessing
            n_jobs = multiprocessing.cpu_count()

        results = []

        if n_jobs > 1:
            # Exécution parallèle
            with ThreadPoolExecutor(max_workers=n_jobs) as executor:
                futures = {}
                for params in combinations:
                    future = executor.submit(
                        self._evaluate_combination,
                        params,
                        objective,
                        cv
                    )
                    futures[future] = params

                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                        if self.config.verbose > 0:
                            logger.info(f"Combiné: {result['params']} -> {result['mean_score']:.4f} (±{result['std_score']:.4f})")
                    except Exception as e:
                        logger.error(f"Erreur lors de l'évaluation: {e}")
                        continue
        else:
            # Exécution séquentielle
            for i, params in enumerate(combinations):
                if self.config.verbose > 0:
                    logger.info(f"Combinaison {i+1}/{self.n_combinations_}")

                try:
                    result = self._evaluate_combination(params, objective, cv)
                    results.append(result)
                    if self.config.verbose > 0:
                        logger.info(f"Combiné: {params} -> {result['mean_score']:.4f} (±{result['std_score']:.4f})")
                except Exception as e:
                    logger.error(f"Erreur lors de l'évaluation: {e}")
                    continue

        self.results = results

        # Meilleure combinaison
        best_result = min(results, key=lambda x: x['mean_score'])
        self.best_params_ = best_result['params']
        self.best_score_ = best_result['mean_score']

        # Construction des résultats CV
        self._build_cv_results()

        self.is_fitted = True

        logger.info(f"Meilleurs paramètres: {self.best_params_}")
        logger.info(f"Meilleur score: {self.best_score_:.6f}")

        return self

    def _build_cv_results(self):
        """Construit les résultats de validation croisée"""
        if not self.results:
            return

        # Extraction des données
        params_list = [r['params'] for r in self.results]
        mean_scores = [r['mean_score'] for r in self.results]
        std_scores = [r['std_score'] for r in self.results]
        total_times = [r['total_time'] for r in self.results]

        # Construction du dictionnaire
        self.cv_results_ = {
            'params': params_list,
            'mean_test_score': mean_scores,
            'std_test_score': std_scores,
            'mean_fit_time': total_times,
        }

        # Ajout des scores par fold
        n_folds = len(self.results[0]['scores'])
        for i in range(n_folds):
            self.cv_results_[f'split{i}_test_score'] = [
                r['scores'][i] if i < len(r['scores']) else np.nan
                for r in self.results
            ]

        self.best_index_ = np.argmin(mean_scores)

    def predict(self, X: Any) -> Any:
        """
        Prédiction avec les meilleurs paramètres.
        À surcharger selon l'application.

        Args:
            X: Données d'entrée

        Returns:
            Any: Prédictions
        """
        raise NotImplementedError("predict doit être implémenté par la sous-classe")

    def get_best_params(self) -> Dict[str, Any]:
        """Retourne les meilleurs paramètres"""
        return self.best_params_

    def get_best_score(self) -> Optional[float]:
        """Retourne le meilleur score"""
        return self.best_score_

    def get_cv_results(self) -> Dict[str, Any]:
        """Retourne les résultats de la validation croisée"""
        return self.cv_results_

    def get_results(self) -> pd.DataFrame:
        """
        Retourne tous les résultats sous forme de DataFrame.

        Returns:
            pd.DataFrame: Résultats
        """
        if not self.results:
            return pd.DataFrame()

        rows = []
        for r in self.results:
            row = r['params'].copy()
            row['mean_score'] = r['mean_score']
            row['std_score'] = r['std_score']
            row['total_time'] = r['total_time']
            rows.append(row)

        return pd.DataFrame(rows)

    def plot_results(self, figsize: Tuple[int, int] = (12, 6)) -> None:
        """
        Affiche les résultats de la recherche.

        Args:
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        if not self.results:
            logger.warning("Aucun résultat à afficher")
            return

        try:
            df = self.get_results()

            fig, axes = plt.subplots(1, 2, figsize=figsize)

            # Distribution des scores
            axes[0].hist(df['mean_score'], bins=20, edgecolor='black', alpha=0.7)
            axes[0].axvline(x=self.best_score_, color='r', linestyle='--', label='Meilleur score')
            axes[0].set_xlabel('Score')
            axes[0].set_ylabel('Fréquence')
            axes[0].set_title('Distribution des scores')
            axes[0].legend()
            axes[0].grid(True, alpha=0.3)

            # Évolution par combinaison
            axes[1].plot(df.index, df['mean_score'], 'b-', label='Score')
            axes[1].fill_between(
                df.index,
                df['mean_score'] - df['std_score'],
                df['mean_score'] + df['std_score'],
                alpha=0.2,
                color='blue',
                label='Écart-type'
            )
            axes[1].axhline(y=self.best_score_, color='r', linestyle='--', label='Meilleur score')
            axes[1].set_xlabel('Combinaison')
            axes[1].set_ylabel('Score')
            axes[1].set_title('Scores par combinaison')
            axes[1].legend()
            axes[1].grid(True, alpha=0.3)

            plt.tight_layout()
            plt.show()

        except Exception as e:
            logger.error(f"Erreur lors du tracé: {e}")

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde le résultat de la recherche.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si la sauvegarde a réussi
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            result = GridSearchResult(
                best_params=self.best_params_,
                best_score=self.best_score_,
                best_index=self.best_index_,
                cv_results=self.cv_results_,
                n_combinations=self.n_combinations_,
                total_time=self._get_total_time(),
            )

            data = {
                'config': self.config.to_dict(),
                'result': result.to_dict(),
                'results': self.results,
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

    def _get_total_time(self) -> float:
        """Calcule le temps total"""
        if self.results:
            return sum(r['total_time'] for r in self.results)
        return 0.0

    @classmethod
    def load(cls, filepath: str) -> 'GridSearch':
        """
        Charge un résultat de recherche.

        Args:
            filepath: Chemin du fichier

        Returns:
            GridSearch: Instance chargée
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = GridSearchConfig(**data['config'])
            gs = cls(config)

            gs.results = data.get('results', [])
            gs.is_fitted = data.get('is_fitted', False)

            if gs.results:
                best_result = min(gs.results, key=lambda x: x['mean_score'])
                gs.best_params_ = best_result['params']
                gs.best_score_ = best_result['mean_score']
                gs._build_cv_results()

            logger.info(f"Résultat chargé: {filepath}")
            return gs

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_grid_search(
    param_grid: Dict[str, List[Any]],
    scoring: Union[str, Callable] = 'neg_mean_squared_error',
    cv: int = 5,
    n_jobs: int = -1,
    **kwargs
) -> GridSearch:
    """
    Factory pour créer une recherche par grille.

    Args:
        param_grid: Grille de paramètres
        scoring: Métrique de scoring
        cv: Nombre de folds
        n_jobs: Nombre de jobs parallèles
        **kwargs: Arguments supplémentaires

    Returns:
        GridSearch: Recherche par grille
    """
    config = GridSearchConfig(
        param_grid=param_grid,
        scoring=scoring,
        cv=cv,
        n_jobs=n_jobs,
        **kwargs
    )
    return GridSearch(config)


__all__ = [
    'GridSearch',
    'GridSearchConfig',
    'GridSearchResult',
    'create_grid_search',
]
