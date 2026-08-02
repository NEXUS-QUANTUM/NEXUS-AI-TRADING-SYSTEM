# trading/bots/hedge_bot/hedge_bot_data_spark.py

import asyncio
import logging
import time
import json
import hashlib
import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import numpy as np
import pandas as pd

try:
    from pyspark.sql import SparkSession, DataFrame, Row
    from pyspark.sql.functions import *
    from pyspark.sql.types import *
    from pyspark.sql.window import Window
    from pyspark.ml.feature import VectorAssembler, StandardScaler, MinMaxScaler
    from pyspark.ml.clustering import KMeans, BisectingKMeans
    from pyspark.ml.classification import RandomForestClassifier, LogisticRegression
    from pyspark.ml.regression import RandomForestRegressor, LinearRegression
    from pyspark.ml.evaluation import MulticlassClassificationEvaluator, RegressionEvaluator
    from pyspark.ml.tuning import ParamGridBuilder, CrossValidator
    from pyspark.mllib.evaluation import MulticlassMetrics
    from pyspark.streaming import StreamingContext
    from pyspark.streaming.kafka import KafkaUtils
    SPARK_AVAILABLE = True
except ImportError:
    SPARK_AVAILABLE = False

logger = logging.getLogger(__name__)


class SparkMode(str, Enum):
    LOCAL = "local"
    CLUSTER = "cluster"
    STANDALONE = "standalone"
    YARN = "yarn"
    K8S = "kubernetes"
    MESOS = "mesos"


class SparkDataFrameType(str, Enum):
    BATCH = "batch"
    STREAMING = "streaming"
    STRUCTURED_STREAMING = "structured_streaming"
    PANDAS = "pandas"
    SPARK = "spark"


class SparkOperation(str, Enum):
    FILTER = "filter"
    SELECT = "select"
    GROUP = "group"
    AGGREGATE = "aggregate"
    JOIN = "join"
    UNION = "union"
    SORT = "sort"
    WINDOW = "window"
    PIVOT = "pivot"
    TRANSFORM = "transform"
    ML = "machine_learning"


@dataclass
class SparkConfig:
    app_name: str
    mode: SparkMode
    master_url: str = "local[*]"
    memory: str = "4g"
    cores: int = 4
    executor_memory: str = "2g"
    executor_cores: int = 2
    num_executors: int = 2
    max_attempts: int = 3
    spark_home: Optional[str] = None
    hadoop_conf: Optional[str] = None
    jars: List[str] = field(default_factory=list)
    packages: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SparkDataFrame:
    id: str
    name: str
    df_type: SparkDataFrameType
    dataframe: Any
    schema: Dict[str, str]
    row_count: int
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SparkQuery:
    id: str
    name: str
    operation: SparkOperation
    query: str
    parameters: Dict[str, Any]
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SparkJob:
    id: str
    name: str
    query_id: str
    status: str
    start_time: float
    end_time: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataSparkManager:
    
    def __init__(self, config: Optional[SparkConfig] = None):
        self.config = config or SparkConfig(
            app_name="nexus_hedge_bot",
            mode=SparkMode.LOCAL
        )
        self._lock = asyncio.Lock()
        self._spark: Optional[SparkSession] = None
        self._streaming_context: Optional[StreamingContext] = None
        self._dataframes: Dict[str, SparkDataFrame] = {}
        self._queries: Dict[str, SparkQuery] = {}
        self._jobs: Dict[str, SparkJob] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_spark()

    def _initialize_spark(self) -> None:
        if not SPARK_AVAILABLE:
            logger.warning("PySpark not available")
            return
        
        builder = SparkSession.builder.appName(self.config.app_name)
        
        if self.config.mode == SparkMode.LOCAL:
            builder = builder.master(self.config.master_url)
        
        builder = builder.config("spark.driver.memory", self.config.memory)
        builder = builder.config("spark.executor.memory", self.config.executor_memory)
        builder = builder.config("spark.executor.cores", str(self.config.executor_cores))
        builder = builder.config("spark.executor.instances", str(self.config.num_executors))
        builder = builder.config("spark.sql.adaptive.enabled", "true")
        builder = builder.config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        builder = builder.config("spark.sql.adaptive.skewJoin.enabled", "true")
        
        if self.config.packages:
            builder = builder.config("spark.jars.packages", ",".join(self.config.packages))
        
        if self.config.jars:
            builder = builder.config("spark.jars", ",".join(self.config.jars))
        
        self._spark = builder.getOrCreate()
        self._spark.sparkContext.setLogLevel("WARN")
        
        logger.info(f"Spark session initialized: {self.config.app_name}")

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_dataframe(
        self,
        name: str,
        data: Union[pd.DataFrame, List[Dict], Dict],
        df_type: SparkDataFrameType = SparkDataFrameType.PANDAS,
        schema: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SparkDataFrame]:
        async with self._lock:
            if not self._spark:
                return None
            
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
            elif isinstance(data, pd.DataFrame):
                df = data
            else:
                return None
            
            spark_df = self._spark.createDataFrame(df)
            
            df_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            schema_dict = {}
            for field in spark_df.schema.fields:
                schema_dict[field.name] = str(field.dataType)
            
            spark_dataframe = SparkDataFrame(
                id=df_id,
                name=name,
                df_type=df_type,
                dataframe=spark_df,
                schema=schema_dict,
                row_count=spark_df.count(),
                created_at=time.time(),
                metadata=metadata or {}
            )
            
            self._dataframes[df_id] = spark_dataframe
            await self._notify_observers("dataframe_created", spark_dataframe)
            return spark_dataframe

    async def read_csv(
        self,
        name: str,
        path: str,
        options: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SparkDataFrame]:
        async with self._lock:
            if not self._spark:
                return None
            
            reader = self._spark.read
            if options:
                for key, value in options.items():
                    reader = reader.option(key, value)
            
            spark_df = reader.csv(path, header=True, inferSchema=True)
            
            df_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            schema_dict = {}
            for field in spark_df.schema.fields:
                schema_dict[field.name] = str(field.dataType)
            
            spark_dataframe = SparkDataFrame(
                id=df_id,
                name=name,
                df_type=SparkDataFrameType.BATCH,
                dataframe=spark_df,
                schema=schema_dict,
                row_count=spark_df.count(),
                created_at=time.time(),
                metadata=metadata or {}
            )
            
            self._dataframes[df_id] = spark_dataframe
            await self._notify_observers("dataframe_created", spark_dataframe)
            return spark_dataframe

    async def read_parquet(
        self,
        name: str,
        path: str,
        options: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SparkDataFrame]:
        async with self._lock:
            if not self._spark:
                return None
            
            reader = self._spark.read
            if options:
                for key, value in options.items():
                    reader = reader.option(key, value)
            
            spark_df = reader.parquet(path)
            
            df_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            schema_dict = {}
            for field in spark_df.schema.fields:
                schema_dict[field.name] = str(field.dataType)
            
            spark_dataframe = SparkDataFrame(
                id=df_id,
                name=name,
                df_type=SparkDataFrameType.BATCH,
                dataframe=spark_df,
                schema=schema_dict,
                row_count=spark_df.count(),
                created_at=time.time(),
                metadata=metadata or {}
            )
            
            self._dataframes[df_id] = spark_dataframe
            await self._notify_observers("dataframe_created", spark_dataframe)
            return spark_dataframe

    async def execute_query(
        self,
        name: str,
        operation: SparkOperation,
        df_id: str,
        parameters: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SparkJob]:
        async with self._lock:
            if df_id not in self._dataframes:
                return None
            
            df = self._dataframes[df_id]
            spark_df = df.dataframe
            
            query_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            query = SparkQuery(
                id=query_id,
                name=name,
                operation=operation,
                query="",
                parameters=parameters,
                created_at=time.time(),
                metadata=metadata or {}
            )
            
            self._queries[query_id] = query
            
            job = SparkJob(
                id=hashlib.md5(f"{query_id}_{time.time()}".encode()).hexdigest(),
                name=name,
                query_id=query_id,
                status="running",
                start_time=time.time(),
                metadata=metadata or {}
            )
            
            self._jobs[job.id] = job
            
            try:
                result = await self._execute_operation(spark_df, operation, parameters)
                job.status = "completed"
                job.end_time = time.time()
                job.result = result
                
                await self._notify_observers("job_completed", job)
                
            except Exception as e:
                job.status = "failed"
                job.end_time = time.time()
                job.error = str(e)
                await self._notify_observers("job_failed", job)
            
            return job

    async def _execute_operation(
        self,
        df: DataFrame,
        operation: SparkOperation,
        parameters: Dict[str, Any]
    ) -> Any:
        if operation == SparkOperation.FILTER:
            condition = parameters.get("condition")
            return df.filter(condition)
        
        elif operation == SparkOperation.SELECT:
            columns = parameters.get("columns", [])
            return df.select(columns)
        
        elif operation == SparkOperation.GROUP:
            columns = parameters.get("columns", [])
            return df.groupBy(columns)
        
        elif operation == SparkOperation.AGGREGATE:
            agg_exprs = parameters.get("aggregations", {})
            group_cols = parameters.get("group_by", [])
            
            if group_cols:
                return df.groupBy(group_cols).agg(agg_exprs)
            else:
                return df.agg(agg_exprs)
        
        elif operation == SparkOperation.JOIN:
            other_df_id = parameters.get("other_df_id")
            join_type = parameters.get("join_type", "inner")
            on = parameters.get("on")
            
            if other_df_id not in self._dataframes:
                raise ValueError(f"DataFrame not found: {other_df_id}")
            
            other_df = self._dataframes[other_df_id].dataframe
            return df.join(other_df, on=on, how=join_type)
        
        elif operation == SparkOperation.UNION:
            other_df_id = parameters.get("other_df_id")
            
            if other_df_id not in self._dataframes:
                raise ValueError(f"DataFrame not found: {other_df_id}")
            
            other_df = self._dataframes[other_df_id].dataframe
            return df.union(other_df)
        
        elif operation == SparkOperation.SORT:
            columns = parameters.get("columns", [])
            ascending = parameters.get("ascending", True)
            return df.sort(*columns, ascending=ascending)
        
        elif operation == SparkOperation.WINDOW:
            partition_by = parameters.get("partition_by", [])
            order_by = parameters.get("order_by", [])
            window_spec = Window.partitionBy(partition_by).orderBy(order_by)
            
            agg_exprs = parameters.get("aggregations", {})
            return df.withColumn("window_agg", agg_exprs).over(window_spec)
        
        elif operation == SparkOperation.PIVOT:
            pivot_col = parameters.get("pivot_col")
            values = parameters.get("values", [])
            agg_col = parameters.get("agg_col")
            agg_func = parameters.get("agg_func", "sum")
            
            return df.groupBy(pivot_col).pivot(values).agg({agg_col: agg_func})
        
        elif operation == SparkOperation.ML:
            return await self._execute_ml_operation(df, parameters)
        
        else:
            raise ValueError(f"Unsupported operation: {operation}")

    async def _execute_ml_operation(self, df: DataFrame, parameters: Dict[str, Any]) -> Any:
        ml_type = parameters.get("ml_type")
        features_cols = parameters.get("features", [])
        label_col = parameters.get("label")
        
        assembler = VectorAssembler(inputCols=features_cols, outputCol="features")
        df = assembler.transform(df)
        
        if parameters.get("scale", False):
            scaler = StandardScaler(inputCol="features", outputCol="scaled_features")
            scaler_model = scaler.fit(df)
            df = scaler_model.transform(df)
            features_col = "scaled_features"
        else:
            features_col = "features"
        
        if ml_type == "kmeans":
            k = parameters.get("k", 5)
            kmeans = KMeans(featuresCol=features_col, k=k, seed=42)
            model = kmeans.fit(df)
            return model.transform(df)
        
        elif ml_type == "random_forest_classifier":
            num_trees = parameters.get("num_trees", 100)
            rf = RandomForestClassifier(featuresCol=features_col, labelCol=label_col, numTrees=num_trees)
            model = rf.fit(df)
            return model.transform(df)
        
        elif ml_type == "random_forest_regression":
            num_trees = parameters.get("num_trees", 100)
            rf = RandomForestRegressor(featuresCol=features_col, labelCol=label_col, numTrees=num_trees)
            model = rf.fit(df)
            return model.transform(df)
        
        elif ml_type == "logistic_regression":
            lr = LogisticRegression(featuresCol=features_col, labelCol=label_col)
            model = lr.fit(df)
            return model.transform(df)
        
        elif ml_type == "linear_regression":
            lr = LinearRegression(featuresCol=features_col, labelCol=label_col)
            model = lr.fit(df)
            return model.transform(df)
        
        else:
            raise ValueError(f"Unsupported ML type: {ml_type}")

    async def get_dataframe(self, df_id: str) -> Optional[SparkDataFrame]:
        return self._dataframes.get(df_id)

    async def get_dataframes(self) -> List[SparkDataFrame]:
        return list(self._dataframes.values())

    async def get_query(self, query_id: str) -> Optional[SparkQuery]:
        return self._queries.get(query_id)

    async def get_job(self, job_id: str) -> Optional[SparkJob]:
        return self._jobs.get(job_id)

    async def get_jobs(self, status: Optional[str] = None) -> List[SparkJob]:
        if status:
            return [j for j in self._jobs.values() if j.status == status]
        return list(self._jobs.values())

    async def get_job_result(self, job_id: str) -> Optional[Any]:
        if job_id not in self._jobs:
            return None
        
        job = self._jobs[job_id]
        if job.status != "completed":
            return None
        
        return job.result

    async def convert_to_pandas(self, df_id: str) -> Optional[pd.DataFrame]:
        if df_id not in self._dataframes:
            return None
        
        spark_df = self._dataframes[df_id].dataframe
        return spark_df.toPandas()

    async def save_dataframe(
        self,
        df_id: str,
        format: str,
        path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        if df_id not in self._dataframes:
            return False
        
        spark_df = self._dataframes[df_id].dataframe
        
        try:
            writer = spark_df.write
            if options:
                for key, value in options.items():
                    writer = writer.option(key, value)
            
            writer.format(format).save(path)
            return True
            
        except Exception as e:
            logger.error(f"Error saving DataFrame: {e}")
            return False

    async def create_temp_view(self, df_id: str, view_name: str) -> bool:
        if df_id not in self._dataframes:
            return False
        
        spark_df = self._dataframes[df_id].dataframe
        spark_df.createOrReplaceTempView(view_name)
        return True

    async def sql_query(self, sql: str) -> Optional[SparkDataFrame]:
        if not self._spark:
            return None
        
        try:
            result_df = self._spark.sql(sql)
            
            df_id = hashlib.md5(f"sql_{time.time()}".encode()).hexdigest()
            
            schema_dict = {}
            for field in result_df.schema.fields:
                schema_dict[field.name] = str(field.dataType)
            
            spark_dataframe = SparkDataFrame(
                id=df_id,
                name="sql_result",
                df_type=SparkDataFrameType.BATCH,
                dataframe=result_df,
                schema=schema_dict,
                row_count=result_df.count(),
                created_at=time.time()
            )
            
            self._dataframes[df_id] = spark_dataframe
            return spark_dataframe
            
        except Exception as e:
            logger.error(f"SQL query error: {e}")
            return None

    async def close(self) -> None:
        if self._spark:
            self._spark.stop()
            self._spark = None
        
        if self._streaming_context:
            self._streaming_context.stop()
            self._streaming_context = None

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
            "dataframes": len(self._dataframes),
            "queries": len(self._queries),
            "jobs": len(self._jobs),
            "running": self._running,
            "spark_version": self._spark.version if self._spark else None,
            "active_jobs": len([j for j in self._jobs.values() if j.status == "running"]),
            "completed_jobs": len([j for j in self._jobs.values() if j.status == "completed"])
        }


__all__ = [
    "SparkMode",
    "SparkDataFrameType",
    "SparkOperation",
    "SparkConfig",
    "SparkDataFrame",
    "SparkQuery",
    "SparkJob",
    "DataSparkManager"
]
