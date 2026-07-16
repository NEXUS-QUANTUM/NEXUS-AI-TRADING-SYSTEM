# ai/simulation/order_book_simulator.py
"""
NEXUS AI TRADING SYSTEM - Order Book Simulator
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import random
import warnings
warnings.filterwarnings('ignore')

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class OrderBookLevel:
    """Niveau du carnet d'ordres"""
    price: float
    quantity: float
    orders: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'price': self.price,
            'quantity': self.quantity,
            'orders': self.orders,
        }


@dataclass
class OrderBookSnapshot:
    """Snapshot du carnet d'ordres"""
    timestamp: datetime
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    mid_price: float
    spread: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'bids': [b.to_dict() for b in self.bids],
            'asks': [a.to_dict() for a in self.asks],
            'mid_price': self.mid_price,
            'spread': self.spread,
        }


@dataclass
class OrderBookSimulatorConfig:
    """Configuration pour Order Book Simulator"""
    symbol: str = "BTC-USD"
    initial_price: float = 50000.0
    price_step: float = 10.0
    depth: int = 20
    spread: float = 0.001  # 0.1%
    tick_size: float = 0.01
    volume_scale: int = 100
    update_frequency: float = 0.1  # secondes
    volatility: float = 0.001
    order_arrival_rate: float = 5.0  # ordres par seconde
    order_cancellation_rate: float = 2.0
    random_seed: Optional[int] = 42

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'initial_price': self.initial_price,
            'price_step': self.price_step,
            'depth': self.depth,
            'spread': self.spread,
            'tick_size': self.tick_size,
            'volume_scale': self.volume_scale,
            'update_frequency': self.update_frequency,
            'volatility': self.volatility,
            'order_arrival_rate': self.order_arrival_rate,
            'order_cancellation_rate': self.order_cancellation_rate,
            'random_seed': self.random_seed,
        }


class OrderBookSimulator:
    """
    Simulateur de carnet d'ordres pour l'IA de trading.

    Features:
    - Bid-ask spread
    - Order arrival and cancellation
    - Price updates
    - Volume simulation
    - Level 2 data

    Example:
        ```python
        config = OrderBookSimulatorConfig(
            symbol='BTC-USD',
            initial_price=50000.0,
            depth=20,
            spread=0.001
        )
        simulator = OrderBookSimulator(config)

        # Get snapshot
        snapshot = simulator.get_snapshot()

        # Update
        simulator.update()
        ```
    """

    def __init__(self, config: Optional[OrderBookSimulatorConfig] = None):
        self.config = config or OrderBookSimulatorConfig()

        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)
            np.random.seed(self.config.random_seed)

        self.current_price = self.config.initial_price
        self.bids: List[OrderBookLevel] = []
        self.asks: List[OrderBookLevel] = []
        self.history: List[OrderBookSnapshot] = []
        self._last_update = datetime.now()

        self._initialize_order_book()

        logger.info(f"OrderBookSimulator initialisé pour {self.config.symbol}")

    def _initialize_order_book(self):
        """Initialise le carnet d'ordres"""
        self.bids = []
        self.asks = []

        bid_price = self.current_price * (1 - self.config.spread / 2)
        ask_price = self.current_price * (1 + self.config.spread / 2)

        for i in range(self.config.depth):
            bid_price = self.current_price - i * self.config.price_step
            ask_price = self.current_price + i * self.config.price_step

            if bid_price > 0:
                volume = random.randint(1, 10) * self.config.volume_scale
                self.bids.append(OrderBookLevel(
                    price=bid_price,
                    quantity=volume,
                    orders=random.randint(1, 5)
                ))

            if ask_price > 0:
                volume = random.randint(1, 10) * self.config.volume_scale
                self.asks.append(OrderBookLevel(
                    price=ask_price,
                    quantity=volume,
                    orders=random.randint(1, 5)
                ))

        self.bids.sort(key=lambda x: -x.price)
        self.asks.sort(key=lambda x: x.price)

    def update(self) -> OrderBookSnapshot:
        """
        Met à jour le carnet d'ordres.

        Returns:
            OrderBookSnapshot: Snapshot mis à jour
        """
        # Mise à jour du prix
        price_change = np.random.normal(0, self.config.volatility)
        self.current_price *= (1 + price_change)
        self.current_price = max(self.current_price, 0.01)

        # Arrivée de nouveaux ordres
        n_orders = np.random.poisson(self.config.order_arrival_rate * self.config.update_frequency)
        for _ in range(int(n_orders)):
            self._add_order()

        # Annulation d'ordres
        n_cancellations = np.random.poisson(self.config.order_cancellation_rate * self.config.update_frequency)
        for _ in range(int(n_cancellations)):
            self._cancel_order()

        # Mise à jour du carnet
        self._update_order_book()

        # Création du snapshot
        snapshot = OrderBookSnapshot(
            timestamp=datetime.now(),
            bids=self.bids.copy(),
            asks=self.asks.copy(),
            mid_price=self.current_price,
            spread=self.asks[0].price - self.bids[0].price if self.asks and self.bids else 0,
        )

        self.history.append(snapshot)

        return snapshot

    def _add_order(self):
        """Ajoute un ordre au carnet"""
        side = random.choice(['bid', 'ask'])
        price_deviation = np.random.exponential(1)
        volume = random.randint(1, 5) * self.config.volume_scale

        if side == 'bid':
            price = self.current_price * (1 - self.config.spread / 2 - price_deviation * self.config.spread)
            price = max(price, 0.01)
            order = OrderBookLevel(
                price=price,
                quantity=volume,
                orders=1
            )
            self.bids.append(order)
            self.bids.sort(key=lambda x: -x.price)
            self.bids = self.bids[:self.config.depth]
        else:
            price = self.current_price * (1 + self.config.spread / 2 + price_deviation * self.config.spread)
            order = OrderBookLevel(
                price=price,
                quantity=volume,
                orders=1
            )
            self.asks.append(order)
            self.asks.sort(key=lambda x: x.price)
            self.asks = self.asks[:self.config.depth]

    def _cancel_order(self):
        """Annule un ordre du carnet"""
        side = random.choice(['bid', 'ask'])

        if side == 'bid' and self.bids:
            idx = random.randint(0, len(self.bids) - 1)
            if self.bids[idx].quantity > 10:
                self.bids[idx].quantity -= random.randint(1, min(10, self.bids[idx].quantity // 2))
            else:
                self.bids.pop(idx)
        elif side == 'ask' and self.asks:
            idx = random.randint(0, len(self.asks) - 1)
            if self.asks[idx].quantity > 10:
                self.asks[idx].quantity -= random.randint(1, min(10, self.asks[idx].quantity // 2))
            else:
                self.asks.pop(idx)

    def _update_order_book(self):
        """Met à jour le carnet d'ordres"""
        # Rééquilibrage des volumes
        for level in self.bids:
            level.quantity *= (1 + np.random.normal(0, 0.01))
            level.quantity = max(level.quantity, 1)

        for level in self.asks:
            level.quantity *= (1 + np.random.normal(0, 0.01))
            level.quantity = max(level.quantity, 1)

        # Mise à jour des prix
        for level in self.bids:
            level.price *= (1 + np.random.normal(0, 0.0001))
            level.price = max(level.price, 0.01)

        for level in self.asks:
            level.price *= (1 + np.random.normal(0, 0.0001))
            level.price = max(level.price, 0.01)

        # Tri
        self.bids.sort(key=lambda x: -x.price)
        self.asks.sort(key=lambda x: x.price)

        # Troncature
        self.bids = self.bids[:self.config.depth]
        self.asks = self.asks[:self.config.depth]

    def get_snapshot(self) -> OrderBookSnapshot:
        """
        Retourne un snapshot du carnet d'ordres.

        Returns:
            OrderBookSnapshot: Snapshot
        """
        return OrderBookSnapshot(
            timestamp=datetime.now(),
            bids=self.bids.copy(),
            asks=self.asks.copy(),
            mid_price=self.current_price,
            spread=self.asks[0].price - self.bids[0].price if self.asks and self.bids else 0,
        )

    def get_best_bid(self) -> Optional[float]:
        """Retourne le meilleur bid"""
        if self.bids:
            return self.bids[0].price
        return None

    def get_best_ask(self) -> Optional[float]:
        """Retourne le meilleur ask"""
        if self.asks:
            return self.asks[0].price
        return None

    def get_depth(self, side: str) -> List[OrderBookLevel]:
        """
        Retourne la profondeur du carnet.

        Args:
            side: 'bid' ou 'ask'

        Returns:
            List[OrderBookLevel]: Profondeur
        """
        if side == 'bid':
            return self.bids.copy()
        elif side == 'ask':
            return self.asks.copy()
        else:
            raise ValueError("side doit être 'bid' ou 'ask'")

    def get_market_impact(self, quantity: float, side: str) -> Tuple[float, float]:
        """
        Calcule l'impact de marché.

        Args:
            quantity: Quantité
            side: 'buy' ou 'sell'

        Returns:
            Tuple[float, float]: (Prix d'exécution, Impact)
        """
        if side == 'buy':
            levels = self.asks
            price = levels[0].price
            remaining = quantity
            for level in levels:
                if remaining <= level.quantity:
                    return level.price * (1 + 0.001 * remaining / level.quantity), 0
                remaining -= level.quantity
        else:
            levels = self.bids
            price = levels[0].price
            remaining = quantity
            for level in levels:
                if remaining <= level.quantity:
                    return level.price * (1 - 0.001 * remaining / level.quantity), 0
                remaining -= level.quantity

        return price, quantity / (sum(l.quantity for l in levels) + 1)

    def plot(self, figsize: Tuple[int, int] = (12, 6)):
        """
        Affiche le carnet d'ordres.

        Args:
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        fig, ax = plt.subplots(figsize=figsize)

        # Bids
        if self.bids:
            bid_prices = [b.price for b in self.bids]
            bid_volumes = [b.quantity for b in self.bids]
            ax.barh(bid_prices, bid_volumes, color='green', alpha=0.7, label='Bids')

        # Asks
        if self.asks:
            ask_prices = [a.price for a in self.asks]
            ask_volumes = [a.quantity for a in self.asks]
            ax.barh(ask_prices, ask_volumes, color='red', alpha=0.7, label='Asks')

        ax.axhline(y=self.current_price, color='blue', linestyle='--', label='Mid Price')
        ax.set_xlabel('Volume')
        ax.set_ylabel('Price')
        ax.set_title(f'Order Book - {self.config.symbol}')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du carnet.

        Returns:
            Dict[str, Any]: Statistiques
        """
        return {
            'symbol': self.config.symbol,
            'current_price': self.current_price,
            'best_bid': self.get_best_bid(),
            'best_ask': self.get_best_ask(),
            'spread': self.get_best_ask() - self.get_best_bid() if self.get_best_bid() else 0,
            'bid_depth': len(self.bids),
            'ask_depth': len(self.asks),
            'total_bid_volume': sum(b.quantity for b in self.bids),
            'total_ask_volume': sum(a.quantity for a in self.asks),
        }


def create_order_book_simulator(
    symbol: str = "BTC-USD",
    initial_price: float = 50000.0,
    depth: int = 20,
    **kwargs
) -> OrderBookSimulator:
    """
    Factory pour créer un simulateur de carnet d'ordres.

    Args:
        symbol: Symbole
        initial_price: Prix initial
        depth: Profondeur
        **kwargs: Arguments supplémentaires

    Returns:
        OrderBookSimulator: Simulateur de carnet d'ordres
    """
    config = OrderBookSimulatorConfig(
        symbol=symbol,
        initial_price=initial_price,
        depth=depth,
        **kwargs
    )
    return OrderBookSimulator(config)


__all__ = [
    'OrderBookSimulator',
    'OrderBookSimulatorConfig',
    'OrderBookLevel',
    'OrderBookSnapshot',
    'create_order_book_simulator',
]
