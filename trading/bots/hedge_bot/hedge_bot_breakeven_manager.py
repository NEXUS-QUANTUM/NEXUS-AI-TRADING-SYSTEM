# trading/bots/hedge_bot/hedge_bot_breakeven_manager.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Breakeven Manager Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Breakeven Manager Module

This module provides comprehensive breakeven analysis and management
capabilities for the NEXUS Hedge Bot system. It calculates breakeven
points, monitors positions, and manages breakeven strategies.

The module covers:
- Breakeven Point Calculation
- Dynamic Breakeven Analysis
- Position Breakeven Monitoring
- Breakeven Strategy Management
- Cost Analysis
- Risk-Reward Analysis
- Breakeven Adjustments
- Trailing Breakeven
- Partial Profit Taking
- Breakeven Alerts
- Breakeven Reporting
"""

import os
import sys
import json
import math
import logging
import numpy as np
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from decimal import Decimal, getcontext

logger = logging.getLogger(__name__)


# ============================================================
# BREAKEVEN ENUMS
# ============================================================

class BreakevenType(Enum):
    """Breakeven types"""
    SIMPLE = "simple"
    DYNAMIC = "dynamic"
    TRAILING = "trailing"
    PARTIAL = "partial"
    ADAPTIVE = "adaptive"
    RISK_BASED = "risk_based"


class BreakevenStatus(Enum):
    """Breakeven status"""
    ABOVE = "above"
    BELOW = "below"
    AT = "at"
    APPROACHING = "approaching"
    BREACHED = "breached"
    PROTECTED = "protected"


class BreakevenAction(Enum):
    """Breakeven actions"""
    HOLD = "hold"
    ADJUST = "adjust"
    CLOSE = "close"
    PARTIAL_CLOSE = "partial_close"
    BREAKEVEN_STOP = "breakeven_stop"
    TRAIL_STOP = "trail_stop"


# ============================================================
# BREAKEVEN DATACLASSES
# ============================================================

@dataclass
class BreakevenMetrics:
    """Breakeven metrics"""
    symbol: str
    entry_price: float
    breakeven_price: float
    current_price: float
    distance: float
    distance_percent: float
    status: BreakevenStatus
    type: BreakevenType
    adjusted_at: Optional[datetime] = None
    adjustments_count: int = 0
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "breakeven_price": self.breakeven_price,
            "current_price": self.current_price,
            "distance": self.distance,
            "distance_percent": self.distance_percent,
            "status": self.status.value,
            "type": self.type.value,
            "adjusted_at": self.adjusted_at.isoformat() if self.adjusted_at else None,
            "adjustments_count": self.adjustments_count,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class BreakevenStrategy:
    """Breakeven strategy"""
    id: str
    name: str
    type: BreakevenType
    parameters: Dict[str, Any]
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "parameters": self.parameters,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class BreakevenAlert:
    """Breakeven alert"""
    id: str
    symbol: str
    breakeven_price: float
    current_price: float
    threshold: float
    status: BreakevenStatus
    action: BreakevenAction
    triggered_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "breakeven_price": self.breakeven_price,
            "current_price": self.current_price,
            "threshold": self.threshold,
            "status": self.status.value,
            "action": self.action.value,
            "triggered_at": self.triggered_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "details": self.details,
        }


# ============================================================
# BREAKEVEN MANAGER
# ============================================================

class BreakevenManager:
    """
    Comprehensive breakeven manager for the hedge bot
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the breakeven manager
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_type = self.config.get("default_type", BreakevenType.SIMPLE.value)
        self.breakeven_threshold = self.config.get("breakeven_threshold", 0.01)
        self.trailing_distance = self.config.get("trailing_distance", 0.02)
        self.partial_close_percent = self.config.get("partial_close_percent", 0.50)
        
        # State
        self.metrics_cache: Dict[str, BreakevenMetrics] = {}
        self.strategies: Dict[str, BreakevenStrategy] = {}
        self.alerts: Dict[str, BreakevenAlert] = {}
        
        # Initialize default strategies
        self._init_default_strategies()
        
        logger.info("Breakeven manager initialized")
    
    # ============================================================
    # DEFAULT STRATEGIES
    # ============================================================
    
    def _init_default_strategies(self) -> None:
        """Initialize default breakeven strategies"""
        strategies = [
            BreakevenStrategy(
                id="strategy_simple",
                name="Simple Breakeven",
                type=BreakevenType.SIMPLE,
                parameters={
                    "threshold": self.breakeven_threshold,
                    "action": "breakeven_stop",
                },
            ),
            BreakevenStrategy(
                id="strategy_trailing",
                name="Trailing Breakeven",
                type=BreakevenType.TRAILING,
                parameters={
                    "trailing_distance": self.trailing_distance,
                    "min_profit": self.breakeven_threshold,
                },
            ),
            BreakevenStrategy(
                id="strategy_partial",
                name="Partial Profit Taking",
                type=BreakevenType.PARTIAL,
                parameters={
                    "partial_close_percent": self.partial_close_percent,
                    "breakeven_profit": self.breakeven_threshold,
                },
            ),
            BreakevenStrategy(
                id="strategy_adaptive",
                name="Adaptive Breakeven",
                type=BreakevenType.ADAPTIVE,
                parameters={
                    "volatility_multiplier": 1.5,
                    "min_distance": 0.01,
                    "max_distance": 0.05,
                },
            ),
        ]
        
        for strategy in strategies:
            self.strategies[strategy.id] = strategy
        
        logger.info(f"Initialized {len(strategies)} breakeven strategies")
    
    # ============================================================
    # BREAKEVEN CALCULATION
    # ============================================================
    
    def calculate_breakeven(
        self,
        entry_price: float,
        position_size: float,
        fees: float = 0.0,
        slippage: float = 0.0,
        financing: float = 0.0,
        type: BreakevenType = BreakevenType.SIMPLE,
        parameters: Optional[Dict[str, Any]] = None,
        symbol: str = "unknown"
    ) -> BreakevenMetrics:
        """
        Calculate breakeven price
        
        Args:
            entry_price: Entry price
            position_size: Position size
            fees: Transaction fees
            slippage: Slippage cost
            financing: Financing costs
            type: Breakeven type
            parameters: Additional parameters
            symbol: Asset symbol
            
        Returns:
            BreakevenMetrics
        """
        if parameters is None:
            parameters = {}
        
        # Calculate base breakeven
        total_cost = fees + slippage + financing
        breakeven_price = entry_price + (total_cost / position_size)
        
        # Adjust based on type
        if type == BreakevenType.SIMPLE:
            pass  # Use base breakeven
        
        elif type == BreakevenType.DYNAMIC:
            volatility = parameters.get("volatility", 0.02)
            multiplier = parameters.get("multiplier", 1.5)
            breakeven_price += entry_price * volatility * multiplier
        
        elif type == BreakevenType.TRAILING:
            trailing_distance = parameters.get("trailing_distance", self.trailing_distance)
            min_profit = parameters.get("min_profit", self.breakeven_threshold)
            # Trailing breakeven will be updated dynamically
        
        elif type == BreakevenType.PARTIAL:
            partial_close_percent = parameters.get("partial_close_percent", self.partial_close_percent)
            breakeven_profit = parameters.get("breakeven_profit", self.breakeven_threshold)
        
        elif type == BreakevenType.ADAPTIVE:
            volatility = parameters.get("volatility", 0.02)
            volatility_multiplier = parameters.get("volatility_multiplier", 1.5)
            min_distance = parameters.get("min_distance", 0.01)
            max_distance = parameters.get("max_distance", 0.05)
            
            distance = entry_price * volatility * volatility_multiplier
            distance = max(distance, entry_price * min_distance)
            distance = min(distance, entry_price * max_distance)
            breakeven_price += distance
        
        elif type == BreakevenType.RISK_BASED:
            risk_percentage = parameters.get("risk_percentage", 0.02)
            breakeven_price = entry_price * (1 + risk_percentage)
        
        # Calculate metrics
        current_price = parameters.get("current_price", entry_price)
        distance = current_price - breakeven_price
        distance_percent = distance / entry_price if entry_price > 0 else 0
        
        # Determine status
        if distance > self.breakeven_threshold * entry_price:
            status = BreakevenStatus.ABOVE
        elif distance < -self.breakeven_threshold * entry_price:
            status = BreakevenStatus.BELOW
        else:
            status = BreakevenStatus.AT
        
        if abs(distance) < 0.5 * self.breakeven_threshold * entry_price:
            status = BreakevenStatus.APPROACHING
        
        metrics = BreakevenMetrics(
            symbol=symbol,
            entry_price=entry_price,
            breakeven_price=breakeven_price,
            current_price=current_price,
            distance=distance,
            distance_percent=distance_percent,
            status=status,
            type=type,
            details={
                "fees": fees,
                "slippage": slippage,
                "financing": financing,
                "position_size": position_size,
                "parameters": parameters,
            },
        )
        
        self.metrics_cache[symbol] = metrics
        return metrics
    
    # ============================================================
    # BREAKEVEN STRATEGIES
    # ============================================================
    
    def apply_strategy(
        self,
        metrics: BreakevenMetrics,
        strategy_id: str
    ) -> Tuple[BreakevenMetrics, Optional[BreakevenAction]]:
        """
        Apply a breakeven strategy
        
        Args:
            metrics: Breakeven metrics
            strategy_id: Strategy ID
            
        Returns:
            (Updated metrics, Action)
        """
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return metrics, None
        
        action = None
        
        if strategy.type == BreakevenType.SIMPLE:
            action = self._apply_simple_strategy(metrics, strategy)
        
        elif strategy.type == BreakevenType.TRAILING:
            action = self._apply_trailing_strategy(metrics, strategy)
        
        elif strategy.type == BreakevenType.PARTIAL:
            action = self._apply_partial_strategy(metrics, strategy)
        
        elif strategy.type == BreakevenType.ADAPTIVE:
            action = self._apply_adaptive_strategy(metrics, strategy)
        
        elif strategy.type == BreakevenType.RISK_BASED:
            action = self._apply_risk_based_strategy(metrics, strategy)
        
        # Update metrics if action taken
        if action:
            metrics.adjustments_count += 1
            metrics.adjusted_at = datetime.now()
            metrics.details["last_action"] = action.value
        
        return metrics, action
    
    def _apply_simple_strategy(
        self,
        metrics: BreakevenMetrics,
        strategy: BreakevenStrategy
    ) -> Optional[BreakevenAction]:
        """Apply simple breakeven strategy"""
        threshold = strategy.parameters.get("threshold", self.breakeven_threshold)
        
        if metrics.status == BreakevenStatus.BELOW:
            return BreakevenAction.CLOSE
        
        if metrics.status == BreakevenStatus.APPROACHING:
            return BreakevenAction.BREAKEVEN_STOP
        
        return None
    
    def _apply_trailing_strategy(
        self,
        metrics: BreakevenMetrics,
        strategy: BreakevenStrategy
    ) -> Optional[BreakevenAction]:
        """Apply trailing breakeven strategy"""
        trailing_distance = strategy.parameters.get("trailing_distance", self.trailing_distance)
        min_profit = strategy.parameters.get("min_profit", self.breakeven_threshold)
        
        # Calculate trailing breakeven
        current_price = metrics.current_price
        trailing_breakeven = current_price * (1 - trailing_distance)
        
        if trailing_breakeven > metrics.breakeven_price:
            # Update breakeven price
            old_breakeven = metrics.breakeven_price
            metrics.breakeven_price = trailing_breakeven
            
            # Check if we should take action
            profit_percent = (current_price - metrics.entry_price) / metrics.entry_price
            
            if profit_percent < min_profit and metrics.status == BreakevenStatus.APPROACHING:
                return BreakevenAction.BREAKEVEN_STOP
            
            if profit_percent > min_profit and metrics.distance_percent < -min_profit:
                return BreakevenAction.TRAIL_STOP
        
        return None
    
    def _apply_partial_strategy(
        self,
        metrics: BreakevenMetrics,
        strategy: BreakevenStrategy
    ) -> Optional[BreakevenAction]:
        """Apply partial profit taking strategy"""
        partial_close_percent = strategy.parameters.get("partial_close_percent", self.partial_close_percent)
        breakeven_profit = strategy.parameters.get("breakeven_profit", self.breakeven_threshold)
        
        profit_percent = (metrics.current_price - metrics.entry_price) / metrics.entry_price
        
        if profit_percent > breakeven_profit:
            return BreakevenAction.PARTIAL_CLOSE
        
        if profit_percent < -breakeven_profit:
            return BreakevenAction.BREAKEVEN_STOP
        
        return None
    
    def _apply_adaptive_strategy(
        self,
        metrics: BreakevenMetrics,
        strategy: BreakevenStrategy
    ) -> Optional[BreakevenAction]:
        """Apply adaptive breakeven strategy"""
        volatility = strategy.parameters.get("volatility_multiplier", 1.5)
        min_distance = strategy.parameters.get("min_distance", 0.01)
        max_distance = strategy.parameters.get("max_distance", 0.05)
        
        # Calculate adaptive breakeven
        current_price = metrics.current_price
        entry_price = metrics.entry_price
        price_change = abs(current_price - entry_price) / entry_price
        
        if price_change < min_distance:
            return None
        
        adaptive_factor = min(max(price_change, min_distance), max_distance)
        adaptive_breakeven = entry_price * (1 + adaptive_factor * volatility)
        
        if adaptive_breakeven > metrics.breakeven_price:
            metrics.breakeven_price = adaptive_breakeven
        
        return None
    
    def _apply_risk_based_strategy(
        self,
        metrics: BreakevenMetrics,
        strategy: BreakevenStrategy
    ) -> Optional[BreakevenAction]:
        """Apply risk-based breakeven strategy"""
        risk_percentage = strategy.parameters.get("risk_percentage", 0.02)
        
        # Risk-based breakeven
        breakeven_price = metrics.entry_price * (1 + risk_percentage)
        
        if metrics.current_price < breakeven_price:
            return BreakevenAction.CLOSE
        
        return None
    
    # ============================================================
    # BREAKEVEN MONITORING
    # ============================================================
    
    def monitor_position(
        self,
        symbol: str,
        current_price: float,
        entry_price: Optional[float] = None,
        position_size: Optional[float] = None,
        fees: float = 0.0,
        slippage: float = 0.0,
        financing: float = 0.0,
        strategy_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Monitor a position for breakeven
        
        Args:
            symbol: Asset symbol
            current_price: Current price
            entry_price: Entry price
            position_size: Position size
            fees: Transaction fees
            slippage: Slippage cost
            financing: Financing costs
            strategy_id: Strategy ID
            
        Returns:
            Monitoring result
        """
        # Get or create metrics
        metrics = self.metrics_cache.get(symbol)
        
        if not metrics or entry_price is not None:
            if entry_price is None:
                entry_price = current_price
            if position_size is None:
                position_size = 1.0
            
            metrics = self.calculate_breakeven(
                entry_price=entry_price,
                position_size=position_size,
                fees=fees,
                slippage=slippage,
                financing=financing,
                symbol=symbol,
                parameters={"current_price": current_price},
            )
        
        # Update current price
        metrics.current_price = current_price
        
        # Update distance
        metrics.distance = current_price - metrics.breakeven_price
        metrics.distance_percent = metrics.distance / metrics.entry_price if metrics.entry_price > 0 else 0
        
        # Update status
        if metrics.distance > self.breakeven_threshold * metrics.entry_price:
            metrics.status = BreakevenStatus.ABOVE
        elif metrics.distance < -self.breakeven_threshold * metrics.entry_price:
            metrics.status = BreakevenStatus.BELOW
        else:
            metrics.status = BreakevenStatus.AT
        
        if abs(metrics.distance) < 0.5 * self.breakeven_threshold * metrics.entry_price:
            metrics.status = BreakevenStatus.APPROACHING
        
        # Apply strategy
        action = None
        if strategy_id:
            metrics, action = self.apply_strategy(metrics, strategy_id)
        
        # Check for alerts
        alert = None
        if metrics.status in [BreakevenStatus.APPROACHING, BreakevenStatus.BELOW]:
            alert = self._create_alert(metrics, action)
        
        result = {
            "metrics": metrics.to_dict(),
            "action": action.value if action else None,
            "alert": alert.to_dict() if alert else None,
            "timestamp": datetime.now().isoformat(),
        }
        
        return result
    
    def _create_alert(
        self,
        metrics: BreakevenMetrics,
        action: Optional[BreakevenAction]
    ) -> BreakevenAlert:
        """
        Create a breakeven alert
        
        Args:
            metrics: Breakeven metrics
            action: Recommended action
            
        Returns:
            BreakevenAlert
        """
        alert = BreakevenAlert(
            id=f"alert_{int(time.time())}_{metrics.symbol}",
            symbol=metrics.symbol,
            breakeven_price=metrics.breakeven_price,
            current_price=metrics.current_price,
            threshold=self.breakeven_threshold * metrics.entry_price,
            status=metrics.status,
            action=action or BreakevenAction.HOLD,
            details={
                "entry_price": metrics.entry_price,
                "distance": metrics.distance,
                "distance_percent": metrics.distance_percent,
            },
        )
        
        self.alerts[alert.id] = alert
        return alert
    
    # ============================================================
    # BREAKEVEN OPTIMIZATION
    # ============================================================
    
    def optimize_breakeven(
        self,
        symbol: str,
        historical_prices: List[float],
        entry_price: Optional[float] = None,
        volatility: float = 0.02
    ) -> Dict[str, Any]:
        """
        Optimize breakeven parameters
        
        Args:
            symbol: Asset symbol
            historical_prices: Historical price data
            entry_price: Entry price
            volatility: Volatility estimate
            
        Returns:
            Optimization results
        """
        if entry_price is None:
            entry_price = historical_prices[-1] if historical_prices else 100.0
        
        # Calculate various breakeven levels
        simple_breakeven = entry_price * (1 + self.breakeven_threshold)
        
        # Volatility-based breakeven
        vol_breakeven = entry_price * (1 + volatility * 1.5)
        
        # Historical support/resistance based
        if historical_prices:
            support = min(historical_prices)
            resistance = max(historical_prices)
            support_breakeven = (entry_price + support) / 2
            resistance_breakeven = (entry_price + resistance) / 2
        else:
            support_breakeven = entry_price * 0.95
            resistance_breakeven = entry_price * 1.05
        
        # Find optimal breakeven
        optimal = max(simple_breakeven, support_breakeven)
        
        return {
            "symbol": symbol,
            "entry_price": entry_price,
            "breakeven_levels": {
                "simple": simple_breakeven,
                "volatility_based": vol_breakeven,
                "support_based": support_breakeven,
                "resistance_based": resistance_breakeven,
            },
            "optimal_breakeven": optimal,
            "volatility": volatility,
            "timestamp": datetime.now().isoformat(),
        }
    
    # ============================================================
    # POSITION BREAKEVEN ANALYSIS
    # ============================================================
    
    def analyze_position_breakeven(
        self,
        position: Dict[str, Any],
        fees: float = 0.001,
        slippage: float = 0.0005
    ) -> Dict[str, Any]:
        """
        Analyze breakeven for a position
        
        Args:
            position: Position data
            fees: Fee percentage
            slippage: Slippage percentage
            
        Returns:
            Breakeven analysis
        """
        symbol = position.get("symbol", "unknown")
        entry_price = position.get("entry_price", 0)
        position_size = position.get("quantity", 0)
        current_price = position.get("current_price", entry_price)
        
        if entry_price <= 0 or position_size <= 0:
            return {"error": "Invalid position data"}
        
        # Calculate costs
        entry_fees = entry_price * position_size * fees
        exit_fees = current_price * position_size * fees
        entry_slippage = entry_price * position_size * slippage
        exit_slippage = current_price * position_size * slippage
        total_costs = entry_fees + exit_fees + entry_slippage + exit_slippage
        
        # Calculate breakeven
        breakeven_price = entry_price + (total_costs / position_size)
        
        # Calculate profit/loss
        pnl = (current_price - entry_price) * position_size - total_costs
        pnl_percent = (current_price - entry_price) / entry_price - (total_costs / (entry_price * position_size))
        
        # Calculate risk-reward
        stop_loss = position.get("stop_loss", entry_price * 0.95)
        take_profit = position.get("take_profit", entry_price * 1.10)
        
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        # Determine status
        if current_price > breakeven_price:
            status = "profitable"
        elif current_price < breakeven_price:
            status = "losing"
        else:
            status = "breakeven"
        
        return {
            "symbol": symbol,
            "entry_price": entry_price,
            "current_price": current_price,
            "position_size": position_size,
            "breakeven_price": breakeven_price,
            "total_costs": total_costs,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "status": status,
            "risk_reward_ratio": risk_reward_ratio,
            "distance_to_breakeven": current_price - breakeven_price,
            "distance_percent": (current_price - breakeven_price) / entry_price,
            "timestamp": datetime.now().isoformat(),
        }
    
    # ============================================================
    # BREAKEVEN ADJUSTMENTS
    # ============================================================
    
    def adjust_breakeven(
        self,
        symbol: str,
        new_breakeven_price: float,
        reason: str = "manual_adjustment"
    ) -> bool:
        """
        Adjust breakeven price
        
        Args:
            symbol: Asset symbol
            new_breakeven_price: New breakeven price
            reason: Adjustment reason
            
        Returns:
            True if adjusted
        """
        metrics = self.metrics_cache.get(symbol)
        if not metrics:
            return False
        
        old_breakeven = metrics.breakeven_price
        metrics.breakeven_price = new_breakeven_price
        metrics.adjustments_count += 1
        metrics.adjusted_at = datetime.now()
        
        metrics.details["last_adjustment"] = {
            "old_breakeven": old_breakeven,
            "new_breakeven": new_breakeven_price,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
        
        logger.info(f"Adjusted breakeven for {symbol}: {old_breakeven} -> {new_breakeven_price}")
        return True
    
    # ============================================================
    # GETTER METHODS
    # ============================================================
    
    def get_metrics(self, symbol: str) -> Optional[BreakevenMetrics]:
        """
        Get breakeven metrics for a symbol
        
        Args:
            symbol: Asset symbol
            
        Returns:
            BreakevenMetrics or None
        """
        return self.metrics_cache.get(symbol)
    
    def get_alerts(self, symbol: Optional[str] = None) -> List[BreakevenAlert]:
        """
        Get breakeven alerts
        
        Args:
            symbol: Filter by symbol
            
        Returns:
            List of alerts
        """
        alerts = list(self.alerts.values())
        if symbol:
            alerts = [a for a in alerts if a.symbol == symbol]
        return alerts
    
    def get_strategies(self) -> List[BreakevenStrategy]:
        """
        Get breakeven strategies
        
        Returns:
            List of strategies
        """
        return list(self.strategies.values())
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get breakeven statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_positions": len(self.metrics_cache),
            "breakeven_positions": len([m for m in self.metrics_cache.values() if m.status == BreakevenStatus.AT]),
            "profitable_positions": len([m for m in self.metrics_cache.values() if m.status == BreakevenStatus.ABOVE]),
            "losing_positions": len([m for m in self.metrics_cache.values() if m.status == BreakevenStatus.BELOW]),
            "total_adjustments": sum(m.adjustments_count for m in self.metrics_cache.values()),
            "total_alerts": len(self.alerts),
            "active_strategies": len([s for s in self.strategies.values() if s.is_active]),
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "BreakevenType",
    "BreakevenStatus",
    "BreakevenAction",
    
    # Dataclasses
    "BreakevenMetrics",
    "BreakevenStrategy",
    "BreakevenAlert",
    
    # Classes
    "BreakevenManager",
]

# ============================================================
# END OF MODULE
# ============================================================
