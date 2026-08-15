"""
Swing Bot Timers Module
========================

This module provides timing utilities for the Swing Bot trading system.
Includes timers, intervals, time measurements, and scheduling utilities.
"""

import time
import threading
import asyncio
from typing import Callable, Optional, Any, Dict, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import functools


class TimerState(Enum):
    """Timer states."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"


class TimerType(Enum):
    """Timer types."""
    ONESHOT = "oneshot"  # Single execution
    INTERVAL = "interval"  # Periodic execution
    COUNTDOWN = "countdown"  # Countdown to zero
    DELAYED = "delayed"  # Delayed execution


@dataclass
class TimerStats:
    """Timer statistics."""
    executions: int = 0
    total_elapsed: float = 0.0
    min_elapsed: float = float('inf')
    max_elapsed: float = 0.0
    avg_elapsed: float = 0.0
    last_execution: Optional[datetime] = None
    next_execution: Optional[datetime] = None


class Timer:
    """
    Timer class for executing functions at specified intervals or after delays.
    """
    
    def __init__(
        self,
        interval: float,
        callback: Callable,
        timer_type: TimerType = TimerType.INTERVAL,
        auto_start: bool = False,
        repeat: int = -1,
        name: Optional[str] = None
    ):
        """
        Initialize a timer.
        
        Args:
            interval: Time interval in seconds
            callback: Function to execute
            timer_type: Type of timer (oneshot, interval, countdown, delayed)
            auto_start: Start timer automatically
            repeat: Number of times to repeat (-1 for infinite)
            name: Timer name for identification
        """
        self.interval = interval
        self.callback = callback
        self.timer_type = timer_type
        self.repeat = repeat
        self.name = name or f"Timer_{id(self)}"
        
        self._state = TimerState.IDLE
        self._thread: Optional[threading.Thread] = None
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Start unpaused
        
        self.stats = TimerStats()
        self._start_time: Optional[float] = None
        self._execution_count = 0
        
        if auto_start:
            self.start()
    
    @property
    def state(self) -> TimerState:
        """Get current timer state."""
        return self._state
    
    @property
    def is_running(self) -> bool:
        """Check if timer is running."""
        return self._state == TimerState.RUNNING
    
    @property
    def is_paused(self) -> bool:
        """Check if timer is paused."""
        return self._state == TimerState.PAUSED
    
    @property
    def is_stopped(self) -> bool:
        """Check if timer is stopped."""
        return self._state == TimerState.STOPPED
    
    def start(self) -> 'Timer':
        """Start the timer."""
        with self._lock:
            if self._state == TimerState.RUNNING:
                return self
            if self._state == TimerState.STOPPED:
                # Reset for restart
                self._stop_event.clear()
                self._execution_count = 0
                self.stats = TimerStats()
            
            self._state = TimerState.RUNNING
            self._start_time = time.time()
            self._schedule_next()
        
        return self
    
    def stop(self) -> 'Timer':
        """Stop the timer."""
        with self._lock:
            if self._state == TimerState.STOPPED:
                return self
            
            self._state = TimerState.STOPPED
            self._stop_event.set()
            if self._timer:
                self._timer.cancel()
                self._timer = None
        
        return self
    
    def pause(self) -> 'Timer':
        """Pause the timer."""
        with self._lock:
            if self._state != TimerState.RUNNING:
                return self
            
            self._state = TimerState.PAUSED
            self._pause_event.clear()
            if self._timer:
                self._timer.cancel()
                self._timer = None
        
        return self
    
    def resume(self) -> 'Timer':
        """Resume the timer."""
        with self._lock:
            if self._state != TimerState.PAUSED:
                return self
            
            self._state = TimerState.RUNNING
            self._pause_event.set()
            self._schedule_next()
        
        return self
    
    def reset(self) -> 'Timer':
        """Reset the timer."""
        with self._lock:
            self.stop()
            self._execution_count = 0
            self.stats = TimerStats()
            self._start_time = None
            self._stop_event.clear()
            if self.timer_type != TimerType.ONESHOT:
                self.start()
        
        return self
    
    def _schedule_next(self) -> None:
        """Schedule the next execution."""
        with self._lock:
            if self._state != TimerState.RUNNING:
                return
            
            # Check if we've reached the repeat limit
            if self.repeat > 0 and self._execution_count >= self.repeat:
                self._state = TimerState.COMPLETED
                return
            
            # Schedule the next execution
            self._timer = threading.Timer(self.interval, self._execute)
            self._timer.daemon = True
            self._timer.start()
            
            # Calculate next execution time
            self.stats.next_execution = datetime.now() + timedelta(seconds=self.interval)
    
    def _execute(self) -> None:
        """Execute the callback."""
        # Check if we should execute
        if self._state != TimerState.RUNNING:
            return
        
        # Check if paused
        if not self._pause_event.is_set():
            # Reschedule if paused
            self._schedule_next()
            return
        
        # Execute callback
        try:
            start = time.time()
            if asyncio.iscoroutinefunction(self.callback):
                # Run async callback
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.callback())
                else:
                    loop.run_until_complete(self.callback())
            else:
                # Run sync callback
                self.callback()
            
            elapsed = time.time() - start
            
            # Update stats
            with self._lock:
                self._execution_count += 1
                self.stats.executions = self._execution_count
                self.stats.total_elapsed += elapsed
                self.stats.min_elapsed = min(self.stats.min_elapsed, elapsed)
                self.stats.max_elapsed = max(self.stats.max_elapsed, elapsed)
                self.stats.avg_elapsed = self.stats.total_elapsed / self._execution_count
                self.stats.last_execution = datetime.now()
                
        except Exception as e:
            # Log error and continue
            print(f"Timer {self.name} callback error: {e}")
        
        # Schedule next execution
        with self._lock:
            if self._state == TimerState.RUNNING:
                self._schedule_next()
    
    def get_elapsed(self) -> float:
        """Get elapsed time since timer started."""
        if self._start_time is None:
            return 0.0
        if self._state == TimerState.PAUSED:
            return self._start_time - time.time()  # Not accurate when paused
        return time.time() - self._start_time
    
    def get_stats(self) -> TimerStats:
        """Get timer statistics."""
        return self.stats
    
    def __repr__(self) -> str:
        return f"Timer(name={self.name}, state={self._state.value}, interval={self.interval}, executions={self._execution_count})"


class TimerManager:
    """
    Manager for multiple timers.
    """
    
    def __init__(self):
        self._timers: Dict[str, Timer] = {}
        self._lock = threading.Lock()
    
    def create_timer(
        self,
        name: str,
        interval: float,
        callback: Callable,
        timer_type: TimerType = TimerType.INTERVAL,
        auto_start: bool = False,
        repeat: int = -1
    ) -> Timer:
        """Create and register a new timer."""
        with self._lock:
            if name in self._timers:
                raise ValueError(f"Timer with name '{name}' already exists")
            
            timer = Timer(
                interval=interval,
                callback=callback,
                timer_type=timer_type,
                auto_start=auto_start,
                repeat=repeat,
                name=name
            )
            self._timers[name] = timer
            return timer
    
    def get_timer(self, name: str) -> Optional[Timer]:
        """Get a timer by name."""
        with self._lock:
            return self._timers.get(name)
    
    def start_timer(self, name: str) -> Optional[Timer]:
        """Start a timer by name."""
        timer = self.get_timer(name)
        if timer:
            timer.start()
        return timer
    
    def stop_timer(self, name: str) -> Optional[Timer]:
        """Stop a timer by name."""
        timer = self.get_timer(name)
        if timer:
            timer.stop()
        return timer
    
    def pause_timer(self, name: str) -> Optional[Timer]:
        """Pause a timer by name."""
        timer = self.get_timer(name)
        if timer:
            timer.pause()
        return timer
    
    def resume_timer(self, name: str) -> Optional[Timer]:
        """Resume a timer by name."""
        timer = self.get_timer(name)
        if timer:
            timer.resume()
        return timer
    
    def remove_timer(self, name: str) -> bool:
        """Remove a timer by name."""
        with self._lock:
            timer = self._timers.get(name)
            if timer:
                timer.stop()
                del self._timers[name]
                return True
            return False
    
    def stop_all(self) -> None:
        """Stop all timers."""
        with self._lock:
            for timer in self._timers.values():
                timer.stop()
    
    def start_all(self) -> None:
        """Start all timers."""
        with self._lock:
            for timer in self._timers.values():
                if timer.state == TimerState.IDLE:
                    timer.start()
    
    def get_all_stats(self) -> Dict[str, TimerStats]:
        """Get statistics for all timers."""
        with self._lock:
            return {name: timer.get_stats() for name, timer in self._timers.items()}
    
    def get_timer_names(self) -> List[str]:
        """Get list of all timer names."""
        with self._lock:
            return list(self._timers.keys())
    
    def get_timers_by_state(self, state: TimerState) -> List[Timer]:
        """Get timers by state."""
        with self._lock:
            return [timer for timer in self._timers.values() if timer.state == state]


# Global timer manager instance
timer_manager = TimerManager()


# Utility functions
def create_interval_timer(
    name: str,
    interval: float,
    callback: Callable,
    auto_start: bool = True,
    repeat: int = -1
) -> Timer:
    """Create an interval timer."""
    return timer_manager.create_timer(
        name=name,
        interval=interval,
        callback=callback,
        timer_type=TimerType.INTERVAL,
        auto_start=auto_start,
        repeat=repeat
    )


def create_delayed_timer(
    name: str,
    delay: float,
    callback: Callable,
    auto_start: bool = True
) -> Timer:
    """Create a delayed timer."""
    return timer_manager.create_timer(
        name=name,
        interval=delay,
        callback=callback,
        timer_type=TimerType.DELAYED,
        auto_start=auto_start,
        repeat=1
    )


def create_countdown_timer(
    name: str,
    duration: float,
    callback: Callable,
    auto_start: bool = True,
    interval: float = 1.0
) -> Timer:
    """Create a countdown timer."""
    def countdown_callback():
        # This will be called at each interval
        pass
    
    timer = timer_manager.create_timer(
        name=name,
        interval=interval,
        callback=countdown_callback,
        timer_type=TimerType.COUNTDOWN,
        auto_start=auto_start,
        repeat=int(duration / interval)
    )
    timer.callback = callback  # Override callback
    return timer


def time_function(func: Callable) -> Callable:
    """
    Decorator to measure function execution time.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        # Could log or store this
        return result
    return wrapper


async def async_time_function(func: Callable) -> Callable:
    """
    Decorator to measure async function execution time.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        elapsed = time.time() - start
        # Could log or store this
        return result
    return wrapper


def sleep_until(target_time: datetime) -> None:
    """
    Sleep until a specific time.
    
    Args:
        target_time: Target datetime to sleep until
    """
    now = datetime.now()
    if target_time <= now:
        return
    diff = (target_time - now).total_seconds()
    time.sleep(diff)


async def async_sleep_until(target_time: datetime) -> None:
    """
    Async sleep until a specific time.
    
    Args:
        target_time: Target datetime to sleep until
    """
    now = datetime.now()
    if target_time <= now:
        return
    diff = (target_time - now).total_seconds()
    await asyncio.sleep(diff)


def get_timestamp() -> str:
    """Get current timestamp as string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")


def measure_time(func: Callable) -> Dict[str, Any]:
    """
    Measure execution time and return results.
    
    Args:
        func: Function to measure
        
    Returns:
        Dictionary with execution time and result
    """
    start = time.perf_counter()
    result = func()
    elapsed = time.perf_counter() - start
    
    return {
        'result': result,
        'elapsed_seconds': elapsed,
        'elapsed_ms': elapsed * 1000,
        'elapsed_micros': elapsed * 1000000
    }


# Export all public classes and functions
__all__ = [
    'TimerState',
    'TimerType',
    'TimerStats',
    'Timer',
    'TimerManager',
    'timer_manager',
    'create_interval_timer',
    'create_delayed_timer',
    'create_countdown_timer',
    'time_function',
    'async_time_function',
    'sleep_until',
    'async_sleep_until',
    'get_timestamp',
    'measure_time',
]
