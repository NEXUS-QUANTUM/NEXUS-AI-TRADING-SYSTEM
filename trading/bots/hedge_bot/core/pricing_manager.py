"""
NEXUS AI TRADING SYSTEM - Hedge Bot Pricing Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Gestionnaire de prix pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import math
import threading
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from scipy.optimize import minimize_scalar

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class PricingModel(Enum):
    """Modèles de pricing"""
    BLACK_SCHOLES = "black_scholes"
    BINOMIAL = "binomial"
    MONTE_CARLO = "monte_carlo"
    HESTON = "heston"
    SABR = "sabr"
    LOCAL_VOL = "local_vol"
    STOCHASTIC = "stochastic"

class PricingType(Enum):
    """Types de pricing"""
    SPOT = "spot"
    FUTURES = "futures"
    OPTIONS = "options"
    SWAPS = "swaps"
    FORWARDS = "forwards"
    BONDS = "bonds"

class VolatilityModel(Enum):
    """Modèles de volatilité"""
    CONSTANT = "constant"
    HESTON = "heston"
    SABR = "sabr"
    GARCH = "garch"
    EWMA = "ewma"
    STOCHASTIC = "stochastic"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class PricingInput:
    """Entrées de pricing"""
    spot_price: float
    strike_price: Optional[float] = None
    volatility: Optional[float] = None
    risk_free_rate: float = 0.02
    time_to_expiry: float = 1.0
    dividend_yield: float = 0.0
    pricing_type: PricingType = PricingType.SPOT
    model: PricingModel = PricingModel.BLACK_SCHOLES
    volatility_model: VolatilityModel = VolatilityModel.CONSTANT
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PricingOutput:
    """Sorties de pricing"""
    price: float
    implied_volatility: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    probability: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class YieldCurve:
    """Courbe de rendement"""
    rates: Dict[float, float]  # term -> rate
    interpolation: str = "linear"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class VolatilitySurface:
    """Surface de volatilité"""
    strikes: List[float]
    expiries: List[float]
    volatilities: np.ndarray
    interpolation: str = "cubic"
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# PRICING MANAGER
# ============================================================

class PricingManager:
    """
    Gestionnaire de prix pour le bot de couverture
    
    Implémente différents modèles de pricing et de volatilité
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        update_interval: int = 60,
        enable_monitoring: bool = True
    ):
        """
        Initialise le gestionnaire de prix
        
        Args:
            config: Configuration
            update_interval: Intervalle de mise à jour
            enable_monitoring: Activer le monitoring
        """
        self.config = config or {}
        self.update_interval = update_interval
        self.enable_monitoring = enable_monitoring
        
        # Prix
        self.prices: Dict[str, PricingOutput] = {}
        self.price_history: Dict[str, List[PricingOutput]] = defaultdict(list)
        
        # Courbes de rendement
        self.yield_curves: Dict[str, YieldCurve] = {}
        
        # Surfaces de volatilité
        self.volatility_surfaces: Dict[str, VolatilitySurface] = {}
        
        # Cache
        self._cache: Dict[str, PricingOutput] = {}
        self._cache_ttl: int = 60  # 1 minute
        
        # Statistiques
        self.stats = {
            'total_pricings': 0,
            'avg_price': 0.0,
            'avg_implied_vol': 0.0,
            'by_model': {},
            'by_type': {},
            'errors': 0,
        }
        
        # Verrous
        self._lock = threading.RLock()
        self._running = False
        self._update_task = None
        
        logger.info("PricingManager initialized")
    
    # ============================================================
    # PRICING METHODS
    # ============================================================
    
    def price(self, inputs: PricingInput) -> PricingOutput:
        """
        Calcule le prix d'un instrument
        
        Args:
            inputs: Entrées de pricing
            
        Returns:
            PricingOutput: Sorties de pricing
        """
        start_time = time.time()
        
        with self._lock:
            # Vérifier le cache
            cache_key = self._generate_cache_key(inputs)
            if cache_key in self._cache:
                return self._cache[cache_key]
            
            # Appliquer le modèle
            if inputs.model == PricingModel.BLACK_SCHOLES:
                output = self._black_scholes(inputs)
            elif inputs.model == PricingModel.BINOMIAL:
                output = self._binomial(inputs)
            elif inputs.model == PricingModel.MONTE_CARLO:
                output = self._monte_carlo(inputs)
            elif inputs.model == PricingModel.HESTON:
                output = self._heston(inputs)
            elif inputs.model == PricingModel.SABR:
                output = self._sabr(inputs)
            else:
                output = self._black_scholes(inputs)
            
            # Ajouter les métadonnées
            output.metadata['model'] = inputs.model.value
            output.metadata['pricing_type'] = inputs.pricing_type.value
            output.metadata['calculation_time'] = time.time() - start_time
            output.metadata['timestamp'] = datetime.now().isoformat()
            
            # Mettre en cache
            self._cache[cache_key] = output
            
            # Mettre à jour l'historique
            self.prices[f"{inputs.pricing_type.value}_{int(time.time())}"] = output
            self.price_history[inputs.pricing_type.value].append(output)
            
            # Mettre à jour les statistiques
            self._update_stats(output, inputs.model, inputs.pricing_type)
            
            return output
    
    def _black_scholes(self, inputs: PricingInput) -> PricingOutput:
        """
        Modèle Black-Scholes
        
        Args:
            inputs: Entrées de pricing
            
        Returns:
            PricingOutput: Sorties de pricing
        """
        S = inputs.spot_price
        K = inputs.strike_price or S
        sigma = inputs.volatility or 0.30
        r = inputs.risk_free_rate
        T = inputs.time_to_expiry
        q = inputs.dividend_yield
        
        if T <= 0:
            return PricingOutput(
                price=max(S - K, 0) if inputs.pricing_type == PricingType.OPTIONS else S,
                implied_volatility=sigma,
                delta=0,
                gamma=0,
                theta=0,
                vega=0,
                rho=0,
                probability=0.5
            )
        
        # Calculs de base
        from scipy.stats import norm
        import math
        
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        nd1 = norm.pdf(d1)
        nd2 = norm.pdf(d2)
        N_d1 = norm.cdf(d1)
        N_d2 = norm.cdf(d2)
        
        if inputs.pricing_type == PricingType.OPTIONS:
            # Prix d'une option call
            price = S * math.exp(-q * T) * N_d1 - K * math.exp(-r * T) * N_d2
            
            # Grecques
            delta = math.exp(-q * T) * N_d1
            gamma = math.exp(-q * T) * nd1 / (S * sigma * math.sqrt(T))
            theta = -(S * sigma * math.exp(-q * T) * nd1) / (2 * math.sqrt(T)) - \
                    r * K * math.exp(-r * T) * N_d2 + \
                    q * S * math.exp(-q * T) * N_d1
            vega = S * math.exp(-q * T) * nd1 * math.sqrt(T)
            rho = K * T * math.exp(-r * T) * N_d2
            
            # Probabilité
            probability = N_d2
        
        else:
            # Prix spot
            price = S * math.exp((r - q) * T)
            delta = 1
            gamma = 0
            theta = -S * math.exp((r - q) * T) * (r - q)
            vega = 0
            rho = 0
            probability = 0.5
        
        # Volatilité implicite
        implied_vol = self._implied_volatility(price, inputs)
        
        return PricingOutput(
            price=price,
            implied_volatility=implied_vol,
            delta=delta,
            gamma=gamma,
            theta=theta / 365,
            vega=vega / 100,
            rho=rho / 100,
            probability=probability
        )
    
    def _binomial(self, inputs: PricingInput, steps: int = 100) -> PricingOutput:
        """
        Modèle binomial pour options américaines
        
        Args:
            inputs: Entrées de pricing
            steps: Nombre de pas
            
        Returns:
            PricingOutput: Sorties de pricing
        """
        S = inputs.spot_price
        K = inputs.strike_price or S
        sigma = inputs.volatility or 0.30
        r = inputs.risk_free_rate
        T = inputs.time_to_expiry
        q = inputs.dividend_yield
        
        if T <= 0 or inputs.pricing_type != PricingType.OPTIONS:
            return self._black_scholes(inputs)
        
        dt = T / steps
        u = math.exp(sigma * math.sqrt(dt))
        d = 1 / u
        p = (math.exp((r - q) * dt) - d) / (u - d)
        
        # Prix à l'échéance
        prices = np.zeros(steps + 1)
        for i in range(steps + 1):
            prices[i] = S * (u ** (steps - i)) * (d ** i)
        
        # Valeurs à l'échéance
        values = np.maximum(prices - K, 0)
        
        # Backward induction
        for step in range(steps - 1, -1, -1):
            values = np.exp(-r * dt) * (p * values[:-1] + (1 - p) * values[1:])
            # Option américaine
            exercise = S * (u ** step) * (d ** (steps - step)) - K
            values = np.maximum(values, exercise)
        
        price = values[0]
        
        # Grecques approximatives
        eps = S * 0.001
        inputs_up = PricingInput(
            spot_price=S + eps,
            strike_price=K,
            volatility=sigma,
            risk_free_rate=r,
            time_to_expiry=T,
            dividend_yield=q,
            pricing_type=inputs.pricing_type,
            model=inputs.model
        )
        price_up = self._binomial(inputs_up, steps).price
        
        inputs_down = PricingInput(
            spot_price=S - eps,
            strike_price=K,
            volatility=sigma,
            risk_free_rate=r,
            time_to_expiry=T,
            dividend_yield=q,
            pricing_type=inputs.pricing_type,
            model=inputs.model
        )
        price_down = self._binomial(inputs_down, steps).price
        
        delta = (price_up - price_down) / (2 * eps)
        gamma = (price_up - 2 * price + price_down) / (eps ** 2)
        
        return PricingOutput(
            price=price,
            implied_volatility=sigma,
            delta=delta,
            gamma=gamma,
            theta=0,
            vega=0,
            rho=0,
            probability=0.5
        )
    
    def _monte_carlo(self, inputs: PricingInput, simulations: int = 10000) -> PricingOutput:
        """
        Simulation Monte Carlo
        
        Args:
            inputs: Entrées de pricing
            simulations: Nombre de simulations
            
        Returns:
            PricingOutput: Sorties de pricing
        """
        S = inputs.spot_price
        K = inputs.strike_price or S
        sigma = inputs.volatility or 0.30
        r = inputs.risk_free_rate
        T = inputs.time_to_expiry
        q = inputs.dividend_yield
        
        if T <= 0 or inputs.pricing_type != PricingType.OPTIONS:
            return self._black_scholes(inputs)
        
        # Simuler
        np.random.seed(42)
        z = np.random.standard_normal(simulations)
        ST = S * np.exp((r - q - 0.5 * sigma ** 2) * T + sigma * np.sqrt(T) * z)
        
        # Paiement
        payoffs = np.maximum(ST - K, 0)
        price = np.exp(-r * T) * np.mean(payoffs)
        
        return PricingOutput(
            price=price,
            implied_volatility=sigma,
            delta=0,
            gamma=0,
            theta=0,
            vega=0,
            rho=0,
            probability=0.5
        )
    
    def _heston(self, inputs: PricingInput) -> PricingOutput:
        """
        Modèle Heston (implémentation simplifiée)
        
        Args:
            inputs: Entrées de pricing
            
        Returns:
            PricingOutput: Sorties de pricing
        """
        # Utiliser Black-Scholes comme approximation
        return self._black_scholes(inputs)
    
    def _sabr(self, inputs: PricingInput) -> PricingOutput:
        """
        Modèle SABR (implémentation simplifiée)
        
        Args:
            inputs: Entrées de pricing
            
        Returns:
            PricingOutput: Sorties de pricing
        """
        # Utiliser Black-Scholes comme approximation
        return self._black_scholes(inputs)
    
    def _implied_volatility(self, price: float, inputs: PricingInput) -> float:
        """
        Calcule la volatilité implicite
        
        Args:
            price: Prix de l'option
            inputs: Entrées de pricing
            
        Returns:
            float: Volatilité implicite
        """
        def objective(sigma):
            inputs.volatility = sigma
            return self._black_scholes(inputs).price - price
        
        try:
            from scipy.optimize import brentq
            implied_vol = brentq(objective, 0.01, 5.0)
        except:
            implied_vol = inputs.volatility or 0.30
        
        return implied_vol
    
    # ============================================================
    # YIELD CURVE MANAGEMENT
    # ============================================================
    
    def add_yield_curve(self, name: str, curve: YieldCurve):
        """
        Ajoute une courbe de rendement
        
        Args:
            name: Nom de la courbe
            curve: Courbe de rendement
        """
        with self._lock:
            self.yield_curves[name] = curve
            logger.info(f"Yield curve added: {name}")
    
    def get_yield_curve(self, name: str) -> Optional[YieldCurve]:
        """
        Récupère une courbe de rendement
        
        Args:
            name: Nom de la courbe
            
        Returns:
            Optional[YieldCurve]: Courbe de rendement
        """
        return self.yield_curves.get(name)
    
    def get_rate(self, term: float, curve_name: str = "default") -> float:
        """
        Récupère le taux pour une durée donnée
        
        Args:
            term: Durée
            curve_name: Nom de la courbe
            
        Returns:
            float: Taux
        """
        curve = self.yield_curves.get(curve_name)
        if not curve:
            return 0.02  # Taux par défaut
        
        # Interpolation linéaire
        terms = sorted(curve.rates.keys())
        if term <= terms[0]:
            return curve.rates[terms[0]]
        if term >= terms[-1]:
            return curve.rates[terms[-1]]
        
        for i in range(len(terms) - 1):
            if terms[i] <= term <= terms[i + 1]:
                t1, r1 = terms[i], curve.rates[terms[i]]
                t2, r2 = terms[i + 1], curve.rates[terms[i + 1]]
                return r1 + (r2 - r1) * (term - t1) / (t2 - t1)
        
        return curve.rates[terms[-1]]
    
    # ============================================================
    # VOLATILITY SURFACE
    # ============================================================
    
    def add_volatility_surface(self, name: str, surface: VolatilitySurface):
        """
        Ajoute une surface de volatilité
        
        Args:
            name: Nom de la surface
            surface: Surface de volatilité
        """
        with self._lock:
            self.volatility_surfaces[name] = surface
            logger.info(f"Volatility surface added: {name}")
    
    def get_volatility_surface(self, name: str) -> Optional[VolatilitySurface]:
        """
        Récupère une surface de volatilité
        
        Args:
            name: Nom de la surface
            
        Returns:
            Optional[VolatilitySurface]: Surface de volatilité
        """
        return self.volatility_surfaces.get(name)
    
    def get_volatility(
        self,
        strike: float,
        expiry: float,
        spot: float,
        surface_name: str = "default"
    ) -> float:
        """
        Récupère la volatilité pour un strike et une échéance
        
        Args:
            strike: Prix strike
            expiry: Échéance
            spot: Prix spot
            surface_name: Nom de la surface
            
        Returns:
            float: Volatilité
        """
        surface = self.volatility_surfaces.get(surface_name)
        if not surface:
            return 0.30  # Volatilité par défaut
        
        # Interpolation
        from scipy.interpolate import RegularGridInterpolator
        
        # Normaliser les strikes
        moneyness = np.array(surface.strikes) / spot
        
        # Créer l'interpolateur
        interpolator = RegularGridInterpolator(
            (surface.strikes, surface.expiries),
            surface.volatilities,
            method=surface.interpolation
        )
        
        return float(interpolator([[strike, expiry]])[0])
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def _generate_cache_key(self, inputs: PricingInput) -> str:
        """
        Génère une clé de cache
        
        Args:
            inputs: Entrées de pricing
            
        Returns:
            str: Clé de cache
        """
        key = f"{inputs.pricing_type.value}_{inputs.model.value}_{inputs.spot_price}_{inputs.strike_price}_{inputs.volatility}_{inputs.time_to_expiry}"
        return key
    
    def _update_stats(self, output: PricingOutput, model: PricingModel, pricing_type: PricingType):
        """
        Met à jour les statistiques
        
        Args:
            output: Sorties de pricing
            model: Modèle de pricing
            pricing_type: Type de pricing
        """
        self.stats['total_pricings'] += 1
        
        model_key = model.value
        if model_key not in self.stats['by_model']:
            self.stats['by_model'][model_key] = 0
        self.stats['by_model'][model_key] += 1
        
        type_key = pricing_type.value
        if type_key not in self.stats['by_type']:
            self.stats['by_type'][type_key] = 0
        self.stats['by_type'][type_key] += 1
        
        total = self.stats['total_pricings']
        self.stats['avg_price'] = (self.stats['avg_price'] * (total - 1) + output.price) / total
        self.stats['avg_implied_vol'] = (self.stats['avg_implied_vol'] * (total - 1) + output.implied_volatility) / total
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        with self._lock:
            return self.stats.copy()
    
    def get_report(self) -> Dict[str, Any]:
        """
        Récupère un rapport
        
        Returns:
            Dict[str, Any]: Rapport
        """
        return {
            'timestamp': time.time(),
            'stats': self.get_stats(),
            'recent_prices': [
                {
                    'type': k.split('_')[0],
                    'price': v.price,
                    'implied_vol': v.implied_volatility,
                    'timestamp': v.metadata.get('timestamp'),
                }
                for k, v in list(self.prices.items())[-10:]
            ],
            'yield_curves': list(self.yield_curves.keys()),
            'volatility_surfaces': list(self.volatility_surfaces.keys()),
        }
    
    # ============================================================
    # MONITORING
    # ============================================================
    
    def start(self):
        """Démarre le monitoring"""
        if self._running:
            return
        
        self._running = True
        self._update_task = threading.Thread(target=self._update_loop, daemon=True)
        self._update_task.start()
        
        logger.info("PricingManager monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._update_task:
            self._update_task.join(timeout=2)
        
        logger.info("PricingManager monitoring stopped")
    
    def _update_loop(self):
        """Boucle de mise à jour"""
        while self._running:
            try:
                self._clean_cache()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Update error: {e}")
                time.sleep(self.update_interval)
    
    def _clean_cache(self):
        """Nettoie le cache"""
        now = time.time()
        for key in list(self._cache.keys()):
            if now - self._cache[key].metadata.get('timestamp', 0) > self._cache_ttl:
                del self._cache[key]

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_pricing_manager: Optional[PricingManager] = None

def get_pricing_manager(
    config: Optional[Dict[str, Any]] = None
) -> PricingManager:
    """
    Récupère le gestionnaire de prix (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        PricingManager: Gestionnaire de prix
    """
    global _pricing_manager
    if _pricing_manager is None:
        _pricing_manager = PricingManager(config)
    return _pricing_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'PricingModel',
    'PricingType',
    'VolatilityModel',
    'PricingInput',
    'PricingOutput',
    'YieldCurve',
    'VolatilitySurface',
    'PricingManager',
    'get_pricing_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Pricing manager module initialized")
