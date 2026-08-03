# trading/bots/hedge_bot/hedge_bot_data_transformation.py

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

logger = logging.getLogger(__name__)


class TransformationType(str, Enum):
    MAP = "map"
    FILTER = "filter"
    REDUCE = "reduce"
    AGGREGATE = "aggregate"
    JOIN = "join"
    UNION = "union"
    PIVOT = "pivot"
    UNPIVOT = "unpivot"
    NORMALIZE = "normalize"
    STANDARDIZE = "standardize"
    ENCODE = "encode"
    DECODE = "decode"
    HASH = "hash"
    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"
    COMPRESS = "compress"
    DECOMPRESS = "decompress"
    SORT = "sort"
    DEDUPLICATE = "deduplicate"
    IMPUTE = "impute"
    OUTLIER = "outlier"
    BIN = "bin"
    SCALE = "scale"
    SHIFT = "shift"
    DIFFERENCE = "difference"
    CUMULATIVE = "cumulative"
    ROLLING = "rolling"
    LAG = "lag"
    LEAD = "lead"
    RANK = "rank"
    DENSE_RANK = "dense_rank"
    PERCENTILE = "percentile"


class TransformationMode(str, Enum):
    BATCH = "batch"
    STREAM = "stream"
    REAL_TIME = "realtime"
    SCHEDULED = "scheduled"
    ON_DEMAND = "on_demand"


@dataclass
class TransformationRule:
    id: str
    name: str
    type: TransformationType
    expression: str
    input_columns: List[str]
    output_columns: List[str]
    mode: TransformationMode = TransformationMode.BATCH
    condition: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    enabled: bool = True


@dataclass
class TransformationResult:
    id: str
    rule_id: str
    input_data: Any
    output_data: Any
    execution_time: float
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransformationPipeline:
    id: str
    name: str
    rules: List[str]
    parallel: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class DataTransformationManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._rules: Dict[str, TransformationRule] = {}
        self._results: Dict[str, TransformationResult] = {}
        self._pipelines: Dict[str, TransformationPipeline] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_rules()

    def _initialize_default_rules(self) -> None:
        default_rules = [
            TransformationRule(
                id="normalize_price",
                name="Normalize Price",
                type=TransformationType.NORMALIZE,
                expression="(price - mean(price)) / std(price)",
                input_columns=["price"],
                output_columns=["price_normalized"]
            ),
            TransformationRule(
                id="log_volume",
                name="Log Volume",
                type=TransformationType.MAP,
                expression="np.log(volume + 1)",
                input_columns=["volume"],
                output_columns=["volume_log"]
            ),
            TransformationRule(
                id="price_difference",
                name="Price Difference",
                type=TransformationType.DIFFERENCE,
                expression="price.diff()",
                input_columns=["price"],
                output_columns=["price_diff"]
            ),
            TransformationRule(
                id="rolling_mean",
                name="Rolling Mean",
                type=TransformationType.ROLLING,
                expression="price.rolling(window=20).mean()",
                input_columns=["price"],
                output_columns=["price_ma20"]
            ),
            TransformationRule(
                id="pct_change",
                name="Percent Change",
                type=TransformationType.MAP,
                expression="price.pct_change() * 100",
                input_columns=["price"],
                output_columns=["price_pct_change"]
            )
        ]
        
        for rule in default_rules:
            self._rules[rule.id] = rule

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def add_rule(
        self,
        name: str,
        type: TransformationType,
        expression: str,
        input_columns: List[str],
        output_columns: List[str],
        mode: TransformationMode = TransformationMode.BATCH,
        condition: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TransformationRule:
        async with self._lock:
            rule_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            rule = TransformationRule(
                id=rule_id,
                name=name,
                type=type,
                expression=expression,
                input_columns=input_columns,
                output_columns=output_columns,
                mode=mode,
                condition=condition,
                metadata=metadata or {}
            )
            
            self._rules[rule_id] = rule
            await self._notify_observers("rule_added", rule)
            return rule

    async def update_rule(
        self,
        rule_id: str,
        expression: Optional[str] = None,
        condition: Optional[str] = None,
        enabled: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[TransformationRule]:
        async with self._lock:
            if rule_id not in self._rules:
                return None
            
            rule = self._rules[rule_id]
            
            if expression:
                rule.expression = expression
            if condition is not None:
                rule.condition = condition
            if enabled is not None:
                rule.enabled = enabled
            if metadata:
                rule.metadata.update(metadata)
            
            rule.updated_at = time.time()
            await self._notify_observers("rule_updated", rule)
            return rule

    async def remove_rule(self, rule_id: str) -> bool:
        async with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                await self._notify_observers("rule_removed", rule_id)
                return True
            return False

    async def transform(
        self,
        data: Union[pd.DataFrame, Dict, List],
        rule_ids: Optional[List[str]] = None,
        pipeline_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Union[pd.DataFrame, Dict, List]:
        async with self._lock:
            if isinstance(data, dict):
                data = pd.DataFrame([data])
            elif isinstance(data, list):
                data = pd.DataFrame(data)
            elif not isinstance(data, pd.DataFrame):
                raise ValueError("Data must be DataFrame, dict, or list")
            
            if pipeline_id and pipeline_id in self._pipelines:
                pipeline = self._pipelines[pipeline_id]
                if pipeline.parallel:
                    result = await self._transform_parallel(data, pipeline.rules)
                else:
                    result = await self._transform_sequential(data, pipeline.rules)
            else:
                rules_to_apply = []
                if rule_ids:
                    for rule_id in rule_ids:
                        if rule_id in self._rules and self._rules[rule_id].enabled:
                            rules_to_apply.append(self._rules[rule_id])
                else:
                    rules_to_apply = [r for r in self._rules.values() if r.enabled]
                
                for rule in rules_to_apply:
                    data = await self._apply_rule(data, rule, metadata)
            
            return data

    async def _transform_sequential(
        self,
        data: pd.DataFrame,
        rule_ids: List[str]
    ) -> pd.DataFrame:
        for rule_id in rule_ids:
            if rule_id in self._rules:
                rule = self._rules[rule_id]
                if rule.enabled:
                    data = await self._apply_rule(data, rule)
        return data

    async def _transform_parallel(
        self,
        data: pd.DataFrame,
        rule_ids: List[str]
    ) -> pd.DataFrame:
        tasks = []
        for rule_id in rule_ids:
            if rule_id in self._rules:
                rule = self._rules[rule_id]
                if rule.enabled:
                    tasks.append(self._apply_rule(data.copy(), rule))
        
        results = await asyncio.gather(*tasks)
        
        for result in results:
            for col in result.columns:
                if col not in data.columns:
                    data[col] = result[col]
                else:
                    data[col] = result[col]
        
        return data

    async def _apply_rule(
        self,
        data: pd.DataFrame,
        rule: TransformationRule,
        metadata: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        start_time = time.time()
        
        try:
            if rule.condition:
                if not eval(rule.condition, {}, {"data": data, "pd": pd, "np": np}):
                    return data
            
            if rule.type == TransformationType.MAP:
                result_data = await self._apply_map(data, rule)
            elif rule.type == TransformationType.FILTER:
                result_data = await self._apply_filter(data, rule)
            elif rule.type == TransformationType.AGGREGATE:
                result_data = await self._apply_aggregate(data, rule)
            elif rule.type == TransformationType.NORMALIZE:
                result_data = await self._apply_normalize(data, rule)
            elif rule.type == TransformationType.STANDARDIZE:
                result_data = await self._apply_standardize(data, rule)
            elif rule.type == TransformationType.DIFFERENCE:
                result_data = await self._apply_difference(data, rule)
            elif rule.type == TransformationType.CUMULATIVE:
                result_data = await self._apply_cumulative(data, rule)
            elif rule.type == TransformationType.ROLLING:
                result_data = await self._apply_rolling(data, rule)
            elif rule.type == TransformationType.LAG:
                result_data = await self._apply_lag(data, rule)
            elif rule.type == TransformationType.LEAD:
                result_data = await self._apply_lead(data, rule)
            elif rule.type == TransformationType.RANK:
                result_data = await self._apply_rank(data, rule)
            elif rule.type == TransformationType.DEDUPLICATE:
                result_data = await self._apply_deduplicate(data, rule)
            elif rule.type == TransformationType.IMPUTE:
                result_data = await self._apply_impute(data, rule)
            elif rule.type == TransformationType.OUTLIER:
                result_data = await self._apply_outlier(data, rule)
            elif rule.type == TransformationType.BIN:
                result_data = await self._apply_bin(data, rule)
            else:
                result_data = data
            
            execution_time = time.time() - start_time
            
            result = TransformationResult(
                id=hashlib.md5(f"{rule.id}_{time.time()}".encode()).hexdigest(),
                rule_id=rule.id,
                input_data=data.copy(),
                output_data=result_data,
                execution_time=execution_time,
                timestamp=time.time(),
                metadata=metadata or {}
            )
            
            self._results[result.id] = result
            await self._notify_observers("transformation_completed", result)
            
            return result_data
            
        except Exception as e:
            logger.error(f"Transformation error for rule {rule.name}: {e}")
            return data

    async def _apply_map(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        result = data.copy()
        for col in rule.input_columns:
            if col in result.columns:
                result[rule.output_columns[0]] = eval(rule.expression, {}, {"data": data, "col": col, "pd": pd, "np": np})
        return result

    async def _apply_filter(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        mask = eval(rule.expression, {}, {"data": data, "pd": pd, "np": np})
        return data[mask]

    async def _apply_aggregate(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        result = data.groupby(rule.input_columns[0]).agg(eval(rule.expression, {}, {"pd": pd, "np": np}))
        return result.reset_index()

    async def _apply_normalize(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        result = data.copy()
        for col in rule.input_columns:
            if col in result.columns:
                min_val = result[col].min()
                max_val = result[col].max()
                if max_val != min_val:
                    result[rule.output_columns[0]] = (result[col] - min_val) / (max_val - min_val)
                else:
                    result[rule.output_columns[0]] = 0
        return result

    async def _apply_standardize(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        result = data.copy()
        for col in rule.input_columns:
            if col in result.columns:
                mean = result[col].mean()
                std = result[col].std()
                if std != 0:
                    result[rule.output_columns[0]] = (result[col] - mean) / std
                else:
                    result[rule.output_columns[0]] = 0
        return result

    async def _apply_difference(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        result = data.copy()
        for col in rule.input_columns:
            if col in result.columns:
                result[rule.output_columns[0]] = result[col].diff()
        return result

    async def _apply_cumulative(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        result = data.copy()
        for col in rule.input_columns:
            if col in result.columns:
                result[rule.output_columns[0]] = result[col].cumsum()
        return result

    async def _apply_rolling(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        result = data.copy()
        for col in rule.input_columns:
            if col in result.columns:
                result[rule.output_columns[0]] = eval(rule.expression, {}, {"data": result, "col": col, "pd": pd})
        return result

    async def _apply_lag(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        result = data.copy()
        for col in rule.input_columns:
            if col in result.columns:
                result[rule.output_columns[0]] = result[col].shift(1)
        return result

    async def _apply_lead(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        result = data.copy()
        for col in rule.input_columns:
            if col in result.columns:
                result[rule.output_columns[0]] = result[col].shift(-1)
        return result

    async def _apply_rank(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        result = data.copy()
        for col in rule.input_columns:
            if col in result.columns:
                result[rule.output_columns[0]] = result[col].rank()
        return result

    async def _apply_deduplicate(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        return data.drop_duplicates(subset=rule.input_columns)

    async def _apply_impute(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        result = data.copy()
        method = rule.metadata.get("impute_method", "mean")
        
        for col in rule.input_columns:
            if col in result.columns:
                if method == "mean":
                    result[col].fillna(result[col].mean(), inplace=True)
                elif method == "median":
                    result[col].fillna(result[col].median(), inplace=True)
                elif method == "mode":
                    result[col].fillna(result[col].mode()[0], inplace=True)
                elif method == "ffill":
                    result[col].fillna(method='ffill', inplace=True)
                elif method == "bfill":
                    result[col].fillna(method='bfill', inplace=True)
                elif method == "constant":
                    result[col].fillna(rule.metadata.get("fill_value", 0), inplace=True)
        
        return result

    async def _apply_outlier(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        result = data.copy()
        method = rule.metadata.get("outlier_method", "zscore")
        threshold = rule.metadata.get("threshold", 3)
        
        for col in rule.input_columns:
            if col in result.columns:
                if method == "zscore":
                    z_scores = np.abs((result[col] - result[col].mean()) / result[col].std())
                    result[col] = result[col].mask(z_scores > threshold)
                elif method == "iqr":
                    q1 = result[col].quantile(0.25)
                    q3 = result[col].quantile(0.75)
                    iqr = q3 - q1
                    lower_bound = q1 - 1.5 * iqr
                    upper_bound = q3 + 1.5 * iqr
                    result[col] = result[col].mask((result[col] < lower_bound) | (result[col] > upper_bound))
        
        return result

    async def _apply_bin(self, data: pd.DataFrame, rule: TransformationRule) -> pd.DataFrame:
        result = data.copy()
        bins = rule.metadata.get("bins", 10)
        labels = rule.metadata.get("labels", None)
        
        for col in rule.input_columns:
            if col in result.columns:
                result[rule.output_columns[0]] = pd.cut(result[col], bins=bins, labels=labels)
        
        return result

    async def get_rule(self, rule_id: str) -> Optional[TransformationRule]:
        return self._rules.get(rule_id)

    async def get_rules(self) -> List[TransformationRule]:
        return list(self._rules.values())

    async def get_result(self, result_id: str) -> Optional[TransformationResult]:
        return self._results.get(result_id)

    async def get_pipeline(self, pipeline_id: str) -> Optional[TransformationPipeline]:
        return self._pipelines.get(pipeline_id)

    async def get_pipelines(self) -> List[TransformationPipeline]:
        return list(self._pipelines.values())

    async def create_pipeline(
        self,
        name: str,
        rule_ids: List[str],
        parallel: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TransformationPipeline:
        async with self._lock:
            pipeline_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            pipeline = TransformationPipeline(
                id=pipeline_id,
                name=name,
                rules=rule_ids,
                parallel=parallel,
                metadata=metadata or {}
            )
            
            self._pipelines[pipeline_id] = pipeline
            await self._notify_observers("pipeline_created", pipeline)
            return pipeline

    async def delete_pipeline(self, pipeline_id: str) -> bool:
        async with self._lock:
            if pipeline_id in self._pipelines:
                del self._pipelines[pipeline_id]
                await self._notify_observers("pipeline_deleted", pipeline_id)
                return True
            return False

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
            "rules": len(self._rules),
            "results": len(self._results),
            "pipelines": len(self._pipelines),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "TransformationType",
    "TransformationMode",
    "TransformationRule",
    "TransformationResult",
    "TransformationPipeline",
    "DataTransformationManager"
]
