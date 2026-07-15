# ai/neural/embeddings/token_embedding.py
"""
NEXUS AI TRADING SYSTEM - Token Embedding Module
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
class TokenEmbeddingConfig:
    """Configuration pour Token Embedding"""
    vocab_size: int = 10000
    embed_dim: int = 256
    padding_idx: Optional[int] = None
    max_norm: Optional[float] = None
    norm_type: float = 2.0
    scale_grad_by_freq: bool = False
    sparse: bool = False
    use_pretrained: bool = False
    pretrained_weights: Optional[torch.Tensor] = None
    freeze: bool = False
    dropout: float = 0.0

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if self.vocab_size <= 0:
            raise ValueError("vocab_size doit être > 0")
        if self.embed_dim <= 0:
            raise ValueError("embed_dim doit être > 0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'vocab_size': self.vocab_size,
            'embed_dim': self.embed_dim,
            'padding_idx': self.padding_idx,
            'max_norm': self.max_norm,
            'norm_type': self.norm_type,
            'scale_grad_by_freq': self.scale_grad_by_freq,
            'sparse': self.sparse,
            'use_pretrained': self.use_pretrained,
            'freeze': self.freeze,
            'dropout': self.dropout,
        }


class TokenEmbedding(nn.Module):
    """
    Token Embedding module.

    Converts token indices to dense vector representations.
    Supports:
    - Standard embedding with configurable parameters
    - Pretrained embeddings (e.g., Word2Vec, GloVe)
    - Padding for variable-length sequences
    - Dropout for regularization
    - Freezing for transfer learning

    Example:
        ```python
        config = TokenEmbeddingConfig(
            vocab_size=10000,
            embed_dim=256,
            padding_idx=0
        )
        token_emb = TokenEmbedding(config)

        # Embed token indices
        embeddings = token_emb(token_ids)
        ```
    """

    def __init__(self, config: Optional[TokenEmbeddingConfig] = None):
        super().__init__()

        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or TokenEmbeddingConfig()
        self.vocab_size = self.config.vocab_size
        self.embed_dim = self.config.embed_dim
        self.padding_idx = self.config.padding_idx
        self.max_norm = self.config.max_norm
        self.norm_type = self.config.norm_type
        self.scale_grad_by_freq = self.config.scale_grad_by_freq
        self.sparse = self.config.sparse
        self.use_pretrained = self.config.use_pretrained
        self.freeze = self.config.freeze
        self.dropout = nn.Dropout(self.config.dropout) if self.config.dropout > 0 else nn.Identity()

        # Création de l'embedding
        if self.use_pretrained and self.config.pretrained_weights is not None:
            self._init_pretrained()
        else:
            self._init_random()

        # Layer norm (optionnel)
        self.layer_norm = nn.LayerNorm(self.embed_dim) if self.config.dropout > 0 else nn.Identity()

    def _init_random(self):
        """Initialisation aléatoire"""
        self.embedding = nn.Embedding(
            num_embeddings=self.vocab_size,
            embedding_dim=self.embed_dim,
            padding_idx=self.padding_idx,
            max_norm=self.max_norm,
            norm_type=self.norm_type,
            scale_grad_by_freq=self.scale_grad_by_freq,
            sparse=self.sparse,
        )
        self._reset_parameters()

    def _init_pretrained(self):
        """Initialisation avec des poids pré-entraînés"""
        weights = self.config.pretrained_weights
        vocab_size, embed_dim = weights.shape

        if vocab_size != self.vocab_size or embed_dim != self.embed_dim:
            logger.warning(
                f"Taille des poids pré-entraînés ({vocab_size}, {embed_dim}) "
                f"diffère de la configuration ({self.vocab_size}, {self.embed_dim})"
            )
            # Ajustement
            if embed_dim != self.embed_dim:
                # Projection pour ajuster la dimension
                projection = nn.Linear(embed_dim, self.embed_dim, bias=False)
                weights = projection(weights)
            if vocab_size != self.vocab_size:
                # Troncature ou padding
                if vocab_size < self.vocab_size:
                    pad = torch.zeros(self.vocab_size - vocab_size, self.embed_dim)
                    weights = torch.cat([weights, pad], dim=0)
                else:
                    weights = weights[:self.vocab_size]

        self.embedding = nn.Embedding.from_pretrained(
            weights,
            freeze=self.freeze,
            padding_idx=self.padding_idx,
            max_norm=self.max_norm,
            norm_type=self.norm_type,
            scale_grad_by_freq=self.scale_grad_by_freq,
            sparse=self.sparse,
        )

    def _reset_parameters(self):
        """Initialise les paramètres"""
        # Xavier uniform pour l'embedding
        nn.init.xavier_uniform_(self.embedding.weight)

        if self.padding_idx is not None:
            with torch.no_grad():
                self.embedding.weight[self.padding_idx].fill_(0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Embedding des tokens.

        Args:
            x: Indices des tokens [batch_size, seq_len]

        Returns:
            torch.Tensor: Embeddings [batch_size, seq_len, embed_dim]
        """
        embeddings = self.embedding(x)
        embeddings = self.dropout(embeddings)
        embeddings = self.layer_norm(embeddings)
        return embeddings

    def get_embeddings(self) -> torch.Tensor:
        """Retourne la matrice d'embedding"""
        return self.embedding.weight

    def get_pretrained_weights(self) -> torch.Tensor:
        """Retourne les poids pré-entraînés (si utilisés)"""
        if self.use_pretrained:
            return self.embedding.weight
        return None

    def set_pretrained_weights(self, weights: torch.Tensor):
        """Définit de nouveaux poids pré-entraînés"""
        if weights.shape != self.embedding.weight.shape:
            raise ValueError(f"Shape mismatch: {weights.shape} vs {self.embedding.weight.shape}")
        self.embedding.weight.data = weights


class MultiTokenEmbedding(nn.Module):
    """
    Multi-Token Embedding.

    Combine plusieurs embeddings (caractères, sous-mots, mots)
    pour une représentation riche.
    """

    def __init__(
        self,
        vocab_sizes: List[int],
        embed_dims: List[int],
        padding_idxs: Optional[List[int]] = None,
        dropout: float = 0.0
    ):
        super().__init__()

        if len(vocab_sizes) != len(embed_dims):
            raise ValueError("vocab_sizes et embed_dims doivent avoir la même longueur")

        self.num_embeddings = len(vocab_sizes)
        self.embed_dims = embed_dims
        self.total_embed_dim = sum(embed_dims)

        if padding_idxs is None:
            padding_idxs = [None] * self.num_embeddings

        self.embeddings = nn.ModuleList([
            TokenEmbedding(
                TokenEmbeddingConfig(
                    vocab_size=vocab_sizes[i],
                    embed_dim=embed_dims[i],
                    padding_idx=padding_idxs[i],
                    dropout=dropout,
                )
            )
            for i in range(self.num_embeddings)
        ])

        self.dropout = nn.Dropout(dropout) if dropout > 0 else nn.Identity()
        self.layer_norm = nn.LayerNorm(self.total_embed_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Combine les embeddings de multiples tokens.

        Args:
            x: Liste ou tensor d'indices [batch_size, seq_len, num_embeddings]

        Returns:
            torch.Tensor: Embeddings combinés
        """
        if isinstance(x, torch.Tensor) and x.dim() == 3:
            # [batch_size, seq_len, num_embeddings]
            embeddings = []
            for i in range(self.num_embeddings):
                indices = x[:, :, i]
                emb = self.embeddings[i](indices)
                embeddings.append(emb)
            combined = torch.cat(embeddings, dim=-1)
        else:
            # Single embedding
            combined = self.embeddings[0](x)

        combined = self.dropout(combined)
        combined = self.layer_norm(combined)

        return combined


class AdaptiveTokenEmbedding(nn.Module):
    """
    Token Embedding adaptatif avec poids appris.

    Permet d'apprendre l'importance relative des différentes
    dimensions de l'embedding.
    """

    def __init__(self, config: TokenEmbeddingConfig):
        super().__init__()

        self.config = config
        self.embedding = TokenEmbedding(config)

        # Poids appris par dimension
        self.importance = nn.Parameter(torch.ones(config.embed_dim))

        self.scale = nn.Parameter(torch.ones(1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        embeddings = self.embedding(x)

        # Appliquer les poids d'importance
        importance = F.softmax(self.importance, dim=0)
        embeddings = embeddings * importance * self.scale

        return embeddings


class PositionalTokenEmbedding(nn.Module):
    """
    Token Embedding avec encodage positionnel intégré.

    Combine token embedding et positional encoding en une seule couche.
    """

    def __init__(self, config: TokenEmbeddingConfig, max_length: int = 1000):
        super().__init__()

        self.config = config
        self.embedding = TokenEmbedding(config)

        # Positional encoding
        from ai.neural.embeddings.positional_encoding import PositionalEncoding, PositionalEncodingConfig

        self.positional = PositionalEncoding(
            PositionalEncodingConfig(
                embed_dim=config.embed_dim,
                max_length=max_length,
                encoding_type='sinusoidal'
            )
        )

        self.dropout = nn.Dropout(config.dropout) if config.dropout > 0 else nn.Identity()
        self.layer_norm = nn.LayerNorm(config.embed_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Combine token embedding et positional encoding.

        Args:
            x: Indices des tokens [batch_size, seq_len]

        Returns:
            torch.Tensor: Embeddings positionnels
        """
        embeddings = self.embedding(x)
        embeddings = self.positional(embeddings)
        embeddings = self.dropout(embeddings)
        embeddings = self.layer_norm(embeddings)

        return embeddings


def create_token_embedding(
    vocab_size: int = 10000,
    embed_dim: int = 256,
    padding_idx: Optional[int] = None,
    dropout: float = 0.0,
    **kwargs
) -> TokenEmbedding:
    """
    Factory pour créer des Token Embeddings.

    Args:
        vocab_size: Taille du vocabulaire
        embed_dim: Dimension d'embedding
        padding_idx: Index de padding
        dropout: Taux de dropout
        **kwargs: Arguments supplémentaires

    Returns:
        TokenEmbedding: Instance de TokenEmbedding
    """
    config = TokenEmbeddingConfig(
        vocab_size=vocab_size,
        embed_dim=embed_dim,
        padding_idx=padding_idx,
        dropout=dropout,
        **kwargs
    )
    return TokenEmbedding(config)


__all__ = [
    'TokenEmbedding',
    'TokenEmbeddingConfig',
    'MultiTokenEmbedding',
    'AdaptiveTokenEmbedding',
    'PositionalTokenEmbedding',
    'create_token_embedding',
]
