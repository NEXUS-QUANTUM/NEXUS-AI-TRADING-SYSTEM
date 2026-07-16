# ai/strategies/hedging/gamma_hedging.py
"""
NEXUS AI TRADING SYSTEM - Gamma Hedging Strategy
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

try:
    from scipy.stats import norm
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class GammaHedgeConfig:
    """Configuration pour Gamma Hedging"""
    underlying_symbol: str = "BTC-USD"
    risk_free_rate: float = 0.02
    rebalance_frequency: int = 1
    gamma_tolerance: float = 0.01
    max_gamma_exposure: float = 1000.0
    min_gamma_exposure: float = 0.0
    include_vanna: bool = True
    include_charm: bool = False
    dynamic_rebalancing: bool = True
    cost_aware: bool = True
    max_hedge_instruments: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            'underlying_symbol': self.underlying_symbol,
            'risk_free_rate': self.risk_free_rate,
            'rebalance_frequency': self.rebalance_frequency,
            'gamma_tolerance': self.gamma_tolerance,
            'max_gamma_exposure': self.max_gamma_exposure,
            'min_gamma_exposure': self.min_gamma_exposure,
            'include_vanna': self.include_vanna,
            'include_charm': self.include_charm,
            'dynamic_rebalancing': self.dynamic_rebalancing,
            'cost_aware': self.cost_aware,
            'max_hedge_instruments': self.max_hedge_instruments,
        }


@dataclass
class GammaHedgePosition:
    """Position de couverture gamma"""
    instrument: str
    instrument_type: str
    quantity: float
    gamma: float
    delta: float
    vega: float
    theta: float
    cost: float
    effectiveness: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'instrument': self.instrument,
            'instrument_type': self.instrument_type,
            'quantity': self.quantity,
            'gamma': self.gamma,
            'delta': self.delta,
            'vega': self.vega,
            'theta': self.theta,
            'cost': self.cost,
            'effectiveness': self.effectiveness,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class OptionGreeks:
    """Grecs d'une option"""
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    vanna: float
    charm: float
    veta: float
    vera: float
    speed: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'delta': self.delta,
            'gamma': self.gamma,
            'vega': self.vega,
            'theta': self.theta,
            'rho': self.rho,
            'vanna': self.vanna,
            'charm': self.charm,
            'veta': self.veta,
            'vera': self.vera,
            'speed': self.speed,
        }


class GammaHedging:
    """
    Stratégie de couverture gamma.

    Features:
    - Gamma exposure management
    - Second-order Greeks
    - Dynamic rebalancing
    - Multiple hedging instruments
    - Cost optimization

    Example:
        ```python
        config = GammaHedgingConfig(
            underlying_symbol='BTC-USD',
            gamma_tolerance=0.01
        )
        strategy = GammaHedging(config)

        # Update prices
        strategy.update_prices(underlying_price, option_prices)

        # Get hedge positions
        positions = strategy.get_positions()
        ```
    """

    def __init__(self, config: Optional[GammaHedgingConfig] = None):
        if not SCIPY_AVAILABLE:
            raise ImportError("SciPy est requis pour Gamma Hedging")

        self.config = config or GammaHedgingConfig()
        self.positions: List[GammaHedgePosition] = []
        self.option_greeks: Dict[str, OptionGreeks] = {}
        self.underlying_price: float = 0.0
        self.hedge_history: List[Dict[str, Any]] = []

        logger.info(f"GammaHedging initialisé")

    def update_prices(self, underlying_price: float, option_prices: Dict[str, float]) -> None:
        """
        Met à jour les prix.

        Args:
            underlying_price: Prix du sous-jacent
            option_prices: Prix des options
        """
        self.underlying_price = underlying_price

        # Calcul des Grecs
        self._calculate_greeks(option_prices)

        # Mise à jour des positions
        self._update_positions()

        # Enregistrement de l'historique
        self.hedge_history.append({
            'timestamp': datetime.now(),
            'underlying_price': self.underlying_price,
            'positions': [p.to_dict() for p in self.positions],
        })

    def _calculate_greeks(self, option_prices: Dict[str, float]) -> None:
        """
        Calcule les Grecs pour toutes les options.

        Args:
            option_prices: Prix des options
        """
        # Implémentation simplifiée
        # Dans la pratique, utiliser un modèle comme Black-Scholes
        for symbol, price in option_prices.items():
            self.option_greeks[symbol] = OptionGreeks(
                delta=np.random.uniform(-1, 1),
                gamma=np.random.uniform(0, 1),
                vega=np.random.uniform(0, 1),
                theta=np.random.uniform(-1, 0),
                rho=np.random.uniform(-1, 1),
                vanna=np.random.uniform(-1, 1),
                charm=np.random.uniform(-1, 1),
                veta=np.random.uniform(-1, 1),
                vera=np.random.uniform(-1, 1),
                speed=np.random.uniform(-1, 1),
            )

    def _update_positions(self) -> None:
        """Met à jour les positions de couverture"""
        self.positions = []

        total_gamma = sum(g.gamma for g in self.option_greeks.values())

        # Vérification du seuil
        if abs(total_gamma) < self.config.gamma_tolerance:
            return

        # Sélection des instruments de couverture
        instruments = self._select_instruments()

        # Calcul des quantités
        quantities = self._calculate_quantities(instruments, total_gamma)

        # Création des positions
        for instrument, quantity in quantities.items():
            gamma = self._get_gamma(instrument) * quantity
            delta = self._get_delta(instrument) * quantity
            vega = self._get_vega(instrument) * quantity
            theta = self._get_theta(instrument) * quantity
            cost = abs(quantity) * self.underlying_price * 0.001

            position = GammaHedgePosition(
                instrument=instrument,
                instrument_type=self._get_instrument_type(instrument),
                quantity=quantity,
                gamma=gamma,
                delta=delta,
                vega=vega,
                theta=theta,
                cost=cost,
                effectiveness=self._calculate_effectiveness(gamma, total_gamma),
                timestamp=datetime.now(),
            )

            self.positions.append(position)

    def _select_instruments(self) -> List[str]:
        """
        Sélectionne les instruments de couverture.

        Returns:
            List[str]: Instruments sélectionnés
        """
        # Simulé
        instruments = list(self.option_greeks.keys())
        return instruments[:self.config.max_hedge_instruments]

    def _calculate_quantities(self, instruments: List[str], total_gamma: float) -> Dict[str, float]:
        """
        Calcule les quantités pour chaque instrument.

        Args:
            instruments: Liste des instruments
            total_gamma: Gamma total

        Returns:
            Dict[str, float]: Quantités par instrument
        """
        quantities = {}

        if not instruments:
            return quantities

        # Distribution proportionnelle
        gamma_per_instrument = total_gamma / len(instruments)

        for instrument in instruments:
            gamma = self._get_gamma(instrument)
            if abs(gamma) > 0:
                quantity = -gamma_per_instrument / gamma
                quantities[instrument] = quantity

        return quantities

    def _get_gamma(self, instrument: str) -> float:
        """Retourne le gamma d'un instrument"""
        if instrument in self.option_greeks:
            return self.option_greeks[instrument].gamma
        return 0.0

    def _get_delta(self, instrument: str) -> float:
        """Retourne le delta d'un instrument"""
        if instrument in self.option_greeks:
            return self.option_greeks[instrument].delta
        return 0.0

    def _get_vega(self, instrument: str) -> float:
        """Retourne le vega d'un instrument"""
        if instrument in self.option_greeks:
            return self.option_greeks[instrument].vega
        return 0.0

    def _get_theta(self, instrument: str) -> float:
        """Retourne le theta d'un instrument"""
        if instrument in self.option_greeks:
            return self.option_greeks[instrument].theta
        return 0.0

    def _get_instrument_type(self, instrument: str) -> str:
        """Retourne le type d'instrument"""
        if instrument.startswith('OPT'):
            return 'option'
        return 'underlying'

    def _calculate_effectiveness(self, gamma: float, total_gamma: float) -> float:
        """
        Calcule l'efficacité de la couverture.

        Args:
            gamma: Gamma de l'instrument
            total_gamma: Gamma total

        Returns:
            float: Efficacité (0-1)
        """
        if abs(total_gamma) == 0:
            return 1.0

        effectiveness = 1 - abs(gamma) / abs(total_gamma)
        return max(0, min(1, effectiveness))

    def get_positions(self) -> List[GammaHedgePosition]:
        """
        Retourne les positions de couverture.

        Returns:
            List[GammaHedgePosition]: Positions
        """
        return self.positions

    def get_total_gamma(self) -> float:
        """
        Retourne le gamma total.

        Returns:
            float: Gamma total
        """
        return sum(p.gamma for p in self.positions)

    def get_total_delta(self) -> float:
        """
        Retourne le delta total.

        Returns:
            float: Delta total
        """
        return sum(p.delta for p in self.positions)

    def get_total_vega(self) -> float:
        """
        Retourne le vega total.

        Returns:
            float: Vega total
        """
        return sum(p.vega for p in self.positions)

    def get_hedge_effectiveness(self) -> float:
        """
        Calcule l'efficacité de la couverture.

        Returns:
            float: Efficacité (0-1)
        """
        if not self.positions:
            return 0.0

        total_gamma = self.get_total_gamma()
        total_absolute_gamma = sum(abs(p.gamma) for p in self.positions)

        if total_absolute_gamma == 0:
            return 1.0

        return 1 - abs(total_gamma) / total_absolute_gamma

    def get_cost(self) -> float:
        """
        Retourne le coût total de la couverture.

        Returns:
            float: Coût total
        """
        return sum(p.cost for p in self.positions)

    def get_performance(self) -> Dict[str, Any]:
        """
        Retourne les performances de la stratégie.

        Returns:
            Dict[str, Any]: Performances
        """
        return {
            'total_gamma': self.get_total_gamma(),
            'total_delta': self.get_total_delta(),
            'total_vega': self.get_total_vega(),
            'hedge_effectiveness': self.get_hedge_effectiveness(),
            'total_cost': self.get_cost(),
            'n_positions': len(self.positions),
            'underlying_price': self.underlying_price,
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de la stratégie.

        Returns:
            Dict[str, Any]: Statistiques
        """
        return {
            'underlying_symbol': self.config.underlying_symbol,
            'positions': [p.to_dict() for p in self.positions],
            'last_update': datetime.now().isoformat(),
        }


def create_gamma_hedging(
    underlying_symbol: str = "BTC-USD",
    gamma_tolerance: float = 0.01,
    **kwargs
) -> GammaHedging:
    """
    Factory pour créer une stratégie de couverture gamma.

    Args:
        underlying_symbol: Symbole du sous-jacent
        gamma_tolerance: Tolérance gamma
        **kwargs: Arguments supplémentaires

    Returns:
        GammaHedging: Stratégie de couverture gamma
    """
    config = GammaHedgingConfig(
        underlying_symbol=underlying_symbol,
        gamma_tolerance=gamma_tolerance,
        **kwargs
    )
    return GammaHedging(config)


__all__ = [
    'GammaHedging',
    'GammaHedgingConfig',
    'GammaHedgePosition',
    'OptionGreeks',
    'create_gamma_hedging',
]
