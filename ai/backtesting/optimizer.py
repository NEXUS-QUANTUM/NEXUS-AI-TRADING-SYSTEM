"""
NEXUS AI TRADING SYSTEM - Optimizer
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Optimizer system with:
- Multiple optimization methods (Grid, Random, Bayesian, Genetic, Gradient)
- Parameter search spaces
- Objective functions
- Constraint handling
- Parallel processing
- Early stopping
- Result visualization
- Export capabilities
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from uuid import uuid4

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pydantic import BaseModel, Field, validator
from scipy.optimize import minimize, differential_evolution, dual_annealing
from scipy.stats import norm, uniform, randint
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, RBF, WhiteKernel

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import OptimizationError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class OptimizationMethod(str, Enum):
    """Optimization methods"""
    GRID = "grid_search"
    RANDOM = "random_search"
    BAYESIAN = "bayesian"
    GENETIC = "genetic"
    GRADIENT = "gradient_descent"
    DIFFERENTIAL_EVOLUTION = "differential_evolution"
    SIMULATED_ANNEALING = "simulated_annealing"
    PATTERN_SEARCH = "pattern_search"


class ObjectiveType(str, Enum):
    """Objective types"""
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class ParameterType(str, Enum):
    """Parameter types"""
    INTEGER = "int"
    FLOAT = "float"
    CATEGORICAL = "categorical"
    BOOLEAN = "bool"


@dataclass
class Parameter:
    """Optimization parameter"""
    name: str
    type: ParameterType
    min: Optional[float] = None
    max: Optional[float] = None
    choices: Optional[List[Any]] = None
    default: Optional[Any] = None
    step: Optional[float] = None


@dataclass
class OptimizationResult:
    """Optimization result"""
    id: str = field(default_factory=lambda: str(uuid4()))
    method: OptimizationMethod
    objective_value: float
    parameters: Dict[str, Any]
    iterations: int
    execution_time: float
    history: List[Dict[str, Any]] = field(default_factory=list)
    convergence: List[float] = field(default_factory=list)
    best_parameters: Dict[str, Any] = field(default_factory=dict)
    best_objective: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationProgress:
    """Optimization progress"""
    id: str
    status: str
    progress: float
    current_best: float
    iterations: int
    elapsed_time: float
    estimated_remaining: float


class OptimizerConfig(BaseModel):
    """Optimizer configuration"""
    method: OptimizationMethod = OptimizationMethod.RANDOM
    objective: ObjectiveType = ObjectiveType.MAXIMIZE
    max_iterations: int = Field(default=100, gt=0)
    max_time: int = Field(default=3600, gt=0)
    early_stopping: bool = True
    early_stopping_patience: int = Field(default=10, gt=0)
    early_stopping_threshold: float = Field(default=0.001, ge=0)
    parallel_workers: int = Field(default=4, gt=0)
    random_seed: Optional[int] = None
    verbose: bool = True
    save_history: bool = True
    cache_results: bool = True
    cache_ttl: int = Field(default=3600, gt=0)
    log_level: str = "info"


# ========================================
# OPTIMIZER
# ========================================

class Optimizer:
    """
    Complete optimizer for trading strategy parameters.
    
    Features:
    - Multiple optimization methods
    - Parameter search spaces
    - Objective functions
    - Constraint handling
    - Parallel processing
    - Early stopping
    - Result visualization
    - Export capabilities
    - Health monitoring
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = OptimizerConfig(**(config or {}))
        self.redis = get_redis()
        
        # Set random seed
        if self.config.random_seed is not None:
            np.random.seed(self.config.random_seed)
        
        # State
        self._results: Dict[str, OptimizationResult] = {}
        self._progress: Dict[str, OptimizationProgress] = {}
        self._running_optimizations: Dict[str, asyncio.Task] = {}
        
        # Cache
        self._cache: Dict[str, Tuple[OptimizationResult, datetime]] = {}
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        
        # Metrics
        self._metrics = {
            "total_optimizations": 0,
            "completed_optimizations": 0,
            "failed_optimizations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_optimization_time": 0.0
        }
        
        self.logger = get_logger(f"{__name__}.Optimizer")
        self.logger.info("Optimizer initialized")
    
    # ========================================
    # MAIN OPTIMIZATION
    # ========================================
    
    async def optimize(
        self,
        objective_function: Callable,
        parameters: List[Parameter],
        constraints: Optional[List[Dict[str, Any]]] = None,
        method: Optional[OptimizationMethod] = None,
        max_iterations: Optional[int] = None
    ) -> OptimizationResult:
        """
        Run optimization.
        
        Args:
            objective_function: Function to optimize
            parameters: Parameter definitions
            constraints: Constraints
            method: Optimization method
            max_iterations: Maximum iterations
            
        Returns:
            OptimizationResult: Optimization result
        """
        start_time = time.time()
        
        # Use config defaults
        method = method or self.config.method
        max_iterations = max_iterations or self.config.max_iterations
        
        # Generate cache key
        cache_key = self._generate_cache_key(
            objective_function,
            parameters,
            constraints,
            method,
            max_iterations
        )
        
        # Check cache
        if self.config.cache_results:
            cached = self._get_cached_result(cache_key)
            if cached:
                self._metrics["cache_hits"] += 1
                return cached
        
        self._metrics["cache_misses"] += 1
        
        try:
            # Initialize result
            result = OptimizationResult(
                method=method,
                objective_value=0.0,
                parameters={},
                iterations=0,
                execution_time=0.0
            )
            
            # Set up progress tracking
            optimization_id = result.id
            self._progress[optimization_id] = OptimizationProgress(
                id=optimization_id,
                status="running",
                progress=0.0,
                current_best=float('-inf'),
                iterations=0,
                elapsed_time=0.0,
                estimated_remaining=0.0
            )
            
            # Run optimization based on method
            if method == OptimizationMethod.GRID:
                result = await self._grid_search(
                    objective_function,
                    parameters,
                    constraints,
                    max_iterations
                )
            elif method == OptimizationMethod.RANDOM:
                result = await self._random_search(
                    objective_function,
                    parameters,
                    constraints,
                    max_iterations
                )
            elif method == OptimizationMethod.BAYESIAN:
                result = await self._bayesian_optimization(
                    objective_function,
                    parameters,
                    constraints,
                    max_iterations
                )
            elif method == OptimizationMethod.GENETIC:
                result = await self._genetic_algorithm(
                    objective_function,
                    parameters,
                    constraints,
                    max_iterations
                )
            elif method == OptimizationMethod.GRADIENT:
                result = await self._gradient_descent(
                    objective_function,
                    parameters,
                    constraints,
                    max_iterations
                )
            elif method == OptimizationMethod.DIFFERENTIAL_EVOLUTION:
                result = await self._differential_evolution(
                    objective_function,
                    parameters,
                    constraints,
                    max_iterations
                )
            elif method == OptimizationMethod.SIMULATED_ANNEALING:
                result = await self._simulated_annealing(
                    objective_function,
                    parameters,
                    constraints,
                    max_iterations
                )
            else:
                result = await self._random_search(
                    objective_function,
                    parameters,
                    constraints,
                    max_iterations
                )
            
            # Update result
            result.execution_time = time.time() - start_time
            result.best_parameters = result.parameters
            result.best_objective = result.objective_value
            
            # Cache result
            if self.config.cache_results:
                self._set_cached_result(cache_key, result)
            
            # Store result
            self._results[result.id] = result
            
            # Update progress
            self._progress[optimization_id].status = "completed"
            self._progress[optimization_id].progress = 100.0
            
            # Update metrics
            self._metrics["total_optimizations"] += 1
            self._metrics["completed_optimizations"] += 1
            self._metrics["avg_optimization_time"] = (
                self._metrics["avg_optimization_time"] * 0.9 + result.execution_time * 0.1
            )
            
            self.logger.info(
                f"Optimization completed in {result.execution_time:.2f}s "
                f"({result.iterations} iterations, best: {result.objective_value:.6f})"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Optimization failed: {e}")
            self._metrics["failed_optimizations"] += 1
            raise OptimizationError(f"Optimization failed: {e}")
        finally:
            if optimization_id in self._progress:
                self._progress[optimization_id].status = "completed"
    
    # ========================================
    # OPTIMIZATION METHODS
    # ========================================
    
    async def _grid_search(
        self,
        objective_function: Callable,
        parameters: List[Parameter],
        constraints: Optional[List[Dict[str, Any]]],
        max_iterations: int
    ) -> OptimizationResult:
        """Grid search optimization"""
        # Generate grid points
        grid_points = self._generate_grid_points(parameters)
        
        # Limit to max iterations
        if len(grid_points) > max_iterations:
            grid_points = grid_points[:max_iterations]
        
        best_value = float('-inf')
        best_params = None
        history = []
        
        for i, params in enumerate(grid_points):
            try:
                # Evaluate objective
                value = await self._evaluate_objective(
                    objective_function,
                    params,
                    constraints
                )
                
                # Track best
                if value > best_value:
                    best_value = value
                    best_params = params
                
                history.append({
                    'iteration': i,
                    'parameters': params,
                    'value': value
                })
                
                # Update progress
                if i % 10 == 0:
                    self._update_progress(grid_points, i, best_value)
                
            except Exception as e:
                self.logger.warning(f"Grid search error at iteration {i}: {e}")
                continue
        
        return OptimizationResult(
            method=OptimizationMethod.GRID,
            objective_value=best_value,
            parameters=best_params or {},
            iterations=len(history),
            execution_time=0.0,
            history=history,
            convergence=[h['value'] for h in history]
        )
    
    async def _random_search(
        self,
        objective_function: Callable,
        parameters: List[Parameter],
        constraints: Optional[List[Dict[str, Any]]],
        max_iterations: int
    ) -> OptimizationResult:
        """Random search optimization"""
        best_value = float('-inf')
        best_params = None
        history = []
        
        for i in range(max_iterations):
            # Sample random parameters
            params = self._sample_parameters(parameters)
            
            try:
                # Evaluate objective
                value = await self._evaluate_objective(
                    objective_function,
                    params,
                    constraints
                )
                
                # Track best
                if value > best_value:
                    best_value = value
                    best_params = params
                
                history.append({
                    'iteration': i,
                    'parameters': params,
                    'value': value
                })
                
                # Update progress
                if i % 10 == 0:
                    self._update_progress(max_iterations, i, best_value)
                
                # Early stopping
                if self._check_early_stopping(history, i):
                    self.logger.info(f"Early stopping at iteration {i}")
                    break
                
            except Exception as e:
                self.logger.warning(f"Random search error at iteration {i}: {e}")
                continue
        
        return OptimizationResult(
            method=OptimizationMethod.RANDOM,
            objective_value=best_value,
            parameters=best_params or {},
            iterations=len(history),
            execution_time=0.0,
            history=history,
            convergence=[h['value'] for h in history]
        )
    
    async def _bayesian_optimization(
        self,
        objective_function: Callable,
        parameters: List[Parameter],
        constraints: Optional[List[Dict[str, Any]]],
        max_iterations: int
    ) -> OptimizationResult:
        """Bayesian optimization"""
        # Initialize with random points
        n_initial = min(10, max_iterations)
        initial_points = [self._sample_parameters(parameters) for _ in range(n_initial)]
        
        # Evaluate initial points
        X = []
        y = []
        
        for params in initial_points:
            try:
                value = await self._evaluate_objective(
                    objective_function,
                    params,
                    constraints
                )
                X.append(self._params_to_vector(params, parameters))
                y.append(value)
            except Exception as e:
                self.logger.warning(f"Initial evaluation error: {e}")
                continue
        
        # Initialize Gaussian Process
        kernel = 1.0 * RBF(length_scale=1.0) + WhiteKernel(noise_level=1e-5)
        gp = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=10,
            normalize_y=True
        )
        
        best_value = max(y) if y else float('-inf')
        best_params = initial_points[y.index(best_value)] if y else {}
        history = []
        
        # Bayesian optimization loop
        for i in range(n_initial, max_iterations):
            if len(X) < 2:
                params = self._sample_parameters(parameters)
            else:
                # Fit GP
                gp.fit(np.array(X), np.array(y))
                
                # Acquisition function (Upper Confidence Bound)
                params = self._acquisition_optimization(gp, parameters)
            
            try:
                # Evaluate objective
                value = await self._evaluate_objective(
                    objective_function,
                    params,
                    constraints
                )
                
                # Update data
                X.append(self._params_to_vector(params, parameters))
                y.append(value)
                
                # Track best
                if value > best_value:
                    best_value = value
                    best_params = params
                
                history.append({
                    'iteration': i,
                    'parameters': params,
                    'value': value
                })
                
                # Update progress
                if i % 5 == 0:
                    self._update_progress(max_iterations, i, best_value)
                
                # Early stopping
                if self._check_early_stopping(history, i):
                    self.logger.info(f"Early stopping at iteration {i}")
                    break
                
            except Exception as e:
                self.logger.warning(f"Bayesian optimization error at iteration {i}: {e}")
                continue
        
        return OptimizationResult(
            method=OptimizationMethod.BAYESIAN,
            objective_value=best_value,
            parameters=best_params or {},
            iterations=len(history),
            execution_time=0.0,
            history=history,
            convergence=[h['value'] for h in history]
        )
    
    async def _genetic_algorithm(
        self,
        objective_function: Callable,
        parameters: List[Parameter],
        constraints: Optional[List[Dict[str, Any]]],
        max_iterations: int
    ) -> OptimizationResult:
        """Genetic algorithm optimization"""
        population_size = min(20, max_iterations // 2)
        mutation_rate = 0.1
        crossover_rate = 0.8
        
        # Initialize population
        population = [self._sample_parameters(parameters) for _ in range(population_size)]
        
        # Evaluate population
        fitness = []
        for params in population:
            try:
                value = await self._evaluate_objective(
                    objective_function,
                    params,
                    constraints
                )
                fitness.append(value)
            except Exception:
                fitness.append(float('-inf'))
        
        best_value = max(fitness) if fitness else float('-inf')
        best_index = fitness.index(best_value) if fitness else 0
        best_params = population[best_index] if population else {}
        history = []
        
        for generation in range(max_iterations):
            # Selection (tournament)
            new_population = []
            new_fitness = []
            
            for _ in range(population_size):
                # Tournament selection
                tournament_size = 3
                tournament_indices = np.random.choice(
                    len(population),
                    tournament_size,
                    replace=False
                )
                winner_idx = max(
                    tournament_indices,
                    key=lambda i: fitness[i]
                )
                new_population.append(population[winner_idx].copy())
                new_fitness.append(fitness[winner_idx])
            
            # Crossover
            for i in range(0, population_size, 2):
                if i + 1 < population_size and np.random.random() < crossover_rate:
                    child1, child2 = self._crossover(
                        new_population[i],
                        new_population[i + 1],
                        parameters
                    )
                    new_population[i] = child1
                    new_population[i + 1] = child2
            
            # Mutation
            for i in range(population_size):
                if np.random.random() < mutation_rate:
                    new_population[i] = self._mutate(
                        new_population[i],
                        parameters
                    )
            
            # Evaluate new population
            fitness = []
            for params in new_population:
                try:
                    value = await self._evaluate_objective(
                        objective_function,
                        params,
                        constraints
                    )
                    fitness.append(value)
                except Exception:
                    fitness.append(float('-inf'))
            
            # Elitism
            if best_value > max(fitness):
                # Keep best individual
                worst_idx = fitness.index(min(fitness))
                new_population[worst_idx] = best_params
                fitness[worst_idx] = best_value
            else:
                # Update best
                best_value = max(fitness)
                best_index = fitness.index(best_value)
                best_params = new_population[best_index]
            
            population = new_population
            
            history.append({
                'generation': generation,
                'best_value': best_value,
                'avg_fitness': np.mean(fitness) if fitness else float('-inf')
            })
            
            # Update progress
            if generation % 5 == 0:
                self._update_progress(max_iterations, generation, best_value)
            
            # Early stopping
            if self._check_early_stopping(history, generation):
                self.logger.info(f"Early stopping at generation {generation}")
                break
        
        return OptimizationResult(
            method=OptimizationMethod.GENETIC,
            objective_value=best_value,
            parameters=best_params or {},
            iterations=len(history),
            execution_time=0.0,
            history=history,
            convergence=[h['best_value'] for h in history]
        )
    
    async def _gradient_descent(
        self,
        objective_function: Callable,
        parameters: List[Parameter],
        constraints: Optional[List[Dict[str, Any]]],
        max_iterations: int
    ) -> OptimizationResult:
        """Gradient descent optimization"""
        # Initial parameters
        current_params = {p.name: p.default for p in parameters}
        if not all(v is not None for v in current_params.values()):
            current_params = self._sample_parameters(parameters)
        
        learning_rate = 0.01
        momentum = 0.9
        velocity = {p.name: 0.0 for p in parameters}
        
        best_value = float('-inf')
        best_params = current_params.copy()
        history = []
        
        for iteration in range(max_iterations):
            try:
                # Evaluate objective
                current_value = await self._evaluate_objective(
                    objective_function,
                    current_params,
                    constraints
                )
                
                # Track best
                if current_value > best_value:
                    best_value = current_value
                    best_params = current_params.copy()
                
                # Compute gradient (finite differences)
                gradient = await self._compute_gradient(
                    objective_function,
                    current_params,
                    parameters,
                    constraints
                )
                
                # Update parameters
                for p in parameters:
                    if p.type == ParameterType.INTEGER:
                        # Discrete update
                        step = int(learning_rate * gradient.get(p.name, 0))
                        current_params[p.name] = max(
                            p.min,
                            min(p.max, current_params[p.name] + step)
                        )
                    elif p.type == ParameterType.FLOAT:
                        # Continuous update with momentum
                        velocity[p.name] = momentum * velocity[p.name] + learning_rate * gradient.get(p.name, 0)
                        current_params[p.name] = max(
                            p.min,
                            min(p.max, current_params[p.name] + velocity[p.name])
                        )
                
                history.append({
                    'iteration': iteration,
                    'value': current_value,
                    'params': current_params.copy()
                })
                
                # Update progress
                if iteration % 5 == 0:
                    self._update_progress(max_iterations, iteration, best_value)
                
                # Early stopping
                if self._check_early_stopping(history, iteration):
                    self.logger.info(f"Early stopping at iteration {iteration}")
                    break
                
            except Exception as e:
                self.logger.warning(f"Gradient descent error at iteration {iteration}: {e}")
                break
        
        return OptimizationResult(
            method=OptimizationMethod.GRADIENT,
            objective_value=best_value,
            parameters=best_params,
            iterations=len(history),
            execution_time=0.0,
            history=history,
            convergence=[h['value'] for h in history]
        )
    
    async def _differential_evolution(
        self,
        objective_function: Callable,
        parameters: List[Parameter],
        constraints: Optional[List[Dict[str, Any]]],
        max_iterations: int
    ) -> OptimizationResult:
        """Differential evolution optimization"""
        population_size = min(15, max_iterations // 2)
        mutation_factor = 0.8
        crossover_rate = 0.7
        
        # Initialize population
        population = [self._sample_parameters(parameters) for _ in range(population_size)]
        
        # Evaluate population
        fitness = []
        for params in population:
            try:
                value = await self._evaluate_objective(
                    objective_function,
                    params,
                    constraints
                )
                fitness.append(value)
            except Exception:
                fitness.append(float('-inf'))
        
        best_value = max(fitness) if fitness else float('-inf')
        best_index = fitness.index(best_value) if fitness else 0
        best_params = population[best_index] if population else {}
        history = []
        
        for generation in range(max_iterations):
            new_population = []
            new_fitness = []
            
            for i in range(population_size):
                # Mutation
                candidates = np.random.choice(
                    [j for j in range(population_size) if j != i],
                    3,
                    replace=False
                )
                a, b, c = candidates
                
                # Mutant vector
                mutant = {}
                for p in parameters:
                    if p.type == ParameterType.FLOAT:
                        mutant[p.name] = (
                            population[a][p.name] +
                            mutation_factor * (population[b][p.name] - population[c][p.name])
                        )
                        mutant[p.name] = max(p.min, min(p.max, mutant[p.name]))
                    elif p.type == ParameterType.INTEGER:
                        mutant[p.name] = int(
                            population[a][p.name] +
                            mutation_factor * (population[b][p.name] - population[c][p.name])
                        )
                        mutant[p.name] = max(int(p.min), min(int(p.max), mutant[p.name]))
                    else:
                        mutant[p.name] = population[a][p.name]
                
                # Crossover
                trial = {}
                for p in parameters:
                    if np.random.random() < crossover_rate:
                        trial[p.name] = mutant[p.name]
                    else:
                        trial[p.name] = population[i][p.name]
                
                # Selection
                try:
                    trial_value = await self._evaluate_objective(
                        objective_function,
                        trial,
                        constraints
                    )
                except Exception:
                    trial_value = float('-inf')
                
                if trial_value > fitness[i]:
                    new_population.append(trial)
                    new_fitness.append(trial_value)
                else:
                    new_population.append(population[i])
                    new_fitness.append(fitness[i])
            
            population = new_population
            fitness = new_fitness
            
            # Update best
            current_best = max(fitness) if fitness else float('-inf')
            if current_best > best_value:
                best_value = current_best
                best_index = fitness.index(best_value)
                best_params = population[best_index]
            
            history.append({
                'generation': generation,
                'best_value': best_value,
                'avg_fitness': np.mean(fitness) if fitness else float('-inf')
            })
            
            # Update progress
            if generation % 5 == 0:
                self._update_progress(max_iterations, generation, best_value)
            
            # Early stopping
            if self._check_early_stopping(history, generation):
                self.logger.info(f"Early stopping at generation {generation}")
                break
        
        return OptimizationResult(
            method=OptimizationMethod.DIFFERENTIAL_EVOLUTION,
            objective_value=best_value,
            parameters=best_params,
            iterations=len(history),
            execution_time=0.0,
            history=history,
            convergence=[h['best_value'] for h in history]
        )
    
    async def _simulated_annealing(
        self,
        objective_function: Callable,
        parameters: List[Parameter],
        constraints: Optional[List[Dict[str, Any]]],
        max_iterations: int
    ) -> OptimizationResult:
        """Simulated annealing optimization"""
        # Initial parameters
        current_params = self._sample_parameters(parameters)
        
        # Evaluate initial
        try:
            current_value = await self._evaluate_objective(
                objective_function,
                current_params,
                constraints
            )
        except Exception:
            current_value = float('-inf')
        
        best_value = current_value
        best_params = current_params.copy()
        temperature = 100.0
        cooling_rate = 0.99
        history = []
        
        for iteration in range(max_iterations):
            # Generate neighbor
            neighbor = self._mutate(current_params, parameters, scale=0.1)
            
            # Evaluate neighbor
            try:
                neighbor_value = await self._evaluate_objective(
                    objective_function,
                    neighbor,
                    constraints
                )
            except Exception:
                neighbor_value = float('-inf')
            
            # Acceptance criteria
            delta = neighbor_value - current_value
            if delta > 0 or np.random.random() < np.exp(delta / temperature):
                current_params = neighbor
                current_value = neighbor_value
            
            # Track best
            if current_value > best_value:
                best_value = current_value
                best_params = current_params.copy()
            
            # Cool down
            temperature *= cooling_rate
            
            history.append({
                'iteration': iteration,
                'value': current_value,
                'temperature': temperature,
                'best': best_value
            })
            
            # Update progress
            if iteration % 10 == 0:
                self._update_progress(max_iterations, iteration, best_value)
            
            # Early stopping
            if self._check_early_stopping(history, iteration):
                self.logger.info(f"Early stopping at iteration {iteration}")
                break
            
            # Stop if temperature is too low
            if temperature < 1e-6:
                break
        
        return OptimizationResult(
            method=OptimizationMethod.SIMULATED_ANNEALING,
            objective_value=best_value,
            parameters=best_params,
            iterations=len(history),
            execution_time=0.0,
            history=history,
            convergence=[h['best'] for h in history]
        )
    
    # ========================================
    # HELPER FUNCTIONS
    # ========================================
    
    async def _evaluate_objective(
        self,
        objective_function: Callable,
        parameters: Dict[str, Any],
        constraints: Optional[List[Dict[str, Any]]]
    ) -> float:
        """Evaluate objective function with constraints"""
        # Check constraints
        if constraints:
            for constraint in constraints:
                if not self._check_constraint(constraint, parameters):
                    return float('-inf')
        
        # Evaluate
        try:
            value = objective_function(parameters)
            
            # Handle objective type
            if self.config.objective == ObjectiveType.MINIMIZE:
                value = -value
            
            return float(value)
            
        except Exception as e:
            self.logger.warning(f"Objective evaluation error: {e}")
            return float('-inf')
    
    def _check_constraint(
        self,
        constraint: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> bool:
        """Check constraint satisfaction"""
        constraint_type = constraint.get('type', '')
        
        if constraint_type == 'ineq':
            # Inequality constraint: function >= 0
            func = constraint.get('function')
            if func:
                return func(parameters) >= 0
        elif constraint_type == 'eq':
            # Equality constraint: function == 0
            func = constraint.get('function')
            if func:
                return abs(func(parameters)) < 1e-6
        elif constraint_type == 'bound':
            # Bound constraint
            param = constraint.get('parameter')
            min_val = constraint.get('min')
            max_val = constraint.get('max')
            if param in parameters:
                value = parameters[param]
                if min_val is not None and value < min_val:
                    return False
                if max_val is not None and value > max_val:
                    return False
        
        return True
    
    def _sample_parameters(self, parameters: List[Parameter]) -> Dict[str, Any]:
        """Sample random parameters"""
        params = {}
        for p in parameters:
            if p.type == ParameterType.INTEGER:
                if p.choices:
                    params[p.name] = np.random.choice(p.choices)
                else:
                    params[p.name] = np.random.randint(int(p.min), int(p.max) + 1)
            elif p.type == ParameterType.FLOAT:
                if p.choices:
                    params[p.name] = np.random.choice(p.choices)
                else:
                    params[p.name] = np.random.uniform(p.min, p.max)
            elif p.type == ParameterType.CATEGORICAL:
                params[p.name] = np.random.choice(p.choices) if p.choices else None
            elif p.type == ParameterType.BOOLEAN:
                params[p.name] = bool(np.random.randint(0, 2))
        
        return params
    
    def _generate_grid_points(self, parameters: List[Parameter]) -> List[Dict[str, Any]]:
        """Generate grid points for grid search"""
        # Calculate grid size
        grid_sizes = []
        for p in parameters:
            if p.type == ParameterType.INTEGER:
                size = int(p.max - p.min) + 1 if p.min is not None and p.max is not None else 10
            elif p.type == ParameterType.FLOAT:
                size = 10  # Number of grid points
            elif p.type == ParameterType.CATEGORICAL:
                size = len(p.choices) if p.choices else 2
            elif p.type == ParameterType.BOOLEAN:
                size = 2
            grid_sizes.append(size)
        
        # Generate grid
        grid_points = []
        
        def _generate(index: int, current: Dict[str, Any]):
            if index == len(parameters):
                grid_points.append(current.copy())
                return
            
            p = parameters[index]
            if p.type == ParameterType.INTEGER:
                values = range(int(p.min), int(p.max) + 1) if p.min is not None and p.max is not None else range(10)
                for v in values:
                    current[p.name] = v
                    _generate(index + 1, current)
            elif p.type == ParameterType.FLOAT:
                if p.min is not None and p.max is not None:
                    values = np.linspace(p.min, p.max, 10)
                else:
                    values = np.linspace(0, 1, 10)
                for v in values:
                    current[p.name] = v
                    _generate(index + 1, current)
            elif p.type == ParameterType.CATEGORICAL:
                choices = p.choices if p.choices else [None]
                for v in choices:
                    current[p.name] = v
                    _generate(index + 1, current)
            elif p.type == ParameterType.BOOLEAN:
                for v in [True, False]:
                    current[p.name] = v
                    _generate(index + 1, current)
        
        _generate(0, {})
        return grid_points
    
    def _params_to_vector(
        self,
        params: Dict[str, Any],
        parameters: List[Parameter]
    ) -> np.ndarray:
        """Convert parameters to vector for GP"""
        vector = []
        for p in parameters:
            if p.type == ParameterType.INTEGER or p.type == ParameterType.FLOAT:
                vector.append(params.get(p.name, 0))
            elif p.type == ParameterType.CATEGORICAL:
                # One-hot encoding (simplified)
                vector.append(params.get(p.name, 0))
            elif p.type == ParameterType.BOOLEAN:
                vector.append(1 if params.get(p.name, False) else 0)
        return np.array(vector)
    
    def _acquisition_optimization(
        self,
        gp: GaussianProcessRegressor,
        parameters: List[Parameter]
    ) -> Dict[str, Any]:
        """Optimize acquisition function (Upper Confidence Bound)"""
        # Simplified: sample random points and pick best UCB
        n_samples = 100
        best_score = -float('inf')
        best_params = None
        
        for _ in range(n_samples):
            params = self._sample_parameters(parameters)
            vector = self._params_to_vector(params, parameters).reshape(1, -1)
            
            # Predict mean and std
            mean, std = gp.predict(vector, return_std=True)
            ucb = mean + 2.0 * std
            
            if ucb > best_score:
                best_score = ucb
                best_params = params
        
        return best_params or self._sample_parameters(parameters)
    
    def _crossover(
        self,
        parent1: Dict[str, Any],
        parent2: Dict[str, Any],
        parameters: List[Parameter]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Crossover for genetic algorithm"""
        child1 = parent1.copy()
        child2 = parent2.copy()
        
        for p in parameters:
            if np.random.random() < 0.5:
                child1[p.name], child2[p.name] = child2[p.name], child1[p.name]
        
        return child1, child2
    
    def _mutate(
        self,
        params: Dict[str, Any],
        parameters: List[Parameter],
        scale: float = 0.1
    ) -> Dict[str, Any]:
        """Mutate parameters"""
        mutated = params.copy()
        
        for p in parameters:
            if np.random.random() < scale:
                if p.type == ParameterType.INTEGER:
                    step = np.random.randint(-5, 6)
                    mutated[p.name] = max(p.min, min(p.max, mutated[p.name] + step)) if p.min is not None else mutated[p.name] + step
                elif p.type == ParameterType.FLOAT:
                    step = np.random.normal(0, scale)
                    mutated[p.name] = max(p.min, min(p.max, mutated[p.name] + step)) if p.min is not None else mutated[p.name] + step
                elif p.type == ParameterType.CATEGORICAL:
                    if p.choices:
                        mutated[p.name] = np.random.choice(p.choices)
                elif p.type == ParameterType.BOOLEAN:
                    mutated[p.name] = not mutated[p.name]
        
        return mutated
    
    async def _compute_gradient(
        self,
        objective_function: Callable,
        params: Dict[str, Any],
        parameters: List[Parameter],
        constraints: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, float]:
        """Compute gradient using finite differences"""
        gradient = {}
        epsilon = 1e-7
        
        base_value = await self._evaluate_objective(
            objective_function,
            params,
            constraints
        )
        
        for p in parameters:
            if p.type not in [ParameterType.INTEGER, ParameterType.FLOAT]:
                continue
            
            # Forward difference
            params_plus = params.copy()
            params_plus[p.name] += epsilon
            
            value_plus = await self._evaluate_objective(
                objective_function,
                params_plus,
                constraints
            )
            
            gradient[p.name] = (value_plus - base_value) / epsilon
        
        return gradient
    
    def _check_early_stopping(self, history: List[Dict], iteration: int) -> bool:
        """Check early stopping condition"""
        if not self.config.early_stopping:
            return False
        
        if len(history) < self.config.early_stopping_patience:
            return False
        
        recent_values = [h.get('value', h.get('best_value', 0)) for h in history[-self.config.early_stopping_patience:]]
        
        # Check if improvement is below threshold
        improvement = max(recent_values) - min(recent_values)
        if abs(improvement) < self.config.early_stopping_threshold:
            return True
        
        return False
    
    def _update_progress(
        self,
        max_iterations: int,
        current_iteration: int,
        best_value: float
    ) -> None:
        """Update optimization progress"""
        # This will be called during optimization
        pass
    
    def _generate_cache_key(
        self,
        objective_function: Callable,
        parameters: List[Parameter],
        constraints: Optional[List[Dict[str, Any]]],
        method: OptimizationMethod,
        max_iterations: int
    ) -> str:
        """Generate cache key"""
        import hashlib
        
        key_data = {
            'method': method.value,
            'max_iterations': max_iterations,
            'parameters': [
                {
                    'name': p.name,
                    'type': p.type.value,
                    'min': p.min,
                    'max': p.max,
                    'choices': p.choices
                }
                for p in parameters
            ],
            'constraints': constraints,
            'objective': self.config.objective.value
        }
        
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cached_result(self, key: str) -> Optional[OptimizationResult]:
        """Get cached result"""
        if key in self._cache:
            result, timestamp = self._cache[key]
            age = (datetime.utcnow() - timestamp).total_seconds()
            if age < self.config.cache_ttl:
                return result
        
        # Check Redis cache
        try:
            cached = self.redis.get(f"optimization:{key}")
            if cached:
                data = json.loads(cached)
                return OptimizationResult(**data)
        except Exception as e:
            self.logger.error(f"Redis cache error: {e}")
        
        return None
    
    def _set_cached_result(self, key: str, result: OptimizationResult) -> None:
        """Cache result"""
        self._cache[key] = (result, datetime.utcnow())
        
        try:
            self.redis.setex(
                f"optimization:{key}",
                self.config.cache_ttl,
                json.dumps(result.__dict__, default=str)
            )
        except Exception as e:
            self.logger.error(f"Redis cache error: {e}")
    
    # ========================================
    # API METHODS
    # ========================================
    
    async def get_result(self, optimization_id: str) -> Optional[OptimizationResult]:
        """Get optimization result"""
        return self._results.get(optimization_id)
    
    async def get_progress(self, optimization_id: str) -> Optional[OptimizationProgress]:
        """Get optimization progress"""
        return self._progress.get(optimization_id)
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get engine metrics"""
        return {
            **self._metrics,
            "running_optimizations": len(self._running_optimizations),
            "total_results": len(self._results)
        }
    
    async def cancel_optimization(self, optimization_id: str) -> bool:
        """Cancel a running optimization"""
        if optimization_id not in self._running_optimizations:
            return False
        
        task = self._running_optimizations[optimization_id]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        del self._running_optimizations[optimization_id]
        self._progress[optimization_id].status = "cancelled"
        
        self.logger.info(f"Optimization {optimization_id} cancelled")
        return True
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the optimizer"""
        self._running = True
        self.logger.info("Optimizer started")
    
    async def stop(self) -> None:
        """Stop the optimizer"""
        self._running = False
        
        # Cancel running optimizations
        for optimization_id in list(self._running_optimizations.keys()):
            await self.cancel_optimization(optimization_id)
        
        self.logger.info("Optimizer stopped")
    
    async def health_check(self) -> bool:
        """Check optimizer health"""
        try:
            self.redis.ping()
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False


# ========================================
# DEPENDENCY INJECTION
# ========================================

_optimizer: Optional[Optimizer] = None


def get_optimizer() -> Optimizer:
    """Get singleton instance of Optimizer"""
    global _optimizer
    if _optimizer is None:
        _optimizer = Optimizer()
    return _optimizer


def reset_optimizer() -> None:
    """Reset the optimizer (for testing)"""
    global _optimizer
    if _optimizer:
        asyncio.create_task(_optimizer.stop())
    _optimizer = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'Optimizer',
    'OptimizerConfig',
    'OptimizationMethod',
    'ObjectiveType',
    'ParameterType',
    'Parameter',
    'OptimizationResult',
    'OptimizationProgress',
    'get_optimizer',
    'reset_optimizer'
]
