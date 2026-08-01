# trading/bots/hedge_bot/hedge_bot_order_manager.py
# Advanced Order Management & Execution Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Order Manager Module - Module avancé de gestion des ordres et d'exécution pour le Hedge Bot.
Gère la création, la modification, l'annulation des ordres, le suivi des exécutions,
la gestion des risques, et l'optimisation des coûts de transaction.
"""

import asyncio
import json
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import concurrent.futures

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_order_manager")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)


# ============== ENUMS & TYPES ==============

class OrderType(Enum):
    """Types d'ordres."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    OCO = "oco"  # One-Cancels-Other
    BRACKET = "bracket"
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"
    POV = "pov"  # Percentage of Volume


class OrderSide(Enum):
    """Côtés des ordres."""
    BUY = "buy"
    SELL = "sell"
    HEDGE = "hedge"
    UNWIND = "unwind"
    REBALANCE = "rebalance"


class OrderStatus(Enum):
    """Statuts des ordres."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"
    PENDING_CANCEL = "pending_cancel"


class OrderTimeInForce(Enum):
    """Durées de validité des ordres."""
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate Or Cancel
    FOK = "fok"  # Fill Or Kill
    DAY = "day"
    GOOD_TILL_DATE = "good_till_date"


# ============== DATA MODELS ==============

@dataclass
class Order:
    """Modèle d'ordre."""
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    order_type: OrderType = OrderType.MARKET
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    time_in_force: OrderTimeInForce = OrderTimeInForce.GTC
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_price: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    parent_order_id: Optional[str] = None
    child_order_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    decision_id: Optional[str] = None
    execution_strategy: str = "default"
    risk_limit: float = 0.0
    max_slippage: float = 0.01
    
    def to_dict(self) -> Dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "order_type": self.order_type.value,
            "side": self.side.value,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "limit_price": self.limit_price,
            "take_profit_price": self.take_profit_price,
            "stop_loss_price": self.stop_loss_price,
            "time_in_force": self.time_in_force.value,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "average_price": self.average_price,
            "commission": self.commission,
            "slippage": self.slippage,
            "created_at": self.created_at.isoformat(),
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "parent_order_id": self.parent_order_id,
            "child_order_ids": self.child_order_ids,
            "metadata": self.metadata,
            "tags": self.tags,
            "decision_id": self.decision_id,
            "execution_strategy": self.execution_strategy,
            "risk_limit": self.risk_limit,
            "max_slippage": self.max_slippage
        }


@dataclass
class OrderBook:
    """Carnet d'ordres."""
    order_book_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    bids: List[Tuple[float, float]] = field(default_factory=list)  # (price, quantity)
    asks: List[Tuple[float, float]] = field(default_factory=list)  # (price, quantity)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderExecution:
    """Exécution d'ordre."""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    symbol: str = ""
    price: float = 0.0
    quantity: float = 0.0
    side: OrderSide = OrderSide.BUY
    commission: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class OrderManagerInterface(ABC):
    """Interface abstraite pour le gestionnaire d'ordres."""
    
    @abstractmethod
    async def create_order(self, order: Order) -> Order:
        """Crée un ordre."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Annule un ordre."""
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Récupère un ordre."""
        pass
    
    @abstractmethod
    async def get_order_book(self, symbol: str) -> OrderBook:
        """Récupère le carnet d'ordres."""
        pass


# ============== IMPLÉMENTATION ==============

class OrderManager(OrderManagerInterface):
    """
    Gestionnaire d'ordres avancé pour le Hedge Bot.
    Gère la création, le suivi et l'exécution des ordres.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des ordres
        self._orders: Dict[str, Order] = {}
        self._orders_lock = threading.RLock()
        
        # Gestion des exécutions
        self._executions: Dict[str, OrderExecution] = {}
        self._exec_lock = threading.RLock()
        
        # Cache des carnets d'ordres
        self._order_books: Dict[str, OrderBook] = {}
        self._book_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "orders_created": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_rejected": 0,
            "total_volume": 0.0,
            "total_commission": 0.0,
            "avg_fill_time_ms": 0.0,
            "fill_rate": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("OrderManager initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "max_orders_per_second": 10,
            "default_time_in_force": OrderTimeInForce.GTC,
            "default_order_type": OrderType.MARKET,
            "slippage_tolerance": 0.01,
            "max_position_size": 1000000,
            "min_order_size": 0.01,
            "fill_timeout": 60,
            "order_book_depth": 10,
            "enable_smart_routing": True,
            "enable_order_validation": True,
            "cache_size": 1000,
            "cache_ttl": 3600,
            "enable_cache": True
        }
    
    async def start(self) -> None:
        """Démarre le gestionnaire d'ordres."""
        logger.info("OrderManager starting...")
        self._is_running = True
        
        # Chargement des ordres
        await self._load_orders()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._order_monitor())
        asyncio.create_task(self._order_book_updater())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("OrderManager started")
    
    async def stop(self) -> None:
        """Arrête le gestionnaire d'ordres."""
        logger.info("OrderManager stopping...")
        self._is_running = False
        
        # Sauvegarde des ordres
        await self._save_orders()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("OrderManager stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_order(self, order: Order) -> Order:
        """Crée un ordre."""
        start_time = time.time()
        self._stats["orders_created"] += 1
        
        # Validation de l'ordre
        if self.config["enable_order_validation"]:
            await self._validate_order(order)
        
        # Soumission de l'ordre
        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now(timezone.utc)
        
        # Simulation d'exécution
        result = await self._execute_order(order)
        
        # Mise à jour du statut
        if result:
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.filled_at = datetime.now(timezone.utc)
            self._stats["orders_filled"] += 1
            self._stats["total_volume"] += order.quantity
            
            # Calcul du temps de remplissage
            fill_time = (order.filled_at - order.submitted_at).total_seconds() * 1000
            self._stats["avg_fill_time_ms"] = (
                self._stats["avg_fill_time_ms"] * 0.9 + fill_time * 0.1
            )
        else:
            order.status = OrderStatus.FAILED
            self._stats["orders_rejected"] += 1
        
        # Stockage de l'ordre
        with self._orders_lock:
            self._orders[order.order_id] = order
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"order:{order.order_id}",
                order.to_dict(),
                DataType.ORDER
            )
        
        # Mise à jour du taux de remplissage
        total = self._stats["orders_filled"] + self._stats["orders_rejected"]
        if total > 0:
            self._stats["fill_rate"] = self._stats["orders_filled"] / total
        
        logger.info(f"Order created: {order.symbol} {order.side.value} qty={order.quantity}")
        return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """Annule un ordre."""
        with self._orders_lock:
            order = self._orders.get(order_id)
            if not order:
                return False
            
            if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
                return False
            
            order.status = OrderStatus.CANCELLED
            order.cancelled_at = datetime.now(timezone.utc)
            self._stats["orders_cancelled"] += 1
        
        logger.info(f"Order cancelled: {order_id}")
        return True
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Récupère un ordre."""
        with self._orders_lock:
            return self._orders.get(order_id)
    
    async def get_order_book(self, symbol: str) -> OrderBook:
        """Récupère le carnet d'ordres."""
        # Vérification du cache
        with self._book_lock:
            if symbol in self._order_books:
                return self._order_books[symbol]
        
        # Récupération des données
        order_book = await self._fetch_order_book(symbol)
        
        with self._book_lock:
            self._order_books[symbol] = order_book
        
        return order_book
    
    # ========== MÉTHODES PRIVÉES - EXÉCUTION ==========
    
    async def _execute_order(self, order: Order) -> bool:
        """Exécute un ordre."""
        # Simulation d'exécution
        # Dans un système réel, on enverrait l'ordre à l'exchange
        
        if order.order_type == OrderType.MARKET:
            # Exécution immédiate
            return await self._execute_market_order(order)
        elif order.order_type == OrderType.LIMIT:
            # Exécution limitée
            return await self._execute_limit_order(order)
        elif order.order_type == OrderType.STOP:
            # Exécution stop
            return await self._execute_stop_order(order)
        else:
            return await self._execute_market_order(order)
    
    async def _execute_market_order(self, order: Order) -> bool:
        """Exécute un ordre marché."""
        # Simulation de slippage
        slippage = np.random.uniform(0, order.max_slippage)
        order.slippage = slippage
        
        # Prix d'exécution
        price = await self._get_market_price(order.symbol)
        order.average_price = price * (1 + slippage if order.side == OrderSide.BUY else 1 - slippage)
        order.commission = order.quantity * order.average_price * 0.001
        
        return True
    
    async def _execute_limit_order(self, order: Order) -> bool:
        """Exécute un ordre limité."""
        # Simulation d'exécution limitée
        price = await self._get_market_price(order.symbol)
        
        if order.side == OrderSide.BUY and price <= order.price:
            order.average_price = price
            order.commission = order.quantity * price * 0.001
            return True
        elif order.side == OrderSide.SELL and price >= order.price:
            order.average_price = price
            order.commission = order.quantity * price * 0.001
            return True
        
        return False
    
    async def _execute_stop_order(self, order: Order) -> bool:
        """Exécute un ordre stop."""
        # Simulation d'exécution stop
        price = await self._get_market_price(order.symbol)
        
        if order.side == OrderSide.BUY and price >= order.stop_price:
            order.average_price = price
            order.commission = order.quantity * price * 0.001
            return True
        elif order.side == OrderSide.SELL and price <= order.stop_price:
            order.average_price = price
            order.commission = order.quantity * price * 0.001
            return True
        
        return False
    
    async def _get_market_price(self, symbol: str) -> float:
        """Récupère le prix de marché."""
        # Dans un système réel, on interrogerait le marché
        return np.random.uniform(90, 110)
    
    async def _fetch_order_book(self, symbol: str) -> OrderBook:
        """Récupère le carnet d'ordres."""
        # Simulation de carnet d'ordres
        bid_prices = np.linspace(95, 100, 10)
        ask_prices = np.linspace(100, 105, 10)
        
        bids = [(p, np.random.uniform(1, 10)) for p in bid_prices]
        asks = [(p, np.random.uniform(1, 10)) for p in ask_prices]
        
        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks
        )
    
    # ========== MÉTHODES PRIVÉES - VALIDATION ==========
    
    async def _validate_order(self, order: Order) -> None:
        """Valide un ordre."""
        if order.quantity <= 0:
            raise ValueError("Invalid quantity")
        
        if order.quantity > self.config["max_position_size"]:
            raise ValueError(f"Quantity exceeds max position size: {order.quantity}")
        
        if order.quantity < self.config["min_order_size"]:
            raise ValueError(f"Quantity below min order size: {order.quantity}")
        
        if order.price and order.price <= 0:
            raise ValueError("Invalid price")
        
        if order.stop_price and order.stop_price <= 0:
            raise ValueError("Invalid stop price")
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _order_monitor(self) -> None:
        """Monitor les ordres en cours."""
        while self._is_running:
            await asyncio.sleep(self.config["fill_timeout"])
            
            try:
                with self._orders_lock:
                    for order in self._orders.values():
                        if order.status == OrderStatus.SUBMITTED:
                            # Vérification du timeout
                            if order.submitted_at:
                                age = (datetime.now(timezone.utc) - order.submitted_at).total_seconds()
                                if age > self.config["fill_timeout"]:
                                    order.status = OrderStatus.EXPIRED
                                    logger.warning(f"Order expired: {order.order_id}")
                
            except Exception as e:
                logger.error(f"Order monitor error: {e}")
    
    async def _order_book_updater(self) -> None:
        """Met à jour les carnets d'ordres."""
        while self._is_running:
            await asyncio.sleep(10)  # 10 secondes
            
            try:
                # Mise à jour des carnets d'ordres pour les symboles actifs
                with self._orders_lock:
                    symbols = set(order.symbol for order in self._orders.values())
                
                for symbol in symbols:
                    order_book = await self._fetch_order_book(symbol)
                    with self._book_lock:
                        self._order_books[symbol] = order_book
                
            except Exception as e:
                logger.error(f"Order book updater error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._book_lock:
                    if len(self._order_books) > self.config["cache_size"]:
                        keys = list(self._order_books.keys())
                        for key in keys[:len(self._order_books) - self.config["cache_size"]]:
                            del self._order_books[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._orders_lock:
                    self._stats["total_orders"] = len(self._orders)
                    pending = len([o for o in self._orders.values() if o.status == OrderStatus.SUBMITTED])
                    self._stats["pending_orders"] = pending
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "order:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_orders(self) -> None:
        """Charge les ordres existants."""
        try:
            if self.data_manager:
                orders_data = await self.data_manager.retrieve(
                    "orders:all",
                    DataType.ORDER
                )
                
                if orders_data:
                    for o_dict in orders_data:
                        order = self._deserialize_order(o_dict)
                        if order:
                            with self._orders_lock:
                                self._orders[order.order_id] = order
            
            logger.info(f"Loaded {len(self._orders)} orders")
            
        except Exception as e:
            logger.error(f"Load orders error: {e}"
    
    async def _save_orders(self) -> None:
        """Sauvegarde les ordres."""
        try:
            if self.data_manager:
                with self._orders_lock:
                    for order in self._orders.values():
                        await self.data_manager.store(
                            f"order:{order.order_id}",
                            order.to_dict(),
                            DataType.ORDER
                        )
            
            logger.info("Orders saved")
            
        except Exception as e:
            logger.error(f"Save orders error: {e}")
    
    def _deserialize_order(self, data: Dict) -> Optional[Order]:
        """Désérialise un ordre."""
        try:
            return Order(
                order_id=data.get("order_id", str(uuid.uuid4())),
                symbol=data.get("symbol", ""),
                order_type=OrderType(data.get("order_type", "market")),
                side=OrderSide(data.get("side", "buy")),
                quantity=data.get("quantity", 0.0),
                price=data.get("price"),
                stop_price=data.get("stop_price"),
                limit_price=data.get("limit_price"),
                take_profit_price=data.get("take_profit_price"),
                stop_loss_price=data.get("stop_loss_price"),
                time_in_force=OrderTimeInForce(data.get("time_in_force", "gtc")),
                status=OrderStatus(data.get("status", "pending")),
                filled_quantity=data.get("filled_quantity", 0.0),
                average_price=data.get("average_price", 0.0),
                commission=data.get("commission", 0.0),
                slippage=data.get("slippage", 0.0),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                submitted_at=datetime.fromisoformat(data.get("submitted_at")) if data.get("submitted_at") else None,
                filled_at=datetime.fromisoformat(data.get("filled_at")) if data.get("filled_at") else None,
                cancelled_at=datetime.fromisoformat(data.get("cancelled_at")) if data.get("cancelled_at") else None,
                expires_at=datetime.fromisoformat(data.get("expires_at")) if data.get("expires_at") else None,
                parent_order_id=data.get("parent_order_id"),
                child_order_ids=data.get("child_order_ids", []),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                decision_id=data.get("decision_id"),
                execution_strategy=data.get("execution_strategy", "default"),
                risk_limit=data.get("risk_limit", 0.0),
                max_slippage=data.get("max_slippage", 0.01)
            )
        except Exception as e:
            logger.error(f"Error deserializing order: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_orders(self, status: Optional[OrderStatus] = None) -> List[Order]:
        """Récupère les ordres."""
        with self._orders_lock:
            orders = list(self._orders.values())
            if status:
                orders = [o for o in orders if o.status == status]
            return sorted(orders, key=lambda o: o.created_at, reverse=True)
    
    async def get_executions(self, order_id: str) -> List[OrderExecution]:
        """Récupère les exécutions d'un ordre."""
        with self._exec_lock:
            return [e for e in self._executions.values() if e.order_id == order_id]
    
    async def create_bracket_order(self, config: Dict[str, Any]) -> List[Order]:
        """Crée un ordre bracket (ordre principal + stop loss + take profit)."""
        orders = []
        
        # Ordre principal
        main_order = Order(
            symbol=config.get("symbol", ""),
            side=OrderSide(config.get("side", "buy")),
            quantity=config.get("quantity", 0.0),
            price=config.get("price"),
            order_type=OrderType(config.get("order_type", "limit"))
        )
        main_order = await self.create_order(main_order)
        orders.append(main_order)
        
        # Stop loss
        stop_loss = config.get("stop_loss")
        if stop_loss:
            stop_order = Order(
                symbol=config.get("symbol", ""),
                side=OrderSide.SELL if main_order.side == OrderSide.BUY else OrderSide.BUY,
                quantity=config.get("quantity", 0.0),
                stop_price=stop_loss,
                order_type=OrderType.STOP,
                parent_order_id=main_order.order_id
            )
            stop_order = await self.create_order(stop_order)
            orders.append(stop_order)
        
        # Take profit
        take_profit = config.get("take_profit")
        if take_profit:
            tp_order = Order(
                symbol=config.get("symbol", ""),
                side=OrderSide.SELL if main_order.side == OrderSide.BUY else OrderSide.BUY,
                quantity=config.get("quantity", 0.0),
                price=take_profit,
                order_type=OrderType.LIMIT,
                parent_order_id=main_order.order_id
            )
            tp_order = await self.create_order(tp_order)
            orders.append(tp_order)
        
        return orders
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._orders_lock:
            self._stats["total_orders"] = len(self._orders)
        
        return self._stats.copy()


# ============== ORDER ROUTER ==============

class OrderRouter:
    """
    Routeur d'ordres intelligent.
    Optimise le routing des ordres vers les meilleurs exchanges.
    """
    
    def __init__(self, manager: OrderManager):
        self.manager = manager
        self._routing_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
    
    async def route_order(self, order: Order) -> Order:
        """Route un ordre vers le meilleur exchange."""
        # Analyse des conditions de marché
        order_book = await self.manager.get_order_book(order.symbol)
        
        # Sélection du meilleur exchange
        # Dans un système réel, on comparerait les prix et la liquidité
        
        # Simulation de routing
        if order.side == OrderSide.BUY:
            best_price = min(order_book.asks, key=lambda x: x[0])[0]
        else:
            best_price = max(order_book.bids, key=lambda x: x[0])[0]
        
        order.price = best_price
        
        return order


# ============== FACTORY ==============

class OrderManagerFactory:
    """Factory pour créer des composants de gestion d'ordres."""
    
    @staticmethod
    async def create_manager(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> OrderManager:
        """Crée un gestionnaire d'ordres."""
        manager = OrderManager(
            data_manager=data_manager,
            config=config
        )
        await manager.start()
        return manager
    
    @staticmethod
    def create_router(manager: OrderManager) -> OrderRouter:
        """Crée un routeur d'ordres."""
        return OrderRouter(manager)


# ============== EXPORT ==============

__all__ = [
    "OrderType",
    "OrderSide",
    "OrderStatus",
    "OrderTimeInForce",
    "Order",
    "OrderBook",
    "OrderExecution",
    "OrderManagerInterface",
    "OrderManager",
    "OrderRouter",
    "OrderManagerFactory"
]
