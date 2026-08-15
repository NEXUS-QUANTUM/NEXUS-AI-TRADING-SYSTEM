"""
Swing Bot Backoff Utilities Module
===================================

This module provides backoff utilities for the Swing Bot trading system.
Includes exponential backoff, retry strategies, and backoff decorators.
"""

import time
import asyncio
import random
import functools
import logging
from typing import Callable, Optional, Union, Tuple, Any, TypeVar, List, Dict
from enum import Enum
from dataclasses import dataclass, field


T = TypeVar('T')


class BackoffType(Enum):
    """Backoff strategy types."""
    NONE = "none"
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"
    FULL_JITTER = "full_jitter"
    DECORRELATED_JITTER = "decorrelated_jitter"
    RANDOM = "random"
    CONSTANT = "constant"
    POLYNOMIAL = "polynomial"


@dataclass
class BackoffConfig:
    """Configuration for backoff strategies."""
    strategy: BackoffType = BackoffType.EXPONENTIAL
    base_delay: float = 1.0
    max_delay: float = 60.0
    multiplier: float = 2.0
    jitter_factor: float = 0.1
    exponent: float = 2.0
    coefficient: float = 1.0
    random_min: float = 0.1
    random_max: float = 10.0


class BackoffCalculator:
    """
    Calculate backoff delays based on different strategies.
    """
    
    def __init__(self, config: Optional[BackoffConfig] = None):
        self.config = config or BackoffConfig()
    
    def calculate(self, attempt: int) -> float:
        """
        Calculate the backoff delay for a given attempt.
        
        Args:
            attempt: Current attempt number (0-based)
        
        Returns:
            Delay in seconds
        """
        if attempt < 0:
            attempt = 0
        
        delay = self._calculate_raw(attempt)
        
        # Apply max delay limit
        return min(delay, self.config.max_delay)
    
    def _calculate_raw(self, attempt: int) -> float:
        """Calculate raw delay without max limit."""
        strategy = self.config.strategy
        
        if strategy == BackoffType.NONE:
            return 0.0
        
        elif strategy == BackoffType.FIXED:
            return self.config.base_delay
        
        elif strategy == BackoffType.LINEAR:
            return self.config.base_delay * (attempt + 1)
        
        elif strategy == BackoffType.EXPONENTIAL:
            return self.config.base_delay * (self.config.multiplier ** attempt)
        
        elif strategy == BackoffType.EXPONENTIAL_JITTER:
            base = self.config.base_delay * (self.config.multiplier ** attempt)
            jitter = base * self.config.jitter_factor
            return base + random.uniform(-jitter, jitter)
        
        elif strategy == BackoffType.FULL_JITTER:
            base = self.config.base_delay * (self.config.multiplier ** attempt)
            return random.uniform(0, base)
        
        elif strategy == BackoffType.DECORRELATED_JITTER:
            base = self.config.base_delay * (self.config.multiplier ** attempt)
            return base * random.uniform(self.config.jitter_factor, 1.0)
        
        elif strategy == BackoffType.RANDOM:
            return random.uniform(self.config.random_min, self.config.random_max)
        
        elif strategy == BackoffType.CONSTANT:
            return self.config.base_delay
        
        elif strategy == BackoffType.POLYNOMIAL:
            return self.config.coefficient * (attempt ** self.config.exponent)
        
        return self.config.base_delay


class RetryState:
    """State for tracking retry attempts."""
    
    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts
        self.attempts = 0
        self.errors: List[Exception] = []
        self.last_error: Optional[Exception] = None
        self.start_time: Optional[float] = None
        self.total_time: Optional[float] = None
    
    def reset(self) -> None:
        """Reset the retry state."""
        self.attempts = 0
        self.errors.clear()
        self.last_error = None
        self.start_time = None
        self.total_time = None
    
    def increment(self) -> int:
        """Increment attempt count."""
        self.attempts += 1
        return self.attempts
    
    def add_error(self, error: Exception) -> None:
        """Add an error to the state."""
        self.errors.append(error)
        self.last_error = error
    
    def is_exhausted(self) -> bool:
        """Check if retry attempts are exhausted."""
        return self.attempts >= self.max_attempts
    
    def get_remaining(self) -> int:
        """Get remaining attempts."""
        return max(0, self.max_attempts - self.attempts)
    
    def start_timer(self) -> None:
        """Start the timer."""
        self.start_time = time.time()
    
    def stop_timer(self) -> float:
        """Stop the timer and return elapsed time."""
        if self.start_time:
            self.total_time = time.time() - self.start_time
        return self.total_time or 0.0


class RetryContext:
    """
    Context manager for retry operations.
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        backoff_config: Optional[BackoffConfig] = None,
        exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
        on_retry: Optional[Callable[[int, Exception], None]] = None,
        on_failure: Optional[Callable[[List[Exception]], None]] = None
    ):
        self.max_attempts = max_attempts
        self.backoff_config = backoff_config or BackoffConfig()
        self.exceptions = exceptions
        self.on_retry = on_retry
        self.on_failure = on_failure
        self.state = RetryState(max_attempts)
        self.backoff = BackoffCalculator(self.backoff_config)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val and isinstance(exc_val, self.exceptions):
            self.state.add_error(exc_val)
            return self._should_retry()
        return False
    
    def _should_retry(self) -> bool:
        """Check if we should retry."""
        self.state.increment()
        
        if self.state.is_exhausted():
            if self.on_failure:
                self.on_failure(self.state.errors)
            return False
        
        if self.on_retry:
            self.on_retry(self.state.attempts, self.state.last_error)
        
        delay = self.backoff.calculate(self.state.attempts)
        if delay > 0:
            time.sleep(delay)
        
        return True
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with retry logic.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Function result
        
        Raises:
            Exception: If all retry attempts fail
        """
        self.state.reset()
        self.state.start_timer()
        
        while not self.state.is_exhausted():
            try:
                result = func(*args, **kwargs)
                self.state.stop_timer()
                return result
            except self.exceptions as e:
                self.state.add_error(e)
                self.state.increment()
                
                if self.state.is_exhausted():
                    if self.on_failure:
                        self.on_failure(self.state.errors)
                    raise self.state.last_error
                
                if self.on_retry:
                    self.on_retry(self.state.attempts, e)
                
                delay = self.backoff.calculate(self.state.attempts)
                if delay > 0:
                    time.sleep(delay)
        
        raise RuntimeError("Retry logic error")
    
    async def async_execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute an async function with retry logic.
        
        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Function result
        
        Raises:
            Exception: If all retry attempts fail
        """
        self.state.reset()
        self.state.start_timer()
        
        while not self.state.is_exhausted():
            try:
                result = await func(*args, **kwargs)
                self.state.stop_timer()
                return result
            except self.exceptions as e:
                self.state.add_error(e)
                self.state.increment()
                
                if self.state.is_exhausted():
                    if self.on_failure:
                        self.on_failure(self.state.errors)
                    raise self.state.last_error
                
                if self.on_retry:
                    self.on_retry(self.state.attempts, e)
                
                delay = self.backoff.calculate(self.state.attempts)
                if delay > 0:
                    await asyncio.sleep(delay)
        
        raise RuntimeError("Retry logic error")


def retry(
    max_attempts: int = 3,
    backoff_config: Optional[BackoffConfig] = None,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
    on_failure: Optional[Callable[[List[Exception]], None]] = None
):
    """
    Decorator for retrying a function with backoff.
    
    Args:
        max_attempts: Maximum number of attempts
        backoff_config: Backoff configuration
        exceptions: Exception types to catch
        on_retry: Callback on retry
        on_failure: Callback on final failure
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            context = RetryContext(
                max_attempts=max_attempts,
                backoff_config=backoff_config,
                exceptions=exceptions,
                on_retry=on_retry,
                on_failure=on_failure
            )
            return context.execute(func, *args, **kwargs)
        return wrapper
    return decorator


def async_retry(
    max_attempts: int = 3,
    backoff_config: Optional[BackoffConfig] = None,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
    on_failure: Optional[Callable[[List[Exception]], None]] = None
):
    """
    Decorator for retrying an async function with backoff.
    
    Args:
        max_attempts: Maximum number of attempts
        backoff_config: Backoff configuration
        exceptions: Exception types to catch
        on_retry: Callback on retry
        on_failure: Callback on final failure
    
    Returns:
        Decorated async function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            context = RetryContext(
                max_attempts=max_attempts,
                backoff_config=backoff_config,
                exceptions=exceptions,
                on_retry=on_retry,
                on_failure=on_failure
            )
            return await context.async_execute(func, *args, **kwargs)
        return wrapper
    return decorator


# Common backoff configurations
NO_BACKOFF = BackoffConfig(strategy=BackoffType.NONE)
FIXED_BACKOFF = BackoffConfig(strategy=BackoffType.FIXED, base_delay=1.0)
LINEAR_BACKOFF = BackoffConfig(strategy=BackoffType.LINEAR, base_delay=0.5)
EXPONENTIAL_BACKOFF = BackoffConfig(strategy=BackoffType.EXPONENTIAL, base_delay=1.0, multiplier=2.0)
EXPONENTIAL_JITTER_BACKOFF = BackoffConfig(
    strategy=BackoffType.EXPONENTIAL_JITTER,
    base_delay=1.0,
    multiplier=2.0,
    jitter_factor=0.1
)
FULL_JITTER_BACKOFF = BackoffConfig(
    strategy=BackoffType.FULL_JITTER,
    base_delay=1.0,
    multiplier=2.0
)
DECORRELATED_JITTER_BACKOFF = BackoffConfig(
    strategy=BackoffType.DECORRELATED_JITTER,
    base_delay=1.0,
    multiplier=2.0,
    jitter_factor=0.1
)


__all__ = [
    # Enums
    'BackoffType',
    
    # Classes
    'BackoffConfig',
    'BackoffCalculator',
    'RetryState',
    'RetryContext',
    
    # Decorators
    'retry',
    'async_retry',
    
    # Predefined backoff configs
    'NO_BACKOFF',
    'FIXED_BACKOFF',
    'LINEAR_BACKOFF',
    'EXPONENTIAL_BACKOFF',
    'EXPONENTIAL_JITTER_BACKOFF',
    'FULL_JITTER_BACKOFF',
    'DECORRELATED_JITTER_BACKOFF',
]
