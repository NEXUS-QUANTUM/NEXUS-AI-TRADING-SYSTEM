"""
NEXUS AI TRADING SYSTEM - Model Factory
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced model factory for creating and configuring AI trading models.
Supports multiple model architectures, hyperparameter optimization,
and dynamic model instantiation.
"""

import asyncio
import importlib
import inspect
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union

import joblib
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector

logger = get_logger(__name__)


class ModelArchitecture(Enum):
    """Supported model architectures."""

    # Neural Network Models
    LSTM = "lstm"
    BILSTM = "bilstm"
    STACKED_LSTM = "stacked_lstm"
    ATTENTION_LSTM = "attention_lstm"
    GRU = "gru"
    TRANSFORMER = "transformer"
    INFORMER = "informer"
    AUTOFORMER = "autoformer"
    PATCHTST = "patchtst"
    TEMPORAL_FUSION = "temporal_fusion"

    # Traditional ML Models
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    CATBOOST = "catboost"
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"

    # Deep Learning Models
    DEEPAR = "deepar"
    N_BEATS = "n_beats"
    TFT = "tft"
    GRU_ATTENTION = "gru_attention"
    RESNET = "resnet"

    # Reinforcement Learning
    DQN = "dqn"
    PPO = "ppo"
    SAC = "sac"
    TD3 = "td3"
    RAINBOW = "rainbow"

    # Ensemble Models
    ENSEMBLE = "ensemble"
    STACKING = "stacking"
    VOTING = "voting"
    BAGGING = "bagging"


class ModelTask(Enum):
    """Tasks a model can perform."""

    REGRESSION = "regression"
    CLASSIFICATION = "classification"
    FORECASTING = "forecasting"
    REINFORCEMENT = "reinforcement"
    ANOMALY_DETECTION = "anomaly_detection"
    PORTFOLIO_OPTIMIZATION = "portfolio_optimization"


@dataclass
class ModelConfig:
    """Configuration for model creation."""

    architecture: ModelArchitecture
    task: ModelTask
    input_dim: int
    output_dim: int
    sequence_length: int = 64
    hidden_dim: int = 256
    num_layers: int = 2
    num_heads: int = 8
    dropout: float = 0.1
    learning_rate: float = 1e-3
    batch_size: int = 64
    epochs: int = 100
    early_stopping_patience: int = 10
    optimizer: str = "adam"
    loss_function: str = "mse"
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

    # Architecture-specific configs
    arch_config: Dict[str, Any] = field(default_factory=dict)

    # Additional metadata
    name: str = ""
    description: str = ""
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "architecture": self.architecture.value,
            "task": self.task.value,
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "sequence_length": self.sequence_length,
            "hidden_dim": self.hidden_dim,
            "num_layers": self.num_layers,
            "num_heads": self.num_heads,
            "dropout": self.dropout,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "epochs": self.epochs,
            "early_stopping_patience": self.early_stopping_patience,
            "optimizer": self.optimizer,
            "loss_function": self.loss_function,
            "device": self.device,
            "arch_config": self.arch_config,
            "name": self.name,
            "description": self.description,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelConfig":
        """Create config from dictionary."""
        return cls(
            architecture=ModelArchitecture(data["architecture"]),
            task=ModelTask(data["task"]),
            input_dim=data["input_dim"],
            output_dim=data["output_dim"],
            sequence_length=data.get("sequence_length", 64),
            hidden_dim=data.get("hidden_dim", 256),
            num_layers=data.get("num_layers", 2),
            num_heads=data.get("num_heads", 8),
            dropout=data.get("dropout", 0.1),
            learning_rate=data.get("learning_rate", 1e-3),
            batch_size=data.get("batch_size", 64),
            epochs=data.get("epochs", 100),
            early_stopping_patience=data.get("early_stopping_patience", 10),
            optimizer=data.get("optimizer", "adam"),
            loss_function=data.get("loss_function", "mse"),
            device=data.get("device", "cuda" if torch.cuda.is_available() else "cpu"),
            arch_config=data.get("arch_config", {}),
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
        )


class ModelFactory:
    """
    Advanced factory for creating and managing AI trading models.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the model factory.

        Args:
            config: Configuration dictionary
            metrics_collector: Optional metrics collector
        """
        self.config = config or {}
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._model_registry: Dict[str, Dict] = {}
        self._model_cache: Dict[str, nn.Module] = {}
        self._lock = asyncio.Lock()

        # Default model configurations
        self.default_configs = self._load_default_configs()

        logger.info("ModelFactory initialized with config: %s", config)

    def _load_default_configs(self) -> Dict[str, ModelConfig]:
        """Load default model configurations."""
        defaults = {}

        # LSTM default config
        defaults["lstm"] = ModelConfig(
            architecture=ModelArchitecture.LSTM,
            task=ModelTask.FORECASTING,
            input_dim=10,
            output_dim=1,
            sequence_length=64,
            hidden_dim=256,
            num_layers=2,
            dropout=0.2,
            learning_rate=1e-3,
            batch_size=64,
            epochs=100,
            arch_config={
                "bidirectional": False,
                "batch_first": True,
            },
        )

        # Transformer default config
        defaults["transformer"] = ModelConfig(
            architecture=ModelArchitecture.TRANSFORMER,
            task=ModelTask.FORECASTING,
            input_dim=10,
            output_dim=1,
            sequence_length=64,
            hidden_dim=512,
            num_heads=8,
            num_layers=4,
            dropout=0.1,
            learning_rate=1e-4,
            batch_size=32,
            epochs=100,
            arch_config={
                "dim_feedforward": 2048,
                "batch_first": True,
            },
        )

        # XGBoost default config
        defaults["xgboost"] = ModelConfig(
            architecture=ModelArchitecture.XGBOOST,
            task=ModelTask.REGRESSION,
            input_dim=20,
            output_dim=1,
            sequence_length=0,
            arch_config={
                "n_estimators": 1000,
                "max_depth": 10,
                "learning_rate": 0.01,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
            },
        )

        # DQN default config
        defaults["dqn"] = ModelConfig(
            architecture=ModelArchitecture.DQN,
            task=ModelTask.REINFORCEMENT,
            input_dim=10,
            output_dim=3,  # Number of actions
            sequence_length=0,
            hidden_dim=256,
            num_layers=2,
            learning_rate=1e-4,
            arch_config={
                "replay_buffer_size": 100000,
                "batch_size": 256,
                "gamma": 0.99,
                "epsilon_start": 1.0,
                "epsilon_end": 0.01,
                "epsilon_decay": 0.995,
                "target_update_freq": 100,
            },
        )

        return defaults

    async def create_model(
        self,
        config: Union[ModelConfig, Dict[str, Any], str],
        **kwargs,
    ) -> nn.Module:
        """
        Create a model based on configuration.

        Args:
            config: Model configuration or architecture name
            **kwargs: Additional configuration overrides

        Returns:
            Model instance
        """
        # Parse configuration
        if isinstance(config, str):
            # Use default config by name
            config = self.default_configs.get(
                config,
                self.default_configs["lstm"]
            )
            if kwargs:
                # Apply overrides
                config = self._override_config(config, kwargs)
        elif isinstance(config, dict):
            config = ModelConfig.from_dict(config)
        elif not isinstance(config, ModelConfig):
            raise ValueError("Invalid config type")

        # Create model
        model_creator = self._get_model_creator(config.architecture)
        model = model_creator(config)

        # Move to device
        model = model.to(config.device)

        # Cache the model
        model_id = f"{config.architecture.value}_{config.name or 'default'}"
        async with self._lock:
            self._model_cache[model_id] = model

        logger.info(f"Created model {model_id} on {config.device}")

        return model

    def _override_config(
        self,
        config: ModelConfig,
        overrides: Dict[str, Any],
    ) -> ModelConfig:
        """Override configuration with provided values."""
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return config

    def _get_model_creator(
        self,
        architecture: ModelArchitecture,
    ) -> Callable[[ModelConfig], nn.Module]:
        """Get the model creator function for an architecture."""
        creators = {
            ModelArchitecture.LSTM: self._create_lstm,
            ModelArchitecture.BILSTM: self._create_bilstm,
            ModelArchitecture.STACKED_LSTM: self._create_stacked_lstm,
            ModelArchitecture.ATTENTION_LSTM: self._create_attention_lstm,
            ModelArchitecture.GRU: self._create_gru,
            ModelArchitecture.TRANSFORMER: self._create_transformer,
            ModelArchitecture.INFORMER: self._create_informer,
            ModelArchitecture.AUTOFORMER: self._create_autoformer,
            ModelArchitecture.PATCHTST: self._create_patchtst,
            ModelArchitecture.TEMPORAL_FUSION: self._create_temporal_fusion,
            ModelArchitecture.DQN: self._create_dqn,
            ModelArchitecture.PPO: self._create_ppo,
            ModelArchitecture.SAC: self._create_sac,
            ModelArchitecture.TD3: self._create_td3,
            ModelArchitecture.RAINBOW: self._create_rainbow,
            ModelArchitecture.ENSEMBLE: self._create_ensemble,
            ModelArchitecture.STACKING: self._create_stacking,
            ModelArchitecture.VOTING: self._create_voting,
            ModelArchitecture.BAGGING: self._create_bagging,
        }

        if architecture not in creators:
            raise ValueError(f"Unsupported architecture: {architecture}")

        return creators[architecture]

    def _create_lstm(self, config: ModelConfig) -> nn.Module:
        """Create LSTM model."""
        from ai.models.lstm.lstm_model import LSTMModel

        return LSTMModel(
            input_dim=config.input_dim,
            hidden_dim=config.hidden_dim,
            num_layers=config.num_layers,
            output_dim=config.output_dim,
            dropout=config.dropout,
            bidirectional=False,
            batch_first=True,
        )

    def _create_bilstm(self, config: ModelConfig) -> nn.Module:
        """Create BiLSTM model."""
        from ai.models.lstm.bilstm_model import BiLSTMModel

        return BiLSTMModel(
            input_dim=config.input_dim,
            hidden_dim=config.hidden_dim,
            num_layers=config.num_layers,
            output_dim=config.output_dim,
            dropout=config.dropout,
            batch_first=True,
        )

    def _create_stacked_lstm(self, config: ModelConfig) -> nn.Module:
        """Create Stacked LSTM model."""
        from ai.models.lstm.stacked_lstm import StackedLSTM

        return StackedLSTM(
            input_dim=config.input_dim,
            hidden_dim=config.hidden_dim,
            num_layers=config.num_layers,
            output_dim=config.output_dim,
            dropout=config.dropout,
            batch_first=True,
        )

    def _create_attention_lstm(self, config: ModelConfig) -> nn.Module:
        """Create Attention LSTM model."""
        from ai.models.lstm.attention_lstm import AttentionLSTM

        return AttentionLSTM(
            input_dim=config.input_dim,
            hidden_dim=config.hidden_dim,
            num_layers=config.num_layers,
            output_dim=config.output_dim,
            dropout=config.dropout,
            batch_first=True,
        )

    def _create_gru(self, config: ModelConfig) -> nn.Module:
        """Create GRU model."""
        from ai.models.forecasting.gru_model import GRUModel

        return GRUModel(
            input_dim=config.input_dim,
            hidden_dim=config.hidden_dim,
            num_layers=config.num_layers,
            output_dim=config.output_dim,
            dropout=config.dropout,
            batch_first=True,
        )

    def _create_transformer(self, config: ModelConfig) -> nn.Module:
        """Create Transformer model."""
        from ai.models.transformers.time_series_transformer import TimeSeriesTransformer

        return TimeSeriesTransformer(
            input_dim=config.input_dim,
            seq_len=config.sequence_length,
            d_model=config.hidden_dim,
            nhead=config.num_heads,
            num_layers=config.num_layers,
            output_dim=config.output_dim,
            dropout=config.dropout,
            batch_first=True,
        )

    def _create_informer(self, config: ModelConfig) -> nn.Module:
        """Create Informer model."""
        from ai.models.transformers.informer_model import InformerModel

        return InformerModel(
            input_dim=config.input_dim,
            seq_len=config.sequence_length,
            d_model=config.hidden_dim,
            nhead=config.num_heads,
            num_layers=config.num_layers,
            output_dim=config.output_dim,
            dropout=config.dropout,
            batch_first=True,
        )

    def _create_autoformer(self, config: ModelConfig) -> nn.Module:
        """Create Autoformer model."""
        from ai.models.transformers.autoformer_model import AutoformerModel

        return AutoformerModel(
            input_dim=config.input_dim,
            seq_len=config.sequence_length,
            d_model=config.hidden_dim,
            nhead=config.num_heads,
            num_layers=config.num_layers,
            output_dim=config.output_dim,
            dropout=config.dropout,
            batch_first=True,
        )

    def _create_patchtst(self, config: ModelConfig) -> nn.Module:
        """Create PatchTST model."""
        from ai.models.transformers.patchtst_model import PatchTSTModel

        return PatchTSTModel(
            input_dim=config.input_dim,
            seq_len=config.sequence_length,
            d_model=config.hidden_dim,
            nhead=config.num_heads,
            num_layers=config.num_layers,
            output_dim=config.output_dim,
            dropout=config.dropout,
            batch_first=True,
        )

    def _create_temporal_fusion(self, config: ModelConfig) -> nn.Module:
        """Create Temporal Fusion Transformer model."""
        from ai.models.forecasting.temporal_fusion import TemporalFusionTransformer

        return TemporalFusionTransformer(
            input_dim=config.input_dim,
            seq_len=config.sequence_length,
            d_model=config.hidden_dim,
            nhead=config.num_heads,
            num_layers=config.num_layers,
            output_dim=config.output_dim,
            dropout=config.dropout,
            batch_first=True,
        )

    def _create_dqn(self, config: ModelConfig) -> nn.Module:
        """Create DQN model."""
        from ai.models.reinforcement.dqn_agent import DQNAgent

        return DQNAgent(
            state_dim=config.input_dim,
            action_dim=config.output_dim,
            hidden_dim=config.hidden_dim,
            learning_rate=config.learning_rate,
            gamma=config.arch_config.get("gamma", 0.99),
            epsilon_start=config.arch_config.get("epsilon_start", 1.0),
            epsilon_end=config.arch_config.get("epsilon_end", 0.01),
            epsilon_decay=config.arch_config.get("epsilon_decay", 0.995),
            batch_size=config.arch_config.get("batch_size", 256),
            replay_buffer_size=config.arch_config.get("replay_buffer_size", 100000),
            target_update_freq=config.arch_config.get("target_update_freq", 100),
        )

    def _create_ppo(self, config: ModelConfig) -> nn.Module:
        """Create PPO model."""
        from ai.models.reinforcement.ppo_agent import PPOAgent

        return PPOAgent(
            state_dim=config.input_dim,
            action_dim=config.output_dim,
            hidden_dim=config.hidden_dim,
            learning_rate=config.learning_rate,
            clip_epsilon=config.arch_config.get("clip_epsilon", 0.2),
            gamma=config.arch_config.get("gamma", 0.99),
            gae_lambda=config.arch_config.get("gae_lambda", 0.95),
            epochs_per_update=config.arch_config.get("epochs_per_update", 10),
            batch_size=config.arch_config.get("batch_size", 64),
        )

    def _create_sac(self, config: ModelConfig) -> nn.Module:
        """Create SAC model."""
        from ai.models.reinforcement.sac_agent import SACAgent

        return SACAgent(
            state_dim=config.input_dim,
            action_dim=config.output_dim,
            hidden_dim=config.hidden_dim,
            learning_rate=config.learning_rate,
            alpha=config.arch_config.get("alpha", 0.2),
            gamma=config.arch_config.get("gamma", 0.99),
            tau=config.arch_config.get("tau", 0.005),
            batch_size=config.arch_config.get("batch_size", 256),
            replay_buffer_size=config.arch_config.get("replay_buffer_size", 100000),
        )

    def _create_td3(self, config: ModelConfig) -> nn.Module:
        """Create TD3 model."""
        from ai.models.reinforcement.td3_agent import TD3Agent

        return TD3Agent(
            state_dim=config.input_dim,
            action_dim=config.output_dim,
            hidden_dim=config.hidden_dim,
            learning_rate=config.learning_rate,
            gamma=config.arch_config.get("gamma", 0.99),
            tau=config.arch_config.get("tau", 0.005),
            policy_noise=config.arch_config.get("policy_noise", 0.2),
            noise_clip=config.arch_config.get("noise_clip", 0.5),
            policy_freq=config.arch_config.get("policy_freq", 2),
            batch_size=config.arch_config.get("batch_size", 256),
            replay_buffer_size=config.arch_config.get("replay_buffer_size", 100000),
        )

    def _create_rainbow(self, config: ModelConfig) -> nn.Module:
        """Create Rainbow DQN model."""
        from ai.models.reinforcement.rainbow_agent import RainbowAgent

        return RainbowAgent(
            state_dim=config.input_dim,
            action_dim=config.output_dim,
            hidden_dim=config.hidden_dim,
            learning_rate=config.learning_rate,
            gamma=config.arch_config.get("gamma", 0.99),
            n_step=config.arch_config.get("n_step", 3),
            priority_alpha=config.arch_config.get("priority_alpha", 0.6),
            priority_beta=config.arch_config.get("priority_beta", 0.4),
            epsilon_start=config.arch_config.get("epsilon_start", 1.0),
            epsilon_end=config.arch_config.get("epsilon_end", 0.01),
            epsilon_decay=config.arch_config.get("epsilon_decay", 0.995),
            batch_size=config.arch_config.get("batch_size", 256),
            replay_buffer_size=config.arch_config.get("replay_buffer_size", 100000),
            target_update_freq=config.arch_config.get("target_update_freq", 100),
        )

    def _create_ensemble(self, config: ModelConfig) -> nn.Module:
        """Create ensemble model."""
        from ai.models.ensemble.voting_ensemble import VotingEnsemble

        # Create base models
        base_models = []
        for i in range(config.arch_config.get("num_models", 3)):
            base_config = self._create_base_config(
                config.arch_config.get("base_architecture", "lstm"),
                config
            )
            base_model = self._get_model_creator(
                ModelArchitecture(base_config.arch_config.get("base_architecture", "lstm"))
            )(base_config)
            base_models.append(base_model)

        return VotingEnsemble(
            models=base_models,
            weights=config.arch_config.get("weights", None),
            voting_type=config.arch_config.get("voting_type", "average"),
        )

    def _create_stacking(self, config: ModelConfig) -> nn.Module:
        """Create stacking ensemble model."""
        from ai.models.ensemble.stacking_ensemble import StackingEnsemble

        # Create base models
        base_models = []
        for i in range(config.arch_config.get("num_base_models", 3)):
            base_config = self._create_base_config(
                config.arch_config.get("base_architecture", "lstm"),
                config
            )
            base_model = self._get_model_creator(
                ModelArchitecture(base_config.arch_config.get("base_architecture", "lstm"))
            )(base_config)
            base_models.append(base_model)

        # Create meta model
        meta_config = self._create_base_config(
            config.arch_config.get("meta_architecture", "xgboost"),
            config
        )
        meta_model = self._get_model_creator(
            ModelArchitecture(meta_config.arch_config.get("meta_architecture", "xgboost"))
        )(meta_config)

        return StackingEnsemble(
            base_models=base_models,
            meta_model=meta_model,
            use_features=config.arch_config.get("use_features", False),
        )

    def _create_voting(self, config: ModelConfig) -> nn.Module:
        """Create voting ensemble model."""
        from ai.models.ensemble.voting_ensemble import VotingEnsemble

        # Create base models
        base_models = []
        base_architectures = config.arch_config.get(
            "base_architectures",
            ["lstm", "gru", "transformer"]
        )
        for arch in base_architectures:
            base_config = self._create_base_config(arch, config)
            base_model = self._get_model_creator(ModelArchitecture(arch))(base_config)
            base_models.append(base_model)

        return VotingEnsemble(
            models=base_models,
            weights=config.arch_config.get("weights", None),
            voting_type=config.arch_config.get("voting_type", "weighted"),
        )

    def _create_bagging(self, config: ModelConfig) -> nn.Module:
        """Create bagging ensemble model."""
        from ai.models.ensemble.bagging_ensemble import BaggingEnsemble

        # Create base models
        base_models = []
        for i in range(config.arch_config.get("num_models", 5)):
            base_config = self._create_base_config(
                config.arch_config.get("base_architecture", "lstm"),
                config
            )
            # Add bootstrap randomness
            base_config.arch_config["bootstrap_seed"] = i
            base_model = self._get_model_creator(
                ModelArchitecture(base_config.arch_config.get("base_architecture", "lstm"))
            )(base_config)
            base_models.append(base_model)

        return BaggingEnsemble(
            models=base_models,
            aggregation_type=config.arch_config.get("aggregation_type", "average"),
            n_bootstraps=config.arch_config.get("num_models", 5),
        )

    def _create_base_config(
        self,
        architecture: str,
        parent_config: ModelConfig,
    ) -> ModelConfig:
        """Create a base model configuration."""
        base_config = ModelConfig(
            architecture=ModelArchitecture(architecture),
            task=parent_config.task,
            input_dim=parent_config.input_dim,
            output_dim=parent_config.output_dim,
            sequence_length=parent_config.sequence_length,
            hidden_dim=parent_config.hidden_dim // 2,
            num_layers=parent_config.num_layers,
            dropout=parent_config.dropout,
            learning_rate=parent_config.learning_rate,
            batch_size=parent_config.batch_size,
            epochs=parent_config.epochs,
            device=parent_config.device,
            arch_config=parent_config.arch_config.get(architecture, {}),
        )
        return base_config

    async def load_model(
        self,
        model_path: Union[str, Path],
        model_id: Optional[str] = None,
    ) -> nn.Module:
        """
        Load a saved model from disk.

        Args:
            model_path: Path to model file
            model_id: Optional model ID for caching

        Returns:
            Loaded model
        """
        model_path = Path(model_path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # Load model state
        model_data = torch.load(model_path, map_location="cpu")

        # Extract config
        config = model_data.get("config")
        if config:
            config = ModelConfig.from_dict(config)

        # Create model
        model = await self.create_model(config)

        # Load state dict
        if "model_state_dict" in model_data:
            model.load_state_dict(model_data["model_state_dict"])

        # Move to device
        model = model.to(config.device if config else "cpu")

        # Cache model
        if model_id:
            async with self._lock:
                self._model_cache[model_id] = model

        logger.info(f"Loaded model from {model_path}")

        return model

    async def save_model(
        self,
        model: nn.Module,
        model_id: str,
        config: ModelConfig,
        output_path: Union[str, Path],
        additional_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Save model to disk.

        Args:
            model: Model to save
            model_id: Model identifier
            config: Model configuration
            output_path: Output path
            additional_data: Additional data to save
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Prepare save data
        save_data = {
            "model_id": model_id,
            "config": config.to_dict(),
            "model_state_dict": model.state_dict(),
            "timestamp": str(timestamp()),
            "version": config.version,
        }

        if additional_data:
            save_data.update(additional_data)

        # Save
        torch.save(save_data, output_path)

        logger.info(f"Saved model to {output_path}")

        # Update registry
        async with self._lock:
            self._model_registry[model_id] = {
                "path": str(output_path),
                "config": config.to_dict(),
                "timestamp": save_data["timestamp"],
            }

    async def get_model(
        self,
        model_id: str,
    ) -> Optional[nn.Module]:
        """
        Get a cached model by ID.

        Args:
            model_id: Model identifier

        Returns:
            Model instance or None
        """
        async with self._lock:
            return self._model_cache.get(model_id)

    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List all registered models.

        Returns:
            List of model information
        """
        async with self._lock:
            return [
                {
                    "model_id": model_id,
                    **info,
                }
                for model_id, info in self._model_registry.items()
            ]

    async def delete_model(
        self,
        model_id: str,
        delete_file: bool = False,
    ):
        """
        Delete a model from registry.

        Args:
            model_id: Model identifier
            delete_file: Whether to delete the model file
        """
        async with self._lock:
            if model_id in self._model_registry:
                if delete_file:
                    model_path = Path(self._model_registry[model_id]["path"])
                    if model_path.exists():
                        model_path.unlink()

                del self._model_registry[model_id]

            if model_id in self._model_cache:
                del self._model_cache[model_id]

        logger.info(f"Deleted model {model_id}")

    async def create_optimizer(
        self,
        model: nn.Module,
        config: ModelConfig,
    ) -> optim.Optimizer:
        """
        Create optimizer for a model.

        Args:
            model: Model to optimize
            config: Model configuration

        Returns:
            Optimizer instance
        """
        optimizer_name = config.optimizer.lower()

        if optimizer_name == "adam":
            return optim.Adam(model.parameters(), lr=config.learning_rate)
        elif optimizer_name == "adamw":
            return optim.AdamW(model.parameters(), lr=config.learning_rate)
        elif optimizer_name == "sgd":
            return optim.SGD(model.parameters(), lr=config.learning_rate, momentum=0.9)
        elif optimizer_name == "rmsprop":
            return optim.RMSprop(model.parameters(), lr=config.learning_rate)
        elif optimizer_name == "lamb":
            from ai.models.optimizers.lamb import Lamb
            return Lamb(model.parameters(), lr=config.learning_rate)
        elif optimizer_name == "lookahead":
            from ai.models.optimizers.lookahead import Lookahead
            base_optimizer = optim.Adam(model.parameters(), lr=config.learning_rate)
            return Lookahead(base_optimizer)
        else:
            raise ValueError(f"Unsupported optimizer: {optimizer_name}")

    async def create_loss_function(
        self,
        config: ModelConfig,
    ) -> nn.Module:
        """
        Create loss function for a model.

        Args:
            config: Model configuration

        Returns:
            Loss function instance
        """
        loss_name = config.loss_function.lower()

        if loss_name == "mse":
            return nn.MSELoss()
        elif loss_name == "mae":
            return nn.L1Loss()
        elif loss_name == "huber":
            return nn.SmoothL1Loss()
        elif loss_name == "cross_entropy":
            return nn.CrossEntropyLoss()
        elif loss_name == "binary_cross_entropy":
            return nn.BCEWithLogitsLoss()
        elif loss_name == "quantile":
            from ai.models.losses.quantile_loss import QuantileLoss
            return QuantileLoss(quantile=0.5)
        elif loss_name == "mse_mae":
            from ai.models.losses.combined_loss import MSE_MAE_Loss
            return MSE_MAE_Loss()
        else:
            raise ValueError(f"Unsupported loss function: {loss_name}")


# Utility function for timestamp
def timestamp():
    """Get current timestamp."""
    from datetime import datetime
    return datetime.utcnow()


# Export model factory instance
model_factory = ModelFactory()
