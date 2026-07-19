# trading/exchanges/forex/__init__.py
# Nexus AI Trading System - Forex Exchange Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Nexus Forex Exchange Module

This module provides a unified interface for multiple Forex brokers and data providers,
including OANDA, FXCM, IG, Forex.com, Dukascopy, and Pepperstone.

Features:
- Unified API across multiple Forex brokers
- Real-time and historical price data
- Order execution with advanced order types
- Position management and portfolio tracking
- Risk management and position sizing
- WebSocket streaming for real-time data
- Multi-account support
- Rate limiting and error handling
- Automatic reconnection and retry logic
- Performance metrics and analytics

Architecture:
    ForexExchange (Base) -> Specific Brokers (OANDA, FXCM, etc.)
    -> ForexDataProvider (Historical & Real-time data)
    -> ForexOrderManager (Order execution & management)
    -> ForexPositionManager (Position tracking & management)
    -> ForexRiskManager (Risk calculation & position sizing)
    -> ForexStreamManager (WebSocket streaming)
    -> ForexAccountManager (Account management)
    -> ForexConverter (Currency conversion & normalization)
    -> ForexWebhookManager (Webhook notifications)
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Type, Union, Tuple, Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from decimal import Decimal

# Core exports
from trading.exchanges.forex.base import ForexExchange, ForexConfig
from trading.exchanges.forex.converter import ForexConverter
from trading.exchanges.forex.exceptions import (
    ForexError,
    ForexConnectionError,
    ForexAuthenticationError,
    ForexRateLimitError,
    ForexOrderError,
    ForexPositionError,
    ForexDataError,
    ForexInvalidSymbolError,
    ForexTimeoutError
)
from trading.exchanges.forex.utils import (
    normalize_currency_pair,
    validate_currency_pair,
    calculate_pip_value,
    calculate_position_size,
    calculate_risk_reward_ratio,
    format_forex_price,
    parse_forex_price,
    get_forex_session,
    get_forex_sessions,
    is_forex_market_open,
    get_next_forex_session_open,
    get_forex_timezone,
    convert_forex_timezone,
    calculate_forex_spread,
    calculate_forex_slippage,
    calculate_forex_commission,
    calculate_forex_swap,
    get_forex_leverage,
    get_forex_margin_requirement
)
from trading.exchanges.forex.webhook import (
    WebhookManager,
    WebhookConfig,
    WebhookPayload,
    WebhookEventType,
    WebhookProvider,
    WebhookStatus,
    WebhookPriority,
    create_webhook_manager,
    get_forex_price_alert_webhook,
    get_telegram_bot_webhook,
    get_slack_webhook,
    get_discord_webhook
)

# Broker implementations
from trading.exchanges.forex.oanda import OandaBroker
from trading.exchanges.forex.fxcm import FXCMBroker
from trading.exchanges.forex.ig import IGBroker
from trading.exchanges.forex.forexcom import ForexComBroker
from trading.exchanges.forex.dukascopy import DukascopyBroker
from trading.exchanges.forex.pepperstone import PepperstoneBroker

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# ENUMS AND TYPES
# =============================================================================

class ForexBrokerType(str, Enum):
    """Supported Forex broker types."""
    OANDA = "oanda"
    FXCM = "fxcm"
    IG = "ig"
    FOREX_COM = "forex_com"
    DUKASCOPY = "dukascopy"
    PEPPERSTONE = "pepperstone"
    CUSTOM = "custom"


class ForexOrderType(str, Enum):
    """Forex order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    MARKET_IF_TOUCHED = "market_if_touched"
    LIMIT_IF_TOUCHED = "limit_if_touched"
    TRAILING_STOP = "trailing_stop"
    TRAILING_STOP_LIMIT = "trailing_stop_limit"
    OCO = "oco"  # One Cancels Other
    OTO = "oto"  # One Triggers Other
    BRACKET = "bracket"


class ForexOrderSide(str, Enum):
    """Forex order sides."""
    BUY = "buy"
    SELL = "sell"


class ForexTimeInForce(str, Enum):
    """Time in force for orders."""
    DAY = "day"
    GTC = "gtc"  # Good Till Cancelled
    GTD = "gtd"  # Good Till Date
    IOC = "ioc"  # Immediate Or Cancel
    FOK = "fok"  # Fill Or Kill
    AT_THE_OPEN = "at_the_open"
    AT_THE_CLOSE = "at_the_close"


class ForexAccountType(str, Enum):
    """Forex account types."""
    LIVE = "live"
    DEMO = "demo"
    PRACTICE = "practice"
    PAPER = "paper"


class ForexOrderStatus(str, Enum):
    """Forex order status."""
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    TRIGGERED = "triggered"


class ForexPositionStatus(str, Enum):
    """Forex position status."""
    OPEN = "open"
    CLOSED = "closed"
    PARTIALLY_CLOSED = "partially_closed"
    PENDING_CLOSE = "pending_close"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ForexPrice:
    """Forex price data."""
    symbol: str
    bid: Decimal
    ask: Decimal
    mid: Decimal
    spread: Decimal
    timestamp: datetime
    volume: Optional[int] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    open: Optional[Decimal] = None
    close: Optional[Decimal] = None
    change: Optional[Decimal] = None
    change_percent: Optional[Decimal] = None
    
    def __post_init__(self):
        """Calculate derived fields."""
        if self.ask and self.bid:
            self.mid = (self.ask + self.bid) / 2
            self.spread = self.ask - self.bid
    
    @property
    def pip_value(self) -> Decimal:
        """Calculate pip value for this price."""
        if self.symbol.startswith('USD'):
            return Decimal('0.0001')
        elif self.symbol.startswith('JPY'):
            return Decimal('0.01')
        else:
            return Decimal('0.0001')


@dataclass
class ForexOrder:
    """Forex order data."""
    id: str
    symbol: str
    side: ForexOrderSide
    order_type: ForexOrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    limit_price: Optional[Decimal] = None
    time_in_force: ForexTimeInForce = ForexTimeInForce.GTC
    status: ForexOrderStatus = ForexOrderStatus.PENDING
    filled_quantity: Decimal = Decimal('0')
    average_price: Optional[Decimal] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    client_order_id: Optional[str] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.status == ForexOrderStatus.FILLED
    
    @property
    def is_pending(self) -> bool:
        """Check if order is pending."""
        return self.status == ForexOrderStatus.PENDING
    
    @property
    def remaining_quantity(self) -> Decimal:
        """Get remaining quantity to fill."""
        return self.quantity - self.filled_quantity


@dataclass
class ForexPosition:
    """Forex position data."""
    id: str
    symbol: str
    side: ForexOrderSide
    quantity: Decimal
    open_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal = Decimal('0')
    total_pnl: Decimal = Decimal('0')
    status: ForexPositionStatus = ForexPositionStatus.OPEN
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    trailing_stop: Optional[Decimal] = None
    opened_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate PnL."""
        if self.current_price and self.open_price:
            price_diff = self.current_price - self.open_price
            if self.side == ForexOrderSide.BUY:
                pnl = price_diff * self.quantity
            else:
                pnl = -price_diff * self.quantity
            self.unrealized_pnl = pnl
            self.total_pnl = self.realized_pnl + self.unrealized_pnl


@dataclass
class ForexAccount:
    """Forex account data."""
    id: str
    type: ForexAccountType
    balance: Decimal
    equity: Decimal
    margin_used: Decimal
    margin_available: Decimal
    margin_ratio: Decimal
    open_positions: List[ForexPosition] = field(default_factory=list)
    orders: List[ForexOrder] = field(default_factory=list)
    total_pnl: Decimal = Decimal('0')
    daily_pnl: Decimal = Decimal('0')
    weekly_pnl: Decimal = Decimal('0')
    monthly_pnl: Decimal = Decimal('0')
    yearly_pnl: Decimal = Decimal('0')
    currency: str = "USD"
    leverage: int = 30
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# FOREX EXCHANGE FACTORY
# =============================================================================

class ForexExchangeFactory:
    """
    Factory for creating Forex exchange instances.
    
    This factory provides a unified interface to create and manage
    Forex broker connections.
    """
    
    _brokers: Dict[str, Type[ForexExchange]] = {}
    
    @classmethod
    def register_broker(cls, broker_type: str, broker_class: Type[ForexExchange]):
        """Register a broker implementation."""
        cls._brokers[broker_type.lower()] = broker_class
        logger.info(f"Registered broker: {broker_type}")
    
    @classmethod
    def get_broker_types(cls) -> List[str]:
        """Get list of registered broker types."""
        return list(cls._brokers.keys())
    
    @classmethod
    async def create_broker(
        cls,
        broker_type: Union[str, ForexBrokerType],
        config: ForexConfig,
        **kwargs
    ) -> ForexExchange:
        """
        Create a Forex broker instance.
        
        Args:
            broker_type: Type of broker to create
            config: Broker configuration
            **kwargs: Additional arguments for the broker
            
        Returns:
            ForexExchange: The created broker instance
        """
        broker_type = broker_type.value if isinstance(broker_type, ForexBrokerType) else broker_type.lower()
        
        if broker_type not in cls._brokers:
            raise ValueError(f"Unknown broker type: {broker_type}. Available: {cls.get_broker_types()}")
        
        broker_class = cls._brokers[broker_type]
        broker = broker_class(config, **kwargs)
        await broker.connect()
        return broker


# Register default brokers
def _register_default_brokers():
    """Register default broker implementations."""
    try:
        from trading.exchanges.forex.oanda import OandaBroker
        ForexExchangeFactory.register_broker('oanda', OandaBroker)
    except ImportError:
        logger.warning("OANDA broker not available")
    
    try:
        from trading.exchanges.forex.fxcm import FXCMBroker
        ForexExchangeFactory.register_broker('fxcm', FXCMBroker)
    except ImportError:
        logger.warning("FXCM broker not available")
    
    try:
        from trading.exchanges.forex.ig import IGBroker
        ForexExchangeFactory.register_broker('ig', IGBroker)
    except ImportError:
        logger.warning("IG broker not available")
    
    try:
        from trading.exchanges.forex.forexcom import ForexComBroker
        ForexExchangeFactory.register_broker('forex_com', ForexComBroker)
    except ImportError:
        logger.warning("Forex.com broker not available")
    
    try:
        from trading.exchanges.forex.dukascopy import DukascopyBroker
        ForexExchangeFactory.register_broker('dukascopy', DukascopyBroker)
    except ImportError:
        logger.warning("Dukascopy broker not available")
    
    try:
        from trading.exchanges.forex.pepperstone import PepperstoneBroker
        ForexExchangeFactory.register_broker('pepperstone', PepperstoneBroker)
    except ImportError:
        logger.warning("Pepperstone broker not available")


# =============================================================================
# MULTI-BROKER MANAGER
# =============================================================================

class ForexMultiBrokerManager:
    """
    Manage multiple Forex broker connections simultaneously.
    
    This manager provides a unified interface for trading across
    multiple Forex brokers, with features like:
    - Cross-broker arbitrage detection
    - Multi-broker order routing
    - Unified portfolio tracking
    - Risk aggregation
    - Performance comparison
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.brokers: Dict[str, ForexExchange] = {}
        self.primary_broker: Optional[str] = None
        self._initialized = False
        self._lock = asyncio.Lock()
    
    async def add_broker(
        self,
        broker_id: str,
        broker_type: Union[str, ForexBrokerType],
        config: ForexConfig,
        make_primary: bool = False
    ) -> ForexExchange:
        """
        Add a broker to the manager.
        
        Args:
            broker_id: Unique identifier for the broker
            broker_type: Type of broker
            config: Broker configuration
            make_primary: Whether to set as primary broker
            
        Returns:
            ForexExchange: The created broker instance
        """
        async with self._lock:
            if broker_id in self.brokers:
                raise ValueError(f"Broker {broker_id} already exists")
            
            broker = await ForexExchangeFactory.create_broker(
                broker_type,
                config
            )
            self.brokers[broker_id] = broker
            
            if make_primary or not self.primary_broker:
                self.primary_broker = broker_id
            
            logger.info(f"Added broker: {broker_id} ({broker_type})")
            return broker
    
    async def remove_broker(self, broker_id: str):
        """Remove a broker from the manager."""
        async with self._lock:
            if broker_id not in self.brokers:
                return
            
            await self.brokers[broker_id].disconnect()
            del self.brokers[broker_id]
            
            if self.primary_broker == broker_id:
                self.primary_broker = next(iter(self.brokers.keys())) if self.brokers else None
            
            logger.info(f"Removed broker: {broker_id}")
    
    def get_broker(self, broker_id: str) -> ForexExchange:
        """Get a broker by ID."""
        if broker_id not in self.brokers:
            raise ValueError(f"Broker {broker_id} not found")
        return self.brokers[broker_id]
    
    def get_primary_broker(self) -> ForexExchange:
        """Get the primary broker."""
        if not self.primary_broker or self.primary_broker not in self.brokers:
            raise ValueError("No primary broker set")
        return self.brokers[self.primary_broker]
    
    async def get_all_prices(self, symbols: List[str]) -> Dict[str, Dict[str, ForexPrice]]:
        """
        Get prices from all brokers for specified symbols.
        
        Returns:
            Dict mapping broker_id to symbol -> price
        """
        results = {}
        tasks = []
        broker_ids = []
        
        for broker_id, broker in self.brokers.items():
            tasks.append(broker.get_prices(symbols))
            broker_ids.append(broker_id)
        
        prices_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        for broker_id, prices in zip(broker_ids, prices_list):
            if isinstance(prices, Exception):
                logger.error(f"Error getting prices from {broker_id}: {prices}")
                results[broker_id] = {}
            else:
                results[broker_id] = prices
        
        return results
    
    async def find_arbitrage_opportunities(
        self,
        symbols: List[str],
        min_spread_pips: Decimal = Decimal('0.0001')
    ) -> List[Dict[str, Any]]:
        """
        Find arbitrage opportunities across brokers.
        
        Args:
            symbols: List of currency pairs to check
            min_spread_pips: Minimum spread in pips to consider
            
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        prices_by_broker = await self.get_all_prices(symbols)
        
        for symbol in symbols:
            broker_prices = []
            for broker_id, prices in prices_by_broker.items():
                if symbol in prices:
                    broker_prices.append((broker_id, prices[symbol]))
            
            if len(broker_prices) < 2:
                continue
            
            # Find lowest ask and highest bid
            lowest_ask = min(broker_prices, key=lambda x: x[1].ask)
            highest_bid = max(broker_prices, key=lambda x: x[1].bid)
            
            # Calculate spread
            spread = highest_bid[1].bid - lowest_ask[1].ask
            
            if spread > 0 and spread >= min_spread_pips:
                opportunities.append({
                    "symbol": symbol,
                    "buy_broker": lowest_ask[0],
                    "buy_price": lowest_ask[1].ask,
                    "sell_broker": highest_bid[0],
                    "sell_price": highest_bid[1].bid,
                    "spread": spread,
                    "spread_pips": spread / Decimal('0.0001'),
                    "timestamp": datetime.utcnow()
                })
        
        return opportunities
    
    async def get_aggregated_portfolio(self) -> Dict[str, ForexPosition]:
        """
        Get aggregated portfolio across all brokers.
        
        Returns:
            Dict mapping symbol to combined position
        """
        all_positions = {}
        
        for broker_id, broker in self.brokers.items():
            positions = await broker.get_positions()
            for pos in positions:
                if pos.symbol not in all_positions:
                    all_positions[pos.symbol] = []
                all_positions[pos.symbol].append((broker_id, pos))
        
        aggregated = {}
        for symbol, positions in all_positions.items():
            total_quantity = Decimal('0')
            total_pnl = Decimal('0')
            
            for broker_id, pos in positions:
                if pos.side == ForexOrderSide.BUY:
                    total_quantity += pos.quantity
                else:
                    total_quantity -= pos.quantity
                total_pnl += pos.total_pnl
            
            if total_quantity != 0:
                # Determine overall side
                side = ForexOrderSide.BUY if total_quantity > 0 else ForexOrderSide.SELL
                # Create aggregated position
                from trading.exchanges.forex.base import ForexPosition as BasePosition
                aggregated[symbol] = BasePosition(
                    id=f"aggregated_{symbol}",
                    symbol=symbol,
                    side=side,
                    quantity=abs(total_quantity),
                    open_price=Decimal('0'),  # Weighted average would be better
                    current_price=Decimal('0'),  # Need to get current price
                    unrealized_pnl=Decimal('0'),
                    realized_pnl=Decimal('0'),
                    total_pnl=total_pnl,
                    status=ForexPositionStatus.OPEN,
                    opened_at=datetime.utcnow(),
                    metadata={"aggregated": True}
                )
        
        return aggregated


# =============================================================================
# ANALYTICS AND PERFORMANCE
# =============================================================================

class ForexAnalytics:
    """
    Forex trading analytics and performance metrics.
    
    Provides advanced analytics for Forex trading including:
    - Win/Loss ratio
    - Average profit/loss
    - Sharpe ratio
    - Maximum drawdown
    - Profit factor
    - Calmar ratio
    - Sortino ratio
    - Expectancy
    - Recovery factor
    """
    
    def __init__(self, trades: List[Dict[str, Any]] = None):
        self.trades = trades or []
        self._metrics_cache = {}
    
    def add_trade(self, trade: Dict[str, Any]):
        """Add a trade to the analytics."""
        self.trades.append(trade)
        self._metrics_cache.clear()
    
    @property
    def winning_trades(self) -> List[Dict[str, Any]]:
        """Get all winning trades."""
        return [t for t in self.trades if t.get('pnl', 0) > 0]
    
    @property
    def losing_trades(self) -> List[Dict[str, Any]]:
        """Get all losing trades."""
        return [t for t in self.trades if t.get('pnl', 0) < 0]
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if not self.trades:
            return 0.0
        return len(self.winning_trades) / len(self.trades)
    
    @property
    def total_pnl(self) -> Decimal:
        """Calculate total P&L."""
        return sum(Decimal(str(t.get('pnl', 0))) for t in self.trades)
    
    @property
    def average_win(self) -> Decimal:
        """Calculate average winning trade."""
        if not self.winning_trades:
            return Decimal('0')
        return sum(Decimal(str(t.get('pnl', 0))) for t in self.winning_trades) / len(self.winning_trades)
    
    @property
    def average_loss(self) -> Decimal:
        """Calculate average losing trade."""
        if not self.losing_trades:
            return Decimal('0')
        return sum(Decimal(str(t.get('pnl', 0))) for t in self.losing_trades) / len(self.losing_trades)
    
    @property
    def profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)."""
        gross_profit = sum(Decimal(str(t.get('pnl', 0))) for t in self.winning_trades)
        gross_loss = abs(sum(Decimal(str(t.get('pnl', 0))) for t in self.losing_trades))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return float(gross_profit / gross_loss)
    
    @property
    def expectancy(self) -> Decimal:
        """Calculate expectancy (average return per trade)."""
        if not self.trades:
            return Decimal('0')
        return self.total_pnl / len(self.trades)
    
    @property
    def sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio."""
        if len(self.trades) < 2:
            return 0.0
        
        returns = [Decimal(str(t.get('return_pct', 0))) for t in self.trades]
        avg_return = sum(returns) / len(returns)
        
        # Calculate standard deviation of returns
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = variance ** Decimal('0.5')
        
        if std_dev == 0:
            return 0.0
        
        return float((avg_return - Decimal(str(risk_free_rate))) / std_dev)
    
    @property
    def sortino_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio (downside risk)."""
        if len(self.trades) < 2:
            return 0.0
        
        returns = [Decimal(str(t.get('return_pct', 0))) for t in self.trades]
        avg_return = sum(returns) / len(returns)
        
        # Calculate downside deviation
        downside_returns = [r for r in returns if r < Decimal('0')]
        if not downside_returns:
            return float('inf') if avg_return > 0 else 0.0
        
        variance = sum((r - avg_return) ** 2 for r in downside_returns) / len(downside_returns)
        std_dev = variance ** Decimal('0.5')
        
        if std_dev == 0:
            return 0.0
        
        return float((avg_return - Decimal(str(risk_free_rate))) / std_dev)
    
    @property
    def max_drawdown(self) -> Decimal:
        """Calculate maximum drawdown."""
        if not self.trades:
            return Decimal('0')
        
        cumulative = Decimal('0')
        peak = Decimal('0')
        max_drawdown = Decimal('0')
        
        for trade in self.trades:
            cumulative += Decimal(str(trade.get('pnl', 0)))
            if cumulative > peak:
                peak = cumulative
            drawdown = cumulative - peak
            if drawdown < max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    @property
    def recovery_factor(self) -> float:
        """Calculate recovery factor (total profit / max drawdown)."""
        if self.max_drawdown == 0:
            return float('inf') if self.total_pnl > 0 else 0.0
        
        return float(self.total_pnl / abs(self.max_drawdown))
    
    @property
    def calmar_ratio(self) -> float:
        """Calculate Calmar ratio (annualized return / max drawdown)."""
        if self.max_drawdown == 0:
            return float('inf') if self.total_pnl > 0 else 0.0
        
        # Annualized return (assuming trades are daily)
        annualized_return = self.total_pnl * 365 / len(self.trades) if self.trades else 0
        return float(annualized_return / abs(self.max_drawdown))
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive summary of analytics.
        
        Returns:
            Dict containing all calculated metrics
        """
        return {
            "total_trades": len(self.trades),
            "winning_trades": len(self.winning_trades),
            "losing_trades": len(self.losing_trades),
            "win_rate": self.win_rate,
            "total_pnl": float(self.total_pnl),
            "average_win": float(self.average_win),
            "average_loss": float(self.average_loss),
            "profit_factor": self.profit_factor,
            "expectancy": float(self.expectancy),
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": float(self.max_drawdown),
            "recovery_factor": self.recovery_factor,
            "calmar_ratio": self.calmar_ratio
        }


# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

# Register default brokers when module is imported
_register_default_brokers()

# Version information
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Core classes
    'ForexExchange',
    'ForexConfig',
    'ForexPrice',
    'ForexOrder',
    'ForexPosition',
    'ForexAccount',
    
    # Factory
    'ForexExchangeFactory',
    'ForexMultiBrokerManager',
    
    # Analytics
    'ForexAnalytics',
    
    # Enums
    'ForexBrokerType',
    'ForexOrderType',
    'ForexOrderSide',
    'ForexTimeInForce',
    'ForexAccountType',
    'ForexOrderStatus',
    'ForexPositionStatus',
    
    # Broker implementations
    'OandaBroker',
    'FXCMBroker',
    'IGBroker',
    'ForexComBroker',
    'DukascopyBroker',
    'PepperstoneBroker',
    
    # Exceptions
    'ForexError',
    'ForexConnectionError',
    'ForexAuthenticationError',
    'ForexRateLimitError',
    'ForexOrderError',
    'ForexPositionError',
    'ForexDataError',
    'ForexInvalidSymbolError',
    'ForexTimeoutError',
    
    # Utils
    'normalize_currency_pair',
    'validate_currency_pair',
    'calculate_pip_value',
    'calculate_position_size',
    'calculate_risk_reward_ratio',
    'format_forex_price',
    'parse_forex_price',
    'get_forex_session',
    'get_forex_sessions',
    'is_forex_market_open',
    'get_next_forex_session_open',
    'get_forex_timezone',
    'convert_forex_timezone',
    'calculate_forex_spread',
    'calculate_forex_slippage',
    'calculate_forex_commission',
    'calculate_forex_swap',
    'get_forex_leverage',
    'get_forex_margin_requirement',
    
    # Converter
    'ForexConverter',
    
    # Webhook
    'WebhookManager',
    'WebhookConfig',
    'WebhookPayload',
    'WebhookEventType',
    'WebhookProvider',
    'WebhookStatus',
    'WebhookPriority',
    'create_webhook_manager',
    'get_forex_price_alert_webhook',
    'get_telegram_bot_webhook',
    'get_slack_webhook',
    'get_discord_webhook',
]

# Version information
__all__.extend(['__version__', '__author__', '__copyright__'])
