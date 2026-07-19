"""
NEXUS AI TRADING SYSTEM - Coinbase Exceptions Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/coinbase/exceptions.py
Description: Coinbase exchange exception handling with full API integration
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

class CoinbaseErrorCode(int, Enum):
    """Coinbase error codes"""
    # General errors
    UNKNOWN = -1
    DISCONNECTED = -2
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    TOO_MANY_REQUESTS = 429
    
    # Authentication errors
    INVALID_API_KEY = 10001
    INVALID_SIGNATURE = 10002
    INVALID_PASSPHRASE = 10003
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
    INVALID_PRODUCT = 20011
    
    # Account errors
    ACCOUNT_NOT_FOUND = 30001
    ACCOUNT_LOCKED = 30002
    ACCOUNT_INSUFFICIENT_BALANCE = 30003
    ACCOUNT_MAX_POSITION = 30004
    
    # Product errors
    PRODUCT_NOT_FOUND = 40001
    PRODUCT_OFFLINE = 40002
    PRODUCT_HALTED = 40003
    INVALID_PRODUCT_ID = 40004
    
    # Rate limit errors
    RATE_LIMIT_EXCEEDED = 50001
    RATE_LIMIT_ORDER_EXCEEDED = 50002
    RATE_LIMIT_WEIGHT_EXCEEDED = 50003


class CoinbaseErrorCategory(str, Enum):
    """Coinbase error categories"""
    AUTHENTICATION = "authentication"
    ORDER = "order"
    ACCOUNT = "account"
    PRODUCT = "product"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class CoinbaseErrorSeverity(str, Enum):
    """Coinbase error severity"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# =============================================================================
# EXCEPTIONS
# =============================================================================

class CoinbaseException(Exception):
    """
    Base Coinbase exception.
    
    Attributes:
        code: Error code
        message: Error message
        category: Error category
        severity: Error severity
        data: Additional error data
    """
    
    def __init__(
        self,
        code: CoinbaseErrorCode,
        message: str,
        category: CoinbaseErrorCategory = CoinbaseErrorCategory.UNKNOWN,
        severity: CoinbaseErrorSeverity = CoinbaseErrorSeverity.ERROR,
        data: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.category = category
        self.severity = severity
        self.data = data or {}
        
        # Log error
        if severity == CoinbaseErrorSeverity.CRITICAL:
            logger.critical(f"Coinbase Critical Error: {code} - {message}")
        elif severity == CoinbaseErrorSeverity.ERROR:
            logger.error(f"Coinbase Error: {code} - {message}")
        elif severity == CoinbaseErrorSeverity.WARNING:
            logger.warning(f"Coinbase Warning: {code} - {message}")
        else:
            logger.info(f"Coinbase Info: {code} - {message}")
        
        super().__init__(message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} ({self.category})"


class CoinbaseAuthenticationError(CoinbaseException):
    """Coinbase authentication error"""
    
    def __init__(
        self,
        code: CoinbaseErrorCode = CoinbaseErrorCode.UNAUTHORIZED,
        message: str = "Authentication failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=CoinbaseErrorCategory.AUTHENTICATION,
            severity=CoinbaseErrorSeverity.ERROR,
            data=data
        )


class CoinbaseOrderError(CoinbaseException):
    """Coinbase order error"""
    
    def __init__(
        self,
        code: CoinbaseErrorCode = CoinbaseErrorCode.ORDER_REJECTED,
        message: str = "Order operation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=CoinbaseErrorCategory.ORDER,
            severity=CoinbaseErrorSeverity.ERROR,
            data=data
        )


class CoinbaseAccountError(CoinbaseException):
    """Coinbase account error"""
    
    def __init__(
        self,
        code: CoinbaseErrorCode = CoinbaseErrorCode.ACCOUNT_NOT_FOUND,
        message: str = "Account operation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=CoinbaseErrorCategory.ACCOUNT,
            severity=CoinbaseErrorSeverity.ERROR,
            data=data
        )


class CoinbaseProductError(CoinbaseException):
    """Coinbase product error"""
    
    def __init__(
        self,
        code: CoinbaseErrorCode = CoinbaseErrorCode.PRODUCT_NOT_FOUND,
        message: str = "Product operation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=CoinbaseErrorCategory.PRODUCT,
            severity=CoinbaseErrorSeverity.ERROR,
            data=data
        )


class CoinbaseRateLimitError(CoinbaseException):
    """Coinbase rate limit error"""
    
    def __init__(
        self,
        code: CoinbaseErrorCode = CoinbaseErrorCode.RATE_LIMIT_EXCEEDED,
        message: str = "Rate limit exceeded",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=CoinbaseErrorCategory.RATE_LIMIT,
            severity=CoinbaseErrorSeverity.WARNING,
            data=data
        )


class CoinbaseValidationError(CoinbaseException):
    """Coinbase validation error"""
    
    def __init__(
        self,
        code: CoinbaseErrorCode = CoinbaseErrorCode.INVALID_ORDER_TYPE,
        message: str = "Validation failed",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=CoinbaseErrorCategory.VALIDATION,
            severity=CoinbaseErrorSeverity.ERROR,
            data=data
        )


class CoinbaseNetworkError(CoinbaseException):
    """Coinbase network error"""
    
    def __init__(
        self,
        code: CoinbaseErrorCode = CoinbaseErrorCode.DISCONNECTED,
        message: str = "Network error",
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=code,
            message=message,
            category=CoinbaseErrorCategory.NETWORK,
            severity=CoinbaseErrorSeverity.CRITICAL,
            data=data
        )


# =============================================================================
# ERROR HANDLING
# =============================================================================

class CoinbaseErrorHandler:
    """
    Coinbase error handler.
    
    Features:
    - Error classification
    - Error recovery
    - Retry logic
    - Error logging
    - Error reporting
    """
    
    def __init__(self):
        """Initialize CoinbaseErrorHandler."""
        # Error mapping
        self._error_mapping = {
            CoinbaseErrorCode.UNAUTHORIZED: CoinbaseAuthenticationError,
            CoinbaseErrorCode.INVALID_API_KEY: CoinbaseAuthenticationError,
            CoinbaseErrorCode.INVALID_SIGNATURE: CoinbaseAuthenticationError,
            CoinbaseErrorCode.INVALID_PASSPHRASE: CoinbaseAuthenticationError,
            CoinbaseErrorCode.API_KEY_EXPIRED: CoinbaseAuthenticationError,
            CoinbaseErrorCode.PERMISSION_DENIED: CoinbaseAuthenticationError,
            
            CoinbaseErrorCode.ORDER_NOT_FOUND: CoinbaseOrderError,
            CoinbaseErrorCode.ORDER_CANCELLED: CoinbaseOrderError,
            CoinbaseErrorCode.ORDER_REJECTED: CoinbaseOrderError,
            CoinbaseErrorCode.INSUFFICIENT_BALANCE: CoinbaseOrderError,
            CoinbaseErrorCode.INVALID_ORDER_TYPE: CoinbaseOrderError,
            CoinbaseErrorCode.INVALID_ORDER_PRICE: CoinbaseOrderError,
            CoinbaseErrorCode.INVALID_ORDER_SIZE: CoinbaseOrderError,
            CoinbaseErrorCode.INVALID_ORDER_SIDE: CoinbaseOrderError,
            CoinbaseErrorCode.ORDER_EXPIRED: CoinbaseOrderError,
            CoinbaseErrorCode.ORDER_FILLED: CoinbaseOrderError,
            CoinbaseErrorCode.INVALID_PRODUCT: CoinbaseOrderError,
            
            CoinbaseErrorCode.ACCOUNT_NOT_FOUND: CoinbaseAccountError,
            CoinbaseErrorCode.ACCOUNT_LOCKED: CoinbaseAccountError,
            CoinbaseErrorCode.ACCOUNT_INSUFFICIENT_BALANCE: CoinbaseAccountError,
            CoinbaseErrorCode.ACCOUNT_MAX_POSITION: CoinbaseAccountError,
            
            CoinbaseErrorCode.PRODUCT_NOT_FOUND: CoinbaseProductError,
            CoinbaseErrorCode.PRODUCT_OFFLINE: CoinbaseProductError,
            CoinbaseErrorCode.PRODUCT_HALTED: CoinbaseProductError,
            CoinbaseErrorCode.INVALID_PRODUCT_ID: CoinbaseProductError,
            
            CoinbaseErrorCode.RATE_LIMIT_EXCEEDED: CoinbaseRateLimitError,
            CoinbaseErrorCode.RATE_LIMIT_ORDER_EXCEEDED: CoinbaseRateLimitError,
            CoinbaseErrorCode.RATE_LIMIT_WEIGHT_EXCEEDED: CoinbaseRateLimitError,
            
            CoinbaseErrorCode.INVALID_ORDER_TYPE: CoinbaseValidationError,
            CoinbaseErrorCode.DISCONNECTED: CoinbaseNetworkError
        }
        
        # Retryable error codes
        self._retryable_codes = {
            CoinbaseErrorCode.DISCONNECTED,
            CoinbaseErrorCode.TOO_MANY_REQUESTS,
            CoinbaseErrorCode.RATE_LIMIT_EXCEEDED,
            CoinbaseErrorCode.RATE_LIMIT_ORDER_EXCEEDED,
            CoinbaseErrorCode.RATE_LIMIT_WEIGHT_EXCEEDED
        }
        
        logger.info("CoinbaseErrorHandler initialized")

    def classify_error(
        self,
        code: int,
        message: str
    ) -> CoinbaseException:
        """
        Classify an error.
        
        Args:
            code: Error code
            message: Error message
            
        Returns:
            CoinbaseException: Classified exception
        """
        try:
            error_code = CoinbaseErrorCode(code)
        except ValueError:
            error_code = CoinbaseErrorCode.UNKNOWN
        
        # Get exception class
        exception_class = self._error_mapping.get(
            error_code,
            CoinbaseException
        )
        
        return exception_class(
            code=error_code,
            message=message
        )

    def is_retryable(self, error: CoinbaseException) -> bool:
        """
        Check if error is retryable.
        
        Args:
            error: Coinbase exception
            
        Returns:
            bool: Whether error is retryable
        """
        return error.code in self._retryable_codes

    def get_retry_delay(self, error: CoinbaseException) -> float:
        """
        Get retry delay for error.
        
        Args:
            error: Coinbase exception
            
        Returns:
            float: Retry delay in seconds
        """
        if error.code == CoinbaseErrorCode.RATE_LIMIT_EXCEEDED:
            return 1.0
        elif error.code == CoinbaseErrorCode.TOO_MANY_REQUESTS:
            return 2.0
        elif error.code == CoinbaseErrorCode.DISCONNECTED:
            return 0.5
        else:
            return 0.5

    def handle_error(
        self,
        error: CoinbaseException
    ) -> Dict[str, Any]:
        """
        Handle an error.
        
        Args:
            error: Coinbase exception
            
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

router = APIRouter(prefix="/api/v1/exchanges/coinbase/exceptions", tags=["Coinbase Exceptions"])


async def get_error_handler() -> CoinbaseErrorHandler:
    """Dependency to get CoinbaseErrorHandler instance"""
    return CoinbaseErrorHandler()


@router.get("/error-codes")
async def get_error_codes():
    """Get all Coinbase error codes"""
    return {
        'codes': [
            {'code': code.value, 'name': code.name, 'description': code.name.replace('_', ' ').title()}
            for code in CoinbaseErrorCode
        ]
    }


@router.get("/error-categories")
async def get_error_categories():
    """Get all Coinbase error categories"""
    return {
        'categories': [
            {'name': cat.value, 'description': cat.name.replace('_', ' ').title()}
            for cat in CoinbaseErrorCategory
        ]
    }


@router.get("/error-severities")
async def get_error_severities():
    """Get all Coinbase error severities"""
    return {
        'severities': [
            {'name': sev.value, 'description': sev.name.title()}
            for sev in CoinbaseErrorSeverity
        ]
    }


@router.get("/retryable-codes")
async def get_retryable_codes(
    handler: CoinbaseErrorHandler = Depends(get_error_handler)
):
    """Get retryable error codes"""
    return {
        'codes': [code.value for code in handler._retryable_codes]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'CoinbaseErrorCode',
    'CoinbaseErrorCategory',
    'CoinbaseErrorSeverity',
    'CoinbaseException',
    'CoinbaseAuthenticationError',
    'CoinbaseOrderError',
    'CoinbaseAccountError',
    'CoinbaseProductError',
    'CoinbaseRateLimitError',
    'CoinbaseValidationError',
    'CoinbaseNetworkError',
    'CoinbaseErrorHandler',
    'router'
]
