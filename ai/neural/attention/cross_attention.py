
# ai/neural/attention/cross_attention.py
"""
NEXUS AI TRADING SYSTEM - Cross-Attention Module
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
class CrossAttentionConfig:
    """Configuration pour Cross-Attention"""
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
        }


class CrossAttention(nn.Module):
    """
    Cross-Attention module for neural networks.

    Cross-attention allows queries from one sequence to attend to
    keys and values from another sequence. This is useful for:
    - Multimodal learning
    - Cross-modal attention
    - Information fusion
    - Feature alignment

    Features:
    - Multi-head attention
    - Configurable dimensions
    - Dropout
    - Bias options
    - Batch-first operations

    Example:
        ```python
        config = CrossAttentionConfig(
            embed_dim=256,
            num_heads=8,
            dropout=0.1
        )
        cross_attn = CrossAttention(config)

        # Query from sequence A, Key/Value from sequence B
        output = cross_attn(query, key, value)
        ```
    """

    def __init__(self, config: Optional[CrossAttentionConfig] = None):
        super().__init__()

        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or CrossAttentionConfig()
        self.embed_dim = self.config.embed_dim
        self.num_heads = self.config.num_heads
        self.dropout = self.config.dropout
        self.bias = self.config.bias
        self.add_bias_kv = self.config.add_bias_kv
        self.add_zero_attn = self.config.add_zero_attn
        self.batch_first = self.config.batch_first

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

        self._reset_parameters()

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
        Forward pass du Cross-Attention.

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

        # Reshape pour multi-head
        q = q.view(batch_size, seq_len_q, self.num_heads, self.head_dim).transpose(1, 2)
        k = k.view(batch_size, seq_len_k, self.num_heads, self.head_dim).transpose(1, 2)
        v = v.view(batch_size, seq_len_v, self.num_heads, self.head_dim).transpose(1, 2)

        # Attention
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

        # Sortie
        output = torch.matmul(attn_weights, v)
        output = output.transpose(1, 2).contiguous().view(batch_size, seq_len_q, self.embed_dim)
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
        }


class CrossAttentionBlock(nn.Module):
    """
    Bloc Cross-Attention avec Feed-Forward et Layer Norm.

    Architecture:
    - Layer Norm
    - Cross-Attention
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
        activation: str = 'gelu'
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.ff_dim = ff_dim or embed_dim * 4

        self.norm1 = nn.LayerNorm(embed_dim)
        self.norm2 = nn.LayerNorm(embed_dim)

        self.cross_attn = CrossAttention(
            CrossAttentionConfig(
                embed_dim=embed_dim,
                num_heads=num_heads,
                dropout=dropout
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
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        key_padding_mask: Optional[torch.Tensor] = None,
        attn_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Forward pass du bloc Cross-Attention.

        Args:
            query: Queries
            key: Keys
            value: Values
            key_padding_mask: Masque de padding
            attn_mask: Masque d'attention

        Returns:
            torch.Tensor: Sortie
        """
        # Cross-Attention avec résidu
        attn_output = self.cross_attn(
            self.norm1(query),
            key,
            value,
            key_padding_mask,
            attn_mask
        )
        query = query + self.dropout(attn_output)

        # Feed-Forward avec résidu
        ffn_output = self.ffn(self.norm2(query))
        output = query + self.dropout(ffn_output)

        return output


class MultiCrossAttention(nn.Module):
    """
    Multi-Cross-Attention pour plusieurs paires de séquences.

    Permet d'appliquer Cross-Attention entre plusieurs paires
    de séquences en parallèle.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        num_attentions: int,
        dropout: float = 0.1
    ):
        super().__init__()

        self.num_attentions = num_attentions

        self.attentions = nn.ModuleList([
            CrossAttention(
                CrossAttentionConfig(
                    embed_dim=embed_dim,
                    num_heads=num_heads,
                    dropout=dropout
                )
            )
            for _ in range(num_attentions)
        ])

        self.combine = nn.Linear(num_attentions * embed_dim, embed_dim)

    def forward(
        self,
        queries: List[torch.Tensor],
        keys: List[torch.Tensor],
        values: List[torch.Tensor],
        key_padding_masks: Optional[List[torch.Tensor]] = None,
        attn_masks: Optional[List[torch.Tensor]] = None
    ) -> torch.Tensor:
        """
        Forward pass du Multi-Cross-Attention.

        Args:
            queries: Liste des queries
            keys: Liste des keys
            values: Liste des values
            key_padding_masks: Liste des masques de padding
            attn_masks: Liste des masques d'attention

        Returns:
            torch.Tensor: Sortie combinée
        """
        if len(queries) != self.num_attentions:
            raise ValueError(f"Nombre de queries ({len(queries)}) différent de num_attentions ({self.num_attentions})")

        outputs = []
        for i, attn in enumerate(self.attentions):
            q = queries[i] if i < len(queries) else queries[0]
            k = keys[i] if i < len(keys) else keys[0]
            v = values[i] if i < len(values) else values[0]

            kpm = None
            am = None
            if key_padding_masks is not None and i < len(key_padding_masks):
                kpm = key_padding_masks[i]
            if attn_masks is not None and i < len(attn_masks):
                am = attn_masks[i]

            output = attn(q, k, v, kpm, am)
            outputs.append(output)

        # Concaténation et projection
        combined = torch.cat(outputs, dim=-1)
        output = self.combine(combined)

        return output


def create_cross_attention(
    embed_dim: int = 256,
    num_heads: int = 8,
    dropout: float = 0.1,
    **kwargs
) -> CrossAttention:
    """
    Factory pour créer un module Cross-Attention.

    Args:
        embed_dim: Dimension d'embedding
        num_heads: Nombre de têtes
        dropout: Taux de dropout
        **kwargs: Arguments supplémentaires

    Returns:
        CrossAttention: Instance de Cross-Attention
    """
    config = CrossAttentionConfig(
        embed_dim=embed_dim,
        num_heads=num_heads,
        dropout=dropout,
        **kwargs
    )
    return CrossAttention(config)


def create_cross_attention_block(
    embed_dim: int = 256,
    num_heads: int = 8,
    dropout: float = 0.1,
    ff_dim: Optional[int] = None,
    **kwargs
) -> CrossAttentionBlock:
    """
    Factory pour créer un bloc Cross-Attention.

    Args:
        embed_dim: Dimension d'embedding
        num_heads: Nombre de têtes
        dropout: Taux de dropout
        ff_dim: Dimension du Feed-Forward
        **kwargs: Arguments supplémentaires

    Returns:
        CrossAttentionBlock: Instance du bloc
    """
    return CrossAttentionBlock(
        embed_dim=embed_dim,
        num_heads=num_heads,
        dropout=dropout,
        ff_dim=ff_dim,
        **kwargs
    )


__all__ = [
    'CrossAttention',
    'CrossAttentionConfig',
    'CrossAttentionBlock',
    'MultiCrossAttention',
    'create_cross_attention',
    'create_cross_attention_block',
]
