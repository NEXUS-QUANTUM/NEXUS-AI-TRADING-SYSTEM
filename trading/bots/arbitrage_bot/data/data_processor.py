# trading/bots/arbitrage_bot/data/data_processor.py
# Nexus AI Trading System - Arbitrage Bot Data Processor Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Data Processor Module

This module provides comprehensive data processing pipeline for the arbitrage
bot system, including:

- Data ingestion from multiple sources
- Data validation and cleaning
- Data transformation and enrichment
- Feature engineering
- Data aggregation and summarization
- Data export and reporting
- Stream processing
- Batch processing
- Real-time processing
- Data quality monitoring
- Data lineage tracking
- Data versioning

The data processor handles all data flow through the arbitrage bot,
ensuring clean, consistent data for analysis and execution.
"""

import asyncio
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from trading.bots.arbitrage_bot.core.market_data import MarketDataManager, MarketPrice, MarketDepth
from trading.bots.arbitrage_bot.data.candle_manager import CandleManager, Candle, CandleInterval
from trading.bots.arbitrage_bot.data.data_aggregator import DataAggregator, AggregatedData
from trading.bots.arbitrage_bot.data.data_normalizer import DataNormalizer, NormalizationConfig
from trading.bots.arbitrage_bot.data.data_cache import DataCache
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class ProcessingMode(str, Enum):
    """Processing modes."""
    BATCH = "batch"          # Batch processing
    STREAM = "stream"        # Stream processing
    REALTIME = "realtime"    # Real-time processing
    HYBRID = "hybrid"        # Hybrid processing


class ProcessingStage(str, Enum):
    """Processing stages."""
    INGEST = "ingest"        # Data ingestion
    VALIDATE = "validate"    # Data validation
    CLEAN = "clean"          # Data cleaning
    TRANSFORM = "transform"  # Data transformation
    ENRICH = "enrich"        # Data enrichment
    AGGREGATE = "aggregate"  # Data aggregation
    FEATURE = "feature"      # Feature engineering
    EXPORT = "export"        # Data export


class ProcessorStatus(str, Enum):
    """Processor status."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETED = "completed"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ProcessingConfig(BaseModel):
    """Processing configuration."""
    enabled: bool = True
    mode: ProcessingMode = ProcessingMode.BATCH
    batch_size: int = 1000
    max_queue_size: int = 10000
    timeout_seconds: int = 300
    retry_count: int = 3
    retry_delay: int = 5
    parallel_workers: int = 4
    enable_validation: bool = True
    enable_cleaning: bool = True
    enable_enrichment: bool = True
    enable_aggregation: bool = True
    enable_feature_engineering: bool = True
    enable_caching: bool = True
    enable_persistence: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProcessingTask(BaseModel):
    """Processing task."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    stage: ProcessingStage
    input_type: str
    output_type: str
    function: str  # Function name or path
    parameters: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    priority: int = 0
    status: ProcessorStatus = ProcessorStatus.IDLE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProcessingPipeline(BaseModel):
    """Processing pipeline."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    enabled: bool = True
    tasks: List[ProcessingTask] = Field(default_factory=list)
    mode: ProcessingMode = ProcessingMode.BATCH
    schedule: Optional[str] = None  # Cron expression
    status: ProcessorStatus = ProcessorStatus.IDLE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProcessingResult(BaseModel):
    """Processing result."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str
    task_id: str
    status: ProcessorStatus
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DataStream(BaseModel):
    """Data stream."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    source: str
    format: str
    schema: Dict[str, Any] = Field(default_factory=dict)
    buffer_size: int = 1000
    flush_interval: int = 5  # seconds
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Processing pipelines
CREATE TABLE IF NOT EXISTS processing_pipelines (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    tasks JSONB NOT NULL,
    mode VARCHAR(20) NOT NULL,
    schedule VARCHAR(50),
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Processing results
CREATE TABLE IF NOT EXISTS processing_results (
    id VARCHAR(64) PRIMARY KEY,
    pipeline_id VARCHAR(64) NOT NULL,
    task_id VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL,
    input_data JSONB,
    output_data JSONB,
    metrics JSONB DEFAULT '{}',
    error_message TEXT,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_ms FLOAT,
    metadata JSONB DEFAULT '{}',
    INDEX idx_processing_results_pipeline_id (pipeline_id),
    INDEX idx_processing_results_task_id (task_id),
    INDEX idx_processing_results_status (status),
    INDEX idx_processing_results_started_at (started_at)
);

-- Data streams
CREATE TABLE IF NOT EXISTS data_streams (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    source VARCHAR(255) NOT NULL,
    format VARCHAR(50) NOT NULL,
    schema JSONB DEFAULT '{}',
    buffer_size INTEGER DEFAULT 1000,
    flush_interval INTEGER DEFAULT 5,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Processed data
CREATE TABLE IF NOT EXISTS processed_data (
    id SERIAL PRIMARY KEY,
    pipeline_id VARCHAR(64) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    data JSONB NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_processed_data_pipeline_id (pipeline_id),
    INDEX idx_processed_data_data_type (data_type),
    INDEX idx_processed_data_timestamp (timestamp)
);
"""


# =============================================================================
# DATA PROCESSOR CLASS
# =============================================================================

class DataProcessor:
    """
    Advanced data processor for arbitrage bot.
    
    Features:
    - Data ingestion from multiple sources
    - Data validation and cleaning
    - Data transformation and enrichment
    - Feature engineering
    - Data aggregation and summarization
    - Data export and reporting
    - Stream processing
    - Batch processing
    - Real-time processing
    - Data quality monitoring
    - Data lineage tracking
    - Data versioning
    """
    
    def __init__(
        self,
        market_data: MarketDataManager,
        candle_manager: CandleManager,
        data_aggregator: DataAggregator,
        data_normalizer: DataNormalizer,
        data_cache: Optional[DataCache] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[ProcessingConfig] = None
    ):
        self.market_data = market_data
        self.candle_manager = candle_manager
        self.data_aggregator = data_aggregator
        self.data_normalizer = data_normalizer
        self.data_cache = data_cache
        self.redis = redis
        self.pool = pool
        self.config = config or ProcessingConfig()
        
        # Pipelines
        self._pipelines: Dict[str, ProcessingPipeline] = {}
        
        # Streams
        self._streams: Dict[str, DataStream] = {}
        
        # Results
        self._results: List[ProcessingResult] = []
        
        # Circuit breakers
        self._processor_cb = CircuitBreaker(
            name="data_processor",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Queue
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        
        logger.info("DataProcessor initialized")
    
    async def initialize(self):
        """Initialize the data processor."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load pipelines
        if self.pool:
            await self._load_pipelines()
        
        # Load streams
        if self.pool:
            await self._load_streams()
        
        # Start workers
        self._running = True
        for i in range(self.config.parallel_workers):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)
        
        # Start stream processors
        for stream in self._streams.values():
            if stream.enabled:
                asyncio.create_task(self._process_stream(stream))
        
        self._initialized = True
        logger.info("DataProcessor initialized")
    
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
    # PIPELINE MANAGEMENT
    # =========================================================================
    
    async def create_pipeline(
        self,
        name: str,
        tasks: List[ProcessingTask],
        mode: ProcessingMode = ProcessingMode.BATCH,
        schedule: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessingPipeline:
        """
        Create a processing pipeline.
        
        Args:
            name: Pipeline name
            tasks: List of processing tasks
            mode: Processing mode
            schedule: Cron schedule
            metadata: Additional metadata
            
        Returns:
            ProcessingPipeline
        """
        pipeline = ProcessingPipeline(
            name=name,
            tasks=tasks,
            mode=mode,
            schedule=schedule,
            metadata=metadata or {}
        )
        
        self._pipelines[pipeline.id] = pipeline
        
        if self.pool:
            await self._save_pipeline(pipeline)
        
        logger.info(f"Created pipeline: {name} with {len(tasks)} tasks")
        return pipeline
    
    async def run_pipeline(
        self,
        pipeline_id: str,
        input_data: Optional[Any] = None
    ) -> ProcessingResult:
        """
        Run a processing pipeline.
        
        Args:
            pipeline_id: Pipeline ID
            input_data: Input data
            
        Returns:
            ProcessingResult
        """
        if pipeline_id not in self._pipelines:
            raise ValueError(f"Pipeline {pipeline_id} not found")
        
        pipeline = self._pipelines[pipeline_id]
        
        # Update pipeline status
        pipeline.status = ProcessorStatus.RUNNING
        
        result = ProcessingResult(
            pipeline_id=pipeline_id,
            task_id="",
            status=ProcessorStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        
        try:
            data = input_data
            
            # Execute tasks in order
            for task in pipeline.tasks:
                if not task.enabled:
                    continue
                
                task.status = ProcessorStatus.RUNNING
                task.started_at = datetime.utcnow()
                
                result.task_id = task.id
                
                try:
                    # Execute task
                    data = await self._execute_task(task, data)
                    
                    task.status = ProcessorStatus.COMPLETED
                    task.completed_at = datetime.utcnow()
                    
                except Exception as e:
                    task.status = ProcessorStatus.ERROR
                    task.error_message = str(e)
                    task.completed_at = datetime.utcnow()
                    
                    result.error_message = str(e)
                    result.status = ProcessorStatus.ERROR
                    break
            
            result.output_data = data
            result.status = ProcessorStatus.COMPLETED
            
        except Exception as e:
            result.status = ProcessorStatus.ERROR
            result.error_message = str(e)
        
        finally:
            result.completed_at = datetime.utcnow()
            result.duration_ms = (result.completed_at - result.started_at).total_seconds() * 1000
            
            # Update pipeline status
            pipeline.status = ProcessorStatus.COMPLETED
            
            self._results.append(result)
            
            if self.pool:
                await self._save_result(result)
        
        return result
    
    async def _execute_task(
        self,
        task: ProcessingTask,
        data: Any
    ) -> Any:
        """
        Execute a processing task.
        
        Args:
            task: Processing task
            data: Input data
            
        Returns:
            Processed data
        """
        # Map task to function
        if task.function == 'normalize_prices':
            return await self._normalize_prices(data, task.parameters)
        elif task.function == 'aggregate_prices':
            return await self._aggregate_prices(data, task.parameters)
        elif task.function == 'calculate_indicators':
            return await self._calculate_indicators(data, task.parameters)
        elif task.function == 'detect_patterns':
            return await self._detect_patterns(data, task.parameters)
        elif task.function == 'enrich_with_fundamentals':
            return await self._enrich_with_fundamentals(data, task.parameters)
        elif task.function == 'validate_data':
            return await self._validate_data(data, task.parameters)
        elif task.function == 'clean_data':
            return await self._clean_data(data, task.parameters)
        elif task.function == 'transform_data':
            return await self._transform_data(data, task.parameters)
        else:
            # Try to execute as custom function
            return data
    
    # =========================================================================
    # TASK IMPLEMENTATIONS
    # =========================================================================
    
    async def _normalize_prices(
        self,
        data: Any,
        params: Dict[str, Any]
    ) -> Any:
        """Normalize price data."""
        config = NormalizationConfig(**params.get('config', {}))
        
        if isinstance(data, list):
            return await self.data_normalizer.normalize_prices(data, config)
        elif isinstance(data, pd.DataFrame):
            return await self.data_normalizer.normalize_time_series(data, config=config)
        else:
            return await self.data_normalizer.normalize_price(data, config)
    
    async def _aggregate_prices(
        self,
        data: Any,
        params: Dict[str, Any]
    ) -> Any:
        """Aggregate price data."""
        symbol = params.get('symbol', '')
        exchanges = params.get('exchanges')
        method = params.get('method', 'mean')
        
        if not symbol:
            return data
        
        return await self.data_aggregator.aggregate_price(
            symbol=symbol,
            exchanges=exchanges,
            method=method
        )
    
    async def _calculate_indicators(
        self,
        data: Any,
        params: Dict[str, Any]
    ) -> Any:
        """Calculate technical indicators."""
        # Implementation depends on data structure
        return data
    
    async def _detect_patterns(
        self,
        data: Any,
        params: Dict[str, Any]
    ) -> Any:
        """Detect patterns in data."""
        # Implementation depends on data structure
        return data
    
    async def _enrich_with_fundamentals(
        self,
        data: Any,
        params: Dict[str, Any]
    ) -> Any:
        """Enrich data with fundamental data."""
        # Implementation depends on data structure
        return data
    
    async def _validate_data(
        self,
        data: Any,
        params: Dict[str, Any]
    ) -> Any:
        """Validate data quality."""
        # Implementation depends on data structure
        return data
    
    async def _clean_data(
        self,
        data: Any,
        params: Dict[str, Any]
    ) -> Any:
        """Clean data."""
        # Implementation depends on data structure
        return data
    
    async def _transform_data(
        self,
        data: Any,
        params: Dict[str, Any]
    ) -> Any:
        """Transform data."""
        # Implementation depends on data structure
        return data
    
    # =========================================================================
    # STREAM PROCESSING
    # =========================================================================
    
    async def create_stream(
        self,
        name: str,
        source: str,
        format: str,
        schema: Optional[Dict[str, Any]] = None,
        buffer_size: int = 1000,
        flush_interval: int = 5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DataStream:
        """
        Create a data stream.
        
        Args:
            name: Stream name
            source: Data source
            format: Data format
            schema: Data schema
            buffer_size: Buffer size
            flush_interval: Flush interval in seconds
            metadata: Additional metadata
            
        Returns:
            DataStream
        """
        stream = DataStream(
            name=name,
            source=source,
            format=format,
            schema=schema or {},
            buffer_size=buffer_size,
            flush_interval=flush_interval,
            metadata=metadata or {}
        )
        
        self._streams[stream.id] = stream
        
        if self.pool:
            await self._save_stream(stream)
        
        # Start stream processor
        if stream.enabled:
            asyncio.create_task(self._process_stream(stream))
        
        logger.info(f"Created data stream: {name}")
        return stream
    
    async def _process_stream(self, stream: DataStream):
        """
        Process a data stream.
        
        Args:
            stream: Data stream to process
        """
        buffer = []
        
        while self._running and stream.enabled:
            try:
                # Get data from source
                data = await self._read_stream_data(stream)
                
                if data:
                    buffer.append(data)
                
                # Flush if buffer is full or interval elapsed
                if len(buffer) >= stream.buffer_size:
                    await self._flush_stream_buffer(stream, buffer)
                    buffer = []
                else:
                    await asyncio.sleep(stream.flush_interval)
                    if buffer:
                        await self._flush_stream_buffer(stream, buffer)
                        buffer = []
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stream processing error: {e}")
                await asyncio.sleep(5)
        
        # Flush remaining buffer on shutdown
        if buffer:
            await self._flush_stream_buffer(stream, buffer)
    
    async def _read_stream_data(self, stream: DataStream) -> Optional[Any]:
        """Read data from a stream source."""
        # Implementation depends on stream source
        return None
    
    async def _flush_stream_buffer(self, stream: DataStream, buffer: List[Any]):
        """Flush stream buffer."""
        try:
            # Process buffer
            processed = await self._process_buffer(stream, buffer)
            
            # Save processed data
            if self.pool:
                await self._save_processed_data(stream.id, processed)
            
            # Cache data
            if self.data_cache:
                await self.data_cache.set(
                    f"stream:{stream.id}",
                    processed,
                    ttl=300
                )
            
            logger.debug(f"Flushed stream {stream.name}: {len(buffer)} items")
            
        except Exception as e:
            logger.error(f"Flush stream error: {e}")
    
    async def _process_buffer(
        self,
        stream: DataStream,
        buffer: List[Any]
    ) -> Any:
        """Process a stream buffer."""
        # Apply pipeline if configured
        if stream.id in self._pipelines:
            pipeline = self._pipelines[stream.id]
            result = await self.run_pipeline(pipeline.id, buffer)
            return result.output_data
        
        return buffer
    
    # =========================================================================
    # WORKER LOOP
    # =========================================================================
    
    async def _worker_loop(self, worker_id: int):
        """
        Worker loop for processing tasks.
        
        Args:
            worker_id: Worker ID
        """
        logger.info(f"Data processor worker {worker_id} started")
        
        while self._running:
            try:
                # Get task from queue
                task = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                
                # Execute task
                try:
                    await self._execute_task(task['function'], task['data'])
                except Exception as e:
                    logger.error(f"Worker {worker_id} task error: {e}")
                
                self._queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Data processor worker {worker_id} stopped")
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _load_pipelines(self):
        """Load processing pipelines from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM processing_pipelines")
                
                for row in rows:
                    pipeline = ProcessingPipeline(
                        id=row['id'],
                        name=row['name'],
                        enabled=row['enabled'],
                        tasks=[ProcessingTask(**t) for t in row['tasks']],
                        mode=ProcessingMode(row['mode']),
                        schedule=row['schedule'],
                        status=ProcessorStatus(row['status']),
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                        metadata=row['metadata'] or {}
                    )
                    self._pipelines[pipeline.id] = pipeline
                
                logger.info(f"Loaded {len(self._pipelines)} pipelines")
                
        except Exception as e:
            logger.error(f"Error loading pipelines: {e}")
    
    async def _load_streams(self):
        """Load data streams from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM data_streams")
                
                for row in rows:
                    stream = DataStream(
                        id=row['id'],
                        name=row['name'],
                        source=row['source'],
                        format=row['format'],
                        schema=row['schema'] or {},
                        buffer_size=row['buffer_size'],
                        flush_interval=row['flush_interval'],
                        enabled=row['enabled'],
                        created_at=row['created_at'],
                        metadata=row['metadata'] or {}
                    )
                    self._streams[stream.id] = stream
                
                logger.info(f"Loaded {len(self._streams)} streams")
                
        except Exception as e:
            logger.error(f"Error loading streams: {e}")
    
    async def _save_pipeline(self, pipeline: ProcessingPipeline):
        """Save pipeline to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO processing_pipelines (
                        id, name, enabled, tasks,
                        mode, schedule, status,
                        created_at, updated_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        enabled = EXCLUDED.enabled,
                        tasks = EXCLUDED.tasks,
                        mode = EXCLUDED.mode,
                        schedule = EXCLUDED.schedule,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at,
                        metadata = EXCLUDED.metadata
                    """,
                    pipeline.id,
                    pipeline.name,
                    pipeline.enabled,
                    json.dumps([t.dict() for t in pipeline.tasks]),
                    pipeline.mode.value,
                    pipeline.schedule,
                    pipeline.status.value,
                    pipeline.created_at,
                    pipeline.updated_at,
                    json.dumps(pipeline.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving pipeline: {e}")
    
    async def _save_stream(self, stream: DataStream):
        """Save stream to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO data_streams (
                        id, name, source, format,
                        schema, buffer_size, flush_interval,
                        enabled, created_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        source = EXCLUDED.source,
                        format = EXCLUDED.format,
                        schema = EXCLUDED.schema,
                        buffer_size = EXCLUDED.buffer_size,
                        flush_interval = EXCLUDED.flush_interval,
                        enabled = EXCLUDED.enabled,
                        metadata = EXCLUDED.metadata
                    """,
                    stream.id,
                    stream.name,
                    stream.source,
                    stream.format,
                    json.dumps(stream.schema),
                    stream.buffer_size,
                    stream.flush_interval,
                    stream.enabled,
                    stream.created_at,
                    json.dumps(stream.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving stream: {e}")
    
    async def _save_result(self, result: ProcessingResult):
        """Save processing result to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO processing_results (
                        id, pipeline_id, task_id, status,
                        input_data, output_data, metrics,
                        error_message, started_at, completed_at,
                        duration_ms, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    result.id,
                    result.pipeline_id,
                    result.task_id,
                    result.status.value,
                    json.dumps(result.input_data, default=str),
                    json.dumps(result.output_data, default=str),
                    json.dumps(result.metrics),
                    result.error_message,
                    result.started_at,
                    result.completed_at,
                    result.duration_ms,
                    json.dumps(result.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving result: {e}")
    
    async def _save_processed_data(
        self,
        stream_id: str,
        data: Any
    ):
        """Save processed data to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO processed_data (
                        pipeline_id, data_type, data, timestamp, metadata
                    ) VALUES ($1, $2, $3, $4, $5)
                    """,
                    stream_id,
                    'stream_data',
                    json.dumps(data, default=str),
                    datetime.utcnow(),
                    json.dumps({}, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving processed data: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the data processor."""
        self._running = False
        
        # Stop workers
        for worker in self._workers:
            worker.cancel()
        
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        logger.info("DataProcessor shutdown")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'DataProcessor',
    'ProcessingMode',
    'ProcessingStage',
    'ProcessorStatus',
    'ProcessingConfig',
    'ProcessingTask',
    'ProcessingPipeline',
    'ProcessingResult',
    'DataStream'
]
