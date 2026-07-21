"""
NEXUS AI TRADING SYSTEM - ARBITRAGE BOT OPTIMIZER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module d'optimisation pour le bot d'arbitrage.
Optimisation des paramètres, stratégies, et performances en temps réel.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import numpy as np
from scipy.optimize import minimize, differential_evolution
from scipy.stats import norm

from ..arbitrage_bot import (
    ArbitrageBot,
    ArbitrageOpportunity,
    ArbitrageConfig,
    ExchangeType,
    ArbitrageType
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class OptimizationMetric(Enum):
    """Métriques d'optimisation."""
    PROFIT = "profit"
    WIN_RATE = "win_rate"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    PROFIT_FACTOR = "profit_factor"
    EXPECTED_VALUE = "expected_value"
    RECOVERY_FACTOR = "recovery_factor"
    COMPOSITE = "composite"


class OptimizationAlgorithm(Enum):
    """Algorithmes d'optimisation."""
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    BAYESIAN = "bayesian"
    GENETIC = "genetic"
    GRADIENT_DESCENT = "gradient_descent"
    SIMULATED_ANNEALING = "simulated_annealing"
    PARTICLE_SWARM = "particle_swarm"


@dataclass
class OptimizationConfig:
    """Configuration d'optimisation."""
    algorithm: OptimizationAlgorithm = OptimizationAlgorithm.GENETIC
    metric: OptimizationMetric = OptimizationMetric.COMPOSITE
    max_iterations: int = 100
    population_size: int = 50
    mutation_rate: float = 0.1
    crossover_rate: float = 0.8
    convergence_threshold: float = 0.001
    parallel_evaluations: int = 4
    random_seed: Optional[int] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationResult:
    """Résultat d'optimisation."""
    optimization_id: UUID
    bot_id: UUID
    config: OptimizationConfig
    best_params: Dict[str, Any]
    best_score: float
    all_scores: List[float]
    all_params: List[Dict[str, Any]]
    duration_seconds: float
    iterations: int
    improvement: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "optimization_id": str(self.optimization_id),
            "bot_id": str(self.bot_id),
            "config": self.config.__dict__,
            "best_params": self.best_params,
            "best_score": self.best_score,
            "all_scores": self.all_scores,
            "all_params": self.all_params,
            "duration_seconds": self.duration_seconds,
            "iterations": self.iterations,
            "improvement": self.improvement,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ParameterSpace:
    """Espace de paramètres."""
    param_name: str
    param_type: str  # "float", "int", "choice", "log"
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    choices: Optional[List[Any]] = None
    step: Optional[float] = None
    distribution: Optional[str] = None  # "uniform", "normal", "log_normal"
    default: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# CLASSE ARBITRAGE BOT OPTIMIZER
# ============================================================================

class ArbitrageBotOptimizer:
    """
    Optimisateur pour le bot d'arbitrage.
    """

    # Paramètres par défaut
    DEFAULT_PARAM_SPACES = {
        "min_profit_threshold": ParameterSpace(
            param_name="min_profit_threshold",
            param_type="float",
            min_value=0.001,
            max_value=0.05,
            step=0.001,
            distribution="uniform",
            default=0.005
        ),
        "max_slippage": ParameterSpace(
            param_name="max_slippage",
            param_type="float",
            min_value=0.001,
            max_value=0.02,
            step=0.001,
            distribution="uniform",
            default=0.005
        ),
        "max_position_size": ParameterSpace(
            param_name="max_position_size",
            param_type="float",
            min_value=100,
            max_value=10000,
            step=100,
            distribution="uniform",
            default=1000
        ),
        "min_position_size": ParameterSpace(
            param_name="min_position_size",
            param_type="float",
            min_value=10,
            max_value=500,
            step=10,
            distribution="uniform",
            default=100
        ),
        "max_execution_time": ParameterSpace(
            param_name="max_execution_time",
            param_type="float",
            min_value=1.0,
            max_value=10.0,
            step=0.5,
            distribution="uniform",
            default=3.0
        ),
        "price_deviation": ParameterSpace(
            param_name="price_deviation",
            param_type="float",
            min_value=0.001,
            max_value=0.01,
            step=0.001,
            distribution="uniform",
            default=0.002
        ),
        "min_liquidity": ParameterSpace(
            param_name="min_liquidity",
            param_type="float",
            min_value=1000,
            max_value=100000,
            step=1000,
            distribution="log",
            default=10000
        ),
        "max_risk_per_trade": ParameterSpace(
            param_name="max_risk_per_trade",
            param_type="float",
            min_value=0.001,
            max_value=0.05,
            step=0.001,
            distribution="uniform",
            default=0.01
        ),
        "stop_loss": ParameterSpace(
            param_name="stop_loss",
            param_type="float",
            min_value=0.001,
            max_value=0.05,
            step=0.001,
            distribution="uniform",
            default=0.02
        ),
        "take_profit": ParameterSpace(
            param_name="take_profit",
            param_type="float",
            min_value=0.01,
            max_value=0.1,
            step=0.005,
            distribution="uniform",
            default=0.05
        ),
        "order_book_depth": ParameterSpace(
            param_name="order_book_depth",
            param_type="int",
            min_value=5,
            max_value=50,
            step=5,
            distribution="uniform",
            default=20
        ),
        "timeout_seconds": ParameterSpace(
            param_name="timeout_seconds",
            param_type="int",
            min_value=5,
            max_value=60,
            step=5,
            distribution="uniform",
            default=30
        ),
        "retry_attempts": ParameterSpace(
            param_name="retry_attempts",
            param_type="int",
            min_value=1,
            max_value=10,
            step=1,
            distribution="uniform",
            default=3
        ),
        "concurrent_trades": ParameterSpace(
            param_name="concurrent_trades",
            param_type="int",
            min_value=1,
            max_value=10,
            step=1,
            distribution="uniform",
            default=3
        ),
        "rebalance_threshold": ParameterSpace(
            param_name="rebalance_threshold",
            param_type="float",
            min_value=0.01,
            max_value=0.1,
            step=0.01,
            distribution="uniform",
            default=0.05
        )
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        config: Optional[OptimizationConfig] = None
    ):
        """
        Initialise l'optimisateur.

        Args:
            redis_client: Client Redis pour le cache
            config: Configuration d'optimisation
        """
        self.redis = redis_client
        self.config = config or OptimizationConfig()
        
        # Cache
        self._optimization_cache: Dict[UUID, OptimizationResult] = {}
        self._param_spaces: Dict[str, ParameterSpace] = {}
        self._running_optimizations: Dict[UUID, bool] = {}
        
        # Métriques
        self._metrics = {
            "total_optimizations": 0,
            "total_evaluations": 0,
            "total_duration": 0,
            "best_score": 0,
            "last_optimization": None,
            "by_algorithm": {}
        }

        # Initialisation des espaces de paramètres
        self._init_param_spaces()

        logger.info("ArbitrageBotOptimizer initialisé avec succès")

    def _init_param_spaces(self) -> None:
        """Initialise les espaces de paramètres par défaut."""
        self._param_spaces = self.DEFAULT_PARAM_SPACES.copy()

    # ========================================================================
    # OPTIMISATION PRINCIPALE
    # ========================================================================

    async def optimize(
        self,
        bot: ArbitrageBot,
        param_spaces: Optional[Dict[str, ParameterSpace]] = None,
        config: Optional[OptimizationConfig] = None,
        historical_data: Optional[List[Dict]] = None,
        callback: Optional[callable] = None
    ) -> OptimizationResult:
        """
        Optimise les paramètres du bot.

        Args:
            bot: Bot à optimiser
            param_spaces: Espaces de paramètres (optionnel)
            config: Configuration d'optimisation (optionnel)
            historical_data: Données historiques (optionnel)
            callback: Fonction de callback

        Returns:
            Résultat d'optimisation
        """
        try:
            optimization_id = uuid4()
            start_time = datetime.now()
            
            # Configuration
            opt_config = config or self.config
            param_spaces = param_spaces or self._param_spaces
            
            # Sélection de l'algorithme
            algorithm = opt_config.algorithm
            self._running_optimizations[optimization_id] = True

            # Exécution de l'optimisation
            if algorithm == OptimizationAlgorithm.GRID_SEARCH:
                result = await self._grid_search(
                    bot, param_spaces, opt_config, historical_data, callback
                )
            elif algorithm == OptimizationAlgorithm.RANDOM_SEARCH:
                result = await self._random_search(
                    bot, param_spaces, opt_config, historical_data, callback
                )
            elif algorithm == OptimizationAlgorithm.BAYESIAN:
                result = await self._bayesian_search(
                    bot, param_spaces, opt_config, historical_data, callback
                )
            elif algorithm == OptimizationAlgorithm.GENETIC:
                result = await self._genetic_algorithm(
                    bot, param_spaces, opt_config, historical_data, callback
                )
            elif algorithm == OptimizationAlgorithm.GRADIENT_DESCENT:
                result = await self._gradient_descent(
                    bot, param_spaces, opt_config, historical_data, callback
                )
            elif algorithm == OptimizationAlgorithm.SIMULATED_ANNEALING:
                result = await self._simulated_annealing(
                    bot, param_spaces, opt_config, historical_data, callback
                )
            elif algorithm == OptimizationAlgorithm.PARTICLE_SWARM:
                result = await self._particle_swarm(
                    bot, param_spaces, opt_config, historical_data, callback
                )
            else:
                raise ValueError(f"Algorithme non supporté: {algorithm}")

            # Mise à jour des métriques
            duration = (datetime.now() - start_time).total_seconds()
            result.duration_seconds = duration
            result.optimization_id = optimization_id
            result.bot_id = bot.config.bot_id

            self._metrics["total_optimizations"] += 1
            self._metrics["total_duration"] += duration
            self._metrics["last_optimization"] = datetime.now().isoformat()
            
            if result.best_score > self._metrics["best_score"]:
                self._metrics["best_score"] = result.best_score

            algorithm_key = algorithm.value
            if algorithm_key not in self._metrics["by_algorithm"]:
                self._metrics["by_algorithm"][algorithm_key] = 0
            self._metrics["by_algorithm"][algorithm_key] += 1

            # Cache
            self._optimization_cache[optimization_id] = result

            # Application des meilleurs paramètres
            await self._apply_parameters(bot, result.best_params)

            return result

        except Exception as e:
            logger.error(f"Erreur lors de l'optimisation: {e}")
            raise
        finally:
            if optimization_id in self._running_optimizations:
                del self._running_optimizations[optimization_id]

    # ========================================================================
    # ALGORITHMES D'OPTIMISATION
    # ========================================================================

    async def _grid_search(
        self,
        bot: ArbitrageBot,
        param_spaces: Dict[str, ParameterSpace],
        config: OptimizationConfig,
        historical_data: Optional[List[Dict]],
        callback: Optional[callable]
    ) -> OptimizationResult:
        """
        Recherche par grille.

        Args:
            bot: Bot
            param_spaces: Espaces de paramètres
            config: Configuration
            historical_data: Données historiques
            callback: Fonction de callback

        Returns:
            Résultat d'optimisation
        """
        try:
            # Génération de la grille
            grid = self._generate_grid(param_spaces)
            total_combinations = len(grid)
            
            logger.info(f"Grille générée: {total_combinations} combinaisons")

            best_score = float('-inf')
            best_params = None
            all_scores = []
            all_params = []

            for i, params in enumerate(grid):
                if not self._running_optimizations.get(bot.config.bot_id, True):
                    break

                # Évaluation
                score = await self._evaluate_params(
                    bot, params, historical_data, config.metric
                )
                all_scores.append(score)
                all_params.append(params)

                if score > best_score:
                    best_score = score
                    best_params = params

                # Progression
                if callback and i % 10 == 0:
                    await callback({
                        "iteration": i,
                        "total": total_combinations,
                        "best_score": best_score,
                        "current_score": score
                    })

                self._metrics["total_evaluations"] += 1

            return OptimizationResult(
                optimization_id=uuid4(),
                bot_id=bot.config.bot_id,
                config=config,
                best_params=best_params or {},
                best_score=best_score,
                all_scores=all_scores,
                all_params=all_params,
                duration_seconds=0,
                iterations=len(grid),
                improvement=best_score - min(all_scores) if all_scores else 0
            )

        except Exception as e:
            logger.error(f"Erreur grid_search: {e}")
            raise

    async def _random_search(
        self,
        bot: ArbitrageBot,
        param_spaces: Dict[str, ParameterSpace],
        config: OptimizationConfig,
        historical_data: Optional[List[Dict]],
        callback: Optional[callable]
    ) -> OptimizationResult:
        """
        Recherche aléatoire.

        Args:
            bot: Bot
            param_spaces: Espaces de paramètres
            config: Configuration
            historical_data: Données historiques
            callback: Fonction de callback

        Returns:
            Résultat d'optimisation
        """
        try:
            max_iterations = config.max_iterations
            best_score = float('-inf')
            best_params = None
            all_scores = []
            all_params = []

            for i in range(max_iterations):
                if not self._running_optimizations.get(bot.config.bot_id, True):
                    break

                # Génération aléatoire
                params = self._random_params(param_spaces)
                
                # Évaluation
                score = await self._evaluate_params(
                    bot, params, historical_data, config.metric
                )
                all_scores.append(score)
                all_params.append(params)

                if score > best_score:
                    best_score = score
                    best_params = params

                if callback and i % 10 == 0:
                    await callback({
                        "iteration": i,
                        "total": max_iterations,
                        "best_score": best_score,
                        "current_score": score
                    })

                self._metrics["total_evaluations"] += 1

            return OptimizationResult(
                optimization_id=uuid4(),
                bot_id=bot.config.bot_id,
                config=config,
                best_params=best_params or {},
                best_score=best_score,
                all_scores=all_scores,
                all_params=all_params,
                duration_seconds=0,
                iterations=max_iterations,
                improvement=best_score - min(all_scores) if all_scores else 0
            )

        except Exception as e:
            logger.error(f"Erreur random_search: {e}")
            raise

    async def _genetic_algorithm(
        self,
        bot: ArbitrageBot,
        param_spaces: Dict[str, ParameterSpace],
        config: OptimizationConfig,
        historical_data: Optional[List[Dict]],
        callback: Optional[callable]
    ) -> OptimizationResult:
        """
        Algorithme génétique.

        Args:
            bot: Bot
            param_spaces: Espaces de paramètres
            config: Configuration
            historical_data: Données historiques
            callback: Fonction de callback

        Returns:
            Résultat d'optimisation
        """
        try:
            population_size = config.population_size
            mutation_rate = config.mutation_rate
            crossover_rate = config.crossover_rate
            max_iterations = config.max_iterations
            
            # Initialisation de la population
            population = []
            for _ in range(population_size):
                params = self._random_params(param_spaces)
                population.append(params)

            best_score = float('-inf')
            best_params = None
            all_scores = []
            all_params = []

            for generation in range(max_iterations):
                if not self._running_optimizations.get(bot.config.bot_id, True):
                    break

                # Évaluation de la population
                scores = []
                for params in population:
                    score = await self._evaluate_params(
                        bot, params, historical_data, config.metric
                    )
                    scores.append(score)
                    all_scores.append(score)
                    all_params.append(params)
                    self._metrics["total_evaluations"] += 1

                # Meilleur de la génération
                gen_best_idx = np.argmax(scores)
                gen_best_score = scores[gen_best_idx]
                gen_best_params = population[gen_best_idx]

                if gen_best_score > best_score:
                    best_score = gen_best_score
                    best_params = gen_best_params

                # Sélection
                selected = self._tournament_selection(population, scores, population_size // 2)

                # Croisement et mutation
                new_population = []
                while len(new_population) < population_size:
                    parent1 = random.choice(selected)
                    parent2 = random.choice(selected)
                    
                    if random.random() < crossover_rate:
                        child1, child2 = self._crossover(parent1, parent2)
                    else:
                        child1, child2 = parent1.copy(), parent2.copy()
                    
                    # Mutation
                    if random.random() < mutation_rate:
                        child1 = self._mutate(child1, param_spaces)
                    if random.random() < mutation_rate:
                        child2 = self._mutate(child2, param_spaces)
                    
                    new_population.append(child1)
                    if len(new_population) < population_size:
                        new_population.append(child2)

                population = new_population

                if callback:
                    await callback({
                        "generation": generation,
                        "population_size": population_size,
                        "best_score": best_score,
                        "gen_best_score": gen_best_score
                    })

            return OptimizationResult(
                optimization_id=uuid4(),
                bot_id=bot.config.bot_id,
                config=config,
                best_params=best_params or {},
                best_score=best_score,
                all_scores=all_scores,
                all_params=all_params,
                duration_seconds=0,
                iterations=max_iterations,
                improvement=best_score - min(all_scores) if all_scores else 0
            )

        except Exception as e:
            logger.error(f"Erreur genetic_algorithm: {e}")
            raise

    async def _bayesian_search(
        self,
        bot: ArbitrageBot,
        param_spaces: Dict[str, ParameterSpace],
        config: OptimizationConfig,
        historical_data: Optional[List[Dict]],
        callback: Optional[callable]
    ) -> OptimizationResult:
        """
        Recherche bayésienne.

        Args:
            bot: Bot
            param_spaces: Espaces de paramètres
            config: Configuration
            historical_data: Données historiques
            callback: Fonction de callback

        Returns:
            Résultat d'optimisation
        """
        try:
            # Pour une implémentation complète, utiliser scikit-optimize ou GPyOpt
            # Version simplifiée avec random search améliorée
            max_iterations = config.max_iterations
            best_score = float('-inf')
            best_params = None
            all_scores = []
            all_params = []

            # Phase d'exploration
            exploration_iterations = max_iterations // 3
            for i in range(exploration_iterations):
                params = self._random_params(param_spaces)
                score = await self._evaluate_params(
                    bot, params, historical_data, config.metric
                )
                all_scores.append(score)
                all_params.append(params)
                self._metrics["total_evaluations"] += 1

                if score > best_score:
                    best_score = score
                    best_params = params

            # Phase d'exploitation
            exploitation_iterations = max_iterations - exploration_iterations
            for i in range(exploitation_iterations):
                # Sampling autour du meilleur
                params = self._sample_around_best(best_params or {}, param_spaces)
                score = await self._evaluate_params(
                    bot, params, historical_data, config.metric
                )
                all_scores.append(score)
                all_params.append(params)
                self._metrics["total_evaluations"] += 1

                if score > best_score:
                    best_score = score
                    best_params = params

                if callback and i % 10 == 0:
                    await callback({
                        "iteration": exploration_iterations + i,
                        "total": max_iterations,
                        "best_score": best_score,
                        "current_score": score
                    })

            return OptimizationResult(
                optimization_id=uuid4(),
                bot_id=bot.config.bot_id,
                config=config,
                best_params=best_params or {},
                best_score=best_score,
                all_scores=all_scores,
                all_params=all_params,
                duration_seconds=0,
                iterations=max_iterations,
                improvement=best_score - min(all_scores) if all_scores else 0
            )

        except Exception as e:
            logger.error(f"Erreur bayesian_search: {e}")
            raise

    # ========================================================================
    # MÉTHODES D'ÉVALUATION
    # ========================================================================

    async def _evaluate_params(
        self,
        bot: ArbitrageBot,
        params: Dict[str, Any],
        historical_data: Optional[List[Dict]],
        metric: OptimizationMetric
    ) -> float:
        """
        Évalue un jeu de paramètres.

        Args:
            bot: Bot
            params: Paramètres
            historical_data: Données historiques
            metric: Métrique

        Returns:
            Score
        """
        try:
            # Application des paramètres
            await self._apply_parameters(bot, params)

            # Backtest ou simulation
            if historical_data:
                results = await self._backtest(bot, historical_data)
            else:
                results = await self._simulate(bot)

            # Calcul du score
            score = self._calculate_score(results, metric)

            return score

        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation: {e}")
            return 0.0

    async def _backtest(
        self,
        bot: ArbitrageBot,
        historical_data: List[Dict]
    ) -> Dict[str, Any]:
        """
        Backtest du bot.

        Args:
            bot: Bot
            historical_data: Données historiques

        Returns:
            Résultats du backtest
        """
        # Simulation simplifiée
        # En production, implémenter un backtest complet
        trades = []
        total_profit = Decimal("0")
        wins = 0
        losses = 0

        for data_point in historical_data[:100]:  # Limite pour la démonstration
            # Simulation de trade
            if random.random() > 0.5:
                profit = Decimal(str(random.uniform(0.001, 0.05)))
                total_profit += profit
                wins += 1
            else:
                loss = Decimal(str(random.uniform(0.001, 0.03)))
                total_profit -= loss
                losses += 1

            trades.append({
                "profit": float(total_profit),
                "win": random.random() > 0.5
            })

        return {
            "total_trades": len(trades),
            "wins": wins,
            "losses": losses,
            "total_profit": float(total_profit),
            "win_rate": wins / len(trades) if trades else 0,
            "profit_factor": (wins * 0.02) / (losses * 0.01) if losses > 0 else 100,
            "max_drawdown": 0.05,
            "sharpe_ratio": 1.5,
            "sortino_ratio": 1.2,
            "calmar_ratio": 0.8
        }

    async def _simulate(
        self,
        bot: ArbitrageBot
    ) -> Dict[str, Any]:
        """
        Simulation du bot.

        Args:
            bot: Bot

        Returns:
            Résultats de simulation
        """
        # Simulation basée sur les paramètres actuels
        min_profit = bot.config.min_profit_threshold
        max_position = bot.config.max_position_size
        
        # Plus le seuil est bas, plus il y a de trades
        expected_trades = int(100 * (0.02 / float(min_profit)))
        win_rate = 0.6 + float(min_profit) * 5  # Plus le seuil est élevé, plus le win rate est élevé
        win_rate = min(win_rate, 0.95)

        wins = int(expected_trades * win_rate)
        losses = expected_trades - wins
        
        avg_win = float(min_profit) * float(max_position) * 0.5
        avg_loss = float(min_profit) * float(max_position) * 0.3

        total_profit = wins * avg_win - losses * avg_loss

        return {
            "total_trades": expected_trades,
            "wins": wins,
            "losses": losses,
            "total_profit": total_profit,
            "win_rate": win_rate,
            "profit_factor": (wins * avg_win) / (losses * avg_loss) if losses > 0 else 100,
            "max_drawdown": 0.03 + (1 - win_rate) * 0.1,
            "sharpe_ratio": 0.5 + win_rate * 1.5,
            "sortino_ratio": 0.4 + win_rate * 1.2,
            "calmar_ratio": 0.3 + win_rate * 0.8
        }

    def _calculate_score(
        self,
        results: Dict[str, Any],
        metric: OptimizationMetric
    ) -> float:
        """
        Calcule le score à partir des résultats.

        Args:
            results: Résultats
            metric: Métrique

        Returns:
            Score
        """
        if metric == OptimizationMetric.PROFIT:
            return results.get("total_profit", 0)
        elif metric == OptimizationMetric.WIN_RATE:
            return results.get("win_rate", 0)
        elif metric == OptimizationMetric.SHARPE_RATIO:
            return results.get("sharpe_ratio", 0)
        elif metric == OptimizationMetric.SORTINO_RATIO:
            return results.get("sortino_ratio", 0)
        elif metric == OptimizationMetric.CALMAR_RATIO:
            return results.get("calmar_ratio", 0)
        elif metric == OptimizationMetric.MAX_DRAWDOWN:
            return -results.get("max_drawdown", 0)
        elif metric == OptimizationMetric.PROFIT_FACTOR:
            return results.get("profit_factor", 0)
        elif metric == OptimizationMetric.EXPECTED_VALUE:
            return results.get("total_profit", 0) / results.get("total_trades", 1)
        elif metric == OptimizationMetric.RECOVERY_FACTOR:
            return results.get("total_profit", 0) / results.get("max_drawdown", 0.01)
        elif metric == OptimizationMetric.COMPOSITE:
            # Score composite
            win_rate = results.get("win_rate", 0)
            profit = results.get("total_profit", 0)
            sharpe = results.get("sharpe_ratio", 0)
            drawdown = results.get("max_drawdown", 0.01)
            
            return (win_rate * 0.3 + 
                    min(profit, 100) / 100 * 0.3 +
                    min(sharpe, 3) / 3 * 0.2 +
                    max(0, 1 - drawdown) * 0.2)
        else:
            return results.get("total_profit", 0)

    # ========================================================================
    # MÉTHODES UTILITAIRES
    # ========================================================================

    def _generate_grid(
        self,
        param_spaces: Dict[str, ParameterSpace]
    ) -> List[Dict[str, Any]]:
        """
        Génère une grille de paramètres.

        Args:
            param_spaces: Espaces de paramètres

        Returns:
            Liste des combinaisons
        """
        grid = [{}]
        
        for name, space in param_spaces.items():
            if space.param_type == "choice":
                values = space.choices or []
            else:
                step = space.step or 1
                min_val = space.min_value or 0
                max_val = space.max_value or 1
                values = list(np.arange(min_val, max_val + step, step))
            
            new_grid = []
            for base in grid:
                for value in values:
                    new_entry = base.copy()
                    new_entry[name] = value
                    new_grid.append(new_entry)
            grid = new_grid
        
        return grid

    def _random_params(
        self,
        param_spaces: Dict[str, ParameterSpace]
    ) -> Dict[str, Any]:
        """
        Génère des paramètres aléatoires.

        Args:
            param_spaces: Espaces de paramètres

        Returns:
            Paramètres aléatoires
        """
        params = {}
        
        for name, space in param_spaces.items():
            if space.param_type == "choice":
                params[name] = random.choice(space.choices or [])
            elif space.param_type == "int":
                if space.distribution == "uniform":
                    params[name] = random.randint(int(space.min_value or 0), int(space.max_value or 1))
                else:
                    params[name] = random.randint(int(space.min_value or 0), int(space.max_value or 1))
            else:  # float
                if space.distribution == "uniform":
                    params[name] = random.uniform(space.min_value or 0, space.max_value or 1)
                elif space.distribution == "log":
                    log_min = math.log(space.min_value or 0.001)
                    log_max = math.log(space.max_value or 1)
                    params[name] = math.exp(random.uniform(log_min, log_max))
                else:
                    params[name] = random.uniform(space.min_value or 0, space.max_value or 1)
        
        return params

    def _sample_around_best(
        self,
        best_params: Dict[str, Any],
        param_spaces: Dict[str, ParameterSpace],
        std_dev: float = 0.1
    ) -> Dict[str, Any]:
        """
        Échantillonne autour des meilleurs paramètres.

        Args:
            best_params: Meilleurs paramètres
            param_spaces: Espaces de paramètres
            std_dev: Écart-type

        Returns:
            Nouveaux paramètres
        """
        params = {}
        
        for name, space in param_spaces.items():
            best_value = best_params.get(name, space.default or 0)
            
            if space.param_type == "choice":
                choices = space.choices or []
                if choices:
                    # Choisir une valeur proche de la meilleure
                    idx = choices.index(best_value) if best_value in choices else 0
                    new_idx = int(np.clip(idx + random.randint(-1, 1), 0, len(choices) - 1))
                    params[name] = choices[new_idx]
                else:
                    params[name] = best_value
            elif space.param_type == "int":
                min_val = space.min_value or 0
                max_val = space.max_value or 1
                step = space.step or 1
                new_val = best_value + random.randint(-2, 2) * step
                params[name] = int(np.clip(new_val, min_val, max_val))
            else:
                min_val = space.min_value or 0
                max_val = space.max_value or 1
                new_val = best_value + random.gauss(0, std_dev * (max_val - min_val))
                params[name] = np.clip(new_val, min_val, max_val)
        
        return params

    def _tournament_selection(
        self,
        population: List[Dict],
        scores: List[float],
        k: int
    ) -> List[Dict]:
        """
        Sélection par tournoi.

        Args:
            population: Population
            scores: Scores
            k: Nombre de sélections

        Returns:
            Sélection
        """
        selected = []
        tournament_size = 3
        
        for _ in range(k):
            tournament_indices = random.sample(range(len(population)), tournament_size)
            winner_idx = max(tournament_indices, key=lambda i: scores[i])
            selected.append(population[winner_idx])
        
        return selected

    def _crossover(
        self,
        parent1: Dict,
        parent2: Dict
    ) -> Tuple[Dict, Dict]:
        """
        Croisement de deux parents.

        Args:
            parent1: Premier parent
            parent2: Deuxième parent

        Returns:
            Deux enfants
        """
        child1 = {}
        child2 = {}
        
        for key in parent1.keys():
            if random.random() < 0.5:
                child1[key] = parent1[key]
                child2[key] = parent2[key]
            else:
                child1[key] = parent2[key]
                child2[key] = parent1[key]
        
        return child1, child2

    def _mutate(
        self,
        params: Dict,
        param_spaces: Dict[str, ParameterSpace],
        mutation_rate: float = 0.1
    ) -> Dict:
        """
        Mutate des paramètres.

        Args:
            params: Paramètres
            param_spaces: Espaces de paramètres
            mutation_rate: Taux de mutation

        Returns:
            Paramètres mutés
        """
        mutated = params.copy()
        
        for name, space in param_spaces.items():
            if random.random() < mutation_rate:
                if space.param_type == "choice":
                    choices = space.choices or []
                    if choices:
                        mutated[name] = random.choice(choices)
                elif space.param_type == "int":
                    min_val = space.min_value or 0
                    max_val = space.max_value or 1
                    step = space.step or 1
                    new_val = mutated.get(name, min_val) + random.randint(-2, 2) * step
                    mutated[name] = int(np.clip(new_val, min_val, max_val))
                else:
                    min_val = space.min_value or 0
                    max_val = space.max_value or 1
                    new_val = mutated.get(name, (min_val + max_val) / 2) + random.gauss(0, 0.1 * (max_val - min_val))
                    mutated[name] = np.clip(new_val, min_val, max_val)
        
        return mutated

    async def _apply_parameters(
        self,
        bot: ArbitrageBot,
        params: Dict[str, Any]
    ) -> None:
        """
        Applique les paramètres au bot.

        Args:
            bot: Bot
            params: Paramètres
        """
        config = bot.config
        
        for key, value in params.items():
            if hasattr(config, key):
                setattr(config, key, value)
            elif key in config.__dict__:
                config.__dict__[key] = value

        # Mise à jour de la configuration
        bot.config = config

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_optimization_result(
        self,
        optimization_id: UUID
    ) -> Optional[OptimizationResult]:
        """
        Récupère un résultat d'optimisation.

        Args:
            optimization_id: ID de l'optimisation

        Returns:
            Résultat d'optimisation
        """
        return self._optimization_cache.get(optimization_id)

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_optimizations": self._metrics["total_optimizations"],
                "total_evaluations": self._metrics["total_evaluations"],
                "total_duration": self._metrics["total_duration"],
                "best_score": self._metrics["best_score"],
                "last_optimization": self._metrics["last_optimization"],
                "by_algorithm": self._metrics["by_algorithm"],
                "cached_results": len(self._optimization_cache),
                "running_optimizations": len(self._running_optimizations),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de ArbitrageBotOptimizer...")
        self._optimization_cache.clear()
        self._running_optimizations.clear()
        logger.info("ArbitrageBotOptimizer fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_arbitrage_bot_optimizer(
    redis_url: str = "redis://localhost:6379/0",
    config: Optional[OptimizationConfig] = None
) -> ArbitrageBotOptimizer:
    """
    Crée une instance de l'optimisateur.

    Args:
        redis_url: URL de connexion Redis
        config: Configuration d'optimisation

    Returns:
        Instance de l'optimisateur
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return ArbitrageBotOptimizer(
        redis_client=redis_client,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "OptimizationMetric",
    "OptimizationAlgorithm",
    "OptimizationConfig",
    "OptimizationResult",
    "ParameterSpace",
    "ArbitrageBotOptimizer",
    "create_arbitrage_bot_optimizer"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation de l'optimisateur."""
    print("=" * 60)
    print("NEXUS AI TRADING - ARBITRAGE BOT OPTIMIZER")
    print("=" * 60)

    # Création de l'optimisateur
    optimizer = create_arbitrage_bot_optimizer()

    # Création d'un bot exemple
    from ..arbitrage_bot import ArbitrageBot, ArbitrageConfig
    
    config = ArbitrageConfig(
        bot_id=uuid4(),
        name="Test Bot",
        min_profit_threshold=0.005,
        max_position_size=1000
    )
    
    bot = ArbitrageBot(
        config=config,
        exchange_clients={}
    )

    print(f"\n✅ Bot créé:")
    print(f"   ID: {bot.config.bot_id}")
    print(f"   Profit threshold: {bot.config.min_profit_threshold}")

    # Optimisation
    print(f"\n🔧 Optimisation en cours...")
    
    result = await optimizer.optimize(
        bot=bot,
        config=OptimizationConfig(
            algorithm=OptimizationAlgorithm.GENETIC,
            metric=OptimizationMetric.COMPOSITE,
            max_iterations=10,
            population_size=10
        )
    )

    print(f"\n📊 Résultat de l'optimisation:")
    print(f"   ID: {result.optimization_id}")
    print(f"   Meilleurs paramètres: {result.best_params}")
    print(f"   Meilleur score: {result.best_score:.4f}")
    print(f"   Itérations: {result.iterations}")
    print(f"   Amélioration: {result.improvement:.4f}")

    # Santé du service
    health = await optimizer.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Optimisations: {health['total_optimizations']}")
    print(f"   Évaluations: {health['total_evaluations']}")
    print(f"   Meilleur score: {health['best_score']:.4f}")

    # Fermeture
    await optimizer.close()

    print("\n" + "=" * 60)
    print("ArbitrageBotOptimizer NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import random
    import numpy as np
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
