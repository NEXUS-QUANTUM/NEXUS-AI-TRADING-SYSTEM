# trading/bots/hedge_bot/hedge_bot_data_adapt.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Adaptation Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Adaptation Module

This module provides comprehensive data adaptation and transformation
capabilities for the NEXUS Hedge Bot system. It handles data from
multiple sources, formats, and structures, adapting them to the
bot's internal data models.

The module covers:
- Data Source Adapters
- Data Format Converters
- Data Normalization
- Data Validation
- Data Enrichment
- Data Cleaning
- Data Aggregation
- Data Resampling
- Data Merging
- Data Filtering
- Data Transformation
- Data Quality Checking
"""

import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import re
import hashlib

logger = logging.getLogger(__name__)


# ============================================================
# DATA ADAPTATION ENUMS
# ============================================================

class DataSource(Enum):
    """Data source types"""
    EXCHANGE = "exchange"
    DATABASE = "database"
    FILE = "file"
    API = "api"
    WEBSOCKET = "websocket"
    CACHE = "cache"
    WEBHOOK = "webhook"


class DataFormat(Enum):
    """Data formats"""
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"
    ORC = "orc"
    EXCEL = "excel"
    HDF5 = "hdf5"
    SQL = "sql"
    PROTOBUF = "protobuf"
    XML = "xml"
    YAML = "yaml"


class DataFrequency(Enum):
    """Data frequencies"""
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
class DataSchema:
    """Data schema definition"""
    fields: Dict[str, Dict[str, Any]]
    required: List[str]
    optional: List[str]
    version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "fields": self.fields,
            "required": self.required,
            "optional": self.optional,
            "version": self.version,
        }


@dataclass
class DataAdapterConfig:
    """Data adapter configuration"""
    source: DataSource
    format: DataFormat
    frequency: DataFrequency
    mapping: Dict[str, str]
    validation: Dict[str, Any]
    transformations: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# DATA ADAPTER BASE CLASS
# ============================================================

class BaseDataAdapter:
    """Base data adapter class"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get("name", "base_adapter")
        self.source = config.get("source", "unknown")
        self.format = config.get("format", "json")
        self.mapping = config.get("mapping", {})
        self.transformations = config.get("transformations", [])
        self.validation_rules = config.get("validation", {})
        
    def adapt(self, data: Any) -> pd.DataFrame:
        """
        Adapt data to internal format
        
        Args:
            data: Input data
            
        Returns:
            Adapted DataFrame
        """
        # Parse data
        parsed = self._parse_data(data)
        
        # Validate data
        self._validate_data(parsed)
        
        # Transform data
        transformed = self._transform_data(parsed)
        
        # Normalize data
        normalized = self._normalize_data(transformed)
        
        return normalized
    
    def _parse_data(self, data: Any) -> Any:
        """Parse input data"""
        raise NotImplementedError
    
    def _validate_data(self, data: Any) -> None:
        """Validate data"""
        # Implement validation logic
        pass
    
    def _transform_data(self, data: Any) -> Any:
        """Transform data"""
        # Implement transformation logic
        return data
    
    def _normalize_data(self, data: Any) -> pd.DataFrame:
        """Normalize data to DataFrame"""
        if isinstance(data, pd.DataFrame):
            return data
        elif isinstance(data, dict):
            return pd.DataFrame([data])
        elif isinstance(data, list):
            return pd.DataFrame(data)
        else:
            raise ValueError(f"Unsupported data type: {type(data)}")


# ============================================================
# DATA ADAPTER IMPLEMENTATIONS
# ============================================================

class ExchangeDataAdapter(BaseDataAdapter):
    """Exchange data adapter"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.exchange = config.get("exchange", "binance")
        self.symbols = config.get("symbols", [])
        
    def _parse_data(self, data: Any) -> Any:
        """Parse exchange data"""
        # Convert exchange data to internal format
        if isinstance(data, dict):
            # Handle exchange websocket/ticker data
            return {
                "symbol": data.get("symbol", ""),
                "timestamp": data.get("timestamp", datetime.now()),
                "open": data.get("open", 0),
                "high": data.get("high", 0),
                "low": data.get("low", 0),
                "close": data.get("close", 0),
                "volume": data.get("volume", 0),
                "bid": data.get("bid", 0),
                "ask": data.get("ask", 0),
            }
        return data


class FileDataAdapter(BaseDataAdapter):
    """File data adapter"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.file_path = config.get("file_path")
        self.delimiter = config.get("delimiter", ",")
        self.encoding = config.get("encoding", "utf-8")
        
    def _parse_data(self, data: Any) -> Any:
        """Parse file data"""
        if isinstance(data, str):
            # File path
            self.file_path = data
        
        if self.file_path and os.path.exists(self.file_path):
            if self.format == "csv":
                return pd.read_csv(self.file_path, delimiter=self.delimiter, encoding=self.encoding)
            elif self.format == "json":
                return pd.read_json(self.file_path)
            elif self.format == "parquet":
                return pd.read_parquet(self.file_path)
            elif self.format == "excel":
                return pd.read_excel(self.file_path)
        
        return data


class APIDataAdapter(BaseDataAdapter):
    """API data adapter"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get("api_url")
        self.api_key = config.get("api_key")
        self.headers = config.get("headers", {})
        self.params = config.get("params", {})
    
    def _parse_data(self, data: Any) -> Any:
        """Parse API data"""
        if isinstance(data, dict):
            # Check for pagination
            if "data" in data:
                return data["data"]
            elif "results" in data:
                return data["results"]
            elif "items" in data:
                return data["items"]
        return data


class WebSocketDataAdapter(BaseDataAdapter):
    """WebSocket data adapter"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.ws_url = config.get("ws_url")
        self.subscriptions = config.get("subscriptions", [])
    
    def _parse_data(self, data: Any) -> Any:
        """Parse WebSocket data"""
        if isinstance(data, dict):
            # Handle WebSocket message format
            if "data" in data:
                return data["data"]
            elif "payload" in data:
                return data["payload"]
        return data


# ============================================================
# DATA ADAPTER FACTORY
# ============================================================

class DataAdapterFactory:
    """Factory for creating data adapters"""
    
    _adapters: Dict[str, type] = {}
    
    @classmethod
    def register_adapter(cls, name: str, adapter_class: type) -> None:
        """Register an adapter class"""
        cls._adapters[name] = adapter_class
    
    @classmethod
    def create_adapter(cls, config: Dict[str, Any]) -> BaseDataAdapter:
        """Create a data adapter"""
        adapter_type = config.get("type", "base")
        
        if adapter_type == "exchange":
            return ExchangeDataAdapter(config)
        elif adapter_type == "file":
            return FileDataAdapter(config)
        elif adapter_type == "api":
            return APIDataAdapter(config)
        elif adapter_type == "websocket":
            return WebSocketDataAdapter(config)
        elif adapter_type in cls._adapters:
            return cls._adapters[adapter_type](config)
        else:
            return BaseDataAdapter(config)


# ============================================================
# DATA ADAPTATION ENGINE
# ============================================================

class DataAdaptationEngine:
    """
    Comprehensive data adaptation engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data adaptation engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.adapters: Dict[str, BaseDataAdapter] = {}
        self.schemas: Dict[str, DataSchema] = {}
        self.transformation_pipelines: Dict[str, List[Callable]] = {}
        
        # Register default schemas
        self._init_default_schemas()
        
        logger.info("Data adaptation engine initialized")
    
    # ============================================================
    # SCHEMA MANAGEMENT
    # ============================================================
    
    def _init_default_schemas(self) -> None:
        """Initialize default data schemas"""
        # Market data schema
        market_schema = DataSchema(
            fields={
                "symbol": {"type": "str", "required": True},
                "timestamp": {"type": "datetime", "required": True},
                "open": {"type": "float", "required": True},
                "high": {"type": "float", "required": True},
                "low": {"type": "float", "required": True},
                "close": {"type": "float", "required": True},
                "volume": {"type": "float", "required": False},
                "bid": {"type": "float", "required": False},
                "ask": {"type": "float", "required": False},
            },
            required=["symbol", "timestamp", "open", "high", "low", "close"],
            optional=["volume", "bid", "ask"],
        )
        self.schemas["market_data"] = market_schema
        
        # Position schema
        position_schema = DataSchema(
            fields={
                "symbol": {"type": "str", "required": True},
                "side": {"type": "str", "required": True},
                "quantity": {"type": "float", "required": True},
                "entry_price": {"type": "float", "required": True},
                "current_price": {"type": "float", "required": True},
                "unrealized_pnl": {"type": "float", "required": False},
                "status": {"type": "str", "required": False},
            },
            required=["symbol", "side", "quantity", "entry_price", "current_price"],
            optional=["unrealized_pnl", "status"],
        )
        self.schemas["position_data"] = position_schema
        
        # Order schema
        order_schema = DataSchema(
            fields={
                "symbol": {"type": "str", "required": True},
                "side": {"type": "str", "required": True},
                "type": {"type": "str", "required": True},
                "quantity": {"type": "float", "required": True},
                "price": {"type": "float", "required": False},
                "status": {"type": "str", "required": True},
                "timestamp": {"type": "datetime", "required": True},
            },
            required=["symbol", "side", "type", "quantity", "status", "timestamp"],
            optional=["price"],
        )
        self.schemas["order_data"] = order_schema
        
        logger.info(f"Initialized {len(self.schemas)} schemas")
    
    def register_schema(self, name: str, schema: DataSchema) -> None:
        """
        Register a data schema
        
        Args:
            name: Schema name
            schema: DataSchema object
        """
        self.schemas[name] = schema
        logger.info(f"Registered schema: {name}")
    
    def get_schema(self, name: str) -> Optional[DataSchema]:
        """
        Get a data schema
        
        Args:
            name: Schema name
            
        Returns:
            DataSchema or None
        """
        return self.schemas.get(name)
    
    # ============================================================
    # ADAPTER MANAGEMENT
    # ============================================================
    
    def register_adapter(self, name: str, adapter: BaseDataAdapter) -> None:
        """
        Register a data adapter
        
        Args:
            name: Adapter name
            adapter: Data adapter instance
        """
        self.adapters[name] = adapter
        logger.info(f"Registered adapter: {name}")
    
    def get_adapter(self, name: str) -> Optional[BaseDataAdapter]:
        """
        Get a data adapter
        
        Args:
            name: Adapter name
            
        Returns:
            Data adapter or None
        """
        return self.adapters.get(name)
    
    def create_adapter(self, config: Dict[str, Any]) -> BaseDataAdapter:
        """
        Create a data adapter
        
        Args:
            config: Adapter configuration
            
        Returns:
            Data adapter instance
        """
        adapter = DataAdapterFactory.create_adapter(config)
        self.register_adapter(adapter.name, adapter)
        return adapter
    
    # ============================================================
    # DATA ADAPTATION
    # ============================================================
    
    def adapt_data(
        self,
        data: Any,
        adapter_name: str,
        schema_name: Optional[str] = None,
        transformations: Optional[List[Callable]] = None
    ) -> pd.DataFrame:
        """
        Adapt data using a registered adapter
        
        Args:
            data: Input data
            adapter_name: Adapter name
            schema_name: Schema name for validation
            transformations: Additional transformations
            
        Returns:
            Adapted DataFrame
        """
        # Get adapter
        adapter = self.get_adapter(adapter_name)
        if not adapter:
            raise ValueError(f"Adapter not found: {adapter_name}")
        
        # Adapt data
        df = adapter.adapt(data)
        
        # Apply schema validation
        if schema_name:
            self.validate_data(df, schema_name)
        
        # Apply transformations
        if transformations:
            for transform in transformations:
                df = transform(df)
        
        # Apply registered pipeline
        if adapter_name in self.transformation_pipelines:
            for transform in self.transformation_pipelines[adapter_name]:
                df = transform(df)
        
        return df
    
    def adapt_batch(
        self,
        data_list: List[Any],
        adapter_name: str,
        schema_name: Optional[str] = None,
        transformations: Optional[List[Callable]] = None
    ) -> pd.DataFrame:
        """
        Adapt a batch of data
        
        Args:
            data_list: List of input data
            adapter_name: Adapter name
            schema_name: Schema name for validation
            transformations: Additional transformations
            
        Returns:
            Adapted DataFrame
        """
        dfs = []
        for data in data_list:
            df = self.adapt_data(data, adapter_name, schema_name, transformations)
            dfs.append(df)
        
        return pd.concat(dfs, ignore_index=True)
    
    # ============================================================
    # DATA TRANSFORMATION
    # ============================================================
    
    def register_transformation_pipeline(
        self,
        adapter_name: str,
        transformations: List[Callable]
    ) -> None:
        """
        Register a transformation pipeline for an adapter
        
        Args:
            adapter_name: Adapter name
            transformations: List of transformation functions
        """
        self.transformation_pipelines[adapter_name] = transformations
        logger.info(f"Registered pipeline for adapter: {adapter_name}")
    
    def create_transformation(self, config: Dict[str, Any]) -> Callable:
        """
        Create a transformation function
        
        Args:
            config: Transformation configuration
            
        Returns:
            Transformation function
        """
        transform_type = config.get("type", "identity")
        
        if transform_type == "rename_columns":
            mapping = config.get("mapping", {})
            return lambda df: df.rename(columns=mapping)
        
        elif transform_type == "select_columns":
            columns = config.get("columns", [])
            return lambda df: df[columns] if all(c in df.columns for c in columns) else df
        
        elif transform_type == "filter_rows":
            query = config.get("query", "")
            return lambda df: df.query(query) if query else df
        
        elif transform_type == "add_column":
            column = config.get("column", "")
            value = config.get("value", 0)
            return lambda df: df.assign(**{column: value}) if column else df
        
        elif transform_type == "convert_types":
            mapping = config.get("mapping", {})
            return lambda df: df.astype(mapping) if mapping else df
        
        elif transform_type == "resample":
            frequency = config.get("frequency", "1min")
            agg_funcs = config.get("agg_funcs", {"close": "last", "volume": "sum"})
            return lambda df: df.resample(frequency, on="timestamp").agg(agg_funcs)
        
        elif transform_type == "fillna":
            value = config.get("value", 0)
            columns = config.get("columns", [])
            return lambda df: df.fillna(value, subset=columns) if columns else df.fillna(value)
        
        elif transform_type == "dropna":
            columns = config.get("columns", [])
            return lambda df: df.dropna(subset=columns) if columns else df.dropna()
        
        else:
            # Identity transformation
            return lambda df: df
    
    # ============================================================
    # DATA VALIDATION
    # ============================================================
    
    def validate_data(
        self,
        df: pd.DataFrame,
        schema_name: str,
        strict: bool = True
    ) -> Dict[str, Any]:
        """
        Validate data against a schema
        
        Args:
            df: DataFrame to validate
            schema_name: Schema name
            strict: Strict validation
            
        Returns:
            Validation results
        """
        schema = self.get_schema(schema_name)
        if not schema:
            raise ValueError(f"Schema not found: {schema_name}")
        
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "missing_required": [],
            "invalid_types": [],
        }
        
        # Check required fields
        for field in schema.required:
            if field not in df.columns:
                results["errors"].append(f"Missing required field: {field}")
                results["missing_required"].append(field)
                results["valid"] = False
        
        # Check field types
        for field, field_info in schema.fields.items():
            if field in df.columns:
                expected_type = field_info.get("type", "any")
                actual_type = df[field].dtype
                
                # Simple type checking
                if expected_type == "str" and actual_type != "object":
                    if strict:
                        results["errors"].append(f"Field {field} expected str, got {actual_type}")
                        results["valid"] = False
                    else:
                        results["warnings"].append(f"Field {field} expected str, got {actual_type}")
                        try:
                            df[field] = df[field].astype(str)
                        except:
                            pass
        
        return results
    
    # ============================================================
    # DATA QUALITY
    # ============================================================
    
    def check_data_quality(
        self,
        df: pd.DataFrame,
        checks: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check data quality
        
        Args:
            df: DataFrame to check
            checks: Quality checks configuration
            
        Returns:
            Quality results
        """
        results = {
            "passed": True,
            "checks": {},
        }
        
        # Check for null values
        if checks.get("check_nulls", True):
            null_counts = df.isnull().sum()
            null_cols = null_counts[null_counts > 0].to_dict()
            results["checks"]["nulls"] = null_cols
            if null_cols:
                results["passed"] = False
        
        # Check for duplicates
        if checks.get("check_duplicates", True):
            duplicate_count = df.duplicated().sum()
            results["checks"]["duplicates"] = duplicate_count
            if duplicate_count > 0:
                results["passed"] = False
        
        # Check for outliers
        if checks.get("check_outliers", True):
            columns = checks.get("outlier_columns", [])
            outliers = {}
            for col in columns:
                if col in df.columns:
                    q1 = df[col].quantile(0.25)
                    q3 = df[col].quantile(0.75)
                    iqr = q3 - q1
                    lower = q1 - 1.5 * iqr
                    upper = q3 + 1.5 * iqr
                    outlier_count = ((df[col] < lower) | (df[col] > upper)).sum()
                    if outlier_count > 0:
                        outliers[col] = outlier_count
            results["checks"]["outliers"] = outliers
            if outliers:
                results["passed"] = False
        
        # Check data ranges
        if checks.get("check_ranges", True):
            ranges = checks.get("ranges", {})
            range_violations = {}
            for col, range_vals in ranges.items():
                if col in df.columns:
                    min_val = range_vals.get("min")
                    max_val = range_vals.get("max")
                    if min_val is not None:
                        violations = (df[col] < min_val).sum()
                        if violations > 0:
                            range_violations[f"{col}_below_min"] = violations
                    if max_val is not None:
                        violations = (df[col] > max_val).sum()
                        if violations > 0:
                            range_violations[f"{col}_above_max"] = violations
            results["checks"]["range_violations"] = range_violations
            if range_violations:
                results["passed"] = False
        
        return results
    
    # ============================================================
    # DATA ENRICHMENT
    # ============================================================
    
    def enrich_data(
        self,
        df: pd.DataFrame,
        enrichment_config: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Enrich data with additional information
        
        Args:
            df: DataFrame to enrich
            enrichment_config: Enrichment configuration
            
        Returns:
            Enriched DataFrame
        """
        # Add derived columns
        if "derived_columns" in enrichment_config:
            for col, formula in enrichment_config["derived_columns"].items():
                try:
                    df[col] = df.eval(formula)
                except Exception as e:
                    logger.warning(f"Failed to add derived column {col}: {e}")
        
        # Add metadata
        if "metadata" in enrichment_config:
            for col, value in enrichment_config["metadata"].items():
                df[col] = value
        
        # Add timestamp
        if enrichment_config.get("add_timestamp", False):
            df["timestamp"] = datetime.now()
        
        # Add source
        if enrichment_config.get("add_source", False):
            df["source"] = enrichment_config.get("source_name", "unknown")
        
        return df
    
    # ============================================================
    # DATA CLEANING
    # ============================================================
    
    def clean_data(
        self,
        df: pd.DataFrame,
        cleaning_config: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Clean data
        
        Args:
            df: DataFrame to clean
            cleaning_config: Cleaning configuration
            
        Returns:
            Cleaned DataFrame
        """
        # Remove duplicates
        if cleaning_config.get("remove_duplicates", False):
            df = df.drop_duplicates()
        
        # Remove nulls
        if cleaning_config.get("remove_nulls", False):
            columns = cleaning_config.get("null_columns", [])
            if columns:
                df = df.dropna(subset=columns)
            else:
                df = df.dropna()
        
        # Fill nulls
        if "fill_nulls" in cleaning_config:
            for col, value in cleaning_config["fill_nulls"].items():
                if col in df.columns:
                    df[col] = df[col].fillna(value)
        
        # Remove outliers
        if cleaning_config.get("remove_outliers", False):
            columns = cleaning_config.get("outlier_columns", [])
            for col in columns:
                if col in df.columns:
                    q1 = df[col].quantile(0.25)
                    q3 = df[col].quantile(0.75)
                    iqr = q3 - q1
                    lower = q1 - 1.5 * iqr
                    upper = q3 + 1.5 * iqr
                    df = df[(df[col] >= lower) & (df[col] <= upper)]
        
        return df
    
    # ============================================================
    # DATA AGGREGATION
    # ============================================================
    
    def aggregate_data(
        self,
        df: pd.DataFrame,
        aggregation_config: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Aggregate data
        
        Args:
            df: DataFrame to aggregate
            aggregation_config: Aggregation configuration
            
        Returns:
            Aggregated DataFrame
        """
        group_by = aggregation_config.get("group_by", [])
        agg_funcs = aggregation_config.get("agg_funcs", {})
        
        if group_by and agg_funcs:
            return df.groupby(group_by).agg(agg_funcs).reset_index()
        elif group_by:
            return df.groupby(group_by).mean().reset_index()
        else:
            return df
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get engine statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_adapters": len(self.adapters),
            "total_schemas": len(self.schemas),
            "total_pipelines": len(self.transformation_pipelines),
            "adapters": list(self.adapters.keys()),
            "schemas": list(self.schemas.keys()),
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "DataFormat",
    "DataSource",
    "DataFrequency",
    
    # Dataclasses
    "DataSchema",
    "DataAdapterConfig",
    
    # Classes
    "BaseDataAdapter",
    "ExchangeDataAdapter",
    "FileDataAdapter",
    "APIDataAdapter",
    "WebSocketDataAdapter",
    "DataAdapterFactory",
    "DataAdaptationEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
