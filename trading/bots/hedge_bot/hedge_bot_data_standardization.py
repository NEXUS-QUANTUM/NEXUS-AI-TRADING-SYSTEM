# trading/bots/hedge_bot/hedge_bot_data_standardization.py

import asyncio
import logging
import time
import json
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler, MaxAbsScaler, QuantileTransformer, PowerTransformer

logger = logging.getLogger(__name__)


class StandardizationType(str, Enum):
    Z_SCORE = "z_score"
    MIN_MAX = "min_max"
    ROBUST = "robust"
    MAX_ABS = "max_abs"
    QUANTILE = "quantile"
    POWER = "power"
    LOG = "log"
    SQRT = "sqrt"
    BOX_COX = "box_cox"
    YEO_JOHNSON = "yeo_johnson"
    RANK = "rank"
    UNIT_VECTOR = "unit_vector"


class NormalizationType(str, Enum):
    L1 = "l1"
    L2 = "l2"
    MAX = "max"
    STANDARD = "standard"


class MissingValueStrategy(str, Enum):
    DROP = "drop"
    FILL_MEAN = "fill_mean"
    FILL_MEDIAN = "fill_median"
    FILL_MODE = "fill_mode"
    FILL_CONSTANT = "fill_constant"
    FILL_FORWARD = "fill_forward"
    FILL_BACKWARD = "fill_backward"
    INTERPOLATE = "interpolate"
    SKIP = "skip"


@dataclass
class StandardizationConfig:
    id: str
    name: str
    type: StandardizationType
    columns: List[str]
    with_mean: bool = True
    with_std: bool = True
    range_min: float = 0.0
    range_max: float = 1.0
    quantile_range: Tuple[float, float] = (25.0, 75.0)
    n_quantiles: int = 1000
    output_distribution: str = "uniform"
    power_type: str = "yeo-johnson"
    missing_strategy: MissingValueStrategy = MissingValueStrategy.FILL_MEAN
    fill_value: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class StandardizationResult:
    id: str
    config_id: str
    original_data: pd.DataFrame
    standardized_data: pd.DataFrame
    scaler: Any
    statistics: Dict[str, Any]
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataValidator:
    id: str
    name: str
    rules: Dict[str, Any]
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class ValidationResult:
    id: str
    validator_id: str
    passed: bool
    errors: List[Dict[str, Any]]
    warnings: List[str]
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataStandardizationManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._configs: Dict[str, StandardizationConfig] = {}
        self._results: Dict[str, StandardizationResult] = {}
        self._validators: Dict[str, DataValidator] = {}
        self._validation_results: Dict[str, ValidationResult] = {}
        self._observers: List[Callable] = []
        self._running = False
        self._scaler_cache: Dict[str, Any] = {}
        
        self._initialize_default_configs()
        self._initialize_default_validators()

    def _initialize_default_configs(self) -> None:
        default_configs = [
            StandardizationConfig(
                id="z_score_default",
                name="Default Z-Score Standardization",
                type=StandardizationType.Z_SCORE,
                columns=["price", "volume", "pnl"]
            ),
            StandardizationConfig(
                id="min_max_default",
                name="Default Min-Max Normalization",
                type=StandardizationType.MIN_MAX,
                columns=["price", "volume", "pnl"],
                range_min=0.0,
                range_max=1.0
            ),
            StandardizationConfig(
                id="robust_default",
                name="Default Robust Scaling",
                type=StandardizationType.ROBUST,
                columns=["price", "volume", "pnl"]
            ),
            StandardizationConfig(
                id="log_transform",
                name="Log Transformation",
                type=StandardizationType.LOG,
                columns=["price", "volume"]
            )
        ]
        
        for config in default_configs:
            self._configs[config.id] = config

    def _initialize_default_validators(self) -> None:
        default_validators = [
            DataValidator(
                id="null_check",
                name="Null Value Check",
                rules={
                    "max_null_percentage": 0.05,
                    "columns": ["price", "volume", "pnl"]
                }
            ),
            DataValidator(
                id="range_check",
                name="Value Range Check",
                rules={
                    "ranges": {
                        "price": (0, 1000000),
                        "volume": (0, 10000000),
                        "pnl": (-100000, 100000)
                    }
                }
            ),
            DataValidator(
                id="type_check",
                name="Data Type Check",
                rules={
                    "types": {
                        "price": "float",
                        "volume": "float",
                        "pnl": "float",
                        "symbol": "string"
                    }
                }
            )
        ]
        
        for validator in default_validators:
            self._validators[validator.id] = validator

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_config(
        self,
        name: str,
        type: StandardizationType,
        columns: List[str],
        with_mean: bool = True,
        with_std: bool = True,
        range_min: float = 0.0,
        range_max: float = 1.0,
        quantile_range: Tuple[float, float] = (25.0, 75.0),
        n_quantiles: int = 1000,
        output_distribution: str = "uniform",
        power_type: str = "yeo-johnson",
        missing_strategy: MissingValueStrategy = MissingValueStrategy.FILL_MEAN,
        fill_value: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StandardizationConfig:
        async with self._lock:
            config_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            config = StandardizationConfig(
                id=config_id,
                name=name,
                type=type,
                columns=columns,
                with_mean=with_mean,
                with_std=with_std,
                range_min=range_min,
                range_max=range_max,
                quantile_range=quantile_range,
                n_quantiles=n_quantiles,
                output_distribution=output_distribution,
                power_type=power_type,
                missing_strategy=missing_strategy,
                fill_value=fill_value,
                metadata=metadata or {}
            )
            
            self._configs[config_id] = config
            await self._notify_observers("config_created", config)
            return config

    async def standardize(
        self,
        data: Union[pd.DataFrame, List[Dict], Dict],
        config_id: str,
        fit_scaler: bool = True
    ) -> Optional[StandardizationResult]:
        async with self._lock:
            if config_id not in self._configs:
                return None
            
            config = self._configs[config_id]
            
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
            elif isinstance(data, pd.DataFrame):
                df = data.copy()
            else:
                return None
            
            df = await self._handle_missing_values(df, config)
            
            scaler = self._get_scaler(config)
            
            if fit_scaler:
                scaler.fit(df[config.columns])
                self._scaler_cache[config_id] = scaler
            else:
                scaler = self._scaler_cache.get(config_id)
                if scaler is None:
                    return None
            
            scaled_data = scaler.transform(df[config.columns])
            
            standardized_df = df.copy()
            standardized_df[config.columns] = scaled_data
            
            result = StandardizationResult(
                id=hashlib.md5(f"{config_id}_{time.time()}".encode()).hexdigest(),
                config_id=config_id,
                original_data=df,
                standardized_data=standardized_df,
                scaler=scaler,
                statistics=await self._compute_statistics(df, standardized_df, config),
                timestamp=time.time()
            )
            
            self._results[result.id] = result
            await self._notify_observers("standardization_completed", result)
            return result

    async def _handle_missing_values(self, df: pd.DataFrame, config: StandardizationConfig) -> pd.DataFrame:
        if config.missing_strategy == MissingValueStrategy.DROP:
            df = df.dropna(subset=config.columns)
        
        elif config.missing_strategy == MissingValueStrategy.FILL_MEAN:
            for col in config.columns:
                if col in df.columns:
                    df[col] = df[col].fillna(df[col].mean())
        
        elif config.missing_strategy == MissingValueStrategy.FILL_MEDIAN:
            for col in config.columns:
                if col in df.columns:
                    df[col] = df[col].fillna(df[col].median())
        
        elif config.missing_strategy == MissingValueStrategy.FILL_MODE:
            for col in config.columns:
                if col in df.columns:
                    df[col] = df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else 0)
        
        elif config.missing_strategy == MissingValueStrategy.FILL_CONSTANT:
            for col in config.columns:
                if col in df.columns:
                    df[col] = df[col].fillna(config.fill_value or 0)
        
        elif config.missing_strategy == MissingValueStrategy.FILL_FORWARD:
            df[config.columns] = df[config.columns].fillna(method='ffill')
        
        elif config.missing_strategy == MissingValueStrategy.FILL_BACKWARD:
            df[config.columns] = df[config.columns].fillna(method='bfill')
        
        elif config.missing_strategy == MissingValueStrategy.INTERPOLATE:
            df[config.columns] = df[config.columns].interpolate(method='linear')
        
        return df

    def _get_scaler(self, config: StandardizationConfig) -> Any:
        if config.type == StandardizationType.Z_SCORE:
            return StandardScaler(with_mean=config.with_mean, with_std=config.with_std)
        elif config.type == StandardizationType.MIN_MAX:
            return MinMaxScaler(feature_range=(config.range_min, config.range_max))
        elif config.type == StandardizationType.ROBUST:
            return RobustScaler(quantile_range=config.quantile_range)
        elif config.type == StandardizationType.MAX_ABS:
            return MaxAbsScaler()
        elif config.type == StandardizationType.QUANTILE:
            return QuantileTransformer(
                n_quantiles=config.n_quantiles,
                output_distribution=config.output_distribution
            )
        elif config.type == StandardizationType.POWER:
            return PowerTransformer(method=config.power_type)
        elif config.type == StandardizationType.LOG:
            return LogTransformer()
        elif config.type == StandardizationType.SQRT:
            return SqrtTransformer()
        else:
            return StandardScaler()

    async def _compute_statistics(
        self,
        original: pd.DataFrame,
        standardized: pd.DataFrame,
        config: StandardizationConfig
    ) -> Dict[str, Any]:
        stats = {}
        
        for col in config.columns:
            if col in original.columns and col in standardized.columns:
                stats[col] = {
                    "original": {
                        "mean": float(original[col].mean()),
                        "std": float(original[col].std()),
                        "min": float(original[col].min()),
                        "max": float(original[col].max()),
                        "median": float(original[col].median()),
                        "q25": float(original[col].quantile(0.25)),
                        "q75": float(original[col].quantile(0.75))
                    },
                    "standardized": {
                        "mean": float(standardized[col].mean()),
                        "std": float(standardized[col].std()),
                        "min": float(standardized[col].min()),
                        "max": float(standardized[col].max()),
                        "median": float(standardized[col].median()),
                        "q25": float(standardized[col].quantile(0.25)),
                        "q75": float(standardized[col].quantile(0.75))
                    }
                }
        
        return stats

    async def create_validator(
        self,
        name: str,
        rules: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> DataValidator:
        async with self._lock:
            validator_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            validator = DataValidator(
                id=validator_id,
                name=name,
                rules=rules,
                metadata=metadata or {}
            )
            
            self._validators[validator_id] = validator
            await self._notify_observers("validator_created", validator)
            return validator

    async def validate_data(
        self,
        data: Union[pd.DataFrame, List[Dict], Dict],
        validator_id: str
    ) -> ValidationResult:
        async with self._lock:
            if validator_id not in self._validators:
                return None
            
            validator = self._validators[validator_id]
            
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
            elif isinstance(data, pd.DataFrame):
                df = data.copy()
            else:
                return None
            
            errors = []
            warnings = []
            passed = True
            
            if "null_check" in validator.rules:
                null_result = await self._check_nulls(df, validator.rules["null_check"])
                if not null_result["passed"]:
                    passed = False
                    errors.append(null_result["errors"])
                if null_result.get("warnings"):
                    warnings.extend(null_result["warnings"])
            
            if "range_check" in validator.rules:
                range_result = await self._check_ranges(df, validator.rules["range_check"])
                if not range_result["passed"]:
                    passed = False
                    errors.append(range_result["errors"])
                if range_result.get("warnings"):
                    warnings.extend(range_result["warnings"])
            
            if "type_check" in validator.rules:
                type_result = await self._check_types(df, validator.rules["type_check"])
                if not type_result["passed"]:
                    passed = False
                    errors.append(type_result["errors"])
                if type_result.get("warnings"):
                    warnings.extend(type_result["warnings"])
            
            result = ValidationResult(
                id=hashlib.md5(f"{validator_id}_{time.time()}".encode()).hexdigest(),
                validator_id=validator_id,
                passed=passed,
                errors=errors,
                warnings=warnings,
                timestamp=time.time()
            )
            
            self._validation_results[result.id] = result
            await self._notify_observers("validation_completed", result)
            return result

    async def _check_nulls(self, df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
        result = {"passed": True, "errors": [], "warnings": []}
        
        max_null_percentage = config.get("max_null_percentage", 0.05)
        columns = config.get("columns", df.columns.tolist())
        
        for col in columns:
            if col in df.columns:
                null_percentage = df[col].isnull().sum() / len(df)
                if null_percentage > max_null_percentage:
                    result["passed"] = False
                    result["errors"].append({
                        "column": col,
                        "message": f"Null percentage {null_percentage:.2%} exceeds threshold {max_null_percentage:.2%}"
                    })
                elif null_percentage > max_null_percentage * 0.5:
                    result["warnings"].append(f"High null percentage in {col}: {null_percentage:.2%}")
        
        return result

    async def _check_ranges(self, df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
        result = {"passed": True, "errors": [], "warnings": []}
        
        ranges = config.get("ranges", {})
        
        for col, (min_val, max_val) in ranges.items():
            if col in df.columns:
                out_of_range = ((df[col] < min_val) | (df[col] > max_val)).sum()
                if out_of_range > 0:
                    result["passed"] = False
                    result["errors"].append({
                        "column": col,
                        "message": f"{out_of_range} values out of range [{min_val}, {max_val}]"
                    })
        
        return result

    async def _check_types(self, df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
        result = {"passed": True, "errors": [], "warnings": []}
        
        types = config.get("types", {})
        
        for col, expected_type in types.items():
            if col in df.columns:
                actual_type = str(df[col].dtype)
                if expected_type == "float" and "float" not in actual_type:
                    result["passed"] = False
                    result["errors"].append({
                        "column": col,
                        "message": f"Expected float, got {actual_type}"
                    })
                elif expected_type == "int" and "int" not in actual_type:
                    result["passed"] = False
                    result["errors"].append({
                        "column": col,
                        "message": f"Expected int, got {actual_type}"
                    })
                elif expected_type == "string" and "object" not in actual_type and "string" not in actual_type:
                    result["passed"] = False
                    result["errors"].append({
                        "column": col,
                        "message": f"Expected string, got {actual_type}"
                    })
        
        return result

    async def get_config(self, config_id: str) -> Optional[StandardizationConfig]:
        return self._configs.get(config_id)

    async def get_configs(self) -> List[StandardizationConfig]:
        return list(self._configs.values())

    async def get_result(self, result_id: str) -> Optional[StandardizationResult]:
        return self._results.get(result_id)

    async def get_results(self) -> List[StandardizationResult]:
        return list(self._results.values())

    async def get_validator(self, validator_id: str) -> Optional[DataValidator]:
        return self._validators.get(validator_id)

    async def get_validators(self) -> List[DataValidator]:
        return list(self._validators.values())

    async def get_validation_result(self, result_id: str) -> Optional[ValidationResult]:
        return self._validation_results.get(result_id)

    async def inverse_transform(
        self,
        result_id: str,
        data: Optional[pd.DataFrame] = None
    ) -> Optional[pd.DataFrame]:
        if result_id not in self._results:
            return None
        
        result = self._results[result_id]
        
        if data is None:
            data = result.standardized_data
        
        config = self._configs.get(result.config_id)
        if not config:
            return None
        
        scaler = result.scaler
        if hasattr(scaler, "inverse_transform"):
            inverse_data = scaler.inverse_transform(data[config.columns])
            inverse_df = data.copy()
            inverse_df[config.columns] = inverse_data
            return inverse_df
        
        return data

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "configs": len(self._configs),
            "results": len(self._results),
            "validators": len(self._validators),
            "validation_results": len(self._validation_results),
            "scaler_cache": len(self._scaler_cache),
            "observers": len(self._observers),
            "running": self._running
        }


class LogTransformer:
    def __init__(self):
        self._fitted = False
    
    def fit(self, X):
        self._fitted = True
        return self
    
    def transform(self, X):
        return np.log1p(X)
    
    def inverse_transform(self, X):
        return np.expm1(X)


class SqrtTransformer:
    def __init__(self):
        self._fitted = False
    
    def fit(self, X):
        self._fitted = True
        return self
    
    def transform(self, X):
        return np.sqrt(X)
    
    def inverse_transform(self, X):
        return np.square(X)


__all__ = [
    "StandardizationType",
    "NormalizationType",
    "MissingValueStrategy",
    "StandardizationConfig",
    "StandardizationResult",
    "DataValidator",
    "ValidationResult",
    "DataStandardizationManager",
    "LogTransformer",
    "SqrtTransformer"
]
