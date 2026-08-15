"""
Swing Bot Evolution Model
===========================

This module provides evolutionary algorithm models for the Swing Bot trading system.
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
class Individual:
    """Individual in evolutionary population."""
    genes: Dict[str, float]
    fitness: float
    age: int
    generation: int
    timestamp: datetime


@dataclass
class EvolutionResult:
    """Evolution result data structure."""
    timestamp: datetime
    best_individual: Individual
    best_fitness: float
    average_fitness: float
    population_size: int
    generation: int
    convergence_rate: float


@dataclass
class EvolutionSignal:
    """Evolution trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    evolution: EvolutionResult
    indicators: Dict[str, Any] = field(default_factory=dict)


class EvolutionModel:
    """
    Evolutionary algorithm model for parameter optimization.
    
    Implements genetic algorithms and evolutionary strategies.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the evolution model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.population_size = self.config.get('population_size', 50)
        self.generations = self.config.get('generations', 100)
        self.mutation_rate = self.config.get('mutation_rate', 0.1)
        self.crossover_rate = self.config.get('crossover_rate', 0.8)
        self.elite_size = self.config.get('elite_size', 5)
        self.tournament_size = self.config.get('tournament_size', 3)
        
        self.population: List[Individual] = []
        self.best_individuals: List[Individual] = []
        self.results: List[EvolutionResult] = []
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        # Define parameter bounds
        self.param_bounds = self.config.get('param_bounds', {
            'fast_ma': (5, 30),
            'slow_ma': (20, 100),
            'rsi_period': (7, 21),
            'bb_period': (10, 30),
            'bb_std': (1.5, 3.0),
            'stop_loss': (0.005, 0.05),
            'take_profit': (0.01, 0.10)
        })
        
    def initialize_population(self) -> None:
        """Initialize the population."""
        self.population = []
        
        for _ in range(self.population_size):
            genes = self._random_genes()
            individual = Individual(
                genes=genes,
                fitness=0.0,
                age=0,
                generation=0,
                timestamp=datetime.now()
            )
            self.population.append(individual)
    
    def _random_genes(self) -> Dict[str, float]:
        """
        Generate random genes.
        
        Returns:
            Dictionary of random genes
        """
        genes = {}
        for param, (min_val, max_val) in self.param_bounds.items():
            genes[param] = random.uniform(min_val, max_val)
        
        return genes
    
    def evaluate_fitness(self, individual: Individual, df: pd.DataFrame) -> float:
        """
        Evaluate fitness of an individual.
        
        Args:
            individual: Individual to evaluate
            df: Market data
            
        Returns:
            Fitness score
        """
        # This is a placeholder - actual fitness would use trading simulation
        # For now, use a simple metric based on parameter combination
        genes = individual.genes
        
        # Simple fitness based on parameter diversity
        fitness = 0.0
        for param, value in genes.items():
            if param in self.param_bounds:
                min_val, max_val = self.param_bounds[param]
                normalized = (value - min_val) / (max_val - min_val)
                fitness += normalized
        
        fitness /= len(genes)
        
        return fitness
    
    def select_parents(self) -> Tuple[Individual, Individual]:
        """
        Select parents using tournament selection.
        
        Returns:
            Tuple of two parent individuals
        """
        def tournament_select():
            tournament = random.sample(self.population, self.tournament_size)
            return max(tournament, key=lambda x: x.fitness)
        
        parent1 = tournament_select()
        parent2 = tournament_select()
        
        return parent1, parent2
    
    def crossover(self, parent1: Individual, parent2: Individual) -> Individual:
        """
        Perform crossover between two parents.
        
        Args:
            parent1: First parent
            parent2: Second parent
            
        Returns:
            Child individual
        """
        if random.random() > self.crossover_rate:
            return parent1
        
        child_genes = {}
        
        for param in parent1.genes.keys():
            if random.random() < 0.5:
                child_genes[param] = parent1.genes[param]
            else:
                child_genes[param] = parent2.genes[param]
        
        return Individual(
            genes=child_genes,
            fitness=0.0,
            age=0,
            generation=parent1.generation + 1,
            timestamp=datetime.now()
        )
    
    def mutate(self, individual: Individual) -> Individual:
        """
        Mutate an individual.
        
        Args:
            individual: Individual to mutate
            
        Returns:
            Mutated individual
        """
        if random.random() > self.mutation_rate:
            return individual
        
        mutated_genes = individual.genes.copy()
        
        for param, value in mutated_genes.items():
            if param in self.param_bounds:
                min_val, max_val = self.param_bounds[param]
                # Random mutation within bounds
                mutation = random.uniform(-0.1, 0.1) * (max_val - min_val)
                mutated_genes[param] = max(min_val, min(max_val, value + mutation))
        
        return Individual(
            genes=mutated_genes,
            fitness=0.0,
            age=0,
            generation=individual.generation + 1,
            timestamp=datetime.now()
        )
    
    def evolve(self, df: pd.DataFrame) -> EvolutionResult:
        """
        Run evolutionary optimization.
        
        Args:
            df: Market data
            
        Returns:
            EvolutionResult object
        """
        if not self.population:
            self.initialize_population()
        
        # Evaluate initial population
        for individual in self.population:
            individual.fitness = self.evaluate_fitness(individual, df)
        
        for generation in range(self.generations):
            new_population = []
            
            # Elitism - keep best individuals
            sorted_population = sorted(self.population, key=lambda x: x.fitness, reverse=True)
            elites = sorted_population[:self.elite_size]
            new_population.extend(elites)
            
            # Create offspring
            while len(new_population) < self.population_size:
                parent1, parent2 = self.select_parents()
                child = self.crossover(parent1, parent2)
                child = self.mutate(child)
                child.fitness = self.evaluate_fitness(child, df)
                new_population.append(child)
            
            self.population = new_population
            
            # Track best individual
            best = max(self.population, key=lambda x: x.fitness)
            self.best_individuals.append(best)
            
            # Check convergence
            if generation > 10:
                recent_best = [b.fitness for b in self.best_individuals[-10:]]
                if max(recent_best) - min(recent_best) < 0.001:
                    break
        
        # Get final results
        best = max(self.population, key=lambda x: x.fitness)
        avg_fitness = np.mean([ind.fitness for ind in self.population])
        
        result = EvolutionResult(
            timestamp=datetime.now(),
            best_individual=best,
            best_fitness=best.fitness,
            average_fitness=avg_fitness,
            population_size=len(self.population),
            generation=len(self.best_individuals),
            convergence_rate=1 - (max([b.fitness for b in self.best_individuals[-10:]]) - 
                                min([b.fitness for b in self.best_individuals[-10:]])) if len(self.best_individuals) >= 10 else 0
        )
        
        self.results.append(result)
        
        return result
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[EvolutionSignal]:
        """
        Generate trading signal from evolution results.
        
        Args:
            df: OHLCV data
            
        Returns:
            EvolutionSignal or None
        """
        if not self.results:
            return None
        
        latest_result = self.results[-1]
        
        if latest_result.best_fitness < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Use best parameters for signal
        params = latest_result.best_individual.genes
        
        # Simple signal based on parameters
        fast_ma = df['close'].rolling(int(params.get('fast_ma', 10))).mean().iloc[-1]
        slow_ma = df['close'].rolling(int(params.get('slow_ma', 30))).mean().iloc[-1]
        
        if fast_ma > slow_ma:
            signal_type = 'buy'
            reason = "Optimized parameters indicate bullish signal"
            confidence = latest_result.best_fitness
            target = current_price * (1 + params.get('take_profit', 0.04))
            stop_loss = current_price * (1 - params.get('stop_loss', 0.02))
            
        elif fast_ma < slow_ma:
            signal_type = 'sell'
            reason = "Optimized parameters indicate bearish signal"
            confidence = latest_result.best_fitness
            target = current_price * (1 - params.get('take_profit', 0.04))
            stop_loss = current_price * (1 + params.get('stop_loss', 0.02))
            
        else:
            return None
        
        return EvolutionSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            evolution=latest_result,
            indicators={
                'best_params': params,
                'fitness': latest_result.best_fitness,
                'generation': latest_result.generation
            }
        )
    
    def get_evolution_summary(self) -> Dict[str, Any]:
        """
        Get evolution summary.
        
        Returns:
            Evolution summary
        """
        if not self.results:
            return {'status': 'no_evolution'}
        
        latest = self.results[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_result': latest,
            'total_generations': len(self.best_individuals),
            'best_fitness': latest.best_fitness,
            'average_fitness': latest.average_fitness,
            'convergence_rate': latest.convergence_rate,
            'best_parameters': latest.best_individual.genes,
            'population_size': latest.population_size
        }


def create_evolution_model(config: Optional[Dict[str, Any]] = None) -> EvolutionModel:
    """
    Create an evolution model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        EvolutionModel instance
    """
    return EvolutionModel(config)


__all__ = [
    'Individual',
    'EvolutionResult',
    'EvolutionSignal',
    'EvolutionModel',
    'create_evolution_model'
]
