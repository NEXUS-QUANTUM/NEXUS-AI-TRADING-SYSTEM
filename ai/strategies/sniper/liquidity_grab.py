
# ai/strategies/sniper/liquidity_grab.py
"""
NEXUS AI TRADING SYSTEM - Liquidity Grab Strategy (Sniper)
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
class LiquidityGrabConfig:
    """Configuration pour Liquidity Grab Strategy"""
    symbol: str = "BTC-USD"
    lookback_period: int = 20
    liquidity_levels: int = 3
    volume_threshold: float = 1.5
    price_impact_threshold: float = 0.01
    position_size: float = 1.0
    stop_loss: float = 0.02
    take_profit: float = 0.04
    max_holding_time: int = 5
    fee_rate: float = 0.001
    min_liquidity: float = 100000.0
    use_order_book: bool = True
    order_book_depth: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'lookback_period': self.lookback_period,
            'liquidity_levels': self.liquidity_levels,
            'volume_threshold': self.volume_threshold,
            'price_impact_threshold': self.price_impact_threshold,
            'position_size': self.position_size,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'max_holding_time': self.max_holding_time,
            'fee_rate': self.fee_rate,
            'min_liquidity': self.min_liquidity,
            'use_order_book': self.use_order_book,
            'order_book_depth': self.order_book_depth,
        }


@dataclass
class LiquidityLevel:
    """Niveau de liquidité"""
    price: float
    volume: float
    side: str
    strength: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'price': self.price,
            'volume': self.volume,
            'side': self.side,
            'strength': self.strength,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class LiquidityGrabSignal:
    """Signal de Liquidity Grab"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    liquidity_level: float
    volume_spike: float
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'liquidity_level': self.liquidity_level,
            'volume_spike': self.volume_spike,
            'confidence': self.confidence,
            'reason': self.reason,
        }


class LiquidityGrabStrategy:
    """
    Stratégie de capture de liquidité (Sniper).

    Features:
    - Liquidity level detection
    - Volume spike analysis
    - Order book analysis
    - Price impact measurement
    - Fast execution

    Example:
        ```python
        config = LiquidityGrabConfig(
            symbol='BTC-USD',
            lookback_period=20,
            liquidity_levels=3
        )
        strategy = LiquidityGrabStrategy(config)

        # Update with data
        signal = strategy.update(price_data)
        ```
    """

    def __init__(self, config: Optional[LiquidityGrabConfig] = None):
        self.config = config or LiquidityGrabConfig()
        self.data: pd.DataFrame = pd.DataFrame()
        self.liquidity_levels: List[LiquidityLevel] = []
        self.position: int = 0
        self.position_entry_price: float = 0.0
        self.position_entry_time: Optional[datetime] = None
        self.signals: List[LiquidityGrabSignal] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.volume_spikes: List[float] = []

        logger.info(f"LiquidityGrabStrategy initialisé pour {self.config.symbol}")

    def update(self, data: pd.DataFrame) -> Optional[LiquidityGrabSignal]:
        """
        Met à jour la stratégie avec de nouvelles données.

        Args:
            data: DataFrame avec colonnes 'high', 'low', 'close', 'volume'

        Returns:
            Optional[LiquidityGrabSignal]: Signal généré
        """
        self.data = data

        if len(data) < self.config.lookback_period:
            return None

        # Détection des niveaux de liquidité
        self._detect_liquidity_levels()

        # Calcul du volume spike
        volume_spike = self._calculate_volume_spike()

        # Analyse du carnet d'ordres
        if self.config.use_order_book:
            order_book_analysis = self._analyze_order_book()
        else:
            order_book_analysis = {'imbalance': 0, 'liquidity': 0}

        # Prix actuel
        current_price = data['close'].iloc[-1]

        # Génération du signal
        signal = self._generate_signal(
            current_price, volume_spike, order_book_analysis
        )

        if signal:
            self.signals.append(signal)

            # Gestion de la position
            if signal.signal_type in ['buy', 'sell']:
                self._open_position(signal)
            elif signal.signal_type == 'exit':
                self._close_position(signal)

        return signal

    def _detect_liquidity_levels(self) -> None:
        """Détecte les niveaux de liquidité"""
        high = self.data['high'].values[-self.config.lookback_period:]
        low = self.data['low'].values[-self.config.lookback_period:]
        close = self.data['close'].values[-self.config.lookback_period:]

        # Niveaux de prix significatifs
        levels = []

        # High/Low récents
        levels.extend(high[-self.config.liquidity_levels:])
        levels.extend(low[-self.config.liquidity_levels:])

        # Moyennes mobiles
        for period in [10, 20, 50]:
            if len(close) >= period:
                ma = np.mean(close[-period:])
                levels.append(ma)

        # Points pivots
        for i in range(1, len(close) - 1):
            if (close[i] > close[i-1] and close[i] > close[i+1]) or \
               (close[i] < close[i-1] and close[i] < close[i+1]):
                levels.append(close[i])

        # Création des niveaux de liquidité
        self.liquidity_levels = []

        for price in set(levels):
            # Volume autour du niveau
            nearby_volume = self._get_volume_near_level(price)
            strength = min(1.0, nearby_volume / self.config.min_liquidity)

            level = LiquidityLevel(
                price=price,
                volume=nearby_volume,
                side='both',
                strength=strength,
                timestamp=datetime.now(),
            )
            self.liquidity_levels.append(level)

        # Trier par force
        self.liquidity_levels.sort(key=lambda x: -x.strength)

    def _get_volume_near_level(self, price: float) -> float:
        """Calcule le volume près d'un niveau"""
        if 'volume' not in self.data.columns:
            return 0.0

        volumes = self.data['volume'].values[-self.config.lookback_period:]
        closes = self.data['close'].values[-self.config.lookback_period:]

        total_volume = 0
        for i, close in enumerate(closes):
            if abs(close - price) / price < 0.01:
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

    def _analyze_order_book(self) -> Dict[str, Any]:
        """Analyse le carnet d'ordres"""
        # Simulation de l'analyse du carnet d'ordres
        # Dans la pratique, utiliser les données L2 réelles

        imbalance = np.random.uniform(-0.3, 0.3)
        liquidity = np.random.uniform(0, 1)

        return {
            'imbalance': imbalance,
            'liquidity': liquidity,
        }

    def _generate_signal(
        self,
        price: float,
        volume_spike: float,
        order_book: Dict[str, Any]
    ) -> Optional[LiquidityGrabSignal]:
        """
        Génère un signal de trading.

        Args:
            price: Prix actuel
            volume_spike: Volume spike
            order_book: Analyse du carnet d'ordres

        Returns:
            Optional[LiquidityGrabSignal]: Signal généré
        """
        if not self.liquidity_levels:
            return None

        if self.position == 0:
            # Recherche du niveau de liquidité le plus proche
            nearest_level = self._find_nearest_level(price)

            if nearest_level is None:
                return None

            # Vérification des conditions
            if volume_spike < self.config.volume_threshold:
                return None

            if order_book['liquidity'] < 0.5:
                return None

            # Direction basée sur le niveau et l'imbalance
            if nearest_level.price > price * (1 + self.config.price_impact_threshold):
                # Niveau au-dessus - potentiel breakout haussier
                if order_book['imbalance'] > 0.2:
                    return LiquidityGrabSignal(
                        timestamp=datetime.now(),
                        symbol=self.config.symbol,
                        signal_type='buy',
                        price=price,
                        liquidity_level=nearest_level.price,
                        volume_spike=volume_spike,
                        confidence=self._calculate_confidence(nearest_level, volume_spike),
                        reason="liquidity_above",
                    )

            elif nearest_level.price < price * (1 - self.config.price_impact_threshold):
                # Niveau en-dessous - potentiel breakout baissier
                if order_book['imbalance'] < -0.2:
                    return LiquidityGrabSignal(
                        timestamp=datetime.now(),
                        symbol=self.config.symbol,
                        signal_type='sell',
                        price=price,
                        liquidity_level=nearest_level.price,
                        volume_spike=volume_spike,
                        confidence=self._calculate_confidence(nearest_level, volume_spike),
                        reason="liquidity_below",
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

    def _find_nearest_level(self, price: float) -> Optional[LiquidityLevel]:
        """Trouve le niveau de liquidité le plus proche"""
        if not self.liquidity_levels:
            return None

        nearest = min(
            self.liquidity_levels,
            key=lambda x: abs(x.price - price)
        )

        # Vérification de la distance
        distance = abs(nearest.price - price) / price
        if distance > 0.05:  # 5% max
            return None

        return nearest

    def _calculate_confidence(self, level: LiquidityLevel, volume_spike: float) -> float:
        """
        Calcule le niveau de confiance.

        Args:
            level: Niveau de liquidité
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

        # Historique des signaux
        if self.signals:
            success_rate = sum(1 for s in self.signals[-20:] if s.signal_type != 'exit') / max(1, len(self.signals[-20:]))
            factors.append(success_rate)

        return np.mean(factors)

    def _create_exit_signal(self, price: float, reason: str) -> LiquidityGrabSignal:
        """Crée un signal de sortie"""
        return LiquidityGrabSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='exit',
            price=price,
            liquidity_level=0.0,
            volume_spike=0.0,
            confidence=0.8,
            reason=reason,
        )

    def _open_position(self, signal: LiquidityGrabSignal) -> None:
        """Ouvre une position"""
        if signal.signal_type == 'buy':
            self.position = self.config.position_size
        elif signal.signal_type == 'sell':
            self.position = -self.config.position_size

        self.position_entry_price = signal.price
        self.position_entry_time = signal.timestamp

        logger.info(f"Position ouverte: {signal.signal_type} @ {signal.price:.2f} (liquidity: {signal.liquidity_level:.2f})")

    def _close_position(self, signal: LiquidityGrabSignal) -> None:
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
            'liquidity_level': signal.liquidity_level,
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
            'liquidity_grab_success': sum(1 for t in self.trade_history if t.get('liquidity_level', 0) > 0) / max(1, len(self.trade_history)),
        }


def create_liquidity_grab_strategy(
    symbol: str = "BTC-USD",
    lookback_period: int = 20,
    liquidity_levels: int = 3,
    **kwargs
) -> LiquidityGrabStrategy:
    """
    Factory pour créer une stratégie de capture de liquidité.

    Args:
        symbol: Symbole
        lookback_period: Période de contexte
        liquidity_levels: Nombre de niveaux de liquidité
        **kwargs: Arguments supplémentaires

    Returns:
        LiquidityGrabStrategy: Stratégie de capture de liquidité
    """
    config = LiquidityGrabConfig(
        symbol=symbol,
        lookback_period=lookback_period,
        liquidity_levels=liquidity_levels,
        **kwargs
    )
    return LiquidityGrabStrategy(config)


__all__ = [
    'LiquidityGrabStrategy',
    'LiquidityGrabConfig',
    'LiquidityLevel',
    'LiquidityGrabSignal',
    'create_liquidity_grab_strategy',
]
