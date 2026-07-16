# ai/strategies/hedging/cross_hedging.py
"""
NEXUS AI TRADING SYSTEM - Cross Hedging Strategy
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
    from scipy import stats
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class HedgeInstrument:
    """Instrument de couverture"""
    symbol: str
    weight: float
    correlation: float
    beta: float
    hedge_ratio: float
    cost: float
    liquidity: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'weight': self.weight,
            'correlation': self.correlation,
            'beta': self.beta,
            'hedge_ratio': self.hedge_ratio,
            'cost': self.cost,
            'liquidity': self.liquidity,
        }


@dataclass
class HedgePosition:
    """Position de couverture"""
    asset: str
    hedge_instruments: List[HedgeInstrument]
    total_exposure: float
    hedge_ratio: float
    cost: float
    effectiveness: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'asset': self.asset,
            'hedge_instruments': [h.to_dict() for h in self.hedge_instruments],
            'total_exposure': self.total_exposure,
            'hedge_ratio': self.hedge_ratio,
            'cost': self.cost,
            'effectiveness': self.effectiveness,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class CrossHedgingConfig:
    """Configuration pour Cross Hedging"""
    assets: List[str] = field(default_factory=lambda: ['BTC-USD'])
    hedge_instruments: List[str] = field(default_factory=lambda: ['ETH-USD', 'SOL-USD'])
    lookback_window: int = 100
    min_correlation: float = 0.5
    max_hedge_ratio: float = 2.0
    min_hedge_ratio: float = 0.1
    target_hedge_ratio: float = 1.0
    cost_threshold: float = 0.001
    rebalance_frequency: int = 10
    max_instruments: int = 3
    min_instruments: int = 1
    use_dynamic_hedging: bool = True
    volatility_scaling: bool = True
    risk_free_rate: float = 0.02

    def to_dict(self) -> Dict[str, Any]:
        return {
            'assets': self.assets,
            'hedge_instruments': self.hedge_instruments,
            'lookback_window': self.lookback_window,
            'min_correlation': self.min_correlation,
            'max_hedge_ratio': self.max_hedge_ratio,
            'min_hedge_ratio': self.min_hedge_ratio,
            'target_hedge_ratio': self.target_hedge_ratio,
            'cost_threshold': self.cost_threshold,
            'rebalance_frequency': self.rebalance_frequency,
            'max_instruments': self.max_instruments,
            'min_instruments': self.min_instruments,
            'use_dynamic_hedging': self.use_dynamic_hedging,
            'volatility_scaling': self.volatility_scaling,
            'risk_free_rate': self.risk_free_rate,
        }


class CrossHedging:
    """
    Stratégie de couverture croisée (Cross Hedging).

    Features:
    - Multi-instrument hedging
    - Correlation analysis
    - Dynamic hedge ratio
    - Cost optimization
    - Volatility scaling

    Example:
        ```python
        config = CrossHedgingConfig(
            assets=['BTC-USD'],
            hedge_instruments=['ETH-USD', 'SOL-USD'],
            lookback_window=100,
            min_correlation=0.5
        )
        strategy = CrossHedging(config)

        # Update data
        strategy.update(price_data)

        # Get hedge positions
        positions = strategy.get_hedge_positions()
        ```
    """

    def __init__(self, config: Optional[CrossHedgingConfig] = None):
        self.config = config or CrossHedgingConfig()
        self.data: Dict[str, pd.Series] = {}
        self.positions: Dict[str, HedgePosition] = {}
        self.correlations: Dict[str, Dict[str, float]] = {}
        self.hedge_history: List[Dict[str, Any]] = []

        logger.info(f"CrossHedging initialisé")

    def update(self, data: Dict[str, pd.Series]) -> None:
        """
        Met à jour les données de prix.

        Args:
            data: Dictionnaire des séries de prix
        """
        self.data = data

        # Mise à jour des corrélations
        self._update_correlations()

        # Mise à jour des positions
        for asset in self.config.assets:
            self._update_hedge_position(asset)

    def _update_correlations(self) -> None:
        """Met à jour les corrélations entre les actifs"""
        if len(self.data) < 2:
            return

        for asset in self.config.assets:
            self.correlations[asset] = {}

            if asset not in self.data:
                continue

            prices_asset = self.data[asset].values[-self.config.lookback_window:]

            for hedge in self.config.hedge_instruments:
                if hedge not in self.data:
                    continue

                prices_hedge = self.data[hedge].values[-self.config.lookback_window:]

                if len(prices_asset) == len(prices_hedge) and len(prices_asset) > 10:
                    corr = np.corrcoef(prices_asset, prices_hedge)[0, 1]
                    self.correlations[asset][hedge] = corr

    def _update_hedge_position(self, asset: str) -> None:
        """
        Met à jour la position de couverture pour un actif.

        Args:
            asset: Actif à couvrir
        """
        if asset not in self.data:
            return

        # Sélection des instruments
        instruments = self._select_instruments(asset)

        if not instruments:
            return

        # Calcul des ratios de couverture
        hedge_ratios = self._calculate_hedge_ratios(asset, instruments)

        # Calcul du coût
        costs = self._calculate_costs(asset, instruments)

        # Calcul de l'efficacité
        effectiveness = self._calculate_effectiveness(asset, instruments)

        # Construction de la position
        position = HedgePosition(
            asset=asset,
            hedge_instruments=[
                HedgeInstrument(
                    symbol=instr,
                    weight=1.0 / len(instruments),
                    correlation=self.correlations[asset].get(instr, 0),
                    beta=hedge_ratios.get(instr, 0),
                    hedge_ratio=hedge_ratios.get(instr, 0),
                    cost=costs.get(instr, 0),
                    liquidity=self._get_liquidity(instr),
                )
                for instr in instruments
            ],
            total_exposure=self._get_exposure(asset),
            hedge_ratio=sum(hedge_ratios.values()),
            cost=sum(costs.values()),
            effectiveness=effectiveness,
        )

        self.positions[asset] = position

        # Historique
        self.hedge_history.append(position.to_dict())

    def _select_instruments(self, asset: str) -> List[str]:
        """
        Sélectionne les instruments de couverture.

        Args:
            asset: Actif à couvrir

        Returns:
            List[str]: Instruments sélectionnés
        """
        if asset not in self.correlations:
            return []

        # Filtrer par corrélation
        eligible = [
            (instr, corr)
            for instr, corr in self.correlations[asset].items()
            if abs(corr) >= self.config.min_correlation
        ]

        # Trier par corrélation
        eligible.sort(key=lambda x: abs(x[1]), reverse=True)

        # Sélectionner les meilleurs
        n_instruments = min(
            len(eligible),
            self.config.max_instruments
        )
        n_instruments = max(n_instruments, self.config.min_instruments)

        return [instr for instr, _ in eligible[:n_instruments]]

    def _calculate_hedge_ratios(self, asset: str, instruments: List[str]) -> Dict[str, float]:
        """
        Calcule les ratios de couverture.

        Args:
            asset: Actif à couvrir
            instruments: Instruments de couverture

        Returns:
            Dict[str, float]: Ratios de couverture
        """
        ratios = {}

        if not SKLEARN_AVAILABLE or not SCIPY_AVAILABLE:
            # Fallback: ratio inverse des corrélations
            for instr in instruments:
                corr = self.correlations[asset].get(instr, 0)
                if abs(corr) > 0:
                    ratios[instr] = 1 / abs(corr)
                else:
                    ratios[instr] = 1.0
            return ratios

        # Régression linéaire
        prices_asset = self.data[asset].values[-self.config.lookback_window:]

        for instr in instruments:
            if instr not in self.data:
                continue

            prices_hedge = self.data[instr].values[-self.config.lookback_window:]

            if len(prices_asset) != len(prices_hedge):
                continue

            # Régression
            X = prices_hedge.reshape(-1, 1)
            y = prices_asset

            model = LinearRegression()
            model.fit(X, y)

            beta = model.coef_[0]

            if abs(beta) >= self.config.min_hedge_ratio and abs(beta) <= self.config.max_hedge_ratio:
                ratios[instr] = beta
            else:
                ratios[instr] = np.sign(beta) * max(
                    self.config.min_hedge_ratio,
                    min(abs(beta), self.config.max_hedge_ratio)
                )

        # Ajustement pour atteindre le ratio cible
        total_ratio = sum(ratios.values())
        if total_ratio > 0:
            target_ratio = self.config.target_hedge_ratio
            scale = target_ratio / total_ratio
            for instr in ratios:
                ratios[instr] *= scale

        return ratios

    def _calculate_costs(self, asset: str, instruments: List[str]) -> Dict[str, float]:
        """
        Calcule les coûts de couverture.

        Args:
            asset: Actif à couvrir
            instruments: Instruments de couverture

        Returns:
            Dict[str, float]: Coûts
        """
        costs = {}

        for instr in instruments:
            # Coût basé sur le spread et la liquidité
            spread = 0.001  # Simulé
            liquidity = self._get_liquidity(instr)
            cost = spread / liquidity

            costs[instr] = cost

        return costs

    def _calculate_effectiveness(self, asset: str, instruments: List[str]) -> float:
        """
        Calcule l'efficacité de la couverture.

        Args:
            asset: Actif à couvrir
            instruments: Instruments de couverture

        Returns:
            float: Efficacité (0-1)
        """
        if asset not in self.data:
            return 0.0

        # Calcul de la réduction de variance
        prices_asset = self.data[asset].values[-self.config.lookback_window:]
        returns_asset = np.diff(prices_asset) / prices_asset[:-1]

        # Simulation de la couverture
        portfolio_returns = returns_asset.copy()

        for instr in instruments:
            if instr not in self.data:
                continue

            prices_hedge = self.data[instr].values[-self.config.lookback_window:]
            returns_hedge = np.diff(prices_hedge) / prices_hedge[:-1]

            # Longueur minimale
            min_len = min(len(returns_asset), len(returns_hedge))
            returns_asset_aligned = returns_asset[:min_len]
            returns_hedge_aligned = returns_hedge[:min_len]

            # Réduction de la variance
            var_asset = np.var(returns_asset_aligned)
            var_hedged = np.var(returns_asset_aligned - returns_hedge_aligned)

            effectiveness = 1 - var_hedged / var_asset

        return max(0, min(1, effectiveness))

    def _get_exposure(self, asset: str) -> float:
        """Calcule l'exposition à un actif"""
        if asset not in self.data:
            return 0.0

        price = self.data[asset].iloc[-1]
        return price * 1000  # Simulé

    def _get_liquidity(self, instrument: str) -> float:
        """Retourne la liquidité d'un instrument"""
        # Simulé
        liquidity = {
            'BTC-USD': 1.0,
            'ETH-USD': 0.8,
            'SOL-USD': 0.5,
        }
        return liquidity.get(instrument, 0.5)

    def get_hedge_positions(self) -> Dict[str, HedgePosition]:
        """
        Retourne les positions de couverture.

        Returns:
            Dict[str, HedgePosition]: Positions
        """
        return self.positions

    def get_hedge_ratio(self, asset: str) -> float:
        """
        Retourne le ratio de couverture pour un actif.

        Args:
            asset: Actif

        Returns:
            float: Ratio de couverture
        """
        if asset in self.positions:
            return self.positions[asset].hedge_ratio
        return 0.0

    def get_effectiveness(self, asset: str) -> float:
        """
        Retourne l'efficacité de la couverture.

        Args:
            asset: Actif

        Returns:
            float: Efficacité
        """
        if asset in self.positions:
            return self.positions[asset].effectiveness
        return 0.0

    def get_performance(self) -> Dict[str, Any]:
        """
        Retourne les performances de la stratégie.

        Returns:
            Dict[str, Any]: Performances
        """
        if not self.positions:
            return {
                'hedged_assets': 0,
                'avg_hedge_ratio': 0.0,
                'avg_effectiveness': 0.0,
                'total_cost': 0.0,
            }

        hedge_ratios = [p.hedge_ratio for p in self.positions.values()]
        effectiveness = [p.effectiveness for p in self.positions.values()]
        costs = [p.cost for p in self.positions.values()]

        return {
            'hedged_assets': len(self.positions),
            'avg_hedge_ratio': np.mean(hedge_ratios) if hedge_ratios else 0.0,
            'avg_effectiveness': np.mean(effectiveness) if effectiveness else 0.0,
            'total_cost': sum(costs) if costs else 0.0,
            'min_effectiveness': min(effectiveness) if effectiveness else 0.0,
            'max_effectiveness': max(effectiveness) if effectiveness else 0.0,
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de la stratégie.

        Returns:
            Dict[str, Any]: Statistiques
        """
        return {
            'assets': self.config.assets,
            'hedge_instruments': self.config.hedge_instruments,
            'positions_count': len(self.positions),
            'correlations': self.correlations,
            'last_update': datetime.now().isoformat(),
        }


def create_cross_hedging(
    assets: List[str] = None,
    hedge_instruments: List[str] = None,
    lookback_window: int = 100,
    min_correlation: float = 0.5,
    **kwargs
) -> CrossHedging:
    """
    Factory pour créer une stratégie de couverture croisée.

    Args:
        assets: Actifs à couvrir
        hedge_instruments: Instruments de couverture
        lookback_window: Fenêtre de contexte
        min_correlation: Corrélation minimum
        **kwargs: Arguments supplémentaires

    Returns:
        CrossHedging: Stratégie de couverture croisée
    """
    if assets is None:
        assets = ['BTC-USD']

    if hedge_instruments is None:
        hedge_instruments = ['ETH-USD', 'SOL-USD']

    config = CrossHedgingConfig(
        assets=assets,
        hedge_instruments=hedge_instruments,
        lookback_window=lookback_window,
        min_correlation=min_correlation,
        **kwargs
    )
    return CrossHedging(config)


__all__ = [
    'CrossHedging',
    'CrossHedgingConfig',
    'HedgeInstrument',
    'HedgePosition',
    'create_cross_hedging',
]
