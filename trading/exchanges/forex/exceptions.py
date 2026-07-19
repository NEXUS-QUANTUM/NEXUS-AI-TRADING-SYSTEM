"""
NEXUS AI TRADING SYSTEM - Forex Exceptions Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/forex/exceptions.py
Description: Forex exchange exception handling with full API integration
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

class ForexErrorCode(int, Enum):
    """Forex error codes"""
    # General errors
    UNKNOWN = -1
    DISCONNECTED = -2
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    TOO_MANY_REQUESTS = 429
    SERVER_ERROR = 500
    
    # Authentication errors
    INVALID_API_KEY = 10001
    INVALID_SIGNATURE = 10002
    INVALID_ACCOUNT = 10003
    API_KEY_EXPIRED = 10004
    PERMISSION_DENIED = 10005
    
    # Order errors
    ORDER_NOT_FOUND = 20001
    ORDER_CANCELLED = 20002
    ORDER_REJECTED = 20003
    INSUFFICIENT_BALANCE = 20004
    INVALID_ORDER_TYPE = 20005
    INVALID_ORDER_PRICE = 20006
    INVALID_ORDER_SIZE = 20007
    INVALID_ORDER_SIDE = 20008
    ORDER_EXPIRED = 20009
    ORDER_FILLED = 20010
    INVALID_INSTRUMENT = 20011
    INVALID_STOP_LOSS = 20012
    INVALID_TAKE_PROFIT = 20013
    INVALID_TRAILING_STOP = 20014
    
    # Position errors
    POSITION_NOT_FOUND = 30001
    POSITION_CLOSED = 30002
    POSITION_SIZE_EXCEEDED = 30003
    INSUFFICIENT_MARGIN = 30004
    
    # Account errors
    ACCOUNT_NOT_FOUND = 40001
    ACCOUNT_LOCKED = 40002
    ACCOUNT_INSUFFICIENT_BALANCE = 40003
    ACCOUNT_MAX_POSITION = 40004
    
    # Rate limit errors
    RATE_LIMIT_EXCEEDED = 50001
    RATE_LIMIT_ORDER_EXCEEDED = 50002
    RATE_LIMIT_WEIGHT_EXCEEDED = 50003


class ForexErrorCategory(str, Enum):
    """Forex error categories"""
    AUTHENTICATION = "authentication"
    ORDER = "order"
    POSITION = "position"
    ACCOUNT = "account"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    VALIDATION = "validation"
    MARKET = "market"
    UNKNOWN = "unknown"


class ForexErrorSeverity(str, Enum):
    """Forex error severity"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# =============================================================================
# EXCEPTIONS
# =============================================================================

class ForexException(Exception):
    """
    Base Forex exception.
    
    Attributes:
        code: Error code
        message: Error message
        category: Error category
        severity: Error severity
        data: Additional error data
    """
    
    def __init__(
        self,
        code: ForexErrorCode,
        message: str,
        category: ForexErrorCategory = ForexErrorCategory.UNKNOWN,
        severity: ForexErrorSeverity = ForexErrorSeverity.ERROR,
        data: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.category = category
        self.severity = severity
        self.data = data or {}
        
        # Log error
        if severity == ForexErrorSeverity.CRITICAL:
            logger.critical(f"Forex Critical Error: {code} - {message}")
        elif severity == ForexErrorSeverity.ERROR:
            logger.error(f"Forex Error: {code} - {message}")
        elif severity == ForexErrorSeverity.WARNING:
            logger.warning(f"Forex Warning: {code} - {message}")
        else:
            logger.info(f"Forex Info: {code} - {message}")
        
        super().__init__(message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} ({self.category})"


class ForexAuthenticationError(ForexException):
    """Forex authentication error"""
    
    def __init__(
        self,
        code: ForexErrorCode = ForexErrorCode.UNAUTHORIZED,
        message: str = "Authentication failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=ForexErrorCategory.AUTHENTICATION,
            severity=ForexErrorSeverity.ERROR,
            data=data
        )


class ForexOrderError(ForexException):
    """Forex order error"""
    
    def __init__(
        self,
        code: ForexErrorCode = ForexErrorCode.ORDER_REJECTED,
        message: str = "Order operation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=ForexErrorCategory.ORDER,
            severity=ForexErrorSeverity.ERROR,
            data=data
        )


class ForexPositionError(ForexException):
    """Forex position error"""
    
    def __init__(
        self,
        code: ForexErrorCode = ForexErrorCode.POSITION_NOT_FOUND,
        message: str = "Position operation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=ForexErrorCategory.POSITION,
            severity=ForexErrorSeverity.ERROR,
            data=data
        )


class ForexAccountError(ForexException):
    """Forex account error"""
    
    def __init__(
        self,
        code: ForexErrorCode = ForexErrorCode.ACCOUNT_NOT_FOUND,
        message: str = "Account operation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=ForexErrorCategory.ACCOUNT,
            severity=ForexErrorSeverity.ERROR,
            data=data
        )


class ForexRateLimitError(ForexException):
    """Forex rate limit error"""
    
    def __init__(
        self,
        code: ForexErrorCode = ForexErrorCode.RATE_LIMIT_EXCEEDED,
        message: str = "Rate limit exceeded",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=ForexErrorCategory.RATE_LIMIT,
            severity=ForexErrorSeverity.WARNING,
            data=data
        )


class ForexValidationError(ForexException):
    """Forex validation error"""
    
    def __init__(
        self,
        code: ForexErrorCode = ForexErrorCode.INVALID_ORDER_TYPE,
        message: str = "Validation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=ForexErrorCategory.VALIDATION,
            severity=ForexErrorSeverity.ERROR,
            data=data
        )


class ForexMarketError(ForexException):
    """Forex market error"""
    
    def __init__(
        self,
        code: ForexErrorCode = ForexErrorCode.INVALID_INSTRUMENT,
        message: str = "Market operation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=ForexErrorCategory.MARKET,
            severity=ForexErrorSeverity.ERROR,
            data=data
        )


class ForexNetworkError(ForexException):
    """Forex network error"""
    
    def __init__(
        self,
        code: ForexErrorCode = ForexErrorCode.DISCONNECTED,
        message: str = "Network error",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=ForexErrorCategory.NETWORK,
            severity=ForexErrorSeverity.CRITICAL,
            data=data
        )


# =============================================================================
# ERROR HANDLING
# =============================================================================

class ForexErrorHandler:
    """
    Forex error handler.
    
    Features:
    - Error classification
    - Error recovery
    - Retry logic
    - Error logging
    - Error reporting
    """
    
    def __init__(self):
        """Initialize ForexErrorHandler."""
        # Error mapping
        self._error_mapping = {
            ForexErrorCode.UNAUTHORIZED: ForexAuthenticationError,
            ForexErrorCode.INVALID_API_KEY: ForexAuthenticationError,
            ForexErrorCode.INVALID_SIGNATURE: ForexAuthenticationError,
            ForexErrorCode.INVALID_ACCOUNT: ForexAuthenticationError,
            ForexErrorCode.API_KEY_EXPIRED: ForexAuthenticationError,
            ForexErrorCode.PERMISSION_DENIED: ForexAuthenticationError,
            
            ForexErrorCode.ORDER_NOT_FOUND: ForexOrderError,
            ForexErrorCode.ORDER_CANCELLED: ForexOrderError,
            ForexErrorCode.ORDER_REJECTED: ForexOrderError,
            ForexErrorCode.INSUFFICIENT_BALANCE: ForexOrderError,
            ForexErrorCode.INVALID_ORDER_TYPE: ForexOrderError,
            ForexErrorCode.INVALID_ORDER_PRICE: ForexOrderError,
            ForexErrorCode.INVALID_ORDER_SIZE: ForexOrderError,
            ForexErrorCode.INVALID_ORDER_SIDE: ForexOrderError,
            ForexErrorCode.ORDER_EXPIRED: ForexOrderError,
            ForexErrorCode.ORDER_FILLED: ForexOrderError,
            ForexErrorCode.INVALID_INSTRUMENT: ForexOrderError,
            ForexErrorCode.INVALID_STOP_LOSS: ForexOrderError,
            ForexErrorCode.INVALID_TAKE_PROFIT: ForexOrderError,
            ForexErrorCode.INVALID_TRAILING_STOP: ForexOrderError,
            
            ForexErrorCode.POSITION_NOT_FOUND: ForexPositionError,
            ForexErrorCode.POSITION_CLOSED: ForexPositionError,
            ForexErrorCode.POSITION_SIZE_EXCEEDED: ForexPositionError,
            ForexErrorCode.INSUFFICIENT_MARGIN: ForexPositionError,
            
            ForexErrorCode.ACCOUNT_NOT_FOUND: ForexAccountError,
            ForexErrorCode.ACCOUNT_LOCKED: ForexAccountError,
            ForexErrorCode.ACCOUNT_INSUFFICIENT_BALANCE: ForexAccountError,
            ForexErrorCode.ACCOUNT_MAX_POSITION: ForexAccountError,
            
            ForexErrorCode.RATE_LIMIT_EXCEEDED: ForexRateLimitError,
            ForexErrorCode.RATE_LIMIT_ORDER_EXCEEDED: ForexRateLimitError,
            ForexErrorCode.RATE_LIMIT_WEIGHT_EXCEEDED: ForexRateLimitError,
            
            ForexErrorCode.INVALID_ORDER_TYPE: ForexValidationError,
            ForexErrorCode.INVALID_INSTRUMENT: ForexMarketError,
            ForexErrorCode.DISCONNECTED: ForexNetworkError
        }
        
        # Retryable error codes
        self._retryable_codes = {
            ForexErrorCode.DISCONNECTED,
            ForexErrorCode.TOO_MANY_REQUESTS,
            ForexErrorCode.RATE_LIMIT_EXCEEDED,
            ForexErrorCode.RATE_LIMIT_ORDER_EXCEEDED,
            ForexErrorCode.RATE_LIMIT_WEIGHT_EXCEEDED,
            ForexErrorCode.SERVER_ERROR
        }
        
        logger.info("ForexErrorHandler initialized")

    def classify_error(
        self,
        code: int,
        message: str
    ) -> ForexException:
        """
        Classify an error.
        
        Args:
            code: Error code
            message: Error message
            
        Returns:
            ForexException: Classified exception
        """
        try:
            error_code = ForexErrorCode(code)
        except ValueError:
            error_code = ForexErrorCode.UNKNOWN
        
        # Get exception class
        exception_class = self._error_mapping.get(
            error_code,
            ForexException
        )
        
        return exception_class(
            code=error_code,
            message=message
        )

    def is_retryable(self, error: ForexException) -> bool:
        """
        Check if error is retryable.
        
        Args:
            error: Forex exception
            
        Returns:
            bool: Whether error is retryable
        """
        return error.code in self._retryable_codes

    def get_retry_delay(self, error: ForexException) -> float:
        """
        Get retry delay for error.
        
        Args:
            error: Forex exception
            
        Returns:
            float: Retry delay in seconds
        """
        if error.code == ForexErrorCode.RATE_LIMIT_EXCEEDED:
            return 1.0
        elif error.code == ForexErrorCode.TOO_MANY_REQUESTS:
            return 2.0
        elif error.code == ForexErrorCode.DISCONNECTED:
            return 0.5
        elif error.code == ForexErrorCode.SERVER_ERROR:
            return 1.0
        else:
            return 0.5

    def handle_error(
        self,
        error: ForexException
    ) -> Dict[str, Any]:
        """
        Handle an error.
        
        Args:
            error: Forex exception
            
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

router = APIRouter(prefix="/api/v1/exchanges/forex/exceptions", tags=["Forex Exceptions"])


async def get_error_handler() -> ForexErrorHandler:
    """Dependency to get ForexErrorHandler instance"""
    return ForexErrorHandler()


@router.get("/error-codes")
async def get_error_codes():
    """Get all Forex error codes"""
    return {
        'codes': [
            {'code': code.value, 'name': code.name, 'description': code.name.replace('_', ' ').title()}
            for code in ForexErrorCode
        ]
    }


@router.get("/error-categories")
async def get_error_categories():
    """Get all Forex error categories"""
    return {
        'categories': [
            {'name': cat.value, 'description': cat.name.replace('_', ' ').title()}
            for cat in ForexErrorCategory
        ]
    }


@router.get("/error-severities")
async def get_error_severities():
    """Get all Forex error severities"""
    return {
        'severities': [
            {'name': sev.value, 'description': sev.name.title()}
            for sev in ForexErrorSeverity
        ]
    }


@router.get("/retryable-codes")
async def get_retryable_codes(
    handler: ForexErrorHandler = Depends(get_error_handler)
):
    """Get retryable error codes"""
    return {
        'codes': [code.value for code in handler._retryable_codes]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'ForexErrorCode',
    'ForexErrorCategory',
    'ForexErrorSeverity',
    'ForexException',
    'ForexAuthenticationError',
    'ForexOrderError',
    'ForexPositionError',
    'ForexAccountError',
    'ForexRateLimitError',
    'ForexValidationError',
    'ForexMarketError',
    'ForexNetworkError',
    'ForexErrorHandler',
    'router'
]
