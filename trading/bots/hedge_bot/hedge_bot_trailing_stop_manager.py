# trading/bots/hedge_bot/hedge_bot_trailing_stop_manager.py
# Advanced Trailing Stop Management System for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Trailing Stop Manager - Module avancé de gestion des stops suiveurs pour le Hedge Bot.
Gère les stops suiveurs dynamiques, les stratégies de sortie adaptatives, l'optimisation des risques
et la protection des gains pour les positions de hedging.
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
logger = get_logger("hedge_bot_trailing_stop")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)


# ============== ENUMS & TYPES ==============

class TrailingStopType(Enum):
    """Types de stops suiveurs."""
    FIXED = "fixed"                    # Distance fixe
    PERCENTAGE = "percentage"          # Pourcentage de distance
    ATR_BASED = "atr_based"            # Basé sur l'ATR
    VOLATILITY_BASED = "volatility_based"  # Basé sur la volatilité
    ADAPTIVE = "adaptive"              # Adaptatif
    DYNAMIC = "dynamic"                # Dynamique
    CHANDELIER = "chandelier"          # Chandelier Exit
    PARABOLIC = "parabolic"            # Parabolique SAR


class StopActivationType(Enum):
    """Types d'activation du stop."""
    IMMEDIATE = "immediate"             # Activation immédiate
    BREAK_EVEN = "break_even"           # Après atteinte du point mort
    PROFIT_THRESHOLD = "profit_threshold"  # Après un certain profit
    TIME_BASED = "time_based"           # Après un certain temps
    PRICE_BASED = "price_based"         # Après un certain prix


class StopAdjustmentType(Enum):
    """Types d'ajustement du stop."""
    NONE = "none"                       # Pas d'ajustement
    LINEAR = "linear"                   # Linéaire
    EXPONENTIAL = "exponential"         # Exponentiel
    STEP = "step"                       # Par paliers
    AI_OPTIMIZED = "ai_optimized"       # Optimisé par IA


# ============== DATA MODELS ==============

@dataclass
class TrailingStop:
    """Modèle de stop suiveur."""
    stop_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    position_id: str = ""
    symbol: str = ""
    entry_price: float = 0.0
    current_price: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = 0.0
    stop_level: float = 0.0
    initial_stop_level: float = 0.0
    distance: float = 0.0
    distance_type: TrailingStopType = TrailingStopType.PERCENTAGE
    activation_type: StopActivationType = StopActivationType.IMMEDIATE
    adjustment_type: StopAdjustmentType = StopAdjustmentType.LINEAR
    is_active: bool = False
    is_triggered: bool = False
    trigger_price: Optional[float] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    triggered_at: Optional[datetime] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    pnl_at_trigger: float = 0.0
    protection_percentage: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "stop_id": self.stop_id,
            "position_id": self.position_id,
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "highest_price": self.highest_price,
            "lowest_price": self.lowest_price,
            "stop_level": self.stop_level,
            "initial_stop_level": self.initial_stop_level,
            "distance": self.distance,
            "distance_type": self.distance_type.value,
            "activation_type": self.activation_type.value,
            "adjustment_type": self.adjustment_type.value,
            "is_active": self.is_active,
            "is_triggered": self.is_triggered,
            "trigger_price": self.trigger_price,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "parameters": self.parameters,
            "metadata": self.metadata,
            "tags": self.tags,
            "pnl_at_trigger": self.pnl_at_trigger,
            "protection_percentage": self.protection_percentage
        }


@dataclass
class StopAdjustment:
    """Ajustement de stop."""
    adjustment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stop_id: str = ""
    old_level: float = 0.0
    new_level: float = 0.0
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StopSignal:
    """Signal de stop."""
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stop_id: str = ""
    signal_type: str = ""  # activate, adjust, trigger, cancel
    price: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class TrailingStopManagerInterface(ABC):
    """Interface abstraite pour le gestionnaire de stops suiveurs."""
    
    @abstractmethod
    async def create_stop(self, position: Dict[str, Any], config: Dict[str, Any]) -> TrailingStop:
        """Crée un stop suiveur."""
        pass
    
    @abstractmethod
    async def update_stop(self, stop_id: str, price: float) -> Optional[TrailingStop]:
        """Met à jour un stop suiveur."""
        pass
    
    @abstractmethod
    async def check_stop(self, stop_id: str) -> Optional[StopSignal]:
        """Vérifie si le stop est déclenché."""
        pass
    
    @abstractmethod
    async def cancel_stop(self, stop_id: str) -> bool:
        """Annule un stop suiveur."""
        pass


# ============== IMPLÉMENTATION ==============

class TrailingStopManager(TrailingStopManagerInterface):
    """
    Gestionnaire de stops suiveurs avancé pour le Hedge Bot.
    Implémente plusieurs stratégies de trailing stop pour la gestion des risques.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des stops
        self._stops: Dict[str, TrailingStop] = {}
        self._stops_lock = threading.RLock()
        
        # Gestion des ajustements
        self._adjustments: Dict[str, List[StopAdjustment]] = defaultdict(list)
        self._adj_lock = threading.RLock()
        
        # Gestion des signaux
        self._signals: deque = deque(maxlen=10000)
        self._signals_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "stops_created": 0,
            "stops_triggered": 0,
            "stops_cancelled": 0,
            "adjustments_made": 0,
            "avg_protection": 0.0,
            "total_pnl_protected": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("TrailingStopManager initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_stop_type": TrailingStopType.PERCENTAGE,
            "default_distance": 0.02,  # 2%
            "default_activation": StopActivationType.IMMEDIATE,
            "default_adjustment": StopAdjustmentType.LINEAR,
            "min_distance": 0.005,  # 0.5%
            "max_distance": 0.10,   # 10%
            "atr_period": 14,
            "atr_multiplier": 2.0,
            "volatility_period": 20,
            "volatility_multiplier": 1.5,
            "check_interval": 1.0,  # secondes
            "adjustment_interval": 5.0,  # secondes
            "max_adjustments_per_stop": 100,
            "enable_ai_optimization": True,
            "ai_optimization_interval": 60,
            "cache_size": 1000,
            "history_size": 10000
        }
    
    async def start(self) -> None:
        """Démarre le gestionnaire de stops suiveurs."""
        logger.info("TrailingStopManager starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._stop_checker_loop())
        asyncio.create_task(self._adjustment_loop())
        asyncio.create_task(self._ai_optimization_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("TrailingStopManager started")
    
    async def stop(self) -> None:
        """Arrête le gestionnaire de stops suiveurs."""
        logger.info("TrailingStopManager stopping...")
        self._is_running = False
        
        # Attente de la terminaison
        await asyncio.sleep(1)
        
        self._compute_pool.shutdown(wait=True)
        logger.info("TrailingStopManager stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_stop(self, position: Dict[str, Any], config: Dict[str, Any]) -> TrailingStop:
        """Crée un stop suiveur."""
        symbol = position.get("symbol", "")
        entry_price = position.get("entry_price", 0.0)
        position_id = position.get("position_id", str(uuid.uuid4()))
        
        # Configuration
        stop_type = TrailingStopType(config.get("type", self.config["default_stop_type"]))
        distance = config.get("distance", self.config["default_distance"])
        activation = StopActivationType(config.get("activation", self.config["default_activation"]))
        adjustment = StopAdjustmentType(config.get("adjustment", self.config["default_adjustment"]))
        
        # Calcul du stop initial
        initial_stop = await self._calculate_initial_stop(
            symbol, entry_price, stop_type, distance, position
        )
        
        # Création du stop
        stop = TrailingStop(
            position_id=position_id,
            symbol=symbol,
            entry_price=entry_price,
            current_price=entry_price,
            highest_price=entry_price,
            lowest_price=entry_price,
            stop_level=initial_stop,
            initial_stop_level=initial_stop,
            distance=distance,
            distance_type=stop_type,
            activation_type=activation,
            adjustment_type=adjustment,
            is_active=True,
            parameters={
                "type": stop_type.value,
                "distance": distance,
                "activation": activation.value,
                "adjustment": adjustment.value
            },
            tags=config.get("tags", [])
        )
        
        # Activation
        if activation == StopActivationType.IMMEDIATE:
            stop.is_active = True
        else:
            stop.is_active = False
        
        with self._stops_lock:
            self._stops[stop.stop_id] = stop
            self._stats["stops_created"] += 1
        
        # Enregistrement de la création
        await self._record_signal(stop, "create", entry_price)
        
        logger.info(f"Trailing stop created: {stop.stop_id} for {symbol} at {entry_price} "
                   f"type={stop_type.value} distance={distance:.2%}")
        
        return stop
    
    async def update_stop(self, stop_id: str, price: float) -> Optional[TrailingStop]:
        """Met à jour un stop suiveur."""
        with self._stops_lock:
            stop = self._stops.get(stop_id)
            if not stop or not stop.is_active:
                return None
        
        try:
            # Mise à jour des prix
            stop.current_price = price
            stop.highest_price = max(stop.highest_price, price)
            stop.lowest_price = min(stop.lowest_price, price)
            
            # Vérification de l'activation
            if not stop.is_active:
                if await self._check_activation(stop, price):
                    stop.is_active = True
                    stop.updated_at = datetime.now(timezone.utc)
                    await self._record_signal(stop, "activate", price)
                    logger.info(f"Stop {stop_id} activated at {price}")
            
            # Mise à jour du niveau de stop
            if stop.is_active:
                new_stop = await self._calculate_stop_level(stop, price)
                
                if new_stop != stop.stop_level:
                    # Enregistrement de l'ajustement
                    adjustment = StopAdjustment(
                        stop_id=stop.stop_id,
                        old_level=stop.stop_level,
                        new_level=new_stop,
                        reason="price_update"
                    )
                    
                    with self._adj_lock:
                        self._adjustments[stop.stop_id].append(adjustment)
                    
                    stop.stop_level = new_stop
                    stop.updated_at = datetime.now(timezone.utc)
                    self._stats["adjustments_made"] += 1
                    
                    await self._record_signal(stop, "adjust", price)
                    
                    logger.debug(f"Stop {stop_id} adjusted: {adjustment.old_level:.4f} -> {adjustment.new_level:.4f}")
            
            # Vérification du déclenchement
            if stop.is_active and price <= stop.stop_level:
                stop.is_triggered = True
                stop.trigger_price = price
                stop.triggered_at = datetime.now(timezone.utc)
                stop.pnl_at_trigger = (price - stop.entry_price) / stop.entry_price
                stop.protection_percentage = (stop.entry_price - price) / stop.entry_price
                
                self._stats["stops_triggered"] += 1
                self._stats["total_pnl_protected"] += stop.pnl_at_trigger
                
                await self._record_signal(stop, "trigger", price)
                
                logger.info(f"Stop {stop_id} triggered at {price} "
                           f"pnl={stop.pnl_at_trigger:.2%} "
                           f"protection={stop.protection_percentage:.2%}")
            
            return stop
            
        except Exception as e:
            logger.error(f"Stop update error: {e}")
            return None
    
    async def check_stop(self, stop_id: str) -> Optional[StopSignal]:
        """Vérifie si le stop est déclenché."""
        with self._stops_lock:
            stop = self._stops.get(stop_id)
            if not stop:
                return None
        
        if stop.is_triggered:
            return StopSignal(
                stop_id=stop.stop_id,
                signal_type="trigger",
                price=stop.trigger_price or stop.current_price,
                metadata={"pnl": stop.pnl_at_trigger}
            )
        
        return None
    
    async def cancel_stop(self, stop_id: str) -> bool:
        """Annule un stop suiveur."""
        with self._stops_lock:
            stop = self._stops.get(stop_id)
            if not stop:
                return False
            
            if not stop.is_active:
                return True
            
            stop.is_active = False
            stop.updated_at = datetime.now(timezone.utc)
            self._stats["stops_cancelled"] += 1
            
            await self._record_signal(stop, "cancel", stop.current_price)
            
            logger.info(f"Stop {stop_id} cancelled")
            return True
    
    # ========== MÉTHODES PRIVÉES - CALCULS ==========
    
    async def _calculate_initial_stop(
        self,
        symbol: str,
        price: float,
        stop_type: TrailingStopType,
        distance: float,
        position: Dict[str, Any]
    ) -> float:
        """Calcule le stop initial."""
        if stop_type == TrailingStopType.FIXED:
            return price - distance
        
        elif stop_type == TrailingStopType.PERCENTAGE:
            return price * (1 - distance)
        
        elif stop_type == TrailingStopType.ATR_BASED:
            atr = await self._get_atr(symbol)
            return price - (atr * self.config["atr_multiplier"])
        
        elif stop_type == TrailingStopType.VOLATILITY_BASED:
            volatility = await self._get_volatility(symbol)
            return price * (1 - volatility * self.config["volatility_multiplier"])
        
        elif stop_type == TrailingStopType.CHANDELIER:
            # Chandelier Exit: highest high - (ATR * multiplier)
            highest_high = await self._get_highest_high(symbol)
            atr = await self._get_atr(symbol)
            return highest_high - (atr * distance)
        
        elif stop_type == TrailingStopType.PARABOLIC:
            # Parabolic SAR simplifié
            af = 0.02  # Acceleration factor
            return price * (1 - af * distance)
        
        else:
            # Par défaut: pourcentage
            return price * (1 - self.config["default_distance"])
    
    async def _calculate_stop_level(self, stop: TrailingStop, price: float) -> float:
        """Calcule le nouveau niveau de stop."""
        # Si le stop est déjà déclenché, retourner le niveau actuel
        if stop.is_triggered:
            return stop.stop_level
        
        # Différentes stratégies d'ajustement
        if stop.adjustment_type == StopAdjustmentType.NONE:
            return stop.stop_level
        
        elif stop.adjustment_type == StopAdjustmentType.LINEAR:
            # Ajustement linéaire basé sur la progression du prix
            price_progress = (price - stop.entry_price) / stop.entry_price
            distance_multiplier = 1 + price_progress * 0.5
            new_distance = stop.distance * distance_multiplier
            new_distance = max(self.config["min_distance"], min(self.config["max_distance"], new_distance))
            return price * (1 - new_distance)
        
        elif stop.adjustment_type == StopAdjustmentType.EXPONENTIAL:
            # Ajustement exponentiel
            price_progress = (price - stop.entry_price) / stop.entry_price
            if price_progress > 0:
                distance_multiplier = math.exp(price_progress * 0.5)
                new_distance = stop.distance * distance_multiplier
                new_distance = max(self.config["min_distance"], min(self.config["max_distance"], new_distance))
                return price * (1 - new_distance)
            return stop.stop_level
        
        elif stop.adjustment_type == StopAdjustmentType.STEP:
            # Ajustement par paliers
            profit_levels = [
                (0.05, 0.01),   # +5% profit, réduction de 1%
                (0.10, 0.015),  # +10% profit, réduction de 1.5%
                (0.20, 0.02),   # +20% profit, réduction de 2%
                (0.30, 0.025),  # +30% profit, réduction de 2.5%
                (0.50, 0.03)    # +50% profit, réduction de 3%
            ]
            
            price_progress = (price - stop.entry_price) / stop.entry_price
            for threshold, reduction in profit_levels:
                if price_progress >= threshold:
                    new_distance = max(self.config["min_distance"], stop.distance - reduction)
                    return price * (1 - new_distance)
            
            return stop.stop_level
        
        elif stop.adjustment_type == StopAdjustmentType.AI_OPTIMIZED:
            # Optimisation par IA (simulée)
            if self.config["enable_ai_optimization"]:
                # Simulation d'optimisation
                volatility = await self._get_volatility(stop.symbol)
                optimal_distance = stop.distance * (1 + volatility * 0.1)
                optimal_distance = max(self.config["min_distance"], min(self.config["max_distance"], optimal_distance))
                return price * (1 - optimal_distance)
            return stop.stop_level
        
        else:
            return stop.stop_level
    
    async def _check_activation(self, stop: TrailingStop, price: float) -> bool:
        """Vérifie si le stop doit être activé."""
        if stop.activation_type == StopActivationType.IMMEDIATE:
            return True
        
        elif stop.activation_type == StopActivationType.BREAK_EVEN:
            # Activation après atteinte du point mort
            return price >= stop.entry_price
        
        elif stop.activation_type == StopActivationType.PROFIT_THRESHOLD:
            # Activation après un certain profit
            threshold = stop.parameters.get("profit_threshold", 0.02)
            return (price - stop.entry_price) / stop.entry_price >= threshold
        
        elif stop.activation_type == StopActivationType.TIME_BASED:
            # Activation après un certain temps
            threshold = stop.parameters.get("time_threshold", 3600)
            if stop.created_at:
                age = (datetime.now(timezone.utc) - stop.created_at).total_seconds()
                return age >= threshold
        
        elif stop.activation_type == StopActivationType.PRICE_BASED:
            # Activation après un certain prix
            target_price = stop.parameters.get("target_price", stop.entry_price * 1.05)
            return price >= target_price
        
        return False
    
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
    
    async def _get_highest_high(self, symbol: str) -> float:
        """Récupère le plus haut pour un symbole."""
        try:
            if self.data_manager:
                data = await self.data_manager.retrieve(
                    f"market:{symbol}:high",
                    DataType.MARKET
                )
                if data:
                    return data.get("value", 100.0)
        except:
            pass
        
        # Valeur par défaut
        return 100.0
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _stop_checker_loop(self) -> None:
        """Boucle de vérification des stops."""
        while self._is_running:
            await asyncio.sleep(self.config["check_interval"])
            
            try:
                with self._stops_lock:
                    for stop in list(self._stops.values()):
                        if stop.is_active and not stop.is_triggered:
                            # Récupération du prix actuel
                            if self.data_manager:
                                price_data = await self.data_manager.retrieve(
                                    f"market:{stop.symbol}:price",
                                    DataType.MARKET
                                )
                                if price_data:
                                    current_price = price_data.get("price", stop.current_price)
                                    await self.update_stop(stop.stop_id, current_price)
                
            except Exception as e:
                logger.error(f"Stop checker error: {e}")
    
    async def _adjustment_loop(self) -> None:
        """Boucle d'ajustement des stops."""
        while self._is_running:
            await asyncio.sleep(self.config["adjustment_interval"])
            
            try:
                with self._stops_lock:
                    for stop in list(self._stops.values()):
                        if stop.is_active and not stop.is_triggered:
                            # Ajustement périodique
                            if stop.adjustment_type != StopAdjustmentType.NONE:
                                current_price = stop.current_price
                                new_stop = await self._calculate_stop_level(stop, current_price)
                                
                                if new_stop != stop.stop_level:
                                    adjustment = StopAdjustment(
                                        stop_id=stop.stop_id,
                                        old_level=stop.stop_level,
                                        new_level=new_stop,
                                        reason="periodic"
                                    )
                                    
                                    with self._adj_lock:
                                        self._adjustments[stop.stop_id].append(adjustment)
                                    
                                    stop.stop_level = new_stop
                                    stop.updated_at = datetime.now(timezone.utc)
                                    self._stats["adjustments_made"] += 1
                                    
                                    logger.debug(f"Periodic adjustment for stop {stop.stop_id}: "
                                               f"{adjustment.old_level:.4f} -> {adjustment.new_level:.4f}")
                
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
                with self._stops_lock:
                    for stop in list(self._stops.values()):
                        if stop.is_active and not stop.is_triggered:
                            # Récupération des données historiques
                            if self.data_manager:
                                history = await self.data_manager.retrieve(
                                    f"market:{stop.symbol}:history",
                                    DataType.HISTORICAL
                                )
                                
                                if history:
                                    # Optimisation du stop
                                    optimal_distance = await self._optimize_stop_distance(
                                        stop, history
                                    )
                                    
                                    if optimal_distance and optimal_distance != stop.distance:
                                        stop.distance = optimal_distance
                                        logger.debug(f"AI optimized stop {stop.stop_id}: "
                                                   f"new distance={optimal_distance:.2%}")
                
            except Exception as e:
                logger.error(f"AI optimization loop error: {e}")
    
    async def _optimize_stop_distance(
        self,
        stop: TrailingStop,
        history: Dict[str, Any]
    ) -> Optional[float]:
        """Optimise la distance du stop avec IA."""
        # Simulation d'optimisation IA
        # Dans un système réel, on utiliserait un modèle ML
        
        # Analyse de la volatilité récente
        volatility = history.get("volatility", 0.02)
        
        # Analyse des drawdowns
        drawdowns = history.get("drawdowns", [])
        avg_drawdown = np.mean(drawdowns) if drawdowns else 0.02
        
        # Distance optimale
        optimal_distance = min(
            max(avg_drawdown * 1.2, self.config["min_distance"]),
            self.config["max_distance"]
        )
        
        return optimal_distance
    
    # ========== MÉTHODES PRIVÉES - ENREGISTREMENT ==========
    
    async def _record_signal(self, stop: TrailingStop, signal_type: str, price: float) -> None:
        """Enregistre un signal."""
        signal = StopSignal(
            stop_id=stop.stop_id,
            signal_type=signal_type,
            price=price,
            metadata={
                "stop_level": stop.stop_level,
                "entry_price": stop.entry_price
            }
        )
        
        with self._signals_lock:
            self._signals.append(signal)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"trailing_stop:signal:{signal.signal_id}",
                signal.to_dict(),
                DataType.SIGNAL
            )
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._stops_lock:
                    active_stops = len([s for s in self._stops.values() if s.is_active and not s.is_triggered])
                    triggered_stops = len([s for s in self._stops.values() if s.is_triggered])
                    
                    self._stats["active_stops"] = active_stops
                    self._stats["triggered_stops"] = triggered_stops
                    self._stats["total_stops"] = len(self._stops)
                
                # Calcul de la protection moyenne
                with self._stops_lock:
                    triggered = [s for s in self._stops.values() if s.is_triggered]
                    if triggered:
                        self._stats["avg_protection"] = np.mean([s.protection_percentage for s in triggered])
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "trailing_stop:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_stop(self, stop_id: str) -> Optional[TrailingStop]:
        """Récupère un stop suiveur."""
        with self._stops_lock:
            return self._stops.get(stop_id)
    
    async def get_stops(
        self,
        symbol: Optional[str] = None,
        active_only: bool = True
    ) -> List[TrailingStop]:
        """Récupère les stops suiveurs."""
        with self._stops_lock:
            stops = list(self._stops.values())
            if symbol:
                stops = [s for s in stops if s.symbol == symbol]
            if active_only:
                stops = [s for s in stops if s.is_active and not s.is_triggered]
            return stops
    
    async def get_adjustments(self, stop_id: str, limit: int = 100) -> List[StopAdjustment]:
        """Récupère les ajustements d'un stop."""
        with self._adj_lock:
            adjustments = self._adjustments.get(stop_id, [])
            return adjustments[-limit:]
    
    async def get_signals(self, stop_id: str, limit: int = 100) -> List[StopSignal]:
        """Récupère les signaux d'un stop."""
        with self._signals_lock:
            signals = [s for s in self._signals if s.stop_id == stop_id]
            return list(signals)[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._stops_lock:
            self._stats["active_stops"] = len([s for s in self._stops.values() if s.is_active and not s.is_triggered])
            self._stats["total_stops"] = len(self._stops)
        
        return self._stats.copy()
    
    async def export_stops(self, format: str = "json") -> str:
        """Exporte les stops suiveurs."""
        with self._stops_lock:
            stops = [s.to_dict() for s in self._stops.values()]
        
        if format == "json":
            return json.dumps(stops, indent=2)
        elif format == "csv":
            import csv
            import io
            output = io.StringIO()
            if stops:
                writer = csv.DictWriter(output, fieldnames=stops[0].keys())
                writer.writeheader()
                writer.writerows(stops)
            return output.getvalue()
        else:
            return json.dumps(stops)


# ============== FACTORY ==============

class TrailingStopFactory:
    """Factory pour créer des composants de stops suiveurs."""
    
    @staticmethod
    async def create_manager(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> TrailingStopManager:
        """Crée un gestionnaire de stops suiveurs."""
        manager = TrailingStopManager(
            data_manager=data_manager,
            config=config
        )
        await manager.start()
        return manager


# ============== EXPORT ==============

__all__ = [
    "TrailingStopType",
    "StopActivationType",
    "StopAdjustmentType",
    "TrailingStop",
    "StopAdjustment",
    "StopSignal",
    "TrailingStopManagerInterface",
    "TrailingStopManager",
    "TrailingStopFactory"
]
