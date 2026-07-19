"""
NEXUS AI TRADING SYSTEM - Bybit Exceptions Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/bybit/exceptions.py
Description: Bybit exchange exception handling with full API integration
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

class BybitErrorCode(int, Enum):
    """Bybit error codes"""
    # General errors
    UNKNOWN = 10000
    DISCONNECTED = 10001
    UNAUTHORIZED = 10003
    TOO_MANY_REQUESTS = 10004
    INVALID_REQUEST = 10005
    SERVER_ERROR = 10006
    
    # Authentication errors
    INVALID_API_KEY = 10010
    INVALID_SIGNATURE = 10011
    API_KEY_EXPIRED = 10012
    PERMISSION_DENIED = 10013
    IP_BLOCKED = 10014
    
    # Order errors
    ORDER_NOT_FOUND = 11001
    ORDER_CANCELLED = 11002
    ORDER_REJECTED = 11003
    INSUFFICIENT_BALANCE = 11004
    INVALID_ORDER_TYPE = 11005
    INVALID_ORDER_PRICE = 11006
    INVALID_ORDER_SIZE = 11007
    INVALID_ORDER_SIDE = 11008
    ORDER_EXPIRED = 11009
    ORDER_FILLED = 11010
    STOP_ORDER_NOT_FOUND = 11011
    
    # Account errors
    ACCOUNT_NOT_FOUND = 12001
    ACCOUNT_LOCKED = 12002
    ACCOUNT_INSUFFICIENT_BALANCE = 12003
    ACCOUNT_INSUFFICIENT_MARGIN = 12004
    ACCOUNT_MAX_POSITION = 12005
    ACCOUNT_MAX_LEVERAGE = 12006
    
    # Position errors
    POSITION_NOT_FOUND = 13001
    POSITION_LIQUIDATED = 13002
    POSITION_CLOSED = 13003
    POSITION_SIZE_EXCEEDED = 13004
    
    # Rate limit errors
    RATE_LIMIT_EXCEEDED = 14001
    RATE_LIMIT_ORDER_EXCEEDED = 14002
    RATE_LIMIT_WEIGHT_EXCEEDED = 14003
    
    # Market errors
    MARKET_NOT_FOUND = 15001
    MARKET_CLOSED = 15002
    MARKET_PAUSED = 15003
    MARKET_NOT_TRADABLE = 15004
    INVALID_SYMBOL = 15005
    INVALID_CATEGORY = 15006


class BybitErrorCategory(str, Enum):
    """Bybit error categories"""
    AUTHENTICATION = "authentication"
    ORDER = "order"
    ACCOUNT = "account"
    POSITION = "position"
    MARKET = "market"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class BybitErrorSeverity(str, Enum):
    """Bybit error severity"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# =============================================================================
# EXCEPTIONS
# =============================================================================

class BybitException(Exception):
    """
    Base Bybit exception.
    
    Attributes:
        code: Error code
        message: Error message
        category: Error category
        severity: Error severity
        data: Additional error data
    """
    
    def __init__(
        self,
        code: BybitErrorCode,
        message: str,
        category: BybitErrorCategory = BybitErrorCategory.UNKNOWN,
        severity: BybitErrorSeverity = BybitErrorSeverity.ERROR,
        data: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.category = category
        self.severity = severity
        self.data = data or {}
        
        # Log error
        if severity == BybitErrorSeverity.CRITICAL:
            logger.critical(f"Bybit Critical Error: {code} - {message}")
        elif severity == BybitErrorSeverity.ERROR:
            logger.error(f"Bybit Error: {code} - {message}")
        elif severity == BybitErrorSeverity.WARNING:
            logger.warning(f"Bybit Warning: {code} - {message}")
        else:
            logger.info(f"Bybit Info: {code} - {message}")
        
        super().__init__(message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} ({self.category})"


class BybitAuthenticationError(BybitException):
    """Bybit authentication error"""
    
    def __init__(
        self,
        code: BybitErrorCode = BybitErrorCode.UNAUTHORIZED,
        message: str = "Authentication failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BybitErrorCategory.AUTHENTICATION,
            severity=BybitErrorSeverity.ERROR,
            data=data
        )


class BybitOrderError(BybitException):
    """Bybit order error"""
    
    def __init__(
        self,
        code: BybitErrorCode = BybitErrorCode.ORDER_REJECTED,
        message: str = "Order operation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BybitErrorCategory.ORDER,
            severity=BybitErrorSeverity.ERROR,
            data=data
        )


class BybitAccountError(BybitException):
    """Bybit account error"""
    
    def __init__(
        self,
        code: BybitErrorCode = BybitErrorCode.ACCOUNT_NOT_FOUND,
        message: str = "Account operation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BybitErrorCategory.ACCOUNT,
            severity=BybitErrorSeverity.ERROR,
            data=data
        )


class BybitPositionError(BybitException):
    """Bybit position error"""
    
    def __init__(
        self,
        code: BybitErrorCode = BybitErrorCode.POSITION_NOT_FOUND,
        message: str = "Position operation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BybitErrorCategory.POSITION,
            severity=BybitErrorSeverity.ERROR,
            data=data
        )


class BybitMarketError(BybitException):
    """Bybit market error"""
    
    def __init__(
        self,
        code: BybitErrorCode = BybitErrorCode.MARKET_NOT_FOUND,
        message: str = "Market operation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BybitErrorCategory.MARKET,
            severity=BybitErrorSeverity.ERROR,
            data=data
        )


class BybitRateLimitError(BybitException):
    """Bybit rate limit error"""
    
    def __init__(
        self,
        code: BybitErrorCode = BybitErrorCode.RATE_LIMIT_EXCEEDED,
        message: str = "Rate limit exceeded",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BybitErrorCategory.RATE_LIMIT,
            severity=BybitErrorSeverity.WARNING,
            data=data
        )


class BybitValidationError(BybitException):
    """Bybit validation error"""
    
    def __init__(
        self,
        code: BybitErrorCode = BybitErrorCode.INVALID_REQUEST,
        message: str = "Validation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BybitErrorCategory.VALIDATION,
            severity=BybitErrorSeverity.ERROR,
            data=data
        )


class BybitNetworkError(BybitException):
    """Bybit network error"""
    
    def __init__(
        self,
        code: BybitErrorCode = BybitErrorCode.DISCONNECTED,
        message: str = "Network error",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=BybitErrorCategory.NETWORK,
            severity=BybitErrorSeverity.CRITICAL,
            data=data
        )


# =============================================================================
# ERROR HANDLING
# =============================================================================

class BybitErrorHandler:
    """
    Bybit error handler.
    
    Features:
    - Error classification
    - Error recovery
    - Retry logic
    - Error logging
    - Error reporting
    """
    
    def __init__(self):
        """Initialize BybitErrorHandler."""
        # Error mapping
        self._error_mapping = {
            BybitErrorCode.UNAUTHORIZED: BybitAuthenticationError,
            BybitErrorCode.INVALID_API_KEY: BybitAuthenticationError,
            BybitErrorCode.INVALID_SIGNATURE: BybitAuthenticationError,
            BybitErrorCode.API_KEY_EXPIRED: BybitAuthenticationError,
            BybitErrorCode.PERMISSION_DENIED: BybitAuthenticationError,
            BybitErrorCode.IP_BLOCKED: BybitAuthenticationError,
            
            BybitErrorCode.ORDER_NOT_FOUND: BybitOrderError,
            BybitErrorCode.ORDER_CANCELLED: BybitOrderError,
            BybitErrorCode.ORDER_REJECTED: BybitOrderError,
            BybitErrorCode.INSUFFICIENT_BALANCE: BybitOrderError,
            BybitErrorCode.INVALID_ORDER_TYPE: BybitOrderError,
            BybitErrorCode.INVALID_ORDER_PRICE: BybitOrderError,
            BybitErrorCode.INVALID_ORDER_SIZE: BybitOrderError,
            BybitErrorCode.INVALID_ORDER_SIDE: BybitOrderError,
            BybitErrorCode.ORDER_EXPIRED: BybitOrderError,
            BybitErrorCode.ORDER_FILLED: BybitOrderError,
            BybitErrorCode.STOP_ORDER_NOT_FOUND: BybitOrderError,
            
            BybitErrorCode.ACCOUNT_NOT_FOUND: BybitAccountError,
            BybitErrorCode.ACCOUNT_LOCKED: BybitAccountError,
            BybitErrorCode.ACCOUNT_INSUFFICIENT_BALANCE: BybitAccountError,
            BybitErrorCode.ACCOUNT_INSUFFICIENT_MARGIN: BybitAccountError,
            BybitErrorCode.ACCOUNT_MAX_POSITION: BybitAccountError,
            BybitErrorCode.ACCOUNT_MAX_LEVERAGE: BybitAccountError,
            
            BybitErrorCode.POSITION_NOT_FOUND: BybitPositionError,
            BybitErrorCode.POSITION_LIQUIDATED: BybitPositionError,
            BybitErrorCode.POSITION_CLOSED: BybitPositionError,
            BybitErrorCode.POSITION_SIZE_EXCEEDED: BybitPositionError,
            
            BybitErrorCode.MARKET_NOT_FOUND: BybitMarketError,
            BybitErrorCode.MARKET_CLOSED: BybitMarketError,
            BybitErrorCode.MARKET_PAUSED: BybitMarketError,
            BybitErrorCode.MARKET_NOT_TRADABLE: BybitMarketError,
            BybitErrorCode.INVALID_SYMBOL: BybitMarketError,
            BybitErrorCode.INVALID_CATEGORY: BybitMarketError,
            
            BybitErrorCode.RATE_LIMIT_EXCEEDED: BybitRateLimitError,
            BybitErrorCode.RATE_LIMIT_ORDER_EXCEEDED: BybitRateLimitError,
            BybitErrorCode.RATE_LIMIT_WEIGHT_EXCEEDED: BybitRateLimitError,
            
            BybitErrorCode.INVALID_REQUEST: BybitValidationError,
            BybitErrorCode.DISCONNECTED: BybitNetworkError
        }
        
        # Retryable error codes
        self._retryable_codes = {
            BybitErrorCode.DISCONNECTED,
            BybitErrorCode.TOO_MANY_REQUESTS,
            BybitErrorCode.RATE_LIMIT_EXCEEDED,
            BybitErrorCode.RATE_LIMIT_ORDER_EXCEEDED,
            BybitErrorCode.RATE_LIMIT_WEIGHT_EXCEEDED,
            BybitErrorCode.SERVER_ERROR
        }
        
        logger.info("BybitErrorHandler initialized")

    def classify_error(
        self,
        code: int,
        message: str
    ) -> BybitException:
        """
        Classify an error.
        
        Args:
            code: Error code
            message: Error message
            
        Returns:
            BybitException: Classified exception
        """
        try:
            error_code = BybitErrorCode(code)
        except ValueError:
            error_code = BybitErrorCode.UNKNOWN
        
        # Get exception class
        exception_class = self._error_mapping.get(
            error_code,
            BybitException
        )
        
        return exception_class(
            code=error_code,
            message=message
        )

    def is_retryable(self, error: BybitException) -> bool:
        """
        Check if error is retryable.
        
        Args:
            error: Bybit exception
            
        Returns:
            bool: Whether error is retryable
        """
        return error.code in self._retryable_codes

    def get_retry_delay(self, error: BybitException) -> float:
        """
        Get retry delay for error.
        
        Args:
            error: Bybit exception
            
        Returns:
            float: Retry delay in seconds
        """
        if error.code == BybitErrorCode.RATE_LIMIT_EXCEEDED:
            return 1.0
        elif error.code == BybitErrorCode.TOO_MANY_REQUESTS:
            return 2.0
        elif error.code == BybitErrorCode.DISCONNECTED:
            return 0.5
        elif error.code == BybitErrorCode.SERVER_ERROR:
            return 1.0
        else:
            return 0.5

    def handle_error(
        self,
        error: BybitException
    ) -> Dict[str, Any]:
        """
        Handle an error.
        
        Args:
            error: Bybit exception
            
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

router = APIRouter(prefix="/api/v1/exchanges/bybit/exceptions", tags=["Bybit Exceptions"])


async def get_error_handler() -> BybitErrorHandler:
    """Dependency to get BybitErrorHandler instance"""
    return BybitErrorHandler()


@router.get("/error-codes")
async def get_error_codes():
    """Get all Bybit error codes"""
    return {
        'codes': [
            {'code': code.value, 'name': code.name, 'description': code.name.replace('_', ' ').title()}
            for code in BybitErrorCode
        ]
    }


@router.get("/error-categories")
async def get_error_categories():
    """Get all Bybit error categories"""
    return {
        'categories': [
            {'name': cat.value, 'description': cat.name.replace('_', ' ').title()}
            for cat in BybitErrorCategory
        ]
    }


@router.get("/error-severities")
async def get_error_severities():
    """Get all Bybit error severities"""
    return {
        'severities': [
            {'name': sev.value, 'description': sev.name.title()}
            for sev in BybitErrorSeverity
        ]
    }


@router.get("/retryable-codes")
async def get_retryable_codes(
    handler: BybitErrorHandler = Depends(get_error_handler)
):
    """Get retryable error codes"""
    return {
        'codes': [code.value for code in handler._retryable_codes]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BybitErrorCode',
    'BybitErrorCategory',
    'BybitErrorSeverity',
    'BybitException',
    'BybitAuthenticationError',
    'BybitOrderError',
    'BybitAccountError',
    'BybitPositionError',
    'BybitMarketError',
    'BybitRateLimitError',
    'BybitValidationError',
    'BybitNetworkError',
    'BybitErrorHandler',
    'router'
]
