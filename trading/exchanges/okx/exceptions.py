# trading/exchanges/okx/exceptions.py
# Nexus AI Trading System - OKX Exchange Exceptions Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
OKX Exchange - Exception Module

This module provides a comprehensive exception hierarchy for the OKX
exchange integration. It includes:

- Base exception classes for all OKX errors
- Detailed error categorization
- Error code mapping from OKX API
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

OKX Error Codes Reference:
- 0: Success
- 1: System error
- 2: Invalid parameter
- 3: Invalid API key
- 4: Invalid signature
- 5: Invalid timestamp
- 6: Rate limit exceeded
- 7: Insufficient balance
- 8: Invalid order
- 9: Invalid instrument
- 10: Market closed
- 11: Order not found
- 12: Position not found
- 13: Invalid withdrawal address
- 14: Withdrawal failed
- 15: Deposit failed
- 16: Transfer failed
- 17: Account frozen
- 18: Permission denied
- 19: Too many requests
- 20: Maintenance
- 21: Invalid passphrase
- 22: 2FA required
- 23: Verification required
- 24: Order already cancelled
- 25: Order already filled
- 26: Price out of range
- 27: Volume out of range
- 28: Invalid order type
- 29: Invalid side
- 30: Invalid time in force
"""

import json
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime

# =============================================================================
# EXCEPTION TYPES
# =============================================================================

class OKXErrorCode(str, Enum):
    """
    OKX API error codes mapping.
    
    Reference: https://www.okx.com/docs-v5/en/#overview-error-codes
    """
    # Success
    SUCCESS = "0"
    
    # System errors
    SYSTEM_ERROR = "1"
    MAINTENANCE = "20"
    SERVICE_UNAVAILABLE = "500"
    
    # Authentication errors
    INVALID_API_KEY = "3"
    INVALID_SIGNATURE = "4"
    INVALID_TIMESTAMP = "5"
    INVALID_PASSPHRASE = "21"
    PERMISSION_DENIED = "18"
    TWO_FA_REQUIRED = "22"
    VERIFICATION_REQUIRED = "23"
    
    # Rate limit errors
    RATE_LIMIT_EXCEEDED = "6"
    TOO_MANY_REQUESTS = "19"
    
    # Parameter errors
    INVALID_PARAMETER = "2"
    INVALID_INSTRUMENT = "9"
    INVALID_ORDER_TYPE = "28"
    INVALID_SIDE = "29"
    INVALID_TIME_IN_FORCE = "30"
    PRICE_OUT_OF_RANGE = "26"
    VOLUME_OUT_OF_RANGE = "27"
    
    # Account errors
    INSUFFICIENT_BALANCE = "7"
    ACCOUNT_FROZEN = "17"
    INVALID_WITHDRAWAL_ADDRESS = "13"
    WITHDRAWAL_FAILED = "14"
    DEPOSIT_FAILED = "15"
    TRANSFER_FAILED = "16"
    
    # Order errors
    INVALID_ORDER = "8"
    ORDER_NOT_FOUND = "11"
    ORDER_ALREADY_CANCELLED = "24"
    ORDER_ALREADY_FILLED = "25"
    MARKET_CLOSED = "10"
    
    # Position errors
    POSITION_NOT_FOUND = "12"
    POSITION_LIMIT_REACHED = "31"
    LIQUIDATION = "32"
    
    # WebSocket errors
    WS_CONNECTION_FAILED = "10001"
    WS_SUBSCRIPTION_FAILED = "10002"
    WS_INVALID_CHANNEL = "10003"
    WS_RATE_LIMIT = "10004"


# =============================================================================
# ERROR CODE MAPPING
# =============================================================================

# Map OKX error codes to exception classes
OKX_ERROR_MAP = {
    "1": "OKXSystemError",
    "2": "OKXValidationError",
    "3": "OKXAuthenticationError",
    "4": "OKXAuthenticationError",
    "5": "OKXAuthenticationError",
    "6": "OKXRateLimitError",
    "7": "OKXInsufficientFundsError",
    "8": "OKXOrderError",
    "9": "OKXInvalidSymbolError",
    "10": "OKXMarketClosedError",
    "11": "OKXOrderNotFoundError",
    "12": "OKXPositionNotFoundError",
    "13": "OKXInvalidAddressError",
    "14": "OKXWithdrawalError",
    "15": "OKXDepositError",
    "16": "OKXTransferError",
    "17": "OKXAccountFrozenError",
    "18": "OKXPermissionError",
    "19": "OKXRateLimitError",
    "20": "OKXSystemError",
    "21": "OKXAuthenticationError",
    "22": "OKXTwoFactorError",
    "23": "OKXVerificationError",
    "24": "OKXOrderCancelledError",
    "25": "OKXOrderFilledError",
    "26": "OKXPriceOutOfRangeError",
    "27": "OKXVolumeOutOfRangeError",
    "28": "OKXOrderTypeError",
    "29": "OKXSideError",
    "30": "OKXTimeInForceError",
    "31": "OKXPositionLimitError",
    "32": "OKXLiquidationError",
    "10001": "OKXWebSocketConnectionError",
    "10002": "OKXWebSocketSubscriptionError",
    "10003": "OKXWebSocketError",
    "10004": "OKXWebSocketRateLimitError",
}

# OKX error codes to user-friendly messages
OKX_ERROR_MESSAGES = {
    "1": "System error. Please try again later.",
    "2": "Invalid parameter. Please check your input.",
    "3": "Invalid API key. Please check your API credentials.",
    "4": "Invalid API signature. Please check your API secret.",
    "5": "Invalid timestamp. Please ensure your system time is synchronized.",
    "6": "Rate limit exceeded. Please slow down your request rate.",
    "7": "Insufficient balance. Please check your account balance.",
    "8": "Invalid order. Please check your order parameters.",
    "9": "Invalid instrument ID. Please check the symbol.",
    "10": "Market is currently closed. Please try again later.",
    "11": "Order not found. The order may have been cancelled or filled.",
    "12": "Position not found. The position may have been closed.",
    "13": "Invalid withdrawal address. Please check the address.",
    "14": "Withdrawal failed. Please try again later.",
    "15": "Deposit failed. Please try again later.",
    "16": "Transfer failed. Please check account balances.",
    "17": "Account is frozen. Please contact support.",
    "18": "Permission denied. Your API key may not have the required permissions.",
    "19": "Too many requests. Please wait before retrying.",
    "20": "System is under maintenance. Please try again later.",
    "21": "Invalid API passphrase. Please check your passphrase.",
    "22": "Two-factor authentication required.",
    "23": "Account verification required. Please complete verification.",
    "24": "Order is already cancelled.",
    "25": "Order is already filled.",
    "26": "Price is out of range. Please check price limits.",
    "27": "Volume is out of range. Please check volume limits.",
    "28": "Invalid order type. Please use a valid order type.",
    "29": "Invalid side. Must be 'buy' or 'sell'.",
    "30": "Invalid time in force. Please use a valid time in force.",
    "31": "Position limit reached. Too many open positions.",
    "32": "Position has been liquidated.",
    "10001": "WebSocket connection failed. Please check your connection.",
    "10002": "WebSocket subscription failed.",
    "10003": "Invalid WebSocket channel.",
    "10004": "WebSocket rate limit exceeded.",
}

# Error categories for retry decisions
RETRYABLE_ERROR_CODES = {
    "1",  # System error
    "6",  # Rate limit exceeded
    "19",  # Too many requests
    "20",  # Maintenance
    "500",  # Service unavailable
    "10001",  # WebSocket connection failed
}

# Error categories for recovery actions
RECOVERY_ACTIONS = {
    "3": "Verify API key is correct and active",
    "4": "Verify API secret is correct",
    "5": "Sync system time with NTP server",
    "6": "Implement exponential backoff and retry",
    "7": "Reduce order size or deposit funds",
    "13": "Verify address format and network",
    "18": "Check API key permissions",
    "21": "Verify API passphrase",
    "22": "Provide 2FA code",
    "23": "Complete account verification",
    "26": "Adjust price to acceptable range",
    "27": "Adjust volume to acceptable range",
    "31": "Close some positions first",
}

# =============================================================================
# BASE EXCEPTION CLASSES
# =============================================================================

class OKXError(Exception):
    """
    Base exception for all OKX errors.
    
    Attributes:
        code: OKX error code
        message: User-friendly error message
        details: Additional error details
        okx_code: Raw OKX error code
        context: Request context
        retryable: Whether the error is retryable
        timestamp: When the error occurred
        recovery_action: Suggested recovery action
    """
    
    def __init__(
        self,
        message: Optional[str] = None,
        code: Optional[Union[str, OKXErrorCode]] = None,
        details: Optional[Dict[str, Any]] = None,
        okx_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
        retryable: bool = False
    ):
        self.code = code
        self.details = details or {}
        self.okx_code = okx_code
        self.context = context or {}
        self.original_exception = original_exception
        self.retryable = retryable
        self.timestamp = datetime.utcnow()
        
        # Determine user-friendly message
        if not message and okx_code:
            message = OKX_ERROR_MESSAGES.get(okx_code, okx_code)
        
        if not message:
            message = "An error occurred while interacting with OKX"
        
        super().__init__(message)
        self.message = str(self)
        
        # Get recovery action
        self.recovery_action = RECOVERY_ACTIONS.get(okx_code) if okx_code else None
        
        # Log error
        self._log_error()
    
    def _log_error(self):
        """Log the error."""
        import logging
        logger = logging.getLogger(__name__)
        logger.error(
            f"OKXError: {self.message} | "
            f"Code: {self.code} | "
            f"OKXCode: {self.okx_code} | "
            f"Context: {self.context}"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "okx_code": self.okx_code,
            "details": self.details,
            "context": self.context,
            "retryable": self.retryable,
            "recovery_action": self.recovery_action,
            "timestamp": self.timestamp.isoformat()
        }
    
    def is_retryable(self) -> bool:
        """Check if the error is retryable."""
        return self.retryable or (
            self.okx_code in RETRYABLE_ERROR_CODES
        )
    
    def get_recovery_suggestion(self) -> Optional[str]:
        """Get recovery suggestion for the error."""
        return self.recovery_action


# =============================================================================
# AUTHENTICATION EXCEPTIONS
# =============================================================================

class OKXAuthenticationError(OKXError):
    """Authentication error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Authentication failed. Please check your API credentials."
        super().__init__(message, **kwargs)


class OKXPermissionError(OKXError):
    """Permission error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Permission denied. Your API key lacks required permissions."
        super().__init__(message, **kwargs)


class OKXTwoFactorError(OKXError):
    """Two-factor authentication error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Two-factor authentication required or invalid."
        super().__init__(message, **kwargs)


class OKXVerificationError(OKXError):
    """Account verification error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Account verification required to perform this action."
        super().__init__(message, **kwargs)


# =============================================================================
# RATE LIMIT EXCEPTIONS
# =============================================================================

class OKXRateLimitError(OKXError):
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

class OKXAccountError(OKXError):
    """Account error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Account operation failed."
        super().__init__(message, **kwargs)


class OKXInsufficientFundsError(OKXAccountError):
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


class OKXAccountFrozenError(OKXAccountError):
    """Account frozen error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Account is frozen. Please contact support."
        super().__init__(message, **kwargs)


# =============================================================================
# ORDER EXCEPTIONS
# =============================================================================

class OKXOrderError(OKXError):
    """Order error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Order operation failed."
        super().__init__(message, **kwargs)


class OKXOrderNotFoundError(OKXOrderError):
    """Order not found error."""
    def __init__(self, order_id: Optional[str] = None, **kwargs):
        self.order_id = order_id
        message = f"Order not found: {order_id}" if order_id else "Order not found."
        super().__init__(message, **kwargs)


class OKXOrderCancelledError(OKXOrderError):
    """Order already cancelled error."""
    def __init__(self, order_id: Optional[str] = None, **kwargs):
        self.order_id = order_id
        message = f"Order already cancelled: {order_id}" if order_id else "Order already cancelled."
        super().__init__(message, **kwargs)


class OKXOrderFilledError(OKXOrderError):
    """Order already filled error."""
    def __init__(self, order_id: Optional[str] = None, **kwargs):
        self.order_id = order_id
        message = f"Order already filled: {order_id}" if order_id else "Order already filled."
        super().__init__(message, **kwargs)


class OKXOrderTypeError(OKXOrderError):
    """Invalid order type error."""
    def __init__(self, order_type: Optional[str] = None, **kwargs):
        self.order_type = order_type
        message = f"Invalid order type: {order_type}" if order_type else "Invalid order type."
        super().__init__(message, **kwargs)


class OKXSideError(OKXOrderError):
    """Invalid side error."""
    def __init__(self, side: Optional[str] = None, **kwargs):
        self.side = side
        message = f"Invalid side: {side}" if side else "Invalid side. Must be 'buy' or 'sell'."
        super().__init__(message, **kwargs)


class OKXTimeInForceError(OKXOrderError):
    """Invalid time in force error."""
    def __init__(self, tif: Optional[str] = None, **kwargs):
        self.tif = tif
        message = f"Invalid time in force: {tif}" if tif else "Invalid time in force."
        super().__init__(message, **kwargs)


class OKXPriceOutOfRangeError(OKXOrderError):
    """Price out of range error."""
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
        message = "Price is out of range"
        if price is not None:
            message += f": {price}"
        if min_price is not None and max_price is not None:
            message += f" (min: {min_price}, max: {max_price})"
        super().__init__(message, **kwargs)


class OKXVolumeOutOfRangeError(OKXOrderError):
    """Volume out of range error."""
    def __init__(
        self,
        volume: Optional[float] = None,
        min_volume: Optional[float] = None,
        max_volume: Optional[float] = None,
        **kwargs
    ):
        self.volume = volume
        self.min_volume = min_volume
        self.max_volume = max_volume
        message = "Volume is out of range"
        if volume is not None:
            message += f": {volume}"
        if min_volume is not None and max_volume is not None:
            message += f" (min: {min_volume}, max: {max_volume})"
        super().__init__(message, **kwargs)


# =============================================================================
# POSITION EXCEPTIONS
# =============================================================================

class OKXPositionError(OKXError):
    """Position error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Position operation failed."
        super().__init__(message, **kwargs)


class OKXPositionNotFoundError(OKXPositionError):
    """Position not found error."""
    def __init__(self, position_id: Optional[str] = None, **kwargs):
        self.position_id = position_id
        message = f"Position not found: {position_id}" if position_id else "Position not found."
        super().__init__(message, **kwargs)


class OKXPositionLimitError(OKXPositionError):
    """Position limit reached error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Position limit reached. Too many open positions."
        super().__init__(message, **kwargs)


class OKXLiquidationError(OKXPositionError):
    """Liquidation error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Position has been liquidated."
        super().__init__(message, **kwargs)


# =============================================================================
# MARKET DATA EXCEPTIONS
# =============================================================================

class OKXMarketDataError(OKXError):
    """Market data error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Market data operation failed."
        super().__init__(message, **kwargs)


class OKXInvalidSymbolError(OKXMarketDataError):
    """Invalid symbol error."""
    def __init__(self, symbol: Optional[str] = None, **kwargs):
        self.symbol = symbol
        message = f"Invalid symbol: {symbol}" if symbol else "Invalid trading symbol."
        super().__init__(message, **kwargs)


class OKXMarketClosedError(OKXMarketDataError):
    """Market closed error."""
    def __init__(self, symbol: Optional[str] = None, **kwargs):
        self.symbol = symbol
        message = f"Market closed: {symbol}" if symbol else "Market is currently closed."
        super().__init__(message, **kwargs)


# =============================================================================
# WITHDRAWAL AND DEPOSIT EXCEPTIONS
# =============================================================================

class OKXWithdrawalError(OKXError):
    """Withdrawal error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Withdrawal operation failed."
        super().__init__(message, **kwargs)


class OKXInvalidAddressError(OKXWithdrawalError):
    """Invalid address error."""
    def __init__(self, address: Optional[str] = None, **kwargs):
        self.address = address
        message = f"Invalid withdrawal address: {address}" if address else "Invalid withdrawal address."
        super().__init__(message, **kwargs)


class OKXDepositError(OKXError):
    """Deposit error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Deposit operation failed."
        super().__init__(message, **kwargs)


class OKXTransferError(OKXError):
    """Transfer error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Transfer operation failed."
        super().__init__(message, **kwargs)


# =============================================================================
# WEBSOCKET EXCEPTIONS
# =============================================================================

class OKXWebSocketError(OKXError):
    """WebSocket error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "WebSocket operation failed."
        super().__init__(message, retryable=True, **kwargs)


class OKXWebSocketConnectionError(OKXWebSocketError):
    """WebSocket connection error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "WebSocket connection failed."
        super().__init__(message, **kwargs)


class OKXWebSocketSubscriptionError(OKXWebSocketError):
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


class OKXWebSocketRateLimitError(OKXWebSocketError):
    """WebSocket rate limit error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "WebSocket rate limit exceeded."
        super().__init__(message, retryable=True, **kwargs)


# =============================================================================
# VALIDATION EXCEPTIONS
# =============================================================================

class OKXValidationError(OKXError):
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


class OKXParameterError(OKXValidationError):
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
# SYSTEM EXCEPTIONS
# =============================================================================

class OKXSystemError(OKXError):
    """System error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "OKX system error."
        super().__init__(message, retryable=True, **kwargs)


class OKXConnectionError(OKXError):
    """Connection error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Failed to connect to OKX."
        super().__init__(message, retryable=True, **kwargs)


class OKXTimeoutError(OKXError):
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

def create_okx_exception(
    okx_code: str,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
    original_exception: Optional[Exception] = None,
    raw_response: Optional[Dict[str, Any]] = None
) -> OKXError:
    """
    Factory function to create appropriate exception from OKX error code.
    
    Args:
        okx_code: Raw OKX error code
        message: Optional custom message
        details: Additional details
        context: Request context
        original_exception: Original exception if any
        raw_response: Raw API response
        
    Returns:
        Appropriate OKXError subclass
    """
    # Determine exception class
    exception_class = OKXError
    
    if okx_code in OKX_ERROR_MAP:
        class_name = OKX_ERROR_MAP[okx_code]
        # Get the class from globals
        exception_class = globals().get(class_name, OKXError)
    
    # Create instance
    return exception_class(
        message=message,
        okx_code=okx_code,
        details=details,
        context=context,
        original_exception=original_exception
    )


def handle_okx_response(response: Dict[str, Any]) -> None:
    """
    Handle OKX API response, raising exceptions for errors.
    
    Args:
        response: OKX API response
        
    Raises:
        Appropriate OKXError subclass
    """
    code = response.get('code', '')
    
    if code != '0':
        message = response.get('msg', 'Unknown error')
        details = {
            'code': code,
            'message': message,
            'data': response.get('data')
        }
        
        raise create_okx_exception(
            okx_code=code,
            message=message,
            details=details,
            context={'response': response}
        )


def handle_okx_error_response(error_data: Dict[str, Any]) -> None:
    """
    Handle OKX error response from WebSocket.
    
    Args:
        error_data: WebSocket error data
        
    Raises:
        Appropriate OKXError subclass
    """
    code = error_data.get('code', '')
    message = error_data.get('msg', 'Unknown error')
    
    if code:
        raise create_okx_exception(
            okx_code=code,
            message=message,
            details=error_data,
            context={'ws_error': True}
        )
    else:
        raise OKXError(message)


# =============================================================================
# DECORATORS AND HELPERS
# =============================================================================

def retry_on_okx_error(
    max_attempts: int = 3,
    exceptions: Union[type, tuple] = (
        OKXRateLimitError,
        OKXSystemError,
        OKXConnectionError,
        OKXTimeoutError,
        OKXWebSocketError,
        OKXWebSocketRateLimitError
    )
):
    """
    Decorator to retry on specific OKX errors.
    
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
                    # Exponential backoff with jitter
                    import time
                    delay = min(2 ** attempt, 30) + (2 ** attempt * 0.1)
                    time.sleep(delay)
            raise last_exception
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def handle_okx_errors(func):
    """
    Decorator to handle OKX errors and convert to appropriate exceptions.
    
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
        except OKXError:
            raise
        except Exception as e:
            raise OKXError(f"Unexpected error: {str(e)}", original_exception=e)
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except OKXError:
            raise
        except Exception as e:
            raise OKXError(f"Unexpected error: {str(e)}", original_exception=e)
    
    import inspect
    if inspect.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Base exception
    'OKXError',
    
    # Authentication exceptions
    'OKXAuthenticationError',
    'OKXPermissionError',
    'OKXTwoFactorError',
    'OKXVerificationError',
    
    # Rate limit exception
    'OKXRateLimitError',
    
    # Account exceptions
    'OKXAccountError',
    'OKXInsufficientFundsError',
    'OKXAccountFrozenError',
    
    # Order exceptions
    'OKXOrderError',
    'OKXOrderNotFoundError',
    'OKXOrderCancelledError',
    'OKXOrderFilledError',
    'OKXOrderTypeError',
    'OKXSideError',
    'OKXTimeInForceError',
    'OKXPriceOutOfRangeError',
    'OKXVolumeOutOfRangeError',
    
    # Position exceptions
    'OKXPositionError',
    'OKXPositionNotFoundError',
    'OKXPositionLimitError',
    'OKXLiquidationError',
    
    # Market data exceptions
    'OKXMarketDataError',
    'OKXInvalidSymbolError',
    'OKXMarketClosedError',
    
    # Withdrawal and deposit exceptions
    'OKXWithdrawalError',
    'OKXInvalidAddressError',
    'OKXDepositError',
    'OKXTransferError',
    
    # WebSocket exceptions
    'OKXWebSocketError',
    'OKXWebSocketConnectionError',
    'OKXWebSocketSubscriptionError',
    'OKXWebSocketRateLimitError',
    
    # Validation exceptions
    'OKXValidationError',
    'OKXParameterError',
    
    # System exceptions
    'OKXSystemError',
    'OKXConnectionError',
    'OKXTimeoutError',
    
    # Factory and helpers
    'create_okx_exception',
    'handle_okx_response',
    'handle_okx_error_response',
    'retry_on_okx_error',
    'handle_okx_errors',
    
    # Error codes
    'OKXErrorCode',
    'OKX_ERROR_MAP',
    'OKX_ERROR_MESSAGES',
    'RETRYABLE_ERROR_CODES',
    'RECOVERY_ACTIONS'
]
