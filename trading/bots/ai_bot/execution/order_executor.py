"""
NEXUS AI TRADING SYSTEM - Order Executor for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/execution/order_executor.py
Description: Exécuteur d'ordres pour le bot AI.
             Supporte l'exécution d'ordres Market, Limit, Stop, Stop-Limit,
             OCO, Iceberg, TWAP, VWAP, avec gestion avancée des erreurs,
             retry, fallback, et simulation de slippage.
             Intègre la gestion des risques et la validation des ordres.
"""

import asyncio
import logging
import time
import uuid
import random
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import threading

import numpy as np

from trading.bots.ai_bot.execution.order_validator import OrderValidator
from trading.bots.ai_bot.execution.order_splitter import OrderSplitter
from trading.bots.ai_bot.execution.order_router import OrderRouter
from trading.brokers.base import Broker, OrderSide, OrderType, OrderStatus
from shared.exceptions import OrderExecutionError
from shared.helpers.trading_helpers import validate_order, calculate_slippage
from shared.helpers.number_helpers import round_decimal

# Configuration du logging
logger = logging.getLogger(__name__)


class OrderExecutionStatus(Enum):
    """Statuts d'exécution des ordres."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class ExecutionStrategy(Enum):
    """Stratégies d'exécution."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    OCO = "oco"
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"
    ADAPTIVE = "adaptive"


@dataclass
class OrderConfig:
    """
    Configuration d'un ordre.
    """
    # Identifiants
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_order_id: Optional[str] = None
    
    # Ordre
    symbol: str = ""
    side: str = "BUY"  # BUY ou SELL
    order_type: str = "MARKET"
    quantity: float = 0.0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    
    # Paramètres avancés
    time_in_force: str = "GTC"  # GTC, IOC, FOK, DAY
    expire_time: Optional[datetime] = None
    post_only: bool = False
    reduce_only: bool = False
    
    # Paramètres de risque
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_slippage: float = 0.01  # 1%
    
    # Paramètres d'exécution
    execution_strategy: ExecutionStrategy = ExecutionStrategy.MARKET
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    
    # Métadonnées
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'id': self.id,
            'client_order_id': self.client_order_id,
            'symbol': self.symbol,
            'side': self.side,
            'order_type': self.order_type,
            'quantity': self.quantity,
            'price': self.price,
            'stop_price': self.stop_price,
            'limit_price': self.limit_price,
            'time_in_force': self.time_in_force,
            'expire_time': self.expire_time.isoformat() if self.expire_time else None,
            'post_only': self.post_only,
            'reduce_only': self.reduce_only,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'max_slippage': self.max_slippage,
            'execution_strategy': self.execution_strategy.value,
            'strategy_params': self.strategy_params,
            'metadata': self.metadata,
            'tags': self.tags
        }


@dataclass
class OrderExecutionResult:
    """
    Résultat d'exécution d'un ordre.
    """
    # Ordre original
    order: OrderConfig
    
    # Résultat
    status: OrderExecutionStatus
    executed_quantity: float = 0.0
    executed_price: float = 0.0
    avg_price: float = 0.0
    total_cost: float = 0.0
    total_commission: float = 0.0
    
    # Slippage
    expected_price: float = 0.0
    actual_price: float = 0.0
    slippage: float = 0.0
    slippage_pct: float = 0.0
    
    # Timing
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    execution_time: float = 0.0
    
    # Erreurs
    error: Optional[str] = None
    
    # Détails d'exécution
    execution_details: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'order': self.order.to_dict(),
            'status': self.status.value,
            'executed_quantity': self.executed_quantity,
            'executed_price': self.executed_price,
            'avg_price': self.avg_price,
            'total_cost': self.total_cost,
            'total_commission': self.total_commission,
            'expected_price': self.expected_price,
            'actual_price': self.actual_price,
            'slippage': self.slippage,
            'slippage_pct': self.slippage_pct,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'execution_time': self.execution_time,
            'error': self.error,
            'execution_details': self.execution_details
        }


@dataclass
class OrderExecutorConfig:
    """
    Configuration de l'exécuteur d'ordres.
    """
    # Paramètres généraux
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    
    # Paramètres de slippage
    default_slippage: float = 0.001  # 0.1%
    dynamic_slippage: bool = True
    
    # Paramètres de marché
    use_market_data: bool = True
    price_tolerance: float = 0.005  # 0.5%
    
    # Paramètres d'exécution
    execution_timeout: float = 60.0
    order_lifetime: float = 3600.0  # 1 heure
    
    # Paramètres de fallback
    fallback_on_error: bool = True
    fallback_to_market: bool = True
    
    # Paramètres de performance
    use_async: bool = True
    batch_execution: bool = False
    max_batch_size: int = 10
    
    # Paramètres de monitoring
    enable_monitoring: bool = True
    log_execution: bool = True
    
    def __post_init__(self):
        """Validation des paramètres."""
        if self.max_retries < 0:
            raise OrderExecutionError("max_retries doit être >= 0")
        
        if self.default_slippage < 0:
            raise OrderExecutionError("default_slippage doit être >= 0")


class OrderExecutor:
    """
    Exécuteur d'ordres pour le bot AI.
    """
    
    def __init__(
        self,
        config: Optional[OrderExecutorConfig] = None,
        broker: Optional[Broker] = None,
        validator: Optional[OrderValidator] = None,
        splitter: Optional[OrderSplitter] = None,
        router: Optional[OrderRouter] = None
    ):
        """
        Initialise l'exécuteur d'ordres.
        
        Args:
            config: Configuration de l'exécuteur.
            broker: Broker pour l'exécution.
            validator: Validateur d'ordres.
            splitter: Splitter d'ordres.
            router: Routeur d'ordres.
        """
        self.config = config or OrderExecutorConfig()
        self.broker = broker
        self.validator = validator or OrderValidator()
        self.splitter = splitter or OrderSplitter()
        self.router = router or OrderRouter()
        
        # Ordres en cours
        self._pending_orders: Dict[str, OrderConfig] = {}
        self._active_orders: Dict[str, OrderExecutionResult] = {}
        self._completed_orders: Dict[str, OrderExecutionResult] = {}
        self._order_history: deque = deque(maxlen=10000)
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'on_order_submitted': [],
            'on_order_filled': [],
            'on_order_cancelled': [],
            'on_order_rejected': [],
            'on_order_failed': [],
            'on_order_update': []
        }
        
        # État
        self._running = False
        self._lock = threading.Lock()
        self._execution_tasks: Dict[str, asyncio.Task] = {}
        
        # Statistiques
        self._stats = {
            'total_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'cancelled_orders': 0,
            'total_volume': 0.0,
            'total_slippage': 0.0,
            'avg_execution_time': 0.0
        }
        
        logger.info("OrderExecutor initialisé")
        logger.info(f"Max retries: {self.config.max_retries}")
        logger.info(f"Default slippage: {self.config.default_slippage:.4f}")
    
    # ============================================================
    # MÉTHODES PRINCIPALES
    # ============================================================
    
    async def execute_order(
        self,
        order: Union[OrderConfig, Dict[str, Any]],
        wait_for_fill: bool = True,
        timeout: Optional[float] = None
    ) -> OrderExecutionResult:
        """
        Exécute un ordre.
        
        Args:
            order: Ordre à exécuter.
            wait_for_fill: Attendre le remplissage.
            timeout: Timeout d'exécution.
            
        Returns:
            Résultat d'exécution.
        """
        # Conversion en OrderConfig
        if isinstance(order, dict):
            order = OrderConfig(**order)
        
        logger.info(f"Exécution de l'ordre {order.id}: {order.side} {order.quantity} {order.symbol}")
        
        # Validation
        if not self.validator.validate_order(order):
            raise OrderExecutionError(f"Ordre invalide: {order.id}")
        
        # Vérification du broker
        if not self.broker:
            # Mode simulation
            return await self._simulate_execution(order)
        
        # Exécution selon la stratégie
        try:
            if order.execution_strategy == ExecutionStrategy.MARKET:
                result = await self._execute_market_order(order)
            elif order.execution_strategy == ExecutionStrategy.LIMIT:
                result = await self._execute_limit_order(order)
            elif order.execution_strategy == ExecutionStrategy.STOP:
                result = await self._execute_stop_order(order)
            elif order.execution_strategy == ExecutionStrategy.STOP_LIMIT:
                result = await self._execute_stop_limit_order(order)
            elif order.execution_strategy == ExecutionStrategy.OCO:
                result = await self._execute_oco_order(order)
            elif order.execution_strategy == ExecutionStrategy.ICEBERG:
                result = await self._execute_iceberg_order(order)
            elif order.execution_strategy == ExecutionStrategy.TWAP:
                result = await self._execute_twap_order(order)
            elif order.execution_strategy == ExecutionStrategy.VWAP:
                result = await self._execute_vwap_order(order)
            elif order.execution_strategy == ExecutionStrategy.ADAPTIVE:
                result = await self._execute_adaptive_order(order)
            else:
                raise OrderExecutionError(f"Stratégie non supportée: {order.execution_strategy}")
            
            # Mise à jour des statistiques
            self._update_stats(result)
            
            # Notification
            self._notify_callbacks('on_order_update', result.to_dict())
            
            if result.status == OrderExecutionStatus.FILLED:
                self._notify_callbacks('on_order_filled', result.to_dict())
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur d'exécution de l'ordre {order.id}: {e}")
            
            # Fallback
            if self.config.fallback_on_error and self.config.fallback_to_market:
                logger.info(f"Fallback to market order for {order.id}")
                return await self._execute_market_order(order, fallback=True)
            
            raise OrderExecutionError(f"Erreur d'exécution: {e}")
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Annule un ordre.
        
        Args:
            order_id: ID de l'ordre.
            
        Returns:
            True si annulé.
        """
        logger.info(f"Annulation de l'ordre {order_id}")
        
        # Vérification de l'ordre
        if order_id not in self._active_orders:
            logger.warning(f"Ordre {order_id} non trouvé")
            return False
        
        # Annulation via le broker
        try:
            if self.broker:
                await self.broker.cancel_order(order_id)
            
            # Mise à jour du statut
            result = self._active_orders[order_id]
            result.status = OrderExecutionStatus.CANCELLED
            result.cancelled_at = datetime.now()
            
            # Déplacement vers les ordres terminés
            self._completed_orders[order_id] = result
            del self._active_orders[order_id]
            
            self._notify_callbacks('on_order_cancelled', result.to_dict())
            
            logger.info(f"Ordre {order_id} annulé")
            return True
            
        except Exception as e:
            logger.error(f"Erreur d'annulation de l'ordre {order_id}: {e}")
            return False
    
    async def get_order_status(self, order_id: str) -> Optional[OrderExecutionResult]:
        """
        Récupère le statut d'un ordre.
        
        Args:
            order_id: ID de l'ordre.
            
        Returns:
            Résultat d'exécution ou None.
        """
        if order_id in self._active_orders:
            return self._active_orders[order_id]
        elif order_id in self._completed_orders:
            return self._completed_orders[order_id]
        return None
    
    async def get_open_orders(self) -> List[OrderExecutionResult]:
        """
        Récupère les ordres ouverts.
        
        Returns:
            Liste des ordres ouverts.
        """
        return list(self._active_orders.values())
    
    async def get_order_history(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[OrderExecutionResult]:
        """
        Récupère l'historique des ordres.
        
        Args:
            limit: Nombre maximum d'ordres.
            offset: Décalage.
            
        Returns:
            Liste des ordres historiques.
        """
        history = list(self._completed_orders.values())
        history = sorted(history, key=lambda x: x.submitted_at, reverse=True)
        return history[offset:offset+limit]
    
    # ============================================================
    # STRATÉGIES D'EXÉCUTION
    # ============================================================
    
    async def _execute_market_order(
        self,
        order: OrderConfig,
        fallback: bool = False
    ) -> OrderExecutionResult:
        """
        Exécute un ordre au marché.
        
        Args:
            order: Ordre à exécuter.
            fallback: Est-ce un fallback.
            
        Returns:
            Résultat d'exécution.
        """
        result = OrderExecutionResult(order=order)
        result.submitted_at = datetime.now()
        result.expected_price = await self._get_market_price(order.symbol)
        
        try:
            # Exécution via le broker
            if self.broker:
                # Création de l'ordre broker
                broker_order = self._to_broker_order(order, 'MARKET')
                
                # Exécution avec retry
                execution = await self._execute_with_retry(
                    self.broker.execute_order,
                    broker_order
                )
                
                # Mise à jour du résultat
                result.status = OrderExecutionStatus.FILLED
                result.executed_quantity = execution.get('executed_qty', order.quantity)
                result.executed_price = execution.get('avg_price', result.expected_price)
                result.avg_price = result.executed_price
                result.total_cost = result.executed_quantity * result.avg_price
                result.total_commission = execution.get('commission', 0)
                result.filled_at = datetime.now()
                result.execution_time = (result.filled_at - result.submitted_at).total_seconds()
                
            else:
                # Simulation
                result = await self._simulate_execution(order)
            
            # Calcul du slippage
            result.actual_price = result.avg_price
            result.slippage = result.actual_price - result.expected_price
            result.slippage_pct = result.slippage / result.expected_price if result.expected_price > 0 else 0
            
            self._active_orders[order.id] = result
            self._notify_callbacks('on_order_submitted', result.to_dict())
            
            return result
            
        except Exception as e:
            result.status = OrderExecutionStatus.FAILED
            result.error = str(e)
            self._stats['failed_orders'] += 1
            raise OrderExecutionError(f"Erreur d'exécution market: {e}")
    
    async def _execute_limit_order(self, order: OrderConfig) -> OrderExecutionResult:
        """
        Exécute un ordre limit.
        
        Args:
            order: Ordre à exécuter.
            
        Returns:
            Résultat d'exécution.
        """
        result = OrderExecutionResult(order=order)
        result.submitted_at = datetime.now()
        
        try:
            if not order.price:
                order.price = await self._get_market_price(order.symbol)
            
            result.expected_price = order.price
            
            if self.broker:
                broker_order = self._to_broker_order(order, 'LIMIT')
                execution = await self._execute_with_retry(
                    self.broker.execute_order,
                    broker_order
                )
                
                if execution.get('status') == 'filled':
                    result.status = OrderExecutionStatus.FILLED
                    result.executed_quantity = execution.get('executed_qty', order.quantity)
                    result.executed_price = execution.get('avg_price', order.price)
                elif execution.get('status') == 'partially_filled':
                    result.status = OrderExecutionStatus.PARTIALLY_FILLED
                    result.executed_quantity = execution.get('executed_qty', 0)
                else:
                    result.status = OrderExecutionStatus.PENDING
                
                result.avg_price = result.executed_price
                result.total_cost = result.executed_quantity * result.avg_price
                result.filled_at = datetime.now() if result.status == OrderExecutionStatus.FILLED else None
                
            else:
                result = await self._simulate_limit_order(order)
            
            self._active_orders[order.id] = result
            return result
            
        except Exception as e:
            result.status = OrderExecutionStatus.FAILED
            result.error = str(e)
            raise OrderExecutionError(f"Erreur d'exécution limit: {e}")
    
    async def _execute_stop_order(self, order: OrderConfig) -> OrderExecutionResult:
        """
        Exécute un ordre stop.
        
        Args:
            order: Ordre à exécuter.
            
        Returns:
            Résultat d'exécution.
        """
        if not order.stop_price:
            raise OrderExecutionError("Stop price requis pour un ordre stop")
        
        # Vérification du prix
        current_price = await self._get_market_price(order.symbol)
        
        if order.side == 'BUY' and current_price >= order.stop_price:
            # Trigger - devient market order
            return await self._execute_market_order(order)
        elif order.side == 'SELL' and current_price <= order.stop_price:
            # Trigger - devient market order
            return await self._execute_market_order(order)
        
        # En attente de trigger
        result = OrderExecutionResult(order=order)
        result.status = OrderExecutionStatus.PENDING
        result.submitted_at = datetime.now()
        result.expected_price = order.stop_price
        
        self._active_orders[order.id] = result
        
        # Surveillance du prix
        asyncio.create_task(self._monitor_stop_order(order.id))
        
        return result
    
    async def _execute_stop_limit_order(self, order: OrderConfig) -> OrderExecutionResult:
        """
        Exécute un ordre stop-limit.
        
        Args:
            order: Ordre à exécuter.
            
        Returns:
            Résultat d'exécution.
        """
        if not order.stop_price or not order.limit_price:
            raise OrderExecutionError("Stop et limit price requis")
        
        result = OrderExecutionResult(order=order)
        result.status = OrderExecutionStatus.PENDING
        result.submitted_at = datetime.now()
        result.expected_price = order.stop_price
        
        self._active_orders[order.id] = result
        
        # Surveillance du prix
        asyncio.create_task(self._monitor_stop_limit_order(order.id))
        
        return result
    
    async def _execute_oco_order(self, order: OrderConfig) -> OrderExecutionResult:
        """
        Exécute un ordre OCO (One-Cancels-Other).
        
        Args:
            order: Ordre à exécuter.
            
        Returns:
            Résultat d'exécution.
        """
        if not order.stop_loss or not order.take_profit:
            raise OrderExecutionError("Stop loss et take profit requis")
        
        # Création des ordres enfants
        stop_order = OrderConfig(
            id=f"{order.id}_stop",
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            stop_price=order.stop_loss,
            order_type='STOP',
            execution_strategy=ExecutionStrategy.STOP
        )
        
        limit_order = OrderConfig(
            id=f"{order.id}_limit",
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.take_profit,
            order_type='LIMIT',
            execution_strategy=ExecutionStrategy.LIMIT
        )
        
        # Exécution des deux ordres
        results = []
        for child_order in [stop_order, limit_order]:
            result = await self.execute_order(child_order, wait_for_fill=False)
            results.append(result)
        
        # Si l'un est rempli, annuler l'autre
        if any(r.status == OrderExecutionStatus.FILLED for r in results):
            for r in results:
                if r.status != OrderExecutionStatus.FILLED:
                    await self.cancel_order(r.order.id)
        
        return results[0] if results else None
    
    async def _execute_iceberg_order(self, order: OrderConfig) -> OrderExecutionResult:
        """
        Exécute un ordre iceberg.
        
        Args:
            order: Ordre à exécuter.
            
        Returns:
            Résultat d'exécution.
        """
        visible_size = order.strategy_params.get('visible_size', order.quantity * 0.1)
        
        result = OrderExecutionResult(order=order)
        result.status = OrderExecutionStatus.PENDING
        result.submitted_at = datetime.now()
        
        total_executed = 0
        
        while total_executed < order.quantity:
            remaining = order.quantity - total_executed
            chunk = min(visible_size, remaining)
            
            # Ordre enfant
            child_order = OrderConfig(
                id=f"{order.id}_chunk_{len(result.execution_details)}",
                symbol=order.symbol,
                side=order.side,
                quantity=chunk,
                price=order.price,
                order_type=order.order_type,
                execution_strategy=ExecutionStrategy.MARKET
            )
            
            child_result = await self.execute_order(child_order, wait_for_fill=True)
            
            result.execution_details.append(child_result.to_dict())
            total_executed += child_result.executed_quantity
            
            # Attendre avant le prochain chunk
            await asyncio.sleep(order.strategy_params.get('interval', 1.0))
        
        result.status = OrderExecutionStatus.FILLED
        result.executed_quantity = total_executed
        result.filled_at = datetime.now()
        
        return result
    
    async def _execute_twap_order(self, order: OrderConfig) -> OrderExecutionResult:
        """
        Exécute un ordre TWAP (Time-Weighted Average Price).
        
        Args:
            order: Ordre à exécuter.
            
        Returns:
            Résultat d'exécution.
        """
        duration = order.strategy_params.get('duration', 3600)  # 1 heure par défaut
        intervals = order.strategy_params.get('intervals', 10)
        
        chunk_size = order.quantity / intervals
        interval_time = duration / intervals
        
        result = OrderExecutionResult(order=order)
        result.status = OrderExecutionStatus.PENDING
        result.submitted_at = datetime.now()
        
        total_executed = 0
        
        for i in range(intervals):
            chunk = min(chunk_size, order.quantity - total_executed)
            
            child_order = OrderConfig(
                id=f"{order.id}_twap_{i}",
                symbol=order.symbol,
                side=order.side,
                quantity=chunk,
                order_type='MARKET',
                execution_strategy=ExecutionStrategy.MARKET
            )
            
            child_result = await self.execute_order(child_order, wait_for_fill=True)
            
            result.execution_details.append(child_result.to_dict())
            total_executed += child_result.executed_quantity
            
            if i < intervals - 1:
                await asyncio.sleep(interval_time)
        
        result.status = OrderExecutionStatus.FILLED
        result.executed_quantity = total_executed
        result.filled_at = datetime.now()
        
        # Calcul du prix moyen
        total_cost = sum(d['total_cost'] for d in result.execution_details)
        result.avg_price = total_cost / total_executed if total_executed > 0 else 0
        
        return result
    
    async def _execute_vwap_order(self, order: OrderConfig) -> OrderExecutionResult:
        """
        Exécute un ordre VWAP (Volume-Weighted Average Price).
        
        Args:
            order: Ordre à exécuter.
            
        Returns:
            Résultat d'exécution.
        """
        # Similaire à TWAP mais avec ajustement par volume
        # Pour la simulation, on utilise TWAP avec des poids aléatoires
        duration = order.strategy_params.get('duration', 3600)
        intervals = order.strategy_params.get('intervals', 10)
        
        # Poids basés sur le volume (simulé)
        weights = np.random.dirichlet(np.ones(intervals))
        
        result = OrderExecutionResult(order=order)
        result.status = OrderExecutionStatus.PENDING
        result.submitted_at = datetime.now()
        
        total_executed = 0
        
        for i, weight in enumerate(weights):
            chunk = order.quantity * weight
            
            child_order = OrderConfig(
                id=f"{order.id}_vwap_{i}",
                symbol=order.symbol,
                side=order.side,
                quantity=chunk,
                order_type='MARKET',
                execution_strategy=ExecutionStrategy.MARKET
            )
            
            child_result = await self.execute_order(child_order, wait_for_fill=True)
            
            result.execution_details.append(child_result.to_dict())
            total_executed += child_result.executed_quantity
        
        result.status = OrderExecutionStatus.FILLED
        result.executed_quantity = total_executed
        result.filled_at = datetime.now()
        
        # Calcul du prix moyen
        total_cost = sum(d['total_cost'] for d in result.execution_details)
        result.avg_price = total_cost / total_executed if total_executed > 0 else 0
        
        return result
    
    async def _execute_adaptive_order(self, order: OrderConfig) -> OrderExecutionResult:
        """
        Exécute un ordre adaptatif (choix dynamique de la stratégie).
        
        Args:
            order: Ordre à exécuter.
            
        Returns:
            Résultat d'exécution.
        """
        # Analyse des conditions de marché
        current_price = await self._get_market_price(order.symbol)
        volatility = await self._get_volatility(order.symbol)
        
        # Choix de la stratégie
        if volatility > 0.02:  # Volatilité élevée
            # Utiliser limit orders
            order.execution_strategy = ExecutionStrategy.LIMIT
            order.price = current_price * (0.995 if order.side == 'BUY' else 1.005)
        elif order.quantity > 1000:  # Gros ordre
            # Utiliser TWAP
            order.execution_strategy = ExecutionStrategy.TWAP
            order.strategy_params['duration'] = 1800
            order.strategy_params['intervals'] = 5
        else:
            # Market order
            order.execution_strategy = ExecutionStrategy.MARKET
        
        logger.info(f"Stratégie adaptative choisie: {order.execution_strategy.value}")
        
        # Exécution avec la stratégie choisie
        return await self.execute_order(order, wait_for_fill=True)
    
    # ============================================================
    # MONITORING DES ORDRES
    # ============================================================
    
    async def _monitor_stop_order(self, order_id: str) -> None:
        """
        Surveille un ordre stop.
        
        Args:
            order_id: ID de l'ordre.
        """
        result = self._active_orders.get(order_id)
        if not result:
            return
        
        order = result.order
        
        while True:
            try:
                current_price = await self._get_market_price(order.symbol)
                
                if order.side == 'BUY' and current_price >= order.stop_price:
                    # Trigger - exécution market
                    await self._execute_market_order(order)
                    break
                elif order.side == 'SELL' and current_price <= order.stop_price:
                    # Trigger - exécution market
                    await self._execute_market_order(order)
                    break
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Erreur de monitoring stop {order_id}: {e}")
                await asyncio.sleep(5)
    
    async def _monitor_stop_limit_order(self, order_id: str) -> None:
        """
        Surveille un ordre stop-limit.
        
        Args:
            order_id: ID de l'ordre.
        """
        result = self._active_orders.get(order_id)
        if not result:
            return
        
        order = result.order
        
        while True:
            try:
                current_price = await self._get_market_price(order.symbol)
                
                if order.side == 'BUY' and current_price >= order.stop_price:
                    # Trigger - exécution limit
                    await self._execute_limit_order(order)
                    break
                elif order.side == 'SELL' and current_price <= order.stop_price:
                    # Trigger - exécution limit
                    await self._execute_limit_order(order)
                    break
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Erreur de monitoring stop-limit {order_id}: {e}")
                await asyncio.sleep(5)
    
    # ============================================================
    # SIMULATION
    # ============================================================
    
    async def _simulate_execution(self, order: OrderConfig) -> OrderExecutionResult:
        """
        Simule l'exécution d'un ordre.
        
        Args:
            order: Ordre à simuler.
            
        Returns:
            Résultat simulé.
        """
        result = OrderExecutionResult(order=order)
        result.submitted_at = datetime.now()
        
        # Prix attendu
        result.expected_price = await self._get_market_price(order.symbol)
        
        # Slippage simulé
        slippage = np.random.normal(0, self.config.default_slippage)
        execution_price = result.expected_price * (1 + slippage)
        
        # Commission simulée
        commission = execution_price * order.quantity * 0.001
        
        # Mise à jour du résultat
        result.status = OrderExecutionStatus.FILLED
        result.executed_quantity = order.quantity
        result.executed_price = execution_price
        result.avg_price = execution_price
        result.total_cost = execution_price * order.quantity + commission
        result.total_commission = commission
        result.filled_at = datetime.now()
        result.execution_time = (result.filled_at - result.submitted_at).total_seconds()
        
        # Slippage
        result.actual_price = execution_price
        result.slippage = result.actual_price - result.expected_price
        result.slippage_pct = result.slippage / result.expected_price if result.expected_price > 0 else 0
        
        self._active_orders[order.id] = result
        
        logger.info(f"Ordre {order.id} simulé: {order.side} {order.quantity} @ {execution_price:.4f}")
        
        return result
    
    async def _simulate_limit_order(self, order: OrderConfig) -> OrderExecutionResult:
        """
        Simule un ordre limit.
        
        Args:
            order: Ordre à simuler.
            
        Returns:
            Résultat simulé.
        """
        result = OrderExecutionResult(order=order)
        result.submitted_at = datetime.now()
        result.expected_price = order.price
        
        # Probabilité de remplissage basée sur l'écart au marché
        current_price = await self._get_market_price(order.symbol)
        price_diff = abs(current_price - order.price) / current_price
        
        fill_probability = max(0, 1 - price_diff * 100)
        
        if random.random() < fill_probability:
            # Rempli
            result.status = OrderExecutionStatus.FILLED
            result.executed_quantity = order.quantity
            result.executed_price = order.price
            result.avg_price = order.price
            result.total_cost = order.price * order.quantity
            result.filled_at = datetime.now()
        else:
            # En attente
            result.status = OrderExecutionStatus.PENDING
        
        return result
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    async def _get_market_price(self, symbol: str) -> float:
        """
        Récupère le prix de marché.
        
        Args:
            symbol: Symbole.
            
        Returns:
            Prix de marché.
        """
        if self.broker:
            try:
                ticker = await self.broker.get_ticker(symbol)
                return ticker.get('last_price', 100.0)
            except:
                pass
        
        # Prix simulé
        return 100.0 + random.uniform(-1, 1)
    
    async def _get_volatility(self, symbol: str) -> float:
        """
        Récupère la volatilité.
        
        Args:
            symbol: Symbole.
            
        Returns:
            Volatilité.
        """
        # Volatilité simulée
        return random.uniform(0.005, 0.03)
    
    async def _execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Exécute une fonction avec retry.
        
        Args:
            func: Fonction à exécuter.
            *args: Arguments.
            **kwargs: Arguments.
            
        Returns:
            Résultat de la fonction.
        """
        last_error = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                if self.config.use_async:
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                return result
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    wait_time = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Tentative {attempt+1} échouée, nouvelle tentative dans {wait_time}s")
                    await asyncio.sleep(wait_time)
        
        raise last_error
    
    def _to_broker_order(self, order: OrderConfig, order_type: str) -> Dict[str, Any]:
        """
        Convertit en ordre broker.
        
        Args:
            order: Ordre config.
            order_type: Type d'ordre broker.
            
        Returns:
            Dictionnaire de l'ordre.
        """
        broker_order = {
            'symbol': order.symbol,
            'side': order.side,
            'type': order_type,
            'quantity': order.quantity,
            'time_in_force': order.time_in_force
        }
        
        if order_type == 'LIMIT':
            broker_order['price'] = order.price
        elif order_type == 'STOP':
            broker_order['stop_price'] = order.stop_price
        elif order_type == 'STOP_LIMIT':
            broker_order['stop_price'] = order.stop_price
            broker_order['limit_price'] = order.limit_price
        
        return broker_order
    
    def _update_stats(self, result: OrderExecutionResult) -> None:
        """
        Met à jour les statistiques.
        
        Args:
            result: Résultat d'exécution.
        """
        self._stats['total_orders'] += 1
        
        if result.status == OrderExecutionStatus.FILLED:
            self._stats['successful_orders'] += 1
            self._stats['total_volume'] += result.executed_quantity
            self._stats['total_slippage'] += abs(result.slippage)
        elif result.status == OrderExecutionStatus.FAILED:
            self._stats['failed_orders'] += 1
        elif result.status == OrderExecutionStatus.CANCELLED:
            self._stats['cancelled_orders'] += 1
        
        # Moyenne glissante
        if self._stats['successful_orders'] > 0:
            self._stats['avg_execution_time'] = (
                self._stats['avg_execution_time'] * (self._stats['successful_orders'] - 1) +
                result.execution_time
            ) / self._stats['successful_orders']
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques.
        
        Returns:
            Statistiques d'exécution.
        """
        return self._stats.copy()
    
    # ============================================================
    # CALLBACKS
    # ============================================================
    
    def on_order_submitted(self, callback: Callable) -> None:
        """Ajoute un callback pour la soumission."""
        self._callbacks['on_order_submitted'].append(callback)
    
    def on_order_filled(self, callback: Callable) -> None:
        """Ajoute un callback pour le remplissage."""
        self._callbacks['on_order_filled'].append(callback)
    
    def on_order_cancelled(self, callback: Callable) -> None:
        """Ajoute un callback pour l'annulation."""
        self._callbacks['on_order_cancelled'].append(callback)
    
    def on_order_rejected(self, callback: Callable) -> None:
        """Ajoute un callback pour le rejet."""
        self._callbacks['on_order_rejected'].append(callback)
    
    def on_order_failed(self, callback: Callable) -> None:
        """Ajoute un callback pour l'échec."""
        self._callbacks['on_order_failed'].append(callback)
    
    def on_order_update(self, callback: Callable) -> None:
        """Ajoute un callback pour les mises à jour."""
        self._callbacks['on_order_update'].append(callback)
    
    def _notify_callbacks(self, event: str, data: Any) -> None:
        """
        Notifie les callbacks.
        
        Args:
            event: Nom de l'événement.
            data: Données.
        """
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Erreur dans le callback {event}: {e}")


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_order_executor(
    broker: Optional[Broker] = None,
    max_retries: int = 3,
    default_slippage: float = 0.001,
    **kwargs
) -> OrderExecutor:
    """
    Crée un exécuteur d'ordres.
    
    Args:
        broker: Broker pour l'exécution.
        max_retries: Nombre maximum de tentatives.
        default_slippage: Slippage par défaut.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Instance de l'exécuteur.
    """
    config = OrderExecutorConfig(
        max_retries=max_retries,
        default_slippage=default_slippage,
        **kwargs
    )
    return OrderExecutor(config, broker)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'OrderExecutor',
    'OrderConfig',
    'OrderExecutionResult',
    'OrderExecutionStatus',
    'ExecutionStrategy',
    'OrderExecutorConfig',
    'create_order_executor'
]

# ============================================================
# FIN DU FICHIER
# ============================================================
