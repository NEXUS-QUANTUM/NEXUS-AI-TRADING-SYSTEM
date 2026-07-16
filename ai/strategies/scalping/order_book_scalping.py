# ai/strategies/scalping/order_book_scalping.py
"""
NEXUS AI TRADING SYSTEM - Order Book Scalping Strategy
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
    import websocket
    import threading
    import json
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class OrderBookLevel:
    """Niveau du carnet d'ordres"""
    price: float
    quantity: float


@dataclass
class OrderBookData:
    """Données du carnet d'ordres"""
    symbol: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: datetime
    bid_volume: float
    ask_volume: float
    imbalance: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'bids': [{'price': b.price, 'quantity': b.quantity} for b in self.bids],
            'asks': [{'price': a.price, 'quantity': a.quantity} for a in self.asks],
            'timestamp': self.timestamp.isoformat(),
            'bid_volume': self.bid_volume,
            'ask_volume': self.ask_volume,
            'imbalance': self.imbalance,
        }


@dataclass
class ScalpingSignal:
    """Signal de scalping"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    direction: str
    size: float
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'direction': self.direction,
            'size': self.size,
            'confidence': self.confidence,
            'reason': self.reason,
        }


@dataclass
class OrderBookScalpingConfig:
    """Configuration pour Order Book Scalping"""
    symbol: str = "BTC-USD"
    depth: int = 10
    min_spread: float = 0.001
    max_spread: float = 0.01
    volume_threshold: float = 100.0
    imbalance_threshold: float = 0.3
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
            'depth': self.depth,
            'min_spread': self.min_spread,
            'max_spread': self.max_spread,
            'volume_threshold': self.volume_threshold,
            'imbalance_threshold': self.imbalance_threshold,
            'position_size': self.position_size,
            'max_position': self.max_position,
            'take_profit': self.take_profit,
            'stop_loss': self.stop_loss,
            'max_holding_time': self.max_holding_time,
            'fee_rate': self.fee_rate,
            'update_interval': self.update_interval,
        }


class OrderBookScalpingStrategy:
    """
    Stratégie de scalping basée sur le carnet d'ordres.

    Features:
    - Order book analysis
    - Imbalance detection
    - Spread monitoring
    - Volume analysis
    - Fast execution

    Example:
        ```python
        config = OrderBookScalpingConfig(
            symbol='BTC-USD',
            depth=10,
            imbalance_threshold=0.3
        )
        strategy = OrderBookScalpingStrategy(config)

        # Update with order book data
        signal = strategy.update(order_book)
        ```
    """

    def __init__(self, config: Optional[OrderBookScalpingConfig] = None):
        self.config = config or OrderBookScalpingConfig()
        self.position: float = 0.0
        self.position_entry_price: float = 0.0
        self.position_entry_time: Optional[datetime] = None
        self.signals: List[ScalpingSignal] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.price_history: List[float] = []
        self.last_order_book: Optional[OrderBookData] = None

        logger.info(f"OrderBookScalpingStrategy initialisé pour {self.config.symbol}")

    def update(self, order_book: OrderBookData) -> Optional[ScalpingSignal]:
        """
        Met à jour la stratégie avec les données du carnet d'ordres.

        Args:
            order_book: Données du carnet d'ordres

        Returns:
            Optional[ScalpingSignal]: Signal généré
        """
        self.last_order_book = order_book
        self.price_history.append(order_book.bids[0].price if order_book.bids else 0.0)

        # Analyse du carnet d'ordres
        analysis = self._analyze_order_book(order_book)

        # Génération du signal
        signal = self._generate_signal(order_book, analysis)

        if signal:
            self.signals.append(signal)

            # Gestion de la position
            if signal.signal_type in ['buy', 'sell']:
                self._open_position(signal)
            elif signal.signal_type == 'exit':
                self._close_position(signal)

        # Gestion de la position ouverte
        if self.position != 0:
            self._manage_position(order_book)

        return signal

    def _analyze_order_book(self, order_book: OrderBookData) -> Dict[str, Any]:
        """
        Analyse le carnet d'ordres.

        Args:
            order_book: Données du carnet d'ordres

        Returns:
            Dict[str, Any]: Résultats de l'analyse
        """
        analysis = {
            'imbalance': 0.0,
            'spread': 0.0,
            'bid_volume': 0.0,
            'ask_volume': 0.0,
            'pressure': 0.0,
            'liquidity': 0.0,
        }

        if not order_book.bids or not order_book.asks:
            return analysis

        # Volume
        analysis['bid_volume'] = sum(b.quantity for b in order_book.bids[:5])
        analysis['ask_volume'] = sum(a.quantity for a in order_book.asks[:5])

        # Imbalance
        total_volume = analysis['bid_volume'] + analysis['ask_volume']
        if total_volume > 0:
            analysis['imbalance'] = (analysis['bid_volume'] - analysis['ask_volume']) / total_volume

        # Spread
        best_bid = order_book.bids[0].price
        best_ask = order_book.asks[0].price
        analysis['spread'] = (best_ask - best_bid) / best_bid

        # Pressure
        analysis['pressure'] = analysis['imbalance'] * 100

        # Liquidity
        analysis['liquidity'] = min(analysis['bid_volume'], analysis['ask_volume'])

        return analysis

    def _generate_signal(
        self,
        order_book: OrderBookData,
        analysis: Dict[str, Any]
    ) -> Optional[ScalpingSignal]:
        """
        Génère un signal de trading.

        Args:
            order_book: Données du carnet d'ordres
            analysis: Résultats de l'analyse

        Returns:
            Optional[ScalpingSignal]: Signal généré
        """
        if not order_book.bids or not order_book.asks:
            return None

        current_price = order_book.bids[0].price

        # Vérification des conditions
        if analysis['spread'] < self.config.min_spread:
            return None

        if analysis['spread'] > self.config.max_spread:
            return None

        if analysis['liquidity'] < self.config.volume_threshold:
            return None

        # Pas de position ouverte
        if self.position == 0:
            # Imbalance haussière
            if analysis['imbalance'] > self.config.imbalance_threshold:
                return ScalpingSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='buy',
                    price=order_book.asks[0].price,
                    direction='long',
                    size=self.config.position_size,
                    confidence=self._calculate_confidence(analysis),
                    reason="bullish_imbalance",
                )

            # Imbalance baissière
            elif analysis['imbalance'] < -self.config.imbalance_threshold:
                return ScalpingSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='sell',
                    price=order_book.bids[0].price,
                    direction='short',
                    size=self.config.position_size,
                    confidence=self._calculate_confidence(analysis),
                    reason="bearish_imbalance",
                )

        else:
            # Position ouverte
            # Take profit
            if self.position > 0:
                pnl_percent = (current_price - self.position_entry_price) / self.position_entry_price
                if pnl_percent >= self.config.take_profit:
                    return self._create_exit_signal(current_price, "take_profit")

                if pnl_percent <= -self.config.stop_loss:
                    return self._create_exit_signal(current_price, "stop_loss")

            elif self.position < 0:
                pnl_percent = (self.position_entry_price - current_price) / self.position_entry_price
                if pnl_percent >= self.config.take_profit:
                    return self._create_exit_signal(current_price, "take_profit")

                if pnl_percent <= -self.config.stop_loss:
                    return self._create_exit_signal(current_price, "stop_loss")

            # Max holding time
            if self.position_entry_time:
                holding_time = (datetime.now() - self.position_entry_time).total_seconds()
                if holding_time >= self.config.max_holding_time:
                    return self._create_exit_signal(current_price, "max_holding_time")

            # Exit on imbalance reversal
            if abs(analysis['imbalance']) < self.config.imbalance_threshold * 0.5:
                if self.position > 0 and analysis['imbalance'] < 0:
                    return self._create_exit_signal(current_price, "imbalance_reversal")
                elif self.position < 0 and analysis['imbalance'] > 0:
                    return self._create_exit_signal(current_price, "imbalance_reversal")

        return None

    def _calculate_confidence(self, analysis: Dict[str, Any]) -> float:
        """
        Calcule le niveau de confiance.

        Args:
            analysis: Résultats de l'analyse

        Returns:
            float: Niveau de confiance (0-1)
        """
        factors = []

        # Imbalance
        factors.append(min(1.0, abs(analysis['imbalance']) / self.config.imbalance_threshold))

        # Volume
        factors.append(min(1.0, analysis['liquidity'] / (self.config.volume_threshold * 2)))

        # Spread
        spread_factor = 1 - (analysis['spread'] / self.config.max_spread)
        factors.append(spread_factor)

        return np.mean(factors)

    def _create_exit_signal(self, price: float, reason: str) -> ScalpingSignal:
        """Crée un signal de sortie"""
        return ScalpingSignal(
            timestamp=datetime.now(),
            symbol=self.config.symbol,
            signal_type='exit',
            price=price,
            direction='',
            size=0.0,
            confidence=0.8,
            reason=reason,
        )

    def _open_position(self, signal: ScalpingSignal) -> None:
        """Ouvre une position"""
        if signal.signal_type == 'buy':
            self.position = signal.size
        elif signal.signal_type == 'sell':
            self.position = -signal.size

        self.position_entry_price = signal.price
        self.position_entry_time = signal.timestamp

        logger.info(f"Position ouverte: {signal.signal_type} @ {signal.price:.2f}")

    def _close_position(self, signal: ScalpingSignal) -> None:
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

    def _manage_position(self, order_book: OrderBookData) -> None:
        """Gère la position ouverte"""
        # Implémentation du trailing stop
        if self.position != 0:
            current_price = order_book.bids[0].price if order_book.bids else 0

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


def create_order_book_scalping(
    symbol: str = "BTC-USD",
    depth: int = 10,
    imbalance_threshold: float = 0.3,
    **kwargs
) -> OrderBookScalpingStrategy:
    """
    Factory pour créer une stratégie de scalping basée sur le carnet d'ordres.

    Args:
        symbol: Symbole
        depth: Profondeur du carnet
        imbalance_threshold: Seuil d'imbalance
        **kwargs: Arguments supplémentaires

    Returns:
        OrderBookScalpingStrategy: Stratégie de scalping
    """
    config = OrderBookScalpingConfig(
        symbol=symbol,
        depth=depth,
        imbalance_threshold=imbalance_threshold,
        **kwargs
    )
    return OrderBookScalpingStrategy(config)


__all__ = [
    'OrderBookScalpingStrategy',
    'OrderBookScalpingConfig',
    'OrderBookData',
    'OrderBookLevel',
    'ScalpingSignal',
    'create_order_book_scalping',
]
