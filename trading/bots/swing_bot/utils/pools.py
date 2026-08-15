"""
Swing Bot Pools Module
=======================

This module provides pool utilities for the Swing Bot trading system.
Includes connection pools, object pools, and resource pool management.
"""

import threading
import time
import queue
from typing import Any, Callable, Optional, List, Dict, Union, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
import logging


class PoolState(Enum):
    """Pool states."""
    ACTIVE = "active"
    DRAINING = "draining"
    CLOSED = "closed"


@dataclass
class PoolStats:
    """Pool statistics."""
    size: int = 0
    available: int = 0
    in_use: int = 0
    max_size: int = 0
    total_created: int = 0
    total_destroyed: int = 0
    total_borrowed: int = 0
    total_returned: int = 0
    total_errors: int = 0
    avg_borrow_time: float = 0.0
    max_borrow_time: float = 0.0
    min_borrow_time: float = float('inf')


class PooledObject(Generic[Any]):
    """Wrapper for pooled objects."""
    
    def __init__(self, obj: Any, created_at: Optional[float] = None):
        self.obj = obj
        self.created_at = created_at or time.time()
        self.last_used: Optional[float] = None
        self.use_count: int = 0
        self.is_valid: bool = True
    
    def mark_used(self) -> None:
        """Mark the object as used."""
        self.last_used = time.time()
        self.use_count += 1
    
    def __repr__(self) -> str:
        return f"PooledObject(obj={self.obj}, use_count={self.use_count}, is_valid={self.is_valid})"


class ObjectPool(Generic[Any]):
    """
    Generic object pool with optional validation and lifecycle management.
    """
    
    def __init__(
        self,
        create_func: Callable[[], Any],
        max_size: int = 10,
        min_size: int = 0,
        max_idle_time: Optional[float] = 60.0,
        validate_func: Optional[Callable[[Any], bool]] = None,
        destroy_func: Optional[Callable[[Any], None]] = None,
        wait_timeout: Optional[float] = 30.0,
        name: str = "ObjectPool"
    ):
        """
        Initialize an object pool.
        
        Args:
            create_func: Function to create new objects
            max_size: Maximum pool size
            min_size: Minimum pool size
            max_idle_time: Maximum idle time before object is removed
            validate_func: Function to validate objects
            destroy_func: Function to destroy objects
            wait_timeout: Timeout for waiting for an object
            name: Pool name
        """
        self.create_func = create_func
        self.max_size = max_size
        self.min_size = min(min_size, max_size)
        self.max_idle_time = max_idle_time
        self.validate_func = validate_func
        self.destroy_func = destroy_func
        self.wait_timeout = wait_timeout
        self.name = name
        
        self._pool: List[PooledObject] = []
        self._in_use: List[PooledObject] = []
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._state = PoolState.ACTIVE
        self._stats = PoolStats(max_size=max_size)
        self._closed = False
        
        # Initialize with minimum size
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize the pool with minimum size."""
        with self._lock:
            for _ in range(self.min_size):
                obj = self._create_object()
                if obj:
                    self._pool.append(obj)
                    self._stats.size += 1
                    self._stats.available += 1
    
    def _create_object(self) -> Optional[PooledObject]:
        """Create a new pooled object."""
        try:
            obj = self.create_func()
            if obj is not None:
                pooled = PooledObject(obj)
                self._stats.total_created += 1
                return pooled
        except Exception as e:
            logging.error(f"Pool {self.name}: Error creating object: {e}")
            self._stats.total_errors += 1
        return None
    
    def _destroy_object(self, pooled: PooledObject) -> None:
        """Destroy a pooled object."""
        try:
            if self.destroy_func and pooled.obj:
                self.destroy_func(pooled.obj)
        except Exception as e:
            logging.error(f"Pool {self.name}: Error destroying object: {e}")
        finally:
            self._stats.total_destroyed += 1
    
    def _validate_object(self, pooled: PooledObject) -> bool:
        """Validate a pooled object."""
        if not pooled.is_valid:
            return False
        if self.validate_func:
            try:
                return self.validate_func(pooled.obj)
            except Exception as e:
                logging.error(f"Pool {self.name}: Error validating object: {e}")
                return False
        return True
    
    def _is_idle_expired(self, pooled: PooledObject) -> bool:
        """Check if an object has been idle too long."""
        if self.max_idle_time is None or pooled.last_used is None:
            return False
        return time.time() - pooled.last_used > self.max_idle_time
    
    def _maintain_pool(self) -> None:
        """Maintain the pool by removing expired or invalid objects."""
        with self._lock:
            # Remove expired or invalid idle objects
            to_remove = []
            for i, pooled in enumerate(self._pool):
                if not self._validate_object(pooled) or self._is_idle_expired(pooled):
                    to_remove.append(i)
            
            # Remove from end to avoid index shifting issues
            for i in reversed(to_remove):
                pooled = self._pool.pop(i)
                self._destroy_object(pooled)
                self._stats.available -= 1
                self._stats.size -= 1
            
            # Ensure minimum size
            while len(self._pool) + len(self._in_use) < self.min_size:
                obj = self._create_object()
                if obj:
                    self._pool.append(obj)
                    self._stats.size += 1
                    self._stats.available += 1
                else:
                    break
    
    def borrow(self, timeout: Optional[float] = None) -> Optional[Any]:
        """
        Borrow an object from the pool.
        
        Args:
            timeout: Timeout in seconds (default: self.wait_timeout)
        
        Returns:
            Borrowed object or None if timeout expires
        """
        if self._state == PoolState.CLOSED:
            raise RuntimeError(f"Pool {self.name} is closed")
        
        start_time = time.time()
        timeout = timeout if timeout is not None else self.wait_timeout
        
        with self._condition:
            # Try to get an available object
            while True:
                # Maintain the pool
                self._maintain_pool()
                
                # Try to get from pool
                if self._pool:
                    pooled = self._pool.pop()
                    if self._validate_object(pooled):
                        self._in_use.append(pooled)
                        self._stats.available -= 1
                        self._stats.in_use += 1
                        self._stats.total_borrowed += 1
                        pooled.mark_used()
                        
                        # Calculate borrow time
                        borrow_time = time.time() - start_time
                        self._stats.avg_borrow_time = (
                            (self._stats.avg_borrow_time * (self._stats.total_borrowed - 1) + borrow_time)
                            / max(1, self._stats.total_borrowed)
                        )
                        self._stats.max_borrow_time = max(self._stats.max_borrow_time, borrow_time)
                        self._stats.min_borrow_time = min(self._stats.min_borrow_time, borrow_time)
                        
                        return pooled.obj
                    else:
                        # Object is invalid, destroy it
                        self._destroy_object(pooled)
                        self._stats.size -= 1
                        continue
                
                # Check if we can create a new object
                if len(self._pool) + len(self._in_use) < self.max_size:
                    pooled = self._create_object()
                    if pooled:
                        self._in_use.append(pooled)
                        self._stats.in_use += 1
                        self._stats.size += 1
                        self._stats.total_borrowed += 1
                        pooled.mark_used()
                        return pooled.obj
                
                # No objects available, wait
                if timeout is not None:
                    remaining = timeout - (time.time() - start_time)
                    if remaining <= 0:
                        return None
                else:
                    remaining = None
                
                try:
                    self._condition.wait(timeout=remaining)
                except Exception:
                    pass
    
    def return_object(self, obj: Any) -> bool:
        """
        Return an object to the pool.
        
        Args:
            obj: Object to return
        
        Returns:
            True if object was returned, False otherwise
        """
        with self._lock:
            # Find the object in use
            for i, pooled in enumerate(self._in_use):
                if pooled.obj is obj:
                    pooled = self._in_use.pop(i)
                    self._stats.in_use -= 1
                    
                    if self._state == PoolState.CLOSED:
                        self._destroy_object(pooled)
                        self._stats.size -= 1
                        return True
                    
                    # Validate object before returning
                    if self._validate_object(pooled):
                        self._pool.append(pooled)
                        self._stats.available += 1
                        self._stats.total_returned += 1
                        self._stats.in_use -= 1
                    else:
                        self._destroy_object(pooled)
                        self._stats.size -= 1
                    
                    with self._condition:
                        self._condition.notify()
                    return True
            
            return False
    
    def close(self) -> None:
        """Close the pool and destroy all objects."""
        with self._lock:
            self._state = PoolState.CLOSED
            self._closed = True
            
            # Destroy all idle objects
            for pooled in self._pool:
                self._destroy_object(pooled)
            self._pool.clear()
            self._stats.available = 0
            self._stats.size = 0
            
            # Destroy all in-use objects (they should be returned first)
            for pooled in self._in_use:
                self._destroy_object(pooled)
            self._in_use.clear()
            self._stats.in_use = 0
            
            with self._condition:
                self._condition.notify_all()
    
    def get_stats(self) -> PoolStats:
        """Get pool statistics."""
        with self._lock:
            return PoolStats(
                size=self._stats.size,
                available=self._stats.available,
                in_use=self._stats.in_use,
                max_size=self.max_size,
                total_created=self._stats.total_created,
                total_destroyed=self._stats.total_destroyed,
                total_borrowed=self._stats.total_borrowed,
                total_returned=self._stats.total_returned,
                total_errors=self._stats.total_errors,
                avg_borrow_time=self._stats.avg_borrow_time,
                max_borrow_time=self._stats.max_borrow_time,
                min_borrow_time=self._stats.min_borrow_time
            )
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class ConnectionPool(ObjectPool):
    """
    Specialized pool for connections.
    """
    
    def __init__(
        self,
        create_func: Callable[[], Any],
        max_size: int = 10,
        min_size: int = 0,
        max_idle_time: Optional[float] = 60.0,
        validate_func: Optional[Callable[[Any], bool]] = None,
        destroy_func: Optional[Callable[[Any], None]] = None,
        wait_timeout: Optional[float] = 30.0,
        name: str = "ConnectionPool"
    ):
        super().__init__(
            create_func=create_func,
            max_size=max_size,
            min_size=min_size,
            max_idle_time=max_idle_time,
            validate_func=validate_func or self._default_validate,
            destroy_func=destroy_func or self._default_destroy,
            wait_timeout=wait_timeout,
            name=name
        )
    
    def _default_validate(self, conn: Any) -> bool:
        """Default connection validation."""
        try:
            # Check if connection is alive
            if hasattr(conn, 'ping') and callable(conn.ping):
                conn.ping()
                return True
            elif hasattr(conn, 'is_connected'):
                return conn.is_connected
            elif hasattr(conn, 'closed'):
                return not conn.closed
            return True
        except Exception:
            return False
    
    def _default_destroy(self, conn: Any) -> None:
        """Default connection destruction."""
        try:
            if hasattr(conn, 'close') and callable(conn.close):
                conn.close()
        except Exception:
            pass


class ThreadPool(ObjectPool):
    """
    Specialized pool for threads.
    """
    
    def __init__(
        self,
        max_size: int = 10,
        min_size: int = 0,
        target: Optional[Callable] = None,
        name: str = "ThreadPool"
    ):
        import threading
        self._target = target
        
        def create_thread():
            thread = threading.Thread(target=self._target, daemon=True)
            thread.start()
            return thread
        
        def validate_thread(thread):
            return thread.is_alive()
        
        def destroy_thread(thread):
            # Can't forcibly stop threads, just mark as invalid
            pass
        
        super().__init__(
            create_func=create_thread,
            max_size=max_size,
            min_size=min_size,
            max_idle_time=None,
            validate_func=validate_thread,
            destroy_func=destroy_thread,
            wait_timeout=10.0,
            name=name
        )
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function in a thread from the pool.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Function result
        """
        import threading
        
        result = None
        error = None
        event = threading.Event()
        
        def wrapper():
            nonlocal result, error
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                error = e
            finally:
                event.set()
        
        # Get a thread from the pool
        thread = self.borrow()
        if thread is None:
            raise RuntimeError("No thread available in pool")
        
        # Execute the function
        thread.run = wrapper
        event.wait()
        
        # Return thread to pool
        self.return_object(thread)
        
        if error:
            raise error
        return result


# Utility functions
def create_object_pool(
    create_func: Callable[[], Any],
    max_size: int = 10,
    min_size: int = 0,
    max_idle_time: Optional[float] = 60.0,
    validate_func: Optional[Callable[[Any], bool]] = None,
    destroy_func: Optional[Callable[[Any], None]] = None,
    wait_timeout: Optional[float] = 30.0,
    name: str = "ObjectPool"
) -> ObjectPool:
    """
    Create an object pool.
    
    Args:
        create_func: Function to create new objects
        max_size: Maximum pool size
        min_size: Minimum pool size
        max_idle_time: Maximum idle time before object is removed
        validate_func: Function to validate objects
        destroy_func: Function to destroy objects
        wait_timeout: Timeout for waiting for an object
        name: Pool name
    
    Returns:
        ObjectPool instance
    """
    return ObjectPool(
        create_func=create_func,
        max_size=max_size,
        min_size=min_size,
        max_idle_time=max_idle_time,
        validate_func=validate_func,
        destroy_func=destroy_func,
        wait_timeout=wait_timeout,
        name=name
    )


def create_connection_pool(
    create_func: Callable[[], Any],
    max_size: int = 10,
    min_size: int = 0,
    max_idle_time: Optional[float] = 60.0,
    validate_func: Optional[Callable[[Any], bool]] = None,
    destroy_func: Optional[Callable[[Any], None]] = None,
    wait_timeout: Optional[float] = 30.0,
    name: str = "ConnectionPool"
) -> ConnectionPool:
    """
    Create a connection pool.
    
    Args:
        create_func: Function to create new connections
        max_size: Maximum pool size
        min_size: Minimum pool size
        max_idle_time: Maximum idle time before connection is removed
        validate_func: Function to validate connections
        destroy_func: Function to destroy connections
        wait_timeout: Timeout for waiting for a connection
        name: Pool name
    
    Returns:
        ConnectionPool instance
    """
    return ConnectionPool(
        create_func=create_func,
        max_size=max_size,
        min_size=min_size,
        max_idle_time=max_idle_time,
        validate_func=validate_func,
        destroy_func=destroy_func,
        wait_timeout=wait_timeout,
        name=name
    )


def create_thread_pool(
    max_size: int = 10,
    min_size: int = 0,
    target: Optional[Callable] = None,
    name: str = "ThreadPool"
) -> ThreadPool:
    """
    Create a thread pool.
    
    Args:
        max_size: Maximum pool size
        min_size: Minimum pool size
        target: Target function for threads
        name: Pool name
    
    Returns:
        ThreadPool instance
    """
    return ThreadPool(
        max_size=max_size,
        min_size=min_size,
        target=target,
        name=name
    )


# Global object pool registry
_pool_registry: Dict[str, ObjectPool] = {}
_pool_registry_lock = threading.RLock()


def register_pool(name: str, pool: ObjectPool) -> None:
    """Register a pool in the global registry."""
    with _pool_registry_lock:
        _pool_registry[name] = pool


def get_pool(name: str) -> Optional[ObjectPool]:
    """Get a pool from the global registry."""
    with _pool_registry_lock:
        return _pool_registry.get(name)


def close_all_pools() -> None:
    """Close all registered pools."""
    with _pool_registry_lock:
        for pool in _pool_registry.values():
            try:
                pool.close()
            except Exception as e:
                logging.error(f"Error closing pool: {e}")
        _pool_registry.clear()


__all__ = [
    # Enums
    'PoolState',
    
    # Classes
    'PoolStats',
    'PooledObject',
    'ObjectPool',
    'ConnectionPool',
    'ThreadPool',
    
    # Functions
    'create_object_pool',
    'create_connection_pool',
    'create_thread_pool',
    'register_pool',
    'get_pool',
    'close_all_pools',
    
    # Global registry
    '_pool_registry',
    '_pool_registry_lock',
]
