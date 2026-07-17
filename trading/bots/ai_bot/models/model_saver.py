"""
NEXUS AI TRADING SYSTEM - Model Saver
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced model saver with multiple format support, compression, encryption,
versioning, and backup capabilities.
"""

import asyncio
import gzip
import hashlib
import json
import pickle
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import aiofiles
import joblib
import torch
import torch.nn as nn
from cryptography.fernet import Fernet
from prometheus_client import Counter, Histogram

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector

logger = get_logger(__name__)

# Prometheus metrics
MODEL_SAVE_COUNTER = Counter(
    "nexus_model_saves_total",
    "Total number of model saves",
    ["format", "status"],
)
MODEL_SAVE_DURATION = Histogram(
    "nexus_model_save_duration_seconds",
    "Duration of model saves",
    ["format"],
)
MODEL_SAVE_SIZE = Histogram(
    "nexus_model_save_size_bytes",
    "Size of saved models",
    ["format"],
)


class SaveFormat(Enum):
    """Supported save formats."""

    PYTORCH = "pytorch"
    PYTORCH_JIT = "pytorch_jit"
    ONNX = "onnx"
    TENSORRT = "tensorrt"
    JOBLIB = "joblib"
    PICKLE = "pickle"
    JSON = "json"
    SAFETENSORS = "safetensors"


class CompressionType(Enum):
    """Compression types."""

    NONE = "none"
    GZIP = "gzip"
    ZSTD = "zstd"
    LZMA = "lzma"
    BROTLI = "brotli"


@dataclass
class SaveConfig:
    """Configuration for model saving."""

    format: SaveFormat
    compression: CompressionType = CompressionType.NONE
    encrypt: bool = False
    include_metadata: bool = True
    include_optimizer: bool = False
    include_config: bool = True
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    compression_level: int = 6
    backup: bool = True
    max_backups: int = 5


@dataclass
class SaveResult:
    """Result of a model save operation."""

    path: Path
    format: SaveFormat
    compression: CompressionType
    size_bytes: int
    original_size_bytes: int
    compression_ratio: float
    checksum: str
    timestamp: datetime
    metadata: Dict[str, Any]
    backup_path: Optional[Path] = None
    duration_seconds: float = 0.0


class ModelSaver:
    """
    Advanced model saver with multiple format support and optimization.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the model saver.

        Args:
            config: Configuration dictionary
            metrics_collector: Metrics collector instance
        """
        self.config = config or {}
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._lock = asyncio.Lock()
        self._encryption_key: Optional[bytes] = None

        # Load configuration
        self.saver_config = self.config.get("model_saver", {})
        self.default_format = SaveFormat(
            self.saver_config.get("default_format", "pytorch")
        )
        self.default_compression = CompressionType(
            self.saver_config.get("default_compression", "gzip")
        )
        self.save_dir = Path(self.saver_config.get("save_dir", "./models/saved"))
        self.backup_dir = Path(self.saver_config.get("backup_dir", "./models/backups"))
        self.encryption_key_path = Path(
            self.saver_config.get("encryption_key_path", "./.keys/model_key.key")
        )

        # Create directories
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Load encryption key if exists
        if self.encryption_key_path.exists():
            self._load_encryption_key()

        logger.info("ModelSaver initialized with config: %s", config)

    async def save_model(
        self,
        model: nn.Module,
        model_id: str,
        config: Union[SaveConfig, Dict[str, Any]],
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> SaveResult:
        """
        Save a model with specified configuration.

        Args:
            model: PyTorch model to save
            model_id: Model identifier
            config: Save configuration
            additional_data: Additional data to include

        Returns:
            SaveResult object
        """
        start_time = time.time()

        # Parse config
        if isinstance(config, dict):
            config = SaveConfig(
                format=SaveFormat(config.get("format", self.default_format.value)),
                compression=CompressionType(
                    config.get("compression", self.default_compression.value)
                ),
                encrypt=config.get("encrypt", False),
                include_metadata=config.get("include_metadata", True),
                include_optimizer=config.get("include_optimizer", False),
                include_config=config.get("include_config", True),
                version=config.get("version", "1.0.0"),
                tags=config.get("tags", []),
                metadata=config.get("metadata", {}),
                compression_level=config.get("compression_level", 6),
                backup=config.get("backup", True),
                max_backups=config.get("max_backups", 5),
            )

        # Prepare save data
        save_data = await self._prepare_save_data(
            model=model,
            model_id=model_id,
            config=config,
            additional_data=additional_data,
        )

        # Determine file extension
        extension = self._get_extension(config.format)

        # Build save path
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{model_id}_{config.version}_{timestamp}{extension}"
        save_path = self.save_dir / filename

        # Handle compression
        if config.compression != CompressionType.NONE:
            compressed_extension = self._get_compression_extension(
                config.compression
            )
            save_path = save_path.with_suffix(
                f"{save_path.suffix}{compressed_extension}"
            )

        # Save the model
        try:
            async with self._lock:
                # Save to temporary file first
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    tmp_path = Path(tmp_file.name)
                    await self._write_model(
                        tmp_path, save_data, config.format, config.compression
                    )

                    # Calculate checksum
                    checksum = await self._calculate_checksum(tmp_path)

                    # Move to final location
                    shutil.move(str(tmp_path), str(save_path))

                # Create backup if enabled
                backup_path = None
                if config.backup:
                    backup_path = await self._create_backup(
                        save_path, config.max_backups
                    )

                # Get file sizes
                size_bytes = save_path.stat().st_size
                original_size = len(pickle.dumps(save_data))

                # Create result
                result = SaveResult(
                    path=save_path,
                    format=config.format,
                    compression=config.compression,
                    size_bytes=size_bytes,
                    original_size_bytes=original_size,
                    compression_ratio=original_size / size_bytes if size_bytes > 0 else 1.0,
                    checksum=checksum,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "model_id": model_id,
                        "version": config.version,
                        "tags": config.tags,
                        **config.metadata,
                    },
                    backup_path=backup_path,
                    duration_seconds=time.time() - start_time,
                )

                # Record metrics
                MODEL_SAVE_COUNTER.labels(
                    format=config.format.value,
                    status="success",
                ).inc()
                MODEL_SAVE_DURATION.labels(
                    format=config.format.value,
                ).observe(result.duration_seconds)
                MODEL_SAVE_SIZE.labels(
                    format=config.format.value,
                ).observe(size_bytes)

                logger.info(
                    f"Saved model {model_id} v{config.version} to {save_path} "
                    f"({size_bytes / 1024:.2f} KB, {result.duration_seconds:.2f}s)"
                )

                return result

        except Exception as e:
            MODEL_SAVE_COUNTER.labels(
                format=config.format.value,
                status="error",
            ).inc()
            logger.error(f"Error saving model {model_id}: {e}")
            raise

    async def _prepare_save_data(
        self,
        model: nn.Module,
        model_id: str,
        config: SaveConfig,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Prepare data for saving."""
        save_data = {
            "model_id": model_id,
            "version": config.version,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Include model state dict
        if config.format == SaveFormat.PYTORCH:
            save_data["model_state_dict"] = model.state_dict()
        elif config.format == SaveFormat.PYTORCH_JIT:
            save_data["model_jit"] = torch.jit.trace(model, torch.randn(1, 10))

        # Include optimizer state if requested
        if config.include_optimizer and hasattr(model, "optimizer"):
            save_data["optimizer_state_dict"] = model.optimizer.state_dict()

        # Include config
        if config.include_config:
            save_data["config"] = self._extract_model_config(model)

        # Include metadata
        if config.include_metadata:
            save_data["metadata"] = {
                "model_type": self._get_model_type(model),
                "parameter_count": self._count_parameters(model),
                "tags": config.tags,
                **config.metadata,
            }

        # Include additional data
        if additional_data:
            save_data.update(additional_data)

        # Encrypt if requested
        if config.encrypt:
            save_data = await self._encrypt_data(save_data)

        return save_data

    async def _write_model(
        self,
        path: Path,
        data: Dict[str, Any],
        format: SaveFormat,
        compression: CompressionType,
    ):
        """Write model data to file."""
        # Convert format
        if format == SaveFormat.PYTORCH:
            serialized = pickle.dumps(data)
        elif format == SaveFormat.PICKLE:
            serialized = pickle.dumps(data)
        elif format == SaveFormat.JOBLIB:
            # Write using joblib
            joblib.dump(data, path)
            return
        elif format == SaveFormat.JSON:
            serialized = json.dumps(data).encode()
        elif format == SaveFormat.SAFETENSORS:
            # Handle safetensors format
            from safetensors.torch import save_file

            # Extract tensors
            tensors = {}
            if "model_state_dict" in data:
                for key, value in data["model_state_dict"].items():
                    if isinstance(value, torch.Tensor):
                        tensors[key] = value
            save_file(tensors, path)
            return
        else:
            raise ValueError(f"Unsupported format: {format}")

        # Apply compression
        if compression == CompressionType.GZIP:
            serialized = gzip.compress(serialized)
        elif compression == CompressionType.ZSTD:
            import zstandard as zstd

            compressor = zstd.ZstdCompressor(level=6)
            serialized = compressor.compress(serialized)
        elif compression == CompressionType.LZMA:
            import lzma

            serialized = lzma.compress(serialized)
        elif compression == CompressionType.BROTLI:
            import brotli

            serialized = brotli.compress(serialized)

        # Write to file
        async with aiofiles.open(path, "wb") as f:
            await f.write(serialized)

    async def _calculate_checksum(self, path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256 = hashlib.sha256()

        async with aiofiles.open(path, "rb") as f:
            while True:
                chunk = await f.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)

        return sha256.hexdigest()

    async def _create_backup(self, save_path: Path, max_backups: int) -> Path:
        """Create a backup of the saved model."""
        # Create backup directory for this model
        model_backup_dir = self.backup_dir / save_path.stem.split("_")[0]
        model_backup_dir.mkdir(parents=True, exist_ok=True)

        # Backup filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{save_path.stem}_{timestamp}{save_path.suffix}"
        backup_path = model_backup_dir / backup_filename

        # Copy file
        shutil.copy2(save_path, backup_path)

        # Cleanup old backups
        await self._cleanup_backups(model_backup_dir, max_backups)

        return backup_path

    async def _cleanup_backups(self, backup_dir: Path, max_backups: int):
        """Clean up old backups."""
        if not backup_dir.exists():
            return

        # Get all backup files
        backup_files = sorted(
            backup_dir.glob("*"),
            key=lambda x: x.stat().st_mtime,
        )

        # Remove old backups
        for old_file in backup_files[:-max_backups]:
            old_file.unlink()
            logger.debug(f"Removed old backup: {old_file}")

    def _get_extension(self, format: SaveFormat) -> str:
        """Get file extension for format."""
        extensions = {
            SaveFormat.PYTORCH: ".pt",
            SaveFormat.PYTORCH_JIT: ".jit.pt",
            SaveFormat.ONNX: ".onnx",
            SaveFormat.TENSORRT: ".engine",
            SaveFormat.JOBLIB: ".joblib",
            SaveFormat.PICKLE: ".pkl",
            SaveFormat.JSON: ".json",
            SaveFormat.SAFETENSORS: ".safetensors",
        }
        return extensions.get(format, ".pt")

    def _get_compression_extension(self, compression: CompressionType) -> str:
        """Get file extension for compression."""
        extensions = {
            CompressionType.NONE: "",
            CompressionType.GZIP: ".gz",
            CompressionType.ZSTD: ".zst",
            CompressionType.LZMA: ".lzma",
            CompressionType.BROTLI: ".br",
        }
        return extensions.get(compression, "")

    def _extract_model_config(self, model: nn.Module) -> Dict[str, Any]:
        """Extract model configuration."""
        config = {
            "model_type": self._get_model_type(model),
            "parameter_count": self._count_parameters(model),
            "device": next(model.parameters()).device.type,
        }

        # Try to extract architecture-specific config
        if hasattr(model, "config"):
            if isinstance(model.config, dict):
                config.update(model.config)
            elif hasattr(model.config, "__dict__"):
                config.update(model.config.__dict__)

        return config

    def _get_model_type(self, model: nn.Module) -> str:
        """Get model type string."""
        return type(model).__name__

    def _count_parameters(self, model: nn.Module) -> int:
        """Count model parameters."""
        return sum(p.numel() for p in model.parameters())

    def _load_encryption_key(self):
        """Load encryption key from file."""
        try:
            with open(self.encryption_key_path, "rb") as f:
                self._encryption_key = f.read()
        except Exception as e:
            logger.warning(f"Failed to load encryption key: {e}")

    async def _encrypt_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt data with Fernet."""
        if self._encryption_key is None:
            # Generate new key
            self._encryption_key = Fernet.generate_key()
            # Save key
            self.encryption_key_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.encryption_key_path, "wb") as f:
                f.write(self._encryption_key)

        fernet = Fernet(self._encryption_key)
        serialized = pickle.dumps(data)
        encrypted = fernet.encrypt(serialized)

        return {"encrypted": True, "data": encrypted}

    async def load_saved_model(
        self,
        model_path: Union[str, Path],
        encryption_key: Optional[bytes] = None,
    ) -> Tuple[nn.Module, Dict[str, Any]]:
        """
        Load a saved model.

        Args:
            model_path: Path to model file
            encryption_key: Optional encryption key

        Returns:
            Tuple of (model, metadata)
        """
        model_path = Path(model_path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # Detect format
        format = self._detect_format(model_path)

        # Read file
        async with aiofiles.open(model_path, "rb") as f:
            data = await f.read()

        # Decompress if needed
        data = self._decompress_data(data, model_path.suffix)

        # Decrypt if needed
        if self._is_encrypted(data):
            key = encryption_key or self._encryption_key
            if key is None:
                raise ValueError("Encryption key required but not provided")
            data = self._decrypt_data(data, key)

        # Deserialize
        if format == SaveFormat.PYTORCH:
            loaded_data = pickle.loads(data)
        elif format == SaveFormat.PICKLE:
            loaded_data = pickle.loads(data)
        elif format == SaveFormat.JOBLIB:
            loaded_data = joblib.load(model_path)
        elif format == SaveFormat.JSON:
            loaded_data = json.loads(data)
        elif format == SaveFormat.SAFETENSORS:
            from safetensors.torch import load_file

            tensors = load_file(model_path)
            loaded_data = {"model_state_dict": tensors}
        elif format == SaveFormat.PYTORCH_JIT:
            loaded_data = {"model_jit": torch.jit.load(model_path)}
        else:
            raise ValueError(f"Unsupported format: {format}")

        # Extract model
        model = self._extract_model(loaded_data, format)

        return model, loaded_data

    def _detect_format(self, path: Path) -> SaveFormat:
        """Detect format from file extension."""
        suffix = path.suffix.lower()

        # Handle compressed files
        if suffix in [".gz", ".zst", ".lzma", ".br"]:
            base_suffix = Path(path.stem).suffix.lower()
            return self._detect_format_by_extension(base_suffix)

        return self._detect_format_by_extension(suffix)

    def _detect_format_by_extension(self, extension: str) -> SaveFormat:
        """Detect format by extension."""
        format_map = {
            ".pt": SaveFormat.PYTORCH,
            ".pth": SaveFormat.PYTORCH,
            ".jit.pt": SaveFormat.PYTORCH_JIT,
            ".onnx": SaveFormat.ONNX,
            ".engine": SaveFormat.TENSORRT,
            ".joblib": SaveFormat.JOBLIB,
            ".pkl": SaveFormat.PICKLE,
            ".pickle": SaveFormat.PICKLE,
            ".json": SaveFormat.JSON,
            ".safetensors": SaveFormat.SAFETENSORS,
        }
        return format_map.get(extension, SaveFormat.PYTORCH)

    def _decompress_data(self, data: bytes, suffix: str) -> bytes:
        """Decompress data based on suffix."""
        if suffix == ".gz":
            return gzip.decompress(data)
        elif suffix == ".zst":
            import zstandard as zstd

            decompressor = zstd.ZstdDecompressor()
            return decompressor.decompress(data)
        elif suffix == ".lzma":
            import lzma

            return lzma.decompress(data)
        elif suffix == ".br":
            import brotli

            return brotli.decompress(data)
        return data

    def _is_encrypted(self, data: bytes) -> bool:
        """Check if data is encrypted."""
        try:
            import pickle

            test_data = pickle.loads(data)
            return test_data.get("encrypted", False)
        except Exception:
            return False

    def _decrypt_data(self, data: bytes, key: bytes) -> bytes:
        """Decrypt data with Fernet."""
        fernet = Fernet(key)
        loaded = pickle.loads(data)
        decrypted = fernet.decrypt(loaded["data"])
        return decrypted

    def _extract_model(
        self,
        loaded_data: Dict[str, Any],
        format: SaveFormat,
    ) -> nn.Module:
        """Extract model from loaded data."""
        if format == SaveFormat.PYTORCH:
            # Need to create model from config first
            config = loaded_data.get("config", {})
            model_type = config.get("model_type", "LSTMModel")

            # Try to dynamically import and create model
            try:
                # Import model factory
                from trading.bots.ai_bot.models.model_factory import ModelFactory

                factory = ModelFactory()
                # Create model
                model = asyncio.run(factory.create_model(config))
                # Load state dict
                if "model_state_dict" in loaded_data:
                    model.load_state_dict(loaded_data["model_state_dict"])
                return model
            except Exception as e:
                logger.error(f"Failed to recreate model: {e}")
                # Return a simple model
                return nn.Linear(10, 1)

        elif format == SaveFormat.PYTORCH_JIT:
            return loaded_data.get("model_jit")

        elif format in [SaveFormat.JOBLIB, SaveFormat.PICKLE]:
            # For sklearn models, wrap them
            class SklearnWrapper(nn.Module):
                def __init__(self, model):
                    super().__init__()
                    self.model = model

                def forward(self, x):
                    if isinstance(x, torch.Tensor):
                        x = x.cpu().numpy()
                    return torch.tensor(self.model.predict(x), dtype=torch.float32)

            if "model" in loaded_data:
                return SklearnWrapper(loaded_data["model"])
            else:
                return nn.Linear(10, 1)

        elif format == SaveFormat.SAFETENSORS:
            # Create model from tensors
            class TensorModel(nn.Module):
                def __init__(self, tensors):
                    super().__init__()
                    self.tensors = tensors

                def forward(self, x):
                    # Just pass through for now
                    return x

            return TensorModel(loaded_data)

        return nn.Linear(10, 1)

    async def create_checkpoint(
        self,
        model: nn.Module,
        model_id: str,
        checkpoint_dir: Optional[Union[str, Path]] = None,
        max_checkpoints: int = 3,
    ) -> Path:
        """
        Create a training checkpoint.

        Args:
            model: Model to checkpoint
            model_id: Model identifier
            checkpoint_dir: Checkpoint directory
            max_checkpoints: Maximum checkpoints to keep

        Returns:
            Path to checkpoint
        """
        checkpoint_dir = Path(checkpoint_dir or "./models/checkpoints")
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        checkpoint_path = checkpoint_dir / f"{model_id}_checkpoint_{timestamp}.pt"

        # Save checkpoint
        checkpoint = {
            "model_state_dict": model.state_dict(),
            "timestamp": timestamp,
            "model_id": model_id,
        }

        # Add optimizer if available
        if hasattr(model, "optimizer"):
            checkpoint["optimizer_state_dict"] = model.optimizer.state_dict()

        torch.save(checkpoint, checkpoint_path)

        # Cleanup old checkpoints
        checkpoints = sorted(
            checkpoint_dir.glob(f"{model_id}_checkpoint_*.pt"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

        for old_checkpoint in checkpoints[max_checkpoints:]:
            old_checkpoint.unlink()

        logger.info(f"Created checkpoint: {checkpoint_path}")

        return checkpoint_path

    async def list_saved_models(
        self,
        model_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List saved models.

        Args:
            model_id: Filter by model ID
            limit: Maximum results

        Returns:
            List of model metadata
        """
        saved_models = []

        for file_path in self.save_dir.glob("*"):
            if model_id and not file_path.stem.startswith(model_id):
                continue

            stats = file_path.stat()
            saved_models.append({
                "path": str(file_path),
                "name": file_path.stem,
                "size_bytes": stats.st_size,
                "modified_at": datetime.fromtimestamp(stats.st_mtime).isoformat(),
                "format": self._detect_format(file_path).value,
            })

        # Sort by modified time
        saved_models.sort(key=lambda x: x["modified_at"], reverse=True)

        return saved_models[:limit]

    async def delete_saved_model(
        self,
        model_path: Union[str, Path],
        include_backups: bool = False,
    ) -> bool:
        """
        Delete a saved model.

        Args:
            model_path: Path to model file
            include_backups: Whether to delete backups

        Returns:
            True if deleted
        """
        model_path = Path(model_path)

        if not model_path.exists():
            return False

        # Delete main file
        model_path.unlink()

        # Delete backups if requested
        if include_backups:
            model_name = model_path.stem.split("_")[0]
            backup_dir = self.backup_dir / model_name
            if backup_dir.exists():
                shutil.rmtree(backup_dir)

        logger.info(f"Deleted model: {model_path}")

        return True
