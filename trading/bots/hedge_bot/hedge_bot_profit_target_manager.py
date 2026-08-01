# trading/bots/hedge_bot/hedge_bot_profit_target_manager.py
# Advanced Profit Target Management & Optimization Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Profit Target Manager Module - Module avancé de gestion des objectifs de profit
et d'optimisation des gains pour le Hedge Bot. Gère les objectifs de profit dynamiques,
les stratégies de sortie, l'optimisation des gains et la protection des profits.
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
logger = get_logger("hedge_bot_profit_target")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)


# ============== ENUMS & TYPES ==============

class ProfitTargetType(Enum):
    """Types d'objectifs de profit."""
    FIXED = "fixed"                    # Objectif fixe
    PERCENTAGE = "percentage"          # Pourcentage de gain
    RATIO = "ratio"                    # Ratio risque/récompense
    DYNAMIC = "dynamic"                # Dynamique
    ADAPTIVE = "adaptive"              # Adaptatif
    VOLATILITY_BASED = "volatility_based"  # Basé sur la volatilité
    SUPPORT_RESISTANCE = "support_resistance"  # Basé sur supports/résistances
    MULTI_TIER = "multi_tier"          # Multi-niveaux


class ProfitTargetActivation(Enum):
    """Modes d'activation des objectifs de profit."""
    IMMEDIATE = "immediate"            # Activation immédiate
    AFTER_TRAILING = "after_trailing"  # Après stop suiveur
    AFTER_BREAK_EVEN = "after_break_even"  # Après point mort
    AFTER_TIME = "after_time"          # Après un certain temps
    BY_CONDITION = "by_condition"      # Par condition


class ProfitTargetStatus(Enum):
    """Statuts des objectifs de profit."""
    PENDING = "pending"                # En attente
    ACTIVE = "active"                  # Active
    PARTIALLY_HIT = "partially_hit"    # Partiellement atteint
    FULLY_HIT = "fully_hit"            # Totalement atteint
    CANCELLED = "cancelled"            # Annulé
    EXPIRED = "expired"                # Expiré
    ADJUSTED = "adjusted"              # Ajusté


# ============== DATA MODELS ==============

@dataclass
class ProfitTarget:
    """Objectif de profit."""
    target_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    position_id: str = ""
    symbol: str = ""
    entry_price: float = 0.0
    target_price: float = 0.0
    target_percentage: float = 0.0
    target_type: ProfitTargetType = ProfitTargetType.PERCENTAGE
    activation: ProfitTargetActivation = ProfitTargetActivation.IMMEDIATE
    status: ProfitTargetStatus = ProfitTargetStatus.PENDING
    quantity_percentage: float = 1.0
    hit_price: Optional[float] = None
    hit_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    priority: int = 1
    is_active: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "target_id": self.target_id,
            "position_id": self.position_id,
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "target_percentage": self.target_percentage,
            "target_type": self.target_type.value,
            "activation": self.activation.value,
            "status": self.status.value,
            "quantity_percentage": self.quantity_percentage,
            "hit_price": self.hit_price,
            "hit_time": self.hit_time.isoformat() if self.hit_time else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags,
            "priority": self.priority,
            "is_active": self.is_active
        }


@dataclass
class ProfitTargetConfig:
    """Configuration d'objectif de profit."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    target_type: ProfitTargetType = ProfitTargetType.PERCENTAGE
    activation: ProfitTargetActivation = ProfitTargetActivation.IMMEDIATE
    target_value: float = 0.02  # 2% par défaut
    risk_reward_ratio: float = 2.0
    multi_tiers: List[Dict[str, float]] = field(default_factory=list)
    dynamic_range: Tuple[float, float] = (0.01, 0.05)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True


@dataclass
class ProfitTargetSignal:
    """Signal d'objectif de profit."""
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    target_id: str = ""
    signal_type: str = ""  # activate, adjust, hit, cancel
    price: float = 0.0
    quantity: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class ProfitTargetManagerInterface(ABC):
    """Interface abstraite pour le gestionnaire d'objectifs de profit."""
    
    @abstractmethod
    async def create_target(self, position: Dict[str, Any], config: ProfitTargetConfig) -> ProfitTarget:
        """Crée un objectif de profit."""
        pass
    
    @abstractmethod
    async def update_target(self, target_id: str, price: float) -> Optional[ProfitTarget]:
        """Met à jour un objectif de profit."""
        pass
    
    @abstractmethod
    async def check_target(self, target_id: str) -> Optional[ProfitTargetSignal]:
        """Vérifie si un objectif est atteint."""
        pass
    
    @abstractmethod
    async def cancel_target(self, target_id: str) -> bool:
        """Annule un objectif de profit."""
        pass


# ============== IMPLÉMENTATION ==============

class ProfitTargetManager(ProfitTargetManagerInterface):
    """
    Gestionnaire d'objectifs de profit avancé pour le Hedge Bot.
    Optimise les gains et protège les profits avec des stratégies dynamiques.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des objectifs
        self._targets: Dict[str, ProfitTarget] = {}
        self._targets_lock = threading.RLock()
        
        # Gestion des configurations
        self._configs: Dict[str, ProfitTargetConfig] = {}
        self._configs_lock = threading.RLock()
        
        # Gestion des signaux
        self._signals: deque = deque(maxlen=10000)
        self._signals_lock = threading.RLock()
        
        # Cache des prix
        self._price_cache: Dict[str, float] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "targets_created": 0,
            "targets_hit": 0,
            "targets_cancelled": 0,
            "adjustments_made": 0,
            "avg_profit_taken": 0.0,
            "total_profit_taken": 0.0,
            "partial_hits": 0,
            "multi_tier_hits": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("ProfitTargetManager initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_target_type": ProfitTargetType.PERCENTAGE,
            "default_target_value": 0.02,  # 2%
            "default_risk_reward": 2.0,
            "default_activation": ProfitTargetActivation.IMMEDIATE,
            "check_interval": 1.0,  # secondes
            "adjustment_interval": 5.0,  # secondes
            "max_adjustments": 100,
            "enable_ai_optimization": True,
            "ai_optimization_interval": 60,
            "multi_tier_default": [
                {"percentage": 0.01, "quantity": 0.25},
                {"percentage": 0.02, "quantity": 0.25},
                {"percentage": 0.03, "quantity": 0.25},
                {"percentage": 0.04, "quantity": 0.25}
            ],
            "cache_size": 1000,
            "history_size": 10000
        }
    
    async def start(self) -> None:
        """Démarre le gestionnaire d'objectifs de profit."""
        logger.info("ProfitTargetManager starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._target_checker_loop())
        asyncio.create_task(self._adjustment_loop())
        asyncio.create_task(self._ai_optimization_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("ProfitTargetManager started")
    
    async def stop(self) -> None:
        """Arrête le gestionnaire d'objectifs de profit."""
        logger.info("ProfitTargetManager stopping...")
        self._is_running = False
        
        # Attente de la terminaison
        await asyncio.sleep(1)
        
        self._compute_pool.shutdown(wait=True)
        logger.info("ProfitTargetManager stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_target(
        self,
        position: Dict[str, Any],
        config: ProfitTargetConfig
    ) -> ProfitTarget:
        """Crée un objectif de profit."""
        symbol = position.get("symbol", "")
        entry_price = position.get("entry_price", 0.0)
        position_id = position.get("position_id", str(uuid.uuid4()))
        
        # Calcul du prix cible
        if config.target_type == ProfitTargetType.FIXED:
            target_price = entry_price + config.target_value
        
        elif config.target_type == ProfitTargetType.PERCENTAGE:
            target_price = entry_price * (1 + config.target_value)
        
        elif config.target_type == ProfitTargetType.RATIO:
            # Ratio risque/récompense
            stop_loss = position.get("stop_loss", entry_price * 0.98)
            risk = entry_price - stop_loss
            target_price = entry_price + risk * config.risk_reward_ratio
        
        elif config.target_type == ProfitTargetType.VOLATILITY_BASED:
            volatility = await self._get_volatility(symbol)
            target_price = entry_price * (1 + volatility * config.target_value)
        
        elif config.target_type == ProfitTargetType.SUPPORT_RESISTANCE:
            resistance = await self._get_resistance(symbol)
            target_price = resistance if resistance > entry_price else entry_price * 1.02
        
        elif config.target_type == ProfitTargetType.MULTI_TIER:
            # Premier tier
            first_tier = config.multi_tiers[0] if config.multi_tiers else {"percentage": 0.01}
            target_price = entry_price * (1 + first_tier["percentage"])
        
        else:
            # Par défaut: pourcentage
            target_price = entry_price * (1 + self.config["default_target_value"])
        
        # Création de l'objectif
        target = ProfitTarget(
            position_id=position_id,
            symbol=symbol,
            entry_price=entry_price,
            target_price=target_price,
            target_percentage=(target_price - entry_price) / entry_price,
            target_type=config.target_type,
            activation=config.activation,
            status=ProfitTargetStatus.PENDING,
            quantity_percentage=1.0 if config.target_type != ProfitTargetType.MULTI_TIER else 0.25,
            metadata={
                "config_id": config.config_id,
                "target_type": config.target_type.value,
                "activation": config.activation.value,
                "multi_tiers": config.multi_tiers if config.target_type == ProfitTargetType.MULTI_TIER else []
            },
            tags=config.tags,
            priority=1
        )
        
        # Activation
        if config.activation == ProfitTargetActivation.IMMEDIATE:
            target.status = ProfitTargetStatus.ACTIVE
        
        with self._targets_lock:
            self._targets[target.target_id] = target
            self._stats["targets_created"] += 1
        
        # Enregistrement de la création
        await self._record_signal(target, "create", target.target_price)
        
        logger.info(f"Profit target created: {target.target_id} for {symbol} "
                   f"target={target.target_price:.2f} ({target.target_percentage:.2%})")
        
        return target
    
    async def update_target(self, target_id: str, price: float) -> Optional[ProfitTarget]:
        """Met à jour un objectif de profit."""
        with self._targets_lock:
            target = self._targets.get(target_id)
            if not target or not target.is_active:
                return None
        
        try:
            # Mise à jour du prix
            target.updated_at = datetime.now(timezone.utc)
            
            # Vérification de l'activation
            if target.status == ProfitTargetStatus.PENDING:
                if await self._check_activation(target, price):
                    target.status = ProfitTargetStatus.ACTIVE
                    await self._record_signal(target, "activate", price)
                    logger.info(f"Profit target {target_id} activated at {price}")
            
            # Ajustement du target
            if target.status == ProfitTargetStatus.ACTIVE:
                new_target = await self._calculate_target(target, price)
                
                if new_target != target.target_price:
                    old_target = target.target_price
                    target.target_price = new_target
                    target.target_percentage = (new_target - target.entry_price) / target.entry_price
                    target.status = ProfitTargetStatus.ADJUSTED
                    self._stats["adjustments_made"] += 1
                    
                    await self._record_signal(target, "adjust", price)
                    
                    logger.debug(f"Profit target {target_id} adjusted: {old_target:.2f} -> {new_target:.2f}")
            
            # Vérification de l'atteinte
            if target.status in [ProfitTargetStatus.ACTIVE, ProfitTargetStatus.ADJUSTED]:
                if await self._check_hit(target, price):
                    if target.quantity_percentage < 1.0:
                        target.status = ProfitTargetStatus.PARTIALLY_HIT
                        self._stats["partial_hits"] += 1
                    else:
                        target.status = ProfitTargetStatus.FULLY_HIT
                        self._stats["targets_hit"] += 1
                    
                    target.hit_price = price
                    target.hit_time = datetime.now(timezone.utc)
                    
                    self._stats["total_profit_taken"] += target.target_percentage
                    self._stats["avg_profit_taken"] = (
                        self._stats["avg_profit_taken"] * 0.9 + target.target_percentage * 0.1
                    )
                    
                    await self._record_signal(target, "hit", price)
                    
                    # Vérification des multi-tiers
                    if target.metadata.get("multi_tiers"):
                        await self._handle_multi_tier(target, price)
                    
                    logger.info(f"Profit target {target_id} hit at {price} "
                               f"profit={target.target_percentage:.2%}")
            
            return target
            
        except Exception as e:
            logger.error(f"Target update error: {e}")
            return None
    
    async def check_target(self, target_id: str) -> Optional[ProfitTargetSignal]:
        """Vérifie si un objectif est atteint."""
        with self._targets_lock:
            target = self._targets.get(target_id)
            if not target:
                return None
        
        if target.status in [ProfitTargetStatus.FULLY_HIT, ProfitTargetStatus.PARTIALLY_HIT]:
            return ProfitTargetSignal(
                target_id=target.target_id,
                signal_type="hit",
                price=target.hit_price or 0.0,
                quantity=target.quantity_percentage,
                metadata={"profit": target.target_percentage}
            )
        
        if target.status == ProfitTargetStatus.CANCELLED:
            return ProfitTargetSignal(
                target_id=target.target_id,
                signal_type="cancelled",
                price=0.0
            )
        
        return None
    
    async def cancel_target(self, target_id: str) -> bool:
        """Annule un objectif de profit."""
        with self._targets_lock:
            target = self._targets.get(target_id)
            if not target:
                return False
            
            if target.status in [ProfitTargetStatus.FULLY_HIT, ProfitTargetStatus.CANCELLED]:
                return True
            
            target.status = ProfitTargetStatus.CANCELLED
            target.is_active = False
            target.updated_at = datetime.now(timezone.utc)
            self._stats["targets_cancelled"] += 1
            
            await self._record_signal(target, "cancel", 0.0)
            
            logger.info(f"Profit target {target_id} cancelled")
            return True
    
    # ========== MÉTHODES PRIVÉES - CALCULS ==========
    
    async def _calculate_target(
        self,
        target: ProfitTarget,
        price: float
    ) -> float:
        """Calcule le nouvel objectif de profit."""
        if target.target_type == ProfitTargetType.FIXED:
            return target.target_price
        
        elif target.target_type == ProfitTargetType.DYNAMIC:
            # Ajustement dynamique basé sur la progression
            progress = (price - target.entry_price) / target.entry_price
            if progress > 0:
                target_multiplier = 1 + progress * 0.5
                new_target = target.entry_price * (1 + target.target_percentage * target_multiplier)
                return new_target
            return target.target_price
        
        elif target.target_type == ProfitTargetType.ADAPTIVE:
            # Ajustement adaptatif
            volatility = await self._get_volatility(target.symbol)
            if volatility > 0:
                target_multiplier = 1 + volatility * 0.3
                new_target = target.entry_price * (1 + target.target_percentage * target_multiplier)
                return new_target
            return target.target_price
        
        elif target.target_type == ProfitTargetType.VOLATILITY_BASED:
            # Ajustement basé sur la volatilité
            volatility = await self._get_volatility(target.symbol)
            if volatility > 0:
                new_target = price * (1 + volatility * 0.5)
                return max(new_target, target.target_price)
            return target.target_price
        
        elif target.target_type == ProfitTargetType.MULTI_TIER:
            # Ajustement pour les multi-tiers
            tiers = target.metadata.get("multi_tiers", [])
            if tiers:
                current_profit = (price - target.entry_price) / target.entry_price
                for tier in tiers:
                    if current_profit >= tier.get("percentage", 0):
                        target.quantity_percentage = tier.get("quantity", 0.25)
                        return price * (1 + tier.get("next_percentage", 0.01))
            return target.target_price
        
        else:
            return target.target_price
    
    async def _check_activation(
        self,
        target: ProfitTarget,
        price: float
    ) -> bool:
        """Vérifie si l'objectif doit être activé."""
        activation = target.metadata.get("activation", "immediate")
        
        if activation == "immediate":
            return True
        
        elif activation == "after_trailing":
            # Activation après le stop suiveur
            return True
        
        elif activation == "after_break_even":
            return price >= target.entry_price
        
        elif activation == "after_time":
            threshold = target.metadata.get("time_threshold", 3600)
            if target.created_at:
                age = (datetime.now(timezone.utc) - target.created_at).total_seconds()
                return age >= threshold
        
        elif activation == "by_condition":
            condition = target.metadata.get("condition", "price > entry_price")
            try:
                return eval(condition, {"price": price, "entry_price": target.entry_price})
            except:
                return False
        
        return False
    
    async def _check_hit(self, target: ProfitTarget, price: float) -> bool:
        """Vérifie si l'objectif est atteint."""
        if target.target_type == ProfitTargetType.MULTI_TIER:
            # Vérification des multi-tiers
            tiers = target.metadata.get("multi_tiers", [])
            if tiers:
                current_profit = (price - target.entry_price) / target.entry_price
                for tier in tiers:
                    if current_profit >= tier.get("percentage", 0):
                        return True
            return False
        
        return price >= target.target_price
    
    async def _handle_multi_tier(self, target: ProfitTarget, price: float) -> None:
        """Gère les multi-tiers."""
        tiers = target.metadata.get("multi_tiers", [])
        if not tiers:
            return
        
        current_profit = (price - target.entry_price) / target.entry_price
        
        # Trouver le prochain tier
        next_tier = None
        for tier in tiers:
            if current_profit >= tier.get("percentage", 0):
                next_tier = tier
                break
        
        if next_tier:
            # Mise à jour de l'objectif pour le prochain tier
            new_target = price * (1 + next_tier.get("next_percentage", 0.01))
            target.target_price = new_target
            target.target_percentage = (new_target - target.entry_price) / target.entry_price
            target.quantity_percentage = next_tier.get("quantity", 0.25)
            target.status = ProfitTargetStatus.ACTIVE
            
            self._stats["multi_tier_hits"] += 1
            
            logger.info(f"Multi-tier hit for {target.target_id}: "
                       f"next tier at {target.target_price:.2f}")
    
    # ========== MÉTHODES PRIVÉES - INDICATEURS ==========
    
    async def _get_volatility(self, symbol: str) -> float:
        """Récupère la volatilité pour un symbole."""
        try:
            if self.data_manager:
                data = await self.data_manager.retrieve(
                    f"indicator:{symbol}:volatility",
                    DataType.INDICATOR
                )
                if data:
                    return data.get("value", 0.2)
        except:
            pass
        
        return 0.2
    
    async def _get_resistance(self, symbol: str) -> float:
        """Récupère le niveau de résistance pour un symbole."""
        try:
            if self.data_manager:
                data = await self.data_manager.retrieve(
                    f"market:{symbol}:resistance",
                    DataType.MARKET
                )
                if data:
                    return data.get("value", 0.0)
        except:
            pass
        
        return 0.0
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _target_checker_loop(self) -> None:
        """Boucle de vérification des objectifs."""
        while self._is_running:
            await asyncio.sleep(self.config["check_interval"])
            
            try:
                with self._targets_lock:
                    for target in list(self._targets.values()):
                        if target.is_active and target.status in [ProfitTargetStatus.ACTIVE, ProfitTargetStatus.ADJUSTED]:
                            # Récupération du prix actuel
                            if self.data_manager:
                                price_data = await self.data_manager.retrieve(
                                    f"market:{target.symbol}:price",
                                    DataType.MARKET
                                )
                                if price_data:
                                    current_price = price_data.get("price", 0.0)
                                    await self.update_target(target.target_id, current_price)
                
            except Exception as e:
                logger.error(f"Target checker error: {e}")
    
    async def _adjustment_loop(self) -> None:
        """Boucle d'ajustement des objectifs."""
        while self._is_running:
            await asyncio.sleep(self.config["adjustment_interval"])
            
            try:
                with self._targets_lock:
                    for target in list(self._targets.values()):
                        if target.is_active and target.status in [ProfitTargetStatus.ACTIVE, ProfitTargetStatus.ADJUSTED]:
                            # Ajustement périodique
                            if target.target_type in [ProfitTargetType.DYNAMIC, ProfitTargetType.ADAPTIVE]:
                                # Récupération du prix actuel
                                if self.data_manager:
                                    price_data = await self.data_manager.retrieve(
                                        f"market:{target.symbol}:price",
                                        DataType.MARKET
                                    )
                                    if price_data:
                                        current_price = price_data.get("price", 0.0)
                                        new_target = await self._calculate_target(target, current_price)
                                        
                                        if new_target != target.target_price:
                                            target.target_price = new_target
                                            target.status = ProfitTargetStatus.ADJUSTED
                                            self._stats["adjustments_made"] += 1
                                            await self._record_signal(target, "adjust", current_price)
                
            except Exception as e:
                logger.error(f"Adjustment loop error: {e}")
    
    async def _ai_optimization_loop(self) -> None:
        """Boucle d'optimisation IA des objectifs."""
        if not self.config["enable_ai_optimization"]:
            return
        
        while self._is_running:
            await asyncio.sleep(self.config["ai_optimization_interval"])
            
            try:
                # Optimisation des objectifs actifs
                with self._targets_lock:
                    for target in list(self._targets.values()):
                        if target.is_active and target.status in [ProfitTargetStatus.ACTIVE, ProfitTargetStatus.ADJUSTED]:
                            # Récupération des données historiques
                            if self.data_manager:
                                history = await self.data_manager.retrieve(
                                    f"market:{target.symbol}:history",
                                    DataType.HISTORICAL
                                )
                                
                                if history:
                                    # Optimisation de l'objectif
                                    optimal_target = await self._optimize_target(target, history)
                                    
                                    if optimal_target and optimal_target != target.target_price:
                                        target.target_price = optimal_target
                                        target.status = ProfitTargetStatus.ADJUSTED
                                        logger.debug(f"AI optimized profit target {target.target_id}: "
                                                   f"new target={optimal_target:.2f}")
                
            except Exception as e:
                logger.error(f"AI optimization loop error: {e}")
    
    async def _optimize_target(
        self,
        target: ProfitTarget,
        history: Dict[str, Any]
    ) -> Optional[float]:
        """Optimise l'objectif de profit avec IA."""
        # Simulation d'optimisation IA
        # Dans un système réel, on utiliserait un modèle ML
        
        # Analyse de la volatilité récente
        volatility = history.get("volatility", 0.02)
        
        # Analyse des niveaux de résistance
        resistances = history.get("resistances", [])
        
        if resistances:
            # Utiliser la résistance la plus proche
            target_resistance = min(
                [r for r in resistances if r > target.entry_price],
                key=lambda r: (r - target.entry_price) / target.entry_price
            )
            return target_resistance
        
        # Ajustement basé sur la volatilité
        target_multiplier = 1 + volatility * 0.5
        optimal_target = target.entry_price * (1 + target.target_percentage * target_multiplier)
        
        return optimal_target
    
    # ========== MÉTHODES PRIVÉES - ENREGISTREMENT ==========
    
    async def _record_signal(self, target: ProfitTarget, signal_type: str, price: float) -> None:
        """Enregistre un signal."""
        signal = ProfitTargetSignal(
            target_id=target.target_id,
            signal_type=signal_type,
            price=price,
            quantity=target.quantity_percentage,
            metadata={
                "target_price": target.target_price,
                "entry_price": target.entry_price,
                "percentage": target.target_percentage
            }
        )
        
        with self._signals_lock:
            self._signals.append(signal)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"profit_target:signal:{signal.signal_id}",
                signal.to_dict(),
                DataType.SIGNAL
            )
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._targets_lock:
                    active_targets = len([t for t in self._targets.values() if t.is_active and t.status in [ProfitTargetStatus.ACTIVE, ProfitTargetStatus.ADJUSTED]])
                    hit_targets = len([t for t in self._targets.values() if t.status in [ProfitTargetStatus.FULLY_HIT, ProfitTargetStatus.PARTIALLY_HIT]])
                    
                    self._stats["active_targets"] = active_targets
                    self._stats["hit_targets"] = hit_targets
                    self._stats["total_targets"] = len(self._targets)
                
                # Calcul du profit moyen
                with self._targets_lock:
                    hit = [t for t in self._targets.values() if t.status in [ProfitTargetStatus.FULLY_HIT, ProfitTargetStatus.PARTIALLY_HIT]]
                    if hit:
                        self._stats["avg_profit_taken"] = np.mean([t.target_percentage for t in hit])
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "profit_target:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_target(self, target_id: str) -> Optional[ProfitTarget]:
        """Récupère un objectif de profit."""
        with self._targets_lock:
            return self._targets.get(target_id)
    
    async def get_targets(
        self,
        symbol: Optional[str] = None,
        status: Optional[ProfitTargetStatus] = None
    ) -> List[ProfitTarget]:
        """Récupère les objectifs de profit."""
        with self._targets_lock:
            targets = list(self._targets.values())
            if symbol:
                targets = [t for t in targets if t.symbol == symbol]
            if status:
                targets = [t for t in targets if t.status == status]
            return targets
    
    async def get_signals(self, target_id: str, limit: int = 100) -> List[ProfitTargetSignal]:
        """Récupère les signaux d'un objectif."""
        with self._signals_lock:
            signals = [s for s in self._signals if s.target_id == target_id]
            return list(signals)[-limit:]
    
    async def create_config(self, config: ProfitTargetConfig) -> str:
        """Crée une configuration d'objectif de profit."""
        with self._configs_lock:
            self._configs[config.config_id] = config
        
        if self.data_manager:
            await self.data_manager.store(
                f"profit_target:config:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Profit target configuration created: {config.name}")
        return config.config_id
    
    async def get_config(self, config_id: str) -> Optional[ProfitTargetConfig]:
        """Récupère une configuration."""
        with self._configs_lock:
            return self._configs.get(config_id)
    
    async def get_configs(self) -> List[ProfitTargetConfig]:
        """Récupère les configurations."""
        with self._configs_lock:
            return list(self._configs.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._targets_lock:
            self._stats["total_targets"] = len(self._targets)
        with self._configs_lock:
            self._stats["total_configs"] = len(self._configs)
        
        return self._stats.copy()
    
    async def export_targets(self, format: str = "json") -> str:
        """Exporte les objectifs de profit."""
        with self._targets_lock:
            targets = [t.to_dict() for t in self._targets.values()]
        
        if format == "json":
            return json.dumps(targets, indent=2)
        elif format == "csv":
            import csv
            import io
            output = io.StringIO()
            if targets:
                writer = csv.DictWriter(output, fieldnames=targets[0].keys())
                writer.writeheader()
                writer.writerows(targets)
            return output.getvalue()
        else:
            return json.dumps(targets)


# ============== PROFIT TARGET STRATEGY BUILDER ==============

class ProfitTargetStrategyBuilder:
    """
    Constructeur de stratégies d'objectifs de profit.
    Facilite la création de stratégies complexes.
    """
    
    def __init__(self):
        self._config = ProfitTargetConfig()
    
    def fixed_target(self, target: float) -> 'ProfitTargetStrategyBuilder':
        """Définit un objectif fixe."""
        self._config.target_type = ProfitTargetType.FIXED
        self._config.target_value = target
        return self
    
    def percentage_target(self, percentage: float) -> 'ProfitTargetStrategyBuilder':
        """Définit un objectif en pourcentage."""
        self._config.target_type = ProfitTargetType.PERCENTAGE
        self._config.target_value = percentage
        return self
    
    def risk_reward(self, ratio: float) -> 'ProfitTargetStrategyBuilder':
        """Définit un ratio risque/récompense."""
        self._config.target_type = ProfitTargetType.RATIO
        self._config.risk_reward_ratio = ratio
        return self
    
    def multi_tier(self, tiers: List[Dict[str, float]]) -> 'ProfitTargetStrategyBuilder':
        """Définit des multi-tiers."""
        self._config.target_type = ProfitTargetType.MULTI_TIER
        self._config.multi_tiers = tiers
        return self
    
    def dynamic_range(self, min_target: float, max_target: float) -> 'ProfitTargetStrategyBuilder':
        """Définit une plage dynamique."""
        self._config.target_type = ProfitTargetType.DYNAMIC
        self._config.dynamic_range = (min_target, max_target)
        return self
    
    def volatility_based(self, multiplier: float) -> 'ProfitTargetStrategyBuilder':
        """Définit un objectif basé sur la volatilité."""
        self._config.target_type = ProfitTargetType.VOLATILITY_BASED
        self._config.target_value = multiplier
        return self
    
    def activate_on(self, activation: ProfitTargetActivation) -> 'ProfitTargetStrategyBuilder':
        """Définit l'activation."""
        self._config.activation = activation
        return self
    
    def build(self) -> ProfitTargetConfig:
        """Construit la configuration."""
        return self._config


# ============== FACTORY ==============

class ProfitTargetFactory:
    """Factory pour créer des composants d'objectifs de profit."""
    
    @staticmethod
    async def create_manager(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ProfitTargetManager:
        """Crée un gestionnaire d'objectifs de profit."""
        manager = ProfitTargetManager(
            data_manager=data_manager,
            config=config
        )
        await manager.start()
        return manager
    
    @staticmethod
    def create_builder() -> ProfitTargetStrategyBuilder:
        """Crée un constructeur de stratégies."""
        return ProfitTargetStrategyBuilder()


# ============== EXPORT ==============

__all__ = [
    "ProfitTargetType",
    "ProfitTargetActivation",
    "ProfitTargetStatus",
    "ProfitTarget",
    "ProfitTargetConfig",
    "ProfitTargetSignal",
    "ProfitTargetManagerInterface",
    "ProfitTargetManager",
    "ProfitTargetStrategyBuilder",
    "ProfitTargetFactory"
]
