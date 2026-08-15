"""
Swing Bot Genetic Model
=========================

This module provides genetic algorithm models for the Swing Bot trading system.
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
class Chromosome:
    """Chromosome data structure."""
    genes: np.ndarray
    fitness: float
    age: int
    generation: int


@dataclass
class GeneticResult:
    """Genetic algorithm result data structure."""
    timestamp: datetime
    best_chromosome: Chromosome
    best_fitness: float
    average_fitness: float
    population_size: int
    generation: int
    convergence_rate: float


@dataclass
class GeneticSignal:
    """Genetic trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    result: GeneticResult
    indicators: Dict[str, Any] = field(default_factory=dict)


class GeneticModel:
    """
    Genetic algorithm model for parameter optimization.
    
    Implements genetic algorithms for trading optimization.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the genetic model.
        
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
        
        self.population: List[Chromosome] = []
        self.best_fitness_history: List[float] = []
        self.results: List[GeneticResult] = []
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        # Define gene bounds
        self.gene_bounds = self.config.get('gene_bounds', {
            'fast_ma': (5, 30),
            'slow_ma': (20, 100),
            'rsi_period': (7, 21),
            'bb_period': (10, 30),
            'bb_std': (1.5, 3.0),
            'stop_loss': (0.005, 0.05),
            'take_profit': (0.01, 0.10)
        })
        
        self.gene_names = list(self.gene_bounds.keys())
        self.n_genes = len(self.gene_names)
        
    def initialize_population(self) -> None:
        """Initialize the population."""
        self.population = []
        
        for _ in range(self.population_size):
            genes = self._random_genes()
            chromosome = Chromosome(
                genes=genes,
                fitness=0.0,
                age=0,
                generation=0
            )
            self.population.append(chromosome)
    
    def _random_genes(self) -> np.ndarray:
        """
        Generate random genes.
        
        Returns:
            Random gene array
        """
        genes = []
        for name in self.gene_names:
            min_val, max_val = self.gene_bounds[name]
            genes.append(random.uniform(min_val, max_val))
        
        return np.array(genes)
    
    def evaluate_fitness(self, chromosome: Chromosome, df: pd.DataFrame) -> float:
        """
        Evaluate fitness of a chromosome.
        
        Args:
            chromosome: Chromosome to evaluate
            df: Market data
            
        Returns:
            Fitness score
        """
        # This is a placeholder - actual fitness would use trading simulation
        # For now, use a simple metric based on gene values
        genes = chromosome.genes
        fitness = 0.0
        
        for i, name in enumerate(self.gene_names):
            if i < len(genes):
                min_val, max_val = self.gene_bounds[name]
                normalized = (genes[i] - min_val) / (max_val - min_val)
                fitness += normalized
        
        fitness /= len(self.gene_names)
        
        return fitness
    
    def select_parents(self) -> Tuple[Chromosome, Chromosome]:
        """
        Select parents using tournament selection.
        
        Returns:
            Tuple of two parent chromosomes
        """
        def tournament_select():
            tournament = random.sample(self.population, self.tournament_size)
            return max(tournament, key=lambda x: x.fitness)
        
        parent1 = tournament_select()
        parent2 = tournament_select()
        
        return parent1, parent2
    
    def crossover(self, parent1: Chromosome, parent2: Chromosome) -> Chromosome:
        """
        Perform crossover between two parents.
        
        Args:
            parent1: First parent
            parent2: Second parent
            
        Returns:
            Child chromosome
        """
        if random.random() > self.crossover_rate:
            return parent1
        
        # Uniform crossover
        child_genes = np.zeros_like(parent1.genes)
        for i in range(len(parent1.genes)):
            if random.random() < 0.5:
                child_genes[i] = parent1.genes[i]
            else:
                child_genes[i] = parent2.genes[i]
        
        return Chromosome(
            genes=child_genes,
            fitness=0.0,
            age=0,
            generation=parent1.generation + 1
        )
    
    def mutate(self, chromosome: Chromosome) -> Chromosome:
        """
        Mutate a chromosome.
        
        Args:
            chromosome: Chromosome to mutate
            
        Returns:
            Mutated chromosome
        """
        if random.random() > self.mutation_rate:
            return chromosome
        
        mutated_genes = chromosome.genes.copy()
        
        for i, name in enumerate(self.gene_names):
            if random.random() < self.mutation_rate:
                min_val, max_val = self.gene_bounds[name]
                # Gaussian mutation
                mutation = np.random.normal(0, 0.1 * (max_val - min_val))
                mutated_genes[i] = max(min_val, min(max_val, mutated_genes[i] + mutation))
        
        return Chromosome(
            genes=mutated_genes,
            fitness=0.0,
            age=0,
            generation=chromosome.generation + 1
        )
    
    def evolve(self, df: pd.DataFrame) -> GeneticResult:
        """
        Run genetic algorithm optimization.
        
        Args:
            df: Market data
            
        Returns:
            GeneticResult object
        """
        if not self.population:
            self.initialize_population()
        
        # Evaluate initial population
        for chromosome in self.population:
            chromosome.fitness = self.evaluate_fitness(chromosome, df)
        
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
            
            # Track best fitness
            best_fitness = max(c.fitness for c in self.population)
            self.best_fitness_history.append(best_fitness)
            
            # Check convergence
            if generation > 10:
                recent_best = self.best_fitness_history[-10:]
                if max(recent_best) - min(recent_best) < 0.001:
                    break
        
        # Get final results
        best = max(self.population, key=lambda x: x.fitness)
        avg_fitness = np.mean([c.fitness for c in self.population])
        
        result = GeneticResult(
            timestamp=datetime.now(),
            best_chromosome=best,
            best_fitness=best.fitness,
            average_fitness=avg_fitness,
            population_size=len(self.population),
            generation=len(self.best_fitness_history),
            convergence_rate=1 - (max(self.best_fitness_history[-10:]) - 
                                min(self.best_fitness_history[-10:])) if len(self.best_fitness_history) >= 10 else 0
        )
        
        self.results.append(result)
        
        return result
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[GeneticSignal]:
        """
        Generate trading signal from genetic algorithm results.
        
        Args:
            df: OHLCV data
            
        Returns:
            GeneticSignal or None
        """
        if not self.results:
            return None
        
        latest_result = self.results[-1]
        
        if latest_result.best_fitness < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Use best genes for signal
        genes = latest_result.best_chromosome.genes
        params = {}
        for i, name in enumerate(self.gene_names):
            if i < len(genes):
                params[name] = genes[i]
        
        # Simple signal based on parameters
        fast_ma = df['close'].rolling(int(params.get('fast_ma', 10))).mean().iloc[-1]
        slow_ma = df['close'].rolling(int(params.get('slow_ma', 30))).mean().iloc[-1]
        
        if fast_ma > slow_ma:
            signal_type = 'buy'
            reason = "Genetic algorithm optimized parameters indicate bullish signal"
            confidence = latest_result.best_fitness
            target = current_price * (1 + params.get('take_profit', 0.04))
            stop_loss = current_price * (1 - params.get('stop_loss', 0.02))
            
        elif fast_ma < slow_ma:
            signal_type = 'sell'
            reason = "Genetic algorithm optimized parameters indicate bearish signal"
            confidence = latest_result.best_fitness
            target = current_price * (1 - params.get('take_profit', 0.04))
            stop_loss = current_price * (1 + params.get('stop_loss', 0.02))
            
        else:
            return None
        
        return GeneticSignal(
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
                'best_genes': params,
                'fitness': latest_result.best_fitness,
                'generation': latest_result.generation,
                'population_size': latest_result.population_size
            }
        )
    
    def get_genetic_summary(self) -> Dict[str, Any]:
        """
        Get genetic algorithm summary.
        
        Returns:
            Genetic summary
        """
        if not self.results:
            return {'status': 'no_results'}
        
        latest = self.results[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_result': latest,
            'total_generations': len(self.best_fitness_history),
            'best_fitness': latest.best_fitness,
            'average_fitness': latest.average_fitness,
            'convergence_rate': latest.convergence_rate,
            'best_genes': latest.best_chromosome.genes.tolist(),
            'population_size': latest.population_size
        }


def create_genetic_model(config: Optional[Dict[str, Any]] = None) -> GeneticModel:
    """
    Create a genetic model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        GeneticModel instance
    """
    return GeneticModel(config)


__all__ = [
    'Chromosome',
    'GeneticResult',
    'GeneticSignal',
    'GeneticModel',
    'create_genetic_model'
]
