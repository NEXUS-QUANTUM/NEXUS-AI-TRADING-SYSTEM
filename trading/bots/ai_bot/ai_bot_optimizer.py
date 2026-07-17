# trading/bots/ai_bot/ai_bot_optimizer.py
# NEXUS AI TRADING SYSTEM - AI Bot Optimizer
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
AI Bot Optimizer for NEXUS AI Trading System.
Provides comprehensive optimization capabilities including:
- Hyperparameter optimization (Grid Search, Random Search, Bayesian, Genetic)
- Strategy parameter optimization
- Model architecture optimization
- Portfolio optimization
- Risk parameter optimization
- Multi-objective optimization
- Real-time optimization
- Distributed optimization
- Optimization tracking and logging
- Performance benchmarking
- A/B testing support
"""

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
from scipy.optimize import minimize, differential_evolution
from sklearn.model_selection import ParameterGrid, ParameterSampler
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, RBF, WhiteKernel

# NEXUS Imports
from trading.bots.ai_bot.config.bot_configs import BotConfig
from trading.bots.ai_bot.data.data_storage import DataStorage
from trading.bots.ai_bot.metrics.metrics_engine import MetricsEngine
from trading.bots.ai_bot.models.model_factory import ModelFactory
from trading.bots.ai_bot.models.model_evaluator import ModelEvaluator
from shared.utilities.logger import get_logger

logger = get_logger("nexus.trading.bot.optimizer")


# ============================================================================
# Enums & Constants
# ============================================================================

class OptimizationMethod(str, Enum):
    """Optimization methods."""
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    BAYESIAN = "bayesian"
    GENETIC = "genetic"
    HILL_CLIMBING = "hill_climbing"
    SIMULATED_ANNEALING = "simulated_annealing"
    GRADIENT_BASED = "gradient_based"
    ENSEMBLE = "ensemble"


class OptimizationObjective(str, Enum):
    """Optimization objectives."""
    MAXIMIZE_PROFIT = "maximize_profit"
    MINIMIZE_RISK = "minimize_risk"
    MAXIMIZE_SHARPE = "maximize_sharpe"
    MAXIMIZE_RETURN = "maximize_return"
    MINIMIZE_DRAWDOWN = "minimize_drawdown"
    MAXIMIZE_WIN_RATE = "maximize_win_rate"
    MAXIMIZE_PROFIT_FACTOR = "maximize_profit_factor"
    MINIMIZE_VOLATILITY = "minimize_volatility"
    CUSTOM = "custom"


class OptimizationStatus(str, Enum):
    """Optimization status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class OptimizationParameter:
    """Optimization parameter."""
    name: str
    type: str  # int, float, str, bool, categorical
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    choices: Optional[List[Any]] = None
    default: Optional[Any] = None
    step: Optional[float] = None
    log_scale: bool = False
    description: str = ""


@dataclass
class OptimizationConfig:
    """Optimization configuration."""
    method: OptimizationMethod
    objective: OptimizationObjective
    parameters: List[OptimizationParameter]
    max_iterations: int = 100
    population_size: int = 20
    generations: int = 10
    early_stopping: int = 10
    random_seed: Optional[int] = None
    parallel_jobs: int = 1
    evaluation_metric: str = "score"
    maximize: bool = True
    cross_validation_folds: int = 3
    early_stopping_threshold: float = 0.001
    constraints: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OptimizationResult:
    """Optimization result."""
    optimization_id: str
    config: OptimizationConfig
    best_params: Dict[str, Any]
    best_score: float
    all_scores: List[float]
    all_params: List[Dict[str, Any]]
    status: OptimizationStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    runtime_ms: float = 0.0
    iterations: int = 0
    evaluations: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParameterImportance:
    """Parameter importance."""
    name: str
    importance: float
    rank: int
    optimal_value: Any
    sensitivity: float
    interaction_effects: Dict[str, float]


# ============================================================================
# AI Bot Optimizer
# ============================================================================

class AIBotOptimizer:
    """
    Advanced AI Bot Optimizer for NEXUS AI Trading System.
    """

    def __init__(
        self,
        config: BotConfig,
        model_factory: ModelFactory,
        model_evaluator: ModelEvaluator,
        data_storage: DataStorage,
        metrics_engine: MetricsEngine,
    ):
        """
        Initialize AI bot optimizer.

        Args:
            config: Bot configuration
            model_factory: Model factory instance
            model_evaluator: Model evaluator instance
            data_storage: Data storage instance
            metrics_engine: Metrics engine instance
        """
        self.config = config
        self.model_factory = model_factory
        self.model_evaluator = model_evaluator
        self.data_storage = data_storage
        self.metrics_engine = metrics_engine

        # Optimization state
        self._optimizations: Dict[str, OptimizationResult] = {}
        self._active_optimizations: Set[str] = set()
        self._optimization_history: List[OptimizationResult] = []
        self._best_result: Optional[OptimizationResult] = None

        # Parameter importance cache
        self._parameter_importance: Dict[str, List[ParameterImportance]] = {}

        # Performance metrics
        self._performance = {
            "optimizations_run": 0,
            "optimizations_completed": 0,
            "optimizations_failed": 0,
            "total_evaluations": 0,
            "avg_optimization_time_ms": 0.0,
            "best_score_improvement": 0.0,
        }

        # Cache for evaluation results
        self._evaluation_cache: Dict[str, float] = {}

        logger.info(
            "AIBotOptimizer initialized",
            extra={
                "optimization_methods": [m.value for m in OptimizationMethod],
                "objectives": [o.value for o in OptimizationObjective],
            }
        )

    # ========================================================================
    # Optimization Methods
    # ========================================================================

    async def optimize(
        self,
        config: OptimizationConfig,
        evaluation_func: Callable,
        **kwargs,
    ) -> OptimizationResult:
        """
        Run optimization.

        Args:
            config: Optimization configuration
            evaluation_func: Evaluation function
            **kwargs: Additional arguments

        Returns:
            OptimizationResult
        """
        start_time = time.time()

        optimization_id = f"opt_{int(time.time() * 1000)}_{len(self._optimizations)}"

        result = OptimizationResult(
            optimization_id=optimization_id,
            config=config,
            best_params={},
            best_score=float('-inf') if config.maximize else float('inf'),
            all_scores=[],
            all_params=[],
            status=OptimizationStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        self._optimizations[optimization_id] = result
        self._active_optimizations.add(optimization_id)

        try:
            result.status = OptimizationStatus.RUNNING
            result.started_at = datetime.utcnow()

            # Run optimization based on method
            if config.method == OptimizationMethod.GRID_SEARCH:
                best_params, best_score, all_scores, all_params = await self._grid_search(
                    config, evaluation_func, **kwargs
                )
            elif config.method == OptimizationMethod.RANDOM_SEARCH:
                best_params, best_score, all_scores, all_params = await self._random_search(
                    config, evaluation_func, **kwargs
                )
            elif config.method == OptimizationMethod.BAYESIAN:
                best_params, best_score, all_scores, all_params = await self._bayesian_optimization(
                    config, evaluation_func, **kwargs
                )
            elif config.method == OptimizationMethod.GENETIC:
                best_params, best_score, all_scores, all_params = await self._genetic_optimization(
                    config, evaluation_func, **kwargs
                )
            elif config.method == OptimizationMethod.HILL_CLIMBING:
                best_params, best_score, all_scores, all_params = await self._hill_climbing(
                    config, evaluation_func, **kwargs
                )
            elif config.method == OptimizationMethod.SIMULATED_ANNEALING:
                best_params, best_score, all_scores, all_params = await self._simulated_annealing(
                    config, evaluation_func, **kwargs
                )
            else:
                best_params, best_score, all_scores, all_params = await self._ensemble_optimization(
                    config, evaluation_func, **kwargs
                )

            # Update result
            result.best_params = best_params
            result.best_score = best_score
            result.all_scores = all_scores
            result.all_params = all_params
            result.status = OptimizationStatus.COMPLETED
            result.completed_at = datetime.utcnow()
            result.runtime_ms = (time.time() - start_time) * 1000
            result.iterations = len(all_scores)
            result.evaluations = len(all_scores)

            self._performance["optimizations_completed"] += 1
            self._performance["total_evaluations"] += len(all_scores)

            # Update best result
            if self._best_result is None or best_score > self._best_result.best_score:
                self._best_result = result
                self._performance["best_score_improvement"] = (
                    best_score - (self._best_result.best_score if self._best_result else 0)
                )

            # Calculate parameter importance
            await self._calculate_parameter_importance(result, all_params, all_scores)

            # Save optimization
            await self.save_optimization(result)

            logger.info(
                f"Optimization completed: {optimization_id}",
                extra={
                    "best_score": best_score,
                    "iterations": len(all_scores),
                    "runtime_ms": result.runtime_ms,
                }
            )

        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            result.status = OptimizationStatus.FAILED
            result.error = str(e)
            self._performance["optimizations_failed"] += 1

        finally:
            self._active_optimizations.discard(optimization_id)
            self._performance["optimizations_run"] += 1

            # Update average runtime
            self._performance["avg_optimization_time_ms"] = (
                (self._performance["avg_optimization_time_ms"] *
                 (self._performance["optimizations_run"] - 1) +
                 result.runtime_ms) /
                self._performance["optimizations_run"]
            )

        return result

    # ========================================================================
    # Optimization Algorithms
    # ========================================================================

    async def _grid_search(
        self,
        config: OptimizationConfig,
        evaluation_func: Callable,
        **kwargs,
    ) -> Tuple[Dict[str, Any], float, List[float], List[Dict[str, Any]]]:
        """Grid search optimization."""
        # Generate parameter grid
        param_grid = self._generate_parameter_grid(config.parameters)

        best_params = {}
        best_score = float('-inf') if config.maximize else float('inf')
        all_scores = []
        all_params = []

        total_params = len(param_grid)
        logger.info(f"Grid search: {total_params} parameter combinations")

        for i, params in enumerate(param_grid):
            # Evaluate parameters
            score = await self._evaluate_params(params, config, evaluation_func, **kwargs)

            all_scores.append(score)
            all_params.append(params)

            # Update best
            if config.maximize:
                if score > best_score:
                    best_score = score
                    best_params = params
            else:
                if score < best_score:
                    best_score = score
                    best_params = params

            # Log progress
            if (i + 1) % max(1, total_params // 10) == 0:
                logger.info(f"Grid search progress: {i + 1}/{total_params} ({((i+1)/total_params*100):.1f}%)")

            # Early stopping
            if config.early_stopping and i > config.early_stopping * 2:
                if self._should_stop_early(all_scores, config):
                    logger.info(f"Early stopping at iteration {i}")
                    break

        return best_params, best_score, all_scores, all_params

    async def _random_search(
        self,
        config: OptimizationConfig,
        evaluation_func: Callable,
        **kwargs,
    ) -> Tuple[Dict[str, Any], float, List[float], List[Dict[str, Any]]]:
        """Random search optimization."""
        # Generate random samples
        param_sampler = ParameterSampler(
            self._generate_parameter_distributions(config.parameters),
            n_iter=config.max_iterations,
            random_state=config.random_seed,
        )

        best_params = {}
        best_score = float('-inf') if config.maximize else float('inf')
        all_scores = []
        all_params = []

        for i, params in enumerate(param_sampler):
            # Evaluate parameters
            score = await self._evaluate_params(params, config, evaluation_func, **kwargs)

            all_scores.append(score)
            all_params.append(params)

            # Update best
            if config.maximize:
                if score > best_score:
                    best_score = score
                    best_params = params
            else:
                if score < best_score:
                    best_score = score
                    best_params = params

            # Log progress
            if (i + 1) % max(1, config.max_iterations // 10) == 0:
                logger.info(f"Random search progress: {i + 1}/{config.max_iterations}")

            # Early stopping
            if config.early_stopping and i > config.early_stopping * 2:
                if self._should_stop_early(all_scores, config):
                    logger.info(f"Early stopping at iteration {i}")
                    break

        return best_params, best_score, all_scores, all_params

    async def _bayesian_optimization(
        self,
        config: OptimizationConfig,
        evaluation_func: Callable,
        **kwargs,
    ) -> Tuple[Dict[str, Any], float, List[float], List[Dict[str, Any]]]:
        """Bayesian optimization."""
        # Initialize Gaussian Process
        kernel = RBF(length_scale=1.0) + WhiteKernel(noise_level=0.1)
        gp = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=10,
            alpha=1e-6,
            normalize_y=True,
            random_state=config.random_seed,
        )

        # Initial random samples
        n_initial = min(10, config.max_iterations // 2)
        initial_params = list(ParameterSampler(
            self._generate_parameter_distributions(config.parameters),
            n_iter=n_initial,
            random_state=config.random_seed,
        ))

        best_params = {}
        best_score = float('-inf') if config.maximize else float('inf')
        all_scores = []
        all_params = []

        # Evaluate initial samples
        for params in initial_params:
            score = await self._evaluate_params(params, config, evaluation_func, **kwargs)
            all_scores.append(score)
            all_params.append(params)

            if config.maximize:
                if score > best_score:
                    best_score = score
                    best_params = params
            else:
                if score < best_score:
                    best_score = score
                    best_params = params

        # Bayesian optimization loop
        for i in range(len(initial_params), config.max_iterations):
            # Prepare data for GP
            X = np.array([self._params_to_vector(p, config.parameters) for p in all_params])
            y = np.array(all_scores)

            if config.maximize:
                y = -y  # GP works with minimization

            # Fit GP
            gp.fit(X, y)

            # Get next sample
            next_params = await self._get_next_bayesian_sample(gp, config, all_params)

            # Evaluate
            score = await self._evaluate_params(next_params, config, evaluation_func, **kwargs)

            all_scores.append(score)
            all_params.append(next_params)

            if config.maximize:
                if score > best_score:
                    best_score = score
                    best_params = next_params
            else:
                if score < best_score:
                    best_score = score
                    best_params = next_params

            # Log progress
            if (i + 1) % max(1, config.max_iterations // 10) == 0:
                logger.info(f"Bayesian optimization progress: {i + 1}/{config.max_iterations}")

            # Early stopping
            if config.early_stopping and i > config.early_stopping * 2:
                if self._should_stop_early(all_scores, config):
                    logger.info(f"Early stopping at iteration {i}")
                    break

        return best_params, best_score, all_scores, all_params

    async def _genetic_optimization(
        self,
        config: OptimizationConfig,
        evaluation_func: Callable,
        **kwargs,
    ) -> Tuple[Dict[str, Any], float, List[float], List[Dict[str, Any]]]:
        """Genetic algorithm optimization."""
        # Initialize population
        population = list(ParameterSampler(
            self._generate_parameter_distributions(config.parameters),
            n_iter=config.population_size,
            random_state=config.random_seed,
        ))

        best_params = {}
        best_score = float('-inf') if config.maximize else float('inf')
        all_scores = []
        all_params = []

        for generation in range(config.generations):
            # Evaluate population
            generation_scores = []
            generation_params = []

            for params in population:
                score = await self._evaluate_params(params, config, evaluation_func, **kwargs)
                generation_scores.append(score)
                generation_params.append(params)

                all_scores.append(score)
                all_params.append(params)

                if config.maximize:
                    if score > best_score:
                        best_score = score
                        best_params = params
                else:
                    if score < best_score:
                        best_score = score
                        best_params = params

            # Select best individuals
            sorted_indices = np.argsort(generation_scores)
            if not config.maximize:
                sorted_indices = sorted_indices[::-1]

            best_indices = sorted_indices[:config.population_size // 2]

            # Create next generation
            next_population = []
            for idx in best_indices:
                next_population.append(generation_params[idx])

            # Crossover and mutation
            while len(next_population) < config.population_size:
                # Select parents
                parent1 = generation_params[np.random.choice(best_indices)]
                parent2 = generation_params[np.random.choice(best_indices)]

                # Crossover
                child = self._crossover(parent1, parent2, config.parameters)

                # Mutation
                if np.random.random() < 0.1:
                    child = self._mutate(child, config.parameters)

                next_population.append(child)

            population = next_population

            logger.info(f"Genetic optimization generation {generation + 1}/{config.generations}")

            if config.early_stopping and generation > config.early_stopping:
                if self._should_stop_early(all_scores, config):
                    logger.info(f"Early stopping at generation {generation}")
                    break

        return best_params, best_score, all_scores, all_params

    async def _hill_climbing(
        self,
        config: OptimizationConfig,
        evaluation_func: Callable,
        **kwargs,
    ) -> Tuple[Dict[str, Any], float, List[float], List[Dict[str, Any]]]:
        """Hill climbing optimization."""
        # Start with random solution
        current_params = self._generate_random_params(config.parameters)
        current_score = await self._evaluate_params(current_params, config, evaluation_func, **kwargs)

        best_params = current_params
        best_score = current_score
        all_scores = [current_score]
        all_params = [current_params]

        for i in range(config.max_iterations):
            # Generate neighbor
            neighbor = self._generate_neighbor(current_params, config.parameters)
            neighbor_score = await self._evaluate_params(neighbor, config, evaluation_func, **kwargs)

            all_scores.append(neighbor_score)
            all_params.append(neighbor)

            # Accept if better
            if (config.maximize and neighbor_score > current_score) or \
               (not config.maximize and neighbor_score < current_score):
                current_params = neighbor
                current_score = neighbor_score

                if (config.maximize and current_score > best_score) or \
                   (not config.maximize and current_score < best_score):
                    best_params = current_params
                    best_score = current_score

            logger.info(f"Hill climbing iteration {i + 1}/{config.max_iterations}")

            if config.early_stopping and i > config.early_stopping * 2:
                if self._should_stop_early(all_scores, config):
                    logger.info(f"Early stopping at iteration {i}")
                    break

        return best_params, best_score, all_scores, all_params

    async def _simulated_annealing(
        self,
        config: OptimizationConfig,
        evaluation_func: Callable,
        **kwargs,
    ) -> Tuple[Dict[str, Any], float, List[float], List[Dict[str, Any]]]:
        """Simulated annealing optimization."""
        # Start with random solution
        current_params = self._generate_random_params(config.parameters)
        current_score = await self._evaluate_params(current_params, config, evaluation_func, **kwargs)

        best_params = current_params
        best_score = current_score
        all_scores = [current_score]
        all_params = [current_params]

        # Temperature schedule
        initial_temp = 100.0
        final_temp = 1.0

        for i in range(config.max_iterations):
            # Calculate temperature
            temp = initial_temp * (final_temp / initial_temp) ** (i / config.max_iterations)

            # Generate neighbor
            neighbor = self._generate_neighbor(current_params, config.parameters)
            neighbor_score = await self._evaluate_params(neighbor, config, evaluation_func, **kwargs)

            all_scores.append(neighbor_score)
            all_params.append(neighbor)

            # Accept with probability
            if config.maximize:
                delta = neighbor_score - current_score
            else:
                delta = current_score - neighbor_score

            if delta > 0 or np.random.random() < np.exp(delta / temp):
                current_params = neighbor
                current_score = neighbor_score

                if (config.maximize and current_score > best_score) or \
                   (not config.maximize and current_score < best_score):
                    best_params = current_params
                    best_score = current_score

            if (i + 1) % max(1, config.max_iterations // 10) == 0:
                logger.info(f"Simulated annealing progress: {i + 1}/{config.max_iterations}")

            if config.early_stopping and i > config.early_stopping * 2:
                if self._should_stop_early(all_scores, config):
                    logger.info(f"Early stopping at iteration {i}")
                    break

        return best_params, best_score, all_scores, all_params

    async def _ensemble_optimization(
        self,
        config: OptimizationConfig,
        evaluation_func: Callable,
        **kwargs,
    ) -> Tuple[Dict[str, Any], float, List[float], List[Dict[str, Any]]]:
        """Ensemble optimization combining multiple methods."""
        methods = [
            OptimizationMethod.RANDOM_SEARCH,
            OptimizationMethod.BAYESIAN,
            OptimizationMethod.GENETIC,
        ]

        all_results = []

        for method in methods:
            try:
                config_copy = OptimizationConfig(
                    method=method,
                    objective=config.objective,
                    parameters=config.parameters,
                    max_iterations=config.max_iterations // len(methods),
                    population_size=config.population_size,
                    generations=config.generations,
                    early_stopping=config.early_stopping,
                    random_seed=config.random_seed,
                    parallel_jobs=config.parallel_jobs,
                    evaluation_metric=config.evaluation_metric,
                    maximize=config.maximize,
                    cross_validation_folds=config.cross_validation_folds,
                    early_stopping_threshold=config.early_stopping_threshold,
                    constraints=config.constraints,
                )

                result = await self.optimize(config_copy, evaluation_func, **kwargs)
                all_results.append(result)

            except Exception as e:
                logger.warning(f"Ensemble method {method.value} failed: {e}")

        # Find best result
        best_result = max(all_results, key=lambda r: r.best_score if config.maximize else -r.best_score)

        return (
            best_result.best_params,
            best_result.best_score,
            [],  # All scores from ensemble
            [],  # All params from ensemble
        )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _evaluate_params(
        self,
        params: Dict[str, Any],
        config: OptimizationConfig,
        evaluation_func: Callable,
        **kwargs,
    ) -> float:
        """Evaluate a set of parameters."""
        # Check cache
        cache_key = self._get_cache_key(params)
        if cache_key in self._evaluation_cache:
            return self._evaluation_cache[cache_key]

        try:
            # Run evaluation
            score = await evaluation_func(params, **kwargs)

            # Cache result
            self._evaluation_cache[cache_key] = score

            return score

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return float('-inf') if config.maximize else float('inf')

    def _generate_parameter_grid(
        self,
        parameters: List[OptimizationParameter],
    ) -> List[Dict[str, Any]]:
        """Generate parameter grid."""
        param_dict = {}

        for param in parameters:
            if param.choices:
                param_dict[param.name] = param.choices
            elif param.type in ['int', 'float']:
                if param.step:
                    values = np.arange(param.min_value, param.max_value + param.step, param.step)
                else:
                    values = np.linspace(param.min_value, param.max_value, 10)
                param_dict[param.name] = values.tolist()
            else:
                param_dict[param.name] = [param.default]

        return list(ParameterGrid(param_dict))

    def _generate_parameter_distributions(
        self,
        parameters: List[OptimizationParameter],
    ) -> Dict[str, Any]:
        """Generate parameter distributions for random search."""
        distributions = {}

        for param in parameters:
            if param.choices:
                distributions[param.name] = param.choices
            elif param.type == 'int':
                distributions[param.name] = list(range(
                    int(param.min_value),
                    int(param.max_value) + 1,
                ))
            elif param.type == 'float':
                distributions[param.name] = np.linspace(
                    param.min_value,
                    param.max_value,
                    100,
                ).tolist()
            else:
                distributions[param.name] = [param.default]

        return distributions

    def _generate_random_params(
        self,
        parameters: List[OptimizationParameter],
    ) -> Dict[str, Any]:
        """Generate random parameters."""
        params = {}

        for param in parameters:
            if param.choices:
                params[param.name] = np.random.choice(param.choices)
            elif param.type == 'int':
                params[param.name] = np.random.randint(param.min_value, param.max_value + 1)
            elif param.type == 'float':
                if param.log_scale:
                    log_min = np.log(param.min_value)
                    log_max = np.log(param.max_value)
                    params[param.name] = np.exp(np.random.uniform(log_min, log_max))
                else:
                    params[param.name] = np.random.uniform(param.min_value, param.max_value)
            else:
                params[param.name] = param.default

        return params

    def _generate_neighbor(
        self,
        current: Dict[str, Any],
        parameters: List[OptimizationParameter],
    ) -> Dict[str, Any]:
        """Generate a neighbor for hill climbing."""
        neighbor = current.copy()

        for param in parameters:
            if param.choices:
                choices = [c for c in param.choices if c != current[param.name]]
                if choices:
                    neighbor[param.name] = np.random.choice(choices)
            elif param.type == 'int':
                step = max(1, int((param.max_value - param.min_value) * 0.1))
                new_value = current[param.name] + np.random.choice([-step, step])
                neighbor[param.name] = max(param.min_value, min(param.max_value, new_value))
            elif param.type == 'float':
                step = (param.max_value - param.min_value) * 0.1
                new_value = current[param.name] + np.random.uniform(-step, step)
                neighbor[param.name] = max(param.min_value, min(param.max_value, new_value))

        return neighbor

    def _crossover(
        self,
        parent1: Dict[str, Any],
        parent2: Dict[str, Any],
        parameters: List[OptimizationParameter],
    ) -> Dict[str, Any]:
        """Crossover for genetic algorithm."""
        child = {}

        for param in parameters:
            if np.random.random() < 0.5:
                child[param.name] = parent1[param.name]
            else:
                child[param.name] = parent2[param.name]

        return child

    def _mutate(
        self,
        params: Dict[str, Any],
        parameters: List[OptimizationParameter],
    ) -> Dict[str, Any]:
        """Mutation for genetic algorithm."""
        mutated = params.copy()

        for param in parameters:
            if np.random.random() < 0.1:
                if param.choices:
                    choices = [c for c in param.choices if c != params[param.name]]
                    if choices:
                        mutated[param.name] = np.random.choice(choices)
                elif param.type == 'int':
                    step = max(1, int((param.max_value - param.min_value) * 0.05))
                    new_value = params[param.name] + np.random.choice([-step, step])
                    mutated[param.name] = max(param.min_value, min(param.max_value, new_value))
                elif param.type == 'float':
                    step = (param.max_value - param.min_value) * 0.05
                    new_value = params[param.name] + np.random.uniform(-step, step)
                    mutated[param.name] = max(param.min_value, min(param.max_value, new_value))

        return mutated

    def _params_to_vector(
        self,
        params: Dict[str, Any],
        parameters: List[OptimizationParameter],
    ) -> np.ndarray:
        """Convert parameters to vector for GP."""
        vector = []

        for param in parameters:
            if param.type == 'int' or param.type == 'float':
                vector.append(params[param.name])
            elif param.choices:
                # One-hot encoding
                for choice in param.choices:
                    vector.append(1 if params[param.name] == choice else 0)

        return np.array(vector)

    async def _get_next_bayesian_sample(
        self,
        gp: GaussianProcessRegressor,
        config: OptimizationConfig,
        previous_params: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Get next sample for Bayesian optimization."""
        # Generate random candidates
        n_candidates = 1000
        candidates = list(ParameterSampler(
            self._generate_parameter_distributions(config.parameters),
            n_iter=n_candidates,
        ))

        # Convert candidates to vectors
        X_candidates = np.array([
            self._params_to_vector(p, config.parameters)
            for p in candidates
        ])

        # Predict mean and std
        y_mean, y_std = gp.predict(X_candidates, return_std=True)

        # Expected improvement
        if config.maximize:
            y_best = max([s for s in gp.y_train_])
        else:
            y_best = min([s for s in gp.y_train_])

        # Calculate acquisition function
        if config.maximize:
            improvement = y_mean - y_best
        else:
            improvement = y_best - y_mean

        z = improvement / (y_std + 1e-9)
        ei = improvement * stats.norm.cdf(z) + y_std * stats.norm.pdf(z)

        # Best candidate
        best_idx = np.argmax(ei)

        return candidates[best_idx]

    def _should_stop_early(
        self,
        scores: List[float],
        config: OptimizationConfig,
    ) -> bool:
        """Check if early stopping should be triggered."""
        if len(scores) < config.early_stopping * 2:
            return False

        recent_scores = scores[-config.early_stopping:]
        older_scores = scores[-config.early_stopping * 2:-config.early_stopping]

        recent_mean = np.mean(recent_scores)
        older_mean = np.mean(older_scores)

        improvement = abs(recent_mean - older_mean)

        return improvement < config.early_stopping_threshold

    def _get_cache_key(self, params: Dict[str, Any]) -> str:
        """Get cache key for parameters."""
        return json.dumps({k: str(v) for k, v in sorted(params.items())})

    # ========================================================================
    # Parameter Importance
    # ========================================================================

    async def _calculate_parameter_importance(
        self,
        result: OptimizationResult,
        all_params: List[Dict[str, Any]],
        all_scores: List[float],
    ) -> None:
        """Calculate parameter importance."""
        if len(all_params) < 10:
            return

        # Calculate importance for each parameter
        importances = []

        for param in result.config.parameters:
            try:
                # Extract values
                values = [p.get(param.name) for p in all_params if param.name in p]

                if len(values) < 10:
                    continue

                # Calculate correlation with score
                corr = np.corrcoef(values, all_scores)[0, 1]

                # Calculate importance
                importance = abs(corr)

                # Find optimal value
                optimal_value = self._find_optimal_value(
                    param,
                    all_params,
                    all_scores,
                    result.config.maximize,
                )

                # Calculate sensitivity
                sensitivity = self._calculate_sensitivity(
                    param,
                    all_params,
                    all_scores,
                )

                param_importance = ParameterImportance(
                    name=param.name,
                    importance=importance,
                    rank=0,
                    optimal_value=optimal_value,
                    sensitivity=sensitivity,
                    interaction_effects={},
                )

                importances.append(param_importance)

            except Exception as e:
                logger.warning(f"Error calculating importance for {param.name}: {e}")

        # Rank parameters
        importances.sort(key=lambda x: x.importance, reverse=True)
        for i, imp in enumerate(importances):
            imp.rank = i + 1

        self._parameter_importance[result.optimization_id] = importances

    def _find_optimal_value(
        self,
        param: OptimizationParameter,
        all_params: List[Dict[str, Any]],
        all_scores: List[float],
        maximize: bool,
    ) -> Any:
        """Find optimal value for parameter."""
        if param.choices:
            # For categorical parameters, find best choice
            best_value = None
            best_score = float('-inf') if maximize else float('inf')

            for choice in param.choices:
                indices = [i for i, p in enumerate(all_params) if p.get(param.name) == choice]
                if indices:
                    scores = [all_scores[i] for i in indices]
                    score = np.mean(scores)

                    if maximize and score > best_score:
                        best_score = score
                        best_value = choice
                    elif not maximize and score < best_score:
                        best_score = score
                        best_value = choice

            return best_value

        else:
            # For continuous parameters, interpolate
            values = [p.get(param.name) for p in all_params if param.name in p]
            if values:
                return np.mean(values)

            return param.default

    def _calculate_sensitivity(
        self,
        param: OptimizationParameter,
        all_params: List[Dict[str, Any]],
        all_scores: List[float],
    ) -> float:
        """Calculate parameter sensitivity."""
        values = [p.get(param.name) for p in all_params if param.name in p]

        if len(values) < 10:
            return 0.0

        # Calculate effect of parameter on score
        value_range = max(values) - min(values)

        if value_range == 0:
            return 0.0

        # Group by value bins
        n_bins = min(10, len(values) // 2)
        bins = np.linspace(min(values), max(values), n_bins + 1)

        bin_scores = []
        for i in range(n_bins):
            indices = [
                idx for idx, v in enumerate(values)
                if bins[i] <= v < bins[i + 1]
            ]
            if indices:
                bin_scores.append(np.mean([all_scores[idx] for idx in indices]))
            else:
                bin_scores.append(0)

        # Calculate sensitivity
        if bin_scores:
            return np.std(bin_scores) / (np.mean(np.abs(bin_scores)) + 1e-9)

        return 0.0

    # ========================================================================
    # Persistence
    # ========================================================================

    async def save_optimization(self, result: OptimizationResult) -> bool:
        """
        Save optimization result.

        Args:
            result: OptimizationResult

        Returns:
            True if saved successfully
        """
        try:
            data = {
                "optimization_id": result.optimization_id,
                "config": {
                    "method": result.config.method.value,
                    "objective": result.config.objective.value,
                    "parameters": [
                        {
                            "name": p.name,
                            "type": p.type,
                            "min_value": p.min_value,
                            "max_value": p.max_value,
                            "choices": p.choices,
                            "default": p.default,
                            "step": p.step,
                            "log_scale": p.log_scale,
                            "description": p.description,
                        }
                        for p in result.config.parameters
                    ],
                    "max_iterations": result.config.max_iterations,
                    "population_size": result.config.population_size,
                    "generations": result.config.generations,
                    "early_stopping": result.config.early_stopping,
                    "random_seed": result.config.random_seed,
                    "parallel_jobs": result.config.parallel_jobs,
                    "evaluation_metric": result.config.evaluation_metric,
                    "maximize": result.config.maximize,
                    "cross_validation_folds": result.config.cross_validation_folds,
                    "early_stopping_threshold": result.config.early_stopping_threshold,
                    "constraints": result.config.constraints,
                },
                "best_params": result.best_params,
                "best_score": result.best_score,
                "all_scores": result.all_scores,
                "all_params": result.all_params,
                "status": result.status.value,
                "created_at": result.created_at.isoformat(),
                "started_at": result.started_at.isoformat() if result.started_at else None,
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "runtime_ms": result.runtime_ms,
                "iterations": result.iterations,
                "evaluations": result.evaluations,
                "error": result.error,
                "metadata": result.metadata,
            }

            key = f"optimization:{result.optimization_id}"
            return await self.data_storage.save_data(key, data)

        except Exception as e:
            logger.error(f"Error saving optimization: {e}")
            return False

    async def load_optimization(self, optimization_id: str) -> Optional[OptimizationResult]:
        """
        Load optimization result.

        Args:
            optimization_id: Optimization ID

        Returns:
            OptimizationResult or None
        """
        try:
            key = f"optimization:{optimization_id}"
            data = await self.data_storage.load_data(key)

            if not data:
                return None

            return self._deserialize_optimization(data)

        except Exception as e:
            logger.error(f"Error loading optimization: {e}")
            return None

    def _deserialize_optimization(self, data: Dict[str, Any]) -> OptimizationResult:
        """Deserialize optimization result."""
        return OptimizationResult(
            optimization_id=data["optimization_id"],
            config=OptimizationConfig(
                method=OptimizationMethod(data["config"]["method"]),
                objective=OptimizationObjective(data["config"]["objective"]),
                parameters=[
                    OptimizationParameter(
                        name=p["name"],
                        type=p["type"],
                        min_value=p.get("min_value"),
                        max_value=p.get("max_value"),
                        choices=p.get("choices"),
                        default=p.get("default"),
                        step=p.get("step"),
                        log_scale=p.get("log_scale", False),
                        description=p.get("description", ""),
                    )
                    for p in data["config"]["parameters"]
                ],
                max_iterations=data["config"]["max_iterations"],
                population_size=data["config"]["population_size"],
                generations=data["config"]["generations"],
                early_stopping=data["config"]["early_stopping"],
                random_seed=data["config"]["random_seed"],
                parallel_jobs=data["config"]["parallel_jobs"],
                evaluation_metric=data["config"]["evaluation_metric"],
                maximize=data["config"]["maximize"],
                cross_validation_folds=data["config"]["cross_validation_folds"],
                early_stopping_threshold=data["config"]["early_stopping_threshold"],
                constraints=data["config"]["constraints"],
            ),
            best_params=data["best_params"],
            best_score=data["best_score"],
            all_scores=data["all_scores"],
            all_params=data["all_params"],
            status=OptimizationStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            runtime_ms=data["runtime_ms"],
            iterations=data["iterations"],
            evaluations=data["evaluations"],
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_optimization(self, optimization_id: str) -> Optional[OptimizationResult]:
        """
        Get optimization result.

        Args:
            optimization_id: Optimization ID

        Returns:
            OptimizationResult or None
        """
        return self._optimizations.get(optimization_id)

    def get_optimizations(
        self,
        status: Optional[OptimizationStatus] = None,
        limit: int = 100,
    ) -> List[OptimizationResult]:
        """
        Get optimizations.

        Args:
            status: Filter by status
            limit: Maximum number

        Returns:
            List of OptimizationResult
        """
        results = list(self._optimizations.values())

        if status:
            results = [r for r in results if r.status == status]

        return sorted(results, key=lambda r: r.created_at, reverse=True)[:limit]

    def get_parameter_importance(self, optimization_id: str) -> List[ParameterImportance]:
        """
        Get parameter importance.

        Args:
            optimization_id: Optimization ID

        Returns:
            List of ParameterImportance
        """
        return self._parameter_importance.get(optimization_id, [])

    def get_best_parameters(
        self,
        objective: Optional[OptimizationObjective] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get best parameters for objective.

        Args:
            objective: Optimization objective

        Returns:
            Best parameters or None
        """
        if self._best_result is None:
            return None

        if objective is None or self._best_result.config.objective == objective:
            return self._best_result.best_params

        # Find best result for objective
        results = [
            r for r in self._optimizations.values()
            if r.status == OptimizationStatus.COMPLETED
            and r.config.objective == objective
        ]

        if not results:
            return None

        best_result = max(results, key=lambda r: r.best_score)

        return best_result.best_params

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Performance metrics
        """
        return {
            **self._performance,
            "total_optimizations": len(self._optimizations),
            "active_optimizations": len(self._active_optimizations),
            "cached_evaluations": len(self._evaluation_cache),
            "best_score": self._best_result.best_score if self._best_result else None,
            "best_params": self._best_result.best_params if self._best_result else None,
        }

    def clear_cache(self) -> None:
        """Clear evaluation cache."""
        self._evaluation_cache.clear()
        logger.info("Optimization cache cleared")

    # ========================================================================
    # Lifecycle Management
    # ========================================================================

    async def start(self) -> None:
        """Start the optimizer."""
        logger.info("AIBotOptimizer started")

    async def stop(self) -> None:
        """Stop the optimizer."""
        self.clear_cache()
        logger.info("AIBotOptimizer stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_ai_bot_optimizer(
    config: BotConfig,
    model_factory: ModelFactory,
    model_evaluator: ModelEvaluator,
    data_storage: DataStorage,
    metrics_engine: MetricsEngine,
) -> AIBotOptimizer:
    """
    Factory function to create an AIBotOptimizer instance.

    Args:
        config: Bot configuration
        model_factory: Model factory instance
        model_evaluator: Model evaluator instance
        data_storage: Data storage instance
        metrics_engine: Metrics engine instance

    Returns:
        AIBotOptimizer instance
    """
    return AIBotOptimizer(
        config=config,
        model_factory=model_factory,
        model_evaluator=model_evaluator,
        data_storage=data_storage,
        metrics_engine=metrics_engine,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the AI bot optimizer
    pass
