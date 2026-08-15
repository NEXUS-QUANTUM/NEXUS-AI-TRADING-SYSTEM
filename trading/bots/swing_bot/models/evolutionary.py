"""
Swing Bot Evolutionary Model
==============================

This module provides evolutionary strategy models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
import random
import warnings
warnings.filterwarnings('ignore')


@dataclass
class EvolutionaryStrategy:
    """Evolutionary strategy configuration."""
    strategy_type: str  # 'es', 'cma_es', 'de'
    population_size: int
    mutation_rate: float
    recombination_rate: float
    selection_pressure: float
    convergence_threshold: float


@dataclass
class EvolutionaryResult:
    """Evolutionary result data structure."""
    timestamp: datetime
    best_solution: Dict[str, float]
    best_fitness: float
    average_fitness: float
    population_size: int
    generation: int
    convergence: float
    strategy: EvolutionaryStrategy


@dataclass
class EvolutionarySignal:
    """Evolutionary trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    result: EvolutionaryResult
    indicators: Dict[str, Any] = field(default_factory=dict)


class EvolutionaryModel:
    """
    Evolutionary strategy model for market optimization.
    
    Implements evolutionary strategies for trading optimization.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the evolutionary model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.population: List[Dict[str, float]] = []
        self.fitness_history: List[float] = []
        self.results: List[EvolutionaryResult] = []
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        # Strategy configuration
        self.strategy = EvolutionaryStrategy(
            strategy_type='cma_es',
            population_size=50,
            mutation_rate=0.1,
            recombination_rate=0.8,
            selection_pressure=0.5,
            convergence_threshold=0.001
        )
        
        # Parameter bounds
        self.param_bounds = self.config.get('param_bounds', {
            'fast_ma': (5, 30),
            'slow_ma': (20, 100),
            'rsi_period': (7, 21),
            'bb_period': (10, 30),
            'bb_std': (1.5, 3.0),
            'stop_loss': (0.005, 0.05),
            'take_profit': (0.01, 0.10)
        })
        
        # Initialize mean and variance for CMA-ES
        self.mean = np.array([(self.param_bounds[p][0] + self.param_bounds[p][1]) / 2 
                            for p in self.param_bounds.keys()])
        self.sigma = 0.3  # Step size
        self.c = 0.1  # Learning rate for covariance matrix
        self.d = 0.2  # Damping factor
        
    def initialize_population(self) -> None:
        """Initialize the population."""
        self.population = []
        param_names = list(self.param_bounds.keys())
        
        for _ in range(self.strategy.population_size):
            individual = self._generate_individual()
            self.population.append(individual)
    
    def _generate_individual(self) -> Dict[str, float]:
        """
        Generate a random individual.
        
        Returns:
            Individual dictionary
        """
        individual = {}
        for param, (min_val, max_val) in self.param_bounds.items():
            individual[param] = random.uniform(min_val, max_val)
        
        return individual
    
    def _cma_es_step(self) -> List[Dict[str, float]]:
        """
        Perform CMA-ES step.
        
        Returns:
            New population
        """
        param_names = list(self.param_bounds.keys())
        n_params = len(param_names)
        new_population = []
        
        # Generate offspring
        for _ in range(self.strategy.population_size):
            # Add random perturbation
            perturbation = np.random.normal(0, self.sigma, n_params)
            new_params = self.mean + perturbation
            
            # Create individual
            individual = {}
            for i, name in enumerate(param_names):
                min_val, max_val = self.param_bounds[name]
                individual[name] = max(min_val, min(max_val, new_params[i]))
            
            new_population.append(individual)
        
        # Evaluate fitness and update mean
        fitness_values = []
        for individual in new_population:
            fitness = self._evaluate_fitness(individual)
            fitness_values.append(fitness)
        
        # Sort by fitness (descending)
        sorted_indices = np.argsort(fitness_values)[::-1]
        
        # Update mean using top individuals
        top_indices = sorted_indices[:self.strategy.population_size // 2]
        top_individuals = [new_population[i] for i in top_indices]
        
        new_mean = np.zeros(n_params)
        for individual in top_individuals:
            for i, name in enumerate(param_names):
                new_mean[i] += individual[name]
        new_mean /= len(top_individuals)
        
        # Update step size
        self.sigma *= np.exp(self.c * (np.mean(fitness_values) - self.fitness_history[-1]) / self.d)
        self.sigma = max(0.01, self.sigma)
        
        # Update mean
        self.mean = new_mean
        
        return new_population
    
    def _evaluate_fitness(self, individual: Dict[str, float]) -> float:
        """
        Evaluate fitness of an individual.
        
        Args:
            individual: Individual to evaluate
            
        Returns:
            Fitness score
        """
        # This is a placeholder - actual fitness would use trading simulation
        # For now, use a simple metric based on parameter combination
        fitness = 0.0
        for param, value in individual.items():
            if param in self.param_bounds:
                min_val, max_val = self.param_bounds[param]
                normalized = (value - min_val) / (max_val - min_val)
                fitness += normalized
        
        fitness /= len(individual)
        
        return fitness
    
    def evolve(self, df: pd.DataFrame) -> EvolutionaryResult:
        """
        Run evolutionary optimization.
        
        Args:
            df: Market data
            
        Returns:
            EvolutionaryResult object
        """
        if not self.population:
            self.initialize_population()
        
        generation = 0
        convergence = 0
        
        while generation < self.config.get('max_generations', 100):
            # Generate new population
            if self.strategy.strategy_type == 'cma_es':
                new_population = self._cma_es_step()
            else:
                # Simple ES
                new_population = []
                for individual in self.population:
                    mutated = self._mutate(individual)
                    new_population.append(mutated)
                self.population = new_population
            
            # Evaluate fitness
            fitness_values = []
            for individual in self.population:
                fitness = self._evaluate_fitness(individual)
                fitness_values.append(fitness)
            
            avg_fitness = np.mean(fitness_values)
            best_fitness = max(fitness_values)
            
            # Track fitness
            self.fitness_history.append(avg_fitness)
            
            # Check convergence
            if len(self.fitness_history) > 10:
                convergence = (max(self.fitness_history[-10:]) - 
                             min(self.fitness_history[-10:]))
                if convergence < self.strategy.convergence_threshold:
                    break
            
            generation += 1
        
        # Get best solution
        best_idx = np.argmax([self._evaluate_fitness(ind) for ind in self.population])
        best_solution = self.population[best_idx]
        
        result = EvolutionaryResult(
            timestamp=datetime.now(),
            best_solution=best_solution,
            best_fitness=max(self.fitness_history) if self.fitness_history else 0,
            average_fitness=avg_fitness,
            population_size=len(self.population),
            generation=generation,
            convergence=convergence,
            strategy=self.strategy
        )
        
        self.results.append(result)
        
        return result
    
    def _mutate(self, individual: Dict[str, float]) -> Dict[str, float]:
        """
        Mutate an individual.
        
        Args:
            individual: Individual to mutate
            
        Returns:
            Mutated individual
        """
        mutated = individual.copy()
        
        for param in mutated:
            if param in self.param_bounds:
                min_val, max_val = self.param_bounds[param]
                # Add random mutation
                mutation = np.random.normal(0, self.strategy.mutation_rate * (max_val - min_val))
                mutated[param] = max(min_val, min(max_val, mutated[param] + mutation))
        
        return mutated
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[EvolutionarySignal]:
        """
        Generate trading signal from evolutionary result.
        
        Args:
            df: OHLCV data
            
        Returns:
            EvolutionarySignal or None
        """
        if not self.results:
            return None
        
        latest_result = self.results[-1]
        
        if latest_result.best_fitness < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Use best solution for signal
        params = latest_result.best_solution
        
        # Simple signal based on parameters
        fast_ma = df['close'].rolling(int(params.get('fast_ma', 10))).mean().iloc[-1]
        slow_ma = df['close'].rolling(int(params.get('slow_ma', 30))).mean().iloc[-1]
        
        if fast_ma > slow_ma:
            signal_type = 'buy'
            reason = "Evolutionary optimized parameters indicate bullish signal"
            confidence = latest_result.best_fitness
            target = current_price * (1 + params.get('take_profit', 0.04))
            stop_loss = current_price * (1 - params.get('stop_loss', 0.02))
            
        elif fast_ma < slow_ma:
            signal_type = 'sell'
            reason = "Evolutionary optimized parameters indicate bearish signal"
            confidence = latest_result.best_fitness
            target = current_price * (1 - params.get('take_profit', 0.04))
            stop_loss = current_price * (1 + params.get('stop_loss', 0.02))
            
        else:
            return None
        
        return EvolutionarySignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            result=latest_result,
            indicators={
                'best_solution': params,
                'fitness': latest_result.best_fitness,
                'generation': latest_result.generation,
                'strategy': latest_result.strategy.strategy_type
            }
        )
    
    def get_evolutionary_summary(self) -> Dict[str, Any]:
        """
        Get evolutionary summary.
        
        Returns:
            Evolutionary summary
        """
        if not self.results:
            return {'status': 'no_evolution'}
        
        latest = self.results[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_result': latest,
            'total_generations': len(self.fitness_history),
            'best_fitness': latest.best_fitness,
            'average_fitness': latest.average_fitness,
            'convergence': latest.convergence,
            'best_solution': latest.best_solution,
            'strategy_type': latest.strategy.strategy_type,
            'population_size': latest.population_size
        }


def create_evolutionary_model(config: Optional[Dict[str, Any]] = None) -> EvolutionaryModel:
    """
    Create an evolutionary model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        EvolutionaryModel instance
    """
    return EvolutionaryModel(config)


__all__ = [
    'EvolutionaryStrategy',
    'EvolutionaryResult',
    'EvolutionarySignal',
    'EvolutionaryModel',
    'create_evolutionary_model'
]
