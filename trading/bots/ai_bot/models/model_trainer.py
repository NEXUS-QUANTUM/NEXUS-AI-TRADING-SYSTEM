"""
NEXUS AI TRADING SYSTEM - Model Trainer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced model trainer with distributed training, hyperparameter optimization,
early stopping, checkpointing, and comprehensive logging.
"""

import asyncio
import gc
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from prometheus_client import Counter, Gauge, Histogram
from torch.cuda.amp import GradScaler, autocast
from torch.utils.data import DataLoader, Dataset, TensorDataset
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector

logger = get_logger(__name__)

# Prometheus metrics
TRAINING_EPOCH_COUNTER = Counter(
    "nexus_training_epochs_total",
    "Total number of training epochs",
    ["model_id"],
)
TRAINING_LOSS_GAUGE = Gauge(
    "nexus_training_loss",
    "Current training loss",
    ["model_id", "phase"],
)
TRAINING_DURATION = Histogram(
    "nexus_training_duration_seconds",
    "Duration of training epochs",
    ["model_id"],
)


class TrainingPhase(Enum):
    """Training phases."""

    TRAINING = "training"
    VALIDATION = "validation"
    TESTING = "testing"


class EarlyStoppingMode(Enum):
    """Early stopping modes."""

    MIN = "min"
    MAX = "max"


@dataclass
class TrainingConfig:
    """Training configuration."""

    model_id: str
    batch_size: int = 64
    epochs: int = 100
    learning_rate: float = 1e-3
    weight_decay: float = 1e-5
    optimizer: str = "adam"
    scheduler: str = "none"
    scheduler_params: Dict[str, Any] = field(default_factory=dict)
    loss_function: str = "mse"
    early_stopping_patience: int = 10
    early_stopping_mode: EarlyStoppingMode = EarlyStoppingMode.MIN
    early_stopping_min_delta: float = 1e-4
    validation_split: float = 0.2
    test_split: float = 0.1
    shuffle: bool = True
    num_workers: int = 4
    pin_memory: bool = True
    gradient_clip: float = 1.0
    use_amp: bool = True
    checkpoint_freq: int = 5
    log_freq: int = 10
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

    # Distributed training
    distributed: bool = False
    world_size: int = 1
    rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_id": self.model_id,
            "batch_size": self.batch_size,
            "epochs": self.epochs,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "optimizer": self.optimizer,
            "scheduler": self.scheduler,
            "scheduler_params": self.scheduler_params,
            "loss_function": self.loss_function,
            "early_stopping_patience": self.early_stopping_patience,
            "early_stopping_mode": self.early_stopping_mode.value,
            "early_stopping_min_delta": self.early_stopping_min_delta,
            "validation_split": self.validation_split,
            "test_split": self.test_split,
            "shuffle": self.shuffle,
            "num_workers": self.num_workers,
            "pin_memory": self.pin_memory,
            "gradient_clip": self.gradient_clip,
            "use_amp": self.use_amp,
            "checkpoint_freq": self.checkpoint_freq,
            "log_freq": self.log_freq,
            "device": self.device,
            "distributed": self.distributed,
            "world_size": self.world_size,
            "rank": self.rank,
        }


@dataclass
class TrainingMetrics:
    """Training metrics container."""

    epoch: int
    train_loss: float
    val_loss: float
    train_accuracy: float = 0.0
    val_accuracy: float = 0.0
    train_metrics: Dict[str, float] = field(default_factory=dict)
    val_metrics: Dict[str, float] = field(default_factory=dict)
    learning_rate: float = 0.0
    duration_seconds: float = 0.0
    memory_usage_mb: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "epoch": self.epoch,
            "train_loss": self.train_loss,
            "val_loss": self.val_loss,
            "train_accuracy": self.train_accuracy,
            "val_accuracy": self.val_accuracy,
            "train_metrics": self.train_metrics,
            "val_metrics": self.val_metrics,
            "learning_rate": self.learning_rate,
            "duration_seconds": self.duration_seconds,
            "memory_usage_mb": self.memory_usage_mb,
        }


class ModelTrainer:
    """
    Advanced model trainer with comprehensive features.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        model_saver: Optional[Any] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the model trainer.

        Args:
            config: Configuration dictionary
            model_saver: Model saver instance
            metrics_collector: Metrics collector instance
        """
        self.config = config or {}
        self.model_saver = model_saver
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._lock = asyncio.Lock()
        self._training_tasks: Dict[str, asyncio.Task] = {}
        self._checkpoint_dir = Path(self.config.get("checkpoint_dir", "./models/checkpoints"))
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Tensorboard writer
        self._writer = None
        log_dir = self.config.get("log_dir", "./logs/tensorboard")
        if log_dir:
            self._writer = SummaryWriter(log_dir)

        # Load training defaults
        self.default_config = self.config.get("training", {})
        self.use_amp = self.default_config.get("use_amp", True)
        self.gradient_clip = self.default_config.get("gradient_clip", 1.0)

        logger.info("ModelTrainer initialized with config: %s", config)

    async def train_model(
        self,
        model: nn.Module,
        train_data: Union[np.ndarray, torch.Tensor, Dataset],
        train_labels: Optional[Union[np.ndarray, torch.Tensor]] = None,
        val_data: Optional[Union[np.ndarray, torch.Tensor, Dataset]] = None,
        val_labels: Optional[Union[np.ndarray, torch.Tensor]] = None,
        config: Optional[Union[TrainingConfig, Dict[str, Any]]] = None,
        callback: Optional[Callable] = None,
    ) -> TrainingMetrics:
        """
        Train a model.

        Args:
            model: Model to train
            train_data: Training data
            train_labels: Training labels
            val_data: Validation data
            val_labels: Validation labels
            config: Training configuration
            callback: Optional callback function

        Returns:
            Training metrics
        """
        # Parse configuration
        if config is None:
            config = TrainingConfig(model_id=model.__class__.__name__)
        elif isinstance(config, dict):
            config = TrainingConfig(**config)

        # Prepare data loaders
        train_loader, val_loader = self._prepare_data_loaders(
            train_data=train_data,
            train_labels=train_labels,
            val_data=val_data,
            val_labels=val_labels,
            config=config,
        )

        # Setup device
        device = torch.device(config.device)
        model = model.to(device)

        # Setup optimizer
        optimizer = self._create_optimizer(model, config)

        # Setup scheduler
        scheduler = self._create_scheduler(optimizer, config)

        # Setup loss function
        criterion = self._create_loss_function(config)

        # Setup scaler for mixed precision
        scaler = GradScaler(enabled=config.use_amp)

        # Training loop
        best_val_loss = float("inf")
        best_model_state = None
        patience_counter = 0
        metrics_history = []

        logger.info(f"Starting training for model {config.model_id}")
        logger.info(f"Training samples: {len(train_loader.dataset)}")
        logger.info(f"Validation samples: {len(val_loader.dataset)}")

        start_time = time.time()

        for epoch in range(1, config.epochs + 1):
            epoch_start = time.time()

            # Training phase
            train_metrics = await self._train_epoch(
                model=model,
                train_loader=train_loader,
                optimizer=optimizer,
                criterion=criterion,
                scaler=scaler,
                config=config,
                epoch=epoch,
            )

            # Validation phase
            val_metrics = await self._validate_epoch(
                model=model,
                val_loader=val_loader,
                criterion=criterion,
                config=config,
                epoch=epoch,
            )

            # Update scheduler
            if scheduler:
                if hasattr(scheduler, "step"):
                    scheduler.step(val_metrics["loss"])
                elif hasattr(scheduler, "step_epoch"):
                    scheduler.step_epoch()

            # Create metrics object
            metrics = TrainingMetrics(
                epoch=epoch,
                train_loss=train_metrics["loss"],
                val_loss=val_metrics["loss"],
                train_accuracy=train_metrics.get("accuracy", 0.0),
                val_accuracy=val_metrics.get("accuracy", 0.0),
                train_metrics=train_metrics,
                val_metrics=val_metrics,
                learning_rate=optimizer.param_groups[0]["lr"],
                duration_seconds=time.time() - epoch_start,
                memory_usage_mb=self._get_memory_usage(),
            )

            metrics_history.append(metrics)

            # Log metrics
            self._log_metrics(metrics, config)
            self._writer_add_scalars(metrics, epoch)

            # Check early stopping
            val_loss = val_metrics["loss"]
            is_better = self._is_improvement(
                val_loss,
                best_val_loss,
                config.early_stopping_mode,
                config.early_stopping_min_delta,
            )

            if is_better:
                best_val_loss = val_loss
                best_model_state = model.state_dict()
                patience_counter = 0
                logger.info(f"Epoch {epoch}: New best validation loss: {best_val_loss:.6f}")
            else:
                patience_counter += 1

            # Save checkpoint
            if epoch % config.checkpoint_freq == 0:
                await self._save_checkpoint(
                    model=model,
                    optimizer=optimizer,
                    metrics=metrics,
                    config=config,
                    epoch=epoch,
                )

            # Callback
            if callback:
                await callback(metrics)

            # Early stopping check
            if patience_counter >= config.early_stopping_patience:
                logger.info(f"Early stopping triggered at epoch {epoch}")
                break

            # Update metrics
            TRAINING_EPOCH_COUNTER.labels(model_id=config.model_id).inc()
            TRAINING_LOSS_GAUGE.labels(
                model_id=config.model_id,
                phase="training",
            ).set(train_metrics["loss"])
            TRAINING_LOSS_GAUGE.labels(
                model_id=config.model_id,
                phase="validation",
            ).set(val_metrics["loss"])
            TRAINING_DURATION.labels(model_id=config.model_id).observe(
                time.time() - epoch_start
            )

            # Memory cleanup
            if epoch % 10 == 0:
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

        total_duration = time.time() - start_time

        # Load best model
        if best_model_state is not None:
            model.load_state_dict(best_model_state)

        # Save final model
        if self.model_saver:
            await self._save_final_model(model, config, metrics_history)

        logger.info(f"Training completed in {total_duration:.2f} seconds")
        logger.info(f"Best validation loss: {best_val_loss:.6f}")

        return metrics_history[-1] if metrics_history else None

    async def _train_epoch(
        self,
        model: nn.Module,
        train_loader: DataLoader,
        optimizer: optim.Optimizer,
        criterion: nn.Module,
        scaler: GradScaler,
        config: TrainingConfig,
        epoch: int,
    ) -> Dict[str, float]:
        """Train one epoch."""
        model.train()
        total_loss = 0.0
        total_correct = 0
        total_samples = 0

        progress_bar = tqdm(
            train_loader,
            desc=f"Epoch {epoch}",
            leave=False,
            disable=config.rank != 0,
        )

        for batch_idx, (data, targets) in enumerate(progress_bar):
            data = data.to(config.device)
            targets = targets.to(config.device)

            optimizer.zero_grad()

            # Forward pass with mixed precision
            with autocast(enabled=config.use_amp):
                outputs = model(data)
                loss = criterion(outputs, targets)

            # Backward pass
            scaler.scale(loss).backward()

            # Gradient clipping
            if config.gradient_clip > 0:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(
                    model.parameters(),
                    config.gradient_clip,
                )

            scaler.step(optimizer)
            scaler.update()

            # Accumulate metrics
            total_loss += loss.item()
            total_samples += targets.size(0)

            # Accuracy for classification
            if config.loss_function in ["cross_entropy", "binary_cross_entropy"]:
                _, predicted = torch.max(outputs.data, 1)
                total_correct += (predicted == targets).sum().item()

            # Update progress bar
            progress_bar.set_postfix({
                "loss": loss.item(),
                "lr": optimizer.param_groups[0]["lr"],
            })

            # Log batch metrics
            if batch_idx % config.log_freq == 0:
                self._writer_add_scalars_batch(
                    loss=loss.item(),
                    lr=optimizer.param_groups[0]["lr"],
                    epoch=epoch,
                    batch=batch_idx,
                )

        # Calculate epoch metrics
        epoch_loss = total_loss / len(train_loader)
        metrics = {
            "loss": epoch_loss,
            "learning_rate": optimizer.param_groups[0]["lr"],
        }

        if config.loss_function in ["cross_entropy", "binary_cross_entropy"]:
            metrics["accuracy"] = total_correct / total_samples

        return metrics

    async def _validate_epoch(
        self,
        model: nn.Module,
        val_loader: DataLoader,
        criterion: nn.Module,
        config: TrainingConfig,
        epoch: int,
    ) -> Dict[str, float]:
        """Validate one epoch."""
        model.eval()
        total_loss = 0.0
        total_correct = 0
        total_samples = 0

        with torch.no_grad():
            for data, targets in val_loader:
                data = data.to(config.device)
                targets = targets.to(config.device)

                with autocast(enabled=config.use_amp):
                    outputs = model(data)
                    loss = criterion(outputs, targets)

                total_loss += loss.item()
                total_samples += targets.size(0)

                if config.loss_function in ["cross_entropy", "binary_cross_entropy"]:
                    _, predicted = torch.max(outputs.data, 1)
                    total_correct += (predicted == targets).sum().item()

        epoch_loss = total_loss / len(val_loader)
        metrics = {"loss": epoch_loss}

        if config.loss_function in ["cross_entropy", "binary_cross_entropy"]:
            metrics["accuracy"] = total_correct / total_samples

        return metrics

    def _prepare_data_loaders(
        self,
        train_data: Union[np.ndarray, torch.Tensor, Dataset],
        train_labels: Optional[Union[np.ndarray, torch.Tensor]],
        val_data: Optional[Union[np.ndarray, torch.Tensor, Dataset]],
        val_labels: Optional[Union[np.ndarray, torch.Tensor]],
        config: TrainingConfig,
    ) -> Tuple[DataLoader, DataLoader]:
        """Prepare data loaders."""
        # Convert to Dataset if needed
        if isinstance(train_data, (np.ndarray, torch.Tensor)):
            if train_labels is None:
                train_dataset = TensorDataset(torch.tensor(train_data))
            else:
                if isinstance(train_labels, np.ndarray):
                    train_labels = torch.tensor(train_labels)
                train_dataset = TensorDataset(
                    torch.tensor(train_data),
                    train_labels,
                )
        else:
            train_dataset = train_data

        # Validation data
        if val_data is not None:
            if isinstance(val_data, (np.ndarray, torch.Tensor)):
                if val_labels is None:
                    val_dataset = TensorDataset(torch.tensor(val_data))
                else:
                    if isinstance(val_labels, np.ndarray):
                        val_labels = torch.tensor(val_labels)
                    val_dataset = TensorDataset(
                        torch.tensor(val_data),
                        val_labels,
                    )
            else:
                val_dataset = val_data
        else:
            # Split from training data
            dataset_size = len(train_dataset)
            val_size = int(dataset_size * config.validation_split)
            train_size = dataset_size - val_size

            if config.shuffle:
                train_dataset, val_dataset = torch.utils.data.random_split(
                    train_dataset,
                    [train_size, val_size],
                )
            else:
                train_dataset, val_dataset = torch.utils.data.Subset(
                    train_dataset,
                    range(train_size),
                ), torch.utils.data.Subset(
                    train_dataset,
                    range(train_size, dataset_size),
                )

        # Create data loaders
        train_loader = DataLoader(
            train_dataset,
            batch_size=config.batch_size,
            shuffle=config.shuffle,
            num_workers=config.num_workers,
            pin_memory=config.pin_memory,
            drop_last=True,
        )

        val_loader = DataLoader(
            val_dataset,
            batch_size=config.batch_size,
            shuffle=False,
            num_workers=config.num_workers,
            pin_memory=config.pin_memory,
        )

        return train_loader, val_loader

    def _create_optimizer(
        self,
        model: nn.Module,
        config: TrainingConfig,
    ) -> optim.Optimizer:
        """Create optimizer."""
        optimizer_map = {
            "adam": optim.Adam,
            "adamw": optim.AdamW,
            "sgd": optim.SGD,
            "rmsprop": optim.RMSprop,
            "adamax": optim.Adamax,
        }

        opt_class = optimizer_map.get(config.optimizer.lower(), optim.Adam)

        if config.optimizer.lower() == "sgd":
            return opt_class(
                model.parameters(),
                lr=config.learning_rate,
                momentum=0.9,
                weight_decay=config.weight_decay,
            )
        else:
            return opt_class(
                model.parameters(),
                lr=config.learning_rate,
                weight_decay=config.weight_decay,
            )

    def _create_scheduler(
        self,
        optimizer: optim.Optimizer,
        config: TrainingConfig,
    ) -> Optional[Any]:
        """Create learning rate scheduler."""
        scheduler_map = {
            "none": None,
            "step_lr": optim.lr_scheduler.StepLR,
            "cosine": optim.lr_scheduler.CosineAnnealingLR,
            "reduce_on_plateau": optim.lr_scheduler.ReduceLROnPlateau,
            "exponential": optim.lr_scheduler.ExponentialLR,
            "cyclic": optim.lr_scheduler.CyclicLR,
        }

        scheduler_type = config.scheduler.lower()

        if scheduler_type not in scheduler_map:
            return None

        if scheduler_type == "none":
            return None

        scheduler_class = scheduler_map[scheduler_type]

        if scheduler_type == "reduce_on_plateau":
            return scheduler_class(
                optimizer,
                mode="min",
                patience=config.scheduler_params.get("patience", 5),
                factor=config.scheduler_params.get("factor", 0.5),
                min_lr=config.scheduler_params.get("min_lr", 1e-7),
            )
        elif scheduler_type == "cyclic":
            return scheduler_class(
                optimizer,
                base_lr=config.learning_rate / 10,
                max_lr=config.learning_rate,
                step_size_up=config.scheduler_params.get("step_size_up", 20),
                mode="triangular",
            )
        else:
            return scheduler_class(
                optimizer,
                step_size=config.scheduler_params.get("step_size", 30),
                gamma=config.scheduler_params.get("gamma", 0.1),
            )

    def _create_loss_function(self, config: TrainingConfig) -> nn.Module:
        """Create loss function."""
        loss_map = {
            "mse": nn.MSELoss,
            "mae": nn.L1Loss,
            "huber": nn.SmoothL1Loss,
            "cross_entropy": nn.CrossEntropyLoss,
            "binary_cross_entropy": nn.BCEWithLogitsLoss,
            "kl_div": nn.KLDivLoss,
            "cosine": nn.CosineEmbeddingLoss,
        }

        loss_class = loss_map.get(config.loss_function.lower(), nn.MSELoss)

        if config.loss_function.lower() == "huber":
            return loss_class(delta=config.scheduler_params.get("huber_delta", 1.0))

        return loss_class()

    def _is_improvement(
        self,
        current: float,
        best: float,
        mode: EarlyStoppingMode,
        min_delta: float,
    ) -> bool:
        """Check if current value is an improvement."""
        if mode == EarlyStoppingMode.MIN:
            return current < best - min_delta
        else:
            return current > best + min_delta

    def _log_metrics(self, metrics: TrainingMetrics, config: TrainingConfig):
        """Log training metrics."""
        logger.info(
            f"Epoch {metrics.epoch}/{config.epochs} - "
            f"Train Loss: {metrics.train_loss:.6f}, "
            f"Val Loss: {metrics.val_loss:.6f}, "
            f"Train Acc: {metrics.train_accuracy:.4f}, "
            f"Val Acc: {metrics.val_accuracy:.4f}, "
            f"LR: {metrics.learning_rate:.2e}, "
            f"Duration: {metrics.duration_seconds:.2f}s"
        )

    def _writer_add_scalars(self, metrics: TrainingMetrics, epoch: int):
        """Add scalars to tensorboard writer."""
        if self._writer is None:
            return

        self._writer.add_scalar("Loss/train", metrics.train_loss, epoch)
        self._writer.add_scalar("Loss/val", metrics.val_loss, epoch)
        self._writer.add_scalar("Accuracy/train", metrics.train_accuracy, epoch)
        self._writer.add_scalar("Accuracy/val", metrics.val_accuracy, epoch)
        self._writer.add_scalar("Learning_Rate", metrics.learning_rate, epoch)

        if metrics.train_metrics:
            for key, value in metrics.train_metrics.items():
                if key not in ["loss", "accuracy"]:
                    self._writer.add_scalar(f"Train/{key}", value, epoch)

        if metrics.val_metrics:
            for key, value in metrics.val_metrics.items():
                if key not in ["loss", "accuracy"]:
                    self._writer.add_scalar(f"Val/{key}", value, epoch)

    def _writer_add_scalars_batch(
        self,
        loss: float,
        lr: float,
        epoch: int,
        batch: int,
    ):
        """Add batch scalars to tensorboard writer."""
        if self._writer is None:
            return

        global_step = (epoch - 1) * 100 + batch
        self._writer.add_scalar("Loss/batch", loss, global_step)
        self._writer.add_scalar("Learning_Rate/batch", lr, global_step)

    def _get_memory_usage(self) -> float:
        """Get memory usage in MB."""
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / (1024 * 1024)
        return 0.0

    async def _save_checkpoint(
        self,
        model: nn.Module,
        optimizer: optim.Optimizer,
        metrics: TrainingMetrics,
        config: TrainingConfig,
        epoch: int,
    ):
        """Save training checkpoint."""
        checkpoint_path = self._checkpoint_dir / f"{config.model_id}_epoch_{epoch}.pt"

        checkpoint = {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "metrics": metrics.to_dict(),
            "config": config.to_dict(),
        }

        torch.save(checkpoint, checkpoint_path)

        # Clean up old checkpoints
        checkpoints = sorted(
            self._checkpoint_dir.glob(f"{config.model_id}_epoch_*.pt"),
            key=lambda x: x.stat().st_mtime,
        )

        # Keep only last 5 checkpoints
        for old_checkpoint in checkpoints[:-5]:
            old_checkpoint.unlink()

        logger.debug(f"Saved checkpoint: {checkpoint_path}")

    async def _save_final_model(
        self,
        model: nn.Module,
        config: TrainingConfig,
        metrics_history: List[TrainingMetrics],
    ):
        """Save final model."""
        if not self.model_saver:
            return

        # Prepare save config
        save_config = {
            "format": "pytorch",
            "compression": "gzip",
            "include_metadata": True,
            "include_config": True,
            "version": config.model_id,
            "tags": ["trained", f"epochs_{len(metrics_history)}"],
            "metadata": {
                "training_config": config.to_dict(),
                "metrics_history": [m.to_dict() for m in metrics_history[-10:]],
                "best_metrics": min(metrics_history, key=lambda x: x.val_loss).to_dict(),
            },
        }

        try:
            await self.model_saver.save_model(
                model=model,
                model_id=config.model_id,
                config=save_config,
            )
            logger.info(f"Saved final model: {config.model_id}")
        except Exception as e:
            logger.error(f"Failed to save final model: {e}")

    async def load_checkpoint(
        self,
        model: nn.Module,
        checkpoint_path: Union[str, Path],
    ) -> Dict[str, Any]:
        """
        Load a training checkpoint.

        Args:
            model: Model to load checkpoint into
            checkpoint_path: Path to checkpoint file

        Returns:
            Checkpoint data
        """
        checkpoint_path = Path(checkpoint_path)

        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

        checkpoint = torch.load(checkpoint_path, map_location="cpu")

        model.load_state_dict(checkpoint["model_state_dict"])

        logger.info(f"Loaded checkpoint from {checkpoint_path}")
        logger.info(f"Epoch: {checkpoint.get('epoch', 'unknown')}")
        logger.info(f"Metrics: {checkpoint.get('metrics', {})}")

        return checkpoint

    async def resume_training(
        self,
        model: nn.Module,
        checkpoint_path: Union[str, Path],
        train_data: Union[np.ndarray, torch.Tensor, Dataset],
        train_labels: Optional[Union[np.ndarray, torch.Tensor]] = None,
        val_data: Optional[Union[np.ndarray, torch.Tensor, Dataset]] = None,
        val_labels: Optional[Union[np.ndarray, torch.Tensor]] = None,
        config: Optional[TrainingConfig] = None,
    ) -> TrainingMetrics:
        """
        Resume training from a checkpoint.

        Args:
            model: Model to train
            checkpoint_path: Path to checkpoint file
            train_data: Training data
            train_labels: Training labels
            val_data: Validation data
            val_labels: Validation labels
            config: Training configuration

        Returns:
            Training metrics
        """
        checkpoint = await self.load_checkpoint(model, checkpoint_path)

        # Update config
        if config is None:
            config = TrainingConfig.from_dict(checkpoint["config"])

        # Adjust epochs
        start_epoch = checkpoint["epoch"]
        config.epochs += start_epoch

        # Resume training
        metrics = await self.train_model(
            model=model,
            train_data=train_data,
            train_labels=train_labels,
            val_data=val_data,
            val_labels=val_labels,
            config=config,
        )

        return metrics

    def _get_optimizer_state(self, optimizer: optim.Optimizer) -> Dict[str, Any]:
        """Get optimizer state for checkpoint."""
        return optimizer.state_dict()

    def _set_optimizer_state(
        self,
        optimizer: optim.Optimizer,
        state: Dict[str, Any],
    ):
        """Set optimizer state from checkpoint."""
        optimizer.load_state_dict(state)

    async def shutdown(self):
        """Shutdown the trainer."""
        if self._writer:
            self._writer.close()

        logger.info("ModelTrainer shut down")


# Utility function to create training config from dict
def create_training_config(
    model_id: str,
    **kwargs,
) -> TrainingConfig:
    """Create a training configuration."""
    return TrainingConfig(
        model_id=model_id,
        **kwargs,
    )
