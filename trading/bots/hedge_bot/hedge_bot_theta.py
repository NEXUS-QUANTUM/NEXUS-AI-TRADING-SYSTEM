# trading/bots/hedge_bot/hedge_bot_data_theta.py
# Advanced Theta & Time Decay Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Theta Module - Module avancé de gestion du Theta et du time decay pour le Hedge Bot.
Gère l'analyse du time decay des options, l'optimisation des stratégies basées sur le theta,
la gestion du risque temporel et les stratégies de hedging adaptatives.
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
from scipy.stats import norm
from scipy.optimize import minimize_scalar

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_theta")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType, HedgeStrategy
)
from trading.bots.hedge_bot.hedge_bot_data_vega import (
    OptionContract, OptionGreeks, OptionType, VolatilityModel
)


# ============== ENUMS & TYPES ==============

class ThetaStrategy(Enum):
    """Stratégies de gestion du theta."""
    NEUTRAL = "neutral"              # Theta neutre
    POSITIVE = "positive"            # Theta positif (vendeur d'options)
    NEGATIVE = "negative"            # Theta négatif (acheteur d'options)
    ADAPTIVE = "adaptive"            # Adaptatif
    DYNAMIC = "dynamic"              # Dynamique
    OPTIMAL = "optimal"              # Optimisation du theta


class ThetaRegime(Enum):
    """Régimes de time decay."""
    ACCELERATED = "accelerated"      # Décélération accélérée (proche expiry)
    LINEAR = "linear"                # Décroissance linéaire
    DECELERATED = "decelerated"      # Décélération ralentie
    STABLE = "stable"                # Stable
    VOLATILE = "volatile"            # Volatile


class ThetaHedgeType(Enum):
    """Types de hedging theta."""
    DIRECT = "direct"                # Hedging direct
    OFFSET = "offset"                # Compensation
    DYNAMIC = "dynamic"              # Dynamique
    PORTFOLIO = "portfolio"          # Au niveau du portefeuille


# ============== DATA MODELS ==============

@dataclass
class ThetaMetrics:
    """Métriques de theta."""
    metrics_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    option_id: str = ""
    theta: float = 0.0
    theta_daily: float = 0.0
    theta_weekly: float = 0.0
    theta_monthly: float = 0.0
    theta_decay_rate: float = 0.0
    theta_breakeven: float = 0.0
    time_to_expiry: float = 0.0  # jours
    days_to_expiry: int = 0
    theta_regime: ThetaRegime = ThetaRegime.STABLE
    theta_velocity: float = 0.0  # changement du theta par jour
    theta_acceleration: float = 0.0  # changement de la vélocité
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class ThetaPosition:
    """Position theta."""
    position_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    option_id: str = ""
    quantity: float = 0.0
    theta_exposure: float = 0.0  # theta total
    theta_per_contract: float = 0.0
    theta_decay_cost: float = 0.0  # coût du time decay
    theta_hedge_ratio: float = 0.0
    theta_target: float = 0.0
    status: str = "active"  # active, hedged, closed
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class ThetaHedgeRecommendation:
    """Recommandation de hedging theta."""
    recommendation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    position_id: str = ""
    action: str = ""  # buy, sell, hold, adjust
    theta_change: float = 0.0
    quantity: float = 0.0
    option_type: OptionType = OptionType.CALL
    strike: float = 0.0
    expiry: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))
    cost_estimate: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    priority: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ThetaDecayProjection:
    """Projection du time decay."""
    projection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    option_id: str = ""
    days: List[int] = field(default_factory=list)
    theta_values: List[float] = field(default_factory=list)
    price_projections: List[float] = field(default_factory=list)
    decay_rate: float = 0.0
    terminal_value: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class ThetaEngineInterface(ABC):
    """Interface abstraite pour le moteur theta."""
    
    @abstractmethod
    async def calculate_theta_metrics(self, option: OptionContract) -> ThetaMetrics:
        """Calcule les métriques theta."""
        pass
    
    @abstractmethod
    async def hedge_theta(self, position: ThetaPosition) -> ThetaHedgeRecommendation:
        """Génère une recommandation de hedging theta."""
        pass
    
    @abstractmethod
    async def project_theta_decay(self, option: OptionContract, days: int) -> ThetaDecayProjection:
        """Projette le time decay."""
        pass


# ============== IMPLÉMENTATION ==============

class ThetaEngine(ThetaEngineInterface):
    """
    Moteur theta avancé pour le Hedge Bot.
    Gère l'analyse du time decay, l'optimisation des stratégies theta et le hedging.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Cache des métriques theta
        self._theta_cache: Dict[str, ThetaMetrics] = {}
        self._cache_lock = threading.RLock()
        
        # Positions theta
        self._positions: Dict[str, ThetaPosition] = {}
        self._pos_lock = threading.RLock()
        
        # Projetcions
        self._projections: Dict[str, ThetaDecayProjection] = {}
        self._proj_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "theta_calculations": 0,
            "hedge_recommendations": 0,
            "avg_theta_exposure": 0.0,
            "avg_decay_cost": 0.0,
            "portfolio_theta": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("ThetaEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "cache_size": 1000,
            "cache_ttl": 3600,  # 1 heure
            "enable_cache": True,
            "default_theta_regime": ThetaRegime.STABLE,
            "hedge_threshold": 0.01,
            "min_theta_hedge": 0.001,
            "max_theta_exposure": 0.10,
            "theta_target_range": (0.01, 0.05),
            "decay_projection_days": 30,
            "position_update_interval": 60,
            "risk_free_rate": 0.02,
            "dividend_yield": 0.0
        }
    
    async def start(self) -> None:
        """Démarre le moteur theta."""
        logger.info("ThetaEngine starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._position_updater())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("ThetaEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur theta."""
        logger.info("ThetaEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("ThetaEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def calculate_theta_metrics(self, option: OptionContract) -> ThetaMetrics:
        """Calcule les métriques theta."""
        start_time = time.time()
        self._stats["theta_calculations"] += 1
        
        try:
            # Vérification du cache
            cache_key = self._compute_cache_key(option)
            if self.config["enable_cache"] and cache_key in self._theta_cache:
                cached = self._theta_cache[cache_key]
                age = (datetime.now(timezone.utc) - cached.timestamp).total_seconds()
                if age < self.config["cache_ttl"]:
                    logger.debug(f"Theta cache hit: {cache_key}")
                    return cached
            
            # Calcul des métriques theta
            metrics = await self._compute_theta_metrics(option)
            
            # Mise en cache
            if self.config["enable_cache"]:
                with self._cache_lock:
                    if len(self._theta_cache) < self.config["cache_size"]:
                        self._theta_cache[cache_key] = metrics
            
            # Stockage persistant
            if self.data_manager:
                await self.data_manager.store(
                    f"theta:metrics:{metrics.metrics_id}",
                    metrics.to_dict(),
                    DataType.METRICS
                )
            
            execution_time = time.time() - start_time
            logger.debug(f"Theta metrics calculated: {option.option_id} "
                        f"theta={metrics.theta:.4f} regime={metrics.theta_regime.value} "
                        f"time={execution_time:.3f}s")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Theta metrics calculation error: {e}")
            raise
    
    async def hedge_theta(self, position: ThetaPosition) -> ThetaHedgeRecommendation:
        """Génère une recommandation de hedging theta."""
        self._stats["hedge_recommendations"] += 1
        
        try:
            # Analyse de l'exposition theta
            theta_exposure = position.theta_exposure
            theta_target = position.theta_target
            
            # Calcul de l'écart
            theta_deviation = theta_exposure - theta_target
            
            # Détermination de l'action
            action = "hold"
            quantity = 0.0
            option_type = OptionType.CALL
            
            if abs(theta_deviation) > self.config["hedge_threshold"]:
                if theta_deviation > 0:
                    # Trop de theta positif -> vendre des options
                    action = "sell"
                    option_type = OptionType.CALL
                    quantity = abs(theta_deviation) / (0.1)  # Facteur simplifié
                else:
                    # Trop de theta négatif -> acheter des options
                    action = "buy"
                    option_type = OptionType.PUT
                    quantity = abs(theta_deviation) / (0.1)
                
                # Ajustement pour éviter le sur-hedging
                quantity = min(quantity, abs(theta_exposure) * 1.5)
            
            # Calcul de la confiance
            confidence = 0.7 + 0.2 * (1 - abs(theta_deviation) / abs(theta_target))
            confidence = min(0.95, max(0.5, confidence))
            
            # Création de la recommandation
            recommendation = ThetaHedgeRecommendation(
                position_id=position.position_id,
                action=action,
                theta_change=theta_deviation,
                quantity=quantity,
                option_type=option_type,
                strike=100.0,  # Simplifié
                expiry=datetime.now(timezone.utc) + timedelta(days=30),
                cost_estimate=quantity * 1.0,  # Simplifié
                confidence=confidence,
                reason=f"{action} {quantity:.2f} {option_type.value} options to adjust theta exposure",
                priority=1 if abs(theta_deviation) > 0.02 else 2
            )
            
            logger.info(f"Theta hedge recommendation: {position.position_id} "
                       f"action={action} quantity={quantity:.2f} "
                       f"deviation={theta_deviation:.4f}")
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Theta hedge recommendation error: {e}")
            raise
    
    async def project_theta_decay(self, option: OptionContract, days: int) -> ThetaDecayProjection:
        """Projette le time decay."""
        try:
            # Calcul des métriques actuelles
            metrics = await self.calculate_theta_metrics(option)
            
            # Projection du time decay
            days_array = list(range(0, days + 1))
            theta_values = []
            price_projections = []
            
            current_price = option.underlying_price
            current_theta = metrics.theta
            
            for d in days_array:
                # Décroissance du theta (simplifiée)
                theta_at_day = current_theta * (1 - d / (metrics.days_to_expiry + 1))
                theta_values.append(theta_at_day)
                
                # Projection du prix (simplifiée)
                price_at_day = current_price * (1 + theta_at_day * d / 365)
                price_projections.append(price_at_day)
            
            # Calcul du taux de décroissance
            decay_rate = (theta_values[0] - theta_values[-1]) / days if days > 0 else 0
            
            # Création de la projection
            projection = ThetaDecayProjection(
                option_id=option.option_id,
                days=days_array,
                theta_values=theta_values,
                price_projections=price_projections,
                decay_rate=decay_rate,
                terminal_value=price_projections[-1] if price_projections else current_price,
                metadata={
                    "initial_theta": current_theta,
                    "days_to_expiry": metrics.days_to_expiry,
                    "decay_acceleration": metrics.theta_acceleration
                }
            )
            
            # Stockage
            with self._proj_lock:
                self._projections[projection.projection_id] = projection
            
            if self.data_manager:
                await self.data_manager.store(
                    f"theta:projection:{projection.projection_id}",
                    projection.to_dict(),
                    DataType.PROJECTION
                )
            
            logger.info(f"Theta decay projection created: {option.option_id} "
                       f"decay_rate={decay_rate:.4f} terminal={projection.terminal_value:.2f}")
            
            return projection
            
        except Exception as e:
            logger.error(f"Theta decay projection error: {e}")
            raise
    
    # ========== MÉTHODES PRIVÉES - CALCULS ==========
    
    async def _compute_theta_metrics(self, option: OptionContract) -> ThetaMetrics:
        """Calcule les métriques theta avancées."""
        # Paramètres
        S = option.underlying_price
        K = option.strike
        T = max((option.expiry - datetime.now(timezone.utc)).total_seconds() / (365.25 * 24 * 3600), 0.001)
        r = option.risk_free_rate
        q = option.dividend_yield
        sigma = option.implied_volatility
        days_to_expiry = max(1, int(T * 365))
        
        # Black-Scholes
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        # Distribution normale
        nd1 = norm.cdf(d1)
        nd2 = norm.cdf(d2)
        pdf_d1 = norm.pdf(d1)
        
        # Calcul du theta
        if option.option_type == OptionType.CALL:
            theta = (-S * math.exp(-q * T) * pdf_d1 * sigma / (2 * math.sqrt(T)
                    - r * K * math.exp(-r * T) * nd2
                    + q * S * math.exp(-q * T) * nd1)) / 365
        else:
            theta = (-S * math.exp(-q * T) * pdf_d1 * sigma / (2 * math.sqrt(T)
                    + r * K * math.exp(-r * T) * (1 - nd2)
                    - q * S * math.exp(-q * T) * (1 - nd1))) / 365
        
        # Métriques dérivées
        theta_daily = theta
        theta_weekly = theta * 7
        theta_monthly = theta * 30
        
        # Taux de décroissance
        if days_to_expiry > 1:
            # Calcul du theta pour un jour de plus
            T_plus = T + 1/365
            d1_plus = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T_plus) / (sigma * math.sqrt(T_plus))
            pdf_d1_plus = norm.pdf(d1_plus)
            
            if option.option_type == OptionType.CALL:
                theta_plus = (-S * math.exp(-q * T_plus) * pdf_d1_plus * sigma / (2 * math.sqrt(T_plus))
                             - r * K * math.exp(-r * T_plus) * norm.cdf(d1_plus - sigma * math.sqrt(T_plus))
                             + q * S * math.exp(-q * T_plus) * norm.cdf(d1_plus)) / 365
            else:
                theta_plus = (-S * math.exp(-q * T_plus) * pdf_d1_plus * sigma / (2 * math.sqrt(T_plus))
                             + r * K * math.exp(-r * T_plus) * (1 - norm.cdf(d1_plus - sigma * math.sqrt(T_plus)))
                             - q * S * math.exp(-q * T_plus) * (1 - norm.cdf(d1_plus))) / 365
            
            theta_decay_rate = (theta - theta_plus) / theta if theta != 0 else 0
        else:
            theta_decay_rate = 0
        
        # Calcul de la vélocité et accélération
        theta_velocity = theta_daily - (theta / days_to_expiry) if days_to_expiry > 0 else 0
        theta_acceleration = 2 * theta / (days_to_expiry ** 2) if days_to_expiry > 0 else 0
        
        # Détermination du régime theta
        if days_to_expiry <= 7:
            regime = ThetaRegime.ACCELERATED
        elif days_to_expiry <= 30:
            regime = ThetaRegime.LINEAR
        elif days_to_expiry <= 90:
            regime = ThetaRegime.DECELERATED
        elif days_to_expiry <= 180:
            regime = ThetaRegime.STABLE
        else:
            regime = ThetaRegime.STABLE
        
        # Point mort theta (prix auquel le theta s'annule)
        if theta != 0:
            theta_breakeven = S * (1 - theta / sigma) if sigma != 0 else S
        else:
            theta_breakeven = S
        
        return ThetaMetrics(
            option_id=option.option_id,
            theta=theta,
            theta_daily=theta_daily,
            theta_weekly=theta_weekly,
            theta_monthly=theta_monthly,
            theta_decay_rate=theta_decay_rate,
            theta_breakeven=theta_breakeven,
            time_to_expiry=T * 365,
            days_to_expiry=days_to_expiry,
            theta_regime=regime,
            theta_velocity=theta_velocity,
            theta_acceleration=theta_acceleration,
            metadata={
                "underlying_price": S,
                "strike": K,
                "implied_volatility": sigma,
                "risk_free_rate": r
            },
            tags=["theta", option.option_type.value]
        )
    
    # ========== MÉTHODES PRIVÉES - POSITIONS ==========
    
    async def _position_updater(self) -> None:
        """Met à jour les positions theta."""
        while self._is_running:
            await asyncio.sleep(self.config["position_update_interval"])
            
            try:
                with self._pos_lock:
                    for position in self._positions.values():
                        if position.status == "active":
                            # Mise à jour de l'exposition theta
                            # Dans un système réel, on recalculerait avec les données de marché
                            pass
                
            except Exception as e:
                logger.error(f"Position updater error: {e}")
    
    # ========== MÉTHODES PRIVÉES - CACHE ==========
    
    def _compute_cache_key(self, option: OptionContract) -> str:
        """Calcule une clé de cache."""
        key_data = {
            "option_id": option.option_id,
            "price": option.underlying_price,
            "vol": option.implied_volatility,
            "expiry": option.expiry.isoformat()
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                with self._cache_lock:
                    if len(self._theta_cache) > self.config["cache_size"]:
                        keys = list(self._theta_cache.keys())
                        for key in keys[:len(self._theta_cache) - self.config["cache_size"]]:
                            del self._theta_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    # ========== MÉTHODES PRIVÉES - MÉTRIQUES ==========
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._pos_lock:
                    if self._positions:
                        total_theta = sum(p.theta_exposure for p in self._positions.values())
                        total_cost = sum(p.theta_decay_cost for p in self._positions.values())
                        count = len(self._positions)
                        
                        self._stats["portfolio_theta"] = total_theta
                        self._stats["avg_theta_exposure"] = total_theta / count
                        self._stats["avg_decay_cost"] = total_cost / count
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "theta:metrics:stats",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def create_theta_position(
        self,
        option_id: str,
        quantity: float,
        theta_exposure: float,
        theta_target: Optional[float] = None
    ) -> ThetaPosition:
        """Crée une position theta."""
        position = ThetaPosition(
            option_id=option_id,
            quantity=quantity,
            theta_exposure=theta_exposure,
            theta_per_contract=theta_exposure / quantity if quantity != 0 else 0,
            theta_target=theta_target or self.config["theta_target_range"][0],
            status="active"
        )
        
        with self._pos_lock:
            self._positions[position.position_id] = position
        
        logger.info(f"Theta position created: {position.position_id} "
                   f"exposure={theta_exposure:.4f} quantity={quantity}")
        
        return position
    
    async def get_position(self, position_id: str) -> Optional[ThetaPosition]:
        """Récupère une position theta."""
        with self._pos_lock:
            return self._positions.get(position_id)
    
    async def get_positions(self, status: Optional[str] = None) -> List[ThetaPosition]:
        """Récupère les positions theta."""
        with self._pos_lock:
            positions = list(self._positions.values())
            if status:
                positions = [p for p in positions if p.status == status]
            return positions
    
    async def close_position(self, position_id: str) -> bool:
        """Ferme une position theta."""
        with self._pos_lock:
            position = self._positions.get(position_id)
            if not position:
                return False
            
            position.status = "closed"
            position.updated_at = datetime.now(timezone.utc)
            
            logger.info(f"Theta position closed: {position_id}")
            return True
    
    async def get_metrics(self, option_id: str) -> Optional[ThetaMetrics]:
        """Récupère les métriques theta d'une option."""
        with self._cache_lock:
            for metrics in self._theta_cache.values():
                if metrics.option_id == option_id:
                    return metrics
        
        if self.data_manager:
            data = await self.data_manager.retrieve(
                f"theta:metrics:{option_id}",
                DataType.METRICS
            )
            if data:
                return self._deserialize_metrics(data)
        
        return None
    
    async def get_projection(self, option_id: str) -> Optional[ThetaDecayProjection]:
        """Récupère une projection theta."""
        with self._proj_lock:
            for projection in self._projections.values():
                if projection.option_id == option_id:
                    return projection
        
        if self.data_manager:
            data = await self.data_manager.retrieve(
                f"theta:projection:{option_id}",
                DataType.PROJECTION
            )
            if data:
                return self._deserialize_projection(data)
        
        return None
    
    def _deserialize_metrics(self, data: Dict) -> ThetaMetrics:
        """Désérialise les métriques theta."""
        try:
            return ThetaMetrics(
                metrics_id=data.get("metrics_id", str(uuid.uuid4())),
                option_id=data.get("option_id", ""),
                theta=data.get("theta", 0.0),
                theta_daily=data.get("theta_daily", 0.0),
                theta_weekly=data.get("theta_weekly", 0.0),
                theta_monthly=data.get("theta_monthly", 0.0),
                theta_decay_rate=data.get("theta_decay_rate", 0.0),
                theta_breakeven=data.get("theta_breakeven", 0.0),
                time_to_expiry=data.get("time_to_expiry", 0.0),
                days_to_expiry=data.get("days_to_expiry", 0),
                theta_regime=ThetaRegime(data.get("theta_regime", "stable")),
                theta_velocity=data.get("theta_velocity", 0.0),
                theta_acceleration=data.get("theta_acceleration", 0.0),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", [])
            )
        except Exception as e:
            logger.error(f"Error deserializing theta metrics: {e}")
            return None
    
    def _deserialize_projection(self, data: Dict) -> Optional[ThetaDecayProjection]:
        """Désérialise une projection theta."""
        try:
            return ThetaDecayProjection(
                projection_id=data.get("projection_id", str(uuid.uuid4())),
                option_id=data.get("option_id", ""),
                days=data.get("days", []),
                theta_values=data.get("theta_values", []),
                price_projections=data.get("price_projections", []),
                decay_rate=data.get("decay_rate", 0.0),
                terminal_value=data.get("terminal_value", 0.0),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                metadata=data.get("metadata", {})
            )
        except Exception as e:
            logger.error(f"Error deserializing theta projection: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._cache_lock:
            self._stats["cache_size"] = len(self._theta_cache)
        with self._pos_lock:
            self._stats["positions_count"] = len(self._positions)
        with self._proj_lock:
            self._stats["projections_count"] = len(self._projections)
        
        return self._stats.copy()


# ============== THETA OPTIMIZER ==============

class ThetaOptimizer:
    """
    Optimiseur de stratégies theta.
    Optimise les positions theta pour maximiser le rendement ajusté du risque.
    """
    
    def __init__(self, engine: ThetaEngine):
        self.engine = engine
        self._optimization_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
    
    async def optimize_portfolio(
        self,
        positions: List[ThetaPosition],
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Optimise un portefeuille de positions theta."""
        try:
            # Extraction des données
            theta_exposures = [p.theta_exposure for p in positions]
            theta_costs = [p.theta_decay_cost for p in positions]
            
            # Fonction objectif: maximiser le theta net
            def objective(weights):
                portfolio_theta = sum(weights[i] * theta_exposures[i] for i in range(len(weights)))
                portfolio_cost = sum(weights[i] * theta_costs[i] for i in range(len(weights)))
                
                # Pénalité pour le coût
                return -(portfolio_theta - portfolio_cost * 0.1)
            
            # Contraintes
            bounds = [(0, 1) for _ in range(len(positions))]
            constraints = (
                {'type': 'eq', 'fun': lambda x: sum(x) - 1}  # Somme des poids = 1
            )
            
            # Optimisation (simplifiée)
            from scipy.optimize import minimize
            initial_weights = [1/len(positions)] * len(positions)
            result = minimize(
                objective,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )
            
            if result.success:
                optimal_weights = result.x
                optimal_theta = sum(optimal_weights[i] * theta_exposures[i] for i in range(len(optimal_weights)))
                optimal_cost = sum(optimal_weights[i] * theta_costs[i] for i in range(len(optimal_weights)))
                
                return {
                    "success": True,
                    "weights": optimal_weights.tolist(),
                    "portfolio_theta": optimal_theta,
                    "portfolio_cost": optimal_cost,
                    "sharpe_theta": optimal_theta / (optimal_cost + 0.001)
                }
            else:
                return {
                    "success": False,
                    "message": "Optimization failed"
                }
            
        except Exception as e:
            logger.error(f"Theta portfolio optimization error: {e}")
            return {"success": False, "error": str(e)}
    
    async def find_optimal_theta_strategy(
        self,
        options: List[OptionContract],
        target_theta: float
    ) -> Dict[str, Any]:
        """Trouve la stratégie theta optimale."""
        try:
            strategies = []
            
            for option in options:
                metrics = await self.engine.calculate_theta_metrics(option)
                
                # Ratio theta/prix
                theta_ratio = abs(metrics.theta) / option.underlying_price if option.underlying_price > 0 else 0
                
                strategies.append({
                    "option_id": option.option_id,
                    "theta": metrics.theta,
                    "theta_ratio": theta_ratio,
                    "days_to_expiry": metrics.days_to_expiry,
                    "regime": metrics.theta_regime.value,
                    "efficiency": theta_ratio * (1 - metrics.days_to_expiry / 365)
                })
            
            # Tri par efficacité
            strategies.sort(key=lambda x: x["efficiency"], reverse=True)
            
            # Sélection de la meilleure stratégie
            if strategies:
                best = strategies[0]
                return {
                    "success": True,
                    "recommended_strategy": best,
                    "alternatives": strategies[:5],
                    "target_theta": target_theta,
                    "estimated_theta": best["theta"]
                }
            
            return {"success": False, "message": "No strategies found"}
            
        except Exception as e:
            logger.error(f"Theta strategy optimization error: {e}")
            return {"success": False, "error": str(e)}


# ============== FACTORY ==============

class ThetaFactory:
    """Factory pour créer des composants theta."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ThetaEngine:
        """Crée un moteur theta."""
        engine = ThetaEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_optimizer(engine: ThetaEngine) -> ThetaOptimizer:
        """Crée un optimiseur theta."""
        return ThetaOptimizer(engine)


# ============== EXPORT ==============

__all__ = [
    "ThetaStrategy",
    "ThetaRegime",
    "ThetaHedgeType",
    "ThetaMetrics",
    "ThetaPosition",
    "ThetaHedgeRecommendation",
    "ThetaDecayProjection",
    "ThetaEngineInterface",
    "ThetaEngine",
    "ThetaOptimizer",
    "ThetaFactory"
]
