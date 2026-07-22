# trading/bots/hedge_bot/strategies/base_strategy.py

"""
NEXUS HEDGE BOT - BASE STRATEGY
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Abstract base class for all hedging strategies with common interface,
lifecycle management, and utility functions.

Version: 3.0.0
"""

import asyncio
import json
import threading
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, TypeVar, Generic

import structlog
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field, validator

from ..core.hedge_types import HedgeSignal, HedgeType, HedgeDirection
from ..core.market_data import MarketDataProvider

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class StrategyStatus(str, Enum):
    """Strategy lifecycle status."""
    INITIALIZED = "initialized"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    CLOSED = "closed"
    ERROR = "error"


class StrategyType(str, Enum):
    """Types of hedging strategies."""
    DELTA = "delta"
    GAMMA = "gamma"
    VEGA = "vega"
    BETA = "beta"
    CORRELATION = "correlation"
    VOLATILITY = "volatility"
    ARBITRAGE = "arbitrage"
    STATISTICAL = "statistical"
    ADAPTIVE = "adaptive"
    HYBRID = "hybrid"
    CUSTOM = "custom"


class RiskProfile(str, Enum):
    """Risk profiles for strategies."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# === DATA MODELS ===

@dataclass
class StrategyConfig:
    """Base configuration for hedging strategies."""
    name: str = ""
    strategy_type: StrategyType = StrategyType.CUSTOM
    risk_profile: RiskProfile = RiskProfile.MEDIUM
    enabled: bool = True
    max_position_size: float = 0.10
    min_position_size: float = 0.01
    max_leverage: float = 1.0
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.10
    max_drawdown_pct: float = 0.15
    target_hedge_ratio: float = 0.75
    rebalance_threshold: float = 0.02
    cooldown_seconds: int = 60
    min_confidence: float = 0.30
    max_confidence: float = 0.95
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "strategy_type": self.strategy_type.value,
            "risk_profile": self.risk_profile.value,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyConfig":
        data = data.copy()
        data["strategy_type"] = StrategyType(data["strategy_type"])
        data["risk_profile"] = RiskProfile(data["risk_profile"])
        return cls(**data)


@dataclass
class StrategyMetrics:
    """Performance metrics for a strategy."""
    total_pnl: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_trade_pnl: float = 0.0
    max_drawdown_pct: float = 0.0
    current_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    profit_factor: float = 0.0
    avg_holding_time: float = 0.0
    avg_trade_size: float = 0.0
    max_trade_size: float = 0.0
    min_trade_size: float = 0.0
    exposure_avg: float = 0.0
    exposure_max: float = 0.0
    hedge_effectiveness: float = 0.0
    tracking_error: float = 0.0
    total_fees: float = 0.0
    total_slippage: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StrategyState:
    """Current state of a strategy."""
    status: StrategyStatus = StrategyStatus.INITIALIZED
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    last_signal: Optional[HedgeSignal] = None
    current_positions: List[Dict[str, Any]] = field(default_factory=list)
    open_trades: List[Dict[str, Any]] = field(default_factory=list)
    closed_trades: List[Dict[str, Any]] = field(default_factory=list)
    pending_orders: List[Dict[str, Any]] = field(default_factory=list)
    error_count: int = 0
    last_error: Optional[str] = None
    active: bool = False
    paused: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "status": self.status.value,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_signal": self.last_signal.to_dict() if self.last_signal else None,
        }


# === BASE STRATEGY CLASS ===

class BaseStrategy(ABC):
    """
    Abstract base class for all hedging strategies.
    Provides common interface, lifecycle management, and utility functions.
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[Union[StrategyConfig, Dict[str, Any]]] = None,
        market_data: Optional[MarketDataProvider] = None,
        **kwargs
    ):
        """
        Initialize the base strategy.
        
        Args:
            name: Unique strategy name
            config: Strategy configuration
            market_data: Market data provider
            **kwargs: Additional arguments
        """
        self.name = name
        self.market_data = market_data
        
        # Initialize config
        if isinstance(config, dict):
            self.config = StrategyConfig.from_dict(config)
            self.config.name = name
        elif isinstance(config, StrategyConfig):
            self.config = config
            self.config.name = name
        else:
            self.config = StrategyConfig(name=name)
        
        # State management
        self._lock = threading.RLock()
        self._state = StrategyState()
        self._metrics = StrategyMetrics()
        self._running = False
        self._closed = False
        
        # History
        self._signal_history: List[HedgeSignal] = []
        self._result_history: List[Dict[str, Any]] = []
        self._trade_history: List[Dict[str, Any]] = []
        self._error_history: List[Dict[str, Any]] = []
        
        # Performance tracking
        self._start_time: Optional[datetime] = None
        self._last_performance_update: Optional[datetime] = None
        self._performance_cache: Dict[str, Any] = {}
        
        # Dependency injection
        self._dependencies: Dict[str, Any] = {}
        
        # Initialize
        self._state.status = StrategyStatus.INITIALIZED
        
        logger.info(
            "base_strategy_initialized",
            name=name,
            strategy_type=self.config.strategy_type.value,
            risk_profile=self.config.risk_profile.value,
        )
    
    # === Abstract Methods ===
    
    @abstractmethod
    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and generate trading signals.
        
        Args:
            market_data: Current market data
            
        Returns:
            Analysis results with signals
        """
        pass
    
    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get strategy performance metrics.
        
        Returns:
            Dictionary of metrics
        """
        pass
    
    # === Lifecycle Methods ===
    
    def start(self) -> None:
        """Start the strategy."""
        with self._lock:
            if self._closed:
                raise RuntimeError("Strategy is closed")
            
            if self._running:
                logger.warning("strategy_already_running", name=self.name)
                return
            
            self._running = True
            self._state.active = True
            self._state.status = StrategyStatus.RUNNING
            self._start_time = datetime.utcnow()
            
            logger.info("strategy_started", name=self.name)
    
    def stop(self) -> None:
        """Stop the strategy."""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            self._state.active = False
            self._state.status = StrategyStatus.STOPPED
            
            logger.info("strategy_stopped", name=self.name)
    
    def pause(self) -> None:
        """Pause the strategy."""
        with self._lock:
            if not self._running:
                return
            
            self._state.paused = True
            self._state.status = StrategyStatus.PAUSED
            
            logger.info("strategy_paused", name=self.name)
    
    def resume(self) -> None:
        """Resume the strategy."""
        with self._lock:
            if not self._running:
                return
            
            self._state.paused = False
            self._state.status = StrategyStatus.RUNNING
            
            logger.info("strategy_resumed", name=self.name)
    
    def close(self) -> None:
        """Close the strategy permanently."""
        with self._lock:
            if self._closed:
                return
            
            self._running = False
            self._closed = True
            self._state.active = False
            self._state.status = StrategyStatus.CLOSED
            
            # Close all positions
            self._close_all_positions()
            
            logger.info("strategy_closed", name=self.name)
    
    # === Core Methods ===
    
    async def execute(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the strategy analysis and trading.
        
        Args:
            market_data: Current market data
            
        Returns:
            Execution results
        """
        if not self._running or self._state.paused:
            return {
                "status": "paused" if self._state.paused else "stopped",
                "name": self.name,
            }
        
        try:
            start_time = time.time()
            
            # Update state
            self._state.last_run = datetime.utcnow()
            self._state.status = StrategyStatus.RUNNING
            
            # Run analysis
            result = await self.analyze(market_data)
            
            # Process results
            if "signal" in result:
                signal = result["signal"]
                if isinstance(signal, dict):
                    signal = HedgeSignal.from_dict(signal)
                self._state.last_signal = signal
                self._signal_history.append(signal)
                
                # Execute signal if valid
                if signal.confidence >= self.config.min_confidence:
                    await self._execute_signal(signal)
            
            # Update metrics
            await self._update_metrics()
            
            # Record execution
            execution_time = (time.time() - start_time) * 1000
            self._result_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "execution_time_ms": execution_time,
                "result": result,
            })
            
            # Limit history
            if len(self._result_history) > 1000:
                self._result_history = self._result_history[-1000:]
            if len(self._signal_history) > 1000:
                self._signal_history = self._signal_history[-1000:]
            
            return {
                "status": "success",
                "name": self.name,
                "execution_time_ms": execution_time,
                "result": result,
            }
            
        except Exception as e:
            self._state.error_count += 1
            self._state.last_error = str(e)
            self._state.status = StrategyStatus.ERROR
            
            self._error_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "traceback": traceback.format_exc(),
            })
            
            logger.error(
                "strategy_execution_failed",
                name=self.name,
                error=str(e),
                traceback=traceback.format_exc(),
            )
            
            return {
                "status": "error",
                "name": self.name,
                "error": str(e),
            }
    
    async def _execute_signal(self, signal: HedgeSignal) -> None:
        """
        Execute a trading signal.
        
        Args:
            signal: Signal to execute
        """
        # This should be implemented by child classes
        # or handled by the portfolio manager
        pass
    
    async def _update_metrics(self) -> None:
        """Update strategy performance metrics."""
        self._last_performance_update = datetime.utcnow()
    
    def _close_all_positions(self) -> None:
        """Close all open positions."""
        # This should be implemented by child classes
        pass
    
    # === Utility Methods ===
    
    def register_dependency(self, name: str, instance: Any) -> None:
        """
        Register a dependency.
        
        Args:
            name: Dependency name
            instance: Dependency instance
        """
        with self._lock:
            self._dependencies[name] = instance
    
    def get_dependency(self, name: str) -> Optional[Any]:
        """
        Get a dependency by name.
        
        Args:
            name: Dependency name
            
        Returns:
            Dependency instance or None
        """
        with self._lock:
            return self._dependencies.get(name)
    
    def get_state(self) -> StrategyState:
        """Get current strategy state."""
        with self._lock:
            return self._state
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return self._metrics.to_dict()
    
    def get_signal_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get signal history.
        
        Args:
            limit: Maximum number of signals
            
        Returns:
            List of signal dictionaries
        """
        with self._lock:
            return [s.to_dict() for s in self._signal_history[-limit:]]
    
    def get_trade_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get trade history.
        
        Args:
            limit: Maximum number of trades
            
        Returns:
            List of trade dictionaries
        """
        with self._lock:
            return self._trade_history[-limit:]
    
    def get_error_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get error history.
        
        Args:
            limit: Maximum number of errors
            
        Returns:
            List of error dictionaries
        """
        with self._lock:
            return self._error_history[-limit:]
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get strategy status.
        
        Returns:
            Status dictionary
        """
        with self._lock:
            return {
                "name": self.name,
                "status": self._state.status.value,
                "running": self._running,
                "closed": self._closed,
                "paused": self._state.paused,
                "active": self._state.active,
                "error_count": self._state.error_count,
                "last_run": self._state.last_run.isoformat() if self._state.last_run else None,
                "start_time": self._start_time.isoformat() if self._start_time else None,
                "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds() if self._start_time else 0,
            }
    
    # === Helper Functions ===
    
    def calculate_position_size(
        self,
        confidence: float,
        capital: float,
        risk_per_trade: float = 0.02,
        max_position: float = None,
        min_position: float = None,
    ) -> float:
        """
        Calculate position size based on confidence and risk.
        
        Args:
            confidence: Signal confidence (0-1)
            capital: Available capital
            risk_per_trade: Risk per trade as fraction of capital
            max_position: Maximum position size
            min_position: Minimum position size
            
        Returns:
            Position size
        """
        max_pos = max_position or self.config.max_position_size
        min_pos = min_position or self.config.min_position_size
        
        # Base size
        base_size = capital * risk_per_trade
        
        # Adjust by confidence
        size = base_size * confidence
        
        # Scale by max position
        size = min(size, capital * max_pos)
        size = max(size, capital * min_pos)
        
        return size
    
    def calculate_stop_loss(
        self,
        price: float,
        direction: HedgeDirection,
        stop_pct: Optional[float] = None,
    ) -> Optional[float]:
        """
        Calculate stop loss price.
        
        Args:
            price: Entry price
            direction: Trade direction
            stop_pct: Stop loss percentage
            
        Returns:
            Stop loss price or None
        """
        if direction == HedgeDirection.NONE or price <= 0:
            return None
        
        stop_pct = stop_pct or self.config.stop_loss_pct
        
        if direction == HedgeDirection.LONG:
            return price * (1 - stop_pct)
        elif direction == HedgeDirection.SHORT:
            return price * (1 + stop_pct)
        else:
            return None
    
    def calculate_take_profit(
        self,
        price: float,
        direction: HedgeDirection,
        profit_pct: Optional[float] = None,
    ) -> Optional[float]:
        """
        Calculate take profit price.
        
        Args:
            price: Entry price
            direction: Trade direction
            profit_pct: Take profit percentage
            
        Returns:
            Take profit price or None
        """
        if direction == HedgeDirection.NONE or price <= 0:
            return None
        
        profit_pct = profit_pct or self.config.take_profit_pct
        
        if direction == HedgeDirection.LONG:
            return price * (1 + profit_pct)
        elif direction == HedgeDirection.SHORT:
            return price * (1 - profit_pct)
        else:
            return None
    
    def calculate_hedge_ratio(
        self,
        delta: float,
        beta: float = 1.0,
        correlation: float = 1.0,
        target_ratio: Optional[float] = None,
    ) -> float:
        """
        Calculate optimal hedge ratio.
        
        Args:
            delta: Delta of the position
            beta: Beta relative to market
            correlation: Correlation with hedge instrument
            target_ratio: Target hedge ratio
            
        Returns:
            Hedge ratio (0-1)
        """
        target = target_ratio or self.config.target_hedge_ratio
        
        # Calculate base ratio
        ratio = delta * beta * correlation
        
        # Apply target adjustment
        ratio = ratio * target
        
        # Clamp
        return max(0, min(1, ratio))
    
    def calculate_sharpe(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0,
    ) -> float:
        """
        Calculate Sharpe ratio.
        
        Args:
            returns: List of returns
            risk_free_rate: Risk-free rate
            
        Returns:
            Sharpe ratio
        """
        if not returns:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        return (mean_return - risk_free_rate) / std_return * np.sqrt(252)
    
    def calculate_sortino(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0,
    ) -> float:
        """
        Calculate Sortino ratio.
        
        Args:
            returns: List of returns
            risk_free_rate: Risk-free rate
            
        Returns:
            Sortino ratio
        """
        if not returns:
            return 0.0
        
        mean_return = np.mean(returns)
        downside_returns = [r for r in returns if r < 0]
        
        if not downside_returns:
            return 0.0
        
        downside_std = np.std(downside_returns)
        
        if downside_std == 0:
            return 0.0
        
        return (mean_return - risk_free_rate) / downside_std * np.sqrt(252)
    
    def calculate_calmar(
        self,
        returns: List[float],
        max_drawdown: float = None,
    ) -> float:
        """
        Calculate Calmar ratio.
        
        Args:
            returns: List of returns
            max_drawdown: Maximum drawdown (if None, calculated)
            
        Returns:
            Calmar ratio
        """
        if not returns:
            return 0.0
        
        mean_return = np.mean(returns) * 252
        
        if max_drawdown is None:
            # Calculate max drawdown
            cumulative = np.cumprod(1 + np.array(returns))
            peak = np.maximum.accumulate(cumulative)
            drawdown = (peak - cumulative) / peak
            max_drawdown = np.max(drawdown)
        
        if max_drawdown == 0:
            return 0.0
        
        return mean_return / max_drawdown
    
    def calculate_drawdown(self, returns: List[float]) -> float:
        """
        Calculate maximum drawdown.
        
        Args:
            returns: List of returns
            
        Returns:
            Maximum drawdown
        """
        if not returns:
            return 0.0
        
        cumulative = np.cumprod(1 + np.array(returns))
        peak = np.maximum.accumulate(cumulative)
        drawdown = (peak - cumulative) / peak
        
        return np.max(drawdown)


# === STRATEGY FACTORY ===

class StrategyFactory:
    """
    Factory for creating strategy instances.
    """
    
    _strategies: Dict[str, Type] = {}
    
    @classmethod
    def register(cls, name: str, strategy_class: Type) -> None:
        """
        Register a strategy class.
        
        Args:
            name: Strategy name
            strategy_class: Strategy class
        """
        cls._strategies[name] = strategy_class
    
    @classmethod
    def create(
        cls,
        name: str,
        strategy_type: Union[str, StrategyType],
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> BaseStrategy:
        """
        Create a strategy instance.
        
        Args:
            name: Strategy name
            strategy_type: Type of strategy
            config: Configuration
            **kwargs: Additional arguments
            
        Returns:
            Strategy instance
        """
        if isinstance(strategy_type, str):
            strategy_type = StrategyType(strategy_type)
        
        # Get strategy class
        strategy_class = cls._strategies.get(strategy_type.value)
        if not strategy_class:
            raise ValueError(f"Strategy type not registered: {strategy_type.value}")
        
        # Create instance
        return strategy_class(name=name, config=config, **kwargs)
    
    @classmethod
    def list_strategies(cls) -> List[str]:
        """List available strategies."""
        return list(cls._strategies.keys())


# === MODULE EXPORTS ===

__all__ = [
    "BaseStrategy",
    "StrategyConfig",
    "StrategyMetrics",
    "StrategyState",
    "StrategyStatus",
    "StrategyType",
    "RiskProfile",
    "StrategyFactory",
]

logger.info("base_strategy_module_loaded", version="3.0.0")
