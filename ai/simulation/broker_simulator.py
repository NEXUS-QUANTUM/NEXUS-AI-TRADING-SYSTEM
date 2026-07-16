# ai/simulation/broker_simulator.py
"""
NEXUS AI TRADING SYSTEM - Broker Simulator
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import time
import random
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """Ordre de trading"""
    id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    order_type: str  # 'market', 'limit', 'stop', 'stop_limit'
    quantity: float
    price: float
    stop_price: Optional[float] = None
    status: str = 'pending'  # 'pending', 'filled', 'partially_filled', 'cancelled', 'rejected'
    filled_quantity: float = 0.0
    average_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side,
            'order_type': self.order_type,
            'quantity': self.quantity,
            'price': self.price,
            'stop_price': self.stop_price,
            'status': self.status,
            'filled_quantity': self.filled_quantity,
            'average_price': self.average_price,
            'timestamp': self.timestamp.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.metadata,
        }


@dataclass
class Position:
    """Position de trading"""
    symbol: str
    quantity: float
    average_price: float
    current_price: float
    pnl: float
    unrealized_pnl: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'average_price': self.average_price,
            'current_price': self.current_price,
            'pnl': self.pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class Account:
    """Compte de trading"""
    balance: float
    equity: float
    margin_used: float
    margin_available: float
    positions: Dict[str, Position]
    orders: List[Order]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'balance': self.balance,
            'equity': self.equity,
            'margin_used': self.margin_used,
            'margin_available': self.margin_available,
            'positions': {k: v.to_dict() for k, v in self.positions.items()},
            'orders': [o.to_dict() for o in self.orders],
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class BrokerSimulatorConfig:
    """Configuration pour Broker Simulator"""
    initial_balance: float = 10000.0
    commission: float = 0.001  # 0.1%
    slippage: float = 0.0005  # 0.05%
    margin_requirement: float = 0.5
    leverage: float = 1.0
    max_position_size: float = 100000.0
    min_position_size: float = 0.001
    order_execution_delay: float = 0.1  # secondes
    market_open: str = "09:30"
    market_close: str = "16:00"
    timezone: str = "UTC"
    use_realistic_execution: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'initial_balance': self.initial_balance,
            'commission': self.commission,
            'slippage': self.slippage,
            'margin_requirement': self.margin_requirement,
            'leverage': self.leverage,
            'max_position_size': self.max_position_size,
            'min_position_size': self.min_position_size,
            'order_execution_delay': self.order_execution_delay,
            'market_open': self.market_open,
            'market_close': self.market_close,
            'timezone': self.timezone,
            'use_realistic_execution': self.use_realistic_execution,
        }


class BrokerSimulator:
    """
    Simulateur de broker pour l'IA de trading.

    Features:
    - Exécution d'ordres
    - Gestion des positions
    - Gestion du compte
    - Slippage et commissions
    - Marge et levier

    Example:
        ```python
        config = BrokerSimulatorConfig(
            initial_balance=10000.0,
            commission=0.001,
            slippage=0.0005
        )
        broker = BrokerSimulator(config)

        # Place order
        order = broker.place_order(
            symbol='BTC-USD',
            side='buy',
            order_type='market',
            quantity=0.1
        )

        # Get account status
        account = broker.get_account()
        ```
    """

    def __init__(self, config: Optional[BrokerSimulatorConfig] = None):
        self.config = config or BrokerSimulatorConfig()

        # Initialisation du compte
        self._account = Account(
            balance=self.config.initial_balance,
            equity=self.config.initial_balance,
            margin_used=0.0,
            margin_available=self.config.initial_balance,
            positions={},
            orders=[],
        )

        self._order_counter = 0
        self._order_history: List[Order] = []
        self._trades: List[Dict[str, Any]] = []

        logger.info(f"BrokerSimulator initialisé avec {self.config.initial_balance:.2f}")

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Order:
        """
        Place un ordre.

        Args:
            symbol: Symbole de l'actif
            side: 'buy' ou 'sell'
            order_type: 'market', 'limit', 'stop', 'stop_limit'
            quantity: Quantité
            price: Prix (pour limit et stop_limit)
            stop_price: Prix de stop (pour stop et stop_limit)
            metadata: Métadonnées

        Returns:
            Order: Ordre placé
        """
        # Validation
        if quantity <= 0:
            raise ValueError("La quantité doit être positive")

        if side not in ['buy', 'sell']:
            raise ValueError("side doit être 'buy' ou 'sell'")

        if order_type not in ['market', 'limit', 'stop', 'stop_limit']:
            raise ValueError(f"Type d'ordre non supporté: {order_type}")

        if order_type in ['limit', 'stop_limit'] and price is None:
            raise ValueError(f"Prix requis pour {order_type}")

        if order_type in ['stop', 'stop_limit'] and stop_price is None:
            raise ValueError(f"Prix de stop requis pour {order_type}")

        # Vérification du solde
        estimated_cost = quantity * (price or 0)
        if side == 'buy' and estimated_cost > self._account.balance * self.config.leverage:
            raise ValueError(f"Solde insuffisant: {estimated_cost:.2f} > {self._account.balance:.2f}")

        # Création de l'ordre
        self._order_counter += 1
        order = Order(
            id=f"ORD_{self._order_counter:06d}",
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price or 0.0,
            stop_price=stop_price,
            status='pending',
            metadata=metadata or {},
            timestamp=datetime.now(),
        )

        self._account.orders.append(order)
        self._order_history.append(order)

        logger.info(f"Ordre placé: {order.id} ({side} {quantity} {symbol})")

        # Exécution
        if self.config.use_realistic_execution:
            time.sleep(self.config.order_execution_delay)

        self._execute_order(order)

        return order

    def _execute_order(self, order: Order) -> None:
        """
        Exécute un ordre.

        Args:
            order: Ordre à exécuter
        """
        # Simuler le slippage
        current_price = self._get_current_price(order.symbol)
        execution_price = self._apply_slippage(current_price, order.side)

        # Vérification des conditions
        if order.order_type == 'limit' and order.price is not None:
            if order.side == 'buy' and current_price > order.price:
                order.status = 'pending'
                return
            elif order.side == 'sell' and current_price < order.price:
                order.status = 'pending'
                return

        if order.order_type in ['stop', 'stop_limit'] and order.stop_price is not None:
            if order.side == 'buy' and current_price < order.stop_price:
                order.status = 'pending'
                return
            elif order.side == 'sell' and current_price > order.stop_price:
                order.status = 'pending'
                return

        # Exécution
        filled_quantity = min(order.quantity, self._get_available_quantity(order.symbol))

        if filled_quantity <= 0:
            order.status = 'rejected'
            order.updated_at = datetime.now()
            logger.warning(f"Ordre {order.id} rejeté: quantité insuffisante")
            return

        # Calcul du coût
        cost = filled_quantity * execution_price
        commission = cost * self.config.commission

        # Mise à jour du solde
        if order.side == 'buy':
            self._account.balance -= (cost + commission)
            self._update_position(order.symbol, filled_quantity, execution_price)
        else:  # sell
            self._account.balance += (cost - commission)
            self._update_position(order.symbol, -filled_quantity, execution_price)

        # Mise à jour de l'ordre
        order.status = 'filled'
        order.filled_quantity = filled_quantity
        order.average_price = execution_price
        order.updated_at = datetime.now()

        self._trades.append({
            'order_id': order.id,
            'symbol': order.symbol,
            'side': order.side,
            'quantity': filled_quantity,
            'price': execution_price,
            'commission': commission,
            'timestamp': order.updated_at,
        })

        logger.info(f"Ordre {order.id} exécuté: {filled_quantity} @ {execution_price:.2f}")

    def _update_position(self, symbol: str, quantity: float, price: float) -> None:
        """
        Met à jour une position.

        Args:
            symbol: Symbole
            quantity: Quantité à ajouter
            price: Prix
        """
        if symbol not in self._account.positions:
            self._account.positions[symbol] = Position(
                symbol=symbol,
                quantity=0.0,
                average_price=0.0,
                current_price=price,
                pnl=0.0,
                unrealized_pnl=0.0,
            )

        position = self._account.positions[symbol]

        # Mise à jour de la position
        old_quantity = position.quantity
        old_avg_price = position.average_price

        new_quantity = old_quantity + quantity

        if new_quantity != 0:
            if old_quantity == 0:
                position.average_price = price
            else:
                # Calcul du nouveau prix moyen
                total_value = old_quantity * old_avg_price + quantity * price
                position.average_price = total_value / new_quantity

        position.quantity = new_quantity
        position.current_price = price

        # P&L
        position.unrealized_pnl = position.quantity * (price - position.average_price)
        position.pnl = position.unrealized_pnl

        # Mise à jour du compte
        self._update_account()

    def _update_account(self) -> None:
        """Met à jour le compte"""
        total_equity = self._account.balance

        for symbol, position in self._account.positions.items():
            current_price = self._get_current_price(symbol)
            position.current_price = current_price
            position.unrealized_pnl = position.quantity * (current_price - position.average_price)
            position.pnl = position.unrealized_pnl
            total_equity += position.quantity * current_price

        self._account.equity = total_equity
        self._account.margin_used = sum(
            abs(p.quantity * p.current_price) * self.config.margin_requirement
            for p in self._account.positions.values()
        )
        self._account.margin_available = self._account.equity - self._account.margin_used

    def _get_current_price(self, symbol: str) -> float:
        """
        Récupère le prix actuel d'un symbole.

        Args:
            symbol: Symbole

        Returns:
            float: Prix actuel
        """
        # Simuler un prix avec du bruit
        base_price = 1000.0  # Prix de base
        random_walk = 1 + np.random.normal(0, 0.001)
        return base_price * random_walk

    def _apply_slippage(self, price: float, side: str) -> float:
        """
        Applique le slippage.

        Args:
            price: Prix
            side: 'buy' ou 'sell'

        Returns:
            float: Prix avec slippage
        """
        slippage_factor = 1 + np.random.normal(0, self.config.slippage)
        if side == 'buy':
            return price * (1 + self.config.slippage * slippage_factor)
        else:
            return price * (1 - self.config.slippage * slippage_factor)

    def _get_available_quantity(self, symbol: str) -> float:
        """
        Calcule la quantité disponible.

        Args:
            symbol: Symbole

        Returns:
            float: Quantité disponible
        """
        max_quantity = self._account.balance * self.config.leverage / self._get_current_price(symbol)
        return min(max_quantity, self.config.max_position_size)

    def cancel_order(self, order_id: str) -> bool:
        """
        Annule un ordre.

        Args:
            order_id: ID de l'ordre

        Returns:
            bool: True si annulé
        """
        for order in self._account.orders:
            if order.id == order_id and order.status in ['pending', 'partially_filled']:
                order.status = 'cancelled'
                order.updated_at = datetime.now()
                logger.info(f"Ordre {order_id} annulé")
                return True
        return False

    def get_account(self) -> Account:
        """
        Retourne l'état du compte.

        Returns:
            Account: Compte
        """
        self._update_account()
        return self._account

    def get_positions(self) -> List[Position]:
        """
        Retourne les positions.

        Returns:
            List[Position]: Positions
        """
        return list(self._account.positions.values())

    def get_orders(self, status: Optional[str] = None) -> List[Order]:
        """
        Retourne les ordres.

        Args:
            status: Statut des ordres (optionnel)

        Returns:
            List[Order]: Ordres
        """
        if status is None:
            return self._order_history
        return [o for o in self._order_history if o.status == status]

    def get_trades(self) -> List[Dict[str, Any]]:
        """
        Retourne l'historique des trades.

        Returns:
            List[Dict[str, Any]]: Historique des trades
        """
        return self._trades

    def get_performance(self) -> Dict[str, Any]:
        """
        Retourne les performances du broker.

        Returns:
            Dict[str, Any]: Performances
        """
        account = self.get_account()

        return {
            'initial_balance': self.config.initial_balance,
            'current_balance': account.balance,
            'equity': account.equity,
            'total_pnl': account.equity - self.config.initial_balance,
            'pnl_percent': (account.equity - self.config.initial_balance) / self.config.initial_balance * 100,
            'total_trades': len(self._trades),
            'win_rate': self._calculate_win_rate(),
            'open_positions': len(account.positions),
        }

    def _calculate_win_rate(self) -> float:
        """Calcule le taux de réussite"""
        if not self._trades:
            return 0.0

        winning_trades = sum(1 for t in self._trades if t.get('pnl', 0) > 0)
        return winning_trades / len(self._trades)

    def reset(self) -> None:
        """Réinitialise le broker"""
        self._account = Account(
            balance=self.config.initial_balance,
            equity=self.config.initial_balance,
            margin_used=0.0,
            margin_available=self.config.initial_balance,
            positions={},
            orders=[],
        )
        self._order_counter = 0
        self._order_history = []
        self._trades = []

        logger.info("BrokerSimulator réinitialisé")

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde l'état du broker.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si sauvegardé
        """
        try:
            import pickle
            import os

            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'account': self._account.to_dict(),
                'orders': [o.to_dict() for o in self._order_history],
                'trades': self._trades,
                'order_counter': self._order_counter,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"BrokerSimulator sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'BrokerSimulator':
        """
        Charge un broker simulé.

        Args:
            filepath: Chemin du fichier

        Returns:
            BrokerSimulator: Broker chargé
        """
        try:
            import pickle

            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = BrokerSimulatorConfig(**data['config'])
            broker = cls(config)

            # Restaurer l'état
            account_data = data.get('account')
            if account_data:
                broker._account = Account(
                    balance=account_data['balance'],
                    equity=account_data['equity'],
                    margin_used=account_data['margin_used'],
                    margin_available=account_data['margin_available'],
                    positions={},
                    orders=[],
                )

                for symbol, pos_data in account_data.get('positions', {}).items():
                    broker._account.positions[symbol] = Position(
                        symbol=symbol,
                        quantity=pos_data['quantity'],
                        average_price=pos_data['average_price'],
                        current_price=pos_data['current_price'],
                        pnl=pos_data['pnl'],
                        unrealized_pnl=pos_data['unrealized_pnl'],
                    )

            broker._order_counter = data.get('order_counter', 0)

            logger.info(f"BrokerSimulator chargé: {filepath}")
            return broker

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_broker_simulator(
    initial_balance: float = 10000.0,
    commission: float = 0.001,
    slippage: float = 0.0005,
    **kwargs
) -> BrokerSimulator:
    """
    Factory pour créer un simulateur de broker.

    Args:
        initial_balance: Solde initial
        commission: Commission
        slippage: Slippage
        **kwargs: Arguments supplémentaires

    Returns:
        BrokerSimulator: Simulateur de broker
    """
    config = BrokerSimulatorConfig(
        initial_balance=initial_balance,
        commission=commission,
        slippage=slippage,
        **kwargs
    )
    return BrokerSimulator(config)


__all__ = [
    'BrokerSimulator',
    'BrokerSimulatorConfig',
    'Order',
    'Position',
    'Account',
    'create_broker_simulator',
]
