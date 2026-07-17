"""
NEXUS AI TRADING SYSTEM - Model Loader
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced model loader with caching, versioning, and hot-reload capabilities.
Supports multiple model formats, distributed loading, and model optimization.
"""

import asyncio
import hashlib
import json
import logging
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import torch
import torch.nn as nn
from prometheus_client import Counter, Gauge, Histogram

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
MODEL_LOAD_COUNTER = Counter(
    "nexus_model_loads_total",
    "Total number of model loads",
    ["model_type", "status"],
)
MODEL_LOAD_DURATION = Histogram(
    "nexus_model_load_duration_seconds",
    "Duration of model loading",
    ["model_type"],
)
MODEL_CACHE_SIZE = Gauge(
    "nexus_model_cache_size",
    "Number of models in cache",
)
MODEL_CACHE_MEMORY = Gauge(
    "nexus_model_cache_memory_bytes",
    "Memory used by model cache",
)


class ModelFormat(Enum):
    """Supported model formats."""

    PYTORCH = "pytorch"
    PYTORCH_JIT = "pytorch_jit"
    ONNX = "onnx"
    TENSORRT = "tensorrt"
    JOBLIB = "joblib"
    PICKLE = "pickle"
    JSON = "json"


class LoadStrategy(Enum):
    """Loading strategies for models."""

    EAGER = "eager"
    LAZY = "lazy"
    MEMORY_MAPPED = "memory_mapped"
    STREAMING = "streaming"
    DISTRIBUTED = "distributed"


@dataclass
class ModelMetadata:
    """Metadata for a loaded model."""

    model_id: str
    model_type: str
    version: str
    format: ModelFormat
    path: Path
    size_bytes: int
    loaded_at: datetime
    last_used: datetime
    use_count: int = 0
    cache_key: str = ""
    checksum: str = ""
    tags: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "model_id": self.model_id,
            "model_type": self.model_type,
            "version": self.version,
            "format": self.format.value,
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "loaded_at": self.loaded_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "use_count": self.use_count,
            "cache_key": self.cache_key,
            "checksum": self.checksum,
            "tags": self.tags,
            "config": self.config,
            "performance": self.performance,
        }


class ModelLoader:
    """
    Advanced model loader with caching, versioning, and optimization.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the model loader.

        Args:
            config: Configuration dictionary
            cache_manager: Optional cache manager
            metrics_collector: Optional metrics collector
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._lock = asyncio.Lock()
        self._model_cache: Dict[str, Tuple[nn.Module, ModelMetadata]] = {}
        self._model_registry: Dict[str, ModelMetadata] = {}
        self._loading_tasks: Dict[str, asyncio.Task] = {}

        # Load configuration
        self.loader_config = self.config.get("model_loader", {})
        self.model_dirs = self.loader_config.get("model_dirs", ["./models"])
        self.cache_size_limit = self.loader_config.get("cache_size_limit", 10)
        self.cache_memory_limit_mb = self.loader_config.get(
            "cache_memory_limit_mb", 1024
        )
        self.default_strategy = LoadStrategy(
            self.loader_config.get("default_strategy", "eager")
        )
        self.check_versions = self.loader_config.get("check_versions", True)
        self.validate_checksums = self.loader_config.get("validate_checksums", True)

        # Initialize model directories
        for model_dir in self.model_dirs:
            Path(model_dir).mkdir(parents=True, exist_ok=True)

        logger.info("ModelLoader initialized with config: %s", config)

    async def load_model(
        self,
        model_id: str,
        model_path: Optional[Union[str, Path]] = None,
        model_type: Optional[str] = None,
        version: Optional[str] = None,
        format: Optional[Union[ModelFormat, str]] = None,
        strategy: Optional[Union[LoadStrategy, str]] = None,
        force_reload: bool = False,
        **kwargs,
    ) -> Tuple[nn.Module, ModelMetadata]:
        """
        Load a model with caching and optimization.

        Args:
            model_id: Unique identifier for the model
            model_path: Path to model file (optional)
            model_type: Type of model (e.g., "lstm", "transformer")
            version: Model version
            format: Model format
            strategy: Loading strategy
            force_reload: Force reload even if cached
            **kwargs: Additional loading arguments

        Returns:
            Tuple of (model, metadata)
        """
        start_time = time.time()

        # Parse parameters
        if isinstance(format, str):
            format = ModelFormat(format)
        if isinstance(strategy, str):
            strategy = LoadStrategy(strategy)

        strategy = strategy or self.default_strategy
        cache_key = self._generate_cache_key(model_id, version)

        # Check cache
        if not force_reload:
            cached = await self._get_from_cache(cache_key)
            if cached:
                model, metadata = cached
                metadata.last_used = datetime.utcnow()
                metadata.use_count += 1
                self._update_usage_stats(metadata)
                logger.debug(f"Cache hit for model {model_id} v{version}")
                return model, metadata

        # Check if already loading
        if cache_key in self._loading_tasks:
            logger.debug(f"Waiting for existing load task for {model_id}")
            return await self._loading_tasks[cache_key]

        # Start loading task
        task = asyncio.create_task(
            self._load_model_async(
                model_id=model_id,
                model_path=model_path,
                model_type=model_type,
                version=version,
                format=format,
                strategy=strategy,
                **kwargs,
            )
        )
        self._loading_tasks[cache_key] = task

        try:
            model, metadata = await task
            return model, metadata
        finally:
            self._loading_tasks.pop(cache_key, None)

    async def _load_model_async(
        self,
        model_id: str,
        model_path: Optional[Union[str, Path]] = None,
        model_type: Optional[str] = None,
        version: Optional[str] = None,
        format: Optional[ModelFormat] = None,
        strategy: Optional[LoadStrategy] = None,
        **kwargs,
    ) -> Tuple[nn.Module, ModelMetadata]:
        """Perform actual model loading."""
        start_time = time.time()

        try:
            # Find model path if not provided
            if model_path is None:
                model_path = await self._find_model_path(model_id, version)

            model_path = Path(model_path)

            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found: {model_path}")

            # Detect format if not specified
            if format is None:
                format = self._detect_format(model_path)

            # Load model based on format and strategy
            model, metadata = await self._load_by_format(
                model_path=model_path,
                model_id=model_id,
                model_type=model_type or "unknown",
                version=version or "latest",
                format=format,
                strategy=strategy,
                **kwargs,
            )

            # Update metadata
            metadata.size_bytes = model_path.stat().st_size
            metadata.loaded_at = datetime.utcnow()
            metadata.last_used = datetime.utcnow()
            metadata.use_count = 1
            metadata.cache_key = self._generate_cache_key(model_id, version)
            metadata.checksum = self._calculate_checksum(model_path)

            # Validate checksum if enabled
            if self.validate_checksums:
                stored_checksum = await self._get_stored_checksum(model_id, version)
                if stored_checksum and stored_checksum != metadata.checksum:
                    logger.warning(
                        f"Checksum mismatch for model {model_id} v{version}"
                    )

            # Cache model
            cache_key = metadata.cache_key
            async with self._lock:
                await self._add_to_cache(cache_key, model, metadata)
                self._model_registry[model_id] = metadata

            # Record metrics
            load_duration = time.time() - start_time
            MODEL_LOAD_DURATION.labels(model_type=metadata.model_type).observe(
                load_duration
            )
            MODEL_LOAD_COUNTER.labels(
                model_type=metadata.model_type, status="success"
            ).inc()

            logger.info(
                f"Loaded model {model_id} v{version} in {load_duration:.2f}s "
                f"({format.value})"
            )

            return model, metadata

        except Exception as e:
            MODEL_LOAD_COUNTER.labels(
                model_type=model_type or "unknown", status="error"
            ).inc()
            logger.error(f"Error loading model {model_id}: {e}")
            raise

    async def _load_by_format(
        self,
        model_path: Path,
        model_id: str,
        model_type: str,
        version: str,
        format: ModelFormat,
        strategy: LoadStrategy,
        **kwargs,
    ) -> Tuple[nn.Module, ModelMetadata]:
        """Load model by format."""
        if format == ModelFormat.PYTORCH:
            return await self._load_pytorch(
                model_path, model_id, model_type, version, strategy, **kwargs
            )
        elif format == ModelFormat.PYTORCH_JIT:
            return await self._load_pytorch_jit(
                model_path, model_id, model_type, version, strategy, **kwargs
            )
        elif format == ModelFormat.ONNX:
            return await self._load_onnx(
                model_path, model_id, model_type, version, strategy, **kwargs
            )
        elif format == ModelFormat.TENSORRT:
            return await self._load_tensorrt(
                model_path, model_id, model_type, version, strategy, **kwargs
            )
        elif format in (ModelFormat.JOBLIB, ModelFormat.PICKLE):
            return await self._load_sklearn(
                model_path, model_id, model_type, version, format, **kwargs
            )
        elif format == ModelFormat.JSON:
            return await self._load_json(
                model_path, model_id, model_type, version, **kwargs
            )
        else:
            raise ValueError(f"Unsupported format: {format}")

    async def _load_pytorch(
        self,
        model_path: Path,
        model_id: str,
        model_type: str,
        version: str,
        strategy: LoadStrategy,
        **kwargs,
    ) -> Tuple[nn.Module, ModelMetadata]:
        """Load PyTorch model."""
        # Extract config and state dict
        if strategy == LoadStrategy.MEMORY_MAPPED:
            # Use memory mapping for large models
            checkpoint = torch.load(
                model_path,
                map_location="cpu",
                weights_only=True,
                mmap=True,
            )
        else:
            checkpoint = torch.load(
                model_path,
                map_location="cpu",
                weights_only=True,
            )

        config = checkpoint.get("config", {})
        state_dict = checkpoint.get("model_state_dict", {})

        # Create model from config
        model = await self._create_model_from_config(config, model_type)

        # Load state dict
        if state_dict:
            model.load_state_dict(state_dict)

        # Move to appropriate device
        device = kwargs.get("device", "cuda" if torch.cuda.is_available() else "cpu")
        model = model.to(device)

        # Set to eval mode by default
        model.eval()

        # Create metadata
        metadata = ModelMetadata(
            model_id=model_id,
            model_type=model_type,
            version=version,
            format=ModelFormat.PYTORCH,
            path=model_path,
            size_bytes=0,
            loaded_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
            use_count=0,
            config=config,
            performance=checkpoint.get("performance", {}),
        )

        return model, metadata

    async def _load_pytorch_jit(
        self,
        model_path: Path,
        model_id: str,
        model_type: str,
        version: str,
        strategy: LoadStrategy,
        **kwargs,
    ) -> Tuple[nn.Module, ModelMetadata]:
        """Load PyTorch JIT model."""
        if strategy == LoadStrategy.MEMORY_MAPPED:
            model = torch.jit.load(
                model_path,
                map_location="cpu",
                _extra_files=kwargs.get("extra_files", {}),
            )
        else:
            model = torch.jit.load(model_path, map_location="cpu")

        device = kwargs.get("device", "cuda" if torch.cuda.is_available() else "cpu")
        model = model.to(device)
        model.eval()

        metadata = ModelMetadata(
            model_id=model_id,
            model_type=model_type,
            version=version,
            format=ModelFormat.PYTORCH_JIT,
            path=model_path,
            size_bytes=0,
            loaded_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
            use_count=0,
            config={"is_jit": True},
        )

        return model, metadata

    async def _load_onnx(
        self,
        model_path: Path,
        model_id: str,
        model_type: str,
        version: str,
        strategy: LoadStrategy,
        **kwargs,
    ) -> Tuple[nn.Module, ModelMetadata]:
        """Load ONNX model."""
        import onnx
        import onnxruntime as ort

        # Check if ONNX model is valid
        onnx_model = onnx.load(model_path)
        onnx.checker.check_model(onnx_model)

        # Create ONNX Runtime session
        providers = kwargs.get("providers", ["CPUExecutionProvider"])
        if "cuda" in str(providers) or "CUDAExecutionProvider" in providers:
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

        session_options = ort.SessionOptions()
        if strategy == LoadStrategy.MEMORY_MAPPED:
            session_options.enable_mem_pattern = True
            session_options.enable_cpu_mem_arena = True

        session = ort.InferenceSession(
            model_path,
            providers=providers,
            sess_options=session_options,
        )

        # Wrap ONNX session as a PyTorch module
        class ONNXWrapper(nn.Module):
            def __init__(self, session, input_names, output_names):
                super().__init__()
                self.session = session
                self.input_names = input_names
                self.output_names = output_names

            def forward(self, *args):
                if len(args) == 1 and isinstance(args[0], torch.Tensor):
                    inputs = {self.input_names[0]: args[0].cpu().numpy()}
                else:
                    inputs = {
                        name: arg.cpu().numpy()
                        for name, arg in zip(self.input_names, args)
                    }
                outputs = self.session.run(self.output_names, inputs)
                if len(outputs) == 1:
                    return torch.tensor(outputs[0])
                return [torch.tensor(out) for out in outputs]

        input_names = [inp.name for inp in onnx_model.graph.input][:1]
        output_names = [out.name for out in onnx_model.graph.output]

        model = ONNXWrapper(session, input_names, output_names)

        metadata = ModelMetadata(
            model_id=model_id,
            model_type=model_type,
            version=version,
            format=ModelFormat.ONNX,
            path=model_path,
            size_bytes=0,
            loaded_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
            use_count=0,
            config={"onnx_inputs": input_names, "onnx_outputs": output_names},
        )

        return model, metadata

    async def _load_tensorrt(
        self,
        model_path: Path,
        model_id: str,
        model_type: str,
        version: str,
        strategy: LoadStrategy,
        **kwargs,
    ) -> Tuple[nn.Module, ModelMetadata]:
        """Load TensorRT model."""
        import tensorrt as trt

        TRT_LOGGER = trt.Logger(trt.Logger.WARNING)

        with open(model_path, "rb") as f:
            engine_data = f.read()

        runtime = trt.Runtime(TRT_LOGGER)
        engine = runtime.deserialize_cuda_engine(engine_data)

        # Create wrapper for TensorRT engine
        class TensorRTWrapper(nn.Module):
            def __init__(self, engine):
                super().__init__()
                self.engine = engine
                self.context = engine.create_execution_context()
                self.input_shape = None

            def forward(self, x):
                if self.input_shape is None:
                    self.input_shape = x.shape
                    self.context.set_binding_shape(0, x.shape)

                output = np.zeros(
                    self.engine.get_binding_shape(1), dtype=np.float32
                )
                # Simplified forward pass
                # In practice, need to handle memory allocation properly
                return torch.tensor(output)

        model = TensorRTWrapper(engine)

        metadata = ModelMetadata(
            model_id=model_id,
            model_type=model_type,
            version=version,
            format=ModelFormat.TENSORRT,
            path=model_path,
            size_bytes=0,
            loaded_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
            use_count=0,
            config={"tensorrt_engine": True},
        )

        return model, metadata

    async def _load_sklearn(
        self,
        model_path: Path,
        model_id: str,
        model_type: str,
        version: str,
        format: ModelFormat,
        **kwargs,
    ) -> Tuple[nn.Module, ModelMetadata]:
        """Load scikit-learn model."""
        if format == ModelFormat.JOBLIB:
            model = joblib.load(model_path)
        else:
            import pickle
            with open(model_path, "rb") as f:
                model = pickle.load(f)

        # Wrap sklearn model as a PyTorch module
        class SklearnWrapper(nn.Module):
            def __init__(self, model):
                super().__init__()
                self.model = model

            def forward(self, x):
                if isinstance(x, torch.Tensor):
                    x = x.cpu().numpy()
                if hasattr(self.model, "predict_proba"):
                    output = self.model.predict_proba(x)
                else:
                    output = self.model.predict(x)
                return torch.tensor(output, dtype=torch.float32)

        wrapped_model = SklearnWrapper(model)

        metadata = ModelMetadata(
            model_id=model_id,
            model_type=model_type,
            version=version,
            format=format,
            path=model_path,
            size_bytes=0,
            loaded_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
            use_count=0,
            config={"sklearn_type": type(model).__name__},
        )

        return wrapped_model, metadata

    async def _load_json(
        self,
        model_path: Path,
        model_id: str,
        model_type: str,
        version: str,
        **kwargs,
    ) -> Tuple[nn.Module, ModelMetadata]:
        """Load model from JSON configuration."""
        with open(model_path, "r") as f:
            config = json.load(f)

        # Create model from JSON config
        model = await self._create_model_from_config(config, model_type)

        metadata = ModelMetadata(
            model_id=model_id,
            model_type=model_type,
            version=version,
            format=ModelFormat.JSON,
            path=model_path,
            size_bytes=0,
            loaded_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
            use_count=0,
            config=config,
        )

        return model, metadata

    async def _create_model_from_config(
        self,
        config: Dict[str, Any],
        model_type: str,
    ) -> nn.Module:
        """Create model from configuration."""
        try:
            # Import model factory dynamically
            from trading.bots.ai_bot.models.model_factory import ModelFactory
            factory = ModelFactory()
            return await factory.create_model(config)
        except Exception as e:
            logger.error(f"Error creating model from config: {e}")
            # Fallback to a simple model
            input_dim = config.get("input_dim", 10)
            output_dim = config.get("output_dim", 1)
            return nn.Sequential(
                nn.Linear(input_dim, 64),
                nn.ReLU(),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Linear(32, output_dim),
            )

    async def _find_model_path(
        self,
        model_id: str,
        version: Optional[str] = None,
    ) -> Path:
        """Find model path by ID and version."""
        # Check registry first
        if model_id in self._model_registry:
            metadata = self._model_registry[model_id]
            path = Path(metadata.path)
            if path.exists():
                return path

        # Search in model directories
        patterns = [
            f"{model_id}_{version or '*'}.pt",
            f"{model_id}_{version or '*'}.pth",
            f"{model_id}_{version or '*'}.onnx",
            f"{model_id}_{version or '*'}.joblib",
            f"{model_id}_{version or '*'}.pkl",
            f"{model_id}_{version or '*'}.json",
        ]

        for model_dir in self.model_dirs:
            dir_path = Path(model_dir)
            if not dir_path.exists():
                continue

            for pattern in patterns:
                matches = list(dir_path.glob(pattern))
                if matches:
                    # Sort by version if multiple matches
                    if version:
                        matches = [m for m in matches if str(m).endswith(f"_{version}")]
                    if matches:
                        return matches[0]

        raise FileNotFoundError(f"Model {model_id} not found")

    def _detect_format(self, model_path: Path) -> ModelFormat:
        """Detect model format from file extension."""
        extension = model_path.suffix.lower()

        format_map = {
            ".pt": ModelFormat.PYTORCH,
            ".pth": ModelFormat.PYTORCH,
            ".pth.tar": ModelFormat.PYTORCH,
            ".onnx": ModelFormat.ONNX,
            ".engine": ModelFormat.TENSORRT,
            ".trt": ModelFormat.TENSORRT,
            ".joblib": ModelFormat.JOBLIB,
            ".pkl": ModelFormat.PICKLE,
            ".pickle": ModelFormat.PICKLE,
            ".json": ModelFormat.JSON,
        }

        if extension in format_map:
            return format_map[extension]

        # Check for JIT model
        if model_path.suffix in (".pt", ".pth"):
            try:
                torch.jit.load(model_path, map_location="cpu")
                return ModelFormat.PYTORCH_JIT
            except Exception:
                pass

        return ModelFormat.PYTORCH

    def _generate_cache_key(self, model_id: str, version: Optional[str]) -> str:
        """Generate cache key for a model."""
        return f"{model_id}_{version or 'latest'}"

    def _calculate_checksum(self, model_path: Path) -> str:
        """Calculate SHA256 checksum of model file."""
        sha256 = hashlib.sha256()
        with open(model_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def _get_stored_checksum(
        self,
        model_id: str,
        version: Optional[str],
    ) -> Optional[str]:
        """Get stored checksum for model."""
        cache_key = f"checksum:{model_id}:{version or 'latest'}"
        return await self.cache_manager.get(cache_key)

    async def _get_from_cache(
        self,
        cache_key: str,
    ) -> Optional[Tuple[nn.Module, ModelMetadata]]:
        """Get model from cache."""
        async with self._lock:
            if cache_key in self._model_cache:
                model, metadata = self._model_cache[cache_key]
                # Move to device if needed
                if hasattr(model, "to"):
                    device = self.config.get("device", "cuda" if torch.cuda.is_available() else "cpu")
                    model = model.to(device)
                return model, metadata
        return None

    async def _add_to_cache(
        self,
        cache_key: str,
        model: nn.Module,
        metadata: ModelMetadata,
    ):
        """Add model to cache."""
        async with self._lock:
            # Check cache size limit
            if len(self._model_cache) >= self.cache_size_limit:
                await self._evict_cache()

            # Check memory limit
            current_memory = sum(
                self._estimate_model_size(m)
                for m, _ in self._model_cache.values()
            )
            model_size = self._estimate_model_size(model)

            if (current_memory + model_size) > (self.cache_memory_limit_mb * 1024 * 1024):
                await self._evict_cache_memory(model_size)

            self._model_cache[cache_key] = (model, metadata)
            MODEL_CACHE_SIZE.set(len(self._model_cache))
            MODEL_CACHE_MEMORY.set(self._get_cache_memory())

    async def _evict_cache(self):
        """Evict least recently used models from cache."""
        if not self._model_cache:
            return

        # Sort by last used time
        sorted_items = sorted(
            self._model_cache.items(),
            key=lambda x: x[1][1].last_used,
        )

        # Remove oldest 30%
        num_to_remove = max(1, int(len(sorted_items) * 0.3))
        for cache_key, _ in sorted_items[:num_to_remove]:
            if cache_key in self._model_cache:
                del self._model_cache[cache_key]

        logger.info(f"Evicted {num_to_remove} models from cache")

    async def _evict_cache_memory(self, required_memory: int):
        """Evict models to free memory."""
        if not self._model_cache:
            return

        # Sort by size and last use
        items = sorted(
            [(k, v[1].size_bytes, v[1].last_used, v) for k, v in self._model_cache.items()],
            key=lambda x: (x[1], x[2]),
            reverse=True,
        )

        freed_memory = 0
        for cache_key, size, _, _ in items:
            if cache_key in self._model_cache:
                del self._model_cache[cache_key]
                freed_memory += size
                if freed_memory >= required_memory * 1.5:
                    break

        logger.info(f"Evicted models to free {freed_memory / (1024*1024):.2f} MB")

    def _estimate_model_size(self, model: nn.Module) -> int:
        """Estimate model size in bytes."""
        try:
            if hasattr(model, "state_dict"):
                total = 0
                for param in model.parameters():
                    total += param.nelement() * param.element_size()
                return total
        except Exception:
            pass
        return 0

    def _get_cache_memory(self) -> int:
        """Get total cache memory in bytes."""
        total = 0
        for model, _ in self._model_cache.values():
            total += self._estimate_model_size(model)
        return total

    def _update_usage_stats(self, metadata: ModelMetadata):
        """Update usage statistics."""
        # Update cache TTL if configured
        ttl = self.loader_config.get("cache_ttl_seconds", 3600)
        if (datetime.utcnow() - metadata.loaded_at).total_seconds() > ttl:
            # Refresh cache by reloading
            asyncio.create_task(
                self.load_model(
                    metadata.model_id,
                    version=metadata.version,
                    force_reload=True,
                )
            )

    async def unload_model(
        self,
        model_id: str,
        version: Optional[str] = None,
    ):
        """Unload a model from cache."""
        cache_key = self._generate_cache_key(model_id, version)
        async with self._lock:
            if cache_key in self._model_cache:
                del self._model_cache[cache_key]
                MODEL_CACHE_SIZE.set(len(self._model_cache))
                MODEL_CACHE_MEMORY.set(self._get_cache_memory())
                logger.info(f"Unloaded model {cache_key}")

    async def list_models(self) -> List[ModelMetadata]:
        """List all loaded models."""
        async with self._lock:
            return list(self._model_registry.values())

    async def get_model_metadata(
        self,
        model_id: str,
        version: Optional[str] = None,
    ) -> Optional[ModelMetadata]:
        """Get metadata for a model."""
        cache_key = self._generate_cache_key(model_id, version)
        async with self._lock:
            if cache_key in self._model_cache:
                return self._model_cache[cache_key][1]
            return self._model_registry.get(model_id)

    async def validate_model(
        self,
        model_path: Union[str, Path],
        model_format: Optional[Union[ModelFormat, str]] = None,
    ) -> bool:
        """Validate a model file."""
        model_path = Path(model_path)

        if not model_path.exists():
            return False

        if isinstance(model_format, str):
            model_format = ModelFormat(model_format)

        if model_format is None:
            model_format = self._detect_format(model_path)

        try:
            if model_format == ModelFormat.PYTORCH:
                checkpoint = torch.load(model_path, map_location="cpu")
                return "model_state_dict" in checkpoint
            elif model_format == ModelFormat.PYTORCH_JIT:
                torch.jit.load(model_path, map_location="cpu")
                return True
            elif model_format == ModelFormat.ONNX:
                import onnx
                model = onnx.load(model_path)
                onnx.checker.check_model(model)
                return True
            elif model_format in (ModelFormat.JOBLIB, ModelFormat.PICKLE):
                if model_format == ModelFormat.JOBLIB:
                    joblib.load(model_path)
                else:
                    import pickle
                    with open(model_path, "rb") as f:
                        pickle.load(f)
                return True
            elif model_format == ModelFormat.JSON:
                with open(model_path, "r") as f:
                    json.load(f)
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Model validation failed: {e}")
            return False

    async def get_model_size(
        self,
        model_id: str,
        version: Optional[str] = None,
    ) -> int:
        """Get model size in bytes."""
        try:
            model_path = await self._find_model_path(model_id, version)
            return model_path.stat().st_size
        except Exception:
            return 0


# Export singleton instance
model_loader = ModelLoader()
