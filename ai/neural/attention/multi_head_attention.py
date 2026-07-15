
# ai/neural/attention/multi_head_attention.py
"""
NEXUS AI TRADING SYSTEM - Multi-Head Attention Module
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
class MultiHeadAttentionConfig:
    """Configuration pour Multi-Head Attention"""
    embed_dim: int = 256
    num_heads: int = 8
    dropout: float = 0.1
    bias: bool = True
    add_bias_kv: bool = False
    add_zero_attn: bool = False
    kdim: Optional[int] = None
    vdim: Optional[int] = None
    batch_first: bool = True
    use_scale: bool = True
    use_flash_attention: bool = False

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if self.embed_dim % self.num_heads != 0:
            raise ValueError("embed_dim doit être divisible par num_heads")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'embed_dim': self.embed_dim,
            'num_heads': self.num_heads,
            'dropout': self.dropout,
            'bias': self.bias,
            'add_bias_kv': self.add_bias_kv,
            'add_zero_attn': self.add_zero_attn,
            'kdim': self.kdim,
            'vdim': self.vdim,
            'batch_first': self.batch_first,
            'use_scale': self.use_scale,
            'use_flash_attention': self.use_flash_attention,
        }


class MultiHeadAttention(nn.Module):
    """
    Multi-Head Attention module as described in "Attention Is All You Need".

    Multi-Head Attention allows the model to jointly attend to information
    from different representation subspaces at different positions.

    Features:
    - Multi-head attention with configurable heads
    - Flash Attention support (PyTorch 2.0+)
    - Masking (padding mask, causal mask)
    - Dropout
    - Bias options
    - Batch-first operations

    Example:
        ```python
        config = MultiHeadAttentionConfig(
            embed_dim=256,
            num_heads=8,
            dropout=0.1
        )
        mha = MultiHeadAttention(config)

        # Self-attention
        output = mha(query, key, value)

        # With masks
        output = mha(query, key, value, attn_mask=causal_mask)
        ```
    """

    def __init__(self, config: Optional[MultiHeadAttentionConfig] = None):
        super().__init__()

        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or MultiHeadAttentionConfig()
        self.embed_dim = self.config.embed_dim
        self.num_heads = self.config.num_heads
        self.dropout = self.config.dropout
        self.bias = self.config.bias
        self.add_bias_kv = self.config.add_bias_kv
        self.add_zero_attn = self.config.add_zero_attn
        self.batch_first = self.config.batch_first
        self.use_scale = self.config.use_scale
        self.use_flash_attention = self.config.use_flash_attention

        self.kdim = self.config.kdim if self.config.kdim is not None else self.embed_dim
        self.vdim = self.config.vdim if self.config.vdim is not None else self.embed_dim

        self.head_dim = self.embed_dim // self.num_heads
        self.scaling = self.head_dim ** -0.5 if self.config.use_scale else 1.0

        # Projections
        self.q_proj = nn.Linear(self.embed_dim, self.embed_dim, bias=self.bias)
        self.k_proj = nn.Linear(self.kdim, self.embed_dim, bias=self.bias)
        self.v_proj = nn.Linear(self.vdim, self.embed_dim, bias=self.bias)

        self.out_proj = nn.Linear(self.embed_dim, self.embed_dim, bias=self.bias)

        # Dropout
        self.attn_dropout = nn.Dropout(self.dropout)
        self.out_dropout = nn.Dropout(self.dropout)

        # Bias KV
        if self.add_bias_kv:
            self.bias_k = nn.Parameter(torch.zeros(1, 1, self.embed_dim))
            self.bias_v = nn.Parameter(torch.zeros(1, 1, self.embed_dim))
        else:
            self.bias_k = None
            self.bias_v = None

        # Zero attention
        if self.add_zero_attn:
            self.zero_attn = nn.Parameter(torch.zeros(1, 1, self.embed_dim))
        else:
            self.zero_attn = None

        self._reset_parameters()

        # Flash Attention (PyTorch 2.0+)
        self._use_flash_attention = (
            self.use_flash_attention and
            hasattr(F, 'scaled_dot_product_attention')
        )

    def _reset_parameters(self):
        """Initialise les paramètres"""
        nn.init.xavier_uniform_(self.q_proj.weight)
        nn.init.xavier_uniform_(self.k_proj.weight)
        nn.init.xavier_uniform_(self.v_proj.weight)
        nn.init.xavier_uniform_(self.out_proj.weight)

        if self.bias:
            nn.init.constant_(self.q_proj.bias, 0.)
            nn.init.constant_(self.k_proj.bias, 0.)
            nn.init.constant_(self.v_proj.bias, 0.)
            nn.init.constant_(self.out_proj.bias, 0.)

        if self.add_bias_kv:
            nn.init.xavier_normal_(self.bias_k)
            nn.init.xavier_normal_(self.bias_v)

        if self.add_zero_attn:
            nn.init.xavier_normal_(self.zero_attn)

    def _apply_flash_attention(
        self,
        q: torch.Tensor,
        k: torch.Tensor,
        v: torch.Tensor,
        attn_mask: Optional[torch.Tensor] = None,
        key_padding_mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Applique Flash Attention (PyTorch 2.0+)

        Returns:
            Tuple[torch.Tensor, torch.Tensor]: (Sortie, Poids d'attention)
        """
        # Flash Attention ne supporte pas le retour des poids
        # Nous retournons des poids vides pour compatibilité

        if attn_mask is not None and attn_mask.dtype == torch.bool:
            attn_mask = attn_mask.to(torch.float)
            attn_mask = attn_mask.masked_fill(attn_mask == 0, float('-inf'))
            attn_mask = attn_mask.masked_fill(attn_mask == 1, 0.0)

        if key_padding_mask is not None:
            # Convertir pour Flash Attention
            if key_padding_mask.dtype == torch.bool:
                key_padding_mask = key_padding_mask.to(torch.float)
                key_padding_mask = key_padding_mask.masked_fill(
                    key_padding_mask == 0, float('-inf')
                )
                key_padding_mask = key_padding_mask.masked_fill(
                    key_padding_mask == 1, 0.0
                )
                key_padding_mask = key_padding_mask.unsqueeze(1)

        output = F.scaled_dot_product_attention(
            q, k, v,
            attn_mask=attn_mask,
            dropout_p=self.dropout if self.training else 0.0,
            is_causal=False,
            scale=self.scaling,
        )

        # Poids d'attention non disponibles en Flash Attention
        attn_weights = torch.zeros(
            q.size(0), self.num_heads, q.size(2), k.size(2),
            device=q.device, dtype=q.dtype
        )

        return output, attn_weights

    def forward(
        self,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        key_padding_mask: Optional[torch.Tensor] = None,
        attn_mask: Optional[torch.Tensor] = None,
        return_attention: bool = False
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Forward pass du Multi-Head Attention.

        Args:
            query: Queries [batch_size, seq_len_q, embed_dim]
            key: Keys [batch_size, seq_len_k, embed_dim]
            value: Values [batch_size, seq_len_v, embed_dim]
            key_padding_mask: Masque de padding pour les clés
            attn_mask: Masque d'attention
            return_attention: Retourner les poids d'attention

        Returns:
            torch.Tensor: Sortie [batch_size, seq_len_q, embed_dim]
            Tuple: (Sortie, Poids d'attention)
        """
        if not self.batch_first:
            query = query.transpose(0, 1)
            key = key.transpose(0, 1)
            value = value.transpose(0, 1)

        batch_size, seq_len_q, _ = query.size()
        _, seq_len_k, _ = key.size()
        _, seq_len_v, _ = value.size()

        # Projections
        q = self.q_proj(query)
        k = self.k_proj(key)
        v = self.v_proj(value)

        # Ajout des biais KV
        if self.add_bias_kv:
            k = torch.cat([k, self.bias_k.repeat(batch_size, 1, 1)], dim=1)
            v = torch.cat([v, self.bias_v.repeat(batch_size, 1, 1)], dim=1)
            if key_padding_mask is not None:
                key_padding_mask = torch.cat([
                    key_padding_mask,
                    torch.zeros(batch_size, 1, dtype=key_padding_mask.dtype, device=key_padding_mask.device)
                ], dim=1)

        # Zero attention
        if self.add_zero_attn:
            k = torch.cat([k, self.zero_attn.repeat(batch_size, 1, 1)], dim=1)
            v = torch.cat([v, self.zero_attn.repeat(batch_size, 1, 1)], dim=1)
            if key_padding_mask is not None:
                key_padding_mask = torch.cat([
                    key_padding_mask,
                    torch.zeros(batch_size, 1, dtype=key_padding_mask.dtype, device=key_padding_mask.device)
                ], dim=1)

        # Reshape pour multi-head
        q = q.view(batch_size, seq_len_q, self.num_heads, self.head_dim).transpose(1, 2)
        k = k.view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        v = v.view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)

        # Flash Attention
        if self._use_flash_attention:
            output, attn_weights = self._apply_flash_attention(
                q, k, v, attn_mask, key_padding_mask
            )
        else:
            # Standard attention
            attn_weights = torch.matmul(q, k.transpose(-2, -1)) * self.scaling

            # Masques
            if attn_mask is not None:
                attn_weights = attn_weights + attn_mask

            if key_padding_mask is not None:
                attn_weights = attn_weights.masked_fill(
                    key_padding_mask.unsqueeze(1).unsqueeze(2),
                    float('-inf')
                )

            attn_weights = F.softmax(attn_weights, dim=-1)
            attn_weights = self.attn_dropout(attn_weights)

            output = torch.matmul(attn_weights, v)

        # Reshape et projection
        output = output.transpose(1, 2).contiguous().view(
            batch_size, seq_len_q, self.embed_dim
        )
        output = self.out_proj(output)
        output = self.out_dropout(output)

        if not self.batch_first:
            output = output.transpose(0, 1)

        if return_attention:
            return output, attn_weights

        return output

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres du module"""
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques du module"""
        total_params = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)

        return {
            'total_parameters': total_params,
            'trainable_parameters': trainable_params,
            'embed_dim': self.embed_dim,
            'num_heads': self.num_heads,
            'head_dim': self.head_dim,
            'use_flash_attention': self._use_flash_attention,
        }


class MultiHeadAttentionBlock(nn.Module):
    """
    Bloc Multi-Head Attention avec Feed-Forward et Layer Norm.

    Architecture:
    - Layer Norm
    - Multi-Head Attention
    - Residual connection
    - Layer Norm
    - Feed-Forward
    - Residual connection
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        ff_dim: Optional[int] = None,
        activation: str = 'gelu',
        **kwargs
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.ff_dim = ff_dim or embed_dim * 4

        self.norm1 = nn.LayerNorm(embed_dim)
        self.norm2 = nn.LayerNorm(embed_dim)

        self.attention = MultiHeadAttention(
            MultiHeadAttentionConfig(
                embed_dim=embed_dim,
                num_heads=num_heads,
                dropout=dropout,
                **kwargs
            )
        )

        self.ffn = nn.Sequential(
            nn.Linear(embed_dim, self.ff_dim),
            nn.GELU() if activation == 'gelu' else nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(self.ff_dim, embed_dim),
            nn.Dropout(dropout)
        )

        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        x: torch.Tensor,
        key_padding_mask: Optional[torch.Tensor] = None,
        attn_mask: Optional[torch.Tensor] = None,
        return_attention: bool = False
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Forward pass du bloc Multi-Head Attention.

        Args:
            x: Tensor d'entrée
            key_padding_mask: Masque de padding
            attn_mask: Masque d'attention
            return_attention: Retourner les poids d'attention

        Returns:
            torch.Tensor: Sortie
            Tuple: (Sortie, Poids d'attention)
        """
        # Multi-Head Attention avec résidu
        attn_output, attn_weights = self.attention(
            self.norm1(x),
            self.norm1(x),
            self.norm1(x),
            key_padding_mask,
            attn_mask,
            return_attention=True
        )
        x = x + self.dropout(attn_output)

        # Feed-Forward avec résidu
        ffn_output = self.ffn(self.norm2(x))
        output = x + self.dropout(ffn_output)

        if return_attention:
            return output, attn_weights

        return output


class CausalMultiHeadAttention(nn.Module):
    """
    Causal Multi-Head Attention (pour auto-régression).

    Ajoute un masque causal pour que chaque position ne puisse
    attendre que les positions précédentes.
    """

    def __init__(self, config: Optional[MultiHeadAttentionConfig] = None):
        super().__init__()

        if config is None:
            config = MultiHeadAttentionConfig()

        self.config = config
        self.attention = MultiHeadAttention(config)
        self._causal_mask = None

    def _get_causal_mask(self, seq_len: int, device: torch.device) -> torch.Tensor:
        """Crée un masque causal"""
        if self._causal_mask is None or self._causal_mask.size(0) < seq_len:
            mask = torch.triu(
                torch.ones(seq_len, seq_len, device=device) * float('-inf'),
                diagonal=1
            )
            self._causal_mask = mask
        return self._causal_mask[:seq_len, :seq_len]

    def forward(
        self,
        query: torch.Tensor,
        key: Optional[torch.Tensor] = None,
        value: Optional[torch.Tensor] = None,
        key_padding_mask: Optional[torch.Tensor] = None,
        return_attention: bool = False
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Forward pass du Causal Multi-Head Attention.

        Args:
            query: Queries
            key: Keys (optionnel, self-attention si None)
            value: Values (optionnel, self-attention si None)
            key_padding_mask: Masque de padding
            return_attention: Retourner les poids d'attention

        Returns:
            torch.Tensor: Sortie
            Tuple: (Sortie, Poids d'attention)
        """
        if key is None:
            key = query
        if value is None:
            value = query

        seq_len = query.size(1) if self.config.batch_first else query.size(0)
        causal_mask = self._get_causal_mask(seq_len, query.device)

        return self.attention(
            query,
            key,
            value,
            key_padding_mask=key_padding_mask,
            attn_mask=causal_mask,
            return_attention=return_attention
        )


def create_multi_head_attention(
    embed_dim: int = 256,
    num_heads: int = 8,
    dropout: float = 0.1,
    **kwargs
) -> MultiHeadAttention:
    """
    Factory pour créer un module Multi-Head Attention.

    Args:
        embed_dim: Dimension d'embedding
        num_heads: Nombre de têtes
        dropout: Taux de dropout
        **kwargs: Arguments supplémentaires

    Returns:
        MultiHeadAttention: Instance de Multi-Head Attention
    """
    config = MultiHeadAttentionConfig(
        embed_dim=embed_dim,
        num_heads=num_heads,
        dropout=dropout,
        **kwargs
    )
    return MultiHeadAttention(config)


def create_causal_multi_head_attention(
    embed_dim: int = 256,
    num_heads: int = 8,
    dropout: float = 0.1,
    **kwargs
) -> CausalMultiHeadAttention:
    """
    Factory pour créer un module Causal Multi-Head Attention.

    Args:
        embed_dim: Dimension d'embedding
        num_heads: Nombre de têtes
        dropout: Taux de dropout
        **kwargs: Arguments supplémentaires

    Returns:
        CausalMultiHeadAttention: Instance de Causal Multi-Head Attention
    """
    config = MultiHeadAttentionConfig(
        embed_dim=embed_dim,
        num_heads=num_heads,
        dropout=dropout,
        **kwargs
    )
    return CausalMultiHeadAttention(config)


__all__ = [
    'MultiHeadAttention',
    'MultiHeadAttentionConfig',
    'MultiHeadAttentionBlock',
    'CausalMultiHeadAttention',
    'create_multi_head_attention',
    'create_causal_multi_head_attention',
]
