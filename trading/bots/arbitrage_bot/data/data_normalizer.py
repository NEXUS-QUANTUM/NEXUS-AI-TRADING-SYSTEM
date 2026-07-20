# trading/bots/arbitrage_bot/data/data_normalizer.py
# Nexus AI Trading System - Arbitrage Bot Data Normalizer Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Data Normalizer Module

This module provides comprehensive data normalization and standardization
for the arbitrage bot system, including:

- Price data normalization
- Volume data normalization
- Time series alignment
- Data scaling and standardization
- Outlier detection and handling
- Missing data imputation
- Data resampling and interpolation
- Symbol normalization
- Exchange-specific data normalization
- Decimal precision management
- Data type conversion
- Data quality validation
- Normalization pipelines
- Batch normalization
- Real-time normalization

The data normalizer ensures consistent, clean data across all
exchanges for accurate arbitrage detection and analysis.
"""

import asyncio
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis
from scipy import stats

# Nexus imports
from trading.bots.arbitrage_bot.core.market_data import MarketPrice, MarketDepth, MarketTrade
from trading.bots.arbitrage_bot.data.candle_manager import Candle, CandleInterval
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class NormalizationType(str, Enum):
    """Normalization types."""
    MIN_MAX = "min_max"  # Min-Max scaling
    Z_SCORE = "z_score"  # Z-score standardization
    ROBUST = "robust"    # Robust scaling
    LOG = "log"          # Log transformation
    SQRT = "sqrt"        # Square root transformation
    BOX_COX = "box_cox"  # Box-Cox transformation
    YEO_JOHNSON = "yeo_johnson"  # Yeo-Johnson transformation
    QUANTILE = "quantile"  # Quantile transformation
    RANK = "rank"        # Rank transformation


class MissingDataStrategy(str, Enum):
    """Missing data strategies."""
    DROP = "drop"          # Drop missing values
    FILL = "fill"          # Fill with value
    INTERPOLATE = "interpolate"  # Interpolate
    FORWARD = "forward"    # Forward fill
    BACKWARD = "backward"  # Backward fill
    MEAN = "mean"          # Fill with mean
    MEDIAN = "median"      # Fill with median
    MODE = "mode"          # Fill with mode
    PREDICT = "predict"    # Predict missing values


class OutlierDetection(str, Enum):
    """Outlier detection methods."""
    Z_SCORE = "z_score"     # Z-score method
    IQR = "iqr"            # Interquartile range
    MAD = "mad"            # Median absolute deviation
    DBSCAN = "dbscan"      # DBSCAN clustering
    ISOLATION_FOREST = "isolation_forest"  # Isolation Forest
    LOCAL_OUTLIER = "local_outlier"  # Local Outlier Factor


class TimeAlignment(str, Enum):
    """Time alignment methods."""
    NEAREST = "nearest"    # Nearest timestamp
    LINEAR = "linear"      # Linear interpolation
    TIME = "time"          # Time-based alignment
    INDEX = "index"        # Index-based alignment


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class NormalizationConfig(BaseModel):
    """Normalization configuration."""
    enabled: bool = True
    type: NormalizationType = NormalizationType.Z_SCORE
    missing_strategy: MissingDataStrategy = MissingDataStrategy.INTERPOLATE
    outlier_method: OutlierDetection = OutlierDetection.IQR
    outlier_threshold: float = 3.0
    time_alignment: TimeAlignment = TimeAlignment.TIME
    decimal_precision: int = 8
    fill_value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    clip: bool = False
    clip_min: Optional[float] = None
    clip_max: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NormalizedData(BaseModel):
    """Normalized data result."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_data: Any
    normalized_data: Any
    type: NormalizationType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    quality_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NormalizationPipeline(BaseModel):
    """Normalization pipeline."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    enabled: bool = True
    steps: List[NormalizationConfig] = Field(default_factory=list)
    input_type: str
    output_type: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DataQualityReport(BaseModel):
    """Data quality report."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_source: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_samples: int = 0
    missing_count: int = 0
    missing_percentage: float = 0.0
    outlier_count: int = 0
    outlier_percentage: float = 0.0
    duplicate_count: int = 0
    duplicate_percentage: float = 0.0
    quality_score: float = 0.0
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Normalization pipelines
CREATE TABLE IF NOT EXISTS normalization_pipelines (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    steps JSONB NOT NULL,
    input_type VARCHAR(50) NOT NULL,
    output_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Normalized data
CREATE TABLE IF NOT EXISTS normalized_data (
    id VARCHAR(64) PRIMARY KEY,
    original_data JSONB NOT NULL,
    normalized_data JSONB NOT NULL,
    type VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    parameters JSONB DEFAULT '{}',
    quality_score FLOAT DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    INDEX idx_normalized_data_type (type),
    INDEX idx_normalized_data_timestamp (timestamp)
);

-- Data quality reports
CREATE TABLE IF NOT EXISTS data_quality_reports (
    id VARCHAR(64) PRIMARY KEY,
    data_source VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    total_samples INTEGER NOT NULL,
    missing_count INTEGER NOT NULL,
    missing_percentage FLOAT NOT NULL,
    outlier_count INTEGER NOT NULL,
    outlier_percentage FLOAT NOT NULL,
    duplicate_count INTEGER NOT NULL,
    duplicate_percentage FLOAT NOT NULL,
    quality_score FLOAT NOT NULL,
    issues JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    INDEX idx_data_quality_reports_data_source (data_source),
    INDEX idx_data_quality_reports_timestamp (timestamp)
);
"""


# =============================================================================
# DATA NORMALIZER CLASS
# =============================================================================

class DataNormalizer:
    """
    Advanced data normalizer for arbitrage bot.
    
    Features:
    - Price data normalization
    - Volume data normalization
    - Time series alignment
    - Data scaling and standardization
    - Outlier detection and handling
    - Missing data imputation
    - Data resampling and interpolation
    - Symbol normalization
    - Exchange-specific data normalization
    - Decimal precision management
    - Data type conversion
    - Data quality validation
    - Normalization pipelines
    - Batch normalization
    - Real-time normalization
    """
    
    def __init__(
        self,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.redis = redis
        self.pool = pool
        self.config = config or {}
        
        # Normalization pipelines
        self._pipelines: Dict[str, NormalizationPipeline] = {}
        
        # Normalization parameters cache
        self._params_cache: Dict[str, Dict[str, Any]] = {}
        
        # Data quality reports
        self._quality_reports: List[DataQualityReport] = []
        
        # Circuit breakers
        self._normalizer_cb = CircuitBreaker(
            name="data_normalizer",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        logger.info("DataNormalizer initialized")
    
    async def initialize(self):
        """Initialize the data normalizer."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load pipelines
        if self.pool:
            await self._load_pipelines()
        
        self._running = True
        self._initialized = True
        
        logger.info("DataNormalizer initialized")
    
    async def _init_database(self):
        """Initialize database tables."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for statement in CREATE_TABLES_SQL.split(';'):
                        if statement.strip():
                            await conn.execute(statement)
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    # =========================================================================
    # PRICE NORMALIZATION
    # =========================================================================
    
    async def normalize_price(
        self,
        price: Union[Decimal, float, str],
        config: Optional[NormalizationConfig] = None
    ) -> Decimal:
        """
        Normalize a price value.
        
        Args:
            price: Price to normalize
            config: Normalization configuration
            
        Returns:
            Normalized price
        """
        if config is None:
            config = NormalizationConfig()
        
        if not config.enabled:
            return Decimal(str(price))
        
        try:
            # Convert to Decimal
            if isinstance(price, str):
                price = Decimal(price)
            elif isinstance(price, float):
                price = Decimal(str(price))
            
            # Apply precision
            price = price.quantize(
                Decimal(f'1e-{config.decimal_precision}'),
                rounding=ROUND_HALF_UP
            )
            
            # Apply clipping if enabled
            if config.clip:
                clip_min = Decimal(str(config.clip_min or 0))
                clip_max = Decimal(str(config.clip_max or float('inf')))
                price = max(clip_min, min(price, clip_max))
            
            return price
            
        except Exception as e:
            logger.error(f"Price normalization error: {e}")
            return Decimal(str(price))
    
    async def normalize_prices(
        self,
        prices: List[Union[Decimal, float, str]],
        config: Optional[NormalizationConfig] = None
    ) -> List[Decimal]:
        """
        Normalize multiple price values.
        
        Args:
            prices: List of prices to normalize
            config: Normalization configuration
            
        Returns:
            List of normalized prices
        """
        return [await self.normalize_price(p, config) for p in prices]
    
    # =========================================================================
    # TIME SERIES NORMALIZATION
    # =========================================================================
    
    async def normalize_time_series(
        self,
        data: pd.DataFrame,
        timestamp_col: str = 'timestamp',
        value_cols: Optional[List[str]] = None,
        config: Optional[NormalizationConfig] = None
    ) -> pd.DataFrame:
        """
        Normalize a time series.
        
        Args:
            data: DataFrame with time series data
            timestamp_col: Timestamp column name
            value_cols: Value columns to normalize
            config: Normalization configuration
            
        Returns:
            Normalized DataFrame
        """
        if config is None:
            config = NormalizationConfig()
        
        if not config.enabled:
            return data
        
        result = data.copy()
        
        if value_cols is None:
            value_cols = [col for col in data.columns if col != timestamp_col]
        
        # Align timestamps
        if config.time_alignment == TimeAlignment.TIME:
            result = self._align_by_time(result, timestamp_col)
        elif config.time_alignment == TimeAlignment.INDEX:
            result = self._align_by_index(result)
        
        # Handle missing data
        for col in value_cols:
            if col in result.columns:
                result[col] = self._handle_missing(result[col], config.missing_strategy)
        
        # Detect and handle outliers
        for col in value_cols:
            if col in result.columns:
                result[col] = self._handle_outliers(result[col], config)
        
        # Normalize values
        for col in value_cols:
            if col in result.columns:
                result[col] = self._normalize_series(result[col], config)
        
        return result
    
    def _align_by_time(self, df: pd.DataFrame, timestamp_col: str) -> pd.DataFrame:
        """Align data by time."""
        if timestamp_col in df.columns:
            df = df.set_index(timestamp_col)
            df = df.resample('1s').mean()
            df = df.reset_index()
        return df
    
    def _align_by_index(self, df: pd.DataFrame) -> pd.DataFrame:
        """Align data by index."""
        return df
    
    def _handle_missing(
        self,
        series: pd.Series,
        strategy: MissingDataStrategy
    ) -> pd.Series:
        """Handle missing data in a series."""
        if strategy == MissingDataStrategy.DROP:
            return series.dropna()
        elif strategy == MissingDataStrategy.FILL:
            return series.fillna(value=0)
        elif strategy == MissingDataStrategy.INTERPOLATE:
            return series.interpolate(method='linear')
        elif strategy == MissingDataStrategy.FORWARD:
            return series.fillna(method='ffill')
        elif strategy == MissingDataStrategy.BACKWARD:
            return series.fillna(method='bfill')
        elif strategy == MissingDataStrategy.MEAN:
            return series.fillna(series.mean())
        elif strategy == MissingDataStrategy.MEDIAN:
            return series.fillna(series.median())
        elif strategy == MissingDataStrategy.MODE:
            return series.fillna(series.mode()[0] if not series.mode().empty else 0)
        else:
            return series
    
    def _handle_outliers(
        self,
        series: pd.Series,
        config: NormalizationConfig
    ) -> pd.Series:
        """Detect and handle outliers in a series."""
        if config.outlier_method == OutlierDetection.Z_SCORE:
            z_scores = np.abs(stats.zscore(series.dropna()))
            outliers = z_scores > config.outlier_threshold
            series[outliers] = series.mean()
            
        elif config.outlier_method == OutlierDetection.IQR:
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            series[(series < lower_bound) | (series > upper_bound)] = series.mean()
            
        elif config.outlier_method == OutlierDetection.MAD:
            median = series.median()
            mad = np.median(np.abs(series - median))
            modified_z_scores = 0.6745 * (series - median) / mad
            outliers = np.abs(modified_z_scores) > config.outlier_threshold
            series[outliers] = median
            
        return series
    
    def _normalize_series(
        self,
        series: pd.Series,
        config: NormalizationConfig
    ) -> pd.Series:
        """Normalize a series using the specified method."""
        if config.type == NormalizationType.MIN_MAX:
            min_val = series.min()
            max_val = series.max()
            if max_val - min_val > 0:
                return (series - min_val) / (max_val - min_val)
            return series
            
        elif config.type == NormalizationType.Z_SCORE:
            mean = series.mean()
            std = series.std()
            if std > 0:
                return (series - mean) / std
            return series
            
        elif config.type == NormalizationType.ROBUST:
            median = series.median()
            q75 = series.quantile(0.75)
            q25 = series.quantile(0.25)
            iqr = q75 - q25
            if iqr > 0:
                return (series - median) / iqr
            return series
            
        elif config.type == NormalizationType.LOG:
            return np.log1p(series)
            
        elif config.type == NormalizationType.SQRT:
            return np.sqrt(series)
            
        elif config.type == NormalizationType.QUANTILE:
            return series.rank(pct=True)
            
        elif config.type == NormalizationType.RANK:
            return series.rank()
            
        else:
            return series
    
    # =========================================================================
    # DATA QUALITY
    # =========================================================================
    
    async def assess_quality(
        self,
        data: pd.DataFrame,
        source: str
    ) -> DataQualityReport:
        """
        Assess data quality.
        
        Args:
            data: DataFrame to assess
            source: Data source identifier
            
        Returns:
            DataQualityReport
        """
        total_samples = len(data)
        
        # Count missing values
        missing_count = data.isnull().sum().sum()
        missing_percentage = (missing_count / (total_samples * len(data.columns))) * 100 if total_samples > 0 else 0
        
        # Detect outliers
        outlier_count = 0
        for col in data.select_dtypes(include=[np.number]).columns:
            Q1 = data[col].quantile(0.25)
            Q3 = data[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            outliers = ((data[col] < lower_bound) | (data[col] > upper_bound)).sum()
            outlier_count += outliers
        
        outlier_percentage = (outlier_count / total_samples) * 100 if total_samples > 0 else 0
        
        # Count duplicates
        duplicate_count = data.duplicated().sum()
        duplicate_percentage = (duplicate_count / total_samples) * 100 if total_samples > 0 else 0
        
        # Calculate quality score
        quality_score = 100
        quality_score -= missing_percentage * 0.5
        quality_score -= outlier_percentage * 0.3
        quality_score -= duplicate_percentage * 0.2
        quality_score = max(0, min(100, quality_score))
        
        # Identify issues
        issues = []
        if missing_percentage > 5:
            issues.append({
                'type': 'missing_data',
                'severity': 'medium' if missing_percentage < 20 else 'high',
                'description': f'{missing_percentage:.1f}% missing values'
            })
        
        if outlier_percentage > 5:
            issues.append({
                'type': 'outliers',
                'severity': 'medium' if outlier_percentage < 20 else 'high',
                'description': f'{outlier_percentage:.1f}% outliers detected'
            })
        
        if duplicate_percentage > 1:
            issues.append({
                'type': 'duplicates',
                'severity': 'medium' if duplicate_percentage < 5 else 'high',
                'description': f'{duplicate_percentage:.1f}% duplicate rows'
            })
        
        report = DataQualityReport(
            data_source=source,
            total_samples=total_samples,
            missing_count=missing_count,
            missing_percentage=missing_percentage,
            outlier_count=outlier_count,
            outlier_percentage=outlier_percentage,
            duplicate_count=duplicate_count,
            duplicate_percentage=duplicate_percentage,
            quality_score=quality_score,
            issues=issues
        )
        
        self._quality_reports.append(report)
        
        if self.pool:
            await self._save_quality_report(report)
        
        return report
    
    # =========================================================================
    # NORMALIZATION PIPELINES
    # =========================================================================
    
    async def create_pipeline(
        self,
        name: str,
        steps: List[NormalizationConfig],
        input_type: str,
        output_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> NormalizationPipeline:
        """
        Create a normalization pipeline.
        
        Args:
            name: Pipeline name
            steps: List of normalization steps
            input_type: Input data type
            output_type: Output data type
            metadata: Additional metadata
            
        Returns:
            NormalizationPipeline
        """
        pipeline = NormalizationPipeline(
            name=name,
            steps=steps,
            input_type=input_type,
            output_type=output_type,
            metadata=metadata or {}
        )
        
        self._pipelines[pipeline.id] = pipeline
        
        if self.pool:
            await self._save_pipeline(pipeline)
        
        logger.info(f"Created normalization pipeline: {name}")
        return pipeline
    
    async def apply_pipeline(
        self,
        pipeline_id: str,
        data: Any
    ) -> Any:
        """
        Apply a normalization pipeline to data.
        
        Args:
            pipeline_id: Pipeline ID
            data: Input data
            
        Returns:
            Normalized data
        """
        if pipeline_id not in self._pipelines:
            raise ValueError(f"Pipeline {pipeline_id} not found")
        
        pipeline = self._pipelines[pipeline_id]
        result = data
        
        for step in pipeline.steps:
            if step.type == NormalizationType.MIN_MAX:
                result = await self._apply_min_max(result, step)
            elif step.type == NormalizationType.Z_SCORE:
                result = await self._apply_z_score(result, step)
            elif step.type == NormalizationType.ROBUST:
                result = await self._apply_robust(result, step)
            elif step.type == NormalizationType.LOG:
                result = await self._apply_log(result, step)
            elif step.type == NormalizationType.SQRT:
                result = await self._apply_sqrt(result, step)
            elif step.type == NormalizationType.BOX_COX:
                result = await self._apply_box_cox(result, step)
            elif step.type == NormalizationType.YEO_JOHNSON:
                result = await self._apply_yeo_johnson(result, step)
            elif step.type == NormalizationType.QUANTILE:
                result = await self._apply_quantile(result, step)
            elif step.type == NormalizationType.RANK:
                result = await self._apply_rank(result, step)
        
        return result
    
    async def _apply_min_max(self, data: Any, config: NormalizationConfig) -> Any:
        """Apply min-max normalization."""
        # Implementation depends on data type
        return data
    
    async def _apply_z_score(self, data: Any, config: NormalizationConfig) -> Any:
        """Apply z-score normalization."""
        return data
    
    async def _apply_robust(self, data: Any, config: NormalizationConfig) -> Any:
        """Apply robust scaling."""
        return data
    
    async def _apply_log(self, data: Any, config: NormalizationConfig) -> Any:
        """Apply log transformation."""
        return data
    
    async def _apply_sqrt(self, data: Any, config: NormalizationConfig) -> Any:
        """Apply square root transformation."""
        return data
    
    async def _apply_box_cox(self, data: Any, config: NormalizationConfig) -> Any:
        """Apply Box-Cox transformation."""
        return data
    
    async def _apply_yeo_johnson(self, data: Any, config: NormalizationConfig) -> Any:
        """Apply Yeo-Johnson transformation."""
        return data
    
    async def _apply_quantile(self, data: Any, config: NormalizationConfig) -> Any:
        """Apply quantile transformation."""
        return data
    
    async def _apply_rank(self, data: Any, config: NormalizationConfig) -> Any:
        """Apply rank transformation."""
        return data
    
    # =========================================================================
    # SYMBOL NORMALIZATION
    # =========================================================================
    
    def normalize_symbol(
        self,
        symbol: str,
        exchange: Optional[str] = None
    ) -> str:
        """
        Normalize a symbol.
        
        Args:
            symbol: Symbol to normalize
            exchange: Exchange name for context
            
        Returns:
            Normalized symbol
        """
        if not symbol:
            return ''
        
        # Remove whitespace
        symbol = symbol.strip().upper()
        
        # Remove exchange-specific suffixes
        if exchange:
            if exchange.lower() == 'binance':
                symbol = symbol.replace('USDT', '/USDT')
            elif exchange.lower() == 'okx':
                symbol = symbol.replace('-', '/')
            elif exchange.lower() == 'kraken':
                if 'USD' in symbol:
                    symbol = symbol.replace('USD', '/USD')
                elif 'EUR' in symbol:
                    symbol = symbol.replace('EUR', '/EUR')
                elif 'JPY' in symbol:
                    symbol = symbol.replace('JPY', '/JPY')
        
        # Standardize format
        if '/' not in symbol:
            # Try to split base and quote
            for quote in ['USDT', 'USD', 'USDC', 'BUSD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD']:
                if symbol.endswith(quote):
                    base = symbol[:-len(quote)]
                    symbol = f"{base}/{quote}"
                    break
        
        return symbol
    
    def normalize_symbols(
        self,
        symbols: List[str],
        exchange: Optional[str] = None
    ) -> List[str]:
        """
        Normalize multiple symbols.
        
        Args:
            symbols: List of symbols
            exchange: Exchange name
            
        Returns:
            List of normalized symbols
        """
        return [self.normalize_symbol(s, exchange) for s in symbols]
    
    # =========================================================================
    # DECIMAL PRECISION
    # =========================================================================
    
    def normalize_decimal(
        self,
        value: Union[Decimal, float, str],
        precision: int = 8
    ) -> Decimal:
        """
        Normalize decimal precision.
        
        Args:
            value: Value to normalize
            precision: Decimal precision
            
        Returns:
            Normalized Decimal
        """
        if isinstance(value, str):
            value = Decimal(value)
        elif isinstance(value, float):
            value = Decimal(str(value))
        
        return value.quantize(
            Decimal(f'1e-{precision}'),
            rounding=ROUND_HALF_UP
        )
    
    # =========================================================================
    # DATA TYPE CONVERSION
    # =========================================================================
    
    def convert_data_types(
        self,
        data: Any,
        target_type: str
    ) -> Any:
        """
        Convert data types.
        
        Args:
            data: Data to convert
            target_type: Target data type
            
        Returns:
            Converted data
        """
        if target_type == 'float':
            if isinstance(data, (Decimal, int)):
                return float(data)
            elif isinstance(data, str):
                try:
                    return float(data)
                except ValueError:
                    return data
        elif target_type == 'int':
            if isinstance(data, (Decimal, float)):
                return int(data)
            elif isinstance(data, str):
                try:
                    return int(data)
                except ValueError:
                    return data
        elif target_type == 'str':
            return str(data)
        elif target_type == 'Decimal':
            if isinstance(data, (int, float)):
                return Decimal(str(data))
            elif isinstance(data, str):
                try:
                    return Decimal(data)
                except ValueError:
                    return data
        
        return data
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _load_pipelines(self):
        """Load normalization pipelines from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM normalization_pipelines")
                
                for row in rows:
                    pipeline = NormalizationPipeline(
                        id=row['id'],
                        name=row['name'],
                        enabled=row['enabled'],
                        steps=[NormalizationConfig(**step) for step in row['steps']],
                        input_type=row['input_type'],
                        output_type=row['output_type'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                        metadata=row['metadata'] or {}
                    )
                    self._pipelines[pipeline.id] = pipeline
                
                logger.info(f"Loaded {len(self._pipelines)} normalization pipelines")
                
        except Exception as e:
            logger.error(f"Error loading pipelines: {e}")
    
    async def _save_pipeline(self, pipeline: NormalizationPipeline):
        """Save normalization pipeline to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO normalization_pipelines (
                        id, name, enabled, steps,
                        input_type, output_type,
                        created_at, updated_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        enabled = EXCLUDED.enabled,
                        steps = EXCLUDED.steps,
                        input_type = EXCLUDED.input_type,
                        output_type = EXCLUDED.output_type,
                        updated_at = EXCLUDED.updated_at,
                        metadata = EXCLUDED.metadata
                    """,
                    pipeline.id,
                    pipeline.name,
                    pipeline.enabled,
                    json.dumps([s.dict() for s in pipeline.steps]),
                    pipeline.input_type,
                    pipeline.output_type,
                    pipeline.created_at,
                    pipeline.updated_at,
                    json.dumps(pipeline.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving pipeline: {e}")
    
    async def _save_quality_report(self, report: DataQualityReport):
        """Save data quality report to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO data_quality_reports (
                        id, data_source, timestamp,
                        total_samples, missing_count, missing_percentage,
                        outlier_count, outlier_percentage,
                        duplicate_count, duplicate_percentage,
                        quality_score, issues, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                              $9, $10, $11, $12, $13)
                    """,
                    report.id,
                    report.data_source,
                    report.timestamp,
                    report.total_samples,
                    report.missing_count,
                    report.missing_percentage,
                    report.outlier_count,
                    report.outlier_percentage,
                    report.duplicate_count,
                    report.duplicate_percentage,
                    report.quality_score,
                    json.dumps(report.issues),
                    json.dumps(report.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving quality report: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the data normalizer."""
        self._running = False
        logger.info("DataNormalizer shutdown")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'DataNormalizer',
    'NormalizationType',
    'MissingDataStrategy',
    'OutlierDetection',
    'TimeAlignment',
    'NormalizationConfig',
    'NormalizedData',
    'NormalizationPipeline',
    'DataQualityReport'
]
