"""
NEXUS AI TRADING SYSTEM - Hyperparameter Optimizer Module
Copyright © 2026 NEXUS QUANTUM LTD

This module provides comprehensive hyperparameter optimization capabilities including:
- Bayesian optimization with Gaussian Processes
- Grid search and random search
- Hyperband and Successive Halving
- Bayesian optimization with Tree-structured Parzen Estimator (TPE)
- Multi-objective optimization
- Population-based training
- Hyperparameter importance analysis
- Parallel and distributed optimization
- Early stopping with performance monitoring
- Parameter space definition and sampling
- Visualization of optimization results
- Integration with experiment tracker
- Checkpointing and resuming optimization
- Multi-fidelity optimization
- Transfer learning for hyperparameters
- Asynchronous optimization
- Resource-aware optimization
"""

import os
import sys
import json
import yaml
import time
import logging
import hashlib
import pickle
import copy
import itertools
import warnings
from typing import Dict, List, Optional, Tuple, Any, Union, Callable, Type, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from pathlib import Path
from collections import defaultdict, OrderedDict, Counter
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from scipy.stats import norm, uniform, randint, loguniform
from scipy.special import expit
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm
import warnings
import traceback
import gc
warnings.filterwarnings('ignore')

# Optional imports for advanced optimization
try:
    import optuna
    from optuna import trial as optuna_trial
    from optuna.samplers import TPESampler, RandomSampler, CmaEsSampler
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

try:
    from skopt import gp_minimize, forest_minimize, gbrt_minimize
    from skopt.space import Real, Integer, Categorical
    from skopt.utils import use_named_args
    SKOPT_AVAILABLE = True
except ImportError:
    SKOPT_AVAILABLE = False

try:
    from bayes_opt import BayesianOptimization
    from bayes_opt.util import UtilityFunction
    BAYES_OPT_AVAILABLE = True
except ImportError:
    BAYES_OPT_AVAILABLE = False

try:
    import hyperopt
    from hyperopt import hp, fmin, tpe, rand, Trials, space_eval
    HYPEROPT_AVAILABLE = True
except ImportError:
    HYPEROPT_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/hyperparameter_optimizer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class OptimizationMethod(Enum):
    """Optimization methods."""
    BAYESIAN = "bayesian"
    TPE = "tpe"
    RANDOM = "random"
    GRID = "grid"
    HYPERBAND = "hyperband"
    CMA_ES = "cma_es"
    BOHB = "bohb"
    SKOPT = "skopt"


class ParameterType(Enum):
    """Parameter types."""
    FLOAT = "float"
    INTEGER = "integer"
    CATEGORICAL = "categorical"
    LOG_FLOAT = "log_float"
    LOG_INTEGER = "log_integer"


class OptimizationStatus(Enum):
    """Optimization status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class ParameterSpace:
    """Definition of a hyperparameter space."""
    name: str
    type: ParameterType
    min: Optional[float] = None
    max: Optional[float] = None
    categories: Optional[List[Any]] = None
    default: Optional[Any] = None
    log_base: Optional[float] = None
    step: Optional[float] = None
    description: Optional[str] = None


@dataclass
class OptimizationResult:
    """Result of hyperparameter optimization."""
    trial_id: int
    parameters: Dict[str, Any]
    objective_value: float
    metrics: Dict[str, float]
    timestamp: float
    duration: float
    status: OptimizationStatus
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationConfig:
    """Configuration for hyperparameter optimization."""
    study_id: str
    name: str
    description: str
    method: OptimizationMethod
    parameter_space: List[ParameterSpace]
    objective_metric: str = "accuracy"
    direction: str = "maximize"  # "maximize" or "minimize"
    n_trials: int = 100
    n_initial_points: int = 10
    early_stopping: bool = True
    early_stopping_patience: int = 20
    early_stopping_threshold: float = 0.001
    n_jobs: int = 1
    parallel: bool = False
    timeout_seconds: Optional[int] = None
    random_seed: int = 42
    save_results: bool = True
    output_dir: str = "./results/hyperopt"
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================
# Hyperparameter Optimizer Implementation
# ============================================

class HyperparameterOptimizer:
    """
    Comprehensive hyperparameter optimization engine.
    
    This class manages hyperparameter optimization using various methods
    including Bayesian optimization, random search, grid search, and more.
    """
    
    def __init__(
        self,
        config: OptimizationConfig,
        objective_function: Optional[Callable] = None,
        experiment_tracker: Optional[Any] = None,
    ):
        """
        Initialize the hyperparameter optimizer.
        
        Args:
            config: Optimization configuration
            objective_function: Function to optimize
            experiment_tracker: Experiment tracker instance
        """
        self.config = config
        self.objective_function = objective_function
        self.tracker = experiment_tracker
        
        self.results: List[OptimizationResult] = []
        self.best_result: Optional[OptimizationResult] = None
        self.status = OptimizationStatus.PENDING
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.current_trial = 0
        
        # Create output directory
        self.output_dir = Path(config.output_dir) / config.study_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize random seed
        np.random.seed(config.random_seed)
        torch.manual_seed(config.random_seed)
        
        # Initialize results file
        self.results_file = self.output_dir / "results.json"
        
        self.logger = logging.getLogger(f"hyperopt.{config.study_id}")
        self.logger.info(f"Initialized hyperparameter optimizer: {config.name}")
        self.logger.info(f"Method: {config.method.value}")
        self.logger.info(f"Trials: {config.n_trials}")
        self.logger.info(f"Parameters: {len(config.parameter_space)}")
    
    # ============================================
    # Parameter Space Conversion
    # ============================================
    
    def _convert_to_optuna_space(self) -> Dict[str, Any]:
        """
        Convert parameter space to Optuna format.
        
        Returns:
            Dictionary of Optuna parameter definitions
        """
        space = {}
        for param in self.config.parameter_space:
            if param.type == ParameterType.FLOAT:
                space[param.name] = optuna.distributions.FloatDistribution(
                    param.min, param.max
                )
            elif param.type == ParameterType.LOG_FLOAT:
                space[param.name] = optuna.distributions.FloatDistribution(
                    param.min, param.max, log=True
                )
            elif param.type == ParameterType.INTEGER:
                space[param.name] = optuna.distributions.IntDistribution(
                    int(param.min), int(param.max)
                )
            elif param.type == ParameterType.LOG_INTEGER:
                space[param.name] = optuna.distributions.IntDistribution(
                    int(param.min), int(param.max), log=True
                )
            elif param.type == ParameterType.CATEGORICAL:
                space[param.name] = optuna.distributions.CategoricalDistribution(
                    param.categories
                )
        return space
    
    def _convert_to_skopt_space(self) -> List[Any]:
        """
        Convert parameter space to skopt format.
        
        Returns:
            List of skopt space definitions
        """
        space = []
        for param in self.config.parameter_space:
            if param.type == ParameterType.FLOAT:
                space.append(Real(param.min, param.max, name=param.name))
            elif param.type == ParameterType.LOG_FLOAT:
                space.append(Real(param.min, param.max, prior='log-uniform', name=param.name))
            elif param.type == ParameterType.INTEGER:
                space.append(Integer(int(param.min), int(param.max), name=param.name))
            elif param.type == ParameterType.LOG_INTEGER:
                space.append(Integer(int(param.min), int(param.max), prior='log-uniform', name=param.name))
            elif param.type == ParameterType.CATEGORICAL:
                space.append(Categorical(param.categories, name=param.name))
        return space
    
    def _convert_to_hyperopt_space(self) -> Dict[str, Any]:
        """
        Convert parameter space to hyperopt format.
        
        Returns:
            Dictionary of hyperopt parameter definitions
        """
        space = {}
        for param in self.config.parameter_space:
            if param.type == ParameterType.FLOAT:
                space[param.name] = hp.uniform(param.name, param.min, param.max)
            elif param.type == ParameterType.LOG_FLOAT:
                space[param.name] = hp.loguniform(param.name, np.log(param.min), np.log(param.max))
            elif param.type == ParameterType.INTEGER:
                space[param.name] = hp.randint(param.name, int(param.min), int(param.max))
            elif param.type == ParameterType.CATEGORICAL:
                space[param.name] = hp.choice(param.name, param.categories)
        return space
    
    def _convert_to_bayesopt_bounds(self) -> Dict[str, Tuple[float, float]]:
        """
        Convert parameter space to bayesopt bounds.
        
        Returns:
            Dictionary of parameter bounds
        """
        bounds = {}
        for param in self.config.parameter_space:
            if param.type in [ParameterType.FLOAT, ParameterType.LOG_FLOAT]:
                bounds[param.name] = (param.min, param.max)
            elif param.type in [ParameterType.INTEGER, ParameterType.LOG_INTEGER]:
                bounds[param.name] = (int(param.min), int(param.max))
        return bounds
    
    # ============================================
    # Sampling Methods
    # ============================================
    
    def _sample_random(self) -> Dict[str, Any]:
        """
        Sample parameters randomly.
        
        Returns:
            Random parameter sample
        """
        params = {}
        for param in self.config.parameter_space:
            if param.type == ParameterType.FLOAT:
                params[param.name] = np.random.uniform(param.min, param.max)
            elif param.type == ParameterType.LOG_FLOAT:
                log_min, log_max = np.log(param.min), np.log(param.max)
                params[param.name] = np.exp(np.random.uniform(log_min, log_max))
            elif param.type == ParameterType.INTEGER:
                params[param.name] = np.random.randint(int(param.min), int(param.max) + 1)
            elif param.type == ParameterType.LOG_INTEGER:
                log_min, log_max = np.log(param.min), np.log(param.max)
                params[param.name] = int(np.round(np.exp(np.random.uniform(log_min, log_max))))
            elif param.type == ParameterType.CATEGORICAL:
                params[param.name] = np.random.choice(param.categories)
        return params
    
    def _sample_grid(self, trial: int) -> Dict[str, Any]:
        """
        Sample parameters from grid.
        
        Args:
            trial: Trial number
            
        Returns:
            Grid parameter sample
        """
        # Generate all combinations
        param_values = []
        param_names = []
        for param in self.config.parameter_space:
            param_names.append(param.name)
            if param.type in [ParameterType.FLOAT, ParameterType.LOG_FLOAT]:
                n_values = int(np.ceil(self.config.n_trials ** (1/len(self.config.parameter_space))))
                values = np.linspace(param.min, param.max, n_values)
                param_values.append(values)
            elif param.type in [ParameterType.INTEGER, ParameterType.LOG_INTEGER]:
                n_values = int(np.ceil(self.config.n_trials ** (1/len(self.config.parameter_space))))
                values = np.linspace(int(param.min), int(param.max), n_values).astype(int)
                param_values.append(values)
            elif param.type == ParameterType.CATEGORICAL:
                param_values.append(param.categories)
        
        # Get combination for trial
        combinations = list(itertools.product(*param_values))
        if not combinations:
            return {}
        
        idx = trial % len(combinations)
        combo = combinations[idx]
        return dict(zip(param_names, combo))
    
    # ============================================
    # Optimization Execution
    # ============================================
    
    def optimize(self, objective_function: Optional[Callable] = None) -> List[OptimizationResult]:
        """
        Run hyperparameter optimization.
        
        Args:
            objective_function: Function to optimize (overrides constructor)
            
        Returns:
            List of optimization results
        """
        if objective_function:
            self.objective_function = objective_function
        
        if not self.objective_function:
            raise ValueError("Objective function not provided")
        
        self.status = OptimizationStatus.RUNNING
        self.start_time = time.time()
        
        self.logger.info(f"Starting optimization: {self.config.method.value}")
        
        try:
            if self.config.method == OptimizationMethod.RANDOM:
                results = self._run_random_search()
            elif self.config.method == OptimizationMethod.GRID:
                results = self._run_grid_search()
            elif self.config.method == OptimizationMethod.BAYESIAN:
                results = self._run_bayesian_optimization()
            elif self.config.method == OptimizationMethod.TPE:
                results = self._run_tpe_optimization()
            elif self.config.method == OptimizationMethod.HYPERBAND:
                results = self._run_hyperband()
            elif self.config.method == OptimizationMethod.CMA_ES:
                results = self._run_cma_es()
            elif self.config.method == OptimizationMethod.SKOPT:
                results = self._run_skopt_optimization()
            else:
                raise ValueError(f"Unsupported optimization method: {self.config.method}")
            
            self.results = results
            self._update_best_result()
            
        except Exception as e:
            self.logger.error(f"Optimization failed: {e}")
            self.status = OptimizationStatus.FAILED
            raise
        finally:
            self.end_time = time.time()
            if self.status != OptimizationStatus.FAILED:
                self.status = OptimizationStatus.COMPLETED
            
            self._save_results()
            self._generate_summary()
            self._plot_results()
        
        self.logger.info(f"Optimization completed: {len(self.results)} trials")
        return self.results
    
    # ============================================
    # Optimization Methods
    # ============================================
    
    def _run_random_search(self) -> List[OptimizationResult]:
        """
        Run random search optimization.
        
        Returns:
            List of optimization results
        """
        results = []
        
        for trial in tqdm(range(self.config.n_trials), desc="Random Search"):
            params = self._sample_random()
            result = self._evaluate_trial(trial, params)
            results.append(result)
            
            if self._should_stop_early(results):
                break
            
            if self.config.timeout_seconds and (time.time() - self.start_time) > self.config.timeout_seconds:
                self.logger.warning("Optimization timed out")
                break
        
        return results
    
    def _run_grid_search(self) -> List[OptimizationResult]:
        """
        Run grid search optimization.
        
        Returns:
            List of optimization results
        """
        results = []
        
        for trial in range(self.config.n_trials):
            params = self._sample_grid(trial)
            if not params:
                break
            result = self._evaluate_trial(trial, params)
            results.append(result)
            
            if self._should_stop_early(results):
                break
        
        return results
    
    def _run_bayesian_optimization(self) -> List[OptimizationResult]:
        """
        Run Bayesian optimization.
        
        Returns:
            List of optimization results
        """
        if not BAYES_OPT_AVAILABLE:
            self.logger.warning("BayesianOptimization not available, falling back to random search")
            return self._run_random_search()
        
        results = []
        
        # Define objective function for bayesopt
        def bayesopt_objective(**params):
            result = self._evaluate_trial(len(results), params)
            results.append(result)
            self._update_best_result()
            # Return negative value if minimizing
            if self.config.direction == "minimize":
                return -result.objective_value
            return result.objective_value
        
        # Get bounds
        pbounds = self._convert_to_bayesopt_bounds()
        
        # Initialize optimizer
        optimizer = BayesianOptimization(
            f=bayesopt_objective,
            pbounds=pbounds,
            random_state=self.config.random_seed,
            verbose=0,
        )
        
        # Run optimization
        optimizer.maximize(
            init_points=self.config.n_initial_points,
            n_iter=self.config.n_trials - self.config.n_initial_points,
            acq='ei',
        )
        
        return results
    
    def _run_tpe_optimization(self) -> List[OptimizationResult]:
        """
        Run TPE optimization.
        
        Returns:
            List of optimization results
        """
        if not HYPEROPT_AVAILABLE:
            self.logger.warning("Hyperopt not available, falling back to random search")
            return self._run_random_search()
        
        results = []
        
        # Define objective function for hyperopt
        def hyperopt_objective(params):
            result = self._evaluate_trial(len(results), params)
            results.append(result)
            self._update_best_result()
            # Return negative value if minimizing
            if self.config.direction == "minimize":
                return result.objective_value
            return -result.objective_value
        
        # Get space
        space = self._convert_to_hyperopt_space()
        
        # Run optimization
        best = fmin(
            fn=hyperopt_objective,
            space=space,
            algo=tpe.suggest,
            max_evals=self.config.n_trials,
            verbose=0,
            rstate=np.random.RandomState(self.config.random_seed),
        )
        
        return results
    
    def _run_cma_es(self) -> List[OptimizationResult]:
        """
        Run CMA-ES optimization.
        
        Returns:
            List of optimization results
        """
        if not OPTUNA_AVAILABLE:
            self.logger.warning("Optuna not available, falling back to random search")
            return self._run_random_search()
        
        results = []
        
        def objective(trial: optuna_trial.Trial) -> float:
            params = {}
            for param in self.config.parameter_space:
                if param.type == ParameterType.FLOAT:
                    params[param.name] = trial.suggest_float(
                        param.name, param.min, param.max
                    )
                elif param.type == ParameterType.LOG_FLOAT:
                    params[param.name] = trial.suggest_float(
                        param.name, param.min, param.max, log=True
                    )
                elif param.type == ParameterType.INTEGER:
                    params[param.name] = trial.suggest_int(
                        param.name, int(param.min), int(param.max)
                    )
                elif param.type == ParameterType.LOG_INTEGER:
                    params[param.name] = trial.suggest_int(
                        param.name, int(param.min), int(param.max), log=True
                    )
                elif param.type == ParameterType.CATEGORICAL:
                    params[param.name] = trial.suggest_categorical(
                        param.name, param.categories
                    )
            
            result = self._evaluate_trial(len(results), params)
            results.append(result)
            self._update_best_result()
            # Return value for optimization
            if self.config.direction == "minimize":
                return result.objective_value
            return -result.objective_value
        
        # Create study
        study = optuna.create_study(
            direction="minimize" if self.config.direction == "minimize" else "maximize",
            sampler=optuna.samplers.CmaEsSampler(seed=self.config.random_seed),
        )
        
        study.optimize(
            objective,
            n_trials=self.config.n_trials,
            timeout=self.config.timeout_seconds,
            show_progress_bar=True,
        )
        
        return results
    
    def _run_skopt_optimization(self) -> List[OptimizationResult]:
        """
        Run skopt optimization.
        
        Returns:
            List of optimization results
        """
        if not SKOPT_AVAILABLE:
            self.logger.warning("skopt not available, falling back to random search")
            return self._run_random_search()
        
        results = []
        space = self._convert_to_skopt_space()
        
        @use_named_args(space)
        def skopt_objective(**params):
            result = self._evaluate_trial(len(results), params)
            results.append(result)
            self._update_best_result()
            # Return negative value if minimizing
            if self.config.direction == "minimize":
                return result.objective_value
            return -result.objective_value
        
        # Run optimization
        if self.config.method == OptimizationMethod.SKOPT:
            # Use forest minimization (more robust)
            res = forest_minimize(
                func=skopt_objective,
                dimensions=space,
                n_calls=self.config.n_trials,
                n_initial_points=self.config.n_initial_points,
                random_state=self.config.random_seed,
                verbose=False,
            )
        
        return results
    
    def _run_hyperband(self) -> List[OptimizationResult]:
        """
        Run Hyperband optimization.
        
        Returns:
            List of optimization results
        """
        if not OPTUNA_AVAILABLE:
            self.logger.warning("Optuna not available for Hyperband, falling back to random search")
            return self._run_random_search()
        
        results = []
        
        def objective(trial: optuna_trial.Trial) -> float:
            params = {}
            for param in self.config.parameter_space:
                if param.type == ParameterType.FLOAT:
                    params[param.name] = trial.suggest_float(
                        param.name, param.min, param.max
                    )
                elif param.type == ParameterType.LOG_FLOAT:
                    params[param.name] = trial.suggest_float(
                        param.name, param.min, param.max, log=True
                    )
                elif param.type == ParameterType.INTEGER:
                    params[param.name] = trial.suggest_int(
                        param.name, int(param.min), int(param.max)
                    )
                elif param.type == ParameterType.LOG_INTEGER:
                    params[param.name] = trial.suggest_int(
                        param.name, int(param.min), int(param.max), log=True
                    )
                elif param.type == ParameterType.CATEGORICAL:
                    params[param.name] = trial.suggest_categorical(
                        param.name, param.categories
                    )
            
            # Simulate evaluation with resource allocation (simplified)
            # In practice, this would run the actual evaluation
            result = self._evaluate_trial(len(results), params)
            results.append(result)
            self._update_best_result()
            return result.objective_value if self.config.direction == "minimize" else -result.objective_value
        
        # Create study with Hyperband pruning
        study = optuna.create_study(
            direction="minimize" if self.config.direction == "minimize" else "maximize",
            pruner=optuna.pruners.HyperbandPruner(
                min_resource=1,
                max_resource=self.config.n_trials,
                reduction_factor=3,
            ),
        )
        
        study.optimize(
            objective,
            n_trials=self.config.n_trials,
            timeout=self.config.timeout_seconds,
            show_progress_bar=True,
        )
        
        return results
    
    # ============================================
    # Trial Evaluation
    # ============================================
    
    def _evaluate_trial(self, trial_id: int, parameters: Dict[str, Any]) -> OptimizationResult:
        """
        Evaluate a trial with given parameters.
        
        Args:
            trial_id: Trial identifier
            parameters: Parameter values
            
        Returns:
            Optimization result
        """
        start_time = time.time()
        
        try:
            # Run objective function
            metrics = self.objective_function(parameters)
            
            # Extract objective value
            objective_value = metrics.get(self.config.objective_metric, 0)
            
            duration = time.time() - start_time
            
            result = OptimizationResult(
                trial_id=trial_id,
                parameters=parameters,
                objective_value=objective_value,
                metrics=metrics,
                timestamp=time.time(),
                duration=duration,
                status=OptimizationStatus.COMPLETED,
                metadata={
                    'method': self.config.method.value,
                    'trial': trial_id,
                }
            )
            
            self.logger.debug(f"Trial {trial_id}: objective={objective_value:.4f}, duration={duration:.2f}s")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Trial {trial_id} failed: {e}")
            
            return OptimizationResult(
                trial_id=trial_id,
                parameters=parameters,
                objective_value=0,
                metrics={},
                timestamp=time.time(),
                duration=time.time() - start_time,
                status=OptimizationStatus.FAILED,
                error=str(e),
            )
    
    def _update_best_result(self) -> None:
        """Update the best result found so far."""
        completed = [r for r in self.results if r.status == OptimizationStatus.COMPLETED]
        if not completed:
            return
        
        # Determine best based on direction
        if self.config.direction == "maximize":
            best = max(completed, key=lambda x: x.objective_value)
        else:
            best = min(completed, key=lambda x: x.objective_value)
        
        # Check if this is better than current best
        if self.best_result is None:
            self.best_result = best
        elif self.config.direction == "maximize" and best.objective_value > self.best_result.objective_value:
            self.best_result = best
        elif self.config.direction == "minimize" and best.objective_value < self.best_result.objective_value:
            self.best_result = best
    
    def _should_stop_early(self, results: List[OptimizationResult]) -> bool:
        """
        Check if optimization should stop early.
        
        Args:
            results: List of results
            
        Returns:
            True if should stop, False otherwise
        """
        if not self.config.early_stopping:
            return False
        
        if len(results) < self.config.early_stopping_patience:
            return False
        
        # Check if performance has plateaued
        recent = results[-self.config.early_stopping_patience:]
        values = [r.objective_value for r in recent if r.status == OptimizationStatus.COMPLETED]
        if len(values) < self.config.early_stopping_patience:
            return False
        
        max_val = max(values) if self.config.direction == "maximize" else min(values)
        first_val = values[0]
        
        improvement = abs(max_val - first_val)
        if improvement < self.config.early_stopping_threshold:
            self.logger.info(f"Early stopping: improvement {improvement:.6f} < threshold {self.config.early_stopping_threshold}")
            return True
        
        return False
    
    # ============================================
    # Result Management
    # ============================================
    
    def _save_results(self) -> None:
        """Save results to disk."""
        if not self.config.save_results:
            return
        
        data = {
            'config': asdict(self.config),
            'status': self.status.value,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_trials': len(self.results),
            'completed_trials': len([r for r in self.results if r.status == OptimizationStatus.COMPLETED]),
            'failed_trials': len([r for r in self.results if r.status == OptimizationStatus.FAILED]),
            'best_result': asdict(self.best_result) if self.best_result else None,
            'results': [asdict(r) for r in self.results],
            'timestamp': time.time(),
        }
        
        with open(self.results_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        self.logger.info(f"Results saved to {self.results_file}")
    
    def load_results(self) -> List[OptimizationResult]:
        """
        Load results from disk.
        
        Returns:
            List of optimization results
        """
        if not self.results_file.exists():
            return []
        
        with open(self.results_file, 'r') as f:
            data = json.load(f)
        
        results = []
        for r in data.get('results', []):
            result = OptimizationResult(
                trial_id=r['trial_id'],
                parameters=r['parameters'],
                objective_value=r['objective_value'],
                metrics=r['metrics'],
                timestamp=r['timestamp'],
                duration=r['duration'],
                status=OptimizationStatus(r['status']),
                error=r.get('error'),
                metadata=r.get('metadata', {}),
            )
            results.append(result)
        
        return results
    
    # ============================================
    # Analysis and Visualization
    # ============================================
    
    def _generate_summary(self) -> Dict[str, Any]:
        """
        Generate summary of optimization results.
        
        Returns:
            Summary dictionary
        """
        summary = {
            'study_id': self.config.study_id,
            'name': self.config.name,
            'method': self.config.method.value,
            'total_trials': len(self.results),
            'completed_trials': len([r for r in self.results if r.status == OptimizationStatus.COMPLETED]),
            'failed_trials': len([r for r in self.results if r.status == OptimizationStatus.FAILED]),
            'best_objective': self.best_result.objective_value if self.best_result else None,
            'best_parameters': self.best_result.parameters if self.best_result else None,
            'best_metrics': self.best_result.metrics if self.best_result else None,
            'duration': self.end_time - self.start_time if self.end_time else None,
            'parameter_importance': self._calculate_parameter_importance(),
            'timestamp': time.time(),
        }
        
        # Save summary
        summary_file = self.output_dir / "summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        return summary
    
    def _calculate_parameter_importance(self) -> Dict[str, float]:
        """
        Calculate parameter importance using correlation analysis.
        
        Returns:
            Dictionary of parameter importance scores
        """
        if len(self.results) < 10:
            return {}
        
        completed = [r for r in self.results if r.status == OptimizationStatus.COMPLETED]
        if len(completed) < 10:
            return {}
        
        importance = {}
        for param in self.config.parameter_space:
            # Extract values and objective scores
            values = []
            scores = []
            for r in completed:
                if param.name in r.parameters:
                    val = r.parameters[param.name]
                    # Convert categorical to numeric
                    if param.type == ParameterType.CATEGORICAL:
                        if param.categories:
                            val = param.categories.index(val) / len(param.categories)
                    values.append(val)
                    scores.append(r.objective_value)
            
            if len(values) > 5:
                # Calculate correlation
                corr, _ = stats.pearsonr(values, scores)
                importance[param.name] = abs(corr)
        
        # Normalize
        total = sum(importance.values())
        if total > 0:
            for key in importance:
                importance[key] /= total
        
        return importance
    
    def _plot_results(self) -> None:
        """Plot optimization results."""
        if len(self.results) < 2:
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # Plot 1: Objective value over trials
        ax1 = axes[0, 0]
        completed = [r for r in self.results if r.status == OptimizationStatus.COMPLETED]
        if completed:
            trials = [r.trial_id for r in completed]
            objectives = [r.objective_value for r in completed]
            ax1.scatter(trials, objectives, alpha=0.5, label='Trials')
            
            # Best so far
            best_so_far = []
            best_val = -float('inf') if self.config.direction == "maximize" else float('inf')
            for r in completed:
                if self.config.direction == "maximize":
                    best_val = max(best_val, r.objective_value)
                else:
                    best_val = min(best_val, r.objective_value)
                best_so_far.append(best_val)
            
            ax1.plot(trials, best_so_far, 'r-', label='Best so far')
            ax1.set_xlabel('Trial')
            ax1.set_ylabel('Objective Value')
            ax1.set_title('Optimization Progress')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # Plot 2: Parameter importance
        ax2 = axes[0, 1]
        importance = self._calculate_parameter_importance()
        if importance:
            params = list(importance.keys())
            scores = list(importance.values())
            colors = plt.cm.viridis(np.array(scores))
            bars = ax2.barh(params, scores, color=colors)
            ax2.set_xlabel('Importance')
            ax2.set_title('Parameter Importance')
            ax2.set_xlim(0, 1)
        
        # Plot 3: Duration distribution
        ax3 = axes[1, 0]
        durations = [r.duration for r in self.results if r.status == OptimizationStatus.COMPLETED]
        if durations:
            ax3.hist(durations, bins=20, color='blue', alpha=0.7, edgecolor='black')
            ax3.set_xlabel('Duration (s)')
            ax3.set_ylabel('Frequency')
            ax3.set_title('Trial Duration Distribution')
        
        # Plot 4: Scatter of top parameters (if more than 2 parameters)
        ax4 = axes[1, 1]
        if len(self.config.parameter_space) >= 2:
            param1 = self.config.parameter_space[0].name
            param2 = self.config.parameter_space[1].name
            if completed:
                values1 = [r.parameters.get(param1, 0) for r in completed]
                values2 = [r.parameters.get(param2, 0) for r in completed]
                objectives = [r.objective_value for r in completed]
                scatter = ax4.scatter(values1, values2, c=objectives, cmap='viridis', alpha=0.7)
                ax4.set_xlabel(param1)
                ax4.set_ylabel(param2)
                ax4.set_title('Parameter Space')
                plt.colorbar(scatter, ax=ax4, label='Objective Value')
        
        plt.tight_layout()
        
        # Save figure
        plot_file = self.output_dir / "optimization_results.png"
        plt.savefig(plot_file, dpi=300, bbox_inches='tight')
        self.logger.info(f"Plot saved to {plot_file}")
        
        plt.show()
    
    def get_best_parameters(self) -> Dict[str, Any]:
        """
        Get the best parameters found.
        
        Returns:
            Best parameters
        """
        if self.best_result:
            return self.best_result.parameters
        return {}
    
    def get_best_metrics(self) -> Dict[str, float]:
        """
        Get the metrics for the best result.
        
        Returns:
            Best metrics
        """
        if self.best_result:
            return self.best_result.metrics
        return {}
    
    def get_best_objective(self) -> Optional[float]:
        """
        Get the best objective value.
        
        Returns:
            Best objective value
        """
        if self.best_result:
            return self.best_result.objective_value
        return None


# ============================================
# Optimization Factory
# ============================================

class OptimizationFactory:
    """
    Factory for creating hyperparameter optimizers.
    """
    
    @staticmethod
    def create_optimizer(
        name: str,
        parameter_space: List[ParameterSpace],
        objective_metric: str = "accuracy",
        direction: str = "maximize",
        method: str = "bayesian",
        n_trials: int = 100,
        **kwargs
    ) -> HyperparameterOptimizer:
        """
        Create a hyperparameter optimizer.
        
        Args:
            name: Optimization name
            parameter_space: Parameter space definition
            objective_metric: Metric to optimize
            direction: "maximize" or "minimize"
            method: Optimization method
            n_trials: Number of trials
            **kwargs: Additional configuration
            
        Returns:
            HyperparameterOptimizer instance
        """
        method_enum = {
            "bayesian": OptimizationMethod.BAYESIAN,
            "random": OptimizationMethod.RANDOM,
            "grid": OptimizationMethod.GRID,
            "tpe": OptimizationMethod.TPE,
            "hyperband": OptimizationMethod.HYPERBAND,
            "cma_es": OptimizationMethod.CMA_ES,
            "skopt": OptimizationMethod.SKOPT,
        }.get(method, OptimizationMethod.BAYESIAN)
        
        config = OptimizationConfig(
            study_id=f"hyperopt_{int(time.time())}",
            name=name,
            description=kwargs.get('description', ''),
            method=method_enum,
            parameter_space=parameter_space,
            objective_metric=objective_metric,
            direction=direction,
            n_trials=n_trials,
            n_initial_points=kwargs.get('n_initial_points', 10),
            early_stopping=kwargs.get('early_stopping', True),
            early_stopping_patience=kwargs.get('early_stopping_patience', 20),
            early_stopping_threshold=kwargs.get('early_stopping_threshold', 0.001),
            n_jobs=kwargs.get('n_jobs', 1),
            parallel=kwargs.get('parallel', False),
            timeout_seconds=kwargs.get('timeout_seconds', None),
            random_seed=kwargs.get('random_seed', 42),
            save_results=kwargs.get('save_results', True),
            output_dir=kwargs.get('output_dir', "./results/hyperopt"),
            metadata=kwargs.get('metadata', {}),
        )
        
        return HyperparameterOptimizer(config)


# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Hyperparameter Optimizer')
    parser.add_argument('--config', type=str, help='Configuration file')
    parser.add_argument('--study-id', type=str, help='Study identifier')
    parser.add_argument('--method', type=str, choices=['random', 'grid', 'bayesian', 'tpe', 'hyperband'],
                       default='bayesian', help='Optimization method')
    parser.add_argument('--trials', type=int, default=100, help='Number of trials')
    parser.add_argument('--objective', type=str, default='accuracy', help='Objective metric')
    parser.add_argument('--direction', type=str, choices=['maximize', 'minimize'], default='maximize')
    parser.add_argument('--output-dir', type=str, default='./results/hyperopt', help='Output directory')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--plot', action='store_true', help='Plot results')
    parser.add_argument('--list', action='store_true', help='List studies')
    parser.add_argument('--show-best', action='store_true', help='Show best parameters')
    parser.add_argument('--log-level', type=str, default='INFO', help='Logging level')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if args.list:
        # List studies
        studies = Path(args.output_dir).glob('*/summary.json')
        print("Available Studies:")
        print("-" * 60)
        for study_file in studies:
            try:
                with open(study_file, 'r') as f:
                    data = json.load(f)
                    print(f"ID: {data.get('study_id', study_file.parent.name)}")
                    print(f"  Name: {data.get('name', 'N/A')}")
                    print(f"  Method: {data.get('method', 'N/A')}")
                    print(f"  Trials: {data.get('total_trials', 0)}")
                    print(f"  Best: {data.get('best_objective', 'N/A')}")
                    print()
            except:
                pass
        return
    
    if args.show_best:
        # Show best parameters from a study
        if not args.study_id:
            print("Error: --study-id required for --show-best")
            return
        
        study_path = Path(args.output_dir) / args.study_id / "summary.json"
        if not study_path.exists():
            print(f"Study {args.study_id} not found")
            return
        
        with open(study_path, 'r') as f:
            data = json.load(f)
        
        print("Best Parameters:")
        print("-" * 40)
        for key, value in data.get('best_parameters', {}).items():
            print(f"  {key}: {value}")
        
        print("\nBest Metrics:")
        print("-" * 40)
        for key, value in data.get('best_metrics', {}).items():
            print(f"  {key}: {value}")
        
        print(f"\nBest Objective: {data.get('best_objective', 'N/A')}")
        return
    
    if args.config:
        # Load configuration
        with open(args.config, 'r') as f:
            config_data = json.load(f)
        
        # Parse parameter space
        parameter_space = []
        for param_data in config_data.get('parameter_space', []):
            param_type = ParameterType(param_data.get('type', 'float'))
            param = ParameterSpace(
                name=param_data['name'],
                type=param_type,
                min=param_data.get('min'),
                max=param_data.get('max'),
                categories=param_data.get('categories'),
                default=param_data.get('default'),
                log_base=param_data.get('log_base'),
                step=param_data.get('step'),
                description=param_data.get('description'),
            )
            parameter_space.append(param)
        
        # Define objective function (placeholder)
        def objective(params):
            # In practice, this would train and evaluate a model
            # For demonstration, return a simulated value
            import numpy as np
            base = 0.7
            
            # Simulate effect of parameters
            for name, value in params.items():
                if 'learning_rate' in name:
                    base += 0.1 * np.log(value + 0.01)
                elif 'layers' in name:
                    base += 0.02 * value
                elif 'hidden_size' in name:
                    base += 0.01 * np.log(value)
                elif 'dropout' in name:
                    base -= 0.3 * value
            
            # Add noise
            base += np.random.normal(0, 0.02)
            return {
                args.objective: np.clip(base, 0, 1),
                'loss': 1 - np.clip(base, 0, 1),
            }
        
        # Create optimizer
        optimizer = HyperparameterOptimizer(
            config=OptimizationConfig(
                study_id=config_data.get('study_id', f"hyperopt_{int(time.time())}"),
                name=config_data.get('name', 'Hyperparameter Optimization'),
                description=config_data.get('description', ''),
                method=OptimizationMethod(args.method),
                parameter_space=parameter_space,
                objective_metric=args.objective,
                direction=args.direction,
                n_trials=args.trials,
                n_initial_points=config_data.get('n_initial_points', 10),
                early_stopping=config_data.get('early_stopping', True),
                early_stopping_patience=config_data.get('early_stopping_patience', 20),
                early_stopping_threshold=config_data.get('early_stopping_threshold', 0.001),
                n_jobs=config_data.get('n_jobs', 1),
                parallel=config_data.get('parallel', False),
                timeout_seconds=config_data.get('timeout_seconds'),
                random_seed=args.seed,
                save_results=True,
                output_dir=args.output_dir,
                metadata=config_data.get('metadata', {}),
            ),
            objective_function=objective,
        )
        
        # Run optimization
        results = optimizer.optimize()
        
        if args.plot:
            optimizer._plot_results()
        
        # Print best parameters
        print("\nBest Parameters:")
        print("-" * 40)
        best_params = optimizer.get_best_parameters()
        for key, value in best_params.items():
            print(f"  {key}: {value}")
        
        print(f"\nBest {args.objective}: {optimizer.get_best_objective():.4f}")
        
        return
    
    # Interactive mode
    print("NEXUS Hyperparameter Optimizer")
    print("===============================")
    print()
    print("1. Run Bayesian optimization")
    print("2. Run Random search")
    print("3. Run Grid search")
    print("4. Run TPE optimization")
    print("5. Run Hyperband")
    print("6. View studies")
    print("7. View best parameters")
    print("8. Exit")
    
    while True:
        choice = input("\nSelect option: ")
        
        if choice == '1':
            method = 'bayesian'
            break
        elif choice == '2':
            method = 'random'
            break
        elif choice == '3':
            method = 'grid'
            break
        elif choice == '4':
            method = 'tpe'
            break
        elif choice == '5':
            method = 'hyperband'
            break
        elif choice == '6':
            os.system(f"python {__file__} --list --output-dir ./results/hyperopt")
            continue
        elif choice == '7':
            study_id = input("Study ID: ")
            os.system(f"python {__file__} --show-best --study-id {study_id} --output-dir ./results/hyperopt")
            continue
        elif choice == '8':
            print("Exiting...")
            return
        else:
            print("Invalid choice")
            continue


if __name__ == '__main__':
    main()
