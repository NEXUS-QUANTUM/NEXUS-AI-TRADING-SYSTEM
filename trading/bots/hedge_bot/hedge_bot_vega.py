# trading/bots/hedge_bot/hedge_bot_data_vega.py
# Advanced Vega & Options Greeks Integration for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Vega Module - Module avancé de gestion des options grecques et du Vega pour le Hedge Bot.
Intègre le calcul des grecques (Delta, Gamma, Vega, Theta, Rho), la gestion du risque de volatilité,
l'analyse des options et les stratégies de hedging basées sur les dérivés.
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
import hashlib
import pickle
from scipy.stats import norm
from scipy.optimize import brentq

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_vega")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType, HedgeStrategy
)


# ============== ENUMS & TYPES ==============

class OptionType(Enum):
    """Types d'options."""
    CALL = "call"
    PUT = "put"


class OptionStyle(Enum):
    """Styles d'options."""
    EUROPEAN = "european"
    AMERICAN = "american"
    EXOTIC = "exotic"


class VolatilityModel(Enum):
    """Modèles de volatilité."""
    BLACK_SCHOLES = "black_scholes"
    HESTON = "heston"
    SABR = "sabr"
    GARCH = "garch"
    LOCAL_VOL = "local_vol"
    STOCHASTIC_VOL = "stochastic_vol"


class GreeksType(Enum):
    """Types de grecques."""
    DELTA = "delta"
    GAMMA = "gamma"
    VEGA = "vega"
    THETA = "theta"
    RHO = "rho"
    VANNA = "vanna"
    VOLGA = "volga"
    CHARM = "charm"
    VETA = "veta"
    SPEED = "speed"
    ZOMMA = "zomma"
    COLOR = "color"
    ULTIMA = "ultima"


# ============== DATA MODELS ==============

@dataclass
class OptionContract:
    """Modèle de contrat d'option."""
    option_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    option_type: OptionType = OptionType.CALL
    strike: float = 0.0
    expiry: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))
    underlying_price: float = 0.0
    implied_volatility: float = 0.2
    risk_free_rate: float = 0.02
    dividend_yield: float = 0.0
    style: OptionStyle = OptionStyle.EUROPEAN
    volume: int = 0
    open_interest: int = 0
    bid_price: float = 0.0
    ask_price: float = 0.0
    last_price: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OptionGreeks:
    """Modèle des grecques d'une option."""
    greeks_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    option_id: str = ""
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    rho: float = 0.0
    vanna: float = 0.0
    volga: float = 0.0
    charm: float = 0.0
    veta: float = 0.0
    speed: float = 0.0
    zomma: float = 0.0
    color: float = 0.0
    ultima: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    implied_volatility: float = 0.0
    historical_volatility: float = 0.0
    model: VolatilityModel = VolatilityModel.BLACK_SCHOLES
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "greeks_id": self.greeks_id,
            "option_id": self.option_id,
            "delta": self.delta,
            "gamma": self.gamma,
            "vega": self.vega,
            "theta": self.theta,
            "rho": self.rho,
            "vanna": self.vanna,
            "volga": self.volga,
            "charm": self.charm,
            "veta": self.veta,
            "speed": self.speed,
            "zomma": self.zomma,
            "color": self.color,
            "ultima": self.ultima,
            "timestamp": self.timestamp.isoformat(),
            "implied_volatility": self.implied_volatility,
            "historical_volatility": self.historical_volatility,
            "model": self.model.value,
            "metadata": self.metadata
        }


@dataclass
class VegaPosition:
    """Position de Vega pour le hedging."""
    position_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    option_id: str = ""
    quantity: float = 0.0
    vega_exposure: float = 0.0
    delta_exposure: float = 0.0
    gamma_exposure: float = 0.0
    theta_exposure: float = 0.0
    underlying_price: float = 0.0
    implied_volatility: float = 0.0
    hedged: bool = False
    hedge_ratio: float = 0.0
    hedge_cost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class VolatilitySurface:
    """Surface de volatilité."""
    surface_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    strikes: List[float] = field(default_factory=list)
    expiries: List[datetime] = field(default_factory=list)
    volatilities: List[List[float]] = field(default_factory=list)
    risk_free_rate: float = 0.02
    dividend_yield: float = 0.0
    spot_price: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    model: VolatilityModel = VolatilityModel.SABR
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "surface_id": self.surface_id,
            "symbol": self.symbol,
            "strikes": self.strikes,
            "expiries": [e.isoformat() for e in self.expiries],
            "volatilities": self.volatilities,
            "risk_free_rate": self.risk_free_rate,
            "dividend_yield": self.dividend_yield,
            "spot_price": self.spot_price,
            "timestamp": self.timestamp.isoformat(),
            "model": self.model.value,
            "metadata": self.metadata
        }


@dataclass
class VegaHedgeRecommendation:
    """Recommandation de hedging Vega."""
    recommendation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    position_id: str = ""
    action: str = ""  # buy, sell, hold, adjust
    quantity: float = 0.0
    option_type: OptionType = OptionType.CALL
    strike: float = 0.0
    expiry: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))
    vega_hedge: float = 0.0
    delta_hedge: float = 0.0
    cost_estimate: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: int = 1


# ============== INTERFACES ==============

class VegaEngineInterface(ABC):
    """Interface abstraite pour le moteur Vega."""
    
    @abstractmethod
    async def calculate_greeks(self, option: OptionContract) -> OptionGreeks:
        """Calcule les grecques d'une option."""
        pass
    
    @abstractmethod
    async def build_volatility_surface(self, symbol: str, options: List[OptionContract]) -> VolatilitySurface:
        """Construit une surface de volatilité."""
        pass
    
    @abstractmethod
    async def hedge_vega(self, position: VegaPosition) -> VegaHedgeRecommendation:
        """Génère une recommandation de hedging Vega."""
        pass


# ============== IMPLÉMENTATION ==============

class VegaEngine(VegaEngineInterface):
    """
    Moteur Vega avancé pour le Hedge Bot.
    Gère le calcul des grecques, l'analyse de volatilité, et le hedging des options.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Cache des grecques
        self._greeks_cache: Dict[str, OptionGreeks] = {}
        self._cache_lock = threading.RLock()
        
        # Surfaces de volatilité
        self._vol_surfaces: Dict[str, VolatilitySurface] = {}
        self._surf_lock = threading.RLock()
        
        # Positions Vega
        self._vega_positions: Dict[str, VegaPosition] = {}
        self._pos_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "greeks_calculated": 0,
            "surfaces_built": 0,
            "hedges_recommended": 0,
            "avg_vega_exposure": 0.0,
            "avg_delta_exposure": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("VegaEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "cache_size": 1000,
            "cache_ttl": 3600,  # 1 heure
            "enable_cache": True,
            "default_volatility": 0.2,
            "default_risk_free_rate": 0.02,
            "default_dividend_yield": 0.0,
            "greeks_tolerance": 1e-6,
            "max_iterations": 100,
            "volatility_surface_strikes": 10,
            "volatility_surface_expiries": 5,
            "hedge_threshold": 0.05,
            "min_vega_hedge": 0.01
        }
    
    async def start(self) -> None:
        """Démarre le moteur Vega."""
        logger.info("VegaEngine starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._surface_updater())
        
        logger.info("VegaEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur Vega."""
        logger.info("VegaEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("VegaEngine stopped")
    
    async def calculate_greeks(self, option: OptionContract) -> OptionGreeks:
        """Calcule les grecques d'une option."""
        start_time = time.time()
        self._stats["greeks_calculated"] += 1
        
        try:
            # Vérification du cache
            cache_key = self._compute_cache_key(option)
            if self.config["enable_cache"] and cache_key in self._greeks_cache:
                cached = self._greeks_cache[cache_key]
                age = (datetime.now(timezone.utc) - cached.timestamp).total_seconds()
                if age < self.config["cache_ttl"]:
                    logger.debug(f"Greeks cache hit: {cache_key}")
                    return cached
            
            # Calcul des grecques
            greeks = await self._compute_greeks(option)
            
            # Mise en cache
            if self.config["enable_cache"]:
                with self._cache_lock:
                    if len(self._greeks_cache) < self.config["cache_size"]:
                        self._greeks_cache[cache_key] = greeks
            
            # Stockage persistant
            if self.data_manager:
                await self.data_manager.store(
                    f"greeks:{greeks.greeks_id}",
                    greeks.to_dict(),
                    DataType.GREEKS
                )
            
            execution_time = time.time() - start_time
            logger.debug(f"Greeks calculated: {option.option_id} "
                        f"delta={greeks.delta:.4f} vega={greeks.vega:.4f} "
                        f"time={execution_time:.3f}s")
            
            return greeks
            
        except Exception as e:
            logger.error(f"Greeks calculation error: {e}")
            raise
    
    async def build_volatility_surface(
        self,
        symbol: str,
        options: List[OptionContract]
    ) -> VolatilitySurface:
        """Construit une surface de volatilité."""
        self._stats["surfaces_built"] += 1
        
        try:
            # Extraction des strikes et expiries
            strikes = sorted(set(o.strike for o in options))
            expiries = sorted(set(o.expiry for o in options))
            
            # Création de la grille de volatilités
            volatilities = []
            
            for expiry in expiries:
                exp_vols = []
                for strike in strikes:
                    # Trouver l'option correspondante
                    option = next(
                        (o for o in options if o.strike == strike and o.expiry == expiry),
                        None
                    )
                    if option:
                        exp_vols.append(option.implied_volatility)
                    else:
                        # Interpolation
                        exp_vols.append(self._interpolate_volatility(options, strike, expiry))
                volatilities.append(exp_vols)
            
            # Création de la surface
            surface = VolatilitySurface(
                symbol=symbol,
                strikes=strikes,
                expiries=expiries,
                volatilities=volatilities,
                risk_free_rate=self.config["default_risk_free_rate"],
                spot_price=options[0].underlying_price if options else 0,
                model=VolatilityModel.SABR,
                metadata={
                    "num_strikes": len(strikes),
                    "num_expiries": len(expiries),
                    "interpolation_method": "linear"
                }
            )
            
            # Stockage
            with self._surf_lock:
                self._vol_surfaces[symbol] = surface
            
            if self.data_manager:
                await self.data_manager.store(
                    f"vol_surface:{surface.surface_id}",
                    surface.to_dict(),
                    DataType.VOLATILITY
                )
            
            logger.info(f"Volatility surface built: {symbol} "
                       f"strikes={len(strikes)} expiries={len(expiries)}")
            
            return surface
            
        except Exception as e:
            logger.error(f"Volatility surface build error: {e}")
            raise
    
    async def hedge_vega(self, position: VegaPosition) -> VegaHedgeRecommendation:
        """Génère une recommandation de hedging Vega."""
        self._stats["hedges_recommended"] += 1
        
        try:
            # Analyse de l'exposition Vega
            vega_exposure = position.vega_exposure
            delta_exposure = position.delta_exposure
            
            # Détermination de l'action
            action = "hold"
            quantity = 0.0
            option_type = OptionType.CALL
            strike = position.underlying_price
            
            if abs(vega_exposure) > self.config["hedge_threshold"]:
                if vega_exposure > 0:
                    # Vega positif -> vendre des options
                    action = "sell"
                    option_type = OptionType.CALL
                    quantity = abs(vega_exposure) / (position.implied_volatility + 0.01)
                else:
                    # Vega négatif -> acheter des options
                    action = "buy"
                    option_type = OptionType.PUT
                    quantity = abs(vega_exposure) / (position.implied_volatility + 0.01)
                
                # Ajustement pour le delta
                if abs(delta_exposure) > 0.1:
                    # Hedging delta supplémentaire
                    quantity *= 1 + abs(delta_exposure)
            
            # Calcul du coût estimé
            cost_estimate = quantity * position.underlying_price * 0.02
            
            # Calcul de la confiance
            confidence = min(0.95, 0.5 + 0.3 * (1 - abs(vega_exposure) / 10))
            
            # Création de la recommandation
            recommendation = VegaHedgeRecommendation(
                position_id=position.position_id,
                action=action,
                quantity=quantity,
                option_type=option_type,
                strike=strike,
                expiry=datetime.now(timezone.utc) + timedelta(days=30),
                vega_hedge=vega_exposure,
                delta_hedge=delta_exposure,
                cost_estimate=cost_estimate,
                confidence=confidence,
                reason=f"{action} {quantity:.2f} {option_type.value} options to hedge vega exposure of {vega_exposure:.4f}",
                priority=1 if abs(vega_exposure) > 0.1 else 2
            )
            
            # Mise à jour de la position
            position.hedged = action != "hold"
            position.hedge_ratio = quantity / (position.vega_exposure + 0.01)
            position.hedge_cost = cost_estimate
            
            logger.info(f"Hedge recommendation: {position.position_id} "
                       f"action={action} quantity={quantity:.2f} "
                       f"vega={vega_exposure:.4f}")
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Hedge recommendation error: {e}")
            raise
    
    # ========== MÉTHODES PRIVÉES - CALCUL DES GRECQUES ==========
    
    async def _compute_greeks(self, option: OptionContract) -> OptionGreeks:
        """Calcule les grecques avec Black-Scholes."""
        # Paramètres
        S = option.underlying_price
        K = option.strike
        T = max((option.expiry - datetime.now(timezone.utc)).total_seconds() / (365.25 * 24 * 3600), 0.001)
        r = option.risk_free_rate
        q = option.dividend_yield
        sigma = option.implied_volatility
        
        # Black-Scholes
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        # Distribution normale
        nd1 = norm.cdf(d1)
        nd2 = norm.cdf(d2)
        pdf_d1 = norm.pdf(d1)
        
        # Calcul des grecques
        if option.option_type == OptionType.CALL:
            # Call
            delta = math.exp(-q * T) * nd1
            theta = (-S * math.exp(-q * T) * pdf_d1 * sigma / (2 * math.sqrt(T))
                    - r * K * math.exp(-r * T) * nd2
                    + q * S * math.exp(-q * T) * nd1)
            rho = K * T * math.exp(-r * T) * nd2 / 100
        else:
            # Put
            delta = -math.exp(-q * T) * (1 - nd1)
            theta = (-S * math.exp(-q * T) * pdf_d1 * sigma / (2 * math.sqrt(T))
                    + r * K * math.exp(-r * T) * (1 - nd2)
                    - q * S * math.exp(-q * T) * (1 - nd1))
            rho = -K * T * math.exp(-r * T) * (1 - nd2) / 100
        
        # Gamma (identique pour call et put)
        gamma = math.exp(-q * T) * pdf_d1 / (S * sigma * math.sqrt(T))
        
        # Vega (identique pour call et put)
        vega = S * math.exp(-q * T) * pdf_d1 * math.sqrt(T) / 100
        
        # Grecques de second ordre
        # Vanna = ∂Vega/∂Spot
        vanna = -math.exp(-q * T) * pdf_d1 * (d2 / sigma) / 100
        
        # Volga = ∂Vega/∂Volatility (Vomma)
        volga = S * math.exp(-q * T) * pdf_d1 * math.sqrt(T) * (d1 * d2) / 10000
        
        # Charm = ∂Delta/∂Time
        charm = -math.exp(-q * T) * pdf_d1 * (
            (2 * (r - q) * T - d2 * sigma * math.sqrt(T)) / (2 * T * sigma * math.sqrt(T))
        )
        
        # Veta = ∂Vega/∂Time
        veta = -S * math.exp(-q * T) * pdf_d1 * math.sqrt(T) * (
            (r - q) * T / (sigma * T) - d1 / (2 * T) - (r - q) / sigma
        ) / 100
        
        # Speed = ∂Gamma/∂Spot
        speed = -math.exp(-q * T) * pdf_d1 * (d1 / (sigma * T) + 1) / (S * S * sigma * math.sqrt(T))
        
        # Zomma = ∂Gamma/∂Volatility
        zomma = math.exp(-q * T) * pdf_d1 * (d1 * d2 - 1) / (S * sigma * sigma * math.sqrt(T))
        
        # Color = ∂Gamma/∂Time
        color = -math.exp(-q * T) * pdf_d1 / (2 * S * sigma * math.sqrt(T)) * (
            1 + (2 * (r - q) * T - d2 * sigma * math.sqrt(T)) / (T * sigma * math.sqrt(T))
        )
        
        # Ultima = ∂Volga/∂Volatility
        ultima = -S * math.exp(-q * T) * pdf_d1 * math.sqrt(T) * (
            d1 * d2 * (1 - d1 * d2) + d1 * d1 + d2 * d2
        ) / 10000
        
        return OptionGreeks(
            option_id=option.option_id,
            delta=delta,
            gamma=gamma,
            vega=vega,
            theta=theta,
            rho=rho,
            vanna=vanna,
            volga=volga,
            charm=charm,
            veta=veta,
            speed=speed,
            zomma=zomma,
            color=color,
            ultima=ultima,
            implied_volatility=sigma,
            historical_volatility=sigma * 0.9,  # Simulé
            model=VolatilityModel.BLACK_SCHOLES
        )
    
    # ========== MÉTHODES PRIVÉES - VOLATILITÉ ==========
    
    def _interpolate_volatility(
        self,
        options: List[OptionContract],
        strike: float,
        expiry: datetime
    ) -> float:
        """Interpole la volatilité pour un strike et expiry donnés."""
        # Volatilité par défaut
        default_vol = self.config["default_volatility"]
        
        # Filtrage des options proches
        close_strikes = [o for o in options if abs(o.strike - strike) < 0.1 * strike]
        if not close_strikes:
            return default_vol
        
        # Interpolation linéaire
        vols = [o.implied_volatility for o in close_strikes]
        return sum(vols) / len(vols)
    
    async def _surface_updater(self) -> None:
        """Met à jour les surfaces de volatilité."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                # Mise à jour des surfaces existantes
                with self._surf_lock:
                    for symbol, surface in self._vol_surfaces.items():
                        # Simulation de mise à jour
                        # Dans un système réel, on récupérerait les données de marché
                        surface.timestamp = datetime.now(timezone.utc)
                
            except Exception as e:
                logger.error(f"Surface updater error: {e}")
    
    # ========== MÉTHODES PRIVÉES - CACHE ==========
    
    def _compute_cache_key(self, option: OptionContract) -> str:
        """Calcule une clé de cache pour les grecques."""
        key_data = {
            "symbol": option.symbol,
            "strike": option.strike,
            "expiry": option.expiry.isoformat(),
            "type": option.option_type.value,
            "price": option.underlying_price,
            "vol": option.implied_volatility,
            "rate": option.risk_free_rate
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                with self._cache_lock:
                    if len(self._greeks_cache) > self.config["cache_size"]:
                        keys = sorted(self._greeks_cache.keys())
                        for key in keys[:len(self._greeks_cache) - self.config["cache_size"]]:
                            del self._greeks_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_greeks(self, option_id: str) -> Optional[OptionGreeks]:
        """Récupère les grecques d'une option."""
        with self._cache_lock:
            for greeks in self._greeks_cache.values():
                if greeks.option_id == option_id:
                    return greeks
        
        if self.data_manager:
            data = await self.data_manager.retrieve(
                f"greeks:{option_id}",
                DataType.GREEKS
            )
            if data:
                return self._deserialize_greeks(data)
        
        return None
    
    async def get_volatility_surface(self, symbol: str) -> Optional[VolatilitySurface]:
        """Récupère la surface de volatilité d'un symbole."""
        with self._surf_lock:
            return self._vol_surfaces.get(symbol)
    
    async def get_vega_position(self, position_id: str) -> Optional[VegaPosition]:
        """Récupère une position Vega."""
        with self._pos_lock:
            return self._vega_positions.get(position_id)
    
    async def create_vega_position(
        self,
        option_id: str,
        quantity: float,
        underlying_price: float,
        implied_volatility: float
    ) -> VegaPosition:
        """Crée une position Vega."""
        # Calcul des grecques
        option = await self.get_option(option_id)
        if not option:
            raise ValueError(f"Option {option_id} not found")
        
        greeks = await self.calculate_greeks(option)
        
        position = VegaPosition(
            option_id=option_id,
            quantity=quantity,
            vega_exposure=greeks.vega * quantity,
            delta_exposure=greeks.delta * quantity,
            gamma_exposure=greeks.gamma * quantity,
            theta_exposure=greeks.theta * quantity,
            underlying_price=underlying_price,
            implied_volatility=implied_volatility,
            hedged=False
        )
        
        with self._pos_lock:
            self._vega_positions[position.position_id] = position
        
        # Mise à jour des statistiques
        total_vega = sum(p.vega_exposure for p in self._vega_positions.values())
        total_delta = sum(p.delta_exposure for p in self._vega_positions.values())
        count = len(self._vega_positions)
        
        self._stats["avg_vega_exposure"] = total_vega / count if count > 0 else 0
        self._stats["avg_delta_exposure"] = total_delta / count if count > 0 else 0
        
        logger.info(f"Vega position created: {position.position_id} "
                   f"vega={position.vega_exposure:.4f} delta={position.delta_exposure:.4f}")
        
        return position
    
    async def get_option(self, option_id: str) -> Optional[OptionContract]:
        """Récupère un contrat d'option."""
        if self.data_manager:
            data = await self.data_manager.retrieve(
                f"option:{option_id}",
                DataType.OPTION
            )
            if data:
                return self._deserialize_option(data)
        return None
    
    def _deserialize_greeks(self, data: Dict) -> OptionGreeks:
        """Désérialise les grecques."""
        try:
            return OptionGreeks(
                greeks_id=data.get("greeks_id", str(uuid.uuid4())),
                option_id=data.get("option_id", ""),
                delta=data.get("delta", 0.0),
                gamma=data.get("gamma", 0.0),
                vega=data.get("vega", 0.0),
                theta=data.get("theta", 0.0),
                rho=data.get("rho", 0.0),
                vanna=data.get("vanna", 0.0),
                volga=data.get("volga", 0.0),
                charm=data.get("charm", 0.0),
                veta=data.get("veta", 0.0),
                speed=data.get("speed", 0.0),
                zomma=data.get("zomma", 0.0),
                color=data.get("color", 0.0),
                ultima=data.get("ultima", 0.0),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                implied_volatility=data.get("implied_volatility", 0.0),
                historical_volatility=data.get("historical_volatility", 0.0),
                model=VolatilityModel(data.get("model", "black_scholes")),
                metadata=data.get("metadata", {})
            )
        except Exception as e:
            logger.error(f"Error deserializing greeks: {e}")
            return None
    
    def _deserialize_option(self, data: Dict) -> Optional[OptionContract]:
        """Désérialise un contrat d'option."""
        try:
            return OptionContract(
                option_id=data.get("option_id", str(uuid.uuid4())),
                symbol=data.get("symbol", ""),
                option_type=OptionType(data.get("option_type", "call")),
                strike=data.get("strike", 0.0),
                expiry=datetime.fromisoformat(data.get("expiry", datetime.now(timezone.utc).isoformat())),
                underlying_price=data.get("underlying_price", 0.0),
                implied_volatility=data.get("implied_volatility", 0.2),
                risk_free_rate=data.get("risk_free_rate", 0.02),
                dividend_yield=data.get("dividend_yield", 0.0),
                style=OptionStyle(data.get("style", "european")),
                volume=data.get("volume", 0),
                open_interest=data.get("open_interest", 0),
                bid_price=data.get("bid_price", 0.0),
                ask_price=data.get("ask_price", 0.0),
                last_price=data.get("last_price", 0.0),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing option: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._cache_lock:
            self._stats["cache_size"] = len(self._greeks_cache)
        with self._surf_lock:
            self._stats["surfaces_count"] = len(self._vol_surfaces)
        with self._pos_lock:
            self._stats["positions_count"] = len(self._vega_positions)
        
        return self._stats.copy()


# ============== VOLATILITY MODELS ==============

class VolatilityModels:
    """
    Collection de modèles de volatilité avancés.
    Implémente différents modèles pour l'estimation et la prévision de la volatilité.
    """
    
    @staticmethod
    def black_scholes_implied_vol(
        price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: OptionType
    ) -> float:
        """
        Calcule la volatilité implicite Black-Scholes par méthode de Brent.
        """
        if T <= 0:
            return 0.0
        
        def objective(sigma: float) -> float:
            if sigma <= 0:
                return 1e6
            
            d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            
            if option_type == OptionType.CALL:
                model_price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
            else:
                model_price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            
            return model_price - price
        
        try:
            # Recherche dans [0.001, 5.0]
            iv = brentq(objective, 0.001, 5.0, maxiter=100)
            return iv
        except:
            return 0.2  # Volatilité par défaut
    
    @staticmethod
    def heston_parameters(
        S: float,
        V0: float,
        kappa: float,
        theta: float,
        sigma: float,
        rho: float,
        T: float
    ) -> Dict[str, float]:
        """Paramètres du modèle Heston."""
        return {
            "S0": S,
            "V0": V0,
            "kappa": kappa,
            "theta": theta,
            "sigma": sigma,
            "rho": rho,
            "T": T
        }
    
    @staticmethod
    def sabr_parameters(
        F: float,
        alpha: float,
        beta: float,
        rho: float,
        nu: float,
        T: float
    ) -> Dict[str, float]:
        """Paramètres du modèle SABR."""
        return {
            "F": F,
            "alpha": alpha,
            "beta": beta,
            "rho": rho,
            "nu": nu,
            "T": T
        }


# ============== FACTORY ==============

class VegaFactory:
    """Factory pour créer des composants Vega."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> VegaEngine:
        """Crée un moteur Vega."""
        engine = VegaEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_option(
        symbol: str,
        option_type: OptionType,
        strike: float,
        expiry: datetime,
        **kwargs
    ) -> OptionContract:
        """Crée un contrat d'option."""
        return OptionContract(
            symbol=symbol,
            option_type=option_type,
            strike=strike,
            expiry=expiry,
            **kwargs
        )


# ============== EXPORT ==============

__all__ = [
    "OptionType",
    "OptionStyle",
    "VolatilityModel",
    "GreeksType",
    "OptionContract",
    "OptionGreeks",
    "VegaPosition",
    "VolatilitySurface",
    "VegaHedgeRecommendation",
    "VegaEngineInterface",
    "VegaEngine",
    "VolatilityModels",
    "VegaFactory"
]
