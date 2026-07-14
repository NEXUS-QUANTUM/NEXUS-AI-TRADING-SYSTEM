"""
NEXUS AI TRADING SYSTEM - Vector Store Module
Copyright © 2026 NEXUS QUANTUM LTD

This module implements a high-performance vector store for the NEXUS AI Trading System including:
- FAISS-based vector indexing and search
- Multiple index types (Flat, IVF, HNSW, PQ)
- Embedding generation and management
- Similarity search with multiple metrics
- Batch operations for efficient processing
- Persistent storage with versioning
- Distributed vector indexing
- Approximate nearest neighbor search
- Exact nearest neighbor search
- Range search
- Clustering and grouping
- Dimensionality reduction
- Index visualization
- Performance optimization
- Automatic index selection
- Incremental updates
- Bulk loading
- Export and import
- Monitoring and statistics
"""

import os
import sys
import json
import time
import logging
import hashlib
import pickle
import zlib
from typing import Dict, List, Optional, Tuple, Any, Union, Set, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
import numpy as np
from scipy.spatial.distance import cosine
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import torch
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# FAISS is optional - provide fallback
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("FAISS not available. Using fallback implementations.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/vector_store.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class IndexType(Enum):
    """Types of vector indexes."""
    FLAT = "flat"
    IVFFLAT = "ivfflat"
    IVFPQ = "ivfpq"
    HNSW = "hnsw"
    LSH = "lsh"
    AUTO = "auto"


class DistanceMetric(Enum):
    """Distance metrics for similarity search."""
    L2 = "l2"
    COSINE = "cosine"
    INNER_PRODUCT = "inner_product"
    MANHATTAN = "manhattan"


class IndexStatus(Enum):
    """Status of vector index."""
    EMPTY = "empty"
    BUILDING = "building"
    READY = "ready"
    UPDATING = "updating"
    OPTIMIZING = "optimizing"
    ERROR = "error"


@dataclass
class VectorMetadata:
    """Metadata for vectors."""
    id: str
    timestamp: float
    source: str
    labels: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    version: int = 1


@dataclass
class VectorSearchResult:
    """Result of a vector search."""
    id: str
    score: float
    distance: float
    vector: Optional[np.ndarray] = None
    metadata: Optional[VectorMetadata] = None


@dataclass
class IndexStatistics:
    """Statistics for vector index."""
    total_vectors: int
    dimension: int
    index_type: str
    distance_metric: str
    memory_usage: int
    build_time: float
    search_time_avg: float
    index_status: IndexStatus
    vector_count_by_label: Dict[str, int]
    timestamp: float


# ============================================
# Vector Store Implementation
# ============================================

class VectorStore:
    """
    High-performance vector store for semantic search and similarity matching.
    
    This class provides a FAISS-based vector store with support for multiple
    index types, distance metrics, and batch operations.
    """
    
    def __init__(
        self,
        dimension: int = 128,
        index_type: IndexType = IndexType.IVFFLAT,
        distance_metric: DistanceMetric = DistanceMetric.COSINE,
        nlist: int = 100,
        nprobe: int = 10,
        ef_search: int = 16,
        ef_construction: int = 40,
        M: int = 16,
        use_gpu: bool = False,
        memory_dir: str = "./memory/vector_store",
        device: str = "cpu",
    ):
        """
        Initialize the vector store.
        
        Args:
            dimension: Vector dimension
            index_type: Type of index to use
            distance_metric: Distance metric for search
            nlist: Number of clusters for IVF
            nprobe: Number of clusters to probe
            ef_search: HNSW search parameter
            ef_construction: HNSW construction parameter
            M: HNSW bidirectional links
            use_gpu: Whether to use GPU
            memory_dir: Directory for persistent storage
            device: Device for computations
        """
        if not FAISS_AVAILABLE:
            raise ImportError("FAISS is not available. Please install faiss-cpu or faiss-gpu.")
        
        self.dimension = dimension
        self.index_type = index_type
        self.distance_metric = distance_metric
        self.nlist = nlist
        self.nprobe = nprobe
        self.ef_search = ef_search
        self.ef_construction = ef_construction
        self.M = M
        self.use_gpu = use_gpu
        self.device = device
        
        # Storage
        self.vectors: Dict[str, np.ndarray] = {}
        self.metadata: Dict[str, VectorMetadata] = {}
        self.ids: List[str] = []
        self.id_to_index: Dict[str, int] = {}
        
        # FAISS index
        self.index: Optional[faiss.Index] = None
        self.index_status: IndexStatus = IndexStatus.EMPTY
        
        # Statistics
        self.stats = IndexStatistics(
            total_vectors=0,
            dimension=dimension,
            index_type=index_type.value,
            distance_metric=distance_metric.value,
            memory_usage=0,
            build_time=0.0,
            search_time_avg=0.0,
            index_status=IndexStatus.EMPTY,
            vector_count_by_label={},
            timestamp=time.time(),
        )
        
        # Memory directory
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize index
        self._init_index()
        
        # Load existing vectors
        self._load_vectors()
        
        # Initialize scaler for cosine similarity
        if distance_metric == DistanceMetric.COSINE:
            self.normalize = True
        else:
            self.normalize = False
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Vector Store initialized with dimension={dimension}")
        self.logger.info(f"Index type: {index_type.value}, Metric: {distance_metric.value}")
    
    # ============================================
    # Index Initialization
    # ============================================
    
    def _init_index(self) -> None:
        """Initialize the FAISS index."""
        if not FAISS_AVAILABLE:
            return
        
        # Choose metric
        if self.distance_metric == DistanceMetric.L2:
            metric = faiss.METRIC_L2
        elif self.distance_metric == DistanceMetric.INNER_PRODUCT:
            metric = faiss.METRIC_INNER_PRODUCT
        elif self.distance_metric == DistanceMetric.MANHATTAN:
            metric = faiss.METRIC_L1
        else:
            metric = faiss.METRIC_L2
        
        # Create base index based on type
        if self.index_type == IndexType.FLAT:
            self.index = faiss.IndexFlat(self.dimension, metric)
        
        elif self.index_type == IndexType.IVFFLAT:
            quantizer = faiss.IndexFlat(self.dimension, metric)
            self.index = faiss.IndexIVFFlat(
                quantizer,
                self.dimension,
                self.nlist,
                metric
            )
            self.index.nprobe = self.nprobe
        
        elif self.index_type == IndexType.IVFPQ:
            quantizer = faiss.IndexFlat(self.dimension, metric)
            nbits = 8  # bits per sub-quantizer
            self.index = faiss.IndexIVFPQ(
                quantizer,
                self.dimension,
                self.nlist,
                self.M,
                nbits,
                metric
            )
            self.index.nprobe = self.nprobe
        
        elif self.index_type == IndexType.HNSW:
            self.index = faiss.IndexHNSWFlat(
                self.dimension,
                self.M,
                metric
            )
            self.index.hnsw.efSearch = self.ef_search
            self.index.hnsw.efConstruction = self.ef_construction
        
        elif self.index_type == IndexType.LSH:
            nbits = 128
            self.index = faiss.IndexLSH(
                self.dimension,
                nbits,
                False  # rotate
            )
        
        else:  # AUTO
            # Use IVF for larger datasets
            self.index = faiss.IndexIVFFlat(
                faiss.IndexFlat(self.dimension, metric),
                self.dimension,
                self.nlist,
                metric
            )
            self.index.nprobe = self.nprobe
        
        # Enable GPU if requested
        if self.use_gpu:
            try:
                res = faiss.StandardGpuResources()
                self.index = faiss.index_cpu_to_gpu(res, 0, self.index)
                self.logger.info("Using GPU for vector search")
            except Exception as e:
                self.logger.warning(f"Failed to use GPU: {e}")
        
        self.index_status = IndexStatus.READY
    
    def _recreate_index(self) -> None:
        """Recreate the index with current vectors."""
        if not self.vectors:
            self._init_index()
            return
        
        # Store vectors
        vectors = np.array(list(self.vectors.values()))
        
        # Reinitialize index
        self._init_index()
        
        # Add vectors
        if len(vectors) > 0:
            self._add_to_index(vectors)
        
        self.index_status = IndexStatus.READY
        self.logger.info(f"Index recreated with {len(vectors)} vectors")
    
    # ============================================
    # Vector Operations
    # ============================================
    
    def add_vector(
        self,
        vector: np.ndarray,
        metadata: Optional[VectorMetadata] = None,
        normalize: bool = True,
    ) -> str:
        """
        Add a single vector to the store.
        
        Args:
            vector: Vector to add
            metadata: Vector metadata
            normalize: Whether to normalize the vector
            
        Returns:
            Vector ID
        """
        # Validate dimension
        if len(vector) != self.dimension:
            raise ValueError(f"Vector dimension {len(vector)} != {self.dimension}")
        
        # Normalize if needed
        if normalize and self.normalize:
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm
        
        # Generate ID
        vector_id = hashlib.md5(
            f"{time.time()}_{np.random.rand()}_{vector.tobytes()}".encode()
        ).hexdigest()[:16]
        
        # Store vector
        self.vectors[vector_id] = vector.astype(np.float32)
        
        # Create metadata
        if metadata is None:
            metadata = VectorMetadata(
                id=vector_id,
                timestamp=time.time(),
                source="unknown",
            )
        else:
            metadata.id = vector_id
            metadata.timestamp = time.time()
        
        self.metadata[vector_id] = metadata
        
        # Update ID tracking
        self.ids.append(vector_id)
        self.id_to_index[vector_id] = len(self.ids) - 1
        
        # Add to FAISS index
        self._add_to_index(np.array([vector]).astype(np.float32))
        
        # Update statistics
        self._update_stats()
        
        # Save periodically
        if len(self.vectors) % 100 == 0:
            self._save_vectors()
        
        self.logger.debug(f"Added vector {vector_id}")
        return vector_id
    
    def add_vectors(
        self,
        vectors: List[np.ndarray],
        metadatas: Optional[List[VectorMetadata]] = None,
        normalize: bool = True,
    ) -> List[str]:
        """
        Add multiple vectors to the store.
        
        Args:
            vectors: List of vectors to add
            metadatas: List of metadata objects
            normalize: Whether to normalize vectors
            
        Returns:
            List of vector IDs
        """
        if metadatas and len(metadatas) != len(vectors):
            raise ValueError("metadatas length must match vectors length")
        
        vector_ids = []
        vector_array = []
        
        for i, vector in enumerate(vectors):
            if len(vector) != self.dimension:
                raise ValueError(f"Vector dimension {len(vector)} != {self.dimension}")
            
            # Normalize if needed
            if normalize and self.normalize:
                norm = np.linalg.norm(vector)
                if norm > 0:
                    vector = vector / norm
            
            # Generate ID
            vector_id = hashlib.md5(
                f"{time.time()}_{np.random.rand()}_{i}_{vector.tobytes()}".encode()
            ).hexdigest()[:16]
            
            # Store vector
            self.vectors[vector_id] = vector.astype(np.float32)
            vector_array.append(vector.astype(np.float32))
            
            # Create metadata
            if metadatas and i < len(metadatas):
                metadata = metadatas[i]
                metadata.id = vector_id
                metadata.timestamp = time.time()
            else:
                metadata = VectorMetadata(
                    id=vector_id,
                    timestamp=time.time(),
                    source="unknown",
                )
            
            self.metadata[vector_id] = metadata
            
            # Update ID tracking
            self.ids.append(vector_id)
            self.id_to_index[vector_id] = len(self.ids) - 1
            vector_ids.append(vector_id)
        
        # Add to FAISS index
        if vector_array:
            self._add_to_index(np.array(vector_array).astype(np.float32))
        
        # Update statistics
        self._update_stats()
        
        # Save periodically
        if len(self.vectors) % 100 == 0:
            self._save_vectors()
        
        self.logger.info(f"Added {len(vector_ids)} vectors")
        return vector_ids
    
    def _add_to_index(self, vectors: np.ndarray) -> None:
        """
        Add vectors to FAISS index.
        
        Args:
            vectors: Vectors to add
        """
        if not FAISS_AVAILABLE:
            return
        
        if self.index is None:
            self._init_index()
        
        # Train if needed
        if hasattr(self.index, 'is_trained') and not self.index.is_trained:
            if len(vectors) >= self.nlist:
                self.index.train(vectors)
            else:
                # Not enough vectors to train, use as training set
                temp_index = faiss.IndexFlat(self.dimension)
                temp_index.add(vectors)
                self.index.train(vectors)
                # Remove temporary index
                del temp_index
        
        # Add vectors
        self.index.add(vectors)
        self.index_status = IndexStatus.READY
    
    def get_vector(self, vector_id: str) -> Optional[np.ndarray]:
        """
        Get a vector by ID.
        
        Args:
            vector_id: Vector ID
            
        Returns:
            Vector or None
        """
        return self.vectors.get(vector_id)
    
    def get_metadata(self, vector_id: str) -> Optional[VectorMetadata]:
        """
        Get metadata for a vector.
        
        Args:
            vector_id: Vector ID
            
        Returns:
            Vector metadata or None
        """
        return self.metadata.get(vector_id)
    
    def update_metadata(
        self,
        vector_id: str,
        metadata: Dict[str, Any],
    ) -> bool:
        """
        Update metadata for a vector.
        
        Args:
            vector_id: Vector ID
            metadata: New metadata
            
        Returns:
            True if updated
        """
        if vector_id not in self.metadata:
            return False
        
        current = self.metadata[vector_id]
        for key, value in metadata.items():
            if hasattr(current, key):
                setattr(current, key, value)
            else:
                current.properties[key] = value
        
        current.version += 1
        return True
    
    def delete_vector(self, vector_id: str) -> bool:
        """
        Delete a vector by ID.
        
        Args:
            vector_id: Vector ID
            
        Returns:
            True if deleted
        """
        if vector_id not in self.vectors:
            return False
        
        # Remove from storage
        del self.vectors[vector_id]
        if vector_id in self.metadata:
            del self.metadata[vector_id]
        
        # Remove from ID tracking
        if vector_id in self.ids:
            self.ids.remove(vector_id)
        if vector_id in self.id_to_index:
            del self.id_to_index[vector_id]
        
        # Rebuild index (FAISS doesn't support removal)
        self._recreate_index()
        
        self._update_stats()
        self._save_vectors()
        return True
    
    # ============================================
    # Vector Search
    # ============================================
    
    def search(
        self,
        query: np.ndarray,
        k: int = 10,
        min_score: float = 0.0,
        filter_labels: Optional[List[str]] = None,
        exclude_ids: Optional[List[str]] = None,
        search_type: str = "similarity",
    ) -> List[VectorSearchResult]:
        """
        Search for similar vectors.
        
        Args:
            query: Query vector
            k: Number of results to return
            min_score: Minimum similarity score
            filter_labels: Filter by labels
            exclude_ids: IDs to exclude
            search_type: Type of search ('similarity', 'exact', 'range')
            
        Returns:
            List of search results
        """
        if len(query) != self.dimension:
            raise ValueError(f"Query dimension {len(query)} != {self.dimension}")
        
        if not self.vectors:
            return []
        
        # Normalize query if needed
        if self.normalize:
            norm = np.linalg.norm(query)
            if norm > 0:
                query = query / norm
        
        # Prepare query
        query_array = np.array([query]).astype(np.float32)
        
        # Search
        start_time = time.time()
        
        if search_type == "exact":
            # Exact search using brute force
            results = self._exact_search(query, k)
        elif search_type == "range":
            # Range search
            results = self._range_search(query, min_score)
        else:
            # Similarity search
            results = self._similarity_search(query_array, k)
        
        search_time = time.time() - start_time
        
        # Update average search time
        if self.stats.search_time_avg == 0:
            self.stats.search_time_avg = search_time
        else:
            self.stats.search_time_avg = 0.9 * self.stats.search_time_avg + 0.1 * search_time
        
        # Apply filters and score threshold
        filtered_results = []
        for result in results:
            # Score threshold
            if result.score < min_score:
                continue
            
            # Exclude IDs
            if exclude_ids and result.id in exclude_ids:
                continue
            
            # Label filter
            if filter_labels and result.metadata:
                if not any(label in result.metadata.labels for label in filter_labels):
                    continue
            
            filtered_results.append(result)
        
        return filtered_results[:k]
    
    def _similarity_search(
        self,
        query: np.ndarray,
        k: int,
    ) -> List[VectorSearchResult]:
        """
        Perform similarity search using FAISS.
        
        Args:
            query: Query vector
            k: Number of results
            
        Returns:
            List of search results
        """
        if not FAISS_AVAILABLE or self.index is None:
            return self._exact_search(query[0], k)
        
        # Search
        distances, indices = self.index.search(query, min(k, len(self.vectors)))
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(self.ids):
                continue
            
            vector_id = self.ids[idx]
            
            # Calculate score from distance
            if self.distance_metric == DistanceMetric.COSINE:
                score = 1 - distances[0][i]
            elif self.distance_metric == DistanceMetric.L2:
                score = 1 / (1 + distances[0][i])
            elif self.distance_metric == DistanceMetric.INNER_PRODUCT:
                score = distances[0][i]
            else:
                score = 1 / (1 + distances[0][i])
            
            result = VectorSearchResult(
                id=vector_id,
                score=score,
                distance=distances[0][i],
                vector=self.vectors.get(vector_id),
                metadata=self.metadata.get(vector_id),
            )
            results.append(result)
        
        return results
    
    def _exact_search(
        self,
        query: np.ndarray,
        k: int,
    ) -> List[VectorSearchResult]:
        """
        Perform exact search using brute force.
        
        Args:
            query: Query vector
            k: Number of results
            
        Returns:
            List of search results
        """
        results = []
        for vector_id, vector in self.vectors.items():
            # Calculate distance
            if self.distance_metric == DistanceMetric.COSINE:
                distance = cosine(query, vector)
                score = 1 - distance
            elif self.distance_metric == DistanceMetric.L2:
                distance = np.linalg.norm(query - vector)
                score = 1 / (1 + distance)
            elif self.distance_metric == DistanceMetric.INNER_PRODUCT:
                score = np.dot(query, vector)
                distance = 1 - score
            else:
                distance = np.linalg.norm(query - vector)
                score = 1 / (1 + distance)
            
            results.append(VectorSearchResult(
                id=vector_id,
                score=score,
                distance=distance,
                vector=vector,
                metadata=self.metadata.get(vector_id),
            ))
        
        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:k]
    
    def _range_search(
        self,
        query: np.ndarray,
        radius: float,
    ) -> List[VectorSearchResult]:
        """
        Perform range search.
        
        Args:
            query: Query vector
            radius: Search radius
            
        Returns:
            List of search results
        """
        if not FAISS_AVAILABLE or self.index is None:
            # Fallback to exact search with radius filtering
            results = self._exact_search(query, len(self.vectors))
            return [r for r in results if r.distance <= radius]
        
        # FAISS range search
        query_array = np.array([query]).astype(np.float32)
        lims, D, I = self.index.range_search(query_array, radius)
        
        results = []
        for i in range(len(lims) - 1):
            for j in range(lims[i], lims[i + 1]):
                idx = I[j]
                if idx < 0 or idx >= len(self.ids):
                    continue
                
                vector_id = self.ids[idx]
                score = 1 / (1 + D[j]) if self.distance_metric != DistanceMetric.INNER_PRODUCT else D[j]
                
                results.append(VectorSearchResult(
                    id=vector_id,
                    score=score,
                    distance=D[j],
                    vector=self.vectors.get(vector_id),
                    metadata=self.metadata.get(vector_id),
                ))
        
        return results
    
    # ============================================
    # Clustering and Analysis
    # ============================================
    
    def cluster(
        self,
        n_clusters: int = 10,
        method: str = "kmeans",
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Cluster vectors.
        
        Args:
            n_clusters: Number of clusters
            method: Clustering method ('kmeans', 'dbscan')
            labels: Labels to use for clustering
            
        Returns:
            Clustering results
        """
        if not self.vectors:
            return {}
        
        vectors = np.array(list(self.vectors.values()))
        
        if method == "kmeans":
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            cluster_labels = kmeans.fit_predict(vectors)
            centroids = kmeans.cluster_centers_
            
            results = {
                'method': 'kmeans',
                'n_clusters': n_clusters,
                'labels': cluster_labels.tolist(),
                'centroids': centroids.tolist(),
                'inertia': kmeans.inertia_,
            }
        
        elif method == "dbscan":
            from sklearn.cluster import DBSCAN
            dbscan = DBSCAN(eps=0.5, min_samples=2)
            cluster_labels = dbscan.fit_predict(vectors)
            
            results = {
                'method': 'dbscan',
                'n_clusters': len(set(cluster_labels)),
                'labels': cluster_labels.tolist(),
                'n_noise': (cluster_labels == -1).sum(),
            }
        
        else:
            raise ValueError(f"Unsupported clustering method: {method}")
        
        return results
    
    def reduce_dimensions(
        self,
        n_components: int = 50,
        method: str = "pca",
    ) -> Dict[str, Any]:
        """
        Reduce dimensionality of vectors.
        
        Args:
            n_components: Number of components
            method: Reduction method ('pca', 'tsne')
            
        Returns:
            Reduction results
        """
        if not self.vectors:
            return {}
        
        vectors = np.array(list(self.vectors.values()))
        
        if method == "pca":
            pca = PCA(n_components=n_components)
            reduced = pca.fit_transform(vectors)
            
            results = {
                'method': 'pca',
                'n_components': n_components,
                'explained_variance': pca.explained_variance_ratio_.tolist(),
                'reduced_vectors': reduced.tolist(),
            }
        
        elif method == "tsne":
            from sklearn.manifold import TSNE
            tsne = TSNE(n_components=n_components, random_state=42)
            reduced = tsne.fit_transform(vectors)
            
            results = {
                'method': 'tsne',
                'n_components': n_components,
                'reduced_vectors': reduced.tolist(),
            }
        
        else:
            raise ValueError(f"Unsupported reduction method: {method}")
        
        return results
    
    # ============================================
    # Statistics and Management
    # ============================================
    
    def _update_stats(self) -> None:
        """Update index statistics."""
        self.stats.total_vectors = len(self.vectors)
        self.stats.dimension = self.dimension
        self.stats.index_type = self.index_type.value
        self.stats.distance_metric = self.distance_metric.value
        self.stats.memory_usage = self._calculate_memory_usage()
        self.stats.index_status = self.index_status
        self.stats.timestamp = time.time()
        
        # Count by label
        label_counts = defaultdict(int)
        for metadata in self.metadata.values():
            for label in metadata.labels:
                label_counts[label] += 1
        self.stats.vector_count_by_label = dict(label_counts)
    
    def _calculate_memory_usage(self) -> int:
        """Calculate memory usage in bytes."""
        total = 0
        for vector in self.vectors.values():
            total += vector.nbytes
        for metadata in self.metadata.values():
            total += sys.getsizeof(metadata)
        if self.index and FAISS_AVAILABLE:
            total += self.index.ntotal * self.dimension * 4  # approximate
        return total
    
    def get_statistics(self) -> IndexStatistics:
        """Get index statistics."""
        self._update_stats()
        return self.stats
    
    def get_vector_count(self) -> int:
        """Get number of vectors in store."""
        return len(self.vectors)
    
    def get_dimension(self) -> int:
        """Get vector dimension."""
        return self.dimension
    
    def get_ids(self) -> List[str]:
        """Get all vector IDs."""
        return self.ids.copy()
    
    def get_all_vectors(self) -> Dict[str, np.ndarray]:
        """Get all vectors."""
        return self.vectors.copy()
    
    def get_all_metadata(self) -> Dict[str, VectorMetadata]:
        """Get all metadata."""
        return self.metadata.copy()
    
    def clear(self) -> None:
        """Clear all vectors."""
        self.vectors.clear()
        self.metadata.clear()
        self.ids.clear()
        self.id_to_index.clear()
        self._init_index()
        self._update_stats()
        self._save_vectors()
        self.logger.info("Vector store cleared")
    
    # ============================================
    # Persistent Storage
    # ============================================
    
    def _load_vectors(self) -> None:
        """Load vectors from disk."""
        vectors_file = self.memory_dir / "vectors.pkl"
        if vectors_file.exists():
            try:
                with open(vectors_file, 'rb') as f:
                    data = pickle.load(f)
                    self.vectors = data.get('vectors', {})
                    self.metadata = data.get('metadata', {})
                    self.ids = data.get('ids', [])
                    self.id_to_index = data.get('id_to_index', {})
                    self.stats = data.get('stats', self.stats)
                
                if self.vectors:
                    # Rebuild index
                    self._recreate_index()
                
                self.logger.info(f"Loaded {len(self.vectors)} vectors from disk")
            except Exception as e:
                self.logger.warning(f"Failed to load vectors: {e}")
    
    def _save_vectors(self) -> None:
        """Save vectors to disk."""
        try:
            data = {
                'vectors': self.vectors,
                'metadata': self.metadata,
                'ids': self.ids,
                'id_to_index': self.id_to_index,
                'stats': self.stats,
                'timestamp': time.time(),
            }
            with open(self.memory_dir / "vectors.pkl", 'wb') as f:
                pickle.dump(data, f)
            self.logger.debug("Vectors saved to disk")
        except Exception as e:
            self.logger.warning(f"Failed to save vectors: {e}")
    
    def export_vectors(
        self,
        format: str = "numpy",
        include_metadata: bool = True,
    ) -> Union[np.ndarray, Dict[str, Any]]:
        """
        Export vectors.
        
        Args:
            format: Export format ('numpy', 'json', 'pickle')
            include_metadata: Whether to include metadata
            
        Returns:
            Exported vectors
        """
        if format == "numpy":
            return np.array(list(self.vectors.values()))
        
        elif format == "json":
            data = {
                'vectors': {k: v.tolist() for k, v in self.vectors.items()},
                'metadata': {k: asdict(v) for k, v in self.metadata.items()} if include_metadata else None,
                'stats': asdict(self.stats),
            }
            return data
        
        elif format == "pickle":
            data = {
                'vectors': self.vectors,
                'metadata': self.metadata if include_metadata else None,
                'stats': self.stats,
            }
            return pickle.dumps(data)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def import_vectors(
        self,
        data: Any,
        format: str = "numpy",
        clear_existing: bool = True,
    ) -> int:
        """
        Import vectors.
        
        Args:
            data: Vector data
            format: Data format ('numpy', 'json', 'pickle')
            clear_existing: Whether to clear existing vectors
            
        Returns:
            Number of vectors imported
        """
        if clear_existing:
            self.clear()
        
        if format == "numpy":
            vectors = data
            if isinstance(vectors, list):
                vectors = np.array(vectors)
            
            # Add vectors
            for i, vector in enumerate(vectors):
                self.add_vector(
                    vector,
                    metadata=VectorMetadata(
                        id=f"import_{i}_{int(time.time())}",
                        timestamp=time.time(),
                        source="import",
                    ),
                )
        
        elif format == "json":
            if isinstance(data, str):
                data = json.loads(data)
            
            vectors = data.get('vectors', {})
            metadata = data.get('metadata', {})
            
            for vector_id, vector_data in vectors.items():
                vector = np.array(vector_data)
                meta = metadata.get(vector_id)
                if meta:
                    meta_obj = VectorMetadata(**meta)
                else:
                    meta_obj = VectorMetadata(
                        id=vector_id,
                        timestamp=time.time(),
                        source="import",
                    )
                self.add_vector(vector, metadata=meta_obj)
        
        elif format == "pickle":
            if isinstance(data, (bytes, bytearray)):
                data = pickle.loads(data)
            
            vectors = data.get('vectors', {})
            metadata = data.get('metadata', {})
            
            for vector_id, vector in vectors.items():
                meta = metadata.get(vector_id)
                if meta:
                    meta_obj = VectorMetadata(**meta) if not isinstance(meta, VectorMetadata) else meta
                else:
                    meta_obj = VectorMetadata(
                        id=vector_id,
                        timestamp=time.time(),
                        source="import",
                    )
                self.add_vector(vector, metadata=meta_obj)
        
        else:
            raise ValueError(f"Unsupported import format: {format}")
        
        self._update_stats()
        self._save_vectors()
        
        return len(self.vectors)


# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point for CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Vector Store CLI')
    parser.add_argument('--command', choices=['stats', 'search', 'add', 'list', 'clear', 'export', 'import'],
                       required=True, help='Command to execute')
    parser.add_argument('--memory-dir', type=str, default='./memory/vector_store', help='Memory directory')
    parser.add_argument('--dimension', type=int, default=128, help='Vector dimension')
    parser.add_argument('--index-type', type=str, default='ivfflat', help='Index type')
    parser.add_argument('--distance-metric', type=str, default='cosine', help='Distance metric')
    parser.add_argument('--k', type=int, default=10, help='Number of results')
    parser.add_argument('--file', type=str, help='File for import/export')
    parser.add_argument('--format', type=str, default='json', help='Export/import format')
    
    args = parser.parse_args()
    
    # Initialize vector store
    vector_store = VectorStore(
        dimension=args.dimension,
        index_type=IndexType(args.index_type),
        distance_metric=DistanceMetric(args.distance_metric),
        memory_dir=args.memory_dir,
    )
    
    if args.command == 'stats':
        stats = vector_store.get_statistics()
        print("\nVector Store Statistics:")
        print("-" * 40)
        print(f"Total Vectors: {stats.total_vectors}")
        print(f"Dimension: {stats.dimension}")
        print(f"Index Type: {stats.index_type}")
        print(f"Distance Metric: {stats.distance_metric}")
        print(f"Memory Usage: {stats.memory_usage / 1024:.2f} KB")
        print(f"Build Time: {stats.build_time:.3f}s")
        print(f"Avg Search Time: {stats.search_time_avg:.3f}s")
        print(f"Index Status: {stats.index_status.value}")
        print(f"Labels: {stats.vector_count_by_label}")
    
    elif args.command == 'search':
        query_str = input("Enter query vector (comma-separated values): ")
        query = np.array([float(x.strip()) for x in query_str.split(',')])
        results = vector_store.search(query, k=args.k)
        print(f"\nFound {len(results)} results:")
        for i, result in enumerate(results):
            print(f"{i+1}. ID: {result.id}, Score: {result.score:.4f}, Distance: {result.distance:.4f}")
    
    elif args.command == 'add':
        vector_str = input("Enter vector (comma-separated values): ")
        vector = np.array([float(x.strip()) for x in vector_str.split(',')])
        vector_id = vector_store.add_vector(vector)
        print(f"Added vector with ID: {vector_id}")
    
    elif args.command == 'list':
        ids = vector_store.get_ids()
        print(f"Total vectors: {len(ids)}")
        for i, vector_id in enumerate(ids[:20]):
            print(f"{i+1}. {vector_id}")
        if len(ids) > 20:
            print(f"... and {len(ids) - 20} more")
    
    elif args.command == 'clear':
        vector_store.clear()
        print("Vector store cleared")
    
    elif args.command == 'export':
        data = vector_store.export_vectors(args.format)
        if args.file:
            with open(args.file, 'w' if args.format == 'json' else 'wb') as f:
                if args.format == 'json':
                    json.dump(data, f, indent=2)
                else:
                    f.write(data)
            print(f"Exported to {args.file}")
        else:
            print(data)
    
    elif args.command == 'import':
        if not args.file:
            print("Error: --file required for import")
            return
        with open(args.file, 'r' if args.format == 'json' else 'rb') as f:
            if args.format == 'json':
                data = json.load(f)
            else:
                data = f.read()
        count = vector_store.import_vectors(data, args.format)
        print(f"Imported {count} vectors")


if __name__ == '__main__':
    main()
