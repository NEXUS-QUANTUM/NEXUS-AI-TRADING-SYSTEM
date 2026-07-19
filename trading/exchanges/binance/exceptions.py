"""
NEXUS AI TRADING SYSTEM - Binance Exceptions Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/binance/exceptions.py
Description: Binance exchange exception handling with full API integration
"""

import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from enum import Enum

# NEXUS Internal Imports
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class BinanceErrorCode(int, Enum):
    """Binance error codes"""
    # General errors
    UNKNOWN = -1000
    DISCONNECTED = -1001
    UNAUTHORIZED = -1002
    TOO_MANY_REQUESTS = -1003
    DUPLICATE = -1004
    NO_SUCH_ORDER = -1013
    INVALID_SYMBOL = -1121
    
    # Order errors
    ORDER_NOT_FOUND = -2010
    ORDER_CANCELLED = -2011
    ORDER_REJECTED = -2013
    INSUFFICIENT_BALANCE = -2014
    INVALID_ORDER_TYPE = -2015
    INVALID_ORDER_PRICE = -2016
    INVALID_ORDER_SIZE = -2017
    INVALID_ORDER_SIDE = -2018
    INVALID_ORDER_STATUS = -2019
    ORDER_EXPIRED = -2020
    ORDER_FILLED = -2021
    
    # Account errors
    ACCOUNT_NOT_FOUND = -3000
    ACCOUNT_LOCKED = -3001
    ACCOUNT_INSUFFICIENT_BALANCE = -3002
    ACCOUNT_INSUFFICIENT_MARGIN = -3003
    ACCOUNT_MAX_POSITION = -3004
    ACCOUNT_MAX_LEVERAGE = -3005
    
    # Market errors
    MARKET_NOT_FOUND = -4000
    MARKET_CLOSED = -4001
    MARKET_PAUSED = -4002
    MARKET_NOT_TRADABLE = -4003
    
    # Rate limit errors
    RATE_LIMIT_EXCEEDED = -5000
    RATE_LIMIT_ORDER_EXCEEDED = -5001
    RATE_LIMIT_WEIGHT_EXCEEDED = -5002


class BinanceErrorCategory(str, Enum):
    """Binance error categories"""
    AUTHENTICATION = "authentication"
    ORDER = "order"
    ACCOUNT = "account"
    MARKET = "market"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class BinanceErrorSeverity(str, Enum):
    """Binance error severity"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# =============================================================================
# EXCEPTIONS
# =============================================================================

class BinanceException(Exception):
    """
    Base Binance exception.
    
    Attributes:
        code: Error code
        message: Error message
        category: Error category
        severity: Error severity
        data: Additional error data
    """
    
    def __init__(
        self,
        code: BinanceErrorCode,
        message: str,
        category: BinanceErrorCategory = BinanceErrorCategory.UNKNOWN,
        severity: BinanceErrorSeverity = BinanceErrorSeverity.ERROR,
        data: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.category = category
        self.severity = severity
        self.data = data or {}
        
        # Log error
        if severity == BinanceErrorSeverity.CRITICAL:
            logger.critical(f"Binance Critical Error: {code} - {message}")
        elif severity == BinanceErrorSeverity.ERROR:
            logger.error(f"Binance Error: {code} - {message}")
        elif severity == BinanceErrorSeverity.WARNING:
            logger.warning(f"Binance Warning: {code} - {message}")
        else:
            logger.info(f"Binance Info: {code} - {message}")
        
        super().__init__(message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} ({self.category})"


class BinanceAuthenticationError(BinanceException):
    """Binance authentication error"""
    
    def __init__(
        self,
        code: BinanceErrorCode = BinanceErrorCode.UNAUTHORIZED,
        message: str = "Authentication failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BinanceErrorCategory.AUTHENTICATION,
            severity=BinanceErrorSeverity.ERROR,
            data=data
        )


class BinanceOrderError(BinanceException):
    """Binance order error"""
    
    def __init__(
        self,
        code: BinanceErrorCode = BinanceErrorCode.ORDER_REJECTED,
        message: str = "Order operation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BinanceErrorCategory.ORDER,
            severity=BinanceErrorSeverity.ERROR,
            data=data
        )


class BinanceAccountError(BinanceException):
    """Binance account error"""
    
    def __init__(
        self,
        code: BinanceErrorCode = BinanceErrorCode.ACCOUNT_NOT_FOUND,
        message: str = "Account operation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BinanceErrorCategory.ACCOUNT,
            severity=BinanceErrorSeverity.ERROR,
            data=data
        )


class BinanceMarketError(BinanceException):
    """Binance market error"""
    
    def __init__(
        self,
        code: BinanceErrorCode = BinanceErrorCode.MARKET_NOT_FOUND,
        message: str = "Market operation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BinanceErrorCategory.MARKET,
            severity=BinanceErrorSeverity.ERROR,
            data=data
        )


class BinanceRateLimitError(BinanceException):
    """Binance rate limit error"""
    
    def __init__(
        self,
        code: BinanceErrorCode = BinanceErrorCode.RATE_LIMIT_EXCEEDED,
        message: str = "Rate limit exceeded",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BinanceErrorCategory.RATE_LIMIT,
            severity=BinanceErrorSeverity.WARNING,
            data=data
        )


class BinanceValidationError(BinanceException):
    """Binance validation error"""
    
    def __init__(
        self,
        code: BinanceErrorCode = BinanceErrorCode.INVALID_SYMBOL,
        message: str = "Validation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BinanceErrorCategory.VALIDATION,
            severity=BinanceErrorSeverity.ERROR,
            data=data
        )


class BinanceNetworkError(BinanceException):
    """Binance network error"""
    
    def __init__(
        self,
        code: BinanceErrorCode = BinanceErrorCode.DISCONNECTED,
        message: str = "Network error",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BinanceErrorCategory.NETWORK,
            severity=BinanceErrorSeverity.CRITICAL,
            data=data
        )


# =============================================================================
# ERROR HANDLING
# =============================================================================

class BinanceErrorHandler:
    """
    Binance error handler.
    
    Features:
    - Error classification
    - Error recovery
    - Retry logic
    - Error logging
    - Error reporting
    """
    
    def __init__(self):
        """Initialize BinanceErrorHandler."""
        # Error mapping
        self._error_mapping = {
            BinanceErrorCode.UNAUTHORIZED: BinanceAuthenticationError,
            BinanceErrorCode.ORDER_NOT_FOUND: BinanceOrderError,
            BinanceErrorCode.ORDER_CANCELLED: BinanceOrderError,
            BinanceErrorCode.ORDER_REJECTED: BinanceOrderError,
            BinanceErrorCode.INSUFFICIENT_BALANCE: BinanceOrderError,
            BinanceErrorCode.INVALID_ORDER_TYPE: BinanceOrderError,
            BinanceErrorCode.INVALID_ORDER_PRICE: BinanceOrderError,
            BinanceErrorCode.INVALID_ORDER_SIZE: BinanceOrderError,
            BinanceErrorCode.INVALID_ORDER_SIDE: BinanceOrderError,
            BinanceErrorCode.INVALID_ORDER_STATUS: BinanceOrderError,
            BinanceErrorCode.ORDER_EXPIRED: BinanceOrderError,
            BinanceErrorCode.ORDER_FILLED: BinanceOrderError,
            BinanceErrorCode.ACCOUNT_NOT_FOUND: BinanceAccountError,
            BinanceErrorCode.ACCOUNT_LOCKED: BinanceAccountError,
            BinanceErrorCode.ACCOUNT_INSUFFICIENT_BALANCE: BinanceAccountError,
            BinanceErrorCode.ACCOUNT_INSUFFICIENT_MARGIN: BinanceAccountError,
            BinanceErrorCode.ACCOUNT_MAX_POSITION: BinanceAccountError,
            BinanceErrorCode.ACCOUNT_MAX_LEVERAGE: BinanceAccountError,
            BinanceErrorCode.MARKET_NOT_FOUND: BinanceMarketError,
            BinanceErrorCode.MARKET_CLOSED: BinanceMarketError,
            BinanceErrorCode.MARKET_PAUSED: BinanceMarketError,
            BinanceErrorCode.MARKET_NOT_TRADABLE: BinanceMarketError,
            BinanceErrorCode.RATE_LIMIT_EXCEEDED: BinanceRateLimitError,
            BinanceErrorCode.RATE_LIMIT_ORDER_EXCEEDED: BinanceRateLimitError,
            BinanceErrorCode.RATE_LIMIT_WEIGHT_EXCEEDED: BinanceRateLimitError,
            BinanceErrorCode.INVALID_SYMBOL: BinanceValidationError,
            BinanceErrorCode.DISCONNECTED: BinanceNetworkError
        }
        
        # Retryable error codes
        self._retryable_codes = {
            BinanceErrorCode.DISCONNECTED,
            BinanceErrorCode.TOO_MANY_REQUESTS,
            BinanceErrorCode.RATE_LIMIT_EXCEEDED,
            BinanceErrorCode.RATE_LIMIT_ORDER_EXCEEDED,
            BinanceErrorCode.RATE_LIMIT_WEIGHT_EXCEEDED
        }
        
        logger.info("BinanceErrorHandler initialized")

    def classify_error(
        self,
        code: int,
        message: str
    ) -> BinanceException:
        """
        Classify an error.
        
        Args:
            code: Error code
            message: Error message
            
        Returns:
            BinanceException: Classified exception
        """
        try:
            error_code = BinanceErrorCode(code)
        except ValueError:
            error_code = BinanceErrorCode.UNKNOWN
        
        # Get exception class
        exception_class = self._error_mapping.get(
            error_code,
            BinanceException
        )
        
        return exception_class(
            code=error_code,
            message=message
        )

    def is_retryable(self, error: BinanceException) -> bool:
        """
        Check if error is retryable.
        
        Args:
            error: Binance exception
            
        Returns:
            bool: Whether error is retryable
        """
        return error.code in self._retryable_codes

    def get_retry_delay(self, error: BinanceException) -> float:
        """
        Get retry delay for error.
        
        Args:
            error: Binance exception
            
        Returns:
            float: Retry delay in seconds
        """
        if error.code == BinanceErrorCode.RATE_LIMIT_EXCEEDED:
            return 5.0
        elif error.code == BinanceErrorCode.TOO_MANY_REQUESTS:
            return 10.0
        elif error.code == BinanceErrorCode.DISCONNECTED:
            return 2.0
        else:
            return 1.0

    def handle_error(
        self,
        error: BinanceException
    ) -> Dict[str, Any]:
        """
        Handle an error.
        
        Args:
            error: Binance exception
            
        Returns:
            Dict[str, Any]: Error response
        """
        return {
            'code': error.code.value if hasattr(error.code, 'value') else error.code,
            'message': error.message,
            'category': error.category.value,
            'severity': error.severity.value,
            'data': error.data,
            'retryable': self.is_retryable(error),
            'retry_delay': self.get_retry_delay(error) if self.is_retryable(error) else None
        }


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/v1/exchanges/binance/exceptions", tags=["Binance Exceptions"])


async def get_error_handler() -> BinanceErrorHandler:
    """Dependency to get BinanceErrorHandler instance"""
    return BinanceErrorHandler()


@router.get("/error-codes")
async def get_error_codes():
    """Get all Binance error codes"""
    return {
        'codes': [
            {'code': code.value, 'name': code.name, 'description': code.name.replace('_', ' ').title()}
            for code in BinanceErrorCode
        ]
    }


@router.get("/error-categories")
async def get_error_categories():
    """Get all Binance error categories"""
    return {
        'categories': [
            {'name': cat.value, 'description': cat.name.replace('_', ' ').title()}
            for cat in BinanceErrorCategory
        ]
    }


@router.get("/error-severities")
async def get_error_severities():
    """Get all Binance error severities"""
    return {
        'severities': [
            {'name': sev.value, 'description': sev.name.title()}
            for sev in BinanceErrorSeverity
        ]
    }


@router.get("/retryable-codes")
async def get_retryable_codes(
    handler: BinanceErrorHandler = Depends(get_error_handler)
):
    """Get retryable error codes"""
    return {
        'codes': [code.value for code in handler._retryable_codes]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BinanceErrorCode',
    'BinanceErrorCategory',
    'BinanceErrorSeverity',
    'BinanceException',
    'BinanceAuthenticationError',
    'BinanceOrderError',
    'BinanceAccountError',
    'BinanceMarketError',
    'BinanceRateLimitError',
    'BinanceValidationError',
    'BinanceNetworkError',
    'BinanceErrorHandler',
    'router'
]
