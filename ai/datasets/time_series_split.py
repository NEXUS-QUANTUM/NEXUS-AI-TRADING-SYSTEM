"""
NEXUS AI TRADING SYSTEM - Time Series Split
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Time Series Split system with:
- Multiple split methods (Walk-Forward, Expanding Window, Rolling Window)
- Train/Validation/Test splits
- Cross-validation for time series
- Purged cross-validation
- Gap handling
- Time-based splits
- Sequential splits
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator
from sklearn.model_selection import TimeSeriesSplit

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import SplitError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class SplitMethod(str, Enum):
    """Split methods"""
    WALK_FORWARD = "walk_forward"
    EXPANDING_WINDOW = "expanding_window"
    ROLLING_WINDOW = "rolling_window"
    SEQUENTIAL = "sequential"
    TIME_BASED = "time_based"
    PURGED = "purged"


class SplitStatus(str, Enum):
    """Split status"""
    CREATED = "created"
    SPLITTING = "splitting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SplitConfig:
    """Split configuration"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    method: SplitMethod
    train_size: int = 0
    val_size: int = 0
    test_size: int = 0
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    step_size: int = 1
    gap_size: int = 0
    purge_size: int = 0
    n_splits: int = 5
    min_train_size: int = 1
    max_train_size: Optional[int] = None
    time_column: Optional[str] = None
    date_range: Optional[Tuple[datetime, datetime]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Split:
    """Split result"""
    id: str = field(default_factory=lambda: str(uuid4()))
    config_id: str
    fold: int
    train_indices: List[int]
    val_indices: List[int]
    test_indices: List[int]
    train_data: Optional[pd.DataFrame] = None
    val_data: Optional[pd.DataFrame] = None
    test_data: Optional[pd.DataFrame] = None
    train_start: Optional[datetime] = None
    train_end: Optional[datetime] = None
    val_start: Optional[datetime] = None
    val_end: Optional[datetime] = None
    test_start: Optional[datetime] = None
    test_end: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SplitResult:
    """Split result"""
    id: str = field(default_factory=lambda: str(uuid4()))
    config_id: str
    splits: List[Split]
    total_splits: int
    train_sizes: List[int]
    val_sizes: List[int]
    test_sizes: List[int]
    status: SplitStatus = SplitStatus.CREATED
    created_at: datetime = field(default_factory=datetime.utcnow)
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SplitterConfig(BaseModel):
    """Splitter configuration"""
    enabled: bool = True
    default_method: SplitMethod = SplitMethod.WALK_FORWARD
    default_train_ratio: float = Field(default=0.7, ge=0, le=1)
    default_val_ratio: float = Field(default=0.15, ge=0, le=1)
    default_test_ratio: float = Field(default=0.15, ge=0, le=1)
    max_splits: int = Field(default=100, gt=0)
    max_rows: int = Field(default=1000000, gt=0)
    parallel_workers: int = Field(default=4, gt=0)
    cache_enabled: bool = True
    cache_ttl: int = Field(default=3600, gt=0)
    health_check_interval: int = Field(default=60, gt=0)
    log_level: str = "info"


# ========================================
# TIME SERIES SPLITTER
# ========================================

class TimeSeriesSplitter:
    """
    Complete time series splitter for trading data.
    
    Features:
    - Multiple split methods (Walk-Forward, Expanding Window, Rolling Window)
    - Train/Validation/Test splits
    - Cross-validation for time series
    - Purged cross-validation
    - Gap handling
    - Time-based splits
    - Sequential splits
    - Health monitoring
    - Configuration management
    - Event handling
    - Logging
    - Metrics collection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = SplitterConfig(**(config or {}))
        self.redis = get_redis()
        
        # State
        self._configs: Dict[str, SplitConfig] = {}
        self._results: Dict[str, SplitResult] = {}
        self._cache: Dict[str, SplitResult] = {}
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        self._tasks: List[asyncio.Task] = []
        
        # Metrics
        self._metrics = {
            "total_splits": 0,
            "successful_splits": 0,
            "failed_splits": 0,
            "total_folds": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_split_time": 0.0
        }
        
        self.logger = get_logger(f"{__name__}.TimeSeriesSplitter")
        self.logger.info("TimeSeriesSplitter initialized")
    
    # ========================================
    # CONFIGURATION MANAGEMENT
    # ========================================
    
    async def register_config(
        self,
        name: str,
        method: SplitMethod = SplitMethod.WALK_FORWARD,
        **kwargs
    ) -> SplitConfig:
        """
        Register a split configuration.
        
        Args:
            name: Configuration name
            method: Split method
            **kwargs: Additional parameters
            
        Returns:
            SplitConfig: Registered configuration
        """
        config = SplitConfig(
            name=name,
            method=method,
            **kwargs
        )
        
        self._configs[config.id] = config
        
        self.logger.info(f"Registered split config: {name}")
        return config
    
    # ========================================
    # SPLIT EXECUTION
    # ========================================
    
    async def execute_split(
        self,
        data: pd.DataFrame,
        config_id: Optional[str] = None,
        config: Optional[SplitConfig] = None,
        cache_key: Optional[str] = None
    ) -> SplitResult:
        """
        Execute time series split.
        
        Args:
            data: Data to split
            config_id: Config ID
            config: Config (alternative)
            cache_key: Cache key
            
        Returns:
            SplitResult: Split results
        """
        start_time = time.time()
        
        # Get config
        if config_id:
            split_config = self._configs.get(config_id)
            if not split_config:
                raise SplitError(f"Config {config_id} not found")
        elif config:
            split_config = config
        else:
            raise SplitError("No config provided")
        
        # Check cache
        if self.config.cache_enabled and cache_key:
            cached = self._get_cached_result(cache_key)
            if cached:
                self._metrics["cache_hits"] += 1
                return cached
        
        try:
            # Validate data
            if len(data) > self.config.max_rows:
                raise SplitError(f"Data exceeds max rows: {len(data)} > {self.config.max_rows}")
            
            # Create result
            result = SplitResult(
                config_id=split_config.id,
                splits=[],
                total_splits=0,
                train_sizes=[],
                val_sizes=[],
                test_sizes=[],
                status=SplitStatus.SPLITTING
            )
            
            # Execute split based on method
            if split_config.method == SplitMethod.WALK_FORWARD:
                splits = await self._walk_forward_split(data, split_config)
            elif split_config.method == SplitMethod.EXPANDING_WINDOW:
                splits = await self._expanding_window_split(data, split_config)
            elif split_config.method == SplitMethod.ROLLING_WINDOW:
                splits = await self._rolling_window_split(data, split_config)
            elif split_config.method == SplitMethod.SEQUENTIAL:
                splits = await self._sequential_split(data, split_config)
            elif split_config.method == SplitMethod.TIME_BASED:
                splits = await self._time_based_split(data, split_config)
            elif split_config.method == SplitMethod.PURGED:
                splits = await self._purged_split(data, split_config)
            else:
                raise SplitError(f"Unsupported split method: {split_config.method}")
            
            # Update result
            result.splits = splits
            result.total_splits = len(splits)
            result.train_sizes = [len(s.train_indices) for s in splits]
            result.val_sizes = [len(s.val_indices) for s in splits]
            result.test_sizes = [len(s.test_indices) for s in splits]
            result.status = SplitStatus.COMPLETED
            result.processing_time = time.time() - start_time
            
            # Update metrics
            self._metrics["total_splits"] += 1
            self._metrics["successful_splits"] += 1
            self._metrics["total_folds"] += len(splits)
            self._metrics["avg_split_time"] = (
                self._metrics["avg_split_time"] * 0.9 + result.processing_time * 0.1
            )
            
            # Cache result
            if self.config.cache_enabled and cache_key:
                self._set_cached_result(cache_key, result)
                self._metrics["cache_misses"] += 1
            
            self.logger.info(
                f"Split completed: {split_config.name} "
                f"splits={len(splits)} time={result.processing_time:.3f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Split failed: {e}")
            self._metrics["failed_splits"] += 1
            raise SplitError(f"Split failed: {e}")
    
    # ========================================
    # SPLIT METHODS
    # ========================================
    
    async def _walk_forward_split(
        self,
        data: pd.DataFrame,
        config: SplitConfig
    ) -> List[Split]:
        """Walk-forward split"""
        splits = []
        n = len(data)
        
        train_size = config.train_size or int(n * config.train_ratio)
        val_size = config.val_size or int(n * config.val_ratio)
        test_size = config.test_size or int(n * config.test_ratio)
        step_size = config.step_size or test_size
        
        # Ensure enough data
        if train_size + val_size + test_size > n:
            raise SplitError("Insufficient data for split sizes")
        
        start = 0
        fold = 0
        
        while start + train_size + val_size + test_size <= n:
            # Get indices
            train_end = start + train_size
            val_end = train_end + val_size
            test_end = val_end + test_size
            
            # Create split
            split = Split(
                config_id=config.id,
                fold=fold,
                train_indices=list(range(start, train_end)),
                val_indices=list(range(train_end, val_end)),
                test_indices=list(range(val_end, test_end)),
                train_data=data.iloc[start:train_end],
                val_data=data.iloc[train_end:val_end],
                test_data=data.iloc[val_end:test_end]
            )
            
            # Add time info if applicable
            if isinstance(data.index, pd.DatetimeIndex):
                split.train_start = data.index[start]
                split.train_end = data.index[train_end - 1]
                split.val_start = data.index[train_end]
                split.val_end = data.index[val_end - 1]
                split.test_start = data.index[val_end]
                split.test_end = data.index[test_end - 1]
            
            splits.append(split)
            
            # Move window
            start += step_size
            fold += 1
            
            if fold >= self.config.max_splits:
                break
        
        return splits
    
    async def _expanding_window_split(
        self,
        data: pd.DataFrame,
        config: SplitConfig
    ) -> List[Split]:
        """Expanding window split"""
        splits = []
        n = len(data)
        
        initial_train_size = config.train_size or int(n * config.train_ratio)
        val_size = config.val_size or int(n * config.val_ratio)
        test_size = config.test_size or int(n * config.test_ratio)
        step_size = config.step_size or test_size
        
        if initial_train_size + val_size + test_size > n:
            raise SplitError("Insufficient data for split sizes")
        
        fold = 0
        train_size = initial_train_size
        
        while train_size + val_size + test_size <= n:
            start = 0
            train_end = train_size
            val_end = train_end + val_size
            test_end = val_end + test_size
            
            split = Split(
                config_id=config.id,
                fold=fold,
                train_indices=list(range(start, train_end)),
                val_indices=list(range(train_end, val_end)),
                test_indices=list(range(val_end, test_end)),
                train_data=data.iloc[start:train_end],
                val_data=data.iloc[train_end:val_end],
                test_data=data.iloc[val_end:test_end]
            )
            
            if isinstance(data.index, pd.DatetimeIndex):
                split.train_start = data.index[start]
                split.train_end = data.index[train_end - 1]
                split.val_start = data.index[train_end]
                split.val_end = data.index[val_end - 1]
                split.test_start = data.index[val_end]
                split.test_end = data.index[test_end - 1]
            
            splits.append(split)
            
            train_size += step_size
            fold += 1
            
            if fold >= self.config.max_splits:
                break
        
        return splits
    
    async def _rolling_window_split(
        self,
        data: pd.DataFrame,
        config: SplitConfig
    ) -> List[Split]:
        """Rolling window split"""
        splits = []
        n = len(data)
        
        window_size = config.train_size or int(n * config.train_ratio)
        val_size = config.val_size or int(n * config.val_ratio)
        test_size = config.test_size or int(n * config.test_ratio)
        step_size = config.step_size or test_size
        
        if window_size + val_size + test_size > n:
            raise SplitError("Insufficient data for split sizes")
        
        fold = 0
        start = 0
        
        while start + window_size + val_size + test_size <= n:
            train_end = start + window_size
            val_end = train_end + val_size
            test_end = val_end + test_size
            
            split = Split(
                config_id=config.id,
                fold=fold,
                train_indices=list(range(start, train_end)),
                val_indices=list(range(train_end, val_end)),
                test_indices=list(range(val_end, test_end)),
                train_data=data.iloc[start:train_end],
                val_data=data.iloc[train_end:val_end],
                test_data=data.iloc[val_end:test_end]
            )
            
            if isinstance(data.index, pd.DatetimeIndex):
                split.train_start = data.index[start]
                split.train_end = data.index[train_end - 1]
                split.val_start = data.index[train_end]
                split.val_end = data.index[val_end - 1]
                split.test_start = data.index[val_end]
                split.test_end = data.index[test_end - 1]
            
            splits.append(split)
            
            start += step_size
            fold += 1
            
            if fold >= self.config.max_splits:
                break
        
        return splits
    
    async def _sequential_split(
        self,
        data: pd.DataFrame,
        config: SplitConfig
    ) -> List[Split]:
        """Sequential split"""
        n = len(data)
        
        train_size = config.train_size or int(n * config.train_ratio)
        val_size = config.val_size or int(n * config.val_ratio)
        test_size = config.test_size or int(n * config.test_ratio)
        
        if train_size + val_size + test_size > n:
            raise SplitError("Insufficient data for split sizes")
        
        # Single split
        split = Split(
            config_id=config.id,
            fold=0,
            train_indices=list(range(0, train_size)),
            val_indices=list(range(train_size, train_size + val_size)),
            test_indices=list(range(train_size + val_size, train_size + val_size + test_size)),
            train_data=data.iloc[:train_size],
            val_data=data.iloc[train_size:train_size + val_size],
            test_data=data.iloc[train_size + val_size:train_size + val_size + test_size]
        )
        
        if isinstance(data.index, pd.DatetimeIndex):
            split.train_start = data.index[0]
            split.train_end = data.index[train_size - 1]
            split.val_start = data.index[train_size]
            split.val_end = data.index[train_size + val_size - 1]
            split.test_start = data.index[train_size + val_size]
            split.test_end = data.index[train_size + val_size + test_size - 1]
        
        return [split]
    
    async def _time_based_split(
        self,
        data: pd.DataFrame,
        config: SplitConfig
    ) -> List[Split]:
        """Time-based split"""
        if not isinstance(data.index, pd.DatetimeIndex):
            raise SplitError("Time-based split requires datetime index")
        
        if not config.date_range:
            raise SplitError("Date range required for time-based split")
        
        start_date, end_date = config.date_range
        n = len(data)
        
        # Find indices
        try:
            start_idx = data.index.get_loc(start_date, method='nearest')
            end_idx = data.index.get_loc(end_date, method='nearest')
        except:
            start_idx = 0
            end_idx = n - 1
        
        # Calculate sizes
        total_range = end_idx - start_idx + 1
        train_size = int(total_range * config.train_ratio)
        val_size = int(total_range * config.val_ratio)
        test_size = total_range - train_size - val_size
        
        # Single split
        split = Split(
            config_id=config.id,
            fold=0,
            train_indices=list(range(start_idx, start_idx + train_size)),
            val_indices=list(range(start_idx + train_size, start_idx + train_size + val_size)),
            test_indices=list(range(start_idx + train_size + val_size, end_idx + 1)),
            train_data=data.iloc[start_idx:start_idx + train_size],
            val_data=data.iloc[start_idx + train_size:start_idx + train_size + val_size],
            test_data=data.iloc[start_idx + train_size + val_size:end_idx + 1]
        )
        
        split.train_start = data.index[start_idx]
        split.train_end = data.index[start_idx + train_size - 1]
        split.val_start = data.index[start_idx + train_size]
        split.val_end = data.index[start_idx + train_size + val_size - 1]
        split.test_start = data.index[start_idx + train_size + val_size]
        split.test_end = data.index[end_idx]
        
        return [split]
    
    async def _purged_split(
        self,
        data: pd.DataFrame,
        config: SplitConfig
    ) -> List[Split]:
        """Purged split"""
        splits = []
        n = len(data)
        
        train_size = config.train_size or int(n * config.train_ratio)
        val_size = config.val_size or int(n * config.val_ratio)
        test_size = config.test_size or int(n * config.test_ratio)
        gap_size = config.gap_size or 0
        purge_size = config.purge_size or 0
        
        if train_size + val_size + test_size + gap_size > n:
            raise SplitError("Insufficient data for split sizes")
        
        fold = 0
        start = 0
        
        while start + train_size + gap_size + val_size + test_size <= n:
            train_end = start + train_size
            gap_start = train_end
            gap_end = gap_start + gap_size
            val_start = gap_end
            val_end = val_start + val_size
            test_start = val_end
            test_end = test_start + test_size
            
            # Purge: remove points near the boundary
            if purge_size > 0:
                # Adjust indices to purge
                purge_start = train_end - purge_size
                train_end_purged = purge_start
                train_indices = list(range(start, train_end_purged))
                
                purge_val_start = val_end - purge_size
                val_end_purged = purge_val_start
                val_indices = list(range(val_start, val_end_purged))
            else:
                train_indices = list(range(start, train_end))
                val_indices = list(range(val_start, val_end))
            
            split = Split(
                config_id=config.id,
                fold=fold,
                train_indices=train_indices,
                val_indices=val_indices,
                test_indices=list(range(test_start, test_end)),
                train_data=data.iloc[train_indices],
                val_data=data.iloc[val_indices],
                test_data=data.iloc[test_start:test_end]
            )
            
            if isinstance(data.index, pd.DatetimeIndex):
                split.train_start = data.index[train_indices[0]] if train_indices else None
                split.train_end = data.index[train_indices[-1]] if train_indices else None
                split.val_start = data.index[val_indices[0]] if val_indices else None
                split.val_end = data.index[val_indices[-1]] if val_indices else None
                split.test_start = data.index[test_start]
                split.test_end = data.index[test_end - 1]
            
            splits.append(split)
            
            start += train_size + gap_size + val_size
            fold += 1
            
            if fold >= self.config.max_splits:
                break
        
        return splits
    
    # ========================================
    # CROSS-VALIDATION
    # ========================================
    
    async def cross_validate(
        self,
        data: pd.DataFrame,
        n_splits: int = 5,
        gap: int = 0
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Generate cross-validation splits.
        
        Args:
            data: Data
            n_splits: Number of splits
            gap: Gap between train and test
            
        Returns:
            List[Tuple[np.ndarray, np.ndarray]]: CV splits
        """
        tscv = TimeSeriesSplit(n_splits=n_splits, gap=gap)
        splits = list(tscv.split(data))
        
        self.logger.info(f"Generated {len(splits)} cross-validation splits")
        return splits
    
    # ========================================
    # CACHE MANAGEMENT
    # ========================================
    
    def _get_cached_result(self, cache_key: str) -> Optional[SplitResult]:
        """Get cached result"""
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Check Redis cache
        try:
            cached = self.redis.get(f"split:{cache_key}")
            if cached:
                data = json.loads(cached)
                return SplitResult(**data)
        except Exception as e:
            self.logger.error(f"Redis cache error: {e}")
        
        return None
    
    def _set_cached_result(self, cache_key: str, result: SplitResult) -> None:
        """Cache result"""
        self._cache[cache_key] = result
        
        try:
            self.redis.setex(
                f"split:{cache_key}",
                self.config.cache_ttl,
                json.dumps(result.__dict__, default=str)
            )
        except Exception as e:
            self.logger.error(f"Redis cache error: {e}")
    
    # ========================================
    # HEALTH MONITORING
    # ========================================
    
    async def _health_loop(self) -> None:
        """Health monitoring loop"""
        while self._running:
            try:
                health = await self.health_check()
                self.logger.debug(f"Health: {health}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health loop error: {e}")
            
            await asyncio.sleep(self.config.health_check_interval)
    
    # ========================================
    # API METHODS
    # ========================================
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get splitter metrics"""
        return {
            **self._metrics,
            "total_configs": len(self._configs),
            "total_results": len(self._results),
            "cache_size": len(self._cache)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check splitter health"""
        health = {
            'status': 'healthy',
            'total_configs': len(self._configs),
            'total_results': len(self._results),
            'cache_size': len(self._cache)
        }
        
        if len(self._cache) > 1000:
            health['status'] = 'degraded'
            health['warning'] = 'Cache size exceeds limit'
        
        return health
    
    async def get_split_result(self, result_id: str) -> Optional[SplitResult]:
        """Get split result by ID"""
        return self._results.get(result_id)
    
    async def get_split(self, result_id: str, fold: int) -> Optional[Split]:
        """Get specific split by fold"""
        result = self._results.get(result_id)
        if not result:
            return None
        
        for split in result.splits:
            if split.fold == fold:
                return split
        
        return None
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the splitter"""
        self._running = True
        
        # Start background tasks
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.logger.info("TimeSeriesSplitter started")
    
    async def stop(self) -> None:
        """Stop the splitter"""
        self._running = False
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.logger.info("TimeSeriesSplitter stopped")


# ========================================
# DEPENDENCY INJECTION
# ========================================

_time_series_splitter: Optional[TimeSeriesSplitter] = None


def get_time_series_splitter() -> TimeSeriesSplitter:
    """Get singleton instance of TimeSeriesSplitter"""
    global _time_series_splitter
    if _time_series_splitter is None:
        _time_series_splitter = TimeSeriesSplitter()
    return _time_series_splitter


def reset_time_series_splitter() -> None:
    """Reset the time series splitter (for testing)"""
    global _time_series_splitter
    if _time_series_splitter:
        asyncio.create_task(_time_series_splitter.stop())
    _time_series_splitter = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'TimeSeriesSplitter',
    'SplitterConfig',
    'SplitConfig',
    'Split',
    'SplitResult',
    'SplitMethod',
    'SplitStatus',
    'get_time_series_splitter',
    'reset_time_series_splitter'
]
