"""
NEXUS AI TRADING SYSTEM - ARBITRAGE BOT ORDER MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des ordres pour le bot d'arbitrage.
Gestion des ordres, positions, suivi des exécutions, et reporting.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
from web3 import Web3

from ..arbitrage_bot import (
    ArbitrageBot,
    ArbitrageOpportunity,
    ArbitrageConfig,
    ExchangeType,
    ArbitrageType,
    ArbitrageStatus
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class OrderType(Enum):
    """Types d'ordres."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    OCO = "oco"  # One-Cancels-Other


class OrderSide(Enum):
    """Côtés d'ordre."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Statuts d'ordre."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class TimeInForce(Enum):
    """Durée de validité des ordres."""
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate Or Cancel
    FOK = "fok"  # Fill Or Kill
    DAY = "day"
    GOOD_TILL_DATE = "gtd"


@dataclass
class Order:
    """Modèle d'ordre."""
    order_id: UUID
    bot_id: UUID
    exchange: ExchangeType
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    limit_price: Optional[Decimal] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: Decimal = Decimal("0")
    average_price: Optional[Decimal] = None
    fees: Decimal = Decimal("0")
    fees_currency: Optional[str] = None
    exchange_order_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "order_id": str(self.order_id),
            "bot_id": str(self.bot_id),
            "exchange": self.exchange.value,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": str(self.quantity),
            "price": str(self.price) if self.price else None,
            "stop_price": str(self.stop_price) if self.stop_price else None,
            "limit_price": str(self.limit_price) if self.limit_price else None,
            "time_in_force": self.time_in_force.value,
            "status": self.status.value,
            "filled_quantity": str(self.filled_quantity),
            "average_price": str(self.average_price) if self.average_price else None,
            "fees": str(self.fees),
            "fees_currency": self.fees_currency,
            "exchange_order_id": self.exchange_order_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "metadata": self.metadata
        }


@dataclass
class Position:
    """Modèle de position."""
    position_id: UUID
    bot_id: UUID
    exchange: ExchangeType
    symbol: str
    side: OrderSide
    entry_price: Decimal
    current_price: Decimal
    quantity: Decimal
    entry_value: Decimal
    current_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    unrealized_pnl_percent: float
    realized_pnl_percent: float
    orders: List[Order] = field(default_factory=list)
    opened_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "position_id": str(self.position_id),
            "bot_id": str(self.bot_id),
            "exchange": self.exchange.value,
            "symbol": self.symbol,
            "side": self.side.value,
            "entry_price": str(self.entry_price),
            "current_price": str(self.current_price),
            "quantity": str(self.quantity),
            "entry_value": str(self.entry_value),
            "current_value": str(self.current_value),
            "unrealized_pnl": str(self.unrealized_pnl),
            "realized_pnl": str(self.realized_pnl),
            "unrealized_pnl_percent": self.unrealized_pnl_percent,
            "realized_pnl_percent": self.realized_pnl_percent,
            "orders": [o.to_dict() for o in self.orders],
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "metadata": self.metadata
        }


@dataclass
class OrderExecution:
    """Exécution d'ordre."""
    execution_id: UUID
    order_id: UUID
    exchange: ExchangeType
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    fee: Decimal
    fee_currency: str
    timestamp: datetime
    exchange_execution_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "execution_id": str(self.execution_id),
            "order_id": str(self.order_id),
            "exchange": self.exchange.value,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": str(self.quantity),
            "price": str(self.price),
            "fee": str(self.fee),
            "fee_currency": self.fee_currency,
            "timestamp": self.timestamp.isoformat(),
            "exchange_execution_id": self.exchange_execution_id,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE ORDER MANAGER
# ============================================================================

class ArbitrageBotOrderManager:
    """
    Gestionnaire d'ordres pour le bot d'arbitrage.
    """

    # Ordres max par bot
    MAX_ORDERS_PER_BOT = 1000
    
    # Timeout pour les ordres
    ORDER_TIMEOUT_SECONDS = 60

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le gestionnaire d'ordres.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        
        # Cache
        self._orders: Dict[UUID, Order] = {}
        self._positions: Dict[UUID, Position] = {}
        self._executions: Dict[UUID, OrderExecution] = {}
        self._order_by_exchange: Dict[str, Dict[str, UUID]] = {}
        
        # Ordres en attente de surveillance
        self._pending_orders: Set[UUID] = set()
        self._monitoring_tasks: Dict[UUID, asyncio.Task] = {}
        
        # Métriques
        self._metrics = {
            "total_orders": 0,
            "total_filled": 0,
            "total_cancelled": 0,
            "total_failed": 0,
            "total_positions": 0,
            "total_volume_usd": Decimal("0"),
            "total_fees_usd": Decimal("0"),
            "total_pnl_usd": Decimal("0"),
            "win_rate": 0.0,
            "by_exchange": {},
            "by_symbol": {}
        }

        logger.info("ArbitrageBotOrderManager initialisé avec succès")

    # ========================================================================
    # CRÉATION D'ORDRES
    # ========================================================================

    async def create_order(
        self,
        bot_id: UUID,
        exchange: ExchangeType,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        limit_price: Optional[Decimal] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        expiry_date: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ) -> Order:
        """
        Crée un nouvel ordre.

        Args:
            bot_id: ID du bot
            exchange: Exchange
            symbol: Symbole
            side: Côté
            quantity: Quantité
            order_type: Type d'ordre
            price: Prix
            stop_price: Prix de stop
            limit_price: Prix limite
            time_in_force: Durée de validité
            expiry_date: Date d'expiration
            metadata: Métadonnées

        Returns:
            Ordre créé
        """
        try:
            # Validation
            if quantity <= 0:
                raise ValueError("La quantité doit être positive")

            # Création de l'ordre
            order = Order(
                order_id=uuid4(),
                bot_id=bot_id,
                exchange=exchange,
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                limit_price=limit_price,
                time_in_force=time_in_force,
                status=OrderStatus.PENDING,
                expiry_date=expiry_date,
                metadata=metadata or {}
            )

            # Stockage
            self._orders[order.order_id] = order
            self._pending_orders.add(order.order_id)
            
            # Index par exchange
            exchange_key = f"{exchange.value}:{symbol}"
            if exchange_key not in self._order_by_exchange:
                self._order_by_exchange[exchange_key] = {}
            self._order_by_exchange[exchange_key][str(order.order_id)] = order.order_id

            # Mise à jour des métriques
            self._metrics["total_orders"] += 1
            if exchange.value not in self._metrics["by_exchange"]:
                self._metrics["by_exchange"][exchange.value] = 0
            self._metrics["by_exchange"][exchange.value] += 1

            # Sauvegarde dans Redis
            if self.redis:
                await self._save_order(order)

            # Lancement du monitoring
            self._monitoring_tasks[order.order_id] = asyncio.create_task(
                self._monitor_order(order.order_id)
            )

            logger.info(f"Ordre créé: {order.order_id} pour {bot_id}")
            return order

        except Exception as e:
            logger.error(f"Erreur lors de la création de l'ordre: {e}")
            raise

    async def create_batch_orders(
        self,
        bot_id: UUID,
        orders_data: List[Dict[str, Any]]
    ) -> List[Order]:
        """
        Crée un lot d'ordres.

        Args:
            bot_id: ID du bot
            orders_data: Données des ordres

        Returns:
            Liste des ordres créés
        """
        orders = []
        for data in orders_data:
            try:
                order = await self.create_order(
                    bot_id=bot_id,
                    exchange=data["exchange"],
                    symbol=data["symbol"],
                    side=data["side"],
                    quantity=data["quantity"],
                    order_type=data.get("order_type", OrderType.MARKET),
                    price=data.get("price"),
                    stop_price=data.get("stop_price"),
                    limit_price=data.get("limit_price"),
                    time_in_force=data.get("time_in_force", TimeInForce.GTC),
                    expiry_date=data.get("expiry_date"),
                    metadata=data.get("metadata")
                )
                orders.append(order)
            except Exception as e:
                logger.error(f"Erreur lors de la création d'un ordre du lot: {e}")
        
        return orders

    # ========================================================================
    # EXÉCUTION D'ORDRES
    # ========================================================================

    async def execute_order(
        self,
        order_id: UUID,
        exchange_client: Any
    ) -> bool:
        """
        Exécute un ordre sur l'exchange.

        Args:
            order_id: ID de l'ordre
            exchange_client: Client de l'exchange

        Returns:
            True si l'exécution a réussi
        """
        try:
            order = self._orders.get(order_id)
            if not order:
                logger.error(f"Ordre {order_id} non trouvé")
                return False

            if order.status != OrderStatus.PENDING:
                logger.warning(f"Ordre {order_id} déjà en cours d'exécution")
                return False

            # Préparation de l'ordre pour l'exchange
            exchange_order = await self._prepare_exchange_order(order, exchange_client)
            
            if not exchange_order:
                order.status = OrderStatus.FAILED
                return False

            # Envoi de l'ordre
            try:
                result = await exchange_client.place_order(exchange_order)
                order.exchange_order_id = result.get("order_id")
                order.status = OrderStatus.OPEN
                order.updated_at = datetime.now()

                # Enregistrement de l'exécution
                await self._record_execution(order, result)

                logger.info(f"Ordre {order_id} exécuté: {result.get('order_id')}")
                return True

            except Exception as e:
                logger.error(f"Erreur lors de l'exécution de l'ordre {order_id}: {e}")
                order.status = OrderStatus.FAILED
                order.metadata["error"] = str(e)
                self._metrics["total_failed"] += 1
                return False

        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de l'ordre: {e}")
            return False

    async def _prepare_exchange_order(
        self,
        order: Order,
        exchange_client: Any
    ) -> Dict[str, Any]:
        """
        Prépare un ordre pour l'exchange.

        Args:
            order: Ordre
            exchange_client: Client de l'exchange

        Returns:
            Ordre préparé
        """
        exchange_order = {
            "symbol": order.symbol,
            "side": order.side.value,
            "type": order.order_type.value,
            "quantity": float(order.quantity)
        }

        if order.order_type == OrderType.LIMIT:
            exchange_order["price"] = float(order.price or 0)
        elif order.order_type == OrderType.STOP_LOSS:
            exchange_order["stopPrice"] = float(order.stop_price or 0)
            exchange_order["price"] = float(order.limit_price or 0)
        elif order.order_type == OrderType.STOP_LIMIT:
            exchange_order["stopPrice"] = float(order.stop_price or 0)
            exchange_order["price"] = float(order.limit_price or 0)

        if order.time_in_force:
            exchange_order["timeInForce"] = order.time_in_force.value.upper()

        return exchange_order

    async def _record_execution(
        self,
        order: Order,
        result: Dict[str, Any]
    ) -> None:
        """
        Enregistre une exécution d'ordre.

        Args:
            order: Ordre
            result: Résultat de l'exécution
        """
        try:
            execution = OrderExecution(
                execution_id=uuid4(),
                order_id=order.order_id,
                exchange=order.exchange,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=Decimal(str(result.get("price", 0))),
                fee=Decimal(str(result.get("fee", 0))),
                fee_currency=result.get("fee_currency", order.symbol.split("/")[1]),
                timestamp=datetime.now(),
                exchange_execution_id=result.get("execution_id"),
                metadata=result.get("metadata", {})
            )

            self._executions[execution.execution_id] = execution

            # Mise à jour de l'ordre
            order.filled_quantity += order.quantity
            order.average_price = execution.price
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now()

            # Mise à jour des métriques
            self._metrics["total_filled"] += 1
            self._metrics["total_volume_usd"] += order.quantity * execution.price
            self._metrics["total_fees_usd"] += execution.fee

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de l'exécution: {e}")

    # ========================================================================
    # ANNULATION D'ORDRES
    # ========================================================================

    async def cancel_order(
        self,
        order_id: UUID,
        exchange_client: Any
    ) -> bool:
        """
        Annule un ordre.

        Args:
            order_id: ID de l'ordre
            exchange_client: Client de l'exchange

        Returns:
            True si l'annulation a réussi
        """
        try:
            order = self._orders.get(order_id)
            if not order:
                return False

            if order.status not in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
                return False

            # Annulation sur l'exchange
            if order.exchange_order_id:
                try:
                    await exchange_client.cancel_order(order.exchange_order_id)
                except Exception as e:
                    logger.error(f"Erreur lors de l'annulation sur l'exchange: {e}")

            order.status = OrderStatus.CANCELLED
            order.cancelled_at = datetime.now()
            order.updated_at = datetime.now()

            self._metrics["total_cancelled"] += 1

            # Arrêt du monitoring
            if order_id in self._monitoring_tasks:
                self._monitoring_tasks[order_id].cancel()
                del self._monitoring_tasks[order_id]

            logger.info(f"Ordre {order_id} annulé")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'annulation de l'ordre: {e}")
            return False

    async def cancel_all_orders(
        self,
        bot_id: UUID,
        exchange_client: Any
    ) -> int:
        """
        Annule tous les ordres d'un bot.

        Args:
            bot_id: ID du bot
            exchange_client: Client de l'exchange

        Returns:
            Nombre d'ordres annulés
        """
        cancelled = 0
        for order in list(self._orders.values()):
            if order.bot_id == bot_id and order.status in [OrderStatus.PENDING, OrderStatus.OPEN]:
                if await self.cancel_order(order.order_id, exchange_client):
                    cancelled += 1
        
        return cancelled

    # ========================================================================
    # GESTION DES POSITIONS
    # ========================================================================

    async def create_position(
        self,
        bot_id: UUID,
        exchange: ExchangeType,
        symbol: str,
        side: OrderSide,
        entry_price: Decimal,
        quantity: Decimal,
        orders: List[Order]
    ) -> Position:
        """
        Crée une position.

        Args:
            bot_id: ID du bot
            exchange: Exchange
            symbol: Symbole
            side: Côté
            entry_price: Prix d'entrée
            quantity: Quantité
            orders: Ordres associés

        Returns:
            Position créée
        """
        try:
            position = Position(
                position_id=uuid4(),
                bot_id=bot_id,
                exchange=exchange,
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                current_price=entry_price,
                quantity=quantity,
                entry_value=entry_price * quantity,
                current_value=entry_price * quantity,
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
                unrealized_pnl_percent=0.0,
                realized_pnl_percent=0.0,
                orders=orders,
                opened_at=datetime.now()
            )

            self._positions[position.position_id] = position
            self._metrics["total_positions"] += 1

            logger.info(f"Position créée: {position.position_id}")
            return position

        except Exception as e:
            logger.error(f"Erreur lors de la création de la position: {e}")
            raise

    async def update_position(
        self,
        position_id: UUID,
        current_price: Decimal
    ) -> Position:
        """
        Met à jour une position.

        Args:
            position_id: ID de la position
            current_price: Prix actuel

        Returns:
            Position mise à jour
        """
        try:
            position = self._positions.get(position_id)
            if not position:
                raise ValueError(f"Position {position_id} non trouvée")

            position.current_price = current_price
            position.current_value = position.quantity * current_price
            
            if position.side == OrderSide.BUY:
                position.unrealized_pnl = position.current_value - position.entry_value
            else:
                position.unrealized_pnl = position.entry_value - position.current_value
            
            position.unrealized_pnl_percent = float(position.unrealized_pnl / position.entry_value * 100) if position.entry_value > 0 else 0

            return position

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de la position: {e}")
            raise

    async def close_position(
        self,
        position_id: UUID,
        exit_price: Decimal,
        exit_orders: List[Order]
    ) -> Position:
        """
        Ferme une position.

        Args:
            position_id: ID de la position
            exit_price: Prix de sortie
            exit_orders: Ordres de sortie

        Returns:
            Position fermée
        """
        try:
            position = self._positions.get(position_id)
            if not position:
                raise ValueError(f"Position {position_id} non trouvée")

            position.current_price = exit_price
            position.current_value = position.quantity * exit_price
            
            if position.side == OrderSide.BUY:
                realized_pnl = position.current_value - position.entry_value
            else:
                realized_pnl = position.entry_value - position.current_value
            
            position.realized_pnl = realized_pnl
            position.realized_pnl_percent = float(realized_pnl / position.entry_value * 100) if position.entry_value > 0 else 0
            position.closed_at = datetime.now()
            position.orders.extend(exit_orders)

            # Mise à jour des métriques
            self._metrics["total_pnl_usd"] += realized_pnl
            
            # Mise à jour du win rate
            if realized_pnl > 0:
                self._metrics["win_rate"] = (self._metrics["win_rate"] * (self._metrics["total_positions"] - 1) + 1) / self._metrics["total_positions"]

            logger.info(f"Position {position_id} fermée: PnL = {realized_pnl}")
            return position

        except Exception as e:
            logger.error(f"Erreur lors de la fermeture de la position: {e}")
            raise

    # ========================================================================
    # SURVEILLANCE DES ORDRES
    # ========================================================================

    async def _monitor_order(self, order_id: UUID) -> None:
        """
        Surveille un ordre.

        Args:
            order_id: ID de l'ordre
        """
        try:
            start_time = time.time()
            
            while (time.time() - start_time) < self.ORDER_TIMEOUT_SECONDS:
                order = self._orders.get(order_id)
                if not order:
                    break

                if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.FAILED]:
                    break

                await asyncio.sleep(1)

            # Timeout
            order = self._orders.get(order_id)
            if order and order.status not in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.FAILED]:
                order.status = OrderStatus.EXPIRED
                logger.warning(f"Ordre {order_id} expiré")

        except asyncio.CancelledError:
            logger.info(f"Monitoring de l'ordre {order_id} annulé")
        except Exception as e:
            logger.error(f"Erreur lors du monitoring de l'ordre {order_id}: {e}")
        finally:
            if order_id in self._pending_orders:
                self._pending_orders.remove(order_id)

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_order(self, order_id: UUID) -> Optional[Order]:
        """
        Récupère un ordre.

        Args:
            order_id: ID de l'ordre

        Returns:
            Ordre ou None
        """
        return self._orders.get(order_id)

    async def get_orders(
        self,
        bot_id: Optional[UUID] = None,
        exchange: Optional[ExchangeType] = None,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Order]:
        """
        Récupère les ordres.

        Args:
            bot_id: Filtrer par bot
            exchange: Filtrer par exchange
            symbol: Filtrer par symbole
            status: Filtrer par statut
            limit: Nombre d'ordres
            offset: Décalage

        Returns:
            Liste des ordres
        """
        orders = list(self._orders.values())
        
        if bot_id:
            orders = [o for o in orders if o.bot_id == bot_id]
        if exchange:
            orders = [o for o in orders if o.exchange == exchange]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        if status:
            orders = [o for o in orders if o.status == status]
        
        orders.sort(key=lambda x: x.created_at, reverse=True)
        
        return orders[offset:offset + limit]

    async def get_position(self, position_id: UUID) -> Optional[Position]:
        """
        Récupère une position.

        Args:
            position_id: ID de la position

        Returns:
            Position ou None
        """
        return self._positions.get(position_id)

    async def get_positions(
        self,
        bot_id: Optional[UUID] = None,
        exchange: Optional[ExchangeType] = None,
        symbol: Optional[str] = None,
        open_only: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[Position]:
        """
        Récupère les positions.

        Args:
            bot_id: Filtrer par bot
            exchange: Filtrer par exchange
            symbol: Filtrer par symbole
            open_only: Positions ouvertes uniquement
            limit: Nombre de positions
            offset: Décalage

        Returns:
            Liste des positions
        """
        positions = list(self._positions.values())
        
        if bot_id:
            positions = [p for p in positions if p.bot_id == bot_id]
        if exchange:
            positions = [p for p in positions if p.exchange == exchange]
        if symbol:
            positions = [p for p in positions if p.symbol == symbol]
        if open_only:
            positions = [p for p in positions if p.closed_at is None]
        
        positions.sort(key=lambda x: x.opened_at, reverse=True)
        
        return positions[offset:offset + limit]

    # ========================================================================
    # STATISTIQUES ET REPORTING
    # ========================================================================

    async def get_statistics(
        self,
        bot_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Récupère les statistiques.

        Args:
            bot_id: ID du bot (optionnel)

        Returns:
            Statistiques
        """
        stats = self._metrics.copy()
        
        if bot_id:
            # Filtrer les statistiques par bot
            orders = [o for o in self._orders.values() if o.bot_id == bot_id]
            positions = [p for p in self._positions.values() if p.bot_id == bot_id]
            
            stats["total_orders"] = len(orders)
            stats["total_filled"] = len([o for o in orders if o.status == OrderStatus.FILLED])
            stats["total_cancelled"] = len([o for o in orders if o.status == OrderStatus.CANCELLED])
            stats["total_failed"] = len([o for o in orders if o.status == OrderStatus.FAILED])
            stats["total_positions"] = len(positions)
            stats["total_pnl_usd"] = sum(p.realized_pnl for p in positions)
            
            if positions:
                wins = len([p for p in positions if p.realized_pnl > 0])
                stats["win_rate"] = wins / len(positions) if positions else 0

        return stats

    # ========================================================================
    # MÉTHODES DE STOCKAGE
    # ========================================================================

    async def _save_order(self, order: Order) -> None:
        """
        Sauvegarde un ordre dans Redis.

        Args:
            order: Ordre à sauvegarder
        """
        try:
            key = f"order:{order.order_id}"
            await self.redis.setex(
                key,
                86400 * 7,  # 7 jours
                json.dumps(order.to_dict())
            )

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'ordre: {e}")

    async def _load_order(self, order_id: UUID) -> Optional[Order]:
        """
        Charge un ordre depuis Redis.

        Args:
            order_id: ID de l'ordre

        Returns:
            Ordre chargé
        """
        try:
            key = f"order:{order_id}"
            data = await self.redis.get(key)
            if data:
                order_dict = json.loads(data)
                return self._order_from_dict(order_dict)
            return None

        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'ordre: {e}")
            return None

    def _order_from_dict(self, data: Dict[str, Any]) -> Order:
        """
        Crée un ordre à partir d'un dictionnaire.

        Args:
            data: Données de l'ordre

        Returns:
            Ordre
        """
        return Order(
            order_id=UUID(data["order_id"]),
            bot_id=UUID(data["bot_id"]),
            exchange=ExchangeType(data["exchange"]),
            symbol=data["symbol"],
            side=OrderSide(data["side"]),
            order_type=OrderType(data["order_type"]),
            quantity=Decimal(data["quantity"]),
            price=Decimal(data["price"]) if data.get("price") else None,
            stop_price=Decimal(data["stop_price"]) if data.get("stop_price") else None,
            limit_price=Decimal(data["limit_price"]) if data.get("limit_price") else None,
            time_in_force=TimeInForce(data["time_in_force"]),
            status=OrderStatus(data["status"]),
            filled_quantity=Decimal(data["filled_quantity"]),
            average_price=Decimal(data["average_price"]) if data.get("average_price") else None,
            fees=Decimal(data["fees"]),
            fees_currency=data.get("fees_currency"),
            exchange_order_id=data.get("exchange_order_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            filled_at=datetime.fromisoformat(data["filled_at"]) if data.get("filled_at") else None,
            cancelled_at=datetime.fromisoformat(data["cancelled_at"]) if data.get("cancelled_at") else None,
            expiry_date=datetime.fromisoformat(data["expiry_date"]) if data.get("expiry_date") else None,
            metadata=data.get("metadata", {})
        )

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_orders": self._metrics["total_orders"],
                "total_filled": self._metrics["total_filled"],
                "total_cancelled": self._metrics["total_cancelled"],
                "total_failed": self._metrics["total_failed"],
                "total_positions": self._metrics["total_positions"],
                "total_volume_usd": float(self._metrics["total_volume_usd"]),
                "total_fees_usd": float(self._metrics["total_fees_usd"]),
                "total_pnl_usd": float(self._metrics["total_pnl_usd"]),
                "win_rate": self._metrics["win_rate"],
                "pending_orders": len(self._pending_orders),
                "open_positions": len([p for p in self._positions.values() if p.closed_at is None]),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de ArbitrageBotOrderManager...")
        
        # Annulation des tâches de monitoring
        for task in self._monitoring_tasks.values():
            task.cancel()
        
        self._orders.clear()
        self._positions.clear()
        self._executions.clear()
        self._order_by_exchange.clear()
        self._pending_orders.clear()
        self._monitoring_tasks.clear()
        
        logger.info("ArbitrageBotOrderManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_arbitrage_bot_order_manager(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None
) -> ArbitrageBotOrderManager:
    """
    Crée une instance du gestionnaire d'ordres.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API

    Returns:
        Instance du gestionnaire
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return ArbitrageBotOrderManager(
        redis_client=redis_client,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "OrderType",
    "OrderSide",
    "OrderStatus",
    "TimeInForce",
    "Order",
    "Position",
    "OrderExecution",
    "ArbitrageBotOrderManager",
    "create_arbitrage_bot_order_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du gestionnaire d'ordres."""
    print("=" * 60)
    print("NEXUS AI TRADING - ARBITRAGE BOT ORDER MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    order_manager = create_arbitrage_bot_order_manager()

    # Création d'un bot exemple
    bot_id = uuid4()
    print(f"\n✅ Bot ID: {bot_id}")

    # Création d'un ordre
    print(f"\n📝 Création d'un ordre...")
    order = await order_manager.create_order(
        bot_id=bot_id,
        exchange=ExchangeType.BINANCE,
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        order_type=OrderType.LIMIT,
        price=Decimal("50000"),
        metadata={"strategy": "arbitrage"}
    )

    print(f"   ID: {order.order_id}")
    print(f"   Symbole: {order.symbol}")
    print(f"   Côté: {order.side.value}")
    print(f"   Quantité: {order.quantity}")
    print(f"   Prix: {order.price}")

    # Création d'un lot d'ordres
    print(f"\n📦 Création d'un lot d'ordres...")
    orders_data = [
        {
            "exchange": ExchangeType.BINANCE,
            "symbol": "ETH/USDT",
            "side": OrderSide.BUY,
            "quantity": Decimal("0.5"),
            "order_type": OrderType.MARKET
        },
        {
            "exchange": ExchangeType.COINBASE,
            "symbol": "ETH/USDT",
            "side": OrderSide.SELL,
            "quantity": Decimal("0.5"),
            "order_type": OrderType.MARKET
        }
    ]
    
    batch_orders = await order_manager.create_batch_orders(bot_id, orders_data)
    print(f"   {len(batch_orders)} ordres créés")

    # Création d'une position
    print(f"\n📊 Création d'une position...")
    position = await order_manager.create_position(
        bot_id=bot_id,
        exchange=ExchangeType.BINANCE,
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        entry_price=Decimal("50000"),
        quantity=Decimal("0.1"),
        orders=[order]
    )
    print(f"   ID: {position.position_id}")
    print(f"   Entry Price: {position.entry_price}")
    print(f"   Quantity: {position.quantity}")

    # Mise à jour de la position
    print(f"\n🔄 Mise à jour de la position...")
    await order_manager.update_position(
        position.position_id,
        Decimal("52000")
    )
    print(f"   PnL non réalisé: {position.unrealized_pnl}")

    # Statistiques
    stats = await order_manager.get_statistics(bot_id)
    print(f"\n📈 Statistiques:")
    print(f"   Ordres: {stats['total_orders']}")
    print(f"   Positions: {stats['total_positions']}")
    print(f"   PnL total: ${stats['total_pnl_usd']:.2f}")

    # Santé du service
    health = await order_manager.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Ordres: {health['total_orders']}")
    print(f"   Positions ouvertes: {health['open_positions']}")
    print(f"   Taux de victoire: {health['win_rate']*100:.1f}%")

    # Fermeture
    await order_manager.close()

    print("\n" + "=" * 60)
    print("ArbitrageBotOrderManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import random
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
