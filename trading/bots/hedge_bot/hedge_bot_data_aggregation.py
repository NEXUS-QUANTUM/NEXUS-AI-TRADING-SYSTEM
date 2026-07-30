# trading/bots/hedge_bot/hedge_bot_data_aggregation.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Aggregation Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Aggregation Module

This module provides comprehensive data aggregation capabilities for the
NEXUS Hedge Bot system. It aggregates data from multiple sources, timeframes,
and formats into unified views for analysis and decision-making.

The module covers:
- Time Series Aggregation
- Cross-Sectional Aggregation
- Multi-Source Aggregation
- Data Consolidation
- Data Resampling
- Data Rollup
- Data Pre-aggregation
- Incremental Aggregation
- Real-time Aggregation
- Batch Aggregation
- Aggregation Functions
- Custom Aggregators
"""

import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import threading
import time

logger = logging.getLogger(__name__)


# ============================================================
# AGGREGATION ENUMS
# ============================================================

class AggregationType(Enum):
    """Aggregation types"""
    TIME_SERIES = "time_series"
    CROSS_SECTIONAL = "cross_sectional"
    MULTI_SOURCE = "multi_source"
    ROLLUP = "rollup"
    RESAMPLE = "resample"
    INCREMENTAL = "incremental"
    REAL_TIME = "real_time"
    BATCH = "batch"


class AggregationFunction(Enum):
    """Aggregation functions"""
    SUM = "sum"
    MEAN = "mean"
    MEDIAN = "median"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    STD = "std"
    VAR = "var"
    FIRST = "first"
    LAST = "last"
    CUSTOM = "custom"


class AggregationFrequency(Enum):
    """Aggregation frequencies"""
    TICK = "tick"
    SECOND = "second"
    MINUTE = "minute"
    FIVE_MINUTE = "5minute"
    FIFTEEN_MINUTE = "15minute"
    THIRTY_MINUTE = "30minute"
    HOUR = "hour"
    FOUR_HOUR = "4hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass
class AggregationConfig:
    """Aggregation configuration"""
    type: AggregationType
    frequency: AggregationFrequency
    functions: List[AggregationFunction]
    columns: List[str]
    group_by: Optional[List[str]] = None
    window: Optional[int] = None
    custom_aggregators: Optional[Dict[str, Callable]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": self.type.value,
            "frequency": self.frequency.value,
            "functions": [f.value for f in self.functions],
            "columns": self.columns,
            "group_by": self.group_by,
            "window": self.window,
        }


@dataclass
class AggregationResult:
    """Aggregation result"""
    data: pd.DataFrame
    config: AggregationConfig
    source_count: int
    records_processed: int
    aggregation_time: float
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "config": self.config.to_dict(),
            "source_count": self.source_count,
            "records_processed": self.records_processed,
            "aggregation_time": self.aggregation_time,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


# ============================================================
# AGGREGATION ENGINE
# ============================================================

class AggregationEngine:
    """
    Comprehensive data aggregation engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the aggregation engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_frequency = self.config.get("default_frequency", AggregationFrequency.MINUTE)
        self.max_memory_mb = self.config.get("max_memory_mb", 1024)
        
        # State
        self.aggregation_cache: Dict[str, pd.DataFrame] = {}
        self.incremental_cache: Dict[str, Dict[str, Any]] = {}
        self.aggregation_history: List[AggregationResult] = []
        
        logger.info("Aggregation engine initialized")
    
    # ============================================================
    # TIME SERIES AGGREGATION
    # ============================================================
    
    def aggregate_time_series(
        self,
        data: pd.DataFrame,
        timestamp_col: str,
        frequency: AggregationFrequency,
        functions: List[AggregationFunction],
        columns: List[str],
        group_by: Optional[List[str]] = None
    ) -> AggregationResult:
        """
        Aggregate time series data
        
        Args:
            data: DataFrame
            timestamp_col: Timestamp column
            frequency: Aggregation frequency
            functions: Aggregation functions
            columns: Columns to aggregate
            group_by: Group by columns
            
        Returns:
            AggregationResult
        """
        start_time = time.time()
        
        # Set timestamp as index
        df = data.copy()
        if timestamp_col in df.columns:
            df[timestamp_col] = pd.to_datetime(df[timestamp_col])
            df = df.set_index(timestamp_col)
        
        # Resample
        freq_map = {
            AggregationFrequency.TICK: '1s',
            AggregationFrequency.SECOND: '1s',
            AggregationFrequency.MINUTE: '1min',
            AggregationFrequency.FIVE_MINUTE: '5min',
            AggregationFrequency.FIFTEEN_MINUTE: '15min',
            AggregationFrequency.THIRTY_MINUTE: '30min',
            AggregationFrequency.HOUR: '1h',
            AggregationFrequency.FOUR_HOUR: '4h',
            AggregationFrequency.DAY: '1d',
            AggregationFrequency.WEEK: '1w',
            AggregationFrequency.MONTH: '1M',
        }
        
        freq_str = freq_map.get(frequency, '1min')
        
        # Define aggregation functions
        agg_functions = {}
        for col in columns:
            if col in df.columns:
                agg_functions[col] = self._get_aggregation_functions(functions)
        
        # Perform resampling
        if group_by:
            # Group by first
            aggregated = df.groupby(group_by).resample(freq_str).agg(agg_functions)
        else:
            aggregated = df.resample(freq_str).agg(agg_functions)
        
        # Flatten MultiIndex columns if needed
        if isinstance(aggregated.columns, pd.MultiIndex):
            aggregated.columns = ['_'.join(col).strip() for col in aggregated.columns.values]
        
        aggregation_time = time.time() - start_time
        
        result = AggregationResult(
            data=aggregated,
            config=AggregationConfig(
                type=AggregationType.TIME_SERIES,
                frequency=frequency,
                functions=functions,
                columns=columns,
                group_by=group_by,
            ),
            source_count=len(df),
            records_processed=len(data),
            aggregation_time=aggregation_time,
            timestamp=datetime.now(),
        )
        
        self.aggregation_history.append(result)
        return result
    
    def _get_aggregation_functions(self, functions: List[AggregationFunction]) -> Dict[str, Any]:
        """Get aggregation functions for pandas"""
        func_map = {
            AggregationFunction.SUM: 'sum',
            AggregationFunction.MEAN: 'mean',
            AggregationFunction.MEDIAN: 'median',
            AggregationFunction.MIN: 'min',
            AggregationFunction.MAX: 'max',
            AggregationFunction.COUNT: 'count',
            AggregationFunction.STD: 'std',
            AggregationFunction.VAR: 'var',
            AggregationFunction.FIRST: 'first',
            AggregationFunction.LAST: 'last',
        }
        return {func_map.get(f, 'mean') for f in functions if f in func_map}
    
    # ============================================================
    # CROSS-SECTIONAL AGGREGATION
    # ============================================================
    
    def aggregate_cross_sectional(
        self,
        data: pd.DataFrame,
        group_by: List[str],
        functions: List[AggregationFunction],
        columns: List[str]
    ) -> AggregationResult:
        """
        Aggregate cross-sectional data
        
        Args:
            data: DataFrame
            group_by: Group by columns
            functions: Aggregation functions
            columns: Columns to aggregate
            
        Returns:
            AggregationResult
        """
        start_time = time.time()
        
        # Group by
        agg_functions = {}
        for col in columns:
            if col in data.columns:
                agg_functions[col] = self._get_aggregation_functions(functions)
        
        if not agg_functions:
            return AggregationResult(
                data=pd.DataFrame(),
                config=AggregationConfig(
                    type=AggregationType.CROSS_SECTIONAL,
                    frequency=AggregationFrequency.TICK,
                    functions=functions,
                    columns=columns,
                    group_by=group_by,
                ),
                source_count=0,
                records_processed=0,
                aggregation_time=0.0,
                timestamp=datetime.now(),
            )
        
        # Perform groupby
        aggregated = data.groupby(group_by).agg(agg_functions)
        
        # Flatten MultiIndex columns if needed
        if isinstance(aggregated.columns, pd.MultiIndex):
            aggregated.columns = ['_'.join(col).strip() for col in aggregated.columns.values]
        
        # Reset index
        aggregated = aggregated.reset_index()
        
        aggregation_time = time.time() - start_time
        
        result = AggregationResult(
            data=aggregated,
            config=AggregationConfig(
                type=AggregationType.CROSS_SECTIONAL,
                frequency=AggregationFrequency.TICK,
                functions=functions,
                columns=columns,
                group_by=group_by,
            ),
            source_count=len(data),
            records_processed=len(data),
            aggregation_time=aggregation_time,
            timestamp=datetime.now(),
        )
        
        self.aggregation_history.append(result)
        return result
    
    # ============================================================
    # MULTI-SOURCE AGGREGATION
    # ============================================================
    
    def aggregate_multi_source(
        self,
        sources: Dict[str, pd.DataFrame],
        merge_on: List[str],
        functions: List[AggregationFunction],
        columns: Dict[str, List[str]]
    ) -> AggregationResult:
        """
        Aggregate data from multiple sources
        
        Args:
            sources: Dictionary of source dataframes
            merge_on: Columns to merge on
            functions: Aggregation functions
            columns: Columns to aggregate per source
            
        Returns:
            AggregationResult
        """
        start_time = time.time()
        
        if not sources:
            return AggregationResult(
                data=pd.DataFrame(),
                config=AggregationConfig(
                    type=AggregationType.MULTI_SOURCE,
                    frequency=AggregationFrequency.TICK,
                    functions=functions,
                    columns=[],
                ),
                source_count=0,
                records_processed=0,
                aggregation_time=0.0,
                timestamp=datetime.now(),
            )
        
        # Merge all sources
        merged = None
        total_records = 0
        
        for source_name, df in sources.items():
            if merged is None:
                merged = df.copy()
            else:
                merged = pd.merge(merged, df, on=merge_on, how='outer', suffixes=('', f'_{source_name}'))
            total_records += len(df)
        
        # Rename columns to avoid conflicts
        # Apply aggregation
        agg_functions = {}
        for col_list in columns.values():
            for col in col_list:
                if col in merged.columns:
                    agg_functions[col] = self._get_aggregation_functions(functions)
        
        if agg_functions:
            aggregated = merged.agg(agg_functions)
        else:
            aggregated = merged
        
        aggregation_time = time.time() - start_time
        
        result = AggregationResult(
            data=aggregated if isinstance(aggregated, pd.DataFrame) else pd.DataFrame([aggregated]),
            config=AggregationConfig(
                type=AggregationType.MULTI_SOURCE,
                frequency=AggregationFrequency.TICK,
                functions=functions,
                columns=list(columns.keys()),
            ),
            source_count=len(sources),
            records_processed=total_records,
            aggregation_time=aggregation_time,
            timestamp=datetime.now(),
        )
        
        self.aggregation_history.append(result)
        return result
    
    # ============================================================
    # INCREMENTAL AGGREGATION
    # ============================================================
    
    def aggregate_incremental(
        self,
        data: pd.DataFrame,
        key: str,
        timestamp_col: str,
        frequency: AggregationFrequency,
        functions: List[AggregationFunction],
        columns: List[str]
    ) -> AggregationResult:
        """
        Perform incremental aggregation
        
        Args:
            data: New data
            key: Cache key
            timestamp_col: Timestamp column
            frequency: Aggregation frequency
            functions: Aggregation functions
            columns: Columns to aggregate
            
        Returns:
            AggregationResult
        """
        start_time = time.time()
        
        # Get cached data
        cached = self.incremental_cache.get(key, {})
        cached_data = cached.get("data")
        
        if cached_data is not None:
            # Merge with cached data
            df = pd.concat([cached_data, data], ignore_index=True)
            df = df.drop_duplicates(subset=[timestamp_col], keep='last')
            df = df.sort_values(timestamp_col)
        else:
            df = data.copy()
        
        # Perform aggregation
        result = self.aggregate_time_series(
            df,
            timestamp_col,
            frequency,
            functions,
            columns,
        )
        
        # Update cache
        self.incremental_cache[key] = {
            "data": df,
            "last_aggregation": datetime.now(),
        }
        
        aggregation_time = time.time() - start_time
        result.aggregation_time = aggregation_time
        
        self.aggregation_history.append(result)
        return result
    
    # ============================================================
    # DATA ROLLUP
    # ============================================================
    
    def rollup_data(
        self,
        data: pd.DataFrame,
        dimensions: List[str],
        measures: List[str],
        functions: List[AggregationFunction]
    ) -> AggregationResult:
        """
        Perform data rollup
        
        Args:
            data: DataFrame
            dimensions: Rollup dimensions
            measures: Measures to aggregate
            functions: Aggregation functions
            
        Returns:
            AggregationResult
        """
        start_time = time.time()
        
        # Create rollup combinations
        rollup_results = []
        
        for i in range(len(dimensions) + 1):
            # Select subset of dimensions
            subset = dimensions[:i]
            
            if subset:
                # Group by subset
                grouped = data.groupby(subset)
                agg_functions = {}
                for measure in measures:
                    if measure in data.columns:
                        agg_functions[measure] = self._get_aggregation_functions(functions)
                
                if agg_functions:
                    rollup = grouped.agg(agg_functions).reset_index()
                    
                    # Add rollup level
                    rollup['rollup_level'] = i
                    rollup_results.append(rollup)
        
        # Combine rollup results
        if rollup_results:
            combined = pd.concat(rollup_results, ignore_index=True)
        else:
            combined = data.copy()
        
        aggregation_time = time.time() - start_time
        
        result = AggregationResult(
            data=combined,
            config=AggregationConfig(
                type=AggregationType.ROLLUP,
                frequency=AggregationFrequency.TICK,
                functions=functions,
                columns=measures,
                group_by=dimensions,
            ),
            source_count=len(data),
            records_processed=len(data),
            aggregation_time=aggregation_time,
            timestamp=datetime.now(),
        )
        
        self.aggregation_history.append(result)
        return result
    
    # ============================================================
    # CUSTOM AGGREGATION
    # ============================================================
    
    def aggregate_custom(
        self,
        data: pd.DataFrame,
        aggregator: Callable[[pd.DataFrame], pd.DataFrame]
    ) -> AggregationResult:
        """
        Apply custom aggregation
        
        Args:
            data: DataFrame
            aggregator: Custom aggregation function
            
        Returns:
            AggregationResult
        """
        start_time = time.time()
        
        result_data = aggregator(data)
        
        aggregation_time = time.time() - start_time
        
        result = AggregationResult(
            data=result_data,
            config=AggregationConfig(
                type=AggregationType.CROSS_SECTIONAL,
                frequency=AggregationFrequency.TICK,
                functions=[],
                columns=[],
            ),
            source_count=len(data),
            records_processed=len(data),
            aggregation_time=aggregation_time,
            timestamp=datetime.now(),
        )
        
        self.aggregation_history.append(result)
        return result
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get aggregation statistics
        
        Returns:
            Statistics dictionary
        """
        total_records = sum(r.records_processed for r in self.aggregation_history)
        
        return {
            "total_aggregations": len(self.aggregation_history),
            "total_records_processed": total_records,
            "avg_aggregation_time": sum(r.aggregation_time for r in self.aggregation_history) / len(self.aggregation_history) if self.aggregation_history else 0,
            "cache_size": len(self.aggregation_cache) + len(self.incremental_cache),
            "default_frequency": self.default_frequency.value,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "AggregationType",
    "AggregationFunction",
    "AggregationFrequency",
    
    # Dataclasses
    "AggregationConfig",
    "AggregationResult",
    
    # Classes
    "AggregationEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
