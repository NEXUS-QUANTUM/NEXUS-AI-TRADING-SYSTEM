Parfait ! Passons maintenant à l'implémentation du module **Vector Database** pour le système d'IA. Ce module est crucial pour le stockage et la recherche de vecteurs d'embedding, permettant au système de faire des recherches sémantiques, de la mémoire à long terme, et de l'analyse de similarité.

## **ai/vector-db/__init__.py - Module Vector Database**

```python
# ai/vector-db/__init__.py
"""
NEXUS AI TRADING SYSTEM - Vector Database Module
Copyright © 2026 NEXUS QUANTUM LTD

Ce module fournit une interface unifiée pour les bases de données vectorielles,
supportant ChromaDB, Pinecone, Weaviate et Milvus pour le stockage et la
recherche d'embeddings vectoriels.

Features:
- Stockage et recherche de vecteurs d'embedding
- Indexation sémantique des données de trading
- Recherche de similarité pour les patterns de marché
- Mémoire à long terme pour les agents IA
- Cache vectoriel pour les prédictions
"""

import logging
import os
from typing import Optional, Dict, Any, List, Union, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import uuid

# Configuration du logging
logger = logging.getLogger(__name__)

# ============================================================
# TYPES & ÉNUMÉRATIONS
# ============================================================

class VectorDBType(Enum):
    """Types de bases de données vectorielles supportées"""
    CHROMA = "chroma"
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    MILVUS = "milvus"
    QDRANT = "qdrant"
    FAISS = "faiss"  # Local / Mémoire


class DistanceMetric(Enum):
    """Métriques de distance pour la recherche de similarité"""
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dotproduct"
    L2 = "l2"
    INNER_PRODUCT = "innerproduct"


class IndexType(Enum):
    """Types d'index pour l'optimisation des recherches"""
    FLAT = "flat"  # Recherche exhaustive
    IVF_FLAT = "ivf_flat"  # Index IVF
    IVF_SQ8 = "ivf_sq8"  # Index IVF avec quantification scalaire
    HNSW = "hnsw"  # Hierarchical Navigable Small World
    ANNOY = "annoy"  # Approximate Nearest Neighbors Oh Yeah


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class VectorDocument:
    """
    Document vectoriel avec métadonnées pour le stockage en base de données
    vectorielle.
    
    Attributes:
        id: Identifiant unique du document
        vector: Vecteur d'embedding (liste de floats)
        metadata: Métadonnées associées (dict)
        content: Contenu textuel optionnel
        timestamp: Timestamp de création
        embedding_model: Modèle d'embedding utilisé
        namespace: Espace de noms pour l'organisation
    """
    id: str
    vector: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    content: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    embedding_model: Optional[str] = None
    namespace: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit le document en dictionnaire"""
        return {
            'id': self.id,
            'vector': self.vector,
            'metadata': self.metadata,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'embedding_model': self.embedding_model,
            'namespace': self.namespace,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VectorDocument':
        """Crée un document à partir d'un dictionnaire"""
        return cls(
            id=data['id'],
            vector=data['vector'],
            metadata=data.get('metadata', {}),
            content=data.get('content'),
            timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now(),
            embedding_model=data.get('embedding_model'),
            namespace=data.get('namespace'),
        )


@dataclass
class SearchResult:
    """
    Résultat d'une recherche de similarité dans la base vectorielle.
    
    Attributes:
        document: Document vectoriel trouvé
        score: Score de similarité (0-1)
        distance: Distance calculée
        rank: Rang dans les résultats
    """
    document: VectorDocument
    score: float
    distance: float
    rank: int

    def to_dict(self) -> Dict[str, Any]:
        """Convertit le résultat en dictionnaire"""
        return {
            'document': self.document.to_dict(),
            'score': self.score,
            'distance': self.distance,
            'rank': self.rank,
        }


@dataclass
class VectorIndexConfig:
    """
    Configuration pour l'index vectoriel.
    
    Attributes:
        index_type: Type d'index à utiliser
        metric: Métrique de distance
        dimension: Dimension des vecteurs
        nlist: Nombre de clusters (pour IVF)
        nprobe: Nombre de clusters à explorer
        ef_construction: Taille de la dynamique de construction (HNSW)
        ef_search: Taille de la dynamique de recherche (HNSW)
        M: Nombre de connexions par couche (HNSW)
        max_elements: Nombre maximum d'éléments
    """
    index_type: IndexType = IndexType.FLAT
    metric: DistanceMetric = DistanceMetric.COSINE
    dimension: Optional[int] = None
    nlist: int = 100
    nprobe: int = 10
    ef_construction: int = 200
    ef_search: int = 100
    M: int = 16
    max_elements: int = 1000000


# ============================================================
# CLASSE PRINCIPALE - VectorDBManager
# ============================================================

class VectorDBManager:
    """
    Gestionnaire unifié des bases de données vectorielles.
    
    Cette classe fournit une interface abstraite pour interagir avec
    différentes implémentations de bases de données vectorielles,
    permettant une migration et une expérimentation faciles.
    
    Example:
        ```python
        # Initialisation avec ChromaDB
        manager = VectorDBManager(
            db_type=VectorDBType.CHROMA,
            collection_name="trading_patterns"
        )
        
        # Ajout d'un document
        doc = VectorDocument(
            id="pattern_001",
            vector=[0.1, 0.2, ...],
            metadata={"type": "bullish", "confidence": 0.95}
        )
        manager.add_document(doc)
        
        # Recherche de similarité
        results = manager.search(
            query_vector=[0.15, 0.25, ...],
            top_k=5,
            filter={"type": "bullish"}
        )
        ```
    """
    
    def __init__(
        self,
        db_type: VectorDBType = VectorDBType.CHROMA,
        collection_name: str = "nexus_vectors",
        config: Optional[VectorIndexConfig] = None,
        connection_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Initialise le gestionnaire de base de données vectorielle.
        
        Args:
            db_type: Type de base de données vectorielle
            collection_name: Nom de la collection / index
            config: Configuration de l'index
            connection_params: Paramètres de connexion spécifiques
            **kwargs: Paramètres additionnels
        """
        self.db_type = db_type
        self.collection_name = collection_name
        self.config = config or VectorIndexConfig()
        self.connection_params = connection_params or {}
        self._client = None
        self._initialized = False
        
        # Cache de résultats
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_size = kwargs.get('cache_size', 1000)
        self._cache_ttl = kwargs.get('cache_ttl', 300)  # 5 minutes
        
        # Statistiques
        self._stats = {
            'documents_added': 0,
            'documents_updated': 0,
            'documents_deleted': 0,
            'search_count': 0,
            'avg_search_time': 0,
            'cache_hits': 0,
            'cache_misses': 0,
        }
        
        logger.info(f"VectorDBManager initialisé avec {db_type.value}")
        self._init_client()
    
    # ============================================================
    # MÉTHODES PRIVÉES
    # ============================================================
    
    def _init_client(self):
        """Initialise le client selon le type de base de données"""
        if self._initialized:
            return
        
        try:
            if self.db_type == VectorDBType.CHROMA:
                self._init_chroma()
            elif self.db_type == VectorDBType.PINECONE:
                self._init_pinecone()
            elif self.db_type == VectorDBType.WEAVIATE:
                self._init_weaviate()
            elif self.db_type == VectorDBType.MILVUS:
                self._init_milvus()
            elif self.db_type == VectorDBType.QDRANT:
                self._init_qdrant()
            elif self.db_type == VectorDBType.FAISS:
                self._init_faiss()
            else:
                raise ValueError(f"Type de base de données non supporté: {self.db_type}")
            
            self._initialized = True
            logger.info(f"Client {self.db_type.value} initialisé avec succès")
            
        except Exception as e:
            logger.error(f"Erreur d'initialisation du client {self.db_type.value}: {e}")
            raise
    
    def _init_chroma(self):
        """Initialise ChromaDB"""
        try:
            import chromadb
            from chromadb.config import Settings
            
            # Configuration ChromaDB
            chroma_settings = Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=self.connection_params.get('persist_directory', './chroma_db'),
                anonymized_telemetry=False,
            )
            
            self._client = chromadb.PersistentClient(
                path=self.connection_params.get('persist_directory', './chroma_db'),
                settings=chroma_settings
            )
            
            # Créer ou récupérer la collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "hnsw:space": self._get_distance_metric(),
                    "dimension": self.config.dimension,
                }
            )
            
        except ImportError:
            logger.error("ChromaDB n'est pas installé. Installez avec: pip install chromadb")
            raise
    
    def _init_pinecone(self):
        """Initialise Pinecone"""
        try:
            import pinecone
            
            # Initialisation avec les paramètres de connexion
            pinecone.init(
                api_key=self.connection_params.get('api_key', os.getenv('PINECONE_API_KEY')),
                environment=self.connection_params.get('environment', os.getenv('PINECONE_ENVIRONMENT')),
            )
            
            # Créer ou récupérer l'index
            index_name = self.collection_name
            dimension = self.config.dimension or 768  # Dimension par défaut
            
            if index_name not in pinecone.list_indexes():
                pinecone.create_index(
                    name=index_name,
                    dimension=dimension,
                    metric=self._get_distance_metric(),
                    pods=self.connection_params.get('pods', 1),
                    pod_type=self.connection_params.get('pod_type', 'p1.x1'),
                )
            
            self._client = pinecone.Index(index_name)
            
        except ImportError:
            logger.error("Pinecone n'est pas installé. Installez avec: pip install pinecone-client")
            raise
    
    def _init_weaviate(self):
        """Initialise Weaviate"""
        try:
            import weaviate
            
            self._client = weaviate.Client(
                url=self.connection_params.get('url', 'http://localhost:8080'),
                auth_client_secret=self.connection_params.get('auth_secret'),
                additional_headers=self.connection_params.get('headers', {}),
            )
            
            # Vérifier que la classe existe
            if not self._client.schema.exists(self.collection_name):
                class_obj = {
                    "class": self.collection_name,
                    "vectorizer": "none",
                    "properties": [
                        {"name": "content", "dataType": ["text"]},
                        {"name": "metadata", "dataType": ["object"]},
                        {"name": "timestamp", "dataType": ["date"]},
                    ]
                }
                self._client.schema.create_class(class_obj)
            
        except ImportError:
            logger.error("Weaviate n'est pas installé. Installez avec: pip install weaviate-client")
            raise
    
    def _init_milvus(self):
        """Initialise Milvus"""
        try:
            from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType
            
            # Connexion à Milvus
            connections.connect(
                alias="default",
                host=self.connection_params.get('host', 'localhost'),
                port=self.connection_params.get('port', '19530'),
                user=self.connection_params.get('user', ''),
                password=self.connection_params.get('password', ''),
            )
            
            # Créer la collection si elle n'existe pas
            collection_name = self.collection_name
            dimension = self.config.dimension or 768
            
            # Vérifier si la collection existe
            from pymilvus import utility
            if not utility.has_collection(collection_name):
                # Définir le schéma
                fields = [
                    FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
                    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
                    FieldSchema(name="metadata", dtype=DataType.JSON),
                    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=10000),
                    FieldSchema(name="timestamp", dtype=DataType.INT64),
                    FieldSchema(name="embedding_model", dtype=DataType.VARCHAR, max_length=100),
                    FieldSchema(name="namespace", dtype=DataType.VARCHAR, max_length=100),
                ]
                schema = CollectionSchema(fields, description=f"Collection pour {collection_name}")
                self._client = Collection(name=collection_name, schema=schema)
                
                # Créer l'index
                index_params = {
                    "metric_type": self._get_distance_metric(),
                    "index_type": "IVF_SQ8",
                    "params": {"nlist": self.config.nlist}
                }
                self._client.create_index("vector", index_params)
            else:
                self._client = Collection(name=collection_name)
            
            # Charger la collection
            self._client.load()
            
        except ImportError:
            logger.error("Milvus n'est pas installé. Installez avec: pip install pymilvus")
            raise
    
    def _init_qdrant(self):
        """Initialise Qdrant"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams, PointStruct
            
            # Connexion à Qdrant
            self._client = QdrantClient(
                host=self.connection_params.get('host', 'localhost'),
                port=self.connection_params.get('port', 6333),
                grpc_port=self.connection_params.get('grpc_port', 6334),
                prefer_grpc=self.connection_params.get('prefer_grpc', False),
                api_key=self.connection_params.get('api_key'),
            )
            
            # Vérifier si la collection existe
            collections = self._client.get_collections()
            collection_name = self.collection_name
            
            if collection_name not in [c.name for c in collections.collections]:
                # Créer la collection
                self._client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.config.dimension or 768,
                        distance=Distance.COSINE if self.config.metric == DistanceMetric.COSINE else Distance.EUCLID,
                    ),
                )
            
        except ImportError:
            logger.error("Qdrant n'est pas installé. Installez avec: pip install qdrant-client")
            raise
    
    def _init_faiss(self):
        """Initialise FAISS (mémoire locale)"""
        try:
            import faiss
            import numpy as np
            
            dimension = self.config.dimension or 768
            self._dimension = dimension
            
            # Créer un index FAISS
            if self.config.index_type == IndexType.FLAT:
                self._index = faiss.IndexFlatIP(dimension) if self.config.metric == DistanceMetric.INNER_PRODUCT else faiss.IndexFlatL2(dimension)
            elif self.config.index_type == IndexType.IVF_FLAT:
                self._index = faiss.IndexIVFFlat(
                    faiss.IndexFlatL2(dimension), dimension, self.config.nlist
                )
            elif self.config.index_type == IndexType.HNSW:
                self._index = faiss.IndexHNSWFlat(dimension, self.config.M)
            else:
                self._index = faiss.IndexFlatL2(dimension)
            
            # Stockage local des documents
            self._documents: Dict[str, VectorDocument] = {}
            self._vectors = []
            
        except ImportError:
            logger.error("FAISS n'est pas installé. Installez avec: pip install faiss-cpu")
            raise
    
    def _get_distance_metric(self) -> str:
        """Convertit DistanceMetric en chaîne pour la base de données"""
        mapping = {
            DistanceMetric.COSINE: "cosine",
            DistanceMetric.EUCLIDEAN: "l2",
            DistanceMetric.DOT_PRODUCT: "ip",
            DistanceMetric.L2: "l2",
            DistanceMetric.INNER_PRODUCT: "ip",
        }
        return mapping.get(self.config.metric, "cosine")
    
    def _generate_cache_key(self, query_vector: List[float], filter: Optional[Dict] = None, top_k: int = 10) -> str:
        """Génère une clé de cache pour une requête"""
        import hashlib
        import json
        
        # Convertir le vecteur en chaîne
        vector_str = ','.join([f'{x:.4f}' for x in query_vector[:10]])  # Limiter pour la clé
        filter_str = json.dumps(filter or {}, sort_keys=True)
        key = f"{vector_str}_{filter_str}_{top_k}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def _normalize_vector(self, vector: List[float]) -> List[float]:
        """Normalise un vecteur"""
        import math
        
        norm = math.sqrt(sum(x * x for x in vector))
        if norm == 0:
            return vector
        return [x / norm for x in vector]
    
    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================
    
    def add_document(self, document: VectorDocument) -> str:
        """
        Ajoute un document vectoriel à la base de données.
        
        Args:
            document: Document vectoriel à ajouter
            
        Returns:
            str: ID du document ajouté
            
        Example:
            ```python
            doc = VectorDocument(
                id="pattern_001",
                vector=[0.1, 0.2, 0.3],
                metadata={"type": "bullish", "confidence": 0.95}
            )
            manager.add_document(doc)
            ```
        """
        if not self._initialized:
            self._init_client()
        
        try:
            # Normalisation du vecteur
            vector = self._normalize_vector(document.vector)
            
            if self.db_type == VectorDBType.CHROMA:
                self._collection.add(
                    ids=[document.id],
                    embeddings=[vector],
                    metadatas=[document.metadata],
                    documents=[document.content] if document.content else None,
                )
            
            elif self.db_type == VectorDBType.PINECONE:
                self._client.upsert([
                    (document.id, vector, document.metadata)
                ])
            
            elif self.db_type == VectorDBType.WEAVIATE:
                properties = {
                    "content": document.content or "",
                    "metadata": document.metadata,
                    "timestamp": document.timestamp.isoformat(),
                }
                self._client.data_object.create(
                    properties,
                    class_name=self.collection_name,
                    vector=vector,
                    uuid=document.id,
                )
            
            elif self.db_type == VectorDBType.MILVUS:
                import time
                data = {
                    "id": document.id,
                    "vector": vector,
                    "metadata": document.metadata,
                    "content": document.content or "",
                    "timestamp": int(time.time()),
                    "embedding_model": document.embedding_model or "",
                    "namespace": document.namespace or "",
                }
                self._client.insert([data])
            
            elif self.db_type == VectorDBType.QDRANT:
                from qdrant_client.models import PointStruct
                
                point = PointStruct(
                    id=document.id,
                    vector=vector,
                    payload={
                        "metadata": document.metadata,
                        "content": document.content,
                        "timestamp": document.timestamp.isoformat(),
                        "embedding_model": document.embedding_model,
                        "namespace": document.namespace,
                    }
                )
                self._client.upsert(self.collection_name, [point])
            
            elif self.db_type == VectorDBType.FAISS:
                import numpy as np
                
                # Stocker le document
                self._documents[document.id] = document
                
                # Ajouter le vecteur à l'index
                vector_np = np.array(vector, dtype=np.float32).reshape(1, -1)
                self._vectors.append(vector_np)
                
                if not hasattr(self._index, 'is_trained') or self._index.is_trained:
                    self._index.add(vector_np)
            
            # Invalider le cache
            self._cache.clear()
            
            self._stats['documents_added'] += 1
            logger.debug(f"Document ajouté: {document.id}")
            return document.id
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout du document {document.id}: {e}")
            raise
    
    def add_documents(self, documents: List[VectorDocument]) -> List[str]:
        """
        Ajoute plusieurs documents vectoriels.
        
        Args:
            documents: Liste de documents à ajouter
            
        Returns:
            List[str]: Liste des IDs ajoutés
        """
        ids = []
        for doc in documents:
            try:
                doc_id = self.add_document(doc)
                ids.append(doc_id)
            except Exception as e:
                logger.error(f"Erreur lors de l'ajout du document {doc.id}: {e}")
        return ids
    
    def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[SearchResult]:
        """
        Effectue une recherche de similarité.
        
        Args:
            query_vector: Vecteur de requête
            top_k: Nombre de résultats à retourner
            filter: Filtre sur les métadonnées
            namespace: Espace de noms pour la recherche
            use_cache: Utiliser le cache
            
        Returns:
            List[SearchResult]: Résultats de la recherche
            
        Example:
            ```python
            results = manager.search(
                query_vector=[0.1, 0.2, 0.3],
                top_k=5,
                filter={"type": "bullish", "confidence": {"$gt": 0.8}}
            )
            for result in results:
                print(f"Score: {result.score}, Document: {result.document.id}")
            ```
        """
        if not self._initialized:
            self._init_client()
        
        # Normalisation du vecteur
        query_vector = self._normalize_vector(query_vector)
        
        # Cache
        cache_key = self._generate_cache_key(query_vector, filter, top_k)
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            # Vérifier l'expiration du cache
            if (datetime.now() - cached['timestamp']).seconds < self._cache_ttl:
                self._stats['cache_hits'] += 1
                logger.debug("Résultat trouvé dans le cache")
                return cached['results']
        
        self._stats['cache_misses'] += 1
        self._stats['search_count'] += 1
        
        try:
            # Construction du filtre
            filter_metadata = {}
            if filter:
                filter_metadata = filter
            if namespace:
                filter_metadata['namespace'] = namespace
            
            results = []
            
            if self.db_type == VectorDBType.CHROMA:
                # Recherche ChromaDB
                if filter_metadata:
                    where = filter_metadata
                else:
                    where = {}
                
                response = self._collection.query(
                    query_embeddings=[query_vector],
                    n_results=top_k,
                    where=where,
                )
                
                if response['ids'] and response['ids'][0]:
                    for i, doc_id in enumerate(response['ids'][0]):
                        document = VectorDocument(
                            id=doc_id,
                            vector=response['embeddings'][0][i] if response.get('embeddings') else [],
                            metadata=response['metadatas'][0][i] if response.get('metadatas') else {},
                            content=response['documents'][0][i] if response.get('documents') else None,
                        )
                        results.append(SearchResult(
                            document=document,
                            score=float(1 - response['distances'][0][i]) if response.get('distances') else 0,
                            distance=float(response['distances'][0][i]) if response.get('distances') else 0,
                            rank=i,
                        ))
            
            elif self.db_type == VectorDBType.PINECONE:
                # Recherche Pinecone
                response = self._client.query(
                    vector=query_vector,
                    top_k=top_k,
                    filter=filter_metadata if filter_metadata else None,
                    include_metadata=True,
                )
                
                for i, match in enumerate(response.matches):
                    document = VectorDocument(
                        id=match.id,
                        vector=[],  # Pinecone ne retourne pas le vecteur par défaut
                        metadata=match.metadata or {},
                    )
                    results.append(SearchResult(
                        document=document,
                        score=float(match.score),
                        distance=float(1 - match.score),
                        rank=i,
                    ))
            
            elif self.db_type == VectorDBType.WEAVIATE:
                # Recherche Weaviate
                import weaviate
                
                where_filter = None
                if filter_metadata:
                    # Construction du filtre Weaviate
                    where_filter = {
                        "path": list(filter_metadata.keys()),
                        "operator": "Equal",
                        "valueString": list(filter_metadata.values())[0],
                    }
                
                response = self._client.query.get(
                    self.collection_name,
                    ['content', 'metadata', 'timestamp']
                ).with_near_vector({
                    "vector": query_vector,
                    "distance": self.config.metric.value,
                }).with_limit(top_k).do()
                
                if response and 'data' in response:
                    for i, item in enumerate(response['data']['Get'][self.collection_name]):
                        document = VectorDocument(
                            id=item.get('_id', str(uuid.uuid4())),
                            vector=[],
                            metadata=item.get('metadata', {}),
                            content=item.get('content'),
                        )
                        results.append(SearchResult(
                            document=document,
                            score=1.0 - item.get('_additional', {}).get('distance', 0),
                            distance=item.get('_additional', {}).get('distance', 0),
                            rank=i,
                        ))
            
            elif self.db_type == VectorDBType.MILVUS:
                # Recherche Milvus
                import numpy as np
                
                # Préparer la recherche
                search_param = {
                    "metric_type": self._get_distance_metric(),
                    "params": {"nprobe": self.config.nprobe},
                }
                
                # Filtrer les métadonnées
                expr = None
                if filter_metadata:
                    expr_parts = []
                    for key, value in filter_metadata.items():
                        if isinstance(value, dict):
                            # Gestion des opérateurs
                            for op, val in value.items():
                                if op == '$gt':
                                    expr_parts.append(f"{key} > {val}")
                                elif op == '$lt':
                                    expr_parts.append(f"{key} < {val}")
                                elif op == '$gte':
                                    expr_parts.append(f"{key} >= {val}")
                                elif op == '$lte':
                                    expr_parts.append(f"{key} <= {val}")
                                elif op == '$eq':
                                    expr_parts.append(f"{key} == {val}")
                        else:
                            expr_parts.append(f"{key} == '{value}'")
                    
                    expr = " and ".join(expr_parts)
                
                # Exécuter la recherche
                response = self._client.search(
                    data=[query_vector],
                    anns_field="vector",
                    param=search_param,
                    limit=top_k,
                    expr=expr,
                    output_fields=["id", "metadata", "content", "timestamp", "embedding_model", "namespace"],
                )
                
                for i, hit in enumerate(response[0]):
                    document = VectorDocument(
                        id=hit.entity.get('id', str(uuid.uuid4())),
                        vector=[],
                        metadata=hit.entity.get('metadata', {}),
                        content=hit.entity.get('content'),
                        timestamp=datetime.fromtimestamp(hit.entity.get('timestamp', 0)),
                        embedding_model=hit.entity.get('embedding_model'),
                        namespace=hit.entity.get('namespace'),
                    )
                    results.append(SearchResult(
                        document=document,
                        score=float(hit.score),
                        distance=float(1 - hit.score),
                        rank=i,
                    ))
            
            elif self.db_type == VectorDBType.QDRANT:
                # Recherche Qdrant
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                
                qdrant_filter = None
                if filter_metadata:
                    conditions = []
                    for key, value in filter_metadata.items():
                        if isinstance(value, dict):
                            # Gestion des opérateurs
                            for op, val in value.items():
                                if op == '$gt':
                                    conditions.append(FieldCondition(key=key, range={"gt": val}))
                                elif op == '$lt':
                                    conditions.append(FieldCondition(key=key, range={"lt": val}))
                                elif op == '$gte':
                                    conditions.append(FieldCondition(key=key, range={"gte": val}))
                                elif op == '$lte':
                                    conditions.append(FieldCondition(key=key, range={"lte": val}))
                                elif op == '$eq':
                                    conditions.append(FieldCondition(key=key, match=MatchValue(value=val)))
                        else:
                            conditions.append(FieldCondition(key=f"metadata.{key}", match=MatchValue(value=value)))
                    
                    if conditions:
                        qdrant_filter = Filter(must=conditions)
                
                response = self._client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    limit=top_k,
                    query_filter=qdrant_filter,
                    with_payload=True,
                )
                
                for i, hit in enumerate(response):
                    document = VectorDocument(
                        id=str(hit.id),
                        vector=[],
                        metadata=hit.payload.get('metadata', {}),
                        content=hit.payload.get('content'),
                        timestamp=datetime.fromisoformat(hit.payload.get('timestamp', datetime.now().isoformat())),
                        embedding_model=hit.payload.get('embedding_model'),
                        namespace=hit.payload.get('namespace'),
                    )
                    results.append(SearchResult(
                        document=document,
                        score=float(hit.score),
                        distance=float(1 - hit.score),
                        rank=i,
                    ))
            
            elif self.db_type == VectorDBType.FAISS:
                import numpy as np
                
                # Recherche FAISS
                query_np = np.array(query_vector, dtype=np.float32).reshape(1, -1)
                
                distances, indices = self._index.search(query_np, min(top_k, len(self._documents)))
                
                for i, idx in enumerate(indices[0]):
                    if idx >= 0 and idx < len(self._documents):
                        # Récupérer le document par son ID (approximatif)
                        doc_ids = list(self._documents.keys())
                        if idx < len(doc_ids):
                            doc_id = doc_ids[idx]
                            document = self._documents.get(doc_id)
                            if document:
                                results.append(SearchResult(
                                    document=document,
                                    score=float(1 / (1 + distances[0][i])) if distances[0][i] >= 0 else 0,
                                    distance=float(distances[0][i]),
                                    rank=i,
                                ))
            
            # Mise en cache
            if use_cache:
                self._cache[cache_key] = {
                    'results': results,
                    'timestamp': datetime.now(),
                }
                # Limiter la taille du cache
                if len(self._cache) > self._cache_size:
                    oldest = min(self._cache.keys(), key=lambda k: self._cache[k]['timestamp'])
                    del self._cache[oldest]
            
            logger.debug(f"Recherche effectuée: {len(results)} résultats trouvés")
            return results
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {e}")
            return []
    
    def get_document(self, doc_id: str) -> Optional[VectorDocument]:
        """
        Récupère un document par son ID.
        
        Args:
            doc_id: ID du document
            
        Returns:
            Optional[VectorDocument]: Document trouvé ou None
        """
        if not self._initialized:
            self._init_client()
        
        try:
            if self.db_type == VectorDBType.CHROMA:
                response = self._collection.get(ids=[doc_id])
                if response['ids']:
                    return VectorDocument(
                        id=response['ids'][0],
                        vector=response['embeddings'][0] if response.get('embeddings') else [],
                        metadata=response['metadatas'][0] if response.get('metadatas') else {},
                        content=response['documents'][0] if response.get('documents') else None,
                    )
            
            elif self.db_type == VectorDBType.PINECONE:
                response = self._client.fetch([doc_id])
                if response.vectors:
                    vector_data = response.vectors.get(doc_id)
                    if vector_data:
                        return VectorDocument(
                            id=doc_id,
                            vector=vector_data.values,
                            metadata=vector_data.metadata or {},
                        )
            
            elif self.db_type == VectorDBType.WEAVIATE:
                response = self._client.data_object.get_by_id(
                    doc_id,
                    class_name=self.collection_name,
                )
                if response:
                    return VectorDocument(
                        id=doc_id,
                        vector=[],  # Weaviate ne retourne pas le vecteur facilement
                        metadata=response.get('metadata', {}),
                        content=response.get('content'),
                        timestamp=datetime.fromisoformat(response.get('timestamp', datetime.now().isoformat())),
                    )
            
            elif self.db_type == VectorDBType.FAISS:
                return self._documents.get(doc_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du document {doc_id}: {e}")
            return None
    
    def update_document(self, document: VectorDocument) -> bool:
        """
        Met à jour un document existant.
        
        Args:
            document: Document mis à jour
            
        Returns:
            bool: True si la mise à jour a réussi
        """
        try:
            # Supprimer l'ancien document
            self.delete_document(document.id)
            
            # Ajouter le nouveau document
            self.add_document(document)
            
            self._stats['documents_updated'] += 1
            logger.debug(f"Document mis à jour: {document.id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du document {document.id}: {e}")
            return False
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Supprime un document de la base de données.
        
        Args:
            doc_id: ID du document à supprimer
            
        Returns:
            bool: True si la suppression a réussi
        """
        if not self._initialized:
            self._init_client()
        
        try:
            if self.db_type == VectorDBType.CHROMA:
                self._collection.delete(ids=[doc_id])
            
            elif self.db_type == VectorDBType.PINECONE:
                self._client.delete(ids=[doc_id])
            
            elif self.db_type == VectorDBType.WEAVIATE:
                self._client.data_object.delete_by_id(doc_id)
            
            elif self.db_type == VectorDBType.MILVUS:
                expr = f"id == '{doc_id}'"
                self._client.delete(expr)
            
            elif self.db_type == VectorDBType.QDRANT:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                filter = Filter(must=[FieldCondition(key="id", match=MatchValue(value=doc_id))])
                self._client.delete(self.collection_name, points_filter=filter)
            
            elif self.db_type == VectorDBType.FAISS:
                if doc_id in self._documents:
                    del self._documents[doc_id]
                    # Réindexation pour FAISS
                    self._rebuild_faiss_index()
            
            # Invalider le cache
            self._cache.clear()
            
            self._stats['documents_deleted'] += 1
            logger.debug(f"Document supprimé: {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du document {doc_id}: {e}")
            return False
    
    def delete_documents(self, filter: Dict[str, Any]) -> int:
        """
        Supprime les documents correspondant au filtre.
        
        Args:
            filter: Filtre pour la suppression
            
        Returns:
            int: Nombre de documents supprimés
        """
        count = 0
        try:
            # Récupérer les documents correspondant au filtre
            # Implémentation simplifiée - dépend du type de base de données
            # Idéalement, utiliser une méthode de recherche pour identifier
            # les documents à supprimer
            logger.warning("delete_documents n'est pas implémenté pour tous les types de DB")
            return count
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression en masse: {e}")
            return count
    
    def _rebuild_faiss_index(self):
        """Reconstruit l'index FAISS"""
        if self.db_type != VectorDBType.FAISS:
            return
        
        import numpy as np
        
        # Réinitialiser l'index
        self._init_faiss()
        
        # Réajouter tous les vecteurs
        for doc in self._documents.values():
            vector_np = np.array(doc.vector, dtype=np.float32).reshape(1, -1)
            self._index.add(vector_np)
    
    def clear_collection(self) -> bool:
        """
        Efface toute la collection.
        
        Returns:
            bool: True si l'effacement a réussi
        """
        try:
            if self.db_type == VectorDBType.CHROMA:
                # Supprimer et recréer la collection
                self._client.delete_collection(self.collection_name)
                self._collection = self._client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": self._get_distance_metric()},
                )
            
            elif self.db_type == VectorDBType.PINECONE:
                self._client.delete(delete_all=True)
            
            elif self.db_type == VectorDBType.WEAVIATE:
                self._client.schema.delete_class(self.collection_name)
                # Recréer la classe
                class_obj = {
                    "class": self.collection_name,
                    "vectorizer": "none",
                    "properties": [
                        {"name": "content", "dataType": ["text"]},
                        {"name": "metadata", "dataType": ["object"]},
                        {"name": "timestamp", "dataType": ["date"]},
                    ]
                }
                self._client.schema.create_class(class_obj)
            
            elif self.db_type == VectorDBType.FAISS:
                self._documents.clear()
                self._vectors.clear()
                self._init_faiss()
            
            # Invalider le cache
            self._cache.clear()
            
            logger.info(f"Collection {self.collection_name} effacée")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'effacement de la collection: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques du gestionnaire.
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        stats = self._stats.copy()
        stats['collection_name'] = self.collection_name
        stats['db_type'] = self.db_type.value
        stats['cache_size'] = len(self._cache)
        stats['initialized'] = self._initialized
        return stats
    
    def close(self):
        """Ferme la connexion à la base de données"""
        try:
            if self.db_type == VectorDBType.MILVUS:
                from pymilvus import connections
                connections.disconnect("default")
            elif self.db_type == VectorDBType.CHROMA:
                # ChromaDB n'a pas de méthode close explicite
                pass
            elif self.db_type == VectorDBType.PINECONE:
                # Pinecone n'a pas de méthode close explicite
                pass
            logger.info("Connexion fermée")
        except Exception as e:
            logger.error(f"Erreur lors de la fermeture de la connexion: {e}")


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_vector_from_text(
    text: str,
    model_name: str = "all-MiniLM-L6-v2",
    **kwargs
) -> List[float]:
    """
    Crée un vecteur d'embedding à partir d'un texte.
    
    Args:
        text: Texte à encoder
        model_name: Nom du modèle d'embedding
        **kwargs: Paramètres additionnels
    
    Returns:
        List[float]: Vecteur d'embedding
    """
    try:
        from sentence_transformers import SentenceTransformer
        
        model = SentenceTransformer(model_name, **kwargs)
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
        
    except ImportError:
        logger.error("SentenceTransformers n'est pas installé")
        raise
    except Exception as e:
        logger.error(f"Erreur de création du vecteur: {e}")
        raise


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calcule la similarité cosinus entre deux vecteurs.
    
    Args:
        vec1: Premier vecteur
        vec2: Deuxième vecteur
        
    Returns:
        float: Similarité cosinus (-1 à 1)
    """
    import math
    
    if len(vec1) != len(vec2):
        raise ValueError("Les vecteurs doivent avoir la même dimension")
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    
    if norm1 == 0 or norm2 == 0:
        return 0
    
    return dot_product / (norm1 * norm2)


# ============================================================
# EXPORTS PRINCIPAUX
# ============================================================

__all__ = [
    # Classes principales
    'VectorDBManager',
    'VectorDocument',
    'SearchResult',
    'VectorIndexConfig',
    
    # Énumérations
    'VectorDBType',
    'DistanceMetric',
    'IndexType',
    
    # Fonctions utilitaires
    'create_vector_from_text',
    'cosine_similarity',
]

# ============================================================
# INITIALISATION DU LOGGING
# ============================================================

if __name__ == "__main__":
    # Test rapide
    logging.basicConfig(level=logging.INFO)
    
    print("NEXUS Vector Database Module")
    print(f"Version: 3.0")
    print(f"Types supportés: {[t.value for t in VectorDBType]}")
    print("\nExemple d'utilisation:")
    print("""
    from ai.vector_db import VectorDBManager, VectorDocument, VectorDBType
    
    manager = VectorDBManager(
        db_type=VectorDBType.FAISS,
        collection_name="test_collection"
    )
    
    doc = VectorDocument(
        id="test_001",
        vector=[0.1, 0.2, 0.3],
        metadata={"type": "test", "value": 42}
    )
    
    manager.add_document(doc)
    results = manager.search(
        query_vector=[0.15, 0.25, 0.35],
        top_k=5
    )
    """)

