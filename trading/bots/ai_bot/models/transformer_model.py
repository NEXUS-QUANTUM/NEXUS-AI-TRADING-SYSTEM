"""
NEXUS AI TRADING SYSTEM - Transformer Model
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced Transformer-based model for time series forecasting and trading.
Implements state-of-the-art transformer architectures with customizations
for financial data.
"""

import math
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn import TransformerEncoder, TransformerEncoderLayer

from shared.utilities.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TransformerConfig:
    """Configuration for Transformer model."""

    input_dim: int = 10
    output_dim: int = 1
    d_model: int = 256
    nhead: int = 8
    num_layers: int = 4
    dim_feedforward: int = 512
    dropout: float = 0.1
    activation: str = "gelu"
    batch_first: bool = True
    max_seq_len: int = 128
    use_positional_encoding: bool = True
    use_learnable_pe: bool = False
    use_time_embedding: bool = True
    use_feature_embedding: bool = False
    time_features_dim: int = 8
    feature_embedding_dim: int = 32
    use_attention_pooling: bool = False
    attention_pooling_heads: int = 4
    use_residual: bool = True
    use_layer_norm: bool = True
    use_multi_scale: bool = False
    scale_factors: List[int] = field(default_factory=lambda: [1, 2, 4])
    use_adaptive_attention: bool = False
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "d_model": self.d_model,
            "nhead": self.nhead,
            "num_layers": self.num_layers,
            "dim_feedforward": self.dim_feedforward,
            "dropout": self.dropout,
            "activation": self.activation,
            "batch_first": self.batch_first,
            "max_seq_len": self.max_seq_len,
            "use_positional_encoding": self.use_positional_encoding,
            "use_learnable_pe": self.use_learnable_pe,
            "use_time_embedding": self.use_time_embedding,
            "use_feature_embedding": self.use_feature_embedding,
            "time_features_dim": self.time_features_dim,
            "feature_embedding_dim": self.feature_embedding_dim,
            "use_attention_pooling": self.use_attention_pooling,
            "attention_pooling_heads": self.attention_pooling_heads,
            "use_residual": self.use_residual,
            "use_layer_norm": self.use_layer_norm,
            "use_multi_scale": self.use_multi_scale,
            "scale_factors": self.scale_factors,
            "use_adaptive_attention": self.use_adaptive_attention,
            "device": self.device,
        }


class PositionalEncoding(nn.Module):
    """
    Positional encoding for transformer models.
    Supports both sinusoidal and learnable positional encodings.
    """

    def __init__(
        self,
        d_model: int,
        max_seq_len: int = 512,
        dropout: float = 0.1,
        learnable: bool = False,
    ):
        """
        Initialize positional encoding.

        Args:
            d_model: Model dimension
            max_seq_len: Maximum sequence length
            dropout: Dropout rate
            learnable: Whether to use learnable positional encoding
        """
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        self.learnable = learnable

        if learnable:
            self.pe = nn.Parameter(torch.randn(1, max_seq_len, d_model) * 0.02)
        else:
            pe = torch.zeros(max_seq_len, d_model)
            position = torch.arange(0, max_seq_len, dtype=torch.float).unsqueeze(1)
            div_term = torch.exp(
                torch.arange(0, d_model, 2).float()
                * (-math.log(10000.0) / d_model)
            )
            pe[:, 0::2] = torch.sin(position * div_term)
            pe[:, 1::2] = torch.cos(position * div_term)
            pe = pe.unsqueeze(0)
            self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply positional encoding.

        Args:
            x: Input tensor (batch_size, seq_len, d_model)

        Returns:
            Tensor with positional encoding
        """
        if self.learnable:
            pe = self.pe[:, : x.size(1), :]
        else:
            pe = self.pe[:, : x.size(1), :]

        x = x + pe
        return self.dropout(x)


class TimeEmbedding(nn.Module):
    """
    Time embedding layer for temporal features.
    """

    def __init__(self, time_features_dim: int, d_model: int):
        """
        Initialize time embedding.

        Args:
            time_features_dim: Number of time features
            d_model: Model dimension
        """
        super().__init__()
        self.time_projection = nn.Linear(time_features_dim, d_model)

    def forward(
        self,
        x: torch.Tensor,
        time_features: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Apply time embedding.

        Args:
            x: Input tensor
            time_features: Time features (batch_size, seq_len, time_features_dim)

        Returns:
            Tensor with time embedding
        """
        if time_features is not None:
            time_emb = self.time_projection(time_features)
            x = x + time_emb
        return x


class FeatureEmbedding(nn.Module):
    """
    Feature embedding layer for categorical features.
    """

    def __init__(
        self,
        input_dim: int,
        feature_embedding_dim: int,
        d_model: int,
    ):
        """
        Initialize feature embedding.

        Args:
            input_dim: Input feature dimension
            feature_embedding_dim: Feature embedding dimension
            d_model: Model dimension
        """
        super().__init__()
        self.feature_projection = nn.Linear(input_dim, feature_embedding_dim)
        self.feature_to_model = nn.Linear(feature_embedding_dim, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply feature embedding.

        Args:
            x: Input tensor (batch_size, seq_len, input_dim)

        Returns:
            Tensor with feature embedding
        """
        x = self.feature_projection(x)
        x = F.gelu(x)
        x = self.feature_to_model(x)
        return x


class MultiScaleAttention(nn.Module):
    """
    Multi-scale attention for capturing patterns at different time scales.
    """

    def __init__(
        self,
        d_model: int,
        nhead: int,
        scale_factors: List[int],
        dropout: float = 0.1,
    ):
        """
        Initialize multi-scale attention.

        Args:
            d_model: Model dimension
            nhead: Number of attention heads
            scale_factors: Scale factors for downsampling
            dropout: Dropout rate
        """
        super().__init__()
        self.scale_factors = scale_factors
        self.attentions = nn.ModuleList()
        self.projections = nn.ModuleList()

        for _ in scale_factors:
            attn = nn.MultiheadAttention(
                d_model,
                nhead,
                dropout=dropout,
                batch_first=True,
            )
            self.attentions.append(attn)
            self.projections.append(nn.Linear(d_model, d_model))

        self.output_projection = nn.Linear(d_model * len(scale_factors), d_model)

    def forward(
        self,
        x: torch.Tensor,
        attn_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Apply multi-scale attention.

        Args:
            x: Input tensor (batch_size, seq_len, d_model)
            attn_mask: Attention mask

        Returns:
            Tensor with multi-scale attention
        """
        batch_size, seq_len, d_model = x.shape
        outputs = []

        for i, scale_factor in enumerate(self.scale_factors):
            if scale_factor == 1:
                scaled_x = x
            else:
                # Downsample
                new_len = seq_len // scale_factor
                if new_len > 1:
                    scaled_x = F.adaptive_avg_pool1d(
                        x.transpose(1, 2),
                        new_len,
                    ).transpose(1, 2)
                else:
                    scaled_x = x

            # Apply attention
            attn_output, _ = self.attentions[i](scaled_x, scaled_x, scaled_x)
            attn_output = self.projections[i](attn_output)

            # Upsample back to original length
            if scale_factor != 1:
                attn_output = F.interpolate(
                    attn_output.transpose(1, 2),
                    size=seq_len,
                    mode="linear",
                    align_corners=False,
                ).transpose(1, 2)

            outputs.append(attn_output)

        # Combine
        combined = torch.cat(outputs, dim=-1)
        combined = self.output_projection(combined)

        return combined


class AdaptiveAttention(nn.Module):
    """
    Adaptive attention with learnable sparsity.
    """

    def __init__(self, d_model: int, nhead: int, dropout: float = 0.1):
        """
        Initialize adaptive attention.

        Args:
            d_model: Model dimension
            nhead: Number of attention heads
            dropout: Dropout rate
        """
        super().__init__()
        self.attention = nn.MultiheadAttention(
            d_model,
            nhead,
            dropout=dropout,
            batch_first=True,
        )
        self.attention_weights = nn.Parameter(torch.randn(1, 1, 1) * 0.1)
        self.gate = nn.Sequential(
            nn.Linear(d_model, d_model // 4),
            nn.ReLU(),
            nn.Linear(d_model // 4, 1),
            nn.Sigmoid(),
        )

    def forward(
        self,
        x: torch.Tensor,
        attn_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Apply adaptive attention.

        Args:
            x: Input tensor
            attn_mask: Attention mask

        Returns:
            Tensor with adaptive attention
        """
        attn_output, attn_weights = self.attention(
            x,
            x,
            x,
            attn_mask=attn_mask,
            need_weights=True,
        )

        # Learnable gate
        gate = self.gate(x).squeeze(-1).unsqueeze(-1)
        output = gate * attn_output + (1 - gate) * x

        return output


class TransformerBlock(nn.Module):
    """
    Advanced transformer block with multiple enhancements.
    """

    def __init__(
        self,
        d_model: int,
        nhead: int,
        dim_feedforward: int,
        dropout: float = 0.1,
        activation: str = "gelu",
        use_multi_scale: bool = False,
        scale_factors: Optional[List[int]] = None,
        use_adaptive_attention: bool = False,
        use_residual: bool = True,
        use_layer_norm: bool = True,
    ):
        """
        Initialize transformer block.

        Args:
            d_model: Model dimension
            nhead: Number of attention heads
            dim_feedforward: Feedforward dimension
            dropout: Dropout rate
            activation: Activation function
            use_multi_scale: Whether to use multi-scale attention
            scale_factors: Scale factors for multi-scale attention
            use_adaptive_attention: Whether to use adaptive attention
            use_residual: Whether to use residual connections
            use_layer_norm: Whether to use layer normalization
        """
        super().__init__()
        self.use_residual = use_residual
        self.use_layer_norm = use_layer_norm

        # Attention
        if use_multi_scale:
            self.attention = MultiScaleAttention(
                d_model,
                nhead,
                scale_factors or [1, 2, 4],
                dropout,
            )
        elif use_adaptive_attention:
            self.attention = AdaptiveAttention(d_model, nhead, dropout)
        else:
            self.attention = nn.MultiheadAttention(
                d_model,
                nhead,
                dropout=dropout,
                batch_first=True,
            )

        # Feedforward
        self.feedforward = nn.Sequential(
            nn.Linear(d_model, dim_feedforward),
            self._get_activation(activation),
            nn.Dropout(dropout),
            nn.Linear(dim_feedforward, d_model),
            nn.Dropout(dropout),
        )

        # Layer norms
        if use_layer_norm:
            self.norm1 = nn.LayerNorm(d_model)
            self.norm2 = nn.LayerNorm(d_model)

    def _get_activation(self, name: str) -> nn.Module:
        """Get activation function."""
        if name == "relu":
            return nn.ReLU()
        elif name == "gelu":
            return nn.GELU()
        elif name == "silu":
            return nn.SiLU()
        elif name == "mish":
            return nn.Mish()
        else:
            return nn.GELU()

    def forward(
        self,
        x: torch.Tensor,
        attn_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Apply transformer block.

        Args:
            x: Input tensor
            attn_mask: Attention mask

        Returns:
            Output tensor
        """
        # Attention
        attn_output = self.attention(x, attn_mask=attn_mask)

        if self.use_residual:
            if self.use_layer_norm:
                x = self.norm1(x + attn_output)
            else:
                x = x + attn_output
        else:
            x = attn_output

        # Feedforward
        ff_output = self.feedforward(x)

        if self.use_residual:
            if self.use_layer_norm:
                x = self.norm2(x + ff_output)
            else:
                x = x + ff_output
        else:
            x = ff_output

        return x


class TransformerModel(nn.Module):
    """
    Advanced Transformer model for time series forecasting.
    """

    def __init__(self, config: Union[TransformerConfig, Dict[str, Any]]):
        """
        Initialize Transformer model.

        Args:
            config: Transformer configuration
        """
        super().__init__()

        if isinstance(config, dict):
            config = TransformerConfig(**config)

        self.config = config
        self.input_dim = config.input_dim
        self.output_dim = config.output_dim
        self.d_model = config.d_model
        self.max_seq_len = config.max_seq_len

        # Input projection
        if config.use_feature_embedding:
            self.input_projection = FeatureEmbedding(
                config.input_dim,
                config.feature_embedding_dim,
                config.d_model,
            )
        else:
            self.input_projection = nn.Linear(config.input_dim, config.d_model)

        # Positional encoding
        if config.use_positional_encoding:
            self.positional_encoding = PositionalEncoding(
                config.d_model,
                config.max_seq_len,
                config.dropout,
                config.use_learnable_pe,
            )
        else:
            self.positional_encoding = None

        # Time embedding
        if config.use_time_embedding:
            self.time_embedding = TimeEmbedding(
                config.time_features_dim,
                config.d_model,
            )
        else:
            self.time_embedding = None

        # Transformer blocks
        self.transformer_blocks = nn.ModuleList(
            [
                TransformerBlock(
                    d_model=config.d_model,
                    nhead=config.nhead,
                    dim_feedforward=config.dim_feedforward,
                    dropout=config.dropout,
                    activation=config.activation,
                    use_multi_scale=config.use_multi_scale and i == 0,
                    scale_factors=config.scale_factors if i == 0 else None,
                    use_adaptive_attention=config.use_adaptive_attention,
                    use_residual=config.use_residual,
                    use_layer_norm=config.use_layer_norm,
                )
                for i in range(config.num_layers)
            ]
        )

        # Output projection
        if config.use_attention_pooling:
            self.output_projection = nn.Sequential(
                nn.MultiheadAttention(
                    config.d_model,
                    config.attention_pooling_heads,
                    batch_first=True,
                ),
                nn.Linear(config.d_model, config.output_dim),
            )
        else:
            self.output_projection = nn.Sequential(
                nn.Linear(config.d_model, config.d_model // 2),
                nn.GELU(),
                nn.Dropout(config.dropout),
                nn.Linear(config.d_model // 2, config.output_dim),
            )

        # Initialization
        self._init_weights()

        logger.info(
            f"TransformerModel initialized with config: "
            f"d_model={config.d_model}, "
            f"nhead={config.nhead}, "
            f"num_layers={config.num_layers}"
        )

    def _init_weights(self):
        """Initialize model weights."""
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)

    def forward(
        self,
        x: torch.Tensor,
        time_features: Optional[torch.Tensor] = None,
        attn_mask: Optional[torch.Tensor] = None,
        return_attention: bool = False,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, List[torch.Tensor]]]:
        """
        Forward pass.

        Args:
            x: Input tensor (batch_size, seq_len, input_dim)
            time_features: Time features (batch_size, seq_len, time_features_dim)
            attn_mask: Attention mask
            return_attention: Whether to return attention weights

        Returns:
            Output tensor (batch_size, output_dim) or (batch_size, seq_len, output_dim)
            or tuple of (output, attention_weights)
        """
        batch_size, seq_len, _ = x.shape

        # Input projection
        x = self.input_projection(x)

        # Time embedding
        if self.time_embedding is not None:
            x = self.time_embedding(x, time_features)

        # Positional encoding
        if self.positional_encoding is not None:
            x = self.positional_encoding(x)

        # Transformer blocks
        attention_weights = []
        for block in self.transformer_blocks:
            x = block(x, attn_mask)
            if return_attention and hasattr(block.attention, "attention"):
                if hasattr(block.attention.attention, "attention_weights"):
                    attention_weights.append(block.attention.attention.attention_weights)

        # Output projection
        if self.config.use_attention_pooling:
            # Pool over sequence dimension
            x, _ = self.output_projection[0](x, x, x)
            x = self.output_projection[1](x)
            # Take mean over sequence
            x = x.mean(dim=1)
        else:
            # Use last output
            x = self.output_projection(x[:, -1, :])

        if return_attention:
            return x, attention_weights

        return x

    def predict(
        self,
        x: torch.Tensor,
        time_features: Optional[torch.Tensor] = None,
        return_uncertainty: bool = False,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Make prediction with optional uncertainty.

        Args:
            x: Input tensor
            time_features: Time features
            return_uncertainty: Whether to return uncertainty estimates

        Returns:
            Predictions and optionally uncertainty
        """
        self.eval()

        with torch.no_grad():
            if return_uncertainty and self.training:
                # Monte Carlo dropout for uncertainty
                self.train()
                predictions = []
                for _ in range(10):
                    pred = self(x, time_features)
                    predictions.append(pred)
                self.eval()

                pred_tensor = torch.stack(predictions)
                mean = pred_tensor.mean(dim=0)
                std = pred_tensor.std(dim=0)
                return mean, std

            # Single prediction
            output = self(x, time_features)

            if return_uncertainty:
                # Return confidence based on output variance
                # (simplified approximation)
                return output, torch.ones_like(output) * 0.05

            return output


class TransformerForecaster:
    """
    Wrapper class for transformer model with training and forecasting utilities.
    """

    def __init__(self, config: Union[TransformerConfig, Dict[str, Any]]):
        """
        Initialize transformer forecaster.

        Args:
            config: Transformer configuration
        """
        self.config = config
        self.model = TransformerModel(config)

    def train_step(
        self,
        x: torch.Tensor,
        y: torch.Tensor,
        time_features: Optional[torch.Tensor] = None,
        optimizer: Optional[torch.optim.Optimizer] = None,
        loss_fn: Optional[nn.Module] = None,
    ) -> float:
        """
        Single training step.

        Args:
            x: Input tensor
            y: Target tensor
            time_features: Time features
            optimizer: Optimizer
            loss_fn: Loss function

        Returns:
            Loss value
        """
        self.model.train()

        if optimizer is None:
            return 0.0

        optimizer.zero_grad()

        predictions = self.model(x, time_features)
        loss = loss_fn(predictions, y) if loss_fn else F.mse_loss(predictions, y)

        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        optimizer.step()

        return loss.item()

    def forecast(
        self,
        x: torch.Tensor,
        steps: int,
        time_features: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Forecast multiple steps ahead.

        Args:
            x: Input tensor
            steps: Number of steps to forecast
            time_features: Time features

        Returns:
            Forecasted values
        """
        self.model.eval()

        predictions = []
        current_input = x

        with torch.no_grad():
            for _ in range(steps):
                pred = self.model(current_input)
                predictions.append(pred)

                # Update input for next step (sliding window)
                if time_features is not None:
                    # Shift time features
                    time_features = time_features[:, 1:, :]

                # Shift input and append prediction
                if current_input.size(1) > 1:
                    current_input = current_input[:, 1:, :]
                else:
                    # If sequence length is 1, need to expand
                    current_input = torch.cat(
                        [current_input[:, 1:, :], pred.unsqueeze(1)],
                        dim=1,
                    )

        return torch.stack(predictions)

    def save(self, path: str):
        """
        Save model.

        Args:
            path: Path to save model
        """
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "config": self.config.to_dict(),
        }, path)

    def load(self, path: str):
        """
        Load model.

        Args:
            path: Path to load model from
        """
        checkpoint = torch.load(path, map_location="cpu")
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.config = TransformerConfig(**checkpoint["config"])
