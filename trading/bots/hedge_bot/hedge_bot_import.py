# trading/bots/hedge_bot/hedge_bot_import.py

import asyncio
import logging
import time
import json
import csv
import io
import os
import hashlib
import zipfile
import tarfile
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable, BinaryIO
from decimal import Decimal
from collections import defaultdict
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class ImportFormat(str, Enum):
    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"
    EXCEL = "excel"
    XML = "xml"
    SQL = "sql"
    PICKLE = "pickle"
    HDF5 = "hdf5"
    FEATHER = "feather"
    ORC = "orc"
    AVRO = "avro"
    PROTOBUF = "protobuf"
    BSON = "bson"
    YAML = "yaml"
    TOML = "toml"
    TEXT = "text"
    BINARY = "binary"


class ImportSource(str, Enum):
    FILE = "file"
    URL = "url"
    API = "api"
    DATABASE = "database"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"
    FTP = "ftp"
    SFTP = "sftp"
    EMAIL = "email"
    WEBHOOK = "webhook"
    STREAM = "stream"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    REDIS = "redis"
    MEMORY = "memory"
    CLIPBOARD = "clipboard"


class ImportMode(str, Enum):
    OVERWRITE = "overwrite"
    APPEND = "append"
    MERGE = "merge"
    UPSERT = "upsert"
    REPLACE = "replace"
    SKIP = "skip"
    ERROR = "error"


class ImportStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"
    VALIDATING = "validating"
    PROCESSING = "processing"


@dataclass
class ImportConfig:
    format: ImportFormat
    source: ImportSource
    mode: ImportMode
    delimiter: str = ","
    encoding: str = "utf-8"
    compression: Optional[str] = None
    skip_rows: int = 0
    header_row: int = 0
    columns: Optional[List[str]] = None
    column_mapping: Optional[Dict[str, str]] = None
    data_types: Optional[Dict[str, str]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    batch_size: int = 1000
    max_file_size: int = 1024 * 1024 * 100
    timeout: int = 300
    retry_count: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportResult:
    id: str
    name: str
    source: ImportSource
    format: ImportFormat
    status: ImportStatus
    total_rows: int = 0
    imported_rows: int = 0
    failed_rows: int = 0
    skipped_rows: int = 0
    total_size: int = 0
    duration: float = 0.0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    checksum: Optional[str] = None
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportBatch:
    id: str
    data: List[Dict[str, Any]]
    start_index: int
    end_index: int
    status: ImportStatus = ImportStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataImporter:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._imports: Dict[str, ImportResult] = {}
        self._batches: Dict[str, ImportBatch] = {}
        self._handlers: Dict[ImportFormat, Callable] = {}
        self._source_handlers: Dict[ImportSource, Callable] = {}
        self._validators: List[Callable] = []
        self._processors: List[Callable] = []
        self._observers: List[Callable] = []
        self._running = False
        self._temp_dir: Optional[str] = None
        
        self._initialize_handlers()
        self._initialize_source_handlers()

    def _initialize_handlers(self) -> None:
        self.register_handler(ImportFormat.CSV, self._import_csv)
        self.register_handler(ImportFormat.JSON, self._import_json)
        self.register_handler(ImportFormat.PARQUET, self._import_parquet)
        self.register_handler(ImportFormat.EXCEL, self._import_excel)
        self.register_handler(ImportFormat.XML, self._import_xml)
        self.register_handler(ImportFormat.SQL, self._import_sql)
        self.register_handler(ImportFormat.PICKLE, self._import_pickle)
        self.register_handler(ImportFormat.HDF5, self._import_hdf5)
        self.register_handler(ImportFormat.FEATHER, self._import_feather)
        self.register_handler(ImportFormat.ORC, self._import_orc)
        self.register_handler(ImportFormat.AVRO, self._import_avro)
        self.register_handler(ImportFormat.YAML, self._import_yaml)
        self.register_handler(ImportFormat.TEXT, self._import_text)
        self.register_handler(ImportFormat.BINARY, self._import_binary)

    def _initialize_source_handlers(self) -> None:
        self.register_source_handler(ImportSource.FILE, self._source_file)
        self.register_source_handler(ImportSource.URL, self._source_url)
        self.register_source_handler(ImportSource.API, self._source_api)
        self.register_source_handler(ImportSource.DATABASE, self._source_database)
        self.register_source_handler(ImportSource.S3, self._source_s3)
        self.register_source_handler(ImportSource.GCS, self._source_gcs)
        self.register_source_handler(ImportSource.AZURE, self._source_azure)
        self.register_source_handler(ImportSource.FTP, self._source_ftp)
        self.register_source_handler(ImportSource.SFTP, self._source_sftp)
        self.register_source_handler(ImportSource.MEMORY, self._source_memory)

    def register_handler(self, format_type: ImportFormat, handler: Callable) -> None:
        self._handlers[format_type] = handler

    def register_source_handler(self, source_type: ImportSource, handler: Callable) -> None:
        self._source_handlers[source_type] = handler

    def register_validator(self, validator: Callable) -> None:
        self._validators.append(validator)

    def register_processor(self, processor: Callable) -> None:
        self._processors.append(processor)

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def import_data(
        self,
        name: str,
        source: ImportSource,
        source_config: Dict[str, Any],
        format_type: ImportFormat,
        config: Optional[ImportConfig] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ImportResult:
        async with self._lock:
            import_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            result = ImportResult(
                id=import_id,
                name=name,
                source=source,
                format=format_type,
                status=ImportStatus.PENDING,
                metadata=metadata or {},
                created_at=time.time()
            )
            
            self._imports[import_id] = result
            
            try:
                result.status = ImportStatus.RUNNING
                await self._notify_observers("import_started", result)
                
                source_handler = self._source_handlers.get(source)
                if not source_handler:
                    raise ValueError(f"Unsupported source: {source}")
                
                raw_data = await source_handler(source_config, result)
                
                if format_type not in self._handlers:
                    raise ValueError(f"Unsupported format: {format_type}")
                
                handler = self._handlers[format_type]
                data = await handler(raw_data, config or ImportConfig(format=format_type, source=source, mode=ImportMode.OVERWRITE), result)
                
                for validator in self._validators:
                    data = await validator(data, result)
                
                for processor in self._processors:
                    data = await processor(data, result)
                
                result.imported_rows = len(data) if isinstance(data, list) else 0
                result.status = ImportStatus.COMPLETED
                result.completed_at = time.time()
                result.duration = result.completed_at - result.created_at
                
                await self._notify_observers("import_completed", result)
                
            except Exception as e:
                logger.error(f"Import failed: {e}")
                result.status = ImportStatus.FAILED
                result.errors.append({"error": str(e), "timestamp": time.time()})
                await self._notify_observers("import_failed", result)
            
            return result

    async def _source_file(self, config: Dict[str, Any], result: ImportResult) -> bytes:
        file_path = config.get("file_path")
        if not file_path or not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")
        
        with open(file_path, "rb") as f:
            data = f.read()
        
        result.total_size = len(data)
        result.checksum = hashlib.sha256(data).hexdigest()
        return data

    async def _source_url(self, config: Dict[str, Any], result: ImportResult) -> bytes:
        import aiohttp
        
        url = config.get("url")
        if not url:
            raise ValueError("URL not provided")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP error: {response.status}")
                data = await response.read()
        
        result.total_size = len(data)
        result.checksum = hashlib.sha256(data).hexdigest()
        return data

    async def _source_api(self, config: Dict[str, Any], result: ImportResult) -> bytes:
        import aiohttp
        
        endpoint = config.get("endpoint")
        method = config.get("method", "GET")
        headers = config.get("headers", {})
        params = config.get("params", {})
        body = config.get("body", {})
        
        if not endpoint:
            raise ValueError("API endpoint not provided")
        
        async with aiohttp.ClientSession() as session:
            if method.upper() == "GET":
                async with session.get(endpoint, headers=headers, params=params) as response:
                    if response.status != 200:
                        raise ValueError(f"API error: {response.status}")
                    data = await response.read()
            else:
                async with session.post(endpoint, headers=headers, json=body, params=params) as response:
                    if response.status != 200:
                        raise ValueError(f"API error: {response.status}")
                    data = await response.read()
        
        result.total_size = len(data)
        result.checksum = hashlib.sha256(data).hexdigest()
        return data

    async def _source_database(self, config: Dict[str, Any], result: ImportResult) -> bytes:
        import sqlalchemy
        
        connection_string = config.get("connection_string")
        query = config.get("query")
        
        if not connection_string or not query:
            raise ValueError("Connection string and query required")
        
        engine = sqlalchemy.create_engine(connection_string)
        df = pd.read_sql(query, engine)
        
        output = io.BytesIO()
        df.to_parquet(output)
        data = output.getvalue()
        
        result.total_size = len(data)
        result.checksum = hashlib.sha256(data).hexdigest()
        return data

    async def _source_s3(self, config: Dict[str, Any], result: ImportResult) -> bytes:
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 not installed")
        
        bucket = config.get("bucket")
        key = config.get("key")
        region = config.get("region", "us-east-1")
        
        if not bucket or not key:
            raise ValueError("Bucket and key required")
        
        s3 = boto3.client('s3', region_name=region)
        response = s3.get_object(Bucket=bucket, Key=key)
        data = response['Body'].read()
        
        result.total_size = len(data)
        result.checksum = hashlib.sha256(data).hexdigest()
        return data

    async def _source_gcs(self, config: Dict[str, Any], result: ImportResult) -> bytes:
        try:
            from google.cloud import storage
        except ImportError:
            raise ImportError("google-cloud-storage not installed")
        
        bucket_name = config.get("bucket")
        blob_name = config.get("blob")
        project = config.get("project")
        
        if not bucket_name or not blob_name:
            raise ValueError("Bucket and blob required")
        
        client = storage.Client(project=project)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        data = blob.download_as_bytes()
        
        result.total_size = len(data)
        result.checksum = hashlib.sha256(data).hexdigest()
        return data

    async def _source_azure(self, config: Dict[str, Any], result: ImportResult) -> bytes:
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError:
            raise ImportError("azure-storage-blob not installed")
        
        connection_string = config.get("connection_string")
        container = config.get("container")
        blob_name = config.get("blob")
        
        if not connection_string or not container or not blob_name:
            raise ValueError("Connection string, container, and blob required")
        
        client = BlobServiceClient.from_connection_string(connection_string)
        container_client = client.get_container_client(container)
        blob_client = container_client.get_blob_client(blob_name)
        data = blob_client.download_blob().readall()
        
        result.total_size = len(data)
        result.checksum = hashlib.sha256(data).hexdigest()
        return data

    async def _source_ftp(self, config: Dict[str, Any], result: ImportResult) -> bytes:
        try:
            import aioftp
        except ImportError:
            raise ImportError("aioftp not installed")
        
        host = config.get("host")
        username = config.get("username")
        password = config.get("password")
        path = config.get("path")
        
        if not host or not path:
            raise ValueError("Host and path required")
        
        async with aioftp.Client() as client:
            await client.connect(host)
            if username and password:
                await client.login(username, password)
            async with client.download_stream(path) as stream:
                data = await stream.read()
        
        result.total_size = len(data)
        result.checksum = hashlib.sha256(data).hexdigest()
        return data

    async def _source_sftp(self, config: Dict[str, Any], result: ImportResult) -> bytes:
        try:
            import asyncssh
        except ImportError:
            raise ImportError("asyncssh not installed")
        
        host = config.get("host")
        username = config.get("username")
        password = config.get("password")
        path = config.get("path")
        port = config.get("port", 22)
        
        if not host or not path:
            raise ValueError("Host and path required")
        
        async with asyncssh.connect(host, username=username, password=password, port=port) as conn:
            async with conn.open_sftp() as sftp:
                data = await sftp.read(path)
        
        result.total_size = len(data)
        result.checksum = hashlib.sha256(data).hexdigest()
        return data

    async def _source_memory(self, config: Dict[str, Any], result: ImportResult) -> bytes:
        data = config.get("data")
        if not data:
            raise ValueError("Data not provided")
        
        if isinstance(data, str):
            data = data.encode('utf-8')
        elif isinstance(data, dict):
            data = json.dumps(data).encode('utf-8')
        
        result.total_size = len(data)
        result.checksum = hashlib.sha256(data).hexdigest()
        return data

    async def _import_csv(self, data: bytes, config: ImportConfig, result: ImportResult) -> List[Dict]:
        text = data.decode(config.encoding)
        csv_reader = csv.DictReader(
            io.StringIO(text),
            delimiter=config.delimiter,
            skipinitialspace=True
        )
        
        if config.skip_rows:
            for _ in range(config.skip_rows):
                next(csv_reader, None)
        
        rows = []
        for row in csv_reader:
            if config.columns and config.column_mapping:
                mapped_row = {}
                for col in config.columns:
                    if col in row:
                        mapped_row[config.column_mapping.get(col, col)] = row[col]
                rows.append(mapped_row)
            else:
                rows.append(row)
        
        return rows

    async def _import_json(self, data: bytes, config: ImportConfig, result: ImportResult) -> List[Dict]:
        text = data.decode(config.encoding)
        json_data = json.loads(text)
        
        if isinstance(json_data, dict):
            json_data = [json_data]
        elif isinstance(json_data, list):
            pass
        else:
            raise ValueError("Invalid JSON format")
        
        return json_data

    async def _import_parquet(self, data: bytes, config: ImportConfig, result: ImportResult) -> List[Dict]:
        import pyarrow.parquet as pq
        import pyarrow as pa
        
        buffer = io.BytesIO(data)
        table = pq.read_table(buffer)
        df = table.to_pandas()
        
        return df.to_dict('records')

    async def _import_excel(self, data: bytes, config: ImportConfig, result: ImportResult) -> List[Dict]:
        excel_data = pd.read_excel(io.BytesIO(data))
        return excel_data.to_dict('records')

    async def _import_xml(self, data: bytes, config: ImportConfig, result: ImportResult) -> List[Dict]:
        import xml.etree.ElementTree as ET
        
        text = data.decode(config.encoding)
        root = ET.fromstring(text)
        
        rows = []
        for child in root:
            row = {}
            for elem in child:
                row[elem.tag] = elem.text
            rows.append(row)
        
        return rows

    async def _import_sql(self, data: bytes, config: ImportConfig, result: ImportResult) -> List[Dict]:
        import sqlite3
        
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.write(data)
        temp_db.close()
        
        conn = sqlite3.connect(temp_db.name)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        all_rows = []
        for table in tables:
            cursor.execute(f"SELECT * FROM {table[0]}")
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            for row in rows:
                row_dict = {columns[i]: row[i] for i in range(len(columns))}
                all_rows.append(row_dict)
        
        conn.close()
        os.unlink(temp_db.name)
        
        return all_rows

    async def _import_pickle(self, data: bytes, config: ImportConfig, result: ImportResult) -> List[Dict]:
        import pickle
        
        obj = pickle.loads(data)
        
        if isinstance(obj, list):
            return obj
        elif isinstance(obj, dict):
            return [obj]
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict('records')
        else:
            raise ValueError(f"Unsupported pickle type: {type(obj)}")

    async def _import_hdf5(self, data: bytes, config: ImportConfig, result: ImportResult) -> List[Dict]:
        import h5py
        import numpy as np
        
        buffer = io.BytesIO(data)
        h5 = h5py.File(buffer, 'r')
        
        rows = []
        for key in h5.keys():
            dataset = h5[key]
            if isinstance(dataset, h5py.Dataset):
                arr = dataset[()]
                if isinstance(arr, np.ndarray):
                    if arr.dtype.names:
                        for i in range(len(arr)):
                            row = {name: arr[name][i] for name in arr.dtype.names}
                            rows.append(row)
                    else:
                        for i in range(len(arr)):
                            rows.append({key: arr[i].tolist()})
        
        return rows

    async def _import_feather(self, data: bytes, config: ImportConfig, result: ImportResult) -> List[Dict]:
        import pyarrow.feather as feather
        
        buffer = io.BytesIO(data)
        df = feather.read_feather(buffer)
        return df.to_dict('records')

    async def _import_orc(self, data: bytes, config: ImportConfig, result: ImportResult) -> List[Dict]:
        import pyarrow.orc as orc
        
        buffer = io.BytesIO(data)
        table = orc.read_table(buffer)
        df = table.to_pandas()
        return df.to_dict('records')

    async def _import_avro(self, data: bytes, config: ImportConfig, result: ImportResult) -> List[Dict]:
        try:
            import avro.io
            import avro.schema
        except ImportError:
            raise ImportError("avro not installed")
        
        buffer = io.BytesIO(data)
        reader = avro.io.DatumReader()
        decoder = avro.io.BinaryDecoder(buffer)
        
        rows = []
        while True:
            try:
                row = reader.read(decoder)
                rows.append(row)
            except:
                break
        
        return rows

    async def _import_yaml(self, data: bytes, config: ImportConfig, result: ImportResult) -> List[Dict]:
        import yaml
        
        text = data.decode(config.encoding)
        yaml_data = yaml.safe_load(text)
        
        if isinstance(yaml_data, list):
            return yaml_data
        elif isinstance(yaml_data, dict):
            return [yaml_data]
        else:
            raise ValueError("Invalid YAML format")

    async def _import_text(self, data: bytes, config: ImportConfig, result: ImportResult) -> List[Dict]:
        text = data.decode(config.encoding)
        lines = text.splitlines()
        
        rows = []
        for i, line in enumerate(lines):
            if i >= config.skip_rows:
                rows.append({"line": i + 1, "text": line})
        
        return rows

    async def _import_binary(self, data: bytes, config: ImportConfig, result: ImportResult) -> List[Dict]:
        return [{"data": data.hex()}]

    async def get_import(self, import_id: str) -> Optional[ImportResult]:
        return self._imports.get(import_id)

    async def get_imports(
        self,
        status: Optional[ImportStatus] = None,
        source: Optional[ImportSource] = None,
        limit: int = 100
    ) -> List[ImportResult]:
        imports = list(self._imports.values())
        
        if status:
            imports = [i for i in imports if i.status == status]
        
        if source:
            imports = [i for i in imports if i.source == source]
        
        imports.sort(key=lambda x: x.created_at, reverse=True)
        return imports[:limit]

    async def cancel_import(self, import_id: str) -> bool:
        if import_id not in self._imports:
            return False
        
        result = self._imports[import_id]
        if result.status in [ImportStatus.COMPLETED, ImportStatus.FAILED]:
            return False
        
        result.status = ImportStatus.CANCELLED
        await self._notify_observers("import_cancelled", result)
        return True

    async def delete_import(self, import_id: str) -> bool:
        if import_id in self._imports:
            del self._imports[import_id]
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
        total = len(self._imports)
        completed = len([i for i in self._imports.values() if i.status == ImportStatus.COMPLETED])
        failed = len([i for i in self._imports.values() if i.status == ImportStatus.FAILED])
        running = len([i for i in self._imports.values() if i.status == ImportStatus.RUNNING])
        
        total_rows = sum(i.imported_rows for i in self._imports.values())
        total_size = sum(i.total_size for i in self._imports.values())
        
        return {
            "total_imports": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "total_rows": total_rows,
            "total_size": total_size,
            "formats": len(self._handlers),
            "sources": len(self._source_handlers),
            "validators": len(self._validators),
            "processors": len(self._processors),
            "running": self._running
        }


__all__ = [
    "ImportFormat",
    "ImportSource",
    "ImportMode",
    "ImportStatus",
    "ImportConfig",
    "ImportResult",
    "ImportBatch",
    "DataImporter"
]
