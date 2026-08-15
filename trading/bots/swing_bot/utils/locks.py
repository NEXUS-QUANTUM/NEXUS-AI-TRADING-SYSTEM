"""
Swing Bot Locks Module
=======================

This module provides locking utilities for the Swing Bot trading system.
Includes distributed locks, thread locks, and concurrency control utilities.
"""

import threading
import time
import asyncio
import uuid
from typing import Any, Optional, Callable, Dict, List, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import redis
from contextlib import contextmanager


class LockState(Enum):
    """Lock states."""
    ACQUIRED = "acquired"
    RELEASED = "released"
    TIMEOUT = "timeout"
    ERROR = "error"


class LockType(Enum):
    """Lock types."""
    THREAD = "thread"
    PROCESS = "process"
    DISTRIBUTED = "distributed"
    READ_WRITE = "read_write"
    SEMAPHORE = "semaphore"
    REENTRANT = "reentrant"


@dataclass
class LockStats:
    """Lock statistics."""
    acquires: int = 0
    releases: int = 0
    timeouts: int = 0
    errors: int = 0
    avg_hold_time: float = 0.0
    max_hold_time: float = 0.0
    min_hold_time: float = float('inf')
    current_holders: int = 0
    contention_count: int = 0


class ThreadLock:
    """
    Thread-safe lock implementation.
    """
    
    def __init__(self, name: str = "ThreadLock", reentrant: bool = True):
        """
        Initialize a thread lock.
        
        Args:
            name: Lock name
            reentrant: Whether the lock is reentrant
        """
        self.name = name
        self.reentrant = reentrant
        self._lock = threading.RLock() if reentrant else threading.Lock()
        self._stats = LockStats()
        self._owner: Optional[int] = None
        self._recursion_depth = 0
    
    def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """
        Acquire the lock.
        
        Args:
            blocking: Whether to block
            timeout: Timeout in seconds
        
        Returns:
            True if acquired, False otherwise
        """
        start_time = time.time()
        try:
            acquired = self._lock.acquire(blocking=blocking, timeout=timeout)
            if acquired:
                self._stats.acquires += 1
                self._stats.current_holders += 1
                
                # Track owner for reentrant locks
                if self.reentrant:
                    if self._owner is None:
                        self._owner = threading.get_ident()
                    self._recursion_depth += 1
                
                # Track hold time
                hold_time = time.time() - start_time
                self._stats.avg_hold_time = (
                    (self._stats.avg_hold_time * (self._stats.acquires - 1) + hold_time)
                    / max(1, self._stats.acquires)
                )
                self._stats.max_hold_time = max(self._stats.max_hold_time, hold_time)
                self._stats.min_hold_time = min(self._stats.min_hold_time, hold_time)
            else:
                self._stats.timeouts += 1
            return acquired
        except Exception as e:
            self._stats.errors += 1
            logging.error(f"Lock {self.name} acquire error: {e}")
            return False
    
    def release(self) -> None:
        """Release the lock."""
        try:
            if self.reentrant and self._owner == threading.get_ident():
                self._recursion_depth -= 1
                if self._recursion_depth <= 0:
                    self._owner = None
                    self._stats.current_holders -= 1
            self._lock.release()
            self._stats.releases += 1
        except Exception as e:
            self._stats.errors += 1
            logging.error(f"Lock {self.name} release error: {e}")
    
    def locked(self) -> bool:
        """Check if the lock is currently held."""
        if self.reentrant:
            return self._lock.acquire(blocking=False)
        return self._lock.locked()
    
    def get_stats(self) -> LockStats:
        """Get lock statistics."""
        return self._stats
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class ReadWriteLock:
    """
    Read-write lock implementation.
    """
    
    def __init__(self, name: str = "ReadWriteLock"):
        """
        Initialize a read-write lock.
        
        Args:
            name: Lock name
        """
        self.name = name
        self._read_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._readers = 0
        self._stats = LockStats()
    
    def acquire_read(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """Acquire a read lock."""
        start_time = time.time()
        try:
            if self._read_lock.acquire(blocking=blocking, timeout=timeout):
                self._readers += 1
                self._read_lock.release()
                self._stats.acquires += 1
                self._stats.current_holders += 1
                return True
            self._stats.timeouts += 1
            return False
        except Exception as e:
            self._stats.errors += 1
            logging.error(f"ReadWriteLock {self.name} acquire_read error: {e}")
            return False
    
    def acquire_write(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """Acquire a write lock."""
        start_time = time.time()
        try:
            acquired = self._write_lock.acquire(blocking=blocking, timeout=timeout)
            if acquired:
                # Wait for all readers to finish
                while self._readers > 0:
                    time.sleep(0.001)
                self._stats.acquires += 1
                self._stats.current_holders += 1
            else:
                self._stats.timeouts += 1
            return acquired
        except Exception as e:
            self._stats.errors += 1
            logging.error(f"ReadWriteLock {self.name} acquire_write error: {e}")
            return False
    
    def release_read(self) -> None:
        """Release a read lock."""
        try:
            with self._read_lock:
                self._readers -= 1
                if self._readers < 0:
                    self._readers = 0
            self._stats.releases += 1
            self._stats.current_holders -= 1
        except Exception as e:
            self._stats.errors += 1
            logging.error(f"ReadWriteLock {self.name} release_read error: {e}")
    
    def release_write(self) -> None:
        """Release a write lock."""
        try:
            self._write_lock.release()
            self._stats.releases += 1
            self._stats.current_holders -= 1
        except Exception as e:
            self._stats.errors += 1
            logging.error(f"ReadWriteLock {self.name} release_write error: {e}")
    
    def get_stats(self) -> LockStats:
        """Get lock statistics."""
        return self._stats


class Semaphore:
    """
    Semaphore implementation.
    """
    
    def __init__(self, value: int = 1, name: str = "Semaphore"):
        """
        Initialize a semaphore.
        
        Args:
            value: Initial semaphore value
            name: Semaphore name
        """
        self.name = name
        self._semaphore = threading.Semaphore(value)
        self._stats = LockStats()
        self._value = value
    
    def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """Acquire the semaphore."""
        start_time = time.time()
        try:
            acquired = self._semaphore.acquire(blocking=blocking, timeout=timeout)
            if acquired:
                self._stats.acquires += 1
                self._stats.current_holders += 1
                self._value -= 1
                hold_time = time.time() - start_time
                self._stats.avg_hold_time = (
                    (self._stats.avg_hold_time * (self._stats.acquires - 1) + hold_time)
                    / max(1, self._stats.acquires)
                )
                self._stats.max_hold_time = max(self._stats.max_hold_time, hold_time)
                self._stats.min_hold_time = min(self._stats.min_hold_time, hold_time)
            else:
                self._stats.timeouts += 1
            return acquired
        except Exception as e:
            self._stats.errors += 1
            logging.error(f"Semaphore {self.name} acquire error: {e}")
            return False
    
    def release(self) -> None:
        """Release the semaphore."""
        try:
            self._semaphore.release()
            self._value += 1
            self._stats.releases += 1
            self._stats.current_holders -= 1
        except Exception as e:
            self._stats.errors += 1
            logging.error(f"Semaphore {self.name} release error: {e}")
    
    def get_value(self) -> int:
        """Get the current semaphore value."""
        return self._value
    
    def get_stats(self) -> LockStats:
        """Get semaphore statistics."""
        return self._stats


class DistributedLock:
    """
    Distributed lock using Redis.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        key: str,
        timeout: float = 10.0,
        retry_interval: float = 0.1,
        name: str = "DistributedLock"
    ):
        """
        Initialize a distributed lock.
        
        Args:
            redis_client: Redis client
            key: Lock key
            timeout: Lock timeout in seconds
            retry_interval: Retry interval in seconds
            name: Lock name
        """
        self.redis = redis_client
        self.key = f"lock:{key}"
        self.timeout = timeout
        self.retry_interval = retry_interval
        self.name = name
        self._token: Optional[str] = None
        self._stats = LockStats()
        self._acquired = False
    
    def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """
        Acquire the distributed lock.
        
        Args:
            blocking: Whether to block
            timeout: Timeout in seconds
        
        Returns:
            True if acquired, False otherwise
        """
        start_time = time.time()
        timeout = timeout or self.timeout
        token = str(uuid.uuid4())
        
        while True:
            try:
                if self.redis.set(self.key, token, nx=True, ex=int(self.timeout)):
                    self._token = token
                    self._acquired = True
                    self._stats.acquires += 1
                    self._stats.current_holders += 1
                    return True
                
                if not blocking:
                    self._stats.timeouts += 1
                    return False
                
                if timeout is not None and time.time() - start_time >= timeout:
                    self._stats.timeouts += 1
                    return False
                
                time.sleep(self.retry_interval)
            except Exception as e:
                self._stats.errors += 1
                logging.error(f"DistributedLock {self.name} acquire error: {e}")
                return False
    
    def release(self) -> bool:
        """Release the distributed lock."""
        if not self._acquired or self._token is None:
            return False
        
        try:
            # Use Lua script to ensure atomicity
            lua_script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
            """
            result = self.redis.eval(lua_script, 1, self.key, self._token)
            if result:
                self._acquired = False
                self._token = None
                self._stats.releases += 1
                self._stats.current_holders -= 1
                return True
            return False
        except Exception as e:
            self._stats.errors += 1
            logging.error(f"DistributedLock {self.name} release error: {e}")
            return False
    
    def renew(self, timeout: Optional[float] = None) -> bool:
        """
        Renew the lock.
        
        Args:
            timeout: New timeout in seconds
        
        Returns:
            True if renewed, False otherwise
        """
        if not self._acquired or self._token is None:
            return False
        
        timeout = timeout or self.timeout
        try:
            lua_script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("expire", KEYS[1], ARGV[2])
                else
                    return 0
                end
            """
            result = self.redis.eval(lua_script, 1, self.key, self._token, int(timeout))
            return bool(result)
        except Exception as e:
            self._stats.errors += 1
            logging.error(f"DistributedLock {self.name} renew error: {e}")
            return False
    
    def is_locked(self) -> bool:
        """Check if the lock is held."""
        try:
            return self.redis.exists(self.key) > 0
        except Exception:
            return False
    
    def get_stats(self) -> LockStats:
        """Get lock statistics."""
        return self._stats
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class LockManager:
    """
    Manager for locks.
    """
    
    def __init__(self):
        self._locks: Dict[str, Union[ThreadLock, ReadWriteLock, Semaphore, DistributedLock]] = {}
        self._lock = threading.Lock()
    
    def create_thread_lock(self, name: str, reentrant: bool = True) -> ThreadLock:
        """Create a thread lock."""
        with self._lock:
            if name in self._locks:
                raise ValueError(f"Lock '{name}' already exists")
            lock = ThreadLock(name, reentrant)
            self._locks[name] = lock
            return lock
    
    def create_read_write_lock(self, name: str) -> ReadWriteLock:
        """Create a read-write lock."""
        with self._lock:
            if name in self._locks:
                raise ValueError(f"Lock '{name}' already exists")
            lock = ReadWriteLock(name)
            self._locks[name] = lock
            return lock
    
    def create_semaphore(self, name: str, value: int = 1) -> Semaphore:
        """Create a semaphore."""
        with self._lock:
            if name in self._locks:
                raise ValueError(f"Lock '{name}' already exists")
            semaphore = Semaphore(value, name)
            self._locks[name] = semaphore
            return semaphore
    
    def create_distributed_lock(self, name: str, redis_client: redis.Redis, key: str, timeout: float = 10.0) -> DistributedLock:
        """Create a distributed lock."""
        with self._lock:
            if name in self._locks:
                raise ValueError(f"Lock '{name}' already exists")
            lock = DistributedLock(redis_client, key, timeout, name=name)
            self._locks[name] = lock
            return lock
    
    def get_lock(self, name: str) -> Optional[Union[ThreadLock, ReadWriteLock, Semaphore, DistributedLock]]:
        """Get a lock by name."""
        with self._lock:
            return self._locks.get(name)
    
    def remove_lock(self, name: str) -> bool:
        """Remove a lock."""
        with self._lock:
            if name in self._locks:
                del self._locks[name]
                return True
            return False
    
    def get_all_stats(self) -> Dict[str, LockStats]:
        """Get statistics for all locks."""
        with self._lock:
            return {name: lock.get_stats() for name, lock in self._locks.items()}
    
    def get_lock_names(self) -> List[str]:
        """Get list of all lock names."""
        with self._lock:
            return list(self._locks.keys())


# Global lock manager
lock_manager = LockManager()


# Utility functions
@contextmanager
def acquire_lock(lock, blocking: bool = True, timeout: Optional[float] = None):
    """
    Context manager for acquiring a lock.
    
    Args:
        lock: Lock object
        blocking: Whether to block
        timeout: Timeout in seconds
    
    Yields:
        Lock object
    """
    acquired = lock.acquire(blocking=blocking, timeout=timeout)
    if not acquired:
        raise RuntimeError(f"Could not acquire lock: {lock.name}")
    try:
        yield lock
    finally:
        lock.release()


@contextmanager
def acquire_read_lock(lock: ReadWriteLock):
    """Context manager for acquiring a read lock."""
    lock.acquire_read()
    try:
        yield
    finally:
        lock.release_read()


@contextmanager
def acquire_write_lock(lock: ReadWriteLock):
    """Context manager for acquiring a write lock."""
    lock.acquire_write()
    try:
        yield
    finally:
        lock.release_write()


def synchronized(lock_name: str, wait_timeout: Optional[float] = None):
    """
    Decorator for synchronizing a function with a lock.
    
    Args:
        lock_name: Name of the lock
        wait_timeout: Timeout for acquiring the lock
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            lock = lock_manager.get_lock(lock_name)
            if lock is None:
                lock = lock_manager.create_thread_lock(lock_name)
            
            with acquire_lock(lock, timeout=wait_timeout):
                return func(*args, **kwargs)
        return wrapper
    return decorator


__all__ = [
    # Enums
    'LockState',
    'LockType',
    
    # Classes
    'LockStats',
    'ThreadLock',
    'ReadWriteLock',
    'Semaphore',
    'DistributedLock',
    'LockManager',
    
    # Functions
    'acquire_lock',
    'acquire_read_lock',
    'acquire_write_lock',
    'synchronized',
    
    # Global instance
    'lock_manager',
]
