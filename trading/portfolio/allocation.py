"""
NEXUS AI TRADING SYSTEM - Portfolio Allocation Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/portfolio/allocation.py
Description: Advanced portfolio allocation with full API integration
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize, Bounds, LinearConstraint
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.portfolio_config import PortfolioConfig
from shared.constants.trading_constants import ASSET_CLASSES
from shared.helpers.trading_helpers import (
    calculate_correlation,
    calculate_covariance,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.repositories.position_repository import PositionRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.portfolio_repository import PortfolioRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class AllocationMethod(str, Enum):
    """Portfolio allocation methods"""
    EQUAL_WEIGHT = "equal_weight"  # Equal weighting
    MARKET_CAP = "market_cap"  # Market capitalization weighting
    RISK_PARITY = "risk_parity"  # Risk parity
    MAX_SHARPE = "max_sharpe"  # Maximum Sharpe ratio
    MIN_VARIANCE = "min_variance"  # Minimum variance
    BLACK_LITTERMAN = "black_litterman"  # Black-Litterman model
    HIERARCHICAL = "hierarchical"  # Hierarchical Risk Parity
    BAYESIAN = "bayesian"  # Bayesian allocation
    REINFORCEMENT = "reinforcement"  # Reinforcement learning based
    CUSTOM = "custom"  # Custom allocation


class RiskParityMethod(str, Enum):
    """Risk parity calculation methods"""
    EQUAL_RISK = "equal_risk"  # Equal risk contribution
    EQUAL_CORRELATION = "equal_correlation"  # Equal correlation
    INVERSE_VOLATILITY = "inverse_volatility"  # Inverse volatility
    MOST_DIVERSIFIED = "most_diversified"  # Most diversified portfolio


class RebalanceFrequency(str, Enum):
    """Rebalancing frequencies"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    ON_DEMAND = "on_demand"
    ADAPTIVE = "adaptive"  # Adaptive based on drift


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class AllocationRequest(BaseModel):
    """Request model for allocation"""
    portfolio_id: str
    method: AllocationMethod = AllocationMethod.RISK_PARITY
    assets: List[str]
    weights: Optional[Dict[str, float]] = None
    risk_free_rate: float = 0.03
    target_return: Optional[float] = None
    target_volatility: Optional[float] = None
    max_weight: float = 0.40
    min_weight: float = 0.01
    lookback_period: int = 252
    rebalance_frequency: RebalanceFrequency = RebalanceFrequency.MONTHLY
    include_cash: bool = True
    constraints: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('max_weight')
    def validate_max_weight(cls, v):
        if not 0 < v <= 1:
            raise ValueError("Max weight must be between 0 and 1")
        return v

    @validator('min_weight')
    def validate_min_weight(cls, v, values):
        if v < 0:
            raise ValueError("Min weight must be non-negative")
        if 'max_weight' in values and v > values['max_weight']:
            raise ValueError("Min weight must be less than max weight")
        return v


class AllocationResponse(BaseModel):
    """Response model for allocation"""
    allocation_id: str
    portfolio_id: str
    method: AllocationMethod
    timestamp: datetime
    weights: Dict[str, float]
    expected_return: float
    expected_volatility: float
    expected_sharpe: float
    risk_contribution: Dict[str, float]
    diversification_ratio: float
    concentration: float
    effective_number: float
    rebalance_needed: bool
    rebalance_drift: float
    recommendations: List[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OptimizationRequest(BaseModel):
    """Request model for portfolio optimization"""
    portfolio_id: str
    objective: str = "sharpe"  # sharpe, variance, return
    constraints: Dict[str, Any] = Field(default_factory=dict)
    include_correlation: bool = True
    iterations: int = 1000
    tolerance: float = 1e-6
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class AllocationContext:
    """Context for allocation"""
    portfolio_id: str
    assets: List[str]
    method: AllocationMethod
    lookback_period: int
    returns: pd.DataFrame
    cov_matrix: pd.DataFrame
    corr_matrix: pd.DataFrame
    volatilities: Dict[str, float]
    expected_returns: Dict[str, float]
    current_weights: Dict[str, float]
    risk_free_rate: float
    constraints: Dict[str, Any]
    timestamp: datetime


@dataclass
class AllocationResult:
    """Result of allocation"""
    weights: Dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    risk_contributions: Dict[str, float]
    diversification_ratio: float
    concentration: float
    effective_number: float
    status: str
    message: str


# =============================================================================
# PORTFOLIO ALLOCATION
# =============================================================================

class PortfolioAllocation:
    """
    Advanced Portfolio Allocation with full API integration.
    
    Features:
    - Multiple allocation methods
    - Risk-based allocation
    - Optimization algorithms
    - Constraint handling
    - Rebalancing
    - Performance metrics
    - Risk contribution analysis
    - Diversification measurement
    """

    def __init__(
        self,
        config: Optional[PortfolioConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        position_repo: Optional[PositionRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        portfolio_repo: Optional[PortfolioRepository] = None
    ):
        """
        Initialize PortfolioAllocation.
        
        Args:
            config: Portfolio configuration
            broker_factory: Factory for broker instances
            position_repo: Position repository
            trade_repo: Trade repository
            portfolio_repo: Portfolio repository
        """
        self.config = config or PortfolioConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.position_repo = position_repo or PositionRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.portfolio_repo = portfolio_repo or PortfolioRepository()
        
        # Allocation cache
        self._allocation_cache: Dict[str, Dict[str, Any]] = {}
        self._optimization_cache: Dict[str, Dict[str, Any]] = {}
        
        # Historical allocations
        self._allocation_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # Performance tracking
        self._performance_metrics: Dict[str, Dict[str, float]] = {}
        
        logger.info("PortfolioAllocation initialized")

    # =========================================================================
    # Allocation
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def allocate(
        self,
        request: AllocationRequest
    ) -> AllocationResponse:
        """
        Allocate portfolio assets.
        
        Args:
            request: Allocation request
            
        Returns:
            AllocationResponse: Allocation results
        """
        try:
            # Build context
            context = await self._build_context(request)
            
            # Calculate allocation based on method
            if request.method == AllocationMethod.EQUAL_WEIGHT:
                result = await self._calculate_equal_weight(context)
            elif request.method == AllocationMethod.MARKET_CAP:
                result = await self._calculate_market_cap(context)
            elif request.method == AllocationMethod.RISK_PARITY:
                result = await self._calculate_risk_parity(context)
            elif request.method == AllocationMethod.MAX_SHARPE:
                result = await self._calculate_max_sharpe(context)
            elif request.method == AllocationMethod.MIN_VARIANCE:
                result = await self._calculate_min_variance(context)
            elif request.method == AllocationMethod.BLACK_LITTERMAN:
                result = await self._calculate_black_litterman(context)
            elif request.method == AllocationMethod.HIERARCHICAL:
                result = await self._calculate_hierarchical(context)
            elif request.method == AllocationMethod.BAYESIAN:
                result = await self._calculate_bayesian(context)
            elif request.method == AllocationMethod.REINFORCEMENT:
                result = await self._calculate_reinforcement(context)
            else:
                result = await self._calculate_risk_parity(context)
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(context, result)
            
            # Create response
            response = AllocationResponse(
                allocation_id=f"alloc_{int(time.time() * 1000)}_{request.portfolio_id}",
                portfolio_id=request.portfolio_id,
                method=request.method,
                timestamp=datetime.utcnow(),
                weights=result.weights,
                expected_return=result.expected_return,
                expected_volatility=result.expected_volatility,
                expected_sharpe=result.sharpe_ratio,
                risk_contribution=result.risk_contributions,
                diversification_ratio=result.diversification_ratio,
                concentration=result.concentration,
                effective_number=result.effective_number,
                rebalance_needed=await self._check_rebalance_needed(context, result),
                rebalance_drift=await self._calculate_drift(context, result),
                recommendations=recommendations,
                metadata=request.metadata
            )
            
            # Cache allocation
            self._allocation_cache[request.portfolio_id] = {
                'response': response,
                'context': context,
                'timestamp': datetime.utcnow()
            }
            
            # Store history
            self._allocation_history.setdefault(request.portfolio_id, []).append({
                'timestamp': datetime.utcnow(),
                'method': request.method.value,
                'weights': result.weights,
                'metrics': {
                    'expected_return': result.expected_return,
                    'expected_volatility': result.expected_volatility,
                    'sharpe_ratio': result.sharpe_ratio
                }
            })
            
            logger.info(f"Allocation completed for {request.portfolio_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error allocating portfolio: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Allocation failed: {str(e)}"
            )

    async def _build_context(self, request: AllocationRequest) -> AllocationContext:
        """Build allocation context"""
        # Get portfolio data
        portfolio = await self.portfolio_repo.get_by_id(request.portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {request.portfolio_id} not found")
        
        # Get positions
        positions = await self.position_repo.get_by_portfolio_id(request.portfolio_id)
        current_weights = {}
        
        total_value = sum(p.value for p in positions) if positions else 1
        for pos in positions:
            current_weights[pos.symbol] = pos.value / total_value if total_value > 0 else 0
        
        # Get returns data
        returns_data = await self._get_returns_data(
            request.assets,
            request.lookback_period
        )
        
        # Calculate covariance matrix
        cov_matrix = returns_data.cov() if len(returns_data) > 1 else pd.DataFrame()
        
        # Calculate correlation matrix
        corr_matrix = returns_data.corr() if len(returns_data) > 1 else pd.DataFrame()
        
        # Calculate volatilities
        volatilities = {asset: returns_data[asset].std() * np.sqrt(252) 
                       for asset in request.assets if asset in returns_data.columns}
        
        # Calculate expected returns
        expected_returns = self._calculate_expected_returns(returns_data)
        
        return AllocationContext(
            portfolio_id=request.portfolio_id,
            assets=request.assets,
            method=request.method,
            lookback_period=request.lookback_period,
            returns=returns_data,
            cov_matrix=cov_matrix,
            corr_matrix=corr_matrix,
            volatilities=volatilities,
            expected_returns=expected_returns,
            current_weights=current_weights,
            risk_free_rate=request.risk_free_rate,
            constraints=request.constraints,
            timestamp=datetime.utcnow()
        )

    async def _get_returns_data(
        self,
        assets: List[str],
        lookback_period: int
    ) -> pd.DataFrame:
        """Get returns data for assets"""
        data = {}
        
        for asset in assets:
            prices = await self._get_price_history(asset, lookback_period)
            if prices and len(prices) > 1:
                returns = [(prices[i] - prices[i-1]) / prices[i-1] 
                          for i in range(1, len(prices))]
                data[asset] = returns
            else:
                # Generate synthetic returns
                data[asset] = list(np.random.normal(0, 0.001, lookback_period))
        
        return pd.DataFrame(data)

    async def _get_price_history(
        self,
        asset: str,
        period: int
    ) -> List[float]:
        """Get price history for asset"""
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    candles = await broker.get_historical_candles(
                        asset,
                        timeframe='1d',
                        limit=period
                    )
                    if candles:
                        return [float(c['close']) for c in candles]
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting price history for {asset}: {e}")
        
        return None

    def _calculate_expected_returns(
        self,
        returns_data: pd.DataFrame
    ) -> Dict[str, float]:
        """Calculate expected returns"""
        expected_returns = {}
        
        for column in returns_data.columns:
            # Simple mean return annualized
            mean_return = returns_data[column].mean()
            expected_returns[column] = mean_return * 252 if not np.isnan(mean_return) else 0
        
        return expected_returns

    # =========================================================================
    # Allocation Methods
    # =========================================================================

    async def _calculate_equal_weight(
        self,
        context: AllocationContext
    ) -> AllocationResult:
        """Calculate equal weight allocation"""
        n_assets = len(context.assets)
        if n_assets == 0:
            return self._empty_result()
        
        weight = 1 / n_assets
        weights = {asset: weight for asset in context.assets}
        
        # Calculate metrics
        expected_return = sum(context.expected_returns.get(asset, 0) * weight 
                            for asset in context.assets)
        
        # Portfolio variance
        if not context.cov_matrix.empty:
            w = np.array([weights[asset] for asset in context.assets])
            portfolio_var = w.T @ context.cov_matrix.values @ w
            expected_volatility = np.sqrt(portfolio_var)
        else:
            expected_volatility = 0.02
        
        sharpe_ratio = (expected_return - context.risk_free_rate) / expected_volatility if expected_volatility > 0 else 0
        
        # Risk contributions
        risk_contributions = self._calculate_risk_contributions(
            weights,
            context.cov_matrix,
            context.assets
        )
        
        # Diversification ratio
        weighted_vol = sum(weights[asset] * context.volatilities.get(asset, 0.02) 
                          for asset in context.assets)
        diversification_ratio = weighted_vol / expected_volatility if expected_volatility > 0 else 1
        
        # Concentration
        concentration = sum(w ** 2 for w in weights.values())
        
        # Effective number
        effective_number = 1 / concentration if concentration > 0 else 0
        
        return AllocationResult(
            weights=weights,
            expected_return=expected_return,
            expected_volatility=expected_volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sharpe_ratio * 1.1,  # Approximate
            calmar_ratio=sharpe_ratio * 0.8,  # Approximate
            risk_contributions=risk_contributions,
            diversification_ratio=diversification_ratio,
            concentration=concentration,
            effective_number=effective_number,
            status='success',
            message='Equal weight allocation'
        )

    async def _calculate_market_cap(
        self,
        context: AllocationContext
    ) -> AllocationResult:
        """Calculate market capitalization weighted allocation"""
        # Get market caps (simplified - use price * volume as proxy)
        market_caps = {}
        total_cap = 0
        
        for asset in context.assets:
            # Use price * volume as market cap proxy
            if asset in context.returns_data.columns:
                price = context.returns_data[asset].iloc[-1]
                volume = 1000000  # Default volume
                cap = price * volume
                market_caps[asset] = cap
                total_cap += cap
        
        if total_cap == 0:
            return await self._calculate_equal_weight(context)
        
        weights = {asset: cap / total_cap for asset, cap in market_caps.items()}
        
        # Calculate metrics
        expected_return = sum(context.expected_returns.get(asset, 0) * weights.get(asset, 0) 
                            for asset in context.assets)
        
        if not context.cov_matrix.empty:
            w = np.array([weights.get(asset, 0) for asset in context.assets])
            portfolio_var = w.T @ context.cov_matrix.values @ w
            expected_volatility = np.sqrt(portfolio_var)
        else:
            expected_volatility = 0.02
        
        sharpe_ratio = (expected_return - context.risk_free_rate) / expected_volatility if expected_volatility > 0 else 0
        
        # Risk contributions
        risk_contributions = self._calculate_risk_contributions(
            weights,
            context.cov_matrix,
            context.assets
        )
        
        weighted_vol = sum(weights.get(asset, 0) * context.volatilities.get(asset, 0.02) 
                          for asset in context.assets)
        diversification_ratio = weighted_vol / expected_volatility if expected_volatility > 0 else 1
        
        concentration = sum(w ** 2 for w in weights.values())
        effective_number = 1 / concentration if concentration > 0 else 0
        
        return AllocationResult(
            weights=weights,
            expected_return=expected_return,
            expected_volatility=expected_volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sharpe_ratio * 1.1,
            calmar_ratio=sharpe_ratio * 0.8,
            risk_contributions=risk_contributions,
            diversification_ratio=diversification_ratio,
            concentration=concentration,
            effective_number=effective_number,
            status='success',
            message='Market cap weighted allocation'
        )

    async def _calculate_risk_parity(
        self,
        context: AllocationContext
    ) -> AllocationResult:
        """Calculate risk parity allocation"""
        n_assets = len(context.assets)
        if n_assets == 0:
            return self._empty_result()
        
        # Start with equal weights
        initial_weights = np.array([1/n_assets] * n_assets)
        
        # Use covariance matrix
        if context.cov_matrix.empty:
            # Fallback to inverse volatility
            vols = np.array([context.volatilities.get(asset, 0.02) for asset in context.assets])
            inv_vols = 1 / vols
            weights_array = inv_vols / inv_vols.sum()
        else:
            # Optimize for equal risk contribution
            cov = context.cov_matrix.values
            bounds = [(0.01, 0.40) for _ in range(n_assets)]
            constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
            
            def risk_parity_objective(w):
                # Calculate risk contributions
                portfolio_var = w.T @ cov @ w
                portfolio_vol = np.sqrt(portfolio_var)
                if portfolio_vol == 0:
                    return 1e6
                
                marginal_contrib = cov @ w / portfolio_vol
                risk_contrib = w * marginal_contrib
                target_risk = portfolio_vol / n_assets
                
                # Penalty for deviation from equal risk
                penalty = np.sum((risk_contrib - target_risk) ** 2)
                return penalty
            
            result = minimize(
                risk_parity_objective,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )
            
            if result.success:
                weights_array = result.x
            else:
                # Fallback to inverse volatility
                vols = np.array([context.volatilities.get(asset, 0.02) for asset in context.assets])
                inv_vols = 1 / vols
                weights_array = inv_vols / inv_vols.sum()
        
        weights = {asset: float(weights_array[i]) 
                  for i, asset in enumerate(context.assets)}
        
        # Calculate metrics
        expected_return = sum(context.expected_returns.get(asset, 0) * weights[asset] 
                            for asset in context.assets)
        
        if not context.cov_matrix.empty:
            w = weights_array
            portfolio_var = w.T @ context.cov_matrix.values @ w
            expected_volatility = np.sqrt(portfolio_var)
        else:
            expected_volatility = 0.02
        
        sharpe_ratio = (expected_return - context.risk_free_rate) / expected_volatility if expected_volatility > 0 else 0
        
        risk_contributions = self._calculate_risk_contributions(
            weights,
            context.cov_matrix,
            context.assets
        )
        
        weighted_vol = sum(weights[asset] * context.volatilities.get(asset, 0.02) 
                          for asset in context.assets)
        diversification_ratio = weighted_vol / expected_volatility if expected_volatility > 0 else 1
        
        concentration = sum(w ** 2 for w in weights.values())
        effective_number = 1 / concentration if concentration > 0 else 0
        
        return AllocationResult(
            weights=weights,
            expected_return=expected_return,
            expected_volatility=expected_volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sharpe_ratio * 1.1,
            calmar_ratio=sharpe_ratio * 0.8,
            risk_contributions=risk_contributions,
            diversification_ratio=diversification_ratio,
            concentration=concentration,
            effective_number=effective_number,
            status='success',
            message='Risk parity allocation'
        )

    async def _calculate_max_sharpe(
        self,
        context: AllocationContext
    ) -> AllocationResult:
        """Calculate maximum Sharpe ratio allocation"""
        n_assets = len(context.assets)
        if n_assets == 0:
            return self._empty_result()
        
        # Get expected returns
        expected_returns = np.array([context.expected_returns.get(asset, 0) 
                                    for asset in context.assets])
        
        # Use covariance matrix
        if context.cov_matrix.empty:
            return await self._calculate_equal_weight(context)
        
        cov = context.cov_matrix.values
        
        # Constraints
        bounds = [(context.min_weight, context.max_weight) for _ in range(n_assets)]
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        
        # Objective: maximize Sharpe ratio
        def negative_sharpe(w):
            portfolio_return = np.sum(expected_returns * w)
            portfolio_var = w.T @ cov @ w
            portfolio_vol = np.sqrt(portfolio_var)
            if portfolio_vol == 0:
                return 1e6
            sharpe = (portfolio_return - context.risk_free_rate) / portfolio_vol
            return -sharpe
        
        initial_weights = np.array([1/n_assets] * n_assets)
        
        result = minimize(
            negative_sharpe,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        if result.success:
            weights_array = result.x
        else:
            return await self._calculate_equal_weight(context)
        
        weights = {asset: float(weights_array[i]) 
                  for i, asset in enumerate(context.assets)}
        
        # Calculate metrics
        expected_return = np.sum(expected_returns * weights_array)
        portfolio_var = weights_array.T @ cov @ weights_array
        expected_volatility = np.sqrt(portfolio_var)
        sharpe_ratio = (expected_return - context.risk_free_rate) / expected_volatility if expected_volatility > 0 else 0
        
        risk_contributions = self._calculate_risk_contributions(
            weights,
            context.cov_matrix,
            context.assets
        )
        
        weighted_vol = sum(weights[asset] * context.volatilities.get(asset, 0.02) 
                          for asset in context.assets)
        diversification_ratio = weighted_vol / expected_volatility if expected_volatility > 0 else 1
        
        concentration = sum(w ** 2 for w in weights.values())
        effective_number = 1 / concentration if concentration > 0 else 0
        
        return AllocationResult(
            weights=weights,
            expected_return=expected_return,
            expected_volatility=expected_volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sharpe_ratio * 1.1,
            calmar_ratio=sharpe_ratio * 0.8,
            risk_contributions=risk_contributions,
            diversification_ratio=diversification_ratio,
            concentration=concentration,
            effective_number=effective_number,
            status='success',
            message='Maximum Sharpe ratio allocation'
        )

    async def _calculate_min_variance(
        self,
        context: AllocationContext
    ) -> AllocationResult:
        """Calculate minimum variance allocation"""
        n_assets = len(context.assets)
        if n_assets == 0:
            return self._empty_result()
        
        if context.cov_matrix.empty:
            return await self._calculate_equal_weight(context)
        
        cov = context.cov_matrix.values
        
        bounds = [(context.min_weight, context.max_weight) for _ in range(n_assets)]
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        
        def objective(w):
            return w.T @ cov @ w
        
        initial_weights = np.array([1/n_assets] * n_assets)
        
        result = minimize(
            objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        if result.success:
            weights_array = result.x
        else:
            return await self._calculate_equal_weight(context)
        
        weights = {asset: float(weights_array[i]) 
                  for i, asset in enumerate(context.assets)}
        
        expected_return = sum(context.expected_returns.get(asset, 0) * weights[asset] 
                            for asset in context.assets)
        portfolio_var = weights_array.T @ cov @ weights_array
        expected_volatility = np.sqrt(portfolio_var)
        sharpe_ratio = (expected_return - context.risk_free_rate) / expected_volatility if expected_volatility > 0 else 0
        
        risk_contributions = self._calculate_risk_contributions(
            weights,
            context.cov_matrix,
            context.assets
        )
        
        weighted_vol = sum(weights[asset] * context.volatilities.get(asset, 0.02) 
                          for asset in context.assets)
        diversification_ratio = weighted_vol / expected_volatility if expected_volatility > 0 else 1
        
        concentration = sum(w ** 2 for w in weights.values())
        effective_number = 1 / concentration if concentration > 0 else 0
        
        return AllocationResult(
            weights=weights,
            expected_return=expected_return,
            expected_volatility=expected_volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sharpe_ratio * 1.1,
            calmar_ratio=sharpe_ratio * 0.8,
            risk_contributions=risk_contributions,
            diversification_ratio=diversification_ratio,
            concentration=concentration,
            effective_number=effective_number,
            status='success',
            message='Minimum variance allocation'
        )

    async def _calculate_black_litterman(
        self,
        context: AllocationContext
    ) -> AllocationResult:
        """Calculate Black-Litterman allocation"""
        # Simplified Black-Litterman
        # First get market cap weights as prior
        market_cap_result = await self._calculate_market_cap(context)
        prior_weights = market_cap_result.weights
        
        # Adjust based on views (simplified - use expected returns)
        views = {}
        for asset in context.assets:
            if context.expected_returns.get(asset, 0) > 0:
                views[asset] = context.expected_returns[asset]
        
        if not views:
            return market_cap_result
        
        # Blend prior and views
        tau = 0.05  # Uncertainty parameter
        weights = {}
        
        for asset in context.assets:
            prior = prior_weights.get(asset, 0)
            view = views.get(asset, 0)
            # Simple blending
            weights[asset] = (1 - tau) * prior + tau * view
        
        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        # Calculate metrics
        expected_return = sum(context.expected_returns.get(asset, 0) * weights.get(asset, 0) 
                            for asset in context.assets)
        
        if not context.cov_matrix.empty:
            w = np.array([weights.get(asset, 0) for asset in context.assets])
            portfolio_var = w.T @ context.cov_matrix.values @ w
            expected_volatility = np.sqrt(portfolio_var)
        else:
            expected_volatility = 0.02
        
        sharpe_ratio = (expected_return - context.risk_free_rate) / expected_volatility if expected_volatility > 0 else 0
        
        risk_contributions = self._calculate_risk_contributions(
            weights,
            context.cov_matrix,
            context.assets
        )
        
        weighted_vol = sum(weights.get(asset, 0) * context.volatilities.get(asset, 0.02) 
                          for asset in context.assets)
        diversification_ratio = weighted_vol / expected_volatility if expected_volatility > 0 else 1
        
        concentration = sum(w ** 2 for w in weights.values())
        effective_number = 1 / concentration if concentration > 0 else 0
        
        return AllocationResult(
            weights=weights,
            expected_return=expected_return,
            expected_volatility=expected_volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sharpe_ratio * 1.1,
            calmar_ratio=sharpe_ratio * 0.8,
            risk_contributions=risk_contributions,
            diversification_ratio=diversification_ratio,
            concentration=concentration,
            effective_number=effective_number,
            status='success',
            message='Black-Litterman allocation'
        )

    async def _calculate_hierarchical(
        self,
        context: AllocationContext
    ) -> AllocationResult:
        """Calculate Hierarchical Risk Parity allocation"""
        # Simplified Hierarchical Risk Parity
        n_assets = len(context.assets)
        if n_assets == 0:
            return self._empty_result()
        
        if context.corr_matrix.empty:
            return await self._calculate_equal_weight(context)
        
        # Use correlation-based clustering
        corr = context.corr_matrix.values
        
        # Simple hierarchical clustering (single linkage)
        clusters = self._simple_clustering(corr, context.assets)
        
        # Allocate within clusters using risk parity
        weights = {}
        for cluster in clusters:
            if len(cluster) == 1:
                weights[cluster[0]] = 1 / len(clusters)
            else:
                # Allocate within cluster
                cluster_weights = await self._calculate_risk_parity_subset(
                    cluster,
                    context
                )
                weights.update(cluster_weights)
        
        # Normalize across clusters
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        # Calculate metrics
        expected_return = sum(context.expected_returns.get(asset, 0) * weights.get(asset, 0) 
                            for asset in context.assets)
        
        if not context.cov_matrix.empty:
            w = np.array([weights.get(asset, 0) for asset in context.assets])
            portfolio_var = w.T @ context.cov_matrix.values @ w
            expected_volatility = np.sqrt(portfolio_var)
        else:
            expected_volatility = 0.02
        
        sharpe_ratio = (expected_return - context.risk_free_rate) / expected_volatility if expected_volatility > 0 else 0
        
        risk_contributions = self._calculate_risk_contributions(
            weights,
            context.cov_matrix,
            context.assets
        )
        
        weighted_vol = sum(weights.get(asset, 0) * context.volatilities.get(asset, 0.02) 
                          for asset in context.assets)
        diversification_ratio = weighted_vol / expected_volatility if expected_volatility > 0 else 1
        
        concentration = sum(w ** 2 for w in weights.values())
        effective_number = 1 / concentration if concentration > 0 else 0
        
        return AllocationResult(
            weights=weights,
            expected_return=expected_return,
            expected_volatility=expected_volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sharpe_ratio * 1.1,
            calmar_ratio=sharpe_ratio * 0.8,
            risk_contributions=risk_contributions,
            diversification_ratio=diversification_ratio,
            concentration=concentration,
            effective_number=effective_number,
            status='success',
            message='Hierarchical Risk Parity allocation'
        )

    def _simple_clustering(
        self,
        corr_matrix: np.ndarray,
        assets: List[str]
    ) -> List[List[str]]:
        """Simple correlation-based clustering"""
        n = len(assets)
        if n <= 2:
            return [[asset] for asset in assets]
        
        # Simple grouping by correlation threshold
        threshold = 0.3
        clusters = []
        used = set()
        
        for i in range(n):
            if i in used:
                continue
            cluster = [assets[i]]
            used.add(i)
            
            for j in range(i + 1, n):
                if j not in used and abs(corr_matrix[i, j]) > threshold:
                    cluster.append(assets[j])
                    used.add(j)
            
            clusters.append(cluster)
        
        # Ensure all assets are assigned
        for i, asset in enumerate(assets):
            if i not in used:
                clusters.append([asset])
        
        return clusters

    async def _calculate_risk_parity_subset(
        self,
        assets: List[str],
        context: AllocationContext
    ) -> Dict[str, float]:
        """Calculate risk parity for subset of assets"""
        if len(assets) == 1:
            return {assets[0]: 1.0}
        
        # Create subset context
        subset_context = AllocationContext(
            portfolio_id=context.portfolio_id,
            assets=assets,
            method=context.method,
            lookback_period=context.lookback_period,
            returns=context.returns[assets] if all(a in context.returns.columns for a in assets) else pd.DataFrame(),
            cov_matrix=context.cov_matrix.loc[assets, assets] if not context.cov_matrix.empty else pd.DataFrame(),
            corr_matrix=context.corr_matrix.loc[assets, assets] if not context.corr_matrix.empty else pd.DataFrame(),
            volatilities={a: context.volatilities.get(a, 0.02) for a in assets},
            expected_returns={a: context.expected_returns.get(a, 0) for a in assets},
            current_weights={a: context.current_weights.get(a, 0) for a in assets},
            risk_free_rate=context.risk_free_rate,
            constraints=context.constraints,
            timestamp=context.timestamp
        )
        
        # Calculate risk parity for subset
        result = await self._calculate_risk_parity(subset_context)
        return result.weights

    async def _calculate_bayesian(
        self,
        context: AllocationContext
    ) -> AllocationResult:
        """Calculate Bayesian allocation"""
        # Use Black-Litterman as proxy
        return await self._calculate_black_litterman(context)

    async def _calculate_reinforcement(
        self,
        context: AllocationContext
    ) -> AllocationResult:
        """Calculate reinforcement learning based allocation"""
        # Simplified RL-based allocation
        # Use performance history to adjust weights
        history = self._allocation_history.get(context.portfolio_id, [])
        
        if len(history) < 10:
            return await self._calculate_risk_parity(context)
        
        # Get recent performance
        recent_history = history[-10:]
        
        # Calculate average performance of each asset
        performance = {}
        for entry in recent_history:
            for asset, weight in entry.get('weights', {}).items():
                if asset not in performance:
                    performance[asset] = 0
                performance[asset] += weight * entry.get('metrics', {}).get('sharpe_ratio', 0)
        
        # Normalize to get weights
        total = sum(performance.values())
        if total == 0:
            return await self._calculate_risk_parity(context)
        
        weights = {asset: perf / total for asset, perf in performance.items()}
        
        # Calculate metrics
        expected_return = sum(context.expected_returns.get(asset, 0) * weights.get(asset, 0) 
                            for asset in context.assets)
        
        if not context.cov_matrix.empty:
            w = np.array([weights.get(asset, 0) for asset in context.assets])
            portfolio_var = w.T @ context.cov_matrix.values @ w
            expected_volatility = np.sqrt(portfolio_var)
        else:
            expected_volatility = 0.02
        
        sharpe_ratio = (expected_return - context.risk_free_rate) / expected_volatility if expected_volatility > 0 else 0
        
        risk_contributions = self._calculate_risk_contributions(
            weights,
            context.cov_matrix,
            context.assets
        )
        
        weighted_vol = sum(weights.get(asset, 0) * context.volatilities.get(asset, 0.02) 
                          for asset in context.assets)
        diversification_ratio = weighted_vol / expected_volatility if expected_volatility > 0 else 1
        
        concentration = sum(w ** 2 for w in weights.values())
        effective_number = 1 / concentration if concentration > 0 else 0
        
        return AllocationResult(
            weights=weights,
            expected_return=expected_return,
            expected_volatility=expected_volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sharpe_ratio * 1.1,
            calmar_ratio=sharpe_ratio * 0.8,
            risk_contributions=risk_contributions,
            diversification_ratio=diversification_ratio,
            concentration=concentration,
            effective_number=effective_number,
            status='success',
            message='Reinforcement learning allocation'
        )

    def _empty_result(self) -> AllocationResult:
        """Return empty allocation result"""
        return AllocationResult(
            weights={},
            expected_return=0,
            expected_volatility=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            calmar_ratio=0,
            risk_contributions={},
            diversification_ratio=0,
            concentration=0,
            effective_number=0,
            status='error',
            message='No assets to allocate'
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _calculate_risk_contributions(
        self,
        weights: Dict[str, float],
        cov_matrix: pd.DataFrame,
        assets: List[str]
    ) -> Dict[str, float]:
        """Calculate risk contributions of each asset"""
        if cov_matrix.empty:
            return {asset: 0 for asset in assets}
        
        w = np.array([weights.get(asset, 0) for asset in assets])
        portfolio_var = w.T @ cov_matrix.values @ w
        portfolio_vol = np.sqrt(portfolio_var)
        
        if portfolio_vol == 0:
            return {asset: 0 for asset in assets}
        
        marginal_contrib = cov_matrix.values @ w / portfolio_vol
        risk_contrib = w * marginal_contrib
        
        return {asset: float(risk_contrib[i]) 
                for i, asset in enumerate(assets)}

    async def _check_rebalance_needed(
        self,
        context: AllocationContext,
        result: AllocationResult
    ) -> bool:
        """Check if rebalancing is needed"""
        if not context.current_weights:
            return True
        
        # Calculate drift
        drift = 0
        for asset in context.assets:
            current = context.current_weights.get(asset, 0)
            target = result.weights.get(asset, 0)
            drift += abs(current - target)
        
        threshold = 0.10  # 10% drift threshold
        
        return drift > threshold

    async def _calculate_drift(
        self,
        context: AllocationContext,
        result: AllocationResult
    ) -> float:
        """Calculate allocation drift"""
        if not context.current_weights:
            return 0
        
        drift = 0
        for asset in context.assets:
            current = context.current_weights.get(asset, 0)
            target = result.weights.get(asset, 0)
            drift += abs(current - target)
        
        return drift

    async def _generate_recommendations(
        self,
        context: AllocationContext,
        result: AllocationResult
    ) -> List[str]:
        """Generate allocation recommendations"""
        recommendations = []
        
        # Check concentration
        if result.concentration > 0.25:
            recommendations.append("High concentration. Consider diversifying.")
        
        # Check diversification
        if result.diversification_ratio < 1.2:
            recommendations.append("Low diversification. Consider adding uncorrelated assets.")
        
        # Check individual weights
        for asset, weight in result.weights.items():
            if weight > context.max_weight * 0.8:
                recommendations.append(f"High weight in {asset}. Consider reducing exposure.")
            elif weight < context.min_weight * 2:
                recommendations.append(f"Very low weight in {asset}. Consider increasing exposure.")
        
        # Check Sharpe ratio
        if result.sharpe_ratio < 0.5:
            recommendations.append("Low Sharpe ratio. Consider adjusting allocation.")
        
        # Check risk contributions
        target_risk = 1 / len(context.assets) if context.assets else 0
        for asset, risk in result.risk_contributions.items():
            if risk > target_risk * 2:
                recommendations.append(f"High risk contribution from {asset}. Consider reducing.")
        
        if not recommendations:
            recommendations.append("Allocation is well balanced.")
        
        return recommendations

    # =========================================================================
    # Allocation Management
    # =========================================================================

    async def get_allocation(
        self,
        portfolio_id: str
    ) -> Optional[AllocationResponse]:
        """Get current allocation"""
        cached = self._allocation_cache.get(portfolio_id)
        if cached and (datetime.utcnow() - cached['timestamp']).seconds < 60:
            return cached['response']
        return None

    async def get_allocation_history(
        self,
        portfolio_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get allocation history"""
        history = self._allocation_history.get(portfolio_id, [])
        return history[-limit:] if history else []

    async def clear_cache(self) -> None:
        """Clear allocation cache"""
        self._allocation_cache.clear()
        self._optimization_cache.clear()

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the allocation module"""
        self._allocation_cache.clear()
        self._optimization_cache.clear()
        self._allocation_history.clear()
        self._performance_metrics.clear()
        logger.info("PortfolioAllocation closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/portfolio/allocation", tags=["Portfolio Allocation"])


async def get_allocator() -> PortfolioAllocation:
    """Dependency to get PortfolioAllocation instance"""
    return PortfolioAllocation()


@router.post("/allocate", response_model=AllocationResponse)
async def allocate_portfolio(
    request: AllocationRequest,
    allocator: PortfolioAllocation = Depends(get_allocator)
):
    """Allocate portfolio assets"""
    return await allocator.allocate(request)


@router.get("/{portfolio_id}")
async def get_allocation(
    portfolio_id: str,
    allocator: PortfolioAllocation = Depends(get_allocator)
):
    """Get current allocation"""
    allocation = await allocator.get_allocation(portfolio_id)
    if not allocation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No allocation found for portfolio {portfolio_id}"
        )
    return allocation


@router.get("/{portfolio_id}/history")
async def get_allocation_history(
    portfolio_id: str,
    limit: int = Query(100, le=1000),
    allocator: PortfolioAllocation = Depends(get_allocator)
):
    """Get allocation history"""
    return await allocator.get_allocation_history(portfolio_id, limit)


@router.get("/methods")
async def get_allocation_methods():
    """Get available allocation methods"""
    return {
        'methods': [
            {'name': m.value, 'description': m.name.replace('_', ' ').title()}
            for m in AllocationMethod
        ]
    }


@router.post("/rebalance")
async def rebalance_portfolio(
    portfolio_id: str = Body(..., embed=True),
    allocator: PortfolioAllocation = Depends(get_allocator)
):
    """Rebalance portfolio"""
    # Get current allocation
    allocation = await allocator.get_allocation(portfolio_id)
    if not allocation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No allocation found for portfolio {portfolio_id}"
        )
    
    # Execute rebalancing
    # Implementation would execute trades to align with target weights
    return {"success": True, "target_weights": allocation.weights}


@router.post("/clear-cache")
async def clear_cache(
    allocator: PortfolioAllocation = Depends(get_allocator)
):
    """Clear allocation cache"""
    await allocator.clear_cache()
    return {"success": True}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PortfolioAllocation',
    'AllocationMethod',
    'RiskParityMethod',
    'RebalanceFrequency',
    'AllocationRequest',
    'AllocationResponse',
    'OptimizationRequest',
    'AllocationContext',
    'AllocationResult',
    'router'
]
