# trading/smart-orders/vwap.py
"""
NEXUS AI TRADING SYSTEM - VWAP Order Execution
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements Volume-Weighted Average Price (VWAP) order execution
strategies for algorithmic trading. VWAP execution aims to execute orders
at prices close to the VWAP of the trading session by intelligently
slicing orders based on historical and real-time volume profiles.

Key Features:
- VWAP order execution with multiple slicing strategies
- Real-time volume profile tracking
- Adaptive execution based on market conditions
- Participation rate control
- Price benchmark tracking
- Performance analytics
"""

import asyncio
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from collections import deque

import numpy as np

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType, TimeInForce
from shared.types.trading import Order, Trade, MarketData, OrderBook
from .base import SmartOrderBase, SmartOrderConfig, SmartOrderType, OrderSlice

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class VWAPExecutionStyle(str, Enum):
    """VWAP execution styles"""
    STANDARD = "standard"          # Standard VWAP slicing
    AGGRESSIVE = "aggressive"      # More aggressive participation
    PASSIVE = "passive"            # More passive participation
    ADAPTIVE = "adaptive"          # Adapts to market conditions
    HIDDEN = "hidden"              # Hidden order execution
    ICEBERG = "iceberg"            # Iceberg-style execution


class VolumeProfileType(str, Enum):
    """Types of volume profiles"""
    HISTORICAL = "historical"      # Historical average volume profile
    REAL_TIME = "real_time"        # Real-time volume profile
    HYBRID = "hybrid"              # Combination of historical and real-time
    PREDICTIVE = "predictive"      # ML-based predictive volume profile


@dataclass
class VWAPConfig(SmartOrderConfig):
    """Configuration for VWAP execution"""
    # Execution parameters
    execution_style: VWAPExecutionStyle = VWAPExecutionStyle.STANDARD
    volume_profile_type: VolumeProfileType = VolumeProfileType.HYBRID
    
    # VWAP parameters
    vwap_period: int = 390  # Number of periods in a trading day
    vwap_lookback: int = 20  # Days for historical VWAP calculation
    
    # Slicing parameters
    slice_interval: int = 5  # Minutes between slices
    min_slice_size: float = 10.0
    max_slice_size: float = 10000.0
    participation_rate: float = 0.10  # Maximum participation rate
    
    # Urgency parameters
    urgency: float = 0.5  # 0-1, higher = more urgent
    urgency_threshold: float = 0.3  # Minimum urgency to execute
    
    # Price parameters
    price_tolerance: float = 0.005  # 0.5% tolerance from VWAP
    max_price_deviation: float = 0.02  # 2% max deviation
    
    # Market impact parameters
    market_impact_model: str = "linear"
    impact_coefficient: float = 0.001
    urgency_impact_multiplier: float = 1.5
    
    # Historical volume profile
    historical_volume_window: int = 20  # Days
    volume_profile_path: Optional[str] = None
    
    # Execution limits
    max_execution_time: int = 3600  # 1 hour
    min_execution_time: int = 60   # 1 minute
    pause_on_adverse_movement: bool = True
    adverse_movement_threshold: float = 0.01  # 1%


@dataclass
class VWAPState:
    """State of VWAP execution"""
    order_id: str
    symbol: str
    side: OrderSide
    total_quantity: float
    remaining_quantity: float
    filled_quantity: float = 0.0
    average_price: float = 0.0
    
    # VWAP tracking
    current_vwap: float = 0.0
    target_vwap: float = 0.0
    vwap_deviation: float = 0.0
    
    # Volume profile
    volume_profile: Dict[int, float] = field(default_factory=dict)
    realized_volume: Dict[int, float] = field(default_factory=dict)
    projected_volume: float = 0.0
    
    # Slicing
    slices: List[OrderSlice] = field(default_factory=list)
    current_slice_index: int = 0
    slice_size: float = 0.0
    slice_interval_seconds: int = 300  # 5 minutes
    
    # Performance
    total_trades: int = 0
    successful_slices: int = 0
    failed_slices: int = 0
    execution_cost: float = 0.0
    implementation_shortfall: float = 0.0
    participation_rate_actual: float = 0.0
    
    # Timing
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_slice_time: datetime = field(default_factory=datetime.utcnow)
    estimated_completion_time: Optional[datetime] = None
    elapsed_seconds: float = 0.0
    
    # Market conditions
    market_volatility: float = 0.0
    current_participation_rate: float = 0.0
    is_paused: bool = False
    pause_reason: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# VWAP EXECUTION ENGINE
# ============================================================================

class VWAPExecutionEngine(SmartOrderBase):
    """
    VWAP (Volume-Weighted Average Price) execution engine.
    
    Implements VWAP order execution with intelligent slicing based on
    volume profiles and market conditions.
    """
    
    def __init__(self, config: Optional[VWAPConfig] = None):
        """
        Initialize the VWAP execution engine.
        
        Args:
            config: VWAP configuration
        """
        super().__init__(config or VWAPConfig())
        self.config = config or VWAPConfig()
        self.smart_type = SmartOrderType.VWAP
        
        # State management
        self._active_states: Dict[str, VWAPState] = {}
        self._completed_orders: List[VWAPState] = []
        
        # Historical data
        self._historical_volume_profile: Optional[Dict[int, float]] = None
        self._historical_vwap: float = 0.0
        
        # Real-time tracking
        self._price_history: deque = deque(maxlen=1000)
        self._volume_history: deque = deque(maxlen=1000)
        self._vwap_history: deque = deque(maxlen=1000)
        
        # Volume profile for current session
        self._session_volume_profile: Dict[int, float] = {}
        self._session_start_time: Optional[datetime] = None
        
        # Timer for slice execution
        self._slice_task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        
        self.logger = logger
    
    # ========================================================================
    # ORDER EXECUTION
    # ========================================================================
    
    async def execute_order(self, order: Order) -> Tuple[bool, List[Trade]]:
        """
        Execute an order using VWAP strategy.
        
        Args:
            order: Order to execute
            
        Returns:
            Tuple[bool, List[Trade]]: Success status and list of executed trades
        """
        # Validate order
        if not self._validate_order(order):
            return False, []
        
        # Create VWAP state
        state = VWAPState(
            order_id=order.order_id or self._generate_order_id(),
            symbol=order.symbol,
            side=order.side,
            total_quantity=order.quantity,
            remaining_quantity=order.quantity,
            slice_interval_seconds=self.config.slice_interval * 60,
        )
        
        # Load volume profile
        if self.config.volume_profile_type in [
            VolumeProfileType.HISTORICAL,
            VolumeProfileType.HYBRID,
        ]:
            await self._load_historical_volume_profile(order.symbol)
        
        # Initialize volume profile for current session
        self._session_start_time = datetime.utcnow()
        self._session_volume_profile = {}
        
        # Calculate initial VWAP target
        state.target_vwap = await self._calculate_target_vwap(order.symbol)
        state.current_vwap = state.target_vwap
        
        # Calculate slice size
        state.slice_size = self._calculate_initial_slice_size(state)
        
        # Store state
        self._active_states[state.order_id] = state
        
        # Start execution
        self._is_running = True
        self._slice_task = asyncio.create_task(self._execute_slices(state))
        
        # Wait for completion or timeout
        try:
            await asyncio.wait_for(
                self._slice_task,
                timeout=self.config.max_execution_time,
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"VWAP execution timed out for order {state.order_id}")
            state.metadata["timeout"] = True
        
        # Return results
        success = state.remaining_quantity < 0.001
        
        # Build trades list
        trades = []
        for slice_info in state.slices:
            if slice_info.trades:
                trades.extend(slice_info.trades)
        
        return success, trades
    
    async def _execute_slices(self, state: VWAPState) -> None:
        """
        Execute VWAP slices over time.
        
        Args:
            state: VWAP state
        """
        while state.remaining_quantity > 0.001 and self._is_running:
            try:
                # Check if paused
                if state.is_paused:
                    await self._check_resume(state)
                    continue
                
                # Update market conditions
                await self._update_market_conditions(state)
                
                # Calculate slice size
                slice_size = self._calculate_slice_size(state)
                
                if slice_size < self.config.min_slice_size:
                    # Place remaining as market order
                    slice_size = state.remaining_quantity
                
                # Execute slice
                slice_result = await self._execute_slice(state, slice_size)
                
                # Process slice result
                state.current_slice_index += 1
                
                if slice_result:
                    state.successful_slices += 1
                else:
                    state.failed_slices += 1
                
                # Update estimated completion time
                self._update_completion_estimate(state)
                
                # Wait for next slice
                await asyncio.sleep(state.slice_interval_seconds)
                
            except asyncio.CancelledError:
                self.logger.info(f"Slice execution cancelled for order {state.order_id}")
                break
            except Exception as e:
                self.logger.error(f"Error executing slice for {state.order_id}: {e}")
                await asyncio.sleep(5)
    
    async def _execute_slice(self, state: VWAPState, quantity: float) -> bool:
        """
        Execute a single slice.
        
        Args:
            state: VWAP state
            quantity: Quantity to execute
            
        Returns:
            bool: True if slice was executed successfully
        """
        # Calculate slice price
        price = await self._calculate_slice_price(state)
        
        if price is None:
            return False
        
        # Create slice order
        slice_order = Order(
            symbol=state.symbol,
            side=state.side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=price,
            time_in_force=TimeInForce.IOC,
            client_order_id=f"vwap_slice_{state.order_id}_{state.current_slice_index}",
        )
        
        # Record slice
        slice_info = OrderSlice(
            order_id=slice_order.order_id or slice_order.client_order_id,
            quantity=quantity,
            price=price,
            side=state.side,
            order_type=OrderType.LIMIT,
            time=datetime.utcnow(),
            status="pending",
        )
        state.slices.append(slice_info)
        
        try:
            # Execute slice (this would call the broker)
            # For now, simulate execution
            executed = await self._simulate_slice_execution(slice_order)
            
            if executed:
                # Update state
                state.filled_quantity += quantity
                state.remaining_quantity -= quantity
                state.total_trades += 1
                
                # Update average price
                state.average_price = (
                    (state.average_price * (state.filled_quantity - quantity) + price * quantity)
                    / max(state.filled_quantity, 0.001)
                )
                
                # Record trade
                trade = Trade(
                    symbol=state.symbol,
                    side=state.side,
                    quantity=quantity,
                    price=price,
                    timestamp=datetime.utcnow(),
                )
                slice_info.trades = [trade]
                slice_info.status = "filled"
                
                # Update VWAP
                await self._update_vwap(state, price, quantity)
                
                self.logger.info(
                    f"VWAP slice executed: {quantity:.2f} @ {price:.4f} "
                    f"({state.filled_quantity:.2f}/{state.total_quantity:.2f})"
                )
                return True
            else:
                slice_info.status = "failed"
                return False
                
        except Exception as e:
            self.logger.error(f"Error executing slice: {e}")
            slice_info.status = "failed"
            return False
    
    # ========================================================================
    # SLICE SIZE CALCULATIONS
    # ========================================================================
    
    def _calculate_initial_slice_size(self, state: VWAPState) -> float:
        """
        Calculate initial slice size.
        
        Args:
            state: VWAP state
            
        Returns:
            float: Initial slice size
        """
        total = state.total_quantity
        intervals = self.config.vwap_period // (self.config.slice_interval or 5)
        
        # Base slice size
        base_size = total / max(intervals, 1)
        
        # Adjust based on urgency
        urgency_multiplier = 1 + self.config.urgency * 2
        slice_size = base_size * urgency_multiplier
        
        # Apply limits
        slice_size = max(slice_size, self.config.min_slice_size)
        slice_size = min(slice_size, self.config.max_slice_size)
        slice_size = min(slice_size, total * 0.5)  # Max 50% of remaining
        
        return slice_size
    
    def _calculate_slice_size(self, state: VWAPState) -> float:
        """
        Calculate slice size based on current conditions.
        
        Args:
            state: VWAP state
            
        Returns:
            float: Slice size
        """
        remaining = state.remaining_quantity
        
        # Get projected remaining volume
        projected_volume = state.projected_volume or remaining
        
        # Calculate remaining intervals
        elapsed = (datetime.utcnow() - state.start_time).total_seconds()
        total_time = self.config.max_execution_time
        remaining_time = total_time - elapsed
        
        if remaining_time <= 0:
            return remaining
        
        intervals_remaining = remaining_time / state.slice_interval_seconds
        
        # Base slice size
        base_size = remaining / max(intervals_remaining, 1)
        
        # Adjust based on VWAP deviation
        deviation_abs = abs(state.vwap_deviation)
        if deviation_abs > self.config.price_tolerance:
            # Increase urgency when deviating from VWAP
            urgency_factor = 1 + deviation_abs * 2
            base_size *= urgency_factor
        
        # Adjust based on market conditions
        market_factor = self._calculate_market_factor(state)
        base_size *= market_factor
        
        # Apply limits
        slice_size = max(base_size, self.config.min_slice_size)
        slice_size = min(slice_size, self.config.max_slice_size)
        slice_size = min(slice_size, remaining * 0.3)  # Max 30% of remaining
        
        # Apply participation rate
        max_participation = remaining * self.config.participation_rate
        slice_size = min(slice_size, max_participation)
        
        return slice_size
    
    def _calculate_market_factor(self, state: VWAPState) -> float:
        """
        Calculate market condition factor.
        
        Args:
            state: VWAP state
            
        Returns:
            float: Market factor
        """
        factor = 1.0
        
        # Adjust based on volatility
        if state.market_volatility > 0:
            if state.market_volatility > 0.02:  # High volatility
                factor *= 0.8  # Reduce size
            elif state.market_volatility < 0.005:  # Low volatility
                factor *= 1.2  # Increase size
        
        # Adjust based on participation rate
        if state.current_participation_rate > self.config.participation_rate:
            factor *= 0.7
        
        return factor
    
    # ========================================================================
    # PRICE CALCULATIONS
    # ========================================================================
    
    async def _calculate_slice_price(self, state: VWAPState) -> Optional[float]:
        """
        Calculate price for the next slice.
        
        Args:
            state: VWAP state
            
        Returns:
            Optional[float]: Slice price or None
        """
        current_vwap = state.current_vwap
        target_vwap = state.target_vwap
        
        # Get current market price
        current_price = await self._get_current_price(state.symbol)
        if current_price is None:
            return None
        
        # Base price is current market price
        base_price = current_price
        
        # Adjust towards VWAP
        if state.side == OrderSide.BUY:
            # For buy orders, try to get below VWAP
            max_price = min(current_price, target_vwap * (1 + self.config.price_tolerance))
            price = min(base_price, max_price)
            
            # If price is above VWAP, we may need to increase urgency
            if price > target_vwap:
                state.metadata["above_vwap"] = True
                # Increase urgency if too far above VWAP
                deviation = (price - target_vwap) / target_vwap
                if deviation > self.config.max_price_deviation:
                    # Market order for this slice
                    return None  # Use market order
        else:
            # For sell orders, try to get above VWAP
            min_price = max(current_price, target_vwap * (1 - self.config.price_tolerance))
            price = max(base_price, min_price)
            
            if price < target_vwap:
                state.metadata["below_vwap"] = True
                deviation = (target_vwap - price) / target_vwap
                if deviation > self.config.max_price_deviation:
                    return None  # Use market order
        
        # Apply price tolerance
        tolerance = self.config.price_tolerance * target_vwap
        price = max(price, target_vwap - tolerance)
        price = min(price, target_vwap + tolerance)
        
        return price
    
    async def _calculate_target_vwap(self, symbol: str) -> float:
        """
        Calculate target VWAP for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            float: Target VWAP
        """
        # If we have historical VWAP, use it
        if self._historical_vwap > 0:
            return self._historical_vwap
        
        # Otherwise use current market price
        current_price = await self._get_current_price(symbol)
        return current_price or 0.0
    
    async def _update_vwap(self, state: VWAPState, price: float, quantity: float) -> None:
        """
        Update VWAP calculation.
        
        Args:
            state: VWAP state
            price: Execution price
            quantity: Execution quantity
        """
        # Update current VWAP
        total_value = state.current_vwap * state.total_quantity
        new_value = price * quantity
        new_total = state.total_quantity + quantity
        
        if new_total > 0:
            state.current_vwap = (total_value + new_value) / new_total
        
        # Update deviation
        state.vwap_deviation = (price - state.current_vwap) / state.current_vwap if state.current_vwap > 0 else 0
    
    # ========================================================================
    # VOLUME PROFILE
    # ========================================================================
    
    async def _load_historical_volume_profile(self, symbol: str) -> None:
        """
        Load historical volume profile for a symbol.
        
        Args:
            symbol: Trading symbol
        """
        # In production, this would load from a database or file
        # For now, use a default profile
        self._historical_volume_profile = self._generate_default_profile()
    
    def _generate_default_profile(self) -> Dict[int, float]:
        """
        Generate a default volume profile (U-shaped).
        
        Returns:
            Dict[int, float]: Volume profile by period index
        """
        profile = {}
        total_periods = self.config.vwap_period
        
        for i in range(total_periods):
            # U-shaped profile: higher volume at open and close
            position = i / total_periods
            if position < 0.1:
                volume = 1.5 - position * 5  # High at open
            elif position > 0.9:
                volume = 1.5 - (1 - position) * 5  # High at close
            else:
                volume = 0.8 + 0.4 * math.sin(position * math.pi)  # Slight mid-day dip
            
            profile[i] = max(0.5, volume)
        
        # Normalize
        total = sum(profile.values())
        for i in profile:
            profile[i] /= total
        
        return profile
    
    async def _update_volume_profile(self, state: VWAPState) -> None:
        """
        Update volume profile with real-time data.
        
        Args:
            state: VWAP state
        """
        # Get current period
        elapsed = (datetime.utcnow() - self._session_start_time).total_seconds()
        period_index = min(
            int(elapsed / (self.config.vwap_period * 60)),
            self.config.vwap_period - 1,
        )
        
        # Get current volume
        current_volume = await self._get_current_volume(state.symbol)
        
        # Update profile
        self._session_volume_profile[period_index] = self._session_volume_profile.get(period_index, 0) + current_volume
    
    # ========================================================================
    # MARKET CONDITIONS
    # ========================================================================
    
    async def _update_market_conditions(self, state: VWAPState) -> None:
        """
        Update market conditions for the order.
        
        Args:
            state: VWAP state
        """
        # Update price history
        price = await self._get_current_price(state.symbol)
        if price:
            self._price_history.append(price)
        
        # Calculate volatility
        if len(self._price_history) > 20:
            prices = list(self._price_history)[-20:]
            state.market_volatility = np.std(prices) / np.mean(prices) if np.mean(prices) > 0 else 0
        
        # Update participation rate
        elapsed = (datetime.utcnow() - state.start_time).total_seconds()
        if elapsed > 0:
            filled_per_second = state.filled_quantity / elapsed
            total_volume = await self._get_current_volume(state.symbol)
            if total_volume > 0:
                state.current_participation_rate = filled_per_second / (total_volume / elapsed)
        
        # Check for adverse movement
        if self.config.pause_on_adverse_movement:
            await self._check_adverse_movement(state)
    
    async def _check_adverse_movement(self, state: VWAPState) -> None:
        """
        Check for adverse price movement and pause execution.
        
        Args:
            state: VWAP state
        """
        if len(self._price_history) < 10:
            return
        
        prices = list(self._price_history)[-10:]
        price_change = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
        
        # For buy orders, pause if price increases (adverse)
        # For sell orders, pause if price decreases (adverse)
        if state.side == OrderSide.BUY:
            if price_change > self.config.adverse_movement_threshold:
                state.is_paused = True
                state.pause_reason = f"Price increased by {price_change:.2%}"
        else:
            if price_change < -self.config.adverse_movement_threshold:
                state.is_paused = True
                state.pause_reason = f"Price decreased by {abs(price_change):.2%}"
    
    async def _check_resume(self, state: VWAPState) -> None:
        """
        Check if execution can resume after a pause.
        
        Args:
            state: VWAP state
        """
        if not state.is_paused:
            return
        
        # Check if price has stabilized
        if len(self._price_history) < 10:
            return
        
        prices = list(self._price_history)[-10:]
        price_change = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
        abs_change = abs(price_change)
        
        if abs_change < self.config.adverse_movement_threshold * 0.5:
            state.is_paused = False
            state.pause_reason = None
            self.logger.info(f"Resuming VWAP execution for {state.order_id}")
    
    # ========================================================================
    # COMPLETION ESTIMATION
    # ========================================================================
    
    def _update_completion_estimate(self, state: VWAPState) -> None:
        """
        Update estimated completion time.
        
        Args:
            state: VWAP state
        """
        if state.filled_quantity == 0:
            return
        
        fill_rate = state.filled_quantity / max((datetime.utcnow() - state.start_time).total_seconds(), 1)
        
        if fill_rate > 0:
            remaining_time = state.remaining_quantity / fill_rate
            state.estimated_completion_time = datetime.utcnow() + timedelta(seconds=remaining_time)
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    async def _simulate_slice_execution(self, order: Order) -> bool:
        """
        Simulate execution of a slice (for testing).
        
        Args:
            order: Slice order
            
        Returns:
            bool: True if executed successfully
        """
        # In production, this would be replaced with actual broker execution
        return True
    
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current market price.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Optional[float]: Current price or None
        """
        # This would call the broker's market data API
        # For now, return a placeholder
        return 100.0
    
    async def _get_current_volume(self, symbol: str) -> float:
        """
        Get current volume.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            float: Current volume
        """
        # This would call the broker's market data API
        # For now, return a placeholder
        return 1000.0
    
    def _generate_order_id(self) -> str:
        """Generate a unique order ID."""
        return f"vwap_{int(time.time() * 1000)}_{id(self)}"
    
    def _validate_order(self, order: Order) -> bool:
        """
        Validate an order for VWAP execution.
        
        Args:
            order: Order to validate
            
        Returns:
            bool: True if order is valid
        """
        if order.quantity <= 0:
            self.logger.error("Order quantity must be positive")
            return False
        
        if order.symbol is None or not order.symbol.strip():
            self.logger.error("Order symbol is required")
            return False
        
        return True
    
    # ========================================================================
    # STATUS AND REPORTING
    # ========================================================================
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a VWAP order.
        
        Args:
            order_id: Order ID
            
        Returns:
            Optional[Dict[str, Any]]: Order status or None
        """
        state = self._active_states.get(order_id)
        if not state:
            return None
        
        return {
            "order_id": state.order_id,
            "symbol": state.symbol,
            "side": state.side.value,
            "total_quantity": state.total_quantity,
            "filled_quantity": state.filled_quantity,
            "remaining_quantity": state.remaining_quantity,
            "average_price": state.average_price,
            "current_vwap": state.current_vwap,
            "target_vwap": state.target_vwap,
            "vwap_deviation": state.vwap_deviation,
            "slices_completed": state.current_slice_index,
            "slices_successful": state.successful_slices,
            "slices_failed": state.failed_slices,
            "total_trades": state.total_trades,
            "execution_cost": state.execution_cost,
            "implementation_shortfall": state.implementation_shortfall,
            "participation_rate": state.current_participation_rate,
            "is_paused": state.is_paused,
            "pause_reason": state.pause_reason,
            "elapsed_seconds": (datetime.utcnow() - state.start_time).total_seconds(),
            "estimated_completion": state.estimated_completion_time.isoformat() if state.estimated_completion_time else None,
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get VWAP performance metrics.
        
        Returns:
            Dict[str, Any]: Performance metrics
        """
        total_orders = len(self._active_states) + len(self._completed_orders)
        
        return {
            "active_orders": len(self._active_states),
            "completed_orders": len(self._completed_orders),
            "total_orders": total_orders,
            "avg_successful_slices": sum(
                s.successful_slices for s in self._completed_orders
            ) / max(len(self._completed_orders), 1),
            "avg_failed_slices": sum(
                s.failed_slices for s in self._completed_orders
            ) / max(len(self._completed_orders), 1),
            "avg_execution_cost": sum(
                s.execution_cost for s in self._completed_orders
            ) / max(len(self._completed_orders), 1),
            "avg_implementation_shortfall": sum(
                s.implementation_shortfall for s in self._completed_orders
            ) / max(len(self._completed_orders), 1),
        }
    
    # ========================================================================
    # LIFECYCLE MANAGEMENT
    # ========================================================================
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a VWAP order.
        
        Args:
            order_id: Order ID
            
        Returns:
            bool: True if order was cancelled
        """
        if order_id in self._active_states:
            state = self._active_states[order_id]
            state.is_paused = True
            state.pause_reason = "Cancelled by user"
            self._is_running = False
            
            if self._slice_task:
                self._slice_task.cancel()
                
            self._completed_orders.append(state)
            del self._active_states[order_id]
            
            self.logger.info(f"Cancelled VWAP order {order_id}")
            return True
        
        return False
    
    def pause_order(self, order_id: str, reason: str = "Manual pause") -> bool:
        """
        Pause a VWAP order.
        
        Args:
            order_id: Order ID
            reason: Pause reason
            
        Returns:
            bool: True if order was paused
        """
        state = self._active_states.get(order_id)
        if state:
            state.is_paused = True
            state.pause_reason = reason
            self.logger.info(f"Paused VWAP order {order_id}: {reason}")
            return True
        return False
    
    def resume_order(self, order_id: str) -> bool:
        """
        Resume a paused VWAP order.
        
        Args:
            order_id: Order ID
            
        Returns:
            bool: True if order was resumed
        """
        state = self._active_states.get(order_id)
        if state and state.is_paused:
            state.is_paused = False
            state.pause_reason = None
            self.logger.info(f"Resumed VWAP order {order_id}")
            return True
        return False
    
    async def stop(self) -> None:
        """Stop all VWAP executions."""
        self._is_running = False
        
        if self._slice_task:
            self._slice_task.cancel()
            try:
                await self._slice_task
            except asyncio.CancelledError:
                pass
            self._slice_task = None
        
        # Cancel all active orders
        for order_id in list(self._active_states.keys()):
            await self.cancel_order(order_id)
        
        self.logger.info("VWAP execution engine stopped")
    
    # ========================================================================
    # CONTEXT MANAGER
    # ========================================================================
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "VWAPExecutionStyle",
    "VolumeProfileType",
    
    # Models
    "VWAPConfig",
    "VWAPState",
    
    # Engine
    "VWAPExecutionEngine",
]
