"""
NEXUS AI TRADING SYSTEM - Position Sizer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced position sizing system for calculating optimal position sizes
based on risk parameters, account equity, volatility, and various
position sizing strategies.
"""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from prometheus_client import Counter, Gauge, Histogram

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
POSITION_SIZER_COUNTER = Counter(
    "nexus_position_sizer_calculations_total",
    "Total number of position size calculations",
    ["strategy", "status"],
)
POSITION_SIZER_DURATION = Histogram(
    "nexus_position_sizer_duration_seconds",
    "Duration of position size calculations",
    ["strategy"],
)
POSITION_SIZE_GAUGE = Gauge(
    "nexus_position_size",
    "Current position size",
    ["symbol", "strategy"],
)


class SizingStrategy(Enum):
    """Position sizing strategies."""

    FIXED = "fixed"                          # Fixed number of units
    PERCENTAGE = "percentage"                # Fixed percentage of equity
    RISK_BASED = "risk_based"                # Risk-based sizing
    VOLATILITY_BASED = "volatility_based"    # Volatility-adjusted sizing
    KELLY = "kelly"                          # Kelly criterion
    OPTIMAL_F = "optimal_f"                  # Optimal f
    MARTINGALE = "martingale"                # Martingale (progressive)
    ANTI_MARTINGALE = "anti_martingale"      # Anti-martingale
    PYRAMIDING = "pyramiding"                # Pyramiding
    SCALING = "scaling"                      # Scaling in/out
    ADAPTIVE = "adaptive"                    # Adaptive sizing


@dataclass
class PositionSizingConfig:
    """Configuration for position sizing."""

    strategy: SizingStrategy
    # Fixed strategy
    fixed_units: float = 1.0

    # Percentage strategy
    percentage_of_equity: float = 0.02  # 2%

    # Risk-based strategy
    risk_per_trade: float = 0.01  # 1%
    stop_loss_pips: float = 50.0
    stop_loss_percent: float = 0.02  # 2%

    # Volatility-based strategy
    atr_multiplier: float = 1.0
    atr_period: int = 14
    volatility_risk_factor: float = 1.0

    # Kelly strategy
    win_rate: float = 0.55
    win_loss_ratio: float = 1.5
    kelly_fraction: float = 0.25  # Fraction of full Kelly

    # Optimal f strategy
    optimal_f_period: int = 100

    # Martingale/Anti-martingale
    martingale_multiplier: float = 2.0
    max_martingale_levels: int = 5

    # Pyramiding
    max_pyramid_levels: int = 3
    pyramid_multiplier: float = 0.5

    # Scaling
    scale_in_levels: int = 3
    scale_out_levels: int = 3
    scale_in_percentages: List[float] = field(default_factory=lambda: [0.33, 0.33, 0.34])
    scale_out_percentages: List[float] = field(default_factory=lambda: [0.33, 0.33, 0.34])

    # Adaptive strategy
    adaptive_lookback: int = 50
    adaptive_performance_weight: float = 0.7

    # Common parameters
    max_position_size: float = 100.0
    min_position_size: float = 0.01
    max_risk_per_trade: float = 0.02
    min_risk_per_trade: float = 0.001
    account_equity: float = 100000.0
    symbol: str = ""
    currency: str = "USD"

    # Advanced parameters
    use_fractional_sizing: bool = True
    use_correlation_adjustment: bool = False
    correlation_threshold: float = 0.7
    max_total_risk: float = 0.05  # 5% total portfolio risk
    max_leverage: float = 10.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "strategy": self.strategy.value,
            "fixed_units": self.fixed_units,
            "percentage_of_equity": self.percentage_of_equity,
            "risk_per_trade": self.risk_per_trade,
            "stop_loss_pips": self.stop_loss_pips,
            "stop_loss_percent": self.stop_loss_percent,
            "atr_multiplier": self.atr_multiplier,
            "atr_period": self.atr_period,
            "volatility_risk_factor": self.volatility_risk_factor,
            "win_rate": self.win_rate,
            "win_loss_ratio": self.win_loss_ratio,
            "kelly_fraction": self.kelly_fraction,
            "optimal_f_period": self.optimal_f_period,
            "martingale_multiplier": self.martingale_multiplier,
            "max_martingale_levels": self.max_martingale_levels,
            "max_pyramid_levels": self.max_pyramid_levels,
            "pyramid_multiplier": self.pyramid_multiplier,
            "scale_in_levels": self.scale_in_levels,
            "scale_out_levels": self.scale_out_levels,
            "scale_in_percentages": self.scale_in_percentages,
            "scale_out_percentages": self.scale_out_percentages,
            "adaptive_lookback": self.adaptive_lookback,
            "adaptive_performance_weight": self.adaptive_performance_weight,
            "max_position_size": self.max_position_size,
            "min_position_size": self.min_position_size,
            "max_risk_per_trade": self.max_risk_per_trade,
            "min_risk_per_trade": self.min_risk_per_trade,
            "account_equity": self.account_equity,
            "symbol": self.symbol,
            "currency": self.currency,
            "use_fractional_sizing": self.use_fractional_sizing,
            "use_correlation_adjustment": self.use_correlation_adjustment,
            "correlation_threshold": self.correlation_threshold,
            "max_total_risk": self.max_total_risk,
            "max_leverage": self.max_leverage,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PositionSizingConfig":
        """Create from dictionary."""
        return cls(
            strategy=SizingStrategy(data.get("strategy", "risk_based")),
            fixed_units=data.get("fixed_units", 1.0),
            percentage_of_equity=data.get("percentage_of_equity", 0.02),
            risk_per_trade=data.get("risk_per_trade", 0.01),
            stop_loss_pips=data.get("stop_loss_pips", 50.0),
            stop_loss_percent=data.get("stop_loss_percent", 0.02),
            atr_multiplier=data.get("atr_multiplier", 1.0),
            atr_period=data.get("atr_period", 14),
            volatility_risk_factor=data.get("volatility_risk_factor", 1.0),
            win_rate=data.get("win_rate", 0.55),
            win_loss_ratio=data.get("win_loss_ratio", 1.5),
            kelly_fraction=data.get("kelly_fraction", 0.25),
            optimal_f_period=data.get("optimal_f_period", 100),
            martingale_multiplier=data.get("martingale_multiplier", 2.0),
            max_martingale_levels=data.get("max_martingale_levels", 5),
            max_pyramid_levels=data.get("max_pyramid_levels", 3),
            pyramid_multiplier=data.get("pyramid_multiplier", 0.5),
            scale_in_levels=data.get("scale_in_levels", 3),
            scale_out_levels=data.get("scale_out_levels", 3),
            scale_in_percentages=data.get("scale_in_percentages", [0.33, 0.33, 0.34]),
            scale_out_percentages=data.get("scale_out_percentages", [0.33, 0.33, 0.34]),
            adaptive_lookback=data.get("adaptive_lookback", 50),
            adaptive_performance_weight=data.get("adaptive_performance_weight", 0.7),
            max_position_size=data.get("max_position_size", 100.0),
            min_position_size=data.get("min_position_size", 0.01),
            max_risk_per_trade=data.get("max_risk_per_trade", 0.02),
            min_risk_per_trade=data.get("min_risk_per_trade", 0.001),
            account_equity=data.get("account_equity", 100000.0),
            symbol=data.get("symbol", ""),
            currency=data.get("currency", "USD"),
            use_fractional_sizing=data.get("use_fractional_sizing", True),
            use_correlation_adjustment=data.get("use_correlation_adjustment", False),
            correlation_threshold=data.get("correlation_threshold", 0.7),
            max_total_risk=data.get("max_total_risk", 0.05),
            max_leverage=data.get("max_leverage", 10.0),
        )


@dataclass
class PositionSizeResult:
    """Position sizing result."""

    size: float
    risk_amount: float
    risk_percent: float
    strategy: SizingStrategy
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "size": self.size,
            "risk_amount": self.risk_amount,
            "risk_percent": self.risk_percent,
            "strategy": self.strategy.value,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "warnings": self.warnings,
        }


@dataclass
class Position:
    """Position information."""

    symbol: str
    size: float
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    pnl: float = 0.0
    risk_amount: float = 0.0
    risk_percent: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "size": self.size,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "pnl": self.pnl,
            "risk_amount": self.risk_amount,
            "risk_percent": self.risk_percent,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


class PositionSizer:
    """
    Advanced position sizing system with multiple strategies.
    """

    def __init__(
        self,
        config: Optional[Union[PositionSizingConfig, Dict[str, Any]]] = None,
        market_data_service: Optional[Any] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the position sizer.

        Args:
            config: Position sizing configuration
            market_data_service: Market data service instance
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
        """
        if isinstance(config, dict):
            self.config = PositionSizingConfig.from_dict(config)
        elif isinstance(config, PositionSizingConfig):
            self.config = config
        else:
            self.config = PositionSizingConfig()

        self.market_data_service = market_data_service
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._lock = asyncio.Lock()
        self._positions: Dict[str, Position] = {}
        self._trade_history: List[Dict[str, Any]] = []
        self._performance_history: List[float] = []

        logger.info(f"PositionSizer initialized with strategy: {self.config.strategy.value}")

    async def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        take_profit: Optional[float] = None,
        account_equity: Optional[float] = None,
        strategy: Optional[Union[SizingStrategy, str]] = None,
        **kwargs,
    ) -> PositionSizeResult:
        """
        Calculate optimal position size.

        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            account_equity: Account equity
            strategy: Sizing strategy to use
            **kwargs: Additional parameters

        Returns:
            Position size result
        """
        start_time = time.time()

        # Parse strategy
        if strategy:
            if isinstance(strategy, str):
                strategy = SizingStrategy(strategy)
        else:
            strategy = self.config.strategy

        # Use account equity from config if not provided
        if account_equity is None:
            account_equity = self.config.account_equity

        # Update config with current values
        self.config.symbol = symbol
        self.config.account_equity = account_equity

        try:
            # Calculate position size based on strategy
            if strategy == SizingStrategy.FIXED:
                result = await self._calculate_fixed(symbol, entry_price, stop_loss, account_equity, **kwargs)
            elif strategy == SizingStrategy.PERCENTAGE:
                result = await self._calculate_percentage(symbol, entry_price, stop_loss, account_equity, **kwargs)
            elif strategy == SizingStrategy.RISK_BASED:
                result = await self._calculate_risk_based(symbol, entry_price, stop_loss, account_equity, **kwargs)
            elif strategy == SizingStrategy.VOLATILITY_BASED:
                result = await self._calculate_volatility_based(symbol, entry_price, stop_loss, account_equity, **kwargs)
            elif strategy == SizingStrategy.KELLY:
                result = await self._calculate_kelly(symbol, entry_price, stop_loss, account_equity, **kwargs)
            elif strategy == SizingStrategy.OPTIMAL_F:
                result = await self._calculate_optimal_f(symbol, entry_price, stop_loss, account_equity, **kwargs)
            elif strategy == SizingStrategy.MARTINGALE:
                result = await self._calculate_martingale(symbol, entry_price, stop_loss, account_equity, **kwargs)
            elif strategy == SizingStrategy.ANTI_MARTINGALE:
                result = await self._calculate_anti_martingale(symbol, entry_price, stop_loss, account_equity, **kwargs)
            elif strategy == SizingStrategy.PYRAMIDING:
                result = await self._calculate_pyramiding(symbol, entry_price, stop_loss, account_equity, **kwargs)
            elif strategy == SizingStrategy.SCALING:
                result = await self._calculate_scaling(symbol, entry_price, stop_loss, account_equity, **kwargs)
            elif strategy == SizingStrategy.ADAPTIVE:
                result = await self._calculate_adaptive(symbol, entry_price, stop_loss, account_equity, **kwargs)
            else:
                raise ValueError(f"Unsupported strategy: {strategy}")

            # Apply risk limits
            result = await self._apply_risk_limits(result, account_equity)

            # Record metrics
            POSITION_SIZER_COUNTER.labels(
                strategy=strategy.value,
                status="success",
            ).inc()
            POSITION_SIZER_DURATION.labels(
                strategy=strategy.value,
            ).observe(time.time() - start_time)
            POSITION_SIZE_GAUGE.labels(
                symbol=symbol,
                strategy=strategy.value,
            ).set(result.size)

            logger.info(
                f"Position size calculated for {symbol}: {result.size:.4f} "
                f"(risk: {result.risk_percent:.2%}, strategy: {strategy.value})"
            )

            return result

        except Exception as e:
            POSITION_SIZER_COUNTER.labels(
                strategy=strategy.value,
                status="error",
            ).inc()
            logger.error(f"Error calculating position size: {e}")
            raise

    async def _calculate_fixed(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        **kwargs,
    ) -> PositionSizeResult:
        """Calculate fixed position size."""
        size = self.config.fixed_units

        risk_amount = abs(entry_price - stop_loss) * size
        risk_percent = risk_amount / account_equity

        return PositionSizeResult(
            size=size,
            risk_amount=risk_amount,
            risk_percent=risk_percent,
            strategy=SizingStrategy.FIXED,
            confidence=1.0,
            metadata={"fixed_units": self.config.fixed_units},
        )

    async def _calculate_percentage(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        **kwargs,
    ) -> PositionSizeResult:
        """Calculate percentage-based position size."""
        percentage = kwargs.get("percentage", self.config.percentage_of_equity)
        risk_amount = account_equity * percentage

        price_diff = abs(entry_price - stop_loss)
        if price_diff == 0:
            size = 0
        else:
            size = risk_amount / price_diff

        return PositionSizeResult(
            size=size,
            risk_amount=risk_amount,
            risk_percent=percentage,
            strategy=SizingStrategy.PERCENTAGE,
            confidence=0.9,
            metadata={"percentage": percentage},
        )

    async def _calculate_risk_based(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        **kwargs,
    ) -> PositionSizeResult:
        """Calculate risk-based position size."""
        risk_per_trade = kwargs.get("risk_per_trade", self.config.risk_per_trade)
        risk_amount = account_equity * risk_per_trade

        price_diff = abs(entry_price - stop_loss)
        if price_diff == 0:
            size = 0
        else:
            size = risk_amount / price_diff

        # Adjust for stop loss percentage
        stop_loss_percent = kwargs.get("stop_loss_percent", self.config.stop_loss_percent)
        if stop_loss_percent > 0:
            max_risk = account_equity * stop_loss_percent
            if risk_amount > max_risk:
                risk_amount = max_risk
                size = risk_amount / price_diff

        return PositionSizeResult(
            size=size,
            risk_amount=risk_amount,
            risk_percent=risk_per_trade,
            strategy=SizingStrategy.RISK_BASED,
            confidence=0.85,
            metadata={
                "risk_per_trade": risk_per_trade,
                "stop_loss_percent": stop_loss_percent,
            },
        )

    async def _calculate_volatility_based(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        **kwargs,
    ) -> PositionSizeResult:
        """Calculate volatility-based position size."""
        atr_period = kwargs.get("atr_period", self.config.atr_period)
        atr_multiplier = kwargs.get("atr_multiplier", self.config.atr_multiplier)

        # Get ATR from market data
        atr = await self._get_atr(symbol, atr_period)

        if atr is None or atr == 0:
            # Fallback to stop loss-based sizing
            return await self._calculate_risk_based(
                symbol, entry_price, stop_loss, account_equity, **kwargs
            )

        # Calculate volatility-adjusted risk
        volatility_risk = atr * atr_multiplier
        risk_amount = account_equity * self.config.risk_per_trade

        # Adjust position size based on volatility
        if volatility_risk > 0:
            size = risk_amount / volatility_risk
        else:
            size = 0

        return PositionSizeResult(
            size=size,
            risk_amount=risk_amount,
            risk_percent=self.config.risk_per_trade,
            strategy=SizingStrategy.VOLATILITY_BASED,
            confidence=0.8,
            metadata={
                "atr": atr,
                "atr_period": atr_period,
                "atr_multiplier": atr_multiplier,
            },
        )

    async def _calculate_kelly(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        **kwargs,
    ) -> PositionSizeResult:
        """Calculate Kelly criterion position size."""
        win_rate = kwargs.get("win_rate", self.config.win_rate)
        win_loss_ratio = kwargs.get("win_loss_ratio", self.config.win_loss_ratio)
        kelly_fraction = kwargs.get("kelly_fraction", self.config.kelly_fraction)

        # Calculate Kelly percentage
        if win_loss_ratio > 0:
            kelly_percent = win_rate - ((1 - win_rate) / win_loss_ratio)
            kelly_percent = max(0, kelly_percent)
            kelly_percent = kelly_percent * kelly_fraction
        else:
            kelly_percent = 0

        # Calculate position size based on Kelly
        risk_amount = account_equity * kelly_percent
        price_diff = abs(entry_price - stop_loss)

        if price_diff == 0:
            size = 0
        else:
            size = risk_amount / price_diff

        return PositionSizeResult(
            size=size,
            risk_amount=risk_amount,
            risk_percent=kelly_percent,
            strategy=SizingStrategy.KELLY,
            confidence=0.7,
            metadata={
                "kelly_percent": kelly_percent,
                "win_rate": win_rate,
                "win_loss_ratio": win_loss_ratio,
                "kelly_fraction": kelly_fraction,
            },
        )

    async def _calculate_optimal_f(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        **kwargs,
    ) -> PositionSizeResult:
        """Calculate optimal f position size."""
        period = kwargs.get("optimal_f_period", self.config.optimal_f_period)

        # Get trade history
        trades = self._trade_history[-period:]
        if len(trades) < 10:
            return await self._calculate_risk_based(
                symbol, entry_price, stop_loss, account_equity, **kwargs
            )

        # Calculate optimal f
        profits = [t.get("profit", 0) for t in trades]
        worst_loss = min(profits) if profits else -1

        if worst_loss >= 0:
            # No losses, use risk-based sizing
            return await self._calculate_risk_based(
                symbol, entry_price, stop_loss, account_equity, **kwargs
            )

        optimal_f = self._calculate_optimal_f_value(profits, worst_loss)
        risk_amount = account_equity * optimal_f
        price_diff = abs(entry_price - stop_loss)

        if price_diff == 0:
            size = 0
        else:
            size = risk_amount / price_diff

        return PositionSizeResult(
            size=size,
            risk_amount=risk_amount,
            risk_percent=optimal_f,
            strategy=SizingStrategy.OPTIMAL_F,
            confidence=0.6,
            metadata={
                "optimal_f": optimal_f,
                "period": period,
                "trades_used": len(profits),
            },
        )

    def _calculate_optimal_f_value(self, profits: List[float], worst_loss: float) -> float:
        """Calculate optimal f value."""
        # Simplified optimal f calculation
        # Full calculation would use the original optimal f formula
        # This is a simplified version

        total_profit = sum(profits)
        if total_profit <= 0:
            return 0.01  # Minimum risk

        avg_profit = total_profit / len(profits)
        f = abs(avg_profit / worst_loss)

        # Bound f between 0.01 and 0.25
        return min(max(f, 0.01), 0.25)

    async def _calculate_martingale(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        **kwargs,
    ) -> PositionSizeResult:
        """Calculate martingale position size."""
        base_size = kwargs.get("base_size", 0.01)
        multiplier = kwargs.get("martingale_multiplier", self.config.martingale_multiplier)
        max_levels = kwargs.get("max_martingale_levels", self.config.max_martingale_levels)

        # Check consecutive losses
        consecutive_losses = 0
        for trade in reversed(self._trade_history):
            if trade.get("profit", 0) < 0:
                consecutive_losses += 1
            else:
                break

        # Calculate size
        level = min(consecutive_losses, max_levels - 1)
        size = base_size * (multiplier ** level)

        # Check if we're in a drawdown
        if self._performance_history:
            recent_performance = self._performance_history[-10:]
            if recent_performance and np.mean(recent_performance) < 0:
                # Reduce size in drawdown
                size = size * 0.5

        risk_amount = abs(entry_price - stop_loss) * size
        risk_percent = risk_amount / account_equity

        return PositionSizeResult(
            size=size,
            risk_amount=risk_amount,
            risk_percent=risk_percent,
            strategy=SizingStrategy.MARTINGALE,
            confidence=0.5,
            metadata={
                "base_size": base_size,
                "multiplier": multiplier,
                "level": level,
                "consecutive_losses": consecutive_losses,
            },
        )

    async def _calculate_anti_martingale(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        **kwargs,
    ) -> PositionSizeResult:
        """Calculate anti-martingale position size."""
        base_size = kwargs.get("base_size", 0.01)
        multiplier = kwargs.get("martingale_multiplier", self.config.martingale_multiplier)
        max_levels = kwargs.get("max_martingale_levels", self.config.max_martingale_levels)

        # Check consecutive wins
        consecutive_wins = 0
        for trade in reversed(self._trade_history):
            if trade.get("profit", 0) > 0:
                consecutive_wins += 1
            else:
                break

        # Calculate size
        level = min(consecutive_wins, max_levels - 1)
        size = base_size * (multiplier ** level)

        # Cap size based on equity
        max_size = account_equity * 0.1  # Max 10% of equity
        size = min(size, max_size)

        risk_amount = abs(entry_price - stop_loss) * size
        risk_percent = risk_amount / account_equity

        return PositionSizeResult(
            size=size,
            risk_amount=risk_amount,
            risk_percent=risk_percent,
            strategy=SizingStrategy.ANTI_MARTINGALE,
            confidence=0.5,
            metadata={
                "base_size": base_size,
                "multiplier": multiplier,
                "level": level,
                "consecutive_wins": consecutive_wins,
            },
        )

    async def _calculate_pyramiding(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        **kwargs,
    ) -> PositionSizeResult:
        """Calculate pyramiding position size."""
        max_levels = kwargs.get("max_pyramid_levels", self.config.max_pyramid_levels)
        pyramid_multiplier = kwargs.get("pyramid_multiplier", self.config.pyramid_multiplier)

        # Check existing positions
        existing_positions = self._positions.get(symbol)
        if existing_positions:
            current_size = existing_positions.size
            if current_size > 0:
                # Calculate next pyramid level
                current_price = existing_positions.current_price
                if current_price > entry_price:
                    # Profit - add position
                    level = min(
                        int(current_size / (current_size * pyramid_multiplier + 1)),
                        max_levels - 1
                    )
                    if level > 0:
                        size = current_size * pyramid_multiplier
                    else:
                        size = 0
                else:
                    size = 0
            else:
                size = 0.01
        else:
            size = 0.01

        risk_amount = abs(entry_price - stop_loss) * size
        risk_percent = risk_amount / account_equity

        return PositionSizeResult(
            size=size,
            risk_amount=risk_amount,
            risk_percent=risk_percent,
            strategy=SizingStrategy.PYRAMIDING,
            confidence=0.6,
            metadata={
                "max_levels": max_levels,
                "pyramid_multiplier": pyramid_multiplier,
            },
        )

    async def _calculate_scaling(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        **kwargs,
    ) -> PositionSizeResult:
        """Calculate scaling position size."""
        scale_in_levels = kwargs.get("scale_in_levels", self.config.scale_in_levels)
        scale_in_percentages = kwargs.get("scale_in_percentages", self.config.scale_in_percentages)

        # Calculate total size using risk-based method
        base_result = await self._calculate_risk_based(
            symbol, entry_price, stop_loss, account_equity, **kwargs
        )

        total_size = base_result.size
        scale_in_size = total_size * (1 / scale_in_levels)

        return PositionSizeResult(
            size=scale_in_size,
            risk_amount=base_result.risk_amount / scale_in_levels,
            risk_percent=base_result.risk_percent / scale_in_levels,
            strategy=SizingStrategy.SCALING,
            confidence=0.7,
            metadata={
                "scale_in_levels": scale_in_levels,
                "scale_in_percentages": scale_in_percentages,
                "total_size": total_size,
            },
        )

    async def _calculate_adaptive(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        **kwargs,
    ) -> PositionSizeResult:
        """Calculate adaptive position size."""
        lookback = kwargs.get("adaptive_lookback", self.config.adaptive_lookback)
        performance_weight = kwargs.get("adaptive_performance_weight", self.config.adaptive_performance_weight)

        # Get recent performance
        recent_performance = self._performance_history[-lookback:] if self._performance_history else []

        if len(recent_performance) < 10:
            # Not enough data, use risk-based
            return await self._calculate_risk_based(
                symbol, entry_price, stop_loss, account_equity, **kwargs
            )

        # Calculate performance factor
        avg_performance = np.mean(recent_performance)
        if avg_performance > 0:
            performance_factor = 1 + (avg_performance * 2)  # Increase size in good performance
            performance_factor = min(performance_factor, 2.0)  # Cap at 2x
        else:
            performance_factor = 1 + avg_performance  # Decrease size in bad performance
            performance_factor = max(performance_factor, 0.25)  # Floor at 0.25x

        # Calculate volatility factor
        volatility = np.std(recent_performance)
        volatility_factor = 1 / (1 + volatility * 10)

        # Calculate adaptive factor
        adaptive_factor = (performance_weight * performance_factor +
                          (1 - performance_weight) * volatility_factor)

        # Apply to base risk
        base_result = await self._calculate_risk_based(
            symbol, entry_price, stop_loss, account_equity, **kwargs
        )

        size = base_result.size * adaptive_factor

        # Apply limits
        size = min(size, self.config.max_position_size)
        size = max(size, self.config.min_position_size)

        risk_amount = abs(entry_price - stop_loss) * size
        risk_percent = risk_amount / account_equity

        return PositionSizeResult(
            size=size,
            risk_amount=risk_amount,
            risk_percent=risk_percent,
            strategy=SizingStrategy.ADAPTIVE,
            confidence=0.6,
            metadata={
                "adaptive_factor": adaptive_factor,
                "performance_factor": performance_factor,
                "volatility_factor": volatility_factor,
                "lookback": lookback,
            },
        )

    async def _apply_risk_limits(
        self,
        result: PositionSizeResult,
        account_equity: float,
    ) -> PositionSizeResult:
        """
        Apply risk limits to position size.

        Args:
            result: Position size result
            account_equity: Account equity

        Returns:
            Adjusted position size result
        """
        warnings = []

        # Apply position limits
        if result.size > self.config.max_position_size:
            result.size = self.config.max_position_size
            warnings.append(f"Position size capped at {self.config.max_position_size}")

        if result.size < self.config.min_position_size:
            result.size = self.config.min_position_size
            warnings.append(f"Position size floored at {self.config.min_position_size}")

        # Apply risk limits
        if result.risk_percent > self.config.max_risk_per_trade:
            result.risk_percent = self.config.max_risk_per_trade
            result.risk_amount = account_equity * result.risk_percent
            warnings.append(f"Risk capped at {self.config.max_risk_per_trade:.2%}")

        if result.risk_percent < self.config.min_risk_per_trade:
            result.risk_percent = self.config.min_risk_per_trade
            result.risk_amount = account_equity * result.risk_percent
            warnings.append(f"Risk floored at {self.config.min_risk_per_trade:.2%}")

        # Apply leverage limit
        leverage = result.size / account_equity if account_equity > 0 else 0
        if leverage > self.config.max_leverage:
            result.size = account_equity * self.config.max_leverage
            result.risk_amount = abs(0)  # Recalculate risk
            warnings.append(f"Leverage capped at {self.config.max_leverage:.1f}x")

        # Add warnings to result
        if warnings:
            result.warnings.extend(warnings)

        return result

    async def _get_atr(self, symbol: str, period: int) -> Optional[float]:
        """
        Get ATR for symbol.

        Args:
            symbol: Trading symbol
            period: ATR period

        Returns:
            ATR value or None
        """
        if self.market_data_service is None:
            return None

        try:
            # Get OHLC data
            ohlc_data = await self.market_data_service.get_ohlc(
                symbol=symbol,
                timeframe="1h",
                limit=period + 1,
            )

            if not ohlc_data or len(ohlc_data) < period + 1:
                return None

            # Calculate ATR
            highs = [d["high"] for d in ohlc_data]
            lows = [d["low"] for d in ohlc_data]
            closes = [d["close"] for d in ohlc_data]

            tr = []
            for i in range(1, len(ohlc_data)):
                high_low = highs[i] - lows[i]
                high_close = abs(highs[i] - closes[i - 1])
                low_close = abs(lows[i] - closes[i - 1])
                tr.append(max(high_low, high_close, low_close))

            atr = np.mean(tr[-period:]) if tr else 0
            return atr

        except Exception as e:
            logger.error(f"Error getting ATR for {symbol}: {e}")
            return None

    async def update_position(
        self,
        symbol: str,
        current_price: float,
        size: Optional[float] = None,
    ):
        """
        Update position information.

        Args:
            symbol: Trading symbol
            current_price: Current price
            size: Current position size
        """
        async with self._lock:
            position = self._positions.get(symbol)

            if position:
                position.current_price = current_price
                position.pnl = (current_price - position.entry_price) * position.size
                position.updated_at = datetime.utcnow()

                if size is not None:
                    position.size = size

            else:
                self._positions[symbol] = Position(
                    symbol=symbol,
                    size=size or 0,
                    entry_price=current_price,
                    current_price=current_price,
                    stop_loss=0,
                    take_profit=0,
                )

        logger.debug(f"Updated position for {symbol}: {size} @ {current_price}")

    async def record_trade(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        size: float,
        profit: float,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Record a completed trade.

        Args:
            symbol: Trading symbol
            entry_price: Entry price
            exit_price: Exit price
            size: Position size
            profit: Trade profit
            metadata: Additional metadata
        """
        trade_data = {
            "symbol": symbol,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "size": size,
            "profit": profit,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }

        async with self._lock:
            self._trade_history.append(trade_data)

            # Update performance history
            self._performance_history.append(profit / (entry_price * size) if size > 0 else 0)

            # Remove position if closed
            if symbol in self._positions:
                del self._positions[symbol]

            # Limit history
            if len(self._trade_history) > 1000:
                self._trade_history = self._trade_history[-1000:]
            if len(self._performance_history) > 1000:
                self._performance_history = self._performance_history[-1000:]

        logger.info(f"Recorded trade for {symbol}: {profit:.2f} (size: {size})")

    async def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position information.

        Args:
            symbol: Trading symbol

        Returns:
            Position or None
        """
        async with self._lock:
            return self._positions.get(symbol)

    async def get_all_positions(self) -> Dict[str, Position]:
        """
        Get all positions.

        Returns:
            Dictionary of positions
        """
        async with self._lock:
            return self._positions.copy()

    async def get_trade_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get trade history.

        Args:
            symbol: Filter by symbol
            limit: Maximum number of trades

        Returns:
            List of trades
        """
        async with self._lock:
            trades = self._trade_history

            if symbol:
                trades = [t for t in trades if t["symbol"] == symbol]

            return trades[-limit:]

    async def get_performance_statistics(
        self,
        symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get performance statistics.

        Args:
            symbol: Filter by symbol

        Returns:
            Performance statistics
        """
        trades = await self.get_trade_history(symbol)

        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "avg_profit": 0,
                "total_profit": 0,
                "max_profit": 0,
                "max_loss": 0,
                "profit_factor": 0,
            }

        profits = [t["profit"] for t in trades]
        winning_trades = [p for p in profits if p > 0]
        losing_trades = [p for p in profits if p < 0]

        total_profit = sum(profits)
        total_wins = sum(winning_trades) if winning_trades else 0
        total_losses = abs(sum(losing_trades)) if losing_trades else 1

        return {
            "total_trades": len(trades),
            "win_rate": len(winning_trades) / len(trades) if trades else 0,
            "avg_profit": np.mean(profits) if profits else 0,
            "total_profit": total_profit,
            "max_profit": max(profits) if profits else 0,
            "max_loss": min(profits) if profits else 0,
            "profit_factor": total_wins / total_losses if total_losses > 0 else 0,
        }

    async def update_config(self, config: Union[PositionSizingConfig, Dict[str, Any]]):
        """
        Update position sizing configuration.

        Args:
            config: New configuration
        """
        if isinstance(config, dict):
            self.config = PositionSizingConfig.from_dict(config)
        else:
            self.config = config

        logger.info(f"PositionSizer configuration updated: {self.config.strategy.value}")

    async def shutdown(self):
        """Shutdown the position sizer."""
        logger.info("PositionSizer shut down")


# Export singleton
position_sizer = PositionSizer()
