# ai/strategies/mean_reversion/bollinger_bands.py
"""
NEXUS AI TRADING SYSTEM - Bollinger Bands Mean Reversion Strategy
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
class BollingerBandsConfig:
    """Configuration pour Bollinger Bands"""
    symbol: str = "BTC-USD"
    window: int = 20
    num_std: float = 2.0
    entry_threshold: float = 2.0
    exit_threshold: float = 1.0
    stop_loss_threshold: float = 3.0
    position_size: float = 1.0
    use_atr_filter: bool = True
    atr_window: int = 14
    use_volume_filter: bool = False
    volume_threshold: float = 1.5
    max_position_duration: int = 10
    fee_rate: float = 0.001

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'window': self.window,
            'num_std': self.num_std,
            'entry_threshold': self.entry_threshold,
            'exit_threshold': self.exit_threshold,
            'stop_loss_threshold': self.stop_loss_threshold,
            'position_size': self.position_size,
            'use_atr_filter': self.use_atr_filter,
            'atr_window': self.atr_window,
            'use_volume_filter': self.use_volume_filter,
            'volume_threshold': self.volume_threshold,
            'max_position_duration': self.max_position_duration,
            'fee_rate': self.fee_rate,
        }


@dataclass
class BollingerSignal:
    """Signal de trading Bollinger Bands"""
    timestamp: datetime
    symbol: str
    signal_type: str  # 'buy', 'sell', 'exit'
    price: float
    upper_band: float
    middle_band: float
    lower_band: float
    z_score: float
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'upper_band': self.upper_band,
            'middle_band': self.middle_band,
            'lower_band': self.lower_band,
            'z_score': self.z_score,
            'confidence': self.confidence,
            'reason': self.reason,
        }


class BollingerBandsStrategy:
    """
    Stratégie de mean reversion avec Bollinger Bands.

    Features:
    - Bollinger Bands calculation
    - Entry/Exit signals
    - ATR filter
    - Volume filter
    - Position management

    Example:
        ```python
        config = BollingerBandsConfig(
            symbol='BTC-USD',
            window=20,
            num_std=2.0,
            entry_threshold=2.0
        )
        strategy = BollingerBandsStrategy(config)

        # Update with data
        signal = strategy.update(price_data)

        # Get current bands
        bands = strategy.get_bands()
        ```
    """

    def __init__(self, config: Optional[BollingerBandsConfig] = None):
        self.config = config or BollingerBandsConfig()
        self.data: pd.DataFrame = pd.DataFrame()
        self.upper_band: float = 0.0
        self.middle_band: float = 0.0
        self.lower_band: float = 0.0
        self.atr: float = 0.0
        self.current_price: float = 0.0
        self.position: int = 0
        self.position_entry_price: float = 0.0
        self.position_entry_time: Optional[datetime] = None
        self.trade_history: List[Dict[str, Any]] = []
        self.signals: List[BollingerSignal] = []

        logger.info(f"BollingerBandsStrategy initialisé pour {self.config.symbol}")

    def update(self, data: pd.DataFrame) -> Optional[BollingerSignal]:
        """
        Met à jour la stratégie avec de nouvelles données.

        Args:
            data: DataFrame avec colonnes 'timestamp', 'close', 'high', 'low', 'volume'

        Returns:
            Optional[BollingerSignal]: Signal généré
        """
        self.data = data

        if len(data) < self.config.window:
            return None

        # Calcul des bandes
        self._calculate_bands()

        # Calcul de l'ATR
        if self.config.use_atr_filter:
            self._calculate_atr()

        # Prix actuel
        self.current_price = data['close'].iloc[-1]

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

    def _calculate_bands(self) -> None:
        """Calcule les Bollinger Bands"""
        close = self.data['close'].values
        window = self.config.window

        # Middle band: SMA
        middle = np.mean(close[-window:])
        self.middle_band = middle

        # Standard deviation
        std = np.std(close[-window:])

        # Upper and lower bands
        self.upper_band = middle + self.config.num_std * std
        self.lower_band = middle - self.config.num_std * std

    def _calculate_atr(self) -> None:
        """Calcule l'ATR (Average True Range)"""
        high = self.data['high'].values
        low = self.data['low'].values
        close = self.data['close'].values
        window = self.config.atr_window

        if len(high) < window:
            self.atr = 0.0
            return

        # True Range
        tr = np.zeros(len(high))
        for i in range(1, len(high)):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )

        # ATR: SMA of TR
        self.atr = np.mean(tr[-window:])

    def _generate_signal(self) -> Optional[BollingerSignal]:
        """
        Génère un signal de trading.

        Returns:
            Optional[BollingerSignal]: Signal généré
        """
        if self.current_price == 0:
            return None

        # Calcul du z-score
        z_score = (self.current_price - self.middle_band) / (self.upper_band - self.middle_band)

        # Filtre ATR
        if self.config.use_atr_filter and self.atr > 0:
            if self.atr / self.middle_band < 0.01:
                return None

        # Filtre volume
        if self.config.use_volume_filter:
            volume = self.data['volume'].values[-1]
            avg_volume = np.mean(self.data['volume'].values[-20:])
            if volume / avg_volume < self.config.volume_threshold:
                return None

        # Vérification de la position
        if self.position == 0:
            # Pas de position ouverte
            if z_score < -self.config.entry_threshold:
                # Oversold -> Buy
                return BollingerSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='buy',
                    price=self.current_price,
                    upper_band=self.upper_band,
                    middle_band=self.middle_band,
                    lower_band=self.lower_band,
                    z_score=z_score,
                    confidence=self._calculate_confidence(z_score),
                    reason=f"oversold_zscore_{abs(z_score):.2f}",
                )
            elif z_score > self.config.entry_threshold:
                # Overbought -> Sell
                return BollingerSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='sell',
                    price=self.current_price,
                    upper_band=self.upper_band,
                    middle_band=self.middle_band,
                    lower_band=self.lower_band,
                    z_score=z_score,
                    confidence=self._calculate_confidence(z_score),
                    reason=f"overbought_zscore_{abs(z_score):.2f}",
                )

        else:
            # Position ouverte
            duration = (datetime.now() - self.position_entry_time).days if self.position_entry_time else 0

            # Vérification de la durée maximale
            if duration >= self.config.max_position_duration:
                return BollingerSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='exit',
                    price=self.current_price,
                    upper_band=self.upper_band,
                    middle_band=self.middle_band,
                    lower_band=self.lower_band,
                    z_score=z_score,
                    confidence=0.8,
                    reason="max_duration_exceeded",
                )

            # Exit lorsque le z-score revient vers la moyenne
            if self.position > 0:  # Long position
                if z_score > -self.config.exit_threshold:
                    return BollingerSignal(
                        timestamp=datetime.now(),
                        symbol=self.config.symbol,
                        signal_type='exit',
                        price=self.current_price,
                        upper_band=self.upper_band,
                        middle_band=self.middle_band,
                        lower_band=self.lower_band,
                        z_score=z_score,
                        confidence=self._calculate_confidence(abs(z_score)),
                        reason="mean_reversion",
                    )

            elif self.position < 0:  # Short position
                if z_score < self.config.exit_threshold:
                    return BollingerSignal(
                        timestamp=datetime.now(),
                        symbol=self.config.symbol,
                        signal_type='exit',
                        price=self.current_price,
                        upper_band=self.upper_band,
                        middle_band=self.middle_band,
                        lower_band=self.lower_band,
                        z_score=z_score,
                        confidence=self._calculate_confidence(abs(z_score)),
                        reason="mean_reversion",
                    )

            # Stop loss
            if abs(z_score) > self.config.stop_loss_threshold:
                return BollingerSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='exit',
                    price=self.current_price,
                    upper_band=self.upper_band,
                    middle_band=self.middle_band,
                    lower_band=self.lower_band,
                    z_score=z_score,
                    confidence=0.9,
                    reason="stop_loss",
                )

        return None

    def _calculate_confidence(self, z_score: float) -> float:
        """
        Calcule le niveau de confiance.

        Args:
            z_score: Z-score

        Returns:
            float: Niveau de confiance (0-1)
        """
        # Plus le z-score est élevé, plus la confiance est élevée
        confidence = min(1.0, abs(z_score) / self.config.entry_threshold)
        return confidence

    def _open_position(self, signal: BollingerSignal) -> None:
        """Ouvre une position"""
        if signal.signal_type == 'buy':
            self.position = self.config.position_size
        elif signal.signal_type == 'sell':
            self.position = -self.config.position_size

        self.position_entry_price = signal.price
        self.position_entry_time = signal.timestamp

        logger.info(f"Position ouverte: {signal.signal_type} @ {signal.price:.2f}")

    def _close_position(self, signal: BollingerSignal) -> None:
        """Ferme une position"""
        if self.position == 0:
            return

        # Calcul du P&L
        if self.position > 0:  # Long position
            pnl = (signal.price - self.position_entry_price) * abs(self.position)
        else:  # Short position
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

    def get_bands(self) -> Dict[str, float]:
        """
        Retourne les Bollinger Bands actuelles.

        Returns:
            Dict[str, float]: Bandes
        """
        return {
            'upper': self.upper_band,
            'middle': self.middle_band,
            'lower': self.lower_band,
        }

    def get_position(self) -> Dict[str, Any]:
        """
        Retourne la position actuelle.

        Returns:
            Dict[str, Any]: Position
        """
        return {
            'position': self.position,
            'entry_price': self.position_entry_price,
            'entry_time': self.position_entry_time.isoformat() if self.position_entry_time else None,
            'current_price': self.current_price,
            'unrealized_pnl': self._calculate_unrealized_pnl(),
        }

    def _calculate_unrealized_pnl(self) -> float:
        """Calcule le P&L non réalisé"""
        if self.position == 0:
            return 0.0

        if self.position > 0:
            pnl = (self.current_price - self.position_entry_price) * abs(self.position)
        else:
            pnl = (self.position_entry_price - self.current_price) * abs(self.position)

        return pnl

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

    def plot(self, figsize: Tuple[int, int] = (12, 6)):
        """
        Affiche les Bollinger Bands et les signaux.

        Args:
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        if len(self.data) < self.config.window:
            return

        fig, ax = plt.subplots(figsize=figsize)

        # Prix
        ax.plot(self.data['timestamp'], self.data['close'], label='Price', color='blue')

        # Bandes
        bands = self._calculate_historical_bands()
        ax.plot(self.data['timestamp'][-len(bands):], bands['upper'], label='Upper Band', color='red', linestyle='--')
        ax.plot(self.data['timestamp'][-len(bands):], bands['middle'], label='Middle Band', color='green', linestyle='--')
        ax.plot(self.data['timestamp'][-len(bands):], bands['lower'], label='Lower Band', color='red', linestyle='--')

        # Signaux
        for signal in self.signals:
            marker = '^' if signal.signal_type == 'buy' else 'v' if signal.signal_type == 'sell' else 'o'
            color = 'green' if signal.signal_type == 'buy' else 'red' if signal.signal_type == 'sell' else 'yellow'
            ax.scatter(signal.timestamp, signal.price, marker=marker, color=color, s=100, label=signal.signal_type if signal.signal_type not in ['buy', 'sell'] else '')

        ax.set_title(f'Bollinger Bands - {self.config.symbol}')
        ax.set_xlabel('Time')
        ax.set_ylabel('Price')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

    def _calculate_historical_bands(self) -> Dict[str, List[float]]:
        """Calcule les bandes historiques"""
        close = self.data['close'].values
        window = self.config.window

        upper = []
        middle = []
        lower = []

        for i in range(window, len(close)):
            window_data = close[i-window:i]
            mean = np.mean(window_data)
            std = np.std(window_data)

            upper.append(mean + self.config.num_std * std)
            middle.append(mean)
            lower.append(mean - self.config.num_std * std)

        return {'upper': upper, 'middle': middle, 'lower': lower}


def create_bollinger_bands_strategy(
    symbol: str = "BTC-USD",
    window: int = 20,
    num_std: float = 2.0,
    entry_threshold: float = 2.0,
    **kwargs
) -> BollingerBandsStrategy:
    """
    Factory pour créer une stratégie Bollinger Bands.

    Args:
        symbol: Symbole
        window: Fenêtre de calcul
        num_std: Nombre d'écarts-types
        entry_threshold: Seuil d'entrée
        **kwargs: Arguments supplémentaires

    Returns:
        BollingerBandsStrategy: Stratégie Bollinger Bands
    """
    config = BollingerBandsConfig(
        symbol=symbol,
        window=window,
        num_std=num_std,
        entry_threshold=entry_threshold,
        **kwargs
    )
    return BollingerBandsStrategy(config)


__all__ = [
    'BollingerBandsStrategy',
    'BollingerBandsConfig',
    'BollingerSignal',
    'create_bollinger_bands_strategy',
]
