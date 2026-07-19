# trading/exchanges/stocks/converter.py
# Nexus AI Trading System - Stock Exchange Converter Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Stock Exchange - Data Converter Module

This module provides comprehensive data conversion and normalization utilities
for stock trading across multiple brokers including Alpaca, IBKR, TD Ameritrade,
Robinhood, and others. It handles:

- Symbol normalization between different broker formats
- Data format conversion between broker APIs and Nexus internal models
- Order type and side conversion
- Price and volume precision handling
- WebSocket message parsing and normalization
- Historical data formatting
- Decimal precision management
- Time format conversions
- Error message normalization
- Account data transformation
- Market data standardization
- Multi-broker compatibility

The converter ensures consistent data representation across the system
and handles broker-specific quirks in data formats.

Supported Brokers:
- Alpaca
- Interactive Brokers (IBKR)
- TD Ameritrade
- Robinhood
- E*TRADE
- Fidelity
- Schwab
- TradeStation
- Tradier
"""

import json
import re
from datetime import datetime, timedelta
from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Union, Tuple
from enum import Enum

from pydantic import BaseModel, Field, validator

# Import base models
from trading.exchanges.stocks.base import (
    StockOrder,
    StockOrderType,
    StockOrderSide,
    StockOrderStatus,
    StockTimeInForce,
    StockQuote,
    StockBar,
    StockTrade,
    StockPosition,
    StockAccount,
    StockAsset,
    StockExchangeType
)

# =============================================================================
# CONSTANTS
# =============================================================================

# Broker-specific symbol mappings
BROKER_SYMBOL_MAP = {
    'alpaca': {},
    'ibkr': {},
    'td_ameritrade': {},
    'robinhood': {},
    'e_trade': {},
    'fidelity': {},
    'schwab': {},
    'tradestation': {},
    'tradier': {},
}

# Standard to broker symbol mapping
STANDARD_SYMBOL_MAP = {v: k for k, v in BROKER_SYMBOL_MAP.items() for v in k.values()}

# Order type mapping across brokers
ORDER_TYPE_MAP = {
    'market': StockOrderType.MARKET,
    'limit': StockOrderType.LIMIT,
    'stop': StockOrderType.STOP,
    'stop_limit': StockOrderType.STOP_LIMIT,
    'trailing_stop': StockOrderType.TRAILING_STOP,
    'market_on_close': StockOrderType.MARKET_ON_CLOSE,
    'limit_on_close': StockOrderType.LIMIT_ON_CLOSE,
    'bracket': StockOrderType.BRACKET,
    'oco': StockOrderType.OCO,
    'oto': StockOrderType.OTO,
}

# Order status mapping
ORDER_STATUS_MAP = {
    'pending': StockOrderStatus.PENDING,
    'accepted': StockOrderStatus.ACCEPTED,
    'new': StockOrderStatus.NEW,
    'partially_filled': StockOrderStatus.PARTIALLY_FILLED,
    'filled': StockOrderStatus.FILLED,
    'done': StockOrderStatus.DONE,
    'cancelled': StockOrderStatus.CANCELLED,
    'expired': StockOrderStatus.EXPIRED,
    'rejected': StockOrderStatus.REJECTED,
    'stopped': StockOrderStatus.STOPPED,
    'suspended': StockOrderStatus.SUSPENDED,
}

# Time in force mapping
TIME_IN_FORCE_MAP = {
    'day': StockTimeInForce.DAY,
    'gtc': StockTimeInForce.GTC,
    'opg': StockTimeInForce.OPG,
    'cls': StockTimeInForce.CLS,
    'ioc': StockTimeInForce.IOC,
    'fok': StockTimeInForce.FOK,
    'gtd': StockTimeInForce.GTD,
}

# Position side mapping
POSITION_SIDE_MAP = {
    'long': 'long',
    'short': 'short',
}

# Exchange mapping
EXCHANGE_MAP = {
    'NYSE': 'NYSE',
    'NASDAQ': 'NASDAQ',
    'AMEX': 'AMEX',
    'ARCA': 'ARCA',
    'BATS': 'BATS',
    'OTC': 'OTC',
    'PINK': 'PINK',
    'CBOE': 'CBOE',
}

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class StandardOrder(BaseModel):
    """Standardized order model."""
    id: str
    client_order_id: Optional[str] = None
    symbol: str
    side: str
    order_type: str
    status: str
    time_in_force: str
    quantity: Decimal
    filled_quantity: Decimal = Decimal('0')
    remaining_quantity: Decimal = Decimal('0')
    price: Optional[Decimal] = None
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    trail_percent: Optional[Decimal] = None
    trail_price: Optional[Decimal] = None
    average_price: Optional[Decimal] = None
    fee: Decimal = Decimal('0')
    cost: Decimal = Decimal('0')
    created_at: datetime
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    extended_hours: bool = False
    order_class: str = "simple"
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def fill_rate(self) -> float:
        if self.quantity == 0:
            return 0.0
        return float(self.filled_quantity / self.quantity * 100)


class StandardQuote(BaseModel):
    """Standardized quote model."""
    symbol: str
    bid_price: Decimal
    bid_size: Decimal
    ask_price: Decimal
    ask_size: Decimal
    last_price: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    conditions: List[str] = Field(default_factory=list)
    exchange: Optional[str] = None


class StandardBar(BaseModel):
    """Standardized bar model."""
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timestamp: datetime
    vwap: Optional[Decimal] = None
    trade_count: Optional[int] = None


class StandardPosition(BaseModel):
    """Standardized position model."""
    symbol: str
    quantity: Decimal
    average_entry_price: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pl: Decimal = Decimal('0')
    unrealized_plpc: Decimal = Decimal('0')
    realized_pl: Decimal = Decimal('0')
    realized_plpc: Decimal = Decimal('0')
    change_today: Decimal = Decimal('0')
    side: Optional[str] = None
    cost_basis: Decimal = Decimal('0')
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class StandardAccount(BaseModel):
    """Standardized account model."""
    id: str
    account_number: Optional[str] = None
    name: Optional[str] = None
    status: str = "active"
    currency: str = "USD"
    buying_power: Decimal = Decimal('0')
    cash: Decimal = Decimal('0')
    equity: Decimal = Decimal('0')
    portfolio_value: Decimal = Decimal('0')
    long_market_value: Decimal = Decimal('0')
    short_market_value: Decimal = Decimal('0')
    margin_used: Decimal = Decimal('0')
    margin_available: Decimal = Decimal('0')
    multiplier: Decimal = Decimal('1')
    day_trade_count: int = 0
    pattern_day_trader: bool = False
    trade_suspended: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class StandardAsset(BaseModel):
    """Standardized asset model."""
    id: str
    symbol: str
    name: str
    exchange: str
    asset_class: str = "equity"
    status: str = "active"
    fractionable: bool = False
    marginable: bool = False
    shortable: bool = False
    tick_size: Decimal = Decimal('0.01')
    min_order_size: Optional[Decimal] = None
    max_order_size: Optional[Decimal] = None


class StandardTrade(BaseModel):
    """Standardized trade model."""
    id: str
    symbol: str
    side: str
    price: Decimal
    quantity: Decimal
    cost: Decimal
    fee: Decimal = Decimal('0')
    timestamp: datetime
    order_id: Optional[str] = None
    trade_id: Optional[str] = None


# =============================================================================
# CONVERTER CLASS
# =============================================================================

class StockConverter:
    """
    Advanced data converter for stock trading across multiple brokers.
    
    Features:
    - Bidirectional symbol normalization
    - Broker-specific data format conversion
    - Order type and side conversion
    - Decimal precision management
    - Timestamp normalization
    - WebSocket message parsing
    - Batch conversion support
    - Validation and error handling
    - Format detection and auto-conversion
    - Multi-broker compatibility
    """
    
    def __init__(self, precision: int = 4):
        """
        Initialize the converter.
        
        Args:
            precision: Default decimal precision for conversions
        """
        self.precision = precision
        self._symbol_cache = {}
        self._broker_type = None
        
        # Set decimal context
        getcontext().prec = precision + 4
        
        # Compile regex patterns
        self._symbol_pattern = re.compile(r'^[A-Z]{1,5}$')
        self._price_pattern = re.compile(r'^(\d+\.?\d*)$')
        self._volume_pattern = re.compile(r'^(\d+)$')
        
        logger.info(f"StockConverter initialized with precision {precision}")
    
    # =========================================================================
    # BROKER CONFIGURATION
    # =========================================================================
    
    def set_broker(self, broker_type: Union[str, StockExchangeType]):
        """
        Set the target broker for conversions.
        
        Args:
            broker_type: Broker type (alpaca, ibkr, etc.)
        """
        if isinstance(broker_type, StockExchangeType):
            self._broker_type = broker_type.value
        else:
            self._broker_type = broker_type.lower()
        
        logger.info(f"Broker set to: {self._broker_type}")
    
    def get_broker(self) -> Optional[str]:
        """Get the current broker type."""
        return self._broker_type
    
    # =========================================================================
    # SYMBOL CONVERSION
    # =========================================================================
    
    def normalize_symbol(self, symbol: str, broker: Optional[str] = None) -> str:
        """
        Normalize a stock symbol.
        
        Args:
            symbol: Symbol to normalize
            broker: Target broker (uses current if None)
            
        Returns:
            Normalized symbol
        """
        if not symbol:
            return ''
        
        # Check cache
        cache_key = f"{broker or self._broker_type}:{symbol}"
        if cache_key in self._symbol_cache:
            return self._symbol_cache[cache_key]
        
        # Clean symbol
        symbol = symbol.upper().strip()
        
        # Remove common suffixes
        symbol = re.sub(r'\.[A-Z]{1,3}$', '', symbol)  # Remove .XX suffix
        symbol = re.sub(r'[^A-Z0-9.]', '', symbol)
        
        # Apply broker-specific mapping
        if broker or self._broker_type:
            broker_key = broker or self._broker_type
            if broker_key in BROKER_SYMBOL_MAP:
                if symbol in BROKER_SYMBOL_MAP[broker_key]:
                    symbol = BROKER_SYMBOL_MAP[broker_key][symbol]
        
        # Cache result
        self._symbol_cache[cache_key] = symbol
        return symbol
    
    def to_broker_symbol(self, symbol: str, broker: Optional[str] = None) -> str:
        """
        Convert standard symbol to broker-specific format.
        
        Args:
            symbol: Standard symbol
            broker: Target broker (uses current if None)
            
        Returns:
            Broker-specific symbol
        """
        if not symbol:
            return ''
        
        symbol = symbol.upper().strip()
        
        broker_key = broker or self._broker_type
        if broker_key and broker_key in STANDARD_SYMBOL_MAP:
            if symbol in STANDARD_SYMBOL_MAP[broker_key]:
                return STANDARD_SYMBOL_MAP[broker_key][symbol]
        
        return symbol
    
    def validate_symbol(self, symbol: str) -> bool:
        """
        Validate a stock symbol.
        
        Args:
            symbol: Symbol to validate
            
        Returns:
            True if valid
        """
        if not symbol:
            return False
        return bool(self._symbol_pattern.match(symbol.upper().strip()))
    
    # =========================================================================
    # ORDER CONVERSION
    # =========================================================================
    
    def from_broker_order(self, broker_order: Dict[str, Any], broker: Optional[str] = None) -> StandardOrder:
        """
        Convert broker-specific order to standard format.
        
        Args:
            broker_order: Broker order data
            broker: Broker type (uses current if None)
            
        Returns:
            Standardized order
        """
        broker_key = broker or self._broker_type or 'alpaca'
        
        # Default parsing for Alpaca-style order
        if broker_key == 'alpaca':
            return self._parse_alpaca_order(broker_order)
        elif broker_key == 'ibkr':
            return self._parse_ibkr_order(broker_order)
        elif broker_key == 'td_ameritrade':
            return self._parse_td_order(broker_order)
        elif broker_key == 'robinhood':
            return self._parse_robinhood_order(broker_order)
        else:
            return self._parse_generic_order(broker_order)
    
    def _parse_alpaca_order(self, data: Dict[str, Any]) -> StandardOrder:
        """Parse Alpaca order."""
        return StandardOrder(
            id=data.get('id', ''),
            client_order_id=data.get('client_order_id'),
            symbol=self.normalize_symbol(data.get('symbol', ''), 'alpaca'),
            side=data.get('side', 'buy'),
            order_type=data.get('type', 'limit'),
            status=data.get('status', 'pending'),
            time_in_force=data.get('time_in_force', 'day'),
            quantity=Decimal(str(data.get('qty', 0))),
            filled_quantity=Decimal(str(data.get('filled_qty', 0))),
            remaining_quantity=Decimal(str(data.get('filled_qty', 0))),
            price=Decimal(str(data.get('limit_price', 0))) if data.get('limit_price') else None,
            limit_price=Decimal(str(data.get('limit_price', 0))) if data.get('limit_price') else None,
            stop_price=Decimal(str(data.get('stop_price', 0))) if data.get('stop_price') else None,
            trail_percent=Decimal(str(data.get('trail_percent', 0))) if data.get('trail_percent') else None,
            trail_price=Decimal(str(data.get('trail_price', 0))) if data.get('trail_price') else None,
            average_price=Decimal(str(data.get('filled_avg_price', 0))) if data.get('filled_avg_price') else None,
            fee=Decimal(str(data.get('fee', 0))),
            cost=Decimal(str(data.get('filled_avg_price', 0))) * Decimal(str(data.get('filled_qty', 0))) if data.get('filled_avg_price') else Decimal('0'),
            created_at=self._parse_timestamp(data.get('created_at')),
            updated_at=self._parse_timestamp(data.get('updated_at')) if data.get('updated_at') else None,
            expires_at=self._parse_timestamp(data.get('expires_at')) if data.get('expires_at') else None,
            extended_hours=data.get('extended_hours', False),
            order_class=data.get('order_class', 'simple'),
            metadata=data
        )
    
    def _parse_ibkr_order(self, data: Dict[str, Any]) -> StandardOrder:
        """Parse Interactive Brokers order."""
        return StandardOrder(
            id=str(data.get('orderId', '')),
            client_order_id=str(data.get('orderRef', '')),
            symbol=self.normalize_symbol(data.get('symbol', ''), 'ibkr'),
            side='buy' if data.get('action') == 'BUY' else 'sell',
            order_type=data.get('orderType', 'LMT').lower(),
            status=self._map_ibkr_status(data.get('orderStatus', '')),
            time_in_force=data.get('tif', 'DAY').lower(),
            quantity=Decimal(str(data.get('totalQuantity', 0))),
            filled_quantity=Decimal(str(data.get('filledQuantity', 0))),
            remaining_quantity=Decimal(str(data.get('remainingQuantity', 0))),
            price=Decimal(str(data.get('limitPrice', 0))) if data.get('limitPrice') else None,
            limit_price=Decimal(str(data.get('limitPrice', 0))) if data.get('limitPrice') else None,
            stop_price=Decimal(str(data.get('stopPrice', 0))) if data.get('stopPrice') else None,
            average_price=Decimal(str(data.get('avgFillPrice', 0))) if data.get('avgFillPrice') else None,
            created_at=self._parse_timestamp(data.get('orderTime')),
            metadata=data
        )
    
    def _parse_td_order(self, data: Dict[str, Any]) -> StandardOrder:
        """Parse TD Ameritrade order."""
        return StandardOrder(
            id=str(data.get('orderId', '')),
            symbol=self.normalize_symbol(data.get('symbol', ''), 'td_ameritrade'),
            side=data.get('orderStrategyType', '').lower(),
            order_type=data.get('orderType', 'LIMIT').lower(),
            status=data.get('status', ''),
            time_in_force=data.get('duration', 'DAY').lower(),
            quantity=Decimal(str(data.get('quantity', 0))),
            filled_quantity=Decimal(str(data.get('filledQuantity', 0))),
            price=Decimal(str(data.get('price', 0))) if data.get('price') else None,
            limit_price=Decimal(str(data.get('price', 0))) if data.get('price') else None,
            stop_price=Decimal(str(data.get('stopPrice', 0))) if data.get('stopPrice') else None,
            created_at=self._parse_timestamp(data.get('enteredTime')),
            metadata=data
        )
    
    def _parse_robinhood_order(self, data: Dict[str, Any]) -> StandardOrder:
        """Parse Robinhood order."""
        return StandardOrder(
            id=data.get('id', ''),
            symbol=self.normalize_symbol(data.get('symbol', ''), 'robinhood'),
            side=data.get('side', 'buy'),
            order_type=data.get('type', 'limit'),
            status=data.get('state', 'pending'),
            time_in_force=data.get('time_in_force', 'gtc'),
            quantity=Decimal(str(data.get('quantity', 0))),
            filled_quantity=Decimal(str(data.get('filled_quantity', 0))),
            price=Decimal(str(data.get('price', 0))) if data.get('price') else None,
            limit_price=Decimal(str(data.get('limit_price', 0))) if data.get('limit_price') else None,
            stop_price=Decimal(str(data.get('stop_price', 0))) if data.get('stop_price') else None,
            average_price=Decimal(str(data.get('average_price', 0))) if data.get('average_price') else None,
            created_at=self._parse_timestamp(data.get('created_at')),
            metadata=data
        )
    
    def _parse_generic_order(self, data: Dict[str, Any]) -> StandardOrder:
        """Parse generic order data."""
        return StandardOrder(
            id=data.get('id', ''),
            client_order_id=data.get('client_order_id'),
            symbol=self.normalize_symbol(data.get('symbol', '')),
            side=data.get('side', 'buy'),
            order_type=data.get('order_type', 'limit'),
            status=data.get('status', 'pending'),
            time_in_force=data.get('time_in_force', 'day'),
            quantity=Decimal(str(data.get('quantity', 0))),
            filled_quantity=Decimal(str(data.get('filled_quantity', 0))),
            price=Decimal(str(data.get('price', 0))) if data.get('price') else None,
            limit_price=Decimal(str(data.get('limit_price', 0))) if data.get('limit_price') else None,
            stop_price=Decimal(str(data.get('stop_price', 0))) if data.get('stop_price') else None,
            created_at=self._parse_timestamp(data.get('created_at')),
            metadata=data
        )
    
    def _map_ibkr_status(self, status: str) -> str:
        """Map IBKR status to standard status."""
        status_map = {
            'PendingSubmit': 'pending',
            'PendingCancel': 'pending',
            'Filled': 'filled',
            'Cancelled': 'cancelled',
            'Inactive': 'rejected',
            'PartiallyFilled': 'partially_filled',
        }
        return status_map.get(status, status.lower())
    
    # =========================================================================
    # QUOTE CONVERSION
    # =========================================================================
    
    def from_broker_quote(self, broker_quote: Dict[str, Any], broker: Optional[str] = None) -> StandardQuote:
        """
        Convert broker-specific quote to standard format.
        
        Args:
            broker_quote: Broker quote data
            broker: Broker type
            
        Returns:
            Standardized quote
        """
        broker_key = broker or self._broker_type or 'alpaca'
        
        if broker_key == 'alpaca':
            return self._parse_alpaca_quote(broker_quote)
        else:
            return self._parse_generic_quote(broker_quote)
    
    def _parse_alpaca_quote(self, data: Dict[str, Any]) -> StandardQuote:
        """Parse Alpaca quote."""
        return StandardQuote(
            symbol=self.normalize_symbol(data.get('symbol', ''), 'alpaca'),
            bid_price=Decimal(str(data.get('bp', 0))),
            bid_size=Decimal(str(data.get('bs', 0))),
            ask_price=Decimal(str(data.get('ap', 0))),
            ask_size=Decimal(str(data.get('as', 0))),
            timestamp=datetime.fromtimestamp(data.get('t', 0) / 1e9) if data.get('t') else datetime.utcnow(),
            conditions=data.get('c', [])
        )
    
    def _parse_generic_quote(self, data: Dict[str, Any]) -> StandardQuote:
        """Parse generic quote."""
        return StandardQuote(
            symbol=self.normalize_symbol(data.get('symbol', '')),
            bid_price=Decimal(str(data.get('bid_price', 0))),
            bid_size=Decimal(str(data.get('bid_size', 0))),
            ask_price=Decimal(str(data.get('ask_price', 0))),
            ask_size=Decimal(str(data.get('ask_size', 0))),
            last_price=Decimal(str(data.get('last_price', 0))) if data.get('last_price') else None,
            volume=Decimal(str(data.get('volume', 0))) if data.get('volume') else None,
            timestamp=self._parse_timestamp(data.get('timestamp')),
            conditions=data.get('conditions', [])
        )
    
    # =========================================================================
    # BAR CONVERSION
    # =========================================================================
    
    def from_broker_bar(self, broker_bar: Dict[str, Any], symbol: str, broker: Optional[str] = None) -> StandardBar:
        """
        Convert broker-specific bar to standard format.
        
        Args:
            broker_bar: Broker bar data
            symbol: Symbol
            broker: Broker type
            
        Returns:
            Standardized bar
        """
        broker_key = broker or self._broker_type or 'alpaca'
        
        if broker_key == 'alpaca':
            return self._parse_alpaca_bar(broker_bar, symbol)
        else:
            return self._parse_generic_bar(broker_bar, symbol)
    
    def _parse_alpaca_bar(self, data: Dict[str, Any], symbol: str) -> StandardBar:
        """Parse Alpaca bar."""
        return StandardBar(
            symbol=self.normalize_symbol(symbol, 'alpaca'),
            open=Decimal(str(data.get('o', 0))),
            high=Decimal(str(data.get('h', 0))),
            low=Decimal(str(data.get('l', 0))),
            close=Decimal(str(data.get('c', 0))),
            volume=Decimal(str(data.get('v', 0))),
            timestamp=datetime.fromtimestamp(data.get('t', 0) / 1e9) if data.get('t') else datetime.utcnow(),
            vwap=Decimal(str(data.get('vw', 0))) if data.get('vw') else None,
            trade_count=data.get('n')
        )
    
    def _parse_generic_bar(self, data: Dict[str, Any], symbol: str) -> StandardBar:
        """Parse generic bar."""
        return StandardBar(
            symbol=self.normalize_symbol(symbol),
            open=Decimal(str(data.get('open', 0))),
            high=Decimal(str(data.get('high', 0))),
            low=Decimal(str(data.get('low', 0))),
            close=Decimal(str(data.get('close', 0))),
            volume=Decimal(str(data.get('volume', 0))),
            timestamp=self._parse_timestamp(data.get('timestamp')),
            vwap=Decimal(str(data.get('vwap', 0))) if data.get('vwap') else None,
            trade_count=data.get('trade_count')
        )
    
    # =========================================================================
    # POSITION CONVERSION
    # =========================================================================
    
    def from_broker_position(self, broker_position: Dict[str, Any], broker: Optional[str] = None) -> StandardPosition:
        """
        Convert broker-specific position to standard format.
        
        Args:
            broker_position: Broker position data
            broker: Broker type
            
        Returns:
            Standardized position
        """
        broker_key = broker or self._broker_type or 'alpaca'
        
        if broker_key == 'alpaca':
            return self._parse_alpaca_position(broker_position)
        else:
            return self._parse_generic_position(broker_position)
    
    def _parse_alpaca_position(self, data: Dict[str, Any]) -> StandardPosition:
        """Parse Alpaca position."""
        quantity = Decimal(str(data.get('qty', 0)))
        
        return StandardPosition(
            symbol=self.normalize_symbol(data.get('symbol', ''), 'alpaca'),
            quantity=quantity,
            average_entry_price=Decimal(str(data.get('avg_entry_price', 0))),
            current_price=Decimal(str(data.get('current_price', 0))),
            market_value=Decimal(str(data.get('market_value', 0))),
            unrealized_pl=Decimal(str(data.get('unrealized_pl', 0))),
            unrealized_plpc=Decimal(str(data.get('unrealized_plpc', 0))),
            realized_pl=Decimal(str(data.get('realized_pl', 0))),
            realized_plpc=Decimal(str(data.get('realized_plpc', 0))),
            change_today=Decimal(str(data.get('change_today', 0))),
            side='long' if quantity > 0 else 'short',
            cost_basis=Decimal(str(data.get('cost_basis', 0)))
        )
    
    def _parse_generic_position(self, data: Dict[str, Any]) -> StandardPosition:
        """Parse generic position."""
        quantity = Decimal(str(data.get('quantity', 0)))
        
        return StandardPosition(
            symbol=self.normalize_symbol(data.get('symbol', '')),
            quantity=quantity,
            average_entry_price=Decimal(str(data.get('avg_entry_price', 0))),
            current_price=Decimal(str(data.get('current_price', 0))),
            market_value=Decimal(str(data.get('market_value', 0))),
            unrealized_pl=Decimal(str(data.get('unrealized_pl', 0))),
            side='long' if quantity > 0 else 'short',
            cost_basis=Decimal(str(data.get('cost_basis', 0)))
        )
    
    # =========================================================================
    # ACCOUNT CONVERSION
    # =========================================================================
    
    def from_broker_account(self, broker_account: Dict[str, Any], broker: Optional[str] = None) -> StandardAccount:
        """
        Convert broker-specific account to standard format.
        
        Args:
            broker_account: Broker account data
            broker: Broker type
            
        Returns:
            Standardized account
        """
        broker_key = broker or self._broker_type or 'alpaca'
        
        if broker_key == 'alpaca':
            return self._parse_alpaca_account(broker_account)
        else:
            return self._parse_generic_account(broker_account)
    
    def _parse_alpaca_account(self, data: Dict[str, Any]) -> StandardAccount:
        """Parse Alpaca account."""
        return StandardAccount(
            id=data.get('id', ''),
            account_number=data.get('account_number', ''),
            status=data.get('status', 'active'),
            currency=data.get('currency', 'USD'),
            buying_power=Decimal(str(data.get('buying_power', 0))),
            cash=Decimal(str(data.get('cash', 0))),
            equity=Decimal(str(data.get('equity', 0))),
            portfolio_value=Decimal(str(data.get('portfolio_value', 0))),
            long_market_value=Decimal(str(data.get('long_market_value', 0))),
            short_market_value=Decimal(str(data.get('short_market_value', 0))),
            multiplier=Decimal(str(data.get('multiplier', 1))),
            day_trade_count=data.get('day_trade_count', 0),
            pattern_day_trader=data.get('pattern_day_trader', False),
            trade_suspended=data.get('trade_suspended', False)
        )
    
    def _parse_generic_account(self, data: Dict[str, Any]) -> StandardAccount:
        """Parse generic account."""
        return StandardAccount(
            id=data.get('id', ''),
            account_number=data.get('account_number'),
            name=data.get('name'),
            status=data.get('status', 'active'),
            currency=data.get('currency', 'USD'),
            buying_power=Decimal(str(data.get('buying_power', 0))),
            cash=Decimal(str(data.get('cash', 0))),
            equity=Decimal(str(data.get('equity', 0))),
            portfolio_value=Decimal(str(data.get('portfolio_value', 0))),
            day_trade_count=data.get('day_trade_count', 0)
        )
    
    # =========================================================================
    # WEBSOCKET CONVERSION
    # =========================================================================
    
    def parse_ws_message(self, message: Dict[str, Any], broker: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse and normalize WebSocket message.
        
        Args:
            message: Raw WebSocket message
            broker: Broker type
            
        Returns:
            Normalized message
        """
        broker_key = broker or self._broker_type or 'alpaca'
        
        if broker_key == 'alpaca':
            return self._parse_alpaca_ws_message(message)
        else:
            return self._parse_generic_ws_message(message)
    
    def _parse_alpaca_ws_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Alpaca WebSocket message."""
        msg_type = message.get('T', '')
        
        if msg_type == 'q':  # Quote
            return {
                'type': 'quote',
                'data': self.from_broker_quote(message, 'alpaca')
            }
        elif msg_type == 't':  # Trade
            return {
                'type': 'trade',
                'data': {
                    'symbol': self.normalize_symbol(message.get('S', ''), 'alpaca'),
                    'price': Decimal(str(message.get('p', 0))),
                    'quantity': Decimal(str(message.get('s', 0))),
                    'timestamp': datetime.fromtimestamp(message.get('t', 0) / 1e9)
                }
            }
        elif msg_type == 'b':  # Bar
            return {
                'type': 'bar',
                'data': self.from_broker_bar(message, message.get('S', ''), 'alpaca')
            }
        elif msg_type == 's':  # Snapshot
            return {
                'type': 'snapshot',
                'data': message
            }
        
        return {'type': 'unknown', 'data': message}
    
    def _parse_generic_ws_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse generic WebSocket message."""
        msg_type = message.get('type', '')
        
        if msg_type == 'quote':
            return {
                'type': 'quote',
                'data': self.from_broker_quote(message.get('data', {}))
            }
        elif msg_type == 'trade':
            return {
                'type': 'trade',
                'data': message.get('data', {})
            }
        elif msg_type == 'bar':
            return {
                'type': 'bar',
                'data': self.from_broker_bar(
                    message.get('data', {}),
                    message.get('symbol', '')
                )
            }
        
        return {'type': 'unknown', 'data': message}
    
    # =========================================================================
    # PRECISION AND VALIDATION
    # =========================================================================
    
    def format_price(self, price: Union[Decimal, float, str], precision: Optional[int] = None) -> Decimal:
        """
        Format price with appropriate precision.
        
        Args:
            price: Price value
            precision: Override precision
            
        Returns:
            Formatted price as Decimal
        """
        if isinstance(price, str):
            price = Decimal(price)
        elif isinstance(price, float):
            price = Decimal(str(price))
        
        prec = precision or self.precision
        return price.quantize(Decimal(f'1e-{prec}'), rounding=ROUND_HALF_UP)
    
    def format_quantity(
        self,
        quantity: Union[Decimal, float, str],
        precision: Optional[int] = None
    ) -> Decimal:
        """
        Format quantity with appropriate precision.
        
        Args:
            quantity: Quantity value
            precision: Override precision
            
        Returns:
            Formatted quantity as Decimal
        """
        if isinstance(quantity, str):
            quantity = Decimal(quantity)
        elif isinstance(quantity, float):
            quantity = Decimal(str(quantity))
        
        prec = precision or 0
        return quantity.quantize(Decimal(f'1e-{prec}'), rounding=ROUND_HALF_UP)
    
    def validate_price(self, price: Union[Decimal, float, str]) -> bool:
        """
        Validate price format.
        
        Args:
            price: Price to validate
            
        Returns:
            True if valid
        """
        try:
            if isinstance(price, str):
                if not self._price_pattern.match(price):
                    return False
                Decimal(price)
            elif isinstance(price, (Decimal, float)):
                if price < 0:
                    return False
            return True
        except Exception:
            return False
    
    def validate_volume(self, volume: Union[Decimal, float, str]) -> bool:
        """
        Validate volume.
        
        Args:
            volume: Volume to validate
            
        Returns:
            True if valid
        """
        try:
            if isinstance(volume, str):
                if not self._volume_pattern.match(volume):
                    return False
                Decimal(volume)
            elif isinstance(volume, (Decimal, float)):
                if volume < 0:
                    return False
            return True
        except Exception:
            return False
    
    # =========================================================================
    # TIMESTAMP CONVERSION
    # =========================================================================
    
    def _parse_timestamp(self, ts: Any) -> datetime:
        """
        Parse timestamp from various formats.
        
        Args:
            ts: Timestamp in various formats
            
        Returns:
            datetime object
        """
        if ts is None:
            return datetime.utcnow()
        
        if isinstance(ts, datetime):
            return ts
        
        if isinstance(ts, (int, float)):
            # Unix timestamp (seconds or milliseconds)
            if ts > 1e12:  # Milliseconds
                return datetime.fromtimestamp(ts / 1000)
            return datetime.fromtimestamp(ts)
        
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except ValueError:
                try:
                    return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        return datetime.strptime(ts, '%Y-%m-%dT%H:%M:%S.%fZ')
                    except ValueError:
                        return datetime.utcnow()
        
        return datetime.utcnow()
    
    def to_broker_timestamp(self, dt: datetime, broker: Optional[str] = None) -> str:
        """
        Convert datetime to broker-specific timestamp format.
        
        Args:
            dt: datetime object
            broker: Broker type
            
        Returns:
            Formatted timestamp string
        """
        broker_key = broker or self._broker_type or 'alpaca'
        
        if broker_key == 'alpaca':
            return dt.isoformat()
        elif broker_key in ['ibkr', 'td_ameritrade']:
            return dt.strftime('%Y%m%d %H:%M:%S')
        else:
            return dt.isoformat()
    
    # =========================================================================
    # BATCH CONVERSION
    # =========================================================================
    
    def batch_from_broker_orders(self, orders: List[Dict[str, Any]], broker: Optional[str] = None) -> List[StandardOrder]:
        """
        Batch convert broker orders.
        
        Args:
            orders: List of broker order data
            broker: Broker type
            
        Returns:
            List of standardized orders
        """
        return [self.from_broker_order(order, broker) for order in orders]
    
    def batch_from_broker_quotes(self, quotes: List[Dict[str, Any]], broker: Optional[str] = None) -> List[StandardQuote]:
        """
        Batch convert broker quotes.
        
        Args:
            quotes: List of broker quote data
            broker: Broker type
            
        Returns:
            List of standardized quotes
        """
        return [self.from_broker_quote(quote, broker) for quote in quotes]
    
    def batch_from_broker_bars(self, bars: List[Dict[str, Any]], symbol: str, broker: Optional[str] = None) -> List[StandardBar]:
        """
        Batch convert broker bars.
        
        Args:
            bars: List of broker bar data
            symbol: Symbol
            broker: Broker type
            
        Returns:
            List of standardized bars
        """
        return [self.from_broker_bar(bar, symbol, broker) for bar in bars]
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def clear_cache(self):
        """Clear conversion cache."""
        self._symbol_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            'symbol_cache_size': len(self._symbol_cache)
        }
    
    def get_supported_brokers(self) -> List[str]:
        """Get list of supported brokers."""
        return list(BROKER_SYMBOL_MAP.keys())


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_default_converter: Optional[StockConverter] = None


def get_converter(precision: int = 4) -> StockConverter:
    """
    Get or create default converter instance.
    
    Args:
        precision: Precision for conversion
        
    Returns:
        StockConverter instance
    """
    global _default_converter
    if _default_converter is None or _default_converter.precision != precision:
        _default_converter = StockConverter(precision)
    return _default_converter


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'StockConverter',
    'StandardOrder',
    'StandardQuote',
    'StandardBar',
    'StandardPosition',
    'StandardAccount',
    'StandardAsset',
    'StandardTrade',
    'get_converter',
    'BROKER_SYMBOL_MAP',
    'STANDARD_SYMBOL_MAP',
    'ORDER_TYPE_MAP',
    'ORDER_STATUS_MAP',
    'TIME_IN_FORCE_MAP',
    'POSITION_SIDE_MAP',
    'EXCHANGE_MAP'
]
