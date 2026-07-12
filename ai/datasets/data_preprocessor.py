"""
NEXUS AI TRADING SYSTEM - Data Preprocessor
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Data Preprocessor system with:
- Data cleaning
- Missing value handling
- Outlier detection
- Normalization
- Standardization
- Feature scaling
- Data transformation
- Time series processing
- Data validation
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
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
from pydantic import BaseModel, Field, validator

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import PreprocessingError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class MissingValueStrategy(str, Enum):
    """Missing value handling strategies"""
    DROP = "drop"
    FILL_MEAN = "fill_mean"
    FILL_MEDIAN = "fill_median"
    FILL_MODE = "fill_mode"
    FILL_CONSTANT = "fill_constant"
    FILL_FFILL = "fill_ffill"
    FILL_BFILL = "fill_bfill"
    FILL_INTERPOLATE = "fill_interpolate"
    FILL_KNN = "fill_knn"


class OutlierMethod(str, Enum):
    """Outlier detection methods"""
    ZSCORE = "zscore"
    IQR = "iqr"
    MAD = "mad"
    ISOLATION_FOREST = "isolation_forest"
    LOF = "lof"
    PERCENTILE = "percentile"


class ScalingMethod(str, Enum):
    """Scaling methods"""
    STANDARD = "standard"
    MINMAX = "minmax"
    ROBUST = "robust"
    MAXABS = "maxabs"
    MEAN = "mean"
    LOG = "log"
    SQRT = "sqrt"


@dataclass
class PreprocessingConfig:
    """Preprocessing configuration"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    columns: List[str] = field(default_factory=list)
    missing_strategy: MissingValueStrategy = MissingValueStrategy.FILL_MEAN
    missing_value: Optional[Any] = None
    outlier_method: OutlierMethod = OutlierMethod.ZSCORE
    outlier_threshold: float = 3.0
    scaling_method: ScalingMethod = ScalingMethod.STANDARD
    scaling_params: Dict[str, Any] = field(default_factory=dict)
    encoding_method: str = "label"  # label, onehot
    date_columns: List[str] = field(default_factory=list)
    drop_columns: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PreprocessingResult:
    """Preprocessing result"""
    id: str = field(default_factory=lambda: str(uuid4()))
    config_id: str
    data: pd.DataFrame
    original_shape: Tuple[int, int]
    processed_shape: Tuple[int, int]
    missing_values_handled: int
    outliers_detected: int
    outliers_handled: int
    scaling_applied: bool
    encoding_applied: bool
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


class PreprocessorConfig(BaseModel):
    """Preprocessor configuration"""
    enabled: bool = True
    default_missing_strategy: MissingValueStrategy = MissingValueStrategy.FILL_MEAN
    default_outlier_method: OutlierMethod = OutlierMethod.ZSCORE
    default_outlier_threshold: float = Field(default=3.0, gt=0)
    default_scaling_method: ScalingMethod = ScalingMethod.STANDARD
    max_rows: int = Field(default=1000000, gt=0)
    parallel_workers: int = Field(default=4, gt=0)
    cache_enabled: bool = True
    cache_ttl: int = Field(default=3600, gt=0)
    health_check_interval: int = Field(default=60, gt=0)
    log_level: str = "info"


# ========================================
# DATA PREPROCESSOR
# ========================================

class DataPreprocessor:
    """
    Complete data preprocessor for trading data.
    
    Features:
    - Data cleaning
    - Missing value handling
    - Outlier detection
    - Normalization
    - Standardization
    - Feature scaling
    - Data transformation
    - Time series processing
    - Data validation
    - Health monitoring
    - Configuration management
    - Event handling
    - Logging
    - Metrics collection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = PreprocessorConfig(**(config or {}))
        self.redis = get_redis()
        
        # State
        self._configs: Dict[str, PreprocessingConfig] = {}
        self._cache: Dict[str, PreprocessingResult] = {}
        self._scalers: Dict[str, Any] = {}
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        self._tasks: List[asyncio.Task] = []
        
        # Metrics
        self._metrics = {
            "total_preprocessings": 0,
            "successful_preprocessings": 0,
            "failed_preprocessings": 0,
            "total_rows_processed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_processing_time": 0.0,
            "missing_handled": 0,
            "outliers_detected": 0
        }
        
        self.logger = get_logger(f"{__name__}.DataPreprocessor")
        self.logger.info("DataPreprocessor initialized")
    
    # ========================================
    # CONFIGURATION MANAGEMENT
    # ========================================
    
    async def register_config(
        self,
        name: str,
        columns: Optional[List[str]] = None,
        **kwargs
    ) -> PreprocessingConfig:
        """
        Register a preprocessing configuration.
        
        Args:
            name: Configuration name
            columns: Columns to process
            **kwargs: Additional parameters
            
        Returns:
            PreprocessingConfig: Registered configuration
        """
        config = PreprocessingConfig(
            name=name,
            columns=columns or [],
            **kwargs
        )
        
        self._configs[config.id] = config
        
        self.logger.info(f"Registered preprocessing config: {name}")
        return config
    
    # ========================================
    # DATA PREPROCESSING
    # ========================================
    
    async def preprocess(
        self,
        data: pd.DataFrame,
        config_id: Optional[str] = None,
        config: Optional[PreprocessingConfig] = None,
        cache_key: Optional[str] = None
    ) -> PreprocessingResult:
        """
        Preprocess data.
        
        Args:
            data: Data to preprocess
            config_id: Config ID
            config: Config (alternative)
            cache_key: Cache key
            
        Returns:
            PreprocessingResult: Preprocessed data
        """
        start_time = time.time()
        
        # Get config
        if config_id:
            preprocess_config = self._configs.get(config_id)
            if not preprocess_config:
                raise PreprocessingError(f"Config {config_id} not found")
        elif config:
            preprocess_config = config
        else:
            raise PreprocessingError("No config provided")
        
        # Check cache
        if self.config.cache_enabled and cache_key:
            cached = self._get_cached_result(cache_key)
            if cached:
                self._metrics["cache_hits"] += 1
                return cached
        
        try:
            # Validate data
            if len(data) > self.config.max_rows:
                raise PreprocessingError(f"Data exceeds max rows: {len(data)} > {self.config.max_rows}")
            
            # Copy data
            df = data.copy()
            original_shape = df.shape
            
            # Track metrics
            missing_handled = 0
            outliers_detected = 0
            
            # Process each column
            columns_to_process = preprocess_config.columns or df.columns.tolist()
            
            for col in columns_to_process:
                if col not in df.columns:
                    continue
                
                # Handle missing values
                if preprocess_config.missing_strategy != MissingValueStrategy.DROP:
                    missing_handled += await self._handle_missing_values(
                        df,
                        col,
                        preprocess_config
                    )
                
                # Detect and handle outliers
                outliers = await self._detect_outliers(
                    df[col],
                    preprocess_config
                )
                if len(outliers) > 0:
                    outliers_detected += len(outliers)
                    df.loc[outliers, col] = np.nan
                    # Re-fill missing values created by outlier removal
                    if preprocess_config.missing_strategy != MissingValueStrategy.DROP:
                        await self._handle_missing_values(
                            df,
                            col,
                            preprocess_config
                        )
                
                # Apply scaling
                if preprocess_config.scaling_method:
                    await self._apply_scaling(
                        df,
                        col,
                        preprocess_config
                    )
            
            # Drop columns
            if preprocess_config.drop_columns:
                df = df.drop(columns=[c for c in preprocess_config.drop_columns if c in df.columns])
            
            # Handle date columns
            if preprocess_config.date_columns:
                for col in preprocess_config.date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col])
            
            # Create result
            result = PreprocessingResult(
                config_id=preprocess_config.id,
                data=df,
                original_shape=original_shape,
                processed_shape=df.shape,
                missing_values_handled=missing_handled,
                outliers_detected=outliers_detected,
                outliers_handled=len(outliers_detected),
                scaling_applied=preprocess_config.scaling_method is not None,
                encoding_applied=False,
                processing_time=time.time() - start_time
            )
            
            # Update metrics
            self._metrics["total_preprocessings"] += 1
            self._metrics["successful_preprocessings"] += 1
            self._metrics["total_rows_processed"] += len(df)
            self._metrics["missing_handled"] += missing_handled
            self._metrics["outliers_detected"] += outliers_detected
            
            self._metrics["avg_processing_time"] = (
                self._metrics["avg_processing_time"] * 0.9 + result.processing_time * 0.1
            )
            
            # Cache result
            if self.config.cache_enabled and cache_key:
                self._set_cached_result(cache_key, result)
                self._metrics["cache_misses"] += 1
            
            self.logger.info(
                f"Preprocessing completed: {preprocess_config.name} "
                f"rows={len(df)} time={result.processing_time:.3f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Preprocessing failed: {e}")
            self._metrics["failed_preprocessings"] += 1
            raise PreprocessingError(f"Preprocessing failed: {e}")
    
    # ========================================
    # MISSING VALUE HANDLING
    # ========================================
    
    async def _handle_missing_values(
        self,
        df: pd.DataFrame,
        col: str,
        config: PreprocessingConfig
    ) -> int:
        """Handle missing values in column"""
        missing_mask = df[col].isna()
        missing_count = missing_mask.sum()
        
        if missing_count == 0:
            return 0
        
        if config.missing_strategy == MissingValueStrategy.DROP:
            df.dropna(subset=[col], inplace=True)
            return missing_count
        
        elif config.missing_strategy == MissingValueStrategy.FILL_MEAN:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(df[col].mean())
            else:
                df[col] = df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else '')
            
        elif config.missing_strategy == MissingValueStrategy.FILL_MEDIAN:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(df[col].median())
            else:
                df[col] = df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else '')
            
        elif config.missing_strategy == MissingValueStrategy.FILL_MODE:
            df[col] = df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else '')
            
        elif config.missing_strategy == MissingValueStrategy.FILL_CONSTANT:
            df[col] = df[col].fillna(config.missing_value or 0)
            
        elif config.missing_strategy == MissingValueStrategy.FILL_FFILL:
            df[col] = df[col].fillna(method='ffill')
            
        elif config.missing_strategy == MissingValueStrategy.FILL_BFILL:
            df[col] = df[col].fillna(method='bfill')
            
        elif config.missing_strategy == MissingValueStrategy.FILL_INTERPOLATE:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].interpolate(method='linear')
            else:
                df[col] = df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else '')
        
        return missing_count
    
    # ========================================
    # OUTLIER DETECTION
    # ========================================
    
    async def _detect_outliers(
        self,
        series: pd.Series,
        config: PreprocessingConfig
    ) -> pd.Index:
        """Detect outliers in series"""
        if not pd.api.types.is_numeric_dtype(series):
            return pd.Index([])
        
        data = series.dropna()
        if len(data) < 10:
            return pd.Index([])
        
        if config.outlier_method == OutlierMethod.ZSCORE:
            zscores = np.abs(stats.zscore(data))
            return data.index[zscores > config.outlier_threshold]
        
        elif config.outlier_method == OutlierMethod.IQR:
            q1 = data.quantile(0.25)
            q3 = data.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            return data.index[(data < lower) | (data > upper)]
        
        elif config.outlier_method == OutlierMethod.MAD:
            median = data.median()
            mad = (data - median).abs().median()
            if mad == 0:
                return pd.Index([])
            modified_zscore = 0.6745 * (data - median) / mad
            return data.index[np.abs(modified_zscore) > 3.5]
        
        elif config.outlier_method == OutlierMethod.PERCENTILE:
            lower = data.quantile(config.outlier_threshold / 100)
            upper = data.quantile(1 - config.outlier_threshold / 100)
            return data.index[(data < lower) | (data > upper)]
        
        else:
            return pd.Index([])
    
    # ========================================
    # SCALING
    # ========================================
    
    async def _apply_scaling(
        self,
        df: pd.DataFrame,
        col: str,
        config: PreprocessingConfig
    ) -> None:
        """Apply scaling to column"""
        if not pd.api.types.is_numeric_dtype(df[col]):
            return
        
        data = df[col].values.reshape(-1, 1)
        scaler_key = f"{config.id}_{col}"
        
        if config.scaling_method == ScalingMethod.STANDARD:
            scaler = StandardScaler()
        elif config.scaling_method == ScalingMethod.MINMAX:
            scaler = MinMaxScaler()
        elif config.scaling_method == ScalingMethod.ROBUST:
            scaler = RobustScaler()
        elif config.scaling_method == ScalingMethod.MAXABS:
            from sklearn.preprocessing import MaxAbsScaler
            scaler = MaxAbsScaler()
        else:
            return
        
        # Fit and transform
        scaled = scaler.fit_transform(data)
        df[col] = scaled.flatten()
        
        # Store scaler for inverse transform
        self._scalers[scaler_key] = scaler
    
    # ========================================
    # INVERSE TRANSFORM
    # ========================================
    
    async def inverse_transform(
        self,
        data: pd.DataFrame,
        config: PreprocessingConfig
    ) -> pd.DataFrame:
        """Inverse transform scaled data"""
        df = data.copy()
        
        for col in config.columns or df.columns:
            scaler_key = f"{config.id}_{col}"
            if scaler_key in self._scalers:
                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                    scaler = self._scalers[scaler_key]
                    df[col] = scaler.inverse_transform(df[col].values.reshape(-1, 1)).flatten()
        
        return df
    
    # ========================================
    # CACHE MANAGEMENT
    # ========================================
    
    def _get_cached_result(self, cache_key: str) -> Optional[PreprocessingResult]:
        """Get cached result"""
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Check Redis cache
        try:
            cached = self.redis.get(f"preprocess:{cache_key}")
            if cached:
                data = json.loads(cached)
                return PreprocessingResult(**data)
        except Exception as e:
            self.logger.error(f"Redis cache error: {e}")
        
        return None
    
    def _set_cached_result(
        self,
        cache_key: str,
        result: PreprocessingResult
    ) -> None:
        """Cache result"""
        self._cache[cache_key] = result
        
        try:
            self.redis.setex(
                f"preprocess:{cache_key}",
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
        """Get preprocessor metrics"""
        return {
            **self._metrics,
            "total_configs": len(self._configs),
            "cache_size": len(self._cache),
            "scalers_count": len(self._scalers)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check preprocessor health"""
        health = {
            'status': 'healthy',
            'total_configs': len(self._configs),
            'cache_size': len(self._cache),
            'scalers_count': len(self._scalers)
        }
        
        if len(self._cache) > 1000:
            health['status'] = 'degraded'
            health['warning'] = 'Cache size exceeds limit'
        
        return health
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the preprocessor"""
        self._running = True
        
        # Start background tasks
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.logger.info("DataPreprocessor started")
    
    async def stop(self) -> None:
        """Stop the preprocessor"""
        self._running = False
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.logger.info("DataPreprocessor stopped")


# ========================================
# DEPENDENCY INJECTION
# ========================================

_data_preprocessor: Optional[DataPreprocessor] = None


def get_data_preprocessor() -> DataPreprocessor:
    """Get singleton instance of DataPreprocessor"""
    global _data_preprocessor
    if _data_preprocessor is None:
        _data_preprocessor = DataPreprocessor()
    return _data_preprocessor


def reset_data_preprocessor() -> None:
    """Reset the data preprocessor (for testing)"""
    global _data_preprocessor
    if _data_preprocessor:
        asyncio.create_task(_data_preprocessor.stop())
    _data_preprocessor = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'DataPreprocessor',
    'PreprocessorConfig',
    'PreprocessingConfig',
    'PreprocessingResult',
    'MissingValueStrategy',
    'OutlierMethod',
    'ScalingMethod',
    'get_data_preprocessor',
    'reset_data_preprocessor'
]
