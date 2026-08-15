"""
Swing Bot Async Utilities Module
==================================

This module provides asynchronous utilities for the Swing Bot trading system.
Includes async task management, async helpers, and async coordination utilities.
"""

import asyncio
import time
import functools
import threading
from typing import Any, Callable, Optional, List, Dict, Union, TypeVar, Coroutine, Awaitable
from concurrent.futures import ThreadPoolExecutor
import logging


T = TypeVar('T')


class AsyncUtils:
    """
    Utility class for asynchronous operations.
    """
    
    @staticmethod
    async def sleep(seconds: float) -> None:
        """
        Sleep for a given number of seconds.
        
        Args:
            seconds: Number of seconds to sleep
        """
        await asyncio.sleep(seconds)
    
    @staticmethod
    async def sleep_ms(milliseconds: float) -> None:
        """
        Sleep for a given number of milliseconds.
        
        Args:
            milliseconds: Number of milliseconds to sleep
        """
        await asyncio.sleep(milliseconds / 1000)
    
    @staticmethod
    async def gather(*tasks: Coroutine, return_exceptions: bool = False) -> List[Any]:
        """
        Gather multiple async tasks.
        
        Args:
            *tasks: Async tasks to gather
            return_exceptions: Return exceptions instead of raising
        
        Returns:
            List of results
        """
        return await asyncio.gather(*tasks, return_exceptions=return_exceptions)
    
    @staticmethod
    async def wait_for(coro: Coroutine, timeout: float) -> Any:
        """
        Wait for a coroutine with a timeout.
        
        Args:
            coro: Coroutine to wait for
            timeout: Timeout in seconds
        
        Returns:
            Coroutine result
        
        Raises:
            TimeoutError: If timeout is exceeded
        """
        return await asyncio.wait_for(coro, timeout=timeout)
    
    @staticmethod
    async def shield(coro: Coroutine) -> Any:
        """
        Shield a coroutine from cancellation.
        
        Args:
            coro: Coroutine to shield
        
        Returns:
            Coroutine result
        """
        return await asyncio.shield(coro)
    
    @staticmethod
    async def create_task(coro: Coroutine, name: Optional[str] = None) -> asyncio.Task:
        """
        Create a task from a coroutine.
        
        Args:
            coro: Coroutine to wrap
            name: Task name
        
        Returns:
            Task object
        """
        return asyncio.create_task(coro, name=name)
    
    @staticmethod
    def run_in_executor(func: Callable, *args, **kwargs) -> Awaitable[Any]:
        """
        Run a function in a thread pool executor.
        
        Args:
            func: Function to run
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Awaitable result
        """
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: func(*args, **kwargs))
    
    @staticmethod
    async def run_async(func: Callable, *args, **kwargs) -> Any:
        """
        Run a synchronous function asynchronously.
        
        Args:
            func: Synchronous function to run
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Function result
        """
        return await AsyncUtils.run_in_executor(func, *args, **kwargs)
    
    @staticmethod
    async def run_all_async(tasks: List[Callable]) -> List[Any]:
        """
        Run multiple synchronous functions asynchronously.
        
        Args:
            tasks: List of functions to run
        
        Returns:
            List of results
        """
        return await AsyncUtils.gather(*(AsyncUtils.run_async(task) for task in tasks))
    
    @staticmethod
    def create_event() -> asyncio.Event:
        """
        Create an async event.
        
        Returns:
            Async event
        """
        return asyncio.Event()
    
    @staticmethod
    def create_queue(maxsize: int = 0) -> asyncio.Queue:
        """
        Create an async queue.
        
        Args:
            maxsize: Maximum queue size
        
        Returns:
            Async queue
        """
        return asyncio.Queue(maxsize=maxsize)
    
    @staticmethod
    def create_lock() -> asyncio.Lock:
        """
        Create an async lock.
        
        Returns:
            Async lock
        """
        return asyncio.Lock()
    
    @staticmethod
    def create_semaphore(value: int) -> asyncio.Semaphore:
        """
        Create an async semaphore.
        
        Args:
            value: Initial semaphore value
        
        Returns:
            Async semaphore
        """
        return asyncio.Semaphore(value=value)
    
    @staticmethod
    async def timeout_after(seconds: float):
        """
        Context manager for timeout.
        
        Args:
            seconds: Timeout in seconds
        
        Returns:
            Async context manager
        """
        return asyncio.timeout(seconds)
    
    @staticmethod
    async def wait_for_condition(
        condition: Callable[[], bool],
        timeout: float,
        interval: float = 0.1
    ) -> bool:
        """
        Wait for a condition to be true.
        
        Args:
            condition: Condition function
            timeout: Timeout in seconds
            interval: Check interval in seconds
        
        Returns:
            True if condition was met, False if timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            if condition():
                return True
            await asyncio.sleep(interval)
        return False
    
    @staticmethod
    async def retry_async(
        func: Callable,
        max_attempts: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception
    ) -> Any:
        """
        Retry an async function with backoff.
        
        Args:
            func: Async function to retry
            max_attempts: Maximum number of attempts
            delay: Initial delay in seconds
            backoff: Backoff multiplier
            exceptions: Exception types to catch
        
        Returns:
            Function result
        
        Raises:
            Exception: If all attempts fail
        """
        attempt = 0
        current_delay = delay
        last_error = None
        
        while attempt < max_attempts:
            try:
                return await func()
            except exceptions as e:
                last_error = e
                attempt += 1
                if attempt >= max_attempts:
                    break
                await asyncio.sleep(current_delay)
                current_delay *= backoff
        
        raise last_error


class AsyncTaskManager:
    """
    Manager for async tasks.
    """
    
    def __init__(self):
        self._tasks: List[asyncio.Task] = []
        self._lock = asyncio.Lock()
        self._running = True
        self._results: List[Any] = []
        self._errors: List[Exception] = []
    
    async def add_task(self, coro: Coroutine, name: Optional[str] = None) -> asyncio.Task:
        """
        Add a task to the manager.
        
        Args:
            coro: Coroutine to add
            name: Task name
        
        Returns:
            Task object
        """
        task = asyncio.create_task(coro, name=name)
        async with self._lock:
            self._tasks.append(task)
        return task
    
    async def wait_all(self, return_exceptions: bool = False) -> List[Any]:
        """
        Wait for all tasks to complete.
        
        Args:
            return_exceptions: Return exceptions instead of raising
        
        Returns:
            List of results
        """
        async with self._lock:
            if not self._tasks:
                return []
            
            results = await asyncio.gather(
                *self._tasks,
                return_exceptions=return_exceptions
            )
            self._tasks.clear()
            return results
    
    async def cancel_all(self) -> None:
        """Cancel all tasks."""
        async with self._lock:
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
                self._tasks.clear()
    
    async def wait_one(self) -> Any:
        """
        Wait for the first task to complete.
        
        Returns:
            Result of the completed task
        
        Raises:
            Exception: If the task raises an exception
        """
        async with self._lock:
            if not self._tasks:
                raise RuntimeError("No tasks to wait for")
            
            done, pending = await asyncio.wait(
                self._tasks,
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Remove completed tasks
            self._tasks = list(pending)
            
            # Get result from completed task
            for task in done:
                return task.result()
            
            raise RuntimeError("No task completed")
    
    @property
    def task_count(self) -> int:
        """Get the number of active tasks."""
        return len(self._tasks)
    
    @property
    def is_running(self) -> bool:
        """Check if the manager is running."""
        return self._running
    
    def stop(self) -> None:
        """Stop the manager."""
        self._running = False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            'task_count': self.task_count,
            'is_running': self.is_running,
            'results_count': len(self._results),
            'errors_count': len(self._errors),
        }


class AsyncRateLimiter:
    """
    Async rate limiter.
    """
    
    def __init__(self, max_calls: int, period: float):
        """
        Initialize the rate limiter.
        
        Args:
            max_calls: Maximum number of calls per period
            period: Period in seconds
        """
        self.max_calls = max_calls
        self.period = period
        self._calls: List[float] = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """
        Acquire a permit for a call.
        
        Raises:
            RuntimeError: If rate limit is exceeded and cannot be acquired
        """
        async with self._lock:
            now = time.time()
            
            # Remove expired calls
            self._calls = [t for t in self._calls if t > now - self.period]
            
            if len(self._calls) >= self.max_calls:
                # Wait until the oldest call expires
                wait_time = self._calls[0] + self.period - now
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                
                # Remove expired calls after waiting
                self._calls = [t for t in self._calls if t > time.time() - self.period]
            
            self._calls.append(time.time())
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def async_wrap(func: Callable) -> Callable:
    """
    Wrap a synchronous function to return an async function.
    
    Args:
        func: Synchronous function to wrap
    
    Returns:
        Async function
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await AsyncUtils.run_async(func, *args, **kwargs)
    return wrapper


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception
):
    """
    Decorator for retrying an async function.
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay in seconds
        backoff: Backoff multiplier
        exceptions: Exception types to catch
    
    Returns:
        Decorated async function
    """
    def decorator(func: Callable) -> Callable:
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


__all__ = [
    # Class
    'AsyncUtils',
    'AsyncTaskManager',
    'AsyncRateLimiter',
    
    # Decorators
    'async_wrap',
    'async_retry',
]
