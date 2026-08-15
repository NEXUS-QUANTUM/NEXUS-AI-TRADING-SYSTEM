"""
Swing Bot Retry Utilities Module
=================================

This module provides retry utilities for the Swing Bot trading system.
Includes retry decorators, backoff strategies, and error handling utilities.
"""

import time
import asyncio
import functools
from typing import Callable, Any, Optional, List, Dict, Union, Tuple, Type, TypeVar
from enum import Enum
from dataclasses import dataclass, field
import logging
import random


class BackoffStrategy(Enum):
    """Backoff strategies for retries."""
    NONE = "none"  # No backoff, retry immediately
    FIXED = "fixed"  # Fixed delay between retries
    LINEAR = "linear"  # Linearly increasing delay
    EXPONENTIAL = "exponential"  # Exponentially increasing delay
    RANDOM = "random"  # Random delay between retries
    EXPONENTIAL_JITTER = "exponential_jitter"  # Exponential with random jitter


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    backoff_multiplier: float = 2.0
    jitter: float = 0.1
    retry_on_exceptions: List[Type[Exception]] = field(default_factory=list)
    retry_on_result: Optional[Callable[[Any], bool]] = None
    timeout: Optional[float] = None
    logging_enabled: bool = True


class RetryError(Exception):
    """Exception raised when retry attempts are exhausted."""
    pass


def calculate_backoff(attempt: int, config: RetryConfig) -> float:
    """
    Calculate the backoff delay for a given attempt.
    
    Args:
        attempt: Current attempt number (0-based)
        config: Retry configuration
    
    Returns:
        Delay in seconds
    """
    if config.backoff_strategy == BackoffStrategy.NONE:
        return 0.0
    
    if config.backoff_strategy == BackoffStrategy.FIXED:
        delay = config.initial_delay
    
    elif config.backoff_strategy == BackoffStrategy.LINEAR:
        delay = config.initial_delay * (attempt + 1)
    
    elif config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
        delay = config.initial_delay * (config.backoff_multiplier ** attempt)
    
    elif config.backoff_strategy == BackoffStrategy.RANDOM:
        delay = random.uniform(0, config.initial_delay * (attempt + 1))
    
    elif config.backoff_strategy == BackoffStrategy.EXPONENTIAL_JITTER:
        base_delay = config.initial_delay * (config.backoff_multiplier ** attempt)
        jitter_amount = base_delay * config.jitter
        delay = base_delay + random.uniform(-jitter_amount, jitter_amount)
        delay = max(0, delay)
    
    else:
        delay = config.initial_delay
    
    # Apply max delay limit
    return min(delay, config.max_delay)


def should_retry_exception(exception: Exception, config: RetryConfig) -> bool:
    """
    Check if an exception should trigger a retry.
    
    Args:
        exception: The exception that occurred
        config: Retry configuration
    
    Returns:
        True if should retry, False otherwise
    """
    if not config.retry_on_exceptions:
        return True
    
    for exc_type in config.retry_on_exceptions:
        if isinstance(exception, exc_type):
            return True
    
    return False


def retry(config: Optional[RetryConfig] = None):
    """
    Decorator for retrying a function.
    
    Args:
        config: Retry configuration
    
    Returns:
        Decorated function
    """
    config = config or RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            last_exception = None
            
            while attempt < config.max_attempts:
                try:
                    # Execute the function
                    if config.timeout:
                        result = _run_with_timeout(func, config.timeout, *args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    
                    # Check if we should retry based on result
                    if config.retry_on_result and config.retry_on_result(result):
                        raise RetryError(f"Result condition triggered retry: {result}")
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    # Check if this exception should trigger a retry
                    if not should_retry_exception(e, config):
                        raise
                    
                    attempt += 1
                    
                    if attempt >= config.max_attempts:
                        break
                    
                    # Calculate and apply backoff
                    delay = calculate_backoff(attempt, config)
                    if delay > 0:
                        if config.logging_enabled:
                            logging.debug(
                                f"Retry {attempt}/{config.max_attempts} for {func.__name__} "
                                f"after {delay:.2f}s delay due to: {e}"
                            )
                        time.sleep(delay)
            
            # All attempts exhausted
            raise RetryError(
                f"All {config.max_attempts} attempts failed for {func.__name__}"
            ) from last_exception
        
        return wrapper
    return decorator


def async_retry(config: Optional[RetryConfig] = None):
    """
    Async decorator for retrying an async function.
    
    Args:
        config: Retry configuration
    
    Returns:
        Decorated async function
    """
    config = config or RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            attempt = 0
            last_exception = None
            
            while attempt < config.max_attempts:
                try:
                    # Execute the function
                    if config.timeout:
                        result = await _async_run_with_timeout(func, config.timeout, *args, **kwargs)
                    else:
                        result = await func(*args, **kwargs)
                    
                    # Check if we should retry based on result
                    if config.retry_on_result and config.retry_on_result(result):
                        raise RetryError(f"Result condition triggered retry: {result}")
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    # Check if this exception should trigger a retry
                    if not should_retry_exception(e, config):
                        raise
                    
                    attempt += 1
                    
                    if attempt >= config.max_attempts:
                        break
                    
                    # Calculate and apply backoff
                    delay = calculate_backoff(attempt, config)
                    if delay > 0:
                        if config.logging_enabled:
                            logging.debug(
                                f"Retry {attempt}/{config.max_attempts} for {func.__name__} "
                                f"after {delay:.2f}s delay due to: {e}"
                            )
                        await asyncio.sleep(delay)
            
            # All attempts exhausted
            raise RetryError(
                f"All {config.max_attempts} attempts failed for {func.__name__}"
            ) from last_exception
        
        return wrapper
    return decorator


def _run_with_timeout(func: Callable, timeout: float, *args, **kwargs) -> Any:
    """
    Run a function with a timeout.
    
    Args:
        func: Function to run
        timeout: Timeout in seconds
        *args: Positional arguments
        **kwargs: Keyword arguments
    
    Returns:
        Function result
    
    Raises:
        TimeoutError: If function times out
    """
    import threading
    
    result = None
    error = None
    completed = False
    
    def wrapper():
        nonlocal result, error, completed
        try:
            result = func(*args, **kwargs)
            completed = True
        except Exception as e:
            error = e
    
    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    thread.join(timeout)
    
    if not completed:
        raise TimeoutError(f"Function timed out after {timeout}s")
    
    if error:
        raise error
    
    return result


async def _async_run_with_timeout(func: Callable, timeout: float, *args, **kwargs) -> Any:
    """
    Run an async function with a timeout.
    
    Args:
        func: Async function to run
        timeout: Timeout in seconds
        *args: Positional arguments
        **kwargs: Keyword arguments
    
    Returns:
        Function result
    
    Raises:
        TimeoutError: If function times out
    """
    try:
        return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(f"Function timed out after {timeout}s")


class RetryContext:
    """
    Context manager for retrying operations.
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.attempts = 0
        self.last_exception = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val and should_retry_exception(exc_val, self.config):
            return self._should_retry()
        return False
    
    def _should_retry(self) -> bool:
        """Check if we should retry."""
        self.attempts += 1
        if self.attempts >= self.config.max_attempts:
            return False
        
        delay = calculate_backoff(self.attempts, self.config)
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
            RetryError: If all attempts fail
        """
        self.attempts = 0
        
        while self.attempts < self.config.max_attempts:
            try:
                if self.config.timeout:
                    return _run_with_timeout(func, self.config.timeout, *args, **kwargs)
                return func(*args, **kwargs)
            except Exception as e:
                self.last_exception = e
                if not should_retry_exception(e, self.config):
                    raise
                self.attempts += 1
                if self.attempts >= self.config.max_attempts:
                    break
                delay = calculate_backoff(self.attempts, self.config)
                if delay > 0:
                    time.sleep(delay)
        
        raise RetryError(
            f"All {self.config.max_attempts} attempts failed"
        ) from self.last_exception
    
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
            RetryError: If all attempts fail
        """
        self.attempts = 0
        
        while self.attempts < self.config.max_attempts:
            try:
                if self.config.timeout:
                    return await _async_run_with_timeout(func, self.config.timeout, *args, **kwargs)
                return await func(*args, **kwargs)
            except Exception as e:
                self.last_exception = e
                if not should_retry_exception(e, self.config):
                    raise
                self.attempts += 1
                if self.attempts >= self.config.max_attempts:
                    break
                delay = calculate_backoff(self.attempts, self.config)
                if delay > 0:
                    await asyncio.sleep(delay)
        
        raise RetryError(
            f"All {self.config.max_attempts} attempts failed"
        ) from self.last_exception


# Convenience functions
def retry_call(func: Callable, *args, config: Optional[RetryConfig] = None, **kwargs) -> Any:
    """
    Call a function with retry logic.
    
    Args:
        func: Function to call
        *args: Positional arguments
        config: Retry configuration
        **kwargs: Keyword arguments
    
    Returns:
        Function result
    """
    context = RetryContext(config)
    return context.execute(func, *args, **kwargs)


async def retry_call_async(func: Callable, *args, config: Optional[RetryConfig] = None, **kwargs) -> Any:
    """
    Call an async function with retry logic.
    
    Args:
        func: Async function to call
        *args: Positional arguments
        config: Retry configuration
        **kwargs: Keyword arguments
    
    Returns:
        Function result
    """
    context = RetryContext(config)
    return await context.async_execute(func, *args, **kwargs)


# Common retry configurations
DEFAULT_RETRY_CONFIG = RetryConfig()
FAST_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay=0.1,
    max_delay=5.0,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    backoff_multiplier=2.0
)
AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    initial_delay=0.5,
    max_delay=10.0,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    backoff_multiplier=2.0
)
VERY_AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=10,
    initial_delay=0.5,
    max_delay=30.0,
    backoff_strategy=BackoffStrategy.EXPONENTIAL_JITTER,
    backoff_multiplier=2.0,
    jitter=0.3
)
NO_RETRY_CONFIG = RetryConfig(max_attempts=1)


__all__ = [
    'BackoffStrategy',
    'RetryConfig',
    'RetryError',
    'calculate_backoff',
    'should_retry_exception',
    'retry',
    'async_retry',
    'RetryContext',
    'retry_call',
    'retry_call_async',
    'DEFAULT_RETRY_CONFIG',
    'FAST_RETRY_CONFIG',
    'AGGRESSIVE_RETRY_CONFIG',
    'VERY_AGGRESSIVE_RETRY_CONFIG',
    'NO_RETRY_CONFIG',
]
