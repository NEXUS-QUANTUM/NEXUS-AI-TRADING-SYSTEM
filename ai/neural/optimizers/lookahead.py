
# ai/neural/optimizers/lookahead.py
"""
NEXUS AI TRADING SYSTEM - Lookahead Optimizer
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
class LookaheadConfig:
    """Configuration pour Lookahead Optimizer"""
    lr: float = 1e-3
    k: int = 5
    alpha: float = 0.5
    inner_optimizer: Optional[Optimizer] = None
    inner_optimizer_config: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if self.lr <= 0:
            raise ValueError("lr doit être > 0")
        if self.k <= 0:
            raise ValueError("k doit être > 0")
        if self.alpha < 0 or self.alpha > 1:
            raise ValueError("alpha doit être entre 0 et 1")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'lr': self.lr,
            'k': self.k,
            'alpha': self.alpha,
            'inner_optimizer_config': self.inner_optimizer_config,
        }


class Lookahead(Optimizer):
    """
    Implémentation de Lookahead Optimizer.

    Lookahead combine un optimiseur interne (fast) avec des mises à jour
    périodiques (slow) pour améliorer la convergence et la stabilité.

    Features:
    - Combinaison d'optimiseurs rapide et lent
    - Mises à jour périodiques
    - Configuration flexible
    - Support de tout optimiseur interne

    Reference:
        Zhang et al., "Lookahead Optimizer: k steps forward, 1 step back", 2019
    """

    def __init__(self, config: Optional[LookaheadConfig] = None, **kwargs):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        if config is None:
            config = LookaheadConfig(**kwargs)
        elif isinstance(config, dict):
            config = LookaheadConfig(**config)

        self.config = config
        self.k = config.k
        self.alpha = config.alpha
        self._step_counter = 0

        # Optimiseur interne
        if config.inner_optimizer is not None:
            self.inner_optimizer = config.inner_optimizer
        else:
            # Créer un optimiseur interne par défaut (SGD)
            from ai.neural.optimizers.sgd import SGD, SGDConfig

            inner_config = config.inner_optimizer_config or {}
            lr = inner_config.pop('lr', config.lr)
            self.inner_optimizer = SGD(
                SGDConfig(
                    lr=lr,
                    **inner_config
                )
            )

        defaults = {
            'lr': config.lr,
        }

        super().__init__([], defaults)

        # Initialisation des paramètres
        self._init_params()

    def _init_params(self):
        """Initialise les paramètres slow"""
        for group in self.param_groups:
            for p in group['params']:
                if p.requires_grad:
                    state = self.state[p]
                    if 'slow_params' not in state:
                        state['slow_params'] = p.data.clone().detach()
                    if 'step' not in state:
                        state['step'] = 0

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

        # Étape de l'optimiseur interne
        self.inner_optimizer.step()

        self._step_counter += 1

        # Mise à jour périodique (slow)
        if self._step_counter % self.k == 0:
            for group in self.param_groups:
                for p in group['params']:
                    if p.requires_grad:
                        state = self.state[p]
                        slow_params = state['slow_params']

                        # Mise à jour slow: slow = slow + alpha * (fast - slow)
                        p.data = slow_params + self.alpha * (p.data - slow_params)
                        state['slow_params'] = p.data.clone().detach()
                        state['step'] += 1

        return loss

    def reset(self):
        """Réinitialise le compteur de pas"""
        self._step_counter = 0

    def get_config(self) -> Dict[str, Any]:
        """Retourne la configuration de l'optimiseur"""
        config = self.config.to_dict()
        if self.inner_optimizer:
            if hasattr(self.inner_optimizer, 'get_config'):
                config['inner_optimizer'] = self.inner_optimizer.get_config()
        return config

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques de l'optimiseur"""
        total_params = sum(p.numel() for group in self.param_groups for p in group['params'])
        trainable_params = sum(p.numel() for group in self.param_groups for p in group['params'] if p.requires_grad)

        metrics = {
            'total_parameters': total_params,
            'trainable_parameters': trainable_params,
            'step_counter': self._step_counter,
            'k': self.k,
            'alpha': self.alpha,
        }

        if self.inner_optimizer and hasattr(self.inner_optimizer, 'get_metrics'):
            metrics['inner_optimizer'] = self.inner_optimizer.get_metrics()

        return metrics


class LookaheadWrapper:
    """
    Wrapper pour appliquer Lookahead à un optimiseur existant.
    """

    def __init__(
        self,
        optimizer: Optimizer,
        k: int = 5,
        alpha: float = 0.5,
    ):
        self.optimizer = optimizer
        self.k = k
        self.alpha = alpha
        self._step_counter = 0

        # Initialisation des paramètres slow
        self._init_params()

    def _init_params(self):
        """Initialise les paramètres slow"""
        for group in self.optimizer.param_groups:
            for p in group['params']:
                if p.requires_grad:
                    state = self.optimizer.state[p]
                    if 'slow_params' not in state:
                        state['slow_params'] = p.data.clone().detach()
                    if 'step' not in state:
                        state['step'] = 0

    def step(self, closure=None):
        """
        Effectue une étape d'optimisation avec Lookahead.

        Args:
            closure: Fonction de closure (optionnel)

        Returns:
            Optional[float]: Perte si closure est fournie
        """
        loss = self.optimizer.step(closure)

        self._step_counter += 1

        if self._step_counter % self.k == 0:
            for group in self.optimizer.param_groups:
                for p in group['params']:
                    if p.requires_grad:
                        state = self.optimizer.state[p]
                        slow_params = state['slow_params']

                        p.data = slow_params + self.alpha * (p.data - slow_params)
                        state['slow_params'] = p.data.clone().detach()
                        state['step'] += 1

        return loss

    def reset(self):
        """Réinitialise le compteur de pas"""
        self._step_counter = 0

    def zero_grad(self):
        """Met les gradients à zéro"""
        self.optimizer.zero_grad()

    def __getattr__(self, name):
        """Délègue les attributs à l'optimiseur interne"""
        if hasattr(self.optimizer, name):
            return getattr(self.optimizer, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


def create_lookahead(
    lr: float = 1e-3,
    k: int = 5,
    alpha: float = 0.5,
    inner_optimizer: Optional[Optimizer] = None,
    **kwargs
) -> Lookahead:
    """
    Factory pour créer un optimiseur Lookahead.

    Args:
        lr: Taux d'apprentissage
        k: Fréquence des mises à jour slow
        alpha: Facteur de mélange
        inner_optimizer: Optimiseur interne (optionnel)
        **kwargs: Arguments supplémentaires

    Returns:
        Lookahead: Optimiseur Lookahead

    Example:
        ```python
        # Avec optimiseur interne par défaut (SGD)
        optimizer = create_lookahead(
            lr=1e-3,
            k=5,
            alpha=0.5
        )

        # Avec optimiseur personnalisé
        from ai.neural.optimizers.adamw import AdamW
        inner = AdamW(lr=1e-3)
        optimizer = create_lookahead(
            k=6,
            alpha=0.5,
            inner_optimizer=inner
        )

        # Utilisation
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        ```
    """
    config = LookaheadConfig(
        lr=lr,
        k=k,
        alpha=alpha,
        inner_optimizer=inner_optimizer,
        **kwargs
    )
    return Lookahead(config)


__all__ = [
    'Lookahead',
    'LookaheadConfig',
    'LookaheadWrapper',
    'create_lookahead',
]
