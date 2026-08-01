# trading/bots/hedge_bot/hedge_bot_sharpe_optimizer.py
# Advanced Sharpe Ratio Optimization & Portfolio Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Sharpe Optimizer Module - Module avancé d'optimisation du ratio de Sharpe et de gestion
de portefeuille pour le Hedge Bot. Optimise l'allocation d'actifs, maximise le rendement ajusté
au risque, gère les contraintes de portefeuille et assure une diversification optimale.
"""

import asyncio
import json
import math
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
import concurrent.futures
from scipy.optimize import minimize, Bounds
from scipy.stats import norm

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_sharpe_optimizer")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)


# ============== ENUMS & TYPES ==============

class OptimizationObjective(Enum):
    """Objectifs d'optimisation."""
    MAX_SHARPE = "max_sharpe"          # Maximiser le ratio de Sharpe
    MIN_VOLATILITY = "min_volatility"  # Minimiser la volatilité
    MAX_RETURN = "max_return"          # Maximiser le rendement
    MAX_SORTINO = "max_sortino"        # Maximiser le ratio de Sortino
    MAX_CALMAR = "max_calmar"          # Maximiser le ratio de Calmar
    RISK_PARITY = "risk_parity"        # Parité des risques
    MIN_DRAWDOWN = "min_drawdown"      # Minimiser le drawdown
    CUSTOM = "custom"                  # Objectif personnalisé


class ConstraintType(Enum):
    """Types de contraintes."""
    LONG_ONLY = "long_only"            # Positions longues uniquement
    SHORT_ALLOWED = "short_allowed"    # Positions courtes autorisées
    MAX_WEIGHT = "max_weight"          # Poids maximum par actif
    MIN_WEIGHT = "min_weight"          # Poids minimum par actif
    MAX_TURNOVER = "max_turnover"      # Rotation maximale du portefeuille
    SECTOR_CAP = "sector_cap"          # Limite par secteur
    ASSET_CLASS_CAP = "asset_class_cap"  # Limite par classe d'actifs


class RiskParityMethod(Enum):
    """Méthodes de parité des risques."""
    EQUAL_VOLATILITY = "equal_volatility"
    EQUAL_CORRELATION = "equal_correlation"
    EQUAL_RISK_CONTRIBUTION = "equal_risk_contribution"
    HIERARCHICAL = "hierarchical"


# ============== DATA MODELS ==============

@dataclass
class Asset:
    """Actif financier."""
    asset_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    name: str = ""
    asset_class: str = ""
    sector: str = ""
    returns: List[float] = field(default_factory=list)
    prices: List[float] = field(default_factory=list)
    volatility: float = 0.0
    expected_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    correlation_matrix: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class Portfolio:
    """Portefeuille optimisé."""
    portfolio_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    weights: Dict[str, float] = field(default_factory=dict)
    expected_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    turnover: float = 0.0
    diversification_ratio: float = 0.0
    constraints: List[ConstraintType] = field(default_factory=list)
    optimization_objective: OptimizationObjective = OptimizationObjective.MAX_SHARPE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class OptimizationResult:
    """Résultat d'optimisation."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    portfolio: Portfolio = field(default_factory=Portfolio)
    objective_value: float = 0.0
    iterations: int = 0
    success: bool = False
    message: str = ""
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class SharpeOptimizerInterface(ABC):
    """Interface abstraite pour l'optimiseur de Sharpe."""
    
    @abstractmethod
    async def optimize(self, assets: List[Asset], objective: OptimizationObjective) -> OptimizationResult:
        """Optimise un portefeuille."""
        pass
    
    @abstractmethod
    async def calculate_sharpe(self, weights: np.ndarray, returns: np.ndarray) -> float:
        """Calcule le ratio de Sharpe."""
        pass
    
    @abstractmethod
    async def risk_parity(self, assets: List[Asset]) -> OptimizationResult:
        """Calcule l'allocation par parité des risques."""
        pass


# ============== IMPLÉMENTATION ==============

class SharpeOptimizer(SharpeOptimizerInterface):
    """
    Optimiseur de Sharpe avancé pour le Hedge Bot.
    Optimise l'allocation d'actifs et maximise le rendement ajusté au risque.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des portefeuilles
        self._portfolios: Dict[str, Portfolio] = {}
        self._portfolios_lock = threading.RLock()
        
        # Gestion des résultats
        self._results: Dict[str, OptimizationResult] = {}
        self._results_lock = threading.RLock()
        
        # Cache des calculs
        self._calculation_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "optimizations_performed": 0,
            "portfolios_created": 0,
            "avg_sharpe": 0.0,
            "max_sharpe": 0.0,
            "optimization_time_ms": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("SharpeOptimizer initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "risk_free_rate": 0.02,
            "max_iterations": 1000,
            "tolerance": 1e-6,
            "max_weights": 0.3,
            "min_weights": 0.01,
            "long_only": True,
            "short_allowed": False,
            "max_turnover": 0.5,
            "diversification_target": 0.5,
            "asset_correlation_lookback": 252,
            "returns_lookback": 252,
            "risk_free_rate_lookback": 30,
            "enable_constraints": True,
            "parallel_optimization": True,
            "cache_size": 100
        }
    
    async def start(self) -> None:
        """Démarre l'optimiseur de Sharpe."""
        logger.info("SharpeOptimizer starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("SharpeOptimizer started")
    
    async def stop(self) -> None:
        """Arrête l'optimiseur de Sharpe."""
        logger.info("SharpeOptimizer stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("SharpeOptimizer stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def optimize(
        self,
        assets: List[Asset],
        objective: OptimizationObjective = OptimizationObjective.MAX_SHARPE,
        constraints: Optional[List[ConstraintType]] = None
    ) -> OptimizationResult:
        """Optimise un portefeuille."""
        start_time = time.time()
        self._stats["optimizations_performed"] += 1
        
        try:
            # Préparation des données
            returns = np.array([a.returns for a in assets])
            
            # Calcul de la matrice de covariance
            cov_matrix = np.cov(returns)
            
            # Rendements attendus
            expected_returns = np.array([a.expected_return for a in assets])
            
            # Définition des contraintes
            n_assets = len(assets)
            constraints_list = constraints or [ConstraintType.LONG_ONLY]
            
            # Construction des contraintes d'optimisation
            cons = await self._build_constraints(n_assets, constraints_list)
            
            # Bornes
            bounds = await self._build_bounds(n_assets, constraints_list)
            
            # Optimisation selon l'objectif
            if objective == OptimizationObjective.MAX_SHARPE:
                result = await self._maximize_sharpe(returns, cov_matrix, expected_returns, cons, bounds)
            elif objective == OptimizationObjective.MIN_VOLATILITY:
                result = await self._minimize_volatility(cov_matrix, cons, bounds)
            elif objective == OptimizationObjective.MAX_RETURN:
                result = await self._maximize_return(expected_returns, cons, bounds)
            elif objective == OptimizationObjective.RISK_PARITY:
                result = await self._risk_parity_optimization(cov_matrix, cons, bounds)
            else:
                # Par défaut: Maximiser le Sharpe
                result = await self._maximize_sharpe(returns, cov_matrix, expected_returns, cons, bounds)
            
            # Création du portefeuille
            portfolio = Portfolio(
                name=f"Portfolio_{uuid.uuid4().hex[:8]}",
                weights={assets[i].symbol: result.x[i] for i in range(n_assets)},
                expected_return=result.fun if result.fun < 0 else result.fun,
                volatility=np.sqrt(np.dot(result.x.T, np.dot(cov_matrix, result.x))),
                sharpe_ratio=await self.calculate_sharpe(result.x, returns),
                constraints=constraints_list,
                optimization_objective=objective
            )
            
            # Métriques supplémentaires
            portfolio.sortino_ratio = await self._calculate_sortino(result.x, returns)
            portfolio.calmar_ratio = await self._calculate_calmar(result.x, returns)
            portfolio.max_drawdown = await self._calculate_max_drawdown(result.x, returns)
            portfolio.diversification_ratio = await self._calculate_diversification(result.x, returns)
            
            # Stockage du portefeuille
            with self._portfolios_lock:
                self._portfolios[portfolio.portfolio_id] = portfolio
                self._stats["portfolios_created"] += 1
            
            # Création du résultat
            optimization_result = OptimizationResult(
                portfolio=portfolio,
                objective_value=result.fun,
                iterations=result.nit if hasattr(result, 'nit') else 0,
                success=result.success,
                message=result.message,
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
            # Mise à jour des statistiques
            self._stats["avg_sharpe"] = (
                self._stats["avg_sharpe"] * 0.9 + portfolio.sharpe_ratio * 0.1
            )
            self._stats["max_sharpe"] = max(self._stats["max_sharpe"], portfolio.sharpe_ratio)
            self._stats["optimization_time_ms"] = (
                self._stats["optimization_time_ms"] * 0.9 + optimization_result.execution_time_ms * 0.1
            )
            
            # Stockage du résultat
            with self._results_lock:
                self._results[optimization_result.result_id] = optimization_result
            
            logger.info(f"Portfolio optimized: sharpe={portfolio.sharpe_ratio:.2f} "
                       f"return={portfolio.expected_return:.2%} "
                       f"vol={portfolio.volatility:.2%}")
            
            return optimization_result
            
        except Exception as e:
            logger.error(f"Optimization error: {e}")
            raise
    
    async def calculate_sharpe(self, weights: np.ndarray, returns: np.ndarray) -> float:
        """Calcule le ratio de Sharpe."""
        if len(returns) == 0 or len(weights) == 0:
            return 0.0
        
        portfolio_return = np.sum(weights * returns.mean(axis=1) if len(returns.shape) > 1 else returns.mean())
        portfolio_vol = np.std(returns.T @ weights if len(returns.shape) > 1 else returns * weights)
        
        if portfolio_vol == 0:
            return 0.0
        
        risk_free_rate = self.config["risk_free_rate"]
        sharpe = (portfolio_return - risk_free_rate) / portfolio_vol
        
        return sharpe
    
    async def risk_parity(self, assets: List[Asset]) -> OptimizationResult:
        """Calcule l'allocation par parité des risques."""
        return await self.optimize(assets, OptimizationObjective.RISK_PARITY)
    
    # ========== MÉTHODES PRIVÉES - OPTIMISATION ==========
    
    async def _maximize_sharpe(self, returns, cov_matrix, expected_returns, cons, bounds):
        """Maximise le ratio de Sharpe."""
        n_assets = len(expected_returns)
        
        # Fonction objectif: -Sharpe Ratio
        def objective(weights):
            portfolio_return = np.sum(weights * expected_returns)
            portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            if portfolio_vol == 0:
                return 0
            return -(portfolio_return - self.config["risk_free_rate"]) / portfolio_vol
        
        # Initialisation
        x0 = np.ones(n_assets) / n_assets
        
        # Optimisation
        result = minimize(
            objective,
            x0,
            method='SLSQP',
            constraints=cons,
            bounds=bounds,
            options={'maxiter': self.config["max_iterations"], 'ftol': self.config["tolerance"]}
        )
        
        return result
    
    async def _minimize_volatility(self, cov_matrix, cons, bounds):
        """Minimise la volatilité du portefeuille."""
        n_assets = len(cov_matrix)
        
        def objective(weights):
            return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        
        x0 = np.ones(n_assets) / n_assets
        
        result = minimize(
            objective,
            x0,
            method='SLSQP',
            constraints=cons,
            bounds=bounds,
            options={'maxiter': self.config["max_iterations"], 'ftol': self.config["tolerance"]}
        )
        
        return result
    
    async def _maximize_return(self, expected_returns, cons, bounds):
        """Maximise le rendement du portefeuille."""
        n_assets = len(expected_returns)
        
        def objective(weights):
            return -np.sum(weights * expected_returns)
        
        x0 = np.ones(n_assets) / n_assets
        
        result = minimize(
            objective,
            x0,
            method='SLSQP',
            constraints=cons,
            bounds=bounds,
            options={'maxiter': self.config["max_iterations"], 'ftol': self.config["tolerance"]}
        )
        
        return result
    
    async def _risk_parity_optimization(self, cov_matrix, cons, bounds):
        """Optimisation par parité des risques."""
        n_assets = len(cov_matrix)
        
        def objective(weights):
            portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            if portfolio_vol == 0:
                return 1e6
            
            # Contribution au risque de chaque actif
            risk_contributions = weights * (cov_matrix @ weights) / portfolio_vol
            
            # Objectif: égaliser les contributions
            target_risk = portfolio_vol / n_assets
            return np.sum((risk_contributions - target_risk) ** 2)
        
        x0 = np.ones(n_assets) / n_assets
        
        result = minimize(
            objective,
            x0,
            method='SLSQP',
            constraints=cons,
            bounds=bounds,
            options={'maxiter': self.config["max_iterations"], 'ftol': self.config["tolerance"]}
        )
        
        return result
    
    # ========== MÉTHODES PRIVÉES - CONTRAINTES ==========
    
    async def _build_constraints(self, n_assets: int, constraints: List[ConstraintType]) -> List[Dict]:
        """Construit les contraintes d'optimisation."""
        cons = []
        
        # Contrainte de somme des poids = 1
        cons.append({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        
        # Contraintes spécifiques
        for constraint in constraints:
            if constraint == ConstraintType.LONG_ONLY:
                # Les poids doivent être >= 0 (géré par les bornes)
                pass
            
            elif constraint == ConstraintType.SHORT_ALLOWED:
                # Les poids peuvent être négatifs (géré par les bornes)
                pass
            
            elif constraint == ConstraintType.MAX_WEIGHT:
                # Poids maximum
                max_w = self.config.get("max_weights", 0.3)
                cons.append({'type': 'ineq', 'fun': lambda x: max_w - np.max(x)})
            
            elif constraint == ConstraintType.MIN_WEIGHT:
                # Poids minimum
                min_w = self.config.get("min_weights", 0.01)
                cons.append({'type': 'ineq', 'fun': lambda x: np.min(x) - min_w})
            
            elif constraint == ConstraintType.MAX_TURNOVER:
                # Rotation maximale
                max_turnover = self.config.get("max_turnover", 0.5)
                # À implémenter avec les poids du portefeuille précédent
                pass
        
        return cons
    
    async def _build_bounds(self, n_assets: int, constraints: List[ConstraintType]) -> Bounds:
        """Construit les bornes des variables."""
        if ConstraintType.LONG_ONLY in constraints:
            lower = np.zeros(n_assets)
            upper = np.ones(n_assets)
        elif ConstraintType.SHORT_ALLOWED in constraints:
            lower = -np.ones(n_assets) * 2
            upper = np.ones(n_assets) * 2
        else:
            # Par défaut: long only
            lower = np.zeros(n_assets)
            upper = np.ones(n_assets)
        
        # Ajustement pour les contraintes de poids
        if ConstraintType.MAX_WEIGHT in constraints:
            max_w = self.config.get("max_weights", 0.3)
            upper = np.minimum(upper, max_w)
        
        if ConstraintType.MIN_WEIGHT in constraints:
            min_w = self.config.get("min_weights", 0.01)
            lower = np.maximum(lower, min_w)
        
        return Bounds(lower, upper)
    
    # ========== MÉTHODES PRIVÉES - MÉTRIQUES ==========
    
    async def _calculate_sortino(self, weights: np.ndarray, returns: np.ndarray) -> float:
        """Calcule le ratio de Sortino."""
        portfolio_returns = np.dot(returns.T, weights) if len(returns.shape) > 1 else returns * weights
        downside_returns = portfolio_returns[portfolio_returns < 0]
        
        if len(downside_returns) == 0:
            return 0
        
        downside_vol = np.std(downside_returns)
        if downside_vol == 0:
            return 0
        
        portfolio_return = np.mean(portfolio_returns)
        risk_free_rate = self.config["risk_free_rate"]
        
        return (portfolio_return - risk_free_rate) / downside_vol
    
    async def _calculate_calmar(self, weights: np.ndarray, returns: np.ndarray) -> float:
        """Calcule le ratio de Calmar."""
        portfolio_returns = np.dot(returns.T, weights) if len(returns.shape) > 1 else returns * weights
        
        portfolio_return = np.mean(portfolio_returns)
        max_drawdown = await self._calculate_max_drawdown(weights, returns)
        
        if max_drawdown == 0:
            return 0
        
        return portfolio_return / max_drawdown
    
    async def _calculate_max_drawdown(self, weights: np.ndarray, returns: np.ndarray) -> float:
        """Calcule le drawdown maximum."""
        portfolio_returns = np.dot(returns.T, weights) if len(returns.shape) > 1 else returns * weights
        
        cumulative = np.cumprod(1 + portfolio_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        
        return abs(np.min(drawdown))
    
    async def _calculate_diversification(self, weights: np.ndarray, returns: np.ndarray) -> float:
        """Calcule le ratio de diversification."""
        # Ratio de diversification: volatilité pondérée / volatilité du portefeuille
        weighted_vol = np.sum(weights * np.std(returns, axis=0) if len(returns.shape) > 1 else np.std(returns))
        portfolio_vol = np.std(np.dot(returns.T, weights) if len(returns.shape) > 1 else returns * weights)
        
        if portfolio_vol == 0:
            return 1.0
        
        return weighted_vol / portfolio_vol
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._calculation_cache) > self.config["cache_size"]:
                        keys = list(self._calculation_cache.keys())
                        for key in keys[:len(self._calculation_cache) - self.config["cache_size"]]:
                            del self._calculation_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._portfolios_lock:
                    self._stats["total_portfolios"] = len(self._portfolios)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "sharpe:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """Récupère un portefeuille."""
        with self._portfolios_lock:
            return self._portfolios.get(portfolio_id)
    
    async def get_portfolios(self) -> List[Portfolio]:
        """Récupère les portefeuilles."""
        with self._portfolios_lock:
            return list(self._portfolios.values())
    
    async def get_result(self, result_id: str) -> Optional[OptimizationResult]:
        """Récupère un résultat d'optimisation."""
        with self._results_lock:
            return self._results.get(result_id)
    
    async def get_results(self) -> List[OptimizationResult]:
        """Récupère les résultats d'optimisation."""
        with self._results_lock:
            return list(self._results.values())
    
    async def rebalance_portfolio(
        self,
        portfolio_id: str,
        current_weights: Dict[str, float]
    ) -> OptimizationResult:
        """Rééquilibre un portefeuille."""
        portfolio = await self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        
        # Calcul de la rotation
        turnover = sum(abs(portfolio.weights.get(s, 0) - current_weights.get(s, 0)) for s in set(portfolio.weights) | set(current_weights))
        portfolio.turnover = turnover
        
        # Optimisation avec contrainte de rotation
        constraints = portfolio.constraints + [ConstraintType.MAX_TURNOVER]
        
        # Récupération des actifs
        assets = []
        for symbol in portfolio.weights:
            # Dans un système réel, on récupérerait les données des actifs
            asset = Asset(symbol=symbol, expected_return=0.1, volatility=0.2)
            assets.append(asset)
        
        # Optimisation
        return await self.optimize(assets, portfolio.optimization_objective, constraints)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._portfolios_lock:
            self._stats["total_portfolios"] = len(self._portfolios)
        with self._results_lock:
            self._stats["total_results"] = len(self._results)
        
        return self._stats.copy()


# ============== EFFICIENT FRONTIER ==============

class EfficientFrontier:
    """
    Calculateur de frontière efficiente.
    Génère la frontière efficiente pour un ensemble d'actifs.
    """
    
    def __init__(self, optimizer: SharpeOptimizer):
        self.optimizer = optimizer
        self._frontier_cache: Dict[str, List[Dict[str, float]]] = {}
        self._cache_lock = threading.RLock()
    
    async def compute(
        self,
        assets: List[Asset],
        points: int = 50
    ) -> List[Dict[str, float]]:
        """Calcule la frontière efficiente."""
        returns = np.array([a.returns for a in assets])
        expected_returns = np.array([a.expected_return for a in assets])
        cov_matrix = np.cov(returns)
        
        frontier = []
        min_return = np.min(expected_returns)
        max_return = np.max(expected_returns)
        
        for target_return in np.linspace(min_return, max_return, points):
            # Minimisation de la volatilité pour un rendement cible
            n_assets = len(assets)
            
            def objective(weights):
                return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            
            constraints = [
                {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
                {'type': 'eq', 'fun': lambda x: np.sum(x * expected_returns) - target_return}
            ]
            
            bounds = Bounds(0, 1)  # Long only
            
            x0 = np.ones(n_assets) / n_assets
            result = minimize(
                objective,
                x0,
                method='SLSQP',
                constraints=constraints,
                bounds=bounds,
                options={'maxiter': 1000, 'ftol': 1e-6}
            )
            
            if result.success:
                frontier.append({
                    'return': target_return,
                    'volatility': result.fun,
                    'sharpe': await self.optimizer.calculate_sharpe(result.x, returns)
                })
        
        return frontier


# ============== FACTORY ==============

class SharpeOptimizerFactory:
    """Factory pour créer des composants d'optimisation."""
    
    @staticmethod
    async def create_optimizer(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> SharpeOptimizer:
        """Crée un optimiseur de Sharpe."""
        optimizer = SharpeOptimizer(
            data_manager=data_manager,
            config=config
        )
        await optimizer.start()
        return optimizer
    
    @staticmethod
    def create_frontier(optimizer: SharpeOptimizer) -> EfficientFrontier:
        """Crée un calculateur de frontière efficiente."""
        return EfficientFrontier(optimizer)


# ============== EXPORT ==============

__all__ = [
    "OptimizationObjective",
    "ConstraintType",
    "RiskParityMethod",
    "Asset",
    "Portfolio",
    "OptimizationResult",
    "SharpeOptimizerInterface",
    "SharpeOptimizer",
    "EfficientFrontier",
    "SharpeOptimizerFactory"
]
