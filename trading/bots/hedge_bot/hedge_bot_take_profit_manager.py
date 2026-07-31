# trading/bots/hedge_bot/hedge_bot_take_profit_manager.py
# Advanced Take Profit Management System for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Take Profit Manager - Module avancé de gestion des prises de profit pour le Hedge Bot.
Gère les stratégies de sortie, les objectifs de profit, les ajustements dynamiques,
et l'optimisation des rendements pour les positions de hedging.
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
logger = get_logger("hedge_bot_take_profit")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)


# ============== ENUMS & TYPES ==============

class TakeProfitType(Enum):
    """Types de prises de profit."""
    FIXED = "fixed"                    # Objectif fixe
    PERCENTAGE = "percentage"          # Pourcentage de gain
    RATIO = "ratio"                    # Ratio risque/récompense
    ATR_BASED = "atr_based"           # Basé sur l'ATR
    VOLATILITY_BASED = "volatility_based"  # Basé sur la volatilité
    RESISTANCE_BASED = "resistance_based"  # Basé sur les résistances
    ADAPTIVE = "adaptive"              # Adaptatif
    DYNAMIC = "dynamic"                # Dynamique
    PARTIAL = "partial"                # Prise de profit partielle
    SCALED = "scaled"                  # Échelonnée


class TakeProfitActivation(Enum):
    """Modes d'activation des prises de profit."""
    IMMEDIATE = "immediate"            # Activation immédiate
    AFTER_BREAK_EVEN = "after_break_even"  # Après point mort
    AFTER_TRAILING = "after_trailing"  # Après stop suiveur
    AFTER_TIME = "after_time"          # Après un certain temps
    BY_CONDITION = "by_condition"      # Par condition


class TakeProfitAdjustment(Enum):
    """Types d'ajustement des prises de profit."""
    NONE = "none"                      # Pas d'ajustement
    LINEAR = "linear"                  # Linéaire
    EXPONENTIAL = "exponential"        # Exponentiel
    STEP = "step"                      # Par paliers
    AI_OPTIMIZED = "ai_optimized"      # Optimisé par IA
    MARKET_BASED = "market_based"      # Basé sur le marché


class TakeProfitStatus(Enum):
    """Statuts des prises de profit."""
    PENDING = "pending"                # En attente
    ACTIVE = "active"                  # Active
    PARTIALLY_HIT = "partially_hit"    # Partiellement atteinte
    FULLY_HIT = "fully_hit"            # Totalement atteinte
    CANCELLED = "cancelled"            # Annulée
    EXPIRED = "expired"                # Expirée
    ADJUSTED = "adjusted"              # Ajustée


# ============== DATA MODELS ==============

@dataclass
class TakeProfitLevel:
    """Niveau de prise de profit."""
    level_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    position_id: str = ""
    symbol: str = ""
    entry_price: float = 0.0
    target_price: float = 0.0
    target_percentage: float = 0.0
    quantity_percentage: float = 1.0  # % de la position à couvrir
    priority: int = 1
    status: TakeProfitStatus = TakeProfitStatus.PENDING
    hit_price: Optional[float] = None
    hit_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    is_active: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "level_id": self.level_id,
            "position_id": self.position_id,
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "target_percentage": self.target_percentage,
            "quantity_percentage": self.quantity_percentage,
            "priority": self.priority,
            "status": self.status.value,
            "hit_price": self.hit_price,
            "hit_time": self.hit_time.isoformat() if self.hit_time else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags,
            "is_active": self.is_active
        }


@dataclass
class TakeProfitConfig:
    """Configuration de prise de profit."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    take_profit_type: TakeProfitType = TakeProfitType.PERCENTAGE
    activation: TakeProfitActivation = TakeProfitActivation.IMMEDIATE
    adjustment: TakeProfitAdjustment = TakeProfitAdjustment.NONE
    target_value: float = 0.02  # 2% par défaut
    risk_reward_ratio: float = 2.0
    partial_levels: List[Dict[str, float]] = field(default_factory=list)
    scaling: List[Dict[str, float]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True


@dataclass
class TakeProfitSignal:
    """Signal de prise de profit."""
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    level_id: str = ""
    signal_type: str = ""  # activate, adjust, hit, cancel
    price: float = 0.0
    quantity: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class TakeProfitManagerInterface(ABC):
    """Interface abstraite pour le gestionnaire de prises de profit."""
    
    @abstractmethod
    async def create_level(self, position: Dict[str, Any], config: TakeProfitConfig) -> TakeProfitLevel:
        """Crée un niveau de prise de profit."""
        pass
    
    @abstractmethod
    async def update_level(self, level_id: str, price: float) -> Optional[TakeProfitLevel]:
        """Met à jour un niveau de prise de profit."""
        pass
    
    @abstractmethod
    async def check_level(self, level_id: str) -> Optional[TakeProfitSignal]:
        """Vérifie si un niveau est atteint."""
        pass
    
    @abstractmethod
    async def cancel_level(self, level_id: str) -> bool:
        """Annule un niveau de prise de profit."""
        pass


# ============== IMPLÉMENTATION ==============

class TakeProfitManager(TakeProfitManagerInterface):
    """
    Gestionnaire de prises de profit avancé pour le Hedge Bot.
    Implémente plusieurs stratégies de sortie et d'optimisation des gains.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des niveaux
        self._levels: Dict[str, TakeProfitLevel] = {}
        self._levels_lock = threading.RLock()
        
        # Gestion des configurations
        self._configs: Dict[str, TakeProfitConfig] = {}
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
            "avg_profit_taken": 0.0,
            "total_profit_taken": 0.0,
            "partial_hits": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("TakeProfitManager initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_tp_type": TakeProfitType.PERCENTAGE,
            "default_target": 0.02,  # 2%
            "default_risk_reward": 2.0,
            "check_interval": 1.0,  # secondes
            "adjustment_interval": 5.0,  # secondes
            "max_adjustments": 100,
            "enable_ai_optimization": True,
            "ai_optimization_interval": 60,
            "partial_level_count": 3,
            "scaling_factor": 0.5,
            "cache_size": 1000,
            "history_size": 10000
        }
    
    async def start(self) -> None:
        """Démarre le gestionnaire de prises de profit."""
        logger.info("TakeProfitManager starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._level_checker_loop())
        asyncio.create_task(self._adjustment_loop())
        asyncio.create_task(self._ai_optimization_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("TakeProfitManager started")
    
    async def stop(self) -> None:
        """Arrête le gestionnaire de prises de profit."""
        logger.info("TakeProfitManager stopping...")
        self._is_running = False
        
        # Attente de la terminaison
        await asyncio.sleep(1)
        
        self._compute_pool.shutdown(wait=True)
        logger.info("TakeProfitManager stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_level(
        self,
        position: Dict[str, Any],
        config: TakeProfitConfig
    ) -> TakeProfitLevel:
        """Crée un niveau de prise de profit."""
        symbol = position.get("symbol", "")
        entry_price = position.get("entry_price", 0.0)
        position_id = position.get("position_id", str(uuid.uuid4()))
        
        # Calcul du prix cible
        if config.take_profit_type == TakeProfitType.FIXED:
            target_price = entry_price + config.target_value
        
        elif config.take_profit_type == TakeProfitType.PERCENTAGE:
            target_price = entry_price * (1 + config.target_value)
        
        elif config.take_profit_type == TakeProfitType.RATIO:
            # Ratio risque/récompense
            stop_loss = position.get("stop_loss", entry_price * 0.98)
            risk = entry_price - stop_loss
            target_price = entry_price + risk * config.risk_reward_ratio
        
        elif config.take_profit_type == TakeProfitType.ATR_BASED:
            atr = await self._get_atr(symbol)
            target_price = entry_price + atr * config.target_value
        
        elif config.take_profit_type == TakeProfitType.RESISTANCE_BASED:
            resistance = await self._get_resistance(symbol)
            target_price = resistance
        
        else:
            # Par défaut: pourcentage
            target_price = entry_price * (1 + self.config["default_target"])
        
        # Création du niveau
        level = TakeProfitLevel(
            position_id=position_id,
            symbol=symbol,
            entry_price=entry_price,
            target_price=target_price,
            target_percentage=(target_price - entry_price) / entry_price,
            quantity_percentage=1.0,
            status=TakeProfitStatus.PENDING,
            metadata={
                "config_id": config.config_id,
                "tp_type": config.take_profit_type.value,
                "activation": config.activation.value,
                "adjustment": config.adjustment.value
            },
            tags=config.tags
        )
        
        # Activation
        if config.activation == TakeProfitActivation.IMMEDIATE:
            level.status = TakeProfitStatus.ACTIVE
        
        with self._levels_lock:
            self._levels[level.level_id] = level
            self._stats["levels_created"] += 1
        
        # Enregistrement de la création
        await self._record_signal(level, "create", level.target_price)
        
        logger.info(f"Take profit level created: {level.level_id} for {symbol} "
                   f"target={level.target_price:.2f} ({level.target_percentage:.2%})")
        
        return level
    
    async def update_level(self, level_id: str, price: float) -> Optional[TakeProfitLevel]:
        """Met à jour un niveau de prise de profit."""
        with self._levels_lock:
            level = self._levels.get(level_id)
            if not level or not level.is_active:
                return None
        
        try:
            # Mise à jour du prix
            level.updated_at = datetime.now(timezone.utc)
            
            # Vérification de l'activation
            if level.status == TakeProfitStatus.PENDING:
                if await self._check_activation(level, price):
                    level.status = TakeProfitStatus.ACTIVE
                    await self._record_signal(level, "activate", price)
                    logger.info(f"Take profit {level_id} activated at {price}")
            
            # Ajustement du niveau
            if level.status == TakeProfitStatus.ACTIVE:
                new_target = await self._calculate_target(level, price)
                
                if new_target != level.target_price:
                    old_target = level.target_price
                    level.target_price = new_target
                    level.target_percentage = (new_target - level.entry_price) / level.entry_price
                    level.status = TakeProfitStatus.ADJUSTED
                    self._stats["adjustments_made"] += 1
                    
                    await self._record_signal(level, "adjust", price)
                    
                    logger.debug(f"Take profit {level_id} adjusted: {old_target:.2f} -> {new_target:.2f}")
            
            # Vérification de l'atteinte
            if level.status in [TakeProfitStatus.ACTIVE, TakeProfitStatus.ADJUSTED]:
                if await self._check_hit(level, price):
                    level.status = TakeProfitStatus.FULLY_HIT
                    level.hit_price = price
                    level.hit_time = datetime.now(timezone.utc)
                    
                    self._stats["levels_hit"] += 1
                    self._stats["total_profit_taken"] += level.target_percentage
                    
                    await self._record_signal(level, "hit", price)
                    
                    logger.info(f"Take profit {level_id} hit at {price} "
                               f"profit={level.target_percentage:.2%}")
            
            return level
            
        except Exception as e:
            logger.error(f"Level update error: {e}")
            return None
    
    async def check_level(self, level_id: str) -> Optional[TakeProfitSignal]:
        """Vérifie si un niveau est atteint."""
        with self._levels_lock:
            level = self._levels.get(level_id)
            if not level:
                return None
        
        if level.status == TakeProfitStatus.FULLY_HIT:
            return TakeProfitSignal(
                level_id=level.level_id,
                signal_type="hit",
                price=level.hit_price or 0.0,
                quantity=level.quantity_percentage,
                metadata={"profit": level.target_percentage}
            )
        
        if level.status == TakeProfitStatus.CANCELLED:
            return TakeProfitSignal(
                level_id=level.level_id,
                signal_type="cancelled",
                price=0.0
            )
        
        return None
    
    async def cancel_level(self, level_id: str) -> bool:
        """Annule un niveau de prise de profit."""
        with self._levels_lock:
            level = self._levels.get(level_id)
            if not level:
                return False
            
            if level.status in [TakeProfitStatus.FULLY_HIT, TakeProfitStatus.CANCELLED]:
                return True
            
            level.status = TakeProfitStatus.CANCELLED
            level.is_active = False
            level.updated_at = datetime.now(timezone.utc)
            self._stats["levels_cancelled"] += 1
            
            await self._record_signal(level, "cancel", 0.0)
            
            logger.info(f"Take profit {level_id} cancelled")
            return True
    
    # ========== MÉTHODES PRIVÉES - CALCULS ==========
    
    async def _calculate_target(
        self,
        level: TakeProfitLevel,
        price: float
    ) -> float:
        """Calcule le nouveau niveau de prise de profit."""
        if level.target_percentage == 0:
            return level.target_price
        
        # Différentes stratégies d'ajustement
        if level.metadata.get("adjustment") == TakeProfitAdjustment.NONE.value:
            return level.target_price
        
        elif level.metadata.get("adjustment") == TakeProfitAdjustment.LINEAR.value:
            # Ajustement linéaire basé sur la progression du prix
            progress = (price - level.entry_price) / level.entry_price
            if progress > 0:
                # Augmentation du target
                target_multiplier = 1 + progress * 0.5
                new_target = level.entry_price * (1 + level.target_percentage * target_multiplier)
                return new_target
            return level.target_price
        
        elif level.metadata.get("adjustment") == TakeProfitAdjustment.EXPONENTIAL.value:
            # Ajustement exponentiel
            progress = (price - level.entry_price) / level.entry_price
            if progress > 0:
                target_multiplier = math.exp(progress * 0.5)
                new_target = level.entry_price * (1 + level.target_percentage * target_multiplier)
                return new_target
            return level.target_price
        
        elif level.metadata.get("adjustment") == TakeProfitAdjustment.STEP.value:
            # Ajustement par paliers
            profit_levels = [
                (0.05, 0.01),   # +5% profit, +1% cible
                (0.10, 0.02),   # +10% profit, +2% cible
                (0.20, 0.03),   # +20% profit, +3% cible
                (0.30, 0.04)    # +30% profit, +4% cible
            ]
            
            progress = (price - level.entry_price) / level.entry_price
            additional_target = 0
            for threshold, increment in profit_levels:
                if progress >= threshold:
                    additional_target = increment
            
            if additional_target > 0:
                new_target = level.entry_price * (1 + level.target_percentage + additional_target)
                return new_target
            return level.target_price
        
        elif level.metadata.get("adjustment") == TakeProfitAdjustment.MARKET_BASED.value:
            # Ajustement basé sur les conditions de marché
            volatility = await self._get_volatility(level.symbol)
            if volatility > 0:
                # Augmentation de la cible en période de forte volatilité
                volatility_factor = 1 + volatility * 0.2
                new_target = level.entry_price * (1 + level.target_percentage * volatility_factor)
                return new_target
            return level.target_price
        
        else:
            return level.target_price
    
    async def _check_activation(
        self,
        level: TakeProfitLevel,
        price: float
    ) -> bool:
        """Vérifie si le niveau doit être activé."""
        activation = level.metadata.get("activation", "immediate")
        
        if activation == "immediate":
            return True
        
        elif activation == "after_break_even":
            # Activation après le point mort
            return price >= level.entry_price
        
        elif activation == "after_trailing":
            # Activation après que le stop suiveur soit déclenché
            # Dans un système réel, on vérifierait l'état du trailing stop
            return True
        
        elif activation == "after_time":
            # Activation après un certain temps
            threshold = level.metadata.get("time_threshold", 3600)
            if level.created_at:
                age = (datetime.now(timezone.utc) - level.created_at).total_seconds()
                return age >= threshold
        
        elif activation == "by_condition":
            # Activation par condition
            condition = level.metadata.get("condition", "price > entry_price")
            # Évaluation de la condition (simplifiée)
            try:
                return eval(condition, {"price": price, "entry_price": level.entry_price})
            except:
                return False
        
        return False
    
    async def _check_hit(self, level: TakeProfitLevel, price: float) -> bool:
        """Vérifie si le niveau de profit est atteint."""
        return price >= level.target_price
    
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
                        if level.is_active and level.status in [TakeProfitStatus.ACTIVE, TakeProfitStatus.ADJUSTED]:
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
                        if level.is_active and level.status in [TakeProfitStatus.ACTIVE, TakeProfitStatus.ADJUSTED]:
                            # Ajustement périodique
                            if level.metadata.get("adjustment") != TakeProfitAdjustment.NONE.value:
                                # Récupération du prix actuel
                                if self.data_manager:
                                    price_data = await self.data_manager.retrieve(
                                        f"market:{level.symbol}:price",
                                        DataType.MARKET
                                    )
                                    if price_data:
                                        current_price = price_data.get("price", 0.0)
                                        new_target = await self._calculate_target(level, current_price)
                                        
                                        if new_target != level.target_price:
                                            level.target_price = new_target
                                            level.status = TakeProfitStatus.ADJUSTED
                                            self._stats["adjustments_made"] += 1
                                            await self._record_signal(level, "adjust", current_price)
                
            except Exception as e:
                logger.error(f"Adjustment loop error: {e}")
    
    async def _ai_optimization_loop(self) -> None:
        """Boucle d'optimisation IA des niveaux."""
        if not self.config["enable_ai_optimization"]:
            return
        
        while self._is_running:
            await asyncio.sleep(self.config["ai_optimization_interval"])
            
            try:
                # Optimisation des niveaux actifs
                with self._levels_lock:
                    for level in list(self._levels.values()):
                        if level.is_active and level.status in [TakeProfitStatus.ACTIVE, TakeProfitStatus.ADJUSTED]:
                            # Récupération des données historiques
                            if self.data_manager:
                                history = await self.data_manager.retrieve(
                                    f"market:{level.symbol}:history",
                                    DataType.HISTORICAL
                                )
                                
                                if history:
                                    # Optimisation du niveau
                                    optimal_target = await self._optimize_target(
                                        level, history
                                    )
                                    
                                    if optimal_target and optimal_target != level.target_price:
                                        level.target_price = optimal_target
                                        level.status = TakeProfitStatus.ADJUSTED
                                        logger.debug(f"AI optimized take profit {level.level_id}: "
                                                   f"new target={optimal_target:.2f}")
                
            except Exception as e:
                logger.error(f"AI optimization loop error: {e}")
    
    async def _optimize_target(
        self,
        level: TakeProfitLevel,
        history: Dict[str, Any]
    ) -> Optional[float]:
        """Optimise le niveau de prise de profit avec IA."""
        # Simulation d'optimisation IA
        # Dans un système réel, on utiliserait un modèle ML
        
        # Analyse de la volatilité récente
        volatility = history.get("volatility", 0.02)
        
        # Analyse des niveaux de résistance
        resistances = history.get("resistances", [])
        
        if resistances:
            # Utiliser la résistance la plus proche
            target = min(
                [r for r in resistances if r > level.entry_price],
                key=lambda r: (r - level.entry_price) / level.entry_price
            )
            return target
        
        # Ajustement basé sur la volatilité
        target_multiplier = 1 + volatility * 0.5
        optimal_target = level.entry_price * (1 + level.target_percentage * target_multiplier)
        
        return optimal_target
    
    # ========== MÉTHODES PRIVÉES - ENREGISTREMENT ==========
    
    async def _record_signal(self, level: TakeProfitLevel, signal_type: str, price: float) -> None:
        """Enregistre un signal."""
        signal = TakeProfitSignal(
            level_id=level.level_id,
            signal_type=signal_type,
            price=price,
            quantity=level.quantity_percentage,
            metadata={
                "target_price": level.target_price,
                "entry_price": level.entry_price,
                "percentage": level.target_percentage
            }
        )
        
        with self._signals_lock:
            self._signals.append(signal)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"take_profit:signal:{signal.signal_id}",
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
                    active_levels = len([l for l in self._levels.values() if l.is_active and l.status in [TakeProfitStatus.ACTIVE, TakeProfitStatus.ADJUSTED]])
                    hit_levels = len([l for l in self._levels.values() if l.status == TakeProfitStatus.FULLY_HIT])
                    
                    self._stats["active_levels"] = active_levels
                    self._stats["hit_levels"] = hit_levels
                    self._stats["total_levels"] = len(self._levels)
                
                # Calcul du profit moyen
                with self._levels_lock:
                    hit = [l for l in self._levels.values() if l.status == TakeProfitStatus.FULLY_HIT]
                    if hit:
                        self._stats["avg_profit_taken"] = np.mean([l.target_percentage for l in hit])
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "take_profit:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_level(self, level_id: str) -> Optional[TakeProfitLevel]:
        """Récupère un niveau de prise de profit."""
        with self._levels_lock:
            return self._levels.get(level_id)
    
    async def get_levels(
        self,
        symbol: Optional[str] = None,
        status: Optional[TakeProfitStatus] = None
    ) -> List[TakeProfitLevel]:
        """Récupère les niveaux de prise de profit."""
        with self._levels_lock:
            levels = list(self._levels.values())
            if symbol:
                levels = [l for l in levels if l.symbol == symbol]
            if status:
                levels = [l for l in levels if l.status == status]
            return levels
    
    async def get_signals(self, level_id: str, limit: int = 100) -> List[TakeProfitSignal]:
        """Récupère les signaux d'un niveau."""
        with self._signals_lock:
            signals = [s for s in self._signals if s.level_id == level_id]
            return list(signals)[-limit:]
    
    async def create_config(self, config: TakeProfitConfig) -> str:
        """Crée une configuration de prise de profit."""
        with self._configs_lock:
            self._configs[config.config_id] = config
        
        if self.data_manager:
            await self.data_manager.store(
                f"take_profit:config:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Take profit configuration created: {config.config_id}")
        return config.config_id
    
    async def get_config(self, config_id: str) -> Optional[TakeProfitConfig]:
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
        """Exporte les niveaux de prise de profit."""
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


# ============== TAKE PROFIT STRATEGY BUILDER ==============

class TakeProfitStrategyBuilder:
    """
    Constructeur de stratégies de prise de profit.
    Facilite la création de stratégies complexes.
    """
    
    def __init__(self):
        self._config = TakeProfitConfig()
    
    def fixed_target(self, target: float) -> 'TakeProfitStrategyBuilder':
        """Définit une cible fixe."""
        self._config.take_profit_type = TakeProfitType.FIXED
        self._config.target_value = target
        return self
    
    def percentage_target(self, percentage: float) -> 'TakeProfitStrategyBuilder':
        """Définit une cible en pourcentage."""
        self._config.take_profit_type = TakeProfitType.PERCENTAGE
        self._config.target_value = percentage
        return self
    
    def risk_reward(self, ratio: float) -> 'TakeProfitStrategyBuilder':
        """Définit un ratio risque/récompense."""
        self._config.take_profit_type = TakeProfitType.RATIO
        self._config.risk_reward_ratio = ratio
        return self
    
    def atr_based(self, multiplier: float) -> 'TakeProfitStrategyBuilder':
        """Définit une cible basée sur l'ATR."""
        self._config.take_profit_type = TakeProfitType.ATR_BASED
        self._config.target_value = multiplier
        return self
    
    def with_partial_levels(self, levels: List[Dict[str, float]]) -> 'TakeProfitStrategyBuilder':
        """Ajoute des niveaux partiels."""
        self._config.partial_levels = levels
        return self
    
    def with_scaling(self, scaling: List[Dict[str, float]]) -> 'TakeProfitStrategyBuilder':
        """Ajoute un échelonnage."""
        self._config.scaling = scaling
        return self
    
    def activate_on(self, activation: TakeProfitActivation) -> 'TakeProfitStrategyBuilder':
        """Définit l'activation."""
        self._config.activation = activation
        return self
    
    def adjust_with(self, adjustment: TakeProfitAdjustment) -> 'TakeProfitStrategyBuilder':
        """Définit l'ajustement."""
        self._config.adjustment = adjustment
        return self
    
    def build(self) -> TakeProfitConfig:
        """Construit la configuration."""
        return self._config


# ============== FACTORY ==============

class TakeProfitFactory:
    """Factory pour créer des composants de prise de profit."""
    
    @staticmethod
    async def create_manager(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> TakeProfitManager:
        """Crée un gestionnaire de prises de profit."""
        manager = TakeProfitManager(
            data_manager=data_manager,
            config=config
        )
        await manager.start()
        return manager
    
    @staticmethod
    def create_builder() -> TakeProfitStrategyBuilder:
        """Crée un constructeur de stratégies."""
        return TakeProfitStrategyBuilder()


# ============== EXPORT ==============

__all__ = [
    "TakeProfitType",
    "TakeProfitActivation",
    "TakeProfitAdjustment",
    "TakeProfitStatus",
    "TakeProfitLevel",
    "TakeProfitConfig",
    "TakeProfitSignal",
    "TakeProfitManagerInterface",
    "TakeProfitManager",
    "TakeProfitStrategyBuilder",
    "TakeProfitFactory"
]
