
# ai/optimization/genetic_algorithm.py
"""
NEXUS AI TRADING SYSTEM - Genetic Algorithm for Hyperparameter Optimization
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import random
import warnings
warnings.filterwarnings('ignore')

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class GeneticAlgorithmConfig:
    """Configuration pour l'algorithme génétique"""
    population_size: int = 50
    n_generations: int = 100
    mutation_rate: float = 0.1
    crossover_rate: float = 0.8
    elitism_rate: float = 0.1
    selection_method: str = 'tournament'  # 'tournament', 'roulette', 'rank'
    tournament_size: int = 3
    mutation_method: str = 'gaussian'  # 'gaussian', 'uniform', 'bit_flip'
    crossover_method: str = 'uniform'  # 'uniform', 'single_point', 'two_point'
    n_jobs: int = -1
    random_state: Optional[int] = 42
    verbose: bool = False
    early_stopping: bool = True
    patience: int = 20
    elitism: bool = True

    def __post_init__(self):
        if self.population_size <= 0:
            raise ValueError("population_size doit être > 0")
        if self.n_generations <= 0:
            raise ValueError("n_generations doit être > 0")
        if self.mutation_rate < 0 or self.mutation_rate > 1:
            raise ValueError("mutation_rate doit être entre 0 et 1")
        if self.crossover_rate < 0 or self.crossover_rate > 1:
            raise ValueError("crossover_rate doit être entre 0 et 1")
        if self.elitism_rate < 0 or self.elitism_rate > 1:
            raise ValueError("elitism_rate doit être entre 0 et 1")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'population_size': self.population_size,
            'n_generations': self.n_generations,
            'mutation_rate': self.mutation_rate,
            'crossover_rate': self.crossover_rate,
            'elitism_rate': self.elitism_rate,
            'selection_method': self.selection_method,
            'tournament_size': self.tournament_size,
            'mutation_method': self.mutation_method,
            'crossover_method': self.crossover_method,
            'n_jobs': self.n_jobs,
            'random_state': self.random_state,
            'verbose': self.verbose,
            'early_stopping': self.early_stopping,
            'patience': self.patience,
            'elitism': self.elitism,
        }


@dataclass
class Individual:
    """Individu de la population"""
    genes: np.ndarray
    fitness: Optional[float] = None
    age: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'genes': self.genes.tolist() if isinstance(self.genes, np.ndarray) else self.genes,
            'fitness': self.fitness,
            'age': self.age,
        }


class GeneticAlgorithm:
    """
    Algorithme génétique pour l'optimisation des hyperparamètres.

    Features:
    - Multiples méthodes de sélection (tournament, roulette, rank)
    - Multiples méthodes de crossover (uniform, single_point, two_point)
    - Multiples méthodes de mutation (gaussian, uniform, bit_flip)
    - Élitisme
    - Arrêt précoce
    - Historique complet
    - Parallélisation

    Example:
        ```python
        def objective(params):
            return -sum(p**2 for p in params)

        config = GeneticAlgorithmConfig(
            population_size=50,
            n_generations=100,
            mutation_rate=0.1,
            crossover_rate=0.8
        )
        ga = GeneticAlgorithm(config)

        # Définir les bornes
        bounds = [(-5, 5), (-5, 5)]

        # Optimiser
        best_params, best_fitness = ga.optimize(
            objective,
            bounds,
            dimensions=['x1', 'x2']
        )
        ```
    """

    def __init__(self, config: Optional[GeneticAlgorithmConfig] = None):
        self.config = config or GeneticAlgorithmConfig()
        self.population: List[Individual] = []
        self.best_individual: Optional[Individual] = None
        self.history: List[Dict[str, Any]] = []
        self.dimensions: List[str] = []
        self.bounds: List[Tuple[float, float]] = []
        self.is_fitted = False

        # Initialisation du générateur aléatoire
        if self.config.random_state is not None:
            random.seed(self.config.random_state)
            np.random.seed(self.config.random_state)

        logger.info(f"GeneticAlgorithm initialisé")

    def _initialize_population(self, bounds: List[Tuple[float, float]]) -> List[Individual]:
        """Initialise la population aléatoirement"""
        population = []
        for _ in range(self.config.population_size):
            genes = np.array([random.uniform(low, high) for low, high in bounds])
            population.append(Individual(genes=genes))
        return population

    def _evaluate_individual(self, individual: Individual, objective: Callable) -> float:
        """Évalue un individu"""
        try:
            fitness = objective(individual.genes)
            individual.fitness = fitness
            return fitness
        except Exception as e:
            logger.debug(f"Erreur d'évaluation: {e}")
            individual.fitness = float('inf')
            return float('inf')

    def _evaluate_population(self, population: List[Individual], objective: Callable) -> List[Individual]:
        """Évalue toute la population"""
        for individual in population:
            self._evaluate_individual(individual, objective)
        return population

    def _select_parents(self, population: List[Individual]) -> Tuple[Individual, Individual]:
        """
        Sélectionne deux parents selon la méthode configurée.

        Returns:
            Tuple[Individual, Individual]: Deux parents
        """
        if self.config.selection_method == 'tournament':
            return self._tournament_selection(population)
        elif self.config.selection_method == 'roulette':
            return self._roulette_selection(population)
        elif self.config.selection_method == 'rank':
            return self._rank_selection(population)
        else:
            raise ValueError(f"Méthode de sélection non supportée: {self.config.selection_method}")

    def _tournament_selection(self, population: List[Individual]) -> Tuple[Individual, Individual]:
        """Sélection par tournoi"""
        parents = []
        for _ in range(2):
            tournament = random.sample(population, self.config.tournament_size)
            winner = min(tournament, key=lambda x: x.fitness)
            parents.append(winner)
        return parents[0], parents[1]

    def _roulette_selection(self, population: List[Individual]) -> Tuple[Individual, Individual]:
        """Sélection par roulette (pour minimisation)"""
        fitnesses = np.array([1 / (ind.fitness + 1e-9) for ind in population])
        probabilities = fitnesses / fitnesses.sum()
        parents = np.random.choice(population, size=2, p=probabilities)
        return parents[0], parents[1]

    def _rank_selection(self, population: List[Individual]) -> Tuple[Individual, Individual]:
        """Sélection par rang"""
        sorted_pop = sorted(population, key=lambda x: x.fitness)
        ranks = np.arange(len(sorted_pop), 0, -1)
        probabilities = ranks / ranks.sum()
        parents = np.random.choice(sorted_pop, size=2, p=probabilities)
        return parents[0], parents[1]

    def _crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """
        Effectue un crossover entre deux parents.

        Returns:
            Tuple[Individual, Individual]: Deux enfants
        """
        if random.random() > self.config.crossover_rate:
            return parent1, parent2

        if self.config.crossover_method == 'uniform':
            return self._uniform_crossover(parent1, parent2)
        elif self.config.crossover_method == 'single_point':
            return self._single_point_crossover(parent1, parent2)
        elif self.config.crossover_method == 'two_point':
            return self._two_point_crossover(parent1, parent2)
        else:
            raise ValueError(f"Méthode de crossover non supportée: {self.config.crossover_method}")

    def _uniform_crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """Crossover uniforme"""
        child1_genes = np.array([
            p1 if random.random() < 0.5 else p2
            for p1, p2 in zip(parent1.genes, parent2.genes)
        ])
        child2_genes = np.array([
            p2 if random.random() < 0.5 else p1
            for p1, p2 in zip(parent1.genes, parent2.genes)
        ])
        return Individual(genes=child1_genes), Individual(genes=child2_genes)

    def _single_point_crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """Crossover à un point"""
        point = random.randint(1, len(parent1.genes) - 1)
        child1_genes = np.concatenate([parent1.genes[:point], parent2.genes[point:]])
        child2_genes = np.concatenate([parent2.genes[:point], parent1.genes[point:]])
        return Individual(genes=child1_genes), Individual(genes=child2_genes)

    def _two_point_crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """Crossover à deux points"""
        point1 = random.randint(1, len(parent1.genes) - 2)
        point2 = random.randint(point1 + 1, len(parent1.genes) - 1)
        child1_genes = np.concatenate([
            parent1.genes[:point1],
            parent2.genes[point1:point2],
            parent1.genes[point2:]
        ])
        child2_genes = np.concatenate([
            parent2.genes[:point1],
            parent1.genes[point1:point2],
            parent2.genes[point2:]
        ])
        return Individual(genes=child1_genes), Individual(genes=child2_genes)

    def _mutate(self, individual: Individual, bounds: List[Tuple[float, float]]) -> Individual:
        """
        Mutate un individu.

        Args:
            individual: Individu à muter
            bounds: Bornes des paramètres

        Returns:
            Individual: Individu muté
        """
        if random.random() > self.config.mutation_rate:
            return individual

        new_genes = individual.genes.copy()

        if self.config.mutation_method == 'gaussian':
            for i in range(len(new_genes)):
                if random.random() < self.config.mutation_rate:
                    low, high = bounds[i]
                    std = (high - low) * 0.1
                    new_genes[i] = new_genes[i] + random.gauss(0, std)
                    new_genes[i] = np.clip(new_genes[i], low, high)

        elif self.config.mutation_method == 'uniform':
            for i in range(len(new_genes)):
                if random.random() < self.config.mutation_rate:
                    low, high = bounds[i]
                    new_genes[i] = random.uniform(low, high)

        elif self.config.mutation_method == 'bit_flip':
            for i in range(len(new_genes)):
                if random.random() < self.config.mutation_rate:
                    # Pour valeurs continues, inversion symétrique
                    low, high = bounds[i]
                    mid = (low + high) / 2
                    new_genes[i] = 2 * mid - new_genes[i]

        else:
            raise ValueError(f"Méthode de mutation non supportée: {self.config.mutation_method}")

        return Individual(genes=new_genes)

    def _create_next_generation(
        self,
        population: List[Individual],
        objective: Callable,
        bounds: List[Tuple[float, float]]
    ) -> List[Individual]:
        """
        Crée la génération suivante.

        Returns:
            List[Individual]: Nouvelle population
        """
        next_population = []

        # Élitisme
        if self.config.elitism:
            n_elites = int(len(population) * self.config.elitism_rate)
            elites = sorted(population, key=lambda x: x.fitness)[:n_elites]
            next_population.extend(elites)

        # Création de nouveaux individus
        while len(next_population) < self.config.population_size:
            parent1, parent2 = self._select_parents(population)

            # Crossover
            child1, child2 = self._crossover(parent1, parent2)

            # Mutation
            child1 = self._mutate(child1, bounds)
            child2 = self._mutate(child2, bounds)

            # Évaluation
            self._evaluate_individual(child1, objective)
            self._evaluate_individual(child2, objective)

            next_population.append(child1)
            if len(next_population) < self.config.population_size:
                next_population.append(child2)

        return next_population

    def optimize(
        self,
        objective: Callable,
        bounds: List[Tuple[float, float]],
        dimensions: Optional[List[str]] = None,
        **kwargs
    ) -> Tuple[np.ndarray, float]:
        """
        Effectue l'optimisation par algorithme génétique.

        Args:
            objective: Fonction objectif (à minimiser)
            bounds: Bornes des paramètres
            dimensions: Noms des dimensions (optionnel)
            **kwargs: Arguments supplémentaires

        Returns:
            Tuple[np.ndarray, float]: (Meilleurs paramètres, Meilleure valeur)
        """
        self.bounds = bounds
        self.dimensions = dimensions or [f'x{i}' for i in range(len(bounds))]

        # Initialisation
        self.population = self._initialize_population(bounds)
        self.population = self._evaluate_population(self.population, objective)

        # Meilleur individu initial
        self.best_individual = min(self.population, key=lambda x: x.fitness)
        best_fitness = self.best_individual.fitness

        # Historique
        self.history = []
        self.history.append({
            'generation': 0,
            'best_fitness': best_fitness,
            'mean_fitness': np.mean([ind.fitness for ind in self.population]),
            'std_fitness': np.std([ind.fitness for ind in self.population]),
            'best_params': dict(zip(self.dimensions, self.best_individual.genes)),
        })

        if self.config.verbose:
            logger.info(f"Generation 0: Best Fitness = {best_fitness:.6f}")

        # Boucle d'optimisation
        patience_counter = 0
        previous_best = best_fitness

        for generation in range(1, self.config.n_generations + 1):
            # Création de la génération suivante
            self.population = self._create_next_generation(
                self.population,
                objective,
                bounds
            )

            # Meilleur individu
            current_best = min(self.population, key=lambda x: x.fitness)

            if current_best.fitness < self.best_individual.fitness:
                self.best_individual = current_best
                best_fitness = current_best.fitness
                patience_counter = 0

                if self.config.verbose:
                    logger.info(f"Generation {generation}: New Best = {best_fitness:.6f}")
            else:
                patience_counter += 1

            # Historique
            self.history.append({
                'generation': generation,
                'best_fitness': self.best_individual.fitness,
                'mean_fitness': np.mean([ind.fitness for ind in self.population]),
                'std_fitness': np.std([ind.fitness for ind in self.population]),
                'best_params': dict(zip(self.dimensions, self.best_individual.genes)),
            })

            # Arrêt précoce
            if self.config.early_stopping and patience_counter >= self.config.patience:
                if self.config.verbose:
                    logger.info(f"Arrêt précoce à la génération {generation}")
                break

        self.is_fitted = True

        return self.best_individual.genes, self.best_individual.fitness

    def get_history(self) -> pd.DataFrame:
        """
        Retourne l'historique de l'optimisation.

        Returns:
            pd.DataFrame: Historique
        """
        return pd.DataFrame(self.history)

    def get_best_params(self) -> Dict[str, Any]:
        """
        Retourne les meilleurs paramètres.

        Returns:
            Dict[str, Any]: Meilleurs paramètres
        """
        if self.best_individual is None:
            return {}
        return dict(zip(self.dimensions, self.best_individual.genes))

    def get_best_fitness(self) -> Optional[float]:
        """Retourne la meilleure valeur de fitness"""
        if self.best_individual is None:
            return None
        return self.best_individual.fitness

    def plot_convergence(self, figsize: Tuple[int, int] = (12, 6)) -> None:
        """
        Affiche la convergence de l'optimisation.

        Args:
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        try:
            df = self.get_history()

            fig, axes = plt.subplots(2, 1, figsize=figsize)

            # Fitness
            axes[0].plot(df['generation'], df['best_fitness'], 'b-', label='Meilleur fitness')
            axes[0].plot(df['generation'], df['mean_fitness'], 'g--', label='Fitness moyen')
            axes[0].fill_between(
                df['generation'],
                df['mean_fitness'] - df['std_fitness'],
                df['mean_fitness'] + df['std_fitness'],
                alpha=0.2,
                color='green',
                label='Écart-type'
            )
            axes[0].set_xlabel('Génération')
            axes[0].set_ylabel('Fitness')
            axes[0].set_title('Convergence de l\'algorithme génétique')
            axes[0].legend()
            axes[0].grid(True, alpha=0.3)

            # Meilleurs paramètres
            if len(self.dimensions) > 0:
                for dim in self.dimensions:
                    axes[1].plot(
                        df['generation'],
                        df['best_params'].apply(lambda x: x.get(dim, 0)),
                        label=dim
                    )
                axes[1].set_xlabel('Génération')
                axes[1].set_ylabel('Paramètres')
                axes[1].set_title('Évolution des meilleurs paramètres')
                axes[1].legend()
                axes[1].grid(True, alpha=0.3)

            plt.tight_layout()
            plt.show()

        except Exception as e:
            logger.error(f"Erreur lors du tracé: {e}")

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde l'optimiseur sur le disque.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si la sauvegarde a réussi
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'population': [ind.to_dict() for ind in self.population],
                'best_individual': self.best_individual.to_dict() if self.best_individual else None,
                'history': self.history,
                'dimensions': self.dimensions,
                'bounds': self.bounds,
                'is_fitted': self.is_fitted,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Optimiseur sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'GeneticAlgorithm':
        """
        Charge un optimiseur depuis le disque.

        Args:
            filepath: Chemin du fichier

        Returns:
            GeneticAlgorithm: Optimiseur chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = GeneticAlgorithmConfig(**data['config'])
            optimizer = cls(config)

            # Restaurer la population
            population = []
            for ind_data in data.get('population', []):
                individual = Individual(
                    genes=np.array(ind_data['genes']),
                    fitness=ind_data['fitness'],
                    age=ind_data['age']
                )
                population.append(individual)
            optimizer.population = population

            # Restaurer le meilleur individu
            best_data = data.get('best_individual')
            if best_data:
                optimizer.best_individual = Individual(
                    genes=np.array(best_data['genes']),
                    fitness=best_data['fitness'],
                    age=best_data['age']
                )

            optimizer.history = data.get('history', [])
            optimizer.dimensions = data.get('dimensions', [])
            optimizer.bounds = data.get('bounds', [])
            optimizer.is_fitted = data.get('is_fitted', False)

            logger.info(f"Optimiseur chargé: {filepath}")
            return optimizer

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_genetic_algorithm(
    population_size: int = 50,
    n_generations: int = 100,
    mutation_rate: float = 0.1,
    crossover_rate: float = 0.8,
    **kwargs
) -> GeneticAlgorithm:
    """
    Factory pour créer un algorithme génétique.

    Args:
        population_size: Taille de la population
        n_generations: Nombre de générations
        mutation_rate: Taux de mutation
        crossover_rate: Taux de crossover
        **kwargs: Arguments supplémentaires

    Returns:
        GeneticAlgorithm: Algorithme génétique
    """
    config = GeneticAlgorithmConfig(
        population_size=population_size,
        n_generations=n_generations,
        mutation_rate=mutation_rate,
        crossover_rate=crossover_rate,
        **kwargs
    )
    return GeneticAlgorithm(config)


__all__ = [
    'GeneticAlgorithm',
    'GeneticAlgorithmConfig',
    'Individual',
    'create_genetic_algorithm',
]
