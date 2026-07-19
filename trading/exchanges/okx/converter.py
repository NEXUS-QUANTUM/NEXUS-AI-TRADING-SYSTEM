# trading/exchanges/okx/converter.py
# Nexus AI Trading System - OKX Exchange Converter Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
OKX Exchange - Data Converter Module

This module provides comprehensive data conversion and normalization utilities
for the OKX cryptocurrency exchange. It handles:

- Instrument ID conversion between OKX and standard formats
- Data format conversion between OKX API and Nexus internal models
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
and handles OKX-specific quirks in data formats.

OKX Instrument ID Format:
- Standard: BTC-USDT, ETH-USD, etc.
- For futures: BTC-USD-220930 (with expiry)
- For options: BTC-USD-220930-C-50000 (with strike and type)
- Perpetual swaps: BTC-USD-SWAP
"""

import json
import re
from datetime import datetime, timedelta
from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Union, Tuple
from enum import Enum

from pydantic import BaseModel, Field, validator

# Import base models
from trading.exchanges.okx.base import (
    OKXOrder,
    OKXOrderType,
    OKXOrderSide,
    OKXOrderStatus,
    OKXTimeInForce,
    OKXTicker,
    OKXOHLC
)

# =============================================================================
# CONSTANTS
# =============================================================================

# OKX to standard currency mapping
OKX_CURRENCY_MAP = {
    'BTC': 'BTC',
    'ETH': 'ETH',
    'USDT': 'USDT',
    'USDC': 'USDC',
    'USD': 'USD',
    'EUR': 'EUR',
    'GBP': 'GBP',
    'JPY': 'JPY',
    'CHF': 'CHF',
    'AUD': 'AUD',
    'CAD': 'CAD',
    'NZD': 'NZD',
    'SGD': 'SGD',
    'HKD': 'HKD',
    'KRW': 'KRW',
    'RUB': 'RUB',
    'TRY': 'TRY',
    'ZAR': 'ZAR',
    'BRL': 'BRL',
    'MXN': 'MXN',
    'PLN': 'PLN',
    'SEK': 'SEK',
    'NOK': 'NOK',
    'DKK': 'DKK',
    'CZK': 'CZK',
    'HUF': 'HUF',
    'ILS': 'ILS',
    'INR': 'INR',
    'PHP': 'PHP',
    'IDR': 'IDR',
    'MYR': 'MYR',
    'THB': 'THB',
    'VND': 'VND',
    'XRP': 'XRP',
    'ADA': 'ADA',
    'DOT': 'DOT',
    'SOL': 'SOL',
    'MATIC': 'MATIC',
    'LINK': 'LINK',
    'UNI': 'UNI',
    'ATOM': 'ATOM',
    'LTC': 'LTC',
    'BCH': 'BCH',
    'XLM': 'XLM',
    'DOGE': 'DOGE',
    'SHIB': 'SHIB',
    'AVAX': 'AVAX',
    'NEAR': 'NEAR',
    'ALGO': 'ALGO',
    'VET': 'VET',
    'ICP': 'ICP',
    'FIL': 'FIL',
    'ETC': 'ETC',
    'XMR': 'XMR',
    'ZEC': 'ZEC',
    'XTZ': 'XTZ',
    'EOS': 'EOS',
    'TRX': 'TRX',
    'BNB': 'BNB',
    'BUSD': 'BUSD',
    'DAI': 'DAI',
    'PAXG': 'PAXG',
    'XAU': 'XAU',
    'XAG': 'XAG',
}

# Standard to OKX currency mapping
STANDARD_CURRENCY_MAP = {v: k for k, v in OKX_CURRENCY_MAP.items()}

# OKX instrument type mapping
OKX_INSTRUMENT_TYPE = {
    'SPOT': 'spot',
    'FUTURES': 'futures',
    'OPTION': 'option',
    'SWAP': 'swap',
    'PERPETUAL': 'perpetual'
}

# Order type mapping
ORDER_TYPE_MAP = {
    'market': OKXOrderType.MARKET,
    'limit': OKXOrderType.LIMIT,
    'post_only': OKXOrderType.POST_ONLY,
    'fok': OKXOrderType.FOK,
    'ioc': OKXOrderType.IOC,
    'optimal_limit_ioc': OKXOrderType.OPTIMAL_LIMIT_IOC,
}

# Order status mapping
ORDER_STATUS_MAP = {
    'pending': OKXOrderStatus.PENDING,
    'live': OKXOrderStatus.OPEN,
    'partially_filled': OKXOrderStatus.PARTIALLY_FILLED,
    'filled': OKXOrderStatus.FILLED,
    'cancelled': OKXOrderStatus.CANCELLED,
    'expired': OKXOrderStatus.EXPIRED,
    'rejected': OKXOrderStatus.REJECTED,
    'triggered': OKXOrderStatus.TRIGGERED,
    'stopped': OKXOrderStatus.STOPPED,
}

# Time in force mapping
TIME_IN_FORCE_MAP = {
    'GTC': OKXTimeInForce.GTC,
    'IOC': OKXTimeInForce.IOC,
    'FOK': OKXTimeInForce.FOK,
    'Day': OKXTimeInForce.DAY,
    'GTX': OKXTimeInForce.GTX,
}

# OKX bar sizes to seconds
OKX_BAR_MAP = {
    '1m': 60,
    '3m': 180,
    '5m': 300,
    '15m': 900,
    '30m': 1800,
    '1H': 3600,
    '2H': 7200,
    '4H': 14400,
    '6H': 21600,
    '12H': 43200,
    '1D': 86400,
    '1W': 604800,
    '1M': 2592000,
    '1Mth': 2592000,
}

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class StandardOrder(BaseModel):
    """Standardized order model."""
    id: str
    symbol: str
    side: str
    type: str
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
    symbol: str
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


class StandardOHLC(BaseModel):
    """Standardized OHLC model."""
    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Optional[Decimal] = None


class StandardInstrument(BaseModel):
    """Standardized instrument model."""
    id: str
    symbol: str
    type: str
    base: str
    quote: str
    settle: Optional[str] = None
    tick_size: Decimal
    lot_size: Decimal
    min_qty: Decimal
    max_qty: Optional[Decimal] = None
    status: str
    expiry: Optional[datetime] = None
    strike: Optional[Decimal] = None
    option_type: Optional[str] = None


# =============================================================================
# CONVERTER CLASS
# =============================================================================

class OKXConverter:
    """
    Advanced data converter for OKX exchange.
    
    Features:
    - Bidirectional instrument ID conversion
    - Standard to OKX format conversion
    - OKX to standard format conversion
    - Instrument type detection and parsing
    - Decimal precision management
    - Timestamp normalization
    - Order data conversion
    - Ticker data conversion
    - Balance data conversion
    - Trade data conversion
    - OHLC data conversion
    - WebSocket message parsing
    - Batch conversion support
    - Validation and error handling
    - Format detection and auto-conversion
    - Instrument metadata extraction
    
    Usage:
        converter = OKXConverter()
        pair = converter.to_standard_symbol("BTC-USDT")  # Returns "BTC/USDT"
        order = converter.from_okx_order(okx_order)
        ticker = converter.to_okx_ticker(standard_ticker)
    """
    
    def __init__(self, precision: int = 8):
        """
        Initialize the converter.
        
        Args:
            precision: Default decimal precision for conversions
        """
        self.precision = precision
        self._symbol_cache = {}
        self._instrument_cache = {}
        
        # Set decimal context
        getcontext().prec = precision + 4
        
        # Compile regex patterns
        self._symbol_pattern = re.compile(r'^([A-Z0-9]+)-([A-Z0-9]+)$')
        self._future_pattern = re.compile(r'^([A-Z0-9]+)-([A-Z0-9]+)-(\d{6})$')
        self._option_pattern = re.compile(r'^([A-Z0-9]+)-([A-Z0-9]+)-(\d{6})-([CP])-(\d+)$')
        self._swap_pattern = re.compile(r'^([A-Z0-9]+)-([A-Z0-9]+)-SWAP$')
        self._currency_pattern = re.compile(r'^[A-Z0-9]{3,5}$')
        self._price_pattern = re.compile(r'^(\d+\.?\d*)$')
        
        logger.info(f"OKXConverter initialized with precision {precision}")
    
    # =========================================================================
    # INSTRUMENT ID CONVERSION
    # =========================================================================
    
    def to_standard_symbol(self, okx_instrument: str) -> str:
        """
        Convert OKX instrument ID to standard symbol format.
        
        Args:
            okx_instrument: OKX instrument ID (e.g., 'BTC-USDT', 'BTC-USD-220930')
            
        Returns:
            Standard symbol (e.g., 'BTC/USDT', 'BTC/USD-220930')
        """
        if not okx_instrument:
            return ''
        
        # Check cache
        if okx_instrument in self._symbol_cache:
            return self._symbol_cache[okx_instrument]
        
        result = okx_instrument
        
        # Check for swap
        swap_match = self._swap_pattern.match(okx_instrument)
        if swap_match:
            base = self.to_standard_currency(swap_match.group(1))
            quote = self.to_standard_currency(swap_match.group(2))
            result = f"{base}/{quote}-PERP"
            self._symbol_cache[okx_instrument] = result
            return result
        
        # Check for option
        option_match = self._option_pattern.match(okx_instrument)
        if option_match:
            base = self.to_standard_currency(option_match.group(1))
            quote = self.to_standard_currency(option_match.group(2))
            expiry = option_match.group(3)
            option_type = 'C' if option_match.group(4) == 'C' else 'P'
            strike = option_match.group(5)
            result = f"{base}/{quote}-{expiry}-{option_type}-{strike}"
            self._symbol_cache[okx_instrument] = result
            return result
        
        # Check for future
        future_match = self._future_pattern.match(okx_instrument)
        if future_match:
            base = self.to_standard_currency(future_match.group(1))
            quote = self.to_standard_currency(future_match.group(2))
            expiry = future_match.group(3)
            result = f"{base}/{quote}-{expiry}"
            self._symbol_cache[okx_instrument] = result
            return result
        
        # Check for standard spot
        symbol_match = self._symbol_pattern.match(okx_instrument)
        if symbol_match:
            base = self.to_standard_currency(symbol_match.group(1))
            quote = self.to_standard_currency(symbol_match.group(2))
            result = f"{base}/{quote}"
            self._symbol_cache[okx_instrument] = result
            return result
        
        # Return as-is
        self._symbol_cache[okx_instrument] = okx_instrument
        return okx_instrument
    
    def to_okx_instrument(self, standard_symbol: str, instrument_type: str = "SPOT") -> str:
        """
        Convert standard symbol to OKX instrument ID.
        
        Args:
            standard_symbol: Standard symbol (e.g., 'BTC/USDT')
            instrument_type: Instrument type (SPOT, FUTURES, OPTION, SWAP)
            
        Returns:
            OKX instrument ID
        """
        if not standard_symbol:
            return ''
        
        # Check reverse cache
        if standard_symbol in self._instrument_cache:
            return self._instrument_cache[standard_symbol]
        
        # Parse standard symbol
        if '/' in standard_symbol:
            base, quote = standard_symbol.split('/')
            base_okx = self.to_okx_currency(base)
            quote_okx = self.to_okx_currency(quote)
            
            # Handle different instrument types
            if instrument_type.upper() == "SWAP" or instrument_type.upper() == "PERPETUAL":
                result = f"{base_okx}-{quote_okx}-SWAP"
            elif instrument_type.upper() == "FUTURES":
                result = f"{base_okx}-{quote_okx}-{datetime.utcnow().strftime('%y%m%d')}"
            elif instrument_type.upper() == "OPTION":
                # Need more info for options
                result = f"{base_okx}-{quote_okx}"
            else:
                result = f"{base_okx}-{quote_okx}"
            
            self._instrument_cache[standard_symbol] = result
            return result
        
        # Try to parse as combined string
        symbol_match = self._symbol_pattern.match(standard_symbol)
        if symbol_match:
            base = self.to_okx_currency(symbol_match.group(1))
            quote = self.to_okx_currency(symbol_match.group(2))
            result = f"{base}-{quote}"
            self._instrument_cache[standard_symbol] = result
            return result
        
        # Return as-is
        return standard_symbol
    
    def parse_instrument_id(self, instrument_id: str) -> Dict[str, Any]:
        """
        Parse OKX instrument ID into components.
        
        Args:
            instrument_id: OKX instrument ID
            
        Returns:
            Dict with instrument components
        """
        # Check for swap
        swap_match = self._swap_pattern.match(instrument_id)
        if swap_match:
            return {
                'type': 'perpetual',
                'base': swap_match.group(1),
                'quote': swap_match.group(2),
                'base_standard': self.to_standard_currency(swap_match.group(1)),
                'quote_standard': self.to_standard_currency(swap_match.group(2)),
            }
        
        # Check for option
        option_match = self._option_pattern.match(instrument_id)
        if option_match:
            return {
                'type': 'option',
                'base': option_match.group(1),
                'quote': option_match.group(2),
                'base_standard': self.to_standard_currency(option_match.group(1)),
                'quote_standard': self.to_standard_currency(option_match.group(2)),
                'expiry': option_match.group(3),
                'option_type': 'call' if option_match.group(4) == 'C' else 'put',
                'strike': Decimal(option_match.group(5)),
            }
        
        # Check for future
        future_match = self._future_pattern.match(instrument_id)
        if future_match:
            return {
                'type': 'futures',
                'base': future_match.group(1),
                'quote': future_match.group(2),
                'base_standard': self.to_standard_currency(future_match.group(1)),
                'quote_standard': self.to_standard_currency(future_match.group(2)),
                'expiry': future_match.group(3),
            }
        
        # Check for standard spot
        symbol_match = self._symbol_pattern.match(instrument_id)
        if symbol_match:
            return {
                'type': 'spot',
                'base': symbol_match.group(1),
                'quote': symbol_match.group(2),
                'base_standard': self.to_standard_currency(symbol_match.group(1)),
                'quote_standard': self.to_standard_currency(symbol_match.group(2)),
            }
        
        return {'type': 'unknown', 'original': instrument_id}
    
    # =========================================================================
    # CURRENCY CONVERSION
    # =========================================================================
    
    def to_standard_currency(self, okx_currency: str) -> str:
        """
        Convert OKX currency code to standard format.
        
        Args:
            okx_currency: OKX currency code
            
        Returns:
            Standard currency code
        """
        if not okx_currency:
            return ''
        
        if okx_currency in OKX_CURRENCY_MAP:
            return OKX_CURRENCY_MAP[okx_currency]
        
        return okx_currency
    
    def to_okx_currency(self, standard_currency: str) -> str:
        """
        Convert standard currency code to OKX format.
        
        Args:
            standard_currency: Standard currency code
            
        Returns:
            OKX currency code
        """
        if not standard_currency:
            return ''
        
        standard_currency = standard_currency.upper()
        
        if standard_currency in STANDARD_CURRENCY_MAP:
            return STANDARD_CURRENCY_MAP[standard_currency]
        
        return standard_currency
    
    # =========================================================================
    # ORDER CONVERSION
    # =========================================================================
    
    def from_okx_order(self, okx_order: Dict[str, Any]) -> StandardOrder:
        """
        Convert OKX order data to standard format.
        
        Args:
            okx_order: OKX order data dictionary
            
        Returns:
            Standardized order
        """
        return StandardOrder(
            id=okx_order.get('ordId', ''),
            symbol=self.to_standard_symbol(okx_order.get('instId', '')),
            side=okx_order.get('side', 'buy'),
            type=okx_order.get('ordType', 'limit'),
            price=Decimal(str(okx_order.get('px', 0))),
            quantity=Decimal(str(okx_order.get('sz', 0))),
            filled_quantity=Decimal(str(okx_order.get('accFillSz', 0))),
            average_price=Decimal(str(okx_order.get('avgPx', 0))) if okx_order.get('avgPx') else None,
            status=okx_order.get('state', 'pending'),
            time_in_force=okx_order.get('tdMode', 'GTC'),
            fee=Decimal(str(okx_order.get('fee', 0))),
            cost=Decimal(str(okx_order.get('cost', 0))),
            created_at=datetime.fromtimestamp(int(okx_order.get('cTime', 0)) / 1000) if okx_order.get('cTime') else datetime.utcnow(),
            updated_at=datetime.fromtimestamp(int(okx_order.get('uTime', 0)) / 1000) if okx_order.get('uTime') else None,
            expires_at=datetime.fromtimestamp(int(okx_order.get('expireTime', 0)) / 1000) if okx_order.get('expireTime') else None,
            metadata=okx_order
        )
    
    def to_okx_order_params(
        self,
        standard_order: StandardOrder,
        instrument_type: str = "SPOT"
    ) -> Dict[str, Any]:
        """
        Convert standard order to OKX order parameters.
        
        Args:
            standard_order: Standardized order
            instrument_type: Instrument type
            
        Returns:
            OKX order parameters
        """
        okx_instrument = self.to_okx_instrument(standard_order.symbol, instrument_type)
        
        # Map order type
        order_type_map = {
            'market': 'market',
            'limit': 'limit',
            'post_only': 'post_only',
            'fok': 'fok',
            'ioc': 'ioc',
        }
        okx_type = order_type_map.get(standard_order.type, 'limit')
        
        # Map time in force
        tif_map = {
            'GTC': 'GTC',
            'IOC': 'IOC',
            'FOK': 'FOK',
            'Day': 'Day',
            'GTX': 'GTX',
        }
        okx_tif = tif_map.get(standard_order.time_in_force, 'GTC')
        
        params = {
            'instId': okx_instrument,
            'side': standard_order.side,
            'ordType': okx_type,
            'sz': str(standard_order.quantity),
            'tdMode': okx_tif,
        }
        
        # Add price for limit orders
        if standard_order.type in ['limit', 'post_only', 'fok', 'ioc']:
            params['px'] = str(standard_order.price)
        
        return params
    
    # =========================================================================
    # TICKER CONVERSION
    # =========================================================================
    
    def from_okx_ticker(self, okx_ticker: OKXTicker) -> StandardTicker:
        """
        Convert OKX ticker to standard format.
        
        Args:
            okx_ticker: OKX ticker object
            
        Returns:
            Standardized ticker
        """
        return StandardTicker(
            symbol=self.to_standard_symbol(okx_ticker.instrument_id),
            bid=okx_ticker.bid,
            ask=okx_ticker.ask,
            last=okx_ticker.last,
            high=okx_ticker.high if okx_ticker.high != Decimal('0') else None,
            low=okx_ticker.low if okx_ticker.low != Decimal('0') else None,
            volume=okx_ticker.volume if okx_ticker.volume != Decimal('0') else None,
            quote_volume=okx_ticker.volume_24h if okx_ticker.volume_24h != Decimal('0') else None,
            change=okx_ticker.change if okx_ticker.change != Decimal('0') else None,
            change_percent=okx_ticker.change_percent if okx_ticker.change_percent != Decimal('0') else None,
            timestamp=okx_ticker.timestamp
        )
    
    def to_okx_ticker_request(self, symbol: str) -> Dict[str, str]:
        """
        Convert standard symbol to OKX ticker request.
        
        Args:
            symbol: Standard symbol
            
        Returns:
            OKX ticker request parameters
        """
        okx_instrument = self.to_okx_instrument(symbol)
        return {'instId': okx_instrument}
    
    # =========================================================================
    # BALANCE CONVERSION
    # =========================================================================
    
    def from_okx_balance(self, okx_balance: Dict[str, Any]) -> StandardBalance:
        """
        Convert OKX balance to standard format.
        
        Args:
            okx_balance: OKX balance data
            
        Returns:
            Standardized balance
        """
        currency = self.to_standard_currency(okx_balance.get('ccy', ''))
        
        return StandardBalance(
            currency=currency,
            total=Decimal(str(okx_balance.get('bal', 0))),
            available=Decimal(str(okx_balance.get('availBal', 0))),
            locked=Decimal(str(okx_balance.get('frozenBal', 0))),
            staked=Decimal(str(okx_balance.get('stakedBal', 0))),
            earned=Decimal(str(okx_balance.get('earnedBal', 0))),
            updated_at=datetime.utcnow()
        )
    
    def to_okx_balance_request(self, currencies: List[str]) -> Dict[str, str]:
        """
        Convert standard currencies to OKX balance request.
        
        Args:
            currencies: List of standard currency codes
            
        Returns:
            OKX balance request parameters
        """
        okx_currencies = [self.to_okx_currency(c) for c in currencies]
        return {'ccy': ','.join(okx_currencies)}
    
    # =========================================================================
    # OHLC CONVERSION
    # =========================================================================
    
    def from_okx_ohlc(
        self,
        okx_ohlc: OKXOHLC,
        symbol: str
    ) -> StandardOHLC:
        """
        Convert OKX OHLC to standard format.
        
        Args:
            okx_ohlc: OKX OHLC object
            symbol: Symbol for the OHLC
            
        Returns:
            Standardized OHLC
        """
        return StandardOHLC(
            symbol=self.to_standard_symbol(symbol),
            timestamp=okx_ohlc.datetime,
            open=okx_ohlc.open,
            high=okx_ohlc.high,
            low=okx_ohlc.low,
            close=okx_ohlc.close,
            volume=okx_ohlc.volume,
            quote_volume=okx_ohlc.volume_quote
        )
    
    def to_okx_ohlc_request(
        self,
        symbol: str,
        bar: str = "1m",
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Convert standard OHLC request to OKX format.
        
        Args:
            symbol: Standard symbol
            bar: Bar size
            limit: Number of candles
            
        Returns:
            OKX OHLC request parameters
        """
        okx_instrument = self.to_okx_instrument(symbol)
        return {
            'instId': okx_instrument,
            'bar': bar,
            'limit': min(limit, 300)
        }
    
    # =========================================================================
    # INSTRUMENT CONVERSION
    # =========================================================================
    
    def from_okx_instrument(self, okx_instrument: Dict[str, Any]) -> StandardInstrument:
        """
        Convert OKX instrument to standard format.
        
        Args:
            okx_instrument: OKX instrument data
            
        Returns:
            Standardized instrument
        """
        inst_id = okx_instrument.get('instId', '')
        parsed = self.parse_instrument_id(inst_id)
        
        expiry = None
        if parsed.get('type') in ['futures', 'option'] and parsed.get('expiry'):
            try:
                expiry = datetime.strptime(parsed['expiry'], '%y%m%d')
            except ValueError:
                pass
        
        return StandardInstrument(
            id=inst_id,
            symbol=self.to_standard_symbol(inst_id),
            type=parsed.get('type', 'spot'),
            base=parsed.get('base_standard', ''),
            quote=parsed.get('quote_standard', ''),
            settle=okx_instrument.get('settleCcy'),
            tick_size=Decimal(str(okx_instrument.get('tickSz', 0.01))),
            lot_size=Decimal(str(okx_instrument.get('lotSz', 0.0001))),
            min_qty=Decimal(str(okx_instrument.get('minSz', 0))),
            max_qty=Decimal(str(okx_instrument.get('maxSz', 0))) if okx_instrument.get('maxSz') else None,
            status=okx_instrument.get('state', 'live'),
            expiry=expiry,
            strike=Decimal(str(okx_instrument.get('strikePx', 0))) if okx_instrument.get('strikePx') else None,
            option_type=okx_instrument.get('optType')
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
        # Check for event
        if 'event' in message:
            event = message.get('event')
            if event == 'error':
                return {
                    'type': 'error',
                    'code': message.get('code'),
                    'message': message.get('msg'),
                    'timestamp': datetime.utcnow().isoformat()
                }
            elif event == 'login':
                return {
                    'type': 'login',
                    'success': message.get('code') == '0',
                    'timestamp': datetime.utcnow().isoformat()
                }
            elif event == 'subscribe':
                return {
                    'type': 'subscribe',
                    'channel': message.get('arg', {}).get('channel'),
                    'instrument': message.get('arg', {}).get('instId'),
                    'success': message.get('code') == '0',
                    'timestamp': datetime.utcnow().isoformat()
                }
            elif event == 'unsubscribe':
                return {
                    'type': 'unsubscribe',
                    'channel': message.get('arg', {}).get('channel'),
                    'instrument': message.get('arg', {}).get('instId'),
                    'success': message.get('code') == '0',
                    'timestamp': datetime.utcnow().isoformat()
                }
        
        # Check for data
        if 'arg' in message and 'data' in message:
            channel = message['arg'].get('channel')
            instrument = message['arg'].get('instId')
            data = message['data']
            
            if channel == 'ticker':
                return self._normalize_ws_ticker(data, instrument)
            elif channel == 'candle':
                return self._normalize_ws_ohlc(data, instrument)
            elif channel == 'trades':
                return self._normalize_ws_trade(data, instrument)
            elif channel in ['books', 'books5']:
                return self._normalize_ws_book(data, instrument)
            elif channel == 'balance':
                return self._normalize_ws_balance(data)
            elif channel == 'positions':
                return self._normalize_ws_position(data)
            elif channel == 'orders':
                return self._normalize_ws_order(data)
        
        return {
            'type': 'unknown',
            'raw': message,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _normalize_ws_ticker(
        self,
        data: List[Dict],
        instrument: str
    ) -> Dict[str, Any]:
        """Normalize WebSocket ticker data."""
        if not data:
            return {}
        
        item = data[0]
        return {
            'type': 'ticker',
            'symbol': self.to_standard_symbol(instrument),
            'bid': Decimal(str(item.get('bidPx', 0))),
            'ask': Decimal(str(item.get('askPx', 0))),
            'last': Decimal(str(item.get('last', 0))),
            'high': Decimal(str(item.get('high24h', 0))),
            'low': Decimal(str(item.get('low24h', 0))),
            'volume': Decimal(str(item.get('vol24h', 0))),
            'change': Decimal(str(item.get('last', 0))) - Decimal(str(item.get('open24h', 0))),
            'change_percent': Decimal(str(item.get('last', 0))) / Decimal(str(item.get('open24h', 0))) * 100 if item.get('open24h') else Decimal('0'),
            'timestamp': datetime.fromtimestamp(int(item.get('ts', 0)) / 1000).isoformat()
        }
    
    def _normalize_ws_ohlc(
        self,
        data: List[List],
        instrument: str
    ) -> Dict[str, Any]:
        """Normalize WebSocket OHLC data."""
        if not data:
            return {}
        
        ohlc_list = []
        for candle in data:
            ohlc_list.append({
                'timestamp': datetime.fromtimestamp(int(candle[0]) / 1000).isoformat(),
                'open': Decimal(str(candle[1])),
                'high': Decimal(str(candle[2])),
                'low': Decimal(str(candle[3])),
                'close': Decimal(str(candle[4])),
                'volume': Decimal(str(candle[5])),
                'quote_volume': Decimal(str(candle[6])) if len(candle) > 6 else None
            })
        
        return {
            'type': 'ohlc',
            'symbol': self.to_standard_symbol(instrument),
            'candles': ohlc_list,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _normalize_ws_trade(
        self,
        data: List[Dict],
        instrument: str
    ) -> Dict[str, Any]:
        """Normalize WebSocket trade data."""
        if not data:
            return {}
        
        trades = []
        for trade in data:
            trades.append({
                'id': trade.get('tradeId', ''),
                'price': Decimal(str(trade.get('px', 0))),
                'quantity': Decimal(str(trade.get('sz', 0))),
                'side': trade.get('side', 'buy'),
                'timestamp': datetime.fromtimestamp(int(trade.get('ts', 0)) / 1000).isoformat()
            })
        
        return {
            'type': 'trade',
            'symbol': self.to_standard_symbol(instrument),
            'trades': trades,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _normalize_ws_book(
        self,
        data: List[Dict],
        instrument: str
    ) -> Dict[str, Any]:
        """Normalize WebSocket order book data."""
        if not data:
            return {}
        
        item = data[0]
        return {
            'type': 'orderbook',
            'symbol': self.to_standard_symbol(instrument),
            'bids': [(Decimal(str(b[0])), Decimal(str(b[1]))) for b in item.get('bids', [])],
            'asks': [(Decimal(str(a[0])), Decimal(str(a[1]))) for a in item.get('asks', [])],
            'timestamp': datetime.fromtimestamp(int(item.get('ts', 0)) / 1000).isoformat(),
            'checksum': item.get('checksum')
        }
    
    def _normalize_ws_balance(self, data: List[Dict]) -> Dict[str, Any]:
        """Normalize WebSocket balance data."""
        if not data:
            return {}
        
        balances = []
        for item in data:
            balances.append({
                'currency': self.to_standard_currency(item.get('ccy', '')),
                'total': Decimal(str(item.get('bal', 0))),
                'available': Decimal(str(item.get('availBal', 0))),
                'frozen': Decimal(str(item.get('frozenBal', 0))),
                'staked': Decimal(str(item.get('stakedBal', 0))),
                'earned': Decimal(str(item.get('earnedBal', 0))),
                'borrowed': Decimal(str(item.get('borrowedBal', 0))),
                'interest': Decimal(str(item.get('interest', 0))),
                'timestamp': datetime.fromtimestamp(int(item.get('ts', 0)) / 1000).isoformat()
            })
        
        return {
            'type': 'balance',
            'balances': balances,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _normalize_ws_position(self, data: List[Dict]) -> Dict[str, Any]:
        """Normalize WebSocket position data."""
        if not data:
            return {}
        
        positions = []
        for item in data:
            positions.append({
                'symbol': self.to_standard_symbol(item.get('instId', '')),
                'side': item.get('posSide', 'net'),
                'quantity': Decimal(str(item.get('pos', 0))),
                'entry_price': Decimal(str(item.get('avgPx', 0))),
                'current_price': Decimal(str(item.get('markPx', 0))),
                'unrealized_pnl': Decimal(str(item.get('upl', 0))),
                'realized_pnl': Decimal(str(item.get('realizedPnl', 0))),
                'margin': Decimal(str(item.get('margin', 0))),
                'leverage': Decimal(str(item.get('lever', 1))),
                'timestamp': datetime.fromtimestamp(int(item.get('ts', 0)) / 1000).isoformat()
            })
        
        return {
            'type': 'position',
            'positions': positions,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _normalize_ws_order(self, data: List[Dict]) -> Dict[str, Any]:
        """Normalize WebSocket order data."""
        if not data:
            return {}
        
        orders = []
        for item in data:
            orders.append({
                'id': item.get('ordId', ''),
                'symbol': self.to_standard_symbol(item.get('instId', '')),
                'side': item.get('side', 'buy'),
                'type': item.get('ordType', 'limit'),
                'status': item.get('state', 'pending'),
                'price': Decimal(str(item.get('px', 0))),
                'quantity': Decimal(str(item.get('sz', 0))),
                'filled_quantity': Decimal(str(item.get('accFillSz', 0))),
                'average_price': Decimal(str(item.get('avgPx', 0))),
                'fee': Decimal(str(item.get('fee', 0))),
                'cost': Decimal(str(item.get('cost', 0))),
                'timestamp': datetime.fromtimestamp(int(item.get('cTime', 0)) / 1000).isoformat(),
                'updated_at': datetime.fromtimestamp(int(item.get('uTime', 0)) / 1000).isoformat()
            })
        
        return {
            'type': 'order',
            'orders': orders,
            'timestamp': datetime.utcnow().isoformat()
        }
    
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
    
    def validate_instrument(self, instrument_id: str) -> bool:
        """
        Validate instrument ID format.
        
        Args:
            instrument_id: Instrument ID to validate
            
        Returns:
            True if valid
        """
        if not instrument_id:
            return False
        
        # Check all patterns
        patterns = [
            self._symbol_pattern,
            self._future_pattern,
            self._option_pattern,
            self._swap_pattern
        ]
        
        for pattern in patterns:
            if pattern.match(instrument_id):
                return True
        
        return False
    
    # =========================================================================
    # BATCH CONVERSION
    # =========================================================================
    
    def batch_convert_symbols(self, symbols: List[str]) -> Dict[str, str]:
        """
        Batch convert symbols to standard format.
        
        Args:
            symbols: List of symbols to convert
            
        Returns:
            Dict mapping original to converted
        """
        result = {}
        for symbol in symbols:
            result[symbol] = self.to_standard_symbol(symbol)
        return result
    
    def batch_from_okx_orders(self, orders: List[Dict[str, Any]]) -> List[StandardOrder]:
        """
        Batch convert OKX orders.
        
        Args:
            orders: List of OKX order data
            
        Returns:
            List of standardized orders
        """
        return [self.from_okx_order(order) for order in orders]
    
    def batch_from_okx_balances(self, balances: List[Dict[str, Any]]) -> List[StandardBalance]:
        """
        Batch convert OKX balances.
        
        Args:
            balances: List of OKX balance data
            
        Returns:
            List of standardized balances
        """
        return [self.from_okx_balance(balance) for balance in balances]
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def get_bar_duration(self, bar: str) -> int:
        """
        Get duration in seconds for a bar size.
        
        Args:
            bar: Bar size (1m, 5m, 1H, etc.)
            
        Returns:
            Duration in seconds
        """
        return OKX_BAR_MAP.get(bar, 60)
    
    def get_supported_instrument_types(self) -> List[str]:
        """Get supported instrument types."""
        return list(OKX_INSTRUMENT_TYPE.keys())
    
    def get_supported_currencies(self) -> List[str]:
        """Get supported currencies."""
        return list(OKX_CURRENCY_MAP.keys())
    
    def clear_cache(self):
        """Clear conversion cache."""
        self._symbol_cache.clear()
        self._instrument_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            'symbol_cache_size': len(self._symbol_cache),
            'instrument_cache_size': len(self._instrument_cache),
            'total_cache_size': len(self._symbol_cache) + len(self._instrument_cache)
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_default_converter: Optional[OKXConverter] = None


def get_converter(precision: int = 8) -> OKXConverter:
    """
    Get or create default converter instance.
    
    Args:
        precision: Precision for conversion
        
    Returns:
        OKXConverter instance
    """
    global _default_converter
    if _default_converter is None or _default_converter.precision != precision:
        _default_converter = OKXConverter(precision)
    return _default_converter


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'OKXConverter',
    'StandardOrder',
    'StandardTicker',
    'StandardBalance',
    'StandardTrade',
    'StandardOHLC',
    'StandardInstrument',
    'get_converter',
    'OKX_CURRENCY_MAP',
    'STANDARD_CURRENCY_MAP',
    'OKX_INSTRUMENT_TYPE',
    'ORDER_TYPE_MAP',
    'ORDER_STATUS_MAP',
    'TIME_IN_FORCE_MAP',
    'OKX_BAR_MAP'
]
