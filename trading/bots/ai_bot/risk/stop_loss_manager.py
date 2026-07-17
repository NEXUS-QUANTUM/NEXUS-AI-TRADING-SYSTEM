"""
NEXUS AI TRADING SYSTEM - Stop Loss Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced stop loss management system for protecting positions,
implementing dynamic stop losses, trailing stops, and automated
risk management.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
from prometheus_client import Counter, Gauge, Histogram

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
STOP_LOSS_COUNTER = Counter(
    "nexus_stop_loss_triggers_total",
    "Total number of stop loss triggers",
    ["stop_type", "symbol", "status"],
)
STOP_LOSS_ACTIVE = Gauge(
    "nexus_stop_loss_active",
    "Number of active stop losses",
    ["symbol"],
)
STOP_LOSS_DURATION = Histogram(
    "nexus_stop_loss_duration_seconds",
    "Duration of stop loss monitoring",
    ["stop_type"],
)


class StopLossType(Enum):
    """Types of stop losses."""

    FIXED = "fixed"                      # Fixed price stop loss
    PERCENTAGE = "percentage"            # Percentage-based stop loss
    TRAILING = "trailing"                # Trailing stop loss
    VOLATILITY_BASED = "volatility_based"  # Volatility-adjusted stop loss
    ATR_BASED = "atr_based"              # ATR-based stop loss
    TIME_BASED = "time_based"            # Time-based stop loss
    BREAK_EVEN = "break_even"            # Move to break-even
    DYNAMIC = "dynamic"                  # Dynamic stop loss
    MULTI_LEVEL = "multi_level"          # Multiple stop loss levels


class StopLossStatus(Enum):
    """Status of a stop loss."""

    ACTIVE = "active"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    BREACHED = "breached"


@dataclass
class StopLossConfig:
    """Configuration for stop loss."""

    stop_type: StopLossType
    # Fixed/Percentage parameters
    stop_value: Optional[float] = None
    stop_percent: Optional[float] = None

    # Trailing parameters
    trailing_percent: Optional[float] = None
    trailing_pips: Optional[float] = None
    activation_threshold: Optional[float] = None

    # Volatility parameters
    volatility_multiplier: float = 1.5
    lookback_period: int = 20

    # ATR parameters
    atr_multiplier: float = 2.0
    atr_period: int = 14

    # Time parameters
    time_limit_hours: float = 24.0

    # Multi-level parameters
    levels: List[Dict[str, Any]] = field(default_factory=list)

    # Common parameters
    symbol: str = ""
    entry_price: float = 0.0
    stop_price: float = 0.0
    current_price: float = 0.0
    quantity: float = 0.0
    position_side: str = "long"  # "long" or "short"
    risk_amount: float = 0.0
    max_risk_percent: float = 0.02

    # Advanced parameters
    use_partial_close: bool = False
    partial_close_percent: float = 0.5
    use_breakeven_after: Optional[float] = None
    breakeven_trigger_percent: float = 0.01
    expire_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stop_type": self.stop_type.value,
            "stop_value": self.stop_value,
            "stop_percent": self.stop_percent,
            "trailing_percent": self.trailing_percent,
            "trailing_pips": self.trailing_pips,
            "activation_threshold": self.activation_threshold,
            "volatility_multiplier": self.volatility_multiplier,
            "lookback_period": self.lookback_period,
            "atr_multiplier": self.atr_multiplier,
            "atr_period": self.atr_period,
            "time_limit_hours": self.time_limit_hours,
            "levels": self.levels,
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "current_price": self.current_price,
            "quantity": self.quantity,
            "position_side": self.position_side,
            "risk_amount": self.risk_amount,
            "max_risk_percent": self.max_risk_percent,
            "use_partial_close": self.use_partial_close,
            "partial_close_percent": self.partial_close_percent,
            "use_breakeven_after": self.use_breakeven_after,
            "breakeven_trigger_percent": self.breakeven_trigger_percent,
            "expire_at": self.expire_at.isoformat() if self.expire_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StopLossConfig":
        """Create from dictionary."""
        return cls(
            stop_type=StopLossType(data["stop_type"]),
            stop_value=data.get("stop_value"),
            stop_percent=data.get("stop_percent"),
            trailing_percent=data.get("trailing_percent"),
            trailing_pips=data.get("trailing_pips"),
            activation_threshold=data.get("activation_threshold"),
            volatility_multiplier=data.get("volatility_multiplier", 1.5),
            lookback_period=data.get("lookback_period", 20),
            atr_multiplier=data.get("atr_multiplier", 2.0),
            atr_period=data.get("atr_period", 14),
            time_limit_hours=data.get("time_limit_hours", 24.0),
            levels=data.get("levels", []),
            symbol=data.get("symbol", ""),
            entry_price=data.get("entry_price", 0.0),
            stop_price=data.get("stop_price", 0.0),
            current_price=data.get("current_price", 0.0),
            quantity=data.get("quantity", 0.0),
            position_side=data.get("position_side", "long"),
            risk_amount=data.get("risk_amount", 0.0),
            max_risk_percent=data.get("max_risk_percent", 0.02),
            use_partial_close=data.get("use_partial_close", False),
            partial_close_percent=data.get("partial_close_percent", 0.5),
            use_breakeven_after=data.get("use_breakeven_after"),
            breakeven_trigger_percent=data.get("breakeven_trigger_percent", 0.01),
            expire_at=datetime.fromisoformat(data["expire_at"]) if data.get("expire_at") else None,
        )


@dataclass
class StopLoss:
    """Stop loss instance."""

    id: str
    config: StopLossConfig
    status: StopLossStatus = StopLossStatus.ACTIVE
    triggered_at: Optional[datetime] = None
    triggered_price: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    stop_history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "config": self.config.to_dict(),
            "status": self.status.value,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "triggered_price": self.triggered_price,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "stop_history": self.stop_history,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StopLoss":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            config=StopLossConfig.from_dict(data["config"]),
            status=StopLossStatus(data["status"]),
            triggered_at=datetime.fromisoformat(data["triggered_at"]) if data.get("triggered_at") else None,
            triggered_price=data.get("triggered_price", 0.0),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            stop_history=data.get("stop_history", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class StopLossEvent:
    """Stop loss event."""

    stop_id: str
    symbol: str
    event_type: str
    old_stop: float
    new_stop: float
    timestamp: datetime
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class StopLossManager:
    """
    Advanced stop loss management system.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        market_data_service: Optional[Any] = None,
    ):
        """
        Initialize the stop loss manager.

        Args:
            config: Configuration dictionary
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
            market_data_service: Market data service instance
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.market_data_service = market_data_service
        self._lock = asyncio.Lock()
        self._stop_losses: Dict[str, StopLoss] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._event_handlers: List[Callable] = []

        # Load configuration
        self.sl_config = self.config.get("stop_loss_manager", {})
        self.monitor_interval = self.sl_config.get("monitor_interval", 1)  # seconds
        self.max_stop_losses = self.sl_config.get("max_stop_losses", 1000)
        self.auto_cleanup_age = self.sl_config.get("auto_cleanup_age", 3600 * 24)  # 24 hours
        self.default_stop_type = StopLossType(
            self.sl_config.get("default_stop_type", "trailing")
        )

        # Start monitoring
        self._start_monitoring()

        logger.info("StopLossManager initialized")

    def _start_monitoring(self):
        """Start the monitoring task."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        """Background loop for monitoring stop losses."""
        while True:
            try:
                await self._update_stop_losses()
                await self._check_trigger_conditions()
                await self._cleanup_old_stop_losses()
                await asyncio.sleep(self.monitor_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)

    async def create_stop_loss(
        self,
        config: Union[StopLossConfig, Dict[str, Any]],
        stop_id: Optional[str] = None,
    ) -> StopLoss:
        """
        Create a new stop loss.

        Args:
            config: Stop loss configuration
            stop_id: Optional stop loss ID

        Returns:
            Created stop loss
        """
        if isinstance(config, dict):
            config = StopLossConfig.from_dict(config)

        # Generate ID
        if stop_id is None:
            stop_id = f"sl_{config.symbol}_{int(time.time())}"

        # Calculate initial stop price
        stop_price = await self._calculate_stop_price(config)

        # Create stop loss
        stop_loss = StopLoss(
            id=stop_id,
            config=config,
            status=StopLossStatus.ACTIVE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            stop_history=[{
                "timestamp": datetime.utcnow().isoformat(),
                "price": stop_price,
                "type": "initial",
            }],
        )

        # Update config with calculated stop price
        stop_loss.config.stop_price = stop_price

        # Store stop loss
        async with self._lock:
            self._stop_losses[stop_id] = stop_loss

            # Limit number of stop losses
            if len(self._stop_losses) > self.max_stop_losses:
                oldest = sorted(
                    self._stop_losses.keys(),
                    key=lambda x: self._stop_losses[x].created_at,
                )[0]
                del self._stop_losses[oldest]

        # Update metrics
        STOP_LOSS_ACTIVE.labels(symbol=config.symbol).inc()

        logger.info(
            f"Created stop loss {stop_id} for {config.symbol} "
            f"at {stop_price:.4f} ({config.stop_type.value})"
        )

        return stop_loss

    async def update_stop_loss(
        self,
        stop_id: str,
        current_price: float,
    ) -> Optional[StopLoss]:
        """
        Update a stop loss based on current price.

        Args:
            stop_id: Stop loss ID
            current_price: Current market price

        Returns:
            Updated stop loss or None
        """
        async with self._lock:
            stop_loss = self._stop_losses.get(stop_id)

            if not stop_loss or stop_loss.status != StopLossStatus.ACTIVE:
                return None

            old_stop = stop_loss.config.stop_price

            # Calculate new stop price
            new_stop = await self._calculate_stop_price(
                stop_loss.config,
                current_price=current_price,
            )

            # Check if stop price needs updating
            should_update = False

            if stop_loss.config.stop_type == StopLossType.TRAILING:
                # Trailing stop: only update when price moves favorably
                if stop_loss.config.position_side == "long":
                    if current_price > stop_loss.config.entry_price and new_stop > old_stop:
                        should_update = True
                else:  # short
                    if current_price < stop_loss.config.entry_price and new_stop < old_stop:
                        should_update = True

            elif stop_loss.config.stop_type in [StopLossType.VOLATILITY_BASED, StopLossType.ATR_BASED]:
                # Volatility-based: update when volatility changes significantly
                if abs(new_stop - old_stop) / old_stop > 0.01:  # 1% change
                    should_update = True

            else:
                # Other types: update if price moved
                should_update = True

            if should_update and new_stop != old_stop:
                stop_loss.config.stop_price = new_stop
                stop_loss.updated_at = datetime.utcnow()

                # Record history
                stop_loss.stop_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "price": new_stop,
                    "old_price": old_stop,
                    "current_price": current_price,
                })

                # Update metrics
                STOP_LOSS_ACTIVE.labels(symbol=stop_loss.config.symbol).inc()

                # Trigger event
                await self._trigger_event(StopLossEvent(
                    stop_id=stop_id,
                    symbol=stop_loss.config.symbol,
                    event_type="updated",
                    old_stop=old_stop,
                    new_stop=new_stop,
                    timestamp=datetime.utcnow(),
                    reason="price_update",
                ))

                logger.debug(
                    f"Updated stop loss {stop_id}: {old_stop:.4f} -> {new_stop:.4f}"
                )

                return stop_loss

            return stop_loss

    async def _calculate_stop_price(
        self,
        config: StopLossConfig,
        current_price: Optional[float] = None,
    ) -> float:
        """
        Calculate stop price based on configuration.

        Args:
            config: Stop loss configuration
            current_price: Current market price

        Returns:
            Stop price
        """
        entry = config.entry_price
        price = current_price or config.current_price or entry

        if config.stop_type == StopLossType.FIXED:
            return config.stop_value or entry * (1 - config.stop_percent) if config.stop_percent else entry

        elif config.stop_type == StopLossType.PERCENTAGE:
            percent = config.stop_percent or 0.02
            if config.position_side == "long":
                return entry * (1 - percent)
            else:
                return entry * (1 + percent)

        elif config.stop_type == StopLossType.TRAILING:
            percent = config.trailing_percent or 0.02
            if config.position_side == "long":
                # Long position: trailing stop moves up
                trailing_stop = price * (1 - percent)
                if config.stop_price > 0:
                    return max(config.stop_price, trailing_stop)
                return trailing_stop
            else:
                # Short position: trailing stop moves down
                trailing_stop = price * (1 + percent)
                if config.stop_price > 0:
                    return min(config.stop_price, trailing_stop)
                return trailing_stop

        elif config.stop_type == StopLossType.VOLATILITY_BASED:
            # Calculate volatility-based stop
            volatility = await self._get_volatility(config.symbol, config.lookback_period)
            if volatility > 0:
                stop_percent = volatility * config.volatility_multiplier
                if config.position_side == "long":
                    return entry * (1 - stop_percent)
                else:
                    return entry * (1 + stop_percent)
            return entry * (1 - config.stop_percent) if config.stop_percent else entry

        elif config.stop_type == StopLossType.ATR_BASED:
            # Calculate ATR-based stop
            atr = await self._get_atr(config.symbol, config.atr_period)
            if atr > 0:
                stop_distance = atr * config.atr_multiplier
                if config.position_side == "long":
                    return entry - stop_distance
                else:
                    return entry + stop_distance
            return entry * (1 - config.stop_percent) if config.stop_percent else entry

        elif config.stop_type == StopLossType.TIME_BASED:
            # Time-based stop: use original stop but check time
            if config.stop_price > 0:
                return config.stop_price
            return entry * (1 - config.stop_percent) if config.stop_percent else entry

        elif config.stop_type == StopLossType.BREAK_EVEN:
            # Move to break-even when profit target reached
            trigger = config.breakeven_trigger_percent or 0.01
            if config.position_side == "long":
                if price > entry * (1 + trigger):
                    return entry
            else:
                if price < entry * (1 - trigger):
                    return entry
            return config.stop_price or entry * (1 - config.stop_percent) if config.stop_percent else entry

        elif config.stop_type == StopLossType.MULTI_LEVEL:
            # Multi-level stop loss
            if config.levels:
                for level in sorted(config.levels, key=lambda x: x.get("price", 0)):
                    if config.position_side == "long":
                        if price > level.get("trigger", 0):
                            return level.get("stop", 0)
                    else:
                        if price < level.get("trigger", 0):
                            return level.get("stop", 0)
            return config.stop_price or entry * (1 - config.stop_percent) if config.stop_percent else entry

        else:
            # Fallback to percentage-based
            percent = config.stop_percent or 0.02
            if config.position_side == "long":
                return entry * (1 - percent)
            else:
                return entry * (1 + percent)

    async def _get_volatility(self, symbol: str, period: int) -> float:
        """
        Get volatility for a symbol.

        Args:
            symbol: Trading symbol
            period: Lookback period

        Returns:
            Volatility value
        """
        if self.market_data_service:
            try:
                ohlc_data = await self.market_data_service.get_ohlc(
                    symbol=symbol,
                    timeframe="1h",
                    limit=period,
                )

                if ohlc_data and len(ohlc_data) > 1:
                    returns = []
                    for i in range(1, len(ohlc_data)):
                        ret = (ohlc_data[i]["close"] - ohlc_data[i-1]["close"]) / ohlc_data[i-1]["close"]
                        returns.append(ret)
                    return np.std(returns) if returns else 0.02

            except Exception as e:
                logger.error(f"Error getting volatility for {symbol}: {e}")

        return 0.02  # Default 2% volatility

    async def _get_atr(self, symbol: str, period: int) -> float:
        """
        Get ATR for a symbol.

        Args:
            symbol: Trading symbol
            period: ATR period

        Returns:
            ATR value
        """
        if self.market_data_service:
            try:
                ohlc_data = await self.market_data_service.get_ohlc(
                    symbol=symbol,
                    timeframe="1h",
                    limit=period + 1,
                )

                if ohlc_data and len(ohlc_data) > period:
                    highs = [d["high"] for d in ohlc_data]
                    lows = [d["low"] for d in ohlc_data]
                    closes = [d["close"] for d in ohlc_data]

                    tr = []
                    for i in range(1, len(ohlc_data)):
                        hl = highs[i] - lows[i]
                        hc = abs(highs[i] - closes[i-1])
                        lc = abs(lows[i] - closes[i-1])
                        tr.append(max(hl, hc, lc))

                    return np.mean(tr[-period:]) if tr else 0

            except Exception as e:
                logger.error(f"Error getting ATR for {symbol}: {e}")

        return 0.01  # Default ATR

    async def _check_trigger_conditions(self):
        """Check if any stop losses should be triggered."""
        async with self._lock:
            for stop_id, stop_loss in list(self._stop_losses.items()):
                if stop_loss.status != StopLossStatus.ACTIVE:
                    continue

                config = stop_loss.config
                current_price = config.current_price

                # Check if stop should be triggered
                should_trigger = False
                trigger_price = 0.0

                if config.position_side == "long":
                    if current_price <= config.stop_price:
                        should_trigger = True
                        trigger_price = current_price
                else:  # short
                    if current_price >= config.stop_price:
                        should_trigger = True
                        trigger_price = current_price

                # Check time-based expiry
                if config.expire_at and datetime.utcnow() > config.expire_at:
                    should_trigger = True
                    trigger_price = current_price

                if should_trigger:
                    await self._trigger_stop_loss(stop_id, trigger_price)

    async def _trigger_stop_loss(self, stop_id: str, price: float):
        """
        Trigger a stop loss.

        Args:
            stop_id: Stop loss ID
            price: Trigger price
        """
        async with self._lock:
            stop_loss = self._stop_losses.get(stop_id)

            if not stop_loss or stop_loss.status != StopLossStatus.ACTIVE:
                return

            # Update status
            stop_loss.status = StopLossStatus.TRIGGERED
            stop_loss.triggered_at = datetime.utcnow()
            stop_loss.triggered_price = price
            stop_loss.updated_at = datetime.utcnow()

            # Update metrics
            STOP_LOSS_COUNTER.labels(
                stop_type=stop_loss.config.stop_type.value,
                symbol=stop_loss.config.symbol,
                status="triggered",
            ).inc()
            STOP_LOSS_ACTIVE.labels(symbol=stop_loss.config.symbol).dec()

            # Trigger event
            await self._trigger_event(StopLossEvent(
                stop_id=stop_id,
                symbol=stop_loss.config.symbol,
                event_type="triggered",
                old_stop=stop_loss.config.stop_price,
                new_stop=price,
                timestamp=datetime.utcnow(),
                reason=f"Price {price} hit stop {stop_loss.config.stop_price}",
                metadata={"trigger_price": price},
            ))

            logger.info(
                f"Stop loss {stop_id} triggered at {price:.4f} "
                f"({stop_loss.config.stop_type.value})"
            )

    async def cancel_stop_loss(self, stop_id: str) -> bool:
        """
        Cancel a stop loss.

        Args:
            stop_id: Stop loss ID

        Returns:
            True if cancelled
        """
        async with self._lock:
            stop_loss = self._stop_losses.get(stop_id)

            if not stop_loss:
                return False

            if stop_loss.status != StopLossStatus.ACTIVE:
                return False

            stop_loss.status = StopLossStatus.CANCELLED
            stop_loss.updated_at = datetime.utcnow()

            STOP_LOSS_ACTIVE.labels(symbol=stop_loss.config.symbol).dec()

            await self._trigger_event(StopLossEvent(
                stop_id=stop_id,
                symbol=stop_loss.config.symbol,
                event_type="cancelled",
                old_stop=stop_loss.config.stop_price,
                new_stop=stop_loss.config.stop_price,
                timestamp=datetime.utcnow(),
                reason="Manual cancellation",
            ))

            logger.info(f"Stop loss {stop_id} cancelled")
            return True

    async def _cleanup_old_stop_losses(self):
        """Clean up old completed stop losses."""
        cutoff = datetime.utcnow() - timedelta(seconds=self.auto_cleanup_age)

        async with self._lock:
            for stop_id, stop_loss in list(self._stop_losses.items()):
                if stop_loss.status in [
                    StopLossStatus.TRIGGERED,
                    StopLossStatus.CANCELLED,
                    StopLossStatus.EXPIRED,
                ]:
                    if stop_loss.updated_at < cutoff:
                        del self._stop_losses[stop_id]
                        logger.debug(f"Cleaned up old stop loss {stop_id}")

    async def _update_stop_losses(self):
        """Update all active stop losses with current prices."""
        async with self._lock:
            for stop_id, stop_loss in self._stop_losses.items():
                if stop_loss.status == StopLossStatus.ACTIVE:
                    # Get current price from market data
                    if self.market_data_service:
                        try:
                            ticker = await self.market_data_service.get_ticker(
                                stop_loss.config.symbol
                            )
                            if ticker:
                                current_price = ticker.get("last_price", 0)
                                if current_price > 0:
                                    stop_loss.config.current_price = current_price
                        except Exception as e:
                            logger.debug(f"Error getting price for {stop_id}: {e}")

    async def get_stop_loss(self, stop_id: str) -> Optional[StopLoss]:
        """
        Get a stop loss by ID.

        Args:
            stop_id: Stop loss ID

        Returns:
            Stop loss or None
        """
        async with self._lock:
            return self._stop_losses.get(stop_id)

    async def get_active_stop_losses(
        self,
        symbol: Optional[str] = None,
    ) -> List[StopLoss]:
        """
        Get active stop losses.

        Args:
            symbol: Filter by symbol

        Returns:
            List of active stop losses
        """
        async with self._lock:
            stop_losses = [
                sl for sl in self._stop_losses.values()
                if sl.status == StopLossStatus.ACTIVE
            ]

            if symbol:
                stop_losses = [sl for sl in stop_losses if sl.config.symbol == symbol]

            return stop_losses

    async def get_stop_loss_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[StopLoss]:
        """
        Get stop loss history.

        Args:
            symbol: Filter by symbol
            limit: Maximum number of results

        Returns:
            List of stop losses
        """
        async with self._lock:
            stop_losses = list(self._stop_losses.values())

            if symbol:
                stop_losses = [sl for sl in stop_losses if sl.config.symbol == symbol]

            stop_losses.sort(key=lambda x: x.created_at, reverse=True)
            return stop_losses[:limit]

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get stop loss statistics.

        Returns:
            Stop loss statistics
        """
        async with self._lock:
            total = len(self._stop_losses)
            active = sum(1 for sl in self._stop_losses.values() if sl.status == StopLossStatus.ACTIVE)
            triggered = sum(1 for sl in self._stop_losses.values() if sl.status == StopLossStatus.TRIGGERED)

            # Calculate success rate
            if total > 0:
                success_rate = triggered / total
            else:
                success_rate = 0

            # Group by symbol
            by_symbol = {}
            for sl in self._stop_losses.values():
                symbol = sl.config.symbol
                if symbol not in by_symbol:
                    by_symbol[symbol] = {"active": 0, "triggered": 0, "total": 0}
                by_symbol[symbol]["total"] += 1
                if sl.status == StopLossStatus.ACTIVE:
                    by_symbol[symbol]["active"] += 1
                elif sl.status == StopLossStatus.TRIGGERED:
                    by_symbol[symbol]["triggered"] += 1

            return {
                "total_stop_losses": total,
                "active": active,
                "triggered": triggered,
                "success_rate": success_rate,
                "by_symbol": by_symbol,
                "timestamp": datetime.utcnow().isoformat(),
            }

    def register_event_handler(self, handler: Callable):
        """
        Register an event handler.

        Args:
            handler: Handler function
        """
        self._event_handlers.append(handler)
        logger.info("Registered stop loss event handler")

    async def _trigger_event(self, event: StopLossEvent):
        """
        Trigger event handlers.

        Args:
            event: Stop loss event
        """
        for handler in self._event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")

    async def shutdown(self):
        """Shutdown the stop loss manager."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("StopLossManager shut down")


# Export singleton
stop_loss_manager = StopLossManager()
