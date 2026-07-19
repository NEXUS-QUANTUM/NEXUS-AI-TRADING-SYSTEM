# trading/exchanges/kraken/converter.py
# Nexus AI Trading System - Kraken Exchange Converter Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Kraken Exchange - Data Converter Module

This module provides comprehensive data conversion and normalization utilities
for the Kraken cryptocurrency exchange. It handles:

- Currency pair normalization between Kraken and standard formats
- Data format conversion between Kraken API and Nexus internal models
- Order type and side conversion
- Price and volume precision handling
- WebSocket message parsing and normalization
- Historical data formatting
- Decimal precision management
- Time format conversions
- Error message normalization
- Account data transformation
- Market data standardization

The converter ensures consistent data representation across the system
and handles Kraken-specific quirks in data formats.
"""

import json
import re
from datetime import datetime, timedelta
from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Union, Tuple
from enum import Enum

from pydantic import BaseModel, Field, validator

# Import base models
from trading.exchanges.kraken.base import (
    KrakenOrder,
    KrakenOrderType,
    KrakenOrderSide,
    KrakenOrderStatus,
    KrakenTimeInForce,
    KrakenTicker,
    KrakenBalance,
    KrakenTrade
)

# =============================================================================
# CONSTANTS
# =============================================================================

# Kraken to standard currency mapping
KRAKEN_CURRENCY_MAP = {
    'XBT': 'BTC',
    'XDG': 'DOGE',
    'XRP': 'XRP',
    'XLM': 'XLM',
    'XMR': 'XMR',
    'XZEC': 'ZEC',
    'XETH': 'ETH',
    'XXRP': 'XRP',
    'XXLM': 'XLM',
    'XXMR': 'XMR',
    'XDAI': 'DAI',
    'XREP': 'REP',
    'XTZ': 'XTZ',
    'XATOM': 'ATOM',
    'XALGO': 'ALGO',
    'XFLOW': 'FLOW',
    'XKSM': 'KSM',
    'XDOT': 'DOT',
    'XSOL': 'SOL',
    'XAVA': 'AVA',
    'XMATIC': 'MATIC',
    'XLINK': 'LINK',
    'XUNI': 'UNI',
    'XAUD': 'AUD',
    'XCAD': 'CAD',
    'XCHF': 'CHF',
    'XEUR': 'EUR',
    'XGBP': 'GBP',
    'XJPY': 'JPY',
    'XNZD': 'NZD',
    'XUSD': 'USD',
    'XXBT': 'BTC',
    'ZUSD': 'USD',
    'ZEUR': 'EUR',
    'ZGBP': 'GBP',
    'ZCAD': 'CAD',
    'ZCHF': 'CHF',
    'ZJPY': 'JPY',
    'ZAUD': 'AUD',
    'ZNZD': 'NZD',
}

# Standard to Kraken currency mapping
STANDARD_CURRENCY_MAP = {v: k for k, v in KRAKEN_CURRENCY_MAP.items()}

# Kraken pair format conversions
KRAKEN_PAIR_MAP = {
    # BTC pairs
    'XBTUSD': 'BTC/USD',
    'XBTUSDT': 'BTC/USDT',
    'XBTEUR': 'BTC/EUR',
    'XBTGBP': 'BTC/GBP',
    'XBTJPY': 'BTC/JPY',
    'XBTCAD': 'BTC/CAD',
    'XBTCHF': 'BTC/CHF',
    'XBTAUD': 'BTC/AUD',
    'XBTNZD': 'BTC/NZD',
    'XBTSGD': 'BTC/SGD',
    'XBTHKD': 'BTC/HKD',
    'XBTTRY': 'BTC/TRY',
    'XBTZAR': 'BTC/ZAR',
    'XBTBRL': 'BTC/BRL',
    
    # ETH pairs
    'ETHUSD': 'ETH/USD',
    'ETHUSDT': 'ETH/USDT',
    'ETHEUR': 'ETH/EUR',
    'ETHGBP': 'ETH/GBP',
    'ETHJPY': 'ETH/JPY',
    'ETHCAD': 'ETH/CAD',
    'ETHCHF': 'ETH/CHF',
    'ETHAUD': 'ETH/AUD',
    'ETHNZD': 'ETH/NZD',
    'ETHBTC': 'ETH/BTC',
    'ETHSGD': 'ETH/SGD',
    'ETHHKD': 'ETH/HKD',
    'ETHTRY': 'ETH/TRY',
    'ETHZAR': 'ETH/ZAR',
    'ETHBRL': 'ETH/BRL',
    
    # XRP pairs
    'XRPUSD': 'XRP/USD',
    'XRPUSDT': 'XRP/USDT',
    'XRPEUR': 'XRP/EUR',
    'XRPGBP': 'XRP/GBP',
    'XRPJPY': 'XRP/JPY',
    'XRPCAD': 'XRP/CAD',
    'XRPCHF': 'XRP/CHF',
    'XRPAUD': 'XRP/AUD',
    'XRPNZD': 'XRP/NZD',
    'XRPBTC': 'XRP/BTC',
    
    # LTC pairs
    'LTCUSD': 'LTC/USD',
    'LTCUSDT': 'LTC/USDT',
    'LTCEUR': 'LTC/EUR',
    'LTCGBP': 'LTC/GBP',
    'LTCJPY': 'LTC/JPY',
    'LTCCAD': 'LTC/CAD',
    'LTCCHF': 'LTC/CHF',
    'LTCAUD': 'LTC/AUD',
    'LTCNZD': 'LTC/NZD',
    'LTCBTC': 'LTC/BTC',
    
    # ADA pairs
    'ADAUSD': 'ADA/USD',
    'ADAUSDT': 'ADA/USDT',
    'ADAEUR': 'ADA/EUR',
    'ADAGBP': 'ADA/GBP',
    'ADAJPY': 'ADA/JPY',
    'ADACAD': 'ADA/CAD',
    'ADACHC': 'ADA/CHF',
    'ADAAUD': 'ADA/AUD',
    'ADANZD': 'ADA/NZD',
    'ADABTC': 'ADA/BTC',
    
    # DOT pairs
    'DOTUSD': 'DOT/USD',
    'DOTUSDT': 'DOT/USDT',
    'DOTEUR': 'DOT/EUR',
    'DOTGBP': 'DOT/GBP',
    'DOTJPY': 'DOT/JPY',
    'DOTCAD': 'DOT/CAD',
    'DOTCHF': 'DOT/CHF',
    'DOTAUD': 'DOT/AUD',
    'DOTNZD': 'DOT/NZD',
    'DOTBTC': 'DOT/BTC',
    
    # SOL pairs
    'SOLUSD': 'SOL/USD',
    'SOLUSDT': 'SOL/USDT',
    'SOLEUR': 'SOL/EUR',
    'SOLGBP': 'SOL/GBP',
    'SOLJPY': 'SOL/JPY',
    'SOLCAD': 'SOL/CAD',
    'SOLCHF': 'SOL/CHF',
    'SOLAUD': 'SOL/AUD',
    'SOLNZD': 'SOL/NZD',
    'SOLBTC': 'SOL/BTC',
}

# Reverse mapping
STANDARD_PAIR_MAP = {v: k for k, v in KRAKEN_PAIR_MAP.items()}

# Order type mapping
ORDER_TYPE_MAP = {
    'market': KrakenOrderType.MARKET,
    'limit': KrakenOrderType.LIMIT,
    'stop-loss': KrakenOrderType.STOP_LOSS,
    'take-profit': KrakenOrderType.TAKE_PROFIT,
    'stop-loss-limit': KrakenOrderType.STOP_LOSS_LIMIT,
    'take-profit-limit': KrakenOrderType.TAKE_PROFIT_LIMIT,
    'settle-position': KrakenOrderType.SETTLE_POSITION,
}

# Order status mapping
ORDER_STATUS_MAP = {
    'pending': KrakenOrderStatus.PENDING,
    'open': KrakenOrderStatus.OPEN,
    'closed': KrakenOrderStatus.CLOSED,
    'cancelled': KrakenOrderStatus.CANCELLED,
    'expired': KrakenOrderStatus.EXPIRED,
    'rejected': KrakenOrderStatus.REJECTED,
    'partially': KrakenOrderStatus.PARTIALLY_FILLED,
    'filled': KrakenOrderStatus.FILLED,
}

# Time in force mapping
TIME_IN_FORCE_MAP = {
    'GTC': KrakenTimeInForce.GTC,
    'IOC': KrakenTimeInForce.IOC,
    'FOK': KrakenTimeInForce.FOK,
    'DAY': KrakenTimeInForce.DAY,
    'GTX': KrakenTimeInForce.GTX,
}

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class StandardOrder(BaseModel):
    """Standardized order model."""
    id: str
    symbol: str  # Standard format: BTC/USD
    side: str  # buy or sell
    type: str  # market, limit, stop_loss, etc.
    price: Decimal
    quantity: Decimal
    filled_quantity: Decimal
    average_price: Optional[Decimal] = None
    status: str
    time_in_force: str
    fee: Decimal = Decimal('0')
    cost: Decimal = Decimal('0')
    created_at: datetime
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StandardTicker(BaseModel):
    """Standardized ticker model."""
    symbol: str  # Standard format: BTC/USD
    bid: Decimal
    ask: Decimal
    last: Decimal
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    quote_volume: Optional[Decimal] = None
    change: Optional[Decimal] = None
    change_percent: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StandardBalance(BaseModel):
    """Standardized balance model."""
    currency: str
    total: Decimal
    available: Decimal
    locked: Decimal = Decimal('0')
    staked: Decimal = Decimal('0')
    earned: Decimal = Decimal('0')
    value_usd: Optional[Decimal] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


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
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StandardPosition(BaseModel):
    """Standardized position model."""
    id: str
    symbol: str
    side: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Optional[Decimal] = None
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    total_pnl: Decimal = Decimal('0')
    liquidation_price: Optional[Decimal] = None
    margin: Decimal = Decimal('0')
    leverage: Decimal = Decimal('1')
    created_at: datetime
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# CONVERTER CLASS
# =============================================================================

class KrakenConverter:
    """
    Advanced data converter for Kraken exchange.
    
    Features:
    - Bidirectional currency pair conversion
    - Standard to Kraken format conversion
    - Kraken to standard format conversion
    - Decimal precision management
    - Timestamp normalization
    - Order data conversion
    - Ticker data conversion
    - Balance data conversion
    - Trade data conversion
    - Position data conversion
    - WebSocket message parsing
    - Batch conversion support
    - Validation and error handling
    - Format detection and auto-conversion
    
    Usage:
        converter = KrakenConverter()
        pair = converter.to_standard_pair("XBTUSD")  # Returns "BTC/USD"
        order = converter.from_kraken_order(kraken_order)
        ticker = converter.to_kraken_ticker(standard_ticker)
    """
    
    def __init__(self, precision: int = 8):
        """
        Initialize the converter.
        
        Args:
            precision: Default decimal precision for conversions
        """
        self.precision = precision
        self._currency_cache = {}
        self._pair_cache = {}
        
        # Set decimal context
        getcontext().prec = precision + 4
        
        # Compile regex patterns
        self._pair_pattern = re.compile(r'^([A-Z0-9]{2,6})([A-Z0-9]{2,6})$')
        self._currency_pattern = re.compile(r'^[A-Z0-9]{3,5}$')
        self._price_pattern = re.compile(r'^(\d+\.?\d*)$')
        
        logger.info(f"KrakenConverter initialized with precision {precision}")
    
    # =========================================================================
    # CURRENCY CONVERSION
    # =========================================================================
    
    def to_standard_currency(self, kraken_currency: str) -> str:
        """
        Convert Kraken currency code to standard format.
        
        Args:
            kraken_currency: Kraken currency code (e.g., 'XBT', 'XXRP')
            
        Returns:
            Standard currency code (e.g., 'BTC', 'XRP')
        """
        if not kraken_currency:
            return ''
        
        # Check cache
        if kraken_currency in self._currency_cache:
            return self._currency_cache[kraken_currency]
        
        # Check mapping
        if kraken_currency in KRAKEN_CURRENCY_MAP:
            result = KRAKEN_CURRENCY_MAP[kraken_currency]
            self._currency_cache[kraken_currency] = result
            return result
        
        # Remove 'X' prefix if present (common Kraken format)
        if kraken_currency.startswith('X') and len(kraken_currency) > 1:
            result = kraken_currency[1:]
            self._currency_cache[kraken_currency] = result
            return result
        
        # Remove 'Z' prefix if present (fiat currencies)
        if kraken_currency.startswith('Z') and len(kraken_currency) > 1:
            result = kraken_currency[1:]
            self._currency_cache[kraken_currency] = result
            return result
        
        # Cache and return
        self._currency_cache[kraken_currency] = kraken_currency
        return kraken_currency
    
    def to_kraken_currency(self, standard_currency: str) -> str:
        """
        Convert standard currency code to Kraken format.
        
        Args:
            standard_currency: Standard currency code (e.g., 'BTC')
            
        Returns:
            Kraken currency code (e.g., 'XBT')
        """
        if not standard_currency:
            return ''
        
        standard_currency = standard_currency.upper()
        
        # Check reverse mapping
        if standard_currency in STANDARD_CURRENCY_MAP:
            return STANDARD_CURRENCY_MAP[standard_currency]
        
        # Default: add X prefix for crypto, Z for fiat
        fiat_currencies = {'USD', 'EUR', 'GBP', 'JPY', 'CAD', 'CHF', 'AUD', 'NZD', 'SGD', 'HKD', 'TRY', 'ZAR', 'BRL'}
        if standard_currency in fiat_currencies:
            return f'Z{standard_currency}'
        else:
            return f'X{standard_currency}'
    
    # =========================================================================
    # PAIR CONVERSION
    # =========================================================================
    
    def to_standard_pair(self, kraken_pair: str) -> str:
        """
        Convert Kraken pair to standard format.
        
        Args:
            kraken_pair: Kraken pair (e.g., 'XBTUSD')
            
        Returns:
            Standard pair (e.g., 'BTC/USD')
        """
        if not kraken_pair:
            return ''
        
        # Check cache
        if kraken_pair in self._pair_cache:
            return self._pair_cache[kraken_pair]
        
        # Check mapping
        if kraken_pair in KRAKEN_PAIR_MAP:
            result = KRAKEN_PAIR_MAP[kraken_pair]
            self._pair_cache[kraken_pair] = result
            return result
        
        # Try to parse
        match = self._pair_pattern.match(kraken_pair)
        if match:
            base = self.to_standard_currency(match.group(1))
            quote = self.to_standard_currency(match.group(2))
            result = f"{base}/{quote}"
            self._pair_cache[kraken_pair] = result
            return result
        
        # Return as-is if can't parse
        self._pair_cache[kraken_pair] = kraken_pair
        return kraken_pair
    
    def to_kraken_pair(self, standard_pair: str) -> str:
        """
        Convert standard pair to Kraken format.
        
        Args:
            standard_pair: Standard pair (e.g., 'BTC/USD')
            
        Returns:
            Kraken pair (e.g., 'XBTUSD')
        """
        if not standard_pair:
            return ''
        
        # Check reverse mapping
        if standard_pair in STANDARD_PAIR_MAP:
            return STANDARD_PAIR_MAP[standard_pair]
        
        # Parse standard pair
        if '/' in standard_pair:
            base, quote = standard_pair.split('/')
            kraken_base = self.to_kraken_currency(base)
            kraken_quote = self.to_kraken_currency(quote)
            return f"{kraken_base}{kraken_quote}"
        
        # Try to parse as combined string
        match = self._pair_pattern.match(standard_pair)
        if match:
            base = match.group(1)
            quote = match.group(2)
            kraken_base = self.to_kraken_currency(base)
            kraken_quote = self.to_kraken_currency(quote)
            return f"{kraken_base}{kraken_quote}"
        
        # Return as-is
        return standard_pair
    
    def extract_pair_components(self, pair: str) -> Tuple[str, str]:
        """
        Extract base and quote currencies from a pair.
        
        Args:
            pair: Pair in either standard or Kraken format
            
        Returns:
            Tuple of (base, quote)
        """
        # Try standard format first
        if '/' in pair:
            base, quote = pair.split('/')
            return base, quote
        
        # Try Kraken format
        match = self._pair_pattern.match(pair)
        if match:
            base = self.to_standard_currency(match.group(1))
            quote = self.to_standard_currency(match.group(2))
            return base, quote
        
        raise ValueError(f"Invalid pair format: {pair}")
    
    # =========================================================================
    # ORDER CONVERSION
    # =========================================================================
    
    def from_kraken_order(self, kraken_order: KrakenOrder) -> StandardOrder:
        """
        Convert Kraken order to standard format.
        
        Args:
            kraken_order: Kraken order object
            
        Returns:
            Standardized order
        """
        return StandardOrder(
            id=kraken_order.id,
            symbol=self.to_standard_pair(kraken_order.pair),
            side=kraken_order.side.value,
            type=kraken_order.type.value,
            price=kraken_order.price,
            quantity=kraken_order.volume,
            filled_quantity=kraken_order.executed_volume,
            average_price=kraken_order.average_price,
            status=kraken_order.status.value,
            time_in_force=kraken_order.time_in_force.value,
            fee=kraken_order.fee,
            cost=kraken_order.cost,
            created_at=kraken_order.created_at,
            updated_at=kraken_order.updated_at,
            expires_at=kraken_order.expires_at,
            metadata=kraken_order.metadata
        )
    
    def to_kraken_order(
        self,
        standard_order: StandardOrder,
        pair: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Convert standard order to Kraken order parameters.
        
        Args:
            standard_order: Standardized order
            pair: Override pair (if not specified, use symbol)
            
        Returns:
            Kraken order parameters
        """
        kraken_pair = self.to_kraken_pair(pair or standard_order.symbol)
        
        # Map order type
        order_type_map = {
            'market': 'market',
            'limit': 'limit',
            'stop_loss': 'stop-loss',
            'take_profit': 'take-profit',
            'stop_loss_limit': 'stop-loss-limit',
            'take_profit_limit': 'take-profit-limit',
        }
        kraken_type = order_type_map.get(standard_order.type, 'limit')
        
        # Map time in force
        tif_map = {
            'GTC': 'GTC',
            'IOC': 'IOC',
            'FOK': 'FOK',
            'DAY': 'Day',
            'GTX': 'GTX',
        }
        kraken_tif = tif_map.get(standard_order.time_in_force, 'GTC')
        
        params = {
            'pair': kraken_pair,
            'type': standard_order.side,
            'ordertype': kraken_type,
            'volume': str(standard_order.quantity),
            'timeinforce': kraken_tif,
        }
        
        # Add price for limit orders
        if standard_order.type in ['limit', 'stop_loss_limit', 'take_profit_limit']:
            params['price'] = str(standard_order.price)
        
        # Add stop/take profit prices
        if standard_order.type in ['stop_loss', 'stop_loss_limit']:
            params['stop'] = str(standard_order.price)
        if standard_order.type in ['take_profit', 'take_profit_limit']:
            params['stop'] = str(standard_order.price)
        
        return params
    
    # =========================================================================
    # TICKER CONVERSION
    # =========================================================================
    
    def from_kraken_ticker(
        self,
        kraken_ticker: KrakenTicker
    ) -> StandardTicker:
        """
        Convert Kraken ticker to standard format.
        
        Args:
            kraken_ticker: Kraken ticker object
            
        Returns:
            Standardized ticker
        """
        return StandardTicker(
            symbol=self.to_standard_pair(kraken_ticker.pair),
            bid=kraken_ticker.bid,
            ask=kraken_ticker.ask,
            last=kraken_ticker.last,
            high=kraken_ticker.high if kraken_ticker.high != Decimal('0') else None,
            low=kraken_ticker.low if kraken_ticker.low != Decimal('0') else None,
            volume=kraken_ticker.volume if kraken_ticker.volume != Decimal('0') else None,
            quote_volume=kraken_ticker.volume_24h if kraken_ticker.volume_24h != Decimal('0') else None,
            change=kraken_ticker.change if kraken_ticker.change != Decimal('0') else None,
            change_percent=kraken_ticker.change_percent if kraken_ticker.change_percent != Decimal('0') else None,
            timestamp=kraken_ticker.timestamp
        )
    
    def to_kraken_ticker_request(self, symbol: str) -> Dict[str, str]:
        """
        Convert standard symbol to Kraken ticker request.
        
        Args:
            symbol: Standard symbol (e.g., 'BTC/USD')
            
        Returns:
            Kraken ticker request parameters
        """
        kraken_pair = self.to_kraken_pair(symbol)
        return {'pair': kraken_pair}
    
    # =========================================================================
    # BALANCE CONVERSION
    # =========================================================================
    
    def from_kraken_balance(
        self,
        kraken_balance: KrakenBalance
    ) -> StandardBalance:
        """
        Convert Kraken balance to standard format.
        
        Args:
            kraken_balance: Kraken balance object
            
        Returns:
            Standardized balance
        """
        return StandardBalance(
            currency=self.to_standard_currency(kraken_balance.currency),
            total=kraken_balance.total,
            available=kraken_balance.available,
            locked=kraken_balance.locked,
            staked=kraken_balance.staked,
            earned=kraken_balance.earned,
            updated_at=datetime.utcnow()
        )
    
    def to_kraken_balance_request(self, currencies: List[str]) -> Dict[str, str]:
        """
        Convert standard currencies to Kraken balance request.
        
        Args:
            currencies: List of standard currency codes
            
        Returns:
            Kraken balance request parameters
        """
        kraken_currencies = [self.to_kraken_currency(c) for c in currencies]
        return {'asset': ','.join(kraken_currencies)}
    
    # =========================================================================
    # TRADE CONVERSION
    # =========================================================================
    
    def from_kraken_trade(self, kraken_trade: KrakenTrade) -> StandardTrade:
        """
        Convert Kraken trade to standard format.
        
        Args:
            kraken_trade: Kraken trade object
            
        Returns:
            Standardized trade
        """
        return StandardTrade(
            id=kraken_trade.id,
            symbol=self.to_standard_pair(kraken_trade.pair),
            side=kraken_trade.side.value,
            price=kraken_trade.price,
            quantity=kraken_trade.volume,
            cost=kraken_trade.cost,
            fee=kraken_trade.fee,
            timestamp=kraken_trade.timestamp,
            order_id=kraken_trade.order_id,
            metadata=kraken_trade.metadata
        )
    
    # =========================================================================
    # POSITION CONVERSION
    # =========================================================================
    
    def from_kraken_position(
        self,
        position_data: Dict[str, Any]
    ) -> StandardPosition:
        """
        Convert Kraken position data to standard format.
        
        Args:
            position_data: Kraken position data
            
        Returns:
            Standardized position
        """
        return StandardPosition(
            id=position_data.get('id', ''),
            symbol=self.to_standard_pair(position_data.get('pair', '')),
            side='long' if float(position_data.get('vol', 0)) > 0 else 'short',
            quantity=abs(Decimal(str(position_data.get('vol', 0)))),
            entry_price=Decimal(str(position_data.get('cost', 0))),
            current_price=Decimal(str(position_data.get('price', 0))),
            unrealized_pnl=Decimal(str(position_data.get('unrealized', 0))),
            realized_pnl=Decimal(str(position_data.get('realized', 0))),
            total_pnl=Decimal(str(position_data.get('total', 0))),
            liquidation_price=Decimal(str(position_data.get('liquidation', 0))) if position_data.get('liquidation') else None,
            margin=Decimal(str(position_data.get('margin', 0))),
            leverage=Decimal(str(position_data.get('leverage', 1))),
            created_at=datetime.fromtimestamp(float(position_data.get('opentm', 0))) if position_data.get('opentm') else datetime.utcnow(),
            updated_at=datetime.fromtimestamp(float(position_data.get('closetm', 0))) if position_data.get('closetm') else None,
            metadata=position_data
        )
    
    # =========================================================================
    # WEBSOCKET CONVERSION
    # =========================================================================
    
    def parse_ws_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and normalize WebSocket message.
        
        Args:
            message: Raw WebSocket message
            
        Returns:
            Normalized message
        """
        # Check for subscription status
        if 'event' in message:
            event = message.get('event')
            if event == 'subscriptionStatus':
                return {
                    'type': 'subscription_status',
                    'status': message.get('status'),
                    'channel': message.get('channelName'),
                    'pair': self.to_standard_pair(message.get('pair', '')),
                    'error': message.get('errorMessage')
                }
            elif event == 'systemStatus':
                return {
                    'type': 'system_status',
                    'status': message.get('status'),
                    'timestamp': message.get('timestamp')
                }
            elif event == 'heartbeat':
                return {
                    'type': 'heartbeat',
                    'timestamp': datetime.utcnow().isoformat()
                }
            elif event == 'pong':
                return {
                    'type': 'pong',
                    'timestamp': datetime.utcnow().isoformat()
                }
        
        # Check for data message
        if 'channel' in message:
            channel = message.get('channel')
            data = message.get('data', [])
            
            # Normalize based on channel
            if channel == 'ticker':
                return self._normalize_ws_ticker(data, message.get('pair', ''))
            elif channel == 'ohlc':
                return self._normalize_ws_ohlc(data, message.get('pair', ''))
            elif channel == 'trade':
                return self._normalize_ws_trade(data, message.get('pair', ''))
            elif channel == 'spread':
                return self._normalize_ws_spread(data, message.get('pair', ''))
            elif channel == 'book':
                return self._normalize_ws_book(data, message.get('pair', ''))
            elif channel in ['ownTrades', 'openOrders', 'balance']:
                return self._normalize_ws_account(data, channel)
        
        return message
    
    def _normalize_ws_ticker(
        self,
        data: List[Any],
        pair: str
    ) -> Dict[str, Any]:
        """Normalize WebSocket ticker data."""
        if not data:
            return {}
        
        # Kraken ticker format: [bid, ask, last, volume, etc.]
        result = {
            'type': 'ticker',
            'pair': self.to_standard_pair(pair),
            'bid': Decimal(str(data[0] if len(data) > 0 else 0)),
            'ask': Decimal(str(data[1] if len(data) > 1 else 0)),
            'last': Decimal(str(data[2] if len(data) > 2 else 0)),
            'volume': Decimal(str(data[3] if len(data) > 3 else 0)),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if len(data) > 4:
            result['high'] = Decimal(str(data[4] if data[4] else 0))
        if len(data) > 5:
            result['low'] = Decimal(str(data[5] if data[5] else 0))
        
        return result
    
    def _normalize_ws_ohlc(
        self,
        data: List[Any],
        pair: str
    ) -> Dict[str, Any]:
        """Normalize WebSocket OHLC data."""
        if not data:
            return {}
        
        # Kraken OHLC format: [time, open, high, low, close, volume, ...]
        return {
            'type': 'ohlc',
            'pair': self.to_standard_pair(pair),
            'time': datetime.fromtimestamp(float(data[0])).isoformat() if data[0] else None,
            'open': Decimal(str(data[1] if len(data) > 1 else 0)),
            'high': Decimal(str(data[2] if len(data) > 2 else 0)),
            'low': Decimal(str(data[3] if len(data) > 3 else 0)),
            'close': Decimal(str(data[4] if len(data) > 4 else 0)),
            'volume': Decimal(str(data[5] if len(data) > 5 else 0)),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _normalize_ws_trade(
        self,
        data: List[Any],
        pair: str
    ) -> Dict[str, Any]:
        """Normalize WebSocket trade data."""
        if not data:
            return {}
        
        # Kraken trade format: [price, volume, time, side, ...]
        trades = []
        for trade in data:
            trades.append({
                'price': Decimal(str(trade[0] if len(trade) > 0 else 0)),
                'volume': Decimal(str(trade[1] if len(trade) > 1 else 0)),
                'time': datetime.fromtimestamp(float(trade[2])).isoformat() if len(trade) > 2 else None,
                'side': 'buy' if len(trade) > 3 and trade[3] == 'b' else 'sell'
            })
        
        return {
            'type': 'trade',
            'pair': self.to_standard_pair(pair),
            'trades': trades,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _normalize_ws_spread(
        self,
        data: List[Any],
        pair: str
    ) -> Dict[str, Any]:
        """Normalize WebSocket spread data."""
        if not data:
            return {}
        
        # Kraken spread format: [bid, ask, time, ...]
        return {
            'type': 'spread',
            'pair': self.to_standard_pair(pair),
            'bid': Decimal(str(data[0] if len(data) > 0 else 0)),
            'ask': Decimal(str(data[1] if len(data) > 1 else 0)),
            'time': datetime.fromtimestamp(float(data[2])).isoformat() if len(data) > 2 else None,
            'spread': Decimal(str(data[1] if len(data) > 1 else 0)) - Decimal(str(data[0] if len(data) > 0 else 0)),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _normalize_ws_book(
        self,
        data: List[Any],
        pair: str
    ) -> Dict[str, Any]:
        """Normalize WebSocket order book data."""
        if not data:
            return {}
        
        # Kraken book format: [price, volume, timestamp, ...]
        bids = []
        asks = []
        
        for entry in data:
            price = Decimal(str(entry[0] if len(entry) > 0 else 0))
            volume = Decimal(str(entry[1] if len(entry) > 1 else 0))
            time = entry[2] if len(entry) > 2 else None
            
            if volume > 0:
                bids.append({'price': price, 'volume': volume, 'time': time})
            else:
                asks.append({'price': price, 'volume': abs(volume), 'time': time})
        
        return {
            'type': 'book',
            'pair': self.to_standard_pair(pair),
            'bids': bids,
            'asks': asks,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _normalize_ws_account(
        self,
        data: List[Any],
        channel: str
    ) -> Dict[str, Any]:
        """Normalize WebSocket account data."""
        result = {
            'type': 'account_update',
            'channel': channel,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if channel == 'balance':
            # Balance update
            balances = {}
            for entry in data:
                if isinstance(entry, dict):
                    for currency, amount in entry.items():
                        balances[self.to_standard_currency(currency)] = Decimal(str(amount))
            result['balances'] = balances
        
        elif channel == 'ownTrades':
            # Trade update
            trades = []
            for entry in data:
                if isinstance(entry, dict):
                    trades.append(self.from_kraken_trade(KrakenTrade(
                        id=entry.get('id', ''),
                        pair=entry.get('pair', ''),
                        side=KrakenOrderSide(entry.get('side', 'buy')),
                        price=Decimal(str(entry.get('price', 0))),
                        volume=Decimal(str(entry.get('volume', 0))),
                        fee=Decimal(str(entry.get('fee', 0))),
                        cost=Decimal(str(entry.get('cost', 0))),
                        timestamp=datetime.fromtimestamp(float(entry.get('time', 0))) if entry.get('time') else datetime.utcnow(),
                        order_id=entry.get('order_id'),
                        metadata=entry
                    )))
            result['trades'] = trades
        
        elif channel == 'openOrders':
            # Order update
            orders = []
            for entry in data:
                if isinstance(entry, dict):
                    orders.append(self.from_kraken_order(KrakenOrder(
                        id=entry.get('id', ''),
                        pair=entry.get('pair', ''),
                        type=KrakenOrderType(entry.get('type', 'limit')),
                        side=KrakenOrderSide(entry.get('side', 'buy')),
                        status=KrakenOrderStatus(entry.get('status', 'open')),
                        price=Decimal(str(entry.get('price', 0))),
                        volume=Decimal(str(entry.get('volume', 0))),
                        executed_volume=Decimal(str(entry.get('executed', 0))),
                        average_price=Decimal(str(entry.get('avg_price', 0))),
                        fee=Decimal(str(entry.get('fee', 0))),
                        cost=Decimal(str(entry.get('cost', 0))),
                        time_in_force=KrakenTimeInForce(entry.get('timeinforce', 'GTC')),
                        created_at=datetime.fromtimestamp(float(entry.get('opentm', 0))) if entry.get('opentm') else datetime.utcnow(),
                        updated_at=datetime.fromtimestamp(float(entry.get('closetm', 0))) if entry.get('closetm') else None,
                        metadata=entry
                    )))
            result['orders'] = orders
        
        return result
    
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
        
        prec = precision or self.precision
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
    
    def validate_currency(self, currency: str) -> bool:
        """
        Validate currency code.
        
        Args:
            currency: Currency code to validate
            
        Returns:
            True if valid
        """
        if not currency:
            return False
        return bool(self._currency_pattern.match(currency))
    
    def validate_pair(self, pair: str) -> bool:
        """
        Validate pair format.
        
        Args:
            pair: Pair to validate
            
        Returns:
            True if valid
        """
        if not pair:
            return False
        
        # Check standard format
        if '/' in pair:
            base, quote = pair.split('/')
            return self.validate_currency(base) and self.validate_currency(quote)
        
        # Check Kraken format
        return bool(self._pair_pattern.match(pair))
    
    # =========================================================================
    # BATCH CONVERSION
    # =========================================================================
    
    def batch_convert_pairs(self, pairs: List[str]) -> Dict[str, str]:
        """
        Batch convert pairs to standard format.
        
        Args:
            pairs: List of pairs to convert
            
        Returns:
            Dict mapping original to converted
        """
        result = {}
        for pair in pairs:
            result[pair] = self.to_standard_pair(pair)
        return result
    
    def batch_from_kraken_orders(self, orders: List[KrakenOrder]) -> List[StandardOrder]:
        """
        Batch convert Kraken orders.
        
        Args:
            orders: List of Kraken orders
            
        Returns:
            List of standardized orders
        """
        return [self.from_kraken_order(order) for order in orders]
    
    def batch_from_kraken_tickers(self, tickers: List[KrakenTicker]) -> List[StandardTicker]:
        """
        Batch convert Kraken tickers.
        
        Args:
            tickers: List of Kraken tickers
            
        Returns:
            List of standardized tickers
        """
        return [self.from_kraken_ticker(ticker) for ticker in tickers]
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def get_supported_pairs(self) -> Dict[str, str]:
        """
        Get all supported pair conversions.
        
        Returns:
            Dict mapping Kraken pairs to standard pairs
        """
        return KRAKEN_PAIR_MAP.copy()
    
    def get_supported_currencies(self) -> Dict[str, str]:
        """
        Get all supported currency conversions.
        
        Returns:
            Dict mapping Kraken currencies to standard currencies
        """
        return KRAKEN_CURRENCY_MAP.copy()
    
    def clear_cache(self):
        """Clear conversion cache."""
        self._currency_cache.clear()
        self._pair_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            'currency_cache_size': len(self._currency_cache),
            'pair_cache_size': len(self._pair_cache),
            'total_cache_size': len(self._currency_cache) + len(self._pair_cache)
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

# Default converter instance
_default_converter: Optional[KrakenConverter] = None


def get_converter(precision: int = 8) -> KrakenConverter:
    """
    Get or create default converter instance.
    
    Args:
        precision: Precision for conversion
        
    Returns:
        KrakenConverter instance
    """
    global _default_converter
    if _default_converter is None or _default_converter.precision != precision:
        _default_converter = KrakenConverter(precision)
    return _default_converter


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'KrakenConverter',
    'StandardOrder',
    'StandardTicker',
    'StandardBalance',
    'StandardTrade',
    'StandardPosition',
    'get_converter',
    'KRAKEN_CURRENCY_MAP',
    'STANDARD_CURRENCY_MAP',
    'KRAKEN_PAIR_MAP',
    'STANDARD_PAIR_MAP',
    'ORDER_TYPE_MAP',
    'ORDER_STATUS_MAP',
    'TIME_IN_FORCE_MAP',
]
