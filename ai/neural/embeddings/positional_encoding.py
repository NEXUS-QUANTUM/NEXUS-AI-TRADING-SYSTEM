
# ai/neural/embeddings/positional_encoding.py
"""
NEXUS AI TRADING SYSTEM - Positional Encoding Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class PositionalEncodingConfig:
    """Configuration pour Positional Encoding"""
    embed_dim: int = 256
    max_length: int = 1000
    dropout: float = 0.1
    encoding_type: str = 'sinusoidal'  # sinusoidal, learned, relative, rotary
    scale: float = 1.0
    learnable: bool = False
    bidirectional: bool = True

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        valid_types = ['sinusoidal', 'learned', 'relative', 'rotary']
        if self.encoding_type not in valid_types:
            raise ValueError(f"Type d'encodage non supporté: {self.encoding_type}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'embed_dim': self.embed_dim,
            'max_length': self.max_length,
            'dropout': self.dropout,
            'encoding_type': self.encoding_type,
            'scale': self.scale,
            'learnable': self.learnable,
            'bidirectional': self.bidirectional,
        }


class PositionalEncoding(nn.Module):
    """
    Positional Encoding for transformer models.

    Positional encoding adds information about the position of tokens
    in a sequence, which is necessary for models that don't have
    built-in sequence order information.

    Supports:
    - Sinusoidal encoding (original Transformer)
    - Learned positional encoding
    - Relative position encoding
    - Rotary position embedding (RoPE)

    Example:
        ```python
        config = PositionalEncodingConfig(
            embed_dim=256,
            max_length=512,
            encoding_type='sinusoidal'
        )
        pos_enc = PositionalEncoding(config)

        # Add to embeddings
        x = x + pos_enc(x)
        ```
    """

    def __init__(self, config: Optional[PositionalEncodingConfig] = None):
        super().__init__()

        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or PositionalEncodingConfig()
        self.embed_dim = self.config.embed_dim
        self.max_length = self.config.max_length
        self.dropout = nn.Dropout(self.config.dropout)
        self.encoding_type = self.config.encoding_type
        self.scale = self.config.scale
        self.learnable = self.config.learnable

        if self.encoding_type == 'sinusoidal':
            self._init_sinusoidal()
        elif self.encoding_type == 'learned':
            self._init_learned()
        elif self.encoding_type == 'relative':
            self._init_relative()
        elif self.encoding_type == 'rotary':
            self._init_rotary()
        else:
            raise ValueError(f"Type d'encodage non supporté: {self.encoding_type}")

    def _init_sinusoidal(self):
        """Initialise l'encodage positionnel sinusoidal"""
        pe = torch.zeros(self.max_length, self.embed_dim)

        position = torch.arange(0, self.max_length, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, self.embed_dim, 2).float() *
            (-np.log(10000.0) / self.embed_dim)
        )

        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)

        if self.learnable:
            self.pe = nn.Parameter(pe)
        else:
            self.register_buffer('pe', pe)

    def _init_learned(self):
        """Initialise l'encodage positionnel appris"""
        self.pe = nn.Parameter(torch.randn(1, self.max_length, self.embed_dim) * 0.02)

    def _init_relative(self):
        """Initialise l'encodage positionnel relatif"""
        self.relative_bias = nn.Parameter(torch.zeros(1, self.max_length, self.max_length))

        # Projections pour les positions relatives
        self.pos_proj = nn.Linear(self.embed_dim, self.embed_dim, bias=False)

    def _init_rotary(self):
        """
        Initialise l'encodage positionnel rotatif (RoPE)

        Rotary Position Embedding (RoPE) encode la position en utilisant
        des rotations dans l'espace complexe.
        """
        # Fréquences
        inv_freq = 1.0 / (10000 ** (torch.arange(0, self.embed_dim, 2).float() / self.embed_dim))
        self.register_buffer('inv_freq', inv_freq)

        # Cache pour les cosinus/sinus
        self.cached_cos = None
        self.cached_sin = None
        self.cached_seq_len = None

    def _get_rotary_embeddings(self, seq_len: int, device: torch.device) -> Tuple[torch.Tensor, torch.Tensor]:
        """Calcule les embeddings rotatifs"""
        if self.cached_seq_len == seq_len and self.cached_cos is not None:
            return self.cached_cos, self.cached_sin

        t = torch.arange(seq_len, device=device).type_as(self.inv_freq)
        freqs = torch.einsum('i,j->ij', t, self.inv_freq)
        emb = torch.cat((freqs, freqs), dim=-1)

        cos = torch.cos(emb)
        sin = torch.sin(emb)

        self.cached_cos = cos
        self.cached_sin = sin
        self.cached_seq_len = seq_len

        return cos, sin

    def _apply_rotary_embedding(self, x: torch.Tensor) -> torch.Tensor:
        """
        Applique Rotary Position Embedding (RoPE) à un tensor.

        RoPE applique des rotations aux paires de dimensions pour
        encoder la position de manière relative.
        """
        seq_len = x.size(1)
        cos, sin = self._get_rotary_embeddings(seq_len, x.device)

        # Reshape pour appliquer la rotation par paires
        x_reshape = x.view(*x.shape[:-1], -1, 2)
        x_complex = torch.view_as_complex(x_reshape.float())

        # Rotation
        rot_cos = cos.unsqueeze(0).unsqueeze(0)
        rot_sin = sin.unsqueeze(0).unsqueeze(0)
        rot_cos = rot_cos.to(x.device)
        rot_sin = rot_sin.to(x.device)

        # Reconstruction
        x_rotated = torch.view_as_real(x_complex * torch.exp(1j * rot_sin))
        x_rotated = x_rotated.view(*x.shape)

        return x_rotated

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Applique l'encodage positionnel.

        Args:
            x: Tensor d'entrée [batch_size, seq_len, embed_dim]

        Returns:
            torch.Tensor: Tensor avec encodage positionnel
        """
        if self.encoding_type == 'sinusoidal' or self.encoding_type == 'learned':
            seq_len = x.size(1)
            if seq_len > self.max_length:
                raise ValueError(f"seq_len ({seq_len}) > max_length ({self.max_length})")

            if self.encoding_type == 'sinusoidal':
                pe = self.pe[:seq_len, :].unsqueeze(0)
                if self.learnable:
                    pe = pe * self.scale
                x = x + pe
            else:  # learned
                pe = self.pe[:, :seq_len, :] * self.scale
                x = x + pe

            return self.dropout(x)

        elif self.encoding_type == 'relative':
            seq_len = x.size(1)
            if seq_len > self.max_length:
                raise ValueError(f"seq_len ({seq_len}) > max_length ({self.max_length})")

            bias = self.relative_bias[:, :seq_len, :seq_len]
            x = x + bias
            return self.dropout(x)

        elif self.encoding_type == 'rotary':
            return self._apply_rotary_embedding(x)

        else:
            return x

    def get_pe(self, seq_len: Optional[int] = None) -> torch.Tensor:
        """
        Retourne l'encodage positionnel.

        Args:
            seq_len: Longueur de séquence (optionnel)

        Returns:
            torch.Tensor: Encodage positionnel
        """
        if self.encoding_type == 'sinusoidal' or self.encoding_type == 'learned':
            if seq_len is None:
                seq_len = self.max_length
            if seq_len > self.max_length:
                raise ValueError(f"seq_len ({seq_len}) > max_length ({self.max_length})")

            if self.encoding_type == 'sinusoidal':
                return self.pe[:seq_len, :].unsqueeze(0) * self.scale
            else:
                return self.pe[:, :seq_len, :] * self.scale

        elif self.encoding_type == 'relative':
            if seq_len is None:
                seq_len = self.max_length
            if seq_len > self.max_length:
                raise ValueError(f"seq_len ({seq_len}) > max_length ({self.max_length})")
            return self.relative_bias[:, :seq_len, :seq_len]

        elif self.encoding_type == 'rotary':
            if seq_len is None:
                seq_len = self.max_length
            cos, sin = self._get_rotary_embeddings(seq_len, self.inv_freq.device)
            return torch.stack([cos, sin], dim=-1)

        else:
            return None


class LearnablePositionalEncoding(nn.Module):
    """Encodage positionnel appris"""

    def __init__(self, embed_dim: int, max_length: int = 1000, dropout: float = 0.1):
        super().__init__()

        self.embed_dim = embed_dim
        self.max_length = max_length
        self.dropout = nn.Dropout(dropout)

        self.pe = nn.Parameter(torch.randn(1, max_length, embed_dim) * 0.02)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        seq_len = x.size(1)
        if seq_len > self.max_length:
            raise ValueError(f"seq_len ({seq_len}) > max_length ({self.max_length})")

        x = x + self.pe[:, :seq_len, :]
        return self.dropout(x)


class RelativePositionalEncoding(nn.Module):
    """Encodage positionnel relatif"""

    def __init__(self, embed_dim: int, max_length: int = 1000):
        super().__init__()

        self.embed_dim = embed_dim
        self.max_length = max_length

        # Biais relatif
        self.relative_bias = nn.Parameter(torch.zeros(1, max_length, max_length))

        # Projection pour les positions relatives
        self.pos_proj = nn.Linear(embed_dim, embed_dim, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        seq_len = x.size(1)
        if seq_len > self.max_length:
            raise ValueError(f"seq_len ({seq_len}) > max_length ({self.max_length})")

        bias = self.relative_bias[:, :seq_len, :seq_len]
        x = x + bias
        return x


class RotaryPositionalEmbedding(nn.Module):
    """
    Rotary Position Embedding (RoPE)

    Implémente l'encodage positionnel rotatif qui est plus efficace
    pour les longues séquences et capture mieux les relations relatives.
    """

    def __init__(self, embed_dim: int, max_length: int = 1000):
        super().__init__()

        self.embed_dim = embed_dim
        self.max_length = max_length

        # Fréquences
        inv_freq = 1.0 / (10000 ** (torch.arange(0, embed_dim, 2).float() / embed_dim))
        self.register_buffer('inv_freq', inv_freq)

        self.cached_cos = None
        self.cached_sin = None
        self.cached_seq_len = None

    def _get_embeddings(self, seq_len: int, device: torch.device) -> Tuple[torch.Tensor, torch.Tensor]:
        if self.cached_seq_len == seq_len and self.cached_cos is not None:
            return self.cached_cos, self.cached_sin

        t = torch.arange(seq_len, device=device).type_as(self.inv_freq)
        freqs = torch.einsum('i,j->ij', t, self.inv_freq)
        emb = torch.cat((freqs, freqs), dim=-1)

        cos = torch.cos(emb)
        sin = torch.sin(emb)

        self.cached_cos = cos
        self.cached_sin = sin
        self.cached_seq_len = seq_len

        return cos, sin

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Applique RoPE au tensor d'entrée.

        Args:
            x: Tensor d'entrée [batch_size, seq_len, embed_dim]

        Returns:
            torch.Tensor: Tensor avec RoPE
        """
        seq_len = x.size(1)
        if seq_len > self.max_length:
            raise ValueError(f"seq_len ({seq_len}) > max_length ({self.max_length})")

        cos, sin = self._get_embeddings(seq_len, x.device)

        # Reshape pour rotation par paires
        x_reshape = x.view(*x.shape[:-1], -1, 2)
        x_complex = torch.view_as_complex(x_reshape.float())

        # Rotation
        rot_cos = cos.unsqueeze(0).unsqueeze(0)
        rot_sin = sin.unsqueeze(0).unsqueeze(0)
        rot_cos = rot_cos.to(x.device)
        rot_sin = rot_sin.to(x.device)

        # Reconstruction
        x_rotated = torch.view_as_real(x_complex * torch.exp(1j * rot_sin))
        x_rotated = x_rotated.view(*x.shape)

        return x_rotated


def create_positional_encoding(
    embed_dim: int = 256,
    max_length: int = 1000,
    encoding_type: str = 'sinusoidal',
    dropout: float = 0.1,
    **kwargs
) -> PositionalEncoding:
    """
    Factory pour créer un module d'encodage positionnel.

    Args:
        embed_dim: Dimension d'embedding
        max_length: Longueur maximum
        encoding_type: Type d'encodage ('sinusoidal', 'learned', 'relative', 'rotary')
        dropout: Taux de dropout
        **kwargs: Arguments supplémentaires

    Returns:
        PositionalEncoding: Instance de PositionalEncoding
    """
    config = PositionalEncodingConfig(
        embed_dim=embed_dim,
        max_length=max_length,
        encoding_type=encoding_type,
        dropout=dropout,
        **kwargs
    )
    return PositionalEncoding(config)


__all__ = [
    'PositionalEncoding',
    'PositionalEncodingConfig',
    'LearnablePositionalEncoding',
    'RelativePositionalEncoding',
    'RotaryPositionalEmbedding',
    'create_positional_encoding',
]
