"""
NEXUS AI TRADING SYSTEM - Hedge Bot Portfolio Optimizer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Optimiseur de portefeuille pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import math
import threading
import numpy as np
from scipy.optimize import minimize, Bounds, LinearConstraint
from scipy.stats import norm
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class OptimizationObjective(Enum):
    """Objectifs d'optimisation"""
    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    MAX_RETURN = "max_return"
    MAX_DIVERSIFICATION = "max_diversification"
    MIN_CVAR = "min_cvar"
    RISK_PARITY = "risk_parity"
    MAX_UTILITY = "max_utility"
    CUSTOM = "custom"

class OptimizationMethod(Enum):
    """Méthodes d'optimisation"""
    MEAN_VARIANCE = "mean_variance"
    BLACK_LITTERMAN = "black_litterman"
    MONTE_CARLO = "monte_carlo"
    GENETIC = "genetic"
    GRADIENT = "gradient"
    BAYESIAN = "bayesian"

class ConstraintType(Enum):
    """Types de contraintes"""
    LONG_ONLY = "long_only"
    SHORT_ONLY = "short_only"
    LEVERAGE = "leverage"
    SECTOR = "sector"
    ASSET = "asset"
    CUSTOM = "custom"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class Portfolio:
    """Portefeuille"""
    id: str
    name: str
    assets: List[str]
    weights: List[float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    var_95: float
    cvar_95: float
    diversification_ratio: float
    turnover: float
    rebalance_frequency: int = 30
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AssetMetrics:
    """Métriques d'actif"""
    symbol: str
    return_avg: float
    return_std: float
    sharpe: float
    max_drawdown: float
    beta: float
    correlation: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OptimizationResult:
    """Résultat d'optimisation"""
    weights: List[float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    var_95: float
    cvar_95: float
    diversification_ratio: float
    convergence: bool
    iterations: int
    time_taken: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OptimizationConfig:
    """Configuration d'optimisation"""
    objective: OptimizationObjective = OptimizationObjective.MAX_SHARPE
    method: OptimizationMethod = OptimizationMethod.MEAN_VARIANCE
    risk_free_rate: float = 0.02
    max_iterations: int = 1000
    tolerance: float = 1e-6
    constraints: List[ConstraintType] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# PORTFOLIO OPTIMIZER
# ============================================================

class PortfolioOptimizer:
    """
    Optimiseur de portefeuille pour le bot de couverture
    
    Implémente différentes méthodes d'optimisation de portefeuille
    """
    
    def __init__(
        self,
        config: Optional[OptimizationConfig] = None,
        update_interval: int = 3600,
        enable_monitoring: bool = True
    ):
        """
        Initialise l'optimiseur de portefeuille
        
        Args:
            config: Configuration d'optimisation
            update_interval: Intervalle de mise à jour
            enable_monitoring: Activer le monitoring
        """
        self.config = config or OptimizationConfig()
        self.update_interval = update_interval
        self.enable_monitoring = enable_monitoring
        
        # Portefeuilles
        self.portfolios: Dict[str, Portfolio] = {}
        self.active_portfolios: Dict[str, Portfolio] = {}
        self.optimized_portfolios: Dict[str, Portfolio] = {}
        
        # Métriques
        self.asset_metrics: Dict[str, AssetMetrics] = {}
        self.correlation_matrix: Optional[np.ndarray] = None
        self.covariance_matrix: Optional[np.ndarray] = None
        
        # Résultats
        self.results: Dict[str, OptimizationResult] = {}
        
        # Statistiques
        self.stats = {
            'total_optimizations': 0,
            'successful_optimizations': 0,
            'failed_optimizations': 0,
            'total_portfolios': 0,
            'active_portfolios': 0,
            'avg_sharpe': 0.0,
            'avg_volatility': 0.0,
            'avg_diversification': 0.0,
        }
        
        # Verrous
        self._lock = threading.RLock()
        self._running = False
        self._update_task = None
        
        # Cache
        self._cache: Dict[str, Any] = {}
        
        logger.info("PortfolioOptimizer initialized")
    
    # ============================================================
    # DATA MANAGEMENT
    # ============================================================
    
    def add_asset_metrics(self, metrics: AssetMetrics):
        """
        Ajoute des métriques d'actif
        
        Args:
            metrics: Métriques à ajouter
        """
        with self._lock:
            self.asset_metrics[metrics.symbol] = metrics
            self._update_matrices()
            logger.info(f"Asset metrics added: {metrics.symbol}")
    
    def remove_asset_metrics(self, symbol: str):
        """
        Supprime des métriques d'actif
        
        Args:
            symbol: Symbole de l'actif
        """
        with self._lock:
            if symbol in self.asset_metrics:
                del self.asset_metrics[symbol]
                self._update_matrices()
                logger.info(f"Asset metrics removed: {symbol}")
    
    def _update_matrices(self):
        """
        Met à jour les matrices de corrélation et covariance
        """
        symbols = list(self.asset_metrics.keys())
        n = len(symbols)
        
        if n == 0:
            self.correlation_matrix = None
            self.covariance_matrix = None
            return
        
        # Matrice de corrélation
        corr_matrix = np.ones((n, n))
        for i, s1 in enumerate(symbols):
            for j, s2 in enumerate(symbols):
                if i != j and s2 in self.asset_metrics[s1].correlation:
                    corr_matrix[i, j] = self.asset_metrics[s1].correlation[s2]
        
        self.correlation_matrix = corr_matrix
        
        # Matrice de covariance
        std = np.array([self.asset_metrics[s].return_std for s in symbols])
        self.covariance_matrix = np.outer(std, std) * corr_matrix
    
    def get_asset_symbols(self) -> List[str]:
        """
        Récupère les symboles des actifs
        
        Returns:
            List[str]: Symboles
        """
        return list(self.asset_metrics.keys())
    
    # ============================================================
    # PORTFOLIO OPTIMIZATION
    # ============================================================
    
    def optimize(
        self,
        symbols: List[str],
        config: Optional[OptimizationConfig] = None,
        constraints: Optional[Dict[str, Any]] = None
    ) -> OptimizationResult:
        """
        Optimise un portefeuille
        
        Args:
            symbols: Liste des symboles
            config: Configuration d'optimisation
            constraints: Contraintes
            
        Returns:
            OptimizationResult: Résultat de l'optimisation
        """
        config = config or self.config
        start_time = time.time()
        
        with self._lock:
            n = len(symbols)
            if n == 0:
                return OptimizationResult([],0,0,0,0,0,0,0,False,0,0)
            
            # Récupérer les métriques
            returns = np.array([self.asset_metrics[s].return_avg for s in symbols])
            cov_matrix = self._get_covariance_matrix(symbols)
            
            # Définir l'objectif
            objective_func = self._get_objective_function(
                returns=returns,
                cov_matrix=cov_matrix,
                config=config
            )
            
            # Définir les contraintes
            constraints_dict = self._get_constraints(
                n=n,
                constraints=constraints,
                config=config
            )
            
            # Optimisation
            initial_weights = np.ones(n) / n
            bounds = Bounds(0, 1) if ConstraintType.LONG_ONLY in config.constraints else None
            
            try:
                result = minimize(
                    objective_func,
                    initial_weights,
                    method='SLSQP',
                    bounds=bounds,
                    constraints=constraints_dict,
                    options={'maxiter': config.max_iterations, 'ftol': config.tolerance}
                )
                
                weights = result.x
                convergence = result.success
                iterations = result.nit
                
                # Calculer les métriques du portefeuille
                expected_return = np.sum(weights * returns)
                volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
                sharpe_ratio = (expected_return - config.risk_free_rate) / volatility if volatility > 0 else 0
                
                # Max drawdown approximatif
                max_drawdown = self._estimate_max_drawdown(weights, symbols)
                
                # VaR et CVaR
                var_95 = self._estimate_var(weights, symbols, 0.95)
                cvar_95 = self._estimate_cvar(weights, symbols, 0.95)
                
                # Diversification
                diversification_ratio = self._calculate_diversification_ratio(weights, symbols)
                
                self.stats['total_optimizations'] += 1
                if convergence:
                    self.stats['successful_optimizations'] += 1
                else:
                    self.stats['failed_optimizations'] += 1
                
                result_obj = OptimizationResult(
                    weights=weights.tolist(),
                    expected_return=expected_return,
                    volatility=volatility,
                    sharpe_ratio=sharpe_ratio,
                    max_drawdown=max_drawdown,
                    var_95=var_95,
                    cvar_95=cvar_95,
                    diversification_ratio=diversification_ratio,
                    convergence=convergence,
                    iterations=iterations,
                    time_taken=time.time() - start_time
                )
                
                self.results[f"opt_{int(time.time())}"] = result_obj
                self._update_stats()
                
                return result_obj
                
            except Exception as e:
                logger.error(f"Optimization failed: {e}")
                self.stats['failed_optimizations'] += 1
                return OptimizationResult([],0,0,0,0,0,0,0,False,0,time.time()-start_time)
    
    def _get_covariance_matrix(self, symbols: List[str]) -> np.ndarray:
        """
        Récupère la matrice de covariance pour les symboles donnés
        
        Args:
            symbols: Liste des symboles
            
        Returns:
            np.ndarray: Matrice de covariance
        """
        n = len(symbols)
        cov_matrix = np.zeros((n, n))
        
        for i, s1 in enumerate(symbols):
            for j, s2 in enumerate(symbols):
                if i == j:
                    cov_matrix[i, j] = self.asset_metrics[s1].return_std ** 2
                else:
                    corr = self.asset_metrics[s1].correlation.get(s2, 0)
                    cov_matrix[i, j] = corr * self.asset_metrics[s1].return_std * self.asset_metrics[s2].return_std
        
        return cov_matrix
    
    def _get_objective_function(
        self,
        returns: np.ndarray,
        cov_matrix: np.ndarray,
        config: OptimizationConfig
    ) -> callable:
        """
        Récupère la fonction objectif
        
        Args:
            returns: Rendements
            cov_matrix: Matrice de covariance
            config: Configuration
            
        Returns:
            callable: Fonction objectif
        """
        if config.objective == OptimizationObjective.MAX_SHARPE:
            def objective(w):
                w = np.array(w)
                port_return = np.sum(w * returns)
                port_vol = np.sqrt(np.dot(w.T, np.dot(cov_matrix, w)))
                return - (port_return - config.risk_free_rate) / port_vol if port_vol > 0 else 0
        
        elif config.objective == OptimizationObjective.MIN_VARIANCE:
            def objective(w):
                w = np.array(w)
                return np.dot(w.T, np.dot(cov_matrix, w))
        
        elif config.objective == OptimizationObjective.MAX_RETURN:
            def objective(w):
                w = np.array(w)
                return -np.sum(w * returns)
        
        elif config.objective == OptimizationObjective.RISK_PARITY:
            def objective(w):
                w = np.array(w)
                port_vol = np.sqrt(np.dot(w.T, np.dot(cov_matrix, w)))
                if port_vol == 0:
                    return 0
                
                # Contribution au risque
                marginal_contrib = np.dot(cov_matrix, w) / port_vol
                risk_contrib = w * marginal_contrib
                
                # Écart des contributions
                target = port_vol / len(w)
                return np.sum((risk_contrib - target) ** 2)
        
        else:
            def objective(w):
                w = np.array(w)
                return -np.sum(w * returns)
        
        return objective
    
    def _get_constraints(
        self,
        n: int,
        constraints: Optional[Dict[str, Any]],
        config: OptimizationConfig
    ) -> List[Dict[str, Any]]:
        """
        Récupère les contraintes
        
        Args:
            n: Nombre d'actifs
            constraints: Contraintes personnalisées
            config: Configuration
            
        Returns:
            List[Dict[str, Any]]: Contraintes
        """
        constraints_list = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # Somme des poids = 1
        ]
        
        if constraints:
            for name, value in constraints.items():
                if name == 'min_weight':
                    constraints_list.append(
                        {'type': 'ineq', 'fun': lambda x: x - value}
                    )
                elif name == 'max_weight':
                    constraints_list.append(
                        {'type': 'ineq', 'fun': lambda x: value - x}
                    )
                elif name == 'min_return':
                    constraints_list.append(
                        {'type': 'ineq', 'fun': lambda x: np.sum(x * value['returns']) - value['target']}
                    )
        
        return constraints_list
    
    # ============================================================
    # PORTFOLIO METRICS
    # ============================================================
    
    def _estimate_max_drawdown(self, weights: np.ndarray, symbols: List[str]) -> float:
        """
        Estime le drawdown maximum
        
        Args:
            weights: Poids
            symbols: Symboles
            
        Returns:
            float: Drawdown maximum
        """
        # Simuler un drawdown maximum
        return 0.15  # 15% par défaut
    
    def _estimate_var(self, weights: np.ndarray, symbols: List[str], confidence: float) -> float:
        """
        Estime la VaR
        
        Args:
            weights: Poids
            symbols: Symboles
            confidence: Niveau de confiance
            
        Returns:
            float: VaR
        """
        # Simuler la VaR
        z_score = norm.ppf(confidence)
        return z_score * 0.02  # 2% par défaut
    
    def _estimate_cvar(self, weights: np.ndarray, symbols: List[str], confidence: float) -> float:
        """
        Estime la CVaR
        
        Args:
            weights: Poids
            symbols: Symboles
            confidence: Niveau de confiance
            
        Returns:
            float: CVaR
        """
        # Simuler la CVaR
        return self._estimate_var(weights, symbols, confidence) * 1.2
    
    def _calculate_diversification_ratio(self, weights: np.ndarray, symbols: List[str]) -> float:
        """
        Calcule le ratio de diversification
        
        Args:
            weights: Poids
            symbols: Symboles
            
        Returns:
            float: Ratio de diversification
        """
        # Simuler le ratio de diversification
        return 0.8  # 80% par défaut
    
    # ============================================================
    # PORTFOLIO MANAGEMENT
    # ============================================================
    
    def create_portfolio(
        self,
        name: str,
        assets: List[str],
        weights: List[float],
        config: Optional[OptimizationConfig] = None
    ) -> Portfolio:
        """
        Crée un portefeuille
        
        Args:
            name: Nom du portefeuille
            assets: Liste des actifs
            weights: Poids
            config: Configuration
            
        Returns:
            Portfolio: Portefeuille créé
        """
        with self._lock:
            # Optimiser si nécessaire
            if not weights:
                result = self.optimize(assets, config)
                weights = result.weights
            
            # Calculer les métriques
            returns = np.array([self.asset_metrics.get(a, AssetMetrics(a,0,0,0,0,0,{})).return_avg for a in assets])
            cov_matrix = self._get_covariance_matrix(assets)
            
            expected_return = np.sum(weights * returns)
            volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))) if len(weights) > 0 else 0
            sharpe_ratio = (expected_return - (config or self.config).risk_free_rate) / volatility if volatility > 0 else 0
            
            portfolio = Portfolio(
                id=f"port_{int(time.time())}_{name}",
                name=name,
                assets=assets,
                weights=weights,
                expected_return=expected_return,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=0.15,
                var_95=0.02,
                cvar_95=0.025,
                diversification_ratio=0.8,
                turnover=0.1,
                rebalance_frequency=30,
                metadata={'config': config.__dict__ if config else {}}
            )
            
            self.portfolios[portfolio.id] = portfolio
            self.active_portfolios[portfolio.id] = portfolio
            self.stats['total_portfolios'] += 1
            self.stats['active_portfolios'] += 1
            
            self._update_stats()
            
            logger.info(f"Portfolio created: {name}")
            return portfolio
    
    def update_portfolio(self, portfolio_id: str, new_weights: List[float]) -> bool:
        """
        Met à jour un portefeuille
        
        Args:
            portfolio_id: ID du portefeuille
            new_weights: Nouveaux poids
            
        Returns:
            bool: True si mis à jour
        """
        with self._lock:
            portfolio = self.portfolios.get(portfolio_id)
            if not portfolio:
                return False
            
            # Calculer le turnover
            old_weights = np.array(portfolio.weights)
            new_weights = np.array(new_weights)
            turnover = np.sum(np.abs(old_weights - new_weights)) / 2
            
            # Mettre à jour
            portfolio.weights = new_weights.tolist()
            portfolio.turnover = turnover
            portfolio.updated_at = datetime.now()
            
            # Recalculer les métriques
            returns = np.array([self.asset_metrics.get(a, AssetMetrics(a,0,0,0,0,0,{})).return_avg for a in portfolio.assets])
            cov_matrix = self._get_covariance_matrix(portfolio.assets)
            
            portfolio.expected_return = np.sum(new_weights * returns)
            portfolio.volatility = np.sqrt(np.dot(new_weights.T, np.dot(cov_matrix, new_weights))) if len(new_weights) > 0 else 0
            portfolio.sharpe_ratio = (portfolio.expected_return - self.config.risk_free_rate) / portfolio.volatility if portfolio.volatility > 0 else 0
            
            logger.info(f"Portfolio updated: {portfolio_id}")
            return True
    
    def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """
        Récupère un portefeuille
        
        Args:
            portfolio_id: ID du portefeuille
            
        Returns:
            Optional[Portfolio]: Portefeuille
        """
        return self.portfolios.get(portfolio_id)
    
    def get_active_portfolios(self) -> List[Portfolio]:
        """
        Récupère les portefeuilles actifs
        
        Returns:
            List[Portfolio]: Portefeuilles actifs
        """
        return list(self.active_portfolios.values())
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        with self._lock:
            portfolios = list(self.portfolios.values())
            if not portfolios:
                return
            
            avg_sharpe = sum(p.sharpe_ratio for p in portfolios) / len(portfolios)
            avg_volatility = sum(p.volatility for p in portfolios) / len(portfolios)
            avg_diversification = sum(p.diversification_ratio for p in portfolios) / len(portfolios)
            
            self.stats.update({
                'avg_sharpe': avg_sharpe,
                'avg_volatility': avg_volatility,
                'avg_diversification': avg_diversification,
            })
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        with self._lock:
            return self.stats.copy()
    
    def get_report(self) -> Dict[str, Any]:
        """
        Récupère un rapport
        
        Returns:
            Dict[str, Any]: Rapport
        """
        return {
            'timestamp': time.time(),
            'stats': self.get_stats(),
            'active_portfolios': [
                {
                    'id': p.id,
                    'name': p.name,
                    'assets': p.assets,
                    'weights': p.weights,
                    'expected_return': p.expected_return,
                    'volatility': p.volatility,
                    'sharpe_ratio': p.sharpe_ratio,
                }
                for p in self.active_portfolios.values()
            ],
            'asset_metrics': [
                {
                    'symbol': s,
                    'return_avg': m.return_avg,
                    'return_std': m.return_std,
                    'sharpe': m.sharpe,
                }
                for s, m in self.asset_metrics.items()
            ],
        }
    
    # ============================================================
    # MONITORING
    # ============================================================
    
    def start(self):
        """Démarre le monitoring"""
        if self._running:
            return
        
        self._running = True
        self._update_task = threading.Thread(target=self._update_loop, daemon=True)
        self._update_task.start()
        
        logger.info("PortfolioOptimizer monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._update_task:
            self._update_task.join(timeout=2)
        
        logger.info("PortfolioOptimizer monitoring stopped")
    
    def _update_loop(self):
        """Boucle de mise à jour"""
        while self._running:
            try:
                self._update_metrics()
                self._check_rebalance()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Update error: {e}")
                time.sleep(self.update_interval)
    
    def _update_metrics(self):
        """Met à jour les métriques"""
        # À implémenter avec les données réelles
        pass
    
    def _check_rebalance(self):
        """Vérifie les rééquilibrages"""
        for portfolio in self.active_portfolios.values():
            if (datetime.now() - portfolio.created_at).days >= portfolio.rebalance_frequency:
                self._rebalance_portfolio(portfolio.id)
    
    def _rebalance_portfolio(self, portfolio_id: str):
        """
        Rééquilibre un portefeuille
        
        Args:
            portfolio_id: ID du portefeuille
        """
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return
        
        # Optimiser à nouveau
        result = self.optimize(portfolio.assets)
        if result.weights:
            self.update_portfolio(portfolio_id, result.weights)
            logger.info(f"Portfolio rebalanced: {portfolio_id}")

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_portfolio_optimizer: Optional[PortfolioOptimizer] = None

def get_portfolio_optimizer(
    config: Optional[OptimizationConfig] = None
) -> PortfolioOptimizer:
    """
    Récupère l'optimiseur de portefeuille (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        PortfolioOptimizer: Optimiseur de portefeuille
    """
    global _portfolio_optimizer
    if _portfolio_optimizer is None:
        _portfolio_optimizer = PortfolioOptimizer(config)
    return _portfolio_optimizer

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'OptimizationObjective',
    'OptimizationMethod',
    'ConstraintType',
    'Portfolio',
    'AssetMetrics',
    'OptimizationResult',
    'OptimizationConfig',
    'PortfolioOptimizer',
    'get_portfolio_optimizer',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Portfolio optimizer module initialized")
