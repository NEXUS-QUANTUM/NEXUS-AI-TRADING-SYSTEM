# ai/strategies/hedging/delta_hedging.py
"""
NEXUS AI TRADING SYSTEM - Delta Hedging Strategy
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
class Option:
    """Option financière"""
    symbol: str
    underlying: str
    option_type: str  # 'call' ou 'put'
    strike: float
    expiry: datetime
    implied_volatility: float
    current_price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'underlying': self.underlying,
            'option_type': self.option_type,
            'strike': self.strike,
            'expiry': self.expiry.isoformat(),
            'implied_volatility': self.implied_volatility,
            'current_price': self.current_price,
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega,
            'rho': self.rho,
        }


@dataclass
class DeltaHedgePosition:
    """Position de couverture delta"""
    option: Option
    underlying_quantity: float
    hedge_ratio: float
    cost: float
    delta_exposure: float
    gamma_exposure: float
    vega_exposure: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'option': self.option.to_dict(),
            'underlying_quantity': self.underlying_quantity,
            'hedge_ratio': self.hedge_ratio,
            'cost': self.cost,
            'delta_exposure': self.delta_exposure,
            'gamma_exposure': self.gamma_exposure,
            'vega_exposure': self.vega_exposure,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class DeltaHedgingConfig:
    """Configuration pour Delta Hedging"""
    options: List[Dict[str, Any]] = field(default_factory=list)
    underlying_symbol: str = "BTC-USD"
    risk_free_rate: float = 0.02
    rebalance_frequency: int = 1  # secondes
    hedging_tolerance: float = 0.01
    max_hedge_ratio: float = 2.0
    min_hedge_ratio: float = 0.0
    include_gamma: bool = True
    include_vega: bool = False
    dynamic_hedging: bool = True
    cost_aware: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'underlying_symbol': self.underlying_symbol,
            'risk_free_rate': self.risk_free_rate,
            'rebalance_frequency': self.rebalance_frequency,
            'hedging_tolerance': self.hedging_tolerance,
            'max_hedge_ratio': self.max_hedge_ratio,
            'min_hedge_ratio': self.min_hedge_ratio,
            'include_gamma': self.include_gamma,
            'include_vega': self.include_vega,
            'dynamic_hedging': self.dynamic_hedging,
            'cost_aware': self.cost_aware,
        }


class DeltaHedging:
    """
    Stratégie de couverture delta.

    Features:
    - Option pricing (Black-Scholes)
    - Greeks calculation
    - Dynamic delta hedging
    - Gamma and Vega exposure
    - Rebalancing optimization

    Example:
        ```python
        config = DeltaHedgingConfig(
            options=[{'strike': 50000, 'expiry': '2024-12-31', 'option_type': 'call'}],
            underlying_symbol='BTC-USD'
        )
        strategy = DeltaHedging(config)

        # Update prices
        strategy.update_prices(underlying_price, option_prices)

        # Get hedge positions
        positions = strategy.get_positions()
        ```
    """

    def __init__(self, config: Optional[DeltaHedgingConfig] = None):
        if not SCIPY_AVAILABLE:
            raise ImportError("SciPy est requis pour Delta Hedging")

        self.config = config or DeltaHedgingConfig()
        self.options: List[Option] = []
        self.positions: List[DeltaHedgingPosition] = []
        self.underlying_price: float = 0.0
        self.hedge_history: List[Dict[str, Any]] = []

        # Initialisation des options
        self._initialize_options()

        logger.info(f"DeltaHedging initialisé")

    def _initialize_options(self) -> None:
        """Initialise les options"""
        for opt_config in self.config.options:
            option = Option(
                symbol=opt_config.get('symbol', f"OPT_{len(self.options)}"),
                underlying=self.config.underlying_symbol,
                option_type=opt_config.get('option_type', 'call'),
                strike=opt_config.get('strike', 1000),
                expiry=pd.to_datetime(opt_config.get('expiry', datetime.now() + timedelta(days=30))),
                implied_volatility=opt_config.get('implied_volatility', 0.2),
                current_price=opt_config.get('current_price', 100),
                delta=0.0,
                gamma=0.0,
                theta=0.0,
                vega=0.0,
                rho=0.0,
            )
            self.options.append(option)

    def update_prices(self, underlying_price: float, option_prices: Optional[List[float]] = None) -> None:
        """
        Met à jour les prix.

        Args:
            underlying_price: Prix du sous-jacent
            option_prices: Prix des options (optionnel)
        """
        self.underlying_price = underlying_price

        # Mise à jour des prix des options
        if option_prices:
            for i, price in enumerate(option_prices):
                if i < len(self.options):
                    self.options[i].current_price = price

        # Calcul des Grecs
        self._calculate_greeks()

        # Mise à jour des positions
        self._update_positions()

        # Enregistrement de l'historique
        self.hedge_history.append({
            'timestamp': datetime.now(),
            'underlying_price': self.underlying_price,
            'positions': [p.to_dict() for p in self.positions],
        })

    def _calculate_greeks(self) -> None:
        """Calcule les Grecs pour toutes les options"""
        for option in self.options:
            # Temps jusqu'à l'expiration
            T = (option.expiry - datetime.now()).total_seconds() / (365 * 24 * 3600)
            T = max(T, 0.0001)

            # Paramètres Black-Scholes
            S = self.underlying_price
            K = option.strike
            r = self.config.risk_free_rate
            sigma = option.implied_volatility

            d1 = (np.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)

            # Delta
            if option.option_type == 'call':
                option.delta = norm.cdf(d1)
            else:
                option.delta = -norm.cdf(-d1)

            # Gamma (même pour call et put)
            option.gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))

            # Theta
            if option.option_type == 'call':
                option.theta = -S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)
            else:
                option.theta = -S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)

            # Vega (même pour call et put)
            option.vega = S * norm.pdf(d1) * np.sqrt(T)

            # Rho
            if option.option_type == 'call':
                option.rho = K * T * np.exp(-r * T) * norm.cdf(d2)
            else:
                option.rho = -K * T * np.exp(-r * T) * norm.cdf(-d2)

    def _update_positions(self) -> None:
        """Met à jour les positions de couverture"""
        self.positions = []

        for option in self.options:
            # Quantité de sous-jacent nécessaire
            hedge_ratio = min(
                self.config.max_hedge_ratio,
                max(self.config.min_hedge_ratio, abs(option.delta))
            )

            if option.option_type == 'call':
                underlying_quantity = -option.delta * 100  # 100 actions par option
            else:
                underlying_quantity = -option.delta * 100

            # Ajustement pour gamma
            if self.config.include_gamma:
                gamma_adjustment = option.gamma * self.underlying_price * 0.01
                underlying_quantity -= gamma_adjustment

            # Ajustement pour vega
            if self.config.include_vega:
                vega_adjustment = option.vega * 0.01
                underlying_quantity -= vega_adjustment

            # Calcul du coût
            cost = abs(underlying_quantity) * self.underlying_price * 0.001  # Coût de transaction

            position = DeltaHedgePosition(
                option=option,
                underlying_quantity=underlying_quantity,
                hedge_ratio=hedge_ratio,
                cost=cost,
                delta_exposure=option.delta * 100,
                gamma_exposure=option.gamma * 100,
                vega_exposure=option.vega * 100,
            )

            self.positions.append(position)

    def get_positions(self) -> List[DeltaHedgePosition]:
        """
        Retourne les positions de couverture.

        Returns:
            List[DeltaHedgePosition]: Positions
        """
        return self.positions

    def get_total_delta(self) -> float:
        """
        Retourne le delta total.

        Returns:
            float: Delta total
        """
        return sum(p.delta_exposure for p in self.positions)

    def get_total_gamma(self) -> float:
        """
        Retourne le gamma total.

        Returns:
            float: Gamma total
        """
        return sum(p.gamma_exposure for p in self.positions)

    def get_total_vega(self) -> float:
        """
        Retourne le vega total.

        Returns:
            float: Vega total
        """
        return sum(p.vega_exposure for p in self.positions)

    def get_hedge_effectiveness(self) -> float:
        """
        Calcule l'efficacité de la couverture.

        Returns:
            float: Efficacité (0-1)
        """
        if not self.positions:
            return 0.0

        total_delta = self.get_total_delta()
        total_absolute_delta = sum(abs(p.delta_exposure) for p in self.positions)

        if total_absolute_delta == 0:
            return 1.0

        return 1 - abs(total_delta) / total_absolute_delta

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
            'total_delta': self.get_total_delta(),
            'total_gamma': self.get_total_gamma(),
            'total_vega': self.get_total_vega(),
            'hedge_effectiveness': self.get_hedge_effectiveness(),
            'total_cost': self.get_cost(),
            'n_positions': len(self.positions),
            'n_options': len(self.options),
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
            'n_options': len(self.options),
            'options': [o.to_dict() for o in self.options],
            'positions': [p.to_dict() for p in self.positions],
            'last_update': datetime.now().isoformat(),
        }


def create_delta_hedging(
    options: List[Dict[str, Any]],
    underlying_symbol: str = "BTC-USD",
    risk_free_rate: float = 0.02,
    **kwargs
) -> DeltaHedging:
    """
    Factory pour créer une stratégie de couverture delta.

    Args:
        options: Liste des options
        underlying_symbol: Symbole du sous-jacent
        risk_free_rate: Taux sans risque
        **kwargs: Arguments supplémentaires

    Returns:
        DeltaHedging: Stratégie de couverture delta
    """
    config = DeltaHedgingConfig(
        options=options,
        underlying_symbol=underlying_symbol,
        risk_free_rate=risk_free_rate,
        **kwargs
    )
    return DeltaHedging(config)


__all__ = [
    'DeltaHedging',
    'DeltaHedgingConfig',
    'Option',
    'DeltaHedgePosition',
    'create_delta_hedging',
]
