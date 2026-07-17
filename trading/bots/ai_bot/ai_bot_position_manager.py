# trading/bots/ai_bot/ai_bot_position_manager.py
# NEXUS AI TRADING SYSTEM - AI Bot Position Manager
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
AI Bot Position Manager for NEXUS AI Trading System.
Provides comprehensive position management capabilities including:
- Position tracking and monitoring
- Position sizing and scaling
- Risk management integration
- Profit/Loss calculation
- Position metrics and analytics
- Position closure and adjustment
- Multi-asset position management
- Position performance tracking
- Automated position sizing
- Position limits enforcement
"""

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from collections import deque, defaultdict

# NEXUS Imports
from trading.bots.ai_bot.config.bot_configs import BotConfig
from trading.bots.ai_bot.data.data_storage import DataStorage
from trading.bots.ai_bot.metrics.metrics_engine import MetricsEngine
from trading.bots.ai_bot.risk.risk_manager import RiskManager
from trading.bots.ai_bot.execution.order_executor import OrderExecutor
from shared.utilities.logger import get_logger

logger = get_logger("nexus.trading.bot.position_manager")


# ============================================================================
# Enums & Constants
# ============================================================================

class PositionSide(str, Enum):
    """Position side."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class PositionStatus(str, Enum):
    """Position status."""
    OPEN = "open"
    CLOSED = "closed"
    PARTIALLY_CLOSED = "partially_closed"
    LIQUIDATED = "liquidated"
    HEDGED = "hedged"
    EXPIRED = "expired"


class PositionType(str, Enum):
    """Position type."""
    SPOT = "spot"
    FUTURES = "futures"
    PERPETUAL = "perpetual"
    OPTION = "option"
    SWAP = "swap"


@dataclass
class Position:
    """Position data."""
    position_id: str
    symbol: str
    side: PositionSide
    position_type: PositionType
    entry_price: float
    current_price: float
    quantity: float
    initial_quantity: float
    average_entry_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    pnl_percentage: float = 0.0
    open_time: datetime = field(default_factory=datetime.utcnow)
    close_time: Optional[datetime] = None
    status: PositionStatus = PositionStatus.OPEN
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    trailing_stop_price: Optional[float] = None
    trailing_stop_activation: Optional[float] = None
    max_quantity: float = 0.0
    min_quantity: float = 0.0
    entry_quantity: float = 0.0
    exit_quantity: float = 0.0
    total_value: float = 0.0
    margin_used: float = 0.0
    leverage: float = 1.0
    liquidation_price: Optional[float] = None
    collateral: float = 0.0
    fees: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    orders: List[str] = field(default_factory=list)
    child_positions: List[str] = field(default_factory=list)
    parent_position_id: Optional[str] = None


@dataclass
class PositionSummary:
    """Position summary."""
    total_positions: int
    open_positions: int
    closed_positions: int
    total_pnl: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    total_quantity: float
    total_value: float
    total_margin: float
    average_leverage: float
    win_count: int
    loss_count: int
    win_rate: float
    best_position: Optional[Position] = None
    worst_position: Optional[Position] = None
    by_symbol: Dict[str, int] = field(default_factory=dict)
    by_side: Dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ============================================================================
# Position Manager
# ============================================================================

class PositionManager:
    """
    Advanced Position Manager for NEXUS AI Trading Bot.
    """

    def __init__(
        self,
        config: BotConfig,
        risk_manager: RiskManager,
        order_executor: OrderExecutor,
        data_storage: DataStorage,
        metrics_engine: MetricsEngine,
    ):
        """
        Initialize position manager.

        Args:
            config: Bot configuration
            risk_manager: Risk manager instance
            order_executor: Order executor instance
            data_storage: Data storage instance
            metrics_engine: Metrics engine instance
        """
        self.config = config
        self.risk_manager = risk_manager
        self.order_executor = order_executor
        self.data_storage = data_storage
        self.metrics_engine = metrics_engine

        # Position storage
        self._positions: Dict[str, Position] = {}
        self._open_positions: Dict[str, Position] = {}
        self._position_history: deque = deque(maxlen=10000)

        # Performance metrics
        self._performance = {
            "positions_created": 0,
            "positions_closed": 0,
            "positions_liquidated": 0,
            "winning_positions": 0,
            "losing_positions": 0,
            "total_pnl": 0.0,
            "total_volume": 0.0,
            "avg_hold_time": 0.0,
            "max_position_size": 0.0,
            "avg_position_size": 0.0,
        }

        # Position ID generation
        self._position_id_counter = 0

        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {
            "position_opened": [],
            "position_updated": [],
            "position_closed": [],
            "position_liquidated": [],
            "stop_loss_triggered": [],
            "take_profit_triggered": [],
            "trailing_stop_updated": [],
        }

        # Position limits
        self._position_limits = config.get("position_limits", {})
        self._max_positions = self._position_limits.get("max_positions", 10)
        self._max_position_size = self._position_limits.get("max_position_size", 100000)
        self._max_leverage = self._position_limits.get("max_leverage", 2)

        logger.info(
            "PositionManager initialized",
            extra={
                "max_positions": self._max_positions,
                "max_position_size": self._max_position_size,
                "max_leverage": self._max_leverage,
            }
        )

    # ========================================================================
    # Position Creation
    # ========================================================================

    async def open_position(
        self,
        symbol: str,
        side: PositionSide,
        position_type: PositionType,
        entry_price: float,
        quantity: float,
        leverage: float = 1.0,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        trailing_stop_percent: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Position]:
        """
        Open a new position.

        Args:
            symbol: Trading symbol
            side: Position side (long/short)
            position_type: Position type
            entry_price: Entry price
            quantity: Position quantity
            leverage: Leverage
            stop_loss_price: Stop loss price
            take_profit_price: Take profit price
            trailing_stop_percent: Trailing stop percentage
            metadata: Additional metadata
            tags: Position tags

        Returns:
            Position or None
        """
        # Check position limits
        if not await self._check_position_limits(symbol, side, quantity):
            logger.warning(f"Position limits exceeded for {symbol}")
            return None

        # Check risk limits
        risk_check = await self.risk_manager.check_position_limits(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=entry_price,
            leverage=leverage,
        )

        if not risk_check["allowed"]:
            logger.warning(f"Risk check failed: {risk_check['reason']}")
            return None

        # Generate position ID
        self._position_id_counter += 1
        position_id = f"pos_{int(time.time() * 1000)}_{self._position_id_counter}"

        # Calculate initial values
        total_value = quantity * entry_price
        margin_used = total_value / leverage if leverage > 0 else total_value

        # Create position
        position = Position(
            position_id=position_id,
            symbol=symbol,
            side=side,
            position_type=position_type,
            entry_price=entry_price,
            current_price=entry_price,
            quantity=quantity,
            initial_quantity=quantity,
            average_entry_price=entry_price,
            total_value=total_value,
            margin_used=margin_used,
            leverage=leverage,
            max_quantity=self._max_position_size,
            min_quantity=self._position_limits.get("min_position_size", 0.001),
            entry_quantity=quantity,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            metadata=metadata or {},
            tags=tags or [],
            open_time=datetime.utcnow(),
            status=PositionStatus.OPEN,
        )

        # Store position
        self._positions[position_id] = position
        self._open_positions[position_id] = position
        self._position_history.append(position)
        self._performance["positions_created"] += 1

        # Update metrics
        await self.metrics_engine.collect_metrics({
            f"position_{side.value}": 1,
            "positions_open": len(self._open_positions),
            "position_size": quantity,
            "position_value": total_value,
        }, metadata={"position_id": position_id, "symbol": symbol})

        # Emit event
        self._emit_event("position_opened", position)

        logger.info(
            f"Position opened: {position_id} - {side.value} {quantity} {symbol} @ {entry_price}"
        )

        return position

    # ========================================================================
    # Position Management
    # ========================================================================

    async def update_position(
        self,
        position_id: str,
        current_price: Optional[float] = None,
        quantity: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update a position.

        Args:
            position_id: Position ID
            current_price: Current price
            quantity: New quantity
            metadata: Additional metadata

        Returns:
            True if updated successfully
        """
        position = self._positions.get(position_id)

        if not position:
            logger.warning(f"Position not found: {position_id}")
            return False

        # Update price
        if current_price is not None:
            position.current_price = current_price

            # Calculate PnL
            await self._update_position_pnl(position)

            # Check stop loss
            if position.stop_loss_price and await self._check_stop_loss(position):
                await self.close_position(position_id, reason="stop_loss")
                self._emit_event("stop_loss_triggered", position)
                return True

            # Check take profit
            if position.take_profit_price and await self._check_take_profit(position):
                await self.close_position(position_id, reason="take_profit")
                self._emit_event("take_profit_triggered", position)
                return True

            # Update trailing stop
            if position.trailing_stop_price:
                await self._update_trailing_stop(position)

        # Update quantity
        if quantity is not None:
            position.quantity = quantity

        # Update metadata
        if metadata:
            position.metadata.update(metadata)

        position.updated_at = datetime.utcnow()

        self._emit_event("position_updated", position)
        return True

    async def close_position(
        self,
        position_id: str,
        exit_price: Optional[float] = None,
        reason: str = "manual",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Close a position.

        Args:
            position_id: Position ID
            exit_price: Exit price
            reason: Close reason
            metadata: Additional metadata

        Returns:
            True if closed successfully
        """
        position = self._positions.get(position_id)

        if not position:
            logger.warning(f"Position not found: {position_id}")
            return False

        if position.status != PositionStatus.OPEN:
            logger.warning(f"Position already closed: {position_id}")
            return False

        try:
            # Execute close order
            if exit_price:
                # Place limit order at exit price
                order_result = await self.order_executor.execute_order(
                    symbol=position.symbol,
                    side="sell" if position.side == PositionSide.LONG else "buy",
                    order_type="limit",
                    quantity=position.quantity,
                    price=exit_price,
                )
            else:
                # Place market order
                order_result = await self.order_executor.execute_order(
                    symbol=position.symbol,
                    side="sell" if position.side == PositionSide.LONG else "buy",
                    order_type="market",
                    quantity=position.quantity,
                )

            if not order_result["success"]:
                logger.error(f"Failed to close position {position_id}: {order_result.get('error')}")
                return False

            # Update position
            position.status = PositionStatus.CLOSED
            position.close_time = datetime.utcnow()
            position.exit_quantity = position.quantity

            if exit_price:
                position.current_price = exit_price
            else:
                position.current_price = order_result.get("executed_price", position.current_price)

            await self._update_position_pnl(position)

            # Remove from open positions
            if position_id in self._open_positions:
                del self._open_positions[position_id]

            # Update performance
            self._performance["positions_closed"] += 1
            self._performance["total_pnl"] += position.total_pnl
            self._performance["total_volume"] += position.total_value

            if position.total_pnl > 0:
                self._performance["winning_positions"] += 1
            elif position.total_pnl < 0:
                self._performance["losing_positions"] += 1

            # Calculate hold time
            hold_time = (position.close_time - position.open_time).total_seconds() / 3600
            self._performance["avg_hold_time"] = (
                (self._performance["avg_hold_time"] *
                 (self._performance["positions_closed"] - 1) +
                 hold_time) /
                self._performance["positions_closed"]
            )

            # Update metrics
            await self.metrics_engine.collect_metrics({
                "positions_closed": 1,
                "positions_open": len(self._open_positions),
                f"position_{position.side.value}_pnl": position.total_pnl,
            }, metadata={"position_id": position_id, "reason": reason})

            self._emit_event("position_closed", position)
            logger.info(f"Position closed: {position_id} - {reason} - PnL: {position.total_pnl:.2f}")

            return True

        except Exception as e:
            logger.error(f"Error closing position {position_id}: {e}")
            return False

    async def close_all_positions(self, reason: str = "manual") -> int:
        """
        Close all open positions.

        Args:
            reason: Close reason

        Returns:
            Number of positions closed
        """
        closed = 0

        for position_id in list(self._open_positions.keys()):
            if await self.close_position(position_id, reason=reason):
                closed += 1

        logger.info(f"Closed {closed} positions")
        return closed

    async def adjust_position(
        self,
        position_id: str,
        quantity_delta: float,
        price: Optional[float] = None,
    ) -> bool:
        """
        Adjust position size.

        Args:
            position_id: Position ID
            quantity_delta: Quantity change
            price: Execution price

        Returns:
            True if adjusted successfully
        """
        position = self._positions.get(position_id)

        if not position:
            logger.warning(f"Position not found: {position_id}")
            return False

        if position.status != PositionStatus.OPEN:
            logger.warning(f"Position already closed: {position_id}")
            return False

        new_quantity = position.quantity + quantity_delta

        if new_quantity <= 0:
            return await self.close_position(position_id)

        # Check limits
        if new_quantity > self._max_position_size:
            logger.warning(f"Position size exceeds max: {new_quantity}")
            return False

        # Execute adjustment order
        order_result = await self.order_executor.execute_order(
            symbol=position.symbol,
            side="buy" if quantity_delta > 0 else "sell",
            order_type="market" if not price else "limit",
            quantity=abs(quantity_delta),
            price=price,
        )

        if not order_result["success"]:
            logger.error(f"Failed to adjust position {position_id}: {order_result.get('error')}")
            return False

        # Update position
        position.quantity = new_quantity
        position.average_entry_price = (
            (position.average_entry_price * position.quantity +
             (price or order_result.get("executed_price", 0)) * abs(quantity_delta)) /
            new_quantity
        )
        position.total_value = new_quantity * position.current_price

        self._emit_event("position_updated", position)
        logger.info(f"Position adjusted: {position_id} - New size: {new_quantity}")

        return True

    # ========================================================================
    # Position PnL Calculation
    # ========================================================================

    async def _update_position_pnl(self, position: Position) -> None:
        """
        Update position PnL.

        Args:
            position: Position
        """
        if position.side == PositionSide.LONG:
            unrealized_pnl = (position.current_price - position.average_entry_price) * position.quantity
        else:
            unrealized_pnl = (position.average_entry_price - position.current_price) * position.quantity

        position.unrealized_pnl = unrealized_pnl
        position.total_pnl = position.realized_pnl + position.unrealized_pnl
        position.pnl_percentage = (position.total_pnl / position.total_value) * 100

    def calculate_pnl(
        self,
        position: Position,
        price: float,
        quantity: Optional[float] = None,
    ) -> Dict[str, float]:
        """
        Calculate PnL for a position.

        Args:
            position: Position
            price: Price
            quantity: Quantity (optional)

        Returns:
            PnL metrics
        """
        qty = quantity or position.quantity

        if position.side == PositionSide.LONG:
            unrealized_pnl = (price - position.average_entry_price) * qty
        else:
            unrealized_pnl = (position.average_entry_price - price) * qty

        total_pnl = position.realized_pnl + unrealized_pnl
        pnl_percentage = (total_pnl / position.total_value) * 100

        return {
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": position.realized_pnl,
            "total_pnl": total_pnl,
            "pnl_percentage": pnl_percentage,
        }

    # ========================================================================
    # Stop Loss / Take Profit
    # ========================================================================

    async def _check_stop_loss(self, position: Position) -> bool:
        """
        Check if stop loss is triggered.

        Args:
            position: Position

        Returns:
            True if stop loss triggered
        """
        if not position.stop_loss_price:
            return False

        if position.side == PositionSide.LONG:
            return position.current_price <= position.stop_loss_price
        else:
            return position.current_price >= position.stop_loss_price

    async def _check_take_profit(self, position: Position) -> bool:
        """
        Check if take profit is triggered.

        Args:
            position: Position

        Returns:
            True if take profit triggered
        """
        if not position.take_profit_price:
            return False

        if position.side == PositionSide.LONG:
            return position.current_price >= position.take_profit_price
        else:
            return position.current_price <= position.take_profit_price

    async def _update_trailing_stop(self, position: Position) -> None:
        """
        Update trailing stop.

        Args:
            position: Position
        """
        if not position.trailing_stop_price:
            return

        if position.side == PositionSide.LONG:
            new_stop = position.current_price * (1 - position.trailing_stop_activation)
            if new_stop > position.trailing_stop_price:
                position.trailing_stop_price = new_stop
                self._emit_event("trailing_stop_updated", position)
        else:
            new_stop = position.current_price * (1 + position.trailing_stop_activation)
            if new_stop < position.trailing_stop_price:
                position.trailing_stop_price = new_stop
                self._emit_event("trailing_stop_updated", position)

    def set_stop_loss(
        self,
        position_id: str,
        stop_loss_price: float,
    ) -> bool:
        """
        Set stop loss for a position.

        Args:
            position_id: Position ID
            stop_loss_price: Stop loss price

        Returns:
            True if set successfully
        """
        position = self._positions.get(position_id)

        if not position:
            logger.warning(f"Position not found: {position_id}")
            return False

        position.stop_loss_price = stop_loss_price
        return True

    def set_take_profit(
        self,
        position_id: str,
        take_profit_price: float,
    ) -> bool:
        """
        Set take profit for a position.

        Args:
            position_id: Position ID
            take_profit_price: Take profit price

        Returns:
            True if set successfully
        """
        position = self._positions.get(position_id)

        if not position:
            logger.warning(f"Position not found: {position_id}")
            return False

        position.take_profit_price = take_profit_price
        return True

    def set_trailing_stop(
        self,
        position_id: str,
        activation_percent: float,
    ) -> bool:
        """
        Set trailing stop for a position.

        Args:
            position_id: Position ID
            activation_percent: Activation percentage

        Returns:
            True if set successfully
        """
        position = self._positions.get(position_id)

        if not position:
            logger.warning(f"Position not found: {position_id}")
            return False

        position.trailing_stop_activation = activation_percent

        if position.side == PositionSide.LONG:
            position.trailing_stop_price = position.current_price * (1 - activation_percent)
        else:
            position.trailing_stop_price = position.current_price * (1 + activation_percent)

        return True

    # ========================================================================
    # Position Limits
    # ========================================================================

    async def _check_position_limits(
        self,
        symbol: str,
        side: PositionSide,
        quantity: float,
    ) -> bool:
        """
        Check position limits.

        Args:
            symbol: Symbol
            side: Position side
            quantity: Quantity

        Returns:
            True if limits are not exceeded
        """
        # Check max positions
        if len(self._open_positions) >= self._max_positions:
            logger.warning(f"Max positions reached: {self._max_positions}")
            return False

        # Check max position size
        if quantity > self._max_position_size:
            logger.warning(f"Position size exceeds max: {quantity} > {self._max_position_size}")
            return False

        # Check per-symbol limit
        symbol_positions = [p for p in self._open_positions.values() if p.symbol == symbol]
        if len(symbol_positions) >= self._position_limits.get("max_positions_per_symbol", 1):
            logger.warning(f"Max positions per symbol reached for {symbol}")
            return False

        return True

    # ========================================================================
    # Position Queries
    # ========================================================================

    def get_position(self, position_id: str) -> Optional[Position]:
        """
        Get position by ID.

        Args:
            position_id: Position ID

        Returns:
            Position or None
        """
        return self._positions.get(position_id)

    def get_positions(
        self,
        symbol: Optional[str] = None,
        status: Optional[PositionStatus] = None,
        side: Optional[PositionSide] = None,
        limit: int = 100,
    ) -> List[Position]:
        """
        Get positions.

        Args:
            symbol: Filter by symbol
            status: Filter by status
            side: Filter by side
            limit: Maximum number

        Returns:
            List of Position
        """
        positions = list(self._positions.values())

        if symbol:
            positions = [p for p in positions if p.symbol == symbol]

        if status:
            positions = [p for p in positions if p.status == status]

        if side:
            positions = [p for p in positions if p.side == side]

        return sorted(positions, key=lambda p: p.open_time, reverse=True)[:limit]

    def get_open_positions(
        self,
        symbol: Optional[str] = None,
        side: Optional[PositionSide] = None,
    ) -> List[Position]:
        """
        Get open positions.

        Args:
            symbol: Filter by symbol
            side: Filter by side

        Returns:
            List of Position
        """
        positions = list(self._open_positions.values())

        if symbol:
            positions = [p for p in positions if p.symbol == symbol]

        if side:
            positions = [p for p in positions if p.side == side]

        return sorted(positions, key=lambda p: p.open_time, reverse=True)

    def get_position_summary(self) -> PositionSummary:
        """
        Get position summary.

        Returns:
            PositionSummary
        """
        all_positions = list(self._positions.values())
        open_positions = list(self._open_positions.values())
        closed_positions = [p for p in all_positions if p.status == PositionStatus.CLOSED]

        total_pnl = sum(p.total_pnl for p in all_positions)
        total_unrealized = sum(p.unrealized_pnl for p in open_positions)
        total_realized = sum(p.realized_pnl for p in closed_positions)

        total_quantity = sum(p.quantity for p in open_positions)
        total_value = sum(p.total_value for p in open_positions)
        total_margin = sum(p.margin_used for p in open_positions)

        win_count = sum(1 for p in closed_positions if p.total_pnl > 0)
        loss_count = sum(1 for p in closed_positions if p.total_pnl < 0)

        win_rate = win_count / (win_count + loss_count) if (win_count + loss_count) > 0 else 0

        avg_leverage = sum(p.leverage for p in open_positions) / len(open_positions) if open_positions else 0

        # Best and worst positions
        best_position = max(closed_positions, key=lambda p: p.total_pnl) if closed_positions else None
        worst_position = min(closed_positions, key=lambda p: p.total_pnl) if closed_positions else None

        # By symbol and side
        by_symbol = defaultdict(int)
        by_side = defaultdict(int)

        for p in open_positions:
            by_symbol[p.symbol] += 1
            by_side[p.side.value] += 1

        return PositionSummary(
            total_positions=len(all_positions),
            open_positions=len(open_positions),
            closed_positions=len(closed_positions),
            total_pnl=total_pnl,
            total_unrealized_pnl=total_unrealized,
            total_realized_pnl=total_realized,
            total_quantity=total_quantity,
            total_value=total_value,
            total_margin=total_margin,
            average_leverage=avg_leverage,
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_rate,
            best_position=best_position,
            worst_position=worst_position,
            by_symbol=dict(by_symbol),
            by_side=dict(by_side),
            timestamp=datetime.utcnow(),
        )

    # ========================================================================
    # Position Performance
    # ========================================================================

    def get_position_performance(self, position_id: str) -> Dict[str, Any]:
        """
        Get position performance metrics.

        Args:
            position_id: Position ID

        Returns:
            Performance metrics
        """
        position = self._positions.get(position_id)

        if not position:
            return {}

        hold_hours = (datetime.utcnow() - position.open_time).total_seconds() / 3600

        return {
            "position_id": position.position_id,
            "symbol": position.symbol,
            "side": position.side.value,
            "entry_price": position.entry_price,
            "current_price": position.current_price,
            "quantity": position.quantity,
            "total_pnl": position.total_pnl,
            "pnl_percentage": position.pnl_percentage,
            "hold_hours": hold_hours,
            "pnl_per_hour": position.total_pnl / hold_hours if hold_hours > 0 else 0,
            "roi": (position.current_price / position.entry_price - 1) * 100,
        }

    def get_aggregated_performance(self) -> Dict[str, Any]:
        """
        Get aggregated performance metrics.

        Returns:
            Aggregated performance
        """
        return {
            "total_pnl": self._performance["total_pnl"],
            "total_positions": self._performance["positions_created"],
            "closed_positions": self._performance["positions_closed"],
            "winning_positions": self._performance["winning_positions"],
            "losing_positions": self._performance["losing_positions"],
            "win_rate": self._performance["winning_positions"] / max(self._performance["positions_closed"], 1),
            "avg_hold_time_hours": self._performance["avg_hold_time"],
            "max_position_size": self._performance["max_position_size"],
            "avg_position_size": self._performance["avg_position_size"],
            "total_volume": self._performance["total_volume"],
        }

    # ========================================================================
    # Risk Management
    # ========================================================================

    def calculate_position_risk(self, position: Position) -> Dict[str, Any]:
        """
        Calculate position risk metrics.

        Args:
            position: Position

        Returns:
            Risk metrics
        """
        risk_amount = position.quantity * position.entry_price
        risk_percent = (risk_amount / position.total_value) * 100

        return {
            "risk_amount": risk_amount,
            "risk_percent": risk_percent,
            "max_loss": risk_amount * 0.02,  # 2% risk
            "max_loss_percent": 2.0,
            "liquidation_distance": abs(position.liquidation_price - position.current_price) if position.liquidation_price else None,
            "liquidation_percent": abs(position.liquidation_price - position.current_price) / position.current_price * 100 if position.liquidation_price else None,
        }

    async def check_risk_limits(self, position: Position) -> bool:
        """
        Check risk limits for position.

        Args:
            position: Position

        Returns:
            True if within limits
        """
        risk = self.calculate_position_risk(position)

        if risk["risk_percent"] > self._position_limits.get("max_risk_percent", 10):
            logger.warning(f"Risk limit exceeded: {risk['risk_percent']}%")
            return False

        if risk["risk_amount"] > self._position_limits.get("max_risk_amount", 10000):
            logger.warning(f"Risk amount limit exceeded: {risk['risk_amount']}")
            return False

        return True

    # ========================================================================
    # Event System
    # ========================================================================

    def on(self, event: str, handler: Callable) -> None:
        """
        Register an event handler.

        Args:
            event: Event name
            handler: Event handler
        """
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    def off(self, event: str, handler: Callable) -> None:
        """
        Remove an event handler.

        Args:
            event: Event name
            handler: Event handler
        """
        if event in self._event_handlers and handler in self._event_handlers[event]:
            self._event_handlers[event].remove(handler)

    def _emit_event(self, event: str, data: Any) -> None:
        """
        Emit an event.

        Args:
            event: Event name
            data: Event data
        """
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")

    # ========================================================================
    # Performance Metrics
    # ========================================================================

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Performance metrics
        """
        return {
            **self._performance,
            "open_positions": len(self._open_positions),
            "total_positions": len(self._positions),
            "position_history": len(self._position_history),
        }

    # ========================================================================
    # Persistence
    # ========================================================================

    async def save_positions(self) -> bool:
        """
        Save positions to storage.

        Returns:
            True if saved successfully
        """
        try:
            data = {
                "positions": [
                    {
                        "position_id": p.position_id,
                        "symbol": p.symbol,
                        "side": p.side.value,
                        "position_type": p.position_type.value,
                        "entry_price": p.entry_price,
                        "current_price": p.current_price,
                        "quantity": p.quantity,
                        "initial_quantity": p.initial_quantity,
                        "average_entry_price": p.average_entry_price,
                        "unrealized_pnl": p.unrealized_pnl,
                        "realized_pnl": p.realized_pnl,
                        "total_pnl": p.total_pnl,
                        "pnl_percentage": p.pnl_percentage,
                        "open_time": p.open_time.isoformat(),
                        "close_time": p.close_time.isoformat() if p.close_time else None,
                        "status": p.status.value,
                        "stop_loss_price": p.stop_loss_price,
                        "take_profit_price": p.take_profit_price,
                        "trailing_stop_price": p.trailing_stop_price,
                        "trailing_stop_activation": p.trailing_stop_activation,
                        "max_quantity": p.max_quantity,
                        "min_quantity": p.min_quantity,
                        "entry_quantity": p.entry_quantity,
                        "exit_quantity": p.exit_quantity,
                        "total_value": p.total_value,
                        "margin_used": p.margin_used,
                        "leverage": p.leverage,
                        "liquidation_price": p.liquidation_price,
                        "collateral": p.collateral,
                        "fees": p.fees,
                        "metadata": p.metadata,
                        "tags": p.tags,
                        "orders": p.orders,
                        "parent_position_id": p.parent_position_id,
                    }
                    for p in self._positions.values()
                ],
                "open_positions": [p.position_id for p in self._open_positions.values()],
            }

            key = f"positions:{datetime.utcnow().isoformat()}"
            return await self.data_storage.save_data(key, data)

        except Exception as e:
            logger.error(f"Error saving positions: {e}")
            return False

    async def load_positions(self) -> bool:
        """
        Load positions from storage.

        Returns:
            True if loaded successfully
        """
        try:
            keys = await self.data_storage.list_keys("positions:*")

            if not keys:
                return True

            latest_key = sorted(keys)[-1]
            data = await self.data_storage.load_data(latest_key)

            if not data:
                return True

            for pos_data in data.get("positions", []):
                position = Position(
                    position_id=pos_data["position_id"],
                    symbol=pos_data["symbol"],
                    side=PositionSide(pos_data["side"]),
                    position_type=PositionType(pos_data["position_type"]),
                    entry_price=pos_data["entry_price"],
                    current_price=pos_data["current_price"],
                    quantity=pos_data["quantity"],
                    initial_quantity=pos_data.get("initial_quantity", pos_data["quantity"]),
                    average_entry_price=pos_data.get("average_entry_price", pos_data["entry_price"]),
                    unrealized_pnl=pos_data.get("unrealized_pnl", 0),
                    realized_pnl=pos_data.get("realized_pnl", 0),
                    total_pnl=pos_data.get("total_pnl", 0),
                    pnl_percentage=pos_data.get("pnl_percentage", 0),
                    open_time=datetime.fromisoformat(pos_data["open_time"]),
                    close_time=datetime.fromisoformat(pos_data["close_time"]) if pos_data.get("close_time") else None,
                    status=PositionStatus(pos_data["status"]),
                    stop_loss_price=pos_data.get("stop_loss_price"),
                    take_profit_price=pos_data.get("take_profit_price"),
                    trailing_stop_price=pos_data.get("trailing_stop_price"),
                    trailing_stop_activation=pos_data.get("trailing_stop_activation"),
                    max_quantity=pos_data.get("max_quantity", 0),
                    min_quantity=pos_data.get("min_quantity", 0),
                    entry_quantity=pos_data.get("entry_quantity", pos_data["quantity"]),
                    exit_quantity=pos_data.get("exit_quantity", 0),
                    total_value=pos_data.get("total_value", 0),
                    margin_used=pos_data.get("margin_used", 0),
                    leverage=pos_data.get("leverage", 1.0),
                    liquidation_price=pos_data.get("liquidation_price"),
                    collateral=pos_data.get("collateral", 0),
                    fees=pos_data.get("fees", 0),
                    metadata=pos_data.get("metadata", {}),
                    tags=pos_data.get("tags", []),
                    orders=pos_data.get("orders", []),
                    parent_position_id=pos_data.get("parent_position_id"),
                )

                self._positions[position.position_id] = position

                if position.status == PositionStatus.OPEN:
                    self._open_positions[position.position_id] = position

                self._position_history.append(position)

            logger.info(f"Loaded {len(self._positions)} positions")
            return True

        except Exception as e:
            logger.error(f"Error loading positions: {e}")
            return False

    # ========================================================================
    # Lifecycle Management
    # ========================================================================

    async def start(self) -> None:
        """Start the position manager."""
        await self.load_positions()
        logger.info("PositionManager started")

    async def stop(self) -> None:
        """Stop the position manager."""
        await self.save_positions()
        logger.info("PositionManager stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_position_manager(
    config: BotConfig,
    risk_manager: RiskManager,
    order_executor: OrderExecutor,
    data_storage: DataStorage,
    metrics_engine: MetricsEngine,
) -> PositionManager:
    """
    Factory function to create a PositionManager instance.

    Args:
        config: Bot configuration
        risk_manager: Risk manager instance
        order_executor: Order executor instance
        data_storage: Data storage instance
        metrics_engine: Metrics engine instance

    Returns:
        PositionManager instance
    """
    return PositionManager(
        config=config,
        risk_manager=risk_manager,
        order_executor=order_executor,
        data_storage=data_storage,
        metrics_engine=metrics_engine,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the position manager
    pass
