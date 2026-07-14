"""
NEXUS AI TRADING SYSTEM - Chroma Client Module
Copyright © 2026 NEXUS QUANTUM LTD

This module implements a ChromaDB client for the NEXUS AI Trading System including:
- ChromaDB connection management
- Collection creation and management
- Vector storage and retrieval
- Metadata filtering and querying
- Similarity search with multiple metrics
- Batch operations for efficient processing
- Persistent storage with versioning
- Distributed vector indexing
- Approximate nearest neighbor search
- Document storage and retrieval
- Collection management
- Query optimization
- Embedding management
- Performance monitoring
- Export and import
- Backup and recovery
- Statistics and monitoring
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
import torch
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# ChromaDB imports
try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("ChromaDB not available. Install with: pip install chromadb")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/chroma_client.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class DistanceMetric(Enum):
    """Distance metrics for ChromaDB."""
    L2 = "l2"
    COSINE = "cosine"
    IP = "ip"  # Inner Product


class CollectionStatus(Enum):
    """Status of ChromaDB collections."""
    CREATED = "created"
    LOADING = "loading"
    READY = "ready"
    UPDATING = "updating"
    DELETING = "deleting"
    ERROR = "error"


@dataclass
class CollectionConfig:
    """Configuration for a ChromaDB collection."""
    name: str
    distance_metric: DistanceMetric = DistanceMetric.COSINE
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding_function: Optional[str] = None
    persistent: bool = True


@dataclass
class Document:
    """Document for ChromaDB storage."""
    id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class QueryResult:
    """Result from a ChromaDB query."""
    id: str
    content: str
    distance: float
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


@dataclass
class CollectionStats:
    """Statistics for a ChromaDB collection."""
    name: str
    count: int
    status: CollectionStatus
    dimension: int
    distance_metric: str
    metadata: Dict[str, Any]
    created_at: float
    updated_at: float
    memory_usage: int


# ============================================
# Chroma Client Implementation
# ============================================

class ChromaClient:
    """
    ChromaDB client for the NEXUS AI Trading System.
    
    This class provides a high-level interface to ChromaDB for vector storage
    and retrieval with support for multiple collections and advanced features.
    """
    
    def __init__(
        self,
        path: str = "./chroma_db",
        host: Optional[str] = None,
        port: Optional[int] = None,
        embedding_function: Optional[str] = None,
        persistent: bool = True,
        **kwargs
    ):
        """
        Initialize the ChromaDB client.
        
        Args:
            path: Path for persistent storage
            host: Host for remote connection
            port: Port for remote connection
            embedding_function: Default embedding function
            persistent: Whether to use persistent storage
            **kwargs: Additional arguments for ChromaDB
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB is not available. Install with: pip install chromadb")
        
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        
        # Initialize client
        if host and port:
            self.client = chromadb.HttpClient(host=host, port=port, **kwargs)
            logger.info(f"Connected to ChromaDB at {host}:{port}")
        else:
            self.client = chromadb.PersistentClient(path=str(self.path), **kwargs)
            logger.info(f"Initialized persistent ChromaDB at {self.path}")
        
        # Default embedding function
        if embedding_function:
            self.default_embedding_function = embedding_function
        else:
            # Use default embedding function
            try:
                self.default_embedding_function = embedding_functions.DefaultEmbeddingFunction()
                logger.info("Using default embedding function")
            except:
                self.default_embedding_function = None
                logger.warning("No embedding function available")
        
        # Collections
        self.collections: Dict[str, Any] = {}
        self.collection_configs: Dict[str, CollectionConfig] = {}
        self.collection_stats: Dict[str, CollectionStats] = {}
        
        # Load existing collections
        self._load_collections()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("ChromaClient initialized")
    
    # ============================================
    # Collection Management
    # ============================================
    
    def _load_collections(self) -> None:
        """Load existing collections."""
        try:
            existing_collections = self.client.list_collections()
            for collection_name in existing_collections:
                self.collections[collection_name] = self.client.get_collection(collection_name)
                self._update_collection_stats(collection_name)
            self.logger.info(f"Loaded {len(existing_collections)} collections")
        except Exception as e:
            self.logger.warning(f"Failed to load collections: {e}")
    
    def _update_collection_stats(self, collection_name: str) -> None:
        """Update statistics for a collection."""
        if collection_name not in self.collections:
            return
        
        collection = self.collections[collection_name]
        try:
            count = collection.count()
            metadata = collection.metadata
            dimension = metadata.get('dimension', 0) if metadata else 0
            
            self.collection_stats[collection_name] = CollectionStats(
                name=collection_name,
                count=count,
                status=CollectionStatus.READY,
                dimension=dimension,
                distance_metric=metadata.get('distance_metric', 'cosine') if metadata else 'cosine',
                metadata=metadata or {},
                created_at=metadata.get('created_at', time.time()) if metadata else time.time(),
                updated_at=metadata.get('updated_at', time.time()) if metadata else time.time(),
                memory_usage=count * dimension * 4 if dimension > 0 else 0,  # Approximate
            )
        except Exception as e:
            self.logger.warning(f"Failed to update collection stats: {e}")
    
    def create_collection(
        self,
        name: str,
        distance_metric: DistanceMetric = DistanceMetric.COSINE,
        embedding_function: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """
        Create a new collection.
        
        Args:
            name: Collection name
            distance_metric: Distance metric
            embedding_function: Embedding function to use
            metadata: Collection metadata
            **kwargs: Additional arguments for ChromaDB
            
        Returns:
            Collection object
        """
        if name in self.collections:
            self.logger.warning(f"Collection {name} already exists")
            return self.collections[name]
        
        try:
            # Prepare metadata
            collection_metadata = metadata or {}
            collection_metadata['distance_metric'] = distance_metric.value
            collection_metadata['created_at'] = time.time()
            collection_metadata['updated_at'] = time.time()
            collection_metadata['dimension'] = 0  # Will be updated on first insert
            
            # Create collection
            if embedding_function:
                collection = self.client.create_collection(
                    name=name,
                    metadata=collection_metadata,
                    embedding_function=embedding_function,
                    **kwargs
                )
            else:
                collection = self.client.create_collection(
                    name=name,
                    metadata=collection_metadata,
                    embedding_function=self.default_embedding_function,
                    **kwargs
                )
            
            self.collections[name] = collection
            self.collection_configs[name] = CollectionConfig(
                name=name,
                distance_metric=distance_metric,
                metadata=collection_metadata,
                embedding_function=embedding_function,
            )
            self._update_collection_stats(name)
            
            self.logger.info(f"Created collection: {name}")
            return collection
            
        except Exception as e:
            self.logger.error(f"Failed to create collection {name}: {e}")
            raise
    
    def get_collection(self, name: str) -> Optional[Any]:
        """
        Get a collection by name.
        
        Args:
            name: Collection name
            
        Returns:
            Collection object or None
        """
        if name in self.collections:
            return self.collections[name]
        
        try:
            collection = self.client.get_collection(name)
            self.collections[name] = collection
            self._update_collection_stats(name)
            return collection
        except:
            return None
    
    def delete_collection(self, name: str) -> bool:
        """
        Delete a collection.
        
        Args:
            name: Collection name
            
        Returns:
            True if deleted
        """
        if name not in self.collections:
            return False
        
        try:
            self.client.delete_collection(name)
            del self.collections[name]
            if name in self.collection_configs:
                del self.collection_configs[name]
            if name in self.collection_stats:
                del self.collection_stats[name]
            self.logger.info(f"Deleted collection: {name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete collection {name}: {e}")
            return False
    
    def list_collections(self) -> List[str]:
        """
        List all collections.
        
        Returns:
            List of collection names
        """
        return list(self.collections.keys())
    
    def get_collection_stats(self, name: str) -> Optional[CollectionStats]:
        """
        Get statistics for a collection.
        
        Args:
            name: Collection name
            
        Returns:
            Collection statistics or None
        """
        if name not in self.collections:
            return None
        
        self._update_collection_stats(name)
        return self.collection_stats.get(name)
    
    def get_all_stats(self) -> Dict[str, CollectionStats]:
        """
        Get statistics for all collections.
        
        Returns:
            Dictionary of collection statistics
        """
        for name in self.collections:
            self._update_collection_stats(name)
        return self.collection_stats
    
    # ============================================
    # Document Operations
    # ============================================
    
    def add(
        self,
        collection_name: str,
        documents: Union[str, List[str]],
        ids: Optional[Union[str, List[str]]] = None,
        embeddings: Optional[Union[List[float], List[List[float]]]] = None,
        metadatas: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
        **kwargs
    ) -> List[str]:
        """
        Add documents to a collection.
        
        Args:
            collection_name: Collection name
            documents: Document(s) to add
            ids: Document ID(s)
            embeddings: Document embedding(s)
            metadatas: Document metadata
            **kwargs: Additional arguments for ChromaDB
            
        Returns:
            List of document IDs
        """
        collection = self.get_collection(collection_name)
        if not collection:
            raise ValueError(f"Collection {collection_name} not found")
        
        # Convert to lists
        if isinstance(documents, str):
            documents = [documents]
        
        if ids is None:
            ids = [f"doc_{int(time.time())}_{i}_{hashlib.md5(doc.encode()).hexdigest()[:8]}" 
                   for i, doc in enumerate(documents)]
        elif isinstance(ids, str):
            ids = [ids]
        
        if embeddings is not None:
            if isinstance(embeddings, (list, tuple)) and len(embeddings) > 0 and isinstance(embeddings[0], (int, float)):
                embeddings = [embeddings]
        
        if metadatas is not None:
            if isinstance(metadatas, dict):
                metadatas = [metadatas]
        
        # Add timestamps to metadata
        if metadatas:
            for meta in metadatas:
                if meta is not None:
                    meta['timestamp'] = time.time()
        
        try:
            collection.add(
                documents=documents,
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                **kwargs
            )
            
            self._update_collection_stats(collection_name)
            self.logger.info(f"Added {len(documents)} documents to {collection_name}")
            return ids
            
        except Exception as e:
            self.logger.error(f"Failed to add documents to {collection_name}: {e}")
            raise
    
    def add_document(
        self,
        collection_name: str,
        document: Document,
        **kwargs
    ) -> str:
        """
        Add a single document to a collection.
        
        Args:
            collection_name: Collection name
            document: Document to add
            **kwargs: Additional arguments for ChromaDB
            
        Returns:
            Document ID
        """
        return self.add(
            collection_name=collection_name,
            documents=[document.content],
            ids=[document.id],
            embeddings=[document.embedding] if document.embedding is not None else None,
            metadatas=[document.metadata],
            **kwargs
        )[0]
    
    def query(
        self,
        collection_name: str,
        query_texts: Optional[Union[str, List[str]]] = None,
        query_embeddings: Optional[Union[List[float], List[List[float]]]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, List[Any]]:
        """
        Query a collection.
        
        Args:
            collection_name: Collection name
            query_texts: Query text(s)
            query_embeddings: Query embedding(s)
            n_results: Number of results to return
            where: Metadata filter
            where_document: Document filter
            include: What to include in results
            **kwargs: Additional arguments for ChromaDB
            
        Returns:
            Query results
        """
        collection = self.get_collection(collection_name)
        if not collection:
            raise ValueError(f"Collection {collection_name} not found")
        
        if query_texts is None and query_embeddings is None:
            raise ValueError("Either query_texts or query_embeddings must be provided")
        
        # Convert to lists
        if query_texts is not None and isinstance(query_texts, str):
            query_texts = [query_texts]
        
        if query_embeddings is not None and isinstance(query_embeddings, (list, tuple)) and len(query_embeddings) > 0 and isinstance(query_embeddings[0], (int, float)):
            query_embeddings = [query_embeddings]
        
        try:
            results = collection.query(
                query_texts=query_texts,
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
                where_document=where_document,
                include=include,
                **kwargs
            )
            
            self.logger.debug(f"Query completed: {len(results.get('ids', []))} results")
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to query {collection_name}: {e}")
            raise
    
    def search(
        self,
        collection_name: str,
        query: Union[str, List[float]],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[QueryResult]:
        """
        Search a collection with a query.
        
        Args:
            collection_name: Collection name
            query: Query text or embedding
            n_results: Number of results
            where: Metadata filter
            **kwargs: Additional arguments
            
        Returns:
            List of QueryResult objects
        """
        results = []
        query_texts = None
        query_embeddings = None
        
        if isinstance(query, str):
            query_texts = [query]
        else:
            query_embeddings = [query]
        
        try:
            raw_results = self.query(
                collection_name=collection_name,
                query_texts=query_texts,
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
                include=['documents', 'metadatas', 'distances', 'embeddings'],
                **kwargs
            )
            
            if raw_results and 'ids' in raw_results:
                ids = raw_results['ids'][0] if raw_results['ids'] else []
                documents = raw_results['documents'][0] if raw_results.get('documents') else []
                distances = raw_results['distances'][0] if raw_results.get('distances') else []
                metadatas = raw_results['metadatas'][0] if raw_results.get('metadatas') else []
                embeddings = raw_results.get('embeddings', [None])[0] if raw_results.get('embeddings') else []
                
                for i in range(len(ids)):
                    results.append(QueryResult(
                        id=ids[i],
                        content=documents[i] if i < len(documents) else '',
                        distance=distances[i] if i < len(distances) else 0,
                        metadata=metadatas[i] if i < len(metadatas) else {},
                        embedding=embeddings[i] if i < len(embeddings) else None,
                    ))
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to search {collection_name}: {e}")
            return []
    
    def get_document(
        self,
        collection_name: str,
        doc_id: str,
        include: Optional[List[str]] = None
    ) -> Optional[Document]:
        """
        Get a document by ID.
        
        Args:
            collection_name: Collection name
            doc_id: Document ID
            include: What to include
            
        Returns:
            Document or None
        """
        collection = self.get_collection(collection_name)
        if not collection:
            return None
        
        try:
            result = collection.get(
                ids=[doc_id],
                include=include or ['documents', 'metadatas', 'embeddings']
            )
            
            if result and result.get('ids') and len(result['ids']) > 0:
                idx = 0
                return Document(
                    id=result['ids'][idx],
                    content=result.get('documents', [''])[idx] if result.get('documents') else '',
                    embedding=result.get('embeddings', [None])[idx] if result.get('embeddings') else None,
                    metadata=result.get('metadatas', [{}])[idx] if result.get('metadatas') else {},
                    timestamp=result.get('metadatas', [{}])[idx].get('timestamp', time.time()) if result.get('metadatas') else time.time(),
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get document {doc_id}: {e}")
            return None
    
    def update_document(
        self,
        collection_name: str,
        doc_id: str,
        content: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> bool:
        """
        Update a document.
        
        Args:
            collection_name: Collection name
            doc_id: Document ID
            content: New content
            embedding: New embedding
            metadata: New metadata
            **kwargs: Additional arguments
            
        Returns:
            True if updated
        """
        collection = self.get_collection(collection_name)
        if not collection:
            return False
        
        try:
            # Get existing document
            existing = collection.get(ids=[doc_id], include=['documents', 'metadatas', 'embeddings'])
            if not existing or not existing.get('ids'):
                return False
            
            # Prepare updates
            update_kwargs = {'ids': [doc_id]}
            
            if content is not None:
                update_kwargs['documents'] = [content]
            
            if embedding is not None:
                update_kwargs['embeddings'] = [embedding]
            
            if metadata is not None:
                # Update metadata
                if 'timestamp' not in metadata:
                    metadata['timestamp'] = time.time()
                update_kwargs['metadatas'] = [metadata]
            
            if update_kwargs:
                collection.update(**update_kwargs)
                self._update_collection_stats(collection_name)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to update document {doc_id}: {e}")
            return False
    
    def delete_document(
        self,
        collection_name: str,
        doc_id: str,
        **kwargs
    ) -> bool:
        """
        Delete a document.
        
        Args:
            collection_name: Collection name
            doc_id: Document ID
            **kwargs: Additional arguments
            
        Returns:
            True if deleted
        """
        collection = self.get_collection(collection_name)
        if not collection:
            return False
        
        try:
            collection.delete(ids=[doc_id], **kwargs)
            self._update_collection_stats(collection_name)
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete document {doc_id}: {e}")
            return False
    
    def delete_documents(
        self,
        collection_name: str,
        where: Dict[str, Any],
        **kwargs
    ) -> int:
        """
        Delete documents by filter.
        
        Args:
            collection_name: Collection name
            where: Metadata filter
            **kwargs: Additional arguments
            
        Returns:
            Number of deleted documents
        """
        collection = self.get_collection(collection_name)
        if not collection:
            return 0
        
        try:
            # Get documents to delete
            result = collection.get(where=where, include=['ids'])
            if not result or not result.get('ids'):
                return 0
            
            ids_to_delete = result['ids']
            collection.delete(ids=ids_to_delete, **kwargs)
            self._update_collection_stats(collection_name)
            return len(ids_to_delete)
            
        except Exception as e:
            self.logger.error(f"Failed to delete documents: {e}")
            return 0
    
    # ============================================
    # Batch Operations
    # ============================================
    
    def batch_add(
        self,
        collection_name: str,
        documents: List[Document],
        batch_size: int = 100,
        **kwargs
    ) -> List[str]:
        """
        Add multiple documents in batches.
        
        Args:
            collection_name: Collection name
            documents: Documents to add
            batch_size: Batch size
            **kwargs: Additional arguments
            
        Returns:
            List of document IDs
        """
        all_ids = []
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            ids = self.add(
                collection_name=collection_name,
                documents=[doc.content for doc in batch],
                ids=[doc.id for doc in batch],
                embeddings=[doc.embedding for doc in batch if doc.embedding is not None] if any(doc.embedding is not None for doc in batch) else None,
                metadatas=[doc.metadata for doc in batch],
                **kwargs
            )
            all_ids.extend(ids)
        
        return all_ids
    
    def batch_query(
        self,
        collection_name: str,
        queries: List[Union[str, List[float]]],
        n_results: int = 10,
        **kwargs
    ) -> List[List[QueryResult]]:
        """
        Query multiple queries in batch.
        
        Args:
            collection_name: Collection name
            queries: List of queries
            n_results: Number of results per query
            **kwargs: Additional arguments
            
        Returns:
            List of query results
        """
        all_results = []
        
        for query in queries:
            results = self.search(
                collection_name=collection_name,
                query=query,
                n_results=n_results,
                **kwargs
            )
            all_results.append(results)
        
        return all_results
    
    # ============================================
    # Export and Import
    # ============================================
    
    def export_collection(
        self,
        collection_name: str,
        file_path: Optional[Union[str, Path]] = None,
        format: str = "json",
    ) -> Union[str, Dict[str, Any]]:
        """
        Export a collection.
        
        Args:
            collection_name: Collection name
            file_path: Path to save the export
            format: Export format ('json', 'pickle')
            
        Returns:
            Exported data or file path
        """
        collection = self.get_collection(collection_name)
        if not collection:
            raise ValueError(f"Collection {collection_name} not found")
        
        try:
            # Get all documents
            result = collection.get(include=['documents', 'metadatas', 'embeddings'])
            
            export_data = {
                'collection_name': collection_name,
                'config': self.collection_configs.get(collection_name, {}),
                'documents': [],
                'timestamp': time.time(),
            }
            
            if result and result.get('ids'):
                for i in range(len(result['ids'])):
                    doc = {
                        'id': result['ids'][i],
                        'content': result.get('documents', [''])[i] if result.get('documents') else '',
                        'metadata': result.get('metadatas', [{}])[i] if result.get('metadatas') else {},
                        'embedding': result.get('embeddings', [None])[i] if result.get('embeddings') else None,
                    }
                    export_data['documents'].append(doc)
            
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
            
        except Exception as e:
            self.logger.error(f"Failed to export collection {collection_name}: {e}")
            raise
    
    def import_collection(
        self,
        data: Union[str, Dict[str, Any], bytes],
        format: str = "json",
        collection_name: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Import a collection.
        
        Args:
            data: Data to import
            format: Data format ('json', 'pickle')
            collection_name: Collection name (if not in data)
            **kwargs: Additional arguments
            
        Returns:
            Collection name
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
            
            collection_name = collection_name or import_data.get('collection_name', f"imported_{int(time.time())}")
            
            # Create collection
            config = import_data.get('config', {})
            distance_metric = config.get('distance_metric', 'cosine')
            self.create_collection(
                name=collection_name,
                distance_metric=DistanceMetric(distance_metric),
                metadata=config.get('metadata', {}),
                **kwargs
            )
            
            # Add documents
            documents = import_data.get('documents', [])
            if documents:
                doc_objects = []
                for doc_data in documents:
                    doc_objects.append(Document(
                        id=doc_data.get('id', f"doc_{int(time.time())}_{i}"),
                        content=doc_data.get('content', ''),
                        embedding=doc_data.get('embedding'),
                        metadata=doc_data.get('metadata', {}),
                    ))
                
                self.batch_add(collection_name, doc_objects, **kwargs)
            
            self.logger.info(f"Imported {len(documents)} documents to {collection_name}")
            return collection_name
            
        except Exception as e:
            self.logger.error(f"Failed to import collection: {e}")
            raise
    
    # ============================================
    # Backup and Recovery
    # ============================================
    
    def create_backup(self, backup_dir: Optional[Union[str, Path]] = None) -> Dict[str, str]:
        """
        Create a backup of all collections.
        
        Args:
            backup_dir: Directory to save backups
            
        Returns:
            Dictionary of collection name to backup file path
        """
        backup_dir = Path(backup_dir) if backup_dir else self.path / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        backup_files = {}
        timestamp = int(time.time())
        
        for collection_name in self.collections:
            try:
                backup_file = backup_dir / f"{collection_name}_{timestamp}.json"
                self.export_collection(collection_name, file_path=backup_file, format="json")
                backup_files[collection_name] = str(backup_file)
            except Exception as e:
                self.logger.error(f"Failed to backup collection {collection_name}: {e}")
        
        self.logger.info(f"Created backup of {len(backup_files)} collections")
        return backup_files
    
    def restore_backup(
        self,
        backup_file: Union[str, Path],
        collection_name: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Restore from a backup.
        
        Args:
            backup_file: Backup file path
            collection_name: Collection name (override)
            **kwargs: Additional arguments
            
        Returns:
            Collection name
        """
        try:
            return self.import_collection(
                data=str(backup_file),
                format="json",
                collection_name=collection_name,
                **kwargs
            )
        except Exception as e:
            self.logger.error(f"Failed to restore backup: {e}")
            raise
    
    # ============================================
    # Maintenance and Monitoring
    # ============================================
    
    def optimize_collection(self, collection_name: str) -> bool:
        """
        Optimize a collection.
        
        Args:
            collection_name: Collection name
            
        Returns:
            True if optimized
        """
        # ChromaDB doesn't have explicit optimization, but we can re-index
        # This is a placeholder for future optimization
        self.logger.info(f"Optimizing collection {collection_name}")
        return True
    
    def get_collection_status(self, collection_name: str) -> Optional[CollectionStatus]:
        """
        Get collection status.
        
        Args:
            collection_name: Collection name
            
        Returns:
            Collection status or None
        """
        if collection_name not in self.collections:
            return None
        
        return CollectionStatus.READY
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Health check results
        """
        try:
            # Check if client is responsive
            self.client.list_collections()
            
            return {
                'status': 'healthy',
                'timestamp': time.time(),
                'collection_count': len(self.collections),
                'total_documents': sum(stats.count for stats in self.collection_stats.values()),
                'version': chromadb.__version__ if hasattr(chromadb, '__version__') else 'unknown',
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
            'collections': self.get_all_stats(),
            'total_collections': len(self.collections),
            'total_documents': sum(stats.count for stats in self.collection_stats.values()),
            'timestamp': time.time(),
        }
        return stats
    
    # ============================================
    # Shutdown
    # ============================================
    
    def shutdown(self) -> None:
        """Shutdown the ChromaDB client."""
        try:
            # In ChromaDB PersistentClient, persistence is automatic
            # This is a placeholder for cleanup
            self.logger.info("Shutting down ChromaClient")
        except Exception as e:
            self.logger.error(f"Shutdown error: {e}")


# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point for CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Chroma Client CLI')
    parser.add_argument('--command', choices=['list', 'stats', 'create', 'delete', 'query', 'add', 'backup', 'restore'],
                       required=True, help='Command to execute')
    parser.add_argument('--path', type=str, default='./chroma_db', help='ChromaDB path')
    parser.add_argument('--collection', type=str, help='Collection name')
    parser.add_argument('--file', type=str, help='File for import/export')
    parser.add_argument('--query', type=str, help='Query text')
    parser.add_argument('--n-results', type=int, default=10, help='Number of results')
    
    args = parser.parse_args()
    
    # Initialize client
    client = ChromaClient(path=args.path)
    
    if args.command == 'list':
        collections = client.list_collections()
        print("Collections:")
        for name in collections:
            stats = client.get_collection_stats(name)
            if stats:
                print(f"  {name}: {stats.count} documents")
            else:
                print(f"  {name}")
    
    elif args.command == 'stats':
        if args.collection:
            stats = client.get_collection_stats(args.collection)
            if stats:
                print(f"\nCollection: {stats.name}")
                print(f"  Documents: {stats.count}")
                print(f"  Status: {stats.status.value}")
                print(f"  Dimension: {stats.dimension}")
                print(f"  Distance: {stats.distance_metric}")
                print(f"  Memory: {stats.memory_usage / 1024:.2f} KB")
            else:
                print(f"Collection {args.collection} not found")
        else:
            all_stats = client.get_stats()
            print(f"\nTotal Collections: {all_stats['total_collections']}")
            print(f"Total Documents: {all_stats['total_documents']}")
            for name, stats in all_stats['collections'].items():
                print(f"\nCollection: {name}")
                print(f"  Documents: {stats.count}")
                print(f"  Status: {stats.status.value}")
    
    elif args.command == 'create':
        if not args.collection:
            print("Error: --collection required for create")
            return
        distance = input("Distance metric (l2/cosine/ip) [cosine]: ") or "cosine"
        client.create_collection(args.collection, distance_metric=DistanceMetric(distance))
        print(f"Collection {args.collection} created")
    
    elif args.command == 'delete':
        if not args.collection:
            print("Error: --collection required for delete")
            return
        if client.delete_collection(args.collection):
            print(f"Collection {args.collection} deleted")
        else:
            print(f"Failed to delete collection {args.collection}")
    
    elif args.command == 'query':
        if not args.collection:
            print("Error: --collection required for query")
            return
        if not args.query:
            query = input("Enter query: ")
        else:
            query = args.query
        
        results = client.search(args.collection, query, n_results=args.n_results)
        print(f"\nFound {len(results)} results:")
        for i, result in enumerate(results):
            print(f"{i+1}. ID: {result.id}")
            print(f"   Distance: {result.distance:.4f}")
            print(f"   Content: {result.content[:100]}..." if len(result.content) > 100 else f"   Content: {result.content}")
            print(f"   Metadata: {result.metadata}")
            print()
    
    elif args.command == 'add':
        if not args.collection:
            print("Error: --collection required for add")
            return
        content = input("Enter document content: ")
        doc_id = input("Enter document ID (optional): ") or None
        client.add(args.collection, documents=content, ids=doc_id)
        print(f"Added document")
    
    elif args.command == 'backup':
        backups = client.create_backup()
        print("Backups created:")
        for name, path in backups.items():
            print(f"  {name}: {path}")
    
    elif args.command == 'restore':
        if not args.file:
            print("Error: --file required for restore")
            return
        collection_name = client.restore_backup(args.file)
        print(f"Restored collection: {collection_name}")
    
    client.shutdown()


if __name__ == '__main__':
    main()
