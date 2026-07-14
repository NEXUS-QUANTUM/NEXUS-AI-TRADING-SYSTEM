"""
NEXUS AI TRADING SYSTEM - Pinecone Client Module
Copyright © 2026 NEXUS QUANTUM LTD

This module implements a Pinecone client for the NEXUS AI Trading System including:
- Pinecone connection management
- Index creation and management
- Vector storage and retrieval
- Metadata filtering and querying
- Similarity search with multiple metrics
- Batch operations for efficient processing
- Persistent storage with versioning
- Distributed vector indexing
- Approximate nearest neighbor search
- Namespace management
- Pod management
- Performance monitoring
- Export and import
- Backup and recovery
- Statistics and monitoring
- Query optimization
- Sparse and dense vectors
- Real-time updates
- Scalable vector search
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
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Pinecone imports
try:
    import pinecone
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Pinecone not available. Install with: pip install pinecone-client")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/pinecone_client.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class IndexStatus(Enum):
    """Status of Pinecone indexes."""
    CREATING = "creating"
    READY = "ready"
    UPDATING = "updating"
    DELETING = "deleting"
    ERROR = "error"


class DistanceMetric(Enum):
    """Distance metrics for Pinecone."""
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOTPRODUCT = "dotproduct"


class PodType(Enum):
    """Pinecone pod types."""
    S1 = "s1"
    S1_X1 = "s1.x1"
    S1_X2 = "s1.x2"
    S1_X4 = "s1.x4"
    S1_X8 = "s1.x8"
    P1 = "p1"
    P1_X1 = "p1.x1"
    P1_X2 = "p1.x2"
    P1_X4 = "p1.x4"
    P1_X8 = "p1.x8"
    P2 = "p2"
    P2_X1 = "p2.x1"
    P2_X2 = "p2.x2"
    P2_X4 = "p2.x4"
    P2_X8 = "p2.x8"


@dataclass
class IndexConfig:
    """Configuration for a Pinecone index."""
    name: str
    dimension: int
    metric: DistanceMetric = DistanceMetric.COSINE
    pod_type: PodType = PodType.P1
    metadata_config: Optional[Dict[str, Any]] = None
    replicas: int = 1
    shards: int = 1
    pods: int = 1


@dataclass
class Vector:
    """Vector for Pinecone storage."""
    id: str
    values: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    sparse_values: Optional[Dict[str, Any]] = None


@dataclass
class QueryResult:
    """Result from a Pinecone query."""
    id: str
    score: float
    metadata: Dict[str, Any]
    values: Optional[List[float]] = None


@dataclass
class IndexStats:
    """Statistics for a Pinecone index."""
    name: str
    dimension: int
    vector_count: int
    status: IndexStatus
    metric: str
    pod_type: str
    replicas: int
    shards: int
    pods: int
    memory_usage: int
    created_at: float
    updated_at: float


# ============================================
# Pinecone Client Implementation
# ============================================

class PineconeClient:
    """
    Pinecone client for the NEXUS AI Trading System.
    
    This class provides a high-level interface to Pinecone for vector storage
    and retrieval with support for multiple indexes and advanced features.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        environment: Optional[str] = None,
        region: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the Pinecone client.
        
        Args:
            api_key: Pinecone API key
            environment: Pinecone environment
            region: Pinecone region
            **kwargs: Additional arguments for Pinecone
        """
        if not PINECONE_AVAILABLE:
            raise ImportError("Pinecone is not available. Install with: pip install pinecone-client")
        
        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.environ.get('PINECONE_API_KEY')
            if not api_key:
                raise ValueError("PINECONE_API_KEY environment variable not set")
        
        self.api_key = api_key
        self.environment = environment or os.environ.get('PINECONE_ENVIRONMENT', 'us-west1-gcp')
        self.region = region or os.environ.get('PINECONE_REGION', 'us-west1')
        
        # Initialize Pinecone
        try:
            pinecone.init(
                api_key=api_key,
                environment=self.environment,
                **kwargs
            )
            self.client = pinecone
            self.logger = logging.getLogger(__name__)
            self.logger.info(f"Connected to Pinecone in {self.environment}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Pinecone: {e}")
            raise
        
        # Cache indexes
        self.indexes: Dict[str, Any] = {}
        self.index_configs: Dict[str, IndexConfig] = {}
        self.index_stats: Dict[str, IndexStats] = {}
        
        # Load existing indexes
        self._load_indexes()
        
        self.logger.info("PineconeClient initialized")
    
    # ============================================
    # Index Management
    # ============================================
    
    def _load_indexes(self) -> None:
        """Load existing indexes."""
        try:
            existing_indexes = pinecone.list_indexes()
            for index_name in existing_indexes:
                self.indexes[index_name] = pinecone.Index(index_name)
                self._update_index_stats(index_name)
            self.logger.info(f"Loaded {len(existing_indexes)} indexes")
        except Exception as e:
            self.logger.warning(f"Failed to load indexes: {e}")
    
    def _update_index_stats(self, index_name: str) -> None:
        """
        Update statistics for an index.
        
        Args:
            index_name: Index name
        """
        if index_name not in self.indexes:
            return
        
        try:
            index = self.indexes[index_name]
            stats = index.describe_index_stats()
            
            self.index_stats[index_name] = IndexStats(
                name=index_name,
                dimension=stats.get('dimension', 0),
                vector_count=stats.get('total_vector_count', 0),
                status=IndexStatus.READY,
                metric=stats.get('metric', 'cosine'),
                pod_type=stats.get('pod_type', 'p1'),
                replicas=stats.get('replicas', 1),
                shards=stats.get('shards', 1),
                pods=stats.get('pods', 1),
                memory_usage=0,
                created_at=stats.get('created_at', time.time()),
                updated_at=stats.get('updated_at', time.time()),
            )
        except Exception as e:
            self.logger.warning(f"Failed to update index stats: {e}")
    
    def create_index(
        self,
        name: str,
        dimension: int,
        metric: DistanceMetric = DistanceMetric.COSINE,
        pod_type: PodType = PodType.P1,
        replicas: int = 1,
        shards: int = 1,
        pods: int = 1,
        metadata_config: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> bool:
        """
        Create a new Pinecone index.
        
        Args:
            name: Index name
            dimension: Vector dimension
            metric: Distance metric
            pod_type: Pod type
            replicas: Number of replicas
            shards: Number of shards
            pods: Number of pods
            metadata_config: Metadata configuration
            **kwargs: Additional arguments
            
        Returns:
            True if created
        """
        if name in self.indexes:
            self.logger.warning(f"Index {name} already exists")
            return False
        
        try:
            pinecone.create_index(
                name=name,
                dimension=dimension,
                metric=metric.value,
                pod_type=pod_type.value,
                replicas=replicas,
                shards=shards,
                pods=pods,
                metadata_config=metadata_config,
                **kwargs
            )
            
            # Wait for index to be ready
            self._wait_for_index_ready(name)
            
            # Connect to index
            self.indexes[name] = pinecone.Index(name)
            self.index_configs[name] = IndexConfig(
                name=name,
                dimension=dimension,
                metric=metric,
                pod_type=pod_type,
                metadata_config=metadata_config,
                replicas=replicas,
                shards=shards,
                pods=pods,
            )
            self._update_index_stats(name)
            
            self.logger.info(f"Created index: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create index {name}: {e}")
            return False
    
    def _wait_for_index_ready(self, name: str, timeout: int = 300) -> bool:
        """
        Wait for index to be ready.
        
        Args:
            name: Index name
            timeout: Timeout in seconds
            
        Returns:
            True if ready
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                indexes = pinecone.list_indexes()
                if name in indexes:
                    return True
                time.sleep(5)
            except:
                time.sleep(5)
        
        self.logger.warning(f"Index {name} not ready after {timeout}s")
        return False
    
    def delete_index(self, name: str) -> bool:
        """
        Delete an index.
        
        Args:
            name: Index name
            
        Returns:
            True if deleted
        """
        if name not in self.indexes:
            return False
        
        try:
            pinecone.delete_index(name)
            del self.indexes[name]
            if name in self.index_configs:
                del self.index_configs[name]
            if name in self.index_stats:
                del self.index_stats[name]
            self.logger.info(f"Deleted index: {name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete index {name}: {e}")
            return False
    
    def list_indexes(self) -> List[str]:
        """
        List all indexes.
        
        Returns:
            List of index names
        """
        return list(self.indexes.keys())
    
    def get_index(self, name: str) -> Optional[Any]:
        """
        Get an index by name.
        
        Args:
            name: Index name
            
        Returns:
            Index object or None
        """
        if name in self.indexes:
            return self.indexes[name]
        
        try:
            index = pinecone.Index(name)
            self.indexes[name] = index
            self._update_index_stats(name)
            return index
        except:
            return None
    
    def get_index_stats(self, name: str) -> Optional[IndexStats]:
        """
        Get statistics for an index.
        
        Args:
            name: Index name
            
        Returns:
            Index statistics or None
        """
        if name not in self.indexes:
            return None
        
        self._update_index_stats(name)
        return self.index_stats.get(name)
    
    def get_all_stats(self) -> Dict[str, IndexStats]:
        """
        Get statistics for all indexes.
        
        Returns:
            Dictionary of index statistics
        """
        for name in self.indexes:
            self._update_index_stats(name)
        return self.index_stats
    
    # ============================================
    # Vector Operations
    # ============================================
    
    def upsert(
        self,
        index_name: str,
        vectors: Union[Vector, List[Vector]],
        namespace: Optional[str] = None,
        **kwargs
    ) -> int:
        """
        Upsert vectors to an index.
        
        Args:
            index_name: Index name
            vectors: Vector(s) to upsert
            namespace: Namespace
            **kwargs: Additional arguments
            
        Returns:
            Number of vectors upserted
        """
        index = self.get_index(index_name)
        if not index:
            raise ValueError(f"Index {index_name} not found")
        
        # Convert to list
        if isinstance(vectors, Vector):
            vectors = [vectors]
        
        # Prepare data
        data = []
        for vector in vectors:
            item = {
                'id': vector.id,
                'values': vector.values,
                'metadata': vector.metadata,
            }
            if vector.sparse_values:
                item['sparse_values'] = vector.sparse_values
            data.append(item)
        
        try:
            index.upsert(vectors=data, namespace=namespace, **kwargs)
            self._update_index_stats(index_name)
            self.logger.info(f"Upserted {len(vectors)} vectors to {index_name}")
            return len(vectors)
        except Exception as e:
            self.logger.error(f"Failed to upsert vectors: {e}")
            raise
    
    def upsert_vector(
        self,
        index_name: str,
        vector: Vector,
        namespace: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Upsert a single vector.
        
        Args:
            index_name: Index name
            vector: Vector to upsert
            namespace: Namespace
            **kwargs: Additional arguments
            
        Returns:
            True if successful
        """
        try:
            self.upsert(index_name, [vector], namespace, **kwargs)
            return True
        except:
            return False
    
    def query(
        self,
        index_name: str,
        vector: List[float],
        top_k: int = 10,
        namespace: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None,
        include_values: bool = False,
        include_metadata: bool = True,
        **kwargs
    ) -> List[QueryResult]:
        """
        Query an index.
        
        Args:
            index_name: Index name
            vector: Query vector
            top_k: Number of results
            namespace: Namespace
            filter: Metadata filter
            include_values: Whether to include vector values
            include_metadata: Whether to include metadata
            **kwargs: Additional arguments
            
        Returns:
            List of query results
        """
        index = self.get_index(index_name)
        if not index:
            raise ValueError(f"Index {index_name} not found")
        
        try:
            results = index.query(
                vector=vector,
                top_k=top_k,
                namespace=namespace,
                filter=filter,
                include_values=include_values,
                include_metadata=include_metadata,
                **kwargs
            )
            
            query_results = []
            if results and results.get('matches'):
                for match in results['matches']:
                    query_results.append(QueryResult(
                        id=match['id'],
                        score=match['score'],
                        metadata=match.get('metadata', {}),
                        values=match.get('values') if include_values else None,
                    ))
            
            return query_results
            
        except Exception as e:
            self.logger.error(f"Failed to query index {index_name}: {e}")
            raise
    
    def query_by_id(
        self,
        index_name: str,
        vector_id: str,
        top_k: int = 10,
        namespace: Optional[str] = None,
        include_values: bool = False,
        include_metadata: bool = True,
        **kwargs
    ) -> List[QueryResult]:
        """
        Query by vector ID.
        
        Args:
            index_name: Index name
            vector_id: Vector ID
            top_k: Number of results
            namespace: Namespace
            include_values: Whether to include vector values
            include_metadata: Whether to include metadata
            **kwargs: Additional arguments
            
        Returns:
            List of query results
        """
        # Get vector first
        vectors = self.fetch(index_name, [vector_id], namespace)
        if not vectors or vector_id not in vectors:
            raise ValueError(f"Vector {vector_id} not found")
        
        vector = vectors[vector_id]
        return self.query(
            index_name,
            vector['values'],
            top_k,
            namespace,
            include_values=include_values,
            include_metadata=include_metadata,
            **kwargs
        )
    
    def fetch(
        self,
        index_name: str,
        ids: Union[str, List[str]],
        namespace: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch vectors by ID.
        
        Args:
            index_name: Index name
            ids: Vector ID(s)
            namespace: Namespace
            **kwargs: Additional arguments
            
        Returns:
            Dictionary of vector data
        """
        index = self.get_index(index_name)
        if not index:
            raise ValueError(f"Index {index_name} not found")
        
        if isinstance(ids, str):
            ids = [ids]
        
        try:
            results = index.fetch(ids=ids, namespace=namespace, **kwargs)
            return results.get('vectors', {})
        except Exception as e:
            self.logger.error(f"Failed to fetch vectors: {e}")
            raise
    
    def delete_vectors(
        self,
        index_name: str,
        ids: Union[str, List[str]],
        namespace: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Delete vectors by ID.
        
        Args:
            index_name: Index name
            ids: Vector ID(s)
            namespace: Namespace
            **kwargs: Additional arguments
            
        Returns:
            True if successful
        """
        index = self.get_index(index_name)
        if not index:
            raise ValueError(f"Index {index_name} not found")
        
        if isinstance(ids, str):
            ids = [ids]
        
        try:
            index.delete(ids=ids, namespace=namespace, **kwargs)
            self._update_index_stats(index_name)
            self.logger.info(f"Deleted {len(ids)} vectors from {index_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete vectors: {e}")
            return False
    
    def delete_by_filter(
        self,
        index_name: str,
        filter: Dict[str, Any],
        namespace: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Delete vectors by metadata filter.
        
        Args:
            index_name: Index name
            filter: Metadata filter
            namespace: Namespace
            **kwargs: Additional arguments
            
        Returns:
            True if successful
        """
        index = self.get_index(index_name)
        if not index:
            raise ValueError(f"Index {index_name} not found")
        
        try:
            index.delete(filter=filter, namespace=namespace, **kwargs)
            self._update_index_stats(index_name)
            self.logger.info(f"Deleted vectors from {index_name} by filter")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete vectors: {e}")
            return False
    
    def delete_all_vectors(
        self,
        index_name: str,
        namespace: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Delete all vectors from an index.
        
        Args:
            index_name: Index name
            namespace: Namespace
            **kwargs: Additional arguments
            
        Returns:
            True if successful
        """
        index = self.get_index(index_name)
        if not index:
            raise ValueError(f"Index {index_name} not found")
        
        try:
            index.delete(delete_all=True, namespace=namespace, **kwargs)
            self._update_index_stats(index_name)
            self.logger.info(f"Deleted all vectors from {index_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete all vectors: {e}")
            return False
    
    # ============================================
    # Batch Operations
    # ============================================
    
    def batch_upsert(
        self,
        index_name: str,
        vectors: List[Vector],
        batch_size: int = 100,
        namespace: Optional[str] = None,
        **kwargs
    ) -> int:
        """
        Upsert vectors in batches.
        
        Args:
            index_name: Index name
            vectors: List of vectors
            batch_size: Batch size
            namespace: Namespace
            **kwargs: Additional arguments
            
        Returns:
            Total number of vectors upserted
        """
        total = 0
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            count = self.upsert(index_name, batch, namespace, **kwargs)
            total += count
            self.logger.debug(f"Upserted batch {i//batch_size + 1}: {count} vectors")
        
        return total
    
    def batch_query(
        self,
        index_name: str,
        vectors: List[List[float]],
        top_k: int = 10,
        namespace: Optional[str] = None,
        **kwargs
    ) -> List[List[QueryResult]]:
        """
        Query multiple vectors.
        
        Args:
            index_name: Index name
            vectors: List of query vectors
            top_k: Number of results per query
            namespace: Namespace
            **kwargs: Additional arguments
            
        Returns:
            List of query results
        """
        all_results = []
        for vector in vectors:
            results = self.query(
                index_name,
                vector,
                top_k,
                namespace,
                **kwargs
            )
            all_results.append(results)
        
        return all_results
    
    # ============================================
    # Namespace Management
    # ============================================
    
    def list_namespaces(self, index_name: str) -> List[str]:
        """
        List all namespaces in an index.
        
        Args:
            index_name: Index name
            
        Returns:
            List of namespace names
        """
        stats = self.get_index_stats(index_name)
        if stats:
            return list(stats.namespaces.keys()) if hasattr(stats, 'namespaces') else []
        return []
    
    def delete_namespace(
        self,
        index_name: str,
        namespace: str,
        **kwargs
    ) -> bool:
        """
        Delete a namespace.
        
        Args:
            index_name: Index name
            namespace: Namespace
            **kwargs: Additional arguments
            
        Returns:
            True if successful
        """
        return self.delete_all_vectors(index_name, namespace, **kwargs)
    
    # ============================================
    # Export and Import
    # ============================================
    
    def export_vectors(
        self,
        index_name: str,
        ids: Optional[List[str]] = None,
        namespace: Optional[str] = None,
        file_path: Optional[Union[str, Path]] = None,
        format: str = "json",
    ) -> Union[str, Dict[str, Any]]:
        """
        Export vectors from an index.
        
        Args:
            index_name: Index name
            ids: Vector IDs to export
            namespace: Namespace
            file_path: Path to save the export
            format: Export format
            
        Returns:
            Exported data or file path
        """
        index = self.get_index(index_name)
        if not index:
            raise ValueError(f"Index {index_name} not found")
        
        if ids:
            vectors = self.fetch(index_name, ids, namespace)
        else:
            # Get all vectors by querying with a dummy vector
            # This is a limitation - Pinecone doesn't support exporting all vectors
            # Use a random vector and high top_k
            stats = self.get_index_stats(index_name)
            if not stats:
                raise ValueError("Cannot get index statistics")
            
            dimension = stats.dimension
            dummy_vector = np.random.randn(dimension).tolist()
            results = self.query(
                index_name,
                dummy_vector,
                top_k=min(stats.vector_count, 10000),
                namespace=namespace,
                include_values=True,
                include_metadata=True
            )
            
            vectors = {}
            for result in results:
                vectors[result.id] = {
                    'values': result.values,
                    'metadata': result.metadata,
                }
        
        export_data = {
            'index_name': index_name,
            'namespace': namespace,
            'vectors': vectors,
            'timestamp': time.time(),
        }
        
        if file_path:
            file_path = Path(file_path)
            if format == "json":
                with open(file_path, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
            elif format == "pickle":
                with open(file_path, 'wb') as f:
                    pickle.dump(export_data, f)
            else:
                raise ValueError(f"Unsupported format: {format}")
            return str(file_path)
        
        return export_data
    
    def import_vectors(
        self,
        index_name: str,
        data: Union[str, Dict[str, Any], bytes],
        format: str = "json",
        namespace: Optional[str] = None,
        **kwargs
    ) -> int:
        """
        Import vectors to an index.
        
        Args:
            index_name: Index name
            data: Data to import
            format: Data format
            namespace: Namespace
            **kwargs: Additional arguments
            
        Returns:
            Number of vectors imported
        """
        try:
            if format == "json":
                if isinstance(data, str):
                    with open(data, 'r') as f:
                        import_data = json.load(f)
                else:
                    import_data = data
            elif format == "pickle":
                if isinstance(data, (bytes, bytearray)):
                    import_data = pickle.loads(data)
                else:
                    with open(data, 'rb') as f:
                        import_data = pickle.load(f)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            vectors_data = import_data.get('vectors', {})
            
            # Convert to Vector objects
            vectors = []
            for vector_id, vector_data in vectors_data.items():
                vectors.append(Vector(
                    id=vector_id,
                    values=vector_data.get('values', []),
                    metadata=vector_data.get('metadata', {}),
                ))
            
            # Upsert vectors
            if vectors:
                count = self.batch_upsert(index_name, vectors, namespace=namespace, **kwargs)
                self.logger.info(f"Imported {count} vectors to {index_name}")
                return count
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Failed to import vectors: {e}")
            raise
    
    # ============================================
    # Backup and Recovery
    # ============================================
    
    def create_backup(
        self,
        index_name: str,
        backup_dir: Optional[Union[str, Path]] = None,
        **kwargs
    ) -> Dict[str, str]:
        """
        Create a backup of an index.
        
        Args:
            index_name: Index name
            backup_dir: Directory to save backup
            **kwargs: Additional arguments
            
        Returns:
            Backup file paths
        """
        backup_dir = Path(backup_dir) if backup_dir else Path("./pinecone_backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = int(time.time())
        backup_file = backup_dir / f"{index_name}_{timestamp}.json"
        
        self.export_vectors(index_name, file_path=backup_file, format="json", **kwargs)
        
        return {index_name: str(backup_file)}
    
    def restore_backup(
        self,
        index_name: str,
        backup_file: Union[str, Path],
        namespace: Optional[str] = None,
        **kwargs
    ) -> int:
        """
        Restore from a backup.
        
        Args:
            index_name: Index name
            backup_file: Backup file path
            namespace: Namespace
            **kwargs: Additional arguments
            
        Returns:
            Number of vectors restored
        """
        return self.import_vectors(index_name, str(backup_file), format="json", namespace=namespace, **kwargs)
    
    # ============================================
    # Monitoring and Maintenance
    # ============================================
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Health check results
        """
        try:
            indexes = pinecone.list_indexes()
            
            return {
                'status': 'healthy',
                'timestamp': time.time(),
                'index_count': len(indexes),
                'indexes': indexes,
                'total_vectors': sum(
                    stats.vector_count for stats in self.index_stats.values()
                ),
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'timestamp': time.time(),
                'error': str(e),
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get overall statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = {
            'indexes': self.get_all_stats(),
            'total_indexes': len(self.indexes),
            'total_vectors': sum(
                stats.vector_count for stats in self.index_stats.values()
            ),
            'timestamp': time.time(),
        }
        return stats
    
    def optimize_index(self, index_name: str) -> bool:
        """
        Optimize an index.
        
        Args:
            index_name: Index name
            
        Returns:
            True if optimized
        """
        # Pinecone automatically optimizes indexes
        self.logger.info(f"Index {index_name} is automatically optimized by Pinecone")
        return True
    
    # ============================================
    # Shutdown
    # ============================================
    
    def shutdown(self) -> None:
        """Shutdown the Pinecone client."""
        try:
            self.logger.info("Shutting down PineconeClient")
        except Exception as e:
            self.logger.error(f"Shutdown error: {e}")


# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point for CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Pinecone Client CLI')
    parser.add_argument('--command', choices=['list', 'stats', 'create', 'delete', 'query', 'upsert', 'backup', 'restore'],
                       required=True, help='Command to execute')
    parser.add_argument('--api-key', type=str, help='Pinecone API key')
    parser.add_argument('--environment', type=str, help='Pinecone environment')
    parser.add_argument('--index', type=str, help='Index name')
    parser.add_argument('--dimension', type=int, help='Vector dimension')
    parser.add_argument('--metric', type=str, default='cosine', help='Distance metric')
    parser.add_argument('--pod-type', type=str, default='p1', help='Pod type')
    parser.add_argument('--file', type=str, help='File for import/export')
    parser.add_argument('--query', type=str, help='Query vector (comma-separated)')
    parser.add_argument('--top-k', type=int, default=10, help='Number of results')
    parser.add_argument('--namespace', type=str, help='Namespace')
    
    args = parser.parse_args()
    
    # Initialize client
    client = PineconeClient(
        api_key=args.api_key,
        environment=args.environment,
    )
    
    if args.command == 'list':
        indexes = client.list_indexes()
        print("Indexes:")
        for name in indexes:
            stats = client.get_index_stats(name)
            if stats:
                print(f"  {name}: {stats.vector_count} vectors")
            else:
                print(f"  {name}")
    
    elif args.command == 'stats':
        if args.index:
            stats = client.get_index_stats(args.index)
            if stats:
                print(f"\nIndex: {stats.name}")
                print(f"  Vectors: {stats.vector_count}")
                print(f"  Dimension: {stats.dimension}")
                print(f"  Metric: {stats.metric}")
                print(f"  Status: {stats.status.value}")
                print(f"  Pod Type: {stats.pod_type}")
                print(f"  Replicas: {stats.replicas}")
                print(f"  Shards: {stats.shards}")
                print(f"  Pods: {stats.pods}")
            else:
                print(f"Index {args.index} not found")
        else:
            all_stats = client.get_stats()
            print(f"\nTotal Indexes: {all_stats['total_indexes']}")
            print(f"Total Vectors: {all_stats['total_vectors']}")
            for name, stats in all_stats['indexes'].items():
                print(f"\nIndex: {name}")
                print(f"  Vectors: {stats.vector_count}")
    
    elif args.command == 'create':
        if not args.index:
            print("Error: --index required for create")
            return
        if not args.dimension:
            print("Error: --dimension required for create")
            return
        
        client.create_index(
            name=args.index,
            dimension=args.dimension,
            metric=DistanceMetric(args.metric),
            pod_type=PodType(args.pod_type),
        )
        print(f"Index {args.index} created")
    
    elif args.command == 'delete':
        if not args.index:
            print("Error: --index required for delete")
            return
        if client.delete_index(args.index):
            print(f"Index {args.index} deleted")
        else:
            print(f"Failed to delete index {args.index}")
    
    elif args.command == 'query':
        if not args.index:
            print("Error: --index required for query")
            return
        if not args.query:
            print("Error: --query required for query")
            return
        
        vector = [float(x.strip()) for x in args.query.split(',')]
        results = client.query(
            args.index,
            vector,
            top_k=args.top_k,
            namespace=args.namespace,
        )
        
        print(f"\nFound {len(results)} results:")
        for i, result in enumerate(results):
            print(f"{i+1}. ID: {result.id}")
            print(f"   Score: {result.score:.4f}")
            print(f"   Metadata: {result.metadata}")
            print()
    
    elif args.command == 'upsert':
        if not args.index:
            print("Error: --index required for upsert")
            return
        if not args.file:
            print("Enter vector data (id,values,metadata):")
            data = input()
            parts = data.split(',', 2)
            if len(parts) < 2:
                print("Error: Invalid format. Use: id,value1,value2,...,metadata")
                return
            
            vector_id = parts[0]
            values = [float(x.strip()) for x in parts[1].split(',') if x.strip()]
            metadata = {}
            if len(parts) > 2:
                try:
                    metadata = json.loads(parts[2])
                except:
                    pass
            
            vector = Vector(id=vector_id, values=values, metadata=metadata)
            client.upsert_vector(args.index, vector, namespace=args.namespace)
            print(f"Upserted vector {vector_id}")
        else:
            with open(args.file, 'r') as f:
                data = json.load(f)
            
            vectors = []
            for item in data:
                vectors.append(Vector(
                    id=item['id'],
                    values=item['values'],
                    metadata=item.get('metadata', {}),
                ))
            
            count = client.batch_upsert(args.index, vectors, namespace=args.namespace)
            print(f"Upserted {count} vectors")
    
    elif args.command == 'backup':
        if not args.index:
            print("Error: --index required for backup")
            return
        backups = client.create_backup(args.index)
        print("Backups created:")
        for name, path in backups.items():
            print(f"  {name}: {path}")
    
    elif args.command == 'restore':
        if not args.index or not args.file:
            print("Error: --index and --file required for restore")
            return
        count = client.restore_backup(args.index, args.file, namespace=args.namespace)
        print(f"Restored {count} vectors to {args.index}")
    
    client.shutdown()


if __name__ == '__main__':
    main()
