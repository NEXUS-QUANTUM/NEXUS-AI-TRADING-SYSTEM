"""
Swing Bot Decorators Module
============================

This module provides decorator utilities for the Swing Bot trading system.
Includes method decorators, function decorators, and utility decorators.
"""

import time
import functools
import asyncio
import logging
import inspect
from typing import Any, Callable, Optional, Type, TypeVar, Union, Tuple, Dict, List
from datetime import datetime
import threading


T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


def timer(func: F) -> F:
    """
    Decorator to measure function execution time.
    
    Args:
        func: Function to decorate
    
    Returns:
        Decorated function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logging.debug(f"{func.__name__} took {elapsed:.4f}s")
        return result
    return wrapper


def async_timer(func: F) -> F:
    """
    Decorator to measure async function execution time.
    
    Args:
        func: Async function to decorate
    
    Returns:
        Decorated async function
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logging.debug(f"{func.__name__} took {elapsed:.4f}s")
        return result
    return wrapper


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception
) -> Callable[[F], F]:
    """
    Decorator to retry a function on failure.
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay in seconds
        backoff: Backoff multiplier
        exceptions: Exception types to catch
    
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            last_error = None
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    attempt += 1
                    if attempt >= max_attempts:
                        break
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_error
        return wrapper
    return decorator


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception
) -> Callable[[F], F]:
    """
    Decorator to retry an async function on failure.
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay in seconds
        backoff: Backoff multiplier
        exceptions: Exception types to catch
    
    Returns:
        Decorated async function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            last_error = None
            
            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    attempt += 1
                    if attempt >= max_attempts:
                        break
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_error
        return wrapper
    return decorator


def timeout(seconds: float) -> Callable[[F], F]:
    """
    Decorator to add a timeout to a function.
    
    Args:
        seconds: Timeout in seconds
    
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds}s")
            
            # Set timeout handler
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(seconds))
            
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            
            return result
        return wrapper
    return decorator


def async_timeout(seconds: float) -> Callable[[F], F]:
    """
    Decorator to add a timeout to an async function.
    
    Args:
        seconds: Timeout in seconds
    
    Returns:
        Decorated async function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds}s")
        return wrapper
    return decorator


def singleton(cls: Type[T]) -> Type[T]:
    """
    Decorator to create a singleton class.
    
    Args:
        cls: Class to decorate
    
    Returns:
        Singleton class
    """
    instances = {}
    
    @functools.wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance


def synchronized(lock: Optional[threading.Lock] = None) -> Callable[[F], F]:
    """
    Decorator to synchronize a function with a lock.
    
    Args:
        lock: Lock object (creates new if None)
    
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        _lock = lock or threading.Lock()
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with _lock:
                return func(*args, **kwargs)
        return wrapper
    return decorator


def async_synchronized(lock: Optional[asyncio.Lock] = None) -> Callable[[F], F]:
    """
    Decorator to synchronize an async function with a lock.
    
    Args:
        lock: Async lock object (creates new if None)
    
    Returns:
        Decorated async function
    """
    def decorator(func: F) -> F:
        _lock = lock or asyncio.Lock()
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with _lock:
                return await func(*args, **kwargs)
        return wrapper
    return decorator


def log_execution(level: int = logging.INFO) -> Callable[[F], F]:
    """
    Decorator to log function execution.
    
    Args:
        level: Log level
    
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logging.log(level, f"Executing {func.__name__}")
            try:
                result = func(*args, **kwargs)
                logging.log(level, f"Completed {func.__name__}")
                return result
            except Exception as e:
                logging.error(f"Error in {func.__name__}: {e}")
                raise
        return wrapper
    return decorator


def async_log_execution(level: int = logging.INFO) -> Callable[[F], F]:
    """
    Decorator to log async function execution.
    
    Args:
        level: Log level
    
    Returns:
        Decorated async function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logging.log(level, f"Executing {func.__name__}")
            try:
                result = await func(*args, **kwargs)
                logging.log(level, f"Completed {func.__name__}")
                return result
            except Exception as e:
                logging.error(f"Error in {func.__name__}: {e}")
                raise
        return wrapper
    return decorator


def cache(ttl: Optional[float] = None, max_size: int = 100) -> Callable[[F], F]:
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time-to-live in seconds (None for infinite)
        max_size: Maximum cache size
    
    Returns:
        Decorated function
    """
    cache_data = {}
    cache_times = {}
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(kwargs.items()))
            
            # Check if in cache and not expired
            if key in cache_data:
                if ttl is None or (time.time() - cache_times[key]) < ttl:
                    return cache_data[key]
            
            # Compute and cache
            result = func(*args, **kwargs)
            cache_data[key] = result
            cache_times[key] = time.time()
            
            # Enforce max size
            if len(cache_data) > max_size:
                oldest_key = min(cache_times, key=cache_times.get)
                del cache_data[oldest_key]
                del cache_times[oldest_key]
            
            return result
        return wrapper
    return decorator


def async_cache(ttl: Optional[float] = None, max_size: int = 100) -> Callable[[F], F]:
    """
    Decorator to cache async function results.
    
    Args:
        ttl: Time-to-live in seconds (None for infinite)
        max_size: Maximum cache size
    
    Returns:
        Decorated async function
    """
    cache_data = {}
    cache_times = {}
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            key = (args, tuple(kwargs.items()))
            
            # Check if in cache and not expired
            if key in cache_data:
                if ttl is None or (time.time() - cache_times[key]) < ttl:
                    return cache_data[key]
            
            # Compute and cache
            result = await func(*args, **kwargs)
            cache_data[key] = result
            cache_times[key] = time.time()
            
            # Enforce max size
            if len(cache_data) > max_size:
                oldest_key = min(cache_times, key=cache_times.get)
                del cache_data[oldest_key]
                del cache_times[oldest_key]
            
            return result
        return wrapper
    return decorator


def validate_args(*types: Type) -> Callable[[F], F]:
    """
    Decorator to validate function arguments.
    
    Args:
        types: Expected argument types
    
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for i, (arg, expected_type) in enumerate(zip(args, types)):
                if not isinstance(arg, expected_type):
                    raise TypeError(
                        f"Argument {i} ({arg}) must be of type {expected_type.__name__}"
                    )
            return func(*args, **kwargs)
        return wrapper
    return decorator


def async_validate_args(*types: Type) -> Callable[[F], F]:
    """
    Decorator to validate async function arguments.
    
    Args:
        types: Expected argument types
    
    Returns:
        Decorated async function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for i, (arg, expected_type) in enumerate(zip(args, types)):
                if not isinstance(arg, expected_type):
                    raise TypeError(
                        f"Argument {i} ({arg}) must be of type {expected_type.__name__}"
                    )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def rate_limit(limit: float, per: float = 1.0) -> Callable[[F], F]:
    """
    Decorator to rate limit a function.
    
    Args:
        limit: Maximum number of calls
        per: Time period in seconds
    
    Returns:
        Decorated function
    """
    last_called = [0.0]
    calls = [0]
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            if now - last_called[0] >= per:
                calls[0] = 0
                last_called[0] = now
            
            if calls[0] >= limit:
                raise RuntimeError(f"Rate limit exceeded: {limit} calls per {per}s")
            
            calls[0] += 1
            return func(*args, **kwargs)
        return wrapper
    return decorator


def async_rate_limit(limit: float, per: float = 1.0) -> Callable[[F], F]:
    """
    Decorator to rate limit an async function.
    
    Args:
        limit: Maximum number of calls
        per: Time period in seconds
    
    Returns:
        Decorated async function
    """
    last_called = [0.0]
    calls = [0]
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            now = time.time()
            if now - last_called[0] >= per:
                calls[0] = 0
                last_called[0] = now
            
            if calls[0] >= limit:
                raise RuntimeError(f"Rate limit exceeded: {limit} calls per {per}s")
            
            calls[0] += 1
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def deprecated(message: Optional[str] = None) -> Callable[[F], F]:
    """
    Decorator to mark a function as deprecated.
    
    Args:
        message: Deprecation message
    
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            msg = message or f"{func.__name__} is deprecated"
            logging.warning(msg)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def async_deprecated(message: Optional[str] = None) -> Callable[[F], F]:
    """
    Decorator to mark an async function as deprecated.
    
    Args:
        message: Deprecation message
    
    Returns:
        Decorated async function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            msg = message or f"{func.__name__} is deprecated"
            logging.warning(msg)
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def requires(*dependencies: str) -> Callable[[F], F]:
    """
    Decorator to check required dependencies.
    
    Args:
        dependencies: Required dependency names
    
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for dep in dependencies:
                try:
                    __import__(dep)
                except ImportError:
                    raise ImportError(f"Required dependency '{dep}' not found")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def async_requires(*dependencies: str) -> Callable[[F], F]:
    """
    Decorator to check required dependencies for async functions.
    
    Args:
        dependencies: Required dependency names
    
    Returns:
        Decorated async function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for dep in dependencies:
                try:
                    __import__(dep)
                except ImportError:
                    raise ImportError(f"Required dependency '{dep}' not found")
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def class_property(func: Callable) -> property:
    """
    Decorator to create a class property.
    
    Args:
        func: Function to decorate
    
    Returns:
        Class property
    """
    return classmethod(property(func))


def static_class_property(func: Callable) -> property:
    """
    Decorator to create a static class property.
    
    Args:
        func: Function to decorate
    
    Returns:
        Static class property
    """
    return staticmethod(property(func))


def singleton_method(func: F) -> F:
    """
    Decorator to ensure a method is called only once.
    
    Args:
        func: Method to decorate
    
    Returns:
        Decorated method
    """
    called = False
    result = None
    
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        nonlocal called, result
        if not called:
            result = func(self, *args, **kwargs)
            called = True
        return result
    return wrapper


def async_singleton_method(func: F) -> F:
    """
    Decorator to ensure an async method is called only once.
    
    Args:
        func: Async method to decorate
    
    Returns:
        Decorated async method
    """
    called = False
    result = None
    
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        nonlocal called, result
        if not called:
            result = await func(self, *args, **kwargs)
            called = True
        return result
    return wrapper


def enforce_type(return_type: Type) -> Callable[[F], F]:
    """
    Decorator to enforce return type.
    
    Args:
        return_type: Expected return type
    
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if not isinstance(result, return_type):
                raise TypeError(
                    f"Return value must be of type {return_type.__name__}, got {type(result).__name__}"
                )
            return result
        return wrapper
    return decorator


def async_enforce_type(return_type: Type) -> Callable[[F], F]:
    """
    Decorator to enforce return type for async functions.
    
    Args:
        return_type: Expected return type
    
    Returns:
        Decorated async function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            if not isinstance(result, return_type):
                raise TypeError(
                    f"Return value must be of type {return_type.__name__}, got {type(result).__name__}"
                )
            return result
        return wrapper
    return decorator


__all__ = [
    'timer',
    'async_timer',
    'retry',
    'async_retry',
    'timeout',
    'async_timeout',
    'singleton',
    'synchronized',
    'async_synchronized',
    'log_execution',
    'async_log_execution',
    'cache',
    'async_cache',
    'validate_args',
    'async_validate_args',
    'rate_limit',
    'async_rate_limit',
    'deprecated',
    'async_deprecated',
    'requires',
    'async_requires',
    'class_property',
    'static_class_property',
    'singleton_method',
    'async_singleton_method',
    'enforce_type',
    'async_enforce_type',
]
