"""
Swing Bot Threads Module
=========================

This module provides threading utilities for the Swing Bot trading system.
Includes thread pools, thread-safe operations, and concurrency management.
"""

import threading
import queue
import time
import asyncio
from typing import Callable, Optional, Any, Dict, List, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import functools
import logging
from concurrent.futures import ThreadPoolExecutor, Future, as_completed


class ThreadState(Enum):
    """Thread states."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class ThreadInfo:
    """Information about a thread."""
    name: str
    state: ThreadState
    thread: Optional[threading.Thread] = None
    start_time: Optional[float] = None
    stop_time: Optional[float] = None
    execution_count: int = 0
    last_execution: Optional[float] = None
    total_execution_time: float = 0.0
    error_count: int = 0
    last_error: Optional[str] = None


class ThreadSafeQueue:
    """
    Thread-safe queue wrapper.
    """
    
    def __init__(self, maxsize: int = 0):
        """
        Initialize a thread-safe queue.
        
        Args:
            maxsize: Maximum queue size (0 for unlimited)
        """
        self._queue = queue.Queue(maxsize)
        self._lock = threading.Lock()
        self._size = 0
    
    def put(self, item: Any, block: bool = True, timeout: Optional[float] = None) -> None:
        """Put an item into the queue."""
        with self._lock:
            self._queue.put(item, block=block, timeout=timeout)
            self._size += 1
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        """Get an item from the queue."""
        with self._lock:
            item = self._queue.get(block=block, timeout=timeout)
            self._size -= 1
            return item
    
    def get_nowait(self) -> Any:
        """Get an item without blocking."""
        return self.get(block=False)
    
    def put_nowait(self, item: Any) -> None:
        """Put an item without blocking."""
        self.put(item, block=False)
    
    def qsize(self) -> int:
        """Get queue size."""
        with self._lock:
            return self._size
    
    def empty(self) -> bool:
        """Check if queue is empty."""
        return self.qsize() == 0
    
    def full(self) -> bool:
        """Check if queue is full."""
        return self._queue.full()
    
    def task_done(self) -> None:
        """Mark a task as done."""
        self._queue.task_done()
    
    def join(self) -> None:
        """Wait for all tasks to complete."""
        self._queue.join()
    
    def clear(self) -> None:
        """Clear all items from the queue."""
        with self._lock:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                    self._size -= 1
                except queue.Empty:
                    break


class ThreadPool:
    """
    Thread pool for executing tasks concurrently.
    """
    
    def __init__(
        self,
        max_workers: int = 10,
        thread_name_prefix: str = "ThreadPool",
        queue_maxsize: int = 0
    ):
        """
        Initialize a thread pool.
        
        Args:
            max_workers: Maximum number of worker threads
            thread_name_prefix: Prefix for thread names
            queue_maxsize: Maximum queue size (0 for unlimited)
        """
        self.max_workers = max_workers
        self.thread_name_prefix = thread_name_prefix
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix
        )
        self._task_queue = ThreadSafeQueue(queue_maxsize)
        self._results = ThreadSafeQueue()
        self._lock = threading.Lock()
        self._running = True
        self._workers: List[ThreadInfo] = []
        self._shutdown_event = threading.Event()
        
        # Start worker threads
        self._start_workers()
    
    def _start_workers(self) -> None:
        """Start worker threads."""
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"{self.thread_name_prefix}-Worker-{i}",
                daemon=True
            )
            info = ThreadInfo(
                name=worker.name,
                state=ThreadState.IDLE,
                thread=worker
            )
            self._workers.append(info)
            worker.start()
    
    def _worker_loop(self) -> None:
        """Worker thread loop."""
        current_thread = threading.current_thread()
        info = next((w for w in self._workers if w.thread == current_thread), None)
        
        if info:
            info.state = ThreadState.RUNNING
        
        while self._running:
            try:
                # Get task from queue
                task = self._task_queue.get(timeout=0.1)
                if task is None:
                    continue
                
                # Execute task
                try:
                    if info:
                        info.execution_count += 1
                        info.last_execution = time.time()
                        start_time = time.time()
                    
                    # Execute the task
                    func, args, kwargs = task
                    result = func(*args, **kwargs)
                    
                    # Store result
                    self._results.put({
                        'result': result,
                        'success': True,
                        'error': None
                    })
                    
                    if info:
                        execution_time = time.time() - start_time
                        info.total_execution_time += execution_time
                    
                except Exception as e:
                    # Store error
                    self._results.put({
                        'result': None,
                        'success': False,
                        'error': str(e)
                    })
                    
                    if info:
                        info.error_count += 1
                        info.last_error = str(e)
                
                finally:
                    self._task_queue.task_done()
                    
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Worker error: {e}")
                continue
        
        if info:
            info.state = ThreadState.STOPPED
    
    def submit(self, func: Callable, *args, **kwargs) -> None:
        """
        Submit a task to the thread pool.
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        """
        if not self._running:
            raise RuntimeError("Thread pool is not running")
        
        self._task_queue.put((func, args, kwargs))
    
    def submit_future(self, func: Callable, *args, **kwargs) -> Future:
        """
        Submit a task and return a Future.
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        
        Returns:
            Future object for the task
        """
        return self._executor.submit(func, *args, **kwargs)
    
    def wait_for_results(self, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Wait for all results.
        
        Args:
            timeout: Timeout in seconds (None for infinite)
        
        Returns:
            List of results
        """
        results = []
        start_time = time.time()
        
        while True:
            if timeout and (time.time() - start_time) > timeout:
                break
            
            try:
                result = self._results.get(timeout=0.1)
                results.append(result)
            except queue.Empty:
                if self._task_queue.empty() and self._results.empty():
                    break
                continue
        
        return results
    
    def get_result(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Get a single result.
        
        Args:
            timeout: Timeout in seconds (None for infinite)
        
        Returns:
            Result dictionary or None if no results
        """
        try:
            return self._results.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the thread pool.
        
        Args:
            wait: Wait for all tasks to complete
        """
        self._running = False
        self._executor.shutdown(wait=wait)
        
        if wait:
            self._task_queue.join()
        
        for info in self._workers:
            info.state = ThreadState.STOPPED
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get thread pool statistics.
        
        Returns:
            Dictionary with statistics
        """
        with self._lock:
            return {
                'max_workers': self.max_workers,
                'running': self._running,
                'task_queue_size': self._task_queue.qsize(),
                'results_queue_size': self._results.qsize(),
                'workers': [
                    {
                        'name': info.name,
                        'state': info.state.value,
                        'execution_count': info.execution_count,
                        'error_count': info.error_count,
                        'total_execution_time': info.total_execution_time,
                        'last_error': info.last_error
                    }
                    for info in self._workers
                ]
            }
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True)


class AsyncThreadPool:
    """
    Async-compatible thread pool.
    """
    
    def __init__(self, max_workers: int = 10):
        """
        Initialize an async thread pool.
        
        Args:
            max_workers: Maximum number of worker threads
        """
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = asyncio.Lock()
        self._running = True
    
    async def run_in_executor(self, func: Callable, *args, **kwargs) -> Any:
        """
        Run a function in the executor.
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        
        Returns:
            Result of the function
        """
        if not self._running:
            raise RuntimeError("Thread pool is not running")
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, lambda: func(*args, **kwargs))
    
    async def submit_many(self, tasks: List[Callable]) -> List[Any]:
        """
        Submit multiple tasks and wait for all to complete.
        
        Args:
            tasks: List of functions to execute
        
        Returns:
            List of results
        """
        results = []
        for task in tasks:
            result = await self.run_in_executor(task)
            results.append(result)
        return results
    
    async def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the thread pool.
        
        Args:
            wait: Wait for all tasks to complete
        """
        self._running = False
        if wait:
            # Wait for all pending tasks
            await asyncio.sleep(0)
        self._executor.shutdown(wait=wait)


class ThreadSafeCounter:
    """
    Thread-safe counter.
    """
    
    def __init__(self, initial_value: int = 0):
        self._value = initial_value
        self._lock = threading.Lock()
    
    def increment(self, amount: int = 1) -> int:
        """Increment the counter."""
        with self._lock:
            self._value += amount
            return self._value
    
    def decrement(self, amount: int = 1) -> int:
        """Decrement the counter."""
        with self._lock:
            self._value -= amount
            return self._value
    
    def get_value(self) -> int:
        """Get the current counter value."""
        with self._lock:
            return self._value
    
    def reset(self, value: int = 0) -> None:
        """Reset the counter."""
        with self._lock:
            self._value = value


class ThreadSafeDict:
    """
    Thread-safe dictionary.
    """
    
    def __init__(self, initial_data: Optional[Dict] = None):
        self._data = initial_data or {}
        self._lock = threading.RLock()
    
    def get(self, key: Any, default: Any = None) -> Any:
        """Get a value from the dictionary."""
        with self._lock:
            return self._data.get(key, default)
    
    def set(self, key: Any, value: Any) -> None:
        """Set a value in the dictionary."""
        with self._lock:
            self._data[key] = value
    
    def delete(self, key: Any) -> bool:
        """Delete a key from the dictionary."""
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False
    
    def keys(self) -> List[Any]:
        """Get all keys."""
        with self._lock:
            return list(self._data.keys())
    
    def values(self) -> List[Any]:
        """Get all values."""
        with self._lock:
            return list(self._data.values())
    
    def items(self) -> List[Tuple[Any, Any]]:
        """Get all items."""
        with self._lock:
            return list(self._data.items())
    
    def update(self, other: Dict) -> None:
        """Update with another dictionary."""
        with self._lock:
            self._data.update(other)
    
    def clear(self) -> None:
        """Clear the dictionary."""
        with self._lock:
            self._data.clear()
    
    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
    
    def __contains__(self, key: Any) -> bool:
        with self._lock:
            return key in self._data


# Utility functions
def synchronized(method: Callable) -> Callable:
    """
    Decorator to synchronize a method with a lock.
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        lock = getattr(self, '_lock', None)
        if lock:
            with lock:
                return method(self, *args, **kwargs)
        else:
            return method(self, *args, **kwargs)
    return wrapper


def run_in_thread(func: Callable, *args, daemon: bool = True, **kwargs) -> threading.Thread:
    """
    Run a function in a separate thread.
    
    Args:
        func: Function to run
        *args: Positional arguments for the function
        daemon: Whether to run as a daemon thread
        **kwargs: Keyword arguments for the function
    
    Returns:
        Thread object
    """
    thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=daemon)
    thread.start()
    return thread


def run_with_timeout(func: Callable, timeout: float, *args, **kwargs) -> Tuple[bool, Any]:
    """
    Run a function with a timeout.
    
    Args:
        func: Function to run
        timeout: Timeout in seconds
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
    
    Returns:
        Tuple of (completed, result)
    """
    result = None
    completed = False
    
    def wrapper():
        nonlocal result, completed
        try:
            result = func(*args, **kwargs)
            completed = True
        except Exception as e:
            result = e
    
    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        return False, None
    
    if isinstance(result, Exception):
        raise result
    
    return completed, result


# Export all public classes and functions
__all__ = [
    'ThreadState',
    'ThreadInfo',
    'ThreadSafeQueue',
    'ThreadPool',
    'AsyncThreadPool',
    'ThreadSafeCounter',
    'ThreadSafeDict',
    'synchronized',
    'run_in_thread',
    'run_with_timeout'
]
