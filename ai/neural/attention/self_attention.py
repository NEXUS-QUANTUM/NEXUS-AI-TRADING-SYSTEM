```python
# ai/neural/attention/self_attention.py
"""
NEXUS AI TRADING SYSTEM - Self-Attention Module
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
class SelfAttentionConfig:
    """Configuration pour Self-Attention"""
    embed_dim: int = 256
    num_heads: int = 8
    dropout: float = 0.1
    bias: bool = True
    batch_first: bool = True
    use_scale: bool = True
    use_flash_attention: bool = False
    use_relative_position: bool = False
    max_position: int = 512

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
            'batch_first': self.batch_first,
            'use_scale': self.use_scale,
            'use_flash_attention': self.use_flash_attention,
            'use_relative_position': self.use_relative_position,
            'max_position': self.max_position,
        }


class _RelativePositionBias(nn.Module):
    """Biais de position relative pour Self-Attention"""

    def __init__(self, num_heads: int, max_position: int = 512):
        super().__init__()
        self.num_heads = num_heads
        self.max_position = max_position
        self.relative_bias = nn.Parameter(torch.zeros(num_heads, 2 * max_position - 1))

    def forward(self, seq_len: int) -> torch.Tensor:
        device = self.relative_bias.device
        positions = torch.arange(seq_len, device=device)
        relative_positions = positions.unsqueeze(0) - positions.unsqueeze(1)
        relative_positions = relative_positions + self.max_position - 1
        relative_positions = torch.clamp(relative_positions, 0, 2 * self.max_position - 2)

        bias = self.relative_bias[:, relative_positions]
        return bias


class SelfAttention(nn.Module):
    """
    Self-Attention module.

    Self-Attention allows each position in a sequence to attend to all
    other positions, capturing global dependencies.

    Features:
    - Multi-head self-attention
    - Relative position bias
    - Flash Attention support
    - Masking (padding mask, causal mask)
    - Dropout
    - Batch-first operations

    Example:
        ```python
        config = SelfAttentionConfig(
            embed_dim=256,
            num_heads=8,
            dropout=0.1,
            use_relative_position=True
        )
        self_attn = SelfAttention(config)

        # Self-attention
        output = self_attn(x)

        # With padding mask
        output = self_attn(x, key_padding_mask=mask)
        ```
    """

    def __init__(self, config: Optional[SelfAttentionConfig] = None):
        super().__init__()

        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or SelfAttentionConfig()
        self.embed_dim = self.config.embed_dim
        self.num_heads = self.config.num_heads
        self.dropout = self.config.dropout
        self.bias = self.config.bias
        self.batch_first = self.config.batch_first
        self.use_scale = self.config.use_scale
        self.use_flash_attention = self.config.use_flash_attention

        self.head_dim = self.embed_dim // self.num_heads
        self.scaling = self.head_dim ** -0.5 if self.config.use_scale else 1.0

        # Projections
        self.q_proj = nn.Linear(self.embed_dim, self.embed_dim, bias=self.bias)
        self.k_proj = nn.Linear(self.embed_dim, self.embed_dim, bias=self.bias)
        self.v_proj = nn.Linear(self.embed_dim, self.embed_dim, bias=self.bias)

        self.out_proj = nn.Linear(self.embed_dim, self.embed_dim, bias=self.bias)

        # Dropout
        self.attn_dropout = nn.Dropout(self.dropout)
        self.out_dropout = nn.Dropout(self.dropout)

        # Relative position bias
        self.use_relative_position = self.config.use_relative_position
        if self.use_relative_position:
            self.relative_bias = _RelativePositionBias(
                self.num_heads,
                self.config.max_position
            )

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
        # Convert masks for Flash Attention
        if attn_mask is not None and attn_mask.dtype == torch.bool:
            attn_mask = attn_mask.to(torch.float)
            attn_mask = attn_mask.masked_fill(attn_mask == 0, float('-inf'))
            attn_mask = attn_mask.masked_fill(attn_mask == 1, 0.0)

        if key_padding_mask is not None:
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
        x: torch.Tensor,
        key_padding_mask: Optional[torch.Tensor] = None,
        attn_mask: Optional[torch.Tensor] = None,
        return_attention: bool = False
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Forward pass du Self-Attention.

        Args:
            x: Tensor d'entrée [batch_size, seq_len, embed_dim]
            key_padding_mask: Masque de padding pour les clés
            attn_mask: Masque d'attention
            return_attention: Retourner les poids d'attention

        Returns:
            torch.Tensor: Sortie [batch_size, seq_len, embed_dim]
            Tuple: (Sortie, Poids d'attention)
        """
        if not self.batch_first:
            x = x.transpose(0, 1)

        batch_size, seq_len, _ = x.size()

        # Projections
        q = self.q_proj(x)
        k = self.k_proj(x)
        v = self.v_proj(x)

        # Reshape pour multi-head
        q = q.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        k = k.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        v = v.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)

        # Flash Attention
        if self._use_flash_attention:
            output, attn_weights = self._apply_flash_attention(
                q, k, v, attn_mask, key_padding_mask
            )
        else:
            # Standard attention
            attn_weights = torch.matmul(q, k.transpose(-2, -1)) * self.scaling

            # Relative position bias
            if self.use_relative_position:
                rel_bias = self.relative_bias(seq_len)
                attn_weights = attn_weights + rel_bias

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
            batch_size, seq_len, self.embed_dim
        )
        output = self.out_proj(output)
        output = self.out_dropout(output)

        if not self.batch_first:
            output = output.transpose(0, 1)

        if return_attention:
            return output, attn_weights

        return output


class SelfAttentionBlock(nn.Module):
    """
    Bloc Self-Attention avec Feed-Forward et Layer Norm.

    Architecture:
    - Layer Norm
    - Self-Attention
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

        self.attention = SelfAttention(
            SelfAttentionConfig(
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
        Forward pass du bloc Self-Attention.

        Args:
            x: Tensor d'entrée
            key_padding_mask: Masque de padding
            attn_mask: Masque d'attention
            return_attention: Retourner les poids d'attention

        Returns:
            torch.Tensor: Sortie
            Tuple: (Sortie, Poids d'attention)
        """
        # Self-Attention avec résidu
        attn_output, attn_weights = self.attention(
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


class CausalSelfAttention(nn.Module):
    """
    Causal Self-Attention (pour auto-régression).

    Ajoute un masque causal pour que chaque position ne puisse
    attendre que les positions précédentes.
    """

    def __init__(self, config: Optional[SelfAttentionConfig] = None):
        super().__init__()

        if config is None:
            config = SelfAttentionConfig()

        self.config = config
        self.attention = SelfAttention(config)
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
        x: torch.Tensor,
        key_padding_mask: Optional[torch.Tensor] = None,
        return_attention: bool = False
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Forward pass du Causal Self-Attention.

        Args:
            x: Tensor d'entrée
            key_padding_mask: Masque de padding
            return_attention: Retourner les poids d'attention

        Returns:
            torch.Tensor: Sortie
            Tuple: (Sortie, Poids d'attention)
        """
        seq_len = x.size(1) if self.config.batch_first else x.size(0)
        causal_mask = self._get_causal_mask(seq_len, x.device)

        return self.attention(
            x,
            key_padding_mask=key_padding_mask,
            attn_mask=causal_mask,
            return_attention=return_attention
        )


def create_self_attention(
    embed_dim: int = 256,
    num_heads: int = 8,
    dropout: float = 0.1,
    **kwargs
) -> SelfAttention:
    """
    Factory pour créer un module Self-Attention.

    Args:
        embed_dim: Dimension d'embedding
        num_heads: Nombre de têtes
        dropout: Taux de dropout
        **kwargs: Arguments supplémentaires

    Returns:
        SelfAttention: Instance de Self-Attention
    """
    config = SelfAttentionConfig(
        embed_dim=embed_dim,
        num_heads=num_heads,
        dropout=dropout,
        **kwargs
    )
    return SelfAttention(config)


def create_causal_self_attention(
    embed_dim: int = 256,
    num_heads: int = 8,
    dropout: float = 0.1,
    **kwargs
) -> CausalSelfAttention:
    """
    Factory pour créer un module Causal Self-Attention.

    Args:
        embed_dim: Dimension d'embedding
        num_heads: Nombre de têtes
        dropout: Taux de dropout
        **kwargs: Arguments supplémentaires

    Returns:
        CausalSelfAttention: Instance de Causal Self-Attention
    """
    config = SelfAttentionConfig(
        embed_dim=embed_dim,
        num_heads=num_heads,
        dropout=dropout,
        **kwargs
    )
    return CausalSelfAttention(config)


__all__ = [
    'SelfAttention',
    'SelfAttentionConfig',
    'SelfAttentionBlock',
    'CausalSelfAttention',
    'create_self_attention',
    'create_causal_self_attention',
]
```
