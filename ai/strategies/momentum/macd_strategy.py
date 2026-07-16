# ai/strategies/momentum/macd_strategy.py
"""
NEXUS AI TRADING SYSTEM - MACD Momentum Strategy
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
class MACDConfig:
    """Configuration pour MACD Strategy"""
    symbol: str = "BTC-USD"
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    entry_threshold: float = 0.0
    exit_threshold: float = 0.0
    use_histogram: bool = True
    use_divergence: bool = True
    use_trend_filter: bool = True
    trend_period: int = 200
    position_size: float = 1.0
    stop_loss: float = 0.02
    take_profit: float = 0.05
    fee_rate: float = 0.001

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'fast_period': self.fast_period,
            'slow_period': self.slow_period,
            'signal_period': self.signal_period,
            'entry_threshold': self.entry_threshold,
            'exit_threshold': self.exit_threshold,
            'use_histogram': self.use_histogram,
            'use_divergence': self.use_divergence,
            'use_trend_filter': self.use_trend_filter,
            'trend_period': self.trend_period,
            'position_size': self.position_size,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'fee_rate': self.fee_rate,
        }


@dataclass
class MACDSignal:
    """Signal de trading MACD"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    macd: float
    signal: float
    histogram: float
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'macd': self.macd,
            'signal': self.signal,
            'histogram': self.histogram,
            'confidence': self.confidence,
            'reason': self.reason,
        }


@dataclass
class Divergence:
    """Divergence détectée"""
    type: str
    price_highs: List[float]
    price_lows: List[float]
    indicator_highs: List[float]
    indicator_lows: List[float]
    confidence: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
        }


class MACDStrategy:
    """
    Stratégie de momentum basée sur MACD.

    Features:
    - MACD calculation
    - Signal line crossovers
    - Histogram analysis
    - Divergence detection
    - Trend filter

    Example:
        ```python
        config = MACDConfig(
            symbol='BTC-USD',
            fast_period=12,
            slow_period=26,
            signal_period=9
        )
        strategy = MACDStrategy(config)

        # Update with data
        signal = strategy.update(price_data)
        ```
    """

    def __init__(self, config: Optional[MACDConfig] = None):
        self.config = config or MACDConfig()
        self.data: pd.DataFrame = pd.DataFrame()
        self.macd: List[float] = []
        self.signal: List[float] = []
        self.histogram: List[float] = []
        self.position: int = 0
        self.position_entry_price: float = 0.0
        self.position_entry_time: Optional[datetime] = None
        self.signals: List[MACDSignal] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.divergences: List[Divergence] = []

        logger.info(f"MACDStrategy initialisé pour {self.config.symbol}")

    def update(self, data: pd.DataFrame) -> Optional[MACDSignal]:
        """
        Met à jour la stratégie avec de nouvelles données.

        Args:
            data: DataFrame avec colonnes 'timestamp' et 'close'

        Returns:
            Optional[MACDSignal]: Signal généré
        """
        self.data = data

        if len(data) < self.config.slow_period:
            return None

        # Calcul du MACD
        self._calculate_macd()

        # Prix actuel
        current_price = data['close'].iloc[-1]

        # Détection de divergence
        if self.config.use_divergence:
            self._detect_divergences()

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

    def _calculate_macd(self) -> None:
        """Calcule le MACD"""
        close = self.data['close'].values

        # EMA rapide et lente
        fast_ema = self._calculate_ema(close, self.config.fast_period)
        slow_ema = self._calculate_ema(close, self.config.slow_period)

        # MACD
        self.macd = fast_ema - slow_ema

        # Signal line
        self.signal = self._calculate_ema(self.macd, self.config.signal_period)

        # Histogram
        self.histogram = np.array(self.macd) - np.array(self.signal)

    def _calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calcule l'EMA"""
        alpha = 2 / (period + 1)
        ema = np.zeros(len(data))
        ema[0] = data[0]

        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]

        return ema

    def _detect_divergences(self) -> None:
        """Détecte les divergences"""
        if len(self.macd) < 20:
            return

        # Détection des extremums
        price = self.data['close'].values[-20:]
        macd = self.macd[-20:]

        # Divergence haussière
        if self._is_bullish_divergence(price, macd):
            divergence = Divergence(
                type='bullish',
                price_highs=[],
                price_lows=[],
                indicator_highs=[],
                indicator_lows=[],
                confidence=0.7,
                timestamp=datetime.now(),
            )
            self.divergences.append(divergence)

        # Divergence baissière
        if self._is_bearish_divergence(price, macd):
            divergence = Divergence(
                type='bearish',
                price_highs=[],
                price_lows=[],
                indicator_highs=[],
                indicator_lows=[],
                confidence=0.7,
                timestamp=datetime.now(),
            )
            self.divergences.append(divergence)

    def _is_bullish_divergence(self, price: np.ndarray, macd: np.ndarray) -> bool:
        """Vérifie une divergence haussière"""
        price_lows = self._find_lows(price)
        macd_lows = self._find_lows(macd)

        if len(price_lows) >= 2 and len(macd_lows) >= 2:
            if price_lows[-1] < price_lows[-2] and macd_lows[-1] > macd_lows[-2]:
                return True

        return False

    def _is_bearish_divergence(self, price: np.ndarray, macd: np.ndarray) -> bool:
        """Vérifie une divergence baissière"""
        price_highs = self._find_highs(price)
        macd_highs = self._find_highs(macd)

        if len(price_highs) >= 2 and len(macd_highs) >= 2:
            if price_highs[-1] > price_highs[-2] and macd_highs[-1] < macd_highs[-2]:
                return True

        return False

    def _find_lows(self, data: np.ndarray) -> List[float]:
        """Trouve les minimums locaux"""
        lows = []
        for i in range(1, len(data) - 1):
            if data[i] < data[i-1] and data[i] < data[i+1]:
                lows.append(data[i])
        return lows

    def _find_highs(self, data: np.ndarray) -> List[float]:
        """Trouve les maximums locaux"""
        highs = []
        for i in range(1, len(data) - 1):
            if data[i] > data[i-1] and data[i] > data[i+1]:
                highs.append(data[i])
        return highs

    def _generate_signal(self) -> Optional[MACDSignal]:
        """
        Génère un signal de trading.

        Returns:
            Optional[MACDSignal]: Signal généré
        """
        if len(self.macd) < 2:
            return None

        current_macd = self.macd[-1]
        current_signal = self.signal[-1]
        current_histogram = self.histogram[-1]
        previous_macd = self.macd[-2]
        previous_signal = self.signal[-2]
        previous_histogram = self.histogram[-2]
        current_price = self.data['close'].iloc[-1]

        # Trend filter
        if self.config.use_trend_filter:
            trend = self._get_trend()
            if trend == 'bearish' and current_macd > 0:
                return None
            if trend == 'bullish' and current_macd < 0:
                return None

        if self.position == 0:
            # Pas de position ouverte
            # Crossover haussier
            if previous_macd <= previous_signal and current_macd > current_signal:
                if self.config.use_histogram:
                    if previous_histogram <= 0 and current_histogram > 0:
                        return self._create_buy_signal(current_price)

                return self._create_buy_signal(current_price)

            # Crossover baissier
            elif previous_macd >= previous_signal and current_macd < current_signal:
                if self.config.use_histogram:
                    if previous_histogram >= 0 and current_histogram < 0:
                        return self._create_sell_signal(current_price)

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
                if previous_macd <= previous_signal and current_macd > current_signal:
                    if abs(current_macd - current_signal) > self.config.exit_threshold:
                        return self._create_exit_signal(current_price, "bearish_crossover")

            elif self.position < 0:
                pnl_percent = (self.position_entry_price - current_price) / self.position_entry_price
                if pnl_percent < -self.config.stop_loss:
                    return self._create_exit_signal(current_price, "stop_loss")
                if pnl_percent > self.config.take_profit:
                    return self._create_exit_signal(current_price, "take_profit")

                # Sortie sur croisement haussier
                if previous_macd >= previous_signal and current_macd < current_signal:
                    if abs(current_macd - current_signal) > self.config.exit_threshold:
                        return self._create_exit_signal(current_price, "bullish_crossover")

            # Sortie sur divergence
            if self.config.use_divergence and self.divergences:
                latest_div = self.divergences[-1]
                if self.position > 0 and latest_div.type == 'bearish':
                    return self._create_exit_signal(current_price, "bearish_divergence")
                elif self.position < 0 and latest_div.type == 'bullish':
                    return self._create_exit_signal(current_price, "bullish_divergence")

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

    def _create_buy_signal(self, price: float) -> MACDSignal:
        """Crée un signal d'achat"""
        confidence = self._calculate_confidence()
        return MACDSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='buy',
            price=price,
            macd=self.macd[-1],
            signal=self.signal[-1],
            histogram=self.histogram[-1],
            confidence=confidence,
            reason="bullish_crossover",
        )

    def _create_sell_signal(self, price: float) -> MACDSignal:
        """Crée un signal de vente"""
        confidence = self._calculate_confidence()
        return MACDSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='sell',
            price=price,
            macd=self.macd[-1],
            signal=self.signal[-1],
            histogram=self.histogram[-1],
            confidence=confidence,
            reason="bearish_crossover",
        )

    def _create_exit_signal(self, price: float, reason: str) -> MACDSignal:
        """Crée un signal de sortie"""
        return MACDSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='exit',
            price=price,
            macd=self.macd[-1],
            signal=self.signal[-1],
            histogram=self.histogram[-1],
            confidence=0.8,
            reason=reason,
        )

    def _calculate_confidence(self) -> float:
        """Calcule le niveau de confiance"""
        # Basé sur la force du croisement
        if len(self.macd) < 2:
            return 0.5

        crossover_strength = abs(self.macd[-1] - self.signal[-1])
        max_strength = abs(self.macd[-1]) + abs(self.signal[-1])

        if max_strength > 0:
            confidence = min(1.0, crossover_strength / max_strength)
        else:
            confidence = 0.5

        return confidence

    def _open_position(self, signal: MACDSignal) -> None:
        """Ouvre une position"""
        if signal.signal_type == 'buy':
            self.position = self.config.position_size
        elif signal.signal_type == 'sell':
            self.position = -self.config.position_size

        self.position_entry_price = signal.price
        self.position_entry_time = signal.timestamp

        logger.info(f"Position ouverte: {signal.signal_type} @ {signal.price:.2f}")

    def _close_position(self, signal: MACDSignal) -> None:
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


def create_macd_strategy(
    symbol: str = "BTC-USD",
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    **kwargs
) -> MACDStrategy:
    """
    Factory pour créer une stratégie MACD.

    Args:
        symbol: Symbole
        fast_period: Période rapide
        slow_period: Période lente
        signal_period: Période du signal
        **kwargs: Arguments supplémentaires

    Returns:
        MACDStrategy: Stratégie MACD
    """
    config = MACDConfig(
        symbol=symbol,
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
        **kwargs
    )
    return MACDStrategy(config)


__all__ = [
    'MACDStrategy',
    'MACDConfig',
    'MACDSignal',
    'Divergence',
    'create_macd_strategy',
]
