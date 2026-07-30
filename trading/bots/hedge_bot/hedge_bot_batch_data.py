# trading/bots/hedge_bot/hedge_bot_batch_data.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Batch Data Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Batch Data Module

This module provides comprehensive batch data processing capabilities for
the NEXUS Hedge Bot system. It handles large-scale data operations,
including data ingestion, transformation, aggregation, and export.

The module covers:
- Batch Data Ingestion
- Data Transformation
- Data Aggregation
- Data Validation
- Data Cleaning
- Data Normalization
- Data Enrichment
- Data Export
- Bulk Operations
- Scheduled Processing
- Parallel Processing
- Memory Optimization
- Performance Tuning
"""

import os
import sys
import json
import time
import math
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple, Callable, Iterator
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from collections import defaultdict, deque
import threading
import queue

logger = logging.getLogger(__name__)


# ============================================================
# BATCH DATA ENUMS
# ============================================================

class BatchOperation(Enum):
    """Batch operation types"""
    INGEST = "ingest"
    TRANSFORM = "transform"
    AGGREGATE = "aggregate"
    VALIDATE = "validate"
    CLEAN = "clean"
    NORMALIZE = "normalize"
    ENRICH = "enrich"
    EXPORT = "export"
    IMPORT = "import"
    DELETE = "delete"
    UPDATE = "update"


class BatchStatus(Enum):
    """Batch job status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class DataFormat(Enum):
    """Data formats"""
    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"
    ORC = "orc"
    SQL = "sql"
    EXCEL = "excel"
    HDF5 = "hdf5"


# ============================================================
# BATCH DATA DATACLASSES
# ============================================================

@dataclass
class BatchJob:
    """Batch job definition"""
    id: str
    name: str
    operation: BatchOperation
    source: str
    destination: Optional[str] = None
    format: DataFormat = DataFormat.CSV
    chunk_size: int = 10000
    parallel: bool = True
    max_workers: int = 4
    compression: bool = True
    validate: bool = True
    transform: Optional[Dict[str, Any]] = None
    schedule: Optional[str] = None
    status: BatchStatus = BatchStatus.PENDING
    progress: float = 0.0
    records_processed: int = 0
    records_total: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "operation": self.operation.value,
            "source": self.source,
            "destination": self.destination,
            "format": self.format.value,
            "chunk_size": self.chunk_size,
            "parallel": self.parallel,
            "max_workers": self.max_workers,
            "compression": self.compression,
            "validate": self.validate,
            "transform": self.transform,
            "schedule": self.schedule,
            "status": self.status.value,
            "progress": self.progress,
            "records_processed": self.records_processed,
            "records_total": self.records_total,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error": self.error,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class BatchResult:
    """Batch job result"""
    job_id: str
    job_name: str
    operation: BatchOperation
    records_processed: int
    records_failed: int
    records_skipped: int
    processing_time: float
    output_size: Optional[int] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    completed_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "job_id": self.job_id,
            "job_name": self.job_name,
            "operation": self.operation.value,
            "records_processed": self.records_processed,
            "records_failed": self.records_failed,
            "records_skipped": self.records_skipped,
            "processing_time": self.processing_time,
            "output_size": self.output_size,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
            "completed_at": self.completed_at.isoformat(),
        }


# ============================================================
# BATCH DATA ENGINE
# ============================================================

class BatchDataEngine:
    """
    Comprehensive batch data processing engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the batch data engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.data_dir = Path(self.config.get("data_dir", "data"))
        self.temp_dir = Path(self.config.get("temp_dir", "temp"))
        
        # Create directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # State
        self.batch_jobs: Dict[str, BatchJob] = {}
        self.batch_results: Dict[str, BatchResult] = {}
        self.processing_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=self.config.get("max_workers", 4))
        self.process_executor = ProcessPoolExecutor(max_workers=self.config.get("max_processes", 2))
        
        # Threading
        self.threads: List[threading.Thread] = []
        self.stop_requested = False
        
        logger.info("Batch data engine initialized")
    
    # ============================================================
    # BATCH JOB MANAGEMENT
    # ============================================================
    
    def create_batch_job(
        self,
        name: str,
        operation: BatchOperation,
        source: str,
        destination: Optional[str] = None,
        format: DataFormat = DataFormat.CSV,
        chunk_size: int = 10000,
        parallel: bool = True,
        max_workers: int = 4,
        transform: Optional[Dict[str, Any]] = None,
        schedule: Optional[str] = None
    ) -> BatchJob:
        """
        Create a batch job
        
        Args:
            name: Job name
            operation: Batch operation
            source: Source path
            destination: Destination path
            format: Data format
            chunk_size: Chunk size for processing
            parallel: Enable parallel processing
            max_workers: Maximum workers
            transform: Transformation configuration
            schedule: Schedule expression
            
        Returns:
            BatchJob
        """
        job = BatchJob(
            id=f"batch_{int(time.time())}_{len(self.batch_jobs)}",
            name=name,
            operation=operation,
            source=source,
            destination=destination or str(self.data_dir / f"{name}_{int(time.time())}"),
            format=format,
            chunk_size=chunk_size,
            parallel=parallel,
            max_workers=max_workers,
            transform=transform,
            schedule=schedule,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        self.batch_jobs[job.id] = job
        logger.info(f"Created batch job: {name} ({operation.value})")
        return job
    
    def update_batch_job(self, job_id: str, updates: Dict[str, Any]) -> Optional[BatchJob]:
        """
        Update a batch job
        
        Args:
            job_id: Job ID
            updates: Updates to apply
            
        Returns:
            Updated job or None
        """
        job = self.batch_jobs.get(job_id)
        if not job:
            return None
        
        for key, value in updates.items():
            if hasattr(job, key):
                setattr(job, key, value)
        
        job.updated_at = datetime.now()
        logger.info(f"Updated batch job: {job.name}")
        return job
    
    def delete_batch_job(self, job_id: str) -> bool:
        """
        Delete a batch job
        
        Args:
            job_id: Job ID
            
        Returns:
            True if deleted
        """
        if job_id in self.batch_jobs:
            del self.batch_jobs[job_id]
            logger.info(f"Deleted batch job: {job_id}")
            return True
        return False
    
    def get_batch_job(self, job_id: str) -> Optional[BatchJob]:
        """
        Get a batch job
        
        Args:
            job_id: Job ID
            
        Returns:
            BatchJob or None
        """
        return self.batch_jobs.get(job_id)
    
    def get_batch_jobs(self, status: Optional[BatchStatus] = None) -> List[BatchJob]:
        """
        Get batch jobs
        
        Args:
            status: Filter by status
            
        Returns:
            List of batch jobs
        """
        jobs = list(self.batch_jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs
    
    # ============================================================
    # BATCH JOB EXECUTION
    # ============================================================
    
    def run_batch_job(self, job_id: str, async_mode: bool = False) -> Union[BatchResult, threading.Thread]:
        """
        Run a batch job
        
        Args:
            job_id: Job ID
            async_mode: Run asynchronously
            
        Returns:
            BatchResult or Thread
        """
        job = self.batch_jobs.get(job_id)
        if not job:
            raise ValueError(f"Batch job not found: {job_id}")
        
        if async_mode:
            thread = threading.Thread(target=self._run_batch_job_sync, args=(job_id,))
            thread.start()
            self.threads.append(thread)
            return thread
        
        return self._run_batch_job_sync(job_id)
    
    def _run_batch_job_sync(self, job_id: str) -> BatchResult:
        """
        Synchronous batch job execution
        
        Args:
            job_id: Job ID
            
        Returns:
            BatchResult
        """
        job = self.batch_jobs.get(job_id)
        if not job:
            raise ValueError(f"Batch job not found: {job_id}")
        
        start_time = time.time()
        job.start_time = datetime.now()
        job.status = BatchStatus.RUNNING
        job.updated_at = datetime.now()
        
        records_processed = 0
        records_failed = 0
        records_skipped = 0
        errors = []
        warnings = []
        
        try:
            # Execute based on operation
            if job.operation == BatchOperation.INGEST:
                records_processed, errors, warnings = self._ingest_data(job)
            elif job.operation == BatchOperation.TRANSFORM:
                records_processed, errors, warnings = self._transform_data(job)
            elif job.operation == BatchOperation.AGGREGATE:
                records_processed, errors, warnings = self._aggregate_data(job)
            elif job.operation == BatchOperation.VALIDATE:
                records_processed, errors, warnings = self._validate_data(job)
            elif job.operation == BatchOperation.CLEAN:
                records_processed, errors, warnings = self._clean_data(job)
            elif job.operation == BatchOperation.NORMALIZE:
                records_processed, errors, warnings = self._normalize_data(job)
            elif job.operation == BatchOperation.ENRICH:
                records_processed, errors, warnings = self._enrich_data(job)
            elif job.operation == BatchOperation.EXPORT:
                records_processed, errors, warnings = self._export_data(job)
            else:
                raise ValueError(f"Unsupported operation: {job.operation}")
            
            job.status = BatchStatus.COMPLETED
            job.progress = 1.0
            job.records_processed = records_processed
            
            logger.info(f"Batch job completed: {job.name}")
            
        except Exception as e:
            job.status = BatchStatus.FAILED
            job.error = str(e)
            errors.append(str(e))
            logger.error(f"Batch job failed: {job.name} - {e}")
        
        job.end_time = datetime.now()
        job.updated_at = datetime.now()
        
        result = BatchResult(
            job_id=job.id,
            job_name=job.name,
            operation=job.operation,
            records_processed=records_processed,
            records_failed=records_failed,
            records_skipped=records_skipped,
            processing_time=time.time() - start_time,
            errors=errors,
            warnings=warnings,
        )
        
        self.batch_results[job.id] = result
        return result
    
    # ============================================================
    # DATA OPERATIONS
    # ============================================================
    
    def _ingest_data(self, job: BatchJob) -> Tuple[int, List[str], List[str]]:
        """
        Ingest data
        
        Args:
            job: Batch job
            
        Returns:
            (records_processed, errors, warnings)
        """
        source_path = Path(job.source)
        errors = []
        warnings = []
        records_processed = 0
        
        try:
            if job.format == DataFormat.CSV:
                # Read CSV in chunks
                chunks = pd.read_csv(source_path, chunksize=job.chunk_size)
                for chunk in chunks:
                    records_processed += len(chunk)
                    # Process chunk if needed
                    if job.transform:
                        chunk = self._apply_transformations(chunk, job.transform)
                    
                    # Save to destination
                    if job.destination:
                        output_path = Path(job.destination)
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        chunk.to_csv(output_path, mode='a', header=not output_path.exists())
            
            elif job.format == DataFormat.JSON:
                with open(source_path, 'r') as f:
                    data = json.load(f)
                    records_processed = len(data)
                    if job.transform:
                        data = self._apply_transformations_to_list(data, job.transform)
                    if job.destination:
                        with open(job.destination, 'w') as f:
                            json.dump(data, f, indent=2)
            
            elif job.format == DataFormat.PARQUET:
                df = pd.read_parquet(source_path)
                records_processed = len(df)
                if job.transform:
                    df = self._apply_transformations(df, job.transform)
                if job.destination:
                    df.to_parquet(job.destination)
            
            else:
                errors.append(f"Unsupported format: {job.format}")
        
        except Exception as e:
            errors.append(str(e))
        
        return records_processed, errors, warnings
    
    def _transform_data(self, job: BatchJob) -> Tuple[int, List[str], List[str]]:
        """
        Transform data
        
        Args:
            job: Batch job
            
        Returns:
            (records_processed, errors, warnings)
        """
        source_path = Path(job.source)
        errors = []
        warnings = []
        records_processed = 0
        
        if not job.transform:
            errors.append("No transformation specified")
            return 0, errors, warnings
        
        try:
            df = self._load_data(source_path, job.format)
            records_processed = len(df)
            
            # Apply transformations
            transformed_df = self._apply_transformations(df, job.transform)
            
            # Save to destination
            if job.destination:
                self._save_data(transformed_df, job.destination, job.format)
            
        except Exception as e:
            errors.append(str(e))
        
        return records_processed, errors, warnings
    
    def _aggregate_data(self, job: BatchJob) -> Tuple[int, List[str], List[str]]:
        """
        Aggregate data
        
        Args:
            job: Batch job
            
        Returns:
            (records_processed, errors, warnings)
        """
        source_path = Path(job.source)
        errors = []
        warnings = []
        records_processed = 0
        
        try:
            df = self._load_data(source_path, job.format)
            records_processed = len(df)
            
            # Apply aggregation
            agg_config = job.transform.get("aggregation", {}) if job.transform else {}
            group_by = agg_config.get("group_by", [])
            aggregations = agg_config.get("aggregations", {})
            
            if group_by and aggregations:
                aggregated_df = df.groupby(group_by).agg(aggregations)
            else:
                # Default aggregation: count and sum
                aggregated_df = df.agg(['count', 'sum'])
            
            # Save to destination
            if job.destination:
                self._save_data(aggregated_df, job.destination, job.format)
            
        except Exception as e:
            errors.append(str(e))
        
        return records_processed, errors, warnings
    
    def _validate_data(self, job: BatchJob) -> Tuple[int, List[str], List[str]]:
        """
        Validate data
        
        Args:
            job: Batch job
            
        Returns:
            (records_processed, errors, warnings)
        """
        source_path = Path(job.source)
        errors = []
        warnings = []
        records_processed = 0
        
        validation_rules = job.transform.get("validation", {}) if job.transform else {}
        
        try:
            df = self._load_data(source_path, job.format)
            records_processed = len(df)
            
            # Validate data types
            if "data_types" in validation_rules:
                for col, dtype in validation_rules["data_types"].items():
                    if col in df.columns:
                        if not pd.api.types.is_dtype_equal(df[col].dtype, dtype):
                            warnings.append(f"Column {col} expected {dtype} but got {df[col].dtype}")
            
            # Validate null values
            if "null_allowed" in validation_rules:
                for col, allowed in validation_rules["null_allowed"].items():
                    if col in df.columns:
                        null_count = df[col].isna().sum()
                        if null_count > 0 and not allowed:
                            errors.append(f"Column {col} has {null_count} null values")
            
            # Validate ranges
            if "ranges" in validation_rules:
                for col, range_info in validation_rules["ranges"].items():
                    if col in df.columns:
                        min_val = range_info.get("min")
                        max_val = range_info.get("max")
                        if min_val is not None:
                            invalid = df[df[col] < min_val]
                            if len(invalid) > 0:
                                warnings.append(f"Column {col} has {len(invalid)} values below {min_val}")
                        if max_val is not None:
                            invalid = df[df[col] > max_val]
                            if len(invalid) > 0:
                                warnings.append(f"Column {col} has {len(invalid)} values above {max_val}")
            
            # Validate unique values
            if "unique" in validation_rules:
                for col in validation_rules["unique"]:
                    if col in df.columns:
                        if not df[col].is_unique:
                            warnings.append(f"Column {col} has duplicate values")
            
            # Validate regex patterns
            if "regex" in validation_rules:
                for col, pattern in validation_rules["regex"].items():
                    if col in df.columns:
                        invalid = df[~df[col].astype(str).str.match(pattern)]
                        if len(invalid) > 0:
                            warnings.append(f"Column {col} has {len(invalid)} values not matching pattern")
            
        except Exception as e:
            errors.append(str(e))
        
        return records_processed, errors, warnings
    
    def _clean_data(self, job: BatchJob) -> Tuple[int, List[str], List[str]]:
        """
        Clean data
        
        Args:
            job: Batch job
            
        Returns:
            (records_processed, errors, warnings)
        """
        source_path = Path(job.source)
        errors = []
        warnings = []
        records_processed = 0
        
        clean_config = job.transform.get("clean", {}) if job.transform else {}
        
        try:
            df = self._load_data(source_path, job.format)
            records_processed = len(df)
            
            # Remove duplicates
            if clean_config.get("remove_duplicates", False):
                df = df.drop_duplicates()
            
            # Handle null values
            if "handle_null" in clean_config:
                for col, strategy in clean_config["handle_null"].items():
                    if col in df.columns:
                        if strategy == "drop":
                            df = df.dropna(subset=[col])
                        elif strategy == "fill":
                            fill_value = clean_config.get("fill_value", {}).get(col, 0)
                            df[col] = df[col].fillna(fill_value)
                        elif strategy == "interpolate":
                            df[col] = df[col].interpolate()
            
            # Remove outliers
            if clean_config.get("remove_outliers", False):
                for col in clean_config.get("outlier_columns", []):
                    if col in df.columns:
                        q1 = df[col].quantile(0.25)
                        q3 = df[col].quantile(0.75)
                        iqr = q3 - q1
                        lower = q1 - 1.5 * iqr
                        upper = q3 + 1.5 * iqr
                        df = df[(df[col] >= lower) & (df[col] <= upper)]
            
            # Save to destination
            if job.destination:
                self._save_data(df, job.destination, job.format)
            
        except Exception as e:
            errors.append(str(e))
        
        return records_processed, errors, warnings
    
    def _normalize_data(self, job: BatchJob) -> Tuple[int, List[str], List[str]]:
        """
        Normalize data
        
        Args:
            job: Batch job
            
        Returns:
            (records_processed, errors, warnings)
        """
        source_path = Path(job.source)
        errors = []
        warnings = []
        records_processed = 0
        
        normalize_config = job.transform.get("normalize", {}) if job.transform else {}
        
        try:
            df = self._load_data(source_path, job.format)
            records_processed = len(df)
            
            if normalize_config:
                method = normalize_config.get("method", "min_max")
                columns = normalize_config.get("columns", df.columns.tolist())
                
                for col in columns:
                    if col in df.columns:
                        if method == "min_max":
                            min_val = df[col].min()
                            max_val = df[col].max()
                            if max_val != min_val:
                                df[col] = (df[col] - min_val) / (max_val - min_val)
                        elif method == "z_score":
                            mean = df[col].mean()
                            std = df[col].std()
                            if std > 0:
                                df[col] = (df[col] - mean) / std
                        elif method == "robust":
                            median = df[col].median()
                            q1 = df[col].quantile(0.25)
                            q3 = df[col].quantile(0.75)
                            iqr = q3 - q1
                            if iqr > 0:
                                df[col] = (df[col] - median) / iqr
            
            # Save to destination
            if job.destination:
                self._save_data(df, job.destination, job.format)
            
        except Exception as e:
            errors.append(str(e))
        
        return records_processed, errors, warnings
    
    def _enrich_data(self, job: BatchJob) -> Tuple[int, List[str], List[str]]:
        """
        Enrich data
        
        Args:
            job: Batch job
            
        Returns:
            (records_processed, errors, warnings)
        """
        source_path = Path(job.source)
        errors = []
        warnings = []
        records_processed = 0
        
        enrich_config = job.transform.get("enrich", {}) if job.transform else {}
        
        try:
            df = self._load_data(source_path, job.format)
            records_processed = len(df)
            
            # Add derived columns
            if "derived_columns" in enrich_config:
                for col, formula in enrich_config["derived_columns"].items():
                    # Simple formula evaluation
                    try:
                        df[col] = df.eval(formula)
                    except:
                        warnings.append(f"Failed to evaluate formula for {col}: {formula}")
            
            # Add computed columns
            if "computed_columns" in enrich_config:
                for col, config in enrich_config["computed_columns"].items():
                    # Add computed column
                    pass
            
            # Save to destination
            if job.destination:
                self._save_data(df, job.destination, job.format)
            
        except Exception as e:
            errors.append(str(e))
        
        return records_processed, errors, warnings
    
    def _export_data(self, job: BatchJob) -> Tuple[int, List[str], List[str]]:
        """
        Export data
        
        Args:
            job: Batch job
            
        Returns:
            (records_processed, errors, warnings)
        """
        source_path = Path(job.source)
        errors = []
        warnings = []
        records_processed = 0
        
        try:
            df = self._load_data(source_path, job.format)
            records_processed = len(df)
            
            # Export based on format
            if job.destination:
                self._save_data(df, job.destination, job.format)
            
        except Exception as e:
            errors.append(str(e))
        
        return records_processed, errors, warnings
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def _load_data(self, path: Path, format: DataFormat) -> pd.DataFrame:
        """
        Load data from file
        
        Args:
            path: File path
            format: Data format
            
        Returns:
            DataFrame
        """
        if format == DataFormat.CSV:
            return pd.read_csv(path)
        elif format == DataFormat.JSON:
            return pd.read_json(path)
        elif format == DataFormat.PARQUET:
            return pd.read_parquet(path)
        elif format == DataFormat.EXCEL:
            return pd.read_excel(path)
        elif format == DataFormat.HDF5:
            return pd.read_hdf(path)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _save_data(self, df: pd.DataFrame, path: str, format: DataFormat) -> None:
        """
        Save data to file
        
        Args:
            df: DataFrame
            path: File path
            format: Data format
        """
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == DataFormat.CSV:
            df.to_csv(output_path, index=False)
        elif format == DataFormat.JSON:
            df.to_json(output_path, orient='records', indent=2)
        elif format == DataFormat.PARQUET:
            df.to_parquet(output_path, index=False)
        elif format == DataFormat.EXCEL:
            df.to_excel(output_path, index=False)
        elif format == DataFormat.HDF5:
            df.to_hdf(output_path, key='data', mode='w')
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _apply_transformations(self, df: pd.DataFrame, transform_config: Dict[str, Any]) -> pd.DataFrame:
        """
        Apply transformations to DataFrame
        
        Args:
            df: DataFrame
            transform_config: Transformation configuration
            
        Returns:
            Transformed DataFrame
        """
        if not transform_config:
            return df
        
        # Select columns
        if "select" in transform_config:
            columns = transform_config["select"]
            df = df[columns] if all(c in df.columns for c in columns) else df
        
        # Rename columns
        if "rename" in transform_config:
            df = df.rename(columns=transform_config["rename"])
        
        # Add calculated columns
        if "calculated" in transform_config:
            for col, formula in transform_config["calculated"].items():
                try:
                    df[col] = df.eval(formula)
                except:
                    pass
        
        # Filter rows
        if "filter" in transform_config:
            query = transform_config["filter"]
            try:
                df = df.query(query)
            except:
                pass
        
        # Sort rows
        if "sort" in transform_config:
            sort_config = transform_config["sort"]
            by = sort_config.get("by", [])
            ascending = sort_config.get("ascending", True)
            if by:
                df = df.sort_values(by, ascending=ascending)
        
        # Sample rows
        if "sample" in transform_config:
            n = transform_config["sample"]
            frac = transform_config.get("frac", None)
            if frac:
                df = df.sample(frac=frac)
            else:
                df = df.sample(n=n)
        
        return df
    
    def _apply_transformations_to_list(self, data: List[Dict], transform_config: Dict[str, Any]) -> List[Dict]:
        """
        Apply transformations to list of dictionaries
        
        Args:
            data: List of dictionaries
            transform_config: Transformation configuration
            
        Returns:
            Transformed data
        """
        if not transform_config:
            return data
        
        transformed = []
        for item in data:
            new_item = item.copy()
            
            # Select fields
            if "select" in transform_config:
                new_item = {k: v for k, v in new_item.items() if k in transform_config["select"]}
            
            # Rename fields
            if "rename" in transform_config:
                for old, new in transform_config["rename"].items():
                    if old in new_item:
                        new_item[new] = new_item.pop(old)
            
            transformed.append(new_item)
        
        return transformed
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get batch statistics
        
        Returns:
            Statistics dictionary
        """
        total_jobs = len(self.batch_jobs)
        completed = len([j for j in self.batch_jobs.values() if j.status == BatchStatus.COMPLETED])
        failed = len([j for j in self.batch_jobs.values() if j.status == BatchStatus.FAILED])
        running = len([j for j in self.batch_jobs.values() if j.status == BatchStatus.RUNNING])
        
        return {
            "total_jobs": total_jobs,
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": total_jobs - completed - failed - running,
            "total_records_processed": sum(j.records_processed for j in self.batch_jobs.values()),
            "jobs_by_operation": {
                op.value: len([j for j in self.batch_jobs.values() if j.operation == op])
                for op in BatchOperation
            },
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "BatchOperation",
    "BatchStatus",
    "DataFormat",
    
    # Dataclasses
    "BatchJob",
    "BatchResult",
    
    # Classes
    "BatchDataEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
