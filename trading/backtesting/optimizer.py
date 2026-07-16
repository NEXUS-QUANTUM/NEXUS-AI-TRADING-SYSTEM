"""
NEXUS AI TRADING SYSTEM - Strategy Optimizer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/backtesting/optimizer.py
Description: Optimiseur de paramètres pour les stratégies de trading.
             Supporte la recherche par grille, l'optimisation bayésienne,
             les algorithmes génétiques et l'optimisation par essaims.
"""

import logging
import time
import itertools
import random
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import partial

import numpy as np
import pandas as pd
from scipy.optimize import minimize, differential_evolution
from scipy.stats import norm, uniform
from tqdm import tqdm
import optuna
from skopt import gp_minimize
from skopt.space import Real, Integer, Categorical

from trading.backtesting.backtest_engine import BacktestEngine, BacktestConfig, BacktestResult
from trading.backtesting.metrics_calculator import MetricsCalculator
from trading.strategies.factory import StrategyFactory
from shared.exceptions import OptimizationError
from shared.helpers.number_helpers import round_decimal

# Configuration du logging
logger = logging.getLogger(__name__)


@dataclass
class OptimizationConfig:
    """
    Configuration de l'optimisation.
    """
    # Paramètres de la stratégie
    strategy_name: str
    param_space: Dict[str, Any]  # {nom: (min, max, step) ou (min, max) ou [values]}
    
    # Paramètres de backtesting
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    timeframe: str = '1h'
    
    # Méthode d'optimisation
    method: str = 'grid'  # 'grid', 'random', 'bayesian', 'genetic', 'optuna', 'particle_swarm'
    
    # Paramètres pour les méthodes
    n_iterations: int = 100
    n_random_starts: int = 10
    n_population: int = 20
    n_generations: int = 50
    crossover_rate: float = 0.7
    mutation_rate: float = 0.1
    patience: int = 20  # Early stopping
    
    # Paramètres pour l'optimisation parallèle
    parallel: bool = True
    n_workers: int = 4
    
    # Paramètres de la fonction objectif
    objective: str = 'sharpe_ratio'  # 'sharpe_ratio', 'total_return', 'profit_factor', 'calmar_ratio', 'custom'
    maximize: bool = True
    penalty: float = 0.1  # Pénalité pour les stratégies risquées
    
    # Paramètres de contrainte
    min_trades: int = 10
    max_trades: int = 1000
    max_drawdown_limit: float = 0.20
    min_win_rate: float = 0.4
    min_profit_factor: float = 1.2
    
    # Paramètres de sortie
    save_results: bool = True
    output_dir: str = "data/optimization_results/"
    verbose: bool = True
    
    def __post_init__(self):
        """Validation des paramètres."""
        if self.strategy_name not in StrategyFactory.get_available_strategies():
            raise OptimizationError(f"Stratégie '{self.strategy_name}' non trouvée")
        
        if self.method not in ['grid', 'random', 'bayesian', 'genetic', 'optuna', 'particle_swarm']:
            raise OptimizationError(f"Méthode '{self.method}' non supportée")
        
        if self.n_iterations < 1:
            raise OptimizationError("n_iterations doit être >= 1")
        
        if self.objective not in ['sharpe_ratio', 'total_return', 'profit_factor', 'calmar_ratio']:
            if self.objective != 'custom':
                raise OptimizationError(f"Objectif '{self.objective}' non supporté")


@dataclass
class OptimizationResult:
    """
    Résultats de l'optimisation.
    """
    # Meilleurs paramètres
    best_params: Dict[str, Any] = field(default_factory=dict)
    best_score: float = 0.0
    best_result: Optional[BacktestResult] = None
    
    # Historique des évaluations
    history: List[Dict[str, Any]] = field(default_factory=list)
    param_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Statistiques
    total_evaluations: int = 0
    total_time: float = 0.0
    
    # Métadonnées
    config: Optional[OptimizationConfig] = None
    convergence_curve: List[float] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit les résultats en dictionnaire."""
        return {
            'best_params': self.best_params,
            'best_score': self.best_score,
            'best_result': self.best_result.to_dict() if self.best_result else None,
            'total_evaluations': self.total_evaluations,
            'total_time': self.total_time,
            'n_history': len(self.history)
        }
    
    def summary(self) -> str:
        """Retourne un résumé lisible des résultats."""
        lines = []
        lines.append("=" * 70)
        lines.append("OPTIMIZATION RESULTS")
        lines.append("=" * 70)
        lines.append(f"Total Evaluations:    {self.total_evaluations}")
        lines.append(f"Total Time:           {self.total_time:.2f}s")
        lines.append(f"Best Score:           {self.best_score:.4f}")
        lines.append("")
        lines.append("BEST PARAMETERS:")
        for name, value in self.best_params.items():
            lines.append(f"  {name}:             {value}")
        
        if self.best_result:
            lines.append("")
            lines.append("PERFORMANCE WITH BEST PARAMETERS:")
            lines.append(f"  Total Return:       {self.best_result.total_return:.2%}")
            lines.append(f"  Sharpe Ratio:       {self.best_result.sharpe_ratio:.3f}")
            lines.append(f"  Win Rate:           {self.best_result.win_rate:.2%}")
            lines.append(f"  Max Drawdown:       {self.best_result.max_drawdown_pct:.2%}")
            lines.append(f"  Total Trades:       {self.best_result.total_trades}")
        
        lines.append("=" * 70)
        return "\n".join(lines)


class ObjectiveFunction:
    """
    Fonction objectif pour l'optimisation des stratégies.
    """
    
    def __init__(
        self,
        config: OptimizationConfig,
        metrics_calculator: Optional[MetricsCalculator] = None
    ):
        """
        Initialise la fonction objectif.
        
        Args:
            config: Configuration de l'optimisation.
            metrics_calculator: Calculateur de métriques.
        """
        self.config = config
        self.metrics_calculator = metrics_calculator or MetricsCalculator()
        
        # Cache pour éviter de réévaluer les mêmes paramètres
        self._cache = {}
        self._evaluations = 0
        
        logger.info("ObjectiveFunction initialisée")
    
    def _check_constraints(self, result: BacktestResult) -> bool:
        """
        Vérifie si les résultats respectent les contraintes.
        
        Args:
            result: Résultats du backtesting.
            
        Returns:
            True si les contraintes sont respectées.
        """
        # Nombre de trades
        if result.total_trades < self.config.min_trades:
            return False
        if result.total_trades > self.config.max_trades:
            return False
        
        # Drawdown maximum
        if result.max_drawdown_pct > self.config.max_drawdown_limit:
            return False
        
        # Win rate minimum
        if result.win_rate < self.config.min_win_rate:
            return False
        
        # Profit factor minimum
        if result.profit_factor < self.config.min_profit_factor:
            return False
        
        return True
    
    def _calculate_score(self, result: BacktestResult) -> float:
        """
        Calcule le score selon l'objectif choisi.
        
        Args:
            result: Résultats du backtesting.
            
        Returns:
            Score (plus élevé = meilleur).
        """
        if self.config.objective == 'sharpe_ratio':
            return result.sharpe_ratio
        
        elif self.config.objective == 'total_return':
            return result.total_return
        
        elif self.config.objective == 'profit_factor':
            return result.profit_factor
        
        elif self.config.objective == 'calmar_ratio':
            return result.calmar_ratio
        
        else:
            # Custom: combinaison pondérée
            score = (
                0.4 * result.sharpe_ratio +
                0.3 * result.total_return +
                0.2 * result.profit_factor +
                0.1 * (1 - result.max_drawdown_pct)
            )
            return score
    
    def _apply_penalty(self, score: float, result: BacktestResult) -> float:
        """
        Applique une pénalité pour les stratégies risquées.
        
        Args:
            score: Score initial.
            result: Résultats du backtesting.
            
        Returns:
            Score pénalisé.
        """
        penalty = 0.0
        
        # Pénalité pour drawdown élevé
        if result.max_drawdown_pct > 0.15:
            penalty += self.config.penalty * (result.max_drawdown_pct - 0.15) / 0.15
        
        # Pénalité pour faible win rate
        if result.win_rate < 0.4:
            penalty += self.config.penalty * (0.4 - result.win_rate) / 0.4
        
        # Pénalité pour trading trop fréquent
        if result.total_trades > 500:
            penalty += self.config.penalty * 0.1
        
        return score - penalty
    
    def evaluate(self, params: Dict[str, Any]) -> float:
        """
        Évalue une combinaison de paramètres.
        
        Args:
            params: Paramètres à évaluer.
            
        Returns:
            Score de la combinaison.
        """
        # Génération d'une clé de cache
        cache_key = tuple(sorted(params.items()))
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            # Création de la configuration de backtest
            backtest_config = BacktestConfig(
                symbol=self.config.symbol,
                start_date=self.config.start_date,
                end_date=self.config.end_date,
                initial_capital=self.config.initial_capital,
                timeframe=self.config.timeframe,
                strategy_name=self.config.strategy_name,
                strategy_params=params
            )
            
            # Exécution du backtest
            engine = BacktestEngine(backtest_config)
            result = engine.run()
            
            # Vérification des contraintes
            if not self._check_constraints(result):
                score = -float('inf')
            else:
                # Calcul du score
                score = self._calculate_score(result)
                
                # Application de la pénalité
                score = self._apply_penalty(score, result)
                
                # Maximisation ou minimisation
                if not self.config.maximize:
                    score = -score
            
            # Mise en cache
            self._cache[cache_key] = score
            self._evaluations += 1
            
            return score
            
        except Exception as e:
            logger.warning(f"Erreur lors de l'évaluation: {e}")
            return -float('inf')
    
    def evaluate_with_result(self, params: Dict[str, Any]) -> Tuple[float, BacktestResult]:
        """
        Évalue une combinaison et retourne le résultat complet.
        
        Args:
            params: Paramètres à évaluer.
            
        Returns:
            Tuple (score, resultat_backtest).
        """
        # Génération d'une clé de cache
        cache_key = tuple(sorted(params.items()))
        
        # Exécution du backtest
        backtest_config = BacktestConfig(
            symbol=self.config.symbol,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            initial_capital=self.config.initial_capital,
            timeframe=self.config.timeframe,
            strategy_name=self.config.strategy_name,
            strategy_params=params
        )
        
        engine = BacktestEngine(backtest_config)
        result = engine.run()
        
        # Calcul du score
        score = self._calculate_score(result)
        
        # Vérification des contraintes
        if not self._check_constraints(result):
            score = -float('inf')
        else:
            score = self._apply_penalty(score, result)
            if not self.config.maximize:
                score = -score
        
        return score, result


class StrategyOptimizer:
    """
    Optimiseur de stratégies de trading.
    Supporte plusieurs méthodes d'optimisation.
    """
    
    def __init__(self, config: OptimizationConfig):
        """
        Initialise l'optimiseur.
        
        Args:
            config: Configuration de l'optimisation.
        """
        self.config = config
        self.objective = ObjectiveFunction(config)
        
        # Résultats
        self.best_params = None
        self.best_score = -float('inf')
        self.best_result = None
        
        # Historique
        self.history = []
        self.convergence_curve = []
        
        logger.info("StrategyOptimizer initialisé")
        logger.info(f"Stratégie: {config.strategy_name}")
        logger.info(f"Méthode: {config.method}")
        logger.info(f"Objectif: {config.objective}")
    
    # ============================================================
    # MÉTHODES D'OPTIMISATION
    # ============================================================
    
    def optimize(self) -> OptimizationResult:
        """
        Lance l'optimisation selon la méthode configurée.
        
        Returns:
            Résultats de l'optimisation.
        """
        start_time = time.time()
        
        logger.info(f"Début de l'optimisation avec {self.config.method}")
        
        if self.config.method == 'grid':
            result = self._grid_search()
        elif self.config.method == 'random':
            result = self._random_search()
        elif self.config.method == 'bayesian':
            result = self._bayesian_optimization()
        elif self.config.method == 'genetic':
            result = self._genetic_algorithm()
        elif self.config.method == 'optuna':
            result = self._optuna_optimization()
        elif self.config.method == 'particle_swarm':
            result = self._particle_swarm()
        else:
            raise OptimizationError(f"Méthode '{self.config.method}' non supportée")
        
        result.total_time = time.time() - start_time
        result.config = self.config
        
        logger.info(f"Optimisation terminée en {result.total_time:.2f}s")
        logger.info(f"Meilleur score: {result.best_score:.4f}")
        
        return result
    
    def _update_best(
        self,
        params: Dict[str, Any],
        score: float,
        result: Optional[BacktestResult] = None
    ) -> None:
        """
        Met à jour les meilleurs paramètres si nécessaire.
        
        Args:
            params: Paramètres évalués.
            score: Score obtenu.
            result: Résultats du backtesting.
        """
        if score > self.best_score and score != -float('inf'):
            self.best_score = score
            self.best_params = params.copy()
            self.best_result = result
            
            if self.config.verbose:
                logger.info(f"Nouveau meilleur score: {score:.4f} avec {params}")
    
    def _evaluate_params(self, params: Dict[str, Any]) -> float:
        """
        Évalue des paramètres et met à jour l'historique.
        
        Args:
            params: Paramètres à évaluer.
            
        Returns:
            Score obtenu.
        """
        score = self.objective.evaluate(params)
        
        # Enregistrement dans l'historique
        self.history.append({
            'params': params.copy(),
            'score': score,
            'timestamp': time.time()
        })
        self.convergence_curve.append(max(self.convergence_curve or [score], score))
        
        return score
    
    def _evaluate_params_with_result(self, params: Dict[str, Any]) -> Tuple[float, BacktestResult]:
        """
        Évalue des paramètres et retourne le résultat complet.
        
        Args:
            params: Paramètres à évaluer.
            
        Returns:
            Tuple (score, resultat_backtest).
        """
        score, result = self.objective.evaluate_with_result(params)
        
        # Enregistrement dans l'historique
        self.history.append({
            'params': params.copy(),
            'score': score,
            'result': result,
            'timestamp': time.time()
        })
        self.convergence_curve.append(max(self.convergence_curve or [score], score))
        
        return score, result
    
    # ============================================================
    # RECHERCHE PAR GRILLE
    # ============================================================
    
    def _grid_search(self) -> OptimizationResult:
        """
        Recherche par grille exhaustive.
        
        Returns:
            Résultats de l'optimisation.
        """
        logger.info("Recherche par grille...")
        
        # Génération des combinaisons
        param_grid = self._generate_grid()
        total_combinations = len(param_grid)
        
        logger.info(f"Nombre de combinaisons: {total_combinations}")
        
        # Évaluation
        with tqdm(total=total_combinations, desc="Grid Search") as pbar:
            for params in param_grid:
                score = self._evaluate_params(params)
                self._update_best(params, score)
                pbar.update(1)
        
        return self._build_result()
    
    def _generate_grid(self) -> List[Dict[str, Any]]:
        """
        Génère toutes les combinaisons de la grille.
        
        Returns:
            Liste des combinaisons de paramètres.
        """
        param_values = []
        param_names = []
        
        for name, spec in self.config.param_space.items():
            param_names.append(name)
            
            if isinstance(spec, list):
                # Valeurs discrètes
                values = spec
            elif isinstance(spec, tuple):
                if len(spec) == 3:
                    # (min, max, step)
                    min_val, max_val, step = spec
                    values = np.arange(min_val, max_val + step, step).tolist()
                else:
                    # (min, max)
                    min_val, max_val = spec
                    # 10 points par défaut
                    values = np.linspace(min_val, max_val, 10).tolist()
            else:
                values = [spec]
            
            param_values.append(values)
        
        # Toutes les combinaisons
        combinations = list(itertools.product(*param_values))
        
        return [
            {param_names[i]: combo[i] for i in range(len(param_names))}
            for combo in combinations
        ]
    
    # ============================================================
    # RECHERCHE ALÉATOIRE
    # ============================================================
    
    def _random_search(self) -> OptimizationResult:
        """
        Recherche aléatoire.
        
        Returns:
            Résultats de l'optimisation.
        """
        logger.info("Recherche aléatoire...")
        logger.info(f"Nombre d'itérations: {self.config.n_iterations}")
        
        for i in range(self.config.n_iterations):
            # Génération aléatoire des paramètres
            params = self._generate_random_params()
            score = self._evaluate_params(params)
            self._update_best(params, score)
            
            if (i + 1) % 10 == 0 and self.config.verbose:
                logger.debug(f"Itération {i+1}/{self.config.n_iterations}, meilleur score: {self.best_score:.4f}")
        
        return self._build_result()
    
    def _generate_random_params(self) -> Dict[str, Any]:
        """
        Génère des paramètres aléatoires.
        
        Returns:
            Paramètres générés.
        """
        params = {}
        
        for name, spec in self.config.param_space.items():
            if isinstance(spec, list):
                params[name] = random.choice(spec)
            elif isinstance(spec, tuple):
                if len(spec) == 2:
                    min_val, max_val = spec
                    if isinstance(min_val, int) and isinstance(max_val, int):
                        params[name] = random.randint(min_val, max_val)
                    else:
                        params[name] = random.uniform(min_val, max_val)
                else:
                    params[name] = spec[0]  # Valeur par défaut
            else:
                params[name] = spec
        
        return params
    
    # ============================================================
    # OPTIMISATION BAYÉSIENNE
    # ============================================================
    
    def _bayesian_optimization(self) -> OptimizationResult:
        """
        Optimisation bayésienne avec scikit-optimize.
        
        Returns:
            Résultats de l'optimisation.
        """
        try:
            from skopt import gp_minimize
        except ImportError:
            raise OptimizationError("scikit-optimize non installé")
        
        logger.info("Optimisation bayésienne...")
        
        # Définition de l'espace de recherche
        dimensions = []
        param_names = []
        
        for name, spec in self.config.param_space.items():
            param_names.append(name)
            
            if isinstance(spec, list):
                dimensions.append(Categorical(spec, name=name))
            elif isinstance(spec, tuple):
                if len(spec) == 2:
                    min_val, max_val = spec
                    if isinstance(min_val, int) and isinstance(max_val, int):
                        dimensions.append(Integer(min_val, max_val, name=name))
                    else:
                        dimensions.append(Real(min_val, max_val, name=name))
                else:
                    dimensions.append(Real(spec[0], spec[1], name=name))
            else:
                # Valeur fixe
                dimensions.append(Real(spec, spec, name=name))
        
        # Fonction objectif pour scikit-optimize
        def objective_skopt(params_list):
            params = {param_names[i]: params_list[i] for i in range(len(param_names))}
            score = self._evaluate_params(params)
            self._update_best(params, score)
            return -score if self.config.maximize else score
        
        # Optimisation
        result = gp_minimize(
            func=objective_skopt,
            dimensions=dimensions,
            n_calls=self.config.n_iterations,
            n_initial_points=self.config.n_random_starts,
            acq_func='EI',  # Expected Improvement
            random_state=42
        )
        
        # Récupération des meilleurs paramètres
        best_params = {param_names[i]: result.x[i] for i in range(len(param_names))}
        best_score = -result.fun if self.config.maximize else result.fun
        
        return self._build_result(best_params, best_score)
    
    # ============================================================
    # ALGORITHME GÉNÉTIQUE
    # ============================================================
    
    def _genetic_algorithm(self) -> OptimizationResult:
        """
        Algorithme génétique avec scipy.
        
        Returns:
            Résultats de l'optimisation.
        """
        try:
            from scipy.optimize import differential_evolution
        except ImportError:
            raise OptimizationError("scipy non installé")
        
        logger.info("Algorithme génétique...")
        
        # Définition des bornes
        bounds = []
        param_names = []
        
        for name, spec in self.config.param_space.items():
            param_names.append(name)
            
            if isinstance(spec, list):
                # Pour les catégories, on utilise l'index
                bounds.append((0, len(spec) - 1))
            elif isinstance(spec, tuple):
                if len(spec) == 2:
                    min_val, max_val = spec
                    bounds.append((min_val, max_val))
                else:
                    bounds.append((spec[0], spec[1]))
            else:
                bounds.append((spec, spec))
        
        # Fonction objectif pour differential_evolution
        def objective_de(params_list):
            params = {}
            for i, name in enumerate(param_names):
                spec = self.config.param_space[name]
                value = params_list[i]
                
                if isinstance(spec, list):
                    # Convertir l'index en valeur
                    value = spec[int(round(value))]
                elif isinstance(spec, tuple) and len(spec) == 3:
                    # Arrondir si step est défini
                    min_val, max_val, step = spec
                    value = min_val + round((value - min_val) / step) * step
                
                params[name] = value
            
            score = self._evaluate_params(params)
            self._update_best(params, score)
            return -score if self.config.maximize else score
        
        # Optimisation
        result = differential_evolution(
            func=objective_de,
            bounds=bounds,
            maxiter=self.config.n_generations,
            popsize=self.config.n_population,
            mutation=(0.5, 1.0),
            recombination=0.7,
            seed=42,
            disp=False
        )
        
        return self._build_result()
    
    # ============================================================
    # OPTUNA
    # ============================================================
    
    def _optuna_optimization(self) -> OptimizationResult:
        """
        Optimisation avec Optuna.
        
        Returns:
            Résultats de l'optimisation.
        """
        try:
            import optuna
        except ImportError:
            raise OptimizationError("optuna non installé")
        
        logger.info("Optimisation Optuna...")
        
        def objective_optuna(trial):
            params = {}
            
            for name, spec in self.config.param_space.items():
                if isinstance(spec, list):
                    params[name] = trial.suggest_categorical(name, spec)
                elif isinstance(spec, tuple):
                    if len(spec) == 2:
                        min_val, max_val = spec
                        if isinstance(min_val, int) and isinstance(max_val, int):
                            params[name] = trial.suggest_int(name, min_val, max_val)
                        else:
                            params[name] = trial.suggest_float(name, min_val, max_val)
                    else:
                        params[name] = trial.suggest_float(name, spec[0], spec[1])
                else:
                    params[name] = spec
            
            score = self._evaluate_params(params)
            self._update_best(params, score)
            
            return -score if self.config.maximize else score
        
        # Création de l'étude
        study = optuna.create_study(
            direction='maximize' if self.config.maximize else 'minimize',
            sampler=optuna.samplers.TPESampler(seed=42),
            pruner=optuna.pruners.MedianPruner()
        )
        
        # Optimisation
        study.optimize(
            objective_optuna,
            n_trials=self.config.n_iterations,
            n_jobs=self.config.n_workers if self.config.parallel else 1,
            show_progress_bar=True
        )
        
        # Récupération des meilleurs paramètres
        best_trial = study.best_trial
        best_params = best_trial.params
        best_score = best_trial.value
        
        return self._build_result(best_params, best_score)
    
    # ============================================================
    # OPTIMISATION PAR ESSAIMS (PARTICLE SWARM)
    # ============================================================
    
    def _particle_swarm(self) -> OptimizationResult:
        """
        Optimisation par essaim de particules.
        
        Returns:
            Résultats de l'optimisation.
        """
        logger.info("Optimisation par essaim de particules...")
        
        # Initialisation des particules
        n_particles = self.config.n_population
        n_params = len(self.config.param_space)
        
        # Génération des bornes
        bounds = []
        param_names = []
        
        for name, spec in self.config.param_space.items():
            param_names.append(name)
            
            if isinstance(spec, list):
                bounds.append((0, len(spec) - 1))
            elif isinstance(spec, tuple):
                if len(spec) == 2:
                    bounds.append((spec[0], spec[1]))
                else:
                    bounds.append((spec[0], spec[1]))
            else:
                bounds.append((spec, spec))
        
        # Particules
        positions = np.random.uniform(
            [b[0] for b in bounds],
            [b[1] for b in bounds],
            (n_particles, n_params)
        )
        velocities = np.random.uniform(-1, 1, (n_particles, n_params))
        
        # Meilleures positions
        personal_best_pos = positions.copy()
        personal_best_scores = np.full(n_particles, -float('inf'))
        
        global_best_pos = None
        global_best_score = -float('inf')
        
        # Paramètres PSO
        w = 0.7  # Inertie
        c1 = 1.5  # Cognitif
        c2 = 1.5  # Social
        
        # Évaluation initiale
        for i in range(n_particles):
            params = self._pso_params_to_dict(param_names, positions[i], bounds)
            score = self._evaluate_params(params)
            
            personal_best_scores[i] = score
            self._update_best(params, score)
            
            if score > global_best_score:
                global_best_score = score
                global_best_pos = positions[i].copy()
        
        # Boucle d'optimisation
        for generation in tqdm(range(self.config.n_generations), desc="PSO"):
            for i in range(n_particles):
                # Mise à jour de la vélocité
                r1, r2 = np.random.random(2)
                velocities[i] = (
                    w * velocities[i] +
                    c1 * r1 * (personal_best_pos[i] - positions[i]) +
                    c2 * r2 * (global_best_pos - positions[i])
                )
                
                # Mise à jour de la position
                positions[i] += velocities[i]
                positions[i] = np.clip(
                    positions[i],
                    [b[0] for b in bounds],
                    [b[1] for b in bounds]
                )
                
                # Évaluation
                params = self._pso_params_to_dict(param_names, positions[i], bounds)
                score = self._evaluate_params(params)
                
                # Mise à jour personnelle
                if score > personal_best_scores[i]:
                    personal_best_scores[i] = score
                    personal_best_pos[i] = positions[i].copy()
                
                # Mise à jour globale
                if score > global_best_score:
                    global_best_score = score
                    global_best_pos = positions[i].copy()
                    self._update_best(params, score)
            
            # Early stopping
            if generation > self.config.patience and len(self.convergence_curve) > self.config.patience:
                recent = self.convergence_curve[-self.config.patience:]
                if max(recent) - min(recent) < 1e-6:
                    logger.info(f"Early stopping à la génération {generation}")
                    break
        
        return self._build_result()
    
    def _pso_params_to_dict(
        self,
        names: List[str],
        values: np.ndarray,
        bounds: List[Tuple[float, float]]
    ) -> Dict[str, Any]:
        """
        Convertit les valeurs PSO en dictionnaire de paramètres.
        
        Args:
            names: Noms des paramètres.
            values: Valeurs des paramètres.
            bounds: Bornes des paramètres.
            
        Returns:
            Dictionnaire des paramètres.
        """
        params = {}
        
        for i, name in enumerate(names):
            spec = self.config.param_space[name]
            value = values[i]
            
            if isinstance(spec, list):
                value = spec[int(round(value))]
            elif isinstance(spec, tuple) and len(spec) == 3:
                min_val, max_val, step = spec
                value = min_val + round((value - min_val) / step) * step
            
            params[name] = value
        
        return params
    
    # ============================================================
    # BUILD RESULT
    # ============================================================
    
    def _build_result(
        self,
        best_params: Optional[Dict[str, Any]] = None,
        best_score: Optional[float] = None
    ) -> OptimizationResult:
        """
        Construit les résultats de l'optimisation.
        
        Args:
            best_params: Meilleurs paramètres (optionnel).
            best_score: Meilleur score (optionnel).
            
        Returns:
            Résultats de l'optimisation.
        """
        if best_params is not None:
            self.best_params = best_params
        
        if best_score is not None:
            self.best_score = best_score
        
        # Si les meilleurs paramètres n'ont pas été évalués avec résultat
        if self.best_params and self.best_result is None:
            _, self.best_result = self.objective.evaluate_with_result(self.best_params)
        
        result = OptimizationResult()
        result.best_params = self.best_params or {}
        result.best_score = self.best_score
        result.best_result = self.best_result
        result.history = self.history
        result.total_evaluations = len(self.history)
        result.convergence_curve = self.convergence_curve
        result.config = self.config
        
        return result
    
    # ============================================================
    # ANALYSE POST-OPTIMISATION
    # ============================================================
    
    def analyze_optimization(self, result: OptimizationResult) -> Dict[str, Any]:
        """
        Analyse les résultats de l'optimisation.
        
        Args:
            result: Résultats de l'optimisation.
            
        Returns:
            Analyse des résultats.
        """
        analysis = {
            'convergence': {
                'final_score': result.best_score,
                'total_evaluations': result.total_evaluations,
                'convergence_rate': 0
            },
            'parameter_importance': {},
            'performance_distribution': {
                'mean': 0,
                'std': 0,
                'min': 0,
                'max': 0
            }
        }
        
        # Analyse de la convergence
        if len(result.convergence_curve) > 1:
            analysis['convergence']['convergence_rate'] = (
                (result.convergence_curve[-1] - result.convergence_curve[0]) /
                len(result.convergence_curve)
            )
        
        # Analyse des scores
        scores = [h['score'] for h in result.history if h['score'] != -float('inf')]
        if scores:
            analysis['performance_distribution'] = {
                'mean': np.mean(scores),
                'std': np.std(scores),
                'min': np.min(scores),
                'max': np.max(scores)
            }
        
        # Analyse des paramètres
        for param_name in self.config.param_space.keys():
            param_values = []
            scores = []
            
            for h in result.history:
                if h['score'] != -float('inf'):
                    param_values.append(h['params'].get(param_name, 0))
                    scores.append(h['score'])
            
            if len(param_values) > 1 and len(scores) > 1:
                # Coefficient de corrélation
                try:
                    corr = np.corrcoef(param_values, scores)[0, 1]
                    analysis['parameter_importance'][param_name] = abs(corr)
                except:
                    analysis['parameter_importance'][param_name] = 0
        
        return analysis


# Fonctions utilitaires
def optimize_strategy(
    strategy_name: str,
    param_space: Dict[str, Any],
    symbol: str,
    start_date: str,
    end_date: str,
    method: str = 'random',
    n_iterations: int = 100,
    **kwargs
) -> OptimizationResult:
    """
    Fonction utilitaire pour optimiser une stratégie.
    
    Args:
        strategy_name: Nom de la stratégie.
        param_space: Espace des paramètres.
        symbol: Symbole à tester.
        start_date: Date de début.
        end_date: Date de fin.
        method: Méthode d'optimisation.
        n_iterations: Nombre d'itérations.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Résultats de l'optimisation.
    """
    config = OptimizationConfig(
        strategy_name=strategy_name,
        param_space=param_space,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        method=method,
        n_iterations=n_iterations,
        **kwargs
    )
    
    optimizer = StrategyOptimizer(config)
    return optimizer.optimize()


# Exportation
__all__ = [
    'StrategyOptimizer',
    'OptimizationConfig',
    'OptimizationResult',
    'ObjectiveFunction',
    'optimize_strategy'
]
