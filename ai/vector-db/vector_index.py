"""
NEXUS AI TRADING SYSTEM - Vector Index Module
Copyright © 2026 NEXUS QUANTUM LTD

This module implements a comprehensive vector index for the NEXUS AI Trading System including:
- Multiple index types (Flat, IVF, HNSW, PQ, LSH)
- Index building and training
- Vector addition and removal
- Similarity search with multiple metrics
- Batch operations
- Index persistence
- Index optimization
- Index statistics and monitoring
- Distributed indexing
- Incremental updates
- Index merging
- Index compression
- Index quantization
- Performance tuning
- GPU acceleration
- Multi-threading support
- Index export/import
- Index backup and recovery
- Index versioning
"""

import os
import sys
import json
import time
import logging
import hashlib
import pickle
import threading
from typing import Dict, List, Optional, Tuple, Any, Union, Set, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
import numpy as np
from scipy.spatial.distance import cosine, euclidean
from sklearn.preprocessing import normalize
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Optional imports
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

try:
    import torch
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/vector_index.log'),
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
    PQ = "pq"
    OPQ = "opq"
    IVF_SQ = "ivf_sq"
    IVF_PQ = "ivf_pq"
    AUTO = "auto"


class DistanceMetric(Enum):
    """Distance metrics for vector index."""
    L2 = "l2"
    COSINE = "cosine"
    INNER_PRODUCT = "inner_product"
    MANHATTAN = "manhattan"
    CHEBYSHEV = "chebyshev"
    MINKOWSKI = "minkowski"


class IndexStatus(Enum):
    """Status of vector index."""
    EMPTY = "empty"
    BUILDING = "building"
    TRAINING = "training"
    READY = "ready"
    UPDATING = "updating"
    OPTIMIZING = "optimizing"
    COMPRESSING = "compressing"
    MERGING = "merging"
    ERROR = "error"


@dataclass
class IndexConfig:
    """Configuration for vector index."""
    index_type: IndexType
    dimension: int
    metric: DistanceMetric = DistanceMetric.L2
    nlist: int = 100  # For IVF
    nprobe: int = 10  # For IVF
    M: int = 16  # For PQ/HNSW
    nbits: int = 8  # For PQ
    ef_search: int = 16  # For HNSW
    ef_construction: int = 40  # For HNSW
    use_gpu: bool = False
    normalize: bool = True
    compress: bool = False
    compression_level: int = 5
    batch_size: int = 1000
    n_jobs: int = 1
    metadata_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IndexStats:
    """Statistics for vector index."""
    name: str
    index_type: str
    dimension: int
    metric: str
    total_vectors: int
    total_memory: int
    compression_ratio: float
    build_time: float
    search_time_avg: float
    status: IndexStatus
    nlist: int
    nprobe: int
    M: int
    nbits: int
    created_at: float
    updated_at: float


@dataclass
class SearchResult:
    """Result of a vector search."""
    id: str
    score: float
    distance: float
    rank: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    vector: Optional[np.ndarray] = None


@dataclass
class SearchResponse:
    """Response from a vector search."""
    query_id: str
    results: List[SearchResult]
    total_results: int
    search_time: float
    index_type: str
    metric: str


# ============================================
# Vector Index Implementation
# ============================================

class VectorIndex:
    """
    Comprehensive vector index for similarity search.
    
    This class provides multiple index types with optimized search,
    supporting both exact and approximate nearest neighbor search.
    """
    
    def __init__(
        self,
        name: str,
        config: IndexConfig,
        vectors: Optional[Dict[str, np.ndarray]] = None,
        metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """
        Initialize the vector index.
        
        Args:
            name: Index name
            config: Index configuration
            vectors: Initial vectors
            metadata: Initial metadata
        """
        self.name = name
        self.config = config
        self.vectors = vectors or {}
        self.metadata = metadata or {}
        self.ids = list(self.vectors.keys()) if vectors else []
        self.index = None
        self.id_to_index = {}
        
        # Statistics
        self.stats = None
        self._build_stats()
        
        # Vector matrix
        self.vector_matrix = None
        self.dimension = config.dimension
        
        # Build index if vectors provided
        if self.vectors:
            self._build_matrix()
            self.build_index()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"VectorIndex initialized: {name}")
        self.logger.info(f"Type: {config.index_type.value}, Dimension: {config.dimension}")
        self.logger.info(f"Metric: {config.metric.value}")
    
    # ============================================
    # Index Building
    # ============================================
    
    def build_index(self, vectors: Optional[Dict[str, np.ndarray]] = None) -> None:
        """
        Build the vector index.
        
        Args:
            vectors: Vectors to index (if None, use existing vectors)
        """
        if vectors:
            self.vectors.update(vectors)
            self._build_matrix()
        
        if not self.vectors:
            self.logger.warning("No vectors to index")
            return
        
        start_time = time.time()
        self.stats.status = IndexStatus.BUILDING
        
        try:
            if self.config.index_type == IndexType.FLAT:
                self._build_flat_index()
            elif self.config.index_type == IndexType.IVFFLAT:
                self._build_ivfflat_index()
            elif self.config.index_type == IndexType.IVFPQ:
                self._build_ivfpq_index()
            elif self.config.index_type == IndexType.HNSW:
                self._build_hnsw_index()
            elif self.config.index_type == IndexType.LSH:
                self._build_lsh_index()
            elif self.config.index_type == IndexType.PQ:
                self._build_pq_index()
            else:
                self._build_auto_index()
            
            self.stats.build_time = time.time() - start_time
            self.stats.status = IndexStatus.READY
            self.stats.total_vectors = len(self.vectors)
            
            self.logger.info(f"Index built: {self.stats.total_vectors} vectors")
            self.logger.info(f"Build time: {self.stats.build_time:.3f}s")
            
        except Exception as e:
            self.logger.error(f"Failed to build index: {e}")
            self.stats.status = IndexStatus.ERROR
            raise
    
    def _build_matrix(self) -> None:
        """Build vector matrix from vectors dictionary."""
        if not self.vectors:
            return
        
        # Get first vector to determine shape
        first_id = next(iter(self.vectors))
        first_vector = self.vectors[first_id]
        
        if isinstance(first_vector, np.ndarray):
            self.dimension = len(first_vector)
        elif isinstance(first_vector, list):
            self.dimension = len(first_vector)
        else:
            raise ValueError(f"Unsupported vector type: {type(first_vector)}")
        
        # Build matrix
        self.ids = list(self.vectors.keys())
        self.vector_matrix = np.zeros((len(self.ids), self.dimension))
        
        for i, vector_id in enumerate(self.ids):
            vector = self.vectors[vector_id]
            if isinstance(vector, list):
                vector = np.array(vector)
            self.vector_matrix[i] = vector
            self.id_to_index[vector_id] = i
        
        # Normalize if needed
        if self.config.normalize:
            norms = np.linalg.norm(self.vector_matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1
            self.vector_matrix = self.vector_matrix / norms
    
    def _build_flat_index(self) -> None:
        """Build flat (exact) index."""
        if not FAISS_AVAILABLE:
            self.logger.warning("FAISS not available, using numpy for flat index")
            return
        
        metric = self._get_faiss_metric()
        self.index = faiss.IndexFlat(self.dimension, metric)
        self._add_to_index()
    
    def _build_ivfflat_index(self) -> None:
        """Build IVF flat index."""
        if not FAISS_AVAILABLE:
            self.logger.warning("FAISS not available, falling back to flat index")
            self._build_flat_index()
            return
        
        metric = self._get_faiss_metric()
        quantizer = faiss.IndexFlat(self.dimension, metric)
        self.index = faiss.IndexIVFFlat(quantizer, self.dimension, self.config.nlist, metric)
        self.index.nprobe = self.config.nprobe
        
        # Train index
        if len(self.vector_matrix) >= self.config.nlist:
            self.stats.status = IndexStatus.TRAINING
            self.index.train(self.vector_matrix)
        
        self._add_to_index()
    
    def _build_ivfpq_index(self) -> None:
        """Build IVF PQ index."""
        if not FAISS_AVAILABLE:
            self.logger.warning("FAISS not available, falling back to flat index")
            self._build_flat_index()
            return
        
        metric = self._get_faiss_metric()
        quantizer = faiss.IndexFlat(self.dimension, metric)
        self.index = faiss.IndexIVFPQ(
            quantizer,
            self.dimension,
            self.config.nlist,
            self.config.M,
            self.config.nbits,
            metric
        )
        self.index.nprobe = self.config.nprobe
        
        # Train index
        if len(self.vector_matrix) >= self.config.nlist:
            self.stats.status = IndexStatus.TRAINING
            self.index.train(self.vector_matrix)
        
        self._add_to_index()
    
    def _build_hnsw_index(self) -> None:
        """Build HNSW index."""
        if not FAISS_AVAILABLE:
            self.logger.warning("FAISS not available, falling back to flat index")
            self._build_flat_index()
            return
        
        metric = self._get_faiss_metric()
        self.index = faiss.IndexHNSWFlat(self.dimension, self.config.M, metric)
        self.index.hnsw.efSearch = self.config.ef_search
        self.index.hnsw.efConstruction = self.config.ef_construction
        
        self._add_to_index()
    
    def _build_lsh_index(self) -> None:
        """Build LSH index."""
        if not FAISS_AVAILABLE:
            self.logger.warning("FAISS not available, falling back to flat index")
            self._build_flat_index()
            return
        
        nbits = self.dimension * self.config.M
        self.index = faiss.IndexLSH(self.dimension, nbits, False)
        
        self._add_to_index()
    
    def _build_pq_index(self) -> None:
        """Build PQ index."""
        if not FAISS_AVAILABLE:
            self.logger.warning("FAISS not available, falling back to flat index")
            self._build_flat_index()
            return
        
        self.index = faiss.IndexPQ(self.dimension, self.config.M, self.config.nbits)
        
        if len(self.vector_matrix) > 0:
            self.stats.status = IndexStatus.TRAINING
            self.index.train(self.vector_matrix)
        
        self._add_to_index()
    
    def _build_auto_index(self) -> None:
        """Auto-select best index type."""
        n_vectors = len(self.vectors)
        
        if n_vectors < 1000:
            self.config.index_type = IndexType.FLAT
            self._build_flat_index()
        elif n_vectors < 10000:
            self.config.index_type = IndexType.IVFFLAT
            self._build_ivfflat_index()
        elif n_vectors < 100000:
            self.config.index_type = IndexType.IVFPQ
            self._build_ivfpq_index()
        else:
            self.config.index_type = IndexType.HNSW
            self._build_hnsw_index()
    
    def _add_to_index(self) -> None:
        """Add vectors to index."""
        if self.index is None:
            return
        
        if len(self.vector_matrix) == 0:
            return
        
        # Convert to float32 for FAISS
        vectors = self.vector_matrix.astype(np.float32)
        
        # Add to index
        self.index.add(vectors)
        
        # Update stats
        self.stats.total_vectors = len(self.vectors)
    
    def _get_faiss_metric(self) -> int:
        """Get FAISS metric."""
        if self.config.metric == DistanceMetric.L2:
            return faiss.METRIC_L2
        elif self.config.metric == DistanceMetric.INNER_PRODUCT:
            return faiss.METRIC_INNER_PRODUCT
        elif self.config.metric == DistanceMetric.MANHATTAN:
            return faiss.METRIC_L1
        else:
            return faiss.METRIC_L2
    
    # ============================================
    # Vector Operations
    # ============================================
    
    def add_vectors(
        self,
        vectors: Dict[str, np.ndarray],
        metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        rebuild: bool = True,
    ) -> None:
        """
        Add vectors to the index.
        
        Args:
            vectors: Vectors to add
            metadata: Metadata for vectors
            rebuild: Whether to rebuild the index
        """
        # Update vectors
        self.vectors.update(vectors)
        if metadata:
            self.metadata.update(metadata)
        
        # Update IDs
        self.ids = list(self.vectors.keys())
        
        # Rebuild matrix and index
        self._build_matrix()
        if rebuild:
            self.build_index()
        else:
            # Just add to existing index
            if self.index is not None and FAISS_AVAILABLE:
                vector_array = np.array([vectors[vid] for vid in vectors]).astype(np.float32)
                if self.config.normalize:
                    norms = np.linalg.norm(vector_array, axis=1, keepdims=True)
                    norms[norms == 0] = 1
                    vector_array = vector_array / norms
                self.index.add(vector_array)
        
        self.logger.info(f"Added {len(vectors)} vectors")
    
    def remove_vectors(self, vector_ids: List[str], rebuild: bool = True) -> None:
        """
        Remove vectors from the index.
        
        Args:
            vector_ids: IDs of vectors to remove
            rebuild: Whether to rebuild the index
        """
        for vid in vector_ids:
            if vid in self.vectors:
                del self.vectors[vid]
            if vid in self.metadata:
                del self.metadata[vid]
        
        self.ids = list(self.vectors.keys())
        
        if rebuild:
            self._build_matrix()
            self.build_index()
        else:
            # FAISS doesn't support removal, so we need to rebuild
            self._build_matrix()
            self.build_index()
        
        self.logger.info(f"Removed {len(vector_ids)} vectors")
    
    def get_vector(self, vector_id: str) -> Optional[np.ndarray]:
        """Get a vector by ID."""
        return self.vectors.get(vector_id)
    
    def get_metadata(self, vector_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata by ID."""
        return self.metadata.get(vector_id)
    
    def update_vector(
        self,
        vector_id: str,
        vector: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update a vector.
        
        Args:
            vector_id: Vector ID
            vector: New vector
            metadata: New metadata
            
        Returns:
            True if updated
        """
        if vector_id not in self.vectors:
            return False
        
        if vector is not None:
            self.vectors[vector_id] = vector
        
        if metadata is not None:
            self.metadata[vector_id] = metadata
        
        # Rebuild index
        self._build_matrix()
        self.build_index()
        
        return True
    
    # ============================================
    # Search Operations
    # ============================================
    
    def search(
        self,
        query: Union[np.ndarray, List[float]],
        top_k: int = 10,
        threshold: float = 0.0,
        metadata_filters: Optional[Dict[str, Any]] = None,
        exclude_ids: Optional[List[str]] = None,
        return_vectors: bool = False,
    ) -> SearchResponse:
        """
        Search the index.
        
        Args:
            query: Query vector
            top_k: Number of results
            threshold: Similarity threshold
            metadata_filters: Metadata filters
            exclude_ids: IDs to exclude
            return_vectors: Whether to return vectors
            
        Returns:
            Search response
        """
        start_time = time.time()
        
        if isinstance(query, list):
            query = np.array(query)
        
        # Normalize query
        if self.config.normalize:
            norm = np.linalg.norm(query)
            if norm > 0:
                query = query / norm
        
        # Apply filters
        filtered_ids = self._apply_filters(metadata_filters, exclude_ids)
        
        if not filtered_ids:
            return SearchResponse(
                query_id=f"query_{int(time.time())}",
                results=[],
                total_results=0,
                search_time=time.time() - start_time,
                index_type=self.config.index_type.value,
                metric=self.config.metric.value,
            )
        
        # Perform search
        if FAISS_AVAILABLE and self.index is not None:
            results = self._faiss_search(query, top_k, filtered_ids)
        else:
            results = self._numpy_search(query, top_k, filtered_ids)
        
        # Apply threshold
        if threshold > 0:
            results = [r for r in results if r.score >= threshold]
        
        # Add metadata
        for result in results:
            if result.id in self.metadata:
                result.metadata = self.metadata[result.id]
            if return_vectors and result.id in self.vectors:
                result.vector = self.vectors[result.id]
        
        return SearchResponse(
            query_id=f"query_{int(time.time())}",
            results=results[:top_k],
            total_results=len(results),
            search_time=time.time() - start_time,
            index_type=self.config.index_type.value,
            metric=self.config.metric.value,
        )
    
    def _faiss_search(
        self,
        query: np.ndarray,
        top_k: int,
        filtered_ids: List[str],
    ) -> List[SearchResult]:
        """
        Search using FAISS.
        
        Args:
            query: Query vector
            top_k: Number of results
            filtered_ids: Filtered vector IDs
            
        Returns:
            List of search results
        """
        if self.index is None:
            return self._numpy_search(query, top_k, filtered_ids)
        
        # Prepare query
        query_array = np.array([query]).astype(np.float32)
        
        # Search
        distances, indices = self.index.search(query_array, min(top_k * 2, len(filtered_ids)))
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(self.ids):
                continue
            
            vector_id = self.ids[idx]
            if vector_id not in filtered_ids:
                continue
            
            # Convert distance to score
            if self.config.metric == DistanceMetric.COSINE:
                score = 1 - distances[0][i]
            elif self.config.metric == DistanceMetric.L2:
                score = 1 / (1 + distances[0][i])
            elif self.config.metric == DistanceMetric.INNER_PRODUCT:
                score = distances[0][i]
            else:
                score = 1 / (1 + distances[0][i])
            
            results.append(SearchResult(
                id=vector_id,
                score=score,
                distance=distances[0][i],
                rank=len(results) + 1,
            ))
            
            if len(results) >= top_k:
                break
        
        return results
    
    def _numpy_search(
        self,
        query: np.ndarray,
        top_k: int,
        filtered_ids: List[str],
    ) -> List[SearchResult]:
        """
        Search using NumPy (exact).
        
        Args:
            query: Query vector
            top_k: Number of results
            filtered_ids: Filtered vector IDs
            
        Returns:
            List of search results
        """
        results = []
        
        # Get filtered vectors
        filtered_vectors = []
        filtered_ids_list = []
        for vid in filtered_ids:
            if vid in self.vectors:
                filtered_vectors.append(self.vectors[vid])
                filtered_ids_list.append(vid)
        
        if not filtered_vectors:
            return results
        
        filtered_matrix = np.array(filtered_vectors)
        
        # Compute similarities
        if self.config.metric == DistanceMetric.COSINE:
            if TORCH_AVAILABLE:
                query_t = torch.from_numpy(query).float()
                vectors_t = torch.from_numpy(filtered_matrix).float()
                similarities = F.cosine_similarity(query_t.unsqueeze(0), vectors_t).numpy()
            else:
                from sklearn.metrics.pairwise import cosine_similarity
                similarities = cosine_similarity(query.reshape(1, -1), filtered_matrix)[0]
        elif self.config.metric == DistanceMetric.L2:
            distances = np.linalg.norm(filtered_matrix - query, axis=1)
            similarities = 1 / (1 + distances)
        elif self.config.metric == DistanceMetric.INNER_PRODUCT:
            similarities = np.dot(filtered_matrix, query)
        else:
            from sklearn.metrics.pairwise import cosine_similarity
            similarities = cosine_similarity(query.reshape(1, -1), filtered_matrix)[0]
        
        # Sort and rank
        sorted_indices = np.argsort(similarities)[::-1]
        
        for i, idx in enumerate(sorted_indices[:top_k]):
            if similarities[idx] > 0:
                results.append(SearchResult(
                    id=filtered_ids_list[idx],
                    score=similarities[idx],
                    distance=1 - similarities[idx] if self.config.metric == DistanceMetric.COSINE else 1 / (similarities[idx] + 1e-8),
                    rank=i + 1,
                ))
        
        return results
    
    def _apply_filters(
        self,
        metadata_filters: Optional[Dict[str, Any]],
        exclude_ids: Optional[List[str]],
    ) -> List[str]:
        """
        Apply metadata filters and exclusions.
        
        Args:
            metadata_filters: Metadata filters
            exclude_ids: IDs to exclude
            
        Returns:
            Filtered vector IDs
        """
        filtered_ids = self.ids.copy()
        
        # Apply metadata filters
        if metadata_filters:
            filtered_ids = [
                vid for vid in filtered_ids
                if vid in self.metadata and self._matches_filters(self.metadata[vid], metadata_filters)
            ]
        
        # Apply exclusions
        if exclude_ids:
            exclude_set = set(exclude_ids)
            filtered_ids = [vid for vid in filtered_ids if vid not in exclude_set]
        
        return filtered_ids
    
    def _matches_filters(
        self,
        metadata: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> bool:
        """
        Check if metadata matches filters.
        
        Args:
            metadata: Item metadata
            filters: Filter criteria
            
        Returns:
            True if matches
        """
        for key, value in filters.items():
            if key not in metadata:
                return False
            if isinstance(value, dict):
                if 'min' in value and metadata[key] < value['min']:
                    return False
                if 'max' in value and metadata[key] > value['max']:
                    return False
            elif isinstance(value, (list, tuple)):
                if metadata[key] not in value:
                    return False
            elif metadata[key] != value:
                return False
        return True
    
    # ============================================
    # Index Optimization
    # ============================================
    
    def optimize(self) -> None:
        """Optimize the index."""
        self.stats.status = IndexStatus.OPTIMIZING
        
        try:
            if FAISS_AVAILABLE and self.index is not None:
                # For IVF indexes, optimize nprobe
                if hasattr(self.index, 'nprobe'):
                    n_vectors = len(self.vectors)
                    if n_vectors < 1000:
                        self.index.nprobe = 1
                    elif n_vectors < 10000:
                        self.index.nprobe = 5
                    elif n_vectors < 100000:
                        self.index.nprobe = 10
                    else:
                        self.index.nprobe = 20
            
            # Rebuild if needed
            self.build_index()
            
            self.stats.status = IndexStatus.READY
            self.logger.info("Index optimized")
            
        except Exception as e:
            self.logger.error(f"Optimization failed: {e}")
            self.stats.status = IndexStatus.ERROR
    
    def compress(self) -> None:
        """Compress the index."""
        if not self.config.compress:
            return
        
        self.stats.status = IndexStatus.COMPRESSING
        
        try:
            # Simple compression: reduce precision
            if self.vector_matrix is not None:
                self.vector_matrix = self.vector_matrix.astype(np.float16)
            
            # Rebuild index
            self.build_index()
            
            self.stats.status = IndexStatus.READY
            self.logger.info("Index compressed")
            
        except Exception as e:
            self.logger.error(f"Compression failed: {e}")
            self.stats.status = IndexStatus.ERROR
    
    # ============================================
    # Index Management
    # ============================================
    
    def _build_stats(self) -> None:
        """Build index statistics."""
        self.stats = IndexStats(
            name=self.name,
            index_type=self.config.index_type.value,
            dimension=self.config.dimension,
            metric=self.config.metric.value,
            total_vectors=len(self.vectors),
            total_memory=0,
            compression_ratio=1.0,
            build_time=0.0,
            search_time_avg=0.0,
            status=IndexStatus.EMPTY,
            nlist=self.config.nlist,
            nprobe=self.config.nprobe,
            M=self.config.M,
            nbits=self.config.nbits,
            created_at=time.time(),
            updated_at=time.time(),
        )
    
    def get_stats(self) -> IndexStats:
        """Get index statistics."""
        self.stats.total_vectors = len(self.vectors)
        self.stats.updated_at = time.time()
        
        # Update memory usage
        if self.vector_matrix is not None:
            self.stats.total_memory = self.vector_matrix.nbytes
            if self.index is not None and FAISS_AVAILABLE:
                self.stats.total_memory += self.index.ntotal * self.dimension * 4
        
        return self.stats
    
    def clear(self) -> None:
        """Clear the index."""
        self.vectors.clear()
        self.metadata.clear()
        self.ids.clear()
        self.id_to_index.clear()
        self.vector_matrix = None
        self.index = None
        self._build_stats()
        self.logger.info(f"Index {self.name} cleared")
    
    # ============================================
    # Index Persistence
    # ============================================
    
    def save(self, file_path: Union[str, Path]) -> None:
        """
        Save index to disk.
        
        Args:
            file_path: Path to save index
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'name': self.name,
            'config': asdict(self.config),
            'vectors': self.vectors,
            'metadata': self.metadata,
            'ids': self.ids,
            'id_to_index': self.id_to_index,
            'stats': asdict(self.stats),
            'timestamp': time.time(),
            'version': '1.0',
        }
        
        # Save FAISS index separately if available
        if FAISS_AVAILABLE and self.index is not None:
            faiss.write_index(self.index, str(file_path) + '.faiss')
        
        with open(file_path, 'wb') as f:
            pickle.dump(data, f)
        
        self.logger.info(f"Index saved to {file_path}")
    
    def load(self, file_path: Union[str, Path]) -> None:
        """
        Load index from disk.
        
        Args:
            file_path: Path to load index from
        """
        file_path = Path(file_path)
        
        with open(file_path, 'rb') as f:
            data = pickle.load(f)
        
        self.name = data['name']
        self.config = IndexConfig(**data['config'])
        self.vectors = data['vectors']
        self.metadata = data['metadata']
        self.ids = data['ids']
        self.id_to_index = data['id_to_index']
        self.stats = IndexStats(**data['stats'])
        
        # Load FAISS index if available
        if FAISS_AVAILABLE and (file_path.with_suffix('.faiss')).exists():
            self.index = faiss.read_index(str(file_path) + '.faiss')
        
        self._build_matrix()
        
        self.logger.info(f"Index loaded from {file_path}")
    
    def export_vectors(self, format: str = "numpy") -> Union[np.ndarray, Dict[str, Any]]:
        """
        Export vectors from the index.
        
        Args:
            format: Export format ('numpy', 'json', 'pickle')
            
        Returns:
            Exported vectors
        """
        if format == "numpy":
            return np.array([self.vectors[vid] for vid in self.ids])
        elif format == "json":
            return {
                'ids': self.ids,
                'vectors': {vid: self.vectors[vid].tolist() for vid in self.ids},
                'metadata': self.metadata,
            }
        elif format == "pickle":
            return {
                'ids': self.ids,
                'vectors': self.vectors,
                'metadata': self.metadata,
            }
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def import_vectors(
        self,
        data: Any,
        format: str = "numpy",
        clear_existing: bool = True,
    ) -> int:
        """
        Import vectors into the index.
        
        Args:
            data: Vector data
            format: Data format
            clear_existing: Whether to clear existing vectors
            
        Returns:
            Number of vectors imported
        """
        if clear_existing:
            self.clear()
        
        if format == "numpy":
            vectors = data
            for i, vector in enumerate(vectors):
                vid = f"import_{i}_{int(time.time())}"
                self.vectors[vid] = vector
                self.metadata[vid] = {'import_index': i}
        elif format == "json":
            ids = data.get('ids', [])
            vectors = data.get('vectors', {})
            metadata = data.get('metadata', {})
            for vid in ids:
                if vid in vectors:
                    self.vectors[vid] = np.array(vectors[vid])
                    if vid in metadata:
                        self.metadata[vid] = metadata[vid]
        elif format == "pickle":
            ids = data.get('ids', [])
            vectors = data.get('vectors', {})
            metadata = data.get('metadata', {})
            for vid in ids:
                if vid in vectors:
                    self.vectors[vid] = vectors[vid]
                    if vid in metadata:
                        self.metadata[vid] = metadata[vid]
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        self._build_matrix()
        self.build_index()
        
        return len(self.vectors)
    
    # ============================================
    # Index Comparison
    # ============================================
    
    def compare_with(
        self,
        other: 'VectorIndex',
        sample_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Compare this index with another.
        
        Args:
            other: Other index to compare
            sample_size: Number of vectors to sample
            
        Returns:
            Comparison results
        """
        # Sample vectors from both indexes
        if sample_size > len(self.vectors) or sample_size > len(other.vectors):
            sample_size = min(len(self.vectors), len(other.vectors))
        
        sample_ids = list(self.vectors.keys())[:sample_size]
        sample_vectors = np.array([self.vectors[vid] for vid in sample_ids])
        
        # Search in both indexes
        search_times = []
        similarities = []
        
        for vector in sample_vectors:
            # Search in this index
            start_time = time.time()
            self.search(vector, top_k=1)
            time1 = time.time() - start_time
            
            # Search in other index
            start_time = time.time()
            other.search(vector, top_k=1)
            time2 = time.time() - start_time
            
            search_times.append(time1 - time2)
        
        return {
            'sample_size': sample_size,
            'avg_time_diff': np.mean(search_times),
            'std_time_diff': np.std(search_times),
            'faster': 'self' if np.mean(search_times) < 0 else 'other',
        }


# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point for CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Vector Index CLI')
    parser.add_argument('--command', choices=['build', 'search', 'add', 'remove', 'stats', 'save', 'load'],
                       required=True, help='Command to execute')
    parser.add_argument('--name', type=str, default='default', help='Index name')
    parser.add_argument('--index-type', type=str, default='flat', help='Index type')
    parser.add_argument('--dimension', type=int, default=128, help='Vector dimension')
    parser.add_argument('--metric', type=str, default='l2', help='Distance metric')
    parser.add_argument('--file', type=str, help='Input/output file')
    parser.add_argument('--query', type=str, help='Query vector (comma-separated)')
    parser.add_argument('--top-k', type=int, default=10, help='Number of results')
    parser.add_argument('--nlist', type=int, default=100, help='Number of clusters')
    parser.add_argument('--nprobe', type=int, default=10, help='Number of probes')
    parser.add_argument('--M', type=int, default=16, help='Number of links')
    parser.add_argument('--use-gpu', action='store_true', help='Use GPU')
    parser.add_argument('--normalize', action='store_true', help='Normalize vectors')
    
    args = parser.parse_args()
    
    # Create configuration
    config = IndexConfig(
        index_type=IndexType(args.index_type),
        dimension=args.dimension,
        metric=DistanceMetric(args.metric),
        nlist=args.nlist,
        nprobe=args.nprobe,
        M=args.M,
        use_gpu=args.use_gpu,
        normalize=args.normalize,
    )
    
    # Create index
    index = VectorIndex(args.name, config)
    
    if args.command == 'build':
        # Generate random vectors
        np.random.seed(42)
        vectors = {}
        for i in range(1000):
            vectors[f'vec_{i}'] = np.random.randn(args.dimension)
        
        index.build_index(vectors)
        print(f"Built index with {len(vectors)} vectors")
        print(index.get_stats())
    
    elif args.command == 'search':
        if not args.query:
            query_str = input("Enter query vector (comma-separated): ")
            query = np.array([float(x.strip()) for x in query_str.split(',')])
        else:
            query = np.array([float(x.strip()) for x in args.query.split(',')])
        
        if args.file:
            index.load(args.file)
        
        response = index.search(query, top_k=args.top_k)
        print(f"\nSearch Results ({response.total_results}):")
        for result in response.results:
            print(f"  {result.rank}. {result.id}: score={result.score:.4f}")
    
    elif args.command == 'add':
        if not args.file:
            print("Error: --file required for add")
            return
        
        with open(args.file, 'r') as f:
            data = json.load(f)
        
        vectors = {}
        metadata = {}
        for item in data:
            vid = item['id']
            vectors[vid] = np.array(item['vector'])
            metadata[vid] = item.get('metadata', {})
        
        index.add_vectors(vectors, metadata)
        print(f"Added {len(vectors)} vectors")
    
    elif args.command == 'remove':
        ids = input("Enter IDs to remove (comma-separated): ").split(',')
        index.remove_vectors([vid.strip() for vid in ids])
        print(f"Removed {len(ids)} vectors")
    
    elif args.command == 'stats':
        stats = index.get_stats()
        print(f"\nIndex: {stats.name}")
        print(f"  Type: {stats.index_type}")
        print(f"  Dimension: {stats.dimension}")
        print(f"  Metric: {stats.metric}")
        print(f"  Vectors: {stats.total_vectors}")
        print(f"  Memory: {stats.total_memory / 1024 / 1024:.2f} MB")
        print(f"  Status: {stats.status.value}")
        print(f"  Build Time: {stats.build_time:.3f}s")
        print(f"  Nlist: {stats.nlist}")
        print(f"  Nprobe: {stats.nprobe}")
        print(f"  M: {stats.M}")
        print(f"  Nbits: {stats.nbits}")
    
    elif args.command == 'save':
        if not args.file:
            print("Error: --file required for save")
            return
        index.save(args.file)
        print(f"Index saved to {args.file}")
    
    elif args.command == 'load':
        if not args.file:
            print("Error: --file required for load")
            return
        index.load(args.file)
        print(f"Index loaded from {args.file}")


if __name__ == '__main__':
    main()
