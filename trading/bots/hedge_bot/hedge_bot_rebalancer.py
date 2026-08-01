# trading/bots/hedge_bot/hedge_bot_rebalancer.py
# Advanced Portfolio Rebalancing & Allocation Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Rebalancer Module - Module avancé de rééquilibrage de portefeuille et de gestion
d'allocation pour le Hedge Bot. Gère le rééquilibrage automatique, l'optimisation d'allocation,
les seuils de tolérance, les coûts de transaction et la gestion des flux de trésorerie.
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
logger = get_logger("hedge_bot_rebalancer")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)
from trading.bots.hedge_bot.hedge_bot_data_execution import (
    Order, ExecutionResult, OrderStatus
)


# ============== ENUMS & TYPES ==============

class RebalancingStrategy(Enum):
    """Stratégies de rééquilibrage."""
    CALENDAR = "calendar"              # Rééquilibrage calendaire
    THRESHOLD = "threshold"            # Rééquilibrage par seuil
    DYNAMIC = "dynamic"                # Rééquilibrage dynamique
    OPPORTUNISTIC = "opportunistic"    # Rééquilibrage opportuniste
    TARGET = "target"                  # Rééquilibrage vers cible
    SMART = "smart"                    # Rééquilibrage intelligent


class RebalancingTrigger(Enum):
    """Déclencheurs de rééquilibrage."""
    TIME = "time"                      # Basé sur le temps
    DEVIATION = "deviation"            # Basé sur la déviation
    CASH_FLOW = "cash_flow"            # Basé sur les flux de trésorerie
    SIGNAL = "signal"                  # Basé sur un signal
    VOLATILITY = "volatility"          # Basé sur la volatilité
    EVENT = "event"                    # Basé sur un événement


class RebalancingCost(Enum):
    """Méthodes de calcul des coûts."""
    FIXED = "fixed"                    # Coût fixe
    PERCENTAGE = "percentage"          # Pourcentage
    SPREAD = "spread"                  # Basé sur le spread
    IMPACT = "impact"                  # Basé sur l'impact de marché
    DYNAMIC = "dynamic"                # Coût dynamique


# ============== DATA MODELS ==============

@dataclass
class PortfolioAllocation:
    """Allocation de portefeuille."""
    allocation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    target_weight: float = 0.0
    current_weight: float = 0.0
    current_value: float = 0.0
    target_value: float = 0.0
    deviation: float = 0.0
    rebalance_action: str = "hold"  # buy, sell, hold
    quantity_to_trade: float = 0.0
    priority: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class RebalancingPlan:
    """Plan de rééquilibrage."""
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy: RebalancingStrategy = RebalancingStrategy.TARGET
    trigger: RebalancingTrigger = RebalancingTrigger.DEVIATION
    target_allocation: Dict[str, float] = field(default_factory=dict)
    current_allocation: Dict[str, float] = field(default_factory=dict)
    allocations: List[PortfolioAllocation] = field(default_factory=list)
    total_value: float = 0.0
    cash_reserve: float = 0.0
    max_deviation: float = 0.02
    min_trade_size: float = 0.0
    max_trade_size: float = 0.0
    rebalance_threshold: float = 0.02
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: Optional[datetime] = None
    status: str = "pending"  # pending, executing, completed, failed
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class RebalancingExecution:
    """Exécution de rééquilibrage."""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    orders: List[Order] = field(default_factory=list)
    total_cost: float = 0.0
    total_slippage: float = 0.0
    execution_time: float = 0.0
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    status: str = "pending"
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


# ============== INTERFACES ==============

class RebalancerInterface(ABC):
    """Interface abstraite pour le rééquilibreur."""
    
    @abstractmethod
    async def create_plan(self, config: Dict[str, Any]) -> RebalancingPlan:
        """Crée un plan de rééquilibrage."""
        pass
    
    @abstractmethod
    async def execute_plan(self, plan_id: str) -> RebalancingExecution:
        """Exécute un plan de rééquilibrage."""
        pass
    
    @abstractmethod
    async def monitor_allocation(self) -> List[PortfolioAllocation]:
        """Monitor l'allocation actuelle."""
        pass


# ============== IMPLÉMENTATION ==============

class PortfolioRebalancer(RebalancerInterface):
    """
    Rééquilibreur de portefeuille avancé pour le Hedge Bot.
    Gère le rééquilibrage automatique et l'optimisation d'allocation.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des plans
        self._plans: Dict[str, RebalancingPlan] = {}
        self._plans_lock = threading.RLock()
        
        # Gestion des exécutions
        self._executions: Dict[str, RebalancingExecution] = {}
        self._exec_lock = threading.RLock()
        
        # Cache d'allocation
        self._allocation_cache: Dict[str, PortfolioAllocation] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "plans_created": 0,
            "executions_performed": 0,
            "trades_executed": 0,
            "total_turnover": 0.0,
            "avg_rebalance_time_ms": 0.0,
            "rebalance_impact": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # Queue d'exécution
        self._execution_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        
        # État
        self._is_running = False
        
        logger.info("PortfolioRebalancer initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_strategy": RebalancingStrategy.TARGET,
            "default_trigger": RebalancingTrigger.DEVIATION,
            "max_deviation": 0.02,
            "rebalance_threshold": 0.02,
            "min_trade_size": 0.01,
            "max_trade_size": 1000000,
            "cost_model": RebalancingCost.PERCENTAGE,
            "fixed_cost": 0.0,
            "percentage_cost": 0.001,
            "cash_reserve": 0.05,
            "target_allocation": {},
            "auto_rebalance": True,
            "check_interval": 3600,
            "max_concurrent_orders": 10,
            "slippage_tolerance": 0.01
        }
    
    async def start(self) -> None:
        """Démarre le rééquilibreur."""
        logger.info("PortfolioRebalancer starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._execution_processor())
        asyncio.create_task(self._monitoring_loop())
        asyncio.create_task(self._auto_rebalance_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("PortfolioRebalancer started")
    
    async def stop(self) -> None:
        """Arrête le rééquilibreur."""
        logger.info("PortfolioRebalancer stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("PortfolioRebalancer stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_plan(self, config: Dict[str, Any]) -> RebalancingPlan:
        """Crée un plan de rééquilibrage."""
        plan = RebalancingPlan(
            name=config.get("name", f"Rebalance_{uuid.uuid4().hex[:8]}"),
            strategy=RebalancingStrategy(config.get("strategy", "target")),
            trigger=RebalancingTrigger(config.get("trigger", "deviation")),
            target_allocation=config.get("target_allocation", {}),
            max_deviation=config.get("max_deviation", self.config["max_deviation"]),
            rebalance_threshold=config.get("rebalance_threshold", self.config["rebalance_threshold"]),
            min_trade_size=config.get("min_trade_size", self.config["min_trade_size"]),
            max_trade_size=config.get("max_trade_size", self.config["max_trade_size"]),
            cash_reserve=config.get("cash_reserve", self.config["cash_reserve"]),
            metadata=config.get("metadata", {}),
            tags=config.get("tags", [])
        )
        
        # Calcul de l'allocation actuelle
        current_allocation = await self._get_current_allocation()
        plan.current_allocation = current_allocation
        
        # Calcul des allocations
        plan.allocations = await self._calculate_allocations(plan)
        
        with self._plans_lock:
            self._plans[plan.plan_id] = plan
            self._stats["plans_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"rebalance:plan:{plan.plan_id}",
                plan.to_dict(),
                DataType.PLAN
            )
        
        logger.info(f"Rebalancing plan created: {plan.name} (id={plan.plan_id})")
        return plan
    
    async def execute_plan(self, plan_id: str) -> RebalancingExecution:
        """Exécute un plan de rééquilibrage."""
        with self._plans_lock:
            plan = self._plans.get(plan_id)
            if not plan:
                raise ValueError(f"Plan {plan_id} not found")
            
            plan.status = "executing"
        
        execution = RebalancingExecution(
            plan_id=plan_id,
            start_time=datetime.now(timezone.utc)
        )
        
        try:
            # Génération des ordres
            orders = await self._generate_orders(plan)
            
            # Exécution des ordres
            executed_orders = await self._execute_orders(orders)
            
            # Mise à jour de l'exécution
            execution.orders = executed_orders
            execution.total_cost = sum(o.commission for o in executed_orders if hasattr(o, "commission"))
            execution.total_slippage = sum(o.slippage for o in executed_orders if hasattr(o, "slippage"))
            execution.end_time = datetime.now(timezone.utc)
            execution.execution_time = (execution.end_time - execution.start_time).total_seconds()
            execution.status = "completed"
            
            # Mise à jour du plan
            plan.executed_at = execution.end_time
            plan.status = "completed"
            
            self._stats["executions_performed"] += 1
            self._stats["trades_executed"] += len(executed_orders)
            self._stats["avg_rebalance_time_ms"] = (
                self._stats["avg_rebalance_time_ms"] * 0.9 + execution.execution_time * 1000 * 0.1
            )
            
            # Stockage de l'exécution
            with self._exec_lock:
                self._executions[execution.execution_id] = execution
            
            logger.info(f"Rebalancing executed: {plan.name} "
                       f"orders={len(executed_orders)} cost={execution.total_cost:.2f}")
            
            return execution
            
        except Exception as e:
            plan.status = "failed"
            execution.status = "failed"
            logger.error(f"Rebalancing execution failed: {e}")
            raise
    
    async def monitor_allocation(self) -> List[PortfolioAllocation]:
        """Monitor l'allocation actuelle."""
        current_allocation = await self._get_current_allocation()
        target_allocation = self.config["target_allocation"]
        
        allocations = []
        total_value = sum(current_allocation.values())
        
        for symbol, value in current_allocation.items():
            current_weight = value / total_value if total_value > 0 else 0
            target_weight = target_allocation.get(symbol, 0)
            deviation = current_weight - target_weight
            
            allocation = PortfolioAllocation(
                symbol=symbol,
                target_weight=target_weight,
                current_weight=current_weight,
                current_value=value,
                target_value=target_weight * total_value,
                deviation=deviation
            )
            allocations.append(allocation)
        
        return allocations
    
    # ========== MÉTHODES PRIVÉES - ALLOCATION ==========
    
    async def _get_current_allocation(self) -> Dict[str, float]:
        """Récupère l'allocation actuelle."""
        # Dans un système réel, on interrogerait les positions
        # Simulation
        symbols = self.config["target_allocation"].keys()
        allocation = {}
        
        for symbol in symbols:
            # Simulation de valeur
            allocation[symbol] = np.random.uniform(1000, 10000)
        
        return allocation
    
    async def _calculate_allocations(self, plan: RebalancingPlan) -> List[PortfolioAllocation]:
        """Calcule les allocations pour un plan."""
        allocations = []
        total_value = sum(plan.current_allocation.values())
        
        for symbol, current_value in plan.current_allocation.items():
            current_weight = current_value / total_value if total_value > 0 else 0
            target_weight = plan.target_allocation.get(symbol, 0)
            deviation = current_weight - target_weight
            
            allocation = PortfolioAllocation(
                symbol=symbol,
                target_weight=target_weight,
                current_weight=current_weight,
                current_value=current_value,
                target_value=target_weight * total_value,
                deviation=deviation,
                rebalance_action=self._determine_action(deviation, plan.rebalance_threshold),
                quantity_to_trade=abs(deviation) * total_value,
                priority=self._calculate_priority(deviation)
            )
            allocations.append(allocation)
        
        return allocations
    
    def _determine_action(self, deviation: float, threshold: float) -> str:
        """Détermine l'action de rééquilibrage."""
        if abs(deviation) < threshold:
            return "hold"
        elif deviation > 0:
            return "sell"
        else:
            return "buy"
    
    def _calculate_priority(self, deviation: float) -> int:
        """Calcule la priorité d'un rééquilibrage."""
        return int(abs(deviation) * 100)
    
    # ========== MÉTHODES PRIVÉES - EXÉCUTION ==========
    
    async def _generate_orders(self, plan: RebalancingPlan) -> List[Order]:
        """Génère les ordres pour un plan."""
        orders = []
        
        for allocation in plan.allocations:
            if allocation.rebalance_action == "hold":
                continue
            
            quantity = allocation.quantity_to_trade
            
            # Vérification des limites
            quantity = max(quantity, plan.min_trade_size)
            quantity = min(quantity, plan.max_trade_size)
            
            # Création de l'ordre
            order = Order(
                symbol=allocation.symbol,
                side=allocation.rebalance_action,
                quantity=quantity,
                order_type=OrderType.LIMIT,
                price=self._get_market_price(allocation.symbol)
            )
            orders.append(order)
        
        return orders
    
    async def _execute_orders(self, orders: List[Order]) -> List[Order]:
        """Exécute les ordres."""
        executed = []
        
        # Limitation du nombre d'ordres simultanés
        semaphore = asyncio.Semaphore(self.config["max_concurrent_orders"])
        
        async def execute_single(order: Order) -> Order:
            async with semaphore:
                # Dans un système réel, on exécuterait l'ordre
                # Simulation d'exécution
                order.status = OrderStatus.FILLED
                order.filled_quantity = order.quantity
                order.average_price = order.price * (1 + np.random.normal(0, 0.001))
                order.commission = order.quantity * order.average_price * 0.001
                order.slippage = abs(order.average_price - order.price) / order.price
                return order
        
        tasks = [execute_single(order) for order in orders]
        results = await asyncio.gather(*tasks)
        
        return results
    
    def _get_market_price(self, symbol: str) -> float:
        """Récupère le prix de marché."""
        # Dans un système réel, on interrogerait le marché
        # Simulation
        return np.random.uniform(90, 110)
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _execution_processor(self) -> None:
        """Traite les exécutions en queue."""
        while self._is_running:
            try:
                plan_id = await self._execution_queue.get()
                await self.execute_plan(plan_id)
                
            except Exception as e:
                logger.error(f"Execution processor error: {e}")
                await asyncio.sleep(1)
    
    async def _monitoring_loop(self) -> None:
        """Monitor l'allocation en continu."""
        while self._is_running:
            await asyncio.sleep(60)  # 1 minute
            
            try:
                allocations = await self.monitor_allocation()
                
                # Mise à jour du cache
                with self._cache_lock:
                    for alloc in allocations:
                        self._allocation_cache[alloc.symbol] = alloc
                
                # Vérification des déviations
                for alloc in allocations:
                    if abs(alloc.deviation) > self.config["max_deviation"]:
                        logger.info(f"Allocation deviation detected: {alloc.symbol} "
                                   f"deviation={alloc.deviation:.2%}")
                
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
    
    async def _auto_rebalance_loop(self) -> None:
        """Boucle de rééquilibrage automatique."""
        if not self.config["auto_rebalance"]:
            return
        
        while self._is_running:
            await asyncio.sleep(self.config["check_interval"])
            
            try:
                # Vérification des déviations
                with self._cache_lock:
                    for symbol, alloc in self._allocation_cache.items():
                        if abs(alloc.deviation) > self.config["max_deviation"]:
                            # Création d'un plan de rééquilibrage
                            plan = await self.create_plan({
                                "name": f"Auto-Rebalance-{symbol}",
                                "target_allocation": self.config["target_allocation"],
                                "max_deviation": self.config["max_deviation"]
                            })
                            await self._execution_queue.put(plan.plan_id)
                            break
                
            except Exception as e:
                logger.error(f"Auto-rebalance loop error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._plans_lock:
                    self._stats["total_plans"] = len(self._plans)
                    active_plans = len([p for p in self._plans.values() if p.status == "pending"])
                    self._stats["active_plans"] = active_plans
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "rebalance:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_plan(self, plan_id: str) -> Optional[RebalancingPlan]:
        """Récupère un plan."""
        with self._plans_lock:
            return self._plans.get(plan_id)
    
    async def get_plans(self) -> List[RebalancingPlan]:
        """Récupère les plans."""
        with self._plans_lock:
            return list(self._plans.values())
    
    async def get_execution(self, execution_id: str) -> Optional[RebalancingExecution]:
        """Récupère une exécution."""
        with self._exec_lock:
            return self._executions.get(execution_id)
    
    async def get_executions(self, plan_id: str) -> List[RebalancingExecution]:
        """Récupère les exécutions d'un plan."""
        with self._exec_lock:
            return [e for e in self._executions.values() if e.plan_id == plan_id]
    
    async def get_allocation(self, symbol: str) -> Optional[PortfolioAllocation]:
        """Récupère l'allocation d'un symbole."""
        with self._cache_lock:
            return self._allocation_cache.get(symbol)
    
    async def get_allocation_summary(self) -> Dict[str, Any]:
        """Récupère le résumé de l'allocation."""
        allocations = await self.monitor_allocation()
        
        summary = {
            "total_assets": len(allocations),
            "total_value": sum(a.current_value for a in allocations),
            "max_deviation": max(a.deviation for a in allocations) if allocations else 0,
            "min_deviation": min(a.deviation for a in allocations) if allocations else 0,
            "assets": []
        }
        
        for alloc in allocations:
            summary["assets"].append({
                "symbol": alloc.symbol,
                "current_weight": alloc.current_weight,
                "target_weight": alloc.target_weight,
                "deviation": alloc.deviation,
                "action": alloc.rebalance_action
            })
        
        return summary
    
    async def cancel_plan(self, plan_id: str) -> bool:
        """Annule un plan."""
        with self._plans_lock:
            plan = self._plans.get(plan_id)
            if not plan or plan.status not in ["pending", "executing"]:
                return False
            
            plan.status = "cancelled"
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._plans_lock:
            self._stats["total_plans"] = len(self._plans)
        
        return self._stats.copy()


# ============== REBALANCING OPTIMIZER ==============

class RebalancingOptimizer:
    """
    Optimiseur de rééquilibrage.
    Optimise les stratégies de rééquilibrage pour minimiser les coûts.
    """
    
    def __init__(self, rebalancer: PortfolioRebalancer):
        self.rebalancer = rebalancer
        self._optimization_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
    
    async def optimize(
        self,
        plan: RebalancingPlan,
        objective: str = "min_cost"
    ) -> RebalancingPlan:
        """Optimise un plan de rééquilibrage."""
        # Analyse des coûts
        costs = await self._calculate_costs(plan)
        
        # Optimisation selon l'objectif
        if objective == "min_cost":
            optimized_plan = await self._minimize_cost(plan, costs)
        elif objective == "min_impact":
            optimized_plan = await self._minimize_impact(plan, costs)
        else:
            optimized_plan = plan
        
        return optimized_plan
    
    async def _calculate_costs(self, plan: RebalancingPlan) -> Dict[str, float]:
        """Calcule les coûts de rééquilibrage."""
        costs = {}
        
        for allocation in plan.allocations:
            if allocation.rebalance_action == "hold":
                costs[allocation.symbol] = 0
                continue
            
            # Simulation de coût
            base_cost = 0.001 * allocation.quantity_to_trade
            slippage = 0.0005 * allocation.quantity_to_trade
            spread = 0.0003 * allocation.quantity_to_trade
            
            costs[allocation.symbol] = base_cost + slippage + spread
        
        return costs
    
    async def _minimize_cost(self, plan: RebalancingPlan, costs: Dict[str, float]) -> RebalancingPlan:
        """Minimise les coûts."""
        # Tri par coût pour donner la priorité aux actifs à faible coût
        plan.allocations.sort(
            key=lambda a: costs.get(a.symbol, 0),
            reverse=False
        )
        return plan
    
    async def _minimize_impact(self, plan: RebalancingPlan, costs: Dict[str, float]) -> RebalancingPlan:
        """Minimise l'impact de marché."""
        # Ajustement des quantités pour réduire l'impact
        for allocation in plan.allocations:
            if allocation.rebalance_action != "hold":
                # Réduction de la quantité
                allocation.quantity_to_trade *= 0.8
        
        return plan


# ============== FACTORY ==============

class RebalancerFactory:
    """Factory pour créer des composants de rééquilibrage."""
    
    @staticmethod
    async def create_rebalancer(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PortfolioRebalancer:
        """Crée un rééquilibreur."""
        rebalancer = PortfolioRebalancer(
            data_manager=data_manager,
            config=config
        )
        await rebalancer.start()
        return rebalancer
    
    @staticmethod
    def create_optimizer(rebalancer: PortfolioRebalancer) -> RebalancingOptimizer:
        """Crée un optimiseur de rééquilibrage."""
        return RebalancingOptimizer(rebalancer)


# ============== EXPORT ==============

__all__ = [
    "RebalancingStrategy",
    "RebalancingTrigger",
    "RebalancingCost",
    "PortfolioAllocation",
    "RebalancingPlan",
    "RebalancingExecution",
    "RebalancerInterface",
    "PortfolioRebalancer",
    "RebalancingOptimizer",
    "RebalancerFactory"
]
