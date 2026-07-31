# trading/bots/hedge_bot/hedge_bot_spot.py
# Advanced Spot Market Trading & Execution Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Spot Module - Module avancé de trading spot et d'exécution pour le Hedge Bot.
Gère les transactions sur le marché spot, l'optimisation des ordres, la gestion de la liquidité,
le routing intelligent et l'exécution des trades pour les stratégies de hedging.
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
logger = get_logger("hedge_bot_spot")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_execution import (
    Order, ExecutionResult, OrderStatus, OrderType, OrderSide
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType, HedgeStrategy
)


# ============== ENUMS & TYPES ==============

class SpotOrderType(Enum):
    """Types d'ordres spot."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    TRAILING_STOP = "trailing_stop"
    OCO = "oco"  # One-Cancels-Other
    BRACKET = "bracket"
    TWAP = "twap"
    VWAP = "vwap"


class SpotOrderStatus(Enum):
    """Statuts des ordres spot."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class SpotExecutionStrategy(Enum):
    """Stratégies d'exécution spot."""
    AGGRESSIVE = "aggressive"
    PASSIVE = "passive"
    ADAPTIVE = "adaptive"
    SMARTER = "smarter"
    VWAP = "vwap"
    TWAP = "twap"
    POV = "pov"
    ICEBERG = "iceberg"
    SNIPER = "sniper"
    DARK = "dark"
    HIDDEN = "hidden"


class SpotLiquidityProvider(Enum):
    """Fournisseurs de liquidité spot."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    DARK_POOL = "dark_pool"
    ECN = "ecn"
    MARKET_MAKER = "market_maker"
    SMART = "smart"


# ============== DATA MODELS ==============

@dataclass
class SpotOrder:
    """Ordre spot."""
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    side: str = ""  # buy, sell
    order_type: SpotOrderType = SpotOrderType.MARKET
    quantity: float = 0.0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    execution_strategy: SpotExecutionStrategy = SpotExecutionStrategy.ADAPTIVE
    liquidity_provider: SpotLiquidityProvider = SpotLiquidityProvider.SMART
    status: SpotOrderStatus = SpotOrderStatus.PENDING
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
    hedge_ratio: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "limit_price": self.limit_price,
            "take_profit_price": self.take_profit_price,
            "stop_loss_price": self.stop_loss_price,
            "execution_strategy": self.execution_strategy.value,
            "liquidity_provider": self.liquidity_provider.value,
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
            "hedge_ratio": self.hedge_ratio
        }


@dataclass
class SpotBalance:
    """Balance spot."""
    balance_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    asset: str = ""
    free: float = 0.0
    locked: float = 0.0
    total: float = 0.0
    usd_value: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpotPosition:
    """Position spot."""
    position_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    quantity: float = 0.0
    average_price: float = 0.0
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    is_hedged: bool = False
    hedge_ratio: float = 0.0


@dataclass
class SpotTrade:
    """Transaction spot."""
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    quantity: float = 0.0
    price: float = 0.0
    total: float = 0.0
    commission: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class SpotEngineInterface(ABC):
    """Interface abstraite pour le moteur spot."""
    
    @abstractmethod
    async def create_order(self, order: SpotOrder) -> SpotOrder:
        """Crée un ordre spot."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Annule un ordre spot."""
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[SpotOrder]:
        """Récupère un ordre spot."""
        pass
    
    @abstractmethod
    async def get_balance(self, asset: str) -> Optional[SpotBalance]:
        """Récupère la balance d'un actif."""
        pass


# ============== IMPLÉMENTATION ==============

class SpotEngine(SpotEngineInterface):
    """
    Moteur spot avancé pour le Hedge Bot.
    Gère le trading spot, les ordres, les balances et les positions.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des ordres
        self._orders: Dict[str, SpotOrder] = {}
        self._orders_lock = threading.RLock()
        
        # Gestion des balances
        self._balances: Dict[str, SpotBalance] = {}
        self._balances_lock = threading.RLock()
        
        # Gestion des positions
        self._positions: Dict[str, SpotPosition] = {}
        self._positions_lock = threading.RLock()
        
        # Gestion des trades
        self._trades: Dict[str, SpotTrade] = {}
        self._trades_lock = threading.RLock()
        
        # Cache de marché
        self._market_cache: Dict[str, Dict[str, float]] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "orders_created": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_rejected": 0,
            "total_volume": 0.0,
            "total_commission": 0.0,
            "total_pnl": 0.0
        }
        
        # Queue d'exécution
        self._execution_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("SpotEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "max_orders_per_second": 10,
            "default_timeout": 30,
            "slippage_tolerance": 0.01,
            "max_position_size": 1000000,
            "min_order_size": 0.01,
            "enable_smart_routing": True,
            "enable_adaptive_slippage": True,
            "enable_market_impact_model": True,
            "default_execution_strategy": SpotExecutionStrategy.ADAPTIVE,
            "default_liquidity_provider": SpotLiquidityProvider.SMART,
            "min_balance_required": 100,
            "max_slippage": 0.02,
            "default_currency": "USD"
        }
    
    async def start(self) -> None:
        """Démarre le moteur spot."""
        logger.info("SpotEngine starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._execution_processor())
        asyncio.create_task(self._market_data_updater())
        asyncio.create_task(self._position_monitor_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("SpotEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur spot."""
        logger.info("SpotEngine stopping...")
        self._is_running = False
        
        # Attente des ordres en cours
        await self._drain_orders()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("SpotEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_order(self, order: SpotOrder) -> SpotOrder:
        """Crée un ordre spot."""
        start_time = time.time()
        self._stats["orders_created"] += 1
        
        try:
            # Validation de l'ordre
            await self._validate_order(order)
            
            # Vérification de la balance
            if order.side == "buy":
                balance = await self.get_balance(order.symbol.split('-')[0])
                if not balance:
                    raise ValueError(f"Insufficient balance for {order.symbol}")
                
                required = order.quantity * (order.price or 0)
                if balance.free < required:
                    raise ValueError(f"Insufficient balance: {balance.free} < {required}")
            
            # Optimisation de l'exécution
            optimized_order = await self._optimize_execution(order)
            
            # Sélection de la stratégie
            strategy = await self._select_execution_strategy(optimized_order)
            
            # Exécution
            result = await self._execute_with_strategy(optimized_order, strategy)
            
            # Mise à jour des statistiques
            await self._update_statistics(result)
            
            # Stockage de l'ordre
            with self._orders_lock:
                self._orders[order.order_id] = result
            
            # Mise à jour de la position
            if result.status == SpotOrderStatus.FILLED:
                await self._update_position(result)
            
            # Log de l'exécution
            execution_time = (time.time() - start_time) * 1000
            logger.info(f"Spot order executed: {order.order_id} "
                       f"status={result.status.value} "
                       f"filled={result.filled_quantity} "
                       f"price={result.average_price} "
                       f"time={execution_time:.2f}ms")
            
            return result
            
        except Exception as e:
            self._stats["orders_rejected"] += 1
            logger.error(f"Order execution failed: {e}")
            
            order.status = SpotOrderStatus.FAILED
            order.metadata["error"] = str(e)
            return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """Annule un ordre spot."""
        with self._orders_lock:
            order = self._orders.get(order_id)
            if not order:
                return False
            
            if order.status in [SpotOrderStatus.FILLED, SpotOrderStatus.CANCELLED]:
                return False
            
            order.status = SpotOrderStatus.PENDING_CANCEL
        
        # Logique d'annulation
        # Dans un système réel, on enverrait la demande d'annulation au broker
        
        with self._orders_lock:
            order = self._orders.get(order_id)
            if order:
                order.status = SpotOrderStatus.CANCELLED
                order.cancelled_at = datetime.now(timezone.utc)
                self._stats["orders_cancelled"] += 1
        
        logger.info(f"Spot order cancelled: {order_id}")
        return True
    
    async def get_order(self, order_id: str) -> Optional[SpotOrder]:
        """Récupère un ordre spot."""
        with self._orders_lock:
            return self._orders.get(order_id)
    
    async def get_balance(self, asset: str) -> Optional[SpotBalance]:
        """Récupère la balance d'un actif."""
        with self._balances_lock:
            return self._balances.get(asset)
    
    # ========== MÉTHODES PRIVÉES - VALIDATION ==========
    
    async def _validate_order(self, order: SpotOrder) -> None:
        """Valide un ordre spot."""
        if order.quantity <= 0:
            raise ValueError(f"Invalid quantity: {order.quantity}")
        
        if order.quantity > self.config["max_position_size"]:
            raise ValueError(f"Quantity exceeds max position size: {order.quantity}")
        
        if order.quantity < self.config["min_order_size"]:
            raise ValueError(f"Quantity below min order size: {order.quantity}")
        
        if order.price and order.price <= 0:
            raise ValueError(f"Invalid price: {order.price}")
    
    # ========== MÉTHODES PRIVÉES - EXÉCUTION ==========
    
    async def _select_execution_strategy(self, order: SpotOrder) -> SpotExecutionStrategy:
        """Sélectionne la stratégie d'exécution."""
        # Analyse du contexte de marché
        market_data = await self._get_market_data(order.symbol)
        
        if not market_data:
            return self.config["default_execution_strategy"]
        
        # Sélection en fonction des conditions
        spread = market_data.get("spread", 0.001)
        volume = market_data.get("volume_24h", 0)
        volatility = market_data.get("volatility", 0.02)
        
        if spread > 0.005 or volatility > 0.05:
            return SpotExecutionStrategy.AGGRESSIVE
        elif spread < 0.001 and volume > 1000000:
            return SpotExecutionStrategy.PASSIVE
        else:
            return SpotExecutionStrategy.ADAPTIVE
    
    async def _execute_with_strategy(
        self,
        order: SpotOrder,
        strategy: SpotExecutionStrategy
    ) -> SpotOrder:
        """Exécute un ordre avec une stratégie."""
        if strategy == SpotExecutionStrategy.AGGRESSIVE:
            return await self._execute_aggressive(order)
        elif strategy == SpotExecutionStrategy.PASSIVE:
            return await self._execute_passive(order)
        elif strategy == SpotExecutionStrategy.ADAPTIVE:
            return await self._execute_adaptive(order)
        elif strategy == SpotExecutionStrategy.VWAP:
            return await self._execute_vwap(order)
        elif strategy == SpotExecutionStrategy.TWAP:
            return await self._execute_twap(order)
        elif strategy == SpotExecutionStrategy.ICEBERG:
            return await self._execute_iceberg(order)
        else:
            return await self._execute_adaptive(order)
    
    async def _execute_aggressive(self, order: SpotOrder) -> SpotOrder:
        """Exécution agressive."""
        market_data = await self._get_market_data(order.symbol)
        price = market_data.get("ask", 0) if order.side == "buy" else market_data.get("bid", 0)
        slippage = 0.001 * (1 + market_data.get("volatility", 0.02))
        
        order.status = SpotOrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.average_price = price * (1 + slippage if order.side == "buy" else 1 - slippage)
        order.filled_at = datetime.now(timezone.utc)
        order.commission = order.quantity * order.average_price * 0.001
        
        return order
    
    async def _execute_passive(self, order: SpotOrder) -> SpotOrder:
        """Exécution passive."""
        market_data = await self._get_market_data(order.symbol)
        price = market_data.get("bid", 0) if order.side == "buy" else market_data.get("ask", 0)
        slippage = 0.0005
        
        order.status = SpotOrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.average_price = price * (1 + slippage if order.side == "buy" else 1 - slippage)
        order.filled_at = datetime.now(timezone.utc)
        order.commission = order.quantity * order.average_price * 0.0005
        
        return order
    
    async def _execute_adaptive(self, order: SpotOrder) -> SpotOrder:
        """Exécution adaptative."""
        market_data = await self._get_market_data(order.symbol)
        
        urgency = 0.5 + 0.5 * (1 - market_data.get("liquidity", 0.7))
        price = market_data.get("mid", 0) * (1 + urgency * market_data.get("spread", 0.001))
        
        adapt_quantity = order.quantity * (0.7 + 0.3 * market_data.get("liquidity", 0.7))
        
        order.status = SpotOrderStatus.FILLED
        order.filled_quantity = adapt_quantity
        order.average_price = price
        order.filled_at = datetime.now(timezone.utc)
        order.commission = adapt_quantity * price * 0.0008
        
        return order
    
    async def _execute_vwap(self, order: SpotOrder) -> SpotOrder:
        """Exécution VWAP."""
        slices = 10
        slice_size = order.quantity / slices
        avg_price = 0
        
        for i in range(slices):
            price = await self._get_market_price(order.symbol)
            avg_price += price * slice_size
        
        avg_price /= order.quantity
        
        order.status = SpotOrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.average_price = avg_price
        order.filled_at = datetime.now(timezone.utc)
        order.commission = order.quantity * avg_price * 0.0006
        order.metadata["slices"] = slices
        
        return order
    
    async def _execute_twap(self, order: SpotOrder) -> SpotOrder:
        """Exécution TWAP."""
        time_horizon = 60
        slices = 12
        slice_size = order.quantity / slices
        avg_price = 0
        
        for i in range(slices):
            price = await self._get_market_price(order.symbol)
            avg_price += price * slice_size
            await asyncio.sleep(time_horizon / slices / 10)
        
        avg_price /= order.quantity
        
        order.status = SpotOrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.average_price = avg_price
        order.filled_at = datetime.now(timezone.utc)
        order.commission = order.quantity * avg_price * 0.0006
        order.metadata["slices"] = slices
        
        return order
    
    async def _execute_iceberg(self, order: SpotOrder) -> SpotOrder:
        """Exécution Iceberg."""
        chunk_size = order.quantity * 0.1
        chunks = int(order.quantity / chunk_size)
        avg_price = 0
        
        for i in range(chunks):
            price = await self._get_market_price(order.symbol)
            avg_price += price * chunk_size
            await asyncio.sleep(0.05)
        
        avg_price /= order.quantity
        
        order.status = SpotOrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.average_price = avg_price
        order.filled_at = datetime.now(timezone.utc)
        order.commission = order.quantity * avg_price * 0.0007
        
        return order
    
    async def _get_market_price(self, symbol: str) -> float:
        """Récupère le prix de marché."""
        market_data = await self._get_market_data(symbol)
        return market_data.get("mid", 0)
    
    async def _get_market_data(self, symbol: str) -> Dict[str, float]:
        """Récupère les données de marché."""
        with self._cache_lock:
            if symbol in self._market_cache:
                return self._market_cache[symbol]
        
        # Données par défaut
        data = {
            "bid": 100,
            "ask": 100.1,
            "mid": 100.05,
            "spread": 0.001,
            "volume_24h": 1000000,
            "volatility": 0.02,
            "liquidity": 0.7
        }
        
        # Récupération depuis le data manager
        if self.data_manager:
            market_data = await self.data_manager.retrieve(
                f"market:{symbol}:current",
                DataType.MARKET
            )
            if market_data:
                data.update(market_data)
        
        with self._cache_lock:
            self._market_cache[symbol] = data
        
        return data
    
    async def _optimize_execution(self, order: SpotOrder) -> SpotOrder:
        """Optimise l'exécution d'un ordre."""
        optimized = copy.deepcopy(order)
        
        # Optimisation du prix
        if optimized.order_type == SpotOrderType.LIMIT:
            market_data = await self._get_market_data(order.symbol)
            if optimized.side == "buy":
                optimized.price = market_data.get("ask", 0) * (1 - market_data.get("spread", 0.001) * 0.5)
            else:
                optimized.price = market_data.get("bid", 0) * (1 + market_data.get("spread", 0.001) * 0.5)
        
        return optimized
    
    async def _update_position(self, order: SpotOrder) -> None:
        """Met à jour la position."""
        with self._positions_lock:
            if order.symbol not in self._positions:
                self._positions[order.symbol] = SpotPosition(
                    symbol=order.symbol,
                    quantity=0,
                    average_price=0
                )
            
            position = self._positions[order.symbol]
            
            if order.side == "buy":
                # Achat
                total_cost = position.quantity * position.average_price
                new_cost = order.filled_quantity * order.average_price
                total_quantity = position.quantity + order.filled_quantity
                
                if total_quantity > 0:
                    position.average_price = (total_cost + new_cost) / total_quantity
                position.quantity = total_quantity
            else:
                # Vente
                position.quantity -= order.filled_quantity
                realized_pnl = (order.average_price - position.average_price) * order.filled_quantity
                position.realized_pnl += realized_pnl
            
            position.updated_at = datetime.now(timezone.utc)
    
    async def _update_statistics(self, order: SpotOrder) -> None:
        """Met à jour les statistiques."""
        if order.status == SpotOrderStatus.FILLED:
            self._stats["orders_filled"] += 1
            self._stats["total_volume"] += order.filled_quantity
            self._stats["total_commission"] += order.commission
            
            # Calcul du PnL
            if order.side == "sell":
                pnl = (order.average_price - order.metadata.get("avg_buy_price", order.average_price)) * order.filled_quantity
                self._stats["total_pnl"] += pnl
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _execution_processor(self) -> None:
        """Processus d'exécution des ordres."""
        rate_limiter = RateLimiter(self.config["max_orders_per_second"])
        
        while self._is_running:
            try:
                if self._execution_queue.empty():
                    await asyncio.sleep(0.01)
                    continue
                
                order = await self._execution_queue.get()
                await rate_limiter.wait()
                
                # Exécution de l'ordre
                result = await self.create_order(order)
                
                # Stockage du résultat
                if self.data_manager:
                    await self.data_manager.store(
                        f"spot:order:{result.order_id}",
                        result.to_dict(),
                        DataType.ORDER
                    )
                
            except Exception as e:
                logger.error(f"Execution processor error: {e}")
                await asyncio.sleep(0.1)
    
    async def _market_data_updater(self) -> None:
        """Met à jour les données de marché."""
        while self._is_running:
            await asyncio.sleep(1)
            
            try:
                if self.data_manager:
                    # Récupération des données de marché
                    market_data = await self.data_manager.retrieve(
                        "market:data",
                        DataType.MARKET
                    )
                    
                    if market_data:
                        with self._cache_lock:
                            for symbol, data in market_data.items():
                                self._market_cache[symbol] = data
                
            except Exception as e:
                logger.error(f"Market data updater error: {e}")
    
    async def _position_monitor_loop(self) -> None:
        """Boucle de monitoring des positions."""
        while self._is_running:
            await asyncio.sleep(5)
            
            try:
                with self._positions_lock:
                    for symbol, position in self._positions.items():
                        # Mise à jour du prix actuel
                        market_data = await self._get_market_data(symbol)
                        position.current_price = market_data.get("mid", 0)
                        
                        # Calcul du PnL
                        if position.quantity > 0:
                            position.unrealized_pnl = (position.current_price - position.average_price) * position.quantity
                            position.pnl = position.realized_pnl + position.unrealized_pnl
                            position.pnl_percent = (position.pnl / (position.average_price * position.quantity)) * 100
                
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._orders_lock:
                    self._stats["total_orders"] = len(self._orders)
                with self._positions_lock:
                    self._stats["total_positions"] = len(self._positions)
                with self._balances_lock:
                    self._stats["total_assets"] = len(self._balances)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "spot:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    async def _drain_orders(self) -> None:
        """Vide les ordres en attente."""
        while not self._execution_queue.empty():
            try:
                order = await self._execution_queue.get()
                order.status = SpotOrderStatus.CANCELLED
            except Exception:
                break
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_position(self, symbol: str) -> Optional[SpotPosition]:
        """Récupère une position."""
        with self._positions_lock:
            return self._positions.get(symbol)
    
    async def get_positions(self) -> List[SpotPosition]:
        """Récupère toutes les positions."""
        with self._positions_lock:
            return list(self._positions.values())
    
    async def get_orders(self, status: Optional[SpotOrderStatus] = None) -> List[SpotOrder]:
        """Récupère les ordres."""
        with self._orders_lock:
            orders = list(self._orders.values())
            if status:
                orders = [o for o in orders if o.status == status]
            return sorted(orders, key=lambda o: o.created_at, reverse=True)
    
    async def get_trades(self, symbol: Optional[str] = None) -> List[SpotTrade]:
        """Récupère les transactions."""
        with self._trades_lock:
            trades = list(self._trades.values())
            if symbol:
                trades = [t for t in trades if t.symbol == symbol]
            return sorted(trades, key=lambda t: t.timestamp, reverse=True)
    
    async def submit_order(self, order: SpotOrder) -> str:
        """Soumet un ordre à exécution."""
        with self._orders_lock:
            self._orders[order.order_id] = order
        
        await self._execution_queue.put(order)
        return order.order_id
    
    async def update_balance(self, asset: str, free: float, locked: float = 0) -> None:
        """Met à jour la balance d'un actif."""
        balance = SpotBalance(
            asset=asset,
            free=free,
            locked=locked,
            total=free + locked
        )
        
        with self._balances_lock:
            self._balances[asset] = balance
        
        if self.data_manager:
            await self.data_manager.store(
                f"spot:balance:{asset}",
                balance.to_dict(),
                DataType.BALANCE
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        return self._stats.copy()


# ============== RATE LIMITER ==============

class RateLimiter:
    """Rate limiter pour le contrôle du débit."""
    
    def __init__(self, max_per_second: float):
        self.max_per_second = max_per_second
        self._tokens = max_per_second
        self._last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def wait(self) -> None:
        """Attend jusqu'à ce qu'un token soit disponible."""
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_refill
            self._tokens = min(self.max_per_second, self._tokens + elapsed * self.max_per_second)
            self._last_refill = now
            
            if self._tokens < 1:
                wait_time = (1 - self._tokens) / self.max_per_second
                await asyncio.sleep(wait_time)
                self._tokens = 0
            else:
                self._tokens -= 1


# ============== FACTORY ==============

class SpotFactory:
    """Factory pour créer des composants spot."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> SpotEngine:
        """Crée un moteur spot."""
        engine = SpotEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "SpotOrderType",
    "SpotOrderStatus",
    "SpotExecutionStrategy",
    "SpotLiquidityProvider",
    "SpotOrder",
    "SpotBalance",
    "SpotPosition",
    "SpotTrade",
    "SpotEngineInterface",
    "SpotEngine",
    "RateLimiter",
    "SpotFactory"
]
