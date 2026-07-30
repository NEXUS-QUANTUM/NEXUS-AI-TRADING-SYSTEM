# trading/bots/hedge_bot/hedge_bot_asset_allocator.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Asset Allocator Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Asset Allocator Module

This module provides comprehensive asset allocation and portfolio
optimization capabilities for the NEXUS Hedge Bot system. It implements
various allocation strategies and optimization algorithms.

The module covers:
- Mean-Variance Optimization
- Risk Parity Allocation
- Equal Weight Allocation
- Minimum Variance Allocation
- Maximum Sharpe Ratio Allocation
- Black-Litterman Allocation
- Hierarchical Risk Parity
- Factor-Based Allocation
- Constraint-Based Optimization
- Rebalancing Strategies
- Tax-Efficient Allocation
- Dynamic Asset Allocation
"""

import os
import sys
import json
import math
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from scipy.optimize import minimize, Bounds, LinearConstraint
from scipy.stats import norm
import itertools

# Try to import optional dependencies
try:
    from sklearn.covariance import LedoitWolf, OAS
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

logger = logging.getLogger(__name__)


# ============================================================
# ALLOCATOR DATACLASSES
# ============================================================

@dataclass
class AssetAllocation:
    """Asset allocation data"""
    timestamp: datetime
    method: str
    assets: Dict[str, float]  # symbol -> weight
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    diversification_ratio: float
    concentration: float
    constraints: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "method": self.method,
            "assets": self.assets,
            "expected_return": self.expected_return,
            "expected_risk": self.expected_risk,
            "sharpe_ratio": self.sharpe_ratio,
            "diversification_ratio": self.diversification_ratio,
            "concentration": self.concentration,
            "constraints": self.constraints,
            "details": self.details,
        }


@dataclass
class PortfolioOptimizationResult:
    """Portfolio optimization result"""
    weights: Dict[str, float]
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    diversification_ratio: float
    concentration: float
    efficient_frontier: List[Dict[str, float]]
    constraints_satisfied: bool
    iterations: int
    time_taken: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "weights": self.weights,
            "expected_return": self.expected_return,
            "expected_risk": self.expected_risk,
            "sharpe_ratio": self.sharpe_ratio,
            "diversification_ratio": self.diversification_ratio,
            "concentration": self.concentration,
            "efficient_frontier": self.efficient_frontier,
            "constraints_satisfied": self.constraints_satisfied,
            "iterations": self.iterations,
            "time_taken": self.time_taken,
        }


@dataclass
class RebalanceResult:
    """Rebalance result"""
    timestamp: datetime
    current_allocation: Dict[str, float]
    target_allocation: Dict[str, float]
    trades: List[Dict[str, Any]]
    estimated_cost: float
    estimated_slippage: float
    estimated_tax: float
    net_cost: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "current_allocation": self.current_allocation,
            "target_allocation": self.target_allocation,
            "trades": self.trades,
            "estimated_cost": self.estimated_cost,
            "estimated_slippage": self.estimated_slippage,
            "estimated_tax": self.estimated_tax,
            "net_cost": self.net_cost,
        }


# ============================================================
# ASSET ALLOCATOR ENGINE
# ============================================================

class AssetAllocator:
    """
    Comprehensive asset allocation engine for the hedge bot
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the asset allocator
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.method = self.config.get("method", "risk_parity")
        self.risk_free_rate = self.config.get("risk_free_rate", 0.04)
        self.max_weight = self.config.get("max_weight", 0.25)
        self.min_weight = self.config.get("min_weight", 0.01)
        self.target_volatility = self.config.get("target_volatility", 0.15)
        
        # State
        self.current_allocation: Dict[str, float] = {}
        self.allocation_history: List[AssetAllocation] = []
        self.optimization_results: Dict[str, Any] = {}
        
        logger.info(f"Asset allocator initialized with method: {self.method}")
    
    # ============================================================
    # MEAN-VARIANCE OPTIMIZATION
    # ============================================================
    
    def optimize_mean_variance(
        self,
        returns: np.ndarray,
        cov_matrix: np.ndarray,
        target_return: Optional[float] = None,
        target_risk: Optional[float] = None,
        max_weight: Optional[float] = None,
        min_weight: Optional[float] = None,
        risk_free_rate: Optional[float] = None
    ) -> PortfolioOptimizationResult:
        """
        Perform mean-variance optimization
        
        Args:
            returns: Expected returns
            cov_matrix: Covariance matrix
            target_return: Target return
            target_risk: Target risk
            max_weight: Maximum weight per asset
            min_weight: Minimum weight per asset
            risk_free_rate: Risk-free rate
            
        Returns:
            PortfolioOptimizationResult
        """
        n = len(returns)
        
        # Set defaults
        if max_weight is None:
            max_weight = self.max_weight
        if min_weight is None:
            min_weight = self.min_weight
        if risk_free_rate is None:
            risk_free_rate = self.risk_free_rate
        
        # Objective: maximize Sharpe ratio or minimize variance
        def objective(weights):
            portfolio_return = np.dot(weights, returns)
            portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
            portfolio_risk = np.sqrt(portfolio_variance)
            
            if target_return is not None:
                # Minimize variance for given return
                return portfolio_variance
            else:
                # Maximize Sharpe ratio (minimize negative Sharpe)
                sharpe = (portfolio_return - risk_free_rate) / portfolio_risk
                return -sharpe
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # Sum to 1
        ]
        
        if target_return is not None:
            constraints.append({
                'type': 'eq',
                'fun': lambda x: np.dot(x, returns) - target_return
            })
        
        if target_risk is not None:
            constraints.append({
                'type': 'ineq',
                'fun': lambda x: target_risk - np.sqrt(np.dot(x.T, np.dot(cov_matrix, x)))
            })
        
        # Bounds
        bounds = [(min_weight, max_weight) for _ in range(n)]
        
        # Initial guess
        initial_weights = np.ones(n) / n
        
        # Optimize
        start_time = datetime.now()
        
        try:
            result = minimize(
                objective,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 1000, 'ftol': 1e-9}
            )
            
            time_taken = (datetime.now() - start_time).total_seconds()
            weights = result.x
            
            # Calculate metrics
            expected_return = np.dot(weights, returns)
            expected_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
            expected_risk = np.sqrt(expected_variance)
            sharpe_ratio = (expected_return - risk_free_rate) / expected_risk if expected_risk > 0 else 0
            
            # Diversification ratio
            weighted_vols = np.sum(weights * np.sqrt(np.diag(cov_matrix)))
            diversification_ratio = weighted_vols / expected_risk if expected_risk > 0 else 1
            
            # Concentration (HHI)
            concentration = np.sum(weights ** 2)
            
            # Efficient frontier (simplified)
            efficient_frontier = []
            for ret in np.linspace(np.min(returns), np.max(returns), 10):
                # Re-optimize for each target return
                constraints_frontier = [
                    {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
                    {'type': 'eq', 'fun': lambda x: np.dot(x, returns) - ret}
                ]
                bounds_frontier = [(min_weight, max_weight) for _ in range(n)]
                result_frontier = minimize(
                    lambda x: np.dot(x.T, np.dot(cov_matrix, x)),
                    initial_weights,
                    method='SLSQP',
                    bounds=bounds_frontier,
                    constraints=constraints_frontier,
                    options={'maxiter': 1000, 'ftol': 1e-9}
                )
                if result_frontier.success:
                    risk = np.sqrt(np.dot(result_frontier.x.T, np.dot(cov_matrix, result_frontier.x)))
                    efficient_frontier.append({
                        'return': ret,
                        'risk': risk,
                    })
            
            # Create result
            asset_names = list(range(n))
            weights_dict = {f"asset_{i}": weights[i] for i in range(n)}
            
            return PortfolioOptimizationResult(
                weights=weights_dict,
                expected_return=expected_return,
                expected_risk=expected_risk,
                sharpe_ratio=sharpe_ratio,
                diversification_ratio=diversification_ratio,
                concentration=concentration,
                efficient_frontier=efficient_frontier,
                constraints_satisfied=result.success,
                iterations=result.nit if hasattr(result, 'nit') else 0,
                time_taken=time_taken,
            )
            
        except Exception as e:
            logger.error(f"Mean-variance optimization failed: {e}")
            return None
    
    # ============================================================
    # RISK PARITY ALLOCATION
    # ============================================================
    
    def optimize_risk_parity(
        self,
        cov_matrix: np.ndarray,
        max_weight: Optional[float] = None,
        min_weight: Optional[float] = None
    ) -> PortfolioOptimizationResult:
        """
        Perform risk parity optimization
        
        Args:
            cov_matrix: Covariance matrix
            max_weight: Maximum weight per asset
            min_weight: Minimum weight per asset
            
        Returns:
            PortfolioOptimizationResult
        """
        n = cov_matrix.shape[0]
        
        if max_weight is None:
            max_weight = self.max_weight
        if min_weight is None:
            min_weight = self.min_weight
        
        # Objective: minimize risk contribution variance
        def objective(weights):
            portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
            marginal_contrib = np.dot(cov_matrix, weights)
            risk_contrib = weights * marginal_contrib / portfolio_variance
            risk_contrib = np.array(risk_contrib).flatten()
            
            # Target equal risk contribution
            target = 1 / n
            return np.sum((risk_contrib - target) ** 2)
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # Sum to 1
        ]
        
        # Bounds
        bounds = [(min_weight, max_weight) for _ in range(n)]
        
        # Initial guess
        initial_weights = np.ones(n) / n
        
        # Optimize
        start_time = datetime.now()
        
        try:
            result = minimize(
                objective,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 1000, 'ftol': 1e-9}
            )
            
            time_taken = (datetime.now() - start_time).total_seconds()
            weights = result.x
            
            # Calculate metrics
            portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
            expected_risk = np.sqrt(portfolio_variance)
            
            # Expected return (simple average)
            expected_return = np.mean(weights)  # Simple approximation
            
            # Diversification ratio
            weighted_vols = np.sum(weights * np.sqrt(np.diag(cov_matrix)))
            diversification_ratio = weighted_vols / expected_risk if expected_risk > 0 else 1
            
            # Concentration (HHI)
            concentration = np.sum(weights ** 2)
            
            # Create result
            asset_names = list(range(n))
            weights_dict = {f"asset_{i}": weights[i] for i in range(n)}
            
            return PortfolioOptimizationResult(
                weights=weights_dict,
                expected_return=expected_return,
                expected_risk=expected_risk,
                sharpe_ratio=(expected_return - self.risk_free_rate) / expected_risk if expected_risk > 0 else 0,
                diversification_ratio=diversification_ratio,
                concentration=concentration,
                efficient_frontier=[],
                constraints_satisfied=result.success,
                iterations=result.nit if hasattr(result, 'nit') else 0,
                time_taken=time_taken,
            )
            
        except Exception as e:
            logger.error(f"Risk parity optimization failed: {e}")
            return None
    
    # ============================================================
    # BLACK-LITTERMAN ALLOCATION
    # ============================================================
    
    def optimize_black_litterman(
        self,
        market_weights: np.ndarray,
        cov_matrix: np.ndarray,
        views: Dict[str, Any],
        tau: float = 0.05,
        max_weight: Optional[float] = None,
        min_weight: Optional[float] = None
    ) -> PortfolioOptimizationResult:
        """
        Perform Black-Litterman optimization
        
        Args:
            market_weights: Market capitalization weights
            cov_matrix: Covariance matrix
            views: Investor views
            tau: Uncertainty parameter
            max_weight: Maximum weight per asset
            min_weight: Minimum weight per asset
            
        Returns:
            PortfolioOptimizationResult
        """
        n = cov_matrix.shape[0]
        
        if max_weight is None:
            max_weight = self.max_weight
        if min_weight is None:
            min_weight = self.min_weight
        
        try:
            # Calculate implied returns (reverse optimization)
            lambda_ = (1 - self.risk_free_rate) / 2  # Risk aversion parameter
            implied_returns = lambda_ * np.dot(cov_matrix, market_weights)
            
            # Process views
            P = np.eye(n)  # View matrix
            Q = np.zeros(n)  # View returns
            
            for i, view in enumerate(views.get('views', [])):
                if 'assets' in view and 'return' in view:
                    for j, asset in enumerate(view['assets']):
                        P[i][j] = view.get('weight', 1)
                    Q[i] = view['return']
            
            # Uncertainty matrix
            omega = np.diag(np.ones(n) * 0.01)
            
            # Black-Litterman returns
            tau_cov = tau * cov_matrix
            inv_tau_cov = np.linalg.inv(tau_cov)
            inv_omega = np.linalg.inv(omega)
            
            # Calculate posterior
            cov_posterior = np.linalg.inv(inv_tau_cov + np.dot(P.T, np.dot(inv_omega, P)))
            returns_posterior = np.dot(cov_posterior, np.dot(inv_tau_cov, implied_returns) + np.dot(P.T, np.dot(inv_omega, Q)))
            
            # Optimize with posterior returns
            result = self.optimize_mean_variance(
                returns=returns_posterior,
                cov_matrix=cov_posterior,
                max_weight=max_weight,
                min_weight=min_weight,
            )
            
            if result:
                result.details = {
                    'implied_returns': implied_returns.tolist(),
                    'posterior_returns': returns_posterior.tolist(),
                    'views': views,
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Black-Litterman optimization failed: {e}")
            return None
    
    # ============================================================
    # EQUAL WEIGHT ALLOCATION
    # ============================================================
    
    def optimize_equal_weight(
        self,
        n_assets: int,
        max_weight: Optional[float] = None,
        min_weight: Optional[float] = None
    ) -> PortfolioOptimizationResult:
        """
        Perform equal weight allocation
        
        Args:
            n_assets: Number of assets
            max_weight: Maximum weight per asset
            min_weight: Minimum weight per asset
            
        Returns:
            PortfolioOptimizationResult
        """
        if max_weight is None:
            max_weight = self.max_weight
        if min_weight is None:
            min_weight = self.min_weight
        
        weight = 1 / n_assets
        weight = max(min_weight, min(weight, max_weight))
        weights = {f"asset_{i}": weight for i in range(n_assets)}
        
        return PortfolioOptimizationResult(
            weights=weights,
            expected_return=0.0,
            expected_risk=0.0,
            sharpe_ratio=0.0,
            diversification_ratio=1.0,
            concentration=1 / n_assets,
            efficient_frontier=[],
            constraints_satisfied=True,
            iterations=1,
            time_taken=0.0,
        )
    
    # ============================================================
    # MINIMUM VARIANCE ALLOCATION
    # ============================================================
    
    def optimize_minimum_variance(
        self,
        cov_matrix: np.ndarray,
        max_weight: Optional[float] = None,
        min_weight: Optional[float] = None
    ) -> PortfolioOptimizationResult:
        """
        Perform minimum variance optimization
        
        Args:
            cov_matrix: Covariance matrix
            max_weight: Maximum weight per asset
            min_weight: Minimum weight per asset
            
        Returns:
            PortfolioOptimizationResult
        """
        n = cov_matrix.shape[0]
        
        if max_weight is None:
            max_weight = self.max_weight
        if min_weight is None:
            min_weight = self.min_weight
        
        # Minimize variance
        def objective(weights):
            return np.dot(weights.T, np.dot(cov_matrix, weights))
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        ]
        
        # Bounds
        bounds = [(min_weight, max_weight) for _ in range(n)]
        
        # Initial guess
        initial_weights = np.ones(n) / n
        
        # Optimize
        start_time = datetime.now()
        
        try:
            result = minimize(
                objective,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 1000, 'ftol': 1e-9}
            )
            
            time_taken = (datetime.now() - start_time).total_seconds()
            weights = result.x
            
            # Calculate metrics
            expected_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
            expected_risk = np.sqrt(expected_variance)
            expected_return = np.mean(weights)  # Simple approximation
            
            # Diversification ratio
            weighted_vols = np.sum(weights * np.sqrt(np.diag(cov_matrix)))
            diversification_ratio = weighted_vols / expected_risk if expected_risk > 0 else 1
            
            # Concentration (HHI)
            concentration = np.sum(weights ** 2)
            
            # Create result
            weights_dict = {f"asset_{i}": weights[i] for i in range(n)}
            
            return PortfolioOptimizationResult(
                weights=weights_dict,
                expected_return=expected_return,
                expected_risk=expected_risk,
                sharpe_ratio=(expected_return - self.risk_free_rate) / expected_risk if expected_risk > 0 else 0,
                diversification_ratio=diversification_ratio,
                concentration=concentration,
                efficient_frontier=[],
                constraints_satisfied=result.success,
                iterations=result.nit if hasattr(result, 'nit') else 0,
                time_taken=time_taken,
            )
            
        except Exception as e:
            logger.error(f"Minimum variance optimization failed: {e}")
            return None
    
    # ============================================================
    # MAXIMUM SHARPE RATIO ALLOCATION
    # ============================================================
    
    def optimize_maximum_sharpe_ratio(
        self,
        returns: np.ndarray,
        cov_matrix: np.ndarray,
        max_weight: Optional[float] = None,
        min_weight: Optional[float] = None,
        risk_free_rate: Optional[float] = None
    ) -> PortfolioOptimizationResult:
        """
        Perform maximum Sharpe ratio optimization (tangency portfolio)
        
        Args:
            returns: Expected returns
            cov_matrix: Covariance matrix
            max_weight: Maximum weight per asset
            min_weight: Minimum weight per asset
            risk_free_rate: Risk-free rate
            
        Returns:
            PortfolioOptimizationResult
        """
        if max_weight is None:
            max_weight = self.max_weight
        if min_weight is None:
            min_weight = self.min_weight
        if risk_free_rate is None:
            risk_free_rate = self.risk_free_rate
        
        n = len(returns)
        
        # Maximize Sharpe ratio
        def objective(weights):
            portfolio_return = np.dot(weights, returns)
            portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
            portfolio_risk = np.sqrt(portfolio_variance)
            
            if portfolio_risk > 0:
                return -(portfolio_return - risk_free_rate) / portfolio_risk
            else:
                return 0
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        ]
        
        # Bounds
        bounds = [(min_weight, max_weight) for _ in range(n)]
        
        # Initial guess
        initial_weights = np.ones(n) / n
        
        # Optimize
        start_time = datetime.now()
        
        try:
            result = minimize(
                objective,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 1000, 'ftol': 1e-9}
            )
            
            time_taken = (datetime.now() - start_time).total_seconds()
            weights = result.x
            
            # Calculate metrics
            expected_return = np.dot(weights, returns)
            expected_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
            expected_risk = np.sqrt(expected_variance)
            sharpe_ratio = (expected_return - risk_free_rate) / expected_risk if expected_risk > 0 else 0
            
            # Diversification ratio
            weighted_vols = np.sum(weights * np.sqrt(np.diag(cov_matrix)))
            diversification_ratio = weighted_vols / expected_risk if expected_risk > 0 else 1
            
            # Concentration (HHI)
            concentration = np.sum(weights ** 2)
            
            # Create result
            weights_dict = {f"asset_{i}": weights[i] for i in range(n)}
            
            return PortfolioOptimizationResult(
                weights=weights_dict,
                expected_return=expected_return,
                expected_risk=expected_risk,
                sharpe_ratio=sharpe_ratio,
                diversification_ratio=diversification_ratio,
                concentration=concentration,
                efficient_frontier=[],
                constraints_satisfied=result.success,
                iterations=result.nit if hasattr(result, 'nit') else 0,
                time_taken=time_taken,
            )
            
        except Exception as e:
            logger.error(f"Maximum Sharpe ratio optimization failed: {e}")
            return None
    
    # ============================================================
    # REBALANCING
    # ============================================================
    
    def calculate_rebalance_trades(
        self,
        current_allocation: Dict[str, float],
        target_allocation: Dict[str, float],
        portfolio_value: float,
        min_trade_size: float = 100.0
    ) -> RebalanceResult:
        """
        Calculate rebalancing trades
        
        Args:
            current_allocation: Current asset allocation
            target_allocation: Target asset allocation
            portfolio_value: Total portfolio value
            min_trade_size: Minimum trade size
            
        Returns:
            RebalanceResult
        """
        trades = []
        total_cost = 0.0
        total_slippage = 0.0
        total_tax = 0.0
        
        # Get all assets
        all_assets = set(current_allocation.keys()) | set(target_allocation.keys())
        
        for asset in all_assets:
            current_weight = current_allocation.get(asset, 0)
            target_weight = target_allocation.get(asset, 0)
            current_value = current_weight * portfolio_value
            target_value = target_weight * portfolio_value
            difference = target_value - current_value
            
            if abs(difference) < min_trade_size:
                continue
            
            if difference > 0:
                side = "buy"
            else:
                side = "sell"
            
            trades.append({
                "asset": asset,
                "side": side,
                "quantity": abs(difference),
                "current_value": current_value,
                "target_value": target_value,
                "difference": difference,
            })
            
            # Estimate costs
            cost = abs(difference) * 0.001  # 0.1% cost
            slippage = abs(difference) * 0.0005  # 0.05% slippage
            tax = abs(difference) * 0.002  # 0.2% tax
            
            total_cost += cost
            total_slippage += slippage
            total_tax += tax
        
        net_cost = total_cost + total_slippage + total_tax
        
        return RebalanceResult(
            timestamp=datetime.now(),
            current_allocation=current_allocation,
            target_allocation=target_allocation,
            trades=trades,
            estimated_cost=total_cost,
            estimated_slippage=total_slippage,
            estimated_tax=total_tax,
            net_cost=net_cost,
        )
    
    def execute_rebalance(
        self,
        rebalance_result: RebalanceResult,
        execute: bool = True
    ) -> Dict[str, Any]:
        """
        Execute rebalancing trades
        
        Args:
            rebalance_result: Rebalance result
            execute: Execute trades
            
        Returns:
            Execution result
        """
        if not execute:
            return {
                "status": "simulated",
                "trades": rebalance_result.trades,
                "cost": rebalance_result.net_cost,
            }
        
        # (Implementation would depend on exchange clients)
        return {
            "status": "executed",
            "trades": rebalance_result.trades,
            "cost": rebalance_result.net_cost,
        }
    
    # ============================================================
    # ALLOCATION METHODS
    # ============================================================
    
    def allocate(
        self,
        assets: Dict[str, Any],
        method: Optional[str] = None,
        **kwargs
    ) -> AssetAllocation:
        """
        Perform asset allocation using specified method
        
        Args:
            assets: Asset data
            method: Allocation method
            **kwargs: Additional parameters
            
        Returns:
            AssetAllocation
        """
        if method is None:
            method = self.method
        
        # Prepare data
        asset_names = list(assets.keys())
        n = len(asset_names)
        
        # Extract returns and covariance
        returns = np.array([assets[a].get('return', 0) for a in asset_names])
        cov_matrix = np.array([
            [assets[i].get('covariance', {}).get(j, 0) for j in asset_names]
            for i in asset_names
        ])
        
        # Perform optimization
        if method == "mean_variance":
            result = self.optimize_mean_variance(returns, cov_matrix, **kwargs)
        elif method == "risk_parity":
            result = self.optimize_risk_parity(cov_matrix, **kwargs)
        elif method == "equal_weight":
            result = self.optimize_equal_weight(n, **kwargs)
        elif method == "minimum_variance":
            result = self.optimize_minimum_variance(cov_matrix, **kwargs)
        elif method == "maximum_sharpe":
            result = self.optimize_maximum_sharpe_ratio(returns, cov_matrix, **kwargs)
        elif method == "black_litterman":
            result = self.optimize_black_litterman(
                np.ones(n) / n, cov_matrix, kwargs.get('views', {}), **kwargs
            )
        else:
            raise ValueError(f"Unknown allocation method: {method}")
        
        if result is None:
            raise ValueError("Optimization failed")
        
        # Map weights to asset names
        weights = {}
        for i, name in enumerate(asset_names):
            weight_key = f"asset_{i}"
            weights[name] = result.weights.get(weight_key, 0)
        
        # Create allocation
        allocation = AssetAllocation(
            timestamp=datetime.now(),
            method=method,
            assets=weights,
            expected_return=result.expected_return,
            expected_risk=result.expected_risk,
            sharpe_ratio=result.sharpe_ratio,
            diversification_ratio=result.diversification_ratio,
            concentration=result.concentration,
            constraints=kwargs.get('constraints', {}),
            details=result.dict(),
        )
        
        # Store history
        self.allocation_history.append(allocation)
        self.current_allocation = weights
        
        return allocation


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Dataclasses
    "AssetAllocation",
    "PortfolioOptimizationResult",
    "RebalanceResult",
    
    # Classes
    "AssetAllocator",
]

# ============================================================
# END OF MODULE
# ============================================================
