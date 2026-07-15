
# ai/neural/optimizers/sgd.py
"""
NEXUS AI TRADING SYSTEM - SGD Optimizer
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
class SGDConfig:
    """Configuration pour SGD Optimizer"""
    lr: float = 1e-2
    momentum: float = 0.0
    weight_decay: float = 0.0
    dampening: float = 0.0
    nesterov: bool = False
    maximize: bool = False
    foreach: Optional[bool] = None
    differentiable: bool = False

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if self.lr <= 0:
            raise ValueError("lr doit être > 0")
        if self.momentum < 0:
            raise ValueError("momentum doit être >= 0")
        if self.weight_decay < 0:
            raise ValueError("weight_decay doit être >= 0")
        if self.dampening < 0:
            raise ValueError("dampening doit être >= 0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'lr': self.lr,
            'momentum': self.momentum,
            'weight_decay': self.weight_decay,
            'dampening': self.dampening,
            'nesterov': self.nesterov,
            'maximize': self.maximize,
            'foreach': self.foreach,
            'differentiable': self.differentiable,
        }


class SGD(Optimizer):
    """
    Implémentation de SGD (Stochastic Gradient Descent).

    SGD avec options de momentum, Nesterov, weight decay,
    et dampening.

    Features:
    - Momentum standard et Nesterov
    - Weight decay
    - Dampening
    - Maximisation optionnelle
    - Différentiable
    - Support foreach

    Reference:
        Sutskever et al., "On the importance of initialization and momentum in deep learning", 2013
    """

    def __init__(self, config: Optional[SGDConfig] = None, **kwargs):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        if config is None:
            config = SGDConfig(**kwargs)
        elif isinstance(config, dict):
            config = SGDConfig(**config)

        self.config = config

        defaults = {
            'lr': config.lr,
            'momentum': config.momentum,
            'weight_decay': config.weight_decay,
            'dampening': config.dampening,
            'nesterov': config.nesterov,
            'maximize': config.maximize,
            'foreach': config.foreach,
            'differentiable': config.differentiable,
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

                # Weight decay
                if group['weight_decay'] != 0:
                    grad = grad.add(p, alpha=group['weight_decay'])

                # Momentum
                if group['momentum'] != 0:
                    if len(state) == 0:
                        state['momentum_buffer'] = torch.zeros_like(p, memory_format=torch.preserve_format)

                    momentum_buffer = state['momentum_buffer']
                    momentum_buffer.mul_(group['momentum']).add_(grad, alpha=1 - group['dampening'])

                    if group['nesterov']:
                        grad = grad.add(momentum_buffer, alpha=group['momentum'])
                    else:
                        grad = momentum_buffer

                # Mise à jour des paramètres
                p.add_(grad, alpha=-group['lr'])

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
            'momentum': self.config.momentum,
            'weight_decay': self.config.weight_decay,
            'dampening': self.config.dampening,
            'nesterov': self.config.nesterov,
            'maximize': self.config.maximize,
        }


class SGDWithWarmup(Optimizer):
    """
    SGD avec warmup pour une convergence plus rapide.

    Augmente progressivement le taux d'apprentissage pendant
    les premières époques.
    """

    def __init__(
        self,
        params,
        lr: float = 1e-2,
        momentum: float = 0.0,
        weight_decay: float = 0.0,
        warmup_steps: int = 100,
        warmup_start_lr: float = 1e-4,
    ):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        defaults = {
            'lr': lr,
            'momentum': momentum,
            'weight_decay': weight_decay,
            'warmup_steps': warmup_steps,
            'warmup_start_lr': warmup_start_lr,
            'step': 0,
        }

        super().__init__(params, defaults)

    @torch.no_grad()
    def step(self, closure=None):
        """
        Effectue une étape d'optimisation avec warmup.

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
            # Calcul du taux d'apprentissage actuel
            step = group['step']
            warmup_steps = group['warmup_steps']
            warmup_start_lr = group['warmup_start_lr']
            lr = group['lr']

            if step < warmup_steps:
                current_lr = warmup_start_lr + (lr - warmup_start_lr) * (step / warmup_steps)
            else:
                current_lr = lr

            for p in group['params']:
                if p.grad is None:
                    continue

                grad = p.grad

                state = self.state[p]

                # Weight decay
                if group['weight_decay'] != 0:
                    grad = grad.add(p, alpha=group['weight_decay'])

                # Momentum
                if group['momentum'] != 0:
                    if len(state) == 0:
                        state['momentum_buffer'] = torch.zeros_like(p, memory_format=torch.preserve_format)

                    momentum_buffer = state['momentum_buffer']
                    momentum_buffer.mul_(group['momentum']).add_(grad)
                    grad = momentum_buffer

                # Mise à jour des paramètres
                p.add_(grad, alpha=-current_lr)

            group['step'] += 1

        return loss


def create_sgd(
    lr: float = 1e-2,
    momentum: float = 0.0,
    weight_decay: float = 0.0,
    dampening: float = 0.0,
    nesterov: bool = False,
    **kwargs
) -> SGD:
    """
    Factory pour créer un optimiseur SGD.

    Args:
        lr: Taux d'apprentissage
        momentum: Facteur de momentum
        weight_decay: Coefficient de weight decay
        dampening: Facteur de dampening
        nesterov: Utiliser Nesterov momentum
        **kwargs: Arguments supplémentaires

    Returns:
        SGD: Optimiseur SGD

    Example:
        ```python
        # SGD standard
        optimizer = create_sgd(lr=1e-2)

        # SGD avec momentum
        optimizer = create_sgd(
            lr=1e-2,
            momentum=0.9,
            weight_decay=1e-5
        )

        # SGD avec Nesterov
        optimizer = create_sgd(
            lr=1e-2,
            momentum=0.9,
            nesterov=True
        )

        # Utilisation
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        ```
    """
    config = SGDConfig(
        lr=lr,
        momentum=momentum,
        weight_decay=weight_decay,
        dampening=dampening,
        nesterov=nesterov,
        **kwargs
    )
    return SGD(config)


__all__ = [
    'SGD',
    'SGDConfig',
    'SGDWithWarmup',
    'create_sgd',
]
