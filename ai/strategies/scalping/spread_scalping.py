# ai/strategies/scalping/spread_scalping.py
"""
NEXUS AI TRADING SYSTEM - Spread Scalping Strategy
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
class SpreadData:
    """Données de spread"""
    symbol: str
    bid: float
    ask: float
    spread: float
    spread_percent: float
    mid_price: float
    timestamp: datetime
    bid_volume: float
    ask_volume: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'bid': self.bid,
            'ask': self.ask,
            'spread': self.spread,
            'spread_percent': self.spread_percent,
            'mid_price': self.mid_price,
            'timestamp': self.timestamp.isoformat(),
            'bid_volume': self.bid_volume,
            'ask_volume': self.ask_volume,
        }


@dataclass
class SpreadSignal:
    """Signal de trading basé sur le spread"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    spread: float
    spread_percent: float
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'spread': self.spread,
            'spread_percent': self.spread_percent,
            'confidence': self.confidence,
            'reason': self.reason,
        }


@dataclass
class SpreadScalpingConfig:
    """Configuration pour Spread Scalping"""
    symbol: str = "BTC-USD"
    min_spread: float = 0.001
    max_spread: float = 0.01
    spread_ma_period: int = 10
    spread_std_period: int = 20
    entry_zscore: float = 2.0
    exit_zscore: float = 0.5
    position_size: float = 1.0
    max_position: float = 10.0
    take_profit: float = 0.001
    stop_loss: float = 0.002
    max_holding_time: float = 60.0
    fee_rate: float = 0.001
    update_interval: float = 0.1

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'min_spread': self.min_spread,
            'max_spread': self.max_spread,
            'spread_ma_period': self.spread_ma_period,
            'spread_std_period': self.spread_std_period,
            'entry_zscore': self.entry_zscore,
            'exit_zscore': self.exit_zscore,
            'position_size': self.position_size,
            'max_position': self.max_position,
            'take_profit': self.take_profit,
            'stop_loss': self.stop_loss,
            'max_holding_time': self.max_holding_time,
            'fee_rate': self.fee_rate,
            'update_interval': self.update_interval,
        }


class SpreadScalpingStrategy:
    """
    Stratégie de scalping basée sur le spread.

    Features:
    - Spread analysis
    - Z-score detection
    - Mean reversion on spreads
    - Volume-weighted execution
    - Fast position management

    Example:
        ```python
        config = SpreadScalpingConfig(
            symbol='BTC-USD',
            min_spread=0.001,
            max_spread=0.01,
            entry_zscore=2.0
        )
        strategy = SpreadScalpingStrategy(config)

        # Update with spread data
        signal = strategy.update(spread_data)
        ```
    """

    def __init__(self, config: Optional[SpreadScalpingConfig] = None):
        self.config = config or SpreadScalpingConfig()
        self.spread_history: List[SpreadData] = []
        self.position: float = 0.0
        self.position_entry_price: float = 0.0
        self.position_entry_time: Optional[datetime] = None
        self.signals: List[SpreadSignal] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.spread_values: List[float] = []
        self.spread_ma: List[float] = []
        self.spread_std: List[float] = []
        self.z_scores: List[float] = []

        logger.info(f"SpreadScalpingStrategy initialisé pour {self.config.symbol}")

    def update(self, spread_data: SpreadData) -> Optional[SpreadSignal]:
        """
        Met à jour la stratégie avec les données de spread.

        Args:
            spread_data: Données de spread

        Returns:
            Optional[SpreadSignal]: Signal généré
        """
        self.spread_history.append(spread_data)
        self.spread_values.append(spread_data.spread_percent)

        # Calcul des indicateurs
        self._calculate_indicators()

        # Génération du signal
        signal = self._generate_signal(spread_data)

        if signal:
            self.signals.append(signal)

            # Gestion de la position
            if signal.signal_type in ['buy', 'sell']:
                self._open_position(signal)
            elif signal.signal_type == 'exit':
                self._close_position(signal)

        # Gestion de la position ouverte
        if self.position != 0:
            self._manage_position(spread_data)

        return signal

    def _calculate_indicators(self) -> None:
        """Calcule les indicateurs de spread"""
        if len(self.spread_values) < self.config.spread_ma_period:
            return

        # Moyenne mobile
        ma = np.mean(self.spread_values[-self.config.spread_ma_period:])
        self.spread_ma.append(ma)

        # Écart-type
        if len(self.spread_values) >= self.config.spread_std_period:
            std = np.std(self.spread_values[-self.config.spread_std_period:])
            self.spread_std.append(std)

            # Z-score
            z_score = (self.spread_values[-1] - ma) / std if std > 0 else 0
            self.z_scores.append(z_score)

    def _generate_signal(self, spread_data: SpreadData) -> Optional[SpreadSignal]:
        """
        Génère un signal de trading.

        Args:
            spread_data: Données de spread

        Returns:
            Optional[SpreadSignal]: Signal généré
        """
        if len(self.z_scores) == 0:
            return None

        current_spread = spread_data.spread_percent
        current_z = self.z_scores[-1]

        # Vérification des conditions
        if current_spread < self.config.min_spread:
            return None

        if current_spread > self.config.max_spread:
            return None

        if self.position == 0:
            # Pas de position ouverte
            # Spread trop large -> vente
            if current_z > self.config.entry_zscore:
                return SpreadSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='sell',
                    price=spread_data.bid,
                    spread=spread_data.spread,
                    spread_percent=current_spread,
                    confidence=self._calculate_confidence(current_z),
                    reason="spread_wide",
                )

            # Spread trop étroit -> achat
            elif current_z < -self.config.entry_zscore:
                return SpreadSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='buy',
                    price=spread_data.ask,
                    spread=spread_data.spread,
                    spread_percent=current_spread,
                    confidence=self._calculate_confidence(current_z),
                    reason="spread_narrow",
                )

        else:
            # Position ouverte
            # Sortie lorsque le spread revient à la moyenne
            if abs(current_z) < self.config.exit_zscore:
                return self._create_exit_signal(spread_data, "mean_reversion")

            # Stop loss
            if self.position > 0:
                pnl_percent = (spread_data.bid - self.position_entry_price) / self.position_entry_price
                if pnl_percent <= -self.config.stop_loss:
                    return self._create_exit_signal(spread_data, "stop_loss")

                if pnl_percent >= self.config.take_profit:
                    return self._create_exit_signal(spread_data, "take_profit")

            elif self.position < 0:
                pnl_percent = (self.position_entry_price - spread_data.ask) / self.position_entry_price
                if pnl_percent <= -self.config.stop_loss:
                    return self._create_exit_signal(spread_data, "stop_loss")

                if pnl_percent >= self.config.take_profit:
                    return self._create_exit_signal(spread_data, "take_profit")

            # Max holding time
            if self.position_entry_time:
                holding_time = (datetime.now() - self.position_entry_time).total_seconds()
                if holding_time >= self.config.max_holding_time:
                    return self._create_exit_signal(spread_data, "max_holding_time")

        return None

    def _calculate_confidence(self, z_score: float) -> float:
        """
        Calcule le niveau de confiance.

        Args:
            z_score: Z-score

        Returns:
            float: Niveau de confiance (0-1)
        """
        confidence = min(1.0, abs(z_score) / (self.config.entry_zscore * 1.5))
        return confidence

    def _create_exit_signal(self, spread_data: SpreadData, reason: str) -> SpreadSignal:
        """Crée un signal de sortie"""
        return SpreadSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='exit',
            price=spread_data.mid_price,
            spread=spread_data.spread,
            spread_percent=spread_data.spread_percent,
            confidence=0.8,
            reason=reason,
        )

    def _open_position(self, signal: SpreadSignal) -> None:
        """Ouvre une position"""
        if signal.signal_type == 'buy':
            self.position = self.config.position_size
        elif signal.signal_type == 'sell':
            self.position = -self.config.position_size

        self.position_entry_price = signal.price
        self.position_entry_time = signal.timestamp

        logger.info(f"Position ouverte: {signal.signal_type} @ {signal.price:.2f} (spread: {signal.spread_percent:.4f}%)")

    def _close_position(self, signal: SpreadSignal) -> None:
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
            'entry_spread': self._get_entry_spread(),
            'exit_spread': signal.spread_percent,
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

    def _get_entry_spread(self) -> float:
        """Retourne le spread à l'entrée"""
        if self.signals and self.signals[-1]:
            return self.signals[-1].spread_percent
        return 0.0

    def _manage_position(self, spread_data: SpreadData) -> None:
        """Gère la position ouverte"""
        # Implémentation du trailing stop
        if self.position != 0:
            current_price = spread_data.mid_price

            if self.position > 0:
                # Trailing stop pour longue position
                if current_price > self.position_entry_price:
                    new_stop = current_price * (1 - self.config.stop_loss)
                    if new_stop > self.position_entry_price * (1 - self.config.stop_loss):
                        self.position_entry_price = new_stop

            elif self.position < 0:
                # Trailing stop pour courte position
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
                'avg_spread': 0.0,
            }

        pnls = [t['net_pnl'] for t in self.trade_history]
        wins = [p for p in pnls if p > 0]
        spreads = [t['entry_spread'] for t in self.trade_history]

        return {
            'total_trades': len(self.trade_history),
            'total_pnl': sum(pnls),
            'win_rate': len(wins) / len(pnls) if pnls else 0.0,
            'avg_pnl': np.mean(pnls) if pnls else 0.0,
            'max_pnl': max(pnls) if pnls else 0.0,
            'min_pnl': min(pnls) if pnls else 0.0,
            'avg_entry_spread': np.mean(spreads) if spreads else 0.0,
        }


def create_spread_scalping(
    symbol: str = "BTC-USD",
    min_spread: float = 0.001,
    max_spread: float = 0.01,
    entry_zscore: float = 2.0,
    **kwargs
) -> SpreadScalpingStrategy:
    """
    Factory pour créer une stratégie de scalping basée sur le spread.

    Args:
        symbol: Symbole
        min_spread: Spread minimum
        max_spread: Spread maximum
        entry_zscore: Z-score d'entrée
        **kwargs: Arguments supplémentaires

    Returns:
        SpreadScalpingStrategy: Stratégie de scalping sur spread
    """
    config = SpreadScalpingConfig(
        symbol=symbol,
        min_spread=min_spread,
        max_spread=max_spread,
        entry_zscore=entry_zscore,
        **kwargs
    )
    return SpreadScalpingStrategy(config)


__all__ = [
    'SpreadScalpingStrategy',
    'SpreadScalpingConfig',
    'SpreadData',
    'SpreadSignal',
    'create_spread_scalping',
]
