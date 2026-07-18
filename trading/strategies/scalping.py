# trading/strategies/scalping.py
"""
NEXUS AI TRADING SYSTEM - Scalping Strategy
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements scalping trading strategies including:
- Tick scalping
- Order book scalping
- Spread scalping
- Momentum scalping
- Pairs scalping
- Market making scalping

Scalping strategies aim to profit from small price movements with
high frequency trades and tight risk management.
"""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from collections import deque

import numpy as np

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType, TimeInForce
from shared.types.trading import MarketData, Signal, Position, Trade, OrderBook
from .base import BaseStrategy, StrategyConfig, SignalType, SignalStrength

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class ScalpingType(str, Enum):
    """Types of scalping strategies"""
    TICK = "tick"
    ORDER_BOOK = "order_book"
    SPREAD = "spread"
    MOMENTUM = "momentum"
    PAIRS = "pairs"
    MARKET_MAKING = "market_making"
    COMBINED = "combined"


class OrderBookSide(str, Enum):
    """Order book sides"""
    BID = "bid"
    ASK = "ask"


@dataclass
class ScalpingConfig:
    """Configuration for scalping strategy"""
    # Strategy type
    scalping_type: ScalpingType = ScalpingType.TICK
    direction: str = "both"  # long, short, both
    
    # Entry parameters
    min_profit_pips: float = 1.0
    max_holding_bars: int = 5
    entry_window: int = 3
    
    # Tick scalping
    tick_threshold: float = 0.001
    tick_volume_min: int = 100
    
    # Order book scalping
    order_book_depth: int = 10
    order_book_imbalance_threshold: float = 0.3
    order_book_min_spread: float = 0.001
    
    # Spread scalping
    spread_threshold: float = 0.002
    spread_mean_reversion: bool = True
    spread_lookback: int = 20
    
    # Momentum scalping
    momentum_period: int = 5
    momentum_threshold: float = 0.001
    momentum_acceleration: bool = True
    
    # Market making
    market_making_spread: float = 0.001
    market_making_depth: int = 5
    market_making_position_limit: float = 1000.0
    
    # Pairs scalping
    pairs_correlation_min: float = 0.8
    pairs_threshold: float = 0.002
    
    # Risk management
    position_size: float = 100.0
    max_position_size: float = 10000.0
    stop_loss_pct: float = 0.005  # 0.5%
    take_profit_pct: float = 0.01   # 1%
    max_positions: int = 5
    max_drawdown: float = 0.02  # 2%
    max_daily_trades: int = 100
    
    # Execution
    order_type: OrderType = OrderType.LIMIT
    time_in_force: TimeInForce = TimeInForce.IOC
    slippage_tolerance: float = 0.001
    
    # Monitoring
    check_interval: int = 1  # bars
    min_volume: float = 1000.0
    require_tick_data: bool = True


@dataclass
class ScalpingState:
    """Current state of scalping strategy"""
    symbol: str
    current_price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    spread: float = 0.0
    
    # Statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    daily_trades: int = 0
    last_trade_time: Optional[datetime] = None
    
    # Tick data
    tick_count: int = 0
    last_tick_time: Optional[datetime] = None
    tick_velocity: float = 0.0
    
    # Order book
    bid_depth: float = 0.0
    ask_depth: float = 0.0
    imbalance: float = 0.0
    
    # Market making
    quote_ids: List[str] = field(default_factory=list)
    filled_quotes: int = 0
    
    # Momentum
    price_momentum: float = 0.0
    volume_momentum: float = 0.0
    
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# SCALPING STRATEGY
# ============================================================================

class ScalpingStrategy(BaseStrategy):
    """
    Scalping trading strategy for high-frequency small profits.
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        scalping_config: Optional[ScalpingConfig] = None,
    ):
        """
        Initialize the scalping strategy.
        
        Args:
            config: Strategy configuration
            scalping_config: Scalping configuration
        """
        super().__init__(config)
        self.scalping_config = scalping_config or ScalpingConfig()
        
        # State management
        self._states: Dict[str, ScalpingState] = {}
        
        # Data storage
        self._price_history: Dict[str, deque] = {}
        self._tick_history: Dict[str, deque] = {}
        self._order_book_history: Dict[str, deque] = {}
        self._spread_history: Dict[str, deque] = {}
        self._volume_history: Dict[str, deque] = {}
        
        # Order tracking
        self._pending_orders: Dict[str, List[Order]] = {}
        self._filled_orders: List[Order] = []
        
        # Daily tracking
        self._daily_date: Optional[datetime] = None
        self._daily_trades: int = 0
        
        # Performance tracking
        self._scalping_stats = {
            "total_signals": 0,
            "valid_signals": 0,
            "trades_executed": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "avg_profit_pips": 0.0,
            "avg_hold_bars": 0.0,
            "max_profit_pips": 0.0,
            "max_loss_pips": 0.0,
            "trades_per_minute": 0.0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        self.logger = logger
    
    # ========================================================================
    # TICK SCALPING
    # ========================================================================
    
    async def _detect_tick_scalping_signal(
        self,
        symbol: str,
        state: ScalpingState,
    ) -> Optional[Signal]:
        """
        Detect tick scalping signal.
        
        Args:
            symbol: Trading symbol
            state: Current state
            
        Returns:
            Optional[Signal]: Scalping signal
        """
        if len(self._tick_history.get(symbol, deque())) < 10:
            return None
        
        ticks = list(self._tick_history[symbol])[-10:]
        tick_velocity = (ticks[-1] - ticks[0]) / len(ticks)
        state.tick_velocity = tick_velocity
        
        # Check tick velocity and volume
        if abs(tick_velocity) > self.scalping_config.tick_threshold:
            if tick_velocity > 0:
                # Upward tick momentum
                if self.scalping_config.direction in ["long", "both"]:
                    return await self._create_scalping_signal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        state=state,
                        reason=f"Upward tick velocity: {tick_velocity:.4f}",
                        metadata={"tick_velocity": tick_velocity},
                    )
            else:
                # Downward tick momentum
                if self.scalping_config.direction in ["short", "both"]:
                    return await self._create_scalping_signal(
                        symbol=symbol,
                        signal_type=SignalType.SELL,
                        state=state,
                        reason=f"Downward tick velocity: {tick_velocity:.4f}",
                        metadata={"tick_velocity": tick_velocity},
                    )
        
        return None
    
    # ========================================================================
    # ORDER BOOK SCALPING
    # ========================================================================
    
    async def _detect_order_book_signal(
        self,
        symbol: str,
        state: ScalpingState,
        order_book: Optional[OrderBook] = None,
    ) -> Optional[Signal]:
        """
        Detect order book scalping signal.
        
        Args:
            symbol: Trading symbol
            state: Current state
            order_book: Order book data
            
        Returns:
            Optional[Signal]: Scalping signal
        """
        if not order_book:
            return None
        
        # Calculate imbalance
        bid_depth = sum(order_book.bids[:self.scalping_config.order_book_depth])
        ask_depth = sum(order_book.asks[:self.scalping_config.order_book_depth])
        
        state.bid_depth = bid_depth
        state.ask_depth = ask_depth
        state.imbalance = bid_depth / (bid_depth + ask_depth) if (bid_depth + ask_depth) > 0 else 0.5
        
        # Check imbalance
        if state.imbalance > 0.5 + self.scalping_config.order_book_imbalance_threshold:
            # Strong bid pressure
            if self.scalping_config.direction in ["long", "both"]:
                return await self._create_scalping_signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    state=state,
                    reason=f"Order book imbalance: {state.imbalance:.2f}",
                    metadata={"imbalance": state.imbalance, "bid_depth": bid_depth, "ask_depth": ask_depth},
                )
        
        elif state.imbalance < 0.5 - self.scalping_config.order_book_imbalance_threshold:
            # Strong ask pressure
            if self.scalping_config.direction in ["short", "both"]:
                return await self._create_scalping_signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    state=state,
                    reason=f"Order book imbalance: {state.imbalance:.2f}",
                    metadata={"imbalance": state.imbalance, "bid_depth": bid_depth, "ask_depth": ask_depth},
                )
        
        return None
    
    # ========================================================================
    # SPREAD SCALPING
    # ========================================================================
    
    async def _detect_spread_scalping_signal(
        self,
        symbol: str,
        state: ScalpingState,
        bid: float,
        ask: float,
    ) -> Optional[Signal]:
        """
        Detect spread scalping signal.
        
        Args:
            symbol: Trading symbol
            state: Current state
            bid: Bid price
            ask: Ask price
            
        Returns:
            Optional[Signal]: Scalping signal
        """
        spread = ask - bid
        state.bid = bid
        state.ask = ask
        state.spread = spread
        
        # Update spread history
        if symbol not in self._spread_history:
            self._spread_history[symbol] = deque(maxlen=50)
        self._spread_history[symbol].append(spread)
        
        # Check spread threshold
        if spread > self.scalping_config.spread_threshold:
            # Wide spread - potential mean reversion
            if self.scalping_config.spread_mean_reversion:
                spread_mean = sum(self._spread_history[symbol]) / len(self._spread_history[symbol])
                if spread > spread_mean * 1.5:
                    # Sell at ask, buy at bid (scalp the spread)
                    if self.scalping_config.direction in ["both", "long"]:
                        return await self._create_scalping_signal(
                            symbol=symbol,
                            signal_type=SignalType.BUY,
                            state=state,
                            price=bid,
                            reason=f"Wide spread scalping: {spread:.4f}",
                            metadata={"spread": spread, "spread_mean": spread_mean},
                        )
        
        return None
    
    # ========================================================================
    # MOMENTUM SCALPING
    # ========================================================================
    
    async def _detect_momentum_scalping_signal(
        self,
        symbol: str,
        state: ScalpingState,
        prices: List[float],
        volumes: Optional[List[float]] = None,
    ) -> Optional[Signal]:
        """
        Detect momentum scalping signal.
        
        Args:
            symbol: Trading symbol
            state: Current state
            prices: Price series
            volumes: Volume series
            
        Returns:
            Optional[Signal]: Scalping signal
        """
        if len(prices) < self.scalping_config.momentum_period + 1:
            return None
        
        # Calculate price momentum
        price_momentum = (prices[-1] - prices[-self.scalping_config.momentum_period]) / self.scalping_config.momentum_period
        state.price_momentum = price_momentum
        
        # Calculate volume momentum
        volume_momentum = 0.0
        if volumes and len(volumes) >= self.scalping_config.momentum_period:
            volume_avg = sum(volumes[-self.scalping_config.momentum_period:]) / self.scalping_config.momentum_period
            if volume_avg > 0:
                volume_momentum = volumes[-1] / volume_avg - 1
        state.volume_momentum = volume_momentum
        
        # Check momentum with volume confirmation
        if abs(price_momentum) > self.scalping_config.momentum_threshold:
            if self.scalping_config.direction in ["long", "both"] and price_momentum > 0:
                # Upward momentum
                if self.scalping_config.momentum_acceleration:
                    if len(prices) > self.scalping_config.momentum_period + 1:
                        prev_momentum = (prices[-2] - prices[-self.scalping_config.momentum_period - 1]) / self.scalping_config.momentum_period
                        if price_momentum <= prev_momentum:
                            # Decelerating - potential exit
                            return None
                
                return await self._create_scalping_signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    state=state,
                    reason=f"Upward momentum: {price_momentum:.4f}",
                    metadata={"price_momentum": price_momentum, "volume_momentum": volume_momentum},
                )
            
            elif self.scalping_config.direction in ["short", "both"] and price_momentum < 0:
                # Downward momentum
                if self.scalping_config.momentum_acceleration:
                    if len(prices) > self.scalping_config.momentum_period + 1:
                        prev_momentum = (prices[-2] - prices[-self.scalping_config.momentum_period - 1]) / self.scalping_config.momentum_period
                        if price_momentum >= prev_momentum:
                            # Decelerating - potential exit
                            return None
                
                return await self._create_scalping_signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    state=state,
                    reason=f"Downward momentum: {price_momentum:.4f}",
                    metadata={"price_momentum": price_momentum, "volume_momentum": volume_momentum},
                )
        
        return None
    
    # ========================================================================
    # MARKET MAKING SCALPING
    # ========================================================================
    
    async def _detect_market_making_signal(
        self,
        symbol: str,
        state: ScalpingState,
        bid: float,
        ask: float,
    ) -> Optional[Signal]:
        """
        Detect market making scalping signal.
        
        Args:
            symbol: Trading symbol
            state: Current state
            bid: Bid price
            ask: Ask price
            
        Returns:
            Optional[Signal]: Scalping signal
        """
        # Market making involves placing both bid and ask orders
        # This is handled separately from signal generation
        
        # Check if we have an active position
        if symbol in self.positions:
            # Update quotes
            position = self.positions[symbol]
            if position.side == OrderSide.BUY:
                # We have a long position, place sell order at ask + spread
                sell_price = ask + self.scalping_config.market_making_spread
                return await self._create_scalping_signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    state=state,
                    price=sell_price,
                    reason=f"Market making sell: {sell_price:.4f}",
                    metadata={"type": "market_making_sell"},
                )
            else:
                # We have a short position, place buy order at bid - spread
                buy_price = bid - self.scalping_config.market_making_spread
                return await self._create_scalping_signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    state=state,
                    price=buy_price,
                    reason=f"Market making buy: {buy_price:.4f}",
                    metadata={"type": "market_making_buy"},
                )
        
        # No position, place both bid and ask orders
        # This would be handled in a more sophisticated implementation
        
        return None
    
    # ========================================================================
    # COMBINED SCALPING
    # ========================================================================
    
    async def _detect_combined_scalping_signal(
        self,
        symbol: str,
        state: ScalpingState,
        prices: List[float],
        bid: float,
        ask: float,
        order_book: Optional[OrderBook] = None,
        volumes: Optional[List[float]] = None,
    ) -> Optional[Signal]:
        """
        Detect combined scalping signal using multiple methods.
        
        Args:
            symbol: Trading symbol
            state: Current state
            prices: Price series
            bid: Bid price
            ask: Ask price
            order_book: Order book data
            volumes: Volume series
            
        Returns:
            Optional[Signal]: Scalping signal
        """
        signals = []
        
        # Check momentum
        momentum_signal = await self._detect_momentum_scalping_signal(symbol, state, prices, volumes)
        if momentum_signal:
            signals.append(momentum_signal)
        
        # Check tick velocity
        tick_signal = await self._detect_tick_scalping_signal(symbol, state)
        if tick_signal:
            signals.append(tick_signal)
        
        # Check order book
        book_signal = await self._detect_order_book_signal(symbol, state, order_book)
        if book_signal:
            signals.append(book_signal)
        
        if not signals:
            return None
        
        # Combine signals (require at least 2 for entry)
        if len(signals) >= 2:
            # Use the strongest signal
            return signals[0]
        
        # Single signal with high confidence
        if len(signals) == 1:
            signal = signals[0]
            if signal.confidence > 0.7:
                return signal
        
        return None
    
    # ========================================================================
    # SIGNAL CREATION
    # ========================================================================
    
    async def _create_scalping_signal(
        self,
        symbol: str,
        signal_type: SignalType,
        state: ScalpingState,
        price: Optional[float] = None,
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Signal]:
        """
        Create a scalping signal.
        
        Args:
            symbol: Trading symbol
            signal_type: Signal type
            state: Current state
            price: Signal price
            reason: Signal reason
            metadata: Additional metadata
            
        Returns:
            Optional[Signal]: Scalping signal
        """
        # Check daily trade limit
        if self._daily_trades >= self.scalping_config.max_daily_trades:
            return None
        
        # Check position limits
        if len(self.positions) >= self.scalping_config.max_positions:
            return None
        
        if symbol in self.positions:
            return None
        
        # Check drawdown
        if self.current_drawdown > self.scalping_config.max_drawdown:
            return None
        
        # Calculate position size
        position_size = self.scalping_config.position_size
        
        # Adjust for volatility
        if len(self._price_history.get(symbol, deque())) > 10:
            price_volatility = np.std(list(self._price_history[symbol])[-10:])
            if price_volatility > 0:
                position_size = min(position_size, self.scalping_config.max_position_size * 0.5 / price_volatility)
        
        position_size = max(0, min(position_size, self.scalping_config.max_position_size))
        
        # Calculate price
        if price is None:
            price = state.current_price
        
        # Determine signal strength
        confidence = self._calculate_scalping_confidence(state, signal_type)
        strength = self._determine_signal_strength(confidence)
        
        # Calculate stop loss and take profit
        if signal_type == SignalType.BUY:
            stop_loss = price * (1 - self.scalping_config.stop_loss_pct)
            take_profit = price * (1 + self.scalping_config.take_profit_pct)
        else:
            stop_loss = price * (1 + self.scalping_config.stop_loss_pct)
            take_profit = price * (1 - self.scalping_config.take_profit_pct)
        
        # Update state
        state.total_trades += 1
        state.daily_trades += 1
        state.last_trade_time = datetime.utcnow()
        self._daily_trades += 1
        
        self._scalping_stats["total_signals"] += 1
        self._scalping_stats["valid_signals"] += 1
        
        # Create signal
        signal = Signal(
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            confidence=confidence,
            price=price,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=datetime.utcnow(),
            metadata={
                **metadata,
                "reason": reason,
                "scalping_type": self.scalping_config.scalping_type.value,
                "state": {
                    "spread": state.spread,
                    "imbalance": state.imbalance,
                    "price_momentum": state.price_momentum,
                    "tick_velocity": state.tick_velocity,
                },
            },
        )
        
        self.logger.info(
            f"Scalping signal: {signal_type.value} {symbol} @ {price:.4f} "
            f"(size: {position_size:.2f}, confidence: {confidence:.2f}) - {reason}"
        )
        
        return signal
    
    def _calculate_scalping_confidence(
        self,
        state: ScalpingState,
        signal_type: SignalType,
    ) -> float:
        """
        Calculate confidence for scalping signal.
        
        Args:
            state: Current state
            signal_type: Signal type
            
        Returns:
            float: Confidence level (0-1)
        """
        confidence = 0.6  # Base confidence
        
        # Add confidence based on multiple factors
        # Spread tightness
        if state.spread > 0:
            spread_ratio = state.spread / self.scalping_config.spread_threshold
            if spread_ratio < 0.5:
                confidence += 0.1
        
        # Order book imbalance
        if state.imbalance > 0:
            imbalance_strength = abs(state.imbalance - 0.5) * 2
            confidence += min(imbalance_strength * 0.1, 0.15)
        
        # Momentum strength
        if abs(state.price_momentum) > 0:
            momentum_strength = min(abs(state.price_momentum) / self.scalping_config.momentum_threshold, 1.0)
            confidence += momentum_strength * 0.1
        
        # Tick velocity
        if abs(state.tick_velocity) > 0:
            tick_strength = min(abs(state.tick_velocity) / self.scalping_config.tick_threshold, 1.0)
            confidence += tick_strength * 0.05
        
        return min(0.95, confidence)
    
    def _determine_signal_strength(self, confidence: float) -> SignalStrength:
        """Determine signal strength based on confidence."""
        if confidence >= 0.85:
            return SignalStrength.STRONG
        elif confidence >= 0.7:
            return SignalStrength.MEDIUM
        else:
            return SignalStrength.WEAK
    
    # ========================================================================
    # SIGNAL GENERATION
    # ========================================================================
    
    async def generate_signal(
        self,
        market_data: List[MarketData],
        order_book: Optional[OrderBook] = None,
    ) -> Optional[Signal]:
        """
        Generate a trading signal based on scalping logic.
        
        Args:
            market_data: Market data
            order_book: Optional order book data
            
        Returns:
            Optional[Signal]: Trading signal
        """
        if not market_data:
            return None
        
        symbol = self.config.symbol or market_data[0].symbol
        
        # Extract data
        prices = [c.close for c in market_data if c.symbol == symbol]
        volumes = [c.volume for c in market_data if c.symbol == symbol] if market_data else None
        bids = [c.bid for c in market_data if c.symbol == symbol] if market_data else None
        asks = [c.ask for c in market_data if c.symbol == symbol] if market_data else None
        
        if not prices:
            return None
        
        current_price = prices[-1]
        current_bid = bids[-1] if bids else current_price * 0.999
        current_ask = asks[-1] if asks else current_price * 1.001
        
        # Initialize state
        if symbol not in self._states:
            self._states[symbol] = ScalpingState(symbol=symbol, current_price=current_price)
        
        state = self._states[symbol]
        state.current_price = current_price
        
        # Update data storage
        if symbol not in self._price_history:
            self._price_history[symbol] = deque(maxlen=100)
        self._price_history[symbol].append(current_price)
        
        if volumes:
            if symbol not in self._volume_history:
                self._volume_history[symbol] = deque(maxlen=100)
            self._volume_history[symbol].append(volumes[-1])
        
        # Update tick data if available
        if hasattr(market_data[-1], 'tick') and market_data[-1].tick:
            if symbol not in self._tick_history:
                self._tick_history[symbol] = deque(maxlen=50)
            self._tick_history[symbol].append(market_data[-1].tick)
            state.tick_count += 1
        
        # Detect signals based on scalping type
        scalping_type = self.scalping_config.scalping_type
        
        signal = None
        
        if scalping_type == ScalpingType.TICK:
            signal = await self._detect_tick_scalping_signal(symbol, state)
        
        elif scalping_type == ScalpingType.ORDER_BOOK:
            signal = await self._detect_order_book_signal(symbol, state, order_book)
        
        elif scalping_type == ScalpingType.SPREAD:
            signal = await self._detect_spread_scalping_signal(symbol, state, current_bid, current_ask)
        
        elif scalping_type == ScalpingType.MOMENTUM:
            signal = await self._detect_momentum_scalping_signal(symbol, state, prices, volumes)
        
        elif scalping_type == ScalpingType.MARKET_MAKING:
            signal = await self._detect_market_making_signal(symbol, state, current_bid, current_ask)
        
        elif scalping_type == ScalpingType.COMBINED:
            signal = await self._detect_combined_scalping_signal(
                symbol, state, prices, current_bid, current_ask, order_book, volumes
            )
        
        # Check if we have an existing position that needs to be closed
        if not signal and symbol in self.positions:
            # Check if position holding period exceeded
            position = self.positions[symbol]
            if hasattr(position, 'entry_time'):
                bars_held = len(self._price_history[symbol]) - list(self._price_history[symbol]).index(position.entry_time) if position.entry_time in self._price_history[symbol] else 0
                if bars_held >= self.scalping_config.max_holding_bars:
                    signal = Signal(
                        symbol=symbol,
                        signal_type=SignalType.CLOSE,
                        strength=SignalStrength.MEDIUM,
                        confidence=0.8,
                        price=current_price,
                        timestamp=datetime.utcnow(),
                        metadata={"reason": "max_holding_period"},
                    )
        
        return signal
    
    # ========================================================================
    # TRADE HANDLING
    # ========================================================================
    
    async def on_trade(self, trade: Trade) -> None:
        """
        Handle completed trade.
        
        Args:
            trade: Completed trade
        """
        await super().on_trade(trade)
        
        pnl = trade.pnl or 0.0
        
        # Update state
        for state in self._states.values():
            if state.symbol == trade.symbol:
                state.total_trades += 1
                if pnl > 0:
                    state.winning_trades += 1
                    self._scalping_stats["winning_trades"] += 1
                else:
                    state.losing_trades += 1
                    self._scalping_stats["losing_trades"] += 1
                state.total_pnl += pnl
                
                # Update stats
                self._scalping_stats["trades_executed"] += 1
                
                # Calculate pips
                pips = abs(pnl) / trade.quantity if trade.quantity > 0 else 0
                if pips > 0:
                    self._scalping_stats["avg_profit_pips"] = (
                        (self._scalping_stats["avg_profit_pips"] * (self._scalping_stats["trades_executed"] - 1) + pips)
                        / self._scalping_stats["trades_executed"]
                    )
                    if pips > self._scalping_stats["max_profit_pips"]:
                        self._scalping_stats["max_profit_pips"] = pips
                    if pips < self._scalping_stats["max_loss_pips"]:
                        self._scalping_stats["max_loss_pips"] = pips
                break
        
        self.logger.info(
            f"Scalping trade: {trade.symbol} P&L: ${pnl:.2f} "
            f"(Win rate: {self._scalping_stats['winning_trades'] / max(1, self._scalping_stats['trades_executed']) * 100:.1f}%)"
        )
    
    async def on_position_update(self, position: Position) -> None:
        """
        Handle position update.
        
        Args:
            position: Updated position
        """
        await super().on_position_update(position)
        
        # Update state
        for state in self._states.values():
            if state.symbol == position.symbol:
                # Update holding period
                if hasattr(position, 'entry_time'):
                    bars_held = len(self._price_history[position.symbol]) - list(self._price_history[position.symbol]).index(position.entry_time) if position.entry_time in self._price_history[position.symbol] else 0
                    self._scalping_stats["avg_hold_bars"] = (
                        (self._scalping_stats["avg_hold_bars"] * (self._scalping_stats["trades_executed"] - 1) + bars_held)
                        / max(1, self._scalping_stats["trades_executed"])
                    )
                break
    
    # ========================================================================
    # DAILY RESET
    # ========================================================================
    
    def check_daily_reset(self) -> None:
        """Check if daily reset is needed."""
        today = datetime.utcnow().date()
        if self._daily_date is None:
            self._daily_date = today
        elif self._daily_date != today:
            # Reset daily counters
            self._daily_date = today
            self._daily_trades = 0
            
            # Reset state daily trades
            for state in self._states.values():
                state.daily_trades = 0
            
            self.logger.info("Daily reset performed")
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def get_scalping_stats(self) -> Dict[str, Any]:
        """
        Get scalping statistics.
        
        Returns:
            Dict[str, Any]: Scalping statistics
        """
        total_trades = self._scalping_stats["trades_executed"]
        
        return {
            **self._scalping_stats,
            "win_rate": (
                self._scalping_stats["winning_trades"] / max(1, total_trades) * 100
            ),
            "profit_factor": (
                self._scalping_stats["winning_trades"] / max(1, self._scalping_stats["losing_trades"])
            ),
            "current_states": {
                symbol: {
                    "price": state.current_price,
                    "spread": state.spread,
                    "imbalance": state.imbalance,
                    "price_momentum": state.price_momentum,
                    "tick_velocity": state.tick_velocity,
                    "total_trades": state.total_trades,
                    "total_pnl": state.total_pnl,
                    "daily_trades": state.daily_trades,
                }
                for symbol, state in self._states.items()
            },
            "daily_trades": self._daily_trades,
            "daily_limit": self.scalping_config.max_daily_trades,
            "scalping_type": self.scalping_config.scalping_type.value,
        }
    
    # ========================================================================
    # STRATEGY LIFECYCLE
    # ========================================================================
    
    async def on_start(self) -> None:
        """Called when the strategy starts."""
        await super().on_start()
        self.logger.info(
            f"Scalping strategy started (type: {self.scalping_config.scalping_type.value})"
        )
    
    async def on_stop(self) -> None:
        """Called when the strategy stops."""
        await super().on_stop()
        self.logger.info("Scalping strategy stopped")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ScalpingType",
    "OrderBookSide",
    "ScalpingConfig",
    "ScalpingState",
    "ScalpingStrategy",
]
