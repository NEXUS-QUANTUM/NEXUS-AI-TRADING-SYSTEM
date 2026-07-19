# trading/exchanges/kraken/exceptions.py
# Nexus AI Trading System - Kraken Exchange Exceptions Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Kraken Exchange - Exception Module

This module provides a comprehensive exception hierarchy for the Kraken
exchange integration. It includes:

- Base exception classes for all Kraken errors
- Detailed error categorization
- Error code mapping from Kraken API
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

The exception hierarchy follows a logical structure that allows
for granular error handling while maintaining compatibility with
the broader Nexus trading system.
"""

import json
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime

# =============================================================================
# EXCEPTION TYPES
# =============================================================================

class KrakenErrorCode(str, Enum):
    """
    Kraken API error codes mapping.
    
    Reference: https://docs.kraken.com/api/docs/errors
    """
    # General errors
    E_API_GENERAL = "EAPI:General"
    E_API_INVALID_SIGNATURE = "EAPI:Invalid signature"
    E_API_INVALID_KEY = "EAPI:Invalid key"
    E_API_INVALID_NONCE = "EAPI:Invalid nonce"
    E_API_RATE_LIMIT = "EAPI:Rate limit exceeded"
    E_API_PERMISSION_DENIED = "EAPI:Permission denied"
    E_API_INTERNAL_ERROR = "EAPI:Internal error"
    E_API_SERVICE_UNAVAILABLE = "EAPI:Service unavailable"
    
    # Order errors
    E_ORDER_GENERAL = "EOrder:General"
    E_ORDER_INSUFFICIENT_FUNDS = "EOrder:Insufficient funds"
    E_ORDER_INVALID_VOLUME = "EOrder:Invalid volume"
    E_ORDER_INVALID_PRICE = "EOrder:Invalid price"
    E_ORDER_INVALID_SIDE = "EOrder:Invalid side"
    E_ORDER_INVALID_ORDER_TYPE = "EOrder:Invalid order type"
    E_ORDER_INVALID_PAIR = "EOrder:Invalid pair"
    E_ORDER_LIMIT_REACHED = "EOrder:Limit reached"
    E_ORDER_DUPLICATE = "EOrder:Duplicate order"
    E_ORDER_NOT_FOUND = "EOrder:Not found"
    E_ORDER_ALREADY_CANCELLED = "EOrder:Already cancelled"
    E_ORDER_ALREADY_CLOSED = "EOrder:Already closed"
    E_ORDER_PRICE_TOO_LOW = "EOrder:Price too low"
    E_ORDER_PRICE_TOO_HIGH = "EOrder:Price too high"
    E_ORDER_VOLUME_TOO_LOW = "EOrder:Volume too low"
    E_ORDER_VOLUME_TOO_HIGH = "EOrder:Volume too high"
    E_ORDER_MARKET_CLOSED = "EOrder:Market closed"
    E_ORDER_STOP_PRICE_INVALID = "EOrder:Invalid stop price"
    E_ORDER_LIMIT_PRICE_INVALID = "EOrder:Invalid limit price"
    
    # Position errors
    E_POSITION_GENERAL = "EPosition:General"
    E_POSITION_NOT_FOUND = "EPosition:Not found"
    E_POSITION_INVALID_SIDE = "EPosition:Invalid side"
    E_POSITION_INSUFFICIENT_MARGIN = "EPosition:Insufficient margin"
    E_POSITION_LIQUIDATION = "EPosition:Liquidation"
    
    # Account errors
    E_ACCOUNT_GENERAL = "EAccount:General"
    E_ACCOUNT_INSUFFICIENT_BALANCE = "EAccount:Insufficient balance"
    E_ACCOUNT_INVALID_CURRENCY = "EAccount:Invalid currency"
    E_ACCOUNT_WITHDRAWAL_DISABLED = "EAccount:Withdrawal disabled"
    E_ACCOUNT_DEPOSIT_DISABLED = "EAccount:Deposit disabled"
    E_ACCOUNT_TIER_LIMIT = "EAccount:Tier limit reached"
    E_ACCOUNT_VERIFICATION_REQUIRED = "EAccount:Verification required"
    E_ACCOUNT_SUSPENDED = "EAccount:Suspended"
    
    # Market data errors
    E_MARKET_GENERAL = "EMarket:General"
    E_MARKET_INVALID_SYMBOL = "EMarket:Invalid symbol"
    E_MARKET_NO_DATA = "EMarket:No data"
    E_MARKET_DATA_UNAVAILABLE = "EMarket:Data unavailable"
    E_MARKET_INTERVAL_INVALID = "EMarket:Invalid interval"
    
    # WebSocket errors
    E_WS_GENERAL = "EWS:General"
    E_WS_CONNECTION_FAILED = "EWS:Connection failed"
    E_WS_SUBSCRIPTION_FAILED = "EWS:Subscription failed"
    E_WS_INVALID_CHANNEL = "EWS:Invalid channel"
    E_WS_RATE_LIMIT = "EWS:Rate limit exceeded"
    E_WS_TIMEOUT = "EWS:Timeout"
    E_WS_ALREADY_SUBSCRIBED = "EWS:Already subscribed"
    E_WS_NOT_SUBSCRIBED = "EWS:Not subscribed"
    
    # Withdrawal errors
    E_WITHDRAWAL_GENERAL = "EWithdrawal:General"
    E_WITHDRAWAL_INVALID_ADDRESS = "EWithdrawal:Invalid address"
    E_WITHDRAWAL_INSUFFICIENT_BALANCE = "EWithdrawal:Insufficient balance"
    E_WITHDRAWAL_MINIMUM_AMOUNT = "EWithdrawal:Minimum amount not met"
    E_WITHDRAWAL_MAXIMUM_AMOUNT = "EWithdrawal:Maximum amount exceeded"
    E_WITHDRAWAL_2FA_REQUIRED = "EWithdrawal:2FA required"
    E_WITHDRAWAL_PENDING = "EWithdrawal:Already pending"
    E_WITHDRAWAL_NOT_ALLOWED = "EWithdrawal:Not allowed"
    
    # Data validation errors
    E_VALIDATION_GENERAL = "EValidation:General"
    E_VALIDATION_INVALID_PARAMETER = "EValidation:Invalid parameter"
    E_VALIDATION_MISSING_PARAMETER = "EValidation:Missing parameter"
    E_VALIDATION_INVALID_FORMAT = "EValidation:Invalid format"
    E_VALIDATION_INVALID_RANGE = "EValidation:Invalid range"
    
    # System errors
    E_SYSTEM_GENERAL = "ESystem:General"
    E_SYSTEM_MAINTENANCE = "ESystem:Maintenance"
    E_SYSTEM_UPGRADE = "ESystem:Upgrade"
    E_SYSTEM_DEGRADED = "ESystem:Degraded"


# =============================================================================
# ERROR CODE MAPPING
# =============================================================================

# Map Kraken error codes to exception classes
KRAKEN_ERROR_MAP = {
    # Authentication errors
    "EAPI:Invalid key": "KrakenAuthenticationError",
    "EAPI:Invalid signature": "KrakenAuthenticationError",
    "EAPI:Invalid nonce": "KrakenAuthenticationError",
    "EAPI:Permission denied": "KrakenPermissionError",
    
    # Rate limit errors
    "EAPI:Rate limit exceeded": "KrakenRateLimitError",
    "EWS:Rate limit exceeded": "KrakenRateLimitError",
    
    # Insufficient funds errors
    "EOrder:Insufficient funds": "KrakenInsufficientFundsError",
    "EAccount:Insufficient balance": "KrakenInsufficientFundsError",
    "EPosition:Insufficient margin": "KrakenInsufficientFundsError",
    
    # Order errors
    "EOrder:Invalid volume": "KrakenOrderError",
    "EOrder:Invalid price": "KrakenOrderError",
    "EOrder:Invalid side": "KrakenOrderError",
    "EOrder:Invalid order type": "KrakenOrderError",
    "EOrder:Invalid pair": "KrakenOrderError",
    "EOrder:Limit reached": "KrakenOrderError",
    "EOrder:Duplicate order": "KrakenOrderError",
    "EOrder:Not found": "KrakenOrderNotFoundError",
    "EOrder:Already cancelled": "KrakenOrderError",
    "EOrder:Already closed": "KrakenOrderError",
    "EOrder:Price too low": "KrakenOrderError",
    "EOrder:Price too high": "KrakenOrderError",
    "EOrder:Volume too low": "KrakenOrderError",
    "EOrder:Volume too high": "KrakenOrderError",
    "EOrder:Market closed": "KrakenOrderError",
    "EOrder:Invalid stop price": "KrakenOrderError",
    "EOrder:Invalid limit price": "KrakenOrderError",
    
    # Position errors
    "EPosition:Not found": "KrakenPositionNotFoundError",
    "EPosition:Invalid side": "KrakenPositionError",
    "EPosition:Liquidation": "KrakenLiquidationError",
    
    # Account errors
    "EAccount:Invalid currency": "KrakenAccountError",
    "EAccount:Withdrawal disabled": "KrakenWithdrawalError",
    "EAccount:Deposit disabled": "KrakenDepositError",
    "EAccount:Tier limit reached": "KrakenAccountError",
    "EAccount:Verification required": "KrakenVerificationError",
    "EAccount:Suspended": "KrakenAccountError",
    
    # Market data errors
    "EMarket:Invalid symbol": "KrakenInvalidSymbolError",
    "EMarket:No data": "KrakenDataError",
    "EMarket:Data unavailable": "KrakenDataError",
    "EMarket:Invalid interval": "KrakenDataError",
    
    # WebSocket errors
    "EWS:Connection failed": "KrakenWebSocketError",
    "EWS:Subscription failed": "KrakenWebSocketError",
    "EWS:Invalid channel": "KrakenWebSocketError",
    "EWS:Timeout": "KrakenWebSocketError",
    "EWS:Already subscribed": "KrakenWebSocketError",
    "EWS:Not subscribed": "KrakenWebSocketError",
    
    # Withdrawal errors
    "EWithdrawal:Invalid address": "KrakenInvalidAddressError",
    "EWithdrawal:Minimum amount not met": "KrakenWithdrawalError",
    "EWithdrawal:Maximum amount exceeded": "KrakenWithdrawalError",
    "EWithdrawal:2FA required": "KrakenTwoFactorError",
    "EWithdrawal:Already pending": "KrakenWithdrawalError",
    "EWithdrawal:Not allowed": "KrakenWithdrawalError",
    
    # Validation errors
    "EValidation:Invalid parameter": "KrakenValidationError",
    "EValidation:Missing parameter": "KrakenValidationError",
    "EValidation:Invalid format": "KrakenValidationError",
    "EValidation:Invalid range": "KrakenValidationError",
    
    # System errors
    "ESystem:Maintenance": "KrakenSystemError",
    "ESystem:Upgrade": "KrakenSystemError",
    "ESystem:Degraded": "KrakenSystemError",
}

# Kraken error codes to user-friendly messages
KRAKEN_ERROR_MESSAGES = {
    "EAPI:Invalid key": "Invalid API key. Please check your API credentials.",
    "EAPI:Invalid signature": "Invalid API signature. Please check your API secret.",
    "EAPI:Invalid nonce": "Invalid nonce. Please ensure your system time is synchronized.",
    "EAPI:Permission denied": "Permission denied. Your API key may not have the required permissions.",
    "EAPI:Rate limit exceeded": "Rate limit exceeded. Please slow down your request rate.",
    "EOrder:Insufficient funds": "Insufficient funds for this order. Please check your balance.",
    "EOrder:Invalid volume": "Invalid volume. Please check the order size.",
    "EOrder:Invalid price": "Invalid price. Please check the order price.",
    "EOrder:Invalid side": "Invalid side. Must be 'buy' or 'sell'.",
    "EOrder:Invalid order type": "Invalid order type. Please use a valid order type.",
    "EOrder:Invalid pair": "Invalid trading pair. Please check the symbol.",
    "EOrder:Limit reached": "Order limit reached. Too many open orders.",
    "EOrder:Duplicate order": "Duplicate order detected. Please wait before retrying.",
    "EOrder:Not found": "Order not found. The order may have been cancelled or filled.",
    "EOrder:Already cancelled": "Order already cancelled.",
    "EOrder:Already closed": "Order already closed.",
    "EOrder:Price too low": "Order price is too low. Please check the minimum price.",
    "EOrder:Price too high": "Order price is too high. Please check the maximum price.",
    "EOrder:Volume too low": "Order volume is too low. Please check the minimum order size.",
    "EOrder:Volume too high": "Order volume is too high. Please check the maximum order size.",
    "EOrder:Market closed": "Market is currently closed. Please try again later.",
    "EPosition:Not found": "Position not found. The position may have been closed.",
    "EPosition:Invalid side": "Invalid position side.",
    "EPosition:Liquidation": "Position has been liquidated.",
    "EAccount:Insufficient balance": "Insufficient account balance.",
    "EAccount:Invalid currency": "Invalid currency. Please check the currency code.",
    "EAccount:Withdrawal disabled": "Withdrawals are currently disabled for this account.",
    "EAccount:Deposit disabled": "Deposits are currently disabled for this account.",
    "EAccount:Tier limit reached": "Account tier limit reached.",
    "EAccount:Verification required": "Account verification required.",
    "EAccount:Suspended": "Account is suspended.",
    "EMarket:Invalid symbol": "Invalid symbol. Please check the trading pair.",
    "EMarket:No data": "No data available for this symbol.",
    "EMarket:Data unavailable": "Market data is currently unavailable.",
    "EWS:Connection failed": "WebSocket connection failed. Please check your connection.",
    "EWS:Subscription failed": "WebSocket subscription failed.",
    "EWS:Invalid channel": "Invalid WebSocket channel.",
    "EWS:Timeout": "WebSocket request timed out.",
    "EWithdrawal:Invalid address": "Invalid withdrawal address. Please check the address.",
    "EWithdrawal:Minimum amount not met": "Withdrawal amount is below the minimum.",
    "EWithdrawal:Maximum amount exceeded": "Withdrawal amount exceeds the maximum.",
    "EWithdrawal:2FA required": "Two-factor authentication required for withdrawal.",
    "EWithdrawal:Already pending": "Withdrawal already pending.",
    "EWithdrawal:Not allowed": "Withdrawal not allowed.",
    "EValidation:Invalid parameter": "Invalid parameter. Please check your input.",
    "EValidation:Missing parameter": "Missing required parameter.",
    "EValidation:Invalid format": "Invalid parameter format.",
    "EValidation:Invalid range": "Parameter out of range.",
    "ESystem:Maintenance": "System is currently under maintenance.",
    "ESystem:Upgrade": "System is being upgraded.",
    "ESystem:Degraded": "System is degraded. Some features may be unavailable.",
}

# Error categories for retry decisions
RETRYABLE_ERROR_CODES = {
    "EAPI:Rate limit exceeded",
    "EAPI:Service unavailable",
    "EAPI:Internal error",
    "EWS:Connection failed",
    "EWS:Timeout",
    "EMarket:Data unavailable",
    "EOrder:Duplicate order",
    "ESystem:Maintenance",
    "ESystem:Upgrade",
    "ESystem:Degraded",
}

# =============================================================================
# BASE EXCEPTION CLASSES
# =============================================================================

class KrakenError(Exception):
    """
    Base exception for all Kraken errors.
    
    Attributes:
        code: Kraken error code
        message: User-friendly error message
        details: Additional error details
        kraken_code: Raw Kraken error code
        context: Request context
        retryable: Whether the error is retryable
        timestamp: When the error occurred
    """
    
    def __init__(
        self,
        message: Optional[str] = None,
        code: Optional[Union[str, KrakenErrorCode]] = None,
        details: Optional[Dict[str, Any]] = None,
        kraken_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
        retryable: bool = False
    ):
        self.code = code
        self.details = details or {}
        self.kraken_code = kraken_code
        self.context = context or {}
        self.original_exception = original_exception
        self.retryable = retryable
        self.timestamp = datetime.utcnow()
        
        # Determine user-friendly message
        if not message and kraken_code:
            message = KRAKEN_ERROR_MESSAGES.get(kraken_code, kraken_code)
        
        if not message:
            message = "An error occurred while interacting with Kraken"
        
        super().__init__(message)
        self.message = str(self)
        
        # Log error
        self._log_error()
    
    def _log_error(self):
        """Log the error."""
        import logging
        logger = logging.getLogger(__name__)
        logger.error(
            f"KrakenError: {self.message} | "
            f"Code: {self.code} | "
            f"KrakenCode: {self.kraken_code} | "
            f"Context: {self.context}"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "kraken_code": self.kraken_code,
            "details": self.details,
            "context": self.context,
            "retryable": self.retryable,
            "timestamp": self.timestamp.isoformat()
        }
    
    def is_retryable(self) -> bool:
        """Check if the error is retryable."""
        return self.retryable or (
            self.kraken_code in RETRYABLE_ERROR_CODES
        )
    
    def get_recovery_suggestion(self) -> Optional[str]:
        """Get recovery suggestion for the error."""
        suggestions = {
            "EAPI:Rate limit exceeded": "Wait 60 seconds and retry with backoff",
            "EAPI:Service unavailable": "Wait and retry in 30 seconds",
            "EAPI:Internal error": "Retry with exponential backoff",
            "EOrder:Insufficient funds": "Check account balance and reduce order size",
            "EOrder:Invalid volume": "Check minimum/maximum order size requirements",
            "EOrder:Invalid price": "Check price precision and bounds",
            "EOrder:Duplicate order": "Wait 10 seconds before retrying",
            "EWS:Connection failed": "Check network connection and retry",
            "EWS:Timeout": "Increase timeout or retry",
            "EMarket:Invalid symbol": "Verify symbol format and availability",
            "EWithdrawal:Invalid address": "Verify address format and network",
            "EWithdrawal:2FA required": "Provide 2FA code",
            "EAccount:Verification required": "Complete account verification",
        }
        return suggestions.get(self.kraken_code) if self.kraken_code else None


# =============================================================================
# AUTHENTICATION EXCEPTIONS
# =============================================================================

class KrakenAuthenticationError(KrakenError):
    """Authentication error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Authentication failed. Please check your API credentials."
        super().__init__(message, **kwargs)


class KrakenPermissionError(KrakenError):
    """Permission error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Permission denied. Your API key lacks required permissions."
        super().__init__(message, **kwargs)


class KrakenTwoFactorError(KrakenError):
    """Two-factor authentication error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Two-factor authentication required or invalid."
        super().__init__(message, **kwargs)


# =============================================================================
# RATE LIMIT EXCEPTIONS
# =============================================================================

class KrakenRateLimitError(KrakenError):
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
# ORDER EXCEPTIONS
# =============================================================================

class KrakenOrderError(KrakenError):
    """Order error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Order operation failed."
        super().__init__(message, **kwargs)


class KrakenOrderNotFoundError(KrakenOrderError):
    """Order not found error."""
    def __init__(self, order_id: Optional[str] = None, **kwargs):
        self.order_id = order_id
        message = f"Order not found: {order_id}" if order_id else "Order not found."
        super().__init__(message, **kwargs)


class KrakenOrderCancelledError(KrakenOrderError):
    """Order already cancelled error."""
    def __init__(self, order_id: Optional[str] = None, **kwargs):
        self.order_id = order_id
        message = f"Order already cancelled: {order_id}" if order_id else "Order already cancelled."
        super().__init__(message, **kwargs)


# =============================================================================
# POSITION EXCEPTIONS
# =============================================================================

class KrakenPositionError(KrakenError):
    """Position error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Position operation failed."
        super().__init__(message, **kwargs)


class KrakenPositionNotFoundError(KrakenPositionError):
    """Position not found error."""
    def __init__(self, position_id: Optional[str] = None, **kwargs):
        self.position_id = position_id
        message = f"Position not found: {position_id}" if position_id else "Position not found."
        super().__init__(message, **kwargs)


class KrakenLiquidationError(KrakenPositionError):
    """Liquidation error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Position has been liquidated."
        super().__init__(message, **kwargs)


# =============================================================================
# ACCOUNT EXCEPTIONS
# =============================================================================

class KrakenAccountError(KrakenError):
    """Account error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Account operation failed."
        super().__init__(message, **kwargs)


class KrakenInsufficientFundsError(KrakenAccountError):
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


class KrakenVerificationError(KrakenAccountError):
    """Account verification error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Account verification required to perform this action."
        super().__init__(message, **kwargs)


class KrakenAccountSuspendedError(KrakenAccountError):
    """Account suspended error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Account has been suspended."
        super().__init__(message, **kwargs)


# =============================================================================
# DATA EXCEPTIONS
# =============================================================================

class KrakenDataError(KrakenError):
    """Data error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Market data operation failed."
        super().__init__(message, **kwargs)


class KrakenInvalidSymbolError(KrakenDataError):
    """Invalid symbol error."""
    def __init__(self, symbol: Optional[str] = None, **kwargs):
        self.symbol = symbol
        message = f"Invalid symbol: {symbol}" if symbol else "Invalid trading symbol."
        super().__init__(message, **kwargs)


# =============================================================================
# WEBSOCKET EXCEPTIONS
# =============================================================================

class KrakenWebSocketError(KrakenError):
    """WebSocket error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "WebSocket operation failed."
        super().__init__(message, retryable=True, **kwargs)


class KrakenWebSocketConnectionError(KrakenWebSocketError):
    """WebSocket connection error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "WebSocket connection failed."
        super().__init__(message, **kwargs)


class KrakenWebSocketSubscriptionError(KrakenWebSocketError):
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


# =============================================================================
# WITHDRAWAL EXCEPTIONS
# =============================================================================

class KrakenWithdrawalError(KrakenError):
    """Withdrawal error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Withdrawal operation failed."
        super().__init__(message, **kwargs)


class KrakenInvalidAddressError(KrakenWithdrawalError):
    """Invalid address error."""
    def __init__(self, address: Optional[str] = None, **kwargs):
        self.address = address
        message = f"Invalid withdrawal address: {address}" if address else "Invalid withdrawal address."
        super().__init__(message, **kwargs)


class KrakenDepositError(KrakenError):
    """Deposit error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Deposit operation failed."
        super().__init__(message, **kwargs)


# =============================================================================
# VALIDATION EXCEPTIONS
# =============================================================================

class KrakenValidationError(KrakenError):
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


class KrakenParameterError(KrakenValidationError):
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

class KrakenSystemError(KrakenError):
    """System error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Kraken system error."
        super().__init__(message, retryable=True, **kwargs)


class KrakenConnectionError(KrakenError):
    """Connection error."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        if not message:
            message = "Failed to connect to Kraken."
        super().__init__(message, retryable=True, **kwargs)


class KrakenTimeoutError(KrakenError):
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

def create_kraken_exception(
    kraken_code: str,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
    original_exception: Optional[Exception] = None
) -> KrakenError:
    """
    Factory function to create appropriate exception from Kraken error code.
    
    Args:
        kraken_code: Raw Kraken error code
        message: Optional custom message
        details: Additional details
        context: Request context
        original_exception: Original exception if any
        
    Returns:
        Appropriate KrakenError subclass
    """
    # Determine exception class
    exception_class = KrakenError
    
    if kraken_code in KRAKEN_ERROR_MAP:
        class_name = KRAKEN_ERROR_MAP[kraken_code]
        # Get the class from globals
        exception_class = globals().get(class_name, KrakenError)
    
    # Create instance
    return exception_class(
        message=message,
        kraken_code=kraken_code,
        details=details,
        context=context,
        original_exception=original_exception
    )


def handle_kraken_response(response: Dict[str, Any]) -> None:
    """
    Handle Kraken API response, raising exceptions for errors.
    
    Args:
        response: Kraken API response
        
    Raises:
        Appropriate KrakenError subclass
    """
    if 'error' in response and response['error']:
        error = response['error'][0]
        
        # Check if error is a dictionary
        if isinstance(error, dict):
            kraken_code = error.get('code', '')
            message = error.get('message', '')
            details = error.get('details', {})
        else:
            kraken_code = str(error)
            message = KRAKEN_ERROR_MESSAGES.get(kraken_code, kraken_code)
            details = {}
        
        raise create_kraken_exception(
            kraken_code=kraken_code,
            message=message,
            details=details,
            context={'response': response}
        )


# =============================================================================
# DECORATORS AND HELPERS
# =============================================================================

def retry_on_kraken_error(
    max_attempts: int = 3,
    exceptions: Union[type, tuple] = (KrakenRateLimitError, KrakenSystemError, KrakenConnectionError)
):
    """
    Decorator to retry on specific Kraken errors.
    
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
                    # Exponential backoff
                    delay = 2 ** attempt
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
                    # Exponential backoff
                    import time
                    delay = 2 ** attempt
                    time.sleep(delay)
            raise last_exception
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Base exception
    'KrakenError',
    
    # Authentication exceptions
    'KrakenAuthenticationError',
    'KrakenPermissionError',
    'KrakenTwoFactorError',
    
    # Rate limit exception
    'KrakenRateLimitError',
    
    # Order exceptions
    'KrakenOrderError',
    'KrakenOrderNotFoundError',
    'KrakenOrderCancelledError',
    
    # Position exceptions
    'KrakenPositionError',
    'KrakenPositionNotFoundError',
    'KrakenLiquidationError',
    
    # Account exceptions
    'KrakenAccountError',
    'KrakenInsufficientFundsError',
    'KrakenVerificationError',
    'KrakenAccountSuspendedError',
    
    # Data exceptions
    'KrakenDataError',
    'KrakenInvalidSymbolError',
    
    # WebSocket exceptions
    'KrakenWebSocketError',
    'KrakenWebSocketConnectionError',
    'KrakenWebSocketSubscriptionError',
    
    # Withdrawal exceptions
    'KrakenWithdrawalError',
    'KrakenInvalidAddressError',
    'KrakenDepositError',
    
    # Validation exceptions
    'KrakenValidationError',
    'KrakenParameterError',
    
    # System exceptions
    'KrakenSystemError',
    'KrakenConnectionError',
    'KrakenTimeoutError',
    
    # Factory and helpers
    'create_kraken_exception',
    'handle_kraken_response',
    'retry_on_kraken_error',
    
    # Error codes
    'KrakenErrorCode',
    'KRAKEN_ERROR_MAP',
    'KRAKEN_ERROR_MESSAGES',
    'RETRYABLE_ERROR_CODES',
]
