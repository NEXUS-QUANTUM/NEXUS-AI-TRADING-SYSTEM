
# ai/neural/optimizers/rmsprop.py
"""
NEXUS AI TRADING SYSTEM - RMSprop Optimizer
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
class RMSpropConfig:
    """Configuration pour RMSprop Optimizer"""
    lr: float = 1e-2
    alpha: float = 0.99
    eps: float = 1e-8
    weight_decay: float = 0.0
    momentum: float = 0.0
    centered: bool = False
    maximize: bool = False
    foreach: Optional[bool] = None
    differentiable: bool = False

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if self.lr <= 0:
            raise ValueError("lr doit être > 0")
        if self.alpha <= 0:
            raise ValueError("alpha doit être > 0")
        if self.eps < 0:
            raise ValueError("eps doit être >= 0")
        if self.weight_decay < 0:
            raise ValueError("weight_decay doit être >= 0")
        if self.momentum < 0:
            raise ValueError("momentum doit être >= 0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'lr': self.lr,
            'alpha': self.alpha,
            'eps': self.eps,
            'weight_decay': self.weight_decay,
            'momentum': self.momentum,
            'centered': self.centered,
            'maximize': self.maximize,
            'foreach': self.foreach,
            'differentiable': self.differentiable,
        }


class RMSprop(Optimizer):
    """
    Implémentation de RMSprop (Root Mean Square Propagation).

    RMSprop est un optimiseur adaptatif qui normalise le gradient par
    la moyenne des carrés des gradients passés.

    Features:
    - Adaptation du taux d'apprentissage
    - Momentum optionnel
    - Centering optionnel
    - Weight decay
    - Maximisation optionnelle
    - Différentiable

    Reference:
        Tieleman & Hinton, "RMSprop: Divide the gradient by a running average of its recent magnitude", 2012
    """

    def __init__(self, config: Optional[RMSpropConfig] = None, **kwargs):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        if config is None:
            config = RMSpropConfig(**kwargs)
        elif isinstance(config, dict):
            config = RMSpropConfig(**config)

        self.config = config

        defaults = {
            'lr': config.lr,
            'alpha': config.alpha,
            'eps': config.eps,
            'weight_decay': config.weight_decay,
            'momentum': config.momentum,
            'centered': config.centered,
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

                if len(state) == 0:
                    state['step'] = 0
                    state['square_avg'] = torch.zeros_like(p, memory_format=torch.preserve_format)
                    if group['momentum'] > 0:
                        state['momentum_buffer'] = torch.zeros_like(p, memory_format=torch.preserve_format)
                    if group['centered']:
                        state['grad_avg'] = torch.zeros_like(p, memory_format=torch.preserve_format)

                square_avg = state['square_avg']
                alpha = group['alpha']
                eps = group['eps']
                weight_decay = group['weight_decay']
                momentum = group['momentum']

                # Mise à jour de la moyenne des carrés
                square_avg.mul_(alpha).addcmul_(grad, grad, value=1 - alpha)

                if group['centered']:
                    grad_avg = state['grad_avg']
                    grad_avg.mul_(alpha).add_(grad, alpha=1 - alpha)
                    avg = square_avg.addcmul(grad_avg, grad_avg, value=-1).sqrt_().add_(eps)
                else:
                    avg = square_avg.sqrt().add_(eps)

                # Weight decay
                if weight_decay != 0:
                    grad = grad.add(p, alpha=weight_decay)

                # Momentum
                if momentum > 0:
                    momentum_buffer = state['momentum_buffer']
                    momentum_buffer.mul_(momentum).addcdiv_(grad, avg)
                    p.add_(momentum_buffer, alpha=-group['lr'])
                else:
                    p.addcdiv_(grad, avg, alpha=-group['lr'])

                state['step'] += 1

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
            'alpha': self.config.alpha,
            'momentum': self.config.momentum,
            'weight_decay': self.config.weight_decay,
            'centered': self.config.centered,
            'maximize': self.config.maximize,
        }


class RMSpropTF(Optimizer):
    """
    RMSprop avec implémentation TensorFlow.

    Utilise la version de RMSprop de TensorFlow avec momentum
    et centered options.
    """

    def __init__(
        self,
        params,
        lr: float = 1e-2,
        alpha: float = 0.9,
        eps: float = 1e-8,
        weight_decay: float = 0.0,
        momentum: float = 0.0,
        centered: bool = False,
        maximize: bool = False,
    ):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        defaults = {
            'lr': lr,
            'alpha': alpha,
            'eps': eps,
            'weight_decay': weight_decay,
            'momentum': momentum,
            'centered': centered,
            'maximize': maximize,
        }

        super().__init__(params, defaults)

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
                    state['rms'] = torch.zeros_like(p, memory_format=torch.preserve_format)
                    if group['momentum'] > 0:
                        state['momentum'] = torch.zeros_like(p, memory_format=torch.preserve_format)
                    if group['centered']:
                        state['grad_mean'] = torch.zeros_like(p, memory_format=torch.preserve_format)

                rms = state['rms']
                alpha = group['alpha']
                eps = group['eps']
                weight_decay = group['weight_decay']
                momentum = group['momentum']

                # Mise à jour de RMS
                rms.mul_(alpha).addcmul_(grad, grad, value=1 - alpha)

                if group['centered']:
                    grad_mean = state['grad_mean']
                    grad_mean.mul_(alpha).add_(grad, alpha=1 - alpha)
                    rms_sub = rms - grad_mean.pow(2)
                    rms_sub = rms_sub.clamp_min(0)
                    denom = rms_sub.sqrt().add_(eps)
                else:
                    denom = rms.sqrt().add_(eps)

                # Weight decay
                if weight_decay != 0:
                    grad = grad.add(p, alpha=weight_decay)

                # Momentum
                if momentum > 0:
                    momentum_buffer = state['momentum']
                    momentum_buffer.mul_(momentum).addcdiv_(grad, denom)
                    p.add_(momentum_buffer, alpha=-group['lr'])
                else:
                    p.addcdiv_(grad, denom, alpha=-group['lr'])

                state['step'] += 1

        return loss


def create_rmsprop(
    lr: float = 1e-2,
    alpha: float = 0.99,
    eps: float = 1e-8,
    weight_decay: float = 0.0,
    momentum: float = 0.0,
    centered: bool = False,
    **kwargs
) -> RMSprop:
    """
    Factory pour créer un optimiseur RMSprop.

    Args:
        lr: Taux d'apprentissage
        alpha: Facteur de décroissance
        eps: Epsilon pour la stabilité
        weight_decay: Coefficient de weight decay
        momentum: Facteur de momentum
        centered: Centrer la normalisation
        **kwargs: Arguments supplémentaires

    Returns:
        RMSprop: Optimiseur RMSprop

    Example:
        ```python
        optimizer = create_rmsprop(
            lr=1e-3,
            alpha=0.99,
            momentum=0.9,
            weight_decay=1e-5
        )

        # Utilisation
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        ```
    """
    config = RMSpropConfig(
        lr=lr,
        alpha=alpha,
        eps=eps,
        weight_decay=weight_decay,
        momentum=momentum,
        centered=centered,
        **kwargs
    )
    return RMSprop(config)


__all__ = [
    'RMSprop',
    'RMSpropConfig',
    'RMSpropTF',
    'create_rmsprop',
]
