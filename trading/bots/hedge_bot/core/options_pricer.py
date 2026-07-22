"""
NEXUS AI TRADING SYSTEM - Hedge Bot Options Pricer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Calculateur de prix d'options pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import math
import logging
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class OptionType(Enum):
    """Types d'options"""
    CALL = "call"
    PUT = "put"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    SPREAD = "spread"
    COLLAR = "collar"
    BUTTERFLY = "butterfly"
    CONDOR = "condor"

class OptionStyle(Enum):
    """Styles d'options"""
    EUROPEAN = "european"
    AMERICAN = "american"
    BERMUDAN = "bermudan"
    EXOTIC = "exotic"

class OptionSettlement(Enum):
    """Types de règlement"""
    PHYSICAL = "physical"
    CASH = "cash"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class OptionInput:
    """Entrées pour le pricing d'options"""
    spot_price: float
    strike_price: float
    volatility: float
    risk_free_rate: float
    time_to_expiry: float  # en années
    dividend_yield: float = 0.0
    option_type: OptionType = OptionType.CALL
    option_style: OptionStyle = OptionStyle.EUROPEAN
    settlement: OptionSettlement = OptionSettlement.CASH
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OptionOutput:
    """Sorties du pricing d'options"""
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_volatility: float
    intrinsic_value: float
    time_value: float
    probability: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GreeksOutput:
    """Sorties des grecques"""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    lambda_val: float
    epsilon: float
    zeta: float
    eta: float
    iota: float
    kappa: float
    mu: float
    nu: float
    xi: float
    omicron: float
    pi: float
    sigma: float
    tau: float
    upsilon: float
    phi: float
    chi: float
    psi: float
    omega: float

@dataclass
class OptionPosition:
    """Position d'options"""
    id: str
    symbol: str
    option_type: OptionType
    strike_price: float
    expiry: datetime
    size: int
    entry_price: float
    current_price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    pnl: float
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# OPTIONS PRICER
# ============================================================

class OptionsPricer:
    """
    Calculateur de prix d'options pour le bot de couverture
    
    Implémente Black-Scholes et d'autres modèles de pricing
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise le calculateur d'options
        
        Args:
            config: Configuration
        """
        self.config = config or {}
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Modèles disponibles
        self.models = {
            'black_scholes': self._black_scholes,
            'black_scholes_merton': self._black_scholes_merton,
            'binomial': self._binomial_tree,
            'monte_carlo': self._monte_carlo,
        }
        
        logger.info("OptionsPricer initialized")
    
    # ============================================================
    # BLACK-SCHOLES MODEL
    # ============================================================
    
    def price(self, inputs: OptionInput) -> OptionOutput:
        """
        Calcule le prix d'une option
        
        Args:
            inputs: Entrées du pricing
            
        Returns:
            OptionOutput: Résultat du pricing
        """
        # Vérifier le cache
        cache_key = self._generate_cache_key(inputs)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Choisir le modèle
        if inputs.option_style == OptionStyle.EUROPEAN:
            price, greeks = self._black_scholes(inputs)
        elif inputs.option_style == OptionStyle.AMERICAN:
            price, greeks = self._binomial_tree(inputs)
        else:
            price, greeks = self._monte_carlo(inputs)
        
        # Calculer les valeurs supplémentaires
        intrinsic_value = self._intrinsic_value(inputs)
        time_value = price - intrinsic_value
        
        # Volatilité implicite
        implied_vol = self._implied_volatility(inputs, price)
        
        # Probabilité
        probability = self._probability(inputs)
        
        output = OptionOutput(
            price=price,
            delta=greeks.delta,
            gamma=greeks.gamma,
            theta=greeks.theta,
            vega=greeks.vega,
            rho=greeks.rho,
            implied_volatility=implied_vol,
            intrinsic_value=intrinsic_value,
            time_value=time_value,
            probability=probability
        )
        
        # Mettre en cache
        self.cache[cache_key] = output
        
        return output
    
    def _black_scholes(self, inputs: OptionInput) -> Tuple[float, GreeksOutput]:
        """
        Modèle Black-Scholes
        
        Args:
            inputs: Entrées du pricing
            
        Returns:
            Tuple[float, GreeksOutput]: Prix et grecques
        """
        S = inputs.spot_price
        K = inputs.strike_price
        sigma = inputs.volatility
        r = inputs.risk_free_rate
        T = inputs.time_to_expiry
        q = inputs.dividend_yield
        option_type = inputs.option_type
        
        if T <= 0:
            return self._zero_greeks(option_type, S, K)
        
        # Calculs de base
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        # Densité et cumulative
        nd1 = norm.pdf(d1)
        nd2 = norm.pdf(d2)
        
        if option_type == OptionType.CALL:
            N_d1 = norm.cdf(d1)
            N_d2 = norm.cdf(d2)
            
            # Prix
            price = S * math.exp(-q * T) * N_d1 - K * math.exp(-r * T) * N_d2
            
            # Grecques
            delta = math.exp(-q * T) * N_d1
            gamma = math.exp(-q * T) * nd1 / (S * sigma * math.sqrt(T))
            theta = -(S * sigma * math.exp(-q * T) * nd1) / (2 * math.sqrt(T)) - \
                    r * K * math.exp(-r * T) * N_d2 + \
                    q * S * math.exp(-q * T) * N_d1
            vega = S * math.exp(-q * T) * nd1 * math.sqrt(T)
            rho = K * T * math.exp(-r * T) * N_d2
            
        elif option_type == OptionType.PUT:
            N_neg_d1 = norm.cdf(-d1)
            N_neg_d2 = norm.cdf(-d2)
            
            # Prix
            price = K * math.exp(-r * T) * N_neg_d2 - S * math.exp(-q * T) * N_neg_d1
            
            # Grecques
            delta = -math.exp(-q * T) * N_neg_d1
            gamma = math.exp(-q * T) * nd1 / (S * sigma * math.sqrt(T))
            theta = -(S * sigma * math.exp(-q * T) * nd1) / (2 * math.sqrt(T)) + \
                    r * K * math.exp(-r * T) * N_neg_d2 - \
                    q * S * math.exp(-q * T) * N_neg_d1
            vega = S * math.exp(-q * T) * nd1 * math.sqrt(T)
            rho = -K * T * math.exp(-r * T) * N_neg_d2
            
        else:
            raise ValueError(f"Unsupported option type: {option_type}")
        
        greeks = GreeksOutput(
            delta=delta,
            gamma=gamma,
            theta=theta / 365,
            vega=vega / 100,
            rho=rho / 100,
            lambda_val=0,
            epsilon=0,
            zeta=0,
            eta=0,
            iota=0,
            kappa=0,
            mu=0,
            nu=0,
            xi=0,
            omicron=0,
            pi=0,
            sigma=0,
            tau=0,
            upsilon=0,
            phi=0,
            chi=0,
            psi=0,
            omega=0
        )
        
        return price, greeks
    
    def _black_scholes_merton(self, inputs: OptionInput) -> Tuple[float, GreeksOutput]:
        """
        Modèle Black-Scholes-Merton (avec dividendes)
        
        Args:
            inputs: Entrées du pricing
            
        Returns:
            Tuple[float, GreeksOutput]: Prix et grecques
        """
        # Même que Black-Scholes avec dividendes
        return self._black_scholes(inputs)
    
    def _binomial_tree(self, inputs: OptionInput, steps: int = 100) -> Tuple[float, GreeksOutput]:
        """
        Arbre binomial pour options américaines
        
        Args:
            inputs: Entrées du pricing
            steps: Nombre de pas
            
        Returns:
            Tuple[float, GreeksOutput]: Prix et grecques
        """
        S = inputs.spot_price
        K = inputs.strike_price
        sigma = inputs.volatility
        r = inputs.risk_free_rate
        T = inputs.time_to_expiry
        q = inputs.dividend_yield
        option_type = inputs.option_type
        
        if T <= 0:
            return self._zero_greeks(option_type, S, K)
        
        # Paramètres de l'arbre
        dt = T / steps
        u = math.exp(sigma * math.sqrt(dt))
        d = 1 / u
        p = (math.exp((r - q) * dt) - d) / (u - d)
        
        # Prix à l'échéance
        prices = np.zeros(steps + 1)
        for i in range(steps + 1):
            prices[i] = S * (u ** (steps - i)) * (d ** i)
        
        # Valeurs à l'échéance
        if option_type == OptionType.CALL:
            values = np.maximum(prices - K, 0)
        else:
            values = np.maximum(K - prices, 0)
        
        # Backward induction
        for step in range(steps - 1, -1, -1):
            values = np.exp(-r * dt) * (p * values[:-1] + (1 - p) * values[1:])
            if option_type == OptionType.CALL:
                values = np.maximum(values, S * (u ** (step)) * (d ** (steps - step)) - K)
            else:
                values = np.maximum(values, K - S * (u ** (step)) * (d ** (steps - step)))
        
        price = values[0]
        
        # Grecques approximatives
        greeks = self._approximate_greeks(inputs, price)
        
        return price, greeks
    
    def _monte_carlo(self, inputs: OptionInput, simulations: int = 10000) -> Tuple[float, GreeksOutput]:
        """
        Simulation Monte Carlo
        
        Args:
            inputs: Entrées du pricing
            simulations: Nombre de simulations
            
        Returns:
            Tuple[float, GreeksOutput]: Prix et grecques
        """
        S = inputs.spot_price
        K = inputs.strike_price
        sigma = inputs.volatility
        r = inputs.risk_free_rate
        T = inputs.time_to_expiry
        q = inputs.dividend_yield
        option_type = inputs.option_type
        
        if T <= 0:
            return self._zero_greeks(option_type, S, K)
        
        # Simuler les prix
        np.random.seed(42)
        z = np.random.standard_normal(simulations)
        ST = S * np.exp((r - q - 0.5 * sigma ** 2) * T + sigma * np.sqrt(T) * z)
        
        # Paiement
        if option_type == OptionType.CALL:
            payoffs = np.maximum(ST - K, 0)
        else:
            payoffs = np.maximum(K - ST, 0)
        
        # Prix
        price = np.exp(-r * T) * np.mean(payoffs)
        
        # Grecques approximatives
        greeks = self._approximate_greeks(inputs, price)
        
        return price, greeks
    
    def _approximate_greeks(self, inputs: OptionInput, price: float) -> GreeksOutput:
        """
        Calcule les grecques approximatives
        
        Args:
            inputs: Entrées du pricing
            price: Prix de l'option
            
        Returns:
            GreeksOutput: Grecques approximatives
        """
        # Delta approximatif
        epsilon = 0.001
        inputs_up = OptionInput(
            spot_price=inputs.spot_price * (1 + epsilon),
            strike_price=inputs.strike_price,
            volatility=inputs.volatility,
            risk_free_rate=inputs.risk_free_rate,
            time_to_expiry=inputs.time_to_expiry,
            dividend_yield=inputs.dividend_yield,
            option_type=inputs.option_type
        )
        price_up = self.price(inputs_up).price
        
        delta = (price_up - price) / (inputs.spot_price * epsilon)
        
        # Gamma approximatif
        inputs_down = OptionInput(
            spot_price=inputs.spot_price * (1 - epsilon),
            strike_price=inputs.strike_price,
            volatility=inputs.volatility,
            risk_free_rate=inputs.risk_free_rate,
            time_to_expiry=inputs.time_to_expiry,
            dividend_yield=inputs.dividend_yield,
            option_type=inputs.option_type
        )
        price_down = self.price(inputs_down).price
        
        gamma = (price_up - 2 * price + price_down) / (inputs.spot_price * epsilon) ** 2
        
        return GreeksOutput(
            delta=delta,
            gamma=gamma,
            theta=0,
            vega=0,
            rho=0,
            lambda_val=0,
            epsilon=0,
            zeta=0,
            eta=0,
            iota=0,
            kappa=0,
            mu=0,
            nu=0,
            xi=0,
            omicron=0,
            pi=0,
            sigma=0,
            tau=0,
            upsilon=0,
            phi=0,
            chi=0,
            psi=0,
            omega=0
        )
    
    def _zero_greeks(self, option_type: OptionType, S: float, K: float) -> Tuple[float, GreeksOutput]:
        """
        Retourne des grecques nulles pour T <= 0
        
        Args:
            option_type: Type d'option
            S: Prix spot
            K: Prix strike
            
        Returns:
            Tuple[float, GreeksOutput]: Prix et grecques
        """
        if option_type == OptionType.CALL:
            price = max(S - K, 0)
        else:
            price = max(K - S, 0)
        
        return price, GreeksOutput(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
    
    # ============================================================
    # IMPLIED VOLATILITY
    # ============================================================
    
    def _implied_volatility(self, inputs: OptionInput, price: float) -> float:
        """
        Calcule la volatilité implicite
        
        Args:
            inputs: Entrées du pricing
            price: Prix de l'option
            
        Returns:
            float: Volatilité implicite
        """
        def objective(sigma):
            inputs.volatility = sigma
            return self.price(inputs).price - price
        
        try:
            implied_vol = brentq(objective, 0.01, 5.0)
        except:
            implied_vol = 0.30
        
        return implied_vol
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def _intrinsic_value(self, inputs: OptionInput) -> float:
        """
        Calcule la valeur intrinsèque
        
        Args:
            inputs: Entrées du pricing
            
        Returns:
            float: Valeur intrinsèque
        """
        S = inputs.spot_price
        K = inputs.strike_price
        
        if inputs.option_type == OptionType.CALL:
            return max(S - K, 0)
        else:
            return max(K - S, 0)
    
    def _probability(self, inputs: OptionInput) -> float:
        """
        Calcule la probabilité de profit
        
        Args:
            inputs: Entrées du pricing
            
        Returns:
            float: Probabilité
        """
        S = inputs.spot_price
        K = inputs.strike_price
        sigma = inputs.volatility
        r = inputs.risk_free_rate
        T = inputs.time_to_expiry
        q = inputs.dividend_yield
        
        if T <= 0:
            return 0.5
        
        if inputs.option_type == OptionType.CALL:
            d2 = (math.log(S / K) + (r - q - 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            return norm.cdf(d2)
        else:
            d2 = (math.log(S / K) + (r - q - 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            return 1 - norm.cdf(d2)
    
    def _generate_cache_key(self, inputs: OptionInput) -> str:
        """
        Génère une clé de cache
        
        Args:
            inputs: Entrées du pricing
            
        Returns:
            str: Clé de cache
        """
        key = f"{inputs.spot_price}_{inputs.strike_price}_{inputs.volatility}_{inputs.risk_free_rate}_{inputs.time_to_expiry}_{inputs.option_type.value}"
        return key
    
    # ============================================================
    # POSITION MANAGEMENT
    # ============================================================
    
    def create_position(
        self,
        symbol: str,
        option_type: OptionType,
        strike_price: float,
        expiry: datetime,
        size: int,
        entry_price: float,
        inputs: OptionInput
    ) -> OptionPosition:
        """
        Crée une position d'options
        
        Args:
            symbol: Symbole
            option_type: Type d'option
            strike_price: Prix strike
            expiry: Date d'expiration
            size: Taille
            entry_price: Prix d'entrée
            inputs: Entrées du pricing
            
        Returns:
            OptionPosition: Position créée
        """
        # Calculer les grecques
        output = self.price(inputs)
        
        position = OptionPosition(
            id=f"opt_pos_{int(time.time())}_{symbol}",
            symbol=symbol,
            option_type=option_type,
            strike_price=strike_price,
            expiry=expiry,
            size=size,
            entry_price=entry_price,
            current_price=entry_price,
            delta=output.delta * size,
            gamma=output.gamma * size,
            theta=output.theta * size,
            vega=output.vega * size,
            pnl=0.0,
            metadata={'greeks': output.__dict__}
        )
        
        return position

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_options_pricer: Optional[OptionsPricer] = None

def get_options_pricer(
    config: Optional[Dict[str, Any]] = None
) -> OptionsPricer:
    """
    Récupère le calculateur d'options (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        OptionsPricer: Calculateur d'options
    """
    global _options_pricer
    if _options_pricer is None:
        _options_pricer = OptionsPricer(config)
    return _options_pricer

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'OptionType',
    'OptionStyle',
    'OptionSettlement',
    'OptionInput',
    'OptionOutput',
    'GreeksOutput',
    'OptionPosition',
    'OptionsPricer',
    'get_options_pricer',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Options pricer module initialized")
