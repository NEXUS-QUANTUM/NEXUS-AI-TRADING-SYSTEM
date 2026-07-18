# trading/brokers/broker_utils.py
"""
NEXUS AI TRADING SYSTEM - Broker Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides utility functions and helpers for broker operations.
Includes symbol formatting, order validation, price rounding, quantity
normalization, and other common utilities used across broker integrations.
"""

import re
import math
from decimal import Decimal, ROUND_DOWN, ROUND_UP, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple, Union, Set
from datetime import datetime, timedelta
from enum import Enum

from shared.types.common import OrderSide, OrderType, TimeInForce
from shared.types.trading import Order, Position, Trade
from .base import BrokerName, AssetClass

logger = logging.getLogger(__name__)


# ============================================================================
# SYMBOL FORMATTING
# ============================================================================

class SymbolFormat(str, Enum):
    """Symbol format types"""
    STANDARD = "standard"          # BTC/USD
    UNDERSCORE = "underscore"      # BTC_USD
    DASH = "dash"                  # BTC-USD
    NO_SEPARATOR = "no_separator"  # BTCUSD
    EXCHANGE_STYLE = "exchange"    # XBTUSD (exchange-specific)
    FUTURES = "futures"            # BTCUSD_PERP, BTCUSD_202412


def format_symbol(
    base_asset: str,
    quote_asset: str,
    format_type: SymbolFormat = SymbolFormat.STANDARD,
    exchange: Optional[BrokerName] = None,
    **kwargs,
) -> str:
    """
    Format a trading symbol according to the specified format.
    
    Args:
        base_asset: Base asset (e.g., BTC, ETH)
        quote_asset: Quote asset (e.g., USD, EUR)
        format_type: Symbol format type
        exchange: Optional exchange for exchange-specific formatting
        **kwargs: Additional formatting parameters
        
    Returns:
        str: Formatted symbol
    """
    if exchange:
        return format_symbol_for_exchange(base_asset, quote_asset, exchange, **kwargs)
    
    separators = {
        SymbolFormat.STANDARD: "/",
        SymbolFormat.UNDERSCORE: "_",
        SymbolFormat.DASH: "-",
        SymbolFormat.NO_SEPARATOR: "",
    }
    
    separator = separators.get(format_type, "/")
    
    # Special handling for futures
    if format_type == SymbolFormat.FUTURES:
        expiry = kwargs.get("expiry", "")
        if expiry:
            return f"{base_asset}{quote_asset}_{expiry}"
        return f"{base_asset}{quote_asset}_PERP"
    
    return f"{base_asset}{separator}{quote_asset}"


def format_symbol_for_exchange(
    base_asset: str,
    quote_asset: str,
    exchange: BrokerName,
    **kwargs,
) -> str:
    """
    Format a symbol specifically for an exchange.
    
    Args:
        base_asset: Base asset
        quote_asset: Quote asset
        exchange: Exchange name
        **kwargs: Additional formatting parameters
        
    Returns:
        str: Exchange-formatted symbol
    """
    exchange_formats = {
        BrokerName.BINANCE: lambda: f"{base_asset.upper()}{quote_asset.upper()}",
        BrokerName.BINANCE_US: lambda: f"{base_asset.upper()}{quote_asset.upper()}",
        BrokerName.BYBIT: lambda: f"{base_asset.upper()}{quote_asset.upper()}",
        BrokerName.COINBASE: lambda: f"{base_asset.upper()}-{quote_asset.upper()}",
        BrokerName.COINBASE_PRO: lambda: f"{base_asset.upper()}-{quote_asset.upper()}",
        BrokerName.KRAKEN: lambda: f"{base_asset.upper()}/{quote_asset.upper()}",
        BrokerName.KUCOIN: lambda: f"{base_asset.upper()}-{quote_asset.upper()}",
        BrokerName.ALPACA: lambda: f"{base_asset.upper()}/{quote_asset.upper()}",
        BrokerName.OANDA: lambda: f"{base_asset.upper()}_{quote_asset.upper()}",
        BrokerName.IBKR: lambda: f"{base_asset.upper()}{quote_asset.upper()}",
        BrokerName.TRADIER: lambda: f"{base_asset.upper()}/{quote_asset.upper()}",
    }
    
    formatter = exchange_formats.get(exchange)
    if formatter:
        return formatter()
    
    # Default: use standard format
    return format_symbol(base_asset, quote_asset, SymbolFormat.STANDARD)


def parse_symbol(symbol: str) -> Tuple[str, str, Optional[SymbolFormat]]:
    """
    Parse a symbol into base and quote assets.
    
    Args:
        symbol: Symbol string
        
    Returns:
        Tuple[str, str, Optional[SymbolFormat]]: (base_asset, quote_asset, detected_format)
    """
    # Try different separators
    separators = [
        ("/", SymbolFormat.STANDARD),
        ("_", SymbolFormat.UNDERSCORE),
        ("-", SymbolFormat.DASH),
    ]
    
    for sep, fmt in separators:
        if sep in symbol:
            parts = symbol.split(sep)
            if len(parts) == 2:
                return parts[0], parts[1], fmt
    
    # No separator found - try to split by common patterns
    # BTCUSD -> BTC, USD
    # ETHUSDT -> ETH, USDT
    common_quotes = ["USDT", "USD", "USDC", "BUSD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD"]
    
    for quote in sorted(common_quotes, key=len, reverse=True):
        if symbol.endswith(quote):
            base = symbol[:-len(quote)]
            if base:
                return base, quote, SymbolFormat.NO_SEPARATOR
    
    # Default: treat as no separator
    return symbol, "", SymbolFormat.NO_SEPARATOR


def normalize_symbol(symbol: str, exchange: Optional[BrokerName] = None) -> str:
    """
    Normalize a symbol to a standard format.
    
    Args:
        symbol: Symbol to normalize
        exchange: Optional exchange for specific formatting
        
    Returns:
        str: Normalized symbol
    """
    # Remove any whitespace
    symbol = symbol.strip().upper()
    
    # Parse if not already in standard format
    if "/" not in symbol and "_" not in symbol and "-" not in symbol:
        base, quote, _ = parse_symbol(symbol)
        if base and quote:
            return format_symbol(base, quote, SymbolFormat.STANDARD)
    
    # Replace underscores and dashes with slashes
    symbol = symbol.replace("_", "/").replace("-", "/")
    
    return symbol


# ============================================================================
# ORDER VALIDATION
# ============================================================================

def validate_order(order: Order, min_size: Optional[float] = None, max_size: Optional[float] = None) -> List[str]:
    """
    Validate an order for basic correctness.
    
    Args:
        order: Order to validate
        min_size: Minimum order size
        max_size: Maximum order size
        
    Returns:
        List[str]: List of validation errors (empty if valid)
    """
    errors = []
    
    # Check symbol
    if not order.symbol or not order.symbol.strip():
        errors.append("Symbol is required")
    
    # Check quantity
    if order.quantity <= 0:
        errors.append("Quantity must be positive")
    
    if min_size is not None and order.quantity < min_size:
        errors.append(f"Quantity {order.quantity} is below minimum {min_size}")
    
    if max_size is not None and order.quantity > max_size:
        errors.append(f"Quantity {order.quantity} exceeds maximum {max_size}")
    
    # Check price for limit orders
    if order.order_type in (OrderType.LIMIT, OrderType.LIMIT_MAKER):
        if order.price is None or order.price <= 0:
            errors.append("Price is required for limit orders")
    
    # Check stop price for stop orders
    if order.order_type in (OrderType.STOP_LOSS, OrderType.STOP_LOSS_LIMIT):
        if order.stop_price is None or order.stop_price <= 0:
            errors.append("Stop price is required for stop orders")
    
    # Validate price vs stop price
    if order.price and order.stop_price:
        if order.side == OrderSide.BUY:
            if order.stop_price >= order.price:
                errors.append("Stop price must be below limit price for buy orders")
        else:
            if order.stop_price <= order.price:
                errors.append("Stop price must be above limit price for sell orders")
    
    # Validate time in force
    if order.time_in_force not in TimeInForce:
        errors.append(f"Invalid time in force: {order.time_in_force}")
    
    return errors


def validate_order_for_exchange(order: Order, exchange: BrokerName) -> List[str]:
    """
    Validate an order for a specific exchange.
    
    Args:
        order: Order to validate
        exchange: Exchange name
        
    Returns:
        List[str]: List of validation errors
    """
    errors = validate_order(order)
    
    # Exchange-specific validations
    if exchange in (BrokerName.BINANCE, BrokerName.BINANCE_US):
        # Binance requires client order ID for some order types
        if not order.client_order_id:
            errors.append("Client order ID is required for Binance")
        
        # Binance doesn't support trailing stops
        if order.order_type == OrderType.TRAILING_STOP:
            errors.append("Trailing stops are not supported on Binance")
    
    elif exchange == BrokerName.COINBASE:
        # Coinbase requires client order ID
        if not order.client_order_id:
            errors.append("Client order ID is required for Coinbase")
    
    elif exchange == BrokerName.KRAKEN:
        # Kraken has specific order type limitations
        if order.order_type == OrderType.TRAILING_STOP:
            errors.append("Trailing stops are not supported on Kraken")
    
    return errors


# ============================================================================
# QUANTITY AND PRICE NORMALIZATION
# ============================================================================

def normalize_quantity(
    quantity: Union[float, Decimal],
    step_size: Union[float, Decimal],
    min_qty: Union[float, Decimal] = 0,
    max_qty: Optional[Union[float, Decimal]] = None,
    round_up: bool = False,
) -> Decimal:
    """
    Normalize a quantity to the exchange's step size.
    
    Args:
        quantity: Raw quantity
        step_size: Step size for quantity
        min_qty: Minimum quantity
        max_qty: Maximum quantity
        round_up: Whether to round up (for buying) or down (for selling)
        
    Returns:
        Decimal: Normalized quantity
    """
    qty = Decimal(str(quantity))
    step = Decimal(str(step_size))
    min_q = Decimal(str(min_qty))
    
    # Apply step size
    if round_up:
        normalized = (qty / step).quantize(Decimal('1'), rounding=ROUND_UP) * step
    else:
        normalized = (qty / step).quantize(Decimal('1'), rounding=ROUND_DOWN) * step
    
    # Apply minimum
    if normalized < min_q:
        normalized = min_q
    
    # Apply maximum
    if max_qty is not None:
        max_q = Decimal(str(max_qty))
        if normalized > max_q:
            normalized = max_q
    
    # Round to step size precision
    precision = -Decimal(str(step)).as_tuple().exponent
    if precision > 0:
        normalized = normalized.quantize(Decimal('0.') + '0' * precision)
    else:
        normalized = normalized.quantize(Decimal('1'))
    
    return normalized


def normalize_price(
    price: Union[float, Decimal],
    tick_size: Union[float, Decimal],
    min_price: Union[float, Decimal] = 0,
    max_price: Optional[Union[float, Decimal]] = None,
) -> Decimal:
    """
    Normalize a price to the exchange's tick size.
    
    Args:
        price: Raw price
        tick_size: Tick size for price
        min_price: Minimum price
        max_price: Maximum price
        
    Returns:
        Decimal: Normalized price
    """
    p = Decimal(str(price))
    tick = Decimal(str(tick_size))
    min_p = Decimal(str(min_price))
    
    # Apply tick size (round to nearest tick)
    normalized = (p / tick).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * tick
    
    # Apply minimum
    if normalized < min_p:
        normalized = min_p
    
    # Apply maximum
    if max_price is not None:
        max_p = Decimal(str(max_price))
        if normalized > max_p:
            normalized = max_p
    
    # Round to tick precision
    precision = -Decimal(str(tick)).as_tuple().exponent
    if precision > 0:
        normalized = normalized.quantize(Decimal('0.') + '0' * precision)
    else:
        normalized = normalized.quantize(Decimal('1'))
    
    return normalized


def calculate_order_value(
    quantity: Union[float, Decimal],
    price: Union[float, Decimal],
) -> Decimal:
    """
    Calculate the total value of an order.
    
    Args:
        quantity: Order quantity
        price: Order price
        
    Returns:
        Decimal: Total order value
    """
    qty = Decimal(str(quantity))
    p = Decimal(str(price))
    return qty * p


def calculate_position_size(
    capital: Union[float, Decimal],
    price: Union[float, Decimal],
    risk_percent: float,
    stop_loss_percent: Optional[float] = None,
) -> Decimal:
    """
    Calculate position size based on risk management.
    
    Args:
        capital: Total capital available
        price: Current price
        risk_percent: Risk per trade (percentage of capital)
        stop_loss_percent: Stop loss percentage from entry
        
    Returns:
        Decimal: Position size
    """
    capital_dec = Decimal(str(capital))
    price_dec = Decimal(str(price))
    risk = Decimal(str(risk_percent / 100))
    
    if stop_loss_percent is None:
        # Use 2% as default stop loss
        stop_loss_percent = 2.0
    
    stop_loss = Decimal(str(stop_loss_percent / 100))
    
    # Kelly-like position sizing
    risk_amount = capital_dec * risk
    position_value = risk_amount / stop_loss
    
    if price_dec > 0:
        return position_value / price_dec
    
    return Decimal('0')


# ============================================================================
# ORDER TYPE HELPERS
# ============================================================================

def order_type_to_string(order_type: OrderType) -> str:
    """
    Convert OrderType enum to string representation.
    
    Args:
        order_type: OrderType enum
        
    Returns:
        str: String representation
    """
    mapping = {
        OrderType.MARKET: "MARKET",
        OrderType.LIMIT: "LIMIT",
        OrderType.LIMIT_MAKER: "LIMIT_MAKER",
        OrderType.STOP_LOSS: "STOP_LOSS",
        OrderType.STOP_LOSS_LIMIT: "STOP_LOSS_LIMIT",
        OrderType.TRAILING_STOP: "TRAILING_STOP",
        OrderType.TAKE_PROFIT: "TAKE_PROFIT",
        OrderType.TAKE_PROFIT_LIMIT: "TAKE_PROFIT_LIMIT",
        OrderType.FILL_OR_KILL: "FILL_OR_KILL",
        OrderType.IMMEDIATE_OR_CANCEL: "IMMEDIATE_OR_CANCEL",
    }
    return mapping.get(order_type, order_type.value)


def string_to_order_type(order_type_str: str) -> OrderType:
    """
    Convert string to OrderType enum.
    
    Args:
        order_type_str: String representation
        
    Returns:
        OrderType: OrderType enum
    """
    mapping = {
        "MARKET": OrderType.MARKET,
        "LIMIT": OrderType.LIMIT,
        "LIMIT_MAKER": OrderType.LIMIT_MAKER,
        "STOP_LOSS": OrderType.STOP_LOSS,
        "STOP_LOSS_LIMIT": OrderType.STOP_LOSS_LIMIT,
        "TRAILING_STOP": OrderType.TRAILING_STOP,
        "TAKE_PROFIT": OrderType.TAKE_PROFIT,
        "TAKE_PROFIT_LIMIT": OrderType.TAKE_PROFIT_LIMIT,
        "FILL_OR_KILL": OrderType.FILL_OR_KILL,
        "IMMEDIATE_OR_CANCEL": OrderType.IMMEDIATE_OR_CANCEL,
    }
    return mapping.get(order_type_str.upper(), OrderType.MARKET)


# ============================================================================
# TIME IN FORCE HELPERS
# ============================================================================

def time_in_force_to_string(time_in_force: TimeInForce) -> str:
    """
    Convert TimeInForce enum to string representation.
    
    Args:
        time_in_force: TimeInForce enum
        
    Returns:
        str: String representation
    """
    mapping = {
        TimeInForce.GTC: "GTC",
        TimeInForce.GTD: "GTD",
        TimeInForce.IOC: "IOC",
        TimeInForce.FOK: "FOK",
        TimeInForce.PO: "PO",
        TimeInForce.DAY: "DAY",
    }
    return mapping.get(time_in_force, time_in_force.value)


def string_to_time_in_force(tif_str: str) -> TimeInForce:
    """
    Convert string to TimeInForce enum.
    
    Args:
        tif_str: String representation
        
    Returns:
        TimeInForce: TimeInForce enum
    """
    mapping = {
        "GTC": TimeInForce.GTC,
        "GTD": TimeInForce.GTD,
        "IOC": TimeInForce.IOC,
        "FOK": TimeInForce.FOK,
        "PO": TimeInForce.PO,
        "DAY": TimeInForce.DAY,
    }
    return mapping.get(tif_str.upper(), TimeInForce.GTC)


# ============================================================================
# POSITION HELPERS
# ============================================================================

def calculate_position_pnl(
    position: Position,
    current_price: Union[float, Decimal],
) -> Decimal:
    """
    Calculate the P&L of a position.
    
    Args:
        position: Position object
        current_price: Current market price
        
    Returns:
        Decimal: P&L amount
    """
    current = Decimal(str(current_price))
    
    if position.side == OrderSide.BUY:
        pnl = (current - position.entry_price) * position.quantity
    else:  # SELL
        pnl = (position.entry_price - current) * position.quantity
    
    return pnl


def calculate_position_pnl_percentage(
    position: Position,
    current_price: Union[float, Decimal],
) -> Decimal:
    """
    Calculate the P&L percentage of a position.
    
    Args:
        position: Position object
        current_price: Current market price
        
    Returns:
        Decimal: P&L percentage
    """
    if position.entry_price == 0:
        return Decimal('0')
    
    current = Decimal(str(current_price))
    
    if position.side == OrderSide.BUY:
        pnl_pct = (current - position.entry_price) / position.entry_price * 100
    else:  # SELL
        pnl_pct = (position.entry_price - current) / position.entry_price * 100
    
    return pnl_pct


def calculate_position_value(
    position: Position,
    current_price: Union[float, Decimal],
) -> Decimal:
    """
    Calculate the current value of a position.
    
    Args:
        position: Position object
        current_price: Current market price
        
    Returns:
        Decimal: Position value
    """
    current = Decimal(str(current_price))
    return position.quantity * current


# ============================================================================
# RISK CALCULATIONS
# ============================================================================

def calculate_stop_loss_price(
    entry_price: Union[float, Decimal],
    side: OrderSide,
    stop_loss_percent: float,
) -> Decimal:
    """
    Calculate stop loss price based on percentage.
    
    Args:
        entry_price: Entry price
        side: Order side (BUY/SELL)
        stop_loss_percent: Stop loss percentage
        
    Returns:
        Decimal: Stop loss price
    """
    entry = Decimal(str(entry_price))
    pct = Decimal(str(stop_loss_percent / 100))
    
    if side == OrderSide.BUY:
        return entry * (Decimal('1') - pct)
    else:  # SELL
        return entry * (Decimal('1') + pct)


def calculate_take_profit_price(
    entry_price: Union[float, Decimal],
    side: OrderSide,
    take_profit_percent: float,
) -> Decimal:
    """
    Calculate take profit price based on percentage.
    
    Args:
        entry_price: Entry price
        side: Order side (BUY/SELL)
        take_profit_percent: Take profit percentage
        
    Returns:
        Decimal: Take profit price
    """
    entry = Decimal(str(entry_price))
    pct = Decimal(str(take_profit_percent / 100))
    
    if side == OrderSide.BUY:
        return entry * (Decimal('1') + pct)
    else:  # SELL
        return entry * (Decimal('1') - pct)


def calculate_risk_reward_ratio(
    entry_price: Union[float, Decimal],
    stop_loss_price: Union[float, Decimal],
    take_profit_price: Union[float, Decimal],
    side: OrderSide,
) -> Decimal:
    """
    Calculate risk-reward ratio.
    
    Args:
        entry_price: Entry price
        stop_loss_price: Stop loss price
        take_profit_price: Take profit price
        side: Order side (BUY/SELL)
        
    Returns:
        Decimal: Risk-reward ratio
    """
    entry = Decimal(str(entry_price))
    stop = Decimal(str(stop_loss_price))
    profit = Decimal(str(take_profit_price))
    
    if side == OrderSide.BUY:
        risk = entry - stop
        reward = profit - entry
    else:  # SELL
        risk = stop - entry
        reward = entry - profit
    
    if risk == 0:
        return Decimal('0')
    
    return reward / risk


# ============================================================================
# MARKET DATA HELPERS
# ============================================================================

def calculate_spread(bid: Union[float, Decimal], ask: Union[float, Decimal]) -> Decimal:
    """
    Calculate bid-ask spread.
    
    Args:
        bid: Bid price
        ask: Ask price
        
    Returns:
        Decimal: Spread
    """
    b = Decimal(str(bid))
    a = Decimal(str(ask))
    return a - b


def calculate_spread_percentage(
    bid: Union[float, Decimal],
    ask: Union[float, Decimal],
) -> Decimal:
    """
    Calculate bid-ask spread as percentage.
    
    Args:
        bid: Bid price
        ask: Ask price
        
    Returns:
        Decimal: Spread percentage
    """
    b = Decimal(str(bid))
    a = Decimal(str(ask))
    
    if b == 0:
        return Decimal('0')
    
    return (a - b) / b * 100


def calculate_mid_price(bid: Union[float, Decimal], ask: Union[float, Decimal]) -> Decimal:
    """
    Calculate mid price.
    
    Args:
        bid: Bid price
        ask: Ask price
        
    Returns:
        Decimal: Mid price
    """
    b = Decimal(str(bid))
    a = Decimal(str(ask))
    return (b + a) / 2


def calculate_weighted_average_price(
    trades: List[Trade],
) -> Decimal:
    """
    Calculate weighted average price from trades.
    
    Args:
        trades: List of trades
        
    Returns:
        Decimal: Weighted average price
    """
    if not trades:
        return Decimal('0')
    
    total_value = Decimal('0')
    total_quantity = Decimal('0')
    
    for trade in trades:
        total_value += trade.price * trade.quantity
        total_quantity += trade.quantity
    
    if total_quantity == 0:
        return Decimal('0')
    
    return total_value / total_quantity


# ============================================================================
# RATE LIMITING HELPERS
# ============================================================================

def calculate_backoff_time(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
) -> float:
    """
    Calculate backoff time for retry attempts.
    
    Args:
        attempt: Attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Whether to add jitter
        
    Returns:
        float: Backoff time in seconds
    """
    import random
    
    delay = min(base_delay * (2 ** attempt), max_delay)
    
    if jitter:
        delay = delay * (0.5 + random.random())
    
    return delay


# ============================================================================
# STRING HELPERS
# ============================================================================

def mask_sensitive_data(data: Dict[str, Any], keys_to_mask: Optional[Set[str]] = None) -> Dict[str, Any]:
    """
    Mask sensitive data in a dictionary.
    
    Args:
        data: Dictionary containing data
        keys_to_mask: Set of keys to mask (default: common sensitive keys)
        
    Returns:
        Dict: Masked dictionary
    """
    if keys_to_mask is None:
        keys_to_mask = {
            "api_key", "api_secret", "api_passphrase", "secret",
            "password", "token", "access_token", "refresh_token",
            "private_key", "passphrase", "key", "secret_key",
            "apiKey", "apiSecret", "accessToken",
        }
    
    masked = {}
    for key, value in data.items():
        if any(mask_key in key.lower() for mask_key in keys_to_mask):
            if isinstance(value, str) and len(value) > 8:
                masked[key] = value[:4] + "****" + value[-4:]
            else:
                masked[key] = "***MASKED***"
        elif isinstance(value, dict):
            masked[key] = mask_sensitive_data(value, keys_to_mask)
        elif isinstance(value, list):
            masked[key] = [
                mask_sensitive_data(item, keys_to_mask) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            masked[key] = value
    
    return masked


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length.
    
    Args:
        s: String to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated
        
    Returns:
        str: Truncated string
    """
    if len(s) <= max_length:
        return s
    
    return s[:max_length - len(suffix)] + suffix


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "SymbolFormat",
    
    # Symbol formatting
    "format_symbol",
    "format_symbol_for_exchange",
    "parse_symbol",
    "normalize_symbol",
    
    # Order validation
    "validate_order",
    "validate_order_for_exchange",
    
    # Quantity and price normalization
    "normalize_quantity",
    "normalize_price",
    "calculate_order_value",
    "calculate_position_size",
    
    # Order type helpers
    "order_type_to_string",
    "string_to_order_type",
    
    # Time in force helpers
    "time_in_force_to_string",
    "string_to_time_in_force",
    
    # Position helpers
    "calculate_position_pnl",
    "calculate_position_pnl_percentage",
    "calculate_position_value",
    
    # Risk calculations
    "calculate_stop_loss_price",
    "calculate_take_profit_price",
    "calculate_risk_reward_ratio",
    
    # Market data helpers
    "calculate_spread",
    "calculate_spread_percentage",
    "calculate_mid_price",
    "calculate_weighted_average_price",
    
    # Rate limiting helpers
    "calculate_backoff_time",
    
    # String helpers
    "mask_sensitive_data",
    "truncate_string",
]
