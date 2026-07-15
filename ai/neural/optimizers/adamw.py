# ai/neural/optimizers/adamw.py
"""
NEXUS AI TRADING SYSTEM - AdamW Optimizer
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
class AdamWConfig:
    """Configuration pour AdamW Optimizer"""
    lr: float = 1e-3
    betas: Tuple[float, float] = (0.9, 0.999)
    eps: float = 1e-8
    weight_decay: float = 0.01
    amsgrad: bool = False
    maximize: bool = False
    foreach: Optional[bool] = None
    capturable: bool = False
    differentiable: bool = False
    fused: Optional[bool] = None

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if self.lr <= 0:
            raise ValueError("lr doit être > 0")
        if self.eps < 0:
            raise ValueError("eps doit être >= 0")
        if self.weight_decay < 0:
            raise ValueError("weight_decay doit être >= 0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'lr': self.lr,
            'betas': self.betas,
            'eps': self.eps,
            'weight_decay': self.weight_decay,
            'amsgrad': self.amsgrad,
            'maximize': self.maximize,
            'foreach': self.foreach,
            'capturable': self.capturable,
            'differentiable': self.differentiable,
            'fused': self.fused,
        }


class AdamW(Optimizer):
    """
    Implémentation d'AdamW (Adam avec correction de weight decay).

    AdamW corrige le weight decay d'Adam en le séparant de la mise à jour
    du gradient, ce qui améliore la régularisation.

    Features:
    - Weight decay découplé
    - AMSGrad optionnel
    - Maximisation optionnelle
    - Fusion pour performance
    - Différentiable
    - Capturable pour compilation

    Reference:
        Loshchilov & Hutter, "Decoupled Weight Decay Regularization", 2019
    """

    def __init__(self, config: Optional[AdamWConfig] = None, **kwargs):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        if config is None:
            config = AdamWConfig(**kwargs)
        elif isinstance(config, dict):
            config = AdamWConfig(**config)

        self.config = config

        defaults = {
            'lr': config.lr,
            'betas': config.betas,
            'eps': config.eps,
            'weight_decay': config.weight_decay,
            'amsgrad': config.amsgrad,
            'maximize': config.maximize,
            'foreach': config.foreach,
            'capturable': config.capturable,
            'differentiable': config.differentiable,
            'fused': config.fused,
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
            params_with_grad = []
            grads = []
            exp_avgs = []
            exp_avg_sqs = []
            max_exp_avg_sqs = []
            state_steps = []

            beta1, beta2 = group['betas']

            for p in group['params']:
                if p.grad is None:
                    continue

                params_with_grad.append(p)
                grads.append(p.grad)

                state = self.state[p]

                if len(state) == 0:
                    state['step'] = 0
                    state['exp_avg'] = torch.zeros_like(p, memory_format=torch.preserve_format)
                    state['exp_avg_sq'] = torch.zeros_like(p, memory_format=torch.preserve_format)
                    if group['amsgrad']:
                        state['max_exp_avg_sq'] = torch.zeros_like(p, memory_format=torch.preserve_format)

                exp_avgs.append(state['exp_avg'])
                exp_avg_sqs.append(state['exp_avg_sq'])
                state_steps.append(state['step'])

                if group['amsgrad']:
                    max_exp_avg_sqs.append(state['max_exp_avg_sq'])

            if len(params_with_grad) == 0:
                continue

            # Mise à jour des paramètres
            self._update_parameters(
                params_with_grad,
                grads,
                exp_avgs,
                exp_avg_sqs,
                max_exp_avg_sqs if group['amsgrad'] else None,
                state_steps,
                group
            )

        return loss

    def _update_parameters(
        self,
        params,
        grads,
        exp_avgs,
        exp_avg_sqs,
        max_exp_avg_sqs,
        state_steps,
        group
    ):
        """Met à jour les paramètres"""
        lr = group['lr']
        beta1, beta2 = group['betas']
        eps = group['eps']
        weight_decay = group['weight_decay']
        amsgrad = group['amsgrad']
        maximize = group['maximize']

        for i, p in enumerate(params):
            grad = grads[i] if not maximize else -grads[i]

            # Mise à jour des états
            exp_avg = exp_avgs[i]
            exp_avg_sq = exp_avg_sqs[i]
            step = state_steps[i]

            # Découplage du weight decay
            if weight_decay != 0:
                p.mul_(1 - lr * weight_decay)

            # Mise à jour des moments
            exp_avg.mul_(beta1).add_(grad, alpha=1 - beta1)
            exp_avg_sq.mul_(beta2).addcmul_(grad, grad, value=1 - beta2)

            if amsgrad and max_exp_avg_sqs is not None:
                max_exp_avg_sq = max_exp_avg_sqs[i]
                torch.maximum(max_exp_avg_sq, exp_avg_sq, out=max_exp_avg_sq)
                denom = (max_exp_avg_sq.sqrt() / math.sqrt(beta2 ** (step + 1))).add_(eps)
            else:
                denom = (exp_avg_sq.sqrt() / math.sqrt(beta2 ** (step + 1))).add_(eps)

            # Mise à jour des paramètres
            p.addcdiv_(exp_avg, denom, value=-lr)

            # Incrément du pas
            step += 1
            state_steps[i] = step

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
            'amsgrad': self.config.amsgrad,
            'maximize': self.config.maximize,
        }


def create_adamw(
    lr: float = 1e-3,
    betas: Tuple[float, float] = (0.9, 0.999),
    eps: float = 1e-8,
    weight_decay: float = 0.01,
    amsgrad: bool = False,
    **kwargs
) -> AdamW:
    """
    Factory pour créer un optimiseur AdamW.

    Args:
        lr: Taux d'apprentissage
        betas: Paramètres de décroissance exponentielle
        eps: Epsilon pour la stabilité
        weight_decay: Coefficient de weight decay
        amsgrad: Utiliser AMSGrad
        **kwargs: Arguments supplémentaires

    Returns:
        AdamW: Optimiseur AdamW

    Example:
        ```python
        optimizer = create_adamw(
            lr=1e-3,
            weight_decay=0.01,
            betas=(0.9, 0.999)
        )

        # Utilisation
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
