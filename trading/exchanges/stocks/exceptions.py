# trading/exchanges/stocks/exceptions.py
# Nexus AI Trading System - Stock Exchange Exceptions Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Stock Exchange - Exception Module

This module provides a comprehensive exception hierarchy for stock trading
integrations across multiple brokers including Alpaca, Interactive Brokers,
TD Ameritrade, Robinhood, E*TRADE, Fidelity, Schwab, and others.

It includes:

- Base exception classes for all stock errors
- Detailed error categorization
- Error code mapping from various broker APIs
- Retry decision logic
- Error context and metadata
- User-friendly error messages
- Error recovery suggestions
- Exception chaining support
- Error logging integration
- Rate limit specific exceptions
- Authentication specific exceptions
- Order and position specific exceptions
- WebSocket specific exceptions
- Account specific exceptions
- Market data specific exceptions

The exception hierarchy follows a logical structure that allows
for granular error handling while maintaining compatibility with
the broader Nexus trading system.

Supported Broker Error Codes:
- Alpaca: https://alpaca.markets/docs/api-documentation/api-v2/#errors
- IBKR: https://interactivebrokers.github.io/tws-api/
- TD Ameritrade: https://developer.tdameritrade.com/error-codes
- Robinhood: https://robinhood.com/us/en/support/
- E*TRADE: https://developer.etrade.com/
"""

import json
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime

# =============================================================================
# EXCEPTION TYPES
# =============================================================================

class StockErrorCode(str, Enum):
    """
    Stock trading error codes.
    
    General error codes that map across multiple brokers.
    """
    # Success
    SUCCESS = "0"
    
    # Authentication errors
    AUTH_INVALID_KEY = "AUTH-001"
    AUTH_INVALID_SECRET = "AUTH-002"
    AUTH_INVALID_TOKEN = "AUTH-003"
    AUTH_TOKEN_EXPIRED = "AUTH-004"
    AUTH_INVALID_OAUTH = "AUTH-005"
    AUTH_PERMISSION_DENIED = "AUTH-006"
    AUTH_2FA_REQUIRED = "AUTH-007"
    
    # Rate limit errors
    RATE_LIMIT_EXCEEDED = "RATE-001"
    RATE_LIMIT_ABUSE = "RATE-002"
    RATE_LIMIT_RESET = "RATE-003"
    
    # Account errors
    ACCOUNT_INSUFFICIENT_FUNDS = "ACCT-001"
    ACCOUNT_FROZEN = "ACCT-002"
    ACCOUNT_SUSPENDED = "ACCT-003"
    ACCOUNT_RESTRICTED = "ACCT-004"
    ACCOUNT_NOT_FOUND = "ACCT-005"
    ACCOUNT_INVALID = "ACCT-006"
    ACCOUNT_PATTERN_DAY_TRADER = "ACCT-007"
    
    # Order errors
    ORDER_INVALID = "ORD-001"
    ORDER_NOT_FOUND = "ORD-002"
    ORDER_INVALID_SYMBOL = "ORD-003"
    ORDER_INVALID_QUANTITY = "ORD-004"
    ORDER_INVALID_PRICE = "ORD-005"
    ORDER_INVALID_SIDE = "ORD-006"
    ORDER_INVALID_TYPE = "ORD-007"
    ORDER_INVALID_TIME_IN_FORCE = "ORD-008"
    ORDER_REJECTED = "ORD-009"
    ORDER_CANCELLED = "ORD-010"
    ORDER_FILLED = "ORD-011"
    ORDER_PARTIALLY_FILLED = "ORD-012"
    ORDER_EXPIRED = "ORD-013"
    ORDER_DUPLICATE = "ORD-014"
    ORDER_LIMIT_REACHED = "ORD-015"
    ORDER_MARKET_CLOSED = "ORD-016"
    ORDER_EXTENDED_HOURS = "ORD-017"
    
    # Position errors
    POSITION_NOT_FOUND = "POS-001"
    POSITION_INVALID = "POS-002"
    POSITION_CLOSED = "POS-003"
    POSITION_LIQUIDATED = "POS-004"
    
    # Market data errors
    MARKET_DATA_UNAVAILABLE = "DATA-001"
    MARKET_DATA_INVALID_SYMBOL = "DATA-002"
    MARKET_DATA_NO_DATA = "DATA-003"
    MARKET_DATA_INVALID_TIMEFRAME = "DATA-004"
    MARKET_DATA_TOO_MANY_REQUESTS = "DATA-005"
    
    # Validation errors
    VALIDATION_INVALID_PARAMETER = "VAL-001"
    VALIDATION_MISSING_PARAMETER = "VAL-002"
    VALIDATION_INVALID_FORMAT = "VAL-003"
    VALIDATION_INVALID_RANGE = "VAL-004"
    
    # WebSocket errors
    WS_CONNECTION_FAILED = "WS-001"
    WS_SUBSCRIPTION_FAILED = "WS-002"
    WS_INVALID_CHANNEL = "WS-003"
    WS_RATE_LIMIT = "WS-004"
    WS_TIMEOUT = "WS-005"
    WS_ALREADY_SUBSCRIBED = "WS-006"
    WS_NOT_SUBSCRIBED = "WS-007"
    
    # System errors
    SYSTEM_ERROR = "SYS-001"
    SYSTEM_MAINTENANCE = "SYS-002"
    SYSTEM_UPGRADE = "SYS-003"
    SYSTEM_DEGRADED = "SYS-004"
    SYSTEM_UNAVAILABLE = "SYS-005"
    
    # Connection errors
    CONNECTION_TIMEOUT = "CONN-001"
    CONNECTION_REFUSED = "CONN-002"
    CONNECTION_CLOSED = "CONN-003"
    CONNECTION_RESET = "CONN-004"


# =============================================================================
# ERROR CODE MAPPING
# =============================================================================

# Map stock error codes to exception classes
STOCK_ERROR_MAP = {
    # Authentication errors
    "AUTH-001": "StockAuthenticationError",
    "AUTH-002": "StockAuthenticationError",
    "AUTH-003": "StockAuthenticationError",
    "AUTH-004": "StockAuthenticationError",
    "AUTH-005": "StockAuthenticationError",
    "AUTH-006": "StockPermissionError",
    "AUTH-007": "StockTwoFactorError",
    
    # Rate limit errors
    "RATE-001": "StockRateLimitError",
    "RATE-002": "StockRateLimitError",
    "RATE-003": "StockRateLimitError",
    
    # Account errors
    "ACCT-001": "StockInsufficientFundsError",
    "ACCT-002": "StockAccountFrozenError",
    "ACCT-003": "StockAccountSuspendedError",
    "ACCT-004": "StockAccountRestrictedError",
    "ACCT-005": "StockNotFoundError",
    "ACCT-006": "StockValidationError",
    "ACCT-007": "StockPatternDayTraderError",
    
    # Order errors
    "ORD-001": "StockOrderError",
    "ORD-002": "StockOrderNotFoundError",
    "ORD-003": "StockInvalidSymbolError",
    "ORD-004": "StockOrderQuantityError",
    "ORD-005": "StockOrderPriceError",
    "ORD-006": "StockOrderSideError",
    "ORD-007": "StockOrderTypeError",
    "ORD-008": "StockOrderTimeInForceError",
    "ORD-009": "StockOrderRejectedError",
    "ORD-010": "StockOrderCancelledError",
    "ORD-011": "StockOrderFilledError",
    "ORD-012": "StockOrderPartiallyFilledError",
    "ORD-013": "StockOrderExpiredError",
    "ORD-014": "StockOrderDuplicateError",
    "ORD-015": "StockOrderLimitError",
    "ORD-016": "StockMarketClosedError",
    "ORD-017": "StockExtendedHoursError",
    
    # Position errors
    "POS-001": "StockPositionNotFoundError",
    "POS-002": "StockPositionError",
    "POS-003": "StockPositionClosedError",
    "POS-004": "StockPositionLiquidationError",
    
    # Market data errors
    "DATA-001": "StockMarketDataError",
    "DATA-002": "StockInvalidSymbolError",
    "DATA-003": "StockDataError",
    "DATA-004": "StockDataError",
    "DATA-005": "StockRateLimitError",
    
    # Validation errors
    "VAL-001": "StockValidationError",
    "VAL-002": "StockValidationError",
    "VAL-003": "StockValidationError",
    "VAL-004": "StockValidationError",
    
    # WebSocket errors
    "WS-001": "StockWebSocketConnectionError",
    "WS-002": "StockWebSocketSubscriptionError",
    "WS-003": "StockWebSocketError",
    "WS-004": "StockWebSocketRateLimitError",
    "WS-005": "StockWebSocketError",
    "WS-006": "StockWebSocketError",
    "WS-007": "StockWebSocketError",
    
    # System errors
    "SYS-001": "StockSystemError",
    "SYS-002": "StockSystemError",
    "SYS-003": "StockSystemError",
    "SYS-004": "StockSystemError",
    "SYS-005": "StockSystemError",
    
    # Connection errors
    "CONN-001": "StockTimeoutError",
    "CONN-002": "StockConnectionError",
    "CONN-003": "StockConnectionError",
    "CONN-004": "StockConnectionError",
}

# Error messages
STOCK_ERROR_MESSAGES = {
    "AUTH-001": "Invalid API key. Please check your API credentials.",
    "AUTH-002": "Invalid API secret. Please check your API credentials.",
    "AUTH-003": "Invalid authentication token. Please re-authenticate.",
    "AUTH-004": "Authentication token expired. Please refresh your token.",
    "AUTH-005": "Invalid OAuth credentials. Please check your OAuth configuration.",
    "AUTH-006": "Permission denied. Your account lacks the required permissions.",
    "AUTH-007": "Two-factor authentication required.",
    
    "RATE-001": "Rate limit exceeded. Please slow down your request rate.",
    "RATE-002": "Rate limit abuse detected. Please wait before retrying.",
    "RATE-003": "Rate limit reset in progress. Please wait.",
    
    "ACCT-001": "Insufficient funds. Please check your account balance.",
    "ACCT-002": "Account is frozen. Please contact support.",
    "ACCT-003": "Account is suspended. Please contact support.",
    "ACCT-004": "Account is restricted. Please contact support.",
    "ACCT-005": "Account not found. Please check your account ID.",
    "ACCT-006": "Invalid account. Please check your account configuration.",
    "ACCT-007": "Pattern day trader restriction. Please be aware of PDT rules.",
    
    "ORD-001": "Invalid order. Please check your order parameters.",
    "ORD-002": "Order not found. The order may have been cancelled or filled.",
    "ORD-003": "Invalid symbol. Please check the stock symbol.",
    "ORD-004": "Invalid quantity. Please check the order size.",
    "ORD-005": "Invalid price. Please check the order price.",
    "ORD-006": "Invalid side. Must be 'buy' or 'sell'.",
    "ORD-007": "Invalid order type. Please use a valid order type.",
    "ORD-008": "Invalid time in force. Please use a valid time in force.",
    "ORD-009": "Order rejected. Please check your order parameters.",
    "ORD-010": "Order already cancelled.",
    "ORD-011": "Order already filled.",
    "ORD-012": "Order partially filled.",
    "ORD-013": "Order expired.",
    "ORD-014": "Duplicate order detected. Please wait before retrying.",
    "ORD-015": "Order limit reached. Too many open orders.",
    "ORD-016": "Market is currently closed. Please try again during market hours.",
    "ORD-017": "Extended hours trading not supported for this symbol.",
    
    "POS-001": "Position not found. The position may have been closed.",
    "POS-002": "Invalid position. Please check your position parameters.",
    "POS-003": "Position already closed.",
    "POS-004": "Position has been liquidated.",
    
    "DATA-001": "Market data unavailable. Please try again later.",
    "DATA-002": "Invalid symbol. Please check the stock symbol.",
    "DATA-003": "No data available for this symbol.",
    "DATA-004": "Invalid timeframe. Please use a valid timeframe.",
    "DATA-005": "Too many market data requests. Please slow down.",
    
    "VAL-001": "Invalid parameter. Please check your input.",
    "VAL-002": "Missing required parameter.",
    "VAL-003": "Invalid parameter format.",
    "VAL-004": "Parameter out of range.",
    
    "WS-001": "WebSocket connection failed. Please check your connection.",
    "WS-002": "WebSocket subscription failed.",
    "WS-003": "Invalid WebSocket channel.",
    "WS-004": "WebSocket rate limit exceeded.",
    "WS-005": "WebSocket request timed out.",
    "WS-006": "Already subscribed to this channel.",
    "WS-007": "Not subscribed to this channel.",
    
    "SYS-001": "System error. Please try again later.",
    "SYS-002": "System is under maintenance. Please try again later.",
    "SYS-003": "System is being upgraded. Please try again later.",
    "SYS-004": "System is degraded. Some features may be unavailable.",
    "SYS-005": "System is unavailable. Please try again later.",
    
    "CONN-001": "Request timed out. Please try again.",
    "CONN-002": "Connection refused. Please check your network.",
    "CONN-003": "Connection closed. Please reconnect.",
    "CONN-004": "Connection reset. Please try again.",
}

# Error categories for retry decisions
RETRYABLE_ERROR_CODES = {
    "RATE-001",
    "RATE-002",
    "RATE-003",
    "DATA-005",
    "WS-001",
    "WS-004",
    "WS-005",
    "SYS-001",
    "SYS-002",
    "SYS-003",
    "SYS-004",
    "SYS-005",
    "CONN-001",
    "CONN-002",
    "CONN-003",
    "CONN-004",
}

# Error categories for recovery actions
RECOVERY_ACTIONS = {
    "AUTH-001": "Verify API key is correct and active",
    "AUTH-002": "Verify API secret is correct",
    "AUTH-003": "Re-authenticate and obtain new token",
    "AUTH-004": "Refresh authentication token",
    "AUTH-005": "Check OAuth configuration",
    "AUTH-006": "Check API key permissions",
    "AUTH-007": "Provide 2FA code",
    
    "RATE-001": "Implement exponential backoff and retry",
    "RATE-002": "Reduce request rate significantly",
    
    "ACCT-001": "Reduce order size or deposit funds",
    "ACCT-007": "Be aware of pattern day trader rules",
    
    "ORD-016": "Wait for market open or use extended hours",
    "ORD-017": "Use regular market hours only",
    
    "DATA-004": "Use valid timeframe: 1m, 5m, 15m, 1h, 1d, 1w, 1M",
}

# Broker-specific error code mappings
BROKER_ERROR_MAP = {
    'alpaca': {
        '401': 'AUTH-001',
        '403': 'AUTH-006',
        '422': 'VAL-001',
        '429': 'RATE-001',
        '500': 'SYS-001',
    },
    'ibkr': {
        '101': 'AUTH-001',
        '102': 'AUTH-002',
        '201': 'ORD-001',
        '202': 'ORD-002',
    },
    'td_ameritrade': {
        '401': 'AUTH-001',
        '403': 'AUTH-006',
        '404': 'ORD-002',
        '429': 'RATE-001',
    },
    'etrade': {
        '401': 'AUTH-001',
        '403': 'AUTH-006',
        '404': 'ORD-002',
        '429': 'RATE-001',
        '500': 'SYS-001',
    },
}

# =============================================================================
# BASE EXCEPTION CLASSES
# =============================================================================

class StockError(Exception):
    """
    Base exception for all stock trading errors.
    
    Attributes:
        code: Stock error code
        message: User-friendly error message
        details: Additional error details
        broker_code: Raw broker error code
        broker: Broker name
        context: Request context
        retryable: Whether the error is retryable
        timestamp: When the error occurred
        recovery_action: Suggested recovery action
    """
    
    def __init__(
        self,
        message: Optional[str] = None,
        code: Optional[Union[str, StockErrorCode]] = None,
        details: Optional[Dict[str, Any]] = None,
        broker_code: Optional[str] = None,
        broker: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
        retryable: bool = False
    ):
        self.code = code
        self.details = details or {}
        self.broker_code = broker_code
        self.broker = broker
        self.context = context or {}
        self.original_exception = original_exception
        self.retryable = retryable
        self.timestamp = datetime.utcnow()
        
        # Determine user-friendly message
        if not message and code and code in STOCK_ERROR_MESSAGES:
            message = STOCK_ERROR_MESSAGES[code]
        elif not message and broker_code:
            message = f"Broker error: {broker_code}"
        
        if not message:
            message = "An error occurred during stock trading operation"
        
        super().__init__(message)
        self.message = str(self)
        
        # Get recovery action
        self.recovery_action = RECOVERY_ACTIONS.get(code) if code else None
        
        # Log error
        self._log_error()
    
    def _log_error(self):
        """Log the error."""
        import logging
        logger = logging.getLogger(__name__)
        logger.error(
            f"StockError: {self.message} | "
            f"Code: {self.code} | "
            f"BrokerCode: {self.broker_code} | "
            f"Broker: {self.broker} | "
            f"Context: {self.context}"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "broker_code": self.broker_code,
            "broker": self.broker,
            "details": self.details,
            "context": self.context,
            "retryable": self.retryable,
            "recovery_action": self.recovery_action,
            "timestamp": self.timestamp.isoformat()
        }
    
    def is_retryable(self) -> bool:
        """Check if the error is retryable."""
        return self.retryable or (
            self.code in RETRYABLE_ERROR_CODES
        )
    
    def get_recovery_suggestion(self) -> Optional[str]:
        """Get recovery suggestion for the error."""
        return self.recovery_action


# =============================================================================
# AUTHENTICATION EXCEPTIONS
# =============================================================================

class StockAuthenticationError(StockError):
    """Authentication error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Authentication failed. Please check your credentials."
        super().__init__(message, **kwargs)


class StockPermissionError(StockError):
    """Permission error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Permission denied. Your account lacks required permissions."
        super().__init__(message, **kwargs)


class StockTwoFactorError(StockError):
    """Two-factor authentication error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Two-factor authentication required."
        super().__init__(message, **kwargs)


# =============================================================================
# RATE LIMIT EXCEPTIONS
# =============================================================================

class StockRateLimitError(StockError):
    """Rate limit error."""
    def __init__(
        self,
        message: Optional[str] = None,
        reset_time: Optional[datetime] = None,
        **kwargs
    ):
        self.reset_time = reset_time
        if not message:
            message = "Rate limit exceeded. Please wait before retrying."
        super().__init__(message, retryable=True, **kwargs)


# =============================================================================
# ACCOUNT EXCEPTIONS
# =============================================================================

class StockAccountError(StockError):
    """Account error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Account operation failed."
        super().__init__(message, **kwargs)


class StockInsufficientFundsError(StockAccountError):
    """Insufficient funds error."""
    def __init__(
        self,
        message: Optional[str] = None,
        currency: Optional[str] = None,
        available: Optional[float] = None,
        required: Optional[float] = None,
        **kwargs
    ):
        self.currency = currency
        self.available = available
        self.required = required
        if not message:
            if currency:
                message = f"Insufficient funds for {currency}"
                if available is not None and required is not None:
                    message += f": {available} available, {required} required"
            else:
                message = "Insufficient funds"
        super().__init__(message, **kwargs)


class StockAccountFrozenError(StockAccountError):
    """Account frozen error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Account is frozen. Please contact support."
        super().__init__(message, **kwargs)


class StockAccountSuspendedError(StockAccountError):
    """Account suspended error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Account is suspended. Please contact support."
        super().__init__(message, **kwargs)


class StockAccountRestrictedError(StockAccountError):
    """Account restricted error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Account is restricted. Please contact support."
        super().__init__(message, **kwargs)


class StockPatternDayTraderError(StockAccountError):
    """Pattern day trader error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Pattern day trader restriction applies."
        super().__init__(message, **kwargs)


# =============================================================================
# ORDER EXCEPTIONS
# =============================================================================

class StockOrderError(StockError):
    """Order error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Order operation failed."
        super().__init__(message, **kwargs)


class StockOrderNotFoundError(StockOrderError):
    """Order not found error."""
    def __init__(self, order_id: Optional[str] = None, **kwargs):
        self.order_id = order_id
        message = f"Order not found: {order_id}" if order_id else "Order not found."
        super().__init__(message, **kwargs)


class StockOrderCancelledError(StockOrderError):
    """Order already cancelled error."""
    def __init__(self, order_id: Optional[str] = None, **kwargs):
        self.order_id = order_id
        message = f"Order already cancelled: {order_id}" if order_id else "Order already cancelled."
        super().__init__(message, **kwargs)


class StockOrderFilledError(StockOrderError):
    """Order already filled error."""
    def __init__(self, order_id: Optional[str] = None, **kwargs):
        self.order_id = order_id
        message = f"Order already filled: {order_id}" if order_id else "Order already filled."
        super().__init__(message, **kwargs)


class StockOrderPartiallyFilledError(StockOrderError):
    """Order partially filled error."""
    def __init__(self, order_id: Optional[str] = None, **kwargs):
        self.order_id = order_id
        message = f"Order partially filled: {order_id}" if order_id else "Order partially filled."
        super().__init__(message, **kwargs)


class StockOrderExpiredError(StockOrderError):
    """Order expired error."""
    def __init__(self, order_id: Optional[str] = None, **kwargs):
        self.order_id = order_id
        message = f"Order expired: {order_id}" if order_id else "Order expired."
        super().__init__(message, **kwargs)


class StockOrderRejectedError(StockOrderError):
    """Order rejected error."""
    def __init__(self, order_id: Optional[str] = None, reason: Optional[str] = None, **kwargs):
        self.order_id = order_id
        self.reason = reason
        message = f"Order rejected: {order_id}" if order_id else "Order rejected."
        if reason:
            message += f" Reason: {reason}"
        super().__init__(message, **kwargs)


class StockOrderQuantityError(StockOrderError):
    """Invalid order quantity error."""
    def __init__(
        self,
        quantity: Optional[float] = None,
        min_quantity: Optional[float] = None,
        max_quantity: Optional[float] = None,
        **kwargs
    ):
        self.quantity = quantity
        self.min_quantity = min_quantity
        self.max_quantity = max_quantity
        message = "Invalid order quantity"
        if quantity is not None:
            message += f": {quantity}"
        if min_quantity is not None and max_quantity is not None:
            message += f" (min: {min_quantity}, max: {max_quantity})"
        super().__init__(message, **kwargs)


class StockOrderPriceError(StockOrderError):
    """Invalid order price error."""
    def __init__(
        self,
        price: Optional[float] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        **kwargs
    ):
        self.price = price
        self.min_price = min_price
        self.max_price = max_price
        message = "Invalid order price"
        if price is not None:
            message += f": {price}"
        if min_price is not None and max_price is not None:
            message += f" (min: {min_price}, max: {max_price})"
        super().__init__(message, **kwargs)


class StockOrderSideError(StockOrderError):
    """Invalid order side error."""
    def __init__(self, side: Optional[str] = None, **kwargs):
        self.side = side
        message = f"Invalid order side: {side}" if side else "Invalid order side. Must be 'buy' or 'sell'."
        super().__init__(message, **kwargs)


class StockOrderTypeError(StockOrderError):
    """Invalid order type error."""
    def __init__(self, order_type: Optional[str] = None, **kwargs):
        self.order_type = order_type
        message = f"Invalid order type: {order_type}" if order_type else "Invalid order type."
        super().__init__(message, **kwargs)


class StockOrderTimeInForceError(StockOrderError):
    """Invalid time in force error."""
    def __init__(self, tif: Optional[str] = None, **kwargs):
        self.tif = tif
        message = f"Invalid time in force: {tif}" if tif else "Invalid time in force."
        super().__init__(message, **kwargs)


class StockOrderDuplicateError(StockOrderError):
    """Duplicate order error."""
    def __init__(self, client_order_id: Optional[str] = None, **kwargs):
        self.client_order_id = client_order_id
        message = f"Duplicate order: {client_order_id}" if client_order_id else "Duplicate order detected."
        super().__init__(message, **kwargs)


class StockOrderLimitError(StockOrderError):
    """Order limit reached error."""
    def __init__(self, limit: Optional[int] = None, **kwargs):
        self.limit = limit
        message = f"Order limit reached: {limit}" if limit else "Order limit reached. Too many open orders."
        super().__init__(message, **kwargs)


class StockMarketClosedError(StockOrderError):
    """Market closed error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Market is closed. Please try again during market hours."
        super().__init__(message, **kwargs)


class StockExtendedHoursError(StockOrderError):
    """Extended hours error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Extended hours trading not supported for this symbol."
        super().__init__(message, **kwargs)


# =============================================================================
# POSITION EXCEPTIONS
# =============================================================================

class StockPositionError(StockError):
    """Position error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Position operation failed."
        super().__init__(message, **kwargs)


class StockPositionNotFoundError(StockPositionError):
    """Position not found error."""
    def __init__(self, symbol: Optional[str] = None, **kwargs):
        self.symbol = symbol
        message = f"Position not found: {symbol}" if symbol else "Position not found."
        super().__init__(message, **kwargs)


class StockPositionClosedError(StockPositionError):
    """Position already closed error."""
    def __init__(self, symbol: Optional[str] = None, **kwargs):
        self.symbol = symbol
        message = f"Position already closed: {symbol}" if symbol else "Position already closed."
        super().__init__(message, **kwargs)


class StockPositionLiquidationError(StockPositionError):
    """Position liquidation error."""
    def __init__(self, symbol: Optional[str] = None, **kwargs):
        self.symbol = symbol
        message = f"Position liquidated: {symbol}" if symbol else "Position has been liquidated."
        super().__init__(message, **kwargs)


# =============================================================================
# MARKET DATA EXCEPTIONS
# =============================================================================

class StockMarketDataError(StockError):
    """Market data error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Market data operation failed."
        super().__init__(message, **kwargs)


class StockDataError(StockMarketDataError):
    """Data error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "No data available."
        super().__init__(message, **kwargs)


class StockInvalidSymbolError(StockMarketDataError):
    """Invalid symbol error."""
    def __init__(self, symbol: Optional[str] = None, **kwargs):
        self.symbol = symbol
        message = f"Invalid symbol: {symbol}" if symbol else "Invalid trading symbol."
        super().__init__(message, **kwargs)


# =============================================================================
# VALIDATION EXCEPTIONS
# =============================================================================

class StockValidationError(StockError):
    """Validation error."""
    def __init__(
        self,
        message: Optional[str] = None,
        parameter: Optional[str] = None,
        **kwargs
    ):
        self.parameter = parameter
        if not message:
            message = f"Validation error for parameter: {parameter}" if parameter else "Validation error."
        super().__init__(message, **kwargs)


class StockParameterError(StockValidationError):
    """Parameter error."""
    def __init__(
        self,
        parameter: str,
        value: Any = None,
        constraint: Optional[str] = None,
        **kwargs
    ):
        self.value = value
        self.constraint = constraint
        message = f"Invalid parameter '{parameter}'"
        if value is not None:
            message += f": {value}"
        if constraint:
            message += f". Must satisfy: {constraint}"
        super().__init__(message, parameter=parameter, **kwargs)


# =============================================================================
# WEBSOCKET EXCEPTIONS
# =============================================================================

class StockWebSocketError(StockError):
    """WebSocket error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "WebSocket operation failed."
        super().__init__(message, retryable=True, **kwargs)


class StockWebSocketConnectionError(StockWebSocketError):
    """WebSocket connection error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "WebSocket connection failed."
        super().__init__(message, **kwargs)


class StockWebSocketSubscriptionError(StockWebSocketError):
    """WebSocket subscription error."""
    def __init__(
        self,
        message: Optional[str] = None,
        channel: Optional[str] = None,
        **kwargs
    ):
        self.channel = channel
        if not message:
            message = f"WebSocket subscription failed: {channel}" if channel else "WebSocket subscription failed."
        super().__init__(message, **kwargs)


class StockWebSocketRateLimitError(StockWebSocketError):
    """WebSocket rate limit error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "WebSocket rate limit exceeded."
        super().__init__(message, retryable=True, **kwargs)


# =============================================================================
# SYSTEM EXCEPTIONS
# =============================================================================

class StockSystemError(StockError):
    """System error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "System error. Please try again later."
        super().__init__(message, retryable=True, **kwargs)


class StockConnectionError(StockError):
    """Connection error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Failed to connect to broker."
        super().__init__(message, retryable=True, **kwargs)


class StockTimeoutError(StockError):
    """Timeout error."""
    def __init__(
        self,
        message: Optional[str] = None,
        timeout: Optional[float] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        self.timeout = timeout
        self.operation = operation
        if not message:
            message = f"Operation '{operation}' timed out after {timeout}s" if operation and timeout else "Request timed out."
        super().__init__(message, retryable=True, **kwargs)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_stock_exception(
    code: Union[str, StockErrorCode],
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    broker_code: Optional[str] = None,
    broker: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    original_exception: Optional[Exception] = None
) -> StockError:
    """
    Factory function to create appropriate exception from stock error code.
    
    Args:
        code: Stock error code
        message: Optional custom message
        details: Additional details
        broker_code: Raw broker error code
        broker: Broker name
        context: Request context
        original_exception: Original exception if any
        
    Returns:
        Appropriate StockError subclass
    """
    # Determine exception class
    exception_class = StockError
    
    if code in STOCK_ERROR_MAP:
        class_name = STOCK_ERROR_MAP[code]
        exception_class = globals().get(class_name, StockError)
    
    # Create instance
    return exception_class(
        message=message,
        code=code,
        details=details,
        broker_code=broker_code,
        broker=broker,
        context=context,
        original_exception=original_exception
    )


def map_broker_error(
    broker: str,
    broker_code: str,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
    original_exception: Optional[Exception] = None
) -> StockError:
    """
    Map broker-specific error to stock exception.
    
    Args:
        broker: Broker name
        broker_code: Broker error code
        message: Optional custom message
        details: Additional details
        context: Request context
        original_exception: Original exception
        
    Returns:
        StockError
    """
    # Try to map broker error code
    stock_code = None
    
    if broker in BROKER_ERROR_MAP and broker_code in BROKER_ERROR_MAP[broker]:
        stock_code = BROKER_ERROR_MAP[broker][broker_code]
    
    if not stock_code:
        stock_code = StockErrorCode.SYSTEM_ERROR
    
    return create_stock_exception(
        code=stock_code,
        message=message,
        details=details,
        broker_code=broker_code,
        broker=broker,
        context=context,
        original_exception=original_exception
    )


# =============================================================================
# DECORATORS AND HELPERS
# =============================================================================

def retry_on_stock_error(
    max_attempts: int = 3,
    exceptions: Union[type, tuple] = (
        StockRateLimitError,
        StockSystemError,
        StockConnectionError,
        StockTimeoutError,
        StockWebSocketError,
        StockWebSocketRateLimitError
    )
):
    """
    Decorator to retry on specific stock errors.
    
    Args:
        max_attempts: Maximum number of retry attempts
        exceptions: Exception types to retry on
        
    Returns:
        Decorated function
    """
    import asyncio
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        raise
                    # Exponential backoff with jitter
                    delay = min(2 ** attempt, 30) + (2 ** attempt * 0.1)
                    await asyncio.sleep(delay)
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        raise
                    import time
                    delay = min(2 ** attempt, 30) + (2 ** attempt * 0.1)
                    time.sleep(delay)
            raise last_exception
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def handle_stock_errors(func):
    """
    Decorator to handle stock errors and convert to appropriate exceptions.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    from functools import wraps
    
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except StockError:
            raise
        except Exception as e:
            raise StockError(f"Unexpected error: {str(e)}", original_exception=e)
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except StockError:
            raise
        except Exception as e:
            raise StockError(f"Unexpected error: {str(e)}", original_exception=e)
    
    import inspect
    if inspect.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Base exception
    'StockError',
    
    # Authentication exceptions
    'StockAuthenticationError',
    'StockPermissionError',
    'StockTwoFactorError',
    
    # Rate limit exception
    'StockRateLimitError',
    
    # Account exceptions
    'StockAccountError',
    'StockInsufficientFundsError',
    'StockAccountFrozenError',
    'StockAccountSuspendedError',
    'StockAccountRestrictedError',
    'StockPatternDayTraderError',
    
    # Order exceptions
    'StockOrderError',
    'StockOrderNotFoundError',
    'StockOrderCancelledError',
    'StockOrderFilledError',
    'StockOrderPartiallyFilledError',
    'StockOrderExpiredError',
    'StockOrderRejectedError',
    'StockOrderQuantityError',
    'StockOrderPriceError',
    'StockOrderSideError',
    'StockOrderTypeError',
    'StockOrderTimeInForceError',
    'StockOrderDuplicateError',
    'StockOrderLimitError',
    'StockMarketClosedError',
    'StockExtendedHoursError',
    
    # Position exceptions
    'StockPositionError',
    'StockPositionNotFoundError',
    'StockPositionClosedError',
    'StockPositionLiquidationError',
    
    # Market data exceptions
    'StockMarketDataError',
    'StockDataError',
    'StockInvalidSymbolError',
    
    # Validation exceptions
    'StockValidationError',
    'StockParameterError',
    
    # WebSocket exceptions
    'StockWebSocketError',
    'StockWebSocketConnectionError',
    'StockWebSocketSubscriptionError',
    'StockWebSocketRateLimitError',
    
    # System exceptions
    'StockSystemError',
    'StockConnectionError',
    'StockTimeoutError',
    
    # Factory and helpers
    'create_stock_exception',
    'map_broker_error',
    'retry_on_stock_error',
    'handle_stock_errors',
    
    # Error codes
    'StockErrorCode',
    'STOCK_ERROR_MAP',
    'STOCK_ERROR_MESSAGES',
    'RETRYABLE_ERROR_CODES',
    'RECOVERY_ACTIONS',
    'BROKER_ERROR_MAP'
]
