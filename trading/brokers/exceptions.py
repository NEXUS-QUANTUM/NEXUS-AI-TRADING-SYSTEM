# trading/brokers/exceptions.py
"""
NEXUS AI TRADING SYSTEM - Broker Exceptions
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module defines all broker-related exceptions used across the trading system.
Exceptions are organized hierarchically to allow fine-grained error handling
and provide detailed error context for debugging and monitoring.
"""

from typing import Any, Dict, Optional, Union
from enum import Enum


# ============================================================================
# EXCEPTION BASE CLASSES
# ============================================================================

class BrokerError(Exception):
    """
    Base exception for all broker-related errors.
    
    All broker exceptions inherit from this class to allow catching
    any broker error at a high level.
    """
    
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        broker_id: Optional[str] = None,
        symbol: Optional[str] = None,
    ):
        self.message = message
        self.code = code
        self.data = data or {}
        self.broker_id = broker_id
        self.symbol = symbol
        
        # Add symbol to data if provided
        if symbol and "symbol" not in self.data:
            self.data["symbol"] = symbol
        
        # Add broker_id to data if provided
        if broker_id and "broker_id" not in self.data:
            self.data["broker_id"] = broker_id
        
        super().__init__(message)
    
    def __str__(self) -> str:
        parts = [self.message]
        if self.code:
            parts.append(f"(code: {self.code})")
        if self.broker_id:
            parts.append(f"[broker: {self.broker_id}]")
        if self.symbol:
            parts.append(f"[symbol: {self.symbol}]")
        return " ".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "data": self.data,
            "broker_id": self.broker_id,
            "symbol": self.symbol,
        }


# ============================================================================
# CONNECTION EXCEPTIONS
# ============================================================================

class BrokerConnectionError(BrokerError):
    """Raised when connection to broker fails."""
    pass


class BrokerDisconnectionError(BrokerError):
    """Raised when disconnection from broker fails."""
    pass


class BrokerTimeoutError(BrokerError):
    """Raised when a broker request times out."""
    pass


class BrokerConnectionPoolError(BrokerError):
    """Raised when connection pool operations fail."""
    pass


class BrokerWebSocketError(BrokerError):
    """Raised when WebSocket operations fail."""
    pass


class BrokerReconnectionError(BrokerError):
    """Raised when reconnection attempts fail."""
    pass


# ============================================================================
# AUTHENTICATION EXCEPTIONS
# ============================================================================

class BrokerAuthenticationError(BrokerError):
    """Raised when authentication with broker fails."""
    pass


class BrokerAuthorizationError(BrokerError):
    """Raised when authorization fails (insufficient permissions)."""
    pass


class BrokerAPIKeyError(BrokerAuthenticationError):
    """Raised when API key is invalid or expired."""
    pass


class BrokerTokenExpiredError(BrokerAuthenticationError):
    """Raised when authentication token has expired."""
    pass


class BrokerTwoFactorRequiredError(BrokerAuthenticationError):
    """Raised when 2FA is required but not provided."""
    pass


# ============================================================================
# ORDER EXCEPTIONS
# ============================================================================

class BrokerOrderError(BrokerError):
    """Raised when order operations fail."""
    pass


class BrokerOrderNotFoundError(BrokerOrderError):
    """Raised when an order cannot be found."""
    pass


class BrokerOrderRejectedError(BrokerOrderError):
    """Raised when an order is rejected by the broker."""
    pass


class BrokerOrderCancellationError(BrokerOrderError):
    """Raised when order cancellation fails."""
    pass


class BrokerOrderModificationError(BrokerOrderError):
    """Raised when order modification fails."""
    pass


class BrokerOrderValidationError(BrokerOrderError):
    """Raised when order validation fails."""
    pass


class BrokerInsufficientBalanceError(BrokerOrderError):
    """Raised when there is insufficient balance for an order."""
    pass


class BrokerMarginError(BrokerOrderError):
    """Raised when margin requirements are not met."""
    pass


class BrokerPositionError(BrokerError):
    """Raised when position operations fail."""
    pass


class BrokerPositionNotFoundError(BrokerPositionError):
    """Raised when a position cannot be found."""
    pass


class BrokerPositionCloseError(BrokerPositionError):
    """Raised when closing a position fails."""
    pass


# ============================================================================
# MARKET DATA EXCEPTIONS
# ============================================================================

class BrokerDataError(BrokerError):
    """Raised when market data operations fail."""
    pass


class BrokerSymbolNotFoundError(BrokerDataError):
    """Raised when a symbol is not found."""
    pass


class BrokerMarketDataUnavailableError(BrokerDataError):
    """Raised when market data is unavailable."""
    pass


class BrokerHistoricalDataError(BrokerDataError):
    """Raised when historical data retrieval fails."""
    pass


class BrokerRateLimitError(BrokerDataError):
    """Raised when rate limit is exceeded."""
    pass


class BrokerWebSocketDataError(BrokerDataError):
    """Raised when WebSocket data feed has errors."""
    pass


# ============================================================================
# CONFIGURATION EXCEPTIONS
# ============================================================================

class BrokerConfigError(BrokerError):
    """Raised when broker configuration is invalid."""
    pass


class BrokerConfigNotFoundError(BrokerConfigError):
    """Raised when broker configuration is not found."""
    pass


class BrokerConfigValidationError(BrokerConfigError):
    """Raised when broker configuration validation fails."""
    pass


class BrokerEndpointError(BrokerConfigError):
    """Raised when broker endpoint configuration is invalid."""
    pass


# ============================================================================
# ACCOUNT EXCEPTIONS
# ============================================================================

class BrokerAccountError(BrokerError):
    """Raised when account operations fail."""
    pass


class BrokerAccountNotFoundError(BrokerAccountError):
    """Raised when an account cannot be found."""
    pass


class BrokerAccountLockedError(BrokerAccountError):
    """Raised when an account is locked."""
    pass


class BrokerAccountSuspendedError(BrokerAccountError):
    """Raised when an account is suspended."""
    pass


# ============================================================================
# HEALTH & MONITORING EXCEPTIONS
# ============================================================================

class BrokerHealthCheckError(BrokerError):
    """Raised when health check fails."""
    pass


class BrokerUnhealthyError(BrokerHealthCheckError):
    """Raised when broker is unhealthy."""
    pass


class BrokerDegradedError(BrokerHealthCheckError):
    """Raised when broker is degraded."""
    pass


class BrokerOfflineError(BrokerHealthCheckError):
    """Raised when broker is offline."""
    pass


# ============================================================================
# RATE LIMIT EXCEPTIONS
# ============================================================================

class BrokerRateLimitExceededError(BrokerRateLimitError):
    """Raised when rate limit is exceeded (specific to rate limiting)."""
    pass


class BrokerRateLimitConfigError(BrokerError):
    """Raised when rate limit configuration is invalid."""
    pass


# ============================================================================
# FACTORY EXCEPTIONS
# ============================================================================

class BrokerFactoryError(BrokerError):
    """Raised when broker factory operations fail."""
    pass


class BrokerNotFoundError(BrokerFactoryError):
    """Raised when a broker implementation is not found."""
    pass


class BrokerRegistrationError(BrokerFactoryError):
    """Raised when broker registration fails."""
    pass


class BrokerDiscoveryError(BrokerFactoryError):
    """Raised when broker discovery fails."""
    pass


# ============================================================================
# ROUTING EXCEPTIONS
# ============================================================================

class BrokerRoutingError(BrokerError):
    """Raised when broker routing fails."""
    pass


class BrokerNoAvailableError(BrokerRoutingError):
    """Raised when no broker is available for routing."""
    pass


class BrokerSelectionError(BrokerRoutingError):
    """Raised when broker selection fails."""
    pass


# ============================================================================
# EXCHANGE-SPECIFIC EXCEPTIONS
# ============================================================================

class BrokerExchangeError(BrokerError):
    """Base exception for exchange-specific errors."""
    pass


class BinanceError(BrokerExchangeError):
    """Binance-specific errors."""
    pass


class CoinbaseError(BrokerExchangeError):
    """Coinbase-specific errors."""
    pass


class KrakenError(BrokerExchangeError):
    """Kraken-specific errors."""
    pass


class BybitError(BrokerExchangeError):
    """Bybit-specific errors."""
    pass


class AlpacaError(BrokerExchangeError):
    """Alpaca-specific errors."""
    pass


class OandaError(BrokerExchangeError):
    """OANDA-specific errors."""
    pass


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def map_exchange_error(
    exchange: str,
    status_code: int,
    error_message: str,
    error_code: Optional[str] = None,
) -> BrokerError:
    """
    Map exchange-specific errors to generic broker exceptions.
    
    Args:
        exchange: Exchange name
        status_code: HTTP status code
        error_message: Error message from exchange
        error_code: Exchange-specific error code
        
    Returns:
        BrokerError: Appropriate broker exception
    """
    # Authentication errors
    if status_code in (401, 403):
        if "api key" in error_message.lower() or "invalid" in error_message.lower():
            return BrokerAPIKeyError(
                message=f"{exchange} API key error: {error_message}",
                code=error_code,
                data={"status_code": status_code},
            )
        if "2fa" in error_message.lower() or "two-factor" in error_message.lower():
            return BrokerTwoFactorRequiredError(
                message=f"{exchange} 2FA required: {error_message}",
                code=error_code,
                data={"status_code": status_code},
            )
        return BrokerAuthenticationError(
            message=f"{exchange} authentication error: {error_message}",
            code=error_code,
            data={"status_code": status_code},
        )
    
    # Rate limit errors
    if status_code == 429:
        return BrokerRateLimitExceededError(
            message=f"{exchange} rate limit exceeded: {error_message}",
            code=error_code,
            data={"status_code": status_code},
        )
    
    # Order errors
    if status_code in (400, 422):
        if "insufficient balance" in error_message.lower():
            return BrokerInsufficientBalanceError(
                message=f"{exchange} insufficient balance: {error_message}",
                code=error_code,
                data={"status_code": status_code},
            )
        if "margin" in error_message.lower():
            return BrokerMarginError(
                message=f"{exchange} margin error: {error_message}",
                code=error_code,
                data={"status_code": status_code},
            )
        if "order" in error_message.lower():
            return BrokerOrderRejectedError(
                message=f"{exchange} order rejected: {error_message}",
                code=error_code,
                data={"status_code": status_code},
            )
        return BrokerOrderValidationError(
            message=f"{exchange} order validation error: {error_message}",
            code=error_code,
            data={"status_code": status_code},
        )
    
    # Symbol errors
    if "symbol" in error_message.lower():
        if "not found" in error_message.lower():
            return BrokerSymbolNotFoundError(
                message=f"{exchange} symbol not found: {error_message}",
                code=error_code,
                data={"status_code": status_code},
            )
        return BrokerDataError(
            message=f"{exchange} symbol error: {error_message}",
            code=error_code,
            data={"status_code": status_code},
        )
    
    # Connection errors
    if status_code in (500, 502, 503, 504):
        return BrokerConnectionError(
            message=f"{exchange} server error: {error_message}",
            code=error_code,
            data={"status_code": status_code},
        )
    
    # Timeout errors
    if "timeout" in error_message.lower() or "timed out" in error_message.lower():
        return BrokerTimeoutError(
            message=f"{exchange} timeout: {error_message}",
            code=error_code,
            data={"status_code": status_code},
        )
    
    # Generic error
    return BrokerError(
        message=f"{exchange} error: {error_message}",
        code=error_code,
        data={"status_code": status_code},
    )


def exception_to_dict(exc: Exception) -> Dict[str, Any]:
    """
    Convert any exception to a dictionary for serialization.
    
    Args:
        exc: Exception to convert
        
    Returns:
        Dict: Exception as dictionary
    """
    if isinstance(exc, BrokerError):
        return exc.to_dict()
    
    return {
        "type": exc.__class__.__name__,
        "message": str(exc),
        "code": getattr(exc, "code", None),
        "data": getattr(exc, "data", {}),
    }


def is_retryable_error(exc: Exception) -> bool:
    """
    Determine if an error is retryable.
    
    Args:
        exc: Exception to check
        
    Returns:
        bool: True if the error is retryable
    """
    retryable_types = (
        BrokerTimeoutError,
        BrokerConnectionError,
        BrokerRateLimitExceededError,
        BrokerDisconnectionError,
        BrokerReconnectionError,
        BrokerWebSocketError,
    )
    
    if isinstance(exc, retryable_types):
        return True
    
    # Check for specific error codes that are retryable
    if isinstance(exc, BrokerError):
        if exc.code in ("RATE_LIMIT", "TIMEOUT", "CONNECTION_ERROR", "SERVER_ERROR"):
            return True
    
    return False


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Base
    "BrokerError",
    
    # Connection
    "BrokerConnectionError",
    "BrokerDisconnectionError",
    "BrokerTimeoutError",
    "BrokerConnectionPoolError",
    "BrokerWebSocketError",
    "BrokerReconnectionError",
    
    # Authentication
    "BrokerAuthenticationError",
    "BrokerAuthorizationError",
    "BrokerAPIKeyError",
    "BrokerTokenExpiredError",
    "BrokerTwoFactorRequiredError",
    
    # Orders
    "BrokerOrderError",
    "BrokerOrderNotFoundError",
    "BrokerOrderRejectedError",
    "BrokerOrderCancellationError",
    "BrokerOrderModificationError",
    "BrokerOrderValidationError",
    "BrokerInsufficientBalanceError",
    "BrokerMarginError",
    "BrokerPositionError",
    "BrokerPositionNotFoundError",
    "BrokerPositionCloseError",
    
    # Data
    "BrokerDataError",
    "BrokerSymbolNotFoundError",
    "BrokerMarketDataUnavailableError",
    "BrokerHistoricalDataError",
    "BrokerRateLimitError",
    "BrokerWebSocketDataError",
    
    # Configuration
    "BrokerConfigError",
    "BrokerConfigNotFoundError",
    "BrokerConfigValidationError",
    "BrokerEndpointError",
    
    # Account
    "BrokerAccountError",
    "BrokerAccountNotFoundError",
    "BrokerAccountLockedError",
    "BrokerAccountSuspendedError",
    
    # Health
    "BrokerHealthCheckError",
    "BrokerUnhealthyError",
    "BrokerDegradedError",
    "BrokerOfflineError",
    
    # Rate limit
    "BrokerRateLimitExceededError",
    "BrokerRateLimitConfigError",
    
    # Factory
    "BrokerFactoryError",
    "BrokerNotFoundError",
    "BrokerRegistrationError",
    "BrokerDiscoveryError",
    
    # Routing
    "BrokerRoutingError",
    "BrokerNoAvailableError",
    "BrokerSelectionError",
    
    # Exchange-specific
    "BrokerExchangeError",
    "BinanceError",
    "CoinbaseError",
    "KrakenError",
    "BybitError",
    "AlpacaError",
    "OandaError",
    
    # Helpers
    "map_exchange_error",
    "exception_to_dict",
    "is_retryable_error",
]
