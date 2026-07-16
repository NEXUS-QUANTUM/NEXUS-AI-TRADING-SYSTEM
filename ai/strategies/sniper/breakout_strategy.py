# ai/strategies/sniper/breakout_strategy.py
"""
NEXUS AI TRADING SYSTEM - Breakout Strategy (Sniper)
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
class BreakoutConfig:
    """Configuration pour Breakout Strategy"""
    symbol: str = "BTC-USD"
    lookback_period: int = 20
    breakout_threshold: float = 0.02
    volume_threshold: float = 1.5
    atr_period: int = 14
    atr_multiplier: float = 2.0
    position_size: float = 1.0
    stop_loss_atr: float = 2.0
    take_profit_atr: float = 4.0
    max_holding_time: int = 10
    fee_rate: float = 0.001
    use_false_breakout_filter: bool = True
    false_breakout_threshold: float = 0.01

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'lookback_period': self.lookback_period,
            'breakout_threshold': self.breakout_threshold,
            'volume_threshold': self.volume_threshold,
            'atr_period': self.atr_period,
            'atr_multiplier': self.atr_multiplier,
            'position_size': self.position_size,
            'stop_loss_atr': self.stop_loss_atr,
            'take_profit_atr': self.take_profit_atr,
            'max_holding_time': self.max_holding_time,
            'fee_rate': self.fee_rate,
            'use_false_breakout_filter': self.use_false_breakout_filter,
            'false_breakout_threshold': self.false_breakout_threshold,
        }


@dataclass
class BreakoutSignal:
    """Signal de trading Breakout"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    breakout_level: float
    volume_ratio: float
    atr: float
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'breakout_level': self.breakout_level,
            'volume_ratio': self.volume_ratio,
            'atr': self.atr,
            'confidence': self.confidence,
            'reason': self.reason,
        }


class BreakoutStrategy:
    """
    Stratégie de breakout (Sniper).

    Features:
    - Resistance/support detection
    - Volume confirmation
    - False breakout filter
    - ATR-based risk management
    - Position sizing

    Example:
        ```python
        config = BreakoutConfig(
            symbol='BTC-USD',
            lookback_period=20,
            breakout_threshold=0.02
        )
        strategy = BreakoutStrategy(config)

        # Update with data
        signal = strategy.update(price_data)
        ```
    """

    def __init__(self, config: Optional[BreakoutConfig] = None):
        self.config = config or BreakoutConfig()
        self.data: pd.DataFrame = pd.DataFrame()
        self.position: int = 0
        self.position_entry_price: float = 0.0
        self.position_entry_time: Optional[datetime] = None
        self.signals: List[BreakoutSignal] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.breakout_levels: List[float] = []
        self.false_breakouts: int = 0

        logger.info(f"BreakoutStrategy initialisé pour {self.config.symbol}")

    def update(self, data: pd.DataFrame) -> Optional[BreakoutSignal]:
        """
        Met à jour la stratégie avec de nouvelles données.

        Args:
            data: DataFrame avec colonnes 'high', 'low', 'close', 'volume'

        Returns:
            Optional[BreakoutSignal]: Signal généré
        """
        self.data = data

        if len(data) < self.config.lookback_period:
            return None

        # Calcul des niveaux
        resistance, support = self._calculate_levels()

        # Calcul de l'ATR
        atr = self._calculate_atr()

        # Prix et volume actuels
        current_price = data['close'].iloc[-1]
        current_volume = data['volume'].iloc[-1] if 'volume' in data.columns else 1
        avg_volume = np.mean(data['volume'].values[-20:]) if 'volume' in data.columns else 1

        # Ratio de volume
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

        # Génération du signal
        signal = self._generate_signal(
            current_price, current_volume, volume_ratio,
            resistance, support, atr
        )

        if signal:
            self.signals.append(signal)
            self.breakout_levels.append(signal.breakout_level)

            # Gestion de la position
            if signal.signal_type in ['buy', 'sell']:
                self._open_position(signal)
            elif signal.signal_type == 'exit':
                self._close_position(signal)

        return signal

    def _calculate_levels(self) -> Tuple[float, float]:
        """
        Calcule les niveaux de résistance et support.

        Returns:
            Tuple[float, float]: (resistance, support)
        """
        high = self.data['high'].values[-self.config.lookback_period:]
        low = self.data['low'].values[-self.config.lookback_period:]

        resistance = np.max(high)
        support = np.min(low)

        return resistance, support

    def _calculate_atr(self) -> float:
        """Calcule l'ATR"""
        high = self.data['high'].values
        low = self.data['low'].values
        close = self.data['close'].values

        if len(high) < self.config.atr_period:
            return 0.0

        tr = np.zeros(len(high))
        for i in range(1, len(high)):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )

        return np.mean(tr[-self.config.atr_period:])

    def _detect_false_breakout(self, price: float, level: float, direction: str) -> bool:
        """
        Détecte un faux breakout.

        Args:
            price: Prix actuel
            level: Niveau
            direction: 'up' ou 'down'

        Returns:
            bool: True si faux breakout
        """
        if not self.config.use_false_breakout_filter:
            return False

        if len(self.breakout_levels) < 2:
            return False

        if direction == 'up':
            # Vérification de la tendance
            if price < level * (1 - self.config.false_breakout_threshold):
                return True
        else:
            if price > level * (1 + self.config.false_breakout_threshold):
                return True

        return False

    def _generate_signal(
        self,
        price: float,
        volume: float,
        volume_ratio: float,
        resistance: float,
        support: float,
        atr: float
    ) -> Optional[BreakoutSignal]:
        """
        Génère un signal de trading.

        Args:
            price: Prix actuel
            volume: Volume actuel
            volume_ratio: Ratio de volume
            resistance: Niveau de résistance
            support: Niveau de support
            atr: ATR

        Returns:
            Optional[BreakoutSignal]: Signal généré
        """
        if self.position == 0:
            # Breakout haussier
            if price > resistance * (1 + self.config.breakout_threshold):
                if volume_ratio > self.config.volume_threshold:
                    if not self._detect_false_breakout(price, resistance, 'up'):
                        return BreakoutSignal(
                            timestamp=datetime.now(),
                            symbol=self.config.symbol,
                            signal_type='buy',
                            price=price,
                            breakout_level=resistance,
                            volume_ratio=volume_ratio,
                            atr=atr,
                            confidence=self._calculate_confidence(volume_ratio, atr),
                            reason="resistance_breakout",
                        )

            # Breakout baissier
            elif price < support * (1 - self.config.breakout_threshold):
                if volume_ratio > self.config.volume_threshold:
                    if not self._detect_false_breakout(price, support, 'down'):
                        return BreakoutSignal(
                            timestamp=datetime.now(),
                            symbol=self.config.symbol,
                            signal_type='sell',
                            price=price,
                            breakout_level=support,
                            volume_ratio=volume_ratio,
                            atr=atr,
                            confidence=self._calculate_confidence(volume_ratio, atr),
                            reason="support_breakout",
                        )

        else:
            # Position ouverte
            if self.position > 0:
                # Stop loss
                if price < self.position_entry_price - self.config.stop_loss_atr * atr:
                    return self._create_exit_signal(price, "stop_loss")

                # Take profit
                if price > self.position_entry_price + self.config.take_profit_atr * atr:
                    return self._create_exit_signal(price, "take_profit")

                # Trailing stop
                if price > self.position_entry_price:
                    new_stop = price - self.config.stop_loss_atr * atr
                    if new_stop > self.position_entry_price - self.config.stop_loss_atr * atr:
                        self.position_entry_price = new_stop

            elif self.position < 0:
                if price > self.position_entry_price + self.config.stop_loss_atr * atr:
                    return self._create_exit_signal(price, "stop_loss")

                if price < self.position_entry_price - self.config.take_profit_atr * atr:
                    return self._create_exit_signal(price, "take_profit")

                if price < self.position_entry_price:
                    new_stop = price + self.config.stop_loss_atr * atr
                    if new_stop < self.position_entry_price + self.config.stop_loss_atr * atr:
                        self.position_entry_price = new_stop

            # Max holding time
            if self.position_entry_time:
                holding_time = (datetime.now() - self.position_entry_time).days
                if holding_time >= self.config.max_holding_time:
                    return self._create_exit_signal(price, "max_holding_time")

        return None

    def _calculate_confidence(self, volume_ratio: float, atr: float) -> float:
        """
        Calcule le niveau de confiance.

        Args:
            volume_ratio: Ratio de volume
            atr: ATR

        Returns:
            float: Niveau de confiance (0-1)
        """
        factors = []

        # Volume
        volume_factor = min(1.0, volume_ratio / (self.config.volume_threshold * 1.5))
        factors.append(volume_factor)

        # ATR (plus l'ATR est élevé, plus le breakout est significatif)
        if atr > 0:
            atr_factor = min(1.0, atr / (self.data['close'].iloc[-1] * 0.02))
            factors.append(atr_factor)

        # Historique des breakout
        if self.breakout_levels:
            success_rate = 1 - (self.false_breakouts / max(1, len(self.breakout_levels)))
            factors.append(success_rate)

        return np.mean(factors)

    def _create_exit_signal(self, price: float, reason: str) -> BreakoutSignal:
        """Crée un signal de sortie"""
        return BreakoutSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='exit',
            price=price,
            breakout_level=0.0,
            volume_ratio=0.0,
            atr=0.0,
            confidence=0.8,
            reason=reason,
        )

    def _open_position(self, signal: BreakoutSignal) -> None:
        """Ouvre une position"""
        if signal.signal_type == 'buy':
            self.position = self.config.position_size
        elif signal.signal_type == 'sell':
            self.position = -self.config.position_size

        self.position_entry_price = signal.price
        self.position_entry_time = signal.timestamp

        logger.info(f"Position ouverte: {signal.signal_type} @ {signal.price:.2f} (breakout: {signal.breakout_level:.2f})")

    def _close_position(self, signal: BreakoutSignal) -> None:
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
            'breakout_level': signal.breakout_level,
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
            'breakout_success_rate': 1 - (self.false_breakouts / max(1, len(self.signals))),
        }


def create_breakout_strategy(
    symbol: str = "BTC-USD",
    lookback_period: int = 20,
    breakout_threshold: float = 0.02,
    **kwargs
) -> BreakoutStrategy:
    """
    Factory pour créer une stratégie de breakout.

    Args:
        symbol: Symbole
        lookback_period: Période de contexte
        breakout_threshold: Seuil de breakout
        **kwargs: Arguments supplémentaires

    Returns:
        BreakoutStrategy: Stratégie de breakout
    """
    config = BreakoutConfig(
        symbol=symbol,
        lookback_period=lookback_period,
        breakout_threshold=breakout_threshold,
        **kwargs
    )
    return BreakoutStrategy(config)


__all__ = [
    'BreakoutStrategy',
    'BreakoutConfig',
    'BreakoutSignal',
    'create_breakout_strategy',
]
