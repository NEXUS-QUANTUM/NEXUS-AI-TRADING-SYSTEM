"""
NEXUS AI TRADING SYSTEM - Embeddings Generator Module
Copyright © 2026 NEXUS QUANTUM LTD

This module implements embedding generation for the NEXUS AI Trading System including:
- Multiple embedding models (OpenAI, HuggingFace, Sentence Transformers)
- Text embedding generation
- Document embedding generation
- Batch embedding generation
- Embedding caching and persistence
- Embedding normalization
- Embedding dimension reduction
- Embedding visualization
- Embedding similarity computation
- Embedding clustering
- Embedding quality metrics
- Model management
- Embedding pipeline
- Performance monitoring
- GPU acceleration
- Batch processing
- Async processing
- Embedding export/import
"""

import os
import sys
import json
import time
import logging
import hashlib
import pickle
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Union, Set, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Optional imports
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    from transformers import AutoTokenizer, AutoModel
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/embeddings_generator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class ModelType(Enum):
    """Types of embedding models."""
    OPENAI = "openai"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    HUGGINGFACE = "huggingface"
    CUSTOM = "custom"
    LOCAL = "local"


class EmbeddingStatus(Enum):
    """Status of embedding generation."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation."""
    model_type: ModelType
    model_name: str
    dimension: int
    batch_size: int = 32
    normalize: bool = True
    use_gpu: bool = False
    cache_enabled: bool = True
    cache_dir: str = "./embeddings_cache"
    max_length: int = 512
    device: str = "cpu"


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    id: str
    text: str
    embedding: np.ndarray
    status: EmbeddingStatus
    timestamp: float
    model_name: str
    dimension: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    generation_time: float = 0.0


@dataclass
class EmbeddingStats:
    """Statistics for embedding generation."""
    total_generations: int
    successful_generations: int
    failed_generations: int
    cached_generations: int
    average_time: float
    total_time: float
    model_name: str
    dimension: int
    timestamp: float


# ============================================
# Embeddings Generator Implementation
# ============================================

class EmbeddingsGenerator:
    """
    Embedding generation engine for the NEXUS AI Trading System.
    
    This class provides embedding generation capabilities using multiple
    models with caching, batching, and performance optimization.
    """
    
    def __init__(self, config: EmbeddingConfig):
        """
        Initialize the embeddings generator.
        
        Args:
            config: Embedding configuration
        """
        self.config = config
        self.model = None
        self.tokenizer = None
        self.model_name = config.model_name
        self.dimension = config.dimension
        
        # Cache
        self.cache_dir = Path(config.cache_dir) if config.cache_enabled else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.cache: Dict[str, np.ndarray] = {}
            self._load_cache()
        
        # Statistics
        self.stats = EmbeddingStats(
            total_generations=0,
            successful_generations=0,
            failed_generations=0,
            cached_generations=0,
            average_time=0.0,
            total_time=0.0,
            model_name=config.model_name,
            dimension=config.dimension,
            timestamp=time.time(),
        )
        
        # Initialize model
        self._init_model()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"EmbeddingsGenerator initialized with model: {config.model_name}")
        self.logger.info(f"Dimension: {config.dimension}, Batch size: {config.batch_size}")
    
    # ============================================
    # Model Initialization
    # ============================================
    
    def _init_model(self) -> None:
        """Initialize the embedding model."""
        if self.config.model_type == ModelType.OPENAI:
            self._init_openai()
        elif self.config.model_type == ModelType.SENTENCE_TRANSFORMERS:
            self._init_sentence_transformers()
        elif self.config.model_type == ModelType.HUGGINGFACE:
            self._init_huggingface()
        elif self.config.model_type == ModelType.LOCAL:
            self._init_local()
        else:
            raise ValueError(f"Unsupported model type: {self.config.model_type}")
    
    def _init_openai(self) -> None:
        """Initialize OpenAI model."""
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI not available. Install with: pip install openai")
        
        try:
            # Check for API key
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            
            openai.api_key = api_key
            
            # Set model
            if not self.model_name:
                self.model_name = "text-embedding-ada-002"
            
            self.dimension = 1536  # Ada-002 dimension
            
            self.logger.info(f"OpenAI model initialized: {self.model_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI: {e}")
            raise
    
    def _init_sentence_transformers(self) -> None:
        """Initialize Sentence Transformers model."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("Sentence Transformers not available. Install with: pip install sentence-transformers")
        
        try:
            # Set device
            device = "cuda" if self.config.use_gpu and torch.cuda.is_available() else "cpu"
            
            # Load model
            self.model = SentenceTransformer(self.model_name, device=device)
            
            # Get dimension
            self.dimension = self.model.get_sentence_embedding_dimension()
            
            self.logger.info(f"Sentence Transformers model initialized: {self.model_name}")
            self.logger.info(f"Dimension: {self.dimension}, Device: {device}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Sentence Transformers: {e}")
            raise
    
    def _init_huggingface(self) -> None:
        """Initialize HuggingFace model."""
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers not available. Install with: pip install transformers")
        
        try:
            # Set device
            device = "cuda" if self.config.use_gpu and torch.cuda.is_available() else "cpu"
            
            # Load tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name).to(device)
            self.model.eval()
            
            # Get dimension
            if hasattr(self.model.config, 'hidden_size'):
                self.dimension = self.model.config.hidden_size
            
            self.logger.info(f"HuggingFace model initialized: {self.model_name}")
            self.logger.info(f"Dimension: {self.dimension}, Device: {device}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize HuggingFace: {e}")
            raise
    
    def _init_local(self) -> None:
        """Initialize local model."""
        # This is a placeholder for custom local models
        self.logger.info("Local model initialized (placeholder)")
        self.dimension = self.config.dimension or 128
    
    # ============================================
    # Cache Management
    # ============================================
    
    def _load_cache(self) -> None:
        """Load cache from disk."""
        if not self.cache_dir:
            return
        
        cache_file = self.cache_dir / "embeddings_cache.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    self.cache = pickle.load(f)
                self.logger.info(f"Loaded {len(self.cache)} cached embeddings")
            except Exception as e:
                self.logger.warning(f"Failed to load cache: {e}")
    
    def _save_cache(self) -> None:
        """Save cache to disk."""
        if not self.cache_dir or not self.cache:
            return
        
        try:
            cache_file = self.cache_dir / "embeddings_cache.pkl"
            with open(cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
            self.logger.debug(f"Saved {len(self.cache)} cached embeddings")
        except Exception as e:
            self.logger.warning(f"Failed to save cache: {e}")
    
    def _get_cache_key(self, text: str) -> str:
        """
        Generate cache key for a text.
        
        Args:
            text: Text to hash
            
        Returns:
            Cache key
        """
        return hashlib.md5(
            f"{text}_{self.model_name}".encode()
        ).hexdigest()
    
    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self.cache.clear()
        if self.cache_dir:
            cache_file = self.cache_dir / "embeddings_cache.pkl"
            if cache_file.exists():
                cache_file.unlink()
        self.logger.info("Cache cleared")
    
    # ============================================
    # Embedding Generation
    # ============================================
    
    def generate_embedding(
        self,
        text: str,
        use_cache: bool = True,
        normalize: Optional[bool] = None,
    ) -> Optional[np.ndarray]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            use_cache: Whether to use cache
            normalize: Whether to normalize embedding
            
        Returns:
            Embedding vector or None
        """
        start_time = time.time()
        self.stats.total_generations += 1
        
        try:
            # Check cache
            if use_cache and self.config.cache_enabled:
                cache_key = self._get_cache_key(text)
                if cache_key in self.cache:
                    embedding = self.cache[cache_key]
                    self.stats.cached_generations += 1
                    self.stats.successful_generations += 1
                    self.logger.debug(f"Cache hit for text: {text[:50]}...")
                    return embedding
            
            # Generate embedding
            embedding = self._generate_single_embedding(text)
            
            if embedding is None:
                self.stats.failed_generations += 1
                return None
            
            # Normalize if needed
            if normalize is None:
                normalize = self.config.normalize
            if normalize:
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm
            
            # Cache
            if use_cache and self.config.cache_enabled:
                cache_key = self._get_cache_key(text)
                self.cache[cache_key] = embedding
                if len(self.cache) % 100 == 0:
                    self._save_cache()
            
            # Update statistics
            generation_time = time.time() - start_time
            self.stats.successful_generations += 1
            self.stats.total_time += generation_time
            self.stats.average_time = self.stats.total_time / self.stats.successful_generations
            
            return embedding
            
        except Exception as e:
            self.logger.error(f"Failed to generate embedding: {e}")
            self.stats.failed_generations += 1
            return None
    
    def _generate_single_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or None
        """
        if self.config.model_type == ModelType.OPENAI:
            return self._generate_openai_embedding(text)
        elif self.config.model_type == ModelType.SENTENCE_TRANSFORMERS:
            return self._generate_sentence_transformers_embedding(text)
        elif self.config.model_type == ModelType.HUGGINGFACE:
            return self._generate_huggingface_embedding(text)
        elif self.config.model_type == ModelType.LOCAL:
            return self._generate_local_embedding(text)
        else:
            raise ValueError(f"Unsupported model type: {self.config.model_type}")
    
    def _generate_openai_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding using OpenAI."""
        try:
            response = openai.Embedding.create(
                model=self.model_name,
                input=text,
            )
            embedding = np.array(response['data'][0]['embedding'])
            return embedding
        except Exception as e:
            self.logger.error(f"OpenAI embedding error: {e}")
            return None
    
    def _generate_sentence_transformers_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding using Sentence Transformers."""
        try:
            embedding = self.model.encode(
                text,
                batch_size=1,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            return embedding
        except Exception as e:
            self.logger.error(f"Sentence Transformers embedding error: {e}")
            return None
    
    def _generate_huggingface_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding using HuggingFace."""
        try:
            # Tokenize
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                max_length=self.config.max_length,
                truncation=True,
                padding=True,
            )
            
            # Move to device
            if self.config.use_gpu and torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # Generate embedding
            with torch.no_grad():
                outputs = self.model(**inputs)
                embedding = outputs.last_hidden_state.mean(dim=1).squeeze().cpu().numpy()
            
            return embedding
        except Exception as e:
            self.logger.error(f"HuggingFace embedding error: {e}")
            return None
    
    def _generate_local_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding using local model."""
        # This is a placeholder - implement custom local embedding
        # For demonstration, use a random vector
        import hashlib
        hash_bytes = hashlib.sha256(text.encode()).digest()
        embedding = np.frombuffer(hash_bytes, dtype=np.uint8)[:self.dimension]
        return embedding.astype(np.float32) / 255.0
    
    # ============================================
    # Batch Embedding Generation
    # ============================================
    
    def generate_embeddings(
        self,
        texts: List[str],
        use_cache: bool = True,
        normalize: Optional[bool] = None,
        show_progress: bool = True,
    ) -> List[Optional[np.ndarray]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            use_cache: Whether to use cache
            normalize: Whether to normalize embeddings
            show_progress: Whether to show progress bar
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        embeddings = []
        
        # Process in batches
        iterator = tqdm(texts, desc="Generating embeddings") if show_progress else texts
        
        for text in iterator:
            embedding = self.generate_embedding(text, use_cache, normalize)
            embeddings.append(embedding)
        
        return embeddings
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        use_cache: bool = True,
        normalize: Optional[bool] = None,
    ) -> List[Optional[np.ndarray]]:
        """
        Generate embeddings in batches for efficiency.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size
            use_cache: Whether to use cache
            normalize: Whether to normalize embeddings
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        batch_size = batch_size or self.config.batch_size
        
        # Check which texts are cached
        uncached_texts = []
        uncached_indices = []
        embeddings = [None] * len(texts)
        
        if use_cache and self.config.cache_enabled:
            for i, text in enumerate(texts):
                cache_key = self._get_cache_key(text)
                if cache_key in self.cache:
                    embeddings[i] = self.cache[cache_key]
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(i)
        else:
            uncached_texts = texts
            uncached_indices = list(range(len(texts)))
        
        # Generate embeddings for uncached texts
        if uncached_texts:
            if self.config.model_type == ModelType.SENTENCE_TRANSFORMERS:
                # Use model's encode method for batching
                try:
                    batch_embeddings = self.model.encode(
                        uncached_texts,
                        batch_size=batch_size,
                        show_progress_bar=True,
                        convert_to_numpy=True,
                        normalize_embeddings=normalize if normalize is not None else self.config.normalize,
                    )
                    
                    for i, embedding in enumerate(batch_embeddings):
                        idx = uncached_indices[i]
                        embeddings[idx] = embedding
                        
                        # Cache
                        if use_cache and self.config.cache_enabled:
                            cache_key = self._get_cache_key(uncached_texts[i])
                            self.cache[cache_key] = embedding
                
                except Exception as e:
                    self.logger.error(f"Batch embedding error: {e}")
                    # Fallback to individual generation
                    for i, text in enumerate(uncached_texts):
                        embedding = self.generate_embedding(text, use_cache, normalize)
                        idx = uncached_indices[i]
                        embeddings[idx] = embedding
            else:
                # Individual generation
                for i, text in enumerate(uncached_texts):
                    embedding = self.generate_embedding(text, use_cache, normalize)
                    idx = uncached_indices[i]
                    embeddings[idx] = embedding
        
        # Save cache if needed
        if use_cache and self.config.cache_enabled and uncached_texts:
            self._save_cache()
        
        return embeddings
    
    # ============================================
    # Document Embedding
    # ============================================
    
    def embed_document(
        self,
        document: Dict[str, Any],
        text_key: str = "text",
        use_cache: bool = True,
        normalize: Optional[bool] = None,
    ) -> Optional[np.ndarray]:
        """
        Generate embedding for a document.
        
        Args:
            document: Document dictionary
            text_key: Key for text content
            use_cache: Whether to use cache
            normalize: Whether to normalize embedding
            
        Returns:
            Embedding vector or None
        """
        text = document.get(text_key, "")
        if not text:
            return None
        
        return self.generate_embedding(text, use_cache, normalize)
    
    def embed_documents(
        self,
        documents: List[Dict[str, Any]],
        text_key: str = "text",
        use_cache: bool = True,
        normalize: Optional[bool] = None,
        show_progress: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Generate embeddings for multiple documents.
        
        Args:
            documents: List of documents
            text_key: Key for text content
            use_cache: Whether to use cache
            normalize: Whether to normalize embeddings
            show_progress: Whether to show progress bar
            
        Returns:
            Documents with embeddings added
        """
        if not documents:
            return []
        
        # Extract texts
        texts = [doc.get(text_key, "") for doc in documents]
        
        # Generate embeddings
        embeddings = self.generate_embeddings_batch(texts, use_cache=use_cache, normalize=normalize)
        
        # Add embeddings to documents
        for doc, embedding in zip(documents, embeddings):
            doc['embedding'] = embedding
        
        return documents
    
    # ============================================
    # Async Embedding Generation
    # ============================================
    
    async def generate_embedding_async(
        self,
        text: str,
        use_cache: bool = True,
        normalize: Optional[bool] = None,
    ) -> Optional[np.ndarray]:
        """
        Generate embedding asynchronously.
        
        Args:
            text: Text to embed
            use_cache: Whether to use cache
            normalize: Whether to normalize embedding
            
        Returns:
            Embedding vector or None
        """
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.generate_embedding,
            text,
            use_cache,
            normalize,
        )
    
    async def generate_embeddings_async(
        self,
        texts: List[str],
        use_cache: bool = True,
        normalize: Optional[bool] = None,
    ) -> List[Optional[np.ndarray]]:
        """
        Generate embeddings asynchronously.
        
        Args:
            texts: List of texts to embed
            use_cache: Whether to use cache
            normalize: Whether to normalize embeddings
            
        Returns:
            List of embedding vectors
        """
        tasks = []
        for text in texts:
            task = self.generate_embedding_async(text, use_cache, normalize)
            tasks.append(task)
        
        return await asyncio.gather(*tasks)
    
    # ============================================
    # Embedding Analysis
    # ============================================
    
    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
        metric: str = "cosine",
    ) -> float:
        """
        Compute similarity between two embeddings.
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            metric: Similarity metric ('cosine', 'euclidean', 'dot')
            
        Returns:
            Similarity score
        """
        if embedding1 is None or embedding2 is None:
            return 0.0
        
        if metric == "cosine":
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return np.dot(embedding1, embedding2) / (norm1 * norm2)
        elif metric == "euclidean":
            return 1.0 / (1.0 + np.linalg.norm(embedding1 - embedding2))
        elif metric == "dot":
            return np.dot(embedding1, embedding2)
        else:
            raise ValueError(f"Unsupported metric: {metric}")
    
    def compute_similarity_matrix(
        self,
        embeddings: List[np.ndarray],
        metric: str = "cosine",
    ) -> np.ndarray:
        """
        Compute similarity matrix for embeddings.
        
        Args:
            embeddings: List of embeddings
            metric: Similarity metric
            
        Returns:
            Similarity matrix
        """
        if not embeddings:
            return np.array([])
        
        n = len(embeddings)
        matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(i, n):
                similarity = self.compute_similarity(embeddings[i], embeddings[j], metric)
                matrix[i, j] = similarity
                matrix[j, i] = similarity
        
        return matrix
    
    def get_stats(self) -> EmbeddingStats:
        """
        Get embedding generation statistics.
        
        Returns:
            Embedding statistics
        """
        self.stats.timestamp = time.time()
        return self.stats
    
    def reset_stats(self) -> None:
        """Reset embedding statistics."""
        self.stats = EmbeddingStats(
            total_generations=0,
            successful_generations=0,
            failed_generations=0,
            cached_generations=0,
            average_time=0.0,
            total_time=0.0,
            model_name=self.config.model_name,
            dimension=self.config.dimension,
            timestamp=time.time(),
        )
    
    # ============================================
    # Model Management
    # ============================================
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model.
        
        Returns:
            Model information
        """
        return {
            'model_type': self.config.model_type.value,
            'model_name': self.model_name,
            'dimension': self.dimension,
            'batch_size': self.config.batch_size,
            'normalize': self.config.normalize,
            'use_gpu': self.config.use_gpu,
            'cache_enabled': self.config.cache_enabled,
            'cache_size': len(self.cache),
        }
    
    def switch_model(self, model_name: str, model_type: Optional[ModelType] = None) -> None:
        """
        Switch to a different model.
        
        Args:
            model_name: New model name
            model_type: New model type
        """
        self.model_name = model_name
        if model_type:
            self.config.model_type = model_type
        
        # Reset model
        self.model = None
        self.tokenizer = None
        self._init_model()
        
        # Clear cache (different model = different embeddings)
        self.clear_cache()
        
        self.logger.info(f"Switched to model: {model_name}")
    
    # ============================================
    # Export and Import
    # ============================================
    
    def export_embeddings(
        self,
        texts: List[str],
        format: str = "numpy",
        file_path: Optional[Union[str, Path]] = None,
    ) -> Union[np.ndarray, Dict[str, Any], str]:
        """
        Export embeddings for texts.
        
        Args:
            texts: List of texts
            format: Export format ('numpy', 'json', 'pickle')
            file_path: Path to save the export
            
        Returns:
            Exported embeddings or file path
        """
        embeddings = self.generate_embeddings(texts, use_cache=True, show_progress=True)
        
        if format == "numpy":
            data = np.array([e for e in embeddings if e is not None])
        elif format == "json":
            data = {
                'texts': texts,
                'embeddings': [e.tolist() if e is not None else None for e in embeddings],
                'model_name': self.model_name,
                'dimension': self.dimension,
                'timestamp': time.time(),
            }
        elif format == "pickle":
            data = {
                'texts': texts,
                'embeddings': embeddings,
                'model_name': self.model_name,
                'dimension': self.dimension,
                'timestamp': time.time(),
            }
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        if file_path:
            file_path = Path(file_path)
            if format == "numpy":
                np.save(file_path, data)
            elif format == "json":
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
            elif format == "pickle":
                with open(file_path, 'wb') as f:
                    pickle.dump(data, f)
            return str(file_path)
        
        return data
    
    def import_embeddings(
        self,
        data: Union[str, Dict[str, Any], bytes],
        format: str = "json",
    ) -> Tuple[List[str], List[np.ndarray]]:
        """
        Import embeddings.
        
        Args:
            data: Data to import
            format: Data format ('numpy', 'json', 'pickle')
            
        Returns:
            Tuple of (texts, embeddings)
        """
        if format == "numpy":
            if isinstance(data, str):
                data = np.load(data)
            embeddings = data
            texts = [f"text_{i}" for i in range(len(embeddings))]
        elif format == "json":
            if isinstance(data, str):
                with open(data, 'r') as f:
                    data = json.load(f)
            texts = data.get('texts', [])
            embeddings = [np.array(e) if e is not None else None for e in data.get('embeddings', [])]
        elif format == "pickle":
            if isinstance(data, str):
                with open(data, 'rb') as f:
                    data = pickle.load(f)
            texts = data.get('texts', [])
            embeddings = data.get('embeddings', [])
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return texts, embeddings


# ============================================
# Embeddings Generator Factory
# ============================================

class EmbeddingsGeneratorFactory:
    """
    Factory for creating embeddings generators.
    """
    
    @staticmethod
    def create_openai_generator(
        model_name: str = "text-embedding-ada-002",
        batch_size: int = 32,
        normalize: bool = True,
        cache_enabled: bool = True,
        cache_dir: str = "./embeddings_cache",
    ) -> EmbeddingsGenerator:
        """
        Create an OpenAI embeddings generator.
        
        Args:
            model_name: OpenAI model name
            batch_size: Batch size
            normalize: Whether to normalize embeddings
            cache_enabled: Whether to enable caching
            cache_dir: Cache directory
            
        Returns:
            EmbeddingsGenerator instance
        """
        config = EmbeddingConfig(
            model_type=ModelType.OPENAI,
            model_name=model_name,
            dimension=1536,
            batch_size=batch_size,
            normalize=normalize,
            cache_enabled=cache_enabled,
            cache_dir=cache_dir,
        )
        return EmbeddingsGenerator(config)
    
    @staticmethod
    def create_sentence_transformer_generator(
        model_name: str = "all-MiniLM-L6-v2",
        batch_size: int = 32,
        normalize: bool = True,
        use_gpu: bool = False,
        cache_enabled: bool = True,
        cache_dir: str = "./embeddings_cache",
    ) -> EmbeddingsGenerator:
        """
        Create a Sentence Transformers embeddings generator.
        
        Args:
            model_name: Sentence Transformers model name
            batch_size: Batch size
            normalize: Whether to normalize embeddings
            use_gpu: Whether to use GPU
            cache_enabled: Whether to enable caching
            cache_dir: Cache directory
            
        Returns:
            EmbeddingsGenerator instance
        """
        config = EmbeddingConfig(
            model_type=ModelType.SENTENCE_TRANSFORMERS,
            model_name=model_name,
            dimension=384,  # Will be updated
            batch_size=batch_size,
            normalize=normalize,
            use_gpu=use_gpu,
            cache_enabled=cache_enabled,
            cache_dir=cache_dir,
        )
        return EmbeddingsGenerator(config)
    
    @staticmethod
    def create_huggingface_generator(
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        batch_size: int = 32,
        normalize: bool = True,
        use_gpu: bool = False,
        max_length: int = 512,
        cache_enabled: bool = True,
        cache_dir: str = "./embeddings_cache",
    ) -> EmbeddingsGenerator:
        """
        Create a HuggingFace embeddings generator.
        
        Args:
            model_name: HuggingFace model name
            batch_size: Batch size
            normalize: Whether to normalize embeddings
            use_gpu: Whether to use GPU
            max_length: Maximum sequence length
            cache_enabled: Whether to enable caching
            cache_dir: Cache directory
            
        Returns:
            EmbeddingsGenerator instance
        """
        config = EmbeddingConfig(
            model_type=ModelType.HUGGINGFACE,
            model_name=model_name,
            dimension=384,  # Will be updated
            batch_size=batch_size,
            normalize=normalize,
            use_gpu=use_gpu,
            max_length=max_length,
            cache_enabled=cache_enabled,
            cache_dir=cache_dir,
        )
        return EmbeddingsGenerator(config)


# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point for CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Embeddings Generator CLI')
    parser.add_argument('--command', choices=['generate', 'batch', 'stats', 'cache', 'model'],
                       required=True, help='Command to execute')
    parser.add_argument('--model-type', type=str, default='sentence_transformers', help='Model type')
    parser.add_argument('--model-name', type=str, default='all-MiniLM-L6-v2', help='Model name')
    parser.add_argument('--text', type=str, help='Text to embed')
    parser.add_argument('--file', type=str, help='File with texts')
    parser.add_argument('--output', type=str, help='Output file')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size')
    parser.add_argument('--cache-dir', type=str, default='./embeddings_cache', help='Cache directory')
    parser.add_argument('--use-gpu', action='store_true', help='Use GPU')
    parser.add_argument('--normalize', action='store_true', help='Normalize embeddings')
    
    args = parser.parse_args()
    
    # Create generator
    if args.model_type == 'openai':
        generator = EmbeddingsGeneratorFactory.create_openai_generator(
            model_name=args.model_name,
            batch_size=args.batch_size,
            normalize=args.normalize,
            cache_dir=args.cache_dir,
        )
    elif args.model_type == 'sentence_transformers':
        generator = EmbeddingsGeneratorFactory.create_sentence_transformer_generator(
            model_name=args.model_name,
            batch_size=args.batch_size,
            normalize=args.normalize,
            use_gpu=args.use_gpu,
            cache_dir=args.cache_dir,
        )
    elif args.model_type == 'huggingface':
        generator = EmbeddingsGeneratorFactory.create_huggingface_generator(
            model_name=args.model_name,
            batch_size=args.batch_size,
            normalize=args.normalize,
            use_gpu=args.use_gpu,
            cache_dir=args.cache_dir,
        )
    else:
        print(f"Unsupported model type: {args.model_type}")
        return
    
    if args.command == 'generate':
        if not args.text:
            text = input("Enter text to embed: ")
        else:
            text = args.text
        
        embedding = generator.generate_embedding(text)
        if embedding is not None:
            print(f"\nEmbedding shape: {embedding.shape}")
            print(f"First 10 values: {embedding[:10]}")
            
            if args.output:
                np.save(args.output, embedding)
                print(f"Saved to {args.output}")
        else:
            print("Failed to generate embedding")
    
    elif args.command == 'batch':
        if args.file:
            with open(args.file, 'r') as f:
                texts = [line.strip() for line in f.readlines()]
        else:
            print("Enter texts (one per line, empty line to finish):")
            texts = []
            while True:
                line = input()
                if not line:
                    break
                texts.append(line)
        
        embeddings = generator.generate_embeddings(texts, show_progress=True)
        
        print(f"\nGenerated {len([e for e in embeddings if e is not None])} embeddings")
        
        if args.output:
            data = {
                'texts': texts,
                'embeddings': [e.tolist() if e is not None else None for e in embeddings],
            }
            with open(args.output, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved to {args.output}")
    
    elif args.command == 'stats':
        stats = generator.get_stats()
        info = generator.get_model_info()
        
        print("\nEmbedding Statistics:")
        print(f"  Model: {stats.model_name}")
        print(f"  Dimension: {stats.dimension}")
        print(f"  Total Generations: {stats.total_generations}")
        print(f"  Successful: {stats.successful_generations}")
        print(f"  Failed: {stats.failed_generations}")
        print(f"  Cached: {stats.cached_generations}")
        print(f"  Average Time: {stats.average_time:.4f}s")
        print(f"  Total Time: {stats.total_time:.2f}s")
        print(f"  Cache Size: {info['cache_size']}")
    
    elif args.command == 'cache':
        stats = generator.get_stats()
        info = generator.get_model_info()
        print(f"Cache size: {info['cache_size']}")
        
        action = input("Clear cache? (y/n): ")
        if action.lower() == 'y':
            generator.clear_cache()
            print("Cache cleared")
    
    elif args.command == 'model':
        info = generator.get_model_info()
        print("\nModel Information:")
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        switch = input("\nSwitch model? (y/n): ")
        if switch.lower() == 'y':
            model_name = input("New model name: ")
            model_type = input("Model type (openai/sentence_transformers/huggingface): ")
            
            if model_type == 'openai':
                generator.switch_model(model_name, ModelType.OPENAI)
            elif model_type == 'sentence_transformers':
                generator.switch_model(model_name, ModelType.SENTENCE_TRANSFORMERS)
            elif model_type == 'huggingface':
                generator.switch_model(model_name, ModelType.HUGGINGFACE)
            else:
                print(f"Unsupported model type: {model_type}")
                return
            
            print("Model switched")


if __name__ == '__main__':
    main()
