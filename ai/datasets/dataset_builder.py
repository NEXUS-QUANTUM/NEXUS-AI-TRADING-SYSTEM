"""
NEXUS AI TRADING SYSTEM - Dataset Builder
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Dataset Builder system with:
- Dataset creation from multiple sources
- Data validation
- Data transformation
- Train/test split
- Time series split
- Cross-validation splits
- Dataset versioning
- Dataset metadata
- Dataset export
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
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from pydantic import BaseModel, Field, validator

from ai.datasets.data_loader import DataLoader, DataLoadResult, get_data_loader
from ai.datasets.data_preprocessor import DataPreprocessor, PreprocessingResult, get_data_preprocessor
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import DatasetBuilderError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class SplitType(str, Enum):
    """Split types"""
    RANDOM = "random"
    TIME_SERIES = "time_series"
    STRATIFIED = "stratified"
    CUSTOM = "custom"


class DatasetStatus(str, Enum):
    """Dataset status"""
    CREATING = "creating"
    READY = "ready"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETED = "deleted"


@dataclass
class DatasetConfig:
    """Dataset configuration"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    version: str = "1.0.0"
    description: str = ""
    sources: List[str] = field(default_factory=list)  # Loader config IDs
    features: List[str] = field(default_factory=list)
    target: Optional[str] = None
    split_type: SplitType = SplitType.RANDOM
    train_ratio: float = 0.7
    validation_ratio: float = 0.15
    test_ratio: float = 0.15
    time_series_folds: int = 5
    shuffle: bool = True
    random_state: int = 42
    preprocess_config: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Dataset:
    """Dataset"""
    id: str = field(default_factory=lambda: str(uuid4()))
    config_id: str
    name: str
    version: str
    status: DatasetStatus = DatasetStatus.CREATING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    data: Optional[pd.DataFrame] = None
    train_data: Optional[pd.DataFrame] = None
    validation_data: Optional[pd.DataFrame] = None
    test_data: Optional[pd.DataFrame] = None
    features: List[str] = field(default_factory=list)
    target: Optional[str] = None
    shape: Tuple[int, int] = (0, 0)
    splits: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_results: List[DataLoadResult] = field(default_factory=list)
    preprocess_result: Optional[PreprocessingResult] = None


@dataclass
class DatasetSummary:
    """Dataset summary"""
    id: str
    name: str
    version: str
    status: DatasetStatus
    created_at: datetime
    rows: int
    columns: int
    features: List[str]
    target: Optional[str]
    splits: Dict[str, int]  # split name -> size


class DatasetBuilderConfig(BaseModel):
    """Dataset builder configuration"""
    enabled: bool = True
    max_dataset_size: int = Field(default=10737418240, gt=0)  # 10GB
    max_rows: int = Field(default=10000000, gt=0)
    default_train_ratio: float = Field(default=0.7, ge=0, le=1)
    default_validation_ratio: float = Field(default=0.15, ge=0, le=1)
    default_test_ratio: float = Field(default=0.15, ge=0, le=1)
    cache_enabled: bool = True
    cache_dir: str = Field(default="./data/datasets")
    max_cache_size: int = Field(default=10737418240, gt=0)  # 10GB
    parallel_workers: int = Field(default=4, gt=0)
    health_check_interval: int = Field(default=60, gt=0)
    log_level: str = "info"


# ========================================
# DATASET BUILDER
# ========================================

class DatasetBuilder:
    """
    Complete dataset builder for AI trading system.
    
    Features:
    - Dataset creation from multiple sources
    - Data validation
    - Data transformation
    - Train/test split
    - Time series split
    - Cross-validation splits
    - Dataset versioning
    - Dataset metadata
    - Dataset export
    - Health monitoring
    - Configuration management
    - Event handling
    - Logging
    - Metrics collection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = DatasetBuilderConfig(**(config or {}))
        self.redis = get_redis()
        self.data_loader = get_data_loader()
        self.data_preprocessor = get_data_preprocessor()
        
        # State
        self._configs: Dict[str, DatasetConfig] = {}
        self._datasets: Dict[str, Dataset] = {}
        self._cache: Dict[str, Dataset] = {}
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        self._tasks: List[asyncio.Task] = []
        
        # Metrics
        self._metrics = {
            "total_datasets": 0,
            "completed_datasets": 0,
            "failed_datasets": 0,
            "total_rows": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_build_time": 0.0
        }
        
        # Initialize cache directory
        self._init_cache_dir()
        
        self.logger = get_logger(f"{__name__}.DatasetBuilder")
        self.logger.info("DatasetBuilder initialized")
    
    # ========================================
    # INITIALIZATION
    # ========================================
    
    def _init_cache_dir(self) -> None:
        """Initialize cache directory"""
        if self.config.cache_enabled:
            Path(self.config.cache_dir).mkdir(parents=True, exist_ok=True)
    
    # ========================================
    # CONFIGURATION MANAGEMENT
    # ========================================
    
    async def register_config(
        self,
        name: str,
        sources: List[str],
        features: Optional[List[str]] = None,
        target: Optional[str] = None,
        **kwargs
    ) -> DatasetConfig:
        """
        Register a dataset configuration.
        
        Args:
            name: Dataset name
            sources: Source loader config IDs
            features: Feature columns
            target: Target column
            **kwargs: Additional parameters
            
        Returns:
            DatasetConfig: Registered configuration
        """
        config = DatasetConfig(
            name=name,
            sources=sources,
            features=features or [],
            target=target,
            **kwargs
        )
        
        self._configs[config.id] = config
        
        self.logger.info(f"Registered dataset config: {name}")
        return config
    
    # ========================================
    # DATASET BUILDING
    # ========================================
    
    async def build_dataset(
        self,
        config_id: str,
        force_rebuild: bool = False,
        cache_key: Optional[str] = None
    ) -> Dataset:
        """
        Build a dataset.
        
        Args:
            config_id: Configuration ID
            force_rebuild: Force rebuild
            cache_key: Cache key
            
        Returns:
            Dataset: Built dataset
        """
        start_time = time.time()
        
        # Get config
        config = self._configs.get(config_id)
        if not config:
            raise DatasetBuilderError(f"Config {config_id} not found")
        
        # Check cache
        if not force_rebuild and self.config.cache_enabled and cache_key:
            cached = self._get_cached_dataset(cache_key)
            if cached:
                self._metrics["cache_hits"] += 1
                return cached
        
        try:
            # Create dataset
            dataset = Dataset(
                config_id=config.id,
                name=config.name,
                version=config.version,
                status=DatasetStatus.CREATING
            )
            
            self._datasets[dataset.id] = dataset
            self._metrics["total_datasets"] += 1
            
            # Load data from sources
            self.logger.info(f"Loading data from {len(config.sources)} sources")
            dataset.status = DatasetStatus.PROCESSING
            
            data_frames = []
            source_results = []
            
            for source_id in config.sources:
                try:
                    result = await self.data_loader.load_data(config_id=source_id)
                    data_frames.append(result.data)
                    source_results.append(result)
                except Exception as e:
                    self.logger.error(f"Failed to load source {source_id}: {e}")
                    raise
            
            # Combine data
            if len(data_frames) > 1:
                combined_data = pd.concat(data_frames, ignore_index=True)
            else:
                combined_data = data_frames[0] if data_frames else pd.DataFrame()
            
            dataset.data = combined_data
            dataset.source_results = source_results
            dataset.shape = combined_data.shape
            
            # Preprocess data
            if config.preprocess_config:
                self.logger.info("Preprocessing data")
                preprocess_result = await self.data_preprocessor.preprocess(
                    data=combined_data,
                    config_id=config.preprocess_config
                )
                dataset.preprocess_result = preprocess_result
                dataset.data = preprocess_result.data
                dataset.shape = preprocess_result.processed_shape
            
            # Select features and target
            features = config.features or [c for c in dataset.data.columns if c != config.target]
            target = config.target
            
            if target and target not in dataset.data.columns:
                raise DatasetBuilderError(f"Target column {target} not found")
            
            dataset.features = features
            dataset.target = target
            
            # Split data
            self.logger.info("Splitting data")
            if config.split_type == SplitType.RANDOM:
                train_data, test_data, val_data = await self._random_split(
                    dataset.data,
                    features,
                    target,
                    config
                )
            elif config.split_type == SplitType.TIME_SERIES:
                train_data, test_data, val_data = await self._time_series_split(
                    dataset.data,
                    features,
                    target,
                    config
                )
            elif config.split_type == SplitType.STRATIFIED:
                train_data, test_data, val_data = await self._stratified_split(
                    dataset.data,
                    features,
                    target,
                    config
                )
            else:
                train_data, test_data, val_data = await self._random_split(
                    dataset.data,
                    features,
                    target,
                    config
                )
            
            dataset.train_data = train_data
            dataset.test_data = test_data
            dataset.validation_data = val_data
            
            # Record splits
            dataset.splits = {
                'train': {'rows': len(train_data)},
                'test': {'rows': len(test_data)},
                'validation': {'rows': len(val_data) if val_data is not None else 0}
            }
            
            dataset.status = DatasetStatus.COMPLETED
            dataset.updated_at = datetime.utcnow()
            
            # Update metrics
            self._metrics["completed_datasets"] += 1
            self._metrics["total_rows"] += len(dataset.data)
            build_time = time.time() - start_time
            self._metrics["avg_build_time"] = (
                self._metrics["avg_build_time"] * 0.9 + build_time * 0.1
            )
            
            # Cache dataset
            if self.config.cache_enabled and cache_key:
                self._set_cached_dataset(cache_key, dataset)
                self._metrics["cache_misses"] += 1
            
            self.logger.info(
                f"Dataset built: {config.name} "
                f"rows={len(dataset.data)} time={build_time:.3f}s"
            )
            
            return dataset
            
        except Exception as e:
            self.logger.error(f"Dataset build failed: {e}")
            dataset.status = DatasetStatus.FAILED
            self._metrics["failed_datasets"] += 1
            raise DatasetBuilderError(f"Dataset build failed: {e}")
    
    # ========================================
    # SPLIT METHODS
    # ========================================
    
    async def _random_split(
        self,
        data: pd.DataFrame,
        features: List[str],
        target: Optional[str],
        config: DatasetConfig
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
        """Random split"""
        train_ratio = config.train_ratio
        test_ratio = config.test_ratio
        val_ratio = config.validation_ratio
        
        # Prepare data
        X = data[features]
        y = data[target] if target else None
        
        # First split: train + val, test
        if val_ratio > 0:
            # Split train+val and test
            train_val_size = train_ratio + val_ratio
            X_train_val, X_test, y_train_val, y_test = train_test_split(
                X, y,
                test_size=test_ratio,
                shuffle=config.shuffle,
                random_state=config.random_state
            )
            
            # Split train and val
            val_size = val_ratio / train_val_size
            X_train, X_val, y_train, y_val = train_test_split(
                X_train_val, y_train_val,
                test_size=val_size,
                shuffle=config.shuffle,
                random_state=config.random_state
            )
            
            # Combine X and y
            train_data = pd.concat([X_train, y_train], axis=1) if y_train is not None else X_train
            val_data = pd.concat([X_val, y_val], axis=1) if y_val is not None else X_val
            test_data = pd.concat([X_test, y_test], axis=1) if y_test is not None else X_test
            
        else:
            # Split train and test only
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=test_ratio,
                shuffle=config.shuffle,
                random_state=config.random_state
            )
            
            train_data = pd.concat([X_train, y_train], axis=1) if y_train is not None else X_train
            test_data = pd.concat([X_test, y_test], axis=1) if y_test is not None else X_test
            val_data = None
        
        return train_data, test_data, val_data
    
    async def _time_series_split(
        self,
        data: pd.DataFrame,
        features: List[str],
        target: Optional[str],
        config: DatasetConfig
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
        """Time series split"""
        # Ensure data is sorted by index (assuming datetime index)
        if isinstance(data.index, pd.DatetimeIndex):
            data = data.sort_index()
        
        n = len(data)
        train_size = int(n * config.train_ratio)
        val_size = int(n * config.validation_ratio)
        test_size = n - train_size - val_size
        
        # Split sequentially
        train_data = data.iloc[:train_size]
        val_data = data.iloc[train_size:train_size + val_size] if val_size > 0 else None
        test_data = data.iloc[train_size + val_size:]
        
        return train_data, test_data, val_data
    
    async def _stratified_split(
        self,
        data: pd.DataFrame,
        features: List[str],
        target: Optional[str],
        config: DatasetConfig
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
        """Stratified split"""
        if not target or target not in data.columns:
            # Fallback to random split
            return await self._random_split(data, features, target, config)
        
        X = data[features]
        y = data[target]
        
        # Stratified split
        train_ratio = config.train_ratio
        test_ratio = config.test_ratio
        val_ratio = config.validation_ratio
        
        if val_ratio > 0:
            train_val_size = train_ratio + val_ratio
            X_train_val, X_test, y_train_val, y_test = train_test_split(
                X, y,
                test_size=test_ratio,
                stratify=y,
                random_state=config.random_state
            )
            
            val_size = val_ratio / train_val_size
            X_train, X_val, y_train, y_val = train_test_split(
                X_train_val, y_train_val,
                test_size=val_size,
                stratify=y_train_val,
                random_state=config.random_state
            )
            
            train_data = pd.concat([X_train, y_train], axis=1)
            val_data = pd.concat([X_val, y_val], axis=1)
            test_data = pd.concat([X_test, y_test], axis=1)
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=test_ratio,
                stratify=y,
                random_state=config.random_state
            )
            
            train_data = pd.concat([X_train, y_train], axis=1)
            test_data = pd.concat([X_test, y_test], axis=1)
            val_data = None
        
        return train_data, test_data, val_data
    
    # ========================================
    # TIME SERIES CROSS-VALIDATION
    # ========================================
    
    async def time_series_cv(
        self,
        dataset: Dataset,
        n_splits: int = 5
    ) -> List[Dict[str, pd.DataFrame]]:
        """
        Generate time series cross-validation splits.
        
        Args:
            dataset: Dataset
            n_splits: Number of splits
            
        Returns:
            List[Dict[str, pd.DataFrame]]: CV splits
        """
        data = dataset.data
        if isinstance(data.index, pd.DatetimeIndex):
            data = data.sort_index()
        
        tscv = TimeSeriesSplit(n_splits=n_splits)
        
        splits = []
        for train_idx, test_idx in tscv.split(data):
            splits.append({
                'train': data.iloc[train_idx],
                'test': data.iloc[test_idx]
            })
        
        return splits
    
    # ========================================
    # CACHE MANAGEMENT
    # ========================================
    
    def _get_cached_dataset(self, cache_key: str) -> Optional[Dataset]:
        """Get cached dataset"""
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Check file cache
        cache_path = Path(self.config.cache_dir) / f"{cache_key}.parquet"
        if cache_path.exists():
            try:
                data = pd.read_parquet(cache_path)
                dataset = Dataset(
                    config_id="",
                    name="cached",
                    version="",
                    status=DatasetStatus.COMPLETED,
                    data=data,
                    shape=data.shape
                )
                self._cache[cache_key] = dataset
                return dataset
            except Exception as e:
                self.logger.error(f"Cache read error: {e}")
        
        return None
    
    def _set_cached_dataset(self, cache_key: str, dataset: Dataset) -> None:
        """Cache dataset"""
        self._cache[cache_key] = dataset
        
        # Save to file cache
        if self.config.cache_enabled and dataset.data is not None:
            cache_path = Path(self.config.cache_dir) / f"{cache_key}.parquet"
            try:
                dataset.data.to_parquet(cache_path)
            except Exception as e:
                self.logger.error(f"Cache write error: {e}")
    
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
    
    async def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Get dataset by ID"""
        return self._datasets.get(dataset_id)
    
    async def get_summary(self, dataset_id: str) -> Optional[DatasetSummary]:
        """Get dataset summary"""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return None
        
        return DatasetSummary(
            id=dataset.id,
            name=dataset.name,
            version=dataset.version,
            status=dataset.status,
            created_at=dataset.created_at,
            rows=len(dataset.data) if dataset.data is not None else 0,
            columns=len(dataset.features) + (1 if dataset.target else 0),
            features=dataset.features,
            target=dataset.target,
            splits={
                'train': len(dataset.train_data) if dataset.train_data is not None else 0,
                'validation': len(dataset.validation_data) if dataset.validation_data is not None else 0,
                'test': len(dataset.test_data) if dataset.test_data is not None else 0
            }
        )
    
    async def list_datasets(self) -> List[DatasetSummary]:
        """List all datasets"""
        summaries = []
        for dataset in self._datasets.values():
            summary = await self.get_summary(dataset.id)
            if summary:
                summaries.append(summary)
        return summaries
    
    async def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset"""
        if dataset_id in self._datasets:
            dataset = self._datasets[dataset_id]
            dataset.status = DatasetStatus.DELETED
            del self._datasets[dataset_id]
            self.logger.info(f"Dataset deleted: {dataset_id}")
            return True
        return False
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get builder metrics"""
        return {
            **self._metrics,
            "total_configs": len(self._configs),
            "total_datasets": len(self._datasets),
            "cache_size": len(self._cache)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check builder health"""
        health = {
            'status': 'healthy',
            'total_configs': len(self._configs),
            'total_datasets': len(self._datasets),
            'cache_size': len(self._cache)
        }
        
        # Check cache size
        if len(self._cache) > 100:
            health['status'] = 'degraded'
            health['warning'] = 'Cache size exceeds limit'
        
        return health
    
    # ========================================
    # EXPORT
    # ========================================
    
    async def export_dataset(
        self,
        dataset_id: str,
        format: str = 'parquet',
        path: Optional[str] = None
    ) -> str:
        """
        Export dataset to file.
        
        Args:
            dataset_id: Dataset ID
            format: Export format
            path: Export path
            
        Returns:
            str: Export path
        """
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            raise DatasetBuilderError(f"Dataset {dataset_id} not found")
        
        if dataset.data is None:
            raise DatasetBuilderError(f"Dataset {dataset_id} has no data")
        
        if not path:
            path = f"{dataset.name}_{dataset.version}.{format}"
        
        if format == 'parquet':
            dataset.data.to_parquet(path)
        elif format == 'csv':
            dataset.data.to_csv(path, index=False)
        elif format == 'json':
            dataset.data.to_json(path, orient='records')
        else:
            raise DatasetBuilderError(f"Unsupported format: {format}")
        
        self.logger.info(f"Dataset exported to {path}")
        return path
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the dataset builder"""
        self._running = True
        
        # Start background tasks
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.logger.info("DatasetBuilder started")
    
    async def stop(self) -> None:
        """Stop the dataset builder"""
        self._running = False
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.logger.info("DatasetBuilder stopped")


# ========================================
# DEPENDENCY INJECTION
# ========================================

_dataset_builder: Optional[DatasetBuilder] = None


def get_dataset_builder() -> DatasetBuilder:
    """Get singleton instance of DatasetBuilder"""
    global _dataset_builder
    if _dataset_builder is None:
        _dataset_builder = DatasetBuilder()
    return _dataset_builder


def reset_dataset_builder() -> None:
    """Reset the dataset builder (for testing)"""
    global _dataset_builder
    if _dataset_builder:
        asyncio.create_task(_dataset_builder.stop())
    _dataset_builder = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'DatasetBuilder',
    'DatasetBuilderConfig',
    'DatasetConfig',
    'Dataset',
    'DatasetSummary',
    'SplitType',
    'DatasetStatus',
    'get_dataset_builder',
    'reset_dataset_builder'
]
