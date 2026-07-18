"""
NEXUS AI TRADING SYSTEM - Iceberg Order Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module: trading/smart-orders/iceberg.py
Version: 1.0.0
Description: Advanced iceberg order implementation with full API integration
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable, Tuple
from collections import deque

from pydantic import BaseModel, Field, ConfigDict, validator

from shared.types.trading import OrderSide, OrderType, OrderStatus, TimeInForce
from shared.helpers.trading_helpers import (
    calculate_percentage_change,
    calculate_price_distance,
    round_to_tick_size,
    calculate_volume_weighted_price,
    calculate_vwap
)
from shared.constants.trading_constants import (
    MIN_ORDER_SIZE,
    MAX_ORDER_SPLIT,
    DEFAULT_ICEBERG_DISPLAY_SIZE,
    MAX_ICEBERG_PIECES
)
from shared.interfaces.broker import BrokerInterface
from shared.utilities.logger import get_logger
from shared.utilities.retry import retry_async

from trading.smart_orders.base_order import SmartOrder, SmartOrderConfig
from trading.smart_orders.order_manager import OrderManager

logger = get_logger(__name__)


class IcebergRefreshMode(str, Enum):
    """Iceberg refresh modes"""
    TIME = "time"                      # Refresh on time interval
    VOLUME = "volume"                  # Refresh on volume threshold
    PRICE = "price"                    # Refresh on price movement
    SMART = "smart"                    # Smart refresh based on conditions
    ADAPTIVE = "adaptive"              # Adaptive refresh


class IcebergSizeMode(str, Enum):
    """Iceberg size modes"""
    FIXED = "fixed"                    # Fixed display size
    PERCENTAGE = "percentage"          # Percentage of remaining
    VOLUME_BASED = "volume_based"      # Based on volume profile
    ADAPTIVE = "adaptive"              # Adaptive size


class IcebergPricing(str, Enum):
    """Iceberg pricing strategies"""
    FIXED = "fixed"                    # Fixed price
    MARKET = "market"                  # Market price
    MID = "mid"                        # Mid price
    BEST_BID = "best_bid"              # Best bid
    BEST_ASK = "best_ask"              # Best ask
    VWAP = "vwap"                      # VWAP price
    ADAPTIVE = "adaptive"              # Adaptive pricing


class IcebergPiece(BaseModel):
    """Individual iceberg piece"""
    piece_id: int = Field(..., description="Piece ID")
    size: float = Field(..., description="Piece size")
    price: float = Field(..., description="Piece price")
    order_id: Optional[str] = Field(None, description="Order ID")
    status: OrderStatus = Field(default=OrderStatus.PENDING, description="Piece status")
    filled_size: float = Field(0.0, description="Filled size")
    avg_price: float = Field(0.0, description="Average fill price")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp")
    filled_at: Optional[datetime] = Field(None, description="Fill timestamp")
    attempts: int = Field(0, description="Attempt count")


class IcebergMetrics(BaseModel):
    """Metrics for iceberg order performance"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    total_size: float = Field(0.0, description="Total order size")
    filled_size: float = Field(0.0, description="Total filled size")
    remaining_size: float = Field(0.0, description="Remaining size")
    
    total_pieces: int = Field(0, description="Total number of pieces")
    executed_pieces: int = Field(0, description="Executed pieces")
    failed_pieces: int = Field(0, description="Failed pieces")
    
    avg_execution_price: float = Field(0.0, description="Average execution price")
    total_cost: float = Field(0.0, description="Total cost")
    total_fees: float = Field(0.0, description="Total fees")
    
    avg_piece_size: float = Field(0.0, description="Average piece size")
    avg_piece_time: float = Field(0.0, description="Average time per piece")
    total_execution_time: float = Field(0.0, description="Total execution time")
    
    slippage: float = Field(0.0, description="Total slippage")
    price_improvement: float = Field(0.0, description="Price improvement")
    
    fill_rate: float = Field(0.0, description="Fill rate percentage")
    success_rate: float = Field(0.0, description="Success rate percentage")


class IcebergConfig(SmartOrderConfig):
    """Configuration for iceberg order"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core settings
    symbol: str = Field(..., description="Trading symbol")
    side: OrderSide = Field(..., description="Order side")
    total_size: float = Field(..., description="Total order size")
    
    # Iceberg settings
    display_size: float = Field(DEFAULT_ICEBERG_DISPLAY_SIZE, description="Visible display size")
    min_piece_size: float = Field(MIN_ORDER_SIZE, description="Minimum piece size")
    max_piece_size: float = Field(MAX_ORDER_SPLIT, description="Maximum piece size")
    max_pieces: int = Field(MAX_ICEBERG_PIECES, description="Maximum number of pieces")
    
    # Refresh settings
    refresh_mode: IcebergRefreshMode = Field(default=IcebergRefreshMode.SMART)
    refresh_interval: float = Field(1.0, description="Refresh interval in seconds")
    refresh_volume_threshold: float = Field(1000.0, description="Volume threshold for refresh")
    refresh_price_threshold: float = Field(0.01, description="Price movement threshold")
    
    # Size settings
    size_mode: IcebergSizeMode = Field(default=IcebergSizeMode.ADAPTIVE)
    size_percent: float = Field(10.0, description="Size as percentage of remaining")
    volume_window: int = Field(20, description="Volume window for volume-based sizing")
    
    # Pricing settings
    pricing_strategy: IcebergPricing = Field(default=IcebergPricing.MID)
    price_offset: float = Field(0.0, description="Price offset from strategy")
    max_price_deviation: float = Field(0.05, description="Maximum price deviation")
    
    # Time settings
    start_time: Optional[datetime] = Field(None, description="Start time")
    end_time: Optional[datetime] = Field(None, description="End time")
    time_limit: Optional[float] = Field(None, description="Time limit in seconds")
    
    # Order settings
    order_type: OrderType = Field(default=OrderType.LIMIT)
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    expire_after: Optional[timedelta] = Field(None, description="Expiration time")
    max_slippage: float = Field(0.01, description="Maximum allowed slippage")
    
    # Risk settings
    max_risk_per_piece: float = Field(0.02, description="Maximum risk per piece")
    cancel_on_adverse_move: bool = Field(False, description="Cancel on adverse price move")
    adverse_move_threshold: float = Field(0.02, description="Adverse move threshold")
    
    # Smart features
    adaptive_sizing: bool = Field(True, description="Enable adaptive sizing")
    smart_pricing: bool = Field(True, description="Enable smart pricing")
    volume_aware: bool = Field(True, description="Enable volume awareness")
    market_impact_reduction: bool = Field(True, description="Enable market impact reduction")

    @validator('total_size')
    def validate_total_size(cls, v):
        if v <= 0:
            raise ValueError("Total size must be positive")
        return v

    @validator('display_size')
    def validate_display_size(cls, v, values):
        if 'total_size' in values and v > values['total_size']:
            raise ValueError("Display size cannot exceed total size")
        if v <= 0:
            raise ValueError("Display size must be positive")
        return v

    @validator('max_pieces')
    def validate_max_pieces(cls, v):
        if v < 1:
            raise ValueError("Max pieces must be at least 1")
        return v

    @validator('refresh_interval')
    def validate_refresh_interval(cls, v):
        if v <= 0:
            raise ValueError("Refresh interval must be positive")
        return v

    @validator('size_percent')
    def validate_size_percent(cls, v):
        if v <= 0 or v > 100:
            raise ValueError("Size percent must be between 0 and 100")
        return v

    @validator('max_price_deviation')
    def validate_price_deviation(cls, v):
        if v < 0:
            raise ValueError("Max price deviation must be non-negative")
        return v


class IcebergOrder(SmartOrder):
    """
    Advanced iceberg order implementation with full API integration.
    
    Features:
    - Hidden order size (only display size visible)
    - Multiple refresh modes (time, volume, price, smart, adaptive)
    - Adaptive sizing based on market conditions
    - Smart pricing strategies
    - Volume awareness
    - Market impact reduction
    - Full broker API integration
    - Performance metrics tracking
    - Real-time monitoring
    """

    def __init__(
        self,
        config: IcebergConfig,
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ):
        """
        Initialize iceberg order.

        Args:
            config: Iceberg configuration
            broker: Optional broker interface
            order_manager: Optional order manager
        """
        super().__init__(config=config, broker=broker, order_manager=order_manager)
        self.config = config
        self._metrics = IcebergMetrics()
        self._state = 'INACTIVE'
        self._current_price: Optional[float] = None
        self._pieces: List[IcebergPiece] = []
        self._active_piece_index: int = -1
        self._filled_size: float = 0.0
        self._remaining_size: float = 0.0
        self._total_cost: float = 0.0
        self._total_fees: float = 0.0
        self._last_refresh_time: datetime = datetime.utcnow()
        self._piece_times: deque = deque(maxlen=100)
        self._subscription_id: Optional[str] = None

        # Price history for smart features
        self._price_history: List[float] = []
        self._volume_history: List[float] = []
        self._timestamp_history: List[datetime] = []
        self._max_history_length = 1000
        
        # Market data
        self._bid_price: Optional[float] = None
        self._ask_price: Optional[float] = None
        self._mid_price: Optional[float] = None
        self._volume_profile: Dict[str, float] = {}
        self._vwap_price: Optional[float] = None

        # Control flags
        self._running: bool = False
        self._refresh_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Locks
        self._piece_lock = asyncio.Lock()
        self._price_lock = asyncio.Lock()

        logger.info(f"Initialized IcebergOrder with ID: {self.id}, size: {config.total_size}")

    async def activate(self, price: Optional[float] = None) -> bool:
        """
        Activate the iceberg order.

        Args:
            price: Optional initial price

        Returns:
            bool: True if activated successfully
        """
        async with self._piece_lock:
            if self._state in ['ACTIVE', 'EXECUTED']:
                logger.warning(f"Iceberg order {self.id} already active or executed")
                return False

            self._current_price = price or self._current_price

            # Initialize metrics
            self._metrics.total_size = self.config.total_size
            self._remaining_size = self.config.total_size
            self._filled_size = 0.0

            # Set initial price
            if self._current_price is None:
                self._current_price = await self._get_market_price()

            # Generate initial pieces
            await self._generate_pieces()

            if not self._pieces:
                logger.error(f"No iceberg pieces generated for {self.id}")
                return False

            # Submit first piece
            self._state = 'ACTIVE'
            await self._submit_next_piece()

            # Start refresh task
            self._running = True
            self._refresh_task = asyncio.create_task(self._refresh_loop())
            self._monitor_task = asyncio.create_task(self._monitor_order())

            logger.info(
                f"Iceberg order {self.id} activated, "
                f"total: {self.config.total_size}, "
                f"display: {self.config.display_size}"
            )

            return True

    async def update_price(self, new_price: float, timestamp: Optional[datetime] = None) -> bool:
        """
        Update current price.

        Args:
            new_price: Current market price
            timestamp: Optional timestamp

        Returns:
            bool: True if updated
        """
        async with self._price_lock:
            self._current_price = new_price

            # Update price history
            self._price_history.append(new_price)
            self._timestamp_history.append(timestamp or datetime.utcnow())
            if len(self._price_history) > self._max_history_length:
                self._price_history.pop(0)
                self._timestamp_history.pop(0)

            # Update VWAP
            if len(self._price_history) > 0:
                self._vwap_price = calculate_vwap(self._price_history, self._volume_history)

            # Check for adverse move
            if self.config.cancel_on_adverse_move:
                await self._check_adverse_move(new_price)

            return True

    async def check_conditions(self, price: Optional[float] = None) -> bool:
        """
        Check if conditions are met.

        Args:
            price: Current price

        Returns:
            bool: True if conditions met
        """
        if self._state != 'ACTIVE':
            return False

        # Check time limit
        if self.config.time_limit:
            elapsed = (datetime.utcnow() - self._last_refresh_time).total_seconds()
            if elapsed > self.config.time_limit:
                await self.cancel()
                return False

        # Check expiration
        if self.config.expire_after:
            created = getattr(self, 'created_at', datetime.utcnow())
            if datetime.utcnow() - created > self.config.expire_after:
                await self.cancel()
                return False

        return True

    async def cancel(self) -> bool:
        """
        Cancel the iceberg order.

        Returns:
            bool: True if cancelled successfully
        """
        async with self._piece_lock:
            if self._state in ['CANCELLED', 'EXECUTED']:
                return False

            self._state = 'CANCELLED'
            self._running = False

            # Cancel refresh and monitor tasks
            if self._refresh_task:
                self._refresh_task.cancel()
            if self._monitor_task:
                self._monitor_task.cancel()

            # Cancel all active pieces
            for piece in self._pieces:
                if piece.order_id and piece.status not in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
                    try:
                        await self._broker.cancel_order(piece.order_id)
                        logger.debug(f"Cancelled piece {piece.piece_id}")
                    except Exception as e:
                        logger.error(f"Failed to cancel piece {piece.piece_id}: {e}")

            logger.info(f"Iceberg order {self.id} cancelled")
            return True

    async def get_metrics(self) -> IcebergMetrics:
        """Get current metrics"""
        async with self._piece_lock:
            return self._metrics.model_copy()

    def get_state(self) -> str:
        """Get current state"""
        return self._state

    def get_filled_size(self) -> float:
        """Get filled size"""
        return self._filled_size

    def get_remaining_size(self) -> float:
        """Get remaining size"""
        return self._remaining_size

    def get_active_piece(self) -> Optional[IcebergPiece]:
        """Get active piece"""
        if self._active_piece_index >= 0 and self._active_piece_index < len(self._pieces):
            return self._pieces[self._active_piece_index]
        return None

    async def get_pieces(self) -> List[IcebergPiece]:
        """Get all pieces"""
        return self._pieces.copy()

    async def _generate_pieces(self):
        """Generate iceberg pieces"""
        remaining = self.config.total_size
        piece_id = 0

        while remaining > 0 and piece_id < self.config.max_pieces:
            # Calculate piece size
            piece_size = await self._calculate_piece_size(remaining, piece_id)

            # Calculate piece price
            piece_price = await self._calculate_piece_price(piece_id)

            piece = IcebergPiece(
                piece_id=piece_id,
                size=piece_size,
                price=piece_price,
                status=OrderStatus.PENDING
            )
            self._pieces.append(piece)

            remaining -= piece_size
            piece_id += 1

        logger.debug(f"Generated {len(self._pieces)} iceberg pieces")

    async def _calculate_piece_size(self, remaining: float, piece_index: int) -> float:
        """Calculate piece size based on strategy"""
        if self.config.size_mode == IcebergSizeMode.FIXED:
            size = min(self.config.display_size, remaining)

        elif self.config.size_mode == IcebergSizeMode.PERCENTAGE:
            size = min(remaining * (self.config.size_percent / 100), self.config.display_size)

        elif self.config.size_mode == IcebergSizeMode.VOLUME_BASED:
            volume_avg = await self._get_average_volume()
            size = min(volume_avg * 0.1, remaining)  # 10% of average volume
            size = max(size, self.config.min_piece_size)

        elif self.config.size_mode == IcebergSizeMode.ADAPTIVE:
            if self.config.adaptive_sizing:
                # Adaptive sizing based on market conditions
                volatility = await self._calculate_volatility()
                spread = await self._get_current_spread()
                volume = await self._get_average_volume()

                # Smaller pieces in high volatility
                volatility_factor = 1 / (1 + volatility * 10)
                spread_factor = 1 / (1 + spread * 10)
                volume_factor = min(1, volume / 1000)

                adaptive_size = self.config.display_size * volatility_factor * spread_factor * volume_factor
                size = min(max(adaptive_size, self.config.min_piece_size), remaining)
            else:
                size = min(self.config.display_size, remaining)

        else:
            size = min(self.config.display_size, remaining)

        # Apply limits
        size = max(size, self.config.min_piece_size)
        size = min(size, self.config.max_piece_size)
        size = min(size, remaining)

        return round_to_tick_size(size)

    async def _calculate_piece_price(self, piece_index: int) -> float:
        """Calculate piece price based on strategy"""
        if self._current_price is None:
            self._current_price = await self._get_market_price()

        base_price = self._current_price

        if self.config.pricing_strategy == IcebergPricing.FIXED:
            price = self.config.price_offset

        elif self.config.pricing_strategy == IcebergPricing.MARKET:
            price = self._current_price

        elif self.config.pricing_strategy == IcebergPricing.MID:
            if self._mid_price:
                price = self._mid_price
            else:
                price = self._current_price

        elif self.config.pricing_strategy == IcebergPricing.BEST_BID:
            if self._bid_price:
                price = self._bid_price
            else:
                price = self._current_price * 0.999

        elif self.config.pricing_strategy == IcebergPricing.BEST_ASK:
            if self._ask_price:
                price = self._ask_price
            else:
                price = self._current_price * 1.001

        elif self.config.pricing_strategy == IcebergPricing.VWAP:
            if self._vwap_price:
                price = self._vwap_price
            else:
                price = self._current_price

        elif self.config.pricing_strategy == IcebergPricing.ADAPTIVE:
            if self.config.smart_pricing:
                # Adaptive pricing based on conditions
                volatility = await self._calculate_volatility()
                direction = 1 if self.config.side == OrderSide.BUY else -1
                adaptive_offset = self.config.price_offset * (1 + volatility * 5)
                price = base_price + (direction * adaptive_offset)
            else:
                price = base_price

        else:
            price = base_price

        # Apply price offset
        if self.config.side == OrderSide.BUY:
            price = price - self.config.price_offset
        else:
            price = price + self.config.price_offset

        # Check max deviation
        if abs(price - base_price) / base_price > self.config.max_price_deviation:
            if self.config.side == OrderSide.BUY:
                price = base_price * (1 - self.config.max_price_deviation)
            else:
                price = base_price * (1 + self.config.max_price_deviation)

        return round_to_tick_size(price)

    async def _submit_next_piece(self):
        """Submit the next iceberg piece"""
        if self._state != 'ACTIVE':
            return

        # Find next pending piece
        next_piece_index = -1
        for i, piece in enumerate(self._pieces):
            if piece.status == OrderStatus.PENDING:
                next_piece_index = i
                break

        if next_piece_index == -1:
            # No more pieces
            if self._filled_size >= self.config.total_size * 0.99:
                self._state = 'EXECUTED'
                logger.info(f"Iceberg order {self.id} fully executed")
            return

        piece = self._pieces[next_piece_index]

        try:
            # Update piece price if needed
            if self.config.smart_pricing and len(self._price_history) > 0:
                piece.price = await self._calculate_piece_price(next_piece_index)

            # Submit order
            order_params = {
                'symbol': self.config.symbol,
                'side': self.config.side,
                'quantity': piece.size,
                'order_type': self.config.order_type,
                'price': piece.price,
                'time_in_force': self.config.time_in_force,
                'client_order_id': f"{self.id}_{piece.piece_id}"
            }

            if self.config.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                order_params['stop_price'] = piece.price

            result = await self._broker.place_order(**order_params)

            piece.order_id = result.get('order_id')
            piece.status = OrderStatus.PENDING
            piece.attempts += 1
            piece.timestamp = datetime.utcnow()

            self._active_piece_index = next_piece_index

            logger.debug(f"Submitted iceberg piece {piece.piece_id} at {piece.price}")

        except Exception as e:
            logger.error(f"Failed to submit piece {piece.piece_id}: {e}")
            piece.status = OrderStatus.REJECTED
            piece.attempts += 1

            # Retry with backoff
            if piece.attempts < 3:
                await asyncio.sleep(0.5 * piece.attempts)
                await self._submit_next_piece()

    async def _monitor_order(self):
        """Monitor active pieces"""
        while self._running and self._state == 'ACTIVE':
            try:
                async with self._piece_lock:
                    # Check active piece
                    active_piece = self.get_active_piece()
                    if active_piece and active_piece.order_id:
                        status = await self._broker.get_order_status(active_piece.order_id)
                        
                        if status.get('status') in ['FILLED', 'PARTIALLY_FILLED']:
                            filled_size = status.get('filled_quantity', active_piece.size)
                            avg_price = status.get('price', active_piece.price)

                            # Update piece
                            active_piece.filled_size = filled_size
                            active_piece.avg_price = avg_price
                            active_piece.filled_at = datetime.utcnow()

                            if filled_size >= active_piece.size * 0.99:
                                active_piece.status = OrderStatus.FILLED
                            else:
                                active_piece.status = OrderStatus.PARTIALLY_FILLED

                            # Update metrics
                            self._filled_size += filled_size
                            self._remaining_size -= filled_size
                            self._total_cost += filled_size * avg_price

                            # Update piece times
                            piece_time = (active_piece.filled_at - active_piece.timestamp).total_seconds()
                            self._piece_times.append(piece_time)

                            # Submit next piece
                            if self._remaining_size > 0:
                                await self._submit_next_piece()
                            else:
                                self._state = 'EXECUTED'
                                logger.info(f"Iceberg order {self.id} fully executed")

                        elif status.get('status') in ['CANCELLED', 'REJECTED', 'EXPIRED']:
                            # Piece failed, retry
                            active_piece.status = OrderStatus(status.get('status'))
                            await self._submit_next_piece()

                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring order: {e}")
                await asyncio.sleep(1)

    async def _refresh_loop(self):
        """Refresh iceberg pieces"""
        while self._running and self._state == 'ACTIVE':
            try:
                await asyncio.sleep(self.config.refresh_interval)

                # Check if refresh needed
                if await self._should_refresh():
                    await self._refresh_order()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in refresh loop: {e}")

    async def _should_refresh(self) -> bool:
        """Check if iceberg should be refreshed"""
        if not self._pieces:
            return False

        active_piece = self.get_active_piece()
        if not active_piece or active_piece.status != OrderStatus.PENDING:
            return False

        current_time = datetime.utcnow()
        elapsed = (current_time - self._last_refresh_time).total_seconds()

        if self.config.refresh_mode == IcebergRefreshMode.TIME:
            return elapsed >= self.config.refresh_interval

        elif self.config.refresh_mode == IcebergRefreshMode.VOLUME:
            volume_since_refresh = await self._get_volume_since(self._last_refresh_time)
            return volume_since_refresh >= self.config.refresh_volume_threshold

        elif self.config.refresh_mode == IcebergRefreshMode.PRICE:
            if self._current_price is None:
                return False
            price_change = abs((self._current_price - active_piece.price) / active_piece.price)
            return price_change >= self.config.refresh_price_threshold

        elif self.config.refresh_mode == IcebergRefreshMode.SMART:
            # Smart refresh based on multiple conditions
            if elapsed >= self.config.refresh_interval * 2:
                return True

            volume_since_refresh = await self._get_volume_since(self._last_refresh_time)
            if volume_since_refresh >= self.config.refresh_volume_threshold:
                return True

            if self._current_price:
                price_change = abs((self._current_price - active_piece.price) / active_piece.price)
                if price_change >= self.config.refresh_price_threshold * 0.5:
                    return True

            return False

        elif self.config.refresh_mode == IcebergRefreshMode.ADAPTIVE:
            # Adaptive refresh based on market conditions
            volatility = await self._calculate_volatility()
            spread = await self._get_current_spread()
            volume = await self._get_average_volume()

            # Adjust refresh rate based on conditions
            if volatility > 0.02 or spread > 0.002:
                # High volatility or spread: refresh more frequently
                return elapsed >= self.config.refresh_interval * 0.5
            elif volume > 10000:
                # High volume: refresh faster
                return elapsed >= self.config.refresh_interval * 0.7
            else:
                return elapsed >= self.config.refresh_interval

        return elapsed >= self.config.refresh_interval

    async def _refresh_order(self):
        """Refresh the current iceberg piece"""
        async with self._piece_lock:
            active_piece = self.get_active_piece()
            if not active_piece or active_piece.status != OrderStatus.PENDING:
                return

            try:
                # Cancel current piece if it's still pending
                if active_piece.order_id:
                    await self._broker.cancel_order(active_piece.order_id)
                    logger.debug(f"Cancelled piece {active_piece.piece_id} for refresh")

                # Update piece status
                active_piece.status = OrderStatus.CANCELLED

                # Recalculate piece price
                active_piece.price = await self._calculate_piece_price(active_piece.piece_id)
                active_piece.timestamp = datetime.utcnow()
                active_piece.status = OrderStatus.PENDING

                # Resubmit
                await self._submit_next_piece()
                self._last_refresh_time = datetime.utcnow()

                logger.debug(f"Refreshed iceberg piece {active_piece.piece_id}")

            except Exception as e:
                logger.error(f"Failed to refresh piece: {e}")

    async def _check_adverse_move(self, current_price: float):
        """Check for adverse price move"""
        if self._filled_size == 0:
            return

        avg_price = self._metrics.avg_execution_price
        if avg_price == 0:
            return

        if self.config.side == OrderSide.BUY:
            adverse_move = (current_price - avg_price) / avg_price
            if adverse_move < -self.config.adverse_move_threshold:
                logger.warning(f"Adverse move detected: {adverse_move:.2%}")
                await self.cancel()

        else:
            adverse_move = (avg_price - current_price) / avg_price
            if adverse_move < -self.config.adverse_move_threshold:
                logger.warning(f"Adverse move detected: {adverse_move:.2%}")
                await self.cancel()

    async def _update_metrics(self):
        """Update metrics"""
        self._metrics.filled_size = self._filled_size
        self._metrics.remaining_size = self._remaining_size
        self._metrics.total_cost = self._total_cost
        self._metrics.total_fees = self._total_fees

        if self._filled_size > 0:
            self._metrics.avg_execution_price = self._total_cost / self._filled_size

        if self.config.total_size > 0:
            self._metrics.fill_rate = (self._filled_size / self.config.total_size) * 100

        if len(self._pieces) > 0:
            executed = sum(1 for p in self._pieces if p.status == OrderStatus.FILLED)
            failed = sum(1 for p in self._pieces if p.status == OrderStatus.REJECTED)
            self._metrics.executed_pieces = executed
            self._metrics.failed_pieces = failed
            self._metrics.success_rate = (executed / len(self._pieces)) * 100 if self._pieces else 0
            self._metrics.avg_piece_size = self._filled_size / executed if executed > 0 else 0

        if self._piece_times:
            self._metrics.avg_piece_time = sum(self._piece_times) / len(self._piece_times)
            self._metrics.total_execution_time = sum(self._piece_times)

        # Calculate slippage
        if self._metrics.avg_execution_price and self._current_price:
            self._metrics.slippage = abs(self._metrics.avg_execution_price - self._current_price) / self._current_price * 100

    async def _get_market_price(self) -> float:
        """Get current market price"""
        if self._current_price:
            return self._current_price

        # Try to get from broker
        try:
            ticker = await self._broker.get_ticker(self.config.symbol)
            if ticker:
                self._bid_price = ticker.get('bid')
                self._ask_price = ticker.get('ask')
                self._mid_price = (self._bid_price + self._ask_price) / 2 if self._bid_price and self._ask_price else None
                return ticker.get('last') or ticker.get('price') or 100.0
        except Exception as e:
            logger.error(f"Failed to get market price: {e}")

        return 100.0  # Fallback

    async def _get_average_volume(self) -> float:
        """Get average volume"""
        if self._volume_history:
            return sum(self._volume_history) / len(self._volume_history)
        return 1000.0

    async def _get_volume_since(self, since: datetime) -> float:
        """Get volume since timestamp"""
        # Simplified - would use actual volume data in production
        return 100.0

    async def _get_current_spread(self) -> float:
        """Get current spread"""
        if self._bid_price and self._ask_price:
            return (self._ask_price - self._bid_price) / self._mid_price if self._mid_price else 0.001
        return 0.001

    async def _calculate_volatility(self) -> float:
        """Calculate current volatility"""
        if len(self._price_history) < 20:
            return 0.01

        returns = []
        for i in range(1, 20):
            if self._price_history[-i-1] != 0:
                returns.append((self._price_history[-i] - self._price_history[-i-1]) / self._price_history[-i-1])

        if not returns:
            return 0.01

        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return variance ** 0.5

    async def register_price_feed(self, callback: Callable[[float], Awaitable[None]]):
        """Register price feed callback"""
        self._price_callback = callback

    async def start_price_monitoring(self, websocket_client: Optional[Any] = None):
        """Start price monitoring"""
        if websocket_client and not self._subscription_id:
            try:
                self._subscription_id = await websocket_client.subscribe(
                    channel='ticker',
                    symbol=self.config.symbol,
                    callback=self._handle_websocket_price
                )
                logger.info(f"Started WebSocket price monitoring for {self.config.symbol}")
            except Exception as e:
                logger.error(f"Failed to start price monitoring: {e}")

    async def _handle_websocket_price(self, data: Dict[str, Any]):
        """Handle WebSocket price updates"""
        if 'price' in data:
            await self.update_price(data['price'])
            if 'volume' in data:
                self._volume_history.append(data['volume'])
                if len(self._volume_history) > self._max_history_length:
                    self._volume_history.pop(0)

            if 'bid' in data:
                self._bid_price = data['bid']
            if 'ask' in data:
                self._ask_price = data['ask']
            if self._bid_price and self._ask_price:
                self._mid_price = (self._bid_price + self._ask_price) / 2

    async def stop_price_monitoring(self):
        """Stop price monitoring"""
        if self._subscription_id and self._broker:
            try:
                if hasattr(self._broker, 'unsubscribe'):
                    await self._broker.unsubscribe(self._subscription_id)
                self._subscription_id = None
                logger.info("Stopped price monitoring")
            except Exception as e:
                logger.error(f"Failed to stop price monitoring: {e}")

    async def to_dict(self) -> Dict[str, Any]:
        """Convert iceberg order to dictionary"""
        return {
            'id': self.id,
            'state': self._state,
            'config': self.config.model_dump(),
            'metrics': self._metrics.model_dump(),
            'current_price': self._current_price,
            'pieces': [piece.model_dump() for piece in self._pieces],
            'active_piece_index': self._active_piece_index,
            'filled_size': self._filled_size,
            'remaining_size': self._remaining_size,
            'total_cost': self._total_cost,
            'total_fees': self._total_fees,
            'last_refresh_time': self._last_refresh_time
        }

    @classmethod
    async def from_dict(
        cls,
        data: Dict[str, Any],
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional[OrderManager] = None
    ) -> 'IcebergOrder':
        """Create iceberg order from dictionary"""
        config = IcebergConfig(**data.get('config', {}))
        iceberg_order = cls(config=config, broker=broker, order_manager=order_manager)

        # Restore state
        iceberg_order._state = data.get('state', 'INACTIVE')
        iceberg_order._current_price = data.get('current_price')
        iceberg_order._filled_size = data.get('filled_size', 0)
        iceberg_order._remaining_size = data.get('remaining_size', 0)
        iceberg_order._total_cost = data.get('total_cost', 0)
        iceberg_order._total_fees = data.get('total_fees', 0)
        iceberg_order._active_piece_index = data.get('active_piece_index', -1)

        if data.get('last_refresh_time'):
            iceberg_order._last_refresh_time = data.get('last_refresh_time')

        # Restore pieces
        if data.get('pieces'):
            iceberg_order._pieces = [IcebergPiece(**piece) for piece in data.get('pieces')]

        # Restore metrics
        if data.get('metrics'):
            iceberg_order._metrics = IcebergMetrics(**data.get('metrics'))

        return iceberg_order

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cancel()
        await self.stop_price_monitoring()
