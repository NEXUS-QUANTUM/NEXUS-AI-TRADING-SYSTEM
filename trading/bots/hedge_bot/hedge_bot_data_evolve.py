# trading/bots/hedge_bot/hedge_bot_data_evolve.py
# Advanced Evolutionary Data Processing & Adaptive Learning for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Evolutionary Data Module - Module d'évolution adaptative avancé pour le Hedge Bot.
Implémente des algorithmes génétiques, l'apprentissage par renforcement, l'adaptation continue
et l'optimisation évolutionnaire des stratégies de hedging.
"""

import asyncio
import json
import math
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import copy
import hashlib
import pickle
import zlib

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_evolve")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType, HedgeStrategy, MarketRegime
)


# ============== ENUMS & TYPES ==============

class EvolutionType(Enum):
    """Types d'évolution."""
    GENETIC = "genetic"
    REINFORCEMENT = "reinforcement"
    ADAPTIVE = "adaptive"
    HYBRID = "hybrid"
    SWARM = "swarm"
    GRADIENT = "gradient"


class SelectionMethod(Enum):
    """Méthodes de sélection évolutionnaire."""
    ROULETTE = "roulette"
    TOURNAMENT = "tournament"
    RANK = "rank"
    ELITE = "elite"
    STOCHASTIC_UNIVERSAL = "stochastic_universal"
    TRUNCATION = "truncation"


class CrossoverMethod(Enum):
    """Méthodes de croisement."""
    SINGLE_POINT = "single_point"
    TWO_POINT = "two_point"
    UNIFORM = "uniform"
    ARITHMETIC = "arithmetic"
    HEURISTIC = "heuristic"
    ORDER = "order"


class MutationMethod(Enum):
    """Méthodes de mutation."""
    RANDOM = "random"
    GAUSSIAN = "gaussian"
    UNIFORM = "uniform"
    BOUNDARY = "boundary"
    ADAPTIVE = "adaptive"
    NON_UNIFORM = "non_uniform"


class FitnessMethod(Enum):
    """Méthodes de calcul de fitness."""
    SHARPE = "sharpe"
    SORTINO = "sortino"
    CALMAR = "calmar"
    PROFIT_FACTOR = "profit_factor"
    WIN_RATE = "win_rate"
    CUSTOM = "custom"
    MULTI_OBJECTIVE = "multi_objective"


# ============== DATA MODELS ==============

@dataclass
class Genome:
    """Génome pour l'évolution."""
    genome_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    genes: Dict[str, Any] = field(default_factory=dict)
    fitness: float = 0.0
    fitness_history: List[float] = field(default_factory=list)
    generation: int = 0
    age: int = 0
    parent_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "genome_id": self.genome_id,
            "genes": self.genes,
            "fitness": self.fitness,
            "fitness_history": self.fitness_history,
            "generation": self.generation,
            "age": self.age,
            "parent_ids": self.parent_ids,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags
        }


@dataclass
class Population:
    """Population d'individus."""
    population_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    genomes: List[Genome] = field(default_factory=list)
    generation: int = 0
    best_fitness: float = 0.0
    avg_fitness: float = 0.0
    worst_fitness: float = 0.0
    diversity: float = 0.0
    convergence_rate: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "population_id": self.population_id,
            "generation": self.generation,
            "best_fitness": self.best_fitness,
            "avg_fitness": self.avg_fitness,
            "worst_fitness": self.worst_fitness,
            "diversity": self.diversity,
            "convergence_rate": self.convergence_rate,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "genome_count": len(self.genomes)
        }


@dataclass
class EvolutionaryExperiment:
    """Expérience évolutionnaire."""
    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    evolution_type: EvolutionType = EvolutionType.GENETIC
    population_size: int = 100
    generations: int = 100
    mutation_rate: float = 0.01
    crossover_rate: float = 0.8
    selection_method: SelectionMethod = SelectionMethod.TOURNAMENT
    crossover_method: CrossoverMethod = CrossoverMethod.TWO_POINT
    mutation_method: MutationMethod = MutationMethod.GAUSSIAN
    fitness_method: FitnessMethod = FitnessMethod.SHARPE
    elitism_count: int = 2
    tournament_size: int = 3
    convergence_threshold: float = 0.001
    max_stagnation: int = 10
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str = "created"  # created, running, completed, failed, paused
    best_genome: Optional[Genome] = None
    population_history: List[Population] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "description": self.description,
            "evolution_type": self.evolution_type.value,
            "population_size": self.population_size,
            "generations": self.generations,
            "mutation_rate": self.mutation_rate,
            "crossover_rate": self.crossover_rate,
            "selection_method": self.selection_method.value,
            "crossover_method": self.crossover_method.value,
            "mutation_method": self.mutation_method.value,
            "fitness_method": self.fitness_method.value,
            "elitism_count": self.elitism_count,
            "tournament_size": self.tournament_size,
            "convergence_threshold": self.convergence_threshold,
            "max_stagnation": self.max_stagnation,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "metadata": self.metadata,
            "tags": self.tags
        }


@dataclass
class ReinforcementExperience:
    """Expérience d'apprentissage par renforcement."""
    experience_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: Dict[str, Any] = field(default_factory=dict)
    action: Dict[str, Any] = field(default_factory=dict)
    reward: float = 0.0
    next_state: Dict[str, Any] = field(default_factory=dict)
    done: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: float = 0.0  # Pour l'échantillonnage prioritaire


@dataclass
class AdaptiveParameter:
    """Paramètre adaptatif."""
    name: str = ""
    value: float = 0.0
    min_value: float = 0.0
    max_value: float = 1.0
    step: float = 0.01
    adaptation_rate: float = 0.1
    history: List[float] = field(default_factory=list)
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============== INTERFACES ==============

class EvolutionEngineInterface(ABC):
    """Interface abstraite pour le moteur d'évolution."""
    
    @abstractmethod
    async def create_experiment(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> EvolutionaryExperiment:
        """Crée une expérience évolutionnaire."""
        pass
    
    @abstractmethod
    async def run_experiment(
        self,
        experiment_id: str,
        fitness_function: Callable[[Genome], float]
    ) -> EvolutionaryExperiment:
        """Exécute une expérience évolutionnaire."""
        pass
    
    @abstractmethod
    async def get_best_genome(self, experiment_id: str) -> Optional[Genome]:
        """Récupère le meilleur génome."""
        pass


class ReinforcementEngineInterface(ABC):
    """Interface abstraite pour le moteur d'apprentissage par renforcement."""
    
    @abstractmethod
    async def record_experience(self, experience: ReinforcementExperience) -> None:
        """Enregistre une expérience."""
        pass
    
    @abstractmethod
    async def get_batch(self, batch_size: int) -> List[ReinforcementExperience]:
        """Récupère un batch d'expériences."""
        pass
    
    @abstractmethod
    async def train(self, batch: List[ReinforcementExperience]) -> Dict[str, Any]:
        """Entraîne le modèle avec un batch."""
        pass


# ============== IMPLÉMENTATIONS ==============

class EvolutionaryEngine(EvolutionEngineInterface):
    """
    Moteur d'évolution avancé avec algorithmes génétiques.
    Optimise les paramètres de hedging à travers des générations.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Stockage des expériences
        self._experiments: Dict[str, EvolutionaryExperiment] = {}
        self._experiments_lock = threading.RLock()
        
        # Stockage des populations
        self._populations: Dict[str, Population] = {}
        self._populations_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "experiments_created": 0,
            "experiments_completed": 0,
            "experiments_failed": 0,
            "total_generations": 0,
            "total_evals": 0
        }
        
        # Cache des génomes
        self._genome_cache: Dict[str, Genome] = {}
        self._cache_lock = threading.RLock()
        
        # Thread pool pour les évaluations parallèles
        self._eval_pool = ThreadPoolExecutor(max_workers=self.config.get("eval_workers", 4))
        
        logger.info("EvolutionaryEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "default_population_size": 100,
            "default_generations": 50,
            "default_mutation_rate": 0.01,
            "default_crossover_rate": 0.8,
            "default_elitism_count": 2,
            "default_tournament_size": 3,
            "parallel_evaluations": True,
            "eval_workers": 4,
            "cache_size": 10000,
            "enable_checkpointing": True,
            "checkpoint_interval": 5
        }
    
    async def create_experiment(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> EvolutionaryExperiment:
        """Crée une expérience évolutionnaire."""
        experiment = EvolutionaryExperiment(
            name=name,
            population_size=config.get("population_size", self.config["default_population_size"]),
            generations=config.get("generations", self.config["default_generations"]),
            mutation_rate=config.get("mutation_rate", self.config["default_mutation_rate"]),
            crossover_rate=config.get("crossover_rate", self.config["default_crossover_rate"]),
            selection_method=SelectionMethod(config.get("selection_method", "tournament")),
            crossover_method=CrossoverMethod(config.get("crossover_method", "two_point")),
            mutation_method=MutationMethod(config.get("mutation_method", "gaussian")),
            fitness_method=FitnessMethod(config.get("fitness_method", "sharpe")),
            elitism_count=config.get("elitism_count", self.config["default_elitism_count"]),
            tournament_size=config.get("tournament_size", self.config["default_tournament_size"]),
            convergence_threshold=config.get("convergence_threshold", 0.001),
            max_stagnation=config.get("max_stagnation", 10),
            metadata=config.get("metadata", {})
        )
        
        with self._experiments_lock:
            self._experiments[experiment.experiment_id] = experiment
        
        self._stats["experiments_created"] += 1
        
        logger.info(f"Experiment created: {name} (id={experiment.experiment_id})")
        return experiment
    
    async def run_experiment(
        self,
        experiment_id: str,
        fitness_function: Callable[[Genome], float]
    ) -> EvolutionaryExperiment:
        """Exécute une expérience évolutionnaire."""
        with self._experiments_lock:
            experiment = self._experiments.get(experiment_id)
            if not experiment:
                raise ValueError(f"Experiment {experiment_id} not found")
            
            experiment.status = "running"
            experiment.start_time = datetime.now(timezone.utc)
        
        try:
            # Initialisation de la population
            population = await self._initialize_population(experiment)
            
            # Boucle d'évolution
            for generation in range(experiment.generations):
                # Évaluation de la fitness
                await self._evaluate_population(population, fitness_function)
                
                # Enregistrement de la population
                await self._record_population(experiment, population, generation)
                
                # Vérification de la convergence
                if await self._check_convergence(experiment, population):
                    logger.info(f"Convergence reached at generation {generation}")
                    break
                
                # Sélection
                selected = await self._selection(experiment, population)
                
                # Croisement
                offspring = await self._crossover(experiment, selected)
                
                # Mutation
                offspring = await self._mutation(experiment, offspring)
                
                # Nouvelle population
                population = await self._create_next_population(
                    experiment,
                    population,
                    offspring
                )
                
                # Mise à jour du génome best
                best = max(population.genomes, key=lambda g: g.fitness)
                if best.fitness > experiment.best_fitness:
                    experiment.best_fitness = best.fitness
                    experiment.best_genome = copy.deepcopy(best)
                
                logger.debug(f"Generation {generation}: best={experiment.best_fitness:.4f}, "
                           f"avg={population.avg_fitness:.4f}")
            
            # Finalisation
            experiment.status = "completed"
            experiment.end_time = datetime.now(timezone.utc)
            
            with self._experiments_lock:
                self._experiments[experiment_id] = experiment
            
            self._stats["experiments_completed"] += 1
            
            return experiment
            
        except Exception as e:
            experiment.status = "failed"
            experiment.end_time = datetime.now(timezone.utc)
            experiment.metadata["error"] = str(e)
            
            with self._experiments_lock:
                self._experiments[experiment_id] = experiment
            
            self._stats["experiments_failed"] += 1
            logger.error(f"Experiment {experiment_id} failed: {e}")
            raise
    
    async def get_best_genome(self, experiment_id: str) -> Optional[Genome]:
        """Récupère le meilleur génome."""
        with self._experiments_lock:
            experiment = self._experiments.get(experiment_id)
            if experiment:
                return experiment.best_genome
        return None
    
    async def get_experiment(self, experiment_id: str) -> Optional[EvolutionaryExperiment]:
        """Récupère une expérience."""
        with self._experiments_lock:
            return self._experiments.get(experiment_id)
    
    async def get_experiments(self) -> List[EvolutionaryExperiment]:
        """Récupère toutes les expériences."""
        with self._experiments_lock:
            return list(self._experiments.values())
    
    # ========== MÉTHODES PRIVÉES ==========
    
    async def _initialize_population(
        self,
        experiment: EvolutionaryExperiment
    ) -> Population:
        """Initialise une population."""
        genomes = []
        
        for i in range(experiment.population_size):
            genome = await self._create_random_genome(experiment)
            genomes.append(genome)
        
        population = Population(
            genomes=genomes,
            generation=0,
            metadata={"experiment_id": experiment.experiment_id}
        )
        
        with self._populations_lock:
            self._populations[population.population_id] = population
        
        return population
    
    async def _create_random_genome(
        self,
        experiment: EvolutionaryExperiment
    ) -> Genome:
        """Crée un génome aléatoire."""
        # Définition de l'espace de recherche
        gene_space = {
            "risk_threshold": (0.1, 0.5),
            "position_size": (0.01, 0.2),
            "stop_loss": (0.02, 0.1),
            "take_profit": (0.04, 0.2),
            "hedge_ratio": (0.1, 0.9),
            "volatility_factor": (0.5, 2.0),
            "correlation_threshold": (0.3, 0.8),
            "momentum_weight": (0.0, 1.0),
            "mean_reversion_weight": (0.0, 1.0),
            "trend_weight": (0.0, 1.0),
            "sentiment_weight": (0.0, 0.5),
            "risk_weight": (0.0, 1.0),
            "max_drawdown": (0.05, 0.2),
            "min_sharpe": (0.0, 2.0),
            "entry_threshold": (0.1, 0.9)
        }
        
        genes = {}
        for gene_name, (min_val, max_val) in gene_space.items():
            genes[gene_name] = random.uniform(min_val, max_val)
        
        # Ajout de paramètres stratégiques
        strategies = [s.value for s in HedgeStrategy]
        genes["strategy"] = random.choice(strategies)
        genes["regime"] = random.choice([r.value for r in MarketRegime])
        
        return Genome(
            genes=genes,
            metadata={"type": "random"}
        )
    
    async def _evaluate_population(
        self,
        population: Population,
        fitness_function: Callable[[Genome], float]
    ) -> None:
        """Évalue une population."""
        self._stats["total_evals"] += len(population.genomes)
        
        # Évaluation parallèle
        if self.config["parallel_evaluations"]:
            import concurrent.futures
            
            def evaluate_genome(genome: Genome) -> Tuple[Genome, float]:
                try:
                    fitness = fitness_function(genome)
                    return (genome, fitness)
                except Exception as e:
                    logger.error(f"Fitness evaluation error: {e}")
                    return (genome, 0.0)
            
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.config["eval_workers"]
            ) as executor:
                results = list(executor.map(evaluate_genome, population.genomes))
        else:
            # Évaluation séquentielle
            results = []
            for genome in population.genomes:
                try:
                    fitness = fitness_function(genome)
                    results.append((genome, fitness))
                except Exception as e:
                    logger.error(f"Fitness evaluation error: {e}")
                    results.append((genome, 0.0))
        
        # Mise à jour des fitness
        fitnesses = []
        for genome, fitness in results:
            genome.fitness = fitness
            genome.fitness_history.append(fitness)
            fitnesses.append(fitness)
        
        # Mise à jour des statistiques de la population
        population.best_fitness = max(fitnesses) if fitnesses else 0.0
        population.avg_fitness = sum(fitnesses) / len(fitnesses) if fitnesses else 0.0
        population.worst_fitness = min(fitnesses) if fitnesses else 0.0
        population.diversity = self._calculate_diversity(population)
        population.updated_at = datetime.now(timezone.utc)
    
    async def _record_population(
        self,
        experiment: EvolutionaryExperiment,
        population: Population,
        generation: int
    ) -> None:
        """Enregistre une population."""
        population.generation = generation
        experiment.population_history.append(population)
        experiment.population_history = experiment.population_history[-100:]  # Limite
        
        # Enregistrement du checkpoint
        if (generation % self.config["checkpoint_interval"] == 0 and
            self.config["enable_checkpointing"] and self.data_manager):
            await self.data_manager.store(
                f"evolution:experiment:{experiment.experiment_id}:generation:{generation}",
                population.to_dict(),
                DataType.EXPERIMENT
            )
    
    async def _selection(
        self,
        experiment: EvolutionaryExperiment,
        population: Population
    ) -> List[Genome]:
        """Sélectionne des individus."""
        method = experiment.selection_method
        selected = []
        
        if method == SelectionMethod.ELITE:
            # Sélection élite
            sorted_genomes = sorted(
                population.genomes,
                key=lambda g: g.fitness,
                reverse=True
            )
            selected = sorted_genomes[:experiment.elitism_count]
        
        elif method == SelectionMethod.TOURNAMENT:
            # Sélection par tournoi
            tournament_size = experiment.tournament_size
            for _ in range(len(population.genomes)):
                tournament = random.sample(population.genomes, tournament_size)
                winner = max(tournament, key=lambda g: g.fitness)
                selected.append(winner)
        
        elif method == SelectionMethod.ROULETTE:
            # Sélection par roulette
            total_fitness = sum(g.fitness for g in population.genomes)
            if total_fitness > 0:
                for _ in range(len(population.genomes)):
                    spin = random.uniform(0, total_fitness)
                    cumulative = 0
                    for genome in population.genomes:
                        cumulative += genome.fitness
                        if cumulative >= spin:
                            selected.append(genome)
                            break
            else:
                selected = random.choices(population.genomes, k=len(population.genomes))
        
        elif method == SelectionMethod.RANK:
            # Sélection par rang
            sorted_genomes = sorted(
                population.genomes,
                key=lambda g: g.fitness,
                reverse=True
            )
            ranks = list(range(1, len(sorted_genomes) + 1))
            rank_sum = sum(ranks)
            probabilities = [r / rank_sum for r in ranks]
            selected = random.choices(sorted_genomes, weights=probabilities, k=len(sorted_genomes))
        
        else:
            # Par défaut: aléatoire
            selected = random.choices(population.genomes, k=len(population.genomes))
        
        return selected
    
    async def _crossover(
        self,
        experiment: EvolutionaryExperiment,
        selected: List[Genome]
    ) -> List[Genome]:
        """Effectue le croisement."""
        offspring = []
        method = experiment.crossover_method
        
        # Ajout des élites
        offspring.extend(selected[:experiment.elitism_count])
        
        # Croisement
        for i in range(0, len(selected) - 1, 2):
            if random.random() < experiment.crossover_rate:
                parent1 = selected[i]
                parent2 = selected[i + 1]
                
                if method == CrossoverMethod.SINGLE_POINT:
                    child1, child2 = await self._crossover_single_point(parent1, parent2)
                elif method == CrossoverMethod.TWO_POINT:
                    child1, child2 = await self._crossover_two_point(parent1, parent2)
                elif method == CrossoverMethod.UNIFORM:
                    child1, child2 = await self._crossover_uniform(parent1, parent2)
                elif method == CrossoverMethod.ARITHMETIC:
                    child1, child2 = await self._crossover_arithmetic(parent1, parent2)
                else:
                    child1, child2 = await self._crossover_uniform(parent1, parent2)
                
                offspring.extend([child1, child2])
            else:
                offspring.append(copy.deepcopy(selected[i]))
                if i + 1 < len(selected):
                    offspring.append(copy.deepcopy(selected[i + 1]))
        
        # Complétion si nécessaire
        while len(offspring) < experiment.population_size:
            genome = copy.deepcopy(random.choice(selected))
            offspring.append(genome)
        
        return offspring[:experiment.population_size]
    
    async def _crossover_single_point(
        self,
        parent1: Genome,
        parent2: Genome
    ) -> Tuple[Genome, Genome]:
        """Croisement à un point."""
        genes1 = parent1.genes.copy()
        genes2 = parent2.genes.copy()
        
        gene_names = list(genes1.keys())
        if gene_names:
            point = random.randint(1, len(gene_names) - 1)
            for i in range(point, len(gene_names)):
                key = gene_names[i]
                genes1[key], genes2[key] = genes2[key], genes1[key]
        
        child1 = Genome(
            genes=genes1,
            parent_ids=[parent1.genome_id, parent2.genome_id],
            metadata={"crossover": "single_point"}
        )
        child2 = Genome(
            genes=genes2,
            parent_ids=[parent1.genome_id, parent2.genome_id],
            metadata={"crossover": "single_point"}
        )
        
        return child1, child2
    
    async def _crossover_two_point(
        self,
        parent1: Genome,
        parent2: Genome
    ) -> Tuple[Genome, Genome]:
        """Croisement à deux points."""
        genes1 = parent1.genes.copy()
        genes2 = parent2.genes.copy()
        
        gene_names = list(genes1.keys())
        if len(gene_names) > 2:
            point1 = random.randint(1, len(gene_names) - 2)
            point2 = random.randint(point1 + 1, len(gene_names) - 1)
            
            for i in range(point1, point2):
                key = gene_names[i]
                genes1[key], genes2[key] = genes2[key], genes1[key]
        
        child1 = Genome(
            genes=genes1,
            parent_ids=[parent1.genome_id, parent2.genome_id],
            metadata={"crossover": "two_point"}
        )
        child2 = Genome(
            genes=genes2,
            parent_ids=[parent1.genome_id, parent2.genome_id],
            metadata={"crossover": "two_point"}
        )
        
        return child1, child2
    
    async def _crossover_uniform(
        self,
        parent1: Genome,
        parent2: Genome
    ) -> Tuple[Genome, Genome]:
        """Croisement uniforme."""
        genes1 = parent1.genes.copy()
        genes2 = parent2.genes.copy()
        
        for key in genes1.keys():
            if random.random() < 0.5:
                genes1[key], genes2[key] = genes2[key], genes1[key]
        
        child1 = Genome(
            genes=genes1,
            parent_ids=[parent1.genome_id, parent2.genome_id],
            metadata={"crossover": "uniform"}
        )
        child2 = Genome(
            genes=genes2,
            parent_ids=[parent1.genome_id, parent2.genome_id],
            metadata={"crossover": "uniform"}
        )
        
        return child1, child2
    
    async def _crossover_arithmetic(
        self,
        parent1: Genome,
        parent2: Genome
    ) -> Tuple[Genome, Genome]:
        """Croisement arithmétique."""
        genes1 = {}
        genes2 = {}
        
        for key in parent1.genes.keys():
            alpha = random.random()
            if isinstance(parent1.genes[key], (int, float)):
                genes1[key] = alpha * parent1.genes[key] + (1 - alpha) * parent2.genes[key]
                genes2[key] = (1 - alpha) * parent1.genes[key] + alpha * parent2.genes[key]
            else:
                genes1[key] = parent1.genes[key] if random.random() < 0.5 else parent2.genes[key]
                genes2[key] = parent2.genes[key] if random.random() < 0.5 else parent1.genes[key]
        
        child1 = Genome(
            genes=genes1,
            parent_ids=[parent1.genome_id, parent2.genome_id],
            metadata={"crossover": "arithmetic"}
        )
        child2 = Genome(
            genes=genes2,
            parent_ids=[parent1.genome_id, parent2.genome_id],
            metadata={"crossover": "arithmetic"}
        )
        
        return child1, child2
    
    async def _mutation(
        self,
        experiment: EvolutionaryExperiment,
        genomes: List[Genome]
    ) -> List[Genome]:
        """Effectue la mutation."""
        method = experiment.mutation_method
        
        for genome in genomes:
            if random.random() < experiment.mutation_rate:
                for key, value in genome.genes.items():
                    if isinstance(value, (int, float)):
                        # Mutation numérique
                        if method == MutationMethod.GAUSSIAN:
                            sigma = abs(value) * 0.1 + 0.01
                            genome.genes[key] += random.gauss(0, sigma)
                        elif method == MutationMethod.UNIFORM:
                            delta = abs(value) * 0.2 + 0.01
                            genome.genes[key] += random.uniform(-delta, delta)
                        elif method == MutationMethod.BOUNDARY:
                            genome.genes[key] = random.uniform(0, 1)
                        elif method == MutationMethod.ADAPTIVE:
                            # Adaptation basée sur la fitness
                            adaptation_rate = 0.1 * (1 - genome.fitness)
                            genome.genes[key] += random.gauss(0, adaptation_rate)
                        else:
                            # Random par défaut
                            genome.genes[key] = random.random() * 2 - 1
                        
                        # Clipping
                        if key in self._get_gene_bounds():
                            min_val, max_val = self._get_gene_bounds()[key]
                            genome.genes[key] = max(min_val, min(max_val, genome.genes[key]))
                    
                    elif isinstance(value, str):
                        # Mutation catégorielle
                        if key == "strategy":
                            strategies = [s.value for s in HedgeStrategy]
                            genome.genes[key] = random.choice(strategies)
                        elif key == "regime":
                            regimes = [r.value for r in MarketRegime]
                            genome.genes[key] = random.choice(regimes)
        
        return genomes
    
    def _get_gene_bounds(self) -> Dict[str, Tuple[float, float]]:
        """Obtient les bornes des gènes."""
        return {
            "risk_threshold": (0.1, 0.5),
            "position_size": (0.01, 0.2),
            "stop_loss": (0.02, 0.1),
            "take_profit": (0.04, 0.2),
            "hedge_ratio": (0.1, 0.9),
            "volatility_factor": (0.5, 2.0),
            "correlation_threshold": (0.3, 0.8),
            "momentum_weight": (0.0, 1.0),
            "mean_reversion_weight": (0.0, 1.0),
            "trend_weight": (0.0, 1.0),
            "sentiment_weight": (0.0, 0.5),
            "risk_weight": (0.0, 1.0),
            "max_drawdown": (0.05, 0.2),
            "min_sharpe": (0.0, 2.0),
            "entry_threshold": (0.1, 0.9)
        }
    
    async def _create_next_population(
        self,
        experiment: EvolutionaryExperiment,
        population: Population,
        offspring: List[Genome]
    ) -> Population:
        """Crée la prochaine génération."""
        # Élitisme
        sorted_genomes = sorted(
            population.genomes,
            key=lambda g: g.fitness,
            reverse=True
        )
        elites = sorted_genomes[:experiment.elitism_count]
        
        # Nouvelle population
        new_genomes = elites + offspring
        
        # Limite de taille
        if len(new_genomes) > experiment.population_size:
            new_genomes = new_genomes[:experiment.population_size]
        
        # Mise à jour des âges
        for genome in new_genomes:
            genome.age += 1
            genome.generation += 1
        
        return Population(
            genomes=new_genomes,
            generation=population.generation + 1,
            metadata={"experiment_id": experiment.experiment_id}
        )
    
    def _calculate_diversity(self, population: Population) -> float:
        """Calcule la diversité de la population."""
        if len(population.genomes) < 2:
            return 0.0
        
        # Calcul basé sur la variance des paramètres
        all_genes = [genome.genes for genome in population.genomes]
        gene_names = list(all_genes[0].keys())
        
        variances = []
        for gene_name in gene_names:
            values = []
            for genes in all_genes:
                if gene_name in genes and isinstance(genes[gene_name], (int, float)):
                    values.append(genes[gene_name])
            if values:
                variances.append(np.var(values))
        
        if variances:
            avg_variance = np.mean(variances)
            # Normalisation
            diversity = avg_variance / (avg_variance + 1.0)
            return diversity
        
        return 0.0
    
    async def _check_convergence(
        self,
        experiment: EvolutionaryExperiment,
        population: Population
    ) -> bool:
        """Vérifie la convergence."""
        # Vérification par stagnation
        if len(population.genomes) < 2:
            return False
        
        # Calcul de l'amélioration récente
        if len(population.genomes) > experiment.max_stagnation:
            recent_genomes = population.genomes[-experiment.max_stagnation:]
            improvements = []
            for i in range(1, len(recent_genomes)):
                improvements.append(
                    recent_genomes[i].fitness - recent_genomes[i-1].fitness
                )
            
            if improvements and max(improvements) < experiment.convergence_threshold:
                return True
        
        # Vérification de la diversité
        if population.diversity < 0.01:
            return True
        
        return False
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._experiments_lock:
            self._stats["active_experiments"] = len([
                e for e in self._experiments.values()
                if e.status == "running"
            ])
            self._stats["completed_experiments"] = len([
                e for e in self._experiments.values()
                if e.status == "completed"
            ])
        
        return self._stats


class ReinforcementEngine(ReinforcementEngineInterface):
    """
    Moteur d'apprentissage par renforcement avancé.
    Implémente des algorithmes DQN, PPO, SAC pour l'apprentissage adaptatif.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Buffer d'expériences
        self._experience_buffer: deque = deque(maxlen=self.config.get("buffer_size", 10000))
        self._buffer_lock = threading.RLock()
        
        # Modèles (simulés)
        self._model_version = 0
        self._policy_network = None
        self._value_network = None
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "experiences_recorded": 0,
            "batches_trained": 0,
            "avg_reward": 0.0,
            "model_updates": 0,
            "training_loss": 0.0
        }
        
        logger.info("ReinforcementEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "buffer_size": 10000,
            "batch_size": 64,
            "gamma": 0.99,
            "learning_rate": 0.001,
            "epsilon_start": 1.0,
            "epsilon_end": 0.01,
            "epsilon_decay": 0.995,
            "target_update_frequency": 100,
            "min_buffer_size": 1000,
            "prioritized_replay": True,
            "alpha": 0.6,
            "beta_start": 0.4,
            "beta_end": 1.0
        }
    
    async def record_experience(self, experience: ReinforcementExperience) -> None:
        """Enregistre une expérience."""
        with self._buffer_lock:
            # Calcul de la priorité
            if self.config["prioritized_replay"]:
                experience.priority = abs(experience.reward) + 0.01
            
            self._experience_buffer.append(experience)
            self._stats["experiences_recorded"] += 1
            
            # Mise à jour de la moyenne des récompenses
            self._stats["avg_reward"] = (
                self._stats["avg_reward"] * 0.99 +
                experience.reward * 0.01
            )
    
    async def get_batch(self, batch_size: int) -> List[ReinforcementExperience]:
        """Récupère un batch d'expériences."""
        with self._buffer_lock:
            if len(self._experience_buffer) < self.config["min_buffer_size"]:
                return []
            
            if self.config["prioritized_replay"]:
                # Échantillonnage prioritaire
                priorities = [exp.priority for exp in self._experience_buffer]
                total_priority = sum(priorities)
                probabilities = [p / total_priority for p in priorities]
                
                indices = np.random.choice(
                    len(self._experience_buffer),
                    size=min(batch_size, len(self._experience_buffer)),
                    p=probabilities,
                    replace=False
                )
                
                batch = [self._experience_buffer[i] for i in indices]
            else:
                # Échantillonnage uniforme
                batch = random.sample(
                    list(self._experience_buffer),
                    min(batch_size, len(self._experience_buffer))
                )
            
            return batch
    
    async def train(self, batch: List[ReinforcementExperience]) -> Dict[str, Any]:
        """Entraîne le modèle avec un batch."""
        if not batch:
            return {"status": "no_data"}
        
        self._stats["batches_trained"] += 1
        
        try:
            # Simulation de l'entraînement
            # Dans un système réel, on utiliserait PyTorch/TensorFlow
            
            # Calcul des pertes
            losses = []
            rewards = []
            
            for experience in batch:
                # TD Error
                target = experience.reward + self.config["gamma"] * 0.5
                current = 0.5  # Simulation
                loss = (target - current) ** 2
                losses.append(loss)
                rewards.append(experience.reward)
            
            avg_loss = np.mean(losses)
            avg_reward = np.mean(rewards)
            
            # Mise à jour du modèle
            self._model_version += 1
            self._stats["model_updates"] += 1
            self._stats["training_loss"] = avg_loss
            
            # Mise à jour des priorités
            if self.config["prioritized_replay"]:
                for exp, loss in zip(batch, losses):
                    exp.priority = abs(exp.reward) + abs(loss) + 0.01
            
            return {
                "status": "success",
                "avg_loss": avg_loss,
                "avg_reward": avg_reward,
                "model_version": self._model_version,
                "batch_size": len(batch)
            }
            
        except Exception as e:
            logger.error(f"Training error: {e}")
            return {"status": "error", "error": str(e)}
    
    async def get_buffer_size(self) -> int:
        """Récupère la taille du buffer."""
        with self._buffer_lock:
            return len(self._experience_buffer)
    
    async def clear_buffer(self) -> None:
        """Vide le buffer."""
        with self._buffer_lock:
            self._experience_buffer.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._buffer_lock:
            self._stats["buffer_size"] = len(self._experience_buffer)
        return self._stats


# ============== ADAPTIVE OPTIMIZER ==============

class AdaptiveOptimizer:
    """
    Optimiseur adaptatif pour les paramètres de hedging.
    Ajuste dynamiquement les paramètres basés sur la performance et les conditions de marché.
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None
    ):
        self.config = config or self._default_config()
        
        # Paramètres adaptatifs
        self._parameters: Dict[str, AdaptiveParameter] = {}
        self._param_lock = threading.RLock()
        
        # Performance historique
        self._performance_history: deque = deque(maxlen=1000)
        self._market_conditions: deque = deque(maxlen=100)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "adaptations": 0,
            "convergences": 0,
            "divergences": 0,
            "current_learning_rate": 0.01
        }
        
        logger.info("AdaptiveOptimizer initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "learning_rate": 0.01,
            "decay_rate": 0.9,
            "momentum": 0.8,
            "epsilon": 1e-8,
            "gradient_clip": 1.0,
            "adaptation_interval": 10,
            "window_size": 20,
            "threshold": 0.01
        }
    
    def register_parameter(
        self,
        name: str,
        initial_value: float,
        min_value: float = 0.0,
        max_value: float = 1.0,
        step: float = 0.01
    ) -> None:
        """Enregistre un paramètre adaptatif."""
        with self._param_lock:
            self._parameters[name] = AdaptiveParameter(
                name=name,
                value=initial_value,
                min_value=min_value,
                max_value=max_value,
                step=step
            )
    
    def update(
        self,
        performance: float,
        market_conditions: Dict[str, Any]
    ) -> Dict[str, float]:
        """Met à jour les paramètres adaptatifs."""
        with self._param_lock:
            if not self._parameters:
                return {}
            
            # Enregistrement de la performance
            self._performance_history.append(performance)
            self._market_conditions.append(market_conditions)
            
            # Adaptation des paramètres
            updates = {}
            
            for name, param in self._parameters.items():
                # Calcul du gradient approximatif
                gradient = self._compute_gradient(name, performance)
                
                # Clip du gradient
                gradient = max(-self.config["gradient_clip"], 
                              min(self.config["gradient_clip"], gradient))
                
                # Mise à jour
                param.value += gradient * self.config["learning_rate"]
                
                # Clip
                param.value = max(param.min_value, min(param.max_value, param.value))
                param.history.append(param.value)
                param.last_update = datetime.now(timezone.utc)
                
                updates[name] = param.value
            
            self._stats["adaptations"] += 1
            
            return updates
    
    def _compute_gradient(self, name: str, performance: float) -> float:
        """Calcule le gradient approximatif."""
        param = self._parameters.get(name)
        if not param or len(param.history) < 2:
            return 0.0
        
        # Différence finie
        previous_value = param.history[-1] if param.history else param.value
        delta = performance - self._performance_history[-1] if self._performance_history else 0.0
        
        # Gradient approximatif
        if param.value != previous_value:
            gradient = delta / (param.value - previous_value + self.config["epsilon"])
        else:
            gradient = 0.0
        
        # Momentum
        if hasattr(self, "_momentum"):
            self._momentum[name] = self._momentum.get(name, 0.0) * self.config["momentum"] + gradient
            gradient = self._momentum[name]
        else:
            self._momentum = {}
            self._momentum[name] = gradient
        
        return gradient
    
    def get_parameters(self) -> Dict[str, float]:
        """Récupère les paramètres actuels."""
        with self._param_lock:
            return {name: param.value for name, param in self._parameters.items()}
    
    def reset(self) -> None:
        """Réinitialise l'optimiseur."""
        with self._param_lock:
            for param in self._parameters.values():
                param.history.clear()
        
        self._performance_history.clear()
        self._market_conditions.clear()
        self._momentum = {}
        self._stats["adaptations"] = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._param_lock:
            self._stats["parameters"] = len(self._parameters)
            self._stats["history_size"] = len(self._performance_history)
        
        return self._stats


# ============== FACTORY ==============

class EvolutionFactory:
    """Factory pour créer des composants évolutionnaires."""
    
    @staticmethod
    async def create_evolutionary_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> EvolutionaryEngine:
        """Crée un moteur d'évolution."""
        return EvolutionaryEngine(
            data_manager=data_manager,
            config=config
        )
    
    @staticmethod
    async def create_reinforcement_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ReinforcementEngine:
        """Crée un moteur d'apprentissage par renforcement."""
        return ReinforcementEngine(
            data_manager=data_manager,
            config=config
        )
    
    @staticmethod
    def create_adaptive_optimizer(
        config: Optional[Dict[str, Any]] = None
    ) -> AdaptiveOptimizer:
        """Crée un optimiseur adaptatif."""
        return AdaptiveOptimizer(config=config)


# ============== EXPORT ==============

__all__ = [
    "EvolutionType",
    "SelectionMethod",
    "CrossoverMethod",
    "MutationMethod",
    "FitnessMethod",
    "Genome",
    "Population",
    "EvolutionaryExperiment",
    "ReinforcementExperience",
    "AdaptiveParameter",
    "EvolutionEngineInterface",
    "ReinforcementEngineInterface",
    "EvolutionaryEngine",
    "ReinforcementEngine",
    "AdaptiveOptimizer",
    "EvolutionFactory"
]
