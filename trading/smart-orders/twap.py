# trading/smart-orders/twap.py
"""
NEXUS AI TRADING SYSTEM - TWAP Order Execution
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements Time-Weighted Average Price (TWAP) order execution
strategies for algorithmic trading. TWAP execution aims to execute orders
evenly over a specified time period to minimize market impact and achieve
a price close to the average price over the execution period.

Key Features:
- TWAP order execution with configurable time horizons
- Multiple slicing strategies (equal, aggressive, passive)
- Urgency-based execution adjustment
- Price benchmark tracking
- Market impact minimization
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
from shared.types.trading import Order, Trade, MarketData
from .base import SmartOrderBase, SmartOrderConfig, SmartOrderType, OrderSlice

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class TWAPExecutionStyle(str, Enum):
    """TWAP execution styles"""
    STANDARD = "standard"          # Equal slices over time
    AGGRESSIVE = "aggressive"      # Larger slices early
    PASSIVE = "passive"            # Larger slices late
    ADAPTIVE = "adaptive"          # Adapts to market conditions
    URGENCY_BASED = "urgency_based"  # Based on urgency parameter
    VOLATILITY_BASED = "volatility_based"  # Based on market volatility


class TWAPUrgency(str, Enum):
    """Urgency levels for TWAP execution"""
    LOW = "low"            # 0-25% urgency
    MEDIUM = "medium"      # 25-50% urgency
    HIGH = "high"          # 50-75% urgency
    CRITICAL = "critical"  # 75-100% urgency


@dataclass
class TWAPConfig(SmartOrderConfig):
    """Configuration for TWAP execution"""
    # Execution parameters
    execution_style: TWAPExecutionStyle = TWAPExecutionStyle.STANDARD
    urgency: TWAPUrgency = TWAPUrgency.MEDIUM
    
    # Time parameters
    execution_horizon: int = 3600  # 1 hour in seconds
    min_slice_interval: int = 5    # Minimum seconds between slices
    max_slice_interval: int = 300  # Maximum seconds between slices
    total_slices: int = 20         # Total number of slices
    
    # Slicing parameters
    min_slice_size: float = 10.0
    max_slice_size: float = 10000.0
    initial_slice_factor: float = 1.0  # Multiplier for first slice
    
    # Price parameters
    price_tolerance: float = 0.01  # 1% tolerance from benchmark
    max_price_deviation: float = 0.03  # 3% max deviation
    
    # Urgency parameters
    urgency_threshold: float = 0.5
    urgency_ramp: float = 0.1  # 10% urgency increase per period
    
    # Market impact parameters
    market_impact_model: str = "linear"
    impact_coefficient: float = 0.001
    urgency_impact_multiplier: float = 1.5
    
    # Execution limits
    max_execution_time: int = 7200  # 2 hours
    min_execution_time: int = 60    # 1 minute
    pause_on_adverse_movement: bool = True
    adverse_movement_threshold: float = 0.015  # 1.5%


@dataclass
class TWAPState:
    """State of TWAP execution"""
    order_id: str
    symbol: str
    side: OrderSide
    total_quantity: float
    remaining_quantity: float
    filled_quantity: float = 0.0
    average_price: float = 0.0
    
    # TWAP tracking
    target_price: float = 0.0
    benchmark_price: float = 0.0
    price_deviation: float = 0.0
    slippage: float = 0.0
    
    # Slicing
    slices: List[OrderSlice] = field(default_factory=list)
    current_slice_index: int = 0
    planned_slice_size: float = 0.0
    actual_slice_size: float = 0.0
    
    # Performance
    total_trades: int = 0
    successful_slices: int = 0
    failed_slices: int = 0
    execution_cost: float = 0.0
    
    # Timing
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_slice_time: datetime = field(default_factory=datetime.utcnow)
    estimated_completion_time: Optional[datetime] = None
    elapsed_seconds: float = 0.0
    
    # Market conditions
    market_volatility: float = 0.0
    current_urgency: float = 0.0
    is_paused: bool = False
    pause_reason: Optional[str] = None
    
    # Execution metrics
    execution_rate: float = 0.0
    completion_percentage: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# TWAP EXECUTION ENGINE
# ============================================================================

class TWAPExecutionEngine(SmartOrderBase):
    """
    TWAP (Time-Weighted Average Price) execution engine.
    
    Implements TWAP order execution with configurable slicing strategies
    and market condition adaptation.
    """
    
    def __init__(self, config: Optional[TWAPConfig] = None):
        """
        Initialize the TWAP execution engine.
        
        Args:
            config: TWAP configuration
        """
        super().__init__(config or TWAPConfig())
        self.config = config or TWAPConfig()
        self.smart_type = SmartOrderType.TWAP
        
        # State management
        self._active_states: Dict[str, TWAPState] = {}
        self._completed_orders: List[TWAPState] = []
        
        # Historical data
        self._price_history: deque = deque(maxlen=1000)
        self._volume_history: deque = deque(maxlen=1000)
        self._execution_history: deque = deque(maxlen=1000)
        
        # Timer for slice execution
        self._slice_task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        
        self.logger = logger
    
    # ========================================================================
    # ORDER EXECUTION
    # ========================================================================
    
    async def execute_order(self, order: Order) -> Tuple[bool, List[Trade]]:
        """
        Execute an order using TWAP strategy.
        
        Args:
            order: Order to execute
            
        Returns:
            Tuple[bool, List[Trade]]: Success status and list of executed trades
        """
        # Validate order
        if not self._validate_order(order):
            return False, []
        
        # Create TWAP state
        state = TWAPState(
            order_id=order.order_id or self._generate_order_id(),
            symbol=order.symbol,
            side=order.side,
            total_quantity=order.quantity,
            remaining_quantity=order.quantity,
            target_price=order.price or 0.0,
        )
        
        # Calculate benchmark price
        state.benchmark_price = await self._calculate_benchmark_price(order.symbol)
        state.target_price = state.benchmark_price
        
        # Calculate planned slice size
        state.planned_slice_size = self._calculate_slice_size(state)
        
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
            self.logger.warning(f"TWAP execution timed out for order {state.order_id}")
            state.metadata["timeout"] = True
        
        # Return results
        success = state.remaining_quantity < 0.001
        
        # Build trades list
        trades = []
        for slice_info in state.slices:
            if slice_info.trades:
                trades.extend(slice_info.trades)
        
        return success, trades
    
    async def _execute_slices(self, state: TWAPState) -> None:
        """
        Execute TWAP slices over time.
        
        Args:
            state: TWAP state
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
                state.actual_slice_size = slice_size
                
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
                
                # Update progress
                state.elapsed_seconds = (datetime.utcnow() - state.start_time).total_seconds()
                state.completion_percentage = (state.filled_quantity / state.total_quantity) * 100
                state.execution_rate = state.filled_quantity / max(state.elapsed_seconds, 1)
                
                # Update estimated completion time
                self._update_completion_estimate(state)
                
                # Log progress
                if state.current_slice_index % 10 == 0 or state.completion_percentage >= 100:
                    self.logger.info(
                        f"TWAP progress: {state.completion_percentage:.1f}% "
                        f"({state.filled_quantity:.2f}/{state.total_quantity:.2f}) "
                        f"Avg price: {state.average_price:.4f}"
                    )
                
                # Wait for next slice
                interval = self._calculate_slice_interval(state)
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                self.logger.info(f"Slice execution cancelled for order {state.order_id}")
                break
            except Exception as e:
                self.logger.error(f"Error executing slice for {state.order_id}: {e}")
                await asyncio.sleep(5)
    
    async def _execute_slice(self, state: TWAPState, quantity: float) -> bool:
        """
        Execute a single slice.
        
        Args:
            state: TWAP state
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
            client_order_id=f"twap_slice_{state.order_id}_{state.current_slice_index}",
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
                
                # Calculate slippage
                if state.benchmark_price > 0:
                    state.slippage = (price - state.benchmark_price) / state.benchmark_price
                    if state.side == OrderSide.SELL:
                        state.slippage = -state.slippage
                    state.price_deviation = state.slippage
                
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
                
                self.logger.debug(
                    f"TWAP slice executed: {quantity:.2f} @ {price:.4f} "
                    f"(slippage: {state.slippage:.4%})"
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
    
    def _calculate_slice_size(self, state: TWAPState) -> float:
        """
        Calculate slice size based on execution style.
        
        Args:
            state: TWAP state
            
        Returns:
            float: Slice size
        """
        remaining = state.remaining_quantity
        elapsed = state.elapsed_seconds
        total_time = self.config.execution_horizon
        
        # Calculate remaining time
        remaining_time = max(total_time - elapsed, 1)
        slices_remaining = max(self.config.total_slices - state.current_slice_index, 1)
        
        # Base slice size (equal distribution)
        base_size = remaining / max(remaining_time / self.config.min_slice_interval, 1)
        
        # Apply execution style
        style = self.config.execution_style
        progress = state.completion_percentage / 100
        
        if style == TWAPExecutionStyle.STANDARD:
            # Equal distribution
            slice_size = base_size
            
        elif style == TWAPExecutionStyle.AGGRESSIVE:
            # Larger slices early
            urgency_factor = 1 + (1 - progress) * 2
            slice_size = base_size * urgency_factor
            
        elif style == TWAPExecutionStyle.PASSIVE:
            # Larger slices late
            urgency_factor = 1 + progress * 2
            slice_size = base_size * urgency_factor
            
        elif style == TWAPExecutionStyle.ADAPTIVE:
            # Adapt to market conditions
            market_factor = self._calculate_market_factor(state)
            urgency_factor = 1 + state.current_urgency
            slice_size = base_size * market_factor * urgency_factor
            
        elif style == TWAPExecutionStyle.URGENCY_BASED:
            # Based on urgency parameter
            urgency_value = self._get_urgency_value(self.config.urgency)
            urgency_factor = 1 + urgency_value * (1 - progress)
            slice_size = base_size * urgency_factor
            
        elif style == TWAPExecutionStyle.VOLATILITY_BASED:
            # Based on market volatility
            if state.market_volatility > 0:
                volatility_factor = 1 + state.market_volatility * 10
                slice_size = base_size / volatility_factor
            else:
                slice_size = base_size
        
        # Apply initial slice factor
        if state.current_slice_index == 0:
            slice_size *= self.config.initial_slice_factor
        
        # Apply limits
        slice_size = max(slice_size, self.config.min_slice_size)
        slice_size = min(slice_size, self.config.max_slice_size)
        slice_size = min(slice_size, remaining * 0.5)  # Max 50% of remaining
        
        return slice_size
    
    def _calculate_slice_interval(self, state: TWAPState) -> float:
        """
        Calculate interval between slices.
        
        Args:
            state: TWAP state
            
        Returns:
            float: Interval in seconds
        """
        elapsed = state.elapsed_seconds
        total_time = self.config.execution_horizon
        
        # Calculate remaining time
        remaining_time = max(total_time - elapsed, 1)
        slices_remaining = max(self.config.total_slices - state.current_slice_index, 1)
        
        # Base interval
        base_interval = remaining_time / max(slices_remaining, 1)
        
        # Apply constraints
        interval = max(base_interval, self.config.min_slice_interval)
        interval = min(interval, self.config.max_slice_interval)
        
        # Adjust based on urgency
        if self.config.execution_style == TWAPExecutionStyle.URGENCY_BASED:
            urgency_value = self._get_urgency_value(self.config.urgency)
            interval *= (1 - urgency_value * 0.5)
        
        # Adjust based on volatility
        if state.market_volatility > 0.02:
            interval *= 1.5  # Slower in high volatility
        
        return max(interval, 1)  # Minimum 1 second
    
    def _calculate_market_factor(self, state: TWAPState) -> float:
        """
        Calculate market condition factor.
        
        Args:
            state: TWAP state
            
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
        
        # Adjust based on price deviation
        if abs(state.price_deviation) > self.config.price_tolerance:
            if state.side == OrderSide.BUY and state.price_deviation > 0:
                factor *= 0.8  # Reduce if price is moving against us
            elif state.side == OrderSide.SELL and state.price_deviation < 0:
                factor *= 0.8
        
        return factor
    
    # ========================================================================
    # PRICE CALCULATIONS
    # ========================================================================
    
    async def _calculate_slice_price(self, state: TWAPState) -> Optional[float]:
        """
        Calculate price for the next slice.
        
        Args:
            state: TWAP state
            
        Returns:
            Optional[float]: Slice price or None
        """
        # Get current market price
        current_price = await self._get_current_price(state.symbol)
        if current_price is None:
            return None
        
        # Calculate price based on side
        if state.side == OrderSide.BUY:
            # For buy orders, try to get below target price
            max_price = current_price * (1 + self.config.price_tolerance)
            price = min(current_price, max_price)
            
            # Check deviation from benchmark
            if state.benchmark_price > 0:
                deviation = (price - state.benchmark_price) / state.benchmark_price
                if deviation > self.config.max_price_deviation:
                    # Too expensive, wait
                    state.is_paused = True
                    state.pause_reason = f"Price {deviation:.2%} above benchmark"
                    return None
        else:
            # For sell orders, try to get above target price
            min_price = current_price * (1 - self.config.price_tolerance)
            price = max(current_price, min_price)
            
            if state.benchmark_price > 0:
                deviation = (state.benchmark_price - price) / state.benchmark_price
                if deviation > self.config.max_price_deviation:
                    # Too cheap, wait
                    state.is_paused = True
                    state.pause_reason = f"Price {deviation:.2%} below benchmark"
                    return None
        
        return price
    
    async def _calculate_benchmark_price(self, symbol: str) -> float:
        """
        Calculate benchmark price for TWAP.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            float: Benchmark price
        """
        # Use current price as benchmark
        current_price = await self._get_current_price(symbol)
        return current_price or 0.0
    
    # ========================================================================
    # MARKET CONDITIONS
    # ========================================================================
    
    async def _update_market_conditions(self, state: TWAPState) -> None:
        """
        Update market conditions for the order.
        
        Args:
            state: TWAP state
        """
        # Update price history
        price = await self._get_current_price(state.symbol)
        if price:
            self._price_history.append(price)
        
        # Calculate volatility
        if len(self._price_history) > 20:
            prices = list(self._price_history)[-20:]
            state.market_volatility = np.std(prices) / np.mean(prices) if np.mean(prices) > 0 else 0
        
        # Update urgency
        elapsed_progress = state.elapsed_seconds / self.config.execution_horizon
        fill_progress = state.completion_percentage / 100
        
        # If we're behind schedule, increase urgency
        if elapsed_progress > fill_progress + 0.1:
            state.current_urgency = min(1.0, state.current_urgency + self.config.urgency_ramp)
        elif elapsed_progress < fill_progress - 0.1:
            state.current_urgency = max(0.0, state.current_urgency - self.config.urgency_ramp)
        
        # Check for adverse movement
        if self.config.pause_on_adverse_movement:
            await self._check_adverse_movement(state)
    
    async def _check_adverse_movement(self, state: TWAPState) -> None:
        """
        Check for adverse price movement and pause execution.
        
        Args:
            state: TWAP state
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
    
    async def _check_resume(self, state: TWAPState) -> None:
        """
        Check if execution can resume after a pause.
        
        Args:
            state: TWAP state
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
            self.logger.info(f"Resuming TWAP execution for {state.order_id}")
    
    # ========================================================================
    # COMPLETION ESTIMATION
    # ========================================================================
    
    def _update_completion_estimate(self, state: TWAPState) -> None:
        """
        Update estimated completion time.
        
        Args:
            state: TWAP state
        """
        if state.filled_quantity == 0:
            return
        
        fill_rate = state.filled_quantity / max(state.elapsed_seconds, 1)
        
        if fill_rate > 0:
            remaining_time = state.remaining_quantity / fill_rate
            state.estimated_completion_time = datetime.utcnow() + timedelta(seconds=remaining_time)
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _get_urgency_value(self, urgency: TWAPUrgency) -> float:
        """
        Get numeric value for urgency level.
        
        Args:
            urgency: Urgency level
            
        Returns:
            float: Urgency value (0-1)
        """
        mapping = {
            TWAPUrgency.LOW: 0.25,
            TWAPUrgency.MEDIUM: 0.50,
            TWAPUrgency.HIGH: 0.75,
            TWAPUrgency.CRITICAL: 1.00,
        }
        return mapping.get(urgency, 0.5)
    
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
    
    def _generate_order_id(self) -> str:
        """Generate a unique order ID."""
        return f"twap_{int(time.time() * 1000)}_{id(self)}"
    
    def _validate_order(self, order: Order) -> bool:
        """
        Validate an order for TWAP execution.
        
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
        Get status of a TWAP order.
        
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
            "target_price": state.target_price,
            "benchmark_price": state.benchmark_price,
            "price_deviation": state.price_deviation,
            "slippage": state.slippage,
            "slices_completed": state.current_slice_index,
            "slices_successful": state.successful_slices,
            "slices_failed": state.failed_slices,
            "total_trades": state.total_trades,
            "execution_cost": state.execution_cost,
            "completion_percentage": state.completion_percentage,
            "execution_rate": state.execution_rate,
            "is_paused": state.is_paused,
            "pause_reason": state.pause_reason,
            "current_urgency": state.current_urgency,
            "market_volatility": state.market_volatility,
            "elapsed_seconds": state.elapsed_seconds,
            "estimated_completion": state.estimated_completion_time.isoformat() if state.estimated_completion_time else None,
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get TWAP performance metrics.
        
        Returns:
            Dict[str, Any]: Performance metrics
        """
        total_orders = len(self._active_states) + len(self._completed_orders)
        
        if not self._completed_orders:
            return {
                "active_orders": len(self._active_states),
                "completed_orders": 0,
                "total_orders": total_orders,
            }
        
        return {
            "active_orders": len(self._active_states),
            "completed_orders": len(self._completed_orders),
            "total_orders": total_orders,
            "avg_successful_slices": sum(
                s.successful_slices for s in self._completed_orders
            ) / len(self._completed_orders),
            "avg_failed_slices": sum(
                s.failed_slices for s in self._completed_orders
            ) / len(self._completed_orders),
            "avg_execution_cost": sum(
                s.execution_cost for s in self._completed_orders
            ) / len(self._completed_orders),
            "avg_slippage": sum(
                s.slippage for s in self._completed_orders
            ) / len(self._completed_orders),
            "avg_completion_time": sum(
                (s.estimated_completion_time - s.start_time).total_seconds()
                for s in self._completed_orders
                if s.estimated_completion_time
            ) / len(self._completed_orders),
        }
    
    # ========================================================================
    # LIFECYCLE MANAGEMENT
    # ========================================================================
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a TWAP order.
        
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
            
            self.logger.info(f"Cancelled TWAP order {order_id}")
            return True
        
        return False
    
    def pause_order(self, order_id: str, reason: str = "Manual pause") -> bool:
        """
        Pause a TWAP order.
        
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
            self.logger.info(f"Paused TWAP order {order_id}: {reason}")
            return True
        return False
    
    def resume_order(self, order_id: str) -> bool:
        """
        Resume a paused TWAP order.
        
        Args:
            order_id: Order ID
            
        Returns:
            bool: True if order was resumed
        """
        state = self._active_states.get(order_id)
        if state and state.is_paused:
            state.is_paused = False
            state.pause_reason = None
            self.logger.info(f"Resumed TWAP order {order_id}")
            return True
        return False
    
    async def stop(self) -> None:
        """Stop all TWAP executions."""
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
        
        self.logger.info("TWAP execution engine stopped")
    
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
    "TWAPExecutionStyle",
    "TWAPUrgency",
    
    # Models
    "TWAPConfig",
    "TWAPState",
    
    # Engine
    "TWAPExecutionEngine",
]
