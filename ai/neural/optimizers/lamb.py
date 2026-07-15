
# ai/neural/optimizers/lamb.py
"""
NEXUS AI TRADING SYSTEM - LAMB Optimizer
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import math
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    from torch.optim import Optimizer
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class LAMBConfig:
    """Configuration pour LAMB Optimizer"""
    lr: float = 1e-3
    betas: Tuple[float, float] = (0.9, 0.999)
    eps: float = 1e-6
    weight_decay: float = 0.01
    amsgrad: bool = False
    maximize: bool = False
    trust_coefficient: float = 1.0
    clamp_value: Optional[float] = None

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if self.lr <= 0:
            raise ValueError("lr doit être > 0")
        if self.eps < 0:
            raise ValueError("eps doit être >= 0")
        if self.weight_decay < 0:
            raise ValueError("weight_decay doit être >= 0")
        if self.trust_coefficient <= 0:
            raise ValueError("trust_coefficient doit être > 0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'lr': self.lr,
            'betas': self.betas,
            'eps': self.eps,
            'weight_decay': self.weight_decay,
            'amsgrad': self.amsgrad,
            'maximize': self.maximize,
            'trust_coefficient': self.trust_coefficient,
            'clamp_value': self.clamp_value,
        }


class LAMB(Optimizer):
    """
    Implémentation de LAMB (Layer-wise Adaptive Moments optimizer for Batch training).

    LAMB combine le momentum et le weight decay avec une adaptation par couche
    pour une meilleure convergence sur de grands batches.

    Features:
    - Adaptation par couche
    - Ratio de confiance pour les mises à jour
    - Weight decay découplé
    - AMSGrad optionnel
    - Clamping des ratios de confiance
    - Maximisation optionnelle

    Reference:
        You et al., "Large Batch Optimization for Deep Learning: Training BERT in 76 minutes", 2020
    """

    def __init__(self, config: Optional[LAMBConfig] = None, **kwargs):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        if config is None:
            config = LAMBConfig(**kwargs)
        elif isinstance(config, dict):
            config = LAMBConfig(**config)

        self.config = config

        defaults = {
            'lr': config.lr,
            'betas': config.betas,
            'eps': config.eps,
            'weight_decay': config.weight_decay,
            'amsgrad': config.amsgrad,
            'maximize': config.maximize,
            'trust_coefficient': config.trust_coefficient,
            'clamp_value': config.clamp_value,
        }

        super().__init__([], defaults)

    @torch.no_grad()
    def step(self, closure=None):
        """
        Effectue une étape d'optimisation.

        Args:
            closure: Fonction de closure (optionnel)

        Returns:
            Optional[float]: Perte si closure est fournie
        """
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()

        for group in self.param_groups:
            for p in group['params']:
                if p.grad is None:
                    continue

                grad = p.grad if not group['maximize'] else -p.grad

                state = self.state[p]

                if len(state) == 0:
                    state['step'] = 0
                    state['exp_avg'] = torch.zeros_like(p, memory_format=torch.preserve_format)
                    state['exp_avg_sq'] = torch.zeros_like(p, memory_format=torch.preserve_format)

                exp_avg = state['exp_avg']
                exp_avg_sq = state['exp_avg_sq']

                beta1, beta2 = group['betas']

                # Mise à jour des moments
                exp_avg.mul_(beta1).add_(grad, alpha=1 - beta1)
                exp_avg_sq.mul_(beta2).addcmul_(grad, grad, value=1 - beta2)

                # Incrément du pas
                state['step'] += 1
                step = state['step']

                # Calcul des paramètres de mise à jour
                bias_correction1 = 1 - beta1 ** step
                bias_correction2 = 1 - beta2 ** step

                # Mise à jour adaptative
                denom = (exp_avg_sq.sqrt() / math.sqrt(bias_correction2)).add_(group['eps'])

                # Ratio de confiance
                if group['weight_decay'] != 0:
                    update = exp_avg / denom + group['weight_decay'] * p
                else:
                    update = exp_avg / denom

                # Adaptation par couche (LAMB)
                norm_update = torch.norm(update)
                norm_param = torch.norm(p)

                if norm_param > 0 and norm_update > 0:
                    trust_ratio = norm_param / norm_update * group['trust_coefficient']
                    if group['clamp_value'] is not None:
                        trust_ratio = torch.clamp(trust_ratio, 0, group['clamp_value'])
                else:
                    trust_ratio = 1.0

                # Mise à jour des paramètres
                p.add_(update, alpha=-group['lr'] * trust_ratio / math.sqrt(bias_correction1))

        return loss

    def get_config(self) -> Dict[str, Any]:
        """Retourne la configuration de l'optimiseur"""
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques de l'optimiseur"""
        total_params = sum(p.numel() for group in self.param_groups for p in group['params'])
        trainable_params = sum(p.numel() for group in self.param_groups for p in group['params'] if p.requires_grad)

        return {
            'total_parameters': total_params,
            'trainable_parameters': trainable_params,
            'learning_rate': self.config.lr,
            'betas': self.config.betas,
            'weight_decay': self.config.weight_decay,
            'trust_coefficient': self.config.trust_coefficient,
            'clamp_value': self.config.clamp_value,
            'amsgrad': self.config.amsgrad,
            'maximize': self.config.maximize,
        }


def create_lamb(
    lr: float = 1e-3,
    betas: Tuple[float, float] = (0.9, 0.999),
    eps: float = 1e-6,
    weight_decay: float = 0.01,
    trust_coefficient: float = 1.0,
    **kwargs
) -> LAMB:
    """
    Factory pour créer un optimiseur LAMB.

    Args:
        lr: Taux d'apprentissage
        betas: Paramètres de décroissance exponentielle
        eps: Epsilon pour la stabilité
        weight_decay: Coefficient de weight decay
        trust_coefficient: Coefficient de confiance pour l'adaptation par couche
        **kwargs: Arguments supplémentaires

    Returns:
        LAMB: Optimiseur LAMB

    Example:
        ```python
        optimizer = create_lamb(
            lr=1e-3,
            weight_decay=0.01,
            trust_coefficient=1.0,
            clamp_value=10.0
        )

        # Utilisation
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        ```
    """
    config = LAMBConfig(
        lr=lr,
        betas=betas,
        eps=eps,
        weight_decay=weight_decay,
        trust_coefficient=trust_coefficient,
        **kwargs
    )
    return LAMB(config)


__all__ = [
    'LAMB',
    'LAMBConfig',
    'create_lamb',
]
