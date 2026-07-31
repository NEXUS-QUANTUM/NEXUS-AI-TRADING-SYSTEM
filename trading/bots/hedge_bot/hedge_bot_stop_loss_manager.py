# trading/bots/hedge_bot/hedge_bot_stop_loss_manager.py
# Advanced Stop Loss Management System for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Stop Loss Manager - Module avancé de gestion des stop loss pour le Hedge Bot.
Gère les stop loss dynamiques, l'optimisation des risques, les stratégies de protection
du capital et les ajustements automatiques des stop loss.
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
logger = get_logger("hedge_bot_stop_loss")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)


# ============== ENUMS & TYPES ==============

class StopLossType(Enum):
    """Types de stop loss."""
    FIXED = "fixed"                    # Stop loss fixe
    PERCENTAGE = "percentage"          # Pourcentage de perte
    ATR_BASED = "atr_based"            # Basé sur l'ATR
    VOLATILITY_BASED = "volatility_based"  # Basé sur la volatilité
    SUPPORT_BASED = "support_based"    # Basé sur les supports
    DYNAMIC = "dynamic"                # Dynamique
    TRAILING = "trailing"              # Stop loss suiveur
    BREAK_EVEN = "break_even"          # Stop loss au point mort
    MENTAL = "mental"                  # Stop loss mental


class StopLossActivation(Enum):
    """Modes d'activation des stop loss."""
    IMMEDIATE = "immediate"            # Activation immédiate
    AFTER_PROFIT = "after_profit"      # Après un certain profit
    AFTER_TIME = "after_time"          # Après un certain temps
    BY_CONDITION = "by_condition"      # Par condition


class StopLossAdjustment(Enum):
    """Types d'ajustement des stop loss."""
    NONE = "none"                      # Pas d'ajustement
    LINEAR = "linear"                  # Linéaire
    EXPONENTIAL = "exponential"        # Exponentiel
    STEP = "step"                      # Par paliers
    AI_OPTIMIZED = "ai_optimized"      # Optimisé par IA
    MARKET_BASED = "market_based"      # Basé sur le marché
    VOLATILITY_BASED = "volatility_based"  # Basé sur la volatilité


class StopLossStatus(Enum):
    """Statuts des stop loss."""
    PENDING = "pending"                # En attente
    ACTIVE = "active"                  # Active
    HIT = "hit"                        # Déclenché
    CANCELLED = "cancelled"            # Annulé
    EXPIRED = "expired"                # Expiré
    ADJUSTED = "adjusted"              # Ajusté


# ============== DATA MODELS ==============

@dataclass
class StopLossLevel:
    """Niveau de stop loss."""
    level_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    position_id: str = ""
    symbol: str = ""
    entry_price: float = 0.0
    stop_price: float = 0.0
    stop_percentage: float = 0.0
    stop_type: StopLossType = StopLossType.PERCENTAGE
    activation: StopLossActivation = StopLossActivation.IMMEDIATE
    adjustment: StopLossAdjustment = StopLossAdjustment.NONE
    status: StopLossStatus = StopLossStatus.PENDING
    hit_price: Optional[float] = None
    hit_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    is_active: bool = True
    risk_amount: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "level_id": self.level_id,
            "position_id": self.position_id,
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "stop_percentage": self.stop_percentage,
            "stop_type": self.stop_type.value,
            "activation": self.activation.value,
            "adjustment": self.adjustment.value,
            "status": self.status.value,
            "hit_price": self.hit_price,
            "hit_time": self.hit_time.isoformat() if self.hit_time else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags,
            "is_active": self.is_active,
            "risk_amount": self.risk_amount
        }


@dataclass
class StopLossConfig:
    """Configuration de stop loss."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stop_type: StopLossType = StopLossType.PERCENTAGE
    activation: StopLossActivation = StopLossActivation.IMMEDIATE
    adjustment: StopLossAdjustment = StopLossAdjustment.NONE
    stop_value: float = 0.02  # 2% par défaut
    atr_multiplier: float = 2.0
    volatility_multiplier: float = 1.5
    max_loss: float = 0.05
    min_loss: float = 0.005
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True


@dataclass
class StopLossSignal:
    """Signal de stop loss."""
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    level_id: str = ""
    signal_type: str = ""  # activate, adjust, hit, cancel
    price: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class StopLossManagerInterface(ABC):
    """Interface abstraite pour le gestionnaire de stop loss."""
    
    @abstractmethod
    async def create_level(self, position: Dict[str, Any], config: StopLossConfig) -> StopLossLevel:
        """Crée un niveau de stop loss."""
        pass
    
    @abstractmethod
    async def update_level(self, level_id: str, price: float) -> Optional[StopLossLevel]:
        """Met à jour un niveau de stop loss."""
        pass
    
    @abstractmethod
    async def check_level(self, level_id: str) -> Optional[StopLossSignal]:
        """Vérifie si un niveau est atteint."""
        pass
    
    @abstractmethod
    async def cancel_level(self, level_id: str) -> bool:
        """Annule un niveau de stop loss."""
        pass


# ============== IMPLÉMENTATION ==============

class StopLossManager(StopLossManagerInterface):
    """
    Gestionnaire de stop loss avancé pour le Hedge Bot.
    Implémente plusieurs stratégies de protection du capital.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des niveaux
        self._levels: Dict[str, StopLossLevel] = {}
        self._levels_lock = threading.RLock()
        
        # Gestion des configurations
        self._configs: Dict[str, StopLossConfig] = {}
        self._configs_lock = threading.RLock()
        
        # Gestion des signaux
        self._signals: deque = deque(maxlen=10000)
        self._signals_lock = threading.RLock()
        
        # Cache des prix
        self._price_cache: Dict[str, float] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "levels_created": 0,
            "levels_hit": 0,
            "levels_cancelled": 0,
            "adjustments_made": 0,
            "avg_loss_protected": 0.0,
            "total_loss_protected": 0.0,
            "hit_rate": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("StopLossManager initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_stop_type": StopLossType.PERCENTAGE,
            "default_stop_value": 0.02,  # 2%
            "default_atr_multiplier": 2.0,
            "default_volatility_multiplier": 1.5,
            "min_stop": 0.005,  # 0.5%
            "max_stop": 0.10,   # 10%
            "check_interval": 1.0,  # secondes
            "adjustment_interval": 5.0,  # secondes
            "max_adjustments": 100,
            "enable_ai_optimization": True,
            "ai_optimization_interval": 60,
            "cache_size": 1000,
            "history_size": 10000
        }
    
    async def start(self) -> None:
        """Démarre le gestionnaire de stop loss."""
        logger.info("StopLossManager starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._level_checker_loop())
        asyncio.create_task(self._adjustment_loop())
        asyncio.create_task(self._ai_optimization_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("StopLossManager started")
    
    async def stop(self) -> None:
        """Arrête le gestionnaire de stop loss."""
        logger.info("StopLossManager stopping...")
        self._is_running = False
        
        # Attente de la terminaison
        await asyncio.sleep(1)
        
        self._compute_pool.shutdown(wait=True)
        logger.info("StopLossManager stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_level(
        self,
        position: Dict[str, Any],
        config: StopLossConfig
    ) -> StopLossLevel:
        """Crée un niveau de stop loss."""
        symbol = position.get("symbol", "")
        entry_price = position.get("entry_price", 0.0)
        position_id = position.get("position_id", str(uuid.uuid4()))
        
        # Calcul du prix de stop
        if config.stop_type == StopLossType.FIXED:
            stop_price = entry_price - config.stop_value
        
        elif config.stop_type == StopLossType.PERCENTAGE:
            stop_price = entry_price * (1 - config.stop_value)
        
        elif config.stop_type == StopLossType.ATR_BASED:
            atr = await self._get_atr(symbol)
            stop_price = entry_price - (atr * config.atr_multiplier)
        
        elif config.stop_type == StopLossType.VOLATILITY_BASED:
            volatility = await self._get_volatility(symbol)
            stop_price = entry_price * (1 - volatility * config.volatility_multiplier)
        
        elif config.stop_type == StopLossType.SUPPORT_BASED:
            support = await self._get_support(symbol)
            stop_price = support
        
        elif config.stop_type == StopLossType.BREAK_EVEN:
            stop_price = entry_price
        
        else:
            # Par défaut: pourcentage
            stop_price = entry_price * (1 - self.config["default_stop_value"])
        
        # Limites
        min_price = entry_price * (1 - self.config["max_stop"])
        max_price = entry_price * (1 - self.config["min_stop"])
        
        # Le stop doit être inférieur au prix d'entrée
        stop_price = min(stop_price, entry_price)
        stop_price = max(stop_price, min_price)
        
        # Création du niveau
        level = StopLossLevel(
            position_id=position_id,
            symbol=symbol,
            entry_price=entry_price,
            stop_price=stop_price,
            stop_percentage=(entry_price - stop_price) / entry_price,
            stop_type=config.stop_type,
            activation=config.activation,
            adjustment=config.adjustment,
            status=StopLossStatus.PENDING,
            risk_amount=position.get("risk_amount", 0),
            metadata={
                "config_id": config.config_id,
                "stop_type": config.stop_type.value,
                "activation": config.activation.value,
                "adjustment": config.adjustment.value
            },
            tags=config.tags
        )
        
        # Activation
        if config.activation == StopLossActivation.IMMEDIATE:
            level.status = StopLossStatus.ACTIVE
        
        with self._levels_lock:
            self._levels[level.level_id] = level
            self._stats["levels_created"] += 1
        
        # Enregistrement de la création
        await self._record_signal(level, "create", entry_price)
        
        logger.info(f"Stop loss level created: {level.level_id} for {symbol} "
                   f"stop={level.stop_price:.2f} ({level.stop_percentage:.2%})")
        
        return level
    
    async def update_level(self, level_id: str, price: float) -> Optional[StopLossLevel]:
        """Met à jour un niveau de stop loss."""
        with self._levels_lock:
            level = self._levels.get(level_id)
            if not level or not level.is_active:
                return None
        
        try:
            # Mise à jour du prix
            level.updated_at = datetime.now(timezone.utc)
            
            # Vérification de l'activation
            if level.status == StopLossStatus.PENDING:
                if await self._check_activation(level, price):
                    level.status = StopLossStatus.ACTIVE
                    await self._record_signal(level, "activate", price)
                    logger.info(f"Stop loss {level_id} activated at {price}")
            
            # Ajustement du stop
            if level.status == StopLossStatus.ACTIVE:
                new_stop = await self._calculate_stop(level, price)
                
                if new_stop != level.stop_price:
                    old_stop = level.stop_price
                    level.stop_price = new_stop
                    level.stop_percentage = (level.entry_price - new_stop) / level.entry_price
                    level.status = StopLossStatus.ADJUSTED
                    self._stats["adjustments_made"] += 1
                    
                    await self._record_signal(level, "adjust", price)
                    
                    logger.debug(f"Stop loss {level_id} adjusted: {old_stop:.2f} -> {new_stop:.2f}")
            
            # Vérification du déclenchement
            if level.status in [StopLossStatus.ACTIVE, StopLossStatus.ADJUSTED]:
                if await self._check_hit(level, price):
                    level.status = StopLossStatus.HIT
                    level.hit_price = price
                    level.hit_time = datetime.now(timezone.utc)
                    
                    loss_protected = (level.entry_price - price) / level.entry_price
                    level.metadata["loss_protected"] = loss_protected
                    
                    self._stats["levels_hit"] += 1
                    self._stats["total_loss_protected"] += loss_protected
                    
                    await self._record_signal(level, "hit", price)
                    
                    logger.info(f"Stop loss {level_id} hit at {price} "
                               f"loss={loss_protected:.2%}")
            
            return level
            
        except Exception as e:
            logger.error(f"Level update error: {e}")
            return None
    
    async def check_level(self, level_id: str) -> Optional[StopLossSignal]:
        """Vérifie si un niveau est atteint."""
        with self._levels_lock:
            level = self._levels.get(level_id)
            if not level:
                return None
        
        if level.status == StopLossStatus.HIT:
            return StopLossSignal(
                level_id=level.level_id,
                signal_type="hit",
                price=level.hit_price or 0.0,
                metadata={"loss": level.metadata.get("loss_protected", 0)}
            )
        
        if level.status == StopLossStatus.CANCELLED:
            return StopLossSignal(
                level_id=level.level_id,
                signal_type="cancelled",
                price=0.0
            )
        
        return None
    
    async def cancel_level(self, level_id: str) -> bool:
        """Annule un niveau de stop loss."""
        with self._levels_lock:
            level = self._levels.get(level_id)
            if not level:
                return False
            
            if level.status in [StopLossStatus.HIT, StopLossStatus.CANCELLED]:
                return True
            
            level.status = StopLossStatus.CANCELLED
            level.is_active = False
            level.updated_at = datetime.now(timezone.utc)
            self._stats["levels_cancelled"] += 1
            
            await self._record_signal(level, "cancel", 0.0)
            
            logger.info(f"Stop loss {level_id} cancelled")
            return True
    
    # ========== MÉTHODES PRIVÉES - CALCULS ==========
    
    async def _calculate_stop(
        self,
        level: StopLossLevel,
        price: float
    ) -> float:
        """Calcule le nouveau niveau de stop loss."""
        # Différentes stratégies d'ajustement
        if level.adjustment == StopLossAdjustment.NONE:
            return level.stop_price
        
        elif level.adjustment == StopLossAdjustment.LINEAR:
            # Ajustement linéaire basé sur la progression du prix
            progress = (price - level.entry_price) / level.entry_price
            if progress > 0:
                # Réduction du stop en fonction du profit
                stop_reduction = progress * 0.5
                new_stop = level.entry_price * (1 - level.stop_percentage + stop_reduction)
                return max(new_stop, level.entry_price * (1 - self.config["min_stop"]))
            return level.stop_price
        
        elif level.adjustment == StopLossAdjustment.EXPONENTIAL:
            # Ajustement exponentiel
            progress = (price - level.entry_price) / level.entry_price
            if progress > 0:
                stop_reduction = 1 - math.exp(-progress * 2)
                new_stop = level.entry_price * (1 - level.stop_percentage * (1 - stop_reduction))
                return max(new_stop, level.entry_price * (1 - self.config["min_stop"]))
            return level.stop_price
        
        elif level.adjustment == StopLossAdjustment.STEP:
            # Ajustement par paliers
            profit_levels = [
                (0.02, 0.005),   # +2% profit, réduction de 0.5%
                (0.05, 0.01),    # +5% profit, réduction de 1%
                (0.10, 0.015),   # +10% profit, réduction de 1.5%
                (0.20, 0.02),    # +20% profit, réduction de 2%
                (0.30, 0.025),   # +30% profit, réduction de 2.5%
                (0.50, 0.03)     # +50% profit, réduction de 3%
            ]
            
            progress = (price - level.entry_price) / level.entry_price
            total_reduction = 0
            for threshold, reduction in profit_levels:
                if progress >= threshold:
                    total_reduction = reduction
            
            if total_reduction > 0:
                new_stop = level.entry_price * (1 - level.stop_percentage + total_reduction)
                return max(new_stop, level.entry_price * (1 - self.config["min_stop"]))
            return level.stop_price
        
        elif level.adjustment == StopLossAdjustment.TRAILING:
            # Stop loss suiveur
            if price > level.entry_price:
                # Le stop suit le prix à une distance fixe
                trailing_distance = level.stop_percentage
                new_stop = price * (1 - trailing_distance)
                
                # Le stop ne peut que monter
                if new_stop > level.stop_price:
                    return new_stop
            return level.stop_price
        
        elif level.adjustment == StopLossAdjustment.VOLATILITY_BASED:
            # Ajustement basé sur la volatilité
            volatility = await self._get_volatility(level.symbol)
            if volatility > 0:
                # Ajustement de la distance du stop en fonction de la volatilité
                distance = level.stop_percentage * (1 + volatility * 0.5)
                distance = min(distance, self.config["max_stop"])
                new_stop = price * (1 - distance)
                return new_stop
            return level.stop_price
        
        else:
            return level.stop_price
    
    async def _check_activation(
        self,
        level: StopLossLevel,
        price: float
    ) -> bool:
        """Vérifie si le stop doit être activé."""
        activation = level.metadata.get("activation", "immediate")
        
        if activation == "immediate":
            return True
        
        elif activation == "after_profit":
            # Activation après un certain profit
            threshold = level.metadata.get("profit_threshold", 0.01)
            profit = (price - level.entry_price) / level.entry_price
            return profit >= threshold
        
        elif activation == "after_time":
            # Activation après un certain temps
            threshold = level.metadata.get("time_threshold", 300)  # 5 minutes
            if level.created_at:
                age = (datetime.now(timezone.utc) - level.created_at).total_seconds()
                return age >= threshold
        
        elif activation == "by_condition":
            # Activation par condition
            condition = level.metadata.get("condition", "price > entry_price")
            try:
                return eval(condition, {"price": price, "entry_price": level.entry_price})
            except:
                return False
        
        return False
    
    async def _check_hit(self, level: StopLossLevel, price: float) -> bool:
        """Vérifie si le stop loss est déclenché."""
        return price <= level.stop_price
    
    # ========== MÉTHODES PRIVÉES - INDICATEURS ==========
    
    async def _get_atr(self, symbol: str) -> float:
        """Récupère l'ATR pour un symbole."""
        try:
            if self.data_manager:
                data = await self.data_manager.retrieve(
                    f"indicator:{symbol}:atr",
                    DataType.INDICATOR
                )
                if data:
                    return data.get("value", 0.1)
        except:
            pass
        
        # Valeur par défaut
        return 0.1
    
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
        
        # Valeur par défaut
        return 0.2
    
    async def _get_support(self, symbol: str) -> float:
        """Récupère le niveau de support pour un symbole."""
        try:
            if self.data_manager:
                data = await self.data_manager.retrieve(
                    f"market:{symbol}:support",
                    DataType.MARKET
                )
                if data:
                    return data.get("value", 0.0)
        except:
            pass
        
        # Valeur par défaut
        return 0.0
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _level_checker_loop(self) -> None:
        """Boucle de vérification des niveaux."""
        while self._is_running:
            await asyncio.sleep(self.config["check_interval"])
            
            try:
                with self._levels_lock:
                    for level in list(self._levels.values()):
                        if level.is_active and level.status in [StopLossStatus.ACTIVE, StopLossStatus.ADJUSTED]:
                            # Récupération du prix actuel
                            if self.data_manager:
                                price_data = await self.data_manager.retrieve(
                                    f"market:{level.symbol}:price",
                                    DataType.MARKET
                                )
                                if price_data:
                                    current_price = price_data.get("price", 0.0)
                                    await self.update_level(level.level_id, current_price)
                
            except Exception as e:
                logger.error(f"Level checker error: {e}")
    
    async def _adjustment_loop(self) -> None:
        """Boucle d'ajustement des niveaux."""
        while self._is_running:
            await asyncio.sleep(self.config["adjustment_interval"])
            
            try:
                with self._levels_lock:
                    for level in list(self._levels.values()):
                        if level.is_active and level.status in [StopLossStatus.ACTIVE, StopLossStatus.ADJUSTED]:
                            # Ajustement périodique
                            if level.adjustment != StopLossAdjustment.NONE:
                                # Récupération du prix actuel
                                if self.data_manager:
                                    price_data = await self.data_manager.retrieve(
                                        f"market:{level.symbol}:price",
                                        DataType.MARKET
                                    )
                                    if price_data:
                                        current_price = price_data.get("price", 0.0)
                                        new_stop = await self._calculate_stop(level, current_price)
                                        
                                        if new_stop != level.stop_price:
                                            level.stop_price = new_stop
                                            level.status = StopLossStatus.ADJUSTED
                                            self._stats["adjustments_made"] += 1
                                            await self._record_signal(level, "adjust", current_price)
                
            except Exception as e:
                logger.error(f"Adjustment loop error: {e}")
    
    async def _ai_optimization_loop(self) -> None:
        """Boucle d'optimisation IA des stops."""
        if not self.config["enable_ai_optimization"]:
            return
        
        while self._is_running:
            await asyncio.sleep(self.config["ai_optimization_interval"])
            
            try:
                # Optimisation des stops actifs
                with self._levels_lock:
                    for level in list(self._levels.values()):
                        if level.is_active and level.status in [StopLossStatus.ACTIVE, StopLossStatus.ADJUSTED]:
                            # Récupération des données historiques
                            if self.data_manager:
                                history = await self.data_manager.retrieve(
                                    f"market:{level.symbol}:history",
                                    DataType.HISTORICAL
                                )
                                
                                if history:
                                    # Optimisation du stop
                                    optimal_stop = await self._optimize_stop(level, history)
                                    
                                    if optimal_stop and optimal_stop != level.stop_price:
                                        level.stop_price = optimal_stop
                                        level.status = StopLossStatus.ADJUSTED
                                        logger.debug(f"AI optimized stop {level.level_id}: "
                                                   f"new stop={optimal_stop:.2f}")
                
            except Exception as e:
                logger.error(f"AI optimization loop error: {e}")
    
    async def _optimize_stop(
        self,
        level: StopLossLevel,
        history: Dict[str, Any]
    ) -> Optional[float]:
        """Optimise le stop loss avec IA."""
        # Simulation d'optimisation IA
        # Dans un système réel, on utiliserait un modèle ML
        
        # Analyse de la volatilité récente
        volatility = history.get("volatility", 0.02)
        
        # Analyse des supports
        supports = history.get("supports", [])
        
        if supports:
            # Utiliser le support le plus proche
            support = max([s for s in supports if s < level.entry_price])
            if support > level.stop_price:
                return support
        
        # Ajustement basé sur la volatilité
        optimal_distance = level.stop_percentage * (1 + volatility * 0.5)
        optimal_distance = max(self.config["min_stop"], min(self.config["max_stop"], optimal_distance))
        optimal_stop = level.entry_price * (1 - optimal_distance)
        
        return optimal_stop
    
    # ========== MÉTHODES PRIVÉES - ENREGISTREMENT ==========
    
    async def _record_signal(self, level: StopLossLevel, signal_type: str, price: float) -> None:
        """Enregistre un signal."""
        signal = StopLossSignal(
            level_id=level.level_id,
            signal_type=signal_type,
            price=price,
            metadata={
                "stop_price": level.stop_price,
                "entry_price": level.entry_price,
                "percentage": level.stop_percentage
            }
        )
        
        with self._signals_lock:
            self._signals.append(signal)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"stop_loss:signal:{signal.signal_id}",
                signal.to_dict(),
                DataType.SIGNAL
            )
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._levels_lock:
                    active_levels = len([l for l in self._levels.values() if l.is_active and l.status in [StopLossStatus.ACTIVE, StopLossStatus.ADJUSTED]])
                    hit_levels = len([l for l in self._levels.values() if l.status == StopLossStatus.HIT])
                    
                    self._stats["active_levels"] = active_levels
                    self._stats["hit_levels"] = hit_levels
                    self._stats["total_levels"] = len(self._levels)
                    
                    if hit_levels > 0:
                        self._stats["hit_rate"] = hit_levels / len(self._levels) if self._levels else 0
                        self._stats["avg_loss_protected"] = self._stats["total_loss_protected"] / hit_levels
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "stop_loss:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_level(self, level_id: str) -> Optional[StopLossLevel]:
        """Récupère un niveau de stop loss."""
        with self._levels_lock:
            return self._levels.get(level_id)
    
    async def get_levels(
        self,
        symbol: Optional[str] = None,
        status: Optional[StopLossStatus] = None
    ) -> List[StopLossLevel]:
        """Récupère les niveaux de stop loss."""
        with self._levels_lock:
            levels = list(self._levels.values())
            if symbol:
                levels = [l for l in levels if l.symbol == symbol]
            if status:
                levels = [l for l in levels if l.status == status]
            return levels
    
    async def get_signals(self, level_id: str, limit: int = 100) -> List[StopLossSignal]:
        """Récupère les signaux d'un niveau."""
        with self._signals_lock:
            signals = [s for s in self._signals if s.level_id == level_id]
            return list(signals)[-limit:]
    
    async def create_config(self, config: StopLossConfig) -> str:
        """Crée une configuration de stop loss."""
        with self._configs_lock:
            self._configs[config.config_id] = config
        
        if self.data_manager:
            await self.data_manager.store(
                f"stop_loss:config:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Stop loss configuration created: {config.config_id}")
        return config.config_id
    
    async def get_config(self, config_id: str) -> Optional[StopLossConfig]:
        """Récupère une configuration."""
        with self._configs_lock:
            return self._configs.get(config_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._levels_lock:
            self._stats["total_levels"] = len(self._levels)
        with self._configs_lock:
            self._stats["total_configs"] = len(self._configs)
        
        return self._stats.copy()
    
    async def export_levels(self, format: str = "json") -> str:
        """Exporte les niveaux de stop loss."""
        with self._levels_lock:
            levels = [l.to_dict() for l in self._levels.values()]
        
        if format == "json":
            return json.dumps(levels, indent=2)
        elif format == "csv":
            import csv
            import io
            output = io.StringIO()
            if levels:
                writer = csv.DictWriter(output, fieldnames=levels[0].keys())
                writer.writeheader()
                writer.writerows(levels)
            return output.getvalue()
        else:
            return json.dumps(levels)


# ============== STOP LOSS STRATEGY BUILDER ==============

class StopLossStrategyBuilder:
    """
    Constructeur de stratégies de stop loss.
    Facilite la création de stratégies complexes.
    """
    
    def __init__(self):
        self._config = StopLossConfig()
    
    def fixed_stop(self, stop_price: float) -> 'StopLossStrategyBuilder':
        """Définit un stop fixe."""
        self._config.stop_type = StopLossType.FIXED
        self._config.stop_value = stop_price
        return self
    
    def percentage_stop(self, percentage: float) -> 'StopLossStrategyBuilder':
        """Définit un stop en pourcentage."""
        self._config.stop_type = StopLossType.PERCENTAGE
        self._config.stop_value = percentage
        return self
    
    def atr_stop(self, multiplier: float) -> 'StopLossStrategyBuilder':
        """Définit un stop basé sur l'ATR."""
        self._config.stop_type = StopLossType.ATR_BASED
        self._config.atr_multiplier = multiplier
        return self
    
    def volatility_stop(self, multiplier: float) -> 'StopLossStrategyBuilder':
        """Définit un stop basé sur la volatilité."""
        self._config.stop_type = StopLossType.VOLATILITY_BASED
        self._config.volatility_multiplier = multiplier
        return self
    
    def support_stop(self) -> 'StopLossStrategyBuilder':
        """Définit un stop basé sur les supports."""
        self._config.stop_type = StopLossType.SUPPORT_BASED
        return self
    
    def trailing_stop(self, distance: float) -> 'StopLossStrategyBuilder':
        """Définit un stop suiveur."""
        self._config.stop_type = StopLossType.TRAILING
        self._config.stop_value = distance
        return self
    
    def break_even_stop(self) -> 'StopLossStrategyBuilder':
        """Définit un stop au point mort."""
        self._config.stop_type = StopLossType.BREAK_EVEN
        self._config.stop_value = 0.0
        return self
    
    def activate_on(self, activation: StopLossActivation) -> 'StopLossStrategyBuilder':
        """Définit l'activation."""
        self._config.activation = activation
        return self
    
    def adjust_with(self, adjustment: StopLossAdjustment) -> 'StopLossStrategyBuilder':
        """Définit l'ajustement."""
        self._config.adjustment = adjustment
        return self
    
    def with_limits(self, min_loss: float, max_loss: float) -> 'StopLossStrategyBuilder':
        """Définit les limites."""
        self._config.min_loss = min_loss
        self._config.max_loss = max_loss
        return self
    
    def build(self) -> StopLossConfig:
        """Construit la configuration."""
        return self._config


# ============== FACTORY ==============

class StopLossFactory:
    """Factory pour créer des composants de stop loss."""
    
    @staticmethod
    async def create_manager(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> StopLossManager:
        """Crée un gestionnaire de stop loss."""
        manager = StopLossManager(
            data_manager=data_manager,
            config=config
        )
        await manager.start()
        return manager
    
    @staticmethod
    def create_builder() -> StopLossStrategyBuilder:
        """Crée un constructeur de stratégies."""
        return StopLossStrategyBuilder()


# ============== EXPORT ==============

__all__ = [
    "StopLossType",
    "StopLossActivation",
    "StopLossAdjustment",
    "StopLossStatus",
    "StopLossLevel",
    "StopLossConfig",
    "StopLossSignal",
    "StopLossManagerInterface",
    "StopLossManager",
    "StopLossStrategyBuilder",
    "StopLossFactory"
]
