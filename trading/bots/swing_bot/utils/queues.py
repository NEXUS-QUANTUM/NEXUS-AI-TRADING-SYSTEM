"""
Swing Bot Queues Module
========================

This module provides queue utilities for the Swing Bot trading system.
Includes queue implementations, priority queues, and queue management utilities.
"""

import queue
import threading
import asyncio
import time
import heapq
from typing import Any, Callable, Optional, List, Dict, Union, Tuple, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
import logging


class QueueType(Enum):
    """Queue types."""
    FIFO = "fifo"  # First In, First Out
    LIFO = "lifo"  # Last In, First Out
    PRIORITY = "priority"  # Priority-based
    DELAYED = "delayed"  # Delayed execution


class QueueState(Enum):
    """Queue states."""
    ACTIVE = "active"
    PAUSED = "paused"
    DRAINING = "draining"
    CLOSED = "closed"


@dataclass
class QueueStats:
    """Queue statistics."""
    size: int = 0
    max_size: int = 0
    total_enqueued: int = 0
    total_dequeued: int = 0
    total_processed: int = 0
    total_errors: int = 0
    avg_processing_time: float = 0.0
    max_processing_time: float = 0.0
    min_processing_time: float = float('inf')
    last_processed: Optional[float] = None


class QueueItem(Generic[Any]):
    """Generic queue item."""
    
    def __init__(self, data: Any, priority: int = 0, delay: float = 0.0):
        self.data = data
        self.priority = priority
        self.delay = delay
        self.enqueue_time = time.time()
        self.process_time: Optional[float] = None
    
    def is_ready(self) -> bool:
        """Check if the item is ready for processing."""
        if self.delay <= 0:
            return True
        return time.time() - self.enqueue_time >= self.delay
    
    def __lt__(self, other: 'QueueItem'):
        return self.priority < other.priority


class BaseQueue:
    """Base queue class."""
    
    def __init__(self, maxsize: int = 0, queue_type: QueueType = QueueType.FIFO):
        self.maxsize = maxsize
        self.queue_type = queue_type
        self._state = QueueState.ACTIVE
        self._lock = threading.RLock()
        self._stats = QueueStats(maxsize=maxsize)
        self._item_condition = threading.Condition(self._lock)
        self._closed = False
    
    @property
    def state(self) -> QueueState:
        return self._state
    
    @property
    def stats(self) -> QueueStats:
        with self._lock:
            return self._stats
    
    @property
    def size(self) -> int:
        raise NotImplementedError
    
    @property
    def empty(self) -> bool:
        raise NotImplementedError
    
    @property
    def full(self) -> bool:
        return self.maxsize > 0 and self.size >= self.maxsize
    
    def put(self, item: Any, priority: int = 0, delay: float = 0.0, block: bool = True, timeout: Optional[float] = None) -> None:
        """Put an item into the queue."""
        if self._closed:
            raise queue.Closed("Queue is closed")
        
        if self.full:
            if not block:
                raise queue.Full
            if timeout is not None:
                # Wait for space
                start = time.time()
                while self.full:
                    if time.time() - start >= timeout:
                        raise queue.Full
                    time.sleep(0.01)
            else:
                while self.full:
                    time.sleep(0.01)
        
        queue_item = QueueItem(item, priority, delay)
        self._do_put(queue_item)
        
        with self._lock:
            self._stats.total_enqueued += 1
            self._stats.size = self.size
        
        with self._item_condition:
            self._item_condition.notify()
    
    def put_nowait(self, item: Any, priority: int = 0, delay: float = 0.0) -> None:
        """Put an item without blocking."""
        self.put(item, priority, delay, block=False)
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        """Get an item from the queue."""
        if self._state == QueueState.CLOSED and self.empty:
            raise queue.Empty
        
        start = time.time()
        while True:
            if not block and (self._state == QueueState.CLOSED or self.empty):
                raise queue.Empty
            
            if not self.empty:
                item = self._do_get()
                if item and item.is_ready():
                    item.process_time = time.time()
                    with self._lock:
                        self._stats.total_dequeued += 1
                        self._stats.size = self.size
                        processing_time = item.process_time - item.enqueue_time
                        self._stats.last_processed = processing_time
                        self._stats.avg_processing_time = (
                            (self._stats.avg_processing_time * (self._stats.total_processed - 1) + processing_time)
                            / max(1, self._stats.total_processed)
                        )
                        self._stats.max_processing_time = max(self._stats.max_processing_time, processing_time)
                        self._stats.min_processing_time = min(self._stats.min_processing_time, processing_time)
                    return item.data
                else:
                    # Wait for item to be ready or for more items
                    if timeout is not None and time.time() - start >= timeout:
                        raise queue.Empty
            
            # Wait for items
            if block:
                with self._item_condition:
                    self._item_condition.wait(timeout=0.1)
            else:
                raise queue.Empty
    
    def get_nowait(self) -> Any:
        """Get an item without blocking."""
        return self.get(block=False)
    
    def _do_put(self, item: QueueItem) -> None:
        """Internal put implementation."""
        raise NotImplementedError
    
    def _do_get(self) -> Optional[QueueItem]:
        """Internal get implementation."""
        raise NotImplementedError
    
    def clear(self) -> None:
        """Clear all items from the queue."""
        raise NotImplementedError
    
    def close(self) -> None:
        """Close the queue."""
        self._closed = True
        self._state = QueueState.CLOSED


class FIFOQueue(BaseQueue):
    """First-In-First-Out queue."""
    
    def __init__(self, maxsize: int = 0):
        super().__init__(maxsize, QueueType.FIFO)
        self._queue: List[QueueItem] = []
    
    @property
    def size(self) -> int:
        return len(self._queue)
    
    @property
    def empty(self) -> bool:
        return len(self._queue) == 0
    
    def _do_put(self, item: QueueItem) -> None:
        self._queue.append(item)
    
    def _do_get(self) -> Optional[QueueItem]:
        if not self._queue:
            return None
        return self._queue.pop(0)
    
    def clear(self) -> None:
        with self._lock:
            self._queue.clear()


class LIFOQueue(BaseQueue):
    """Last-In-First-Out queue."""
    
    def __init__(self, maxsize: int = 0):
        super().__init__(maxsize, QueueType.LIFO)
        self._queue: List[QueueItem] = []
    
    @property
    def size(self) -> int:
        return len(self._queue)
    
    @property
    def empty(self) -> bool:
        return len(self._queue) == 0
    
    def _do_put(self, item: QueueItem) -> None:
        self._queue.append(item)
    
    def _do_get(self) -> Optional[QueueItem]:
        if not self._queue:
            return None
        return self._queue.pop()
    
    def clear(self) -> None:
        with self._lock:
            self._queue.clear()


class PriorityQueue(BaseQueue):
    """Priority-based queue."""
    
    def __init__(self, maxsize: int = 0):
        super().__init__(maxsize, QueueType.PRIORITY)
        self._queue: List[Tuple[int, int, QueueItem]] = []
        self._counter = 0
    
    @property
    def size(self) -> int:
        return len(self._queue)
    
    @property
    def empty(self) -> bool:
        return len(self._queue) == 0
    
    def _do_put(self, item: QueueItem) -> None:
        heapq.heappush(self._queue, (item.priority, self._counter, item))
        self._counter += 1
    
    def _do_get(self) -> Optional[QueueItem]:
        if not self._queue:
            return None
        return heapq.heappop(self._queue)[2]
    
    def clear(self) -> None:
        with self._lock:
            self._queue.clear()
            self._counter = 0


class DelayedQueue(BaseQueue):
    """Delayed execution queue."""
    
    def __init__(self, maxsize: int = 0):
        super().__init__(maxsize, QueueType.DELAYED)
        self._queue: List[QueueItem] = []
        self._ready_queue: List[QueueItem] = []
    
    @property
    def size(self) -> int:
        return len(self._queue) + len(self._ready_queue)
    
    @property
    def empty(self) -> bool:
        return len(self._queue) == 0 and len(self._ready_queue) == 0
    
    def _do_put(self, item: QueueItem) -> None:
        self._queue.append(item)
        # Check if any items are ready
        self._process_ready()
    
    def _do_get(self) -> Optional[QueueItem]:
        # Process ready items
        self._process_ready()
        if not self._ready_queue:
            return None
        return self._ready_queue.pop(0)
    
    def _process_ready(self) -> None:
        """Move ready items from delayed queue to ready queue."""
        now = time.time()
        remaining = []
        for item in self._queue:
            if item.is_ready():
                self._ready_queue.append(item)
            else:
                remaining.append(item)
        self._queue = remaining
    
    def clear(self) -> None:
        with self._lock:
            self._queue.clear()
            self._ready_queue.clear()


class QueueManager:
    """
    Manager for multiple queues.
    """
    
    def __init__(self):
        self._queues: Dict[str, BaseQueue] = {}
        self._lock = threading.RLock()
    
    def create_queue(
        self,
        name: str,
        queue_type: QueueType = QueueType.FIFO,
        maxsize: int = 0,
    ) -> BaseQueue:
        """Create a new queue."""
        with self._lock:
            if name in self._queues:
                raise ValueError(f"Queue '{name}' already exists")
            
            queue_classes = {
                QueueType.FIFO: FIFOQueue,
                QueueType.LIFO: LIFOQueue,
                QueueType.PRIORITY: PriorityQueue,
                QueueType.DELAYED: DelayedQueue,
            }
            
            queue_class = queue_classes.get(queue_type)
            if queue_class is None:
                raise ValueError(f"Unknown queue type: {queue_type}")
            
            queue = queue_class(maxsize=maxsize)
            self._queues[name] = queue
            return queue
    
    def get_queue(self, name: str) -> Optional[BaseQueue]:
        """Get a queue by name."""
        with self._lock:
            return self._queues.get(name)
    
    def remove_queue(self, name: str) -> bool:
        """Remove a queue."""
        with self._lock:
            if name in self._queues:
                self._queues[name].close()
                del self._queues[name]
                return True
            return False
    
    def clear_queue(self, name: str) -> bool:
        """Clear a queue."""
        with self._lock:
            queue = self._queues.get(name)
            if queue:
                queue.clear()
                return True
            return False
    
    def get_all_stats(self) -> Dict[str, QueueStats]:
        """Get statistics for all queues."""
        with self._lock:
            return {name: queue.stats for name, queue in self._queues.items()}
    
    def get_queue_names(self) -> List[str]:
        """Get list of all queue names."""
        with self._lock:
            return list(self._queues.keys())
    
    def close_all(self) -> None:
        """Close all queues."""
        with self._lock:
            for queue in self._queues.values():
                queue.close()


class AsyncQueue:
    """
    Asynchronous queue for async operations.
    """
    
    def __init__(self, maxsize: int = 0):
        self._queue = asyncio.Queue(maxsize)
        self._stats = QueueStats(maxsize=maxsize)
        self._lock = asyncio.Lock()
        self._closed = False
    
    @property
    def size(self) -> int:
        return self._queue.qsize()
    
    @property
    def empty(self) -> bool:
        return self._queue.empty()
    
    @property
    def full(self) -> bool:
        return self._queue.full()
    
    @property
    def stats(self) -> QueueStats:
        return self._stats
    
    async def put(self, item: Any, priority: int = 0, delay: float = 0.0) -> None:
        """Put an item into the queue."""
        if self._closed:
            raise queue.Closed("Queue is closed")
        
        queue_item = QueueItem(item, priority, delay)
        await self._queue.put(queue_item)
        
        async with self._lock:
            self._stats.total_enqueued += 1
            self._stats.size = self.size
    
    def put_nowait(self, item: Any, priority: int = 0, delay: float = 0.0) -> None:
        """Put an item without blocking."""
        if self._closed:
            raise queue.Closed("Queue is closed")
        
        queue_item = QueueItem(item, priority, delay)
        self._queue.put_nowait(queue_item)
        
        self._stats.total_enqueued += 1
        self._stats.size = self.size
    
    async def get(self) -> Any:
        """Get an item from the queue."""
        if self._closed and self._queue.empty():
            raise queue.Empty
        
        queue_item = await self._queue.get()
        queue_item.process_time = time.time()
        
        async with self._lock:
            self._stats.total_dequeued += 1
            self._stats.size = self.size
            processing_time = queue_item.process_time - queue_item.enqueue_time
            self._stats.last_processed = processing_time
            self._stats.avg_processing_time = (
                (self._stats.avg_processing_time * (self._stats.total_processed - 1) + processing_time)
                / max(1, self._stats.total_processed)
            )
            self._stats.max_processing_time = max(self._stats.max_processing_time, processing_time)
            self._stats.min_processing_time = min(self._stats.min_processing_time, processing_time)
        
        return queue_item.data
    
    def get_nowait(self) -> Any:
        """Get an item without blocking."""
        if self._closed and self._queue.empty():
            raise queue.Empty
        
        queue_item = self._queue.get_nowait()
        queue_item.process_time = time.time()
        
        self._stats.total_dequeued += 1
        self._stats.size = self.size
        processing_time = queue_item.process_time - queue_item.enqueue_time
        self._stats.last_processed = processing_time
        self._stats.avg_processing_time = (
            (self._stats.avg_processing_time * (self._stats.total_processed - 1) + processing_time)
            / max(1, self._stats.total_processed)
        )
        self._stats.max_processing_time = max(self._stats.max_processing_time, processing_time)
        self._stats.min_processing_time = min(self._stats.min_processing_time, processing_time)
        
        return queue_item.data
    
    def task_done(self) -> None:
        """Mark a task as done."""
        self._queue.task_done()
        self._stats.total_processed += 1
    
    async def join(self) -> None:
        """Wait for all tasks to complete."""
        await self._queue.join()
    
    def close(self) -> None:
        """Close the queue."""
        self._closed = True
    
    def clear(self) -> None:
        """Clear all items from the queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break
        self._stats.size = 0


# Utility functions
def create_queue(queue_type: QueueType = QueueType.FIFO, maxsize: int = 0) -> BaseQueue:
    """
    Create a queue of the specified type.
    
    Args:
        queue_type: Type of queue to create
        maxsize: Maximum queue size
    
    Returns:
        Queue instance
    """
    queue_classes = {
        QueueType.FIFO: FIFOQueue,
        QueueType.LIFO: LIFOQueue,
        QueueType.PRIORITY: PriorityQueue,
        QueueType.DELAYED: DelayedQueue,
    }
    
    queue_class = queue_classes.get(queue_type)
    if queue_class is None:
        raise ValueError(f"Unknown queue type: {queue_type}")
    
    return queue_class(maxsize=maxsize)


def create_async_queue(maxsize: int = 0) -> AsyncQueue:
    """
    Create an asynchronous queue.
    
    Args:
        maxsize: Maximum queue size
    
    Returns:
        AsyncQueue instance
    """
    return AsyncQueue(maxsize=maxsize)


# Global queue manager
queue_manager = QueueManager()


__all__ = [
    # Enums
    'QueueType',
    'QueueState',
    
    # Classes
    'QueueStats',
    'QueueItem',
    'BaseQueue',
    'FIFOQueue',
    'LIFOQueue',
    'PriorityQueue',
    'DelayedQueue',
    'QueueManager',
    'AsyncQueue',
    
    # Functions
    'create_queue',
    'create_async_queue',
    
    # Global instance
    'queue_manager',
]
