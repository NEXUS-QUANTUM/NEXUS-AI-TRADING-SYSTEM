"""
Swing Bot Optimization Model
==============================

This module provides optimization models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from scipy.optimize import minimize, differential_evolution
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class OptimizationResult:
    """Optimization result data structure."""
    timestamp: datetime
    parameters: Dict[str, float]
    objective_value: float
    constraints_satisfied: bool
    iterations: int
    convergence: float
    method: str
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class OptimizationSignal:
    """Optimization trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    parameters: Dict[str, float]
    metrics: Dict[str, float] = field(default_factory=dict)


class OptimizationModel:
    """
    Optimization model for parameter tuning and strategy optimization.
    
    Implements various optimization algorithms for trading parameters.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the optimization model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.parameter_bounds: Dict[str, Tuple[float, float]] = {}
        self.objective_function: Optional[Callable] = None
        self.constraints: List[Dict] = []
        self.results: List[OptimizationResult] = []
        self.lookback_period = self.config.get('lookback_period', 100)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.max_iterations = self.config.get('max_iterations', 100)
        self.method = self.config.get('method', 'SLSQP')
        
        # Register default parameters
        self._register_parameters()
        
    def _register_parameters(self) -> None:
        """Register default optimization parameters."""
        self.parameter_bounds = {
            'fast_ma': (5, 30),
            'slow_ma': (20, 100),
            'rsi_period': (7, 21),
            'bb_period': (10, 30),
            'bb_std': (1.5, 3.0),
            'stop_loss': (0.005, 0.05),
            'take_profit': (0.01, 0.10),
            'position_size': (0.01, 0.10),
            'adx_threshold': (20, 40),
            'momentum_period': (5, 30)
        }
        
        self.default_parameters = {
            'fast_ma': 10,
            'slow_ma': 30,
            'rsi_period': 14,
            'bb_period': 20,
            'bb_std': 2.0,
            'stop_loss': 0.02,
            'take_profit': 0.04,
            'position_size': 0.02,
            'adx_threshold': 25,
            'momentum_period': 14
        }
    
    def set_objective_function(self, func: Callable) -> None:
        """
        Set the objective function for optimization.
        
        Args:
            func: Objective function
        """
        self.objective_function = func
    
    def add_constraint(self, constraint: Dict) -> None:
        """
        Add a constraint to the optimization.
        
        Args:
            constraint: Constraint dictionary
        """
        self.constraints.append(constraint)
    
    def optimize_parameters(self, **kwargs) -> OptimizationResult:
        """
        Optimize parameters using the specified method.
        
        Args:
            **kwargs: Parameters for optimization
            
        Returns:
            OptimizationResult object
        """
        if self.objective_function is None:
            raise ValueError("Objective function not set")
        
        # Get bounds for parameters
        bounds = []
        param_names = []
        
        for name, value in kwargs.items():
            if name in self.parameter_bounds:
                bounds.append(self.parameter_bounds[name])
                param_names.append(name)
            else:
                bounds.append((value * 0.5, value * 1.5))
                param_names.append(name)
        
        # Objective function wrapper
        def objective(x):
            params = dict(zip(param_names, x))
            return -self.objective_function(params)  # Minimize negative for maximization
        
        # Run optimization
        if self.method == 'SLSQP':
            result = minimize(
                objective,
                np.array([kwargs[name] for name in param_names]),
                method='SLSQP',
                bounds=bounds,
                constraints=self.constraints,
                options={'maxiter': self.max_iterations}
            )
        elif self.method == 'differential_evolution':
            result = differential_evolution(
                objective,
                bounds,
                maxiter=self.max_iterations,
                constraints=self.constraints
            )
        else:
            raise ValueError(f"Unsupported method: {self.method}")
        
        # Extract results
        optimized_params = dict(zip(param_names, result.x))
        objective_value = -result.fun
        
        optimization_result = OptimizationResult(
            timestamp=datetime.now(),
            parameters=optimized_params,
            objective_value=objective_value,
            constraints_satisfied=result.success,
            iterations=result.nit if hasattr(result, 'nit') else 0,
            convergence=result.fun,
            method=self.method,
            metrics={
                'improvement': (objective_value - self._evaluate_default_params()) / self._evaluate_default_params() if self._evaluate_default_params() != 0 else 0,
                'confidence': min(objective_value, 1.0)
            }
        )
        
        self.results.append(optimization_result)
        
        return optimization_result
    
    def _evaluate_default_params(self) -> float:
        """
        Evaluate the objective with default parameters.
        
        Returns:
            Objective value
        """
        if self.objective_function is None:
            return 0.0
        
        return self.objective_function(self.default_parameters)
    
    def grid_search(self, param_grid: Dict[str, List[float]], **kwargs) -> OptimizationResult:
        """
        Perform grid search optimization.
        
        Args:
            param_grid: Parameter grid
            **kwargs: Additional parameters
            
        Returns:
            OptimizationResult object
        """
        if self.objective_function is None:
            raise ValueError("Objective function not set")
        
        # Generate grid combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        best_params = None
        best_value = -float('inf')
        
        # Simple grid search
        from itertools import product
        for values in product(*param_values):
            params = dict(zip(param_names, values))
            value = self.objective_function(params)
            
            if value > best_value:
                best_value = value
                best_params = params
        
        if best_params is None:
            raise ValueError("No valid parameters found")
        
        optimization_result = OptimizationResult(
            timestamp=datetime.now(),
            parameters=best_params,
            objective_value=best_value,
            constraints_satisfied=True,
            iterations=len(list(product(*param_values))),
            convergence=0,
            method='grid_search',
            metrics={
                'grid_size': len(list(product(*param_values))),
                'improvement': (best_value - self._evaluate_default_params()) / self._evaluate_default_params() if self._evaluate_default_params() != 0 else 0,
                'confidence': min(best_value, 1.0)
            }
        )
        
        self.results.append(optimization_result)
        
        return optimization_result
    
    def random_search(self, param_ranges: Dict[str, Tuple[float, float]], 
                     n_iterations: int = 100, **kwargs) -> OptimizationResult:
        """
        Perform random search optimization.
        
        Args:
            param_ranges: Parameter ranges
            n_iterations: Number of iterations
            **kwargs: Additional parameters
            
        Returns:
            OptimizationResult object
        """
        if self.objective_function is None:
            raise ValueError("Objective function not set")
        
        best_params = None
        best_value = -float('inf')
        
        for _ in range(n_iterations):
            params = {}
            for name, (low, high) in param_ranges.items():
                params[name] = np.random.uniform(low, high)
            
            value = self.objective_function(params)
            
            if value > best_value:
                best_value = value
                best_params = params
        
        if best_params is None:
            raise ValueError("No valid parameters found")
        
        optimization_result = OptimizationResult(
            timestamp=datetime.now(),
            parameters=best_params,
            objective_value=best_value,
            constraints_satisfied=True,
            iterations=n_iterations,
            convergence=0,
            method='random_search',
            metrics={
                'search_space_size': len(param_ranges),
                'iterations': n_iterations,
                'improvement': (best_value - self._evaluate_default_params()) / self._evaluate_default_params() if self._evaluate_default_params() != 0 else 0,
                'confidence': min(best_value, 1.0)
            }
        )
        
        self.results.append(optimization_result)
        
        return optimization_result
    
    def generate_signal(self, df: pd.DataFrame, params: Dict[str, float]) -> Optional[OptimizationSignal]:
        """
        Generate trading signal using optimized parameters.
        
        Args:
            df: OHLCV data
            params: Optimized parameters
            
        Returns:
            OptimizationSignal or None
        """
        if len(df) < self.lookback_period:
            return None
        
        # Use optimized parameters to generate signal
        # This is a simplified example - actual implementation would use the parameters
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Calculate simple signal based on parameters
        fast_ma = df['close'].rolling(int(params.get('fast_ma', 10))).mean().iloc[-1]
        slow_ma = df['close'].rolling(int(params.get('slow_ma', 30))).mean().iloc[-1]
        
        confidence = self.results[-1].metrics.get('confidence', 0.5) if self.results else 0.5
        
        if confidence < self.confidence_threshold:
            return None
        
        if fast_ma > slow_ma:
            signal_type = 'buy'
            reason = "Optimized parameters indicate bullish signal"
            target = current_price * (1 + params.get('take_profit', 0.04))
            stop_loss = current_price * (1 - params.get('stop_loss', 0.02))
        elif fast_ma < slow_ma:
            signal_type = 'sell'
            reason = "Optimized parameters indicate bearish signal"
            target = current_price * (1 - params.get('take_profit', 0.04))
            stop_loss = current_price * (1 + params.get('stop_loss', 0.02))
        else:
            return None
        
        return OptimizationSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            parameters=params,
            metrics=self.results[-1].metrics if self.results else {}
        )
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """
        Get optimization statistics.
        
        Returns:
            Optimization statistics
        """
        if not self.results:
            return {'total_optimizations': 0}
        
        stats = {
            'total_optimizations': len(self.results),
            'best_result': self.results[-1] if self.results else None,
            'methods_used': list(set(r.method for r in self.results)),
            'avg_iterations': np.mean([r.iterations for r in self.results]),
            'avg_convergence': np.mean([r.convergence for r in self.results]),
            'best_objective': max([r.objective_value for r in self.results]),
            'worst_objective': min([r.objective_value for r in self.results])
        }
        
        return stats


def create_optimization_model(config: Optional[Dict[str, Any]] = None) -> OptimizationModel:
    """
    Create an optimization model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        OptimizationModel instance
    """
    return OptimizationModel(config)


__all__ = [
    'OptimizationResult',
    'OptimizationSignal',
    'OptimizationModel',
    'create_optimization_model'
]
