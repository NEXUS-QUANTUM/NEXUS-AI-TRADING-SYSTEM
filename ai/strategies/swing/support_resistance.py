# ai/strategies/swing/support_resistance.py
"""
NEXUS AI TRADING SYSTEM - Support & Resistance Swing Strategy
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
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class SupportResistanceConfig:
    """Configuration pour Support & Resistance Strategy"""
    symbol: str = "BTC-USD"
    lookback_period: int = 50
    consolidation_threshold: float = 0.02
    breakout_threshold: float = 0.015
    volume_threshold: float = 1.5
    position_size: float = 1.0
    stop_loss: float = 0.02
    take_profit: float = 0.05
    max_holding_time: int = 10
    fee_rate: float = 0.001
    min_touch_count: int = 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'lookback_period': self.lookback_period,
            'consolidation_threshold': self.consolidation_threshold,
            'breakout_threshold': self.breakout_threshold,
            'volume_threshold': self.volume_threshold,
            'position_size': self.position_size,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'max_holding_time': self.max_holding_time,
            'fee_rate': self.fee_rate,
            'min_touch_count': self.min_touch_count,
        }


@dataclass
class SupportResistanceLevel:
    """Niveau de support/résistance"""
    price: float
    type: str
    strength: float
    touch_count: int
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'price': self.price,
            'type': self.type,
            'strength': self.strength,
            'touch_count': self.touch_count,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class SupportResistanceSignal:
    """Signal de trading Support & Resistance"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    level_price: float
    level_type: str
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'level_price': self.level_price,
            'level_type': self.level_type,
            'confidence': self.confidence,
            'reason': self.reason,
        }


class SupportResistanceStrategy:
    """
    Stratégie Swing basée sur Support & Résistance.

    Features:
    - Support/Résistance detection
    - Breakout detection
    - Consolidation zones
    - Multiple touchpoints
    - Volume confirmation

    Example:
        ```python
        config = SupportResistanceConfig(
            symbol='BTC-USD',
            lookback_period=50,
            consolidation_threshold=0.02
        )
        strategy = SupportResistanceStrategy(config)

        # Update with data
        signal = strategy.update(price_data)
        ```
    """

    def __init__(self, config: Optional[SupportResistanceConfig] = None):
        self.config = config or SupportResistanceConfig()
        self.data: pd.DataFrame = pd.DataFrame()
        self.levels: List[SupportResistanceLevel] = []
        self.position: int = 0
        self.position_entry_price: float = 0.0
        self.position_entry_time: Optional[datetime] = None
        self.signals: List[SupportResistanceSignal] = []
        self.trade_history: List[Dict[str, Any]] = []

        logger.info(f"SupportResistanceStrategy initialisé pour {self.config.symbol}")

    def update(self, data: pd.DataFrame) -> Optional[SupportResistanceSignal]:
        """
        Met à jour la stratégie avec de nouvelles données.

        Args:
            data: DataFrame avec colonnes 'high', 'low', 'close', 'volume'

        Returns:
            Optional[SupportResistanceSignal]: Signal généré
        """
        self.data = data

        if len(data) < self.config.lookback_period:
            return None

        # Détection des niveaux
        self._detect_levels()

        # Prix et volume actuels
        current_price = data['close'].iloc[-1]
        current_volume = data['volume'].iloc[-1] if 'volume' in data.columns else 1
        avg_volume = np.mean(data['volume'].values[-20:]) if 'volume' in data.columns else 1
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

        # Génération du signal
        signal = self._generate_signal(current_price, volume_ratio)

        if signal:
            self.signals.append(signal)

            # Gestion de la position
            if signal.signal_type in ['buy', 'sell']:
                self._open_position(signal)
            elif signal.signal_type == 'exit':
                self._close_position(signal)

        return signal

    def _detect_levels(self) -> None:
        """Détecte les niveaux de support et résistance"""
        high = self.data['high'].values
        low = self.data['low'].values
        close = self.data['close'].values

        # Niveaux de prix significatifs
        price_levels = {}

        # Pivots hauts et bas
        for i in range(1, len(high) - 1):
            # Résistance
            if high[i] > high[i-1] and high[i] > high[i+1]:
                price = high[i]
                level_type = 'resistance'
                self._add_level(price_levels, price, level_type)

            # Support
            if low[i] < low[i-1] and low[i] < low[i+1]:
                price = low[i]
                level_type = 'support'
                self._add_level(price_levels, price, level_type)

        # Niveaux de consolidation
        for i in range(0, len(close) - self.config.lookback_period, 5):
            segment = close[i:i+self.config.lookback_period]
            price_range = (np.max(segment) - np.min(segment)) / np.mean(segment)

            if price_range < self.config.consolidation_threshold:
                level_price = np.mean(segment)
                level_type = 'consolidation'
                self._add_level(price_levels, level_price, level_type)

        # Création des niveaux
        self.levels = []

        for price, info in price_levels.items():
            level = SupportResistanceLevel(
                price=price,
                type=info['type'],
                strength=min(1.0, info['count'] / self.config.min_touch_count),
                touch_count=info['count'],
                timestamp=datetime.now(),
            )
            self.levels.append(level)

        # Trier par force
        self.levels.sort(key=lambda x: -x.strength)

    def _add_level(self, levels: Dict, price: float, level_type: str) -> None:
        """Ajoute un niveau à la liste"""
        # Vérification de la proximité
        for existing_price in list(levels.keys()):
            if abs(existing_price - price) / price < 0.005:
                # Mise à jour du niveau existant
                levels[existing_price]['count'] += 1
                return

        # Nouveau niveau
        levels[price] = {
            'type': level_type,
            'count': 1,
        }

    def _generate_signal(self, price: float, volume_ratio: float) -> Optional[SupportResistanceSignal]:
        """
        Génère un signal de trading.

        Args:
            price: Prix actuel
            volume_ratio: Ratio de volume

        Returns:
            Optional[SupportResistanceSignal]: Signal généré
        """
        if not self.levels:
            return None

        if self.position == 0:
            # Recherche du niveau le plus proche
            nearest_level = self._find_nearest_level(price)

            if nearest_level is None:
                return None

            # Vérification du volume
            if volume_ratio < self.config.volume_threshold:
                return None

            # Breakout de résistance
            if nearest_level.type == 'resistance':
                if price > nearest_level.price * (1 + self.config.breakout_threshold):
                    return SupportResistanceSignal(
                        timestamp=datetime.now(),
                        symbol=self.config.symbol,
                        signal_type='buy',
                        price=price,
                        level_price=nearest_level.price,
                        level_type='resistance',
                        confidence=self._calculate_confidence(nearest_level, volume_ratio),
                        reason="resistance_breakout",
                    )

            # Breakout de support
            elif nearest_level.type == 'support':
                if price < nearest_level.price * (1 - self.config.breakout_threshold):
                    return SupportResistanceSignal(
                        timestamp=datetime.now(),
                        symbol=self.config.symbol,
                        signal_type='sell',
                        price=price,
                        level_price=nearest_level.price,
                        level_type='support',
                        confidence=self._calculate_confidence(nearest_level, volume_ratio),
                        reason="support_breakout",
                    )

            # Retour sur support
            elif nearest_level.type == 'support':
                if price > nearest_level.price * (1 + self.config.breakout_threshold):
                    return SupportResistanceSignal(
                        timestamp=datetime.now(),
                        symbol=self.config.symbol,
                        signal_type='buy',
                        price=price,
                        level_price=nearest_level.price,
                        level_type='support',
                        confidence=self._calculate_confidence(nearest_level, volume_ratio),
                        reason="support_bounce",
                    )

            # Retour sur résistance
            elif nearest_level.type == 'resistance':
                if price < nearest_level.price * (1 - self.config.breakout_threshold):
                    return SupportResistanceSignal(
                        timestamp=datetime.now(),
                        symbol=self.config.symbol,
                        signal_type='sell',
                        price=price,
                        level_price=nearest_level.price,
                        level_type='resistance',
                        confidence=self._calculate_confidence(nearest_level, volume_ratio),
                        reason="resistance_reject",
                    )

        else:
            # Position ouverte
            if self.position > 0:
                if price > self.position_entry_price * (1 + self.config.take_profit):
                    return self._create_exit_signal(price, "take_profit")

                if price < self.position_entry_price * (1 - self.config.stop_loss):
                    return self._create_exit_signal(price, "stop_loss")

            elif self.position < 0:
                if price < self.position_entry_price * (1 - self.config.take_profit):
                    return self._create_exit_signal(price, "take_profit")

                if price > self.position_entry_price * (1 + self.config.stop_loss):
                    return self._create_exit_signal(price, "stop_loss")

            # Max holding time
            if self.position_entry_time:
                holding_time = (datetime.now() - self.position_entry_time).days
                if holding_time >= self.config.max_holding_time:
                    return self._create_exit_signal(price, "max_holding_time")

            # Sortie sur cassure du niveau opposé
            nearest_level = self._find_nearest_level(price)
            if nearest_level:
                if self.position > 0 and nearest_level.type == 'resistance':
                    if price < nearest_level.price:
                        return self._create_exit_signal(price, "resistance_reject")
                elif self.position < 0 and nearest_level.type == 'support':
                    if price > nearest_level.price:
                        return self._create_exit_signal(price, "support_bounce")

        return None

    def _find_nearest_level(self, price: float) -> Optional[SupportResistanceLevel]:
        """Trouve le niveau le plus proche"""
        if not self.levels:
            return None

        # Filtrer les niveaux avec force suffisante
        strong_levels = [l for l in self.levels if l.strength > 0.5]

        if not strong_levels:
            strong_levels = self.levels

        nearest = min(
            strong_levels,
            key=lambda x: abs(x.price - price)
        )

        distance = abs(nearest.price - price) / price
        if distance > 0.03:  # 3% max
            return None

        return nearest

    def _calculate_confidence(self, level: SupportResistanceLevel, volume_ratio: float) -> float:
        """
        Calcule le niveau de confiance.

        Args:
            level: Niveau de support/résistance
            volume_ratio: Ratio de volume

        Returns:
            float: Niveau de confiance (0-1)
        """
        factors = []

        # Force du niveau
        factors.append(level.strength)

        # Volume spike
        volume_factor = min(1.0, volume_ratio / (self.config.volume_threshold * 1.5))
        factors.append(volume_factor)

        # Type de niveau
        type_factors = {'support': 0.8, 'resistance': 0.8, 'consolidation': 0.6}
        factors.append(type_factors.get(level.type, 0.5))

        return np.mean(factors)

    def _create_exit_signal(self, price: float, reason: str) -> SupportResistanceSignal:
        """Crée un signal de sortie"""
        return SupportResistanceSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='exit',
            price=price,
            level_price=0.0,
            level_type='',
            confidence=0.8,
            reason=reason,
        )

    def _open_position(self, signal: SupportResistanceSignal) -> None:
        """Ouvre une position"""
        if signal.signal_type == 'buy':
            self.position = self.config.position_size
        elif signal.signal_type == 'sell':
            self.position = -self.config.position_size

        self.position_entry_price = signal.price
        self.position_entry_time = signal.timestamp

        logger.info(f"Position ouverte: {signal.signal_type} @ {signal.price:.2f} ({signal.level_type} {signal.level_price:.2f})")

    def _close_position(self, signal: SupportResistanceSignal) -> None:
        """Ferme une position"""
        if self.position == 0:
            return

        # Calcul du P&L
        if self.position > 0:
            pnl = (signal.price - self.position_entry_price) * abs(self.position)
        else:
            pnl = (self.position_entry_price - signal.price) * abs(self.position)

        # Frais
        fees = abs(self.position) * signal.price * self.config.fee_rate
        net_pnl = pnl - fees

        trade = {
            'entry_time': self.position_entry_time.isoformat() if self.position_entry_time else None,
            'exit_time': signal.timestamp.isoformat(),
            'entry_price': self.position_entry_price,
            'exit_price': signal.price,
            'position_size': self.position,
            'level_price': signal.level_price,
            'level_type': signal.level_type,
            'pnl': pnl,
            'fees': fees,
            'net_pnl': net_pnl,
            'signal': signal.to_dict(),
        }

        self.trade_history.append(trade)

        logger.info(f"Position fermée: P&L={net_pnl:.2f}")

        # Reset position
        self.position = 0
        self.position_entry_price = 0.0
        self.position_entry_time = None

    def get_performance(self) -> Dict[str, Any]:
        """
        Retourne les performances de la stratégie.

        Returns:
            Dict[str, Any]: Performances
        """
        if not self.trade_history:
            return {
                'total_trades': 0,
                'total_pnl': 0.0,
                'win_rate': 0.0,
                'avg_pnl': 0.0,
            }

        pnls = [t['net_pnl'] for t in self.trade_history]
        wins = [p for p in pnls if p > 0]

        return {
            'total_trades': len(self.trade_history),
            'total_pnl': sum(pnls),
            'win_rate': len(wins) / len(pnls) if pnls else 0.0,
            'avg_pnl': np.mean(pnls) if pnls else 0.0,
            'max_pnl': max(pnls) if pnls else 0.0,
            'min_pnl': min(pnls) if pnls else 0.0,
            'level_success_rate': sum(1 for t in self.trade_history if t.get('level_price', 0) > 0) / max(1, len(self.trade_history)),
        }


def create_support_resistance_strategy(
    symbol: str = "BTC-USD",
    lookback_period: int = 50,
    consolidation_threshold: float = 0.02,
    **kwargs
) -> SupportResistanceStrategy:
    """
    Factory pour créer une stratégie Support & Résistance.

    Args:
        symbol: Symbole
        lookback_period: Période de contexte
        consolidation_threshold: Seuil de consolidation
        **kwargs: Arguments supplémentaires

    Returns:
        SupportResistanceStrategy: Stratégie Support & Résistance
    """
    config = SupportResistanceConfig(
        symbol=symbol,
        lookback_period=lookback_period,
        consolidation_threshold=consolidation_threshold,
        **kwargs
    )
    return SupportResistanceStrategy(config)


__all__ = [
    'SupportResistanceStrategy',
    'SupportResistanceConfig',
    'SupportResistanceLevel',
    'SupportResistanceSignal',
    'create_support_resistance_strategy',
]
