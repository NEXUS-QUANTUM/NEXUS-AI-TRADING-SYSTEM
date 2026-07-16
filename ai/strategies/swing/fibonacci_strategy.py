
# ai/strategies/swing/fibonacci_strategy.py
"""
NEXUS AI TRADING SYSTEM - Fibonacci Swing Strategy
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
class FibonacciConfig:
    """Configuration pour Fibonacci Strategy"""
    symbol: str = "BTC-USD"
    lookback_period: int = 50
    fib_levels: List[float] = field(default_factory=lambda: [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0])
    retracement_levels: List[float] = field(default_factory=lambda: [0.382, 0.5, 0.618])
    extension_levels: List[float] = field(default_factory=lambda: [1.272, 1.618, 2.618])
    entry_zone: float = 0.05
    position_size: float = 1.0
    stop_loss: float = 0.02
    take_profit: float = 0.05
    max_holding_time: int = 14
    fee_rate: float = 0.001
    use_trend_filter: bool = True
    trend_period: int = 50

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'lookback_period': self.lookback_period,
            'fib_levels': self.fib_levels,
            'retracement_levels': self.retracement_levels,
            'extension_levels': self.extension_levels,
            'entry_zone': self.entry_zone,
            'position_size': self.position_size,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'max_holding_time': self.max_holding_time,
            'fee_rate': self.fee_rate,
            'use_trend_filter': self.use_trend_filter,
            'trend_period': self.trend_period,
        }


@dataclass
class FibonacciLevel:
    """Niveau de Fibonacci"""
    level: float
    price: float
    type: str
    strength: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'level': self.level,
            'price': self.price,
            'type': self.type,
            'strength': self.strength,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class FibonacciSignal:
    """Signal de trading Fibonacci"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    fib_level: float
    fib_price: float
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'fib_level': self.fib_level,
            'fib_price': self.fib_price,
            'confidence': self.confidence,
            'reason': self.reason,
        }


class FibonacciStrategy:
    """
    Stratégie Swing basée sur Fibonacci.

    Features:
    - Fibonacci retracement
    - Fibonacci extension
    - Trend filter
    - Multiple entry zones
    - Risk management

    Example:
        ```python
        config = FibonacciConfig(
            symbol='BTC-USD',
            lookback_period=50,
            fib_levels=[0.382, 0.5, 0.618]
        )
        strategy = FibonacciStrategy(config)

        # Update with data
        signal = strategy.update(price_data)
        ```
    """

    def __init__(self, config: Optional[FibonacciConfig] = None):
        self.config = config or FibonacciConfig()
        self.data: pd.DataFrame = pd.DataFrame()
        self.fib_levels: List[FibonacciLevel] = []
        self.position: int = 0
        self.position_entry_price: float = 0.0
        self.position_entry_time: Optional[datetime] = None
        self.signals: List[FibonacciSignal] = []
        self.trade_history: List[Dict[str, Any]] = []

        logger.info(f"FibonacciStrategy initialisé pour {self.config.symbol}")

    def update(self, data: pd.DataFrame) -> Optional[FibonacciSignal]:
        """
        Met à jour la stratégie avec de nouvelles données.

        Args:
            data: DataFrame avec colonnes 'high', 'low', 'close'

        Returns:
            Optional[FibonacciSignal]: Signal généré
        """
        self.data = data

        if len(data) < self.config.lookback_period:
            return None

        # Calcul des niveaux de Fibonacci
        self._calculate_fibonacci_levels()

        # Prix actuel
        current_price = data['close'].iloc[-1]

        # Génération du signal
        signal = self._generate_signal(current_price)

        if signal:
            self.signals.append(signal)

            # Gestion de la position
            if signal.signal_type in ['buy', 'sell']:
                self._open_position(signal)
            elif signal.signal_type == 'exit':
                self._close_position(signal)

        return signal

    def _calculate_fibonacci_levels(self) -> None:
        """Calcule les niveaux de Fibonacci"""
        high = self.data['high'].values[-self.config.lookback_period:]
        low = self.data['low'].values[-self.config.lookback_period:]

        # Points extrêmes
        swing_high = np.max(high)
        swing_low = np.min(low)
        diff = swing_high - swing_low

        self.fib_levels = []

        # Retracement
        for level in self.config.retracement_levels:
            price = swing_high - diff * level
            fib_level = FibonacciLevel(
                level=level,
                price=price,
                type='retracement',
                strength=self._calculate_level_strength(price, level),
                timestamp=datetime.now(),
            )
            self.fib_levels.append(fib_level)

        # Extensions
        if self._is_bullish_trend():
            for level in self.config.extension_levels:
                price = swing_low + diff * level
                fib_level = FibonacciLevel(
                    level=level,
                    price=price,
                    type='extension',
                    strength=self._calculate_level_strength(price, level),
                    timestamp=datetime.now(),
                )
                self.fib_levels.append(fib_level)
        else:
            for level in self.config.extension_levels:
                price = swing_high - diff * level
                fib_level = FibonacciLevel(
                    level=level,
                    price=price,
                    type='extension',
                    strength=self._calculate_level_strength(price, level),
                    timestamp=datetime.now(),
                )
                self.fib_levels.append(fib_level)

        # Trier par prix
        self.fib_levels.sort(key=lambda x: x.price)

    def _calculate_level_strength(self, price: float, level: float) -> float:
        """
        Calcule la force d'un niveau.

        Args:
            price: Prix du niveau
            level: Niveau de Fibonacci

        Returns:
            float: Force du niveau (0-1)
        """
        # Historique des prix près du niveau
        closes = self.data['close'].values
        volume = self.data['volume'].values if 'volume' in self.data.columns else np.ones_like(closes)

        # Volume autour du niveau
        near_level = 0
        total_volume = 0

        for i, close in enumerate(closes):
            if abs(close - price) / price < 0.02:
                near_level += volume[i]
            total_volume += volume[i]

        volume_ratio = near_level / total_volume if total_volume > 0 else 0

        # Force basée sur la position du niveau
        strength = 0.5 + 0.5 * volume_ratio

        return min(1.0, strength)

    def _is_bullish_trend(self) -> bool:
        """Détermine si la tendance est haussière"""
        if not self.config.use_trend_filter:
            return True

        close = self.data['close'].values
        sma = np.mean(close[-self.config.trend_period:])
        current_price = close[-1]

        return current_price > sma

    def _generate_signal(self, price: float) -> Optional[FibonacciSignal]:
        """
        Génère un signal de trading.

        Args:
            price: Prix actuel

        Returns:
            Optional[FibonacciSignal]: Signal généré
        """
        if not self.fib_levels:
            return None

        if self.position == 0:
            # Recherche des niveaux de Fibonacci
            nearest_level = self._find_nearest_level(price)

            if nearest_level is None:
                return None

            # Vérification de la zone d'entrée
            distance = abs(price - nearest_level.price) / price

            if distance > self.config.entry_zone:
                return None

            # Direction basée sur le niveau
            if nearest_level.type == 'retracement':
                if self._is_bullish_trend():
                    # Retracement haussier -> achat
                    confidence = self._calculate_confidence(nearest_level, price)
                    if confidence > 0.5:
                        return FibonacciSignal(
                            timestamp=datetime.now(),
                            symbol=self.config.symbol,
                            signal_type='buy',
                            price=price,
                            fib_level=nearest_level.level,
                            fib_price=nearest_level.price,
                            confidence=confidence,
                            reason="fib_retracement_bullish",
                        )
                else:
                    # Retracement baissier -> vente
                    confidence = self._calculate_confidence(nearest_level, price)
                    if confidence > 0.5:
                        return FibonacciSignal(
                            timestamp=datetime.now(),
                            symbol=self.config.symbol,
                            signal_type='sell',
                            price=price,
                            fib_level=nearest_level.level,
                            fib_price=nearest_level.price,
                            confidence=confidence,
                            reason="fib_retracement_bearish",
                        )

            elif nearest_level.type == 'extension':
                if self._is_bullish_trend():
                    # Extension haussière -> achat
                    confidence = self._calculate_confidence(nearest_level, price)
                    if confidence > 0.5:
                        return FibonacciSignal(
                            timestamp=datetime.now(),
                            symbol=self.config.symbol,
                            signal_type='buy',
                            price=price,
                            fib_level=nearest_level.level,
                            fib_price=nearest_level.price,
                            confidence=confidence,
                            reason="fib_extension_bullish",
                        )
                else:
                    # Extension baissière -> vente
                    confidence = self._calculate_confidence(nearest_level, price)
                    if confidence > 0.5:
                        return FibonacciSignal(
                            timestamp=datetime.now(),
                            symbol=self.config.symbol,
                            signal_type='sell',
                            price=price,
                            fib_level=nearest_level.level,
                            fib_price=nearest_level.price,
                            confidence=confidence,
                            reason="fib_extension_bearish",
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

    def _find_nearest_level(self, price: float) -> Optional[FibonacciLevel]:
        """Trouve le niveau de Fibonacci le plus proche"""
        if not self.fib_levels:
            return None

        nearest = min(
            self.fib_levels,
            key=lambda x: abs(x.price - price)
        )

        distance = abs(nearest.price - price) / price
        if distance > 0.05:  # 5% max
            return None

        return nearest

    def _calculate_confidence(self, level: FibonacciLevel, price: float) -> float:
        """
        Calcule le niveau de confiance.

        Args:
            level: Niveau de Fibonacci
            price: Prix actuel

        Returns:
            float: Niveau de confiance (0-1)
        """
        factors = []

        # Force du niveau
        factors.append(level.strength)

        # Proximité du niveau
        distance = abs(price - level.price) / price
        proximity = 1 - min(1.0, distance / self.config.entry_zone)
        factors.append(proximity)

        # Type de niveau
        type_factors = {'retracement': 0.8, 'extension': 0.6}
        factors.append(type_factors.get(level.type, 0.5))

        return np.mean(factors)

    def _create_exit_signal(self, price: float, reason: str) -> FibonacciSignal:
        """Crée un signal de sortie"""
        return FibonacciSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='exit',
            price=price,
            fib_level=0.0,
            fib_price=0.0,
            confidence=0.8,
            reason=reason,
        )

    def _open_position(self, signal: FibonacciSignal) -> None:
        """Ouvre une position"""
        if signal.signal_type == 'buy':
            self.position = self.config.position_size
        elif signal.signal_type == 'sell':
            self.position = -self.config.position_size

        self.position_entry_price = signal.price
        self.position_entry_time = signal.timestamp

        logger.info(f"Position ouverte: {signal.signal_type} @ {signal.price:.2f} (fib: {signal.fib_level:.3f})")

    def _close_position(self, signal: FibonacciSignal) -> None:
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
            'fib_level': signal.fib_level,
            'fib_price': signal.fib_price,
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
            'fib_success_rate': sum(1 for t in self.trade_history if t.get('fib_level', 0) > 0) / max(1, len(self.trade_history)),
        }


def create_fibonacci_strategy(
    symbol: str = "BTC-USD",
    lookback_period: int = 50,
    **kwargs
) -> FibonacciStrategy:
    """
    Factory pour créer une stratégie Fibonacci.

    Args:
        symbol: Symbole
        lookback_period: Période de contexte
        **kwargs: Arguments supplémentaires

    Returns:
        FibonacciStrategy: Stratégie Fibonacci
    """
    config = FibonacciConfig(
        symbol=symbol,
        lookback_period=lookback_period,
        **kwargs
    )
    return FibonacciStrategy(config)


__all__ = [
    'FibonacciStrategy',
    'FibonacciConfig',
    'FibonacciLevel',
    'FibonacciSignal',
    'create_fibonacci_strategy',
]
