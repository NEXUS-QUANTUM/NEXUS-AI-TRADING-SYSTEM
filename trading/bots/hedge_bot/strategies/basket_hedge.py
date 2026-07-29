# trading/bots/hedge_bot/strategies/basket_hedge.py

"""
NEXUS HEDGE BOT - BASKET HEDGE STRATEGY
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced basket hedging strategy that manages multiple positions simultaneously,
using a portfolio approach to hedge against market movements while maintaining
diversification and risk optimization.

Version: 3.0.0
"""

import asyncio
import json
import math
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

import numpy as np
import pandas as pd
import structlog
from scipy.optimize import minimize
from scipy.stats import norm
from pydantic import BaseModel, Field, validator

from ..core.base_hedge import BaseHedgeStrategy
from ..core.hedge_types import HedgeType, HedgeDirection, HedgeSignal
from ..core.portfolio_manager import PortfolioManager
from ..core.risk_manager import RiskManager
from ..core.market_data import MarketDataProvider

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class BasketWeightingMethod(str, Enum):
    """Methods for weighting basket components."""
    EQUAL = "equal"
    MARKET_CAP = "market_cap"
    VOLATILITY_INVERSE = "volatility_inverse"
    RISK_PARITY = "risk_parity"
    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    OPTIMAL = "optimal"
    DYNAMIC = "dynamic"


class BasketRebalanceTrigger(str, Enum):
    """Triggers for basket rebalancing."""
    TIME_BASED = "time_based"
    THRESHOLD = "threshold"
    SIGNAL = "signal"
    VOLATILITY = "volatility"
    HYBRID = "hybrid"


class BasketHedgeType(str, Enum):
    """Types of basket hedging."""
    MARKET_NEUTRAL = "market_neutral"
    BETA_NEUTRAL = "beta_neutral"
    CURRENCY_NEUTRAL = "currency_neutral"
    SECTOR_NEUTRAL = "sector_neutral"
    FACTOR_NEUTRAL = "factor_neutral"
    TAIL_RISK = "tail_risk"
    VOLATILITY = "volatility"
    MACRO = "macro"
    DYNAMIC = "dynamic"


# === DATA MODELS ===

@dataclass
class BasketComponent:
    """Component of a hedging basket."""
    symbol: str = ""
    weight: float = 0.0
    target_weight: float = 0.0
    current_weight: float = 0.0
    position_size: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    beta: float = 1.0
    volatility: float = 0.0
    correlation: float = 0.0
    hedge_ratio: float = 0.0
    sector: str = ""
    currency: str = "USD"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BasketState:
    """State of the hedging basket."""
    basket_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_rebalance: Optional[datetime] = None
    next_rebalance: Optional[datetime] = None
    components: List[BasketComponent] = field(default_factory=list)
    total_value: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    total_exposure: float = 0.0
    net_exposure: float = 0.0
    gross_exposure: float = 0.0
    leverage: float = 0.0
    beta: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    hedging_effectiveness: float = 0.0
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_rebalance": self.last_rebalance.isoformat() if self.last_rebalance else None,
            "next_rebalance": self.next_rebalance.isoformat() if self.next_rebalance else None,
            "components": [c.to_dict() for c in self.components],
        }


# === BASKET HEDGE STRATEGY ===

class BasketHedgeStrategy(BaseHedgeStrategy):
    """
    Advanced basket hedging strategy that manages multiple positions
    simultaneously using a portfolio approach.
    """
    
    def __init__(
        self,
        name: str = "basket_hedge",
        hedge_type: BasketHedgeType = BasketHedgeType.MARKET_NEUTRAL,
        weighting_method: BasketWeightingMethod = BasketWeightingMethod.RISK_PARITY,
        rebalance_trigger: BasketRebalanceTrigger = BasketRebalanceTrigger.HYBRID,
        portfolio_manager: Optional[PortfolioManager] = None,
        risk_manager: Optional[RiskManager] = None,
        market_data: Optional[MarketDataProvider] = None,
        **kwargs
    ):
        """
        Initialize the basket hedge strategy.
        
        Args:
            name: Strategy name
            hedge_type: Type of basket hedging
            weighting_method: Method for weighting components
            rebalance_trigger: Trigger for rebalancing
            portfolio_manager: Portfolio manager instance
            risk_manager: Risk manager instance
            market_data: Market data provider
            **kwargs: Additional configuration
        """
        super().__init__(name=name, **kwargs)
        
        self.hedge_type = hedge_type
        self.weighting_method = weighting_method
        self.rebalance_trigger = rebalance_trigger
        
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.market_data = market_data
        
        # Strategy state
        self._lock = threading.RLock()
        self._running = False
        self._closed = False
        
        # Basket
        self._basket = BasketState()
        self._basket_history: List[BasketState] = []
        
        # Configuration
        self._config = {
            "min_components": 3,
            "max_components": 20,
            "target_volatility": 0.15,
            "max_leverage": 1.5,
            "min_leverage": 0.5,
            "rebalance_threshold": 0.05,      # 5% deviation from target weights
            "rebalance_interval_hours": 4,
            "max_single_position_pct": 0.30,   # 30% max per position
            "min_single_position_pct": 0.02,   # 2% min per position
            "correlation_threshold": 0.70,
            "beta_target": 0.0,
            "max_exposure": 0.8,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.15,
            "trailing_stop_pct": 0.03,
            "volatility_lookback_days": 30,
            "correlation_lookback_days": 60,
        }
        
        # Performance tracking
        self._performance = {
            "rebalances": 0,
            "trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "avg_pnl_per_trade": 0.0,
        }
        
        # Optimization cache
        self._optimization_cache: Dict[str, Any] = {}
        
        logger.info(
            "basket_hedge_strategy_initialized",
            name=name,
            hedge_type=hedge_type.value,
            weighting_method=weighting_method.value,
        )
    
    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and manage basket positions.
        
        Args:
            market_data: Current market data
            
        Returns:
            Analysis results with basket updates
        """
        try:
            # Update basket components
            await self._update_basket_components(market_data)
            
            # Calculate basket metrics
            await self._calculate_basket_metrics(market_data)
            
            # Check rebalancing trigger
            if await self._should_rebalance():
                await self._rebalance_basket(market_data)
            
            # Generate signals
            signal = await self._generate_basket_signal(market_data)
            
            return {
                "basket": self._basket.to_dict(),
                "signal": signal.to_dict() if signal else None,
                "performance": self._performance,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(
                "basket_hedge_analysis_failed",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    async def _update_basket_components(self, market_data: Dict[str, Any]) -> None:
        """Update basket components with current data."""
        with self._lock:
            symbols = market_data.get("symbols", [])
            
            # Filter symbols
            valid_symbols = await self._filter_symbols(symbols, market_data)
            
            # Add new components if needed
            if len(self._basket.components) < self._config["min_components"]:
                for symbol in valid_symbols:
                    if not any(c.symbol == symbol for c in self._basket.components):
                        self._basket.components.append(
                            BasketComponent(
                                symbol=symbol,
                                weight=0.0,
                                target_weight=0.0,
                            )
                        )
            
            # Update prices and metrics
            for component in self._basket.components:
                if component.symbol in market_data.get("prices", {}):
                    component.current_price = market_data["prices"][component.symbol]
                    
                    # Calculate PnL
                    if component.entry_price > 0:
                        component.pnl = (component.current_price - component.entry_price) * component.position_size
                        component.pnl_pct = (component.current_price - component.entry_price) / component.entry_price * 100
            
            # Remove invalid components
            self._basket.components = [c for c in self._basket.components if c.symbol in valid_symbols]
    
    async def _filter_symbols(self, symbols: List[str], market_data: Dict[str, Any]) -> List[str]:
        """Filter symbols based on criteria."""
        filtered = []
        
        for symbol in symbols:
            # Check if we have enough data
            if symbol not in market_data.get("prices", {}):
                continue
            
            # Check volatility
            volatility = market_data.get("volatility", {}).get(symbol, 0.0)
            if volatility > self._config.get("max_volatility", 1.0):
                continue
            
            # Check liquidity
            volume = market_data.get("volume", {}).get(symbol, 0.0)
            if volume < self._config.get("min_volume", 1000000):
                continue
            
            # Check correlation with existing components
            if self._basket.components:
                correlations = []
                for comp in self._basket.components:
                    corr = market_data.get("correlations", {}).get(f"{comp.symbol}_{symbol}", 0.0)
                    correlations.append(abs(corr))
                
                if correlations:
                    avg_corr = np.mean(correlations)
                    if avg_corr > self._config["correlation_threshold"]:
                        continue
            
            filtered.append(symbol)
        
        return filtered
    
    async def _calculate_basket_metrics(self, market_data: Dict[str, Any]) -> None:
        """Calculate basket-level metrics."""
        with self._lock:
            if not self._basket.components:
                return
            
            # Calculate weights
            total_value = sum(c.position_size * c.current_price for c in self._basket.components)
            self._basket.total_value = total_value
            
            # Calculate exposures
            long_exposure = sum(
                c.position_size * c.current_price 
                for c in self._basket.components 
                if c.position_size > 0
            )
            short_exposure = sum(
                abs(c.position_size * c.current_price)
                for c in self._basket.components
                if c.position_size < 0
            )
            
            self._basket.gross_exposure = long_exposure + short_exposure
            self._basket.net_exposure = long_exposure - short_exposure
            self._basket.leverage = self._basket.gross_exposure / total_value if total_value > 0 else 0
            
            # Calculate beta
            total_beta = sum(c.beta * c.current_weight for c in self._basket.components)
            self._basket.beta = total_beta
            
            # Calculate volatility
            if len(self._basket.components) > 1:
                weights = [c.current_weight for c in self._basket.components]
                volatilities = [c.volatility for c in self._basket.components]
                
                # Build correlation matrix
                n = len(self._basket.components)
                corr_matrix = np.ones((n, n))
                for i in range(n):
                    for j in range(n):
                        if i != j:
                            c1 = self._basket.components[i]
                            c2 = self._basket.components[j]
                            corr_matrix[i, j] = market_data.get("correlations", {}).get(
                                f"{c1.symbol}_{c2.symbol}", 0.3
                            )
                
                portfolio_variance = np.dot(
                    weights, 
                    np.dot(corr_matrix * np.outer(volatilities, volatilities), weights)
                )
                self._basket.volatility = np.sqrt(portfolio_variance)
            else:
                self._basket.volatility = self._basket.components[0].volatility if self._basket.components else 0
            
            # Calculate PnL
            total_pnl = sum(c.pnl for c in self._basket.components)
            self._basket.total_pnl = total_pnl
            self._basket.total_pnl_pct = total_pnl / total_value * 100 if total_value > 0 else 0
    
    async def _should_rebalance(self) -> bool:
        """Check if basket should be rebalanced."""
        with self._lock:
            if not self._basket.components:
                return False
            
            # Time-based trigger
            if self._config["rebalance_interval_hours"] > 0:
                if self._basket.last_rebalance is None:
                    return True
                
                hours_since = (datetime.utcnow() - self._basket.last_rebalance).total_seconds() / 3600
                if hours_since >= self._config["rebalance_interval_hours"]:
                    return True
            
            # Threshold trigger
            if self.rebalance_trigger in [BasketRebalanceTrigger.THRESHOLD, BasketRebalanceTrigger.HYBRID]:
                for component in self._basket.components:
                    if abs(component.current_weight - component.target_weight) > self._config["rebalance_threshold"]:
                        return True
            
            # Volatility trigger
            if self.rebalance_trigger in [BasketRebalanceTrigger.VOLATILITY, BasketRebalanceTrigger.HYBRID]:
                if self._basket.volatility > self._config["target_volatility"] * 1.5:
                    return True
                if self._basket.volatility < self._config["target_volatility"] * 0.5:
                    return True
            
            return False
    
    async def _rebalance_basket(self, market_data: Dict[str, Any]) -> None:
        """Rebalance the basket to target weights."""
        with self._lock:
            # Calculate target weights
            await self._calculate_target_weights(market_data)
            
            # Generate rebalancing trades
            trades = await self._generate_rebalance_trades()
            
            # Execute trades
            for trade in trades:
                await self._execute_rebalance_trade(trade)
            
            # Update basket state
            self._basket.last_rebalance = datetime.utcnow()
            self._basket.next_rebalance = self._basket.last_rebalance + timedelta(
                hours=self._config["rebalance_interval_hours"]
            )
            
            self._performance["rebalances"] += 1
            
            # Store history
            self._basket_history.append(self._basket)
            if len(self._basket_history) > 100:
                self._basket_history = self._basket_history[-100:]
            
            logger.info(
                "basket_rebalanced",
                basket_id=self._basket.basket_id,
                components=len(self._basket.components),
                trades=len(trades),
            )
    
    async def _calculate_target_weights(self, market_data: Dict[str, Any]) -> None:
        """Calculate target weights for basket components."""
        with self._lock:
            if not self._basket.components:
                return
            
            method = self.weighting_method
            
            if method == BasketWeightingMethod.EQUAL:
                weight = 1.0 / len(self._basket.components)
                for component in self._basket.components:
                    component.target_weight = weight
            
            elif method == BasketWeightingMethod.VOLATILITY_INVERSE:
                total_inv_vol = sum(1.0 / (c.volatility + 0.001) for c in self._basket.components)
                for component in self._basket.components:
                    component.target_weight = (1.0 / (component.volatility + 0.001)) / total_inv_vol
            
            elif method == BasketWeightingMethod.RISK_PARITY:
                # Risk parity optimization
                volatilities = [c.volatility for c in self._basket.components]
                correlations = self._get_correlation_matrix(market_data)
                
                weights = self._optimize_risk_parity(volatilities, correlations)
                for i, component in enumerate(self._basket.components):
                    component.target_weight = weights[i]
            
            elif method in [BasketWeightingMethod.MAX_SHARPE, BasketWeightingMethod.MIN_VARIANCE]:
                # Optimization-based weights
                volatilities = [c.volatility for c in self._basket.components]
                correlations = self._get_correlation_matrix(market_data)
                
                if method == BasketWeightingMethod.MAX_SHARPE:
                    weights = self._optimize_max_sharpe(volatilities, correlations)
                else:
                    weights = self._optimize_min_variance(volatilities, correlations)
                
                for i, component in enumerate(self._basket.components):
                    component.target_weight = weights[i]
            
            elif method == BasketWeightingMethod.DYNAMIC:
                # Dynamic weighting based on market conditions
                weights = await self._calculate_dynamic_weights(market_data)
                for i, component in enumerate(self._basket.components):
                    if i < len(weights):
                        component.target_weight = weights[i]
            
            # Apply constraints
            self._apply_weight_constraints()
            
            # Apply hedging type adjustments
            await self._apply_hedge_type_adjustments(market_data)
    
    def _get_correlation_matrix(self, market_data: Dict[str, Any]) -> np.ndarray:
        """Get correlation matrix for basket components."""
        n = len(self._basket.components)
        corr_matrix = np.eye(n)
        
        for i in range(n):
            for j in range(i + 1, n):
                key = f"{self._basket.components[i].symbol}_{self._basket.components[j].symbol}"
                corr = market_data.get("correlations", {}).get(key, 0.3)
                corr_matrix[i, j] = corr
                corr_matrix[j, i] = corr
        
        return corr_matrix
    
    def _optimize_risk_parity(self, volatilities: List[float], correlations: np.ndarray) -> np.ndarray:
        """Optimize weights for risk parity."""
        n = len(volatilities)
        
        def risk_parity_objective(weights):
            weights = np.array(weights)
            portfolio_variance = np.dot(weights, np.dot(correlations * np.outer(volatilities, volatilities), weights))
            marginal_risks = np.dot(correlations * np.outer(volatilities, volatilities), weights)
            risk_contributions = weights * marginal_risks / (portfolio_variance + 1e-10)
            target = np.ones(n) / n
            return np.sum((risk_contributions - target) ** 2)
        
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0},
            {'type': 'ineq', 'fun': lambda x: x - self._config["min_single_position_pct"]},
            {'type': 'ineq', 'fun': lambda x: self._config["max_single_position_pct"] - x},
        ]
        
        result = minimize(
            risk_parity_objective,
            np.ones(n) / n,
            method='SLSQP',
            constraints=constraints,
            options={'maxiter': 1000},
        )
        
        return result.x if result.success else np.ones(n) / n
    
    def _optimize_max_sharpe(self, volatilities: List[float], correlations: np.ndarray) -> np.ndarray:
        """Optimize weights for maximum Sharpe ratio."""
        n = len(volatilities)
        
        def sharpe_objective(weights):
            weights = np.array(weights)
            portfolio_variance = np.dot(weights, np.dot(correlations * np.outer(volatilities, volatilities), weights))
            portfolio_return = np.mean(weights * 0.1)  # Simplified expected returns
            return -(portfolio_return / np.sqrt(portfolio_variance + 1e-10))
        
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0},
            {'type': 'ineq', 'fun': lambda x: x - self._config["min_single_position_pct"]},
            {'type': 'ineq', 'fun': lambda x: self._config["max_single_position_pct"] - x},
        ]
        
        result = minimize(
            sharpe_objective,
            np.ones(n) / n,
            method='SLSQP',
            constraints=constraints,
            options={'maxiter': 1000},
        )
        
        return result.x if result.success else np.ones(n) / n
    
    def _optimize_min_variance(self, volatilities: List[float], correlations: np.ndarray) -> np.ndarray:
        """Optimize weights for minimum variance."""
        n = len(volatilities)
        
        def variance_objective(weights):
            weights = np.array(weights)
            return np.dot(weights, np.dot(correlations * np.outer(volatilities, volatilities), weights))
        
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0},
            {'type': 'ineq', 'fun': lambda x: x - self._config["min_single_position_pct"]},
            {'type': 'ineq', 'fun': lambda x: self._config["max_single_position_pct"] - x},
        ]
        
        result = minimize(
            variance_objective,
            np.ones(n) / n,
            method='SLSQP',
            constraints=constraints,
            options={'maxiter': 1000},
        )
        
        return result.x if result.success else np.ones(n) / n
    
    async def _calculate_dynamic_weights(self, market_data: Dict[str, Any]) -> List[float]:
        """Calculate dynamic weights based on market conditions."""
        # This is a simplified implementation
        # In practice, this could use ML, regime detection, etc.
        n = len(self._basket.components)
        weights = np.ones(n) / n
        
        # Adjust based on volatility regime
        vix = market_data.get("vix", 20.0)
        if vix > 30:
            # High volatility - increase weight of low beta assets
            for i, component in enumerate(self._basket.components):
                if component.beta < 0.8:
                    weights[i] *= 1.5
        elif vix < 15:
            # Low volatility - increase weight of high beta assets
            for i, component in enumerate(self._basket.components):
                if component.beta > 1.2:
                    weights[i] *= 1.5
        
        # Normalize
        weights = weights / np.sum(weights)
        return weights.tolist()
    
    def _apply_weight_constraints(self) -> None:
        """Apply weight constraints to target weights."""
        for component in self._basket.components:
            component.target_weight = max(
                self._config["min_single_position_pct"],
                min(
                    self._config["max_single_position_pct"],
                    component.target_weight
                )
            )
        
        # Normalize
        total_weight = sum(c.target_weight for c in self._basket.components)
        if total_weight > 0:
            for component in self._basket.components:
                component.target_weight /= total_weight
    
    async def _apply_hedge_type_adjustments(self, market_data: Dict[str, Any]) -> None:
        """Apply hedge type-specific adjustments."""
        hedge_type = self.hedge_type
        
        if hedge_type == BasketHedgeType.MARKET_NEUTRAL:
            # Ensure long = short
            long_weight = sum(c.target_weight for c in self._basket.components if c.symbol in market_data.get("long_symbols", []))
            short_weight = 1 - long_weight
            
            if long_weight > 0.6:
                # Reduce long exposure
                for c in self._basket.components:
                    if c.symbol in market_data.get("long_symbols", []):
                        c.target_weight *= 0.5
        
        elif hedge_type == BasketHedgeType.BETA_NEUTRAL:
            # Target beta = 0
            current_beta = sum(c.target_weight * c.beta for c in self._basket.components)
            if abs(current_beta) > 0.1:
                for c in self._basket.components:
                    c.target_weight *= (1 - current_beta / (c.beta + 0.001))
        
        elif hedge_type == BasketHedgeType.VOLATILITY:
            # Volatility targeting
            current_vol = self._basket.volatility
            target_vol = self._config["target_volatility"]
            if current_vol > 0:
                scale = target_vol / current_vol
                for c in self._basket.components:
                    c.target_weight *= scale
    
    async def _generate_rebalance_trades(self) -> List[Dict[str, Any]]:
        """Generate trades for rebalancing."""
        trades = []
        
        with self._lock:
            total_value = self._basket.total_value
            
            for component in self._basket.components:
                current_value = component.current_weight * total_value
                target_value = component.target_weight * total_value
                difference = target_value - current_value
                
                if abs(difference) > self._config["min_single_position_pct"] * total_value:
                    trades.append({
                        "symbol": component.symbol,
                        "side": "BUY" if difference > 0 else "SELL",
                        "size": abs(difference) / component.current_price if component.current_price > 0 else 0,
                        "price": component.current_price,
                        "value": abs(difference),
                        "reason": f"Rebalance: {component.current_weight:.2%} -> {component.target_weight:.2%}",
                    })
        
        return trades
    
    async def _execute_rebalance_trade(self, trade: Dict[str, Any]) -> None:
        """Execute a rebalancing trade."""
        try:
            # Place order through portfolio manager
            if self.portfolio_manager:
                order = await self.portfolio_manager.place_order(
                    symbol=trade["symbol"],
                    side=trade["side"],
                    size=trade["size"],
                    order_type="MARKET",
                    metadata={"strategy": self.name, "reason": trade.get("reason", "basket_rebalance")},
                )
                
                # Update component
                with self._lock:
                    for component in self._basket.components:
                        if component.symbol == trade["symbol"]:
                            if trade["side"] == "BUY":
                                component.position_size += trade["size"]
                                component.entry_price = trade["price"]
                            else:
                                component.position_size -= trade["size"]
                
                self._performance["trades"] += 1
                self._performance["total_pnl"] += 0  # Will be updated later
                
                logger.info(
                    "rebalance_trade_executed",
                    symbol=trade["symbol"],
                    side=trade["side"],
                    size=trade["size"],
                    order_id=order.get("order_id"),
                )
        
        except Exception as e:
            logger.error(
                "rebalance_trade_failed",
                trade=trade,
                error=str(e),
            )
    
    async def _generate_basket_signal(self, market_data: Dict[str, Any]) -> Optional[HedgeSignal]:
        """Generate a hedge signal for the basket."""
        try:
            # Determine if basket needs hedging
            if len(self._basket.components) < self._config["min_components"]:
                return None
            
            # Calculate hedge ratio
            hedge_ratio = 1 - self._basket.hedging_effectiveness
            
            # Determine direction
            direction = HedgeDirection.NONE
            if self._basket.net_exposure > 0:
                direction = HedgeDirection.SHORT
            elif self._basket.net_exposure < 0:
                direction = HedgeDirection.LONG
            
            # Calculate size
            size = abs(self._basket.net_exposure) * hedge_ratio / self._basket.total_value
            
            # Calculate confidence
            confidence = self._calculate_basket_confidence(market_data)
            
            if confidence > self.config.min_confidence and size > 0:
                return HedgeSignal(
                    hedge_type=HedgeType.BASKET,
                    direction=direction,
                    size=size,
                    confidence=confidence,
                    reason=f"Basket hedge signal based on {self.hedge_type.value}",
                    metadata={
                        "basket_id": self._basket.basket_id,
                        "net_exposure": self._basket.net_exposure,
                        "hedge_ratio": hedge_ratio,
                        "components": len(self._basket.components),
                    }
                )
            
            return None
            
        except Exception as e:
            logger.error("basket_signal_generation_error", error=str(e))
            return None
    
    def _calculate_basket_confidence(self, market_data: Dict[str, Any]) -> float:
        """Calculate confidence in the basket hedge signal."""
        confidence = 0.5
        
        # Component count confidence
        if len(self._basket.components) >= self._config["min_components"]:
            confidence += 0.1
        
        # Diversification confidence
        weights = [c.current_weight for c in self._basket.components]
        if len(set(weights)) / len(weights) > 0.5:
            confidence += 0.1
        
        # Volatility confidence
        if self._basket.volatility < self._config["target_volatility"]:
            confidence += 0.1
        
        # Beta confidence
        if abs(self._basket.beta) < 0.3:
            confidence += 0.1
        
        # Hedging effectiveness confidence
        if self._basket.hedging_effectiveness > 0.7:
            confidence += 0.1
        
        # Clamp
        return max(0.1, min(0.95, confidence))
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get strategy metrics."""
        with self._lock:
            return {
                "basket_id": self._basket.basket_id,
                "components": len(self._basket.components),
                "total_value": self._basket.total_value,
                "total_pnl": self._basket.total_pnl,
                "total_pnl_pct": self._basket.total_pnl_pct,
                "net_exposure": self._basket.net_exposure,
                "gross_exposure": self._basket.gross_exposure,
                "leverage": self._basket.leverage,
                "volatility": self._basket.volatility,
                "beta": self._basket.beta,
                "hedging_effectiveness": self._basket.hedging_effectiveness,
                "rebalances": self._performance["rebalances"],
                "trades": self._performance["trades"],
                "total_pnl_performance": self._performance["total_pnl"],
                "config": self._config,
            }
    
    def get_basket_state(self) -> Dict[str, Any]:
        """Get current basket state."""
        with self._lock:
            return self._basket.to_dict()
    
    def get_component_weights(self) -> Dict[str, float]:
        """Get current component weights."""
        with self._lock:
            return {
                c.symbol: {
                    "current": c.current_weight,
                    "target": c.target_weight,
                    "deviation": c.current_weight - c.target_weight,
                }
                for c in self._basket.components
            }
    
    def add_component(self, symbol: str, **kwargs) -> None:
        """
        Add a component to the basket.
        
        Args:
            symbol: Symbol to add
            **kwargs: Additional component parameters
        """
        with self._lock:
            if any(c.symbol == symbol for c in self._basket.components):
                return
            
            component = BasketComponent(symbol=symbol, **kwargs)
            self._basket.components.append(component)
            
            logger.info("basket_component_added", symbol=symbol)
    
    def remove_component(self, symbol: str) -> None:
        """
        Remove a component from the basket.
        
        Args:
            symbol: Symbol to remove
        """
        with self._lock:
            self._basket.components = [c for c in self._basket.components if c.symbol != symbol]
            logger.info("basket_component_removed", symbol=symbol)
    
    def start(self) -> None:
        """Start the strategy."""
        self._running = True
        logger.info("basket_hedge_strategy_started")
    
    def stop(self) -> None:
        """Stop the strategy."""
        self._running = False
        logger.info("basket_hedge_strategy_stopped")
    
    def close(self) -> None:
        """Close the strategy."""
        self._closed = True
        self._running = False
        logger.info("basket_hedge_strategy_closed")


# === MODULE EXPORTS ===

__all__ = [
    "BasketHedgeStrategy",
    "BasketComponent",
    "BasketState",
    "BasketWeightingMethod",
    "BasketRebalanceTrigger",
    "BasketHedgeType",
]

logger.info("basket_hedge_module_loaded", version="3.0.0")
