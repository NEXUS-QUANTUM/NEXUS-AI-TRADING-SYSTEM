"""
NEXUS AI TRADING SYSTEM - Take Profit Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced take profit management system for optimizing trade exits,
implementing dynamic profit targets, trailing take profits, and
automated profit taking strategies.
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
TAKE_PROFIT_COUNTER = Counter(
    "nexus_take_profit_triggers_total",
    "Total number of take profit triggers",
    ["tp_type", "symbol", "status"],
)
TAKE_PROFIT_ACTIVE = Gauge(
    "nexus_take_profit_active",
    "Number of active take profits",
    ["symbol"],
)
TAKE_PROFIT_DURATION = Histogram(
    "nexus_take_profit_duration_seconds",
    "Duration of take profit monitoring",
    ["tp_type"],
)


class TakeProfitType(Enum):
    """Types of take profits."""

    FIXED = "fixed"                      # Fixed price take profit
    PERCENTAGE = "percentage"            # Percentage-based take profit
    TRAILING = "trailing"                # Trailing take profit
    VOLATILITY_BASED = "volatility_based"  # Volatility-adjusted take profit
    RISK_REWARD = "risk_reward"          # Risk-reward ratio based
    TIME_BASED = "time_based"            # Time-based take profit
    SCALING = "scaling"                  # Scaling out at multiple levels
    DYNAMIC = "dynamic"                  # Dynamic take profit
    RSI_BASED = "rsi_based"              # RSI-based take profit
    FIBONACCI = "fibonacci"              # Fibonacci-based take profit


class TakeProfitStatus(Enum):
    """Status of a take profit."""

    ACTIVE = "active"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PARTIAL = "partial"


@dataclass
class TakeProfitConfig:
    """Configuration for take profit."""

    tp_type: TakeProfitType
    # Fixed/Percentage parameters
    tp_value: Optional[float] = None
    tp_percent: Optional[float] = None

    # Trailing parameters
    trailing_percent: Optional[float] = None
    trailing_pips: Optional[float] = None
    activation_threshold: Optional[float] = None

    # Risk-reward parameters
    risk_reward_ratio: float = 2.0

    # Volatility parameters
    volatility_multiplier: float = 1.5
    lookback_period: int = 20

    # Scaling parameters
    levels: List[Dict[str, Any]] = field(default_factory=list)
    level_percentages: List[float] = field(default_factory=list)

    # Time parameters
    time_limit_hours: float = 48.0

    # RSI parameters
    rsi_upper_threshold: float = 70.0
    rsi_period: int = 14

    # Fibonacci parameters
    fib_levels: List[float] = field(default_factory=lambda: [0.382, 0.5, 0.618, 0.786])

    # Common parameters
    symbol: str = ""
    entry_price: float = 0.0
    tp_price: float = 0.0
    current_price: float = 0.0
    quantity: float = 0.0
    position_side: str = "long"  # "long" or "short"
    stop_loss: float = 0.0
    risk_amount: float = 0.0

    # Advanced parameters
    use_partial_close: bool = False
    partial_close_percent: float = 0.5
    partial_close_levels: List[float] = field(default_factory=list)
    breakeven_at_level: Optional[float] = None
    expire_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tp_type": self.tp_type.value,
            "tp_value": self.tp_value,
            "tp_percent": self.tp_percent,
            "trailing_percent": self.trailing_percent,
            "trailing_pips": self.trailing_pips,
            "activation_threshold": self.activation_threshold,
            "risk_reward_ratio": self.risk_reward_ratio,
            "volatility_multiplier": self.volatility_multiplier,
            "lookback_period": self.lookback_period,
            "levels": self.levels,
            "level_percentages": self.level_percentages,
            "time_limit_hours": self.time_limit_hours,
            "rsi_upper_threshold": self.rsi_upper_threshold,
            "rsi_period": self.rsi_period,
            "fib_levels": self.fib_levels,
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "tp_price": self.tp_price,
            "current_price": self.current_price,
            "quantity": self.quantity,
            "position_side": self.position_side,
            "stop_loss": self.stop_loss,
            "risk_amount": self.risk_amount,
            "use_partial_close": self.use_partial_close,
            "partial_close_percent": self.partial_close_percent,
            "partial_close_levels": self.partial_close_levels,
            "breakeven_at_level": self.breakeven_at_level,
            "expire_at": self.expire_at.isoformat() if self.expire_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TakeProfitConfig":
        """Create from dictionary."""
        return cls(
            tp_type=TakeProfitType(data["tp_type"]),
            tp_value=data.get("tp_value"),
            tp_percent=data.get("tp_percent"),
            trailing_percent=data.get("trailing_percent"),
            trailing_pips=data.get("trailing_pips"),
            activation_threshold=data.get("activation_threshold"),
            risk_reward_ratio=data.get("risk_reward_ratio", 2.0),
            volatility_multiplier=data.get("volatility_multiplier", 1.5),
            lookback_period=data.get("lookback_period", 20),
            levels=data.get("levels", []),
            level_percentages=data.get("level_percentages", []),
            time_limit_hours=data.get("time_limit_hours", 48.0),
            rsi_upper_threshold=data.get("rsi_upper_threshold", 70.0),
            rsi_period=data.get("rsi_period", 14),
            fib_levels=data.get("fib_levels", [0.382, 0.5, 0.618, 0.786]),
            symbol=data.get("symbol", ""),
            entry_price=data.get("entry_price", 0.0),
            tp_price=data.get("tp_price", 0.0),
            current_price=data.get("current_price", 0.0),
            quantity=data.get("quantity", 0.0),
            position_side=data.get("position_side", "long"),
            stop_loss=data.get("stop_loss", 0.0),
            risk_amount=data.get("risk_amount", 0.0),
            use_partial_close=data.get("use_partial_close", False),
            partial_close_percent=data.get("partial_close_percent", 0.5),
            partial_close_levels=data.get("partial_close_levels", []),
            breakeven_at_level=data.get("breakeven_at_level"),
            expire_at=datetime.fromisoformat(data["expire_at"]) if data.get("expire_at") else None,
        )


@dataclass
class TakeProfit:
    """Take profit instance."""

    id: str
    config: TakeProfitConfig
    status: TakeProfitStatus = TakeProfitStatus.ACTIVE
    triggered_at: Optional[datetime] = None
    triggered_price: float = 0.0
    triggered_quantity: float = 0.0
    remaining_quantity: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tp_history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "config": self.config.to_dict(),
            "status": self.status.value,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "triggered_price": self.triggered_price,
            "triggered_quantity": self.triggered_quantity,
            "remaining_quantity": self.remaining_quantity,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tp_history": self.tp_history,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TakeProfit":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            config=TakeProfitConfig.from_dict(data["config"]),
            status=TakeProfitStatus(data["status"]),
            triggered_at=datetime.fromisoformat(data["triggered_at"]) if data.get("triggered_at") else None,
            triggered_price=data.get("triggered_price", 0.0),
            triggered_quantity=data.get("triggered_quantity", 0.0),
            remaining_quantity=data.get("remaining_quantity", 0.0),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            tp_history=data.get("tp_history", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TakeProfitEvent:
    """Take profit event."""

    tp_id: str
    symbol: str
    event_type: str
    old_tp: float
    new_tp: float
    timestamp: datetime
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class TakeProfitManager:
    """
    Advanced take profit management system.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        market_data_service: Optional[Any] = None,
    ):
        """
        Initialize the take profit manager.

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
        self._take_profits: Dict[str, TakeProfit] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._event_handlers: List[Callable] = []

        # Load configuration
        self.tp_config = self.config.get("take_profit_manager", {})
        self.monitor_interval = self.tp_config.get("monitor_interval", 1)  # seconds
        self.max_take_profits = self.tp_config.get("max_take_profits", 1000)
        self.auto_cleanup_age = self.tp_config.get("auto_cleanup_age", 3600 * 48)  # 48 hours
        self.default_tp_type = TakeProfitType(
            self.tp_config.get("default_tp_type", "risk_reward")
        )

        # Start monitoring
        self._start_monitoring()

        logger.info("TakeProfitManager initialized")

    def _start_monitoring(self):
        """Start the monitoring task."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        """Background loop for monitoring take profits."""
        while True:
            try:
                await self._update_take_profits()
                await self._check_trigger_conditions()
                await self._cleanup_old_take_profits()
                await asyncio.sleep(self.monitor_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)

    async def create_take_profit(
        self,
        config: Union[TakeProfitConfig, Dict[str, Any]],
        tp_id: Optional[str] = None,
    ) -> TakeProfit:
        """
        Create a new take profit.

        Args:
            config: Take profit configuration
            tp_id: Optional take profit ID

        Returns:
            Created take profit
        """
        if isinstance(config, dict):
            config = TakeProfitConfig.from_dict(config)

        # Generate ID
        if tp_id is None:
            tp_id = f"tp_{config.symbol}_{int(time.time())}"

        # Calculate initial take profit price
        tp_price = await self._calculate_tp_price(config)

        # Create take profit
        take_profit = TakeProfit(
            id=tp_id,
            config=config,
            status=TakeProfitStatus.ACTIVE,
            remaining_quantity=config.quantity,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            tp_history=[{
                "timestamp": datetime.utcnow().isoformat(),
                "price": tp_price,
                "type": "initial",
            }],
        )

        # Update config with calculated TP price
        take_profit.config.tp_price = tp_price

        # Store take profit
        async with self._lock:
            self._take_profits[tp_id] = take_profit

            # Limit number of take profits
            if len(self._take_profits) > self.max_take_profits:
                oldest = sorted(
                    self._take_profits.keys(),
                    key=lambda x: self._take_profits[x].created_at,
                )[0]
                del self._take_profits[oldest]

        # Update metrics
        TAKE_PROFIT_ACTIVE.labels(symbol=config.symbol).inc()

        logger.info(
            f"Created take profit {tp_id} for {config.symbol} "
            f"at {tp_price:.4f} ({config.tp_type.value})"
        )

        return take_profit

    async def update_take_profit(
        self,
        tp_id: str,
        current_price: float,
    ) -> Optional[TakeProfit]:
        """
        Update a take profit based on current price.

        Args:
            tp_id: Take profit ID
            current_price: Current market price

        Returns:
            Updated take profit or None
        """
        async with self._lock:
            take_profit = self._take_profits.get(tp_id)

            if not take_profit or take_profit.status not in [
                TakeProfitStatus.ACTIVE,
                TakeProfitStatus.PARTIAL,
            ]:
                return None

            old_tp = take_profit.config.tp_price

            # Calculate new TP price
            new_tp = await self._calculate_tp_price(
                take_profit.config,
                current_price=current_price,
            )

            # Check if TP price needs updating
            should_update = False

            if take_profit.config.tp_type in [TakeProfitType.TRAILING, TakeProfitType.DYNAMIC]:
                # Trailing/Dynamic TP: update when price moves favorably
                if take_profit.config.position_side == "long":
                    if current_price > take_profit.config.entry_price and new_tp > old_tp:
                        should_update = True
                else:  # short
                    if current_price < take_profit.config.entry_price and new_tp < old_tp:
                        should_update = True

            elif take_profit.config.tp_type in [TakeProfitType.VOLATILITY_BASED]:
                # Volatility-based: update when volatility changes significantly
                if abs(new_tp - old_tp) / old_tp > 0.01:  # 1% change
                    should_update = True

            else:
                # Other types: update if price moved
                should_update = True

            if should_update and new_tp != old_tp:
                take_profit.config.tp_price = new_tp
                take_profit.updated_at = datetime.utcnow()

                # Record history
                take_profit.tp_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "price": new_tp,
                    "old_price": old_tp,
                    "current_price": current_price,
                })

                # Trigger event
                await self._trigger_event(TakeProfitEvent(
                    tp_id=tp_id,
                    symbol=take_profit.config.symbol,
                    event_type="updated",
                    old_tp=old_tp,
                    new_tp=new_tp,
                    timestamp=datetime.utcnow(),
                    reason="price_update",
                ))

                logger.debug(
                    f"Updated take profit {tp_id}: {old_tp:.4f} -> {new_tp:.4f}"
                )

                return take_profit

            return take_profit

    async def _calculate_tp_price(
        self,
        config: TakeProfitConfig,
        current_price: Optional[float] = None,
    ) -> float:
        """
        Calculate take profit price based on configuration.

        Args:
            config: Take profit configuration
            current_price: Current market price

        Returns:
            Take profit price
        """
        entry = config.entry_price
        price = current_price or config.current_price or entry

        if config.tp_type == TakeProfitType.FIXED:
            return config.tp_value or entry * (1 + config.tp_percent) if config.tp_percent else entry

        elif config.tp_type == TakeProfitType.PERCENTAGE:
            percent = config.tp_percent or 0.02
            if config.position_side == "long":
                return entry * (1 + percent)
            else:
                return entry * (1 - percent)

        elif config.tp_type == TakeProfitType.RISK_REWARD:
            risk = abs(entry - config.stop_loss) if config.stop_loss > 0 else entry * 0.01
            ratio = config.risk_reward_ratio or 2.0
            target = risk * ratio
            if config.position_side == "long":
                return entry + target
            else:
                return entry - target

        elif config.tp_type == TakeProfitType.TRAILING:
            percent = config.trailing_percent or 0.03
            if config.position_side == "long":
                # Long position: trailing TP moves up
                trailing_tp = price * (1 + percent)
                if config.tp_price > 0:
                    return max(config.tp_price, trailing_tp)
                return trailing_tp
            else:
                # Short position: trailing TP moves down
                trailing_tp = price * (1 - percent)
                if config.tp_price > 0:
                    return min(config.tp_price, trailing_tp)
                return trailing_tp

        elif config.tp_type == TakeProfitType.VOLATILITY_BASED:
            # Calculate volatility-based TP
            volatility = await self._get_volatility(config.symbol, config.lookback_period)
            if volatility > 0:
                tp_percent = volatility * config.volatility_multiplier
                if config.position_side == "long":
                    return entry * (1 + tp_percent)
                else:
                    return entry * (1 - tp_percent)
            return entry * (1 + config.tp_percent) if config.tp_percent else entry

        elif config.tp_type == TakeProfitType.SCALING:
            # Scaling out at multiple levels
            if config.level_percentages:
                # Sort levels based on position side
                if config.position_side == "long":
                    levels = sorted(config.level_percentages)
                else:
                    levels = sorted(config.level_percentages, reverse=True)

                # Calculate current level
                if config.position_side == "long":
                    for level in levels:
                        if price >= entry * (1 + level):
                            return entry * (1 + level)
                else:
                    for level in levels:
                        if price <= entry * (1 - level):
                            return entry * (1 - level)

            return entry * (1 + config.tp_percent) if config.tp_percent else entry

        elif config.tp_type == TakeProfitType.RSI_BASED:
            # RSI-based TP: use RSI to determine exit
            rsi = await self._get_rsi(config.symbol, config.rsi_period)
            if rsi is not None and rsi > config.rsi_upper_threshold:
                # Overbought condition for long, oversold for short
                if config.position_side == "long":
                    return price * 0.99  # Take profit near current price
                else:
                    return price * 1.01
            return entry * (1 + config.tp_percent) if config.tp_percent else entry

        elif config.tp_type == TakeProfitType.FIBONACCI:
            # Fibonacci-based TP
            if config.fib_levels and config.stop_loss > 0:
                range_high = entry if config.position_side == "long" else config.stop_loss
                range_low = config.stop_loss if config.position_side == "long" else entry
                range_size = abs(range_high - range_low)

                for level in config.fib_levels:
                    if config.position_side == "long":
                        tp = entry + range_size * level
                    else:
                        tp = entry - range_size * level

                    if level >= 0.5:  # Only use higher fib levels
                        return tp

            return entry * (1 + config.tp_percent) if config.tp_percent else entry

        elif config.tp_type == TakeProfitType.TIME_BASED:
            # Time-based TP: use original TP but check time
            if config.tp_price > 0:
                return config.tp_price
            return entry * (1 + config.tp_percent) if config.tp_percent else entry

        elif config.tp_type == TakeProfitType.DYNAMIC:
            # Dynamic TP based on market conditions
            if await self._should_adjust_tp(config):
                # Adjust TP based on market conditions
                volatility = await self._get_volatility(config.symbol, config.lookback_period)
                if volatility > 0:
                    if config.position_side == "long":
                        return price * (1 + volatility * 1.5)
                    else:
                        return price * (1 - volatility * 1.5)

            return config.tp_price or entry * (1 + config.tp_percent) if config.tp_percent else entry

        else:
            # Fallback to percentage-based
            percent = config.tp_percent or 0.02
            if config.position_side == "long":
                return entry * (1 + percent)
            else:
                return entry * (1 - percent)

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

    async def _get_rsi(self, symbol: str, period: int) -> Optional[float]:
        """
        Get RSI for a symbol.

        Args:
            symbol: Trading symbol
            period: RSI period

        Returns:
            RSI value or None
        """
        if self.market_data_service:
            try:
                ohlc_data = await self.market_data_service.get_ohlc(
                    symbol=symbol,
                    timeframe="1h",
                    limit=period + 1,
                )

                if ohlc_data and len(ohlc_data) > period:
                    closes = [d["close"] for d in ohlc_data]
                    gains = []
                    losses = []

                    for i in range(1, len(closes)):
                        diff = closes[i] - closes[i-1]
                        if diff > 0:
                            gains.append(diff)
                            losses.append(0)
                        else:
                            gains.append(0)
                            losses.append(abs(diff))

                    avg_gain = np.mean(gains[-period:]) if gains else 0
                    avg_loss = np.mean(losses[-period:]) if losses else 0

                    if avg_loss == 0:
                        return 100.0

                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                    return rsi

            except Exception as e:
                logger.error(f"Error getting RSI for {symbol}: {e}")

        return None

    async def _should_adjust_tp(self, config: TakeProfitConfig) -> bool:
        """
        Determine if TP should be adjusted dynamically.

        Args:
            config: Take profit configuration

        Returns:
            True if TP should be adjusted
        """
        # Check time factor
        if config.created_at:
            age = (datetime.utcnow() - config.created_at).total_seconds() / 3600
            if age > config.time_limit_hours / 2:
                return True

        # Check volatility factor
        volatility = await self._get_volatility(config.symbol, config.lookback_period)
        if volatility > 0.03:  # High volatility
            return True

        # Check price action
        price_change = abs(config.current_price - config.entry_price) / config.entry_price
        if price_change > 0.02:  # 2% price change
            return True

        return False

    async def _check_trigger_conditions(self):
        """Check if any take profits should be triggered."""
        async with self._lock:
            for tp_id, take_profit in list(self._take_profits.items()):
                if take_profit.status not in [TakeProfitStatus.ACTIVE, TakeProfitStatus.PARTIAL]:
                    continue

                config = take_profit.config
                current_price = config.current_price

                # Check if TP should be triggered
                should_trigger = False
                trigger_price = 0.0
                trigger_quantity = 0.0

                if config.position_side == "long":
                    if current_price >= config.tp_price:
                        should_trigger = True
                        trigger_price = current_price
                else:  # short
                    if current_price <= config.tp_price:
                        should_trigger = True
                        trigger_price = current_price

                # Check time-based expiry
                if config.expire_at and datetime.utcnow() > config.expire_at:
                    should_trigger = True
                    trigger_price = current_price

                if should_trigger:
                    # Calculate trigger quantity
                    if config.use_partial_close and take_profit.status == TakeProfitStatus.ACTIVE:
                        # Partial close
                        if config.partial_close_levels:
                            # Use levels for partial closes
                            for level in config.partial_close_levels:
                                if config.position_side == "long":
                                    if current_price >= config.entry_price * (1 + level):
                                        trigger_quantity = config.quantity * 0.5
                                        break
                                else:
                                    if current_price <= config.entry_price * (1 - level):
                                        trigger_quantity = config.quantity * 0.5
                                        break
                        else:
                            trigger_quantity = config.quantity * config.partial_close_percent

                        if trigger_quantity > 0 and trigger_quantity < config.quantity:
                            await self._partial_trigger_take_profit(tp_id, trigger_price, trigger_quantity)
                            continue

                    await self._trigger_take_profit(tp_id, trigger_price)

    async def _trigger_take_profit(self, tp_id: str, price: float):
        """
        Trigger a take profit.

        Args:
            tp_id: Take profit ID
            price: Trigger price
        """
        async with self._lock:
            take_profit = self._take_profits.get(tp_id)

            if not take_profit or take_profit.status not in [
                TakeProfitStatus.ACTIVE,
                TakeProfitStatus.PARTIAL,
            ]:
                return

            # Update status
            take_profit.status = TakeProfitStatus.TRIGGERED
            take_profit.triggered_at = datetime.utcnow()
            take_profit.triggered_price = price
            take_profit.triggered_quantity = take_profit.remaining_quantity or take_profit.config.quantity
            take_profit.remaining_quantity = 0
            take_profit.updated_at = datetime.utcnow()

            # Update metrics
            TAKE_PROFIT_COUNTER.labels(
                tp_type=take_profit.config.tp_type.value,
                symbol=take_profit.config.symbol,
                status="triggered",
            ).inc()
            TAKE_PROFIT_ACTIVE.labels(symbol=take_profit.config.symbol).dec()

            # Trigger event
            await self._trigger_event(TakeProfitEvent(
                tp_id=tp_id,
                symbol=take_profit.config.symbol,
                event_type="triggered",
                old_tp=take_profit.config.tp_price,
                new_tp=price,
                timestamp=datetime.utcnow(),
                reason=f"Price {price} hit TP {take_profit.config.tp_price}",
                metadata={
                    "trigger_price": price,
                    "quantity": take_profit.triggered_quantity,
                },
            ))

            logger.info(
                f"Take profit {tp_id} triggered at {price:.4f} "
                f"({take_profit.config.tp_type.value})"
            )

    async def _partial_trigger_take_profit(
        self,
        tp_id: str,
        price: float,
        quantity: float,
    ):
        """
        Partially trigger a take profit.

        Args:
            tp_id: Take profit ID
            price: Trigger price
            quantity: Quantity to close
        """
        async with self._lock:
            take_profit = self._take_profits.get(tp_id)

            if not take_profit or take_profit.status != TakeProfitStatus.ACTIVE:
                return

            if quantity >= take_profit.remaining_quantity:
                await self._trigger_take_profit(tp_id, price)
                return

            # Update remaining quantity
            take_profit.remaining_quantity = take_profit.config.quantity - quantity
            take_profit.status = TakeProfitStatus.PARTIAL
            take_profit.triggered_at = datetime.utcnow()
            take_profit.triggered_price = price
            take_profit.triggered_quantity = quantity
            take_profit.updated_at = datetime.utcnow()

            # Update metrics
            TAKE_PROFIT_COUNTER.labels(
                tp_type=take_profit.config.tp_type.value,
                symbol=take_profit.config.symbol,
                status="partial",
            ).inc()

            # Trigger event
            await self._trigger_event(TakeProfitEvent(
                tp_id=tp_id,
                symbol=take_profit.config.symbol,
                event_type="partial_triggered",
                old_tp=take_profit.config.tp_price,
                new_tp=price,
                timestamp=datetime.utcnow(),
                reason=f"Partial close at {price}",
                metadata={
                    "trigger_price": price,
                    "quantity": quantity,
                    "remaining": take_profit.remaining_quantity,
                },
            ))

            logger.info(
                f"Partial take profit {tp_id} triggered at {price:.4f} "
                f"(quantity: {quantity}, remaining: {take_profit.remaining_quantity})"
            )

    async def cancel_take_profit(self, tp_id: str) -> bool:
        """
        Cancel a take profit.

        Args:
            tp_id: Take profit ID

        Returns:
            True if cancelled
        """
        async with self._lock:
            take_profit = self._take_profits.get(tp_id)

            if not take_profit:
                return False

            if take_profit.status not in [TakeProfitStatus.ACTIVE, TakeProfitStatus.PARTIAL]:
                return False

            take_profit.status = TakeProfitStatus.CANCELLED
            take_profit.updated_at = datetime.utcnow()

            TAKE_PROFIT_ACTIVE.labels(symbol=take_profit.config.symbol).dec()

            await self._trigger_event(TakeProfitEvent(
                tp_id=tp_id,
                symbol=take_profit.config.symbol,
                event_type="cancelled",
                old_tp=take_profit.config.tp_price,
                new_tp=take_profit.config.tp_price,
                timestamp=datetime.utcnow(),
                reason="Manual cancellation",
            ))

            logger.info(f"Take profit {tp_id} cancelled")
            return True

    async def _cleanup_old_take_profits(self):
        """Clean up old completed take profits."""
        cutoff = datetime.utcnow() - timedelta(seconds=self.auto_cleanup_age)

        async with self._lock:
            for tp_id, take_profit in list(self._take_profits.items()):
                if take_profit.status in [
                    TakeProfitStatus.TRIGGERED,
                    TakeProfitStatus.CANCELLED,
                    TakeProfitStatus.EXPIRED,
                ]:
                    if take_profit.updated_at < cutoff:
                        del self._take_profits[tp_id]
                        logger.debug(f"Cleaned up old take profit {tp_id}")

    async def _update_take_profits(self):
        """Update all active take profits with current prices."""
        async with self._lock:
            for tp_id, take_profit in self._take_profits.items():
                if take_profit.status in [TakeProfitStatus.ACTIVE, TakeProfitStatus.PARTIAL]:
                    # Get current price from market data
                    if self.market_data_service:
                        try:
                            ticker = await self.market_data_service.get_ticker(
                                take_profit.config.symbol
                            )
                            if ticker:
                                current_price = ticker.get("last_price", 0)
                                if current_price > 0:
                                    take_profit.config.current_price = current_price
                        except Exception as e:
                            logger.debug(f"Error getting price for {tp_id}: {e}")

    async def get_take_profit(self, tp_id: str) -> Optional[TakeProfit]:
        """
        Get a take profit by ID.

        Args:
            tp_id: Take profit ID

        Returns:
            Take profit or None
        """
        async with self._lock:
            return self._take_profits.get(tp_id)

    async def get_active_take_profits(
        self,
        symbol: Optional[str] = None,
    ) -> List[TakeProfit]:
        """
        Get active take profits.

        Args:
            symbol: Filter by symbol

        Returns:
            List of active take profits
        """
        async with self._lock:
            take_profits = [
                tp for tp in self._take_profits.values()
                if tp.status in [TakeProfitStatus.ACTIVE, TakeProfitStatus.PARTIAL]
            ]

            if symbol:
                take_profits = [tp for tp in take_profits if tp.config.symbol == symbol]

            return take_profits

    async def get_take_profit_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[TakeProfit]:
        """
        Get take profit history.

        Args:
            symbol: Filter by symbol
            limit: Maximum number of results

        Returns:
            List of take profits
        """
        async with self._lock:
            take_profits = list(self._take_profits.values())

            if symbol:
                take_profits = [tp for tp in take_profits if tp.config.symbol == symbol]

            take_profits.sort(key=lambda x: x.created_at, reverse=True)
            return take_profits[:limit]

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get take profit statistics.

        Returns:
            Take profit statistics
        """
        async with self._lock:
            total = len(self._take_profits)
            active = sum(1 for tp in self._take_profits.values() if tp.status == TakeProfitStatus.ACTIVE)
            partial = sum(1 for tp in self._take_profits.values() if tp.status == TakeProfitStatus.PARTIAL)
            triggered = sum(1 for tp in self._take_profits.values() if tp.status == TakeProfitStatus.TRIGGERED)

            # Calculate success rate
            if total > 0:
                success_rate = triggered / total
            else:
                success_rate = 0

            # Calculate average profit
            profits = []
            for tp in self._take_profits.values():
                if tp.status == TakeProfitStatus.TRIGGERED and tp.triggered_price > 0:
                    if tp.config.position_side == "long":
                        profit = (tp.triggered_price - tp.config.entry_price) / tp.config.entry_price
                    else:
                        profit = (tp.config.entry_price - tp.triggered_price) / tp.config.entry_price
                    profits.append(profit)

            avg_profit = np.mean(profits) if profits else 0

            # Group by symbol
            by_symbol = {}
            for tp in self._take_profits.values():
                symbol = tp.config.symbol
                if symbol not in by_symbol:
                    by_symbol[symbol] = {"active": 0, "partial": 0, "triggered": 0, "total": 0}
                by_symbol[symbol]["total"] += 1
                if tp.status == TakeProfitStatus.ACTIVE:
                    by_symbol[symbol]["active"] += 1
                elif tp.status == TakeProfitStatus.PARTIAL:
                    by_symbol[symbol]["partial"] += 1
                elif tp.status == TakeProfitStatus.TRIGGERED:
                    by_symbol[symbol]["triggered"] += 1

            return {
                "total_take_profits": total,
                "active": active,
                "partial": partial,
                "triggered": triggered,
                "success_rate": success_rate,
                "average_profit": avg_profit,
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
        logger.info("Registered take profit event handler")

    async def _trigger_event(self, event: TakeProfitEvent):
        """
        Trigger event handlers.

        Args:
            event: Take profit event
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
        """Shutdown the take profit manager."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("TakeProfitManager shut down")


# Export singleton
take_profit_manager = TakeProfitManager()
