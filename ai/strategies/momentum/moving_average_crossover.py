# ai/strategies/momentum/moving_average_crossover.py
"""
NEXUS AI TRADING SYSTEM - Moving Average Crossover Strategy
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
class MovingAverageCrossoverConfig:
    """Configuration pour Moving Average Crossover Strategy"""
    symbol: str = "BTC-USD"
    fast_period: int = 50
    slow_period: int = 200
    entry_threshold: float = 0.0
    exit_threshold: float = 0.0
    use_volume_filter: bool = False
    volume_threshold: float = 1.5
    use_trend_filter: bool = True
    trend_period: int = 50
    position_size: float = 1.0
    stop_loss: float = 0.02
    take_profit: float = 0.05
    fee_rate: float = 0.001

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'fast_period': self.fast_period,
            'slow_period': self.slow_period,
            'entry_threshold': self.entry_threshold,
            'exit_threshold': self.exit_threshold,
            'use_volume_filter': self.use_volume_filter,
            'volume_threshold': self.volume_threshold,
            'use_trend_filter': self.use_trend_filter,
            'trend_period': self.trend_period,
            'position_size': self.position_size,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'fee_rate': self.fee_rate,
        }


@dataclass
class CrossSignal:
    """Signal de trading"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    fast_ma: float
    slow_ma: float
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'fast_ma': self.fast_ma,
            'slow_ma': self.slow_ma,
            'confidence': self.confidence,
            'reason': self.reason,
        }


class MovingAverageCrossoverStrategy:
    """
    Stratégie de crossover de moyennes mobiles.

    Features:
    - Multiple moving averages
    - Crossover detection
    - Volume filter
    - Trend filter
    - Position management

    Example:
        ```python
        config = MovingAverageCrossoverConfig(
            symbol='BTC-USD',
            fast_period=50,
            slow_period=200
        )
        strategy = MovingAverageCrossoverStrategy(config)

        # Update with data
        signal = strategy.update(price_data)
        ```
    """

    def __init__(self, config: Optional[MovingAverageCrossoverConfig] = None):
        self.config = config or MovingAverageCrossoverConfig()
        self.data: pd.DataFrame = pd.DataFrame()
        self.fast_ma: List[float] = []
        self.slow_ma: List[float] = []
        self.position: int = 0
        self.position_entry_price: float = 0.0
        self.position_entry_time: Optional[datetime] = None
        self.signals: List[CrossSignal] = []
        self.trade_history: List[Dict[str, Any]] = []

        logger.info(f"MovingAverageCrossoverStrategy initialisé pour {self.config.symbol}")

    def update(self, data: pd.DataFrame) -> Optional[CrossSignal]:
        """
        Met à jour la stratégie avec de nouvelles données.

        Args:
            data: DataFrame avec colonnes 'timestamp' et 'close'

        Returns:
            Optional[CrossSignal]: Signal généré
        """
        self.data = data

        if len(data) < self.config.slow_period:
            return None

        # Calcul des moyennes mobiles
        self._calculate_moving_averages()

        # Prix actuel
        current_price = data['close'].iloc[-1]

        # Génération du signal
        signal = self._generate_signal()

        if signal:
            self.signals.append(signal)

            # Gestion de la position
            if signal.signal_type in ['buy', 'sell']:
                self._open_position(signal)
            elif signal.signal_type == 'exit':
                self._close_position(signal)

        return signal

    def _calculate_moving_averages(self) -> None:
        """Calcule les moyennes mobiles"""
        close = self.data['close'].values

        # Moyenne mobile rapide
        self.fast_ma = self._calculate_sma(close, self.config.fast_period)

        # Moyenne mobile lente
        self.slow_ma = self._calculate_sma(close, self.config.slow_period)

    def _calculate_sma(self, data: np.ndarray, period: int) -> List[float]:
        """Calcule la SMA"""
        sma = []
        for i in range(len(data)):
            if i < period - 1:
                sma.append(data[i])
            else:
                sma.append(np.mean(data[i-period+1:i+1]))
        return sma

    def _generate_signal(self) -> Optional[CrossSignal]:
        """
        Génère un signal de trading.

        Returns:
            Optional[CrossSignal]: Signal généré
        """
        if len(self.fast_ma) < 2 or len(self.slow_ma) < 2:
            return None

        current_fast = self.fast_ma[-1]
        current_slow = self.slow_ma[-1]
        previous_fast = self.fast_ma[-2]
        previous_slow = self.slow_ma[-2]
        current_price = self.data['close'].iloc[-1]

        # Filtre volume
        if self.config.use_volume_filter:
            volume = self.data['volume'].iloc[-1] if 'volume' in self.data.columns else 1
            avg_volume = np.mean(self.data['volume'].values[-20:]) if 'volume' in self.data.columns else 1
            if volume / avg_volume < self.config.volume_threshold:
                return None

        # Filtre tendance
        if self.config.use_trend_filter:
            trend = self._get_trend()
            if trend == 'bearish' and current_fast > current_slow:
                return None
            if trend == 'bullish' and current_fast < current_slow:
                return None

        if self.position == 0:
            # Pas de position ouverte
            # Crossover haussier
            if previous_fast <= previous_slow and current_fast > current_slow:
                if abs(current_fast - current_slow) > self.config.entry_threshold:
                    return self._create_buy_signal(current_price)

            # Crossover baissier
            elif previous_fast >= previous_slow and current_fast < current_slow:
                if abs(current_fast - current_slow) > self.config.entry_threshold:
                    return self._create_sell_signal(current_price)

        else:
            # Position ouverte
            duration = (datetime.now() - self.position_entry_time).days if self.position_entry_time else 0

            # Stop loss
            if self.position > 0:
                pnl_percent = (current_price - self.position_entry_price) / self.position_entry_price
                if pnl_percent < -self.config.stop_loss:
                    return self._create_exit_signal(current_price, "stop_loss")
                if pnl_percent > self.config.take_profit:
                    return self._create_exit_signal(current_price, "take_profit")

                # Sortie sur croisement baissier
                if previous_fast >= previous_slow and current_fast < current_slow:
                    if abs(current_fast - current_slow) > self.config.exit_threshold:
                        return self._create_exit_signal(current_price, "bearish_crossover")

            elif self.position < 0:
                pnl_percent = (self.position_entry_price - current_price) / self.position_entry_price
                if pnl_percent < -self.config.stop_loss:
                    return self._create_exit_signal(current_price, "stop_loss")
                if pnl_percent > self.config.take_profit:
                    return self._create_exit_signal(current_price, "take_profit")

                # Sortie sur croisement haussier
                if previous_fast <= previous_slow and current_fast > current_slow:
                    if abs(current_fast - current_slow) > self.config.exit_threshold:
                        return self._create_exit_signal(current_price, "bullish_crossover")

        return None

    def _get_trend(self) -> str:
        """
        Détermine la tendance actuelle.

        Returns:
            str: 'bullish', 'bearish', 'neutral'
        """
        if len(self.data) < self.config.trend_period:
            return 'neutral'

        close = self.data['close'].values
        sma = np.mean(close[-self.config.trend_period:])
        current_price = close[-1]

        if current_price > sma * 1.01:
            return 'bullish'
        elif current_price < sma * 0.99:
            return 'bearish'
        else:
            return 'neutral'

    def _create_buy_signal(self, price: float) -> CrossSignal:
        """Crée un signal d'achat"""
        confidence = self._calculate_confidence()
        return CrossSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='buy',
            price=price,
            fast_ma=self.fast_ma[-1],
            slow_ma=self.slow_ma[-1],
            confidence=confidence,
            reason="golden_cross",
        )

    def _create_sell_signal(self, price: float) -> CrossSignal:
        """Crée un signal de vente"""
        confidence = self._calculate_confidence()
        return CrossSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='sell',
            price=price,
            fast_ma=self.fast_ma[-1],
            slow_ma=self.slow_ma[-1],
            confidence=confidence,
            reason="death_cross",
        )

    def _create_exit_signal(self, price: float, reason: str) -> CrossSignal:
        """Crée un signal de sortie"""
        return CrossSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='exit',
            price=price,
            fast_ma=self.fast_ma[-1],
            slow_ma=self.slow_ma[-1],
            confidence=0.8,
            reason=reason,
        )

    def _calculate_confidence(self) -> float:
        """Calcule le niveau de confiance"""
        if len(self.fast_ma) < 2 or len(self.slow_ma) < 2:
            return 0.5

        crossover_strength = abs(self.fast_ma[-1] - self.slow_ma[-1])
        avg_value = (abs(self.fast_ma[-1]) + abs(self.slow_ma[-1])) / 2

        if avg_value > 0:
            confidence = min(1.0, crossover_strength / avg_value)
        else:
            confidence = 0.5

        return confidence

    def _open_position(self, signal: CrossSignal) -> None:
        """Ouvre une position"""
        if signal.signal_type == 'buy':
            self.position = self.config.position_size
        elif signal.signal_type == 'sell':
            self.position = -self.config.position_size

        self.position_entry_price = signal.price
        self.position_entry_time = signal.timestamp

        logger.info(f"Position ouverte: {signal.signal_type} @ {signal.price:.2f}")

    def _close_position(self, signal: CrossSignal) -> None:
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
        }


def create_moving_average_crossover(
    symbol: str = "BTC-USD",
    fast_period: int = 50,
    slow_period: int = 200,
    **kwargs
) -> MovingAverageCrossoverStrategy:
    """
    Factory pour créer une stratégie de crossover de moyennes mobiles.

    Args:
        symbol: Symbole
        fast_period: Période rapide
        slow_period: Période lente
        **kwargs: Arguments supplémentaires

    Returns:
        MovingAverageCrossoverStrategy: Stratégie de crossover
    """
    config = MovingAverageCrossoverConfig(
        symbol=symbol,
        fast_period=fast_period,
        slow_period=slow_period,
        **kwargs
    )
    return MovingAverageCrossoverStrategy(config)


__all__ = [
    'MovingAverageCrossoverStrategy',
    'MovingAverageCrossoverConfig',
    'CrossSignal',
    'create_moving_average_crossover',
]
