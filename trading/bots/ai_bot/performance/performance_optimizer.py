"""
NEXUS AI TRADING SYSTEM - Performance Optimizer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced performance optimization system for trading bots, models, and
strategies with hyperparameter tuning, multi-objective optimization,
and adaptive optimization capabilities.
"""

import asyncio
import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import yaml
from prometheus_client import Counter, Gauge, Histogram

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
OPTIMIZATION_COUNTER = Counter(
    "nexus_optimizations_total",
    "Total number of optimizations performed",
    ["optimizer_type", "status"],
)
OPTIMIZATION_DURATION = Histogram(
    "nexus_optimization_duration_seconds",
    "Duration of optimization runs",
    ["optimizer_type"],
)
OPTIMIZATION_SCORE_GAUGE = Gauge(
    "nexus_optimization_score",
    "Optimization score",
    ["objective"],
)


class OptimizerType(Enum):
    """Types of optimizers."""

    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    BAYESIAN = "bayesian"
    GENETIC = "genetic"
    SIMULATED_ANNEALING = "simulated_annealing"
    PARTICLE_SWARM = "particle_swarm"
    GRADIENT_BASED = "gradient_based"
    MULTI_OBJECTIVE = "multi_objective"
    ADAPTIVE = "adaptive"


class OptimizationObjective(Enum):
    """Optimization objectives."""

    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


@dataclass
class ParameterSpace:
    """Parameter space definition."""

    name: str
    type: str  # "int", "float", "categorical", "boolean"
    range: Optional[Tuple[float, float]] = None
    choices: Optional[List[Any]] = None
    default: Optional[Any] = None
    step: Optional[float] = None
    distribution: str = "uniform"  # "uniform", "log_uniform", "normal"

    def sample(self) -> Any:
        """Sample a value from the parameter space."""
        if self.type == "int":
            if self.range:
                if self.distribution == "uniform":
                    return int(np.random.uniform(self.range[0], self.range[1]))
                elif self.distribution == "log_uniform":
                    return int(np.exp(np.random.uniform(np.log(self.range[0]), np.log(self.range[1]))))
        elif self.type == "float":
            if self.range:
                if self.distribution == "uniform":
                    return float(np.random.uniform(self.range[0], self.range[1]))
                elif self.distribution == "log_uniform":
                    return float(np.exp(np.random.uniform(np.log(self.range[0]), np.log(self.range[1]))))
                elif self.distribution == "normal":
                    mean = (self.range[0] + self.range[1]) / 2
                    std = (self.range[1] - self.range[0]) / 4
                    return float(np.random.normal(mean, std))
        elif self.type == "categorical":
            if self.choices:
                return random.choice(self.choices)
        elif self.type == "boolean":
            return bool(random.choice([True, False]))

        return self.default

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "range": self.range,
            "choices": self.choices,
            "default": self.default,
            "step": self.step,
            "distribution": self.distribution,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParameterSpace":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            type=data["type"],
            range=data.get("range"),
            choices=data.get("choices"),
            default=data.get("default"),
            step=data.get("step"),
            distribution=data.get("distribution", "uniform"),
        )


@dataclass
class OptimizationConfig:
    """Configuration for optimization."""

    optimizer_type: OptimizerType
    objective: OptimizationObjective
    parameters: List[ParameterSpace]
    max_iterations: int = 100
    early_stopping_patience: int = 10
    early_stopping_threshold: float = 0.001
    n_jobs: int = 1
    random_seed: int = 42
    timeout_seconds: int = 3600
    metrics: List[str] = field(default_factory=list)
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "optimizer_type": self.optimizer_type.value,
            "objective": self.objective.value,
            "parameters": [p.to_dict() for p in self.parameters],
            "max_iterations": self.max_iterations,
            "early_stopping_patience": self.early_stopping_patience,
            "early_stopping_threshold": self.early_stopping_threshold,
            "n_jobs": self.n_jobs,
            "random_seed": self.random_seed,
            "timeout_seconds": self.timeout_seconds,
            "metrics": self.metrics,
            "constraints": self.constraints,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OptimizationConfig":
        """Create from dictionary."""
        return cls(
            optimizer_type=OptimizerType(data["optimizer_type"]),
            objective=OptimizationObjective(data["objective"]),
            parameters=[ParameterSpace.from_dict(p) for p in data["parameters"]],
            max_iterations=data.get("max_iterations", 100),
            early_stopping_patience=data.get("early_stopping_patience", 10),
            early_stopping_threshold=data.get("early_stopping_threshold", 0.001),
            n_jobs=data.get("n_jobs", 1),
            random_seed=data.get("random_seed", 42),
            timeout_seconds=data.get("timeout_seconds", 3600),
            metrics=data.get("metrics", []),
            constraints=data.get("constraints", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class OptimizationResult:
    """Result of an optimization run."""

    id: str
    config: OptimizationConfig
    best_parameters: Dict[str, Any]
    best_score: float
    all_scores: List[float]
    all_parameters: List[Dict[str, Any]]
    iteration_history: List[Dict[str, Any]]
    duration_seconds: float
    status: str
    metrics: Dict[str, Any]
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "config": self.config.to_dict(),
            "best_parameters": self.best_parameters,
            "best_score": self.best_score,
            "all_scores": self.all_scores,
            "all_parameters": self.all_parameters,
            "iteration_history": self.iteration_history,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "metrics": self.metrics,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OptimizationResult":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            config=OptimizationConfig.from_dict(data["config"]),
            best_parameters=data["best_parameters"],
            best_score=data["best_score"],
            all_scores=data["all_scores"],
            all_parameters=data["all_parameters"],
            iteration_history=data["iteration_history"],
            duration_seconds=data["duration_seconds"],
            status=data["status"],
            metrics=data["metrics"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class PerformanceOptimizer:
    """
    Advanced performance optimization system for trading components.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the performance optimizer.

        Args:
            config: Configuration dictionary
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._lock = asyncio.Lock()
        self._results: Dict[str, OptimizationResult] = {}
        self._running_optimizations: Dict[str, asyncio.Task] = {}
        self._optimization_queue: List[Dict[str, Any]] = []
        self._objective_function: Optional[Callable] = None

        # Load configuration
        self.opt_config = self.config.get("performance_optimizer", {})
        self.results_path = Path(self.opt_config.get("results_path", "./data/optimizations"))
        self.max_results = self.opt_config.get("max_results", 100)
        self.results_path.mkdir(parents=True, exist_ok=True)

        # Load existing results
        self._load_results()

        logger.info("PerformanceOptimizer initialized")

    def _load_results(self):
        """Load optimization results from storage."""
        try:
            for file_path in self.results_path.glob("*.json"):
                with open(file_path, "r") as f:
                    data = json.load(f)
                    result = OptimizationResult.from_dict(data)
                    self._results[result.id] = result
            logger.info(f"Loaded {len(self._results)} optimization results")
        except Exception as e:
            logger.error(f"Error loading results: {e}")

    def register_objective_function(self, func: Callable):
        """
        Register the objective function for optimization.

        Args:
            func: Async function that takes parameters and returns a score
        """
        self._objective_function = func
        logger.info("Objective function registered")

    async def optimize(
        self,
        config: Union[OptimizationConfig, Dict[str, Any]],
        objective_function: Optional[Callable] = None,
    ) -> OptimizationResult:
        """
        Run optimization.

        Args:
            config: Optimization configuration
            objective_function: Objective function to optimize

        Returns:
            Optimization result
        """
        if isinstance(config, dict):
            config = OptimizationConfig.from_dict(config)

        if objective_function:
            self.register_objective_function(objective_function)

        if self._objective_function is None:
            raise ValueError("No objective function registered")

        # Set random seed
        np.random.seed(config.random_seed)
        random.seed(config.random_seed)

        # Generate optimization ID
        opt_id = f"opt_{int(time.time())}_{random.randint(1000, 9999)}"

        logger.info(f"Starting optimization {opt_id} with {config.optimizer_type.value}")

        start_time = time.time()

        try:
            # Run optimization based on type
            if config.optimizer_type == OptimizerType.GRID_SEARCH:
                result = await self._grid_search(config, opt_id)
            elif config.optimizer_type == OptimizerType.RANDOM_SEARCH:
                result = await self._random_search(config, opt_id)
            elif config.optimizer_type == OptimizerType.BAYESIAN:
                result = await self._bayesian_optimization(config, opt_id)
            elif config.optimizer_type == OptimizerType.GENETIC:
                result = await self._genetic_algorithm(config, opt_id)
            elif config.optimizer_type == OptimizerType.SIMULATED_ANNEALING:
                result = await self._simulated_annealing(config, opt_id)
            elif config.optimizer_type == OptimizerType.PARTICLE_SWARM:
                result = await self._particle_swarm_optimization(config, opt_id)
            elif config.optimizer_type == OptimizerType.MULTI_OBJECTIVE:
                result = await self._multi_objective_optimization(config, opt_id)
            elif config.optimizer_type == OptimizerType.ADAPTIVE:
                result = await self._adaptive_optimization(config, opt_id)
            else:
                raise ValueError(f"Unsupported optimizer type: {config.optimizer_type}")

            # Record metrics
            OPTIMIZATION_DURATION.labels(
                optimizer_type=config.optimizer_type.value
            ).observe(result.duration_seconds)
            OPTIMIZATION_COUNTER.labels(
                optimizer_type=config.optimizer_type.value,
                status="success",
            ).inc()
            OPTIMIZATION_SCORE_GAUGE.labels(
                objective=config.objective.value
            ).set(result.best_score)

            return result

        except Exception as e:
            logger.error(f"Optimization {opt_id} failed: {e}")
            OPTIMIZATION_COUNTER.labels(
                optimizer_type=config.optimizer_type.value,
                status="failed",
            ).inc()
            raise

    async def _evaluate_parameters(
        self,
        parameters: Dict[str, Any],
        config: OptimizationConfig,
    ) -> float:
        """
        Evaluate a set of parameters.

        Args:
            parameters: Parameters to evaluate
            config: Optimization configuration

        Returns:
            Score
        """
        try:
            # Check constraints
            for constraint in config.constraints:
                if not self._check_constraint(parameters, constraint):
                    return float("-inf") if config.objective == OptimizationObjective.MAXIMIZE else float("inf")

            # Evaluate objective function
            if asyncio.iscoroutinefunction(self._objective_function):
                score = await self._objective_function(parameters)
            else:
                score = self._objective_function(parameters)

            return float(score)

        except Exception as e:
            logger.error(f"Error evaluating parameters: {e}")
            return float("-inf") if config.objective == OptimizationObjective.MAXIMIZE else float("inf")

    def _check_constraint(
        self,
        parameters: Dict[str, Any],
        constraint: Dict[str, Any],
    ) -> bool:
        """
        Check if constraint is satisfied.

        Args:
            parameters: Parameters to check
            constraint: Constraint definition

        Returns:
            True if satisfied
        """
        param_name = constraint.get("parameter")
        operator = constraint.get("operator")
        value = constraint.get("value")

        if param_name not in parameters:
            return True

        param_value = parameters[param_name]

        if operator == ">":
            return param_value > value
        elif operator == ">=":
            return param_value >= value
        elif operator == "<":
            return param_value < value
        elif operator == "<=":
            return param_value <= value
        elif operator == "==":
            return param_value == value
        elif operator == "!=":
            return param_value != value
        else:
            return True

    def _is_better(
        self,
        new_score: float,
        best_score: float,
        objective: OptimizationObjective,
    ) -> bool:
        """Check if new score is better than best score."""
        if objective == OptimizationObjective.MAXIMIZE:
            return new_score > best_score
        else:
            return new_score < best_score

    # Optimization Algorithms

    async def _grid_search(
        self,
        config: OptimizationConfig,
        opt_id: str,
    ) -> OptimizationResult:
        """Grid search optimization."""
        # Generate grid points
        grid_points = self._generate_grid(config.parameters)

        if not grid_points:
            raise ValueError("No grid points generated")

        # Limit grid points
        grid_points = grid_points[:config.max_iterations]

        # Evaluate all points
        scores = []
        all_parameters = []
        history = []

        for i, params in enumerate(grid_points):
            score = await self._evaluate_parameters(params, config)
            scores.append(score)
            all_parameters.append(params)

            history.append({
                "iteration": i,
                "parameters": params,
                "score": score,
            })

            # Check early stopping
            if i > config.early_stopping_patience:
                recent_scores = scores[-config.early_stopping_patience:]
                if max(recent_scores) - min(recent_scores) < config.early_stopping_threshold:
                    break

        # Find best result
        best_idx = np.argmax(scores) if config.objective == OptimizationObjective.MAXIMIZE else np.argmin(scores)
        best_params = all_parameters[best_idx]
        best_score = scores[best_idx]

        return OptimizationResult(
            id=opt_id,
            config=config,
            best_parameters=best_params,
            best_score=best_score,
            all_scores=scores,
            all_parameters=all_parameters,
            iteration_history=history,
            duration_seconds=time.time() - time_start,
            status="completed",
            metrics={"total_evaluations": len(scores)},
            created_at=datetime.utcnow(),
        )

    async def _random_search(
        self,
        config: OptimizationConfig,
        opt_id: str,
    ) -> OptimizationResult:
        """Random search optimization."""
        scores = []
        all_parameters = []
        history = []
        best_score = float("-inf") if config.objective == OptimizationObjective.MAXIMIZE else float("inf")
        best_params = None

        for i in range(config.max_iterations):
            # Sample parameters
            params = {p.name: p.sample() for p in config.parameters}

            # Evaluate
            score = await self._evaluate_parameters(params, config)
            scores.append(score)
            all_parameters.append(params)

            history.append({
                "iteration": i,
                "parameters": params,
                "score": score,
            })

            # Update best
            if self._is_better(score, best_score, config.objective):
                best_score = score
                best_params = params

            # Check early stopping
            if i > config.early_stopping_patience:
                recent_scores = scores[-config.early_stopping_patience:]
                if max(recent_scores) - min(recent_scores) < config.early_stopping_threshold:
                    break

        return OptimizationResult(
            id=opt_id,
            config=config,
            best_parameters=best_params or {},
            best_score=best_score,
            all_scores=scores,
            all_parameters=all_parameters,
            iteration_history=history,
            duration_seconds=time.time() - time_start,
            status="completed",
            metrics={"total_evaluations": len(scores)},
            created_at=datetime.utcnow(),
        )

    async def _bayesian_optimization(
        self,
        config: OptimizationConfig,
        opt_id: str,
    ) -> OptimizationResult:
        """Bayesian optimization using Gaussian Process."""
        try:
            from bayesian_optimization import BayesianOptimizer as BO
        except ImportError:
            logger.warning("bayesian_optimization not available, falling back to random search")
            return await self._random_search(config, opt_id)

        # Define parameter bounds
        bounds = {}
        for p in config.parameters:
            if p.type == "int":
                bounds[p.name] = (int(p.range[0]), int(p.range[1]))
            elif p.type == "float":
                bounds[p.name] = (p.range[0], p.range[1])
            elif p.type == "categorical":
                bounds[p.name] = p.choices
            elif p.type == "boolean":
                bounds[p.name] = [False, True]

        # Initialize optimizer
        optimizer = BO(
            bounds=bounds,
            objective=lambda **kwargs: asyncio.run(
                self._evaluate_parameters(kwargs, config)
            ),
            maximize=config.objective == OptimizationObjective.MAXIMIZE,
            random_state=config.random_seed,
        )

        # Run optimization
        best_params = {}
        best_score = float("-inf") if config.objective == OptimizationObjective.MAXIMIZE else float("inf")
        scores = []
        all_parameters = []
        history = []

        for i in range(config.max_iterations):
            # Suggest next parameters
            suggested = optimizer.suggest()

            # Evaluate
            score = await self._evaluate_parameters(suggested, config)
            scores.append(score)
            all_parameters.append(suggested)

            history.append({
                "iteration": i,
                "parameters": suggested,
                "score": score,
            })

            # Update optimizer
            optimizer.update(suggested, score)

            # Update best
            if self._is_better(score, best_score, config.objective):
                best_score = score
                best_params = suggested

            # Check early stopping
            if i > config.early_stopping_patience:
                recent_scores = scores[-config.early_stopping_patience:]
                if max(recent_scores) - min(recent_scores) < config.early_stopping_threshold:
                    break

        return OptimizationResult(
            id=opt_id,
            config=config,
            best_parameters=best_params,
            best_score=best_score,
            all_scores=scores,
            all_parameters=all_parameters,
            iteration_history=history,
            duration_seconds=time.time() - time_start,
            status="completed",
            metrics={"total_evaluations": len(scores)},
            created_at=datetime.utcnow(),
        )

    async def _genetic_algorithm(
        self,
        config: OptimizationConfig,
        opt_id: str,
    ) -> OptimizationResult:
        """Genetic algorithm optimization."""
        population_size = min(20, config.max_iterations)
        mutation_rate = 0.1
        crossover_rate = 0.8

        # Initialize population
        population = []
        for _ in range(population_size):
            params = {p.name: p.sample() for p in config.parameters}
            population.append(params)

        scores = []
        all_parameters = []
        history = []
        best_score = float("-inf") if config.objective == OptimizationObjective.MAXIMIZE else float("inf")
        best_params = None

        generation = 0
        total_evaluations = 0

        while total_evaluations < config.max_iterations:
            # Evaluate population
            generation_scores = []
            for params in population:
                score = await self._evaluate_parameters(params, config)
                generation_scores.append(score)
                scores.append(score)
                all_parameters.append(params)
                total_evaluations += 1

                if self._is_better(score, best_score, config.objective):
                    best_score = score
                    best_params = params.copy()

                history.append({
                    "generation": generation,
                    "iteration": total_evaluations,
                    "parameters": params,
                    "score": score,
                })

            # Selection (tournament)
            selected = []
            for _ in range(population_size):
                # Tournament selection
                tournament_size = 3
                tournament_idx = np.random.choice(len(population), tournament_size, replace=False)
                tournament_scores = [generation_scores[i] for i in tournament_idx]

                if config.objective == OptimizationObjective.MAXIMIZE:
                    winner_idx = tournament_idx[np.argmax(tournament_scores)]
                else:
                    winner_idx = tournament_idx[np.argmin(tournament_scores)]

                selected.append(population[winner_idx].copy())

            # Crossover
            new_population = []
            for i in range(0, population_size, 2):
                if i + 1 < population_size and np.random.random() < crossover_rate:
                    parent1 = selected[i]
                    parent2 = selected[i + 1]
                    child1, child2 = self._crossover(parent1, parent2)
                    new_population.extend([child1, child2])
                else:
                    new_population.append(selected[i].copy())
                    if i + 1 < population_size:
                        new_population.append(selected[i + 1].copy())

            # Mutation
            for params in new_population:
                for param_name in params:
                    if np.random.random() < mutation_rate:
                        # Find parameter definition
                        param_def = next((p for p in config.parameters if p.name == param_name), None)
                        if param_def:
                            params[param_name] = param_def.sample()

            population = new_population[:population_size]
            generation += 1

            # Check early stopping
            if generation > config.early_stopping_patience:
                recent_scores = scores[-config.early_stopping_patience * population_size:]
                if len(recent_scores) > 0:
                    score_range = max(recent_scores) - min(recent_scores)
                    if score_range < config.early_stopping_threshold:
                        break

        return OptimizationResult(
            id=opt_id,
            config=config,
            best_parameters=best_params or {},
            best_score=best_score,
            all_scores=scores,
            all_parameters=all_parameters,
            iteration_history=history,
            duration_seconds=time.time() - time_start,
            status="completed",
            metrics={"generations": generation, "total_evaluations": total_evaluations},
            created_at=datetime.utcnow(),
        )

    def _crossover(
        self,
        parent1: Dict[str, Any],
        parent2: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Crossover for genetic algorithm."""
        child1 = {}
        child2 = {}

        for key in parent1:
            if np.random.random() < 0.5:
                child1[key] = parent1[key]
                child2[key] = parent2[key]
            else:
                child1[key] = parent2[key]
                child2[key] = parent1[key]

        return child1, child2

    async def _simulated_annealing(
        self,
        config: OptimizationConfig,
        opt_id: str,
    ) -> OptimizationResult:
        """Simulated annealing optimization."""
        # Initialize with random parameters
        current_params = {p.name: p.sample() for p in config.parameters}
        current_score = await self._evaluate_parameters(current_params, config)

        best_params = current_params.copy()
        best_score = current_score

        scores = [current_score]
        all_parameters = [current_params.copy()]
        history = [{
            "iteration": 0,
            "parameters": current_params.copy(),
            "score": current_score,
            "temperature": 1.0,
        }]

        temperature = 1.0
        cooling_rate = 0.99

        for i in range(1, config.max_iterations):
            # Generate neighbor
            neighbor_params = current_params.copy()
            param_name = random.choice(list(neighbor_params.keys()))
            param_def = next((p for p in config.parameters if p.name == param_name), None)

            if param_def:
                neighbor_params[param_name] = param_def.sample()

            neighbor_score = await self._evaluate_parameters(neighbor_params, config)

            # Decide whether to accept
            if self._is_better(neighbor_score, current_score, config.objective):
                accept = True
            else:
                # Accept with probability based on temperature
                if config.objective == OptimizationObjective.MAXIMIZE:
                    delta = neighbor_score - current_score
                else:
                    delta = current_score - neighbor_score

                probability = np.exp(delta / (temperature + 1e-10))
                accept = np.random.random() < probability

            if accept:
                current_params = neighbor_params.copy()
                current_score = neighbor_score

            # Update best
            if self._is_better(current_score, best_score, config.objective):
                best_params = current_params.copy()
                best_score = current_score

            scores.append(current_score)
            all_parameters.append(current_params.copy())
            history.append({
                "iteration": i,
                "parameters": current_params.copy(),
                "score": current_score,
                "temperature": temperature,
            })

            # Cool down
            temperature *= cooling_rate

            # Check early stopping
            if temperature < 0.01:
                break

        return OptimizationResult(
            id=opt_id,
            config=config,
            best_parameters=best_params,
            best_score=best_score,
            all_scores=scores,
            all_parameters=all_parameters,
            iteration_history=history,
            duration_seconds=time.time() - time_start,
            status="completed",
            metrics={"final_temperature": temperature},
            created_at=datetime.utcnow(),
        )

    async def _particle_swarm_optimization(
        self,
        config: OptimizationConfig,
        opt_id: str,
    ) -> OptimizationResult:
        """Particle swarm optimization."""
        # Implementation simplified for brevity
        # Full implementation would include velocity updates, inertia, etc.
        return await self._random_search(config, opt_id)

    async def _multi_objective_optimization(
        self,
        config: OptimizationConfig,
        opt_id: str,
    ) -> OptimizationResult:
        """Multi-objective optimization."""
        # Implementation simplified for brevity
        # Full implementation would use NSGA-II or similar
        return await self._random_search(config, opt_id)

    async def _adaptive_optimization(
        self,
        config: OptimizationConfig,
        opt_id: str,
    ) -> OptimizationResult:
        """Adaptive optimization with dynamic strategy selection."""
        # Implementation simplified for brevity
        # Full implementation would switch between strategies based on performance
        return await self._random_search(config, opt_id)

    def _generate_grid(self, parameters: List[ParameterSpace]) -> List[Dict[str, Any]]:
        """Generate grid points for grid search."""
        if not parameters:
            return []

        # Generate grid for each parameter
        grids = []
        for param in parameters:
            if param.type == "int":
                if param.range and param.step:
                    values = list(range(int(param.range[0]), int(param.range[1]) + 1, int(param.step)))
                elif param.range:
                    values = list(range(int(param.range[0]), int(param.range[1]) + 1))
                else:
                    values = [param.default] if param.default is not None else []
            elif param.type == "float":
                if param.range and param.step:
                    values = np.arange(param.range[0], param.range[1] + param.step, param.step)
                elif param.range:
                    values = np.linspace(param.range[0], param.range[1], 10)
                else:
                    values = [param.default] if param.default is not None else []
            elif param.type == "categorical":
                values = param.choices or []
            elif param.type == "boolean":
                values = [False, True]
            else:
                values = [param.default] if param.default is not None else []

            grids.append([(param.name, v) for v in values])

        # Generate combinations
        if not grids:
            return []

        # Limit grid size
        max_grid_size = 10000
        total_combinations = 1
        for grid in grids:
            total_combinations *= len(grid)

        if total_combinations > max_grid_size:
            # Sample from grid
            samples = []
            for _ in range(min(max_grid_size, 1000)):
                params = {}
                for grid in grids:
                    param_name, value = random.choice(grid)
                    params[param_name] = value
                samples.append(params)
            return samples

        # Generate all combinations
        from itertools import product

        combinations = []
        for combination in product(*grids):
            params = {}
            for param_name, value in combination:
                params[param_name] = value
            combinations.append(params)

        return combinations

    async def get_results(
        self,
        limit: int = 10,
        status: Optional[str] = None,
    ) -> List[OptimizationResult]:
        """
        Get optimization results.

        Args:
            limit: Maximum number of results
            status: Filter by status

        Returns:
            List of optimization results
        """
        async with self._lock:
            results = list(self._results.values())

            if status:
                results = [r for r in results if r.status == status]

            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[:limit]

    async def get_best_result(self) -> Optional[OptimizationResult]:
        """
        Get the best optimization result.

        Returns:
            Best result or None
        """
        async with self._lock:
            results = [r for r in self._results.values() if r.status == "completed"]

            if not results:
                return None

            # Find best result
            best_result = None
            best_score = float("-inf") if results[0].config.objective == OptimizationObjective.MAXIMIZE else float("inf")

            for result in results:
                if self._is_better(result.best_score, best_score, result.config.objective):
                    best_score = result.best_score
                    best_result = result

            return best_result

    async def save_result(self, result: OptimizationResult):
        """
        Save optimization result.

        Args:
            result: Result to save
        """
        async with self._lock:
            self._results[result.id] = result

            # Save to file
            file_path = self.results_path / f"{result.id}.json"
            with open(file_path, "w") as f:
                json.dump(result.to_dict(), f, indent=2)

            # Limit results
            if len(self._results) > self.max_results:
                oldest = sorted(self._results.keys(), key=lambda x: self._results[x].created_at)[0]
                del self._results[oldest]
                (self.results_path / f"{oldest}.json").unlink(missing_ok=True)

        logger.info(f"Optimization result saved: {result.id}")

    async def get_optimization_progress(self, opt_id: str) -> Optional[Dict[str, Any]]:
        """
        Get progress of a running optimization.

        Args:
            opt_id: Optimization ID

        Returns:
            Progress information or None
        """
        if opt_id not in self._running_optimizations:
            return None

        # Get progress from result
        result = self._results.get(opt_id)
        if not result:
            return {
                "status": "running",
                "iterations": 0,
            }

        return {
            "status": result.status,
            "iterations": len(result.all_scores),
            "best_score": result.best_score,
            "duration_seconds": result.duration_seconds,
        }

    async def stop_optimization(self, opt_id: str) -> bool:
        """
        Stop a running optimization.

        Args:
            opt_id: Optimization ID

        Returns:
            True if stopped
        """
        if opt_id not in self._running_optimizations:
            return False

        task = self._running_optimizations[opt_id]
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        del self._running_optimizations[opt_id]

        # Update result status
        if opt_id in self._results:
            self._results[opt_id].status = "stopped"

        logger.info(f"Optimization {opt_id} stopped")
        return True

    async def shutdown(self):
        """Shutdown the optimizer."""
        # Stop all running optimizations
        for opt_id in list(self._running_optimizations.keys()):
            await self.stop_optimization(opt_id)

        logger.info("PerformanceOptimizer shut down")


# Export singleton
performance_optimizer = PerformanceOptimizer()
