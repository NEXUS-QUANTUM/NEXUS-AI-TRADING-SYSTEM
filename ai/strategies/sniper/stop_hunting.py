
# ai/strategies/sniper/stop_hunting.py
"""
NEXUS AI TRADING SYSTEM - Stop Hunting Strategy (Sniper)
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
class StopHuntingConfig:
    """Configuration pour Stop Hunting Strategy"""
    symbol: str = "BTC-USD"
    lookback_period: int = 20
    stop_level_threshold: float = 0.01
    volume_threshold: float = 1.5
    recovery_threshold: float = 0.005
    position_size: float = 1.0
    stop_loss: float = 0.015
    take_profit: float = 0.03
    max_holding_time: int = 3
    fee_rate: float = 0.001
    min_volume: float = 1000.0
    use_fibonacci: bool = True
    fibonacci_levels: List[float] = field(default_factory=lambda: [0.236, 0.382, 0.5, 0.618, 0.786])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'lookback_period': self.lookback_period,
            'stop_level_threshold': self.stop_level_threshold,
            'volume_threshold': self.volume_threshold,
            'recovery_threshold': self.recovery_threshold,
            'position_size': self.position_size,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'max_holding_time': self.max_holding_time,
            'fee_rate': self.fee_rate,
            'min_volume': self.min_volume,
            'use_fibonacci': self.use_fibonacci,
            'fibonacci_levels': self.fibonacci_levels,
        }


@dataclass
class StopLevel:
    """Niveau de stop"""
    price: float
    type: str
    strength: float
    volume: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'price': self.price,
            'type': self.type,
            'strength': self.strength,
            'volume': self.volume,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class StopHuntingSignal:
    """Signal de Stop Hunting"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    stop_level: float
    volume_spike: float
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'stop_level': self.stop_level,
            'volume_spike': self.volume_spike,
            'confidence': self.confidence,
            'reason': self.reason,
        }


class StopHuntingStrategy:
    """
    Stratégie de chasse aux stops (Sniper).

    Features:
    - Stop level detection
    - Volume confirmation
    - Fibonacci retracement
    - Recovery detection
    - Fast execution

    Example:
        ```python
        config = StopHuntingConfig(
            symbol='BTC-USD',
            lookback_period=20,
            stop_level_threshold=0.01
        )
        strategy = StopHuntingStrategy(config)

        # Update with data
        signal = strategy.update(price_data)
        ```
    """

    def __init__(self, config: Optional[StopHuntingConfig] = None):
        self.config = config or StopHuntingConfig()
        self.data: pd.DataFrame = pd.DataFrame()
        self.stop_levels: List[StopLevel] = []
        self.position: int = 0
        self.position_entry_price: float = 0.0
        self.position_entry_time: Optional[datetime] = None
        self.signals: List[StopHuntingSignal] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.volume_spikes: List[float] = []

        logger.info(f"StopHuntingStrategy initialisé pour {self.config.symbol}")

    def update(self, data: pd.DataFrame) -> Optional[StopHuntingSignal]:
        """
        Met à jour la stratégie avec de nouvelles données.

        Args:
            data: DataFrame avec colonnes 'high', 'low', 'close', 'volume'

        Returns:
            Optional[StopHuntingSignal]: Signal généré
        """
        self.data = data

        if len(data) < self.config.lookback_period:
            return None

        # Détection des niveaux de stop
        self._detect_stop_levels()

        # Calcul du volume spike
        volume_spike = self._calculate_volume_spike()

        # Prix actuel
        current_price = data['close'].iloc[-1]

        # Génération du signal
        signal = self._generate_signal(current_price, volume_spike)

        if signal:
            self.signals.append(signal)

            # Gestion de la position
            if signal.signal_type in ['buy', 'sell']:
                self._open_position(signal)
            elif signal.signal_type == 'exit':
                self._close_position(signal)

        return signal

    def _detect_stop_levels(self) -> None:
        """Détecte les niveaux de stop"""
        high = self.data['high'].values[-self.config.lookback_period:]
        low = self.data['low'].values[-self.config.lookback_period:]
        close = self.data['close'].values[-self.config.lookback_period:]

        self.stop_levels = []

        # Niveaux de support/résistance
        support_levels = self._find_support_levels(low)
        resistance_levels = self._find_resistance_levels(high)

        # Niveaux de Fibonacci
        if self.config.use_fibonacci:
            fib_levels = self._calculate_fibonacci_levels(high, low)
        else:
            fib_levels = []

        # Création des niveaux de stop
        for price in support_levels + resistance_levels:
            volume = self._get_volume_near_level(price)
            if volume > self.config.min_volume:
                level_type = 'support' if price in support_levels else 'resistance'
                strength = min(1.0, volume / (self.config.min_volume * 2))

                stop_level = StopLevel(
                    price=price,
                    type=level_type,
                    strength=strength,
                    volume=volume,
                    timestamp=datetime.now(),
                )
                self.stop_levels.append(stop_level)

        # Ajout des niveaux Fibonacci
        for level in fib_levels:
            volume = self._get_volume_near_level(level)
            if volume > self.config.min_volume:
                stop_level = StopLevel(
                    price=level,
                    type='fibonacci',
                    strength=0.6,
                    volume=volume,
                    timestamp=datetime.now(),
                )
                self.stop_levels.append(stop_level)

    def _find_support_levels(self, low: np.ndarray) -> List[float]:
        """Trouve les niveaux de support"""
        supports = []
        for i in range(1, len(low) - 1):
            if low[i] < low[i-1] and low[i] < low[i+1]:
                supports.append(low[i])
        return supports

    def _find_resistance_levels(self, high: np.ndarray) -> List[float]:
        """Trouve les niveaux de résistance"""
        resistances = []
        for i in range(1, len(high) - 1):
            if high[i] > high[i-1] and high[i] > high[i+1]:
                resistances.append(high[i])
        return resistances

    def _calculate_fibonacci_levels(self, high: np.ndarray, low: np.ndarray) -> List[float]:
        """Calcule les niveaux de Fibonacci"""
        if len(high) < 2 or len(low) < 2:
            return []

        max_high = np.max(high)
        min_low = np.min(low)
        diff = max_high - min_low

        levels = []
        for level in self.config.fibonacci_levels:
            if level < 1:
                levels.append(max_high - diff * level)

        return levels

    def _get_volume_near_level(self, price: float) -> float:
        """Calcule le volume près d'un niveau"""
        if 'volume' not in self.data.columns:
            return 0.0

        volumes = self.data['volume'].values[-self.config.lookback_period:]
        closes = self.data['close'].values[-self.config.lookback_period:]

        total_volume = 0
        for i, close in enumerate(closes):
            if abs(close - price) / price < self.config.stop_level_threshold:
                total_volume += volumes[i]

        return total_volume

    def _calculate_volume_spike(self) -> float:
        """Calcule le volume spike"""
        if 'volume' not in self.data.columns:
            return 1.0

        volumes = self.data['volume'].values[-20:]
        current_volume = volumes[-1] if len(volumes) > 0 else 1
        avg_volume = np.mean(volumes[:-1]) if len(volumes) > 1 else 1

        spike = current_volume / avg_volume if avg_volume > 0 else 1
        self.volume_spikes.append(spike)

        return spike

    def _generate_signal(self, price: float, volume_spike: float) -> Optional[StopHuntingSignal]:
        """
        Génère un signal de trading.

        Args:
            price: Prix actuel
            volume_spike: Volume spike

        Returns:
            Optional[StopHuntingSignal]: Signal généré
        """
        if not self.stop_levels:
            return None

        if self.position == 0:
            # Recherche du niveau de stop le plus proche
            nearest_stop = self._find_nearest_stop_level(price)

            if nearest_stop is None:
                return None

            # Vérification du volume
            if volume_spike < self.config.volume_threshold:
                return None

            # Détection de la chasse aux stops
            if nearest_stop.type in ['support', 'fibonacci']:
                # Support -> potentiel d'achat
                if price < nearest_stop.price * (1 + self.config.stop_level_threshold):
                    if self._detect_stop_hunt(price, nearest_stop, 'support'):
                        return StopHuntingSignal(
                            timestamp=datetime.now(),
                            symbol=self.config.symbol,
                            signal_type='buy',
                            price=price,
                            stop_level=nearest_stop.price,
                            volume_spike=volume_spike,
                            confidence=self._calculate_confidence(nearest_stop, volume_spike),
                            reason="stop_hunt_support",
                        )

            elif nearest_stop.type in ['resistance', 'fibonacci']:
                if price > nearest_stop.price * (1 - self.config.stop_level_threshold):
                    if self._detect_stop_hunt(price, nearest_stop, 'resistance'):
                        return StopHuntingSignal(
                            timestamp=datetime.now(),
                            symbol=self.config.symbol,
                            signal_type='sell',
                            price=price,
                            stop_level=nearest_stop.price,
                            volume_spike=volume_spike,
                            confidence=self._calculate_confidence(nearest_stop, volume_spike),
                            reason="stop_hunt_resistance",
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

        return None

    def _find_nearest_stop_level(self, price: float) -> Optional[StopLevel]:
        """Trouve le niveau de stop le plus proche"""
        if not self.stop_levels:
            return None

        nearest = min(
            self.stop_levels,
            key=lambda x: abs(x.price - price)
        )

        distance = abs(nearest.price - price) / price
        if distance > 0.03:  # 3% max
            return None

        return nearest

    def _detect_stop_hunt(self, price: float, level: StopLevel, direction: str) -> bool:
        """
        Détecte une chasse aux stops.

        Args:
            price: Prix actuel
            level: Niveau de stop
            direction: 'support' ou 'resistance'

        Returns:
            bool: True si chasse aux stops détectée
        """
        # Vérification du croisement
        if direction == 'support':
            # Prix qui traverse le support puis remonte
            if price > level.price * (1 + self.config.recovery_threshold):
                return True
        else:
            # Prix qui traverse la résistance puis redescend
            if price < level.price * (1 - self.config.recovery_threshold):
                return True

        return False

    def _calculate_confidence(self, level: StopLevel, volume_spike: float) -> float:
        """
        Calcule le niveau de confiance.

        Args:
            level: Niveau de stop
            volume_spike: Volume spike

        Returns:
            float: Niveau de confiance (0-1)
        """
        factors = []

        # Force du niveau
        factors.append(level.strength)

        # Volume spike
        volume_factor = min(1.0, volume_spike / (self.config.volume_threshold * 1.5))
        factors.append(volume_factor)

        # Type de niveau
        type_factors = {'support': 0.8, 'resistance': 0.8, 'fibonacci': 0.6}
        factors.append(type_factors.get(level.type, 0.5))

        return np.mean(factors)

    def _create_exit_signal(self, price: float, reason: str) -> StopHuntingSignal:
        """Crée un signal de sortie"""
        return StopHuntingSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='exit',
            price=price,
            stop_level=0.0,
            volume_spike=0.0,
            confidence=0.8,
            reason=reason,
        )

    def _open_position(self, signal: StopHuntingSignal) -> None:
        """Ouvre une position"""
        if signal.signal_type == 'buy':
            self.position = self.config.position_size
        elif signal.signal_type == 'sell':
            self.position = -self.config.position_size

        self.position_entry_price = signal.price
        self.position_entry_time = signal.timestamp

        logger.info(f"Position ouverte: {signal.signal_type} @ {signal.price:.2f} (stop: {signal.stop_level:.2f})")

    def _close_position(self, signal: StopHuntingSignal) -> None:
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
            'stop_level': signal.stop_level,
            'volume_spike': signal.volume_spike,
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
            'stop_hunt_success': sum(1 for t in self.trade_history if t.get('stop_level', 0) > 0) / max(1, len(self.trade_history)),
        }


def create_stop_hunting_strategy(
    symbol: str = "BTC-USD",
    lookback_period: int = 20,
    stop_level_threshold: float = 0.01,
    **kwargs
) -> StopHuntingStrategy:
    """
    Factory pour créer une stratégie de chasse aux stops.

    Args:
        symbol: Symbole
        lookback_period: Période de contexte
        stop_level_threshold: Seuil de niveau de stop
        **kwargs: Arguments supplémentaires

    Returns:
        StopHuntingStrategy: Stratégie de chasse aux stops
    """
    config = StopHuntingConfig(
        symbol=symbol,
        lookback_period=lookback_period,
        stop_level_threshold=stop_level_threshold,
        **kwargs
    )
    return StopHuntingStrategy(config)


__all__ = [
    'StopHuntingStrategy',
    'StopHuntingConfig',
    'StopLevel',
    'StopHuntingSignal',
    'create_stop_hunting_strategy',
]
