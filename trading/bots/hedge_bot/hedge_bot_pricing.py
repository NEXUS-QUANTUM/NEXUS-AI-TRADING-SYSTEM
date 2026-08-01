# trading/bots/hedge_bot/hedge_bot_pricing.py
# Advanced Pricing & Valuation Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Pricing Module - Module avancé de pricing et de valorisation pour le Hedge Bot.
Gère l'évaluation des actifs, le pricing des options, les modèles de valorisation,
les courbes de rendement et l'analyse de sensibilité pour les stratégies de hedging.
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
from scipy.optimize import minimize, brentq
import matplotlib.pyplot as plt
import seaborn as sns

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_pricing")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)


# ============== ENUMS & TYPES ==============

class PricingModel(Enum):
    """Modèles de pricing."""
    BLACK_SCHOLES = "black_scholes"
    BINOMIAL = "binomial"
    MONTE_CARLO = "monte_carlo"
    HESTON = "heston"
    SABR = "sabr"
    LOCAL_VOL = "local_vol"
    STOCHASTIC_VOL = "stochastic_vol"
    JUMP_DIFFUSION = "jump_diffusion"
    VIX = "vix"
    GARCH = "garch"


class OptionType(Enum):
    """Types d'options."""
    CALL = "call"
    PUT = "put"
    EUROPEAN = "european"
    AMERICAN = "american"
    EXOTIC = "exotic"
    DIGITAL = "digital"
    BARRIER = "barrier"
    ASIAN = "asian"
    BINARY = "binary"


class VolatilitySurfaceType(Enum):
    """Types de surfaces de volatilité."""
    IMPLIED = "implied"
    HISTORICAL = "historical"
    FORWARD = "forward"
    TERM_STRUCTURE = "term_structure"
    SMILE = "smile"


# ============== DATA MODELS ==============

@dataclass
class PricingParameters:
    """Paramètres de pricing."""
    params_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model: PricingModel = PricingModel.BLACK_SCHOLES
    spot_price: float = 0.0
    strike_price: float = 0.0
    time_to_maturity: float = 0.0
    risk_free_rate: float = 0.02
    dividend_yield: float = 0.0
    volatility: float = 0.2
    option_type: OptionType = OptionType.CALL
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class PricingResult:
    """Résultat de pricing."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    params_id: str = ""
    price: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    rho: float = 0.0
    implied_vol: float = 0.0
    model: PricingModel = PricingModel.BLACK_SCHOLES
    iterations: int = 0
    convergence: float = 0.0
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class VolatilitySurface:
    """Surface de volatilité."""
    surface_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    surface_type: VolatilitySurfaceType = VolatilitySurfaceType.IMPLIED
    strikes: List[float] = field(default_factory=list)
    expiries: List[datetime] = field(default_factory=list)
    volatilities: np.ndarray = field(default_factory=lambda: np.array([]))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class YieldCurve:
    """Courbe de rendement."""
    curve_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    tenors: List[float] = field(default_factory=list)
    rates: List[float] = field(default_factory=list)
    curve_type: str = "zero_coupon"
    interpolated: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============== INTERFACES ==============

class PricingEngineInterface(ABC):
    """Interface abstraite pour le moteur de pricing."""
    
    @abstractmethod
    async def price(self, params: PricingParameters) -> PricingResult:
        """Évalue un instrument."""
        pass
    
    @abstractmethod
    async def calculate_implied_vol(self, price: float, params: PricingParameters) -> float:
        """Calcule la volatilité implicite."""
        pass
    
    @abstractmethod
    async def build_volatility_surface(self, symbol: str) -> VolatilitySurface:
        """Construit une surface de volatilité."""
        pass


# ============== IMPLÉMENTATION ==============

class PricingEngine(PricingEngineInterface):
    """
    Moteur de pricing avancé pour le Hedge Bot.
    Gère l'évaluation des actifs et le pricing des options.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des paramètres
        self._params: Dict[str, PricingParameters] = {}
        self._params_lock = threading.RLock()
        
        # Gestion des résultats
        self._results: Dict[str, PricingResult] = {}
        self._results_lock = threading.RLock()
        
        # Gestion des surfaces
        self._surfaces: Dict[str, VolatilitySurface] = {}
        self._surf_lock = threading.RLock()
        
        # Gestion des courbes de rendement
        self._curves: Dict[str, YieldCurve] = {}
        self._curve_lock = threading.RLock()
        
        # Cache des calculs
        self._calc_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "pricings_performed": 0,
            "implied_vol_calculations": 0,
            "surfaces_built": 0,
            "avg_pricing_time_ms": 0.0,
            "avg_iv_time_ms": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("PricingEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_model": PricingModel.BLACK_SCHOLES,
            "default_volatility": 0.2,
            "default_risk_free": 0.02,
            "implied_vol_tolerance": 1e-6,
            "max_iterations": 100,
            "monte_carlo_paths": 10000,
            "binomial_steps": 100,
            "surface_interpolation": "cubic",
            "cache_size": 1000,
            "enable_cache": True,
            "parallel_pricing": True,
            "accuracy_threshold": 0.001
        }
    
    async def start(self) -> None:
        """Démarre le moteur de pricing."""
        logger.info("PricingEngine starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("PricingEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de pricing."""
        logger.info("PricingEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("PricingEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def price(self, params: PricingParameters) -> PricingResult:
        """Évalue un instrument."""
        start_time = time.time()
        self._stats["pricings_performed"] += 1
        
        # Vérification du cache
        cache_key = self._compute_cache_key(params)
        if self.config["enable_cache"] and cache_key in self._calc_cache:
            return self._calc_cache[cache_key]
        
        try:
            # Sélection du modèle
            if params.model == PricingModel.BLACK_SCHOLES:
                result = await self._black_scholes_price(params)
            elif params.model == PricingModel.BINOMIAL:
                result = await self._binomial_price(params)
            elif params.model == PricingModel.MONTE_CARLO:
                result = await self._monte_carlo_price(params)
            elif params.model == PricingModel.HESTON:
                result = await self._heston_price(params)
            elif params.model == PricingModel.SABR:
                result = await self._sabr_price(params)
            else:
                result = await self._black_scholes_price(params)
            
            # Calcul des grecques
            await self._calculate_greeks(result, params)
            
            # Métadonnées
            result.model = params.model
            result.execution_time_ms = (time.time() - start_time) * 1000
            
            # Mise en cache
            if self.config["enable_cache"]:
                with self._cache_lock:
                    if len(self._calc_cache) < self.config["cache_size"]:
                        self._calc_cache[cache_key] = result
            
            # Mise à jour des statistiques
            self._stats["avg_pricing_time_ms"] = (
                self._stats["avg_pricing_time_ms"] * 0.9 + result.execution_time_ms * 0.1
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Pricing error: {e}")
            raise
    
    async def calculate_implied_vol(self, price: float, params: PricingParameters) -> float:
        """Calcule la volatilité implicite."""
        start_time = time.time()
        self._stats["implied_vol_calculations"] += 1
        
        try:
            def objective(sigma):
                params.volatility = sigma
                result = await self.price(params)
                return result.price - price
            
            # Recherche de la volatilité implicite
            implied_vol = brentq(
                objective,
                0.001,
                5.0,
                maxiter=self.config["max_iterations"]
            )
            
            self._stats["avg_iv_time_ms"] = (
                self._stats["avg_iv_time_ms"] * 0.9 +
                (time.time() - start_time) * 1000 * 0.1
            )
            
            return implied_vol
            
        except Exception as e:
            logger.error(f"Implied vol error: {e}")
            return params.volatility
    
    async def build_volatility_surface(self, symbol: str) -> VolatilitySurface:
        """Construit une surface de volatilité."""
        self._stats["surfaces_built"] += 1
        
        try:
            # Récupération des données
            if not self.data_manager:
                raise ValueError("Data manager not available")
            
            # Dans un système réel, on récupérerait les options
            strikes = np.linspace(50, 150, 10)
            expiries = [datetime.now(timezone.utc) + timedelta(days=d) for d in [30, 60, 90, 180, 365]]
            
            # Construction de la surface
            volatilities = np.zeros((len(expiries), len(strikes)))
            for i, expiry in enumerate(expiries):
                for j, strike in enumerate(strikes):
                    volatilities[i, j] = 0.2 + 0.1 * np.random.randn()
            
            surface = VolatilitySurface(
                symbol=symbol,
                surface_type=VolatilitySurfaceType.IMPLIED,
                strikes=strikes.tolist(),
                expiries=expiries,
                volatilities=volatilities,
                metadata={"interpolation": self.config["surface_interpolation"]}
            )
            
            with self._surf_lock:
                self._surfaces[surface.surface_id] = surface
            
            logger.info(f"Volatility surface built for {symbol}")
            return surface
            
        except Exception as e:
            logger.error(f"Volatility surface error: {e}")
            raise
    
    # ========== MÉTHODES PRIVÉES - PRICING ==========
    
    async def _black_scholes_price(self, params: PricingParameters) -> PricingResult:
        """Black-Scholes pricing."""
        S = params.spot_price
        K = params.strike_price
        T = params.time_to_maturity
        r = params.risk_free_rate
        q = params.dividend_yield
        sigma = params.volatility
        
        if T <= 0:
            d1 = 0
            d2 = 0
        else:
            d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
        
        if params.option_type == OptionType.CALL:
            price = S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)
        
        result = PricingResult(
            price=price,
            implied_vol=sigma,
            model=PricingModel.BLACK_SCHOLES
        )
        
        return result
    
    async def _binomial_price(self, params: PricingParameters) -> PricingResult:
        """Binomial tree pricing."""
        S = params.spot_price
        K = params.strike_price
        T = params.time_to_maturity
        r = params.risk_free_rate
        q = params.dividend_yield
        sigma = params.volatility
        n = self.config["binomial_steps"]
        
        dt = T / n
        u = math.exp(sigma * math.sqrt(dt))
        d = 1 / u
        p = (math.exp((r - q) * dt) - d) / (u - d)
        
        # Construction de l'arbre
        stock = np.zeros((n + 1, n + 1))
        option = np.zeros((n + 1, n + 1))
        
        for i in range(n + 1):
            stock[i, n] = S * (u ** (n - i)) * (d ** i)
            
            if params.option_type == OptionType.CALL:
                option[i, n] = max(stock[i, n] - K, 0)
            else:
                option[i, n] = max(K - stock[i, n], 0)
        
        for j in range(n - 1, -1, -1):
            for i in range(j + 1):
                stock[i, j] = S * (u ** (j - i)) * (d ** i)
                option[i, j] = math.exp(-r * dt) * (p * option[i, j + 1] + (1 - p) * option[i + 1, j + 1])
        
        price = option[0, 0]
        
        result = PricingResult(
            price=price,
            implied_vol=sigma,
            model=PricingModel.BINOMIAL,
            iterations=n
        )
        
        return result
    
    async def _monte_carlo_price(self, params: PricingParameters) -> PricingResult:
        """Monte Carlo pricing."""
        S = params.spot_price
        K = params.strike_price
        T = params.time_to_maturity
        r = params.risk_free_rate
        q = params.dividend_yield
        sigma = params.volatility
        n_paths = self.config["monte_carlo_paths"]
        
        # Simulation des prix
        dt = T / 252
        n_steps = int(T / dt) + 1
        
        # Génération des rendements
        returns = np.random.normal(
            (r - q - 0.5 * sigma**2) * dt,
            sigma * np.sqrt(dt),
            (n_paths, n_steps)
        )
        
        # Calcul des prix finaux
        log_returns = np.cumsum(returns, axis=1)
        final_prices = S * np.exp(log_returns[:, -1])
        
        # Payoffs
        if params.option_type == OptionType.CALL:
            payoffs = np.maximum(final_prices - K, 0)
        else:
            payoffs = np.maximum(K - final_prices, 0)
        
        price = np.exp(-r * T) * np.mean(payoffs)
        
        result = PricingResult(
            price=price,
            implied_vol=sigma,
            model=PricingModel.MONTE_CARLO,
            iterations=n_paths
        )
        
        return result
    
    async def _heston_price(self, params: PricingParameters) -> PricingResult:
        """Heston model pricing."""
        # Simulation simplifiée
        result = await self._black_scholes_price(params)
        result.model = PricingModel.HESTON
        return result
    
    async def _sabr_price(self, params: PricingParameters) -> PricingResult:
        """SABR model pricing."""
        result = await self._black_scholes_price(params)
        result.model = PricingModel.SABR
        return result
    
    # ========== MÉTHODES PRIVÉES - GREQUES ==========
    
    async def _calculate_greeks(self, result: PricingResult, params: PricingParameters) -> None:
        """Calcule les grecques par différences finies."""
        S = params.spot_price
        sigma = params.volatility
        T = params.time_to_maturity
        
        # Delta
        params.spot_price = S * 1.01
        up_price = await self.price(params)
        params.spot_price = S * 0.99
        down_price = await self.price(params)
        result.delta = (up_price.price - down_price.price) / (S * 0.02)
        
        # Gamma
        params.spot_price = S * 1.01
        up2_price = await self.price(params)
        params.spot_price = S * 0.99
        down2_price = await self.price(params)
        result.gamma = (up2_price.price - 2 * result.price + down2_price.price) / (S * 0.01)**2
        
        # Vega
        params.volatility = sigma * 1.01
        up_vol_price = await self.price(params)
        params.volatility = sigma * 0.99
        down_vol_price = await self.price(params)
        result.vega = (up_vol_price.price - down_vol_price.price) / (sigma * 0.02) / 100
        
        # Theta
        if T > 0:
            params.time_to_maturity = T + 0.01
            up_time_price = await self.price(params)
            params.time_to_maturity = T - 0.01
            down_time_price = await self.price(params)
            result.theta = -(up_time_price.price - down_time_price.price) / 0.02 / 365
        
        # Rho
        params.risk_free_rate = 0.021
        up_rate_price = await self.price(params)
        params.risk_free_rate = 0.019
        down_rate_price = await self.price(params)
        result.rho = (up_rate_price.price - down_rate_price.price) / 0.002 / 100
        
        # Restaurer les paramètres
        params.spot_price = S
        params.volatility = sigma
        params.time_to_maturity = T
        params.risk_free_rate = 0.02
    
    # ========== MÉTHODES PRIVÉES - CACHE ==========
    
    def _compute_cache_key(self, params: PricingParameters) -> str:
        """Calcule une clé de cache."""
        key_data = {
            "model": params.model.value,
            "spot": params.spot_price,
            "strike": params.strike_price,
            "time": params.time_to_maturity,
            "rate": params.risk_free_rate,
            "vol": params.volatility,
            "type": params.option_type.value
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._calc_cache) > self.config["cache_size"]:
                        keys = list(self._calc_cache.keys())
                        for key in keys[:len(self._calc_cache) - self.config["cache_size"]]:
                            del self._calc_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._params_lock:
                    self._stats["total_params"] = len(self._params)
                with self._results_lock:
                    self._stats["total_results"] = len(self._results)
                with self._surf_lock:
                    self._stats["total_surfaces"] = len(self._surfaces)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "pricing:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_params(self, params_id: str) -> Optional[PricingParameters]:
        """Récupère des paramètres."""
        with self._params_lock:
            return self._params.get(params_id)
    
    async def get_result(self, result_id: str) -> Optional[PricingResult]:
        """Récupère un résultat."""
        with self._results_lock:
            return self._results.get(result_id)
    
    async def get_surface(self, surface_id: str) -> Optional[VolatilitySurface]:
        """Récupère une surface."""
        with self._surf_lock:
            return self._surfaces.get(surface_id)
    
    async def get_curve(self, curve_id: str) -> Optional[YieldCurve]:
        """Récupère une courbe de rendement."""
        with self._curve_lock:
            return self._curves.get(curve_id)
    
    async def create_yield_curve(self, curve: YieldCurve) -> str:
        """Crée une courbe de rendement."""
        # Interpolation
        if curve.interpolated:
            curve.rates = await self._interpolate_curve(curve)
        
        with self._curve_lock:
            self._curves[curve.curve_id] = curve
        
        logger.info(f"Yield curve created: {curve.name}")
        return curve.curve_id
    
    async def _interpolate_curve(self, curve: YieldCurve) -> List[float]:
        """Interpole une courbe de rendement."""
        # Interpolation cubique
        from scipy.interpolate import CubicSpline
        if len(curve.tenors) < 2:
            return curve.rates
        
        cs = CubicSpline(curve.tenors, curve.rates)
        return cs(curve.tenors).tolist()
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._params_lock:
            self._stats["total_params"] = len(self._params)
        with self._results_lock:
            self._stats["total_results"] = len(self._results)
        
        return self._stats.copy()


# ============== OPTION PRICING VISUALIZER ==============

class OptionPricingVisualizer:
    """
    Visualiseur de pricing d'options.
    Génère des visualisations pour l'analyse de pricing.
    """
    
    def __init__(self, engine: PricingEngine):
        self.engine = engine
    
    async def plot_volatility_surface(self, surface: VolatilitySurface) -> str:
        """Génère un graphique de surface de volatilité."""
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        # Création de la grille
        X, Y = np.meshgrid(surface.strikes, range(len(surface.expiries)))
        Z = surface.volatilities
        
        # Graphique
        surf = ax.plot_surface(X, Y, Z, cmap='viridis', alpha=0.8)
        
        ax.set_xlabel('Strike Price')
        ax.set_ylabel('Expiry Index')
        ax.set_zlabel('Implied Volatility')
        ax.set_title(f'Volatility Surface - {surface.symbol}')
        
        plt.colorbar(surf)
        plt.tight_layout()
        
        # Sauvegarde
        path = f"vol_surface_{surface.symbol}_{int(time.time())}.png"
        plt.savefig(path, dpi=100)
        plt.close()
        
        return path
    
    async def plot_greeks(self, result: PricingResult) -> str:
        """Génère un graphique des grecques."""
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        
        greeks = [
            ('Delta', result.delta),
            ('Gamma', result.gamma),
            ('Vega', result.vega),
            ('Theta', result.theta),
            ('Rho', result.rho)
        ]
        
        for i, (name, value) in enumerate(greeks):
            row = i // 3
            col = i % 3
            axes[row, col].bar(name, value, color='steelblue')
            axes[row, col].set_title(name)
            axes[row, col].set_ylabel('Value')
        
        axes[1, 2].axis('off')
        plt.suptitle('Option Greeks')
        plt.tight_layout()
        
        path = f"greeks_{int(time.time())}.png"
        plt.savefig(path, dpi=100)
        plt.close()
        
        return path


# ============== FACTORY ==============

class PricingFactory:
    """Factory pour créer des composants de pricing."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PricingEngine:
        """Crée un moteur de pricing."""
        engine = PricingEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_visualizer(engine: PricingEngine) -> OptionPricingVisualizer:
        """Crée un visualiseur de pricing."""
        return OptionPricingVisualizer(engine)


# ============== EXPORT ==============

__all__ = [
    "PricingModel",
    "OptionType",
    "VolatilitySurfaceType",
    "PricingParameters",
    "PricingResult",
    "VolatilitySurface",
    "YieldCurve",
    "PricingEngineInterface",
    "PricingEngine",
    "OptionPricingVisualizer",
    "PricingFactory"
]
