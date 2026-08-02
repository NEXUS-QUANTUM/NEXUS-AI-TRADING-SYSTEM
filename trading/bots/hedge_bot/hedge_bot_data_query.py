# trading/bots/hedge_bot/hedge_bot_data_query.py

import asyncio
import logging
import time
import json
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable, Generator
from decimal import Decimal
from collections import defaultdict, deque
import numpy as np
import pandas as pd
from functools import reduce
from operator import and_, or_, not_
import itertools

logger = logging.getLogger(__name__)


class QueryOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NIN = "nin"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"
    BETWEEN = "between"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    ANY = "any"
    ALL = "all"
    NONE = "none"


class QueryLogic(str, Enum):
    AND = "and"
    OR = "or"
    NOT = "not"
    XOR = "xor"
    NAND = "nand"
    NOR = "nor"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class QueryType(str, Enum):
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    AGGREGATE = "aggregate"
    JOIN = "join"
    UNION = "union"
    INTERSECT = "intersect"
    EXCEPT = "except"
    GROUP_BY = "group_by"
    ORDER_BY = "order_by"
    LIMIT = "limit"
    OFFSET = "offset"
    WINDOW = "window"
    PIVOT = "pivot"
    UNPIVOT = "unpivot"
    MERGE = "merge"
    TRANSFORM = "transform"


@dataclass
class QueryCondition:
    field: str
    operator: QueryOperator
    value: Any
    logic: QueryLogic = QueryLogic.AND
    nested: List['QueryCondition'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryProjection:
    fields: List[str]
    aliases: Optional[Dict[str, str]] = None
    expressions: Optional[Dict[str, str]] = None
    aggregations: Optional[Dict[str, str]] = None


@dataclass
class QuerySort:
    field: str
    order: SortOrder = SortOrder.ASC


@dataclass
class QueryJoin:
    table: str
    condition: QueryCondition
    type: str = "inner"
    alias: Optional[str] = None


@dataclass
class QueryWindow:
    partition_by: List[str]
    order_by: List[QuerySort]
    frame_start: Optional[str] = None
    frame_end: Optional[str] = None


@dataclass
class Query:
    id: str
    type: QueryType
    source: Union[str, List[str]]
    conditions: Optional[List[QueryCondition]] = None
    projection: Optional[QueryProjection] = None
    sorts: Optional[List[QuerySort]] = None
    joins: Optional[List[QueryJoin]] = None
    group_by: Optional[List[str]] = None
    having: Optional[QueryCondition] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    window: Optional[QueryWindow] = None
    distinct: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 30
    created_at: float = field(default_factory=time.time)


@dataclass
class QueryResult:
    query_id: str
    data: Union[pd.DataFrame, List[Dict[str, Any]]]
    count: int
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class DataQueryEngine:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._queries: Dict[str, Query] = {}
        self._results: Dict[str, QueryResult] = {}
        self._data_sources: Dict[str, Any] = {}
        self._indices: Dict[str, Dict[str, Any]] = {}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 300
        self._query_history: deque = deque(maxlen=1000)
        self._optimizer = QueryOptimizer()
        self._executor = QueryExecutor()
        self._analyzers: Dict[str, Callable] = {}
        self._transformers: Dict[str, Callable] = {}
        
        self._register_default_analyzers()
        self._register_default_transformers()

    def _register_default_analyzers(self) -> None:
        self.register_analyzer("stats", self._analyze_statistics)
        self.register_analyzer("distribution", self._analyze_distribution)
        self.register_analyzer("correlation", self._analyze_correlation)
        self.register_analyzer("trend", self._analyze_trend)
        self.register_analyzer("patterns", self._analyze_patterns)

    def _register_default_transformers(self) -> None:
        self.register_transformer("normalize", self._transform_normalize)
        self.register_transformer("scale", self._transform_scale)
        self.register_transformer("encode", self._transform_encode)
        self.register_transformer("pivot", self._transform_pivot)
        self.register_transformer("unpivot", self._transform_unpivot)

    def register_analyzer(self, name: str, analyzer: Callable) -> None:
        self._analyzers[name] = analyzer

    def register_transformer(self, name: str, transformer: Callable) -> None:
        self._transformers[name] = transformer

    def register_data_source(self, name: str, source: Any) -> None:
        self._data_sources[name] = source
        logger.info(f"Registered data source: {name}")

    async def execute_query(self, query: Query) -> QueryResult:
        async with self._lock:
            start_time = time.time()
            
            if query.id in self._cache and self._is_cache_valid(query.id):
                result = self._cache[query.id]["result"]
                result.execution_time = time.time() - start_time
                return result
            
            try:
                optimized_query = self._optimizer.optimize(query)
                
                if isinstance(query.source, str):
                    source_data = await self._get_data_source(query.source)
                else:
                    source_data = [await self._get_data_source(s) for s in query.source]
                
                result_data = await self._executor.execute(optimized_query, source_data)
                
                result = QueryResult(
                    query_id=query.id,
                    data=result_data,
                    count=len(result_data) if hasattr(result_data, '__len__') else 0,
                    execution_time=time.time() - start_time,
                    metadata=query.metadata
                )
                
                self._cache[query.id] = {
                    "result": result,
                    "timestamp": time.time()
                }
                
                self._queries[query.id] = query
                self._results[query.id] = result
                self._query_history.append(query)
                
                return result
                
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                return QueryResult(
                    query_id=query.id,
                    data=[],
                    count=0,
                    execution_time=time.time() - start_time,
                    errors=[str(e)]
                )

    async def _get_data_source(self, source_name: str) -> Any:
        if source_name not in self._data_sources:
            raise ValueError(f"Data source not found: {source_name}")
        
        source = self._data_sources[source_name]
        
        if callable(source):
            return await source()
        
        return source

    def _is_cache_valid(self, query_id: str) -> bool:
        if query_id not in self._cache:
            return False
        
        cache_entry = self._cache[query_id]
        return time.time() - cache_entry["timestamp"] < self._cache_ttl

    async def create_query(
        self,
        query_type: QueryType,
        source: Union[str, List[str]],
        conditions: Optional[List[QueryCondition]] = None,
        projection: Optional[QueryProjection] = None,
        sorts: Optional[List[QuerySort]] = None,
        joins: Optional[List[QueryJoin]] = None,
        group_by: Optional[List[str]] = None,
        having: Optional[QueryCondition] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        distinct: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Query:
        query_id = hashlib.md5(f"{query_type.value}_{source}_{time.time()}".encode()).hexdigest()
        
        return Query(
            id=query_id,
            type=query_type,
            source=source,
            conditions=conditions,
            projection=projection,
            sorts=sorts,
            joins=joins,
            group_by=group_by,
            having=having,
            limit=limit,
            offset=offset,
            distinct=distinct,
            metadata=metadata or {},
            created_at=time.time()
        )

    async def select(
        self,
        source: Union[str, List[str]],
        fields: Optional[List[str]] = None,
        conditions: Optional[List[QueryCondition]] = None,
        sorts: Optional[List[QuerySort]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        distinct: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        projection = None
        if fields:
            projection = QueryProjection(fields=fields)
        
        query = await self.create_query(
            query_type=QueryType.SELECT,
            source=source,
            conditions=conditions,
            projection=projection,
            sorts=sorts,
            limit=limit,
            offset=offset,
            distinct=distinct,
            metadata=metadata
        )
        
        return await self.execute_query(query)

    async def aggregate(
        self,
        source: Union[str, List[str]],
        aggregations: Dict[str, str],
        group_by: Optional[List[str]] = None,
        conditions: Optional[List[QueryCondition]] = None,
        having: Optional[QueryCondition] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        projection = QueryProjection(
            fields=list(aggregations.keys()),
            aggregations=aggregations
        )
        
        query = await self.create_query(
            query_type=QueryType.AGGREGATE,
            source=source,
            conditions=conditions,
            projection=projection,
            group_by=group_by,
            having=having,
            metadata=metadata
        )
        
        return await self.execute_query(query)

    async def join(
        self,
        source: Union[str, List[str]],
        joins: List[QueryJoin],
        conditions: Optional[List[QueryCondition]] = None,
        projection: Optional[QueryProjection] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        query = await self.create_query(
            query_type=QueryType.JOIN,
            source=source,
            conditions=conditions,
            projection=projection,
            joins=joins,
            metadata=metadata
        )
        
        return await self.execute_query(query)

    async def analyze(
        self,
        query_id: str,
        analysis_type: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if query_id not in self._results:
            raise ValueError(f"Query result not found: {query_id}")
        
        if analysis_type not in self._analyzers:
            raise ValueError(f"Analyzer not found: {analysis_type}")
        
        result = self._results[query_id]
        analyzer = self._analyzers[analysis_type]
        
        return await analyzer(result.data, params or {})

    async def transform(
        self,
        query_id: str,
        transform_type: str,
        params: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        if query_id not in self._results:
            raise ValueError(f"Query result not found: {query_id}")
        
        if transform_type not in self._transformers:
            raise ValueError(f"Transformer not found: {transform_type}")
        
        result = self._results[query_id]
        transformer = self._transformers[transform_type]
        
        transformed_data = await transformer(result.data, params or {})
        
        new_query_id = hashlib.md5(f"{query_id}_{transform_type}_{time.time()}".encode()).hexdigest()
        
        return QueryResult(
            query_id=new_query_id,
            data=transformed_data,
            count=len(transformed_data) if hasattr(transformed_data, '__len__') else 0,
            execution_time=0,
            metadata=result.metadata
        )

    async def _analyze_statistics(self, data: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        df = self._to_dataframe(data)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        stats = {}
        for col in numeric_cols:
            stats[col] = {
                "count": int(df[col].count()),
                "mean": float(df[col].mean()),
                "std": float(df[col].std()),
                "min": float(df[col].min()),
                "q25": float(df[col].quantile(0.25)),
                "q50": float(df[col].median()),
                "q75": float(df[col].quantile(0.75)),
                "max": float(df[col].max()),
                "skew": float(df[col].skew()),
                "kurtosis": float(df[col].kurtosis()),
                "missing": int(df[col].isnull().sum())
            }
        
        return stats

    async def _analyze_distribution(self, data: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        df = self._to_dataframe(data)
        bins = params.get("bins", 10)
        column = params.get("column")
        
        if not column:
            return {}
        
        if column not in df.columns:
            return {}
        
        values = df[column].dropna()
        hist, bin_edges = np.histogram(values, bins=bins)
        
        return {
            "column": column,
            "histogram": [int(h) for h in hist],
            "bin_edges": [float(e) for e in bin_edges],
            "min": float(values.min()),
            "max": float(values.max()),
            "mean": float(values.mean()),
            "median": float(values.median()),
            "std": float(values.std()),
            "count": int(len(values))
        }

    async def _analyze_correlation(self, data: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        df = self._to_dataframe(data)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        if len(numeric_cols) < 2:
            return {}
        
        corr_matrix = df[numeric_cols].corr().round(4)
        
        correlations = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                col1 = corr_matrix.columns[i]
                col2 = corr_matrix.columns[j]
                corr_val = corr_matrix.iloc[i, j]
                if not np.isnan(corr_val):
                    correlations.append({
                        "col1": col1,
                        "col2": col2,
                        "correlation": float(corr_val)
                    })
        
        correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)
        
        return {
            "matrix": corr_matrix.to_dict(),
            "correlations": correlations[:params.get("limit", 10)]
        }

    async def _analyze_trend(self, data: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        df = self._to_dataframe(data)
        column = params.get("column")
        time_col = params.get("time_col")
        
        if not column or not time_col:
            return {}
        
        if column not in df.columns or time_col not in df.columns:
            return {}
        
        df_sorted = df.sort_values(time_col)
        values = df_sorted[column].values
        times = df_sorted[time_col].values
        
        if len(values) < 3:
            return {}
        
        x = np.arange(len(values))
        coefficients = np.polyfit(x, values, 1)
        trend = coefficients[0]
        
        return {
            "column": column,
            "trend_slope": float(trend),
            "trend_direction": "up" if trend > 0 else "down" if trend < 0 else "stable",
            "data_points": int(len(values)),
            "start_time": times[0] if hasattr(times[0], 'isoformat') else times[0],
            "end_time": times[-1] if hasattr(times[-1], 'isoformat') else times[-1]
        }

    async def _analyze_patterns(self, data: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        df = self._to_dataframe(data)
        column = params.get("column")
        
        if not column or column not in df.columns:
            return {}
        
        values = df[column].dropna()
        
        if len(values) < 4:
            return {}
        
        patterns = {}
        
        seasonal = params.get("seasonal", True)
        if seasonal:
            try:
                from statsmodels.tsa.seasonal import seasonal_decompose
                decomp = seasonal_decompose(values, model='additive', period=params.get("period", 7))
                patterns["seasonal"] = {
                    "trend": decomp.trend.tolist() if hasattr(decomp.trend, 'tolist') else None,
                    "seasonal": decomp.seasonal.tolist() if hasattr(decomp.seasonal, 'tolist') else None,
                    "residual": decomp.resid.tolist() if hasattr(decomp.resid, 'tolist') else None
                }
            except:
                pass
        
        patterns["autocorrelation"] = {
            f"lag_{i}": float(values.autocorr(lag=i)) 
            for i in range(1, min(10, len(values)//2))
        }
        
        return patterns

    async def _transform_normalize(self, data: Any, params: Dict[str, Any]) -> Any:
        df = self._to_dataframe(data)
        columns = params.get("columns", df.select_dtypes(include=[np.number]).columns.tolist())
        
        for col in columns:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                min_val = df[col].min()
                max_val = df[col].max()
                if max_val != min_val:
                    df[col] = (df[col] - min_val) / (max_val - min_val)
                else:
                    df[col] = 0
        
        return df

    async def _transform_scale(self, data: Any, params: Dict[str, Any]) -> Any:
        df = self._to_dataframe(data)
        columns = params.get("columns", df.select_dtypes(include=[np.number]).columns.tolist())
        
        for col in columns:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                mean = df[col].mean()
                std = df[col].std()
                if std > 0:
                    df[col] = (df[col] - mean) / std
                else:
                    df[col] = 0
        
        return df

    async def _transform_encode(self, data: Any, params: Dict[str, Any]) -> Any:
        df = self._to_dataframe(data)
        columns = params.get("columns", df.select_dtypes(include=['object', 'category']).columns.tolist())
        method = params.get("method", "onehot")
        
        if method == "onehot":
            for col in columns:
                if col in df.columns:
                    dummies = pd.get_dummies(df[col], prefix=col)
                    df = pd.concat([df.drop(col, axis=1), dummies], axis=1)
        
        elif method == "label":
            from sklearn.preprocessing import LabelEncoder
            le = LabelEncoder()
            for col in columns:
                if col in df.columns:
                    df[col] = le.fit_transform(df[col].astype(str))
        
        return df

    async def _transform_pivot(self, data: Any, params: Dict[str, Any]) -> Any:
        df = self._to_dataframe(data)
        index = params.get("index")
        columns = params.get("columns")
        values = params.get("values")
        
        if not index or not columns or not values:
            return df
        
        return df.pivot_table(index=index, columns=columns, values=values, aggfunc=params.get("aggfunc", np.mean))

    async def _transform_unpivot(self, data: Any, params: Dict[str, Any]) -> Any:
        df = self._to_dataframe(data)
        id_vars = params.get("id_vars", [])
        value_vars = params.get("value_vars", [])
        var_name = params.get("var_name", "variable")
        value_name = params.get("value_name", "value")
        
        if not value_vars:
            value_vars = [c for c in df.columns if c not in id_vars]
        
        return pd.melt(df, id_vars=id_vars, value_vars=value_vars, var_name=var_name, value_name=value_name)

    def _to_dataframe(self, data: Any) -> pd.DataFrame:
        if isinstance(data, pd.DataFrame):
            return data
        elif isinstance(data, list):
            return pd.DataFrame(data)
        elif isinstance(data, dict):
            return pd.DataFrame([data])
        else:
            return pd.DataFrame(data)

    async def get_query(self, query_id: str) -> Optional[Query]:
        return self._queries.get(query_id)

    async def get_result(self, query_id: str) -> Optional[QueryResult]:
        return self._results.get(query_id)

    async def get_query_history(self, limit: int = 100) -> List[Query]:
        return list(self._query_history)[-limit:]

    async def clear_cache(self) -> None:
        self._cache.clear()

    async def clear_results(self) -> None:
        self._results.clear()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "queries": len(self._queries),
            "results": len(self._results),
            "cache_size": len(self._cache),
            "cache_ttl": self._cache_ttl,
            "history_size": len(self._query_history),
            "data_sources": len(self._data_sources),
            "analyzers": len(self._analyzers),
            "transformers": len(self._transformers)
        }


class QueryOptimizer:
    
    def optimize(self, query: Query) -> Query:
        optimized = query
        
        if query.conditions:
            optimized = self._optimize_conditions(optimized)
        
        if query.projection:
            optimized = self._optimize_projection(optimized)
        
        if query.joins:
            optimized = self._optimize_joins(optimized)
        
        if query.group_by:
            optimized = self._optimize_group_by(optimized)
        
        return optimized

    def _optimize_conditions(self, query: Query) -> Query:
        if not query.conditions:
            return query
        
        optimized_conditions = []
        for condition in query.conditions:
            optimized_condition = self._simplify_condition(condition)
            if optimized_condition:
                optimized_conditions.append(optimized_condition)
        
        query.conditions = self._merge_conditions(optimized_conditions)
        return query

    def _simplify_condition(self, condition: QueryCondition) -> Optional[QueryCondition]:
        if condition.operator == QueryOperator.IS_NULL:
            if condition.value is None:
                return QueryCondition(
                    field=condition.field,
                    operator=QueryOperator.EQ,
                    value=None
                )
        
        if condition.operator == QueryOperator.IS_NOT_NULL:
            if condition.value is None:
                return QueryCondition(
                    field=condition.field,
                    operator=QueryOperator.NE,
                    value=None
                )
        
        if condition.operator == QueryOperator.IN:
            if not condition.value:
                return None
            if len(condition.value) == 1:
                return QueryCondition(
                    field=condition.field,
                    operator=QueryOperator.EQ,
                    value=condition.value[0]
                )
        
        if condition.operator == QueryOperator.BETWEEN:
            if not condition.value or len(condition.value) != 2:
                return None
        
        return condition

    def _merge_conditions(self, conditions: List[QueryCondition]) -> List[QueryCondition]:
        if not conditions:
            return conditions
        
        merged = []
        current = None
        
        for condition in conditions:
            if current is None:
                current = condition
            elif current.logic == condition.logic:
                if current.field == condition.field and current.operator == condition.operator:
                    if current.operator in [QueryOperator.IN, QueryOperator.NIN]:
                        if isinstance(current.value, list) and isinstance(condition.value, list):
                            current.value = list(set(current.value + condition.value))
                    continue
                current.nested.append(condition)
            else:
                merged.append(current)
                current = condition
        
        if current:
            merged.append(current)
        
        return merged

    def _optimize_projection(self, query: Query) -> Query:
        if not query.projection or not query.projection.fields:
            return query
        
        if query.distinct and query.projection.fields:
            distinct_fields = set(query.projection.fields)
            query.projection.fields = list(distinct_fields)
        
        return query

    def _optimize_joins(self, query: Query) -> Query:
        if not query.joins:
            return query
        
        optimized_joins = []
        for join in query.joins:
            if join.condition:
                join.condition = self._simplify_condition(join.condition)
            optimized_joins.append(join)
        
        query.joins = optimized_joins
        return query

    def _optimize_group_by(self, query: Query) -> Query:
        if not query.group_by:
            return query
        
        if query.projection and query.projection.aggregations:
            aggregate_fields = set(query.projection.aggregations.keys())
            group_fields = set(query.group_by)
            query.group_by = list(group_fields.intersection(aggregate_fields))
        
        return query


class QueryExecutor:
    
    def __init__(self):
        self._lock = asyncio.Lock()

    async def execute(self, query: Query, data: Any) -> Any:
        if query.type == QueryType.SELECT:
            return await self._execute_select(query, data)
        elif query.type == QueryType.AGGREGATE:
            return await self._execute_aggregate(query, data)
        elif query.type == QueryType.JOIN:
            return await self._execute_join(query, data)
        elif query.type == QueryType.UNION:
            return await self._execute_union(query, data)
        elif query.type == QueryType.INTERSECT:
            return await self._execute_intersect(query, data)
        elif query.type == QueryType.EXCEPT:
            return await self._execute_except(query, data)
        elif query.type == QueryType.GROUP_BY:
            return await self._execute_group_by(query, data)
        elif query.type == QueryType.ORDER_BY:
            return await self._execute_order_by(query, data)
        elif query.type == QueryType.PIVOT:
            return await self._execute_pivot(query, data)
        elif query.type == QueryType.UNPIVOT:
            return await self._execute_unpivot(query, data)
        else:
            raise ValueError(f"Unsupported query type: {query.type}")

    async def _execute_select(self, query: Query, data: Any) -> Any:
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        elif isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            df = pd.DataFrame(data)
        
        if query.conditions:
            df = self._apply_conditions(df, query.conditions)
        
        if query.projection:
            df = self._apply_projection(df, query.projection)
        
        if query.sorts:
            df = self._apply_sorts(df, query.sorts)
        
        if query.distinct:
            df = df.drop_duplicates()
        
        if query.limit is not None:
            if query.offset:
                df = df.iloc[query.offset:query.offset + query.limit]
            else:
                df = df.iloc[:query.limit]
        
        return df.to_dict('records') if not isinstance(data, pd.DataFrame) else df

    async def _execute_aggregate(self, query: Query, data: Any) -> Any:
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        elif isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            df = pd.DataFrame(data)
        
        if query.conditions:
            df = self._apply_conditions(df, query.conditions)
        
        if query.projection and query.projection.aggregations:
            agg_dict = {}
            for field, agg_func in query.projection.aggregations.items():
                if agg_func == "count":
                    agg_dict[field] = 'count'
                elif agg_func == "sum":
                    agg_dict[field] = 'sum'
                elif agg_func == "mean":
                    agg_dict[field] = 'mean'
                elif agg_func == "median":
                    agg_dict[field] = 'median'
                elif agg_func == "min":
                    agg_dict[field] = 'min'
                elif agg_func == "max":
                    agg_dict[field] = 'max'
                elif agg_func == "std":
                    agg_dict[field] = 'std'
                elif agg_func == "var":
                    agg_dict[field] = 'var'
                elif agg_func == "first":
                    agg_dict[field] = 'first'
                elif agg_func == "last":
                    agg_dict[field] = 'last'
                else:
                    agg_dict[field] = agg_func
            
            if query.group_by:
                grouped = df.groupby(query.group_by).agg(agg_dict)
                df = grouped.reset_index()
            else:
                df = df.agg(agg_dict).to_frame().T
        
        if query.having:
            df = self._apply_conditions(df, [query.having])
        
        if query.sorts:
            df = self._apply_sorts(df, query.sorts)
        
        return df.to_dict('records') if not isinstance(data, pd.DataFrame) else df

    async def _execute_join(self, query: Query, data: Any) -> Any:
        if not query.joins:
            return data
        
        if isinstance(data, list):
            left_df = pd.DataFrame(data)
        elif isinstance(data, dict):
            left_df = pd.DataFrame([data])
        elif isinstance(data, pd.DataFrame):
            left_df = data.copy()
        else:
            left_df = pd.DataFrame(data)
        
        for join in query.joins:
            right_data = await self._get_join_data(join)
            if right_data is None:
                continue
            
            right_df = pd.DataFrame(right_data)
            
            condition = join.condition
            if condition and condition.operator == QueryOperator.EQ:
                left_col = condition.field
                right_col = condition.value
                if right_col in right_df.columns:
                    if join.type == "inner":
                        left_df = left_df.merge(right_df, left_on=left_col, right_on=right_col, how='inner')
                    elif join.type == "left":
                        left_df = left_df.merge(right_df, left_on=left_col, right_on=right_col, how='left')
                    elif join.type == "right":
                        left_df = left_df.merge(right_df, left_on=left_col, right_on=right_col, how='right')
                    elif join.type == "outer":
                        left_df = left_df.merge(right_df, left_on=left_col, right_on=right_col, how='outer')
                    elif join.type == "cross":
                        left_df = left_df.merge(right_df, how='cross')
            else:
                left_df = left_df.merge(right_df, how='inner')
        
        if query.projection:
            left_df = self._apply_projection(left_df, query.projection)
        
        if query.conditions:
            left_df = self._apply_conditions(left_df, query.conditions)
        
        if query.sorts:
            left_df = self._apply_sorts(left_df, query.sorts)
        
        return left_df.to_dict('records') if not isinstance(data, pd.DataFrame) else left_df

    async def _execute_union(self, query: Query, data: Any) -> Any:
        if not isinstance(data, list) or len(data) < 2:
            return data
        
        dfs = []
        for d in data:
            if isinstance(d, list):
                dfs.append(pd.DataFrame(d))
            elif isinstance(d, dict):
                dfs.append(pd.DataFrame([d]))
            elif isinstance(d, pd.DataFrame):
                dfs.append(d.copy())
        
        result = pd.concat(dfs, ignore_index=True)
        
        if query.distinct:
            result = result.drop_duplicates()
        
        if query.sorts:
            result = self._apply_sorts(result, query.sorts)
        
        if query.limit is not None:
            result = result.iloc[:query.limit]
        
        return result.to_dict('records') if not isinstance(data, pd.DataFrame) else result

    async def _execute_intersect(self, query: Query, data: Any) -> Any:
        if not isinstance(data, list) or len(data) < 2:
            return []
        
        dfs = []
        for d in data:
            if isinstance(d, list):
                dfs.append(pd.DataFrame(d))
            elif isinstance(d, dict):
                dfs.append(pd.DataFrame([d]))
            elif isinstance(d, pd.DataFrame):
                dfs.append(d.copy())
        
        result = dfs[0]
        for df in dfs[1:]:
            result = pd.merge(result, df, how='inner')
        
        if query.sorts:
            result = self._apply_sorts(result, query.sorts)
        
        if query.limit is not None:
            result = result.iloc[:query.limit]
        
        return result.to_dict('records') if not isinstance(data, pd.DataFrame) else result

    async def _execute_except(self, query: Query, data: Any) -> Any:
        if not isinstance(data, list) or len(data) < 2:
            return data
        
        dfs = []
        for d in data:
            if isinstance(d, list):
                dfs.append(pd.DataFrame(d))
            elif isinstance(d, dict):
                dfs.append(pd.DataFrame([d]))
            elif isinstance(d, pd.DataFrame):
                dfs.append(d.copy())
        
        result = dfs[0]
        for df in dfs[1:]:
            result = pd.merge(result, df, how='outer', indicator=True)
            result = result[result['_merge'] == 'left_only'].drop('_merge', axis=1)
        
        if query.sorts:
            result = self._apply_sorts(result, query.sorts)
        
        if query.limit is not None:
            result = result.iloc[:query.limit]
        
        return result.to_dict('records') if not isinstance(data, pd.DataFrame) else result

    async def _execute_group_by(self, query: Query, data: Any) -> Any:
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        elif isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            df = pd.DataFrame(data)
        
        if not query.group_by:
            return data
        
        grouped = df.groupby(query.group_by)
        
        if query.projection and query.projection.aggregations:
            agg_dict = {}
            for field, agg_func in query.projection.aggregations.items():
                if field in df.columns:
                    agg_dict[field] = agg_func
            result = grouped.agg(agg_dict).reset_index()
        else:
            result = grouped.size().reset_index(name='count')
        
        if query.having:
            result = self._apply_conditions(result, [query.having])
        
        if query.sorts:
            result = self._apply_sorts(result, query.sorts)
        
        return result.to_dict('records') if not isinstance(data, pd.DataFrame) else result

    async def _execute_order_by(self, query: Query, data: Any) -> Any:
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        elif isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            return data
        
        if not query.sorts:
            return data
        
        return self._apply_sorts(df, query.sorts)

    async def _execute_pivot(self, query: Query, data: Any) -> Any:
        if not query.metadata:
            return data
        
        pivot_params = query.metadata.get("pivot", {})
        index = pivot_params.get("index")
        columns = pivot_params.get("columns")
        values = pivot_params.get("values")
        aggfunc = pivot_params.get("aggfunc", "mean")
        
        if not index or not columns or not values:
            return data
        
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        elif isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            return data
        
        return df.pivot_table(index=index, columns=columns, values=values, aggfunc=aggfunc)

    async def _execute_unpivot(self, query: Query, data: Any) -> Any:
        if not query.metadata:
            return data
        
        unpivot_params = query.metadata.get("unpivot", {})
        id_vars = unpivot_params.get("id_vars", [])
        value_vars = unpivot_params.get("value_vars", [])
        var_name = unpivot_params.get("var_name", "variable")
        value_name = unpivot_params.get("value_name", "value")
        
        if not id_vars:
            return data
        
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        elif isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            return data
        
        if not value_vars:
            value_vars = [c for c in df.columns if c not in id_vars]
        
        return pd.melt(df, id_vars=id_vars, value_vars=value_vars, var_name=var_name, value_name=value_name)

    async def _get_join_data(self, join: QueryJoin) -> Optional[Any]:
        if hasattr(join, 'data'):
            return join.data
        return None

    def _apply_conditions(self, df: pd.DataFrame, conditions: List[QueryCondition]) -> pd.DataFrame:
        if not conditions:
            return df
        
        mask = None
        
        for condition in conditions:
            condition_mask = self._build_condition_mask(df, condition)
            if condition_mask is not None:
                if mask is None:
                    mask = condition_mask
                elif condition.logic == QueryLogic.AND:
                    mask = mask & condition_mask
                elif condition.logic == QueryLogic.OR:
                    mask = mask | condition_mask
                elif condition.logic == QueryLogic.NOT:
                    mask = mask & ~condition_mask
                elif condition.logic == QueryLogic.XOR:
                    mask = mask ^ condition_mask
                elif condition.logic == QueryLogic.NAND:
                    mask = ~(mask & condition_mask)
                elif condition.logic == QueryLogic.NOR:
                    mask = ~(mask | condition_mask)
        
        if mask is not None:
            return df[mask]
        
        return df

    def _build_condition_mask(self, df: pd.DataFrame, condition: QueryCondition) -> Optional[pd.Series]:
        if condition.field not in df.columns:
            return None
        
        if condition.operator == QueryOperator.EQ:
            return df[condition.field] == condition.value
        elif condition.operator == QueryOperator.NE:
            return df[condition.field] != condition.value
        elif condition.operator == QueryOperator.GT:
            return df[condition.field] > condition.value
        elif condition.operator == QueryOperator.GTE:
            return df[condition.field] >= condition.value
        elif condition.operator == QueryOperator.LT:
            return df[condition.field] < condition.value
        elif condition.operator == QueryOperator.LTE:
            return df[condition.field] <= condition.value
        elif condition.operator == QueryOperator.IN:
            return df[condition.field].isin(condition.value)
        elif condition.operator == QueryOperator.NIN:
            return ~df[condition.field].isin(condition.value)
        elif condition.operator == QueryOperator.CONTAINS:
            return df[condition.field].astype(str).str.contains(str(condition.value), na=False)
        elif condition.operator == QueryOperator.STARTS_WITH:
            return df[condition.field].astype(str).str.startswith(str(condition.value))
        elif condition.operator == QueryOperator.ENDS_WITH:
            return df[condition.field].astype(str).str.endswith(str(condition.value))
        elif condition.operator == QueryOperator.MATCHES:
            return df[condition.field].astype(str).str.match(condition.value)
        elif condition.operator == QueryOperator.BETWEEN:
            if len(condition.value) == 2:
                return (df[condition.field] >= condition.value[0]) & (df[condition.field] <= condition.value[1])
        elif condition.operator == QueryOperator.IS_NULL:
            return df[condition.field].isnull()
        elif condition.operator == QueryOperator.IS_NOT_NULL:
            return df[condition.field].notnull()
        
        return None

    def _apply_projection(self, df: pd.DataFrame, projection: QueryProjection) -> pd.DataFrame:
        if not projection:
            return df
        
        result = df.copy()
        
        if projection.fields:
            existing_fields = [f for f in projection.fields if f in df.columns]
            if existing_fields:
                result = result[existing_fields]
        
        if projection.aliases:
            for field, alias in projection.aliases.items():
                if field in df.columns:
                    result[alias] = result[field]
                    if field != alias:
                        result.drop(field, axis=1, inplace=True)
        
        if projection.expressions:
            for expr_name, expr in projection.expressions.items():
                try:
                    result[expr_name] = result.eval(expr)
                except:
                    pass
        
        return result

    def _apply_sorts(self, df: pd.DataFrame, sorts: List[QuerySort]) -> pd.DataFrame:
        if not sorts:
            return df
        
        sort_cols = []
        ascending = []
        
        for sort in sorts:
            if sort.field in df.columns:
                sort_cols.append(sort.field)
                ascending.append(sort.order == SortOrder.ASC)
        
        if sort_cols:
            return df.sort_values(by=sort_cols, ascending=ascending)
        
        return df


__all__ = [
    "QueryOperator",
    "QueryLogic",
    "SortOrder",
    "QueryType",
    "QueryCondition",
    "QueryProjection",
    "QuerySort",
    "QueryJoin",
    "QueryWindow",
    "Query",
    "QueryResult",
    "DataQueryEngine",
    "QueryOptimizer",
    "QueryExecutor"
]
