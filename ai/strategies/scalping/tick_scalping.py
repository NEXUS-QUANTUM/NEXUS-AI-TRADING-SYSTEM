# ai/strategies/scalping/tick_scalping.py
"""
NEXUS AI TRADING SYSTEM - Tick Scalping Strategy
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
class TickData:
    """Données de tick"""
    symbol: str
    price: float
    volume: float
    timestamp: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None
    trade_type: str = "trade"  # 'trade', 'bid', 'ask'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'price': self.price,
            'volume': self.volume,
            'timestamp': self.timestamp.isoformat(),
            'bid': self.bid,
            'ask': self.ask,
            'trade_type': self.trade_type,
        }


@dataclass
class TickSignal:
    """Signal de scalping sur ticks"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    volume: float
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'volume': self.volume,
            'confidence': self.confidence,
            'reason': self.reason,
        }


@dataclass
class TickScalpingConfig:
    """Configuration pour Tick Scalping"""
    symbol: str = "BTC-USD"
    tick_window: int = 100
    volume_threshold: float = 100.0
    price_change_threshold: float = 0.001
    momentum_threshold: float = 0.5
    position_size: float = 1.0
    max_position: float = 10.0
    take_profit: float = 0.001
    stop_loss: float = 0.002
    max_holding_time: float = 30.0
    min_trade_interval: float = 1.0
    fee_rate: float = 0.001
    update_interval: float = 0.01

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'tick_window': self.tick_window,
            'volume_threshold': self.volume_threshold,
            'price_change_threshold': self.price_change_threshold,
            'momentum_threshold': self.momentum_threshold,
            'position_size': self.position_size,
            'max_position': self.max_position,
            'take_profit': self.take_profit,
            'stop_loss': self.stop_loss,
            'max_holding_time': self.max_holding_time,
            'min_trade_interval': self.min_trade_interval,
            'fee_rate': self.fee_rate,
            'update_interval': self.update_interval,
        }


class TickScalpingStrategy:
    """
    Stratégie de scalping sur ticks.

    Features:
    - Tick-by-tick analysis
    - Volume momentum
    - Price action detection
    - Fast execution
    - Micro-trend identification

    Example:
        ```python
        config = TickScalpingConfig(
            symbol='BTC-USD',
            tick_window=100,
            volume_threshold=100.0
        )
        strategy = TickScalpingStrategy(config)

        # Update with tick data
        signal = strategy.update(tick_data)
        ```
    """

    def __init__(self, config: Optional[TickScalpingConfig] = None):
        self.config = config or TickScalpingConfig()
        self.tick_history: List[TickData] = []
        self.position: float = 0.0
        self.position_entry_price: float = 0.0
        self.position_entry_time: Optional[datetime] = None
        self.signals: List[TickSignal] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.prices: List[float] = []
        self.volumes: List[float] = []
        self.momentum: float = 0.0
        self.volume_momentum: float = 0.0
        self.last_trade_time: Optional[datetime] = None

        logger.info(f"TickScalpingStrategy initialisé pour {self.config.symbol}")

    def update(self, tick_data: TickData) -> Optional[TickSignal]:
        """
        Met à jour la stratégie avec un nouveau tick.

        Args:
            tick_data: Données de tick

        Returns:
            Optional[TickSignal]: Signal généré
        """
        self.tick_history.append(tick_data)
        self.prices.append(tick_data.price)
        self.volumes.append(tick_data.volume)

        # Garder seulement la fenêtre configurée
        if len(self.prices) > self.config.tick_window:
            self.prices = self.prices[-self.config.tick_window:]
            self.volumes = self.volumes[-self.config.tick_window:]

        # Calcul des indicateurs
        self._calculate_momentum()
        self._calculate_volume_momentum()

        # Génération du signal
        signal = self._generate_signal(tick_data)

        if signal:
            self.signals.append(signal)

            # Gestion de la position
            if signal.signal_type in ['buy', 'sell']:
                if self._can_trade():
                    self._open_position(signal)
            elif signal.signal_type == 'exit':
                self._close_position(signal)

        # Gestion de la position ouverte
        if self.position != 0:
            self._manage_position(tick_data)

        return signal

    def _calculate_momentum(self) -> None:
        """Calcule le momentum des prix"""
        if len(self.prices) < 2:
            self.momentum = 0.0
            return

        # Momentum = prix actuel - prix il y a N ticks
        lookback = min(10, len(self.prices) - 1)
        self.momentum = (self.prices[-1] - self.prices[-lookback]) / self.prices[-lookback]

    def _calculate_volume_momentum(self) -> None:
        """Calcule le momentum des volumes"""
        if len(self.volumes) < 2:
            self.volume_momentum = 0.0
            return

        # Volume momentum = volume moyen récent / volume moyen passé
        recent_volume = np.mean(self.volumes[-5:]) if len(self.volumes) >= 5 else np.mean(self.volumes)
        past_volume = np.mean(self.volumes[-20:-5]) if len(self.volumes) >= 20 else recent_volume

        if past_volume > 0:
            self.volume_momentum = recent_volume / past_volume
        else:
            self.volume_momentum = 1.0

    def _generate_signal(self, tick_data: TickData) -> Optional[TickSignal]:
        """
        Génère un signal de trading.

        Args:
            tick_data: Données de tick

        Returns:
            Optional[TickSignal]: Signal généré
        """
        if len(self.prices) < 5:
            return None

        current_price = tick_data.price
        current_volume = tick_data.volume

        # Pas de position ouverte
        if self.position == 0:
            # Signal d'achat: momentum haussier avec volume
            if (self.momentum > self.config.price_change_threshold and
                self.volume_momentum > self.config.momentum_threshold and
                current_volume > self.config.volume_threshold):

                return TickSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='buy',
                    price=current_price,
                    volume=current_volume,
                    confidence=self._calculate_confidence(),
                    reason="bullish_momentum_volume",
                )

            # Signal de vente: momentum baissier avec volume
            elif (self.momentum < -self.config.price_change_threshold and
                  self.volume_momentum > self.config.momentum_threshold and
                  current_volume > self.config.volume_threshold):

                return TickSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='sell',
                    price=current_price,
                    volume=current_volume,
                    confidence=self._calculate_confidence(),
                    reason="bearish_momentum_volume",
                )

            # Signal d'achat: cassure de niveau
            elif self._detect_breakout():
                return TickSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='buy',
                    price=current_price,
                    volume=current_volume,
                    confidence=self._calculate_confidence() * 0.8,
                    reason="breakout",
                )

        else:
            # Position ouverte
            # Take profit
            if self.position > 0:
                pnl_percent = (current_price - self.position_entry_price) / self.position_entry_price
                if pnl_percent >= self.config.take_profit:
                    return self._create_exit_signal(tick_data, "take_profit")

                if pnl_percent <= -self.config.stop_loss:
                    return self._create_exit_signal(tick_data, "stop_loss")

                # Sortie sur momentum reversal
                if self.momentum < -self.config.price_change_threshold:
                    return self._create_exit_signal(tick_data, "momentum_reversal")

            elif self.position < 0:
                pnl_percent = (self.position_entry_price - current_price) / self.position_entry_price
                if pnl_percent >= self.config.take_profit:
                    return self._create_exit_signal(tick_data, "take_profit")

                if pnl_percent <= -self.config.stop_loss:
                    return self._create_exit_signal(tick_data, "stop_loss")

                if self.momentum > self.config.price_change_threshold:
                    return self._create_exit_signal(tick_data, "momentum_reversal")

            # Max holding time
            if self.position_entry_time:
                holding_time = (datetime.now() - self.position_entry_time).total_seconds()
                if holding_time >= self.config.max_holding_time:
                    return self._create_exit_signal(tick_data, "max_holding_time")

        return None

    def _detect_breakout(self) -> bool:
        """Détecte une cassure de niveau"""
        if len(self.prices) < 20:
            return False

        # Résistance/support récent
        recent_prices = self.prices[-20:]
        resistance = np.max(recent_prices)
        support = np.min(recent_prices)

        current_price = self.prices[-1]

        # Cassure de résistance avec volume
        if current_price > resistance * 1.001:
            if self.volumes[-1] > np.mean(self.volumes[-20:]) * 1.5:
                return True

        # Cassure de support avec volume
        if current_price < support * 0.999:
            if self.volumes[-1] > np.mean(self.volumes[-20:]) * 1.5:
                return True

        return False

    def _can_trade(self) -> bool:
        """Vérifie si on peut trader"""
        if self.last_trade_time is None:
            return True

        elapsed = (datetime.now() - self.last_trade_time).total_seconds()
        return elapsed >= self.config.min_trade_interval

    def _calculate_confidence(self) -> float:
        """Calcule le niveau de confiance"""
        factors = []

        # Momentum strength
        momentum_strength = min(1.0, abs(self.momentum) / (self.config.price_change_threshold * 2))
        factors.append(momentum_strength)

        # Volume strength
        volume_strength = min(1.0, self.volume_momentum / (self.config.momentum_threshold * 2))
        factors.append(volume_strength)

        # Recent trend
        if len(self.prices) > 10:
            trend = np.polyfit(range(10), self.prices[-10:], 1)[0]
            trend_strength = min(1.0, abs(trend) / (self.config.price_change_threshold * 5))
            factors.append(trend_strength)

        return np.mean(factors)

    def _create_exit_signal(self, tick_data: TickData, reason: str) -> TickSignal:
        """Crée un signal de sortie"""
        return TickSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='exit',
            price=tick_data.price,
            volume=tick_data.volume,
            confidence=0.8,
            reason=reason,
        )

    def _open_position(self, signal: TickSignal) -> None:
        """Ouvre une position"""
        if signal.signal_type == 'buy':
            self.position = self.config.position_size
        elif signal.signal_type == 'sell':
            self.position = -self.config.position_size

        self.position_entry_price = signal.price
        self.position_entry_time = signal.timestamp
        self.last_trade_time = signal.timestamp

        logger.info(f"Position ouverte: {signal.signal_type} @ {signal.price:.2f} (volume: {signal.volume:.2f})")

    def _close_position(self, signal: TickSignal) -> None:
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
            'holding_time': (signal.timestamp - self.position_entry_time).total_seconds() if self.position_entry_time else 0,
            'pnl': pnl,
            'fees': fees,
            'net_pnl': net_pnl,
            'signal': signal.to_dict(),
        }

        self.trade_history.append(trade)

        logger.info(f"Position fermée: P&L={net_pnl:.2f}")

        # Reset position
        self.position = 0.0
        self.position_entry_price = 0.0
        self.position_entry_time = None

    def _manage_position(self, tick_data: TickData) -> None:
        """Gère la position ouverte"""
        # Trailing stop
        if self.position != 0:
            current_price = tick_data.price

            if self.position > 0:
                if current_price > self.position_entry_price:
                    new_stop = current_price * (1 - self.config.stop_loss)
                    if new_stop > self.position_entry_price * (1 - self.config.stop_loss):
                        self.position_entry_price = new_stop

            elif self.position < 0:
                if current_price < self.position_entry_price:
                    new_stop = current_price * (1 + self.config.stop_loss)
                    if new_stop < self.position_entry_price * (1 + self.config.stop_loss):
                        self.position_entry_price = new_stop

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
                'avg_holding_time': 0.0,
            }

        pnls = [t['net_pnl'] for t in self.trade_history]
        wins = [p for p in pnls if p > 0]
        holding_times = [t['holding_time'] for t in self.trade_history]

        return {
            'total_trades': len(self.trade_history),
            'total_pnl': sum(pnls),
            'win_rate': len(wins) / len(pnls) if pnls else 0.0,
            'avg_pnl': np.mean(pnls) if pnls else 0.0,
            'max_pnl': max(pnls) if pnls else 0.0,
            'min_pnl': min(pnls) if pnls else 0.0,
            'avg_holding_time': np.mean(holding_times) if holding_times else 0.0,
        }


def create_tick_scalping(
    symbol: str = "BTC-USD",
    tick_window: int = 100,
    volume_threshold: float = 100.0,
    **kwargs
) -> TickScalpingStrategy:
    """
    Factory pour créer une stratégie de scalping sur ticks.

    Args:
        symbol: Symbole
        tick_window: Fenêtre de ticks
        volume_threshold: Seuil de volume
        **kwargs: Arguments supplémentaires

    Returns:
        TickScalpingStrategy: Stratégie de scalping sur ticks
    """
    config = TickScalpingConfig(
        symbol=symbol,
        tick_window=tick_window,
        volume_threshold=volume_threshold,
        **kwargs
    )
    return TickScalpingStrategy(config)


__all__ = [
    'TickScalpingStrategy',
    'TickScalpingConfig',
    'TickData',
    'TickSignal',
    'create_tick_scalping',
]
