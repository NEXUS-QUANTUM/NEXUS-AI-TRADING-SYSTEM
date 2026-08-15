"""
Swing Bot Asset Allocation Model
==================================

This module provides asset allocation models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
from scipy.optimize import minimize


@dataclass
class AssetAllocation:
    """Asset allocation data structure."""
    timestamp: datetime
    weights: Dict[str, float]
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    diversification_score: float
    rebalance_needed: bool = False
    rebalance_reason: str = ""


@dataclass
class AssetAllocationSignal:
    """Asset allocation trading signal."""
    symbol: str
    timestamp: datetime
    action: str  # 'rebalance', 'add', 'remove', 'hold'
    asset: str
    weight_change: float
    confidence: float
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class AssetAllocationModel:
    """
    Asset allocation model for portfolio optimization.
    
    Implements modern portfolio theory and risk parity allocation.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the asset allocation model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.assets = self.config.get('assets', [])
        self.risk_free_rate = self.config.get('risk_free_rate', 0.02)
        self.max_allocation = self.config.get('max_allocation', 0.30)
        self.min_allocation = self.config.get('min_allocation', 0.01)
        self.rebalance_threshold = self.config.get('rebalance_threshold', 0.05)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.lookback_period = self.config.get('lookback_period', 252)
        
        # Current allocation
        self.current_allocation: Dict[str, float] = {}
        self.history: List[AssetAllocation] = []
        
    def optimize(
        self,
        returns_data: Dict[str, np.ndarray],
        method: str = 'risk_parity'
    ) -> AssetAllocation:
        """
        Optimize asset allocation.
        
        Args:
            returns_data: Dictionary of asset returns
            method: Optimization method ('risk_parity', 'mean_variance', 'equal_weight')
            
        Returns:
            AssetAllocation object
        """
        if not self.assets:
            self.assets = list(returns_data.keys())
        
        if method == 'risk_parity':
            weights = self._risk_parity(returns_data)
        elif method == 'mean_variance':
            weights = self._mean_variance(returns_data)
        elif method == 'equal_weight':
            weights = {asset: 1.0 / len(self.assets) for asset in self.assets}
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        # Calculate metrics
        expected_return = self._calculate_portfolio_return(returns_data, weights)
        expected_risk = self._calculate_portfolio_risk(returns_data, weights)
        sharpe = (expected_return - self.risk_free_rate) / expected_risk if expected_risk > 0 else 0
        diversification = self._calculate_diversification_score(weights)
        
        # Check if rebalance is needed
        rebalance_needed, rebalance_reason = self._check_rebalance_needed(weights)
        
        allocation = AssetAllocation(
            timestamp=datetime.now(),
            weights=weights,
            expected_return=expected_return,
            expected_risk=expected_risk,
            sharpe_ratio=sharpe,
            diversification_score=diversification,
            rebalance_needed=rebalance_needed,
            rebalance_reason=rebalance_reason
        )
        
        self.history.append(allocation)
        self.current_allocation = weights
        
        return allocation
    
    def _risk_parity(self, returns_data: Dict[str, np.ndarray]) -> Dict[str, float]:
        """
        Calculate risk parity weights.
        
        Args:
            returns_data: Dictionary of asset returns
            
        Returns:
            Risk parity weights
        """
        n_assets = len(self.assets)
        if n_assets == 0:
            return {}
        
        # Calculate covariance matrix
        returns_matrix = np.column_stack([returns_data[asset] for asset in self.assets])
        cov_matrix = np.cov(returns_matrix.T)
        
        # Check if covariance matrix is positive definite
        if np.isnan(cov_matrix).any() or np.isinf(cov_matrix).any():
            return {asset: 1.0 / n_assets for asset in self.assets}
        
        # Risk parity optimization
        def risk_parity_objective(weights):
            weights = np.array(weights)
            portfolio_var = np.dot(weights.T, np.dot(cov_matrix, weights))
            if portfolio_var == 0:
                return float('inf')
            
            # Calculate marginal risk contributions
            marginal_risk = np.dot(cov_matrix, weights) / np.sqrt(portfolio_var)
            risk_contributions = weights * marginal_risk
            
            # Target equal risk contributions
            target_risk = np.mean(risk_contributions)
            return np.sum((risk_contributions - target_risk) ** 2)
        
        # Constraints and bounds
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        ]
        bounds = [(self.min_allocation, self.max_allocation) for _ in range(n_assets)]
        
        # Initial guess (equal weights)
        initial_weights = np.array([1.0 / n_assets] * n_assets)
        
        try:
            result = minimize(
                risk_parity_objective,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )
            optimized_weights = result.x
        except Exception:
            optimized_weights = initial_weights
        
        # Normalize and create dictionary
        optimized_weights = np.maximum(optimized_weights, self.min_allocation)
        optimized_weights /= np.sum(optimized_weights)
        
        return {asset: weight for asset, weight in zip(self.assets, optimized_weights)}
    
    def _mean_variance(self, returns_data: Dict[str, np.ndarray]) -> Dict[str, float]:
        """
        Calculate mean-variance optimized weights.
        
        Args:
            returns_data: Dictionary of asset returns
            
        Returns:
            Mean-variance weights
        """
        n_assets = len(self.assets)
        if n_assets == 0:
            return {}
        
        # Calculate expected returns and covariance
        returns_matrix = np.column_stack([returns_data[asset] for asset in self.assets])
        expected_returns = np.mean(returns_matrix, axis=0)
        cov_matrix = np.cov(returns_matrix.T)
        
        # Check for NaN or Inf
        if np.isnan(cov_matrix).any() or np.isinf(cov_matrix).any():
            return {asset: 1.0 / n_assets for asset in self.assets}
        
        # Maximize Sharpe ratio
        def sharpe_objective(weights):
            weights = np.array(weights)
            portfolio_return = np.sum(weights * expected_returns)
            portfolio_risk = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            if portfolio_risk == 0:
                return -float('inf')
            return -(portfolio_return - self.risk_free_rate) / portfolio_risk
        
        # Constraints and bounds
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        ]
        bounds = [(self.min_allocation, self.max_allocation) for _ in range(n_assets)]
        
        # Initial guess (equal weights)
        initial_weights = np.array([1.0 / n_assets] * n_assets)
        
        try:
            result = minimize(
                sharpe_objective,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )
            optimized_weights = result.x
        except Exception:
            optimized_weights = initial_weights
        
        # Normalize and create dictionary
        optimized_weights = np.maximum(optimized_weights, self.min_allocation)
        optimized_weights /= np.sum(optimized_weights)
        
        return {asset: weight for asset, weight in zip(self.assets, optimized_weights)}
    
    def _calculate_portfolio_return(self, returns_data: Dict[str, np.ndarray],
                                  weights: Dict[str, float]) -> float:
        """
        Calculate portfolio expected return.
        
        Args:
            returns_data: Dictionary of asset returns
            weights: Asset weights
            
        Returns:
            Portfolio return
        """
        total_return = 0.0
        for asset, weight in weights.items():
            if asset in returns_data:
                total_return += weight * np.mean(returns_data[asset])
        return total_return
    
    def _calculate_portfolio_risk(self, returns_data: Dict[str, np.ndarray],
                                weights: Dict[str, float]) -> float:
        """
        Calculate portfolio risk.
        
        Args:
            returns_data: Dictionary of asset returns
            weights: Asset weights
            
        Returns:
            Portfolio risk (standard deviation)
        """
        assets = list(weights.keys())
        returns_matrix = np.column_stack([returns_data[asset] for asset in assets])
        cov_matrix = np.cov(returns_matrix.T)
        
        weight_array = np.array([weights[asset] for asset in assets])
        portfolio_var = np.dot(weight_array.T, np.dot(cov_matrix, weight_array))
        return np.sqrt(max(portfolio_var, 0))
    
    def _calculate_diversification_score(self, weights: Dict[str, float]) -> float:
        """
        Calculate diversification score.
        
        Args:
            weights: Asset weights
            
        Returns:
            Diversification score (0-1)
        """
        n_assets = len(weights)
        if n_assets == 0:
            return 0.0
        
        # Herfindahl index
        hhi = sum(w ** 2 for w in weights.values())
        max_hhi = 1.0
        min_hhi = 1.0 / n_assets
        
        if max_hhi == min_hhi:
            return 1.0
        
        # Diversification score (1 - normalized HHI)
        diversification = 1 - (hhi - min_hhi) / (max_hhi - min_hhi)
        return min(max(diversification, 0.0), 1.0)
    
    def _check_rebalance_needed(self, new_weights: Dict[str, float]) -> Tuple[bool, str]:
        """
        Check if rebalancing is needed.
        
        Args:
            new_weights: New asset weights
            
        Returns:
            Tuple of (rebalance_needed, reason)
        """
        if not self.current_allocation:
            return True, "Initial allocation"
        
        # Calculate weight changes
        changes = {}
        for asset in set(self.current_allocation.keys()) | set(new_weights.keys()):
            current = self.current_allocation.get(asset, 0)
            new = new_weights.get(asset, 0)
            changes[asset] = abs(current - new)
        
        # Check if any change exceeds threshold
        max_change = max(changes.values()) if changes else 0
        if max_change > self.rebalance_threshold:
            # Find largest change
            largest_change_asset = max(changes, key=changes.get)
            return True, f"Weight change for {largest_change_asset} exceeds threshold"
        
        return False, "No significant changes needed"
    
    def get_allocation_signal(self, returns_data: Dict[str, np.ndarray]) -> Optional[AssetAllocationSignal]:
        """
        Generate allocation signal based on current data.
        
        Args:
            returns_data: Dictionary of asset returns
            
        Returns:
            AssetAllocationSignal or None
        """
        # Optimize allocation
        allocation = self.optimize(returns_data)
        
        if not allocation.rebalance_needed:
            return None
        
        if allocation.confidence < self.confidence_threshold:
            return None
        
        # Find assets with largest changes
        changes = {}
        for asset in set(self.current_allocation.keys()) | set(allocation.weights.keys()):
            current = self.current_allocation.get(asset, 0)
            new = allocation.weights.get(asset, 0)
            changes[asset] = new - current
        
        # Get asset with largest positive change
        positive_changes = {k: v for k, v in changes.items() if v > 0}
        if positive_changes:
            asset = max(positive_changes, key=positive_changes.get)
            action = 'add'
            weight_change = positive_changes[asset]
            reason = f"Increase allocation to {asset} by {weight_change:.2%}"
        else:
            # Get asset with largest negative change
            negative_changes = {k: v for k, v in changes.items() if v < 0}
            if negative_changes:
                asset = min(negative_changes, key=negative_changes.get)
                action = 'remove'
                weight_change = abs(negative_changes[asset])
                reason = f"Decrease allocation to {asset} by {weight_change:.2%}"
            else:
                return None
        
        return AssetAllocationSignal(
            symbol=asset,
            timestamp=datetime.now(),
            action=action,
            asset=asset,
            weight_change=weight_change,
            confidence=allocation.sharpe_ratio * 0.5 + allocation.diversification_score * 0.5,
            reason=reason,
            indicators={
                'current_allocation': self.current_allocation,
                'new_allocation': allocation.weights,
                'expected_return': allocation.expected_return,
                'expected_risk': allocation.expected_risk,
                'sharpe_ratio': allocation.sharpe_ratio,
                'diversification_score': allocation.diversification_score
            }
        )
    
    def get_allocation_summary(self) -> Dict[str, Any]:
        """
        Get current allocation summary.
        
        Returns:
            Allocation summary dictionary
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'current_allocation': self.current_allocation,
            'history_length': len(self.history),
            'latest_allocation': self.history[-1] if self.history else None,
            'diversification_score': self.history[-1].diversification_score if self.history else 0,
            'sharpe_ratio': self.history[-1].sharpe_ratio if self.history else 0,
            'expected_return': self.history[-1].expected_return if self.history else 0,
            'expected_risk': self.history[-1].expected_risk if self.history else 0
        }


def create_asset_allocation_model(config: Optional[Dict[str, Any]] = None) -> AssetAllocationModel:
    """
    Create an asset allocation model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        AssetAllocationModel instance
    """
    return AssetAllocationModel(config)


__all__ = [
    'AssetAllocation',
    'AssetAllocationSignal',
    'AssetAllocationModel',
    'create_asset_allocation_model'
]
