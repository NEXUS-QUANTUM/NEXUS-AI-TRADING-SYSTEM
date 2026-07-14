"""
NEXUS AI TRADING SYSTEM - Weaviate Client Module
Copyright © 2026 NEXUS QUANTUM LTD

This module implements a Weaviate client for the NEXUS AI Trading System including:
- Weaviate connection management
- Schema creation and management
- Class (collection) management
- Vector storage and retrieval
- Metadata filtering and querying
- Similarity search with multiple metrics
- Batch operations for efficient processing
- GraphQL query support
- Near-text and near-vector search
- Hybrid search
- Cross-reference support
- Property indexing
- Vector indexing configuration
- Backup and recovery
- Statistics and monitoring
- Multi-tenancy support
- Replication configuration
- Module integration (text2vec, multi2vec, etc.)
- Export and import
- Schema migration
- Version management
"""

import os
import sys
import json
import time
import logging
import hashlib
import pickle
from typing import Dict, List, Optional, Tuple, Any, Union, Set, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
import numpy as np
import weaviate
from weaviate import Client, AuthClientPassword, AuthClientCredentials
from weaviate import Config
from weaviate.data import (
    DataObject,
    Batch,
    Reference,
    ConsistencyLevel,
)
from weaviate.gql import (
    get,
    GraphQL,
)
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/weaviate_client.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class Vectorizer(Enum):
    """Vectorizer modules for Weaviate."""
    TEXT2VEC = "text2vec-openai"
    MULTI2VEC = "multi2vec-clip"
    TEXT2VEC_HUGGINGFACE = "text2vec-huggingface"
    TEXT2VEC_TRANSFORMERS = "text2vec-transformers"
    NONE = "none"


class DistanceMetric(Enum):
    """Distance metrics for Weaviate."""
    COSINE = "cosine"
    L2 = "l2"
    DOT = "dot"
    HAMMING = "hamming"


class ConsistencyLevel(Enum):
    """Consistency levels for Weaviate."""
    ALL = "ALL"
    QUORUM = "QUORUM"
    ONE = "ONE"


@dataclass
class WeaviateConfig:
    """Configuration for Weaviate client."""
    url: str
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    additional_headers: Optional[Dict[str, str]] = None
    timeout: int = 30
    batch_size: int = 100
    consistency_level: ConsistencyLevel = ConsistencyLevel.QUORUM
    vectorizer: Vectorizer = Vectorizer.TEXT2VEC
    distance_metric: DistanceMetric = DistanceMetric.COSINE
    replication_factor: int = 1
    multi_tenancy: bool = False
    use_ssl: bool = True


@dataclass
class WeaviateClass:
    """Weaviate class (collection) definition."""
    class_name: str
    vectorizer: Vectorizer
    distance_metric: DistanceMetric
    properties: List[Dict[str, Any]]
    vector_index_config: Optional[Dict[str, Any]] = None
    replication_config: Optional[Dict[str, Any]] = None
    sharding_config: Optional[Dict[str, Any]] = None
    multi_tenancy_config: Optional[Dict[str, Any]] = None
    inverted_index_config: Optional[Dict[str, Any]] = None
    module_config: Optional[Dict[str, Any]] = None


@dataclass
class WeaviateObject:
    """Weaviate data object."""
    class_name: str
    properties: Dict[str, Any]
    vector: Optional[List[float]] = None
    id: Optional[str] = None
    consistency_level: Optional[ConsistencyLevel] = None


@dataclass
class WeaviateQueryResult:
    """Result from a Weaviate query."""
    id: str
    class_name: str
    properties: Dict[str, Any]
    vector: Optional[List[float]] = None
    distance: Optional[float] = None
    _additional: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WeaviateStats:
    """Statistics for Weaviate."""
    total_objects: int
    total_classes: int
    schema_version: int
    vectorizer: str
    distance_metric: str
    replication_factor: int
    multi_tenancy: bool
    memory_usage: int
    objects_by_class: Dict[str, int]
    timestamp: float


# ============================================
# Weaviate Client Implementation
# ============================================

class WeaviateClient:
    """
    Weaviate client for the NEXUS AI Trading System.
    
    This class provides a high-level interface to Weaviate for vector storage
    and retrieval with support for multiple classes, schemas, and advanced features.
    """
    
    def __init__(self, config: WeaviateConfig):
        """
        Initialize the Weaviate client.
        
        Args:
            config: Weaviate configuration
        """
        self.config = config
        self.client = None
        self.classes = {}
        self.schema = None
        
        # Initialize client
        self._init_client()
        
        # Load schema
        self._load_schema()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"WeaviateClient initialized with URL: {config.url}")
        self.logger.info(f"Vectorizer: {config.vectorizer.value}")
        self.logger.info(f"Distance Metric: {config.distance_metric.value}")
    
    # ============================================
    # Client Initialization
    # ============================================
    
    def _init_client(self) -> None:
        """Initialize the Weaviate client."""
        try:
            auth_config = self._get_auth_config()
            
            self.client = Client(
                url=self.config.url,
                auth_client_secret=auth_config,
                timeout_config=(self.config.timeout, self.config.timeout * 2),
                additional_headers=self.config.additional_headers,
            )
            
            # Test connection
            self.client.is_ready()
            self.logger.info("Connected to Weaviate")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Weaviate client: {e}")
            raise
    
    def _get_auth_config(self) -> Optional[Any]:
        """Get authentication configuration."""
        if self.config.api_key:
            return AuthClientCredentials(
                client_secret=self.config.api_key
            )
        elif self.config.username and self.config.password:
            return AuthClientPassword(
                username=self.config.username,
                password=self.config.password
            )
        return None
    
    def _load_schema(self) -> None:
        """Load schema from Weaviate."""
        try:
            self.schema = self.client.schema.get()
            
            if self.schema and 'classes' in self.schema:
                for class_info in self.schema['classes']:
                    class_name = class_info['class']
                    self.classes[class_name] = class_info
            
            self.logger.info(f"Loaded schema with {len(self.classes)} classes")
            
        except Exception as e:
            self.logger.warning(f"Failed to load schema: {e}")
            self.schema = {'classes': []}
    
    # ============================================
    # Class (Collection) Management
    # ============================================
    
    def create_class(self, class_config: WeaviateClass) -> bool:
        """
        Create a class in Weaviate.
        
        Args:
            class_config: Class configuration
            
        Returns:
            True if created
        """
        class_name = class_config.class_name
        
        if class_name in self.classes:
            self.logger.warning(f"Class {class_name} already exists")
            return False
        
        try:
            # Build class schema
            class_schema = {
                'class': class_name,
                'description': class_config.properties,
                'vectorizer': class_config.vectorizer.value,
                'vectorIndexConfig': class_config.vector_index_config or {
                    'distance': class_config.distance_metric.value,
                    'skip': False,
                },
                'properties': class_config.properties,
                'replicationConfig': class_config.replication_config or {
                    'factor': self.config.replication_factor,
                },
                'shardingConfig': class_config.sharding_config or {
                    'desiredCount': 1,
                },
                'multiTenancyConfig': class_config.multi_tenancy_config or {
                    'enabled': self.config.multi_tenancy,
                },
                'invertedIndexConfig': class_config.inverted_index_config or {
                    'stopwords': {
                        'preset': 'en',
                    },
                },
            }
            
            if class_config.module_config:
                class_schema['moduleConfig'] = class_config.module_config
            
            # Create class
            self.client.schema.create_class(class_schema)
            
            # Update cache
            self.classes[class_name] = class_schema
            self._load_schema()
            
            self.logger.info(f"Created class: {class_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create class {class_name}: {e}")
            return False
    
    def delete_class(self, class_name: str) -> bool:
        """
        Delete a class from Weaviate.
        
        Args:
            class_name: Class name
            
        Returns:
            True if deleted
        """
        if class_name not in self.classes:
            return False
        
        try:
            self.client.schema.delete_class(class_name)
            del self.classes[class_name]
            self._load_schema()
            self.logger.info(f"Deleted class: {class_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete class {class_name}: {e}")
            return False
    
    def get_class(self, class_name: str) -> Optional[Dict[str, Any]]:
        """
        Get class schema.
        
        Args:
            class_name: Class name
            
        Returns:
            Class schema or None
        """
        return self.classes.get(class_name)
    
    def list_classes(self) -> List[str]:
        """
        List all classes.
        
        Returns:
            List of class names
        """
        return list(self.classes.keys())
    
    # ============================================
    # Data Object Management
    # ============================================
    
    def create_object(self, weaviate_object: WeaviateObject) -> Optional[str]:
        """
        Create a data object in Weaviate.
        
        Args:
            weaviate_object: Weaviate object
            
        Returns:
            Object ID or None
        """
        try:
            # Prepare data
            data = {
                'class': weaviate_object.class_name,
                'properties': weaviate_object.properties,
            }
            
            if weaviate_object.id:
                data['id'] = weaviate_object.id
            
            if weaviate_object.vector:
                data['vector'] = weaviate_object.vector
            
            # Create object
            result = self.client.data_object.create(
                data['properties'],
                data['class'],
                data.get('id'),
                data.get('vector'),
                consistency_level=weaviate_object.consistency_level.value if weaviate_object.consistency_level else None,
            )
            
            self.logger.info(f"Created object in {weaviate_object.class_name}: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to create object: {e}")
            return None
    
    def get_object(
        self,
        class_name: str,
        object_id: str,
        include_vector: bool = False,
    ) -> Optional[WeaviateQueryResult]:
        """
        Get a data object from Weaviate.
        
        Args:
            class_name: Class name
            object_id: Object ID
            include_vector: Whether to include vector
            
        Returns:
            Weaviate object or None
        """
        try:
            result = self.client.data_object.get(
                object_id,
                class_name,
                include_vector=include_vector,
            )
            
            if result:
                return WeaviateQueryResult(
                    id=result.get('id'),
                    class_name=result.get('class'),
                    properties=result.get('properties', {}),
                    vector=result.get('vector'),
                    _additional=result.get('_additional', {}),
                )
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get object {object_id}: {e}")
            return None
    
    def update_object(self, weaviate_object: WeaviateObject) -> bool:
        """
        Update a data object in Weaviate.
        
        Args:
            weaviate_object: Weaviate object
            
        Returns:
            True if updated
        """
        if not weaviate_object.id:
            self.logger.warning("Object ID required for update")
            return False
        
        try:
            self.client.data_object.update(
                weaviate_object.properties,
                weaviate_object.class_name,
                weaviate_object.id,
                weaviate_object.vector,
            )
            
            self.logger.info(f"Updated object {weaviate_object.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update object {weaviate_object.id}: {e}")
            return False
    
    def delete_object(self, class_name: str, object_id: str) -> bool:
        """
        Delete a data object from Weaviate.
        
        Args:
            class_name: Class name
            object_id: Object ID
            
        Returns:
            True if deleted
        """
        try:
            self.client.data_object.delete(
                object_id,
                class_name,
            )
            self.logger.info(f"Deleted object {object_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete object {object_id}: {e}")
            return False
    
    # ============================================
    # Batch Operations
    # ============================================
    
    def batch_create_objects(
        self,
        objects: List[WeaviateObject],
        batch_size: Optional[int] = None,
    ) -> List[str]:
        """
        Batch create data objects in Weaviate.
        
        Args:
            objects: List of Weaviate objects
            batch_size: Batch size
            
        Returns:
            List of object IDs
        """
        batch_size = batch_size or self.config.batch_size
        object_ids = []
        
        with self.client.batch(
            batch_size=batch_size,
            consistency_level=self.config.consistency_level.value,
        ) as batch:
            for obj in objects:
                try:
                    result = batch.add_data_object(
                        obj.properties,
                        obj.class_name,
                        obj.id,
                        obj.vector,
                    )
                    object_ids.append(result)
                except Exception as e:
                    self.logger.error(f"Failed to add object to batch: {e}")
        
        self.logger.info(f"Batch created {len(object_ids)} objects")
        return object_ids
    
    def batch_delete_objects(
        self,
        class_name: str,
        where: Dict[str, Any],
        batch_size: Optional[int] = None,
    ) -> int:
        """
        Batch delete objects from Weaviate.
        
        Args:
            class_name: Class name
            where: Filter conditions
            batch_size: Batch size
            
        Returns:
            Number of objects deleted
        """
        batch_size = batch_size or self.config.batch_size
        deleted_count = 0
        
        try:
            # Get objects to delete
            result = self.client.data_object.get(
                class_name=class_name,
                where=where,
                limit=batch_size,
            )
            
            while result and result.get('objects'):
                for obj in result['objects']:
                    self.delete_object(class_name, obj['id'])
                    deleted_count += 1
                
                # Get next batch
                result = self.client.data_object.get(
                    class_name=class_name,
                    where=where,
                    limit=batch_size,
                    after=result['objects'][-1]['id'],
                )
            
            self.logger.info(f"Batch deleted {deleted_count} objects")
            
        except Exception as e:
            self.logger.error(f"Failed to batch delete objects: {e}")
        
        return deleted_count
    
    # ============================================
    # Search Operations
    # ============================================
    
    def near_vector_search(
        self,
        class_name: str,
        vector: List[float],
        limit: int = 10,
        distance: Optional[float] = None,
        where: Optional[Dict[str, Any]] = None,
        additional_fields: Optional[List[str]] = None,
        properties: Optional[List[str]] = None,
        certainty: Optional[float] = None,
        include_vector: bool = False,
    ) -> List[WeaviateQueryResult]:
        """
        Search by vector similarity.
        
        Args:
            class_name: Class name
            vector: Query vector
            limit: Number of results
            distance: Maximum distance
            where: Filter conditions
            additional_fields: Additional fields to include
            properties: Properties to return
            certainty: Minimum certainty
            include_vector: Whether to include vector
            
        Returns:
            List of query results
        """
        try:
            result = self.client.query.get(
                class_name,
                properties or [],
            ).with_near_vector({
                'vector': vector,
                'distance': distance,
                'certainty': certainty,
            }).with_limit(limit)
            
            if where:
                result = result.with_where(where)
            
            if additional_fields:
                result = result.with_additional(additional_fields)
            
            if include_vector:
                result = result.with_additional(['vector'])
            
            result = result.do()
            
            return self._parse_query_result(result, class_name)
            
        except Exception as e:
            self.logger.error(f"Failed to perform vector search: {e}")
            return []
    
    def near_text_search(
        self,
        class_name: str,
        text: str,
        limit: int = 10,
        distance: Optional[float] = None,
        where: Optional[Dict[str, Any]] = None,
        additional_fields: Optional[List[str]] = None,
        properties: Optional[List[str]] = None,
        certainty: Optional[float] = None,
        include_vector: bool = False,
    ) -> List[WeaviateQueryResult]:
        """
        Search by text similarity.
        
        Args:
            class_name: Class name
            text: Query text
            limit: Number of results
            distance: Maximum distance
            where: Filter conditions
            additional_fields: Additional fields to include
            properties: Properties to return
            certainty: Minimum certainty
            include_vector: Whether to include vector
            
        Returns:
            List of query results
        """
        try:
            result = self.client.query.get(
                class_name,
                properties or [],
            ).with_near_text({
                'concepts': [text],
                'distance': distance,
                'certainty': certainty,
            }).with_limit(limit)
            
            if where:
                result = result.with_where(where)
            
            if additional_fields:
                result = result.with_additional(additional_fields)
            
            if include_vector:
                result = result.with_additional(['vector'])
            
            result = result.do()
            
            return self._parse_query_result(result, class_name)
            
        except Exception as e:
            self.logger.error(f"Failed to perform text search: {e}")
            return []
    
    def hybrid_search(
        self,
        class_name: str,
        query: str,
        vector: Optional[List[float]] = None,
        limit: int = 10,
        alpha: float = 0.5,
        where: Optional[Dict[str, Any]] = None,
        additional_fields: Optional[List[str]] = None,
        properties: Optional[List[str]] = None,
        include_vector: bool = False,
    ) -> List[WeaviateQueryResult]:
        """
        Perform hybrid search (text + vector).
        
        Args:
            class_name: Class name
            query: Text query
            vector: Vector query
            limit: Number of results
            alpha: Balance between text and vector (0 = pure vector, 1 = pure text)
            where: Filter conditions
            additional_fields: Additional fields to include
            properties: Properties to return
            include_vector: Whether to include vector
            
        Returns:
            List of query results
        """
        try:
            result = self.client.query.get(
                class_name,
                properties or [],
            ).with_hybrid({
                'query': query,
                'alpha': alpha,
                'vector': vector,
            }).with_limit(limit)
            
            if where:
                result = result.with_where(where)
            
            if additional_fields:
                result = result.with_additional(additional_fields)
            
            if include_vector:
                result = result.with_additional(['vector'])
            
            result = result.do()
            
            return self._parse_query_result(result, class_name)
            
        except Exception as e:
            self.logger.error(f"Failed to perform hybrid search: {e}")
            return []
    
    def bm25_search(
        self,
        class_name: str,
        query: str,
        limit: int = 10,
        where: Optional[Dict[str, Any]] = None,
        additional_fields: Optional[List[str]] = None,
        properties: Optional[List[str]] = None,
        include_vector: bool = False,
    ) -> List[WeaviateQueryResult]:
        """
        Perform BM25 keyword search.
        
        Args:
            class_name: Class name
            query: Query text
            limit: Number of results
            where: Filter conditions
            additional_fields: Additional fields to include
            properties: Properties to return
            include_vector: Whether to include vector
            
        Returns:
            List of query results
        """
        try:
            result = self.client.query.get(
                class_name,
                properties or [],
            ).with_bm25({
                'query': query,
            }).with_limit(limit)
            
            if where:
                result = result.with_where(where)
            
            if additional_fields:
                result = result.with_additional(additional_fields)
            
            if include_vector:
                result = result.with_additional(['vector'])
            
            result = result.do()
            
            return self._parse_query_result(result, class_name)
            
        except Exception as e:
            self.logger.error(f"Failed to perform BM25 search: {e}")
            return []
    
    def _parse_query_result(
        self,
        result: Dict[str, Any],
        class_name: str,
    ) -> List[WeaviateQueryResult]:
        """
        Parse query result.
        
        Args:
            result: Raw query result
            class_name: Class name
            
        Returns:
            Parsed query results
        """
        results = []
        
        if result and 'data' in result and 'Get' in result['data']:
            data = result['data']['Get']
            if class_name in data:
                for item in data[class_name]:
                    # Extract properties
                    properties = {}
                    for key, value in item.items():
                        if not key.startswith('_'):
                            properties[key] = value
                    
                    # Extract additional fields
                    additional = {}
                    for key, value in item.items():
                        if key.startswith('_'):
                            additional[key] = value
                    
                    results.append(WeaviateQueryResult(
                        id=item.get('_additional', {}).get('id', ''),
                        class_name=class_name,
                        properties=properties,
                        vector=additional.get('vector'),
                        distance=additional.get('distance'),
                        _additional=additional,
                    ))
        
        return results
    
    # ============================================
    # Cross-Reference Operations
    # ============================================
    
    def create_reference(
        self,
        from_class: str,
        from_id: str,
        from_property: str,
        to_class: str,
        to_id: str,
    ) -> bool:
        """
        Create a cross-reference between objects.
        
        Args:
            from_class: Source class
            from_id: Source object ID
            from_property: Source property
            to_class: Target class
            to_id: Target object ID
            
        Returns:
            True if created
        """
        try:
            self.client.data_object.reference.add(
                from_class,
                from_id,
                from_property,
                to_class,
                to_id,
            )
            self.logger.info(f"Created reference: {from_id} -> {to_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create reference: {e}")
            return False
    
    def delete_reference(
        self,
        from_class: str,
        from_id: str,
        from_property: str,
        to_class: str,
        to_id: str,
    ) -> bool:
        """
        Delete a cross-reference.
        
        Args:
            from_class: Source class
            from_id: Source object ID
            from_property: Source property
            to_class: Target class
            to_id: Target object ID
            
        Returns:
            True if deleted
        """
        try:
            self.client.data_object.reference.delete(
                from_class,
                from_id,
                from_property,
                to_class,
                to_id,
            )
            self.logger.info(f"Deleted reference: {from_id} -> {to_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete reference: {e}")
            return False
    
    # ============================================
    # Backup and Recovery
    # ============================================
    
    def create_backup(self, backup_id: str, class_names: Optional[List[str]] = None) -> bool:
        """
        Create a backup of classes.
        
        Args:
            backup_id: Backup identifier
            class_names: Classes to backup (all if None)
            
        Returns:
            True if created
        """
        try:
            result = self.client.backup.create(
                backup_id=backup_id,
                class_names=class_names,
            )
            
            # Wait for completion
            while True:
                status = self.client.backup.get_create_status(backup_id)
                if status.get('status') == 'SUCCESS':
                    self.logger.info(f"Backup {backup_id} created")
                    return True
                elif status.get('status') == 'FAILED':
                    self.logger.error(f"Backup {backup_id} failed: {status.get('error')}")
                    return False
                time.sleep(2)
                
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return False
    
    def restore_backup(self, backup_id: str, class_names: Optional[List[str]] = None) -> bool:
        """
        Restore from a backup.
        
        Args:
            backup_id: Backup identifier
            class_names: Classes to restore (all if None)
            
        Returns:
            True if restored
        """
        try:
            result = self.client.backup.restore(
                backup_id=backup_id,
                class_names=class_names,
            )
            
            # Wait for completion
            while True:
                status = self.client.backup.get_restore_status(backup_id)
                if status.get('status') == 'SUCCESS':
                    self.logger.info(f"Backup {backup_id} restored")
                    self._load_schema()
                    return True
                elif status.get('status') == 'FAILED':
                    self.logger.error(f"Backup {backup_id} restore failed: {status.get('error')}")
                    return False
                time.sleep(2)
                
        except Exception as e:
            self.logger.error(f"Failed to restore backup: {e}")
            return False
    
    # ============================================
    # Export and Import
    # ============================================
    
    def export_class(
        self,
        class_name: str,
        file_path: Optional[Union[str, Path]] = None,
        include_vectors: bool = True,
    ) -> Dict[str, Any]:
        """
        Export a class to a file.
        
        Args:
            class_name: Class name
            file_path: Output file path
            include_vectors: Whether to include vectors
            
        Returns:
            Exported data
        """
        # Get all objects
        objects = []
        cursor = None
        
        while True:
            result = self.client.data_object.get(
                class_name=class_name,
                limit=1000,
                after=cursor,
                include_vector=include_vectors,
            )
            
            if not result or not result.get('objects'):
                break
            
            for obj in result['objects']:
                objects.append({
                    'id': obj['id'],
                    'properties': obj['properties'],
                    'vector': obj.get('vector'),
                })
            
            if len(result['objects']) < 1000:
                break
            cursor = result['objects'][-1]['id']
        
        export_data = {
            'class_name': class_name,
            'schema': self.get_class(class_name),
            'objects': objects,
            'timestamp': time.time(),
            'version': '1.0',
        }
        
        if file_path:
            file_path = Path(file_path)
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            self.logger.info(f"Exported class {class_name} to {file_path}")
        
        return export_data
    
    def import_class(
        self,
        file_path: Union[str, Path],
        class_name: Optional[str] = None,
        overwrite: bool = False,
    ) -> int:
        """
        Import a class from a file.
        
        Args:
            file_path: Input file path
            class_name: Class name (override)
            overwrite: Whether to overwrite existing objects
            
        Returns:
            Number of objects imported
        """
        file_path = Path(file_path)
        
        with open(file_path, 'r') as f:
            import_data = json.load(f)
        
        target_class = class_name or import_data.get('class_name')
        
        if not target_class:
            raise ValueError("Class name not specified")
        
        # Create class if not exists
        if target_class not in self.classes:
            schema = import_data.get('schema')
            if schema:
                class_config = WeaviateClass(
                    class_name=target_class,
                    vectorizer=Vectorizer(schema.get('vectorizer', 'none')),
                    distance_metric=DistanceMetric(
                        schema.get('vectorIndexConfig', {}).get('distance', 'cosine')
                    ),
                    properties=schema.get('properties', []),
                    vector_index_config=schema.get('vectorIndexConfig'),
                    replication_config=schema.get('replicationConfig'),
                    sharding_config=schema.get('shardingConfig'),
                    multi_tenancy_config=schema.get('multiTenancyConfig'),
                    inverted_index_config=schema.get('invertedIndexConfig'),
                    module_config=schema.get('moduleConfig'),
                )
                self.create_class(class_config)
        
        # Import objects
        objects = import_data.get('objects', [])
        imported_count = 0
        
        for obj_data in objects:
            weaviate_obj = WeaviateObject(
                class_name=target_class,
                properties=obj_data['properties'],
                vector=obj_data.get('vector'),
                id=obj_data.get('id'),
            )
            
            if overwrite and obj_data.get('id'):
                # Update existing object
                self.update_object(weaviate_obj)
            else:
                # Create new object
                self.create_object(weaviate_obj)
            
            imported_count += 1
        
        self.logger.info(f"Imported {imported_count} objects to {target_class}")
        return imported_count
    
    # ============================================
    # Monitoring and Statistics
    # ============================================
    
    def get_stats(self) -> WeaviateStats:
        """
        Get Weaviate statistics.
        
        Returns:
            Weaviate statistics
        """
        total_objects = 0
        objects_by_class = {}
        
        for class_name in self.classes:
            try:
                result = self.client.data_object.get(
                    class_name=class_name,
                    limit=1,
                )
                count = result.get('totalResults', 0) if result else 0
                objects_by_class[class_name] = count
                total_objects += count
            except:
                objects_by_class[class_name] = 0
        
        return WeaviateStats(
            total_objects=total_objects,
            total_classes=len(self.classes),
            schema_version=self.schema.get('version', 0) if self.schema else 0,
            vectorizer=self.config.vectorizer.value,
            distance_metric=self.config.distance_metric.value,
            replication_factor=self.config.replication_factor,
            multi_tenancy=self.config.multi_tenancy,
            memory_usage=self._estimate_memory_usage(),
            objects_by_class=objects_by_class,
            timestamp=time.time(),
        )
    
    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage."""
        # This is a rough estimate
        return len(self.classes) * 1024 * 1024  # 1MB per class
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Health check results
        """
        try:
            is_ready = self.client.is_ready()
            
            return {
                'status': 'healthy' if is_ready else 'degraded',
                'timestamp': time.time(),
                'is_ready': is_ready,
                'schema_version': self.schema.get('version', 0) if self.schema else 0,
                'total_classes': len(self.classes),
                'vectorizer': self.config.vectorizer.value,
                'distance_metric': self.config.distance_metric.value,
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'timestamp': time.time(),
                'error': str(e),
            }
    
    # ============================================
    # Schema Management
    # ============================================
    
    def update_schema(self) -> None:
        """Update schema cache."""
        self._load_schema()
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get full schema.
        
        Returns:
            Schema dictionary
        """
        return self.schema
    
    # ============================================
    # Shutdown
    # ============================================
    
    def shutdown(self) -> None:
        """Shutdown the Weaviate client."""
        try:
            self.logger.info("Shutting down WeaviateClient")
        except Exception as e:
            self.logger.error(f"Shutdown error: {e}")


# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point for CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Weaviate Client CLI')
    parser.add_argument('--command', choices=['list', 'stats', 'create', 'delete', 'search', 'backup', 'restore'],
                       required=True, help='Command to execute')
    parser.add_argument('--url', type=str, default='http://localhost:8080', help='Weaviate URL')
    parser.add_argument('--api-key', type=str, help='API key')
    parser.add_argument('--class-name', type=str, help='Class name')
    parser.add_argument('--vectorizer', type=str, default='none', help='Vectorizer')
    parser.add_argument('--metric', type=str, default='cosine', help='Distance metric')
    parser.add_argument('--file', type=str, help='File for import/export')
    parser.add_argument('--query', type=str, help='Query text')
    parser.add_argument('--vector', type=str, help='Query vector (comma-separated)')
    parser.add_argument('--limit', type=int, default=10, help='Number of results')
    parser.add_argument('--alpha', type=float, default=0.5, help='Hybrid search alpha')
    
    args = parser.parse_args()
    
    # Create configuration
    config = WeaviateConfig(
        url=args.url,
        api_key=args.api_key,
        vectorizer=Vectorizer(args.vectorizer),
        distance_metric=DistanceMetric(args.metric),
    )
    
    # Initialize client
    client = WeaviateClient(config)
    
    if args.command == 'list':
        classes = client.list_classes()
        print("Classes:")
        for name in classes:
            print(f"  {name}")
    
    elif args.command == 'stats':
        stats = client.get_stats()
        print(f"\nWeaviate Statistics:")
        print(f"  Total Objects: {stats.total_objects}")
        print(f"  Total Classes: {stats.total_classes}")
       
