# ai/strategies/swing/harmonic_patterns.py
"""
NEXUS AI TRADING SYSTEM - Harmonic Patterns Strategy
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
class HarmonicPatternConfig:
    """Configuration pour Harmonic Patterns Strategy"""
    symbol: str = "BTC-USD"
    lookback_period: int = 100
    min_pattern_quality: float = 0.7
    max_retracement_error: float = 0.05
    position_size: float = 1.0
    stop_loss: float = 0.02
    take_profit: float = 0.04
    max_holding_time: int = 10
    fee_rate: float = 0.001
    patterns: List[str] = field(default_factory=lambda: ['gartley', 'bat', 'butterfly', 'crab'])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'lookback_period': self.lookback_period,
            'min_pattern_quality': self.min_pattern_quality,
            'max_retracement_error': self.max_retracement_error,
            'position_size': self.position_size,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'max_holding_time': self.max_holding_time,
            'fee_rate': self.fee_rate,
            'patterns': self.patterns,
        }


@dataclass
class HarmonicPoint:
    """Point d'un motif harmonique"""
    index: int
    price: float
    type: str
    x: float
    y: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.index,
            'price': self.price,
            'type': self.type,
            'x': self.x,
            'y': self.y,
        }


@dataclass
class HarmonicPattern:
    """Motif harmonique détecté"""
    name: str
    points: List[HarmonicPoint]
    quality: float
    entry_price: float
    stop_loss: float
    take_profit: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'points': [p.to_dict() for p in self.points],
            'quality': self.quality,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class HarmonicSignal:
    """Signal de trading harmonique"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    pattern_name: str
    pattern_quality: float
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'pattern_name': self.pattern_name,
            'pattern_quality': self.pattern_quality,
            'confidence': self.confidence,
            'reason': self.reason,
        }


class HarmonicPatternsStrategy:
    """
    Stratégie Swing basée sur les motifs harmoniques.

    Features:
    - Gartley pattern
    - Bat pattern
    - Butterfly pattern
    - Crab pattern
    - Pattern quality scoring

    Example:
        ```python
        config = HarmonicPatternConfig(
            symbol='BTC-USD',
            lookback_period=100,
            min_pattern_quality=0.7
        )
        strategy = HarmonicPatternsStrategy(config)

        # Update with data
        signal = strategy.update(price_data)
        ```
    """

    def __init__(self, config: Optional[HarmonicPatternConfig] = None):
        self.config = config or HarmonicPatternConfig()
        self.data: pd.DataFrame = pd.DataFrame()
        self.patterns: List[HarmonicPattern] = []
        self.position: int = 0
        self.position_entry_price: float = 0.0
        self.position_entry_time: Optional[datetime] = None
        self.signals: List[HarmonicSignal] = []
        self.trade_history: List[Dict[str, Any]] = []

        logger.info(f"HarmonicPatternsStrategy initialisé pour {self.config.symbol}")

    def update(self, data: pd.DataFrame) -> Optional[HarmonicSignal]:
        """
        Met à jour la stratégie avec de nouvelles données.

        Args:
            data: DataFrame avec colonnes 'high', 'low', 'close'

        Returns:
            Optional[HarmonicSignal]: Signal généré
        """
        self.data = data

        if len(data) < self.config.lookback_period:
            return None

        # Détection des motifs harmoniques
        self._detect_patterns()

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

    def _detect_patterns(self) -> None:
        """Détecte les motifs harmoniques"""
        high = self.data['high'].values
        low = self.data['low'].values
        close = self.data['close'].values

        # Détection des points extrêmes
        swing_points = self._find_swing_points(high, low)

        if len(swing_points) < 5:
            return

        self.patterns = []

        # Recherche des motifs
        for i in range(len(swing_points) - 4):
            points = swing_points[i:i+5]

            for pattern_name in self.config.patterns:
                pattern = self._check_pattern(points, pattern_name)
                if pattern and pattern.quality >= self.config.min_pattern_quality:
                    self.patterns.append(pattern)

    def _find_swing_points(self, high: np.ndarray, low: np.ndarray) -> List[HarmonicPoint]:
        """Trouve les points de swing"""
        points = []
        n = len(high)

        for i in range(1, n - 1):
            # Sommet
            if high[i] > high[i-1] and high[i] > high[i+1]:
                points.append(HarmonicPoint(
                    index=i,
                    price=high[i],
                    type='high',
                    x=i,
                    y=high[i]
                ))
            # Creux
            elif low[i] < low[i-1] and low[i] < low[i+1]:
                points.append(HarmonicPoint(
                    index=i,
                    price=low[i],
                    type='low',
                    x=i,
                    y=low[i]
                ))

        return points

    def _check_pattern(self, points: List[HarmonicPoint], pattern_name: str) -> Optional[HarmonicPattern]:
        """
        Vérifie un motif harmonique spécifique.

        Args:
            points: Points de swing
            pattern_name: Nom du motif

        Returns:
            Optional[HarmonicPattern]: Motif détecté
        """
        if len(points) < 5:
            return None

        # Points X, A, B, C, D
        X, A, B, C, D = points[-5:]

        # Calcul des ratios Fibonacci
        ab_ratio = self._fib_ratio(X.price, A.price, B.price)
        bc_ratio = self._fib_ratio(A.price, B.price, C.price)
        cd_ratio = self._fib_ratio(B.price, C.price, D.price)

        # Vérification du motif
        quality = 0.0
        pattern_type = None

        if pattern_name == 'gartley':
            pattern_type = self._check_gartley(ab_ratio, bc_ratio, cd_ratio)
        elif pattern_name == 'bat':
            pattern_type = self._check_bat(ab_ratio, bc_ratio, cd_ratio)
        elif pattern_name == 'butterfly':
            pattern_type = self._check_butterfly(ab_ratio, bc_ratio, cd_ratio)
        elif pattern_name == 'crab':
            pattern_type = self._check_crab(ab_ratio, bc_ratio, cd_ratio)

        if not pattern_type:
            return None

        # Calcul de la qualité
        quality = self._calculate_pattern_quality(ab_ratio, bc_ratio, cd_ratio, pattern_type)

        if quality < self.config.min_pattern_quality:
            return None

        # Points de trading
        entry_price = self._calculate_entry_price(points, pattern_type)
        stop_loss = self._calculate_stop_loss(points, pattern_type)
        take_profit = self._calculate_take_profit(points, pattern_type)

        return HarmonicPattern(
            name=pattern_name,
            points=points,
            quality=quality,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=datetime.now(),
        )

    def _fib_ratio(self, p1: float, p2: float, p3: float) -> float:
        """
        Calcule le ratio de Fibonacci entre deux mouvements.

        Args:
            p1: Premier prix
            p2: Deuxième prix
            p3: Troisième prix

        Returns:
            float: Ratio de Fibonacci
        """
        move1 = abs(p2 - p1)
        move2 = abs(p3 - p2)
        if move1 > 0:
            return move2 / move1
        return 0.0

    def _check_gartley(self, ab: float, bc: float, cd: float) -> Optional[str]:
        """
        Vérifie le motif Gartley.

        Args:
            ab: Ratio AB
            bc: Ratio BC
            cd: Ratio CD

        Returns:
            Optional[str]: Type de motif ('bullish' ou 'bearish')
        """
        if (0.618 - self.config.max_retracement_error < ab < 0.618 + self.config.max_retracement_error and
            0.382 - self.config.max_retracement_error < bc < 0.886 + self.config.max_retracement_error and
            1.272 - self.config.max_retracement_error < cd < 1.618 + self.config.max_retracement_error):
            return 'bullish' if ab < 0.618 else 'bearish'
        return None

    def _check_bat(self, ab: float, bc: float, cd: float) -> Optional[str]:
        """
        Vérifie le motif Bat.

        Args:
            ab: Ratio AB
            bc: Ratio BC
            cd: Ratio CD

        Returns:
            Optional[str]: Type de motif
        """
        if (0.382 - self.config.max_retracement_error < ab < 0.5 + self.config.max_retracement_error and
            0.382 - self.config.max_retracement_error < bc < 0.886 + self.config.max_retracement_error and
            1.618 - self.config.max_retracement_error < cd < 2.618 + self.config.max_retracement_error):
            return 'bullish' if ab < 0.5 else 'bearish'
        return None

    def _check_butterfly(self, ab: float, bc: float, cd: float) -> Optional[str]:
        """
        Vérifie le motif Butterfly.

        Args:
            ab: Ratio AB
            bc: Ratio BC
            cd: Ratio CD

        Returns:
            Optional[str]: Type de motif
        """
        if (0.786 - self.config.max_retracement_error < ab < 0.886 + self.config.max_retracement_error and
            0.382 - self.config.max_retracement_error < bc < 0.886 + self.config.max_retracement_error and
            1.618 - self.config.max_retracement_error < cd < 2.618 + self.config.max_retracement_error):
            return 'bullish' if ab < 0.886 else 'bearish'
        return None

    def _check_crab(self, ab: float, bc: float, cd: float) -> Optional[str]:
        """
        Vérifie le motif Crab.

        Args:
            ab: Ratio AB
            bc: Ratio BC
            cd: Ratio CD

        Returns:
            Optional[str]: Type de motif
        """
        if (0.382 - self.config.max_retracement_error < ab < 0.618 + self.config.max_retracement_error and
            0.382 - self.config.max_retracement_error < bc < 0.886 + self.config.max_retracement_error and
            2.618 - self.config.max_retracement_error < cd < 3.618 + self.config.max_retracement_error):
            return 'bullish' if ab < 0.618 else 'bearish'
        return None

    def _calculate_pattern_quality(self, ab: float, bc: float, cd: float, pattern_type: str) -> float:
        """
        Calcule la qualité d'un motif.

        Args:
            ab: Ratio AB
            bc: Ratio BC
            cd: Ratio CD
            pattern_type: Type de motif

        Returns:
            float: Qualité du motif (0-1)
        """
        # Calcul des erreurs par rapport aux ratios idéaux
        errors = []

        if pattern_type in ['bullish', 'bearish']:
            # Pour chaque motif, les ratios idéaux sont différents
            # Simplification: utiliser les erreurs absolues
            ideal_ratios = {
                'gartley': (0.618, 0.618, 1.272),
                'bat': (0.382, 0.618, 1.618),
                'butterfly': (0.786, 0.618, 1.618),
                'crab': (0.382, 0.618, 2.618),
            }

            ideal = ideal_ratios.get('gartley', (0.618, 0.618, 1.272))
            errors.extend([
                abs(ab - ideal[0]) / ideal[0] if ideal[0] > 0 else 0,
                abs(bc - ideal[1]) / ideal[1] if ideal[1] > 0 else 0,
                abs(cd - ideal[2]) / ideal[2] if ideal[2] > 0 else 0,
            ])

        avg_error = np.mean(errors) if errors else 1.0
        quality = max(0, 1 - avg_error)

        return quality

    def _calculate_entry_price(self, points: List[HarmonicPoint], pattern_type: str) -> float:
        """Calcule le prix d'entrée"""
        D = points[-1]
        return D.price

    def _calculate_stop_loss(self, points: List[HarmonicPoint], pattern_type: str) -> float:
        """Calcule le stop loss"""
        D = points[-1]
        if pattern_type == 'bullish':
            return D.price * (1 - self.config.stop_loss)
        else:
            return D.price * (1 + self.config.stop_loss)

    def _calculate_take_profit(self, points: List[HarmonicPoint], pattern_type: str) -> float:
        """Calcule le take profit"""
        D = points[-1]
        if pattern_type == 'bullish':
            return D.price * (1 + self.config.take_profit)
        else:
            return D.price * (1 - self.config.take_profit)

    def _generate_signal(self, price: float) -> Optional[HarmonicSignal]:
        """
        Génère un signal de trading.

        Args:
            price: Prix actuel

        Returns:
            Optional[HarmonicSignal]: Signal généré
        """
        if not self.patterns:
            return None

        if self.position == 0:
            # Recherche du meilleur motif
            best_pattern = max(self.patterns, key=lambda x: x.quality)

            if best_pattern.quality < self.config.min_pattern_quality:
                return None

            # Vérification de la proximité du prix
            if abs(price - best_pattern.entry_price) / price < 0.01:
                # Direction basée sur le motif
                if best_pattern.name in ['gartley', 'bat', 'butterfly', 'crab']:
                    # Bullish pattern
                    if best_pattern.quality > 0.7:
                        return HarmonicSignal(
                            timestamp=datetime.now(),
                            symbol=self.config.symbol,
                            signal_type='buy',
                            price=price,
                            pattern_name=best_pattern.name,
                            pattern_quality=best_pattern.quality,
                            confidence=best_pattern.quality,
                            reason="harmonic_pattern_bullish",
                        )
                    else:
                        return HarmonicSignal(
                            timestamp=datetime.now(),
                            symbol=self.config.symbol,
                            signal_type='sell',
                            price=price,
                            pattern_name=best_pattern.name,
                            pattern_quality=best_pattern.quality,
                            confidence=best_pattern.quality,
                            reason="harmonic_pattern_bearish",
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

    def _create_exit_signal(self, price: float, reason: str) -> HarmonicSignal:
        """Crée un signal de sortie"""
        return HarmonicSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='exit',
            price=price,
            pattern_name='',
            pattern_quality=0.0,
            confidence=0.8,
            reason=reason,
        )

    def _open_position(self, signal: HarmonicSignal) -> None:
        """Ouvre une position"""
        if signal.signal_type == 'buy':
            self.position = self.config.position_size
        elif signal.signal_type == 'sell':
            self.position = -self.config.position_size

        self.position_entry_price = signal.price
        self.position_entry_time = signal.timestamp

        logger.info(f"Position ouverte: {signal.signal_type} @ {signal.price:.2f} (pattern: {signal.pattern_name})")

    def _close_position(self, signal: HarmonicSignal) -> None:
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
            'pattern_name': signal.pattern_name,
            'pattern_quality': signal.pattern_quality,
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
            'pattern_success_rate': sum(1 for t in self.trade_history if t.get('pattern_name', '') != '') / max(1, len(self.trade_history)),
        }


def create_harmonic_patterns_strategy(
    symbol: str = "BTC-USD",
    lookback_period: int = 100,
    min_pattern_quality: float = 0.7,
    **kwargs
) -> HarmonicPatternsStrategy:
    """
    Factory pour créer une stratégie de motifs harmoniques.

    Args:
        symbol: Symbole
        lookback_period: Période de contexte
        min_pattern_quality: Qualité minimum du motif
        **kwargs: Arguments supplémentaires

    Returns:
        HarmonicPatternsStrategy: Stratégie de motifs harmoniques
    """
    config = HarmonicPatternConfig(
        symbol=symbol,
        lookback_period=lookback_period,
        min_pattern_quality=min_pattern_quality,
        **kwargs
    )
    return HarmonicPatternsStrategy(config)


__all__ = [
    'HarmonicPatternsStrategy',
    'HarmonicPatternConfig',
    'HarmonicPoint',
    'HarmonicPattern',
    'HarmonicSignal',
    'create_harmonic_patterns_strategy',
]
