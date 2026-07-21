"""
NEXUS AI TRADING SYSTEM - Hedge Bot Gamma Calculator
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Calculateur de gamma pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import math
import numpy as np
from scipy.stats import norm
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

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

class GammaType(Enum):
    """Types de gamma"""
    SPOT = "spot"
    FUTURES = "futures"
    FORWARD = "forward"
    EXOTIC = "exotic"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class GammaInput:
    """Entrées pour le calcul de gamma"""
    spot_price: float
    strike_price: float
    volatility: float
    risk_free_rate: float
    time_to_expiry: float  # en années
    dividend_yield: float = 0.0
    option_type: OptionType = OptionType.CALL
    gamma_type: GammaType = GammaType.SPOT

@dataclass
class GammaOutput:
    """Sorties du calcul de gamma"""
    gamma: float
    delta: float
    theta: float
    vega: float
    rho: float
    gamma_pnl: float
    delta_pnl: float
    theta_pnl: float
    vega_pnl: float
    total_pnl: float
    breakeven: float
    probability: float

@dataclass
class GammaPosition:
    """Position gamma"""
    id: str
    symbol: str
    option_type: OptionType
    strike_price: float
    expiry: float
    size: int
    gamma: float
    delta: float
    theta: float
    vega: float
    entry_price: float
    current_price: float
    pnl: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GammaMetrics:
    """Métriques gamma"""
    total_gamma: float
    total_delta: float
    total_theta: float
    total_vega: float
    gamma_exposure: float
    gamma_skew: float
    gamma_concentration: float
    gamma_hedge_ratio: float
    gamma_effectiveness: float

# ============================================================
# GAMMA CALCULATOR
# ============================================================

class GammaCalculator:
    """
    Calculateur de gamma pour le bot de couverture
    
    Calcule le gamma, delta, theta, vega et rho pour les options
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise le calculateur de gamma
        
        Args:
            config: Configuration
        """
        self.config = config or {}
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        logger.info("GammaCalculator initialized")
    
    # ============================================================
    # BLACK-SCHOLES CALCULATIONS
    # ============================================================
    
    def calculate_greeks(self, inputs: GammaInput) -> GammaOutput:
        """
        Calcule les grecques avec Black-Scholes
        
        Args:
            inputs: Entrées de calcul
            
        Returns:
            GammaOutput: Grecques calculées
        """
        S = inputs.spot_price
        K = inputs.strike_price
        sigma = inputs.volatility
        r = inputs.risk_free_rate
        T = inputs.time_to_expiry
        q = inputs.dividend_yield
        option_type = inputs.option_type
        
        if T <= 0:
            return self._zero_output()
        
        # Calculs de base
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        # Call greeks
        if option_type == OptionType.CALL:
            delta = norm.cdf(d1) * math.exp(-q * T)
            gamma = norm.pdf(d1) * math.exp(-q * T) / (S * sigma * math.sqrt(T))
            theta = -(S * sigma * math.exp(-q * T) * norm.pdf(d1)) / (2 * math.sqrt(T)) - \
                    r * K * math.exp(-r * T) * norm.cdf(d2) + \
                    q * S * math.exp(-q * T) * norm.cdf(d1)
            vega = S * math.exp(-q * T) * norm.pdf(d1) * math.sqrt(T)
            rho = K * T * math.exp(-r * T) * norm.cdf(d2)
        
        # Put greeks
        else:
            delta = -norm.cdf(-d1) * math.exp(-q * T)
            gamma = norm.pdf(d1) * math.exp(-q * T) / (S * sigma * math.sqrt(T))
            theta = -(S * sigma * math.exp(-q * T) * norm.pdf(d1)) / (2 * math.sqrt(T)) + \
                    r * K * math.exp(-r * T) * norm.cdf(-d2) - \
                    q * S * math.exp(-q * T) * norm.cdf(-d1)
            vega = S * math.exp(-q * T) * norm.pdf(d1) * math.sqrt(T)
            rho = -K * T * math.exp(-r * T) * norm.cdf(-d2)
        
        # Probabilité
        prob = norm.cdf(d2) if option_type == OptionType.CALL else norm.cdf(-d2)
        
        # PNL (pour 1 option)
        if option_type == OptionType.CALL:
            option_price = S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        else:
            option_price = K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)
        
        # Breakeven
        breakeven = K + option_price if option_type == OptionType.CALL else K - option_price
        
        return GammaOutput(
            gamma=gamma,
            delta=delta,
            theta=theta / 365,  # par jour
            vega=vega / 100,    # par 1% de volatilité
            rho=rho / 100,      # par 1% de taux
            gamma_pnl=0.0,
            delta_pnl=0.0,
            theta_pnl=0.0,
            vega_pnl=0.0,
            total_pnl=0.0,
            breakeven=breakeven,
            probability=prob
        )
    
    def _zero_output(self) -> GammaOutput:
        """Retourne des grecques nulles"""
        return GammaOutput(
            gamma=0.0,
            delta=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
            gamma_pnl=0.0,
            delta_pnl=0.0,
            theta_pnl=0.0,
            vega_pnl=0.0,
            total_pnl=0.0,
            breakeven=0.0,
            probability=0.0
        )
    
    # ============================================================
    # GREEKS PNL
    # ============================================================
    
    def calculate_greeks_pnl(
        self,
        greeks: GammaOutput,
        spot_change: float,
        vol_change: float,
        rate_change: float,
        time_change: float
    ) -> Dict[str, float]:
        """
        Calcule le PNL des grecques
        
        Args:
            greeks: Grecques calculées
            spot_change: Variation du spot
            vol_change: Variation de la volatilité
            rate_change: Variation du taux
            time_change: Variation du temps
            
        Returns:
            Dict[str, float]: PNL par grecque
        """
        # Gamma PNL (approximation)
        gamma_pnl = 0.5 * greeks.gamma * spot_change ** 2
        
        # Delta PNL
        delta_pnl = greeks.delta * spot_change
        
        # Theta PNL
        theta_pnl = greeks.theta * time_change
        
        # Vega PNL
        vega_pnl = greeks.vega * vol_change
        
        # Rho PNL
        rho_pnl = greeks.rho * rate_change
        
        total_pnl = gamma_pnl + delta_pnl + theta_pnl + vega_pnl + rho_pnl
        
        return {
            'gamma_pnl': gamma_pnl,
            'delta_pnl': delta_pnl,
            'theta_pnl': theta_pnl,
            'vega_pnl': vega_pnl,
            'rho_pnl': rho_pnl,
            'total_pnl': total_pnl
        }
    
    # ============================================================
    # GAMMA HEDGING
    # ============================================================
    
    def calculate_gamma_hedge(
        self,
        gamma: float,
        hedge_gamma: float,
        delta: float = 0.0,
        hedge_delta: float = 0.0
    ) -> Dict[str, float]:
        """
        Calcule la couverture gamma
        
        Args:
            gamma: Gamma à couvrir
            hedge_gamma: Gamma de l'instrument de couverture
            delta: Delta à couvrir
            hedge_delta: Delta de l'instrument de couverture
            
        Returns:
            Dict[str, float]: Couverture calculée
        """
        # Couverture gamma
        gamma_hedge_ratio = -gamma / hedge_gamma if hedge_gamma != 0 else 0
        
        # Couverture delta
        delta_hedge_ratio = -(delta + gamma_hedge_ratio * hedge_delta) / hedge_delta if hedge_delta != 0 else 0
        
        return {
            'gamma_hedge_ratio': gamma_hedge_ratio,
            'delta_hedge_ratio': delta_hedge_ratio,
            'total_hedge_ratio': gamma_hedge_ratio + delta_hedge_ratio
        }
    
    def calculate_gamma_scalping(
        self,
        gamma: float,
        spot_price: float,
        spot_move: float,
        delta_threshold: float = 0.01
    ) -> Dict[str, Any]:
        """
        Calcule le gamma scalping
        
        Args:
            gamma: Gamma de la position
            spot_price: Prix du spot
            spot_move: Mouvement du spot
            delta_threshold: Seuil de delta
            
        Returns:
            Dict[str, Any]: Résultats du gamma scalping
        """
        # Delta change
        delta_change = gamma * spot_move
        
        # Nombre de rééquilibrages
        rebalance_count = abs(delta_change) / delta_threshold
        
        # Profit du scalping
        scalping_profit = 0.5 * gamma * spot_move ** 2 * rebalance_count
        
        return {
            'delta_change': delta_change,
            'rebalance_count': rebalance_count,
            'scalping_profit': scalping_profit,
            'threshold': delta_threshold
        }
    
    # ============================================================
    # GAMMA POSITIONS
    # ============================================================
    
    def create_gamma_position(
        self,
        symbol: str,
        option_type: OptionType,
        strike_price: float,
        expiry: float,
        size: int,
        entry_price: float
    ) -> GammaPosition:
        """
        Crée une position gamma
        
        Args:
            symbol: Symbole
            option_type: Type d'option
            strike_price: Prix d'exercice
            expiry: Temps jusqu'à l'expiration
            size: Taille
            entry_price: Prix d'entrée
            
        Returns:
            GammaPosition: Position gamma
        """
        # Calculer les grecques
        inputs = GammaInput(
            spot_price=entry_price,
            strike_price=strike_price,
            volatility=0.30,  # Volatilité implicite par défaut
            risk_free_rate=0.05,  # Taux sans risque par défaut
            time_to_expiry=expiry,
            option_type=option_type
        )
        
        greeks = self.calculate_greeks(inputs)
        
        position = GammaPosition(
            id=f"gamma_pos_{int(time.time())}_{symbol}",
            symbol=symbol,
            option_type=option_type,
            strike_price=strike_price,
            expiry=expiry,
            size=size,
            gamma=greeks.gamma * size,
            delta=greeks.delta * size,
            theta=greeks.theta * size,
            vega=greeks.vega * size,
            entry_price=entry_price,
            current_price=entry_price,
            pnl=0.0,
            metadata={
                'greeks': greeks.__dict__,
                'entry_time': time.time()
            }
        )
        
        return position
    
    def update_gamma_position(
        self,
        position: GammaPosition,
        current_price: float,
        volatility: float = None
    ) -> GammaPosition:
        """
        Met à jour une position gamma
        
        Args:
            position: Position gamma
            current_price: Prix actuel
            volatility: Volatilité implicite
            
        Returns:
            GammaPosition: Position mise à jour
        """
        # Calculer les grecques
        inputs = GammaInput(
            spot_price=current_price,
            strike_price=position.strike_price,
            volatility=volatility or 0.30,
            risk_free_rate=0.05,
            time_to_expiry=position.expiry - (time.time() - position.metadata.get('entry_time', time.time())) / 365,
            option_type=position.option_type
        )
        
        greeks = self.calculate_greeks(inputs)
        
        # Mettre à jour
        position.current_price = current_price
        position.gamma = greeks.gamma * position.size
        position.delta = greeks.delta * position.size
        position.theta = greeks.theta * position.size
        position.vega = greeks.vega * position.size
        
        # Calculer PNL
        price_change = current_price - position.entry_price
        pnl_change = position.delta * price_change + 0.5 * position.gamma * price_change ** 2
        position.pnl += pnl_change
        
        position.metadata['greeks'] = greeks.__dict__
        position.metadata['last_update'] = time.time()
        
        return position
    
    # ============================================================
    # GAMMA METRICS
    # ============================================================
    
    def calculate_gamma_metrics(
        self,
        positions: List[GammaPosition],
        spot_price: float
    ) -> GammaMetrics:
        """
        Calcule les métriques gamma
        
        Args:
            positions: Liste des positions gamma
            spot_price: Prix du spot
            
        Returns:
            GammaMetrics: Métriques gamma
        """
        total_gamma = sum(p.gamma for p in positions)
        total_delta = sum(p.delta for p in positions)
        total_theta = sum(p.theta for p in positions)
        total_vega = sum(p.vega for p in positions)
        
        # Exposition gamma
        gamma_exposure = total_gamma * spot_price
        
        # Skew gamma (répartition des strikes)
        strikes = [p.strike_price for p in positions]
        if strikes:
            gamma_skew = np.std(strikes) / np.mean(strikes) if np.mean(strikes) > 0 else 0
        else:
            gamma_skew = 0
        
        # Concentration gamma (Herfindahl)
        gamma_values = [p.gamma for p in positions]
        if gamma_values and sum(gamma_values) > 0:
            gamma_concentration = sum((g / sum(gamma_values)) ** 2 for g in gamma_values)
        else:
            gamma_concentration = 0
        
        return GammaMetrics(
            total_gamma=total_gamma,
            total_delta=total_delta,
            total_theta=total_theta,
            total_vega=total_vega,
            gamma_exposure=gamma_exposure,
            gamma_skew=gamma_skew,
            gamma_concentration=gamma_concentration,
            gamma_hedge_ratio=0.0,
            gamma_effectiveness=0.0
        )
    
    # ============================================================
    # CACHE AND HISTORY
    # ============================================================
    
    def clear_cache(self):
        """Vide le cache"""
        self.cache.clear()
    
    def add_history(self, entry: Dict[str, Any]):
        """
        Ajoute une entrée à l'historique
        
        Args:
            entry: Entrée à ajouter
        """
        self.history.append(entry)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
    
    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Récupère l'historique
        
        Args:
            limit: Nombre d'entrées
            
        Returns:
            List[Dict[str, Any]]: Historique
        """
        return self.history[-limit:]

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_gamma_calculator: Optional[GammaCalculator] = None

def get_gamma_calculator(
    config: Optional[Dict[str, Any]] = None
) -> GammaCalculator:
    """
    Récupère le calculateur de gamma (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        GammaCalculator: Calculateur de gamma
    """
    global _gamma_calculator
    if _gamma_calculator is None:
        _gamma_calculator = GammaCalculator(config)
    return _gamma_calculator

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'OptionType',
    'GammaType',
    'GammaInput',
    'GammaOutput',
    'GammaPosition',
    'GammaMetrics',
    'GammaCalculator',
    'get_gamma_calculator',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Gamma calculator module initialized")
