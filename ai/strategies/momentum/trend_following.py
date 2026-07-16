# ai/strategies/momentum/trend_following.py
"""
NEXUS AI TRADING SYSTEM - Trend Following Strategy
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
class TrendFollowingConfig:
    """Configuration pour Trend Following Strategy"""
    symbol: str = "BTC-USD"
    adx_period: int = 14
    adx_threshold: float = 25.0
    use_ema_filter: bool = True
    fast_ema: int = 50
    slow_ema: int = 200
    use_channel_breakout: bool = True
    channel_period: int = 20
    position_size: float = 1.0
    stop_loss_atr: float = 2.0
    take_profit_atr: float = 4.0
    trailing_stop: bool = True
    trailing_atr: float = 1.5
    fee_rate: float = 0.001
    atr_period: int = 14

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'adx_period': self.adx_period,
            'adx_threshold': self.adx_threshold,
            'use_ema_filter': self.use_ema_filter,
            'fast_ema': self.fast_ema,
            'slow_ema': self.slow_ema,
            'use_channel_breakout': self.use_channel_breakout,
            'channel_period': self.channel_period,
            'position_size': self.position_size,
            'stop_loss_atr': self.stop_loss_atr,
            'take_profit_atr': self.take_profit_atr,
            'trailing_stop': self.trailing_stop,
            'trailing_atr': self.trailing_atr,
            'fee_rate': self.fee_rate,
            'atr_period': self.atr_period,
        }


@dataclass
class TrendSignal:
    """Signal de trading de tendance"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    adx: float
    trend_strength: float
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'adx': self.adx,
            'trend_strength': self.trend_strength,
            'confidence': self.confidence,
            'reason': self.reason,
        }


class TrendFollowingStrategy:
    """
    Stratégie de suivi de tendance.

    Features:
    - ADX indicator for trend strength
    - EMA filters
    - Channel breakouts
    - ATR-based position sizing
    - Trailing stop loss

    Example:
        ```python
        config = TrendFollowingConfig(
            symbol='BTC-USD',
            adx_period=14,
            adx_threshold=25.0
        )
        strategy = TrendFollowingStrategy(config)

        # Update with data
        signal = strategy.update(price_data)
        ```
    """

    def __init__(self, config: Optional[TrendFollowingConfig] = None):
        self.config = config or TrendFollowingConfig()
        self.data: pd.DataFrame = pd.DataFrame()
        self.adx: List[float] = []
        self.atr: List[float] = []
        self.position: int = 0
        self.position_entry_price: float = 0.0
        self.position_entry_time: Optional[datetime] = None
        self.trailing_stop_price: float = 0.0
        self.signals: List[TrendSignal] = []
        self.trade_history: List[Dict[str, Any]] = []

        logger.info(f"TrendFollowingStrategy initialisé pour {self.config.symbol}")

    def update(self, data: pd.DataFrame) -> Optional[TrendSignal]:
        """
        Met à jour la stratégie avec de nouvelles données.

        Args:
            data: DataFrame avec colonnes 'timestamp', 'high', 'low', 'close'

        Returns:
            Optional[TrendSignal]: Signal généré
        """
        self.data = data

        if len(data) < max(self.config.adx_period, self.config.atr_period):
            return None

        # Calcul des indicateurs
        self._calculate_adx()
        self._calculate_atr()

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

        # Mise à jour du trailing stop
        if self.position != 0 and self.config.trailing_stop:
            self._update_trailing_stop()

        return signal

    def _calculate_adx(self) -> None:
        """Calcule l'ADX (Average Directional Index)"""
        high = self.data['high'].values
        low = self.data['low'].values
        close = self.data['close'].values

        # True Range
        tr = np.zeros(len(high))
        for i in range(1, len(high)):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )

        # Average True Range
        atr = self._calculate_sma(tr, self.config.adx_period)

        # Directional Movement
        plus_dm = np.zeros(len(high))
        minus_dm = np.zeros(len(high))

        for i in range(1, len(high)):
            up_move = high[i] - high[i-1]
            down_move = low[i-1] - low[i]

            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            else:
                plus_dm[i] = 0

            if down_move > up_move and down_move > 0:
                minus_dm[i] = down_move
            else:
                minus_dm[i] = 0

        # Smooth DI
        plus_di = self._calculate_sma(plus_dm, self.config.adx_period) / atr * 100
        minus_di = self._calculate_sma(minus_dm, self.config.adx_period) / atr * 100

        # DX and ADX
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
        self.adx = self._calculate_sma(dx, self.config.adx_period)

    def _calculate_atr(self) -> None:
        """Calcule l'ATR (Average True Range)"""
        high = self.data['high'].values
        low = self.data['low'].values
        close = self.data['close'].values

        tr = np.zeros(len(high))
        for i in range(1, len(high)):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )

        self.atr = self._calculate_sma(tr, self.config.atr_period)

    def _calculate_sma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calcule la SMA"""
        sma = np.zeros(len(data))
        for i in range(len(data)):
            if i < period - 1:
                sma[i] = data[i]
            else:
                sma[i] = np.mean(data[i-period+1:i+1])
        return sma

    def _get_trend_direction(self) -> str:
        """
        Détermine la direction de la tendance.

        Returns:
            str: 'bullish', 'bearish', 'neutral'
        """
        if len(self.adx) < 2:
            return 'neutral'

        current_adx = self.adx[-1]
        if current_adx < self.config.adx_threshold:
            return 'neutral'

        # Direction de la tendance
        close = self.data['close'].values

        if self.config.use_ema_filter:
            fast_ema = self._calculate_sma(close, self.config.fast_ema)
            slow_ema = self._calculate_sma(close, self.config.slow_ema)

            if fast_ema[-1] > slow_ema[-1]:
                return 'bullish'
            else:
                return 'bearish'

        # Prix vs moyenne
        sma = np.mean(close[-20:])
        if close[-1] > sma:
            return 'bullish'
        else:
            return 'bearish'

    def _get_channel_levels(self) -> Tuple[float, float]:
        """
        Retourne les niveaux du canal.

        Returns:
            Tuple[float, float]: (support, resistance)
        """
        high = self.data['high'].values[-self.config.channel_period:]
        low = self.data['low'].values[-self.config.channel_period:]

        resistance = np.max(high)
        support = np.min(low)

        return support, resistance

    def _generate_signal(self) -> Optional[TrendSignal]:
        """
        Génère un signal de trading.

        Returns:
            Optional[TrendSignal]: Signal généré
        """
        if len(self.adx) < 2:
            return None

        current_price = self.data['close'].iloc[-1]
        current_adx = self.adx[-1]
        trend = self._get_trend_direction()

        if self.position == 0:
            if current_adx < self.config.adx_threshold:
                return None

            if trend == 'neutral':
                return None

            if self.config.use_channel_breakout:
                support, resistance = self._get_channel_levels()

                if trend == 'bullish' and current_price > resistance:
                    return self._create_buy_signal(current_price, current_adx)
                elif trend == 'bearish' and current_price < support:
                    return self._create_sell_signal(current_price, current_adx)

            else:
                if trend == 'bullish':
                    return self._create_buy_signal(current_price, current_adx)
                elif trend == 'bearish':
                    return self._create_sell_signal(current_price, current_adx)

        else:
            # Position ouverte
            if self.position > 0:
                # Sortie si tendance baissière
                if trend == 'bearish' and current_adx > self.config.adx_threshold:
                    return self._create_exit_signal(current_price, "bearish_trend")

                # Sortie si ADX descend en dessous du seuil
                if current_adx < self.config.adx_threshold:
                    return self._create_exit_signal(current_price, "weak_trend")

                # Stop loss
                pnl_percent = (current_price - self.position_entry_price) / self.position_entry_price
                if pnl_percent < -self.config.stop_loss_atr * self.atr[-1] / self.position_entry_price:
                    return self._create_exit_signal(current_price, "stop_loss")

                # Take profit
                if pnl_percent > self.config.take_profit_atr * self.atr[-1] / self.position_entry_price:
                    return self._create_exit_signal(current_price, "take_profit")

                # Trailing stop
                if self.config.trailing_stop and current_price < self.trailing_stop_price:
                    return self._create_exit_signal(current_price, "trailing_stop")

            elif self.position < 0:
                # Sortie si tendance haussière
                if trend == 'bullish' and current_adx > self.config.adx_threshold:
                    return self._create_exit_signal(current_price, "bullish_trend")

                if current_adx < self.config.adx_threshold:
                    return self._create_exit_signal(current_price, "weak_trend")

                pnl_percent = (self.position_entry_price - current_price) / self.position_entry_price
                if pnl_percent < -self.config.stop_loss_atr * self.atr[-1] / self.position_entry_price:
                    return self._create_exit_signal(current_price, "stop_loss")

                if pnl_percent > self.config.take_profit_atr * self.atr[-1] / self.position_entry_price:
                    return self._create_exit_signal(current_price, "take_profit")

                if self.config.trailing_stop and current_price > self.trailing_stop_price:
                    return self._create_exit_signal(current_price, "trailing_stop")

        return None

    def _create_buy_signal(self, price: float, adx: float) -> TrendSignal:
        """Crée un signal d'achat"""
        confidence = self._calculate_confidence(adx)
        return TrendSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='buy',
            price=price,
            adx=adx,
            trend_strength=adx / 100,
            confidence=confidence,
            reason="bullish_trend",
        )

    def _create_sell_signal(self, price: float, adx: float) -> TrendSignal:
        """Crée un signal de vente"""
        confidence = self._calculate_confidence(adx)
        return TrendSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='sell',
            price=price,
            adx=adx,
            trend_strength=adx / 100,
            confidence=confidence,
            reason="bearish_trend",
        )

    def _create_exit_signal(self, price: float, reason: str) -> TrendSignal:
        """Crée un signal de sortie"""
        return TrendSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='exit',
            price=price,
            adx=self.adx[-1],
            trend_strength=self.adx[-1] / 100,
            confidence=0.8,
            reason=reason,
        )

    def _calculate_confidence(self, adx: float) -> float:
        """Calcule le niveau de confiance"""
        confidence = min(1.0, adx / 50)
        return confidence

    def _update_trailing_stop(self) -> None:
        """Met à jour le trailing stop"""
        if self.atr is None or len(self.atr) == 0:
            return

        current_atr = self.atr[-1]
        current_price = self.data['close'].iloc[-1]

        if self.position > 0:
            # Long position
            new_stop = current_price - self.config.trailing_atr * current_atr
            if new_stop > self.trailing_stop_price:
                self.trailing_stop_price = new_stop
        elif self.position < 0:
            # Short position
            new_stop = current_price + self.config.trailing_atr * current_atr
            if new_stop < self.trailing_stop_price or self.trailing_stop_price == 0:
                self.trailing_stop_price = new_stop

    def _open_position(self, signal: TrendSignal) -> None:
        """Ouvre une position"""
        if signal.signal_type == 'buy':
            self.position = self.config.position_size
        elif signal.signal_type == 'sell':
            self.position = -self.config.position_size

        self.position_entry_price = signal.price
        self.position_entry_time = signal.timestamp

        # Initialisation du trailing stop
        if self.config.trailing_stop and self.atr:
            current_atr = self.atr[-1]
            if self.position > 0:
                self.trailing_stop_price = signal.price - self.config.trailing_atr * current_atr
            else:
                self.trailing_stop_price = signal.price + self.config.trailing_atr * current_atr

        logger.info(f"Position ouverte: {signal.signal_type} @ {signal.price:.2f}")

    def _close_position(self, signal: TrendSignal) -> None:
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
        self.trailing_stop_price = 0.0

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


def create_trend_following_strategy(
    symbol: str = "BTC-USD",
    adx_period: int = 14,
    adx_threshold: float = 25.0,
    **kwargs
) -> TrendFollowingStrategy:
    """
    Factory pour créer une stratégie de suivi de tendance.

    Args:
        symbol: Symbole
        adx_period: Période ADX
        adx_threshold: Seuil ADX
        **kwargs: Arguments supplémentaires

    Returns:
        TrendFollowingStrategy: Stratégie de suivi de tendance
    """
    config = TrendFollowingConfig(
        symbol=symbol,
        adx_period=adx_period,
        adx_threshold=adx_threshold,
        **kwargs
    )
    return TrendFollowingStrategy(config)


__all__ = [
    'TrendFollowingStrategy',
    'TrendFollowingConfig',
    'TrendSignal',
    'create_trend_following_strategy',
]
